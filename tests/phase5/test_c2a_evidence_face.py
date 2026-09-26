"""C2-a (Phase 11) — eight more RESOURCE targets reach R4, and the credit
face widens from one approved §24.7 link to nine.

C1 built the §8.1 evidence face and pinned it (tests/phase5/
test_c1_evidence_face.py); C2-a authored the other eight RESOURCE targets'
evidence documents and approved their curriculum links. What this file pins,
in order:

- the eight C2-a targets read ``R4_DETECTION_READY`` with all nineteen §8.1
  keys present and no blocking key, per target (parametrized);
- the level is *entailed by the artifact*, not by the read face: for five
  independently-read fact families (R0 membership, the R1 lexical entry, the
  R2 curriculum link, the R3 TypicalError, the R4 fixtures), dropping that
  block in a variant source drops the level of the target the variant edits —
  each family named with the key that goes missing;
- the detection evidence of every authored document is paired as C1 pinned
  its own: every rule ordinal carries a fixture at the same ordinal, both
  declared fixture kinds are present, and every ``expected`` value is one of
  the two declared readings;
- the credit face widened with the approvals, read in both halves at C2-b's
  truth: the fifteen RESOURCE targets whose approved row is a ``REALIZES``
  row read the §24.7 node their link names through the one gate
  (``CAPABILITY_CREDIT_EDITORIAL_STATUS``), the thirteen whose approved row is
  a ``SUPPORTS`` row read ``None`` while their row stays readable, and the
  five CAPABILITY entities still read ``None`` — the same read, more rows;
- the volume gate's reading sentence: twenty-eight usable R4 targets against
  IP §13's Calibration100 floor of 100 — the number moved, the verdict
  (unmet) did not, and no opening claim is made here. IP §13's own first rung
  (28 resources) *is* met and is asserted separately from the three floors.

The canonical authoring trees are never edited: every variant lives in a
pytest tmp copy built through the real build step.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

import pytest

from elc.content.build import (
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok

#: The eight targets C2-a authored evidence for (C1's own target excluded).
C2A_TARGETS = (
    "res-colloc-pay-attention-to",
    "res-discourse-by-the-way",
    "res-frame-id-like-to",
    "res-hedge-i-think",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
    "res-softener-kind-of",
)

#: The nineteen targets C2-b authored as entities *and* as evidence documents
#: (it also approved their §24.7 links). Listed here so the corpus truth is
#: written out rather than derived from the artifact.
C2B_TARGETS = (
    "res-colloc-heavy-rain",
    "res-colloc-make-sense",
    "res-colloc-meet-a-deadline",
    "res-colloc-play-a-role",
    "res-colloc-take-part-in",
    "res-discourse-anyway",
    "res-discourse-to-be-honest",
    "res-frame-what-im-saying-is",
    "res-frame-would-you-mind",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-idiom-on-the-same-page",
    "res-idiom-piece-of-cake",
    "res-phrasal-come-up-with",
    "res-phrasal-figure-out",
    "res-phrasal-run-out-of",
    "res-pragmatic-sorry-to-interrupt",
    "res-pragmatic-thats-a-good-point-but",
    "res-softener-a-bit",
)

#: The twenty-eight RESOURCE targets, in id order (C1's, C2-a's eight and
#: C2-b's nineteen).
RES_TARGETS = ("res-colloc-make-a-decision", *C2A_TARGETS, *C2B_TARGETS)

#: The fifteen targets whose approved §24.7 link is a REALIZES row and
#: therefore credits a capability node on the credit face (C2-a's nine plus
#: C2-b's six).
CREDIT_TARGETS = (
    "res-colloc-make-a-decision",
    "res-colloc-pay-attention-to",
    "res-discourse-anyway",
    "res-discourse-by-the-way",
    "res-discourse-to-be-honest",
    "res-frame-id-like-to",
    "res-hedge-i-think",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
    "res-pragmatic-thats-a-good-point-but",
    "res-softener-a-bit",
    "res-softener-kind-of",
)

#: The thirteen targets whose single approved §24.7 row is a SUPPORTS row:
#: §8.1 R2-readable, credit-safe (the read filters relation = REALIZES).
SUPPORT_ONLY_TARGETS = tuple(
    target for target in RES_TARGETS if target not in CREDIT_TARGETS
)

CAP_TARGETS = (
    "cap-disc-topic-shift",
    "cap-eval-hedged-opinion",
    "cap-interact-backchannel",
    "cap-ref-ask-clarification",
    "cap-stance-soften-disagreement",
)

FIXTURE_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY")
EXPECTED_READINGS = ("NO_MATCH", "NO_MATCH_BOUNDARY")


def _evidence_variant(
    tmp_path: Path, target_id: str, edit: Callable[[dict], None]
) -> Path:
    """A copy of both authoring trees with one edit applied to one evidence
    document, built through the real build step.

    ``build_variant_artifact`` hands the *entity* documents to its callbacks;
    the readiness evidence lives in its own tree, so this file carries the
    two-line-local variant builder instead of widening the shared helper.
    """

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    path = content_src / "evidence" / f"{target_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


def _level_and_missing(
    artifact: Path, target_id: str
) -> tuple[str | None, tuple[str, ...]]:
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        assessment = supply.readiness(target_id)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    return assessment.value.level, assessment.value.missing_keys


# ---------------------------------------------------------------------------
# ① the eight new targets, one by one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", C2A_TARGETS)
def test_each_c2a_target_satisfies_all_nineteen_keys_and_reads_r4(
    built_content_db: Path, target_id: str
) -> None:
    """Per target: every §8.1 key present (eighteen read from their own tables,
    ``entity_row`` proven by the preceding ``get_resource`` success) and the
    level is the top rung with nothing blocking the next one."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(target_id)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(target_id)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    for key in READINESS_FACT_KEYS:
        assert facts.value.present(key) is True, (target_id, key)
    assert assessment.value.level == "R4_DETECTION_READY", target_id
    assert assessment.value.next_level is None, target_id
    assert assessment.value.missing_keys == (), target_id
    assert assessment.value.detection_ready is True, target_id


