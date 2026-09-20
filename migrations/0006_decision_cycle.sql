-- 0006_decision_cycle.sql — Phase 3 P3-0 DecisionCycle table
-- (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.55 ④;
-- docs/IMPLEMENTATION_PLAN.md §5 Phase 3).
--
-- Authority map:
--   docs/DATA_MODEL.md §4 DecisionCycle — the column set below is the
--                            §4:165-192 list word for word:
--                            decision_cycle_id, turn_id, cycle_index,
--                            learning_snapshot_id, evidence_watermark,
--                            curriculum_version, goal_version,
--                            schedule_version, policy_version,
--                            context_view_version,
--                            relationship_view_version?, planner_decision_id?,
--                            gate_decision_id?, created_at;
--                            Unique (turn_id, cycle_index).
--
-- Scope fence (P3-0): the TABLE only. No write face is created in this
-- slice — decision_cycle rows are first written when P3-1 lands the
-- lineage semantics, which is also the window where
-- generation_action_intent.decision_cycle_id / turn_record.
-- active_decision_cycle_id tighten from nullable (DEC-…091f35c3.7 b
-- successor note updated in migration 0003 by this same task).
--
-- Physical decisions (each minimal, no silent widening):
--   * CHECK (cycle_index >= 0) — §4 pins no vocabulary; the guard only
--     excludes negative indices (a physical domain invariant, not a
--     canonical word list).
--   * CHECK (evidence_watermark >= 0) — mirrors the 0004 watermark
--     semantics (durable, monotonic from 0).
--   * No FK from planner_decision_id / gate_decision_id: those tables do
--     not exist yet (their phases have not arrived); the back-references
--     stay plain data exactly as turn_record.active_decision_cycle_id
--     does in 0002.
--   * No CHECK on the six *_version columns: §4 pins no vocabulary; they
--     are opaque version strings owned by their respective domains.
CREATE TABLE IF NOT EXISTS decision_cycle (
    decision_cycle_id         TEXT PRIMARY KEY,
    turn_id                   TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    cycle_index               INTEGER NOT NULL CHECK (cycle_index >= 0),
    learning_snapshot_id      TEXT NOT NULL,
    evidence_watermark        INTEGER NOT NULL CHECK (evidence_watermark >= 0),
    curriculum_version        TEXT NOT NULL,
    goal_version              TEXT NOT NULL,
    schedule_version          TEXT NOT NULL,
    policy_version            TEXT NOT NULL,
    context_view_version      TEXT NOT NULL,
    relationship_view_version TEXT,
    planner_decision_id       TEXT,
    gate_decision_id          TEXT,
    created_at                TEXT NOT NULL,
    UNIQUE (turn_id, cycle_index)
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '6')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '6')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
