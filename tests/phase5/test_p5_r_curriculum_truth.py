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

What is pinned here, in order (written at P5-R's truth; C1, C2-a and C2-b each
moved the corpus forward, and each group states both):

- the rows are honest: all nine seed rows were ``CURRICULUM_MAPPED`` at P5-R;
  C1's editorial review approved one, C2-a's approved the other eight while
  authoring their readiness evidence, and C2-b authored and approved nineteen
  more while authoring its entities — so today all twenty-eight rows are
  ``CANONICAL_APPROVED``, each with a rationale that names the approval, what
  it covered and what it did not (curriculum/links.json). The seed rows'
  mapping fields (`relation`, `strength`, `primary_flag`, the two ids) are
  untouched by the approvals; the C2-b rows declare their own relation, and
  the 13 ``SUPPORTS`` rows carry ``primary_flag = false`` because the primary
  flag marks the primary **REALIZES** link (the only thing the build's
  at-most-one check counts);
- the credit read is gated by status *and* by relation: a *demoted* link keeps
  its row readable and answers ``None`` on the credit face — the canonical
  corpus now carries only approved rows, so the off-state is built as a
  variant — and an approved ``SUPPORTS`` row credits nothing (the read filters
  ``relation = REALIZES``), which is the second off-state the corpus itself
  now carries. Every approved ``REALIZES`` row credits its node;
- the gate is a gate, not a deletion: a demoted variant keeps the row and
  drops only the credit;
- end to end: res-colloc-make-a-decision's alternative realization now
  produces the CAPABILITY_LINKAGE POSITIVE/SUCCESS claim the approval
  admits **plus** the unchanged honest NEUTRAL/ABSTAIN claim on the
  resource (旧真值: one NEUTRAL claim, zero capability change);
- the entity-level §24.11 lifecycle stays the author's (the gate reads the
  link's editorial status, never the entity's).

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

#: The eight rows C2-a approved while authoring their readiness evidence
#: (C1's own row is DECISION above).
C2A_APPROVED = (
    "res-colloc-pay-attention-to",
    "res-discourse-by-the-way",
    "res-frame-id-like-to",
    "res-hedge-i-think",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
    "res-softener-kind-of",
)

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


def test_all_seed_links_are_approved_with_their_mapping_fields_untouched() -> None:
    """Old truth (P5-R): all nine rows were *mapped*, none *approved*. C1
    approved one row; C2-a approved the other eight while authoring their
    targets' readiness evidence; C2-b authored and approved nineteen more,
    so today all twenty-eight rows are ``CANONICAL_APPROVED`` — and the
    mapping-describing fields of the nine migrated rows (relation, strength,
    primary_flag, and the two ids) are exactly what the approvals were
    forbidden to touch, asserted row by row from the source document. The
    nineteen C2-b rows are held to the same field discipline: a ``REALIZES``
    row carries ``primary_flag = true``, a ``SUPPORTS`` row ``false``, and
    ``strength`` is null everywhere (no vocabulary is invented)."""

    links = _links_document()["links"]
    assert len(links) == 28
    realizes = 0
    supports = 0
    for row in links:
        assert row["editorial_status"] == "CANONICAL_APPROVED", row
        assert row["editorial_status"] in LIFECYCLE_STATUSES, row
        assert row["relation"] in ("REALIZES", "SUPPORTS"), row
        assert row["strength"] is None, row
        assert str(row["resource_id"]).startswith("res-"), row
        assert str(row["node_id"]).startswith("cap-"), row
        if row["relation"] == "REALIZES":
            realizes += 1
            assert row["primary_flag"] is True, row
        else:
            supports += 1
            assert row["primary_flag"] is False, row
    assert (realizes, supports) == (15, 13)
    print(
        "[p5-r] corpus links -> "
        f"{sorted({row['editorial_status'] for row in links})}"
        f" ({len(links)} rows, all approved; {realizes} REALIZES,"
        f" {supports} SUPPORTS)"
    )


