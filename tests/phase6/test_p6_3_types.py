"""P6-3 ③.2 — the §9 object and its two vocabularies, read out of the document.

What is pinned here is exactly what the object claims:

- **§9's column block, extracted at test time** (``canonical_lines``) rather
  than typed twice: exactly nine lines, in the document's order, with the
  ``?`` suffixes stripped — and the dataclass field order is that order,
  word for word (``dataclasses.fields``).
- **§9's two word lists, extracted the same way**: the four
  ``constraint_type`` words and the three ``scope`` words, each compared with
  the module-level constant *and* with the enum's members — two shapes for one
  list, so a word list cannot hide in one of them and drift from the other
  (the P6-0 F-2 lesson).
- **the derived judgements are written down where they are decided**: the
  placement (R1 — §5.1's Owns list does not name this object, so nothing here
  may be quoted as canonical), the ``active`` exception (R6 — BF-03's
  "Gate 不偷偷修改用户约束" is why a transfer face exists), and the ``scope``
  reading (R7 — carried, never interpreted; ``THIS_SESSION`` has no column to
  bind to).

The migration's own face of the same pins (DDL column order, CHECK
vocabularies, nullability) lives in tests/phase6/test_p6_3_migration_0013.py.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum
from pathlib import Path

import pytest

from elc.platform.types import TargetId, TurnId
from elc.user_config import types as user_config_types
from elc.user_config.types import (
    PLANNER_CONSTRAINT_SCOPES,
    PLANNER_CONSTRAINT_TYPES,
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
)

from .conftest import canonical_lines

#: docs/DATA_MODEL.md §9's heading — the block the extraction reads.
SECTION_9 = "## 9. TeachingPreference / PlannerConstraint"

#: The nine canonical columns, as §9 spells them (``?`` suffixes included).
CANONICAL_COLUMNS = (
    "constraint_id",
    "target_type?",
    "target_id?",
    "constraint_type",
    "scope",
    "starts_at",
    "expires_at?",
    "created_from_turn_id?",
    "active",
)

#: The columns §9 spells with a ``?`` — the ones a dataclass may default.
OPTIONAL_COLUMNS = (
    "target_type",
    "target_id",
    "expires_at",
    "created_from_turn_id",
)


# -- ① the column block ------------------------------------------------------


def test_the_document_block_is_the_nine_columns() -> None:
    """§9's first fenced block, verbatim: nine lines, in this order."""

    block = canonical_lines("DATA_MODEL.md", SECTION_9, 0)
    assert block == CANONICAL_COLUMNS


def test_the_dataclass_field_order_is_the_document_order() -> None:
    """One declaration, two shapes: the document's block and the dataclass
    must agree line for line, ``?`` stripped."""

    block = canonical_lines("DATA_MODEL.md", SECTION_9, 0)
    assert [field.name for field in dataclasses.fields(PlannerConstraint)] == [
        line.rstrip("?") for line in block
    ]


def test_the_nine_fields_are_the_nine_canonical_ones() -> None:
    assert len(dataclasses.fields(PlannerConstraint)) == 9
    assert {field.name for field in dataclasses.fields(PlannerConstraint)} == {
        line.rstrip("?") for line in CANONICAL_COLUMNS
    }


@pytest.mark.parametrize(
    "name", [column.rstrip("?") for column in CANONICAL_COLUMNS]
)
def test_every_canonical_column_has_a_field(name: str) -> None:
    assert name in {
        field.name for field in dataclasses.fields(PlannerConstraint)
    }


# -- ② the four types --------------------------------------------------------


def test_the_types_block_is_the_document_block() -> None:
    """§9's ``Types`` block, extracted: the four words, in the block's order."""

    block = canonical_lines("DATA_MODEL.md", SECTION_9, 1)
    assert block == (
        "DO_NOT_AUTO_TEACH",
        "SUPPRESS_REVIEW",
        "JUST_CHAT",
        "MANUAL_FOCUS",
    )
    assert block == PLANNER_CONSTRAINT_TYPES


@pytest.mark.parametrize("word", PLANNER_CONSTRAINT_TYPES)
def test_every_type_word_is_in_both_shapes(word: str) -> None:
    """Constant and enum agree, member by member (and the member's *value* is
    the word — a StrEnum that renamed itself in transit would fail here)."""

    assert word in PLANNER_CONSTRAINT_TYPES
    assert PlannerConstraintType(word).value == word
    assert word in PlannerConstraintType.__members__


def test_the_type_enum_members_are_exactly_the_constant() -> None:
    assert [member.value for member in PlannerConstraintType] == list(
        PLANNER_CONSTRAINT_TYPES
    )


def test_the_type_enum_has_four_members_and_no_more() -> None:
    assert len(PlannerConstraintType.__members__) == 4


# -- ③ the three scopes ------------------------------------------------------