# ---------------------------------------------------------------------------
# ② the level is entailed by the artifact: five fact families, five variants
# ---------------------------------------------------------------------------


def test_dropping_the_membership_row_drops_the_target_below_r0(
    tmp_path: Path,
) -> None:
    """R0's third named thing, read strictly: without the §24.8 row the target
    has no level at all — §8.1 has no word below R0."""

    def drop(document: dict) -> None:
        del document["assessment_membership"]

    artifact = _evidence_variant(tmp_path, "res-pragmatic-could-you", drop)
    level, missing = _level_and_missing(artifact, "res-pragmatic-could-you")
    assert level is None
    assert missing == ("assessment_membership",)


def test_dropping_the_lexical_entry_drops_the_target_to_r0(
    tmp_path: Path,
) -> None:
    """R1's ``pos`` fact is its own evidence: the four R1 keys are read
    separately, so losing the entry row costs exactly that key."""

    def drop(document: dict) -> None:
        del document["lexical_entry"]

    artifact = _evidence_variant(tmp_path, "res-phrasal-look-forward-to", drop)
    level, missing = _level_and_missing(artifact, "res-phrasal-look-forward-to")
    assert level == "R0_INDEXED"
    assert missing == ("pos",)


def test_demoting_the_link_drops_the_target_to_r1(tmp_path: Path) -> None:
    """R2's ``curriculum_link`` reads the §24.7 status, not the row: demoting
    the approved link to ``CURRICULUM_MAPPED`` costs the level the row was
    carrying, while the row itself stays readable."""

    from tests.phase5.conftest import build_variant_artifact

    def demote(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == "res-frame-id-like-to":
                row["editorial_status"] = "CURRICULUM_MAPPED"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=demote)
    level, missing = _level_and_missing(artifact, "res-frame-id-like-to")
    assert level == "R1_LEXICALLY_RESOLVED"
    assert missing == ("curriculum_link",)


def test_a_declared_error_need_without_rows_drops_the_target_to_r2(
    tmp_path: Path,
) -> None:
    """§8.1 R3's "以及需要时的 TypicalError" is a source declaration: the need
    stays declared while the rows are gone, so the key is unsatisfied and the
    target stops one rung lower."""

    def drop(document: dict) -> None:
        assert document["typical_error_required"] is True
        del document["typical_errors"]

    artifact = _evidence_variant(tmp_path, "res-idiom-break-the-ice", drop)
    level, missing = _level_and_missing(artifact, "res-idiom-break-the-ice")
    assert level == "R2_PLANNER_READY"
    assert missing == ("typical_error_when_needed",)


def test_dropping_the_fixtures_keeps_r3_and_loses_r4(tmp_path: Path) -> None:
    """R4's four facts are read separately and cumulative: without the
    fixture rows the target keeps the teaching rungs and loses both fixture
    keys — and the two surviving R4 keys are not enough to hold the level."""

    def drop(document: dict) -> None:
        del document["detection_fixtures"]

    artifact = _evidence_variant(tmp_path, "res-softener-kind-of", drop)
    level, missing = _level_and_missing(artifact, "res-softener-kind-of")
    assert level == "R3_TEACHING_READY"
    assert missing == ("negative_fixtures", "false_positive_boundaries")


