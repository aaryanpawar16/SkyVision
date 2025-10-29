"""
Generate CLIP embeddings for airports (text and/or image) and airlines (logos).

Reads:
- data/processed/airports.parquet
- data/processed/airlines.parquet
- data/external/image_urls.csv

Writes:
- data/processed/embeddings/airports_txt.npy
- data/processed/embeddings/airports_img.npy
- data/processed/embeddings/airlines_logo.npy
"""
from __future__ import annotations
import argparse, os
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
from PIL import Image
import requests
from io import BytesIO
from pipeline.utils.clip_backend import get_model, ensure_dim
from pipeline.utils.io import ensure_dir

# --------- Text prompts ---------
def airport_text_prompt(row) -> str:
    parts = [str(row.get("name") or ""), str(row.get("city") or ""), str(row.get("country") or "")]
    base = ", ".join([p for p in parts if p and p.lower() != "nan"])
    return f"{base}. airport, architecture, travel, terminals, runways."

def airline_text_prompt(row) -> str:
    name = row.get("name") or ""
    country = row.get("country") or ""
    return f"{name} airline logo, brand identity, typography, colors, {country}"

def fetch_image(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        return img
    except Exception:
        return None

def main(args):
    out_dir = Path(args.out_dir)
    emb_dir = out_dir / "embeddings"
    ensure_dir(emb_dir)

    airports = pd.read_parquet(out_dir / "airports.parquet")
    airlines = pd.read_parquet(out_dir / "airlines.parquet")

    urls_path = Path(args.urls_csv)
    urls = pd.read_csv(urls_path) if urls_path.exists() else pd.DataFrame(columns=["entity_type","id","url","style","tags","license","attribution"])

    # Merge URLs
    ap_urls = urls[urls["entity_type"]=="airport"][["id","url","style","tags","license","attribution"]].rename(columns={"url":"image_url"})
    al_urls = urls[urls["entity_type"]=="airline"][["id","url","style","tags","license","attribution"]].rename(columns={"url":"logo_url"})

    airports = airports.merge(ap_urls, on="id", how="left")
    airlines = airlines.merge(al_urls, on="id", how="left")

    # Load model
    model = get_model(args.model_name)
    dim = ensure_dim(model, args.dim)

    # Airports text embeddings
    ap_prompts = [airport_text_prompt(r) for _, r in airports.iterrows()]
    ap_txt_vecs = model.encode(ap_prompts, normalize_embeddings=True, convert_to_numpy=True).astype("float32")
    assert ap_txt_vecs.shape[1] == dim
    np.save(emb_dir / "airports_txt.npy", ap_txt_vecs)

    # Airports image embeddings (optional, only if image_url)
    ap_img_vecs = np.zeros((len(airports), dim), dtype="float32")
    if args.with_images:
        for i, row in tqdm(list(airports.iterrows()), desc="airports_img"):
            url = row.get("image_url")
            if not isinstance(url, str) or not url:
                continue
            img = fetch_image(url)
            if img is None:
                continue
            vec = model.encode([img], normalize_embeddings=True, convert_to_numpy=True)[0].astype("float32")
            ap_img_vecs[i] = vec
    np.save(emb_dir / "airports_img.npy", ap_img_vecs)

    # Airlines logo embeddings (image preferred; fallback to text prompt)
    al_logo_vecs = np.zeros((len(airlines), dim), dtype="float32")
    for i, row in tqdm(list(airlines.iterrows()), desc="airlines_logo"):
        url = row.get("logo_url")
        vec: np.ndarray | None = None
        if isinstance(url, str) and url:
            img = fetch_image(url)
            if img is not None:
                vec = model.encode([img], normalize_embeddings=True, convert_to_numpy=True)[0].astype("float32")
        if vec is None:
            # fallback to text description
            vec = model.encode([airline_text_prompt(row)], normalize_embeddings=True, convert_to_numpy=True)[0].astype("float32")
        al_logo_vecs[i] = vec
    np.save(emb_dir / "airlines_logo.npy", al_logo_vecs)

    # Save merged datasets (with urls & styles for later load)
    airports.to_parquet(out_dir / "airports.parquet", index=False)
    airlines.to_parquet(out_dir / "airlines.parquet", index=False)

    print("Embeddings saved to", emb_dir)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out_dir", default="data/processed", help="Processed dir with parquet outputs")
    p.add_argument("--urls_csv", default="data/external/image_urls.csv")
    p.add_argument("--model_name", default="clip-ViT-B-32", help="Sentence-Transformers CLIP model")
    p.add_argument("--dim", type=int, default=512, help="Embedding dimension (must match DB schema)")
    p.add_argument("--with_images", action="store_true", help="Enable image embedding for airports if URLs exist")
    main(p.parse_args())
