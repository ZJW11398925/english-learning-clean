"""D-6-a — the dispatch unit: one turn's text through the registry.

The CURRENT_USER_ERROR producer's own contract, pinned where it lives:
sorted de-duplicated ids, zero hits answer empty, many hits answer many,
a matcher that raises skips its own target (the runtime layer of the
two-layer failure posture — the build refuses, the runtime degrades), and
the output never names an id outside the registry.
"""

from __future__ import annotations

import ast

from elc.detection import DetectorRegistry
from elc.detection.dispatch import RegistryDispatch, detect_current_user_errors
from elc.detection.pilot import register_pilot
from elc.detection.types import DetectionMatch, Matcher
from tests.conftest import SRC_ROOT


def _registry_with(*pairs: tuple[str, Matcher]) -> DetectorRegistry:
    registry = DetectorRegistry()
    for entity_id, matcher in pairs:
        registry.register(entity_id, (0,), matcher)
    return registry


def _always(error_type: str) -> Matcher:
    def matcher(text: str) -> DetectionMatch | None:
        return DetectionMatch(error_type)

    return matcher


def _when(needle: str) -> Matcher:
    def matcher(text: str) -> DetectionMatch | None:
        if needle in text.lower():
            return DetectionMatch("SPLIT_SPELLING")
        return None

    return matcher


class _InsertionOrderDuplicates(DetectorRegistry):
    """A registry that answers ``entries()`` in insertion order, duplicated.

    ``DetectorRegistry.entries()`` sorts, so the dispatch's own sorted-set
    contract needs a registry whose iteration is *not* already sorted (and
    carries each entry twice) for the pin to have teeth: deleting the
    dispatch's ``sorted(set(...))`` turns this red, while the shipped
    registry's own sorting would keep it green either way.
    """

    def entries(self) -> tuple:  # type: ignore[override]
        values = tuple(self._entries.values())
        return values + values


def test_hits_come_back_sorted_and_deduplicated() -> None:
    registry = _InsertionOrderDuplicates()
    # Registered in reverse alphabetical order on purpose: the answer must
    # not follow the registry's iteration order.
    registry.register("res-b-second", (0,), _always("FORM_SLIP"))
    registry.register("res-a-first", (0,), _always("FORM_SLIP"))
    assert detect_current_user_errors("anything", registry) == (
        "res-a-first",
        "res-b-second",
    )


def test_zero_hits_answer_the_empty_tuple() -> None:
    registry = _registry_with(("res-x", _when("needle")))
    assert detect_current_user_errors("nothing relevant here", registry) == ()


def test_many_hits_answer_many_ids() -> None:
    registry = _registry_with(
        ("res-anyway", _when("any way")),
        ("res-got-it", _when("are got it")),
    )
    hits = detect_current_user_errors(
        "Any way, they are got it wrong.", registry
    )
    assert hits == ("res-anyway", "res-got-it")


def test_a_raising_matcher_skips_its_own_target_only() -> None:
    def broken(text: str) -> DetectionMatch | None:
        raise ZeroDivisionError("a matcher that cannot run")

    registry = _registry_with(
        ("res-broken", broken),
        ("res-healthy", _when("any way")),
    )
    assert detect_current_user_errors("Any way, fine.", registry) == (
        "res-healthy",
    )


def test_the_output_never_leaves_the_registry() -> None:
    """m8's pin: no fabricated id — every answer is a registered target."""

    registry = DetectorRegistry()
    register_pilot(registry)
    for text in (
        "Any way, let's continue with the plan.",
        "The meeting starts at nine.",
        "Any way, they are got it wrong.",
        "Think we should leave earlier.",
    ):
        for hit in detect_current_user_errors(text, registry):
            assert hit in registry.known_targets()


def test_the_pilot_registry_reads_the_dogfood_sentences() -> None:
    registry = DetectorRegistry()
    register_pilot(registry)
    assert detect_current_user_errors(
        "Any way, let's continue with the plan.", registry
    ) == ("res-discourse-anyway",)
    assert (
        detect_current_user_errors("The meeting starts at nine.", registry)
        == ()
    )


def test_the_bound_face_answers_as_the_function_does() -> None:
    registry = DetectorRegistry()
    register_pilot(registry)
    face = RegistryDispatch(registry)
    assert face.detect_current_user_errors(
        "Any way, let's continue."
    ) == detect_current_user_errors("Any way, let's continue.", registry)


def test_no_turn_text_answers_none_not_an_empty_observation() -> None:
    """The D-6-a review LOW-2 guard: ``_turn_observation`` with a wired face
    but no turn text answers ``None`` — "no observation" — never an empty
    ``OpportunityObservation()`` (which would read as "observed zero hits").
    The three-state promise is the wiring docstring's; this pins the middle
    state at the unit the review's m9 mutation broke (deleting the guard
    silently downgrades "not observed" into "observed nothing")."""

    from elc.runtime.automatic_turn import (
        AutomaticTurnWiring,
        _turn_observation,
    )

    registry = DetectorRegistry()
    register_pilot(registry)
    wiring = AutomaticTurnWiring(
        planner_store=None,  # type: ignore[arg-type]
        teaching=None,  # type: ignore[arg-type]
        error_detectors=RegistryDispatch(registry),
    )
    assert _turn_observation(wiring, None, []) is None


def test_the_detection_package_never_imports_content_still_holds() -> None:
    """The D-2 one-way dependency re-asserted over the new module (the
    package-level scan in ``test_d2_build_ev_derivation`` already covers it;
    this is the new file's own name in the offender list if it ever breaks).
    """

    path = SRC_ROOT / "detection" / "dispatch.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not alias.name.startswith("elc.content")
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("elc.content")
