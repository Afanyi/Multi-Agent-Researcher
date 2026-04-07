from __future__ import annotations

import time
from uuid import UUID

import httpx
import pytest

from app.config import settings
from app.models import EvidenceChunk, Report, ResearchRun, Source, Trace
from worker import tasks as worker_tasks
from worker.tools import SearchError


pytestmark = pytest.mark.integration


def install_successful_external_mocks(monkeypatch):
    async def fake_search(query: str, num: int = 8) -> list[dict]:
        return [
            {"url": "https://docs.example.com/guide", "title": "Official Guide"},
            {"url": "https://docs.example.com/guide", "title": "Official Guide Duplicate"},
            {"url": "https://kb.example.com/troubleshooting", "title": "Troubleshooting Documentation"},
        ][:num]

    async def fake_fetch(url: str) -> dict:
        if "guide" in url:
            text = (
                "FastAPI integrates with Celery for background task execution. "
                "Redis is a common broker choice for Celery workers. "
                "Configuration should include a dedicated queue and worker process."
            )
            return {"text": text, "title": "Official Guide", "hash": "hash-guide"}

        text = (
            "Troubleshooting should verify Redis connectivity and Celery worker health. "
            "Documentation recommends validating broker URLs and retry behavior. "
            "FastAPI services should expose health endpoints for the worker stack."
        )
        return {"text": text, "title": "Troubleshooting Documentation", "hash": "hash-kb"}

    monkeypatch.setattr(worker_tasks, "serper_search", fake_search)
    monkeypatch.setattr(worker_tasks, "fetch_and_extract", fake_fetch)


def create_research_run(client, *, keywords: str = "fastapi celery redis", depth: int = 2) -> str:
    response = client.post(
        "/api/v1/research",
        json={"keywords": keywords, "depth": depth, "domain_allowlist": ["example.com"]},
    )
    assert response.status_code == 200
    return response.json()["run_id"]


def test_pipeline_completes_end_to_end_via_api_worker_and_postgres(
    client,
    db_session,
    monkeypatch,
    celery_worker_factory,
    wait_for_run,
):
    install_successful_external_mocks(monkeypatch)
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    with celery_worker_factory():
        run_id = create_research_run(client)
        payload = wait_for_run(client, run_id)

    assert payload["status"] == "succeeded"
    assert payload["error"] is None
    assert len(payload["sources"]) == 2
    assert payload["report"] is not None
    assert payload["report"]["confidence"] > 0.0
    assert "## Sources" in payload["report"]["report_md"]

    run = db_session.get(ResearchRun, UUID(payload["run_id"]))
    assert run.status == "succeeded"
    assert db_session.query(Source).filter(Source.run_id == run.id).count() == 2
    assert db_session.query(EvidenceChunk).join(Source).filter(Source.run_id == run.id).count() > 0
    assert db_session.query(Report).filter(Report.run_id == run.id).count() == 1

    trace_response = client.get(f"/api/v1/research/{run_id}/trace")
    assert trace_response.status_code == 200
    trace_payload = trace_response.json()
    agents = {event["agent"] for event in trace_payload}
    assert {"planner", "scout", "reader", "synthesizer", "verifier"} <= agents


def test_pipeline_retry_endpoint_replaces_stale_artifacts_before_reprocessing(
    client,
    db_session,
    monkeypatch,
    celery_worker_factory,
    wait_for_run,
):
    install_successful_external_mocks(monkeypatch)
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    run = ResearchRun(keywords="fastapi celery redis", depth=2, status="failed", error="old error")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    stale_source = Source(
        run_id=run.id,
        url="https://stale.example.com/old",
        title="Stale Source",
        domain="stale.example.com",
        rank_score=0.1,
        status="failed",
        content_text="old text",
        content_hash="stale-hash",
    )
    db_session.add(stale_source)
    db_session.flush()
    db_session.add(EvidenceChunk(source_id=stale_source.id, heading=None, snippet="stale snippet", relevance_score=0.1))
    db_session.add(Report(run_id=run.id, report_md="# Old report\n\nStale text [1]\n\n## Sources\n- [1] stale", confidence=0.1, coverage=0.1))
    db_session.add(Trace(run_id=run.id, agent="pipeline", event_type="error", payload={"message": "stale trace"}))
    db_session.commit()

    with celery_worker_factory():
        retry_response = client.post(f"/api/v1/research/{run.id}/retry")
        assert retry_response.status_code == 200
        payload = wait_for_run(client, str(run.id))

    assert payload["status"] == "succeeded"
    assert all(source["url"] != "https://stale.example.com/old" for source in payload["sources"])
    assert "Old report" not in payload["report"]["report_md"]

    current_sources = db_session.query(Source).filter(Source.run_id == run.id).all()
    assert len(current_sources) == 2
    assert {source.url for source in current_sources} == {
        "https://docs.example.com/guide",
        "https://kb.example.com/troubleshooting",
    }
    current_traces = db_session.query(Trace).filter(Trace.run_id == run.id).all()
    assert len(current_traces) > 1
    assert all(trace.payload.get("message") != "stale trace" for trace in current_traces)


