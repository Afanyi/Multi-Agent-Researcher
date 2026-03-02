from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class ResearchCreate(BaseModel):
    keywords: str = Field(min_length=3)
    depth: int = Field(default=6, ge=1, le=20)
    domain_allowlist: Optional[list[str]] = None


class ResearchCreated(BaseModel):
    run_id: UUID
    status: str


class SourceOut(BaseModel):
    url: str
    title: str | None
    domain: str | None
    rank_score: float


class ReportOut(BaseModel):
    report_md: str
    confidence: float
    coverage: float


class ResearchOut(BaseModel):
    run_id: UUID
    keywords: str
    status: str
    depth: int
    domain_allowlist: Optional[list[str]] = None
    sources: list[SourceOut] = []
    report: ReportOut | None = None
    error: str | None = None


class TraceOut(BaseModel):
    agent: str
    event_type: str
    payload: dict
    created_at: str
