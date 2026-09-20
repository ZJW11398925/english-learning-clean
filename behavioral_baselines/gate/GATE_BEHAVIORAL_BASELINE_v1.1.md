# Teaching Gate Behavioral Baseline v1.1

> Status: **GATE BEHAVIORAL BASELINE V1.1**  
> Canonical source: `STATE_MACHINES.md` + `DATA_MODEL.md` + `RUNTIME_ARCHITECTURE.md`.  
> Executable reference: `teaching_gate_reference_v1_1.py`.

## Core split

```text
Planner = worth teaching?
Gate    = may execute now?
```

Authorization basis:

```text
OPEN         -> DECISION_CYCLE
CONTINUATION -> ACTIVE_MOMENT
```

An active TeachingMoment's own newly committed Evidence does not by itself invalidate its continuation authorization.

Gate checks execution admissibility only: safety/privacy, lineage/authorization, target/content validity, suppression, latest intent, auto-teach controls, TeachingLock/lifecycle, protected flow, opening budget/cooldown, hard attempt/turn caps.

Gate does not re-rank pedagogy or inspect learning_need / goal_relevance / coverage_debt / Planner utility.

Critical execution state unknown:

```text
GateExecutionStatus = DEGRADED
GateDecision = none
```

Explicit user requests may bypass controls whose sole role is preventing unsolicited interruption, but never bypass safety/privacy, active suppression, invalid target/content, lock/lifecycle conflict or hard teaching limits.
