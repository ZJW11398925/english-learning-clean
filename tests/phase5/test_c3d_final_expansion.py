"""C3-d (Phase 11) — the final batch: eighteen more RESOURCE targets take
the corpus to 100, the Calibration100 volume floor.

What this cut did, and what this file pins:

- **the corpus truth at C3-d**: 105 entities (5 `cap-*` + 100 `res-*`),
  **52 × R4_DETECTION_READY + 48 × R1_LEXICALLY_RESOLVED + 5 × None**,
  `resource_count` = 100, links 100 (51 REALIZES + 49 SUPPORTS; 52
  CURRICULUM_MAPPING + 48 COVERAGE_PLACEMENT), evidence documents 100. CORE_A
  reads 32 (24 + this cut's 8 HIGH targets) and CORE_C reads 20 (10 + its 10
  MEDIUM targets) under the **declared reading** the user's adjudication
  fixed at C3-a (R3+ level × `core_utility` band; Revisit when the canonical
  Calibration100 definition lands).
- **the three floors are pinned apart — and all three now read met**: CORE_A
  32 >= 30 (met), CORE_C 20 >= 2 (met), `resource_count` 100 >= 100 (met,
  IP §13's 28→100 first rung topped). Three assertions with three printed
  readings and no single "gate passed" sentence — and **zero opening claim**:
  the three floors met is not the rollout open, the undeclared stage still
  refuses, and the authoring tree carries no stage declaration.
- **the new-template obligations hold**: every new entity carries a
  POSITIVE_ERROR fixture per declared error_type (the build refuses less),
  every new link's mapping_class was adjudicated against its capability's
  functional definition with the criterion entries named, and the eighteen
  new entities entered provenance as AUTHOR_DECLARED by structure alone —
  no audit record was written for them (`content_src/audits/` is untouched).
- **the three-key dedup lands as a pin (N-C3C-1's in-cut obligation)**: the
  eighteen new entities' canonical forms, alternative realizations and slot
  tokens collide with no other entity in the whole 100-resource corpus, and
  canonical ∩ alternative is empty within every entity; the pre-existing
  corpus's own slot-token sharing (INFO-2's legacy group shape) is declared,
  not claimed away.
- **LOW-1 is closed with a time qualifier**: the two capability files'
  "no resource of the current corpus is of this shape" sentences are
  qualified to C3-R1 — the criterion faces (statement, counts_as_realization,
  does_not_count, every other boundary case, basis) digest unchanged against
  the parent commit.
- **the untouched faces are pinned blob-for-blob**: the existing 82 link
  rows, the existing 487 fixture rows (242 / 85 / 160) and every existing
  typical-error row and detection rule — each behind a sha256 digest over
  the canonical JSON of the frozen rows.
- **the credit face widens 33 → 51** by the cut's eighteen REALIZES rows.

Ordering conventions declared (N-C3C-2): `C3D_TARGETS` and every other id
list in this file is in **plain id sort order** (no extension); the
`index.json` lists are pinned by the **full path string** including
`.json`, and the two sort rules disagree exactly on the `-` < `.` boundary
(`res-pragmatic-could-you-clarify.json` sorts before
`res-pragmatic-could-you.json` as paths, but
`res-pragmatic-could-you` < `res-pragmatic-could-you-clarify` as ids). The
eighteen new link rows were **appended after row 82 in the cut's own
authoring order** (discourse, hedge, backchannel, clarification,
soften-disagreement), which is document order, not id order; both orders are
declared where they are pinned.

The canonical authoring trees are never edited by a test: every variant
lives in a pytest tmp copy built through the real build step.
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
    CONTENT_DB_VERSION,
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    BuildError,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.curriculum.readiness import READINESS_FACT_KEYS
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok
from elc.teaching.rollout import corpus_rollout_gate, stage_allows_automatic
from tests.phase5.conftest import build_variant_artifact

#: The eighteen RESOURCE targets C3-d authored as entities, evidence
#: documents and links, in plain id sort order (declared convention, see the
#: module docstring).
C3D_TARGETS = (
    "res-discourse-before-i-forget",
    "res-discourse-that-brings-me-to",
    "res-discourse-where-was-i",
    "res-hedge-from-what-i-can-tell",
    "res-hedge-if-you-ask-me",
    "res-hedge-in-a-way",
    "res-hedge-more-or-less",
    "res-pragmatic-come-again",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-go-on",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-no-way",
    "res-pragmatic-right",
    "res-pragmatic-run-that-by-me-again",
    "res-pragmatic-thats-debatable",
    "res-pragmatic-what-was-that",
    "res-pragmatic-youre-kidding",
)

#: The eight C3-d targets whose pedagogical profile declares core_utility
#: HIGH (they move CORE_A from 24 to 32). The bands are honest authoring
#: judgements, not floor-chasing: the ten MEDIUM targets below carry the
#: same evidence face.
C3D_HIGH_TARGETS = (
    "res-discourse-before-i-forget",
    "res-hedge-more-or-less",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-right",
    "res-pragmatic-run-that-by-me-again",
    "res-pragmatic-what-was-that",
)

#: The ten C3-d targets that declare MEDIUM (they move CORE_C from 10 to 20).
#: This cut authored no LOW band; the corpus's LOW example is still
#: `res-pragmatic-could-i-ask` (C3-a).
C3D_MEDIUM_TARGETS = (
    "res-discourse-that-brings-me-to",
    "res-discourse-where-was-i",
    "res-hedge-from-what-i-can-tell",
    "res-hedge-if-you-ask-me",
    "res-hedge-in-a-way",
    "res-pragmatic-come-again",
    "res-pragmatic-go-on",
    "res-pragmatic-no-way",
    "res-pragmatic-thats-debatable",
    "res-pragmatic-youre-kidding",
)

#: The node each C3-d row maps into (every row of this cut is a
#: CURRICULUM_MAPPING; the capability file named in the rationale must be
#: this node's).
C3D_NODE_OF = {
    "res-discourse-before-i-forget": "cap-disc-topic-shift",
    "res-discourse-that-brings-me-to": "cap-disc-topic-shift",
    "res-discourse-where-was-i": "cap-disc-topic-shift",
    "res-hedge-from-what-i-can-tell": "cap-eval-hedged-opinion",
    "res-hedge-if-you-ask-me": "cap-eval-hedged-opinion",
    "res-hedge-in-a-way": "cap-eval-hedged-opinion",
    "res-hedge-more-or-less": "cap-eval-hedged-opinion",
    "res-pragmatic-come-again": "cap-ref-ask-clarification",
    "res-pragmatic-could-you-clarify": "cap-ref-ask-clarification",
    "res-pragmatic-go-on": "cap-interact-backchannel",
    "res-pragmatic-i-hear-you-but": "cap-stance-soften-disagreement",
    "res-pragmatic-im-not-convinced": "cap-stance-soften-disagreement",
    "res-pragmatic-no-way": "cap-interact-backchannel",
    "res-pragmatic-right": "cap-interact-backchannel",
    "res-pragmatic-run-that-by-me-again": "cap-ref-ask-clarification",
    "res-pragmatic-thats-debatable": "cap-stance-soften-disagreement",
    "res-pragmatic-what-was-that": "cap-ref-ask-clarification",
    "res-pragmatic-youre-kidding": "cap-interact-backchannel",
}

#: The thirty-four resources whose §24.7 rows were curriculum mappings before
#: this cut (C3-R1's sixteen plus C3-c's eighteen); their ids are what R4
#: was at C3-c.
PRIOR_R4 = (
    "res-discourse-anyway",
    "res-discourse-by-the-way",
    "res-discourse-having-said-that",
    "res-discourse-moving-on",
    "res-discourse-on-another-note",
    "res-discourse-speaking-of-which",
    "res-discourse-that-reminds-me",
    "res-discourse-to-be-honest",
    "res-discourse-to-get-back-to-the-point",
    "res-hedge-as-far-as-i-know",
    "res-hedge-i-guess",
    "res-hedge-i-think",
    "res-hedge-if-im-not-mistaken",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-hedge-it-seems-to-me",
    "res-hedge-not-really",
    "res-hedge-sort-of",
    "res-pragmatic-are-you-saying",
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-fair-enough",
    "res-pragmatic-got-it",
    "res-pragmatic-i-see",
    "res-pragmatic-i-see-your-point-but",
    "res-pragmatic-let-me-make-sure",
    "res-pragmatic-no-offense-but",
    "res-pragmatic-that-makes-sense",
    "res-pragmatic-thats-a-good-point-but",
    "res-pragmatic-up-to-a-point",
    "res-pragmatic-what-do-you-mean",
    "res-pragmatic-with-all-due-respect",
    "res-softener-a-bit",
    "res-softener-kind-of",
    "res-softener-to-be-fair",
)

#: The thirty-three rows that credited a capability before this cut (C3-c's
#: REALIZES set), each with the node it credits. The eighteen new rows widen
#: this face to fifty-one; these thirty-three must credit the same node as
#: before. (`res-hedge-not-really` is deliberately absent — its row is
#: SUPPORTS + CURRICULUM_MAPPING, readable but crediting nothing.)
PRIOR_CREDIT = {
    "res-discourse-anyway": "cap-disc-topic-shift",
    "res-discourse-by-the-way": "cap-disc-topic-shift",
    "res-discourse-having-said-that": "cap-stance-soften-disagreement",
    "res-discourse-that-reminds-me": "cap-disc-topic-shift",
    "res-discourse-to-be-honest": "cap-eval-hedged-opinion",
    "res-hedge-i-guess": "cap-eval-hedged-opinion",
    "res-hedge-i-think": "cap-eval-hedged-opinion",
    "res-hedge-im-not-sure": "cap-eval-hedged-opinion",
    "res-hedge-it-depends": "cap-eval-hedged-opinion",
    "res-hedge-sort-of": "cap-stance-soften-disagreement",
    "res-pragmatic-no-offense-but": "cap-stance-soften-disagreement",
    "res-pragmatic-thats-a-good-point-but": "cap-stance-soften-disagreement",
    "res-softener-a-bit": "cap-stance-soften-disagreement",
    "res-softener-kind-of": "cap-stance-soften-disagreement",
    "res-softener-to-be-fair": "cap-stance-soften-disagreement",
    "res-discourse-moving-on": "cap-disc-topic-shift",
    "res-discourse-on-another-note": "cap-disc-topic-shift",
    "res-discourse-speaking-of-which": "cap-disc-topic-shift",
    "res-discourse-to-get-back-to-the-point": "cap-disc-topic-shift",
    "res-hedge-as-far-as-i-know": "cap-eval-hedged-opinion",
    "res-hedge-if-im-not-mistaken": "cap-eval-hedged-opinion",
    "res-hedge-it-seems-to-me": "cap-eval-hedged-opinion",
    "res-pragmatic-are-you-saying": "cap-ref-ask-clarification",
    "res-pragmatic-could-you-say-that-again": "cap-ref-ask-clarification",
    "res-pragmatic-let-me-make-sure": "cap-ref-ask-clarification",
    "res-pragmatic-what-do-you-mean": "cap-ref-ask-clarification",
    "res-pragmatic-fair-enough": "cap-interact-backchannel",
    "res-pragmatic-got-it": "cap-interact-backchannel",
    "res-pragmatic-i-see": "cap-interact-backchannel",
    "res-pragmatic-that-makes-sense": "cap-interact-backchannel",
    "res-pragmatic-i-see-your-point-but": "cap-stance-soften-disagreement",
    "res-pragmatic-up-to-a-point": "cap-stance-soften-disagreement",
    "res-pragmatic-with-all-due-respect": "cap-stance-soften-disagreement",
}

#: The two audit records the earlier disposition cuts landed, plus this
#: cut's own disposition record (the delivery cut itself wrote none).
AUDIT_PATH = CONTENT_SRC_DIR / "audits" / "c3r2-stratified-audit.json"
AUDIT2_PATH = CONTENT_SRC_DIR / "audits" / "c3c-stratified-audit.json"
AUDIT3_PATH = CONTENT_SRC_DIR / "audits" / "c3d-stratified-audit.json"

#: The sixteen entities this cut's review passed on both faces: twelve of
#: the eighteen new entities (the six unsampled — from-what-i-can-tell,
#: if-you-ask-me, what-was-that, run-that-by-me-again, youre-kidding,
#: thats-debatable — are deliberately withheld, strict over lenient) plus
#: the four C3-c entities that review re-audited. The disposition cut's
#: audit record approves exactly these.
C3D_AUDITED_PASS = (
    "res-discourse-before-i-forget",
    "res-discourse-that-brings-me-to",
    "res-discourse-where-was-i",
    "res-hedge-in-a-way",
    "res-hedge-more-or-less",
    "res-pragmatic-come-again",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-go-on",
    "res-pragmatic-got-it",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-no-way",
    "res-pragmatic-right",
    "res-pragmatic-that-makes-sense",
    "res-pragmatic-with-all-due-respect",
)

#: The declared CORE reading's level set and band partition (C3-a's
#: adjudication, still the reading here).
CORE_LEVELS = ("R3_TEACHING_READY", "R4_DETECTION_READY")
UTILITY_BANDS = ("HIGH", "MEDIUM", "LOW")

#: The three Calibration100 floors as read from the frozen plan text.
_CALIBRATION100_FLOORS = {"resource_count": 100, "CORE_A": 30, "CORE_C": 2}

_PLAN = Path(__file__).resolve().parents[2] / "docs" / "IMPLEMENTATION_PLAN.md"

FIXTURE_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY", "POSITIVE_ERROR")
EXPECTED_READINGS = ("NO_MATCH", "NO_MATCH_BOUNDARY", "MATCH")

#: The sha256 digest over the canonical JSON of the 82 pre-existing link
#: rows as one list, in document order (blob-for-blob zero-change pin).
LINKS82_DIGEST = (
    "800a1fcf720d73bbb49643bcb2086c28d1ebb887aea29eb7394908e6c22b781b"
)

#: The eighteen new rows, in their appended document order (the cut's own
#: authoring order — see the module docstring's ordering declaration).
APPEND_ORDER = (
    "res-discourse-before-i-forget",
    "res-discourse-that-brings-me-to",
    "res-discourse-where-was-i",
    "res-hedge-from-what-i-can-tell",
    "res-hedge-if-you-ask-me",
    "res-hedge-in-a-way",
    "res-hedge-more-or-less",
    "res-pragmatic-come-again",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-go-on",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-no-way",
    "res-pragmatic-right",
    "res-pragmatic-run-that-by-me-again",
    "res-pragmatic-thats-debatable",
    "res-pragmatic-what-was-that",
    "res-pragmatic-youre-kidding",
)

#: Digests over the 82 pre-existing evidence documents' frozen faces (every
#: detection fixture row, every typical-error row and every detection rule,
#: blob for blob — this cut touched none of them).
FIXTURES_DIGEST = (
    "305b0d3bd46befa379298bb2145d2b6d786569df241be123e845ea02c5b4d1a1"
)
TYPICAL_ERRORS_DIGEST = (
    "b390318cbe5f030e315bd24888b3fd75dc9a06a634c86d20b8017aa69571b450"
)
RULES_DIGEST = (
    "2ea7a212b20cbc72f2bbc7494e1a1a1802d2ea46f0f545961cacf3ead942cddd"
)

#: The old documents' fixture counts (242 / 85 / 160 = 487) and the new
#: documents' contribution (54 / 18 / 36 = 108); together 296 / 103 / 196 =
#: 595.
OLD_FIXTURE_TOTALS = {
    "NEGATIVE": 242,
    "FALSE_POSITIVE_BOUNDARY": 85,
    "POSITIVE_ERROR": 160,
}
NEW_FIXTURE_TOTALS = {
    "NEGATIVE": 54,
    "FALSE_POSITIVE_BOUNDARY": 18,
    "POSITIVE_ERROR": 36,
}

#: The LOW-1 closure, per capability file: the boundary-case index whose
#: narrative sentence this cut qualified, the time-qualified wording, the
#: placement-era wording that must be gone, and the sha256 digest over the
#: file's **criterion face** (the whole document minus that one boundary
#: entry) as it stood at the parent commit — the digest proves every
#: criterion word (statement, counts_as_realization, does_not_count, the
#: other boundary cases, basis) is untouched.
LOW1_EDITS = {
    "cap-interact-backchannel": {
        "boundary_index": 2,
        "new_sentence": (
            "at C3-R1 the corpus carried no resource of this shape, which is"
            " why this node's links were placements then; the C3-c and C3-d"
            " cuts have since authored REALIZES rows for this node"
        ),
        "old_sentence": (
            "no resource of the current corpus is of this shape, which is"
            " why this node's links are placements at C3-R1"
        ),
        "criterion_digest": (
            "fdb2f08a9b19ee271223953d47bd3bd8a4b23c20eb95fc9d0a524727332e5863"
        ),
    },
    "cap-ref-ask-clarification": {
        "boundary_index": 1,
        "new_sentence": (
            "at C3-R1 the corpus carried no resource of this shape, which is"
            " why this node's links were placements then; the C3-c and C3-d"
            " cuts have since authored REALIZES rows for this node"
        ),
        "old_sentence": (
            "no resource of the current corpus is of this shape, which is"
            " why this node's links are placements at C3-R1"
        ),
        "criterion_digest": (
            "8da48503a7db12417df329eeb1f0b1e3304359137609144d5591b8ba7c1c71e0"
        ),
    },
}


def _canon(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _digest(payload: object) -> str:
    return hashlib.sha256(_canon(payload)).hexdigest()


def _old_evidence_paths() -> list[Path]:
    """The 82 pre-existing evidence documents, in sorted id order."""

    news = set(C3D_TARGETS)
    paths = [
        path
        for path in sorted((CONTENT_SRC_DIR / "evidence").glob("res-*.json"))
        if path.stem not in news
    ]
    assert len(paths) == 82
    return paths


def _links_document() -> dict:
    return json.loads(
        (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    )


def _capability_document(name: str) -> dict:
    return json.loads(
        (CURRICULUM_DIR / "capabilities" / f"{name}.json").read_text(
            encoding="utf-8"
        )
    )


def _levels_and_utilities(
    artifact: Path,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """The two read halves of the declared CORE reading, from the artifact."""

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
    """CORE_A / CORE_C under the declared reading (2026-09-26 adjudication)."""

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


def _entity_key_documents() -> dict[str, dict]:
    """Every `res-*` entity document in the authoring tree, keyed by id
    (the three-key dedup reads the source, which is where the keys live)."""

    documents: dict[str, dict] = {}
    for path in sorted((CONTENT_SRC_DIR / "entities").glob("res-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        documents[document["entity"]["entity_id"]] = document
    return documents


def _three_key_report(documents: dict[str, dict]) -> dict[str, list]:
    """The N-C3C-1 dedup over the corpus's three ownership-critical key
    spaces, from the entity documents' `teaching_content`.

    Returns the collision lists: canonical forms shared across entities,
    alternative realizations shared across entities, slot tokens shared
    between a C3-d entity and any other entity, and canonical ∩ alternative
    overlaps within one entity. (The pre-existing corpus's own slot-token
    sharing is INFO-2's registered legacy shape and is reported separately,
    never claimed away.)
    """

    canon: dict[str, set[str]] = {}
    alt: dict[str, set[str]] = {}
    slots: dict[str, set[str]] = {}
    for entity_id, document in documents.items():
        teaching = document["teaching_content"]
        for form in teaching.get("canonical_forms", []):
            canon.setdefault(form.strip().lower(), set()).add(entity_id)
        for form in teaching.get("alternative_realizations", []):
            alt.setdefault(form.strip().lower(), set()).add(entity_id)
        for group in teaching.get("required_slots", []):
            for token in group:
                slots.setdefault(str(token).strip().lower(), set()).add(
                    entity_id
                )
    news = set(C3D_TARGETS)
    return {
        "canonical_cross": sorted(
            key for key, ids in canon.items() if len(ids) > 1
        ),
        "alternative_cross": sorted(
            key for key, ids in alt.items() if len(ids) > 1
        ),
        "slot_new_vs_any": sorted(
            key
            for key, ids in slots.items()
            if len(ids & news) > 0 and len(ids) > 1
        ),
        "within_entity_overlap": sorted(
            entity_id
            for entity_id, document in documents.items()
            if {f.strip().lower() for f in
                document["teaching_content"].get("canonical_forms", [])}
            & {f.strip().lower() for f in
               document["teaching_content"].get("alternative_realizations", [])}
        ),
        "legacy_slot_groups": sorted(
            key
            for key, ids in slots.items()
            if len(ids) > 1 and ids <= set(documents) - news
        ),
    }


def _criterion_face(name: str, boundary_index: int) -> tuple[dict, object]:
    """The capability document minus the one boundary entry LOW-1 rewrote:
    the digest face that proves every criterion word is untouched."""

    document = _capability_document(name)
    face = json.loads(json.dumps(document))
    face["functional_definition"]["boundary_cases"] = [
        case
        for i, case in enumerate(
            document["functional_definition"]["boundary_cases"]
        )
        if i != boundary_index
    ]
    return face, document["functional_definition"]["boundary_cases"][
        boundary_index
    ]


def _evidence_variant(
    tmp_path: Path, target_id: str, edit: "object"
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
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


# ---------------------------------------------------------------------------
# ① the corpus truth at C3-d
# ---------------------------------------------------------------------------


def test_the_corpus_table_reads_52_r4_48_r1_and_5_none(
    built_content_db: Path,
) -> None:
    """The whole readiness table, read once at this cut's truth: the
    fifty-two `res-*` targets whose §24.7 row is a curriculum mapping read
    R4, the forty-eight placements read R1_LEXICALLY_RESOLVED, and the five
    `cap-*` entities read None. This cut's eighteen rows are all mappings, so
    the R4 side is 34 + 18 and the R1 side is unchanged."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    table = {a.target_id: a.level for a in assessments.value}
    assert len(table) == 105
    r4 = sorted(
        t for t, level in table.items() if level == "R4_DETECTION_READY"
    )
    r1 = sorted(
        t for t, level in table.items() if level == "R1_LEXICALLY_RESOLVED"
    )
    none = sorted(t for t, level in table.items() if level is None)
    assert len(r4) == 52
    assert len(r1) == 48
    assert len(none) == 5
    assert all(target.startswith("cap-") for target in none)
    unexpected = [
        level
        for level in table.values()
        if level not in (None, "R4_DETECTION_READY", "R1_LEXICALLY_RESOLVED")
    ]
    assert unexpected == []


