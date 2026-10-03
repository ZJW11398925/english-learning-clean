"""Queue-3 core-expression thickening (2026-10, DEC-OPI-32409938-3ba8-
4d3a-b988-b4942c57f69a.1): the 30 core targets' scenario variants.

What this file pins (VAL-OPI-32409938-3ba8-4d3a-b988-b4942c57f69a.3):

- **the roster, id by id**: the thirty targets the cut thickened are
  exactly the top thirty ``core_utility = HIGH`` resources under the
  cut's declared pre-selection order (transfer/productive/receptive
  HIGH-first, then productive_difficulty, then explanation_cost, both
  ascending, then the id — the order the ruling's R2 names
  "pedagogical_profile order"; the pin compares **sets**, the roster
  constant's own order is the published reading order);
- **four variants each, real-context differentiated**: every roster
  target's evidence carries ``usage`` rows at ordinals 2–5 (``en``,
  right sense), each aligned with the ``content_resource_label`` row of
  the **same ordinal**; the four label tuples are pairwise distinct and
  disjoint from the target's own baseline pair (ordinal 0/1) — that
  disjointness is what "distinct real context" means in machine terms
  here; the four sentences are pairwise distinct and none of them is
  the ordinal-0 usage row (not same-sentence rewrites);
- **zero migration**: the table set and ``CONTENT_DB_VERSION`` are
  untouched, the six-word §24.3 role list is untouched (the variants
  ride the existing ``usage`` role at fresh ordinals), and the corpus
  still builds deterministically across processes;
- **the detection face stays silent**: the 16 roster targets that sit
  in the D-3 pilot registry answer NO_MATCH on every one of their
  variant sentences — correct-use sentences are not learner errors —
  and no fixture row was added or changed to buy that (the provenance
  distribution is untouched: 54 AUTHOR_DECLARED / 10 EDITOR_REVIEWED /
  36 EXECUTABLY_VERIFIED on the pilot build);
- **the read face**: the word card's ``usage_variants`` key exposes the
  variant rows with their aligned context/genre words, and a target
  without variants reads an empty list;
- **the truth migration, executable**: the default artifact's digest
  moved (re-derived in tests/detection/test_d_expansion.py) and the
  mutation group below proves the face pin is load-bearing — deleting a
  variant row, deleting its aligned label row, or colliding a label
  tuple into the baseline each turns the face red.

Zero opening claim: this cut thickens the content's per-expression
depth; the rollout stage leg is untouched and still refuses.
"""

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
    build_content_db,
)
from elc.detection.pilot import PILOT_ENTITIES, register_pilot
from elc.detection.registry import DetectorRegistry
from elc.web import _word_lookup
from tests.detection.support import provenance_map
from tests.phase5.conftest import REPO_ROOT

#: The thirty roster targets, in the published reading order (the cut's
#: own pre-selection order; the pin compares sets against the re-derived
#: sort, so this constant's order is presentation, not the pin).
QUEUE3_TARGETS = (
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-what-do-you-mean",
    "res-pragmatic-what-was-that",
    "res-hedge-i-think",
    "res-pragmatic-i-see-your-point-but",
    "res-colloc-pay-attention-to",
    "res-phrasal-give-up",
    "res-phrasal-run-out-of",
    "res-colloc-take-a-look",
    "res-colloc-take-advantage-of",
    "res-frame-id-like-to",
    "res-frame-just-wondering",
    "res-hedge-it-seems-to-me",
    "res-phrasal-bring-up",
    "res-phrasal-figure-out",
    "res-phrasal-work-out",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-run-that-by-me-again",
    "res-pragmatic-thats-a-good-point-but",
    "res-colloc-have-an-effect-on",
    "res-discourse-before-i-forget",
    "res-hedge-as-far-as-i-know",
    "res-hedge-more-or-less",
    "res-pragmatic-right",
    "res-pragmatic-fair-enough",
    "res-pragmatic-got-it",
    "res-pragmatic-i-see",
    "res-pragmatic-that-makes-sense",
)

#: The variant ordinals (the ordinal-0 usage row is the baseline; the
#: baseline label pair sits at 0/1, so the variant block starts at 2 —
#: same-ordinal alignment, no offset).
VARIANT_ORDINALS = (2, 3, 4, 5)

#: The label tuple that must be pairwise distinct across a target's
#: variants and disjoint from its baseline pair.
_LABEL_KEYS = (
    "register",
    "usage_modality",
    "genre",
    "context",
    "domain",
    "variety",
)

#: The example-policy clause the cut appended to each roster target.
_POLICY_CLAUSE = "scenario variants"

