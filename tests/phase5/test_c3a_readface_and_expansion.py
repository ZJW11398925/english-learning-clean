"""C3-a (Phase 11) — the CORE_A/CORE_C declared reading lands, and eighteen
more RESOURCE targets take the corpus to 46.

What this cut did, and what this file pins:

- **the read face moved from family counts to core_utility bands.** Until
  C3-a the two CORE cells of IP §13's Calibration100 gate were read as
  capability *families* (`curriculum_capability.family`), a reading that can
  never move when resources are authored. The user's adjudication
  (2026-09-26) fixed the declared reading this file implements: CORE_A is the
  number of `res-*` entities whose readiness level is R3_TEACHING_READY or
  R4_DETECTION_READY and whose `content_pedagogical_profile.core_utility` is
  ``HIGH``; CORE_C is the same count over ``MEDIUM`` and ``LOW``. It is a
  **declared reading**, not a canonical rule (the plan text fixes only the
  floor numbers), so every pin below names it and carries the Revisit.
- **the corpus truth at C3-a**: 51 entities (5 `cap-*` + 46 `res-*`),
  **46 × R4_DETECTION_READY + 5 × None**, `resource_count` = 46, links 46
  (18 REALIZES + 28 SUPPORTS), evidence documents 46. CORE_A reads 32
  (22 + the cut's 10 HIGH targets) and CORE_C reads 14 (6 + its 7 MEDIUM and
  1 LOW targets). **C3-b (Phase 11) moved the corpus after this cut**: 69
  entities / 64 RESOURCE targets, 64 × R4 + 5 × None, links 64 (21 REALIZES
  and 43 SUPPORTS), evidence documents 64, CORE_A 42 / CORE_C 22 — so this
  file's artifact-wide readings are re-pinned to that truth (the per-target
  pins above stay scoped to C3-a's own eighteen).
- **the three floors are pinned apart** — CORE_A >= 30 met, CORE_C >= 2 met,
  `resource_count` 64 < 100 still unmet — and never as one combined
  "gate passed/failed" sentence. No rollout opening is claimed.
- **the eighteen new targets** are pinned per target (nineteen fact keys, R4,
  source-side pairing of rules and fixtures, the entity/evidence pair
  describing one unit) and as a group (index order, credit face, links).
- **the level is load-bearing for the CORE counts**: a variant that demotes a
  HIGH target's bandwidth link below R3 drops it out of CORE_A even though
  its core_utility is untouched — that is the R3+ half of the declared
  reading, pinned so a band-only reading cannot pass this file.

The canonical authoring trees are never edited: every variant lives in a
pytest tmp copy built through the real build step.
"""

from __future__ import annotations

import hashlib
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
    BuildError,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok
from tests.phase5.conftest import build_variant_artifact

#: The eighteen RESOURCE targets C3-a authored as entities, evidence
#: documents and links, in id order.
C3A_TARGETS = (
    "res-colloc-come-to-a-conclusion",
    "res-colloc-draw-attention-to",
    "res-colloc-have-an-effect-on",
    "res-colloc-keep-in-mind",
    "res-colloc-take-advantage-of",
    "res-discourse-having-said-that",
    "res-discourse-in-fact",
    "res-frame-if-you-dont-mind",
    "res-frame-lets-say",
    "res-hedge-i-mean",
    "res-hedge-sort-of",
    "res-idiom-hit-the-nail-on-the-head",
    "res-idiom-under-the-weather",
    "res-phrasal-carry-on",
    "res-phrasal-give-up",
    "res-phrasal-turn-out",
    "res-pragmatic-could-i-ask",
    "res-softener-to-be-fair",
)

#: The ten C3-a targets whose pedagogical profile declares core_utility HIGH
#: (they are the ones that move CORE_A from 22 to 32).
C3A_HIGH_TARGETS = (
    "res-colloc-draw-attention-to",
    "res-colloc-have-an-effect-on",
    "res-colloc-keep-in-mind",
    "res-colloc-take-advantage-of",
    "res-discourse-in-fact",
    "res-hedge-i-mean",
    "res-hedge-sort-of",
    "res-phrasal-carry-on",
    "res-phrasal-give-up",
    "res-phrasal-turn-out",
)

