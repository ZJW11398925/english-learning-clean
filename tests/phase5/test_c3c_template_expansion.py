"""C3-c (Phase 11) — the new template's first batch: eighteen more RESOURCE
targets take the corpus to 82.

What this cut did, and what this file pins:

- **the corpus truth at C3-c**: 87 entities (5 `cap-*` + 82 `res-*`),
  **34 × R4_DETECTION_READY + 48 × R1_LEXICALLY_RESOLVED + 5 × None**,
  `resource_count` = 82, links 82 (33 REALIZES + 49 SUPPORTS; 34
  CURRICULUM_MAPPING + 48 COVERAGE_PLACEMENT), evidence documents 82. CORE_A
  reads 24 (11 + the cut's 13 HIGH targets) and CORE_C reads 10 (5 + its 5
  MEDIUM targets) under the **declared reading** the user's adjudication
  fixed at C3-a (R3+ level × `core_utility` band; Revisit when the canonical
  Calibration100 definition lands).
- **the three floors are pinned apart** — CORE_A 24 < 30 unmet, CORE_C
  10 >= 2 met, `resource_count` 82 < 100 unmet — and never as one combined
  "gate passed/failed" sentence. The four BF-02 §10 content rows answer GO
  over the widened table, and no rollout opening is claimed.
- **the new-template obligations hold**: every new entity carries a
  POSITIVE_ERROR fixture per declared error_type (the build refuses less),
  every new link's mapping_class was adjudicated against its capability's
  functional definition with the criterion entries named, and the eighteen
  new entities entered provenance as AUTHOR_DECLARED by structure alone —
  no audit record was written for them.
- **the untouched faces are pinned blob-for-blob**: the existing 64 link
  rows, the existing 379 fixture rows, the existing typical-error rows, and
  every existing detection rule except the one row the LOW-2 reconciliation
  fixed (`res-softener-if-anything` rule ordinal 2) — each behind a sha256
  digest over the canonical JSON of the frozen rows.
- **the credit face widens 15 → 33** by the cut's eighteen REALIZES rows:
  the fifteen prior REALIZES rows credit the same nodes as before, the
  eighteen new rows name the node their own row points at, and the live risk
  R-C1-credit's registered face widens with them.

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

#: The eighteen RESOURCE targets C3-c authored as entities, evidence
#: documents and links, in id order.
C3C_TARGETS = (
    "res-discourse-moving-on",
    "res-discourse-on-another-note",
    "res-discourse-speaking-of-which",
    "res-discourse-to-get-back-to-the-point",
    "res-hedge-as-far-as-i-know",
    "res-hedge-if-im-not-mistaken",
    "res-hedge-it-seems-to-me",
    "res-pragmatic-are-you-saying",
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-fair-enough",
    "res-pragmatic-got-it",
    "res-pragmatic-i-see",
    "res-pragmatic-i-see-your-point-but",
    "res-pragmatic-let-me-make-sure",
    "res-pragmatic-that-makes-sense",
    "res-pragmatic-up-to-a-point",
    "res-pragmatic-what-do-you-mean",
    "res-pragmatic-with-all-due-respect",
)

#: The eighteen RESOURCE targets C3-d authored after this cut (readable
#: here so this file's whole-corpus pins can state the post-C3-d truth
#: without importing a sibling test module). Plain id sort order.
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

#: The thirteen C3-c targets whose pedagogical profile declares core_utility
#: HIGH (they move CORE_A from 11 to 24).
C3C_HIGH_TARGETS = (
    "res-discourse-moving-on",
    "res-discourse-on-another-note",
    "res-discourse-speaking-of-which",
    "res-discourse-to-get-back-to-the-point",
    "res-hedge-as-far-as-i-know",
    "res-hedge-it-seems-to-me",
    "res-pragmatic-fair-enough",
    "res-pragmatic-got-it",
    "res-pragmatic-i-see",
    "res-pragmatic-that-makes-sense",
    "res-pragmatic-what-do-you-mean",
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-i-see-your-point-but",
)

#: The five C3-c targets that declare MEDIUM (they move CORE_C from 5 to 10).
#: This cut authored no LOW band; the corpus's LOW example is still
#: `res-pragmatic-could-i-ask` (C3-a).
C3C_MEDIUM_TARGETS = (
    "res-hedge-if-im-not-mistaken",
    "res-pragmatic-are-you-saying",
    "res-pragmatic-let-me-make-sure",
    "res-pragmatic-up-to-a-point",
    "res-pragmatic-with-all-due-respect",
)

#: The node each C3-c row maps into (every row of this cut is a
#: CURRICULUM_MAPPING; the capability file named in the rationale must be
#: this node's).
C3C_NODE_OF = {
    "res-discourse-moving-on": "cap-disc-topic-shift",
    "res-discourse-on-another-note": "cap-disc-topic-shift",
    "res-discourse-speaking-of-which": "cap-disc-topic-shift",
    "res-discourse-to-get-back-to-the-point": "cap-disc-topic-shift",
    "res-hedge-as-far-as-i-know": "cap-eval-hedged-opinion",
    "res-hedge-if-im-not-mistaken": "cap-eval-hedged-opinion",
    "res-hedge-it-seems-to-me": "cap-eval-hedged-opinion",
    "res-pragmatic-are-you-saying": "cap-ref-ask-clarification",
    "res-pragmatic-could-you-say-that-again": "cap-ref-ask-clarification",
    "res-pragmatic-fair-enough": "cap-interact-backchannel",
    "res-pragmatic-got-it": "cap-interact-backchannel",
    "res-pragmatic-i-see": "cap-interact-backchannel",
    "res-pragmatic-i-see-your-point-but": "cap-stance-soften-disagreement",
    "res-pragmatic-let-me-make-sure": "cap-ref-ask-clarification",
    "res-pragmatic-that-makes-sense": "cap-interact-backchannel",
    "res-pragmatic-up-to-a-point": "cap-stance-soften-disagreement",
    "res-pragmatic-what-do-you-mean": "cap-ref-ask-clarification",
    "res-pragmatic-with-all-due-respect": "cap-stance-soften-disagreement",
}

#: The sixteen resources whose §24.7 rows were curriculum mappings before
#: this cut (C3-R1's mapping set); their ids are what R4 was at C3-R2.
PRIOR_R4 = (
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

#: The fifteen rows that credited a capability before this cut (C3-R1's
#: surviving REALIZES set), each with the node it credits. The eighteen new
#: rows widen this face to thirty-three; these fifteen must credit the same
#: node as before.
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
    "res-hedge-not-really": None,  # SUPPORTS + MAPPING: readable, no credit
    "res-hedge-sort-of": "cap-stance-soften-disagreement",
    "res-pragmatic-no-offense-but": "cap-stance-soften-disagreement",
    "res-pragmatic-thats-a-good-point-but": "cap-stance-soften-disagreement",
    "res-softener-a-bit": "cap-stance-soften-disagreement",
    "res-softener-kind-of": "cap-stance-soften-disagreement",
    "res-softener-to-be-fair": "cap-stance-soften-disagreement",
}

#: The provenance audit record C3-R2's disposition landed (the first audit
#: record in the tree; the delivery cut wrote none).
AUDIT_PATH = CONTENT_SRC_DIR / "audits" / "c3r2-stratified-audit.json"

#: The second audit record — this cut's disposition landing the review's
#: stratified audit of the new-template first run.
AUDIT2_PATH = CONTENT_SRC_DIR / "audits" / "c3c-stratified-audit.json"

#: The third record — the C3-d disposition re-auditing this cut's four
#: unsampled leftovers among its own sixteen approvals.
AUDIT3_PATH = CONTENT_SRC_DIR / "audits" / "c3d-stratified-audit.json"

#: The fifteen entities that review passed on both faces: fourteen of this
#: cut's eighteen (the four unsampled — that-makes-sense,
#: could-you-say-that-again, got-it, with-all-due-respect — are deliberately
#: withheld, strict over lenient) plus res-softener-if-anything, re-audited
#: once its LOW-2 detection-rules reconciliation had landed.
C3C_AUDITED_PASS = (
    "res-discourse-moving-on",
    "res-discourse-on-another-note",
    "res-discourse-speaking-of-which",
    "res-discourse-to-get-back-to-the-point",
    "res-hedge-as-far-as-i-know",
    "res-hedge-if-im-not-mistaken",
    "res-hedge-it-seems-to-me",
    "res-pragmatic-are-you-saying",
    "res-pragmatic-fair-enough",
    "res-pragmatic-i-see",
    "res-pragmatic-i-see-your-point-but",
    "res-pragmatic-let-me-make-sure",
    "res-pragmatic-up-to-a-point",
    "res-pragmatic-what-do-you-mean",
    "res-softener-if-anything",
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

#: The sha256 digest over the canonical JSON of the 64 pre-existing link
#: rows as one list, in document order (blob-for-blob zero-change pin).
LINKS64_DIGEST = (
    "d641c78088cfd79ebd23ec22a1f9b5454283d56f1598e40aaeb907f807d889b1"
)

#: The first 64 rows' resource ids, in document order (readable half of the
#: same pin — document order is the historical append order, not id order).
LINKS64_IDS = (
    "res-discourse-to-be-honest",
    "res-discourse-anyway",
    "res-hedge-im-not-sure",
    "res-hedge-it-depends",
    "res-softener-a-bit",
    "res-pragmatic-thats-a-good-point-but",
    "res-colloc-take-part-in",
    "res-colloc-meet-a-deadline",
    "res-colloc-play-a-role",
    "res-colloc-heavy-rain",
    "res-colloc-make-sense",
    "res-phrasal-figure-out",
    "res-phrasal-come-up-with",
    "res-phrasal-run-out-of",
    "res-idiom-on-the-same-page",
    "res-idiom-piece-of-cake",
    "res-frame-would-you-mind",
    "res-frame-what-im-saying-is",
    "res-pragmatic-sorry-to-interrupt",
    "res-hedge-i-think",
    "res-softener-kind-of",
    "res-colloc-pay-attention-to",
    "res-frame-id-like-to",
    "res-discourse-by-the-way",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
    "res-idiom-break-the-ice",
    "res-colloc-make-a-decision",
    "res-hedge-sort-of",
    "res-softener-to-be-fair",
    "res-discourse-having-said-that",
    "res-colloc-keep-in-mind",
    "res-colloc-take-advantage-of",
    "res-colloc-come-to-a-conclusion",
    "res-colloc-draw-attention-to",
    "res-colloc-have-an-effect-on",
    "res-phrasal-give-up",
    "res-phrasal-carry-on",
    "res-phrasal-turn-out",
    "res-idiom-hit-the-nail-on-the-head",
    "res-idiom-under-the-weather",
    "res-discourse-in-fact",
    "res-frame-if-you-dont-mind",
    "res-frame-lets-say",
    "res-hedge-i-mean",
    "res-pragmatic-could-i-ask",
    "res-colloc-make-progress",
    "res-colloc-save-time",
    "res-colloc-take-a-look",
    "res-colloc-raise-awareness",
    "res-colloc-make-an-effort",
    "res-phrasal-work-out",
    "res-phrasal-bring-up",
    "res-phrasal-put-off",
    "res-idiom-the-ball-is-in-your-court",
    "res-idiom-a-blessing-in-disguise",
    "res-discourse-that-reminds-me",
    "res-discourse-long-story-short",
    "res-frame-just-wondering",
    "res-frame-the-thing-is",
    "res-hedge-i-guess",
    "res-hedge-not-really",
    "res-softener-if-anything",
    "res-pragmatic-no-offense-but",
)

#: Digests over the 64 pre-existing evidence documents' frozen faces. The
#: detection-rules digest excludes exactly one row — rule ordinal 2 of
#: `res-softener-if-anything` — because the LOW-2 reconciliation (DEC-OPI-
#: 643b9639-…12) is the one registered change this cut was allowed to make;
#: the same document's rules 0, 1 and 3, its fixtures and its typical errors
#: are inside the digests like every other old document's.
FIXTURES_DIGEST = (
    "58bba543e60247033dde31cc6f135405ae96890d3574000185596abc47934f35"
)
TYPICAL_ERRORS_DIGEST = (
    "baf9f8bf969c920169d36cf5bd6b3300ac65a26f62320cef34057a471b291722"
)
RULES_DIGEST = (
    "92ea34ef53695f0ba83878763af3cabc5c9ae320d0a487a8c9e2749607f108db"
)

#: The LOW-2 reconciliation's own sentence: rule 2's third example now
#: carries the preceding statement rule 1 requires, so the quoted surface no
#: longer collides with the marker-without-a-statement rule.
IF_ANYTHING_FIXED_EXAMPLE = "we aren't late; if anything, we're a little early"

#: The old documents' fixture counts (188 / 67 / 124 = 379) and the new
#: documents' contribution (54 / 18 / 36 = 108); together 242 / 85 / 160 =
#: 487.
OLD_FIXTURE_TOTALS = {
    "NEGATIVE": 188,
    "FALSE_POSITIVE_BOUNDARY": 67,
    "POSITIVE_ERROR": 124,
}
NEW_FIXTURE_TOTALS = {
    "NEGATIVE": 54,
    "FALSE_POSITIVE_BOUNDARY": 18,
    "POSITIVE_ERROR": 36,
}


def _canon(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _digest(payload: object) -> str:
    return hashlib.sha256(_canon(payload)).hexdigest()


def _old_evidence_paths() -> list[Path]:
    """The 64 pre-existing evidence documents, in sorted id order (the
    documents that predate both this cut and C3-d)."""

    news = set(C3C_TARGETS) | set(C3D_TARGETS)
    paths = [
        path
        for path in sorted((CONTENT_SRC_DIR / "evidence").glob("res-*.json"))
        if path.stem not in news
    ]
    assert len(paths) == 64
    return paths


def _links_document() -> dict:
    return json.loads(
        (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
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
# ① the corpus truth at C3-c
# ---------------------------------------------------------------------------


def test_the_corpus_table_reads_34_r4_48_r1_and_5_none(
    built_content_db: Path,
) -> None:
    """The whole readiness table, read once at the post-C3-d truth: the
    fifty-two `res-*` targets whose §24.7 row is a curriculum mapping read
    R4, the forty-eight placements read R1_LEXICALLY_RESOLVED, and the five
    `cap-*` entities read None. This cut's eighteen rows were all mappings,
    and C3-d's eighteen joined them, so the R4 side is 16 + 18 + 18 and the
    R1 side is unchanged."""

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
    """The R4 set, id for id: the sixteen resources whose rows were mappings
    before this cut, plus this cut's eighteen, plus C3-d's eighteen — no
    target entered R4 by any other door and none left it."""

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
    assert r4 == sorted(
        set(PRIOR_R4) | set(C3C_TARGETS) | set(C3D_TARGETS)
    )
    assert len(PRIOR_R4) == 16
    assert set(PRIOR_R4).isdisjoint(C3C_TARGETS)
    assert set(C3C_TARGETS).isdisjoint(C3D_TARGETS)


def test_resource_count_reads_100_of_105_entities(
    built_content_db: Path,
) -> None:
    """The volume counter and the entity table: 100 `res-*` resources of 105
    entities — the IP §13 28→100 ladder's rung, topped by C3-d."""

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
    assert set(C3C_TARGETS) <= set(resources)


