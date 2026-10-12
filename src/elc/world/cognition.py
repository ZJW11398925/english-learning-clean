"""The Narrative V3 cognition read face (V3-5R, TASK-OPI-dc1bafdf…13 /
the opening ruling DEC-OPI-dc1bafdf…11's HIGH-1; DATA §26.2.3's
"V3-5R 最小读路") — the minimal read through which a V3 consumer (the
Scene Planner's context today, the POV writer's context compilation
later) sees what one viewer knows of one world.

**The three laws this face resolves** (:func:`v3_cognition_view`):

- **V3 event judgment rides the explicit lineage face** — an event
  enters this read only through its ``segment_commit`` row (the JOIN).
  A legacy V2 event holds no lineage row and never appears: its
  vocabulary (cast persona ids ∪ the user id) is not a V3 participant
  vocabulary, and its ``occurred_at`` is a V2 ISO moment this face
  deliberately does not read.
- **Ordering rides the lineage actual interval** —
  ``actual_start_tick, actual_end_tick, event_id`` ascending: the world's
  story time as the commit transaction attributed it (the review's #1
  hard door's read side), never an event-id's naming.
- **The layers are canonical-identity judgments** — ``participants``
  empty ⇒ the event is public; the viewer among ``participants`` ⇒ the
  event is witnessed; otherwise the event is not the viewer's knowledge
  and is dropped. The comparison is over the canonical ``actor_id`` /
  ``player_character_id`` vocabulary (the V3-3R freeze) — **never** a
  persona id and never the Package's user-character mapping.

**Scope, declared honestly**: this face writes nothing (a pure read —
its SQL contains no transaction control at all), never consults
:mod:`elc.world.package`, and does not touch the legacy C1 cognition
view (:mod:`elc.host`'s world port: 公共 ∪ 亲历 ∪ 用户层) — that face
stays the legacy reader its callers keep, exactly as before. V3-7's
actor memory / belief materialization lands its own faces; when it does,
this read descends to a compatibility / fallback role (DATA §26.2.3's
same sentence, its C1 twin).

Discipline (the house store law): **value semantics** — a malformed
``viewer_id`` answers ``VALIDATION_FAILED`` with a human sentence, never
an exception; **the corrupted-row posture** — a stored ``participants``
payload this module's own codec family cannot decode raises
``ValueError`` (the store family's honest corrupted-row arm), never a
fabricated comparison; **no SQL string building** — fixed literals and
parameter binding only.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.types import decode_participants

__all__ = ["V3CognitionEvent", "V3CognitionView", "v3_cognition_view"]


@dataclass(frozen=True)
class V3CognitionEvent:
    """One V3 event as the cognition read answers it: the durable
    ``world_event`` row's identifying text plus the lineage face's
    actual interval (``actual_start_tick`` / ``actual_end_tick``)."""

    event_id: str
    kind: str
    narration: str
    participants: tuple[str, ...]
    actual_start_tick: int
    actual_end_tick: int


@dataclass(frozen=True)
class V3CognitionView:
    """One viewer's cognition of one world, split by the canonical
    layers: ``public`` — events with no participants (the world's own
    moves, everyone's knowledge) — and ``witnessed`` — events whose
    ``participants`` carry the viewer's own canonical identity. Both
    tuples ride the lineage order (actual interval, then event id); an
    event naming some other cast only is neither layer (it is not this
    viewer's knowledge)."""

    viewer_id: str
    public: tuple[V3CognitionEvent, ...]
    witnessed: tuple[V3CognitionEvent, ...]


def v3_cognition_view(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    viewer_id: str,
) -> Result[V3CognitionView]:
    """Read one viewer's V3 cognition view of one world — the three laws
    in the module docstring, nothing else.

    A ``viewer_id`` that is not a non-empty string is refused
    ``VALIDATION_FAILED`` (a human sentence: the viewer is the read's own
    address, and an empty addressee names nobody). The read is pure — no
    transaction of its own, in any case (the store family's read
    posture); a corrupted stored ``participants`` column raises
    ``ValueError`` (see the module docstring).
    """

    if not isinstance(viewer_id, str) or not viewer_id.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "cognition view refused: viewer_id must be a"
                    " non-empty string naming the viewer's canonical"
                    f" identity (got {viewer_id!r}) — an empty addressee"
                    " names nobody"
                ),
            )
        )
    rows = conn.execute(
        "SELECT e.event_id, e.kind, e.narration, e.participants,"
        " c.actual_start_tick, c.actual_end_tick"
        " FROM world_event e"
        " JOIN segment_commit c ON c.event_id = e.event_id"
        " WHERE e.world_id = ?"
        " ORDER BY c.actual_start_tick ASC, c.actual_end_tick ASC,"
        " e.event_id ASC",
        (world_id,),
    ).fetchall()
    public: list[V3CognitionEvent] = []
    witnessed: list[V3CognitionEvent] = []
    for row in rows:
        decoded = decode_participants(str(row[3]))
        if isinstance(decoded, Err):
            raise ValueError(
                f"event {row[0]!r} carries an undecodable participants"
                f" column: {decoded.error.message}"
            )
        event = V3CognitionEvent(
            event_id=str(row[0]),
            kind=str(row[1]),
            narration=str(row[2]),
            participants=decoded.value,
            actual_start_tick=int(row[4]),
            actual_end_tick=int(row[5]),
        )
        if not decoded.value:
            public.append(event)
        elif viewer_id in decoded.value:
            witnessed.append(event)
    return Ok(
        V3CognitionView(
            viewer_id=viewer_id,
            public=tuple(public),
            witnessed=tuple(witnessed),
        )
    )
