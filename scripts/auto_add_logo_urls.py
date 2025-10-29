# scripts/auto_add_logo_urls.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
AIRLINES = PROC / "airlines.parquet"
LOGOS   = ROOT / "data" / "external" / "logo_urls.csv"

LOGO_ENTRIES = [
    {"hint": "Air India",           "url": "https://logos-world.net/wp-content/uploads/2023/01/Air-India-Logo.jpg"},
    {"hint": "Emirates",            "url": "https://pluspng.com/img-png/emirates-airlines-logo-png-emirates-logo-the-most-famous-brands-and-company-logos-in-the-world-3840x2160.png"},
    {"hint": "Singapore Airlines",  "url": "https://pluspng.com/img-png/singapore-airlines-logo-png-singapore-airlines-logos-brands-and-logotypes-4600x1950.png"},
    # {"hint": "Qatar Airways",       "url": "https://seeklogo.com/images/Q/qatar-airways-logo-E096F45AE3-seeklogo.com.png"},
    {"hint": "Lufthansa",           "url": "https://tse4.mm.bing.net/th/id/OIP.rQJPr1moJefKCUwgYtpCGQHaEK?pid=Api&P=0&h=220"},
    {"hint": "British Airways",     "url": "https://logos-world.net/wp-content/uploads/2021/02/British-Airways-Logo-1997-present.jpg"},
    {"hint": "United Airlines",     "url": "https://logos-world.net/wp-content/uploads/2020/11/United-Airlines-Logo.png"},
    {"hint": "American Airlines",   "url": "https://logos-world.net/wp-content/uploads/2020/11/American-Airlines-Logo.png"},
    {"hint": "Delta Air Lines",     "url": "https://logos-world.net/wp-content/uploads/2021/08/Delta-Logo.png"},
]

def best_match(df, hint: str):
    m = df[df["name"].str.contains(hint, case=False, na=False)]
    if m.empty:
        return None
    # Prefer rows with IATA, shortest name
    m = m.assign(_has_iata=m["iata"].notna()).sort_values(["_has_iata","name"], ascending=[False,True])
    return m.iloc[0]

def main():
    df = pd.read_parquet(AIRLINES)
    rows = []
    for e in LOGO_ENTRIES:
        r = best_match(df, e["hint"])
        if r is None:
            print(f"[warn] no match: {e['hint']}")
            continue
        rows.append({
            "entity_type": "airline",
            "id": int(r["id"]),
            "url": e["url"],
            "style": "logo",
            "tags": "brand,airline"
        })
        print(f"[ok] {e['hint']} -> id={int(r['id'])}, name={r['name']}")
    out = pd.DataFrame(rows, columns=["entity_type","id","url","style","tags"])
    LOGOS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(LOGOS, index=False)
    print(f"[done] wrote {LOGOS} with {len(out)} rows")

if __name__ == "__main__":
    main()
