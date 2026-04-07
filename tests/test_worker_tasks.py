from types import SimpleNamespace

import httpx
from sqlalchemy.exc import OperationalError

from worker.tasks import claim_run_for_execution, is_retryable_error, retry_delay_for
from worker.tools import SearchError


class FakeQuery:
    def __init__(self, run):
        self.run = run

    def filter(self, *_args, **_kwargs):
        return self

    def with_for_update(self):
        return self

    def one_or_none(self):
        return self.run


class FakeSession:
    def __init__(self, run):
        self.run = run
        self.commits = 0
        self.rollbacks = 0
        self.refreshes = 0

    def query(self, *_args, **_kwargs):
        return FakeQuery(self.run)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _run):
        self.refreshes += 1


def test_retry_delay_caps():
    assert retry_delay_for(0) == 5
    assert retry_delay_for(1) == 10
    assert retry_delay_for(2) == 20
    assert retry_delay_for(3) == 30
    assert retry_delay_for(4) == 30


def test_is_retryable_error_classification():
    request = httpx.Request("GET", "https://example.com")

    assert not is_retryable_error(SearchError("missing key"))
    assert is_retryable_error(OperationalError("SELECT 1", {}, Exception("db down")))
    assert is_retryable_error(httpx.RequestError("network", request=request))
    assert is_retryable_error(
        httpx.HTTPStatusError("rate limited", request=request, response=httpx.Response(429, request=request))
    )
    assert not is_retryable_error(
        httpx.HTTPStatusError("bad request", request=request, response=httpx.Response(400, request=request))
    )


def test_claim_run_for_execution_resets_failed_run(monkeypatch):
    run = SimpleNamespace(id="run-1", status="failed", error="old error")
    db = FakeSession(run)
    reset_calls = []

    def fake_reset_run_artifacts(_db, _run):
        reset_calls.append((_db, _run))

    monkeypatch.setattr("worker.tasks.reset_run_artifacts", fake_reset_run_artifacts)

    claimed_run, action = claim_run_for_execution(db, "run-1")

    assert claimed_run is run
    assert action == "claimed"
    assert run.status == "running"
    assert run.error is None
    assert db.commits == 1
    assert db.refreshes == 1
    assert reset_calls == [(db, run)]


def test_claim_run_for_execution_reclaims_retrying_run(monkeypatch):
    run = SimpleNamespace(id="run-1", status="retrying", error="transient")
    db = FakeSession(run)
    reset_calls = []

    def fake_reset_run_artifacts(_db, _run):
        reset_calls.append((_db, _run))

    monkeypatch.setattr("worker.tasks.reset_run_artifacts", fake_reset_run_artifacts)

    claimed_run, action = claim_run_for_execution(db, "run-1")

    assert claimed_run is run
    assert action == "claimed"
    assert run.status == "running"
    assert run.error is None
    assert reset_calls == [(db, run)]


def test_claim_run_for_execution_skips_running_run():
    run = SimpleNamespace(id="run-1", status="running", error=None)
    db = FakeSession(run)

    claimed_run, action = claim_run_for_execution(db, "run-1")

    assert claimed_run is run
    assert action == "skip_in_progress"
    assert db.rollbacks == 1
