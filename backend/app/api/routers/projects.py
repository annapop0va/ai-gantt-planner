from __future__ import annotations

import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.api.deps import get_project_service
from app.domain.constants import MAX_FILE_SIZE_BYTES
from app.domain.errors import FileTooLargeError
from app.schemas.project import ImportResponse, ProjectOut, project_to_out
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_READ_CHUNK_SIZE = 1024 * 1024


@router.post("/import", response_model=ImportResponse, status_code=201)
async def import_project(
    file: UploadFile = File(...),
    project_start_date: date = Form(...),
    service: ProjectService = Depends(get_project_service),
) -> ImportResponse:
    content = await _read_capped(file)
    project, warnings = await service.import_project(
        content=content,
        filename=file.filename or "project.xlsx",
        project_start_date=project_start_date,
    )
    return ImportResponse(project=project_to_out(project), warnings=warnings)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)
) -> ProjectOut:
    project = await service.get_project(project_id)
    return project_to_out(project)


@router.get("/{project_id}/export")
async def export_project(
    project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)
) -> Response:
    content, filename = await service.export_project(project_id)
    ascii_fallback = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "-_. ") else "_" for ch in filename) or "project.xlsx"
    encoded = quote(filename)
    disposition = f"attachment; filename*=UTF-8''{encoded}; filename=\"{ascii_fallback}\""
    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": disposition},
    )


async def _read_capped(file: UploadFile) -> bytes:
    """Read the upload in bounded chunks so an oversized file never lands
    fully in memory before we can reject it."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(
                f"Файл превышает лимит {MAX_FILE_SIZE_BYTES // (1024 * 1024)} МБ."
            )
        chunks.append(chunk)
    return b"".join(chunks)
