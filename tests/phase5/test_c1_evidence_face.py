"""C1 (Phase 11) — the §8.1 readiness evidence face, pinned as built.

docs/DATA_MODEL.md §24 (Normative) + PRODUCT_CONTRACT.md §8.1. Thirteen new
tables (elc.content.build.SCHEMA_STATEMENTS, 11 → 24, grown to 25 by
C3-R2's ``content_provenance``), a strict
``content_src/evidence/<entity_id>.json`` authoring tree, and a read face
(elc.curriculum.store.readiness_facts) that reads the eighteen row-backed
§8.1 fact keys from the artifact and proves ``entity_row`` from the entity's
own §24.1 row (the preceding ``get_resource`` success) instead of declaring
any of them absent. What this file pins, in order:

- the thirteen tables exist with exactly the declared columns and primary
  keys, and every FK points at content_entity(entity_id);
- the build stays deterministic: two builds from one source are
  byte-identical, a rebuild over an existing file is a replay, and two
  *subprocess* builds under different ``PYTHONHASHSEED`` values hash equal
  (C1 disposition F4 — hash randomization must not reach the bytes);
- the corpus table reads 16 × R4_DETECTION_READY (the RESOURCE targets whose
  §24.7 row is a curriculum mapping — C3-R1 re-reviewed the links, and only
  those rows satisfy §8.1 R2) + 48 × R1_LEXICALLY_RESOLVED (the same targets
  with every other evidence fact present and a coverage-placement link, so
  the ladder stops at R1 — the fall-back C3-R1's decision made on purpose)
  + 5 × None (the five CAPABILITY entities, whose sources state no readiness
  evidence at all). Before C3-R1 this table read 64 × R4 + 5 × None: the
  count moved because the R2 fact moved, not because any evidence was
  removed (every evidence pin in this file is unchanged);
- every §8.1 fact key has a dedicated per-fact pin, both directions (present
  for the evidenced target, absent for an evidence-less one), and the
  content_text role reads are load-bearing: the artifact's per-role row
  counts and texts are pinned, and the store's role predicates are pinned
  against a variant where the counts differ (C1 disposition F5);
- the strict loader refuses, never degrades: unknown text role, unknown
  fixture kind, duplicate primary key, unknown block key (outer *and*
  inner — C1 disposition F3), an empty array block (C1 disposition F3),
  an unlisted or dangling evidence document — each is a BuildError with no
  artifact;
- the conditional TypicalError fact ("以及需要时") is a source declaration:
  declared need without rows reports the gap (the ladder's answer, not a
  build refusal), an untriggered need satisfies the key, and a declared
  satisfied need keeps the target's level;
- the R4 evidence is checkable by construction: every detection rule's
  ordinal carries a fixture, every fixture states a non-empty expected
  reading, and both kinds are the declared vocabulary;
- the artifact declares the bumped ``content_db_version`` (C1 disposition
  F6: the constant is "2" and the artifact agrees);
- ``reviewed_explanation`` is the C1 disposition's declared reading: a
  teaching_note row **and** the entity's §24.11 lifecycle_status being
  ``CANONICAL_APPROVED`` — a variant whose entity is not approved flips the
  fact while the row count stays (C1 disposition F7c);
- ``UNREAD_FACT_EVIDENCE``'s entries — whatever is registered there, today
  none — stay well-formed (C1 disposition F10's restored guard).

The canonical authoring trees are never edited to make a test convenient:
every variant lives in a pytest tmp copy built through the real build step.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from elc.content.build import (
    CONTENT_DB_VERSION,
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    SCHEMA_STATEMENTS,
    BuildError,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import UNREAD_FACT_EVIDENCE, CurriculumContentStore
from elc.platform.types import Ok
from tests.conftest import REPO_ROOT

#: The C1-authored target, and one entity whose source states no evidence.
#: Since C2-a every RESOURCE target states evidence, so the evidence-less
#: class is the five CAPABILITY entities (they carry no `evidence/` document
#: and no §24.7 link row of their own) — the same absence, one entity type
#: over, and the reason the per-key zero pins below read 0 rather than "".
#:
#: **C3-R1 moved this target's level, not its evidence**: the capability
#: re-review found its §24.7 row a coverage placement (a collocation names an
#: act; it hedges nothing), so §8.1's ``curriculum_link`` fact is now False
#: for it and it reads R1_LEXICALLY_RESOLVED. Keeping this constant is the
#: point: every evidence pin below still holds unchanged, because the rows
#: are all still there and only the link's mapping class moved. Tests whose
#: subject is the *level* (a ladder step that cannot be observed on a target
#: already stopped at R1) use ``MAPPING_TARGET`` instead.
R4_TARGET = "res-colloc-make-a-decision"
NO_EVIDENCE_TARGET = "cap-disc-topic-shift"

#: A target whose §24.7 row *is* a curriculum mapping after C3-R1, so it
#: still reads R4_DETECTION_READY and all nineteen §8.1 fact keys are
#: satisfied for it.
MAPPING_TARGET = "res-hedge-i-think"

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


def test_the_artifact_has_exactly_the_declared_tables(
    built_content_db: Path,
) -> None:
    """The artifact's table set is SCHEMA_STATEMENTS (11 + 13 = 24, grown
    to 25 by C3-R2's ``content_provenance``), nothing more, nothing less."""

    declared = tuple(
        statement.split("(", 1)[0].split()[-1] for statement in SCHEMA_STATEMENTS
    )
    assert len(declared) == 25
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


