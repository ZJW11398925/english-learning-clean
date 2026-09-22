"""P6-1 ②② — the two §5.2 objects: canonical column sets, the vocabulary
replacement, and the two derived readings.

docs/DATA_MODEL.md §5.2 is the authority these tests read: both column lists
below are extracted from the document at test time and compared, in order,
with the dataclass field list — so a drifted column (a renamed one, an extra
one, a missing one) fails here instead of becoming the repo's de-facto schema.

Three further claims of this slice are pinned here, each because it is a
*reading* rather than a quotation:

- **the vocabulary replacement** — the four canonical ``review_state`` words
  are the enum's members, the Phase 0 skeleton's five words survive nowhere as
  code (they appear only in the prose that records their deletion), and the
  one implementation-declared list (``SpacingStage``) says so;
- **R8** — ``version`` keeps §5.2's bare spelling (the registry binds no
  ``version_field`` for it, unlike the qualified §5.1 pair);
- **R4 / R5** — ``review_urgency`` and ``event_type`` are carried raw with no
  vocabulary, and the module says which phase owns each reading.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from enum import StrEnum
from pathlib import Path
from typing import get_type_hints

import pytest

from elc.platform.registry import CANONICAL_OBJECTS
from elc.platform.types import (
    EvidenceGroupId,
    EvidenceModality,
    MomentId,
    ScheduleVersion,
    TargetId,
    TurnId,
)
from elc.scheduler import types as scheduler_types
from elc.scheduler.types import (
    REVIEW_STATES,
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    ScheduleView,
    SpacingStage,
)
from tests.conftest import REPO_ROOT, SRC_ROOT

from .conftest import canonical_lines

TYPES_MODULE = Path(scheduler_types.__file__)

#: The test modules allowed to spell a deleted word **as code**, each because
#: it must name the word to assert its refusal (the enumeration is the point:
#: any other file that spells one is residue, and ``src/`` has no exemption at
#: all):
#:  - this pin spells both words to search for them;
#:  - test_p6_1_store.py writes ``'LAPSED'`` as a raw SQL value to prove the
#:    schema refuses a fifth state;
#:  - test_p6_1_invariants.py asks ``hasattr(ReviewState, "SUSPENDED")`` to
#:    prove the deleted member is not there.
RESIDUE_SCAN_EXEMPT = (
    "test_p6_1_types.py",
    "test_p6_1_store.py",
    "test_p6_1_invariants.py",
)

#: The Phase 0 skeleton's five words — the vocabulary this slice replaced.
SKELETON_WORDS = ("NEW", "LEARNING", "REVIEW", "LAPSED", "SUSPENDED")

#: The two of them that exist **nowhere else** in this repository's
#: vocabulary (grepped, not assumed): ``LAPSED`` and ``SUSPENDED``. They are
#: what a whole-tree *code* residue scan can use, because an occurrence of
#: one is an occurrence of the deleted word and nothing else. ``NEW`` /
#: ``LEARNING`` / ``REVIEW`` are not usable that way — ``REVIEW`` is a
#: canonical teaching ``target_mode`` (migration 0007's CHECK) and
#: ``learning`` names a bounded context — so those three are pinned through
#: :class:`ReviewState`'s own members and through every ``ReviewState.<x>``
#: use site instead (the two pins below).
SKELETON_ONLY_WORDS = ("LAPSED", "SUSPENDED")

#: The ``?`` columns plus ``review_urgency`` (R4: ``float | None``, raw).
OPTIONAL_FIELDS = (
    "review_urgency",
    "next_review_window_start",
    "next_review_window_end",
    "spacing_stage",
)

SCHEMAS = {"### ScheduleItem": ScheduleItem, "### ReviewEvent": ReviewEvent}


def _canonical_columns(heading: str) -> list[str]:
    """§5.2's column block, read out of the document (never typed twice)."""

    columns = [
        line.rstrip("?").removesuffix("[]")
        for line in canonical_lines("DATA_MODEL.md", heading, 0)
    ]
    assert columns, f"{heading} yielded no columns"
    return columns


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


def _prose_stripped(source: str) -> str:
    """The source with every docstring and comment removed — what is left is
    code, where a vocabulary residue would actually mean something."""

    tree = ast.parse(source)
    stripped = source
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        docstring = ast.get_docstring(node, clean=False)
        if docstring:
            stripped = stripped.replace(docstring, "")
    return re.sub(r"#[^\n]*", "", stripped)


# -- ① the column sets, word for word ---------------------------------------


