"""The target-match observation contract (P5-R, pure).

P5-2's chat leg produced one object — ``ResolvedTarget`` — and handed it
straight to the evidence face, so a *match* and an *evidence claim* were the
same thing and the matcher's string certainty was spent as performance
certainty (external review: a quoted, paraphrased, negated or merely
mentioned form could mint a strong Performance Evidence claim). P5-R splits
the two facts apart:

    utterance + supply facts
        → resolve_target            (the matcher: is a form present?)
        → TargetMatchObservation    (this module: where, how, how certain)
        → admitted_for_evidence     (the V1 admission set, rules 1-3)
        → EvidenceClaimView         (elc.learning.silent_claim — admitted only)

The observation is a **contract, not a state object**: it never enters
LearnerState, it carries no claim, and building one decides nothing. A match
that fails admission is *observation-only*: zero claim, zero LearnerState
change, the chat turn entirely unaffected.

``match_certainty`` is the certainty of the **matcher** (the string occurred —
a deterministic fact about the turn), and it is deliberately *not* the
certainty of the **performance** (did the learner produce the target?). That
second question is a judgement, so the admitted claim carries
``USE_JUDGMENT_CONFIDENCE`` (elc.learning.silent_claim) and never this
number. ``1.0`` stays here, on the matcher, where it is true.

**The V1 admission set** — a match becomes strong evidence only when all five
hold. Rules 1-3 are decided here; rules 4-5 are the caller's existing guards:

1. ``target_type == RESOURCE`` — a CAPABILITY hit from free chat is
   observation-only. Crediting a capability needs a use-validator and the
   capability's own functional definition, neither of which V1 has; a
   lexical token is not evidence about a capability.
2. ``matched_via`` is a **form** class — ``CANONICAL_FORM`` or
   ``ALTERNATIVE_REALIZATION``. ``REQUIRED_SLOTS`` never admits: a slot hit
   is a co-occurrence of tokens, not the occurrence of a form.
3. the match spans the **whole utterance** — casefold, whitespace collapse
   and edge-punctuation strip on both sides, then equality
   (:func:`spans_the_whole_utterance`). Any embedded span, any half sentence,
   any form quoted inside a longer sentence is observation-only: "the phrase
   'X' is in my textbook", "my teacher told me to say 'X'", "don't say 'X'",
   "'X' is what she said" are all turns *about* the form, not turns using it,
   and no string test can tell them apart from use — so the string test only
   counts when there is nothing else in the sentence.
4. the same target has no **open TeachingMoment** — the existing F-2 window
   guard (elc.runtime.controller._observed_target_is_under_teaching),
   unchanged.
5. the supply was readable — the port's existing RA §21 degradation
   (``Err`` → NO_TARGET, the conversation never blocks), unchanged.

Rules 4-5 stay where they are: this module is pure (no IO, no DB, no clock,
no model), so the live caller keeps owning "is a moment open?" and "did the
supply read?".

**V1 deliberately closes (with its revisit condition).**

- *capability-from-chat* — closed until a use-validator and capability
  functional definitions exist; reopening is a new admission rule with its
  own acceptance, not a relaxation of rule 1.
- *slot-only and embedded spans* — closed until an **approved** §8.1 R4
  detection policy with negative fixtures and a measured false-positive rate
  exists (the corpus now carries forty-six structurally testable R4
  policies, but a measured false-positive rate is still owed content work,
  and the slot rule's boundary is declared rather than measured —
  elc.learning.target_resolution's false-positive section).

Not re-exported from ``elc.learning.__init__``: the durable store and the
coordinator import it by full path (the elc.learning.validation precedent),
so this slice leaves the package's public face unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.learning.target_resolution import (
    MatchVia,
    ResolvedTarget,
    located_span,
    normalize_form,
)

__all__ = [
    "ADMITTED_MATCH_CLASSES",
    "EVIDENCE_TARGET_TYPE",
    "MATCH_CERTAINTY",
    "TargetMatchObservation",
    "admitted_for_evidence",
    "observe_target_match",
    "spans_the_whole_utterance",
]

#: The certainty of the **matcher** (demoted to observation in P5-R): the form
#: occurred in the turn, and that is deterministic — no model, no doubt. This
#: is not a claim's ``evaluator_confidence``, which is a judgement about the
#: learner's performance (elc.learning.silent_claim.USE_JUDGMENT_CONFIDENCE).
MATCH_CERTAINTY = 1.0

#: The ``matched_via`` classes admission rule 2 admits (form classes only).
ADMITTED_MATCH_CLASSES = (
    MatchVia.CANONICAL_FORM,
    MatchVia.ALTERNATIVE_REALIZATION,
)

#: The one ``target_type`` admission rule 1 admits.
EVIDENCE_TARGET_TYPE = "RESOURCE"


@dataclass(frozen=True)
class TargetMatchObservation:
    """One extracted target match as the caller observed it (P5-R).

    ``matched_span`` is the span of the matched form in the utterance's own
    comparison coordinates (casefold + whitespace collapse; the
    ``elc.learning.target_resolution.located_span`` contract) — ``""`` when
    the form does not occur as a bounded span, which is how a fabricated or
    stale resolution document fails admission instead of being trusted.
    ``match_certainty`` is the matcher's certainty; see the module docstring
    for why it is not a claim confidence.
    """

    turn_id: str
    target_type: str
    target_id: str
    matched_via: MatchVia
    matched_form: str
    matched_span: str
    match_certainty: float = MATCH_CERTAINTY


def observe_target_match(
    *,
    turn_id: str,
    utterance: str,
    resolution: ResolvedTarget,
) -> TargetMatchObservation:
    """Turn one resolution into its observation (pure, deterministic).

    The only derived field is the span; everything else is copied verbatim,
    so the observation is exactly the resolution plus *where* it matched.
    """

    return TargetMatchObservation(
        turn_id=turn_id,
        target_type=resolution.target_type,
        target_id=resolution.target_id,
        matched_via=resolution.matched_via,
        matched_form=resolution.matched_form,
        matched_span=located_span(utterance, resolution),
        match_certainty=MATCH_CERTAINTY,
    )


def spans_the_whole_utterance(
    observation: TargetMatchObservation, utterance: str
) -> bool:
    """Admission rule 3: is the matched span the whole utterance?

    Both sides go through the one normalization the resolver already uses
    (casefold + whitespace collapse + edge-punctuation strip,
    ``normalize_form``), so ``"I think it is going to rain!!"`` and
    ``"i think it is going to rain"`` both span the whole utterance, while
    ``"Well, I think it is going to rain tomorrow."`` does not — the form
    sits inside a longer sentence and *that* sentence, not the form, is what
    the learner produced. An empty span never spans anything.
    """

    if not observation.matched_span:
        return False
    return normalize_form(observation.matched_span) == normalize_form(utterance)


def admitted_for_evidence(
    observation: TargetMatchObservation, utterance: str
) -> bool:
    """The V1 admission set's pure half (rules 1-3; see the module docstring).

    ``True`` means "this observation may be converted into an
    ``EvidenceClaimView``"; the caller must still hold rules 4 (no open
    TeachingMoment for the same target) and 5 (the supply read succeeded),
    which need the teaching port and the supply port and therefore cannot
    live in a pure module.
    """

    if observation.target_type != EVIDENCE_TARGET_TYPE:
        return False
    if observation.matched_via not in ADMITTED_MATCH_CLASSES:
        return False
    return spans_the_whole_utterance(observation, utterance)
