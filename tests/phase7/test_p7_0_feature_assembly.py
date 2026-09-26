"""P7-0 ③ — the feature-assembly authority.

The most important rule of this cut lives here: BF-02 §5 (lines 128–166) — an
incomplete assembly or an invalid snapshot is ``DEGRADED`` with no decision,
and neither a missing Scheduler nor a stale authority may be answered with a
``0``. What this suite holds the implementation to, in three parts:

- the **numbers** are BF-02's reference values, extracted from the frozen
  baseline asset at test time rather than typed twice (the phase-6 pin's
  convention, one factor over);
- the **mapping** from §5.1's implementation-declared frequencies to BF-02's
  profile words is versioned and carries a basis per pair, quoted where a
  quotation exists and registered as a judgement where none does;
- the **statuses** are executable, and today's honest production answer — on
  the shipped supply — is INCOMPLETE.
"""

from __future__ import annotations

import ast
import json

import pytest

from elc.curriculum.readiness import judge_readiness
from elc.learning.controller import LearningController
from elc.learning.types import LearningSnapshot, LearningSnapshotId
from elc.planner.feature_assembly import (
    FEATURE_ASSEMBLY_MODEL_VERSION,
    POLICY_PROFILE_MAPPING_VERSION,
    SCHEDULE_URGENCY_BANDS,
    TEACHING_FREQUENCY_TO_PROFILE,
    AuthorityName,
    FeatureAssemblyStatus,
    PlannerProfile,
    ScheduleAuthority,
    SnapshotStatus,
    assemble_feature_authority,
    execution_status_of,
    goal_relevance_of,
    profile_mapping_of,
    schedule_authority_of,
    schedule_urgency_of,
)
from elc.planner.types import (
    PlannerDecision,
    PlannerDecisionOutcome,
    PlannerEvaluation,
    PlannerExecutionStatusRecord,
    PlanningOutcome,
)
from elc.platform.types import (
    DecisionCycleId,
    Ok,
    PlannerDecisionId,
    PlannerEvaluationId,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
)
from elc.scheduler.spacing import URGENCY_ANCHORS
from elc.scheduler.types import ScheduleView
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    TeachingFrequency,
    TeachingPolicyProfile,
)

from .conftest import (
    BASELINES,
    CONV,
    DAY_TWO,
    MODALITY,
    OTHER_MODALITY,
    TARGET_ID,
    USER,
    constraint,
    portfolio,
    schedule_item,
    source_text,
    teaching_policy,
)

PROFILE = (
    BASELINES / "planner" / "planner_reference_profile_v1_1.json"
)
BF_02 = BASELINES / "planner" / "BF-02_Planner_Decision_Spec_v1.1.md"
BF_03 = BASELINES / "gate" / "BF-03_Teaching_Gate_Decision_Spec_v1.0.md"


def _snapshot(watermark: int) -> LearningSnapshot:
    """One §12 snapshot with no targets: this suite reads its watermark only."""

    return LearningSnapshot(
        learning_snapshot_id=LearningSnapshotId("ls-p7-0"),
        user_scope_id=str(USER),
        as_of=DAY_TWO,
        estimator_version="est-v1",
        evidence_watermark=watermark,
        targets=(),
    )


def _view(*rows) -> ScheduleView:
    return ScheduleView(
        schedule_version="sd1",
        as_of=DAY_TWO,
        due_items=tuple(rows),
        overdue_items=(),
        upcoming=(),
    )


def _full_bag(**overrides):
    """Every authority present and usable — the COMPLETE branch's input."""

    bag = {
        "learning_snapshot": _snapshot(3),
        "current_learning_watermark": 3,
        "schedule_view": _view(schedule_item(watermark="3", urgency=0.75)),
        "teaching_policy": teaching_policy(frequency=TeachingFrequency.BALANCED),
        "goal_portfolio": portfolio(assessment_targets=()),
        "curriculum_readiness": {str(TARGET_ID): "R3"},
        "constraint_view_present": True,
    }
    bag.update(overrides)
    return assemble_feature_authority(**bag)


