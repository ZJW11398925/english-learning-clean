"""Attempt evaluator v0 — a pure, deterministic, no-LLM evaluator.

Phase 3 P3-1B, TASK-…2.2 ④ (design authority DEC-…2babb21e.5 Q4). The
evaluator answers exactly one question — *what did this attempt realize?* —
and answers it from the target's own validated answer key (the P3-1B
fixtures; Phase 5 replaces the key source with content.db), never from a
model and never from a fuzzy heuristic.

Decision order (fixed, documented, tested):

1. no attempt text / nothing left after normalization  → ``ABSTAIN``
   (真不可判定: there is no attempt to judge — the §5 value that exists so
   "unjudgeable" is never laundered into FAILURE);
2. normalized text equals a canonical form              → ``SUCCESS``
3. normalized text equals an allowed alternative
   realization (the fixture whitelist)                  → ``ALTERNATIVE_SUCCESS``
4. every required slot of the key is covered by
   whole-token presence                                 → ``PARTIAL``
5. otherwise                                            → ``FAILURE``

"I am not a substring matcher": steps 2 and 3 are WHOLE-ANSWER equality
over normalized text, so "I think so" never counts as the canonical form
"I think" merely because it contains it. Step 4 is whole-token coverage
across the key's declared slot groups, which is a declared, reviewable
fact about the target — not a general substring rule (the task book's
"无通用 substring 当 SUCCESS").

The five STATE_MACHINES §5 values are returned as-is: ``ALTERNATIVE_
SUCCESS`` is NOT folded into SUCCESS here. Folding it is the Learning
evidence conversion's job (capability positive + resource neutral), which
is exactly why the durable ``attempt_evaluation_record.outcome`` CHECK
carries all five words (migration 0008).

Everything in this module is pure: no storage, no clock, no randomness —
the same (text, key) pair always yields the same evaluation, and the
confidence of a decision is a fixed function of which rule fired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from elc.teaching.types import AttemptOutcome

__all__ = [
    "ATTEMPT_EVALUATOR_ID",
    "ATTEMPT_EVALUATOR_VERSION",
    "EVALUATION_BASES",
    "TARGET_UNRESOLVED_BASIS",
    "AttemptAnswerKey",
    "AttemptEvaluation",
    "evaluate_attempt",
    "normalize_answer",
    "unjudgeable_evaluation",
]

#: The evaluator's identity (docs/DATA_MODEL.md §17 ``evaluator_id`` /
#: ``evaluator_version`` columns; the §25 evidence-commit key includes the
#: evaluator version, so a v1 evaluator is a new evidence identity).
ATTEMPT_EVALUATOR_ID = "attempt-evaluator-v0"
ATTEMPT_EVALUATOR_VERSION = "v0"

#: The basis words recorded with an evaluation (durable trace of WHICH
#: rule fired — never evidence on their own). ``TARGET_UNRESOLVED`` is the
#: unjudgeable case: the target's key could not be resolved at all, so the
#: attempt is an ABSTAIN and *never* a FAILURE — a resolver outage must not
#: become a negative claim about the learner.
EVALUATION_BASES = (
    "NO_ATTEMPT",
    "CANONICAL_FORM_EXACT",
    "ALTERNATIVE_REALIZATION_EXACT",
    "REQUIRED_SLOT_COVERAGE",
    "NO_MATCH",
    "TARGET_UNRESOLVED",
)

#: The unjudgeable basis word (see :data:`EVALUATION_BASES`).
TARGET_UNRESOLVED_BASIS = "TARGET_UNRESOLVED"

#: Fixed confidences per basis: an exact whole-answer match is certain; a
#: slot-coverage PARTIAL is a weaker judgement and says so. Nothing here is
#: a learner claim — evidence carries its own evaluator_confidence, mapped
#: from these values by the evidence builder.
_CONFIDENCE_BY_BASIS = {
    "NO_ATTEMPT": 0.0,
    "CANONICAL_FORM_EXACT": 1.0,
    "ALTERNATIVE_REALIZATION_EXACT": 1.0,
    "REQUIRED_SLOT_COVERAGE": 0.5,
    "NO_MATCH": 0.5,
    "TARGET_UNRESOLVED": 0.0,
}

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = re.compile(r"^[^\w]+|[^\w]+$")
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class AttemptAnswerKey:
    """One target's validated answer key (the fixture whitelist).

    ``canonical_forms`` — the forms the target is teaching, word for word.
    ``alternative_realizations`` — other realizations that count as a
    valid realization of the same capability (STATE_MACHINES §5 "valid
    capability success"); matching one is ``ALTERNATIVE_SUCCESS``, never a
    plain ``SUCCESS``.
    ``required_slots`` — groups of tokens; an attempt that carries every
    group (any one token per group) is a ``PARTIAL`` realization.

    An empty key is a legal, honest value ("this target's key is not
    available in this phase") and yields FAILURE for any concrete attempt
    — the worst case is a plain FAILURE, never a fabricated SUCCESS.
    """

    canonical_forms: tuple[str, ...] = ()
    alternative_realizations: tuple[str, ...] = ()
    required_slots: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class AttemptEvaluation:
    """One evaluation result: the §5 outcome, its confidence and the basis
    word that produced it."""

    outcome: AttemptOutcome
    confidence: float
    basis: str
    matched_form: str | None = None


def normalize_answer(text: str) -> str:
    """Canonical comparison form: casefolded, whitespace-collapsed, edge
    punctuation stripped. Deterministic and idempotent — the evaluator
    normalizes its own input, so a caller never has to."""

    collapsed = _WHITESPACE.sub(" ", text).strip()
    stripped = _EDGE_PUNCTUATION.sub("", collapsed)
    return stripped.casefold()


def _tokens(text: str) -> tuple[str, ...]:
    """Whole tokens of a normalized answer.

    Splitting on word characters (not on spaces) is what makes the slot
    coverage a *token* check: ``rain, i think`` covers the ``rain`` group
    exactly like ``rain i think`` does. The comparison itself stays
    whole-answer equality — this function only feeds step 4.
    """

    return tuple(_WORD.findall(normalize_answer(text)))


def _qualified(text: str, forms: tuple[str, ...]) -> str | None:
    """Whole-answer equality against a form list (never substring)."""

    normalized = normalize_answer(text)
    if not normalized:
        return None
    for form in forms:
        if normalized == normalize_answer(form):
            return form
    return None


def evaluate_attempt(
    text: str | None, key: AttemptAnswerKey
) -> AttemptEvaluation:
    """Evaluate one attempt against one target's validated key."""

    normalized = normalize_answer(text or "")
    if not normalized:
        return AttemptEvaluation(
            outcome=AttemptOutcome.ABSTAIN,
            confidence=_CONFIDENCE_BY_BASIS["NO_ATTEMPT"],
            basis="NO_ATTEMPT",
        )
    canonical = _qualified(normalized, key.canonical_forms)
    if canonical is not None:
        return AttemptEvaluation(
            outcome=AttemptOutcome.SUCCESS,
            confidence=_CONFIDENCE_BY_BASIS["CANONICAL_FORM_EXACT"],
            basis="CANONICAL_FORM_EXACT",
            matched_form=canonical,
        )

    alternative = _qualified(normalized, key.alternative_realizations)
    if alternative is not None:
        return AttemptEvaluation(
            outcome=AttemptOutcome.ALTERNATIVE_SUCCESS,
            confidence=_CONFIDENCE_BY_BASIS["ALTERNATIVE_REALIZATION_EXACT"],
            basis="ALTERNATIVE_REALIZATION_EXACT",
            matched_form=alternative,
        )

    if key.required_slots:
        tokens = _tokens(normalized)
        if all(
            any(token in tokens for token in group) for group in key.required_slots
        ):
            return AttemptEvaluation(
                outcome=AttemptOutcome.PARTIAL,
                confidence=_CONFIDENCE_BY_BASIS["REQUIRED_SLOT_COVERAGE"],
                basis="REQUIRED_SLOT_COVERAGE",
            )

    return AttemptEvaluation(
        outcome=AttemptOutcome.FAILURE,
        confidence=_CONFIDENCE_BY_BASIS["NO_MATCH"],
        basis="NO_MATCH",
    )


def unjudgeable_evaluation(basis: str = TARGET_UNRESOLVED_BASIS) -> AttemptEvaluation:
    """The evaluator's honest "cannot judge this" result.

    Used when there is no key to judge against at all (the moment's target
    could not be resolved in this phase). The §5 value is ``ABSTAIN`` on
    purpose: an unjudgeable attempt must never be laundered into FAILURE,
    because a FAILURE is a negative claim about the learner and an outage
    is not.
    """

    return AttemptEvaluation(
        outcome=AttemptOutcome.ABSTAIN,
        confidence=_CONFIDENCE_BY_BASIS.get(basis, 0.0),
        basis=basis,
    )
