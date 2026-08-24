from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.mcp_server.schemas import MODEL_ARGS_BY_TOOL
from tests.conftest import build_mcp_test_env, build_test_settings, import_sample_via_service

_INTERNAL_BASE_URL = "http://localhost:8000/"


@asynccontextmanager
async def _connect(asgi_app, url: str = _INTERNAL_BASE_URL) -> AsyncIterator[ClientSession]:
    """Real MCP client/server exchange over Streamable HTTP through an
    in-process ASGI transport — same pattern AgentService uses in production
    (app/agent/service.py), using the current (non-deprecated) SDK client entry
    point with a pre-built httpx.AsyncClient."""
    http_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi_app), base_url=url)
    async with http_client:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


def test_list_tools_returns_exactly_the_four_allow_listed_tools():
    async def run():
        env = build_mcp_test_env()
        async with env.mcp.session_manager.run():
            async with _connect(env.asgi_app) as session:
                result = await session.list_tools()
                names = sorted(t.name for t in result.tools)
                assert names == sorted(
                    ["get_project_outline", "search_tasks", "get_task_details", "apply_change_set"]
                )

    asyncio.run(run())


def test_mounted_mcp_server_starts_under_actual_fastapi_lifespan():
    """End-to-end through app.main.create_app(): real FastAPI lifespan, real
    mount at /mcp — not the standalone FastMCP object the other tests build."""

    async def run():
        import app.main as main_module
        from app.settings import Settings

        original_get_settings = main_module.get_settings

        def patched() -> Settings:
            return build_test_settings(
                enable_mcp=True,
                enable_dev_endpoints=True,
                openrouter_api_key="test-key",
                openrouter_model="test-model",
            )

        main_module.get_settings = patched
        try:
            app = main_module.create_app()
        finally:
            main_module.get_settings = original_get_settings

        async with app.router.lifespan_context(app):
            async with _connect(app, "http://localhost:8000/mcp/") as session:
                result = await session.list_tools()
                names = sorted(t.name for t in result.tools)
                assert names == sorted(
                    ["get_project_outline", "search_tasks", "get_task_details", "apply_change_set"]
                )

    asyncio.run(run())


def test_rest_and_mcp_share_one_project_store():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)

        async with env.mcp.session_manager.run():
            async with _connect(env.asgi_app) as session:
                result = await session.call_tool(
                    "get_project_outline", {"project_id": str(project.id), "offset": 0, "limit": 5}
                )
                assert result.structuredContent["task_count"] == 16
                assert result.structuredContent["revision"] == 1

        # Same store, same ProjectService — REST-style read sees the identical project.
        reloaded = await env.service.get_project(project.id)
        assert reloaded.id == project.id
        assert len(reloaded.tasks) == 16

    asyncio.run(run())


def test_read_tools_do_not_change_revision():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)

        async with env.mcp.session_manager.run():
            async with _connect(env.asgi_app) as session:
                await session.call_tool("get_project_outline", {"project_id": str(project.id)})
                await session.call_tool(
                    "search_tasks", {"project_id": str(project.id), "query": "backend", "limit": 5}
                )
                first_id = str(project.tasks[0].id)
                await session.call_tool("get_task_details", {"project_id": str(project.id), "task_id": first_id})

        reloaded = await env.service.get_project(project.id)
        assert reloaded.revision == 1

    asyncio.run(run())


def test_apply_tool_mutates_the_same_stored_project_via_project_service():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)
        task_id = str(project.tasks[0].id)

        async with env.mcp.session_manager.run():
            async with _connect(env.asgi_app) as session:
                result = await session.call_tool(
                    "apply_change_set",
                    {
                        "project_id": str(project.id),
                        "expected_revision": 1,
                        "operations": [
                            {
                                "op": "change_duration",
                                "task": {"task_id": task_id},
                                "mode": "set",
                                "unit": "workdays",
                                "value": 2,
                            }
                        ],
                    },
                )
                assert result.structuredContent["ok"] is True

        reloaded = await env.service.get_project(project.id)
        assert reloaded.revision == 2
        assert next(t for t in reloaded.tasks if t.id == project.tasks[0].id).duration_workdays == 2

    asyncio.run(run())


def test_model_visible_schema_has_no_project_id_or_expected_revision():
    for name, model_cls in MODEL_ARGS_BY_TOOL.items():
        schema = model_cls.model_json_schema()
        properties = schema.get("properties", {})
        assert "project_id" not in properties, name
        assert "expected_revision" not in properties, name


def test_model_visible_schema_rejects_unknown_extra_fields():
    apply_args_cls = MODEL_ARGS_BY_TOOL["apply_change_set"]
    with pytest.raises(Exception):
        apply_args_cls.model_validate({"operations": [], "project_id": "sneaky", "expected_revision": 999})


def test_structured_domain_error_surfaces_through_tool_result():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)

        async with env.mcp.session_manager.run():
            async with _connect(env.asgi_app) as session:
                result = await session.call_tool(
                    "get_task_details",
                    {"project_id": str(project.id), "task_id": "00000000-0000-0000-0000-000000000000"},
                )
                assert result.isError is False  # a domain "not found" is a normal structured result
                assert result.structuredContent["ok"] is False
                assert result.structuredContent["code"] == "TASK_NOT_FOUND"

    asyncio.run(run())


def test_get_project_outline_pagination():
    async def run():
        env = build_mcp_test_env()
        project = await import_sample_via_service(env.service)

        async with env.mcp.session_manager.run():
            async with _connect(env.asgi_app) as session:
                page1 = await session.call_tool(
                    "get_project_outline", {"project_id": str(project.id), "offset": 0, "limit": 10}
                )
                assert len(page1.structuredContent["tasks"]) == 10
                assert page1.structuredContent["truncated"] is True
                assert page1.structuredContent["next_offset"] == 10

                page2 = await session.call_tool(
                    "get_project_outline", {"project_id": str(project.id), "offset": 10, "limit": 10}
                )
                assert len(page2.structuredContent["tasks"]) == 6
                assert page2.structuredContent["truncated"] is False
                assert page2.structuredContent["next_offset"] is None

    asyncio.run(run())
