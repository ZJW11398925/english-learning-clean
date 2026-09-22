"""Phase 6 tests — Goal Portfolio + Scheduler views (docs/IMPLEMENTATION_PLAN.md
§1.5 Phase 6). P6-0 is the first cut: the three §5.1 objects, their durable
rows (migration 0011) and their authority faces. P6-1 is the second: the §5.2
ScheduleItem / ReviewEvent durable core (migration 0012), its store and its
authority face. P6-2 is the third: the due/overdue decision (the pure policy in
``elc.scheduler.spacing``), the Scheduler view production and ``is_review_due``
— every face P6-1 left declared now answers, and this cut lands no migration.
P6-3 is the fourth: docs/DATA_MODEL.md §9's PlannerConstraint — its durable
row (migration 0013), the append-first write face with the one movable
``active`` column, and the three active-window reads that answer "which
constraints are in force at this instant", for one target or in general."""