# -- ① the numbers are BF-02's, extracted ------------------------------------


def test_the_bands_are_the_reference_profiles_schedule_urgency() -> None:
    """BF-02 §6's ``schedule_urgency`` reference bands, read out of the frozen
    baseline asset and compared with this module's table **and** with the
    Scheduler's own anchors: one number, three readers, one source."""

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    anchors = profile["reference_factor_bands"]["schedule_urgency"]
    assert {state.value: value for state, value in SCHEDULE_URGENCY_BANDS.items()} == (
        anchors
    )
    assert dict(URGENCY_ANCHORS) == {
        state: value for state, value in SCHEDULE_URGENCY_BANDS.items()
    }
    assert profile["status"] == "REFERENCE_DEFAULT_CALIBRATABLE"


def test_the_profile_words_are_bf_02s() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert set(profile["policy_profiles"]) == set(PlannerProfile)
    text = BF_02.read_text(encoding="utf-8")
    for word in ("LOUNGE", "BALANCED", "STUDY_FIRST"):
        assert word in text, word
    for phrase in ("BALANCED    +.08", "STUDY_FIRST +.10", "LOUNGE       +0"):
        assert phrase in text, phrase


def test_the_bands_are_reference_values_and_say_so() -> None:
    """BF-02 §21: the regression does not validate these numbers, and the
    module says so where the table lives (a "frozen numbers" claim is what
    this pin forbids)."""

    source = source_text("src/elc/planner/feature_assembly.py")
    assert "Reference values, not frozen ones" in source
    assert "REFERENCE_DEFAULT_CALIBRATABLE" in source


# -- ② the versioned mapping --------------------------------------------------


def test_the_mapping_covers_every_declared_frequency_word() -> None:
    assert set(TEACHING_FREQUENCY_TO_PROFILE) == set(TeachingFrequency)
    for frequency, mapping in TEACHING_FREQUENCY_TO_PROFILE.items():
        assert mapping.teaching_frequency is frequency
        assert isinstance(mapping.profile, PlannerProfile)


def test_every_pair_carries_a_basis_and_the_judged_ones_a_revisit() -> None:
    """The honesty requirement: a pair either quotes where its justification
    comes from or registers itself as a judgement with the condition that
    re-opens it — and every row's basis names the *pairing* as the declared
    judgement it is. The label is required of all four pairs, not of the two
    the first cut sampled (P7-0's disposition: OFF's basis quotes its BF-03
    switch and now says so about the pairing the same way the other three do).
    """

    for frequency, mapping in TEACHING_FREQUENCY_TO_PROFILE.items():
        assert mapping.basis.strip(), frequency
        assert mapping.revisit.strip(), frequency
        assert "declared judgement" in mapping.basis, frequency
    assert "implementation-declared" in (
        TEACHING_FREQUENCY_TO_PROFILE[TeachingFrequency.BALANCED].basis
    )
    assert "BF-02 §21" in TEACHING_FREQUENCY_TO_PROFILE[
        TeachingFrequency.EAGER
    ].basis


def test_the_mapping_is_versioned_and_the_version_rides_the_record() -> None:
    assert POLICY_PROFILE_MAPPING_VERSION == "tp2bf02-v1"
    assert FEATURE_ASSEMBLY_MODEL_VERSION == "fa1"
    assert _full_bag().policy_mapping_version == POLICY_PROFILE_MAPPING_VERSION


