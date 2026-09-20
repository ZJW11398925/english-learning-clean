-- 0001_bootstrap.sql — Phase 0 app.db bootstrap (docs/IMPLEMENTATION_PLAN.md §17-02).
-- Frozen semantics live in docs/DATA_MODEL.md §26.1 (schema/runtime metadata) and
-- docs/RUNTIME_ARCHITECTURE.md §24 (runtime_epoch restart ownership boundary).
-- Domain tables are NOT created here: DATA_MODEL §27 leaves concrete column DDL to
-- later implementation phases; Phase 0 only establishes infra metadata.

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- runtime_epoch: every process start opens a new epoch; rows only grow.
-- TurnRecord/GenerationAction style owner_epoch values are compared against
-- max(epoch) by the startup fence (src/elc/platform/db/epoch.py).
CREATE TABLE IF NOT EXISTS runtime_epoch (
    epoch     INTEGER PRIMARY KEY,
    opened_at TEXT NOT NULL
);

INSERT INTO schema_meta (key, value)
VALUES ('schema_version', '1'), ('runtime_schema_version', '1')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
