-- 0027_chronicle_attribution.sql — C1-a (the chronicle attribution
-- foundation, the outer review's HIGH-1/P16 common ground):
-- the world event gains its who and its run.
--
-- Two columns land on ``world_event``, no new table, no seed row (the
-- chronicle is append-only history; nothing is rewritten here).
--
-- Authority: the C1-a adjudication (DEC-OPI-41a4df20…55 R1–R7). The
-- columns are the adjudication's own spelling, column for column:
--   * ``participants`` TEXT NOT NULL DEFAULT '[]' — the canonical JSON
--     array of the cast members the event is about (the chronicle's
--     who), encoded/decoded by elc.world.types' strict codec; ``'[]'``
--     is the honest default (an event about nobody in particular).
--   * ``run_id`` TEXT NULL — the world run the event belongs to (the
--     engine's and the generated step's writes carry their own run's
--     id; the wr-8R P16 barrier's key). Deliberately NO foreign key,
--     the same posture ``world_run.trigger_turn_id`` spells: the event
--     must not pin a run row's lifetime beyond what the tree already
--     carries in its derived ids.
--
-- 存量行诚实留空: existing rows answer the DEFAULT — ``'[]'`` and
-- NULL. No back-fill, no inference: a pre-0027 row simply does not
-- know who it was about or which run it rode (the ids it carries
-- already encode the run, and re-deriving is this migration's
-- neighbour cut's question, never a silent rewrite here).
--
-- Physical decisions (the 0024 conventions restated):
--   * The write face stays exactly one —
--     :meth:`elc.world.store.SqliteWorldStore.record_event` (plus the
--     interaction face this cut adds beside it); append-only law
--     untouched.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
ALTER TABLE world_event ADD COLUMN participants TEXT NOT NULL DEFAULT '[]';

ALTER TABLE world_event ADD COLUMN run_id TEXT NULL;

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '27')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '27')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
