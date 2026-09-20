# BF-03 Gate v1.1 — Cross-layer Authorization Repair

> Discovered during BF-04 Golden Scenario integration.

## Problem in BF-03 v1.0

BF-03 v1.0 used one field:

```text
decision_cycle_status
```

for both:

```text
OPEN
and
TeachingMoment continuation
```

and rejected `STALE`.

That is correct for opening a new moment, but wrong for continuation.

Why:

```text
TeachingMoment opens from DecisionCycle N
→ user attempt occurs
→ Evidence commits
→ Learning watermark advances
→ opening snapshot is no longer the latest snapshot
```

The active TeachingMoment is **not** supposed to re-plan its focus after every retry.
Therefore normal in-moment Evidence must not invalidate continuation.

## v1.1 Repair

Gate now consumes:

```text
authorization_basis:
  DECISION_CYCLE
  ACTIVE_MOMENT

authorization_status:
  VALID
  INVALIDATED
  UNKNOWN
```

### OPEN

Authorization basis:

```text
DECISION_CYCLE
```

A stale/invalidated opening decision becomes:

```text
authorization_status = INVALIDATED
→ DENY AUTHORIZATION_INVALID
```

### Continuation

Authorization basis:

```text
ACTIVE_MOMENT
```

It is invalidated only by a real moment-authorization failure, such as:

```text
moment superseded/aborted
target invalidated
policy/safety hard invalidation
recovery invalidation
```

It is **not** invalidated merely because the Moment itself committed new Evidence.

This preserves:

```text
do not re-plan active focus on every retry
```

while still allowing hard invalidation.
