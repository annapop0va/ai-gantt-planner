from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.diff import ChangeSummary
from app.schemas.project import ProjectOut


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    expected_revision: int


class ChatResponse(BaseModel):
    status: Literal["applied", "clarification_required", "rejected"]
    message: str
    # Only populated for "applied" — the other two statuses leave the project
    # untouched, so the frontend keeps what it already has (see
    # docs/backend-contract-audit.md for the adapter that consumes this).
    project: ProjectOut | None = None
    change_summary: ChangeSummary | None = None
    warnings: list[str] = []
