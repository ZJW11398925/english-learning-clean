# DATA_MODEL.md

> 状态：CANONICAL IMPLEMENTATION BASELINE V1  
> 目标：定义 V1 Clean Rewrite 的 canonical data、projection、主要实体、ID、幂等与存储边界。  
> 注意：此文档先冻结语义模型，不锁死具体 SQLite DDL。

---

## 1. Storage Principles

### 1.1 Separate canonical source from projection

```text
Evidence → Learner State projection
Conversation transcript → Relationship/Episode/Index projection
content_src → content.db build artifact
```

### 1.2 Stable opaque IDs

所有 canonical entity 使用稳定 opaque ID，避免以可变文本作为主键。

### 1.3 Append-first for facts

Evidence、turn events、source assertions 等优先 append/supersede，不原地抹除历史。

### 1.4 Version every derived model

```text
estimator_version
planner_version
policy_version
evaluator_version
validator_version
content_version
curriculum_version
```

---

## 2. Suggested Physical Stores

Local Runtime V1 物理 profile：

```text
app.db       — all mutable user/runtime state needed for short atomic commits
content.db   — read-only, versioned canonical content runtime build
secret store — API keys / tokens; app.db only keeps secret_ref
```

`app.db` 可物理共址 Conversation/UserProfile/Learning/Relationship/Planner/Teaching/Runtime 等 mutable tables，是为了让 CP0/CP2/terminalization/CP3 等短事务真正原子；**物理共库不等于 Domain Authority 合并**。

Future cloud profile 可以重新拆物理存储，只要 canonical authority、atomic groups、idempotency 与 recovery 语义保持。

---

## 3. Conversation Entities

### Conversation

```text
conversation_id
persona_id?
scene_id?
created_at
status
next_turn_sequence
next_message_sequence
```

### Sequence Semantics

```text
turn_sequence
→ 每个 user-input coordination turn 严格递增；UserTurn 与该 turn 的 AssistantTurn? 共享 turn_id/turn_sequence。

message_sequence
→ canonical transcript 中每条 UserTurn / AssistantTurn 的严格顺序。
```

`DecisionCycle` 不占 message sequence；partial/cancelled AssistantTurn 若进入 canonical transcript，仍获得自己的 message sequence。

### UserTurn

```text
user_turn_id
turn_id
conversation_id
turn_sequence
message_sequence
input_id
client_message_id?
interaction_channel
raw_content
normalized_content?
created_at
```

### AssistantTurn

```text
assistant_turn_id
turn_id
conversation_id
turn_sequence
message_sequence
action_id
content
delivery_state
delivery_certainty
created_at
```

### CanonicalTurnSlice

DTO：

```text
UserTurn
AssistantTurn?  # none/partial/full
TurnOutcome
```

---

## 4. Runtime Coordination

### InputEnvelope

```text
input_id
client_message_id?
conversation_id
persona_id?
scene_id?
interaction_channel
raw_payload
received_at
```

Unique：

```text
client_message_id where present
```

### TurnRecord

```text
turn_id
conversation_id
turn_sequence
input_id
status
active_decision_cycle_id?
failure_class?
failure_reason?
runtime_version
started_at
updated_at
terminal_at?
turn_outcome?
```

### DecisionCycle

```text
decision_cycle_id
turn_id
cycle_index

learning_snapshot_id
evidence_watermark
curriculum_version
goal_version
schedule_version
policy_version
context_view_version
relationship_view_version?

planner_decision_id?
gate_decision_id?
created_at
```

Unique：

```text
(turn_id, cycle_index)
```

---

## 5. AnalysisArtifact

Durable proposal-only artifact：

```text
analysis_id
turn_id
analysis_type
producer_id
producer_version
structured_proposal
confidence
status
created_at
```

`analysis_type`：

```text
LEARNING_EVIDENCE
TEACHING_OBSERVER
USER_INTENT
CONVERSATION_PRIORITY
```

Status：

