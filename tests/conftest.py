from __future__ import annotations

import time
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest
import redis
from alembic import command
from alembic.config import Config
from celery.contrib.testing.worker import start_worker
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, wait_for_database
from app.main import app
from worker.celery_app import celery_app
import worker.tasks  # noqa: F401


TRUNCATE_ALL_TABLES_SQL = text(
    "TRUNCATE TABLE traces, reports, evidence_chunks, sources, research_runs RESTART IDENTITY CASCADE"
)


def _database_name() -> str:
    return urlparse(settings.database_url).path.rsplit("/", 1)[-1]


def _require_test_database() -> None:
    database_name = _database_name()
    if "test" not in database_name:
        pytest.skip(
            f"Full-stack tests require a dedicated test database, got '{database_name}'.",
            allow_module_level=True,
        )


def _make_alembic_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def _redis_client(url: str) -> redis.Redis | None:
    if not url.startswith("redis://"):
        return None
    return redis.Redis.from_url(url, decode_responses=True)


def _flush_redis_databases() -> None:
    for url in (settings.celery_broker_url, settings.celery_result_backend):
        client = _redis_client(url)
        if client is None:
            continue
        client.flushdb()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: exercises the real app stack with Postgres/Redis")


@pytest.fixture(scope="session")
def integration_environment() -> None:
    _require_test_database()
    try:
        wait_for_database(max_attempts=5, delay_seconds=0.2)
    except Exception as exc:  # pragma: no cover - only reached when infra is absent
        pytest.skip(f"Postgres is not available for integration tests: {exc}", allow_module_level=True)

    command.upgrade(_make_alembic_config(), "head")


@pytest.fixture
def db_session(integration_environment):
    db = SessionLocal()
    db.execute(TRUNCATE_ALL_TABLES_SQL)
    db.commit()
    try:
        yield db
    finally:
        db.execute(TRUNCATE_ALL_TABLES_SQL)
        db.commit()
        db.close()


@pytest.fixture
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def celery_worker_factory(integration_environment):
    broker_client = _redis_client(settings.celery_broker_url)
    result_client = _redis_client(settings.celery_result_backend)

    try:
        if broker_client is not None:
            broker_client.ping()
        if result_client is not None:
            result_client.ping()
    except redis.RedisError as exc:  # pragma: no cover - only reached when infra is absent
        pytest.skip(f"Redis is not available for full-stack worker tests: {exc}")

    @contextmanager
    def _start():
        _flush_redis_databases()
        with start_worker(
            celery_app,
            pool="solo",
            concurrency=1,
            queues=["default"],
            perform_ping_check=False,
            loglevel="INFO",
            shutdown_timeout=20.0,
        ):
            yield
        _flush_redis_databases()

    return _start


@pytest.fixture
def wait_for_run():
    def _wait(client: TestClient, run_id: str, *, timeout: float = 15.0, interval: float = 0.1) -> dict:
        deadline = time.monotonic() + timeout
        last_payload = None

        while time.monotonic() < deadline:
            response = client.get(f"/api/v1/research/{run_id}")
            assert response.status_code == 200
            last_payload = response.json()
            if last_payload["status"] in {"succeeded", "failed"}:
                return last_payload
            time.sleep(interval)

        pytest.fail(f"Timed out waiting for run {run_id} to finish. Last payload: {last_payload}")

    return _wait
