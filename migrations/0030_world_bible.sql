-- 0030_world_bible.sql — V3-2 (the World Bible, the Narrative V3
-- program's second cut; TASK-OPI-bab4da9f…29 / VAL-OPI-bab4da9f…33 —
-- the contract was already canonical: DATA_MODEL §26.2.1's
-- ``world_bible_revision`` entry, DOMAIN_MODEL §20.3-6 and N-INV-006,
-- the design supplement §五's authority direction, IMPLEMENTATION_PLAN
-- §20's V3-2 row).
--
-- One table and one partial index, and nothing else: this cut freezes
-- the instance-level World Bible's authoritative face — the versioned
-- row a world's setting, rules and history live in — plus its read
-- primitives (:mod:`elc.world.bible`). The projection/adapter toward
-- the legacy lore view and the prompt reading face are later cuts';
-- nothing here projects, nothing here reads for a prompt.
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1 — the entity contract, column for column:
--     ``world_id, revision, parent_revision?`` plus the fourteen
--     semantic fields (``premise, genre, tone, calendar, physics,
--     magic_rules, geography, society, politics, technology, religion,
--     history, hard_rules, narrative_preferences``) and
--     ``status: CURRENT | SUPERSEDED`` (append-only versioning; rows
--     are never deleted or rewritten — a revision supersedes, it does
--     not edit). The contract's own note is this cut's law: the
--     template/Package seeds the first revision at creation time only
--     (``parent_revision`` records the source; the store mints the
--     seed as revision 1 with a NULL parent), and a template's later
--     updates never rewrite this table (N-INV-006, V3-2 implements).
--   * DOMAIN_MODEL §20.3-6 / N-INV-006 — the template is not the
--     instance Bible: a world template or package only seeds at
--     creation; the instance's ``world_bible_revision`` is the sole
--     authority; a template's later update must not silently rewrite
--     an existing world (an update is an explicit fork/migrate
--     decision — reserved here, decided by a later cut).
--   * The design supplement (2026-10-12-narrative-v3-paradigm-shift.md
--     §五 / §9.3) — the authority direction runs **World Bible →
--     projection/adapter → legacy lore view**, never the reverse.
--     ``world_lore_fact`` stays legacy: it is not the per-world Bible
--     storage, and this cut builds no projection — one authority, no
--     double bookkeeping (IMPLEMENTATION_PLAN §20's V3-2 gate).
--   * The single-authority shape is race-free at the storage level:
--     the partial UNIQUE index below admits at most one ``CURRENT``
--     row per world (DATA §26.2.1's single-authority semantics, and
--     the race-free form the 0029 narrative store's docstring
--     registered as the commit cuts' obligation — landing it here
--     where the invariant is this table's own).
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION
--     equivalent (RESTRICT posture) is this cut's whole deletion
--     story — the same posture 0023–0025, 0028 and 0029 spell; the
--     table is registered keep-side in GLOBAL_CONTENT_TABLES (this
--     cut): its FK chain (``world_id`` → ``world``) is keep-side at
--     every link, so no sweep can be refused through it.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_bible_revision (
    bible_revision_id TEXT PRIMARY KEY,
    world_id     TEXT NOT NULL REFERENCES world(world_id),
    revision     INTEGER NOT NULL CHECK (revision > 0),
    parent_revision INTEGER CHECK (parent_revision IS NULL OR parent_revision < revision),
    status       TEXT NOT NULL CHECK (status IN ('CURRENT','SUPERSEDED')),
    premise TEXT NOT NULL, genre TEXT NOT NULL, tone TEXT NOT NULL,
    calendar TEXT NOT NULL, physics TEXT NOT NULL, magic_rules TEXT NOT NULL,
    geography TEXT NOT NULL, society TEXT NOT NULL, politics TEXT NOT NULL,
    technology TEXT NOT NULL, religion TEXT NOT NULL, history TEXT NOT NULL,
    hard_rules TEXT NOT NULL, narrative_preferences TEXT NOT NULL,
    created_at   TEXT NOT NULL, updated_at TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (world_id, revision));

-- The single-CURRENT invariant as a storage fact, not a store-side
-- convention: one world, at most one row whose ``status`` is
-- ``CURRENT`` (DATA §26.2.1's single-authority semantics; the
-- race-free form the 0029 store's registered obligation names). The
-- supersede-then-insert order inside the revision transaction is what
-- keeps the index satisfiable; the index is what keeps it honest.
CREATE UNIQUE INDEX IF NOT EXISTS ux_world_bible_revision_current
    ON world_bible_revision (world_id) WHERE status = 'CURRENT';

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '30')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '30')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
