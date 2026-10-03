"""The pilot expansion cut — the roster grows from twelve to thirty-six.

D-3's mode replicated over twenty-four further ``EDITOR_REVIEWED`` R4
targets (read the entity's declared rules, implement them on surface
anchors and word tables, pass the full fixture set). Pinned here:

- the roster face: ``PILOT_ENTITIES`` is thirty-six ids and stays sorted
  (the assembling sentinels compare the registry's sorted id list
  against this tuple verbatim, so the sort is load-bearing), the
  twenty-four expansion ids are all present beside the untouched D-3
  twelve, and every roster id has exactly one registered matcher with a
  non-empty rule-ordinal claim;
- the fixture face: every expansion matcher passes its own full fixture
  set through the real runner (NEGATIVE and FALSE_POSITIVE_BOUNDARY
  rows must not match, POSITIVE_ERROR rows must match with the row's
  own error type);
- the artifact face: the CLI pilot build carries exactly the roster as
  ``EXECUTABLY_VERIFIED`` (36 EV / 10 EDITOR / 54 AUTHOR / 0 EC), while
  the default API build stays zero-EV and byte-identical with the
  parent commit's own library-default artifact (the sha256 is pinned);
- the gate face: over the pilot artifact the automatic
  CURRENT_USER_ERROR row reads usable 36 / blocked 16 / GO, and over
  the default artifact 0 / 52 / HOLD — the expansion moved only the
  roster's own targets;
- the generalization probes: unseen same-pattern sentences are judged
  by the declared rules, not by fixture text.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import (
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    build_content_db,
    load_source,
)
from elc.content.store import ContentStore
from elc.curriculum.store import CurriculumContentStore
from elc.detection import DetectorRegistry, run_fixtures
from elc.detection.pilot import (
    _PILOT_DETECTORS,
    PILOT_ENTITIES,
    PILOT_VERSION,
    register_pilot,
)
from elc.platform.types import Ok
from elc.teaching.rollout import EXECUTABLE_VERIFICATION_FLOOR, corpus_rollout_gate
from tests.conftest import REPO_ROOT
from tests.detection.support import provenance_map

#: The twelve the D-3 cut landed; the expansion appends beside them and
#: their matchers stay byte-identical (pinned by the cut's own diff).
_D3_ORIGINAL_TWELVE = (
    "res-discourse-anyway",
    "res-discourse-before-i-forget",
    "res-discourse-moving-on",
    "res-hedge-i-guess",
    "res-hedge-i-think",
    "res-hedge-more-or-less",
    "res-pragmatic-come-again",
    "res-pragmatic-fair-enough",
    "res-pragmatic-got-it",
    "res-pragmatic-i-see",
    "res-pragmatic-no-way",
    "res-pragmatic-that-makes-sense",
)

#: The twenty-four expansion targets, in roster order.
_EXPANSION_ENTITIES = (
    "res-discourse-on-another-note",
    "res-discourse-speaking-of-which",
    "res-discourse-that-brings-me-to",
    "res-discourse-to-be-honest",
    "res-discourse-to-get-back-to-the-point",
    "res-discourse-where-was-i",
    "res-hedge-as-far-as-i-know",
    "res-hedge-if-im-not-mistaken",
    "res-hedge-in-a-way",
    "res-hedge-it-seems-to-me",
    "res-pragmatic-are-you-saying",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-go-on",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-i-see-your-point-but",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-let-me-make-sure",
    "res-pragmatic-no-offense-but",
    "res-pragmatic-right",
    "res-pragmatic-up-to-a-point",
    "res-pragmatic-what-do-you-mean",
    "res-pragmatic-with-all-due-respect",
    "res-softener-kind-of",
)

#: The parent commit's own library-default artifact digest: the sha256 of
#: the ``build_content_db()`` (no registry) product built from the
#: archived parent tree. The default build's bytes did not move with that
#: cut — a corpus or build change does move them, and this pin must be
#: re-derived then (a truth-migration pin, not a freeze; re-derived for the
#: queue-2 screening: 6edb57cf… was the C3-d-truth artifact; re-derived
#: again for the queue-2 disposal cut's rationale citation fix:
#: 7a2816ab… was the queue-2 delivery artifact; re-derived for the
#: queue-3 scenario-variant cut — its 120 usage-variant rows + 120 aligned
#: resource-label rows moved the corpus bytes:
#: 21d039f3… is the queue-3 delivery artifact; re-derived for the
#: queue-3 disposal cut (the F-1 roster swap — two unteachable R1
#: survivors out, two R4 receipt targets in — held the 120-row shape
#: but moved the corpus bytes:
#: 90932ab5… is the queue-3 disposal artifact).
_PARENT_DEFAULT_SHA256 = (
    "90932ab597154a3b8a3da86af1bc34529621347b012ffb8c7c539cdfd5b9d399"
)


@pytest.fixture(scope="module")
def source_documents() -> dict[str, Any]:
    """The authoring source's evidence documents, by entity id."""

    source = load_source(CONTENT_SRC_DIR, CURRICULUM_DIR)
    return {document.entity_id: document for document in source.evidence}


