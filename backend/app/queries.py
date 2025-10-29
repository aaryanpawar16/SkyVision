from __future__ import annotations
from typing import Optional, Tuple, Any, Dict, List
import math
import re

from .config import settings
from .db import get_conn

try:
    from .utils.metrics import time_block
except Exception:
    from contextlib import contextmanager
    @contextmanager
    def time_block(_label: str):
        yield


# ------------ Helpers ------------

def _apply_filters(base_sql: str, filters: Optional[Dict[str, Any]], params: List[Any]) -> str:
    """Apply optional filters to the base SQL query."""
    if not filters:
        return base_sql

    clauses: List[str] = []
    if filters.get("country"):
        clauses.append("LOWER(country) = LOWER(?)")
        params.append(filters["country"])
    if filters.get("city"):
        clauses.append("LOWER(city) = LOWER(?)")
        params.append(filters["city"])
    if filters.get("style"):
        clauses.append("LOWER(JSON_VALUE(metadata, '$.style')) = LOWER(?)")
        params.append(filters["style"])
    if filters.get("has_image"):
        clauses.append("(image_url IS NOT NULL AND image_url <> '')")
    if filters.get("has_logo"):
        clauses.append("(logo_url IS NOT NULL AND logo_url <> '')")

    if clauses:
        base_sql += " WHERE " + " AND ".join(clauses)
    return base_sql


def _vec_text(vec_list: List[float]) -> str:
    """Serialize Python list[float] to MariaDB VEC_FromText-compatible string."""
    cleaned = [float(x) if math.isfinite(float(x)) else 0.0 for x in vec_list]
    return "[" + ",".join(map(str, cleaned)) + "]"


def _distance_expr() -> str:
    """Return SQL distance function (cosine or L2)."""
    fn = (settings.VECTOR_DISTANCE_FN or "VEC_DISTANCE_COSINE").strip()
    return f"{fn}(embedding, VEC_FromText(?))"


# ------------ Keyword + Region Detection ------------

_KEYWORD_WHITELIST = {
    "indoor", "garden", "gardens", "greenery", "trees", "plants",
    "glass", "modern", "classic", "vault", "arched", "arches",
    "wood", "bamboo", "fabric", "curved", "color", "bright",
    "lotus", "heritage", "spacious", "art", "biophilic", "beautiful", "facade", "facades"
}

_REGION_KEYWORDS = {
    "asia": ["india", "china", "japan", "singapore", "uae", "indonesia", "korea", "thailand", "qatar"],
    "europe": ["france", "uk", "germany", "italy", "switzerland", "spain", "netherlands", "turkey"],
    "africa": ["south africa", "egypt", "ethiopia", "morocco"],
    "america": ["usa", "canada", "mexico", "brazil"],
    "oceania": ["australia", "new zealand"]
}


def _extract_keywords(q: str) -> List[str]:
    """Extract known architectural and visual keywords from text."""
    toks = re.findall(r"[a-zA-Z]+", (q or "").lower())
    return sorted({t for t in toks if t in _KEYWORD_WHITELIST})


def _detect_region(q: str) -> Optional[List[str]]:
    """Detect region (e.g., 'Asian', 'European') from query text."""
    q_lower = (q or "").lower()
    for region, countries in _REGION_KEYWORDS.items():
        if region in q_lower or any(c in q_lower for c in countries):
            return countries
    return None


def _keyword_hit_sql_and_params(keywords: List[str]) -> tuple[str, List[Any]]:
    """Generate SQL expression for keyword matching in metadata."""
    if not keywords:
        return "0", []
    parts, params = [], []
    for kw in keywords:
        like = f"%{kw}%"
        parts.append(
            "(LOWER(JSON_VALUE(metadata, '$.style')) LIKE LOWER(?) "
            "OR LOWER(JSON_EXTRACT(metadata, '$.tags')) LIKE LOWER(?))"
        )
        params.extend([like, like])
    # --- FIXED: Use OR for multiple keywords ---
    # This means "bamboo garden" will find items matching "bamboo" OR "garden".
    return "(" + " OR ".join(parts) + ")", params


# ------------ Search Queries ------------

def search_airports_by_text(
    vec: List[float],
    k: int,  # not a hard cap anymore, we’ll limit to 1000 below
    filters: Optional[Dict[str, Any]] = None,
    query_text: Optional[str] = None,
) -> List[Tuple]:
    """
    Enhanced vector + region-aware keyword search.
    Returns tuples: (id, name, city, country, image_url, metadata, distance)
    Ordered by: has image → region match → distance
    """
    # Query analysis
    q_text = (query_text or "").strip().lower()
    keywords = _extract_keywords(q_text)
    region_countries = _detect_region(q_text)
    kw_expr, kw_params = _keyword_hit_sql_and_params(keywords)

    # --- CHANGED: A "region search" only happens if NO keywords are present ---
    is_region_search = bool(region_countries) and not bool(keywords)

    if is_region_search:
        # If a region is detected (and no other keywords), don't use vector distance.
        # Select 0.0 as distance so it's consistent.
        sql = (
            "SELECT id, name, city, country, image_url, metadata, "
            "0.0 AS distance "
            "FROM airports"
        )
        params = [] # Don't need the vector param
    else:
        # Original vector search logic
        dist = _distance_expr()
        sql = (
            "SELECT id, name, city, country, image_url, metadata, "
            f"{dist} AS distance "
            "FROM airports"
        )
        params = [_vec_text(vec)] # Start with vector param

    # Apply filters
    sql = _apply_filters(sql, filters, params)

    # Apply keywords as a STRICT FILTER (if they exist)
    if keywords:
        if "WHERE" in sql.upper():
            sql += f" AND ({kw_expr}) "
        else:
            sql += f" WHERE ({kw_expr}) "
        params.extend(kw_params)

    # Apply region detection (restrict by countries)
    if region_countries:
        region_clause = " OR ".join(["LOWER(country) LIKE LOWER(?)" for _ in region_countries])
        if "WHERE" in sql.upper():
            sql += f" AND ({region_clause})"
        else:
            sql += f" WHERE ({region_clause})"
        params.extend(region_countries)

    # --- CHANGED: Different ordering based on search type ---
    if is_region_search:
        # For region search, just sort by name
        sql += f"""
            ORDER BY
              (image_url IS NULL OR image_url='') ASC,
              name ASC
            LIMIT 1000
        """
    else:
        # For vector search, sort by distance
        sql += f"""
            ORDER BY
              (image_url IS NULL OR image_url='') ASC,
              distance ASC
            LIMIT 1000
        """
    
    # --- END CHANGED ---

    with get_conn() as conn, conn.cursor() as cur, time_block("db.search_airports"):
        cur.execute(sql, params)
        rows = cur.fetchall()

    return rows


def search_airlines_by_image(
    vec: List[float],
    k: int,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Tuple]:
    """Image-based airline logo similarity search."""
    params: List[Any] = []
    dist = _distance_expr()

    sql = (
        "SELECT id, name, iata, icao, logo_url, metadata, "
        f"{dist} AS distance "
        "FROM airlines"
    )
    sql = _apply_filters(sql, filters, params)
    sql += """
        ORDER BY
          (logo_url IS NULL OR logo_url='') ASC,
          distance ASC
        LIMIT 1000
    """

    params = [_vec_text(vec)] + params

    with get_conn() as conn, conn.cursor() as cur, time_block("db.search_airlines"):
        cur.execute(sql, params)
        rows = cur.fetchall()

    return rows

