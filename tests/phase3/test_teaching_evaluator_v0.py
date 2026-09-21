"""VAL ④ — evaluator v0 (pure, deterministic, no LLM) and the ladder's
pure one-way rule.

The evaluator answers exactly one question — what did this attempt realize? —
from the target's own validated answer key, and it can never be talked into
SUCCESS by a substring: steps 2 and 3 are whole-answer equality over
normalized text, step 4 is a declared slot-coverage check, and an
unjudgeable attempt is an ABSTAIN (never a FAILURE, because a FAILURE is a
negative claim and an outage is not).
"""

from __future__ import annotations

import pytest

from elc.teaching.evaluator import (
    ATTEMPT_EVALUATOR_ID,
    ATTEMPT_EVALUATOR_VERSION,
    EVALUATION_BASES,
    TARGET_UNRESOLVED_BASIS,
    AttemptAnswerKey,
    evaluate_attempt,
    normalize_answer,
    unjudgeable_evaluation,
)
from elc.teaching.ladder import (
    evidence_support_level,
    is_post_reveal_attempt,
    ladder_step,
    ladder_step_refusal,
)
from elc.teaching.types import (
    AttemptOutcome,
    PresentationPhase,
    TeachingSupportLevel,
)
from tests.phase3.target_fixtures import (
    TEACHING_CONTENT,
    FixtureTeachingTargetProvider,
)

KEY = AttemptAnswerKey(
    canonical_forms=("I think it is going to rain.",),
    alternative_realizations=("It might rain.",),
    required_slots=(("rain",), ("think", "guess", "reckon")),
)


def test_evaluator_identity_is_version_pinned() -> None:
    assert ATTEMPT_EVALUATOR_ID == "attempt-evaluator-v0"
    assert ATTEMPT_EVALUATOR_VERSION == "v0"
    assert TARGET_UNRESOLVED_BASIS in EVALUATION_BASES


def test_normalization_is_deterministic_and_idempotent() -> None:
    once = normalize_answer("  I THINK it is going to rain.  ")
    assert once == "i think it is going to rain"
    assert normalize_answer(once) == once


@pytest.mark.parametrize(
    ("text", "expected", "basis"),
    (
        (
            "I think it is going to rain.",
            AttemptOutcome.SUCCESS,
            "CANONICAL_FORM_EXACT",
        ),
        (
            "i think it is going to rain",
            AttemptOutcome.SUCCESS,
            "CANONICAL_FORM_EXACT",
        ),
        (
            "It might rain.",
            AttemptOutcome.ALTERNATIVE_SUCCESS,
            "ALTERNATIVE_REALIZATION_EXACT",
        ),
        (
            "it might rain",
            AttemptOutcome.ALTERNATIVE_SUCCESS,
            "ALTERNATIVE_REALIZATION_EXACT",
        ),
        ("rain, I think", AttemptOutcome.PARTIAL, "REQUIRED_SLOT_COVERAGE"),
        ("the cat sat on the mat", AttemptOutcome.FAILURE, "NO_MATCH"),
    ),
)
def test_the_five_values_are_a_fixed_function_of_text_and_key(
    text: str, expected: AttemptOutcome, basis: str
) -> None:
    evaluation = evaluate_attempt(text, KEY)
    assert evaluation.outcome is expected
    assert evaluation.basis == basis
    # Determinism: the same pair always yields the same evaluation.
    assert evaluate_attempt(text, KEY) == evaluation


def test_no_substring_rule_can_produce_success() -> None:
    """The canonical form is "I think it is going to rain." — a longer or
    shorter text that merely contains pieces of it is never a SUCCESS."""

    assert evaluate_attempt("I think", KEY).outcome is not AttemptOutcome.SUCCESS
    assert (
        evaluate_attempt("I think it is going to rain, maybe", KEY).outcome
        is not AttemptOutcome.SUCCESS
    )
    assert (
        evaluate_attempt("So I think it is going to rain.", KEY).outcome
        is AttemptOutcome.PARTIAL
    )
    assert evaluate_attempt("I think it will rain", KEY).outcome in (
        AttemptOutcome.PARTIAL,
        AttemptOutcome.FAILURE,
    )


