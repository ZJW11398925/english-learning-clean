"""W-5 — the answer-key face becomes judgeable for the twelve EV pilot
targets (Phase 11, content program; DEC-OPI-631452f9-bd11-4b69-8fb6-df16f825fca6.1
as refined by DEC-OPI-631452f9-bd11-4b69-8fb6-df16f825fca6.4).

What this cut did, and what this file pins:

- **the dogfood evidence**: the read-only user library (D:\\_d6b\\app.db)
  showed 4 teaching moments / 4 attempts / 4:4 all FAILURE at confidence
  0.5 (the NO_MATCH shape) on semantically correct attempts, because the
  12 EV pilot keys carried contextualized whole sentences as canonical and
  in-sentence content words as required slots. The attempt face was
  effectively unpassable on the dogfood-reachable set.
- **the key face (conservative addition)**: each of the twelve entities
  gains the bare formula as ``canonical_forms[0]`` — the previous
  contextualized sentence stays verbatim behind it (got-it also gains the
  common subject-carrying variant) — ``alternative_realizations`` are
  untouched, and ``required_slots`` become the formula's own tokens
  (i-think keeps its old slots). Monotonicity: the previously accepted set
  is revoked nowhere, pinned by re-judging the old canonical sentence to
  SUCCESS.
- **the metadata face**: ``entity_revision`` 1 → 2 and
  ``updated_in_version`` "content-v1" → "content-w5" for exactly the
  twelve; every other corpus row stays at revision 1 / content-v1.
- **the audit record**: ``content_src/audits/w5-key-face-audit.json``
  approves exactly the twelve, all already inside the prior records'
  union — provenance stays 54 × AUTHOR_DECLARED + 46 × EDITOR_REVIEWED.
- **the corpus truth stands**: readiness 52 × R4 + 48 × R1 + 5 × None,
  the three Calibration100 floors 32 / 20 / 100, the 51-row credit face,
  595 fixtures, and the default-API build's EV = 0 (the pilot registry is
  not the default; nothing here opens anything).

The canonical authoring trees are never edited by a test: every variant
lives in a pytest tmp copy built through the real build step.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.content.build import CONTENT_SRC_DIR
from elc.content.store import ContentStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok
from elc.teaching.evaluator import evaluate_attempt
from elc.teaching.types import AttemptOutcome
from tests.phase5.test_content_migration import (
    V3D_FIRST_TOUCH_TARGETS,
    V3D_INFLECTION_TARGETS,
    V3D_UPDATED_IN_VERSION,
    V31_REWRITE_TARGETS,
    V31_UPDATED_IN_VERSION,
)

#: The twelve W-5 targets, in plain id sort order (the N-C3C-2 convention).
W5_TARGETS = (
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

#: The pre-written key face, verbatim from the task book's table:
#: (canonical_forms, alternative_realizations, required_slots). The
#: alternative lists are the values as v3-1 left them — W-5's "保留旧值,
#: byte for byte" held until the v3-1 slot-criterion rewrite added the
#: evidence-declared realization to i-think and replaced its slot groups
#: with the formula's own tokens（槽位 = 目标自身的词汇材料）.
_KeyFace = tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, ...], ...]]
W5_KEY_FACE: dict[str, _KeyFace] = {
    "res-discourse-anyway": (
        ("Anyway.", "Anyway, let's get back to the topic."),
        ("Anyhow, let's get back to the topic.",),
        (("anyway",),),
    ),
    "res-discourse-before-i-forget": (
        (
            "Before I forget.",
            "Before I forget — the parking permit expires on Monday.",
        ),
        ("Before I forget, did you pay the invoice?",),
        (("before",), ("forget",)),
    ),
    "res-discourse-moving-on": (
        ("Moving on.", "Moving on, let's look at the timeline."),
        ("Moving on to the next item, let's look at the timeline.",),
        (("moving",), ("on",)),
    ),
    "res-hedge-i-guess": (
        ("I guess.", "I guess we should leave soon."),
        ("It's going to rain, I guess.",),
        (("guess",),),
    ),
    "res-hedge-i-think": (
        ("I think.", "I think it is going to rain."),
        (
            "It might rain.",
            "I'd say it will rain.",
            "It is going to rain, I think.",
        ),
        # v3-1: the example-scene topic word group (["rain"]) is gone; the
        # slot key is the hedge formula's own tokens.
        (("think", "guess", "reckon"),),
    ),
    "res-hedge-more-or-less": (
        ("More or less.", "The migration is more or less complete."),
        ("The two estimates match more or less.",),
        (("more",), ("less",)),
    ),
    "res-pragmatic-come-again": (
        ("Come again?", "Come again? I didn't quite catch the name."),
        ("Come again — did you say four thirty or four fifteen?",),
        (("come",), ("again",)),
    ),
    "res-pragmatic-fair-enough": (
        ("Fair enough.", "Fair enough — let's split the difference."),
        ("Fair enough, we'll do it your way this time.",),
        (("fair",), ("enough",)),
    ),
    "res-pragmatic-got-it": (
        ("Got it.", "I got it.", "Got it. I'll send the file tonight."),
        ("Got it, thanks — I'll send the file tonight.",),
        (("got",),),
    ),
    "res-pragmatic-i-see": (
        ("I see.", "Right, I see. Please go on."),
        ("I see. Please go on.",),
        (("see",),),
    ),
    "res-pragmatic-no-way": (
        ("No way!", "No way! She actually moved to Lisbon?"),
        ("No way — he ran the whole marathon?",),
        (("no",), ("way",)),
    ),
    "res-pragmatic-that-makes-sense": (
        ("That makes sense.", "That makes sense — so we start in May."),
        ("That makes sense to me.",),
        (("makes",), ("sense",)),
    ),
}

#: The audit record's own words (its strict keys; the id is unique repo-wide).
W5_AUDIT_ID = "w5-key-face-audit"
W5_UPDATED_IN_VERSION = "content-w5"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _example_rows(artifact: Path, entity_id: str) -> tuple[str, ...]:
    """The §24.5 PRIMARY_TARGET forms in authored ordinal order."""

    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT form FROM content_example "
            "WHERE entity_id = ? AND role = 'PRIMARY_TARGET' ORDER BY ordinal",
            (entity_id,),
        ).fetchall()
    finally:
        conn.close()
    return tuple(str(row[0]) for row in rows)


def _slot_rows(artifact: Path, entity_id: str) -> tuple[tuple[str, ...], ...]:
    """The §24.5 slot groups in authored (group, token) ordinal order."""

    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT group_ordinal, token FROM content_slot "
            "WHERE entity_id = ? ORDER BY group_ordinal, token_ordinal",
            (entity_id,),
        ).fetchall()
    finally:
        conn.close()
    groups: list[list[str]] = []
    current = -1
    for group_ordinal, token in rows:
        if int(group_ordinal) != current:
            groups.append([])
            current = int(group_ordinal)
        groups[-1].append(str(token))
    return tuple(tuple(group) for group in groups)


def _readiness_levels(artifact: Path) -> dict[str, str | None]:
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        table = supply.readiness_by_target()
        assert isinstance(table, Ok), table
    finally:
        store.close()
    return {a.target_id: a.level for a in table.value}


def _provenance(artifact: Path) -> dict[str, str]:
    store = ContentStore(artifact)
    try:
        levels = store.provenance_levels()
        assert isinstance(levels, Ok), levels
    finally:
        store.close()
    return dict(levels.value)


@pytest.fixture()
def provider(built_content_db: Path):
    """The production provider over the session artifact (the real key
    source of the judging chain), closed by the test."""

    opened = ContentBackedTeachingTargetProvider(built_content_db)
    yield opened
    opened.close()


def _key_of(provider: ContentBackedTeachingTargetProvider, target_id: str):
    view = provider.resolve("RESOURCE", target_id)
    assert isinstance(view, Ok), view
    return view.value.answer_key()


# ---------------------------------------------------------------------------
# ① the key face: content_example / content_slot == the pre-written table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", W5_TARGETS)
def test_the_key_face_rows_read_the_prewritten_table_verbatim(
    built_content_db: Path, target_id: str
) -> None:
    """The stored §24.5 example rows and slot groups, in authored order,
    equal the pre-written table word for word (canonical[0] is the new bare
    formula, canonical[1] the old sentence kept verbatim; got-it carries
    the extra subject-carrying variant at [1]; the alternative lists are
    the old values, byte for byte)."""

    canonical, alternatives, slots = W5_KEY_FACE[target_id]
    assert _example_rows(built_content_db, target_id) == canonical
    store = ContentStore(built_content_db)
    try:
        view = store.get_teaching_content(target_id)
        assert isinstance(view, Ok), view
    finally:
        store.close()
    assert view.value.alternative_realizations == alternatives
    assert view.value.required_slots == slots
    assert _slot_rows(built_content_db, target_id) == slots


@pytest.mark.parametrize("target_id", W5_TARGETS)
def test_the_reveal_form_still_ends_the_canonical_list(
    built_content_db: Path, target_id: str
) -> None:
    """The untouched face stays untouched: the reveal form — the
    contextualized sentence W-5 did not edit — is still the canonical
    list's tail, and the bare formula precedes it."""

    store = ContentStore(built_content_db)
    try:
        view = store.get_teaching_content(target_id)
        assert isinstance(view, Ok), view
    finally:
        store.close()
    canonical = view.value.canonical_forms
    assert canonical[-1] == view.value.reveal_form
    assert canonical[0] != canonical[-1]
    assert canonical[0] == W5_KEY_FACE[target_id][0][0]


