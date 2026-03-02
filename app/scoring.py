def keyword_coverage(keywords: str, report_md: str) -> float:
    terms = [t.strip().lower() for t in keywords.split() if len(t.strip()) >= 3]
    if not terms:
        return 0.0
    hit = 0
    text = report_md.lower()
    for t in set(terms):
        if t in text:
            hit += 1
    return hit / max(1, len(set(terms)))


def confidence_from_evidence(num_sources: int, num_chunks: int, cite_ok: bool) -> float:
    base = 0.2
    base += min(0.5, 0.1 * num_sources)
    base += min(0.2, 0.02 * num_chunks)
    if cite_ok:
        base += 0.1
    return max(0.0, min(1.0, base))
