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

---

## 21. Chapter Lifecycle（Narrative V3）

```text
PLANNED       # Blueprint 已落（Plan 面）；章未开
ACTIVE        # 至少一场开始（≥1 scene ACTIVE）
SETTLING      # 章末结算进行中
CLOSED        # Settlement 完成（summary / narrative memory 已落）
```

主流程：

```text
Blueprint(plan_revision ADOPTED) → PLANNED
→ 第一场 ACTIVE → ACTIVE
→ 章目标达成 / 收束判定 → SETTLING
→ Settlement 完成 → CLOSED
→ 下一章规划（新 chapter + 新 plan revision）
```

规则：

- 一个世界同一时间至多一章 `ACTIVE`（MVP；并行章禁止）。
- **章重叠禁止（评审 #4 前置裁决，V3-4 起强制）**：前一章 `CLOSED` 之前，其世界不得出现新的 `ACTIVE` 章——`SETTLING` 章与下一章 `ACTIVE` 共存亦禁止。**操作形（V3-4 落地读法，与 `SqliteNarrativeStore.activate_chapter` 一致）**：`activate_chapter` 在世界内存在 `ACTIVE` **或** `SETTLING` 的其他章时拒开；`PLANNED` 章不挡（多份 Blueprint 可先备好〔章间作者层〕，开章顺序由 lifecycle 面决定——前一章未 CLOSED 时是否拒开新章 = 已登记的 V3-5/V3-6 生命周期事项）。
- **ACTIVE 前置（评审 #4 前置裁决，V3-4 起强制）**：章进入 `ACTIVE` 必须已有一份 `ADOPTED` 的 Chapter Blueprint（plan_revision）。
- **lifecycle tick authority（评审 #3，V3-4/V3-5 起强制）**：`opened_at_tick` / `closed_at_tick` 在正式管线中必须取自当前 `world.current_tick`，并在转移事务内校验（V3-1 staging 的调用方代书为过渡态，提交刀接管）。
- `CLOSED` 不可 reopen；修正走后续章（N-INV-003）。
- `ACTIVE` 期间允许 Plan Revision（重规划**剩余**部分）；已 commit 的场景/段落不受影响。
- `chapter_index` 单调 +1；chapter identity 稳定。
- `SETTLING` 是短窗口：Settlement 产出全部落完才 `CLOSED`；崩溃于 `SETTLING` → recovery 重跑 Settlement（同章 summary 只落一版；重跑 = no-op 或显式新 revision）。

## 22. Scene Lifecycle（Narrative V3）

```text
PLANNED       # Plan 面：Blueprint/Dossier 计划的场（可被重规划 DISCARDED）
ACTIVE        # Dossier 已落；正文段写入中（含 User Gate 停点）
COMMITTED     # 场的全部段落已 commit（canon 面已成立）
CLOSED        # 场关闭（下一场输入包已生成）
DISCARDED     # 仅 PLANNED 可达：重规划使该场不再成立（从未发生）
```

主流程：

```text
PLANNED → ACTIVE（Dossier 落）
ACTIVE  → COMMITTED（最后一段 SEGMENT COMMIT + scene exit 达成）
COMMITTED → CLOSED
PLANNED → DISCARDED（Plan Revision）
```

规则：

- **SCENE COMMIT = 场的最后一段 SEGMENT COMMIT 的别名**（`ACTIVE → COMMITTED` 的翻转与该段提交**同事务**完成）；**不是第三种提交事务**。
- **ACTIVE 前置（评审 #4 前置裁决，V3-4 起强制）**：场进入 `ACTIVE` 必须已有一份 `ADOPTED` 的 Scene Dossier（dossier_revision）。
- **一旦有 segment commit，场景不可 DISCARDED / 取消**——已发生事实不可重写；只能按实际发生的方向 `COMMITTED`（提前收束合法）。
- 场内段落顺序 commit；段与段之间世界可被读取（下一段看得到上一段的事实）。
- 崩溃于 `ACTIVE`：从最后已 commit 段落续跑（未 commit 的正文草案不构成事实）；同 `segment_key` 重放 = no-op（§25）。
- User Gate 是场内的停点：gate `OPEN` 时 scene 保持 `ACTIVE`。（**V3-6 落法**：场的 gate 处于 `OPEN` / `ANSWERED` / `RESOLVING` 时新段落提交被拒——「故事停止」的物理形；新段落提交落成时该场全部 `COMMITTED` gate **同事务**转 `CLOSED`——「续写已开始」的物理形。）

