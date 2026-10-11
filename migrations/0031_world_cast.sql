-- 0031_world_cast.sql — V3-3 (World Cast & Player Identity, the
-- Narrative V3 program's third cut; TASK-OPI-bab4da9f…52 /
-- VAL-OPI-bab4da9f…54 — the contract was already canonical:
-- DATA_MODEL §26.2.1's ``world_player_character`` and
-- ``world_actor_profile`` entries, DOMAIN_MODEL §20.1's Cast row and
-- §20.2's authority table, the design supplement §7.1-7.2,
-- IMPLEMENTATION_PLAN §20's V3-3 row).
--
-- Two tables and nothing else: this cut freezes the durable cast
-- faces Director's first planning must read — who is the protagonist,
-- who may carry a POV, what each AI actor's long-term drive and
-- current arc are, what is private to them, and who the player is in
-- this world — plus the one derivation that unifies the namespace
-- (:func:`elc.world.cast.participant_namespace`). The old
-- ``world_actor`` row is untouched: the design supplement §7.1's
-- boundary is spelled — do not reshape ``world_actor`` (it keeps
-- representing AI-controlled actors); a new, independent
-- user-controlled durable entity joins the participant namespace
-- instead (§八/§九), and the profile rides the same actor id through
-- its own FK. ``CharacterCard`` (0019) answers *who she is*;
-- ``world_actor_profile`` answers *who she is in this world* — never
-- the same question, never one table (§7.2).
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1 — the entity contracts, column for column.
--     ``world_player_character``: ``player_character_id, world_id,
--     name, background, appearance, abilities, limits, location,
--     state, knowledge_refs?`` with the contract's own note as this
--     table's law — 与 participants namespace 统一（cast ids ∪
--     {player_character_id} ∪ 居民名）— the derivation is
--     :func:`elc.world.cast.participant_namespace`, a pure function,
--     not a stored fact. One player character per world is the
--     ``UNIQUE (world_id)`` structural law: the reader enters each
--     world as one durable person, so a second row under the same
--     world refuses at the storage level.
--   * DATA_MODEL §26.2.1 — ``world_actor_profile``: ``actor_id,
--     world_id, story_role (PROTAGONIST|MAJOR|SUPPORTING),
--     pov_eligible, pov_weight, long_term_drive, current_arc_seed,
--     private_context``, the AI actor's narrative profile (its note:
--     CharacterCard ≠ 本表). The three nullable columns are the
--     honest *undeclared*: ``story_role`` / ``pov_eligible`` /
--     ``pov_weight`` a package (or a caller) never spoke ride as
--     NULL — NULL means "not declared", never a guessed default, so
--     a consumer can tell a field the template never took a stance on
--     from one it did; the vocabulary columns' CHECKs admit exactly
--     the canonical words or NULL. ``pov_eligible`` stores 0/1
--     (SQLite has no boolean type); ``pov_weight`` is a non-negative
--     int. The three text faces of the arc (``long_term_drive`` /
--     ``current_arc_seed`` / ``private_context``) are NOT NULL and
--     the store writes the empty string when the caller declares
--     nothing — the same honest-undeclared spelling the Bible's
--     content fields keep (0030's posture).
--   * DOMAIN_MODEL §20.1 — the Cast row of the Narrative Domain map:
--     ``world_actor`` (reused, untouched) + ``world_actor_profile`` +
--     ``world_player_character``; §20.2 gives the planning face its
--     authorities, and this cut's tables are what Director's cast
--     input reads from — a later cut's consumer, no projection here.
--   * The design supplement §7.1 — the user character is durable per
--     world (independent of any persona or card; the package's v7
--     ``user_character`` id survives unchanged as the durable row's
--     id at seed time), and §7.2 — the profile's six fields never
--     migrate back onto the card.
--   * Both tables are world-owned and registered keep-side in
--     GLOBAL_CONTENT_TABLES (this cut, 13 → 15 members): their FK
--     chains (``world_id`` → ``world``; ``actor_id`` →
--     ``world_actor`` → ``world``) are keep-side at every link, so no
--     sweep can be refused through them.
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION
--     equivalent (RESTRICT posture) is this cut's whole deletion
--     story — the same posture 0023–0025, 0028, 0029 and 0030 spell.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_player_character (
    player_character_id TEXT PRIMARY KEY,
    world_id     TEXT NOT NULL REFERENCES world(world_id),
    name         TEXT NOT NULL,
    background   TEXT NOT NULL,
    appearance   TEXT NOT NULL,
    abilities    TEXT NOT NULL,
    limits       TEXT NOT NULL,
    location     TEXT NOT NULL,
    state        TEXT NOT NULL,
    knowledge_refs TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    UNIQUE (world_id));

CREATE TABLE IF NOT EXISTS world_actor_profile (
    actor_id     TEXT PRIMARY KEY REFERENCES world_actor(actor_id),
    world_id     TEXT NOT NULL REFERENCES world(world_id),
    story_role   TEXT CHECK (story_role IS NULL OR story_role IN ('PROTAGONIST','MAJOR','SUPPORTING')),
    pov_eligible INTEGER CHECK (pov_eligible IS NULL OR pov_eligible IN (0, 1)),
    pov_weight   INTEGER CHECK (pov_weight IS NULL OR pov_weight >= 0),
    long_term_drive  TEXT NOT NULL,
    current_arc_seed TEXT NOT NULL,
    private_context  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0));

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '31')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '31')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
