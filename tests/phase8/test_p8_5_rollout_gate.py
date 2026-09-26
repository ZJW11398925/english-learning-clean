"""P8-5 ①–④ — the stage face, the content gate, and the wiring's composition.

The cut's core, in four groups:

- **the stage face** (§12's four words, the monotone criterion, the
  fail-closed default, and the mode leg read from the one table that carries
  it — never a second source);
- **the content gate** (BF-02 §10's four floors over a readiness table: the
  shipped corpus answers GO on all four rows (the C1–C3 evidence face grades
  sixty-four RESOURCE targets at R4), and a *legal* §8.1 assessment built
  through the ladder's own ``judge_readiness`` turns rows GO — the two
  directions of the same executable condition);
- **the registered reading** (the overall verdict is the conjunction over all
  four rows, which implies the task book's "both automatic rows 0 ⇒ HOLD" and
  is strictly stronger; a target at R3 alone is the case that separates them);
- **the wiring** (``AutomaticTurnWiring.rollout_stage``: a declared stage
  composes with the Planner's assembled value, and an undeclared one refuses —
  proven end to end through the real coordinator, plus the mode leg through a
  real §5.1 row written as ``OFF``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.curriculum.readiness import (
    ReadinessAssessment,
    ReadinessFacts,
    judge_readiness,
    required_fact_keys,
)
from elc.planner.feature_assembly import TEACHING_FREQUENCY_TO_PROFILE
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PolicyVersion,
    Result,
)
from elc.teaching.rollout import (
    AUTOMATIC_STAGES,
    DEFAULT_ROLLOUT_STAGE,
    GATE_OPENING_CONDITIONS,
    GATE_ROWS,
    READINESS_RANK,
    ROLLOUT_STAGES,
    RolloutStage,
    RolloutVerdict,
    automatic_teaching_enabled_of,
    corpus_rollout_gate,
    gate_row_verdict,
    mode_allows_automatic,
    opening_conditions,
    rollout_gate_of,
    stage_allows_automatic,
    usable_targets_for,
)
from elc.user_config.types import TeachingFrequency, TeachingPolicyProfile
from tests.phase7.conftest import CONV, benefit_vector, proposal
from tests.phase8.conftest import supply_of
from tests.phase8.p8_4_world import (
    PLANNER_FACT_TABLES,
    TEACHING_FACT_TABLES,
    USER,
    World,
    acceptance_supply,
    begin_turn_ok,
    build_content,
    count_events,
    counts,
    wiring,
    world,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator

AS_OF = "2026-09-24T00:00:00+00:00"

#: One legal §12 benefit vector whose utility clears the LOUNGE profile's own
#: 0.36 activation threshold (0.38), so an OPEN reaches the Gate under *any*
#: declared profile — the shape the mode leg's test needs (the frozen §20
#: vector answers 0.3175 and stops at the activation threshold under LOUNGE).
HIGH_UTILITY_BENEFIT = benefit_vector(learning_need=1.0, context_fit=1.0)


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db: sqlite3.Connection, fence, content: Path) -> World:
    return world(db, fence, content)


# -- ① the stage face --------------------------------------------------------


def test_the_four_stage_words_are_the_documents_spellings() -> None:
    assert [stage.value for stage in ROLLOUT_STAGES] == [
        "manual/user-initiated",
        "Study-first",
        "Balanced",
        "Lounge",
    ]
    assert all(isinstance(stage, str) for stage in ROLLOUT_STAGES)


def test_only_the_manual_stage_refuses_automatic() -> None:
    assert stage_allows_automatic(RolloutStage.MANUAL_USER_INITIATED) is False
    assert stage_allows_automatic(RolloutStage.STUDY_FIRST) is True
    assert stage_allows_automatic(RolloutStage.BALANCED) is True
    assert stage_allows_automatic(RolloutStage.LOUNGE) is True


def test_the_allowing_stages_are_the_documented_tail_of_the_order() -> None:
    """Monotone by construction: no stage after the manual one is outside
    ``AUTOMATIC_STAGES``, and the manual one is not inside it."""

    assert AUTOMATIC_STAGES == ROLLOUT_STAGES[1:]
    assert DEFAULT_ROLLOUT_STAGE is RolloutStage.MANUAL_USER_INITIATED
    assert RolloutStage.MANUAL_USER_INITIATED not in AUTOMATIC_STAGES


def test_an_undeclared_stage_refuses() -> None:
    """Fail-closed: "nothing was said" is the manual stage's answer."""

    assert stage_allows_automatic(None) is False
    assert (
        automatic_teaching_enabled_of(
            stage=None, teaching_frequency=TeachingFrequency.EAGER
        )
        is False
    )