```text
PRODUCED
COMMIT_PENDING
COMMITTED
REJECTED
SUPERSEDED
```

不是 Domain truth。

---

## 5.1 Persona / Profile / Goal / Policy Canonical Objects

### CharacterPackage

```text
character_package_id
persona_id
revision
identity
personality
background
speech_style
values
boundaries
opening
scenario
generation_policy
lore_refs[]
status
updated_at
```

Owned by Persona Domain.

### UserProfile

```text
user_profile_id
revision
profile_facts
preferences
settings
updated_at
```

### DisclosurePolicy

```text
disclosure_policy_id
revision
rules[]
updated_at
```

Produces `DisclosedUserProfile` for a specific Persona/runtime context.

### LearningGoalPortfolio

```text
goal_portfolio_id
version
goals[]
modality_weights
assessment_targets[]
register_style_goals[]
effective_from
updated_at
```

### TeachingPolicyProfile

```text
teaching_policy_profile_id
version
mode
teaching_frequency
interruption_budget
curriculum_initiative
correction_strictness
hint_policy
assessment_visibility
practice_density
persona_freedom
effective_from
updated_at
```

### SessionFocus

```text
session_focus_id
conversation_id
base_goal_portfolio_version
temporary_goal_weights
manual_focus_target?
starts_at
expires_at?
```

Goal/Policy/Profile owned by User Configuration/Profile authority, not Learning.

### World/Lore

World/Lore canonical records are owned by World/Lore authority；Persona Runtime receives resolved `WorldLoreView`.

---

## 5.2 Scheduler Canonical / View Objects

### ScheduleItem

```text
schedule_item_id
target_type
target_id
evidence_modality
review_state
review_urgency
next_review_window_start?
next_review_window_end?
spacing_stage?
source_learning_watermark
version
updated_at
```

`review_state`：

```text
NOT_SCHEDULED
UPCOMING
DUE
OVERDUE
```

### ReviewEvent

```text
review_event_id
schedule_item_id
teaching_moment_id?
source_turn_id?
event_type
engaged
evidence_group_id?
created_at
```

### SessionBudgetView

Derived view：

```text
conversation_id
policy_version
automatic_teaching_used
automatic_teaching_remaining
probe_budget_remaining
cooldown_remaining
recent_skips
recent_rejections
fatigue_signal
as_of
```

---

## 5.3 Episode Projection

```text
episode_id
conversation_id
version
source_turn_sequence_start
source_turn_sequence_end
summary
open_threads[]
recent_events[]
status
updated_at
```

Episode 是 transcript-derived projection，可重建，不拥有 Conversation truth。

---

## 6. Learning Evidence Model

### EvidenceGroup

```text
evidence_group_id
source_turn_id
conversation_id
persona_id?
teaching_moment_id?
evidence_modality
created_at
```

一个 observable behavior 对应一个 group。

### EvidenceClaim

```text
evidence_claim_id
evidence_group_id
opportunity_id?

target_type
target_id

performance_type
polarity
outcome
qualifiers[]

evidence_modality
elicitation_type
spontaneity
support_level
answer_exposure_state
exposure_estimate_id?
support_attribution_certainty
support_attribution_basis

accuracy?
pragmatic_fit?
fluency?

error_attribution?

delay_seconds?
context_novelty
persona_novelty
evidence_modality_novelty

capability_evidence_basis?

source_turn_id
conversation_id
persona_id?
teaching_moment_id?

evaluator_id
evaluator_version
evaluator_confidence

status
supersedes_claim_id?
created_at
```

### Performance Type

```text
RECOGNITION
IMITATIVE_PRODUCTION
GUIDED_PRODUCTION
INDEPENDENT_PRODUCTION
SPONTANEOUS_PRODUCTION
SELF_REPAIR
FAILED_ATTEMPT
MISUSE
```

### Qualifiers

```text
DELAYED
CROSS_CONTEXT
CROSS_PERSONA
CROSS_MODALITY
NOVEL_REALIZATION
LOW_SUPPORT
HIGH_CONTEXT_NOVELTY
```

