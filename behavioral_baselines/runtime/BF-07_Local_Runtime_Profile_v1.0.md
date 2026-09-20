# BF-07 · Local Runtime Profile v1.0

> 日期：2026-09-20  
> 状态：**LOCAL RUNTIME BASELINE V1**  
> 前置：Canonical RC2、BF-01A～BF-06  
> 目的：为 local-first V1 冻结一个足够可靠、但不过度分布式化的物理运行时实现 profile。

---

## 1. 核心原则

保留：

```text
TurnTransaction = coordination saga + short ACID commits + external actions
one user-visible coordinator per conversation
one active teaching focus per conversation
retry action, not whole turn
external at-least-once / uncertain
internal exactly-once canonicalization
partial delivery != full delivery
post-turn projections do not own transcript truth
crash recovery resumes checkpoint/action
```

但 V1 不要求：

```text
Redis
Kafka
distributed lease service
heartbeat daemon
leader election
multi-worker orchestration
distributed transaction coordinator
always-on recovery worker
```

一句话：

> **冻结 runtime invariant，不冻结分布式基础设施。**

---

## 2. V1 Process Model

```text
single device
single application process
single mutable SQLite database
external model provider(s)
optional local web/UI client
```

允许内部异步任务，但不允许两个独立 worker 同时拥有同一 conversation 的 user-visible execution authority。

未来 cloud/multi-process 版本可以替换协调实现，但不得改变上层 Runtime contract。

---

## 3. Physical Storage Topology

### app.db

V1 推荐把所有需要短事务原子的**可变用户/运行时状态**放入同一个 SQLite 数据库：

```text
Conversation
UserProfile
Relationship
Learning
Goal / Policy
Scheduler
Planner trace
Teaching
Runtime actions
Delivery
Projection jobs
Deletion/provenance metadata
```

理由不是“所有 Domain 共用 Authority”，而是：

> Domain Authority 可以逻辑隔离，短事务原子性却需要物理共址。

特别是：

```text
GateDecision(ALLOW)
+ TeachingMoment
+ TeachingLock
+ first GenerationAction
```

必须能在 CP2 用一个 SQLite transaction 提交。

### content.db

继续作为：

```text
read-only versioned release artifact
```

不混入用户可变状态。

### SecretStore

API keys/tokens：

```text
OS / platform secret store
```

`app.db` 只保存：

```text
secret_ref
```

不得保存 secret value。

---

## 4. SQLite Profile

Reference：

```text
journal_mode = WAL
foreign_keys = ON
busy_timeout ≈ bounded local value
synchronous = NORMAL reference default
```

具体 timeout/synchronous 可按平台调整。

Normative：

```text
foreign keys on
short transactions
no provider/network call inside SQL transaction
atomic groups really atomic
```

---

## 5. ConversationCoordinatorLease — Local Mapping

Canonical 名称：

```text
ConversationCoordinatorLease
```

保留作为逻辑 contract。

Local Profile 不实现真正的 distributed lease service。

物理实现：

```text
per-conversation in-process keyed mutex
+
runtime_epoch crash fencing
+
durable TurnRecord / Action state
```

### 为什么够

单进程存活时：

```text
keyed mutex
→ same conversation only one visible coordinator
```

进程崩溃后：

```text
mutex automatically disappears
→ new startup runtime_epoch
→ durable nonterminal state is recovery source
```

因此不需要：

```text
lease TTL
heartbeat renewal
lease reaper service
```

---

## 6. runtime_epoch

每次 app process 启动：

```text
runtime_epoch += 1
```

durable work 可以记录：

```text
owner_epoch
```

启动后：

```text
owner_epoch < current_epoch
+
nonterminal state
→ abandoned/crashed work candidate
```

这不是分布式 fencing token 的完整替代品。

它是：

> 单设备、单活动进程 profile 下的 crash ownership boundary。

如果未来允许多个进程同时工作，必须升级协调 profile。

---

## 7. Input Ingestion 与 Coordinator 分离

新用户输入入口不能要求先获得当前 conversation mutex。

否则：

```text
old assistant streaming
→ old coordinator owns mutex
→ new user input cannot even request interruption
```

Local Profile：

```text
InputEnvelope
→ durable / dedupe first

if active turn:
  write InterruptRequest

current coordinator
→ observe cancel/supersede
→ canonicalize old partial result
→ terminalize old turn
→ release guard
→ handoff new input
```

所以：

```text
ingestion may occur outside coordinator guard
user-visible generation may not
```

---

## 8. Barge-in

Local V1 使用：

```text
in-process cancellation token / AbortController equivalent
+
durable InterruptRequest
```

不需要 distributed cancellation bus。

顺序：