def test_an_unknown_stage_is_refused_not_guessed() -> None:
    with pytest.raises(ValueError) as raised:
        stage_allows_automatic("Sideways")  # type: ignore[arg-type]
    message = str(raised.value)
    assert "Sideways" in message
    for stage in ROLLOUT_STAGES:
        assert stage.value in message


def test_the_mode_leg_is_the_feature_assembly_tables_own_flag() -> None:
    """No third source: the §5.1 leg *is* ``TEACHING_FREQUENCY_TO_PROFILE``'s
    flag, for every declared word (and ``OFF`` is the table's own False)."""

    for frequency in TeachingFrequency:
        expected = TEACHING_FREQUENCY_TO_PROFILE[
            frequency
        ].automatic_teaching_enabled
        assert mode_allows_automatic(frequency) is expected
    assert mode_allows_automatic(TeachingFrequency.OFF) is False
    assert mode_allows_automatic(None) is False


def test_an_unknown_frequency_refuses() -> None:
    """A word the table cannot map is not "the default policy": it refuses
    (the ``profile_mapping_of`` posture, one package over)."""

    assert mode_allows_automatic("SOMETIMES") is False  # type: ignore[arg-type]


def test_the_composed_switch_is_the_conjunction_of_the_two_legs() -> None:
    for stage in (None, *ROLLOUT_STAGES):
        for frequency in (None, *TeachingFrequency):
            expected = stage_allows_automatic(
                stage
            ) and mode_allows_automatic(frequency)
            assert (
                automatic_teaching_enabled_of(
                    stage=stage, teaching_frequency=frequency
                )
                is expected
            ), (stage, frequency)


def test_off_refuses_at_every_stage() -> None:
    for stage in ROLLOUT_STAGES:
        assert (
            automatic_teaching_enabled_of(
                stage=stage, teaching_frequency=TeachingFrequency.OFF
            )
            is False
        )


# -- ② the content gate ------------------------------------------------------


