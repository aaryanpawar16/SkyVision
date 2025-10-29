from __future__ import annotations
from typing import Dict, List
from time import perf_counter
from contextlib import contextmanager
from threading import Lock
from collections import deque
import math

# Simple in-memory latency store per label (thread-safe).
# Keeps last N samples for quick stats (avg, p95).
_MAX_SAMPLES = 500
_store: Dict[str, deque] = {}
_lock = Lock()


def record_latency(label: str, seconds: float) -> None:
    with _lock:
        dq = _store.setdefault(label, deque(maxlen=_MAX_SAMPLES))
        dq.append(seconds)


def get_stats(label: str) -> Dict[str, float]:
    with _lock:
        dq = list(_store.get(label, ()))
    if not dq:
        return {"count": 0, "avg": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    arr = sorted(dq)
    count = len(arr)
    avg = sum(arr) / count
    p95_idx = max(0, math.ceil(0.95 * count) - 1)
    return {
        "count": float(count),
        "avg": avg,
        "p95": arr[p95_idx],
        "min": arr[0],
        "max": arr[-1],
    }


@contextmanager
def time_block(label: str):
    """
    Usage:
        with time_block("db.search"):
            run_query()
    """
    start = perf_counter()
    try:
        yield
    finally:
        record_latency(label, perf_counter() - start)
