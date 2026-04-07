import pytest
from pydantic import ValidationError

from app.schemas import ResearchCreate


def test_research_create_normalizes_keywords_and_domains():
    payload = ResearchCreate(
        keywords="  fastapi celery  ",
        domain_allowlist=[" Docs.CeleryQ.dev ", " ", "FASTAPI.TIANGOLO.COM"],
    )

    assert payload.keywords == "fastapi celery"
    assert payload.domain_allowlist == ["docs.celeryq.dev", "fastapi.tiangolo.com"]


def test_research_create_rejects_blank_keywords():
    with pytest.raises(ValidationError):
        ResearchCreate(keywords="   ")
