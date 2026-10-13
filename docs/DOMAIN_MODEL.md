# DOMAIN_MODEL.md

> 状态：CANONICAL IMPLEMENTATION BASELINE V1  
> 目标：定义 V1 Clean Rewrite 的 Domain 边界、Authority、核心对象与跨域接口。

---

## 1. Domain Map

V1 区分 **core runtime domains** 与 **supporting bounded contexts**。

Core runtime domains：

```text
Conversation
Persona
Relationship
Learning
Curriculum
Teaching
Scheduler
Planner
Runtime / Platform
```

Supporting bounded contexts：

```text
Content Library
User Configuration / Profile
World / Lore
```

**Narrative V3（2026-10-12 范式转折；产品范式已冻结）**：`World / Lore` 升格为第一层 **Narrative（World）Domain**——叙事引擎（World Director / Scene Planner / POV Writer / User Gate / Action Resolver / Chapter Settlement）、实例级 World Bible、玩家角色与 actor 叙事档案、章/场/正文与两级提交事务均归其下（见 §20）。旧 World/Lore 面（`world_event` / `world_state_fact` / `world_storyline` 等真相层）继续复用；letter/run/reveal 旧链为 **legacy**（并行保留，不进 V3 authority 面）。

`Pedagogy Planner` 是 Application Service，横跨 Learning/Curriculum/Scheduler/Conversation/User Configuration，但不拥有这些 Domain 的 truth。

`Content Library` 拥有 canonical teaching resources；`User Configuration/Profile` 拥有长期目标、教学策略、用户资料与 disclosure policy；`World/Lore` 拥有场景/世界事实。

## 2. Authority Matrix

| 问题 | Authority |
|---|---|
| 用户实际说了什么 | Conversation |
| 用户行为是否形成 Learning Evidence | Learning |
| Learner State 如何派生 | Learning Estimator |
| 课程节点、前置关系、核心价值 | Curriculum |
| canonical teaching resource / readiness / provenance | Content Library |
| 什么时候到复习窗口 | Scheduler |
| 长期 GoalPortfolio / TeachingPolicy / SessionFocus | User Configuration/Profile |
| UserProfile / DisclosurePolicy | User Configuration/Profile |
| World/Lore canonical facts | World/Lore |
| 世界设定/规则/历法/历史背景（实例级） | World Bible（`world_bible_revision`；模板只 seed，见 §20.3-6） |
| 下一章发生什么（PLAN） | World Director（Blueprint） |
| 一场怎样展开（PLAN） | Scene Planner（Dossier） |
| 用户行为的真实 outcome | **Action Resolver（唯一权威）** |
| 何时必须停下问用户 | User Gate |
| 什么已经发生（CANON 落地） | **SEGMENT / ACTION OUTCOME COMMIT**（§20；Chapter Settlement 只压缩收束） |
| actor 知道/相信什么 | Actor Memory / Belief（V3-7 物化） |
| 读者看过什么 | Reader Exposure（记录面；不写 actor cognition） |
| 当前 session teaching/probe/cooldown budget | Teaching Policy + Runtime Session State |
| 当前最值得学什么 | Pedagogy Planner |
| 是否允许自动教学 | Teaching Gate |
| TeachingMoment 生命周期 | Teaching |
| 角色是谁、如何说 | Persona |
| Persona×User 关系记忆 | Relationship |
| 最终 provider prompt | Persona Runtime / PromptCompiler |
| turn sequencing / retry / recovery | Runtime Orchestrator |

## 3. Conversation Domain

### Owns

```text
Conversation
UserTurn
AssistantTurn
CanonicalTurnSlice
Episode source events
conversation sequence
```

### Does not own

```text
Learning mastery
Relationship memory truth
Teaching selection
Persona identity
```

### Key rule

Canonical transcript 表示系统确认的实际 conversation state；未 delivery 的 provider output 不进入 transcript。

---

## 4. Persona Domain

### Owns

```text
CharacterPackage
Character identity
personality
background
speech style
values
boundaries
opening/scenario
generation policy
lore references
```

### Persona Runtime consumes

```text
CharacterPackage
RelationshipView
EpisodeView
WorldLoreView
DisclosedUserProfile
ConversationWindow
LanguagePolicy
GenerationPolicy
EphemeralTeachingDirective?
GenerationContract
```

### Does not own

```text
Teaching target selection
Learner state
Relationship write
```

