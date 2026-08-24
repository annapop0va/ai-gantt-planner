from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from app.domain.errors import DependencyCycleError
from app.scheduler.engine import compute_schedule
from tests.conftest import CANONICAL_START_DATE, REPO_ROOT, make_task


def test_single_task_starts_on_project_start_date():
    t = make_task(name="Only task", duration_workdays=3, display_order=1)
    result = compute_schedule([t], CANONICAL_START_DATE)
    assert result.tasks[0].start_date == CANONICAL_START_DATE


def test_duration_is_inclusive_of_start_day():
    # Monday 2026-09-07, 5 workdays -> ends Friday 2026-09-11 (not the following Monday).
    t = make_task(name="Week task", duration_workdays=5, display_order=1)
    result = compute_schedule([t], CANONICAL_START_DATE)
    assert result.tasks[0].start_date == date(2026, 9, 7)
    assert result.tasks[0].end_date == date(2026, 9, 11)


def test_friday_plus_two_days_lands_on_monday():
    # Start Friday 2026-09-11, duration 1 -> ends same Friday. A 2-day successor
    # must start the next Monday and run through Tuesday.
    friday_task = make_task(name="Friday task", duration_workdays=1, display_order=1)
    successor = make_task(
        name="Successor", duration_workdays=2, predecessor_ids=[friday_task.id], display_order=2
    )
    result = compute_schedule([friday_task, successor], date(2026, 9, 11))
    by_name = {t.name: t for t in result.tasks}
    assert by_name["Friday task"].end_date == date(2026, 9, 11)
    assert by_name["Successor"].start_date == date(2026, 9, 14)  # Monday
    assert by_name["Successor"].end_date == date(2026, 9, 15)  # Tuesday


def test_linear_chain():
    a = make_task(name="A", duration_workdays=2, display_order=1)
    b = make_task(name="B", duration_workdays=3, predecessor_ids=[a.id], display_order=2)
    c = make_task(name="C", duration_workdays=1, predecessor_ids=[b.id], display_order=3)
    result = compute_schedule([a, b, c], CANONICAL_START_DATE)
    by_name = {t.name: t for t in result.tasks}
    assert by_name["A"].start_date == date(2026, 9, 7)
    assert by_name["A"].end_date == date(2026, 9, 8)
    assert by_name["B"].start_date == date(2026, 9, 9)
    assert by_name["B"].end_date == date(2026, 9, 11)
    assert by_name["C"].start_date == date(2026, 9, 14)
    assert by_name["C"].end_date == date(2026, 9, 14)


def test_parallel_branches_run_independently():
    root = make_task(name="Root", duration_workdays=1, display_order=1)
    left = make_task(name="Left", duration_workdays=2, predecessor_ids=[root.id], display_order=2)
    right = make_task(name="Right", duration_workdays=5, predecessor_ids=[root.id], display_order=3)
    result = compute_schedule([root, left, right], CANONICAL_START_DATE)
    by_name = {t.name: t for t in result.tasks}
    assert by_name["Left"].start_date == by_name["Right"].start_date == date(2026, 9, 8)
    assert by_name["Left"].end_date == date(2026, 9, 9)
    assert by_name["Right"].end_date == date(2026, 9, 14)


def test_multiple_predecessors_wait_for_the_latest():
    a = make_task(name="A", duration_workdays=2, display_order=1)  # ends 2026-09-08
    b = make_task(name="B", duration_workdays=5, display_order=2)  # ends 2026-09-11
    join = make_task(name="Join", duration_workdays=1, predecessor_ids=[a.id, b.id], display_order=3)
    result = compute_schedule([a, b, join], CANONICAL_START_DATE)
    by_name = {t.name: t for t in result.tasks}
    assert by_name["Join"].start_date == date(2026, 9, 14)  # first workday after 09-11


def test_independent_roots_both_start_on_project_start():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(name="B", duration_workdays=1, display_order=2)
    result = compute_schedule([a, b], CANONICAL_START_DATE)
    assert all(t.start_date == CANONICAL_START_DATE for t in result.tasks)


def test_start_not_before_pushes_start_later_than_dependency_would_allow():
    a = make_task(name="A", duration_workdays=1, display_order=1)  # ends 2026-09-07
    b = make_task(
        name="B",
        duration_workdays=1,
        predecessor_ids=[a.id],
        start_not_before=date(2026, 9, 21),
        display_order=2,
    )
    result = compute_schedule([a, b], CANONICAL_START_DATE)
    by_name = {t.name: t for t in result.tasks}
    assert by_name["B"].start_date == date(2026, 9, 21)


