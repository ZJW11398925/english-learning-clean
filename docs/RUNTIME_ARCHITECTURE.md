# RUNTIME_ARCHITECTURE.md

> 状态：CANONICAL IMPLEMENTATION BASELINE V1  
> 目标：定义 V1 一个真实 conversation turn 的执行顺序、Authority、commit point、provider/streaming/retry/recovery 与降级策略。

---

## 1. Runtime Thesis

`TurnTransaction` 不是大事务，而是：

```text
logical coordination saga
+
short ACID commits
+
external actions
```

外部 provider call 不进入长 DB transaction。

---

## 2. Core Runtime Components

```text
Conversation Orchestrator
Conversation Domain
Learning Evaluator / Learning Domain
Teaching Observer
Pedagogy Planner
Teaching Gate
TeachingMoment Controller
Teaching Planner
Persona Runtime / PromptCompiler
Response Validator
Delivery Manager
Relationship Recorder / Relationship Domain
Episode Recorder
Persistence / Action Log / Recovery Worker
```

物理上可合并进单进程，但逻辑 Authority 必须保持。

---

## 3. Orchestrator Responsibilities

可以：

```text
assign turn id / sequence
acquire coordinator lease
dedupe input
advance TurnRecord
call domain query/command handlers
create DecisionCycle
coordinate generation/delivery
recover incomplete actions
emit trace
```

禁止：

```text
decide target
write Evidence directly
write Relationship directly
build final prompt
generate persona text
```

---

## 4. Normal Turn Pipeline

```text
0  Acquire ConversationCoordinatorLease logical guard (Local V1: keyed mutex)
1  Dedupe / durable InputEnvelope
2  CP0: commit UserTurn + TurnRecord

3  Produce durable AnalysisArtifacts
   ├─ Learning evidence proposal
   ├─ Teaching opportunity proposal
   ├─ UserIntentScope
   └─ ConversationPriorityView

4  Learning validates/commits current-user Evidence
   → CP1
   → materialize new evidence watermark

5  Create DecisionCycle
   → bind LearningSnapshot + Curriculum/Goal/Schedule/Policy versions

6  Candidate generators
7  ActiveLearningFrontier
8  Pedagogy Planner

9A PlannerExecutionStatus = DEGRADED/FAILED/UNAVAILABLE
   → RuntimeDecisionOutcome = DEGRADED_NO_AUTOMATIC_TEACHING
   → no synthetic PlannerDecision
   → Normal Persona generation

9B PlannerDecision = NO_TARGET
   → Normal Persona generation

9C PlannerDecision = SELECT
   → Teaching Gate

10A Gate DENY
    → persist GateDecision(DENY)
    → Normal Persona generation

10B Gate ALLOW
    → CP2 atomically create:
       GateDecision(ALLOW)
       TeachingMoment
       TeachingLockLease / active_teaching_lock
       first GenerationActionIntent
    → Teaching Planner creates EphemeralTeachingDirective

11 Persona Runtime builds final prompt
12 Provider generation
13 Response Validator
14 PreDeliveryGuard
15 Delivery Manager
16 CP3a: ServerDelivery terminal + initial ExposureEstimate + AssistantTurn? canonicalization
17 Teaching delivery transition if applicable
18 Turn terminalization / DELIVERY_TERMINAL
19 release/handoff ConversationCoordinatorLease
20 CP4 post-turn projections asynchronously / best-effort
21 ClientRenderAck may arrive later and refine Exposure certainty
```

## 5. Active Teaching Turn Pipeline

如果有效 `TeachingLockLease + TeachingMoment`（Local V1: durable active_teaching_lock + Moment）：

```text
CP0 UserTurn
→ TeachingResponseEnvelope
→ optional AttemptRecord
→ AttemptEvaluationRecord durable
→ Learning Evidence commit/proposal
→ TeachingMoment state transition
→ Continuation Gate
→ next Teaching action / terminal
```

默认不跑普通 Planner。

只有：

```text
explicit USER SWITCH_TARGET
```

才关闭旧 Moment、释放锁、创建同 turn 新 DecisionCycle。

---

## 6. Commit Points

