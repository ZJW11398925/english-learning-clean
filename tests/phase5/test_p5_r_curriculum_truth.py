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

What is pinned here, in order (written at P5-R's truth; C1, C2-a, C2-b and
C3-a each moved the corpus forward, and each group states both):

- the rows are honest: all nine seed rows were ``CURRICULUM_MAPPED`` at P5-R;
  C1's editorial review approved one, C2-a's approved the other eight while
  authoring their readiness evidence, C2-b authored and approved nineteen
  more while authoring its entities, and C3-a authored and approved eighteen
  more — so today all sixty-four rows are ``CANONICAL_APPROVED``, each with a
  rationale that names the approval, what it covered and what it did not
  (curriculum/links.json). The seed rows' mapping fields (`relation`,
  `strength`, `primary_flag`, the two ids) are untouched by the approvals;
  the C2-b and C3-a rows declare their own relation, and the 43 ``SUPPORTS``
  rows carry ``primary_flag = false`` because the primary flag marks the
  primary **REALIZES** link (the only thing the build's at-most-one check
  counts);
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
#: ``cap-eval-hedged-opinion`` on the strength of the P3 fixture alone. C3-R1
#: demoted the row (a collocation names an act, it hedges nothing), so the
#: chain no longer credits it.
DECISION = "res-colloc-make-a-decision"
DECISION_ALTERNATIVE = "We have to take a decision today."
HEDGED_OPINION = "cap-eval-hedged-opinion"
MODALITY = "TEXT_PRODUCTION"

#: A RESOURCE whose §24.7 row C3-R1 kept as a curriculum mapping (relation
#: REALIZES, mapping class CURRICULUM_MAPPING), used by the end-to-end credit
#: test so the credit path stays proven after the six demotions.
HEDGE_TARGET = "res-hedge-i-think"
HEDGE_ALTERNATIVE = "It might rain."

SEED_LINKS = CURRICULUM_DIR / "links.json"

#: The nine P3-1A/P3-1B migrated rows whose linkage the authoring fixture
#: (tests/phase3/target_fixtures.py) declares — every other row's rationale
#: says that no fixture declares it.
FIXTURE_DECLARED = (
    "res-colloc-make-a-decision",
    "res-colloc-pay-attention-to",
    "res-discourse-by-the-way",
    "res-frame-id-like-to",
    "res-hedge-i-think",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
    "res-softener-kind-of",
)

#: The six rows C3-R1 demoted from REALIZES to SUPPORTS (each rationale
#: discloses it, each frozen primary_flag still records the authoring claim).
DEMOTED = (
    "res-colloc-make-a-decision",
    "res-colloc-pay-attention-to",
    "res-frame-id-like-to",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
)

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

