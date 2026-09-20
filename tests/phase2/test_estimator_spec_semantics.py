"""VAL ① — BF-01 v1.1 section-by-section semantic pins on the src
estimator (direct spec assertions, independent of the oracle and the
golden pack — those live in test_estimator_golden_equivalence).

Section map pinned here: §5 topology, §6 negative asymmetry, §8
support/exposure, §9 PARTIAL convergence, §10 confidence floor, §11
group dedup, §12/§13 cluster correlation + diminishing returns, §14
UNKNOWN threshold + ability/confidence separation, §15 diversity bonus,
§16 self-repair restriction, §18/§19 transfer gates, §20 strong-only
NARROW_EVIDENCE, §21 assisted-only UNKNOWN, §22 freshness bands +
mass immutability, §23 stability, §24 hierarchy-conflict blocking, §27
quality split, §28 modality isolation, §29 status filter.
"""

from __future__ import annotations

import pytest

from elc.learning.estimator import (
    EstimatorClaimView,
    estimate_target_state,
)

AS_OF = "2026-09-20T10:00:00+00:00"


def claim(
    index: int,
    *,
    group_id: str | None = None,
    performance_type: str = "SPONTANEOUS_PRODUCTION",
    polarity: str = "POSITIVE",
    outcome: str = "SUCCESS",
    support_level: str = "NONE",
    exposure_level: str = "NONE",
    opportunity_type: str = "NATURAL",
    qualifiers: tuple[str, ...] = (),
    error_attribution: str = "UNKNOWN",
    accuracy: float | None = None,
    pragmatic_fit: float | None = None,
    conversation_id: str = "c1",
    teaching_moment_id: str | None = None,
    persona_id: str = "p1",
    context_key: str = "ctx1",
    realization_key: str = "r1",
    day: str = "2026-09-01",
    minute: int = 0,
    modality: str = "TEXT_PRODUCTION",
    status: str = "ACTIVE",
    spontaneity: str | None = None,
    target_type: str = "RESOURCE",
    evaluator_confidence: float = 0.95,
) -> EstimatorClaimView:
    return EstimatorClaimView(
        group_id=group_id if group_id is not None else f"g{index}",
        timestamp=f"{day}T10:{minute:02d}:00+00:00",
        performance_type=performance_type,
        polarity=polarity,
        outcome=outcome,
        evaluator_confidence=evaluator_confidence,
        support_level=support_level,
        exposure_level=exposure_level,
        opportunity_type=opportunity_type,
        qualifiers=qualifiers,
        error_attribution=error_attribution,
        accuracy=accuracy,
        pragmatic_fit=pragmatic_fit,
        conversation_id=conversation_id,
        teaching_moment_id=teaching_moment_id,
        persona_id=persona_id,
        context_key=context_key,
        realization_key=realization_key,
        target_type=target_type,
        target_id="expr.test",
        modality=modality,
        status=status,
        spontaneity=spontaneity,
    )


def estimate(claims, *, target_type: str = "RESOURCE", as_of: str = AS_OF):
    return estimate_target_state(
        claims,
        target_type=target_type,
        target_id="expr.test",
        modality="TEXT_PRODUCTION",
        as_of=as_of,
    )


# -- §5 positive performance topology --------------------------------------


def test_positive_downward_entailment_is_one_evidence_many_dimensions():
    state = estimate([claim(1)])
    dims = state.dimensions
    # One SPONTANEOUS success weakly supports the lower tiers.
    assert dims["recognition"].positive_mass > 0
    assert dims["guided_production"].positive_mass > 0
    assert dims["independent_production"].positive_mass > 0
    assert dims["spontaneous_production"].positive_mass > 0
    # ...but it is ONE piece of evidence, not four: each tier's mass is
    # bounded by the single claim's strength.
    assert dims["spontaneous_production"].positive_mass == pytest.approx(
        0.95
    )
    assert dims["recognition"].positive_mass == pytest.approx(0.9 * 0.95)


def test_imitative_production_is_weak_guided_support_only():
    state = estimate(
        [
            claim(
                1,
                performance_type="IMITATIVE_PRODUCTION",
                opportunity_type="ELICITED",
            )
        ]
    )
    dims = state.dimensions
    assert dims["independent_production"].estimate is None
    assert dims["spontaneous_production"].estimate is None
    assert dims["guided_production"].positive_mass < dims[
        "recognition"
    ].positive_mass


