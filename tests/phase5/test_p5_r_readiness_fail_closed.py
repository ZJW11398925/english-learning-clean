"""P5-R / D3 — readiness, fail-closed: the ladder reports what the artifact
carries.

The blocker this file closes (external review, TASK-OPI-a68fd9eb-…22 /
DEC-OPI-a68fd9eb-…15): §8.1 R1 requires "POS / sense / basic definition /
forms 已可追溯", the corpus carried none of the four, and the implementation
reported R1 anyway by reading ``entity_type == EXPRESSION`` as "lexically
resolved" — a canonical-drift in the direction of a *friendlier* answer.
R0's third named thing (assessment membership) was likewise excluded from
R0's requirements.

The corrected reading, pinned here (written at P5-R's truth; C1 narrowed
the corpus claim to its current shape, and each line says which):

- R0 requires all three named things (strict conjunction); R1 requires the
  four named things, each read from its own evidence and from nothing else;
- the entity-type equivalence is gone from the code, not just from the prose;
- the corpus read **no level at all** (``level is None``) for all 14 targets
  at P5-R's truth — the honest report; since C1 the thirteen evidence-less
  targets still read exactly that, and the one C1-evidenced target reads
  R4_DETECTION_READY (same ladder, same strictness, artifact-driven);
- no level word is invented for "below R0";
- the ∨ reading of R0 is recorded in the module as the alternative that was
  not adopted.

The canonical words are extracted from docs/ at test time (the P5-0/P5-1
precedent), so a doc edit that changes them fails here first.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import get_type_hints

import pytest

from elc.content.store import ContentStore
from elc.content.types import ReadinessLevel
from elc.curriculum.readiness import (
    DECLARED_ABSENT_FACT_KEYS,
    LEVEL_ADDED_FACTS,
    READINESS_FACT_KEYS,
    READINESS_LEVELS,
    ReadinessAssessment,
    ReadinessFacts,
    judge_readiness,
    required_fact_keys,
)
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok
from tests.conftest import SRC_ROOT
from tests.phase5.conftest import DOCS_ROOT, build_variant_artifact

FOCUS = "res-hedge-i-think"
R1_FACETS = ("pos", "sense", "basic_definition", "forms")
HEADING_8_1 = "## 8.1 Content Readiness（Normative）"


def _facts(**present: bool) -> ReadinessFacts:
    return ReadinessFacts(target_id=FOCUS, **present)


def _r0_bundle(**extra: bool) -> ReadinessFacts:
    """A bundle carrying R0's three named things, plus ``extra``."""

    present = {
        "entity_row": True,
        "canonical_form": True,
        "assessment_membership": True,
    }
    present.update(extra)
    return _facts(**present)


def _section_text(doc: str, heading: str) -> str:
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
    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    return tuple(assessments.value)


# ---------------------------------------------------------------------------
# ① the canonical words, read from the documents
# ---------------------------------------------------------------------------


def test_the_r1_line_names_the_four_things_the_ladder_requires() -> None:
    """R1 is "POS / sense / basic definition / forms 已可追溯" — four named
    things, mapped to four fact keys, none of them derived from another."""

    section = _section_text("PRODUCT_CONTRACT.md", HEADING_8_1)
    assert "POS / sense / basic definition / forms 已可追溯。" in section
    assert LEVEL_ADDED_FACTS["R1_LEXICALLY_RESOLVED"] == R1_FACETS
    assert len(R1_FACETS) == 4


def test_the_r0_line_names_the_three_things_and_all_three_are_required() -> None:
    section = _section_text("PRODUCT_CONTRACT.md", HEADING_8_1)
    assert "source / assessment membership / canonical form 可定位" in section
    assert LEVEL_ADDED_FACTS["R0_INDEXED"] == (
        "entity_row",
        "canonical_form",
        "assessment_membership",
    )
    assert "assessment_membership" in required_fact_keys("R0_INDEXED")
    # 旧真值 → 新真值（C1）: the key was the declared-absent one; the
    # thirteen evidence tables made it readable, so the mechanism is empty
    # while the requirement is unchanged.
    assert DECLARED_ABSENT_FACT_KEYS == ()
    print(
        "[p5-r] R0 requires the third item (now table-read) -> "
        f"{required_fact_keys('R0_INDEXED')}"
    )


