-- 0010_episode_and_user_config.sql — Phase 4 P4-3: the Episode projection +
-- the User Configuration/Profile durable objects (TASK-OPI-4d516e4f-8d08-
-- 6bf19a95bd25.19 ⑥).
--
-- Three tables land here, and nothing else. This migration is DDL +
-- vocabulary only — no backfill, no rebuild, no row is created by it. The
-- runtime faces that write them belong to this same slice: P4-3 ① writes
-- episode rows (elc.relationship.episode_store), P4-3 ③ writes the profile /
-- disclosure rows (elc.user_config.store). Nothing earlier in the chain is
-- touched: 0001–0009 are byte-identical and every table they created keeps
-- its shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §5.3   Episode Projection — the ten columns of the
--                             first table, word for word: episode_id /
--                             conversation_id / version /
--                             source_turn_sequence_start /
--                             source_turn_sequence_end / summary /
--                             open_threads[] / recent_events[] / status /
--                             updated_at. §5.3 also fixes what the row is:
--                             "Episode 是 transcript-derived projection，
--                             可重建，不拥有 Conversation truth" — which is
--                             why this table is a projection store, and why
--                             nothing here is ever the source of transcript
--                             truth.
--   docs/DATA_MODEL.md §5.1   UserProfile — user_profile_id / revision /
--                             profile_facts / preferences / settings /
--                             updated_at (six columns, verbatim) — and
--                             DisclosurePolicy — disclosure_policy_id /
--                             revision / rules[] / updated_at (four
--                             columns, verbatim). §5.1's note "Produces
--                             `DisclosedUserProfile` for a specific
--                             Persona/runtime context" is the rule the third
--                             table feeds: the policy is the *only* source
--                             of a disclosure decision, and
--                             DisclosedUserProfile itself is never a row (it
--                             is a per-consumer view, built at read time).
--   docs/DOMAIN_MODEL.md §5.1 Owns: UserProfile, DisclosurePolicy (the
--                             User Configuration/Profile bounded context).
--   docs/DOMAIN_MODEL.md §18.1 Trust/Privacy Authority: "高敏感 Profile/
--                             Relationship persistence 需要显式用户许可；模型
--                             不得把推断的高敏感属性直接提交为长期事实".
--                             §5.1 pins no consent column and this migration
--                             adds none, so the consent gate is a *domain*
--                             rule (elc.user_config.controller
--                             upsert_user_profile(explicit_consent=…), the
--                             P4-1 sensitive-gate precedent) rather than a
--                             cross-column CHECK — stated here because the
--                             absence is deliberate, not an oversight.
--   docs/DOMAIN_MODEL.md §4   "Persona Runtime 只能获得 DisclosedUserProfile，
--                             不能读取完整 UserProfile" (§5.1 Rules) — the
--                             read face enforces it by never exposing the
--                             full profile through the persona-facing port.
--   docs/RUNTIME_ARCHITECTURE.md §11  EpisodeView / DisclosedUserProfile are
--                             GenerationContext members the PromptCompiler
--                             renders; the views carry content only (the
--                             prompt never renders updated_at).
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
-- 1. episode — the transcript-derived conversation projection (§5.3)
--
-- Column notes (none of them adds a column; they say what each canonical
-- name stores):
--   episode_id      TEXT PRIMARY KEY — §5.3; §1.2 stable opaque id. Derived,
--                   never minted: "ep-{sha256(conversation_id)[:20]}" (the
--                   repo-wide deterministic-id convention), so a rebuild or
--                   a crash-gap repair addresses the same row.
--   conversation_id TEXT NOT NULL REFERENCES conversation — §5.3. The
--                   conversation is the unit of this projection (Local V1:
--                   one conversation, one episode — the stance declared in
--                   elc.relationship.episode; the UNIQUE index below makes
--                   it structural rather than aspirational).
--   version         TEXT NOT NULL — §5.3; the content digest
--                   ("epv-{sha256[:20]}", elc.relationship.episode
--                   episode_version_for). It covers the content columns and
--                   the source window, and no clock, so "the same episode
--                   was rebuilt" is decidable without comparing every column
--                   (and the store's idempotent replay rides on it).
--   source_turn_sequence_start / _end INTEGER NOT NULL — §5.3. The window
--                   the episode was built from, in turn_sequence terms.
--   summary         TEXT NOT NULL — §5.3. Extractive, verbatim (the Local V1
--                   reading declared in elc.relationship.episode): not a
--                   generated narrative.
--   open_threads    TEXT NOT NULL — §5.3 ``open_threads[]``; JSON array (the
--                   0004 qualifier-list / 0009 source_turn_ids precedent:
--                   arrays are JSON text, never a second table). Ordered:
--                   the Persona×User pair's ACTIVE OPEN_THREAD memory
--                   contents by memory id.
--   recent_events   TEXT NOT NULL — §5.3 ``recent_events[]``; JSON array of
--                   the rendered canonical slices (elc.conversation.commands
--                   describe_slice), oldest of the kept ones first.
--   status          TEXT NOT NULL CHECK — §5.3. The vocabulary is the
--                   conversation's own (§3 Conversation status): ACTIVE /
--                   CLOSED. §5.3 pins no episode-specific word list, and
--                   reading the conversation's status is exactly what
--                   "status" means here (the episode does not own a
--                   lifecycle of its own).
--   updated_at      TEXT NOT NULL — §5.3. The store's clock, never the
--                   rebuild's and never the prompt's.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS episode (
    episode_id                 TEXT PRIMARY KEY,
    conversation_id            TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    version                    TEXT NOT NULL,
    source_turn_sequence_start INTEGER NOT NULL,
    source_turn_sequence_end   INTEGER NOT NULL,
    summary                    TEXT NOT NULL,
    open_threads               TEXT NOT NULL,
    recent_events              TEXT NOT NULL,
    status                     TEXT NOT NULL
        CHECK (status IN ('ACTIVE', 'CLOSED')),
    updated_at                 TEXT NOT NULL
);

-- Local V1: one conversation holds one episode, so the conversation key is
-- unique — every read in elc.relationship.episode_store is keyed by it, and
-- a second row for the same conversation would make "the episode" ambiguous.
CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_conversation
    ON episode (conversation_id);

-- ---------------------------------------------------------------------------
-- 2. user_profile — the long-term profile this context owns (§5.1)
--
--   user_profile_id TEXT PRIMARY KEY — §5.1. The id is the user's own id
--                   (elc.user_config.types.UserProfile types the field
--                   ``UserId``): Local V1 has one profile per user, and §5.1
--                   pins no separate owner column to link them.
--   revision        TEXT NOT NULL — §5.1. The stamp of this revision of the
--                   profile. §1.4 "version every derived model": a write
--                   that changes the content under an unchanged revision is
--                   refused by the store (CONFLICT) instead of silently
--                   rewriting a stamped revision.
--   profile_facts   TEXT NOT NULL — §5.1 ``profile_facts``; JSON array of
--                   ``{"text": …, "sensitivity": "PERSONAL" |
--                   "HIGH_SENSITIVITY"}`` (elc.user_config.types
--                   ProfileFact). The sensitivity vocabulary is
--                   elc.relationship.types.MemorySensitivityClass, i.e. the
--                   BF-05 data_classes pair P4-1 already uses for
--                   relationship memories — one privacy vocabulary in the
--                   process, not two.
--   preferences     TEXT NOT NULL — §5.1 ``preferences``; JSON array of
--                   strings.
--   settings        TEXT NOT NULL — §5.1 ``settings``; JSON array of strings.
--   updated_at      TEXT NOT NULL — §5.1; the store's clock.
--
-- The high-sensitivity persistence rule (§18.1) is deliberately NOT a CHECK
-- here: §5.1 pins no consent column, and inventing one would change the
-- canonical column set. It is enforced by the domain write face
-- (elc.user_config.controller.upsert_user_profile refuses a profile carrying
-- any HIGH_SENSITIVITY fact unless the caller passes explicit_consent=True,
-- with zero writes) and pinned by test.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profile (
    user_profile_id TEXT PRIMARY KEY,
    revision        TEXT NOT NULL,
    profile_facts   TEXT NOT NULL,
    preferences     TEXT NOT NULL,
    settings        TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 3. disclosure_policy — what a specific Persona may be told (§5.1)
--
--   disclosure_policy_id TEXT PRIMARY KEY — §5.1. As with the profile, §5.1
--                   pins no owner column: Local V1 keys a user's policy by
--                   the user's id (elc.user_config.store and .controller
--                   declare that linking convention, and the alternative —
--                   a second table or an added column — would exceed the
--                   canonical column set).
--   revision        TEXT NOT NULL — §5.1; same stamp discipline as above.
--   rules           TEXT NOT NULL — §5.1 ``rules[]``; JSON array of
--                   ``{"persona_id": … | null, "disclosure_level":
--                   "MINIMAL" | "FUNCTIONAL" | "RICH"}``
--                   (elc.user_config.types.DisclosureRule). ``null``
--                   persona_id is the default rule. The level vocabulary is
--                   elc.user_config.types.DisclosureLevel (the Phase 0
--                   word list, unchanged).
--   updated_at      TEXT NOT NULL — §5.1; the store's clock.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS disclosure_policy (
    disclosure_policy_id TEXT PRIMARY KEY,
    revision             TEXT NOT NULL,
    rules                TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '10')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '10')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