#: The eight C3-a targets that declare MEDIUM (seven) or LOW (one), i.e. the
#: ones that move CORE_C from 6 to 14.
C3A_NON_HIGH_TARGETS = tuple(
    target for target in C3A_TARGETS if target not in C3A_HIGH_TARGETS
)

#: The three C3-a rows whose relation is REALIZES (the credit-bearing half).
C3A_REALIZES = (
    "res-discourse-having-said-that",
    "res-hedge-sort-of",
    "res-softener-to-be-fair",
)

#: The fifteen C3-a rows whose relation is SUPPORTS (the credit-safe half).
C3A_SUPPORT_TARGETS = tuple(
    target for target in C3A_TARGETS if target not in C3A_REALIZES
)

FIXTURE_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY")
EXPECTED_READINGS = ("NO_MATCH", "NO_MATCH_BOUNDARY")

#: The declared CORE reading's level set and band partition (C3-a).
CORE_LEVELS = ("R3_TEACHING_READY", "R4_DETECTION_READY")
UTILITY_BANDS = ("HIGH", "MEDIUM", "LOW")

#: The three Calibration100 floors as read from the frozen plan text.
_CALIBRATION100_FLOORS = {"resource_count": 100, "CORE_A": 30, "CORE_C": 2}

_PLAN = Path(__file__).resolve().parents[2] / "docs" / "IMPLEMENTATION_PLAN.md"

#: The entity-id type prefixes the corpus uses (`res-<type>-<stem>`).
_TYPE_PREFIXES = (
    "colloc-",
    "phrasal-",
    "idiom-",
    "discourse-",
    "frame-",
    "hedge-",
    "softener-",
    "pragmatic-",
)


def _stem(entity_id: str) -> str:
    for prefix in _TYPE_PREFIXES:
        if entity_id.startswith(f"res-{prefix}"):
            return entity_id.removeprefix(f"res-{prefix}")
    raise AssertionError(entity_id)


def _levels_and_utilities(
    artifact: Path,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """The two read halves of the declared CORE reading, from the artifact.

    Levels come from the live readiness face (`readiness_by_target`); the
    ``core_utility`` band is read from the ``content_pedagogical_profile``
    table itself (the artifact carries the band; §24.7 declares no word list
    for it, so the three values are the corpus's own authored strings).
    """

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
            str(entity_id): str(band)
            for entity_id, band in conn.execute(
                "SELECT entity_id, core_utility FROM content_pedagogical_profile"
            ).fetchall()
        }
    finally:
        conn.close()
    return levels, utilities


def _core_counts(artifact: Path) -> tuple[int, int]:
    """CORE_A / CORE_C under the declared reading (2026-09-26)."""

    levels, utilities = _levels_and_utilities(artifact)
    resources = sorted(
        entity_id
        for entity_id, level in levels.items()
        if entity_id.startswith("res-") and level in CORE_LEVELS
    )
    core_a = [t for t in resources if utilities.get(t) == "HIGH"]
    core_c = [t for t in resources if utilities.get(t) in ("MEDIUM", "LOW")]
    assert all(utilities.get(t) in UTILITY_BANDS for t in resources), resources
    return len(core_a), len(core_c)


def _evidence_variant(
    tmp_path: Path, target_id: str, edit: Callable[[dict], None]
) -> Path:
    """A tmp copy of both authoring trees with one evidence edit, built
    through the real build step (test_c2a's two-line-local helper)."""

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


def _level_of(artifact: Path, target_id: str) -> str | None:
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        assessment = supply.readiness(target_id)
        assert isinstance(assessment, Ok), assessment
    finally:
        store.close()
    return assessment.value.level


# ---------------------------------------------------------------------------
# ① the declared CORE reading, from the artifact
# ---------------------------------------------------------------------------