def test_r4_is_exactly_the_prior_mappings_plus_the_eighteen_new_ones(
    built_content_db: Path,
) -> None:
    """The R4 set, id for id: the thirty-four resources whose rows were
    mappings before this cut, plus this cut's eighteen — no target entered
    R4 by any other door and none left it."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
    finally:
        store.close()
    table = {a.target_id: a.level for a in assessments.value}
    r4 = sorted(
        t for t, level in table.items() if level == "R4_DETECTION_READY"
    )
    assert r4 == sorted(set(PRIOR_R4) | set(C3D_TARGETS))
    assert len(PRIOR_R4) == 34
    assert set(PRIOR_R4).isdisjoint(C3D_TARGETS)


def test_resource_count_reads_100_of_105_entities(
    built_content_db: Path,
) -> None:
    """The volume counter and the entity table: 100 `res-*` resources of 105
    entities — the IP §13 28→100 ladder's first rung, topped."""

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
    assert len(resources) == 100
    assert len(entity_ids) == 105
    assert set(C3D_TARGETS) <= set(resources)


def test_the_three_calibration100_floors_read_separately_and_all_met(
    built_content_db: Path,
) -> None:
    """The three floors, each on its own line — the cut's honesty face.

    At C3-d's truth: CORE_A 32 >= 30 (**met**), CORE_C 20 >= 2 (met),
    resource_count 100 >= 100 (met, IP §13's 28→100 first rung topped):
    three assertions, three printed readings, and no single "gate passed"
    sentence. **Zero opening claim**: the floors meeting is the volume gate's
    answer, not the rollout's — the undeclared stage still refuses (pinned
    again in `test_no_opening_claim_is_made_by_this_cut`), SessionBudget's
    three-way split and the separate opening adjudication are untouched.
    The floor numbers come from the frozen plan text, not from a second
    hand-typed copy.
    """

    plan_text = _PLAN.read_text(encoding="utf-8")
    gates = {
        name: int(re.search(rf"{re.escape(name)} >= (\d+)", plan_text).group(1))
        for name in ("resource_count", "CORE_A", "CORE_C")
    }
    assert gates == _CALIBRATION100_FLOORS

    core_a, core_c = _core_counts(built_content_db)
    print(
        f"[c3d] CORE_A = {core_a} (floor {gates['CORE_A']},"
        f" {'met' if core_a >= gates['CORE_A'] else 'unmet'})"
    )
    print(
        f"[c3d] CORE_C = {core_c} (floor {gates['CORE_C']},"
        f" {'met' if core_c >= gates['CORE_C'] else 'unmet'})"
    )
    print(
        f"[c3d] resource_count = 100 (floor {gates['resource_count']},"
        f" {'met' if 100 >= gates['resource_count'] else 'unmet'})"
    )
    assert core_a >= gates["CORE_A"]  # CORE_A met (32 of 30)
    assert core_c >= gates["CORE_C"]  # CORE_C met
    assert 100 >= gates["resource_count"]  # volume floor met — to the top
    assert core_a + core_c == 52  # the CORE cells count the mapping set


