# BF-01 · Estimator V1 Operational Specification v1.1

> 日期：2026-09-20  
> 状态：**BEHAVIORAL BASELINE V1 — ENGINEERING FROZEN / NUMERICALLY CALIBRATABLE**  
> 前置：BF-01 v1.0、BF-01A Behavioral Stress Test  
> 目的：规定 `Evidence → LearnerTargetState` 的 V1 可执行行为，使独立工程实现对同一规范化输入得到基本一致的状态输出。

---

## 1. 冻结范围

本规范冻结：

```text
performance-type → state-dimension topology
positive downward entailment
negative propagation boundaries
PARTIAL outcome semantics
support / exposure semantics
EstimatorClaimView input contract
EvidenceGroup deduplication
EvidenceCluster diminishing returns
UNKNOWN exit semantics
ability / confidence separation
transfer derivation
support-dependency derivation
freshness / stability semantics
Resource / Capability differentiation
projection-band conflict handling
determinism / rebuild / versioning rules
```

不冻结为“科学最终值”的内容：

```text
base masses
multipliers
confidence saturation constants
threshold numbers
freshness day windows
```

这些属于 versioned reference profile，可通过真实数据校准。

---

## 2. Estimator 是纯确定性 projection

输入：

```text
ACTIVE canonical Evidence
+ deterministic EstimatorClaimView
+ estimator profile
+ as_of
```

输出：

```text
LearnerTargetState
```

Estimator 内禁止：

```text
LLM call
randomness
Planner feedback
Goal weighting
Schedule urgency
Relationship opinion
```

相同输入 + 相同 profile/version 必须得到相同输出。

---

## 3. Scope

Canonical state key：

```text
target_type
target_id
skill_modality
```

V1 不跨 modality 自动合并 ability。

---

## 4. Base dimensions 与 derived dimensions

Evidence-Mass 直接估计：

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

`transfer` 与 `support_dependency` 不使用与 recognition 完全相同的直接质量公式。

---

## 5. Positive performance topology

```text
RECOGNITION
→ recognition

IMITATIVE_PRODUCTION
→ weak recognition
→ very weak guided support

GUIDED_PRODUCTION
→ recognition
→ guided

INDEPENDENT_PRODUCTION
→ recognition
→ guided
→ independent

SPONTANEOUS_PRODUCTION
→ recognition
→ guided
→ independent
→ spontaneous

SELF_REPAIR
→ recognition
→ guided
→ independent
→ conditional spontaneous support
```

这是 positive downward entailment。

强行为可以弱支持低层能力，但仍是**同一条 Evidence 的多维 contribution**，不是多份独立证据。

---

## 6. Negative propagation 不对称

禁止：

```text
spontaneous failure
→ recognition failure
→ guided failure
```

Negative evidence 只影响 Opportunity/Attempt 直接支持诊断的维度。

Reference：

```text
NATURAL low-support FAILED_ATTEMPT
→ spontaneous negative
→ independent negative
→ not guided/recognition

ELICITED low-support FAILED_ATTEMPT
→ independent negative

supported FAILED_ATTEMPT
→ guided negative

MISUSE
→ primarily accuracy negative
→ optional weak production negative if opportunity directly supports it
```

---

## 7. EstimatorClaimView 输入契约

Canonical Evidence 进入 Estimator 前必须满足最低一致性。

### 7.1 Independent / Spontaneous 与支架兼容

以下 claim 无效：

```text
INDEPENDENT_PRODUCTION + SEMANTIC/STRUCTURAL/PARTIAL/FULL support
INDEPENDENT_PRODUCTION + answer exposure != NONE
SPONTANEOUS_PRODUCTION + assistance
SPONTANEOUS_PRODUCTION + answer exposure
SPONTANEOUS_PRODUCTION + opportunity != NATURAL
```

这些错误应由 Learning Validator 在 commit 前阻止。

Reference Estimator 在 strict mode 下也拒绝这些输入，防止 canonical corruption 被静默计算。

### 7.2 同一 EvidenceGroup × target × modality

最多一个 primary performance claim。

允许一个行为产生：

```text
多个不同 target 的 EvidenceClaims
```

但不允许对同一个 target 同一行为同时提交：

```text
FAILED_ATTEMPT
+
GUIDED_PRODUCTION
```

作为两个 primary performance claims。

---

## 8. Support / Exposure

Reference assistance factor：

```text
assist =
min(support_factor, exposure_factor)
```

避免同一个帮助来源被重复惩罚。

Reference support：

