"""BoundMcpToolGateway — the seam between "what the LLM is allowed to see and
send" and "what actually goes over the MCP wire".

For every allow-listed tool there are two schemas (app/mcp_server/schemas.py):
a wire schema (includes `project_id`, and `expected_revision` for
`apply_change_set`) and a model-visible schema (does not). This gateway is
constructed once per chat request, bound to one `project_id` and one
`expected_revision` captured before any model call — the model's raw
`tool_calls[].function.arguments` JSON is validated against the
*model-visible* schema (untrusted input; `extra="forbid"` rejects anything
foreign, including an attempt to smuggle in `project_id`/`expected_revision`),
and only then merged with the bound values and sent as a real
`session.call_tool()` — the model itself never constructs a wire call.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from mcp import ClientSession
from pydantic import ValidationError

from app.mcp_server.schemas import MODEL_ARGS_BY_TOOL
from app.mcp_server.tools import TOOL_DESCRIPTIONS

logger = logging.getLogger("ai_gantt_planner.agent")

ALLOWED_TOOLS = ("get_project_outline", "search_tasks", "get_task_details", "apply_change_set")
READ_TOOLS = ("get_project_outline", "search_tasks", "get_task_details")
MUTATION_TOOL = "apply_change_set"


@dataclass(frozen=True)
class ToolCallOutcome:
    kind: Literal["success", "invalid_arguments", "transport_error"]
    data: dict[str, Any] | None = None
    error_message: str | None = None


class BoundMcpToolGateway:
    def __init__(self, session: ClientSession, *, project_id: str, expected_revision: int) -> None:
        self._session = session
        self._project_id = project_id
        self._expected_revision = expected_revision

    def model_tool_definitions(self) -> list[dict[str, Any]]:
        """OpenRouter/OpenAI-format tool definitions, built from our own
        sanitized model-visible arg schemas — never from the wire schema, so
        `project_id`/`expected_revision` cannot appear here by construction."""
        definitions: list[dict[str, Any]] = []
        for name in ALLOWED_TOOLS:
            model_args_cls = MODEL_ARGS_BY_TOOL[name]
            schema = model_args_cls.model_json_schema()
            schema.pop("title", None)
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": TOOL_DESCRIPTIONS[name],
                        "parameters": schema,
                    },
                }
            )
        return definitions

    async def call(self, name: str, raw_arguments_json: str) -> ToolCallOutcome:
        if name not in ALLOWED_TOOLS:
            return ToolCallOutcome(kind="invalid_arguments", error_message=f"Tool '{name}' is not allowed.")

        # Untrusted JSON from the model — parse defensively, never `eval`/trust structure.
        try:
            raw_arguments = json.loads(raw_arguments_json) if raw_arguments_json else {}
        except (TypeError, ValueError):
            return ToolCallOutcome(kind="invalid_arguments", error_message="Tool arguments were not valid JSON.")
        if not isinstance(raw_arguments, dict):
            return ToolCallOutcome(kind="invalid_arguments", error_message="Tool arguments must be a JSON object.")

        model_args_cls = MODEL_ARGS_BY_TOOL[name]
        try:
            model_args = model_args_cls.model_validate(raw_arguments)
        except ValidationError as exc:
            return ToolCallOutcome(kind="invalid_arguments", error_message=f"Invalid arguments for {name}: {exc}")

        wire_arguments: dict[str, Any] = {"project_id": self._project_id, **model_args.model_dump(mode="json")}
        if name == MUTATION_TOOL:
            wire_arguments["expected_revision"] = self._expected_revision

        try:
            result = await self._session.call_tool(name, wire_arguments)
        except Exception as exc:  # noqa: BLE001 - any transport failure maps uniformly
            logger.warning("mcp_tool_transport_error tool=%s error=%s", name, exc)
            return ToolCallOutcome(kind="transport_error", error_message=str(exc))

        if result.isError:
            text = _first_text(result.content)
            logger.warning("mcp_tool_call_error tool=%s message=%s", name, text)
            return ToolCallOutcome(kind="transport_error", error_message=text or f"Tool {name} reported an error.")

        data = result.structuredContent or {}
        return ToolCallOutcome(kind="success", data=data)


def _first_text(content: list[Any]) -> str | None:
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return text
    return None
