-- 0005_learner_target_state.sql — Phase 2 P2B LearnerTargetState
-- projection (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.44;
-- docs/DATA_MODEL.md §11 / §12; docs/IMPLEMENTATION_PLAN.md §5
-- "Target × Modality LearnerTargetState" + "LearningSnapshot").
--
-- Authority map:
--   docs/DATA_MODEL.md §11   LearnerTargetState — base scope
--                            (target_type + target_id +
--                            evidence_modality), dimensions / coverage /
--                            freshness / projection / meta blocks, and
--                            "LearnerTargetState 是 materialized
--                            projection，可删后重建".
--   docs/DATA_MODEL.md §12   LearningSnapshot consumes the same
--                            projection rows (evidence-derived only).
--   docs/DOMAIN_MODEL.md §6  "State is rebuildable" — the projection
--                            carries estimator_version +
--                            evidence_watermark.
--   BF-01 v1.1               the estimator semantics behind the
--                            projection (elc.learning.estimator).
--
-- Physical-storage adjudication (DATA_MODEL §27 — implementation-
-- defined, recorded here): the §11 entity is persisted as ONE
-- materialized document row per (user_scope_id, target_type, target_id,
-- evidence_modality). The keyed columns (scope, target, modality,
-- estimator_version, evidence_watermark, updated_at) stay relational
-- and queryable; the §11 nested blocks (dimensions / coverage /
-- freshness / projection) live in state_json as the canonical §11
-- document. This is sound because the projection is derived,
-- deletable, and rebuildable from append-only evidence — schema
-- stability across estimator-version dimension evolution is worth more
-- than normalizing a materialized cache. The delete→rebuild equality
-- is pinned by tests/phase2.
--
-- user_scope_id: Local V1 single-user default scope (adjudicated
-- DEC-…eaaa5a1d.26 f; same key as evidence_watermark).
-- evidence_modality vocabulary: DATA_MODEL §24.14 V1 frozen values.
CREATE TABLE IF NOT EXISTS learner_target_state (
    user_scope_id      TEXT NOT NULL,
    target_type        TEXT NOT NULL
        CHECK (target_type IN ('RESOURCE', 'CAPABILITY')),
    target_id          TEXT NOT NULL,
    evidence_modality  TEXT NOT NULL
        CHECK (evidence_modality IN ('TEXT_PRODUCTION',
                                     'TEXT_COMPREHENSION')),
    estimator_version  TEXT NOT NULL,
    evidence_watermark INTEGER NOT NULL CHECK (evidence_watermark >= 0),
    state_json         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    PRIMARY KEY (user_scope_id, target_type, target_id, evidence_modality)
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '5')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '5')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
