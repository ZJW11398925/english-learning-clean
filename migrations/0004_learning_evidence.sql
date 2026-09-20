-- 0004_learning_evidence.sql — Phase 2 P2A Learning durable core
-- (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.30; docs/
-- IMPLEMENTATION_PLAN.md §5 Learning Evidence Kernel).
--
-- Authority map (canonical column names follow the cited sections
-- verbatim; every column outside the cited sets is individually
-- justified below):
--   docs/DATA_MODEL.md §5   analysis_artifact (proposal-only, "不是
--                           Domain truth") + analysis_type / status
--                           vocabularies
--   docs/DATA_MODEL.md §6   evidence_group / evidence_claim + performance
--                           type / qualifiers / polarity / outcome
--                           vocabularies
--   docs/DATA_MODEL.md §7   learning_opportunity_record + opportunity_
--                           type / target_explicitness vocabularies
--   docs/DATA_MODEL.md §8   learner_self_report + report_type vocabulary
--   docs/DATA_MODEL.md §10  expression_need
--   docs/DATA_MODEL.md §24.14  EvidenceModality V1 frozen values
--                           (TEXT_PRODUCTION / TEXT_COMPREHENSION)
--   docs/DATA_MODEL.md §25  Evidence commit key (moment_id + attempt_id
--                           + target_id + claim_role + evaluator_version)
--   docs/DOMAIN_MODEL.md §6  evidence status ACTIVE/SUPERSEDED/
--                           INVALIDATED is pinned word-for-word by
--                           docs/STATE_MACHINES.md §18 ("Learning
--                           Evidence State Semantics"); claim targets are
--                           RESOURCE or CAPABILITY ("每个 claim 独立指向
--                           RESOURCE / CAPABILITY")
--   docs/RUNTIME_ARCHITECTURE.md §6 CP1 + §4 step 4  "materialize new
--                           evidence watermark" — the watermark is durable
--                           and monotonically increasing; DOMAIN_MODEL §6
--                           "State is rebuildable" (state carries
--                           estimator_version + evidence_watermark).
--
-- Physical-table decisions outside the six canonical column sets
-- (each is durable infrastructure, not domain truth):
--   evidence_watermark  — CP1 watermark storage face (RA §4 step 4;
--                         consumed by P2B LearnerTargetState §11 Meta /
--                         LearningSnapshot §12). One row per
--                         user_scope_id; Local V1 single-user default
--                         scope (adjudicated DEC-…eaaa5a1d.26 f).
--   evidence_commit     — the durable CP1 commit fact (which commit
--                         produced which watermark) so commit replay is
--                         idempotent and "crash after CP1 does not
--                         repeat Evidence" (RA §22/§23) is checkable.

-- DATA_MODEL §5 AnalysisArtifact — durable proposal-only artifact
-- ("不是 Domain truth"). Status vocabulary is the §5 five-value list;
-- Phase 2 P2A drives PRODUCED → COMMITTED / REJECTED (COMMIT_PENDING /
-- SUPERSEDED reserved for the later real-LLM analysis phases).
-- Idempotency: RA §4 step 3 produces durable artifacts per turn; the
-- unique (turn_id, analysis_type, producer_id) makes re-running analysis
-- after "crash after CP0" (RA §23) replay instead of double-producing.
CREATE TABLE IF NOT EXISTS analysis_artifact (
    analysis_id          TEXT PRIMARY KEY,
    turn_id              TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    analysis_type        TEXT NOT NULL
        CHECK (analysis_type IN (
            'LEARNING_EVIDENCE', 'TEACHING_OBSERVER', 'USER_INTENT',
            'CONVERSATION_PRIORITY')),
    producer_id          TEXT NOT NULL,
    producer_version     TEXT NOT NULL,
    structured_proposal  TEXT NOT NULL,
    confidence           REAL NOT NULL,
    status               TEXT NOT NULL
        CHECK (status IN (
            'PRODUCED', 'COMMIT_PENDING', 'COMMITTED', 'REJECTED',
            'SUPERSEDED')),
    created_at           TEXT NOT NULL,
    UNIQUE (turn_id, analysis_type, producer_id)
);

-- DATA_MODEL §7 LearningOpportunityRecord — "Target-specific negative
-- evidence 需要 Opportunity 或 attempted use" (§7 note; DOMAIN_MODEL §6
-- Negative evidence rule). opportunity_type / target_explicitness
-- vocabularies are the §7 lists. attempt_observed /
-- alternative_realizations_allowed are booleans (0/1). Created before
-- evidence_claim because evidence_claim.opportunity_id references it.
CREATE TABLE IF NOT EXISTS learning_opportunity_record (
    learning_opportunity_id          TEXT PRIMARY KEY,
    source_turn_id                   TEXT
        REFERENCES turn_record(turn_id),
    teaching_moment_id               TEXT,
    target_type                      TEXT NOT NULL
        CHECK (target_type IN ('RESOURCE', 'CAPABILITY')),
    target_id                        TEXT NOT NULL,
    opportunity_type                 TEXT NOT NULL
        CHECK (opportunity_type IN (
            'NATURAL', 'ELICITED', 'CONTROLLED_TASK', 'DIRECT_TEST')),
    target_explicitness              TEXT NOT NULL
        CHECK (target_explicitness IN (
            'IMPLICIT', 'SEMANTICALLY_CONSTRAINED', 'FORM_CONSTRAINED',
            'EXPLICIT_TARGET')),
    attempt_observed                 INTEGER NOT NULL
        CHECK (attempt_observed IN (0, 1)),
    alternative_realizations_allowed INTEGER NOT NULL
        CHECK (alternative_realizations_allowed IN (0, 1)),
    created_at                       TEXT NOT NULL
);

-- DATA_MODEL §6 EvidenceGroup — "一个 observable behavior 对应一个
-- group". The (source_turn_id, evidence_modality) unique index is the
-- P2A deterministic-producer granularity (one observable behavior per
-- turn × modality); a future multi-behavior producer widens it via
-- migration. evidence_modality vocabulary: §24.14 V1 frozen values.
CREATE TABLE IF NOT EXISTS evidence_group (
    evidence_group_id    TEXT PRIMARY KEY,
    source_turn_id       TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    conversation_id      TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    persona_id           TEXT,
    teaching_moment_id   TEXT,
    evidence_modality    TEXT NOT NULL
        CHECK (evidence_modality IN ('TEXT_PRODUCTION',
                                     'TEXT_COMPREHENSION')),
    created_at           TEXT NOT NULL,
    UNIQUE (source_turn_id, evidence_modality)
);

-- DATA_MODEL §6 EvidenceClaim — column set verbatim from §6:425-474.
-- Physical additions beyond the canonical set (both justified by
-- canonical constraint lists, mirroring the 0002 owner_epoch precedent):
--   attempt_id  — DATA_MODEL §25 Evidence commit key member.
--   claim_role  — DATA_MODEL §25 Evidence commit key member (also a
--                 Phase 0 protocol field, elc.learning.types.
--                 EvidenceClaimView.claim_role).
-- The §25 commit-key unique index deliberately keeps NULL moments/
-- attempts distinct (SQLite unique-NULL semantics): while teaching-flow
-- phases have not opened (moment_id/attempt_id NULL), double-commit
-- protection is carried by the evidence_group primary key + the
-- evidence_commit unique; the full §25 key tightens when those columns
-- go non-NULL.
-- qualifiers: stored as a JSON text array of the §6 seven-value
-- vocabulary (storage form is implementation-defined, DATA_MODEL §27).
-- status: ACTIVE/SUPERSEDED/INVALIDATED word-for-word from
-- STATE_MACHINES §18 (append-only evidence; only ACTIVE evidence enters
-- estimation).
CREATE TABLE IF NOT EXISTS evidence_claim (
    evidence_claim_id              TEXT PRIMARY KEY,
    evidence_group_id              TEXT NOT NULL
        REFERENCES evidence_group(evidence_group_id),
    opportunity_id                 TEXT
        REFERENCES learning_opportunity_record(learning_opportunity_id),
    target_type                    TEXT NOT NULL
        CHECK (target_type IN ('RESOURCE', 'CAPABILITY')),
    target_id                      TEXT NOT NULL,
    performance_type               TEXT NOT NULL
        CHECK (performance_type IN (
            'RECOGNITION', 'IMITATIVE_PRODUCTION', 'GUIDED_PRODUCTION',
            'INDEPENDENT_PRODUCTION', 'SPONTANEOUS_PRODUCTION',
            'SELF_REPAIR', 'FAILED_ATTEMPT', 'MISUSE')),
    polarity                       TEXT NOT NULL
        CHECK (polarity IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')),
    outcome                        TEXT NOT NULL
        CHECK (outcome IN ('SUCCESS', 'PARTIAL', 'FAILURE', 'ABSTAIN')),
    qualifiers                     TEXT NOT NULL,
    evidence_modality              TEXT NOT NULL
        CHECK (evidence_modality IN ('TEXT_PRODUCTION',
                                     'TEXT_COMPREHENSION')),
    elicitation_type               TEXT NOT NULL,
    spontaneity                    TEXT NOT NULL,
    support_level                  TEXT NOT NULL,
    answer_exposure_state          TEXT NOT NULL,
    exposure_estimate_id           TEXT,
    support_attribution_certainty  REAL NOT NULL,
    support_attribution_basis      TEXT NOT NULL,
    accuracy                       REAL,
    pragmatic_fit                  REAL,
    fluency                        REAL,
    error_attribution              TEXT,
    delay_seconds                  INTEGER,
    context_novelty                REAL NOT NULL,
    persona_novelty                REAL NOT NULL,
    evidence_modality_novelty      REAL NOT NULL,
    capability_evidence_basis      TEXT,
    source_turn_id                 TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    conversation_id                TEXT NOT NULL
        REFERENCES conversation(conversation_id),
    persona_id                     TEXT,
    teaching_moment_id             TEXT,
    evaluator_id                   TEXT NOT NULL,
    evaluator_version              TEXT NOT NULL,
    evaluator_confidence           REAL NOT NULL,
    status                         TEXT NOT NULL
        CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'INVALIDATED')),
    supersedes_claim_id            TEXT
        REFERENCES evidence_claim(evidence_claim_id),
    attempt_id                     TEXT,
    claim_role                     TEXT,
    created_at                     TEXT NOT NULL,
    UNIQUE (teaching_moment_id, attempt_id, target_id, claim_role,
            evaluator_version)
);

-- DATA_MODEL §8 LearnerSelfReport — "不直接改 Ability". report_type is
-- the §8 five-value list. Target columns keep the RESOURCE/CAPABILITY
-- vocabulary (DOMAIN_MODEL §6 claim targets).
CREATE TABLE IF NOT EXISTS learner_self_report (
    self_report_id    TEXT PRIMARY KEY,
    user_turn_id      TEXT NOT NULL
        REFERENCES user_turn(user_turn_id),
    target_type       TEXT
        CHECK (target_type IS NULL OR target_type IN ('RESOURCE',
                                                      'CAPABILITY')),
    target_id         TEXT,
    report_type       TEXT NOT NULL
        CHECK (report_type IN (
            'CLAIMS_KNOWN', 'CLAIMS_UNKNOWN', 'TYPO_DECLARED', 'TOO_EASY',
            'TOO_HARD')),
    scope             TEXT,
    created_at        TEXT NOT NULL
);

-- DATA_MODEL §10 ExpressionNeed — Personal Expression Frontier, "不是
-- negative mastery evidence". status vocabulary is not pinned by §10;
-- P2A derives OPEN/RESOLVED from the §10 resolved_resources semantics
-- (adjudicated: implementation-defined vocabulary, DATA_MODEL §27).
CREATE TABLE IF NOT EXISTS expression_need (
    expression_need_id    TEXT PRIMARY KEY,
    source_turn_id        TEXT NOT NULL
        REFERENCES turn_record(turn_id),
    intended_meaning      TEXT NOT NULL,
    context_summary       TEXT,
    recurrence_count      INTEGER NOT NULL CHECK (recurrence_count > 0),
    personal_relevance    TEXT NOT NULL,
    last_seen_at          TEXT NOT NULL,
    resolved_resources    TEXT,
    status                TEXT NOT NULL
        CHECK (status IN ('OPEN', 'RESOLVED'))
);

-- CP1 watermark storage face (RA §4 step 4 "materialize new evidence
-- watermark"; DOMAIN_MODEL §6 "State is rebuildable": the projection
-- carries estimator_version + evidence_watermark). Monotonically
-- increasing, one row per user_scope_id; Local V1 single-user default
-- scope (DEC-…eaaa5a1d.26 f). Absence of a row means watermark 0.
CREATE TABLE IF NOT EXISTS evidence_watermark (
    user_scope_id    TEXT PRIMARY KEY,
    watermark        INTEGER NOT NULL CHECK (watermark >= 0),
    updated_at       TEXT NOT NULL
);

-- Durable CP1 commit fact: which commit produced which watermark, for
-- which group / artifact. Powers commit replay idempotency and the
-- "crash after CP1 does not repeat Evidence" recovery check (RA §22/§23).
CREATE TABLE IF NOT EXISTS evidence_commit (
    evidence_commit_id    TEXT PRIMARY KEY,
    evidence_group_id     TEXT NOT NULL UNIQUE
        REFERENCES evidence_group(evidence_group_id),
    analysis_id           TEXT
        REFERENCES analysis_artifact(analysis_id),
    user_scope_id         TEXT NOT NULL,
    watermark_after       INTEGER NOT NULL CHECK (watermark_after > 0),
    committed_at          TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '4')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '4')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
