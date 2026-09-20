# BF-03 · Teaching Gate Decision Specification v1.0

> 日期：2026-09-20  
> 状态：**GATE BEHAVIORAL BASELINE V1 — ENGINEERING FROZEN**  
> 前置：OQ-023A、OQ-024/024A、OQ-025/025A、BF-02A Planner Behavioral Baseline V1  
> 目标：把 Teaching Gate 收敛成一个窄、确定性、可审计的执行许可层。

---

## 1. Gate 只回答一个问题

> **Planner / Teaching Controller 已经提出一个教学动作，现在是否允许执行？**

Gate 不回答：

```text
哪个 target 更值得教
用户掌握程度如何
课程价值多大
CoverageDebt 多高
该用什么提示
Persona 应该怎么说
```

这些分别属于：

```text
Learning
Planner
Teaching Planner
Persona Runtime
```

---

## 2. Planner 与 Gate 的唯一分工

```text
Planner
= worth teaching?

Gate
= may execute now?
```

Gate **不得重新计算**：

```text
learning_need
curriculum_value
goal_relevance
schedule_urgency
coverage_debt
planner utility
candidate ranking
```

因此：

```text
Gate DENY
```

不能触发 Planner 在同一 turn 轮流试第二候选来绕过 Gate。

---

## 3. Gate contexts

### OPEN

创建新的 TeachingMoment 前的授权。

来源：

```text
AUTOMATIC
USER_INITIATED
```

必须已有：

```text
PlannerExecutionStatus = SUCCEEDED
PlannerDecision = SELECT
```

Gate ALLOW 仍不等于 Moment 已经创建；Runtime 必须在 CP2 原子取得 TeachingLock 并创建 Moment。

### AUTO_CONTINUE

已有 TeachingMoment 内，由系统决定继续：

```text
HINT
RETRY
EXPLANATION
REVEAL
TERMINAL_FEEDBACK
```

### USER_REQUESTED_CONTINUE

用户明确说：

```text
再试一次
给我提示
直接告诉我
解释一下
```

仍属于当前 Moment，不创建新 target。

---

## 4. Gate output

### 正常

```text
GateExecutionStatus = SUCCEEDED

GateDecision =
  ALLOW
  or
  DENY
```

DENY 输出：

```text
primary_reason
reasons[]
```

### 关键状态未知

如果以下关键状态无法确定：

```text
DecisionCycle
subject lineage
target/content validity
safety/privacy
TeachingLock
gate state completeness
```

则：

```text
GateExecutionStatus = DEGRADED
GateDecision = none
```

不能把：

```text
UNKNOWN
```

伪装成：

```text
DENY
```

也不能冒险 ALLOW。

---

## 5. Decision order

Gate 固定按以下语义检查：

```text
critical-state completeness
→ safety/privacy
→ action/selection lineage
→ DecisionCycle validity
→ target/content validity
→ suppression
→ latest user intent
→ automatic-teaching preference
→ lock/lifecycle
→ automatic flow protection
→ automatic opening budget/cooldown
→ continuation hard caps
→ ALLOW
```

它不是 utility pipeline。

---

## 6. Safety / Privacy

如果可信 Safety/Privacy view：

```text
BLOCK
```

所有 context：

```text
DENY
```

显式用户请求不能绕过。

如果：

```text
UNKNOWN
```

Gate：

```text
DEGRADED
```

BF-05 将进一步冻结 Safety/Privacy contract；BF-03 只冻结 Gate 的消费语义。

---

## 7. Action / Selection lineage

Gate 拒绝：

```text
CANCELLED
SUPERSEDED
```

OPEN 中 subject 是 Planner-selected candidate lineage。

Continuation 中 subject 是当前 proposed teaching action lineage。

Late/superseded action 不得重新产生副作用。

---

## 8. DecisionCycle

```text
VALID
→ 可继续判断

INVALIDATED / STALE
→ DENY: DECISION_CYCLE_INVALID

UNKNOWN
→ DEGRADED
```

Gate 不自行重新 Planner。

---

## 9. Target / Content validity

```text
target INVALID / DEPRECATED / MISSING
→ DENY TARGET_INVALID

content INVALID
→ DENY CONTENT_INVALID

unknown validity
→ DEGRADED
```

---

## 10. Suppression

只要当前 authoritative constraint 仍然：

