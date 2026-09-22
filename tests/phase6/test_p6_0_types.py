"""P6-0 ① — the three §5.1 objects: canonical column sets, declared shapes,
and the version-naming decision.

docs/DATA_MODEL.md §5.1 is the authority these tests read: every column list
below is extracted from the document at test time and compared, in order,
with the dataclass field list — so a drifted column (a renamed one, an extra
one, a missing one) fails here instead of becoming the repo's de-facto
schema. §5.1 pins the *names* of the list/map elements and not their shape,
so what this file also pins is the shape this implementation declares
(DATA_MODEL §27) and the one naming decision the canonical blocks leave open:
the qualified ``goal_version`` / ``policy_version`` spelling of §5.1's bare
``version``, whose rationale, limitation and revisit condition live in
elc/user_config/types.py.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from enum import StrEnum
from pathlib import Path
from typing import Mapping, get_type_hints

import pytest

from elc.platform.registry import CANONICAL_OBJECTS
from elc.platform.types import VERSION_FIELDS as PLATFORM_VERSION_FIELDS
from elc.platform.types import (
    ConversationId,
    GoalModality,
    GoalVersion,
    PolicyVersion,
    ScheduleVersion,
    UserId,
)
from elc.user_config import types as user_config_types
from elc.user_config.types import (
    DisclosureLevel,
    LearningGoal,
    LearningGoalPortfolio,
    PlannerConstraintScope,
    PlannerConstraintType,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)

from .conftest import canonical_lines

TYPES_MODULE = Path(user_config_types.__file__)

#: §5.1's column blocks, and the implementation's spelling of the one column
#: the canonical blocks leave unqualified (the module docstring carries the
#: reasons; the reveal is pinned below).
VERSION_SPELLINGS = {
    "### LearningGoalPortfolio": "goal_version",
    "### TeachingPolicyProfile": "policy_version",
    "### SessionFocus": None,
}

#: The eight TeachingPolicyProfile columns whose value range §5.1 does not
#: pin — carried raw, never interpreted, never given a vocabulary here.
UNPINNED_POLICY_COLUMNS = (
    "mode",
    "interruption_budget",
    "curriculum_initiative",
    "correction_strictness",
    "hint_policy",
    "assessment_visibility",
    "practice_density",
    "persona_freedom",
)


def _canonical_columns(heading: str) -> list[str]:
    """§5.1's column block, with the declared version spelling applied.

    ``goal_portfolio_id`` and friends are read straight out of the document
    (never typed twice); only the bare ``version`` line is translated, and
    only when this implementation declares a qualified name for it.
    """

    spelling = VERSION_SPELLINGS[heading]
    columns: list[str] = []
    for line in canonical_lines("DATA_MODEL.md", heading, 0):
        name = line.rstrip("?").removesuffix("[]")
        columns.append(spelling if name == "version" and spelling else name)
    assert columns, f"{heading} yielded no columns"
    return columns


# -- ① the column sets, under the declared version alias ---------------------


@pytest.mark.parametrize("heading", sorted(VERSION_SPELLINGS))
def test_the_column_set_is_the_canonical_block_with_the_declared_alias(
    heading,
) -> None:
    """The field list equals §5.1's block **with the declared version alias
    applied** — P7-0's re-wording of this pin's claim, which used to say
    "word for word".

    There is one translated line and it is named: §5.1 spells ``version`` and
    this implementation spells ``goal_version`` / ``policy_version``, a
    binding the platform registry needs (the alias reading is in
    elc/user_config/types.py). Everything else is the canonical block's own
    text, and the translation itself is asserted separately below — so the
    claim this file makes is "the canonical block, under one declared alias",
    never "identical to it".
    """

    schema = {
        "### LearningGoalPortfolio": LearningGoalPortfolio,
        "### TeachingPolicyProfile": TeachingPolicyProfile,
        "### SessionFocus": SessionFocus,
    }[heading]
    fields = [field.name for field in dataclasses.fields(schema)]
    assert fields == _canonical_columns(heading)


def test_the_three_column_counts_are_the_canonical_ones() -> None:
    assert len(dataclasses.fields(LearningGoalPortfolio)) == 8
    assert len(dataclasses.fields(TeachingPolicyProfile)) == 13
    assert len(dataclasses.fields(SessionFocus)) == 7


def test_the_canonical_blocks_spell_a_bare_version() -> None:
    """The alias's *reason*, pinned as a fact: §5.1's own blocks say
    ``version``, so the qualified spelling is a declared reading and the
    module writes the limitation down where the spelling is (P7-0: it also
    says, in as many words, that the two are **not** to be called equal)."""

    for heading in ("### LearningGoalPortfolio", "### TeachingPolicyProfile"):
        block = canonical_lines("DATA_MODEL.md", heading, 0)
        assert "version" in block
        assert not [line for line in block if line.startswith("goal_version")]
        assert not [line for line in block if line.startswith("policy_version")]


def test_the_phase_zero_fields_did_not_survive_the_rewrite() -> None:
    """The fields the canonical set does not carry are gone (not renamed):
    ``user_id`` on all three, ``focus_goal_ids`` / ``weight_override`` on the
    focus, ``automatic_teaching_enabled`` on the policy."""

    names = {
        field.name
        for schema in (
            LearningGoalPortfolio,
            TeachingPolicyProfile,
            SessionFocus,
        )
        for field in dataclasses.fields(schema)
    }
    assert not names & {
        "user_id",
        "focus_goal_ids",
        "weight_override",
        "automatic_teaching_enabled",
    }


def test_the_user_owned_ids_are_user_ids() -> None:
    """The Local V1 keying convention, in the type system: §5.1 pins no owner
    column, so the portfolio and the policy are keyed by the user's own id
    (the ``user_profile_id`` precedent)."""

    assert (
        get_type_hints(LearningGoalPortfolio)["goal_portfolio_id"] is UserId
    )
    assert (
        get_type_hints(TeachingPolicyProfile)["teaching_policy_profile_id"]
        is UserId
    )
    for schema in (LearningGoalPortfolio, TeachingPolicyProfile):
        assert "user's own id" in (schema.__doc__ or "")


def test_the_policy_keeps_the_canonical_order_and_the_not_configured_default() -> None:
    """§5.1 declares ``mode`` before ``teaching_frequency`` while the eight
    unpinned columns default to "not configured": the object is keyword-only
    so both can hold without inventing a default *value* for the frequency
    (the declaration is positional-free by construction)."""

    assert TeachingPolicyProfile.__dataclass_params__.kw_only is True
    parameters = inspect.signature(TeachingPolicyProfile).parameters
    assert parameters["teaching_frequency"].default is inspect.Parameter.empty
    assert parameters["mode"].default is None


# -- ② the declared element shapes (§27) ------------------------------------


def test_the_goals_column_is_a_tuple_of_declared_goal_elements() -> None:
    hints = get_type_hints(LearningGoalPortfolio)
    assert hints["goals"] == tuple[LearningGoal, ...]
    assert [field.name for field in dataclasses.fields(LearningGoal)] == [
        "goal_id",
        "goal_modality",
        "description",
    ]
    assert "goals[]" in (LearningGoalPortfolio.__doc__ or "")


def test_modality_weights_is_goal_modality_to_float() -> None:
    assert (
        get_type_hints(LearningGoalPortfolio)["modality_weights"]
        == Mapping[GoalModality, float]
    )
    assert (
        get_type_hints(SessionFocus)["temporary_goal_weights"]
        == Mapping[GoalModality, float]
    )


def test_the_two_str_list_columns_are_str_tuples() -> None:
    hints = get_type_hints(LearningGoalPortfolio)
    assert hints["assessment_targets"] == tuple[str, ...]
    assert hints["register_style_goals"] == tuple[str, ...]


def test_the_time_columns_are_iso_strings_and_the_optional_one_is_optional() -> None:
    portfolio = get_type_hints(LearningGoalPortfolio)
    policy = get_type_hints(TeachingPolicyProfile)
    focus = get_type_hints(SessionFocus)
    assert portfolio["effective_from"] is str
    assert portfolio["updated_at"] is str
    assert policy["effective_from"] is str
    assert policy["updated_at"] is str
    assert focus["starts_at"] is str
    assert focus["expires_at"] == (str | None)
    # The store stamps updated_at; the caller's time columns default to
    # "not configured" (the empty string) and the open-ended window to None.
    assert dataclasses.fields(LearningGoalPortfolio)[-1].default == ""
    assert dataclasses.fields(TeachingPolicyProfile)[-1].default == ""
    assert dataclasses.fields(SessionFocus)[-1].default is None


def test_the_goal_modality_is_the_platform_vocabulary() -> None:
    """ARCHITECTURE_BASELINE §6's GoalModality line, read from the document."""

    line = canonical_lines(
        "ARCHITECTURE_BASELINE.md", "## 6. Modality Boundary", 0
    )[0]
    assert line.startswith("GoalModality:")
    words = tuple(
        word.strip() for word in line.split(":", 1)[1].split("|")
    )
    assert tuple(GoalModality.__members__) == words
    assert get_type_hints(LearningGoal)["goal_modality"] is GoalModality


