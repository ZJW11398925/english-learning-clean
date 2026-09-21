"""P5-R / D1 — curriculum truth: an unreviewed mapping is not capability
evidence.

The blocker this file closes (external review, evidenced in
TASK-OPI-a68fd9eb-…22 / DEC-OPI-a68fd9eb-…15): `curriculum/links.json`
carried nine `REALIZES` rows marked ``CANONICAL_APPROVED`` whose own
rationale named the P3-1A/P3-1B test fixture as the only basis — so a
test-corpus convenience mapping could credit a CAPABILITY / POSITIVE claim
through the teaching leg's §5 ``ALTERNATIVE_SUCCESS`` fold
(elc.content.store._primary_realization_node → elc.runtime.controller.
_verified_capability_linkage → elc.learning.teaching_evidence).

What is pinned here, in order:

- the seed rows are honest: ``CURRICULUM_MAPPED`` (a §24.11 word, not an
  invented one), `primary_flag`/`strength` untouched, and the rationale
  states the P3-test-corpus basis, the missing curriculum-semantic review and
  the ban on capability evidence;
- the credit read is gated: an unapproved link keeps its row readable and
  answers ``None`` on the credit face (content.db read + provider view);
- the gate is a gate, not a deletion: an approved variant artifact is
  credited again;
- end to end: the named blocker pair — res-colloc-make-a-decision's
  alternative realization credited to cap-eval-hedged-opinion — now produces
  exactly one honest NEUTRAL claim on the resource and **zero** change on the
  capability (no claim, no durable state);
- the entity-level §24.11 lifecycle stays the author's (the fix is the link's
  editorial status, never the entity's).

Nothing here reads the P3 fixture supply: the corpus is the repository's own
artifact.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from elc.content.store import (
    CAPABILITY_CREDIT_EDITORIAL_STATUS,
    ContentStore,
)
from elc.content.types import LIFECYCLE_STATUSES
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.learning.controller import LearningController
from elc.platform.types import EvidenceModality, Ok, ResourceId, TargetId
from tests.phase5.conftest import (
    CURRICULUM_DIR,
    attempt,
    build_variant_artifact,
    open_moment,
    production_coordinator,
    reply_ok,
)

#: The blocker pair: a RESOURCE whose §24.7 link named
#: ``cap-eval-hedged-opinion`` on the strength of the P3 fixture alone.
DECISION = "res-colloc-make-a-decision"
DECISION_ALTERNATIVE = "We have to take a decision today."
HEDGED_OPINION = "cap-eval-hedged-opinion"
MODALITY = "TEXT_PRODUCTION"

SEED_LINKS = CURRICULUM_DIR / "links.json"

_CLAIM_COLUMNS = (
    "evidence_claim_id",
    "target_type",
    "target_id",
    "claim_role",
    "polarity",
    "outcome",
)


def _links_document() -> dict[str, Any]:
    return json.loads(SEED_LINKS.read_text(encoding="utf-8"))


def _claims(db: sqlite3.Connection) -> tuple[dict[str, object], ...]:
    rows = db.execute(
        f"SELECT {', '.join(_CLAIM_COLUMNS)} FROM evidence_claim"
    ).fetchall()
    return tuple(dict(zip(_CLAIM_COLUMNS, row)) for row in rows)


def _count(db: sqlite3.Connection, statement: str, params: tuple = ()) -> int:
    row = db.execute(statement, params).fetchone()
    assert row is not None
    return int(row[0])


def _capability_rows(db: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    """Every durable row that speaks about the capability: claims + §11 state.

    The "zero change" evidence is a row-set comparison, not an estimate
    reading: a capability with no rows before and no rows after has not
    moved, whatever a rebuild would compute.
    """

    claims = db.execute(
        "SELECT evidence_claim_id, target_type, target_id, polarity, outcome"
        " FROM evidence_claim WHERE target_id = ? ORDER BY evidence_claim_id",
        (HEDGED_OPINION,),
    ).fetchall()
    states = db.execute(
        "SELECT target_id, evidence_modality, evidence_watermark"
        " FROM learner_target_state WHERE target_id = ? ORDER BY target_id",
        (HEDGED_OPINION,),
    ).fetchall()
    return tuple(claims) + tuple(states)


# ---------------------------------------------------------------------------
# ① the seed rows tell the truth
# ---------------------------------------------------------------------------


def test_every_seed_link_is_curriculum_mapped_never_canonical_approved() -> None:
    """The nine rows are *mapped*, not *approved* — the §24.11 word for "the
    mapping exists", with the fields that describe the mapping untouched."""

    links = _links_document()["links"]
    assert len(links) == 9
    for row in links:
        assert row["editorial_status"] == "CURRICULUM_MAPPED", row
        assert row["editorial_status"] in LIFECYCLE_STATUSES, row
        assert row["editorial_status"] != "CANONICAL_APPROVED", row
        assert row["relation"] == "REALIZES", row
        assert row["primary_flag"] is True, row
        assert row["strength"] is None, row
    print(
        "[p5-r] seed links -> "
        f"{sorted({row['editorial_status'] for row in links})}"
        f" ({len(links)} rows)"
    )


