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

## 26.2 Narrative V3 Additions（V3-1 实现合同）

> 依据：`docs/design/2026-10-12-narrative-v3-paradigm-shift.md`（v3.1 / V3-0R）+ `DOMAIN_MODEL.md §20`。语义在此冻结；具体 SQLite DDL 由 V3-1 migration 设计（0029+），但不得改变本节语义边界（design-first）。

### 26.2.1 实体合同（字段为语义字段，非最终列名）

```text
world_bible_revision          # 实例级 World Bible（权威）
  world_id, revision, parent_revision?
  premise, genre, tone, calendar, physics, magic_rules,
  geography, society, politics, technology, religion, history,
  hard_rules, narrative_preferences
  status: CURRENT | SUPERSEDED（append-only 版本化；不减删）
  注：模板/Package 只在创建时 seed（parent_revision 记录来源）；
      模板后续更新不改写本表（N-INV-006；V3-2 实现）

world_player_character        # durable 用户角色（不改 world_actor）
  player_character_id, world_id, name, background, appearance,
  abilities, limits, location, state, knowledge_refs?
  # identity/seed 冻结见本节末（V3-3R）

world_actor_profile           # AI actor 的叙事档案（CharacterCard ≠ 本表）
  actor_id, world_id, story_role（PROTAGONIST|MAJOR|SUPPORTING）,
  pov_eligible, pov_weight, long_term_drive, current_arc_seed,
  private_context

world_chapter                 # 章（canon 面进度）
  chapter_id, world_id, chapter_index, status（§21）,
  opened_at_tick, closed_at_tick?

world_chapter_plan            # 章规划（PLAN 面，append-only 版本化）
  chapter_plan_id, chapter_id, plan_revision, status（§24）,
  goal, dramatic_question, planned_start_tick, planned_end_tick,
  closing_pressure, desired_development, soft_outcomes,
  chapter_questions_to_advance, scenes_json（场景表）

world_scene                   # 场（canon 面进度）
  scene_id, chapter_id, scene_index, status（§22）,
  actual_start_tick, actual_end_tick?

world_scene_dossier           # 场的执行规划（PLAN 面；重规划 = 新版本）
  dossier_id, scene_id, dossier_revision,
  pov_actor_id, participants, place, planned_start_tick,
  revealable, must_hide, entry_goals, exit_condition, elasticity

narrative_passage             # 正文（CANON 面；不可变）
  passage_id, scene_id, segment_seq, body, language,
  outcome_ref?（引用已 committed 的 action outcome；Writer 只呈现）
  created_at_tick

user_gate                     # 用户意志停点
  gate_id, scene_id, status（§23）, opened_at_tick,
  options_json（2–4 选项 + 自由输入）

user_action                   # 用户提交与裁定
  user_action_id, gate_id, submission_id（幂等锚点；UNIQUE(gate_id, submission_id)）,
  intent_text, selected_option?,
  status: ANSWERED | RESOLVING | COMMITTED,
  interpretation, outcome, actual_action, consequences,
  state_effects, participants, replan_scope（NONE|SCENE|CHAPTER）,
  actual_tick（裁定终态的 story tick——ACTION 族的 Canon 时间锚）

actor_memory / belief         # （V3-7 物化；V3-5 不做，路径见 §26.2.3）
  memory_id, world_id, actor_id（或 player_character_id）,
  kind: EXPERIENCED | HEARD | BELIEVED | INFERRED | MISTAKEN?,
  content, source_event_id?, learned_at_tick, salience?

chapter_settlement            # 章末压缩产出（Narrative Memory）
  chapter_id, summary, storyline_updates, hooks, resolved_lines,
  salience_notes, created_at_revision

reader_exposure               # 读者暴露面（记录语义；本轮无 metagame）
  exposure_id, passage_id, reader_id（MVP = 本地用户）, exposed_at
  边界：不写 actor_memory / belief（N-INV-005）
  建表刀位：随 V3-5；**与 SEGMENT COMMIT 解耦（评审 #2，V3-5 硬门）**——
  passage commit ≠ 用户已看见；exposure 在交付/渲染侧独立记录（MVP 可保守
  estimate），绝不与提交同事务充当 reader knowledge
```

**V3-5 落表形（开工裁决 `DEC-OPI-be7b094f-…32`，2026-10-12；migration `0033`）**：

