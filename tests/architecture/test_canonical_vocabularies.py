"""Canonical enum vocabularies are pinned word-for-word to the source docs.

R2 of the external review: enum members must mirror the canonical text
exactly — vocabulary only, no transition logic. Each list below is copied
verbatim from the cited canonical lines, so any drift (a missing state, an
invented one, a renamed outcome) fails here rather than silently becoming
the repo's de-facto semantics.
"""

from __future__ import annotations

import dataclasses

from elc.conversation.types import TurnOutcome
from elc.learning.types import EvidenceClaimView
from elc.runtime.types import TurnStatus
from elc.teaching.types import MomentState


def test_moment_state_matches_state_machines_section_1() -> None:
    """docs/STATE_MACHINES.md §1 lines 13-22 "Canonical lifecycle states"."""
    canonical = (
        "AUTHORIZED",
        "OPENING",
        "AWAITING_USER",
        "EVALUATING",
        "DECIDING_NEXT_ACTION",
        "COMPLETING",
        "ABORTING",
        "TEACHING_TERMINAL",
        "RESUMING",
        "CLOSED",
    )
    assert tuple(MomentState.__members__) == canonical


def test_turn_status_matches_state_machines_section_10() -> None:
    """docs/STATE_MACHINES.md §10 lines 278-291 协调状态."""
    canonical = (
        "RECEIVED",
        "USER_COMMITTED",
        "ANALYZING",
        "DECIDING",
        "GENERATING",
        "DELIVERING",
        "DELIVERY_TERMINAL",
        "POSTPROCESSING",
        "COMPLETED",
        "CANCELLED_BY_USER",
        "FAILED_RECOVERABLE",
        "FAILED_FINAL",
    )
    assert tuple(TurnStatus.__members__) == canonical


def test_turn_outcome_matches_state_machines_section_10() -> None:
    """docs/STATE_MACHINES.md §10 lines 296-301 "Turn outcome 单独记录"."""
    canonical = (
        "REPLIED_FULL",
        "REPLIED_PARTIAL",
        "NO_ASSISTANT_OUTPUT",
        "CANCELLED_BY_USER",
        "FAILED_USER_VISIBLE",
    )
    assert tuple(TurnOutcome.__members__) == canonical


def test_evidence_claim_view_carries_bf_01a_fields() -> None:
    """BF-01A canonical claim fields
    (behavioral_baselines/estimator/BF-01_Estimator_V1_Operational_Spec_
    v1.1.md §7-§9/§27/§29; field list fixed by external review R2):
    polarity / outcome / support / exposure / evaluator_confidence /
    error_attribution / accuracy / pragmatic_fit / status / provenance."""
    required = {
        "polarity",
        "outcome",
        "support",
        "exposure",
        "evaluator_confidence",
        "error_attribution",
        "accuracy",
        "pragmatic_fit",
        "status",
        "provenance",
    }
    fields = {f.name for f in dataclasses.fields(EvidenceClaimView)}
    assert required <= fields, f"BF-01A fields missing: {required - fields}"