@pytest.mark.parametrize("index", range(9))
def test_every_seed_rationale_states_its_basis_and_its_limit(index: int) -> None:
    """The rationale must carry all three facts: the P3 test-corpus basis,
    the missing curriculum-semantic review, and the ban on capability
    evidence until the capability has a functional definition and an author
    review."""

    row = _links_document()["links"][index]
    rationale = str(row["rationale"])
    assert "P3-1A/P3-1B test-corpus design" in rationale, rationale
    assert "no curriculum-semantic review" in rationale, rationale
    assert "must not count as capability evidence" in rationale, rationale
    assert "author review approves this link" in rationale, rationale
    # The rationale names the very node the row points at (no copy-paste
    # mismatch between the mapping and the sentence about it).
    assert str(row["node_id"]) in rationale, rationale


def test_the_entity_lifecycle_is_the_authors_and_was_not_touched(
    built_content_db,
) -> None:
    """The fix is the *link's* editorial status. Every §24.1 entity row is
    still ``CANONICAL_APPROVED`` — the §24.11 supply set is untouched by
    P5-R."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        for entity_id in store.entity_ids().value:
            resource = supply.get_resource(entity_id)
            assert isinstance(resource, Ok), resource
            assert resource.value.lifecycle_status == "CANONICAL_APPROVED"
        eligible = supply.supply_entity_ids()
        assert isinstance(eligible, Ok), eligible
        assert len(eligible.value) == 14
    finally:
        store.close()


# ---------------------------------------------------------------------------
# ② the credit read is gated (artifact + provider face)
# ---------------------------------------------------------------------------


def test_the_link_row_stays_readable_and_the_credit_face_reads_none(
    built_content_db,
) -> None:
    """Unapproved ≠ deleted: the §24.7 row and its rationale are still there,
    while the teaching payload's ``capability_linkage`` — the field the §5
    fold credits — answers ``None`` (the P5-R gate)."""

    store = ContentStore(built_content_db)
    try:
        links = store.curriculum_links_of(DECISION)
        assert isinstance(links, Ok), links
        assert len(links.value) == 1
        assert links.value[0].editorial_status == "CURRICULUM_MAPPED"
        assert links.value[0].node_id == HEDGED_OPINION
        assert links.value[0].rationale
        teaching = store.get_teaching_content(DECISION)
        assert isinstance(teaching, Ok), teaching
        assert teaching.value.capability_linkage is None
        # Every unaffected field of the payload is untouched by the gate.
        assert teaching.value.canonical_forms
        assert teaching.value.alternative_realizations
        assert teaching.value.required_slots
    finally:
        store.close()

    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        view = provider.resolve("RESOURCE", DECISION)
        assert isinstance(view, Ok), view
        assert view.value.capability_linkage is None
        assert view.value.target_status == "VALID"
    finally:
        provider.close()


def test_no_corpus_resource_credits_a_capability(built_content_db) -> None:
    """All nine linked resources read ``None`` on the credit face — the gate
    applies to the whole seed corpus, not to the one row the review named."""

    store = ContentStore(built_content_db)
    try:
        linked = 0
        for entity_id in store.entity_ids().value:
            links = store.curriculum_links_of(entity_id)
            assert isinstance(links, Ok), links
            if not links.value:
                continue
            linked += 1
            teaching = store.get_teaching_content(entity_id)
            assert isinstance(teaching, Ok), teaching
            assert teaching.value.capability_linkage is None, entity_id
        assert linked == 9
    finally:
        store.close()
    print(f"[p5-r] linked resources with no capability credit -> {linked}")


def test_the_gate_is_a_gate_not_a_deletion(tmp_path) -> None:
    """An *approved* variant artifact is credited again: the same read, the
    same code path, only the editorial status differs."""

    def approve(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == DECISION:
                row["editorial_status"] = "CANONICAL_APPROVED"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=approve)
    store = ContentStore(artifact)
    try:
        teaching = store.get_teaching_content(DECISION)
        assert isinstance(teaching, Ok), teaching
        assert teaching.value.capability_linkage == HEDGED_OPINION
        other = store.get_teaching_content("res-hedge-i-think")
        assert isinstance(other, Ok), other
        assert other.value.capability_linkage is None
    finally:
        store.close()
    assert CAPABILITY_CREDIT_EDITORIAL_STATUS == "CANONICAL_APPROVED"


# ---------------------------------------------------------------------------
# ③ end to end: the named blocker pair
# ---------------------------------------------------------------------------


def test_make_a_decision_alternative_success_credits_no_capability(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    """The evidenced blocker, run through the shipped chain: a moment on
    res-colloc-make-a-decision, an attempt that is its alternative
    realization → ``ALTERNATIVE_SUCCESS`` → exactly one honest NEUTRAL claim
    on the resource, and cap-eval-hedged-opinion's estimate and durable rows
    unchanged (before == after: nothing)."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
    )
    learning_controller = LearningController(learning)
    capability_before = _capability_rows(db)
    assert capability_before == (), "the before state is the chain's, not a seed"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0

    opened = open_moment(coordinator, "cm-p5r-credit-open", DECISION)
    assert opened.gate_decision == "ALLOW"
    assert opened.moment_id is not None
    reply = reply_ok(
        coordinator, attempt(DECISION_ALTERNATIVE), "cm-p5r-credit-attempt"
    )
    assert reply.evaluation_outcome == "ALTERNATIVE_SUCCESS"

    claims = _claims(db)
    rendered = [
        (c["target_id"], c["claim_role"], c["polarity"], c["outcome"])
        for c in claims
    ]
    print(f"[p5-r] alternative-success claims -> {rendered}")
    assert len(claims) == 1, "no capability claim may exist"
    claim = claims[0]
    assert claim["target_id"] == DECISION
    assert claim["target_type"] == "RESOURCE"
    assert claim["claim_role"] == "FOCUS_TARGET"
    assert claim["polarity"] == "NEUTRAL"
    assert claim["outcome"] == "ABSTAIN"

    # The capability's durable rows: zero before, zero after. The rebuild is
    # called explicitly so "no state" is the rebuild's answer too, not just
    # an untouched row.
    rebuilt = learning_controller.rebuild_learner_state(
        TargetId(HEDGED_OPINION), EvidenceModality(MODALITY)
    )
    assert isinstance(rebuilt, Ok), rebuilt
    assert _capability_rows(db) == capability_before == ()
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (HEDGED_OPINION,),
        )
        == 0
    )
    # The resource's own projection (the honest single claim) still moves.
    resource_rebuild = learning_controller.rebuild_learner_state(
        TargetId(DECISION), EvidenceModality(MODALITY)
    )
    assert isinstance(resource_rebuild, Ok), resource_rebuild
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (DECISION,),
        )
        == 1
    )
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (HEDGED_OPINION,),
        )
        == 0
    )


def test_the_credit_gate_is_the_only_thing_that_changed(
    built_content_db,
) -> None:
    """One-field proof for the receipt: the artifact's teaching payload is
    byte-for-byte what it was except ``capability_linkage`` — the §24.5 rows,
    the ladder and the slots are unchanged, so the fix did not smuggle a
    content edit in behind the gate."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        teaching = supply.get_teaching_content(DECISION)
        assert isinstance(teaching, Ok), teaching
        payload = teaching.value
        print(
            "[p5-r] payload -> "
            f"ladder={len(payload.hint_ladder)}"
            f" forms={payload.canonical_forms}"
            f" alts={payload.alternative_realizations}"
            f" slots={payload.required_slots}"
            f" linkage={payload.capability_linkage}"
        )
        assert payload.reveal_form == "We have to make a decision today."
        assert payload.canonical_forms == ("We have to make a decision today.",)
        assert payload.alternative_realizations == (
            "We have to take a decision today.",
        )
        assert payload.capability_linkage is None
        links = supply.curriculum_links_of(ResourceId(DECISION))
        assert isinstance(links, Ok), links
        assert [str(link.node_id) for link in links.value] == [HEDGED_OPINION]
    finally:
        store.close()
