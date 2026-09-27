"""The fixture runner — the judgment that earns ``EXECUTABLY_VERIFIED``.

The judgment is pinned per fixture kind, one arm per kind:

- ``NEGATIVE`` (expected ``NO_MATCH``) — the matcher must **not** match;
- ``FALSE_POSITIVE_BOUNDARY`` (expected ``NO_MATCH_BOUNDARY``) — the
  matcher must **not** match: the boundary word is a semantic marker about
  the example (it sits exactly on the declared edge), not a different
  judgment — sitting on the edge still means the declared rules do not
  fire;
- ``POSITIVE_ERROR`` (expected ``MATCH``) — the matcher **must** match AND
  the hit's ``error_type`` must equal the row's own ``source_error_type``:
  a hit with the wrong declared type is a failure, not a pass.

A matcher that raises is a defect of the registration, not a fixture
failure, so the exception is not caught here — it propagates, and the
build (elc.content.build) wraps it into a ``BuildError`` that names the
detector.
"""

from __future__ import annotations

from collections.abc import Sequence

from elc.detection.types import (
    DetectionFixture,
    DetectionMatch,
    FixtureOutcome,
    Matcher,
    VerificationOutcome,
)

#: The two fixture kinds whose expected reading is "the declared rules do
#: not fire" — a boundary row is judged exactly like a negative row.
_NON_MATCH_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY")

#: The one kind whose expected reading is a typed match.
_MATCH_KIND = "POSITIVE_ERROR"


def run_fixture(matcher: Matcher, fixture: DetectionFixture) -> FixtureOutcome:
    """Run one fixture row through the matcher and judge it per kind."""

    match: DetectionMatch | None = matcher(fixture.text)
    matched = match is not None
    matched_error_type = match.error_type if match is not None else None
    if fixture.kind == _MATCH_KIND:
        passed = matched and matched_error_type == fixture.source_error_type
    elif fixture.kind in _NON_MATCH_KINDS:
        passed = not matched
    else:
        raise ValueError(
            f"unknown fixture kind {fixture.kind!r} (the runner judges the "
            f"three declared kinds only: {_NON_MATCH_KINDS + (_MATCH_KIND,)})"
        )
    return FixtureOutcome(
        ordinal=fixture.ordinal,
        kind=fixture.kind,
        expected=fixture.expected,
        matched=matched,
        matched_error_type=matched_error_type,
        passed=passed,
    )


def run_fixtures(
    matcher: Matcher,
    fixtures: Sequence[DetectionFixture],
    *,
    entity_id: str,
) -> VerificationOutcome:
    """Run a target's full fixture set; ``all_passed`` is the EV decision.

    An empty fixture set answers ``all_passed=True`` vacuously — the
    grantor (elc.content.build) additionally requires ``fixture_count > 0``,
    so no entity is ever promoted for having nothing to pass.
    """

    outcomes = tuple(run_fixture(matcher, fixture) for fixture in fixtures)
    return VerificationOutcome(
        entity_id=entity_id,
        outcomes=outcomes,
        all_passed=all(outcome.passed for outcome in outcomes),
        fixture_count=len(outcomes),
    )
