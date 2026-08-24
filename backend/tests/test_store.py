from __future__ import annotations

import asyncio

import pytest

from app.domain.errors import ProjectNotFoundError, RevisionConflictError
from app.storage.project_store import InMemoryProjectStore
from tests.conftest import make_project, make_task


def test_two_projects_are_isolated():
    async def run():
        store = InMemoryProjectStore()
        p1 = make_project([make_task(name="A", display_order=1)])
        p2 = make_project([make_task(name="B", display_order=1)])
        await store.create(p1)
        await store.create(p2)

        async def rename(current):
            return current.model_copy(update={"revision": current.revision + 1})

        await store.apply(p1.id, expected_revision=1, mutator=rename)

        reloaded_p1 = await store.get(p1.id)
        reloaded_p2 = await store.get(p2.id)
        assert reloaded_p1.revision == 2
        assert reloaded_p2.revision == 1  # untouched

    asyncio.run(run())


def test_get_missing_project_raises():
    async def run():
        store = InMemoryProjectStore()
        with pytest.raises(ProjectNotFoundError):
            await store.get(make_project([make_task(name="A", display_order=1)]).id)

    asyncio.run(run())


def test_apply_checks_revision_inside_the_lock():
    async def run():
        store = InMemoryProjectStore()
        project = make_project([make_task(name="A", display_order=1)])
        await store.create(project)

        async def bump(current):
            return current.model_copy(update={"revision": current.revision + 1})

        with pytest.raises(RevisionConflictError):
            await store.apply(project.id, expected_revision=99, mutator=bump)

        unchanged = await store.get(project.id)
        assert unchanged.revision == 1

    asyncio.run(run())


def test_mutator_exception_leaves_store_untouched():
    async def run():
        store = InMemoryProjectStore()
        project = make_project([make_task(name="A", display_order=1)])
        await store.create(project)

        async def explode(current):
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await store.apply(project.id, expected_revision=1, mutator=explode)

        unchanged = await store.get(project.id)
        assert unchanged.revision == 1

    asyncio.run(run())
