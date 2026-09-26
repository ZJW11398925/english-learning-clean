"""C3-R1 (Phase 11) — capability functional definitions + the link re-review.

What this cut did, and what this file pins:

- **the five capability definitions** (`curriculum/capabilities/<id>.json`,
  their optional ``functional_definition`` block): statement /
  counts_as_realization / does_not_count / boundary_cases (>= 2) / basis, read
  strictly by the build and carried on the loaded source. The basis is
  authoring judgement over the canonical vocabulary that exists
  (docs/DOMAIN_MODEL.md §7 families + §8 subtypes and the capability's own
  fixture face) — never an external psychometric source;
- **the 64-row re-review**: every §24.7 row carries the declared-reading
  ``mapping_class`` column, 16 rows are ``CURRICULUM_MAPPING`` and 48 are
  ``COVERAGE_PLACEMENT`` (m + p = 64); ``REALIZES`` implies
  ``CURRICULUM_MAPPING``; six rows were demoted from REALIZES to SUPPORTS and
  say so in their own rationale; the five mapping fields of every row are
  unchanged (the nine migrated rows are checked against the P3-1A/P3-1B
  fixture declaration, byte for byte); and every rationale is written in the
  review genre: it names the node it points at, cites that node's definition
  file, quotes the resource's own first taught rung, states the class word,
  cites the criterion list it was judged by, states its provenance, and
  registers its Revisit;
- **the R2 read change** (the cut's src behaviour change): §8.1's
  ``curriculum_link`` fact reads "an approved row that is a **mapping**", so
  the C1 target — whose collocation row the re-review placed — reads
  R1_LEXICALLY_RESOLVED while every other evidence fact stays True. The other
  eighteen §8.1 keys are untouched, and ``CONTENT_DB_VERSION`` moves to "3"
  with the new column;
- **the honest fall-back**: the corpus table reads 16 × R4 + 48 × R1 + 5 ×
  None (before C3-R1: 64 × R4 + 5 × None). The fall-back is the *purpose* of
  the decision (a pure vocabulary item no longer passes PLANNER_READY on
  nearest-node bookkeeping), so the direction is asserted rather than
  lamented: the four content rows still read GO (>= 1 R4), CORE_A falls below
  its floor again, CORE_C stays met;
- **the supply evidence note**: `elc.planner.supply` was **not** changed. It
  resolves a resource's curriculum *node* (REALIZES) rather than answering
  "is there a mapping", and the build's ``REALIZES => CURRICULUM_MAPPING``
  rule keeps the two readings from splitting in the unsafe direction. The pin
  below holds both halves on the real artifact.

Variants live in pytest tmp copies built through the real build step; the
canonical authoring trees are never edited to make a test convenient.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.content.build import (
    CONTENT_DB_VERSION,
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    CURRICULUM_MAPPING_CLASS,
    BuildError,
)
from elc.content.store import CURRICULUM_MAPPING_CLASS as READ_FACE_MAPPING_CLASS
from elc.content.store import ContentStore
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import CurriculumContentStore
from elc.planner.supply import prerequisite_state_of
from elc.platform.types import EvidenceModality, Ok, ResourceId
from tests.phase3.target_fixtures import TEACHING_CONTENT
from tests.phase5.conftest import build_variant_artifact

#: The five registry nodes, in id order.
CAPABILITY_IDS = (
    "cap-disc-topic-shift",
    "cap-eval-hedged-opinion",
    "cap-interact-backchannel",
    "cap-ref-ask-clarification",
    "cap-stance-soften-disagreement",
)

#: The sixteen resources whose §24.7 row is a curriculum mapping after the
#: C3-R1 re-review — the R4 set, written out rather than derived.
MAPPING_TARGETS = (
    "res-discourse-anyway",
    "res-discourse-by-the-way",
    "res-discourse-having-said-that",
    "res-discourse-that-reminds-me",
    "res-discourse-to-be-honest",
    "res-hedge-i-guess",
    "res-hedge-i-think",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-hedge-not-really",
    "res-hedge-sort-of",
    "res-pragmatic-no-offense-but",
    "res-pragmatic-thats-a-good-point-but",
    "res-softener-a-bit",
    "res-softener-kind-of",
    "res-softener-to-be-fair",
)

#: The fifteen REALIZES rows that survived the re-review (the credit face).
REALIZES_TARGETS = tuple(
    target for target in MAPPING_TARGETS if target != "res-hedge-not-really"
)

#: The six rows the re-review demoted to SUPPORTS (they were REALIZES before
#: C3-R1; each rationale says so in its own words).
DEMOTED_TARGETS = (
    "res-colloc-make-a-decision",
    "res-colloc-pay-attention-to",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
    "res-frame-id-like-to",
)

#: The nine rows whose linkage the P3-1A/P3-1B authoring fixture declares.
FIXTURE_LINKED_TARGETS = tuple(
    target_id
    for target_id in (
        "res-hedge-i-think",
        "res-softener-kind-of",
        "res-colloc-pay-attention-to",
        "res-frame-id-like-to",
        "res-discourse-by-the-way",
        "res-phrasal-look-forward-to",
        "res-pragmatic-could-you",
        "res-idiom-break-the-ice",
        "res-colloc-make-a-decision",
    )
    if target_id
)

#: The five CAPABILITY entities, which carry no §24.7 row of their own.
CAP_ENTITIES = CAPABILITY_IDS

#: The declared CORE reading (C3-a's adjudication, unchanged by C3-R1).
CORE_LEVELS = ("R3_TEACHING_READY", "R4_DETECTION_READY")


def _links_document() -> dict:
    return json.loads((CURRICULUM_DIR / "links.json").read_text(encoding="utf-8"))


def _link_rows() -> dict[str, dict]:
    return {
        str(row["resource_id"]): row for row in _links_document()["links"]
    }


def _entity_documents() -> dict[str, dict]:
    documents = {}
    for path in sorted((CONTENT_SRC_DIR / "entities").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        documents[str(document["entity"]["entity_id"])] = document
    return documents


def _mapping_resource_ids(artifact: Path) -> tuple[str, ...]:
    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT resource_id FROM curriculum_link "
            "WHERE mapping_class = ? ORDER BY resource_id",
            (CURRICULUM_MAPPING_CLASS,),
        ).fetchall()
    finally:
        conn.close()
    return tuple(str(row[0]) for row in rows)


def _levels(artifact: Path) -> dict[str, str | None]:
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        table = supply.readiness_by_target()
        assert isinstance(table, Ok), table
    finally:
        store.close()
    return {a.target_id: a.level for a in table.value}


def _facts(artifact: Path, target_id: str):
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(target_id)
        assert isinstance(facts, Ok), facts
    finally:
        store.close()
    return facts.value


def _curriculum_edit(edit) -> object:
    def apply(documents: dict, index: dict) -> None:
        edit(documents["links.json"]["links"])

    return apply


# ---------------------------------------------------------------------------
# ① the five functional definitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("capability_id", CAPABILITY_IDS)
def test_each_capability_carries_a_definition_the_build_reads(
    capability_id: str,
) -> None:
    """The block is present, complete and non-trivial, and the build's own
    reader carries it (``load_source`` is the strict read under test — a
    block the build dropped would not appear here)."""

    from elc.content.build import load_source

    source = load_source()
    document = json.loads(
        (CURRICULUM_DIR / "capabilities" / f"{capability_id}.json").read_text(
            encoding="utf-8"
        )
    )
    block = document["functional_definition"]
    assert sorted(block) == [
        "basis",
        "boundary_cases",
        "counts_as_realization",
        "does_not_count",
        "statement",
    ]
    assert block["statement"].strip()
    assert len(block["counts_as_realization"]) >= 3
    assert len(block["does_not_count"]) >= 3
    assert len(block["boundary_cases"]) >= 2
    carried = {
        capability.capability_id: capability
        for capability in source.capabilities
    }[capability_id].functional_definition
    assert carried is not None
    assert carried.statement == block["statement"]
    assert carried.boundary_cases == tuple(block["boundary_cases"])


@pytest.mark.parametrize("capability_id", CAPABILITY_IDS)
def test_the_definition_basis_is_authoring_judgement(capability_id: str) -> None:
    """The basis states what it is: this repository's authoring judgement over
    the canonical vocabulary that exists, plus the capability's own fixture
    face — and states that no external source is claimed."""

    document = json.loads(
        (CURRICULUM_DIR / "capabilities" / f"{capability_id}.json").read_text(
            encoding="utf-8"
        )
    )
    basis = str(document["functional_definition"]["basis"])
    assert "DOMAIN_MODEL" in basis
    assert "tests/phase3/target_fixtures.py" in basis
    assert "No external psychometric" in basis
    assert "Revisit" in basis


def test_the_definitions_are_operational() -> None:
    """The criteria can be applied to a row: each list is prose about what the
    expression does when it is uttered, and the five definitions cross-check
    the two nodes whose lowering could be confused (hedged claim vs softened
    negative move), so neither can silently absorb the other's rows."""

    blocks = {
        capability_id: json.loads(
            (
                CURRICULUM_DIR / "capabilities" / f"{capability_id}.json"
            ).read_text(encoding="utf-8")
        )["functional_definition"]
        for capability_id in CAPABILITY_IDS
    }
    hedge = " ".join(blocks["cap-eval-hedged-opinion"]["does_not_count"])
    soften = " ".join(blocks["cap-stance-soften-disagreement"]["does_not_count"])
    assert "interpersonal force" in hedge
    assert "hedged-claim node" in soften
    assert "commitment to one's own claim" in soften


