-- 0011_goal_policy_focus.sql — Phase 6 P6-0: the Goal / Policy / SessionFocus
-- durable rows (TASK-OPI-a68fd9eb-….48 ③).
--
-- Three tables land here, and nothing else. This migration is DDL +
-- vocabulary only — no backfill, no rebuild, no row is created by it. The
-- write faces that fill them belong to this same slice: elc.user_config.store
-- (the durable rows and every SQL statement) behind
-- elc.user_config.controller (the authority face). Nothing earlier in the
-- chain is touched: 0001–0010 are byte-identical and every table they
-- created keeps its shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §5.1   LearningGoalPortfolio — goal_portfolio_id /
--                             version / goals[] / modality_weights /
--                             assessment_targets[] / register_style_goals[] /
--                             effective_from / updated_at (eight columns);
--                             TeachingPolicyProfile — teaching_policy_
--                             profile_id / version / mode /
--                             teaching_frequency / interruption_budget /
--                             curriculum_initiative / correction_strictness /
--                             hint_policy / assessment_visibility /
--                             practice_density / persona_freedom /
--                             effective_from / updated_at (thirteen);
--                             SessionFocus — session_focus_id /
--                             conversation_id / base_goal_portfolio_version /
--                             temporary_goal_weights / manual_focus_target? /
--                             starts_at / expires_at? (seven).
--                             §5.1 spells the version column ``version`` in
--                             each object block; the columns here are the
--                             *qualified* names goal_version / policy_version
--                             — the rationale (DATA_MODEL's own DecisionCycle
--                             block spells them qualified;
--                             elc.platform.types.VERSION_FIELDS binds a
--                             version type by field name, and three objects
--                             share the bare name), the known limitation and
--                             the revisit condition are stated in full in
--                             elc/user_config/types.py, which owns the
--                             spelling.
--   docs/DOMAIN_MODEL.md §5.1 Owns: LearningGoalPortfolio,
--                             TeachingPolicyProfile, SessionFocus ("Goal/
--                             Policy/Profile owned by User Configuration/
--                             Profile authority, not Learning"), and the two
--                             rules these tables exist to keep: "Goal/Policy
--                             是 versioned configuration，不是 Learning
--                             Evidence" and "`GlobalGoalPortfolio` 可被
--                             `SessionFocus` 临时重加权，但不能静默修改长期
--                             目标" — the latter is why session_focus is its
--                             own table with its own rows and why writing one
--                             never touches a goal_portfolio row.
--   docs/PRODUCT_CONTRACT.md §4.7  Goal/Policy/Profile authority: these
--                             objects "可以影响 Planner / Persona Runtime 的
--                             view，但不能直接改写 Learning Evidence 或
--                             Learner State" — the durable columns below are
--                             configuration, readable by the planner/persona
--                             views and writable by nothing else.
--   docs/DATA_MODEL.md §1.3   Append-first for facts: a SessionFocus is a
--                             temporary re-weighting with a start/expiry
--                             window, so a *new* focus is a new row (a new
--                             session_focus_id), never an in-place rewrite of
--                             the previous one — which is also why no unique
--                             index on conversation_id lands here (several
--                             focuses for one conversation over time are the
--                             history §1.3 asks to keep; the episode table,
--                             whose whole point is one row per conversation,
--                             added one in 0010).
--   docs/DATA_MODEL.md §1.4   Version every derived model: the two versioned
--                             objects carry their stamp in a column
--                             (goal_version / policy_version) and the store
--                             refuses a content change under an unchanged
--                             stamp. SessionFocus has **no** stamp column in
--                             §5.1 at all, so its identity (session_focus_id)
--                             is one-shot and the store refuses a content
--                             change under it rather than rewriting a row
--                             nothing could version (elc.user_config.store).
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27    the physical form (column type, index names)
--                             is the implementation's; the *element* shapes
--                             of §5.1's list/map columns are declared in
--                             elc.user_config.types (LearningGoal, the
--                             GoalModality → float weight maps, the str
--                             tuples) and stored as JSON text, the 0004
--                             qualifier-list / 0009 / 0010 precedent: a
--                             canonical list stays one column, never a
--                             second table.
--
-- ---------------------------------------------------------------------------
-- 1. goal_portfolio — the versioned long-term goals (§5.1)
--
-- Column notes (none of them adds a column; they say what each canonical
-- name stores):
--   goal_portfolio_id       TEXT PRIMARY KEY — §5.1. The id is the user's own
--                           id (elc.user_config.types types it ``UserId``):
--                           Local V1 has one portfolio per user, and §5.1
--                           pins no separate owner column to link them — the
--                           user_profile_id / disclosure_policy_id precedent
--                           in 0010.
--   goal_version            TEXT NOT NULL — §5.1's ``version`` under the
--                           qualified spelling (header above). The store's
--                           stamp discipline: a moved version replaces the
--                           content, and the same version with different
--                           content is refused (CONFLICT) instead of
--                           silently rewriting a stamped configuration.
--   goals                   TEXT NOT NULL — §5.1 ``goals[]``; JSON array of
--                           ``{"goal_id": …, "goal_modality": …,
--                           "description": …}`` (types.LearningGoal). The
--                           modality vocabulary is elc.platform.types.
--                           GoalModality (ARCHITECTURE_BASELINE §6) — the
--                           goal modality, never an EvidenceModality
--                           (DATA_MODEL §24.14).
--   modality_weights        TEXT NOT NULL — §5.1 ``modality_weights``; JSON
--                           object ``{GoalModality value: float}``.
--   assessment_targets      TEXT NOT NULL — §5.1 ``assessment_targets[]``;
--                           JSON array of strings (the declaration lives in
--                           types; §5.1 pins no element id space).
--   register_style_goals    TEXT NOT NULL — §5.1 ``register_style_goals[]``;
--                           JSON array of strings.
--   effective_from          TEXT NOT NULL — §5.1; ISO-8601, **the caller's**
--                           declaration of when the configuration takes
--                           effect. The store never invents one (only
--                           updated_at is its clock); "not configured" is
--                           the empty string, which is what a caller that
--                           did not say leaves here.
--   updated_at              TEXT NOT NULL — §5.1; the store's clock.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goal_portfolio (
    goal_portfolio_id    TEXT PRIMARY KEY,
    goal_version         TEXT NOT NULL,
    goals                TEXT NOT NULL,
    modality_weights     TEXT NOT NULL,
    assessment_targets   TEXT NOT NULL,
    register_style_goals TEXT NOT NULL,
    effective_from       TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 2. teaching_policy — the versioned how/how-often configuration (§5.1)
--
-- Column notes:
--   teaching_policy_profile_id TEXT PRIMARY KEY — §5.1. As with the
--                           portfolio, §5.1 pins no owner column: Local V1
--                           keys the policy by the user's own id
--                           (types.TeachingPolicyProfile types it ``UserId``).
--   policy_version          TEXT NOT NULL — §5.1's ``version``, qualified
--                           (header); same stamp discipline as above.
--   mode                    TEXT — §5.1. Carried raw, nullable: §5.1 pins no
--                           value range, so the schema holds no vocabulary
--                           for it and the store interprets nothing (``None``
--                           = not configured). The same holds for the seven
--                           columns below it (interruption_budget /
--                           curriculum_initiative / correction_strictness /
--                           hint_policy / assessment_visibility /
--                           practice_density / persona_freedom): eight
--                           unpinned columns, deliberately bare TEXT with no
--                           CHECK — inventing a word list here would freeze
--                           an implementation guess into a canonical column
--                           (types module docstring: "禁发明新枚举/新词表").
--   teaching_frequency      TEXT NOT NULL — §5.1 names the column and pins no
--                           value range; this repository's
--                           TeachingFrequency enum (OFF / MINIMAL / BALANCED
--                           / EAGER) is an implementation declaration, **not**
--                           a canonical vocabulary — which is exactly why no
--                           CHECK lands on this column either (a CHECK would
--                           make an implementation word list a schema
--                           constraint; the §17/§5 vocabularies that *are*
--                           canonical — 0008's outcomes — were enforced by
--                           the schema because canonical text pinned them).
--   effective_from          TEXT NOT NULL — §5.1; ISO-8601, the caller's
--                           declaration (never the store's clock).
--   updated_at              TEXT NOT NULL — §5.1; the store's clock.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teaching_policy (
    teaching_policy_profile_id TEXT PRIMARY KEY,
    policy_version             TEXT NOT NULL,
    mode                       TEXT,
    teaching_frequency         TEXT NOT NULL,
    interruption_budget        TEXT,
    curriculum_initiative      TEXT,
    correction_strictness      TEXT,
    hint_policy                TEXT,
    assessment_visibility      TEXT,
    practice_density           TEXT,
    persona_freedom            TEXT,
    effective_from             TEXT NOT NULL,
    updated_at                 TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 3. session_focus — the temporary re-weighting of a conversation (§5.1)
--
-- Column notes:
--   session_focus_id        TEXT PRIMARY KEY — §5.1. Opaque identity (typed
--                           ``str``: no platform NewType exists for it, and
--                           this slice mints no id space). One-shot by
--                           construction: §5.1 gives SessionFocus no version
--                           stamp, so the store refuses a content change
--                           under an unchanged id instead of rewriting a row
--                           nothing could version (header §1.3/§1.4).
--   conversation_id         TEXT NOT NULL REFERENCES conversation — §5.1.
--                           The FK is the repo-wide convention for a
--                           canonical object that names a conversation
--                           (episode 0010, teaching_moment 0008, evidence_
--                           group 0004): a focus belongs to a real
--                           conversation or it does not exist. No unique
--                           index: several focuses for one conversation over
--                           time are the append-first history (header).
--   base_goal_portfolio_version TEXT NOT NULL — §5.1. The portfolio version
--                           this focus was derived from: the link that lets a
--                           re-weighting say which goals it re-weights,
--                           without a FK — a portfolio version is a content
--                           stamp, and the portfolio row it names may be
--                           replaced by a later version while this focus
--                           keeps naming the one it was built against (§1.4
--                           is a stamp, not a pointer).
--   temporary_goal_weights  TEXT NOT NULL — §5.1; JSON object
--                           ``{GoalModality value: float}``, the same
--                           declared shape as modality_weights.
--   manual_focus_target     TEXT — §5.1 ``manual_focus_target?``; NULL is the
--                           normal case (no manual focus declared). A
--                           ``TargetId`` when present: a manual focus names a
--                           teaching target, not a goal (types.SessionFocus).
--   starts_at               TEXT NOT NULL — §5.1; ISO-8601, the caller's
--                           window start (never the store's clock).
--   expires_at              TEXT — §5.1 ``expires_at?``; NULL is an
--                           open-ended focus.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_focus (
    session_focus_id            TEXT PRIMARY KEY,
    conversation_id             TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    base_goal_portfolio_version TEXT NOT NULL,
    temporary_goal_weights      TEXT NOT NULL,
    manual_focus_target         TEXT,
    starts_at                   TEXT NOT NULL,
    expires_at                  TEXT
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '11')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '11')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
