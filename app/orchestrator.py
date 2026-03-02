from sqlalchemy.orm import Session
from app.models import Trace, Report, Source, EvidenceChunk, ResearchRun
from app.policies import enforce_no_cite_no_claim
from app.scoring import keyword_coverage, confidence_from_evidence


def trace(db: Session, run_id, agent: str, event_type: str, payload: dict):
    db.add(Trace(run_id=run_id, agent=agent, event_type=event_type, payload=payload))
    db.commit()


def save_sources_and_chunks(db: Session, run: ResearchRun, sources_payload: list[dict]):
    # clear previous (if retry)
    db.query(EvidenceChunk).join(Source).filter(Source.run_id == run.id).delete(synchronize_session=False)
    db.query(Source).filter(Source.run_id == run.id).delete(synchronize_session=False)
    db.commit()

    for s in sources_payload:
        src = Source(
            run_id=run.id,
            url=s["url"],
            title=s.get("title"),
            domain=s.get("domain"),
            rank_score=float(s.get("rank_score", 0.0)),
            content_text=s.get("content_text"),
            content_hash=s.get("content_hash"),
            status=s.get("status", "fetched"),
        )
        db.add(src)
        db.flush()
        for c in s.get("chunks", []):
            db.add(
                EvidenceChunk(
                    source_id=src.id,
                    heading=c.get("heading"),
                    snippet=c["snippet"],
                    relevance_score=float(c.get("relevance_score", 0.0)),
                )
            )
    db.commit()


def upsert_report(db: Session, run: ResearchRun, report_md: str):
    cite_ok, _issues = enforce_no_cite_no_claim(report_md)
    num_sources = db.query(Source).filter(Source.run_id == run.id).count()
    num_chunks = db.query(EvidenceChunk).join(Source).filter(Source.run_id == run.id).count()
    coverage = keyword_coverage(run.keywords, report_md)
    confidence = confidence_from_evidence(num_sources, num_chunks, cite_ok)

    existing = db.query(Report).filter(Report.run_id == run.id).one_or_none()
    if existing:
        existing.report_md = report_md
        existing.coverage = coverage
        existing.confidence = confidence
    else:
        db.add(Report(run_id=run.id, report_md=report_md, coverage=coverage, confidence=confidence))
    db.commit()

    return cite_ok
