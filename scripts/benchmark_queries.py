#!/usr/bin/env python3
"""
Benchmark vector queries against MariaDB and/or the FastAPI backend.

Usage examples:
  python scripts/benchmark_queries.py --mode db --host localhost --query "airports like changi" --runs 50
  python scripts/benchmark_queries.py --mode api --api_url http://localhost:8000 --query "airports like changi" --runs 50
"""
from __future__ import annotations
import argparse, json, time, statistics
from typing import List, Dict, Any

def bench_db(host: str, port: int, user: str, password: str, db: str, qvec: List[float], k: int) -> float:
    import mariadb
    conn = mariadb.connect(host=host, port=port, user=user, password=password, database=db, autocommit=True)
    try:
        sql = """
        SELECT id, name, city, country,
               VECTOR_COSINE_DISTANCE(embedding, ?) AS distance
        FROM airports
        ORDER BY distance ASC
        LIMIT ?
        """
        start = time.perf_counter()
        cur = conn.cursor()
        cur.execute(sql, [qvec, k])
        _ = cur.fetchall()
        cur.close()
        return time.perf_counter() - start
    finally:
        conn.close()

def bench_api(api_url: str, query: str, k: int) -> float:
    import requests
    payload = {"query": query, "k": k}
    start = time.perf_counter()
    r = requests.post(f"{api_url}/search/text", json=payload, timeout=120)
    r.raise_for_status()
    _ = r.json()
    return time.perf_counter() - start

def text_to_unit_vec(query: str, model_name: str) -> List[float]:
    # Use same model as backend to approximate query embedding for DB-mode benchmarks.
    from sentence_transformers import SentenceTransformer
    import numpy as np
    model = SentenceTransformer(model_name)
    vec = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0].astype("float32")
    return vec.tolist()

def summarize(samples: List[float]) -> Dict[str, float]:
    samples_sorted = sorted(samples)
    n = len(samples_sorted)
    p95 = samples_sorted[max(0, int(0.95 * n) - 1)]
    return {
        "n": n,
        "avg_ms": statistics.mean(samples) * 1000.0,
        "p50_ms": statistics.median(samples) * 1000.0,
        "p95_ms": p95 * 1000.0,
        "min_ms": samples_sorted[0] * 1000.0,
        "max_ms": samples_sorted[-1] * 1000.0,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["db","api"], default="api")
    p.add_argument("--runs", type=int, default=30)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--k", type=int, default=12)
    p.add_argument("--query", default="airports like singapore changi with indoor gardens")
    # DB
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=3306)
    p.add_argument("--user", default="sky")
    p.add_argument("--password", default="vision")
    p.add_argument("--db", default="skyvision")
    p.add_argument("--model_name", default="clip-ViT-B-32")
    # API
    p.add_argument("--api_url", default="http://localhost:8000")
    args = p.parse_args()

    times: List[float] = []

    if args.mode == "db":
        qvec = text_to_unit_vec(args.query, args.model_name)
        # warmup
        for _ in range(args.warmup):
            _ = bench_db(args.host, args.port, args.user, args.password, args.db, qvec, args.k)
        # measure
        for _ in range(args.runs):
            t = bench_db(args.host, args.port, args.user, args.password, args.db, qvec, args.k)
            times.append(t)
    else:
        # warmup
        for _ in range(args.warmup):
            _ = bench_api(args.api_url, args.query, args.k)
        # measure
        for _ in range(args.runs):
            t = bench_api(args.api_url, args.query, args.k)
            times.append(t)

    print(json.dumps(summarize(times), indent=2))

if __name__ == "__main__":
    main()
