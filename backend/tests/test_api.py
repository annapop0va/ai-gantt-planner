from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SAMPLE_XLSX_PATH, build_test_settings


def _client(*, dev_endpoints: bool = True) -> TestClient:
    import app.main as main_module
    from app.settings import Settings

    original = main_module.get_settings

    def patched() -> Settings:
        return build_test_settings(enable_dev_endpoints=dev_endpoints)

    main_module.get_settings = patched  # type: ignore[assignment]
    try:
        app = create_app()
    finally:
        main_module.get_settings = original  # type: ignore[assignment]
    # TestClient must be entered as a context manager to run the app's
    # `lifespan` (that's what creates app.state.project_store).
    client = TestClient(app)
    client.__enter__()
    return client


def test_health_does_not_require_store():
    client = _client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dev_endpoint_registered_when_enabled():
    client = _client(dev_endpoints=True)
    paths = [route.path for route in client.app.routes]
    assert "/api/v1/projects/{project_id}/changes" in paths


def test_dev_endpoint_not_registered_when_disabled():
    client = _client(dev_endpoints=False)
    paths = [route.path for route in client.app.routes]
    assert "/api/v1/projects/{project_id}/changes" not in paths


def _import_sample(client: TestClient) -> dict:
    with SAMPLE_XLSX_PATH.open("rb") as fh:
        response = client.post(
            "/api/v1/projects/import",
            files={"file": (SAMPLE_XLSX_PATH.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"project_start_date": "2026-09-07"},
        )
    assert response.status_code == 201, response.text
    return response.json()


def test_import_canonical_sample():
    client = _client()
    body = _import_sample(client)
    project = body["project"]
    assert len(project["tasks"]) == 16
    assert project["revision"] == 1
    release = max(project["tasks"], key=lambda t: t["end_date"])
    assert release["end_date"] == "2026-11-02"
    # successor_ids is derived and present on every task.
    assert all("successor_ids" in t for t in project["tasks"])


def test_get_project_after_import():
    client = _client()
    project = _import_sample(client)["project"]
    response = client.get(f"/api/v1/projects/{project['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == project["id"]


def test_get_missing_project_returns_404_with_error_shape():
    client = _client()
    response = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "PROJECT_NOT_FOUND"
    assert "message" in body


def test_import_rejects_non_xlsx_extension():
    client = _client()
    response = client.post(
        "/api/v1/projects/import",
        files={"file": ("plan.csv", io.BytesIO(b"not excel"), "text/csv")},
        data={"project_start_date": "2026-09-07"},
    )
    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"


def test_import_rejects_oversized_file():
    client = _client()
    oversized = io.BytesIO(b"0" * (5 * 1024 * 1024 + 1))
    response = client.post(
        "/api/v1/projects/import",
        files={"file": ("plan.xlsx", oversized, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"project_start_date": "2026-09-07"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_canonical_change_set_via_dev_endpoint():
    client = _client(dev_endpoints=True)
    project = _import_sample(client)["project"]
    by_name = {t["name"]: t for t in project["tasks"]}

    agreement = by_name["Согласование требований к карточке пациента и расписанию врача"]
    frontend = by_name["Frontend-разработка карточки пациента"]
    dev_result = by_name["Согласование результата разработки"]
    qa = by_name["QA-тестирование карточки пациента"]

    operations = [
        {"op": "change_duration", "task": {"task_id": agreement["id"]}, "mode": "set", "unit": "workdays", "value": 5},
        {"op": "change_duration", "task": {"task_id": frontend["id"]}, "mode": "set", "unit": "workdays", "value": 8},
        {
            "op": "create_task",
            "client_ref": "backend_fix",
            "name": "Правки backend по итогам согласования",
            "assignee": "Василий",
            "duration_workdays": 2,
            "predecessor_refs": [{"task_id": dev_result["id"]}],
            "display_after_ref": {"task_id": dev_result["id"]},
        },
        {
            "op": "create_task",
            "client_ref": "frontend_fix",
            "name": "Правки frontend по итогам согласования",
            "assignee": "Дмитрий",
            "duration_workdays": 3,
            "predecessor_refs": [{"task_id": dev_result["id"]}],
            "display_after_ref": {"client_ref": "backend_fix"},
        },
        {
            "op": "set_predecessors",
            "task": {"task_id": qa["id"]},
            "predecessor_refs": [{"client_ref": "backend_fix"}, {"client_ref": "frontend_fix"}],
        },
    ]

    response = client.post(
        f"/api/v1/projects/{project['id']}/changes",
        json={"expected_revision": 1, "operations": operations},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applied"
    new_project = body["project"]
    assert len(new_project["tasks"]) == 18
    assert new_project["revision"] == 2
    release = max(new_project["tasks"], key=lambda t: t["end_date"])
    assert release["end_date"] == "2026-11-09"

    summary = body["change_summary"]
    assert len(summary["created_tasks"]) == 2
    assert summary["previous_revision"] == 1
    assert summary["new_revision"] == 2


def test_revision_conflict_returns_409():
    client = _client(dev_endpoints=True)
    project = _import_sample(client)["project"]
    task_id = project["tasks"][0]["id"]
    operations = [{"op": "change_duration", "task": {"task_id": task_id}, "mode": "set", "unit": "workdays", "value": 2}]

    response = client.post(
        f"/api/v1/projects/{project['id']}/changes",
        json={"expected_revision": 99, "operations": operations},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REVISION_CONFLICT"


def test_export_returns_xlsx_with_content_disposition():
    client = _client()
    project = _import_sample(client)["project"]
    response = client.get(f"/api/v1/projects/{project['id']}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers["content-disposition"]
    assert len(response.content) > 0
