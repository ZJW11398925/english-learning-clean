"""elc.detection — the execution half of ``EXECUTABLY_VERIFIED`` (D-2).

This package executes detector matchers against the authoring source's
declared detection fixtures (the ones elc.content.build carries into
``content_detection_fixture``). The dependency direction is one-way —
``elc.content.build`` imports this package; nothing here imports
``elc.content`` (pinned by tests/detection) — so the runtime detection face
can grow without dragging the build step into it.

What a detector IS in V1: a **pure function over the learner production's
plain text** (:data:`Matcher`) — no model call, no confidence score, no side
effects. The package ships **no registered matcher** (the D-2 skeleton
state: :data:`elc.detection.registry.GLOBAL_REGISTRY` starts empty, and
D-3 pilots the first real matchers), so a default build derives no
``EXECUTABLY_VERIFIED`` row — the level moves only when a build is handed
a registry whose registered matcher passes an entity's full fixture set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class DetectionMatch:
    """One matcher hit: the declared §24.9 error_type the text instantiates."""

    error_type: str


#: A detector: the learner production's plain text in, one hit (or none)
#: out. No model, no confidence — the declared rules answer "which declared
#: error type does this text instantiate, if any", and nothing else.
Matcher = Callable[[str], DetectionMatch | None]


class DetectionFixture(Protocol):
    """One fixture row, read structurally.

    The shape is the build step's ``DetectionFixtureRow`` (elc.content.
    build), declared here as a protocol instead of imported, so this
    package never depends on ``elc.content``. A runner consumer may hand
    in any object carrying these five readable attributes.
    """

    @property
    def ordinal(self) -> int: ...

    @property
    def kind(self) -> str: ...

    @property
    def text(self) -> str: ...

    @property
    def expected(self) -> str: ...

    @property
    def source_error_type(self) -> str | None: ...


@dataclass(frozen=True)
class FixtureOutcome:
    """One fixture row's execution record (the row's judgment, kept)."""

    ordinal: int
    kind: str
    expected: str
    matched: bool
    matched_error_type: str | None
    passed: bool


@dataclass(frozen=True)
class VerificationOutcome:
    """One target's full fixture-set execution — the EV decision's input.

    ``all_passed`` is the vacuous truth over ``outcomes``; the grantor
    (elc.content.build) additionally requires ``fixture_count > 0``, so an
    entity with no fixtures is never promoted for an empty pass.
    """

    entity_id: str
    outcomes: tuple[FixtureOutcome, ...]
    all_passed: bool
    fixture_count: int
