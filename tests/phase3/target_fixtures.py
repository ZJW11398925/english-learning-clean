"""Validated target fixtures for the P3-1A/P3-1B teaching slice
(TASK-…17 ⑦, TASK-…2babb21e.2 ⑤).

IMPLEMENTATION_PLAN §1.5: the first vertical slice needs "少量（约 10–20）
validated targets" — this module is that set for the repo-native tests
(Phase 5 replaces the provider with the real Curriculum/Content runtime
views; the port is elc.teaching.targets.TeachingTargetProvider).

Every fixture is a :class:`TeachingTargetView` with status VALID / content
VALID and a canonical §11 default target_mode + learning_intent, so a Gate
ALLOW and a CP2 open can be driven end to end. The provider is
deterministic: unknown ids resolve to NOT_FOUND (the Gate's deterministic
TARGET_INVALID path), and the hostile variants below model resolver
failure (UNKNOWN → DEGRADED) and content invalidity.

Phase 3 P3-1B adds each target's *teaching content* — the ladder rungs, the
reveal form, the evaluator's answer key (canonical forms / alternative
realizations / required slots) and the capability linkage. The ladder and
evaluator v0 are fixture-driven by design (TASK-…2.2 ④⑤), so this is the
one place the validated content lives until Phase 5's content runtime:

- ``hint_ladder`` — the ordered rungs (semantic → structural → partial
  form); the provider never picks a stage, it reports the target's own
  validated rungs;
- ``canonical_forms`` — the forms the target teaches, word for word;
- ``alternative_realizations`` — other realizations that still count as a
  valid realization of the same capability (§5 ALTERNATIVE_SUCCESS);
- ``required_slots`` — token groups an attempt must cover to be a PARTIAL;
- ``capability_linkage`` — the CAPABILITY a RESOURCE realizes (DATA_MODEL
  §13 REALIZES/SUPPORTS), which is what lets Learning credit an
  alternative realization onto the capability instead of the resource.
"""

from __future__ import annotations

from elc.platform.types import DomainError, DomainErrorCode, Err, Ok, Result
from elc.teaching.targets import TeachingTargetView

__all__ = [
    "CONTENT_INVALID_PROVIDER_VIEW",
    "TEACHING_CONTENT",
    "UNAVAILABLE_TARGET_PROVIDER",
    "UNKNOWN_TARGET_PROVIDER_VIEW",
    "VALIDATED_TARGET_FIXTURES",
    "FixtureTeachingTargetProvider",
    "provider_over",
]


