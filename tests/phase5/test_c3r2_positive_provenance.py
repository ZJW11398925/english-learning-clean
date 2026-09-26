"""C3-R2 (Phase 11) — POSITIVE_ERROR fixtures + structurally derived
provenance.

What this cut did, and what this file pins:

- **the third fixture word**: ``DETECTION_FIXTURE_KINDS`` grows
  ``POSITIVE_ERROR`` — a real learner-error production the declared
  detection rules must fire on, whose expected reading is ``MATCH``. The
  external review's HIGH-2 was that a detector stub answering ``NO_MATCH``
  to everything could pass a negative-only fixture set; the stubs below now
  fail it (§④). The word is still a **declared reading** of docs/
  DATA_MODEL.md §24.10 (which names no word list), and the closure is an
  *existence* closure: the corpus now carries rows a lying stub cannot
  satisfy — nothing here claims a detector executor exists (the N21
  registration stands);
- **the pairing as a source contract**: ``DETECTION_FIXTURE_EXPECTED_BY_
  KIND`` decides the expected side of every row; a row that disagrees with
  its own kind is refused by the build (the c2-a review F4 rule, now at
  build level, covering the pre-existing 255 rows too);
- **per-type coverage**: every declared ``error_type`` needs at least one
  POSITIVE_ERROR row (124 positive rows over the corpus: 60 entities × 2
  error types + 4 entities × 1). The build checks the *structure* only —
  the English itself is judged by review, not by code;
- **derived provenance**: ``content_provenance`` (the 25th table) carries
  one level per documented entity — ``AUTHOR_DECLARED`` for the bare
  evidence baseline, ``EDITOR_REVIEWED`` once an audit record in
  `content_src/audits/` approves the entity. The two stronger words of
  ``PROVENANCE_LEVELS`` are reachable today by nothing: no derivation
  produces them (no detector executor, no real-run data), and their
  conditions are written on the constant. The dimension is independent of
  the §8.1 ladder by construction: ``READINESS_FACT_KEYS`` gains no key,
  and the truth table, the three Calibration100 gates and the four content
  rows all read exactly as they did at C3-R1.

The repository's own `content_src/audits/` carries one record since the
disposition cut (`c3r2-stratified-audit.json`, the fifteen entities the
review's stratified audit passed on both faces), so the canonical corpus
reads 49 × AUTHOR_DECLARED + 15 × EDITOR_REVIEWED; the audit variants below
build from pytest tmp copies, never from the canonical tree.
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
    AUDITS_DIRNAME,
    CONTENT_DB_VERSION,
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    REPO_ROOT,
    SCHEMA_STATEMENTS,
    BuildError,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.content.types import (
    DETECTION_FIXTURE_EXPECTED_BY_KIND,
    DETECTION_FIXTURE_KINDS,
    PROVENANCE_LEVELS,
)
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok

#: The three declared fixture kinds, C3-R2's third word included.
THREE_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY", "POSITIVE_ERROR")

#: The kind→expected pairing, mirrored here so a drift in the constant
#: itself is caught by comparing against this literal.
PAIRING = {
    "NEGATIVE": "NO_MATCH",
    "FALSE_POSITIVE_BOUNDARY": "NO_MATCH_BOUNDARY",
    "POSITIVE_ERROR": "MATCH",
}

#: The four entities whose source declares exactly one typical error (the
#: other sixty declare two): one positive row each.
SINGLE_ERROR_TARGETS = (
    "res-discourse-anyway",
    "res-discourse-in-fact",
    "res-discourse-to-be-honest",
    "res-phrasal-figure-out",
)

#: The provenance words no derivation produces today.
UNREACHABLE_LEVELS = ("EXECUTABLY_VERIFIED", "EMPIRICALLY_CALIBRATED")

#: The fifteen entities the review's stratified audit passed on both faces
#: (16 audited; res-softener-if-anything withheld pending its detection-rules
#: reconciliation) — the disposition cut's audit record approves exactly these,
#: and the record's own list must equal this set.
AUDITED_PASS_ENTITIES = (
    "res-colloc-keep-in-mind",
    "res-colloc-make-a-decision",
    "res-colloc-pay-attention-to",
    "res-discourse-anyway",
    "res-discourse-to-be-honest",
    "res-frame-just-wondering",
    "res-frame-what-im-saying-is",
    "res-hedge-i-guess",
    "res-hedge-i-think",
    "res-idiom-break-the-ice",
    "res-phrasal-figure-out",
    "res-phrasal-turn-out",
    "res-pragmatic-could-you",
    "res-pragmatic-no-offense-but",
    "res-softener-kind-of",
)


# ---------------------------------------------------------------------------
# helpers (tmp copies only — the canonical tree is never edited)
# ---------------------------------------------------------------------------


def _evidence_variant(
    tmp_path: Path, target_id: str, edit
) -> Path:
    """A tmp copy of both authoring trees with one evidence edit, built
    through the real build step."""

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
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


def _audits_variant(tmp_path: Path, records: list[dict]) -> Path:
    """A tmp copy whose `content_src/audits/` carries exactly these records.

    The canonical audits directory is *replaced*, not copied: the variant's
    audit state is these records alone, so the assertions below stay about
    the record under test and not about whatever the repository's own
    audit history happens to carry."""

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(
        CONTENT_SRC_DIR, content_src, ignore=shutil.ignore_patterns(AUDITS_DIRNAME)
    )
    shutil.copytree(CURRICULUM_DIR, curriculum)
    audits = content_src / AUDITS_DIRNAME
    audits.mkdir()
    for index, record in enumerate(records):
        (audits / f"audit-{index:02d}.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


def _fixtures(artifact: Path) -> list[tuple[str, int, str, str, str]]:
    """Every (entity_id, ordinal, kind, text, expected) row of the artifact,
    in (entity, ordinal) order."""

    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT entity_id, ordinal, kind, text, expected "
            "FROM content_detection_fixture ORDER BY entity_id, ordinal"
        ).fetchall()
    finally:
        conn.close()
    return [
        (str(a), int(b), str(c), str(d), str(e)) for a, b, c, d, e in rows
    ]


def _provenance(artifact: Path) -> dict[str, str]:
    store = ContentStore(artifact)
    try:
        levels = store.provenance_levels()
        assert isinstance(levels, Ok), levels
    finally:
        store.close()
    return dict(levels.value)


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
    """CORE_A / CORE_C under the declared reading (the c3-a/c3-b rule)."""

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
# ① the three-word vocabulary and the kind↔expected pairing
# ---------------------------------------------------------------------------


def test_the_fixture_vocabulary_now_carries_three_words() -> None:
    """The declared vocabulary and the pairing constant agree, and the third
    word is a declared reading (the docs/ text is untouched)."""

    assert DETECTION_FIXTURE_KINDS == THREE_KINDS
    assert "POSITIVE_ERROR" in DETECTION_FIXTURE_KINDS
    assert set(DETECTION_FIXTURE_EXPECTED_BY_KIND) == set(THREE_KINDS)
    for kind, expected in PAIRING.items():
        assert DETECTION_FIXTURE_EXPECTED_BY_KIND[kind] == expected
    assert len(PROVENANCE_LEVELS) == 4  # sanity: the file's other constant


def test_every_corpus_row_reads_the_declared_pairing(
    built_content_db: Path,
) -> None:
    """The pairing holds over the whole artifact — the pre-existing 255 rows
    included (they already read the pairing; now the build enforces it)."""

    fixtures = _fixtures(built_content_db)
    assert len(fixtures) == 379  # 255 pre-existing + 124 positive
    for entity_id, ordinal, kind, text, expected in fixtures:
        assert DETECTION_FIXTURE_EXPECTED_BY_KIND[kind] == expected, (
            entity_id,
            ordinal,
        )
        assert text, (entity_id, ordinal)


def test_each_documented_entity_carries_all_three_kinds(
    built_content_db: Path,
) -> None:
    """Every documented resource's kind set is the full vocabulary — the
    positive row exists, next to the negatives and the boundary."""

    by_entity: dict[str, set[str]] = {}
    for entity_id, _ordinal, kind, _text, _expected in _fixtures(
        built_content_db
    ):
        by_entity.setdefault(entity_id, set()).add(kind)
    assert sorted(by_entity) == sorted(_res_ids(built_content_db))
    for entity_id, kinds in by_entity.items():
        assert kinds == set(THREE_KINDS), entity_id


def _res_ids(artifact: Path) -> list[str]:
    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT entity_id FROM content_entity WHERE entity_id LIKE 'res-%'"
        ).fetchall()
    finally:
        conn.close()
    return [str(row[0]) for row in rows]


@pytest.mark.parametrize(
    ("kind", "wrong_expected"),
    [
        ("NEGATIVE", "MATCH"),
        ("FALSE_POSITIVE_BOUNDARY", "MATCH"),
        ("POSITIVE_ERROR", "NO_MATCH"),
    ],
)
def test_a_row_that_disagrees_with_its_kind_is_refused(
    tmp_path: Path, kind: str, wrong_expected: str
) -> None:
    """Three wrong pairings, one per kind, each refused by the build (the
    error names the legal reading)."""

    def edit(document: dict) -> None:
        for row in document["detection_fixtures"]:
            if row["kind"] == kind:
                row["expected"] = wrong_expected
                return
        raise AssertionError(kind)

    with pytest.raises(BuildError) as raised:
        _evidence_variant(
            tmp_path, "res-colloc-make-a-decision", edit
        )
    assert f"expects '{PAIRING[kind]}'" in str(raised.value)


def test_an_unknown_fixture_kind_is_refused(tmp_path: Path) -> None:
    """The vocabulary is closed: a fourth word is refused like any other
    value outside a declared set."""

    def edit(document: dict) -> None:
        document["detection_fixtures"][0]["kind"] = "POSITIVE_CONFIRMED"

    with pytest.raises(BuildError) as raised:
        _evidence_variant(tmp_path, "res-hedge-i-think", edit)
    assert "POSITIVE_CONFIRMED" in str(raised.value)


# ---------------------------------------------------------------------------
# ② the per-type coverage rule (refusals)
# ---------------------------------------------------------------------------


def test_deleting_the_single_positive_row_is_refused(tmp_path: Path) -> None:
    """A single-error entity with its positive row deleted fails the
    coverage check (one declared type, zero positive rows)."""

    def edit(document: dict) -> None:
        document["detection_fixtures"] = [
            row
            for row in document["detection_fixtures"]
            if row["kind"] != "POSITIVE_ERROR"
        ]

    with pytest.raises(BuildError) as raised:
        _evidence_variant(tmp_path, "res-discourse-anyway", edit)
    assert "POSITIVE_ERROR" in str(raised.value)


def test_deleting_one_of_two_positive_rows_is_refused(
    tmp_path: Path,
) -> None:
    """A two-error entity keeps needing one positive row per type: with two
    declared types and one row left, the count check refuses the source."""

    def edit(document: dict) -> None:
        positives = [
            row
            for row in document["detection_fixtures"]
            if row["kind"] == "POSITIVE_ERROR"
        ]
        assert len(positives) == 2
        document["detection_fixtures"] = [
            row
            for row in document["detection_fixtures"]
            if row is not positives[0]
        ]

    with pytest.raises(BuildError) as raised:
        _evidence_variant(tmp_path, "res-colloc-make-a-decision", edit)
    assert "2 declared error_type(s)" in str(raised.value)


# ---------------------------------------------------------------------------
# ③ the source-level coverage table
# ---------------------------------------------------------------------------


def test_every_declared_error_type_has_a_positive_row(
    built_content_db: Path,
) -> None:
    """Source-level coverage: for every documented entity, the positive row
    count covers its distinct declared error types, positives append after
    the rule-bounded ordinals, and the corpus total meets the 124 floor."""

    total_positive = 0
    for path in sorted((CONTENT_SRC_DIR / "evidence").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        types = {row["error_type"] for row in document["typical_errors"]}
        fixtures = document["detection_fixtures"]
        positives = [f for f in fixtures if f["kind"] == "POSITIVE_ERROR"]
        bounded = [f for f in fixtures if f["kind"] != "POSITIVE_ERROR"]
        assert len(positives) >= len(types), path.name
        rule_ords = sorted(
            int(r["ordinal"]) for r in document["detection_rules"]
        )
        assert [int(f["ordinal"]) for f in bounded] == rule_ords, path.name
        if positives:
            max_bounded = max(int(f["ordinal"]) for f in bounded)
            assert [int(f["ordinal"]) for f in positives] == list(
                range(max_bounded + 1, max_bounded + 1 + len(positives))
            ), path.name
        total_positive += len(positives)
    print(f"[c3r2] POSITIVE_ERROR rows = {total_positive} (floor 124)")
    assert total_positive >= 124
    assert total_positive == sum(
        1
        for _e, _o, kind, _t, _x in _fixtures(built_content_db)
        if kind == "POSITIVE_ERROR"
    )


def test_the_four_single_error_entities_and_their_positive_rows(
    built_content_db: Path,
) -> None:
    """The four single-error entities are exactly this list, one positive
    row each; every other documented entity declares two and carries two."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT entity_id, COUNT(*) FROM content_typical_error "
            "GROUP BY entity_id ORDER BY entity_id"
        ).fetchall()
        positives = dict(
            conn.execute(
                "SELECT entity_id, COUNT(*) FROM content_detection_fixture "
                "WHERE kind = 'POSITIVE_ERROR' GROUP BY entity_id"
            ).fetchall()
        )
    finally:
        conn.close()
    singles = {
        str(e): int(n) for e, n in rows if int(n) == 1
    }
    assert sorted(singles) == sorted(SINGLE_ERROR_TARGETS)
    for entity_id in SINGLE_ERROR_TARGETS:
        assert positives[str(entity_id)] == 1, entity_id
    twos = {str(e): int(n) for e, n in rows if int(n) == 2}
    for entity_id, count in twos.items():
        assert positives[entity_id] == count, entity_id


