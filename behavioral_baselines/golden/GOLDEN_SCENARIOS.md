# GOLDEN_SCENARIOS.md

> 状态：V1 normative test asset

## Purpose

Golden Scenario 用于验证跨 Domain 的稳定行为，而不是自然语言 exact-string 输出。

每个 scenario 应包含：

```text
initial canonical state
scripted nondeterministic proposals
reference deterministic execution
expected decisions
expected state changes
forbidden side effects
```

## Scenario classes

```text
pipeline
switch_pipeline
canonicalization
runtime_contract
cross_layer_gate_revision
```

## Repository placement

```text
tests/golden/evidence/
tests/golden/planner/
tests/golden/gate/
tests/golden/teaching/
tests/golden/runtime/
tests/golden/cross_layer/
```

## Failure policy

Golden failure 不允许静默修改 expected value。

必须属于：

```text
implementation bug
explicit contract revision
versioned/calibrated profile change
```

并保留行为 diff。

## Non-deterministic boundary

以下层允许由 fixture 提供 canonical scripted output：

```text
model-assisted Evidence proposal
Observer proposal
Attempt evaluation
relationship proposal (future packs)
```

以下必须使用真实 deterministic reference semantics：

```text
Estimator
Candidate canonicalization
Planner
Gate
Teaching state transition
Runtime invariants
```
