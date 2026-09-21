"""Teaching presentation ladder — the SM §3 one-way rule.

docs/STATE_MACHINES.md §3:

    presentation phases: INITIAL_PROMPT, HINT_SEMANTIC, HINT_STRUCTURAL,
        HINT_PARTIAL_FORM, FULL_REVEAL, POST_REVEAL_OPTIONAL_ATTEMPT,
        EXPLANATION
    support levels: NONE, CONTEXT_ONLY, SEMANTIC_HINT, STRUCTURAL_HINT,
        PARTIAL_FORM, FULL_FORM_SHOWN
    "同一个 Moment 内真实 exposure 一旦提高，后续 Evidence 不得假装更少
    支架。"

That sentence is a monotonicity property, and this module is where it is
made mechanical — in two directions:

- **Forward (delivery)**: the ladder never steps *down*. A hint request
  moves to the next ladder rung, a reveal jumps to FULL_REVEAL; nothing in
  the slice may lower the support level or move the phase backwards. The
  rungs themselves come from the target fixture's ``hint_ladder`` (the
  target's validated teaching text) — the provider never picks a stage
  ("provider 不自定阶段"): Persona Runtime only receives the phase/support
  the Teaching domain stamped on the directive.
- **Backward (evidence)**: an attempt's evidence carries at least the
  support the learner was actually exposed to
  (:func:`evidence_support_level`), so a claim may never look "more
  independent" than the real exposure that preceded it. A post-reveal
  attempt is additionally capped
  (:func:`is_post_reveal_attempt`: after FULL_REVEAL a moment produces
  follow-up evidence, never fresh independent evidence).

docs/DOMAIN_MODEL.md §15: "完整答案曝光后，当前 Moment 后续不再产生
independent evidence" — hence ``POST_REVEAL_PERFORMANCE_TYPE``: the
post-reveal claim is an IMITATIVE_PRODUCTION (the learner is reproducing
the rule just shown), and the evidence builder marks it as
``POST_REVEAL_ATTEMPT``.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.platform.types import DomainError, DomainErrorCode
from elc.teaching.types import (
    AnswerExposureState,
    PresentationPhase,
    TeachingSupportLevel,
)

__all__ = [
    "HINT_PHASES",
    "LADDER_PHASES",
    "POST_REVEAL_PHASES",
    "POST_REVEAL_PERFORMANCE_TYPE",
    "PRESENTATION_PHASES",
    "SUPPORT_LEVELS",
    "LadderStep",
    "evidence_answer_exposure",
    "evidence_support_level",
    "hint_rung",
    "is_post_reveal_attempt",
    "ladder_step",
    "ladder_step_refusal",
    "phase_rank",
    "support_rank",
]

#: The §3 phase order as the ladder's ranking (word for word).
LADDER_PHASES = tuple(item.value for item in PresentationPhase)
PRESENTATION_PHASES = LADDER_PHASES

#: The §3 support order (word for word).
SUPPORT_LEVELS = tuple(item.value for item in TeachingSupportLevel)

#: Hint rungs, in ladder order — each one is one presentation phase.
HINT_PHASES = (
    PresentationPhase.HINT_SEMANTIC.value,
    PresentationPhase.HINT_STRUCTURAL.value,
    PresentationPhase.HINT_PARTIAL_FORM.value,
)

#: Phases at/after the full reveal (DOMAIN_MODEL §15: no further
#: independent evidence inside this moment).
POST_REVEAL_PHASES = (
    PresentationPhase.FULL_REVEAL.value,
    PresentationPhase.POST_REVEAL_OPTIONAL_ATTEMPT.value,
    PresentationPhase.EXPLANATION.value,
)

#: The performance type a post-reveal attempt claims (see module docstring).
POST_REVEAL_PERFORMANCE_TYPE = "IMITATIVE_PRODUCTION"

_PHASE_RANK = {phase: index for index, phase in enumerate(LADDER_PHASES)}
_SUPPORT_RANK = {
    support: index for index, support in enumerate(SUPPORT_LEVELS)
}


def phase_rank(phase: str) -> int:
    return _PHASE_RANK[phase]


def support_rank(support: str) -> int:
    return _SUPPORT_RANK[support]


def hint_rung(index: int) -> tuple[PresentationPhase, TeachingSupportLevel]:
    """The (phase, support) of the ladder's ``index``-th hint rung (0-based).

    An absolute address into the ladder — the caller that has to rebuild a
    rung from durable facts (the crash reconciliation of
    ``elc.runtime.controller``) needs the rung itself, not the next step
    relative to wherever the moment happens to be.
    """

    phase = HINT_PHASES[index]
    return PresentationPhase(phase), TeachingSupportLevel(_HINT_SUPPORT[phase])


def ladder_step_refusal(
    current_phase: str, current_support: str, next_phase: str, next_support: str
) -> DomainError | None:
    """The SM §3 one-way rule as a pure refusal (None = allowed).

    Both the phase and the support level must be non-decreasing; the
    support level additionally never exceeds the phase's ceiling
    (:func:`_support_ceiling`), so a moment cannot advertise
    FULL_FORM_SHOWN while still presenting an initial prompt.
    """

    if next_phase not in _PHASE_RANK:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=f"unknown presentation phase: {next_phase}",
        )
    if next_support not in _SUPPORT_RANK:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=f"unknown support level: {next_support}",
        )
    if phase_rank(next_phase) < phase_rank(current_phase):
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"presentation ladder never steps back:"
                f" {current_phase} → {next_phase} (STATE_MACHINES §3)"
            ),
        )
    if support_rank(next_support) < support_rank(current_support):
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"support level never drops inside one moment:"
                f" {current_support} → {next_support} (STATE_MACHINES §3)"
            ),
        )
    if support_rank(next_support) > _support_ceiling(next_phase):
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"support {next_support} exceeds the ceiling of phase"
                f" {next_phase}"
            ),
        )
    return None


def _support_ceiling(phase: str) -> int:
    """The highest support level one phase may claim.

    The initial prompt shows context only; each hint rung reaches exactly
    its own support level; the reveal / post-reveal / explanation phases
    reach FULL_FORM_SHOWN.
    """

    ceiling = {
        PresentationPhase.INITIAL_PROMPT.value: (
            TeachingSupportLevel.CONTEXT_ONLY.value
        ),
        PresentationPhase.HINT_SEMANTIC.value: (
            TeachingSupportLevel.SEMANTIC_HINT.value
        ),
        PresentationPhase.HINT_STRUCTURAL.value: (
            TeachingSupportLevel.STRUCTURAL_HINT.value
        ),
        PresentationPhase.HINT_PARTIAL_FORM.value: (
            TeachingSupportLevel.PARTIAL_FORM.value
        ),
    }.get(phase, TeachingSupportLevel.FULL_FORM_SHOWN.value)
    return support_rank(ceiling)


#: Each hint rung's support level (the rung IS its support level).
_HINT_SUPPORT = {
    PresentationPhase.HINT_SEMANTIC.value: (
        TeachingSupportLevel.SEMANTIC_HINT.value
    ),
    PresentationPhase.HINT_STRUCTURAL.value: (
        TeachingSupportLevel.STRUCTURAL_HINT.value
    ),
    PresentationPhase.HINT_PARTIAL_FORM.value: (
        TeachingSupportLevel.PARTIAL_FORM.value
    ),
}


@dataclass(frozen=True)
class LadderStep:
    """One ladder move: where the moment goes and what gets delivered.

    ``terminalizing`` is the *ladder's* own reading of a move: only a move
    that cannot be followed by any further ladder step is terminalizing.
    Whether the moment actually closes is the next-action decision's
    (elc.teaching.next_action) — a reveal shown on request leaves the
    moment open at FULL_REVEAL (STATE_MACHINES §3
    POST_REVEAL_OPTIONAL_ATTEMPT), and only the §8 hard-cap conversion or
    an explicit closing decision ends the episode."""

    presentation_phase: PresentationPhase
    support_level: TeachingSupportLevel
    text: str | None
    delivery_kind: str  # HINT | REVEAL | EXPLANATION | OPENING | RETRY
    terminalizing: bool = False


def ladder_step(
    *,
    current_phase: str,
    current_support: str,
    hint_ladder: tuple[str, ...],
    reveal_form: str | None,
    delivery_kind: str,
) -> LadderStep:
    """Compute the ladder move for one delivery kind.

    ``hint_ladder`` is the TargetFixture's ordered hint text (semantic →
    structural → partial form). A hint walks to the next rung; when the
    ladder is exhausted the only remaining moves are the reveal and the
    explanation, so an exhausted hint request lands on FULL_REVEAL (there
    is no next rung to show without repeating one).

    The move is always forward: the returned phase/support are never below
    the current ones (the caller still runs
    :func:`ladder_step_refusal` before committing).
    """

    if delivery_kind == "HINT":
        next_index = _next_hint_index(current_phase, hint_ladder)
        if next_index is None:
            return LadderStep(
                presentation_phase=PresentationPhase.FULL_REVEAL,
                support_level=TeachingSupportLevel.FULL_FORM_SHOWN,
                text=reveal_form,
                delivery_kind="REVEAL",
            )
        next_phase = HINT_PHASES[next_index]
        return LadderStep(
            presentation_phase=PresentationPhase(next_phase),
            support_level=TeachingSupportLevel(_HINT_SUPPORT[next_phase]),
            text=hint_ladder[next_index],
            delivery_kind="HINT",
        )
    if delivery_kind == "REVEAL":
        return LadderStep(
            presentation_phase=PresentationPhase.FULL_REVEAL,
            support_level=TeachingSupportLevel.FULL_FORM_SHOWN,
            text=reveal_form,
            delivery_kind="REVEAL",
        )
    if delivery_kind == "EXPLANATION":
        return LadderStep(
            presentation_phase=PresentationPhase.EXPLANATION,
            support_level=TeachingSupportLevel(
                _higher_support(
                    current_support, TeachingSupportLevel.FULL_FORM_SHOWN.value
                )
                if is_post_reveal_attempt(current_phase)
                else current_support
            ),
            text=None,  # the explanation text is the persona's own content
            delivery_kind="EXPLANATION",
        )
    if delivery_kind == "RETRY":
        return LadderStep(
            presentation_phase=PresentationPhase(current_phase),
            support_level=TeachingSupportLevel(current_support),
            text=None,
            delivery_kind="RETRY",
        )
    raise ValueError(f"unknown delivery kind: {delivery_kind}")


def _next_hint_index(current_phase: str, hint_ladder: tuple[str, ...]) -> int | None:
    """The next rung's index in ``hint_ladder``.

    The rung is addressed by the ladder's own ordering: a moment that has
    not hinted yet (INITIAL_PROMPT) starts at rung 0; a moment that already
    showed rung *k* continues at rung *k + 1*. Rungs beyond the fixture's
    ladder do not exist → None (the caller reveals instead).
    """

    if current_phase == PresentationPhase.INITIAL_PROMPT.value:
        next_index = 0
    elif current_phase in HINT_PHASES:
        next_index = HINT_PHASES.index(current_phase) + 1
    else:
        return None
    return next_index if next_index < len(hint_ladder) else None


def _higher_support(left: str, right: str) -> str:
    return left if support_rank(left) >= support_rank(right) else right


def evidence_support_level(
    peak_support: str, attempt_support: str
) -> TeachingSupportLevel:
    """SM §3 backward direction: evidence never claims less support than the
    real exposure of the moment (the peak reached across its deliveries)."""

    return TeachingSupportLevel(_higher_support(peak_support, attempt_support))


def evidence_answer_exposure(
    answer_exposure_state: str, attempt_support: str
) -> AnswerExposureState:
    """The answer-exposure fact recorded with an attempt's evidence.

    A full form already shown keeps the moment at FULL exposure no matter
    what the attempt's recorded state says — the conservative direction
    (§13 "不确定时使用 conservative upper-bound support attribution")."""

    if answer_exposure_state == AnswerExposureState.FULL.value:
        return AnswerExposureState.FULL
    if support_rank(attempt_support) >= support_rank(
        TeachingSupportLevel.FULL_FORM_SHOWN.value
    ):
        return AnswerExposureState.FULL
    return AnswerExposureState(answer_exposure_state)


def is_post_reveal_attempt(phase: str) -> bool:
    """True once the full form has been presented in this moment."""

    return phase in POST_REVEAL_PHASES
