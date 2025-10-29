# scripts/localize_images.py
from __future__ import annotations
import argparse, hashlib, os, re, sys, time
from pathlib import Path
from typing import Tuple, Optional
import pandas as pd
import requests

VERSION = "localize_images.py v2.1 (no-rewrite, robust-csv)"

ROOT = Path(__file__).resolve().parents[1]
CSV_IN  = ROOT / "data" / "external" / "image_urls.csv"
CSV_OUT = ROOT / "data" / "external" / "image_urls_local.csv"
MEDIA   = ROOT / "data" / "media"

SAFE = re.compile(r"[^A-Za-z0-9_.-]+")
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
WIKI_HEADERS = {"Referer": "https://commons.wikimedia.org/"}

def safe_name(s: str) -> str:
    s = SAFE.sub("_", s).strip("._")
    return s or "img"

def ext_from_url(url: str) -> str:
    p = url.split("?", 1)[0]
    ext = os.path.splitext(p)[1].lower()
    return ext if ext in ALLOWED_EXTS else ""

def ext_from_content_type(ct: Optional[str]) -> str:
    if not ct:
        return ""
    ct = ct.split(";", 1)[0].strip().lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg":  ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
        "image/gif":  ".gif",
    }
    return mapping.get(ct, "")

def decide_ext(url: str, ct: Optional[str]) -> str:
    return ext_from_url(url) or ext_from_content_type(ct) or ".jpg"

def is_image_content_type(ct: Optional[str]) -> bool:
    return bool(ct) and ct.split(";", 1)[0].strip().lower() in ALLOWED_MIME

def download(url: str, timeout: int = 60, retries: int = 3, backoff: float = 1.3) -> Tuple[bytes, str]:
    headers = dict(BASE_HEADERS)
    if "upload.wikimedia.org" in url:
        headers.update(WIKI_HEADERS)

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=headers, timeout=timeout, stream=True) as r:
                r.raise_for_status()
                ct = r.headers.get("Content-Type", "") or ""
                if not is_image_content_type(ct):
                    # Peek a few bytes to allow missing/incorrect content-type
                    peek = r.raw.read(16, decode_content=True) or b""
                    sig = peek[:8]
                    if sig.startswith(b"\xff\xd8") or sig.startswith(b"\x89PNG") or sig.startswith(b"RIFF") or sig.startswith(b"GIF"):
                        content = peek + r.content
                        return content, ct or "image/unknown"
                    raise ValueError(f"Non-image content-type: {ct or 'unknown'}")
                chunks = []
                for chunk in r.iter_content(chunk_size=32768):
                    if chunk:
                        chunks.append(chunk)
                return b"".join(chunks), ct
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(backoff ** (attempt - 1))
            else:
                raise
    assert last_exc
    raise last_exc  # pragma: no cover

def main(overwrite: bool = False):
    print(VERSION)
    MEDIA.mkdir(parents=True, exist_ok=True)

    if not CSV_IN.exists():
        print(f"[err] Missing {CSV_IN}. Expected columns at minimum: entity_type,id,url")
        sys.exit(2)

    # Robust CSV read (handles quoted commas etc.)
    df = pd.read_csv(CSV_IN, dtype=str, engine="python", quoting=0, keep_default_na=False)
    df.columns = [c.strip().lower() for c in df.columns]

    need_cols = {"entity_type", "id", "url"}
    if not need_cols.issubset(df.columns):
        print(f"[err] CSV missing required columns: {sorted(need_cols)}")
        print(f"[hint] Found columns: {list(df.columns)}")
        sys.exit(2)

    # Clean
    df = df.replace({"": None})
    df = df.dropna(subset=["entity_type", "id", "url"]).copy()
    df["entity_type"] = df["entity_type"].str.strip().str.lower()
    df = df[df["entity_type"].isin(["airport", "airline"])].copy()

    # Coerce id to int
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df = df.dropna(subset=["id"])
    df["id"] = df["id"].astype(int)

    out_rows = []
    ok = fail = kept = skipped = 0

    for _, row in df.iterrows():
        et = row["entity_type"]
        rid = int(row["id"])
        url = (row["url"] or "").strip()

        if not url:
            skipped += 1
            out_rows.append(row.to_dict())
            print(f"[skip] empty url id={rid}")
            continue

        if url.startswith("/media/"):
            kept += 1
            out_rows.append(row.to_dict())
            print(f"[keep] local url {url}")
            continue

        # Deterministic filename based on URL
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        base = safe_name(f"{et}_{rid}_{h}")

        try:
            content, ct = download(url)
            ext = decide_ext(url, ct)
            fname = f"{base}{ext}"
            fpath = MEDIA / fname

            if fpath.exists() and not overwrite:
                print(f"[skip] exists: {fname}")
            else:
                with open(fpath, "wb") as f:
                    f.write(content)
                print(f"[ok] {url} -> {fname} (ct={ct or 'unknown'})")

            # rewrite to /media
            row = row.copy()
            row["url"] = f"/media/{fname}"
            out_rows.append(row.to_dict())
            ok += 1

        except Exception as e:
            fail += 1
            out_rows.append(row.to_dict())
            print(f"[warn] failed: {url} ({e})")

    out = pd.DataFrame(out_rows, columns=df.columns)
    out.to_csv(CSV_OUT, index=False)
    print(f"\n[done] wrote {CSV_OUT}")
    print(f"Results: ok={ok}, kept={kept}, skipped={skipped}, failed={fail}")
    print(f"Serve directory: {MEDIA}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true", help="Re-download even if file exists")
    args = ap.parse_args()
    main(overwrite=args.overwrite)