### CP0 — User durable

```text
InputEnvelope dedupe
UserTurn
TurnRecord
```

必须在 provider 调用前成功。

### CP1 — Current-user learning

```text
EvidenceGroup / EvidenceClaim
Learning watermark
```

当前 turn 的用户行为先进入 Learning，再创建正常 Planner DecisionCycle。

### CP2 — Decision durable

成功路径：

```text
DecisionCycle
PlannerExecutionStatus = SUCCEEDED
PlannerEvaluation
PlannerDecision
GateDecision?   # only when SELECT reaches Gate
```

Planner failure/unavailable：

```text
PlannerExecutionStatus = DEGRADED / FAILED / UNAVAILABLE
RuntimeDecisionOutcome = DEGRADED_NO_AUTOMATIC_TEACHING
```

不伪造 `PlannerDecision`。

若 opening teaching：

```text
TeachingMoment
TeachingLockLease
GenerationActionIntent
```

尽量同短事务原子提交。

### CP2.5 — Provider action log

```text
ProviderAttempt
validation attempt
```

### CP3a — Delivery canonicalization

```text
ServerDeliveryRecord terminal state
initial ExposureEstimate
AssistantTurn canonical content?  # zero/partial/full
Teaching delivery event
```

主 Turn 不等待 `ClientRenderAck`。

### ClientRenderAck — asynchronous refinement

```text
ClientRenderAck
→ refine ExposureEstimate certainty
```

Late ACK 默认只提高 audit certainty；V1 不自动把已提交 Evidence 升级为更独立的能力证据。需要重评时必须显式 supersede/re-evaluate。

### CP4 — Projections

```text
Relationship
Episode
PlanningLedger actual exposure/outcome
Retrieval index
analytics
```

CP4 在 `ConversationCoordinatorLease` 释放后运行；projection 延迟或失败不得阻塞下一 user-visible turn。

---

## 7. What Must Never Share One Large Transaction

禁止绑定：

```text
UserTurn + provider generation
Learning Evidence + assistant delivery
Assistant delivery + Relationship projection
Teaching completion + Persona Resume delivery
Planner selection + actual teaching exposure
Transcript + retrieval index
```

失败语义不同。

---

## 8. Analysis Before Planner

正常 turn 必须：

```text
UserTurn durable
→ current behavior evaluation
→ Evidence commit
→ Learning State materialize
→ Planner snapshot
```

防止：

```text
用户刚自然说对
系统仍按旧 gap 再教
```

---

## 9. DecisionCycle Consistency

一个 DecisionCycle 内固定：

```text
LearningSnapshot
Curriculum
Goal
Policy
Schedule
Context
```

Planner/Gate/Teaching action planning 不静默切换版本。

同 turn replan 必须新建 cycle。

Second DecisionCycle 不得重新消费/提交已经完成的同一 user-turn analysis；只读取新的 evidence watermark、explicit switch intent 与缺失 artifact 的 recovery result。

---

## 10. Inference Coalescing

性能优化允许一次模型调用同时返回：

```text
learning evidence proposals
teaching opportunity proposals
user intent proposal
conversation priority proposal
```

但必须：

```text
namespaced schema
separate confidence
separate validation
separate commit
```

Inference coalescing ≠ Authority coalescing。

---

## 11. Persona Runtime

唯一拥有 final PromptCompiler。

`GenerationContext`：

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

Orchestrator 只传结构化 view/reference，不拼 prompt。

---

## 12. Response Validation

位置：

```text
Persona Runtime output
→ Response Validator
→ PreDeliveryGuard
→ Delivery
```

Validator 检查：

```text
GenerationContract compliance
TeachingDirective compliance
persona identity consistency
disclosure boundary
no unauthorized teaching expansion
no hidden system/meta leakage
no false mastery claim
presentation-phase constraints
```

输出：

```text
ACCEPT
RETRY
FALLBACK
ABORT_DELIVERY
```

Retry bounded。

---

## 13. Delivery Modes

### BUFFERED_VALIDATED

默认用于：

```text
TEACHING_OPEN
TEACHING_HINT
TEACHING_REVEAL
TEACHING_EXPLANATION
high-risk disclosure-sensitive action
```