def test_the_three_calibration100_floors_read_separately(
    built_content_db: Path,
) -> None:
    """The three floors, each on its own line — the cut's honesty face.

    At this cut's own truth the reading was CORE_A 24 < 30 (**unmet**, eleven
    points short), CORE_C 10 >= 2 (met), resource_count 82 < 100 (unmet,
    eighteen short). C3-d's eighteen mappings carried all three over: CORE_A
    32 >= 30 (met), CORE_C 20 >= 2 (met), resource_count 100 >= 100 (met) —
    three assertions with three directions, three printed readings, and no
    single "gate passed" sentence. **Zero opening claim**: the floors meeting
    is the volume gate's answer, not the rollout's. The floor numbers come
    from the frozen plan text, not from a second hand-typed copy.
    """

    plan_text = _PLAN.read_text(encoding="utf-8")
    gates = {
        name: int(re.search(rf"{re.escape(name)} >= (\d+)", plan_text).group(1))
        for name in ("resource_count", "CORE_A", "CORE_C")
    }
    assert gates == _CALIBRATION100_FLOORS

    core_a, core_c = _core_counts(built_content_db)
    print(
        f"[c3c] CORE_A = {core_a} (floor {gates['CORE_A']},"
        f" {'met' if core_a >= gates['CORE_A'] else 'unmet'})"
    )
    print(
        f"[c3c] CORE_C = {core_c} (floor {gates['CORE_C']},"
        f" {'met' if core_c >= gates['CORE_C'] else 'unmet'})"
    )
    print(
        f"[c3c] resource_count = 100 (floor {gates['resource_count']},"
        f" {'met' if 100 >= gates['resource_count'] else 'unmet'})"
    )
    assert core_a >= gates["CORE_A"]  # CORE_A met (32 of 30, was 24 here)
    assert core_c >= gates["CORE_C"]  # CORE_C met
    assert 100 >= gates["resource_count"]  # volume floor met (topped)
    assert core_a + core_c == 52  # the CORE cells count the mapping set