def test_every_fact_key_is_required_by_exactly_one_level() -> None:
    """No key sits outside the ladder, and no key is required twice — the
    strict reading leaves no exempt fact in the vocabulary."""

    flattened = tuple(
        key for level in READINESS_LEVELS for key in LEVEL_ADDED_FACTS[level]
    )
    assert len(set(flattened)) == len(flattened)
    assert set(flattened) == set(READINESS_FACT_KEYS)
    assert set(DECLARED_ABSENT_FACT_KEYS) <= set(flattened)
    # The cumulative view still starts at R0 and never skips a level.
    for level in READINESS_LEVELS:
        assert required_fact_keys(level) == flattened[
            : len(required_fact_keys(level))
        ]


def test_no_level_word_is_invented_for_below_r0() -> None:
    """§8.1 has five levels; a target that reaches none reads ``None`` and no
    sixth word is minted for it (the module may *name* the hypothetical word it
    refuses to create, so this is a code check, not a substring one)."""

    import ast

    assert READINESS_LEVELS == tuple(str(level) for level in ReadinessLevel)
    assert len(READINESS_LEVELS) == 5
    path = SRC_ROOT / "curriculum" / "readiness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for invented in ("INDEXED_ONLY", "BELOW_R0", "NOT_INDEXED", "UNINDEXED"):
        assert invented not in constants
    assessment = judge_readiness(_facts())
    assert assessment.level is None
    assert assessment.next_level == "R0_INDEXED"


def test_the_assessment_level_is_an_optional_word() -> None:
    hints = get_type_hints(ReadinessAssessment)
    assert hints["level"] == (str | None)
    assert hints["next_level"] == (str | None)


def test_the_strict_reading_is_declared_with_its_rejected_alternative() -> None:
    """The module must *say* that the strict conjunction was adopted and that
    the ∨ reading was recorded but not adopted — a reader may check the
    decision, not just its consequence."""

    source = (SRC_ROOT / "curriculum" / "readiness.py").read_text(encoding="utf-8")
    assert "strict" in source
    assert "∨" in source
    assert "not adopted" in source
    assert "assessment_membership" in source


# ---------------------------------------------------------------------------
# ② the judgement, one key at a time
# ---------------------------------------------------------------------------


def test_r0_needs_all_three_named_things() -> None:
    assert judge_readiness(_facts(entity_row=True)).level is None
    assert judge_readiness(
        _facts(entity_row=True, canonical_form=True)
    ).level is None, "the third named item is required (strict conjunction)"
    assert judge_readiness(_r0_bundle()).level == "R0_INDEXED"


def test_r1_needs_each_of_the_four_named_things() -> None:
    complete = _r0_bundle(**{facet: True for facet in R1_FACETS})
    assert judge_readiness(complete).level == "R1_LEXICALLY_RESOLVED"
    for facet in R1_FACETS:
        bundle = dataclasses.replace(complete, **{facet: False})
        assessment = judge_readiness(bundle)
        assert assessment.level == "R0_INDEXED", facet
        assert assessment.next_level == "R1_LEXICALLY_RESOLVED"
        assert facet in assessment.missing_keys
        assert assessment.judgement("R1_LEXICALLY_RESOLVED").reached is False


def test_no_single_fact_can_stand_in_for_a_lexical_resolution() -> None:
    """The retracted equivalence in one probe: nothing except the four facts
    themselves raises R1 — an entity row, a canonical form, a contrast or a
    teaching payload is not a lexical resolution."""

    stand_ins = (
        "entity_row",
        "canonical_form",
        "contrast_or_usage",
        "curriculum_link",
    )
    for wrong in stand_ins:
        bundle = _r0_bundle(**{wrong: True})
        assessment = judge_readiness(bundle)
        assert assessment.level == "R0_INDEXED", wrong
        assert set(R1_FACETS) <= set(assessment.missing_keys), wrong


# ---------------------------------------------------------------------------
# ③ the corpus: the artifact's answer (P5-R: no level at all; C1: 1×R4 +
# 13×None), and the block is named
# ---------------------------------------------------------------------------


