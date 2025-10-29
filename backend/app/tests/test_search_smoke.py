from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("service") == "skyvision-backend"
    assert "ok" in j


def test_search_text_smoke(monkeypatch):
    # --- Arrange: monkeypatch embeddings + DB search ---
    from app import embeddings as _emb
    from app import queries as _queries

    def fake_embed_text(q: str):
        # Return a deterministic 3-dim vector; router only calls .tolist()
        import numpy as np
        return np.array([0.1, 0.2, 0.3], dtype="float32")

    def fake_search_airports_by_text(vec, k, filters=None):
        # Mimic DB rows: (id, name, city, country, image_url, metadata, distance)
        return [
            (1, "Test Airport", "Test City", "Testland", "https://img/test.jpg", {"style": "glass"}, 0.05),
            (2, "Demo Field", "Demo City", "Demostan", None, {}, 0.09),
        ][:k]

    monkeypatch.setattr(_emb, "embed_text", fake_embed_text)
    monkeypatch.setattr(_queries, "search_airports_by_text", fake_search_airports_by_text)

    # --- Act ---
    r = client.post("/search/text", json={"query": "airports like changi", "k": 2})

    # --- Assert ---
    assert r.status_code == 200
    j = r.json()
    assert j["count"] == 2
    assert isinstance(j["hits"], list)
    assert {"id", "name", "distance"}.issubset(j["hits"][0].keys())