def test_core_a_counts_the_eleven_survivors_plus_the_thirteen_new_highs(
    built_content_db: Path,
) -> None:
    """CORE_A = R3+ level ∧ core_utility HIGH. At C3-R1's truth the reading
    answered 11; this cut's thirteen HIGH targets are all mappings by their
    own rows, so all thirteen read R4 and count — the reading answered 24 at
    this cut's own truth, and C3-d's eight HIGH mappings carried it to 32.
    The band half is load-bearing (a HIGH demoted to MEDIUM leaves the cell;
    the variants in test_c3b hold that door, and the digest pins here hold
    the authored bands against silent edits)."""

    levels, utilities = _levels_and_utilities(built_content_db)
    core_a, core_c = _core_counts(built_content_db)
    assert core_a == 32
    assert core_a >= 30  # met again (C3-d's eight HIGH mappings)
    assert len(C3C_HIGH_TARGETS) == 13
    for target in C3C_HIGH_TARGETS:
        assert utilities[target] == "HIGH", target
        assert levels[target] == "R4_DETECTION_READY", target
    kept = [t for t in C3C_HIGH_TARGETS if levels[t] == "R4_DETECTION_READY"]
    assert len(kept) == 13


def test_core_c_counts_the_five_survivors_plus_the_five_new_mediums(
    built_content_db: Path,
) -> None:
    """CORE_C = R3+ level ∧ core_utility MEDIUM/LOW. At C3-R1's truth the
    reading answered 5; this cut's five MEDIUM targets are all mappings, so
    the reading answered 10 here, and C3-d's ten MEDIUM mappings carry it to
    20. The corpus's LOW arm is still C3-a's
    `res-pragmatic-could-i-ask`; neither cut authored a LOW band.

    声明读法 + Revisit（用户 2026-09-26 裁决），与 CORE_A 同一条读法。
    """

    levels, utilities = _levels_and_utilities(built_content_db)
    core_a, core_c = _core_counts(built_content_db)
    assert core_c == 20
    assert core_c >= 2
    assert len(C3C_MEDIUM_TARGETS) == 5
    for target in C3C_MEDIUM_TARGETS:
        assert utilities[target] == "MEDIUM", target
        assert levels[target] == "R4_DETECTION_READY", target
    assert utilities["res-pragmatic-could-i-ask"] == "LOW"
    assert core_a + core_c == 52


