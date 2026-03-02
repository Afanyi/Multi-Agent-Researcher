# Multi-Agent Researcher (Keywords → Evidence-Based Report)

A starter project for an AI Engineer portfolio: you provide **keywords**, the system searches online documentation,
extracts evidence snippets, and produces a **structured report with citations**. A trace endpoint shows what each
agent did (planner/scout/reader/synthesizer/verifier).

## Quick start (Docker)
1. Copy `.env.example` → `.env` and set `SERPER_API_KEY`
2. Start:
   ```bash
   docker compose up --build
   ```

## API
- Health: `GET http://localhost:8000/api/v1/health`
- Create research run:
  ```bash
  curl -X POST http://localhost:8000/api/v1/research \
    -H "Content-Type: application/json" \
    -d '{"keywords":"fastapi background tasks celery redis","depth":6}'
  ```
- Fetch run:
  - `GET http://localhost:8000/api/v1/research/{run_id}`
- Trace:
  - `GET http://localhost:8000/api/v1/research/{run_id}/trace`

## Key policy
- **No citation → no claim** (verifier enforces citation tokens like `[1]` in every paragraph).