@pytest.mark.parametrize("heading", sorted(SCHEMAS))
def test_the_column_set_is_the_canonical_block_word_for_word(heading) -> None:
    fields = [field.name for field in dataclasses.fields(SCHEMAS[heading])]
    assert fields == _canonical_columns(heading)


def test_the_two_column_counts_are_the_canonical_ones() -> None:
    assert len(dataclasses.fields(ScheduleItem)) == 12
    assert len(dataclasses.fields(ReviewEvent)) == 8


def test_the_phase_zero_fields_did_not_survive_the_rewrite() -> None:
    """The Phase 0 skeleton's record carried ``state`` and a target-only key;
    §5.2's columns are the authority, so the object it described is replaced
    (``ReviewStateRecord`` is gone) rather than renamed."""

    assert not hasattr(scheduler_types, "ReviewStateRecord")
    names = {field.name for field in dataclasses.fields(ScheduleItem)}
    assert "state" not in names
    assert "user_id" not in names
    assert "retrieved" not in names


def test_the_optional_columns_are_optional_and_default_to_not_configured() -> None:
    hints = get_type_hints(ScheduleItem)
    fields = {field.name: field for field in dataclasses.fields(ScheduleItem)}
    assert hints["review_urgency"] == (float | None)
    assert hints["next_review_window_start"] == (str | None)
    assert hints["next_review_window_end"] == (str | None)
    assert hints["spacing_stage"] == (SpacingStage | None)
    for name in OPTIONAL_FIELDS:
        assert fields[name].default is None, name


def test_the_required_columns_are_the_canonical_ones() -> None:
    hints = get_type_hints(ScheduleItem)
    assert hints["schedule_item_id"] is str
    assert hints["target_id"] is TargetId
    assert hints["evidence_modality"] is EvidenceModality
    assert hints["review_state"] is ReviewState
    assert hints["source_learning_watermark"] is str
    assert hints["version"] is ScheduleVersion
    assert hints["updated_at"] is str


def test_target_type_is_a_plain_str_because_the_platform_declares_no_type() -> None:
    """§5.2 names the column; migration 0012 enforces the two canonical words;
    the platform has no ``TargetType`` to type it with (the
    ``LearnerTargetStateRecord.target_type`` precedent), and the docstring
    says so rather than leaving the choice unstated."""

    assert get_type_hints(ScheduleItem)["target_type"] is str
    assert "TargetType" in (ScheduleItem.__doc__ or "")
    assert "LearnerTargetStateRecord" in (ScheduleItem.__doc__ or "")


def test_the_event_columns_are_the_canonical_ones() -> None:
    hints = get_type_hints(ReviewEvent)
    assert hints["review_event_id"] is str
    assert hints["schedule_item_id"] is str
    assert hints["teaching_moment_id"] == (MomentId | None)
    assert hints["source_turn_id"] == (TurnId | None)
    assert hints["event_type"] is str
    assert hints["engaged"] is bool
    assert hints["evidence_group_id"] == (EvidenceGroupId | None)
    assert hints["created_at"] is str


def test_the_fields_are_keyword_only_so_the_canonical_order_holds() -> None:
    """§5.2 declares optional columns before required ones; a defaulted field
    cannot precede a required one positionally, so both objects are
    keyword-only (the ``TeachingPolicyProfile`` precedent) — which is what
    lets the canonical order and the "not configured" default coexist."""

    assert ScheduleItem.__dataclass_params__.kw_only is True
    assert ReviewEvent.__dataclass_params__.kw_only is True
    parameters = inspect.signature(ScheduleItem).parameters
    assert parameters["review_urgency"].default is None
    assert parameters["source_learning_watermark"].default is inspect.Parameter.empty


def test_the_event_optional_columns_default_to_none() -> None:
    fields = {field.name: field for field in dataclasses.fields(ReviewEvent)}
    for name in (
        "teaching_moment_id",
        "source_turn_id",
        "evidence_group_id",
        "created_at",
    ):
        assert fields[name].default is None or fields[name].default == "", name
    assert fields["event_type"].default is dataclasses.MISSING
    assert fields["engaged"].default is dataclasses.MISSING


# -- ② the vocabulary replacement --------------------------------------------


def test_the_review_state_vocabulary_is_the_canonical_block() -> None:
    words = canonical_lines("DATA_MODEL.md", "### ScheduleItem", 1)
    assert REVIEW_STATES == words
    assert tuple(ReviewState.__members__) == words
    for word in words:
        assert ReviewState(word).value == word