### Polarity

```text
POSITIVE
NEGATIVE
NEUTRAL
```

### Outcome

```text
SUCCESS
PARTIAL
FAILURE
ABSTAIN
```

---

## 7. LearningOpportunityRecord

```text
learning_opportunity_id
source_turn_id?
teaching_moment_id?

target_type
target_id

opportunity_type
target_explicitness
attempt_observed
alternative_realizations_allowed

created_at
```

`opportunity_type`：

```text
NATURAL
ELICITED
CONTROLLED_TASK
DIRECT_TEST
```

`target_explicitness`：

```text
IMPLICIT
SEMANTICALLY_CONSTRAINED
FORM_CONSTRAINED
EXPLICIT_TARGET
```

Target-specific negative evidence 需要 Opportunity 或 attempted use。

---

## 8. LearnerSelfReport

```text
self_report_id
user_turn_id
target_type?
target_id?
report_type
scope?
created_at
```

Types：

```text
CLAIMS_KNOWN
CLAIMS_UNKNOWN
TYPO_DECLARED
TOO_EASY
TOO_HARD
```

不直接改 Ability。

---

## 9. TeachingPreference / PlannerConstraint

```text
constraint_id
target_type?
target_id?
constraint_type
scope
starts_at
expires_at?
created_from_turn_id?
active
```

Types：

```text
DO_NOT_AUTO_TEACH
SUPPRESS_REVIEW
JUST_CHAT
MANUAL_FOCUS
```

Scope 例如：

```text
THIS_SESSION
UNTIL_DATE
UNTIL_USER_REENABLES
```

---

## 10. ExpressionNeed

```text
expression_need_id
source_turn_id
intended_meaning
context_summary?
recurrence_count
personal_relevance
last_seen_at
resolved_resources?
status
```

ExpressionNeed 属于 Personal Expression Frontier，不是 negative mastery evidence。

---

## 11. LearnerTargetState

基础作用域：

```text
target_type
target_id
evidence_modality
```

Dimensions：

```text
recognition
guided_production
independent_production
spontaneous_production
transfer
accuracy
pragmatic_control
support_dependency
```

每维：

```text
estimate?       # null = unknown
confidence
last_relevant_evidence_at?
```

Coverage：

```text
evidence_groups
independent_clusters
sessions
days
contexts
personas
realizations
modalities
```

Freshness：

```text
last_strong_retrieval_at?
elapsed_since_strong_retrieval?
freshness_band
```

Projection：

```text
ability_band
confidence_band
transfer_band
support_band
stability_band
learning_flags[]
```

Meta：

```text
estimator_version
evidence_watermark
updated_at
```

LearnerTargetState 是 materialized projection，可删后重建。

---

## 12. LearningSnapshot

```text
snapshot_id
user_scope_id
as_of
estimator_version
evidence_watermark
targets[]
```

TargetLearningView 只包含 evidence-derived learning state，不包含：

```text
goal importance
review due
teaching priority
exam importance
```

---

## 13. Curriculum / Content Runtime Views

### CurriculumCandidateView

```text
target_type
target_id
family
core_tier
prerequisites[]
core_utility
transfer_value
difficulty_estimate
teaching_cost_estimate
goal_compatibility_tags[]
```

### CurriculumLink

```text
resource_id
node_id
relation
strength
primary_flag
editorial_status
rationale
```

Relation：

```text
REALIZES
SUPPORTS
EXEMPLIFIES
CONTRASTS
REQUIRES
```

`CurriculumLink != EvidenceProjectionRule`。

---

## 13.1 ContextOpportunity / ContextOpportunitySet

Planner/Observer 的短生命周期 proposal/view：

```text
context_opportunity_id
source_turn_id
candidate_target_type?
candidate_target_id?
opportunity_kind
context_fit
meaning_relevance
communicative_impact?
interruption_cost_estimate
user_intent_alignment
observer_confidence
expires_after_turn?
```

