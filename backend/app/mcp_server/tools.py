"""The 4 MCP tools, registered against a `ProjectService`/`SearchService` that
are the exact same instances the REST API uses (see app/mcp_server/app.py —
there is one `InMemoryProjectStore` per process, never a second one).

FastMCP builds each tool's JSON schema from the tool function's *individual*
parameters — a single Pydantic-model parameter would wrap everything one
level too deep (`{"args": {...}}` instead of the flat object schema MCP
clients expect), so every tool below takes plain scalar/list parameters
rather than one bundled model. `list[Operation]` still reuses
`app.domain.changeset.Operation` — the exact same union
`POST /projects/{id}/changes` validates against — as the type of the
`operations` parameter, so the schema itself is generated from that one
source of truth.

Every handler returns a structured result with an `ok` flag rather than
raising for *expected* domain outcomes (not found, revision conflict, a
rejected change set) — those are normal MCP tool results, not transport
failures. An exception only escapes for genuinely unexpected bugs, which the
MCP SDK turns into `CallToolResult(isError=True)` on its own.
"""

from __future__ import annotations

import uuid

from mcp.server.fastmcp import FastMCP

from app.domain.changeset import ChangeSetRequest, Operation
from app.domain.errors import DomainError
from app.domain.models import Project, Task
from app.mcp_server.schemas import (
    ApplyChangeSetResult,
    ProjectOutlineResult,
    RelatedTaskRef,
    SearchTasksResult,
    TaskDetailsResult,
    TaskOutlineItem,
    TaskSearchResultItem,
)
from app.services.project_service import ProjectService
from app.services.search_service import search_tasks

TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_project_outline": (
        "Get a concise outline of the project: name, start date, revision, task "
        "count, release date, and a page of lightweight tasks (id, name, "
        "assignee, duration, dates, display order). Use offset/limit to page "
        "through large projects. Use this first to orient yourself."
    ),
    "search_tasks": (
        "Search tasks by name or assignee. Returns id, name, assignee, "
        "duration, dates and a relevance score. Use this to resolve a task the "
        "user referred to by name before mutating it."
    ),
    "get_task_details": (
        "Get full details for one task by id: description, assignee, "
        "duration, planned effort hours, dates, start-not-before constraint, "
        "source, and its predecessors/successors by id and name."
    ),
    "apply_change_set": (
        "Apply one atomic set of change operations to the project (update "
        "fields, change duration, move, create, insert between, set/add/remove "
        "dependencies, bulk-assign, clear a start constraint). All operations "
        "either fully apply together or none do. Call this at most once per "
        "user request, after resolving every referenced task via "
        "search_tasks/get_task_details."
    ),
}

_MAX_OUTLINE_LIMIT = 100
_MAX_SEARCH_LIMIT = 20