def test_the_focus_names_a_target_not_a_goal() -> None:
    """§5.1 spells the column ``manual_focus_target?``: a manual focus names
    a teaching target (the vocabulary learning/teaching use), never a
    goal-modality word."""

    from elc.platform.types import TargetId

    assert get_type_hints(SessionFocus)["manual_focus_target"] == (
        TargetId | None
    )
    assert "None" in (SessionFocus.__doc__ or "")


# -- ③ the vocabulary honesty ------------------------------------------------


def test_the_eight_unpinned_columns_are_raw_str_or_none() -> None:
    hints = get_type_hints(TeachingPolicyProfile)
    fields = {field.name: field for field in dataclasses.fields(
        TeachingPolicyProfile
    )}
    for name in UNPINNED_POLICY_COLUMNS:
        assert hints[name] == (str | None), name
        assert fields[name].default is None, name


def test_teaching_frequency_is_declared_as_an_implementation_word_list() -> None:
    """§5.1 pins no value range for the column, so the enum is this repo's
    declaration and says so (which is also why migration 0011 puts no CHECK
    on the column)."""

    assert tuple(TeachingFrequency.__members__) == (
        "OFF",
        "MINIMAL",
        "BALANCED",
        "EAGER",
    )
    assert "Implementation-declared word list" in (
        TeachingFrequency.__doc__ or ""
    )
    assert (
        get_type_hints(TeachingPolicyProfile)["teaching_frequency"]
        is TeachingFrequency
    )


