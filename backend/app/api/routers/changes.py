"""Development/testing-only endpoint for exercising ChangeSet operations
without the chat/agent layer. Only registered when ENABLE_DEV_ENDPOINTS=true
(see app/main.py). The MCP `apply_change_set` tool (app/mcp_server/tools.py)
calls the exact same `ProjectService.apply_change_set()`, never around it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_project_service
from app.domain.changeset import ChangeSetRequest
from app.schemas.changeset import ChangeSetResponse
from app.schemas.project import project_to_out
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["dev"])


@router.post("/{project_id}/changes", response_model=ChangeSetResponse)
async def apply_change_set(
    project_id: uuid.UUID,
    request: ChangeSetRequest,
    service: ProjectService = Depends(get_project_service),
) -> ChangeSetResponse:
    result = await service.apply_change_set(project_id, request)
    return ChangeSetResponse(
        project=project_to_out(result.project),
        change_summary=result.change_summary,
        warnings=result.warnings,
    )