def test_core_a_counts_the_high_utility_targets_at_r3_and_above(
    built_content_db: Path,
) -> None:
    """CORE_A = R3+ level ∧ core_utility HIGH over the `res-*` entities.

    声明读法 + Revisit（用户 2026-09-26 裁决）: the plan text fixes the floor
    (CORE_A >= 30) and no definition of what is counted; the level x band
    reading is the adjudicated one, implemented here and in the three migrated
    pins. Revisit when the canonical Calibration100 definition lands. At
    C3-b's truth the reading answers 42 (C3-a's 32 plus C3-b's ten HIGH
    targets).
    """

    levels, utilities = _levels_and_utilities(built_content_db)
    core_a, core_c = _core_counts(built_content_db)
    assert core_a == 42
    assert core_a >= 30
    assert core_a + core_c == 64
    assert len(C3A_HIGH_TARGETS) == 10
    for target in C3A_HIGH_TARGETS:
        assert levels[target] == "R4_DETECTION_READY", target
        assert utilities[target] == "HIGH", target


def test_core_c_counts_the_medium_and_low_utility_targets_at_r3_and_above(
    built_content_db: Path,
) -> None:
    """CORE_C = R3+ level ∧ core_utility MEDIUM/LOW, and the LOW arm is
    exercised: `res-pragmatic-could-i-ask` is the corpus's first LOW band.

    声明读法 + Revisit（用户 2026-09-26 裁决），与 CORE_A 同一条读法。At
    C3-b's truth the reading answers 22 (C3-a's 14 plus C3-b's eight MEDIUM
    targets).
    """

    levels, utilities = _levels_and_utilities(built_content_db)
    core_a, core_c = _core_counts(built_content_db)
    assert core_c == 22
    assert core_c >= 2
    assert len(C3A_NON_HIGH_TARGETS) == 8
    assert utilities["res-pragmatic-could-i-ask"] == "LOW"
    for target in C3A_NON_HIGH_TARGETS:
        assert levels[target] == "R4_DETECTION_READY", target
        assert utilities[target] in ("MEDIUM", "LOW"), target
    # Every banded target at R3+ is in exactly one cell.
    banded = {t for t in levels if t.startswith("res-")}
    assert len(banded) == 64
    for target in banded:
        assert utilities[target] in UTILITY_BANDS, target


def test_a_high_utility_target_demoted_to_medium_leaves_core_a(
    tmp_path: Path,
) -> None:
    """The band half of the reading, load-bearing: editing one evidence
    document's core_utility from HIGH to MEDIUM moves that target from CORE_A
    to CORE_C (42/22 -> 41/23), so a pin that ignored the band would survive
    this edit and this one does not."""

    def demote(document: dict) -> None:
        assert document["pedagogical_profile"]["core_utility"] == "HIGH"
        document["pedagogical_profile"]["core_utility"] = "MEDIUM"

    artifact = _evidence_variant(tmp_path, "res-phrasal-give-up", demote)
    assert _level_of(artifact, "res-phrasal-give-up") == "R4_DETECTION_READY"
    assert _core_counts(artifact) == (41, 23)


def test_demoting_a_high_targets_link_below_r3_drops_its_core_a_count(
    tmp_path: Path,
) -> None:
    """The level half of the reading, load-bearing: demoting one HIGH
    target's approved §24.7 link to CURRICULUM_MAPPED costs it the R2 fact and
    the level falls to R1_LEXICALLY_RESOLVED — so it leaves CORE_A although
    its core_utility is untouched (42/22 -> 41/22). A band-only reading would
    keep counting it."""

    def demote(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == "res-discourse-in-fact":
                row["editorial_status"] = "CURRICULUM_MAPPED"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=demote)
    assert _level_of(artifact, "res-discourse-in-fact") == "R1_LEXICALLY_RESOLVED"
    levels, utilities = _levels_and_utilities(artifact)
    assert utilities["res-discourse-in-fact"] == "HIGH"
    assert levels["res-discourse-in-fact"] not in CORE_LEVELS
    assert _core_counts(artifact) == (41, 22)


