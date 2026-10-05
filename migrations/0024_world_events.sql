-- 0024_world_events.sql — W-1-1 (the living-world program's second cut):
-- the world's event tree and its minimal state projection, two tables.
--
-- Two tables land here, no seed row (a fresh world has an empty chronicle
-- and zero state facts; events enter only through elc.world.store's
-- record_event — the face that also settles the projection, atomically).
--
-- Authority: the W-1-1 adjudication chain (DEC-OPI-7e3744ee…17 R1–R9;
-- M0.1 AD-3R — the lore table stays the static lore's own table and the
-- living state lives here, two tables, not one; AD-2 — this cut carries no
-- model face: narration arrives as the caller's string). The column set is
-- the adjudication's own spelling, column for column.
--
-- Physical decisions (each minimal, the 0020/0023 conventions restated):
--   * ``world_event`` is append-only: the event log is never updated in
--     place — corrections are new events (the tree, not a mutable row).
--   * ``world_event.kind`` TEXT NOT NULL — a free word (the vocabulary is
--     W-1-2's adjudication, not this migration's); the store does not
--     constrain it and neither does the schema.
--   * ``world_event.narration`` TEXT NOT NULL — the caller's own narration
--     string (AD-2: this cut generates no prose).
--   * ``world_event.effects`` TEXT NOT NULL — the canonical JSON array of
--     ``[{"key": ..., "statement": ...}]`` objects, encoded/decoded by
--     elc.world.types' codec (strict: bad JSON / non-array / element
--     missing a key or carrying a non-string ⇒ value-semantics Err). An
--     empty array is a legal pure-narration event (zero settlement).
--   * ``world_event.occurred_at`` TEXT NOT NULL — ISO-8601, the event's own
--     time as the caller supplies it; no separate write-time column is
--     kept (the event carries its moment, the log does not re-stamp it).
--   * ``world_event.source`` TEXT NOT NULL — the origin word (who/what
--     produced the event; free text until a later cut registers words).
--   * ``world_state_fact.source_event_id`` REFERENCES world_event(event_id)
--     — every fact is settled BY one event; the projection is a reading of
--     the tree, never an independent write (record_event is the only
--     writer of either table).
--   * ``world_state_fact.status`` TEXT NOT NULL CHECK (status IN
--     ('CURRENT', 'SUPERSEDED')) — the minimal projection's two-word
--     lifecycle: the newest fact per (world_id, canonical_key) is CURRENT,
--     every older fact stays as SUPERSEDED history.
--   * NO UNIQUE on (world_id, canonical_key): several rows per key are the
--     design — the projection keeps its superseded history, and the
--     CURRENT read filters by status.
--   * One index — (world_id, canonical_key, status) — serves both the
--     CURRENT read and a key's history walk; nothing else is indexed (the
--     chronicle walks by its ORDER BY over a per-world slice).
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION equivalent
--     (RESTRICT posture) is this cut's whole deletion story — the same
--     posture 0023 spells; the deletion face stays W-1-3's registered cut.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_event (
    event_id    TEXT PRIMARY KEY,
    world_id    TEXT NOT NULL REFERENCES world(world_id),
    kind        TEXT NOT NULL,
    narration   TEXT NOT NULL,
    effects     TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    source      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS world_state_fact (
    fact_id         TEXT PRIMARY KEY,
    world_id        TEXT NOT NULL REFERENCES world(world_id),
    source_event_id TEXT NOT NULL REFERENCES world_event(event_id),
    canonical_key   TEXT NOT NULL,
    statement       TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('CURRENT', 'SUPERSEDED')),
    recorded_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_world_state_fact_key_status
    ON world_state_fact (world_id, canonical_key, status);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '24')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '24')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
