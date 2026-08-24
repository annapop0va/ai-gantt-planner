"""Minimal OpenRouter client — OpenAI-compatible `/chat/completions` with
tool calling, over plain `httpx` (already a dependency; no `openai` SDK, no
LangChain/etc). One small class, one method, deliberately not general-purpose.

Logs model, latency, step-relevant counts, and provider-reported token usage
— never the API key, the Authorization header, or full project/task text.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.domain.errors import AiNotConfiguredError, AiProviderError, AiProviderTimeoutError
from app.settings import Settings

logger = logging.getLogger("ai_gantt_planner.agent")


@dataclass(frozen=True)
class CompletionResult:
    message: dict[str, Any]
    """The assistant message dict: role, content, and optionally tool_calls."""
    finish_reason: str | None
    usage: dict[str, Any] | None
    latency_ms: float


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        if not self._settings.ai_configured:
            raise AiNotConfiguredError(
                "OPENROUTER_API_KEY and OPENROUTER_MODEL must both be set to use the AI chat."
            )

        payload: dict[str, Any] = {
            "model": self._settings.openrouter_model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tools:
            payload["tools"] = tools
            # Keeps the mutation-safety policy in app/agent/service.py simple:
            # at most one tool call to reason about per model turn.
            payload["parallel_tool_calls"] = False

        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.openrouter_base_url,
                timeout=self._settings.openrouter_timeout_seconds,
            ) as client:
                response = await client.post("/chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AiProviderTimeoutError("OpenRouter request timed out.") from exc
        except httpx.HTTPError as exc:
            raise AiProviderError(f"Failed to reach OpenRouter: {exc}") from exc

        latency_ms = (time.monotonic() - start) * 1000

        if response.status_code >= 400:
            raise AiProviderError(
                f"OpenRouter returned HTTP {response.status_code}.",
                details=[{"status": response.status_code}],
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AiProviderError("OpenRouter returned a malformed (non-JSON) response.") from exc

        choices = data.get("choices")
        if not choices or "message" not in choices[0]:
            raise AiProviderError("OpenRouter response had no usable choice.")

        usage = data.get("usage")
        logger.info(
            "openrouter_completion model=%s latency_ms=%.0f finish_reason=%s usage=%s",
            self._settings.openrouter_model,
            latency_ms,
            choices[0].get("finish_reason"),
            usage,
        )

        return CompletionResult(
            message=choices[0]["message"],
            finish_reason=choices[0].get("finish_reason"),
            usage=usage,
            latency_ms=latency_ms,
        )