def test_core_a_counts_the_twentyfour_survivors_plus_the_eight_new_highs(
    built_content_db: Path,
) -> None:
    """CORE_A = R3+ level ∧ core_utility HIGH. At C3-c's truth the reading
    answered 24; this cut's eight HIGH targets are all mappings by their own
    rows, so all eight read R4 and count — the reading answers 32. The bands
    are the cut's own authoring judgements (each new document's rationale
    says so, with the Revisit), not floor-chasing: the ten MEDIUM targets
    carry the same evidence face."""

    levels, utilities = _levels_and_utilities(built_content_db)
    core_a, _core_c = _core_counts(built_content_db)
    assert core_a == 32
    assert len(C3D_HIGH_TARGETS) == 8
    for target in C3D_HIGH_TARGETS:
        assert utilities[target] == "HIGH", target
        assert levels[target] == "R4_DETECTION_READY", target


def test_core_c_counts_the_ten_survivors_plus_the_ten_new_mediums(
    built_content_db: Path,
) -> None:
    """CORE_C = R3+ level ∧ core_utility MEDIUM/LOW. At C3-c's truth the
    reading answered 10; this cut's ten MEDIUM targets are all mappings, so
    the reading answers 20. The corpus's LOW arm is still C3-a's
    `res-pragmatic-could-i-ask`; this cut authored no LOW band.

    声明读法 + Revisit（用户 2026-09-26 裁决），与 CORE_A 同一条读法。
    """

    levels, utilities = _levels_and_utilities(built_content_db)
    _core_a, core_c = _core_counts(built_content_db)
    assert core_c == 20
    assert len(C3D_MEDIUM_TARGETS) == 10
    for target in C3D_MEDIUM_TARGETS:
        assert utilities[target] == "MEDIUM", target
        assert levels[target] == "R4_DETECTION_READY", target
    assert utilities["res-pragmatic-could-i-ask"] == "LOW"
    banded = {t for t in levels if t.startswith("res-")}
    assert len(banded) == 100


