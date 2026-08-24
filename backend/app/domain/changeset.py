"""ChangeSet wire/domain shapes: TaskRef and the 10 supported operations
(product-spec §9, §10, §12, §14).

These are transport-agnostic on purpose — an HTTP request body today, a tool
call's arguments from an MCP client later. Nothing here imports FastAPI.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from app.domain.errors import InvalidClientRefError

_CLIENT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class TaskRef(BaseModel):
    """Exactly one of `task_id` (an existing task) or `client_ref` (a task
    created earlier in the same change set) must be set."""

    task_id: uuid.UUID | None = None
    client_ref: str | None = None

    @model_validator(mode="after")
    def _check_exactly_one(self) -> "TaskRef":
        has_id = self.task_id is not None
        has_ref = self.client_ref is not None
        if has_id == has_ref:
            raise InvalidClientRefError(
                "TaskRef must set exactly one of task_id or client_ref."
            )
        if has_ref and not _CLIENT_REF_RE.match(self.client_ref):  # type: ignore[arg-type]
            raise InvalidClientRefError(
                f"client_ref '{self.client_ref}' must be 1-64 chars of letters, digits, "
                "underscore or hyphen."
            )
        return self


class UpdateTaskFields(BaseModel):
    op: Literal["update_task_fields"] = "update_task_fields"
    task: TaskRef
    name: str | None = None
    description: str | None = None
    assignee: str | None = None
    clear_assignee: bool = False


class ChangeDuration(BaseModel):
    op: Literal["change_duration"] = "change_duration"
    task: TaskRef
    mode: Literal["set", "add", "subtract"]
    unit: Literal["workdays", "person_hours"]
    value: int = Field(gt=0)


class MoveTask(BaseModel):
    op: Literal["move_task"] = "move_task"
    task: TaskRef
    offset_workdays: int | None = None
    target_start_date: date | None = None

    @model_validator(mode="after")
    def _check_exactly_one(self) -> "MoveTask":
        has_offset = self.offset_workdays is not None
        has_target = self.target_start_date is not None
        if has_offset == has_target:
            raise ValueError("move_task requires exactly one of offset_workdays or target_start_date.")
        return self


class CreateTask(BaseModel):
    op: Literal["create_task"] = "create_task"
    client_ref: str
    name: str
    description: str = ""
    assignee: str | None = None
    duration_workdays: int
    predecessor_refs: list[TaskRef] = Field(default_factory=list)
    start_not_before: date | None = None
    display_after_ref: TaskRef | None = None

    @model_validator(mode="after")
    def _check_client_ref(self) -> "CreateTask":
        if not _CLIENT_REF_RE.match(self.client_ref):
            raise InvalidClientRefError(
                f"client_ref '{self.client_ref}' must be 1-64 chars of letters, digits, "
                "underscore or hyphen."
            )
        return self


class InsertTaskBetween(BaseModel):
    op: Literal["insert_task_between"] = "insert_task_between"
    client_ref: str
    name: str
    description: str = ""
    assignee: str | None = None
    duration_workdays: int
    predecessor: TaskRef
    successor: TaskRef

    @model_validator(mode="after")
    def _check_client_ref(self) -> "InsertTaskBetween":
        if not _CLIENT_REF_RE.match(self.client_ref):
            raise InvalidClientRefError(
                f"client_ref '{self.client_ref}' must be 1-64 chars of letters, digits, "
                "underscore or hyphen."
            )
        return self


class SetPredecessors(BaseModel):
    op: Literal["set_predecessors"] = "set_predecessors"
    task: TaskRef
    predecessor_refs: list[TaskRef] = Field(default_factory=list)


class AddDependency(BaseModel):
    op: Literal["add_dependency"] = "add_dependency"
    predecessor: TaskRef
    successor: TaskRef


class RemoveDependency(BaseModel):
    op: Literal["remove_dependency"] = "remove_dependency"
    predecessor: TaskRef
    successor: TaskRef


class BulkSetAssignee(BaseModel):
    op: Literal["bulk_set_assignee"] = "bulk_set_assignee"
    tasks: list[TaskRef] = Field(min_length=1)
    assignee: str | None = None


class ClearStartConstraint(BaseModel):
    op: Literal["clear_start_constraint"] = "clear_start_constraint"
    task: TaskRef


Operation = Annotated[
    Union[
        UpdateTaskFields,
        ChangeDuration,
        MoveTask,
        CreateTask,
        InsertTaskBetween,
        SetPredecessors,
        AddDependency,
        RemoveDependency,
        BulkSetAssignee,
        ClearStartConstraint,
    ],
    Field(discriminator="op"),
]


class ChangeSetRequest(BaseModel):
    expected_revision: int
    operations: list[Operation] = Field(min_length=1)