`ContextOpportunity` 不等于 Learning 的 `LearningOpportunityRecord`，不得作为 negative Evidence 的 canonical opportunity truth。

---

## 14. Planner Data

### RawTargetCandidate / TargetCandidate

```text
candidate_id
initiative_class
origins[]
target_mode
learning_intent
focus_target
supporting_targets[]
evidence_modality

opportunity_id?
expression_need_id?
schedule_item_id?

prerequisite_state
content_readiness
evidence_goal?
preferred_support_ceiling?

benefit factors...
cost factors...
confidence...
reason_codes[]

source_turn_id?
expires_after_turn?
```

### PlannerEvaluation

```text
planner_evaluation_id
decision_cycle_id
frontier_candidate_ids[]
ranked_candidate_ids[]
factor_trace
planner_version
policy_profile_version
created_at
```

### PlannerDecision

```text
planner_decision_id
decision_cycle_id
decision
selected_candidate_id?
no_target_reason?
planner_evaluation_id
created_at
```

Decision：

```text
SELECT
NO_TARGET
```

### PlannerExecutionStatus

```text
decision_cycle_id
status
  SUCCEEDED
  DEGRADED
  FAILED
  UNAVAILABLE
error_code?
created_at
```

### RuntimeDecisionOutcome

```text
turn_id
decision_cycle_id?
outcome
  NORMAL
  DEGRADED_NO_AUTOMATIC_TEACHING
reason_codes[]
created_at
```

Runtime degradation is not a PlannerDecision.

### PlanningLedger

不记录 mastery。

```text
target/family last_selected_at
last_presented_at
teaching_exposure_counts
probe_counts
review_offers
recent_skips/rejections
overexposure_window
coverage_obligations[]
  obligation_key
  scope_type
  target_or_family_id
  goal_id?
  window_start
  window_end
  debt_value
  accrual_paused
  pause_reason?
  last_served_at?
  last_engaged_at?
coverage_debt_rollups
recent_target_families
version
```

---

## 14.1 GateDecision

```text
gate_decision_id
decision_cycle_id
candidate_id
context
  OPEN
  AUTO_CONTINUE
  USER_REQUESTED_CONTINUE
decision
  ALLOW
  DENY
reason_codes[]
policy_version
created_at
```

`NO_TARGET` 时不存在 GateDecision。

### GateExecutionStatus

```text
gate_execution_status_id
decision_cycle_id?
moment_id?
gate_context
  OPEN
  AUTO_CONTINUE
  USER_REQUESTED_CONTINUE
authorization_basis
  DECISION_CYCLE
  ACTIVE_MOMENT
authorization_status
  VALID
  INVALIDATED
  UNKNOWN
status
  SUCCEEDED
  DEGRADED
missing_or_unknown[]
created_at
```

`DEGRADED` 表示关键执行事实未知/不完整；此时不存在 synthetic `GateDecision(DENY)`。OPEN 绑定 DecisionCycle authorization；continuation 绑定 ActiveMoment authorization。

---

## 15. TeachingMoment

```text
moment_id
conversation_id
persona_id?
source

decision_cycle_id
candidate_id
gate_decision_id

focus_target
supporting_targets[]
target_mode
learning_intent
evidence_modality

evidence_goal?
preferred_support_ceiling?

learning_snapshot_id
evidence_watermark
curriculum_version
content_version
policy_version

lifecycle_state
presentation_phase
attempt_index
support_level

completion_outcome?
abort_reason?

state_version
created_at
opened_at?
teaching_terminal_at?
closed_at?
```

Source：

```text
AUTOMATIC
USER_INITIATED
MANUAL_FOCUS
SCHEDULED_STUDY
```

---

## 16. TeachingResponseEnvelope

Transient/durable analysis result：

```text
attempt_present
attempt_payload?
control_intent
target_switch_request?
clarification_request?
user_preference_signal?
interpretation_confidence
```

---

## 17. AttemptRecord / AttemptEvaluationRecord

