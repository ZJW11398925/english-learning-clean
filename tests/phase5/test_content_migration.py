"""① Migration comparison — every validated target lands field-complete.

The authoring source under test is a *migration* of the P3-1A/P3-1B validated
corpus `tests/phase3/target_fixtures.py` (IMPLEMENTATION_PLAN §6 "先迁移工具链
与 seed"). These tests compare the three layers one target at a time:

    old fixture field  →  content_src document  →  content.db row

and fail on any silently dropped or rewritten field. The only fixture fields
that do not land verbatim are `target_status` / `content_status`, which are
resolution-time validity judgments rather than content data — their declared
mapping is asserted separately below, so "not stored" stays a decision rather
than an omission.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elc.content.build import CONTENT_SRC_DIR
from elc.content.store import ContentStore
from elc.content.types import ContentType, ExampleLinkRole
from elc.platform.types import Ok, ResourceId
from tests.phase3.target_fixtures import TEACHING_CONTENT, VALIDATED_TARGET_FIXTURES

FIXTURE_BY_TARGET = {view.target_id: view for view in VALIDATED_TARGET_FIXTURES}
TARGET_IDS = tuple(FIXTURE_BY_TARGET)
CONTENT_VERSION = "content-v1"

#: The six of the nine fixture-linked RESOURCE targets whose §24.7 row C3-R1
#: demoted from REALIZES to SUPPORTS (its capability re-review found no
#: realization in them; a realization claim must be a mapping claim). Their
#: rows stay readable and approved, keep the fixture's node_id and their
#: frozen primary_flag, and no longer credit a capability.
C3R1_DEMOTED_TARGETS = (
    "res-colloc-make-a-decision",
    "res-colloc-pay-attention-to",
    "res-frame-id-like-to",
    "res-idiom-break-the-ice",
    "res-phrasal-look-forward-to",
    "res-pragmatic-could-you",
)


def _document(entity_id: str) -> dict[str, object]:
    path = CONTENT_SRC_DIR / "entities" / f"{entity_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_fixture_set_is_the_fourteen_validated_targets() -> None:
    assert len(VALIDATED_TARGET_FIXTURES) == 14
    assert len(TARGET_IDS) == 14
    assert len(set(TARGET_IDS)) == 14
    kinds = [view.target_type for view in VALIDATED_TARGET_FIXTURES]
    assert kinds.count("RESOURCE") == 9
    assert kinds.count("CAPABILITY") == 5


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_target_id_survives_verbatim(store: ContentStore, target_id: str) -> None:
    """The entity id is the fixture target id — no derived or hashed renaming."""

    assert target_id in store.entity_ids().value
    document = _document(target_id)
    entity = document["entity"]
    assert isinstance(entity, dict)
    assert entity["entity_id"] == target_id
    assert store.get_resource(target_id).value.entity_id == target_id


def test_stable_resource_identity_is_the_fixture_id_set(store: ContentStore) -> None:
    """The rebuilt id set *contains* the validated target id set — nothing
    minted, nothing renamed, nothing dropped.

    旧真值 (P5-0): the rebuilt id set *was* the fixture id set (14 == 14).
    新真值 (C3-b): the corpus has grown past the migration — the fourteen
    fixture ids are all still there, and fifty-five further RESOURCE
    entities were authored by the C2-b, C3-a and C3-b cuts, so the set is a
    strict
    superset (69). The fixture half stays an equality: every fixture id must
    still resolve.
    """

    rebuilt = set(store.entity_ids().value)
    assert set(TARGET_IDS) <= rebuilt
    assert rebuilt - set(TARGET_IDS) == {
        "res-colloc-come-to-a-conclusion",
        "res-colloc-draw-attention-to",
        "res-colloc-have-an-effect-on",
        "res-colloc-heavy-rain",
        "res-colloc-keep-in-mind",
        "res-colloc-make-an-effort",
        "res-colloc-make-progress",
        "res-colloc-make-sense",
        "res-colloc-meet-a-deadline",
        "res-colloc-play-a-role",
        "res-colloc-raise-awareness",
        "res-colloc-save-time",
        "res-colloc-take-a-look",
        "res-colloc-take-advantage-of",
        "res-colloc-take-part-in",
        "res-discourse-anyway",
        "res-discourse-having-said-that",
        "res-discourse-in-fact",
        "res-discourse-long-story-short",
        "res-discourse-that-reminds-me",
        "res-discourse-to-be-honest",
        "res-frame-if-you-dont-mind",
        "res-frame-just-wondering",
        "res-frame-lets-say",
        "res-frame-the-thing-is",
        "res-frame-what-im-saying-is",
        "res-frame-would-you-mind",
        "res-hedge-i-guess",
        "res-hedge-i-mean",
        "res-hedge-im-not-sure",
        "res-hedge-it-depends",
        "res-hedge-not-really",
        "res-hedge-sort-of",
        "res-idiom-a-blessing-in-disguise",
        "res-idiom-hit-the-nail-on-the-head",
        "res-idiom-on-the-same-page",
        "res-idiom-piece-of-cake",
        "res-idiom-the-ball-is-in-your-court",
        "res-idiom-under-the-weather",
        "res-phrasal-bring-up",
        "res-phrasal-carry-on",
        "res-phrasal-come-up-with",
        "res-phrasal-figure-out",
        "res-phrasal-give-up",
        "res-phrasal-put-off",
        "res-phrasal-run-out-of",
        "res-phrasal-turn-out",
        "res-phrasal-work-out",
        "res-pragmatic-could-i-ask",
        "res-pragmatic-no-offense-but",
        "res-pragmatic-sorry-to-interrupt",
        "res-pragmatic-thats-a-good-point-but",
        "res-softener-a-bit",
        "res-softener-if-anything",
        "res-softener-to-be-fair",
    }
    assert len(rebuilt) == 69


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_entity_row_is_the_seven_canonical_columns(
    store: ContentStore, target_id: str
) -> None:
    view = store.get_resource(target_id).value
    assert view.entity_type == str(ContentType.EXPRESSION)
    assert view.language == "en"
    assert view.lifecycle_status == "CANONICAL_APPROVED"
    assert view.entity_revision == 1
    assert view.created_in_version == CONTENT_VERSION
    assert view.updated_in_version == CONTENT_VERSION


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_target_defaults_match_the_fixture_verbatim(
    store: ContentStore, target_id: str
) -> None:
    fixture = FIXTURE_BY_TARGET[target_id]
    view = store.get_target(target_id).value
    assert view.target_type == fixture.target_type
    assert view.target_mode == fixture.target_mode
    assert view.learning_intent == fixture.learning_intent
    assert view.evidence_modality == fixture.evidence_modality


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_teaching_payload_matches_the_fixture_verbatim(
    store: ContentStore, target_id: str
) -> None:
    """No silent drop: every P3-1B field, value for value, in authored order.

    The credit face reads a §24.7 link the review **approved** *and* whose
    ``mapping_class`` is ``CURRICULUM_MAPPING`` (that is what the credit read
    filters — P5-R's status gate plus C3-R1's mapping class). P5-R landed with
    all nine links unapproved, C1 approved exactly one
    (res-colloc-make-a-decision) and C2-a approved the other eight while
    authoring their readiness evidence; C3-R1's capability re-review then
    found six of those nine rows coverage placements — the collocation, the
    request frame and the phrasal verb name an act or a wish rather than
    performing the node's move — and moved them to ``SUPPORTS``, so three of
    the nine still credit their node
    (``res-hedge-i-think``, ``res-softener-kind-of``, ``res-discourse-by-the-way``)
    and six read ``None`` while their row stays readable and approved. A
    CAPABILITY entity carries no link row of its own and reads ``None``. The
    fixture's declared linkage is in either case the row's ``node_id``,
    asserted below, which is what keeps "the payload is unchanged" a checked
    statement rather than a hope. The unapproved case — "a candidate mapping
    credits nothing" — is pinned against a demoted variant in
    tests/phase5/test_p5_r_curriculum_truth.py (the gate's own test), because
    the canonical corpus no longer carries an unapproved row.
    """

    fixture = FIXTURE_BY_TARGET[target_id]
    view = store.get_teaching_content(target_id).value
    assert view.hint_ladder == fixture.hint_ladder
    assert view.reveal_form == fixture.reveal_form
    assert view.canonical_forms == fixture.canonical_forms
    assert view.alternative_realizations == fixture.alternative_realizations
    assert view.required_slots == fixture.required_slots
    if fixture.capability_linkage is None:
        assert view.capability_linkage is None
    elif target_id in C3R1_DEMOTED_TARGETS:
        # The row is still there, still approved, still naming the fixture's
        # node — and no longer a realization, so it credits nothing.
        assert view.capability_linkage is None
        links = store.curriculum_links_of(ResourceId(target_id))
        assert isinstance(links, Ok), links
        assert len(links.value) == 1
        assert str(links.value[0].node_id) == fixture.capability_linkage
        assert str(links.value[0].relation) == "SUPPORTS"
        assert links.value[0].editorial_status == "CANONICAL_APPROVED"
    else:
        # C1/C2-a: the §24.7 link the editorial review approved. The credit
        # face reads the node — an approved mapping is exactly what the gate
        # admits — and the node is the fixture's declared linkage.
        assert view.capability_linkage == fixture.capability_linkage, (
            "the approved §24.7 link credits its node on the credit face"
        )
        links = store.curriculum_links_of(ResourceId(target_id))
        assert isinstance(links, Ok), links
        assert [str(link.node_id) for link in links.value] == [
            fixture.capability_linkage
        ]
        assert {str(link.editorial_status) for link in links.value} == {
            "CANONICAL_APPROVED"
        }


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_authored_document_matches_the_fixture_verbatim(target_id: str) -> None:
    """The middle column of the comparison: fixture → content_src document."""

    fixture = FIXTURE_BY_TARGET[target_id]
    fixture_content = TEACHING_CONTENT[target_id]
    teaching = _document(target_id)["teaching_content"]
    assert isinstance(teaching, dict)
    assert tuple(teaching["hint_ladder"]) == tuple(fixture_content["hint_ladder"])
    assert teaching["reveal_form"] == fixture_content["reveal_form"]
    assert tuple(teaching["canonical_forms"]) == tuple(
        fixture_content["canonical_forms"]
    )
    assert tuple(teaching["alternative_realizations"]) == tuple(
        fixture_content["alternative_realizations"]
    )
    assert (
        tuple(tuple(group) for group in teaching["required_slots"])
        == tuple(fixture_content["required_slots"])
    )
    target = _document(target_id)["target"]
    assert isinstance(target, dict)
    assert target["target_type"] == fixture.target_type
    assert target["target_mode"] == fixture.target_mode
    assert target["learning_intent"] == fixture.learning_intent
    assert target["evidence_modality"] == fixture.evidence_modality


def test_validity_facts_are_the_declared_non_migrated_pair(
    store: ContentStore, built_content_db: Path
) -> None:
    """`target_status` / `content_status` are the only fixture fields without
    a column, and the declared mapping (resolvable entity + live lifecycle) is
    what stands in for them."""

    import sqlite3

    conn = sqlite3.connect(str(built_content_db))
    try:
        entity_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(content_entity)")
        }
        target_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(content_target)")
        }
    finally:
        conn.close()
    assert "target_status" not in entity_columns | target_columns
    assert "content_status" not in entity_columns | target_columns
    for target_id in TARGET_IDS:
        assert FIXTURE_BY_TARGET[target_id].target_status == "VALID"
        assert FIXTURE_BY_TARGET[target_id].content_status == "VALID"
        assert store.get_resource(target_id).value.lifecycle_status == (
            "CANONICAL_APPROVED"
        )


def test_forms_are_stored_under_canonical_example_roles(
    store: ContentStore, built_content_db: Path
) -> None:
    """canonical_forms → §24.5 PRIMARY_TARGET, alternative_realizations →
    SUPPORTING; the role vocabulary is the canonical §24.5 one."""

    import sqlite3

    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT DISTINCT role FROM content_example ORDER BY role"
        ).fetchall()
    finally:
        conn.close()
    roles = {row[0] for row in rows}
    # The corpus exercises two of the four §24.5 roles; both must be legal.
    assert roles == {
        str(ExampleLinkRole.PRIMARY_TARGET),
        str(ExampleLinkRole.SUPPORTING),
    }
    assert roles <= {str(member) for member in ExampleLinkRole}
    for target_id in TARGET_IDS:
        view = store.get_teaching_content(target_id).value
        if view.canonical_forms:
            assert view.canonical_forms[0] == view.reveal_form


def test_hint_ladder_ordinals_are_dense_and_ordered(
    built_content_db: Path,
) -> None:
    import sqlite3

    conn = sqlite3.connect(str(built_content_db))
    try:
        rows = conn.execute(
            "SELECT entity_id, ordinal FROM content_hint_rung "
            "ORDER BY entity_id, ordinal"
        ).fetchall()
    finally:
        conn.close()
    per_entity: dict[str, list[int]] = {}
    for entity_id, ordinal in rows:
        per_entity.setdefault(str(entity_id), []).append(int(ordinal))
    assert len(per_entity) == 69
    for entity_id, ordinals in per_entity.items():
        assert ordinals == list(range(len(ordinals))), entity_id
        assert len(ordinals) == 3


def test_migration_ledger_is_complete_for_all_fourteen(
    store: ContentStore,
) -> None:
    """The one-table view of the migration: fixture field → document → row.

    `pytest -s` prints the ledger; the assertions check that every row carries
    every migrated field, so a partial row fails here rather than in a reader.
    """

    ledger: list[dict[str, str]] = []
    for target_id in TARGET_IDS:
        fixture = FIXTURE_BY_TARGET[target_id]
        resource = store.get_resource(target_id).value
        expression = store.get_expression(target_id).value
        target = store.get_target(target_id).value
        teaching = store.get_teaching_content(target_id).value
        links = store.curriculum_links_of(target_id)
        assert isinstance(links, Ok), links
        ledger.append(
            {
                "target_id": target_id,
                "fixture_type": fixture.target_type,
                "entity_id": resource.entity_id,
                "entity_type": resource.entity_type,
                "lifecycle": resource.lifecycle_status,
                "expression": expression.expression_type,
                "mode": target.target_mode,
                "intent": target.learning_intent,
                "ladder": str(len(teaching.hint_ladder)),
                "forms": str(len(teaching.canonical_forms)),
                "alts": str(len(teaching.alternative_realizations)),
                "slots": str(len(teaching.required_slots)),
                "linkage": str(teaching.capability_linkage),
                "link_status": ",".join(
                    sorted({str(link.editorial_status) for link in links.value})
                )
                or "none",
            }
        )
    for row in ledger:
        print(
            "[migration] {target_id} | fixture={fixture_type} -> entity_id="
            "{entity_id} type={entity_type} lifecycle={lifecycle} expr={expression} "
            "mode={mode} intent={intent} | ladder={ladder} forms={forms} alts={alts} "
            "slots={slots} linkage={linkage} link_status={link_status}".format(**row)
        )
        assert row["entity_id"] == row["target_id"]
        assert row["entity_type"] == "EXPRESSION"
        assert row["lifecycle"] == "CANONICAL_APPROVED"
        assert int(row["ladder"]) == 3
        assert int(row["forms"]) >= 1
        assert int(row["slots"]) >= 1
        # P5-R's gate plus C3-R1's mapping class: every RESOURCE target's
        # §24.7 row is approved and readable, and the row credits its node
        # unless C3-R1 demoted it (then the credit face reads None and the
        # row keeps the fixture's node); the CAPABILITY entities carry no link
        # row of their own, so their credit face reads None.
        if row["fixture_type"] == "RESOURCE":
            expected_node = FIXTURE_BY_TARGET[row["target_id"]].capability_linkage
            assert expected_node is not None, row["target_id"]
            assert row["link_status"] == "CANONICAL_APPROVED"
            if row["target_id"] in C3R1_DEMOTED_TARGETS:
                assert row["linkage"] == "None"
            else:
                assert row["linkage"] == expected_node
        else:
            assert row["linkage"] == "None"
            assert row["link_status"] == "none"
    assert len(ledger) == 14


def test_corpus_size_is_the_migrated_fourteen_plus_the_phase11_additions(
    store: ContentStore,
) -> None:
    """§6: migrate first, do not expand to 100 — read against the corpus as
    it stands after the Phase 11 content programme.

    旧真值 (P5-0): 14 entities / 5 capabilities, i.e. "the migrated fourteen
    and nothing else". 新真值 (C3-b): 69 entities / 5 capabilities — the
    fourteen migrated targets are all still present (the equality above), the
    fifty-five additions are the C2-b, C3-a and C3-b RESOURCE entities, and
    the capability registry is untouched at five. The 100 of IP §13 is still
    not
    reached (64 < 100); of the Calibration100 floors the volume one is unmet
    while CORE_A/CORE_C are met under the declared reading — this test pins
    the size only, and the three readings live in
    test_c2b_resource_expansion.py and test_c3a_readface_and_expansion.py."""

    assert len(store.entity_ids().value) == 69
    assert len(store.capability_ids().value) == 5
    resources = [
        entity_id
        for entity_id in store.entity_ids().value
        if str(entity_id).startswith("res-")
    ]
    assert len(resources) == 64
    assert CONTENT_SRC_DIR.name == "content_src"