def test_two_subprocess_builds_with_different_hash_seeds_hash_equal(
    tmp_path: Path,
) -> None:
    """Cross-process determinism (C1 disposition F4): no ``hash()``
    randomization may reach the artifact's bytes. Two fresh interpreters with
    different ``PYTHONHASHSEED`` values build from the same source and the
    two artifacts hash equal."""

    script = (
        "import sys;"
        "from elc.content.build import build_content_db;"
        "build_content_db(sys.argv[1])"
    )
    src = str(REPO_ROOT / "src")
    digests: list[str] = []
    for seed in ("0", "12345"):
        output = tmp_path / f"seed-{seed}.db"
        env = dict(os.environ)
        env["PYTHONPATH"] = (
            src + os.pathsep + env["PYTHONPATH"]
            if env.get("PYTHONPATH")
            else src
        )
        env["PYTHONHASHSEED"] = seed
        subprocess.run(
            [sys.executable, "-c", script, str(output)],
            check=True,
            env=env,
            timeout=120,
        )
        digests.append(hashlib.sha256(output.read_bytes()).hexdigest())
    assert digests[0] == digests[1]


# ---------------------------------------------------------------------------
# ③ the corpus table and the per-fact pins
# ---------------------------------------------------------------------------


def test_readiness_by_target_is_sixteen_r4_forty_eight_r1_and_five_none(
    built_content_db: Path,
) -> None:
    """The corpus table on the real artifact, at C3-R1's truth: the sixteen
    RESOURCE targets whose §24.7 row is a curriculum mapping read
    R4_DETECTION_READY, the other forty-eight RESOURCE targets read
    R1_LEXICALLY_RESOLVED (their evidence is complete but their link is a
    coverage placement, so §8.1 R2 is not satisfied and the ladder stops at
    R1 — this is the *deliberate* fall-back, not a loss of evidence), and the
    five CAPABILITY entities read None — no level is invented for them, §8.1
    has no word below R0, and their sources state no evidence."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    table = {a.target_id: a.level for a in assessments.value}
    assert len(table) == 69
    res_targets = sorted(t for t in table if t.startswith("res-"))
    cap_targets = sorted(t for t in table if t.startswith("cap-"))
    assert len(res_targets) == 64 and len(cap_targets) == 5
    r4 = [t for t in res_targets if table[t] == "R4_DETECTION_READY"]
    r1 = [t for t in res_targets if table[t] == "R1_LEXICALLY_RESOLVED"]
    assert (len(r4), len(r1)) == (16, 48)
    # The split is exactly the link's mapping class — the level is read, and
    # it is the mapping set that carries it (the C3-R1 consistency pin).
    mapping_rows = set(_mapping_resource_ids(built_content_db))
    assert set(r4) == mapping_rows
    for target_id in cap_targets:
        assert table[target_id] is None, target_id
    assert sum(1 for level in table.values() if level is None) == 5


def _mapping_resource_ids(artifact: Path) -> tuple[str, ...]:
    """The resources whose §24.7 row declares CURRICULUM_MAPPING."""

    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT resource_id FROM curriculum_link "
            "WHERE mapping_class = 'CURRICULUM_MAPPING' ORDER BY resource_id"
        ).fetchall()
    finally:
        conn.close()
    return tuple(str(row[0]) for row in rows)


@pytest.mark.parametrize("key", READINESS_FACT_KEYS)
def test_every_fact_key_is_present_for_a_mapping_target(
    built_content_db: Path, key: str
) -> None:
    """Per-fact pin, present side: a target whose §24.7 row is a curriculum
    mapping satisfies all nineteen §8.1 fact keys (eighteen read from their
    own tables; ``entity_row`` proven by the preceding ``get_resource``
    success). The target is the C3-R1 mapping one — the C1-authored target
    no longer satisfies ``curriculum_link`` (its row is a placement), which
    the corpus-table test above pins instead."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(MAPPING_TARGET)
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