def _string_literal_container(node: ast.expr) -> bool:
    """True for a tuple / list / set / dict literal whose elements are all
    string constants (a dict is read through its keys *and* its values)."""

    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        elements: list[ast.expr | None] = list(node.elts)
    elif isinstance(node, ast.Dict):
        elements = [*node.keys, *node.values]
    else:
        return False
    return bool(elements) and all(
        isinstance(element, ast.Constant) and isinstance(element.value, str)
        for element in elements
        if element is not None
    )


def _module_level_word_lists(tree: ast.Module) -> list[str]:
    """Every module-level ALL_CAPS name bound to a string-literal container:
    the shape a declared vocabulary takes besides a ``StrEnum`` subclass."""

    names: list[str] = []
    for node in tree.body:
        targets: list[str] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            targets = [node.target.id]
            value = node.value
        if value is not None and _string_literal_container(value):
            names.extend(name for name in targets if name.isupper())
    return sorted(names)


def test_the_types_module_invents_no_further_vocabulary() -> None:
    """The vocabulary this module declares is enumerated here, in both of the
    shapes a word list can take in its source: a ``StrEnum`` subclass (Phase
    0's form) and a module-level ALL_CAPS name bound to a string-literal tuple
    / list / set / dict — ``POLICY_MODES = ("PREVIEW_V0", "SOCRATIC")`` is a
    word list just as much as an enum is, and a *new* one fails here rather
    than becoming the de-facto vocabulary of an unpinned column.

    The listed names are the module's whole vocabulary, and the distinction
    between them is the point: :class:`TeachingFrequency` is an
    **implementation declaration** (which is why migration 0011 puts no CHECK
    on its column) and :class:`DisclosureLevel` is this package's disclosure
    ladder, while P6-3's :class:`PlannerConstraintType` /
    :class:`PlannerConstraintScope` and their module-level restatements are
    **§9's own words**, enforced by migration 0013's CHECK and extracted from
    the document by tests/phase6/test_p6_3_types.py. P7-0 adds
    :class:`TargetLeg` — also an implementation declaration (§9 pins no
    vocabulary for the *reading* of its two optional target columns), and it
    names a shape of a pair, never a column. A further name — of either shape
    — is the case this pin exists for.
    """

    tree = ast.parse(TYPES_MODULE.read_text(encoding="utf-8"))
    enums = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "StrEnum"
            for base in node.bases
        )
    ]
    assert sorted(enums) == [
        "DisclosureLevel",
        "PlannerConstraintScope",
        "PlannerConstraintType",
        "TargetLeg",
        "TeachingFrequency",
    ]
    assert not [name for name in enums if "Modality" in name]
    assert _module_level_word_lists(tree) == [
        "PLANNER_CONSTRAINT_SCOPES",
        "PLANNER_CONSTRAINT_TYPES",
    ]
    for enum_type in (
        TeachingFrequency,
        DisclosureLevel,
        PlannerConstraintScope,
        PlannerConstraintType,
    ):
        assert issubclass(enum_type, StrEnum)
    assert tuple(DisclosureLevel.__members__) == ("MINIMAL", "FUNCTIONAL", "RICH")


