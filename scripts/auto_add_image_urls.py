# scripts/auto_add_image_urls.py
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
URLS_CSV = ROOT / "data" / "external" / "image_urls.csv"

DEF_SAMPLE = "https://upload.wikimedia.org/wikipedia/commons/7/78/Sample_Image.jpg"

# ✈️ Curated Global Airport Image Entries (Fixed + Expanded)
IMAGE_ENTRIES = [
    # ---- ASIA / APAC ----
    {"hint": "Singapore Changi", "city": "Singapore",
     "url": "https://thedesignair.files.wordpress.com/2015/03/image-3-aerial-view-of-jewel-changi-airport-2.jpg",
     "style": "glass", "tags": "modern,indoor,garden"},
    {"hint": "Dubai International", "city": "Dubai",
     "url": "https://c8.alamy.com/comp/R5FD23/terminal-3-dubai-international-airport-dubai-uae-R5FD23.jpg",
     "style": "glass", "tags": "modern,hub"},
    {"hint": "Hamad International", "city": "Doha",
     "url": "https://images.adsttc.com/media/images/5ce3/0013/284d/d176/7b00/028d/large_jpg/1_HIA_Tim_Griffith_HOK.jpg?1558380556",
     "style": "glass", "tags": "modern,art,hub,spacious"},
    {"hint": "Hong Kong International", "city": "Hong Kong",
     "url": "https://aviationsourcenews.com/wp-content/uploads/2024/11/HKIA-bird-1.jpg",
     "style": "steel", "tags": "glass,curved,modern"},
    {"hint": "Tokyo Haneda", "city": "Tokyo",
     "url": "https://thumbs.dreamstime.com/z/tokyo-international-airport-haneda-hnd-sign-japan-haneda-one-two-primary-airports-serve-greater-tokyo-area-base-181999175.jpg",
     "style": "clean", "tags": "japan,minimal"},
    {"hint": "Incheon International", "city": "Incheon",
     "url": "https://s28477.pcdn.co/wp-content/uploads/2017/12/ICN_1-984x554.jpg",
     "style": "glass", "tags": "curved,greenery"},

    # ---- INDIA ----
    {"hint": "Indira Gandhi International", "city": "Delhi",
     "url": "https://buildings.honeywell.com/content/dam/hbtbt/en/images/horizontal/case-indira-gandhi-international-airport-igia-new-delhi-2880x1440.jpg",
     "style": "art", "tags": "installations,modern,india"},
    {"hint": "Kempegowda International", "city": "Bangalore",
     "url": "https://www.arch2o.com/wp-content/uploads/2018/07/Arch2O-kempegowda-international-airport-hok-3.jpg",
     "style": "garden", "tags": "biophilic,wood"},
    {"hint": "Rajiv Gandhi International", "city": "Hyderabad",
     "url": "https://tse1.mm.bing.net/th/id/OIP.Jx467U10U2KX3NUAxOSZ0wHaDP?pid=Api&P=0&h=220",
     "style": "modern", "tags": "spacious"},
    {"hint": "Cochin International", "city": "Kochi",
     "url": "https://s28477.pcdn.co/wp-content/uploads/2020/05/cochin_3-984x554.jpg",
     "style": "heritage", "tags": "wood,arches"},
    # New Chennai Link
    {"hint": "Chennai International", "city": "Madras",
     "url": "https://static.tnn.in/thumb/msid-97976624,thumbsize-94210,width-1280,height-720,resizemode-75/97976624.jpg",
     "style": "modern", "tags": "bright,india"},

    # ---- EUROPE ----
    {"hint": "Zürich", "city": "Zurich",
     "url": "https://www.myswitzerland.com/-/media/st/gadmin/images/partner/strapa/flughafen%20zrich/03_airport_zurich_plane_92626.jpg",
     "style": "glass", "tags": "swiss,clean"},
    {"hint": "London Heathrow", "city": "London",
     "url": "https://tse2.mm.bing.net/th/id/OIP.OU0YJWOLPk-Jdq8sDDp8JgHaDz?pid=Api&P=0&h=220",
     "style": "steel", "tags": "T5,arched"},
    {"hint": "Frankfurt am Main", "city": "Frankfurt",
     "url": "https://tse4.mm.bing.net/th/id/OIP.caZbXLBazxvNeY2CrLqbaQHaE8?pid=Api&P=0&h=220",
     "style": "modern", "tags": "hub,germany"},
    {"hint": "Amsterdam Airport Schiphol", "city": "Amsterdam",
     "url": "https://tse2.mm.bing.net/th/id/OIP.c8N0OOmRpo5WQ3qvnyt59QHaFj?pid=Api&P=0&h=220",
     "style": "modern", "tags": "netherlands"},
    {"hint": "Charles de Gaulle", "city": "Paris",
     "url": "https://images.travelandleisureasia.com/wp-content/uploads/sites/2/2022/12/05140724/TERMINAL-ONE.jpg",
     "style": "wood", "tags": "curved,arches"},
    {"hint": "Adolfo Suárez Madrid–Barajas", "city": "Madrid",
     "url": "https://s28477.pcdn.co/wp-content/uploads/2018/01/MAD_1-984x554.jpg",
     "style": "color", "tags": "bamboo,waves"},
    {"hint": "Fiumicino", "city": "Rome",
     "url": "https://s28477.pcdn.co/wp-content/uploads/2018/03/FCO_New_5-984x554.jpg",
     "style": "modern", "tags": "italy"},
    # New Munich Link
    {"hint": "Munich", "city": "Munich",
     "url": "https://tse4.mm.bing.net/th/id/OIP.OmDx7-dcTEwExuldHRLB5AHaE8?pid=Api&P=0&h=220",
     "style": "glass", "tags": "bavaria,clean"},
    # New Istanbul Link
    {"hint": "Istanbul Airport", "city": "Istanbul",
     "url": "https://thumbs.dreamstime.com/b/istanbul-airport-iata-ist-icao-ltfm-main-international-airport-serving-istanbul-turkey-located-arnavutkoy-147017479.jpg",
     "style": "vault", "tags": "arches,spacious,modern"},

    # ---- NORTH AMERICA ----
    {"hint": "Los Angeles International", "city": "Los Angeles",
     "url": "https://www.dlrgroup.com/wp-content/uploads/2021/07/75_13225_00_N9_weblg.jpg",
     "style": "modern", "tags": "LAX,international"},
    {"hint": "John F Kennedy International", "city": "New York",
     "url": "http://newyorkyimby.com/wp-content/uploads/2017/01/John-F.-Kennedy-International-Airport.jpg",
     "style": "modern", "tags": "JFK,bright"},
    {"hint": "San Francisco International", "city": "San Francisco",
     "url": "https://tse4.mm.bing.net/th/id/OIP.q0HQied0OcUFeb8PCI_adgHaEf?pid=Api&P=0&h=220",
     "style": "wood", "tags": "SFO,curved"},
    {"hint": "Lester B. Pearson", "city": "Toronto",
     "url": "http://www.world-airport-codes.com/content/uploads/2013/08/YYZ_alexander_cortez_verygoodairportbeenthere_n01zq5oaox.jpg",
     "style": "vault", "tags": "canada,hub"},
    {"hint": "Vancouver International", "city": "Vancouver",
     "url": "https://journeyable.org/wp-content/uploads/2024/01/Vancouver-International-Airport-Aerial-Shot.jpg",
     "style": "wood", "tags": "canada,biophilic"},
    # New DFW Link
    {"hint": "Dallas Fort Worth International", "city": "Dallas-Fort Worth",
     "url": "http://res.cloudinary.com/culturemap-com/image/upload/q_auto/ar_4:3,c_fill,g_faces:center,w_1200/v1479695938/photos/68943_original.jpg",
     "style": "modern", "tags": "DFW,hub,spacious"},
    # New Denver Link
    {"hint": "Denver International", "city": "Denver",
     "url": "https://image.architonic.com/imgArc/project-1/4/5205148/Fentress-DenverAirport-09.jpg",
     "style": "fabric", "tags": "peaks,tents,white"},
    # New Chicago O'Hare Link
    {"hint": "Chicago O'Hare International", "city": "Chicago",
     "url": "https://www.hok.com/wp-content/uploads/2019/05/OHare-International-Airport-Terminal-5-Exterior-1900-1600x1069.jpg",
     "style": "tunnel", "tags": "ORD,neon,art,color"},
    # New Miami Link
    {"hint": "Miami International", "city": "Miami",
     "url": "https://miami-airport.com/images/fine%20arts/Hall%20of%20Aviation/Image%202.jpg",
     "style": "color", "tags": "MIA,art,installation"},

    # ---- OCEANIA ----
    # New Goroka Link
    {"hint": "Goroka", "city": "Goroka",
     "url": "https://www.ehp.gov.pg/wp-content/uploads/elementor/thumbs/Goroka-Airport-1-q8obtpbw8lsoc5nzv1y50x2aojtdxpb9yh3nkzd8s8.webp",
     "style": "glass", "tags": "green,modern"},
    # New Sydney Link
    {"hint": "Sydney Kingsford Smith", "city": "Sydney",
     "url": "https://tse1.mm.bing.net/th/id/OIP.psJfhrJ4d0X0fdg85POiwwHaEK?pid=Api&P=0&h=220",
     "style": "modern", "tags": "australia,glass"},
    # New Auckland Link
    {"hint": "Auckland International", "city": "Auckland",
     "url": "https://tse2.mm.bing.net/th/id/OIP.ai4UTHI-wAbmyhWm_y3yCgHaE8?pid=Api&P=0&h=220",
     "style": "modern", "tags": "new zealand,maori,art"},
]


