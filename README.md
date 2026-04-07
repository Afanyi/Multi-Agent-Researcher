# Multi-Agent Researcher

`Multi-Agent Researcher` is a backend-first MVP that turns a keyword prompt into an evidence-backed markdown report with stored sources, extracted snippets, and an agent trace.

## Project Status

Status as of `2026-04-07`: the core API, worker pipeline, persistence layer, Docker setup, and CI/CD workflows are implemented. The project is usable as a development MVP, but it is still early-stage and relies on simple heuristics rather than an LLM-driven orchestration layer.

### Working now

- FastAPI API for creating and retrieving research runs
- Celery worker pipeline with `queued -> running -> succeeded/failed` run states
- Postgres persistence for runs, sources, evidence chunks, reports, and trace events
- Redis-backed task queue for asynchronous processing
- Serper-powered search plus page fetch/extraction with `httpx`, `BeautifulSoup`, and `trafilatura`
- Citation policy enforcement: non-heading paragraphs must include citation tokens like `[1]`
- Report scoring fields for keyword coverage and confidence
- Docker Compose setup for local development
- GitHub Actions workflows for CI (`ruff`, `pytest`) and CD (build/push/deploy)

### Still missing or intentionally basic

- No frontend or dashboard
- No authentication, rate limiting, or multi-tenant isolation
- No database migration workflow; tables are auto-created on API startup
- No end-to-end or integration tests in the repository yet
- Planner, ranking, evidence extraction, synthesis, and verification are heuristic implementations
- Search requires a valid `SERPER_API_KEY`; without it, research runs fail in the worker

## Architecture

- `api`: FastAPI app in [app/main.py](/home/blasius/Videos/multi-agent-researcher/app/main.py)
- `worker`: Celery task runner in [worker/tasks.py](/home/blasius/Videos/multi-agent-researcher/worker/tasks.py)
- `db`: SQLAlchemy models in [app/models.py](/home/blasius/Videos/multi-agent-researcher/app/models.py)
- `queue`: Redis for Celery broker and result backend
- `storage`: Postgres with Postgres-specific column types (`UUID`, `ARRAY`, `JSONB`)
- `search/fetch`: Serper API for discovery, then direct page extraction

## Research Flow

1. `POST /api/v1/research` creates a `research_runs` row with status `queued`.
2. The API enqueues `worker.tasks.run_pipeline`.
3. The worker generates search queries, calls Serper, ranks candidate URLs, fetches page content, and extracts evidence snippets.
4. Sources and evidence chunks are stored in Postgres.
5. A markdown report is synthesized and verified for citations.
6. The worker stores the report, confidence, coverage, and detailed trace entries.

## Quick Start

### Docker

1. Copy `.env.example` to `.env`.
2. Set `SERPER_API_KEY`.
3. Start the stack:

```bash
docker compose up --build
```

Services started by [docker-compose.yml](/home/blasius/Videos/multi-agent-researcher/docker-compose.yml):

- `api` on `http://localhost:8000`
- `worker`
- `postgres` on `localhost:5432`
- `redis` on `localhost:6379`

### Local Python environment

```bash
pip install -e .
pip install -e ".[dev]"
uvicorn app.main:app --reload
celery -A worker.celery_app:celery_app worker --loglevel=INFO
```

## Environment Variables

Required:

- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SERPER_API_KEY`

Optional:

- `DOMAIN_DEFAULT_ALLOWLIST`: comma-separated domains used when the request does not provide an explicit allowlist

See [`.env.example`](/home/blasius/Videos/multi-agent-researcher/.env.example) for the current template.

## API

- `GET /` returns service metadata
- `GET /api/v1/health` returns a health response
- `POST /api/v1/research` creates a research run
- `GET /api/v1/research/{run_id}` returns run status, ranked sources, and the stored report
- `GET /api/v1/research/{run_id}/trace` returns the agent trace

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "fastapi background tasks celery redis",
    "depth": 6,
    "domain_allowlist": ["fastapi.tiangolo.com", "docs.celeryq.dev"]
  }'
```

## Quality Checks

The repository includes:

- Unit tests for citation policy and scoring helpers in [tests/test_policies.py](/home/blasius/Videos/multi-agent-researcher/tests/test_policies.py) and [tests/test_scoring.py](/home/blasius/Videos/multi-agent-researcher/tests/test_scoring.py)
- A CI workflow in [.github/workflows/ci.yml](/home/blasius/Videos/multi-agent-researcher/.github/workflows/ci.yml) that installs dependencies, runs `ruff check .`, and runs `pytest -q`
- A CD workflow in [.github/workflows/cd.yml](/home/blasius/Videos/multi-agent-researcher/.github/workflows/cd.yml) that builds and pushes GHCR images and deploys with Docker Compose over SSH

Run checks locally after installing dev dependencies:

```bash
ruff check .
pytest -q
```

## Notes

- The API creates database tables automatically on startup via `Base.metadata.create_all(...)`.
- Because the models use Postgres-specific SQLAlchemy types, Postgres is the intended database for local and production use.
- The current report generator is deterministic and citation-oriented, but not semantically deep. Improving retrieval, summarization quality, and verifier behavior is the main next step.
