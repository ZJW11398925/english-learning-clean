-- 0036_action_replan.sql — V3-6R (the external review's HIGH-1; TASK-OPI-
-- dc1bafdf…33 / the opening ruling DEC-OPI-dc1bafdf…31, DECISION_REGISTER
-- v1.5.2).
--
-- One new table: the **durable replan obligation** a ruling's
-- ``replan_scope ≠ NONE`` leaves behind — the crash-proof anchor between
-- NCP-2's one short transaction and the plan face that consumes the
-- verdict.
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1's "V3-6R 落法" block, column for column:
--     ``action_replan`` — ``replan_request_id`` TEXT PRIMARY KEY
--     (**derived** ``f"rp:{gate_id}:{submission_id}"`` — the stable
--     function of the action family's ``action_commit_key``),
--     ``user_action_id`` NOT NULL **UNIQUE** REFERENCES
--     ``user_action(user_action_id)`` (one action carries at most one
--     obligation), ``scope`` NOT NULL CHECK ``('SCENE','CHAPTER')``
--     (``NONE`` never births a row — zero rows is "no obligation"),
--     ``status`` NOT NULL CHECK ``('PENDING','APPLIED')``,
--     ``target_ref`` TEXT NULL (**eager claim**: the claimed target
--     revision's identity — ``dossier_id`` for SCENE, ``chapter_plan_id``
--     for CHAPTER — written **before** the plan change executes, so a
--     retry converges on the same revision; the **composite CHECK**
--     ``status <> 'APPLIED' OR target_ref IS NOT NULL`` makes the
--     complete step unwritable without a claim), the bookkeeping pair
--     and ``state_version`` NOT NULL CHECK > 0 (the house CAS
--     discipline).
--   * STATE_MACHINES §25's "V3-6R 落法" — the consumption protocol
--     ``claim → work → complete`` (all three steps idempotent; the claim
--     is the crash retry's convergence anchor) lives in
--     :mod:`elc.world.action`'s helpers; ``ScenePlanner.replan_scene`` /
--     ``Director.apply_action_replan`` are the two consumers, entered by
--     ``replan_request_id``.
--   * STATE_MACHINES §23's V3-6R tightening ① (``RESOLVING`` is the only
--     door into ``COMMITTED``) and ② (one un-``CLOSED`` gate per scene)
--     — both native to the code faces, nothing to store here.
--   * RUNTIME_ARCHITECTURE §28 (the NCP-2 arm ⑧ — the obligation's
--     birth inside the same short atomic group) / §29 (the recovery
--     scan's fifth family: ``PENDING`` obligations).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- FK chain (all keep-side): obligation → action → gate → scene →
-- chapter → world. The table joins ``GLOBAL_CONTENT_TABLES``' keep side
-- (20 → 21 members, the chronological tail append: 0029 → 0030 → 0031 →
-- 0033 → 0034 → 0035 → 0036) — deletion pins ride along.
--
-- No index anywhere: the MVP's pending-obligation slice is single
-- digits, a scan is the honest cost (0028–0035's posture). No ON DELETE
-- clause: SQLite's default NO ACTION (the RESTRICT posture) is this
-- cut's whole deletion story, the same posture 0023–0035 spell. The
-- table must be built after 0035: its ``user_action_id`` FK names a
-- table 0035 creates.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_replan (
    replan_request_id TEXT PRIMARY KEY,
    user_action_id TEXT NOT NULL UNIQUE REFERENCES user_action(user_action_id),
    scope        TEXT NOT NULL CHECK (scope IN ('SCENE','CHAPTER')),
    status       TEXT NOT NULL CHECK (status IN ('PENDING','APPLIED')),
    target_ref   TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    CHECK (status <> 'APPLIED' OR target_ref IS NOT NULL));

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '36')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '36')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
