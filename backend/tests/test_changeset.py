from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest

from app.domain.changeset import ChangeSetRequest
from app.domain.errors import (
    DateConstraintViolationError,
    DependencyCycleError,
    DependencyNotFoundError,
    DuplicateTaskNameError,
    InvalidClientRefError,
    InvalidDurationError,
    RevisionConflictError,
    UnresolvedClientRefError,
    UnsupportedEffortGranularityError,
)
from app.scheduler.engine import compute_schedule
from app.services.changeset_ops import ChangeSetApplier
from app.services.project_service import ProjectService
from app.storage.project_store import InMemoryProjectStore
from tests.conftest import CANONICAL_START_DATE, SAMPLE_XLSX_PATH, make_project, make_task


def _scheduled_project(tasks, *, revision=1, start=CANONICAL_START_DATE):
    schedule = compute_schedule(tasks, start)
    project = make_project(schedule.tasks, revision=revision, project_start_date=start)
    return project


def _apply(tasks, ops, *, start=CANONICAL_START_DATE):
    applier = ChangeSetApplier([t.model_copy(deep=True) for t in tasks], start)
    return applier.apply_all(ops)


async def _import_sample_project(store: InMemoryProjectStore) -> tuple[ProjectService, "Project"]:  # noqa: F821
    service = ProjectService(store)
    content = SAMPLE_XLSX_PATH.read_bytes()
    project, _warnings = await service.import_project(
        content=content, filename=SAMPLE_XLSX_PATH.name, project_start_date=CANONICAL_START_DATE
    )
    return service, project


def test_change_duration_set_person_hours_24_equals_3_days():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "change_duration", "task": {"task_id": str(a.id)}, "mode": "set", "unit": "person_hours", "value": 24}
            ],
        }
    ).operations
    result = _apply([a], ops)
    assert result[0].duration_workdays == 3


def test_change_duration_add_16_hours_adds_2_days():
    a = make_task(name="A", duration_workdays=5, display_order=1)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "change_duration", "task": {"task_id": str(a.id)}, "mode": "add", "unit": "person_hours", "value": 16}
            ],
        }
    ).operations
    result = _apply([a], ops)
    assert result[0].duration_workdays == 7


def test_change_duration_12_hours_rejected_no_silent_rounding():
    a = make_task(name="A", duration_workdays=5, display_order=1)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "change_duration", "task": {"task_id": str(a.id)}, "mode": "set", "unit": "person_hours", "value": 12}
            ],
        }
    ).operations
    with pytest.raises(UnsupportedEffortGranularityError):
        _apply([a], ops)


def test_subtract_below_minimum_is_rejected():
    a = make_task(name="A", duration_workdays=2, display_order=1)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "change_duration", "task": {"task_id": str(a.id)}, "mode": "subtract", "unit": "workdays", "value": 5}
            ],
        }
    ).operations
    with pytest.raises(InvalidDurationError):
        _apply([a], ops)


def test_move_task_earlier_violating_dependency_is_rejected():
    a = make_task(name="A", duration_workdays=10, display_order=1)  # ends 2026-09-18
    b = make_task(name="B", duration_workdays=1, predecessor_ids=[a.id], display_order=2)
    scheduled = compute_schedule([a, b], CANONICAL_START_DATE).tasks

    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "move_task", "task": {"task_id": str(b.id)}, "target_start_date": "2026-09-08"}
            ],
        }
    ).operations
    with pytest.raises(DateConstraintViolationError):
        _apply(scheduled, ops)


def test_move_task_later_sets_start_not_before():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    scheduled = compute_schedule([a], CANONICAL_START_DATE).tasks
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "move_task", "task": {"task_id": str(a.id)}, "offset_workdays": 3}
            ],
        }
    ).operations
    result = _apply(scheduled, ops)
    assert result[0].start_not_before == date(2026, 9, 10)