def test_the_real_corpus_answers_go_on_all_four_rows_and_the_rollout_stays_held(
    p8world: World,
) -> None:
    """The measured answer at C3-a's truth, as a two-layer statement (旧真值:
    every row 0, four HOLD rows, 14 targets all without a level; C1: the one
    authored R4 target made every row GO; C2-a: nine usable targets; C2-b:
    twenty-eight; C3-a: forty-six; 新真值 C3-b: the sixty-four RESOURCE targets
    reach R4, so
    every row reads sixty-four usable targets — BF-02 §10's "at least one
    target" is met on all four floors — **and the rollout is still held**):
    layer one is the content gate's GO; layer two is the stage leg, which no
    shipped caller declares — ``stage_allows_automatic`` answers False for the
    undeclared stage and for the fail-closed default, and the two-leg
    composition refuses with any frequency word — plus the Calibration100
    volume gate (docs/IMPLEMENTATION_PLAN.md §13's 100/30/2), under which the
    volume floor alone is unmet while the two CORE cells are met under the
    declared reading. Content capable ≠ rollout open."""

    report = corpus_rollout_gate(p8world.curriculum)
    assert isinstance(report, Ok), report
    gate = report.value
    # Layer one: the content gate's four rows all read GO on sixty-four usable
    # targets — 旧真值 was ("PROBE", 0) … ("automatic CURRENT_USER_ERROR", 0).
    assert [(row.row_word, row.usable_targets) for row in gate.rows] == [
        ("PROBE", 64),
        ("user-initiated teaching", 64),
        ("automatic general/review", 64),
        ("automatic CURRENT_USER_ERROR", 64),
    ]
    assert all(row.verdict is RolloutVerdict.GO for row in gate.rows)
    assert gate.verdict is RolloutVerdict.GO
    assert gate.automatic_verdict is RolloutVerdict.GO
    assert gate.targets_considered == 69
    assert gate.targets_without_level == 5
    assert gate.unknown_levels == ()
    assert gate.summary() == (
        "PROBE: required R2_PLANNER_READY, usable targets 64 → GO",
        "user-initiated teaching: required R3_TEACHING_READY, usable targets 64"
        " → GO",
        "automatic general/review: required R3_TEACHING_READY, usable targets 64"
        " → GO",
        "automatic CURRENT_USER_ERROR: required R4_DETECTION_READY, usable"
        " targets 64 → GO",
        "targets: 69 considered, 5 without a level",
        "verdict: GO (automatic rows: GO)",
    )
    # No row blocks, so the report's blocked tail is empty (旧真值: four
    # "blocked: …" lines, one per HOLD row).
    assert gate.blocking_rows == ()
    # Layer two: the rollout stays held. No shipped caller declares a stage,
    # the fail-closed default refuses, the composed two-leg switch refuses
    # with any §5.1 frequency word, and the Calibration100 volume gate is
    # unmet on the artifact's own counts.
    assert stage_allows_automatic(None) is False
    assert stage_allows_automatic(DEFAULT_ROLLOUT_STAGE) is False
    for frequency in (None, *TeachingFrequency):
        assert (
            automatic_teaching_enabled_of(
                stage=None, teaching_frequency=frequency
            )
            is False
        )
    _calibration100_floors_are_readable()


def _calibration100_floors_are_readable() -> None:
    """docs/IMPLEMENTATION_PLAN.md §13's Calibration100 floors (100/30/2),
    read against the built artifact's own counts at C3-b's truth: the volume
    floor is unmet (64 resources < 100), while CORE_A (42 >= 30) and CORE_C
    (22 >= 2) are met under the **声明读法 + Revisit（用户 2026-09-26 裁决）**
    — R3_TEACHING_READY or R4_DETECTION_READY crossed with
    ``content_pedagogical_profile.core_utility`` HIGH / {MEDIUM, LOW}. The
    numbers live in the frozen document and are read from it, and the three
    floors are asserted one per line so they can never be folded into one
    "gate passed" sentence."""

    import re
    import sqlite3
    import tempfile

    from elc.content.build import build_content_db

    plan_text = (
        Path(__file__).resolve().parents[2] / "docs" / "IMPLEMENTATION_PLAN.md"
    ).read_text(encoding="utf-8")
    gates = {
        name: int(re.search(rf"{re.escape(name)} >= (\d+)", plan_text).group(1))
        for name in ("resource_count", "CORE_A", "CORE_C")
    }
    assert gates == {"resource_count": 100, "CORE_A": 30, "CORE_C": 2}

    path = Path(tempfile.mkdtemp()) / "content.db"
    build_content_db(path)
    conn = sqlite3.connect(str(path))
    try:
        resources = conn.execute("SELECT COUNT(*) FROM content_entity").fetchone()[0]
        utilities = {
            str(entity_id): str(band)
            for entity_id, band in conn.execute(
                "SELECT entity_id, core_utility FROM content_pedagogical_profile"
            ).fetchall()
        }
    finally:
        conn.close()
    from elc.content.store import ContentStore
    from elc.curriculum.store import CurriculumContentStore

    store = ContentStore(path)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
        levels = {a.target_id: a.level for a in assessments.value}
    finally:
        store.close()
    banded = [
        target_id
        for target_id, level in levels.items()
        if target_id.startswith("res-")
        and level in ("R3_TEACHING_READY", "R4_DETECTION_READY")
    ]
    core_a = [t for t in banded if utilities.get(t) == "HIGH"]
    core_c = [t for t in banded if utilities.get(t) in ("MEDIUM", "LOW")]
    assert resources < gates["resource_count"]  # volume floor unmet
    assert len(core_a) >= gates["CORE_A"]  # CORE_A met
    assert len(core_c) >= gates["CORE_C"]  # CORE_C met


