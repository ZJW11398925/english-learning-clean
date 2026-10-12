-- 0035_user_gate_action.sql — V3-6 (User Gate + user_action + Action
-- Resolver + OUTCOME COMMIT, the Narrative V3 program's sixth cut;
-- TASK-OPI-dc1bafdf…23 / the opening ruling DEC-OPI-dc1bafdf…5, re-run
-- revision …21; DECISION_REGISTER v1.5.0).
--
-- Two new tables and one rebuild: the gate a story stops at, the user's
-- own submission and its adjudication, and ``segment_commit``'s second
-- kind — the ACTION_OUTCOME lineage row.
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1 — the "V3-6 落表形" block, column for column:
--     ``user_gate`` (``gate_id`` derived ``f"{scene_id}-g{gate_seq:02d}"``
--     / ``scene_id`` / the five-word ``status`` / ``opened_at_tick`` /
--     ``options_json`` — two to four natural behaviour options plus the
--     implied free text / the bookkeeping pair / ``state_version``),
--     ``user_action`` (``user_action_id`` derived ``f"{gate_id}-a"`` /
--     ``gate_id`` / ``submission_id`` / ``intent_text`` /
--     ``selected_option?`` / the three-word ``status`` / the eight
--     terminal columns ``interpretation`` / ``outcome`` /
--     ``actual_action`` / ``consequences`` / ``state_effects`` /
--     ``participants`` / ``replan_scope`` / ``actual_tick`` / the
--     bookkeeping pair / ``state_version`` / **UNIQUE (gate_id,
--     submission_id)** and the **terminal-integrity composite CHECK**),
--     and the ACTION family's derivation laws (``commit_id =
--     f"ac:{gate_id}:{submission_id}"``, ``event_id =
--     f"ac:{gate_id}:{submission_id}:event"``, ``action_commit_key =
--     (gate_id, submission_id)``).
--   * STATE_MACHINES §23 — the User Gate lifecycle: ``OPEN → ANSWERED →
--     RESOLVING → COMMITTED → CLOSED``, with §22's interlock sentence
--     (a story stops at a gate; a landed segment closes the scene's
--     committed gates) and §25's "V3-6 落法" arm list for the ACTION
--     OUTCOME COMMIT transaction (the transaction itself lives in
--     :mod:`elc.world.action`).
--   * RUNTIME_ARCHITECTURE §28 (NCP-1 / NCP-2) / §29 (the recovery
--     scan's four families) / §30 (N-R-INV-004: all-or-nothing).
--   * DOMAIN_MODEL §20.3-1 / §20.3-3: an option or a free-text answer
--     is an **intent**, never a fact — the adjudication is the only
--     writer of the action's canon, and the action's outcome lands at
--     the same level as a segment.
--
--   * ``user_gate`` — the user's will as a durable stop (the design
--     supplement §2.5's "the story stops" check): ``gate_id`` TEXT
--     PRIMARY KEY, derived ``f"{scene_id}-g{gate_seq:02d}"`` (a local
--     derivation law serving idempotent replay only — narrative time
--     attribution never rides an id's naming, §26.2.2's lineage
--     discipline), ``scene_id`` NOT NULL REFERENCES
--     world_scene(scene_id), ``status`` NOT NULL CHECK the five words
--     of §23 verbatim, ``opened_at_tick`` NOT NULL (the opening face
--     reads ``world.current_tick`` inside its own short transaction —
--     the #3 lifecycle tick authority's extension: opening a stop is
--     not a commit, the tick is read and never advanced), ``options_json``
--     NOT NULL (the canonical participants codec's shape: a JSON array
--     of the gate's option strings — two to four, validated by the
--     opening face), the bookkeeping pair and the CAS counter
--     (``state_version`` NOT NULL CHECK > 0 — the house discipline).
--   * ``user_action`` — the submission and its adjudication, one row
--     per gate: ``user_action_id`` TEXT PRIMARY KEY, derived
--     ``f"{gate_id}-a"`` (one gate accepts exactly one submission; the
--     row's identity rides the gate), ``gate_id`` NOT NULL REFERENCES
--     user_gate(gate_id), ``submission_id`` NOT NULL (one half of the
--     NCP-1 idempotency anchor), ``intent_text`` NOT NULL (the user's
--     own words — an intent, never a fact), ``selected_option`` NULL
--     (when given it must be one of the gate's recorded options — the
--     NCP-1 check; NULL is the free-text arm), ``status`` NOT NULL
--     CHECK ``('ANSWERED','RESOLVING','COMMITTED')`` — **no 'OPEN'**:
--     the row is born ``ANSWERED`` in NCP-1. The eight terminal columns
--     (``interpretation`` / ``outcome`` / ``actual_action`` /
--     ``consequences`` / ``state_effects`` / ``participants`` /
--     ``replan_scope`` / ``actual_tick``) stay NULL through
--     ``ANSWERED`` / ``RESOLVING`` and are written all at once by NCP-2
--     (``replan_scope`` CHECK ``('NONE','SCENE','CHAPTER')``;
--     ``actual_tick`` = the ruling's story tick — the ACTION family's
--     Canon time anchor, the post-advance ``actual_end``), the
--     bookkeeping pair, ``state_version`` CHECK > 0, **UNIQUE (gate_id,
--     submission_id)** (§26.2.4's idempotency anchor verbatim) and the
--     **terminal-integrity composite CHECK**: ``status <> 'COMMITTED'``
--     or all eight columns NOT NULL — "COMMITTED ⇒ the ruling's whole
--     face landed" is NCP-2's all-or-nothing redundancy at the storage
--     surface (the 0032 composite-FK posture; an invariant in the
--     storage, not only in the store).
--   * ``segment_commit`` — **rebuilt** (the 0032 precedent), carrying
--     the V3-5R face unchanged: ``is_last_segment`` (0034's column) and
--     ``UNIQUE (scene_id, segment_seq)`` survive the rebuild as they
--     stand, and the back-fill law's column is copied with every row.
--     What changes: ``kind`` CHECK widens to
--     ``('SEGMENT','ACTION_OUTCOME')``; ``action_id`` TEXT NULL
--     REFERENCES user_action(user_action_id) arrives; ``segment_seq`` /
--     ``passage_id`` become NULLable; and two kind-consistency CHECKs
--     pin the two row shapes — a ``SEGMENT`` row carries
--     ``segment_seq`` / ``passage_id`` and no ``action_id``; an
--     ``ACTION_OUTCOME`` row carries ``action_id``, no ``segment_seq`` /
--     ``passage_id``, and ``is_last_segment = 0`` (**a gate's action
--     does not carry a SCENE COMMIT** — the flip stays the last
--     SEGMENT's). The migration copies the carried rows with an
--     **explicit column list** (``INSERT … SELECT`` — the column order
--     changed with ``action_id``'s arrival; ``SELECT *`` would be
--     wrong, and the carried rows take their persisted
--     ``is_last_segment`` verbatim). The lineage read path
--     ``story_time_of(event_id)`` answers both kinds (same table, same
--     columns — kind-agnostic), and the V3 cognition read's lineage JOIN
--     is kind-agnostic too: ACTION_OUTCOME events are visible from this
--     migration on.
--   * The FK chains are real: a gate hangs off the scene it stops, an
--     action off its gate, an ACTION_OUTCOME lineage row off its action
--     row and its event — the NCP-2 group's rows (action terminal
--     columns / event / state settlement / tick / lineage row / gate
--     flip / chapter arm) land in one short transaction or not at all
--     (N-R-INV-004).
--   * Build order: ``user_gate`` → ``user_action`` (its FK) → the
--     ``segment_commit`` rebuild (its FK to ``user_action``).
--   * No index anywhere: per-scene gate and action slices are single
--     digits in the MVP, a scan is the honest cost (0028–0034's
--     posture).
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION
--     equivalent (RESTRICT posture) is this cut's whole deletion story
--     — the same posture 0023–0034 spell; the two tables are registered
--     keep-side in GLOBAL_CONTENT_TABLES (V3-6, same cut; 18 → 20
--     members, the chronological tail append), every FK link keep-side
--     (gate → scene → chapter → world; action → gate).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_gate (
    gate_id      TEXT PRIMARY KEY,
    scene_id     TEXT NOT NULL REFERENCES world_scene(scene_id),
    status       TEXT NOT NULL CHECK (status IN ('OPEN','ANSWERED','RESOLVING','COMMITTED','CLOSED')),
    opened_at_tick INTEGER NOT NULL,
    options_json TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0));

CREATE TABLE IF NOT EXISTS user_action (
    user_action_id TEXT PRIMARY KEY,
    gate_id      TEXT NOT NULL REFERENCES user_gate(gate_id),
    submission_id TEXT NOT NULL,
    intent_text  TEXT NOT NULL,
    selected_option TEXT,
    status       TEXT NOT NULL CHECK (status IN ('ANSWERED','RESOLVING','COMMITTED')),
    interpretation TEXT,
    outcome      TEXT,
    actual_action TEXT,
    consequences TEXT,
    state_effects TEXT,
    participants TEXT,
    replan_scope TEXT CHECK (replan_scope IS NULL OR replan_scope IN ('NONE','SCENE','CHAPTER')),
    actual_tick  INTEGER,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (gate_id, submission_id),
    CHECK (status <> 'COMMITTED' OR (
        interpretation IS NOT NULL
        AND outcome IS NOT NULL
        AND actual_action IS NOT NULL
        AND consequences IS NOT NULL
        AND state_effects IS NOT NULL
        AND participants IS NOT NULL
        AND replan_scope IS NOT NULL
        AND actual_tick IS NOT NULL)));

CREATE TABLE IF NOT EXISTS segment_commit_rebuilt (
    commit_id    TEXT PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('SEGMENT','ACTION_OUTCOME')),
    scene_id     TEXT NOT NULL,
    segment_seq  INTEGER,
    passage_id   TEXT REFERENCES narrative_passage(passage_id),
    action_id    TEXT REFERENCES user_action(user_action_id),
    actual_start_tick INTEGER NOT NULL,
    actual_end_tick   INTEGER NOT NULL,
    event_id     TEXT NOT NULL REFERENCES world_event(event_id),
    is_last_segment INTEGER NOT NULL DEFAULT 0 CHECK (is_last_segment IN (0, 1)),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (scene_id, segment_seq),
    CHECK (kind <> 'SEGMENT' OR (
        segment_seq IS NOT NULL
        AND passage_id IS NOT NULL
        AND action_id IS NULL)),
    CHECK (kind <> 'ACTION_OUTCOME' OR (
        action_id IS NOT NULL
        AND segment_seq IS NULL
        AND passage_id IS NULL
        AND is_last_segment = 0)));

INSERT INTO segment_commit_rebuilt (
    commit_id, kind, scene_id, segment_seq, passage_id, action_id,
    actual_start_tick, actual_end_tick, event_id, is_last_segment,
    created_at, updated_at, state_version)
    SELECT
    commit_id, kind, scene_id, segment_seq, passage_id, NULL,
    actual_start_tick, actual_end_tick, event_id, is_last_segment,
    created_at, updated_at, state_version
    FROM segment_commit;

DROP TABLE segment_commit;
ALTER TABLE segment_commit_rebuilt RENAME TO segment_commit;

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '35')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '35')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