```text
target_suppressed = true
```

所有 context 都：

```text
DENY
```

即使用户显式请求同一 target，也应先由 User Constraint / Intent 层完成：

```text
re-enable / clear suppression
```

Gate 不偷偷修改用户约束。

---

## 11. Latest UserIntent revalidation

### Automatic OPEN

必须仍然：

```text
OPEN
```

如果用户已经切：

```text
JUST_CHAT
NON_LEARNING_TASK
LEARNING_REQUEST
...
```

旧 automatic opening：

```text
DENY USER_INTENT_BLOCK
```

### User-initiated OPEN

最新 intent 必须仍然：

```text
LEARNING_REQUEST
TARGETED_LEARNING_REQUEST
```

### Continuation

必须：

```text
ACTIVE_TEACHING_CONTINUATION
```

Topic shift / just-chat / unrelated task：

```text
DENY USER_INTENT_BLOCK
```

---

## 12. User request vs conversation protection

BF-03 构建决策表时确认：

> `hard_protected_flow` 是防止**自动教学打断对话**的保护，不是对最新显式学习请求的否决权。

因此：

```text
automatic OPEN
AUTO_CONTINUE
+
hard_protected_flow
→ DENY
```

而：

```text
USER_INITIATED OPEN
USER_REQUESTED_CONTINUE
```

可绕过纯 conversation-flow protection。

真正不可绕过的是：

```text
safety/privacy
active suppression
invalid target/content
lock/lifecycle conflict
hard teaching limits
```

如果存在真正系统级不可执行状态，应通过 Runtime/Safety block 表达，而不是滥用 `hard_protected_flow`。

---

## 13. Automatic teaching preference

```text
automatic_teaching_enabled = false
```

阻止：

```text
automatic OPEN
AUTO_CONTINUE of AUTO_OPENED moment
```

不阻止：

```text
USER_INITIATED OPEN
USER_REQUESTED_CONTINUE
```

如果 Moment 原本就是：

```text
USER_AUTHORIZED
```

其正常内部 auto continuation 也不被全局“禁止自动插课”设置误杀。

---

## 14. TeachingLock

### OPEN

观察到任何现存 teaching lock：

```text
DENY TEACHING_LOCK_CONFLICT
```

### Continuation

必须：

```text
lock_state = OWNED_BY_THIS_MOMENT
```

否则：

```text
OWNED_BY_OTHER
→ TEACHING_LOCK_CONFLICT

NONE
→ TEACHING_LOCK_INVALID

UNKNOWN
→ DEGRADED
```

注意：

> Gate ALLOW 不等于锁已预留。

OPEN 后真正的 lock acquire + Moment create 仍必须由 Runtime 在 CP2 原子完成。若竞态导致 acquire 失败，不得打开 Moment，也不得绕 Gate 选第二 target。

---

## 15. TeachingMoment lifecycle

Continuation 只有在：

```text
moment_state = DECIDING_NEXT_ACTION
```

才允许执行下一教学动作。

其它状态：

```text
DENY MOMENT_NOT_CONTINUABLE
```

Persona Resume 不再持有 TeachingLock，也不属于 continuation Gate。

---

## 16. Automatic session budget

```text
automatic_session_budget_exhausted
```

只阻止：

```text
new AUTOMATIC OPEN
```

它不应在 Moment 已经打开后突然杀死当前教学 episode。

用户主动发起的新教学请求也不受 automatic session budget 限制。

---

## 17. Hard opening cooldown

同样只针对：

```text
new AUTOMATIC OPEN
```

不阻止：

```text
user-initiated OPEN
active Moment continuation
```

---

## 18. Hard attempt limit

当：

```text
hard_attempt_limit_exhausted = true
```

禁止继续：

```text
RETRY
HINT
```

因为它们会制造下一次 attempt loop。

仍允许：

```text
EXPLANATION
REVEAL
TERMINAL_FEEDBACK
```

前提是其它规则允许。

用户说：

```text
“直接告诉我答案”
```

不会因为“已经不能再重试”而被错误拒绝。

---

## 19. Hard teaching-turn limit

当 Moment 达到 hard turn cap：

```text
nonterminal continuation
→ DENY
```

但必须保留一个 clean-exit path：

```text
REVEAL
TERMINAL_FEEDBACK
or terminalizing_action=true
→ may ALLOW
```

