# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):
    """
    Centralized configuration for the SkyVision backend.
    Loads values automatically from environment variables or .env file.
    """

    # ---------- Database ----------
    DATABASE_HOST: str = "db"
    DATABASE_PORT: int = 3306
    DATABASE_USER: str = "sky"
    DATABASE_PASSWORD: str = "vision"
    DATABASE_NAME: str = "skyvision"

    DB_POOL_MIN: int = 1
    DB_POOL_MAX: int = 10
    DB_CONNECT_TIMEOUT: int = 5

    # ---------- Embeddings ----------
    EMBEDDING_MODEL: str = "clip-ViT-B-32"  # e.g., OpenCLIP or Sentence-Transformer
    EMBEDDING_DIM: int = 512  # must match your MariaDB VECTOR(dim) column

    # ---------- Vector Similarity ----------
    # ✅ FIX: Use the correct MariaDB function name
    VECTOR_DISTANCE_FN: str = "VEC_DISTANCE_COSINE"
    VECTOR_ORDER: Literal["ASC", "DESC"] = "ASC"  # ASC for distance, DESC for similarity

    # ---------- CORS ----------
    CORS_ALLOW_ORIGINS: str = "*"  # or comma-separated list of allowed origins

    # ---------- URLs (Optional, used by frontend / scripts) ----------
    API_URL: Optional[str] = None  # used for embed scripts or hybrid pipeline
    MEDIA_BASE_URL: Optional[str] = None  # base URL for /media files
    PUBLIC_BASE_URL: Optional[str] = None  # for static media references

    # ---------- Model Config ----------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # 👈 allows extra env vars like MEDIA_BASE_URL, API_URL, etc.
    )


# Instantiate global settings
settings = Settings()

# ---------- Safety Check ----------
if settings.EMBEDDING_DIM not in (256, 512, 768, 1024):
    print(f"[warn] ⚠️ EMBEDDING_DIM={settings.EMBEDDING_DIM} looks unusual — ensure it matches DB schema.")

if not settings.VECTOR_DISTANCE_FN.startswith("VEC_"):
    print(f"[warn] ⚠️ VECTOR_DISTANCE_FN={settings.VECTOR_DISTANCE_FN} may be invalid for MariaDB Vector — expected 'VEC_DISTANCE_COSINE'.")