## 23. User Gate Lifecycle（Narrative V3）

```text
OPEN          # 呈现停点（2–4 选项 + 自由输入）；故事停止
ANSWERED      # 用户提交一次（submission durable；幂等锚点）
RESOLVING     # Action Resolver 裁定中（事务外 provider 调用）
COMMITTED     # ACTION OUTCOME COMMIT 完成（结果成为 canon）
CLOSED        # 续写（新段落/场）已开始，或章末结算接管
```

主流程：

```text
OPEN → ANSWERED → RESOLVING → COMMITTED → CLOSED
```

规则：

- 一个 gate 只接受**一次** submission；重复到达按幂等键 `(gate_id, submission_id)` 去重（§25）。
- 一旦 `OPEN` 必须走完：无取消 / 无超时（本地单用户；故事停在该点直到用户回答）。
- `RESOLVING` 崩溃 → recovery 以同一 `submission_id` 重新裁定；**绝不产生第二份 outcome**。
- `COMMITTED` 后不可回到 `ANSWERED` / `RESOLVING`；修正走后续叙事。
- 选项与自由输入都只是 **intent**，不是事实（DOMAIN_MODEL §20.3-1）。

**V3-6 落法（开工裁决 `DEC-OPI-dc1bafdf-…5`；重放行修订 `…21`）**：门面与提交面落于 `elc/world/action.py`——`open_gate`（仅 `ACTIVE` 场；`options` 2–4 非空串；一场同一时间至多一个非终态门——`OPEN`/`ANSWERED`/`RESOLVING`，查在开门的短事务内而非部分 UNIQUE 索引）、`submit_gate`（**NCP-1**：`OPEN → ANSWERED` + `user_action` `ANSWERED` 行同一短事务；`(gate_id, submission_id)` 已存 ⇒ 形状同返回存行 / 异 `CONFLICT`；非 `OPEN` 且非本 submission 重放 ⇒ `VALIDATION_FAILED`——一个 gate 只接受一次 submission）、`begin_resolving`（`ANSWERED → RESOLVING` 两行同事务——事务外 provider 裁定前的 durable 停点；自 `RESOLVING` 重呼幂等）、`commit_action`（**NCP-2**，全臂见 §25）。`COMMITTED → CLOSED` 不需要独立面：下一条新段落提交即「续写已开始」（§22 互锁句，同事务）。崩溃语义：NCP-1 后未 `COMMITTED` ⇒ recovery 以同一 `submission_id` 重新裁定（唯一终态）；`COMMITTED` 后重放 = 幂等 no-op。

**V3-6R 收紧（开工裁决 `DEC-OPI-dc1bafdf-…31`）**：① **`RESOLVING` 为唯一入终态前驱**——`commit_action` 仅接受 `RESOLVING`（`ANSWERED` 直达 ⇒ `VALIDATION_FAILED` 点名 `begin_resolving`）；确定性 Resolver 基线以 `begin_resolving → commit_action` 为正链（单条主路径，不留旁路）。② **一场一未 `CLOSED` 门**——`open_gate` 拒绝场景存在**任何非 `CLOSED` gate**（`COMMITTED` 未续写亦拦）；先以带 `outcome_ref` 的续写段关闭前一门（§25 强制律），方可开下一门。③ `COMMITTED → CLOSED` 的物理形**收紧为显式臂**：携带 `outcome_ref` 的 fresh 段同事务关闭其被引 gate（不再泛关全部 COMMITTED 门）。

