from __future__ import annotations
import os
import mariadb
from contextlib import contextmanager

# Keep a single pool across the app
_pool = None
_cfg = None

def _cfg_from_env() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),              # 👈 default localhost
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "sky"),
        "password": os.getenv("DB_PASSWORD", "vision"),
        "database": os.getenv("DB_NAME", "skyvision"),
        "connect_timeout": 5,
        "autocommit": True,
    }

def init_pool():
    """Initialize a small connection pool using current env configuration."""
    global _pool, _cfg
    if _pool is not None:
        return
    _cfg = _cfg_from_env()

    # Allow disabling pool for debugging if needed
    use_pool = os.getenv("DB_USE_POOL", "1") != "0"
    if use_pool:
        _pool = mariadb.ConnectionPool(
            pool_name="skyvision",
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            **_cfg,
        )
    else:
        _pool = None  # fall back to direct connections

def raw_connection():
    """Return a raw connection (from pool if available, else direct)."""
    if _pool is None:
        # lazy-init if not yet initialized
        init_pool()

    if _pool is not None:
        return _pool.get_connection()
    # no pool path
    return mariadb.connect(**_cfg_from_env())

@contextmanager
def get_conn():
    """Context manager that yields a connection and always closes it."""
    conn = raw_connection()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass

def current_db_config_snapshot() -> dict:
    """Safe snapshot (no secrets) for health/debug endpoints."""
    c = _cfg or _cfg_from_env()
    return {
        "host": c.get("host"),
        "port": c.get("port"),
        "database": c.get("database"),
        "user": c.get("user"),
        "pool": _pool is not None,
    }
# --- add this small helper for backward compatibility ---
def ping() -> bool:
    """
    Lightweight DB ping used by health endpoints.
    Returns True if a simple SELECT works, else False.
    """
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False
