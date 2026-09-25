"""C1 (Phase 11) — the §8.1 readiness evidence face, pinned as built.

docs/DATA_MODEL.md §24 (Normative) + PRODUCT_CONTRACT.md §8.1. Thirteen new
tables (elc.content.build.SCHEMA_STATEMENTS, 11 → 24), a strict
``content_src/evidence/<entity_id>.json`` authoring tree, and a read face
(elc.curriculum.store.readiness_facts) that reads all nineteen §8.1 fact
keys from the artifact instead of declaring them absent. What this file
pins, in order:

- the thirteen tables exist with exactly the declared columns and primary
  keys, and every FK points at content_entity(entity_id);
- the build stays deterministic: two builds from one source are
  byte-identical, and a rebuild over an existing file is a replay;
- the corpus table reads 1 × R4_DETECTION_READY (res-colloc-make-a-decision,
  the one target whose source states all nineteen facts) + 13 × None;
- every §8.1 fact key has a dedicated per-fact pin, both directions (present
  for the evidenced target, absent for an evidence-less one);
- the strict loader refuses, never degrades: unknown text role, unknown
  fixture kind, duplicate primary key, unknown block key, an unlisted or
  dangling evidence document — each is a BuildError with no artifact;
- the conditional TypicalError fact ("以及需要时") is a source declaration:
  declared need without rows reports the gap (the ladder's answer, not a
  build refusal), an untriggered need satisfies the key, and a declared
  satisfied need keeps the target's level;
- the R4 evidence is checkable by construction: every detection rule's
  ordinal carries a fixture, every fixture states a non-empty expected
  reading, and both kinds are the declared vocabulary.

The canonical authoring trees are never edited to make a test convenient:
every variant lives in a pytest tmp copy built through the real build step.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

import pytest

from elc.content.build import (
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    SCHEMA_STATEMENTS,
    BuildError,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok

#: The one C1-evidenced target, and one evidence-less sibling.
R4_TARGET = "res-colloc-make-a-decision"
NO_EVIDENCE_TARGET = "res-hedge-i-think"

#: The thirteen evidence tables, transcribed independently of
#: ``SCHEMA_STATEMENTS`` (a second hand-typed copy is the point: a schema
#: edit that silently drops or renames a column fails here, not only in its
#: own DDL). Each entry: (table, columns in declared order, primary key).
EVIDENCE_TABLES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "content_assessment_membership",
        ("entity_id", "assessment_id", "membership_status", "source"),
        ("entity_id", "assessment_id"),
    ),
    ("content_lexical_entry", ("entity_id", "lemma", "pos"), ("entity_id",)),
    (
        "content_sense",
        ("entity_id", "sense_id", "ordinal"),
        ("entity_id", "sense_id"),
    ),
    (
        "content_text",
        ("entity_id", "sense_id", "language", "role", "ordinal", "text"),
        ("entity_id", "role", "ordinal"),
    ),
    (
        "content_form",
        (
            "entity_id",
            "form_id",
            "written",
            "normalized",
            "form_type",
            "morph_features",
            "pronunciation",
        ),
        ("entity_id", "form_id"),
    ),
    (
        "content_pedagogical_profile",
        (
            "entity_id",
            "core_utility",
            "receptive_value",
            "productive_value",
            "receptive_difficulty",
            "productive_difficulty",
            "explanation_cost",
            "transfer_value",
            "naturalness_value",
            "default_target_mode",
            "editorial_status",
            "rationale",
        ),
        ("entity_id",),
    ),
    (
        "content_pack_overlay",
        ("entity_id", "pack_id", "weight", "rationale"),
        ("entity_id", "pack_id"),
    ),
    (
        "content_resource_label",
        (
            "entity_id",
            "ordinal",
            "register",
            "usage_modality",
            "genre",
            "context",
            "style",
            "domain",
            "variety",
        ),
        ("entity_id", "ordinal"),
    ),
    (
        "content_example_policy",
        ("entity_id", "policy_version", "policy"),
        ("entity_id",),
    ),
    (
        "content_typical_error",
        (
            "entity_id",
            "ordinal",
            "learner_l1",
            "error_type",
            "error_pattern",
            "corrected_pattern",
            "explanation",
            "severity",
            "detection_policy",
        ),
        ("entity_id", "ordinal"),
    ),
    (
        "content_detection_policy",
        ("entity_id", "policy_version", "policy"),
        ("entity_id",),
    ),
    (
        "content_detection_rule",
        ("entity_id", "ordinal", "rule"),
        ("entity_id", "ordinal"),
    ),
    (
        "content_detection_fixture",
        ("entity_id", "ordinal", "kind", "text", "expected"),
        ("entity_id", "ordinal"),
    ),
)


def _edited_source(
    tmp_path: Path, edit: Callable[[Path], None]
) -> tuple[Path, Path]:
    """A copy of both authoring trees with one edit applied to content_src.

    The edit receives the copied ``content_src`` directory and may do
    anything to it (rewrite the evidence document, drop it, unlist it); the
    canonical trees themselves are never touched.
    """

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    edit(content_src)
    return content_src, curriculum


def _build_edited(tmp_path: Path, edit: Callable[[Path], None]) -> Path:
    content_src, curriculum = _edited_source(tmp_path, edit)
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


# ---------------------------------------------------------------------------
# ① the thirteen tables, column by column
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table,columns,primary_key", EVIDENCE_TABLES)
def test_each_evidence_table_carries_its_declared_columns(
    built_content_db: Path,
    table: str,
    columns: tuple[str, ...],
    primary_key: tuple[str, ...],
) -> None:
    """The §24 columns (or the declared reading where §24 names no field
    table), in declared order, with the declared primary key."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        info = conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    finally:
        conn.close()
    assert tuple(row[1] for row in info) == columns, table
    assert tuple(row[1] for row in info if row[5]) == primary_key, table