#: The full table set the artifact must still carry (zero migration).
EXPECTED_TABLES = frozenset(
    {
        "content_assessment_membership",
        "content_detection_fixture",
        "content_detection_policy",
        "content_detection_rule",
        "content_entity",
        "content_example",
        "content_example_policy",
        "content_expression",
        "content_form",
        "content_hint_rung",
        "content_lexical_entry",
        "content_meta",
        "content_pack_overlay",
        "content_pedagogical_profile",
        "content_provenance",
        "content_resource_label",
        "content_sense",
        "content_slot",
        "content_target",
        "content_teaching",
        "content_text",
        "content_typical_error",
        "content_verification_profile",
        "curriculum_capability",
        "curriculum_link",
        "curriculum_prerequisite",
    }
)


def _label_tuple(row: sqlite3.Row) -> tuple:
    return tuple(row[key] for key in _LABEL_KEYS)


def _variant_face_violations(conn: sqlite3.Connection) -> list[str]:
    """The scenario-variant face as one judgment: empty means the whole
    face holds (roster coverage, alignment, differentiation, closure).
    The mutation group calls this same function on variant artifacts, so
    a red here is the pin moving, not the test."""

    problems: list[str] = []
    for entity_id in QUEUE3_TARGETS:
        texts = {
            int(row["ordinal"]): row
            for row in conn.execute(
                "SELECT ordinal, sense_id, language, text FROM content_text"
                " WHERE entity_id = ? AND role = 'usage' ORDER BY ordinal",
                (entity_id,),
            )
        }
        labels = {
            int(row["ordinal"]): row
            for row in conn.execute(
                "SELECT * FROM content_resource_label WHERE entity_id = ?"
                " ORDER BY ordinal",
                (entity_id,),
            )
        }
        if 0 not in texts:
            problems.append(f"{entity_id}: baseline usage row 0 missing")
            continue
        for ordinal in VARIANT_ORDINALS:
            if ordinal not in texts:
                problems.append(
                    f"{entity_id}: variant ordinal {ordinal} missing"
                )
                continue
            if ordinal not in labels:
                problems.append(
                    f"{entity_id}: label row {ordinal} (aligned) missing"
                )
            row = texts[ordinal]
            if str(row["language"]) != "en":
                problems.append(f"{entity_id}: variant {ordinal} not en")
            if str(row["sense_id"]) != texts[0]["sense_id"]:
                problems.append(f"{entity_id}: variant {ordinal} wrong sense")
        variant_tuples = {
            _label_tuple(labels[o]) for o in VARIANT_ORDINALS if o in labels
        }
        if len(variant_tuples) != len(VARIANT_ORDINALS) and all(
            o in labels for o in VARIANT_ORDINALS
        ):
            problems.append(f"{entity_id}: label tuples not pairwise distinct")
        baseline_tuples = {_label_tuple(labels[o]) for o in (0, 1) if o in labels}
        if variant_tuples & baseline_tuples:
            problems.append(f"{entity_id}: label tuple collides with baseline")
        variant_texts = [str(texts[o]["text"]) for o in VARIANT_ORDINALS if o in texts]
        if len(set(variant_texts)) != len(variant_texts):
            problems.append(f"{entity_id}: variant sentences not distinct")
        if str(texts[0]["text"]) in variant_texts:
            problems.append(f"{entity_id}: a variant is the ordinal-0 row")
    outside = conn.execute(
        "SELECT COUNT(*) FROM content_text WHERE role = 'usage'"
        " AND ordinal >= 2 AND entity_id NOT IN ("
        + ",".join("?" * len(QUEUE3_TARGETS))
        + ")",
        QUEUE3_TARGETS,
    ).fetchone()[0]
    if outside:
        problems.append(f"{outside} variant rows outside the roster")
    total = conn.execute(
        "SELECT COUNT(*) FROM content_text WHERE role = 'usage'"
        " AND ordinal >= 2"
    ).fetchone()[0]
    if total != len(QUEUE3_TARGETS) * len(VARIANT_ORDINALS):
        problems.append(f"variant row total {total}, expected 120")
    return problems


# ---------------------------------------------------------------------------
# group 1 — the roster and the variant discipline
# ---------------------------------------------------------------------------


