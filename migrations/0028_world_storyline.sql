-- 0028_world_storyline.sql — C2 (the storyline cut, the outer review
-- sixth round's placement): the story's arcs as a first-class
-- structure — the plot layer's own table.
--
-- One table lands here, no seed row (storylines enter through the
-- package seed's ``initial_storylines`` face at open time; the
-- narrator's own hand opening new lines is ledger P4, a later cut's).
--
-- Authority: the C2 adjudication (DEC-OPI-b290799a…43 R1–R8) and the
-- canonical pair — the living-world spec 术语表「剧情线 = 一等公民结构：
-- 挂起的事件弧〔主题+关联事件集+收束条件〕，有生命周期」 with §5.4
-- (剧情线是记忆的一等挂架；线收束，整线沉降为一条冷层记忆要点) and the
-- cognition-and-narrative-quality doc 域二 裁断点③④: ≤3 active lines
-- per world, package-initial / manual open in v1 (the narrator's
-- auto-open is ledger P4), and the data lands in a NEW table — 0028,
-- the sixth review's own renumbering (0027 went to C1-a's chronicle
-- attribution).
--
-- The column set is the adjudication's own spelling, column for
-- column (the v1-minimal shape: the canonical structure's ``linked``
-- event set and ``hooks`` queue are the later cuts' — this table
-- carries the arc's identity, its topic and its closure condition).
--   * ``line_id`` TEXT PRIMARY KEY — the storyline's identity; the
--     package seed derives ``line-<world token>-<ordinal>`` (the
--     actor-id derivation's sibling).
--   * ``world_id`` TEXT NOT NULL REFERENCES world(world_id) — a line
--     belongs to exactly one world.
--   * ``theme`` TEXT NOT NULL — the one-sentence arc topic.
--   * ``opened_by`` TEXT NULL — the chronicle event that opened the
--     line, when one exists (a package-initial line has no opening
--     event). Deliberately NO foreign key, the same posture
--     ``world_run.trigger_turn_id`` and 0027's ``run_id`` spell: the
--     structure row must not pin a chronicle row's lifetime beyond
--     what the tree carries; the deletion face stays W-1-3's
--     registered cut.
--   * ``status`` TEXT NOT NULL DEFAULT 'active' CHECK (status IN
--     ('active', 'resolved', 'settled')) — the three-word lifecycle
--     the spec spells (开启 / 收束 / 沉降). This cut moves only
--     active → resolved (:meth:`elc.world.store.SqliteWorldStore.
--     resolve_storyline`); ``settled`` is the later cut's word
--     (整线沉降为一条冷记忆要点, spec §5.4) and sits in the
--     vocabulary so the schema never needs a second migration to
--     name it. The DEFAULT is the create face's only starting word.
--   * ``resolve_at`` TEXT NOT NULL — the closure condition in the
--     narrator's own narrative terms; the store never evaluates it
--     (the narrator judges, the structure records).
--   * ``created_at`` TEXT NOT NULL — the caller's ISO-8601 stamp; no
--     hidden clock anywhere in this cut.
--   * No ``updated_at`` column: the row's one legal move (active →
--     resolved) is announced where every world claim is announced —
--     the projection, under the canonical key
--     ``storyline:<line_id>`` with the statement ``resolved``
--     (elc.world.types' :func:`elc.world.types.storyline_effect_key`).
--     The projection fact's ``recorded_at`` carries the closure's
--     moment; the structure row says the line is closed, the
--     chronicle says when. The two-layer law (v1 adjudication): the
--     storyline row's status does NOT auto-flip with the projection —
--     the active read filters through the projection instead, so an
--     effects-proposed closure takes effect on the next step's
--     prompt without a second state machine.
--   * No index: per-world slices are single digits (裁断点③ caps the
--     active set at three), a scan is the honest cost.
--   * No ON DELETE clause anywhere: SQLite's default NO ACTION
--     equivalent (RESTRICT posture) is this cut's whole deletion
--     story — the same posture 0023–0025 spell.
--
-- P8 verdict (the Revisit ledger's P8 row, settled this cut per the
-- C2 adjudication R6): the pool event's ``days`` is a **declaration,
-- not a fact** — the package author's claim about the story's own
-- span, carried by the JSON and consumed by the calendar faces at
-- read time. The world's dates derive from the durable chronicle's
-- stamps (:func:`elc.world.package.story_elapsed_days_of`), so
-- editing the package changes FUTURE spans and never rewrites
-- history: the chronicle is append-only, and the same events answer
-- the same dates forever (AD-6's determinism carried into time).
--
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_storyline (
    line_id    TEXT PRIMARY KEY,
    world_id   TEXT NOT NULL REFERENCES world(world_id),
    theme      TEXT NOT NULL,
    opened_by  TEXT NULL,
    status     TEXT NOT NULL DEFAULT 'active'
               CHECK (status IN ('active', 'resolved', 'settled')),
    resolve_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '28')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '28')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
