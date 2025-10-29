# backend/app/routers/search.py
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import List, Optional, Any
import json
import base64
import numpy as np
import mariadb
import logging

from ..models.request import TextQuery, HybridTextQuery
from ..models.response import Hit, RankedResult
from ..embeddings import embed_text, embed_image_bytes
from ..queries import search_airports_by_text, search_airlines_by_image
from ..config import settings

router = APIRouter(prefix="/search", tags=["search"])
log = logging.getLogger(__name__)


def _as_json(val: Any) -> Optional[dict]:
    """Safely decode a DB JSON column into a Python dict."""
    if val is None or isinstance(val, dict):
        return val
    if isinstance(val, (bytes, bytearray)):
        try:
            return json.loads(val.decode("utf-8"))
        except Exception:
            return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return None
    try:
        return json.loads(json.dumps(val))
    except Exception:
        return None


def _validate_dim(vec: np.ndarray, where: str):
    """Ensure embedding length matches settings.EMBEDDING_DIM."""
    dim = int(settings.EMBEDDING_DIM)
    if vec.ndim != 1:
        raise HTTPException(status_code=400, detail=f"{where}: embedding must be 1-D, got shape {tuple(vec.shape)}")
    if vec.size != dim:
        raise HTTPException(
            status_code=400,
            detail=f"{where}: embedding dim {vec.size} != configured EMBEDDING_DIM {dim}. Check model/DB consistency.",
        )


@router.post("/text", response_model=RankedResult)
def search_text(body: TextQuery) -> RankedResult:
    """Text → Image airport search."""
    try:
        raw_vec = embed_text(body.query)
        vec = np.array(raw_vec, dtype=np.float32).ravel()
        _validate_dim(vec, "text")
        log.info("[/search/text] q=%r | dim=%d | k=%s | filters=%s", body.query, vec.size, body.k, body.filters)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Embedding error (text): {e}")

    try:
        rows = search_airports_by_text(
            vec.tolist(),
            body.k,
            body.filters,
            query_text=body.query,  # pass-through for keyword boosting
        )
    except mariadb.Error as db_err:
        log.exception("MariaDB error in search_text")
        raise HTTPException(status_code=500, detail=f"DB error: {db_err}")
    except Exception as e:
        log.exception("Unexpected error in search_text")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

    hits: List[Hit] = []
    for r in rows:
        hits.append(
            Hit(
                id=r[0],
                name=r[1],
                city=r[2],
                country=r[3],
                url=(r[4] or "").strip(),
                metadata=_as_json(r[5]),
                distance=float(r[6]),
            )
        )
    return RankedResult(count=len(hits), hits=hits)


@router.post("/image", response_model=RankedResult)
async def search_image(
    file: UploadFile = File(...),
    k: int = 12,
    has_logo: bool = Query(False),
) -> RankedResult:
    """Image → Image airline logo search."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")
    data = await file.read()

    try:
        raw_vec = embed_image_bytes(data)
        vec = np.array(raw_vec, dtype=np.float32).ravel()
        _validate_dim(vec, "image")
        log.info("[/search/image] file=%s | dim=%d | k=%s | has_logo=%s", file.filename, vec.size, k, has_logo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Embedding error (image): {e}")

    try:
        filters = {"has_logo": True} if has_logo else None
        rows = search_airlines_by_image(vec.tolist(), k, filters)
    except mariadb.Error as db_err:
        log.exception("MariaDB error in search_image")
        raise HTTPException(status_code=500, detail=f"DB error: {db_err}")
    except Exception as e:
        log.exception("Unexpected error in search_image")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

    hits: List[Hit] = []
    for r in rows:
        name = r[1]
        code = f" ({r[2] or ''}/{r[3] or ''})".strip()
        hits.append(
            Hit(
                id=r[0],
                name=f"{name}{code}",
                url=(r[4] or "").strip(),
                metadata=_as_json(r[5]),
                distance=float(r[6]),
            )
        )
    return RankedResult(count=len(hits), hits=hits)


@router.post("/hybrid", response_model=RankedResult)
def search_hybrid(body: HybridTextQuery) -> RankedResult:
    """
    Hybrid Search: Combine text semantics + optional image embedding + filters.
    Weights are normalized so they sum to 1 before combining vectors.
    """
    # 1) Text embedding
    try:
        t_raw = embed_text(body.query)
        t_vec = np.array(t_raw, dtype=np.float32).ravel()
        _validate_dim(t_vec, "hybrid.text")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text embedding error: {e}")

    # 2) Optional image embedding (base64)
    i_vec = None
    if getattr(body, "image_base64", None):
        try:
            img_bytes = base64.b64decode(body.image_base64)
            i_raw = embed_image_bytes(img_bytes)
            i_vec = np.array(i_raw, dtype=np.float32).ravel()
            _validate_dim(i_vec, "hybrid.image")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Image embedding error: {e}")

    # 3) Normalize weights and combine
    wt = float(getattr(body, "weight_text", 0.5))
    wi = float(getattr(body, "weight_image", 0.5))
    wt = max(0.0, min(1.0, wt))
    wi = max(0.0, min(1.0, wi))
    denom = max(wt + wi, 1e-9)
    wt, wi = wt / denom, wi / denom

    if i_vec is not None:
        if i_vec.shape != t_vec.shape:
            raise HTTPException(status_code=400, detail="Image/text embedding shape mismatch.")
        vec = wt * t_vec + wi * i_vec
    else:
        vec = t_vec

    log.info("[/search/hybrid] q=%r | dim=%d | k=%s | filters=%s | wt=%.3f wi=%.3f",
             body.query, vec.size, body.k, body.filters, wt, wi)

    # 4) DB search
    try:
        rows = search_airports_by_text(
            vec.tolist(),
            body.k,
            body.filters,
            query_text=body.query,
        )
    except mariadb.Error as db_err:
        log.exception("MariaDB error in search_hybrid")
        raise HTTPException(status_code=500, detail=f"DB error: {db_err}")
    except Exception as e:
        log.exception("Unexpected error in search_hybrid")
        raise HTTPException(status_code=500, detail=f"DB error during hybrid search: {e}")

    hits: List[Hit] = []
    for r in rows:
        hits.append(
            Hit(
                id=r[0],
                name=r[1],
                city=r[2],
                country=r[3],
                url=(r[4] or "").strip(),
                metadata=_as_json(r[5]),
                distance=float(r[6]),
            )
        )
    return RankedResult(count=len(hits), hits=hits)
