"""API-facing Project/Task shapes.

This is the one seam where `successor_ids` gets computed — it is
deliberately *not* part of the domain `Task` (see app/domain/models.py) so
nothing internal can mistake it for authoritative per-task state. Domain
`Project`/`Task` objects are never returned directly from a router.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.domain.models import CreatedSource, Project


class TaskOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    assignee: str | None
    duration_workdays: int
    planned_effort_hours: int
    predecessor_ids: list[uuid.UUID]
    successor_ids: list[uuid.UUID]
    start_not_before: date | None
    start_date: date
    end_date: date
    display_order: int
    created_source: CreatedSource


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    project_start_date: date
    revision: int
    tasks: list[TaskOut]
    created_at: datetime
    updated_at: datetime


class ImportResponse(BaseModel):
    project: ProjectOut
    warnings: list[str] = []


def project_to_out(project: Project) -> ProjectOut:
    successors: dict[uuid.UUID, list[uuid.UUID]] = {task.id: [] for task in project.tasks}
    for task in project.tasks:
        for pred_id in task.predecessor_ids:
            if pred_id in successors:
                successors[pred_id].append(task.id)

    ordered = sorted(project.tasks, key=lambda t: t.display_order)
    tasks_out = [
        TaskOut(
            id=task.id,
            name=task.name,
            description=task.description,
            assignee=task.assignee,
            duration_workdays=task.duration_workdays,
            planned_effort_hours=task.planned_effort_hours,
            predecessor_ids=task.predecessor_ids,
            successor_ids=successors[task.id],
            start_not_before=task.start_not_before,
            start_date=task.start_date,
            end_date=task.end_date,
            display_order=task.display_order,
            created_source=task.created_source,
        )
        for task in ordered
    ]

    return ProjectOut(
        id=project.id,
        name=project.name,
        project_start_date=project.project_start_date,
        revision=project.revision,
        tasks=tasks_out,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