def test_the_store_reports_positive_error_counts(
    built_content_db: Path,
) -> None:
    """The evidence-count face gained the ``positive_errors`` report field
    (a report, not a ladder key): it reads the positive rows per entity and
    totals to the corpus count."""

    store = ContentStore(built_content_db)
    try:
        total = 0
        for entity_id in _res_ids(built_content_db):
            counts = store.evidence_counts(entity_id)
            assert isinstance(counts, Ok), counts
            total += counts.value.positive_errors
        first = store.evidence_counts(_res_ids(built_content_db)[0])
        assert isinstance(first, Ok), first
        # The three fixture fields report the three kinds.
        assert (
            first.value.negative_fixtures
            + first.value.false_positive_boundaries
            + first.value.positive_errors
        ) == len(
            [
                row
                for row in _fixtures(built_content_db)
                if row[0] == _res_ids(built_content_db)[0]
            ]
        )
    finally:
        store.close()
    assert total == 124


# ---------------------------------------------------------------------------
# ④ the stub closure (existence logic — no detector is claimed)
# ---------------------------------------------------------------------------


def _stub_failures(artifact: Path, stub_answer: str) -> int:
    """How many fixture rows a stub answering ``stub_answer`` to every text
    would fail. This is the existence logic the HIGH-2 closure rests on: the
    corpus now carries rows whose declared reading the stub cannot produce.
    No executor is claimed or used — the rows and their declared readings
    are compared directly."""

    return sum(
        1
        for _e, _o, _k, _t, expected in _fixtures(artifact)
        if expected != stub_answer
    )