def test_the_roster_is_the_top_thirty_high_targets(
    built_content_db: Path,
) -> None:
    """R2's pre-selection order, re-derived: among ``core_utility = HIGH``
    resources that carry an approved curriculum mapping (the R4 teachable
    half — the queue-3 disposal cut narrowed the roster to teachable
    targets, dropping its two R1 survivors), order by
    transfer/productive/receptive (HIGH first), then
    productive_difficulty, then explanation_cost (both ascending), then
    the id — and the cut took the first thirty. Set equality, so the pin
    survives a tie's presentation order."""

    conn = sqlite3.connect(str(built_content_db))
    conn.row_factory = sqlite3.Row
    try:
        candidates = conn.execute(
            "SELECT l.entity_id, p.transfer_value, p.productive_value,"
            " p.receptive_value, p.productive_difficulty, p.explanation_cost"
            " FROM content_pedagogical_profile p"
            " JOIN content_lexical_entry l USING (entity_id)"
            " WHERE p.core_utility = 'HIGH' AND EXISTS ("
            " SELECT 1 FROM curriculum_link k"
            " WHERE k.resource_id = l.entity_id"
            " AND k.editorial_status = 'CANONICAL_APPROVED'"
            " AND k.mapping_class = 'CURRICULUM_MAPPING')"
        ).fetchall()
    finally:
        conn.close()
    ordered = sorted(
        (str(row["entity_id"]), row) for row in candidates
    )
    ranked = [
        entity
        for entity, row in sorted(
            ordered,
            key=lambda item: (
                item[1]["transfer_value"] != "HIGH",
                item[1]["productive_value"] != "HIGH",
                item[1]["receptive_value"] != "HIGH",
                item[1]["productive_difficulty"],
                item[1]["explanation_cost"],
                item[0],
            ),
        )
    ]
    assert set(ranked[:30]) == set(QUEUE3_TARGETS)
    assert len(QUEUE3_TARGETS) == 30


def test_the_variant_face_holds_on_the_canonical_artifact(
    built_content_db: Path,
) -> None:
    """The whole face as one judgment on the real artifact: coverage,
    alignment, differentiation, closure — the mutation group's baseline."""

    conn = sqlite3.connect(str(built_content_db))
    conn.row_factory = sqlite3.Row
    try:
        assert _variant_face_violations(conn) == []
    finally:
        conn.close()


def test_every_roster_policy_declares_the_variant_role(
    built_content_db: Path,
) -> None:
    """R1's policy clause, migrated: each roster target's example_policy
    names the scenario variants and their budget independence, and the
    policy_version stayed at v1 (a clarification of the existing policy,
    not a new one)."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        for entity_id in QUEUE3_TARGETS:
            policy = conn.execute(
                "SELECT policy_version, policy FROM content_example_policy"
                " WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
            assert policy is not None, entity_id
            assert policy[0] == "example-policy-v1", entity_id
            assert _POLICY_CLAUSE in str(policy[1]), entity_id
            assert "two-example-per-attempt budget" in str(policy[1]), entity_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# group 2 — zero migration
# ---------------------------------------------------------------------------


def test_the_table_set_and_version_are_untouched(
    built_content_db: Path,
) -> None:
    conn = sqlite3.connect(str(built_content_db))
    try:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        conn.close()
    assert tables == EXPECTED_TABLES
    assert CONTENT_DB_VERSION == "6"


def test_the_role_vocabulary_is_untouched(built_content_db: Path) -> None:
    """The variants ride the existing ``usage`` role at fresh ordinals —
    the six-word §24.3 list gained no word and no row uses one."""

    from elc.content.types import CONTENT_TEXT_ROLES

    assert CONTENT_TEXT_ROLES == (
        "gloss",
        "definition",
        "translation",
        "usage",
        "teaching_note",
        "disambiguation",
    )
    conn = sqlite3.connect(str(built_content_db))
    try:
        roles = {
            str(row[0])
            for row in conn.execute("SELECT DISTINCT role FROM content_text")
        }
    finally:
        conn.close()
    assert roles <= set(CONTENT_TEXT_ROLES)


def test_the_corpus_builds_deterministically_across_processes(
    tmp_path: Path,
) -> None:
    """Two independent interpreter processes, two hash seeds, one byte
    stream: the variant rows ride the build's own sort key like every
    other row."""

    digests = []
    for index, seed in enumerate(("1", "2")):
        out = tmp_path / f"det-{index}.db"
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from elc.content.build import build_content_db;"
                f" build_content_db({str(out)!r})",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
    assert digests[0] == digests[1]


# ---------------------------------------------------------------------------
# group 3 — the detection face stays silent
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pilot_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    register_pilot(registry)
    return registry


def test_the_pilot_matchers_stay_silent_on_every_variant_sentence(
    built_content_db: Path,
    pilot_registry: DetectorRegistry,
) -> None:
    """VAL ③'s confirm-no-trigger arm: the roster targets that sit in the
    D-3 pilot registry (16 of the 30) answer NO_MATCH on all their
    variant sentences — a correct-use model sentence is not a learner
    error, and no BOUNDARY fixture was spent buying that."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        variant_rows = conn.execute(
            "SELECT entity_id, ordinal, text FROM content_text"
            " WHERE role = 'usage' AND ordinal >= 2 ORDER BY entity_id, ordinal"
        ).fetchall()
    finally:
        conn.close()
    roster = set(QUEUE3_TARGETS)
    pilot = set(PILOT_ENTITIES)
    probed = 0
    for entity_id, _ordinal, text in variant_rows:
        entity_id = str(entity_id)
        if entity_id not in roster & pilot:
            continue
        matcher = pilot_registry.resolve(entity_id)
        assert matcher is not None, entity_id
        assert matcher(str(text)) is None, (entity_id, str(text))
        probed += 1
    assert probed == 64