#: The validated teaching content of each target: hint rungs (semantic →
#: structural → partial form), the revealed form, the answer key and the
#: capability linkage. Keyed by target id so the fixture set and its content
#: stay one readable table.
TEACHING_CONTENT: dict[str, dict[str, object]] = {
    "res-hedge-i-think": {
        "hint_ladder": (
            "Hedge the claim so it does not sound like a fact.",
            "Use a short phrase before the statement, not after it.",
            "Start with the two words: I ___ it is going to rain.",
        ),
        "reveal_form": "I think it is going to rain.",
        "canonical_forms": ("I think it is going to rain.",),
        "alternative_realizations": ("It might rain.", "I'd say it will rain."),
        "required_slots": (("rain",), ("think", "guess", "reckon")),
        "capability_linkage": "cap-eval-hedged-opinion",
    },
    "res-softener-kind-of": {
        "hint_ladder": (
            "Soften the statement: it should not sound absolute.",
            "Add a softener directly before the adjective.",
            "Fill in: The ending is ___ sad.",
        ),
        "reveal_form": "The ending is kind of sad.",
        "canonical_forms": ("The ending is kind of sad.",),
        "alternative_realizations": ("The ending is a bit sad.",),
        "required_slots": (("ending",), ("kind", "sort", "bit")),
        "capability_linkage": "cap-stance-soften-disagreement",
    },
    "res-colloc-pay-attention-to": {
        "hint_ladder": (
            "Name the collocation for focusing on something.",
            "The verb is not 'take' or 'make' here.",
            "Fill in: You should ___ attention to the stress.",
        ),
        "reveal_form": "You should pay attention to the stress.",
        "canonical_forms": ("You should pay attention to the stress.",),
        "alternative_realizations": (),
        "required_slots": (("attention",), ("pay",)),
        "capability_linkage": "cap-ref-ask-clarification",
    },
    "res-frame-id-like-to": {
        "hint_ladder": (
            "Frame a polite request, not a bare imperative.",
            "The frame takes a contracted subject + a verb.",
            "Fill in: I___ ___ to join the group.",
        ),
        "reveal_form": "I'd like to join the group.",
        "canonical_forms": ("I'd like to join the group.",),
        "alternative_realizations": ("I would like to join the group.",),
        "required_slots": (("join",), ("like",)),
        "capability_linkage": "cap-interact-backchannel",
    },
    "res-discourse-by-the-way": {
        "hint_ladder": (
            "Signal that you are adding a side remark.",
            "It is a three-word discourse marker.",
            "Fill in: ___ ___ ___, did you book the room?",
        ),
        "reveal_form": "By the way, did you book the room?",
        "canonical_forms": ("By the way, did you book the room?",),
        "alternative_realizations": ("Incidentally, did you book the room?",),
        "required_slots": (("way",), ("book", "room")),
        "capability_linkage": "cap-disc-topic-shift",
    },
    "res-phrasal-look-forward-to": {
        "hint_ladder": (
            "Use the phrasal verb for anticipating something pleasant.",
            "The particle is not 'for' and not 'at'.",
            "Fill in: I look ___ ___ seeing you.",
        ),
        "reveal_form": "I look forward to seeing you.",
        "canonical_forms": ("I look forward to seeing you.",),
        "alternative_realizations": ("I'm looking forward to seeing you.",),
        "required_slots": (("forward",), ("seeing",)),
        "capability_linkage": "cap-interact-backchannel",
    },
    "res-pragmatic-could-you": {
        "hint_ladder": (
            "Ask for help with a modal, not with 'give me'.",
            "Start with 'Could you' — not 'Can you please'.",
            "Fill in: Could you ___ me the file?",
        ),
        "reveal_form": "Could you send me the file?",
        "canonical_forms": ("Could you send me the file?",),
        "alternative_realizations": ("Would you send me the file?",),
        "required_slots": (("file",), ("could", "would")),
        "capability_linkage": "cap-ref-ask-clarification",
    },
    "res-idiom-break-the-ice": {
        "hint_ladder": (
            "Name the idiom for easing initial awkwardness.",
            "The verb is not 'cut' and not 'open'.",
            "Fill in: He told a joke to ___ the ice.",
        ),
        "reveal_form": "He told a joke to break the ice.",
        "canonical_forms": ("He told a joke to break the ice.",),
        "alternative_realizations": (),
        "required_slots": (("ice",), ("break",)),
        "capability_linkage": "cap-disc-topic-shift",
    },
    "res-colloc-make-a-decision": {
        "hint_ladder": (
            "Name the collocation for choosing a course of action.",
            "The verb is not 'do' and not 'take'.",
            "Fill in: We have to ___ a decision today.",
        ),
        "reveal_form": "We have to make a decision today.",
        "canonical_forms": ("We have to make a decision today.",),
        "alternative_realizations": (
            "We have to take a decision today.",
        ),
        "required_slots": (("decision",), ("make", "take")),
        "capability_linkage": "cap-eval-hedged-opinion",
    },
    "cap-ref-ask-clarification": {
        "hint_ladder": (
            "Ask the speaker to clarify without repeating them badly.",
            "Use a wh-question frame with 'mean'.",
            "Fill in: What do you ___ by that?",
        ),
        "reveal_form": "What do you mean by that?",
        "canonical_forms": ("What do you mean by that?",),
        "alternative_realizations": ("Sorry, what does that mean?",),
        "required_slots": (("mean",),),
        "capability_linkage": None,
    },
    "cap-stance-soften-disagreement": {
        "hint_ladder": (
            "Soften the disagreement so it stays polite.",
            "Start with 'I see your point, but ...'.",
            "Fill in: I see your ___, but I'm not sure.",
        ),
        "reveal_form": "I see your point, but I'm not sure.",
        "canonical_forms": ("I see your point, but I'm not sure.",),
        "alternative_realizations": (
            "I take your point, but I'm not sure.",
        ),
        "required_slots": (("point",), ("sure",)),
        "capability_linkage": None,
    },
    "cap-disc-topic-shift": {
        "hint_ladder": (
            "Move the conversation to a new topic explicitly.",
            "Use a short signpost, then the new topic.",
            "Fill in: Speaking of which, ___ the meeting?",
        ),
        "reveal_form": "Speaking of which, how was the meeting?",
        "canonical_forms": ("Speaking of which, how was the meeting?",),
        "alternative_realizations": ("On that note, how was the meeting?",),
        "required_slots": (("meeting",),),
        "capability_linkage": None,
    },
    "cap-eval-hedged-opinion": {
        "hint_ladder": (
            "Give an opinion with a hedge, not as a fact.",
            "Hedge first, then state the opinion.",
            "Fill in: I think it ___ be too late.",
        ),
        "reveal_form": "I think it might be too late.",
        "canonical_forms": ("I think it might be too late.",),
        "alternative_realizations": ("It could be too late, I think.",),
        "required_slots": (("late",), ("think", "might", "could")),
        "capability_linkage": None,
    },
    "cap-interact-backchannel": {
        "hint_ladder": (
            "Show you are listening without taking the turn.",
            "One short phrase is enough.",
            "Fill in: ___, I see.",
        ),
        "reveal_form": "Right, I see.",
        "canonical_forms": ("Right, I see.",),
        "alternative_realizations": ("Uh-huh, I see.",),
        "required_slots": (("see",),),
        "capability_linkage": None,
    },
}