# ---------------------------------------------------------------------------
# ② the content gate stays GO over the widened table
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


def test_the_two_records_raise_their_slices_and_the_third_widens_them(
    built_content_db: Path,
) -> None:
    """The provenance read after C3-d's disposition landed the third audit
    record: 100 rows, 46 EDITOR_REVIEWED — the C3-R2 record's fifteen and
    the C3-c record's fifteen still exactly their own slices, joined by the
    C3-d record's sixteen (twelve sampled C3-d entities plus this cut's
    four re-audited leftovers: that-makes-sense, could-you-say-that-again,
    got-it, with-all-due-respect, all now EDITOR_REVIEWED) — and 54
    AUTHOR_DECLARED."""

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
    audit1 = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    audit2 = json.loads(AUDIT2_PATH.read_text(encoding="utf-8"))
    audit3 = json.loads(AUDIT3_PATH.read_text(encoding="utf-8"))
    approved1 = set(audit1["approved_entities"])
    approved2 = set(audit2["approved_entities"])
    approved3 = set(audit3["approved_entities"])
    assert approved1 | approved2 | approved3 == set(editor)
    assert approved1 & approved2 == set()
    assert approved1 & approved3 == set()
    assert approved2 & approved3 == set()
    assert approved2 == set(C3C_AUDITED_PASS)
    unsampled_c3c = set(C3C_TARGETS) - set(C3C_AUDITED_PASS)
    assert unsampled_c3c < approved3
    higher = [
        (e, lvl)
        for e, lvl in levels.items()
        if lvl in ("EXECUTABLY_VERIFIED", "EMPIRICALLY_CALIBRATED")
    ]
    assert higher == []