PromptCompiler 属于 Persona Runtime。

---

## 5. Relationship Domain

### Unit

```text
Persona × User
```

### Memory types

```text
USER_STATED_FACT
SHARED_EVENT
PERSONA_IMPRESSION
PROMISE
OPEN_THREAD
RUNNING_JOKE
RELATIONSHIP_EVENT
CONVERSATION_PREFERENCE
```

### Important distinction

```text
USER_STATED_FACT
SYSTEM_INFERRED_FACT
PERSONA_IMPRESSION
```

Persona subjective impression 不自动成为 Teaching Fact。

### Write flow

```text
Relationship Recorder proposal
→ Relationship Domain validate/dedupe
→ canonical Relationship Memory
```

Relationship projection failure 不回滚 conversation turn。

---

## 5.1 User Configuration / Profile Bounded Context

### Owns

```text
UserProfile
DisclosurePolicy
LearningGoalPortfolio
TeachingPolicyProfile
SessionFocus
```

### Rules

- Goal/Policy 是 versioned configuration，不是 Learning Evidence。
- `GlobalGoalPortfolio` 可被 `SessionFocus` 临时重加权，但不能静默修改长期目标。
- Persona Runtime 只能获得 `DisclosedUserProfile`，不能读取完整 UserProfile。
- TeachingPolicy 只改变“如何/多频繁教学”，不改 Learner State truth。

---

## 6. Learning Domain

### Source of truth

```text
EvidenceGroup
EvidenceClaim
LearningOpportunityRecord
LearnerSelfReport
```

Learner State 是 materialized projection。

### Learning Evidence kernel

一个用户行为：

```text
EvidenceGroup
```

可以包含多个：

```text
EvidenceClaim
```

每个 claim 独立指向：

```text
RESOURCE
CAPABILITY
```

并拥有自己的 outcome/confidence/support。

### Primary performance types

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

Delayed/transfer 不是额外独立 success。

### Negative evidence rule

只有：

```text
genuine Opportunity
or attempted use
```

才能形成 target-specific negative evidence。

### Learner State

基础作用域：

```text
Target × EvidenceModality
```

核心维度：

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

每个维度拥有：

```text
estimate?
confidence
```

UNKNOWN 通过 `estimate = null` 表达，不是 0。

### State is rebuildable

Evidence append-only；State 带：

```text
estimator_version
evidence_watermark
```

可重算。

---


## 6.1 Learner State Estimator — Behavioral Baseline V1

Estimator 是 deterministic、model-free projection：

```text
ACTIVE Evidence
→ normalized EstimatorClaimView
→ EvidenceGroup dedup
→ EvidenceCluster diminishing returns
→ positive/negative effective mass
→ base dimensions
→ confidence
→ derived transfer/support_dependency
→ projection bands/learning flags
```

基础维度：

```text
recognition
guided_production
independent_production
spontaneous_production
accuracy
pragmatic_control
```

二次派生：

```text
transfer
support_dependency
```

Normative：positive stronger behavior 可弱向下支持；negative 不对称向下传播；PARTIAL 是 mixed evidence；FULL exposure 不能生成当前 Moment 的 independent evidence；同 EvidenceGroup 去重；同 cluster 衰减；UNKNOWN 由 evidence mass gate 表达；SelfReport/ExpressionNeed 不进入 ability mass。

Resource 与 Capability 分开估计；Capability transfer 额外要求 realization diversity。数值 profile 可校准，但 topology、单调方向、UNKNOWN/authority 语义冻结。

## 7. Curriculum Domain

### Owns

```text
Curriculum Graph
Capability registry
prerequisites
core tier
curriculum links
goal/assessment mappings
```

### Canonical capability families

V2.1 当前 14 families / 89 Level-2 capabilities：

```text
REF
NAR
EXPL
EVAL
STANCE
PLAN
NORM
AFFECT
SOCIAL
INFO
INTERACT
DISC
MEDIATE
STYLE
```

### Edges

```text
DECOMPOSES_INTO
REALIZED_BY
SUPPORTS
PREREQUISITE_FOR
REFINES
ALTERNATIVE_TO
CONTRASTS_WITH
REGISTER_VARIANT_OF
COMMONLY_CONFUSED_WITH
GENERALIZES_TO
ELICITABLE_IN
```

Prerequisite strength：

