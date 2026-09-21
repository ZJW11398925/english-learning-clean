"""①/③ — the §8.1 readiness ladder: pinned, judged, and told the truth about.

Three things this file establishes, in that order:

- the ladder's own vocabulary (five levels, the level → fact-key table) is
  pinned against docs/PRODUCT_CONTRACT.md §8.1 and docs/DATA_MODEL.md §24.10
  as they are written, so a level or a required fact cannot drift silently;
- the judgement is exercised over synthetic fact bundles, one missing key at a
  time — including the requirement §24.10 adds beyond the level names: "R4
  必须包含可测试 detection policy/fixtures/false-positive boundary";
- the corpus's own read is computed from the built content.db and printed
  verbatim (`pytest -s`), the same evidence style the P5-0 probes use. The
  reading is not decorated: no target of this corpus is R4, and the print says
  which fact keys block the next level and why
  (elc.curriculum.store.UNREAD_FACT_EVIDENCE).
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from elc.content.build import SCHEMA_STATEMENTS
from elc.content.store import ContentStore, open_read_only
from elc.content.types import ReadinessLevel, supply_eligible
from elc.curriculum.readiness import (
    DECLARED_ABSENT_FACT_KEYS,
    DEFAULT_AVAILABILITY,
    LEVEL_ADDED_FACTS,
    READINESS_FACT_KEYS,
    READINESS_LEVELS,
    ReadinessAssessment,
    ReadinessFacts,
    judge_readiness,
    required_fact_keys,
)
from elc.curriculum.store import UNREAD_FACT_EVIDENCE, CurriculumContentStore
from elc.platform.types import Ok, ResourceId
from tests.phase5.conftest import (
    DOCS_ROOT,
    build_variant_artifact,
    canonical_lines,
)

FOCUS = "res-hedge-i-think"

#: The §8.1 facts beyond R1, grouped by the level that adds them.
R2_FACTS = (
    "curriculum_link",
    "pedagogical_profile",
    "goal_pack_overlay",
    "resource_labels",
)
R3_FACTS = (
    "reviewed_explanation",
    "example_policy",
    "contrast_or_usage",
    "typical_error_when_needed",
)
R4_FACTS = (
    "detection_policy",
    "recognition_rules",
    "negative_fixtures",
    "false_positive_boundaries",
)

#: §8.1 R1's four named things (P5-R: four separate facts, one per word).
R1_FACETS = ("pos", "sense", "basic_definition", "forms")

HEADING_8_1 = "## 8.1 Content Readiness（Normative）"
HEADING_24_10 = "### 24.10 Readiness"


def _facts(**present: bool) -> ReadinessFacts:
    """A fact bundle with exactly the named keys satisfied.

    The names are the fact keys themselves, so a test cannot satisfy a key
    that does not exist (the dataclass rejects it) — the same reason
    ``ReadinessFacts.present`` raises on an unknown key.
    """

    return ReadinessFacts(target_id="res-hedge-i-think", **present)


def _through(level: str, **extra: bool) -> ReadinessFacts:
    """A bundle satisfying every fact up to `level`, plus `extra`."""

    present = {key: True for key in required_fact_keys(level)}
    present.pop("typical_error_when_needed", None)
    present.update(extra)
    return _facts(**present)


def _section_text(doc: str, heading: str) -> str:
    """The raw text of one canonical section (the heading line excluded)."""

    lines = (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"heading {heading!r} not found in {doc}"
    collected: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level:
                break
        collected.append(line)
    return "\n".join(collected)


def _corpus_assessments(built_content_db: Path) -> tuple[ReadinessAssessment, ...]:
    """Every artifact target's assessment, in id order."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    return tuple(assessments.value)


def _corpus_table(
    built_content_db: Path,
) -> tuple[tuple[str, str | None, tuple[str, ...]], ...]:
    """(target, level, keys blocking the next level) for every artifact target."""

    return tuple(
        (assessment.target_id, assessment.level, assessment.missing_keys)
        for assessment in _corpus_assessments(built_content_db)
    )


