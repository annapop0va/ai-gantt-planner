"""Change summary: diff between a before/after Project snapshot
(technical-blueprint §5-6).

Deliberately snapshot-based, not tracked-during-apply: comparing the
committed `before` and `after` Project is simpler, cannot drift from what
actually got persisted, and mirrors the same strategy the frontend prototype
already uses in `frontend/src/lib/diff.ts` for the mock demo. Classification
precedence: created > direct > derived.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.domain.models import Project, Task
from app.scheduler.calendar import workdays_between

_DIRECT_FIELDS = ("name", "description", "assignee", "duration_workdays")


class FieldDelta(BaseModel):
    field: str
    before: str
    after: str


class DirectChange(BaseModel):
    task_id: uuid.UUID
    name: str
    deltas: list[FieldDelta]


class CreatedTaskChange(BaseModel):
    task_id: uuid.UUID
    name: str
    assignee: str | None
    duration_workdays: int
    planned_effort_hours: int


class DependencyChange(BaseModel):
    predecessor_id: uuid.UUID
    successor_id: uuid.UUID
    kind: Literal["added", "removed"]


class DerivedScheduleChange(BaseModel):
    task_id: uuid.UUID
    name: str
    before_start: date
    after_start: date
    before_end: date
    after_end: date
    workday_shift: int


class ChangeSummary(BaseModel):
    previous_revision: int
    new_revision: int
    direct_changes: list[DirectChange]
    created_tasks: list[CreatedTaskChange]
    dependency_changes: list[DependencyChange]
    derived_schedule_changes: list[DerivedScheduleChange]


def compute_change_summary(before: Project, after: Project) -> ChangeSummary:
    before_by_id: dict[uuid.UUID, Task] = {t.id: t for t in before.tasks}

    direct_changes: list[DirectChange] = []
    created_tasks: list[CreatedTaskChange] = []
    derived_changes: list[DerivedScheduleChange] = []

    for task in sorted(after.tasks, key=lambda t: t.display_order):
        prev = before_by_id.get(task.id)

        if prev is None:
            created_tasks.append(
                CreatedTaskChange(
                    task_id=task.id,
                    name=task.name,
                    assignee=task.assignee,
                    duration_workdays=task.duration_workdays,
                    planned_effort_hours=task.planned_effort_hours,
                )
            )
            continue

        deltas = _field_deltas(prev, task)
        if deltas:
            direct_changes.append(DirectChange(task_id=task.id, name=task.name, deltas=deltas))
            continue

        if prev.start_date != task.start_date or prev.end_date != task.end_date:
            derived_changes.append(
                DerivedScheduleChange(
                    task_id=task.id,
                    name=task.name,
                    before_start=prev.start_date,
                    after_start=task.start_date,
                    before_end=prev.end_date,
                    after_end=task.end_date,
                    workday_shift=workdays_between(prev.end_date, task.end_date),
                )
            )

    return ChangeSummary(
        previous_revision=before.revision,
        new_revision=after.revision,
        direct_changes=direct_changes,
        created_tasks=created_tasks,
        dependency_changes=_dependency_changes(before, after),
        derived_schedule_changes=derived_changes,
    )


def _field_deltas(prev: Task, task: Task) -> list[FieldDelta]:
    deltas: list[FieldDelta] = []
    for field in _DIRECT_FIELDS:
        before_value = getattr(prev, field)
        after_value = getattr(task, field)
        if before_value != after_value:
            deltas.append(FieldDelta(field=field, before=str(before_value), after=str(after_value)))
    if set(prev.predecessor_ids) != set(task.predecessor_ids):
        deltas.append(
            FieldDelta(
                field="predecessor_ids",
                before=",".join(str(p) for p in prev.predecessor_ids),
                after=",".join(str(p) for p in task.predecessor_ids),
            )
        )
    if prev.start_not_before != task.start_not_before:
        deltas.append(
            FieldDelta(
                field="start_not_before",
                before=prev.start_not_before.isoformat() if prev.start_not_before else "",
                after=task.start_not_before.isoformat() if task.start_not_before else "",
            )
        )
    return deltas


def _dependency_changes(before: Project, after: Project) -> list[DependencyChange]:
    def edges(project: Project) -> set[tuple[uuid.UUID, uuid.UUID]]:
        return {
            (pred_id, task.id)
            for task in project.tasks
            for pred_id in task.predecessor_ids
        }

    before_edges = edges(before)
    after_edges = edges(after)
    after_task_ids = {t.id for t in after.tasks}

    changes = [
        DependencyChange(predecessor_id=pred, successor_id=succ, kind="added")
        for pred, succ in sorted(after_edges - before_edges, key=lambda e: (e[1], e[0]))
    ]
    changes += [
        DependencyChange(predecessor_id=pred, successor_id=succ, kind="removed")
        for pred, succ in sorted(before_edges - after_edges, key=lambda e: (e[1], e[0]))
        if pred in after_task_ids and succ in after_task_ids
    ]
    return changes
