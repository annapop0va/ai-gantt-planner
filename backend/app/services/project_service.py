"""Orchestrates import, retrieval, change-set application and export.

This is the single seam a future MCP tool boundary would call directly
(product-spec §14: "Agent Orchestrator MUST выполнять mutation через MCP
Client, а не напрямую через ProjectService" — meaning MCP calls through this
same service, never around it). Routers must not contain this logic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.domain.changeset import ChangeSetRequest
from app.domain.diff import ChangeSummary, compute_change_summary
from app.domain.models import Project
from app.scheduler.engine import compute_schedule
from app.services.changeset_ops import ChangeSetApplier
from app.services.excel_export import ExcelExportService, export_filename
from app.services.excel_import import ExcelImportService
from app.storage.project_store import InMemoryProjectStore


@dataclass(frozen=True)
class ChangeSetApplyResult:
    project: Project
    change_summary: ChangeSummary
    warnings: list[str]
    client_ref_map: dict[str, uuid.UUID] = field(default_factory=dict)


class ProjectService:
    def __init__(self, store: InMemoryProjectStore) -> None:
        self._store = store
        self._importer = ExcelImportService()
        self._exporter = ExcelExportService()

    async def import_project(
        self, *, content: bytes, filename: str, project_start_date: date
    ) -> tuple[Project, list[str]]:
        parsed = self._importer.parse(content, filename=filename)
        schedule = compute_schedule(parsed.tasks, project_start_date)

        now = datetime.now(timezone.utc)
        project = Project(
            id=uuid.uuid4(),
            name=parsed.project_name,
            project_start_date=schedule.project_start_date,
            revision=1,
            tasks=schedule.tasks,
            created_at=now,
            updated_at=now,
        )
        await self._store.create(project)

        warnings = [*parsed.warnings, *(w.message for w in schedule.warnings)]
        return project, warnings

    async def get_project(self, project_id: uuid.UUID) -> Project:
        return await self._store.get(project_id)

    async def apply_change_set(
        self, project_id: uuid.UUID, request: ChangeSetRequest
    ) -> ChangeSetApplyResult:
        before_snapshot: Project | None = None
        collected_warnings: list[str] = []
        collected_client_ref_map: dict[str, uuid.UUID] = {}

        async def mutator(current: Project) -> Project:
            nonlocal before_snapshot, collected_warnings, collected_client_ref_map
            before_snapshot = current

            working_tasks = [task.model_copy(deep=True) for task in current.tasks]
            applier = ChangeSetApplier(working_tasks, current.project_start_date)
            applied_tasks = applier.apply_all(request.operations)
            collected_client_ref_map = dict(applier.client_ref_map)

            schedule = compute_schedule(applied_tasks, current.project_start_date)
            collected_warnings = [w.message for w in schedule.warnings]

            return current.model_copy(
                update={
                    "tasks": schedule.tasks,
                    "revision": current.revision + 1,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        new_project = await self._store.apply(
            project_id, expected_revision=request.expected_revision, mutator=mutator
        )
        assert before_snapshot is not None  # mutator always runs before apply() returns
        change_summary = compute_change_summary(before_snapshot, new_project)
        return ChangeSetApplyResult(
            project=new_project,
            change_summary=change_summary,
            warnings=collected_warnings,
            client_ref_map=collected_client_ref_map,
        )

    async def export_project(self, project_id: uuid.UUID) -> tuple[bytes, str]:
        project = await self._store.get(project_id)
        content = self._exporter.export(project)
        return content, export_filename(project)
