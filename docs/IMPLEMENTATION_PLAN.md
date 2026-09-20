# IMPLEMENTATION_PLAN.md

> 状态：CANONICAL IMPLEMENTATION BASELINE V1  
> 目标：把当前架构转化为 Clean Rewrite 的可执行开发顺序。  
> 原则：先打通最小真实 vertical slice，再逐步引入自动教学；不先做大规模内容生产。

---

## 1. Clean Rewrite Rules

### 1.1 New canonical implementation space

推荐：

```text
new repository
or
orphan clean branch
```

旧 repo/branch 保留为：

```text
exploration archive / historical evidence
```

不作为代码基底。

### 1.2 Migration whitelist

迁移：

```text
confirmed product decisions
research/evidence
content schema/toolchain
validated content seed
design references
```

不迁移：

```text
old implementation defaults
old source-of-truth assumptions
old tests as release evidence
contradictory teaching state logic
```

### 1.3 Canonical docs before code

新仓库根目录先放：

```text
PRODUCT_CONTRACT.md
DOMAIN_MODEL.md
STATE_MACHINES.md
DATA_MODEL.md
RUNTIME_ARCHITECTURE.md
IMPLEMENTATION_PLAN.md
```

实现 PR 必须能指出自己遵循/修改哪一条 contract。

---


## 1.5 Post-BF V1 Execution Order — Normative

外部评审后的 Behavioral Freeze 已完成；以下顺序**取代 RC2 中“Relationship 早于 Learning vertical slice”的优先级解释**。旧 phase 章节仍提供详细任务清单，但执行依赖按本节排序。

```text
Phase 0  Repository Bootstrap + Local Runtime foundations
Phase 1  Conversation + Persona buffered minimum runtime
Phase 2  Learning Evidence Kernel + Estimator Behavioral Baseline V1
Phase 3  User-initiated TeachingMoment vertical slice
Phase 4  Relationship + Episode projection
Phase 5  Curriculum + Content runtime integration
Phase 6  Goal Portfolio + Scheduler views
Phase 7  Planner shadow mode + Planner Behavioral Baseline V1
Phase 8  Teaching Gate + automatic teaching rollout
Phase 9  Delivery/Exposure hardening + guarded streaming/barge-in
Phase 10 Recovery hardening
Phase 11 Content calibration resume / broader production
```

第一条必须验证的学习 vertical slice：

```text
Basic Persona Conversation
→ canonical Performance Evidence
→ Estimator LearnerState
→ explicit user TeachingMoment
→ user attempt
→ new Evidence
→ updated LearnerState
```

只需要少量（约 10–20）validated targets 即可开始，不等待完整 Relationship、自动教学或百条内容生产。

## 2. Phase 0 — Repository Bootstrap

目标：建立不会继续架构漂移的工程骨架。

### Deliverables

```text
/docs canonical six documents
/src domain folders
/tests architecture tests
/migrations
/content link or package
/runtime trace schema
```

建议模块：

```text
conversation/
persona/
relationship/
learning/
curriculum/
scheduler/
planner/
teaching/
runtime/
content/
platform/
```

### Gate

- 每个 Domain 有 own command/query interfaces。
- Orchestrator 无 direct DB table mutation。
- PromptCompiler 仅存在 Persona Runtime。
- canonical IDs / version fields 统一。
- Goal/Policy/Profile/Scheduler/Gate/Validator/Projection 等 canonical object 均有 owner/schema。
- `PlannerDecision(NO_TARGET)` 与 `PlannerExecutionStatus(DEGRADED/FAILED/UNAVAILABLE)` 完全分离。
- `turn_sequence` 与 `message_sequence` 有独立测试。

---

## 3. Phase 1 — Conversation + Persona Minimum Runtime

先不做自动教学。

目标：

```text
UserTurn durable
→ Persona Runtime
→ Validator
→ Delivery
→ AssistantTurn
```

### Implement

- InputEnvelope dedupe
- ConversationCoordinatorLease logical interface; Local V1 = keyed async mutex + runtime_epoch
- ConversationInputQueue / InterruptRequest
- explicit turn_sequence + message_sequence
- TurnRecord
- UserTurn / AssistantTurn
- GenerationActionIntent / ProviderAttempt
- Persona Runtime
- GenerationContext
- PromptCompiler
- basic GenerationContract
- app.db migrations / transaction helpers / runtime_epoch startup recovery
- durable active_teaching_lock / projection_job
- BUFFERED_VALIDATED reply first
- Response Validator minimum deterministic rules
- action-level retry
- canonical transcript

### Acceptance