def test_the_three_calibration100_floors_read_separately(
    built_content_db: Path,
) -> None:
    """The three floors, each on its own line — the cut's honesty face.

    CORE_A 42 >= 30 (met), CORE_C 22 >= 2 (met), resource_count 64 < 100
    (unmet): three assertions, three printed readings, and no single
    "gate passed" sentence. The floor numbers come from the frozen plan text,
    not from a second hand-typed copy.
    """

    plan_text = _PLAN.read_text(encoding="utf-8")
    gates = {
        name: int(re.search(rf"{re.escape(name)} >= (\d+)", plan_text).group(1))
        for name in ("resource_count", "CORE_A", "CORE_C")
    }
    assert gates == _CALIBRATION100_FLOORS

    conn = sqlite3.connect(str(built_content_db))
    try:
        entity_ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT entity_id FROM content_entity ORDER BY entity_id"
            )
        ]
    finally:
        conn.close()
    resources = [eid for eid in entity_ids if eid.startswith("res-")]
    core_a, core_c = _core_counts(built_content_db)
    print(
        f"[c3b] CORE_A = {core_a} (floor {gates['CORE_A']},"
        f" {'met' if core_a >= gates['CORE_A'] else 'unmet'})"
    )
    print(
        f"[c3b] CORE_C = {core_c} (floor {gates['CORE_C']},"
        f" {'met' if core_c >= gates['CORE_C'] else 'unmet'})"
    )
    print(
        f"[c3b] resource_count = {len(resources)}"
        f" (floor {gates['resource_count']},"
        f" {'met' if len(resources) >= gates['resource_count'] else 'unmet'})"
    )
    assert core_a >= gates["CORE_A"]  # CORE_A met
    assert core_c >= gates["CORE_C"]  # CORE_C met
    assert len(resources) < gates["resource_count"]  # volume floor unmet
    assert len(resources) == 64
    assert len(entity_ids) == 69


