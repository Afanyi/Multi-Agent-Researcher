import hashlib
import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.config import settings


class SearchError(RuntimeError):
    pass


async def serper_search(query: str, num: int = 8) -> list[dict]:
    """
    Returns list of {url,title}
    """
    if not settings.serper_api_key:
        raise SearchError("SERPER_API_KEY not set")

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": num}

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    out = []
    for item in data.get("organic", [])[:num]:
        link = item.get("link")
        title = item.get("title")
        if link:
            out.append({"url": link, "title": title})
    return out


async def fetch_and_extract(url: str) -> dict:
    """
    Fetch URL and return {text, title, hash}.
    """
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        html = r.text

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None

    downloaded = trafilatura.extract(html, include_comments=False, include_tables=False)
    text = (downloaded or "").strip()
    h = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    return {"text": text, "title": title, "hash": h}
