from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from PIL import Image
from io import BytesIO
from .config import settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # SentenceTransformer auto-selects device (CPU/GPU)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def embed_text(text: str) -> np.ndarray:
    model = _get_model()
    vec = model.encode([text], normalize_embeddings=True)
    vec = vec[0]
    # Ensure expected dimension
    if vec.shape[0] != settings.EMBEDDING_DIM:
        raise ValueError(
            f"Text embedding dim {vec.shape[0]} != configured EMBEDDING_DIM {settings.EMBEDDING_DIM}"
        )
    return vec.astype(np.float32)


def embed_image_bytes(data: bytes) -> np.ndarray:
    model = _get_model()
    img = Image.open(BytesIO(data)).convert("RGB")
    vec = model.encode([img], normalize_embeddings=True)
    vec = vec[0]
    if vec.shape[0] != settings.EMBEDDING_DIM:
        raise ValueError(
            f"Image embedding dim {vec.shape[0]} != configured EMBEDDING_DIM {settings.EMBEDDING_DIM}"
        )
    return vec.astype(np.float32)


def to_db_vector_param(vec: np.ndarray) -> List[float]:
    """
    MariaDB Python connector will map Python list[float] to a vector param
    for VECTOR(N) columns (on supported versions). Keep as plain list.
    """
    return vec.tolist()
