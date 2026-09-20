# STATE_MACHINES.md

> 状态：CANONICAL IMPLEMENTATION BASELINE V1  
> 目标：冻结 V1 Clean Rewrite 的主要状态机与合法 transition 语义。

---

## 1. TeachingMoment Lifecycle

### Canonical lifecycle states

```text
AUTHORIZED
OPENING
AWAITING_USER
EVALUATING
DECIDING_NEXT_ACTION
COMPLETING
ABORTING
TEACHING_TERMINAL
RESUMING
CLOSED
```

### Main flow

```text
Planner SELECT
    ↓
Gate OPEN ALLOW
    ↓
AUTHORIZED
    ↓ acquire TeachingLockLease
OPENING
    ↓ opening delivery confirmed/estimated
AWAITING_USER
    ↓ TeachingResponseEnvelope
optional attempt
    ↓
EVALUATING
    ↓ AttemptEvaluationRecord + Evidence handling
DECIDING_NEXT_ACTION
    ├─ HINT / RETRY ───────────→ AWAITING_USER
    ├─ REVEAL / EXPLAIN ───────→ AWAITING_USER or COMPLETING
    ├─ USER SWITCH ─────────────→ ABORTING
    ├─ SKIP / TOPIC SHIFT ──────→ ABORTING
    └─ SUCCESS ─────────────────→ COMPLETING

COMPLETING / ABORTING
    ↓ finalize teaching outcome
TEACHING_TERMINAL
    ↓ release TeachingLockLease
    ├─ resume needed → RESUMING
    └─ no resume ───────────────→ CLOSED

RESUMING
    ↓ delivered / failed
CLOSED
```

---

## 2. TeachingMoment Rules

- 创建前必须 `Planner SELECT + Gate ALLOW`。
- Gate DENY 不创建 Moment。
- 一个 Moment 只有一个 FocusTarget。
- Closed 不允许 reopen。
- future teaching 使用 new `moment_id`。
- v1 不支持长期 `SUSPENDED`。
- Topic shift / later 默认结束当前 Moment。
- Explicit SWITCH_TARGET：先关闭当前 Moment，再同 turn 新 DecisionCycle。
- Teaching completion 不等于 mastery。
- TeachingPointResolved 不等于整句完全自然。

---

## 3. Teaching Presentation Phases

```text
INITIAL_PROMPT
HINT_SEMANTIC
HINT_STRUCTURAL
HINT_PARTIAL_FORM
FULL_REVEAL
POST_REVEAL_OPTIONAL_ATTEMPT
EXPLANATION
```

Support levels：

```text
NONE
CONTEXT_ONLY
SEMANTIC_HINT
STRUCTURAL_HINT
PARTIAL_FORM
FULL_FORM_SHOWN
```

同一个 Moment 内真实 exposure 一旦提高，后续 Evidence 不得假装更少支架。

---

## 4. TeachingResponseEnvelope

用户教学回复不是互斥单枚举。

```text
TeachingResponseEnvelope
  attempt?
  control_intent
  target_switch_request?
  clarification_request?
  user_preference_signal?
  interpretation_confidence
```

`control_intent`：

```text
CONTINUE
ASK_HINT
ASK_ANSWER
ASK_EXPLANATION
ASK_CLARIFICATION
SKIP
REJECT_TARGET
CHANGE_TOPIC
SWITCH_TARGET
META_DISCUSSION
NONE
```

处理顺序：

```text
1 parse control intent
2 detect optional attempt
3 if attempt: evaluate + durable record + evidence commit/proposal
4 apply control intent
5 next action / close / replan
```

---

## 5. Attempt Evaluation

Evaluation outcomes：

```text
SUCCESS
PARTIAL
FAILURE
ALTERNATIVE_SUCCESS
ABSTAIN
```

### Capability Practice

Alternative realization 成功：

```text
ALTERNATIVE_SUCCESS → valid capability success
```

### Resource Practice

用户通过其它说法完成 communication：

```text
Capability positive
Resource neutral/not demonstrated
```

不能把 communication success 粗暴标成整体失败。

---

## 6. Teaching Completion Outcome

```text
SUCCESS_UNSUPPORTED
SUCCESS_SUPPORTED
SUCCESS_ALTERNATIVE
PARTIAL_PROGRESS
REVEALED
USER_SATISFIED
NO_FURTHER_VALUE
```

这些只描述 teaching episode，不写 mastery。

---

## 7. Teaching Abort Reason

```text
USER_SKIP
USER_REJECTED_TARGET
USER_TOPIC_SHIFT
USER_SWITCH_TARGET
AMBIGUOUS_EXIT

POLICY_STOP
ATTEMPT_LIMIT
CONTENT_INVALID
SNAPSHOT_INVALIDATED
PRE_DELIVERY_INVALIDATED

SYSTEM_FAILURE
DELIVERY_FAILURE
EXPIRED
SYSTEM_RECOVERY_ABORT
```