```text
HARD
SOFT
SCAFFOLDABLE
```

Hard prerequisite subgraph 应保持 DAG。

---

## 8. Content Domain / Library

Canonical content types：

```text
LEXICAL_ENTRY
FORM
SENSE
EXPRESSION
CONSTRUCTION
EXAMPLE
```

Expression subtypes：

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

重要关系：

```text
CurriculumLink
ContentRelation
AssessmentMembership
TypicalError
PedagogicalProfile
ResourceLabel
Assertion / SourceSnapshot / ContentSource
```

### Content Readiness（Normative）

```text
R0 INDEXED
R1 LEXICALLY_RESOLVED
R2 PLANNER_READY
R3 TEACHING_READY
R4 DETECTION_READY
```

- R0：来源/assessment membership/canonical form 已索引；
- R1：POS/sense/basic definition/forms 可追溯；
- R2：具备 CurriculumLink、PedagogicalProfile、goal/pack/register/usage-modality/context 等 Planner 信息；
- R3：具备 reviewed explanation/note、example policy、必要 contrast/usage/TypicalError；
- R4：具备 detection policy、recognition/negative fixtures、false-positive boundary，可用于 automatic error-triggered teaching。

V1 中，未经 R4 或正式结构化 detector certification 的 target，不进入 automatic error-triggered path。

Runtime 使用 `TeachingUnit` aggregate DTO，不使用 canonical mega-table。

---

## 9. Scheduler Domain

### Owns

```text
review_state
review_urgency
next_review_window
spacing_stage
```

### Reads

```text
Learning freshness
last strong retrieval
stability evidence
teaching/review history
```

### Does not own

```text
ability judgment
target priority
```

Learning 不能直接输出 `REVIEW_DUE`；Scheduler 才决定 due/overdue。

---

## 10. Pedagogy Planner

### Input authorities

```text
LearningSnapshot
CurriculumCandidateView
ScheduleView
GoalView
TeachingPolicyView
ContextOpportunitySet
PlannerConstraintView
SessionBudgetView
UserIntentScope
ConversationPriorityView
PlanningLedger
```

### SessionBudgetView Authority

`SessionBudgetView` 由：

```text
TeachingPolicyProfile
+
Runtime Session State
```

共同派生，至少包含：

```text
automatic_teaching_used / remaining
probe_budget
cooldown
recent_skips/rejections
fatigue_signal
```

它是 Planner input，不是 Learning State。

### Output

Planner 分成两层结果：

```text
PlannerEvaluation
  ranked TargetCandidateSet
  factor/reason trace

PlannerDecision
  SELECT(selected_candidate_id)
  or NO_TARGET
```

`Planner failure/unavailable` 不伪装成 `PlannerDecision`；它由 Runtime 的 `PlannerExecutionStatus` 表达。

### Does not own

```text
Learning State
Teaching authorization
final teaching text
Persona prompt
```

### Opportunity Type Boundary

`ContextOpportunity` 与 Learning 的 `LearningOpportunityRecord` 是不同类型：

```text
ContextOpportunity
→ Planner/Observer 视角：当前有没有可利用的教学机会。

LearningOpportunityRecord
→ Learning provenance：是否存在足以支持某条 Evidence，尤其 negative Evidence 的真实尝试机会。
```

二者可以通过 source turn / teaching moment 关联，但不能共用 canonical truth。

### ActiveLearningFrontier

动态计算：

```text
curriculum candidates
∪ scheduled review
∪ confirmed gaps
∪ unknown probes
∪ transfer opportunities
∪ personal expression needs
∪ current context opportunities
```

经过 eligibility/prerequisite/content readiness/user constraints/cognitive feasibility 后形成 Frontier。

---


## 10.1 Planner Decision Kernel — Behavioral Baseline V1

Planner 固定决策顺序：

```text
CandidateProposal canonicalize
→ authoritative feature assembly
→ planning-context validity
→ hard eligibility
→ policy utility
→ coverage-starvation safeguard
→ per-candidate activation
→ explicit-request priority
→ Pareto prune
→ near-tie deterministic tie-break
→ SELECT / NO_TARGET
```

Benefit factors 包括：`learning_need / uncertainty_reduction / curriculum_value / goal_relevance / schedule_urgency / context_fit / personal_relevance / transfer_value / coverage_debt / opportunity_expiry / communicative_impact`。