# -- §6 negative propagation asymmetry --------------------------------------


def test_natural_low_support_failure_does_not_hit_guided_or_recognition():
    state = estimate(
        [
            claim(
                1,
                performance_type="FAILED_ATTEMPT",
                polarity="NEGATIVE",
                outcome="FAILURE",
                error_attribution="LIKELY_KNOWLEDGE_GAP",
            )
        ]
    )
    dims = state.dimensions
    assert dims["spontaneous_production"].negative_mass > 0
    assert dims["independent_production"].negative_mass > 0
    assert dims["guided_production"].negative_mass == 0
    assert dims["recognition"].negative_mass == 0


def test_supported_failure_lands_on_guided_only():
    state = estimate(
        [
            claim(
                1,
                performance_type="FAILED_ATTEMPT",
                polarity="NEGATIVE",
                outcome="FAILURE",
                support_level="STRUCTURAL_HINT",
                opportunity_type="ELICITED",
                error_attribution="LIKELY_KNOWLEDGE_GAP",
            )
        ]
    )
    dims = state.dimensions
    assert dims["guided_production"].negative_mass > 0
    assert dims["independent_production"].negative_mass == 0
    assert dims["spontaneous_production"].negative_mass == 0


def test_misuse_is_primarily_accuracy_negative():
    state = estimate(
        [
            claim(
                1,
                performance_type="MISUSE",
                polarity="NEGATIVE",
                outcome="FAILURE",
                error_attribution="SYSTEMATIC_PATTERN",
            )
        ]
    )
    dims = state.dimensions
    assert dims["accuracy"].negative_mass > dims[
        "spontaneous_production"
    ].negative_mass
    assert dims["accuracy"].negative_mass > dims[
        "independent_production"
    ].negative_mass


# -- §8 support / exposure ---------------------------------------------------


def test_full_answer_exposure_collapses_independent_mass():
    clean = estimate(
        [
            claim(
                1,
                performance_type="INDEPENDENT_PRODUCTION",
                opportunity_type="ELICITED",
            )
        ]
    )
    exposed = estimate(
        [
            claim(
                1,
                performance_type="GUIDED_PRODUCTION",
                opportunity_type="ELICITED",
                support_level="FULL_FORM_SHOWN",
                exposure_level="FULL",
            )
        ]
    )
    assert (
        exposed.dimensions["guided_production"].effective_mass
        < clean.dimensions["independent_production"].effective_mass
    )
    # E01 semantics: imitation after a full reveal cannot form
    # independent evidence at all.
    imitation = estimate(
        [
            claim(
                1,
                performance_type="IMITATIVE_PRODUCTION",
                opportunity_type="ELICITED",
                support_level="FULL_FORM_SHOWN",
                exposure_level="FULL",
            )
        ]
    )
    assert (
        imitation.dimensions["independent_production"].estimate is None
    )


# -- §9 PARTIAL is mixed evidence -------------------------------------------


def test_repeated_partial_converges_to_partial_control_not_mastery():
    partials = [
        claim(
            index,
            performance_type="GUIDED_PRODUCTION",
            opportunity_type="ELICITED",
            support_level="SEMANTIC_HINT",
            outcome="PARTIAL",
            day=f"2026-09-{day:02d}",
        )
        for index, day in enumerate((1, 3, 5, 7, 9, 11), start=1)
    ]
    state = estimate(partials)
    guided = state.dimensions["guided_production"]
    assert guided.estimate is not None
    # v1.1: repeated PARTIAL stays near the partial-control region
    # (positive / (positive + residual negative) with the 0.5/0.5
    # balance) and never climbs toward 1.0.
    assert guided.estimate <= 0.6
    # Confidence does grow with consistent partial evidence.
    assert guided.confidence > 0.3


# -- §10 evaluator confidence floor ------------------------------------------


def test_below_floor_confidence_contributes_no_mass():
    state = estimate([claim(1, evaluator_confidence=0.4)])
    for name, dim in state.dimensions.items():
        assert dim.effective_mass == 0, name
        assert dim.estimate is None, name
    assert state.projection.ability_band == "UNKNOWN"
    assert "INSUFFICIENT_EVIDENCE" in state.projection.learning_flags


# -- §11 EvidenceGroup dedup --------------------------------------------------