def test_start_not_before_does_not_override_a_later_dependency_start():
    a = make_task(name="A", duration_workdays=10, display_order=1)  # ends 2026-09-18
    b = make_task(
        name="B",
        duration_workdays=1,
        predecessor_ids=[a.id],
        start_not_before=date(2026, 9, 8),  # earlier than dependency allows
        display_order=2,
    )
    result = compute_schedule([a, b], CANONICAL_START_DATE)
    by_name = {t.name: t for t in result.tasks}
    assert by_name["B"].start_date == date(2026, 9, 21)  # first workday after A ends


def test_weekend_project_start_is_normalized_forward_with_warning():
    saturday = date(2026, 9, 12)
    t = make_task(name="Only task", duration_workdays=1, display_order=1)
    result = compute_schedule([t], saturday)
    assert result.project_start_date == date(2026, 9, 14)  # Monday
    assert result.tasks[0].start_date == date(2026, 9, 14)
    codes = [w.code for w in result.warnings]
    assert "PROJECT_START_NORMALIZED" in codes


def test_weekend_start_not_before_is_normalized_forward_with_warning():
    a = make_task(name="A", duration_workdays=1, display_order=1)
    b = make_task(
        name="B",
        duration_workdays=1,
        predecessor_ids=[a.id],
        start_not_before=date(2026, 9, 12),  # Saturday
        display_order=2,
    )
    result = compute_schedule([a, b], CANONICAL_START_DATE)
    by_name = {t.name: t for t in result.tasks}
    assert by_name["B"].start_date == date(2026, 9, 14)
    codes = [w.code for w in result.warnings]
    assert "START_NOT_BEFORE_NORMALIZED" in codes


def test_cycle_is_detected_and_rejected():
    a_id, b_id = uuid.uuid4(), uuid.uuid4()
    a = make_task(name="A", duration_workdays=1, predecessor_ids=[b_id], display_order=1, task_id=a_id)
    b = make_task(name="B", duration_workdays=1, predecessor_ids=[a_id], display_order=2, task_id=b_id)
    with pytest.raises(DependencyCycleError):
        compute_schedule([a, b], CANONICAL_START_DATE)


def test_deterministic_order_uses_display_order_as_tie_breaker():
    root = make_task(name="Root", duration_workdays=1, display_order=1)
    # Two tasks become ready at the same time; display_order must break the tie
    # the same way on every run.
    late = make_task(name="Z", duration_workdays=1, predecessor_ids=[root.id], display_order=10)
    early = make_task(name="A", duration_workdays=1, predecessor_ids=[root.id], display_order=2)
    result_1 = compute_schedule([root, late, early], CANONICAL_START_DATE)
    result_2 = compute_schedule([root, late, early], CANONICAL_START_DATE)
    order_1 = [t.id for t in result_1.tasks]
    order_2 = [t.id for t in result_2.tasks]
    assert order_1 == order_2
    # Output is always re-sorted by display_order for presentation.
    assert [t.display_order for t in result_1.tasks] == sorted(t.display_order for t in result_1.tasks)


def test_exact_canonical_schedule_matches_fixture():
    """Rebuild the 16-task canonical graph (names/durations/predecessors only,
    no dates) and confirm the scheduler reproduces every date in
    fixtures/mock_project_before.json, semantically (by task name), not by UUID."""
    fixture_path = REPO_ROOT / "fixtures" / "mock_project_before.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    id_map: dict[str, uuid.UUID] = {t["id"]: uuid.uuid4() for t in fixture["tasks"]}
    tasks = [
        make_task(
            name=t["name"],
            duration_workdays=t["duration_workdays"],
            predecessor_ids=[id_map[p] for p in t["predecessor_ids"]],
            display_order=t["display_order"],
            start_not_before=date.fromisoformat(t["start_not_before"]) if t["start_not_before"] else None,
            task_id=id_map[t["id"]],
        )
        for t in fixture["tasks"]
    ]

    result = compute_schedule(tasks, date.fromisoformat(fixture["project_start_date"]))

    expected_by_name = {t["name"]: t for t in fixture["tasks"]}
    for task in result.tasks:
        expected = expected_by_name[task.name]
        assert task.start_date.isoformat() == expected["start_date"], task.name
        assert task.end_date.isoformat() == expected["end_date"], task.name

    release = max(result.tasks, key=lambda t: t.end_date)
    assert release.end_date == date(2026, 11, 2)