### AttemptRecord

```text
attempt_id
moment_id
attempt_index
user_turn_id
support_level_before_attempt
answer_exposure_state
exposure_estimate_id?
support_attribution_certainty
support_attribution_basis
created_at
```

### AttemptEvaluationRecord

```text
attempt_evaluation_id
moment_id
attempt_id
evaluator_id
evaluator_version
outcome
confidence
evidence_proposal_refs[]
created_at
```

必须在下一不可逆教学动作前 durable。

---

## 18. TeachingLockLease

逻辑 contract；Local V1 canonical durable representation：

```text
conversation_id  # UNIQUE/PK
moment_id        # UNIQUE
state_version
```

CP2 与 TeachingMoment/first action 同事务取得；TEACHING_TERMINAL 与 lock release 同短事务提交。Local V1 不需要 expiry/heartbeat。Future cloud profile 可添加物理 lease metadata，但不能改变 lock identity/exclusivity。

---

## 19. ConversationCoordinatorLease

逻辑 contract。Local V1 不建立 durable distributed lease table；物理实现为：

```text
per-conversation keyed mutex
runtime_epoch
TurnRecord.owner_epoch
GenerationAction owner/action state
```

保证同一 conversation user-visible execution 串行；新 InputEnvelope/InterruptRequest 可在 guard 外先 durable。

---

## 20. Generation / Provider

### GenerationActionIntent

```text
action_id
turn_id
decision_cycle_id
moment_id?
assistant_turn_id

action_type
generation_contract_id
status
attempt_count
created_at
```

Action types：

```text
NORMAL_PERSONA_REPLY
TEACHING_OPEN
TEACHING_HINT
TEACHING_REVEAL
TEACHING_EXPLANATION
PERSONA_RESUME
```

### ProviderAttempt

```text
provider_attempt_id
action_id
attempt_no
provider_request_id?
request_hash
status
result_hash?
created_at
terminal_at?
```

多个 attempt → 一个 canonical accepted result。

---

## 21. GenerationContract

```text
generation_contract_id
action_type
persona_id
allowed_disclosures
teaching_focus?
presentation_phase?
reveal_policy?
language_policy
style_constraints
forbidden_claims[]
response_mode
max_length?
```

Forbidden claims 至少防止：

```text
未经证据的“你已经完全掌握”
未经授权的“整句已经完全地道”
```

---

## 21.1 Validator / PreDelivery Guard Records

### ValidatorResult

```text
validator_result_id
action_id
attempt_no
decision
  ACCEPT
  RETRY
  FALLBACK
  ABORT_DELIVERY
reason_codes[]
validator_version
created_at
```

### PreDeliveryGuardResult

```text
pre_delivery_guard_result_id
action_id
decision
  VALID
  INVALIDATE_ACTION
reason_codes[]
checked_lineage_version
created_at
```

---

## 22. Delivery Data

### ServerDeliveryRecord

```text
action_id
assistant_turn_id
state
sent_prefix
last_chunk_seq
started_at
terminal_at?
```

### ClientRenderAck

异步 refinement event；主 Turn 不等待 ACK 才 terminalize。

```text
action_id
assistant_turn_id
rendered_chunk_seq
rendered_text_hash
acked_at
final_rendered
```

### ExposureEstimate

```text
action_id
certainty
exposure_level
max_possible_exposure
confirmed_exposure
derivation_reason
```

Evidence 使用 conservative exposure。

---

## 22.1 ProjectionArtifact / ProjectionJob

```text
projection_id
projection_type
source_turn_id
source_turn_slice_hash
base_domain_version?
status
  PENDING
  RUNNING
  COMMITTED
  FAILED_RETRYABLE
  REJECTED
attempt_count
created_at
updated_at
```

Projection retry 必须 source-aware + version-aware revalidation，不允许 blind SQL replay。

---

## 23. Relationship Memory

```text
relationship_memory_id
user_id
persona_id
memory_type
canonical_content
source_turn_ids[]
confidence?
status
created_at
updated_at
```