测试：

```text
duplicate input
provider no-output
provider retry
late callback
crash after user commit
assistant partial/failure terminalization
```

此阶段必须已经不需要“retry whole turn”。

---

## 4. Detail Block — Relationship + Episode Projection（Post-BF Phase 4）

目标：

```text
自然角色连续性
```

### Implement

- RelationshipView
- Relationship Recorder proposal
- Relationship Domain validate/dedupe
- Episode projection
- UserProfile disclosure
- post-turn projection queue/action log
- projection retry with version-aware revalidation

### Acceptance

- 未 delivery assistant output 不进入 Relationship。
- Relationship failure 不影响 transcript。
- Persona A 关系记忆不能泄漏给 Persona B。
- current user turn 即使 Relationship projection 未完成，Persona 下一轮仍可通过 transcript 连贯回答。

---

## 5. Detail Block — Learning Evidence Kernel（Post-BF Phase 2）

仍不自动教学。

目标：

```text
silent observation
→ evidence
→ learner state
```

### Implement

- AnalysisArtifact
- EvidenceGroup / EvidenceClaim
- LearningOpportunityRecord
- LearnerSelfReport
- ExpressionNeed
- Evidence idempotency
- Evidence invalidation/supersede
- deterministic Evidence-Mass Estimator v1
- Target × Modality LearnerTargetState
- LearningSnapshot
- exposure_estimate_id / support attribution certainty provenance
- late ACK does not silently upgrade committed Evidence

### Initial estimator

只实现：

```text
factor mapping
effective evidence mass
correlation/diminishing returns
ability/confidence separation
freshness
diversity
```

不要追求最优 numeric calibration。

### Acceptance

复现 OQ-022A / 022B 场景：

```text
immediate imitation
spontaneous first use
delayed use
cross-persona use
alternative realization
resource fail + circumlocution success
Chinese fallback
multi-capability utterance
typo vs systematic error
self-report
```

---

## 6. Detail Block — Curriculum + Content Integration（Post-BF Phase 5）

目标：让 Learning target 与真实 content/curriculum 可定位。

### Reuse existing validated tooling

来源：

```text
OQ-021A-100_content_toolchain
```

当前基础：

```text
28 canonical resources
47/89 capabilities touched
14/14 families
toolchain 13/13 PASS
```

先迁移工具链与 seed，不继续盲目扩到100。

### Implement

- curriculum registry loader
- content.db runtime reader
- CurriculumCandidateView
- Content readiness R0–R4
- ContentResourceView
- stable resource identity
- Personal Content origin separation

### Acceptance

- unknown capability ID rejected
- candidate content excluded
- stable IDs rebuild stable
- R4 fixtures enforced
- canonical/personal origin preserved

---

## 7. Detail Block — Scheduler + Goal Portfolio（Post-BF Phase 6）

目标：提供 Planner 所需长期 views。

### Implement

- canonical/versioned UserProfile + DisclosurePolicy
- canonical/versioned LearningGoalPortfolio
- canonical/versioned TeachingPolicyProfile
- SessionFocus
- ScheduleItem / ReviewEvent / ScheduleView
- review state/urgency
- spacing history
- PlannerConstraint / suppression scope
- Goal/Assessment pack mapping

### Important

```text
Learning freshness != review_due
```

Scheduler 根据 Learning + history 决定 due。

---

## 8. Detail Block — Planner / ActiveLearningFrontier（Post-BF Phase 7）

先只输出 trace，不真正自动教学。

### Implement

- Track A candidate generators
- Track B candidate generators
- UserIntentScope
- ConversationPriorityView
- candidate canonicalization
- prerequisite resolver
- content readiness gate
- ActiveLearningFrontier
- PlanningLedger
- CoverageDebt
- overexposure
- Hard Rules + Policy Utility
- activation threshold
- deterministic tie-break
- NO_TARGET
- PlannerEvaluation + PlannerDecision
- PlannerExecutionStatus / RuntimeDecisionOutcome
- PlannerTrace

### Shadow mode

先运行：

```text
Planner decides
but UI does not auto-teach
```

记录：

```text
what would have been selected
why
```

人工/测试审查。

### Acceptance

复现 OQ-023A 12+ conflict cases。

---

## 9. Detail Block — Teaching Gate + TeachingMoment（user-initiated Phase 3 / automatic Phase 8）

打开 user-initiated teaching first。

### 7.1 User-initiated path

实现：

