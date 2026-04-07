from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.db import get_db, wait_for_database
from app.models import ResearchRun, Source, Report, Trace
from app.schemas import ResearchCreate, ResearchCreated, ResearchOut, SourceOut, ReportOut, TraceOut
from app.utils import normalize_allowlist
from app.config import settings
from worker.tasks import run_pipeline  # Celery task


app = FastAPI(title="Multi-Agent Researcher", version="0.1.0")


@app.on_event("startup")
def startup():
    # Database schema is applied through Alembic migrations; startup only waits for connectivity.
    wait_for_database()

@app.get("/")
def root():
    return {"name": "Multi-Agent Researcher", "docs": "/docs", "health": "/api/v1/health"}

@app.get("/api/v1/health")
def health():
    return {"ok": True}


@app.post("/api/v1/research", response_model=ResearchCreated)
def create_research(payload: ResearchCreate, db: Session = Depends(get_db)):
    if not settings.serper_api_key:
        raise HTTPException(status_code=503, detail="SERPER_API_KEY is not configured")

    allowlist = payload.domain_allowlist
    if allowlist is None and settings.domain_default_allowlist:
        allowlist = normalize_allowlist(settings.domain_default_allowlist.split(","))

    run = ResearchRun(
        keywords=payload.keywords,
        depth=payload.depth,
        domain_allowlist=allowlist,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run_pipeline.delay(str(run.id))
    return ResearchCreated(run_id=run.id, status=run.status)


@app.post("/api/v1/research/{run_id}/retry", response_model=ResearchCreated)
def retry_research(run_id: UUID, db: Session = Depends(get_db)):
    if not settings.serper_api_key:
        raise HTTPException(status_code=503, detail="SERPER_API_KEY is not configured")

    run = db.query(ResearchRun).filter(ResearchRun.id == run_id).one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    if run.status in {"queued", "running", "retrying"}:
        raise HTTPException(status_code=409, detail=f"run is already {run.status}")

    run.status = "queued"
    run.error = None
    db.commit()
    db.refresh(run)

    run_pipeline.delay(str(run.id))
    return ResearchCreated(run_id=run.id, status=run.status)


@app.get("/api/v1/research/{run_id}", response_model=ResearchOut)
def get_research(run_id: UUID, db: Session = Depends(get_db)):
    run = db.query(ResearchRun).filter(ResearchRun.id == run_id).one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    sources = (
        db.query(Source)
        .filter(Source.run_id == run.id)
        .order_by(Source.rank_score.desc())
        .all()
    )
    report = db.query(Report).filter(Report.run_id == run.id).one_or_none()

    return ResearchOut(
        run_id=run.id,
        keywords=run.keywords,
        status=run.status,
        depth=run.depth,
        domain_allowlist=run.domain_allowlist,
        error=run.error,
        sources=[SourceOut(url=s.url, title=s.title, domain=s.domain, rank_score=s.rank_score) for s in sources],
        report=ReportOut(report_md=report.report_md, confidence=report.confidence, coverage=report.coverage) if report else None,
    )


@app.get("/api/v1/research/{run_id}/trace", response_model=list[TraceOut])
def get_trace(run_id: UUID, db: Session = Depends(get_db)):
    rows = (
        db.query(Trace)
        .filter(Trace.run_id == run_id)
        .order_by(Trace.created_at.asc())
        .all()
    )
    return [
        TraceOut(
            agent=r.agent,
            event_type=r.event_type,
            payload=r.payload,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
