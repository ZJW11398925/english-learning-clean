-- 0032_actor_profile_world_fk.sql — V3-3R identity correction (the
-- external review's item 4; TASK-OPI-bab4da9f…61 /
-- VAL-OPI-bab4da9f…64; authorization: the external review's verdict,
-- relayed — DECISION_REGISTER v1.3.3).
--
-- One rebuild and nothing else: ``world_actor_profile`` is rebuilt
-- with the composite foreign key ``(actor_id, world_id) REFERENCES
-- world_actor(actor_id, world_id)`` — the actor-profile ownership
-- invariant becomes a storage fact: a profile filed under a world its
-- actor is not bound to refuses at the database's own surface, not
-- only through the store's pre-check. The store's
-- ``VALIDATION_FAILED`` human-words layer
-- (:mod:`elc.world.cast`'s ``seed_actor_profile``) stays — the
-- composite FK is the storage backstop, not its replacement. The
-- target key is migration 0023's own ``UNIQUE (actor_id, world_id)``
-- on ``world_actor`` (migrations/0023_world_identity.sql:66), and the
-- house precedent is 0023's ``world_conversation``, which has carried
-- the same composite FK since the world identity cut.
--
-- Data face, CHECK vocabulary and column order are unchanged: the
-- rebuilt table's eleven columns copy 0031's definition and order
-- exactly (the ``INSERT … SELECT *`` rides that order), the three
-- nullable columns' honest-undeclared posture and the three arc
-- texts' NOT NULL empty-string posture carry through, and the carried
-- rows are the rows 0031 landed (no back-fill, no legacy write). The
-- single-column world FK (``world_id → world(world_id)``) and the
-- composite FK coexist; the pre-0032 single-column actor FK
-- (``actor_id → world_actor(actor_id)``, 0031's own) is subsumed by
-- the composite one — every (actor_id, world_id) pair the composite
-- FK admits names the actor's own world, which is strictly stronger.
--
-- Safety of the rebuild sequence, stated as it runs: the migration
-- runner wraps each file in one ``BEGIN IMMEDIATE … COMMIT``
-- (``elc.platform.db.migrations``), and the production connection
-- profile — and every suite fixture — holds
-- ``PRAGMA foreign_keys = ON``. Under that posture the sequence is
-- safe: the ``INSERT … SELECT`` re-checks every carried row against
-- the new composite FK (the store's pre-check has kept the pairs
-- honest since 0031), the ``DROP TABLE`` touches a child table
-- nothing references (``world_actor_profile`` is a leaf — no table's
-- FK names it), and the ``RENAME`` fixes up no other table (nothing
-- references the rebuilt table either). 0031's
-- ``world_actor_profile`` definition stays in place above as the
-- historical layer; the live table's semantics are the rebuilt one
-- this file lands.
--
-- DATA_MODEL §26.1: migrations bump schema_version explicitly.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_actor_profile_rebuilt (
    actor_id     TEXT PRIMARY KEY,
    world_id     TEXT NOT NULL REFERENCES world(world_id),
    story_role   TEXT CHECK (story_role IS NULL OR story_role IN ('PROTAGONIST','MAJOR','SUPPORTING')),
    pov_eligible INTEGER CHECK (pov_eligible IS NULL OR pov_eligible IN (0, 1)),
    pov_weight   INTEGER CHECK (pov_weight IS NULL OR pov_weight >= 0),
    long_term_drive  TEXT NOT NULL,
    current_arc_seed TEXT NOT NULL,
    private_context  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    FOREIGN KEY (actor_id, world_id) REFERENCES world_actor(actor_id, world_id));

INSERT INTO world_actor_profile_rebuilt
    SELECT * FROM world_actor_profile;
DROP TABLE world_actor_profile;
ALTER TABLE world_actor_profile_rebuilt RENAME TO world_actor_profile;

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '32')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '32')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
