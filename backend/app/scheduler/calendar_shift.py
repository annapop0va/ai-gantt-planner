"""Signed working-day shift, split out from calendar.py because it is only
needed by move_task (which must support moving a task *earlier*)."""

from __future__ import annotations

from datetime import date, timedelta

from app.scheduler.calendar import is_weekend


def shift_workdays(start: date, offset: int) -> date:
    if offset == 0:
        return start
    step = 1 if offset > 0 else -1
    cursor = start
    remaining = abs(offset)
    while remaining > 0:
        cursor += timedelta(days=step)
        if not is_weekend(cursor):
            remaining -= 1
    return cursor