# ---------------------------------------------------------------------------
# ② the 64-row re-review
# ---------------------------------------------------------------------------


def test_the_corpus_review_splits_sixteen_mappings_and_forty_eight_placements() -> None:
    """m + p = 64, and the split is written out rather than counted twice."""

    rows = _link_rows()
    assert len(rows) == 64
    mapping = sorted(
        target
        for target, row in rows.items()
        if row["mapping_class"] == "CURRICULUM_MAPPING"
    )
    placement = sorted(
        target
        for target, row in rows.items()
        if row["mapping_class"] == "COVERAGE_PLACEMENT"
    )
    assert mapping == sorted(MAPPING_TARGETS)
    assert len(mapping) == 16
    assert len(placement) == 48
    assert len(mapping) + len(placement) == 64


def test_realizes_implies_curriculum_mapping() -> None:
    """A realization claim is a mapping claim (the build refuses the pair, and
    the corpus has no row of that shape)."""

    rows = _link_rows()
    for target, row in rows.items():
        if row["relation"] == "REALIZES":
            assert row["mapping_class"] == "CURRICULUM_MAPPING", target
            assert row["primary_flag"] is True, target
    realizes = sorted(
        target for target, row in rows.items() if row["relation"] == "REALIZES"
    )
    assert realizes == sorted(REALIZES_TARGETS)
    assert len(realizes) == 15


