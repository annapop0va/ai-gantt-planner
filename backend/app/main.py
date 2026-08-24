from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

from app.agent.conversation_store import InMemoryAgentConversationStore
from app.agent.service import AgentService
from app.api.errors import register_exception_handlers
from app.api.routers import changes, chat, health, projects
from app.mcp_server.app import build_mcp_asgi_app, create_mcp_server
from app.services.project_service import ProjectService
from app.settings import Settings, get_settings
from app.storage.project_store import InMemoryProjectStore


def create_app() -> FastAPI:
    settings = get_settings()

    # Created once per process, at app-construction time (not inside a request,
    # not a bare module-level global) — the same InMemoryProjectStore backs
    # both the REST routers (via app.state, see app/api/deps.py) and every MCP
    # tool call, because there is exactly one project store per process.
    project_store = InMemoryProjectStore()
    project_service = ProjectService(project_store)

    mcp_server: FastMCP | None = None
    if settings.enable_mcp:
        mcp_server = create_mcp_server(project_service)
        # Must be called before the app starts (creates the session manager
        # lazily) so the parent lifespan below can enter mcp_server.session_manager.run().
        mcp_asgi_app = build_mcp_asgi_app(mcp_server)
    else:
        mcp_asgi_app = None

    agent_service: AgentService | None = None
    if mcp_server is not None:
        agent_service = AgentService(
            settings=settings,
            project_service=project_service,
            mcp_asgi_app=mcp_asgi_app,
            conversation_store=InMemoryAgentConversationStore(max_turns=settings.agent_history_turns),
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.project_store = project_store
        app.state.project_service = project_service
        app.state.agent_service = agent_service
        app.state.settings = settings

        # `streamable_http_app()`'s own Starlette wrapper sets a `lifespan=`
        # that starts this same session manager — but Starlette does not
        # propagate a *mounted* sub-app's lifespan to the parent, so that
        # inner lifespan never runs on its own. This is the SDK-documented
        # fix: enter the session manager directly in the parent's lifespan.
        # See app/mcp_server/app.py for the full mounting explanation.
        if mcp_server is not None:
            async with mcp_server.session_manager.run():
                yield
        else:
            yield

    app = FastAPI(title="AI Gantt Planner API", version="0.2.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        # Content-Disposition is not on the CORS-safelisted response header list,
        # so the browser hides it from `fetch()` unless explicitly exposed —
        # the frontend export flow reads the real filename from it.
        expose_headers=["Content-Disposition"],
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(projects.router, prefix="/api/v1")
    if settings.enable_dev_endpoints:
        app.include_router(changes.router, prefix="/api/v1")
    if agent_service is not None:
        app.include_router(chat.router, prefix="/api/v1")

    if mcp_asgi_app is not None:
        # FastMCP's own streamable_http_path is configured as "/" (see
        # app/mcp_server/app.py) specifically so this mount lands on exactly
        # /mcp, not /mcp/mcp. The browser/frontend never calls this directly —
        # only AgentService does, and it connects to `mcp_asgi_app` in-process
        # via httpx.ASGITransport rather than through this mounted route (see
        # app/agent/service.py). The mount exists so /mcp is independently
        # reachable for manual verification (curl, an external MCP client)
        # and to keep the "target endpoint /mcp" contract literally true.
        app.mount("/mcp", mcp_asgi_app)

    return app


app = create_app()
