-- 0037_actor_memory_chapter_settlement.sql — V3-7 (the opening ruling
-- DEC-OPI-d274a7fb…6, DECISION_REGISTER v1.6.0).
--
-- Two new tables: the **actor memory / belief** materialization (the
-- memory six-way split's fourth domain — what the actors of the world
-- know, witnessed or heard) and the **chapter settlement** (the
-- chapter-end compression product — Narrative Memory's compressed half,
-- NCP-4's only row).
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1's "V3-7 落表形" block, column for column
--     (the block header's own note: the fields are semantic fields; the
--     column names below are this cut's spelling of them, the semantic
--     boundaries unchanged):
--     ``actor_memory`` — ``memory_id`` TEXT PRIMARY KEY (**derived**
--     ``f"mem:{event_id}:{participant_id}:{kind}"``: one event, one
--     participant, one kind — at most one row; append-only, the
--     derivation serves idempotent replay only, §26.2.2's lineage
--     discipline), ``world_id`` NOT NULL REFERENCES ``world``,
--     ``participant_id`` NOT NULL (**canonical participant identity** —
--     ``world_actor.actor_id`` ∪
--     ``world_player_character.player_character_id``, the V3-3R freeze;
--     a persona id never enters), ``kind`` NOT NULL CHECK
--     ``('EXPERIENCED','HEARD','BELIEVED','INFERRED','MISTAKEN')``
--     (**all five words reachable** — the commit arms land
--     ``EXPERIENCED`` automatically, ``elc.world.memory.record_belief``
--     carries the other four), ``content`` NOT NULL (the memory's text —
--     the deterministic baseline is the event's ``narration``; LLM
--     alteration is the provider cut's), ``source_event_id`` NOT NULL
--     REFERENCES ``world_event(event_id)`` (the memory's factual source —
--     every row of this cut arrives through an event the commit
--     transactions landed; the heard-kind rumour source separates from
--     its event later), ``learned_at_tick`` NOT NULL (= its COMMIT's
--     ``actual_end_tick`` — the canon time anchor), ``salience`` NULL
--     (significance — the deterministic baseline does not evaluate it;
--     storage and pass-through only, retrieval policy later), the
--     bookkeeping pair, ``state_version`` NOT NULL CHECK > 0.
--     **Append-only** (N-INV-003: memories append with events;
--     corrections arrive as later memories, never rewrites).
--   * ``chapter_settlement`` — ``chapter_id`` TEXT PRIMARY KEY
--     REFERENCES ``world_chapter(chapter_id)`` (**one version per
--     chapter** — the PK is the chapter id: one summary ever lands,
--     re-runs are no-ops; STATE §21's SETTLING recovery sentence),
--     ``summary`` / ``storyline_updates`` / ``hooks`` /
--     ``resolved_lines`` / ``salience_notes`` NOT NULL (the
--     deterministic baseline's conservative assembly — see
--     :mod:`elc.world.settlement`'s ``settle_chapter``; the structured
--     storyline advancement, the hook queue and the salience evaluation
--     are registered later cuts), ``created_at_revision`` NOT NULL (the
--     chapter's latest ``plan_revision`` when the row landed — the Plan
--     face's version witness), the bookkeeping pair, ``state_version``
--     NOT NULL CHECK > 0. **N-INV-004's storage face**: this table only
--     compresses / closes what is already committed — it writes no
--     ``world_event``, no ``world_state_fact``, no ``actor_memory`` and
--     advances no ``world.current_tick``.
--   * STATE_MACHINES §25's "V3-7 落法" — the memory arm of BOTH commit
--     transactions (NCP-2 / NCP-3: one ``EXPERIENCED`` row per event
--     participant, in the same short atomic group; the replay arm
--     answers first, so a replay never double-lands memory) and the
--     NCP-4 orchestration (the short transaction that lands this
--     settlement row and flips ``SETTLING → CLOSED`` with
--     ``closed_at_tick`` read inside it; the tick is never advanced).
--   * RUNTIME_ARCHITECTURE §28 (NCP-4 — not a fact-landing boundary) /
--     §29 (the recovery scan's sixth family: ``SETTLING`` chapters).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- FK chain (all keep-side): memory → world; memory → event; settlement →
-- chapter → world. Both tables join ``GLOBAL_CONTENT_TABLES``' keep side
-- (21 → 23 members, the chronological tail append: 0029 → 0030 → 0031 →
-- 0033 → 0034 → 0035 → 0036 → 0037) — deletion pins ride along.
--
-- No index anywhere: the MVP's memory and settlement slices are small, a
-- scan is the honest cost (0028–0036's posture). No ON DELETE clause:
-- SQLite's default NO ACTION (the RESTRICT posture) is this cut's whole
-- deletion story, the same posture 0023–0036 spell. The tables must be
-- built after the rows they reference: ``world_event`` (0024 era) and
-- ``world_chapter`` (0029).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS actor_memory (
    memory_id       TEXT PRIMARY KEY,
    world_id        TEXT NOT NULL REFERENCES world(world_id),
    participant_id  TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('EXPERIENCED','HEARD','BELIEVED','INFERRED','MISTAKEN')),
    content         TEXT NOT NULL,
    source_event_id TEXT NOT NULL REFERENCES world_event(event_id),
    learned_at_tick INTEGER NOT NULL,
    salience        REAL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    state_version   INTEGER NOT NULL CHECK (state_version > 0));

CREATE TABLE IF NOT EXISTS chapter_settlement (
    chapter_id          TEXT PRIMARY KEY REFERENCES world_chapter(chapter_id),
    summary             TEXT NOT NULL,
    storyline_updates   TEXT NOT NULL,
    hooks               TEXT NOT NULL,
    resolved_lines      TEXT NOT NULL,
    salience_notes      TEXT NOT NULL,
    created_at_revision INTEGER NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    state_version       INTEGER NOT NULL CHECK (state_version > 0));

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '37')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '37')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