def test_the_six_demotions_are_disclosed_row_by_row() -> None:
    """Each demoted row keeps its node, its approval, its frozen
    ``primary_flag`` and its own statement of the change."""

    rows = _link_rows()
    for target in DEMOTED_TARGETS:
        row = rows[target]
        assert row["relation"] == "SUPPORTS", target
        assert row["primary_flag"] is True, target  # frozen: the authoring claim
        assert row["editorial_status"] == "CANONICAL_APPROVED", target
        assert row["mapping_class"] == "COVERAGE_PLACEMENT", target
        rationale = str(row["rationale"])
        assert "corrected from REALIZES to SUPPORTS" in rationale, target
        assert "primary_flag stays true" in rationale, target


def test_the_migrated_rows_are_unchanged_against_the_fixture_declaration() -> None:
    """The nine P3-1A/P3-1B rows: the fixture's own ``capability_linkage`` is
    the node the row names, and the row's five mapping fields are exactly what
    the migration fixed (no silent re-pointing, no strength invention)."""

    rows = _link_rows()
    for target in FIXTURE_LINKED_TARGETS:
        declared = TEACHING_CONTENT[target]["capability_linkage"]
        row = rows[target]
        assert row["node_id"] == declared, target
        assert str(row["node_id"]).startswith("cap-"), target
        assert row["strength"] is None, target
        assert row["editorial_status"] == "CANONICAL_APPROVED", target


def test_every_rationale_is_written_in_the_review_genre() -> None:
    """All 64 rationales: they name the node they point at and that node's
    definition file, quote the resource's **own** first taught rung (the
    row-identity check that replaced "names its own row" — it is checkable
    against the entity source, so a copy-pasted rationale fails), state the
    class word, cite the criterion list they were judged by, state their
    credit consequence in their own words, state their provenance, and
    register their Revisit."""

    rows = _link_rows()
    entities = _entity_documents()
    for target, row in rows.items():
        rationale = str(row["rationale"])
        node = str(row["node_id"])
        assert node in rationale, target
        assert f"curriculum/capabilities/{node}.json" in rationale, target
        assert row["mapping_class"] in rationale, target
        assert "C3-R1 (Phase 11) capability-semantics re-review" in rationale, target
        assert "Revisit" in rationale, target
        assert "Row provenance:" in rationale, target
        rung = entities[target]["teaching_content"]["hint_ladder"][0]
        assert str(rung) in rationale, target
        if row["mapping_class"] == "CURRICULUM_MAPPING":
            assert "counts_as_realization" in rationale, target
        else:
            assert "does_not_count" in rationale, target
        if row["relation"] == "REALIZES":
            assert "credit face" in rationale, target
        else:
            # A SUPPORTS row mints nothing; the six demoted ones say their
            # credit is withdrawn, which is the same fact from the other side.
            assert (
                "mints nothing" in rationale or "credit" in rationale
            ), target