流程：

```text
provider complete
→ full validation
→ delivery
```

### GUARDED_STREAM

默认用于普通 persona chat。

需要：

```text
small buffer / chunk guard
server delivery tracking
client render ack where possible
late callback protection
```

---

## 14. Exposure Semantics

分三层：

```text
PresentationAction
ServerDeliveryRecord / ClientRenderAck
ExposureEstimate
```

服务端不宣称知道“人类真的看到”。

教学 Evidence：

```text
confirmed exposure where available
otherwise max-possible-exposure
```

宁可低估 independence，不高估。

Late ClientRenderAck 只作为 certainty refinement；V1 默认不 retroactively upgrade committed Evidence。若未来允许重评，必须生成 superseding EvidenceClaim / re-evaluation trace。

---

## 15. PreDeliveryGuard

只检查 hard invalidation：

```text
conversation inactive
action superseded
action cancelled
TeachingLock invalid
new target suppression
JUST_CHAT hard switch
lineage mismatch
```

不重新跑 Planner utility。

---

## 16. Retry Model

### Never retry whole Turn

只 retry：

```text
AnalysisArtifact generation
Learning commit
GenerationAction
Delivery action
Projection
```

每个 action/projection 有稳定 ID。

### External provider

采用：

```text
at-least-once / uncertain execution
```

### Internal canonical state

采用：

```text
exactly-once canonicalization
```

一个 GenerationAction 可以多个 ProviderAttempt，最多一个 accepted result。

---

## 17. Partial Delivery

如果已发送部分内容：

```text
不自动从头重放
```

canonicalize 已发送/确认边界并标记 uncertainty。

Teaching action 按 ExposureEstimate 处理。

---

## 17.1 Conversation Interrupt / Input Queue

新输入不能因为旧 worker 持有 `ConversationCoordinatorLease` 就无法请求中断。

V1 需要：

```text
ConversationInputQueue / InterruptRequest
```

语义：

1. 新 `InputEnvelope` 可先 durable/dedupe。
2. 若存在 active delivery，入口写 `InterruptRequest(active_turn_id, action_id, new_input_id)`。
3. 当前 lease holder 或 recovery owner 是唯一可执行 cancel/supersede、partial canonicalization、old-turn terminalization 的 actor。
4. old turn terminalize 后 lease handoff 给 new turn。
5. handoff 前 new turn 不得产生 user-visible assistant output。

---

## 18. User Barge-in

```text
cancel current stream if possible
→ terminalize current delivery as PARTIAL/CANCELLED
→ canonicalize old AssistantTurn
→ old Turn terminal
→ start new user turn sequence
```

同 conversation 不允许两个 user-visible assistant streams 并发。

---

## 19. Relationship / Episode Projection

默认在 canonical turn 后运行。

Relationship Recorder 输入：

```text
actual UserTurn
actual canonical AssistantTurn? 
existing RelationshipView
```

输出 proposal，Relationship Domain re-validates。

未实际 delivery 的 assistant output 不得成为 shared event。

Projection failure：

```text
不回滚 transcript
不重发 assistant
不继续占用 ConversationCoordinatorLease
```

---

## 20. PlanningLedger

区分：

```text
candidate_selected
teaching_presented
hint_presented
reveal_presented
user_skip
```

`SELECT != exposure`。

CoverageDebt 不因 selection 自动偿还。

---

## 21. Runtime Degradation

### Learning evaluator unavailable

```text
normal persona
automatic teaching disabled/conservative
```

### Learning commit unavailable

```text
durable proposal pending
normal persona
no risky automatic remediation/probe
```

### Planner unavailable

```text
PlannerExecutionStatus = DEGRADED / FAILED / UNAVAILABLE
RuntimeDecisionOutcome = DEGRADED_NO_AUTOMATIC_TEACHING
normal persona
```

不创建 synthetic `PlannerDecision(NO_TARGET)`。

### Gate unavailable

```text
no automatic teaching
normal persona
```

### Teaching state failure

```text
abort/no-open teaching
normal persona
```