- TeachingMoment lifecycle
- TeachingResponseEnvelope
- AttemptRecord
- AttemptEvaluationRecord
- TeachingLockLease
- hint/reveal
- skip/reject/topic shift
- explicit switch target
- TEACHING_TERMINAL
- PersonaResumeDirective
- EvidenceGoal
- continuation gate
- soft/hard turn limits

### 7.2 Automatic teaching later

当 user-initiated path 稳定后：

```text
Planner SELECT
→ Gate OPEN
→ automatic TeachingMoment
```

默认先在 Balanced/Study-first 开。

Lounge 自动教学最后开启。

### Acceptance

复现 OQ-024A 16+ state cases。

---

## 10. Detail Block — Delivery / Exposure Hardening（Post-BF Phase 9）

### Implement

- BUFFERED_VALIDATED teaching actions
- GUARDED_STREAM normal chat
- ServerDeliveryRecord
- ClientRenderAck as asynchronous refinement
- ExposureEstimate initial + refined certainty
- no-wait-ACK turn terminalization
- PreDeliveryGuard
- partial stream canonicalization
- barge-in
- cancelled/superseded late callback ignore
- state_version/CAS

### Acceptance

- partial reveal 不被记为 full exposure
- no ACK 使用 conservative support
- barge-in 旧 tail 不进入 transcript
- late provider result 无副作用

---

## 11. Detail Block — Runtime Recovery（Post-BF Phase 10）

### Implement

Recovery worker 扫：

```text
non-terminal TurnRecord
GenerationActionIntent
TeachingMoment
TeachingLockLease
ConversationCoordinatorLease
pending AnalysisArtifact
pending projections
```

### Recovery rules

```text
CP0 crash → analysis
CP1 crash → DecisionCycle
CP2 crash → same action
CP3 uncertainty → no blind replay
terminal teaching + resume fail → no reopen
```

### Acceptance

复现 OQ-025A 25类 runtime failure scenario。

---

## 12. Detail Block — Automatic Teaching Rollout（Post-BF Phase 8 late stage）

建议顺序：

```text
manual/user-initiated
→ Study-first
→ Balanced
→ Lounge
```

每阶段先小流量/本地 dogfood。

观察：

```text
unwanted interruption
skip/reject
continuation
NO_TARGET appropriateness
overexposure
Evidence gain
```

如果 unwanted interruption 高：

```text
提高 threshold / policy cost
```

而不是修改 Learning truth。

---

## 13. Detail Block — Content Calibration Resume（Post-BF Phase 11）

只有 Runtime 主链稳定后才恢复：

```text
28 → 100 resource calibration
```

优先使用内容填补真实运行时测试需要，而不是为了数量。

未通过的 Calibration100 gates 当前包括：

```text
resource_count >= 100
CORE_A >= 30
CORE_C >= 2
```

其它结构 breadth gate 已有较好基础。

---


## 13.1 Behavioral Baseline Assets — Must Ship With Repository

新仓库必须带入并自动回归：

```text
Estimator Behavioral Baseline V1
Planner Behavioral Baseline V1
Teaching Gate Behavioral Baseline V1.1 authorization semantics
Golden Scenario Baseline V1
Security/Privacy/Deletion Contract Baseline V1
Modality Scope Baseline V1
Local Runtime Baseline V1
```

不得把它们降级为“设计参考”。它们是 architecture tests / golden fixtures 的实现合同。

关键实现规则：

- `Target × EvidenceModality`；V1 first slice 使用 `TEXT_PRODUCTION`。
- `TEXT_COMPREHENSION` 只在 explicit comprehension opportunity 中产生。
- `SPEAKING/LISTENING` direct obligation 在无 voice/audio runtime 时暂停，不累计 impossible CoverageDebt。
- Estimator deterministic、无 LLM、可 rebuild；参数版本化。
- Planner hard eligibility → utility → activation → request priority → Pareto → tie-break。
- Gate 不 re-rank pedagogy；OPEN 用 DecisionCycle authorization，continuation 用 ActiveMoment authorization。
- Security: secret-by-reference、minimal disclosure、provenance-aware deletion。
- Local runtime: one process + app.db + content.db + SecretStore；不引入 Redis/Kafka/distributed leases。

## 14. Testing Strategy

### Architecture tests

检查：

```text
Orchestrator cannot directly mutate domain stores
PromptCompiler only Persona Runtime
Planner cannot write Learning State
Gate only auto-teaching authority
Relationship isolation across persona
```

### State-machine tests

Teaching transitions table + invalid transition tests。

### Determinism tests

相同：

```text
snapshot
policy
candidate set
```

产生相同 Planner selection/tie-break。

### Property tests