# ---------------------------------------------------------------------------
# ③ the detection evidence of every authored document is paired
# ---------------------------------------------------------------------------


def test_every_authored_documents_detection_evidence_is_paired(
    built_content_db: Path,
) -> None:
    """§24.10's "可测试" read as the corpus's own self-constraint: every rule
    ordinal carries a fixture at the same ordinal, both declared fixture kinds
    are present, and every ``expected`` value is one of the two declared
    readings — checked document by document, so an unpaired rule in any of the
    nine fails here rather than only for C1's target."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        rules = conn.execute(
            "SELECT entity_id, ordinal FROM content_detection_rule "
            "ORDER BY entity_id, ordinal"
        ).fetchall()
        fixtures = conn.execute(
            "SELECT entity_id, ordinal, kind, text, expected "
            "FROM content_detection_fixture ORDER BY entity_id, ordinal"
        ).fetchall()
        policies = [
            row[0]
            for row in conn.execute(
                "SELECT entity_id FROM content_detection_policy"
            )
        ]
    finally:
        conn.close()
    rule_ordinals: dict[str, list[int]] = {}
    for entity_id, ordinal in rules:
        rule_ordinals.setdefault(str(entity_id), []).append(int(ordinal))
    fixture_ordinals: dict[str, list[int]] = {}
    kinds: dict[str, set[str]] = {}
    for entity_id, ordinal, kind, text, expected in fixtures:
        assert text, (entity_id, ordinal)
        assert str(expected) in EXPECTED_READINGS, (entity_id, expected)
        assert str(kind) in FIXTURE_KINDS, (entity_id, kind)
        # the pair, not just each side: a NEGATIVE fixture reads NO_MATCH and
        # a FALSE_POSITIVE_BOUNDARY fixture reads NO_MATCH_BOUNDARY (c2-a
        # review F4 — kind and expected are two spellings of one reading).
        assert (str(kind), str(expected)) in (
            ("NEGATIVE", "NO_MATCH"),
            ("FALSE_POSITIVE_BOUNDARY", "NO_MATCH_BOUNDARY"),
        ), (entity_id, ordinal, kind, expected)
        fixture_ordinals.setdefault(str(entity_id), []).append(int(ordinal))
        kinds.setdefault(str(entity_id), set()).add(str(kind))
    assert sorted(rule_ordinals) == sorted(RES_TARGETS)
    assert sorted(policies) == sorted(RES_TARGETS)
    for target_id in RES_TARGETS:
        assert set(rule_ordinals[target_id]) == set(
            fixture_ordinals[target_id]
        ), target_id
        assert kinds[target_id] == set(FIXTURE_KINDS), target_id


# ---------------------------------------------------------------------------
# ④ the credit face widened: nine approved rows, five entities without one
# ---------------------------------------------------------------------------


def test_the_credit_face_reads_the_fifteen_approved_realizes_nodes(
    built_content_db: Path,
) -> None:
    """The behavior change, stated as a read — now in two halves. With all
    twenty-eight §24.7 rows approved, **fifteen** RESOURCE targets (C2-a's
    nine plus C2-b's six REALIZES rows) carry the node their link names in
    their teaching payload (this is what an ``ALTERNATIVE_SUCCESS`` attempt
    can credit), the provider view agrees; the **thirteen** targets whose
    single approved row is a ``SUPPORTS`` row read ``None`` on the credit
    face while their row stays fully readable — the credit-safe direction
    C2-b introduced; and the five CAPABILITY entities — no link row of their
    own — still read ``None``."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        for target_id in RES_TARGETS:
            links = supply.curriculum_links_of(target_id)
            assert isinstance(links, Ok), links
            assert len(links.value) == 1, target_id
            node = str(links.value[0].node_id)
            relation = str(links.value[0].relation)
            assert relation in ("REALIZES", "SUPPORTS"), target_id
            teaching = supply.get_teaching_content(target_id)
            assert isinstance(teaching, Ok), teaching
            if target_id in CREDIT_TARGETS:
                assert relation == "REALIZES", target_id
                assert teaching.value.capability_linkage == node, target_id
            else:
                assert relation == "SUPPORTS", target_id
                assert teaching.value.capability_linkage is None, target_id
        for target_id in CAP_TARGETS:
            teaching = supply.get_teaching_content(target_id)
            assert isinstance(teaching, Ok), teaching
            assert teaching.value.capability_linkage is None, target_id
    finally:
        store.close()

    assert len(CREDIT_TARGETS) == 15
    assert len(SUPPORT_ONLY_TARGETS) == 13

    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        for target_id in CREDIT_TARGETS:
            view = provider.resolve("RESOURCE", target_id)
            assert isinstance(view, Ok), view
            assert view.value.capability_linkage is not None, target_id
        for target_id in SUPPORT_ONLY_TARGETS:
            view = provider.resolve("RESOURCE", target_id)
            assert isinstance(view, Ok), view
            assert view.value.capability_linkage is None, target_id
    finally:
        provider.close()


# ---------------------------------------------------------------------------
# ⑤ the volume gate's reading sentence moved, its verdict did not
# ---------------------------------------------------------------------------


def test_the_index_lists_the_twenty_eight_evidence_documents_in_entity_order() -> None:
    """The source-side half of "the corpus states evidence for every RESOURCE
    target": the index's ``evidence`` list names exactly the twenty-eight
    documents, in the same order the ``entities`` list carries them
    (content_src/README.md "文件布局"), and the CAPABILITY entities are absent
    from it by decision (their ``None`` level is constructive)."""

    index = json.loads(
        (CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8")
    )
    entities = [str(entry) for entry in index["entities"]]
    expected = [
        entry.replace("entities/", "evidence/")
        for entry in entities
        if entry.startswith("entities/res-")
    ]
    assert index["evidence"] == expected
    assert len(expected) == 28
    for listed in index["evidence"]:
        assert (CONTENT_SRC_DIR / listed).is_file(), listed
    assert len(entities) == 33
    # The order rule, stated positively: both lists are plain id order, which
    # is what "the same order as the entities list" means here.
    assert entities == sorted(entities)
    assert index["evidence"] == sorted(index["evidence"])


def test_the_calibration100_reading_moves_and_the_verdict_does_not(
    built_content_db: Path,
) -> None:
    """The numbers the rollout HOLD rests on, read from both sides: the
    artifact now answers twenty-eight detection-ready resource targets out of
    thirty-three entities (旧真值: one of fourteen; C2-a: nine of fourteen),
    while the floors IP §13 states are 100 / 30 / 2 — so every one of them is
    still unmet and nothing here is an opening claim. IP §13's own starting
    number is 28, and the RESOURCE count now *is* 28: that is the first rung
    of "28 → 100", not a Calibration100 pass, and the two readings are
    asserted separately so the two spellings cannot drift apart."""

    plan_text = (
        Path(__file__).resolve().parents[2] / "docs" / "IMPLEMENTATION_PLAN.md"
    ).read_text(encoding="utf-8")
    gates = {
        name: int(re.search(rf"{re.escape(name)} >= (\d+)", plan_text).group(1))
        for name in ("resource_count", "CORE_A", "CORE_C")
    }
    assert gates == {"resource_count": 100, "CORE_A": 30, "CORE_C": 2}
    # IP §13's first rung, read out of the document rather than re-typed.
    assert re.search(r"28 → 100 resource calibration", plan_text)

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        table = supply.readiness_by_target()
        assert isinstance(table, Ok), table
        ready = [
            assessment.target_id
            for assessment in table.value
            if assessment.level == "R4_DETECTION_READY"
        ]
    finally:
        store.close()
    conn = sqlite3.connect(str(built_content_db))
    try:
        resources = [
            row[0]
            for row in conn.execute(
                "SELECT entity_id FROM content_entity ORDER BY entity_id"
            )
        ]
        families = dict(
            conn.execute(
                "SELECT family, COUNT(*) FROM curriculum_capability GROUP BY family"
            ).fetchall()
        )
    finally:
        conn.close()
    res_rows = [
        entity_id for entity_id in resources if str(entity_id).startswith("res-")
    ]
    assert len(ready) == 28
    assert sorted(ready) == res_rows
    assert len(res_rows) == 28  # the IP §13 first rung: 28 resources
    assert len(resources) == 33
    print(
        f"[c2b] calibration reading -> {len(ready)}/{gates['resource_count']} "
        f"resources ({len(ready)} R4 of {len(resources)} entities;"
        f" IP §13 first rung = 28)"
    )
    assert len(ready) >= 28  # the first rung, met
    assert len(ready) < gates["resource_count"]
    assert len(res_rows) < gates["resource_count"]
    assert families.get("CORE_A", 0) < gates["CORE_A"]
    assert families.get("CORE_C", 0) < gates["CORE_C"]
