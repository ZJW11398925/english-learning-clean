-- 0014_deletion_tombstone.sql — Gate 2: the BF-05 deletion tombstone
-- (TASK-OPI-b99560d4-….19 ①; docs/IMPLEMENTATION_PLAN.md §16 DoD #25 —
-- "删除 canonical user source 可删除/重建 solely-derived
-- Learning/Relationship/Episode/Index state").
--
-- One table lands here, and nothing else. This migration is DDL + vocabulary
-- only — no backfill, no rebuild, no row is created by it. The write faces
-- that fill it belong to this same slice: elc.deletion.store (the durable
-- rows and every SQL statement) behind elc.deletion.controller (the
-- authority face). Nothing earlier in the chain is touched: 0001–0013 are
-- byte-identical (0013's header comment included — this cut does not edit
-- that file) and every table they created keeps its shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   behavioral_baselines/security/
--     SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md §24 "Deletion Tombstone"
--                             (lines 831–852) — the whole column set this
--                             table carries, verbatim:
--                                 opaque entity identity/hash
--                                 deleted_at
--                                 deletion_scope/version
--                             plus the two rules the section states:
--                             "不得保存被删除正文" (SEC-023) and
--                             "Import stale backup 时：tombstone wins"
--                             (SEC-024).
--   ... §19/§20/§21/§22/§23  the seven scope words this table's
--                             ``deletion_scope`` CHECK freezes. Five of them
--                             are literal tokens in the contract's own text —
--                             §20 spells LEARNING_TARGET and
--                             ALL_LEARNING_HISTORY, §21 spells
--                             RELATIONSHIP_PAIR, §22 spells PERSONA_PACKAGE,
--                             §23 spells ALL_USER_DATA. The other two are
--                             **not** contract tokens and this header says so
--                             rather than flattening the difference:
--                             CONVERSATION is §19's *section* (its heading
--                             reads "Conversation 删除", mixed case; the
--                             uppercase scope token is the one the executable
--                             benchmark uses in S41's ``request.scope``), and
--                             PROFILE_FIELD comes from the benchmark alone
--                             (S44's ``request.scope``, with a ``field_key``)
--                             — the contract deletes a profile fact as part
--                             of §19's provenance closure and never names a
--                             standalone scope for one. Both words are
--                             therefore benchmark-sourced, which is why
--                             elc/deletion/types.py registers them as derived
--                             while the other five are quoted.
--   docs/DATA_MODEL.md §24.14
--                             "Security / Deletion Records" (lines
--                             1580–1584): "Deletion tombstone 仅保存 opaque
--                             id/scope/version/hash metadata，不保存已删
--                             plaintext" — the same four things §24 lists,
--                             restated by the data model.
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27    the physical form (column type, index names)
--                             is the implementation's; the element shape of
--                             §24 is declared in elc/deletion/types.py.
--
-- ---------------------------------------------------------------------------
-- 1. deletion_tombstone — one minimal, plaintext-free deletion ledger row
--
-- Column notes (none of them adds a column; they say what each canonical
-- name stores):
--   tombstone_id   TEXT PRIMARY KEY — §24 "opaque entity identity/hash".
--                  **Derived, never minted from a clock**: the id is
--                  ``ts-{sha256(entity_kind + US + entity_hash)[:20]}``
--                  (elc/deletion/plan.py), so re-running the same deletion
--                  addresses the same row instead of growing the ledger a
--                  second entry for one entity (the pj-/rm-/sv- deterministic
--                  id convention this repository uses everywhere).
--   entity_kind    TEXT NOT NULL — §24 "opaque entity identity/hash": the
--                  *kind* half of the identity. The value is the durable
--                  table name the entity was removed from (or the scope word
--                  for a non-row entity, e.g. a Profile field key), and it is
--                  deliberately **not** CHECKed: §24 pins no vocabulary for
--                  it, and a closed CHECK here would turn every future
--                  migration into a re-check of an old table's schema —
--                  the 0012 ``event_type`` precedent for a canonical column
--                  that names no word list. elc/deletion/types.py declares
--                  the spelling and the read face pins it.
--   entity_hash    TEXT NOT NULL — §24 "opaque entity identity/hash": the
--                  non-reversible digest that makes the identity opaque.
--                  Algorithm (this cut's declaration, a derived judgement
--                  rather than a quoted one — §24 pins the *property*,
--                  "opaque", not the function): the full 64 hex characters of
--                  ``sha256(entity_kind + US + entity_id)`` with US = ASCII
--                  0x1f, the repository's unit-separator convention
--                  (elc/runtime/projections.py). One-way by construction,
--                  and stable for the same entity across processes.
--   deleted_at     TEXT NOT NULL — §24. The caller's instant when the caller
--                  declares one; the writing store's clock otherwise (the
--                  0007 teaching_moment ``created_at or _now()`` precedent).
--                  §24 pins no format and this migration pins none either.
--   deletion_scope TEXT NOT NULL CHECK — §24 "deletion_scope/version". The
--                  seven words are the five the contract spells as scope
--                  tokens (§20–§23) plus the two the executable benchmark
--                  supplies (§19's conversation scope and S44's profile
--                  field), and the CHECK freezes them: unlike §9's Scope list
--                  (0013's "Scope 例如"), §20–§23 each name their scope as the
--                  *subject* of their own section, so those five are closed by
--                  the documents themselves. A new scope word is a canonical
--                  revision, not an implementation choice.
--   scope_version  TEXT NOT NULL — §24 "deletion_scope/version". The version
--                  of the deletion semantics the row was written under, so a
--                  later policy revision can tell its own tombstones from an
--                  earlier one's. The value is elc.deletion.types'
--                  DELETION_POLICY_VERSION (a derived declaration: §24 asks
--                  for a version and names no vocabulary for it).
--
-- **SEC-023 is structural here, not a promise.** The table has no column that
-- could hold deleted content: no body, no summary, no ref list. The only
-- readable values are an opaque id, a table name, a one-way digest, a
-- timestamp, a scope word and a policy version — which is exactly §24's
-- "只记录最小信息" list and nothing more. A test asserts the absence by
-- searching the whole table for the deleted plaintext.
--
-- **SEC-024 is a predicate, not a paragraph.** ``is_tombstoned`` and the
-- import guard (elc/deletion/controller.py) answer "is this entity
-- tombstoned?" and "which of these incoming records must not be admitted?";
-- a stale backup's rows for a tombstoned entity are refused rather than
-- re-created.
--
-- Uniqueness: one row per (entity_kind, entity_hash). §24 does not spell an
-- index, and the uniqueness is this migration's choice with a stated reason —
-- the tombstone is the ledger of *entities* removed, so a second row for the
-- same entity would be a duplicate ledger entry, and the unique index is also
-- the read path ``is_tombstoned`` walks. It is what makes the write
-- idempotent under the derived ``tombstone_id``.
--
-- ---------------------------------------------------------------------------
-- Derived judgements carried by this migration (NOT canonical text)
--
-- **This migration decides nothing about what deletion means.** No scope
-- walk, no cascade and no rebuild is declared here: those are
-- elc/deletion/plan.py's declared surfaces (per scope, pinned by test) and
-- elc/deletion/store.py's statements. This file only makes the ledger
-- durable.
--
-- **The table is not swept by ALL_USER_DATA.** §23 keeps "一个最小、无
-- plaintext 的 deletion-protection ledger，以防 stale backup 自动复活" and
-- adds that a factory reset may clear it; the sweep therefore treats this
-- table as retained infrastructure (elc/deletion/types.py RETAINED_TABLES),
-- and the pin test holds that list against the real database.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deletion_tombstone (
    tombstone_id   TEXT PRIMARY KEY,
    entity_kind    TEXT NOT NULL,
    entity_hash    TEXT NOT NULL,
    deleted_at     TEXT NOT NULL,
    deletion_scope TEXT NOT NULL
        CHECK (deletion_scope IN ('CONVERSATION', 'LEARNING_TARGET',
                                  'ALL_LEARNING_HISTORY', 'RELATIONSHIP_PAIR',
                                  'PROFILE_FIELD', 'PERSONA_PACKAGE',
                                  'ALL_USER_DATA')),
    scope_version  TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_deletion_tombstone_entity
    ON deletion_tombstone (entity_kind, entity_hash);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '14')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '14')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