def test_the_row_words_and_floors_are_bf_02_section_10() -> None:
    assert [(spec.row_word, spec.required_level) for spec in GATE_ROWS] == [
        ("PROBE", "R2_PLANNER_READY"),
        ("user-initiated teaching", "R3_TEACHING_READY"),
        ("automatic general/review", "R3_TEACHING_READY"),
        ("automatic CURRENT_USER_ERROR", "R4_DETECTION_READY"),
    ]
    automatic = [spec.row_word for spec in GATE_ROWS if spec.automatic]
    assert automatic == [
        "automatic general/review",
        "automatic CURRENT_USER_ERROR",
    ]


def _facts_for(level: str) -> ReadinessFacts:
    """A **legal** assessment at exactly ``level``: every fact the rungs up to
    it require is present, and nothing above it is. Judged by the ladder's own
    ``judge_readiness``, so the fixture cannot claim a level the ladder would
    not (no fixture *target* provider exists here — the P5-1 red line)."""

    keys = set(required_fact_keys(level))
    values: dict[str, object] = {"target_id": "res-legal"}
    for key in keys:
        if key == "typical_error_when_needed":
            continue
        values[key] = True
    facts = ReadinessFacts(**values)  # type: ignore[arg-type]
    assert judge_readiness(facts).level == level
    return facts


@pytest.mark.parametrize(
    "level,expected",
    [
        ("R0_INDEXED", (0, 0, 0, 0)),
        ("R1_LEXICALLY_RESOLVED", (0, 0, 0, 0)),
        ("R2_PLANNER_READY", (1, 0, 0, 0)),
        ("R3_TEACHING_READY", (1, 1, 1, 0)),
        ("R4_DETECTION_READY", (1, 1, 1, 1)),
    ],
)
def test_a_legal_assessment_turns_exactly_the_rows_it_should(
    level: str, expected: tuple[int, int, int, int]
) -> None:
    report = rollout_gate_of(
        [("res-legal", judge_readiness(_facts_for(level)).level)]
    )
    assert tuple(row.usable_targets for row in report.rows) == expected
    assert report.targets_considered == 1
    assert report.targets_without_level == 0


def test_the_r4_assessment_turns_every_row_go() -> None:
    report = rollout_gate_of(
        [("res-legal", judge_readiness(_facts_for("R4_DETECTION_READY")).level)]
    )
    assert report.verdict is RolloutVerdict.GO
    assert report.automatic_verdict is RolloutVerdict.GO
    assert report.blocking_rows == ()


def test_a_none_level_is_never_usable() -> None:
    report = rollout_gate_of([(f"res-{index}", None) for index in range(14)])
    assert all(row.usable_targets == 0 for row in report.rows)
    assert report.targets_without_level == 14
    assert report.verdict is RolloutVerdict.HOLD


def test_an_unknown_level_word_is_recorded_and_not_counted() -> None:
    report = rollout_gate_of([("res-future", "R9_FUTURE")])
    assert report.unknown_levels == ("R9_FUTURE",)
    assert all(row.usable_targets == 0 for row in report.rows)


def test_the_overall_verdict_is_the_conjunction_over_every_row() -> None:
    """The registered reading: a corpus that can only serve PROBE is HOLD —
    the task book's "both automatic rows 0 ⇒ HOLD" is the other direction of
    the same rule, and a GO needs every row."""

    report = rollout_gate_of([("res-legal", "R2_PLANNER_READY")])
    assert report.row("PROBE").verdict is RolloutVerdict.GO
    assert (
        report.row("automatic general/review").verdict is RolloutVerdict.HOLD
    )
    assert report.automatic_verdict is RolloutVerdict.HOLD
    assert report.verdict is RolloutVerdict.HOLD
    assert [row.row_word for row in report.blocking_rows] == [
        "user-initiated teaching",
        "automatic general/review",
        "automatic CURRENT_USER_ERROR",
    ]


