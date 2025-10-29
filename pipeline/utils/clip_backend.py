from __future__ import annotations
from typing import Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from PIL import Image

_model_cache: dict[str, SentenceTransformer] = {}

def get_model(model_name: str) -> SentenceTransformer:
    # trust_remote_code allows some community models; safe here.
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name, trust_remote_code=True)
    return _model_cache[model_name]

def _probe_dim(model: SentenceTransformer) -> int:
    """
    Robustly determine embedding dimension even for multimodal models where
    get_sentence_embedding_dimension() may return None.
    """
    # 1) Try the official API
    try:
        got: Optional[int] = model.get_sentence_embedding_dimension()
        if isinstance(got, int) and got > 0:
            return got
    except Exception:
        pass

    # 2) Probe with a text embedding
    try:
        vec = model.encode(["dimension probe"], normalize_embeddings=True, convert_to_numpy=True)
        if isinstance(vec, np.ndarray):
            return int(vec.shape[-1])
        if isinstance(vec, list) and len(vec) and hasattr(vec[0], "shape"):
            return int(vec[0].shape[-1])
    except Exception:
        pass

    # 3) (Very rare) probe with a 1x1 RGB image if text path failed
    try:
        dummy = Image.new("RGB", (1, 1), color=(0, 0, 0))
        vec = model.encode([dummy], normalize_embeddings=True, convert_to_numpy=True)
        if isinstance(vec, np.ndarray):
            return int(vec.shape[-1])
        if isinstance(vec, list) and len(vec) and hasattr(vec[0], "shape"):
            return int(vec[0].shape[-1])
    except Exception:
        pass

    raise RuntimeError("Could not determine model embedding dimension via probe.")

def ensure_dim(model: SentenceTransformer, expected: int) -> int:
    got = _probe_dim(model)
    if got != expected:
        # If you intentionally changed model/dim, adjust:
        #  - db/init/10_schema.sql -> VECTOR(<got>)
        #  - backend/app/config.py  -> EMBEDDING_DIM=<got>
        #  - your embed command     -> --dim <got>
        raise ValueError(f"Model dim {got} != expected {expected}. Align EMBEDDING_DIM/DB VECTOR(N).")
    return got
