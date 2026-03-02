from dataclasses import dataclass
from typing import Optional
from app.utils import get_domain


@dataclass
class Plan:
    queries: list[str]
    subquestions: list[str]
    domain_allowlist: Optional[list[str]]


def planner(keywords: str, domain_allowlist: Optional[list[str]]) -> Plan:
    k = keywords.strip()
    queries = [
        k,
        f"{k} official documentation",
        f"{k} configuration",
    ]
    subq = [
        f"What do the docs say about: {k}?",
        "What are common causes and recommended fixes in official docs?",
    ]
    return Plan(queries=queries, subquestions=subq, domain_allowlist=domain_allowlist)


def score_candidate(url: str, title: str | None, allowlist: Optional[list[str]]) -> float:
    domain = get_domain(url) or ""
    score = 0.3
    if allowlist and any(domain.endswith(d) or domain == d for d in allowlist):
        score += 0.6
    t = (title or "").lower()
    if "docs" in t or "documentation" in t:
        score += 0.1
    return min(1.0, score)


def extract_evidence(text: str, keywords: str, max_snippets: int = 6) -> list[dict]:
    terms = [t.lower() for t in keywords.split() if len(t) >= 3]
    if not text:
        return []

    sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if len(s.strip()) > 40]
    scored: list[tuple[float, str]] = []
    for s in sentences:
        low = s.lower()
        hits = sum(1 for t in terms if t in low)
        if hits:
            scored.append((hits / max(1, len(terms)), s))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for sc, sent in scored[:max_snippets]:
        out.append(
            {"heading": None, "snippet": sent if sent.endswith(".") else sent + ".", "relevance_score": sc}
        )
    return out


def synthesize_report(keywords: str, sources: list[dict]) -> str:
    lines = []
    lines.append("# Research report\n")
    lines.append(f"**Keywords:** `{keywords}`\n")
    lines.append("## Summary\n")

    bullets = []
    cite = 1
    for s in sources:
        chunks = s.get("chunks", [])
        if not chunks:
            continue
        top = chunks[0]["snippet"]
        bullets.append(f"- {top} [{cite}]")
        cite += 1
        if len(bullets) >= 5:
            break

    if not bullets:
        lines.append("- No strong evidence snippets were extracted from retrieved pages. [1]\n")
    else:
        lines.extend(bullets)
        lines.append("")

    lines.append("## Steps / Recommendations (evidence-based)\n")
    cite = 1
    step_i = 1
    for s in sources:
        chunks = s.get("chunks", [])
        if not chunks:
            cite += 1
            continue
        lines.append(
            f"{step_i}. Review the relevant documentation section from the cited source and apply the documented configuration/steps. [{cite}]"
        )
        step_i += 1
        cite += 1
        if step_i > 6:
            break

    lines.append("\n## Sources\n")
    cite = 1
    for s in sources[:10]:
        lines.append(f"- [{cite}] {s.get('title') or s['url']} — {s['url']}")
        cite += 1

    return "\n".join(lines)


def verify_report(report_md: str) -> tuple[bool, list[str]]:
    issues = []
    if "## Sources" not in report_md:
        issues.append("Missing '## Sources' section.")
    if "[" not in report_md or "]" not in report_md:
        issues.append("No citation tokens detected.")

    from app.policies import enforce_no_cite_no_claim

    ok, more = enforce_no_cite_no_claim(report_md)
    issues.extend(more)
    return ok and not issues, issues
