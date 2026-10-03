-- 0020_world_lore_facts.sql — 主线-3 (world_lore domain implementation,
-- DEC-OPI-32409938…36): the canonical world facts of the World/Lore
-- bounded context.
--
-- One table lands here; no seed row. The first fact batch is seeded by the
-- composition root at open (elc/world_lore/content.py — the penpal-seed
-- precedent stayed in pure SQL only because the card copy is held honest by
-- a field-for-field pin; the lore batch is richer and lives in the domain
-- module, so the store's idempotent append keeps reseeds a no-op).
--
-- Authority: the task's adjudication (DEC-OPI-32409938…36 R1) — the column
-- set is derived from the Phase 0 shapes (elc/world_lore/types.py:
-- WorldLoreRecord's world_lore_fact_id / fact_kind / canonical_key /
-- statement; WorldLoreProposal's source) plus the adjudication's own
-- columns (scope / status / epoch). **The table shape is an
-- implementation-defined reading**: docs/DATA_MODEL.md names the domain and
-- the lore_refs column but defines no table for it; when canonical grows
-- one, this migration's reading aligns to it (the declared Revisit, the
-- CORE_A/CORE_C declared-reading precedent).
--
-- Physical decisions (each minimal, the 0018/0019 conventions restated):
--   * ``world_lore_fact_id`` TEXT PRIMARY KEY — the canonical fact's own id
--     (the WorldLoreFactId value; seeded rows carry stable ``wlf-`` ids so
--     reseeding is idempotent by PK).
--   * ``scope`` TEXT NOT NULL CHECK (scope IN ('world', 'character')) — the
--     adjudication's two scopes: a world fact is common to every
--     conversation; a character fact is visible inside one character's
--     conversations only.
--   * ``persona_id`` TEXT — the character scope's key (the conversation's
--     bound persona): NULL for world rows, NOT NULL for character rows; the
--     CHECK spells the pairing so a world fact can never grow a persona and
--     a character fact can never lose its owner.
--   * ``fact_kind`` TEXT NOT NULL CHECK — the WorldLoreFactKind vocabulary
--     word for word (docs/PRODUCT_CONTRACT.md §World/Lore: 场景、NPC、
--     地点、规则 → SCENE / NPC / PLACE / RULE).
--   * ``canonical_key`` TEXT NOT NULL — the stable reference key the
--     persona card's ``lore_refs`` names (§5.1 ``lore_refs[]``); the view
--     resolution does not join on it (the card names, the store answers),
--     it is the durable name facts are addressed by.
--   * ``statement`` TEXT NOT NULL — the fact's prose (the one column the
--     prompt's [lore] section renders).
--   * ``source`` TEXT NOT NULL — the WorldLoreProposal.source column: who
--     authored the row ("builtin-lore-v1" for the shipped batch; untrusted
--     proposals keep their declared source for the later approval face).
--   * ``status`` TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PENDING')) —
--     the P-INV-013 half: ACTIVE rows are canonical and view-visible;
--     PENDING rows are proposals (untrusted content) that no view ever
--     serves until an approval cut lands (registered, not simulated).
--   * ``write_epoch`` INTEGER NOT NULL — the runtime epoch that wrote the
--     row (the store stamps ``fence.current``; the house epoch convention).
--   * ``created_at`` TEXT NOT NULL — ISO-8601, the store's clock convention
--     (0019's ``created_at`` shape); one stamp, facts are append-first.
--   * No foreign keys: a character fact references its persona by the
--     conversation domain's binding (0019's card table reads it the same
--     way — persona rows live in the conversation binding, not a table of
--     their own). One index serves the view resolution (status + scope +
--     persona); everything else is PK or full-list.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_lore_fact (
    world_lore_fact_id TEXT PRIMARY KEY,
    scope              TEXT NOT NULL CHECK (scope IN ('world', 'character')),
    persona_id         TEXT,
    fact_kind          TEXT NOT NULL
                       CHECK (fact_kind IN ('SCENE', 'NPC', 'PLACE', 'RULE')),
    canonical_key      TEXT NOT NULL,
    statement          TEXT NOT NULL,
    source             TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PENDING')),
    write_epoch        INTEGER NOT NULL,
    created_at         TEXT NOT NULL,
    CHECK (
        (scope = 'world' AND persona_id IS NULL)
        OR (scope = 'character' AND persona_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_world_lore_fact_view
    ON world_lore_fact (status, scope, persona_id);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '20')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '20')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
