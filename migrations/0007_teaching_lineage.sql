-- 0007_teaching_lineage.sql — Phase 3 P3-1A teaching lineage
-- (TASK-OPI-2babb21e-bc72-47a2-9382-e773c92211d2.17 ①;母决策
-- DEC-OPI-2babb21e-….5 核心裁定②;docs/IMPLEMENTATION_PLAN.md §1.5
-- Phase 3 "User-initiated TeachingMoment vertical slice").
--
-- Authority map (canonical column names follow the cited sections
-- verbatim; every column outside the cited sets is individually
-- justified below):
--   docs/DATA_MODEL.md §14.1  gate_decision (eight columns word for word:
--                             gate_decision_id, decision_cycle_id,
--                             candidate_id, context, decision,
--                             reason_codes[], policy_version, created_at;
--                             context vocabulary OPEN / AUTO_CONTINUE /
--                             USER_REQUESTED_CONTINUE; decision
--                             vocabulary ALLOW / DENY) and
--                             gate_execution_status (nine columns:
--                             gate_execution_status_id, decision_cycle_id?,
--                             moment_id?, gate_context, authorization_basis
--                             DECISION_CYCLE / ACTIVE_MOMENT,
--                             authorization_status VALID / INVALIDATED /
--                             UNKNOWN, status SUCCEEDED / DEGRADED,
--                             missing_or_unknown[], created_at).
--   docs/DATA_MODEL.md §15    teaching_moment — the thirty-column §15 set
--                             word for word (source vocabulary AUTOMATIC /
--                             USER_INITIATED / MANUAL_FOCUS /
--                             SCHEDULED_STUDY); lifecycle_state /
--                             presentation_phase carry the
--                             docs/STATE_MACHINES.md §1 / §3 vocabularies.
--   docs/STATE_MACHINES.md §3 presentation phases (INITIAL_PROMPT …
--                             EXPLANATION) and support levels (NONE …
--                             FULL_FORM_SHOWN).
--   docs/DOMAIN_MODEL.md §11  target_mode (RESOURCE_PRACTICE /
--                             CAPABILITY_PRACTICE / PROBE / REVIEW /
--                             TRANSFER) and learning_intent (ESTABLISH /
--                             DEVELOP / WITHDRAW_SUPPORT / CONSOLIDATE /
--                             PROBE / TRANSFER / EXPAND_REPERTOIRE) —
--                             §15 pins the column names, the canonical
--                             value lists live in §11.
--   docs/DATA_MODEL.md §24.14 evidence_modality V1 values
--                             (TEXT_PRODUCTION / TEXT_COMPREHENSION).
--   docs/DATA_MODEL.md §20    generation_action_intent rebuild: the §20
--                             column set is unchanged; what tightens is
--                             decision_cycle_id NOT NULL + FK(decision_cycle)
--                             and moment_id nullable FK(teaching_moment)
--                             (DEC-…091f35c3.7 adjudication successor note,
--                             re-pointed to P3-1 by TASK-…eaaa5a1d.55 ④).
--   docs/DATA_MODEL.md §25    UNIQUE(turn_id, cycle_index) preserved by the
--                             decision_cycle rebuild below.
--
-- Legacy DecisionCycle backfill (DEC-…2babb21e.5 核心裁定②): every turn
-- that owns at least one historical GenerationActionIntent receives one
-- deterministic legacy cycle (cycle_index = 0, all snapshot/version and
-- planner/gate columns NULL, created_at = turn_record.started_at,
-- decision_cycle_id = 'dcy-legacy-' || turn_id). The backfill is a pure
-- export of already-durable rows: every statement is INSERT…SELECT /
-- UPDATE…WHERE over existing rows, so re-running it is a no-op
-- (WHERE NOT EXISTS + WHERE … IS NULL guards). Historical actions are
-- re-pointed at that cycle, and only NONTERMINAL turns get their
-- turn_record.active_decision_cycle_id set (the active pointer is not an
-- audit pointer: a terminal historical turn keeps NULL and is not
-- disguised as having an active cycle). state_version is deliberately not
-- bumped: this is a one-shot data export of pre-existing rows, not a
-- runtime coordination transition (STATE_MACHINES §10/§20 CAS guards
-- runtime transitions; no live owner can be raced by a migration).
--
-- decision_cycle relaxation (physical, minimal): §4 marks only
-- relationship_view_version / planner_decision_id / gate_decision_id with
-- '?', but the legacy export above requires the snapshot/version columns
-- to be legitimately NULL-able — a pre-lineage turn had captured no
-- Learning snapshot, and NULL is the honest value ("no source", never a
-- fabricated stamp). 0006 pinned those columns NOT NULL before the lineage
-- semantics existed; this migration rebuilds exactly that nullability
-- (no CHECK, no UNIQUE, no column added or renamed) so the adjudicated
-- backfill can be represented truthfully.
--
-- Rebuild order (SQLite: a parent table that children reference cannot be
-- dropped with foreign_keys=ON and non-empty children):
--   1. decision_cycle rebuild — FIRST, while no FK references it yet;
--   2. gate_decision → teaching_moment → gate_execution_status (the FK
--      creation order follows the §15/§14.1 references);
--   3. legacy cycle backfill;
--   4. generation_action_intent rebuild (provider_attempt is its only FK
--      child, so the unit sets PRAGMA defer_foreign_keys=ON for the
--      drop/recreate; the pragma is transaction-scoped and resets at the
--      migration's COMMIT).
--
-- Storage forms (implementation-defined, DATA_MODEL §27): array columns
-- (reason_codes / supporting_targets / missing_or_unknown) and the
-- focus_target pair are JSON text — the 0004 qualifiers precedent.
-- focus_target is the single §15 target: {"target_type", "target_id"},
-- stored under the canonical column name rather than split into two
-- physical columns.
--
-- Scope fence: this migration creates the SCHEMA plus the legacy export.
-- The write faces land in src/elc/runtime (DecisionCycle port) and
-- src/elc/teaching (CP2 / Gate store).

-- ---------------------------------------------------------------------------
-- 1. decision_cycle rebuild — snapshot/version fields become NULL-able
--    (the legacy export above). Same fourteen §4 columns, same UNIQUE.
-- ---------------------------------------------------------------------------
CREATE TABLE decision_cycle_v7 (
    decision_cycle_id         TEXT PRIMARY KEY,
    turn_id                   TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    cycle_index               INTEGER NOT NULL CHECK (cycle_index >= 0),
    learning_snapshot_id      TEXT,
    evidence_watermark        INTEGER
        CHECK (evidence_watermark IS NULL OR evidence_watermark >= 0),
    curriculum_version        TEXT,
    goal_version              TEXT,
    schedule_version          TEXT,
    policy_version            TEXT,
    context_view_version      TEXT,
    relationship_view_version TEXT,
    planner_decision_id       TEXT,
    gate_decision_id          TEXT,
    created_at                TEXT NOT NULL,
    UNIQUE (turn_id, cycle_index)
);

INSERT INTO decision_cycle_v7 (
    decision_cycle_id, turn_id, cycle_index, learning_snapshot_id,
    evidence_watermark, curriculum_version, goal_version, schedule_version,
    policy_version, context_view_version, relationship_view_version,
    planner_decision_id, gate_decision_id, created_at)
SELECT
    decision_cycle_id, turn_id, cycle_index, learning_snapshot_id,
    evidence_watermark, curriculum_version, goal_version, schedule_version,
    policy_version, context_view_version, relationship_view_version,
    planner_decision_id, gate_decision_id, created_at
FROM decision_cycle;

DROP TABLE decision_cycle;

ALTER TABLE decision_cycle_v7 RENAME TO decision_cycle;

-- ---------------------------------------------------------------------------
-- 2. gate_decision — DATA_MODEL §14.1, eight columns word for word.
--    No UNIQUE beyond the PK: §25 pins no gate idempotency key; the
--    one-decision-per-(cycle, context, subject) discipline is the Gate's
--    authority (src/elc/teaching/gate.py) and is covered by tests.
-- ---------------------------------------------------------------------------
CREATE TABLE gate_decision (
    gate_decision_id   TEXT PRIMARY KEY,
    decision_cycle_id  TEXT NOT NULL
        REFERENCES decision_cycle(decision_cycle_id),
    candidate_id       TEXT NOT NULL,
    context            TEXT NOT NULL
        CHECK (context IN ('OPEN', 'AUTO_CONTINUE',
                           'USER_REQUESTED_CONTINUE')),
    decision           TEXT NOT NULL CHECK (decision IN ('ALLOW', 'DENY')),
    reason_codes       TEXT NOT NULL,
    policy_version     TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 3. teaching_moment — DATA_MODEL §15, thirty columns word for word.
--    Nullable: the §15 '?' columns (persona_id, evidence_goal,
--    preferred_support_ceiling, completion_outcome, abort_reason,
--    opened_at, teaching_terminal_at, closed_at) plus
--    learning_snapshot_id / evidence_watermark / curriculum_version /
--    content_version / policy_version — §15 lists those five without '?',
--    but Phase 3 has no Curriculum/Content/TeachingPolicy durable source;
--    CP2 stamps what exists (Learning snapshot + watermark) and NULL means
--    "no source in this phase", never a fabricated version string.
--    lifecycle_state / presentation_phase / support_level vocabularies are
--    the STATE_MACHINES §1 / §3 lists; target_mode / learning_intent the
--    DOMAIN_MODEL §11 lists.
-- ---------------------------------------------------------------------------
CREATE TABLE teaching_moment (
    moment_id                 TEXT PRIMARY KEY,
    conversation_id           TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    persona_id                TEXT,
    source                    TEXT NOT NULL
        CHECK (source IN ('AUTOMATIC', 'USER_INITIATED', 'MANUAL_FOCUS',
                          'SCHEDULED_STUDY')),
    decision_cycle_id         TEXT NOT NULL
        REFERENCES decision_cycle(decision_cycle_id),
    candidate_id              TEXT NOT NULL,
    gate_decision_id          TEXT NOT NULL
        REFERENCES gate_decision(gate_decision_id),
    focus_target              TEXT NOT NULL,
    supporting_targets        TEXT NOT NULL,
    target_mode               TEXT NOT NULL
        CHECK (target_mode IN ('RESOURCE_PRACTICE', 'CAPABILITY_PRACTICE',
                               'PROBE', 'REVIEW', 'TRANSFER')),
    learning_intent           TEXT NOT NULL
        CHECK (learning_intent IN ('ESTABLISH', 'DEVELOP',
                                   'WITHDRAW_SUPPORT', 'CONSOLIDATE',
                                   'PROBE', 'TRANSFER',
                                   'EXPAND_REPERTOIRE')),
    evidence_modality         TEXT NOT NULL
        CHECK (evidence_modality IN ('TEXT_PRODUCTION',
                                     'TEXT_COMPREHENSION')),
    evidence_goal             TEXT,
    preferred_support_ceiling TEXT,
    learning_snapshot_id      TEXT,
    evidence_watermark        INTEGER
        CHECK (evidence_watermark IS NULL OR evidence_watermark >= 0),
    curriculum_version        TEXT,
    content_version           TEXT,
    policy_version            TEXT,
    lifecycle_state           TEXT NOT NULL
        CHECK (lifecycle_state IN ('AUTHORIZED', 'OPENING', 'AWAITING_USER',
                                   'EVALUATING', 'DECIDING_NEXT_ACTION',
                                   'COMPLETING', 'ABORTING',
                                   'TEACHING_TERMINAL', 'RESUMING',
                                   'CLOSED')),
    presentation_phase        TEXT NOT NULL
        CHECK (presentation_phase IN ('INITIAL_PROMPT', 'HINT_SEMANTIC',
                                      'HINT_STRUCTURAL', 'HINT_PARTIAL_FORM',
                                      'FULL_REVEAL',
                                      'POST_REVEAL_OPTIONAL_ATTEMPT',
                                      'EXPLANATION')),
    attempt_index             INTEGER NOT NULL CHECK (attempt_index >= 0),
    support_level             TEXT NOT NULL
        CHECK (support_level IN ('NONE', 'CONTEXT_ONLY', 'SEMANTIC_HINT',
                                 'STRUCTURAL_HINT', 'PARTIAL_FORM',
                                 'FULL_FORM_SHOWN')),
    completion_outcome        TEXT,
    abort_reason              TEXT,
    state_version             INTEGER NOT NULL CHECK (state_version > 0),
    created_at                TEXT NOT NULL,
    opened_at                 TEXT,
    teaching_terminal_at      TEXT,
    closed_at                 TEXT
);

-- ---------------------------------------------------------------------------
-- 4. gate_execution_status — DATA_MODEL §14.1, nine columns word for word.
--    decision_cycle_id? / moment_id? are the §14.1 '?' columns: an OPEN
--    execution binds DECISION_CYCLE authorization (moment_id NULL — the
--    moment does not exist before the ALLOW lands), a continuation binds
--    ACTIVE_MOMENT (decision_cycle_id NULL). DEGRADED rows carry the
--    missing_or_unknown fact-key array and never a synthetic GateDecision
--    (§14.1; the row itself is the trace).
-- ---------------------------------------------------------------------------
CREATE TABLE gate_execution_status (
    gate_execution_status_id TEXT PRIMARY KEY,
    decision_cycle_id        TEXT
        REFERENCES decision_cycle(decision_cycle_id),
    moment_id                TEXT
        REFERENCES teaching_moment(moment_id),
    gate_context             TEXT NOT NULL
        CHECK (gate_context IN ('OPEN', 'AUTO_CONTINUE',
                                'USER_REQUESTED_CONTINUE')),
    authorization_basis      TEXT NOT NULL
        CHECK (authorization_basis IN ('DECISION_CYCLE', 'ACTIVE_MOMENT')),
    authorization_status     TEXT NOT NULL
        CHECK (authorization_status IN ('VALID', 'INVALIDATED', 'UNKNOWN')),
    status                   TEXT NOT NULL
        CHECK (status IN ('SUCCEEDED', 'DEGRADED')),
    missing_or_unknown       TEXT NOT NULL,
    created_at               TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 5. Legacy cycle backfill — deterministic, idempotent, existing rows only.
-- ---------------------------------------------------------------------------
INSERT INTO decision_cycle (
    decision_cycle_id, turn_id, cycle_index, learning_snapshot_id,
    evidence_watermark, curriculum_version, goal_version, schedule_version,
    policy_version, context_view_version, relationship_view_version,
    planner_decision_id, gate_decision_id, created_at)
SELECT
    'dcy-legacy-' || t.turn_id, t.turn_id, 0, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, t.started_at
FROM turn_record t
WHERE EXISTS (SELECT 1 FROM generation_action_intent g
              WHERE g.turn_id = t.turn_id)
  AND NOT EXISTS (SELECT 1 FROM decision_cycle d
                  WHERE d.turn_id = t.turn_id AND d.cycle_index = 0);

UPDATE generation_action_intent
SET decision_cycle_id = (
    SELECT d.decision_cycle_id FROM decision_cycle d
    WHERE d.turn_id = generation_action_intent.turn_id
      AND d.cycle_index = 0)
WHERE decision_cycle_id IS NULL;

UPDATE turn_record
SET active_decision_cycle_id = (
    SELECT d.decision_cycle_id FROM decision_cycle d
    WHERE d.turn_id = turn_record.turn_id AND d.cycle_index = 0)
WHERE status NOT IN ('COMPLETED', 'CANCELLED_BY_USER', 'FAILED_FINAL')
  AND active_decision_cycle_id IS NULL
  AND EXISTS (SELECT 1 FROM decision_cycle d
              WHERE d.turn_id = turn_record.turn_id AND d.cycle_index = 0);

-- ---------------------------------------------------------------------------
-- 6. generation_action_intent rebuild — §20 column set unchanged; the two
--    lineage columns tighten (NOT NULL + FK(decision_cycle); nullable
--    FK(moment_id)).
--
--    provider_attempt is the only FK child of this table, and with
--    foreign_keys=ON (the canonical connection profile) SQLite refuses to
--    drop a parent table that still has child rows. The child rows are
--    therefore copied aside, the child table is dropped, the parent is
--    rebuilt, and the child is recreated and refilled — all inside the
--    migration's single transaction, so the pair is never observably
--    inconsistent. (PRAGMA defer_foreign_keys was tried first and does
--    NOT survive the parent drop: SQLite still fails the COMMIT with
--    FOREIGN KEY constraint failed.)
-- ---------------------------------------------------------------------------
CREATE TABLE provider_attempt_backup AS SELECT * FROM provider_attempt;

DROP TABLE provider_attempt;

CREATE TABLE generation_action_intent_v7 (
    action_id               TEXT PRIMARY KEY,
    turn_id                 TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    decision_cycle_id       TEXT NOT NULL
        REFERENCES decision_cycle(decision_cycle_id),
    moment_id               TEXT
        REFERENCES teaching_moment(moment_id),
    assistant_turn_id       TEXT NOT NULL,
    action_type             TEXT NOT NULL
        CHECK (action_type IN (
            'NORMAL_PERSONA_REPLY', 'TEACHING_OPEN', 'TEACHING_HINT',
            'TEACHING_REVEAL', 'TEACHING_EXPLANATION', 'PERSONA_RESUME')),
    generation_contract_id  TEXT NOT NULL,
    status                  TEXT NOT NULL
        CHECK (status IN (
            'PREPARED', 'REQUESTED', 'GENERATING', 'VALIDATING',
            'READY_TO_DELIVER', 'DELIVERING', 'TERMINAL')),
    attempt_count           INTEGER NOT NULL CHECK (attempt_count >= 0),
    owner_epoch             INTEGER NOT NULL,
    created_at              TEXT NOT NULL
);

INSERT INTO generation_action_intent_v7 (
    action_id, turn_id, decision_cycle_id, moment_id, assistant_turn_id,
    action_type, generation_contract_id, status, attempt_count, owner_epoch,
    created_at)
SELECT
    action_id, turn_id, decision_cycle_id, moment_id, assistant_turn_id,
    action_type, generation_contract_id, status, attempt_count, owner_epoch,
    created_at
FROM generation_action_intent;

DROP TABLE generation_action_intent;

ALTER TABLE generation_action_intent_v7 RENAME TO generation_action_intent;

-- The 0003 DDL, verbatim (minus the trailing comment block).
CREATE TABLE provider_attempt (
    provider_attempt_id  TEXT PRIMARY KEY,
    action_id            TEXT NOT NULL
        REFERENCES generation_action_intent(action_id),
    attempt_no           INTEGER NOT NULL CHECK (attempt_no > 0),
    provider_request_id  TEXT,
    request_hash         TEXT NOT NULL,
    status               TEXT NOT NULL
        CHECK (status IN ('SUCCEEDED', 'FAILED')),
    result_hash          TEXT,
    created_at           TEXT NOT NULL,
    terminal_at          TEXT,
    UNIQUE (action_id, attempt_no)
);

INSERT INTO provider_attempt (
    provider_attempt_id, action_id, attempt_no, provider_request_id,
    request_hash, status, result_hash, created_at, terminal_at)
SELECT
    provider_attempt_id, action_id, attempt_no, provider_request_id,
    request_hash, status, result_hash, created_at, terminal_at
FROM provider_attempt_backup;

DROP TABLE provider_attempt_backup;

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '7')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '7')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