def test_both_automatic_rows_zero_answers_hold() -> None:
    """The task book's explicit condition, as a test of its own."""

    report = rollout_gate_of([("res-legal", "R3_TEACHING_READY")])
    assert report.automatic_verdict is RolloutVerdict.HOLD
    assert report.verdict is RolloutVerdict.HOLD
    assert [
        row.row_word for row in report.automatic_rows if row.usable_targets == 0
    ] == ["automatic CURRENT_USER_ERROR"]


def test_a_target_at_r3_leaves_only_the_detection_row_blocked() -> None:
    report = rollout_gate_of([("res-legal", "R3_TEACHING_READY")])
    assert report.row("automatic general/review").verdict is RolloutVerdict.GO
    assert (
        report.row("automatic CURRENT_USER_ERROR").verdict
        is RolloutVerdict.HOLD
    )
    assert report.automatic_verdict is RolloutVerdict.HOLD


def test_gate_row_verdict_is_the_executable_condition() -> None:
    assert gate_row_verdict(0) is RolloutVerdict.HOLD
    assert gate_row_verdict(1) is RolloutVerdict.GO
    assert gate_row_verdict(14) is RolloutVerdict.GO


def test_usable_targets_for_counts_by_rank_and_never_by_word_order() -> None:
    levels = ["R0_INDEXED", "R2_PLANNER_READY", None, "R3_TEACHING_READY"]
    assert usable_targets_for(levels, required_level="R2_PLANNER_READY") == 2
    assert usable_targets_for(levels, required_level="R3_TEACHING_READY") == 1
    assert usable_targets_for(levels, required_level="R4_DETECTION_READY") == 0
    assert usable_targets_for(levels, required_level="R1_LEXICALLY_RESOLVED") == 2


def test_the_rank_table_is_the_kernels_readiness_rank() -> None:
    """One rank, two spellings: the checker's table is held against
    ``elc.planner.kernel.READINESS_RANK``'s by value."""

    from elc.planner.kernel import READINESS_RANK as KERNEL_RANK
    from elc.planner.kernel import ReadinessLevel

    assert {level.value: rank for level, rank in KERNEL_RANK.items()} == dict(
        READINESS_RANK
    )
    assert READINESS_RANK["R0_INDEXED"] == 0
    assert READINESS_RANK[ReadinessLevel.R4_DETECTION_READY.value] == 4


def test_usable_targets_for_refuses_an_unknown_threshold() -> None:
    with pytest.raises(ValueError):
        usable_targets_for(["R3_TEACHING_READY"], required_level="R9_FUTURE")


def test_the_opening_conditions_are_the_ladders_own_keys() -> None:
    conditions = opening_conditions()
    assert [row_word for row_word, _, _ in conditions] == [
        spec.row_word for spec in GATE_ROWS
    ]
    for (row_word, required_level, facts), spec in zip(conditions, GATE_ROWS):
        assert required_level == spec.required_level
        assert facts == required_fact_keys(required_level)
        assert "assessment_membership" in facts  # R0's third named thing
    ordered = [
        level
        for level, _ in sorted(READINESS_RANK.items(), key=lambda item: item[1])
    ]
    for index in range(1, len(ordered)):
        assert set(required_fact_keys(ordered[index - 1])) <= set(
            required_fact_keys(ordered[index])
        )


def test_the_opening_condition_list_is_the_rows_own() -> None:
    assert [word for word, _ in GATE_OPENING_CONDITIONS] == [
        spec.row_word for spec in GATE_ROWS
    ]
    for _, condition in GATE_OPENING_CONDITIONS:
        assert "at least one target reaches" in condition


def test_a_failed_read_is_returned_untouched() -> None:
    """A readiness table that cannot be read has no gate answer: the ``Err``
    passes through (neither a manufactured HOLD nor a manufactured GO)."""

    error = DomainError(
        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE, message="no corpus"
    )

    class Broken:
        def readiness_by_target(
            self,
        ) -> Result[tuple[ReadinessAssessment, ...]]:
            return Err(error)

    answer = corpus_rollout_gate(Broken())
    assert isinstance(answer, Err)
    assert answer.error is error