```text
new InputEnvelope durable
→ InterruptRequest durable
→ cancel provider/stream if possible
→ mark old action superseded/cancelled
→ canonicalize actual delivered prefix
→ old turn terminal
→ release conversation guard
→ next turn acquires guard
```

两个 assistant stream 不得并发对用户可见。

---

## 9. TeachingLockLease — Local Mapping

TeachingLock 比 ConversationCoordinator 更需要 durable state，因为它属于 Teaching domain truth：

```text
same conversation
→ at most one active TeachingMoment
```

Local Profile 使用：

```text
active_teaching_lock
  conversation_id UNIQUE/PK
  moment_id UNIQUE
  state_version
```

不使用：

```text
TTL
heartbeat
```

Moment terminalization：

```text
TeachingMoment → TEACHING_TERMINAL
+
delete/release active_teaching_lock
```

必须在一个短事务中完成。

---

## 10. CP0

一个 transaction：

```text
TurnRecord
+
UserTurn
```

InputEnvelope 已先 durable/dedupe。

失败：

```text
both commit
or neither commit
```

---

## 11. CP1

Learning Evidence 仍按 Learning Domain transaction 提交。

如果 app.db 共址，不代表 Orchestrator 可以越过 Learning interface 直接改表。

物理共库：

```text
!= authority merge
```

---

## 12. CP2

Teaching opening 必须一个 transaction：

```text
GateDecision(ALLOW)
TeachingMoment
active TeachingLock
first GenerationAction
TurnRecord checkpoint
```

BF-07 reference integration test 对 transaction 中每一个中间点注入 failure，并要求：

```text
all rollback
```

不能留下：

```text
Moment without Lock
Lock without Action
Gate ALLOW without valid opening state
```

---

## 13. Provider Calls

严格：

```text
commit durable action intent
→ leave DB transaction
→ provider call
```

Reference runtime 如果发现：

```text
connection.in_transaction == true
```

时发 provider call：

```text
RuntimeInvariantError
```

---

## 14. Provider Attempts

一个稳定：

```text
GenerationAction.action_id
```

可以有多个：

```text
ProviderAttempt
```

Retry：

```text
same action_id
new attempt_id
ordinal + 1
```

禁止：

```text
retry whole Turn
new TeachingMoment for provider retry
new PlannerDecision for transport retry
```

---

## 15. External exactly-once 不承诺

Provider：

```text
at-least-once / uncertain
```

所以可能：

```text
request sent
timeout
provider actually generated
retry
late old result arrives
```

Local runtime 必须做到：

```text
at most one accepted ProviderAttempt per GenerationAction
```

Late callback 如果 action 已：

```text
CANCELLED
SUPERSEDED
TERMINAL
```

只能：

```text
ignore / audit
```

不得产生新的 canonical assistant side effect。

---

## 16. Canonical exactly-once

Internal canonicalization 使用：

```text
stable primary keys
unique(action_id)
unique(turn_id)
unique(input_id)
CAS/state_version where needed
```

例如重复 delivery callback：

```text
AssistantTurn canonicalized once
```

不是依赖“回调应该只来一次”。

---

## 17. ClientRenderAck

仍然是：

```text
async refinement
```

可以在 Turn 已：

```text
COMPLETED
```

之后到达。

它：

```text
refines exposure certainty
```

不：

```text
reopen turn
re-run planner
automatically upgrade committed learning evidence
```

---

## 18. CP4 Projection

Projection 使用 durable job record：

```text
projection_id
source_turn_id
projection_type
source_version
state
```

执行时：

```text
ConversationCoordinatorGuard must already be released
```

Projection pending/failed：

```text
must not block next user-visible turn
```

Local V1 不要求后台 daemon。

允许：

```text
after-turn in-process task
idle-time drain
startup recovery drain
before-app-close bounded drain
```

---

## 19. Recovery Worker 在 Local Profile 中不是 Service

Canonical 里的：

```text
Recovery Worker
```

在 Local V1 是一个逻辑组件。

物理上：

```text
startup recovery scan
+
opportunistic recovery before opening a conversation
```

即可。

不要求：

```text
always-on background process
heartbeat monitor
cron service
```

---

## 20. Recovery Checkpoints

### old CP0

```text
RESUME_ANALYSIS
```

### old CP1

```text
RESUME_DECISION
```

### old CP2

```text
RESUME_ACTION_BY_STABLE_ACTION_ID
```

不能：

```text
new Moment
new action id
whole-turn replay
```

### CP3 uncertainty

```text
CONSERVATIVE_DELIVERY_RECONCILIATION
```

若无法证明“没发送”：

```text
do not blindly replay
```

---

## 21. Recovery of Teaching Lock

启动扫描：

```text
active_teaching_lock
JOIN TeachingMoment
```

如果：

```text
Moment = TEACHING_TERMINAL
+
lock remains
→ RELEASE_ORPHAN_LOCK
```

