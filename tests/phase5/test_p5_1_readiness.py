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

#: An entity whose source states no readiness evidence at all. C1 and C2-a
#: authored an evidence document for every RESOURCE target, so the
#: evidence-less class is the five CAPABILITY entities: no `evidence/`
#: document, no §24.7 link row of their own, hence no level — the honest
#: specimen for "the artifact carries nothing" that the zero-side pins read.
NO_EVIDENCE_ENTITY = "cap-disc-topic-shift"

#: The sixty-four RESOURCE targets, in id order — every one of them states all
#: nineteen §8.1 facts in its own evidence document (C1 authored one, C2-a
#: eight, C2-b nineteen with their entities, C3-a eighteen of its cut and
#: C3-b the last eighteen), and the list is written out rather than derived
#: from the artifact, so a source that loses a document fails here instead of
#: quietly shrinking the expected set. **C3-R1 moved their *level*, not their
#: evidence**: the sixteen whose §24.7 row is a curriculum mapping read R4,
#: the other forty-eight are coverage placements and read R1 (their link is
#: the first missing key). The split is written out in ``MAPPING_TARGETS``.
RESOURCE_TARGETS = (
    "res-colloc-come-to-a-conclusion",
    "res-colloc-draw-attention-to",
    "res-colloc-have-an-effect-on",
    "res-colloc-heavy-rain",
    "res-colloc-keep-in-mind",
    "res-colloc-make-a-decision",
    "res-colloc-make-an-effort",
    "res-colloc-make-progress",
    "res-colloc-make-sense",
    "res-colloc-meet-a-deadline",
    "res-colloc-pay-attention-to",
    "res-colloc-play-a-role",
    "res-colloc-raise-awareness",
    "res-colloc-save-time",
    "res-colloc-take-a-look",
    "res-colloc-take-advantage-of",
    "res-colloc-take-part-in",
    "res-discourse-anyway",
    "res-discourse-by-the-way",
    "res-discourse-having-said-that",
    "res-discourse-in-fact",
    "res-discourse-long-story-short",
    "res-discourse-that-reminds-me",
    "res-discourse-to-be-honest",
    "res-frame-id-like-to",
    "res-frame-if-you-dont-mind",
    "res-frame-just-wondering",
    "res-frame-lets-say",
    "res-frame-the-thing-is",
    "res-frame-what-im-saying-is",
    "res-frame-would-you-mind",
    "res-hedge-i-guess",
    "res-hedge-i-mean",
    "res-hedge-i-think",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-hedge-not-really",
    "res-hedge-sort-of",
    "res-idiom-a-blessing-in-disguise",
    "res-idiom-break-the-ice",
    "res-idiom-hit-the-nail-on-the-head",
    "res-idiom-on-the-same-page",
    "res-idiom-piece-of-cake",
    "res-idiom-the-ball-is-in-your-court",
    "res-idiom-under-the-weather",
    "res-phrasal-bring-up",
    "res-phrasal-carry-on",
    "res-phrasal-come-up-with",
    "res-phrasal-figure-out",
    "res-phrasal-give-up",
    "res-phrasal-look-forward-to",
    "res-phrasal-put-off",
    "res-phrasal-run-out-of",
    "res-phrasal-turn-out",
    "res-phrasal-work-out",
    "res-pragmatic-could-i-ask",
    "res-pragmatic-could-you",
    "res-pragmatic-no-offense-but",
    "res-pragmatic-sorry-to-interrupt",
    "res-pragmatic-thats-a-good-point-but",
    "res-softener-a-bit",
    "res-softener-if-anything",
    "res-softener-kind-of",
    "res-softener-to-be-fair",
)

#: The five CAPABILITY entities, in id order: no evidence document, no link
#: row of their own, no level.
NO_LEVEL_TARGETS = (
    "cap-disc-topic-shift",
    "cap-eval-hedged-opinion",
    "cap-interact-backchannel",
    "cap-ref-ask-clarification",
    "cap-stance-soften-disagreement",
)

#: The sixteen RESOURCE targets whose §24.7 row is a curriculum mapping after
#: C3-R1 — the R4 half of the corpus, written out rather than derived.
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

#: The other forty-eight: the same evidence, a coverage-placement link.
PLACEMENT_TARGETS = tuple(
    target for target in RESOURCE_TARGETS if target not in MAPPING_TARGETS
)

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
    # declared-absent keys are required like any other (P5-R history: that is
    # what made the corpus's then-"no level at all" a report rather than a
    # default; since C1 the mapping is empty and the report is artifact-driven).
    assert set(flattened) == set(READINESS_FACT_KEYS)
    assert set(DECLARED_ABSENT_FACT_KEYS) <= set(flattened)