# ---------------------------------------------------------------------------
# the vocabulary, pinned against the documents
# ---------------------------------------------------------------------------


def test_the_five_levels_are_the_canonical_words() -> None:
    assert READINESS_LEVELS == (
        "R0_INDEXED",
        "R1_LEXICALLY_RESOLVED",
        "R2_PLANNER_READY",
        "R3_TEACHING_READY",
        "R4_DETECTION_READY",
    )
    # One vocabulary, not two: the ladder re-reads the level type the content
    # domain already owns instead of re-typing the five words.
    assert READINESS_LEVELS == tuple(str(level) for level in ReadinessLevel)


@pytest.mark.parametrize(
    "doc,heading",
    (
        ("PRODUCT_CONTRACT.md", HEADING_8_1),
        ("DATA_MODEL.md", HEADING_24_10),
    ),
)
def test_both_canonical_documents_list_the_five_levels(
    doc: str, heading: str
) -> None:
    """The levels come from the documents, not from this module's memory."""

    block = canonical_lines(doc, heading, 0)
    named = tuple(
        "_".join(line.split()[:2]) for line in block if re.match(r"^R\d ", line)
    )
    assert named == READINESS_LEVELS


def test_section_24_10_requires_testable_detection_for_r4() -> None:
    """The one requirement §24.10 adds beyond the level names."""

    text = _section_text("DATA_MODEL.md", HEADING_24_10)
    assert (
        "R4 必须包含可测试 detection policy/fixtures/false-positive boundary"
        in text
    )
    # ... and PRODUCT_CONTRACT §8 forbids the cheap substitute for it.
    contract = _section_text("PRODUCT_CONTRACT.md", HEADING_8_1)
    assert "V1 不把“模型自称高置信”自动视为 R4 等价认证。" in contract


def test_the_level_to_fact_key_table_is_cumulative_and_complete() -> None:
    assert tuple(LEVEL_ADDED_FACTS) == READINESS_LEVELS
    flattened = tuple(
        key for level in READINESS_LEVELS for key in LEVEL_ADDED_FACTS[level]
    )
    assert len(set(flattened)) == len(flattened), "a fact key belongs to one level"
    for level in READINESS_LEVELS:
        assert required_fact_keys(level) == flattened[
            : len(required_fact_keys(level))
        ]
    # P5-R, strict reading: every declared fact key is *required* by exactly
    # one level — none sits outside the ladder as a silent exemption, and the
    # declared-absent keys are required like any other (that is what makes
    # the corpus's "no level at all" a report rather than a default).
    assert set(flattened) == set(READINESS_FACT_KEYS)
    assert set(DECLARED_ABSENT_FACT_KEYS) <= set(flattened)


def test_the_slash_list_operationalization_is_the_declared_one() -> None:
    """F-3, restated by P5-R: every separately named concept is one required
    fact — R1's four (POS / sense / basic definition / forms), R2's four,
    R4's four — and R0's third named item is required too (the strict
    conjunction; DECLARED_ABSENT no longer means "exempt")."""

    assert len(LEVEL_ADDED_FACTS["R1_LEXICALLY_RESOLVED"]) == 4
    assert len(LEVEL_ADDED_FACTS["R2_PLANNER_READY"]) == 4
    assert len(LEVEL_ADDED_FACTS["R4_DETECTION_READY"]) == 4
    assert DECLARED_ABSENT_FACT_KEYS == ("assessment_membership",)
    assert "assessment_membership" in required_fact_keys("R0_INDEXED")
    assert "assessment_membership" in READINESS_FACT_KEYS
    # The two spellings of a fold row are one value each (the P5-0 precedent):
    # §24.11 is enumerated in elc.content.types, not compounded here.
    from elc.content.types import LIFECYCLE_STATUSES

    assert "SENSE_RESOLVED" in LIFECYCLE_STATUSES
    assert "STRUCTURED" in LIFECYCLE_STATUSES
    assert "SENSE_RESOLVED / STRUCTURED" not in LIFECYCLE_STATUSES