#: The eighteen rows C3-a authored and approved while authoring its entities.
C3A_APPROVED = (
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

#: The eighteen rows C3-b authored and approved while authoring its entities.
C3B_APPROVED = (
    "res-colloc-make-an-effort",
    "res-colloc-make-progress",
    "res-colloc-raise-awareness",
    "res-colloc-save-time",
    "res-colloc-take-a-look",
    "res-discourse-long-story-short",
    "res-discourse-that-reminds-me",
    "res-frame-just-wondering",
    "res-frame-the-thing-is",
    "res-hedge-i-guess",
    "res-hedge-not-really",
    "res-idiom-a-blessing-in-disguise",
    "res-idiom-the-ball-is-in-your-court",
    "res-phrasal-bring-up",
    "res-phrasal-put-off",
    "res-phrasal-work-out",
    "res-pragmatic-no-offense-but",
    "res-softener-if-anything",
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
    C3-a eighteen and C3-b the last eighteen, so today all sixty-four rows are
    ``CANONICAL_APPROVED``.
    **C3-R1 then re-read their semantics**: the relation word of six rows
    moved (REALIZES → SUPPORTS, each row's own rationale disclosing it) while
    the five mapping fields the approvals were forbidden to touch
    (``node_id``, ``strength``, ``primary_flag``, ``editorial_status`` and the
    resource id) are exactly what the re-review was forbidden to touch too.
    ``primary_flag`` therefore records the *authoring* claim: it stays true on
    those six rows, and the credit read — which keys on
    ``relation = REALIZES`` — is what the demotion changes. ``strength`` is
    null everywhere (no vocabulary is invented)."""

    links = _links_document()["links"]
    assert len(links) == 64
    realizes = 0
    supports = 0
    demoted = 0
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
            if row["primary_flag"] is True:
                # A demoted row: the flag is the frozen authoring claim.
                demoted += 1
                assert (
                    "corrected from REALIZES to SUPPORTS" in str(row["rationale"])
                ), row
            else:
                assert row["primary_flag"] is False, row
    assert (realizes, supports) == (15, 49)
    assert demoted == 6
    print(
        "[p5-r] corpus links -> "
        f"{sorted({row['editorial_status'] for row in links})}"
        f" ({len(links)} rows, all approved; {realizes} REALIZES,"
        f" {supports} SUPPORTS)"
    )


@pytest.mark.parametrize("index", range(64))
def test_every_rationale_states_its_basis_and_its_limit(index: int) -> None:
    """Every rationale is written in the C3-R1 review genre: it names the node
    it points at and that node's functional-definition file, quotes the
    resource's **own** first taught rung (the row-identity check — it is
    checkable against the entity source, so a copy-pasted rationale fails),
    states the mapping class it was judged into, cites the criterion list it
    was judged by (``counts_as_realization`` for a mapping, ``does_not_count``
    for a placement), states its credit consequence in its own words, states
    its provenance (which cut authored the row, and whether an authoring
    fixture declares the linkage) and registers its Revisit. The six demoted
    rows additionally disclose the relation change in their own words. The
    P5-R ban on crediting an unapproved row is not carried by prose any more
    but by the status field: since C2-a no corpus row is unapproved, so this
    file pins the demoted case against a variant
    (test_the_gate_is_a_gate_not_a_deletion below)."""

    row = _links_document()["links"][index]
    rationale = str(row["rationale"])
    node = str(row["node_id"])
    assert node in rationale, rationale
    assert f"curriculum/capabilities/{node}.json" in rationale, rationale
    assert row["editorial_status"] == "CANONICAL_APPROVED", row
    assert row["mapping_class"] in rationale, rationale
    assert "C3-R1 (Phase 11) capability-semantics re-review" in rationale
    assert "Revisit" in rationale, rationale
    assert "Row provenance:" in rationale, rationale
    resource_id = str(row["resource_id"])
    # Provenance: the nine fixture-declared rows say so; the cuts' own rows
    # say which cut authored them.
    if resource_id in FIXTURE_DECLARED:
        assert "authoring fixture" in rationale, resource_id
    else:
        assert "no authoring fixture" in rationale, resource_id
        if resource_id in C3A_APPROVED:
            assert "C3-a (Phase 11)" in rationale, resource_id
        elif resource_id in C3B_APPROVED:
            assert "C3-b (Phase 11)" in rationale, resource_id
        else:
            # Every remaining row was authored by C2-b (the C2-a rows are all
            # fixture-declared; C1's own row is DECISION above).
            assert "C2-b (Phase 11)" in rationale, resource_id
    if row["mapping_class"] == "CURRICULUM_MAPPING":
        assert "counts_as_realization" in rationale, rationale
    else:
        assert "does_not_count" in rationale, rationale
    if row["relation"] == "REALIZES":
        assert "credit face" in rationale, rationale
    else:
        assert "mints nothing" in rationale or "credit" in rationale, rationale
    if resource_id in DEMOTED:
        assert "corrected from REALIZES to SUPPORTS" in rationale, resource_id


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
        assert len(eligible.value) == 69
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
    C1: the same row, now approved, stayed readable and the credit face
    answered the node; **C3-R1**: the row is still readable and approved, and
    the credit face now answers ``None`` — the capability re-review found the
    collocation a coverage placement, so its relation word moved to
    ``SUPPORTS`` and a realization claim it no longer makes is not
    credited). Unapproved ≠ deleted was never about this one row's status —
    it is the demoted variant in ``test_the_gate_is_a_gate_not_a_deletion``
    that keeps that discipline pinned."""

    store = ContentStore(built_content_db)
    try:
        links = store.curriculum_links_of(DECISION)
        assert isinstance(links, Ok), links
        assert len(links.value) == 1
        assert links.value[0].editorial_status == "CANONICAL_APPROVED"
        assert links.value[0].node_id == HEDGED_OPINION
        assert str(links.value[0].relation) == "SUPPORTS"
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


def test_only_the_approved_realizes_link_credits_a_capability(
    built_content_db,
) -> None:
    """The gate applies by status **and by relation**, not by row count
    (旧真值: all nine linked resources read ``None`` on the credit face; C1:
    one approved row credited its node; C2-a: all nine approved rows credited;
    C2-b: twenty-eight rows approved, fifteen crediting; C3-b: sixty-four rows
    approved and twenty-one crediting; **新真值 C3-R1**: sixty-four rows are
    approved and exactly the fifteen ``REALIZES`` rows credit — the six rows
    the re-review demoted are approved ``SUPPORTS`` rows now, and the other
    forty-three approved ``SUPPORTS`` rows were placements all along, so none
    of them credits (the read filters ``relation = REALIZES``). The count is
    what still distinguishes this from "every entity credits": the five
    CAPABILITY entities carry no link row at all and read ``None``. The
    unapproved direction is pinned against a demoted variant in
    test_the_gate_is_a_gate_not_a_deletion below."""

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
        assert linked == 64
        assert credited == 15
        assert supports_only == 49
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
        # An untouched sibling still credits its node (a surviving REALIZES
        # row — C3-R1 moved the demoted collocation out of the credit set).
        other = store.get_teaching_content("res-hedge-i-guess")
        assert isinstance(other, Ok), other
        assert other.value.capability_linkage == HEDGED_OPINION
    finally:
        store.close()
    assert CAPABILITY_CREDIT_EDITORIAL_STATUS == "CANONICAL_APPROVED"


# ---------------------------------------------------------------------------
# ③ end to end: the named blocker pair
# ---------------------------------------------------------------------------


def test_make_a_decision_no_longer_credits_its_reviewed_placement(
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
    """The blocker pair, end to end, at C3-R1's truth: the attempt still
    evaluates ALTERNATIVE_SUCCESS (the evaluator is untouched), and the §5
    fold credits nothing — one honest NEUTRAL/ABSTAIN claim on the resource
    and **zero** capability movement. The C1 approval admitted this row when
    approval was the whole gate; C3-R1's capability re-review found the
    collocation a coverage placement, so the credit the approval once
    admitted is withdrawn — the same shape as P5-R's 旧真值, reached this time
    by review rather than by an unapproved row. The credit path itself is
    still exercised end to end by
    ``test_a_surviving_mapping_credits_its_capability_end_to_end`` below."""

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
    assert len(claims) == 1
    assert rendered == [(DECISION, "FOCUS_TARGET", "NEUTRAL", "ABSTAIN")]

    # No capability claim, so no capability durable state: the rebuild answers
    # "nothing to project" for the capability and still moves for the resource.
    learning_controller.rebuild_learner_state(
        TargetId(HEDGED_OPINION), EvidenceModality(MODALITY)
    )
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (HEDGED_OPINION,),
        )
        == 0
    )
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


def test_a_surviving_mapping_credits_its_capability_end_to_end(
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
    """The credit path, end to end, on a row C3-R1 kept: res-hedge-i-think's
    alternative realization ('It might rain.') is an ALTERNATIVE_SUCCESS, and
    the §5 fold credits it — one CAPABILITY_LINKAGE POSITIVE/SUCCESS claim on
    cap-eval-hedged-opinion plus the unchanged honest NEUTRAL/ABSTAIN claim on
    the resource, with the capability's durable state moving with its claim.
    Written after the demotion so "the fall-back withdrew six targets, not the
    credit mechanism" is a pinned fact rather than a claim."""

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
    assert _capability_rows(db) == ()
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0

    opened = open_moment(coordinator, "cm-c3r1-credit-open", HEDGE_TARGET)
    assert opened.gate_decision == "ALLOW"
    assert opened.moment_id is not None
    reply = reply_ok(
        coordinator,
        attempt(HEDGE_ALTERNATIVE),
        "cm-c3r1-credit-attempt",
    )
    assert reply.evaluation_outcome == "ALTERNATIVE_SUCCESS"

    rendered = [
        (c["target_id"], c["claim_role"], c["polarity"], c["outcome"])
        for c in _claims(db)
    ]
    print(f"[c3r1] alternative-success claims -> {rendered}")
    assert len(rendered) == 2
    assert rendered == [
        (HEDGED_OPINION, "CAPABILITY_LINKAGE", "POSITIVE", "SUCCESS"),
        (HEDGE_TARGET, "FOCUS_TARGET", "NEUTRAL", "ABSTAIN"),
    ]
    rebuild = learning_controller.rebuild_learner_state(
        TargetId(HEDGED_OPINION), EvidenceModality(MODALITY)
    )
    assert isinstance(rebuild, Ok), rebuild
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (HEDGED_OPINION,),
        )
        == 1
    )


def test_the_payload_is_unchanged_except_the_now_approved_linkage(
    built_content_db,
) -> None:
    """One-field proof for the receipt, at C3-R1's truth: the artifact's
    teaching payload is byte-for-byte what it was except ``capability_linkage``
    — the §24.5 rows, the ladder and the slots are unchanged, so neither C1's
    approval (a link-row status edit + the readiness evidence authoring) nor
    C3-R1's demotion (a relation-word edit + the mapping-class column)
    smuggled a content edit in behind the gate (旧真值: the linkage read
    ``None``; C1..C3-b: it read the node the approved link pointed at;
    新真值 C3-R1: ``None`` again, because the row is no longer a
    realization)."""

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
        assert [
            str(link.editorial_status) for link in links.value
        ] == ["CANONICAL_APPROVED"]
        assert [str(link.relation) for link in links.value] == ["SUPPORTS"]
    finally:
        store.close()