def test_the_slash_list_operationalization_is_the_declared_one() -> None:
    """F-3, restated by P5-R: every separately named concept is one required
    fact — R1's four (POS / sense / basic definition / forms), R2's four,
    R4's four — and R0's third named item is required too (the strict
    conjunction). C1 (Phase 11) emptied DECLARED_ABSENT_FACT_KEYS: every
    §8.1 fact key now has an evidence table, so nothing is exempt *and*
    nothing is unread — the strictness is unchanged, its carrier is not."""

    assert len(LEVEL_ADDED_FACTS["R1_LEXICALLY_RESOLVED"]) == 4
    assert len(LEVEL_ADDED_FACTS["R2_PLANNER_READY"]) == 4
    assert len(LEVEL_ADDED_FACTS["R4_DETECTION_READY"]) == 4
    # 旧真值 → 新真值（C1）: ("assessment_membership",) → () — the key's
    # evidence table exists now (content_assessment_membership), so the
    # declared-absent mechanism has nothing left to declare.
    assert DECLARED_ABSENT_FACT_KEYS == ()
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


def test_every_readiness_fact_key_has_a_carrier_table_in_the_artifact(
    built_content_db: Path,
) -> None:
    """The positive successor of the deleted name-word scan (旧真值: 11
    tables, no §8.1 fact table, facts read absent by construction; 新真值
    C1: 24 tables, every §8.1 fact key's evidence carried).

    The artifact's table set is exactly ``SCHEMA_STATEMENTS``, and every
    §8.1 fact key this module reads names the table(s) that carry it — so a
    build that drops a carrier fails here first, and "this fact cannot be
    read" can never come back as a silent default.
    """

    declared = tuple(
        statement.split("(", 1)[0].split()[-1] for statement in SCHEMA_STATEMENTS
    )
    assert len(declared) == 24
    conn = open_read_only(built_content_db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    artifact_tables = tuple(str(row[0]) for row in rows)
    assert artifact_tables == tuple(sorted(declared))
    # One carrier (or carrier pair) per §8.1 fact key, spelled out — the
    # same mapping readiness_facts reads through evidence_counts().
    carriers: dict[str, tuple[str, ...]] = {
        "entity_row": ("content_entity",),
        "canonical_form": ("content_example",),
        "assessment_membership": ("content_assessment_membership",),
        "pos": ("content_lexical_entry",),
        "sense": ("content_sense",),
        "basic_definition": ("content_text",),
        "forms": ("content_form",),
        "curriculum_link": ("curriculum_link",),
        "pedagogical_profile": ("content_pedagogical_profile",),
        "goal_pack_overlay": ("content_pack_overlay",),
        "resource_labels": ("content_resource_label",),
        # C1 disposition F7c: the fact reads the note row *and* the entity's
        # §24.11 lifecycle_status (content_entity), so both carriers are named.
        "reviewed_explanation": ("content_text", "content_entity"),
        "example_policy": ("content_example_policy",),
        "contrast_or_usage": ("content_example", "content_resource_label"),
        "typical_error_when_needed": ("content_typical_error", "content_meta"),
        "detection_policy": ("content_detection_policy",),
        "recognition_rules": ("content_detection_rule",),
        "negative_fixtures": ("content_detection_fixture",),
        "false_positive_boundaries": ("content_detection_fixture",),
    }
    assert set(carriers) == set(READINESS_FACT_KEYS)
    for key, tables in carriers.items():
        for table in tables:
            assert table in artifact_tables, (key, table)


def test_corpus_readiness_table_is_computed_and_printed(
    built_content_db: Path,
) -> None:
    """P5-R truth, now driven by the artifact instead of by missing tables
    (C1, then C2-a, then C2-b, then C3-a, then C3-b): the five CAPABILITY
    entities state
    no evidence and read no level, blocked at R0 by ``assessment_membership``;
    the sixty-four RESOURCE targets — C1's authored document, C2-a's eight,
    C2-b's nineteen, C3-a's eighteen and C3-b's eighteen — state all nineteen
    facts, and their *level* is then decided by the link's C3-R1 mapping
    class: sixteen read ``R4_DETECTION_READY`` and the other forty-eight read
    ``R1_LEXICALLY_RESOLVED`` with ``curriculum_link`` as the first key
    blocking the next level. The table prints the blocking keys so the reading
    is checkable rather than asserted."""

    table = _corpus_table(built_content_db)

    print("\n[readiness] target -> level -> keys blocking the next level")
    for target_id, level, missing in table:
        print(f"[readiness] {target_id:32} {level!s:22} {missing}")

    assert len(table) == 69
    levels = {(target, missing): level for target, level, missing in table}
    # 旧真值 → 新真值（C1: 1×R4+13×None；C2-a: 9×R4+5×None；C2-b:
    # 28×R4+5×None；C3-a: 46×R4+5×None；C3-b: 64×R4+5×None；C3-R1:
    # 16×R4 + 48×R1 + 5×None）.
    assert levels[("res-hedge-i-think", ())] == "R4_DETECTION_READY"
    assert (
        levels[("res-colloc-make-a-decision", ("curriculum_link",))]
        == "R1_LEXICALLY_RESOLVED"
    )
    for (target_id, missing), level in levels.items():
        if target_id.startswith("res-"):
            if target_id in MAPPING_TARGETS:
                assert level == "R4_DETECTION_READY", (target_id, level)
                assert missing == (), (target_id, missing)
            else:
                assert level == "R1_LEXICALLY_RESOLVED", (target_id, level)
                assert missing[0] == "curriculum_link", (target_id, missing)
            continue
        assert level is None, (target_id, level)
        assert missing == ("assessment_membership",), (target_id, missing)
    assert sorted(t for t, _ in levels if t.startswith("res-")) == list(
        RESOURCE_TARGETS
    )


def test_every_corpus_resource_target_is_detection_ready(
    built_content_db: Path,
) -> None:
    """不虚报, both directions (旧真值: none; C1: exactly one; C2-a: nine; C2-b:
    twenty-eight; C3-b: all sixty-four; 新真值 C3-R1: the sixteen mapping
    targets — the decision's honest fall-back): every target whose §24.7 row
    is a curriculum mapping reads
    R4 with its judgement fully reached, every placement target stops at R1
    with the link among its missing keys, and every target whose source
    states nothing carries no detection evidence, no level, and reports the
    four R4 facts as missing."""

    r4_targets: list[str] = []
    r1_targets: list[str] = []
    no_level_targets: list[str] = []
    for assessment in _corpus_assessments(built_content_db):
        if assessment.level == "R4_DETECTION_READY":
            r4_targets.append(assessment.target_id)
            assert assessment.detection_ready is True
            r4 = assessment.judgement("R4_DETECTION_READY")
            assert r4.reached is True
            assert r4.missing_keys == ()
            continue
        if assessment.level == "R1_LEXICALLY_RESOLVED":
            # The C3-R1 middle band: the evidence is all there, the link is a
            # coverage placement, and R4 is reported as unreached — never as
            # "absent evidence". The R4 judgement names every key of the R4
            # set that the facts satisfy as unreached, and the *level-1*
            # blocking key is the link itself.
            r1_targets.append(assessment.target_id)
            assert assessment.detection_ready is False
            r4 = assessment.judgement("R4_DETECTION_READY")
            assert r4.reached is False, assessment.target_id
            assert "curriculum_link" in assessment.missing_keys, (
                assessment.target_id
            )
            assert set(R4_FACTS) <= set(r4.required_keys)
            continue
        no_level_targets.append(assessment.target_id)
        assert assessment.level is None, assessment.target_id
        r4 = assessment.judgement("R4_DETECTION_READY")
        assert r4.reached is False, assessment.target_id
        # R4 is cumulative: the four detection facts *and* everything below
        # them are reported missing for every target that does not reach it.
        assert set(R4_FACTS) <= set(r4.missing_keys)
    assert r4_targets == list(MAPPING_TARGETS)
    assert r1_targets == list(PLACEMENT_TARGETS)
    assert no_level_targets == list(NO_LEVEL_TARGETS)


def test_the_never_present_keys_are_a_source_property_and_the_unread_mapping_is_empty(
    built_content_db: Path,
) -> None:
    """Old truth (P5-R): the keys the corpus never satisfied were exactly the
    ones with named missing evidence — "we did not read it" could not hide.
    New truth (C1, unchanged by C2-a): **every** §8.1 fact key is readable
    (the declared-absent mapping is empty), so what the corpus never
    satisfies is a property of the *sources*, not of the read face: the five
    CAPABILITY entities state no evidence at all, and their missing-key union
    is every key except the conditional TypicalError one — which no source
    triggers, so it is satisfied by the declared absence of a need on all
    fourteen."""

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
    # 旧真值 → 新真值（C1）: the equation against UNREAD_FACT_EVIDENCE plus
    # {curriculum_link, contrast_or_usage} collapses — the mapping is empty
    # and every key's evidence is readable — into this source-side equation.
    # Three keys are satisfied for every target today and so absent from the
    # union: ``entity_row`` (every artifact row exists), ``canonical_form``
    # (every target carries its §24.5 PRIMARY_TARGET row, the P3-1B
    # migration), and the conditional ``typical_error_when_needed`` (no
    # source triggers the need, so the declared absence satisfies it).
    assert never_present == set(READINESS_FACT_KEYS) - {
        "entity_row",
        "canonical_form",
        "typical_error_when_needed",
    }
    # The declared-absent mechanism itself: empty, kept, and still honest.
    assert UNREAD_FACT_EVIDENCE == {}
    assert DECLARED_ABSENT_FACT_KEYS == ()
    # ...and the conditional key is satisfied for every target today, which
    # is why it alone is absent from the union.
    for assessment in assessments.value:
        judgement = assessment.judgement("R4_DETECTION_READY")
        assert "typical_error_when_needed" not in judgement.missing_keys


def test_every_artifact_entity_is_an_expression(built_content_db: Path) -> None:
    """A corpus-shape fact that no longer carries an R1 reading (P5-R): all
    51 entities are EXPRESSION, and that is *not* why any target read R1 —
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
    assert len(types) == 69


def test_a_non_expression_entity_reads_the_same_no_level(tmp_path: Path) -> None:
    """The old F-1 counterexample, now a no-op by construction: flipping one
    entity's §24.1 ``entity_type`` to ``SENSE`` changes nothing, because
    entity type is not a readiness fact any more (P5-R removed the
    equivalence). The variant still proves the read path runs on a
    non-EXPRESSION artifact row — and it is built on a CAPABILITY entity,
    whose source states no evidence, so the no-level answer is read from the
    artifact rather than assumed."""

    def edit(documents: dict, index: dict) -> None:
        del index
        documents[f"entities/{NO_EVIDENCE_ENTITY}.json"]["entity"][
            "entity_type"
        ] = "SENSE"

    artifact = build_variant_artifact(tmp_path, edit)
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(NO_EVIDENCE_ENTITY)
        assert isinstance(facts, Ok), facts
        print(
            "[f1] SENSE entity -> entity_row="
            f"{facts.value.entity_row} canonical_form={facts.value.canonical_form}"
            f" pos={facts.value.pos} sense={facts.value.sense}"
            f" basic_definition={facts.value.basic_definition}"
            f" forms={facts.value.forms}"
        )
        assessment = supply.readiness(NO_EVIDENCE_ENTITY)
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
        assert isinstance(supply.get_resource(NO_EVIDENCE_ENTITY), Ok)
        # Its siblings are untouched (and read the same no-level answer).
        sibling = supply.readiness("cap-ref-ask-clarification")
        assert isinstance(sibling, Ok) and sibling.value.level is None
    finally:
        store.close()


def test_assessment_membership_is_required_and_absent(built_content_db: Path) -> None:
    """F-2, restated by P5-R and re-homed by C1: R0's third item is read,
    reported, **and required** — the strict conjunction. The strict reading
    is declared in the module rather than silently applied or silently
    skipped; the ∨ reading is recorded there as the option that was not
    adopted. C1 gave the fact a table, so what is absent for this target is
    the *source's* membership row, never the reader's reach (旧真值: the key
    sat in UNREAD_FACT_EVIDENCE; 新真值: the mapping is empty and the count
    reads 0 from its own table). The specimen is a CAPABILITY entity: since
    C2-a every RESOURCE target states a membership row."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(NO_EVIDENCE_ENTITY)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(NO_EVIDENCE_ENTITY)
        assert isinstance(assessment, Ok), assessment
        counts = store.evidence_counts(NO_EVIDENCE_ENTITY)
        assert isinstance(counts, Ok), counts
    finally:
        store.close()
    print(
        "[f2] assessment_membership -> "
        f"fact={facts.value.assessment_membership}"
        f" level={assessment.value.level}"
        " declared_absent=" + str(DECLARED_ABSENT_FACT_KEYS)
    )
    assert facts.value.assessment_membership is False
    assert counts.value.assessment_memberships == 0
    assert "assessment_membership" in READINESS_FACT_KEYS
    assert "assessment_membership" in assessment.value.judgement(
        "R0_INDEXED"
    ).required_keys
    assert assessment.value.level is None
    assert assessment.value.missing_keys == ("assessment_membership",)
    # C1: the fact is readable now — the absence is this source's, not the
    # read face's — so the declared-absent mapping no longer names it.
    assert "assessment_membership" not in UNREAD_FACT_EVIDENCE
    assert UNREAD_FACT_EVIDENCE == {}


def test_every_corpus_link_is_approved_and_satisfies_the_r2_fact(
    built_content_db: Path,
) -> None:
    """The corpus read one level down, now at C3-R1's truth (旧真值: every link
    was ``CURRICULUM_MAPPED`` and the R2 fact was False for all 14; C1: one
    approved link; C2-a: all nine RESOURCE targets' links approved by editorial
    review — C1 reviewed one, C2-a the other eight while authoring their
    readiness evidence, C2-b the nineteen it authored, C3-a and C3-b the
    eighteen each; **C3-R1**: the approval is no longer enough — the row must
    also be a ``CURRICULUM_MAPPING``, and the capability re-review found 48 of
    the 64 rows coverage placements). So the R2 ``curriculum_link`` fact is
    satisfied for exactly the sixteen mapping targets, every linked target's
    row is still approved (approval and mapping are now two separate
    clauses), and the 5 CAPABILITY nodes still have no link row of their own
    (curriculum/README.md C1 — no self-link is invented). The unapproved
    direction — a candidate mapping satisfies nothing — is pinned against a
    demoted variant in test_an_unapproved_curriculum_link_is_not_an_r2_fact
    below."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        linked: list[str] = []
        with_fact: list[str] = []
        approved: list[str] = []
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
                    link.editorial_status == "CANONICAL_APPROVED"
                    for link in links.value
                ), entity_id
                approved.append(entity_id)
        assert len(store.entity_ids().value) - len(linked) == 5
    finally:
        store.close()
    assert len(linked) == 64
    assert all(entity_id.startswith("res-") for entity_id in linked)
    # Every linked row is approved, and the R2 fact now reads one clause
    # further: it is satisfied exactly by the mapping rows (C3-R1).
    assert approved == sorted(linked)
    assert len(with_fact) == 16
    assert set(with_fact) <= set(approved)


def test_an_unapproved_curriculum_link_is_not_an_r2_fact(
    tmp_path: Path,
) -> None:
    """The fact is not dead in either direction: it turns on approval and off
    again when the approval is withdrawn. The corpus carries no unapproved
    row since C2-a (all sixty-four are approved), so the demotion is built
    as a variant — and the row stays readable either way (unapproved ≠
    deleted). The canonical artifact is read too, so the pair "approved ⇒
    True, demoted ⇒ False" holds over two real builds rather than over one."""

    def demote(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == FOCUS:
                assert row["editorial_status"] == "CANONICAL_APPROVED"
                row["editorial_status"] = "CURRICULUM_MAPPED"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=demote)
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        demoted = supply.readiness_facts(FOCUS)
        assert isinstance(demoted, Ok), demoted
        assert demoted.value.curriculum_link is False
        assert demoted.value is not None
        # The link row itself is still readable, and now says CURRICULUM_MAPPED.
        links = supply.curriculum_links_of(ResourceId(FOCUS))
        assert isinstance(links, Ok) and len(links.value) == 1
        assert links.value[0].editorial_status == "CURRICULUM_MAPPED"
    finally:
        store.close()


def test_an_approved_curriculum_link_is_an_r2_fact(tmp_path: Path) -> None:
    """The fact is not dead: an approved §24.7 mapping satisfies it, and
    nothing else does. The canonical corpus now carries only approved rows
    (C2-a), so both states are built as variants over one artifact: two rows
    are demoted first — the fact drops for both — and then one of them is
    approved again, which turns that target's fact back on while the other
    stays off. The row stays readable in all three states (unapproved ≠
    deleted), so the reading is the status, never the row's presence."""

    def demote_two_then_approve_one(
        documents: dict, _index: dict
    ) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] in (FOCUS, "res-softener-kind-of"):
                row["editorial_status"] = "CURRICULUM_MAPPED"
            if row["resource_id"] == FOCUS:
                row["editorial_status"] = "CANONICAL_APPROVED"

    artifact = build_variant_artifact(
        tmp_path, curriculum_edit=demote_two_then_approve_one
    )
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
        # Both link rows stay readable on the demoted/approved variant.
        links = supply.curriculum_links_of(ResourceId("res-softener-kind-of"))
        assert isinstance(links, Ok) and len(links.value) == 1
        assert links.value[0].editorial_status == "CURRICULUM_MAPPED"
        approved = supply.curriculum_links_of(ResourceId(FOCUS))
        assert isinstance(approved, Ok) and len(approved.value) == 1
        assert approved.value[0].editorial_status == "CANONICAL_APPROVED"
    finally:
        store.close()


def test_assessment_type_is_the_readiness_one() -> None:
    """A small structural pin: the judgement returns the module's own type."""

    assert isinstance(judge_readiness(_facts()), ReadinessAssessment)
