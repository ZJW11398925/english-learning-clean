-- 0023_world_identity.sql — W-1-0 (the living-world program's first cut):
-- the world's identity binding, three tables.
--
-- Three tables land here, no seed row (identity is bound, not born — a
-- database opens with zero worlds and the composition root seeds none; the
-- first world is created by the caller through elc.world.store's idempotent
-- create, W-1-4's shape).
--
-- Authority: the W-1-0 adjudication chain (direction DEC-OPI-7e3744ee…2 —
-- the user's living-world mainline; the program's opening ruling
-- DEC-OPI-7e3744ee…4 R1–R9; M0.1 DEC-OPI-d96fd92d…7 AD-1 "conservative
-- overlay" + AD-5 "the three identity tables land once, here"). The column
-- set is the adjudication's own spelling, column for column.
--
-- Physical decisions (each minimal, the 0020/0022 conventions restated):
--   * ``world.world_id`` TEXT PRIMARY KEY — the world's own id (W-3-2
--     consumes the fork lineage below).
--   * ``world.template_world_id`` TEXT NULL REFERENCES world(world_id) —
--     the fork's parent; NULL is a root world. Self-referencing FK because
--     a fork's parent is itself a world row (checked by SQLite's own
--     foreign-key enforcement, foreign_keys=ON per the connection profile).
--   * ``world_actor.actor_id`` TEXT PRIMARY KEY — an actor is a global
--     identity (one actor belongs to exactly one world via the NOT NULL
--     FK below); the (actor_id, world_id) UNIQUE is spelled for the
--     composite FK that world_conversation needs, not because a second
--     world could re-use the id.
--   * ``world_actor.persona_id`` TEXT NOT NULL REFERENCES
--     character_card(persona_id) — the actor speaks through a character
--     card (migration 0019's table, the clean FK target MC-0 provided);
--     UNIQUE (world_id, persona_id) so one card speaks as at most one
--     actor per world.
--   * ``world_conversation.binding_id`` TEXT PRIMARY KEY — the binding is
--     its own row identity (a conversation's world membership is a fact
--     with a name, W-1-2 consumes bindings).
--   * ``FOREIGN KEY (actor_id, world_id) REFERENCES world_actor
--     (actor_id, world_id)`` — the composite FK keeps a binding's actor
--     inside its own world: a binding may not pair an actor with a world
--     the actor does not belong to, and (world_id, actor_id) pairs not
--     present in world_actor are refused by SQLite's own enforcement.
--   * ``world_conversation.conversation_id`` TEXT NOT NULL UNIQUE
--     REFERENCES conversation(conversation_id) — one conversation binds to
--     at most one world (the UNIQUE), and the conversation row must exist
--     (migration 0002's PK is the target).
--   * ``created_at`` TEXT NOT NULL — ISO-8601, the store's clock convention
--     (0019's shape); one stamp per row, identity rows are append-first.
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION equivalent
--     (RESTRICT posture) is this cut's whole deletion story — the deletion
--     face is registered, not built (Revisit W-1-3 decides the real
--     semantics; this migration does not pre-empt it).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world (
    world_id         TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    template_world_id TEXT REFERENCES world(world_id),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS world_actor (
    actor_id   TEXT PRIMARY KEY,
    world_id   TEXT NOT NULL REFERENCES world(world_id),
    persona_id TEXT NOT NULL REFERENCES character_card(persona_id),
    created_at TEXT NOT NULL,
    UNIQUE (world_id, persona_id),
    UNIQUE (actor_id, world_id)
);

CREATE TABLE IF NOT EXISTS world_conversation (
    binding_id      TEXT PRIMARY KEY,
    world_id        TEXT NOT NULL,
    actor_id        TEXT NOT NULL,
    conversation_id TEXT NOT NULL UNIQUE
                    REFERENCES conversation(conversation_id),
    created_at      TEXT NOT NULL,
    FOREIGN KEY (actor_id, world_id)
        REFERENCES world_actor(actor_id, world_id)
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '23')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '23')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