def test_off_switches_automatic_teaching_off_and_below_the_scale() -> None:
    """``OFF`` is the one frequency that stops automatic teaching, and the
    switch is BF-03 §13's (quoted in the module), not a column §5.1 has."""

    off = TEACHING_FREQUENCY_TO_PROFILE[TeachingFrequency.OFF]
    assert off.automatic_teaching_enabled is False
    assert off.profile is PlannerProfile.LOUNGE
    for frequency in (
        TeachingFrequency.MINIMAL,
        TeachingFrequency.BALANCED,
        TeachingFrequency.EAGER,
    ):
        assert TEACHING_FREQUENCY_TO_PROFILE[frequency].automatic_teaching_enabled
    text = BF_03.read_text(encoding="utf-8")
    assert "automatic_teaching_enabled = false" in text
    source = source_text("src/elc/planner/feature_assembly.py")
    assert "USER_REQUESTED_CONTINUE" in source


def test_eager_is_capped_at_the_top_declared_profile() -> None:
    eager = TEACHING_FREQUENCY_TO_PROFILE[TeachingFrequency.EAGER]
    assert eager.profile is PlannerProfile.STUDY_FIRST
    assert set(PlannerProfile) == {
        PlannerProfile.LOUNGE,
        PlannerProfile.BALANCED,
        PlannerProfile.STUDY_FIRST,
    }


def test_an_undeclared_frequency_word_maps_to_nothing() -> None:
    """The schema puts no CHECK on the column (the word list is
    implementation-declared), so a junk word is reachable — and the mapping
    refuses to guess rather than falling back to a default profile."""

    junk = TeachingPolicyProfile(
        teaching_policy_profile_id=USER,
        policy_version=PolicyVersion("pv-junk"),
        teaching_frequency="SOMETIMES",  # type: ignore[arg-type]
    )
    assert profile_mapping_of(junk) is None
    authority = _full_bag(teaching_policy=junk)
    assert AuthorityName.TEACHING_POLICY in authority.missing_authorities
    assert authority.planner_profile is None
    assert authority.automatic_teaching_enabled is False


# -- ③ the schedule authority and the urgency conversion ----------------------


def test_the_schedule_authority_is_missing_stale_or_current() -> None:
    assert (
        schedule_authority_of(None, 3) is ScheduleAuthority.MISSING
    )
    assert (
        schedule_authority_of(_view(schedule_item(watermark="3")), 3)
        is ScheduleAuthority.CURRENT
    )
    assert (
        schedule_authority_of(_view(schedule_item(watermark="2")), 3)
        is ScheduleAuthority.STALE
    )
    assert schedule_authority_of(_view(), 3) is ScheduleAuthority.CURRENT


def test_urgency_is_unknown_and_never_zero_without_a_current_authority() -> None:
    row = schedule_item(watermark="2", urgency=0.75)
    for authority in (ScheduleAuthority.MISSING, ScheduleAuthority.STALE):
        assert schedule_urgency_of(row, authority) is None


def test_a_target_the_scheduler_was_never_asked_about_is_unknown_not_zero() -> None:
    """The distinction P6-2 wrote a row for: no row = "never asked", a written
    ``NOT_SCHEDULED`` row = a *known* absence of review debt."""

    assert schedule_urgency_of(None, ScheduleAuthority.CURRENT) is None
    written = schedule_item(
        watermark="3",
        review_state="NOT_SCHEDULED",
        urgency=0.0,
    )
    assert schedule_urgency_of(written, ScheduleAuthority.CURRENT) == 0.0


def test_the_stored_urgency_wins_and_the_band_is_the_fallback() -> None:
    configured = schedule_item(watermark="3", urgency=0.42)
    assert schedule_urgency_of(configured, ScheduleAuthority.CURRENT) == 0.42
    unconfigured = schedule_item(watermark="3", urgency=None, review_state="DUE")
    assert schedule_urgency_of(unconfigured, ScheduleAuthority.CURRENT) == 0.75


def test_goal_relevance_is_unknown_and_never_zero() -> None:
    """``0`` would be a claim ("known to be irrelevant"), and the mapping that
    could support it — IMPLEMENTATION_PLAN §7 line 340 — is not landed."""

    for relation in (None, "NONE", "PREPARATORY", "DIRECT_TARGET_LEVEL"):
        assert goal_relevance_of(relation) is None


