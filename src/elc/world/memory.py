"""The Narrative V3 actor memory / belief face (V3-7, TASK-OPI-d274a7fb…8
/ the opening ruling DEC-OPI-d274a7fb…6; DATA §26.2.1's "V3-7 落表形"
block; STATE §25's "V3-7 落法") — migration 0037's ``actor_memory``
table, its two-writer face and its one-viewer read.

**What a memory is** (the design's memory six-way split, its fourth
domain): a durable row saying *this participant knows this much of this
event, in this way*. The five kind words are the vocabulary, and **every
one of them is reachable** — the cut's own law against a dead word
table:

- ``EXPERIENCED`` — the witnessed kind, landed **automatically** by the
  two commit transactions (:func:`record_experienced_in_transaction`
  under NCP-2 / NCP-3's own atomic groups: every participant of the
  event lived it);
- ``HEARD`` / ``BELIEVED`` / ``INFERRED`` / ``MISTAKEN`` — the
  caller-supplied kinds, landed through :func:`record_belief` (the
  explicit increment face the orchestration layer and the later cuts
  call; the automatic arm deliberately refuses to mint them).

**Identities are derived, append-only is the law**: ``memory_id`` spells
``f"mem:{event_id}:{participant_id}:{kind}"`` — one event, one
participant, one kind, at most one row (the derivation serves idempotent
replay only; §26.2.2's lineage discipline: narrative time is attributed
through the explicit faces, never inferred from an id's naming). A
``record_belief`` replay with the same shape answers the stored row
unchanged; a different shape is a ``CONFLICT`` — **memories do not
rewrite** (N-INV-003: corrections arrive as later memories), and the
table's own ``CHECK (kind IN ...)`` is the storage-side word list.

**The read face** (:func:`v3_memory_view`) answers one viewer's memory
of one world — ``participant_id`` = the viewer's **canonical identity**
(the V3-3R freeze: ``world_actor.actor_id`` ∪
``world_player_character.player_character_id``; a persona id names no
one here), layered by the five-word kind order (:class:`MemoryKind`'s
own declaration order — experienced first, the most direct) and, inside
a layer, ordered by ``learned_at_tick`` then ``memory_id``: a
deterministic walk replays byte for byte. The viewer's own canonical
identity is the read's address; an empty or malformed one is refused
``VALIDATION_FAILED`` (a human sentence, the cognition face's own
posture). A viewer with no memory answers the honest empty view.

**The participant vocabulary is the caller's faithful tuple**: the
automatic arm writes one ``EXPERIENCED`` row per participant **in
order, skipping nothing**, with plain ``INSERT`` statements — a genuine
second write (the derived identity already carried) surfaces as the
table's own refusal, mapped to ``CONFLICT`` by the caller's own
``_refusal_code``, never a silent ``INSERT OR IGNORE`` that would let a
memory go missing. The caller's participant tuple has passed the
canonical ``participant_namespace`` check one layer up (the commit
transactions judge it; this leaf module never re-derives it — the
Package is not consulted, and this module imports no store).

Discipline (the house store law): **value semantics** — a malformed
``viewer_id`` or a caller-supplied field answers ``VALIDATION_FAILED``
with a human sentence, never an exception; a dangling identity answers
``NOT_FOUND``; a shape clash answers ``CONFLICT``; the database's own
failures answer ``DEPENDENCY_UNAVAILABLE``; **one short transaction**
per write face (the automatic arm is the caller's transaction's own
body — it opens none); **the corrupted-row posture** — a stored
``kind`` word this module's own vocabulary cannot decode raises
``ValueError`` (the store family's honest corrupted-row arm); **no
hidden clock** — every stamp rides the caller's ``now`` and every
``learned_at_tick`` the caller's canon read; **no SQL string building**
— fixed literals and parameter binding only; the one ``f"..."`` that
builds values builds *identities* (``memory_id``), never SQL. A leaf
module: it imports :mod:`elc.platform.types` only (no cycle, cold-start
safe).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = [
    "ActorMemoryRecord",
    "MemoryKind",
    "V3MemoryView",
    "memory_id_for",
    "record_belief",
    "record_experienced_in_transaction",
    "v3_memory_view",
]


class MemoryKind(StrEnum):
    """The five memory kind words — DATA §26.2.1's ``actor_memory``
    block, word for word (migration 0037's CHECK spells the same list),
    in the contract's own declaration order (the view's layering order).
    """

    EXPERIENCED = "EXPERIENCED"
    HEARD = "HEARD"
    BELIEVED = "BELIEVED"
    INFERRED = "INFERRED"
    MISTAKEN = "MISTAKEN"


#: The layering order (:meth:`MemoryKind`'s declaration order) as the
#: view's ORDER BY reads it — one truth for the SQL and the docstring.
_KIND_ORDER = tuple(kind.value for kind in MemoryKind)


@dataclass(frozen=True)
class ActorMemoryRecord:
    """One ``actor_memory`` row — the durable memory, verbatim.

    ``kind`` rides as the :class:`MemoryKind` word (a stored word
    outside the vocabulary raises ``ValueError`` on read — the
    corrupted-row posture); ``salience`` is ``None`` for every
    deterministic-baseline row (the evaluation is a later cut's), and
    the bookkeeping pair carries the caller's stamps.
    """

    memory_id: str
    world_id: str
    participant_id: str
    kind: MemoryKind
    content: str
    source_event_id: str
    learned_at_tick: int
    salience: float | None
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class V3MemoryView:
    """One viewer's memory of one world: the ``viewer_id`` addressed (the
    viewer's canonical identity) and its memory rows, layered by kind
    (:class:`MemoryKind`'s order — ``EXPERIENCED`` first) and, inside a
    layer, ordered by ``learned_at_tick`` then ``memory_id`` ascending.
    An empty tuple is the honest "this participant remembers nothing
    yet", never an error."""

    viewer_id: str
    memories: tuple[ActorMemoryRecord, ...]


def memory_id_for(
    event_id: str, participant_id: str, kind: MemoryKind
) -> str:
    """The memory identity law: ``f"mem:{event_id}:{participant_id}:{kind}"``
    — one event, one participant, one kind, at most one row
    (DATA §26.2.1's derivation; idempotent replay only, never a
    narrative-time attribution — §26.2.2's lineage discipline)."""

    return f"mem:{event_id}:{participant_id}:{kind.value}"


def record_experienced_in_transaction(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    event_id: str,
    participants: tuple[str, ...],
    content: str,
    learned_at_tick: int,
    now: str,
) -> None:
    """The two commit transactions' shared memory arm (STATE §25's
    "V3-7 落法"): one ``EXPERIENCED`` row per event participant, landed
    **inside the caller's transaction** — this arm runs no
    ``BEGIN`` / ``COMMIT`` of its own (the same no-transaction posture
    :func:`elc.world.store._settle_effects_in_transaction` and the
    narrative store's ``*_tx`` arms keep). NCP-3
    (:func:`elc.world.settlement.commit_segment`) and NCP-2
    (:func:`elc.world.action.commit_action`) are its two callers; both
    call it on the **fresh** path only — the replay arm answers first, so
    a replay never double-lands a memory.

    The participant tuple rides **in order, skipping nothing**: every
    canonical participant lived the event, so every one gets a row. The
    statements are plain ``INSERT`` — a genuine second write (the derived
    identity already carried) is the table's own refusal, surfaced by the
    caller's error mapping, never silently dropped.

    ``content`` is the event's ``narration`` (the deterministic
    baseline); ``learned_at_tick`` the commit's ``actual_end_tick`` (the
    canon time anchor); ``salience`` stays NULL (unevaluated). Raises
    ``sqlite3.Error`` on the database's refusal — the caller's
    transaction owns the rollback, the ``_settle_effects_in_transaction``
    posture spelled once next door.
    """

    for participant_id in participants:
        conn.execute(
            "INSERT INTO actor_memory ("
            " memory_id, world_id, participant_id, kind, content,"
            " source_event_id, learned_at_tick, salience,"
            " created_at, updated_at, state_version"
            ") VALUES (?, ?, ?, 'EXPERIENCED', ?, ?, ?, NULL, ?, ?, 1)",
            (
                memory_id_for(event_id, participant_id, MemoryKind.EXPERIENCED),
                world_id,
                participant_id,
                content,
                event_id,
                learned_at_tick,
                now,
                now,
            ),
        )


def record_belief(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    event_id: str,
    participant_id: str,
    kind: MemoryKind,
    content: str,
    learned_at_tick: int,
    now: str,
    salience: float | None = None,
) -> Result[ActorMemoryRecord]:
    """Land one caller-supplied memory — the explicit increment face the
    automatic arm deliberately leaves open. One short ``BEGIN IMMEDIATE``
    … ``COMMIT`` writes the row (a write face, the house posture).

    ``kind`` must be one of the four **caller-supplied words** —
    ``HEARD`` / ``BELIEVED`` / ``INFERRED`` / ``MISTAKEN``;
    ``EXPERIENCED`` is refused: the witnessed kind is the two commit
    transactions' own automatic arm (a caller minting it would forge the
    "was there" claim). The identity derives
    ``f"mem:{event_id}:{participant_id}:{kind}"``; ``content`` is the
    caller's memory text, ``learned_at_tick`` the caller's canon read
    (the commit's tick — the world's actual time), ``salience`` optional.

    Refusals, all value semantics, nothing written:

    - ``participant_id`` not a non-empty string — ``VALIDATION_FAILED``
      (the canonical-identity address; an empty one names nobody);
    - ``event_id`` / ``world_id`` not non-empty strings, or
      ``learned_at_tick`` not an integer ``>= 0`` (a bool is not an
      integer here), or ``kind`` not a :class:`MemoryKind`, or
      ``EXPERIENCED`` given, or ``content`` not a string, or
      ``salience`` neither ``None`` nor a real number —
      ``VALIDATION_FAILED`` (the message names the field);
    - the event does not exist — ``NOT_FOUND``; the event belongs to
      another world — ``VALIDATION_FAILED`` (a memory names its own
      world's event);
    - the same derived identity with a different shape (``content`` /
      ``learned_at_tick`` / ``salience`` included) — ``CONFLICT``
      (**append-only**: the identity landed once and does not rewrite —
      a correction or an alteration arrives as a later memory,
      N-INV-003).

    A replay of the same identity with the same shape answers the stored
    row unchanged — zero write, the stored ``learned_at_tick`` and
    ``salience`` standing (the caller's shape is what must match). The
    existence read runs outside the ``BEGIN IMMEDIATE`` (the same
    posture :func:`elc.world.settlement.record_exposure` documents): a
    concurrent first-write race would surface as the table's own PK
    refusal (``CONFLICT``) — never a silent second row.
    """

    if not isinstance(participant_id, str) or not participant_id.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: participant_id must be a"
                    " non-empty string naming the rememberer's canonical"
                    f" identity (got {participant_id!r}) — an empty"
                    " addressee names nobody"
                ),
            )
        )
    if not isinstance(world_id, str) or not world_id.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: world_id must be a non-empty"
                    f" string (got {world_id!r})"
                ),
            )
        )
    if not isinstance(event_id, str) or not event_id.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: event_id must be a non-empty"
                    f" string naming the memory's source event (got"
                    f" {event_id!r})"
                ),
            )
        )
    if not isinstance(kind, MemoryKind):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: kind must be a MemoryKind word"
                    f" ({', '.join(_KIND_ORDER)}); got {kind!r}"
                ),
            )
        )
    if kind is MemoryKind.EXPERIENCED:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: EXPERIENCED is the commit"
                    " transactions' own automatic arm — every event"
                    " participant witnesses it as the segment or action"
                    " commits (STATE §25's V3-7 memory arm); this face"
                    " carries the caller-supplied kinds (HEARD / BELIEVED"
                    " / INFERRED / MISTAKEN)"
                ),
            )
        )
    if not isinstance(content, str):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: content must be a string; got"
                    f" {type(content).__name__}"
                ),
            )
        )
    if (
        not isinstance(learned_at_tick, int)
        or isinstance(learned_at_tick, bool)
        or learned_at_tick < 0
    ):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: learned_at_tick must be an"
                    f" integer >= 0 (got {learned_at_tick!r}) — a memory"
                    " is learned at a canonical tick"
                ),
            )
        )
    if salience is not None and (
        not isinstance(salience, (int, float)) or isinstance(salience, bool)
    ):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory not recorded: salience must be None or a"
                    f" real number; got {type(salience).__name__}"
                ),
            )
        )

    memory_id = memory_id_for(event_id, participant_id, kind)
    existing = _memory_row(conn, memory_id)
    if existing is not None:
        if (
            existing.world_id,
            existing.participant_id,
            existing.kind,
            existing.content,
            existing.source_event_id,
            existing.learned_at_tick,
            existing.salience,
        ) == (
            world_id,
            participant_id,
            kind,
            content,
            event_id,
            learned_at_tick,
            None if salience is None else float(salience),
        ):
            return Ok(existing)
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"memory {memory_id!r} already exists with a different"
                    " shape (its content / learned_at_tick / salience are"
                    " stored facts); memories are append-only and do not"
                    " rewrite — a correction or an alteration arrives as a"
                    " later memory (N-INV-003)"
                ),
            )
        )

    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        event_row = conn.execute(
            "SELECT world_id FROM world_event WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if event_row is None:
            conn.execute("ROLLBACK")
            began = False
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"memory {memory_id!r} not recorded: source event"
                        f" {event_id!r} does not exist — a memory names"
                        " the event it was learned from"
                    ),
                )
            )
        if str(event_row[0]) != world_id:
            conn.execute("ROLLBACK")
            began = False
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"memory {memory_id!r} not recorded: event"
                        f" {event_id!r} belongs to world"
                        f" {str(event_row[0])!r}, not {world_id!r} — a"
                        " memory names its own world's event"
                    ),
                )
            )
        conn.execute(
            "INSERT INTO actor_memory ("
            " memory_id, world_id, participant_id, kind, content,"
            " source_event_id, learned_at_tick, salience,"
            " created_at, updated_at, state_version"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                memory_id,
                world_id,
                participant_id,
                kind.value,
                content,
                event_id,
                learned_at_tick,
                None if salience is None else float(salience),
                now,
                now,
            ),
        )
    except sqlite3.Error as exc:
        if began:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        return Err(
            DomainError(
                code=_refusal_code(exc),
                message=f"memory {memory_id!r} not recorded: {exc}",
            )
        )
    conn.execute("COMMIT")
    row = _memory_row(conn, memory_id)
    assert row is not None  # the INSERT above just landed it
    return Ok(row)


