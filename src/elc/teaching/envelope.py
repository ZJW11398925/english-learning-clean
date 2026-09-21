"""TeachingResponseEnvelope — the user's teaching reply (Phase 3 P3-1B).

Authority: docs/STATE_MACHINES.md §4 (the envelope is "不是互斥单枚举": an
attempt plus a control intent plus optional requests), docs/DATA_MODEL.md
§16 (the record's field set) and docs/RUNTIME_ARCHITECTURE.md §5 (the
active-teaching turn pipeline that consumes it).

The envelope is an *analysis result*, not natural language: exactly like
the ``TEACHING_REQUEST`` command turn (elc.teaching.request), the teaching
meaning travels through a typed payload. In Local V1 there is no NLU
authority over the reply, so the envelope is either

- carried as the canonical ``TEACHING_RESPONSE`` JSON payload of the turn
  (a typed command turn — :func:`teaching_response_payload` /
  :func:`parse_teaching_response_payload`), or
- assembled by the caller as a :class:`TeachingResponseEnvelope` value.

The five-step processing order (:data:`ENVELOPE_STEPS`) is canonical and
pinned: parse control intent → detect optional attempt → evaluate + durable
record + evidence commit/proposal → apply control intent → next action /
close / replan. This module owns steps 1-2 (parse + the shape rules of
"what an envelope may claim"); the orchestrator executes steps 3-5 through
the Teaching / Learning authority faces.

Two §4 shape rules are enforced here, before anything durable happens
(acceptance groups ② and ④):

- ``attempt_present`` is a fact about the *reply*, not a default: it is
  true exactly when an attempt payload is attached. A control-only reply
  never fabricates an attempt.
- ``SKIP`` / ``REJECT_TARGET`` / ``CHANGE_TOPIC`` are control-only
  intents: they mean the user did not attempt anything, so an envelope
  carrying one of them with ``attempt_present=True`` is refused
  (:data:`ATTEMPTLESS_CONTROL_INTENTS`). In particular the orchestrator
  must NOT invent an ``ABSTAIN`` attempt for a skip (an ABSTAIN evaluation
  is reserved for "an attempt happened and could not be judged").

``interpretation_confidence`` is the envelope's own confidence in the
parse (Data_MODEL §16); it travels into the evaluation confidence of a
non-attempt control decision but never into evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import DomainError, DomainErrorCode

__all__ = [
    "ATTEMPTLESS_CONTROL_INTENTS",
    "CONTROL_INTENTS",
    "ENVELOPE_STEPS",
    "TEACHING_RESPONSE_TYPE",
    "AttemptPayload",
    "EnvelopeStep",
    "TeachingControlIntent",
    "TeachingResponseEnvelope",
    "envelope_refusal",
    "parse_teaching_response_payload",
    "teaching_response_payload",
]

#: Payload discriminator of the canonical teaching-reply JSON.
TEACHING_RESPONSE_TYPE = "TEACHING_RESPONSE"


class TeachingControlIntent(StrEnum):
    """docs/STATE_MACHINES.md §4 ``control_intent``, word for word (11)."""

    CONTINUE = "CONTINUE"
    ASK_HINT = "ASK_HINT"
    ASK_ANSWER = "ASK_ANSWER"
    ASK_EXPLANATION = "ASK_EXPLANATION"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    SKIP = "SKIP"
    REJECT_TARGET = "REJECT_TARGET"
    CHANGE_TOPIC = "CHANGE_TOPIC"
    SWITCH_TARGET = "SWITCH_TARGET"
    META_DISCUSSION = "META_DISCUSSION"
    NONE = "NONE"


CONTROL_INTENTS = tuple(item.value for item in TeachingControlIntent)

#: The three control intents that are *control-only by definition*: the
#: user is leaving / refusing / changing the teaching focus, so no attempt
#: was made. An envelope claiming otherwise is a contract error (refused
#: before any durable write), and the orchestrator never manufactures an
#: ABSTAIN attempt for them.
ATTEMPTLESS_CONTROL_INTENTS = frozenset(
    {
        TeachingControlIntent.SKIP.value,
        TeachingControlIntent.REJECT_TARGET.value,
        TeachingControlIntent.CHANGE_TOPIC.value,
    }
)


class EnvelopeStep(StrEnum):
    """docs/STATE_MACHINES.md §4 processing order (five steps, pinned)."""

    PARSE_CONTROL_INTENT = "PARSE_CONTROL_INTENT"
    DETECT_ATTEMPT = "DETECT_ATTEMPT"
    EVALUATE_ATTEMPT = "EVALUATE_ATTEMPT"
    APPLY_CONTROL_INTENT = "APPLY_CONTROL_INTENT"
    NEXT_ACTION = "NEXT_ACTION"


#: The canonical §4 order, as a tuple — the orchestrator walks it in
#: exactly this order and the repo-native test pins it against the doc.
ENVELOPE_STEPS = tuple(item.value for item in EnvelopeStep)


@dataclass(frozen=True)
class AttemptPayload:
    """The optional attempt's payload (docs/DATA_MODEL.md §16
    ``attempt_payload?``).

    ``text`` is what the learner produced — already normalized by whoever
    parsed the reply (the evaluator normalizes again, idempotently);
    ``source`` names the elicitation fact so a trace can tell a typed
    answer from a free-form one.
    """

    text: str
    source: str = "USER_REPLY"


@dataclass(frozen=True)
class TeachingResponseEnvelope:
    """docs/DATA_MODEL.md §16 / STATE_MACHINES §4 envelope.

    Defaults describe the minimal legal reply: a bare continuation with no
    attempt. ``interpretation_confidence`` defaults to 1.0 for a typed
    payload (nothing was interpreted) — a lexical parser passes its own
    confidence in explicitly.
    """

    control_intent: TeachingControlIntent = TeachingControlIntent.CONTINUE
    attempt_present: bool = False
    attempt: AttemptPayload | None = None
    target_switch_request: str | None = None
    clarification_request: str | None = None
    user_preference_signal: str | None = None
    interpretation_confidence: float = 1.0

    @property
    def is_attemptless_control(self) -> bool:
        return self.control_intent.value in ATTEMPTLESS_CONTROL_INTENTS

    @property
    def is_leaving(self) -> bool:
        """A control intent that ends (or replaces) the current moment:
        SKIP / REJECT_TARGET / CHANGE_TOPIC / SWITCH_TARGET."""

        return self.control_intent.value in ATTEMPTLESS_CONTROL_INTENTS or (
            self.control_intent is TeachingControlIntent.SWITCH_TARGET
        )


def envelope_refusal(envelope: TeachingResponseEnvelope) -> DomainError | None:
    """The §4 shape rules, as a pure refusal decision (None = accepted).

    Contract errors are not decisions (the Gate's BF-03 §21 posture): a
    caller that violates the envelope contract gets a VALIDATION_FAILED
    before any teaching state is touched.
    """

    if envelope.control_intent.value not in CONTROL_INTENTS:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"control_intent={envelope.control_intent} is outside the"
                " STATE_MACHINES §4 vocabulary"
            ),
        )
    if not 0.0 <= envelope.interpretation_confidence <= 1.0:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "interpretation_confidence must be within [0, 1] (got"
                f" {envelope.interpretation_confidence})"
            ),
        )
    if envelope.attempt_present and envelope.attempt is None:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message="attempt_present=True requires an attempt payload",
        )
    if envelope.attempt is not None and not envelope.attempt_present:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "an attached attempt payload without attempt_present=True"
                " is a contradictory envelope"
            ),
        )
    if envelope.is_attemptless_control and envelope.attempt_present:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"control_intent={envelope.control_intent.value} is"
                " control-only: it carries no attempt (STATE_MACHINES §4)"
            ),
        )
    if (
        envelope.control_intent is TeachingControlIntent.SWITCH_TARGET
        and not envelope.target_switch_request
    ):
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "SWITCH_TARGET requires the requested target"
                " (target_switch_request)"
            ),
        )
    return None


def teaching_response_payload(envelope: TeachingResponseEnvelope) -> str:
    """Canonical JSON of a teaching reply (deterministic: sorted keys,
    fixed separators, absent optional fields omitted) — the typed-payload
    form an ``InputEnvelope.raw_payload`` can carry.

    ``interpretation_confidence`` is serialized as a JSON *number* (review
    F6): it is a confidence value, and a payload that said
    ``"interpretation_confidence": "1.0"`` would describe a string. The
    canonical form stays byte-deterministic — ``json.dumps`` renders the
    same float identically — and round-trips through
    :func:`parse_teaching_response_payload` exactly.
    """

    payload: dict[str, object] = {
        "type": TEACHING_RESPONSE_TYPE,
        "control_intent": envelope.control_intent.value,
        "attempt_present": envelope.attempt_present,
    }
    if envelope.attempt is not None:
        payload["attempt_text"] = envelope.attempt.text
    if envelope.target_switch_request is not None:
        payload["target_switch_request"] = envelope.target_switch_request
    if envelope.clarification_request is not None:
        payload["clarification_request"] = envelope.clarification_request
    if envelope.user_preference_signal is not None:
        payload["user_preference_signal"] = envelope.user_preference_signal
    payload["interpretation_confidence"] = float(
        envelope.interpretation_confidence
    )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def parse_teaching_response_payload(
    payload: str,
) -> TeachingResponseEnvelope:
    """Parse + shape-check a canonical TEACHING_RESPONSE payload.

    Raises ``ValueError`` on a payload that is not a teaching reply (the
    ``parse_teaching_request_payload`` posture). The §4 shape rules are
    NOT applied here — the caller runs :func:`envelope_refusal` so a
    malformed envelope is refused as a domain contract error rather than a
    parse error.

    ``interpretation_confidence`` is read as a JSON number (the canonical
    form the writer emits) and tolerates a numeric string, so a payload
    written by an older caller still parses; anything else is a parse error.
    """

    document = json.loads(payload)
    if not isinstance(document, dict):
        raise ValueError("teaching response payload must be a JSON object")
    if document.get("type") != TEACHING_RESPONSE_TYPE:
        raise ValueError(
            f"payload type is not {TEACHING_RESPONSE_TYPE}:"
            f" {document.get('type')!r}"
        )
    intent = document.get("control_intent")
    if not isinstance(intent, str) or intent not in CONTROL_INTENTS:
        raise ValueError(f"invalid control_intent: {intent!r}")
    present = bool(document.get("attempt_present", False))
    text = document.get("attempt_text")
    attempt = (
        AttemptPayload(text=str(text))
        if present and text is not None
        else None
    )
    confidence = document.get("interpretation_confidence", 1.0)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float, str)):
        raise ValueError(f"invalid interpretation_confidence: {confidence!r}")
    if isinstance(confidence, str) and not confidence.strip():
        raise ValueError(f"invalid interpretation_confidence: {confidence!r}")
    try:
        parsed_confidence = float(confidence)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"invalid interpretation_confidence: {confidence!r}"
        ) from exc
    switch = document.get("target_switch_request")
    clarification = document.get("clarification_request")
    preference = document.get("user_preference_signal")
    return TeachingResponseEnvelope(
        control_intent=TeachingControlIntent(intent),
        attempt_present=present,
        attempt=attempt,
        target_switch_request=None if switch is None else str(switch),
        clarification_request=(
            None if clarification is None else str(clarification)
        ),
        user_preference_signal=None if preference is None else str(preference),
        interpretation_confidence=parsed_confidence,
    )
