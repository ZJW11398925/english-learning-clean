-- 0022_app_settings.sql — veto-response cut (user dogfood first-verification
-- veto, five feedback groups): the generic host settings table.
--
-- Authority map / deviations (each minimal, no silent widening):
--   * The §12 stage becomes page-movable (POST /api/settings/mode): the
--     user's explicit tier choice in the running process is the same power
--     as choosing it on the launch command — a single-user local app has
--     one principal. The durable home for that choice is a host-level
--     key/value table, NOT the §5.1 policy row: the stage is a process
--     declaration (the stage face's own words — "A stage is a
--     process-level declaration, not user data"), so it must not be welded
--     onto a §5.1 aggregate. This table is that home.
--   * Generic shape on purpose: one key/value pair per row (key PRIMARY
--     KEY, value NOT NULL), no per-facet columns. The living-world program
--     (W-1-0) reuses this table for world settings in its own follow-up
--     migration (0023 — the next number is reserved there); no second
--     settings table gets minted.
--   * This cut writes exactly one key — the stage word's home; its single
--     spelling lives in elc.platform.db.app_settings (the reader and the
--     writer import the same constant, so a renamed key cannot fork into
--     two spellings). open_host reads it only when the launch command
--     declares no stage of its own (explicit argument > persisted word >
--     None — the fail-closed default is untouched). An unparseable stored
--     word is ignored by the reader (treated as absent), never guessed
--     around. This file itself seeds no row and spells no stage word —
--     a migration carries no stage (the P8-5 honesty law, restated).
--   * No seed row: absence is the honest "not chosen yet" — the launch
--     parameter or None answers until the page's first write.
--   * Deletion: the table holds one process-level preference, not learner
--     data; BF-05's deletion scopes do not gain a surface from it (nothing
--     in the table identifies a learner or a conversation).

CREATE TABLE app_setting (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '22')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '22')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