def test_default_availability_is_the_canonical_default_block() -> None:
    contract = _section_text("PRODUCT_CONTRACT.md", HEADING_8_1)
    for phrase in (
        "不进入自动 Teaching Frontier",
        "Planner / probe 可用，默认不自动教学",
        "teach / review / transfer 可用",
        "automatic error-triggered teaching 可用",
    ):
        assert phrase in contract, phrase
    assert tuple(DEFAULT_AVAILABILITY) == READINESS_LEVELS
    # The empty tuple *is* the canonical "不进入自动 Teaching Frontier".
    assert DEFAULT_AVAILABILITY["R0_INDEXED"] == ()
    assert DEFAULT_AVAILABILITY["R1_LEXICALLY_RESOLVED"] == ()
    assert DEFAULT_AVAILABILITY["R2_PLANNER_READY"] == ("PLANNER", "PROBE")
    assert DEFAULT_AVAILABILITY["R3_TEACHING_READY"] == (
        "TEACH",
        "REVIEW",
        "TRANSFER",
    )
    assert DEFAULT_AVAILABILITY["R4_DETECTION_READY"] == (
        "AUTOMATIC_ERROR_TRIGGERED_TEACHING",
    )


def test_an_unknown_fact_key_fails_loudly() -> None:
    facts = ReadinessFacts(target_id="res-hedge-i-think")
    with pytest.raises(ValueError):
        facts.present("no_such_fact")


def test_the_ladder_reads_no_lifecycle_fact() -> None:
    """Readiness and supply are different axes (§8.1 vs §24.11): the fact
    bundle has no lifecycle field, so no level can be "supply eligibility" in
    disguise."""

    names = {field.name for field in dataclasses.fields(ReadinessFacts)}
    assert not names & {"lifecycle_status", "content_origin"}
    assert supply_eligible("CANONICAL_APPROVED") is True
    assert supply_eligible("REVIEW_REQUIRED") is False


# ---------------------------------------------------------------------------
# the judgement, one key at a time
# ---------------------------------------------------------------------------


def test_the_ladder_module_is_pure() -> None:
    """§8.1 judgement is a pure function of the fact bundle: the module has no
    IO surface at all (no database, no clock, no randomness, no filesystem)."""

    import ast

    from tests.conftest import SRC_ROOT

    path = SRC_ROOT / "curriculum" / "readiness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    forbidden = {"sqlite3", "time", "datetime", "random", "uuid", "secrets", "os"}
    assert not (imported & forbidden), imported & forbidden
    assert not (names & {"open", "connect", "read_text", "write_text"}), names
    # The only elc import is the vocabulary it re-reads, not a store.
    allowed = {"__future__", "dataclasses", "typing", "elc"}
    assert {module for module in imported if module not in allowed} == set()


def test_below_r0_is_no_level_at_all() -> None:
    assessment = judge_readiness(_facts())
    assert assessment.level is None
    assert assessment.next_level == "R0_INDEXED"
    assert assessment.missing_keys == (
        "entity_row",
        "canonical_form",
        "assessment_membership",
    )
    assert assessment.judgement("R0_INDEXED").reached is False


def test_r0_needs_all_three_named_things() -> None:
    """P5-R strict conjunction: "source / assessment membership / canonical
    form 可定位" — all three required, so two of three is no level."""

    assert judge_readiness(_facts(entity_row=True)).level is None
    assert judge_readiness(_facts(canonical_form=True)).level is None
    assert (
        judge_readiness(_facts(entity_row=True, canonical_form=True)).level
        is None
    ), "assessment_membership is required (P5-R)"
    assert (
        judge_readiness(
            _facts(
                entity_row=True,
                canonical_form=True,
                assessment_membership=True,
            )
        ).level
        == "R0_INDEXED"
    )


