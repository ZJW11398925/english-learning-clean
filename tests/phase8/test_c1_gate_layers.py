"""C1 (Phase 11) — the rollout gate over the now-capable corpus, layered.

The C1 content work made one corpus target reach R4_DETECTION_READY, which
turns BF-02 §10's four rows GO (each row's executable condition is "at
least one target reaches the floor"). What C1 did **not** do is open the
rollout: the stage leg, the composed two-leg switch and the Calibration100
volume gate are unchanged. This file pins the layers so neither direction
can drift:

- the floors are cumulative (one R4 target serves every row), and a target
  at a lower floor serves only the rows at or below it;
- the gate itself did not move: an all-None table still answers HOLD on
  every row (the pre-C1 answer is one input away, not deleted);
- capable + undeclared stage is still refused, while capable + *declared*
  stage composes to True — the stage declaration is the only door between
  the capable corpus and automatic teaching, and C1 left its lock intact.
"""

from __future__ import annotations

from elc.teaching.rollout import (
    RolloutStage,
    RolloutVerdict,
    automatic_teaching_enabled_of,
    rollout_gate_of,
    stage_allows_automatic,
    usable_targets_for,
)
from elc.user_config.types import TeachingFrequency

R4 = "R4_DETECTION_READY"
R2 = "R2_PLANNER_READY"


def test_the_floors_are_cumulative_and_a_lower_floor_leaks_nothing_upward() -> None:
    """One R4 target is usable for every row (R2 ⊆ R3 ⊆ R4 cumulative); a
    target at R2 only serves the PROBE row — usable_targets_for reads the
    ladder's rank, never a row's own word."""

    levels = {"res-one": R4, "res-two": None}
    assert usable_targets_for(levels.values(), required_level=R2) == 1
    assert usable_targets_for(levels.values(), required_level=R4) == 1
    r2_only = {"res-three": R2}
    assert usable_targets_for(r2_only.values(), required_level=R2) == 1
    assert usable_targets_for(r2_only.values(), required_level=R4) == 0


def test_the_gate_did_not_move_an_all_none_table_still_answers_hold() -> None:
    """Anti-overcorrection pin: C1 moved the corpus, never the checker. The
    pre-C1 table (every target without a level) still produces four HOLD
    rows and a HOLD verdict, with the blocked tail populated."""

    report = rollout_gate_of([(f"res-{index}", None) for index in range(14)])
    assert report.verdict is RolloutVerdict.HOLD
    assert report.automatic_verdict is RolloutVerdict.HOLD
    assert all(row.verdict is RolloutVerdict.HOLD for row in report.rows)
    assert report.targets_without_level == 14
    assert report.summary()[-4:] == tuple(
        f"blocked: {row.line()}" for row in report.rows
    )


def test_the_stage_declaration_is_the_only_door_and_it_is_still_locked() -> None:
    """Content GO + undeclared stage ⇒ refused (C1's state); content GO +
    declared stage ⇒ the composition answers True — proving C1 did not
    hard-code a deny into the composed switch. The lock is the absence of a
    declared stage in the shipped product, not a change to the lock."""

    assert stage_allows_automatic(None) is False
    assert (
        automatic_teaching_enabled_of(
            stage=None, teaching_frequency=TeachingFrequency.BALANCED
        )
        is False
    )
    assert stage_allows_automatic(RolloutStage.STUDY_FIRST) is True
    assert (
        automatic_teaching_enabled_of(
            stage=RolloutStage.STUDY_FIRST,
            teaching_frequency=TeachingFrequency.BALANCED,
        )
        is True
    )
