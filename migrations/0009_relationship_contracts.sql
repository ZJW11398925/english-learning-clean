-- 0009_relationship_contracts.sql — Phase 4 P4-0: Phase 3 carryover +
-- memory/projection contracts (TASK-OPI-5ba74efc-9f26-483b-a7de-c833834275a4.84
-- ①③; 设计权威 DEC-OPI-5ba74efc-9f26-483b-a7de-c833834275a4.68 C1/C2/F).
--
-- Two tables land here, and nothing else: the runtime faces that write them
-- belong to P4-1 (Relationship durable core) / P4-2 (CP4 projection runtime).
-- This migration is DDL + vocabulary only — no backfill, no rebuild, no row
-- is created by it.
--
-- Authority map (canonical first; every column outside a cited set is
-- individually justified below):
--   docs/RUNTIME_ARCHITECTURE.md §21 "Learning commit unavailable" →
--                             "durable proposal pending / normal persona /
--                             no risky automatic remediation/probe"
--                             (the semantic gap C1 closes: today an Attempt
--                             and its Evaluation are durable while the
--                             evidence may never reach LearnerState).
--   docs/DOMAIN_MODEL.md §18  Proposal-only components — the Relationship
--                             Recorder proposal is validated/committed by
--                             the Domain Controller, never by the proposal.
--   docs/DOMAIN_MODEL.md §5   Relationship Domain: unit Persona × User,
--                             the eight memory types, the
--                             USER_STATED_FACT / SYSTEM_INFERRED_FACT /
--                             PERSONA_IMPRESSION distinction (the provenance
--                             vocabulary, word for word), and the write flow
--                             proposal → validate/dedupe → canonical memory.
--   docs/DOMAIN_MODEL.md §17  Memory Separation: "Relationship 不跨 Persona
--                             泄漏" (the persona_id/user_id pair is the
--                             scope key, never a cross-persona read).
--   docs/DOMAIN_MODEL.md §18.1 Trust/Privacy Authority: "高敏感 Profile/
--                             Relationship persistence 需要显式用户许可；
--                             模型不得把推断的高敏感属性直接提交为长期事实".
--   docs/DATA_MODEL.md §23    Relationship Memory column set — the *naming*
--                             authority of the second table below
--                             (relationship_memory_id / canonical_content /
--                             source_turn_ids[] / confidence? / status /
--                             created_at / updated_at + user_id / persona_id
--                             / memory_type, verbatim).
--   docs/DATA_MODEL.md §1.4   "Version every derived model" (recorder /
--                             validator versions are durable, not inferred).
--   behavioral_baselines/security/security_privacy_policy_v1.json (BF-05):
--                             data_classes PERSONAL (examples include
--                             "relationship memories") and HIGH_SENSITIVITY
--                             (auto_promote_to_durable_memory = false,
--                             explicit_persistence_required = true);
--                             sensitive_memory_policy
--                             automatic_relationship_promotion = DENY,
--                             explicit_user_persistence =
--                             ALLOW_AFTER_VALIDATION; trust_classes
--                             TRUSTED_AUTHORITY =
--                             "domain-validated canonical write".
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--
-- ---------------------------------------------------------------------------
-- 1. teaching_evidence_proposal — Learning-owned durable proposal
--
-- docs/RUNTIME_ARCHITECTURE.md §21 (:616-621) names the state this table
-- makes durable: when the Learning commit is unavailable, the proposal stays
-- *pending* — durably — instead of vanishing with the process. The owner is
-- the Learning domain (docs/DOMAIN_MODEL.md §6 "Learning Evidence kernel
-- keeps the truth"; §16 D-INV-001: the orchestrator never writes domain
-- truth), so the table lives in app.db next to the evidence kernel it feeds
-- and is written only by elc.learning.store.
--
-- Deliberately NOT a projection_job row: projection_job (migrations/0002,
-- DATA_MODEL §22.1) is the CP4 derived-projection work queue whose failure
-- never rolls back a turn (RUNTIME §19). A pending teaching-evidence
-- proposal is *canonical evidence input* — Learning's own commit backlog —
-- not a rebuildable projection; conflating them would make evidence truth
-- depend on a projection retry policy. Pinned by test.
--
-- Column set (TASK-…84 ① / DEC-…68 C1): the proposal identity, the durable
-- lineage it was produced from, the versioned provenance of the evaluation
-- that made it, the payload Learning will commit, and the retry state:
--   proposal_id          deterministic "tep-{attempt_id}" (the same string
--                        the teaching side writes into §17
--                        evidence_proposal_refs — the double-namespace
--                        reconciliation of TASK-…84 ①).
--   source_attempt_id    FK attempt_record — the attempt whose evaluation
--                        produced this proposal (durable before it: the
--                        §17 write-order rule).
--   source_evaluation_id FK attempt_evaluation_record — the evaluation
--                        itself; one proposal per attempt/evaluation pair.
--   moment_id            FK teaching_moment — the episode the evidence
--                        belongs to (the §25 commit key's moment leg).
--   provenance           JSON (target_type / target_id / evaluator_id /
--                        evaluator_version / payload_hash): the versioned
--                        provenance of the proposal, i.e. what the payload
--                        was computed from and who computed it.
--   payload              the serialized claim views Learning will commit
--                        plus the commit context (group id, source turn,
--                        conversation, persona) — canonical JSON, so a
--                        retry after a crash needs no live teaching object
--                        and no cross-domain read.
--   status               PENDING / COMMITTED / REJECTED (the AnalysisArtifact
--                        vocabulary precedent, migration 0004:412-420: the
--                        artifact is PRODUCED until the commit unit flips it
--                        COMMITTED or a validation refusal flips it
--                        REJECTED; here PENDING is the durable-pending
--                        spelling of that same pre-commit state).
--   attempt_count        commit attempts made so far (0 = recorded, never
--                        attempted; RA §21 "no risky automatic
--                        remediation" — the retry face is explicit).
--   created_at /         durable timestamps; committed_at is NULL until the
--   updated_at /         commit actually lands, which is what makes
--   committed_at         "pending" auditable rather than inferred.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teaching_evidence_proposal (
    proposal_id          TEXT PRIMARY KEY,
    source_attempt_id    TEXT NOT NULL
        REFERENCES attempt_record(attempt_id),
    source_evaluation_id TEXT NOT NULL
        REFERENCES attempt_evaluation_record(attempt_evaluation_id),
    moment_id            TEXT NOT NULL
        REFERENCES teaching_moment(moment_id),
    provenance           TEXT NOT NULL,
    payload              TEXT NOT NULL,
    status               TEXT NOT NULL
        CHECK (status IN ('PENDING', 'COMMITTED', 'REJECTED')),
    attempt_count        INTEGER NOT NULL CHECK (attempt_count >= 0),
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    committed_at         TEXT
);

-- The retry face reads exactly the PENDING backlog in durable order.
CREATE INDEX IF NOT EXISTS idx_teaching_evidence_proposal_status
    ON teaching_evidence_proposal (status, created_at, proposal_id);

-- ---------------------------------------------------------------------------
-- 2. relationship_memory — the canonical Persona × User memory row
--
-- DDL only: the Recorder / validate-dedupe / append-first supersede write
-- faces are P4-1 (docs/DOMAIN_MODEL.md §5 write flow).
--
-- Column naming authority: docs/DATA_MODEL.md §23, verbatim. The Phase 0
-- record's ``memory_id`` / ``content`` spellings are superseded by §23's
-- ``relationship_memory_id`` / ``canonical_content`` (canonical text outranks
-- the Phase 0 skeleton; the record type is synced in the same slice). The
-- columns beyond §23 are marked 增列 below and are the only additions — they
-- are authorized by DEC-…5ba74efc.68 C/F. The physical order groups identity
-- → scope → type/provenance → content → source → status → additions →
-- timestamps; the canonical *set* is §23 + the marked additions (ordering is
-- implementation-defined, DATA_MODEL §27).
--
--   §23 columns, word for word:
--     relationship_memory_id  TEXT PRIMARY KEY — §23; §1.2 stable opaque id.
--     user_id          TEXT NOT NULL — §23; one leg of the §5 unit.
--     persona_id       TEXT NOT NULL — §23; the other leg (§5 unit Persona ×
--                      User; §17 "Relationship 不跨 Persona 泄漏").
--     memory_type      TEXT NOT NULL CHECK — §23; DOMAIN_MODEL §5 "Memory
--                      types" word for word (the eight words below).
--     canonical_content TEXT NOT NULL — §23.
--     source_turn_ids  TEXT NOT NULL — §23 ``source_turn_ids[]``; JSON array
--                      (the 0004 qualifier-list precedent: arrays are JSON
--                      text, never a second table).
--     confidence       REAL (nullable) — §23 ``confidence?``; NULL = a user
--                      statement rather than a scored inference (§5
--                      "Important distinction").
--     status           TEXT NOT NULL CHECK — §23. §23 pins no status
--                      vocabulary; the three words are the ones the Phase 0
--                      record carried and are kept as the
--                      implementation-defined spelling (§27) until canonical
--                      lands a list (append-first semantics: corrections
--                      supersede, history is not erased — DATA_MODEL §1.3).
--     created_at / updated_at TEXT NOT NULL — §23.
--
--   增列 (DEC-…5ba74efc.68 C/F authorization; §23 has none of these, each is
--   required by the rule cited):
--     provenance       TEXT NOT NULL CHECK — §23 carries no provenance
--                      column; the vocabulary is DOMAIN_MODEL §5 "Important
--                      distinction", word for word: USER_STATED_FACT /
--                      SYSTEM_INFERRED_FACT / PERSONA_IMPRESSION. BF-05
--                      corroborates the spelling independently
--                      (security_benchmark_v1.json ``proposal_kind``:
--                      "USER_STATED_FACT" / "SYSTEM_INFERRED_FACT";
--                      SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md §289
--                      "`USER_STATED_FACT` 必须有真实 UserTurn provenance").
--     source_turn_id   TEXT (nullable) REFERENCES turn_record — the one turn a
--                      memory was read from; NULL for a memory with no single
--                      originating turn (§17 traceability).
--     provenance_refs  TEXT NOT NULL — the durable refs the memory was
--                      derived from (turn / message ids): BF-05 §18.1
--                      requires relationship writes to be traceable to their
--                      source.
--     supersedes_memory_id TEXT (nullable) self-FK — append-first supersede:
--                      the replacement row points at the row it corrects; the
--                      replaced row keeps its history (§1.3).
--     recorder_version TEXT NOT NULL — §1.4 "version every derived model":
--                      VERSION_FIELDS has no "recorder_version" key, so the
--                      spelling follows the review list and carries the
--                      version of the Recorder that proposed the row.
--     validator_version TEXT (nullable) — the validator that committed it;
--                      NULL when the write did not pass through a
--                      model-assisted validator but through a TRUSTED_AUTHORITY
--                      typed/validated command (DOMAIN_MODEL §18.1).
--     sensitivity_class TEXT NOT NULL CHECK — BF-05 data_classes: PERSONAL is
--                      the class whose examples include "relationship
--                      memories"; HIGH_SENSITIVITY is the class BF-05 pins to
--                      auto_promote_to_durable_memory = false. No other BF-05
--                      class is legal for a relationship memory.
--     persistence_authorization TEXT NOT NULL CHECK — the authorization the
--                      row was persisted under, from BF-05 trust_classes /
--                      sensitive_memory_policy: VALIDATED_DOMAIN_WRITE
--                      (TRUSTED_AUTHORITY "domain-validated canonical write")
--                      or USER_EXPLICIT_CONSENT (explicit_persistence_required
--                      / DOMAIN_MODEL §18.1 "高敏感 … 需要显式用户许可").
--
--   One cross-column rule, in the schema rather than only in a docstring
--   (DOMAIN_MODEL §18.1 + BF-05 HIGH_SENSITIVITY.explicit_persistence_required
--   = true): a HIGH_SENSITIVITY row may only be persisted under
--   USER_EXPLICIT_CONSENT. A model-inferred high-sensitivity attribute can
--   therefore never become a durable long-term fact by write path alone.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS relationship_memory (
    relationship_memory_id    TEXT PRIMARY KEY,
    persona_id                TEXT NOT NULL,
    user_id                   TEXT NOT NULL,
    memory_type               TEXT NOT NULL
        CHECK (memory_type IN ('USER_STATED_FACT', 'SHARED_EVENT',
                               'PERSONA_IMPRESSION', 'PROMISE', 'OPEN_THREAD',
                               'RUNNING_JOKE', 'RELATIONSHIP_EVENT',
                               'CONVERSATION_PREFERENCE')),
    provenance                TEXT NOT NULL
        CHECK (provenance IN ('USER_STATED_FACT', 'SYSTEM_INFERRED_FACT',
                              'PERSONA_IMPRESSION')),
    canonical_content         TEXT NOT NULL,
    source_turn_id            TEXT REFERENCES turn_record(turn_id),
    status                    TEXT NOT NULL
        CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'WITHDRAWN')),
    source_turn_ids           TEXT NOT NULL,
    provenance_refs           TEXT NOT NULL,
    confidence                REAL
        CHECK (confidence IS NULL OR
               (confidence >= 0.0 AND confidence <= 1.0)),
    supersedes_memory_id      TEXT
        REFERENCES relationship_memory(relationship_memory_id),
    recorder_version          TEXT NOT NULL,
    validator_version         TEXT,
    sensitivity_class         TEXT NOT NULL
        CHECK (sensitivity_class IN ('PERSONAL', 'HIGH_SENSITIVITY')),
    persistence_authorization TEXT NOT NULL
        CHECK (persistence_authorization IN ('USER_EXPLICIT_CONSENT',
                                             'VALIDATED_DOMAIN_WRITE')),
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL,
    CHECK (NOT (sensitivity_class = 'HIGH_SENSITIVITY'
                AND persistence_authorization != 'USER_EXPLICIT_CONSENT'))
);

-- The Persona × User scope read (DOMAIN_MODEL §5/§17: a relationship view is
-- always one pair, never a cross-persona scan) and the supersede chain walk.
CREATE INDEX IF NOT EXISTS idx_relationship_memory_scope
    ON relationship_memory (persona_id, user_id, status, created_at);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '9')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '9')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