def test_r1_needs_the_four_named_lexical_facts() -> None:
    """"POS / sense / basic definition / forms 已可追溯" is four required
    facts, each of which is a fact and never a stand-in for the other three."""

    assert judge_readiness(_through("R0_INDEXED")).level == "R0_INDEXED"
    complete = _through(
        "R0_INDEXED",
        pos=True,
        sense=True,
        basic_definition=True,
        forms=True,
    )
    assert judge_readiness(complete).level == "R1_LEXICALLY_RESOLVED"
    for facet in R1_FACETS:
        bundle = dataclasses.replace(complete, **{facet: False})
        assessment = judge_readiness(bundle)
        assert assessment.level == "R0_INDEXED", facet
        assert assessment.next_level == "R1_LEXICALLY_RESOLVED"
        assert assessment.missing_keys == (facet,), facet
    # A bundle that carries everything *except* the four lexical facts (the
    # old entity-type shortcut's shape) reaches R0 at most.
    assert judge_readiness(_through("R0_INDEXED")).level == "R0_INDEXED"


@pytest.mark.parametrize("missing", R2_FACTS)
def test_r2_needs_all_four_planner_facts(missing: str) -> None:
    assert judge_readiness(_through("R2_PLANNER_READY")).level == "R2_PLANNER_READY"
    bundle = dataclasses.replace(_through("R2_PLANNER_READY"), **{missing: False})
    assessment = judge_readiness(bundle)
    assert assessment.level == "R1_LEXICALLY_RESOLVED"
    assert assessment.next_level == "R2_PLANNER_READY"
    assert assessment.missing_keys == (missing,)


@pytest.mark.parametrize("missing", R3_FACTS)
def test_r3_needs_explanation_example_policy_contrast_and_typical_error(
    missing: str,
) -> None:
    assert judge_readiness(_through("R3_TEACHING_READY")).level == "R3_TEACHING_READY"
    if missing == "typical_error_when_needed":
        # "以及需要时的 TypicalError": the key is conditional, so it drops the
        # level only once a source declares the need and the content is absent.
        bundle = dataclasses.replace(
            _through("R3_TEACHING_READY"),
            typical_error_required=True,
            typical_error=False,
        )
    else:
        bundle = dataclasses.replace(
            _through("R3_TEACHING_READY"), **{missing: False}
        )
    assessment = judge_readiness(bundle)
    assert assessment.level == "R2_PLANNER_READY"
    assert assessment.judgement("R3_TEACHING_READY").reached is False
    assert missing in assessment.missing_keys


def test_r3_needs_each_of_the_three_unconditional_keys() -> None:
    for key in ("reviewed_explanation", "example_policy", "contrast_or_usage"):
        bundle = dataclasses.replace(_through("R3_TEACHING_READY"), **{key: False})
        assert judge_readiness(bundle).level == "R2_PLANNER_READY", key


def test_typical_error_is_required_only_when_a_source_declares_the_need() -> None:
    no_need = dataclasses.replace(
        _through("R3_TEACHING_READY"),
        typical_error_required=False,
        typical_error=False,
    )
    assert judge_readiness(no_need).level == "R3_TEACHING_READY"
    needed_and_present = dataclasses.replace(
        _through("R3_TEACHING_READY"),
        typical_error_required=True,
        typical_error=True,
    )
    assert judge_readiness(needed_and_present).level == "R3_TEACHING_READY"
    needed_and_absent = dataclasses.replace(
        _through("R3_TEACHING_READY"),
        typical_error_required=True,
        typical_error=False,
    )
    assert judge_readiness(needed_and_absent).level == "R2_PLANNER_READY"


@pytest.mark.parametrize("missing", R4_FACTS)
def test_r4_needs_all_four_testable_detection_facts(missing: str) -> None:
    """§24.10: a detection policy alone is not R4 — the fixtures and the
    false-positive boundary are part of the level."""

    assert judge_readiness(_through("R4_DETECTION_READY")).level == "R4_DETECTION_READY"
    assessment = judge_readiness(
        dataclasses.replace(_through("R4_DETECTION_READY"), **{missing: False})
    )
    assert assessment.level == "R3_TEACHING_READY"
    assert assessment.next_level == "R4_DETECTION_READY"
    assert assessment.missing_keys == (missing,)
    assert assessment.detection_ready is False