@pytest.mark.parametrize("index", range(28))
def test_every_rationale_states_its_basis_and_its_limit(index: int) -> None:
    """Every rationale must carry its basis **and** its limit, and each one
    names its own row. The basis differs by cut (C1 for the first row, C2-a
    for the eight it approved, C2-b for the nineteen it authored and
    approved), and the limits are stated in each row's own words: what the
    review did not cover (no capability-semantics audit, because the
    capability has no functional definition here), the Revisit, and — for the
    credit-bearing REALIZES rows — the live risk ``R-C1-credit``. A SUPPORTS
    row states the same no-audit limit and adds its own credit limit: the
    credit face reads REALIZES only, so an approved SUPPORTS row mints
    nothing. The P5-R ban on crediting an unapproved row is not carried by
    prose any more but by the status field: since C2-a no corpus row is
    unapproved, so this file pins the demoted case against a variant
    (test_the_gate_is_a_gate_not_a_deletion below)."""

    row = _links_document()["links"][index]
    rationale = str(row["rationale"])
    assert str(row["node_id"]) in rationale, rationale
    assert str(row["resource_id"]) in rationale, rationale
    assert row["editorial_status"] == "CANONICAL_APPROVED", row
    resource_id = str(row["resource_id"])
    if resource_id == DECISION:
        assert "Approved by the C1 (Phase 11) editorial review" in rationale
    elif resource_id in C2A_APPROVED:
        assert "Approved by the C2-a (Phase 11) editorial review" in rationale
    else:
        assert "C2-b (Phase 11) editorial review" in rationale, resource_id
        # The nineteen rows this cut authored carry their own provenance
        # limit: unlike the migrated nine, no authoring fixture declares them.
        assert "fixture" in rationale, resource_id
    assert "no functional definition" in rationale, rationale
    assert "no capability-semantics audit" in rationale, rationale
    assert "Revisit" in rationale, rationale
    if row["relation"] == "REALIZES":
        assert "did NOT cover" in rationale, rationale
        assert "no capability certification" in rationale, rationale
        assert "R-C1-credit" in rationale, rationale
    else:
        assert "SUPPORTS" in rationale, rationale
        assert "credit-safe" in rationale or "mints nothing" in rationale, rationale
        assert "primary_flag is false" in rationale, rationale


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
        assert len(eligible.value) == 33
    finally:
        store.close()


# ---------------------------------------------------------------------------
# ② the credit read is gated (artifact + provider face)
# ---------------------------------------------------------------------------


def test_the_link_row_stays_readable_and_the_credit_face_reads_the_approved_node(
    built_content_db,
) -> None:
    """The gate reads the link's own status, in both directions (旧真值: the
    unapproved row stayed readable and the credit face answered ``None``;
    新真值 C1: the same row, now approved, stays readable and the credit
    face answers the node). Unapproved ≠ deleted was never about this one
    row's status — it is the demoted variant in
    ``test_the_gate_is_a_gate_not_a_deletion`` that keeps that discipline
    pinned now that C2-a approved the remaining eight rows."""

    store = ContentStore(built_content_db)
    try:
        links = store.curriculum_links_of(DECISION)
        assert isinstance(links, Ok), links
        assert len(links.value) == 1
        assert links.value[0].editorial_status == "CANONICAL_APPROVED"
        assert links.value[0].node_id == HEDGED_OPINION
        assert links.value[0].rationale
        teaching = store.get_teaching_content(DECISION)
        assert isinstance(teaching, Ok), teaching
        assert teaching.value.capability_linkage == HEDGED_OPINION
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
        assert view.value.capability_linkage == HEDGED_OPINION
        assert view.value.target_status == "VALID"
    finally:
        provider.close()


def test_only_the_approved_realizes_link_credits_a_capability(
    built_content_db,
) -> None:
    """The gate applies by status **and by relation**, not by row count
    (旧真值: all nine linked resources read ``None`` on the credit face; C1:
    one approved row credited its node; C2-a: all nine approved rows credited;
    新真值 C2-b: twenty-eight rows are approved, and exactly the fifteen
    ``REALIZES`` rows credit — the thirteen approved ``SUPPORTS`` rows satisfy
    §8.1 R2's ``curriculum_link`` fact and mint nothing, because the read
    filters ``relation = REALIZES``). The count is what still distinguishes
    this from "every entity credits": the five CAPABILITY entities carry no
    link row at all and read ``None``. The unapproved direction is pinned
    against a demoted variant in test_the_gate_is_a_gate_not_a_deletion
    below."""

    store = ContentStore(built_content_db)
    try:
        linked = 0
        credited = 0
        supports_only = 0
        for entity_id in store.entity_ids().value:
            links = store.curriculum_links_of(entity_id)
            assert isinstance(links, Ok), links
            teaching = store.get_teaching_content(entity_id)
            assert isinstance(teaching, Ok), teaching
            if not links.value:
                assert teaching.value.capability_linkage is None, entity_id
                continue
            linked += 1
            relations = {str(link.relation) for link in links.value}
            if "REALIZES" in relations:
                assert teaching.value.capability_linkage is not None, entity_id
                assert teaching.value.capability_linkage in {
                    str(link.node_id)
                    for link in links.value
                    if str(link.relation) == "REALIZES"
                }, entity_id
                credited += 1
            else:
                # An approved SUPPORTS-only row: R2-readable, credit-safe.
                supports_only += 1
                assert relations == {"SUPPORTS"}, entity_id
                assert teaching.value.capability_linkage is None, entity_id
        assert linked == 28
        assert credited == 15
        assert supports_only == 13
    finally:
        store.close()
    print(
        f"[p5-r] linked resources -> {linked} (credited: {credited};"
        f" support-only: {supports_only})"
    )