def test_the_four_unsampled_new_entities_rose_via_the_c3d_record(
    built_content_db: Path,
) -> None:
    """The new-template provenance obligation, as it stands after the
    disposition cut: the four new entities the review's stratified audit
    deliberately left out of its formal sample stayed AUTHOR_DECLARED until
    the C3-d review re-audited them — that disposition's record (#3) is what
    promotes them — while the fourteen sampled new entities plus
    res-softener-if-anything rose to EDITOR_REVIEWED through this cut's own
    disposition-cut record alone (provenance is never promoted by hand;
    structure decides it, and the audits directory is scanned by the
    build)."""

    store = ContentStore(built_content_db)
    try:
        rows = store.provenance_levels()
        assert isinstance(rows, Ok), rows
    finally:
        store.close()
    levels = dict(rows.value)
    unsampled = set(C3C_TARGETS) - set(C3C_AUDITED_PASS)
    assert len(unsampled) == 4
    for target in unsampled:
        assert levels[target] == "EDITOR_REVIEWED", target
    for target in C3C_AUDITED_PASS:
        assert levels[target] == "EDITOR_REVIEWED", target
    audit_files = sorted((CONTENT_SRC_DIR / "audits").glob("*.json"))
    assert [p.name for p in audit_files] == [
        "c3c-stratified-audit.json",
        "c3d-stratified-audit.json",
        "c3r2-stratified-audit.json",
    ]
    audit3 = json.loads(AUDIT3_PATH.read_text(encoding="utf-8"))
    assert unsampled <= set(audit3["approved_entities"])
    for path in (AUDIT_PATH, AUDIT2_PATH):
        audit = json.loads(path.read_text(encoding="utf-8"))
        assert set(audit["approved_entities"]) & unsampled == set()


