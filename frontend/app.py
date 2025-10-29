# frontend/app.py
import os
import io
import json
import time
import base64
from typing import Dict, Any, List, Optional
from urllib.parse import quote

import requests
import streamlit as st
from PIL import Image

# ---------- Config ----------
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="SkyVision — Multimodal Travel Search",
    page_icon="✈️",
    layout="wide",
)

# Inline SVG fallback for missing images
PLACEHOLDER_DATA_URI = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='400'>"
    "<rect width='100%' height='100%' fill='%23f3f4f6'/>"
    "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
    "font-family='sans-serif' font-size='16' fill='%239ca3af'>No image</text>"
    "</svg>"
)

# ---------- Styles ----------
def load_local_styles():
    """Loads custom CSS from frontend/assets/styles.css"""
    try:
        # Path is relative to where streamlit is run (project root)
        css_path = os.path.join("frontend", "assets", "styles.css")
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("styles.css not found. Make sure it's at frontend/assets/styles.css")
    except Exception as e:
        st.error(f"Error loading styles: {e}")

# Load the external stylesheet
load_local_styles()

# ---------- Helpers ----------
def _safe_error_detail(resp: Optional[requests.Response], default_msg: str = "Request failed") -> str:
    if resp is None:
        return default_msg
    try:
        j = resp.json()
        if isinstance(j, dict) and "detail" in j:
            return str(j["detail"])
        return json.dumps(j)
    except Exception:
        return (resp.text or "").strip() or default_msg


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Unified URL handler:
    - /media/... or media/... → serve directly from backend
    - absolute http/https URLs → proxy via backend /proxy?u=<encoded>
    - bare filenames → treated as /media/<filename>
    """
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None

    # Fix missing leading slash
    if u.startswith("media/"):
        u = "/" + u

    # Local backend-served media
    if u.startswith("/media/"):
        return f"{API_URL}{u}"

    # External URLs — route through proxy
    if u.startswith(("http://", "https://")):
        return f"{API_URL}/proxy?u={quote(u, safe='')}"

    # Bare filenames — assume media file in backend
    return f"{API_URL}/media/{u.lstrip('/')}"


def _add_cache_bust(u: Optional[str], nonce: Optional[str]) -> Optional[str]:
    if not u:
        return None
    if nonce:
        sep = "&" if "?" in u else "?"
        u = f"{u}{sep}cb={nonce}"
    return u

# ---------- API Calls ----------
def api_health() -> Dict[str, Any]:
    try:
        r = requests.get(f"{API_URL}/healthz", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def api_search_text(query: str, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {"query": query, "k": 24, "filters": filters or {}} # 9999 -> 24
    r = requests.post(f"{API_URL}/search/text", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def api_search_image(file_bytes: bytes, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    files = {"file": ("upload.png", file_bytes, "image/png")}
    params = {"k": 24} # 9999 -> 24
    if filters and filters.get("has_logo"):
        params["has_logo"] = "true"
    r = requests.post(f"{API_URL}/search/image", files=files, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def api_search_hybrid(query: str, image_bytes: Optional[bytes], filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None
    payload = {
        "query": query,
        "k": 24, # 1000 -> 24
        "filters": filters or {},
        "image_base64": image_b64,
        "weight_text": 0.6,
        "weight_image": 0.4,
    }
    r = requests.post(f"{API_URL}/search/hybrid", json=payload, timeout=90)
    r.raise_for_status()
    return r.json()

# ---------- UI Components ----------
def card(hit: Dict[str, Any], debug: bool = False) -> str:
    name = hit.get("name", "Unknown")
    city = hit.get("city", "")
    country = hit.get("country", "")
    where = ", ".join(p for p in [city, country] if p)
    raw_url = (hit.get("url") or "").strip()
    url = _add_cache_bust(_normalize_url(raw_url), st.session_state.get("img_nonce"))
    distance = hit.get("distance") # Get the distance

    meta = hit.get("metadata") or {}
    tags = meta.get("tags", []) # This might be a string
    style = meta.get("style")

    img_html = (
        f"<img src='{url}' alt='{name}' class='card-img' loading='lazy' decoding='async' "
        f"referrerpolicy='no-referrer' "
        f"onerror=\"this.onerror=null;this.src='{PLACEHOLDER_DATA_URI}';\"/>"
        if url else f"<img src='{PLACEHOLDER_DATA_URI}' class='card-img placeholder' alt='No image'/>"
    )
    
    # --- THIS IS THE FIX ---
    # Create a clean list of all chip items
    chip_items = ([style] if style else [])
    if isinstance(tags, str):
        # Handle comma-separated or space-separated string from CSV/DB
        # This fixes "glassgardenindoormodern"
        tags_list = tags.replace(',', ' ').split()
        chip_items.extend(t.strip() for t in tags_list if t.strip())
    elif isinstance(tags, list):
        # Handle list of strings (if data is already clean)
        chip_items.extend(tags)
    
    # Limit to 4 chips total for a clean look
    tag_html = "".join(f"<span class='chip'>{t}</span>" for t in chip_items[:4])
    # --- END OF FIX ---
    
    # Create the distance badge HTML
    badge_html = ""
    if distance is not None:
        badge_html = f"<span class='badge'>Distance: {distance:.4f}</span>"

    debug_html = f"<div class='debug-url'>{url}</div>" if debug and url else ""

    return f"""
    <div class='card'>
      {img_html}
      <div class='card-body'>
        <div class='card-title'>{name}</div>
        <div class='card-sub'>{where}</div>
        <div class='chips'>{tag_html}</div>
        {badge_html}
        {debug_html}
      </div>
    </div>
    """

def render_results(results: Dict[str, Any], debug: bool = False):
    hits = results.get("hits", [])
    if not hits:
        st.info("No results found. Try refining your search query.")
        return

    cols_per_row = 4
    for i in range(0, len(hits), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, c in enumerate(cols):
            if i + j >= len(hits):
                break
            h = hits[i + j]
            with c:
                st.markdown(card(h, debug=debug), unsafe_allow_html=True)

# ---------- Sidebar ----------
st.sidebar.title("SkyVision ✈️")
st.sidebar.caption("Multimodal Travel Media Search (MariaDB Vector)")

with st.sidebar.expander("Backend", expanded=False):
    st.write(f"API URL: `{API_URL}`")
    st.write(f"Media base: `{MEDIA_BASE_URL}`")
    health = api_health()
    if health.get("ok"):
        st.success("✅ Backend Healthy")
    else:
        st.error(f"❌ {health.get('error', 'Unknown error')}")

with st.sidebar.expander("Filters", expanded=True):
    country = st.text_input("Country (optional)", value="")
    style = st.text_input("Style (optional)", value="", help="e.g., glass, modern, classic")
    only_images = st.checkbox("Only results with images (airports)", value=True)
    only_logos = st.checkbox("Only results with logos (airlines)", value=True)
    debug_mode = st.checkbox("🧩 Debug mode (show URLs)", value=False)

    if "img_nonce" not in st.session_state:
        st.session_state.img_nonce = str(int(time.time()))
    if st.button("🔄 Force refresh images"):
        st.session_state.img_nonce = str(int(time.time()))
        st.rerun()

# ---------- Tabs ----------
tab1, tab2, tab3 = st.tabs(["🔎 Text Search", "🖼️ Image Search", "🧠 Hybrid Search"])

# --- Text Search ---
with tab1:
    st.header("Text → Image: Find visually similar airports")
    # st.caption("Example: *airports like Singapore Changi with indoor gardens*")

    q = st.text_input("Describe what you want to find", placeholder="e.g. airports with bamboo ceilings and glass facades")
    if st.button("Search", type="primary", use_container_width=True):
        if not q.strip():
            st.warning("Please enter a valid query.")
        else:
            flt = {}
            if country.strip():
                flt["country"] = country.strip()
            if style.strip():
                flt["style"] = style.strip()
            if only_images:
                flt["has_image"] = True

            with st.spinner("🔍 Searching by text..."):
                try:
                    render_results(api_search_text(q.strip(), flt), debug=debug_mode)
                except Exception as e:
                    st.error(f"Server error: {e}")

# --- Image Search ---
with tab2:
    st.header("Image → Image: Find similar airline logos")
    uploaded = st.file_uploader("Upload a logo or image", type=["png", "jpg", "jpeg", "webp"])
    if uploaded:
        img = Image.open(uploaded).convert("RGB")
        st.image(img, caption="Uploaded", use_column_width=True)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        if st.button("Search Similar Images", type="secondary", use_container_width=True):
            with st.spinner("🔎 Searching visually..."):
                try:
                    filters = {"has_logo": True} if only_logos else {}
                    render_results(api_search_image(img_bytes, filters), debug=debug_mode)
                except Exception as e:
                    st.error(f"Error: {e}")

# --- Hybrid Search ---
with tab3:
    st.header("Hybrid Search: Combine Text + Image Intelligence")
    st.caption("Blend semantic and visual similarity for more powerful retrieval.")

    q2 = st.text_input("Describe your query", placeholder="e.g. airports with wooden ceilings and natural gardens")
    uploaded2 = st.file_uploader("Optional image (for context)", type=["png", "jpg", "jpeg", "webp"], key="hybrid")
    image_bytes2 = None
    if uploaded2:
        img = Image.open(uploaded2).convert("RGB")
        st.image(img, caption="Uploaded reference image", use_column_width=True)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes2 = buf.getvalue()

    if st.button("Run Hybrid Search 🚀", type="primary", use_container_width=True):
        if not q2.strip():
            st.warning("Please enter a description.")
        else:
            flt = {}
            if country.strip():
                flt["country"] = country.strip()
            if style.strip():
                flt["style"] = style.strip()
            if only_images:
                flt["has_image"] = True
            with st.spinner("🔍 Running hybrid multimodal search..."):
                try:
                    render_results(api_search_hybrid(q2.strip(), image_bytes2, flt), debug=debug_mode)
                except Exception as e:
                    st.error(f"Hybrid search error: {e}")

# ---------- Footer ----------
st.markdown(
    """
    <div class='footer'>
      <span>🌍 Powered by <b>MariaDB Vector</b> · Built with ❤️ using Streamlit</span>
    </div>
    """,
    unsafe_allow_html=True,
)


