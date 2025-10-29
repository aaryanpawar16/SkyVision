"""
Collect image/logo URLs and licenses into a single CSV to be merged via entity id.
This script does NOT download images; it only aggregates URLs & metadata.

Input example:
- data/external/image_urls.csv with columns:
  entity_type (airport|airline), id, url, license, attribution, style, tags (comma-separated)

Output:
- data/external/image_urls.csv (cleaned & de-duped)
"""
from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path

def main(args):
    src = Path(args.input_csv)
    if not src.exists():
        # Create an empty scaffold if not present
        df = pd.DataFrame(columns=["entity_type","id","url","license","attribution","style","tags"])
        df.to_csv(src, index=False)
        print(f"Created template: {src}")
        return

    df = pd.read_csv(src)
    # Basic cleanup
    df["entity_type"] = df["entity_type"].str.strip().str.lower()
    df = df[df["entity_type"].isin(["airport", "airline"])]
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["id", "url"])
    df["id"] = df["id"].astype(int)
    df = df.drop_duplicates(subset=["entity_type","id"]).reset_index(drop=True)
    df.to_csv(src, index=False)
    print(f"Cleaned image url list → {src} ({len(df)} rows)")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input_csv", default="data/external/image_urls.csv")
    main(p.parse_args())