```text
NONE             1.00
CONTEXT_ONLY     0.90
SEMANTIC_HINT    0.70
STRUCTURAL_HINT  0.50
PARTIAL_FORM     0.30
FULL_FORM_SHOWN  0.10
```

Reference exposure：

```text
NONE     1.00
PARTIAL  0.60
FULL     0.15
```

Full answer exposure 后，同一 TeachingMoment 不产生 independent evidence。

---

## 9. PARTIAL outcome — v1.1 关键修订

BF-01A 发现 v1.0 的结构错误：

```text
PARTIAL success
→ 只是较小的 pure positive mass
```

这样重复很多次 PARTIAL 最终会趋近：

```text
ability estimate = 1.0
```

这是错误的。

v1.1 冻结：

> `PARTIAL` 是混合证据，不是缩小版完整成功。

对 primary direct dimension：

```text
PARTIAL
→ positive mass
+
residual negative mass
```

Reference direct balance：

```text
positive fraction = 0.50
negative fraction = 0.50
```

因此反复 partial guided performance 会提高 confidence，但其 direct ability estimate 仍接近 partial-control 区域，而不是逐渐变成完全掌握。

Downward supportive dimensions 可以保留弱 positive contribution；不会机械复制 direct negative。

---

## 10. Evaluator confidence

Reference minimum：

```text
evaluator_confidence >= 0.50
```

低于阈值：

```text
no state mass
```

不等于负证据。

---

## 11. EvidenceGroup dedup

同一 EvidenceGroup：

```text
same target
same dimension
same polarity
```

只保留 strongest contribution。

目的：

```text
一个 utterance 不能因为多个 evaluator path 被重复计票
```

---

## 12. EvidenceCluster

### Teaching

```text
same teaching_moment_id
→ same correlation cluster
```

### Natural evidence

Reference cluster key：

```text
conversation
day
context
realization
persona
```

Cluster 是相关性折减单位，不是 mastery 单位。

---

## 13. Same-cluster diminishing returns

Reference：

```text
1st  × 1.00
2nd  × 0.35
3rd+ × 0.15
```

同 cluster mass cap：

```text
<= 1.60 × strongest same-polarity contribution
```

所以：

```text
同五分钟重复3次
```

不能等价于：

```text
跨天/跨情境独立出现3次
```

---

## 14. Ability estimate / UNKNOWN

对每个 base dimension：

```text
P = effective positive mass
N = effective negative mass
M = P + N
```

Reference：

```text
M < 0.55
→ estimate = null  # UNKNOWN
```

否则：

```text
estimate = P / (P + N)
```

因此合法：

```text
一次强成功
→ estimate 高
→ confidence 低
```

以及：

```text
多次一致失败
→ estimate 低
→ confidence 高
```

---

## 15. Confidence

Reference：

```text
mass_confidence =
1 - exp(-effective_mass / tau)

tau = 2.40
```

多样性只给予有限 confidence bonus：

```text
days
contexts
personas
realizations
```

多样性不会直接把 ability estimate 抬高。

---

## 16. Self-repair — v1.1 修订

v1.0 会把：

```text
提示后的 SELF_REPAIR
```

错误视为 strong retrieval，从而抬高：

```text
freshness
transfer
stability
```

v1.1 冻结：

SELF_REPAIR 只有在：

```text
spontaneity ∈ {INDEPENDENT, SPONTANEOUS}
+
low assistance
+
SUCCESS
```

时，才可进入 strong-retrieval set。

Guided self-repair 仍可贡献 guided/independent-related普通 Evidence，但不证明独立 retrieval freshness/transfer。

---

## 17. Transfer — strong cluster derived

Transfer 只从 strong retrieval clusters 构建。

Strong retrieval：

```text
INDEPENDENT / SPONTANEOUS / eligible SELF_REPAIR
SUCCESS
evaluator_confidence >= 0.70
assist >= 0.70
```

### v1.1 cluster dedup

同一个新情境内连续重复：

```text
不能多次叠加 transfer mass
```

每个 strong cluster 只取一个代表贡献。

Negative transfer evidence 同样按 cluster 去重。

---

## 18. Resource Transfer

需要：

```text
>= 2 strong clusters
+
至少一个 meaningful diversity axis
```

例如：

```text
new context
new persona
new realization
cross-modality condition
```

---

## 19. Capability Transfer

除 Resource 条件外，额外要求：

```text
realization_diversity >= 2
```

同一固定表达跨多个场景使用，不足以证明整个 CommunicativeCapability 的 realization transfer。

---

## 20. NARROW_EVIDENCE — v1.1 修订

v1.0 使用所有 ACTIVE Evidence 的 context/realization coverage，导致：