def test_the_provenance_distribution_is_untouched(tmp_path: Path) -> None:
    """No fixture row was added or changed: the pilot build still answers
    54 AUTHOR_DECLARED / 10 EDITOR_REVIEWED / 36 EXECUTABLY_VERIFIED /
    0 EMPIRICALLY_CALIBRATED, exactly as the queue-1 disposal left it."""

    out = tmp_path / "pilot.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    from elc.content.build import build_content_db

    build_content_db(out, detector_registry=registry)
    levels = list(provenance_map(out).values())
    assert levels.count("AUTHOR_DECLARED") == 54
    assert levels.count("EDITOR_REVIEWED") == 10
    assert levels.count("EXECUTABLY_VERIFIED") == 36
    assert levels.count("EMPIRICALLY_CALIBRATED") == 0


# ---------------------------------------------------------------------------
# group 4 — the read face
# ---------------------------------------------------------------------------


def test_the_word_card_reads_the_variant_face(
    built_content_db: Path,
) -> None:
    """The minimal read exposure: a roster target's card carries its four
    variant rows with the aligned context/genre words; a target outside
    the roster reads an empty list and the page renders nothing."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        dense = _word_lookup(conn, "got it")
        plain = _word_lookup(conn, "make a decision")
    finally:
        conn.close()
    assert dense["found"] is True
    assert dense["entity_id"] == "res-pragmatic-got-it"
    variants = dense["usage_variants"]
    assert [v["text"] for v in variants] == [
        "Got it — the report goes to both inboxes, and I'll copy the auditor.",
        "Got it. One flat white and a croissant — that's table twelve.",
        "Got it — we meet at the north gate at nine, not the ticket office.",
        "Got it, I'll move the dentist call to Thursday afternoon.",
    ]
    assert variants[0]["genre"] == "PROFESSIONAL_DISCOURSE"
    assert variants[0]["context"] == "SOCIAL_INTERACTION"
    assert plain["found"] is True
    assert plain["entity_id"] == "res-colloc-make-a-decision"
    assert plain["usage_variants"] == []


# ---------------------------------------------------------------------------
# group 5 — the mutation group (the face pin is load-bearing)
# ---------------------------------------------------------------------------


def _violations_of(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return _variant_face_violations(conn)
    finally:
        conn.close()


#: The mutation edits operate on one roster document: the helper copies
#: both authoring trees into *tmp*, mutates the copy's evidence document,
#: and builds through the real build step — the canonical corpus is never
#: edited for a test (the conftest's own variant helper reads only the
#: entity documents, so the evidence-side mutation gets its own small
#: copy on the same shape).

_TARGET_ENTITY = "res-pragmatic-got-it"


def _edited_artifact(tmp_path: Path, mutate) -> Path:
    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    evidence_path = (
        content_src / "evidence" / f"{_TARGET_ENTITY}.json"
    )
    document = json.loads(evidence_path.read_text(encoding="utf-8"))
    mutate(document)
    evidence_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


def _drop_usage_row(document: dict) -> None:
    document["texts"] = [
        row
        for row in document["texts"]
        if not (row["role"] == "usage" and row["ordinal"] == 3)
    ]


def _drop_label_row(document: dict) -> None:
    document["resource_labels"] = [
        row for row in document["resource_labels"] if row["ordinal"] != 3
    ]


def _collide_label_into_baseline(document: dict) -> None:
    labels = document["resource_labels"]
    baseline = next(row for row in labels if row["ordinal"] == 0)
    for row in labels:
        if row["ordinal"] == 3:
            for key in _LABEL_KEYS:
                row[key] = baseline[key]


def test_deleting_a_variant_row_turns_the_face_red(tmp_path: Path) -> None:
    artifact = _edited_artifact(tmp_path / "m1", _drop_usage_row)
    problems = _violations_of(artifact)
    assert any("variant ordinal 3 missing" in p for p in problems)
    assert any("variant row total" in p for p in problems)


def test_deleting_an_aligned_label_row_turns_the_face_red(
    tmp_path: Path,
) -> None:
    artifact = _edited_artifact(tmp_path / "m2", _drop_label_row)
    problems = _violations_of(artifact)
    assert any("label row 3 (aligned) missing" in p for p in problems)


def test_a_label_collision_into_the_baseline_turns_the_face_red(
    tmp_path: Path,
) -> None:
    artifact = _edited_artifact(
        tmp_path / "m3", _collide_label_into_baseline
    )
    problems = _violations_of(artifact)
    assert any("collides with baseline" in p for p in problems)