def test_the_skeleton_five_words_survive_nowhere_as_code() -> None:
    """The Phase 0 vocabulary is deleted, not renamed.

    Two scopes, deliberately different:

    - **``src/`` carries no exemption at all** — the product's source never
      spells a deleted word as code (a docstring may, because the deletion is
      *recorded* there, and that is the one place it belongs);
    - **``tests/`` may spell one only to assert its refusal**, and the files
      allowed to do that are enumerated below — the enumeration is the point,
      because any other file that spells one is the residue this pin is for.

    The scan uses the two words that exist nowhere else in this repository
    (:data:`SKELETON_ONLY_WORDS`); the other three are pinned by the enum's
    members and by every use site, because ``REVIEW`` / ``LEARNING`` are
    canonical vocabulary of other domains and a whole-tree grep for them would
    be noise rather than evidence.
    """

    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        code = _prose_stripped(path.read_text(encoding="utf-8"))
        offenders.extend(
            _spelled_deleted_words(code, f"src/{path.name}", ())
        )
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        code = _prose_stripped(path.read_text(encoding="utf-8"))
        offenders.extend(
            _spelled_deleted_words(code, f"tests/{path.name}", RESIDUE_SCAN_EXEMPT)
        )
    assert not offenders, offenders


def _spelled_deleted_words(
    code: str, label: str, exempt: tuple[str, ...]
) -> list[str]:
    if Path(label).name in exempt:
        return []
    found: list[str] = []
    for word in SKELETON_ONLY_WORDS:
        if re.search(rf"\b{word}\b", code):
            found.append(f"{label}: {word}")
        if f'"{word}"' in code or f"'{word}'" in code:
            found.append(f"{label}: {word!r} literal")
    return found


def test_no_other_class_declares_a_skeleton_state_word() -> None:
    """A second home for the old vocabulary (a different enum, a module-level
    tuple) would be a rename in disguise."""

    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            members = {
                target.id
                for statement in node.body
                if isinstance(statement, ast.Assign)
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
            assert not members & set(SKELETON_ONLY_WORDS), (
                f"{path.name}:{node.name}"
            )


def test_no_module_level_constant_holds_a_skeleton_state_word() -> None:
    """The same rule one scope out: no ALL_CAPS constant in the tree binds the
    deleted words as a tuple/list (the shape a renamed vocabulary would
    take)."""

    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _module_level_word_lists(tree):
            node = next(
                statement
                for statement in tree.body
                if name
                in {
                    target.id
                    for target in getattr(statement, "targets", [])
                    if isinstance(target, ast.Name)
                }
                or (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == name
                )
            )
            value = node.value
            elements = [
                element.value
                for element in ast.walk(value)
                if isinstance(element, ast.Constant)
                and isinstance(element.value, str)
            ]
            assert not set(elements) & set(SKELETON_ONLY_WORDS), (
                f"{path.name}:{name}"
            )


def test_every_review_state_use_names_a_canonical_member() -> None:
    """Every ``ReviewState.<member>`` reached anywhere in the tree is one of
    the four: no call site was left pointing at a deleted word."""

    canonical = set(ReviewState.__members__)
    for root in (SRC_ROOT, REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Attribute):
                    continue
                if node.attr.startswith("__"):
                    continue
                owner = node.value
                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "ReviewState"
                ):
                    assert node.attr in canonical, f"{path.name}: {node.attr}"


def test_the_types_module_invents_no_further_vocabulary() -> None:
    """The only word lists this module declares are the canonical
    ``review_state`` block (as :data:`REVIEW_STATES` and the enum that
    restates it) and the implementation-declared ``SpacingStage`` — no third
    enum, no second ALL_CAPS constant, and nothing for ``event_type``."""

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
    assert sorted(enums) == ["ReviewState", "SpacingStage"]
    assert _module_level_word_lists(tree) == ["REVIEW_STATES"]
    assert all(
        issubclass(schema, StrEnum) for schema in (ReviewState, SpacingStage)
    )


def test_spacing_stage_is_declared_as_an_implementation_word_list() -> None:
    """§5.2 spells ``spacing_stage?`` and pins no value range: the five words
    are this repository's declaration, they carry no schema CHECK, ``None``
    means 未分阶, and this slice implements no transition."""

    assert tuple(SpacingStage.__members__) == (
        "STAGE_0",
        "STAGE_1",
        "STAGE_2",
        "STAGE_3",
        "STAGE_4",
    )
    docstring = SpacingStage.__doc__ or ""
    for phrase in (
        "implementation-declared word list",
        "未分阶",
        "no transition",
        "Revisit condition",
    ):
        assert phrase in docstring, phrase


# -- ③ the derived readings (R4 / R5 / R8) -----------------------------------


