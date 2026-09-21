-- 0002_conversation_core.sql — Phase 1 P1A durable conversation core
-- (TASK-OPI-091f35c3.11; docs/IMPLEMENTATION_PLAN.md §3).
--
-- Authority map (canonical column names follow the cited sections verbatim;
-- columns outside §3/§4 are individually justified below):
--   docs/DATA_MODEL.md §3        Conversation / UserTurn / AssistantTurn
--                                + Sequence Semantics (turn_sequence /
--                                message_sequence 双序列)
--   docs/DATA_MODEL.md §4        InputEnvelope (client_message_id unique
--                                where present) / TurnRecord
--   docs/DATA_MODEL.md §18       active_teaching_lock 三列 durable unique
--                                (Local V1 无 expiry/heartbeat)
--   docs/DATA_MODEL.md §22.1     projection_job (durable CP4 work)
--   docs/DATA_MODEL.md §19       turn_record.owner_epoch
--   docs/STATE_MACHINES.md §10   turn_record.status / turn_outcome vocabulary
--   docs/STATE_MACHINES.md §20   turn_record.state_version compare-and-swap
--   docs/RUNTIME_ARCHITECTURE.md §17.1  interrupt_request
--   docs/RUNTIME_ARCHITECTURE.md §6     CP0 atomic unit (all tables above are
--                                co-located in app.db so the CP0 short
--                                transaction is truly atomic, DATA_MODEL §2)
--
-- Phase 1 only creates the tables: no teaching flow lives here
-- (IMPLEMENTATION_PLAN §3 "先不做自动教学"); active_teaching_lock /
-- projection_job are durable infrastructure only.

CREATE TABLE IF NOT EXISTS conversation (
    conversation_id       TEXT PRIMARY KEY,
    persona_id            TEXT,
    scene_id              TEXT,
    created_at            TEXT NOT NULL,
    status                TEXT NOT NULL
        CHECK (status IN ('ACTIVE', 'CLOSED')),
    next_turn_sequence    INTEGER NOT NULL CHECK (next_turn_sequence > 0),
    next_message_sequence INTEGER NOT NULL CHECK (next_message_sequence > 0)
);

