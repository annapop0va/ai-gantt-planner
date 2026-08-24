"""AgentService — the natural-language editing loop.

Flow (product-spec §13, integration brief): validate the request cheaply
before spending any tokens -> bounded conversation history -> OpenRouter with
the system prompt + allow-listed MCP tools -> the model's tool_calls,
executed one at a time through `BoundMcpToolGateway` (which is the only path
to the real MCP `apply_change_set`, which is the only path to
`ProjectService.apply_change_set()`) -> at most one successful mutation ->
optional short wrap-up completion with tools disabled, or a deterministic
fallback if that fails.

AgentService never calls `ProjectService.apply_change_set()` directly — only
`BoundMcpToolGateway.call("apply_change_set", ...)` does, which goes through
the mounted MCP server. See docs/mcp-agent-architecture.md for why.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette

from app.agent.ambiguity_guard import SearchCandidate, evaluate_ambiguity
from app.agent.conversation_store import InMemoryAgentConversationStore
from app.agent.gateway import MUTATION_TOOL, READ_TOOLS, BoundMcpToolGateway, ToolCallOutcome
from app.agent.openrouter_client import OpenRouterClient
from app.agent.system_prompt import SYSTEM_PROMPT
from app.domain.diff import ChangeSummary
from app.domain.errors import (
    AgentError,
    AgentInvalidToolCallError,
    AgentStepLimitError,
    AiNotConfiguredError,
    McpUnavailableError,
    RevisionConflictError,
)
from app.services.project_service import ProjectService
from app.settings import Settings

logger = logging.getLogger("ai_gantt_planner.agent")

AgentTurnStatus = Literal["applied", "clarification_required", "rejected"]

_FALLBACK_APPLIED_MESSAGE = "План обновлён."
# FastMCP auto-enables DNS-rebinding protection for the default 127.0.0.1/
# localhost host: allowed_hosts is ["127.0.0.1:*", "localhost:*", "[::1]:*"]
# — note the ":*" suffix requires an actual port in the Host header, so a
# bare "localhost" (no port) is rejected with 421 just like a made-up
# hostname would be. Using the real server port here is not load-bearing
# (ASGITransport never opens a socket) but keeps the Host header meaningful.
_MCP_INTERNAL_BASE_URL = "http://localhost:8000/"


@dataclass(frozen=True)
class AgentTurnResult:
    status: AgentTurnStatus
    message: str
    change_summary: ChangeSummary | None
    warnings: list[str]


class AgentService:
    def __init__(
        self,
        *,
        settings: Settings,
        project_service: ProjectService,
        mcp_asgi_app: Starlette,
        conversation_store: InMemoryAgentConversationStore,
        openrouter_client: OpenRouterClient | None = None,
    ) -> None:
        self._settings = settings
        self._project_service = project_service
        self._mcp_asgi_app = mcp_asgi_app
        self._conversations = conversation_store
        self._client = openrouter_client or OpenRouterClient(settings)

    async def run_turn(self, *, project_id: uuid.UUID, message: str, expected_revision: int) -> AgentTurnResult:
        if not self._settings.ai_configured:
            raise AiNotConfiguredError(
                "OPENROUTER_API_KEY and OPENROUTER_MODEL must both be set to use the AI chat."
            )

        # Cheap advisory check before spending any tokens. The atomic, truthful
        # check happens again inside ProjectService.apply_change_set()'s lock
        # when/if the model actually calls apply_change_set — this one only
        # avoids paying for a whole agent run against a request we already
        # know is stale.
        current = await self._project_service.get_project(project_id)
        if current.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, project is at revision {current.revision}.",
                details=[{"expected": expected_revision, "actual": current.revision}],
            )

        history = self._conversations.get_history(project_id)
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend({"role": turn.role, "content": turn.content} for turn in history)
        messages.append({"role": "user", "content": message})

        try:
            async with self._mcp_session() as session:
                gateway = BoundMcpToolGateway(
                    session, project_id=str(project_id), expected_revision=expected_revision
                )
                result = await self._run_loop(messages, gateway, user_message=message)
        except Exception as exc:  # noqa: BLE001 - unwrapped below; re-raised as-is or wrapped
            # anyio task groups (used internally by the MCP session/transport)
            # wrap even a single exception that escapes their `async with`
            # block in a BaseExceptionGroup — including our own AgentError
            # subclasses raised deep inside `_run_loop`. Unwrap one level so
            # those keep their real type instead of all becoming
            # McpUnavailableError.
            unwrapped = _unwrap_single_exception(exc)
            if isinstance(unwrapped, AgentError):
                raise unwrapped from exc
            logger.warning("mcp_session_failed error=%s", unwrapped)
            raise McpUnavailableError(f"Could not use the MCP tool server: {unwrapped}") from exc

        self._conversations.append_turn(project_id, user_message=message, assistant_message=result.message)
        return result

    # -- the loop -----------------------------------------------------------------

    async def _run_loop(
        self, messages: list[dict[str, Any]], gateway: BoundMcpToolGateway, *, user_message: str
    ) -> AgentTurnResult:
        tools = gateway.model_tool_definitions()

        mutated = False
        change_summary: ChangeSummary | None = None
        last_rejection: str | None = None
        read_tool_calls = 0
        correction_used = False
        warnings: list[str] = []
        last_search_candidates: list[SearchCandidate] | None = None

        for step in range(self._settings.agent_max_steps):
            completion = await self._client.chat_completion(
                messages=messages, tools=None if mutated else tools
            )
            assistant_message = completion.message
            messages.append(_sanitize_assistant_message(assistant_message))

            tool_calls = assistant_message.get("tool_calls") or []

            if not tool_calls:
                final_text = (assistant_message.get("content") or "").strip()
                if mutated:
                    return AgentTurnResult(
                        status="applied",
                        message=final_text or _FALLBACK_APPLIED_MESSAGE,
                        change_summary=change_summary,
                        warnings=warnings,
                    )
                if last_rejection is not None:
                    return AgentTurnResult(
                        status="rejected", message=final_text or last_rejection, change_summary=None, warnings=[]
                    )
                return AgentTurnResult(
                    status="clarification_required",
                    message=final_text or "Уточните, пожалуйста, запрос.",
                    change_summary=None,
                    warnings=[],
                )

            if mutated:
                # Tools were not offered this step (tools=None above), so a
                # tool_calls entry here would be a model hallucination — ignore
                # it and treat whatever text came back as the wrap-up message.
                final_text = (assistant_message.get("content") or "").strip()
                return AgentTurnResult(
                    status="applied",
                    message=final_text or _FALLBACK_APPLIED_MESSAGE,
                    change_summary=change_summary,
                    warnings=warnings,
                )

            if len(tool_calls) > 1:
                if correction_used:
                    raise AgentInvalidToolCallError(
                        "Model proposed multiple tool calls in one turn more than once."
                    )
                correction_used = True
                for call in tool_calls:
                    messages.append(_tool_result_message(call["id"], {
                        "ok": False,
                        "code": "AGENT_INVALID_TOOL_CALL",
                        "message": "Only one tool call is allowed per turn. Call exactly one tool, then wait for its result.",
                    }))
                continue

            call = tool_calls[0]
            name = call["function"]["name"]
            call_id = call["id"]
            arguments_json = call["function"].get("arguments") or "{}"

            if name in READ_TOOLS:
                if read_tool_calls >= self._settings.agent_max_read_tool_calls:
                    raise AgentStepLimitError("Reached the maximum number of read tool calls for this request.")
                read_tool_calls += 1

            if name == MUTATION_TOOL and last_search_candidates:
                # Deterministic, code-level guard: even if the model ignores
                # the system prompt's "ask, don't guess" instruction, a
                # mutation that would resolve an unflagged name ambiguity
                # itself never reaches the MCP server at all — see
                # app/agent/ambiguity_guard.py.
                verdict = evaluate_ambiguity(
                    user_message=user_message,
                    search_candidates=last_search_candidates,
                    raw_apply_arguments_json=arguments_json,
                )
                if verdict.blocked:
                    names = ", ".join(f"«{c.name}»" for c in verdict.candidates)
                    return AgentTurnResult(
                        status="clarification_required",
                        message=f"Уточните, какую задачу вы имеете в виду — найдено несколько подходящих: {names}.",
                        change_summary=None,
                        warnings=warnings,
                    )

            outcome = await gateway.call(name, arguments_json)
            payload = _outcome_payload(outcome)
            messages.append(_tool_result_message(call_id, payload))

            if name == "search_tasks":
                results = payload.get("results") if outcome.kind == "success" else None
                candidates = [
                    SearchCandidate(id=r["id"], name=r["name"])
                    for r in (results or [])
                    if isinstance(r, dict) and r.get("id") and r.get("name")
                ]
                last_search_candidates = candidates if len(candidates) >= 2 else None

            if name == MUTATION_TOOL:
                if outcome.kind == "success" and payload.get("ok"):
                    mutated = True
                    if payload.get("change_summary") is not None:
                        change_summary = ChangeSummary.model_validate(payload["change_summary"])
                    return await self._finish_after_mutation(messages, change_summary, warnings)
                last_rejection = payload.get("message") or "Изменения не применены."
        else:
            raise AgentStepLimitError("Reached the maximum number of agent steps for this request.")

    async def _finish_after_mutation(
        self, messages: list[dict[str, Any]], change_summary: ChangeSummary | None, warnings: list[str]
    ) -> AgentTurnResult:
        """One optional prose-only completion to summarize the change for the
        user. If it fails for any reason, the mutation already happened and is
        kept — we never retry it, we just fall back to a fixed message."""
        try:
            completion = await self._client.chat_completion(messages=messages, tools=None)
            text = (completion.message.get("content") or "").strip()
        except Exception as exc:  # noqa: BLE001 - provider failure here must not look like a mutation failure
            logger.warning("post_mutation_completion_failed error=%s", exc)
            text = ""
        return AgentTurnResult(
            status="applied",
            message=text or _FALLBACK_APPLIED_MESSAGE,
            change_summary=change_summary,
            warnings=warnings,
        )

    # -- MCP session ----------------------------------------------------------------

    @asynccontextmanager
    async def _mcp_session(self) -> AsyncIterator[ClientSession]:
        """Connects to the mounted MCP server over Streamable HTTP through an
        in-process ASGI transport (httpx.ASGITransport) — a real MCP
        client/server protocol exchange (session negotiation, JSON-RPC
        framing), just without an actual OS socket, which is both the
        SDK-documented way to embed FastMCP in a bigger ASGI app and the most
        robust option for a server calling its own mounted sub-app from
        within the same process/event loop. Uses `streamable_http_client` (not
        the deprecated `streamablehttp_client` alias) with a pre-built
        `httpx.AsyncClient` — the current SDK's documented low-level entry
        point for supplying a custom transport."""
        http_client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._mcp_asgi_app),
            base_url=_MCP_INTERNAL_BASE_URL,
        )
        async with http_client:
            async with streamable_http_client(_MCP_INTERNAL_BASE_URL, http_client=http_client) as (
                read_stream,
                write_stream,
                _get_session_id,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session


def _unwrap_single_exception(exc: BaseException) -> BaseException:
    """Recursively unwrap a `BaseExceptionGroup` that contains exactly one
    exception — anyio task groups wrap even a single propagated exception
    this way. A group with multiple exceptions is returned as-is (there is no
    single "real" cause to unwrap to)."""
    exceptions = getattr(exc, "exceptions", None)
    if exceptions and len(exceptions) == 1:
        return _unwrap_single_exception(exceptions[0])
    return exc


def _sanitize_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields the OpenAI-compatible wire format needs when this
    message is replayed as conversation history within the same request."""
    out: dict[str, Any] = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        out["tool_calls"] = message["tool_calls"]
    return out


def _tool_result_message(tool_call_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(payload, ensure_ascii=False)}


def _outcome_payload(outcome: ToolCallOutcome) -> dict[str, Any]:
    if outcome.kind == "success":
        return outcome.data if outcome.data is not None else {"ok": True}
    code = "AGENT_INVALID_TOOL_CALL" if outcome.kind == "invalid_arguments" else "MCP_TOOL_ERROR"
    return {"ok": False, "code": code, "message": outcome.error_message}
