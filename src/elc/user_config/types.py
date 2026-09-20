"""User Configuration / Profile bounded context.

Owns (docs/DOMAIN_MODEL.md §5.1): UserProfile, DisclosurePolicy,
LearningGoalPortfolio, TeachingPolicyProfile, SessionFocus.

Goal/Policy are versioned configuration — never Learning Evidence. The
GlobalGoalPortfolio can be temporarily re-weighted by a SessionFocus but
never silently rewritten. Persona Runtime may only ever receive
DisclosedUserProfile, never the full UserProfile. TeachingPolicy changes
only how/how-often teaching happens — never Learner State truth.

This bounded context is one of the canonical supporting contexts alongside
the eleven Phase 0 packages; the task list's eleven modules plus this
context is what Gate item 5 (owner+schema for Goal/Policy/Profile) requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import GoalId, GoalVersion, PersonaId, PolicyVersion, UserId


class TeachingFrequency(StrEnum):
    """Coarse policy knob: how/how-often, never mastery truth (§5.1)."""

    OFF = "OFF"
    MINIMAL = "MINIMAL"
    BALANCED = "BALANCED"
    EAGER = "EAGER"


class DisclosureLevel(StrEnum):
    """Per-persona disclosure policy knob."""

    MINIMAL = "MINIMAL"
    FUNCTIONAL = "FUNCTIONAL"
    RICH = "RICH"


@dataclass(frozen=True)
class UserProfile:
    """Long-term user profile; high-sensitive persistence requires explicit
    user consent (docs/DOMAIN_MODEL.md §18.1)."""

    user_id: UserId
    display_name: str | None
    high_sensitive: tuple[str, ...]  # persisted only with explicit consent


@dataclass(frozen=True)
class DisclosurePolicy:
    """Action-specific minimal view policy for provider/persona disclosure."""

    persona_id: PersonaId | None
    disclosure_level: DisclosureLevel


@dataclass(frozen=True)
class DisclosedUserProfile:
    """The ONLY user-profile shape Persona Runtime may consume (§5.1)."""

    persona_id: PersonaId
    disclosure_level: DisclosureLevel
    disclosed_facts: tuple[str, ...]


@dataclass(frozen=True)
class LearningGoal:
    """One long-term learning goal; GoalModality separates goal from evidence."""

    goal_id: GoalId
    goal_modality: str  # elc.platform.types.GoalModality value
    description: str


@dataclass(frozen=True)
class LearningGoalPortfolio:
    """Versioned goal portfolio (docs/DATA_MODEL.md §315
    base_goal_portfolio_version)."""

    user_id: UserId
    goal_version: GoalVersion
    goals: tuple[LearningGoal, ...]


@dataclass(frozen=True)
class TeachingPolicyProfile:
    """Versioned teaching policy — how/how-often only (§5.1)."""

    user_id: UserId
    policy_version: PolicyVersion
    teaching_frequency: TeachingFrequency
    automatic_teaching_enabled: bool


@dataclass(frozen=True)
class SessionFocus:
    """Temporary re-weighting of the portfolio; never rewrites long-term
    goals silently (§5.1)."""

    user_id: UserId
    focus_goal_ids: tuple[GoalId, ...]
    weight_override: dict[str, float]