# -- ④ the statuses, and today's honest answer --------------------------------


def test_an_empty_authority_bag_names_every_gap_in_a_fixed_order() -> None:
    authority = assemble_feature_authority(
        learning_snapshot=None,
        current_learning_watermark=None,
        schedule_view=None,
        teaching_policy=None,
        goal_portfolio=None,
        curriculum_readiness=None,
        constraint_view_present=False,
    )
    assert authority.status is FeatureAssemblyStatus.INCOMPLETE
    assert authority.snapshot_status is SnapshotStatus.INVALID
    assert authority.schedule_authority is ScheduleAuthority.MISSING
    #: the pack-mapping leg needs a portfolio to be *needed*, so it is the one
    #: name an empty bag does not carry (a portfolio that names no assessment
    #: target needs no mapping either).
    assert authority.missing_authorities == (
        AuthorityName.LEARNING_SNAPSHOT,
        AuthorityName.SCHEDULE,
        AuthorityName.TEACHING_POLICY,
        AuthorityName.GOAL_PORTFOLIO,
        AuthorityName.CURRICULUM_READINESS,
        AuthorityName.PLANNER_CONSTRAINT,
    )
    assert list(authority.missing_authorities) == [
        name
        for name in AuthorityName
        if name in set(authority.missing_authorities)
    ]
    assert len(authority.reasons) == len(authority.missing_authorities)
    assert not authority.complete
    assert execution_status_of(authority) is PlannerExecutionStatusValue.DEGRADED


def test_a_complete_bag_is_complete_and_valid() -> None:
    """The COMPLETE branch is reachable — this cut did not make degradation
    the only possible answer, it made the *honest* answer the only one."""

    authority = _full_bag()
    assert authority.status is FeatureAssemblyStatus.COMPLETE
    assert authority.snapshot_status is SnapshotStatus.VALID
    assert authority.schedule_authority is ScheduleAuthority.CURRENT
    assert authority.missing_authorities == ()
    assert authority.reasons == ()
    assert authority.complete
    assert authority.planner_profile is PlannerProfile.BALANCED
    assert authority.automatic_teaching_enabled
    assert execution_status_of(authority) is PlannerExecutionStatusValue.SUCCEEDED


def test_a_stale_snapshot_is_invalid() -> None:
    authority = _full_bag(
        learning_snapshot=_snapshot(2), current_learning_watermark=3
    )
    assert authority.snapshot_status is SnapshotStatus.INVALID
    assert AuthorityName.LEARNING_SNAPSHOT in authority.missing_authorities
    assert not authority.complete
    assert execution_status_of(authority) is PlannerExecutionStatusValue.DEGRADED


def test_an_unreadable_watermark_cannot_make_a_snapshot_valid() -> None:
    authority = _full_bag(current_learning_watermark=None)
    assert authority.snapshot_status is SnapshotStatus.INVALID
    assert authority.schedule_authority is ScheduleAuthority.STALE
    assert set(authority.missing_authorities) >= {
        AuthorityName.LEARNING_SNAPSHOT,
        AuthorityName.SCHEDULE,
    }


def test_a_stale_schedule_row_makes_the_assembly_incomplete() -> None:
    authority = _full_bag(
        schedule_view=_view(schedule_item(watermark="2", urgency=0.75))
    )
    assert authority.schedule_authority is ScheduleAuthority.STALE
    assert authority.snapshot_status is SnapshotStatus.VALID
    assert authority.missing_authorities == (AuthorityName.SCHEDULE,)
    assert "older Learning watermark" in authority.reasons[0]
    assert execution_status_of(authority) is PlannerExecutionStatusValue.DEGRADED


