USE skyvision;

-- Vector indexes (HNSW). One vector index per table is recommended.
-- DISTANCE=cosine aligns with normalized CLIP embeddings and the app's VEC_DISTANCE_COSINE usage.

-- Airports
ALTER TABLE airports
  ADD VECTOR INDEX vidx_airports_embedding (embedding) DISTANCE=cosine;

-- Airlines
ALTER TABLE airlines
  ADD VECTOR INDEX vidx_airlines_embedding (embedding) DISTANCE=cosine;