# ---------------------------------------------------------------------------
# ② the eighteen new targets, one by one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", C3A_TARGETS)
def test_each_c3a_target_carries_all_nineteen_keys_and_reads_r4(
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


def test_the_corpus_table_is_sixty_four_r4_and_five_none(
    built_content_db: Path,
) -> None:
    """The whole table, read once: every `res-*` target reads R4, the five
    `cap-*` entities read None, and every one of the eighteen new ids is in
    the R4 half (C3-a's and C3-b's alike)."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    table = {a.target_id: a.level for a in assessments.value}
    assert len(table) == 69
    r4 = sorted(t for t, level in table.items() if level == "R4_DETECTION_READY")
    none = sorted(t for t, level in table.items() if level is None)
    assert all(target in r4 for target in C3A_TARGETS)
    assert len(r4) == 64
    assert len(none) == 5
    assert all(target.startswith("cap-") for target in none)
    unexpected = [
        level for level in table.values() if level not in (None, "R4_DETECTION_READY")
    ]
    assert unexpected == []


@pytest.mark.parametrize("target_id", C3A_TARGETS)
def test_each_c3a_entity_teaches_the_unit_its_evidence_entries(
    built_content_db: Path, target_id: str
) -> None:
    """The entity half and the evidence half describe one unit: the canonical
    sentence carries the lemma's lexical anchor, the reveal form is one of the
    canonical forms, the ladder has three rungs, the evidence's base form is
    written the way the lemma is, and the sense id follows the corpus
    convention."""

    entity = json.loads(
        (CONTENT_SRC_DIR / "entities" / f"{target_id}.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = json.loads(
        (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").read_text(
            encoding="utf-8"
        )
    )
    teaching = entity["teaching_content"]
    assert teaching["reveal_form"] in teaching["canonical_forms"], target_id
    assert len(teaching["hint_ladder"]) == 3, target_id
    assert teaching["required_slots"], target_id
    lemma = str(evidence["lexical_entry"]["lemma"])
    assert str(evidence["lexical_entry"]["pos"]), target_id
    canonical = str(teaching["canonical_forms"][0]).lower()
    anchor = lemma.lower().split()[-1]
    assert anchor in canonical, (target_id, lemma, canonical)
    first = lemma.lower().split()[0]
    forms = [str(row["written"]).lower() for row in evidence["forms"]]
    assert any(first in written for written in forms), (target_id, lemma, forms)
    assert all(
        str(row["form_id"]).startswith(_stem(target_id))
        for row in evidence["forms"]
    ), target_id
    assert str(evidence["senses"][0]["sense_id"]) == f"{_stem(target_id)}.sense-1", (
        target_id
    )


def test_every_c3a_evidence_document_pairs_its_rules_and_fixtures() -> None:
    """The R4 self-constraint over the eighteen new documents: every rule
    ordinal carries a fixture at the same ordinal, both declared kinds are
    present, every ``expected`` is one of the two declared readings with kind
    and expected agreeing, and the four non-optional text roles plus the
    detection policy, example policy, labels, overlays and a typical error are
    all there."""

    for target_id in C3A_TARGETS:
        document = json.loads(
            (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").read_text(
                encoding="utf-8"
            )
        )
        rules = sorted(int(row["ordinal"]) for row in document["detection_rules"])
        fixtures = sorted(
            int(row["ordinal"]) for row in document["detection_fixtures"]
        )
        assert rules == fixtures == list(range(len(rules))), target_id
        assert len(rules) >= 2, target_id
        kinds = {str(row["kind"]) for row in document["detection_fixtures"]}
        assert kinds == set(FIXTURE_KINDS), (target_id, kinds)
        for row in document["detection_fixtures"]:
            assert str(row["expected"]) in EXPECTED_READINGS, (target_id, row)
            assert (str(row["kind"]) == "NEGATIVE") == (
                str(row["expected"]) == "NO_MATCH"
            ), (target_id, row)
            assert str(row["text"]), (target_id, row)
        roles = {str(row["role"]) for row in document["texts"]}
        assert {
            "definition",
            "usage",
            "teaching_note",
            "translation",
        } <= roles, (target_id, roles)
        assert document["detection_policy"]["policy_version"] == "detection-policy-v1"
        assert document["example_policy"]["policy_version"] == "example-policy-v1"
        assert document["typical_error_required"] is True, target_id
        assert document["typical_errors"], target_id
        assert document["typical_errors"][0]["detection_policy"], target_id
        assert document["resource_labels"], target_id
        assert document["pack_overlays"], target_id


# ---------------------------------------------------------------------------
# ③ the credit face and the links
# ---------------------------------------------------------------------------


def test_the_credit_face_widens_by_the_three_new_realizes_rows(
    built_content_db: Path,
) -> None:
    """The links document carries 64 rows of which 21 are REALIZES
    (18 through C3-a, plus C3-b's 3) and 43 SUPPORTS; the credit face answers
    a node for exactly the 21 REALIZES rows, each reading the node its own row
    names; the fifteen new SUPPORTS rows of this cut stay readable and mint
    nothing (C3-b's fifteen are held to the same discipline by its own file)."""

    document = json.loads(
        (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    )
    rows = document["links"]
    assert len(rows) == 64
    realizes = {
        str(row["resource_id"]): str(row["node_id"])
        for row in rows
        if row["relation"] == "REALIZES"
    }
    assert len(realizes) == 21
    assert set(C3A_REALIZES) <= set(realizes)
    assert realizes["res-hedge-sort-of"] == "cap-stance-soften-disagreement"
    assert realizes["res-softener-to-be-fair"] == "cap-stance-soften-disagreement"
    assert (
        realizes["res-discourse-having-said-that"] == "cap-stance-soften-disagreement"
    )

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        credited: dict[str, str] = {}
        for entity_id in store.entity_ids().value:
            teaching = supply.get_teaching_content(entity_id)
            assert isinstance(teaching, Ok), teaching
            if teaching.value.capability_linkage is not None:
                credited[str(entity_id)] = str(teaching.value.capability_linkage)
            for target_id in C3A_SUPPORT_TARGETS:
                if str(entity_id) == target_id:
                    assert teaching.value.capability_linkage is None, target_id
    finally:
        store.close()
    assert credited == realizes
    assert len(credited) == 21
    assert len(C3A_SUPPORT_TARGETS) == 15
    assert len(C3A_TARGETS) == 18


def test_the_new_links_state_their_basis_and_their_limit() -> None:
    """Every new row states what its approval covers and what it does not:
    a REALIZES row names the absence of a capability-semantics audit, a
    SUPPORTS row declares its nearest-node placement, all rows are approved
    with the relation's own primary_flag and a null strength."""

    rows = json.loads(
        (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    )["links"]
    new_rows = {
        str(row["resource_id"]): row
        for row in rows
        if str(row["resource_id"]) in C3A_TARGETS
    }
    assert sorted(new_rows) == sorted(C3A_TARGETS)
    for target_id, row in new_rows.items():
        assert row["editorial_status"] == "CANONICAL_APPROVED", target_id
        assert row["strength"] is None, target_id
        assert str(row["node_id"]).startswith("cap-"), target_id
        rationale = str(row["rationale"])
        if row["relation"] == "REALIZES":
            assert row["primary_flag"] is True, target_id
            assert "no capability-semantics audit" in rationale, target_id
            assert "R-C1-credit" in rationale, target_id
        else:
            assert row["relation"] == "SUPPORTS", target_id
            assert row["primary_flag"] is False, target_id
            assert "nearest available node" in rationale, target_id
            assert "mints nothing" in rationale, target_id


# ---------------------------------------------------------------------------
# ④ the source side: index order, strict loader, determinism
# ---------------------------------------------------------------------------


def test_the_index_lists_sixty_nine_and_sixty_four_documents() -> None:
    """The index grew in both lists: entity documents 33 → 51 → 69 (C3-b),
    evidence documents 28 → 46 → 64, both plain id order, and the eighteen new
    ids appear in each list exactly once."""

    index = json.loads((CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8"))
    entities = [str(entry) for entry in index["entities"]]
    evidence = [str(entry) for entry in index["evidence"]]
    assert len(entities) == 69
    assert len(evidence) == 64
    assert entities == sorted(entities)
    assert evidence == sorted(evidence)
    for target_id in C3A_TARGETS:
        assert entities.count(f"entities/{target_id}.json") == 1, target_id
        assert evidence.count(f"evidence/{target_id}.json") == 1, target_id
        assert (CONTENT_SRC_DIR / "entities" / f"{target_id}.json").is_file()
        assert (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").is_file()


def test_an_unknown_block_in_a_new_evidence_document_is_refused(
    tmp_path: Path,
) -> None:
    """The strict loader gives the new documents no leniency: an unknown block
    in one of them is a BuildError and no artifact is written."""

    target_id = "res-colloc-keep-in-mind"
    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    path = content_src / "evidence" / f"{target_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["collocations"] = []
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(BuildError, match="unknown evidence block"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_two_builds_of_the_grown_source_are_byte_equal(tmp_path: Path) -> None:
    """Determinism re-checked after the corpus passed 64: two builds of the
    same source produce the same bytes."""

    first = tmp_path / "a.db"
    second = tmp_path / "b.db"
    build_content_db(first)
    build_content_db(second)
    assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(
        second.read_bytes()
    ).hexdigest()
    report = build_content_db(tmp_path / "c.db")
    assert report.entity_count == 69
    assert report.evidence_count == 64
    assert report.link_count == 64
    assert report.capability_count == 5


def test_no_opening_claim_is_made_by_this_cut() -> None:
    """The stage leg is the only door and this cut did not touch it: the
    undeclared stage still refuses, and the authoring tree carries no stage
    declaration."""

    from elc.teaching.rollout import stage_allows_automatic

    assert stage_allows_automatic(None) is False
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(CONTENT_SRC_DIR.rglob("*.json"))
    ) + (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    assert "rollout_stage" not in blob
    assert "ROLLOUT" not in blob
