"""The user-initiated teaching request — command shape + canonical payload.

Phase 3 P3-1A, TASK-OPI-2babb21e-….17 ⑥ (mother decision DEC-…2babb21e.5:
``request_teaching(conversation_id, focus_target_id, target_type?,
target_mode?)``).

A call forms a canonical *command turn*:

- the ``InputEnvelope.raw_payload`` is the canonical TEACHING_REQUEST JSON
  (:func:`teaching_request_payload` — sorted keys, fixed separators, i.e.
  the elc.learning.analysis canonical-JSON convention), so the request is a
  typed payload, not natural language;
- the ``UserTurn`` carries ``raw_content=""`` / ``normalized_content=None``:
  nothing was said, so nothing is asserted into the transcript;
- a command turn produces no TEXT_PRODUCTION / TEXT_COMPREHENSION evidence
  and must never be injected into a ConversationWindow as a normal persona
  utterance (the teaching meaning travels through the typed payload, not
  through NLU over an empty string).

The intent scope is derived from the request itself (BF-03 §11: a
user-initiated OPEN must carry LEARNING_REQUEST /
TARGETED_LEARNING_REQUEST): an explicit focus target is a
TARGETED_LEARNING_REQUEST.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    TargetId,
)

__all__ = [
    "TEACHING_REQUEST_TYPE",
    "TeachingRequest",
    "intent_scope_for_request",
    "parse_teaching_request_payload",
    "teaching_request_payload",
]

#: Payload discriminator of the canonical command-turn JSON.
TEACHING_REQUEST_TYPE = "TEACHING_REQUEST"


@dataclass(frozen=True)
class TeachingRequest:
    """One user-initiated teaching request (the command face's input).

    ``target_type`` is the RESOURCE / CAPABILITY scope (docs/DOMAIN_MODEL
    §6); ``target_mode`` is the optional docs/DOMAIN_MODEL §11 mode — when
    omitted, the resolved target's canonical default is used (the
    TeachingTargetView). ``client_message_id`` dedupes the command turn the
    same way any other input does (docs/DATA_MODEL.md §4 Unique).
    """

    conversation_id: ConversationId
    focus_target_id: TargetId
    target_type: str = "RESOURCE"
    target_mode: str | None = None
    client_message_id: ClientMessageId | None = None
    input_id: InputId | None = None
    interaction_channel: InteractionChannel = InteractionChannel.TEXT
    requested_at: str | None = None
    runtime_version: str = "runtime-v1"


def teaching_request_payload(request: TeachingRequest) -> str:
    """Canonical JSON of the request payload (deterministic: sorted keys,
    fixed separators, absent optional fields omitted)."""

    payload: dict[str, str] = {
        "type": TEACHING_REQUEST_TYPE,
        "focus_target_id": str(request.focus_target_id),
        "target_type": request.target_type,
    }
    if request.target_mode is not None:
        payload["target_mode"] = request.target_mode
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def parse_teaching_request_payload(payload: str) -> dict[str, str]:
    """Parse + shape-check a canonical TEACHING_REQUEST payload.

    Raises ``ValueError`` on a payload that is not a teaching request —
    the same "contract error, not a decision" posture the Gate takes on a
    malformed call (BF-03 §21).
    """

    document = json.loads(payload)
    if not isinstance(document, dict):
        raise ValueError("teaching request payload must be a JSON object")
    if document.get("type") != TEACHING_REQUEST_TYPE:
        raise ValueError(
            f"payload type is not {TEACHING_REQUEST_TYPE}:"
            f" {document.get('type')!r}"
        )
    if not document.get("focus_target_id"):
        raise ValueError("teaching request payload lacks focus_target_id")
    return {str(key): str(value) for key, value in document.items()}


def intent_scope_for_request(request: TeachingRequest) -> str:
    """BF-03 §11 scope for a user-initiated OPEN: an explicit focus target
    is a TARGETED_LEARNING_REQUEST (a bare learning request would be
    LEARNING_REQUEST)."""

    return (
        "TARGETED_LEARNING_REQUEST"
        if request.focus_target_id
        else "LEARNING_REQUEST"
    )