# ---------------------------------------------------------------------------
# ② the judging behavior: real evaluate_attempt over the real built key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", W5_TARGETS)
def test_the_bare_formula_judges_success_on_every_target(
    provider: ContentBackedTeachingTargetProvider, target_id: str
) -> None:
    """Each target's bare formula — the dogfood-observable production —
    judges SUCCESS through the real evaluator and the real built key."""

    key = _key_of(provider, target_id)
    evaluation = evaluate_attempt(W5_KEY_FACE[target_id][0][0], key)
    assert evaluation.outcome is AttemptOutcome.SUCCESS
    assert evaluation.basis == "CANONICAL_FORM_EXACT"
    assert evaluation.confidence == 1.0


def test_no_way_judges_the_dogfood_sentences(
    provider: ContentBackedTeachingTargetProvider,
) -> None:
    """The dogfood evidence replayed, case by case: the full-width
    exclamation attempt judges SUCCESS; the old canonical sentence keeps
    judging SUCCESS (monotonicity — the old accepted set is revoked
    nowhere); a slot-covering extra sentence is PARTIAL; a near miss is
    FAILURE; the empty attempt is ABSTAIN (never laundered)."""

    key = _key_of(provider, "res-pragmatic-no-way")
    fullwidth = evaluate_attempt("No way！", key)
    assert fullwidth.outcome is AttemptOutcome.SUCCESS
    old_sentence = evaluate_attempt(
        "No way! She actually moved to Lisbon?", key
    )
    assert old_sentence.outcome is AttemptOutcome.SUCCESS
    assert old_sentence.basis == "CANONICAL_FORM_EXACT"
    extra = evaluate_attempt("No way! let me go!", key)
    assert extra.outcome is AttemptOutcome.PARTIAL
    assert extra.basis == "REQUIRED_SLOT_COVERAGE"
    near_miss = evaluate_attempt("not way", key)
    assert near_miss.outcome is AttemptOutcome.FAILURE
    assert near_miss.basis == "NO_MATCH"
    empty = evaluate_attempt("", key)
    assert empty.outcome is AttemptOutcome.ABSTAIN
    assert empty.basis == "NO_ATTEMPT"


