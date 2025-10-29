# scripts/check_images.py
from __future__ import annotations
import os
import sys
import argparse
import requests
import mariadb
from urllib.parse import quote, urlparse

DEFAULT_API = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Some CDNs want a Referer (e.g., Wikimedia)
REFERERS = {
    "upload.wikimedia.org": "https://commons.wikimedia.org/",
    "wikimedia.org": "https://commons.wikimedia.org/",
}

def norm_local(u: str, api_base: str) -> str:
    """Normalize a LOCAL /media path to a fetchable URL on the backend host."""
    if u.startswith("media/"):
        u = "/" + u
    if u.startswith("/media/"):
        return f"{api_base}{u}"
    # not local
    return ""

def norm_remote(u: str, api_base: str, via_backend_proxy: bool) -> str:
    """Return a fetchable URL for a REMOTE http(s) resource."""
    if not u.startswith(("http://", "https://")):
        return ""
    if via_backend_proxy:
        return f"{api_base}/proxy?u={quote(u, safe='')}"
    return u

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s

def is_image_response(resp: requests.Response) -> bool:
    ct = (resp.headers.get("Content-Type") or "").lower()
    return ct.startswith("image/") or ct.startswith("application/octet-stream")

def fetch_ok(session: requests.Session, url: str) -> tuple[bool, int, str]:
    """
    Try HEAD first; if inconclusive or no content-length, fall back to GET (streamed).
    Returns (ok, status_code, content_type).
    """
    if not url:
        return False, 0, ""

    # Set optional Referer based on host
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    headers = {}
    for key in REFERERS:
        if host.endswith(key):
            headers["Referer"] = REFERERS[key]
            break

    try:
        # HEAD pass
        r = session.head(url, timeout=10, allow_redirects=True, headers=headers)
        if r.status_code == 200 and is_image_response(r):
            # Consider ok if content-length reasonable (when present)
            clen = int(r.headers.get("content-length", "0") or "0")
            if clen >= 200:
                return True, r.status_code, r.headers.get("Content-Type", "")
        # GET fallback (stream small chunk)
        r = session.get(url, timeout=12, headers=headers, stream=True, allow_redirects=True)
        if r.status_code == 200 and is_image_response(r):
            total = 0
            for chunk in r.iter_content(65536):
                if not chunk:
                    break
                total += len(chunk)
                if total >= 200:
                    return True, r.status_code, r.headers.get("Content-Type", "")
            # Small file
            return False, r.status_code, r.headers.get("Content-Type", "")
        return False, r.status_code, r.headers.get("Content-Type", "")
    except Exception:
        return False, 0, ""

def check_table(kind: str,
                api_base: str,
                db_host: str,
                db_user: str,
                db_password: str,
                db_name: str,
                limit: int,
                show_ok: bool,
                skip_remote: bool,
                via_backend_proxy: bool):
    """
    kind: 'airports' or 'airlines'
    """
    col = "image_url" if kind == "airports" else "logo_url"

    conn = mariadb.connect(
        host=db_host, user=db_user, password=db_password, database=db_name, connect_timeout=5
    )
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, name, {col}
        FROM {kind}
        WHERE {col} IS NOT NULL AND {col} <> ''
        LIMIT {int(limit)};
        """
    )

    session = make_session()

    total = 0
    local_ok = local_bad = 0
    remote_ok = remote_bad = 0
    remote_skipped = 0

    for id_, name, url in cur:
        total += 1
        u = (url or "").strip()
        is_remote = u.startswith(("http://", "https://"))

        if not is_remote:
            # Treat as local (/media/...)
            test_url = norm_local(u, api_base)
            ok, status, _ = fetch_ok(session, test_url)
            if ok:
                local_ok += 1
                if show_ok:
                    print(f"[OK]  {kind} #{id_} {name} -> {test_url}")
            else:
                local_bad += 1
                print(f"[BAD] {kind} #{id_} {name} -> {test_url} [{status}]")
        else:
            if skip_remote:
                remote_skipped += 1
                print(f"[SKIP REMOTE] {kind} #{id_} {name} -> {u}")
                continue
            test_url = norm_remote(u, api_base, via_backend_proxy)
            ok, status, _ = fetch_ok(session, test_url)
            if ok:
                remote_ok += 1
                if show_ok:
                    print(f"[OK-REMOTE] {kind} #{id_} {name} -> {test_url}")
            else:
                remote_bad += 1
                print(f"[BAD-REMOTE] {kind} #{id_} {name} -> {test_url} [{status}]")

    cur.close()
    conn.close()

    print(
        f"\n{kind} summary: total={total} | "
        f"local ok={local_ok}, local bad={local_bad} | "
        f"remote ok={remote_ok}, remote bad={remote_bad}, remote skipped={remote_skipped}"
    )

def main():
    ap = argparse.ArgumentParser(description="Check image/logo URLs for airports/airlines.")
    ap.add_argument("--api", default=DEFAULT_API, help="Backend base (for /media and optional /proxy)")
    ap.add_argument("--db_host", default=os.getenv("DB_HOST", "localhost"))
    ap.add_argument("--db_user", default=os.getenv("DB_USER", "sky"))
    ap.add_argument("--db_password", default=os.getenv("DB_PASSWORD", "vision"))
    ap.add_argument("--db_name", default=os.getenv("DB_NAME", "skyvision"))
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--show-ok", action="store_true", help="Print OK rows too")
    ap.add_argument("--skip-remote", action="store_true", help="Only check local /media URLs; mark remotes as skipped")
    ap.add_argument("--via-backend-proxy", action="store_true",
                    help="When checking remote http(s) URLs, route via {API}/proxy?u=…")
    ap.add_argument("--only", choices=["airports", "airlines", "both"], default="both")
    args = ap.parse_args()

    if args.only in ("airports", "both"):
        check_table("airports", args.api, args.db_host, args.db_user, args.db_password, args.db_name,
                    args.limit, args.show_ok, args.skip_remote, args.via_backend_proxy)
    if args.only in ("airlines", "both"):
        check_table("airlines", args.api, args.db_host, args.db_user, args.db_password, args.db_name,
                    args.limit, args.show_ok, args.skip_remote, args.via_backend_proxy)

if __name__ == "__main__":
    main()