def test_provenance_stays_an_independent_dimension_outside_the_ladder(
    built_content_db: Path,
) -> None:
    """The ladder does not know provenance: no fact key names it, the
    provenance words appear nowhere in the ladder's vocabulary, and the
    nineteen-key set is exactly what §8.1 requires — provenance widens
    nothing and blocks nothing. (The audited set spans both link classes, so
    no level is implied by any provenance word — that independence is the
    point.)"""

    for key in READINESS_FACT_KEYS:
        assert "provenance" not in key, key
        assert "EDITOR" not in key, key
    assert len(READINESS_FACT_KEYS) == 19
    store = ContentStore(built_content_db)
    try:
        rows = store.provenance_levels()
        assert isinstance(rows, Ok), rows
    finally:
        store.close()
    audited = {e for e, lvl in rows.value if lvl == "EDITOR_REVIEWED"}
    assert all(entity.startswith("res-") for entity in audited)
    assert len(audited) == 46


# ---------------------------------------------------------------------------
# ④ the eighteen new targets, one by one (new template obligations)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_id", C3C_TARGETS)
def test_each_new_target_carries_nineteen_keys_reads_r4_and_covers_its_errors(
    built_content_db: Path, target_id: str
) -> None:
    """Per new target, the whole new template at once: every §8.1 fact key
    present (including `curriculum_link` — this cut's rows are mappings),
    the level reads R4_DETECTION_READY, the document declares exactly two
    error types with one POSITIVE_ERROR fixture per type, the rule ordinals
    stay dense with the bounded fixtures and the positives append after
    them, all three fixture kinds are present with kind and expected
    agreeing, and the boundary fixtures exist for every rule ordinal."""

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

    for target_id in C3C_TARGETS:
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
        assert "C3-c authoring declaration" in str(membership[0]["source"])


# ---------------------------------------------------------------------------
# ⑤ the untouched faces, blob for blob
# ---------------------------------------------------------------------------


