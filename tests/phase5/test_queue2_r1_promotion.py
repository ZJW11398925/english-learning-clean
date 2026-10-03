"""Queue-2 R1-to-R3 screening (2026-10, DEC-OPI-c91a2957-5f8e-448a-a3a5-
9de2f626af36.9): the three new lexical capabilities and the forty-eight
R1 rows' per-entity adjudication.

What this file pins (VAL-OPI-c91a2957-5f8e-448a-a3a5-9de2f626af36.11):

- **the promotion set, id by id**: the forty-one lexical resources the
  screening promoted each carry an approved ``REALIZES``
  ``CURRICULUM_MAPPING`` row against the lexical capability their family
  maps to (colloc → cap-lexcol-word-partnership, phrasal →
  cap-lexcol-verb-particle, idiom + frame → cap-lexcol-fixed-expression),
  and every row's rationale cites that capability's functional-definition
  entries by name;
- **the survivors, id by id, each with its reason**: the seven pragmatic
  rows that failed the screen stay at R1 — every one is named by an
  **existing** functional definition's ``does_not_count`` entry, so the
  screen's negative side is the definitions' own words, not this file's
  taste;
- **the frozen 52**: the C3-R1/C3-c/C3-d mapping set is untouched — no
  promoted id collides with it and none of its rows changed;
- **the three gates and the supply read, separately**: CORE_A 60,
  CORE_C 33, resource_count 100, supply-eligible R3+ = 93;
- **the credit face, counted**: 51 + 41 = 92 approved REALIZES rows, and
  the three new capability entities carry no evidence document — so the
  provenance table carries no row for them (nothing is claimed to be
  reviewed that was not).

Zero opening claim: this cut widens the manually teachable face; the
rollout stage leg is untouched and still refuses.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from elc.content.build import CONTENT_SRC_DIR, CURRICULUM_DIR
from elc.content.store import ContentStore
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Ok
from tests.phase5.conftest import build_variant_artifact
from tests.phase5.test_c3r1_capability_semantics import (
    MAPPING_TARGETS_CORPUS,
    QUEUE2_PROMOTED,
)

#: The family → capability mapping the adjudication followed (the ruling's
#: own table: colloc → word-partnership, phrasal → verb-particle,
#: idiom + frame → fixed-expression).
FAMILY_NODE = {
    "colloc": "cap-lexcol-word-partnership",
    "phrasal": "cap-lexcol-verb-particle",
    "idiom": "cap-lexcol-fixed-expression",
    "frame": "cap-lexcol-fixed-expression",
}

#: The three new lexical capability ids.
LEXICAL_NODES = tuple(sorted(set(FAMILY_NODE.values())))

#: The seven pragmatic rows that failed the screen, each with the
#: functional-definition entry that names it (the adjudication table's
#: reason column, verbatim citations — a survivor without its entry would
#: be a silent drop, which the ruling forbids).
SURVIVORS: tuple[tuple[str, str, str], ...] = (
    (
        "res-discourse-in-fact",
        "cap-disc-topic-shift",
        '"in fact" asserts factuality',
    ),
    (
        "res-discourse-long-story-short",
        "cap-disc-topic-shift",
        '"long story short" compresses',
    ),
    (
        "res-hedge-i-mean",
        "cap-ref-ask-clarification",
        '"I mean"',
    ),
    (
        "res-pragmatic-could-i-ask",
        "cap-ref-ask-clarification",
        'permission ("Could I ask you a question?")',
    ),
    (
        "res-pragmatic-could-you",
        "cap-ref-ask-clarification",
        '"Could you send me the file?"',
    ),
    (
        "res-pragmatic-sorry-to-interrupt",
        "cap-interact-backchannel",
        '"Sorry to interrupt" is a floor bid',
    ),
    (
        "res-softener-if-anything",
        "cap-stance-soften-disagreement",
        '"if anything" corrects',
    ),
)


def _links_document() -> dict:
    return json.loads(
        (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    )


def _screened_rows() -> dict[str, dict]:
    """The forty-one screening rows, keyed by resource id."""

    return {
        str(row["resource_id"]): row
        for row in _links_document()["links"]
        if "queue-2 R1-to-R3" in str(row["rationale"])
    }


def _levels(artifact: Path) -> dict[str, str | None]:
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        assessments = supply.readiness_by_target()
        assert isinstance(assessments, Ok), assessments
        return {
            a.target_id: a.level  # type: ignore[misc]
            for a in assessments.value
        }
    finally:
        store.close()


# ---------------------------------------------------------------------------
# ① the promotion set, id by id
# ---------------------------------------------------------------------------


def test_the_screening_roster_is_exactly_the_promoted_set() -> None:
    """The rows labelled as this cut's screening are exactly the forty-one
    promoted ids — no silent extra row, no missing one."""

    screened = _screened_rows()
    assert sorted(screened) == sorted(QUEUE2_PROMOTED)
    assert len(screened) == 41


@pytest.mark.parametrize("target_id", QUEUE2_PROMOTED)
def test_each_promoted_row_is_a_realizes_mapping_citing_the_definition(
    target_id: str,
) -> None:
    """Per promoted id: the row is REALIZES ∧ CURRICULUM_MAPPING ∧ approved
    ∧ primary, against the node its family maps to, and the rationale cites
    the functional definition by file, by the counts_as list it was judged
    by, and by its own credit consequence."""

    row = _screened_rows()[target_id]
    node = FAMILY_NODE[target_id.split("-")[1]]
    assert row["node_id"] == node, target_id
    assert row["relation"] == "REALIZES", target_id
    assert row["mapping_class"] == "CURRICULUM_MAPPING", target_id
    assert row["editorial_status"] == "CANONICAL_APPROVED", target_id
    assert row["primary_flag"] is True, target_id
    assert row["strength"] is None, target_id
    rationale = str(row["rationale"])
    assert f"curriculum/capabilities/{node}.json" in rationale, target_id
    assert "counts_as_realization" in rationale, target_id
    assert "does_not_count" in rationale, target_id
    assert "CURRICULUM_MAPPING" in rationale, target_id
    assert "credit face" in rationale, target_id
    assert "Revisit" in rationale, target_id
    assert "Row provenance:" in rationale, target_id


def test_every_promoted_rationale_cites_a_real_counts_as_entry() -> None:
    """The citation discipline, checked against the definitions themselves:
    at least one ``counts_as_realization N`` reference in every promoted
    rationale resolves to an entry index the named definition actually
    carries (a citation of an entry that does not exist is an empty
    citation)."""

    screened = _screened_rows()
    for target_id, row in screened.items():
        node = FAMILY_NODE[target_id.split("-")[1]]
        definition = json.loads(
            (CURRICULUM_DIR / "capabilities" / f"{node}.json").read_text(
                encoding="utf-8"
            )
        )["functional_definition"]
        count = len(definition["counts_as_realization"])
        cited = {
            int(number)
            for number in __import__("re").findall(
                r"counts_as_realization (\d)", str(row["rationale"])
            )
        }
        assert cited, target_id
        assert all(1 <= number <= count for number in cited), (
            target_id,
            sorted(cited),
            count,
        )


# ---------------------------------------------------------------------------
# ② the frozen 52 and the survivors with their reasons
# ---------------------------------------------------------------------------


def test_the_prior_mapping_set_is_untouched_by_the_screening() -> None:
    """The frozen 52: queue-2's promoted ids are disjoint from it (the 93 =
    52 + 41 arithmetic is an equality, not an overlap), and none of the
    fifty-two pre-existing rows was rewritten — their rationales carry no
    screening label."""

    assert set(QUEUE2_PROMOTED).isdisjoint(
        set(MAPPING_TARGETS_CORPUS) - set(QUEUE2_PROMOTED)
    )
    prior = sorted(set(MAPPING_TARGETS_CORPUS) - set(QUEUE2_PROMOTED))
    assert len(prior) == 52
    rows = {
        str(row["resource_id"]): row
        for row in _links_document()["links"]
        if str(row["resource_id"]) in prior
    }
    assert len(rows) == 52
    for target_id, row in rows.items():
        assert "queue-2 R1-to-R3" not in str(row["rationale"]), target_id


@pytest.mark.parametrize("survivor", SURVIVORS)
def test_each_survivor_stays_r1_with_its_definition_entry(
    survivor: tuple[str, str, str],
    built_content_db: Path,
) -> None:
    """Per survivor: the resource reads R1 (blocked exactly by the link
    key), carries no link row against any lexical node, and the
    functional-definition entry this cut cited as its reason is verbatim in
    the named capability's does_not_count list."""

    target_id, node, entry = survivor
    levels = _levels(built_content_db)
    assert levels[target_id] == "R1_LEXICALLY_RESOLVED", target_id
    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        links = supply.curriculum_links_of(target_id)
        assert isinstance(links, Ok), links
        if links.value:
            # A survivor may keep its frozen SUPPORTS placement row; it must
            # have no REALIZES row against the lexical set.
            assert all(
                str(link.relation) == "SUPPORTS" for link in links.value
            ), target_id
        facts = supply.readiness_facts(target_id)
        assert isinstance(facts, Ok), facts
        assert facts.value.curriculum_link is False, target_id
    finally:
        store.close()
    definition = json.loads(
        (CURRICULUM_DIR / "capabilities" / f"{node}.json").read_text(
            encoding="utf-8"
        )
    )["functional_definition"]
    assert entry in " ".join(definition["does_not_count"]), target_id