# -- ③ the wiring ------------------------------------------------------------


def test_the_mode_leg_reaches_the_gate_through_the_planners_value(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """A §5.1 row written as ``OFF`` refuses **at the Gate**, even with the
    most permissive stage declared and a proposal the run really selects: the
    Planner assembles ``automatic_teaching_enabled=False`` from the policy,
    the wiring's conjunction keeps it, and the Gate answers with the switch's
    own word. The control case (the same proposal under ``MINIMAL``) ALLOWs,
    so the refusal cannot be an artifact of the proposal."""

    written = p8world.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=USER,
            policy_version=PolicyVersion("pv-p8-5-off"),
            teaching_frequency=TeachingFrequency.OFF,
        )
    )
    assert isinstance(written, Ok), written
    hint = supply_of(
        proposal(
            "cand-p8-5-off",
            benefit=HIGH_UTILITY_BENEFIT,
            schedule_urgency=1.0,
        )
    )
    completion = begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(
                p8world,
                supply=hint,
                rollout_stage=RolloutStage.LOUNGE,
            ),
        ),
        "cm-off",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert db.execute(
        "SELECT decision FROM planner_decision"
    ).fetchone() == ("SELECT",)
    assert db.execute(
        "SELECT context, decision, reason_codes FROM gate_decision"
    ).fetchone() == ("OPEN", "DENY", '["AUTO_TEACH_DISABLED"]')
    assert counts(db, "teaching_moment", "active_teaching_lock") == {
        "teaching_moment": 0,
        "active_teaching_lock": 0,
    }


def test_the_same_proposal_allows_under_an_engaged_policy(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """The control for the test above: ``MINIMAL``'s own flag is True, so the
    identical run through the identical stage ALLOWs. ``MINIMAL`` maps to the
    LOUNGE *profile* too — so the only difference between the two runs is the
    §5.1 mode leg, which is exactly what the composition claims."""

    hint = supply_of(
        proposal(
            "cand-p8-5-off",
            benefit=HIGH_UTILITY_BENEFIT,
            schedule_urgency=1.0,
        )
    )
    written = p8world.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=USER,
            policy_version=PolicyVersion("pv-p8-5-minimal"),
            teaching_frequency=TeachingFrequency.MINIMAL,
        )
    )
    assert isinstance(written, Ok), written
    completion = begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(
                p8world, supply=hint, rollout_stage=RolloutStage.LOUNGE
            ),
        ),
        "cm-minimal",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert db.execute(
        "SELECT context, decision FROM gate_decision"
    ).fetchone() == ("OPEN", "ALLOW")
    assert counts(db, "teaching_moment") == {"teaching_moment": 1}


def test_an_off_policy_stops_at_the_activation_threshold_with_the_frozen_vector(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """The mode leg has a second, earlier effect and it is registered here:
    ``OFF`` assembles at BF-02's LOUNGE **profile**, whose activation threshold
    the frozen §20 vector (utility 0.3175) does not clear — so that run is
    ``NO_TARGET``/``BELOW_ACTIVATION_THRESHOLD`` and never reaches a Gate at
    all. Both effects are the same policy answer; a reader must not read the
    absence of a Gate row as "the mode leg did nothing"."""

    written = p8world.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=USER,
            policy_version=PolicyVersion("pv-p8-5-off"),
            teaching_frequency=TeachingFrequency.OFF,
        )
    )
    assert isinstance(written, Ok), written
    completion = begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(
                p8world,
                supply=acceptance_supply(),
                rollout_stage=RolloutStage.LOUNGE,
            ),
        ),
        "cm-off-frozen",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert db.execute(
        "SELECT decision, no_target_reason FROM planner_decision"
    ).fetchone() == ("NO_TARGET", "BELOW_ACTIVATION_THRESHOLD")
    assert counts(db, "gate_decision") == {"gate_decision": 0}
    assert counts(db, "teaching_moment") == {"teaching_moment": 0}


