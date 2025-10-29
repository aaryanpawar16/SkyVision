"""
Load OpenFlights data into normalized Parquet files used by later steps.

Supports either:
- data/raw/openflights/airports.dat  (canonical OpenFlights, no headers)
- data/raw/openflights/airlines.dat  (canonical OpenFlights, no headers)
or:
- data/raw/openflights/airports.csv  (any headers; mapped below)
- data/raw/openflights/airlines.csv  (any headers; mapped below)

Outputs:
- data/processed/airports.parquet
- data/processed/airlines.parquet
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

# --- Expected columns for the canonical .dat files (no headers) ---
AIRPORT_DAT_COLS = [
    "id","name","city","country","iata","icao","latitude","longitude",
    "altitude","timezone","dst","tz","type","source"
]

AIRLINE_DAT_COLS = [
    "id","name","alias","iata","icao","callsign","country","active"
]

# --- Flexible header mapping for CSV inputs (if you use CSVs instead of .dat) ---
AIRPORT_COLMAP = {
    "Airport ID": "id",
    "Name": "name",
    "City": "city",
    "Country": "country",
    "IATA": "iata",
    "ICAO": "icao",
    "Latitude": "latitude",
    "Longitude": "longitude",
    # lowercase variants
    "airport id": "id",
    "name": "name",
    "city": "city",
    "country": "country",
    "iata": "iata",
    "icao": "icao",
    "latitude": "latitude",
    "longitude": "longitude",
}

AIRLINE_COLMAP = {
    "Airline ID": "id",
    "Name": "name",
    "Alias": "alias",
    "IATA": "iata",
    "ICAO": "icao",
    "Callsign": "callsign",
    "Country": "country",
    "Active": "active",
    # lowercase
    "airline id": "id",
    "name": "name",
    "alias": "alias",
    "iata": "iata",
    "icao": "icao",
    "callsign": "callsign",
    "country": "country",
    "active": "active",
}


def _load_openflights_file(path: Path, kind: str) -> pd.DataFrame:
    """
    Load a single OpenFlights file (.dat or .csv) and return a DataFrame
    with canonical column names for the given kind ('airport' or 'airline').
    """
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    suffix = path.suffix.lower()
    if kind == "airport":
        if suffix == ".dat":
            df = pd.read_csv(
                path, header=None, names=AIRPORT_DAT_COLS,
                na_values="\\N", keep_default_na=True
            )
            # Keep only the subset we need downstream
            keep = ["id","name","city","country","iata","icao","latitude","longitude"]
            df = df[keep].copy()
        else:
            # CSV with headers → map to our canonical names
            df = pd.read_csv(path)
            rename = {c: AIRPORT_COLMAP[c] for c in df.columns if c in AIRPORT_COLMAP}
            df = df.rename(columns=rename)
            keep = ["id","name","city","country","iata","icao","latitude","longitude"]
            df = df[[c for c in keep if c in df.columns]].copy()
    elif kind == "airline":
        if suffix == ".dat":
            df = pd.read_csv(
                path, header=None, names=AIRLINE_DAT_COLS,
                na_values="\\N", keep_default_na=True
            )
            keep = ["id","name","alias","iata","icao","callsign","country","active"]
            df = df[keep].copy()
        else:
            df = pd.read_csv(path)
            rename = {c: AIRLINE_COLMAP[c] for c in df.columns if c in AIRLINE_COLMAP}
            df = df.rename(columns=rename)
            keep = ["id","name","alias","iata","icao","callsign","country","active"]
            df = df[[c for c in keep if c in df.columns]].copy()
    else:
        raise ValueError("kind must be 'airport' or 'airline'")

    # Deduplicate by id
    if "id" in df.columns:
        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["id"]).copy()
        df["id"] = df["id"].astype(int)

    # Numeric coercions
    for col in ("latitude", "longitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # String cleanups
    for col in ("iata","icao","country","city","name","alias","callsign","active"):
        if col in df.columns:
            # ensure None instead of "nan"
            df[col] = df[col].astype(object).where(pd.notna(df[col]), None)

    return df


def _resolve_input_files(raw_dir: Path) -> tuple[Path, Path]:
    """
    Return (airports_path, airlines_path) by preferring .dat if present, else .csv.
    """
    candidates = {
        "airports": [raw_dir/"airports.dat", raw_dir/"airports.csv"],
        "airlines": [raw_dir/"airlines.dat", raw_dir/"airlines.csv"],
    }
    chosen = []
    for key in ("airports", "airlines"):
        for p in candidates[key]:
            if p.exists():
                chosen.append(p)
                break
        else:
            raise FileNotFoundError(
                f"Could not find {key}.dat or {key}.csv in {raw_dir}.\n"
                f"Tip: download the canonical .dat files:\n"
                f"  airports.dat : https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat\n"
                f"  airlines.dat : https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
            )
    return chosen[0], chosen[1]


def main(args):
    raw_dir = Path(args.csv_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ap_path, al_path = _resolve_input_files(raw_dir)

    airports = _load_openflights_file(ap_path, kind="airport")
    airlines = _load_openflights_file(al_path, kind="airline")

    airports.to_parquet(out_dir / "airports.parquet", index=False)
    airlines.to_parquet(out_dir / "airlines.parquet", index=False)

    print(f"Wrote {len(airports)} airports → {out_dir/'airports.parquet'}")
    print(f"Wrote {len(airlines)} airlines → {out_dir/'airlines.parquet'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv_dir", default="data/raw/openflights", help="Folder with OpenFlights .dat or .csv files")
    p.add_argument("--out_dir", default="data/processed", help="Output folder for Parquet files")
    main(p.parse_args())