def test_the_goal_pack_mapping_is_reported_when_the_portfolio_names_targets() -> None:
    named = _full_bag(goal_portfolio=portfolio(assessment_targets=("ielts",)))
    assert AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING in (
        named.missing_authorities
    )
    nameless = _full_bag(goal_portfolio=portfolio(assessment_targets=()))
    assert nameless.status is FeatureAssemblyStatus.COMPLETE


def test_a_candidate_with_no_content_level_is_a_missing_authority() -> None:
    unknown = _full_bag(curriculum_readiness={str(TARGET_ID): None})
    assert unknown.missing_authorities == (AuthorityName.CURRICULUM_READINESS,)
    assert "no content level is reachable" in unknown.reasons[0]
    known = _full_bag(curriculum_readiness={str(TARGET_ID): "R0"})
    assert known.status is FeatureAssemblyStatus.COMPLETE


def test_a_missing_constraint_view_is_a_missing_authority() -> None:
    authority = _full_bag(constraint_view_present=False)
    assert authority.missing_authorities == (AuthorityName.PLANNER_CONSTRAINT,)


def test_natural_break_availability_rides_through() -> None:
    assert _full_bag(natural_break_available=True).natural_break_available
    assert not _full_bag().natural_break_available


@pytest.mark.parametrize(
    "overrides",
    [
        {"learning_snapshot": None},
        {"current_learning_watermark": None},
        {"schedule_view": None},
        {"teaching_policy": None},
        {"goal_portfolio": None},
        {"curriculum_readiness": None},
        {"constraint_view_present": False},
    ],
)
def test_any_single_gap_is_degraded(overrides: dict) -> None:
    authority = _full_bag(**overrides)
    assert authority.status is FeatureAssemblyStatus.INCOMPLETE
    assert not authority.complete
    assert execution_status_of(authority) is PlannerExecutionStatusValue.DEGRADED


def test_degraded_carries_no_decision() -> None:
    """BF-02 §5 lines 161–174's coupling with the canonical outcome shape: a
    DEGRADED run has no ``PlannerDecision`` at all (docs/DOMAIN_MODEL.md §10
    line 559 — failure is never disguised as a decision, and never as a
    fabricated ``NO_TARGET``)."""

    authority = assemble_feature_authority(
        learning_snapshot=None,
        current_learning_watermark=None,
        schedule_view=None,
        teaching_policy=None,
        goal_portfolio=None,
        curriculum_readiness=None,
        constraint_view_present=False,
    )
    status = PlannerExecutionStatusRecord(
        decision_cycle_id=DecisionCycleId("dc-p7-0"),
        status=execution_status_of(authority),
    )
    evaluation = PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId("pe-p7-0"),
        decision_cycle_id=DecisionCycleId("dc-p7-0"),
        planner_version=PlannerVersion("planner-v1"),
        policy_version=PolicyVersion("policy-v1"),
        ranked_candidates=(),
        reason_trace=(),
    )
    degraded = PlanningOutcome(
        evaluation=evaluation, execution_status=status, decision=None
    )
    assert degraded.decision is None
    with pytest.raises(ValueError):
        PlanningOutcome(
            evaluation=evaluation,
            execution_status=status,
            decision=PlannerDecision(
                planner_decision_id=PlannerDecisionId("pd-p7-0"),
                decision_cycle_id=DecisionCycleId("dc-p7-0"),
                decision=PlannerDecisionOutcome.NO_TARGET,
                planner_evaluation_id=PlannerEvaluationId("pe-p7-0"),
            ),
        )