## 24. Plan Revision Lifecycle（Narrative V3）

适用范围：Chapter 重规划（replan_scope=CHAPTER）与 Scene 重规划（replan_scope=SCENE，落为 Dossier 新版本）。

```text
PROPOSED      # Director / Scene Planner 产出新 plan revision
ADOPTED       # 成为当前 plan（旧 revision 保留为历史）
SUPERSEDED    # 被更新的 revision 取代（历史保留）
REJECTED      # 显式否决（记录理由）
```

规则：

- Plan 面 **append-only 版本化**：不改写旧 revision；`ADOPTED` 指向当前。
- 已 commit 的 canon 永不因 Plan Revision 改变（N-INV-003）。
- SCENE 级：未开的 `PLANNED` 场可 `DISCARDED`；`ACTIVE` 场只能以已发生方向收束。
- CHAPTER 级：只重规划**剩余**部分；对已 `COMMITTED` 场无写权。
- 用户章间作者层输入（方向/基调）= plan 的偏好输入，不自动成事实；采纳与否由 Director 在 Blueprint/Revision 中体现。

## 25. Commit Transactions（Narrative V3）——原子组 / 幂等 / 崩溃重试

### SEGMENT COMMIT

原子组（一个短事务；全或无）：

```text
narrative_passage（正文，不可变）
world_event（本段沉淀的非用户事实；participants / effects）
world_state_fact 结算（effects → CURRENT / SUPERSEDED）
story_tick actual 推进（该段 duration_ticks）
（V3-7 起）actor memory / belief 增量
```

**reader_exposure 不在本提交内（评审 #2 解耦）**：passage commit ≠ 用户已看见；exposure 需要独立的 delivered/rendered 记录或保守 estimate（RA §14 的 certainty 家族），绝不与提交同事务充当 reader knowledge。

**V3-5 落法（开工裁决 `DEC-OPI-be7b094f-…32`）**：`segment_commit`（#1 lineage 面）随本提交同批落行——`commit_id` 由 segment_key 派生、携带 `actual_start_tick`/`actual_end_tick`/`event_id`/`passage_id`；**`SCENE COMMIT` = 场的最后一段 SEGMENT COMMIT 的别名**：`is_last_segment` 的 SEGMENT COMMIT 同事务翻转 `world_scene` `ACTIVE → COMMITTED`；章的 `opened_at_tick` 由本链正式管线化（首段提交事务内读 `world.current_tick`，章 PLANNED→ACTIVE 同批补章）——**lifecycle tick authority（评审 #3）自 V3-5 起由提交事务接管，不再由调用方代书**。

**V3-5R 落法（开工裁决 `DEC-OPI-dc1bafdf-…11`）**：① **场景 actual 区间 = 本事务唯一写权**——fresh 段提交的同一事务内，一个 UPDATE（store 无事务臂 `_advance_scene_actual_span_tx`）写 `actual_start_tick = COALESCE(actual_start_tick, 段 actual_start)`、`actual_end_tick = 段 actual_end`、`is_last` 时 `status='COMMITTED'`（**一次版本推进**；SCENE COMMIT 仍不是第三个事务）；replay 不改 span。② **顺序律**：fresh 段严格 `segment_seq == max(committed_seq) + 1`（首段必须 1；0 / 负数 / 跳号 / 倒序 ⇒ `VALIDATION_FAILED` 点名 given 与 expected；replay arm 先行——已存 key 的重放不受本律约束）。③ **terminality**：`segment_commit.is_last_segment`（migration 0034）持久化该段的 SCENE COMMIT 身份；replay 形状比对含之（同 segment_key 不同 `is_last_segment` ⇒ `CONFLICT`）。