def _edit_evidence(
    text_edit: Callable[[dict], None], target: str = R4_TARGET
) -> Callable[[Path], None]:
    """An edit closure over one target's evidence document.

    Defaults to the C1-authored target (the loader tests below are about
    that document); the level tests pass ``MAPPING_TARGET`` because a target
    the ladder already stops at R1 cannot show an R3/R4 step moving.
    """

    def edit(content_src: Path) -> None:
        path = content_src / "evidence" / f"{target}.json"
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


def test_an_unknown_key_inside_a_block_is_refused(tmp_path: Path) -> None:
    """The strict reader's inner half (C1 disposition F3): ``_exact_keys``
    guards not only the document's block set but every block's key set, so a
    key neither §24 nor the declared reading names is refused, never ignored.
    Legal counterpart first: the canonical document — the same document
    without the invented key — builds."""

    legal = _build_edited(tmp_path / "legal", lambda content_src: None)
    assert legal.is_file()

    def invent_entry_key(document: dict) -> None:
        document["lexical_entry"]["paradigm"] = "make-decision VERB"

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path / "entry", _edit_evidence(invent_entry_key))
    assert "paradigm" in str(raised.value)

    def invent_row_key(document: dict) -> None:
        document["texts"][0]["bogus"] = "x"

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path / "row", _edit_evidence(invent_row_key))
    assert "bogus" in str(raised.value)