```text
一个 evaluator_confidence=0.2 的“不同情境” claim
```

也能移除 `NARROW_EVIDENCE`。

v1.1 改为：

```text
NARROW_EVIDENCE
只看 strong-retrieval diversity
```

无效/低置信/纯失败证据不能伪造广度。

---

## 21. Support dependency

不能从：

```text
repeated unsupported failure
```

单独推导。

因为它只证明：

```text
gap
```

### 高 support dependency 的诊断模式

需要可比较条件：

```text
low-support failure
+
assisted success
```

最好跨多个独立 Moment/cluster 重复。

### 低 dependency

可由：

```text
repeated low-support success
```

建立。

### Assisted success only

没有 low-support opportunity 时：

```text
support_dependency = UNKNOWN
```

---

## 22. Freshness

只基于 strong retrieval。

Reference：

```text
<= 7d    FRESH
8–21d    AGING
>21d     STALE
none     UNKNOWN
```

时间不改变历史 ability mass。

---

## 23. Stability — v1.1 修订

`STABLE` 只能依据 strong retrieval 的：

```text
cluster count
strong-day diversity
freshness
```

低置信或无效 Evidence 出现在另一天，不能把单日强 Evidence 升级成 STABLE。

---

## 24. Ability band 与 hierarchy conflict

Reference band：

```text
UNKNOWN
EARLY
GUIDED
INDEPENDENT
SPONTANEOUS
```

允许：

```text
SPONTANEOUS + LOW confidence
```

用于表示“一次强自然成功，但证据仍少”。

但是 BF-01A 发现：

```text
one spontaneous success
+
multiple high-confidence independent failures
```

v1.0 会出现：

```text
ability_band = SPONTANEOUS
+
CONFIRMED_GAP
```

作为 headline 状态过于误导。

v1.1 冻结：

```text
higher tier is blocked
if its lower prerequisite tier has a high-confidence confirmed gap
```

同时输出：

```text
CONFLICTING_EVIDENCE
```

例如上例可能变成：

```text
ability_band = GUIDED
CONFIRMED_GAP
CONFLICTING_EVIDENCE
```

保留异常 spontaneous evidence，但不让单次异常事件压过稳定反证。

---

## 25. Learning flags

允许：

```text
CONFIRMED_GAP
SUPPORT_DEPENDENT
CONFLICTING_EVIDENCE
INSUFFICIENT_EVIDENCE
NARROW_EVIDENCE
STRONG_INDEPENDENT_CONTROL
STRONG_SPONTANEOUS_CONTROL
```

禁止：

```text
REVIEW_DUE
TRANSFER_NEEDED
TEACH_NOW
HIGH_PRIORITY
```

---

## 26. CONFIRMED_GAP reference

Reference：

```text
estimate <= 0.35
confidence >= 0.65
```

单次 failure/slip 通常不能达到这个状态。

---

## 27. Quality dimensions

如果 evaluator 提供：

```text
accuracy ∈ [0,1]
pragmatic_fit ∈ [0,1]
```

Estimator 将其转为正/负质量 mass：

```text
positive ∝ q
negative ∝ (1-q)
```

不会用最新一次分数覆盖历史。

---

## 28. Modality isolation

Estimator 只消费当前：

```text
target × modality
```

Evidence。

例如：

```text
WRITING success
```

不能自动写入：

```text
TEXT_PRODUCTION / SPEAKING
```

跨 modality 能力需要显式 future projection，不由本 Estimator 偷偷推断。

---

## 29. Invalidation / Supersede

只有：

```text
status = ACTIVE
```

进入估计。

`INVALIDATED / SUPERSEDED` 不贡献 mass、freshness、transfer 或 diversity。

---

## 30. Determinism

Reference implementation必须满足：

```text
input order does not change state
```

对合法 Evidence set，排列顺序不改变最终 LearnerTargetState。

---

## 31. Reference profile 版本纪律

v1.1 profile：

```text
estimator-v1.1-reference-2026-09-stress-tested
```

结构语义属于 Behavioral Baseline。

数字允许校准，但每次改变必须：

```text
new profile_id
estimator/profile version bump
full golden + stress + metamorphic regression
old/new diff review
```

---

## 32. Baseline status

BF-01A 之后：

```text
Estimator V1 Operational Kernel
= BEHAVIORAL BASELINE V1
```

这里的 baseline 含义是：

> 工程实现行为已经足够明确、可复制、可回归。

它**不表示**：

```text
reference weights 已经通过真实学习者纵向数据验证
```

真实用户校准仍属于后续 empirical calibration。
