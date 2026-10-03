-- 0020_provider_usage.sql — fr-A token metering: the provider-reported
-- usage counters ride the ProviderAttempt row they belong to.
--
-- Authority map / deviations (each minimal, no silent widening):
--   * docs/DATA_MODEL.md §20 pins the ProviderAttempt column set verbatim;
--     these three columns are an adjudicated extension — the same shape as
--     ``generation_action_intent.owner_epoch`` (DATA_MODEL §19's adjudicated
--     lease column): usage is a fact OF THE ATTEMPT (one provider call, one
--     reported ``usage`` object), so it lives on the attempt row, is written
--     once at ``record_attempt`` time, and dies with the row under the
--     deletion scopes that already sweep ``provider_attempt``. No new table,
--     no deletion-surface change.
--   * All three columns are NULLABLE: an OpenAI-compatible endpoint that
--     reports no ``usage`` object (or no single counter) leaves NULL — the
--     honest reading, never a fabricated 0. The read faces (elc.web) rely on
--     SQL's SUM-ignores-NULL semantics for exactly this reason.
--   * CHECK (>= 0): a token count is never negative. The extraction layer
--     (elc.persona.openai_provider._usage_of) already maps non-integer /
--     boolean / negative values to NULL; the constraint is the durable echo
--     of that rule (SQLite enforces CHECK on ADD COLUMN for later writes).
--   * No backfill: attempts recorded before this migration carry NULL —
--     "not metered", which is the truth of their moment.

ALTER TABLE provider_attempt ADD COLUMN prompt_tokens INTEGER
    CHECK (prompt_tokens >= 0);
ALTER TABLE provider_attempt ADD COLUMN completion_tokens INTEGER
    CHECK (completion_tokens >= 0);
ALTER TABLE provider_attempt ADD COLUMN total_tokens INTEGER
    CHECK (total_tokens >= 0);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '20')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '20')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