Abort 本身不产生 negative mastery evidence。

---

## 8. Continuation Gate

Gate contexts：

```text
OPEN
AUTO_CONTINUE
USER_REQUESTED_CONTINUE
```

User-requested continue（如“再试一次”“给我提示”）可降低 interruption cost，但不绕过 hard cap。

预算分：

```text
soft_attempt_limit
hard_attempt_limit
soft_teaching_turn_limit
hard_teaching_turn_limit
```

具体数值实现期校准。

---

## 9. TeachingLockLease

`TeachingLockLease` 是“同一 conversation 至多一个 active TeachingMoment”的逻辑锁 contract。

Local Runtime V1 使用 durable unique lock row：

```text
conversation_id  # UNIQUE / PK
moment_id        # UNIQUE
state_version
```

生命周期：

```text
Moment created
→ durable lock acquired in same CP2 transaction
→ teaching active
→ TEACHING_TERMINAL
→ durable lock released in short transaction
→ Persona Resume no longer holds lock
```

Local V1 不依赖 TTL/heartbeat 判断进程死亡；startup recovery 通过 durable Moment state + runtime_epoch revalidate/release orphan lock。Cloud/multi-process profile 可替换物理锁实现，但不能改变 exclusivity 语义。

---

## 10. TurnRecord State Machine

协调状态：

```text
RECEIVED
USER_COMMITTED
ANALYZING
DECIDING
GENERATING
DELIVERING
DELIVERY_TERMINAL
POSTPROCESSING
COMPLETED

CANCELLED_BY_USER
FAILED_RECOVERABLE
FAILED_FINAL
```

Turn outcome 单独记录：

```text
REPLIED_FULL
REPLIED_PARTIAL
NO_ASSISTANT_OUTPUT
CANCELLED_BY_USER
FAILED_USER_VISIBLE
```

`DELIVERY_TERMINAL` 表示 user-visible assistant path 已终止。`REPLIED_FULL`、`REPLIED_PARTIAL`、`NO_ASSISTANT_OUTPUT` 都可进入 `DELIVERY_TERMINAL → POSTPROCESSING/COMPLETED`；不要求一定存在 AssistantTurn。

---

## 11. DecisionCycle

通常：

```text
1 Turn = 1 DecisionCycle
```

但 same-turn explicit target switch 可以：

```text
DecisionCycle #1
→ current attempt evidence
→ close old TeachingMoment
→ DecisionCycle #2
```

每个 cycle 固定：

```text
learning_snapshot_id
evidence_watermark
curriculum_version
goal_version
schedule_version
policy_version
context_view_version
```

Planner/Gate/Teaching action planning 在同 cycle 内使用同一版本。

---

## 12. Planner / Runtime Decision Semantics

Planner 自身只有合法决策：

```text
SELECT
NO_TARGET
```

独立执行状态：

```text
PlannerExecutionStatus:
  SUCCEEDED
  DEGRADED
  FAILED
  UNAVAILABLE
```

当 Planner/Learning/Gate 等故障导致自动教学关闭时，Runtime 可产生：

```text
RuntimeDecisionOutcome = DEGRADED_NO_AUTOMATIC_TEACHING
```

它不是 `PlannerDecision`。


## 12.1 Teaching Gate Authorization — v1.1

Gate contexts：

```text
OPEN
AUTO_CONTINUE
USER_REQUESTED_CONTINUE
```

Authorization basis 必须区分：

```text
OPEN         → DECISION_CYCLE
CONTINUATION → ACTIVE_MOMENT
```

统一状态：

```text
authorization_status = VALID | INVALIDATED | UNKNOWN
```

这是 BF-04 的跨层修订：active TeachingMoment 自己提交新 Attempt Evidence 会推进 Learning watermark，但**不会**仅因此使当前 Moment continuation 失效。Continuation 由 ACTIVE_MOMENT authorization lineage 约束，而不是要求 opening DecisionCycle 永远是最新 LearningSnapshot。

Gate 固定只检查 execution admissibility：safety/privacy、lineage/authorization validity、target/content validity、suppression、latest UserIntent、auto-teach setting、TeachingLock/lifecycle、hard flow protection、automatic opening budget/cooldown、hard attempt/turn caps。Gate 不重新计算 learning_need、goal_relevance、coverage_debt 或 Planner utility。

Critical Gate state UNKNOWN 时：

```text
GateExecutionStatus = DEGRADED
GateDecision = none
```

显式用户请求可绕过纯 automatic-interruption controls（auto preference、automatic opening budget/cooldown、conversation-flow protection），但不能绕过 safety/privacy、active suppression、invalid target/content、lock/lifecycle conflict 或 hard teaching limits。


## 13. Delivery State

### ServerDeliveryRecord

```text
NOT_SENT
SENDING
SENT_PARTIAL
SENT_COMPLETE
FAILED
CANCELLED
```

### Client render