- `narrative_passage`（正文，CANON 面不可变）：`passage_id` TEXT PK（**由 segment_key 派生** = `f"{scene_id}-p{segment_seq:04d}"`；派生只服务幂等重放，§26.2.2 的 lineage 纪律）、`scene_id` NOT NULL REFERENCES `world_scene`、`segment_seq` NOT NULL、`body` NOT NULL、`language` NOT NULL、`outcome_ref` NULL（V3-6 起引用已 committed action outcome；Writer 只呈现）、`created_at_tick` NOT NULL（= 其 SEGMENT COMMIT 的 actual_end_tick）、双 stamp、`state_version` CHECK>0；**`UNIQUE (scene_id, segment_seq)`**（§26.2.4 幂等键——同 segment_key 重放 = no-op）。
- `reader_exposure`（读者暴露面，**与 SEGMENT COMMIT 解耦**——评审 #2 硬门的物理形）：`exposure_id` TEXT PK（派生 = `f"{passage_id}-x{reader_id}"`）、`passage_id` NOT NULL REFERENCES `narrative_passage`、`reader_id` NOT NULL（MVP = 本地用户词）、`exposed_at` NOT NULL（**ISO bookkeeping，不是 story time**）、双 stamp、`state_version` CHECK>0；**不在 NCP-3 原子组内**——passage commit ≠ 用户已看见；记录面 = 独立的 delivered/rendered 保守记录（MVP 显式调用，渲染 ack 后刀）；N-INV-005：不写 actor memory / belief（本刀无该表，曝光面 SQL 永不触之——扫描钉承重）。
- `segment_commit`（**#1 lineage 显式面**——V3 事件 story-time attribution 的权威读路）：`commit_id` TEXT PK（派生 = `f"sg:{scene_id}:{segment_seq:04d}"`）、`kind` NOT NULL CHECK `('SEGMENT')`（V3-6 增 `'ACTION_OUTCOME'` 词）、`scene_id` NOT NULL、`segment_seq` NOT NULL、`passage_id` NOT NULL REFERENCES `narrative_passage`、`actual_start_tick` NOT NULL、`actual_end_tick` NOT NULL、`event_id` NOT NULL REFERENCES `world_event`（本段沉淀的非用户事实行）、双 stamp、`state_version` CHECK>0；**`UNIQUE (scene_id, segment_seq)`**（与 passage 同幂等键族）。**V3 事件的叙事时间 = 经本表归属的 actual 区间**（`story_time_of(event_id)` 读路）——**禁止以 opaque event-id 命名规则反推**（评审 #1 硬门）；V3 cognition 不得把 legacy `occurred_at`（Legacy V2 ISO 语义）当世界时间（§26.2.2 同句）。
- **V3 事件的 `world_event.participants` 词表 = canonical identity**（`actor_id` ∪ `player_character_id`，participant_namespace 派生）；legacy 行（cast persona ids ∪ user id）**不回写、不同表混读**——区分靠本 lineage 面与读路过滤（V3-7 cognition 的职责），§26.2.3 的 V3-3R 注同义。

**V3-5R 落法（外审 2 HIGH + 1 MEDIUM-HIGH；开工裁决 `DEC-OPI-dc1bafdf-…11`，2026-10-12；migration `0034`）**：

- `segment_commit` 增列 `is_last_segment INTEGER NOT NULL DEFAULT 0 CHECK (is_last_segment IN (0,1))`（migration `0034_segment_terminality.sql`）——**terminality 的持久化形**：`is_last_segment=1` ⇔ 该段的 SEGMENT COMMIT 同事务翻转了场 `ACTIVE → COMMITTED`（SCENE COMMIT=别名）。回填律（迁移注释成文，只对 V3-5 管线产物为真）：`COMMITTED`/`CLOSED` 场的最大 `segment_seq` 行 = 1。replay 形状比对含该列——同一 `segment_key` 以不同 `is_last_segment` 重放 ⇒ 明确 `CONFLICT`（不静默返回旧结果）。**顺序律**：fresh segment 严格 `segment_seq == max(committed_seq) + 1`（首段必须 1；0 / 负数 / 跳号 / 倒序一律 `VALIDATION_FAILED`，消息点名 given 与 expected；replay arm 先行）。
- **场景 actual 区间 = NCP-3 的唯一写权**（STATE §26）：首个 committed segment 同事务写 `world_scene.actual_start_tick`；每个 segment 同事务推进 `world_scene.actual_end_tick`；末段同时 `ACTIVE → COMMITTED`——**一个 UPDATE 一次版本推进**（store 的无事务臂 `_advance_scene_actual_span_tx`），不得另起第三个 Scene Commit 事务；replay 零重改。
- **V3-5R 最小读路（§26.2.3 重写）**：V3 cognition read face（`elc/world/cognition.py`）——V3 event 判定走**显式 lineage**（`segment_commit.event_id` JOIN；legacy 事件无 lineage 行，不进 V3 读）；排序用 lineage actual 区间（`actual_start_tick, actual_end_tick, event_id`）；公共层 = `participants` 空、亲历层 = viewer ∈ participants（**canonical `actor_id` / `player_character_id` 直接过滤**——不得经 persona id 或 Package user-character mapping 判断 V3 亲历）。`ScenePlanner` 以当前 POV 的该读面作为 dossier/context 输入（`SceneContext` + `SceneOpening.context`）；legacy C1（`host.py` 世界端口）保持 legacy 读面不改写；V3-7 物化 actor memory/belief 后该面降为兼容/fallback。