def test_a_detection_policy_alone_does_not_reach_r4() -> None:
    assessment = judge_readiness(_through("R3_TEACHING_READY", detection_policy=True))
    assert assessment.level == "R3_TEACHING_READY"
    assert set(assessment.missing_keys) == {
        "recognition_rules",
        "negative_fixtures",
        "false_positive_boundaries",
    }


def test_the_assessment_answers_which_keys_support_which_level() -> None:
    assessment = judge_readiness(_through("R2_PLANNER_READY", detection_policy=True))
    r2 = assessment.judgement("R2_PLANNER_READY")
    assert r2.reached is True
    assert r2.satisfied_keys == r2.required_keys
    r4 = assessment.judgement("R4_DETECTION_READY")
    assert r4.reached is False
    # Every key is reported in its own level's order: the R0–R2 prefix, the
    # conditional TypicalError key (satisfied by the declared-absent need), and
    # the one R4 fact the bundle carries.
    assert r4.satisfied_keys == (
        *required_fact_keys("R2_PLANNER_READY"),
        "typical_error_when_needed",
        "detection_policy",
    )
    assert assessment.level == "R2_PLANNER_READY"
    assert assessment.next_level == "R3_TEACHING_READY"


# ---------------------------------------------------------------------------
# the corpus: computed, printed, and not decorated
# ---------------------------------------------------------------------------


