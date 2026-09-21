-- 0008_attempt_records.sql — Phase 3 P3-1B attempt / evaluation records
-- (TASK-OPI-5ba74efc-9f26-483b-a7de-c833834275a4.2 ①;设计权威
-- DEC-OPI-2babb21e-bc72-47a2-9382-e773c92211d2.5 Q4/LOR 编排链;
-- docs/IMPLEMENTATION_PLAN.md §1.5 Phase 3 "User-initiated TeachingMoment
-- vertical slice").
--
-- Authority map (canonical column names follow the cited sections
-- verbatim; every column outside the cited sets is individually
-- justified below):
--   docs/DATA_MODEL.md §17    attempt_record — the ten-column set word for
--                             word (attempt_id, moment_id, attempt_index,
--                             user_turn_id, support_level_before_attempt,
--                             answer_exposure_state, exposure_estimate_id?,
--                             support_attribution_certainty,
--                             support_attribution_basis, created_at).
--   docs/DATA_MODEL.md §17    attempt_evaluation_record — the nine-column
--                             set word for word (attempt_evaluation_id,
--                             moment_id, attempt_id, evaluator_id,
--                             evaluator_version, outcome, confidence,
--                             evidence_proposal_refs[], created_at), plus
--                             the §17 normative write-order rule "必须在
--                             下一不可逆教学动作前 durable".
--   docs/STATE_MACHINES.md §5 evaluation outcomes (SUCCESS / PARTIAL /
--                             FAILURE / ALTERNATIVE_SUCCESS / ABSTAIN) as
--                             the outcome CHECK — the §5 five-value set is
--                             preserved at this layer (ALTERNATIVE_SUCCESS
--                             is NOT folded into SUCCESS here; the
--                             capability-positive / resource-neutral
--                             mapping belongs to the Learning evidence
--                             conversion, DEC-…2babb21e.5 Q4).
--   docs/STATE_MACHINES.md §3 support levels (NONE / CONTEXT_ONLY /
--                             SEMANTIC_HINT / STRUCTURAL_HINT /
--                             PARTIAL_FORM / FULL_FORM_SHOWN) as the
--                             support_level_before_attempt CHECK.
--   docs/STATE_MACHINES.md §13 ExposureEstimate certainty
--                             (CONFIRMED_RENDERED / SERVER_SENT_UNCONFIRMED
--                             / UNKNOWN) and exposure_level (NONE /
--                             PARTIAL / FULL) for the two answer-exposure
--                             columns.
--   docs/STATE_MACHINES.md §6 teaching completion outcome (seven words)
--                             and §7 teaching abort reason (fourteen
--                             words) as the two new teaching_moment CHECKs
--                             (review F8's landing point: the completion /
--                             abort vocabularies must be enforced by the
--                             schema, not only by the writer).
--   docs/DATA_MODEL.md §25    UNIQUE(moment_id, attempt_index) is the
--                             canonical key list's attempt identity; one
--                             evaluation per attempt (UNIQUE(attempt_id))
--                             mirrors "a moment carries at most one
--                             evaluation per attempt" and is what makes the
--                             §17 write order checkable after a crash.
--
-- Rebuild order (SQLite: a parent table that children reference cannot be
-- dropped with foreign_keys=ON and non-empty children — the 0007 note):
--   1. the two children of teaching_moment are copied aside and dropped
--      (gate_execution_status; generation_action_intent with its own child
--      provider_attempt);
--   2. teaching_moment is rebuilt with the two new CHECKs and renamed;
--   3. the children are recreated from the 0007 / 0003 DDL verbatim and
--      refilled;
--   4. the two new attempt tables are created (they reference the rebuilt
--      teaching_moment), so they never see a half-rebuilt parent.
--   Everything runs inside the migration runner's single BEGIN IMMEDIATE
--   transaction, so the pair is never observably inconsistent.
--
-- Storage forms (implementation-defined, DATA_MODEL §27): the
-- evidence_proposal_refs[] array column is JSON text — the 0004
-- qualifiers / 0007 reason_codes precedent. support_attribution_basis is
-- free text (the durable trace of WHICH exposure fact the attribution was
-- based on); every enumerated column above carries its vocabulary as a
-- CHECK.
--
-- Scope fence: this migration creates the two P3-1B tables and tightens
-- the two teaching_moment vocabularies. The write faces land in
-- src/elc/teaching (store + attempt/evaluation orchestration).

-- ---------------------------------------------------------------------------
-- 1. Children of teaching_moment copied aside (see the rebuild order note).
-- ---------------------------------------------------------------------------
CREATE TABLE gate_execution_status_backup AS
    SELECT * FROM gate_execution_status;

DROP TABLE gate_execution_status;

CREATE TABLE provider_attempt_backup AS SELECT * FROM provider_attempt;

DROP TABLE provider_attempt;

CREATE TABLE generation_action_intent_backup AS
    SELECT * FROM generation_action_intent;

DROP TABLE generation_action_intent;

-- ---------------------------------------------------------------------------
-- 2. teaching_moment rebuild — same thirty §15 columns; the two nullable
--    outcome columns gain their canonical vocabularies as CHECKs (F8).
-- ---------------------------------------------------------------------------
CREATE TABLE teaching_moment_v8 (
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
    completion_outcome        TEXT
        CHECK (completion_outcome IS NULL OR completion_outcome IN (
            'SUCCESS_UNSUPPORTED', 'SUCCESS_SUPPORTED',
            'SUCCESS_ALTERNATIVE', 'PARTIAL_PROGRESS', 'REVEALED',
            'USER_SATISFIED', 'NO_FURTHER_VALUE')),
    abort_reason              TEXT
        CHECK (abort_reason IS NULL OR abort_reason IN (
            'USER_SKIP', 'USER_REJECTED_TARGET', 'USER_TOPIC_SHIFT',
            'USER_SWITCH_TARGET', 'AMBIGUOUS_EXIT', 'POLICY_STOP',
            'ATTEMPT_LIMIT', 'CONTENT_INVALID', 'SNAPSHOT_INVALIDATED',
            'PRE_DELIVERY_INVALIDATED', 'SYSTEM_FAILURE', 'DELIVERY_FAILURE',
            'EXPIRED', 'SYSTEM_RECOVERY_ABORT')),
    state_version             INTEGER NOT NULL CHECK (state_version > 0),
    created_at                TEXT NOT NULL,
    opened_at                 TEXT,
    teaching_terminal_at      TEXT,
    closed_at                 TEXT
);

INSERT INTO teaching_moment_v8 (
    moment_id, conversation_id, persona_id, source, decision_cycle_id,
    candidate_id, gate_decision_id, focus_target, supporting_targets,
    target_mode, learning_intent, evidence_modality, evidence_goal,
    preferred_support_ceiling, learning_snapshot_id, evidence_watermark,
    curriculum_version, content_version, policy_version, lifecycle_state,
    presentation_phase, attempt_index, support_level, completion_outcome,
    abort_reason, state_version, created_at, opened_at, teaching_terminal_at,
    closed_at)
SELECT
    moment_id, conversation_id, persona_id, source, decision_cycle_id,
    candidate_id, gate_decision_id, focus_target, supporting_targets,
    target_mode, learning_intent, evidence_modality, evidence_goal,
    preferred_support_ceiling, learning_snapshot_id, evidence_watermark,
    curriculum_version, content_version, policy_version, lifecycle_state,
    presentation_phase, attempt_index, support_level, completion_outcome,
    abort_reason, state_version, created_at, opened_at, teaching_terminal_at,
    closed_at
FROM teaching_moment;

DROP TABLE teaching_moment;

ALTER TABLE teaching_moment_v8 RENAME TO teaching_moment;

-- ---------------------------------------------------------------------------
-- 3. Children recreated (DDL verbatim from 0007 / 0003) and refilled.
-- ---------------------------------------------------------------------------
CREATE TABLE generation_action_intent (
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

INSERT INTO generation_action_intent (
    action_id, turn_id, decision_cycle_id, moment_id, assistant_turn_id,
    action_type, generation_contract_id, status, attempt_count, owner_epoch,
    created_at)
SELECT
    action_id, turn_id, decision_cycle_id, moment_id, assistant_turn_id,
    action_type, generation_contract_id, status, attempt_count, owner_epoch,
    created_at
FROM generation_action_intent_backup;

DROP TABLE generation_action_intent_backup;

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

INSERT INTO gate_execution_status (
    gate_execution_status_id, decision_cycle_id, moment_id, gate_context,
    authorization_basis, authorization_status, status, missing_or_unknown,
    created_at)
SELECT
    gate_execution_status_id, decision_cycle_id, moment_id, gate_context,
    authorization_basis, authorization_status, status, missing_or_unknown,
    created_at
FROM gate_execution_status_backup;

DROP TABLE gate_execution_status_backup;

-- ---------------------------------------------------------------------------
-- 4. attempt_record — DATA_MODEL §17, ten columns word for word.
--    attempt_index counts attempts inside one moment starting at 1 (the
--    moment's own attempt_index mirrors that count after each recorded
--    attempt), so UNIQUE(moment_id, attempt_index) is the §25 identity.
-- ---------------------------------------------------------------------------
CREATE TABLE attempt_record (
    attempt_id                    TEXT PRIMARY KEY,
    moment_id                     TEXT NOT NULL
        REFERENCES teaching_moment(moment_id),
    attempt_index                 INTEGER NOT NULL
        CHECK (attempt_index > 0),
    user_turn_id                  TEXT NOT NULL
        REFERENCES user_turn(user_turn_id),
    support_level_before_attempt  TEXT NOT NULL
        CHECK (support_level_before_attempt IN (
            'NONE', 'CONTEXT_ONLY', 'SEMANTIC_HINT', 'STRUCTURAL_HINT',
            'PARTIAL_FORM', 'FULL_FORM_SHOWN')),
    answer_exposure_state         TEXT NOT NULL
        CHECK (answer_exposure_state IN ('NONE', 'PARTIAL', 'FULL')),
    exposure_estimate_id          TEXT,
    support_attribution_certainty TEXT NOT NULL
        CHECK (support_attribution_certainty IN (
            'CONFIRMED_RENDERED', 'SERVER_SENT_UNCONFIRMED', 'UNKNOWN')),
    support_attribution_basis     TEXT NOT NULL,
    created_at                    TEXT NOT NULL,
    UNIQUE (moment_id, attempt_index)
);

-- ---------------------------------------------------------------------------
-- 5. attempt_evaluation_record — DATA_MODEL §17, nine columns word for
--    word; outcome CHECK = STATE_MACHINES §5 five values (all five are
--    kept at this layer). One evaluation per attempt: a second evaluation
--    of the same attempt is a separate explicit re-evaluation (STATE_
--    MACHINES §13 late-ACK rule), never a silent second row.
-- ---------------------------------------------------------------------------
CREATE TABLE attempt_evaluation_record (
    attempt_evaluation_id  TEXT PRIMARY KEY,
    moment_id              TEXT NOT NULL
        REFERENCES teaching_moment(moment_id),
    attempt_id             TEXT NOT NULL UNIQUE
        REFERENCES attempt_record(attempt_id),
    evaluator_id           TEXT NOT NULL,
    evaluator_version      TEXT NOT NULL,
    outcome                TEXT NOT NULL
        CHECK (outcome IN ('SUCCESS', 'PARTIAL', 'FAILURE',
                           'ALTERNATIVE_SUCCESS', 'ABSTAIN')),
    confidence             REAL NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence_proposal_refs TEXT NOT NULL,
    created_at             TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '8')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '8')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