def test_an_empty_attempt_is_abstain_and_an_empty_key_is_never_success() -> None:
    empty_attempt = evaluate_attempt("   ", KEY)
    assert empty_attempt.outcome is AttemptOutcome.ABSTAIN
    assert empty_attempt.confidence == 0.0
    # An empty key (no validated content in this phase) is honest: any
    # concrete attempt is a FAILURE, never a fabricated SUCCESS.
    assert evaluate_attempt("anything", AttemptAnswerKey()).outcome is (
        AttemptOutcome.FAILURE
    )


def test_unjudgeable_evaluation_is_an_abstain_with_its_own_basis() -> None:
    unjudgeable = unjudgeable_evaluation()
    assert unjudgeable.outcome is AttemptOutcome.ABSTAIN
    assert unjudgeable.basis == TARGET_UNRESOLVED_BASIS
    assert unjudgeable.confidence == 0.0


def test_the_alternative_success_is_not_folded_into_success() -> None:
    """④: the five-value set is preserved by the evaluator; folding is the
    Learning evidence conversion's job."""

    assert evaluate_attempt("It might rain.", KEY).outcome is (
        AttemptOutcome.ALTERNATIVE_SUCCESS
    )


def test_every_validated_fixture_has_a_usable_answer_key() -> None:
    provider = FixtureTeachingTargetProvider()
    for target_id in TEACHING_CONTENT:
        for target_type in ("RESOURCE", "CAPABILITY"):
            resolved = provider.resolve(target_type, target_id)
            if isinstance(resolved, Exception):  # pragma: no cover - defensive
                continue
            if getattr(resolved, "value", None) is None:
                continue
            view = resolved.value
            answer_key = view.answer_key()
            assert answer_key.canonical_forms, target_id
            # Every canonical form evaluates to SUCCESS against its own key.
            for form in answer_key.canonical_forms:
                assert evaluate_attempt(form, answer_key).outcome is (
                    AttemptOutcome.SUCCESS
                )
            for alternative in view.alternative_realizations:
                assert evaluate_attempt(alternative, answer_key).outcome is (
                    AttemptOutcome.ALTERNATIVE_SUCCESS
                )


# ---------------------------------------------------------------------------
# the ladder's pure rules
# ---------------------------------------------------------------------------


def test_ladder_step_never_moves_backwards() -> None:
    first = ladder_step(
        current_phase=PresentationPhase.INITIAL_PROMPT.value,
        current_support=TeachingSupportLevel.CONTEXT_ONLY.value,
        hint_ladder=("h1", "h2", "h3"),
        reveal_form="the form",
        delivery_kind="HINT",
    )
    assert first.presentation_phase is PresentationPhase.HINT_SEMANTIC
    second = ladder_step(
        current_phase=first.presentation_phase.value,
        current_support=first.support_level.value,
        hint_ladder=("h1", "h2", "h3"),
        reveal_form="the form",
        delivery_kind="HINT",
    )
    assert second.presentation_phase is PresentationPhase.HINT_STRUCTURAL
    # A backwards move is refused by the pure rule (the store's CAS would
    # otherwise happily write it).
    refusal = ladder_step_refusal(
        second.presentation_phase.value,
        second.support_level.value,
        first.presentation_phase.value,
        first.support_level.value,
    )
    assert refusal is not None
    assert refusal.code.value == "VALIDATION_FAILED"


def test_evidence_support_never_drops_below_the_real_exposure() -> None:
    assert evidence_support_level(
        TeachingSupportLevel.FULL_FORM_SHOWN.value,
        TeachingSupportLevel.NONE.value,
    ) is TeachingSupportLevel.FULL_FORM_SHOWN
    assert evidence_support_level(
        TeachingSupportLevel.SEMANTIC_HINT.value,
        TeachingSupportLevel.NONE.value,
    ) is TeachingSupportLevel.SEMANTIC_HINT
    assert is_post_reveal_attempt(PresentationPhase.FULL_REVEAL.value)
    assert not is_post_reveal_attempt(PresentationPhase.INITIAL_PROMPT.value)