def test_an_always_no_match_stub_fails_every_positive_row(
    built_content_db: Path,
) -> None:
    """The HIGH-2 stub (answering NO_MATCH to everything) now fails the
    fixture set — exactly on the positive rows (124), where it cannot
    produce the declared MATCH."""

    failures = _stub_failures(built_content_db, "NO_MATCH")
    # It fails every one of the 124 positive rows (its declared MATCH is
    # unreachable for the stub) plus the 67 boundary rows whose declared
    # reading is NO_MATCH_BOUNDARY — 191 rows in total, so the stub can no
    # longer pass the set.
    positive_failures = sum(
        1
        for _e, _o, _k, _t, expected in _fixtures(built_content_db)
        if expected == "MATCH"
    )
    assert positive_failures == 124
    print(f"[c3r2] always-NO_MATCH stub fails {failures} rows (>= 124)")
    assert failures >= 124
    assert failures == 191


def test_an_always_match_stub_fails_every_negative_row(
    built_content_db: Path,
) -> None:
    """The mirror stub (answering MATCH to everything) fails the set too —
    on the 255 rows whose declared reading is not MATCH."""

    assert _stub_failures(built_content_db, "MATCH") == 255
    assert _stub_failures(built_content_db, "NO_MATCH_BOUNDARY") == 312


