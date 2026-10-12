-- 0033_segment_commit.sql — V3-5 (Scene + Dossier + POV Writer +
-- narrative_passage + SEGMENT COMMIT, the Narrative V3 program's fifth
-- cut; TASK-OPI-be7b094f…34 / VAL-OPI-be7b094f…36; the opening ruling
-- DEC-OPI-be7b094f…32, DECISION_REGISTER v1.4.0).
--
-- Three tables and nothing else: this cut lands the physical forms the
-- contract already froze — the segment's prose (CANON), the reader
-- exposure record (deliberately decoupled), and the explicit lineage
-- face that attributes V3 events to story time. The commit transaction
-- itself lives in :mod:`elc.world.settlement` (NCP-3's one short
-- atomic group); no planning engine, no LLM writer face and no actor
-- memory land here.
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1 — the entity contract, column for column:
--     ``narrative_passage`` (``passage_id, scene_id, segment_seq, body,
--     language, outcome_ref?, created_at_tick``), ``reader_exposure``
--     (``exposure_id, passage_id, reader_id, exposed_at``) and the
--     segment-commit lineage row the "V3-5 落表形" block freezes
--     (``commit_id`` derived ``f"sg:{scene_id}:{segment_seq:04d}"`` /
--     ``kind`` CHECK 'SEGMENT' / ``passage_id`` / ``actual_start_tick``
--     / ``actual_end_tick`` / ``event_id``).
--   * STATE_MACHINES §25 (the SEGMENT COMMIT atomic group: passage +
--     event + state settlement + tick advance; ``segment_key =
--     (scene_id, segment_seq)`` as the idempotency key) and §22 (SCENE
--     COMMIT = the scene's last SEGMENT COMMIT's alias — the flip and
--     the commit land in the same transaction there, not here).
--   * RUNTIME_ARCHITECTURE §28 (NCP-3) / §29 (the recovery scan) /
--     §30 (N-R-INV-004/005: all-or-nothing, and the actual tick moves
--     only inside a commit transaction).
--   * DOMAIN_MODEL §20.3-2/§20.3-7 + N-INV-005: ``reader_exposure``
--     references the passage and writes no actor memory — the
--     exposure face is **not** in the NCP-3 atomic group (the review's
--     item 2: passage commit ≠ the user has seen it).
--
--   * ``narrative_passage`` — the segment's prose, the CANON face's
--     immutable row (N-INV-003: a committed passage is never rewritten;
--     corrections arrive as later segments). ``passage_id`` TEXT
--     PRIMARY KEY, derived ``f"{scene_id}-p{segment_seq:04d}"`` (the
--     derivation serves idempotent replay only — narrative time
--     attribution never rides an id's naming, §26.2.2's lineage
--     discipline), ``scene_id`` NOT NULL REFERENCES
--     world_scene(scene_id), ``segment_seq`` NOT NULL with
--     **UNIQUE (scene_id, segment_seq)** (§26.2.4's idempotency key:
--     a replay of the same segment_key is a no-op), ``body`` /
--     ``language`` NOT NULL, ``outcome_ref`` NULL (V3-6 on: it
--     references an already-committed action outcome; the Writer only
--     renders), ``created_at_tick`` NOT NULL (integer story tick = the
--     SEGMENT COMMIT's ``actual_end_tick``; the time-field law
--     §26.2.2 — canon-face time is ticks, written by the commit
--     transaction), the bookkeeping pair and the CAS counter
--     (``state_version`` NOT NULL CHECK > 0 — the house discipline).
--   * ``reader_exposure`` — the reader-exposure record face, **decoupled
--     from SEGMENT COMMIT** (the review's item 2 / STATE §25 / RA §28):
--     ``exposure_id`` TEXT PRIMARY KEY, derived
--     ``f"{passage_id}-x{reader_id}"``, ``passage_id`` NOT NULL
--     REFERENCES narrative_passage(passage_id), ``reader_id`` NOT NULL
--     (MVP = the local user's word), ``exposed_at`` NOT NULL (**ISO
--     bookkeeping — a wall-clock stamp, not story time**), the
--     bookkeeping pair and the CAS counter. N-INV-005: the exposure
--     face writes no actor memory / belief (V3-5 ships neither table;
--     the settlement module's source scan pins the exposure SQL never
--     names their vocabulary). Nothing in the NCP-3 group writes this
--     table — a passage commit is not a reading.
--   * ``segment_commit`` — the **explicit lineage face** (the review's
--     item 1): V3 events' story time is attributed through this row,
--     never inferred from an opaque event-id's naming. ``commit_id``
--     TEXT PRIMARY KEY, derived ``f"sg:{scene_id}:{segment_seq:04d}"``,
--     ``kind`` NOT NULL CHECK ('SEGMENT') (V3-6 adds the
--     'ACTION_OUTCOME' word), ``scene_id`` NOT NULL, ``segment_seq``
--     NOT NULL, ``passage_id`` NOT NULL REFERENCES
--     narrative_passage(passage_id), ``actual_start_tick`` /
--     ``actual_end_tick`` NOT NULL (the segment's actual span: the
--     current tick before the advance, plus its duration), ``event_id``
--     NOT NULL REFERENCES world_event(event_id) (the non-user fact row
--     this segment settled), the bookkeeping pair and the CAS counter,
--     with **UNIQUE (scene_id, segment_seq)** (the same idempotency key
--     family as the passage). The ``story_time_of(event_id)`` read path
--     resolves a V3 event's narrative span through this table; a
--     legacy event with no row here answers honestly absent.
--   * The three FKs are real: the passage hangs off the scene anchor
--     it was written for, the exposure off the passage it records, the
--     lineage row off both the passage and the event — the commit
--     group's four rows (passage / event / segment_commit, plus the
--     state settlement) land in one short transaction or not at all
--     (N-R-INV-004).
--   * No index anywhere: per-scene segment slices are single digits in
--     the MVP, a scan is the honest cost (0028–0032's posture).
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION
--     equivalent (RESTRICT posture) is this cut's whole deletion
--     story — the same posture 0023–0025, 0028 and 0029–0032 spell;
--     the three tables are registered keep-side in
--     GLOBAL_CONTENT_TABLES (V3-5, same cut).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS narrative_passage (
    passage_id   TEXT PRIMARY KEY,
    scene_id     TEXT NOT NULL REFERENCES world_scene(scene_id),
    segment_seq  INTEGER NOT NULL,
    body         TEXT NOT NULL,
    language     TEXT NOT NULL,
    outcome_ref  TEXT,
    created_at_tick INTEGER NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (scene_id, segment_seq));

CREATE TABLE IF NOT EXISTS reader_exposure (
    exposure_id  TEXT PRIMARY KEY,
    passage_id   TEXT NOT NULL REFERENCES narrative_passage(passage_id),
    reader_id    TEXT NOT NULL,
    exposed_at   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0));

CREATE TABLE IF NOT EXISTS segment_commit (
    commit_id    TEXT PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('SEGMENT')),
    scene_id     TEXT NOT NULL,
    segment_seq  INTEGER NOT NULL,
    passage_id   TEXT NOT NULL REFERENCES narrative_passage(passage_id),
    actual_start_tick INTEGER NOT NULL,
    actual_end_tick   INTEGER NOT NULL,
    event_id     TEXT NOT NULL REFERENCES world_event(event_id),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (scene_id, segment_seq));

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '33')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '33')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
