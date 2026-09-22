"""Canonical object registry (docs/IMPLEMENTATION_PLAN.md §2 Gate item 5).

Every canonical object — Goal / Policy / Profile / Scheduler view / Gate
decision / Validator result / Projection job, plus the domain-owned
aggregates — is registered here with exactly one owning authority and one
schema type (docs/DOMAIN_MODEL.md §2 Authority Matrix).

The registry is the machine-checkable form of the matrix: ownership drift in
either direction (two owners, or a schema type imported from the wrong
package) fails tests/architecture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from elc.content.types import TeachingUnit
from elc.conversation.types import ConversationRecord
from elc.curriculum.types import CurriculumGraphRecord
from elc.learning.types import EvidenceGroupRecord, LearnerTargetStateRecord
from elc.persona.types import CharacterPackageRecord
from elc.planner.types import PlannerDecision
from elc.relationship.types import RelationshipMemoryRecord
from elc.runtime.types import ProjectionJobRecord, ValidatorResultRecord
from elc.scheduler.types import ReviewEvent, ScheduleItem, ScheduleView
from elc.teaching.types import GateDecisionRecord, TeachingMomentRecord
from elc.user_config.types import (
    DisclosurePolicy,
    LearningGoalPortfolio,
    PlannerConstraint,
    SessionFocus,
    TeachingPolicyProfile,
    UserProfile,
)
from elc.world_lore.types import WorldLoreRecord

# Owner authority labels — one per canonical object. The owning module lives
# under src/elc/<owner>/ and must exist (asserted by tests/architecture).
OWNER_USER_CONFIG = "user_config"
OWNER_CONVERSATION = "conversation"
OWNER_PERSONA = "persona"
OWNER_RELATIONSHIP = "relationship"
OWNER_LEARNING = "learning"
OWNER_CURRICULUM = "curriculum"
OWNER_SCHEDULER = "scheduler"
OWNER_PLANNER = "planner"
OWNER_TEACHING = "teaching"
OWNER_RUNTIME = "runtime"
OWNER_CONTENT = "content"
OWNER_WORLD_LORE = "world_lore"


@dataclass(frozen=True)
class CanonicalObject:
    """One canonical object: its owning authority and its schema type."""

    name: str
    owner: str
    schema: type
    version_field: str | None = None


CANONICAL_OBJECTS: Mapping[str, CanonicalObject] = {
    # -- Goal / Policy / Profile: User Configuration/Profile bounded context
    # (docs/DOMAIN_MODEL.md §5.1).
    "goal_portfolio": CanonicalObject(
        "LearningGoalPortfolio",
        OWNER_USER_CONFIG,
        LearningGoalPortfolio,
        version_field="goal_version",
    ),
    "teaching_policy": CanonicalObject(
        "TeachingPolicyProfile",
        OWNER_USER_CONFIG,
        TeachingPolicyProfile,
        version_field="policy_version",
    ),
    "user_profile": CanonicalObject(
        "UserProfile", OWNER_USER_CONFIG, UserProfile
    ),
    "disclosure_policy": CanonicalObject(
        "DisclosurePolicy", OWNER_USER_CONFIG, DisclosurePolicy
    ),
    "session_focus": CanonicalObject(
        "SessionFocus", OWNER_USER_CONFIG, SessionFocus
    ),
    # docs/DATA_MODEL.md §9's TeachingPreference / PlannerConstraint (P6-3;
    # TASK-OPI-5a0be06d-….20 ③.5). The placement is a **derived judgement**:
    # §5.1's Owns list for User Configuration/Profile does not name this
    # object, so the registry entry is this cut's reading rather than a quoted
    # one — §9's shape (a typed preference with three user-level scopes and a
    # ``created_from_turn_id?`` provenance leg) plus DOMAIN_MODEL §18.1's
    # TRUSTED_AUTHORITY ("typed user settings" are the user's own statement)
    # put it here. No ``version_field``: §9 pins no version column on this
    # object at all, so a binding would claim a canonical spelling that does
    # not exist (the ScheduleItem entry's rule).
    "planner_constraint": CanonicalObject(
        "PlannerConstraint", OWNER_USER_CONFIG, PlannerConstraint
    ),
    # -- Scheduler-owned review truth (docs/DOMAIN_MODEL.md §9; the two §5.2
    # objects land with P6-1 — TASK-OPI-6259f6fd-….12).
    "schedule_view": CanonicalObject(
        "ScheduleView", OWNER_SCHEDULER, ScheduleView,
        version_field="schedule_version",
    ),
    # The Phase 0 key was ``review_state`` → ``ReviewStateRecord``; §5.2's
    # object is ScheduleItem (the skeleton's five-word state vocabulary and
    # its record type are gone, not renamed — elc/scheduler/types.py).
    # ``version_field`` stays None on purpose: §5.2 spells the column bare
    # ``version`` on ScheduleItem, so binding the qualified
    # ``schedule_version`` here would claim a canonical spelling the document
    # does not use (the ScheduleView entry above binds it, because §5.2's
    # *view* block does spell ``schedule_version``).
    "schedule_item": CanonicalObject(
        "ScheduleItem", OWNER_SCHEDULER, ScheduleItem
    ),
    "review_event": CanonicalObject(
        "ReviewEvent", OWNER_SCHEDULER, ReviewEvent
    ),
    # -- Teaching Gate authorization truth (docs/DOMAIN_MODEL.md §14;
    # docs/DATA_MODEL.md §14.1).
    "gate_decision": CanonicalObject(
        "GateDecisionRecord", OWNER_TEACHING, GateDecisionRecord,
        version_field="policy_version",
    ),
    # -- Validator results are proposal-only artifacts recorded on the runtime
    # trace (docs/DOMAIN_MODEL.md §18; validators never own domain writes).
    "validator_result": CanonicalObject(
        "ValidatorResultRecord", OWNER_RUNTIME, ValidatorResultRecord,
        version_field="validator_version",
    ),
    # -- CP4 projection work belongs to Runtime (docs/DOMAIN_MODEL.md §16).
    "projection_job": CanonicalObject(
        "ProjectionJobRecord", OWNER_RUNTIME, ProjectionJobRecord
    ),
    # -- Domain-owned aggregates.
    "conversation": CanonicalObject(
        "ConversationRecord", OWNER_CONVERSATION, ConversationRecord
    ),
    "character_package": CanonicalObject(
        "CharacterPackageRecord", OWNER_PERSONA, CharacterPackageRecord
    ),
    "relationship_memory": CanonicalObject(
        "RelationshipMemoryRecord", OWNER_RELATIONSHIP, RelationshipMemoryRecord
    ),
    "evidence_group": CanonicalObject(
        "EvidenceGroupRecord", OWNER_LEARNING, EvidenceGroupRecord
    ),
    "learner_target_state": CanonicalObject(
        "LearnerTargetStateRecord", OWNER_LEARNING, LearnerTargetStateRecord,
        version_field="estimator_version",
    ),
    "curriculum_graph": CanonicalObject(
        "CurriculumGraphRecord", OWNER_CURRICULUM, CurriculumGraphRecord,
        version_field="curriculum_version",
    ),
    "planner_decision": CanonicalObject(
        "PlannerDecision", OWNER_PLANNER, PlannerDecision
    ),
    "teaching_moment": CanonicalObject(
        "TeachingMomentRecord", OWNER_TEACHING, TeachingMomentRecord
    ),
    # -- World/Lore canonical facts (docs/DOMAIN_MODEL.md §2 Authority
    # Matrix; docs/DATA_MODEL.md §5.1 — Persona Runtime only consumes the
    # resolved WorldLoreView).
    "world_lore_fact": CanonicalObject(
        "WorldLoreRecord", OWNER_WORLD_LORE, WorldLoreRecord
    ),
    "teaching_unit": CanonicalObject(
        "TeachingUnit", OWNER_CONTENT, TeachingUnit,
        version_field="content_version",
    ),
}
