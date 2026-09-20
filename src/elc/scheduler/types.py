"""Scheduler domain — review truth.

Owns (docs/DOMAIN_MODEL.md §9): review_state, review_urgency,
next_review_window, spacing_stage. Reads learning freshness / last strong
retrieval / stability evidence / teaching history.

Decides due/overdue. Learning never emits REVIEW_DUE directly (D-INV-009);
Planner consumes ScheduleView but owns no review truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import ScheduleVersion, TargetId


class ReviewState(StrEnum):
    """Coarse review lifecycle state."""

    NEW = "NEW"
    LEARNING = "LEARNING"
    REVIEW = "REVIEW"
    LAPSED = "LAPSED"
    SUSPENDED = "SUSPENDED"


class SpacingStage(StrEnum):
    """Scheduler-owned spacing stage."""

    STAGE_0 = "STAGE_0"
    STAGE_1 = "STAGE_1"
    STAGE_2 = "STAGE_2"
    STAGE_3 = "STAGE_3"
    STAGE_4 = "STAGE_4"


@dataclass(frozen=True)
class ReviewStateRecord:
    """One target's scheduler-owned review truth."""

    target_id: TargetId
    state: ReviewState
    spacing_stage: SpacingStage
    next_review_window_start: str | None
    next_review_window_end: str | None
    review_urgency: float | None


@dataclass(frozen=True)
class ScheduleView:
    """Planner input authority (docs/DOMAIN_MODEL.md §10)."""

    schedule_version: ScheduleVersion
    due_targets: tuple[TargetId, ...]
    overdue_targets: tuple[TargetId, ...]
    upcoming: tuple[ReviewStateRecord, ...]
