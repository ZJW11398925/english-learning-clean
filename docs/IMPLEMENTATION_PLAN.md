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

---

## 19. Detail Block — 用户角色入世界（Living-World Phase, 2026-10-11 补写）

**依据**：living-world-spec §3.2 v2.2（用户角色款）+ cognition-and-narrative-quality 域一 v1.2（用户层）。**问题**：总设计从未定义「用户在世界里的位置」——用户在 canonical 层是「学习者」、在活世界层是「发条」，都不是「世界内的居民」。这是总设计的结构性缺口（用户 dogfood 报告「根本没出现这个人」的根治面）。

**工程含义**（五条，按依赖序）：

1. **包级 `user_character` 节**：世界包新增可选节（名/一句锚/住处）——世界知道你是谁。Berrymoor 先给（用户角色 = 镇上的居民，名字/住处由世界包声明，用户可在设置面改名）。
2. **narrator cast 区加「你的角色」行**：`build_narrator_prompt` 的 cast 区在角色名册之后加一行「Your character: {name} — {anchor}」——叙事者写的世界里有你。
3. **事件 participants 可含用户**：`participants` 词表扩入用户角色 id（包级声明的 `user_character.id`）——你参与的事入编年史。
4. **认知视图含「用户层」**：角色认知视图的亲历层含「与你共处的事件」（participants 含用户角色 id 的事件）——她记得你。
5. **沉浸模式的「替你活」**：不选走向时，世界按你的日常节奏生成你的行动（narrator 可以写「你今天去了面包摊」——你存在，即使你此刻没写信）。

**前端面**（D-3 的前置）：世界详情页（六角色名册 + 你的角色卡 + 线 + 编年史）——你看见自己住在镇上。

**验收**：用户 dogfood 报告的四缺口（①用户角色零存在 ②叙事密度碎 ③前端卡逻辑 ④六角色不可见）中，①④由本刀根治；②③由后续刀（D-2 密度校准 / D-3 前端重构）根治。

---

## 20. Narrative V3 — 范式转折后的实现程序（2026-10-12，用户主导）

**依据**：范式转折交接（用户，2026-10-12）+ 设计篇 `docs/design/2026-10-12-narrative-v3-paradigm-shift.md`（同一套设计的补充收敛篇：职责分离 / Plan≠Canon / story_tick / Passage≠Event / 记忆六分 + 三种知道 / durable 用户角色 / 映射审计 / slicing；**已按外评 V3-0R 六项修订：结算两级 / World Bible 权威独立 / World Cast 入 V3-3 / Reader Exposure 本体 / tick 语义 / canonical 隔离**）。living-world-spec v3 已把 §2/§4 等旧条款降 legacy（物理重标题 + 术语拆表）；cognition 篇 v1.3 已重挂记忆域。

**产品核心**：一个持续存在、能够自己发展剧情的小说世界；用户本人是其中一个真实角色，章内只控制自己的角色（User Gate），章间有限参与故事方向（作者层）。**信件只是 UI/narrative presentation element。**

**原则**：

1. **并行新链**——不把现 `run_generated_step()` 改成新系统；旧生产链（letter-triggered run / NOTICE·RESPONSE / reveal 队列 / 每步 direction）保留、全绿，直到新纵向切片完整后再显式裁决退役。
2. **Plan ≠ Canon**（物理或语义分离）：Director 规划过而未发生的内容不得进入历史；**落地边界 = SEGMENT/SCENE COMMIT（微观、即时）**——每一段正文/每一次裁定结果立即入正史；**Chapter Settlement 只做压缩与收束，不是唯一沉淀边界**（V3-0R 修订）。
3. **USER INTENT ≠ WORLD FACT**：用户输入一律经 Action Resolver 裁定后才可能成为事实。
### 4. **单一时间刻度（V3-0R 裁定）**：`story_tick` = 整数世界时间单位（数据层唯一形态；粒度/含义由 World Calendar 解释，不依赖地球公历）；**Plan 时间（planned_start/end_tick）≠ Canon 时间（actual_start/end_tick）**；wall clock 仅系统 bookkeeping；不允许三套时间混成用户时间线。
5. **复用优先**：world/template_world_id/world_actor/character_card/voice/world_event/world_state_fact/world_storyline/participants/C1 认知视图/persona 生成基础/教学系统/用户配置与安全边界——全部保留复用（设计篇 §9.1）。
6. **MVP 规模纪律**：先只做一个世界、一名 AI 主角、一名用户角色、一章；**纵向切片真正「好玩」以前不扩大规模**（不做多世界 UI / 多主角 / 复杂遗忘 / 学习桥 / 多模板）。

**第一阶段 slicing（刀序，开工前逐刀走本仓四查+VAL+TASK 流程）**：