def test_same_group_keeps_only_strongest_contribution():
    # §7.2 (strict mode) already refuses two primary performance claims
    # per group × target × modality, so the §11 group dedup is exercised
    # in diagnostic loose mode: it is the estimator's defense in depth
    # against double-counting one utterance across evaluator paths.
    deduped = estimate_target_state(
        [
            claim(1, group_id="g1", evaluator_confidence=0.9),
            # Same group, weaker evaluator path — deduplicated away.
            claim(2, group_id="g1", evaluator_confidence=0.6),
        ],
        target_type="RESOURCE",
        target_id="expr.test",
        modality="TEXT_PRODUCTION",
        as_of=AS_OF,
        strict=False,
    )
    single = estimate([claim(1, evaluator_confidence=0.9)])
    assert (
        deduped.dimensions["spontaneous_production"].positive_mass
        == single.dimensions["spontaneous_production"].positive_mass
    )


# -- §12/§13 cluster correlation + diminishing returns -----------------------


def test_same_cluster_repeats_cannot_equal_independent_occurrences():
    same_cluster = estimate(
        [
            claim(1, minute=0),
            claim(2, minute=2),
            claim(3, minute=4),
        ]
    )
    across_days = estimate(
        [
            claim(1, day="2026-09-01"),
            claim(2, day="2026-09-04"),
            claim(3, day="2026-09-08"),
        ]
    )
    assert (
        same_cluster.dimensions["independent_production"].independent_clusters
        == 1
    )
    assert (
        across_days.dimensions[
            "independent_production"
        ].independent_clusters
        == 3
    )
    assert (
        across_days.dimensions["independent_production"].effective_mass
        > same_cluster.dimensions["independent_production"].effective_mass
    )
    # §13 cap: three same-cluster repeats stay below 1.6 × the strongest.
    strongest = 0.95
    assert same_cluster.dimensions[
        "independent_production"
    ].effective_mass <= 1.6 * strongest + 1e-9


def test_teaching_moment_is_one_cluster():
    state = estimate(
        [
            claim(1, teaching_moment_id="m1", minute=0),
            claim(2, teaching_moment_id="m1", minute=2),
        ]
    )
    assert (
        state.dimensions["independent_production"].independent_clusters == 1
    )


# -- §14 UNKNOWN threshold + ability/confidence separation -------------------


def test_below_minimum_effective_mass_is_unknown():
    # assist 0.1 × conf 0.55 keeps effective mass below 0.55.
    state = estimate(
        [
            claim(
                1,
                performance_type="GUIDED_PRODUCTION",
                opportunity_type="ELICITED",
                support_level="FULL_FORM_SHOWN",
                evaluator_confidence=0.55,
            )
        ]
    )
    guided = state.dimensions["guided_production"]
    assert guided.effective_mass < 0.55
    assert guided.estimate is None


def test_ability_and_confidence_are_separate_axes():
    one_success = estimate([claim(1)])
    assert (
        one_success.dimensions["independent_production"].estimate >= 0.95
    )
    assert one_success.projection.confidence_band == "LOW"

    consistent_failures = estimate(
        [
            claim(
                index,
                performance_type="FAILED_ATTEMPT",
                polarity="NEGATIVE",
                outcome="FAILURE",
                error_attribution="SYSTEMATIC_PATTERN",
                day=f"2026-09-{day:02d}",
                conversation_id=f"c{index}",
                context_key=f"ctx{index}",
            )
            for index, day in enumerate((1, 3, 6, 9, 12), start=1)
        ]
    )
    independent = consistent_failures.dimensions["independent_production"]
    assert independent.estimate is not None and independent.estimate <= 0.05
    assert (
        consistent_failures.projection.confidence_band == "HIGH"
    )


# -- §15 diversity bonus is bounded -------------------------------------------


def test_diversity_raises_confidence_not_ability():
    single = estimate([claim(1)])
    diverse = estimate(
        [
            claim(1, day="2026-09-01", context_key="a"),
            claim(2, day="2026-09-05", context_key="b"),
            claim(3, day="2026-09-09", context_key="c"),
        ]
    )
    assert (
        diverse.dimensions["independent_production"].confidence
        > single.dimensions["independent_production"].confidence
    )
    # The estimate itself does not exceed what the evidence supports.
    assert (
        diverse.dimensions["independent_production"].estimate <= 1.0 + 1e-9
    )