def test_the_artifact_carries_no_table_for_the_unread_facts(
    built_content_db: Path,
) -> None:
    """The absent facts are absent because the artifact has no such table.

    Pinning the artifact's table set is what makes the readiness assembly's
    False defaults a *declared* gap rather than a hardcoded one: a build that
    adds a table carrying one of these facts fails here first.
    """

    declared = tuple(
        statement.split("(", 1)[0].split()[-1] for statement in SCHEMA_STATEMENTS
    )
    assert len(declared) == 11
    conn = open_read_only(built_content_db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    artifact_tables = tuple(str(row[0]) for row in rows)
    assert artifact_tables == tuple(sorted(declared))
    for table in artifact_tables:
        for word in (
            "pedagogical",
            "label",
            "overlay",
            "explanation",
            "typical_error",
            "detection",
            "fixture",
        ):
            assert word not in table, (
                f"artifact table {table!r} may carry a §8.1 fact this module"
                " reads as absent — revisit readiness_facts"
            )


def test_corpus_readiness_table_is_computed_and_printed(
    built_content_db: Path,
) -> None:
    """P5-R truth: the corpus reaches **no level**. §8.1 R0 requires the three
    named things and the artifact carries no assessment membership; R1's four
    lexical facts are absent too. The table prints the blocking keys so the
    reading is checkable rather than asserted."""

    table = _corpus_table(built_content_db)

    print("\n[readiness] target -> level -> keys blocking the next level")
    for target_id, level, missing in table:
        print(f"[readiness] {target_id:32} {level!s:22} {missing}")

    assert len(table) == 14
    for target_id, level, missing in table:
        assert level is None, (target_id, level)
        assert missing == ("assessment_membership",), (target_id, missing)


def test_no_corpus_target_is_detection_ready(built_content_db: Path) -> None:
    """不虚报: the corpus carries no detection fixtures, so no target reads R4."""

    for assessment in _corpus_assessments(built_content_db):
        assert assessment.level != "R4_DETECTION_READY", assessment.target_id
        r4 = assessment.judgement("R4_DETECTION_READY")
        assert r4.reached is False
        # R4 is cumulative: the four detection facts *and* everything below
        # them are reported missing for every corpus target.
        assert set(R4_FACTS) <= set(r4.missing_keys)


def test_the_corpus_missing_keys_are_exactly_the_unread_fact_evidence(
    built_content_db: Path,
) -> None:
    """Every key this corpus never satisfies has a named piece of missing
    evidence — the mapping is exhaustive, so "we did not read it" cannot hide
    behind "we did not need it".

    Three keys are missing for this corpus yet deliberately *not* counted as
    "never satisfied by design" here, and the equation below says why:
    ``typical_error`` is the raw §24.9 fact behind the conditional level key
    ``typical_error_when_needed`` (satisfied by a declared-absent need), and
    ``contrast_or_usage`` is read from §24.5 CONTRAST rows — a readable read
    path this corpus happens to carry no row for. ``lexical_resolution`` no
    longer exists at all: P5-R replaced it with §8.1 R1's four named facts,
    which are in the mapping like every other unread key. ``curriculum_link``
    is the one key that moved *into* the never-satisfied set in P5-R (the seed
    links are CURRICULUM_MAPPED, so no row is an approved mapping) while
    staying out of the unread mapping — the evidence is readable, it is the
    status that is not an approval.
    """

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
        never_present: set[str] = set()
        for assessment in assessments.value:
            for judgement in assessment.judgements:
                never_present |= set(judgement.missing_keys)
    finally:
        store.close()
    not_level_required = {"typical_error"}
    assert never_present == (
        set(UNREAD_FACT_EVIDENCE) - not_level_required
        | {"curriculum_link", "contrast_or_usage"}
    )
    for key, evidence in UNREAD_FACT_EVIDENCE.items():
        # `typical_error` is the raw §24.9 fact; the level key derived from it
        # is `typical_error_when_needed`.
        assert key in READINESS_FACT_KEYS or key == "typical_error"
        assert evidence
    assert "typical_error_when_needed" not in UNREAD_FACT_EVIDENCE
    assert "curriculum_link" not in UNREAD_FACT_EVIDENCE
    assert "contrast_or_usage" not in UNREAD_FACT_EVIDENCE
    # The five structurally unread keys (P5-R): R0's third item and R1's four.
    assert "assessment_membership" in UNREAD_FACT_EVIDENCE
    for facet in R1_FACETS:
        assert facet in UNREAD_FACT_EVIDENCE


def test_every_artifact_entity_is_an_expression(built_content_db: Path) -> None:
    """A corpus-shape fact that no longer carries an R1 reading (P5-R): all
    14 entities are EXPRESSION, and that is *not* why any target read R1 —
    entity type is not a readiness fact at all (see
    test_a_non_expression_entity_reads_the_same_no_level)."""

    store = ContentStore(built_content_db)
    try:
        types = {
            entity_id: store.get_resource(entity_id).value.entity_type
            for entity_id in store.entity_ids().value
        }
    finally:
        store.close()
    print(f"[f1] artifact entity types -> {sorted(set(types.values()))} ({len(types)})")
    assert set(types.values()) == {"EXPRESSION"}
    assert len(types) == 14


def test_a_non_expression_entity_reads_the_same_no_level(tmp_path: Path) -> None:
    """The old F-1 counterexample, now a no-op by construction: flipping one
    entity's §24.1 ``entity_type`` to ``SENSE`` changes nothing, because
    entity type is not a readiness fact any more (P5-R removed the
    equivalence). The variant still proves the read path runs on a
    non-EXPRESSION artifact row."""

    def edit(documents: dict, index: dict) -> None:
        del index
        documents[f"entities/{FOCUS}.json"]["entity"]["entity_type"] = "SENSE"

    artifact = build_variant_artifact(tmp_path, edit)
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(FOCUS)
        assert isinstance(facts, Ok), facts
        print(
            "[f1] SENSE entity -> entity_row="
            f"{facts.value.entity_row} canonical_form={facts.value.canonical_form}"
            f" pos={facts.value.pos} sense={facts.value.sense}"
            f" basic_definition={facts.value.basic_definition}"
            f" forms={facts.value.forms}"
        )
        assessment = supply.readiness(FOCUS)
        assert isinstance(assessment, Ok), assessment
        print(f"[f1] SENSE entity level -> {assessment.value.level}")
        for facet in R1_FACETS:
            assert getattr(facts.value, facet) is False, facet
        assert not hasattr(facts.value, "lexical_resolution")
        assert assessment.value.level is None
        assert assessment.value.next_level == "R0_INDEXED"
        assert assessment.value.missing_keys == ("assessment_membership",)
        # The entity is still resolvable and still readable: readiness is a
        # report, not an exclusion.
        assert isinstance(supply.get_resource(FOCUS), Ok)
        # Its siblings are untouched (and read the same no-level answer).
        sibling = supply.readiness("res-softener-kind-of")
        assert isinstance(sibling, Ok) and sibling.value.level is None
    finally:
        store.close()


def test_assessment_membership_is_required_and_absent(built_content_db: Path) -> None:
    """F-2, restated by P5-R: R0's third item is read, reported, **and
    required** — the strict conjunction. The strict reading is declared in
    the module rather than silently applied or silently skipped; the ∨
    reading is recorded there as the option that was not adopted."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(FOCUS)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(FOCUS)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    print(
        "[f2] assessment_membership -> "
        f"fact={facts.value.assessment_membership}"
        f" level={assessment.value.level}"
        " declared_absent=" + str(DECLARED_ABSENT_FACT_KEYS)
    )
    assert facts.value.assessment_membership is False
    assert "assessment_membership" in READINESS_FACT_KEYS
    assert "assessment_membership" in assessment.value.judgement(
        "R0_INDEXED"
    ).required_keys
    assert assessment.value.level is None
    assert assessment.value.missing_keys == ("assessment_membership",)
    assert "assessment_membership" in UNREAD_FACT_EVIDENCE


def test_no_corpus_target_carries_an_approved_curriculum_link(
    built_content_db: Path,
) -> None:
    """The corpus read one level down: the 9 RESOURCE targets carry a §24.7
    CurriculumLink row, and every row is ``CURRICULUM_MAPPED`` (P5-R) — so
    the R2 ``curriculum_link`` fact is False for all 14 targets, and the 5
    CAPABILITY nodes have no link row of their own (curriculum/README.md C1 —
    no self-link is invented)."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        linked: list[str] = []
        with_fact: list[str] = []
        for entity_id in store.entity_ids().value:
            facts = supply.readiness_facts(entity_id)
            assert isinstance(facts, Ok), facts
            assert isinstance(facts.value, ReadinessFacts)
            if facts.value.curriculum_link:
                with_fact.append(entity_id)
            links = supply.curriculum_links_of(ResourceId(entity_id))
            assert isinstance(links, Ok), links
            if links.value:
                linked.append(entity_id)
                assert all(
                    link.editorial_status == "CURRICULUM_MAPPED"
                    for link in links.value
                ), entity_id
        assert len(store.entity_ids().value) - len(linked) == 5
    finally:
        store.close()
    assert len(linked) == 9
    assert all(entity_id.startswith("res-") for entity_id in linked)
    assert with_fact == [], "no unapproved mapping may satisfy the R2 fact"


def test_an_approved_curriculum_link_is_an_r2_fact(tmp_path: Path) -> None:
    """The fact is not dead: an approved §24.7 mapping satisfies it. The
    canonical corpus carries none (CURRICULUM_MAPPED), hence the variant —
    and the row stays readable either way (unapproved ≠ deleted)."""

    def approve(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == FOCUS:
                row["editorial_status"] = "CANONICAL_APPROVED"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=approve)
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        changed = supply.readiness_facts(FOCUS)
        other = supply.readiness_facts("res-softener-kind-of")
        assert isinstance(changed, Ok), changed
        assert isinstance(other, Ok), other
        assert changed.value.curriculum_link is True
        assert other.value.curriculum_link is False
        assert other.value is not None
        # The link row itself is readable in the canonical corpus too.
        links = supply.curriculum_links_of(ResourceId("res-softener-kind-of"))
        assert isinstance(links, Ok) and len(links.value) == 1
        assert links.value[0].editorial_status == "CURRICULUM_MAPPED"
    finally:
        store.close()


def test_assessment_type_is_the_readiness_one() -> None:
    """A small structural pin: the judgement returns the module's own type."""

    assert isinstance(judge_readiness(_facts()), ReadinessAssessment)
