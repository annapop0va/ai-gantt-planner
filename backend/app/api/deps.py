"""FastAPI dependency providers.

The store, the (single, process-lifetime) `AgentService`, and settings all
live on `app.state`, set once in main.py — never as module-level globals.
Every request gets a fresh, cheap `ProjectService` wrapping the single shared
store; `AgentService` is not request-scoped because it holds no per-request
state of its own (see app/agent/service.py — `run_turn()` takes everything
it needs as arguments).
"""

from __future__ import annotations

from fastapi import Request

from app.agent.service import AgentService
from app.services.project_service import ProjectService
from app.settings import Settings
from app.storage.project_store import InMemoryProjectStore


def get_store(request: Request) -> InMemoryProjectStore:
    return request.app.state.project_store  # type: ignore[no-any-return]


def get_project_service(request: Request) -> ProjectService:
    return ProjectService(get_store(request))


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service  # type: ignore[no-any-return]