def _pilot_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    register_pilot(registry)
    return registry


# ---------------------------------------------------------------------------
# the roster face
# ---------------------------------------------------------------------------


def test_the_roster_is_thirty_six_sorted_ids_with_the_expansion_appended(
) -> None:
    assert len(PILOT_ENTITIES) == 36
    assert PILOT_ENTITIES == tuple(sorted(PILOT_ENTITIES))
    assert len(set(PILOT_ENTITIES)) == 36
    assert set(_D3_ORIGINAL_TWELVE).issubset(PILOT_ENTITIES)
    assert set(_EXPANSION_ENTITIES).issubset(PILOT_ENTITIES)
    assert set(_D3_ORIGINAL_TWELVE).isdisjoint(_EXPANSION_ENTITIES)
    assert set(_D3_ORIGINAL_TWELVE) | set(_EXPANSION_ENTITIES) == set(
        PILOT_ENTITIES
    )


def test_the_pilot_version_names_the_expansion_set() -> None:
    assert PILOT_VERSION == "d3-pilot-2"
    assert PILOT_VERSION not in PILOT_ENTITIES


def test_every_roster_id_has_exactly_one_registered_matcher() -> None:
    """Deleting a matcher entry breaks this pin; deleting a roster id
    breaks the artifact pins below — the roster and the registered set
    are two views of one list."""

    registry = _pilot_registry()
    assert registry.known_targets() == tuple(sorted(PILOT_ENTITIES))
    detector_ids = tuple(row[0] for row in _PILOT_DETECTORS)
    assert detector_ids == PILOT_ENTITIES
    ordinals = {
        entry.entity_id: entry.rule_ordinals for entry in registry.entries()
    }
    assert all(ordinals[entity] for entity in PILOT_ENTITIES)
    with pytest.raises(ValueError):
        register_pilot(registry)


# ---------------------------------------------------------------------------
# the fixture face — every expansion matcher passes its own fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entity_id", _EXPANSION_ENTITIES)
def test_every_expansion_matcher_passes_its_own_fixture_set(
    source_documents: dict[str, Any], entity_id: str
) -> None:
    entry = next(
        entry
        for entry in _pilot_registry().entries()
        if entry.entity_id == entity_id
    )
    outcome = run_fixtures(
        entry.matcher,
        source_documents[entity_id].detection_fixtures,
        entity_id=entity_id,
    )
    assert outcome.fixture_count > 0
    failures = [
        (row.ordinal, row.kind, row.text, row.matched_error_type)
        for row in outcome.outcomes
        if not row.passed
    ]
    assert outcome.all_passed, failures


# ---------------------------------------------------------------------------
# the artifact face — the pilot build carries exactly the roster
# ---------------------------------------------------------------------------


def test_the_cli_pilot_build_carries_exactly_the_roster(
    tmp_path: Path,
) -> None:
    out = tmp_path / "cli-content.db"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "elc.content.build", "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    levels = list(provenance_map(out).values())
    ev = sorted(
        entity
        for entity, level in provenance_map(out).items()
        if level == "EXECUTABLY_VERIFIED"
    )
    assert ev == sorted(PILOT_ENTITIES)
    assert levels.count("EXECUTABLY_VERIFIED") == 36
    assert levels.count("EDITOR_REVIEWED") == 10
    assert levels.count("AUTHOR_DECLARED") == 54
    assert levels.count("EMPIRICALLY_CALIBRATED") == 0


