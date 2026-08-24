from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.diff import ChangeSummary
from app.schemas.project import ProjectOut


class ChangeSetResponse(BaseModel):
    status: Literal["applied"] = "applied"
    project: ProjectOut
    change_summary: ChangeSummary
    warnings: list[str] = []