# ---------- Matching + CSV Writing ----------
def best_match(df: pd.DataFrame, hint: str, city: str | None) -> pd.Series | None:
    m = df[df["name"].str.contains(hint, case=False, na=False)]
    if city:
        mc = m[m["city"].str.contains(city, case=False, na=False)]
        if not mc.empty:
            m = mc
    if m.empty:
        return None
    m = m.assign(_has_iata=m["iata"].notna())
    m = m.sort_values(by=["_has_iata", "name"], ascending=[False, True])
    return m.iloc[0]


def main(overwrite: bool = False, dry_run: bool = False):
    PROC.mkdir(parents=True, exist_ok=True)
    URLS_CSV.parent.mkdir(parents=True, exist_ok=True)

    airports = pd.read_parquet(PROC / "airports.parquet")

    rows = []
    for e in IMAGE_ENTRIES:
        match = best_match(airports, e["hint"], e.get("city"))
        if match is None:
            print(f"⚠️  no match: {e['hint']} ({e.get('city', 'any')})")
            continue

        airport_id = int(match["id"])
        url = e.get("url") or f"/media/airport_{airport_id}.jpg"

        rows.append({
            "entity_type": "airport",
            "id": airport_id,
            "url": url,
            "license": "CC-BY / CC0 (verify source)",
            "attribution": "Wikimedia Commons or Local",
            "style": e.get("style", "modern"),
            "tags": e.get("tags", "international,hub"),
        })
        print(f"✅ matched {e['hint']} → id={airport_id}")

    df_new = pd.DataFrame(rows)

    if dry_run:
        print(df_new.head(10))
        return

    if URLS_CSV.exists():
        df_old = pd.read_csv(URLS_CSV)
        if overwrite:
            df = pd.concat([df_old, df_new]).drop_duplicates(subset=["entity_type", "id"], keep="last")
        else:
            existing = set(zip(df_old["entity_type"], df_old["id"]))
            new_rows = [r for r in rows if (r["entity_type"], r["id"]) not in existing]
            df_add = pd.DataFrame(new_rows)
            df = pd.concat([df_old, df_add])
    else:
        df = df_new

    df.to_csv(URLS_CSV, index=False)
    print(f"✨ wrote {URLS_CSV} with {len(df)} total entries.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing rows")
    ap.add_argument("--dry-run", action="store_true", help="Preview matches without writing")
    args = ap.parse_args()
    main(overwrite=args.overwrite, dry_run=args.dry_run)
