-- 0029_narrative_v3_foundations.sql — V3-1 (Narrative foundations, the
-- Narrative V3 paradigm shift's first code cut; DEC-OPI-bab4da9f…11
-- landed the contract, DEC-OPI-bab4da9f…16 is the disposition that
-- released the migration and the code).
--
-- Four tables + one column, and nothing else: this cut freezes the
-- *foundations* only — the story_tick primitive, the Chapter / Scene
-- lifecycle types, and the Plan/Canon boundary as physical tables.
-- The commit transactions (NCP-1..NCP-4), the passage/gate/action
-- faces and the planning engines are the later cuts' (V3-2..V3-7);
-- nothing here writes canon.
--
-- Authority: the four canonical V3 sections written design-first in
-- the same decision — DOMAIN_MODEL §20 (Narrative V3 Domain: the
-- authority detail and the seven hard boundaries), STATE_MACHINES
-- §21–§27 (the Chapter / Scene / User Gate / Plan Revision lifecycles,
-- the two commit transactions, the story_tick rules, the invalid
-- transitions), DATA_MODEL §26.2 (the entity contract, the time-field
-- law, the idempotency keys) and RUNTIME_ARCHITECTURE §27–§30 (the V3
-- pipeline, the commit points, the recovery scan, N-R-INV-001..008).
-- The DDL below is the contract's own spelling, column for column; the
-- disposition's L1 three corrections (``CHECK (state_version > 0)``,
-- the double stamp at the tail, and the PLAN row's ``updated_at`` +
-- ``state_version``) are baked in.
--
--   * ``world.current_tick`` — the story_tick column (ALTER on the
--     existing table): INTEGER NOT NULL DEFAULT 0. Single-writer law
--     (N-INV-007 / N-R-INV-005): the actual tick moves only inside a
--     commit transaction, monotone non-decreasing; V3-1 ships only the
--     column and the read/advance primitives
--     (:mod:`elc.world.time`) — no commit transaction exists yet, so
--     nothing in this cut advances it.
--   * ``world_chapter`` — the chapter's canon-face progress row
--     (DATA §26.2.1): ``chapter_id`` TEXT PRIMARY KEY, ``world_id`` NOT
--     NULL REFERENCES world(world_id), ``chapter_index`` NOT NULL with
--     UNIQUE (world_id, chapter_index) (the idempotency key set, DATA
--     §26.2.4 — the chapter order is monotone +1), ``status`` with the
--     §21 word list exactly ('PLANNED','ACTIVE','SETTLING','CLOSED'),
--     ``opened_at_tick`` / ``closed_at_tick`` nullable (the canon-face
--     time fields; this cut has no commit transaction — the lifecycle
--     flip faces write them from the caller's value, which in the full
--     pipeline rides from the current actual tick; the tick's *advance*
--     stays commit-only, §26),
--     ``created_at`` / ``updated_at`` the caller's ISO-8601 bookkeeping
--     stamps, ``state_version`` NOT NULL CHECK (state_version > 0) the
--     row's CAS counter (the house store discipline).
--   * ``world_chapter_plan`` — the chapter's PLAN face, append-only
--     versioned (DATA §26.2.1 + STATE §24): ``chapter_plan_id`` TEXT
--     PRIMARY KEY, ``chapter_id`` NOT NULL REFERENCES
--     world_chapter(chapter_id), ``plan_revision`` NOT NULL with
--     UNIQUE (chapter_id, plan_revision) (§26.2.4), ``status`` with the
--     §24 word list exactly ('PROPOSED','ADOPTED','SUPERSEDED',
--     'REJECTED'), the Blueprint's semantic fields verbatim — ``goal``,
--     ``dramatic_question``, ``planned_start_tick`` / 
--     ``planned_end_tick`` (Plan-face time, the planned_ prefix law,
--     DATA §26.2.2), the soft-expectation set ``closing_pressure`` /
--     ``desired_development`` / ``soft_outcomes`` /
--     ``chapter_questions_to_advance`` (the V3-0R wording law: never a
--     postcondition), ``scenes`` (the scene table, JSON), and the L1
--     bookkeeping: ``created_at`` / ``updated_at`` NOT NULL +
--     ``state_version`` NOT NULL CHECK (state_version > 0). PLAN rows
--     are never canon (N-INV-001 / N-R-INV-007) — the status word is
--     the boundary marker the types carry.
--   * ``world_scene`` — the scene's canon-face progress row
--     (DATA §26.2.1): ``scene_id`` TEXT PRIMARY KEY, ``chapter_id``
--     NOT NULL REFERENCES world_chapter(chapter_id), ``scene_index``
--     NOT NULL with UNIQUE (chapter_id, scene_index) (§26.2.4),
--     ``status`` with the §22 word list exactly ('PLANNED','ACTIVE',
--     'COMMITTED','CLOSED','DISCARDED'), ``actual_start_tick`` /
--     ``actual_end_tick`` nullable canon-time fields, the bookkeeping
--     pair and the CAS counter as above.
--   * ``world_scene_dossier`` — the scene's PLAN face, append-only
--     versioned (DATA §26.2.1 + STATE §24): ``dossier_id`` TEXT
--     PRIMARY KEY, ``scene_id`` NOT NULL REFERENCES
--     world_scene(scene_id), ``dossier_revision`` NOT NULL with
--     UNIQUE (scene_id, dossier_revision) (§26.2.4), ``status`` with
--     the §24 word list, the Dossier's semantic fields verbatim —
--     ``pov_actor_id`` (one POV per scene), ``participants`` (the
--     namespace cast ids ∪ {player_character_id} ∪ residents), 
--     ``place``, ``planned_start_tick``, the POV-discipline pair
--     ``revealable`` / ``must_hide``, ``entry_goals``,
--     ``exit_condition``, ``elasticity`` — plus the bookkeeping pair
--     and the CAS counter.
--   * ``world_chapter_plan`` carries ``chapter_id`` NOT NULL and
--     ``world_scene_dossier`` carries ``scene_id`` NOT NULL as real
--     foreign keys: the PLAN face hangs off the canon-face progress
--     row it plans (replanning writes new revisions, never rewrites —
--     STATE §24's append-only law).
--   * No index anywhere: per-world chapter slices and per-chapter
--     scene slices are single digits in the MVP, a scan is the honest
--     cost (0028's posture).
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION
--     equivalent (RESTRICT posture) is this cut's whole deletion
--     story — the same posture 0023–0025 and 0028 spell; the four
--     tables are registered keep-side in GLOBAL_CONTENT_TABLES
--     (L5, same cut).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
ALTER TABLE world ADD COLUMN current_tick INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS world_chapter (
    chapter_id   TEXT PRIMARY KEY,
    world_id     TEXT NOT NULL REFERENCES world(world_id),
    chapter_index INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PLANNED','ACTIVE','SETTLING','CLOSED')),
    opened_at_tick  INTEGER,
    closed_at_tick  INTEGER,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (world_id, chapter_index));

CREATE TABLE IF NOT EXISTS world_chapter_plan (
    chapter_plan_id TEXT PRIMARY KEY,
    chapter_id   TEXT NOT NULL REFERENCES world_chapter(chapter_id),
    plan_revision INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PROPOSED','ADOPTED','SUPERSEDED','REJECTED')),
    goal TEXT NOT NULL, dramatic_question TEXT NOT NULL,
    planned_start_tick INTEGER NOT NULL, planned_end_tick INTEGER NOT NULL,
    closing_pressure TEXT NOT NULL, desired_development TEXT NOT NULL,
    soft_outcomes TEXT NOT NULL, chapter_questions_to_advance TEXT NOT NULL,
    scenes TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (chapter_id, plan_revision));

CREATE TABLE IF NOT EXISTS world_scene (
    scene_id     TEXT PRIMARY KEY,
    chapter_id   TEXT NOT NULL REFERENCES world_chapter(chapter_id),
    scene_index  INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PLANNED','ACTIVE','COMMITTED','CLOSED','DISCARDED')),
    actual_start_tick INTEGER, actual_end_tick INTEGER,
    created_at   TEXT NOT NULL, updated_at TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (chapter_id, scene_index));

CREATE TABLE IF NOT EXISTS world_scene_dossier (
    dossier_id   TEXT PRIMARY KEY,
    scene_id     TEXT NOT NULL REFERENCES world_scene(scene_id),
    dossier_revision INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PROPOSED','ADOPTED','SUPERSEDED','REJECTED')),
    pov_actor_id TEXT NOT NULL, participants TEXT NOT NULL, place TEXT NOT NULL,
    planned_start_tick INTEGER NOT NULL,
    revealable TEXT NOT NULL, must_hide TEXT NOT NULL, entry_goals TEXT NOT NULL,
    exit_condition TEXT NOT NULL, elasticity TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (scene_id, dossier_revision));

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '29')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '29')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
