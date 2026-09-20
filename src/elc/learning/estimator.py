"""Evidence-Mass Estimator V1 — pure deterministic projection (Phase 2 P2B).

Semantic authority: behavioral_baselines/estimator/
BF-01_Estimator_V1_Operational_Spec_v1.1.md (sections cited per block
below). This module is an independent engineering implementation of that
behavioral baseline; it copies the *frozen structure* and the versioned
reference *numbers* (self-minted constants with source citations —
``src`` never imports ``behavioral_baselines``; the frozen reference is
relegated to test-oracle duty only, tests/behavioral + tests/phase2).

BF-01 §2: the estimator is a pure deterministic projection — ACTIVE
canonical evidence + deterministic claim views + profile + as_of →
LearnerTargetState estimate. No LLM, no randomness, no Planner feedback,
no goal weighting, no schedule urgency, no relationship opinion. Same
input + same profile/version → same output (§30: input order does not
change state).

Section map (BF-01 v1.1 → this module):
  §3   scope: one target_type × target_id × modality per call (the
        ``estimate_target_state`` arguments); §28 modality isolation is
        the ACTIVE-claim filter.
  §4   base dimensions (direct evidence mass) + derived dimensions
        (transfer / support_dependency use their own formulas below).
  §5   positive performance topology → POSITIVE_MAPPING + the
        SELF_REPAIR conditional spontaneous support.
  §6   negative propagation asymmetry → _negative_dimension_map.
  §7   EstimatorClaimView contract → validate_claims /
        EstimatorContractError (strict mode refuses corrupted canon
        instead of silently computing it).
  §8   support / exposure factors, assist = min(support, exposure).
  §9   PARTIAL outcome is mixed evidence (positive + residual negative
        on the direct dimension), not a small pure success.
  §10  evaluator confidence floor (below → no mass, not negative mass).
  §11  EvidenceGroup dedup (strongest contribution per dim × polarity).
  §12  EvidenceCluster key (teaching moment / natural correlation key).
  §13  same-cluster diminishing returns + same-cluster mass cap.
  §14  ability estimate / UNKNOWN mass threshold.
  §15  confidence saturation + bounded diversity bonus.
  §16  self-repair enters the strong-retrieval set only when
        spontaneity ∈ {INDEPENDENT, SPONTANEOUS} + low assistance +
        SUCCESS.
  §17  transfer from strong-retrieval clusters with v1.1 cluster dedup.
  §18  resource transfer gate (≥2 strong clusters + a diversity axis).
  §19  capability transfer additionally requires realization diversity.
  §20  NARROW_EVIDENCE only looks at strong-retrieval diversity.
  §21  support dependency diagnostic (assisted-only → UNKNOWN).
  §22  freshness bands from strong retrieval only.
  §23  stability from strong-retrieval clusters/days/freshness only.
  §24  ability band hierarchy-conflict blocking + confidence bands.
  §25  learning flag vocabulary (allowed set pinned).
  §26  CONFIRMED_GAP reference thresholds.
  §27  quality dimensions → accuracy / pragmatic_control mass split.
  §29  only ACTIVE claims enter estimation (caller-side filter is also
        applied here defensively).
  §30  determinism (iteration orders pinned; pure functions).
  §31  profile version discipline (ESTIMATOR_PROFILE_ID).

DATA_MODEL §11 adds a per-dimension ``last_relevant_evidence_at`` which
the frozen reference does not track; this module computes it from the
claims whose contribution touched each dimension (documented
implementation-defined extension, DATA_MODEL §27).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

__all__ = [
    "ABILITY_DIMENSIONS",
    "ALLOWED_LEARNING_FLAGS",
    "ContractViolation",
    "Coverage",
    "EstimatorClaimView",
    "EstimatorContractError",
    "ESTIMATOR_PROFILE_ID",
    "Freshness",
    "MassDimensionState",
    "PRODUCTION_TYPES",
    "Projection",
    "SupportDependencyState",
    "TargetStateEstimate",
    "estimate_target_state",
    "validate_claims",
]

# ---------------------------------------------------------------------------
# Versioned reference profile (BF-01 §1: structure frozen / numbers
# calibratable; §31: every numeric change needs a new profile id + version
# bump + full regression). All numbers below are copied verbatim from
# behavioral_baselines/estimator/estimator_reference_profile_v1_1.json
# (profile_id below) with per-constant source citations.
# ---------------------------------------------------------------------------

#: BF-01 §31 — v1.1 profile identity. Riding every LearnerTargetState as
#: meta.estimator_version (DATA_MODEL §11).
ESTIMATOR_PROFILE_ID = "estimator-v1.1-reference-2026-09-stress-tested"

#: profile claim_min_confidence — BF-01 §10: evaluator_confidence >= 0.50
#: or the claim contributes no state mass (never negative mass).
CLAIM_MIN_CONFIDENCE: float = 0.50

#: profile dimension_min_effective_mass — BF-01 §14: effective mass below
#: 0.55 → estimate = UNKNOWN (null).
DIMENSION_MIN_EFFECTIVE_MASS: float = 0.55

#: profile confidence_tau — BF-01 §15: mass_confidence = 1 - exp(-M/tau).
CONFIDENCE_TAU: float = 2.40

#: profile same_cluster_repeat_weights — BF-01 §13: 1st × 1.00, 2nd ×
#: 0.35, 3rd+ × 0.15 inside one correlation cluster.
SAME_CLUSTER_REPEAT_WEIGHTS: tuple[float, ...] = (1.00, 0.35, 0.15)

#: profile same_cluster_mass_cap_multiple — BF-01 §13: same-cluster mass
#: capped at 1.60 × the strongest same-polarity contribution.
SAME_CLUSTER_MASS_CAP_MULTIPLE: float = 1.60

#: BF-01 §5 positive performance topology (downward entailment weights;
#: profile positive_mapping). One strong behavior is ONE piece of
#: evidence contributing to several dimensions — not several independent
#: pieces of evidence.
POSITIVE_MAPPING: Mapping[str, Mapping[str, float]] = {
    "RECOGNITION": {"recognition": 1.00},
    "IMITATIVE_PRODUCTION": {"recognition": 0.65, "guided_production": 0.25},
    "GUIDED_PRODUCTION": {"recognition": 0.75, "guided_production": 1.00},
    "INDEPENDENT_PRODUCTION": {
        "recognition": 0.85,
        "guided_production": 0.75,
        "independent_production": 1.00,
    },
    "SPONTANEOUS_PRODUCTION": {
        "recognition": 0.90,
        "guided_production": 0.80,
        "independent_production": 1.00,
        "spontaneous_production": 1.00,
    },
    "SELF_REPAIR": {
        "recognition": 0.65,
        "guided_production": 0.55,
        "independent_production": 0.70,
    },
}

#: profile support_factor — BF-01 §8 reference support discounts.
SUPPORT_FACTOR: Mapping[str, float] = {
    "NONE": 1.00,
    "CONTEXT_ONLY": 0.90,
    "SEMANTIC_HINT": 0.70,
    "STRUCTURAL_HINT": 0.50,
    "PARTIAL_FORM": 0.30,
    "FULL_FORM_SHOWN": 0.10,
}

#: profile exposure_factor — BF-01 §8 reference answer-exposure
#: discounts (full exposure after the same TeachingMoment yields no
#: independent evidence).
EXPOSURE_FACTOR: Mapping[str, float] = {
    "NONE": 1.00,
    "PARTIAL": 0.60,
    "FULL": 0.15,
}

#: profile support_burden — BF-01 §21 diagnostic burden of each support
#: level for the support-dependency dimension.
SUPPORT_BURDEN: Mapping[str, float] = {
    "NONE": 0.00,
    "CONTEXT_ONLY": 0.10,
    "SEMANTIC_HINT": 0.35,
    "STRUCTURAL_HINT": 0.55,
    "PARTIAL_FORM": 0.75,
    "FULL_FORM_SHOWN": 0.95,
}

#: BF-01 §8: exposure burden used by the §21 diagnostic (profile value
#: embedded in the reference _claim dependency classification).
EXPOSURE_BURDEN: Mapping[str, float] = {
    "NONE": 0.00,
    "PARTIAL": 0.75,
    "FULL": 0.95,
}

#: profile error_attribution_multiplier — BF-01 §6/§21 error attribution
#: calibration keys.
ERROR_ATTRIBUTION_MULTIPLIER: Mapping[str, float] = {
    "LIKELY_SLIP": 0.20,
    "UNKNOWN": 0.60,
    "LIKELY_KNOWLEDGE_GAP": 1.00,
    "SYSTEMATIC_PATTERN": 1.35,
}

#: Unattributed errors default to the UNKNOWN multiplier (BF-01 §6
#: reference default).
ERROR_ATTRIBUTION_DEFAULT_MULTIPLIER: float = 0.60

#: profile outcome_factor — BF-01 §9: PARTIAL contributes half-strength
#: positive mass plus a residual negative share on the direct dimension.
OUTCOME_FACTOR: Mapping[str, float] = {
    "SUCCESS": 1.00,
    "PARTIAL": 0.50,
    "FAILURE": 1.00,
    "ABSTAIN": 0.00,
}

#: profile quality_strength — BF-01 §27: evaluator quality scores are
#: converted to positive ∝ q / negative ∝ (1-q) mass with these
#: per-performance-type strengths; never overwritten by the latest score.
QUALITY_STRENGTH: Mapping[str, float] = {
    "IMITATIVE_PRODUCTION": 0.30,
    "GUIDED_PRODUCTION": 0.65,
    "INDEPENDENT_PRODUCTION": 1.00,
    "SPONTANEOUS_PRODUCTION": 1.00,
    "SELF_REPAIR": 0.80,
    "MISUSE": 0.80,
}

#: profile support_dependency_min_mass — BF-01 §21 identifiability mass.
SUPPORT_DEPENDENCY_MIN_MASS: float = 1.20

#: profile freshness_days — BF-01 §22 bands (≤7d FRESH, 8–21d AGING,
#: >21d STALE, none UNKNOWN). Time never changes historical mass.
FRESHNESS_DAYS_FRESH_MAX: int = 7
FRESHNESS_DAYS_AGING_MAX: int = 21

#: profile confidence_bands — BF-01 §24 confidence band edges.
CONFIDENCE_BAND_LOW_MAX: float = 0.39
CONFIDENCE_BAND_MEDIUM_MAX: float = 0.69

#: profile planning_thresholds — BF-01 §26 CONFIRMED_GAP reference.
CONFIRMED_GAP_ESTIMATE_MAX: float = 0.35
CONFIRMED_GAP_CONFIDENCE_MIN: float = 0.65
#: profile planning_thresholds — BF-01 §25 SUPPORT_DEPENDENT flag.
SUPPORT_DEPENDENT_ESTIMATE_MIN: float = 0.65
SUPPORT_DEPENDENT_CONFIDENCE_MIN: float = 0.55
#: profile planning_thresholds — BF-01 §25 strong-control flags.
STRONG_CONTROL_ESTIMATE_MIN: float = 0.80
STRONG_CONTROL_CONFIDENCE_MIN: float = 0.65
#: profile planning_thresholds — within-dimension conflict window.
CONFLICT_MASS_MIN_EACH: float = 0.80
CONFLICT_RATIO_LOW: float = 0.35
CONFLICT_RATIO_HIGH: float = 0.65

#: profile capability_confidence_caps — BF-01 §19: capability
#: independent/spontaneous/pragmatic confidence is capped below
#: realization diversity 2; capability transfer confidence is capped
#: below context diversity 2.
CAPABILITY_REALIZATION_DIVERSITY_CAP: float = 0.65
CAPABILITY_TRANSFER_CONTEXT_DIVERSITY_CAP: float = 0.55

#: profile partial_direct_negative_fraction — BF-01 §9 v1.1: PARTIAL
#: direct balance is 0.50 positive / 0.50 residual negative.
PARTIAL_DIRECT_NEGATIVE_FRACTION: float = 0.50

#: BF-01 §16/§17 strong-retrieval membership floors.
STRONG_RETRIEVAL_MIN_CONFIDENCE: float = 0.70
STRONG_RETRIEVAL_MIN_ASSIST: float = 0.70

#: BF-01 §12: the conditional spontaneous support weight of an eligible
#: SELF_REPAIR claim (§5 "conditional spontaneous support").
SELF_REPAIR_SPONTANEOUS_SUPPORT: float = 0.50

#: BF-01 §25 allowed learning-flag vocabulary (the forbidden scheduler
#: words REVIEW_DUE / TRANSFER_NEEDED / TEACH_NOW / HIGH_PRIORITY can
#: never be emitted — the estimator is evidence-derived only).
ALLOWED_LEARNING_FLAGS: frozenset[str] = frozenset(
    {
        "CONFIRMED_GAP",
        "SUPPORT_DEPENDENT",
        "CONFLICTING_EVIDENCE",
        "INSUFFICIENT_EVIDENCE",
        "NARROW_EVIDENCE",
        "STRONG_INDEPENDENT_CONTROL",
        "STRONG_SPONTANEOUS_CONTROL",
    }
)

#: BF-01 §4 base dimensions estimated directly from evidence mass.
ABILITY_DIMENSIONS: tuple[str, ...] = (
    "recognition",
    "guided_production",
    "independent_production",
    "spontaneous_production",
    "accuracy",
    "pragmatic_control",
)

#: BF-01 §4/§7 production performance types (primary performance faces).
PRODUCTION_TYPES: frozenset[str] = frozenset(
    {
        "IMITATIVE_PRODUCTION",
        "GUIDED_PRODUCTION",
        "INDEPENDENT_PRODUCTION",
        "SPONTANEOUS_PRODUCTION",
        "SELF_REPAIR",
        "FAILED_ATTEMPT",
        "MISUSE",
    }
)

#: BF-01 §9: the direct dimension of each positive performance type (the
#: dimension a PARTIAL residual lands on).
DIRECT_DIMENSION: Mapping[str, str] = {
    "RECOGNITION": "recognition",
    "GUIDED_PRODUCTION": "guided_production",
    "INDEPENDENT_PRODUCTION": "independent_production",
    "SPONTANEOUS_PRODUCTION": "spontaneous_production",
    "SELF_REPAIR": "independent_production",
}

#: BF-01 §15 diversity bonus weights (limited confidence bonus only —
#: diversity never raises the ability estimate itself).
DIVERSITY_BONUS_WEIGHTS: Mapping[str, float] = {
    "days": 0.35,
    "contexts": 0.25,
    "personas": 0.15,
    "realizations": 0.25,
}


# ---------------------------------------------------------------------------
# Claim view (BF-01 §7 input contract)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EstimatorClaimView:
    """One canonical claim as the estimator sees it (BF-01 §7).

    Field set mirrors the BF-01A canonical claim dict (golden / stress
    case claim shape): provenance (group/timestamp/conversation/moment/
    persona/context/realization), performance (type/polarity/outcome/
    qualifiers/spontaneity), support & exposure, evaluator fields,
    quality inputs, target scope, and correction status.
    """

    group_id: str
    timestamp: str
    performance_type: str
    polarity: str
    outcome: str
    evaluator_confidence: float
    support_level: str = "NONE"
    exposure_level: str = "NONE"
    opportunity_type: str | None = None
    qualifiers: tuple[str, ...] = ()
    error_attribution: str | None = None
    accuracy: float | None = None
    pragmatic_fit: float | None = None
    conversation_id: str | None = None
    teaching_moment_id: str | None = None
    persona_id: str | None = None
    context_key: str | None = None
    realization_key: str | None = None
    target_type: str = "RESOURCE"
    target_id: str = ""
    modality: str = "TEXT_PRODUCTION"
    status: str = "ACTIVE"
    spontaneity: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> EstimatorClaimView:
        """Build a view from a BF-01A canonical claim dict (the golden /
        stress case shape)."""

        def text(key: str) -> str:
            return str(data[key])

        def opt_text(key: str) -> str | None:
            value = data.get(key)
            return None if value is None else str(value)

        def number(key: str) -> float:
            return float(cast(float, data[key]))

        def opt_number(key: str) -> float | None:
            value = data.get(key)
            return None if value is None else float(cast(float, value))

        qualifiers = data.get("qualifiers", ())
        return cls(
            group_id=text("group_id"),
            timestamp=text("timestamp"),
            performance_type=text("performance_type"),
            polarity=text("polarity"),
            outcome=text("outcome"),
            evaluator_confidence=number("evaluator_confidence"),
            support_level=str(data.get("support_level", "NONE")),
            exposure_level=str(data.get("exposure_level", "NONE")),
            opportunity_type=opt_text("opportunity_type"),
            qualifiers=tuple(str(q) for q in cast(Sequence[object], qualifiers)),
            error_attribution=opt_text("error_attribution"),
            accuracy=opt_number("accuracy"),
            pragmatic_fit=opt_number("pragmatic_fit"),
            conversation_id=opt_text("conversation_id"),
            teaching_moment_id=opt_text("teaching_moment_id"),
            persona_id=opt_text("persona_id"),
            context_key=opt_text("context_key"),
            realization_key=opt_text("realization_key"),
            target_type=str(data.get("target_type", "RESOURCE")),
            target_id=str(data.get("target_id", "")),
            modality=str(data.get("modality", "TEXT_PRODUCTION")),
            status=str(data.get("status", "ACTIVE")),
            spontaneity=opt_text("spontaneity"),
        )


@dataclass(frozen=True)
class ContractViolation:
    """One BF-01 §7 EstimatorClaimView contract violation."""

    code: str
    claim_index: int | None = None
    detail: str = ""


class EstimatorContractError(ValueError):
    """Raised in strict mode when claims violate the §7 contract.

    BF-01 §7: these errors should have been stopped by the Learning
    Validator before commit; the estimator refuses them too so canonical
    corruption is never silently computed.
    """

    def __init__(self, violations: Sequence[ContractViolation]) -> None:
        self.violations = tuple(violations)
        rendered = json.dumps(
            [
                {
                    "code": v.code,
                    "index": v.claim_index,
                    "detail": v.detail,
                }
                for v in self.violations
            ],
            ensure_ascii=False,
            default=str,
        )
        super().__init__(
            "EstimatorClaimView contract violation: " + rendered
        )


def validate_claims(
    claims: Sequence[EstimatorClaimView],
) -> tuple[ContractViolation, ...]:
    """BF-01 §7 input-contract check (independent of any target scope).

    §7.1: INDEPENDENT/SPONTANEOUS production is incompatible with
    assistance or answer exposure; SPONTANEOUS requires a NATURAL
    opportunity. §7.2: at most one primary performance claim per
    EvidenceGroup × target × modality (one behavior may target many
    targets, but never two primary performance claims on one).
    """

    violations: list[ContractViolation] = []
    group_primary: defaultdict[tuple[str, str, str, str], list[int]] = (
        defaultdict(list)
    )
    for index, claim in enumerate(claims):
        performance = claim.performance_type
        if performance in PRODUCTION_TYPES or performance == "RECOGNITION":
            key = (
                claim.group_id,
                claim.target_type,
                claim.target_id,
                claim.modality,
            )
            group_primary[key].append(index)

        if performance in {"INDEPENDENT_PRODUCTION", "SPONTANEOUS_PRODUCTION"}:
            if claim.support_level not in {"NONE", "CONTEXT_ONLY"}:
                violations.append(
                    ContractViolation(
                        code="INDEPENDENT_WITH_ASSISTANCE",
                        claim_index=index,
                        detail=(
                            f"performance_type={performance}"
                            f" support_level={claim.support_level}"
                        ),
                    )
                )
            if claim.exposure_level != "NONE":
                violations.append(
                    ContractViolation(
                        code="INDEPENDENT_WITH_ANSWER_EXPOSURE",
                        claim_index=index,
                        detail=(
                            f"performance_type={performance}"
                            f" exposure_level={claim.exposure_level}"
                        ),
                    )
                )
        if (
            performance == "SPONTANEOUS_PRODUCTION"
            and claim.opportunity_type != "NATURAL"
        ):
            violations.append(
                ContractViolation(
                    code="SPONTANEOUS_REQUIRES_NATURAL_OPPORTUNITY",
                    claim_index=index,
                    detail=(
                        "opportunity_type="
                        f"{claim.opportunity_type!r}"
                    ),
                )
            )

    for key, indexes in group_primary.items():
        if len(indexes) > 1:
            violations.append(
                ContractViolation(
                    code="MULTIPLE_PRIMARY_PERFORMANCE_SAME_GROUP_TARGET",
                    detail=f"group_target={key} claims={indexes}",
                )
            )
    return tuple(violations)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MassDimensionState:
    """One base/transfer dimension (BF-01 §14/§15/§17).

    ``estimate`` is None ⇔ UNKNOWN (never 0). Masses are carried so the
    projection stays auditable; DATA_MODEL §11's per-dimension surface
    (estimate/confidence/last_relevant_evidence_at) is derived by the
    store record.
    """

    estimate: float | None
    confidence: float
    positive_mass: float
    negative_mass: float
    effective_mass: float
    independent_clusters: int
    last_relevant_evidence_at: str | None


@dataclass(frozen=True)
class SupportDependencyState:
    """The §21 derived dimension: burden-weighted estimate over the
    diagnostic claim mix (low_success / assisted_success / low_failure /
    supported_failure masses)."""

    estimate: float | None
    confidence: float
    effective_mass: float
    diagnostic_mass: Mapping[str, float]
    last_relevant_evidence_at: str | None


@dataclass(frozen=True)
class Coverage:
    """DATA_MODEL §11 coverage counts (BF-01 §12/§15 diversity basis).
    ``sessions`` is the distinct-conversation count (Local V1: one
    session ≡ one conversation)."""

    evidence_groups: int
    independent_clusters: int
    sessions: int
    days: int
    contexts: int
    personas: int
    realizations: int
    modalities: int


@dataclass(frozen=True)
class Freshness:
    """BF-01 §22: strong-retrieval freshness only."""

    last_strong_retrieval_at: str | None
    days_since_strong_retrieval: float | None
    band: str


@dataclass(frozen=True)
class Projection:
    """BF-01 §24 projection bands + §25 flags."""

    ability_band: str
    confidence_band: str
    transfer_band: str
    support_band: str
    stability_band: str
    learning_flags: tuple[str, ...]


@dataclass(frozen=True)
class TargetStateEstimate:
    """Full estimator output for one target_type × target_id × modality."""

    target_type: str
    target_id: str
    modality: str
    dimensions: Mapping[str, MassDimensionState | SupportDependencyState]
    coverage: Coverage
    freshness: Freshness
    projection: Projection

    def dimension(self, name: str) -> MassDimensionState | SupportDependencyState:
        return self.dimensions[name]

    def as_reference_dict(self) -> dict[str, object]:
        """Reference-comparable shape (the frozen v1.1 output contract:
        dimensions / coverage / freshness / projection). Used by the
        golden-equivalence oracle tests; ``sessions`` (§11) and the
        per-dimension ``last_relevant_evidence_at`` stay out because the
        frozen reference does not track them."""

        dimensions: dict[str, object] = {}
        for name in ABILITY_DIMENSIONS:
            dim = cast(MassDimensionState, self.dimensions[name])
            dimensions[name] = {
                "estimate": dim.estimate,
                "confidence": dim.confidence,
                "positive_mass": dim.positive_mass,
                "negative_mass": dim.negative_mass,
                "effective_mass": dim.effective_mass,
                "independent_clusters": dim.independent_clusters,
            }
        transfer = cast(MassDimensionState, self.dimensions["transfer"])
        dimensions["transfer"] = {
            "estimate": transfer.estimate,
            "confidence": transfer.confidence,
            "positive_mass": transfer.positive_mass,
            "negative_mass": transfer.negative_mass,
            "effective_mass": transfer.effective_mass,
            "independent_clusters": transfer.independent_clusters,
        }
        dependency = cast(
            SupportDependencyState, self.dimensions["support_dependency"]
        )
        dimensions["support_dependency"] = {
            "estimate": dependency.estimate,
            "confidence": dependency.confidence,
            "effective_mass": dependency.effective_mass,
            "diagnostic_mass": dict(dependency.diagnostic_mass),
        }
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "modality": self.modality,
            "dimensions": dimensions,
            "coverage": {
                "evidence_groups": self.coverage.evidence_groups,
                "independent_clusters": self.coverage.independent_clusters,
                "days": self.coverage.days,
                "contexts": self.coverage.contexts,
                "personas": self.coverage.personas,
                "realizations": self.coverage.realizations,
                "modalities": self.coverage.modalities,
            },
            "freshness": {
                "last_strong_retrieval_at": (
                    self.freshness.last_strong_retrieval_at
                ),
                "days_since_strong_retrieval": (
                    self.freshness.days_since_strong_retrieval
                ),
                "freshness_band": self.freshness.band,
            },
            "projection": {
                "ability_band": self.projection.ability_band,
                "confidence_band": self.projection.confidence_band,
                "transfer_band": self.projection.transfer_band,
                "support_band": self.projection.support_band,
                "stability_band": self.projection.stability_band,
                "learning_flags": list(self.projection.learning_flags),
            },
        }


# ---------------------------------------------------------------------------
# Internal helpers (BF-01 §5-§13, §15-§17, §22)
# ---------------------------------------------------------------------------


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assist_factor(claim: EstimatorClaimView) -> float:
    """BF-01 §8: assist = min(support_factor, exposure_factor) so one
    help source is not punished twice."""

    support = SUPPORT_FACTOR.get(claim.support_level, 1.0)
    exposure = EXPOSURE_FACTOR.get(claim.exposure_level, 1.0)
    return min(support, exposure)


def _error_multiplier(claim: EstimatorClaimView) -> float:
    if claim.error_attribution is None:
        return ERROR_ATTRIBUTION_DEFAULT_MULTIPLIER
    return ERROR_ATTRIBUTION_MULTIPLIER.get(
        claim.error_attribution, ERROR_ATTRIBUTION_DEFAULT_MULTIPLIER
    )


def _cluster_key(claim: EstimatorClaimView) -> str:
    """BF-01 §12 correlation cluster key. Teaching attempts inside one
    TeachingMoment are one cluster; natural evidence clusters by
    conversation × day × context × realization × persona with documented
    fallbacks (a CROSS_CONTEXT/HIGH_CONTEXT_NOVELTY-qualified claim
    without a context key is its own novel context; likewise
    NOVEL_REALIZATION)."""

    if claim.teaching_moment_id:
        return "teach:" + claim.teaching_moment_id
    day = _parse_dt(claim.timestamp).date().isoformat()
    if claim.context_key:
        context = claim.context_key
    elif "CROSS_CONTEXT" in claim.qualifiers or (
        "HIGH_CONTEXT_NOVELTY" in claim.qualifiers
    ):
        context = "novel:" + claim.group_id
    else:
        context = "context:unknown"
    if claim.realization_key:
        realization = claim.realization_key
    elif "NOVEL_REALIZATION" in claim.qualifiers:
        realization = "novel:" + claim.group_id
    else:
        realization = "realization:unknown"
    persona = claim.persona_id or "persona:none"
    conversation = claim.conversation_id or "conv:none"
    return f"natural:{conversation}:{day}:{context}:{realization}:{persona}"


def _negative_dimension_map(claim: EstimatorClaimView) -> dict[str, float]:
    """BF-01 §6 negative propagation boundaries (asymmetric): a natural
    low-support failure diagnoses spontaneous + independent (the attempted
    behavior itself), an elicited low-support failure diagnoses
    independent, a supported failure diagnoses guided, and recognition
    failures stay on recognition. Spontaneous failure never propagates to
    guided/recognition. MISUSE is primarily an accuracy negative with an
    optional weak production negative where the opportunity directly
    supports it."""

    performance = claim.performance_type
    low_support = claim.support_level in {"NONE", "CONTEXT_ONLY"}

    if performance == "RECOGNITION":
        return {"recognition": 1.0}
    if performance == "FAILED_ATTEMPT":
        if claim.opportunity_type == "NATURAL" and low_support:
            return {
                "spontaneous_production": 1.0,
                "independent_production": 0.75,
            }
        if low_support:
            return {"independent_production": 1.0}
        return {"guided_production": 1.0}
    if performance == "MISUSE":
        out: dict[str, float] = {"accuracy": 1.0}
        if claim.opportunity_type == "NATURAL" and low_support:
            out["spontaneous_production"] = 0.50
            out["independent_production"] = 0.50
        elif low_support:
            out["independent_production"] = 0.50
        else:
            out["guided_production"] = 0.50
        return out
    return {}


def _claim_contribution(
    claim: EstimatorClaimView,
) -> tuple[dict[str, float], dict[str, float]]:
    """Positive/negative dimension mass of one claim (BF-01 §5/§6/§8/§9/
    §10/§27). Returns (positive, negative) mappings — keys are dimension
    names touched with mass > 0."""

    positive: defaultdict[str, float] = defaultdict(float)
    negative: defaultdict[str, float] = defaultdict(float)
    confidence = float(claim.evaluator_confidence)

    # §10 evaluator-confidence floor + ABSTAIN: no state mass at all.
    if confidence < CLAIM_MIN_CONFIDENCE or claim.outcome == "ABSTAIN":
        return dict(positive), dict(negative)

    outcome_factor = OUTCOME_FACTOR.get(claim.outcome, 1.0)
    performance = claim.performance_type

    if claim.polarity == "POSITIVE" and performance in POSITIVE_MAPPING:
        assist = _assist_factor(claim)
        for dim, weight in POSITIVE_MAPPING[performance].items():
            positive[dim] += weight * outcome_factor * confidence * assist

        # §9 v1.1: PARTIAL is mixed evidence — the direct dimension also
        # takes a residual negative share so repeated partial performance
        # converges to partial control, never to 1.0.
        if claim.outcome == "PARTIAL" and performance in DIRECT_DIMENSION:
            direct = DIRECT_DIMENSION[performance]
            direct_weight = POSITIVE_MAPPING[performance].get(direct, 1.0)
            negative[direct] += (
                direct_weight
                * PARTIAL_DIRECT_NEGATIVE_FRACTION
                * confidence
                * assist
            )

        # §5 conditional spontaneous support + §16: only a low-exposure
        # spontaneous self-repair supports the spontaneous dimension.
        if (
            performance == "SELF_REPAIR"
            and claim.spontaneity == "SPONTANEOUS"
            and claim.exposure_level != "FULL"
        ):
            positive["spontaneous_production"] += (
                SELF_REPAIR_SPONTANEOUS_SUPPORT
                * outcome_factor
                * confidence
                * assist
            )
            if claim.outcome == "PARTIAL":
                negative["spontaneous_production"] += (
                    SELF_REPAIR_SPONTANEOUS_SUPPORT
                    * float(PARTIAL_DIRECT_NEGATIVE_FRACTION)
                    * confidence
                    * assist
                )

        # §27 quality dimensions: positive ∝ q, negative ∝ (1-q).
        quality_strength = (
            QUALITY_STRENGTH.get(performance, 0.0)
            * outcome_factor
            * confidence
            * assist
        )
        if claim.accuracy is not None and quality_strength > 0:
            q = min(1.0, max(0.0, float(claim.accuracy)))
            positive["accuracy"] += quality_strength * q
            negative["accuracy"] += quality_strength * (1 - q)
        if claim.pragmatic_fit is not None and quality_strength > 0:
            q = min(1.0, max(0.0, float(claim.pragmatic_fit)))
            positive["pragmatic_control"] += quality_strength * q
            negative["pragmatic_control"] += quality_strength * (1 - q)

    if claim.polarity == "NEGATIVE":
        error_multiplier = _error_multiplier(claim)
        for dim, weight in _negative_dimension_map(claim).items():
            negative[dim] += weight * outcome_factor * confidence * error_multiplier

    return dict(positive), dict(negative)


def _aggregate_group(
    claims: Sequence[EstimatorClaimView],
) -> tuple[dict[str, float], dict[str, float]]:
    """BF-01 §11 EvidenceGroup dedup: same group keeps only the
    strongest contribution per dimension × polarity (one utterance must
    not be counted once per evaluator path)."""

    group_positive: defaultdict[str, float] = defaultdict(float)
    group_negative: defaultdict[str, float] = defaultdict(float)
    for claim in claims:
        positive, negative = _claim_contribution(claim)
        for dim, value in positive.items():
            group_positive[dim] = max(group_positive[dim], value)
        for dim, value in negative.items():
            group_negative[dim] = max(group_negative[dim], value)
    return dict(group_positive), dict(group_negative)


def _aggregate_cluster(
    group_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, float], dict[str, float]]:
    """BF-01 §13 same-cluster diminishing returns: per dimension ×
    polarity, timestamp-ordered repeat weights with a same-cluster mass
    cap — three repetitions inside one correlated cluster never equal
    three independent cross-day/cross-context occurrences."""

    out_positive: defaultdict[str, float] = defaultdict(float)
    out_negative: defaultdict[str, float] = defaultdict(float)
    ordered = sorted(
        group_rows, key=lambda row: cast(datetime, row["timestamp"])
    )

    for dim in ABILITY_DIMENSIONS:
        for side, out in (("p", out_positive), ("n", out_negative)):
            values: list[float] = []
            for row in ordered:
                source = cast(Mapping[str, float], row[side])
                value = source.get(dim, 0.0)
                if value > 0:
                    values.append(value)
            if not values:
                continue
            total = 0.0
            for index, value in enumerate(values):
                weight = (
                    SAME_CLUSTER_REPEAT_WEIGHTS[index]
                    if index < len(SAME_CLUSTER_REPEAT_WEIGHTS)
                    else SAME_CLUSTER_REPEAT_WEIGHTS[-1]
                )
                total += weight * value
            total = min(total, SAME_CLUSTER_MASS_CAP_MULTIPLE * max(values))
            out[dim] = total
    return dict(out_positive), dict(out_negative)


def _confidence_value(
    total_mass: float,
    diversity: Mapping[str, int],
    target_type: str,
    dimension: str,
) -> float:
    """BF-01 §15 confidence: saturation from effective mass, a bounded
    diversity bonus, and the §19 capability caps. Diversity never raises
    the ability estimate itself."""

    if total_mass <= 0:
        return 0.0
    mass_confidence = 1.0 - math.exp(-total_mass / CONFIDENCE_TAU)
    extra = (
        DIVERSITY_BONUS_WEIGHTS["days"] * max(0, diversity["days"] - 1)
        + DIVERSITY_BONUS_WEIGHTS["contexts"] * max(0, diversity["contexts"] - 1)
        + DIVERSITY_BONUS_WEIGHTS["personas"] * max(0, diversity["personas"] - 1)
        + DIVERSITY_BONUS_WEIGHTS["realizations"]
        * max(0, diversity["realizations"] - 1)
    )
    diversity_confidence = 1.0 - math.exp(-extra)
    confidence = mass_confidence * (0.80 + 0.20 * diversity_confidence)

    if target_type == "CAPABILITY":
        if dimension in {
            "independent_production",
            "spontaneous_production",
            "pragmatic_control",
        } and diversity["realizations"] < 2:
            confidence = min(
                confidence, CAPABILITY_REALIZATION_DIVERSITY_CAP
            )
    return min(1.0, max(0.0, confidence))


def _confidence_band(confidence: float) -> str:
    if confidence <= CONFIDENCE_BAND_LOW_MAX:
        return "LOW"
    if confidence <= CONFIDENCE_BAND_MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


def _is_strong_retrieval(claim: EstimatorClaimView) -> bool:
    """BF-01 §16/§17 strong-retrieval membership: POSITIVE SUCCESS at
    INDEPENDENT/SPONTANEOUS (or an eligible SELF_REPAIR — spontaneity ∈
    {INDEPENDENT, SPONTANEOUS}) with evaluator confidence ≥ 0.70 and
    assist ≥ 0.70. Guided self-repair stays ordinary evidence."""

    if claim.polarity != "POSITIVE" or claim.outcome != "SUCCESS":
        return False
    performance = claim.performance_type
    if performance not in {
        "INDEPENDENT_PRODUCTION",
        "SPONTANEOUS_PRODUCTION",
        "SELF_REPAIR",
    }:
        return False
    if performance == "SELF_REPAIR" and claim.spontaneity not in {
        "INDEPENDENT",
        "SPONTANEOUS",
    }:
        return False
    if claim.evaluator_confidence < STRONG_RETRIEVAL_MIN_CONFIDENCE:
        return False
    if _assist_factor(claim) < STRONG_RETRIEVAL_MIN_ASSIST:
        return False
    return True


# ---------------------------------------------------------------------------
# The estimator (BF-01 §2: pure deterministic projection)
# ---------------------------------------------------------------------------


def estimate_target_state(
    claims: Sequence[EstimatorClaimView],
    *,
    target_type: str,
    target_id: str,
    modality: str,
    as_of: str | datetime,
    strict: bool = True,
) -> TargetStateEstimate:
    """Estimate the LearnerTargetState of one target_type × target_id ×
    modality (BF-01 §3) from the ACTIVE canonical claims.

    ``strict=True`` (default) refuses §7 contract violations loudly
    (EstimatorContractError) so canonical corruption is never silently
    computed; ``strict=False`` computes past them (diagnostic use only).
    """

    contract_violations = validate_claims(claims)
    if contract_violations and strict:
        raise EstimatorContractError(contract_violations)

    # §29 only ACTIVE evidence enters estimation; §3/§28 the estimator
    # consumes only this target × modality's claims.
    active = [
        claim
        for claim in claims
        if claim.status == "ACTIVE"
        and claim.target_type == target_type
        and claim.target_id == target_id
        and claim.modality == modality
    ]

    # §11 EvidenceGroup aggregation (insertion order pinned, §30).
    by_group: defaultdict[str, list[EstimatorClaimView]] = defaultdict(list)
    for claim in active:
        by_group[claim.group_id].append(claim)

    # DATA_MODEL §11 per-dimension last_relevant_evidence_at: claims
    # whose contribution touched the dimension (pre-dedup view).
    dim_last: defaultdict[str, str] = defaultdict(str)

    group_rows: list[dict[str, object]] = []
    for group_id, group_claims in by_group.items():
        group_positive, group_negative = _aggregate_group(group_claims)
        for claim in group_claims:
            claim_positive, claim_negative = _claim_contribution(claim)
            for dim in set(claim_positive) | set(claim_negative):
                if claim_positive.get(dim, 0.0) > 0 or claim_negative.get(
                    dim, 0.0
                ) > 0:
                    if claim.timestamp > dim_last[dim]:
                        dim_last[dim] = claim.timestamp
        exemplar = sorted(
            group_claims, key=lambda claim: _parse_dt(claim.timestamp)
        )[0]
        group_rows.append(
            {
                "group_id": group_id,
                "timestamp": _parse_dt(exemplar.timestamp),
                "cluster": _cluster_key(exemplar),
                "p": group_positive,
                "n": group_negative,
                "claims": list(group_claims),
            }
        )

    # §12 EvidenceCluster aggregation.
    by_cluster: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for row in group_rows:
        by_cluster[str(row["cluster"])].append(row)

    total_positive: defaultdict[str, float] = defaultdict(float)
    total_negative: defaultdict[str, float] = defaultdict(float)
    dim_meta: dict[str, dict[str, set[str]]] = {
        dim: {
            "days": set(),
            "contexts": set(),
            "personas": set(),
            "realizations": set(),
            "clusters": set(),
        }
        for dim in ABILITY_DIMENSIONS
    }

    for cluster_key, rows in by_cluster.items():
        cluster_positive, cluster_negative = _aggregate_cluster(rows)
        for dim in ABILITY_DIMENSIONS:
            value = cluster_positive.get(dim, 0.0)
            if value > 0:
                total_positive[dim] += value
            value = cluster_negative.get(dim, 0.0)
            if value > 0:
                total_negative[dim] += value
        for dim in ABILITY_DIMENSIONS:
            if (
                cluster_positive.get(dim, 0) > 0
                or cluster_negative.get(dim, 0) > 0
            ):
                meta = dim_meta[dim]
                meta["clusters"].add(cluster_key)
                for row in rows:
                    row_claims = cast(
                        list[EstimatorClaimView], row["claims"]
                    )
                    for claim in row_claims:
                        meta["days"].add(
                            _parse_dt(claim.timestamp).date().isoformat()
                        )
                        meta["contexts"].add(claim.context_key or "unknown")
                        if claim.persona_id:
                            meta["personas"].add(claim.persona_id)
                        meta["realizations"].add(
                            claim.realization_key or "unknown"
                        )

    dimensions: dict[str, MassDimensionState | SupportDependencyState] = {}
    for dim in ABILITY_DIMENSIONS:
        positive_mass = total_positive[dim]
        negative_mass = total_negative[dim]
        effective_mass = positive_mass + negative_mass
        counts = {
            "days": len(dim_meta[dim]["days"]),
            "contexts": len(dim_meta[dim]["contexts"]),
            "personas": len(dim_meta[dim]["personas"]),
            "realizations": len(dim_meta[dim]["realizations"]),
            "clusters": len(dim_meta[dim]["clusters"]),
        }
        if effective_mass < DIMENSION_MIN_EFFECTIVE_MASS:
            estimate: float | None = None
            confidence = (
                0.0
                if effective_mass == 0
                else _confidence_value(
                    effective_mass, counts, target_type, dim
                )
            )
        else:
            estimate = positive_mass / effective_mass
            confidence = _confidence_value(
                effective_mass, counts, target_type, dim
            )
        dimensions[dim] = MassDimensionState(
            estimate=None if estimate is None else round(estimate, 4),
            confidence=round(confidence, 4),
            positive_mass=round(positive_mass, 4),
            negative_mass=round(negative_mass, 4),
            effective_mass=round(effective_mass, 4),
            independent_clusters=counts["clusters"],
            last_relevant_evidence_at=dim_last.get(dim) or None,
        )

    # §17 transfer — strong-retrieval clusters only, v1.1 cluster dedup:
    # one representative per strong cluster; repeated uses inside one new
    # condition never multiply transfer mass.
    strong = [claim for claim in active if _is_strong_retrieval(claim)]
    strong_by_cluster: defaultdict[str, list[EstimatorClaimView]] = (
        defaultdict(list)
    )
    for claim in strong:
        strong_by_cluster[_cluster_key(claim)].append(claim)

    strong_cluster_rows: list[dict[str, object]] = []
    for cluster_key, cluster_claims in strong_by_cluster.items():
        representative = max(
            cluster_claims,
            key=lambda claim: (
                claim.evaluator_confidence * _assist_factor(claim),
                _parse_dt(claim.timestamp),
            ),
        )
        strong_cluster_rows.append(
            {
                "cluster": cluster_key,
                "timestamp": _parse_dt(representative.timestamp),
                "context": representative.context_key or "unknown",
                "persona": representative.persona_id or "none",
                "realization": representative.realization_key or "unknown",
                "mass": representative.evaluator_confidence
                * _assist_factor(representative),
                "claim": representative,
            }
        )
    strong_cluster_rows.sort(
        key=lambda row: cast(datetime, row["timestamp"])
    )

    transfer_positive = 0.0
    transfer_negative = 0.0
    if strong_cluster_rows:
        base = strong_cluster_rows[0]
        for row in strong_cluster_rows[1:]:
            claim = cast(EstimatorClaimView, row["claim"])
            diverse = (
                row["context"] != base["context"]
                or row["persona"] != base["persona"]
                or row["realization"] != base["realization"]
                or any(
                    qualifier
                    in {
                        "CROSS_CONTEXT",
                        "CROSS_PERSONA",
                        "NOVEL_REALIZATION",
                        "CROSS_MODALITY",
                    }
                    for qualifier in claim.qualifiers
                )
            )
            if diverse:
                transfer_positive += cast(float, row["mass"])

    # Negative transfer evidence is cluster-deduped too (§17 v1.1).
    negative_transfer_by_cluster: defaultdict[str, list[float]] = (
        defaultdict(list)
    )
    for claim in active:
        if claim.polarity == "NEGATIVE" and claim.performance_type in {
            "FAILED_ATTEMPT",
            "MISUSE",
        }:
            if any(
                qualifier
                in {
                    "CROSS_CONTEXT",
                    "CROSS_PERSONA",
                    "NOVEL_REALIZATION",
                    "CROSS_MODALITY",
                }
                for qualifier in claim.qualifiers
            ):
                negative_transfer_by_cluster[_cluster_key(claim)].append(
                    claim.evaluator_confidence * _error_multiplier(claim)
                )
    for values in negative_transfer_by_cluster.values():
        transfer_negative += max(values)

    strong_clusters = set(strong_by_cluster)
    strong_contexts = {
        str(row["context"]) for row in strong_cluster_rows
    }
    strong_personas = {
        str(row["persona"]) for row in strong_cluster_rows
    }
    strong_realizations = {
        str(row["realization"]) for row in strong_cluster_rows
    }
    strong_days = {
        cast(datetime, row["timestamp"]).date().isoformat()
        for row in strong_cluster_rows
    }
    transfer_mass = transfer_positive + transfer_negative

    # §18 resource transfer gate; §19 capability adds realization
    # diversity (a fixed expression across many scenes does not prove a
    # CommunicativeCapability's realization transfer).
    transfer_gate = len(strong_clusters) >= 2 and (
        len(strong_contexts) >= 2
        or len(strong_personas) >= 2
        or len(strong_realizations) >= 2
    )
    if target_type == "CAPABILITY":
        transfer_gate = transfer_gate and len(strong_realizations) >= 2

    if transfer_gate and transfer_mass >= DIMENSION_MIN_EFFECTIVE_MASS:
        transfer_estimate: float | None = (
            transfer_positive / transfer_mass if transfer_mass else None
        )
        transfer_meta = {
            "days": len(strong_days),
            "contexts": len(strong_contexts),
            "personas": len(strong_personas),
            "realizations": len(strong_realizations),
            "clusters": len(strong_clusters),
        }
        transfer_confidence = _confidence_value(
            transfer_mass, transfer_meta, target_type, "transfer"
        )
        if target_type == "CAPABILITY" and len(strong_contexts) < 2:
            transfer_confidence = min(
                transfer_confidence,
                CAPABILITY_TRANSFER_CONTEXT_DIVERSITY_CAP,
            )
    else:
        transfer_estimate = None
        transfer_confidence = 0.0
    if strong:
        transfer_last = max(claim.timestamp for claim in strong)
    else:
        transfer_last = ""
    dimensions["transfer"] = MassDimensionState(
        estimate=(
            None if transfer_estimate is None else round(transfer_estimate, 4)
        ),
        confidence=round(transfer_confidence, 4),
        positive_mass=round(transfer_positive, 4),
        negative_mass=round(transfer_negative, 4),
        effective_mass=round(transfer_mass, 4),
        independent_clusters=len(strong_clusters),
        last_relevant_evidence_at=transfer_last or None,
    )

    # §21 support dependency — NOT inferable from repeated unsupported
    # failure alone (that only proves a gap). High dependency needs the
    # comparable-condition diagnostic (low-support failure + assisted
    # success, ideally across Moments/clusters); low dependency is
    # established by repeated low-support success; assisted success
    # without any low-support opportunity leaves it UNKNOWN.
    dependency_observations: list[dict[str, object]] = []
    for group_id, group_claims in by_group.items():
        candidates = [
            claim
            for claim in group_claims
            if claim.performance_type in PRODUCTION_TYPES
            and claim.evaluator_confidence >= CLAIM_MIN_CONFIDENCE
        ]
        if not candidates:
            continue
        # Strongest diagnostic claim for this target/group.
        claim = max(
            candidates, key=lambda item: item.evaluator_confidence
        )
        confidence = claim.evaluator_confidence
        if claim.polarity == "POSITIVE" and claim.outcome in {
            "SUCCESS",
            "PARTIAL",
        }:
            burden = max(
                SUPPORT_BURDEN.get(claim.support_level, 0.0),
                EXPOSURE_BURDEN.get(claim.exposure_level, 0.0),
            )
            mass = confidence * OUTCOME_FACTOR.get(claim.outcome, 1.0)
            kind = "low_success" if burden <= 0.10 else "assisted_success"
        elif claim.polarity == "NEGATIVE" and claim.outcome in {
            "FAILURE",
            "PARTIAL",
        }:
            burden = 1.0
            mass = (
                confidence
                * _error_multiplier(claim)
                * OUTCOME_FACTOR.get(claim.outcome, 1.0)
            )
            kind = (
                "low_failure"
                if claim.support_level in {"NONE", "CONTEXT_ONLY"}
                else "supported_failure"
            )
        else:
            continue
        dependency_observations.append(
            {
                "cluster": _cluster_key(claim),
                "timestamp": _parse_dt(claim.timestamp),
                "burden": burden,
                "mass": mass,
                "kind": kind,
                "iso": claim.timestamp,
            }
        )

    # Correlated repeats diminish here too (§13 discipline).
    dependency_numerator = 0.0
    dependency_denominator = 0.0
    kind_mass: defaultdict[str, float] = defaultdict(float)
    by_dependency_cluster: defaultdict[str, list[dict[str, object]]] = (
        defaultdict(list)
    )
    for observation in dependency_observations:
        by_dependency_cluster[str(observation["cluster"])].append(
            observation
        )
    for cluster_observations in by_dependency_cluster.values():
        ordered = sorted(
            cluster_observations,
            key=lambda item: cast(datetime, item["timestamp"]),
        )
        for index, observation in enumerate(ordered):
            repeat_weight = (
                SAME_CLUSTER_REPEAT_WEIGHTS[index]
                if index < len(SAME_CLUSTER_REPEAT_WEIGHTS)
                else SAME_CLUSTER_REPEAT_WEIGHTS[-1]
            )
            effective = cast(float, observation["mass"]) * repeat_weight
            dependency_denominator += effective
            dependency_numerator += (
                cast(float, observation["burden"]) * effective
            )
            kind_mass[str(observation["kind"])] += effective

    dependency_identifiable = (
        kind_mass["low_success"] >= SUPPORT_DEPENDENCY_MIN_MASS
        or (
            kind_mass["assisted_success"] >= 0.50
            and kind_mass["low_failure"] >= 0.50
        )
    )
    if (
        dependency_identifiable
        and dependency_denominator >= SUPPORT_DEPENDENCY_MIN_MASS
    ):
        dependency_estimate: float | None = (
            dependency_numerator / dependency_denominator
        )
        dependency_meta = {
            "days": len(
                {
                    _parse_dt(claim.timestamp).date().isoformat()
                    for claim in active
                }
            ),
            "contexts": len(
                {claim.context_key or "unknown" for claim in active}
            ),
            "personas": len(
                {claim.persona_id or "none" for claim in active}
            ),
            "realizations": len(
                {claim.realization_key or "unknown" for claim in active}
            ),
            "clusters": len(by_dependency_cluster),
        }
        dependency_confidence = _confidence_value(
            dependency_denominator,
            dependency_meta,
            target_type,
            "support_dependency",
        )
    else:
        dependency_estimate = None
        dependency_confidence = 0.0
    if dependency_observations:
        dependency_last = max(
            str(observation["iso"]) for observation in dependency_observations
        )
    else:
        dependency_last = ""
    dimensions["support_dependency"] = SupportDependencyState(
        estimate=(
            None
            if dependency_estimate is None
            else round(dependency_estimate, 4)
        ),
        confidence=round(dependency_confidence, 4),
        effective_mass=round(dependency_denominator, 4),
        diagnostic_mass={
            kind: round(mass, 4) for kind, mass in kind_mass.items()
        },
        last_relevant_evidence_at=dependency_last or None,
    )

    # DATA_MODEL §11 coverage (sessions = distinct conversations).
    coverage = Coverage(
        evidence_groups=len(by_group),
        independent_clusters=len(by_cluster),
        sessions=len(
            {claim.conversation_id or "none" for claim in active}
        ),
        days=len(
            {_parse_dt(claim.timestamp).date().isoformat() for claim in active}
        ),
        contexts=len({claim.context_key or "unknown" for claim in active}),
        personas=len({claim.persona_id or "none" for claim in active}),
        realizations=len(
            {claim.realization_key or "unknown" for claim in active}
        ),
        modalities=len({claim.modality for claim in active}),
    )

    # §22 freshness — strong retrieval only; time never changes mass.
    if strong:
        last_strong = max(_parse_dt(claim.timestamp) for claim in strong)
        days_since = max(
            0.0, (_parse_dt(as_of) - last_strong).total_seconds() / 86400
        )
        if days_since <= FRESHNESS_DAYS_FRESH_MAX:
            freshness_band = "FRESH"
        elif days_since <= FRESHNESS_DAYS_AGING_MAX:
            freshness_band = "AGING"
        else:
            freshness_band = "STALE"
        freshness = Freshness(
            last_strong_retrieval_at=last_strong.isoformat(),
            days_since_strong_retrieval=round(days_since, 2),
            band=freshness_band,
        )
    else:
        freshness = Freshness(
            last_strong_retrieval_at=None,
            days_since_strong_retrieval=None,
            band="UNKNOWN",
        )

    # §24 projection bands (hierarchy-conflict blocking).
    spontaneous = cast(
        MassDimensionState, dimensions["spontaneous_production"]
    ).estimate
    independent = cast(
        MassDimensionState, dimensions["independent_production"]
    ).estimate
    guided = cast(
        MassDimensionState, dimensions["guided_production"]
    ).estimate

    def _confirmed_gap(dim_name: str) -> bool:
        state = cast(MassDimensionState, dimensions[dim_name])
        return (
            state.estimate is not None
            and state.estimate <= CONFIRMED_GAP_ESTIMATE_MAX
            and state.confidence >= CONFIRMED_GAP_CONFIDENCE_MIN
        )

    # §24 v1.1: a higher tier is blocked when its lower prerequisite
    # tier has a high-confidence confirmed gap — one anomalous strong
    # event must not headline over stable counter-evidence.
    if (
        spontaneous is not None
        and spontaneous >= 0.75
        and not _confirmed_gap("independent_production")
    ):
        ability_band = "SPONTANEOUS"
    elif (
        independent is not None
        and independent >= 0.75
        and not _confirmed_gap("guided_production")
    ):
        ability_band = "INDEPENDENT"
    elif guided is not None and guided >= 0.75:
        ability_band = "GUIDED"
    elif any(
        cast(MassDimensionState, dimensions[name]).estimate is not None
        for name in (
            "guided_production",
            "independent_production",
            "spontaneous_production",
        )
    ):
        ability_band = "EARLY"
    else:
        ability_band = "UNKNOWN"

    if ability_band == "SPONTANEOUS":
        focus_confidence = cast(
            MassDimensionState, dimensions["spontaneous_production"]
        ).confidence
    elif ability_band == "INDEPENDENT":
        focus_confidence = cast(
            MassDimensionState, dimensions["independent_production"]
        ).confidence
    elif ability_band == "GUIDED":
        focus_confidence = cast(
            MassDimensionState, dimensions["guided_production"]
        ).confidence
    else:
        focus_confidence = max(
            cast(MassDimensionState, dimensions[name]).confidence
            for name in (
                "recognition",
                "guided_production",
                "independent_production",
                "spontaneous_production",
            )
        )
    confidence_band = _confidence_band(focus_confidence)

    transfer_dimension = cast(MassDimensionState, dimensions["transfer"])
    if transfer_dimension.estimate is None:
        if (independent is not None and independent >= 0.75) or (
            spontaneous is not None and spontaneous >= 0.75
        ):
            transfer_band = "NARROW"
        else:
            transfer_band = "UNTESTED"
    else:
        if len(strong_contexts) >= 3 and len(strong_clusters) >= 3:
            transfer_band = "MULTI_CONTEXT"
        else:
            transfer_band = "CROSS_CONTEXT"

    dependency = dimensions["support_dependency"]
    dependency_estimate_value = dependency.estimate
    if dependency_estimate_value is None:
        support_band = "UNKNOWN"
    elif dependency_estimate_value >= 0.75:
        support_band = "HIGH_SUPPORT"
    elif dependency_estimate_value >= 0.50:
        support_band = "PARTIAL_SUPPORT"
    elif dependency_estimate_value >= 0.20:
        support_band = "LOW_SUPPORT"
    else:
        support_band = "INDEPENDENT"

    # §23 stability — strong-retrieval clusters / strong-day diversity /
    # freshness only (a low-confidence claim on another day can never
    # upgrade one strong day to STABLE).
    if not strong:
        stability_band = "UNTESTED"
    elif len(strong_clusters) < 2:
        stability_band = "FRAGILE"
    elif freshness.band == "STALE":
        stability_band = "STALE"
    elif len(strong_clusters) >= 4 and len(strong_days) >= 2:
        stability_band = "STABLE"
    else:
        stability_band = freshness.band

    # §25/§26 flags.
    flags: list[str] = []
    production_known = [
        cast(MassDimensionState, dimensions[name])
        for name in (
            "spontaneous_production",
            "independent_production",
            "guided_production",
        )
        if cast(MassDimensionState, dimensions[name]).estimate is not None
    ]
    if production_known:
        best = max(production_known, key=lambda state: state.confidence)
        if (
            best.estimate is not None
            and best.estimate <= CONFIRMED_GAP_ESTIMATE_MAX
            and best.confidence >= CONFIRMED_GAP_CONFIDENCE_MIN
        ):
            flags.append("CONFIRMED_GAP")
    if (
        dependency_estimate_value is not None
        and dependency_estimate_value >= SUPPORT_DEPENDENT_ESTIMATE_MIN
        and dependency.confidence >= SUPPORT_DEPENDENT_CONFIDENCE_MIN
    ):
        flags.append("SUPPORT_DEPENDENT")
    if (
        independent is not None
        and independent >= STRONG_CONTROL_ESTIMATE_MIN
        and cast(
            MassDimensionState, dimensions["independent_production"]
        ).confidence
        >= STRONG_CONTROL_CONFIDENCE_MIN
    ):
        flags.append("STRONG_INDEPENDENT_CONTROL")
    if (
        spontaneous is not None
        and spontaneous >= STRONG_CONTROL_ESTIMATE_MIN
        and cast(
            MassDimensionState, dimensions["spontaneous_production"]
        ).confidence
        >= STRONG_CONTROL_CONFIDENCE_MIN
    ):
        flags.append("STRONG_SPONTANEOUS_CONTROL")

    # §20 v1.1: NARROW_EVIDENCE looks only at strong-retrieval
    # diversity — invalid/low-confidence/pure-failure evidence cannot
    # fake breadth.
    if ability_band in {"INDEPENDENT", "SPONTANEOUS"} and (
        len(strong_contexts) < 2 or len(strong_realizations) < 2
    ):
        flags.append("NARROW_EVIDENCE")

    # Within-dimension conflict.
    for dim in ABILITY_DIMENSIONS:
        state = cast(MassDimensionState, dimensions[dim])
        total = state.positive_mass + state.negative_mass
        if (
            state.positive_mass >= CONFLICT_MASS_MIN_EACH
            and state.negative_mass >= CONFLICT_MASS_MIN_EACH
        ):
            ratio = state.positive_mass / total if total else 0.5
            if CONFLICT_RATIO_LOW <= ratio <= CONFLICT_RATIO_HIGH:
                flags.append("CONFLICTING_EVIDENCE")
                break

    # §24 cross-dimensional hierarchy conflict.
    if (
        spontaneous is not None
        and spontaneous >= 0.75
        and _confirmed_gap("independent_production")
    ) or (
        independent is not None
        and independent >= 0.75
        and _confirmed_gap("guided_production")
    ):
        flags.append("CONFLICTING_EVIDENCE")

    if all(
        cast(MassDimensionState, dimensions[name]).estimate is None
        for name in (
            "recognition",
            "guided_production",
            "independent_production",
            "spontaneous_production",
        )
    ):
        flags.append("INSUFFICIENT_EVIDENCE")

    projection = Projection(
        ability_band=ability_band,
        confidence_band=confidence_band,
        transfer_band=transfer_band,
        support_band=support_band,
        stability_band=stability_band,
        learning_flags=tuple(sorted(set(flags))),
    )

    return TargetStateEstimate(
        target_type=target_type,
        target_id=target_id,
        modality=modality,
        dimensions=dimensions,
        coverage=coverage,
        freshness=freshness,
        projection=projection,
    )