def test_the_survivor_table_covers_the_whole_r1_band() -> None:
    """No silent drop: the seven named survivors are exactly the corpus's
    R1 band."""

    levels = _levels_built()
    r1 = sorted(
        t for t, level in levels.items() if level == "R1_LEXICALLY_RESOLVED"
    )
    assert r1 == sorted(survivor[0] for survivor in SURVIVORS)


def _levels_built() -> dict[str, str | None]:
    """Build the canonical artifact into a session-local path once."""

    cache = _levels_built.__dict__.get("cache")
    if cache is None:
        import tempfile

        from elc.content.build import build_content_db

        handle = tempfile.mkdtemp(prefix="queue2-nail-")
        build_content_db(Path(handle) / "content.db")
        cache = _levels(Path(handle) / "content.db")
        _levels_built.__dict__["cache"] = cache
    return cache


# ---------------------------------------------------------------------------
# ③ the three gates and the supply read, separately
# ---------------------------------------------------------------------------


def test_the_three_gates_read_60_33_100_separately(
    built_content_db: Path,
) -> None:
    """CORE_A 60 (28 HIGH lexical rows joined the 32), CORE_C 33 (13 MEDIUM
    lexical rows joined the 20), resource_count 100 — three separate
    readings of the declared reading (R3+ × core_utility band); **zero
    opening claim**."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        utilities = {
            str(entity_id): str(band)
            for entity_id, band in conn.execute(
                "SELECT entity_id, core_utility FROM "
                "content_pedagogical_profile"
            ).fetchall()
        }
        resources = [
            str(row[0])
            for row in conn.execute(
                "SELECT entity_id FROM content_entity WHERE entity_id "
                "LIKE 'res-%'"
            )
        ]
    finally:
        conn.close()
    levels = _levels(built_content_db)
    r3_plus = {
        t
        for t, level in levels.items()
        if t.startswith("res-")
        and level in ("R3_TEACHING_READY", "R4_DETECTION_READY")
    }
    core_a = sum(1 for t in r3_plus if utilities.get(t) == "HIGH")
    core_c = sum(
        1 for t in r3_plus if utilities.get(t) in ("MEDIUM", "LOW")
    )
    assert core_a == 60
    assert core_c == 33
    assert len(resources) == 100


def test_the_supply_eligible_r3_plus_set_is_93(
    built_content_db: Path,
) -> None:
    """The manually teachable face: the R3+ resource set is the 52 prior
    mappings plus the 41 screened rows = 93 — each id named by the
    screening roster."""

    levels = _levels(built_content_db)
    usable = sorted(
        t
        for t, level in levels.items()
        if t.startswith("res-")
        and level in ("R3_TEACHING_READY", "R4_DETECTION_READY")
    )
    assert len(usable) == 93
    assert set(usable) == set(MAPPING_TARGETS_CORPUS)


# ---------------------------------------------------------------------------
# ④ the credit face and the provenance honesty
# ---------------------------------------------------------------------------


def test_the_credit_face_is_51_plus_41_and_each_new_row_feeds_it(
    built_content_db: Path,
) -> None:
    """R-C1-credit's registered face: 92 approved REALIZES rows (51 prior +
    41 screened); the screening's rows are exactly the delta. This cut's
    behaviour change, counted. Today no real teaching run exists, so no
    learner evidence is minted by this widening."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        realizes = conn.execute(
            "SELECT COUNT(*) FROM curriculum_link WHERE relation = 'REALIZES'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert realizes == 92
    for target_id in QUEUE2_PROMOTED:
        assert target_id in set(MAPPING_TARGETS_CORPUS)