# -- §16 self-repair restriction ----------------------------------------------


def test_guided_self_repair_is_not_strong_retrieval():
    state = estimate(
        [
            claim(
                1,
                performance_type="SELF_REPAIR",
                support_level="SEMANTIC_HINT",
                opportunity_type="ELICITED",
                spontaneity=None,
            )
        ]
    )
    assert state.freshness.band == "UNKNOWN"
    assert state.projection.stability_band == "UNTESTED"


def test_spontaneous_successful_self_repair_is_strong_retrieval():
    state = estimate(
        [
            claim(
                1,
                day="2026-09-19",
                performance_type="SELF_REPAIR",
                spontaneity="SPONTANEOUS",
            )
        ]
    )
    assert state.freshness.band == "FRESH"
    assert state.freshness.last_strong_retrieval_at is not None
    # §5 conditional spontaneous support: the spontaneous dimension
    # received mass from the eligible self-repair.
    assert (
        state.dimensions["spontaneous_production"].positive_mass > 0
    )


# -- §18/§19 transfer gates ----------------------------------------------------


def test_resource_transfer_needs_two_strong_clusters_plus_diversity():
    same_context = estimate(
        [
            claim(1, day="2026-09-01"),
            claim(2, day="2026-09-02"),
        ]
    )
    assert same_context.dimensions["transfer"].estimate is None

    cross_context = estimate(
        [
            claim(1, day="2026-09-01", context_key="a"),
            claim(2, day="2026-09-04", context_key="b"),
        ]
    )
    assert cross_context.dimensions["transfer"].estimate is not None


def test_capability_transfer_requires_realization_diversity():
    fixed_realization = estimate(
        [
            claim(1, day="2026-09-01", context_key="a",
                  realization_key="same", target_type="CAPABILITY"),
            claim(2, day="2026-09-04", context_key="b",
                  realization_key="same", target_type="CAPABILITY",
                  qualifiers=("CROSS_CONTEXT",)),
        ],
        target_type="CAPABILITY",
    )
    assert fixed_realization.dimensions["transfer"].estimate is None

    varied = estimate(
        [
            claim(1, day="2026-09-01", context_key="a",
                  realization_key="r1", target_type="CAPABILITY"),
            claim(2, day="2026-09-04", context_key="b",
                  realization_key="r2", target_type="CAPABILITY",
                  qualifiers=("CROSS_CONTEXT", "NOVEL_REALIZATION")),
        ],
        target_type="CAPABILITY",
    )
    assert varied.dimensions["transfer"].estimate is not None


# -- §20 NARROW_EVIDENCE is strong-only ----------------------------------------


def test_low_confidence_breadth_cannot_clear_narrow_evidence():
    weak_breadth = estimate(
        [
            claim(1, day="2026-09-01", context_key="a"),
            # Low-confidence claim in a different context: cannot fake
            # breadth (v1.1 strong-only diversity).
            claim(
                2,
                day="2026-09-05",
                context_key="b",
                evaluator_confidence=0.5,
            ),
        ]
    )
    assert "NARROW_EVIDENCE" in weak_breadth.projection.learning_flags


# -- §21 support dependency ------------------------------------------------------


def test_assisted_success_only_leaves_dependency_unknown():
    state = estimate(
        [
            claim(
                index,
                performance_type="GUIDED_PRODUCTION",
                opportunity_type="ELICITED",
                support_level="SEMANTIC_HINT",
                day=f"2026-09-{day:02d}",
            )
            for index, day in enumerate((1, 4, 7), start=1)
        ]
    )
    dependency = state.dimensions["support_dependency"]
    assert dependency.estimate is None
    assert state.projection.support_band == "UNKNOWN"


def test_repeated_low_support_success_establishes_low_dependency():
    state = estimate(
        [
            claim(index, day=f"2026-09-{day:02d}")
            for index, day in enumerate((1, 4, 7, 10), start=1)
        ]
    )
    dependency = state.dimensions["support_dependency"]
    assert dependency.estimate is not None
    assert dependency.estimate < 0.2


# -- §22 freshness ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "band"),
    [(0, "FRESH"), (7, "FRESH"), (10, "AGING"), (21, "AGING"),
     (30, "STALE")],
)
def test_freshness_bands(days: int, band: str) -> None:
    from datetime import datetime, timedelta

    strong_at = datetime.fromisoformat(AS_OF) - timedelta(days=days)
    state = estimate(
        [claim(1, day=strong_at.date().isoformat())], as_of=AS_OF
    )
    assert state.freshness.band == band