```text
duplicate input does not duplicate UserTurn
duplicate evaluator retry does not duplicate Evidence
duplicate provider callback does not duplicate AssistantTurn
Planner failure never creates synthetic NO_TARGET
late ClientRenderAck does not silently upgrade Evidence
CP4 projection delay does not block next turn
ContextOpportunity cannot satisfy Learning negative-evidence opportunity
no-output turn still terminalizes and projects
CLOSED TeachingMoment never reopens
```

### Failure injection

每个 CP 前后 crash。

### Golden scenarios

把 OQ-022A / 023A / 024A / 025A 变成 executable scenario fixtures。

---

## 15. Observability

每 turn trace：

```text
turn_id
user_turn_id
analysis ids
evidence ids
decision_cycle
planner/gate
teaching moment/action
provider attempts
validator
delivery/exposure
assistant turn
projections
```

前端/开发工具应能查看：

```text
Why did the system teach?
Why did it not teach?
What evidence changed?
What support was visible?
Why was a turn degraded?
```

---

## 16. Definition of Done — V1 Runtime

V1 Clean Rewrite 主链完成必须满足：

```text
1. 自然 persona chat 可独立工作。
2. Learning failure 不拖垮聊天。
3. current-user Evidence 可进入 Planner。
4. UNKNOWN 不被当 gap。
5. Planner 可合法 NO_TARGET。
6. Gate 是唯一自动授权者。
7. TeachingMoment bounded 且不嵌套。
8. Full reveal 后不会误记 independent evidence。
9. partial delivery 不污染 transcript/exposure。
10. duplicate/retry 不产生重复 canonical side effect。
11. crash recovery 不重跑整个 turn。
12. Relationship 与 Learning 不串域。
13. 当前用户明确请求不会被 coverage debt 抢占。
14. Planner/Teaching/Runtime stress fixtures 全部通过。
15. CP4 projections 不持有 ConversationCoordinatorLease。
16. `NO_ASSISTANT_OUTPUT` 有合法 Turn path，并可形成 user-only CanonicalTurnSlice。
17. GateDecision 只在 SELECT candidate 进入 Gate 时存在。
18. ContextOpportunity 与 LearningOpportunityRecord 类型/存储隔离。
19. R0–R4 readiness 在 canonical docs 内有规范定义。
20. Planner failure 与合法 NO_TARGET 在数据、trace、测试上不可混淆。
21. Learner State 与 Evidence 使用 EvidenceModality；GoalModality 不覆盖 evidence source。
22. 无 voice/audio runtime 时，不生成 VOICE_PRODUCTION/AUDIO_COMPREHENSION Evidence，也不累计 impossible direct coverage debt。
23. Gate continuation 使用 ACTIVE_MOMENT authorization；本 Moment 新 Evidence 不使其自身 continuation 失效。
24. Secret 不进入 app.db prompt payload/log/export；Provider 使用最小 disclosure view。
25. 删除 canonical user source 可删除/重建 solely-derived Learning/Relationship/Episode/Index state。
26. Local Runtime 不依赖 distributed lease/heartbeat；CP2 atomic rollback 与 runtime_epoch recovery 测试通过。
27. BF-01A～BF-07 与 Golden Scenario regression 全部通过。
```

---

## 17. Initial Implementation Priorities

第一批代码提交顺序：

```text
01 IDs / versions / Result / Error / EvidenceModality types
02 app.db migrations + transaction helpers + runtime_epoch
03 InputEnvelope / TurnRecord / keyed conversation mutex / InterruptRequest
04 Persona Runtime + PromptCompiler + Provider adapter + BUFFERED_VALIDATED delivery
05 canonical transcript + action-level idempotency + terminalization
06 Learning Evidence kernel + Estimator v1.1 reference regression
07 user-initiated TeachingMoment + durable active_teaching_lock
08 minimal Curriculum/Content runtime for 10–20 validated targets
09 Goal/Scheduler views + impossible-modality pause semantics
10 Planner shadow mode + v1.1 benchmark
11 Gate v1.1 + automatic teaching
12 Relationship/Episode projections if not already added after vertical slice
13 guarded streaming / barge-in hardening
14 startup/opportunistic recovery hardening
15 content calibration resume
```

Do **not** install Redis/Kafka/distributed-lock/workflow infrastructure in bootstrap without a new multi-process requirement.

## 18. Explicitly Deferred

不让这些阻塞 V1：

```text
full voice live runtime
full multi-character Scene Runtime
cloud account sync
advanced probabilistic learner model
large-scale exam analytics
massive content expansion
```

先把核心 runtime 做对。
