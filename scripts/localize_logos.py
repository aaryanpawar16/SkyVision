# scripts/localize_logos.py
from __future__ import annotations
import argparse, hashlib, os, re, sys
from pathlib import Path
from typing import Tuple, Optional

import pandas as pd
import requests

# -------- Paths --------
ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
MEDIA = ROOT / "data" / "media"
CSV_IN = EXT / "logo_urls.csv"
CSV_OUT = EXT / "logo_urls_local.csv"

MEDIA.mkdir(parents=True, exist_ok=True)

# -------- HTTP --------
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "image/avif,image/webp,image/png,image/jpeg,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
}

# -------- Filename helpers --------
SAFE = re.compile(r"[^A-Za-z0-9_.-]+")
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

def safe_name(s: str) -> str:
    s = SAFE.sub("_", str(s)).strip("._")
    return s or "logo"

def ext_from_url(url: str) -> str:
    p = url.split("?", 1)[0]
    ext = os.path.splitext(p)[1].lower()
    return ext if ext in ALLOWED_EXTS else ""

def ext_from_content_type(ct: Optional[str]) -> str:
    if not ct:
        return ""
    ct = ct.split(";")[0].strip().lower()
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    return mapping.get(ct, "")

def decide_ext(url: str, ct: Optional[str]) -> str:
    return ext_from_url(url) or ext_from_content_type(ct) or ".png"

def download(url: str) -> Tuple[bytes, str]:
    with requests.get(url, headers=HEADERS, timeout=45, stream=True) as r:
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "") or ""
        data = b"".join(r.iter_content(chunk_size=1 << 15))
        return data, ct

def try_svg_to_png(svg_bytes: bytes) -> Optional[bytes]:
    # Optional: convert SVG → PNG if cairosvg is available
    try:
        import cairosvg  # type: ignore
        return cairosvg.svg2png(bytestring=svg_bytes)  # returns PNG bytes
    except Exception:
        return None

def main(overwrite: bool = False):
    if not CSV_IN.exists() or CSV_IN.stat().st_size == 0:
        print(f"[err] No CSV at {CSV_IN}. Expected columns include: entity_type,id,url")
        sys.exit(2)

    df = pd.read_csv(CSV_IN)
    need_cols = {"entity_type", "id", "url"}
    if not need_cols.issubset(df.columns):
        print(f"[err] CSV must include columns: {sorted(need_cols)}")
        sys.exit(2)

    out_rows = []
    ok = fail = kept = 0

    for _, r in df.iterrows():
        row = r.to_dict()
        etype = str(row.get("entity_type", "")).strip().lower()
        rid = int(row.get("id"))
        src = str(row.get("url") or "").strip()

        # pass through empty or already-local rows
        if not src:
            out_rows.append(row); fail += 1
            print(f"[skip] empty url id={rid}")
            continue
        if src.startswith("/media/"):
            out_rows.append(row); kept += 1
            print(f"[keep] local url {src}")
            continue

        # deterministic base name: airline_<id>_<hash>
        h = hashlib.sha1(src.encode("utf-8")).hexdigest()[:8]
        base = safe_name(f"{etype}_{rid}_{h}")

        try:
            data, ct = download(src)
            ext = decide_ext(src, ct)

            # If SVG, try to convert → PNG for better compatibility with embedding
            if ext == ".svg":
                png = try_svg_to_png(data)
                if png:
                    data = png
                    ext = ".png"  # store as PNG

            fname = f"{base}{ext}"
            fpath = MEDIA / fname

            if not fpath.exists() or overwrite:
                with open(fpath, "wb") as f:
                    f.write(data)
                print(f"[ok] {src} -> {fname} (ct={ct or 'unknown'})")
            else:
                print(f"[skip] exists: {fname}")

            row["url"] = f"/media/{fname}"
            out_rows.append(row)
            ok += 1

        except Exception as e:
            print(f"[warn] failed: {src} ({e})")
            out_rows.append(row)
            fail += 1

    out = pd.DataFrame(out_rows, columns=df.columns)
    out.to_csv(CSV_OUT, index=False)
    print(f"[done] wrote {CSV_OUT} (media dir: {MEDIA}) | ok={ok} kept={kept} fail={fail}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true", help="Re-download and overwrite existing files")
    args = ap.parse_args()
    main(overwrite=args.overwrite)