| 刀 | 内容 | 门/兑现面 |
|---|---|---|
| V3-0R | 设计修订（外评六项：结算两级 / Bible 权威 / V3-3 扩面 / Reader Exposure / tick 语义 / canonical 隔离）——**复核通过即冻结 V3.0** | 复核通过才开 V3-1 |
| V3-1 | **Narrative foundations（design-first）**：实现合同已入四份 canonical（见下表后注）；本刀落 story_tick + chapter/scene 生命周期**类型** + Plan/Canon 边界类型 + 最小 migration（0029） | 验收：同一世界 Plan/Canon 类型隔离；tick 单调；状态机合法；旧 V2 链全绿；两 commit 的**类型与幂等键基础**就位（其「原子边界成立 / 崩溃不重复裁定」断语归 V3-5 / V3-6 兑现门——V3-1 无 passage/gate/action 表，物理上不可测） |
| V3-2 | World Bible（`world_bible_revision` 权威面 + 读取；权威方向 = Bible → projection → legacy lore） | 版本化、可引用；与 legacy lore 不双权威 |
| V3-3 | **World Cast & Player Identity**：`world_actor_profile` + durable player character + participant namespace | Director 的 cast 输入齐备；旧 `world_actor` 不动 |
| V3-4 | Director + `world_chapter(_plan)`（Blueprint 严格 schema；软期望集 + 硬条件律；Plan≠Canon 落表） | 计划不上屏入史；`closing_pressure` 非 postcondition 有钉 |
| V3-5 | Scene + Dossier + POV Writer + `narrative_passage` + **SEGMENT COMMIT** | 一场一 POV；秘密不泄漏；commit 后下一场立即可读 |
| V3-6 | User Gate + `user_action` + Action Resolver + **OUTCOME COMMIT** + SCENE/CHAPTER replan | intent≠fact；用户选择让原计划失效后不许绕回 |
| V3-7 | Actor Memory/Belief + Chapter Settlement + chapter summary + Narrative Memory | 章末只做压缩/收束；下一章只读摘要面 |
| V3-8 | Gold Scenario 端到端 + 最小阅读面 + **结构验收 12 条** | 12 条全绿 + 用户亲验「好玩」（两者同时）；通过后才议 UI 切换与旧链退役 |

**V3-1 实现合同位置（先合同后 migration，不得边写表边反推 authority）**：`DOMAIN_MODEL.md §20`（权威与七条硬边界）/ `STATE_MACHINES.md §21–§27`（生命周期、两级提交、tick 规则）/ `DATA_MODEL.md §26.2`（实体语义、幂等键、V3-5 最小读路）/ `RUNTIME_ARCHITECTURE.md §27–§30`（管线、NCP-1..4、恢复与不变量）。V3-1 的 migration 设计（0029+）与本实现合同同批评审（**已评审 PASS WITH CORRECTIONS，处置已落**——见 `DECISION_REGISTER.md` v1.3.1）。

**Gold Scenario（固定）**：帝国历 105 年 10 月 1 日——主角莉亚；用户角色远房表弟；父亲凌晨赴帝都、母亲上午从乡下带用户回来；初见；至少一次自由 User Gate；ActionResolver 裁定；按用户选择继续；第一章结束、Settlement、生成第二章 Blueprint。验收链：创建世界→创建角色→Chapter Blueprint→Scene Dossier→POV prose→User Gate→User Action→Action Resolver→必要时 Replan→继续正文（每段 SEGMENT COMMIT）→Chapter Settlement→Chapter 2 Blueprint。

**结构验收 12 条（V3-0R，与用户「好玩」门并列）**：① Director 产出完整 Blueprint ② Writer 正确保持莉亚 POV ③ 秘密没有提前泄漏 ④ User Gate 只在真实意志点触发 ⑤ 用户自由输入被 Resolver 裁定 ⑥ 一个用户选择真正让原计划失效 ⑦ Replan 后没有强行绕回旧计划 ⑧ Scene 3 能读取 Scene 2 已 commit 的事实 ⑨ 第一章实际结果与 Blueprint 可以明显不同 ⑩ Chapter Settlement 生成摘要 ⑪ Chapter 2 使用真实 Chapter 1 结果，而不是原计划 ⑫ 重启后能够从最新 narrative state 恢复。

**V3-8f（2026-10-13 补写——真实模型接线基线）**：首次真实凭证亲验（V3-8e 收口后）显示阅读面「连流程都跑不通」：egress 时限 30s < 真实单次写作 43–72s；四臂 prompt 未写明 JSON 值类型 ⇒ 模型对复数语义字段输出数组、严格解析拒收（`bad-shape`）；seam 失败码被压平成 `transport-error`（用户面误导）；V3 写路由 60s host 等待截断长驱动。修复刀按范式篇 **§10.4「真实模型接线基线」** 执行（时限独立校准 180s ／ prompt 逐字段类型合同＋解析宽容刀口 ／ 失败码透传人话 ／ 长驱动等待覆盖驱动预算 600s）；门 = 四门全绿 + 新钉族 + **真实模型全链冒烟**（仓外副本、四臂覆盖）通过，随后用户重跑「好玩」亲验。双门纪律不变。

**与既有 Phase 的关系**：Phase 0–10 runtime 面（conversation/persona/learning/teaching/runtime/……）全部不动；Narrative V3 是在其上新增的叙事域程序。真实 automatic-teaching rollout 维持 HOLD（SessionBudget 三分与内容补课为开闸前置）不变；P17 学习桥硬门转由叙事域的咬合面承接（触发条件改判须显式留痕）。
