-- 0025_world_runs.sql — W-1-2 (the living-world program's third cut):
-- the world run, one durable row per advance of the engine (AD-6).
--
-- One table lands here, no seed row (a fresh world has zero runs; runs
-- enter only through elc.world.store's run face, and the deterministic
-- engine — elc.world.engine — is the only caller that moves them).
--
-- Authority: the W-1-2 adjudication chain (DEC-OPI-7e3744ee…26 R1–R10)
-- and the living-world spec §4.2 v2.1
-- (docs/design/2026-10-05-living-world-spec.md): a World Run is one full
-- advance of the world, started by the user's reply (the only run
-- starter), pausing at NOTICE checkpoints and terminating at the
-- RESPONSE stop; M0.1 AD-6 — the run is durable so a restart does not
-- re-roll the dice (seed and cursor ride the row; the sequence replays
-- from (seed, cursor), never re-authored).
--
-- Physical decisions (each minimal, the 0023/0024 conventions restated):
--   * ``run_id`` TEXT PRIMARY KEY — the run's identity; the chronicle
--     events inside the run derive their ids as ``<run_id>:<cursor>``
--     (deterministic per cycle).
--   * ``world_id`` TEXT NOT NULL REFERENCES world(world_id) — a run
--     belongs to exactly one world.
--   * ``trigger_turn_id`` TEXT NULL — the user reply that wound the
--     spring, when it is known. Deliberately NO foreign key: the turn
--     lives in migration 0002's conversation tables and the run must not
--     pin a conversation's lifetime (Revisit W-1-3, the deletion cut).
--   * ``seed`` INTEGER NOT NULL — the run's dice. Every cycle's draw is
--     seeded from (seed, cursor); the same seed replays the same run
--     (AD-6: 跨重启不重新撰骰).
--   * ``status`` TEXT NOT NULL CHECK (status IN ('AT_CHECKPOINT',
--     'TERMINAL')) — the two-word run lifecycle the spec spells: paused
--     at a checkpoint, or terminated at the RESPONSE stop. ``create_run``
--     starts a run at AT_CHECKPOINT — creation is the zeroth checkpoint.
--   * ``checkpoint_kind`` TEXT NOT NULL CHECK (checkpoint_kind IN
--     ('NOTICE', 'RESPONSE')) — the kind of stop the run sits at.
--     DIRECTION is deliberately NOT in the vocabulary: W-2-2 opens it.
--   * ``cursor`` INTEGER NOT NULL CHECK (cursor >= 0) — the cycle
--     counter: creation is 0 (the zeroth checkpoint), each completed
--     cycle advances it; the per-cycle PRNG is (seed, cursor).
--   * ``state_version`` INTEGER NOT NULL CHECK (state_version > 0) —
--     bumped on every run write; NOT a canonical version spelling (the
--     registry entry carries no version_field for this reason).
--   * ``created_at`` / ``updated_at`` TEXT NOT NULL — ISO-8601 stamps
--     the caller supplies; no hidden clock anywhere in this cut.
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION equivalent
--     (RESTRICT posture) is this cut's whole deletion story — the same
--     posture 0023/0024 spell; the deletion face stays W-1-3's cut.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_run (
    run_id          TEXT PRIMARY KEY,
    world_id        TEXT NOT NULL REFERENCES world(world_id),
    trigger_turn_id TEXT,
    seed            INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('AT_CHECKPOINT', 'TERMINAL')),
    checkpoint_kind TEXT NOT NULL CHECK (checkpoint_kind IN ('NOTICE', 'RESPONSE')),
    "cursor"        INTEGER NOT NULL CHECK ("cursor" >= 0),
    state_version   INTEGER NOT NULL CHECK (state_version > 0),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '25')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '25')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
