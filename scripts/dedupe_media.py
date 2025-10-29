# scripts/dedupe_media.py
from __future__ import annotations
import hashlib, csv, argparse
from pathlib import Path
from typing import Dict, List
import mariadb

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "data" / "media"
IMG_CSV = ROOT / "data" / "external" / "image_urls_local.csv"
MAP_CSV = ROOT / "data" / "external" / "media_dedupe_map.csv"

def sha1_of(path: Path, chunk=1<<20):
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def build_map() -> Dict[str, str]:
    # returns {"/media/duplicate.jpg": "/media/canonical.jpg"}
    by_hash: Dict[str, List[Path]] = {}
    for p in MEDIA.glob("*"):
        if not p.is_file(): continue
        try:
            h = sha1_of(p)
            by_hash.setdefault(h, []).append(p)
        except Exception:
            pass
    dup_map: Dict[str, str] = {}
    for files in by_hash.values():
        if len(files) < 2: continue
        files = sorted(files, key=lambda x: x.name.lower())
        canonical = f"/media/{files[0].name}"
        for dup in files[1:]:
            dup_map[f"/media/{dup.name}"] = canonical
    return dup_map

def write_map_csv(dup_map: Dict[str,str]):
    MAP_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MAP_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from","to"])
        for k,v in sorted(dup_map.items()):
            w.writerow([k,v])
    print(f"[map] wrote {MAP_CSV} ({len(dup_map)} remaps)")

def rewrite_image_urls_csv(dup_map: Dict[str,str]):
    if not IMG_CSV.exists(): 
        print(f"[csv] {IMG_CSV} not found, skip.")
        return
    import pandas as pd
    df = pd.read_csv(IMG_CSV)
    if "url" not in df.columns:
        print(f"[csv] no 'url' col in {IMG_CSV}, skip.")
        return
    before = df["url"].copy()
    df["url"] = df["url"].apply(lambda u: dup_map.get(str(u).strip(), u))
    changed = (df["url"] != before).sum()
    df.to_csv(IMG_CSV, index=False)
    print(f"[csv] updated {IMG_CSV} (changed {changed} rows)")

def patch_db(dup_map: Dict[str,str], host, port, user, password, db):
    if not dup_map:
        print("[db] no changes.")
        return
    conn = mariadb.connect(host=host, port=port, user=user, password=password, database=db, autocommit=True)
    cur = conn.cursor()
    # Airports
    for frm, to in dup_map.items():
        cur.execute(
            "UPDATE airports SET image_url=? WHERE image_url=?",
            (to, frm)
        )
    # (If you also store logos in /media, you can enable this)
    # for frm, to in dup_map.items():
    #     cur.execute(
    #         "UPDATE airlines SET logo_url=? WHERE logo_url=?",
    #         (to, frm)
    #     )
    cur.close(); conn.close()
    print("[db] patched URLs in DB.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update_csv", action="store_true", help="Rewrite data/external/image_urls_local.csv using mapping")
    ap.add_argument("--update_db", action="store_true", help="Rewrite airports.image_url in MariaDB")
    ap.add_argument("--db_host", default="localhost")
    ap.add_argument("--db_port", type=int, default=3306)
    ap.add_argument("--db_user", default="sky")
    ap.add_argument("--db_password", default="vision")
    ap.add_argument("--db_name", default="skyvision")
    args = ap.parse_args()

    dup_map = build_map()
    write_map_csv(dup_map)

    if args.update_csv:
        rewrite_image_urls_csv(dup_map)

    if args.update_db:
        patch_db(dup_map, args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)

if __name__ == "__main__":
    main()