# ---------------------------------------------------------------------------
# ② the content gate stays GO over the widened table; nothing opens
# ---------------------------------------------------------------------------


def test_the_four_content_gate_rows_answer_go_over_the_new_table(
    built_content_db: Path,
) -> None:
    """BF-02 §10's four floors, checked by the real checker over the real
    table: every row GO, the report counting 105 targets of which 5 carry no
    level — and the stage leg still refuses, so nothing is open."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        report = corpus_rollout_gate(supply)
        assert isinstance(report, Ok), report
    finally:
        store.close()
    value = report.value
    assert value.verdict.name == "GO"
    assert len(value.rows) == 4
    assert all(row.verdict.name == "GO" for row in value.rows)
    assert value.targets_considered == 105
    assert value.targets_without_level == 5
    assert value.unknown_levels == ()
    assert stage_allows_automatic(None) is False


# ---------------------------------------------------------------------------
# ③ provenance: the new entities enter by structure, not by audit
# ---------------------------------------------------------------------------


def test_provenance_reads_54_author_and_the_46_editor_rows(
    built_content_db: Path,
) -> None:
    """The provenance read after the disposition cut landed the review's
    third audit record: 100 rows — one per evidence document — of which 46
    are EDITOR_REVIEWED (three records' disjoint approved lists: C3-R2's
    fifteen, C3-c's fifteen, and this cut's sixteen — twelve sampled new
    entities plus the four C3-c entities re-audited here) and 54 are
    AUTHOR_DECLARED; the six unsampled new entities stay at the baseline."""

    store = ContentStore(built_content_db)
    try:
        rows = store.provenance_levels()
        assert isinstance(rows, Ok), rows
    finally:
        store.close()
    levels = {entity: level for entity, level in rows.value}
    assert len(levels) == 100
    editor = sorted(
        e for e, lvl in levels.items() if lvl == "EDITOR_REVIEWED"
    )
    author = sorted(
        e for e, lvl in levels.items() if lvl == "AUTHOR_DECLARED"
    )
    assert len(editor) == 46
    assert len(author) == 54
    audit3 = json.loads(AUDIT3_PATH.read_text(encoding="utf-8"))
    approved3 = set(audit3["approved_entities"])
    assert approved3 == set(C3D_AUDITED_PASS)
    unsampled = set(C3D_TARGETS) - set(C3D_AUDITED_PASS)
    assert len(unsampled) == 6
    for target in unsampled:
        assert levels[target] == "AUTHOR_DECLARED", target
    for target in C3D_AUDITED_PASS:
        assert levels[target] == "EDITOR_REVIEWED", target
    higher = [
        (e, lvl)
        for e, lvl in levels.items()
        if lvl in ("EXECUTABLY_VERIFIED", "EMPIRICALLY_CALIBRATED")
    ]
    assert higher == []


def test_the_audit_directory_carries_the_four_records() -> None:
    """The audits directory holds the three records the C3-R2, C3-c and
    C3-d disposition cuts landed — the C3-d delivery cut itself wrote none
    (provenance promotion is a disposition-cut act on review evidence, never
    an authoring-cut act) — plus the W-5 key-face re-audit record, whose
    approved set is a subset of the prior union and so promotes nobody."""

    audit_files = sorted((CONTENT_SRC_DIR / "audits").glob("*.json"))
    assert [p.name for p in audit_files] == [
        "c3c-stratified-audit.json",
        "c3d-stratified-audit.json",
        "c3r2-stratified-audit.json",
        "w5-key-face-audit.json",
    ]


def test_provenance_stays_an_independent_dimension_outside_the_ladder(
    built_content_db: Path,
) -> None:
    """The ladder does not know provenance: no fact key names it, and the
    nineteen-key set is exactly what §8.1 requires — provenance widens
    nothing and blocks nothing."""

    for key in READINESS_FACT_KEYS:
        assert "provenance" not in key, key
        assert "EDITOR" not in key, key
    assert len(READINESS_FACT_KEYS) == 19


# ---------------------------------------------------------------------------
# ④ the eighteen new targets, one by one (new template obligations)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", C3D_TARGETS)
def test_each_new_target_carries_nineteen_keys_reads_r4_and_covers_its_errors(
    built_content_db: Path, target_id: str
) -> None:
    """Per new target, the whole new template at once: every §8.1 fact key
    present (including `curriculum_link` — this cut's rows are mappings),
    the level reads R4_DETECTION_READY, the document declares exactly two
    error types with one POSITIVE_ERROR fixture per type, the rule ordinals
    stay dense with the bounded fixtures and the positives append after
    them, all three fixture kinds are present with kind and expected
    agreeing, and the four text roles are in place."""

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

    document = json.loads(
        (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").read_text(
            encoding="utf-8"
        )
    )
    errors = document["typical_errors"]
    fixtures = document["detection_fixtures"]
    rules = sorted(int(row["ordinal"]) for row in document["detection_rules"])
    bounded = sorted(
        int(row["ordinal"])
        for row in fixtures
        if row["kind"] != "POSITIVE_ERROR"
    )
    positives = sorted(
        int(row["ordinal"])
        for row in fixtures
        if row["kind"] == "POSITIVE_ERROR"
    )
    assert len(errors) == 2, target_id
    assert len({row["error_type"] for row in errors}) == 2, target_id
    assert len(positives) == 2, target_id
    assert rules == bounded == list(range(len(rules))), target_id
    assert positives == list(
        range(len(rules), len(rules) + len(positives))
    ), target_id
    assert len(rules) >= 2, target_id
    kinds = {str(row["kind"]) for row in fixtures}
    assert kinds == set(FIXTURE_KINDS), (target_id, kinds)
    for row in fixtures:
        assert str(row["expected"]) in EXPECTED_READINGS, (target_id, row)
        assert (str(row["kind"]) == "NEGATIVE") == (
            str(row["expected"]) == "NO_MATCH"
        ), (target_id, row)
        assert (str(row["kind"]) == "POSITIVE_ERROR") == (
            str(row["expected"]) == "MATCH"
        ), (target_id, row)
    roles = {str(row["role"]) for row in document["texts"]}
    assert {"definition", "usage", "teaching_note", "translation"} <= roles, (
        target_id,
        roles,
    )
    profile = document["pedagogical_profile"]
    assert profile["core_utility"] in UTILITY_BANDS, target_id
    assert "V1 carries no calibration data" in str(profile["rationale"])
    assert "Revisit" in str(profile["rationale"])


def test_the_new_documents_keep_the_policy_versions_and_the_overlays() -> None:
    """The declared policy versions and the overlay/label faces the loader
    reads, over all eighteen documents."""

    for target_id in C3D_TARGETS:
        document = json.loads(
            (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").read_text(
                encoding="utf-8"
            )
        )
        assert (
            document["detection_policy"]["policy_version"]
            == "detection-policy-v1"
        ), target_id
        assert (
            document["example_policy"]["policy_version"] == "example-policy-v1"
        ), target_id
        assert document["typical_error_required"] is True, target_id
        assert document["detection_rules"], target_id
        assert document["resource_labels"], target_id
        assert document["pack_overlays"], target_id
        overlay_ids = {row["pack_id"] for row in document["pack_overlays"]}
        assert overlay_ids == {
            "pack-general-fluency-v1",
            "pack-workplace-communication-v1",
        }, target_id
        membership = document["assessment_membership"]
        assert membership[0]["assessment_id"] == "elc-placement-bank-v1"
        assert membership[0]["membership_status"] == "MEMBER"
        assert "C3-d authoring declaration" in str(membership[0]["source"])


def test_every_new_boundary_fixture_guards_a_declared_reading() -> None:
    """The context-guard obligations of this cut's selection list: the four
    named guard readings (right's adjective reading, go-on's urging reading,
    come-again's literal return invitation, no-way's refusal) each sit in
    their own document's FALSE_POSITIVE_BOUNDARY fixture, and every new
    document carries exactly one such fixture whose text differs from every
    NEGATIVE row's (the boundary is a different sentence, not a repeat)."""

    guards = {
        "res-pragmatic-right": "the right answer",
        "res-pragmatic-go-on": "take the last biscuit",
        "res-pragmatic-come-again": "come again next weekend",
        "res-pragmatic-no-way": "not lending you the car",
    }
    for target_id in C3D_TARGETS:
        document = json.loads(
            (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").read_text(
                encoding="utf-8"
            )
        )
        boundaries = [
            str(row["text"])
            for row in document["detection_fixtures"]
            if row["kind"] == "FALSE_POSITIVE_BOUNDARY"
        ]
        negatives = {
            str(row["text"])
            for row in document["detection_fixtures"]
            if row["kind"] == "NEGATIVE"
        }
        assert len(boundaries) == 1, target_id
        assert boundaries[0] not in negatives, target_id
        if target_id in guards:
            assert guards[target_id].lower() in boundaries[0].lower(), target_id


# ---------------------------------------------------------------------------
# ⑤ the untouched faces, blob for blob
# ---------------------------------------------------------------------------


def test_the_existing_82_link_rows_are_untouched_blob_for_blob() -> None:
    """The 82 rows this cut appended after are byte-identical through their
    canonical JSON: same ids in the same order, same digest — and the new
    eighteen are exactly the rows appended at the end, in the declared
    authoring order."""

    rows = _links_document()["links"]
    assert len(rows) == 100
    first = rows[:82]
    assert _digest(first) == LINKS82_DIGEST
    appended = [str(row["resource_id"]) for row in rows[82:]]
    assert appended == list(APPEND_ORDER)
    assert sorted(appended) == sorted(C3D_TARGETS)
    assert len(appended) == 18


def test_the_existing_fixture_rows_are_untouched_blob_for_blob() -> None:
    """The 487 fixture rows of the 82 old documents digest to the frozen
    value and still count 242 / 85 / 160; the eighteen new documents
    contribute exactly 54 / 18 / 36, so the artifact total is 296 / 103 /
    196 = 595 and every old row is inside the digest.

    D-1 migration: the digest is computed over each row's four original
    keys (``ordinal`` / ``kind`` / ``text`` / ``expected`` — D-1 later
    appended the nullable ``source_error_type`` key to positive rows), and
    the projection is additionally proven exact: every old row equals its
    own projection plus at most that one appended key."""

    fx_digest = hashlib.sha256()
    totals = {"NEGATIVE": 0, "FALSE_POSITIVE_BOUNDARY": 0, "POSITIVE_ERROR": 0}
    for path in _old_evidence_paths():
        document = json.loads(path.read_text(encoding="utf-8"))
        rows = document["detection_fixtures"]
        fx_digest.update(
            _canon(
                [
                    {
                        key: row[key]
                        for key in ("ordinal", "kind", "text", "expected")
                    }
                    for row in rows
                ]
            )
        )
        for row in rows:
            totals[str(row["kind"])] += 1
            if row["kind"] == "POSITIVE_ERROR":
                assert set(row) == {
                    "ordinal",
                    "kind",
                    "text",
                    "expected",
                    "source_error_type",
                }, (path.name, row["ordinal"])
            else:
                assert set(row) == {
                    "ordinal",
                    "kind",
                    "text",
                    "expected",
                }, (path.name, row["ordinal"])
    assert fx_digest.hexdigest() == FIXTURES_DIGEST
    assert totals == OLD_FIXTURE_TOTALS
    new_totals = {
        "NEGATIVE": 0,
        "FALSE_POSITIVE_BOUNDARY": 0,
        "POSITIVE_ERROR": 0,
    }
    for target in C3D_TARGETS:
        document = json.loads(
            (CONTENT_SRC_DIR / "evidence" / f"{target}.json").read_text(
                encoding="utf-8"
            )
        )
        for row in document["detection_fixtures"]:
            new_totals[str(row["kind"])] += 1
    assert new_totals == NEW_FIXTURE_TOTALS


def test_the_existing_typical_error_rows_are_untouched_blob_for_blob() -> None:
    """The typical_errors arrays of the 82 old documents digest to the
    frozen value — this cut authored two errors per new target and touched
    no old one."""

    digest = hashlib.sha256()
    for path in _old_evidence_paths():
        document = json.loads(path.read_text(encoding="utf-8"))
        digest.update(_canon(document["typical_errors"]))
    assert digest.hexdigest() == TYPICAL_ERRORS_DIGEST


def test_the_existing_detection_rules_are_untouched_blob_for_blob() -> None:
    """The detection rules of the 82 old documents digest to the frozen
    value — no LOW-2-style reconciliation was needed this time, so the rules
    face is wholly untouched."""

    digest = hashlib.sha256()
    for path in _old_evidence_paths():
        document = json.loads(path.read_text(encoding="utf-8"))
        digest.update(_canon(document["detection_rules"]))
    assert digest.hexdigest() == RULES_DIGEST


# ---------------------------------------------------------------------------
# ⑥ the credit face: 33 → 51, node by node
# ---------------------------------------------------------------------------


def test_the_credit_face_widens_from_33_to_51_and_the_prior_nodes_stand(
    built_content_db: Path,
) -> None:
    """The credit read keys on REALIZES rows: the corpus now carries 51, the
    thirty-three prior rows credit exactly the node they credited before
    this cut, and the eighteen new rows credit the node their own row names
    — the live risk R-C1-credit's registered face widens with them, and its
    Revisit does not move."""

    rows = _links_document()["links"]
    realizes = {
        str(row["resource_id"]): str(row["node_id"])
        for row in rows
        if row["relation"] == "REALIZES"
    }
    assert len(realizes) == 51
    assert set(C3D_TARGETS) <= set(realizes)

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        credited: dict[str, str] = {}
        for entity_id in store.entity_ids().value:
            teaching = supply.get_teaching_content(entity_id)
            assert isinstance(teaching, Ok), teaching
            if teaching.value.capability_linkage is not None:
                credited[str(entity_id)] = str(
                    teaching.value.capability_linkage
                )
    finally:
        store.close()
    assert credited == realizes
    assert len(PRIOR_CREDIT) == 33
    for target, node in PRIOR_CREDIT.items():
        assert credited[target] == node, target
    for target in C3D_TARGETS:
        assert credited[target] == C3D_NODE_OF[target], target


def test_every_new_link_adjudicates_against_its_capability_definition() -> None:
    """Every new row is a REALIZES + CURRICULUM_MAPPING + approved row with a
    null strength and the true primary flag, and its rationale is written in
    the adjudication genre: it names the node and that node's functional-
    definition file, cites `counts_as_realization` as the criterion it was
    judged by, states its credit consequence in its own words, states its
    provenance (C3-d, no authoring fixture) and registers its Revisit."""

    rows = _links_document()["links"]
    new_rows = {
        str(row["resource_id"]): row
        for row in rows
        if str(row["resource_id"]) in set(C3D_TARGETS)
    }
    assert sorted(new_rows) == sorted(C3D_TARGETS)
    for target_id, row in new_rows.items():
        assert row["relation"] == "REALIZES", target_id
        assert row["mapping_class"] == "CURRICULUM_MAPPING", target_id
        assert row["editorial_status"] == "CANONICAL_APPROVED", target_id
        assert row["strength"] is None, target_id
        assert row["primary_flag"] is True, target_id
        node = str(row["node_id"])
        assert node == C3D_NODE_OF[target_id], target_id
        rationale = str(row["rationale"])
        assert node in rationale, target_id
        assert f"curriculum/capabilities/{node}.json" in rationale, target_id
        assert "CURRICULUM_MAPPING" in rationale, target_id
        assert "counts_as_realization" in rationale, target_id
        assert "does_not_count" in rationale, target_id
        assert "credit face" in rationale, target_id
        assert "C3-d (Phase 11)" in rationale, target_id
        assert "no authoring fixture" in rationale, target_id
        assert "Revisit" in rationale, target_id
        assert "Row provenance:" in rationale, target_id


def test_realizes_implies_curriculum_mapping_across_the_whole_corpus() -> None:
    """The build rule C3-R1 landed, read over the whole source: no row is a
    REALIZES placement. The one REALIZES + PLACEMENT mutation a careless
    author could write is a build refusal, and this pin states the source
    side of the same rule over all 100 rows."""

    rows = _links_document()["links"]
    assert len(rows) == 100
    for row in rows:
        if row["relation"] == "REALIZES":
            assert row["mapping_class"] == "CURRICULUM_MAPPING", row
    mixed = [
        row
        for row in rows
        if row["relation"] == "REALIZES"
        and row["mapping_class"] == "COVERAGE_PLACEMENT"
    ]
    assert mixed == []


def test_a_new_row_rewritten_into_a_placement_is_refused_by_the_build(
    tmp_path: Path,
) -> None:
    """The same rule from the build side: rewriting one new row's
    mapping_class to COVERAGE_PLACEMENT while keeping REALIZES is a
    BuildError and no artifact is written."""

    def rewrite(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == "res-pragmatic-right":
                assert row["relation"] == "REALIZES"
                row["mapping_class"] = "COVERAGE_PLACEMENT"

    with pytest.raises(BuildError, match="REALIZES"):
        build_variant_artifact(tmp_path, curriculum_edit=rewrite)


# ---------------------------------------------------------------------------
# ⑦ the three-key dedup (N-C3C-1's in-cut obligation), keyed spaces
# ---------------------------------------------------------------------------


def test_the_three_key_spaces_are_collision_free_over_100_entities() -> None:
    """The N-C3C-1 dedup, run in-cut and pinned: across the whole
    100-resource corpus no canonical form and no alternative realization is
    shared between two entities, and within every entity the canonical and
    alternative key sets are disjoint. The slot-token face moved with W-5
    (旧真值 C3-d: no C3-d slot token shared with any other entity; 新真值
    W-5: the bare formula's own tokens `come`/`again`/`way` are shared) and
    is pinned to that exact closed list below. The pre-existing corpus's own
    slot-token sharing (INFO-2's registered legacy group shape — content
    words like `time` or `point` inside old slot groups) is declared here,
    not claimed away: the pin reports it as the legacy set and asserts only
    that no **new** key enters any collision beyond the declared list."""

    documents = _entity_key_documents()
    assert len(documents) == 100
    report = _three_key_report(documents)
    assert report["canonical_cross"] == [], report["canonical_cross"]
    assert report["alternative_cross"] == [], report["alternative_cross"]
    # 旧真值 (C3-d): []. W-5 真值: the key-face cut replaced two C3-d
    # entities' in-sentence content-word slots with the bare formula's own
    # tokens, and those tokens are shared with legacy slot groups
    # (`come`/`again` via res-pragmatic-come-again, `way` via
    # res-pragmatic-no-way). v3-1 真值: the slot-criterion rewrite
    # （槽位 = 目标自身的词汇材料）rewrote sixty keys; the C3-d entities
    # among them now share these tokens with the rest of the corpus
    # (`ask` via res-hedge-if-you-ask-me, `come`/`on` via
    # res-pragmatic-go-on and res-phrasal-come-up-with, `run` via
    # res-pragmatic-run-that-by-me-again and res-phrasal-run-out-of,
    # `way` via res-discourse-by-the-way and res-hedge-in-a-way,
    # `again` via res-pragmatic-come-again). Declared as this exact
    # closed list — no other C3-d slot token entered any collision.
    assert report["slot_new_vs_any"] == ["again", "ask", "come", "on", "run", "way"], (
        report["slot_new_vs_any"]
    )
    assert report["within_entity_overlap"] == []
    # INFO-2's legacy shape, declared: the corpus's own shared slot
    # tokens. 旧真值 (C3-d): 34. v3-1 真值: 21 — the slot rewrite moved
    # the example-scene topic words out of the key faces, so most of the
    # old in-sentence content-word collisions (english/design/answer/
    # train/booking/...) left the slot space entirely. This is the
    # registered reading — a future cut that shrinks it may move this pin
    # with the truth.
    assert len(report["legacy_slot_groups"]) == 21


def test_the_new_id_lists_declare_their_ordering_convention() -> None:
    """N-C3C-2's ordering declaration, made testable: this file's id lists
    are plain-id sorted, the index's lists are full-path sorted, and the two
    rules genuinely disagree on the `-` < `.` boundary — so the declaration
    is load-bearing, not decoration. The corpus's own pair
    `res-pragmatic-could-you` / `res-pragmatic-could-you-clarify` is the
    witness."""

    assert list(C3D_TARGETS) == sorted(C3D_TARGETS)
    assert list(APPEND_ORDER) == sorted(APPEND_ORDER)  # authoring order
    index = json.loads(
        (CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8")
    )
    entities = [str(entry) for entry in index["entities"]]
    evidence = [str(entry) for entry in index["evidence"]]
    assert entities == sorted(entities)
    assert evidence == sorted(evidence)
    # the path sort puts the longer id first (…clarify.json before …you.json)
    pair_paths = sorted(
        [
            "entities/res-pragmatic-could-you-clarify.json",
            "entities/res-pragmatic-could-you.json",
        ]
    )
    assert pair_paths[0] == "entities/res-pragmatic-could-you-clarify.json"
    assert pair_paths[1] == "entities/res-pragmatic-could-you.json"
    # …while the plain-id sort puts the shorter id first
    pair_ids = sorted(
        ["res-pragmatic-could-you", "res-pragmatic-could-you-clarify"]
    )
    assert pair_ids[0] == "res-pragmatic-could-you"
    assert pair_ids[1] == "res-pragmatic-could-you-clarify"
    # and the index really carries both in the path order
    assert entities.index("entities/res-pragmatic-could-you-clarify.json") < (
        entities.index("entities/res-pragmatic-could-you.json")
    )


# ---------------------------------------------------------------------------
# ⑧ the LOW-1 closure: the two capability files, sentence and criterion face
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("capability", sorted(LOW1_EDITS))
def test_low1_sentences_are_time_qualified(capability: str) -> None:
    """The placement-era narrative sentence is gone from both capability
    files and the time-qualified wording stands in its place: the boundary
    entry now says the corpus carried no resource of this shape **at C3-R1**
    and names the cuts that have since authored REALIZES rows."""

    spec = LOW1_EDITS[capability]
    _face, boundary = _criterion_face(
        capability, int(spec["boundary_index"])
    )
    text = str(boundary)
    assert spec["new_sentence"] in text, capability
    assert spec["old_sentence"] not in text, capability


@pytest.mark.parametrize("capability", sorted(LOW1_EDITS))
def test_low1_criterion_faces_are_untouched_against_the_parent_commit(
    capability: str,
) -> None:
    """Only the narrative sentence moved: the digest over each file's
    criterion face — the whole document minus the one rewritten boundary
    entry — equals the parent-commit value, so statement,
    counts_as_realization, does_not_count, every other boundary case and the
    basis are byte-identical (canonical JSON). The criterion digests below
    are the parent-commit blobs', computed once and frozen."""

    spec = LOW1_EDITS[capability]
    face, _boundary = _criterion_face(capability, int(spec["boundary_index"]))
    assert _digest(face) == str(spec["criterion_digest"]), capability


# ---------------------------------------------------------------------------
# ⑨ determinism on the widened corpus
# ---------------------------------------------------------------------------


def test_two_builds_of_the_widened_source_are_byte_equal(tmp_path: Path) -> None:
    """Two builds of the same source produce the same bytes, and the report
    counts 105 entities / 100 evidence documents / 100 links / 5
    capabilities."""

    first = tmp_path / "a.db"
    second = tmp_path / "b.db"
    build_content_db(first)
    build_content_db(second)
    assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(
        second.read_bytes()
    ).hexdigest()
    report = build_content_db(tmp_path / "c.db")
    assert report.entity_count == 105
    assert report.evidence_count == 100
    assert report.link_count == 100
    assert report.capability_count == 5


def test_a_subprocess_build_matches_the_bytes_under_pythonhashseed(
    tmp_path: Path,
) -> None:
    """Cross-process determinism: fresh interpreters under two different
    ``PYTHONHASHSEED`` values build from the same source and hash equal to
    this process's build (three builds, three seeds, one digest)."""

    script = (
        "import sys;"
        "from elc.content.build import build_content_db;"
        "build_content_db(sys.argv[1])"
    )
    src = str(Path(__file__).resolve().parents[2] / "src")
    in_process = tmp_path / "in-process.db"
    build_content_db(in_process)
    expected = hashlib.sha256(in_process.read_bytes()).hexdigest()
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
        )
        assert hashlib.sha256(output.read_bytes()).hexdigest() == expected, seed


# ---------------------------------------------------------------------------
# ⑩ the version stays, the index lists both trees in order, nothing opens
# ---------------------------------------------------------------------------


def test_content_db_version_tracks_the_current_generation(
    built_content_db: Path,
) -> None:
    """No schema change of this cut's own: the module constant and the built
    artifact moved "4" → "5" when D-1 later added the nullable
    ``content_detection_fixture.source_error_type`` column, and "5" → "6"
    when D-5R added the ``content_verification_profile`` table; they read
    the current generation."""

    assert CONTENT_DB_VERSION == "6"
    conn = sqlite3.connect(str(built_content_db))
    try:
        row = conn.execute(
            "SELECT value FROM content_meta WHERE key = 'content_db_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == CONTENT_DB_VERSION == "6"


def test_the_index_lists_105_and_100_documents_in_sorted_order() -> None:
    """The index grew in both lists: entity documents 87 → 105, evidence
    documents 82 → 100, both full-path sort order (the declared convention),
    and the eighteen new ids appear in each list exactly once."""

    index = json.loads(
        (CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8")
    )
    entities = [str(entry) for entry in index["entities"]]
    evidence = [str(entry) for entry in index["evidence"]]
    assert len(entities) == 105
    assert len(evidence) == 100
    assert entities == sorted(entities)
    assert evidence == sorted(evidence)
    for target_id in C3D_TARGETS:
        assert entities.count(f"entities/{target_id}.json") == 1, target_id
        assert evidence.count(f"evidence/{target_id}.json") == 1, target_id
        assert (CONTENT_SRC_DIR / "entities" / f"{target_id}.json").is_file()
        assert (CONTENT_SRC_DIR / "evidence" / f"{target_id}.json").is_file()


def test_an_index_entry_missing_its_document_is_refused(tmp_path: Path) -> None:
    """The strict loader gives the widened index no leniency: an index entry
    whose document does not exist is a BuildError and no artifact is
    written."""

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    (content_src / "entities" / "res-pragmatic-right.json").unlink()
    with pytest.raises(BuildError, match="listed document does not exist"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_an_unknown_fixture_kind_in_a_new_document_is_refused(
    tmp_path: Path,
) -> None:
    """The vocabulary wall holds for the new documents: a fixture row whose
    kind is not one of the three declared words is a BuildError."""

    def inject(document: dict) -> None:
        document["detection_fixtures"].append(
            {"ordinal": 9, "kind": "POSITIVE", "text": "x", "expected": "MATCH"}
        )

    with pytest.raises(BuildError, match="outside the canonical set"):
        _evidence_variant(tmp_path, "res-pragmatic-right", inject)


def test_deleting_a_positive_fixture_from_a_new_document_is_refused(
    tmp_path: Path,
) -> None:
    """The per-error_type coverage check is build-level and load-bearing for
    the new documents: dropping one POSITIVE_ERROR row from a two-type
    document leaves one type uncovered and the build refuses (the receipt's
    '删新实体正例 ⇒ 覆盖钉' mutation, stated from the build side)."""

    def drop(document: dict) -> None:
        positives = [
            row
            for row in document["detection_fixtures"]
            if row["kind"] == "POSITIVE_ERROR"
        ]
        assert len(positives) == 2
        document["detection_fixtures"].remove(positives[-1])

    # D-1 truth update: the build refuses by naming the uncovered declared
    # error type (the per-type coverage check that replaced the row-count
    # proxy), so the match reads the check's own words.
    with pytest.raises(BuildError, match="no POSITIVE_ERROR fixture"):
        _evidence_variant(tmp_path, "res-pragmatic-right", drop)


def test_no_opening_claim_is_made_by_this_cut() -> None:
    """The stage leg is the only door and this cut did not touch it: the
    undeclared stage still refuses, and the authoring tree carries no stage
    declaration — three floors met is a content-gate answer, not an
    opening."""

    assert stage_allows_automatic(None) is False
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(CONTENT_SRC_DIR.rglob("*.json"))
    ) + (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    assert "rollout_stage" not in blob
    assert "ROLLOUT" not in blob
