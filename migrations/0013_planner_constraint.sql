-- 0013_planner_constraint.sql — Phase 6 P6-3: the TeachingPreference /
-- PlannerConstraint durable row (TASK-OPI-5a0be06d-….20 ③.1).
--
-- One table lands here, and nothing else. This migration is DDL + vocabulary
-- only — no backfill, no rebuild, no row is created by it. The write faces
-- that fill it belong to this same slice: elc.user_config.store (the durable
-- rows and every SQL statement) behind elc.user_config.controller (the
-- authority face). Nothing earlier in the chain is touched: 0001–0012 are
-- byte-identical (0012's header comment included, expired predictions and
-- all — this cut does not edit that file) and every table they created keeps
-- its shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §9     TeachingPreference / PlannerConstraint
--                             (lines 586–607) — constraint_id / target_type? /
--                             target_id? / constraint_type / scope /
--                             starts_at / expires_at? / created_from_turn_id?
--                             / active (nine columns, in this order); the
--                             block's Types list — DO_NOT_AUTO_TEACH /
--                             SUPPRESS_REVIEW / JUST_CHAT / MANUAL_FOCUS
--                             (four words); and its Scope list — THIS_SESSION
--                             / UNTIL_DATE / UNTIL_USER_REENABLES (three).
--                             Both vocabularies are canonical text pinned by
--                             §9, so both are enforced by the schema below
--                             (the 0010 ``episode.status`` precedent for a
--                             pinned vocabulary; an unpinned one may not be
--                             frozen there — see the 0012 header for that
--                             half of the rule).
--   docs/DOMAIN_MODEL.md §18.1 TRUSTED_AUTHORITY: a typed user setting is the
--                             user's own statement. The constraint row is
--                             that setting's durable form, which is why its
--                             columns are never derived from a model's
--                             inference and why ``created_from_turn_id`` is
--                             the only turn leg it carries.
--   docs/DATA_MODEL.md §24.14 modal vocabulary separation: this table carries
--                             no evidence modality at all — a constraint
--                             suppresses or permits teaching, it is never an
--                             evidence source.
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27    the physical form (column type, index names) is
--                             the implementation's; the element shape of §9
--                             is declared in elc/user_config/types.py.
--
-- ---------------------------------------------------------------------------
-- 1. planner_constraint — one durable user constraint (§9)
--
-- Column notes (none of them adds a column; they say what each canonical name
-- stores):
--   constraint_id           TEXT PRIMARY KEY — §9. Opaque identity. No
--                           platform NewType exists for it and this cut mints
--                           no id space, so it is typed ``str`` (the
--                           ScheduleItem / SessionFocus id precedent).
--   target_type             TEXT CHECK — §9 ``target_type?``; NULL = the
--                           constraint is **not target-limited** (it speaks
--                           about teaching / review / chat in general). The
--                           vocabulary is the one 0004/0005/0012 already
--                           enforce (RESOURCE / CAPABILITY), restated here
--                           because this is a new table rather than a
--                           reference to an old one. The column is nullable,
--                           so the CHECK only constrains the values that are
--                           present (SQLite: a NULL operand makes the
--                           comparison NULL, which is not a violation).
--   target_id               TEXT — §9 ``target_id?``; NULL = no target named.
--                           A teaching target; no FK, the 0004/0005/0012
--                           precedent: the target vocabulary belongs to the
--                           content/curriculum side.
--   constraint_type         TEXT NOT NULL CHECK — §9's four Types words,
--                           verbatim. Canonical text pins the list, so the
--                           schema freezes it; a fifth word is a canonical
--                           revision, not an implementation choice.
--   scope                   TEXT NOT NULL CHECK — §9's three Scope words,
--                           verbatim (§9 writes "Scope 例如", which is why the
--                           header says the three words are carried exactly
--                           as given rather than treated as an open set this
--                           cut may extend). THIS_SESSION's conversation
--                           binding has no column anywhere in §9 — the
--                           vocabulary is carried, and how a consumer decides
--                           which session is current is **not** decided
--                           here (elc/user_config/store.py registers the
--                           reading).
--   starts_at               TEXT NOT NULL — §9. ISO-8601 when the caller
--                           declares it; the caller's declaration, never this
--                           store's clock. §9 pins no format and this
--                           migration pins none either (no CHECK, no
--                           generated column).
--   expires_at              TEXT — §9 ``expires_at?``; NULL = no end declared
--                           (an UNTIL_USER_REENABLES constraint is exactly
--                           that). Same ISO-8601 convention, same absence of
--                           a CHECK.
--   created_from_turn_id    TEXT REFERENCES turn_record(turn_id) — §9
--                           ``created_from_turn_id?``; NULL = the constraint
--                           was not written from a turn (the "别自动教" a user
--                           states in a settings face rather than in chat).
--                           The FK follows 0007/0012's turn identity column.
--   active                  INTEGER NOT NULL CHECK (active IN (0, 1)) — §9.
--                           The 0004 ``attempt_observed`` precedent for a
--                           canonical boolean column: the canonical set's
--                           ``active`` is a flag, and this is the flag's
--                           durable form. **It is the one column a constrained
--                           update may move** — see the derived judgement
--                           below.
--
-- No UNIQUE and no index: §9 gives the object no second key (one constraint
-- per ``constraint_id``, and nothing says a target may carry only one
-- constraint — a user may hold DO_NOT_AUTO_TEACH and SUPPRESS_REVIEW on the
-- same target at once), and canonical text names no index here. The absence of
-- a unique index is also what keeps the row append-first in the sense §1.3
-- asks for: a new constraint is a new ``constraint_id``.
--
-- ---------------------------------------------------------------------------
-- Derived judgements carried by this migration (NOT canonical text)
--
-- **Ownership (R1).** §9's heading is "TeachingPreference / PlannerConstraint"
-- and its shape is a user-level setting (a typed preference with three scopes,
-- a ``created_from_turn_id?`` provenance leg, and an ``active`` flag a user
-- re-enables). §5.1's Owns list for User Configuration / Profile does **not**
-- name PlannerConstraint, so this is a derived placement rather than a quoted
-- one, and the reasons are: §9 is a preference object; §18.1's
-- TRUSTED_AUTHORITY treats a typed user setting as the user's own statement;
-- and all three scopes (THIS_SESSION / UNTIL_DATE / UNTIL_USER_REENABLES) are
-- user-level lifecycles rather than per-target learning state. The row
-- therefore lives with the other user configuration rows (elc.user_config),
-- and the registry entry records the same placement.
--
-- **``active`` is the one column an update may move (R6).** §9 carries no
-- ``version`` / ``revision`` column, so a row cannot be re-stamped and a
-- content change under an unchanged id is refused instead of applied (the
-- SessionFocus precedent, elc/user_config/store.py). ``active`` is the single
-- exception, and it is deliberately **not** reachable through the content-write
-- face: BF-03 makes re-enabling a suppressed constraint the User Constraint
-- layer's act ("Gate 不偷偷修改用户约束"), so a transfer face exists for the flag
-- alone. The full statement, with the refusal rules, is in
-- elc/user_config/store.py and elc/user_config/types.py.
--
-- **This migration decides nothing about the constraint's effect.** No
-- Planner reads this table in this cut, no Gate consults it, and nothing here
-- creates a constraint from user speech: the durable truth lands, and the
-- application faces (PlannerConstraintView in Phase 7, TARGET_SUPPRESSED in
-- Phase 8) are later cuts.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS planner_constraint (
    constraint_id        TEXT PRIMARY KEY,
    target_type          TEXT
        CHECK (target_type IN ('RESOURCE', 'CAPABILITY')),
    target_id            TEXT,
    constraint_type      TEXT NOT NULL
        CHECK (constraint_type IN ('DO_NOT_AUTO_TEACH', 'SUPPRESS_REVIEW',
                                   'JUST_CHAT', 'MANUAL_FOCUS')),
    scope                TEXT NOT NULL
        CHECK (scope IN ('THIS_SESSION', 'UNTIL_DATE',
                         'UNTIL_USER_REENABLES')),
    starts_at            TEXT NOT NULL,
    expires_at           TEXT,
    created_from_turn_id TEXT REFERENCES turn_record(turn_id),
    active               INTEGER NOT NULL CHECK (active IN (0, 1))
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '13')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '13')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