def test_the_default_build_stays_zero_ev_and_byte_identical_with_the_parent(
    tmp_path: Path,
) -> None:
    """``build_content_db()`` with no registry keeps building the
    parent's artifact: zero EV, and the same bytes the parent commit's
    own library-default build produced (the digest above was computed
    over the archived parent tree — this pin makes the byte-identity
    executable in-repo)."""

    out = tmp_path / "default.db"
    build_content_db(out)
    baseline = provenance_map(out)
    assert len(baseline) == 100
    levels = list(baseline.values())
    assert levels.count("EXECUTABLY_VERIFIED") == 0
    assert levels.count("EMPIRICALLY_CALIBRATED") == 0
    assert levels.count("EDITOR_REVIEWED") == 46
    assert levels.count("AUTHOR_DECLARED") == 54
    assert (
        hashlib.sha256(out.read_bytes()).hexdigest()
        == _PARENT_DEFAULT_SHA256
    )


# ---------------------------------------------------------------------------
# the gate face — the fourth row over both artifacts
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def default_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dexp-default") / "content.db"
    build_content_db(path)
    return path


@pytest.fixture(scope="module")
def pilot_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dexp-pilot") / "content.db"
    build_content_db(path, detector_registry=_pilot_registry())
    return path


def _fourth_row(db: Path) -> tuple[int, int, str]:
    """The artifact's automatic CURRENT_USER_ERROR row: usable, blocked,
    verdict."""

    store = ContentStore(db)
    try:
        supply = CurriculumContentStore(store)
        provenance = store.provenance_levels()
        assert isinstance(provenance, Ok), provenance
        report = corpus_rollout_gate(supply, dict(provenance.value))
        assert isinstance(report, Ok), report
    finally:
        store.close()
    row = report.value.row("automatic CURRENT_USER_ERROR")
    assert row.verdict is not None
    return (
        row.usable_targets,
        row.blocked_by_provenance,
        report.value.verdict.value,
    )


def test_the_pilot_artifact_opens_the_fourth_row_on_thirty_six(
    pilot_db: Path,
) -> None:
    assert _fourth_row(pilot_db) == (36, 57, "GO")


def test_the_default_artifact_holds_the_fourth_row_on_zero_ev(
    default_db: Path,
) -> None:
    assert _fourth_row(default_db) == (0, 93, "HOLD")


def test_the_expansion_moved_only_the_rosters_own_targets(
    default_db: Path, pilot_db: Path
) -> None:
    """Every non-roster entity reads the same level under both builds —
    the promotion set is exactly the roster, id for id."""

    baseline = provenance_map(default_db)
    promoted = provenance_map(pilot_db)
    assert set(baseline) == set(promoted)
    for entity, level in baseline.items():
        if entity in PILOT_ENTITIES:
            assert promoted[entity] == EXECUTABLE_VERIFICATION_FLOOR, entity
        else:
            assert promoted[entity] == level, entity


# ---------------------------------------------------------------------------
# the generalization probes — same pattern, new words
# ---------------------------------------------------------------------------


