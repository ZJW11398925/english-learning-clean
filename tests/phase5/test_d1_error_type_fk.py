"""D-1 (Detector Executability Program) — POSITIVE_ERROR becomes a real
foreign key.

What this cut did, and what this file pins:

- **the source contract**: every ``POSITIVE_ERROR`` fixture row carries
  ``source_error_type`` — the declared §24.9 ``error_type`` the row
  instantiates. A positive row without the key, or naming a word the
  entity's ``typical_errors`` do not declare, is refused by the build; a
  ``source_error_type`` key on a NEGATIVE or FALSE_POSITIVE_BOUNDARY row is
  refused too (a non-error example instantiates no error type). Every
  declared error type must in turn be instantiated by at least one
  positive row naming it — the per-type coverage check that replaces the
  C3-R2 row-count proxy (registrations N-C3R2-1 / EXT-C3-01 closed).
- **the 196-row migration**: every pre-existing positive row gained
  exactly one key, appended after ``expected``; the other three keys and
  every NEGATIVE / FALSE_POSITIVE_BOUNDARY row are untouched — proven by
  the migrated projection digests in test_c3c/test_c3d (the frozen
  constants recomputed over the four original keys) and re-proven here
  from the artifact side.
- **the artifact**: ``content_detection_fixture`` gains the nullable
  ``source_error_type`` column; ``CONTENT_DB_VERSION`` moves "4" → "5".
- **what does not move**: the corpus truth (52 × R4 + 48 × R1 + 5 × None),
  the three calibration gates (32 / 20 / 100), the provenance derivation
  (54 × AUTHOR_DECLARED + 46 × EDITOR_REVIEWED), and the
  zero-executably-verified posture (D-1 is an FK contract, not a detector
  executor — EXECUTABLY_VERIFIED stays unreachable at 0).
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

import pytest

from elc.content.build import (
    CONTENT_DB_VERSION,
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    REPO_ROOT,
    SCHEMA_STATEMENTS,
    BuildError,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok

#: The fixture kinds that are NOT error instances — carrying the foreign
#: key on them is refused (the row declares a non-error).
NON_ERROR_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY")

#: The single-error entities (one declared type, one positive row each).
SINGLE_ERROR_TARGETS = (
    "res-discourse-anyway",
    "res-discourse-in-fact",
    "res-discourse-to-be-honest",
    "res-phrasal-figure-out",
)


# ---------------------------------------------------------------------------
# helpers (tmp copies only — the canonical tree is never edited)
# ---------------------------------------------------------------------------


def _evidence_variant(
    tmp_path: Path, target_id: str, edit
) -> None:
    """A tmp copy of both authoring trees with one evidence edit, built
    through the real build step. Returns nothing: every caller expects a
    BuildError and pytest.raises carries the assertion."""

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    path = content_src / "evidence" / f"{target_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    path.write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )
    build_content_db(
        tmp_path / "content.db",
        content_src_dir=content_src,
        curriculum_dir=curriculum,
    )


def _fixture_rows(artifact: Path) -> list[tuple]:
    """Every (entity_id, ordinal, kind, text, expected, source_error_type)
    row of the artifact, in (entity, ordinal) order."""

    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT entity_id, ordinal, kind, text, expected, "
            "source_error_type FROM content_detection_fixture "
            "ORDER BY entity_id, ordinal"
        ).fetchall()
    finally:
        conn.close()
    return [
        (str(a), int(b), str(c), str(d), str(e), f)
        for a, b, c, d, e, f in rows
    ]


def _levels(artifact: Path) -> dict[str, str | None]:
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        table = supply.readiness_by_target()
        assert isinstance(table, Ok), table
    finally:
        store.close()
    return {a.target_id: a.level for a in table.value}


def _core_counts(artifact: Path) -> tuple[int, int]:
    """CORE_A / CORE_C under the declared reading (the C3-a/C3-b rule)."""

    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
        levels = {a.target_id: a.level for a in assessments.value}
    finally:
        store.close()
    conn = sqlite3.connect(str(artifact))
    try:
        utilities = {
            str(e): str(u)
            for e, u in conn.execute(
                "SELECT entity_id, core_utility FROM "
                "content_pedagogical_profile"
            ).fetchall()
        }
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
    return core_a, core_c


# ---------------------------------------------------------------------------
# ① the artifact face: the column, the version, the row facts
# ---------------------------------------------------------------------------


def test_content_db_version_moves_to_five() -> None:
    """The module constant says "5" — D-1's column move, explicit per
    docs/DATA_MODEL.md §26.1 (the artifact's own copy is pinned in the
    migrated C1/C3-R2/C3-c/C3-d/C3-R1 version tests)."""

    assert CONTENT_DB_VERSION == "5"


def test_the_table_set_is_unchanged_at_twenty_five() -> None:
    """D-1 adds a column, not a table: the schema statement set is exactly
    what C3-R2 left (25 tables), content_detection_fixture among them."""

    names = tuple(
        statement.split("(", 1)[0].split()[-1]
        for statement in SCHEMA_STATEMENTS
    )
    assert len(names) == 25
    assert "content_detection_fixture" in names


def test_the_fixture_table_gains_the_source_error_type_column(
    built_content_db: Path,
) -> None:
    """The column list is the old five plus the nullable
    ``source_error_type``, in that order, and the primary key is unchanged."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        info = conn.execute(
            "PRAGMA table_info(content_detection_fixture)"
        ).fetchall()
    finally:
        conn.close()
    assert tuple(row[1] for row in info) == (
        "entity_id",
        "ordinal",
        "kind",
        "text",
        "expected",
        "source_error_type",
    )
    assert tuple(row[1] for row in info if row[5]) == (
        "entity_id",
        "ordinal",
    )