def _strings(content: dict[str, object], key: str) -> tuple[str, ...]:
    """One string-tuple field of a content entry (absent → empty)."""

    value = content.get(key, ())
    if not isinstance(value, tuple):
        return ()
    return tuple(str(item) for item in value)


def _slot_groups(content: dict[str, object]) -> tuple[tuple[str, ...], ...]:
    """The ``required_slots`` token groups of a content entry."""

    value = content.get("required_slots", ())
    if not isinstance(value, tuple):
        return ()
    return tuple(
        tuple(str(token) for token in group)
        for group in value
        if isinstance(group, tuple)
    )


def _optional_str(content: dict[str, object], key: str) -> str | None:
    value = content.get(key)
    return None if value is None else str(value)


def _view(
    target_type: str,
    target_id: str,
    target_mode: str,
    learning_intent: str,
    *,
    target_status: str = "VALID",
    content_status: str = "VALID",
    evidence_modality: str = "TEXT_PRODUCTION",
) -> TeachingTargetView:
    content = TEACHING_CONTENT.get(target_id)
    return TeachingTargetView(
        target_type=target_type,
        target_id=target_id,
        target_status=target_status,
        content_status=content_status,
        target_mode=target_mode,
        learning_intent=learning_intent,
        evidence_modality=evidence_modality,
        hint_ladder=() if content is None else _strings(content, "hint_ladder"),
        reveal_form=(
            None if content is None else _optional_str(content, "reveal_form")
        ),
        canonical_forms=(
            () if content is None else _strings(content, "canonical_forms")
        ),
        alternative_realizations=(
            ()
            if content is None
            else _strings(content, "alternative_realizations")
        ),
        required_slots=() if content is None else _slot_groups(content),
        capability_linkage=(
            None if content is None else _optional_str(content, "capability_linkage")
        ),
    )