def test_pipeline_retries_transient_failures_and_surfaces_retrying_status(
    client,
    monkeypatch,
    celery_worker_factory,
    wait_for_run,
):
    request = httpx.Request("GET", "https://google.serper.dev/search")
    attempts = {"count": 0}

    async def flaky_search(query: str, num: int = 8) -> list[dict]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.RequestError("temporary network issue", request=request)
        return [
            {"url": "https://docs.example.com/guide", "title": "Official Guide"},
            {"url": "https://kb.example.com/troubleshooting", "title": "Troubleshooting Documentation"},
        ][:num]

    async def fake_fetch(url: str) -> dict:
        return {
            "text": (
                "FastAPI integrates with Celery for background jobs. "
                "Redis is a reliable broker for retried worker tasks. "
                "Operations teams should monitor retries and worker health."
            ),
            "title": "Integration Guide",
            "hash": f"hash-{url.rsplit('/', 1)[-1]}",
        }

    monkeypatch.setattr(worker_tasks, "serper_search", flaky_search)
    monkeypatch.setattr(worker_tasks, "fetch_and_extract", fake_fetch)
    monkeypatch.setattr(worker_tasks, "retry_delay_for", lambda _retry_number: 1)
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    seen_retrying = False

    with celery_worker_factory():
        run_id = create_research_run(client)

        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            response = client.get(f"/api/v1/research/{run_id}")
            assert response.status_code == 200
            payload = response.json()
            seen_retrying = seen_retrying or payload["status"] == "retrying"
            if payload["status"] == "succeeded":
                break
            time.sleep(0.1)
        else:
            pytest.fail(f"Run {run_id} did not complete after a transient retry.")

    assert seen_retrying
    assert attempts["count"] >= 2
    assert payload["status"] == "succeeded"
    assert payload["error"] is None


def test_pipeline_marks_verifier_failures_clearly_after_exhausting_attempts(
    client,
    db_session,
    monkeypatch,
    celery_worker_factory,
    wait_for_run,
):
    install_successful_external_mocks(monkeypatch)
    monkeypatch.setattr(worker_tasks, "verify_report", lambda _report_md: (False, ["insufficient evidence"]))
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    with celery_worker_factory():
        run_id = create_research_run(client)
        payload = wait_for_run(client, run_id)

    assert payload["status"] == "failed"
    assert payload["error"] == "Verifier failed after retries: insufficient evidence"

    run = db_session.get(ResearchRun, UUID(run_id))
    assert run.status == "failed"
    verifier_events = (
        db_session.query(Trace)
        .filter(Trace.run_id == run.id, Trace.agent == "verifier", Trace.event_type == "end")
        .all()
    )
    assert len(verifier_events) == 3


def test_pipeline_marks_non_retryable_search_errors_as_failed(
    client,
    db_session,
    monkeypatch,
    celery_worker_factory,
    wait_for_run,
):
    async def bad_search(query: str, num: int = 8) -> list[dict]:
        raise SearchError("search credentials are invalid")

    monkeypatch.setattr(worker_tasks, "serper_search", bad_search)
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    with celery_worker_factory():
        run_id = create_research_run(client)
        payload = wait_for_run(client, run_id)

    assert payload["status"] == "failed"
    assert payload["error"] == "search credentials are invalid"

    run = db_session.get(ResearchRun, UUID(run_id))
    assert run.status == "failed"
    assert db_session.query(Source).filter(Source.run_id == run.id).count() == 0
