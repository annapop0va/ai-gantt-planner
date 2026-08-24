"""POST /api/v1/projects/{project_id}/chat — the only production entry point
to the AI agent. Only registered when MCP is enabled (see app/main.py); if
OpenRouter itself is not configured, `AgentService.run_turn()` raises
`AiNotConfiguredError`, mapped by the shared DomainError handler to a 503
with code AI_NOT_CONFIGURED — the rest of the API is unaffected either way.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_agent_service, get_project_service
from app.agent.service import AgentService
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.project import project_to_out
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["chat"])


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def chat(
    project_id: uuid.UUID,
    request: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ChatResponse:
    result = await agent.run_turn(
        project_id=project_id, message=request.message, expected_revision=request.expected_revision
    )

    if result.status != "applied":
        return ChatResponse(status=result.status, message=result.message)

    # AgentService never returns the full Project DTO itself — mutation went
    # through MCP -> ProjectService.apply_change_set(); this is a plain,
    # read-only refetch for the HTTP response, not a second mutation path.
    project = await project_service.get_project(project_id)
    return ChatResponse(
        status="applied",
        message=result.message,
        project=project_to_out(project),
        change_summary=result.change_summary,
        warnings=result.warnings,
    )
