"""The World bounded context — identity binding (W-1-0) plus the event
tree and its minimal state projection (W-1-1).

W-1-0 is the living-world program's first cut (direction
DEC-OPI-7e3744ee…2, the user's living-world mainline; the program's
opening ruling DEC-OPI-7e3744ee…4; M0.1 DEC-OPI-d96fd92d…7): it lands the
three migration-0023 tables (:mod:`elc.world.store` is their SQL face)
and the frozen identity record shapes below.

W-1-1 (DEC-OPI-7e3744ee…17) lands the event tree and the minimal state
projection: :class:`WorldEvent` is one append-only chronicle entry
carrying its caller-written narration and zero or more
:class:`StateEffect` claims; :class:`WorldStateFact` is one settled
state row — ``CURRENT`` for the newest fact per ``(world_id,
canonical_key)``, ``SUPERSEDED`` for every older one (the projection
keeps its history; there is no unique on the key). Still not here: no
engine, no reveal face, no narration generation, no world behaviour —
those are W-1-2+ / W-1-3 registered cuts, and this package ships none of
them rather than a stub that pretends to.

Value semantics: a world is a named root or fork (``template_world_id``
names the fork parent, NULL is a root — the fork lineage is W-3-2's
consumption, recorded here and built nowhere); an actor binds one world
to one character card (migration 0019's ``character_card.persona_id``);
a conversation binding puts one conversation inside one world through an
actor of that world (the composite FK keeps the actor and the world a
real pair — the migration spells it, the store refuses around it).

The effects codec: :func:`encode_effects` freezes an effects tuple into
the column's canonical JSON text (compact, non-escaped, insertion-ordered
— the same tuple always encodes to the same bytes);
:func:`decode_effects` is its strict inverse. A payload that is not
valid JSON, not a JSON array, not an object of exactly ``key`` and
``statement`` string fields, comes back as a value-semantics ``Err``
(never an exception) with the discriminating reason in the message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
)

__all__ = [
    "WorldRecord",
    "WorldActorRecord",
    "WorldConversationRecord",
    "StateEffect",
    "WorldEvent",
    "WorldStateFact",
    "STORYLINE_EFFECT_KEY_PREFIX",
    "STORYLINE_RESOLVED_STATEMENT",
    "encode_effects",
    "decode_effects",
    "encode_participants",
    "decode_participants",
    "storyline_effect_key",
]


@dataclass(frozen=True)
class WorldRecord:
    """One world's identity row (migration 0023's ``world`` table).

    ``template_world_id`` is the fork's parent (``None`` = a root world);
    the referenced world may be created later only by another row's own
    write — the FK refuses a dangling template at insert time.
    """

    world_id: str
    name: str
    template_world_id: str | None
    created_at: str


@dataclass(frozen=True)
class WorldActorRecord:
    """One actor's identity row (migration 0023's ``world_actor`` table).

    An actor is the join of one world and one character card: the card
    must exist (the FK target MC-0's migration 0019 provides), and one
    card speaks as at most one actor per world (the
    ``UNIQUE (world_id, persona_id)``).
    """

    actor_id: str
    world_id: str
    persona_id: PersonaId
    created_at: str


@dataclass(frozen=True)
class WorldConversationRecord:
    """One conversation's world binding (migration 0023's
    ``world_conversation`` table).

    ``conversation_id`` is UNIQUE — a conversation binds to at most one
    world — and the composite FK (actor, world) keeps the bound actor a
    member of the bound world; a binding that pairs an actor with a world
    it does not belong to is refused, never stored.
    """

    binding_id: str
    world_id: str
    actor_id: str
    conversation_id: ConversationId
    created_at: str


@dataclass(frozen=True)
class StateEffect:
    """One state claim an event settles (migration 0024's ``effects``
    element shape).

    ``key`` is the canonical state key (free text until W-1-2 registers a
    vocabulary); ``statement`` is the claim the event makes about the
    world's state. An event's effects are settled together, atomically:
    the whole event lands or none of it does.
    """

    key: str
    statement: str


@dataclass(frozen=True)
class WorldEvent:
    """One chronicle entry (migration 0024's ``world_event`` table,
    extended by migration 0027's two attribution columns).

    Append-only: an event is written once and never updated — corrections
    arrive as later events. ``narration`` is the caller's own prose (this
    cut generates none); ``effects`` is the ordered tuple of state claims
    the event settles (an empty tuple is a legal pure-narration event);
    ``occurred_at`` is the event's own ISO-8601 moment as the caller
    supplies it — the log does not re-stamp it; ``source`` names the
    origin (a free word until a later cut registers the vocabulary).

    C1-a (DEC-OPI-41a4df20…55): ``participants`` is the ordered tuple of
    cast members the event is about (the chronicle's who — the strict
    codec below freezes it into migration 0027's JSON column; an empty
    tuple is the default, and a legacy row reads back as one);
    ``run_id`` is the world run the event rode (``None`` for the user
    interaction rows — an interaction is not a run event — and for a
    pre-0027 legacy row, which honestly does not know).
    """

    event_id: str
    world_id: str
    kind: str
    narration: str
    effects: tuple[StateEffect, ...]
    occurred_at: str
    source: str
    participants: tuple[str, ...] = ()
    run_id: str | None = None


@dataclass(frozen=True)
class WorldStateFact:
    """One settled state row (migration 0024's ``world_state_fact``
    table).

    Every fact is settled *by* one event (``source_event_id`` — the
    projection is a reading of the tree, never an independent write).
    ``status`` is the two-word lifecycle the migration's CHECK spells:
    ``CURRENT`` for the newest fact of its ``(world_id, canonical_key)``,
    ``SUPERSEDED`` for every older one — several rows per key are the
    design (the projection keeps its history). ``recorded_at`` is the
    source event's own ``occurred_at`` (the settlement is synchronous
    with the event, and the projection stays derived from the tree).
    """

    fact_id: str
    world_id: str
    source_event_id: str
    canonical_key: str
    statement: str
    status: str
    recorded_at: str


def encode_effects(effects: tuple[StateEffect, ...]) -> str:
    """Freeze an effects tuple into the column's canonical JSON text.

    The encoding is deterministic (compact separators, insertion order,
    non-escaped characters): the same tuple always encodes to the same
    bytes — a replay writes what the first write wrote.
    """

    payload = [{"key": effect.key, "statement": effect.statement} for effect in effects]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_effects(text: str) -> Result[tuple[StateEffect, ...]]:
    """The strict inverse of :func:`encode_effects`.

    A payload that is not valid JSON, not a JSON array, not an object of
    exactly the two string fields ``key`` and ``statement``, answers a
    value-semantics ``Err`` (``VALIDATION_FAILED``) whose message names
    the reason — the discrimination words are ``not valid JSON`` / ``not
    a JSON array`` / ``not a JSON object`` / ``missing 'key'`` /
    ``missing 'statement'`` / ``is not a string`` / ``unexpected
    fields``. Decoding is a read-side concern only (the write face
    encodes from typed records and cannot produce a bad payload).
    """

    def _err(message: str) -> Err[Any]:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=f"effects refused: {message}",
            )
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _err(f"not valid JSON ({exc})")
    if not isinstance(payload, list):
        return _err(f"not a JSON array (got {type(payload).__name__})")
    effects: list[StateEffect] = []
    for index, element in enumerate(payload):
        if not isinstance(element, dict):
            return _err(
                f"effects[{index}] not a JSON object (got"
                f" {type(element).__name__})"
            )
        if "key" not in element:
            return _err(f"effects[{index}] missing 'key'")
        if "statement" not in element:
            return _err(f"effects[{index}] missing 'statement'")
        if not isinstance(element["key"], str):
            return _err(f"effects[{index}].key is not a string")
        if not isinstance(element["statement"], str):
            return _err(f"effects[{index}].statement is not a string")
        extra = set(element) - {"key", "statement"}
        if extra:
            return _err(
                f"effects[{index}] unexpected fields"
                f" ({', '.join(sorted(extra))})"
            )
        effects.append(StateEffect(key=element["key"], statement=element["statement"]))
    return Ok(tuple(effects))


def encode_participants(participants: tuple[str, ...]) -> str:
    """Freeze a participants tuple into migration 0027's canonical JSON
    column text — the same deterministic law :func:`encode_effects`
    spells (compact, insertion-ordered, non-escaped): the same tuple
    always encodes to the same bytes, so a replay writes what the first
    write wrote."""

    return json.dumps(list(participants), ensure_ascii=False, separators=(",", ":"))


def decode_participants(text: str) -> Result[tuple[str, ...]]:
    """The strict inverse of :func:`encode_participants`.

    A payload that is not valid JSON or not a JSON array of strings
    answers a value-semantics ``Err`` (``VALIDATION_FAILED``) whose
    message names the reason — the discrimination words are ``not valid
    JSON`` / ``not a JSON array`` / ``is not a string``. Decoding is a
    read-side concern only (the write face encodes from typed records
    and cannot produce a bad payload)."""

    def _err(message: str) -> Err[Any]:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=f"participants refused: {message}",
            )
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _err(f"not valid JSON ({exc})")
    if not isinstance(payload, list):
        return _err(f"not a JSON array (got {type(payload).__name__})")
    for index, element in enumerate(payload):
        if not isinstance(element, str):
            return _err(
                f"participants[{index}] is not a string (got"
                f" {type(element).__name__})"
            )
    return Ok(tuple(payload))


#: The state-effect key prefix a storyline closure proposal carries
#: (C2, DEC-OPI-b290799a…45): the narrator declares a storyline
#: resolved by proposing, in the beat's own ``effects``, the canonical
#: key :func:`storyline_effect_key` spells — the same key namespace
#: every other projection claim rides, one layer for the structure and
#: one for the state.
STORYLINE_EFFECT_KEY_PREFIX = "storyline:"

#: The statement word that makes a closure a closure (C2): the
#: projection filter in ``SqliteWorldStore.active_storylines`` honors
#: exactly this word — a different statement under a
#: :data:`STORYLINE_EFFECT_KEY_PREFIX` key is a state claim about the
#: line, never its retirement.
STORYLINE_RESOLVED_STATEMENT = "resolved"


def storyline_effect_key(line_id: str) -> str:
    """The canonical state key one storyline's closure proposal carries:
    ``storyline:<line_id>`` (C2). The narrator's prompt teaches the
    format and the store's active read filters on it — one derivation,
    both consumers, never two spellings."""

    return f"{STORYLINE_EFFECT_KEY_PREFIX}{line_id}"
