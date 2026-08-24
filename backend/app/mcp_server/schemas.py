"""MCP tool argument/result shapes.

Two argument shapes per mutating/scoped tool:

- `*Args` — the real wire schema a `call_tool()` request carries. Includes
  `project_id` (all tools) and `expected_revision` (`apply_change_set` only).
- `*ModelArgs` — what the LLM actually sees and fills in (via
  `BoundMcpToolGateway`, see app/agent/gateway.py). Never includes
  `project_id`/`expected_revision` — those are injected server-side from the
  chat request, so the model can never target another project or revision.

`operations: list[Operation]` reuses `app.domain.changeset.Operation` — the
exact same union `POST /projects/{id}/changes` validates against. This is the
single source of truth for what a change set can contain; nothing here
redefines it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.changeset import Operation
from app.domain.diff import ChangeSummary

_FORBID = ConfigDict(extra="forbid")

# --- wire args (server -> MCP server, project_id/expected_revision bound) ---


class GetProjectOutlineArgs(BaseModel):
    model_config = _FORBID
    project_id: str
    offset: int = 0
    limit: int = 100


class SearchTasksArgs(BaseModel):
    model_config = _FORBID
    project_id: str
    query: str
    limit: int = 20


class GetTaskDetailsArgs(BaseModel):
    model_config = _FORBID
    project_id: str
    task_id: str


class ApplyChangeSetArgs(BaseModel):
    model_config = _FORBID
    project_id: str
    expected_revision: int
    operations: list[Operation] = Field(min_length=1)


# --- model-visible args (LLM -> gateway, no project_id/expected_revision) ---


class GetProjectOutlineModelArgs(BaseModel):
    model_config = _FORBID
    offset: int = 0
    limit: int = 100


class SearchTasksModelArgs(BaseModel):
    model_config = _FORBID
    query: str
    limit: int = 20


class GetTaskDetailsModelArgs(BaseModel):
    model_config = _FORBID
    task_id: str


class ApplyChangeSetModelArgs(BaseModel):
    model_config = _FORBID
    operations: list[Operation] = Field(min_length=1)


MODEL_ARGS_BY_TOOL: dict[str, type[BaseModel]] = {
    "get_project_outline": GetProjectOutlineModelArgs,
    "search_tasks": SearchTasksModelArgs,
    "get_task_details": GetTaskDetailsModelArgs,
    "apply_change_set": ApplyChangeSetModelArgs,
}

# --- results ------------------------------------------------------------------


class TaskOutlineItem(BaseModel):
    id: str
    name: str
    assignee: str | None
    duration_workdays: int
    start_date: str
    end_date: str
    display_order: int


class ProjectOutlineResult(BaseModel):
    ok: bool = True
    code: str | None = None
    message: str | None = None
    project_name: str | None = None
    project_start_date: str | None = None
    revision: int | None = None
    task_count: int | None = None
    release_date: str | None = None
    tasks: list[TaskOutlineItem] = Field(default_factory=list)
    truncated: bool = False
    next_offset: int | None = None


class TaskSearchResultItem(BaseModel):
    id: str
    name: str
    assignee: str | None
    duration_workdays: int
    start_date: str
    end_date: str
    relevance: float


class SearchTasksResult(BaseModel):
    ok: bool = True
    code: str | None = None
    message: str | None = None
    query: str | None = None
    results: list[TaskSearchResultItem] = Field(default_factory=list)


class RelatedTaskRef(BaseModel):
    id: str
    name: str


class TaskDetailsResult(BaseModel):
    ok: bool = True
    code: str | None = None
    message: str | None = None
    id: str | None = None
    name: str | None = None
    description: str | None = None
    assignee: str | None = None
    duration_workdays: int | None = None
    planned_effort_hours: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    start_not_before: str | None = None
    created_source: str | None = None
    predecessors: list[RelatedTaskRef] = Field(default_factory=list)
    successors: list[RelatedTaskRef] = Field(default_factory=list)


class ApplyChangeSetResult(BaseModel):
    ok: bool
    code: str | None = None
    message: str | None = None
    status: str | None = None
    change_summary: ChangeSummary | None = None
    client_ref_map: dict[str, str] = Field(default_factory=dict)
    task_count: int | None = None
    release_date: str | None = None
