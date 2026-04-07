# MVP TODO

This document lists the remaining work to complete the project as a simple, usable MVP.

## Current Baseline

Already implemented:

- FastAPI endpoints for creating and fetching research runs
- Celery worker pipeline with Postgres and Redis
- Search, fetch, extraction, report synthesis, and citation verification
- Docker Compose setup for local development
- CI/CD workflow scaffolding

The phases below are ordered. Finish them in sequence.

## Phase 1: Stabilize The Backend Core

Goal: make the current backend reliable enough to use repeatedly without manual fixes.

Tasks:

- [x] Add database migrations with Alembic instead of relying on auto-create at startup
- [x] Make model timestamps update correctly on changes
- [x] Improve worker error handling and retry behavior
- [x] Add validation for missing configuration and bad requests
- [x] Make research runs idempotent enough to retry safely
- [x] Clean up environment variable examples and deployment defaults

Completed in this phase:

- Alembic scaffolding and an initial schema migration are in the repository
- Docker Compose now runs a dedicated migration step before starting `api` and `worker`
- API startup no longer creates tables directly with `Base.metadata.create_all(...)`
- Request validation now trims keywords/domain allowlists and rejects blank keyword input
- Pipeline runs now clear stale errors, retry transient failures with backoff, and surface `retrying` status
- Retry requests can be requeued through the API without creating a new run record
- Worker execution now clears stale artifacts before reruns and skips duplicate in-progress jobs

Done when:

- A fresh environment can boot the stack and create tables through migrations
- Failed runs return clear error messages
- Retrying a run does not leave duplicate or inconsistent data

## Phase 2: Improve Retrieval And Evidence Quality

Goal: make the collected sources and snippets good enough to support trustworthy reports.

Tasks:

- Improve query generation beyond the current fixed heuristic
- Apply domain allowlists consistently in ranking and filtering
- Filter low-value pages such as empty, duplicate, or thin-content pages
- Rank sources using more than domain match and title keywords
- Extract cleaner evidence chunks with better sentence and section handling
- Store enough metadata to explain why a source was selected

Done when:

- Most runs return relevant sources for a focused topic
- The top evidence snippets are readable and directly related to the keywords
- Duplicate or low-quality sources are rare

## Phase 3: Improve Report Generation And Verification

Goal: produce a report that is useful to a human reader, not just technically cited.

Tasks:

- Replace the current basic bullet output with a consistent report template
- Tie claims more directly to evidence chunks, not only source numbers
- Fail gracefully when there is not enough evidence to support a conclusion
- Improve verifier checks for unsupported claims, weak evidence, and empty sections
- Clarify what confidence and coverage mean in the API response
- Add example outputs for expected report quality

Done when:

- Reports are readable, structured, and clearly supported by evidence
- Weak runs are marked as incomplete instead of pretending to be conclusive
- Citation checks catch obvious unsupported paragraphs

## Phase 4: Add A Minimal User Interface

Goal: make the MVP usable without manual API calls.

Tasks:

- Add a simple frontend or server-rendered UI
- Let users submit keywords, depth, and optional domain allowlist
- Show run status while the worker is processing
- Display the final report, sources, and trace output
- Show failure states and retry options

Done when:

- A user can complete one full research run from the browser
- The UI shows enough detail to inspect results without using curl

## Phase 5: Add Test Coverage For Real Flows

Goal: protect the MVP from regressions before calling it complete.

Tasks:

- [x] Add API tests for creating and retrieving runs
- [x] Add worker pipeline tests with mocked search/fetch services
- [x] Add integration tests for Postgres and Redis backed execution
- [x] Add test coverage for failure paths and verifier failures
- [x] Make CI run the full fast test suite reliably

Completed in this phase:

- The repository now includes Postgres-backed API integration tests and Redis-backed Celery worker tests
- The worker test suite covers successful runs, retry flows, verifier failures, and non-retryable search failures
- CI now applies Alembic migrations against a dedicated test database before running the full pytest suite

Done when:

- The main research flow is covered by automated tests
- CI catches regressions in the API, worker, and policy checks

## Phase 6: Production Hardening

Goal: make the MVP deployable and safe enough for limited real use.

Tasks:

- Add authentication or at least basic access protection
- Add request limits and background job safeguards
- Add logging, metrics, and basic monitoring
- Review deployment secrets, health checks, and restart behavior
- Document backup and recovery expectations for Postgres
- Fix production image/versioning details and deployment documentation

Done when:

- The system can run in production with basic operational visibility
- Abuse and accidental overload are limited
- Deployment and rollback steps are documented

## MVP Completion Criteria

The project can be considered complete as a simple MVP when:

- A user can submit a research topic from a UI
- The system returns a stored report with sources and trace data
- Failed runs are understandable and recoverable
- The main flow is covered by automated tests
- Local and production deployment are documented and repeatable

## Not Required For The First MVP

These can wait until after the MVP is complete:

- Multi-tenant accounts and organization support
- Advanced LLM planning or agent memory
- Vector search or embeddings infrastructure
- Billing, quotas, or usage analytics
- Complex frontend polish