-- DATA_MODEL §4 InputEnvelope; Unique: "client_message_id where present".
-- The partial unique index makes the uniqueness apply exactly when the value
-- is present (absent client_message_id never dedupes).
CREATE TABLE IF NOT EXISTS input_envelope (
    input_id            TEXT PRIMARY KEY,
    client_message_id   TEXT,
    conversation_id     TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    persona_id          TEXT,
    scene_id            TEXT,
    interaction_channel TEXT NOT NULL,
    raw_payload         TEXT NOT NULL,
    received_at         TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_input_envelope_client_message_id
    ON input_envelope (client_message_id)
    WHERE client_message_id IS NOT NULL;

-- DATA_MODEL §3 UserTurn. One UserTurn per coordination turn (turn_id
-- UNIQUE); the turn's AssistantTurn? shares turn_id/turn_sequence and takes
-- its own message_sequence (§3 Sequence Semantics).
CREATE TABLE IF NOT EXISTS user_turn (
    user_turn_id        TEXT PRIMARY KEY,
    turn_id             TEXT NOT NULL UNIQUE,
    conversation_id     TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    turn_sequence       INTEGER NOT NULL,
    message_sequence    INTEGER NOT NULL,
    input_id            TEXT NOT NULL REFERENCES input_envelope(input_id),
    client_message_id   TEXT,
    interaction_channel TEXT NOT NULL,
    raw_content         TEXT NOT NULL,
    normalized_content  TEXT,
    created_at          TEXT NOT NULL,
    UNIQUE (conversation_id, turn_sequence),
    UNIQUE (conversation_id, message_sequence)
);

-- DATA_MODEL §3 AssistantTurn (canonical transcript rows only — undelivered
-- provider output never enters the transcript, DOMAIN_MODEL §3 key rule).
-- delivery_state has no durable CHECK: the canonical text names the column
-- but pins no vocabulary (adjudicated DEC-…091f35c3.7); the store derives
-- canonicalization-eligible values from STATE_MACHINES §13 semantics.
CREATE TABLE IF NOT EXISTS assistant_turn (
    assistant_turn_id  TEXT PRIMARY KEY,
    turn_id            TEXT NOT NULL UNIQUE,
    conversation_id    TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    turn_sequence      INTEGER NOT NULL,
    message_sequence   INTEGER NOT NULL,
    action_id          TEXT NOT NULL,
    content            TEXT NOT NULL,
    delivery_state     TEXT NOT NULL,
    delivery_certainty TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    UNIQUE (conversation_id, turn_sequence),
    UNIQUE (conversation_id, message_sequence)
);

-- DATA_MODEL §4 TurnRecord, plus:
--   owner_epoch     — DATA_MODEL §19 ConversationCoordinatorLease physical
--                     mapping ("TurnRecord.owner_epoch"); restart fencing,
--                     RUNTIME_ARCHITECTURE §24.
--   state_version   — STATE_MACHINES §20: all multi-event state transitions
--                     use "state_version + compare-and-swap".
--   active_decision_cycle_id is nullable per §4 and stays a plain
--   back-reference (no FK), exactly like the 0006 gate_decision_id
--   precedent; its writer is the Runtime-owned DecisionCycle store
--   (Phase 3 P3-1A, TASK-OPI-2babb21e-….17 ②). This clears the stale
--   Phase 1 note that pointed the generation-side tighten at "Phase 2"
--   (adjudicated DEC-…091f35c3.7): that tighten is the
--   generation_action_intent rebuild in migration 0007.
CREATE TABLE IF NOT EXISTS turn_record (
    turn_id                  TEXT PRIMARY KEY,
    conversation_id          TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    turn_sequence            INTEGER NOT NULL,
    input_id                 TEXT NOT NULL REFERENCES input_envelope(input_id),
    status                   TEXT NOT NULL
        CHECK (status IN (
            'RECEIVED', 'USER_COMMITTED', 'ANALYZING', 'DECIDING',
            'GENERATING', 'DELIVERING', 'DELIVERY_TERMINAL', 'POSTPROCESSING',
            'COMPLETED', 'CANCELLED_BY_USER', 'FAILED_RECOVERABLE',
            'FAILED_FINAL')),
    active_decision_cycle_id TEXT,
    failure_class            TEXT,
    failure_reason           TEXT,
    runtime_version          TEXT NOT NULL,
    started_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,
    terminal_at              TEXT,
    turn_outcome             TEXT
        CHECK (turn_outcome IS NULL OR turn_outcome IN (
            'REPLIED_FULL', 'REPLIED_PARTIAL', 'NO_ASSISTANT_OUTPUT',
            'CANCELLED_BY_USER', 'FAILED_USER_VISIBLE')),
    owner_epoch              INTEGER NOT NULL,
    state_version            INTEGER NOT NULL CHECK (state_version > 0)
);

-- RUNTIME_ARCHITECTURE §17.1 Conversation Interrupt / Input Queue: a barge-in
-- request is durable while the old coordinator still holds the guard. The
-- interrupt rides the input queue keyed by the new input's input_id
-- (InterruptRequest(active_turn_id, action_id, new_input_id)).
CREATE TABLE IF NOT EXISTS interrupt_request (
    input_id         TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    active_turn_id   TEXT,
    active_action_id TEXT,
    reason           TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

-- DATA_MODEL §18 TeachingLockLease — Local V1 canonical durable
-- representation, three columns exactly: conversation_id UNIQUE/PK,
-- moment_id UNIQUE, state_version. No expiry/heartbeat column (§18: "Local
-- V1 不需要 expiry/heartbeat"). Phase 1 only creates the table; acquisition
-- happens with CP2 in the teaching phase.
CREATE TABLE IF NOT EXISTS active_teaching_lock (
    conversation_id TEXT PRIMARY KEY,
    moment_id       TEXT NOT NULL UNIQUE,
    state_version   INTEGER NOT NULL CHECK (state_version > 0)
);

-- DATA_MODEL §22.1 ProjectionArtifact / ProjectionJob — durable CP4 work;
-- retry is source-aware + version-aware revalidation (status vocabulary is
-- the §22.1 list, enforced durably).
CREATE TABLE IF NOT EXISTS projection_job (
    projection_id          TEXT PRIMARY KEY,
    projection_type        TEXT NOT NULL,
    source_turn_id         TEXT NOT NULL,
    source_turn_slice_hash TEXT NOT NULL,
    base_domain_version    TEXT,
    status                 TEXT NOT NULL
        CHECK (status IN
            ('PENDING', 'RUNNING', 'COMMITTED', 'FAILED_RETRYABLE',
             'REJECTED')),
    attempt_count          INTEGER NOT NULL CHECK (attempt_count >= 0),
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '2')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '2')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
