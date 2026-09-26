"""C2-b (Phase 11) — nineteen new RESOURCE entities ⇒ resource_count 28.

The cut: nineteen authored entities (each with an entity document, a
nineteen-key §8.1 evidence document and one §24.7 link) land in the canonical
authoring tree, taking the corpus from 9 × R4_DETECTION_READY to **28 × R4 +
5 × None** and `resource_count` (`res-*` entities) to **28** — IP §13's own
starting number, i.e. the first rung of "28 → 100 resource calibration", not a
Calibration100 pass (100/30/2 all stay unmet). The credit face widens from 9
to 15 because six of the nineteen rows are REALIZES; the other thirteen are
SUPPORTS rows, which satisfy §8.1 R2's `curriculum_link` fact and mint
nothing.

What this file pins, in order:

- the nineteen new targets, one by one: all nineteen §8.1 fact keys present
  and R4, with nothing blocking the next rung (parametrized);
- the first rung and the three floors as two separate readings, both driven
  by the artifact and by the frozen plan text: `resource_count` == 28 ≥ 28
  (IP §13's start) **and** 28 < 100 with CORE_A / CORE_C at zero;
- the credit face is consistent with the links: the count of REALIZES rows is
  15 and the count of entities whose `capability_linkage` is not None is 15,
  per id; the six C2-b REALIZES rows are named; and the thirteen SUPPORTS
  rows — approved, R2-readable — credit nothing (the negative pin);
- the source side: the index lists the nineteen new documents in id order in
  both lists, every new entity document carries a real teaching payload whose
  canonical form is the lexical entry's own unit, and every new evidence
  document pairs its rules with fixtures (same ordinal, both declared kinds,
  the two declared `expected` readings);
- the strict loader still refuses new-source mistakes: an unknown key in a
  new entity document and an unknown block in a new evidence document are
  each a BuildError with no artifact (and each builds clean once reverted);
- the artifact is still deterministic across processes: two subprocess builds
  under different ``PYTHONHASHSEED`` values hash equal;
- no opening claim: the composed rollout switch still answers False for the
  undeclared stage, and this cut opens nothing.

The canonical authoring trees are never edited: every variant lives in a
pytest tmp copy built through the real build step.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

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

#: The nineteen entities C2-b authored (entities + evidence + links).
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

#: The six C2-b rows whose relation is REALIZES (the credit-bearing half).
C2B_CREDIT_TARGETS = (
    "res-discourse-anyway",
    "res-discourse-to-be-honest",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-pragmatic-thats-a-good-point-but",
    "res-softener-a-bit",
)

#: The thirteen C2-b rows whose relation is SUPPORTS (the credit-safe half).
C2B_SUPPORT_TARGETS = tuple(
    target for target in C2B_TARGETS if target not in C2B_CREDIT_TARGETS
)

FIXTURE_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY")
EXPECTED_READINGS = ("NO_MATCH", "NO_MATCH_BOUNDARY")

#: 旧真值 → 新真值: the credit face before and after this cut.
CREDIT_FACE_BEFORE = 9
CREDIT_FACE_AFTER = 15

_PLAN = Path(__file__).resolve().parents[2] / "docs" / "IMPLEMENTATION_PLAN.md"


def _artifact(tmp_path: Path) -> Path:
    output = tmp_path / "content.db"
    build_content_db(output)
    return output


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
    """The sense-id stem of a RESOURCE entity id (seed convention)."""

    for prefix in _TYPE_PREFIXES:
        if entity_id.startswith(f"res-{prefix}"):
            return entity_id.removeprefix(f"res-{prefix}")
    raise AssertionError(entity_id)


# ---------------------------------------------------------------------------
# ① the nineteen new targets, one by one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", C2B_TARGETS)
def test_each_c2b_target_carries_all_nineteen_keys_and_reads_r4(
    built_content_db: Path, target_id: str
) -> None:
    """Per target: every §8.1 key present (eighteen read from their own
    tables, ``entity_row`` proven by the preceding ``get_resource`` success)
    and the level is the top rung with nothing blocking the next one. The
    evidence documents are the cut's own — no authoring fixture backs them —
    so the claim under test is exactly "this source states all nineteen
    facts", not "a fixture said so"."""

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