# -- ④ the version-naming decision -------------------------------------------


def test_the_qualified_version_names_are_bound_by_the_platform_registry() -> None:
    """Why the qualified spelling: the registry binds a version *type* by
    field name, and three canonical objects would otherwise share the bare
    name ``version`` with three different types. **That binding is what makes
    the spelling an alias** (P7-0's word): the field name stands in for §5.1's
    column because the platform has no other way to bind the type, and the
    module docstring says so instead of claiming the two spellings are
    identical."""

    assert CANONICAL_OBJECTS["goal_portfolio"].schema is LearningGoalPortfolio
    assert CANONICAL_OBJECTS["goal_portfolio"].version_field == "goal_version"
    assert CANONICAL_OBJECTS["teaching_policy"].schema is TeachingPolicyProfile
    assert (
        CANONICAL_OBJECTS["teaching_policy"].version_field == "policy_version"
    )
    for field in ("goal_version", "policy_version"):
        assert PLATFORM_VERSION_FIELDS[field] is not None
    assert len({GoalVersion, PolicyVersion, ScheduleVersion}) == 3
    assert PLATFORM_VERSION_FIELDS["goal_version"] is GoalVersion
    assert PLATFORM_VERSION_FIELDS["policy_version"] is PolicyVersion


def test_the_module_docstring_records_the_alias_the_limitation_and_the_revisit(
) -> None:
    """D2, as P7-0 re-worded it: the rationale is written where the spelling
    is, it names the *alias* (with the canonical lines the alias's words come
    from) and the limitation (§5.1 says ``version``), and it names the
    condition that re-opens it."""

    docstring = user_config_types.__doc__ or ""
    for phrase in (
        "Version field naming",
        "DecisionCycle",
        "VERSION_FIELDS",
        "elc.platform.registry",
        "Known limitation",
        "Revisit condition",
        "*alias*",
        "word-for-word equal",
        "lines 175–177",
        "lines 330–332",
    ):
        assert phrase in docstring, phrase


def test_the_focus_carries_no_version_stamp_of_its_own() -> None:
    """§5.1 gives SessionFocus no ``version`` / ``revision`` column:
    ``base_goal_portfolio_version`` names the portfolio it was derived from,
    and the store's append-first rule is built on that absence."""

    fields = {field.name for field in dataclasses.fields(SessionFocus)}
    assert "version" not in fields
    assert "revision" not in fields
    assert get_type_hints(SessionFocus)[
        "base_goal_portfolio_version"
    ] is GoalVersion
    assert "No version stamp" in (SessionFocus.__doc__ or "")


def test_the_conversation_leg_is_a_conversation_id() -> None:
    assert get_type_hints(SessionFocus)["conversation_id"] is ConversationId