# ---------------------------------------------------------------------------
# ⑤ derived provenance
# ---------------------------------------------------------------------------


def test_the_repository_audit_record_raises_fifteen_entities(
    built_content_db: Path,
) -> None:
    """The repository's own audit record (landed by the disposition cut from
    the review's stratified audit) promotes exactly the fifteen entities that
    passed both audit faces; the other forty-nine documented entities stay at
    the AUTHOR_DECLARED baseline, no capability row exists at all, and no
    row reaches the two words no derivation produces."""

    levels = _provenance(built_content_db)
    assert len(levels) == 64
    assert all(entity_id.startswith("res-") for entity_id in levels)
    reviewed = {
        entity_id for entity_id, level in levels.items()
        if level == "EDITOR_REVIEWED"
    }
    assert reviewed == set(AUDITED_PASS_ENTITIES)
    assert sum(1 for level in levels.values() if level == "AUTHOR_DECLARED") == 49
    assert not (set(levels.values()) & set(UNREACHABLE_LEVELS))
    # The read face and the table agree (one read, already checked above).
    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM content_provenance"
        ).fetchone()
    finally:
        conn.close()
    assert int(rows[0]) == 64


def test_an_audit_approval_raises_the_entity_to_editor_reviewed(
    tmp_path: Path,
) -> None:
    """An audit record promotes exactly the entities it approves; everyone
    else stays at the baseline (the record is a third-party fact, so an
    author cannot promote their own work)."""

    artifact = _audits_variant(
        tmp_path,
        [
            {
                "audit_id": "c3r2-review-sample",
                "performed_by": "independent reviewer (executor-pro)",
                "basis": "C3-R2 layered sampling protocol: content "
                "linguistic face + link judgement against the functional "
                "definitions",
                "approved_entities": [
                    "res-colloc-make-a-decision",
                    "res-hedge-i-think",
                ],
            }
        ],
    )
    levels = _provenance(artifact)
    assert levels["res-colloc-make-a-decision"] == "EDITOR_REVIEWED"
    assert levels["res-hedge-i-think"] == "EDITOR_REVIEWED"
    assert len(levels) == 64
    assert sum(1 for v in levels.values() if v == "EDITOR_REVIEWED") == 2
    assert sum(1 for v in levels.values() if v == "AUTHOR_DECLARED") == 62