def v3_memory_view(
    conn: sqlite3.Connection,
    *,
    world_id: str,
    viewer_id: str,
) -> Result[V3MemoryView]:
    """Read one viewer's actor memory of one world — the V3-7 dossier /
    context input (DATA §26.2.1's "dossier 改读 actor memory"; the
    cognition view descends to its compatibility / fallback role beside
    this face). A pure read: no transaction of its own, no write, and
    the reader's own memory rows are the whole answer — ``viewer_id`` is
    the viewer's canonical identity (the where-clause's participant).

    A ``viewer_id`` that is not a non-empty string is refused
    ``VALIDATION_FAILED`` (the read's own address; an empty addressee
    names nobody — the cognition face's sentence family). The rows ride
    layered by :class:`MemoryKind`'s declaration order, then by
    ``learned_at_tick`` and ``memory_id`` ascending; a viewer with no
    row answers the honest empty view. A corrupted stored ``kind`` word
    raises ``ValueError`` (see the module docstring).
    """

    if not isinstance(viewer_id, str) or not viewer_id.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "memory view refused: viewer_id must be a non-empty"
                    " string naming the viewer's canonical identity (got"
                    f" {viewer_id!r}) — an empty addressee names nobody"
                ),
            )
        )
    rows = conn.execute(
        "SELECT memory_id, world_id, participant_id, kind, content,"
        " source_event_id, learned_at_tick, salience, created_at,"
        " updated_at, state_version FROM actor_memory"
        " WHERE world_id = ? AND participant_id = ?"
        " ORDER BY CASE kind"
        "   WHEN 'EXPERIENCED' THEN 0"
        "   WHEN 'HEARD' THEN 1"
        "   WHEN 'BELIEVED' THEN 2"
        "   WHEN 'INFERRED' THEN 3"
        "   WHEN 'MISTAKEN' THEN 4"
        " END ASC, learned_at_tick ASC, memory_id ASC",
        (world_id, viewer_id),
    ).fetchall()
    return Ok(
        V3MemoryView(
            viewer_id=viewer_id,
            memories=tuple(_memory_record(row) for row in rows),
        )
    )