`ClientRenderAck` 是异步 refinement event；主 Turn 不等待 ACK 才 terminalize。

- 有 ACK：提高 `ExposureEstimate` certainty。
- 无 ACK：保留 `SERVER_SENT_UNCONFIRMED`。
- late ACK 默认只完善审计 certainty，不自动把已经提交的 Learning Evidence 升级为更强能力证据；重评必须走显式 supersede/re-evaluation。

### ExposureEstimate

```text
certainty:
  CONFIRMED_RENDERED
  SERVER_SENT_UNCONFIRMED
  UNKNOWN

exposure_level:
  NONE
  PARTIAL
  FULL
```

Teaching Evidence 在不确定时使用 conservative upper-bound support attribution。

---

## 13.1 Opening Delivery Predicate

`OPENING → AWAITING_USER` 不等待 ClientRenderAck。

合法条件：

```text
ServerDeliveryRecord 已达到 terminal send state
AND initial ExposureEstimate != NONE
```

如果 opening 完全未发送：

```text
ABORTING(reason = DELIVERY_FAILURE)
```

如果只发送 partial opening，则由 Teaching Controller 决定继续、补救或 abort，但不得假装 full exposure。

---

## 14. GenerationActionIntent

```text
PREPARED
REQUESTED
GENERATING
VALIDATING
READY_TO_DELIVER
DELIVERING
TERMINAL
```

一个 action 可以有多个 `ProviderAttempt`，但最多一个 canonical accepted result。

Late result 对 cancelled/superseded action 不得产生 canonical side effect。

---

## 15. Response Validator

输出：

```text
ACCEPT
RETRY
FALLBACK
ABORT_DELIVERY
```

Retry bounded。

Validator 不写 Learning/Relationship/Teaching truth，不自己补教学文本。

---

## 16. PreDeliveryGuard

只做 hard invalidation：

```text
conversation inactive
action cancelled/superseded
TeachingLock invalid
new hard suppression
JUST_CHAT hard invalidation
lineage mismatch
```

输出：

```text
VALID
INVALIDATE_ACTION
```

不重新打分、不 replan。

---

## 17. ConversationCoordinatorLease

用于保证同一 conversation 只有一个 user-visible coordinator。它是逻辑 coordination contract。

Local Runtime V1 映射为：

```text
per-conversation in-process keyed mutex
+ runtime_epoch restart fencing
+ durable TurnRecord / GenerationAction state
```

Local V1 不需要 durable coordinator lease table、TTL 或 heartbeat。未来 cloud/multi-process profile 可替换物理实现。

它不同于 TeachingLockLease：

```text
ConversationCoordinatorLease = turn serialization
TeachingLockLease = teaching focus exclusivity
```

---

## 17.1 Barge-in / Interrupt Path

V1 使用逻辑上的：

```text
ConversationInputQueue / InterruptRequest
```

规则：

1. 新 `InputEnvelope` 可在 coordinator lease 外先 durable/dedupe。
2. 若旧 turn 正 streaming，新输入产生 `InterruptRequest` 指向 active turn/action。
3. 只有当前 lease holder（或 recovery owner）能 cancel/supersede current delivery、canonicalize old partial output、terminalize old turn。
4. 完成后 lease handoff 给新 turn。
5. 新 worker 不得绕过旧 lease 直接输出第二条并发 assistant stream。

---

## 18. Learning Evidence State Semantics

Evidence 是 append-only。

修正：

```text
ACTIVE
SUPERSEDED
INVALIDATED
```

Learner State 由 active evidence 重建。

UNKNOWN 是 dimension-level absence of sufficient evidence，不是 0。

---

## 19. Planner Flow State

```text
Resolve UserIntentScope
→ generate Track A/B CandidateProposal
→ canonicalize / merge origins
→ authoritative feature assembly
→ planning-context validity
→ hard eligibility (scope/prereq/readiness/modality/suppression)
→ ActiveLearningFrontier
→ Policy Utility
→ coverage-starvation safeguard at eligible natural break
→ per-candidate activation threshold
→ explicit request_priority restriction
→ Pareto prune
→ deterministic near-tie break
→ SELECT / NO_TARGET
```

Tie-break 只在近似同分时：

```text
request_aligned
→ user_initiated
→ REACTIVE > OPPORTUNISTIC > PROACTIVE
→ opportunity_expiry
→ lower interruption cost
→ lower overexposure
→ lower cognitive load
→ candidate_id
```

---

## 20. Invalid Transition Principles

以下直接拒绝：

```text
CLOSED → active
OPENING without authorized Moment
AWAITING_USER before opening delivery state known
HINT_DELIVERED without delivery/exposure evidence
second automatic TeachingMoment while TeachingLock active
canonical delivery commit from superseded action
```

所有 multi-event state transition 使用：

```text
state_version + compare-and-swap
```

避免 callback/user interrupt/recovery worker 乱序覆盖。
