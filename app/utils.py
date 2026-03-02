from urllib.parse import urlparse


def get_domain(url: str) -> str | None:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def normalize_allowlist(domains: list[str] | None) -> list[str] | None:
    if not domains:
        return None
    out = []
    for d in domains:
        d = d.strip().lower()
        if d:
            out.append(d)
    return out or None