**V3-6R 落法（开工裁决 `DEC-OPI-dc1bafdf-…31`）**：**`outcome_ref` 臂**——`PovWriter.write_segment(..., outcome_ref)` 直通本提交：ref 存在 ⇒ 必须指向真实 **COMMITTED** `user_action`（缺失 `NOT_FOUND` / 非 COMMITTED `VALIDATION_FAILED`）且其 gate 的 `scene_id` 属于本段 scene；`narrative_passage.outcome_ref` 落 `user_action_id`；**同一事务**将该 gate `COMMITTED → CLOSED`（§22 互锁句的 V3-6R 显式形）；**强制律**：场存在 `COMMITTED` 未 `CLOSED` gate ⇒ 本 fresh 段必须携带其 action 的 `outcome_ref`（缺/异 `VALIDATION_FAILED`）；replay 形状比对含 `outcome_ref`。span 臂本体不变（NCP-2 与 NCP-3 各自事务调用同一臂——§26 两臂律）。

幂等键：`segment_key = (scene_id, segment_seq)`；passage 与 event 的 id 由 segment_key 派生（重放写同一批 id）。

```text
commit 前崩溃 → 未发生；重跑该段（重生成正文，只提交一次）
commit 中崩溃 → 事务全或无；重启后回到「最后已提交段」续跑
commit 后崩溃 → 同 segment_key 重放 = 幂等 no-op（不产生第二行、不重复推进 tick）
```

### ACTION OUTCOME COMMIT

原子组（一个短事务；全或无）：

```text
user_action（裁定终态：interpretation / outcome / actual_action / consequences）
world_event（用户行为事实行；participants 含用户角色）
world_state_fact 结算（state_effects）
story_tick actual 推进（行为时长）
（V3-7 起）actor memory / belief 增量
replan 记录（replan_scope = NONE | SCENE | CHAPTER）
```

幂等键：`action_commit_key = (gate_id, submission_id)`（submission_id 在 `ANSWERED` 时 durable，源自输入去重链）。

```text
ANSWERED 后、COMMITTED 前崩溃 → recovery 以同一 submission_id 重新裁定（只此一次终态）
COMMITTED 后重放            → 幂等 no-op；呈现层从 durable 状态重读
```

**V3-6 落法（开工裁决 `DEC-OPI-dc1bafdf-…5`；重放行修订 `…21`）**：`commit_action`（`elc/world/action.py`）一个 `BEGIN IMMEDIATE`…`COMMIT` 落全臂——① `user_action` 终态八列（`interpretation` / `outcome` / `actual_action` / `consequences` / `state_effects` / `participants` / `replan_scope` / `actual_tick`=推进后 `actual_end`）；② `world_event` 行为事实行（id 派生 `f"ac:{gate_id}:{submission_id}:event"`，`kind='action'`，participants 含用户角色，effects=裁定 `state_effects`）；③ `world_state_fact` 结算（`_settle_effects_in_transaction` 一真源）；④ `world.current_tick` 推进（`duration_ticks ≥ 0`；`actual_start`=事务内推进前读）；⑤ `segment_commit` 行（`kind='ACTION_OUTCOME'`，`commit_id=f"ac:{gate_id}:{submission_id}"`，`action_id` 载、`passage_id`/`segment_seq` 空、**`is_last_segment`=0（门面不翻场）**）；⑥ gate `(ANSWERED|RESOLVING) → COMMITTED`；⑦ 章若仍 `PLANNED` ⇒ 同事务 `PLANNED→ACTIVE` 且 `opened_at_tick=actual_start`（#3 同 commit_segment 律——首段或首次行动裁定开启章）。幂等：同 `action_commit_key=(gate_id, submission_id)` 形状同重放 = 全组 no-op；形状异 `CONFLICT`（形状比对含语义载荷——裁定四文本/effects/participants/replan_scope/duration；簿记戳不比——SEGMENT COMMIT 同律）。**`replan_scope ≠ NONE` 的计划面消费不在本事务**：SCENE ⇒ `ScenePlanner.replan_scene`（新 dossier revision=max+1，PROPOSED→ADOPT 由 store 面同短事务 supersede）；CHAPTER ⇒ `Director.revise_blueprint`（现役 V3-4 面，语义不改）。