### Persona provider failure

```text
bounded action retry
else user-visible failure outcome
```

### Relationship/Episode failure

```text
turn still succeeds
projection retry/rebuild
```

---

## 22. Recovery

Recovery 扫描非 terminal：

```text
TurnRecord
GenerationActionIntent
TeachingMoment
TeachingLockLease
ConversationCoordinatorLease
ServerDeliveryRecord
pending AnalysisArtifact
pending projections
```

只恢复未完成 action/projection，不重跑整个 user turn。

---

## 23. Recovery Checkpoints

### Crash after CP0

从 analysis 继续。

### Crash after CP1

从 DecisionCycle/Planner 继续，不重复 Evidence。

### Crash after CP2

继续同 `action_id`，不新建 Moment。

### Crash around CP3

若无发送，可 retry；若 delivery uncertain，保守 canonicalize，不盲目重放。

### Teaching terminal + Resume failed

不 reopen Moment；resume 可 retry 或由下个 turn 自然恢复。

---

## 24. Coordination Contracts / Local Runtime Mapping

### ConversationCoordinatorLease

逻辑保证：

```text
same conversation one user-visible coordinator
```

Local Runtime V1：

```text
in-process keyed mutex
+ runtime_epoch
+ durable Turn/Action state
```

新 InputEnvelope / InterruptRequest 可在 mutex 外 durable；只有当前 coordinator/recovery owner 可以 canonicalize old partial output 与 terminalize old turn。

### TeachingLockLease

逻辑保证：

```text
same conversation one active teaching focus
```

Local Runtime V1：durable `active_teaching_lock` unique row；不使用 TTL/heartbeat。

### Crash recovery

Local V1 不以 expiry 猜 owner 已死，而由新的 `runtime_epoch` 对旧 epoch nonterminal work 进行 startup/opportunistic recovery。Future multi-process profile 才需要真正 distributed lease/fencing implementation。

---


## 24.1 LOCAL_RUNTIME_PROFILE_V1

```text
single device / single active app process
app.db       → mutable user/runtime state
content.db   → read-only content release
SecretStore  → API key/token values
keyed mutex  → live ConversationCoordinator
runtime_epoch→ restart ownership boundary
active_teaching_lock → durable one-focus guarantee
projection_job → durable CP4 work
```

明确不要求：Redis、Kafka、distributed lock/lease service、heartbeat、leader election、multi-worker orchestration、2PC 或 always-on recovery daemon。

External provider call 必须发生在 DB transaction 之外。Provider retry：同 `GenerationAction.action_id` 下新增 `ProviderAttempt`，不得重跑 whole Turn。一个 Action 最多接受一个 ProviderAttempt；cancelled/superseded/terminal action 的 late result 只能忽略/审计。

Recovery：

```text
CP0 → RESUME_ANALYSIS
CP1 → RESUME_DECISION
CP2 → RESUME_ACTION_BY_STABLE_ACTION_ID
CP3 uncertain → CONSERVATIVE_DELIVERY_RECONCILIATION
```

CP4 projection 在 coordinator guard release 后执行；pending/failure 不阻塞下一 user-visible turn。

## 24.2 Gate Authorization Across Turn / TeachingMoment

OPEN Gate 绑定 `DECISION_CYCLE` authorization。TeachingMoment 打开后，continuation 绑定 `ACTIVE_MOMENT` authorization。当前 Moment 自己提交新 Evidence 导致 Learning watermark 前进，不构成 continuation invalidation。

Gate unknown critical state → `GateExecutionStatus=DEGRADED, GateDecision=null`；不得伪造 DENY。Gate DENY 后不得在同一 DecisionCycle 尝试 runner-up candidate 绕过授权。

## 24.3 Security / Provider Disclosure Runtime Boundary

PromptCompiler/Provider adapter 只能消费 action-specific disclosure view。Secret 在 send-time 由 transport 通过 `secret_ref` resolve；不进入 PromptCompiler、durable GenerationAction、普通日志或 portable export。删除进行中必须取消未发送 pending action；已发送第三方数据只能按 provider capability 尝试远端删除，不得虚假声明 remote revocation。

