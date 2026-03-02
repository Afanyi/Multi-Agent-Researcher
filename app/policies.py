import re

CITATION_RE = re.compile(r"\[\d+\]")

def paragraphs(text: str) -> list[str]:
    chunks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return chunks


def enforce_no_cite_no_claim(report_md: str) -> tuple[bool, list[str]]:
    """
    Returns (ok, issues). Every non-heading paragraph must include at least one citation token [n].
    """
    issues: list[str] = []
    for i, p in enumerate(paragraphs(report_md), start=1):
        if p.startswith("#") or p.startswith("```"):
            continue
        if not CITATION_RE.search(p):
            issues.append(f"Paragraph {i} missing citation token like [1].")
    return (len(issues) == 0, issues)