def test_the_artifact_still_counts_595_rows_with_196_positives(
    built_content_db: Path,
) -> None:
    """The corpus row counts did not move: 595 fixtures, 196 of them
    positive, the other 399 split 296 / 103."""

    rows = _fixture_rows(built_content_db)
    assert len(rows) == 595
    positives = [row for row in rows if row[2] == "POSITIVE_ERROR"]
    assert len(positives) == 196
    assert sum(1 for row in rows if row[2] == "NEGATIVE") == 296
    assert (
        sum(1 for row in rows if row[2] == "FALSE_POSITIVE_BOUNDARY") == 103
    )


def test_every_positive_row_is_non_null_and_every_other_row_is_null(
    built_content_db: Path,
) -> None:
    """The column's nullability is the contract read from the artifact:
    all 196 positive rows carry a name, and not one of the 399 non-error
    rows does (a negative or boundary example is not an error instance)."""

    rows = _fixture_rows(built_content_db)
    for entity_id, ordinal, kind, _text, _expected, source in rows:
        if kind == "POSITIVE_ERROR":
            assert isinstance(source, str) and source, (entity_id, ordinal)
        else:
            assert source is None, (entity_id, ordinal)


# ---------------------------------------------------------------------------
# ② the source truth: the 196-row migration, entity by entity
# ---------------------------------------------------------------------------


