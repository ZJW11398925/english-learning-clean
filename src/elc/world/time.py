"""The story_tick primitives (V3-1, DEC-OPI-bab4da9f…11/…16) — the
world's own time, one integer per world.

The time model (the design doc §四 / STATE_MACHINES §26 / DATA_MODEL
§26.2.2): ``story_tick`` is an **integer world time unit** — the data
layer's only time form; the World Calendar (World Bible, a later cut)
*interprets* it for display and never participates in ordering. The
database does not depend on the Gregorian calendar anywhere. Wall-clock
ISO strings remain system bookkeeping (row timestamps) and never enter
the user-visible timeline.

MVP granularity (V3-1's ruling, DOMAIN_MODEL §20.3-5): **1 tick =
1 minute** for the Gold Scenario's imperial calendar. The Calendar is
pure interpretation — it formats, it does not count — so this module
ships the integer primitive only and deliberately ships **no
formatting function**: a tick is read, advanced and compared as an
integer; turning one into an imperial date is the Calendar cut's work.

The two primitives:

- :func:`read_current_tick` — the world's current actual tick (the
  ``world.current_tick`` column migration 0029 adds; ``0`` is the
  column's DEFAULT, a world starts at tick zero).
- :func:`advance_current_tick` — move the tick forward by a
  non-negative delta, monotone by construction (``current_tick =
  current_tick + delta`` in one UPDATE): a negative delta is refused
  with ``VALIDATION_FAILED`` before anything is written, and a missing
  world is ``NOT_FOUND`` — value semantics, never an exception.

**Authority (N-INV-007 / N-R-INV-005, spelled here because this module
is where a future violator will look): the actual tick moves only
inside a commit transaction** — SEGMENT COMMIT / ACTION OUTCOME COMMIT
(RUNTIME_ARCHITECTURE §28, NCP-2 / NCP-3) are the only sanctioned
callers. V3-1 ships the primitive and *not* the commit transaction:
until a later cut lands one, nothing in production code advances the
tick, and :func:`advance_current_tick` is a building block that the
commit transaction will call **inside its own short transaction** (the
primitives manage no transactions of their own — a nested BEGIN would
break exactly the composability the commit needs). The Plan face
(Director / Scene Planner) writes ``planned_*_tick`` columns only and
has no write path to ``world.current_tick`` at all.

Sorting and causality read the actual tick; display is the Calendar's
interpretation (§26). ``planned ≠ actual``: user behaviour may drag a
scene past its planned window, and the two field families never share
a "story time span".
"""

from __future__ import annotations

import sqlite3

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = ["read_current_tick", "advance_current_tick"]


def read_current_tick(
    conn: sqlite3.Connection, world_id: str
) -> Result[int]:
    """Read one world's current actual tick (the ``world.current_tick``
    column, migration 0029's DEFAULT ``0``).

    A world the table does not know is ``NOT_FOUND`` — a dangling
    reference is a value-semantics refusal, never an exception (the
    store's posture). The read is a pure column read: no default
    invention, no clock consultation — the tick is whatever the last
    commit transaction left.
    """

    row = conn.execute(
        "SELECT current_tick FROM world WHERE world_id = ?", (world_id,)
    ).fetchone()
    if row is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"tick of world {world_id!r} not read: the world"
                    " does not exist"
                ),
            )
        )
    return Ok(int(row[0]))


def advance_current_tick(
    conn: sqlite3.Connection, world_id: str, delta: int
) -> Result[int]:
    """Advance one world's actual tick by ``delta`` (``delta >= 0``),
    returning the new tick.

    Monotone by construction: the single UPDATE adds the delta to the
    stored value, so the tick never moves backwards and a concurrent
    read sees either the old or the new value, never an intermediate.
    Refusals, both before anything is written:

    - ``delta < 0`` — ``VALIDATION_FAILED`` (the actual tick does not
      go backwards; STATE_MACHINES §26 / §27's 「actual tick 回退」);
    - the world does not exist — ``NOT_FOUND``.

    **The caller owns the transaction.** The only sanctioned caller is
    a commit transaction (NCP-2 / NCP-3) that advances the tick as one
    arm of its atomic group; this function manages no BEGIN/COMMIT of
    its own so it composes inside that short transaction. V3-1 ships
    no commit transaction — until one lands, nothing in production
    advances the tick (the authority note this module's docstring
    spells).
    """

    if delta < 0:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"tick of world {world_id!r} not advanced by"
                    f" {delta}: the actual tick never moves backwards"
                ),
            )
        )
    cursor = conn.execute(
        "UPDATE world SET current_tick = current_tick + ?"
        " WHERE world_id = ?",
        (delta, world_id),
    )
    if cursor.rowcount != 1:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"tick of world {world_id!r} not advanced: the"
                    " world does not exist"
                ),
            )
        )
    row = conn.execute(
        "SELECT current_tick FROM world WHERE world_id = ?", (world_id,)
    ).fetchone()
    assert row is not None  # the UPDATE above just touched it
    return Ok(int(row[0]))