## 25. Canonical Runtime Trace

每 turn 串联：

```text
turn_id
input_id
user_turn_id
analysis_ids
evidence_commit_ids
decision_cycle_id
learning_snapshot_id
planner_decision_id
gate_decision_id
teaching_moment_id?
generation_action_id
provider_attempt_ids
validator_result_ids
server_delivery_id
client_render_ack_ids
assistant_turn_id?
projection_ids
runtime_version
```

---

## 26. Runtime Invariants

```text
R-INV-001 UserTurn provider 前 durable。
R-INV-002 current-user Evidence 在正常 Planner 前 commit/materialize。
R-INV-003 DecisionCycle 内 snapshot/version 固定。
R-INV-004 provider call 不在长 DB transaction 内。
R-INV-005 committed Evidence 不因 reply failure 回滚。
R-INV-006 canonical assistant content 不包含未发送 provider tail。
R-INV-007 retry action，不 retry whole turn。
R-INV-008 Planner/Gate decision 在授权 generation 前 durable。
R-INV-009 Teaching delivery transition 依赖 actual delivery/exposure，不依赖 planned content。
R-INV-010 post-turn projections 不拥有 transcript truth。
R-INV-011 same conversation user-visible runtime 串行。
R-INV-012 all side effects stable idempotency identity。
R-INV-013 validator 不拥有 domain writes。
R-INV-014 inference coalescing 不合并 authority。
R-INV-015 teaching intelligence failure 优先降级正常 conversation。
R-INV-016 service 不宣称知道人类视觉注意力；Exposure 有 certainty。
R-INV-017 external execution 可重复，canonical side effect 不重复。
R-INV-018 same-turn second DecisionCycle 不重复消费已提交 analysis。
```

---

## 27. Narrative V3 Runtime Pipeline（V3-1 实现合同）

> 依据：`docs/design/2026-10-12-narrative-v3-paradigm-shift.md`（v3.1 / V3-0R）+ `DOMAIN_MODEL.md §20` + `STATE_MACHINES.md §21–§27`。旧 turn pipeline（§4）与 Narrative V2 链（letter/run/reveal）为 legacy，继续全绿；V3 管线并行新增。

```text
章内循环（每章）：
  Director（读 Bible/State/Summaries/Storylines/relevant memories）
    → Chapter Blueprint（plan_revision ADOPTED；只写计划面）
  → Scene Planner：Dossier（planned ticks；POV；revealable / must_hide）
  → POV Writer：正文段（只写已规划且规则允许之事）
      → [遇到用户意志点] User Gate OPEN（故事停止）
            → 用户提交（ANSWERED；submission durable）
            → Action Resolver（事务外裁定）→ ACTION OUTCOME COMMIT
            → replan_scope 非 NONE → Plan Revision（SCENE/CHAPTER 级）
      → SEGMENT COMMIT（每段：passage + event + state + tick〔+ memory V3-7〕）
  → 场内段序循环；scene exit 达成 → SCENE COMMIT（场关闭）
章末：
  → CHAPTER SETTLEMENT（压缩 / 收束：summary / 线 / hooks / 显著性；不新增事实）
  → 下一章 Director 输入包（Bible + Current State + Chapter Summaries + Active Storylines + relevant memories）
```

边界（与 DOMAIN_MODEL §20.3 同源）：

- **Resolver 唯一裁定权**：outcome 先落（ACTION OUTCOME COMMIT）；Writer 只做文学化呈现（passage 的 `outcome_ref`），不得重复裁定或重复写同一 event/effects。
- Writer 拥有的只有**随后新产生的非用户事实**（经规划与规则允许），随 SEGMENT COMMIT 落地。**评审 #5 澄清：ACTION OUTCOME COMMIT 与随后呈现该 outcome 的 SEGMENT COMMIT 是三个事务链中的两环（resolver 裁定 → outcome commit → 引用呈现 → segment commit），不是同一事务。**
- Plan 面（Blueprint/Dossier）与 Canon 面（passage/event/state/memory）**类型隔离**；读 canon 只见已 commit 的内容。

## 28. Narrative V3 Commit Points（NCP）

