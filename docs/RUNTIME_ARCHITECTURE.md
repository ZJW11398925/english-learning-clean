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