def test_the_existing_64_link_rows_are_untouched_blob_for_blob() -> None:
    """The 64 rows this cut appended after are byte-identical through their
    canonical JSON: same ids in the same order, same digests — and the new
    eighteen are exactly the rows appended at the end (C3-d appended its own
    eighteen after them)."""

    rows = _links_document()["links"]
    assert len(rows) == 100
    first = rows[:64]
    assert tuple(str(row["resource_id"]) for row in first) == LINKS64_IDS
    assert _digest(first) == LINKS64_DIGEST
    appended = [str(row["resource_id"]) for row in rows[64:82]]
    # The eighteen new rows are exactly the appended tail (this cut appended
    # them in its own authoring order after the frozen 64).
    assert sorted(appended) == sorted(C3C_TARGETS)
    assert len(appended) == 18
    tail = [str(row["resource_id"]) for row in rows[82:]]
    assert sorted(tail) == sorted(C3D_TARGETS)
    assert len(tail) == 18


def test_the_existing_fixture_rows_are_untouched_blob_for_blob() -> None:
    """The 379 fixture rows of the 64 old documents digest to the frozen
    value and still count 188 / 67 / 124; the eighteen new documents
    contribute exactly 54 / 18 / 36, so the artifact total is 242 / 85 /
    160 = 487 and every old row is inside the digest.

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
    for target in C3C_TARGETS:
        document = json.loads(
            (CONTENT_SRC_DIR / "evidence" / f"{target}.json").read_text(
                encoding="utf-8"
            )
        )
        for row in document["detection_fixtures"]:
            new_totals[str(row["kind"])] += 1
    assert new_totals == NEW_FIXTURE_TOTALS


def test_the_existing_typical_error_rows_are_untouched_blob_for_blob() -> None:
    """The typical_errors arrays of the 64 old documents digest to the
    frozen value — this cut authored two errors per new target and touched
    no old one."""

    digest = hashlib.sha256()
    for path in _old_evidence_paths():
        document = json.loads(path.read_text(encoding="utf-8"))
        digest.update(_canon(document["typical_errors"]))
    assert digest.hexdigest() == TYPICAL_ERRORS_DIGEST


def test_the_if_anything_fix_is_the_only_detection_rules_change() -> None:
    """The detection rules of the 64 old documents, minus exactly one row —
    rule ordinal 2 of `res-softener-if-anything`, the LOW-2 reconciliation —
    digest to the frozen value. The reconciled rule now quotes its third
    example with the statement in front of it that rule 1 requires, so the
    quoted surface can no longer be one the rules both demand and forbid;
    the document's two POSITIVE_ERROR rows are inside the fixtures digest
    and stay covered by rules 0 and 1, which the digest pins unchanged."""

    digest = hashlib.sha256()
    fixed_seen = False
    for path in _old_evidence_paths():
        document = json.loads(path.read_text(encoding="utf-8"))
        rules = document["detection_rules"]
        if path.stem == "res-softener-if-anything":
            kept = [row for row in rules if int(row["ordinal"]) != 2]
            rule2 = next(
                row for row in rules if int(row["ordinal"]) == 2
            )
            assert IF_ANYTHING_FIXED_EXAMPLE in str(rule2["rule"])
            assert "statement" in str(rule2["rule"])
            fixed_seen = True
        else:
            kept = rules
        digest.update(_canon(kept))
    assert fixed_seen
    assert digest.hexdigest() == RULES_DIGEST


# ---------------------------------------------------------------------------
# ⑥ the credit face: 15 → 33, node by node
# ---------------------------------------------------------------------------


def test_the_credit_face_widens_from_15_to_33_and_the_prior_nodes_stand(
    built_content_db: Path,
) -> None:
    """The credit read keys on REALIZES rows: the corpus carried 33 after
    this cut — the fifteen prior rows crediting exactly the node they
    credited before it (or none, for the one SUPPORTS+MAPPING row) and the
    eighteen new rows crediting the node their own row names — and C3-d's
    eighteen rows widen the face to 51. The live risk R-C1-credit's
    registered face widens with them, and its Revisit does not move."""

    rows = _links_document()["links"]
    realizes = {
        str(row["resource_id"]): str(row["node_id"])
        for row in rows
        if row["relation"] == "REALIZES"
    }
    assert len(realizes) == 51
    assert set(C3C_TARGETS) <= set(realizes)

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
    for target, node in PRIOR_CREDIT.items():
        if node is None:
            assert target not in credited, target
        else:
            assert credited[target] == node, target
    for target in C3C_TARGETS:
        assert credited[target] == C3C_NODE_OF[target], target


def test_every_new_link_adjudicates_against_its_capability_definition() -> None:
    """Every new row is a REALIZES + CURRICULUM_MAPPING + approved row with a
    null strength and the true primary flag, and its rationale is written in
    the adjudication genre: it names the node and that node's functional-
    definition file, cites `counts_as_realization` as the criterion it was
    judged by, states its credit consequence in its own words, states its
    provenance (C3-c, no authoring fixture) and registers its Revisit."""

    rows = _links_document()["links"]
    new_rows = {
        str(row["resource_id"]): row
        for row in rows
        if str(row["resource_id"]) in set(C3C_TARGETS)
    }
    assert sorted(new_rows) == sorted(C3C_TARGETS)
    for target_id, row in new_rows.items():
        assert row["relation"] == "REALIZES", target_id
        assert row["mapping_class"] == "CURRICULUM_MAPPING", target_id
        assert row["editorial_status"] == "CANONICAL_APPROVED", target_id
        assert row["strength"] is None, target_id
        assert row["primary_flag"] is True, target_id
        node = str(row["node_id"])
        assert node == C3C_NODE_OF[target_id], target_id
        rationale = str(row["rationale"])
        assert node in rationale, target_id
        assert f"curriculum/capabilities/{node}.json" in rationale, target_id
        assert "CURRICULUM_MAPPING" in rationale, target_id
        assert "counts_as_realization" in rationale, target_id
        assert "credit face" in rationale, target_id
        assert "C3-c (Phase 11)" in rationale, target_id
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
            if row["resource_id"] == "res-pragmatic-got-it":
                assert row["relation"] == "REALIZES"
                row["mapping_class"] = "COVERAGE_PLACEMENT"

    with pytest.raises(BuildError, match="REALIZES"):
        build_variant_artifact(tmp_path, curriculum_edit=rewrite)


# ---------------------------------------------------------------------------
# ⑦ determinism on the widened corpus
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
    this process's build (the C1 disposition F4 pin, re-read at C3-c's
    size — three builds, three seeds, one digest)."""

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
# ⑧ the version stays, the index lists both trees in order, nothing opens
# ---------------------------------------------------------------------------