def test_unseen_sentences_are_judged_by_the_declared_rules() -> None:
    from elc.detection.pilot import (
        detect_are_you_saying,
        detect_could_you_say_that_again,
        detect_go_on,
        detect_kind_of,
        detect_on_another_note,
        detect_right,
        detect_up_to_a_point,
        detect_where_was_i,
        detect_with_all_due_respect,
    )

    # on-another-note: the wrong preposition on a fresh matter; the
    # accepted variant spelling and the literal note refuse; the
    # comma-less marker fires the punctuation rule.
    assert (
        detect_on_another_note(
            "In another note, the venue moved to June."
        ).error_type
        == "PREPOSITION_SLIP"
    )
    assert detect_on_another_note("On a different note, see you Friday.") is None
    assert (
        detect_on_another_note("On another note the invoice still waits.")
        .error_type
        == "MISSING_COMMA"
    )

    # where-was-i: the broken orders with a fresh follow-up; the
    # inverted question and the embedded indirect question refuse.
    assert (
        detect_where_was_i("Where I was? Oh yes — the venue booking.")
        .error_type
        == "QUESTION_INVERSION_SLIP"
    )
    assert (
        detect_where_was_i("I was where? Oh yes — the venue booking.")
        .error_type
        == "WH_IN_SITU"
    )
    assert detect_where_was_i("Where was I? Oh yes — the venue booking.") is None
    assert detect_where_was_i("Do you remember where I was?") is None

    # go-on: the subjectless be-clause on a fresh matter; the owned
    # clause and the inverted question refuse.
    assert (
        detect_go_on("Go on, is cold in here.").error_type
        == "SUBJECT_DROP"
    )
    assert detect_go_on("Go on, is it just me?") is None
    assert (
        detect_go_on("Go on — what happen after that?").error_type
        == "PAST_MARKING_SLIP"
    )
    assert detect_go_on("Go on — what happened after that?") is None

    # right: the homophone and the adverb form in the receipt slot on a
    # fresh follow-up; the bare receipt refuses.
    assert (
        detect_right("Write — the speaker is with you.").error_type
        == "HOMOPHONE_SPELLING"
    )
    assert (
        detect_right("Rightly — the speaker is with you.").error_type
        == "ADVERB_OVERCORRECTION"
    )
    assert detect_right("Right — the speaker is with you.") is None

    # are-you-saying: the auxiliary drop and the bare verb form on a
    # fresh check; the whole check refuses.
    assert (
        detect_are_you_saying("You saying that the venue changed again?")
        .error_type
        == "AUXILIARY_DROP"
    )
    assert (
        detect_are_you_saying("Are you say that the truck comes on Monday?")
        .error_type
        == "VERB_FORM_SLIP"
    )
    assert (
        detect_are_you_saying("Are you saying that the truck comes on Monday?")
        is None
    )

    # could-you-say-that-again: the doubled marking and the objectless
    # say on fresh tails; the owned request refuses.
    assert (
        detect_could_you_say_that_again(
            "Could you repeat again? I missed the room number."
        ).error_type
        == "REDUNDANT_AGAIN"
    )
    assert (
        detect_could_you_say_that_again(
            "Could you say again, please? The speaker cut out."
        ).error_type
        == "OBJECT_DROP"
    )
    assert (
        detect_could_you_say_that_again("Could you say that again, please?")
        is None
    )

    # up-to-a-point: the dropped article and the swapped preposition on
    # a fresh objection; the whole phrase refuses.
    assert (
        detect_up_to_a_point(
            "Up to point, yes, but the second survey worries me."
        ).error_type
        == "ARTICLE_DROP"
    )
    assert (
        detect_up_to_a_point(
            "I agree until a point, but the second survey worries me."
        ).error_type
        == "PREPOSITION_SLIP"
    )
    assert (
        detect_up_to_a_point("Up to a point, yes — the second survey waits.")
        is None
    )

    # with-all-due-respect: the wrong preposition and the plural noun on
    # a fresh criticism; the whole flag refuses.
    assert (
        detect_with_all_due_respect(
            "In all due respect, the numbers disagree with the report."
        ).error_type
        == "PREPOSITION_SLIP"
    )
    assert (
        detect_with_all_due_respect(
            "With all due respects, that is not what we agreed."
        ).error_type
        == "NUMBER_SLIP"
    )
    assert (
        detect_with_all_due_respect(
            "With all due respect, the numbers disagree with the report."
        )
        is None
    )

    # kind-of: the intruded article before a modifier and the bare
    # softener before a head noun, on fresh words; the classifier and
    # the wh-question refuse.
    assert (
        detect_kind_of("The soup was a kind of strange, if you ask me.")
        .error_type
        == "ARTICLE_INTRUSION"
    )
    assert (
        detect_kind_of("They opened kind of shop by the river.")
        .error_type
        == "CLASSIFIER_ARTICLE_MISSING"
    )
    assert detect_kind_of("This is a kind of problem that repeats.") is None
    assert detect_kind_of("What kind of bird is that?") is None
    assert detect_kind_of("The ending is kind of sad.") is None
