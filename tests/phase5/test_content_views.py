"""⑤ — the two runtime views, pinned column by column against canonical.

"两视图列集逐列钉": the content view's column set is the docs/DATA_MODEL.md
§24.1 seven-column list, and the curriculum registry view's column set is the
§7 registry record the repo already owns. Nothing here is a second hand-typed
copy of the vocabulary under test: the §24.1 and §24.7 lists are extracted
from the canonical document at test time, so a rename or an added column
fails here rather than silently becoming schema.

The other canonical vocabularies the build validates against (§24.4 subtypes /
fixedness / recognition policies, §24.5 example roles, §24.11 lifecycle,
§24.7 relations, §7 families and prerequisite strengths) are pinned the same
way.
"""

from __future__ import annotations

import dataclasses

import pytest

from elc.content.queries import (
    ContentExpressionView,
    ContentResourceView,
    ContentTargetView,
    ContentTeachingView,
)
from elc.content.store import ContentStore
from elc.content.types import (
    LEARNING_INTENTS,
    LIFECYCLE_STATUSES,
    TARGET_MODES,
    TARGET_TYPES,
    ContentType,
    ExampleLinkRole,
    ExpressionFixedness,
    ExpressionSubtype,
    RecognitionPolicy,
)
from elc.curriculum.types import (
    CapabilityFamily,
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
    CurriculumLinkRecord,
    CurriculumLinkRelation,
    PrerequisiteStrength,
)
from tests.phase5.conftest import canonical_lines

DATA_MODEL = "DATA_MODEL.md"
DOMAIN_MODEL = "DOMAIN_MODEL.md"

SECTION_24_4 = "### 24.4 Expression"
SECTION_24_7 = "### 24.7 Pedagogy / Labels / Curriculum Mapping"


def _field_names(record: type) -> tuple[str, ...]:
    return tuple(field.name for field in dataclasses.fields(record))


def test_content_resource_view_is_the_24_1_column_list_verbatim() -> None:
    canonical = canonical_lines(DATA_MODEL, "### 24.1 ContentEntity", 0)
    assert _field_names(ContentResourceView) == canonical
    assert len(canonical) == 7


def test_content_resource_view_has_exactly_seven_columns() -> None:
    """A superset would already be a schema change: §24.1 is the whole row."""

    assert set(_field_names(ContentResourceView)) == {
        "entity_id",
        "entity_type",
        "language",
        "lifecycle_status",
        "entity_revision",
        "created_in_version",
        "updated_in_version",
    }


def test_entity_type_enum_is_the_24_1_six_word_table() -> None:
    canonical = canonical_lines(DATA_MODEL, "### 24.1 ContentEntity", 1)
    assert tuple(str(member) for member in ContentType) == canonical
    assert len(canonical) == 6


def test_expression_subtypes_are_the_24_4_eight_words() -> None:
    canonical = canonical_lines(DATA_MODEL, SECTION_24_4, 0)
    assert tuple(str(member) for member in ExpressionSubtype) == canonical
    assert len(canonical) == 8


def test_expression_fixedness_is_the_24_4_three_words() -> None:
    canonical = canonical_lines(DATA_MODEL, SECTION_24_4, 1)
    assert tuple(str(member) for member in ExpressionFixedness) == canonical
    assert len(canonical) == 3


def test_recognition_policies_are_the_24_4_four_words() -> None:
    canonical = canonical_lines(DATA_MODEL, SECTION_24_4, 2)
    assert tuple(str(member) for member in RecognitionPolicy) == canonical
    assert len(canonical) == 4


def test_example_link_roles_are_the_24_5_four_words() -> None:
    canonical = canonical_lines(DATA_MODEL, "### 24.5 Construction / Example", 0)
    assert tuple(str(member) for member in ExampleLinkRole) == canonical
    assert len(canonical) == 4


def test_lifecycle_vocabulary_is_the_24_11_word_list() -> None:
    """Two canonical rows are slash alternatives ("X / Y" = either spelling
    is a legal value), so the word list expands them to single names."""

    canonical = canonical_lines(DATA_MODEL, "### 24.11 Lifecycle", 0)
    expanded = tuple(
        word
        for line in canonical
        for word in (part.strip() for part in line.split("/"))
    )
    assert LIFECYCLE_STATUSES == expanded
    assert "CANONICAL_APPROVED" in LIFECYCLE_STATUSES