def test_the_gate_is_a_gate_not_a_deletion(tmp_path) -> None:
    """A *demoted* variant artifact is not credited again: the same read, the
    same code path, only the editorial status differs (C2-a: the canonical
    corpus carries no unapproved row, so the off-state has to be built, and
    building it is what keeps "unapproved ≠ deleted" — the row stays readable
    while the credit face answers ``None``)."""

    def demote(documents: dict, _index: dict) -> None:
        for row in documents["links.json"]["links"]:
            if row["resource_id"] == "res-hedge-i-think":
                assert row["editorial_status"] == "CANONICAL_APPROVED"
                row["editorial_status"] = "CURRICULUM_MAPPED"

    artifact = build_variant_artifact(tmp_path, curriculum_edit=demote)
    store = ContentStore(artifact)
    try:
        demoted = store.get_teaching_content("res-hedge-i-think")
        assert isinstance(demoted, Ok), demoted
        assert demoted.value.capability_linkage is None
        # The row itself is still there, and still readable as a mapping.
        links = store.curriculum_links_of("res-hedge-i-think")
        assert isinstance(links, Ok), links
        assert len(links.value) == 1
        assert links.value[0].editorial_status == "CURRICULUM_MAPPED"
        # An untouched sibling still credits its node.
        other = store.get_teaching_content(DECISION)
        assert isinstance(other, Ok), other
        assert other.value.capability_linkage == HEDGED_OPINION
    finally:
        store.close()
    assert CAPABILITY_CREDIT_EDITORIAL_STATUS == "CANONICAL_APPROVED"


# ---------------------------------------------------------------------------
# ③ end to end: the named blocker pair
# ---------------------------------------------------------------------------


def test_make_a_decision_alternative_success_credits_the_approved_capability(
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
    """The same chain, at C1's truth (旧真值: the attempt produced exactly one
    honest NEUTRAL claim on the resource and **zero** change on the
    capability; 新真值: the C1-approved link makes the §5 fold credit it —
    one CAPABILITY_LINKAGE POSITIVE/SUCCESS claim on
    cap-eval-hedged-opinion **plus** the unchanged honest NEUTRAL/ABSTAIN
    claim on the resource, and the capability's durable state now moves with
    its claim). The gate's semantics are unchanged; what changed is the
    link's editorial status."""

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
    assert len(claims) == 2
    assert rendered == [
        (HEDGED_OPINION, "CAPABILITY_LINKAGE", "POSITIVE", "SUCCESS"),
        (DECISION, "FOCUS_TARGET", "NEUTRAL", "ABSTAIN"),
    ]

    # The capability's durable state now exists once its claim does (the
    # rebuild is called explicitly so "moved" is the rebuild's answer too,
    # not just an untouched row).
    rebuilt = learning_controller.rebuild_learner_state(
        TargetId(HEDGED_OPINION), EvidenceModality(MODALITY)
    )
    assert isinstance(rebuilt, Ok), rebuilt
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (HEDGED_OPINION,),
        )
        == 1
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


def test_the_payload_is_unchanged_except_the_now_approved_linkage(
    built_content_db,
) -> None:
    """One-field proof for the receipt, at C1's truth: the artifact's teaching
    payload is byte-for-byte what it was except ``capability_linkage`` — the
    §24.5 rows, the ladder and the slots are unchanged, so C1's approval (a
    link-row status edit + the readiness evidence authoring) did not smuggle
    a content edit in behind the gate (旧真值: the linkage read ``None``;
    新真值: it reads the node the approved link points at)."""

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
        assert payload.capability_linkage == HEDGED_OPINION
        links = supply.curriculum_links_of(ResourceId(DECISION))
        assert isinstance(links, Ok), links
        assert [str(link.node_id) for link in links.value] == [HEDGED_OPINION]
        assert [
            str(link.editorial_status) for link in links.value
        ] == ["CANONICAL_APPROVED"]
    finally:
        store.close()
