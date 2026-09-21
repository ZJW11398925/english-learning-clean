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
from tests.phase3.target_fixtures import TEACHING_CONTENT, VALIDATED_TARGET_FIXTURES

FIXTURE_BY_TARGET = {view.target_id: view for view in VALIDATED_TARGET_FIXTURES}
TARGET_IDS = tuple(FIXTURE_BY_TARGET)
CONTENT_VERSION = "content-v1"


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
    """The rebuilt id set *is* the validated target id set — nothing minted,
    nothing renamed, nothing dropped."""

    assert set(store.entity_ids().value) == set(TARGET_IDS)


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
    """No silent drop: every P3-1B field, value for value, in authored order."""

    fixture = FIXTURE_BY_TARGET[target_id]
    view = store.get_teaching_content(target_id).value
    assert view.hint_ladder == fixture.hint_ladder
    assert view.reveal_form == fixture.reveal_form
    assert view.canonical_forms == fixture.canonical_forms
    assert view.alternative_realizations == fixture.alternative_realizations
    assert view.required_slots == fixture.required_slots
    assert view.capability_linkage == fixture.capability_linkage


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
    assert len(per_entity) == 14
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
            }
        )
    for row in ledger:
        print(
            "[migration] {target_id} | fixture={fixture_type} -> entity_id="
            "{entity_id} type={entity_type} lifecycle={lifecycle} expr={expression} "
            "mode={mode} intent={intent} | ladder={ladder} forms={forms} alts={alts} "
            "slots={slots} linkage={linkage}".format(**row)
        )
        assert row["entity_id"] == row["target_id"]
        assert row["entity_type"] == "EXPRESSION"
        assert row["lifecycle"] == "CANONICAL_APPROVED"
        assert int(row["ladder"]) == 3
        assert int(row["forms"]) >= 1
        assert int(row["slots"]) >= 1
        if row["fixture_type"] == "RESOURCE":
            assert row["linkage"] != "None"
        else:
            assert row["linkage"] == "None"
    assert len(ledger) == 14


def test_corpus_size_is_the_migrated_fourteen_not_a_new_expansion(
    store: ContentStore,
) -> None:
    """§6: migrate first, do not expand to 100."""

    assert len(store.entity_ids().value) == 14
    assert len(store.capability_ids().value) == 5
    assert CONTENT_SRC_DIR.name == "content_src"
