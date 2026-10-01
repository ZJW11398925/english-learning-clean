-- 0019_character_cards.sql — MC-0 (multi-character program, backend ground
-- cut): the user-authored character card.
--
-- One table lands here, plus one seed row. This is the repository's first
-- app.db migration since 0018 (the long zero-migration stretch ends here on
-- the user's explicit call: user-created characters must persist).
--
-- Authority: the task's adjudication (DEC-OPI-a31b14c9…43) — "角色卡支持自
-- 主创建且可创建很多". The column set mirrors the canonical CharacterPackage
-- (docs/DATA_MODEL.md §5.1 via elc.persona.types.CharacterPackageRecord),
-- with the two columns a user-facing card needs beyond it: ``name`` (the
-- spoken name — §5.1 derives it from the identity line's first segment, but
-- a user names a card directly) and ``is_builtin`` (the seeded penpal vs.
-- user-authored cards; builtins are editable and never deletable — the
-- adjudication's own ruling). No portrait/asset column: explicitly out of
-- scope for this cut.
--
-- Physical decisions (each minimal, the 0018 conventions restated):
--   * ``character_id`` TEXT PRIMARY KEY — the card's own id (the §5.1
--     character_package_id value; the seeded row carries the penpal's real
--     id, user cards get server-minted ``card-`` ids).
--   * ``persona_id`` TEXT NOT NULL UNIQUE — the Persona half of the
--     (persona, user) pair the relationship projections key on. The seed
--     row carries the penpal's real persona id; a user card derives
--     ``persona-<character_id>`` at creation. Unique because two cards
--     sharing a persona would share one memory — the isolation this table
--     exists to provide.
--   * Prose columns are NOT NULL: the §5.1 card has no optional prose; a
--     field the user has not written yet is the empty string, never NULL
--     (one spelling of "not written").
--   * ``"values"`` is quoted — VALUES is a SQL keyword; the quoting is the
--     column's name, not a convention change (the store quotes it in every
--     statement for the same reason).
--   * ``lore_refs`` TEXT — bracketed list column carrying a deterministic
--     JSON array document (the 0015/0016/0018 convention: json.dumps with
--     sort_keys and tight separators; the write face owns the encoding).
--   * ``revision`` INTEGER NOT NULL — the §5.1 package revision counter;
--     the store bumps it on every update.
--   * ``status`` TEXT NOT NULL — lifecycle metadata (§5.1); every row this
--     cut creates is ACTIVE.
--   * ``is_builtin`` INTEGER NOT NULL CHECK (is_builtin IN (0, 1)) — the
--     one-bit CHECK spells the boolean's type, the 0018 ``final_rendered``
--     shape.
--   * ``created_at`` / ``updated_at`` TEXT NOT NULL — ISO-8601 strings, the
--     store's clock convention (the conversation store's _now shape).
--   * No foreign keys: a card references nothing (persona rows live in the
--     conversation domain's binding, not a table of their own). No index
--     beyond the PK and the persona uniqueness — the reads are full-list
--     or by-key.
--   * The seed row: the fixed penpal (elc.persona.penpal), field for field
--     from that file's constants — the migration is pure SQL (the runner
--     executescripts), so the values are copied here verbatim and the copy
--     is held honest by the seed pin (tests/host/test_mc0_multi_character
--     .py compares the row against penpal_character_package() field by
--     field). created_at carries her fixed updated_at stamp for the same
--     determinism reason penpal.py fixes that stamp.
--   * DATA_MODEL §26.1: migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS character_card (
    character_id      TEXT PRIMARY KEY,
    persona_id        TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    identity          TEXT NOT NULL,
    personality       TEXT NOT NULL,
    background        TEXT NOT NULL,
    speech_style      TEXT NOT NULL,
    "values"          TEXT NOT NULL,
    boundaries        TEXT NOT NULL,
    opening           TEXT NOT NULL,
    scenario          TEXT NOT NULL,
    generation_policy TEXT NOT NULL,
    lore_refs         TEXT NOT NULL,
    revision          INTEGER NOT NULL,
    status            TEXT NOT NULL,
    is_builtin        INTEGER NOT NULL CHECK (is_builtin IN (0, 1)),
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- The seed: the fixed penpal, verbatim from elc/persona/penpal.py.
INSERT INTO character_card (
    character_id, persona_id, name, identity, personality, background,
    speech_style, "values", boundaries, opening, scenario,
    generation_policy, lore_refs, revision, status, is_builtin,
    created_at, updated_at
) VALUES (
    'cpkg-nell-alder',
    'persona-nell-alder',
    'Nell Alder',
    'Nell Alder — a bookbinder in Berrymoor, a small harbour town; she signs her letters Yours, Nell',
    'unhurried and warm; patient with slow letters and half-finished sentences; quietly funny; genuinely curious about her faraway friend''s city and days',
    'served her apprenticeship at her grandfather''s workbench; keeps a bindery with a green door by the water; mends torn spines and gives worn favourites new covers; walks the harbour path on Sunday mornings; writes letters on quiet evenings, lamp on, kettle warm',
    'plain prose in short, unhurried paragraphs; concrete details from the bench and the harbour; one gentle question at a time; closes with a small wish and signs off as Yours, Nell',
    'patience, careful handwork, honesty — a mended book keeps its scar and says so — and real interest in other people''s days',
    'never preaches and never pries; says plainly when she does not know something; keeps her own private matters private',
    'Hello from across the water — your letter reached my bench today and I read it twice before the kettle boiled. What does your street sound like in the morning?',
    'evening at the bindery: lamp on, glue pot warm, an open letter flat on the workbench',
    'persona-normal-v1',
    '["lore-berrymoor-harbour","lore-bindery-green-door"]',
    1,
    'ACTIVE',
    1,
    '2026-10-01T00:00:00+00:00',
    '2026-10-01T00:00:00+00:00'
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '19')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '19')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