@pytest.mark.parametrize("table,columns,primary_key", EVIDENCE_TABLES)
def test_every_evidence_table_fk_points_at_content_entity(
    built_content_db: Path,
    table: str,
    columns: tuple[str, ...],
    primary_key: tuple[str, ...],
) -> None:
    """One parent, everywhere: the evidence hangs off the §24.1 entity row,
    never at a second anchor (the build's own comment block, now pinned)."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    assert [(row[3], row[2], row[4]) for row in fks] == [
        ("entity_id", "content_entity", "entity_id")
    ], table


def test_the_artifact_has_exactly_the_declared_twenty_four_tables(
    built_content_db: Path,
) -> None:
    """The artifact's table set is SCHEMA_STATEMENTS (11 + 13 = 24), nothing
    more, nothing less."""

    declared = tuple(
        statement.split("(", 1)[0].split()[-1] for statement in SCHEMA_STATEMENTS
    )
    assert len(declared) == 24
    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    assert tuple(str(row[0]) for row in rows) == tuple(sorted(declared))


# ---------------------------------------------------------------------------
# ② determinism, again, over the evidence face
# ---------------------------------------------------------------------------


def test_two_builds_are_byte_identical_and_a_rebuild_is_a_replay(
    tmp_path: Path,
) -> None:
    """No filesystem, index or authoring-array order may reach the bytes:
    two builds from one source are identical, and building over an existing
    file replays it."""

    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    build_content_db(first)
    build_content_db(second)
    assert first.read_bytes() == second.read_bytes()
    # A rebuild over an existing artifact is the same bytes (idempotent).
    build_content_db(first)
    assert first.read_bytes() == second.read_bytes()


# ---------------------------------------------------------------------------
# ③ the corpus table and the per-fact pins
# ---------------------------------------------------------------------------


def test_readiness_by_target_is_one_r4_and_thirteen_none(
    built_content_db: Path,
) -> None:
    """The corpus table on the real artifact: the one evidenced target reads
    R4_DETECTION_READY; the thirteen evidence-less targets read None (no
    level is invented for them — §8.1 has no word below R0)."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    table = {a.target_id: a.level for a in assessments.value}
    assert len(table) == 14
    assert table[R4_TARGET] == "R4_DETECTION_READY"
    assert sum(1 for level in table.values() if level is None) == 13