def test_every_positive_row_names_one_of_its_declared_error_types() -> None:
    """The real foreign key, read over the whole source tree: for each of
    the 100 evidence documents, every positive row's ``source_error_type``
    is one of that entity's declared §24.9 words, and every declared word
    is named by at least one positive row (the build's own two checks,
    re-read here from the files)."""

    checked = 0
    for path in sorted((CONTENT_SRC_DIR / "evidence").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        declared = {row["error_type"] for row in document["typical_errors"]}
        positives = [
            row
            for row in document["detection_fixtures"]
            if row["kind"] == "POSITIVE_ERROR"
        ]
        for row in positives:
            assert row["source_error_type"] in declared, (
                path.name,
                row["ordinal"],
            )
        named = {row["source_error_type"] for row in positives}
        assert named == declared, path.name
        checked += len(positives)
    assert checked == 196


def test_the_ordinal_correspondence_the_migration_used() -> None:
    """The migration's editorial correspondence, pinned as a machine check:
    within every entity the i-th positive row (by ordinal) instantiates the
    i-th declared error type (by ordinal) — every pair hand-verified
    against the row's text and the declared ``error_pattern`` at migration
    time, so a later re-pairing is a visible authoring act, not a drift."""

    for path in sorted((CONTENT_SRC_DIR / "evidence").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        declared = sorted(
            document["typical_errors"], key=lambda row: row["ordinal"]
        )
        positives = sorted(
            (
                row
                for row in document["detection_fixtures"]
                if row["kind"] == "POSITIVE_ERROR"
            ),
            key=lambda row: row["ordinal"],
        )
        assert [row["error_type"] for row in declared] == [
            row["source_error_type"] for row in positives
        ], path.name


def test_the_four_single_error_entities_keep_their_one_row(
    built_content_db: Path,
) -> None:
    """The single-type entities (one declared type, one positive row) are
    exactly the four registered ids, and each row names that type."""

    rows = _fixture_rows(built_content_db)
    for entity_id in SINGLE_ERROR_TARGETS:
        positives = [
            row for row in rows if row[0] == entity_id and row[2] == "POSITIVE_ERROR"
        ]
        assert len(positives) == 1, entity_id
    for path in sorted((CONTENT_SRC_DIR / "evidence").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        entity_id = path.stem
        declared = {row["error_type"] for row in document["typical_errors"]}
        if len(declared) == 1:
            assert entity_id in SINGLE_ERROR_TARGETS, entity_id


def test_a_sample_of_the_mapping_table_reads_the_declared_types(
    built_content_db: Path,
) -> None:
    """Named spot checks of the migration mapping (the receipt's per-entity
    table, sampled): the positive row's text and its named type agree the
    way the declared patterns state."""

    expected_pairs = {
        # (entity, text substring, named type)
        "res-colloc-make-a-decision": [
            ("done a decision", "LIGHT_VERB_CHOICE"),
            ("make decision", "ARTICLE_OMISSION"),
        ],
        "res-pragmatic-let-me-make-sure": [
            ("Let me to make sure", "INFINITIVE_MARKER_SLIP"),
            ("Let me making sure", "GERUND_SLIP"),
        ],
        "res-idiom-piece-of-cake": [
            ("was piece of cake", "ARTICLE_OMISSION"),
            ("pieces of cakes", "PLURALISED_UNIT"),
        ],
        "res-hedge-not-really": [
            ("Not real,", "DOUBLED_NEGATION"),
            ("layout? Not.", "SOFT_ANSWER_WITHOUT_REALLY"),
        ],
        "res-softener-if-anything": [
            ("If anything is,", "SPLIT_FIXED_PAIR"),
            (
                "this route takes longer",
                "MARKER_WITHOUT_A_STATEMENT",
            ),
        ],
    }
    rows = _fixture_rows(built_content_db)
    for entity_id, pairs in expected_pairs.items():
        positives = [
            row for row in rows if row[0] == entity_id and row[2] == "POSITIVE_ERROR"
        ]
        for substring, source_type in pairs:
            matches = [
                row
                for row in positives
                if substring in row[3] and row[5] == source_type
            ]
            assert matches, (entity_id, substring, source_type)


# ---------------------------------------------------------------------------
# ③ the refusals (each one a build-level contract, not a test-side check)
# ---------------------------------------------------------------------------


def test_a_positive_row_without_the_key_is_refused(tmp_path: Path) -> None:
    """Deleting the ``source_error_type`` key from a positive row is a key
    mismatch, refused like any other undeclared shape."""

    def edit(document: dict) -> None:
        for row in document["detection_fixtures"]:
            if row["kind"] == "POSITIVE_ERROR":
                del row["source_error_type"]
                return
        raise AssertionError("no positive row")

    with pytest.raises(BuildError, match="source_error_type"):
        _evidence_variant(tmp_path, "res-discourse-anyway", edit)


def test_a_dangling_error_type_is_refused_with_the_legal_set(
    tmp_path: Path,
) -> None:
    """A positive row naming a word the entity does not declare is refused,
    and the error message carries the entity's legal set."""

    def edit(document: dict) -> None:
        for row in document["detection_fixtures"]:
            if row["kind"] == "POSITIVE_ERROR":
                row["source_error_type"] = "NOT_A_DECLARED_TYPE"
                return
        raise AssertionError("no positive row")

    with pytest.raises(BuildError) as raised:
        _evidence_variant(tmp_path, "res-hedge-i-think", edit)
    message = str(raised.value)
    assert "NOT_A_DECLARED_TYPE" in message
    assert "SUBJECT_OMISSION" in message
    assert "COMMA_INTRUSION" in message


def test_removing_a_declared_type_dangles_its_positive_row(
    tmp_path: Path,
) -> None:
    """Declaring one fewer error type while keeping both positive rows
    leaves one row dangling — refused by the same foreign key (the
    declared set is the only legal value domain)."""

    def edit(document: dict) -> None:
        errors = document["typical_errors"]
        assert len(errors) == 2
        del errors[1]
        for row in document["detection_fixtures"]:
            if row["ordinal"] == 4:
                row["source_error_type"] = errors[0]["error_type"]
                return

    with pytest.raises(BuildError, match="not one of the entity's declared"):
        _evidence_variant(tmp_path, "res-pragmatic-got-it", edit)


def test_repointing_a_row_leaves_its_type_uncovered(tmp_path: Path) -> None:
    """Both positive rows naming the same declared type leaves the other
    declared type with no instantiating row — the per-type coverage check
    refuses and names the uncovered type (the D-1 replacement for the
    row-count proxy, which could only compare counts)."""

    def edit(document: dict) -> None:
        types = [row["error_type"] for row in document["typical_errors"]]
        assert len(types) == 2
        for row in document["detection_fixtures"]:
            if row["kind"] == "POSITIVE_ERROR" and row["ordinal"] == 4:
                row["source_error_type"] = types[1]
                return
        raise AssertionError("ordinal 4 not found")

    with pytest.raises(BuildError, match="no POSITIVE_ERROR fixture"):
        _evidence_variant(tmp_path, "res-colloc-make-a-decision", edit)


@pytest.mark.parametrize("kind", NON_ERROR_KINDS)
def test_a_non_error_row_carrying_the_key_is_refused(
    tmp_path: Path, kind: str
) -> None:
    """A NEGATIVE or FALSE_POSITIVE_BOUNDARY row naming a source error
    contradicts the row's own declared non-error reading — refused, not
    tolerated. (The build's chosen reading of the D-1 boundary: the key is
    POSITIVE_ERROR-only, disclosed in the receipt.)"""

    def edit(document: dict) -> None:
        for row in document["detection_fixtures"]:
            if row["kind"] == kind:
                row["source_error_type"] = "SOME_TYPE"
                return
        raise AssertionError(kind)

    with pytest.raises(BuildError, match="unknown=\\['source_error_type'\\]"):
        _evidence_variant(tmp_path, "res-hedge-i-think", edit)


# ---------------------------------------------------------------------------
# ④ the build stays deterministic
# ---------------------------------------------------------------------------


def test_two_builds_are_byte_identical(tmp_path: Path) -> None:
    """Same source, same bytes: the migrated tree builds identically twice
    (the new column rides the deterministic DDL and the ordinal-ordered
    inserts)."""

    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    build_content_db(first)
    build_content_db(second)
    assert first.read_bytes() == second.read_bytes()


def test_cross_process_determinism_with_three_hash_seeds(
    tmp_path: Path,
) -> None:
    """Three fresh interpreters with different ``PYTHONHASHSEED`` values
    build the migrated source and the three artifacts hash equal."""

    script = (
        "import sys;"
        "from pathlib import Path;"
        "from elc.content.build import build_content_db;"
        "build_content_db("
        "Path(sys.argv[1]), "
        f"content_src_dir=Path(r'{CONTENT_SRC_DIR}'), "
        f"curriculum_dir=Path(r'{CURRICULUM_DIR}'))"
    )
    src = str(REPO_ROOT / "src")
    digests: list[str] = []
    for seed in ("0", "12345", "random"):
        output = tmp_path / f"seed-{seed}.db"
        env = dict(os.environ)
        env["PYTHONPATH"] = src
        env["PYTHONHASHSEED"] = seed
        subprocess.run(
            [sys.executable, "-c", script, str(output)],
            check=True,
            env=env,
        )
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        digests.append(digest)
    assert len(set(digests)) == 1


# ---------------------------------------------------------------------------
# ⑤ what does not move (the honesty face)
# ---------------------------------------------------------------------------


def test_the_readiness_truth_is_unchanged_52_48_5(
    built_content_db: Path,
) -> None:
    """52 × R4 + 48 × R1 + 5 × None — the FK contract moves no level: a
    column addition never retires or grants §8.1 evidence."""

    table = _levels(built_content_db)
    assert len(table) == 105
    r4 = sum(1 for v in table.values() if v == "R4_DETECTION_READY")
    r1 = sum(1 for v in table.values() if v == "R1_LEXICALLY_RESOLVED")
    none = sum(1 for v in table.values() if v is None)
    assert (r4, r1, none) == (52, 48, 5)


def test_the_three_calibration_gates_unchanged_32_20_100(
    built_content_db: Path,
) -> None:
    """CORE_A 32 / CORE_C 20 / resource_count 100 — unchanged, and no
    rollout opening is claimed: the floors are the volume gate's answer,
    not the rollout's."""

    core_a, core_c = _core_counts(built_content_db)
    resources = [
        t for t in _levels(built_content_db) if t.startswith("res-")
    ]
    print(
        f"[d1] CORE_A = {core_a}/30, CORE_C = {core_c}/2, "
        f"resource_count = {len(resources)}/100"
    )
    assert core_a == 32
    assert core_c == 20
    assert len(resources) == 100


def test_provenance_unchanged_54_author_46_editor(
    built_content_db: Path,
) -> None:
    """The provenance derivation reads exactly as before the column: 100
    rows, 54 × AUTHOR_DECLARED + 46 × EDITOR_REVIEWED — an FK contract is
    not an audit record, so nothing is promoted."""

    store = ContentStore(built_content_db)
    try:
        rows = store.provenance_levels()
        assert isinstance(rows, Ok), rows
    finally:
        store.close()
    levels = [level for _entity, level in rows.value]
    assert len(levels) == 100
    assert levels.count("AUTHOR_DECLARED") == 54
    assert levels.count("EDITOR_REVIEWED") == 46


def test_no_detector_executability_is_claimed(
    built_content_db: Path,
) -> None:
    """D-1 is a source contract, not a detector executor:
    EXECUTABLY_VERIFIED and EMPIRICALLY_CALIBRATED stay at zero rows — the
    honesty posture D-3 will move, one pilot at a time, never this cut."""

    store = ContentStore(built_content_db)
    try:
        rows = store.provenance_levels()
        assert isinstance(rows, Ok), rows
    finally:
        store.close()
    higher = [
        level
        for _entity, level in rows.value
        if level in ("EXECUTABLY_VERIFIED", "EMPIRICALLY_CALIBRATED")
    ]
    assert higher == []
