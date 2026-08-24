"""Domain model: Project and Task (product-spec §6).

Pydantic v2 is used here purely as a typed-model/validation library — this
module does not import FastAPI and is usable standalone (by the scheduler,
by tests, by a future MCP tool boundary).

`planned_effort_hours` is a computed field: duration_workdays × 8, never an
independently-settable source field. `successor_ids` is intentionally *not*
part of this model — it is cross-task derived data, built only at the API
serialization boundary (see app/schemas/project.py) so nothing here can
accidentally treat it as authoritative per-task state.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.domain.constants import HOURS_PER_WORKDAY

CreatedSource = Literal["import", "agent"]


class Task(BaseModel):
    id: uuid.UUID
    name: str
    description: str = ""
    assignee: str | None = None
    duration_workdays: int
    predecessor_ids: list[uuid.UUID] = Field(default_factory=list)
    start_not_before: date | None = None
    start_date: date
    end_date: date
    display_order: int
    created_source: CreatedSource

    @computed_field  # type: ignore[misc]
    @property
    def planned_effort_hours(self) -> int:
        return self.duration_workdays * HOURS_PER_WORKDAY


class Project(BaseModel):
    id: uuid.UUID
    name: str
    project_start_date: date
    revision: int
    tasks: list[Task] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    def task_by_id(self, task_id: uuid.UUID) -> Task | None:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