def test_the_scope_block_is_the_document_block() -> None:
    """§9's ``Scope 例如`` block, extracted: the three words, in order.

    §9 writes "例如" ("for example"), and the reading this cut takes is stated
    in the migration header: the three words are carried **exactly as given**
    — the schema freezes them, and a fourth word is a canonical revision
    rather than an implementation choice.
    """

    block = canonical_lines("DATA_MODEL.md", SECTION_9, 2)
    assert block == (
        "THIS_SESSION",
        "UNTIL_DATE",
        "UNTIL_USER_REENABLES",
    )
    assert block == PLANNER_CONSTRAINT_SCOPES


@pytest.mark.parametrize("word", PLANNER_CONSTRAINT_SCOPES)
def test_every_scope_word_is_in_both_shapes(word: str) -> None:
    assert word in PLANNER_CONSTRAINT_SCOPES
    assert PlannerConstraintScope(word).value == word
    assert word in PlannerConstraintScope.__members__


def test_the_scope_enum_members_are_exactly_the_constant() -> None:
    assert [member.value for member in PlannerConstraintScope] == list(
        PLANNER_CONSTRAINT_SCOPES
    )


def test_the_scope_enum_has_three_members_and_no_more() -> None:
    assert len(PlannerConstraintScope.__members__) == 3


def test_the_two_lists_share_no_word() -> None:
    """A constraint type is never a scope: the two vocabularies are separate
    (§9 keeps them in separate blocks, and mixing them would make
    ``scope='JUST_CHAT'`` a value some reader might accept)."""

    assert not set(PLANNER_CONSTRAINT_TYPES) & set(PLANNER_CONSTRAINT_SCOPES)


@pytest.mark.parametrize(
    "enum_type",
    [PlannerConstraintType, PlannerConstraintScope],
)
def test_the_two_enums_are_string_ones(enum_type: type[StrEnum]) -> None:
    """A ``str`` subclass, so a value survives JSON/durable round trips as the
    word itself (the repo-wide StrEnum convention)."""

    assert issubclass(enum_type, str)
    for member in enum_type:
        assert isinstance(member, str)
        assert member == member.value


# -- ④ the dataclass shape ---------------------------------------------------


@pytest.mark.parametrize("name", OPTIONAL_COLUMNS)
def test_the_optional_columns_default_to_none(name: str) -> None:
    """The four ``?`` columns are the ones with a default, and the default is
    ``None`` = "not declared" (never a fabricated value)."""

    field = {f.name: f for f in dataclasses.fields(PlannerConstraint)}[name]
    assert field.default is None


def test_the_required_columns_have_no_default() -> None:
    """``constraint_type`` / ``scope`` / ``starts_at`` / ``active`` are the
    columns §9 does not mark ``?``: a caller must declare them."""

    for name in ("constraint_type", "scope", "starts_at", "active"):
        field = {f.name: f for f in dataclasses.fields(PlannerConstraint)}[name]
        assert field.default is dataclasses.MISSING, name


def test_the_two_target_columns_are_honestly_optional() -> None:
    """§9's two ``?`` target columns: ``target_type`` is a bare ``str`` (the
    platform declares no ``TargetType``, the ScheduleItem precedent) and
    ``target_id`` is the platform ``TargetId``."""

    fields = {f.name: f for f in dataclasses.fields(PlannerConstraint)}
    assert fields["target_type"].type in ("str | None", str | None)
    assert fields["target_id"].default is None
    instance = PlannerConstraint(
        constraint_id="pc-x",
        constraint_type=PlannerConstraintType.JUST_CHAT,
        scope=PlannerConstraintScope.THIS_SESSION,
        starts_at="2026-09-22T09:00:00+00:00",
        active=True,
    )
    assert instance.target_type is None and instance.target_id is None


def test_the_target_and_turn_fields_use_the_platform_types() -> None:
    """Where a platform type exists it is used: ``target_id`` is a
    ``TargetId`` and ``created_from_turn_id`` a ``TurnId`` (the annotation is
    the type, so a caller cannot hand a plain string to a type checker
    silently)."""

    fields = {f.name: f for f in dataclasses.fields(PlannerConstraint)}
    assert fields["target_id"].type == "TargetId | None"
    assert fields["created_from_turn_id"].type == "TurnId | None"
    instance = PlannerConstraint(
        constraint_id="pc-x",
        target_type="RESOURCE",
        target_id=TargetId("res-hedge-i-think"),
        constraint_type=PlannerConstraintType.SUPPRESS_REVIEW,
        scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
        starts_at="2026-09-22T09:00:00+00:00",
        created_from_turn_id=TurnId("t-1"),
        active=False,
    )
    assert str(instance.target_id) == "res-hedge-i-think"
    assert str(instance.created_from_turn_id) == "t-1"


