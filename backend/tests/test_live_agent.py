"""Opt-in live suite against the real OpenRouter API — spends real tokens.

Skipped by default (and by every command in this project's docs/CI) unless
`RUN_LIVE_LLM_TESTS=1` is set *and* `OPENROUTER_API_KEY`/`OPENROUTER_MODEL`
are configured. Every other test file in this project uses
`FakeOpenRouterClient` and makes zero network calls — this is the only file
that talks to a real model, and it asserts on the resulting `Project`
DTO/revision, not just on the assistant's prose, so a model that "sounds
right" but didn't actually call apply_change_set correctly still fails.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from app.agent.conversation_store import InMemoryAgentConversationStore
from app.agent.service import AgentService
from app.settings import get_settings
from tests.conftest import build_mcp_test_env, import_sample_via_service
from tests.test_agent import CANONICAL_COMMAND

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
    reason=(
        "Opt-in: set RUN_LIVE_LLM_TESTS=1 with a configured OPENROUTER_API_KEY/"
        "OPENROUTER_MODEL in the environment to run these against the real "
        "OpenRouter API. Skipped by default — see docs/spikes/mcp-agent-report.md."
    ),
)


def _live_agent(env):
    settings = get_settings()
    assert settings.ai_configured, (
        "RUN_LIVE_LLM_TESTS=1 was set but OPENROUTER_API_KEY/OPENROUTER_MODEL are not configured"
    )
    return AgentService(
        settings=settings,
        project_service=env.service,
        mcp_asgi_app=env.asgi_app,
        conversation_store=InMemoryAgentConversationStore(max_turns=settings.agent_history_turns),
    )


def test_live_simple_mutation():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)
        agent = _live_agent(env)
        async with env.mcp.session_manager.run():
            result = await agent.run_turn(
                project_id=project.id,
                message="Увеличь длительность задачи «Подготовка релиза» на 1 рабочий день",
                expected_revision=1,
            )
        print("LIVE RESULT:", result.status, "-", result.message)
        assert result.status == "applied"
        reloaded = await env.service.get_project(project.id)
        assert reloaded.revision == 2

    asyncio.run(run())


def test_live_canonical_full_command():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)
        agent = _live_agent(env)
        async with env.mcp.session_manager.run():
            result = await agent.run_turn(project_id=project.id, message=CANONICAL_COMMAND, expected_revision=1)
        print("LIVE RESULT:", result.status, "-", result.message)
        assert result.status == "applied"
        reloaded = await env.service.get_project(project.id)
        assert len(reloaded.tasks) == 18
        assert reloaded.revision == 2
        release = max(reloaded.tasks, key=lambda t: t.end_date)
        assert release.end_date.isoformat() == "2026-11-09"

    asyncio.run(run())


def test_live_ambiguous_command_asks_for_clarification():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)
        agent = _live_agent(env)
        async with env.mcp.session_manager.run():
            result = await agent.run_turn(
                project_id=project.id, message="Перенеси разработку на неделю позже", expected_revision=1
            )
        print("LIVE RESULT:", result.status, "-", result.message)
        assert result.status == "clarification_required"
        reloaded = await env.service.get_project(project.id)
        assert reloaded.revision == 1

    asyncio.run(run())