def test_no_derivation_produces_the_two_higher_levels(
    tmp_path: Path,
) -> None:
    """EXECUTABLY_VERIFIED / EMPIRICALLY_CALIBRATED stay reachable-only:
    even with audit records present, no derivation emits them (no detector
    executor N21; no real-run data — rollout HOLD)."""

    artifact = _audits_variant(
        tmp_path,
        [
            {
                "audit_id": "audit-a",
                "performed_by": "reviewer",
                "basis": "sampling",
                "approved_entities": ["res-hedge-i-think"],
            }
        ],
    )
    levels = _provenance(artifact)
    for word in UNREACHABLE_LEVELS:
        assert word not in levels.values()
    assert set(levels.values()) <= set(PROVENANCE_LEVELS)


def test_an_audit_for_an_undocumented_entity_writes_no_row(
    tmp_path: Path,
) -> None:
    """An audit may only approve declared entities, and a documented row
    comes only from evidence: approving nothing documented would leave the
    table empty. (The dangling case is refused — see the refusals below.)"""

    artifact = _audits_variant(
        tmp_path,
        [
            {
                "audit_id": "audit-empty",
                "performed_by": "reviewer",
                "basis": "nothing approved yet",
                "approved_entities": [],
            }
        ],
    )
    levels = _provenance(artifact)
    assert set(levels.values()) == {"AUTHOR_DECLARED"}


# ---------------------------------------------------------------------------
# ⑥ the ladder independence (the hard boundary)
# ---------------------------------------------------------------------------


def test_readiness_fact_keys_gain_no_provenance_key() -> None:
    """Provenance never enters the §8.1 ladder: no fact key mentions it."""

    assert all(
        "PROVENANCE" not in key and "provenance" not in key
        for key in READINESS_FACT_KEYS
    )