如果 Moment nonterminal：

```text
REVALIDATE_ACTIVE_MOMENT
```

不是：

```text
blindly resume prompt generation
```

先检查：

```text
Moment state
target/content validity
Gate authorization lineage
action state
delivery state
```

---

## 22. BUFFERED first

Phase 1 推荐：

```text
BUFFERED_VALIDATED
```

优先打通正确性。

普通 Persona `GUARDED_STREAM` 可以后加。

Teaching action 保持：

```text
BUFFERED_VALIDATED
```

优先级更高。

这不是永久禁止 streaming，而是降低第一条 vertical slice 的并发复杂度。

---

## 23. Local Projection Queue

不引入：

```text
Celery
RabbitMQ
Kafka
Redis queue
```

V1：

```text
projection_job table
+
in-process executor
```

进程退出后 pending row 仍在；下次启动继续。

---

## 24. What V1 Explicitly Does Not Build

```text
distributed coordinator lease
distributed TeachingLock service
lease heartbeat renewal
leader election
Redis lock
Kafka event bus
multi-worker routing
cross-node recovery
distributed saga coordinator
two-phase commit
always-on scheduler daemon
automatic cross-device state sync
```

这些不是“架构被删除”。

它们是：

```text
not required by LOCAL_RUNTIME_PROFILE_V1
```

---

## 25. Cloud Upgrade Boundary

未来需要：

```text
multiple app processes
server cluster
cross-device real-time sync
background always-on jobs
```

时，可以替换：

```text
ConversationCoordinator implementation
TeachingLock implementation
Projection executor
Recovery executor
```

但以下 contract 不变：

```text
stable action IDs
short commits
no provider in DB tx
one visible conversation coordinator
one active teaching focus
action-level retry
exactly-once canonical state
checkpoint recovery
CP4 nonblocking
```

---

## 26. Implementation consequence

因此 Repository Bootstrap 不应该一上来安装：

```text
Redis
Kafka
distributed lock SDK
workflow engine
```

第一版只需要：

```text
SQLite
domain repositories
transaction boundary helpers
keyed async mutex
cancellation token
startup recovery scanner
durable action/projection tables
```

---

## 27. Reference Integration Checks

BF-07 运行 SQLite-backed integration/contract checks：

```text
43 / 43 PASS
```

覆盖：

```text
Input dedupe
interrupt outside coordinator
coordinator serialization
CP0 atomicity
CP2 injected rollback at every intermediate stage
TeachingLock uniqueness
terminal lock release
action-level retry
one accepted provider result
late-result suppression
duplicate delivery canonicalization
async ClientRenderAck
CP4 after guard release
barge-in handoff
runtime_epoch recovery
projection recovery
orphan lock recovery
no heartbeat/TTL
no distributed coordinator table
no whole-turn replay
stable action retry
terminal turn not recovered
pending projection nonblocking
```

---

## 28. Local Runtime Invariants

```text
LR-INV-001
app.db contains mutable state needed for short atomic groups.

LR-INV-002
content.db remains read-only release data.

LR-INV-003
secret values never enter app.db.

LR-INV-004
one in-process conversation guard owns user-visible execution.

LR-INV-005
input ingestion/interrupt recording may occur without owning that guard.

LR-INV-006
TeachingLock is durable and unique per conversation.

LR-INV-007
Local V1 uses no heartbeat or TTL to infer process death.

LR-INV-008
runtime_epoch + durable state defines restart recovery ownership.

LR-INV-009
external provider calls never run inside SQLite transaction.

LR-INV-010
retries create ProviderAttempts, not new Turns.

LR-INV-011
one GenerationAction accepts at most one provider result.

LR-INV-012
late cancelled/superseded results cannot create canonical output.

LR-INV-013
duplicate callbacks cannot duplicate canonical AssistantTurn.

LR-INV-014
CP4 projection execution does not hold the conversation coordinator.

LR-INV-015
pending projection does not block the next turn.

LR-INV-016
ClientRenderAck may refine terminal delivery state asynchronously.

LR-INV-017
startup recovery resumes checkpoint/action, never whole user turn.

LR-INV-018
uncertain delivery is reconciled conservatively, not blindly replayed.

LR-INV-019
terminal turns are not recovered.

LR-INV-020
physical simplification must never change domain authority.
```

---

## 29. Current Verdict

External review concern:

> “local-first V1 risks implementing a distributed backend before validating the learning loop.”

BF-07 closes this concern.

Final status:

```text
LOCAL RUNTIME BASELINE V1
```

The V1 runtime is deliberately boring:

```text
one process
one mutable SQLite DB
one read-only content DB
one OS secret store
in-process conversation mutex
durable TeachingLock row
startup recovery
action-level idempotency
```

That is enough to preserve the frozen runtime semantics for the first real product slice.