def _memory_row(
    conn: sqlite3.Connection, memory_id: str
) -> ActorMemoryRecord | None:
    """One memory row by its derived identity, or ``None`` — the read
    every replay answer uses."""

    row = conn.execute(
        "SELECT memory_id, world_id, participant_id, kind, content,"
        " source_event_id, learned_at_tick, salience, created_at,"
        " updated_at, state_version FROM actor_memory"
        " WHERE memory_id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None
    return _memory_record(row)


def _memory_record(row: tuple[Any, ...]) -> ActorMemoryRecord:
    """One memory row tuple in the record shape (the strict kind
    vocabulary; a stored word this module does not carry raises
    ``ValueError`` — the corrupted-row posture)."""

    try:
        kind = MemoryKind(str(row[3]))
    except ValueError as exc:
        raise ValueError(
            f"memory {str(row[0])!r} carries an unknown kind word"
            f" {str(row[3])!r} (the vocabulary is"
            f" {'/'.join(_KIND_ORDER)}) — a corrupted memory row"
        ) from exc
    return ActorMemoryRecord(
        memory_id=str(row[0]),
        world_id=str(row[1]),
        participant_id=str(row[2]),
        kind=kind,
        content=str(row[4]),
        source_event_id=str(row[5]),
        learned_at_tick=int(row[6]),
        salience=None if row[7] is None else float(row[7]),
        created_at=str(row[8]),
        updated_at=str(row[9]),
        state_version=int(row[10]),
    )


def _refusal_code(exc: sqlite3.Error) -> DomainErrorCode:
    """Map the database's own refusal to the store vocabulary — the same
    three families :mod:`elc.world.settlement` spells: a UNIQUE / PK
    clash is a ``CONFLICT``, a FOREIGN KEY refusal is ``NOT_FOUND``, any
    other database failure answers ``DEPENDENCY_UNAVAILABLE`` with the
    raw error riding the message."""

    text = str(exc)
    if "UNIQUE constraint failed" in text:
        return DomainErrorCode.CONFLICT
    if "FOREIGN KEY constraint failed" in text:
        return DomainErrorCode.NOT_FOUND
    return DomainErrorCode.DEPENDENCY_UNAVAILABLE
