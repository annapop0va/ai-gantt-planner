"""In-memory project store (product-spec §20).

One process, one worker, no persistence — state is lost on restart. That is
an explicit MVP constraint, not an oversight (see docs/backend-architecture.md).

Each project has its own `asyncio.Lock`. `apply()` is the only way to mutate
a stored project: it acquires the lock, re-reads the current revision *inside*
the lock, and only then calls the caller-supplied mutator — so a revision
check can never race with another request's commit, even though this store
itself is single-process/single-worker.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from app.domain.errors import ProjectNotFoundError, RevisionConflictError
from app.domain.models import Project

Mutator = Callable[[Project], Awaitable[Project]]


class InMemoryProjectStore:
    def __init__(self) -> None:
        self._projects: dict[uuid.UUID, Project] = {}
        self._locks: dict[uuid.UUID, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock_for(self, project_id: uuid.UUID) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(project_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[project_id] = lock
            return lock

    async def create(self, project: Project) -> Project:
        lock = await self._lock_for(project.id)
        async with lock:
            self._projects[project.id] = project
            return project

    async def get(self, project_id: uuid.UUID) -> Project:
        lock = await self._lock_for(project_id)
        async with lock:
            return self._get_unlocked(project_id)

    async def apply(
        self,
        project_id: uuid.UUID,
        *,
        expected_revision: int | None,
        mutator: Mutator,
    ) -> Project:
        """Atomically: lock -> read current -> check revision -> mutate -> store.

        `mutator` receives the current committed `Project` (never mutate it in
        place — it is still the store's committed copy until this returns) and
        must return the full next `Project`. If `mutator` raises, nothing is
        stored and the revision is untouched.
        """
        lock = await self._lock_for(project_id)
        async with lock:
            current = self._get_unlocked(project_id)
            if expected_revision is not None and current.revision != expected_revision:
                raise RevisionConflictError(
                    f"Expected revision {expected_revision}, project is at revision {current.revision}.",
                    details=[{"expected": expected_revision, "actual": current.revision}],
                )
            next_project = await mutator(current)
            self._projects[project_id] = next_project
            return next_project

    def _get_unlocked(self, project_id: uuid.UUID) -> Project:
        project = self._projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project {project_id} not found.")
        return project
