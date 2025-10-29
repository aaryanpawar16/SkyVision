from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
import httpx

# --- App ---
app = FastAPI(title="SkyVision API")

# --- CORS ---
_env_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
if not _env_origins or _env_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GZIP ---
app.add_middleware(GZipMiddleware, minimum_size=1024)

# --- Static /media with NO-CACHE headers ---
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        # Force fresh loads for media files
        resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

# --- Resolve media dir ---
DEFAULT_MEDIA_DIR = Path(__file__).resolve().parents[2] / "data" / "media"
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(DEFAULT_MEDIA_DIR))).resolve()
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", NoCacheStaticFiles(directory=str(MEDIA_DIR)), name="media")

# --- Routers ---
from .routers import search, health  # noqa: E402

app.include_router(health.router)
app.include_router(search.router)

# --- Root check ---
@app.get("/")
def root():
    return {
        "ok": True,
        "media_dir": str(MEDIA_DIR),
        "time": datetime.utcnow().isoformat() + "Z",
        "cors_allow_origins": allow_origins,
    }

# --- Media sanity check ---
@app.get("/media-check")
def media_check(filename: str = Query(..., description="e.g. airport_346_e56cb440.jpg")):
    """Check if a local media file exists."""
    p = MEDIA_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {p.name}")
    return {"ok": True, "path": str(p), "size": p.stat().st_size}


# --- Image Proxy (critical for external image URLs) ---
@app.get("/proxy")
async def proxy_image(u: str = Query(..., description="Absolute image URL")):
    """
    Fetch remote images safely (Wikimedia, Flickr, etc.)
    to avoid mixed content / CORS issues.
    Example:
      /proxy?u=https://upload.wikimedia.org/xyz.jpg
    """
    parsed = urlparse(u)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Invalid scheme")

    headers = {
        "User-Agent": "SkyVision/1.0 (+https://skyvision.local)",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": f"{parsed.scheme}://{parsed.netloc}/",
    }

    try:
        timeout = httpx.Timeout(15.0, read=15.0)
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.get(u, headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Proxy fetch failed: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Upstream returned {resp.status_code}")

    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type", "image/jpeg"),
        headers={
            "Cache-Control": "no-store, max-age=0, must-revalidate",
            "Referrer-Policy": "no-referrer",
        },
    )