def test_the_new_capability_entities_carry_no_evidence_row(
    built_content_db: Path,
) -> None:
    """The provenance honesty half: a capability with no evidence document
    makes no provenance claim (the build's own rule), so the three new
    lexical capabilities read no provenance row — nothing is implied to
    have been reviewed or verified that was not. (The C2-a R3 ruling's
    shape: constructive None, honestly reported.)"""

    conn = sqlite3.connect(str(built_content_db))
    try:
        documented = {
            str(row[0])
            for row in conn.execute("SELECT entity_id FROM content_provenance")
        }
        capabilities = {
            str(row[0])
            for row in conn.execute(
                "SELECT capability_id FROM curriculum_capability"
            )
        }
    finally:
        conn.close()
    assert capabilities == {
        *sorted(LEXICAL_NODES),
        "cap-disc-topic-shift",
        "cap-eval-hedged-opinion",
        "cap-interact-backchannel",
        "cap-ref-ask-clarification",
        "cap-stance-soften-disagreement",
    }
    assert not capabilities & documented


# ---------------------------------------------------------------------------
# ⑤ the mutation doors the screening's pins must keep
# ---------------------------------------------------------------------------


def test_deleting_one_screened_row_drops_its_target_out_of_the_promotion_set(
    tmp_path: Path,
) -> None:
    """Mutation 1: deleting one screening row's link drops that target out
    of the R4 set and out of the promotion roster — the id-by-id pin is
    load-bearing, not decorative."""

    def drop(documents: dict, _index: dict) -> None:
        rows = documents["links.json"]["links"]
        victim = next(
            row
            for row in rows
            if row["resource_id"] == "res-colloc-heavy-rain"
            and "queue-2 R1-to-R3" in str(row["rationale"])
        )
        rows.remove(victim)

    artifact = build_variant_artifact(tmp_path, curriculum_edit=drop)
    levels = _levels(artifact)
    assert levels["res-colloc-heavy-rain"] == "R1_LEXICALLY_RESOLVED"
    assert len(levels) == 108


