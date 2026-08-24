"""Mon–Fri working calendar. No holidays (product-spec §8). Date-only, no time
component and no timezone anywhere in this module.
"""

from __future__ import annotations

from datetime import date, timedelta

_SATURDAY = 5
_SUNDAY = 6


def is_weekend(day: date) -> bool:
    return day.weekday() in (_SATURDAY, _SUNDAY)


def next_workday(day: date) -> date:
    """`day` itself if it's already a workday, otherwise the next Monday."""
    while is_weekend(day):
        day += timedelta(days=1)
    return day


def add_workdays(start: date, workdays: int) -> date:
    """`start` plus `workdays` working days, skipping weekends.

    `add_workdays(d, 0) == d` (assuming `d` is itself a workday) — this is
    what makes `end_date = add_workdays(start_date, duration_workdays - 1)`
    correctly treat the start day as day 1 of the duration.
    """
    if workdays < 0:
        raise ValueError("workdays must be >= 0")
    cursor = start
    remaining = workdays
    while remaining > 0:
        cursor += timedelta(days=1)
        if not is_weekend(cursor):
            remaining -= 1
    return cursor


def first_workday_after(day: date) -> date:
    return next_workday(day + timedelta(days=1))


def workdays_between(start: date, end: date) -> int:
    """Count of working days strictly after `start` up to and including `end`.
    Negative when `end` is earlier than `start`. Used for "+N workdays" deltas."""
    if start == end:
        return 0
    forward = end > start
    step = 1 if forward else -1
    cursor = start if forward else end
    target = end if forward else start
    count = 0
    while cursor < target:
        cursor += timedelta(days=1)
        if not is_weekend(cursor):
            count += 1
    return count * step
