-- Optional later path: Aurora PostgreSQL + pgvector
-- Not provisioned during the $0 hackathon window.
-- Same 5-dimension embeddings written to DynamoDB can be upserted here.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS thermoguard_event_vectors (
  event_id TEXT PRIMARY KEY,
  risk_tier TEXT NOT NULL,
  methodology_version TEXT NOT NULL,
  embedding vector(5) NOT NULL
);

CREATE INDEX IF NOT EXISTS thermoguard_event_vectors_hnsw
  ON thermoguard_event_vectors
  USING hnsw (embedding vector_cosine_ops);
