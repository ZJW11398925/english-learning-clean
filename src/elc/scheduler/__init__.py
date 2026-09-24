"""Scheduler domain — review_state / urgency / windows / spacing.

docs/DOMAIN_MODEL.md §9. Only the Scheduler decides review due (D-INV-009:
"Scheduler 决定 review due；Learning 只提供 freshness").

The durable core of §5.2's ScheduleItem / ReviewEvent lives in
:mod:`elc.scheduler.types` (the objects), :mod:`elc.scheduler.store` (the rows
and the SQL) and :mod:`elc.scheduler.controller` (the authority face); the due
decision lives in :mod:`elc.scheduler.spacing`, a pure policy with no store and
no clock, which the controller composes with the durable rows. Phase 6 P6-2
implemented the three faces P6-1 had left declared —
``recompute_schedule_item`` / ``get_schedule_view`` / ``is_review_due`` — so no
part of this package raises a phase pointer any more. The policy's constants
(:data:`SCHEDULER_MODEL_VERSION` / :data:`INTERVAL_DAYS` / :data:`GRACE_DAYS` /
:data:`URGENCY_ANCHORS`) are exported because they are what a row's version and
urgency *mean*: a consumer reading a schedule row needs the same declarations
the writer used. P7-0 adds :mod:`elc.scheduler.authority` — the watermark
handshake (``CURRENT`` / ``STALE``) a consumer compares a row against the
current Learning evidence with. P8-3 adds :mod:`elc.scheduler.review_record` —
§5.2's ``event_type`` words (declared, not frozen into the schema) and the
success / failure / unknown reading of a recorded review, off ``engaged`` and
``evidence_group_id`` alone.
"""

from elc.scheduler.authority import ScheduleCurrency, currency_of
from elc.scheduler.commands import SchedulerCommands
from elc.scheduler.controller import SchedulerController, schedule_item_id_for
from elc.scheduler.queries import SchedulerQueries
from elc.scheduler.spacing import (
    GRACE_DAYS,
    INTERVAL_DAYS,
    SCHEDULER_MODEL_VERSION,
    SPACING_STAGES,
    URGENCY_ANCHORS,
    FreshnessPort,
    LearningReadPort,
    ReviewEventRole,
    anchor_of,
    next_window,
    plan_schedule_item,
    role_of,
    row_version,
    stage_from_history,
    state_at,
    urgency_of,
)
from elc.scheduler.store import (
    REVIEW_EVENT_TABLE,
    SCHEDULE_ITEM_TABLE,
    SqliteSchedulerStore,
    StaleSchedulerStoreError,
)
from elc.scheduler.types import (
    REVIEW_STATES,
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    ScheduleView,
    SpacingStage,
)

__all__ = [
    "FreshnessPort",
    "GRACE_DAYS",
    "INTERVAL_DAYS",
    "LearningReadPort",
    "REVIEW_EVENT_TABLE",
    "REVIEW_STATES",
    "ReviewEvent",
    "ReviewEventRole",
    "ReviewState",
    "SCHEDULER_MODEL_VERSION",
    "SCHEDULE_ITEM_TABLE",
    "SPACING_STAGES",
    "ScheduleCurrency",
    "ScheduleItem",
    "ScheduleView",
    "SchedulerCommands",
    "SchedulerController",
    "SchedulerQueries",
    "SpacingStage",
    "SqliteSchedulerStore",
    "StaleSchedulerStoreError",
    "URGENCY_ANCHORS",
    "anchor_of",
    "currency_of",
    "next_window",
    "plan_schedule_item",
    "role_of",
    "row_version",
    "schedule_item_id_for",
    "stage_from_history",
    "state_at",
    "urgency_of",
]
