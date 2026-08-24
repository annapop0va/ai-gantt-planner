"""Applies a validated list of ChangeSet operations to a working copy of
tasks (product-spec §9-§14).

`ChangeSetApplier` never touches the store or the scheduler — it only
mutates an in-memory list of `Task` domain objects and raises a `DomainError`
subclass the moment something is invalid. The caller (ProjectService) is
responsible for: deep-copying tasks before handing them here, running the
scheduler afterwards, and discarding everything if any exception escapes.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.domain.changeset import (
    AddDependency,
    BulkSetAssignee,
    ChangeDuration,
    ClearStartConstraint,
    CreateTask,
    InsertTaskBetween,
    MoveTask,
    Operation,
    RemoveDependency,
    SetPredecessors,
    TaskRef,
    UpdateTaskFields,
)
from app.domain.constants import (
    HOURS_PER_WORKDAY,
    MAX_ASSIGNEE_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_DURATION_WORKDAYS,
    MAX_TASK_NAME_LENGTH,
    MIN_DURATION_WORKDAYS,
)
from app.domain.errors import (
    DateConstraintViolationError,
    DependencyAlreadyExistsError,
    DependencyNotFoundError,
    DuplicateTaskNameError,
    InvalidClientRefError,
    InvalidDurationError,
    InvalidTaskFieldError,
    SelfDependencyError,
    TaskNotFoundError,
    UnresolvedClientRefError,
    UnsupportedEffortGranularityError,
)
from app.domain.models import Task
from app.domain.normalize import normalize_name
from app.scheduler.calendar import first_workday_after
from app.scheduler.calendar_shift import shift_workdays

_PLACEHOLDER_DATE = date(2000, 1, 1)


class ChangeSetApplier:
    def __init__(self, tasks: list[Task], project_start_date: date) -> None:
        self.tasks = list(tasks)
        self.by_id: dict[uuid.UUID, Task] = {t.id: t for t in self.tasks}
        self.client_ref_map: dict[str, uuid.UUID] = {}
        self._project_start_date = project_start_date

    def apply_all(self, operations: list[Operation]) -> list[Task]:
        self._preallocate_client_refs(operations)
        for op in operations:
            self._apply_one(op)
        self._renumber_display_order()
        return self.tasks

    # --- ref resolution -----------------------------------------------------

    def _preallocate_client_refs(self, operations: list[Operation]) -> None:
        for op in operations:
            if isinstance(op, (CreateTask, InsertTaskBetween)):
                if op.client_ref in self.client_ref_map:
                    raise InvalidClientRefError(f"Duplicate client_ref '{op.client_ref}' in change set.")
                self.client_ref_map[op.client_ref] = uuid.uuid4()

    def _resolve(self, ref: TaskRef) -> uuid.UUID:
        if ref.task_id is not None:
            if ref.task_id not in self.by_id:
                raise TaskNotFoundError(f"Task {ref.task_id} not found.")
            return ref.task_id
        task_id = self.client_ref_map.get(ref.client_ref)  # type: ignore[arg-type]
        if task_id is None:
            raise UnresolvedClientRefError(f"client_ref '{ref.client_ref}' does not resolve to any task.")
        return task_id

    # --- dispatch -------------------------------------------------------------

    def _apply_one(self, op: Operation) -> None:
        handler = getattr(self, f"_op_{op.op}")
        handler(op)

    # --- operations -----------------------------------------------------------

    def _op_update_task_fields(self, op: UpdateTaskFields) -> None:
        task = self.by_id[self._resolve(op.task)]

        if op.name is not None:
            name = _validate_name(op.name)
            self._check_name_available(name, exclude=task.id)
            task.name = name
        if op.description is not None:
            task.description = _validate_description(op.description)
        if op.clear_assignee:
            task.assignee = None
        elif op.assignee is not None:
            task.assignee = _validate_assignee(op.assignee)

    def _op_change_duration(self, op: ChangeDuration) -> None:
        task = self.by_id[self._resolve(op.task)]

        if op.unit == "person_hours":
            if op.value % HOURS_PER_WORKDAY != 0:
                raise UnsupportedEffortGranularityError(
                    f"{op.value} person-hours is not divisible by {HOURS_PER_WORKDAY}; "
                    "durations are whole workdays only."
                )
            delta_workdays = op.value // HOURS_PER_WORKDAY
        else:
            delta_workdays = op.value

        if op.mode == "set":
            new_duration = delta_workdays
        elif op.mode == "add":
            new_duration = task.duration_workdays + delta_workdays
        else:
            new_duration = task.duration_workdays - delta_workdays

        if not (MIN_DURATION_WORKDAYS <= new_duration <= MAX_DURATION_WORKDAYS):
            raise InvalidDurationError(
                f"Resulting duration {new_duration} workdays is outside "
                f"[{MIN_DURATION_WORKDAYS}, {MAX_DURATION_WORKDAYS}]."
            )
        task.duration_workdays = new_duration

    def _op_move_task(self, op: MoveTask) -> None:
        task = self.by_id[self._resolve(op.task)]

        if op.offset_workdays is not None:
            target = shift_workdays(task.start_date, op.offset_workdays)
        else:
            target = op.target_start_date  # type: ignore[assignment]

        earliest_start = self._dependency_earliest_start(task)
        if target < earliest_start:
            raise DateConstraintViolationError(
                f"Задачу «{task.name}» нельзя перенести на {target.isoformat()}: "
                f"она не может начаться раньше {earliest_start.isoformat()} из-за зависимостей.",
                details=[{"task_id": str(task.id), "earliest_start": earliest_start.isoformat()}],
            )
        task.start_not_before = target

    def _op_clear_start_constraint(self, op: ClearStartConstraint) -> None:
        task = self.by_id[self._resolve(op.task)]
        task.start_not_before = None

    def _op_create_task(self, op: CreateTask) -> None:
        task_id = self.client_ref_map[op.client_ref]
        name = _validate_name(op.name)
        self._check_name_available(name, exclude=None)

        predecessor_ids = [self._resolve(ref) for ref in op.predecessor_refs]

        task = Task(
            id=task_id,
            name=name,
            description=_validate_description(op.description),
            assignee=_validate_assignee(op.assignee),
            duration_workdays=_validate_duration(op.duration_workdays),
            predecessor_ids=predecessor_ids,
            start_not_before=op.start_not_before,
            start_date=_PLACEHOLDER_DATE,
            end_date=_PLACEHOLDER_DATE,
            display_order=0,
            created_source="agent",
        )
        after_id = self._resolve(op.display_after_ref) if op.display_after_ref else None
        self._insert_after(task, after_id)

    def _op_insert_task_between(self, op: InsertTaskBetween) -> None:
        pred_id = self._resolve(op.predecessor)
        succ_id = self._resolve(op.successor)
        successor = self.by_id[succ_id]

        if pred_id not in successor.predecessor_ids:
            raise DependencyNotFoundError(
                "insert_task_between requires a direct predecessor -> successor edge."
            )

        task_id = self.client_ref_map[op.client_ref]
        name = _validate_name(op.name)
        self._check_name_available(name, exclude=None)

        new_task = Task(
            id=task_id,
            name=name,
            description=_validate_description(op.description),
            assignee=_validate_assignee(op.assignee),
            duration_workdays=_validate_duration(op.duration_workdays),
            predecessor_ids=[pred_id],
            start_not_before=None,
            start_date=_PLACEHOLDER_DATE,
            end_date=_PLACEHOLDER_DATE,
            display_order=0,
            created_source="agent",
        )
        successor.predecessor_ids = [task_id if p == pred_id else p for p in successor.predecessor_ids]
        self._insert_after(new_task, pred_id)

    def _op_set_predecessors(self, op: SetPredecessors) -> None:
        task = self.by_id[self._resolve(op.task)]
        resolved: list[uuid.UUID] = []
        for ref in op.predecessor_refs:
            pred_id = self._resolve(ref)
            if pred_id == task.id:
                raise SelfDependencyError(f"Task «{task.name}» cannot depend on itself.")
            if pred_id not in resolved:
                resolved.append(pred_id)
        task.predecessor_ids = resolved

    def _op_add_dependency(self, op: AddDependency) -> None:
        pred_id = self._resolve(op.predecessor)
        succ_id = self._resolve(op.successor)
        if pred_id == succ_id:
            raise SelfDependencyError("A task cannot depend on itself.")
        successor = self.by_id[succ_id]
        if pred_id in successor.predecessor_ids:
            raise DependencyAlreadyExistsError(
                f"«{self.by_id[pred_id].name}» is already a predecessor of «{successor.name}»."
            )
        successor.predecessor_ids = [*successor.predecessor_ids, pred_id]

    def _op_remove_dependency(self, op: RemoveDependency) -> None:
        pred_id = self._resolve(op.predecessor)
        succ_id = self._resolve(op.successor)
        successor = self.by_id[succ_id]
        if pred_id not in successor.predecessor_ids:
            raise DependencyNotFoundError(
                f"«{self.by_id[pred_id].name}» is not a predecessor of «{successor.name}»."
            )
        successor.predecessor_ids = [p for p in successor.predecessor_ids if p != pred_id]

    def _op_bulk_set_assignee(self, op: BulkSetAssignee) -> None:
        resolved_ids: list[uuid.UUID] = []
        for ref in op.tasks:
            task_id = self._resolve(ref)
            if task_id in resolved_ids:
                raise InvalidTaskFieldError("bulk_set_assignee task list must not contain duplicates.")
            resolved_ids.append(task_id)
        assignee = _validate_assignee(op.assignee)
        for task_id in resolved_ids:
            self.by_id[task_id].assignee = assignee

    # --- helpers ---------------------------------------------------------------

    def _dependency_earliest_start(self, task: Task) -> date:
        if not task.predecessor_ids:
            return self._project_start_date
        latest_end = max(self.by_id[p].end_date for p in task.predecessor_ids)
        return first_workday_after(latest_end)

    def _check_name_available(self, name: str, *, exclude: uuid.UUID | None) -> None:
        normalized = normalize_name(name)
        for other in self.tasks:
            if other.id == exclude:
                continue
            if normalize_name(other.name) == normalized:
                raise DuplicateTaskNameError(f"Task name «{name}» is already used by another task.")

    def _insert_after(self, task: Task, after_id: uuid.UUID | None) -> None:
        if after_id is None:
            self.tasks.append(task)
        else:
            index = next(i for i, t in enumerate(self.tasks) if t.id == after_id)
            self.tasks.insert(index + 1, task)
        self.by_id[task.id] = task

    def _renumber_display_order(self) -> None:
        for index, task in enumerate(self.tasks, start=1):
            task.display_order = index


def _validate_name(name: str) -> str:
    stripped = name.strip()
    if not (1 <= len(stripped) <= MAX_TASK_NAME_LENGTH):
        raise InvalidTaskFieldError(f"Task name must be 1-{MAX_TASK_NAME_LENGTH} characters.")
    if ";" in stripped:
        raise InvalidTaskFieldError("Task name must not contain ';'.")
    return stripped


def _validate_description(description: str) -> str:
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise InvalidTaskFieldError(f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters.")
    return description


def _validate_assignee(assignee: str | None) -> str | None:
    if assignee is None:
        return None
    stripped = assignee.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_ASSIGNEE_LENGTH:
        raise InvalidTaskFieldError(f"Assignee must be at most {MAX_ASSIGNEE_LENGTH} characters.")
    return stripped


def _validate_duration(duration: int) -> int:
    if not (MIN_DURATION_WORKDAYS <= duration <= MAX_DURATION_WORKDAYS):
        raise InvalidDurationError(
            f"Duration {duration} workdays is outside [{MIN_DURATION_WORKDAYS}, {MAX_DURATION_WORKDAYS}]."
        )
    return duration