Cost factors：`interruption_cost / cognitive_load / overexposure / support_cost / user_resistance`。

Hard exclusion 不是 penalty；缺失 authoritative view 或 invalid snapshot 进入 `PlannerExecutionStatus=DEGRADED/FAILED/UNAVAILABLE`，不得伪造 `NO_TARGET`。

显式 user learning request 通过 scope/readiness/prerequisite 后不使用 automatic interruption threshold；多重显式请求用 `request_priority` 约束。Origin labels 不能重复加 utility。

## 11. Planner Candidate Model

### Initiative class

```text
REACTIVE
OPPORTUNISTIC
PROACTIVE
```

### Target mode

```text
RESOURCE_PRACTICE
CAPABILITY_PRACTICE
PROBE
REVIEW
TRANSFER
```

### Learning intent

```text
ESTABLISH
DEVELOP
WITHDRAW_SUPPORT
CONSOLIDATE
PROBE
TRANSFER
EXPAND_REPERTOIRE
```

### Benefit factors

```text
learning_need
uncertainty_reduction
curriculum_value
goal_relevance
schedule_urgency
context_fit
personal_relevance
transfer_value
coverage_debt
opportunity_expiry
```

### Cost factors

```text
interruption_cost
cognitive_load
overexposure
support_cost
user_resistance
```

冻结 factor semantics，不冻结权重。

---

## 12. UserIntentScope

```text
OPEN
LEARNING_REQUEST
TARGETED_LEARNING_REQUEST
JUST_CHAT
NON_LEARNING_TASK
ACTIVE_TEACHING_CONTINUATION
```

`TARGETED_LEARNING_REQUEST` 是 candidate-scope constraint，不是普通 bonus。

---

## 13. ConversationPriorityView

```text
flow_priority:
  LOW
  NORMAL
  HIGH
  PROTECTED

interaction_phase:
  OPEN
  DEEP_EXCHANGE
  TASK_EXECUTION
  STORY_FLOW
  USER_SUPPORT
  TEACHING
  WRAP_UP

natural_break_available
```

它用于表达当前对话保护级别；Gate 保留最终授权权威。

---

## 14. Teaching Domain

### Owns

```text
TeachingMoment
AttemptRecord
AttemptEvaluationRecord
PresentationAction
TeachingResponseEnvelope
TeachingLockLease
Teaching lifecycle
```

### Teaching Gate

执行教学动作的唯一 Gate authority；Planner 只判断 worth teaching，Gate 只判断 may execute now。

Decision contexts：

```text
OPEN
AUTO_CONTINUE
USER_REQUESTED_CONTINUE
```

### Teaching Planner

把 TargetCandidate 变成：

```text
EphemeralTeachingDirective
```

但不创建 persona prompt。

---

## 15. TeachingMoment Core

单一 FocusTarget；支持：

```text
hint
retry
reveal
explanation
skip
reject
topic shift
explicit target switch
```

v1 不支持长期 suspended zombie moment。

完整答案曝光后，当前 Moment 后续不再产生 independent evidence。

---

## 16. Runtime / Platform

### Conversation Orchestrator

owns sequencing, not truth。

可以：

```text
assign turn/sequence
resolve runtime state
call domain commands
advance turn coordination
handle retry/recovery
emit trace
```

不能直接更新 Domain-owned canonical state。

### Runtime-specific records

```text
TurnRecord
DecisionCycle
AnalysisArtifact
GenerationActionIntent
ProviderAttempt
ServerDeliveryRecord
ClientRenderAck
ExposureEstimate
ConversationCoordinatorLease  # logical coordination contract
runtime_epoch                 # Local V1 restart fencing metadata
ProjectionJob
```

---

## 17. Memory Separation

```text
User Profile
Learning Memory
CharacterPackage
Relationship Memory
Episode Memory
World/Lore
Retrieval Index
```

Learning 可跨 Persona 汇总；Relationship 不跨 Persona 泄漏。

---

## 18. Proposal-only Components

以下默认 proposal-only：

```text
Teaching Observer
Learning Evaluator
Relationship Recorder
model-assisted response interpretation
model-assisted validators
```

Domain Controller 决定：

```text
VALIDATE
COMMIT
REJECT
ABSTAIN
```

推理调用可以物理合并，但 Authority 不合并。

---


## 18.1 Trust / Privacy Authority