与 legacy CP0–CP4 并列，V3 管线使用自己的提交点（物理可同库，authority 不合并）：

### NCP-1 — Submission durable（用户提交）

原子组（一个短事务）：

```text
user_gate: OPEN → ANSWERED
user_action: 建 ANSWERED 行（intent_text / selected_option? / submission_id）
```

在裁定（provider 调用）之前必须成功（gate 行与 action 行**同事务**落，不得拆开）；此点之后重复到达按 `(gate_id, submission_id)` 去重；action 族 event/outcome id 由 `action_commit_key` 派生。

**V3-6 落法（开工裁决 `DEC-OPI-dc1bafdf-…5`；重放行修订 `…21`）**：`submit_gate`（`elc/world/action.py`）——`user_action_id` 派生 `f"{gate_id}-a"`；`selected_option` 给定时须为该门已录选项之一（否则 `VALIDATION_FAILED` 点名）；重复到达：`(gate_id, submission_id)` 已存且形状同 ⇒ 返回存行（零写）、形状异 ⇒ `CONFLICT`；门非 `OPEN` 且非本 submission 重放 ⇒ `VALIDATION_FAILED`。

### NCP-2 — Action Outcome Commit

原子组（一个短事务）：

```text
user_action（终态：interpretation / outcome / actual_action / consequences）
world_event（用户行为事实；participants 含用户角色）
world_state_fact 结算（state_effects）
story_tick actual 推进
replan 记录（NONE | SCENE | CHAPTER）
（V3-7 起）actor memory / belief 增量
```

**V3-6 落法（开工裁决 `DEC-OPI-dc1bafdf-…5`；重放行修订 `…21`）**：`commit_action`（`elc/world/action.py`）——八列终态一次写齐（`actual_tick` = 推进后 `actual_end`）；行为事实行 id 派生 `f"ac:{gate_id}:{submission_id}:event"`（`kind='action'`，canonical participants ⊇ 用户角色）；lineage 行 `kind='ACTION_OUTCOME'`（`commit_id=f"ac:{gate_id}:{submission_id}"`、`action_id` 载、`passage_id`/`segment_seq` 空、`is_last_segment`=0）；章 `PLANNED→ACTIVE` 臂与 NCP-3 同律（#3）；重放形状同 = 全组 no-op、形状异 `CONFLICT`。完整臂序见 `STATE_MACHINES §25`「V3-6 落法」段。

**V3-6R 落法（开工裁决 `DEC-OPI-dc1bafdf-…31`）**：⑧ `action_replan` `PENDING` 出生（`replan_request_id` 派生；`NONE` 零行）；场 span 臂 `close_scene=False`（扩展场 actual 区间、不关场）；入终态仅自 `RESOLVING`。

### NCP-3 — Segment Commit

原子组（一个短事务）：

```text
narrative_passage（不可变）
world_event（本段非用户事实）
world_state_fact 结算
story_tick actual 推进
（V3-7 起）actor memory / belief 增量
```

**reader_exposure 不在本提交内（评审 #2 解耦）**：passage commit ≠ 用户已看见——exposure 在交付/渲染侧独立记录或保守 estimate（RA §14 家族），绝不与提交同事务充当 reader knowledge。

**V3-5R 落法（开工裁决 `DEC-OPI-dc1bafdf-…11`）**：① 同事务增写 `world_scene` 的 actual 区间（首段 start / 每段 end / 末段随 `ACTIVE→COMMITTED` 翻转——一个 UPDATE 一次版本推进；`commit_scene` 显式面不写 span；replay 零重改）；② fresh 段顺序律 `segment_seq == max(committed_seq) + 1`（首段 1；0/负数/跳号/倒序 ⇒ `VALIDATION_FAILED`；replay arm 先行）；③ `segment_commit.is_last_segment`（migration `0034_segment_terminality.sql`）持久化 SCENE COMMIT 身份并入 replay 形状比对（同 segment_key 不同 `is_last_segment` ⇒ `CONFLICT`）。完整臂序见 `STATE_MACHINES §25`「V3-5R 落法」段。