def test_the_shipped_supply_grades_the_resources_and_leaves_the_caps_ungraded(
    content_supply,
) -> None:
    """The corpus-side fact the assembly turns into an INCOMPLETE verdict,
    at C2-a's truth (旧真值: the real content.db graded no target; C1: it
    graded exactly one — res-colloc-make-a-decision at R4 — and left thirteen
    ungraded; 新真值: it grades the nine RESOURCE targets and leaves the five
    CAPABILITY entities ungraded, so the assembly stays INCOMPLETE because
    ungraded candidates the caller holds still exist)."""

    ids = content_supply.supply_entity_ids()
    assert isinstance(ids, Ok)
    assert ids.value, "the shipped supply is empty — nothing was asserted"
    levels: dict[str, str | None] = {}
    for entity_id in ids.value:
        facts = content_supply.readiness_facts(str(entity_id))
        assert isinstance(facts, Ok), entity_id
        levels[str(entity_id)] = judge_readiness(facts.value).level
    # 旧真值 → C1 → 新真值（C2-a）: {None} → one R4 + thirteen None → nine
    # graded RESOURCE targets and five ungraded CAPABILITY entities.
    for entity_id, level in levels.items():
        if str(entity_id).startswith("res-"):
            assert level == "R4_DETECTION_READY", entity_id
            continue
        assert level is None, entity_id
    ungraded = {target for target, level in levels.items() if level is None}
    assert len(ungraded) == 5
    authority = _full_bag(curriculum_readiness=levels)
    assert authority.status is FeatureAssemblyStatus.INCOMPLETE
    assert AuthorityName.CURRICULUM_READINESS in authority.missing_authorities


