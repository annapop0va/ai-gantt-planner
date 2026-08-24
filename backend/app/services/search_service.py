"""Deterministic, read-only task search — no regex/SQL/user code, just
substring matching over normalized names/assignees with a simple, stable
relevance ranking. Backs the MCP `search_tasks` tool.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Project, Task
from app.domain.normalize import normalize_name


@dataclass(frozen=True)
class TaskSearchHit:
    task: Task
    relevance: float


def search_tasks(project: Project, query: str, *, limit: int) -> list[TaskSearchHit]:
    normalized_query = normalize_name(query)
    if not normalized_query:
        return []

    hits: list[TaskSearchHit] = []
    for task in project.tasks:
        score = _score(normalized_query, task)
        if score > 0:
            hits.append(TaskSearchHit(task=task, relevance=score))

    hits.sort(key=lambda hit: (-hit.relevance, hit.task.display_order))
    return hits[:limit]


def _score(normalized_query: str, task: Task) -> float:
    name = normalize_name(task.name)
    if name == normalized_query:
        return 1.0
    if name.startswith(normalized_query):
        return 0.9
    if normalized_query in name:
        return 0.7
    if task.assignee and normalized_query in normalize_name(task.assignee):
        return 0.5
    return 0.0