@pytest.mark.parametrize("key", READINESS_FACT_KEYS)
def test_every_fact_key_is_present_for_the_r4_target(
    built_content_db: Path, key: str
) -> None:
    """Per-fact pin, present side: the evidenced target satisfies all
    nineteen §8.1 fact keys, each read from its own table."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(R4_TARGET)
        assert isinstance(facts, Ok), facts
    finally:
        store.close()
    assert facts.value.present(key) is True, key


@pytest.mark.parametrize(
    "key",
    [
        "assessment_membership",
        "pos",
        "sense",
        "basic_definition",
        "forms",
        "curriculum_link",
        "pedagogical_profile",
        "goal_pack_overlay",
        "resource_labels",
        "reviewed_explanation",
        "example_policy",
        "contrast_or_usage",
        "detection_policy",
        "recognition_rules",
        "negative_fixtures",
        "false_positive_boundaries",
    ],
)
def test_every_fact_key_is_absent_for_an_evidence_less_target(
    built_content_db: Path, key: str
) -> None:
    """Per-fact pin, absent side: a target whose source states no evidence
    reads False on every evidence-backed key — absence read as absence, and
    (unlike the pre-C1 face) each False is a table count of 0, not a
    hardcoded default."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(NO_EVIDENCE_TARGET)
        assert isinstance(facts, Ok), facts
        counts = store.evidence_counts(NO_EVIDENCE_TARGET)
        assert isinstance(counts, Ok), counts
    finally:
        store.close()
    assert facts.value.present(key) is False, key
    assert facts.value.assessment_membership is (
        counts.value.assessment_memberships >= 1
    )


# ---------------------------------------------------------------------------
# ④ the strict loader: refuse, never degrade
# ---------------------------------------------------------------------------


def _edit_evidence(text_edit: Callable[[dict], None]) -> Callable[[Path], None]:
    """An edit closure over the one evidence document."""

    def edit(content_src: Path) -> None:
        path = content_src / "evidence" / f"{R4_TARGET}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        text_edit(document)
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return edit


def test_an_unknown_text_role_is_refused(tmp_path: Path) -> None:
    def break_role(document: dict) -> None:
        document["texts"][0]["role"] = "commentary"

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path, _edit_evidence(break_role))
    assert "commentary" in str(raised.value)


def test_an_unknown_fixture_kind_is_refused(tmp_path: Path) -> None:
    def break_kind(document: dict) -> None:
        document["detection_fixtures"][0]["kind"] = "POSITIVE"

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path, _edit_evidence(break_kind))
    assert "POSITIVE" in str(raised.value)


def test_a_duplicate_primary_key_is_refused(tmp_path: Path) -> None:
    def break_pk(document: dict) -> None:
        document["detection_rules"].append(
            dict(document["detection_rules"][0])
        )

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path, _edit_evidence(break_pk))
    assert "duplicate" in str(raised.value)


def test_an_unknown_evidence_block_is_refused(tmp_path: Path) -> None:
    def break_block(document: dict) -> None:
        document["mystery_block"] = []

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path, _edit_evidence(break_block))
    assert "mystery_block" in str(raised.value)


def test_an_unlisted_evidence_document_is_refused(tmp_path: Path) -> None:
    """No silent skip, evidence edition: a document the index does not list
    is an error, exactly like an unlisted entity document."""

    def add_unlisted(content_src: Path) -> None:
        source = content_src / "evidence" / f"{R4_TARGET}.json"
        shutil.copyfile(source, content_src / "evidence" / f"{NO_EVIDENCE_TARGET}.json")

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path, add_unlisted)
    assert "not listed" in str(raised.value)


def test_a_dangling_evidence_document_is_refused(tmp_path: Path) -> None:
    """An evidence document naming an entity the index does not declare is a
    dangling reference."""

    def add_dangling(content_src: Path) -> None:
        source = content_src / "evidence" / f"{R4_TARGET}.json"
        shutil.copyfile(source, content_src / "evidence" / "res-ghost.json")
        index_path = content_src / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["evidence"].append("evidence/res-ghost.json")
        index_path.write_text(
            json.dumps(index, indent=2) + "\n", encoding="utf-8"
        )

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path, add_dangling)
    assert "res-ghost" in str(raised.value)


def test_an_empty_evidence_list_is_a_legal_source(tmp_path: Path) -> None:
    """"This corpus states no readiness evidence" is a buildable state (the
    index's ``evidence`` key allows ``[]``), and the artifact then carries no
    evidence rows: every target reads None."""

    def empty_evidence(content_src: Path) -> None:
        (content_src / "evidence" / f"{R4_TARGET}.json").unlink()
        index_path = content_src / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["evidence"] = []
        index_path.write_text(
            json.dumps(index, indent=2) + "\n", encoding="utf-8"
        )

    artifact = _build_edited(tmp_path, empty_evidence)
    conn = sqlite3.connect(str(artifact))
    try:
        total = conn.execute(
            "SELECT ("
            " (SELECT COUNT(*) FROM content_assessment_membership) +"
            " (SELECT COUNT(*) FROM content_lexical_entry) +"
            " (SELECT COUNT(*) FROM content_detection_fixture))"
        ).fetchone()[0]
    finally:
        conn.close()
    assert total == 0
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    assert all(a.level is None for a in assessments.value)