`PERSONA_IMPRESSION` 与事实类型分开。

---

## 24. Content Canonical Schema Baseline（Normative）

Content authoring source of truth：

```text
content_src/*
curriculum/*
```

`content.db` 是 generated runtime artifact，不手改。

### 24.1 ContentEntity

```text
entity_id
entity_type
language
lifecycle_status
entity_revision
created_in_version
updated_in_version
```

Stable opaque IDs；entity types：

```text
LEXICAL_ENTRY
FORM
SENSE
EXPRESSION
CONSTRUCTION
EXAMPLE
```

### 24.2 LexicalEntry / Form / Sense

`LexicalEntry` 以 lemma/POS/morphological paradigm 区分；同词不同词性可为不同 entry。

`Form`：

```text
written
normalized
form_type
morph_features
pronunciation?
```

`Sense` 是主要可学习语义单位。

### 24.3 ContentText

多语言 text roles：

```text
gloss
definition
translation
usage
teaching_note
disambiguation
```

### 24.4 Expression

First-class types：

```text
COLLOCATION
LEXICAL_CHUNK
PHRASAL_VERB
IDIOM
DISCOURSE_MARKER
FUNCTIONAL_EXPRESSION
PRAGMATIC_FORMULA
SENTENCE_FRAME
```

Fixedness：

```text
FIXED
SEMI_FIXED
SLOT_BASED
```

`ExpressionVariant / RecognitionPattern` policies：

```text
EXACT
LEMMA_SEQUENCE
SLOT_PATTERN
MODEL_ASSISTED
```

Recognition proposes a match；不等于 mastery。

### 24.5 Construction / Example

Content `Construction` 不等于 Curriculum `GrammarConstruction` node；通过 `CurriculumLink` 连接。

`ExampleLink` roles：

```text
PRIMARY_TARGET
SUPPORTING
CONTRAST
ERROR_INSTANCE
```

### 24.6 Provenance

使用：

```text
ContentSource
SourceSnapshot
Assertion
```

表达来源，不采用每个字段一个 `*_source_id`。

### 24.7 Pedagogy / Labels / Curriculum Mapping

`PedagogicalProfile`：

```text
core_utility
receptive_value
productive_value
receptive_difficulty
productive_difficulty
explanation_cost
transfer_value
naturalness_value
default_target_mode
editorial_status
rationale
```

`ResourceLabel`：

```text
register
usage_modality
genre
context
style
domain
variety
```

`CurriculumLink`：

```text
resource_id
node_id
relation
strength
primary_flag
editorial_status
rationale
```

Relation：

```text
REALIZES
SUPPORTS
EXEMPLIFIES
CONTRASTS
REQUIRES
```

`CurriculumLink != EvidenceProjectionRule`。

### 24.8 Assessment

`AssessmentMembership` 保存 source fact；`PackOverlay` 保存内部教学策略/权重，二者分离。

### 24.9 TypicalError

```text
learner_l1?
error_type
error_pattern
corrected_pattern
explanation
severity
detection_policy
```

### 24.10 Readiness

```text
R0 INDEXED
R1 LEXICALLY_RESOLVED
R2 PLANNER_READY
R3 TEACHING_READY
R4 DETECTION_READY
```

R4 必须包含可测试 detection policy/fixtures/false-positive boundary。

### 24.11 Lifecycle

```text
RAW_IMPORTED
NORMALIZED
SENSE_RESOLVED / STRUCTURED
ENRICHED
CURRICULUM_MAPPED
PEDAGOGICALLY_ANNOTATED
REVIEW_REQUIRED
CANONICAL_APPROVED
DEPRECATED / REPLACED
```

Model-generated candidate 默认不是 `CANONICAL_APPROVED`。

### 24.12 EntityMigration

```text
REPLACED
MERGED
SPLIT
DEPRECATED
```

SPLIT 不得自动复制 mastery。

### 24.13 Runtime Aggregate