def test_time_passage_changes_freshness_not_mass():
    recent = estimate([claim(1, day="2026-09-18")], as_of=AS_OF)
    later = estimate([claim(1, day="2026-09-18")],
                     as_of="2026-10-18T10:00:00+00:00")
    assert recent.freshness.band == "FRESH"
    assert later.freshness.band == "STALE"
    assert (
        later.dimensions["independent_production"].effective_mass
        == recent.dimensions["independent_production"].effective_mass
    )
    assert (
        later.dimensions["independent_production"].estimate
        == recent.dimensions["independent_production"].estimate
    )


# -- §23 stability -----------------------------------------------------------------


def test_stability_needs_strong_cluster_and_day_diversity():
    one_strong_day = estimate(
        [
            claim(1, minute=0),
            claim(2, minute=30),
        ]
    )
    assert one_strong_day.projection.stability_band == "FRAGILE"

    spread = estimate(
        [
            claim(1, day="2026-09-01"),
            claim(2, day="2026-09-02"),
            claim(3, day="2026-09-03"),
            claim(4, day="2026-09-04"),
        ]
    )
    assert spread.projection.stability_band == "STABLE"


# -- §24 hierarchy-conflict blocking --------------------------------------------


def test_confirmed_lower_tier_gap_blocks_higher_tier_headline():
    state = estimate(
        [
            # One anomalous spontaneous success...
            claim(1, day="2026-09-01"),
            # ...plus multiple high-confidence independent failures
            # (elicited low-support: they diagnose independent, not
            # spontaneous, so the spontaneous tier itself stays high —
            # exactly the §24 v1.1 headline-conflict scenario).
            *[
                claim(
                    index,
                    performance_type="FAILED_ATTEMPT",
                    polarity="NEGATIVE",
                    outcome="FAILURE",
                    opportunity_type="ELICITED",
                    error_attribution="SYSTEMATIC_PATTERN",
                    day=f"2026-09-{day:02d}",
                    conversation_id=f"c{index}",
                    context_key=f"ctx{index}",
                )
                for index, day in enumerate((3, 6, 9, 12), start=2)
            ],
        ]
    )
    projection = state.projection
    assert (
        state.dimensions["spontaneous_production"].estimate is not None
        and state.dimensions["spontaneous_production"].estimate >= 0.75
    )
    assert projection.ability_band != "SPONTANEOUS"
    assert "CONFIRMED_GAP" in projection.learning_flags
    assert "CONFLICTING_EVIDENCE" in projection.learning_flags


# -- §27 quality dimensions --------------------------------------------------------


def test_quality_scores_split_into_positive_and_negative_mass():
    state = estimate(
        [
            claim(1, accuracy=0.9, pragmatic_fit=0.2),
        ]
    )
    dims = state.dimensions
    assert dims["accuracy"].positive_mass > dims["accuracy"].negative_mass
    assert dims["pragmatic_control"].positive_mass < dims[
        "pragmatic_control"
    ].negative_mass
    # The latest score never overwrites history: mass accumulates.
    more = estimate(
        [claim(1, accuracy=0.9), claim(2, day="2026-09-05", accuracy=0.9)]
    )
    assert (
        more.dimensions["accuracy"].positive_mass
        > state.dimensions["accuracy"].positive_mass
    )


# -- §28 modality isolation ---------------------------------------------------------


def test_other_modality_evidence_is_isolated():
    state = estimate(
        [
            claim(1, modality="TEXT_COMPREHENSION"),
            claim(2, day="2026-09-04", modality="TEXT_COMPREHENSION"),
        ]
    )
    for name, dim in state.dimensions.items():
        assert dim.effective_mass == 0, name
    assert state.projection.ability_band == "UNKNOWN"


# -- §29 status filter ----------------------------------------------------------------


def test_only_active_claims_enter_estimation():
    state = estimate(
        [
            claim(1),
            claim(2, day="2026-09-04", status="SUPERSEDED"),
            claim(3, day="2026-09-08", status="INVALIDATED"),
        ]
    )
    assert (
        state.dimensions["independent_production"].independent_clusters == 1
    )
    assert state.coverage.evidence_groups == 1
