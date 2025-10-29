# backend/app/routers/media_proxy.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from urllib.parse import urlparse
import requests

router = APIRouter(prefix="", tags=["media-proxy"])

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

COMMONS_REF = "https://commons.wikimedia.org/"
ACCEPT_IMG = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"

ALLOWED_SCHEMES = {"http", "https"}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB guardrail

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": ACCEPT_IMG})

@router.get("/proxy")
def proxy(u: str = Query(..., description="Absolute image URL to fetch")) -> Response:
    try:
        pr = urlparse(u)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if pr.scheme.lower() not in ALLOWED_SCHEMES or not pr.netloc:
        raise HTTPException(status_code=400, detail="Only http/https absolute URLs are allowed")

    # Per-domain tweak (Wikimedia likes a Referer)
    headers = {}
    host = pr.netloc.lower()
    if "wikimedia.org" in host or "wikipedia.org" in host:
        headers["Referer"] = COMMONS_REF

    try:
        r = session.get(u, headers=headers, stream=True, timeout=30)
        r.raise_for_status()
    except requests.HTTPError as he:
        raise HTTPException(status_code=r.status_code, detail=f"Upstream error: {he}") from he
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")

    ctype = r.headers.get("Content-Type", "application/octet-stream")
    # Size guardrail (best effort with Content-Length; we still stream-check below)
    try:
        clen = int(r.headers.get("Content-Length", "0"))
        if clen and clen > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Image too large")
    except ValueError:
        pass

    def gen():
        total = 0
        for chunk in r.iter_content(1 << 15):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                r.close()
                break
            yield chunk

    resp = StreamingResponse(gen(), media_type=ctype)
    # Disable caching to avoid stale cards
    resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    # Allow images to be embedded cross-origin
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
