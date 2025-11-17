import os
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Page

APP_NAME = "Mezzofy SME Content Crawler"
BASE_DOMAIN = "https://www.mezzofy.com"
KEYWORDS = [
    "sme", "smb", "pricing", "features", "merchant", "e-commerce", "ecommerce",
    "pos", "coupon", "loyalty", "reward", "subscription", "payment", "api", "docs",
]

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CrawlRequest(BaseModel):
    start_url: Optional[str] = None
    max_pages: int = 20


def is_valid_mezzofy_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.netloc.endswith("mezzofy.com") and parsed.scheme in {"http", "https"}
    except Exception:
        return False


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None


def extract_info(url: str, soup: BeautifulSoup) -> Page:
    title = (soup.title.string.strip() if soup.title and soup.title.string else None)
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", None) if desc_tag else None
    og_img_tag = soup.find("meta", attrs={"property": "og:image"})
    image = og_img_tag.get("content", None) if og_img_tag else None

    # Create a basic snippet from the first paragraph
    snippet = None
    p = soup.find("p")
    if p and p.get_text():
        snippet = p.get_text().strip()[:240]

    text = soup.get_text(" ").lower()
    matched = sorted({kw for kw in KEYWORDS if kw in text})

    return Page(url=url, title=title, description=description, keywords_matched=list(matched), snippet=snippet, image=image)


@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME}


@app.post("/crawl")
async def crawl(req: CrawlRequest):
    start_url = req.start_url or BASE_DOMAIN
    if not is_valid_mezzofy_url(start_url):
        raise HTTPException(status_code=400, detail="start_url must be mezzofy.com")

    to_visit = [start_url]
    visited = set()
    saved = 0

    while to_visit and len(visited) < req.max_pages:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)

        soup = fetch_page(current)
        if not soup:
            continue

        # Save page if relevant
        page_model = extract_info(current, soup)
        if page_model.keywords_matched:
            try:
                create_document("page", page_model)
                saved += 1
            except Exception:
                # Database may not be configured; ignore but continue
                pass

        # Discover next links (same domain only)
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("#") or href.startswith("mailto:"):
                continue
            absolute = urljoin(current, href)
            if is_valid_mezzofy_url(absolute) and absolute not in visited and absolute not in to_visit:
                to_visit.append(absolute)

    return {"visited": len(visited), "saved": saved}


@app.get("/pages")
async def list_pages(q: Optional[str] = Query(None, description="Optional search query"), limit: int = 50):
    filter_dict = {}
    if q:
        # Simple regex OR search across relevant fields
        regex = {"$regex": q, "$options": "i"}
        filter_dict = {"$or": [
            {"title": regex},
            {"description": regex},
            {"snippet": regex},
            {"keywords_matched": regex},
        ]}

    try:
        docs = get_documents("page", filter_dict=filter_dict, limit=limit)
        # Convert ObjectId and datetime to strings
        def norm(d):
            d = dict(d)
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
            for k, v in list(d.items()):
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            return d
        return [norm(x) for x in docs]
    except Exception:
        # Fallback empty list if DB not configured
        return []


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