def test_review_urgency_is_carried_raw_with_no_declared_range() -> None:
    """R4: §5.2 names the column and pins neither type nor range, so this
    slice stores ``float | None`` verbatim — and the docstring names BF-02's
    numeric map as a *Planner* feature assembly rather than this column's
    semantics."""

    hints = get_type_hints(ScheduleItem)
    assert hints["review_urgency"] == (float | None)
    docstring = ScheduleItem.__doc__ or ""
    for phrase in ("R4", "Planner feature assembly", "not configured"):
        assert phrase in docstring, phrase
    assert "0.25" in docstring and "0.75" in docstring
    assert "R8" in docstring and "version" in docstring


def test_the_version_field_keeps_the_bare_canonical_spelling() -> None:
    """R8: §5.2 says ``version`` on ScheduleItem, so the field does too, and
    the registry binds no ``version_field`` for the object (the qualified
    ``schedule_version`` is ScheduleView's field, not this one's)."""

    assert "version" in {
        field.name for field in dataclasses.fields(ScheduleItem)
    }
    assert get_type_hints(ScheduleItem)["version"] is ScheduleVersion
    entry = CANONICAL_OBJECTS["schedule_item"]
    assert entry.version_field is None
    assert entry.schema is ScheduleItem
    view = CANONICAL_OBJECTS["schedule_view"]
    assert view.version_field == "schedule_version"
    assert view.schema is ScheduleView


def test_event_type_carries_no_vocabulary_and_says_which_phase_owns_it() -> None:
    """R5: neither the canonical documents nor behavioral_baselines declare a
    word for ``event_type``, so this slice declares none either — the first
    consumer that must branch on a value is p6-2's history read."""

    assert get_type_hints(ReviewEvent)["event_type"] is str
    docstring = ReviewEvent.__doc__ or ""
    for phrase in ("R5", "no vocabulary", "p6-2"):
        assert phrase in docstring, phrase
    assert "EVENT_TYPES" not in TYPES_MODULE.read_text(encoding="utf-8")


def test_the_event_is_append_first_in_its_docstring() -> None:
    docstring = ReviewEvent.__doc__ or ""
    for phrase in ("append-first", "no unique index", "schedule_item_id"):
        assert phrase in docstring, phrase


def test_the_view_carries_the_production_shape_and_its_membership_rule() -> None:
    """P6-1 declared the shape; P6-2 produces it. What is pinned here is what a
    production answers with: the model stamp, the instant it was classified at,
    the three state buckets (each a tuple of ``ScheduleItem`` defaulting to
    empty), and the two sentences a consumer needs — ``NOT_SCHEDULED`` is in no
    bucket, and each bucket is ordered by ``(next_review_window_start,
    schedule_item_id)``."""

    hints = get_type_hints(ScheduleView)
    assert hints["schedule_version"] is ScheduleVersion
    assert hints["as_of"] is str
    field_names = [field.name for field in dataclasses.fields(ScheduleView)]
    assert field_names == [
        "schedule_version",
        "as_of",
        "due_items",
        "overdue_items",
        "upcoming",
    ]
    assert dataclasses.fields(ScheduleView)[field_names.index("as_of")].default \
        is dataclasses.MISSING
    for bucket in ("due_items", "overdue_items", "upcoming"):
        assert hints[bucket] == tuple[ScheduleItem, ...], bucket
        assert dataclasses.fields(ScheduleView)[
            field_names.index(bucket)
        ].default == ()
    docstring = ScheduleView.__doc__ or ""
    for phrase in (
        "NOT_SCHEDULED",
        "none of them",
        "next_review_window_start",
        "schedule_item_id",
        "P6-2",
    ):
        assert phrase in docstring, phrase


def test_the_registry_carries_the_two_objects_and_the_view() -> None:
    scheduler_entries = {
        key: entry
        for key, entry in CANONICAL_OBJECTS.items()
        if entry.owner == "scheduler"
    }
    assert set(scheduler_entries) == {
        "schedule_item",
        "review_event",
        "schedule_view",
    }
    assert scheduler_entries["review_event"].schema is ReviewEvent
    assert scheduler_entries["review_event"].version_field is None
    assert "ReviewStateRecord" not in {
        entry.schema.__name__ for entry in CANONICAL_OBJECTS.values()
    }


def test_the_module_docstring_cites_the_canonical_authority() -> None:
    docstring = scheduler_types.__doc__ or ""
    for phrase in (
        "DOMAIN_MODEL.md §9",
        "D-INV-009",
        "§5.2",
        "P6-1",
    ):
        assert phrase in docstring, phrase
