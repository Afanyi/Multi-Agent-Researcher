import asyncio
import httpx
from celery.exceptions import Retry
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from worker.celery_app import celery_app
from app.db import SessionLocal
from app.models import ResearchRun
from app.orchestrator import reset_run_artifacts, trace, save_sources_and_chunks, upsert_report
from worker.tools import serper_search, fetch_and_extract, SearchError
from worker.agents import planner, score_candidate, extract_evidence, synthesize_report, verify_report
from app.utils import get_domain


MAX_PIPELINE_RETRIES = 3


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        # Fallback: create a new loop for this task context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, SearchError):
        return False
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500
    return False


def retry_delay_for(retry_number: int) -> int:
    # 5s, 10s, 20s, then cap at 30s for any later retries.
    return min(30, 5 * (2**retry_number))


def claim_run_for_execution(db: Session, run_id: str) -> tuple[ResearchRun | None, str]:
    run = db.query(ResearchRun).filter(ResearchRun.id == run_id).with_for_update().one_or_none()
    if run is None:
        return None, "missing"

    if run.status == "succeeded":
        db.rollback()
        return run, "skip_succeeded"

    if run.status == "running":
        db.rollback()
        return run, "skip_in_progress"

    reset_run_artifacts(db, run)
    run.status = "running"
    run.error = None
    db.commit()
    db.refresh(run)
    return run, "claimed"


@celery_app.task(name="worker.tasks.run_pipeline", bind=True, max_retries=MAX_PIPELINE_RETRIES)
def run_pipeline(self, run_id: str):
    db: Session = SessionLocal()
    try:
        run, action = claim_run_for_execution(db, run_id)
        if action == "missing":
            return

        if action == "skip_succeeded":
            trace(db, run.id, "pipeline", "info", {"message": "Skipping already-succeeded run."})
            return

        if action == "skip_in_progress":
            trace(db, run.id, "pipeline", "info", {"message": f"Skipping run with status '{run.status}'."})
            return

        trace(db, run.id, "planner", "start", {"keywords": run.keywords})
        plan = planner(run.keywords, run.domain_allowlist)
        trace(db, run.id, "planner", "end", {"queries": plan.queries, "allowlist": plan.domain_allowlist})

        attempts = 0
        last_issues = []
        while attempts < 3:
            attempts += 1

            trace(db, run.id, "scout", "start", {"attempt": attempts})
            candidates = []
            for q in plan.queries[:2]:
                try:
                    res = run_async(serper_search(q, num=max(6, run.depth)))
                    candidates.extend(res)
                except SearchError as e:
                    trace(db, run.id, "scout", "error", {"error": str(e)})
                    raise

            seen = set()
            deduped = []
            for c in candidates:
                u = c["url"]
                if u in seen:
                    continue
                seen.add(u)
                deduped.append(c)

            scored = []
            for c in deduped:
                d = get_domain(c["url"])
                s = score_candidate(c["url"], c.get("title"), plan.domain_allowlist)
                scored.append({**c, "domain": d, "rank_score": s})

            scored.sort(key=lambda x: x["rank_score"], reverse=True)
            picked = scored[: run.depth]
            trace(db, run.id, "scout", "end", {"picked": picked})

            trace(db, run.id, "reader", "start", {"n": len(picked)})
            sources_payload = []
            for p in picked:
                url = p["url"]
                try:
                    fx = run_async(fetch_and_extract(url))
                    text = fx["text"]
                    chunks = extract_evidence(text, run.keywords, max_snippets=6)
                    sources_payload.append(
                        {
                            "url": url,
                            "title": fx["title"] or p.get("title"),
                            "domain": p.get("domain"),
                            "rank_score": p.get("rank_score", 0.0),
                            "content_text": text[:150_000],
                            "content_hash": fx.get("hash"),
                            "status": "fetched" if text else "failed",
                            "chunks": chunks,
                        }
                    )
                except Exception as e:
                    sources_payload.append(
                        {
                            "url": url,
                            "title": p.get("title"),
                            "domain": p.get("domain"),
                            "rank_score": p.get("rank_score", 0.0),
                            "content_text": None,
                            "content_hash": None,
                            "status": "failed",
                            "chunks": [],
                        }
                    )
                    trace(db, run.id, "reader", "warning", {"url": url, "error": str(e)})

            trace(db, run.id, "reader", "end", {"sources": len(sources_payload)})

            save_sources_and_chunks(db, run, sources_payload)

            trace(db, run.id, "synthesizer", "start", {"attempt": attempts})
            report_md = synthesize_report(run.keywords, sources_payload)
            trace(db, run.id, "synthesizer", "end", {"chars": len(report_md)})

            trace(db, run.id, "verifier", "start", {"attempt": attempts})
            ok, issues = verify_report(report_md)
            trace(db, run.id, "verifier", "end", {"ok": ok, "issues": issues})
            last_issues = issues

            cite_ok = upsert_report(db, run, report_md)

            if ok and cite_ok:
                run.status = "succeeded"
                run.error = None
                db.commit()
                return

        run.status = "failed"
        run.error = "Verifier failed after retries: " + "; ".join(last_issues[:10])
        db.commit()

    except Retry:
        raise
    except Exception as e:
        try:
            run = db.query(ResearchRun).filter(ResearchRun.id == run_id).one_or_none()
            if run:
                trace(db, run.id, "pipeline", "error", {"error": str(e)})
                if is_retryable_error(e) and self.request.retries < self.max_retries:
                    delay = retry_delay_for(self.request.retries)
                    run.status = "retrying"
                    run.error = f"Transient error. Retrying in {delay}s: {e}"
                    db.commit()
                    trace(
                        db,
                        run.id,
                        "pipeline",
                        "warning",
                        {
                            "message": "Transient error. Scheduling retry.",
                            "retry_in_seconds": delay,
                            "current_retry": self.request.retries + 1,
                        },
                    )
                    raise self.retry(exc=e, countdown=delay)

                run.status = "failed"
                run.error = str(e)
                db.commit()
        except Retry:
            raise
        except Exception:
            pass
        raise
    finally:
        db.close()