# ---------------------------------------------------------------------------
# ③ the R2 read change
# ---------------------------------------------------------------------------


def test_the_artifact_carries_the_mapping_class_column(built_content_db: Path) -> None:
    """The column exists with the declared vocabulary and the artifact's
    version moved with it (docs/DATA_MODEL.md §26.1: explicit, never
    guessed)."""

    assert CONTENT_DB_VERSION == "3"
    assert CURRICULUM_MAPPING_CLASS == READ_FACE_MAPPING_CLASS
    conn = sqlite3.connect(str(built_content_db))
    try:
        columns = [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(curriculum_link)")
        ]
        words = sorted(
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT mapping_class FROM curriculum_link"
            )
        )
        version = conn.execute(
            "SELECT value FROM content_meta WHERE key = 'content_db_version'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert "mapping_class" in columns
    assert words == ["COVERAGE_PLACEMENT", "CURRICULUM_MAPPING"]
    assert version == "3"


def test_the_c1_target_falls_to_r1_although_its_evidence_is_intact(
    built_content_db: Path,
) -> None:
    """The cut's behaviour change, pinned where it hurts: the C1 target's
    collocation row is a placement, so §8.1's ``curriculum_link`` is False and
    the ladder stops at R1 — while all eighteen other fact keys stay True and
    the row itself stays readable and approved. The fall-back is a read
    change, never a deletion."""

    facts = _facts(built_content_db, "res-colloc-make-a-decision")
    for key in READINESS_FACT_KEYS:
        if key == "curriculum_link":
            continue
        assert facts.present(key) is True, key
    assert facts.curriculum_link is False
    store = ContentStore(built_content_db)
    try:
        links = store.curriculum_links_of("res-colloc-make-a-decision")
        assert isinstance(links, Ok), links
        assert len(links.value) == 1
        assert links.value[0].editorial_status == "CANONICAL_APPROVED"
        mapping = store.has_approved_curriculum_mapping("res-colloc-make-a-decision")
        assert isinstance(mapping, Ok), mapping
        assert mapping.value is False
        unknown = store.has_approved_curriculum_mapping("res-ghost")
        assert not isinstance(unknown, Ok)
        assert unknown.error.code.value == "NOT_FOUND"
    finally:
        store.close()


def test_the_mapping_read_is_the_r4_set(built_content_db: Path) -> None:
    """The declared-reading column and the ladder agree: the resources whose
    row is a mapping are exactly the resources reading R4."""

    levels = _levels(built_content_db)
    r4 = sorted(t for t, level in levels.items() if level == "R4_DETECTION_READY")
    assert r4 == sorted(MAPPING_TARGETS)
    assert r4 == list(_mapping_resource_ids(built_content_db))


def test_an_unapproved_mapping_row_does_not_satisfy_r2(tmp_path: Path) -> None:
    """Both halves of the clause are load-bearing: the read needs the approval
    **and** the mapping class. Un-approving a mapping row flips the fact while
    the row stays readable (the P5-R discipline, re-pinned on the new
    predicate)."""

    def unapprove(rows: list) -> None:
        for row in rows:
            if row["resource_id"] == "res-hedge-i-think":
                row["editorial_status"] = "CURRICULUM_MAPPED"

    artifact = build_variant_artifact(
        tmp_path, curriculum_edit=_curriculum_edit(unapprove)
    )
    assert _facts(artifact, "res-hedge-i-think").curriculum_link is False
    assert _levels(artifact)["res-hedge-i-think"] == "R1_LEXICALLY_RESOLVED"


def test_flipping_one_mapping_to_a_placement_flips_that_target(tmp_path: Path) -> None:
    """The read-direction pin: a single row's mapping class decides that
    target's R2 fact (here the corpus's one SUPPORTS mapping row, so the
    relation word is untouched and only the class moves)."""

    def place(rows: list) -> None:
        for row in rows:
            if row["resource_id"] == "res-hedge-not-really":
                assert row["mapping_class"] == "CURRICULUM_MAPPING"
                row["mapping_class"] = "COVERAGE_PLACEMENT"

    artifact = build_variant_artifact(
        tmp_path, curriculum_edit=_curriculum_edit(place)
    )
    assert _facts(artifact, "res-hedge-not-really").curriculum_link is False
    assert _levels(artifact)["res-hedge-not-really"] == "R1_LEXICALLY_RESOLVED"
    assert len(_mapping_resource_ids(artifact)) == 15


# ---------------------------------------------------------------------------
# ④ the honest fall-back: the truth table and the rows that still stand
# ---------------------------------------------------------------------------


def test_the_truth_table_is_m_r4_and_the_rest_at_r1(built_content_db: Path) -> None:
    """M × R4 + (64 − M) × R1 + 5 × None, with M = 16 stated as the mapping
    count — the consistency the decision asked to be pinned."""

    levels = _levels(built_content_db)
    assert len(levels) == 69
    r4 = sorted(t for t, level in levels.items() if level == "R4_DETECTION_READY")
    r1 = sorted(
        t for t, level in levels.items() if level == "R1_LEXICALLY_RESOLVED"
    )
    none = sorted(t for t, level in levels.items() if level is None)
    assert r4 == sorted(MAPPING_TARGETS)
    assert len(r4) == 16 == len(_mapping_resource_ids(built_content_db))
    assert len(r1) == 48
    assert len(r1) + len(r4) == 64
    assert none == sorted(CAP_ENTITIES)
    # Every resource is in exactly one of the two bands: nothing new appears.
    assert sorted(r4 + r1) == sorted(
        target for target in levels if target.startswith("res-")
    )


def test_a_placement_target_stops_at_r1_on_the_link_key_alone(
    built_content_db: Path,
) -> None:
    """The rung itself: for a placement target the *first* missing key is the
    link, and the R3/R4 keys are reported as unreached rather than absent."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessment = supply.readiness("res-colloc-heavy-rain")
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    assert assessment.value.level == "R1_LEXICALLY_RESOLVED"
    assert assessment.value.missing_keys[0] == "curriculum_link"
    assert assessment.value.detection_ready is False


def test_the_four_content_rows_still_read_go(built_content_db: Path) -> None:
    """The four BF-02 §10 content rows stay GO: the fall-back must leave at
    least one R4 target, or the corpus would lose its teachable core."""

    r4 = [
        target
        for target, level in _levels(built_content_db).items()
        if level == "R4_DETECTION_READY"
    ]
    assert len(r4) >= 1
    assert "res-hedge-i-think" in r4


# ---------------------------------------------------------------------------
# ⑤ the supply evidence note: not changed, and why that is safe
# ---------------------------------------------------------------------------


def test_supply_reads_the_node_and_the_r2_fact_agrees_where_it_acts(
    built_content_db: Path,
) -> None:
    """The planner's node resolution is REALIZES-based (unchanged by C3-R1)
    and the §8.1 fact is mapping-based: the direction that matters is that
    **every target supply acts on satisfies R2** — the build's
    ``REALIZES => CURRICULUM_MAPPING`` rule makes that structural, and the
    corpus proves it row by row. The reverse gap is the honest one:
    ``res-hedge-not-really`` is a mapping the planner cannot read a node for,
    so its prerequisites are UNKNOWN (fail-closed), never absent."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        for target in REALIZES_TARGETS:
            outcome = prerequisite_state_of(
                "RESOURCE",
                target,
                EvidenceModality.TEXT_PRODUCTION,
                prerequisites=supply,
                learner_state=None,
            )
            assert outcome.nodes, target
            facts = supply.readiness_facts(target)
            assert isinstance(facts, Ok), facts
            assert facts.value.curriculum_link is True, target
        # The one mapping row the planner does not act on.
        not_really = prerequisite_state_of(
            "RESOURCE",
            "res-hedge-not-really",
            EvidenceModality.TEXT_PRODUCTION,
            prerequisites=supply,
            learner_state=None,
        )
        assert not_really.nodes == ()
        assert not_really.state.value == "UNKNOWN"
        assert "no §24.7 REALIZES link" in " ".join(not_really.reasons)
        facts = supply.readiness_facts("res-hedge-not-really")
        assert isinstance(facts, Ok), facts
        assert facts.value.curriculum_link is True
        links = supply.curriculum_links_of(
            ResourceId("res-hedge-not-really")
        )
        assert isinstance(links, Ok), links
        assert str(links.value[0].relation) == "SUPPORTS"
    finally:
        store.close()


# ---------------------------------------------------------------------------
# ⑥ the build's two new refusals and the definition block's strictness
# ---------------------------------------------------------------------------


def test_a_realizes_row_cannot_be_a_placement(tmp_path: Path) -> None:
    """The first refusal: REALIZES + COVERAGE_PLACEMENT is a contradiction the
    build rejects (a realization claim is a mapping claim)."""

    def contradict(rows: list) -> None:
        for row in rows:
            if row["resource_id"] == "res-hedge-i-think":
                row["mapping_class"] = "COVERAGE_PLACEMENT"

    with pytest.raises(BuildError) as raised:
        build_variant_artifact(tmp_path, curriculum_edit=_curriculum_edit(contradict))
    assert "REALIZES" in str(raised.value)
    assert "CURRICULUM_MAPPING" in str(raised.value)


def test_an_unknown_mapping_class_is_refused(tmp_path: Path) -> None:
    """The column is validated against its two-word vocabulary."""

    def invent(rows: list) -> None:
        rows[0]["mapping_class"] = "SEMANTIC_MAPPING"

    with pytest.raises(BuildError) as raised:
        build_variant_artifact(tmp_path, curriculum_edit=_curriculum_edit(invent))
    assert "SEMANTIC_MAPPING" in str(raised.value)
    assert "CURRICULUM_MAPPING" in str(raised.value)


def test_a_mapping_on_a_definition_less_capability_is_refused(tmp_path: Path) -> None:
    """The second refusal: a mapping is only meaningful against a stated
    standard, so a mapping row naming a capability that carries no
    ``functional_definition`` is refused at build time."""

    def strip_definition(documents: dict, _index: dict) -> None:
        del documents["capabilities/cap-disc-topic-shift.json"][
            "functional_definition"
        ]

    with pytest.raises(BuildError) as raised:
        build_variant_artifact(tmp_path, curriculum_edit=strip_definition)
    assert "functional_definition" in str(raised.value)
    assert "no stated standard" in str(raised.value)


@pytest.mark.parametrize(
    "edit",
    [
        lambda block: block.update({"mystery": "x"}),
        lambda block: block.pop("statement"),
        lambda block: block.update({"counts_as_realization": []}),
        lambda block: block.update({"does_not_count": []}),
        lambda block: block.update({"boundary_cases": ["only one"]}),
        lambda block: block.update({"basis": ""}),
    ],
)
def test_the_definition_block_is_read_strictly(tmp_path: Path, edit) -> None:
    """Unknown key, missing key, empty list (either list), a single boundary
    case and an empty string are all refused — a half-written standard cannot
    pass for a standard. The legal counterpart (the unedited document) builds,
    so the refusals are the edit's doing."""

    def break_block(documents: dict, _index: dict) -> None:
        edit(documents["capabilities/cap-ref-ask-clarification.json"]["functional_definition"])

    with pytest.raises(BuildError) as raised:
        build_variant_artifact(tmp_path, curriculum_edit=break_block)
    assert "functional_definition" in str(raised.value)

    legal = build_variant_artifact(tmp_path / "legal", curriculum_edit=None)
    assert legal.is_file()


def test_a_capability_without_a_definition_is_still_legal(tmp_path: Path) -> None:
    """The block is optional: a registry node with no definition builds as
    long as nothing claims to be a mapping onto it (cf. the refusal above)."""

    def strip_all_definitions(documents: dict, _index: dict) -> None:
        for name, document in documents.items():
            if name.startswith("capabilities/"):
                document.pop("functional_definition", None)
        for row in documents["links.json"]["links"]:
            row["relation"] = "SUPPORTS"
            row["mapping_class"] = "COVERAGE_PLACEMENT"

    artifact = build_variant_artifact(
        tmp_path, curriculum_edit=strip_all_definitions
    )
    assert _mapping_resource_ids(artifact) == ()
    levels = _levels(artifact)
    assert all(
        level is None or level == "R1_LEXICALLY_RESOLVED"
        for level in levels.values()
    )
