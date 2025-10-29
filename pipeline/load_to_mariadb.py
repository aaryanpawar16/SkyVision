from __future__ import annotations
import argparse, os, json
from pathlib import Path
import numpy as np
import pandas as pd
import mariadb

# ---------------- DB ----------------
def connect(args):
    return mariadb.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,   # ✅ fixed: use args.db_name
        autocommit=True,
        connect_timeout=5,
    )

# ---------------- Utils ----------------
def _none_if_nan(x):
    """Convert pandas NaN or empty strings to None."""
    try:
        if isinstance(x, str):
            return x.strip() or None
        if pd.isna(x):
            return None
    except Exception:
        pass
    return x

def _vec_text(v: np.ndarray) -> str:
    """Convert NumPy vector to MariaDB VECTOR text format."""
    v = np.asarray(v, dtype="float32").ravel()
    v = np.where(np.isfinite(v), v, 0.0)
    return "[" + ",".join(str(float(x)) for x in v.tolist()) + "]"

def _normalize_url(url: str | None, base: str | None) -> str | None:
    """Make URLs absolute if base is provided."""
    u = (url or "").strip()
    if not u:
        return None
    if u.startswith(("http://", "https://")):
        return u
    if u.startswith("/") and base:
        return f"{base.rstrip('/')}{u}"
    return f"{base.rstrip('/')}/{u}" if base else u

def _drop_xy(df: pd.DataFrame) -> pd.DataFrame:
    """Drop lingering _x/_y columns from previous merges."""
    bad = [c for c in df.columns if c.endswith("_x") or c.endswith("_y")]
    return df.drop(columns=bad) if bad else df

def _merge_override(left: pd.DataFrame,
                    right: pd.DataFrame,
                    on: str,
                    cols: list[str]) -> pd.DataFrame:
    """
    Merge right into left on `on`, and for each column in `cols`,
    override left[col] with right[col] whenever right[col] is non-null/non-empty.
    """
    if right is None or right.empty:
        return left

    r = right[[on] + [c for c in cols if c in right.columns]].copy()
    # Use distinct suffix unlikely to collide
    merged = left.merge(r, on=on, how="left", suffixes=("", "__r"))

    for c in cols:
        rc = f"{c}__r"
        if rc in merged.columns:
            # Treat empty strings as nulls for override purposes
            right_val = merged[rc].replace("", pd.NA)
            merged[c] = right_val.combine_first(merged.get(c))
            merged.drop(columns=[rc], inplace=True)

    return merged