# ---------------------------------------------------------------------------
# ⑤ the conditional TypicalError fact is a source declaration
# ---------------------------------------------------------------------------


def test_a_declared_need_without_rows_reports_the_gap(tmp_path: Path) -> None:
    """A source that declares the TypicalError need before writing the error
    is **built** (readiness is a report, never a build-time refusal) and the
    ladder answers: ``typical_error_when_needed`` unsatisfied, level R2."""

    def drop_errors(document: dict) -> None:
        del document["typical_errors"]
        # `typical_error_required: true` stays declared.

    artifact = _build_edited(tmp_path, _edit_evidence(drop_errors))
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(R4_TARGET)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(R4_TARGET)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    assert facts.value.typical_error is False
    assert facts.value.typical_error_required is True
    assert facts.value.present("typical_error_when_needed") is False
    assert assessment.value.level == "R2_PLANNER_READY"
    assert "typical_error_when_needed" in assessment.value.missing_keys


def test_an_untriggered_need_satisfies_the_conditional_key(
    tmp_path: Path,
) -> None:
    """No declaration, no rows: the conditional key is satisfied by the
    declared absence of a need (§8.1 "以及需要时" — a condition, not a
    silent skip), so the R3 set completes without any TypicalError row —
    and the detection face is independent of it, so the level is still R4."""

    def drop_need_and_errors(document: dict) -> None:
        del document["typical_errors"]
        del document["typical_error_required"]

    artifact = _build_edited(tmp_path, _edit_evidence(drop_need_and_errors))
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(R4_TARGET)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(R4_TARGET)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    assert facts.value.typical_error is False
    assert facts.value.typical_error_required is False
    assert facts.value.present("typical_error_when_needed") is True
    assert assessment.value.level == "R4_DETECTION_READY"


def test_a_declared_and_satisfied_need_keeps_the_level(
    built_content_db: Path,
) -> None:
    """The canonical R4 target declares the need **and** carries the errors:
    the conditional key is satisfied by the rows, and the level is the
    highest one whose set is complete."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(R4_TARGET)
        assert isinstance(facts, Ok), facts
        error_need = store.typical_error_required(R4_TARGET)
        assert isinstance(error_need, Ok), error_need
    finally:
        store.close()
    assert error_need.value is True
    assert facts.value.typical_error is True
    assert facts.value.present("typical_error_when_needed") is True


# ---------------------------------------------------------------------------
# ⑥ the R4 evidence is checkable by construction
# ---------------------------------------------------------------------------


def test_every_rule_carries_a_fixture_and_every_fixture_an_expected_reading(
    built_content_db: Path,
) -> None:
    """§24.10: "R4 必须包含可测试 detection policy/fixtures/false-positive
    boundary". Testable means paired: every rule's ordinal carries a fixture
    that bounds it, every fixture states a non-empty expected reading, and
    both fixture kinds are the declared two-word vocabulary."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        rules = conn.execute(
            "SELECT ordinal, rule FROM content_detection_rule "
            "WHERE entity_id = ? ORDER BY ordinal",
            (R4_TARGET,),
        ).fetchall()
        fixtures = conn.execute(
            "SELECT ordinal, kind, text, expected FROM content_detection_fixture "
            "WHERE entity_id = ? ORDER BY ordinal",
            (R4_TARGET,),
        ).fetchall()
        policy = conn.execute(
            "SELECT policy FROM content_detection_policy WHERE entity_id = ?",
            (R4_TARGET,),
        ).fetchone()
    finally:
        conn.close()
    assert policy is not None and policy[0]
    rule_ordinals = [row[0] for row in rules]
    fixture_ordinals = [row[0] for row in fixtures]
    assert rule_ordinals == sorted(rule_ordinals)
    # Every rule ordinal is bounded by a fixture at the same ordinal, and
    # the kinds are exactly the declared vocabulary.
    assert set(rule_ordinals) == set(fixture_ordinals)
    for _, kind, text, expected in fixtures:
        assert kind in ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY"), kind
        assert text
        assert expected
        assert expected in ("NO_MATCH", "NO_MATCH_BOUNDARY"), expected
    kinds = {row[1] for row in fixtures}
    assert kinds == {"NEGATIVE", "FALSE_POSITIVE_BOUNDARY"}
