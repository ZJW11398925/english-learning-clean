# POST-BF Canonical Consolidation Report

> Date: 2026-09-20  
> Result: **PASS — IMPLEMENTATION BASELINE V1**  
> Supersedes: Clean Rewrite Architecture Baseline RC2

## 1. What was consolidated

BF-01A through BF-07 are no longer parallel design notes. Their frozen conclusions are merged into the six canonical documents.

The canonical package now includes:

```text
Estimator behavioral semantics
Planner decision semantics
Gate v1.1 authorization semantics
Cross-layer Golden invariants
Security / Privacy / Deletion contract
GoalModality / EvidenceModality / InteractionChannel split
Local Runtime physical profile
Post-BF implementation order
```

## 2. Important repairs

- `Target × SkillModality` -> `Target × EvidenceModality`.
- `UserTurn/InputEnvelope.modality` -> `interaction_channel`.
- Planner/Teaching target modality -> `evidence_modality`.
- `PlannerExecutionStatus=DEGRADED` is canonical.
- Gate OPEN uses `DECISION_CYCLE`; continuation uses `ACTIVE_MOMENT`.
- Local V1 removes required lease expiry/heartbeat fields.
- Local storage is `app.db + content.db + SecretStore`.
- `runtime_epoch`, durable `active_teaching_lock`, and durable `projection_job` are canonical Local V1 runtime mechanisms.
- Security now freezes secret-by-reference, minimal provider disclosure, high-sensitivity persistence rules and provenance-aware deletion.
- Text-only IELTS Speaking preparation is allowed, but text evidence is not Speaking/Listening measurement.

## 3. Implementation order

The first real learning proof is now:

```text
Persona Conversation
-> Performance Evidence
-> LearnerState
-> explicit user TeachingMoment
-> Attempt
-> New Evidence
```

Full Relationship projection and automatic teaching no longer precede this vertical slice.

## 4. Executed regression

- Estimator stress: **PASS** — Stress: 43/43 PASS
- Planner stress: **PASS** — Stress: 43/43 PASS
- Golden cross-layer pack: **PASS** — Golden scenarios: 28/28 PASS
- Local runtime integration: **PASS** — Local runtime checks: 43/43 PASS
- Gate v1.1 regression: **PASS** — 60/60
- Gate metamorphic: **PASS** — 14/14
- Security benchmark: **PASS** — 61/61
- Modality benchmark: **PASS** — 40/40
- Reference Python compile: **PASS** — 14 files

Cross-document consistency:

```text
60 / 60 PASS
```

No failed consistency checks remain.

## 5. Freeze meaning

Frozen for V1:

```text
authority
state semantics
decision order
authorization boundaries
transaction/idempotency/recovery invariants
privacy/deletion semantics
modality truth boundaries
Local Runtime physical profile
```

Still versioned/calibratable:

```text
Estimator numeric masses/thresholds
Planner weights/activation thresholds
CoverageDebt rates/service bonus
budget/cooldown/hard-cap numbers
freshness/review windows
streaming/validator tuning
```

Any behavioral-profile change requires a version bump and regression/diff review.

## 6. Next phase

```text
PHASE 0 — REPOSITORY BOOTSTRAP
```
