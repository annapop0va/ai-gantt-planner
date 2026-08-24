from __future__ import annotations

from fastapi.testclient import TestClient

from app.settings import Settings
from tests.conftest import FakeOpenRouterClient, SAMPLE_XLSX_PATH, build_test_settings


def _client(*, ai_configured: bool = True, enable_mcp: bool = True) -> TestClient:
    import app.main as main_module

    original_get_settings = main_module.get_settings

    def patched() -> Settings:
        return build_test_settings(
            enable_mcp=enable_mcp,
            enable_dev_endpoints=True,
            openrouter_api_key=("test-key" if ai_configured else None),
            openrouter_model=("test-model" if ai_configured else None),
        )

    main_module.get_settings = patched
    try:
        app = main_module.create_app()
    finally:
        main_module.get_settings = original_get_settings

    client = TestClient(app)
    client.__enter__()  # runs the real lifespan: MCP session manager + app.state wiring
    return client


def _inject_fake_agent(client: TestClient, fake: FakeOpenRouterClient) -> None:
    # AgentService has no test-injection constructor param in create_app() —
    # swapping its private `_client` after construction is the smallest way
    # to run the real HTTP/MCP stack against a scripted model, no network.
    client.app.state.agent_service._client = fake


def _import_sample(client: TestClient) -> dict:
    with SAMPLE_XLSX_PATH.open("rb") as fh:
        response = client.post(
            "/api/v1/projects/import",
            files={"file": (SAMPLE_XLSX_PATH.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"project_start_date": "2026-09-07"},
        )
    assert response.status_code == 201, response.text
    return response.json()["project"]


def test_chat_not_registered_when_mcp_disabled():
    client = _client(enable_mcp=False)
    paths = [route.path for route in client.app.routes]
    assert "/api/v1/projects/{project_id}/chat" not in paths


def test_chat_returns_503_when_ai_not_configured():
    client = _client(ai_configured=False)
    project = _import_sample(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/chat", json={"message": "test", "expected_revision": 1}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "AI_NOT_CONFIGURED"


def test_chat_stale_revision_returns_409():
    client = _client()
    project = _import_sample(client)
    fake = FakeOpenRouterClient([])
    _inject_fake_agent(client, fake)

    response = client.post(
        f"/api/v1/projects/{project['id']}/chat", json={"message": "test", "expected_revision": 99}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REVISION_CONFLICT"
    assert fake.calls == []


def test_chat_applied_returns_full_project_and_change_summary():
    client = _client()
    project = _import_sample(client)
    frontend = next(t for t in project["tasks"] if t["name"] == "Frontend-разработка карточки пациента")

    fake = FakeOpenRouterClient(
        [
            [
                {
                    "name": "apply_change_set",
                    "arguments": {
                        "operations": [
                            {
                                "op": "change_duration",
                                "task": {"task_id": frontend["id"]},
                                "mode": "add",
                                "unit": "workdays",
                                "value": 2,
                            }
                        ]
                    },
                }
            ],
            "Готово. Увеличил Frontend-разработку на 2 дня.",
        ]
    )
    _inject_fake_agent(client, fake)

    response = client.post(
        f"/api/v1/projects/{project['id']}/chat", json={"message": "Увеличь Frontend на 2 дня", "expected_revision": 1}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applied"
    assert body["project"]["revision"] == 2
    new_frontend = next(t for t in body["project"]["tasks"] if t["id"] == frontend["id"])
    assert new_frontend["duration_workdays"] == frontend["duration_workdays"] + 2
    assert body["change_summary"] is not None
    assert len(body["change_summary"]["direct_changes"]) == 1


def test_chat_clarification_required_leaves_project_and_status_shape():
    client = _client()
    project = _import_sample(client)
    fake = FakeOpenRouterClient(
        [
            [{"name": "search_tasks", "arguments": {"query": "разработка", "limit": 20}}],
            "Уточните, какую задачу вы имеете в виду.",
        ]
    )
    _inject_fake_agent(client, fake)

    response = client.post(
        f"/api/v1/projects/{project['id']}/chat", json={"message": "Перенеси разработку", "expected_revision": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "clarification_required"
    assert body["project"] is None

    reloaded = client.get(f"/api/v1/projects/{project['id']}")
    assert reloaded.json()["revision"] == 1


def test_chat_rejected_leaves_project_unchanged():
    client = _client()
    project = _import_sample(client)
    qa = next(t for t in project["tasks"] if t["name"] == "QA-тестирование карточки пациента")

    fake = FakeOpenRouterClient(
        [
            [
                {
                    "name": "apply_change_set",
                    "arguments": {
                        "operations": [
                            {"op": "move_task", "task": {"task_id": qa["id"]}, "target_start_date": "2026-09-08"}
                        ]
                    },
                }
            ],
            "Не удалось перенести: нарушает зависимости.",
        ]
    )
    _inject_fake_agent(client, fake)

    response = client.post(
        f"/api/v1/projects/{project['id']}/chat", json={"message": "Перенеси QA раньше", "expected_revision": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["project"] is None

    reloaded = client.get(f"/api/v1/projects/{project['id']}")
    assert reloaded.json()["revision"] == 1


def test_chat_message_too_long_is_rejected_by_validation():
    client = _client()
    project = _import_sample(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/chat",
        json={"message": "x" * 5000, "expected_revision": 1},
    )
    assert response.status_code == 422
