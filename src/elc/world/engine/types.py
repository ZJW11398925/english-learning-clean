"""The world-run engine's record shapes and vocabularies (W-1-2).

The engine advances one :class:`WorldRunRecord` — migration 0025's
``world_run`` row — through cycles of the spec §4.2 v2.1 sequence: the
pool's mature events happen, at most one actor is choreographed to
write, and the selected event's moment is the run's exit for the call
(:class:`MomentKind` — ``NOTICE`` pauses the run at its checkpoint,
``RESPONSE`` terminates it; ``DIRECTION`` is deliberately absent from
the vocabulary, W-2-2 opens it).

The pool (:class:`PoolEvent`) is pre-authored content: kind word,
narration, state effects, maturity conditions and the moment — this cut
generates no prose and carries no model face and no provider (AD-2's
continuity). :class:`Condition` is one maturity test: its
``(canonical_key, statement)`` pair must CURRENT-match the world's
state projection exactly for the event to be mature.

:class:`EngineConfig` carries the calibration knobs (spec §4.7: the
density is never a priori constant) — both numbers are **calibratable,
Revisit W-4-2**; the user's real runs will set them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.world.types import StateEffect

__all__ = [
    "Condition",
    "EngineConfig",
    "MomentKind",
    "PoolEvent",
    "RunStatus",
    "WorldRunRecord",
]


class MomentKind(StrEnum):
    """The special moment's participation requirement (spec §4.6).

    Two words this cut: ``NOTICE`` (seeing is enough — one light continue
    action resumes the same run) and ``RESPONSE`` (the world waits for
    the user's reply — the run's terminal stop). ``DIRECTION`` is
    deliberately not here: W-2-2 opens it, and the store's CHECK spells
    the same two words, so a third word cannot reach the row.
    """

    NOTICE = "NOTICE"
    RESPONSE = "RESPONSE"


class RunStatus(StrEnum):
    """The run row's two-word lifecycle (migration 0025's CHECK).

    ``AT_CHECKPOINT`` — the run is paused at its checkpoint (creation is
    the zeroth checkpoint; every NOTICE pause is the same word);
    ``TERMINAL`` — the run ended at the RESPONSE stop and the world
    waits for the next reply.
    """

    AT_CHECKPOINT = "AT_CHECKPOINT"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True)
class WorldRunRecord:
    """One world-run row (migration 0025's ``world_run`` table).

    ``seed`` is the run's dice: every cycle's draw is seeded from
    ``(seed, cursor)``, so the same seed replays the same run (M0.1
    AD-6 — a restart does not re-roll them). ``cursor`` is the cycle
    counter; ``state_version`` bumps on every run write and is
    deliberately NOT a canonical version spelling (the registry entry
    carries no ``version_field``). ``trigger_turn_id`` is the user reply
    that wound the spring, when known — no foreign key by design
    (Revisit W-1-3).
    """

    run_id: str
    world_id: str
    trigger_turn_id: str | None
    seed: int
    status: RunStatus
    checkpoint_kind: MomentKind
    cursor: int
    state_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class EngineConfig:
    """The engine's calibration knobs (spec §4.7 — calibratable, Revisit
    W-4-2).

    ``days_per_cycle`` is the step-2 time advance per cycle (this cut
    keeps no world calendar — the count is recorded in the trace and
    nothing pretends to be a clock). ``max_cycles`` is the fail-closed
    ceiling: a call that burns this many cycles without a mature event
    terminates the run (the engine never loops forever). Nonsense values
    are refused at construction — a negative day count or a zero ceiling
    would make the ceiling meaningless.
    """

    days_per_cycle: int = 1
    max_cycles: int = 8

    def __post_init__(self) -> None:
        if self.days_per_cycle < 0:
            raise ValueError(
                f"days_per_cycle must be >= 0, got {self.days_per_cycle}"
            )
        if self.max_cycles < 1:
            raise ValueError(f"max_cycles must be >= 1, got {self.max_cycles}")


@dataclass(frozen=True)
class Condition:
    """One maturity condition on a pool event.

    Mature means every condition of the event CURRENT-matches the world's
    state projection exactly — the canonical key exists as a ``CURRENT``
    fact and its statement is byte-equal. An event with no conditions is
    always mature.
    """

    canonical_key: str
    statement: str


@dataclass(frozen=True)
class PoolEvent:
    """One pre-authored pool event (the engine invents nothing).

    ``kind`` is the chronicle kind word and ``narration`` is the event's
    own prose — both arrive as the world package's content (AD-2: this
    cut generates none). ``effects`` are the state claims the event
    settles through the store's ``record_event`` (an empty tuple is a
    legal pure-narration event). ``conditions`` gate maturity.
    ``moment`` is the run's exit word when this event is selected — the
    default is the terminal stop (the world waits; the conservative
    reading of an unmarked event).

    A2 (DEC-…88/…90): ``days`` is the story's own span — the number of
    world days this event carries (zero = a same-day beat). The virtual
    world calendar (``elc.world.package.world_date_of``) sums the
    happened events' days on top of the package's ``calendar_start``;
    the engine itself stays clockless and this field is content the
    orchestrator's timestamp source reads — never a mechanical advance.

    The two tuple fields are runtime-defended (this cut's own answer to
    the DC4T LOW-1 shape registered on :mod:`elc.world.types` — there
    the declared tuple is not defended and a list passed at runtime
    survives the write but breaks the replay comparison): a sequence
    passed where the tuple is declared is coerced here, so the record
    the engine hands to the store always carries exact tuples.
    """

    kind: str
    narration: str
    effects: tuple[StateEffect, ...] = ()
    conditions: tuple[Condition, ...] = ()
    moment: MomentKind = MomentKind.RESPONSE
    days: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.effects, tuple):
            object.__setattr__(self, "effects", tuple(self.effects))
        if not isinstance(self.conditions, tuple):
            object.__setattr__(self, "conditions", tuple(self.conditions))
        if type(self.days) is not int or self.days < 0:
            raise ValueError(
                f"days must be a non-negative int, got {self.days!r}"
            )