def test_thirteen_targets_read_no_level_and_one_reads_r4(
    built_content_db: Path,
) -> None:
    """Old truth: all fourteen read no level, blocked at R0 by
    ``assessment_membership``. New truth (C1): the thirteen targets whose
    sources state no evidence read exactly that, and the one target whose
    source states all nineteen facts reads ``R4_DETECTION_READY`` — the same
    fail-closed ladder, now driven by the artifact."""

    assessments = _corpus_assessments(built_content_db)
    print("\n[p5-r] target -> level -> keys blocking the next level")
    for assessment in assessments:
        print(
            f"[p5-r] {assessment.target_id:32} {assessment.level!s:22}"
            f" {assessment.missing_keys}"
        )
    assert len(assessments) == 14
    for assessment in assessments:
        if assessment.target_id == "res-colloc-make-a-decision":
            assert assessment.level == "R4_DETECTION_READY"
            assert assessment.next_level is None
            assert assessment.missing_keys == ()
            continue
        assert assessment.level is None, assessment.target_id
        assert assessment.next_level == "R0_INDEXED"
        assert assessment.missing_keys == ("assessment_membership",)
        r1 = assessment.judgement("R1_LEXICALLY_RESOLVED")
        assert not r1.reached
        assert set(R1_FACETS) <= set(r1.missing_keys)
        # Cumulative reporting: the R0 blocker is still standing in R1's set.
        assert "assessment_membership" in r1.missing_keys


def test_the_lexical_resolution_equivalence_is_gone_from_the_code() -> None:
    """No *code* in either module still names a ``lexical_resolution`` key or
    touches ``entity_type`` — the retraction is in the AST, not only in the
    prose (both words survive inside the docstrings that record the
    retraction, which is why this is an AST check and not a substring one)."""

    import ast

    for relative in ("curriculum/readiness.py", "curriculum/store.py"):
        path = SRC_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        constants = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert "lexical_resolution" not in constants, relative
        assert "entity_type" not in attributes, relative


def test_a_non_expression_entity_reads_the_same_no_level(tmp_path: Path) -> None:
    """The old F-1 counterexample, now trivially satisfied: flipping
    ``entity_type`` changes nothing at all, because entity type is not a
    readiness fact any more."""

    def edit(documents: dict, index: dict) -> None:
        del index
        documents[f"entities/{FOCUS}.json"]["entity"]["entity_type"] = "SENSE"

    artifact = build_variant_artifact(tmp_path, edit)
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(FOCUS)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(FOCUS)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    for facet in R1_FACETS:
        assert getattr(facts.value, facet) is False, facet
    assert assessment.value.level is None
    assert assessment.value.missing_keys == ("assessment_membership",)
    assert not hasattr(facts.value, "lexical_resolution")


def test_the_readiness_facts_bundle_carries_exactly_the_ladder_keys() -> None:
    """The dataclass fields and the fact-key vocabulary cannot drift: every
    field is a key (``typical_error`` backing ``typical_error_when_needed``)
    and every key is a field."""

    names = {field.name for field in dataclasses.fields(ReadinessFacts)}
    names.discard("target_id")
    names.discard("typical_error_required")
    assert names - {"typical_error"} == set(READINESS_FACT_KEYS) - {
        "typical_error_when_needed"
    }
    assert "typical_error" in names
    for facet in R1_FACETS:
        assert facet in names


@pytest.mark.parametrize("level", READINESS_LEVELS)
def test_no_level_is_reported_without_every_required_key(level: str) -> None:
    """The general rule behind the corpus truth: for each level, dropping one
    required key reports a level strictly below it (or None)."""

    present = {key: True for key in required_fact_keys(level)}
    present.pop("typical_error_when_needed", None)
    assert judge_readiness(_facts(**present)).level == level
    for key in required_fact_keys(level):
        if key == "typical_error_when_needed":
            continue
        bundle = _facts(**{**present, key: False})
        assert judge_readiness(bundle).level != level, key
        assert judge_readiness(bundle).level is None or (
            READINESS_LEVELS.index(judge_readiness(bundle).level)
            < READINESS_LEVELS.index(level)
        )


def test_the_retracted_reading_is_recorded_in_the_module_docstring() -> None:
    source = (SRC_ROOT / "curriculum" / "readiness.py").read_text(encoding="utf-8")
    assert re.search(r"P5-R removes that\s+equivalence", source), source[:200]
    assert re.search(
        r"An entity type is not evidence about a lexical\s+resolution\.", source
    )