def test_an_empty_array_block_is_refused(tmp_path: Path) -> None:
    """An empty JSON array is never a stated fact (C1 disposition F3;
    content_src/README.md "空 JSON 数组 ⇒ BuildError"): "no rows" is stated
    by *omitting* the block. Legal counterpart first: the same document with
    the block omitted builds, and the omission reaches the read face as
    absence — the sense fact reads False and the table carries no rows."""

    def drop_senses(document: dict) -> None:
        del document["senses"]

    legal_artifact = _build_edited(tmp_path / "legal", _edit_evidence(drop_senses))
    conn = sqlite3.connect(str(legal_artifact))
    try:
        sense_rows = conn.execute(
            "SELECT COUNT(*) FROM content_sense "
            "WHERE entity_id = ?",
            (R4_TARGET,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert sense_rows == 0
    store = ContentStore(legal_artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(R4_TARGET)
        assert isinstance(facts, Ok), facts
    finally:
        store.close()
    assert facts.value.sense is False

    def empty_senses(document: dict) -> None:
        document["senses"] = []

    with pytest.raises(BuildError) as raised:
        _build_edited(tmp_path / "empty", _edit_evidence(empty_senses))
    assert "senses" in str(raised.value)


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
    evidence rows: every target reads None. Since C2-a the corpus lists nine
    evidence documents, so the variant unlists and removes all nine — the
    empty-list state is a property of the *source index*, not of one file."""

    def empty_evidence(content_src: Path) -> None:
        index_path = content_src / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for listed in index["evidence"]:
            (content_src / listed).unlink()
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
    ladder answers: ``typical_error_when_needed`` unsatisfied, level R2 — the
    variant is built over the C3-R1 mapping target, because R2 is where a
    target with a mapping link but an incomplete R3 set stops."""

    def drop_errors(document: dict) -> None:
        del document["typical_errors"]
        # `typical_error_required: true` stays declared.

    artifact = _build_edited(
        tmp_path, _edit_evidence(drop_errors, MAPPING_TARGET)
    )
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(MAPPING_TARGET)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(MAPPING_TARGET)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    assert facts.value.curriculum_link is True
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
    and the detection face is independent of it, so the level is still R4
    (the variant is built over the C3-R1 mapping target: R4 is reachable
    only where the §24.7 row is a mapping)."""

    def drop_need_and_errors(document: dict) -> None:
        del document["typical_errors"]
        del document["typical_error_required"]

    artifact = _build_edited(
        tmp_path, _edit_evidence(drop_need_and_errors, MAPPING_TARGET)
    )
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(MAPPING_TARGET)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(MAPPING_TARGET)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    assert facts.value.curriculum_link is True
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
    the fixture kinds are the declared three-word vocabulary (C3-R2 added
    POSITIVE_ERROR)."""

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
    # Every rule ordinal is bounded by a fixture at the same ordinal, the
    # kinds are exactly the declared vocabulary, and the positive-error rows
    # (C3-R2) are the only fixtures beyond the rule ordinals.
    positive_ordinals = [row[0] for row in fixtures if row[1] == "POSITIVE_ERROR"]
    assert set(rule_ordinals) | set(positive_ordinals) == set(fixture_ordinals)
    if positive_ordinals:
        assert min(positive_ordinals) > max(rule_ordinals)
    for _, kind, text, expected in fixtures:
        assert kind in ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY", "POSITIVE_ERROR"), kind
        assert text
        assert expected
        assert expected in ("NO_MATCH", "NO_MATCH_BOUNDARY", "MATCH"), expected
    kinds = {row[1] for row in fixtures}
    assert kinds == {"NEGATIVE", "FALSE_POSITIVE_BOUNDARY", "POSITIVE_ERROR"}


# ---------------------------------------------------------------------------
# ⑦ the C1 disposition pins (F5 role reads, F6 version, F7c reviewed, F10)
# ---------------------------------------------------------------------------


def test_the_r4_target_s_text_rows_are_pinned_per_role(
    built_content_db: Path,
) -> None:
    """C1 disposition F5: role reads are load-bearing. The artifact's
    ``content_text`` rows are pinned per role — row count **and** content —
    so a read that swapped the role word moves both."""
    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT role, ordinal, language, text FROM content_text "
            "WHERE entity_id = ? ORDER BY role, ordinal",
            (R4_TARGET,),
        ).fetchall()
    finally:
        conn.close()
    by_role: dict[str, list[tuple[int, str, str]]] = {}
    for role, ordinal, language, text in rows:
        by_role.setdefault(str(role), []).append(
            (int(ordinal), str(language), str(text))
        )
    assert {
        role: len(role_rows) for role, role_rows in sorted(by_role.items())
    } == {
        "definition": 1,
        "teaching_note": 1,
        "translation": 1,
        "usage": 1,
    }
    # The content half: the roles carry different sentences from the source,
    # so a swapped role predicate reads the wrong text, not just the wrong
    # count.
    assert by_role["definition"][0][2].startswith(
        "To choose one course of action"
    )
    assert by_role["usage"][0][2].startswith(
        "Used when the choice carries some weight"
    )
    assert by_role["teaching_note"][0][2].startswith("The light verb is make")
    assert by_role["translation"][0][:2] == (0, "zh")


def test_the_store_s_role_predicates_count_their_own_role(
    built_content_db: Path,
    tmp_path: Path,
) -> None:
    """C1 disposition F5, store half: the ``definitions`` /
    ``teaching_notes`` predicates count *their* role's rows. On the canonical
    artifact both roles answer 1 — indistinguishable by count — so the pin
    builds a variant whose source adds a second ``usage`` row: the store's
    ``definitions`` must stay 1 there (a predicate reading the wrong role
    would answer 2)."""

    store = ContentStore(built_content_db)
    try:
        canonical = store.evidence_counts(R4_TARGET)
        assert isinstance(canonical, Ok), canonical
    finally:
        store.close()
    assert canonical.value.definitions == 1
    assert canonical.value.teaching_notes == 1

    def add_second_usage(document: dict) -> None:
        usage_rows = [
            row for row in document["texts"] if row["role"] == "usage"
        ]
        extra = dict(usage_rows[0])
        extra["ordinal"] = 1
        document["texts"].append(extra)

    artifact = _build_edited(tmp_path, _edit_evidence(add_second_usage))
    conn = sqlite3.connect(str(artifact))
    try:
        usage_count = conn.execute(
            "SELECT COUNT(*) FROM content_text "
            "WHERE entity_id = ? AND role = 'usage'",
            (R4_TARGET,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert usage_count == 2
    store = ContentStore(artifact)
    try:
        counts = store.evidence_counts(R4_TARGET)
        assert isinstance(counts, Ok), counts
    finally:
        store.close()
    assert counts.value.definitions == 1
    assert counts.value.teaching_notes == 1


def test_an_evidence_less_target_reads_zero_rows_per_role(
    built_content_db: Path,
) -> None:
    """C1 disposition F5, zero side: an evidence-less target answers 0 rows
    in every role, through both the artifact and the store's counts."""
    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT role, COUNT(*) FROM content_text "
            "WHERE entity_id = ? GROUP BY role",
            (NO_EVIDENCE_TARGET,),
        ).fetchall()
    finally:
        conn.close()
    assert rows == []
    store = ContentStore(built_content_db)
    try:
        counts = store.evidence_counts(NO_EVIDENCE_TARGET)
        assert isinstance(counts, Ok), counts
    finally:
        store.close()
    assert counts.value.definitions == 0
    assert counts.value.teaching_notes == 0


def test_the_artifact_declares_the_bumped_content_db_version(
    built_content_db: Path,
) -> None:
    """C1 disposition F6, moved again by C3-R1 and C3-R2: the schema
    generation is explicit (docs/DATA_MODEL.md §26.1 requires the version to
    be updated explicitly, never guessed from the schema). C1 moved "1" →
    "2" with the table set (11 → 24); C3-R1 moved "2" → "3" with a column
    (``curriculum_link.mapping_class``); C3-R2 moves "3" → "4" with the
    ``content_provenance`` table (24 → 25), so a reader can always tell the
    artifact generations apart."""
    assert CONTENT_DB_VERSION == "4"
    conn = sqlite3.connect(str(built_content_db))
    try:
        row = conn.execute(
            "SELECT value FROM content_meta WHERE key = 'content_db_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == CONTENT_DB_VERSION == "4"


def test_reviewed_explanation_requires_the_approved_lifecycle(
    tmp_path: Path,
) -> None:
    """C1 disposition F7c: "reviewed" is read through the entity's §24.11
    editorial discipline — a ``teaching_note`` row **and** the entity's
    ``lifecycle_status`` being ``CANONICAL_APPROVED`` (the same editorial
    word the approved curriculum_link carries; no dedicated §24 marker on
    the note). A variant whose entity is not approved flips the fact while
    the note row stays, and the R3 set no longer completes (level falls to
    R2 — the variant is built over the C3-R1 mapping target, since a target
    whose link is a placement would stop at R1 before the R3 step could be
    observed)."""

    def demote_entity(content_src: Path) -> None:
        path = content_src / "entities" / f"{MAPPING_TARGET}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["entity"]["lifecycle_status"] = "PEDAGOGICALLY_ANNOTATED"
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    artifact = _build_edited(tmp_path, demote_entity)
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        facts = supply.readiness_facts(MAPPING_TARGET)
        assert isinstance(facts, Ok), facts
        assessment = supply.readiness(MAPPING_TARGET)
        assert isinstance(assessment, Ok), assessment
        counts = store.evidence_counts(MAPPING_TARGET)
        assert isinstance(counts, Ok), counts
    finally:
        store.close()
    # The note row is still there; the fact is still False.
    assert counts.value.teaching_notes == 1
    assert facts.value.curriculum_link is True
    assert facts.value.reviewed_explanation is False
    assert assessment.value.level == "R2_PLANNER_READY"


def test_unread_fact_evidence_entries_stay_well_formed() -> None:
    """C1 disposition F10: the loop that used to pin
    ``UNREAD_FACT_EVIDENCE``'s entry shape went silent when C1 emptied the
    set, so the shape requirement lives on here — whatever is registered
    later must carry a non-empty evidence description and a key the ladder
    actually declares (today the mapping is empty and the loop runs zero
    times; it is the guard, not a no-op claim)."""

    for key, evidence in UNREAD_FACT_EVIDENCE.items():
        assert evidence.strip(), (
            f"UNREAD_FACT_EVIDENCE[{key!r}] needs a non-empty evidence"
            " description"
        )
        assert key in READINESS_FACT_KEYS, key