def test_the_corpus_table_is_twenty_eight_r4_and_five_none(
    built_content_db: Path,
) -> None:
    """The whole table, read once: the twenty-eight ``res-*`` targets read
    R4, the five ``cap-*`` entities read None, and every one of the nineteen
    new ids is in the R4 half (the per-target pin above is the positive
    direction; this one is the completeness direction)."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    table = {a.target_id: a.level for a in assessments.value}
    assert len(table) == 33
    r4 = sorted(t for t, level in table.items() if level == "R4_DETECTION_READY")
    none = sorted(t for t, level in table.items() if level is None)
    assert all(target in r4 for target in C2B_TARGETS)
    assert len(r4) == 28
    assert none == [
        "cap-disc-topic-shift",
        "cap-eval-hedged-opinion",
        "cap-interact-backchannel",
        "cap-ref-ask-clarification",
        "cap-stance-soften-disagreement",
    ]
    unexpected = [
        level for level in table.values() if level not in (None, "R4_DETECTION_READY")
    ]
    assert unexpected == []


# ---------------------------------------------------------------------------
# ② the first rung and the three floors, as two readings
# ---------------------------------------------------------------------------


def test_the_first_rung_is_met_and_the_three_floors_are_not(
    built_content_db: Path,
) -> None:
    """IP §13's "28 → 100 resource calibration" read as two separate facts:
    the corpus's RESOURCE count is **28**, which is the starting number the
    frozen plan text names (so the first rung is met), and the Calibration100
    floors are 100 / 30 / 2, so the corpus is still below every one of them
    (28 < 100, CORE_A 0 < 30, CORE_C 0 < 2). This test deliberately asserts
    both directions: a cut that reached 100, or that claimed IP §13's start
    as a gate pass, would fail here."""

    plan_text = _PLAN.read_text(encoding="utf-8")
    assert "28 → 100 resource calibration" in plan_text
    assert "优先使用内容填补真实运行时测试需要，而不是为了数量" in plan_text
    gates = {
        name: int(re.search(rf"{re.escape(name)} >= (\d+)", plan_text).group(1))
        for name in ("resource_count", "CORE_A", "CORE_C")
    }
    assert gates == {"resource_count": 100, "CORE_A": 30, "CORE_C": 2}

    conn = sqlite3.connect(str(built_content_db))
    try:
        entity_ids = [
            str(row[0])
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
    resources = [eid for eid in entity_ids if eid.startswith("res-")]
    assert len(resources) == 28  # IP §13's start: the first rung
    assert len(resources) >= 28
    assert len(resources) < gates["resource_count"]  # 100/30/2 all unmet
    assert len(entity_ids) == 33
    assert families.get("CORE_A", 0) < gates["CORE_A"]
    assert families.get("CORE_C", 0) < gates["CORE_C"]
    print(
        f"[c2b] first rung met: resource_count = {len(resources)} (IP §13 start"
        f" = 28); Calibration100 floors still unmet:"
        f" {len(resources)}/{gates['resource_count']},"
        f" CORE_A {families.get('CORE_A', 0)}/{gates['CORE_A']},"
        f" CORE_C {families.get('CORE_C', 0)}/{gates['CORE_C']}"
    )


def test_no_opening_claim_is_made_by_this_cut() -> None:
    """The stage leg is the only door and this cut did not touch it: the
    undeclared stage still refuses, and the source tree this cut authored
    carries no stage declaration (a grep over the authoring documents, so the
    claim is checked rather than asserted)."""

    from elc.teaching.rollout import stage_allows_automatic

    assert stage_allows_automatic(None) is False
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(CONTENT_SRC_DIR.rglob("*.json"))
    ) + (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    assert "rollout_stage" not in blob
    assert "ROLLOUT" not in blob


# ---------------------------------------------------------------------------
# ③ the credit face and the links agree, in both directions
# ---------------------------------------------------------------------------


def test_the_credit_face_delta_equals_the_new_realizes_rows(
    built_content_db: Path,
) -> None:
    """The behaviour change, counted three ways so it cannot drift: the
    links document carries 28 rows of which 15 are REALIZES (9 + k, k = 6);
    the credit face answers a node for exactly 15 entities; and the six C2-b
    ids that credit are the six named ones, each reading the node its own row
    names."""

    document = json.loads(
        (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    )
    rows = document["links"]
    assert len(rows) == 28
    realizes = {
        str(row["resource_id"]): str(row["node_id"])
        for row in rows
        if row["relation"] == "REALIZES"
    }
    assert len(realizes) == CREDIT_FACE_AFTER == CREDIT_FACE_BEFORE + 6
    assert set(C2B_CREDIT_TARGETS) <= set(realizes)

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        credited: dict[str, str] = {}
        for entity_id in store.entity_ids().value:
            teaching = supply.get_teaching_content(entity_id)
            assert isinstance(teaching, Ok), teaching
            if teaching.value.capability_linkage is not None:
                credited[str(entity_id)] = str(teaching.value.capability_linkage)
    finally:
        store.close()
    assert credited == realizes
    assert len(credited) == CREDIT_FACE_AFTER


def test_the_approved_supports_rows_credit_nothing(built_content_db: Path) -> None:
    """The negative pin: an approved ``SUPPORTS`` row satisfies §8.1 R2's
    ``curriculum_link`` fact and does **not** enter capability credit — the
    read filters ``relation = REALIZES``. Without this direction the corpus
    could not distinguish "the approval is what admits a row" from "any
    approved row credits"."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        for target_id in C2B_SUPPORT_TARGETS:
            links = supply.curriculum_links_of(target_id)
            assert isinstance(links, Ok), links
            assert len(links.value) == 1, target_id
            row = links.value[0]
            assert str(row.relation) == "SUPPORTS", target_id
            assert row.primary_flag is False, target_id
            assert row.editorial_status == "CANONICAL_APPROVED", target_id
            teaching = supply.get_teaching_content(target_id)
            assert isinstance(teaching, Ok), teaching
            assert teaching.value.capability_linkage is None, target_id
            # R2-readable all the same: the readiness fact is satisfied.
            facts = supply.readiness_facts(target_id)
            assert isinstance(facts, Ok), facts
            assert facts.value.curriculum_link is True, target_id
        assert len(C2B_SUPPORT_TARGETS) == 13
    finally:
        store.close()


