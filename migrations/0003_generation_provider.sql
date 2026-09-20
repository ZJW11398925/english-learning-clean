-- 0003_generation_provider.sql — Phase 1 P1B generation/provider tables
-- (TASK-OPI-d7937fd7.9; docs/IMPLEMENTATION_PLAN.md §3).
--
-- Authority map (canonical column names follow the cited sections verbatim;
-- columns outside §20 are individually justified below):
--   docs/DATA_MODEL.md §20  GenerationActionIntent / ProviderAttempt column
--                            sets, word for word:
--                            action_id, turn_id, decision_cycle_id, moment_id?,
--                            assistant_turn_id, action_type,
--                            generation_contract_id, status, attempt_count,
--                            created_at;
--                            provider_attempt_id, action_id, attempt_no,
--                            provider_request_id?, request_hash, status,
--                            result_hash?, created_at, terminal_at?
--   docs/DATA_MODEL.md §25  UNIQUE(action_id, provider_attempt attempt_no)
--   docs/STATE_MACHINES.md §14   status vocabulary: PREPARED / REQUESTED /
--                            GENERATING / VALIDATING / READY_TO_DELIVER /
--                            DELIVERING / TERMINAL (seven values, word for
--                            word; corrects the Phase 0 six-value deviation,
--                            DEC-OPI-091f35c3.7)
--   docs/DATA_MODEL.md §19   generation_action_intent.owner_epoch — the
--                            lease's physical mapping includes
--                            "GenerationAction owner/action state" alongside
--                            TurnRecord.owner_epoch; restart fencing
--                            (RUNTIME_ARCHITECTURE §24) needs the durable
--                            epoch stamp on the action too.
--   docs/RUNTIME_ARCHITECTURE.md §6 CP2.5   ProviderAttempt = provider
--                            action log; every attempt (including failed /
--                            no-output ones) leaves a durable row.
--
-- Deviations / adjudications (each minimal, no silent widening):
--   * decision_cycle_id is NULLABLE here: canonical §20 lists it as a
--     required column, but Phase 1 has no DecisionCycle yet
--     (IMPLEMENTATION_PLAN §3); Phase 2 (decision phases) tightens it to
--     NOT NULL (adjudicated DEC-OPI-091f35c3.7 for the sibling
--     turn_record.active_decision_cycle_id; same transition window).
--   * provider_attempt.status carries no canonical vocabulary (§20 names
--     the column, pins no value list); P1B pins the minimal deterministic
--     set SUCCEEDED / FAILED below — revisit when a later phase needs
--     in-flight attempt states.
--   * No provider CHECK on generation_action_intent.assistant_turn_id: the
--     id is minted at action creation (stable opaque id, DATA_MODEL §1.2)
--     and realized as the assistant_turn row only at canonicalization
--     (CP3a); the back-reference survives as plain data.

CREATE TABLE IF NOT EXISTS generation_action_intent (
    action_id               TEXT PRIMARY KEY,
    turn_id                 TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    decision_cycle_id       TEXT,
    moment_id               TEXT,
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

-- DATA_MODEL §20 ProviderAttempt + §25 UNIQUE(action_id, attempt_no):
-- action-level retry means "same stable action_id, one more attempt row"
-- (RUNTIME_ARCHITECTURE §16 / §24.1: never re-run the whole turn).
CREATE TABLE IF NOT EXISTS provider_attempt (
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

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '3')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '3')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
