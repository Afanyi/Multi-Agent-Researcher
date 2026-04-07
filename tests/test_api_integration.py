from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from app import main as main_module
from app.config import settings
from app.models import ResearchRun, Trace


pytestmark = pytest.mark.integration


def test_create_research_persists_normalized_payload(client, db_session, monkeypatch):
    queued = []

    def fake_delay(run_id: str):
        queued.append(run_id)
        return SimpleNamespace(id="task-1")

    monkeypatch.setattr(main_module, "run_pipeline", SimpleNamespace(delay=fake_delay))
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    response = client.post(
        "/api/v1/research",
        json={
            "keywords": "  fastapi celery redis  ",
            "depth": 4,
            "domain_allowlist": [" Docs.CeleryQ.dev ", " ", "FASTAPI.TIANGOLO.COM"],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    run = db_session.get(ResearchRun, UUID(payload["run_id"]))
    assert run is not None
    assert queued == [payload["run_id"]]
    assert run.keywords == "fastapi celery redis"
    assert run.depth == 4
    assert run.domain_allowlist == ["docs.celeryq.dev", "fastapi.tiangolo.com"]
    assert payload["status"] == "queued"

    fetch_response = client.get(f"/api/v1/research/{payload['run_id']}")
    assert fetch_response.status_code == 200
    assert fetch_response.json() == {
        "run_id": payload["run_id"],
        "keywords": "fastapi celery redis",
        "status": "queued",
        "depth": 4,
        "domain_allowlist": ["docs.celeryq.dev", "fastapi.tiangolo.com"],
        "sources": [],
        "report": None,
        "error": None,
    }


def test_create_research_applies_default_allowlist(client, db_session, monkeypatch):
    queued = []

    def fake_delay(run_id: str):
        queued.append(run_id)
        return SimpleNamespace(id="task-1")

    monkeypatch.setattr(main_module, "run_pipeline", SimpleNamespace(delay=fake_delay))
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")
    monkeypatch.setattr(settings, "domain_default_allowlist", " Docs.Python.org , FASTAPI.TIANGOLO.COM , ")

    response = client.post(
        "/api/v1/research",
        json={"keywords": "python packaging", "depth": 3},
    )

    assert response.status_code == 200
    payload = response.json()

    run = db_session.get(ResearchRun, UUID(payload["run_id"]))
    assert queued == [payload["run_id"]]
    assert run.domain_allowlist == ["docs.python.org", "fastapi.tiangolo.com"]


def test_create_research_rejects_blank_keywords(client, monkeypatch):
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    response = client.post(
        "/api/v1/research",
        json={"keywords": "   ", "depth": 3},
    )

    assert response.status_code == 422
    assert "keywords" in response.text


def test_create_research_requires_serper_key(client, monkeypatch):
    monkeypatch.setattr(settings, "serper_api_key", None)

    response = client.post(
        "/api/v1/research",
        json={"keywords": "fastapi celery redis", "depth": 3},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "SERPER_API_KEY is not configured"}


def test_retry_research_requeues_same_run_without_creating_another(client, db_session, monkeypatch):
    queued = []

    def fake_delay(run_id: str):
        queued.append(run_id)
        return SimpleNamespace(id="task-1")

    run = ResearchRun(
        keywords="retry me",
        depth=2,
        status="failed",
        error="previous failure",
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    monkeypatch.setattr(main_module, "run_pipeline", SimpleNamespace(delay=fake_delay))
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    response = client.post(f"/api/v1/research/{run.id}/retry")

    assert response.status_code == 200
    assert response.json() == {"run_id": str(run.id), "status": "queued"}
    assert queued == [str(run.id)]

    db_session.expire_all()
    refreshed = db_session.get(ResearchRun, run.id)
    assert refreshed.status == "queued"
    assert refreshed.error is None
    assert db_session.query(ResearchRun).count() == 1


def test_retry_research_rejects_active_runs(client, db_session, monkeypatch):
    run = ResearchRun(
        keywords="still running",
        depth=2,
        status="running",
        error=None,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    response = client.post(f"/api/v1/research/{run.id}/retry")

    assert response.status_code == 409
    assert response.json() == {"detail": "run is already running"}


def test_get_trace_returns_events_in_created_order(client, db_session):
    run = ResearchRun(keywords="trace order", depth=2, status="queued")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    earlier = datetime.utcnow() - timedelta(minutes=1)
    later = datetime.utcnow()
    db_session.add_all(
        [
            Trace(
                run_id=run.id,
                agent="planner",
                event_type="start",
                payload={"step": 1},
                created_at=later,
            ),
            Trace(
                run_id=run.id,
                agent="planner",
                event_type="end",
                payload={"step": 2},
                created_at=earlier,
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/v1/research/{run.id}/trace")

    assert response.status_code == 200
    payload = response.json()
    assert [event["event_type"] for event in payload] == ["end", "start"]
    assert [event["payload"] for event in payload] == [{"step": 2}, {"step": 1}]