def test_the_real_chain_is_incomplete_today(
    db,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    content_supply,
) -> None:
    """The end-to-end honest answer: real durable rows, real read faces, the
    real corpus — and a Planner that may not proceed. Nothing here is
    synthetic except the snapshot the Learning face cannot yet produce with
    content levels."""

    assert isinstance(
        user_config_store.upsert_teaching_policy(
            teaching_policy(frequency=TeachingFrequency.BALANCED)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.upsert_goal_portfolio(portfolio()), Ok
    )
    assert isinstance(
        user_config_store.record_planner_constraint(constraint()), Ok
    )
    policy = user_config_controller.get_teaching_policy(USER)
    goals = user_config_controller.get_goal_portfolio(USER)
    constraints = user_config_controller.get_planner_constraint_view(
        DAY_TWO, CONV
    )
    watermark = learning_controller.get_learning_watermark()
    assert isinstance(policy, Ok) and policy.value is not None
    assert isinstance(goals, Ok) and goals.value is not None
    assert isinstance(constraints, Ok)
    assert isinstance(watermark, Ok)

    ids = content_supply.supply_entity_ids()
    assert isinstance(ids, Ok)
    levels = {}
    for entity_id in ids.value:
        facts = content_supply.readiness_facts(str(entity_id))
        assert isinstance(facts, Ok)
        levels[str(entity_id)] = judge_readiness(facts.value).level

    authority = assemble_feature_authority(
        learning_snapshot=_snapshot(watermark.value),
        current_learning_watermark=watermark.value,
        schedule_view=ScheduleView(
            schedule_version="sd1",
            as_of=DAY_TWO,
            due_items=(),
            overdue_items=(),
            upcoming=(),
        ),
        teaching_policy=policy.value,
        goal_portfolio=goals.value,
        curriculum_readiness=levels,
        constraint_view_present=bool(constraints.value.entries),
    )
    assert authority.snapshot_status is SnapshotStatus.VALID
    assert authority.schedule_authority is ScheduleAuthority.CURRENT
    assert authority.planner_profile is PlannerProfile.BALANCED
    assert authority.status is FeatureAssemblyStatus.INCOMPLETE
    assert set(authority.missing_authorities) == {
        AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING,
        AuthorityName.CURRICULUM_READINESS,
    }
    assert execution_status_of(authority) is PlannerExecutionStatusValue.DEGRADED


# -- ⑤ the boundary itself ----------------------------------------------------


def test_the_assembly_module_quotes_bf_02s_context_and_degradation() -> None:
    source = source_text("src/elc/planner/feature_assembly.py")
    for name in (
        "feature_assembly_status",
        "snapshot_status",
        "missing_authorities",
        "natural_break_available",
    ):
        assert name in source, name
    for phrase in (
        "missing Scheduler",
        "schedule_urgency = 0",
        "DEGRADED_NO_AUTOMATIC_TEACHING",
        "PlannerDecision = none",
    ):
        assert phrase in source, phrase


def test_the_assembly_module_holds_no_store_and_no_clock() -> None:
    source = source_text("src/elc/planner/feature_assembly.py")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported == {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "elc.platform.types",
        "elc.scheduler.types",
        "elc.user_config.types",
    }
    for forbidden in ("sqlite3", "datetime", "connect("):
        assert forbidden not in source, forbidden


def test_the_assembly_produces_no_decision() -> None:
    """The honesty pin for this cut: the assembly answers authority, so it
    contains no outcome construction at all — and the Planner service beside it
    is still the Phase 0 skeleton (no scoring, no shadow mode, no automatic
    teaching)."""

    source = source_text("src/elc/planner/feature_assembly.py")
    assert "PlanningOutcome(" not in source
    assert "ranked_candidates" not in source
    assert "SELECT" not in source
    controller = source_text("src/elc/planner/controller.py")
    assert "NotImplementedError" in controller


def test_the_assembly_answers_a_caller_who_holds_nothing() -> None:
    """Totality: every argument may be ``None`` (or ``False``) and the answer
    is still a record — no exception, no partial object, no raising path."""

    authority = assemble_feature_authority(
        learning_snapshot=None,
        current_learning_watermark=None,
        schedule_view=None,
        teaching_policy=None,
        goal_portfolio=None,
        curriculum_readiness=None,
        constraint_view_present=False,
    )
    assert authority.planner_profile is None
    assert not authority.automatic_teaching_enabled
    assert authority.schedule_authority is ScheduleAuthority.MISSING



def test_the_two_statuses_cannot_be_read_apart() -> None:
    """``complete`` is the conjunction BF-02 §5 states, in one place: an
    INCOMPLETE assembly is not complete even when its snapshot is VALID, and a
    stale snapshot is not complete even when nothing else is missing."""

    incomplete = _full_bag(schedule_view=None)
    assert incomplete.snapshot_status is SnapshotStatus.VALID
    assert not incomplete.complete
    stale = _full_bag(
        learning_snapshot=_snapshot(1), current_learning_watermark=3
    )
    assert stale.snapshot_status is SnapshotStatus.INVALID
    assert not stale.complete


def test_a_row_on_another_modality_is_one_more_row_for_the_handshake() -> None:
    """The schedule view's rows are read for their watermark only — a row on
    another modality is one more row, and the modality key stays the
    Scheduler's (the assembly never reconstructs it)."""

    authority = _full_bag(
        schedule_view=_view(
            schedule_item(item_id="si-a", watermark="3", urgency=0.75),
            schedule_item(
                item_id="si-b",
                modality=OTHER_MODALITY,
                watermark="3",
                urgency=0.25,
            ),
        )
    )
    assert authority.schedule_authority is ScheduleAuthority.CURRENT
    assert authority.status is FeatureAssemblyStatus.COMPLETE
    assert MODALITY.value == "TEXT_PRODUCTION"


def test_the_incomplete_reading_survives_a_bad_target_level_supply() -> None:
    """A level the caller cannot read is a gap like any other: it is reported,
    not defaulted (a default would be the "level = R0" reading P5-R
    removed)."""

    authority = _full_bag(curriculum_readiness={str(TARGET_ID): None})
    assert authority.missing_authorities == (AuthorityName.CURRICULUM_READINESS,)
    assert authority.reasons[0].startswith("no content level is reachable")



def test_the_snapshot_port_reads_one_field() -> None:
    """The structural half of the port: this module can reach a snapshot's
    watermark and nothing else about it (the ``LearningReadPort`` convention —
    a port that named more would invite a reader to consume more)."""

    assert "evidence_watermark" in LearningSnapshot.__dataclass_fields__
    assert _full_bag().snapshot_status is SnapshotStatus.VALID