def test_curriculum_link_view_is_the_24_7_column_list_verbatim() -> None:
    canonical = canonical_lines(DATA_MODEL, SECTION_24_7, 2)
    assert _field_names(CurriculumLinkRecord) == canonical
    assert len(canonical) == 7


def test_curriculum_link_relations_are_the_24_7_five_words() -> None:
    canonical = canonical_lines(DATA_MODEL, SECTION_24_7, 3)
    assert tuple(str(member) for member in CurriculumLinkRelation) == canonical
    assert len(canonical) == 5


def test_capability_registry_view_is_the_section_7_record() -> None:
    """The registry loader answers the domain's own §7 record —
    (curriculum_node_id, capability_id, family, level), no extra columns."""

    assert _field_names(CapabilityNodeRecord) == (
        "curriculum_node_id",
        "capability_id",
        "family",
        "level",
    )
    canonical_families = canonical_lines(
        DOMAIN_MODEL, "### Canonical capability families", 0
    )
    assert tuple(str(member) for member in CapabilityFamily) == canonical_families
    assert len(canonical_families) == 14


def test_target_types_are_the_section_6_two_words() -> None:
    """docs/DOMAIN_MODEL.md §6: every claim points at RESOURCE or CAPABILITY.

    elc.content.types declares the pair for the build's own source validation
    (elc.teaching.targets owns the Gate-port copy); the canonical list itself
    is extracted from §6 here so the local copy cannot drift silently.
    """

    canonical = canonical_lines(DOMAIN_MODEL, "### Learning Evidence kernel", 2)
    assert canonical == ("RESOURCE", "CAPABILITY")
    assert TARGET_TYPES == canonical


def test_target_modes_and_learning_intents_are_the_section_11_words() -> None:
    """docs/DOMAIN_MODEL.md §11 target modes / learning intents, verbatim
    (the same values elc.planner.types pins for the planner side)."""

    modes = canonical_lines(DOMAIN_MODEL, "### Target mode", 0)
    assert TARGET_MODES == modes
    assert len(modes) == 5
    intents = canonical_lines(DOMAIN_MODEL, "### Learning intent", 0)
    assert LEARNING_INTENTS == intents
    assert len(intents) == 7


def test_prerequisite_strengths_are_the_section_7_three_words() -> None:
    canonical = canonical_lines(DOMAIN_MODEL, "### Edges", 1)
    assert tuple(str(member) for member in PrerequisiteStrength) == canonical
    assert len(canonical) == 3


def test_prerequisite_edge_view_reuses_the_registry_record() -> None:
    assert _field_names(CurriculumEdgeRecord) == (
        "from_node",
        "to_node",
        "edge_type",
        "prerequisite_strength",
    )


def test_registry_rows_carry_the_whole_record(store: ContentStore) -> None:
    """Every declared row answers every declared column with a legal value."""

    expression_types = tuple(str(member) for member in ExpressionSubtype)
    fixedness_values = tuple(str(member) for member in ExpressionFixedness)
    policies = tuple(str(member) for member in RecognitionPolicy)
    families = tuple(str(member) for member in CapabilityFamily)
    for entity_id in store.entity_ids().value:
        resource = store.get_resource(entity_id).value
        assert resource.entity_id == entity_id
        assert resource.lifecycle_status in LIFECYCLE_STATUSES
        expression = store.get_expression(entity_id).value
        assert expression.expression_type in expression_types
        assert expression.fixedness in fixedness_values
        assert expression.recognition_policy in policies
        target = store.get_target(entity_id).value
        assert target.target_type in ("RESOURCE", "CAPABILITY")
        teaching = store.get_teaching_content(entity_id).value
        assert teaching.reveal_form in teaching.canonical_forms
    for capability_id in store.capability_ids().value:
        node = store.get_capability(capability_id).value
        assert node.capability_id == capability_id
        assert node.curriculum_node_id == capability_id
        assert node.family in families
        assert node.level == 2


def test_view_records_are_frozen() -> None:
    view = ContentResourceView(
        entity_id="x",
        entity_type="EXPRESSION",
        language="en",
        lifecycle_status="CANONICAL_APPROVED",
        entity_revision=1,
        created_in_version="content-v1",
        updated_in_version="content-v1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.language = "xx"
    for record in (
        ContentExpressionView,
        ContentTargetView,
        ContentTeachingView,
        CurriculumLinkRecord,
    ):
        assert record.__dataclass_params__.frozen is True