**V3-6R 落法（开工裁决 `DEC-OPI-dc1bafdf-…31`）**：⑧ **义务出生**——`replan_scope ≠ NONE` ⇒ 同事务建 `action_replan` `PENDING` 行（`replan_request_id = f"rp:{gate_id}:{submission_id}"`；`NONE` ⇒ 零行）；**消费协议改为 claim → work → complete**：`ScenePlanner.replan_scene(replan_request_id, …)`（SCENE）/ `Director.apply_action_replan(replan_request_id, …)`（CHAPTER）——`APPLIED` 重试零写返回 `target_ref`；`PENDING` 先写 `target_ref`（claim）再执行，崩溃重试收敛**同一 revision**、零第二次计划变更。**场 span 臂**：`advance_scene_actual_span_tx(..., close_scene=False)`——扩展场 actual 区间、不关场（§26 两臂律）。`status` 仅自 `RESOLVING` 入 `COMMITTED`（§23 V3-6R 收紧①）。

### 两条提交的共同纪律

- 每个 commit 各自全或无；正文与其**本段新产生的非用户事实**同批提交（零撕裂）。
- **两级不同事务（评审 #5 澄清）**：用户行为先经 ACTION OUTCOME COMMIT 成为 canon 事实；POV Writer **随后引用该已 committed 的 outcome** 生成 prose，再由 SEGMENT COMMIT 落正文及其新产生的非用户事实——**两者不是同一事务**（不存在「行为事实与正文同批」）。
- POV Writer 的呈现引用**已 committed** 的 outcome/passage；正文不得重新裁定用户行为（N-INV-002）。
- **SCENE COMMIT 不是第三种事务**（见 §22：它是场的最后一段 SEGMENT COMMIT 的别名，翻转与提交同事务）。
- Chapter Settlement **不是**提交事务（只压缩 / 收束；不新增事实）。

## 26. story_tick Rules（Narrative V3）

```text
数据层：整数 tick，world-local；World Calendar 解释显示（MVP：1 tick = 1 分钟）
planned_*_tick：Plan 面（Director / Scene Planner 写）
actual_*_tick：Canon 面（只由 SEGMENT / ACTION OUTCOME COMMIT 写；单调不减）
```

规则：

- `actual_start_tick` = 推进行为前的 world tick；`actual_end_tick` = 加 `duration_ticks` 后的 world tick（`duration_ticks >= 0`）。
- 同一世界 actual 区间非递减；跨章继续；章/场的 actual 区间由 commit 决定（可与 planned 不同——用户行为可改变时间进程）。
- **场 actual 区间的写者 = 两个提交事务的共同臂（V3-5R 立、V3-6R 泛化，`DEC-OPI-dc1bafdf-…31`）**：`world_scene.actual_start_tick` / `actual_end_tick` 只由提交事务经同一无事务臂 `advance_scene_actual_span_tx(scene_id, actual_start, actual_end, close_scene, …)` 写——NCP-2（ACTION OUTCOME）扩展 span、`close_scene=False`（不关场）；NCP-3（SEGMENT）扩展 span、`close_scene=is_last_segment` 时才随 `ACTIVE → COMMITTED` 翻转；首写 `actual_start_tick` 用 COALESCE 保首值；各自事务内**一次版本推进**；`commit_scene` 显式面不写 span；replay 零重改。
- 排序与因果读 actual；显示由 Calendar 把 tick 解释成世界日期（不依赖地球公历）。
- 章规划中的时间只写 planned；不得预写 actual。

## 27. Invalid Narrative Transitions（V3）

以下直接拒绝：

```text
未 commit 的 Plan 内容作为事实读取
CLOSED chapter / scene 重新 ACTIVE
有已 commit 段落的 scene → DISCARDED
同一 gate 二次 submission 重新裁定（应按幂等键去重）
COMMITTED 之后 gate 回退
一个世界并行两个 ACTIVE 章（MVP）
writer 写入与已 committed outcome 冲突的同一 event / effects（N-INV-002）
actual tick 回退，或非提交事务写 actual tick
```
