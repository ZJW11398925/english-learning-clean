"""Phase 8 tests — CP2 durable conversations of the decision cycle (P8-0).

P8-0 is the first cut: docs/RUNTIME_ARCHITECTURE.md §6 CP2's **Planner half**
— migration 0015's four docs/DATA_MODEL.md §14 tables, the one short
transaction that commits a cycle's records plus the ``decision_cycle``
back-reference, the five reads beside it, and the failure path that persists
a status instead of a fabricated ``PlannerDecision``. The teaching half of
CP2 (``TeachingMoment`` / ``TeachingLockLease`` / the first
``GenerationActionIntent``) belongs to the Gate's automatic face and is not
in this cut.
"""
