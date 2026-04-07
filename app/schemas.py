from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID


class ResearchCreate(BaseModel):
    keywords: str = Field(min_length=3)
    depth: int = Field(default=6, ge=1, le=20)
    domain_allowlist: Optional[list[str]] = None

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value):
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("keywords must contain at least 3 non-space characters")
        return normalized

    @field_validator("domain_allowlist", mode="before")
    @classmethod
    def normalize_domain_allowlist(cls, value):
        if value is None:
            return None
        if not isinstance(value, list):
            return value

        normalized = [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]
        return normalized or None


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
