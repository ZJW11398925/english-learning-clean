# English Learning Application — Implementation Baseline V1

> 状态：**IMPLEMENTATION BASELINE V1 / POST-BF CONSOLIDATED**  
> 日期：2026-09-20  
> 前身：Clean Rewrite Architecture Baseline RC2  
> 规范优先级：本目录六份 canonical 文档 > 本包 behavioral reference/test assets > OQ 历史设计文档 > 旧实现。

---

## 1. Canonical Documents

1. `PRODUCT_CONTRACT.md`
2. `DOMAIN_MODEL.md`
3. `STATE_MACHINES.md`
4. `DATA_MODEL.md`
5. `RUNTIME_ARCHITECTURE.md`
6. `IMPLEMENTATION_PLAN.md`

`DECISION_REGISTER.md`、behavioral assets、Golden scenarios 与 consistency reports 是规范索引/可执行证据，不新增 Domain authority。

---

## 2. What changed after RC2

RC2 的 Domain/Authority/transaction skeleton 保留；外部评审指出的 behavioral closure gaps 已通过 BF-01～BF-07 收敛：

```text
BF-01A  Evidence → LearnerState          BEHAVIORAL BASELINE V1
BF-02A  Candidate → PlannerDecision      PLANNER BEHAVIORAL BASELINE V1
BF-03/04 PlannerDecision → Gate          GATE BEHAVIORAL BASELINE V1.1
BF-04   Cross-layer Golden Scenarios     GOLDEN SCENARIO BASELINE V1
BF-05   Security/Privacy/Deletion        CONTRACT BASELINE V1
BF-06   Operational Modality             MODALITY SCOPE BASELINE V1
BF-07   Local Runtime                    LOCAL RUNTIME BASELINE V1
```

因此 V1 implementation freeze 现在包括**行为结构**，而不仅是结构一致性。

---

## 3. Frozen V1 Core

```text
Domain Authority / source of truth
Evidence / LearnerState semantics
Estimator mapping topology, UNKNOWN and correlation semantics
Planner decision order / hard eligibility / NO_TARGET
Gate execution-only authority and authorization lineage
TeachingMoment bounded lifecycle
Delivery / Exposure epistemic boundary
TurnTransaction / retry / recovery invariants
Persona / Relationship / Learning separation
Security trust boundaries / minimal provider disclosure / deletion provenance
GoalModality vs EvidenceModality vs InteractionChannel
Local Runtime physical profile for first product slice
```

Still calibratable with version bump + full regression:

```text
Estimator masses / thresholds
Planner weights / activation thresholds
CoverageDebt rates / service bonus
review/probe/hint/retry counts
hard attempt/turn numeric caps
cooldown/budget numbers
stream buffer tuning
validator weighting
```

Calibration may not change frozen topology/authority semantics silently.

---

## 4. V1 Source-of-truth Summary

- Conversation truth: canonical UserTurn / AssistantTurn / TurnOutcome.
- Learning truth: active EvidenceGroup/EvidenceClaim/Opportunity; LearnerState is rebuildable.
- Goal truth: LearningGoalPortfolio; GoalModality does not rewrite evidence source.
- Content truth: version-controlled `content_src/*` and `curriculum/*`; `content.db` is generated read-only runtime artifact.
- Mutable local V1 truth: `app.db`, accessed through Domain interfaces.
- Secret truth: OS/platform SecretStore; DB only keeps opaque refs.
- Relationship truth: validated Relationship canonical memory; never inferred from Learning state.
- Derived indexes/projections: rebuildable and deletion-aware.

---

## 5. Local Runtime Profile

First implementation deliberately uses:

```text
single process
app.db mutable state
content.db read-only
OS SecretStore
per-conversation keyed mutex
runtime_epoch startup fencing
durable active_teaching_lock
durable projection_job
BUFFERED_VALIDATED first
```

Redis/Kafka/distributed leases/heartbeats/leader election are not V1 prerequisites.

---

## 6. Modality Boundary

```text
GoalModality: SPEAKING | LISTENING | READING | WRITING
V1 EvidenceModality: TEXT_PRODUCTION | TEXT_COMPREHENSION
Future: VOICE_PRODUCTION | AUDIO_COMPREHENSION
```

V1 may support IELTS Speaking **preparation**, but text-only evidence is not speaking/pronunciation/listening measurement.

---

## 7. Security Boundary

Untrusted text/model output is proposal-only; Domain validators own canonical writes. High-sensitivity durable memory requires explicit persistence permission. Provider disclosure is action-minimal. Deletion is provenance-aware cascade/rebuild; local deletion cannot falsely claim third-party remote revocation.

---

## 8. Implementation Entry Point

Architecture convergence is complete enough to enter Repository Bootstrap. The first real product proof must be:

```text
Persona Conversation
→ Performance Evidence
→ LearnerState
→ explicit TeachingMoment
→ Attempt
→ New Evidence
```

Automatic teaching, advanced Relationship projection, guarded streaming and large content expansion come after this minimal learning loop is proven.