def test_got_it_judges_both_bare_variants_and_the_alternative(
    provider: ContentBackedTeachingTargetProvider,
) -> None:
    """got-it's three-form canonical: both bare variants judge SUCCESS, and
    the alternative realization keeps judging ALTERNATIVE_SUCCESS."""

    key = _key_of(provider, "res-pragmatic-got-it")
    assert evaluate_attempt("Got it", key).outcome is AttemptOutcome.SUCCESS
    assert evaluate_attempt("I got it", key).outcome is AttemptOutcome.SUCCESS
    alternative = evaluate_attempt(
        "Got it, thanks — I'll send the file tonight.", key
    )
    assert alternative.outcome is AttemptOutcome.ALTERNATIVE_SUCCESS
    assert alternative.basis == "ALTERNATIVE_REALIZATION_EXACT"


# ---------------------------------------------------------------------------
# ③ the audit record and the provenance derivation
# ---------------------------------------------------------------------------


def test_the_w5_audit_record_loads_and_approves_exactly_the_twelve() -> None:
    """The record carries the strict key set, a repo-unique id, and an
    approved list equal to the twelve W-5 targets; the build (the strict
    loader) accepted the directory — built_content_db exists."""

    record = json.loads(
        (CONTENT_SRC_DIR / "audits" / "w5-key-face-audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(record) == {
        "format",
        "format_version",
        "audit_id",
        "performed_by",
        "basis",
        "approved_entities",
    }
    assert record["format"] == "elc.content_src"
    assert record["format_version"] == 1
    assert record["audit_id"] == W5_AUDIT_ID
    assert record["performed_by"]
    assert "DEC-OPI-631452f9" in record["basis"]
    assert "保守加法" in record["basis"] or "conservative-addition" in (
        record["basis"]
    )
    assert tuple(record["approved_entities"]) == W5_TARGETS
    audit_ids = [
        json.loads(path.read_text(encoding="utf-8"))["audit_id"]
        for path in sorted((CONTENT_SRC_DIR / "audits").glob("*.json"))
    ]
    assert audit_ids.count(W5_AUDIT_ID) == 1
    assert len(audit_ids) == 4


def test_the_provenance_derivation_is_unchanged_by_the_w5_record(
    built_content_db: Path,
) -> None:
    """The twelve approved entities were all already inside the three prior
    records' union, so the derivation stands: 54 × AUTHOR_DECLARED + 46 ×
    EDITOR_REVIEWED, and the two unreachable words are produced by no
    default build."""

    levels = _provenance(built_content_db)
    assert len(levels) == 100
    assert sum(1 for v in levels.values() if v == "AUTHOR_DECLARED") == 54
    assert sum(1 for v in levels.values() if v == "EDITOR_REVIEWED") == 46
    assert "EXECUTABLY_VERIFIED" not in set(levels.values())
    assert "EMPIRICALLY_CALIBRATED" not in set(levels.values())


# ---------------------------------------------------------------------------
# ④ the corpus truth invariants
# ---------------------------------------------------------------------------


def test_the_readiness_table_still_reads_52_r4_48_r1_and_5_none(
    built_content_db: Path,
) -> None:
    """The W-5 key-face edit moves no §8.1 fact: the table stands."""

    table = _readiness_levels(built_content_db)
    assert len(table) == 105
    assert (
        sum(1 for v in table.values() if v == "R4_DETECTION_READY") == 52
    )
    assert (
        sum(1 for v in table.values() if v == "R1_LEXICALLY_RESOLVED") == 48
    )
    assert sum(1 for v in table.values() if v is None) == 5


def test_the_three_calibration100_floors_still_read_32_20_100(
    built_content_db: Path,
) -> None:
    """CORE_A 32, CORE_C 20, resource_count 100 — the declared reading
    (R3+ × core_utility band), unchanged by the key-face edit."""

    levels = _readiness_levels(built_content_db)
    conn = sqlite3.connect(str(built_content_db))
    try:
        utilities = {
            str(entity_id): str(band)
            for entity_id, band in conn.execute(
                "SELECT entity_id, core_utility FROM "
                "content_pedagogical_profile"
            ).fetchall()
        }
        resources = [
            str(row[0])
            for row in conn.execute(
                "SELECT entity_id FROM content_entity WHERE entity_id "
                "LIKE 'res-%'"
            )
        ]
    finally:
        conn.close()
    core = [
        t
        for t, level in levels.items()
        if t.startswith("res-")
        and level in ("R3_TEACHING_READY", "R4_DETECTION_READY")
    ]
    core_a = sum(1 for t in core if utilities.get(t) == "HIGH")
    core_c = sum(1 for t in core if utilities.get(t) in ("MEDIUM", "LOW"))
    assert core_a == 32
    assert core_c == 20
    assert len(resources) == 100


def test_the_credit_face_fixtures_and_default_ev_stand(
    built_content_db: Path,
) -> None:
    """51 REALIZES rows credit a capability, 595 fixture rows carry the
    three-word detection face, and the default-API build (no pilot
    registry) verifies nothing executably — EV = 0."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        realizes = conn.execute(
            "SELECT COUNT(*) FROM curriculum_link WHERE relation = 'REALIZES'"
        ).fetchone()[0]
        fixtures = conn.execute(
            "SELECT COUNT(*) FROM content_detection_fixture"
        ).fetchone()[0]
    finally:
        conn.close()
    assert realizes == 51
    assert fixtures == 595


# ---------------------------------------------------------------------------
# ⑤ the entity metadata face
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", W5_TARGETS)
def test_the_twelve_read_their_cut_metadata(
    built_content_db: Path, target_id: str
) -> None:
    """The metadata face, per cut: W-5 moved the twelve to revision 2 /
    content-w5, and v3-1 moved i-think on top of that (revision 3 /
    content-v31 — its key face was rewritten again by the slot-criterion
    cut)."""

    expected_revision = 3 if target_id == "res-hedge-i-think" else 2
    expected_version = (
        V31_UPDATED_IN_VERSION
        if target_id == "res-hedge-i-think"
        else W5_UPDATED_IN_VERSION
    )
    store = ContentStore(built_content_db)
    try:
        view = store.get_resource(target_id)
        assert isinstance(view, Ok), view
    finally:
        store.close()
    assert view.value.entity_revision == expected_revision
    assert view.value.created_in_version == "content-v1"
    assert view.value.updated_in_version == expected_version


def test_no_other_corpus_row_moved_revision_or_version(
    built_content_db: Path,
) -> None:
    """The metadata face moved exactly the W-5 twelve (revision 2 /
    content-w5; i-think 3 / content-v31), the v3-1 rewrite set
    (revision 2 / content-v31) and the v3-d inflection twelve
    (revision 3, 首触一件 carry-on / content-v3d): every entity outside those
    cuts keeps revision 1 and content-v1."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT entity_id, entity_revision, updated_in_version "
            "FROM content_entity"
        ).fetchall()
    finally:
        conn.close()
    for entity_id, revision, version in rows:
        name = str(entity_id)
        if name == "res-hedge-i-think":
            assert int(revision) == 3
            assert str(version) == V31_UPDATED_IN_VERSION
        elif name in V3D_INFLECTION_TARGETS:
            if name in V3D_FIRST_TOUCH_TARGETS:
                assert int(revision) == 2, name
            else:
                assert int(revision) == 3, name
            assert str(version) == V3D_UPDATED_IN_VERSION, name
        elif name in V31_REWRITE_TARGETS:
            assert int(revision) == 2, name
            assert str(version) == V31_UPDATED_IN_VERSION, name
        elif name in W5_TARGETS:
            assert int(revision) == 2, name
            assert str(version) == W5_UPDATED_IN_VERSION, name
        else:
            assert int(revision) == 1, name
            assert str(version) == "content-v1", name