**V3-6R 落法（开工裁决 `DEC-OPI-dc1bafdf-…31`）**：`outcome_ref` 臂——`narrative_passage.outcome_ref` 引用真实 **COMMITTED** `user_action`（缺失 `NOT_FOUND`/非 COMMITTED `VALIDATION_FAILED`；其 gate 须属本场）；**同一事务**将该 gate `COMMITTED → CLOSED`；场有未 `CLOSED` committed gate 时 fresh 段**必须**携带该 ref（恢复正文不得以 NULL 落地）；replay 形状含 `outcome_ref`。span 臂由 NCP-2 与 NCP-3 共同调用（两臂律见 STATE §26）。

### NCP-4 — Chapter Settlement

```text
chapter_settlement（summary / storyline updates / hooks / salience）
chapter: SETTLING → CLOSED
```

**不是**事实落地边界——只压缩 / 收束已 commit 内容（N-INV-004）。

崩溃窗口与恢复：

```text
NCP-1 后崩溃      → recovery 以同一 submission_id 重新裁定（唯一终态）
NCP-2 中崩溃      → 事务全或无；重启后从 gate 的 ANSWERED 重放（幂等）
NCP-2 后崩溃      → 重放 = no-op；呈现层从 durable 状态重读
NCP-3 前崩溃      → 该段未发生；重新生成该段（只提交一次）
NCP-3 中崩溃      → 回到「最后已提交段」续跑
NCP-3 后崩溃      → 同 segment_key 重放 = no-op
NCP-4 中崩溃      → 重跑 Settlement（同章 summary 只落一版）
```

## 29. Narrative V3 Recovery

Startup / opportunistic recovery 扫描（在 legacy 面之外新增）：

```text
user_gate（ANSWERED / RESOLVING 未 COMMITTED）
user_action（RESOLVING 未 COMMITTED）
world_scene（ACTIVE 未 COMMITTED）
world_chapter（ACTIVE / SETTLING）
```

规则：

- 只恢复未完成动作；不重跑已 committed 内容。
- 不重复用户行为裁定（N-INV-002）：submission 幂等键是恢复锚点。
- 未 commit 的正文草案不是事实——恢复时可按 dossier 重新生成该段。
- 旧链 recovery（§22/§23）不受影响；两套恢复面互不写对方的行。

**V3-6 落法（开工裁决 `DEC-OPI-dc1bafdf-…5`；重放行修订 `…21`）**：扫描面落于 `elc/world/action.py` 的 `recovery_scan`（纯读；四族逐字：gates `ANSWERED`/`RESOLVING` 未 `COMMITTED`、actions `RESOLVING` 未 `COMMITTED`、scenes `ACTIVE`、chapters `ACTIVE`/`SETTLING`）；resume 的自动编排归管线刀（V3-8 前置），本阶段交扫描面与「submission 幂等键是恢复锚」的语义（NCP-1 后中断 ⇒ 扫描见 gate ⇒ 同一 `submission_id` 重裁定 ⇒ 唯一 outcome）。

**V3-6R 落法（开工裁决 `DEC-OPI-dc1bafdf-…31`）**：**第五族**——`action_replan` `status='PENDING'` 的义务（durable 恢复锚：claim 先行写入 `target_ref`，重试收敛同一 revision；`APPLIED` 零写返回）。

## 30. Narrative V3 Runtime Invariants

```text
N-R-INV-001 用户行为裁定唯一（Resolver）；恢复不产生第二份 outcome。
N-R-INV-002 Plan 面可重规划（版本化），Canon 面永不重写。
N-R-INV-003 提交事务外的正文/裁定草案不构成事实、不可被读取。
N-R-INV-004 两套提交（NCP-2 / NCP-3）全或无；同批写正文与其事实（零撕裂）。
N-R-INV-005 actual story_tick 只由提交事务推进，单调不减。
N-R-INV-006 Writer 不重复裁定用户行为；只呈现已 committed 结果。
N-R-INV-007 V3 读 canon 走已 commit 面；不得以 Plan 面冒充事实。
N-R-INV-008 legacy Narrative V2 链与 V3 管线互不写对方的表。
```