**V3-3R identity/seed 冻结（外审，2026-10-12）**：

- **canonical participant identity**：AI-controlled durable character = `world_actor.actor_id`；user-controlled character = `world_player_character.player_character_id`。**`persona_id` 是 CharacterCard / template identity，不作为 Narrative V3 canonical world participant identity**（V3 链不做 actor↔persona 转换）。
- **residents**：package-only，**暂不具 durable V3 participant identity**（仍为 prose/scene 素材）；未来需长期被事件引用、拥有 memory 或升级 POV 时，另定显式 durable identity 方案。
- **seed 语义**：`world_player_character` 的 `name/background/appearance/abilities/limits` 属角色档案；**`location` / `state` / `knowledge_refs` 仅表示 creation-time seed**——当前 location/state 的权威在 `world_state_fact`，当前 knowledge/belief 的权威归 V3-7 actor memory/belief；**V3-4 Director 不得把 seed 字段当运行态当前事实**。
- **Legacy 不回写**：`world_event.participants`（Legacy V2：cast persona ids ∪ user id）语义不动、零回填——**V3-5 的 lineage / cognition read path 负责区分 Legacy 与 V3**。

**V3-4 Blueprint 严格 schema 与 scenes ↔ world_scene 对账规则（L3 落点，2026-10-12；开工裁决 `DEC-OPI-be7b094f-…7`；V3-4R 外审修正 `DEC-OPI-be7b094f-…21`）**：