def test_content_db_version_stays_until_d1(built_content_db: Path) -> None:
    """No schema change of this cut's own: the module constant and the built
    artifact moved "4" → "5" when D-1 later added the nullable
    ``content_detection_fixture.source_error_type`` column, and read the
    same generation."""

    assert CONTENT_DB_VERSION == "5"
    conn = sqlite3.connect(str(built_content_db))
    try:
        row = conn.execute(
            "SELECT value FROM content_meta WHERE key = 'content_db_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == CONTENT_DB_VERSION == "5"


def test_the_index_lists_105_and_100_documents_in_sorted_order() -> None:
    """The index grew in both lists: entity documents 69 → 87 → 105, evidence
    documents 64 → 82 → 100, both plain id order, and the eighteen new ids
    appear in each list exactly once."""

    index = json.loads(
        (CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8")
    )
    entities = [str(entry) for entry in index["entities"]]
    evidence = [str(entry) for entry in index["evidence"]]
    assert len(entities) == 105
    assert len(evidence) == 100
    assert entities == sorted(entities)
    assert evidence == sorted(evidence)
    for target_id in C3C_TARGETS:
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
    (content_src / "entities" / "res-pragmatic-got-it.json").unlink()
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
        _evidence_variant(tmp_path, "res-pragmatic-got-it", inject)


def test_deleting_a_positive_fixture_from_a_new_document_is_refused(
    tmp_path: Path,
) -> None:
    """The per-error_type coverage check is build-level and load-bearing for
    the new documents: dropping one POSITIVE_ERROR row from a two-type
    document leaves one type uncovered and the build refuses."""

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
        _evidence_variant(tmp_path, "res-pragmatic-got-it", drop)


def test_no_opening_claim_is_made_by_this_cut() -> None:
    """The stage leg is the only door and this cut did not touch it: the
    undeclared stage still refuses, and the authoring tree carries no stage
    declaration."""

    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(CONTENT_SRC_DIR.rglob("*.json"))
    ) + (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    assert "rollout_stage" not in blob
    assert "ROLLOUT" not in blob