def test_the_source_documents_carry_the_same_metadata_face() -> None:
    """The authoring tree and the artifact agree: the source documents
    declare the same cut metadata face (W-5 twelve; v3-1 sixty with
    i-think on top; v3-d inflection twelve on top of that), and no other
    document moved (a source-side leak of the metadata face would build a
    second-class truth)."""

    moved = []
    for path in sorted((CONTENT_SRC_DIR / "entities").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        entity = document["entity"]
        name = str(entity["entity_id"])
        if entity["entity_revision"] != 1 or (
            entity["updated_in_version"] != "content-v1"
        ):
            moved.append(name)
            if name == "res-hedge-i-think":
                assert entity["entity_revision"] == 3
                assert entity["updated_in_version"] == V31_UPDATED_IN_VERSION
            elif name in V3D_INFLECTION_TARGETS:
                if name in V3D_FIRST_TOUCH_TARGETS:
                    assert entity["entity_revision"] == 2, name
                else:
                    assert entity["entity_revision"] == 3, name
                assert (
                    entity["updated_in_version"] == V3D_UPDATED_IN_VERSION
                ), name
            elif name in V31_REWRITE_TARGETS:
                assert entity["entity_revision"] == 2, name
                assert (
                    entity["updated_in_version"] == V31_UPDATED_IN_VERSION
                ), name
            else:
                assert name in W5_TARGETS, name
                assert entity["entity_revision"] == 2, name
                assert entity["updated_in_version"] == W5_UPDATED_IN_VERSION, (
                    name
                )
    assert set(moved) == (
        set(W5_TARGETS) | set(V31_REWRITE_TARGETS) | set(V3D_INFLECTION_TARGETS)
    )
    # v3-d 随迁：71 → 72（W-5 十二 ∪ v3-1 四十九 ∪ v3-d 十二，i-think
    # 双刀去重；v3-d 的十件自 v3-1 名单移入、首触一件 carry-on 新入）。
    assert len(moved) == 72