#: The validated target set (14 fixtures, inside the 10–20 window of
#: IMPLEMENTATION_PLAN §1.5). Resource fixtures carry canonical §11
#: RESOURCE_PRACTICE/REVIEW modes; capability fixtures carry
#: CAPABILITY_PRACTICE.
VALIDATED_TARGET_FIXTURES: tuple[TeachingTargetView, ...] = (
    _view("RESOURCE", "res-hedge-i-think", "RESOURCE_PRACTICE", "ESTABLISH"),
    _view("RESOURCE", "res-softener-kind-of", "RESOURCE_PRACTICE", "DEVELOP"),
    _view(
        "RESOURCE",
        "res-colloc-pay-attention-to",
        "RESOURCE_PRACTICE",
        "ESTABLISH",
    ),
    _view("RESOURCE", "res-frame-id-like-to", "RESOURCE_PRACTICE", "DEVELOP"),
    _view(
        "RESOURCE",
        "res-discourse-by-the-way",
        "RESOURCE_PRACTICE",
        "ESTABLISH",
    ),
    _view(
        "RESOURCE",
        "res-phrasal-look-forward-to",
        "RESOURCE_PRACTICE",
        "ESTABLISH",
    ),
    _view(
        "RESOURCE",
        "res-pragmatic-could-you",
        "RESOURCE_PRACTICE",
        "CONSOLIDATE",
    ),
    _view(
        "RESOURCE",
        "res-idiom-break-the-ice",
        "RESOURCE_PRACTICE",
        "ESTABLISH",
    ),
    _view(
        "RESOURCE",
        "res-colloc-make-a-decision",
        "REVIEW",
        "CONSOLIDATE",
    ),
    _view(
        "CAPABILITY",
        "cap-ref-ask-clarification",
        "CAPABILITY_PRACTICE",
        "DEVELOP",
    ),
    _view(
        "CAPABILITY",
        "cap-stance-soften-disagreement",
        "CAPABILITY_PRACTICE",
        "DEVELOP",
    ),
    _view(
        "CAPABILITY",
        "cap-disc-topic-shift",
        "CAPABILITY_PRACTICE",
        "ESTABLISH",
    ),
    _view(
        "CAPABILITY",
        "cap-eval-hedged-opinion",
        "CAPABILITY_PRACTICE",
        "DEVELOP",
    ),
    _view(
        "CAPABILITY",
        "cap-interact-backchannel",
        "CAPABILITY_PRACTICE",
        "ESTABLISH",
    ),
)

#: Hostile fixture: the resolver answers, but cannot judge validity.
UNKNOWN_TARGET_PROVIDER_VIEW = _view(
    "RESOURCE",
    "res-hedge-i-think",
    "RESOURCE_PRACTICE",
    "ESTABLISH",
    target_status="UNKNOWN",
    content_status="UNKNOWN",
)

#: Hostile fixture: the target resolves, its content is known-invalid.
CONTENT_INVALID_PROVIDER_VIEW = _view(
    "RESOURCE",
    "res-hedge-i-think",
    "RESOURCE_PRACTICE",
    "ESTABLISH",
    content_status="INVALID",
)


class FixtureTeachingTargetProvider:
    """Deterministic provider over a fixed view set.

    Unknown ``(target_type, target_id)`` → NOT_FOUND (deterministic: the
    Gate denies TARGET_INVALID). Wrap with :func:`provider_over` for the
    degenerate single-view variants.
    """

    def __init__(
        self, views: tuple[TeachingTargetView, ...] = VALIDATED_TARGET_FIXTURES
    ) -> None:
        self._views = {f"{view.target_type}/{view.target_id}": view for view in views}

    def resolve(
        self, target_type: str, target_id: str
    ) -> Result[TeachingTargetView]:
        view = self._views.get(f"{target_type}/{target_id}")
        if view is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=f"no validated target {target_type}/{target_id}",
                )
            )
        return Ok(view)


class UnavailableTargetProvider:
    """Resolver-down stand-in: every resolve fails with
    DEPENDENCY_UNAVAILABLE → the Gate sees UNKNOWN validity → DEGRADED."""

    def resolve(
        self, target_type: str, target_id: str
    ) -> Result[TeachingTargetView]:
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message=f"target resolver unavailable for {target_type}/{target_id}",
            )
        )


#: The resolver-down instance (stateless; shared by the phase-3 tests).
UNAVAILABLE_TARGET_PROVIDER = UnavailableTargetProvider()


def provider_over(view: TeachingTargetView) -> FixtureTeachingTargetProvider:
    """A provider serving exactly one view (any id resolves to it)."""

    class _SingleViewProvider(FixtureTeachingTargetProvider):
        def resolve(
            self, target_type: str, target_id: str
        ) -> Result[TeachingTargetView]:
            del target_type, target_id
            return Ok(view)

    return _SingleViewProvider((view,))