def register_tools(mcp: FastMCP, project_service: ProjectService) -> None:
    @mcp.tool(name="get_project_outline", description=TOOL_DESCRIPTIONS["get_project_outline"])
    async def get_project_outline(project_id: str, offset: int = 0, limit: int = 100) -> ProjectOutlineResult:
        project = await _load_project(project_service, project_id, ProjectOutlineResult)
        if isinstance(project, ProjectOutlineResult):
            return project

        safe_offset = max(0, offset)
        safe_limit = max(1, min(limit, _MAX_OUTLINE_LIMIT))
        ordered = sorted(project.tasks, key=lambda t: t.display_order)
        page = ordered[safe_offset : safe_offset + safe_limit]
        next_offset = safe_offset + safe_limit if safe_offset + safe_limit < len(ordered) else None

        return ProjectOutlineResult(
            ok=True,
            project_name=project.name,
            project_start_date=project.project_start_date.isoformat(),
            revision=project.revision,
            task_count=len(project.tasks),
            release_date=_release_date(project),
            tasks=[
                TaskOutlineItem(
                    id=str(task.id),
                    name=task.name,
                    assignee=task.assignee,
                    duration_workdays=task.duration_workdays,
                    start_date=task.start_date.isoformat(),
                    end_date=task.end_date.isoformat(),
                    display_order=task.display_order,
                )
                for task in page
            ],
            truncated=next_offset is not None,
            next_offset=next_offset,
        )

    @mcp.tool(name="search_tasks", description=TOOL_DESCRIPTIONS["search_tasks"])
    async def search_tasks_tool(project_id: str, query: str, limit: int = 20) -> SearchTasksResult:
        project = await _load_project(project_service, project_id, SearchTasksResult)
        if isinstance(project, SearchTasksResult):
            return project

        safe_limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        hits = search_tasks(project, query, limit=safe_limit)
        return SearchTasksResult(
            ok=True,
            query=query,
            results=[
                TaskSearchResultItem(
                    id=str(hit.task.id),
                    name=hit.task.name,
                    assignee=hit.task.assignee,
                    duration_workdays=hit.task.duration_workdays,
                    start_date=hit.task.start_date.isoformat(),
                    end_date=hit.task.end_date.isoformat(),
                    relevance=hit.relevance,
                )
                for hit in hits
            ],
        )

    @mcp.tool(name="get_task_details", description=TOOL_DESCRIPTIONS["get_task_details"])
    async def get_task_details(project_id: str, task_id: str) -> TaskDetailsResult:
        project = await _load_project(project_service, project_id, TaskDetailsResult)
        if isinstance(project, TaskDetailsResult):
            return project

        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            return TaskDetailsResult(ok=False, code="INVALID_TASK_ID", message="task_id is not a valid UUID.")

        task = project.task_by_id(task_uuid)
        if task is None:
            return TaskDetailsResult(ok=False, code="TASK_NOT_FOUND", message=f"No task with id {task_id}.")

        by_id = {t.id: t for t in project.tasks}
        successors = [t for t in project.tasks if task_uuid in t.predecessor_ids]

        return TaskDetailsResult(
            ok=True,
            id=str(task.id),
            name=task.name,
            description=task.description,
            assignee=task.assignee,
            duration_workdays=task.duration_workdays,
            planned_effort_hours=task.planned_effort_hours,
            start_date=task.start_date.isoformat(),
            end_date=task.end_date.isoformat(),
            start_not_before=task.start_not_before.isoformat() if task.start_not_before else None,
            created_source=task.created_source,
            predecessors=[
                RelatedTaskRef(id=str(p), name=by_id[p].name) for p in task.predecessor_ids if p in by_id
            ],
            successors=[RelatedTaskRef(id=str(t.id), name=t.name) for t in successors],
        )

    @mcp.tool(name="apply_change_set", description=TOOL_DESCRIPTIONS["apply_change_set"])
    async def apply_change_set(
        project_id: str, expected_revision: int, operations: list[Operation]
    ) -> ApplyChangeSetResult:
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return ApplyChangeSetResult(ok=False, code="INVALID_PROJECT_ID", message="project_id is not a valid UUID.")

        request = ChangeSetRequest(expected_revision=expected_revision, operations=operations)
        try:
            result = await project_service.apply_change_set(project_uuid, request)
        except DomainError as exc:
            return ApplyChangeSetResult(ok=False, code=exc.code, message=exc.message)

        return ApplyChangeSetResult(
            ok=True,
            status="applied",
            change_summary=result.change_summary,
            client_ref_map={ref: str(task_id) for ref, task_id in result.client_ref_map.items()},
            task_count=len(result.project.tasks),
            release_date=_release_date(result.project),
        )


async def _load_project(service: ProjectService, project_id: str, result_type: type):
    """Shared not-found/invalid-id handling for the 3 project-scoped read tools.
    Returns the `Project` on success, or a populated `result_type(ok=False, ...)`
    on failure — callers check `isinstance(result, result_type)`."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        return result_type(ok=False, code="INVALID_PROJECT_ID", message="project_id is not a valid UUID.")
    try:
        return await service.get_project(project_uuid)
    except DomainError as exc:
        return result_type(ok=False, code=exc.code, message=exc.message)


def _release_date(project: Project) -> str | None:
    if not project.tasks:
        return None
    latest: Task = max(project.tasks, key=lambda t: t.end_date)
    return latest.end_date.isoformat()