```text
UNTRUSTED_CONTENT:
  user free text
  Persona card / Lore
  provider/model output
  retrieved memory text

MODEL_PROPOSAL:
  semantic/evidence/profile/relationship proposals

TRUSTED_AUTHORITY:
  typed user settings
  validated Domain commands
  system policy
```

Untrusted content 不能自行获得 UserProfile、Relationship、Learning 或 Runtime canonical write authority。

高敏感 Profile/Relationship persistence 需要显式用户许可；模型不得把推断的高敏感属性直接提交为长期事实。

Provider disclosure 由 action-specific minimal view 产生；Relationship 不跨 Persona，Learning truth 不自动写入 Relationship。

## 19. Domain Invariants

```text
D-INV-001 Orchestrator 不直接改 Domain truth。
D-INV-002 Persona Runtime 不创建 TeachingDirective。
D-INV-003 TeachingDirective 不进入 Relationship Memory。
D-INV-004 Planner 不写 Learner State。
D-INV-005 Relationship Memory 不直接影响 mastery。
D-INV-006 CurriculumLink 不是 EvidenceProjectionRule。
D-INV-007 Resource mastery 不自动等于 Capability mastery。
D-INV-008 Capability success 可以不命中 canonical Resource。
D-INV-009 Scheduler 决定 review due；Learning 只提供 freshness。
D-INV-010 Planner 决定 transfer need；Learning 只提供 transfer evidence。
D-INV-011 Relationship / Episode / RetrievalIndex 均为投影或独立域，不拥有 transcript truth。
D-INV-012 final provider prompt 只能由 Persona Runtime / PromptCompiler 构建。
```

---

## 20. Narrative V3 Domain（World 第一层；V3-1 实现合同）

> 依据：`docs/design/2026-10-12-narrative-v3-paradigm-shift.md`（v3.1 / V3-0R，产品范式与高层架构已冻结）。本节是 V3-1 的 domain 合同：authority、边界与不变量在此冻结；migration 与代码不得反向改写本节（design-first）。

### 20.1 Domain Map

```text
Narrative (World) Domain
  World Bible      —— 实例级世界权威（world_bible_revision）
  Cast             —— world_actor（复用）+ world_actor_profile + world_player_character
  Planning         —— World Director + Chapter Blueprint + Scene Dossier（PLAN 面）
  Writing          —— POV Writer → narrative_passage（CANON 面·正文）
  Interaction      —— User Gate + Action Resolver → user_action
  Commit           —— SEGMENT COMMIT / ACTION OUTCOME COMMIT（唯一落地边界）
  Memory           —— world_event / world_state_fact / world_storyline（复用）
                      + actor memory / belief + chapter summary（Narrative Memory）
  Exposure         —— reader_exposure（记录面；≠ actor cognition）
```

### 20.2 Authority 明细

