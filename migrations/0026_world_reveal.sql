-- 0026_world_reveal.sql — W-1-3 (the living-world program's fourth cut):
-- the reveal queue, the presentation half of the spec's dual-start design.
--
-- One table lands here, no seed row (a fresh world owes no reveals; items
-- enter only through elc.world.engine.orchestrate's run_step, which enqueues
-- one item per event the run's advance wrote — same short transaction, so a
-- step that writes events can never leave them un-inventoried — and the web
-- face's reveal_all is the only thing that ever flips PENDING → REVEALED).
--
-- Authority: the W-1-3 adjudication chain (DEC-OPI-7e3744ee…49 R1–R10) and
-- the living-world spec §4.1/§4.2 v2.1
-- (docs/design/2026-10-05-living-world-spec.md): a run may leave
-- "future-revealable special moments" behind when it stops; they sit until
-- the user next enters the app, and revealing is a *presentation trigger*,
-- never run fuel — the user's reply is the only run starter. The item row is
-- the durable form of that sitting: one event the run wrote, one queue item.
--
-- Physical decisions (each minimal, the 0023/0024/0025 conventions restated):
--   * ``item_id`` TEXT PRIMARY KEY — derived as ``<event_id>:reveal`` (the
--     projection's derived-id convention: ``world_state_fact.fact_id`` spells
--     ``<event_id>:<key>``; the reveal item is the same move pointed at the
--     presentation half), so the same event can never enqueue twice.
--   * ``world_id`` TEXT NOT NULL REFERENCES world(world_id) — the item hangs
--     in one world's inbox.
--   * ``source_event_id`` TEXT NOT NULL REFERENCES world_event(event_id) —
--     the event whose narration this item reveals; the inbox read joins the
--     event for its prose (the item carries the pointer, never a copy).
--   * ``actor_id`` TEXT NULL REFERENCES world_actor(actor_id) — the cast
--     member the item is signed by (the comms step's chosen correspondent);
--     NULL is the world's own narration (世界旁白).
--   * ``status`` TEXT NOT NULL CHECK (status IN ('PENDING', 'REVEALED')) —
--     the two-word lifecycle the spec spells: sitting until revealed.
--     ``revealed_at`` TEXT NULL rides the same flip (NULL while PENDING, the
--     reveal moment once REVEALED) — one transition, atomically per world.
--   * ``created_at`` TEXT NOT NULL — ISO-8601, the enqueue moment the caller
--     supplies (the orchestration's own ``now``; no hidden clock).
--   * One index — (world_id, status) — serves the inbox read (the PENDING
--     slice) and the atomic reveal's targeted flip; nothing else is indexed.
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION equivalent
--     (RESTRICT posture) is this cut's whole deletion story — the same
--     posture 0023/0024/0025 spell. The one table this migration's face does
--     NOT touch is ``world_conversation``: W-1-3's deletion face moves that
--     table out of the global keep set and into the conversation scope's
--     sweep (elc/deletion/types.py, the three-cut Revisit closed here).
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_reveal_item (
    item_id         TEXT PRIMARY KEY,
    world_id        TEXT NOT NULL REFERENCES world(world_id),
    source_event_id TEXT NOT NULL REFERENCES world_event(event_id),
    actor_id        TEXT REFERENCES world_actor(actor_id),
    status          TEXT NOT NULL CHECK (status IN ('PENDING', 'REVEALED')),
    revealed_at     TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_world_reveal_item_world_status
    ON world_reveal_item (world_id, status);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '26')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '26')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