def test_clear_start_constraint_lets_scheduler_pick_earliest():
    a = make_task(name="A", duration_workdays=1, display_order=1, start_not_before=date(2026, 9, 21))
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [{"op": "clear_start_constraint", "task": {"task_id": str(a.id)}}],
        }
    ).operations
    result = _apply([a], ops)
    assert result[0].start_not_before is None
    scheduled = compute_schedule(result, CANONICAL_START_DATE)
    assert scheduled.tasks[0].start_date == CANONICAL_START_DATE


def test_rename_to_duplicate_name_is_rejected():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(name="B", duration_workdays=1, display_order=2)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "update_task_fields", "task": {"task_id": str(b.id)}, "name": "A"}
            ],
        }
    ).operations
    with pytest.raises(DuplicateTaskNameError):
        _apply([a, b], ops)


def test_insert_task_between_requires_direct_edge():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(name="B", duration_workdays=1, display_order=2)  # not a successor of A
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {
                    "op": "insert_task_between",
                    "client_ref": "mid",
                    "name": "Mid",
                    "duration_workdays": 1,
                    "predecessor": {"task_id": str(a.id)},
                    "successor": {"task_id": str(b.id)},
                }
            ],
        }
    ).operations
    with pytest.raises(DependencyNotFoundError):
        _apply([a, b], ops)


def test_insert_task_between_rewires_edge_atomically():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(name="B", duration_workdays=1, predecessor_ids=[a.id], display_order=2)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {
                    "op": "insert_task_between",
                    "client_ref": "mid",
                    "name": "Mid",
                    "duration_workdays": 1,
                    "predecessor": {"task_id": str(a.id)},
                    "successor": {"task_id": str(b.id)},
                }
            ],
        }
    ).operations
    result = _apply([a, b], ops)
    by_name = {t.name: t for t in result}
    assert by_name["B"].predecessor_ids == [by_name["Mid"].id]
    assert by_name["Mid"].predecessor_ids == [a.id]


def test_duplicate_client_ref_is_rejected():
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "create_task", "client_ref": "x", "name": "One", "duration_workdays": 1},
                {"op": "create_task", "client_ref": "x", "name": "Two", "duration_workdays": 1},
            ],
        }
    ).operations
    with pytest.raises(InvalidClientRefError):
        _apply([], ops)


def test_unresolved_client_ref_is_rejected():
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "create_task", "client_ref": "x", "name": "One", "duration_workdays": 1, "predecessor_refs": [{"client_ref": "missing"}]},
            ],
        }
    ).operations
    with pytest.raises(UnresolvedClientRefError):
        _apply([], ops)


def test_forward_client_ref_within_same_change_set_resolves():
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                # References "second", defined later in the same operations list.
                {"op": "create_task", "client_ref": "first", "name": "First", "duration_workdays": 1, "predecessor_refs": [{"client_ref": "second"}]},
                {"op": "create_task", "client_ref": "second", "name": "Second", "duration_workdays": 1},
            ],
        }
    ).operations
    result = _apply([], ops)
    by_name = {t.name: t for t in result}
    assert by_name["Second"].id in by_name["First"].predecessor_ids


def test_cycle_introduced_by_change_set_is_rejected():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(name="B", duration_workdays=1, predecessor_ids=[a.id], display_order=2)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "add_dependency", "predecessor": {"task_id": str(b.id)}, "successor": {"task_id": str(a.id)}}
            ],
        }
    ).operations
    applied = _apply([a, b], ops)
    with pytest.raises(DependencyCycleError):
        compute_schedule(applied, CANONICAL_START_DATE)


def test_deterministic_display_order_after_creates():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(name="B", duration_workdays=1, display_order=2)
    ops = ChangeSetRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {"op": "create_task", "client_ref": "new", "name": "New", "duration_workdays": 1, "display_after_ref": {"task_id": str(a.id)}},
            ],
        }
    ).operations
    result = _apply([a, b], ops)
    assert [t.name for t in result] == ["A", "New", "B"]
    assert [t.display_order for t in result] == [1, 2, 3]


# --- ProjectService-level (async, atomicity, revision) ------------------------


