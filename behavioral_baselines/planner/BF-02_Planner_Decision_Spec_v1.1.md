# BF-02 · Planner Decision Specification v1.1

> 日期：2026-09-20  
> 状态：**PLANNER BEHAVIORAL BASELINE V1 — ENGINEERING FROZEN / NUMERICALLY CALIBRATABLE**  
> 前置：BF-02 v1.0、BF-02A Behavioral Stress Test、BF-01A Estimator Behavioral Baseline V1  
> 目标：规定 `canonical learning candidates → PlannerDecision` 的 V1 可执行行为。

---

## 1. 冻结范围

v1.1 冻结：

```text
candidate canonicalization boundary
UserIntentScope semantics
hard eligibility order
content/prerequisite rules
communicative-impact factor
feature-assembly degradation semantics
explicit-request priority
utility topology
coverage-starvation safeguard
activation-before-tie
Pareto dominance
deterministic tie-break
NO_TARGET semantics
Planner/Gate authority boundary
```

数值权重、threshold、normalization band 数字仍允许 empirical calibration，但必须版本化并回归。

---

## 2. Planner 只判断 worth teaching

Planner：

```text
which candidate is worth proposing now?
```

Gate：

```text
may the selected action execute now?
```

Planner 不拥有：

```text
Learning truth
ReviewDue truth
Teaching authorization
TeachingMoment lifecycle
Persona wording
```

Gate 不重新计算：

```text
learning_need
curriculum_value
goal_relevance
coverage_debt
```

---

## 3. Candidate pipeline

固定顺序：

```text
Generator CandidateProposal[]
→ canonicalize / merge
→ authoritative feature assembly
→ planning-context validity check
→ hard eligibility
→ policy utility
→ coverage-service adjustment
→ per-candidate activation
→ explicit-request priority scope
→ Pareto prune
→ near-tie window
→ deterministic tie-break
→ SELECT / NO_TARGET
```

---

## 4. Canonicalization

同一个：

```text
focus target
target mode
modality
learning intent
opportunity binding class
```

形成一个 `canonical_key`。

重复 generator proposal：

```text
origins union
user_initiated OR
request_aligned OR
request_priority = minimum explicit priority
initiative = most immediate lane
```

**最终 factor vector 不在 merge 时相加或取 max。**

Merge 后必须重新从 authoritative views 计算一次 factor vector，因此：

```text
origin count != utility bonus
```

Kernel 接收到重复 `canonical_key` 属于 input contract error。

---

## 5. Feature assembly completeness

Planner 不允许：

```text
missing Scheduler
→ schedule_urgency = 0
```

也不允许：

```text
stale LearningSnapshot
→ 假装仍有效
```

PlanningContext 至少包含：

```text
feature_assembly_status
snapshot_status
missing_authorities[]
natural_break_available
```

如果：

```text
feature_assembly_status != COMPLETE
or
snapshot_status != VALID
```

返回：

```text
PlannerExecutionStatus = DEGRADED
PlannerDecision = none
```

Runtime 才输出：

```text
DEGRADED_NO_AUTOMATIC_TEACHING
```

而不是伪造 `NO_TARGET`。

---

## 6. Benefit factors v1.1

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
communicative_impact
```

v1.0 遗漏的 `communicative_impact` 已恢复。

### Communicative impact

Reference band：

```text
NONE      0
LOW       .10
MEDIUM    .50
HIGH      .80
BLOCKING  1.00
```

它回答：

> 当前问题对用户正在表达的意思造成多大损害？

因此：

```text
wrong negation changing intended meaning
```

可以显著高于：

```text
minor article error
```

---

## 7. Cost factors

```text
interruption_cost
cognitive_load
overexposure
support_cost
user_resistance
```

Hard suppression 不编码为 `user_resistance=1`；它直接 hard-exclude。

---

## 8. Explicit request priority

多重 user request 不能最终退化为：

```text
candidate_id alphabetical order
```

UserIntentResolver 可输出：

```text
request_priority = 0,1,2...
```

只有在用户语义确实表达先后/主次时才区分。

规则：

```text
eligible user-initiated candidates exist
→ restrict to minimum request_priority
→ then utility/tie-break
```

如果多个请求同级：

```text
same request_priority
```

则正常 utility 决定。

---

## 9. Contradictory scope

以下组合属于上游契约错误：

```text
UserIntentScope = JUST_CHAT
+
user_initiated learning candidate
```

用户如果显式发起学习请求，本 DecisionCycle 的 UserIntentScope 应先变化为：

```text
LEARNING_REQUEST
or
TARGETED_LEARNING_REQUEST
```

Planner 不静默猜测哪一个 Authority 是对的。

---

## 10. Readiness 与 runtime-generated content

V1：

```text
PROBE                         R2+
user-initiated teaching       R3+
automatic general/review      R3+
automatic CURRENT_USER_ERROR  R4
```

`runtime_generated_ready` 仅允许作为：

```text
user-initiated
```

的 fallback/escape hatch。

它**不能**让：

```text
automatic CURRENT_USER_ERROR R1/R2/R3
```

绕过 R4，也不能让普通 proactive automatic target 绕过 R3。

---

## 11. Prerequisite scaffold contract

如果：

```text
READY_WITH_SCAFFOLD
or
UNKNOWN + prerequisite_scaffoldable
```

则 candidate 必须显式体现支架成本。

Reference minimum：

```text
support_cost >= .25
cognitive_load >= .20
```

这些是 reference numeric floors，可校准。

结构不变：

> scaffold 不能被当成“免费 prerequisite”。

---

## 12. Utility v1.1

Reference Benefit weights：

```text
learning_need           .17
uncertainty_reduction   .10
curriculum_value        .08
goal_relevance          .09
schedule_urgency        .08
context_fit             .13
personal_relevance      .08
transfer_value          .05
coverage_debt           .08
opportunity_expiry      .02
communicative_impact    .12
```

Cost：

```text
interruption_cost  .40
cognitive_load     .20
overexposure       .20
support_cost       .10
user_resistance    .10
```

Reference formula：

```text
Benefit = Σ(w_b × b)

