"""Deterministic scheduling engine (product-spec §8).

Framework-free: takes plain domain `Task` objects and a `project_start_date`,
returns new `Task` objects with `start_date`/`end_date` filled in, plus any
normalization warnings. Does not know about FastAPI, Excel, the frontend, or
change sets — it is pure date arithmetic over a dependency graph.

Only Finish-to-Start dependencies exist in this domain: a task cannot start
before every one of its predecessors has finished.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.domain.errors import DependencyCycleError
from app.domain.models import Task
from app.scheduler.calendar import add_workdays, first_workday_after, is_weekend, next_workday


@dataclass(frozen=True)
class ScheduleWarning:
    code: str
    message: str
    task_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ScheduleResult:
    tasks: list[Task]
    project_start_date: date
    warnings: list[ScheduleWarning]


def compute_schedule(tasks: list[Task], project_start_date: date) -> ScheduleResult:
    warnings: list[ScheduleWarning] = []

    normalized_start = next_workday(project_start_date)
    if normalized_start != project_start_date:
        warnings.append(
            ScheduleWarning(
                code="PROJECT_START_NORMALIZED",
                message=(
                    f"Дата начала проекта {project_start_date.isoformat()} приходится на выходной "
                    f"и перенесена на {normalized_start.isoformat()}."
                ),
            )
        )

    by_id: dict[uuid.UUID, Task] = {task.id: task for task in tasks}
    order = _topological_order(tasks)

    computed_end: dict[uuid.UUID, date] = {}
    computed_start: dict[uuid.UUID, date] = {}
    result_tasks: list[Task] = []

    for task_id in order:
        task = by_id[task_id]

        if task.predecessor_ids:
            latest_predecessor_end = max(computed_end[pred_id] for pred_id in task.predecessor_ids)
            earliest_start = first_workday_after(latest_predecessor_end)
        else:
            earliest_start = normalized_start

        constraint = task.start_not_before
        if constraint is not None:
            normalized_constraint = next_workday(constraint)
            if normalized_constraint != constraint:
                warnings.append(
                    ScheduleWarning(
                        code="START_NOT_BEFORE_NORMALIZED",
                        message=(
                            f"Ограничение «не ранее» {constraint.isoformat()} для задачи "
                            f"«{task.name}» приходится на выходной и перенесено на "
                            f"{normalized_constraint.isoformat()}."
                        ),
                        task_id=task.id,
                    )
                )
            start = max(earliest_start, normalized_constraint)
        else:
            start = earliest_start

        end = add_workdays(start, task.duration_workdays - 1)

        computed_start[task.id] = start
        computed_end[task.id] = end
        result_tasks.append(task.model_copy(update={"start_date": start, "end_date": end}))

    result_tasks.sort(key=lambda t: t.display_order)
    return ScheduleResult(tasks=result_tasks, project_start_date=normalized_start, warnings=warnings)


def _topological_order(tasks: list[Task]) -> list[uuid.UUID]:
    """Kahn's algorithm with `display_order` as the tie-breaker among tasks
    that are simultaneously ready, so the output ordering is stable and does
    not depend on dict/set iteration order."""

    by_id = {task.id: task for task in tasks}
    in_degree: dict[uuid.UUID, int] = {task.id: len(task.predecessor_ids) for task in tasks}
    successors: dict[uuid.UUID, list[uuid.UUID]] = {task.id: [] for task in tasks}

    for task in tasks:
        for pred_id in task.predecessor_ids:
            if pred_id not in by_id:
                raise ValueError(
                    f"Task {task.id} references unknown predecessor {pred_id}; "
                    "predecessor existence must be validated before scheduling."
                )
            successors[pred_id].append(task.id)

    ready = [task_id for task_id, degree in in_degree.items() if degree == 0]
    ready.sort(key=lambda task_id: by_id[task_id].display_order)

    order: list[uuid.UUID] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        newly_ready: list[uuid.UUID] = []
        for succ_id in successors[current]:
            in_degree[succ_id] -= 1
            if in_degree[succ_id] == 0:
                newly_ready.append(succ_id)
        if newly_ready:
            ready.extend(newly_ready)
            ready.sort(key=lambda task_id: by_id[task_id].display_order)

    if len(order) != len(tasks):
        unresolved = [task_id for task_id in in_degree if task_id not in order]
        unresolved_names = ", ".join(f"«{by_id[t].name}»" for t in unresolved)
        raise DependencyCycleError(
            f"Обнаружен цикл зависимостей среди задач: {unresolved_names}.",
            details=[{"task_id": str(t)} for t in unresolved],
        )

    return order


__all__ = ["compute_schedule", "ScheduleResult", "ScheduleWarning", "is_weekend"]