def test_the_object_is_frozen_and_keyword_only() -> None:
    """Configuration truth: immutable once built (frozen), and keyword-only
    because §9's two ``?`` columns precede the required
    ``constraint_type`` — a defaulted field cannot precede a required one in
    a positional dataclass (the TeachingPolicyProfile / ScheduleItem
    precedent)."""

    assert dataclasses.fields(PlannerConstraint)[0].kw_only is True
    built = PlannerConstraint(
        constraint_id="pc-x",
        constraint_type=PlannerConstraintType.JUST_CHAT,
        scope=PlannerConstraintScope.THIS_SESSION,
        starts_at="2026-09-22T09:00:00+00:00",
        active=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        built.active = False


def test_the_object_compares_by_value() -> None:
    """Two constructions of the same content are the same value: the store's
    idempotent-replay rule leans on exactly this."""

    first = PlannerConstraint(
        constraint_id="pc-x",
        constraint_type=PlannerConstraintType.DO_NOT_AUTO_TEACH,
        scope=PlannerConstraintScope.UNTIL_DATE,
        starts_at="2026-09-22T09:00:00+00:00",
        expires_at="2026-09-24T09:00:00+00:00",
        active=True,
    )
    second = PlannerConstraint(
        constraint_id="pc-x",
        constraint_type=PlannerConstraintType.DO_NOT_AUTO_TEACH,
        scope=PlannerConstraintScope.UNTIL_DATE,
        starts_at="2026-09-22T09:00:00+00:00",
        expires_at="2026-09-24T09:00:00+00:00",
        active=True,
    )
    assert first == second
    assert first != dataclasses.replace(first, active=False)


# -- ⑤ the derived judgements, written where they are decided ----------------


def _flat(text: str) -> str:
    """The text with wrapping collapsed, so a phrase pin does not fail on
    where the docstring happens to break a line (the p6-1 lesson: a scan must
    look for the *claim*, not for one editor's line breaks)."""

    return " ".join(text.split())


def test_the_module_docstring_registers_the_placement() -> None:
    """R1: §5.1's Owns list does not name this object, so the placement in
    this package is a derived judgement and the docstring must say so — the
    one thing this cut may not do is present it as canonical text."""

    docstring = _flat(user_config_types.__doc__ or "")
    for phrase in (
        "§9",
        "derived judgement",
        "§5.1's Owns list",
        "18.1",
        "TRUSTED_AUTHORITY",
        "not a quoted one",
    ):
        assert phrase in docstring, phrase


def test_the_object_docstring_registers_the_active_exception() -> None:
    """R6: §9 has no version column, so content is append-first — except the
    ``active`` flag, whose one movable column is the BF-03 rule."""

    docstring = _flat(PlannerConstraint.__doc__ or "")
    for phrase in (
        "No version column",
        "CONFLICT",
        "one** exception",
        "set_planner_constraint_active",
        "BF-03",
        "Gate 不偷偷修改用户约束",
        "UNTIL_USER_REENABLES",
    ):
        assert phrase in docstring, phrase


def test_the_object_docstring_registers_the_scope_reading() -> None:
    """R7: the three words are carried and none is interpreted — and the
    revisit condition names what would have to change."""

    docstring = _flat(PlannerConstraint.__doc__ or "")
    for phrase in (
        "Scope is carried, never interpreted",
        "THIS_SESSION",
        "no conversation column",
        "Revisit condition",
    ):
        assert phrase in docstring, phrase


def test_the_object_docstring_names_the_instant_rule() -> None:
    """The window columns are ISO-8601 instants with an offset, compared as
    instants — never assumed to be UTC when the offset is missing."""

    docstring = _flat(PlannerConstraint.__doc__ or "")
    for phrase in (
        "ISO-8601",
        "UTC offset",
        "compare them as instants",
        "naive",
    ):
        assert phrase in docstring, phrase


def test_the_type_enum_docstring_says_it_carries_no_behaviour() -> None:
    """A vocabulary is not a policy: nothing in this cut consumes a
    constraint, and the docstring must not imply otherwise."""

    docstring = _flat(PlannerConstraintType.__doc__ or "")
    assert "carries no behaviour" in docstring
    assert "CHECK" in docstring
    assert "TARGET_SUPPRESSED" in docstring


def test_the_scope_closing_is_not_presented_as_canonical() -> None:
    """L-1: §9 writes ``Scope 例如``, so the three words are the document's
    *example* while **closing** the set is this cut's schema choice.

    The Scope docstring must keep the distinction (and say what extending it
    costs), and the constant's own comment must keep the ``例如`` reading in
    front of a reader of the module — the two places a future edit could
    quietly re-promote the closure to canonical text.
    """

    docstring = _flat(PlannerConstraintScope.__doc__ or "")
    for phrase in (
        "from §9's example block",
        "does not hold the canonical position the Types list holds",
        "closing** the set is this cut's schema choice",
        "a fourth scope word extends migration 0013's CHECK",
    ):
        assert phrase in docstring, phrase
    source = _flat(
        Path(user_config_types.__file__).read_text(encoding="utf-8")
    )
    assert "Scope 例如" in source
    assert "PLANNER_CONSTRAINT_SCOPES" in source
    # The Types list keeps the canonical contrast it really has (a pinned
    # list), so the pair reads as a distinction rather than one blanket rule.
    assert "pins exactly" in _flat(PlannerConstraintType.__doc__ or "")