Cost = Σ(w_c × c)

Utility =
  initiative_multiplier(policy) × Benefit
  - cost_multiplier(policy) × Cost
  + eligible coverage-service bonus
```

这些数字不是科学最终值。

---

## 13. Coverage debt starvation safeguard

v1.0 的 `coverage_debt=.025` reference weight 太弱，Balanced 模式下即使 debt 达最大值，也容易长期输给轻量 Reactive target。

这违背：

```text
CoverageDebt prevents starvation
```

v1.1 做两层修正：

1. reference `coverage_debt` weight 提高到 `.08`；
2. 当：

```text
coverage_service_state = CRITICAL
+
natural_break_available = true
+
policy ∈ {BALANCED, STUDY_FIRST}
```

可获得小的 versioned service bonus。

Reference：

```text
BALANCED    +.08
STUDY_FIRST +.10
LOUNGE       +0
```

Coverage service **仍不能突破**：

```text
TARGETED_LEARNING_REQUEST
JUST_CHAT
suppression
hard prerequisite
Gate hard protected state
```

因此它是 starvation safeguard，不是最高优先级命令。

---

## 14. Activation before tie-break

固定：

```text
score
→ service adjustment
→ per-candidate activation
→ active set
→ tie
```

未激活 candidate：

```text
never enters tie-break
```

Reference Balanced threshold v1.1：

```text
0.195
```

这是 profile calibration，不是架构常数。

---

## 15. Pareto dominance

BF-02A 发现 v1.0 在 near-tie 中可能因为最终 stable ID 选择一个**严格更差**的 candidate。

v1.1：

在相同：

```text
activation path
initiative class
request priority
coverage-service class
```

内，如果 A：

```text
all benefit factors >= B
all cost factors <= B
and at least one strict
```

则：

```text
B is Pareto dominated
→ remove before tie-break
```

这样 stable ID 只能解决真正无法区分的 candidate，不会战胜明显更好的方案。

---

## 16. Tie-break

对 activated + non-dominated 的 near-tie：

```text
1 request_aligned
2 user_initiated
3 REACTIVE > OPPORTUNISTIC > PROACTIVE
4 higher opportunity expiry
5 lower interruption cost
6 lower overexposure
7 lower cognitive load
8 stable candidate_id
```

Tie-break 仍然只是 near-tie 规则，不代替 utility。

---

## 17. Planner/Gate boundary stress result

BF-02A 明确保留：

```text
Planner may SELECT
even if a later Gate hard state will DENY
```

例如 Planning 时：

```text
interruption_cost = PROTECTED/high
```

但 target 价值极高，Study-first Planner 仍可能判断：

```text
worth teaching
```

真正的：

```text
hard protected-state prohibition
hard budget exhausted
TeachingLock conflict
new suppression
safety/privacy block
```

属于 Gate BF-03。

这防止 Planner/Gate 两边各维护一套 pedagogy ranking。

---

## 18. v1.0 stress failures

43 个新增 stress cases：

```text
v1.0 = 29/43 PASS
```

14 个失败集中于：

```text
multiple explicit request priority
communicative impact omission
Pareto near-tie failure
duplicate canonical identity
authority unavailable degradation
stale snapshot degradation
JUST_CHAT contradiction
runtime-generated automatic readiness bypass
missing scaffold cost
coverage debt starvation
low-impact error vs review
request-binding theft
missing-factor degradation
```

---

## 19. v1.1 results

```text
BF-02 initial benchmark regression  32/32
BF-02A stress                       43/43
Candidate canonicalization           5/5
Metamorphic properties              12/12
-----------------------------------------
Final                               92/92 PASS
```

---

## 20. What is behaviorally frozen now

给定同一个：

```text
canonical candidate set
complete normalized factor vectors
UserIntentScope
PlanningContext
TeachingPolicyProfile
planner reference profile
```

独立实现应该得到相同：

```text
eligibility exclusions
degraded/no-decision state
utility trace
activation set
request-priority class
Pareto-pruned set
tie set
SELECT / NO_TARGET
```

---

## 21. 仍可校准的内容

不能把 92/92 理解成：

```text
.17 learning_need 已被真实用户验证
.195 Balanced threshold 最优
+.08 coverage service bonus 最优
```

它证明的是：

```text
Planner engineering semantics 已可复制、可回归
```

真实产品仍需：

```text
dogfood
benchmark expansion
sensitivity analysis
real-user calibration
```

参数变更必须：

```text
planner_profile_version++
full benchmark regression
decision diff review
```

---

## 22. 当前状态

BF-02 / BF-02A：

```text
PLANNER BEHAVIORAL BASELINE V1
```

下一项：

```text
BF-03 — Teaching Gate Decision Table
```

此时 Gate 可以建立在稳定的 Planner output 上，只做执行许可，不再重做 pedagogy ranking。
