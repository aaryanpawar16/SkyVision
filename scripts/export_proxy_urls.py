# scripts/export_proxy_urls.py
from __future__ import annotations
import os
import mariadb
import pandas as pd

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "sky")
DB_PASS = os.getenv("DB_PASSWORD", "vision")
DB_NAME = os.getenv("DB_NAME", "skyvision")

OUT = "data/external/image_urls.csv"

def main():
    conn = mariadb.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASS, database=DB_NAME
    )
    cur = conn.cursor()

    # Anything still using the proxy or hotlinking big hosts
    proxy_like = (
        "image_url LIKE 'http://127.0.0.1:8000/proxy%' OR "
        "image_url LIKE 'https://upload.wikimedia.org/%' OR "
        "image_url LIKE 'http://upload.wikimedia.org/%' OR "
        "image_url LIKE 'https://%wikipedia.org/%' OR "
        "image_url LIKE 'http://%wikipedia.org/%' "
    )

    # Airports
    cur.execute(f"""
        SELECT id, COALESCE(image_url,'')
        FROM airports
        WHERE image_url IS NOT NULL AND image_url <> ''
          AND ({proxy_like});
    """)
    ap_rows = [{"entity_type":"airport","id":r[0],"url":r[1]} for r in cur.fetchall()]

    # Airlines
    cur.execute(f"""
        SELECT id, COALESCE(logo_url,'')
        FROM airlines
        WHERE logo_url IS NOT NULL AND logo_url <> ''
          AND (logo_url LIKE 'http://127.0.0.1:8000/proxy%%' OR
               logo_url LIKE 'https://%seeklogo.com/%');
    """)
    al_rows = [{"entity_type":"airline","id":r[0],"url":r[1]} for r in cur.fetchall()]

    cur.close()
    conn.close()

    rows = ap_rows + al_rows
    if not rows:
        print("[info] nothing to export — no proxy/hotlink URLs remain.")
        return

    df = pd.DataFrame(rows, columns=["entity_type","id","url"])
    df.to_csv(OUT, index=False)
    print(f"[ok] wrote {OUT} with {len(df)} rows")

if __name__ == "__main__":
    main()