| 问题 | Authority |
|---|---|
| 世界设定 / 规则 / 历法 / 历史背景（实例级） | World Bible（`world_bible_revision`；`world_id` 归属） |
| 下一章发生什么（PLAN） | World Director（产出 Blueprint；不写正文、不写 canon） |
| 一场具体怎样展开（PLAN） | Scene Planner（Dossier；对 Blueprint 的即时再规划） |
| 用户行为的真实 outcome | **Action Resolver（唯一权威）** |
| 何时必须停下问用户 | User Gate |
| 正文怎么写（文学化呈现） | POV Writer（只呈现已成立结果） |
| 随后新产生的非用户事实 | POV Writer（经规划与规则允许；进入 segment commit 才会成真） |
| 什么已经发生（CANON 落地） | **SEGMENT COMMIT / ACTION OUTCOME COMMIT** |
| 章末整理（压缩 / 收束） | Chapter Settlement（**不负责第一次落地**） |
| 每个 actor 知道 / 相信 / 误解什么 | Actor Memory / Belief（有视角；V3-7 物化） |
| 读者看过什么 | Reader Exposure（记录面；**不写 actor cognition**） |
| 世界当前时刻（actual） | commit 事务（唯一推进者）；Director/Scene 只写 planned |
| 管线驱动顺序（谁在何时调用谁） | **编排器**（`elc/world/pipeline.py`；**零写权**——一切写入由被编排的库面在自己的短事务内落；RA §27 编排面，V3-8a 落法） |
| Writer 正文 / Planner（SCENE 级）dossier 内容的**生产面** | provider 协议面（`elc/world/providers.py` 的 Protocol + deterministic fake；真实 LLM 接线是「好玩」亲验前的显式一步，V3-8a 落法） |
| **CHAPTER 级 Blueprint（初次规划与 CHAPTER replan）的生产面** | **World Director / DirectorProvider**（输入基于 `DirectorContext` 全知面——Bible/current facts/full cast/active storylines/chapter settlements/current_tick + 触发本 replan 的 action/reason；`Director.apply_action_replan` 仍负责 validation/persistence，但 Blueprint 的**生产权**不由 POV-limited PlannerProvider 代替——V3-8b 外审 HIGH-3 重冻结） |
| **Resolver 裁定的权威输入** | **world-authoritative `ResolverContext`**（CURRENT World Bible/hard rules + relevant `world_state_fact` + player profile〔abilities/limits〕+ 当前 location/physical state + inventory/resource state + scene/environment canonical facts + relevant counterpart state；**玩家角色自身的 `v3_cognition_view`/`v3_memory_view` 读面（`viewer = player_character_id`，随 `player_cognition`/`player_memory` 并载）用于判断「用户角色知道什么」**；场景 POV 的 cognition/memory 作为**叙述面**随 `pov_actor_id` 并载，不作为「用户知道什么」的判据（V3-8c F4 裁定）；两者都不是 Resolver 自身的知识上限；Resolver 不替用户发明 intent——V3-8b 外审 HIGH-2 重冻结 + V3-8c F4 精确化） |
| 世界 + 初始 Bible 的原子创建 | 原子创建服务（`create_world_with_bible`；一个短事务全或无；V3-8a 落法） |

### 20.3 七条硬边界（V3-1 冻结）

1. **Resolver 唯一裁定权**：ACTION OUTCOME COMMIT 之后，POV Writer 只能文学化呈现该已成立结果（passage 引用 outcome）；**不得**重复裁定或重复写入同一 event/effects。Writer 只拥有随后新产生的非用户事实。
2. **V3-5 最小 commit 不依赖 V3-7 表**：V3-5 的 SEGMENT COMMIT 落地面 = `narrative_passage` + `world_event`（participants / effects）+ `world_state_fact` + `story_tick` 推进；「下一场立即知道上一场」由 `world_event.participants` + 现役 **C1 cognition view**（host 世界端口）保证。V3-7 物化 actor memory / belief 后接入 commit 与 dossier，C1 读面降为兼容层。
3. **两级提交的原子组 / 幂等键 / crash-retry-recovery 语义**：见 `DATA_MODEL.md §26.2` 与 `RUNTIME_ARCHITECTURE.md §28`（同一合同的三张脸）。
4. **合法生命周期**：Chapter / Scene / User Gate / Plan Revision 状态机见 `STATE_MACHINES.md §21–§24`。
5. **story_tick**：MVP 粒度 1 tick = 1 分钟（World Calendar 解释显示）；actual ticks 推进权只在提交事务；planned ticks 写权在 Director（Blueprint）/ Scene Planner（Dossier）。见 `STATE_MACHINES.md §26`。
6. **模板 ≠ 实例 Bible**：世界模板 / 包只在**创建时 seed**；实例的 `world_bible_revision` 是唯一权威；**模板后续更新不得自动改写已存在世界**（更新须显式 fork / migrate 决策——V3-2 按此预留）。
7. **Reader Exposure 本轮只冻结本体与引用边界**：`reader_exposure` 引用 `narrative_passage`；不写 actor memory；不做 metagame 机制。

### 20.4 Narrative Invariants

```text
N-INV-001 未 commit 的 Plan 内容不得作为 canon 事实被读取。
N-INV-002 同一用户行为只有一份权威 outcome（Resolver 产出）；Writer 不得再裁定。
N-INV-003 已提交的 passage / event / state / memory 不可改写（append-only；修正以后续事件到达）。
N-INV-004 Chapter Settlement 不产生新事实（只压缩 / 收束已 commit 的内容）。
N-INV-005 reader_exposure 不写入 actor memory / belief。
N-INV-006 实例 Bible 权威在 world_bible_revision；模板不拥有已存在世界的改写权。
N-INV-007 actual story_tick 只由提交事务推进，且单调不减。
N-INV-008 旧 Narrative V2 链（world_run / reveal / letter 触发）为 legacy，不进入 V3 authority 面。
```
