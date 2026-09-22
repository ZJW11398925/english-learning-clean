-- 0012_schedule_review.sql — Phase 6 P6-1: the Scheduler durable core
-- (TASK-OPI-6259f6fd-….12 ②①).
--
-- Two tables land here, and nothing else. This migration is DDL +
-- vocabulary only — no backfill, no rebuild, no row is created by it. The
-- write faces that fill them belong to this same slice: elc.scheduler.store
-- (the durable rows and every SQL statement) behind
-- elc.scheduler.controller (the authority face). Nothing earlier in the
-- chain is touched: 0001–0011 are byte-identical and every table they
-- created keeps its shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §5.2   ScheduleItem — schedule_item_id / target_type /
--                             target_id / evidence_modality / review_state /
--                             review_urgency / next_review_window_start? /
--                             next_review_window_end? / spacing_stage? /
--                             source_learning_watermark / version /
--                             updated_at (twelve columns); the
--                             ``review_state`` vocabulary block beside it —
--                             NOT_SCHEDULED / UPCOMING / DUE / OVERDUE
--                             (the four words; the Phase 0 skeleton's five
--                             words are gone from the source tree);
--                             ReviewEvent — review_event_id /
--                             schedule_item_id / teaching_moment_id? /
--                             source_turn_id? / event_type / engaged /
--                             evidence_group_id? / created_at (eight).
--                             §5.2 spells the ScheduleItem version column
--                             bare ``version`` and this migration keeps that
--                             spelling: the qualified ``schedule_version``
--                             exists as a platform version *type*
--                             (elc.platform.types.ScheduleVersion) and as
--                             ScheduleView's own field, but §5.2's
--                             ScheduleItem block says ``version``, the
--                             object shares the bare name with nothing in
--                             its own block, and no registry binding is
--                             forged for it (see elc/platform/registry.py
--                             and elc/scheduler/types.py, which own the
--                             reading).
--   docs/DOMAIN_MODEL.md §9   Owns: review_state / review_urgency /
--                             next_review_window / spacing_stage. Reads:
--                             learning freshness / last strong retrieval /
--                             stability evidence / teaching/review history
--                             (``source_learning_watermark`` is the durable
--                             form of that read input, carried verbatim);
--                             and the rule these tables exist to keep:
--                             "Learning 不能直接输出 `REVIEW_DUE`；Scheduler
--                             才决定 due/overdue" — the due decision is not
--                             in either table, it is the Scheduler's read of
--                             them (p6-2).
--   docs/DOMAIN_MODEL.md §10  ScheduleView is the Planner's input authority;
--                             ScheduleItem / ReviewEvent are the Scheduler's
--                             own truth, so the view is derived from them
--                             rather than stored beside them.
--   docs/DOMAIN_MODEL.md      D-INV-009 "Scheduler 决定 review due；Learning
--   (line 903)                只提供 freshness" — the modality key below is
--                             the same leg the learning projection keys on,
--                             which is what lets a schedule row be lined up
--                             against freshness without inventing a second
--                             key.
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27    the physical form (column type, index names) is
--                             the implementation's; the element shapes of
--                             §5.2 are declared in elc/scheduler/types.py.
--
-- ---------------------------------------------------------------------------
-- 1. schedule_item — one durable row per (target × evidence modality) (§5.2)
--
-- Column notes (none of them adds a column; they say what each canonical
-- name stores):
--   schedule_item_id        TEXT PRIMARY KEY — §5.2. Opaque identity (typed
--                           ``str``: no platform NewType exists for it, and
--                           this slice mints no id space).
--   target_type             TEXT NOT NULL CHECK — §5.2. The vocabulary is
--                           the one 0004/0005 already enforce (RESOURCE /
--                           CAPABILITY), restated here because this is a new
--                           table rather than a reference to an old one.
--   target_id               TEXT NOT NULL — §5.2. A teaching target
--                           (elc.platform.types.TargetId); no FK, the 0004/
--                           0005 precedent: the target vocabulary is the
--                           content/curriculum side's, and the learning
--                           projection is not foreign-keyed to it either.
--   evidence_modality       TEXT NOT NULL CHECK — §5.2. §24.14's frozen V1
--                           values (TEXT_PRODUCTION / TEXT_COMPREHENSION),
--                           the same CHECK 0004/0005 carry. This CHECK is
--                           also the mechanism face of IP §16 DoD #22 (and
--                           DECISION_REGISTER:20): a voice/audio debt cannot
--                           be written into this table, because both of its
--                           modality columns are the V1 text pair.
--   review_state            TEXT NOT NULL CHECK — §5.2's four words,
--                           enforced by the schema because canonical text
--                           pins them (the 0010 ``episode.status``
--                           precedent: a pinned vocabulary may be a CHECK;
--                           an unpinned one may not — see below).
--   review_urgency          REAL — §5.2 names the column and pins neither a
--                           type nor a value range, so it is carried raw and
--                           nullable (``None`` = not configured) with zero
--                           interpretation: this slice declares no range,
--                           no conversion, and no default *meaning*. The
--                           numeric picture BF-02 sketches (0.0 / 0.25 /
--                           0.75 / 1.0 per state) is the Planner's feature
--                           assembly in Phase 7, never this column's
--                           semantics — the full statement is in
--                           elc/scheduler/types.py (ScheduleItem's
--                           docstring), which owns the reading.
--   next_review_window_start TEXT — §5.2 ``next_review_window_start?``; NULL
--                           = no window declared. ISO-8601 when present; the
--                           caller's declaration, never this store's clock.
--   next_review_window_end  TEXT — §5.2 ``next_review_window_end?``; same.
--                           The two columns are stored as given: this slice
--                           computes no window and compares no timestamps.
--   spacing_stage           TEXT — §5.2 ``spacing_stage?``; NULL = 未分阶.
--                           No CHECK: §5.2 pins no value range, and the
--                           five STAGE_0…STAGE_4 words are elc/scheduler/
--                           types.py's **implementation-declared** list —
--                           freezing an implementation word list into a
--                           canonical column is exactly what a CHECK here
--                           would do (the 0002:78 / 0011:156 precedent).
--                           This slice implements no transition and no
--                           ladder policy.
--   source_learning_watermark TEXT NOT NULL — §5.2. The learning-side
--                           watermark this schedule row was derived from
--                           (DOMAIN_MODEL §9 Reads: "Learning freshness /
--                           last strong retrieval / stability evidence").
--                           Carried verbatim as TEXT: this slice neither
--                           parses nor advances it (the semantics belong to
--                           p6-2's due computation).
--   version                 TEXT NOT NULL — §5.2's bare ``version`` (header).
--                           The store's stamp discipline: a moved version
--                           replaces the content, and the same version with
--                           different content is refused (CONFLICT) instead
--                           of silently rewriting a stamped projection. §5.2
--                           pins no ordering, so versions are compared for
--                           equality and never for order.
--   updated_at              TEXT NOT NULL — §5.2; the store's clock.
--
-- Keying convention (Local V1, declared rather than assumed): §5.2 pins no
-- owner column for ScheduleItem, so the row's key is its content key —
-- UNIQUE(target_type, target_id, evidence_modality), which is the same
-- modality leg the learning projection's primary key carries
-- (learner_target_state's (user_scope_id, target_type, target_id,
-- evidence_modality), migration 0005), minus the user scope column §5.2 does
-- not have. One current schedule row per (target × modality) is the whole
-- meaning of "current projection", and the same key is what an inbound
-- lookup for a target/evidence-modality-delete starts from.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedule_item (
    schedule_item_id          TEXT PRIMARY KEY,
    target_type               TEXT NOT NULL
        CHECK (target_type IN ('RESOURCE', 'CAPABILITY')),
    target_id                 TEXT NOT NULL,
    evidence_modality         TEXT NOT NULL
        CHECK (evidence_modality IN ('TEXT_PRODUCTION',
                                     'TEXT_COMPREHENSION')),
    review_state              TEXT NOT NULL
        CHECK (review_state IN ('NOT_SCHEDULED', 'UPCOMING', 'DUE',
                                'OVERDUE')),
    review_urgency            REAL,
    next_review_window_start  TEXT,
    next_review_window_end    TEXT,
    spacing_stage             TEXT,
    source_learning_watermark TEXT NOT NULL,
    version                   TEXT NOT NULL,
    updated_at                TEXT NOT NULL,
    UNIQUE (target_type, target_id, evidence_modality)
);

-- ---------------------------------------------------------------------------
-- 2. review_event — the append-first review history (§5.2)
--
-- Column notes:
--   review_event_id         TEXT PRIMARY KEY — §5.2. Opaque identity.
--   schedule_item_id        TEXT NOT NULL REFERENCES schedule_item — §5.2.
--                           The event belongs to a real schedule row or it
--                           does not exist (the 0004/0008/0010/0011 FK
--                           convention for a canonical object that names
--                           another canonical object). The FK is why the
--                           store checks the row's existence explicitly
--                           before inserting: a caller gets NOT_FOUND rather
--                           than a bare sqlite error.
--   teaching_moment_id      TEXT REFERENCES teaching_moment(moment_id) —
--                           §5.2 ``teaching_moment_id?``; NULL = the review
--                           event is not tied to a TeachingMoment (a manual
--                           or schedule-driven review). The FK follows 0007's
--                           teaching_moment identity column.
--   source_turn_id          TEXT REFERENCES turn_record(turn_id) — §5.2
--                           ``source_turn_id?``; NULL = no originating turn.
--   event_type              TEXT NOT NULL — §5.2 names the column and pins
--                           **no** vocabulary: neither the canonical
--                           documents nor behavioral_baselines/ declare one
--                           word for it (grepped, not assumed). It is
--                           therefore carried raw as NOT NULL with no CHECK
--                           and no branch-on-value anywhere in this slice —
--                           the first consumer that must branch on a value
--                           is p6-2's review history read, so the word list
--                           is p6-2's to declare (elc/scheduler/types.py
--                           ReviewEvent docstring).
--   engaged                 INTEGER NOT NULL CHECK (engaged IN (0, 1)) —
--                           §5.2; the 0004 ``attempt_observed`` precedent for
--                           a canonical boolean column.
--   evidence_group_id       TEXT REFERENCES evidence_group(evidence_group_id)
--                           — §5.2 ``evidence_group_id?``; NULL = the event
--                           cites no evidence group (a skip, an expiry, a
--                           manual mark). The event's own target/modality
--                           is **not** required to match the group's or the
--                           moment's: §5.2 pins no such constraint, and
--                           inventing one here would be a rule the canonical
--                           set does not make.
--   created_at              TEXT NOT NULL — §5.2; the caller's timestamp when
--                           given and this store's clock otherwise (the
--                           0007 teaching_moment ``created_at or _now()``
--                           precedent).
--
-- Append-first (docs/DATA_MODEL.md §1.3): **no** unique index lands on
-- schedule_item_id, and none on any other column — several review events for
-- one schedule row over time are the history §1.3 asks to keep, and a row is
-- never rewritten in place (the store refuses a differing content under an
-- existing review_event_id rather than updating it). This is the one
-- deliberate structural difference from the schedule_item table above, whose
-- unique index exists because a schedule row is the *current* projection
-- rather than a fact.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_event (
    review_event_id    TEXT PRIMARY KEY,
    schedule_item_id   TEXT NOT NULL
        REFERENCES schedule_item(schedule_item_id),
    teaching_moment_id TEXT REFERENCES teaching_moment(moment_id),
    source_turn_id     TEXT REFERENCES turn_record(turn_id),
    event_type         TEXT NOT NULL,
    engaged            INTEGER NOT NULL CHECK (engaged IN (0, 1)),
    evidence_group_id  TEXT REFERENCES evidence_group(evidence_group_id),
    created_at         TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '12')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '12')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