这样 hard cap 的含义是：

> 不再延长教学循环。

而不是：

> 系统连收尾都不能做。

---

## 20. User-requested continuation

显式用户继续请求可以绕过：

```text
auto-teach preference
automatic opening budget
automatic opening cooldown
conversation-flow protection
```

不能绕过：

```text
safety/privacy
active suppression
target/content invalidity
DecisionCycle invalidity
TeachingLock mismatch
Moment lifecycle
hard attempt/turn limits
```

---

## 21. Contract error vs DENY vs DEGRADED

### Contract Error

调用 Gate 本身违反接口：

```text
OPEN without Planner SELECT
OPEN with non-OPENING action
Continuation without moment_id
USER_REQUESTED_CONTINUE without explicit request
invalid enum
```

这是程序错误，不是 GateDecision。

### DENY

输入完整且事实已知，但明确不允许执行。

### DEGRADED

执行所需关键事实未知/不完整。

三者不得混淆。

---

## 22. Stable deny reasons

Gate 返回所有命中的硬阻断，并使用固定 primary precedence：

```text
SAFETY_PRIVACY_BLOCK
ACTION_CANCELLED
ACTION_SUPERSEDED
DECISION_CYCLE_INVALID
TARGET_INVALID
CONTENT_INVALID
TARGET_SUPPRESSED
USER_INTENT_BLOCK
AUTO_TEACH_DISABLED
TEACHING_LOCK_CONFLICT
TEACHING_LOCK_INVALID
MOMENT_NOT_CONTINUABLE
HARD_PROTECTED_FLOW
AUTO_SESSION_BUDGET_EXHAUSTED
HARD_COOLDOWN_ACTIVE
HARD_ATTEMPT_LIMIT
HARD_TEACHING_TURN_LIMIT
```

这样 trace 不依赖代码 if 顺序偶然变化。

---

## 23. Gate 和 PreDeliveryGuard

Gate 在：

```text
Planner selection
→ TeachingMoment/action authorization
```

阶段运行。

之后仍可能发生：

```text
user changes intent
action cancelled
suppression changes
lock changes
```

所以真正 delivery 前：

```text
PreDeliveryGuard
```

仍负责最后一次 hard invalidation。

它不是 Gate 的重复 ranking，而是时间推进后的重新验证。

---

## 24. Gate 不读取 Planner utility

Reference Gate API 中不存在：

```text
learning_need
goal_relevance
coverage_debt
planner utility
```

即使调用方附带这些多余字段，也不影响 ALLOW/DENY。

因此 Gate 无法演变成第二个 Planner。

---

## 25. Benchmark

BF-03 决策表共覆盖：

```text
60 Gate cases
```

包括：

```text
automatic opening
user-initiated opening
auto continuation
user-requested continuation
JUST_CHAT
auto-teach disable
budget/cooldown
flow protection
suppression
DecisionCycle invalidation
target/content invalidation
lock conflicts
Moment lifecycle
attempt/turn caps
terminal reveal
safety/privacy
unknown/degraded state
multiple blockers
contract errors
Planner/Gate no-rerank boundary
```

结果：

```text
60 / 60 PASS
```

---

## 26. Metamorphic properties

另外验证：

```text
safety monotonicity
suppression across contexts
user request bypasses only automatic controls
budget applies only to opening
cooldown applies only to opening
flow protection preserves user agency
attempt cap is action-sensitive
turn cap retains terminal escape
unknown critical state degrades
Gate ignores pedagogy factors
deny reason order deterministic
lock ownership mandatory
latest user intent revalidated
terminalizing action semantics
```

结果：

```text
14 / 14 PASS
```

---

## 27. Current baseline

最终：

```text
Gate benchmark       60/60
Metamorphic          14/14
---------------------------
Total                74/74 PASS
```

Teaching Gate 当前升级为：

```text
GATE BEHAVIORAL BASELINE V1
```

与 BF-01A / BF-02A 一样：

```text
engineering semantics frozen
policy numbers / hard-cap values calibratable
```

具体：

```text
hard attempt limit = 几次
hard turn limit = 几轮
cooldown = 多久
automatic budget = 多少
```

不在 BF-03 固定为科学常数；但它们的**作用范围和绕过规则**已经冻结。