def _load_urls(urls_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load airports and airlines image/logo URLs safely."""
    empty_cols_ap = ["id", "image_url", "style", "tags", "license", "attribution"]
    empty_cols_al = ["id", "logo_url", "style", "tags", "license", "attribution"]

    if not urls_csv.exists() or urls_csv.stat().st_size == 0:
        return pd.DataFrame(columns=empty_cols_ap), pd.DataFrame(columns=empty_cols_al)

    df = pd.read_csv(urls_csv)
    if df.empty:
        return pd.DataFrame(columns=empty_cols_ap), pd.DataFrame(columns=empty_cols_al)

    df = df.dropna(subset=["entity_type", "id"]).copy()
    df["id"] = df["id"].astype(int)

    def ensure_cols(df, rename_map, base_cols):
        df = df.rename(columns=rename_map)
        for col in base_cols:
            if col not in df.columns:
                df[col] = None
        return df[base_cols]

    ap = df[df["entity_type"].str.lower() == "airport"].copy()
    ap = ensure_cols(ap, {"url": "image_url"}, empty_cols_ap)

    al = df[df["entity_type"].str.lower() == "airline"].copy()
    al = ensure_cols(al, {"url": "logo_url"}, empty_cols_al)

    return ap, al

def load_json_meta(style, tags, license, attribution):
    """Prepare metadata JSON for storage."""
    md: dict[str, object] = {}
    style = _none_if_nan(style)
    tags = _none_if_nan(tags)
    license = _none_if_nan(license)
    attribution = _none_if_nan(attribution)
    if style:
        md["style"] = style
    if isinstance(tags, str):
        md["tags"] = sorted(t.strip() for t in tags.split(",") if t.strip())
    if license:
        md["license"] = license
    if attribution:
        md["attribution"] = attribution
    return md

# ---------------- Upserts (batched) ----------------
def upsert_airports(conn, airports: pd.DataFrame, ap_vecs: np.ndarray, public_base_url: str | None):
    sql = """
    INSERT INTO airports
      (id, name, city, country, iata, icao, latitude, longitude, image_url, metadata, embedding)
    VALUES
      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, VEC_FromText(?))
    ON DUPLICATE KEY UPDATE
      name=VALUES(name),
      city=VALUES(city),
      country=VALUES(country),
      iata=VALUES(iata),
      icao=VALUES(icao),
      latitude=VALUES(latitude),
      longitude=VALUES(longitude),
      image_url=VALUES(image_url),
      metadata=VALUES(metadata),
      embedding=VALUES(embedding);
    """
    payload = []
    for pos, row in enumerate(airports.itertuples(index=False), 0):
        md = load_json_meta(getattr(row, "style", None),
                            getattr(row, "tags", None),
                            getattr(row, "license", None),
                            getattr(row, "attribution", None))
        e = ap_vecs[pos]
        img_url = _normalize_url(_none_if_nan(getattr(row, "image_url", None)), public_base_url)

        lat_val = getattr(row, "latitude", None)
        lon_val = getattr(row, "longitude", None)
        lat = float(lat_val) if lat_val is not None and pd.notna(lat_val) else None
        lon = float(lon_val) if lon_val is not None and pd.notna(lon_val) else None

        payload.append((
            int(getattr(row, "id")),
            _none_if_nan(getattr(row, "name", None)),
            _none_if_nan(getattr(row, "city", None)),
            _none_if_nan(getattr(row, "country", None)),
            _none_if_nan(getattr(row, "iata", None)),
            _none_if_nan(getattr(row, "icao", None)),
            lat, lon,
            img_url,
            json.dumps(md) if md else None,
            _vec_text(e),
        ))

    cur = conn.cursor()
    try:
        cur.executemany(sql, payload)
    finally:
        cur.close()

def upsert_airlines(conn, airlines: pd.DataFrame, al_vecs: np.ndarray, public_base_url: str | None):
    sql = """
    INSERT INTO airlines
      (id, name, alias, iata, icao, callsign, country, active, logo_url, metadata, embedding)
    VALUES
      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, VEC_FromText(?))
    ON DUPLICATE KEY UPDATE
      name=VALUES(name),
      alias=VALUES(alias),
      iata=VALUES(iata),
      icao=VALUES(icao),
      callsign=VALUES(callsign),
      country=VALUES(country),
      active=VALUES(active),
      logo_url=VALUES(logo_url),
      metadata=VALUES(metadata),
      embedding=VALUES(embedding);
    """
    payload = []
    for pos, row in enumerate(airlines.itertuples(index=False), 0):
        md = load_json_meta(getattr(row, "style", None),
                            getattr(row, "tags", None),
                            getattr(row, "license", None),
                            getattr(row, "attribution", None))
        e = al_vecs[pos]
        logo_url = _normalize_url(_none_if_nan(getattr(row, "logo_url", None)), public_base_url)
        payload.append((
            int(getattr(row, "id")),
            _none_if_nan(getattr(row, "name", None)),
            _none_if_nan(getattr(row, "alias", None)),
            _none_if_nan(getattr(row, "iata", None)),
            _none_if_nan(getattr(row, "icao", None)),
            _none_if_nan(getattr(row, "callsign", None)),
            _none_if_nan(getattr(row, "country", None)),
            _none_if_nan(getattr(row, "active", None)),
            logo_url,
            json.dumps(md) if md else None,
            _vec_text(e),
        ))

    cur = conn.cursor()
    try:
        cur.executemany(sql, payload)
    finally:
        cur.close()

# ---------------- Main ----------------
def main(args):
    processed = Path(args.processed_dir)
    airports = pd.read_parquet(processed / "airports.parquet")
    airlines = pd.read_parquet(processed / "airlines.parquet")

    airports = _drop_xy(airports)
    airlines = _drop_xy(airlines)

    # Load CSV with pinned URLs
    urls_csv = Path(args.urls_csv) if args.urls_csv else (processed.parents[1] / "data" / "external" / "image_urls.csv")
    ap_urls, al_urls = _load_urls(urls_csv)

    # Also allow extra logo CSVs (take latest)
    extra_logo_dfs = []
    for logo_csv in [
        processed.parents[1] / "data" / "external" / "logo_urls_local.csv",
        processed.parents[1] / "data" / "external" / "logo_urls.csv",
    ]:
        if logo_csv.exists() and logo_csv.stat().st_size > 0:
            df = pd.read_csv(logo_csv)
            if "entity_type" in df.columns:
                df = df[df["entity_type"].str.lower() == "airline"].copy()
            if df.empty:
                continue
            df["id"] = df["id"].astype(int)
            if "url" in df.columns:
                df = df.rename(columns={"url": "logo_url"})
            for col in ["style", "tags", "license", "attribution"]:
                if col not in df.columns:
                    df[col] = None
            df = df[["id", "logo_url", "style", "tags", "license", "attribution"]]
            extra_logo_dfs.append(df)
    if extra_logo_dfs:
        merged_logos = pd.concat(extra_logo_dfs, ignore_index=True).drop_duplicates(subset=["id"], keep="last")
        al_urls = pd.concat([al_urls, merged_logos], ignore_index=True).drop_duplicates(subset=["id"], keep="last")

    # 🔄 Override left with right where right has values
    airports = _merge_override(
        airports, ap_urls, on="id",
        cols=["image_url", "style", "tags", "license", "attribution"],
    )
    airlines = _merge_override(
        airlines, al_urls, on="id",
        cols=["logo_url", "style", "tags", "license", "attribution"],
    )

    print(f"[info] merge: airports with image_url: {(airports['image_url'].fillna('') != '').sum()} / {len(airports)}")
    print(f"[info] merge: airlines with logo_url : {(airlines['logo_url'].fillna('') != '').sum()} / {len(airlines)}")

    emb_dir = processed / "embeddings"
    ap_vecs = np.load(emb_dir / ("airports_img.npy" if args.prefer_image else "airports_txt.npy"))
    al_vecs = np.load(emb_dir / "airlines_logo.npy")

    airports = airports.reset_index(drop=True)
    airlines = airlines.reset_index(drop=True)

    if len(airports) != len(ap_vecs):
        raise ValueError(f"airports rows ({len(airports)}) != airports embeddings ({len(ap_vecs)})")
    if len(airlines) != len(al_vecs):
        raise ValueError(f"airlines rows ({len(airlines)}) != airlines embeddings ({len(al_vecs)})")

    print(f"[info] embeddings: airports shape={ap_vecs.shape}, airlines shape={al_vecs.shape}")

    conn = connect(args)
    try:
        conn.autocommit = False
        upsert_airports(conn, airports, ap_vecs, args.public_base_url)
        upsert_airlines(conn, airlines, al_vecs, args.public_base_url)
        conn.commit()
        print("✅ Load complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ---------------- Entry ----------------
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--processed_dir", default="data/processed")
    p.add_argument("--urls_csv", default=os.getenv("URLS_CSV", ""))
    p.add_argument("--public_base_url", default=os.getenv("PUBLIC_BASE_URL", ""))
    p.add_argument("--db_host", default=os.getenv("DB_HOST", "localhost"))
    p.add_argument("--db_port", type=int, default=int(os.getenv("DB_PORT", "3306")))
    p.add_argument("--db_user", default=os.getenv("DB_USER", "sky"))
    p.add_argument("--db_password", default=os.getenv("DB_PASSWORD", "vision"))
    p.add_argument("--db_name", default=os.getenv("DB_NAME", "skyvision"))
    p.add_argument("--prefer_image", action="store_true")
    args = p.parse_args()
    main(args)
