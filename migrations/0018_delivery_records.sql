-- 0018_delivery_records.sql — Phase 9 P9-1: the five delivery records of
-- docs/DATA_MODEL.md §22 and §21.1 (TASK-OPI-e26b27a7-….3 §1-A).
--
-- Five tables land here, and nothing else. This migration is DDL + vocabulary
-- only — no backfill, no rebuild, no row is created by it. The write face
-- that fills them belongs to this same slice: elc.platform.db.delivery_store
-- (every statement) behind the SQL-free port
-- elc.runtime.delivery_records.DeliveryRecordStore. Nothing earlier in the
-- chain is touched: 0001–0017 are byte-identical (0017's header comment
-- included — this cut does not edit that file) and every table they created
-- keeps its shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §22 "Delivery Data" (lines 1209–1249) — three fenced
--                           blocks:
--                             ServerDeliveryRecord (lines 1211–1221), seven
--                               columns in this order — action_id /
--                               assistant_turn_id / state / sent_prefix /
--                               last_chunk_seq / started_at / terminal_at?
--                             ClientRenderAck     (lines 1223–1234, whose
--                               heading is separated from its block by the
--                               sentence "异步 refinement event；主 Turn 不等待
--                               ACK 才 terminalize."): action_id /
--                               assistant_turn_id / rendered_chunk_seq /
--                               rendered_text_hash / acked_at / final_rendered
--                             ExposureEstimate    (lines 1236–1245), six
--                               columns: action_id / certainty /
--                               exposure_level / max_possible_exposure /
--                               confirmed_exposure / derivation_reason
--   docs/DATA_MODEL.md §21.1 "Validator / PreDelivery Guard Records"
--                           (lines 1176–1205) — two fenced blocks:
--                             ValidatorResult (lines 1178–1192): the seven
--                               columns validator_result_id / action_id /
--                               attempt_no / decision (with its four indented
--                               words ACCEPT / RETRY / FALLBACK /
--                               ABORT_DELIVERY) / reason_codes[] /
--                               validator_version / created_at
--                             PreDeliveryGuardResult (lines 1194–1205): the
--                               six columns pre_delivery_guard_result_id /
--                               action_id / decision (with its two indented
--                               words VALID / INVALIDATE_ACTION) /
--                               reason_codes[] / checked_lineage_version /
--                               created_at
--   docs/STATE_MACHINES.md §13 (lines 405–440) — the words the §22 blocks
--                           carry but do not spell: the six ServerDeliveryRecord
--                           state words (NOT_SENT / SENDING / SENT_PARTIAL /
--                           SENT_COMPLETE / FAILED / CANCELLED, lines 409–416)
--                           and the two ExposureEstimate vocabularies
--                           (certainty: CONFIRMED_RENDERED /
--                           SERVER_SENT_UNCONFIRMED / UNKNOWN, lines 428–432;
--                           exposure_level: NONE / PARTIAL / FULL, lines
--                           434–438).
--   docs/STATE_MACHINES.md §16 (lines 500–520) — the PreDeliveryGuard output
--                           words VALID / INVALIDATE_ACTION (lines 515–519),
--                           the two words §21.1's block repeats inline.
--   docs/RUNTIME_ARCHITECTURE.md §6 CP3a (lines 221–230) — the commit point
--                           these rows are: "ServerDeliveryRecord terminal
--                           state / initial ExposureEstimate / AssistantTurn
--                           canonical content?" in one step, with "主 Turn 不
--                          等待 ClientRenderAck" as the record split this
--                           file's two shapes serve (the ACK is §6's
--                           "asynchronous refinement", lines 232–239).
--   docs/RUNTIME_ARCHITECTURE.md §14 (lines 435–456) — the three exposure
--                           layers (PresentationAction / ServerDeliveryRecord ·
--                           ClientRenderAck / ExposureEstimate) and the
--                           conservative rule §22's last line repeats.
--   docs/RUNTIME_ARCHITECTURE.md §15 (lines 460–474) — the PreDeliveryGuard's
--                           hard-invalidation list: "不重新跑 Planner utility".
--   docs/RUNTIME_ARCHITECTURE.md §17 (lines 514–526) — partial delivery: the
--                           sent/confirmed boundary is canonicalized and marked
--                           uncertain rather than replayed from the top, which
--                           is why ``sent_prefix`` and ``last_chunk_seq`` are
--                           the record's durable boundary and why
--                           ``sent_prefix`` is never reset by this schema.
--   docs/RUNTIME_ARCHITECTURE.md §18 (lines 548–558) — barge-in terminalizes
--                           the current delivery as PARTIAL/CANCELLED: two of
--                           §13's six state words, written by a later cut.
--   docs/RUNTIME_ARCHITECTURE.md §22 (lines 663–678) — recovery scans
--                           "ServerDeliveryRecord" among the non-terminal work
--                           ("只恢复未完成 action/projection"), which is what
--                           makes ``terminal_at`` the record's own freezing
--                           instant and ``last_chunk_seq``/``sent_prefix`` its
--                           resumable boundary.
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27    the physical form (column type, JSON encoding,
--                           index names) is the implementation's; the record
--                           shapes are declared in elc.runtime.delivery_records
--                           (four new frozen records) and reused from
--                           elc.persona.types (ValidatorResult — see the
--                           registry note below).
--
-- ---------------------------------------------------------------------------
-- Physical decisions (each minimal, no silent widening)
--
--   * **Keys.** §22's three blocks carry no independent id column, so each is
--     keyed by what its record *is*: ``server_delivery_record`` PK =
--     ``action_id`` (one action has one server-delivery fact — RA §6 CP3a
--     names the record in the singular: "ServerDeliveryRecord terminal
--     state"); ``client_render_ack`` PK = (action_id, rendered_chunk_seq)
--     (an action's ACK stream is one event per chunk, §22 line 1229 names the
--     sequence column, and the block has no id to key on — the 0003
--     ``provider_attempt`` UNIQUE(action_id, attempt_no) shape for a
--     per-action sequence); ``exposure_estimate`` PK = ``action_id`` (the row
--     is the action's *current* estimate — the initial write is this cut's
--     port, and refinement is the explicit face P9-4 lands). §21.1's two
--     blocks *do* carry ids, so ``validator_result`` PK =
--     ``validator_result_id`` and ``pre_delivery_guard_result`` PK =
--     ``pre_delivery_guard_result_id``. No other UNIQUE and no index: neither
--     section names a second key.
--   * **Foreign keys — the five ``action_id`` columns.** Every one of the five
--     rows is *about* one GenerationAction, and that row always exists first
--     (0003's table is where an action becomes durable), so all five
--     ``action_id`` columns are ``REFERENCES
--     generation_action_intent(action_id)``. This is the same argument 0015
--     made for its four §14 rows and it is checkable: an action_id with no
--     action is a row about nothing.
--   * **``assistant_turn_id`` carries no foreign key — and that is 0003's own
--     reading, quoted verbatim from that file's header:**
--         "No provider CHECK on generation_action_intent.assistant_turn_id:
--          the id is minted at action creation (stable opaque id, DATA_MODEL
--          §1.2) and realized as the assistant_turn row only at
--          canonicalization (CP3a); the back-reference survives as plain
--          data."
--     Two of the five records (§22's) carry the same column under the same
--     meaning — the assistant turn the delivery will become, minted at action
--     creation, durable only at CP3a — and migration 0003 already chose plain
--     data for that reference for exactly this reason: at the instant a
--     delivery row is first written the ``assistant_turn`` row need not exist
--     yet, so a foreign key would be unsatisfiable at write time. The column
--     is therefore ``TEXT NOT NULL`` with no reference, the 0003 shape
--     restated rather than reversed. Revisit: canonicalization lands the
--     assistant_turn row before any delivery record (then the reference
--     becomes satisfiable and the question re-opens — at that point the same
--     audit must run over 0003's column too).
--   * **CHECKs: only §21.1's two inline vocabularies.**
--     ``validator_result.decision IN (ACCEPT, RETRY, FALLBACK,
--     ABORT_DELIVERY)`` and ``pre_delivery_guard_result.decision IN (VALID,
--     INVALIDATE_ACTION)`` carry exactly the words their blocks indent, none
--     added, none dropped. The four words are also §15's Validator output and
--     the two §16's PreDeliveryGuard output — the same sets the type system
--     already holds (``elc.persona.types.ValidatorDecision``), and the port's
--     vocabulary constants read them from there rather than spelling a second
--     copy.
--   * **The §22 vocabulary columns carry no schema-level CHECK.** §22's blocks
--     state their column lists and nothing else — the words live in
--     STATE_MACHINES §13 and in the repository's enums
--     (``elc.conversation.types.DeliveryState`` for ``state``,
--     ``elc.teaching.types.ExposureEstimateCertainty`` for ``certainty``,
--     ``elc.teaching.types.AnswerExposureState`` for ``exposure_level`` and
--     the two exposure columns below). A CHECK here would spell words §22 does
--     not state, so the *write face* validates them in Python instead — the
--     port's word refusals answer ``VALIDATION_FAILED`` for a word outside the
--     vocabulary, and the schema stays silent, which is the same posture
--     migration 0015 took for the two §14 status blocks it *did* have words
--     for inline. Revisit: canonical moves the vocabularies into §22's blocks
--     (then the CHECKs land with that revision), or the P9-2/P9-4 writers need
--     the schema itself to refuse a word (then the CHECKs land with that cut,
--     and the port's Python refusals retire into it).
--   * **The two exposure columns carry §13's ``exposure_level`` words, not
--     numbers.** ``max_possible_exposure`` / ``confirmed_exposure`` name §14's
--     two readings of one estimate ("confirmed exposure where available,
--     otherwise max-possible-exposure"), and the only exposure vocabulary
--     canonical text carries is §13's three-word scale (NONE / PARTIAL /
--     FULL) — the shape the estimator's own baseline
--     (behavioral_baselines/estimator/baseline_golden_cases_v1.json) uses in
--     its claims ("exposure_level": "FULL"). A numeric reading has no declared
--     scale anywhere (§22 gives no unit, no range, no mapping), so it is
--     **refused**, not implemented: writing integers here would mint a scale
--     nobody declared. Revisit: canonical (or BF-01) declares a numeric
--     exposure scale (then the column type and the port's word refusal move
--     together).
--   * **``sent_prefix``: the empty string is "nothing sent yet".** §22 gives
--     the column no null, and RA §17 makes the sent boundary the record's
--     durable fact, so "not sent" is the empty prefix and nothing else — the
--     store's advance rule reads it as one (an empty string is a prefix of
--     every string, which is exactly the monotonic shape §17 needs). A NULL
--     here would be a second spelling of the same state.
--   * **``terminal_at`` is the one nullable column of the five.** §22 writes
--     it ``terminal_at?`` and RA §22's recovery scans non-terminal
--     ``ServerDeliveryRecord`` rows — a row that is not terminal yet has no
--     terminal instant. Every other column of the five blocks is written
--     ``NOT NULL`` because its block lists it without a ``?`` — keys
--     excepted, the 0010–0015 convention: a SQLite rowid table reports
--     ``notnull=0`` for a ``TEXT PRIMARY KEY`` column whatever the DDL says,
--     so a ``NOT NULL`` beside a key would be both redundant and unreadable
--     through ``PRAGMA table_info`` (a key's nullability is the key's
--     business).
--   * **JSON columns.** §21.1's two ``reason_codes[]`` columns are bracketed
--     list columns and land as TEXT carrying a deterministic JSON **array**
--     document — one encoding, reused from elc/teaching/store.py's
--     ``_array_document`` (``json.dumps(list(...), sort_keys=True,
--     separators=(",", ":"))``) rather than a second spelling; 0015 and 0016
--     carry the same convention for the same column name.
--   * **``final_rendered`` is 0/1.** §22 names the column without saying what
--     it holds; it is the ACK's boolean (this chunk was the final rendered
--     one), and the one-bit CHECK is a schema-level spelling of a *type*
--     §22's block already states by name — not a vocabulary invented here.
--   * **The rows are removal surface.** All five tables are children of
--     ``generation_action_intent`` (the five FKs above), so BF-05's walks have
--     to reach them before the action row goes: they are declared in
--     ``elc.deletion.types``' three surfaces (SWEPT_TABLES /
--     CONVERSATION_SWEPT_TABLES / LEARNING_HISTORY_SWEPT_TABLES, each ahead
--     of ``generation_action_intent``) in this same change, and
--     ``elc.deletion.store`` carries one SELECT, one DELETE and the
--     CONVERSATION walk's keyed leg for each. No clearing leg is owed: the one
--     column that ever points into these tables from outside is
--     ``attempt_record.exposure_estimate_id`` (0008, §17's '?'), it is plain
--     data with no foreign key, and ``attempt_record`` is removed in the same
--     three scopes — so no dangling reference can survive a sweep (the probes
--     in tests/phase9 assert exactly that).
--   * **The registry's existing ``validator_result`` entry is not touched.**
--     ``elc.platform.registry`` binds that name to
--     ``elc.runtime.types.ValidatorResultRecord`` (a Phase 0 shape: turn_id /
--     proposal_status / checked_refs), while this cut's durable row is shaped
--     by ``elc.persona.types.ValidatorResult`` ("§21.1 column set verbatim",
--     the object the shipped validator produces). The drift is **registered,
--     not repaired** here: the four records this file lands are
--     Runtime-specific runtime records (docs/DOMAIN_MODEL.md §16's list, the
--     ``decision_cycle`` / ``gate_execution_status`` /
--     ``runtime_decision_outcome`` family) and the registry has never carried
--     those. Revisit: a cut that touches the ``validator_result`` registry
--     entry (or the ``ValidatorResultRecord`` shape) has to reconcile the two
--     types in one place; the port's module docstring repeats this note where
--     the row shape is declared.
-- ---------------------------------------------------------------------------
-- 1. server_delivery_record — §22 lines 1211–1221
CREATE TABLE IF NOT EXISTS server_delivery_record (
    action_id         TEXT PRIMARY KEY
        REFERENCES generation_action_intent(action_id),
    assistant_turn_id TEXT NOT NULL,
    state             TEXT NOT NULL,
    sent_prefix       TEXT NOT NULL,
    last_chunk_seq    INTEGER NOT NULL,
    started_at        TEXT NOT NULL,
    terminal_at       TEXT
);

-- ---------------------------------------------------------------------------
-- 2. client_render_ack — §22 lines 1223–1234
CREATE TABLE IF NOT EXISTS client_render_ack (
    action_id          TEXT NOT NULL
        REFERENCES generation_action_intent(action_id),
    assistant_turn_id  TEXT NOT NULL,
    rendered_chunk_seq INTEGER NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    acked_at           TEXT NOT NULL,
    final_rendered     INTEGER NOT NULL CHECK (final_rendered IN (0, 1)),
    PRIMARY KEY (action_id, rendered_chunk_seq)
);

-- ---------------------------------------------------------------------------
-- 3. exposure_estimate — §22 lines 1236–1245
-- state's / certainty's / the exposure words' vocabularies are §13's; the
-- Python write face refuses a word outside them (see the header).
CREATE TABLE IF NOT EXISTS exposure_estimate (
    action_id             TEXT PRIMARY KEY
        REFERENCES generation_action_intent(action_id),
    certainty             TEXT NOT NULL,
    exposure_level        TEXT NOT NULL,
    max_possible_exposure TEXT NOT NULL,
    confirmed_exposure    TEXT NOT NULL,
    derivation_reason     TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 4. validator_result — §21.1 lines 1178–1192
-- The four CHECK words are that block's indented decision vocabulary,
-- verbatim; the write face's Python vocabulary constants read the same four
-- from elc.persona.types.ValidatorDecision.
CREATE TABLE IF NOT EXISTS validator_result (
    validator_result_id TEXT PRIMARY KEY,
    action_id           TEXT NOT NULL
        REFERENCES generation_action_intent(action_id),
    attempt_no          INTEGER NOT NULL,
    decision            TEXT NOT NULL
        CHECK (decision IN ('ACCEPT', 'RETRY', 'FALLBACK', 'ABORT_DELIVERY')),
    reason_codes        TEXT NOT NULL,
    validator_version   TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 5. pre_delivery_guard_result — §21.1 lines 1194–1205
-- The two CHECK words are §16's PreDeliveryGuard output, verbatim.
CREATE TABLE IF NOT EXISTS pre_delivery_guard_result (
    pre_delivery_guard_result_id TEXT PRIMARY KEY,
    action_id                    TEXT NOT NULL
        REFERENCES generation_action_intent(action_id),
    decision                     TEXT NOT NULL
        CHECK (decision IN ('VALID', 'INVALIDATE_ACTION')),
    reason_codes                 TEXT NOT NULL,
    checked_lineage_version      TEXT NOT NULL,
    created_at                   TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '18')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '18')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
