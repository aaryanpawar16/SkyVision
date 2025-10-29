# scripts/pin_airport_images.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "data" / "external" / "image_urls.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

# ✅ Only URLs known to succeed (based on your previous OK logs)
PINS = [
    (507,   "https://tse2.mm.bing.net/th/id/OIP.OU0YJWOLPk-Jdq8sDDp8JgHaDz?pid=Api&P=0&h=220", "steel", "arched,uk"),
    (3469,  "https://tse4.mm.bing.net/th/id/OIP.q0HQied0OcUFeb8PCI_adgHaEf?pid=Api&P=0&h=220", "wood", "sfo,curved"),
    (3576,  "https://tse3.mm.bing.net/th/id/OIP.ZwG9LeDXudaFfVn2GHeaEQHaEK?pid=Api&P=0&h=220", "modern", "mia,terminal"),
    (3670,  "https://sika.scene7.com/is/image/sika/glo-dallas-airport-2:3-2?wid=3300&hei=2200&fit=crop%2C1", "modern", "dfw,wide"),
    (11051, "https://images.adsttc.com/media/images/5ce3/0013/284d/d176/7b00/028d/large_jpg/1_HIA_Tim_Griffith_HOK.jpg?1558380556", "glass", "doha,hok"),
    (12087, "https://tse1.mm.bing.net/th/id/OIP.Jx467U10U2KX3NUAxOSZ0wHaDP?pid=Api&P=0&h=220", "modern", "hyderabad,india"),
    # Add more that you know are good (from your earlier “ok -> airport_xxx_*.jpg” list):
    (156,   "https://journeyable.org/wp-content/uploads/2024/01/Vancouver-International-Airport-Aerial-Shot.jpg", "wood", "canada,biophilic"),
    (1128,  "https://www.cairo-airport.info/wp-content/uploads/2022/03/cairo-airport-cai.jpg", "modern", "egypt,hub"),
    (1229,  "https://s28477.pcdn.co/wp-content/uploads/2018/01/MAD_1-984x554.jpg", "color", "bamboo,waves"),
    (1382,  "https://images.travelandleisureasia.com/wp-content/uploads/sites/2/2022/12/05140724/TERMINAL-ONE.jpg", "wood", "curved,arches"),
    (1555,  "https://s28477.pcdn.co/wp-content/uploads/2018/03/FCO_New_5-984x554.jpg", "modern", "italy"),
    (1678,  "https://www.myswitzerland.com/-/media/st/gadmin/images/partner/strapa/flughafen%20zrich/03_airport_zurich_plane_92626.jpg", "glass", "swiss,clean"),
    (2179,  "https://mybayutcdn.bayut.com/mybayut/wp-content/uploads/abu-dhabi-airport-terminal-1-7220-1024x640.jpg", "modern", "uae,spacious"),
    (3131,  "https://www.arch2o.com/wp-content/uploads/2018/07/Arch2O-kempegowda-international-airport-hok-3.jpg", "garden", "biophilic,wood"),
    (3136,  "https://s28477.pcdn.co/wp-content/uploads/2020/05/cochin_3-984x554.jpg", "heritage", "wood,arches"),
    (3316,  "https://thedesignair.files.wordpress.com/2015/03/image-3-aerial-view-of-jewel-changi-airport-2.jpg", "glass", "jewel,garden"),
    (3361,  "https://d3e1m60ptf1oym.cloudfront.net/77a4fcdd-b4cf-4af1-9ced-417d869b9d4e/160524-A336_uxga.jpg", "glass", "sydney,interior"),
    (3797,  "http://newyorkyimby.com/wp-content/uploads/2017/01/John-F.-Kennedy-International-Airport.jpg", "modern", "JFK,bright"),
]

def main():
    rows = []
    for aid, url, style, tags in PINS:
        rows.append({
            "entity_type": "airport",
            "id": aid,
            "url": url,
            "style": style,
            "tags": tags,
            "license": "Check source license",
            "attribution": "Source per URL",
        })
    df = pd.DataFrame(rows, columns=["entity_type","id","url","style","tags","license","attribution"])
    df.to_csv(OUT, index=False)
    print(f"[ok] wrote {OUT} with {len(df)} rows")

if __name__ == "__main__":
    main()