def test_the_readiness_truth_table_is_exactly_unchanged(
    built_content_db: Path,
) -> None:
    """16 × R4 + 48 × R1 + 5 × None — the C3-R1 truth, re-pinned after this
    cut (counted, plus five named ids per band as spot checks)."""

    table = _levels(built_content_db)
    assert len(table) == 69
    r4 = sorted(
        t for t, v in table.items() if v == "R4_DETECTION_READY"
    )
    r1 = sorted(
        t for t, v in table.items() if v == "R1_LEXICALLY_RESOLVED"
    )
    none = sorted(t for t, v in table.items() if v is None)
    assert (len(r4), len(r1), len(none)) == (16, 48, 5)
    # Five named ids per band (the full sets are pinned by c3-r1's tests).
    assert {
        "res-discourse-anyway",
        "res-hedge-i-think",
        "res-softener-a-bit",
        "res-pragmatic-no-offense-but",
        "res-softener-to-be-fair",
    } <= set(r4)
    assert {
        "res-colloc-make-a-decision",
        "res-colloc-heavy-rain",
        "res-phrasal-bring-up",
        "res-idiom-piece-of-cake",
        "res-frame-lets-say",
    } <= set(r1)
    assert all(t.startswith("cap-") for t in none)


# ---------------------------------------------------------------------------
# ⑦ the gates read exactly as at C3-R1
# ---------------------------------------------------------------------------


def test_the_three_calibration_gates_are_unchanged(
    built_content_db: Path,
) -> None:
    """CORE_A 11 (unmet) / CORE_C 5 (met) / resource_count 64 (unmet) — the
    C3-R1 readings, to the value. No rollout opening is claimed."""

    core_a, core_c = _core_counts(built_content_db)
    resources = [t for t in _levels(built_content_db) if t.startswith("res-")]
    print(
        f"[c3r2] CORE_A = {core_a}/30, CORE_C = {core_c}/2, "
        f"resource_count = {len(resources)}/100"
    )
    assert core_a == 11
    assert core_c == 5
    assert len(resources) == 64


def test_the_four_content_rows_still_read_go(
    built_content_db: Path,
) -> None:
    """BF-02 §10's four content rows stay GO (>= 1 R4 target)."""

    r4 = [
        t for t, v in _levels(built_content_db).items()
        if v == "R4_DETECTION_READY"
    ]
    assert len(r4) >= 1
    assert "res-hedge-i-think" in r4


# ---------------------------------------------------------------------------
# ⑧ the artifact version and table set
# ---------------------------------------------------------------------------