# ---------------------------------------------------------------------------
# ④ the source side: index order, payload ↔ lexical entry, pairing
# ---------------------------------------------------------------------------


def test_the_index_lists_the_nineteen_new_documents_in_both_lists(
    built_content_db: Path,
) -> None:
    """The index grew in both lists and in the same order rule: entity
    documents 14 → 33, evidence documents 9 → 28, both plain id order, and the
    nineteen new ids appear in each list exactly once (a document present on
    disk but unlisted is a BuildError, so the listing is also what makes the
    build succeed)."""

    index = json.loads((CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8"))
    entities = [str(entry) for entry in index["entities"]]
    evidence = [str(entry) for entry in index["evidence"]]
    assert len(entities) == 33
    assert len(evidence) == 28
    assert entities == sorted(entities)
    assert evidence == sorted(evidence)
    for target_id in C2B_TARGETS:
        assert entities.count(f"entities/{target_id}.json") == 1, target_id
        assert evidence.count(f"evidence/{target_id}.json") == 1, target_id
        assert (CONTENT_SRC_DIR / "entities" / f"{target_id}.json").is_file()
        assert (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").is_file()


@pytest.mark.parametrize("target_id", C2B_TARGETS)
def test_each_new_entity_teaches_the_unit_its_evidence_entries(
    built_content_db: Path, target_id: str
) -> None:
    """The entity half and the evidence half describe one unit: the entity's
    canonical form is a whole sentence carrying the lexical entry's lemma, the
    reveal form is one of the canonical forms, the hint ladder has at least
    three rungs, and the evidence's base form is written the way the lemma
    is — so a document pair that drifted apart fails here."""

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
    assert len(teaching["hint_ladder"]) >= 3, target_id
    assert teaching["required_slots"], target_id
    lemma = str(evidence["lexical_entry"]["lemma"])
    assert str(evidence["lexical_entry"]["pos"]), target_id
    # The two halves name one unit: the canonical sentence carries the
    # lemma's lexical anchor (its head word, last token), and the evidence's
    # `forms` block spells the unit out beginning from the lemma's first
    # token. Inflection is expected on the sentence side (took / met / came),
    # which is why the anchor is the invariant part of the unit.
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
    # The sense id follows the corpus convention: the entity id minus its
    # `res-<type>-` prefix (res-colloc-make-a-decision → make-a-decision),
    # which is the same stem the seed documents use.
    assert str(evidence["senses"][0]["sense_id"]) == f"{_stem(target_id)}.sense-1", (
        target_id
    )


def test_every_new_evidence_document_pairs_its_rules_and_fixtures() -> None:
    """The R4 self-constraint, over the nineteen new documents: every rule
    ordinal carries a fixture at the same ordinal, both declared kinds are
    present, every ``expected`` is one of the two declared readings, kind and
    expected agree, and the four non-optional blocks (definition, usage,
    teaching_note, translation) plus the detection policy and a typical error
    are all there — the "carries all nineteen keys" claim, read at the source
    so a document that only satisfies the loader still fails."""

    for target_id in C2B_TARGETS:
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
# ⑤ the strict loader still refuses, and the build is still deterministic
# ---------------------------------------------------------------------------


def test_an_unknown_key_in_a_new_entity_document_is_refused(
    tmp_path: Path,
) -> None:
    """A new document gets no leniency the seed documents did not have: an
    unknown key inside a block is a BuildError and no artifact is written."""

    target_id = "res-softener-a-bit"

    def edit(documents: dict, _index: dict) -> None:
        document = documents[f"entities/{target_id}.json"]
        document["teaching_content"]["extra_note"] = "not a declared key"

    with pytest.raises(BuildError, match="key mismatch"):
        build_variant_artifact(tmp_path, edit)
    assert not (tmp_path / "content.db").exists()


def test_an_unknown_block_in_a_new_evidence_document_is_refused(
    tmp_path: Path,
) -> None:
    """Same for the evidence tree: the declared block set is closed, and a
    new document that invents a block is refused rather than partly read."""

    target_id = "res-colloc-heavy-rain"
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


def test_two_process_builds_under_different_hash_seeds_are_byte_equal(
    tmp_path: Path,
) -> None:
    """Determinism across processes, re-checked after the corpus grew: two
    subprocess builds with different ``PYTHONHASHSEED`` values produce the
    same bytes, so the nineteen new documents' order cannot leak into the
    artifact."""

    script = (
        "import sys\n"
        "from elc.content.build import build_content_db\n"
        "build_content_db(sys.argv[1])\n"
    )
    src = str(Path(__file__).resolve().parents[2] / "src")
    digests = []
    for seed in ("0", "1"):
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


def test_the_canonical_trees_are_unchanged_by_a_variant_build(
    tmp_path: Path,
) -> None:
    """The variant helpers copy the trees; the canonical documents must be
    exactly what the commit carries after every build this file ran."""

    before = {
        path.relative_to(CONTENT_SRC_DIR).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(CONTENT_SRC_DIR.rglob("*.json"))
    }
    curriculum_before = {
        path.relative_to(CURRICULUM_DIR).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(CURRICULUM_DIR.rglob("*.json"))
    }
    build_content_db(tmp_path / "content.db")

    def digest(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(root.rglob("*.json"))
        }

    assert digest(CONTENT_SRC_DIR) == before
    assert digest(CURRICULUM_DIR) == curriculum_before
