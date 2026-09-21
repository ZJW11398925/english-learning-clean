"""Validated target fixtures for the P3-1A teaching slice (TASK-…17 ⑦).

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
"""

from __future__ import annotations

from elc.platform.types import DomainError, DomainErrorCode, Err, Ok, Result
from elc.teaching.targets import TeachingTargetView

__all__ = [
    "CONTENT_INVALID_PROVIDER_VIEW",
    "UNAVAILABLE_TARGET_PROVIDER",
    "UNKNOWN_TARGET_PROVIDER_VIEW",
    "VALIDATED_TARGET_FIXTURES",
    "FixtureTeachingTargetProvider",
    "provider_over",
]


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
    return TeachingTargetView(
        target_type=target_type,
        target_id=target_id,
        target_status=target_status,
        content_status=content_status,
        target_mode=target_mode,
        learning_intent=learning_intent,
        evidence_modality=evidence_modality,
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