`TeachingUnit` 是 runtime aggregate DTO，不是 canonical mega-table。

---


## 24.14 Behavioral Baseline V1 Additions

### GoalModality / EvidenceModality / InteractionChannel

```text
GoalModality: SPEAKING | LISTENING | READING | WRITING
V1 EvidenceModality: TEXT_PRODUCTION | TEXT_COMPREHENSION
Future EvidenceModality: VOICE_PRODUCTION | AUDIO_COMPREHENSION
InteractionChannel V1: TEXT
```

`LearnerTargetState` key：

```text
target_type + target_id + evidence_modality
```

`fluency?` 在 TEXT modality 中不得解释为 speaking fluency；未来 pronunciation/speaking_fluency 只能由 VOICE_PRODUCTION evaluator 写入。

### EstimatorClaimView

Estimator 使用 deterministic read projection，至少包含：performance/polarity/outcome/qualifiers/support/exposure/evaluator_confidence/error_attribution/quality/context/persona/realization/evidence_modality/status。矛盾 label（如 INDEPENDENT + answer exposure）必须在 Learning validator/strict estimator input contract 拒绝。

### Planner Candidate Additions

```text
canonical_key
request_priority
goal_relation = NONE | PREPARATORY | DIRECT_TARGET_LEVEL
communicative_impact
coverage_service_state
```

当前 runtime 无 direct observation 的 SPEAKING/LISTENING direct obligation：

```text
UNAVAILABLE_IN_CURRENT_RUNTIME
```

不累计 impossible direct CoverageDebt；对应 text target 可以有 PREPARATORY goal relevance。

### Gate Authorization

```text
authorization_basis = DECISION_CYCLE | ACTIVE_MOMENT
authorization_status = VALID | INVALIDATED | UNKNOWN
GateExecutionStatus = SUCCEEDED | DEGRADED
```

OPEN 使用 DECISION_CYCLE；continuation 使用 ACTIVE_MOMENT。

### Security / Deletion Records

长期 private/derived records 必须保留 provenance/source ids，支持 source-aware deletion/rebuild。Portable export 排除 Secret 与默认 RuntimeDiagnostic raw content。Deletion tombstone 仅保存 opaque id/scope/version/hash metadata，不保存已删 plaintext。Provider disclosure 可记录 action/provider/data-class/time/remote-revocation capability receipt。

### Local Runtime Metadata

```text
runtime_epoch
owner_epoch
projection_job(state, source_turn_id, projection_type, source_version)
active_teaching_lock(conversation_id UNIQUE, moment_id UNIQUE, state_version)
```

## 25. Key Unique / Idempotency Constraints

建议：

```text
UNIQUE(client_message_id)
UNIQUE(turn_id, cycle_index)
Local V1: keyed mutex uniqueness per conversation; cloud profile may use UNIQUE(active coordinator lease)
UNIQUE(conversation_id, active_teaching_lock)
UNIQUE(action_id, provider_attempt attempt_no)
UNIQUE(moment_id, attempt_index)
```

Evidence commit key：

```text
moment_id
+ attempt_id
+ target_id
+ claim_role
+ evaluator_version
```

Post-turn projection 也需要 stable projection identity。

---

## 26. Rebuildable Projections

可重建：

```text
LearnerTargetState
LearningSnapshot
Relationship retrieval index
Episode summary/index
FTS/vector index
analytics rollups
some PlanningLedger rollups
```

不可把 rebuildable projection 当唯一事实来源。

---

## 26.1 Schema / Runtime Metadata

```text
schema_version
runtime_schema_version
content_db_version
curriculum_version
last_migration_id
updated_at
```

数据库迁移必须显式更新版本，禁止依赖代码猜 schema。

---

## 27. Data Model Non-goals

本阶段不冻结：

```text
具体 SQL column type
具体 index 名
SQLite PRAGMA
queue implementation
encryption implementation
sync protocol
```

这些进入实现设计，但不得改变本文语义边界。
