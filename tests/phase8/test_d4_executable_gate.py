"""D-4 — the provenance hard gate: the fifth leg on the rollout wiring.

EXT-C3-03's wiring half, closed here: the automatic CURRENT_USER_ERROR row
now *can* demand, at the rollout layer, that a target be not merely R4 but
executably verified — as a **declared reading** beside the frozen BF-02 §10
lines (the marker is a field, the document is untouched, and a call without
a provenance mapping is field for field the historical four-floor answer).
Pinned here:

- **the row spec**: the marker sits on the automatic CURRENT_USER_ERROR row
  alone, and the four rows' frozen fields (word, floor, automatic, facts)
  are unchanged from the parent (hard-coded from the parent's own values);
- **the fifth leg, both ways**: over a synthetic corpus shaped like the
  shipped one (52×R4 + 48×R1 + 5×None — the p8-5 raw-level precedent), a
  36-EV mapping leaves the marked row GO on thirty-six with sixteen held
  back, and a zero-EV mapping holds it with all fifty-two counted as
  blocked;
- **the isolation**: the other three rows never read provenance (their
  readings are identical with and without a mapping), an EV below the
  readiness floor buys nothing, a missing provenance entry fails closed,
  and ``EMPIRICALLY_CALIBRATED`` — the vocabulary's higher rung — passes;
- **the backward compatibility**: ``provenance=None`` answers the plain
  call field for field, every row's blocked count zero;
- **the corpus face**: over the real built artifact the fourth row reads
  GO/36/16 under the D-3 pilot build's provenance and HOLD/0/52 under the
  default build's (zero EV);
- **fail-closed vocabulary**: an unknown provenance word is held, not
  guessed; and the row's receipt line carries the blocked count.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from elc.content.build import build_content_db
from elc.content.store import ContentStore
from elc.content.types import PROVENANCE_LEVELS
from elc.curriculum.store import CurriculumContentStore
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_ENTITIES, register_pilot
from elc.platform.types import Ok
from elc.teaching.rollout import (
    EXECUTABLE_VERIFICATION_FLOOR,
    GATE_ROWS,
    RolloutGateReport,
    RolloutGateRow,
    RolloutVerdict,
    corpus_rollout_gate,
    rollout_gate_of,
)

#: The shipped corpus's readiness shape (52×R4 + 48×R1 + 5×None), synthesized
#: as plain ladder words — the p8-5 raw-level precedent (its own synthetic
#: corpora pass raw words; level *legality* from facts is that file's
#: ``judge_readiness`` tests' subject, not this one's).
_R4_COUNT = 52
_R1_COUNT = 48
_NONE_COUNT = 5

#: The D-3 pilot's size: thirty-six R4 targets verified executable (the
#: same set the real pilot build promotes — asserted against
#: ``PILOT_ENTITIES`` on the corpus face below).
_EV_COUNT = 36


def _synthetic_pairs() -> list[tuple[str, str | None]]:
    pairs: list[tuple[str, str | None]] = [
        (f"res-r4-{index:02d}", "R4_DETECTION_READY")
        for index in range(_R4_COUNT)
    ]
    pairs += [
        (f"res-r1-{index:02d}", "R1_LEXICALLY_RESOLVED")
        for index in range(_R1_COUNT)
    ]
    pairs += [(f"cap-none-{index}", None) for index in range(_NONE_COUNT)]
    return pairs


def _pilot_shaped_provenance(
    *, ev_level: str = EXECUTABLE_VERIFICATION_FLOOR
) -> dict[str, str]:
    """The artifact-shaped mapping: the pilot ids at ``ev_level``,
    every other target at a below-floor word (the default build's truth)."""

    provenance = {
        target_id: "EDITOR_REVIEWED"
        for target_id, _ in _synthetic_pairs()
    }
    for index in range(_EV_COUNT):
        provenance[f"res-r4-{index:02d}"] = ev_level
    return provenance


def _fourth_row(report: RolloutGateReport) -> RolloutGateRow:
    return report.row("automatic CURRENT_USER_ERROR")


# -- ① the row spec -----------------------------------------------------------


def test_the_detection_marker_is_on_the_automatic_error_row_alone() -> None:
    assert [
        spec.requires_executable_detection for spec in GATE_ROWS
    ] == [False, False, False, True]


def test_the_four_rows_frozen_fields_are_the_parents_own() -> None:
    """The §10 semantics did not move: word, floor, automatic flag and the
    cumulative fact keys, hard-coded from the parent's own GATE_ROWS (the
    fifth leg added a field *beside* them, never a value inside)."""

    r2_facts = (
        "entity_row",
        "canonical_form",
        "assessment_membership",
        "pos",
        "sense",
        "basic_definition",
        "forms",
        "curriculum_link",
        "pedagogical_profile",
        "goal_pack_overlay",
        "resource_labels",
    )
    r3_facts = r2_facts + (
        "reviewed_explanation",
        "example_policy",
        "contrast_or_usage",
        "typical_error_when_needed",
    )
    r4_facts = r3_facts + (
        "detection_policy",
        "recognition_rules",
        "negative_fixtures",
        "false_positive_boundaries",
    )
    assert [
        (
            spec.row_word,
            spec.required_level,
            spec.automatic,
            spec.required_facts,
        )
        for spec in GATE_ROWS
    ] == [
        ("PROBE", "R2_PLANNER_READY", False, r2_facts),
        ("user-initiated teaching", "R3_TEACHING_READY", False, r3_facts),
        ("automatic general/review", "R3_TEACHING_READY", True, r3_facts),
        ("automatic CURRENT_USER_ERROR", "R4_DETECTION_READY", True, r4_facts),
    ]


def test_the_provenance_floor_is_the_vocabularys_own_rung() -> None:
    """The floor word is ``PROVENANCE_LEVELS``' own, and the order the leg
    reads is the vocabulary's — EC above EV above EDITOR above AUTHOR."""

    assert EXECUTABLE_VERIFICATION_FLOOR == "EXECUTABLY_VERIFIED"
    assert PROVENANCE_LEVELS == (
        "AUTHOR_DECLARED",
        "EDITOR_REVIEWED",
        "EXECUTABLY_VERIFIED",
        "EMPIRICALLY_CALIBRATED",
    )
    assert PROVENANCE_LEVELS.index("EMPIRICALLY_CALIBRATED") > PROVENANCE_LEVELS.index(
        EXECUTABLE_VERIFICATION_FLOOR
    )


# -- ② the fifth leg, both ways -----------------------------------------------


def test_the_fifth_leg_go_way_counts_twelve_and_names_forty_blocked() -> None:
    row = _fourth_row(
        rollout_gate_of(
            _synthetic_pairs(), provenance=_pilot_shaped_provenance()
        )
    )
    assert row.usable_targets == _EV_COUNT
    assert row.blocked_by_provenance == _R4_COUNT - _EV_COUNT
    assert row.verdict is RolloutVerdict.GO


def test_the_fifth_leg_hold_way_counts_zero_and_names_all_fifty_two() -> None:
    row = _fourth_row(
        rollout_gate_of(
            _synthetic_pairs(),
            provenance=_pilot_shaped_provenance(
                ev_level="EDITOR_REVIEWED"
            ),
        )
    )
    assert row.usable_targets == 0
    assert row.blocked_by_provenance == _R4_COUNT
    assert row.verdict is RolloutVerdict.HOLD


# -- ③ the isolation ----------------------------------------------------------


def test_the_other_three_rows_never_read_provenance() -> None:
    plain = rollout_gate_of(_synthetic_pairs())
    mapped = rollout_gate_of(
        _synthetic_pairs(), provenance=_pilot_shaped_provenance()
    )
    for plain_row, mapped_row in zip(plain.rows[:3], mapped.rows[:3]):
        assert plain_row == mapped_row
        assert mapped_row.blocked_by_provenance == 0
    assert plain.rows[3] != mapped.rows[3]


def test_an_ev_below_the_readiness_floor_buys_nothing() -> None:
    """EV ∧ ¬R4 ⇒ held out of the count entirely: an R1 target with the
    strongest provenance still clears no floor, so it appears neither as
    usable nor as provenance-blocked (the level leg is what puts a target
    in either bucket)."""

    single = _fourth_row(
        rollout_gate_of(
            [("res-lexical", "R1_LEXICALLY_RESOLVED")],
            provenance={
                "res-lexical": EXECUTABLE_VERIFICATION_FLOOR
            },
        )
    )
    assert single.usable_targets == 0
    assert single.blocked_by_provenance == 0
    assert single.verdict is RolloutVerdict.HOLD

    pairs = _synthetic_pairs()
    pairs.append(("res-r1-extra", "R1_LEXICALLY_RESOLVED"))
    provenance = _pilot_shaped_provenance()
    provenance["res-r1-extra"] = EXECUTABLE_VERIFICATION_FLOOR
    row = _fourth_row(rollout_gate_of(pairs, provenance=provenance))
    assert row.usable_targets == _EV_COUNT
    assert row.blocked_by_provenance == _R4_COUNT - _EV_COUNT


def test_a_missing_provenance_entry_fails_closed() -> None:
    """A target the mapping does not mention has no provenance claim — the
    marked row holds it back (an empty mapping blocks every R4 target)."""

    row = _fourth_row(rollout_gate_of(_synthetic_pairs(), provenance={}))
    assert row.usable_targets == 0
    assert row.blocked_by_provenance == _R4_COUNT
    assert row.verdict is RolloutVerdict.HOLD


def test_emperically_calibrated_is_a_higher_rung_and_passes() -> None:
    row = _fourth_row(
        rollout_gate_of(
            _synthetic_pairs(),
            provenance=_pilot_shaped_provenance(
                ev_level="EMPIRICALLY_CALIBRATED"
            ),
        )
    )
    assert row.usable_targets == _EV_COUNT
    assert row.blocked_by_provenance == _R4_COUNT - _EV_COUNT
    assert row.verdict is RolloutVerdict.GO


# -- ④ backward compatibility -------------------------------------------------


def test_provenance_none_answers_the_plain_call_field_for_field() -> None:
    pairs = _synthetic_pairs()
    plain = rollout_gate_of(pairs)
    explicit_none = rollout_gate_of(pairs, provenance=None)
    assert explicit_none == plain
    for row in plain.rows:
        assert row.blocked_by_provenance == 0
    assert plain.verdict is RolloutVerdict.GO
    assert plain.targets_considered == _R4_COUNT + _R1_COUNT + _NONE_COUNT
    assert plain.targets_without_level == _NONE_COUNT


# -- ⑤ the corpus face --------------------------------------------------------


@pytest.fixture(scope="module")
def default_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("d4-default") / "content.db"
    build_content_db(path)
    return path


@pytest.fixture(scope="module")
def pilot_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("d4-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(path, detector_registry=registry)
    return path


def _gate_over(db: Path) -> tuple[int, int, RolloutVerdict, RolloutVerdict]:
    """The real artifact's fourth row (usable, blocked, row verdict) and the
    report's overall verdict, under the build's own provenance mapping."""

    store = ContentStore(db)
    try:
        supply = CurriculumContentStore(store)
        provenance = store.provenance_levels()
        assert isinstance(provenance, Ok), provenance
        report = corpus_rollout_gate(supply, dict(provenance.value))
    finally:
        store.close()
    assert isinstance(report, Ok), report
    row = _fourth_row(report.value)
    return (
        row.usable_targets,
        row.blocked_by_provenance,
        row.verdict,
        report.value.verdict,
    )


def test_the_real_pilot_build_opens_the_fourth_row_on_thirty_six(
    pilot_db: Path,
) -> None:
    usable, blocked, verdict, overall = _gate_over(pilot_db)
    assert usable == _EV_COUNT
    assert blocked == _R4_COUNT - _EV_COUNT
    assert verdict is RolloutVerdict.GO
    assert overall is RolloutVerdict.GO


def test_the_default_build_holds_the_fourth_row_on_zero_ev(
    default_db: Path,
) -> None:
    usable, blocked, verdict, overall = _gate_over(default_db)
    assert usable == 0
    assert blocked == _R4_COUNT
    assert verdict is RolloutVerdict.HOLD
    assert overall is RolloutVerdict.HOLD


def test_the_pilot_ev_set_is_what_the_fourth_row_counts(
    pilot_db: Path,
) -> None:
    """The thirty-six the marked row counts are the pilot entities
    themselves — the D-3 roster, read back through the corpus's own
    provenance face."""

    store = ContentStore(pilot_db)
    try:
        provenance = store.provenance_levels()
        assert isinstance(provenance, Ok), provenance
        levels = dict(provenance.value)
    finally:
        store.close()
    ev = sorted(
        entity
        for entity, level in levels.items()
        if level == EXECUTABLE_VERIFICATION_FLOOR
    )
    assert ev == sorted(PILOT_ENTITIES)


def test_corpus_rollout_gate_without_a_mapping_is_the_plain_answer(
    default_db: Path,
) -> None:
    """The face protocol did not grow a provenance read, and the corpus
    checker without one is field for field the historical GO report."""

    store = ContentStore(default_db)
    try:
        supply = CurriculumContentStore(store)
        plain = corpus_rollout_gate(supply)
        explicit_none = corpus_rollout_gate(supply, None)
    finally:
        store.close()
    assert isinstance(plain, Ok) and isinstance(explicit_none, Ok)
    assert explicit_none.value == plain.value
    assert plain.value.verdict is RolloutVerdict.GO
    assert all(row.blocked_by_provenance == 0 for row in plain.value.rows)


# -- ⑥ fail-closed vocabulary and the receipt ---------------------------------


def test_an_unknown_provenance_word_is_held_not_guessed() -> None:
    pairs = _synthetic_pairs()
    provenance = _pilot_shaped_provenance()
    provenance["res-r4-00"] = "SOMETHING_ELSE"
    row = _fourth_row(rollout_gate_of(pairs, provenance=provenance))
    assert row.usable_targets == _EV_COUNT - 1
    assert row.blocked_by_provenance == _R4_COUNT - _EV_COUNT + 1

    single = _fourth_row(
        rollout_gate_of(
            [("res-lonely", "R4_DETECTION_READY")],
            provenance={"res-lonely": "SOMETHING_ELSE"},
        )
    )
    assert single.usable_targets == 0
    assert single.blocked_by_provenance == 1
    assert single.verdict is RolloutVerdict.HOLD


def test_the_receipt_line_carries_the_blocked_count() -> None:
    mapped = rollout_gate_of(
        _synthetic_pairs(), provenance=_pilot_shaped_provenance()
    )
    fourth = mapped.row("automatic CURRENT_USER_ERROR")
    assert fourth.line() == (
        "automatic CURRENT_USER_ERROR: required R4_DETECTION_READY, usable"
        f" targets {_EV_COUNT} → GO ({_R4_COUNT - _EV_COUNT} blocked by"
        " provenance)"
    )
    # The unmarked rows' lines are byte for byte the historical format —
    # a zero blocked count changes nothing a reader saw before.
    assert mapped.row("PROBE").line() == (
        "PROBE: required R2_PLANNER_READY, usable targets 52 → GO"
    )
    held = rollout_gate_of(
        _synthetic_pairs(),
        provenance=_pilot_shaped_provenance(ev_level="EDITOR_REVIEWED"),
    )
    held_row = held.row("automatic CURRENT_USER_ERROR")
    assert held_row.line() == (
        "automatic CURRENT_USER_ERROR: required R4_DETECTION_READY, usable"
        f" targets 0 → HOLD ({_R4_COUNT} blocked by provenance)"
    )
    assert held.summary()[-1] == (
        "blocked: automatic CURRENT_USER_ERROR: required"
        " R4_DETECTION_READY, usable targets 0 → HOLD (52 blocked by"
        " provenance)"
    )