def test_content_db_version_moves_to_four(
    built_content_db: Path,
) -> None:
    """CONTENT_DB_VERSION = "4", in the module and in the artifact's own
    content_meta (the explicit-bump discipline of §26.1)."""

    assert CONTENT_DB_VERSION == "4"
    conn = sqlite3.connect(str(built_content_db))
    try:
        row = conn.execute(
            "SELECT value FROM content_meta WHERE key = 'content_db_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and str(row[0]) == "4"


def test_the_artifact_has_exactly_twenty_five_tables(
    built_content_db: Path,
) -> None:
    """The 25th table is content_provenance; the artifact's table set is
    exactly SCHEMA_STATEMENTS, nothing more, nothing less."""

    declared = tuple(
        statement.split("(", 1)[0].split()[-1]
        for statement in SCHEMA_STATEMENTS
    )
    assert len(declared) == 25
    assert declared[-1] == "content_provenance"
    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    assert tuple(str(row[0]) for row in rows) == tuple(sorted(declared))


# ---------------------------------------------------------------------------
# ⑨ audit record refusals
# ---------------------------------------------------------------------------


def test_an_audit_naming_an_unknown_entity_is_refused(
    tmp_path: Path,
) -> None:
    """A provenance approval may not dangle: an unknown entity id is a
    BuildError, not a silent no-op."""

    with pytest.raises(BuildError) as raised:
        _audits_variant(
            tmp_path,
            [
                {
                    "audit_id": "audit-bad",
                    "performed_by": "reviewer",
                    "basis": "sampling",
                    "approved_entities": ["res-does-not-exist"],
                }
            ],
        )
    assert "res-does-not-exist" in str(raised.value)


def test_an_audit_missing_a_required_key_is_refused(
    tmp_path: Path,
) -> None:
    """The strict minimum (audit_id / performed_by / basis /
    approved_entities) is strict: a record without ``performed_by`` says
    nothing about who reviewed, so it is refused."""

    with pytest.raises(BuildError) as raised:
        _audits_variant(
            tmp_path,
            [
                {
                    "audit_id": "audit-thin",
                    "basis": "sampling",
                    "approved_entities": ["res-hedge-i-think"],
                }
            ],
        )
    assert "performed_by" in str(raised.value)


def test_an_audit_with_an_unknown_key_is_refused(tmp_path: Path) -> None:
    """No ignore-extra-keys switch: a typo'd key is refused."""

    with pytest.raises(BuildError) as raised:
        _audits_variant(
            tmp_path,
            [
                {
                    "audit_id": "audit-extra",
                    "performed_by": "reviewer",
                    "basis": "sampling",
                    "approved_entities": [],
                    "verdict": "looks fine",
                }
            ],
        )
    assert "verdict" in str(raised.value)


def test_two_audits_with_the_same_id_are_refused(tmp_path: Path) -> None:
    """The audit_id is the record's identity: a duplicate is a BuildError
    even when both records are otherwise legal."""

    record = {
        "audit_id": "audit-dup",
        "performed_by": "reviewer",
        "basis": "sampling",
        "approved_entities": ["res-hedge-i-think"],
    }
    with pytest.raises(BuildError) as raised:
        _audits_variant(tmp_path, [dict(record), dict(record)])
    assert "duplicate audit_id" in str(raised.value)


def test_two_audits_approving_the_same_entity_are_legal(
    tmp_path: Path,
) -> None:
    """Two distinct records may approve the same entity (the level reads
    'approved by at least one record' and stays EDITOR_REVIEWED)."""

    def record(audit_id: str, entity: str) -> dict:
        return {
            "audit_id": audit_id,
            "performed_by": "reviewer",
            "basis": "sampling",
            "approved_entities": [entity],
        }

    artifact = _audits_variant(
        tmp_path,
        [
            record("audit-one", "res-hedge-i-think"),
            record("audit-two", "res-hedge-i-think"),
        ],
    )
    assert _provenance(artifact)["res-hedge-i-think"] == "EDITOR_REVIEWED"


# ---------------------------------------------------------------------------
# ⑩ determinism (double builds and cross-process, with audits injected)
# ---------------------------------------------------------------------------


def test_two_audited_builds_are_byte_identical(tmp_path: Path) -> None:
    """The provenance rows are a pure function of the source: two builds of
    the same audited tree produce identical bytes."""

    def build(name: str) -> Path:
        return _audits_variant(
            tmp_path / name,
            [
                {
                    "audit_id": "audit-det",
                    "performed_by": "reviewer",
                    "basis": "sampling",
                    "approved_entities": [
                        "res-colloc-make-a-decision",
                        "res-hedge-i-think",
                    ],
                }
            ],
        )

    first = build("first")
    second = build("second")
    assert first.read_bytes() == second.read_bytes()


def test_cross_process_determinism_with_three_hash_seeds(
    tmp_path: Path,
) -> None:
    """Three fresh interpreters with different ``PYTHONHASHSEED`` values
    build the audited source and the three artifacts hash equal (the
    m6/m6b mechanism fact: the ordering keys decide, never hash order)."""

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(
        CONTENT_SRC_DIR, content_src, ignore=shutil.ignore_patterns(AUDITS_DIRNAME)
    )
    shutil.copytree(CURRICULUM_DIR, curriculum)
    audits = content_src / AUDITS_DIRNAME
    audits.mkdir()
    (audits / "audit-00.json").write_text(
        json.dumps(
            {
                "audit_id": "audit-xproc",
                "performed_by": "reviewer",
                "basis": "sampling",
                "approved_entities": [
                    "res-colloc-make-a-decision",
                    "res-discourse-anyway",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    script = (
        "import sys;"
        "from pathlib import Path;"
        "from elc.content.build import build_content_db;"
        "build_content_db("
        "Path(sys.argv[1]), "
        f"content_src_dir=Path(r'{content_src}'), "
        f"curriculum_dir=Path(r'{curriculum}'))"
    )
    src = str(REPO_ROOT / "src")
    digests: list[str] = []
    for seed in ("0", "12345", "random"):
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
    assert digests[0] == digests[1] == digests[2]