- **Blueprint 严格 schema**（`world_chapter_plan` 行内容与 `scenes` JSON 的元素形状；`src/elc/world/director.py` 是机件化面）：章面字段照 §26.2.1 合同逐字（`goal` / `dramatic_question` / `planned_start_tick` / `planned_end_tick` / 软期望集 `closing_pressure` / `desired_development` / `soft_outcomes` / `chapter_questions_to_advance` / `scenes`）。**软期望集永远不是 postcondition**（设计篇 §2.2 措辞律——`closing_pressure` 表达「朝哪里压」，不表达「必须到达哪里」）；**硬条件只允许世界规则 / 已发生因果 / 不可撤销事实**——作者愿望（「必须成为朋友」类）不得把 Director 变成铁路调度（设计篇 §三 1.5）。**V3-4R 最小语义收紧**：`scenes` 非空；`planned_start_tick <= planned_end_tick`；scene 的 `planned_start_tick >= 0` 且不超过本章 `planned_end_tick`；**`pov_actor_id ∈ participants`**（POV 必须在场）。不扩成剧情合理性检测器。
- **`scenes[]` 元素的规范键集**（Blueprint 的场景草案，Plan 素材）：`purpose` / `place` / `pov_actor_id` / `participants` / `planned_start_tick` / `entry_goals` / `exit_condition` / `elasticity` / `revealable` / `must_hide`；可容的自由补充键（beats / gate 提示等）由 Director 自定义，schema 校验不拒。**identity 一律 canonical**：AI 侧 = `world_actor.actor_id`、user 侧 = `world_player_character.player_character_id`；`persona_id` 不入口径（V3-3R 冻结块，见上）。**POV eligibility 实权化（V3-4R 外审 #3）**：`pov_actor_id` 指向 AI actor 时其 `world_actor_profile.pov_eligible` 必须为 `True`——explicit `False` 拒为 POV；`None` = 未声明**不自动授权**（MVP 拒，消息人话）；`player_character_id` 为 POV **允许**（用户是自己故事的主角——世界观内天然 POV 候选）。
- **scene identity 与呈现顺序分离（V3-4R 外审 #1 HIGH）**：`scenes[]` 数组表达**呈现/计划顺序**，不承担持久身份。每个元素可带稳定身份键 **`scene_ref`**（可选；指向同章既有 `world_scene` anchor 的 `scene_index`，type=int 严格；重 `scene_ref` 拒、指向不存在 anchor 拒、指向他章 anchor 拒、与同位他锚冲突拒）；不带 `scene_ref` 的元素按数组序位指认同位置（`scene_index` = 序位）的既有 anchor。退休 anchor（`DISCARDED`）**永不复活、永不重铸、永远不被 `scene_ref` 指认**。**`scene_ref` 通道的现役语义（V3-4R 评审 F1 成文）**：`scene_ref` 是**与序位一致的对偶声明**通道（同位冲突律要求被接受的 ref 等于其自身序位）——它**不承担重排（换序）与中段 PLANNED 锚退休**；稀疏 durable identity 由 DISCARDED-skip + unused-monotonic 铸造表达。**放宽路径（登记给 V3-5/V3-6）**：若消费刀需要换序或中段退休，显式重开本条并把冲突律改为「该序位自有锚须被其他元素认领或被 discard」；在此之前，消费刀不得把 DISCARDED 锚当作可激活的计划场，也不得重编位次（V3-4 处置 F2 的消费刀禁令，同句回迁）。
- **identity stamping（受控一次性改写，append-only 的边界成文）**：Director 为元素创建 anchor 时，把派生 `scene_id` **烧入 plan 行 `scenes` JSON 的对应元素**（键名 `scene_id`；仅新增此一键、仅在该 anchor 创建时一次、在 adopt 落地前完成、其余内容字节不动）——这是 plan 行在其生命周期内唯一一次受控重写（`updated_at` 与 `state_version` 照常推进），此后任何 revision 不重写已烧身份。最新 ADOPTED revision 的 `scenes` JSON 因此**自然表示稀疏 durable identity**（rev3 = `[{scene_ref:1…}, {scene_ref:2…}, {新场…}]` → 新场配 unused monotonic `scene_index = max(既有)+1`，零幽灵/占位行）。
- **对账方向单向**：Director 采纳（ADOPT）一份 Blueprint revision 时按上述 identity 规则对账：**行是对账锚、JSON 是内容源**——内容权威永远在最新 ADOPTED plan revision 的 `scenes` JSON，`world_scene` 行只是 canon 面进度锚（状态字 + actual tick 列）。
- **派生律三条**（幂等与对账专用；叙事时间归属不靠 id 命名，§26.2.2 的 lineage 要求）：`chapter_id = f"{world_id}-ch{chapter_index:02d}"`、`plan_id = f"{chapter_id}-bp-r{plan_revision}"`、`scene_id = f"{chapter_id}-s{scene_index:02d}"`（chapter/scene 序位零填充两位、plan_revision 不填充）。
- **重规划 Diff 规则**（新 `plan_revision` 整体重述 `scenes[]`；STATE §24 append-only，旧 revision 保留为历史）：①`scene_ref` 指认的 anchor 留任（内容随新 JSON 走，行不动）；②无 `scene_ref` 且无同位 anchor 的新元素 → 配 **unused monotonic `scene_index`**（`max(既有 scene_index)+1`）新行 `PLANNED`；③未被新 revision 任何元素指认/同位的仍 `PLANNED` anchor → `discard_scene`（§22：仅 PLANNED 可达 DISCARDED）；④已 `ACTIVE` / `COMMITTED` / `CLOSED` 行**永不动**（N-INV-003——重规划对已发生无写权）；⑤`scene_index` 不复用（退休位次保留其锚，永不重铸、永不指认）。
- **重规划的章状态边界（V3-4 处置 F3）**：`revise_blueprint` 对 `SETTLING` / `CLOSED` 章拒 `VALIDATION_FAILED`——已定章无「剩余部分」可重规划（STATE §21 「CLOSED 不可 reopen；修正走后续章」/ §24 「只重规划剩余部分」）。
- **Director 全程不推进 `world.current_tick`**（#3 lifecycle tick authority：opened/closed tick 在正式管线取自 `world.current_tick` 且转移事务内校验；本刀 Director 只写 Plan 面与 `PLANNED` 行，tick 推进权只在提交事务，N-INV-007）。
- **World authority fail-closed（V3-4R 外审 #2）**：`world` 存在但无 `CURRENT` `world_bible_revision` ⇒ 禁止规划（`NOT_FOUND`，消息人话含 Bible）——无世界权威则无 Director。`DirectorContext` 必携带 **`current_tick`**（`world.current_tick` 的读数；Director 产生 planned ticks 时必须知道 canonical story time——初始 chapter planning 以 `current_tick` 为现实起点；replan 对已发生部分可保留历史 planned time，新规划不得无意识倒退 canonical time）。**Director cast 输入厚度（V3-4R 外审 #3 后半）**：AI cast 成员 = `actor_id` + `character_card` 人物信息（`name` / `identity` / `personality` / `background` / `speech_style` / `values` / `boundaries`——card 缺失或字段空则空串 honest undeclared，成员仍在）+ `world_actor_profile`；player 输入 = `player_character_id` / `name` / `background` / `appearance` / `abilities` / `limits`（`location` / `state` / `knowledge_refs` 继续结构级缺席——creation-time seed，V3-3R 冻结）。

