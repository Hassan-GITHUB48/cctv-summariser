-- Idempotent: runs on first container start and again from pipeline.db.init_schema().

CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'ingesting', 'keyframes', 'detecting', 'reporting', 'done', 'failed')),
    error       TEXT,
    meta        JSONB,              -- ffprobe metadata of the source video
    sampling    JSONB,              -- sampling mode and parameters
    timings     JSONB,              -- per-stage seconds
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Added in Phase 3; ALTER keeps existing databases in sync.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS failed_stage TEXT;

CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    job_id       TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    timestamp_s  DOUBLE PRECISION NOT NULL,
    frame_index  INTEGER NOT NULL,
    label        TEXT NOT NULL,
    confidence   REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    bbox         INTEGER[4] NOT NULL,  -- x1, y1, x2, y2
    frame_path   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_job_time_idx ON events (job_id, timestamp_s);

CREATE TABLE IF NOT EXISTS reports (
    job_id      TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    incidents   JSONB NOT NULL,     -- validated list of incidents from the LLM
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
