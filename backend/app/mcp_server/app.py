"""Builds the in-process MCP server.

Mounting note (the well-known FastMCP-in-FastAPI pitfall): `FastMCP`'s own
`streamable_http_path` setting defaults to `/mcp`, and `streamable_http_app()`
serves that path *within the Starlette app it returns*. Mounting that app at
`/mcp` on the parent — the natural thing to try — doubles the path to
`/mcp/mcp`. The fix used here (documented by the SDK itself as the pattern
for "mounting FastMCP servers in a FastAPI application"): construct `FastMCP`
with `streamable_http_path="/"`, then mount the resulting app at `/mcp` on
the parent, so the two compose into exactly `/mcp`.

Lifespan note: `streamable_http_app()` returns a Starlette app whose own
`lifespan` starts the `StreamableHTTPSessionManager`. Starlette does **not**
propagate a mounted sub-app's lifespan automatically, so that inner lifespan
never runs on its own here — see app/main.py, which instead enters
`mcp.session_manager.run()` directly inside the *parent* FastAPI app's own
lifespan. `session_manager` is only initialized once `streamable_http_app()`
has been called (lazily, by design — see the SDK's own docstring on that
property), which is why `build_mcp_asgi_app()` must run before the parent
lifespan tries to touch `mcp.session_manager`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from app.mcp_server.tools import register_tools
from app.services.project_service import ProjectService


def create_mcp_server(project_service: ProjectService) -> FastMCP:
    mcp = FastMCP(
        name="ai-gantt-planner",
        instructions="Read and mutate AI Gantt Planner projects through a fixed, allow-listed tool set.",
        streamable_http_path="/",
        # DNS-rebinding protection is auto-enabled by the SDK for the default
        # 127.0.0.1/localhost host — left as-is intentionally, see
        # docs/mcp-agent-architecture.md for the production-hardening TODO.
    )
    register_tools(mcp, project_service)
    return mcp


def build_mcp_asgi_app(mcp: FastMCP) -> Starlette:
    """Call once at startup: creates the session manager (lazily, as a side
    effect) and returns the ASGI app to `.mount("/mcp", ...)` on the parent."""
    return mcp.streamable_http_app()
