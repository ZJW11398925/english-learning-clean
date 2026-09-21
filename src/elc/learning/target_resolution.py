"""Deterministic target resolution for the natural-conversation leg (P5-2).

docs/PRODUCT_CONTRACT.md §2.4 ("`NO_TARGET` 是合法且常见结果") and P-INV-009
("自然对话本身是正常产品状态") mean the chat leg must be able to observe a
target — silently, without a TeachingMoment — when the learner uses one of
its forms, and must answer NO_TARGET the rest of the time. This module is the
observation half: a pure function from (utterance, supply facts) to

    ResolvedTarget(target_type, target_id, matched_form, matched_via)

or :data:`NO_TARGET`.

**前置裁决 (P5-2, inherited from the slice's task book).** The §8.1 default
readiness threshold (docs/PRODUCT_CONTRACT.md §8.1: R0/R1 targets do not
enter the automatic Teaching Frontier) constrains the **Planner automatic
teaching face**. It does not constrain the **evidence-forming face**: this
slice may form silent evidence on an R1 target (the whole corpus stops at R1,
so no target would be reachable otherwise), and it must not — and does not —
open any automatic teaching choice (that stays Phase 8). Nothing in this
module reads or judges readiness.

**Extraction rules, in the fixed priority order** (canonical form >
alternative realization > required slots):

1. ``CANONICAL_FORM`` — a §24.5 PRIMARY_TARGET form occurs in the normalized
   utterance on token boundaries;
2. ``ALTERNATIVE_REALIZATION`` — the same, over the §24.5 SUPPORTING forms;
3. ``REQUIRED_SLOTS`` — every slot group is covered by at least one of its
   own tokens, present as a whole token in the utterance, **and the slot key
   must be discriminating** (:data:`SLOTS_MIN_GROUPS`): a key with a single
   one-token group is a bare word check with no false-positive lower bound
   and never drives a match — see the false-positive boundary below.

Normalization is the in-repo precedent (``elc.teaching.evaluator.
normalize_answer``; ``elc.relationship.validation.normalize_memory_content``):
casefold + whitespace collapse + edge-punctuation strip. The one deliberate
difference is the unit of comparison — the evaluator compares a whole attempt
answer against a whole form, while a natural chat turn is free text in which
the target form is at most a span — so rules 1/2 ask "does the normalized
form occur as a bounded span", not "are the two equal". Internal punctuation
is never loosened: a form that does not literally occur is not a match.

**False-positive boundary of the slot rule (declared, and the first input to
the §8.1 R4 detection-policy / false-positive-boundary ladder).** A slot key's
discriminating power is a property of its shape, not of the utterance:

- a single one-token group (``[["see"]]``) matches every sentence that
  contains that word — any "I want to see that movie." would be credited as
  spontaneous production of the target. The rule cannot bound that, so such
  keys are **never** matched through the slot path (the canonical form or an
  alternative realization still can, and still outranks it);
- a key with ≥2 groups, or with at least one multi-token group, needs a
  co-occurrence that free chat produces far more rarely — it stays the
  lowest-priority class, which is why rules 1/2 always win first.

Determinism: no IO, no model, no clock, no RNG; the answer depends only on
(utterance, facts). Within the highest matching class the winner is the
longest matched form, ties broken by the lexicographically smallest target
id; the slot class has no form length and picks the smallest target id. A
miss is :data:`NO_TARGET` with zero side effects.

**What this module deliberately is not.** 抽取式第一切片；模型辅助解析属另版
（需版本号 + 单独验收）. No fuzzy/lemmatized matching, no context-aware
disambiguation, no model inference, no "guess the intended word": a resolver
that guesses is a different producer, with a version id and its own
acceptance, and does not live here.

Supply facts (:class:`TargetSupplyFacts`) are the caller's input — this
module never reads content.db, and it never decides *supply*: an entity that
may not enter supply simply never reaches this function
(elc.learning.silent_evidence applies the §24.11 filter at the read face). A
fact whose ``target_type`` is outside the canonical pair (docs/DOMAIN_MODEL.md
§6 RESOURCE / CAPABILITY) is ignored, never matched — the kind filter is the
resolver's own guard, tested here rather than assumed from the read face.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "CANONICAL_TARGET_TYPES",
    "MatchVia",
    "NO_TARGET",
    "ResolvedTarget",
    "SLOTS_MIN_GROUPS",
    "TargetResolution",
    "TargetSupplyFacts",
    "normalize_form",
    "resolution_document",
    "resolution_from_document",
    "resolve_target",
    "slots_can_discriminate",
]

#: docs/DOMAIN_MODEL.md §6 — the two claim scopes a resolver may answer with.
#: Same pair as elc.content.types.TARGET_TYPES (the content build's own
#: copy); duplicated here because the resolver judges its *input* facts and
#: may not depend on a supply-domain module for a vocabulary check.
CANONICAL_TARGET_TYPES = ("RESOURCE", "CAPABILITY")

#: The discriminator threshold of the slot rule (false-positive boundary):
#: the slot path engages only for a key with at least this many groups — or
#: for a key with at least one multi-token group (see the module docstring's
#: boundary section). One single-token group is a bare word check and never
#: drives a match.
SLOTS_MIN_GROUPS = 2

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = re.compile(r"^[^\w]+|[^\w]+$")
_WORD = re.compile(r"\w+")


class MatchVia(StrEnum):
    """How one resolution was extracted; the fixed priority order is the
    declaration order of this enum (canonical form > alternative realization
    > required slots)."""

    CANONICAL_FORM = "CANONICAL_FORM"
    ALTERNATIVE_REALIZATION = "ALTERNATIVE_REALIZATION"
    REQUIRED_SLOTS = "REQUIRED_SLOTS"


@dataclass(frozen=True)
class TargetSupplyFacts:
    """One supply-eligible target as the resolver sees it.

    ``canonical_forms`` / ``alternative_realizations`` / ``required_slots``
    are the §24.5 payload of the entity (``content_example`` rows and
    ``content_slot`` groups), already filtered by the caller: a fact reaching
    the resolver is an entity that may enter supply. Empty tuples are legal
    and simply make the corresponding rule unable to match — never a failure.
    """

    target_type: str
    target_id: str
    canonical_forms: tuple[str, ...] = ()
    alternative_realizations: tuple[str, ...] = ()
    required_slots: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class ResolvedTarget:
    """One extracted target observation.

    ``matched_form`` is the authored form for form rules and the covered
    token render for the slot rule (see :func:`resolve_target`);
    ``matched_via`` names which rule produced it, so the provenance written
    by the evidence face can say *why* this turn counts as evidence.
    """

    target_type: str
    target_id: str
    matched_form: str
    matched_via: MatchVia


#: The resolver's miss answer — a legal, common product state (§2.4), not an
#: error channel. Zero side effects: nothing was committed, nothing is owed.
NO_TARGET: None = None

#: What one resolution attempt answers.
TargetResolution = ResolvedTarget | None


#: The document keys of one resolution inside a durable proposal payload.
#: One shape, written here and read by :func:`resolution_from_document`, so
#: the producer and every parser cannot drift.
RESOLUTION_DOCUMENT_KEYS = (
    "target_type",
    "target_id",
    "matched_form",
    "matched_via",
)


def resolution_document(resolution: ResolvedTarget) -> dict[str, str]:
    """One resolution as plain JSON data (enum words, never enum objects)."""

    return {
        "target_type": resolution.target_type,
        "target_id": resolution.target_id,
        "matched_form": resolution.matched_form,
        "matched_via": resolution.matched_via.value,
    }


def resolution_from_document(document: Mapping[str, object]) -> ResolvedTarget:
    """Rebuild one resolution from its payload document (the exact inverse
    of :func:`resolution_document`).

    An unknown word or a missing key raises ``ValueError`` (the caller
    surfaces it as a refusal — never a silent default), and a kind outside
    :data:`CANONICAL_TARGET_TYPES` is rejected here too: a durable document
    is data, and data this module reads back must still satisfy the same
    guard the resolver applies to its live input.
    """

    target_type = str(document["target_type"])
    if target_type not in CANONICAL_TARGET_TYPES:
        raise ValueError(f"unknown target_type in resolution: {target_type!r}")
    matched_via = MatchVia(str(document["matched_via"]))
    target_id = str(document["target_id"])
    if not target_id:
        raise ValueError("resolution document carries an empty target_id")
    return ResolvedTarget(
        target_type=target_type,
        target_id=target_id,
        matched_form=str(document["matched_form"]),
        matched_via=matched_via,
    )


def normalize_form(text: str) -> str:
    """The comparison form: casefolded, whitespace-collapsed, edge
    punctuation stripped (the attempt evaluator's ``normalize_answer`` is the
    in-repo precedent). Deterministic and idempotent — the resolver
    normalizes its own input, so a caller never has to."""

    collapsed = _WHITESPACE.sub(" ", text).strip()
    stripped = _EDGE_PUNCTUATION.sub("", collapsed)
    return stripped.casefold()


def _normalize_utterance(text: str) -> str:
    """The utterance side of a form search: casefold + whitespace collapse.

    Edge punctuation is deliberately *not* stripped here — the search scans
    for a bounded occurrence inside the text, and stripping the utterance's
    edges could not change whether an internal occurrence exists.
    """

    return _WHITESPACE.sub(" ", text).strip().casefold()


def _is_word_char(character: str) -> bool:
    return character.isalnum() or character == "_"


def _bounded_occurrence(text: str, core: str) -> bool:
    """Does ``core`` occur in ``text`` as a whole-word span?

    The span's neighbours must not be word characters, which is what keeps
    ``rain`` from matching inside ``rainy`` while still letting a form sit in
    the middle of a longer sentence ("well, i think it is going to rain
    today"). ``core`` is already normalized and has no edge punctuation, so
    the authored form's trailing period neither blocks nor is required.
    """

    start = 0
    while True:
        index = text.find(core, start)
        if index < 0:
            return False
        end = index + len(core)
        left_ok = index == 0 or not _is_word_char(text[index - 1])
        right_ok = end == len(text) or not _is_word_char(text[end])
        if left_ok and right_ok:
            return True
        start = index + 1


def resolve_target(
    utterance: str, facts: tuple[TargetSupplyFacts, ...]
) -> TargetResolution:
    """Resolve one utterance against the supply facts (see module docstring).

    Returns the single best :class:`ResolvedTarget`, or :data:`NO_TARGET` —
    an empty/blank utterance never matches, and neither does a fact whose
    ``target_type`` is outside :data:`CANONICAL_TARGET_TYPES`.
    """

    text = _normalize_utterance(utterance)
    if not text:
        return NO_TARGET
    for via in (MatchVia.CANONICAL_FORM, MatchVia.ALTERNATIVE_REALIZATION):
        resolved = _best_form_match(text, facts, via)
        if resolved is not None:
            return resolved
    return _best_slot_match(text, facts)


def _forms_for(fact: TargetSupplyFacts, via: MatchVia) -> tuple[str, ...]:
    if via is MatchVia.CANONICAL_FORM:
        return fact.canonical_forms
    return fact.alternative_realizations


def _best_form_match(
    text: str, facts: tuple[TargetSupplyFacts, ...], via: MatchVia
) -> TargetResolution:
    """The longest matched form of one class; ties by smallest target id."""

    best: ResolvedTarget | None = None
    best_length = -1
    for fact in facts:
        if fact.target_type not in CANONICAL_TARGET_TYPES:
            continue
        for form in _forms_for(fact, via):
            core = normalize_form(form)
            if not core or not _bounded_occurrence(text, core):
                continue
            better = (
                best is None
                or len(core) > best_length
                or (len(core) == best_length and fact.target_id < best.target_id)
            )
            if better:
                best = ResolvedTarget(
                    target_type=fact.target_type,
                    target_id=fact.target_id,
                    matched_form=form,
                    matched_via=via,
                )
                best_length = len(core)
    return best


def slots_can_discriminate(facts: TargetSupplyFacts) -> bool:
    """Does this slot key have any false-positive lower bound at all?

    ``≥ SLOTS_MIN_GROUPS`` groups, or at least one multi-token group, means a
    co-occurrence is required; a single one-token group means the key is just
    that word, and free chat is full of that word. The second condition is
    what keeps a one-group alternative set ("I ___ it" style keys) usable
    when its members are real alternatives rather than a bare token.

    Public because the boundary is part of the resolver's contract: the
    false-positive face of a slot key is a property a caller (or a readiness
    assessment) may ask about without resolving anything.
    """

    if len(facts.required_slots) >= SLOTS_MIN_GROUPS:
        return True
    return any(len(group) >= 2 for group in facts.required_slots)


def _best_slot_match(
    text: str, facts: tuple[TargetSupplyFacts, ...]
) -> TargetResolution:
    """Every slot group covered by a whole token; smallest target id wins.

    Only a discriminating key can match (see the module docstring's
    false-positive boundary): a single one-token group is a bare word check
    and never drives a resolution. ``matched_form`` is the covered token
    render: one token per slot group, in authored group order, each the first
    member of the group that occurs in the utterance. There is no single
    authored form for a slot match — the render is the deterministic record
    of *which* tokens did the covering.
    """

    tokens = frozenset(_WORD.findall(text))
    best: TargetSupplyFacts | None = None
    best_covered: tuple[str, ...] = ()
    for fact in facts:
        if fact.target_type not in CANONICAL_TARGET_TYPES:
            continue
        if not fact.required_slots:
            continue
        if not slots_can_discriminate(fact):
            continue
        covered: list[str] = []
        matched = True
        for group in fact.required_slots:
            hit: str | None = None
            for token in group:
                normalized_token = normalize_form(token)
                if normalized_token and normalized_token in tokens:
                    hit = normalized_token
                    break
            if hit is None:
                matched = False
                break
            covered.append(hit)
        if not matched:
            continue
        if best is None or fact.target_id < best.target_id:
            best = fact
            best_covered = tuple(covered)
    if best is None:
        return NO_TARGET
    return ResolvedTarget(
        target_type=best.target_type,
        target_id=best.target_id,
        matched_form=" ".join(best_covered),
        matched_via=MatchVia.REQUIRED_SLOTS,
    )
