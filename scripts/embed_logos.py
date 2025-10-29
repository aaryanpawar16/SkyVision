from __future__ import annotations
import os, io, sys, json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests
from PIL import Image

# --- project paths ---
ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
EXT  = ROOT / "data" / "external"
EMB_DIR = PROC / "embeddings"
EMB_DIR.mkdir(parents=True, exist_ok=True)

AIRLINES_PARQUET = PROC / "airlines.parquet"
LOGO_URLS_CSV    = EXT / "logo_urls.csv"
OUT_NPY          = EMB_DIR / "airlines_logo.npy"

# --- import shared embed function ---
sys.path.insert(0, str(ROOT))
try:
    from backend.app.embeddings import embed_image_bytes
except Exception as e:
    print(f"[err] Cannot import backend.app.embeddings: {e}")
    sys.exit(2)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}


def _fetch_image_bytes(url: str) -> Optional[bytes]:
    """Download image from URL."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def main():
    # Load airline data
    if not AIRLINES_PARQUET.exists():
        print(f"[err] Missing {AIRLINES_PARQUET}")
        sys.exit(2)

    airlines = pd.read_parquet(AIRLINES_PARQUET).reset_index(drop=True)

    # Load logo CSV
    if not LOGO_URLS_CSV.exists() or LOGO_URLS_CSV.stat().st_size == 0:
        print(f"[warn] No logo CSV at {LOGO_URLS_CSV}. All embeddings will be zeros.")
        logo_df = pd.DataFrame(columns=["entity_type", "id", "url"])
    else:
        logo_df = pd.read_csv(LOGO_URLS_CSV)

    # Keep only airline URLs
    logo_df = logo_df[(logo_df["entity_type"].str.lower() == "airline") & (logo_df["url"].astype(str).str.strip() != "")]
    logo_df = logo_df[["id", "url"]].copy()
    logo_df["id"] = logo_df["id"].astype(int)
    logo_df["url"] = logo_df["url"].astype(str)

    # Merge with airline table
    df = airlines.merge(logo_df, on="id", how="left")
    n = len(df)
    valid_count = (df["url"].astype(str).str.strip() != "").sum()
    print(f"[info] airlines: {n} rows, with logos: {valid_count}")

    # Prepare embedding container
    dim_env = int(os.getenv("EMBEDDING_DIM", "512"))
    dim: Optional[int] = None
    vecs: list[np.ndarray] = []
    ok, fail, skipped = 0, 0, 0

    for _, row in df.iterrows():
        url = str(row.get("url") or "").strip()
        if not url:
            vecs.append(np.zeros(dim or 1, dtype=np.float32))
            skipped += 1
            continue

        b = _fetch_image_bytes(url)
        if not b:
            vecs.append(np.zeros(dim or 1, dtype=np.float32))
            fail += 1
            continue

        try:
            Image.open(io.BytesIO(b)).convert("RGB")
            v = np.array(embed_image_bytes(b), dtype=np.float32).ravel()
            if dim is None:
                dim = v.size if v.size > 1 else dim_env
            if v.size != dim:
                z = np.zeros(dim, dtype=np.float32)
                z[: min(dim, v.size)] = v[: min(dim, v.size)]
                v = z
            vecs.append(v)
            ok += 1
        except Exception:
            vecs.append(np.zeros(dim or 1, dtype=np.float32))
            fail += 1

    # Finalize dimensions
    dim = dim or dim_env
    arr = np.vstack([v if v.size == dim else np.zeros(dim, dtype=np.float32) for v in vecs])
    np.save(OUT_NPY, arr)
    print(f"[done] wrote {OUT_NPY} shape={arr.shape} | ok={ok} fail={fail} skipped(no logo)={skipped}")


if __name__ == "__main__":
    main()