### 26.2.2 时间字段（story_tick）

```text
Plan 面时间字段带 planned_ 前缀（planned_start_tick / planned_end_tick…）；
Canon 面时间一律 tick 语义、禁 ISO（字段名可为 actual_start_tick / actual_end_tick /
opened_at_tick / closed_at_tick / created_at_tick；共性 = 整数 tick、由提交事务写）
world.current_tick: 单调不减；由提交事务推进（§25 / STATE_MACHINES §26）
V3 事件行的叙事时间 = 其提交事务的 actual tick，经**显式 lineage 面**归属：
  提交记录表（commit_id / kind / passage_id|action_id / actual ticks / event ids，
  V3-5 落表）——**禁止以 opaque event-id 命名规则反推**（评审 #1，V3-5 硬门）；
  V3 cognition 不得把 legacy `occurred_at`（Legacy V2 ISO 语义）当世界时间
（不为 world_event 增 ISO / tick 列——读路经 lineage 连回）
```

### 26.2.3 V3-5 最小读路（不依赖 V3-7 表）

「下一场立即知道上一场」的保证不依赖 actor memory：

```text
1) 事实读：world_event（含 participants/effects）+ world_state_fact(CURRENT)（V3-3R 注：该列的 legacy 词汇 = persona ids ∪ user id；V3 canonical identity 见 §26.2.1 冻结——区分归 V3-5 lineage）
2) 认知读（V3-5R 落法，DEC-OPI-dc1bafdf-…11）：elc/world/cognition.py 的
   v3_cognition_view(conn, world_id, viewer_id) 纯读——
   · V3 event 判定走显式 lineage（segment_commit.event_id JOIN；legacy 事件绝不出现在 V3 读）
   · 排序用 lineage actual 区间（actual_start_tick, actual_end_tick, event_id）
   · 公共层 = participants 空；亲历层 = viewer ∈ participants
     （canonical actor_id / player_character_id 直接过滤——不得经 persona id
     或 Package user-character mapping 判断 V3 亲历）
   · ScenePlanner 以当前 POV 的该读面作为 dossier/context 输入（SceneContext）
   · legacy C1（host.py 世界端口：公共 ∪ 亲历 ∪ 用户层）保持 legacy 读面，不改写
V3-7 物化 actor memory/belief 后：commit 增加该臂；dossier 改读 actor memory；
本读面降为兼容/fallback（C1 同位）。
```

### 26.2.4 幂等与键

```text
UNIQUE(gate_id, submission_id)               # 用户提交去重（裁定只此一次）
UNIQUE(scene_id, segment_seq)                # 段落提交幂等（replay = no-op）
UNIQUE(chapter_id, plan_revision)            # Plan 版本单调
UNIQUE(scene_id, dossier_revision)           # Dossier 版本单调
UNIQUE(world_id, chapter_index)              # 章序单调
passage/event id 由 segment_key 派生          # 重放写同一批 id（§25；**id 派生只服务幂等重放——叙事时间归属不得依赖 id 命名**，见 §26.2.2 的 lineage 要求）
action 族 event/outcome id 由 action_commit_key 派生（与 segment_key 命名空间不相交；同一 lineage 纪律）
```

### 26.2.5 可重建投影（V3）

```text
chapter progress view（由 chapter/scene/segment 状态派生）
cognition view（V3-7 起可由 actor memory 重建；C1 读面为兼容兜底）
reader_exposure 未来可由 passage + render ack 重建（MVP 记录为准）
```



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