def test_canonical_change_set_end_to_end():
    async def run():
        store = InMemoryProjectStore()
        service, project = await _import_sample_project(store)
        assert len(project.tasks) == 16
        assert project.revision == 1

        by_name = {t.name: t for t in project.tasks}
        agreement = by_name["Согласование требований к карточке пациента и расписанию врача"]
        frontend = by_name["Frontend-разработка карточки пациента"]
        dev_result = by_name["Согласование результата разработки"]
        qa = by_name["QA-тестирование карточки пациента"]

        request = ChangeSetRequest.model_validate(
            {
                "expected_revision": 1,
                "operations": [
                    {"op": "change_duration", "task": {"task_id": str(agreement.id)}, "mode": "set", "unit": "workdays", "value": 5},
                    {"op": "change_duration", "task": {"task_id": str(frontend.id)}, "mode": "set", "unit": "workdays", "value": 8},
                    {
                        "op": "create_task",
                        "client_ref": "backend_fix",
                        "name": "Правки backend по итогам согласования",
                        "assignee": "Василий",
                        "duration_workdays": 2,
                        "predecessor_refs": [{"task_id": str(dev_result.id)}],
                        "display_after_ref": {"task_id": str(dev_result.id)},
                    },
                    {
                        "op": "create_task",
                        "client_ref": "frontend_fix",
                        "name": "Правки frontend по итогам согласования",
                        "assignee": "Дмитрий",
                        "duration_workdays": 3,
                        "predecessor_refs": [{"task_id": str(dev_result.id)}],
                        "display_after_ref": {"client_ref": "backend_fix"},
                    },
                    {
                        "op": "set_predecessors",
                        "task": {"task_id": str(qa.id)},
                        "predecessor_refs": [{"client_ref": "backend_fix"}, {"client_ref": "frontend_fix"}],
                    },
                ],
            }
        )
        result = await service.apply_change_set(project.id, request)
        new_project, summary = result.project, result.change_summary
        assert len(new_project.tasks) == 18
        assert new_project.revision == 2
        release = max(new_project.tasks, key=lambda t: t.end_date)
        assert release.end_date == date(2026, 11, 9)
        assert len(summary.created_tasks) == 2
        assert len(summary.direct_changes) == 3  # agreement, frontend, QA predecessors
        assert set(result.client_ref_map) == {"backend_fix", "frontend_fix"}
        created_ids = {c.task_id for c in summary.created_tasks}
        assert set(result.client_ref_map.values()) == created_ids

    asyncio.run(run())


def test_rollback_on_invalid_operation_leaves_revision_untouched():
    async def run():
        store = InMemoryProjectStore()
        service, project = await _import_sample_project(store)
        task_id = project.tasks[0].id

        bad_request = ChangeSetRequest.model_validate(
            {
                "expected_revision": 1,
                "operations": [
                    {"op": "change_duration", "task": {"task_id": str(task_id)}, "mode": "set", "unit": "workdays", "value": 3},
                    {"op": "change_duration", "task": {"task_id": str(uuid.uuid4())}, "mode": "set", "unit": "workdays", "value": 1},
                ],
            }
        )
        with pytest.raises(Exception):
            await service.apply_change_set(project.id, bad_request)

        reloaded = await service.get_project(project.id)
        assert reloaded.revision == 1
        assert reloaded.tasks[0].duration_workdays == project.tasks[0].duration_workdays

    asyncio.run(run())


def test_stale_revision_is_rejected_under_concurrent_apply():
    async def run():
        store = InMemoryProjectStore()
        service, project = await _import_sample_project(store)
        task_id = project.tasks[0].id

        def request(value: int) -> ChangeSetRequest:
            return ChangeSetRequest.model_validate(
                {
                    "expected_revision": 1,
                    "operations": [
                        {"op": "change_duration", "task": {"task_id": str(task_id)}, "mode": "set", "unit": "workdays", "value": value}
                    ],
                }
            )

        results = await asyncio.gather(
            service.apply_change_set(project.id, request(2)),
            service.apply_change_set(project.id, request(3)),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], RevisionConflictError)

        final = await service.get_project(project.id)
        assert final.revision == 2

    asyncio.run(run())