@pytest.mark.parametrize(
    "stage",
    [RolloutStage.STUDY_FIRST, RolloutStage.BALANCED, RolloutStage.LOUNGE],
)
def test_a_declared_automatic_stage_opens_the_same_way(
    db: sqlite3.Connection, fence, p8world: World, stage: RolloutStage
) -> None:
    completion = begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(
                p8world, supply=acceptance_supply(), rollout_stage=stage
            ),
        ),
        f"cm-{stage.name.lower()}",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert db.execute(
        "SELECT context, decision FROM gate_decision"
    ).fetchone() == ("OPEN", "ALLOW")
    assert counts(db, *TEACHING_FACT_TABLES) == dict.fromkeys(
        TEACHING_FACT_TABLES, 1
    )
    assert count_events(db) == 1


@pytest.mark.parametrize("stage", [None, RolloutStage.MANUAL_USER_INITIATED])
def test_an_undeclared_or_manual_stage_denies_the_automatic_open(
    db: sqlite3.Connection, fence, p8world: World, stage: RolloutStage | None
) -> None:
    """The fail-closed answer, end to end: the Planner half is durable (the run
    really happened), the Gate DENYs with the automatic switch's own word, and
    nothing teaching-shaped exists — no moment, no lock, no exposure event."""

    completion = begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(
                p8world, supply=acceptance_supply(), rollout_stage=stage
            ),
        ),
        "cm-closed",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert not str(completion.action_id).endswith("-automatic-open")
    assert completion.ledger_event is None
    assert counts(db, *PLANNER_FACT_TABLES) == dict.fromkeys(
        PLANNER_FACT_TABLES, 1
    )
    assert db.execute(
        "SELECT context, decision, reason_codes FROM gate_decision"
    ).fetchone() == ("OPEN", "DENY", '["AUTO_TEACH_DISABLED"]')
    # The DENY's own two facts are durable; nothing that means an episode is.
    assert counts(db, "gate_execution_status") == {"gate_execution_status": 1}
    assert counts(db, "teaching_moment", "active_teaching_lock") == {
        "teaching_moment": 0,
        "active_teaching_lock": 0,
    }
    assert count_events(db) == 0


def test_the_real_corpus_answers_no_target_with_or_without_a_stage(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """The stage never invents targets: over the shipped corpus the run is
    ``NO_TARGET`` whether or not a stage is declared (the content gap is the
    binding constraint)."""

    for stage in (RolloutStage.STUDY_FIRST, None):
        completion = begin_turn_ok(
            build_coordinator(
                p8world,
                automatic=wiring(
                    p8world, supply=None, rollout_stage=stage
                ),
            ),
            f"cm-real-{stage}",
        )
        assert completion.outcome == "REPLIED_FULL"
    assert counts(db, "gate_decision") == {"gate_decision": 0}
    assert counts(db, "teaching_moment") == {"teaching_moment": 0}
    rows = db.execute(
        "SELECT decision, selected_candidate_id FROM planner_decision ORDER BY rowid"
    ).fetchall()
    assert rows == [("NO_TARGET", None), ("NO_TARGET", None)]


@pytest.mark.parametrize(
    "stage,expected",
    [
        (RolloutStage.STUDY_FIRST, True),
        (RolloutStage.BALANCED, True),
        (RolloutStage.LOUNGE, True),
        (None, False),
        (RolloutStage.MANUAL_USER_INITIATED, False),
    ],
)
def test_the_inner_assembly_composes_both_legs(
    p8world: World, stage: RolloutStage | None, expected: bool
) -> None:
    """The read half's own answer, with no durable cycle needed: the Planner's
    assembled value is ``True`` over this policy (the mode leg), and the stage
    leg is what the controls carry."""

    from elc.runtime.automatic_turn import assemble_automatic_turn

    plan = assemble_automatic_turn(
        wiring=wiring(
            p8world, supply=acceptance_supply(), rollout_stage=stage
        ),
        conversation_id=CONV,
        decision_cycle_id="dc-p8-5-compose",
        as_of=AS_OF,
    )
    assert isinstance(plan, Ok), plan
    assert plan.value.run.trace.context.automatic_teaching_enabled is True
    assert plan.value.controls.automatic_teaching_enabled is expected