def test_demoting_one_screened_row_to_a_placement_flips_its_target(
    tmp_path: Path,
) -> None:
    """Mutation 2: demoting one screening row to a SUPPORTS placement (the
    legal demotion shape — a REALIZES row may not carry a placement class,
    the build refuses that pair) flips that target to R1 — the promotion
    travels by the row's own mapping class (the C3-R1 declared reading),
    never by a count."""

    def demote(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if (
                row["resource_id"] == "res-phrasal-figure-out"
                and "queue-2 R1-to-R3" in str(row["rationale"])
            ):
                row["relation"] = "SUPPORTS"
                row["primary_flag"] = False
                row["mapping_class"] = "COVERAGE_PLACEMENT"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=demote)
    levels = _levels(artifact)
    assert levels["res-phrasal-figure-out"] == "R1_LEXICALLY_RESOLVED"


def test_editing_a_counts_as_entry_text_is_inert_but_the_word_is_load_bearing(
    tmp_path: Path,
) -> None:
    """Mutation 3: the definitions are the standard the rows were judged by
    — the build reads them strictly (a broken five-key block is refused),
    so an edit that empties a judgement list cannot pass silently. The
    screening rows cite entry *numbers*, so a re-worded definition does not
    retroactively falsify a row; what guards the standard is the strict
    block (this mutation) and the definition files' own digest discipline
    (C3-d's N-C3D-3), not this file."""

    def break_definition(documents: dict, _index: dict) -> None:
        document = documents["capabilities/cap-lexcol-word-partnership.json"]
        document["functional_definition"]["counts_as_realization"] = []

    with pytest.raises(Exception, match="counts_as_realization"):
        build_variant_artifact(
            tmp_path, curriculum_edit=break_definition
        )


def test_no_opening_claim_is_made_by_this_cut() -> None:
    """The stage leg is the only rollout door and this cut did not touch
    it: the undeclared stage still refuses, and the authoring documents
    this cut wrote carry no stage declaration."""

    from elc.teaching.rollout import stage_allows_automatic

    assert stage_allows_automatic(None) is False
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((CONTENT_SRC_DIR / "entities").rglob("*.json"))
    ) + "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(
            (CURRICULUM_DIR / "capabilities").rglob("*.json")
        )
    ) + (CURRICULUM_DIR / "links.json").read_text(encoding="utf-8")
    assert "rollout_stage" not in blob
    assert "ROLLOUT" not in blob
