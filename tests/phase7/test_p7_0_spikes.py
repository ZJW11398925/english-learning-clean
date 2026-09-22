"""P7-0 ④ — the two spikes, as pins.

**The alias spike.** ``version`` vs ``goal_version`` / ``policy_version`` was
raised as a drift. The evidence says the *problem is real but the description
was not*: the canonical documents use the qualified spellings themselves
(docs/DATA_MODEL.md lines 175–177, docs/STATE_MACHINES.md lines 330–332), the
implementation's field name is a **binding** the platform registry needs, and
the two are therefore an alias pair — not "the same word twice". The pins below
hold the three phase-6 statements to that wording, and the retired phrasing
("word for word" / a claim of equality) may not come back: the canonical
revision, if it is ever made, is the canonical documents' to make, and this
repository only states the question.

**The spacing spike.** §5.2's ``ReviewEvent`` carries ``engaged`` and
``created_at`` and nothing else the ladder reads, so what an event *does* is
decidable from those two fields alone — four roles, one table, and the failures
(the "reviewed and it did not engage" case) have exactly one spelling. The
table is frozen where the ladder lives so the first producer of a review event
reads it before writing one.
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

from elc.platform.registry import CANONICAL_OBJECTS
from elc.scheduler.spacing import (
    SCHEDULER_MODEL_VERSION,
    SPACING_STAGES,
    ReviewEventRole,
    anchor_of,
    role_of,
    stage_from_history,
)
from elc.scheduler.types import ReviewState
from elc.user_config import types as user_config_types
from elc.user_config.types import (
    LearningGoalPortfolio,
    SessionFocus,
    TeachingPolicyProfile,
)

from .conftest import (
    DAY_ONE,
    canonical_lines,
    document_text,
    review_event,
    source_text,
)

# -- the alias spike ---------------------------------------------------------

#: P7-0's re-wording of the three phase-6 statements, recorded here so the
#: change is machine-checkable rather than a matter of memory.
ALIAS_PINS_BEFORE_AFTER = {
    # before -> after
    "test_the_column_set_is_the_canonical_block_word_for_word": (
        "test_the_column_set_is_the_canonical_block_with_the_declared_alias"
    ),
    "test_the_module_docstring_records_the_limitation_and_the_revisit": (
        "test_the_module_docstring_records_the_alias_the_limitation_and_"
        "the_revisit"
    ),
}
PHASE6_TYPES_TESTS = "tests/phase6/test_p6_0_types.py"


def test_the_canonical_blocks_spell_a_bare_version() -> None:
    """§5.1's three blocks, read out of the document: ``version`` is the
    canonical column name, and the qualified spellings are not in them."""

    for heading in ("### LearningGoalPortfolio", "### TeachingPolicyProfile"):
        block = canonical_lines("DATA_MODEL.md", heading, 0)
        assert "version" in block
        assert not [line for line in block if line.startswith("goal_version")]


def test_the_alias_word_is_the_documents_own() -> None:
    """The alias's vocabulary is quoted, not invented: both canonical blocks
    that name the qualified spellings list all three, in one place each."""

    data_model = document_text("DATA_MODEL.md")
    state_machines = document_text("STATE_MACHINES.md")
    expected = ("goal_version", "schedule_version", "policy_version")
    assert tuple(line.strip() for line in data_model[174:177]) == expected
    assert tuple(line.strip() for line in state_machines[329:332]) == expected


def test_the_module_records_the_alias_and_forbids_the_verbatim_claim() -> None:
    docstring = user_config_types.__doc__ or ""
    for phrase in (
        "The qualified spelling is an *alias*",
        "word-for-word equal",
        "lines 175–177",
        "lines 330–332",
        "Known limitation",
        "Revisit condition",
    ):
        assert phrase in docstring, phrase


def test_the_retired_phrasing_is_gone_from_the_three_pins() -> None:
    """The before/after record, as a pin: the phase-6 statement that used to
    say "word for word" now says "with the declared alias", the docstring pin
    now requires the alias phrases, and the retired *claim* (a name or an
    assertion that says the two spellings are identical) is gone from that
    file. The phrase itself survives in one place only — inside the sentence
    that records its retirement."""

    source = source_text(PHASE6_TYPES_TESTS)
    for before, after in ALIAS_PINS_BEFORE_AFTER.items():
        assert f"def {before}(" not in source, before
        assert f"def {after}(" in source, after
    assert "word_for_word" not in source
    assert "records_the_alias" in source
    assert source.count("word for word") == 1
    assert "used to say" in source


def test_the_alias_is_still_bound_by_the_platform() -> None:
    """The reason the alias exists, unchanged by this cut: the registry binds
    a version type per object, and the bare word could not carry three."""

    from elc.platform.types import VERSION_FIELDS

    assert CANONICAL_OBJECTS["goal_portfolio"].version_field == "goal_version"
    assert CANONICAL_OBJECTS["teaching_policy"].version_field == "policy_version"
    assert VERSION_FIELDS["goal_version"] is not None
    assert VERSION_FIELDS["policy_version"] is not None


def test_the_alias_touches_one_column_and_no_other() -> None:
    """The scope of the reading: exactly one field per object is a translated
    line, and the rest is the canonical block's own text (the phase-6 column
    pin proves the whole list; this one proves the *difference* is one).

    The block's spellings carry the canonical ``?`` / ``[]`` decorations, so
    they are normalized the way the phase-6 reader normalizes them.
    """

    for schema, field, heading in (
        (LearningGoalPortfolio, "goal_version", "### LearningGoalPortfolio"),
        (TeachingPolicyProfile, "policy_version", "### TeachingPolicyProfile"),
    ):
        names = [entry.name for entry in dataclasses.fields(schema)]
        assert field in names
        canonical = [
            line.rstrip("?").removesuffix("[]")
            for line in canonical_lines("DATA_MODEL.md", heading, 0)
        ]
        assert len(names) == len(canonical)
        assert [name for name in names if name not in canonical] == [field]
        assert [name for name in canonical if name not in names] == ["version"]
    focus_names = [entry.name for entry in dataclasses.fields(SessionFocus)]
    focus_canonical = [
        line.rstrip("?").removesuffix("[]")
        for line in canonical_lines("DATA_MODEL.md", "### SessionFocus", 0)
    ]
    assert [name for name in focus_names if name not in focus_canonical] == []


def test_the_alias_reading_offers_the_canonical_question_and_edits_nothing() -> None:
    """The spike's edge: the conclusion is *not* "change the canonical set".
    The documents are read-only here, and the module says the revision is not
    this repository's to make."""

    docstring = user_config_types.__doc__ or ""
    assert "That revision is not" in docstring
    assert "canonical document" in docstring


# -- the spacing spike -------------------------------------------------------


def test_the_freezes_four_roles_are_the_four_shapes() -> None:
    assert tuple(ReviewEventRole.__members__) == (
        "ANCHOR_AND_ADVANCE",
        "ANCHOR_ONLY",
        "ADVANCE_ONLY",
        "HISTORY_ONLY",
    )
    assert set(ReviewEventRole) & set(ReviewState) == set()


@pytest.mark.parametrize(
    ("engaged", "created_at", "role", "anchors", "advances"),
    [
        (True, DAY_ONE, ReviewEventRole.ANCHOR_AND_ADVANCE, True, True),
        (False, DAY_ONE, ReviewEventRole.ANCHOR_ONLY, True, False),
        (True, "", ReviewEventRole.ADVANCE_ONLY, False, True),
        (False, "", ReviewEventRole.HISTORY_ONLY, False, False),
    ],
)
def test_each_role_drives_the_ladder_exactly_as_the_table_says(
    engaged: bool,
    created_at: str,
    role: ReviewEventRole,
    anchors: bool,
    advances: bool,
) -> None:
    """The table is not prose: every row is driven through the two functions
    it describes, so a change to either one that changed what an event does
    would fail here."""

    event = review_event(
        "re-role", engaged=engaged, created_at=created_at
    )
    assert role_of(event) is role

    empty_freshness = _NoStrongRetrieval()
    anchored = anchor_of(empty_freshness, (event,))
    assert (anchored.value is not None) is anchors, anchored
    assert (stage_from_history((event,)) != stage_from_history(())) is advances


class _NoStrongRetrieval:
    """The freshness port with no strong retrieval: every anchor in these pins
    comes from the event, never from the Learning side."""

    last_strong_retrieval_at: str | None = None


def test_a_review_that_did_not_engage_is_anchored_and_does_not_advance() -> None:
    """The failure case, spelled the only way §5.2 can spell it: there is no
    outcome column, so "it happened and it did not engage" is
    ``engaged=False`` — and the ladder keeps the touch (the window anchors
    there) while the stage does not move."""

    failed = review_event("re-failed", engaged=False, created_at=DAY_ONE)
    assert role_of(failed) is ReviewEventRole.ANCHOR_ONLY
    assert anchor_of(_NoStrongRetrieval(), (failed,)).value == DAY_ONE
    assert stage_from_history((failed,)) is SPACING_STAGES[0]
    engaged = review_event("re-engaged", engaged=True, created_at=DAY_ONE)
    assert stage_from_history((engaged,)) is SPACING_STAGES[1]


def test_the_ladder_reads_no_event_type_word() -> None:
    """The other half of the freeze: ``event_type`` carries no vocabulary and
    the ladder **reads** it nowhere — no comparison, no membership test, no
    attribute read. So a producer's word is not read back, and the two columns
    the table keys on are the two it must get right."""

    source = source_text("src/elc/scheduler/spacing.py")
    assert ".event_type" not in source
    assert "event_type ==" not in source
    assert "event_type in" not in source
    assert "engaged" in source
    assert "created_at" in source


def test_the_table_names_the_producer_that_must_cite_it() -> None:
    docstring = ReviewEventRole.__doc__ or ""
    for phrase in (
        "P7-0 freeze table",
        "must cite this table before it writes an event",
        "engaged",
        "created_at",
    ):
        assert phrase in docstring, phrase


def test_the_table_is_a_declaration_and_changes_no_ladder_behaviour() -> None:
    """P7-0 added a table to the ladder's module and **not** a call from it:
    none of the ladder's own functions calls ``role_of``, and the module's
    model version is untouched (a behaviour change would move it)."""

    tree = ast.parse(source_text("src/elc/scheduler/spacing.py"))
    ladder = {
        "anchor_of",
        "stage_from_history",
        "next_window",
        "state_at",
        "urgency_of",
        "plan_schedule_item",
        "row_version",
        "version_content",
    }
    callers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in ladder:
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "role_of"
            ):
                callers.append(node.name)
    assert callers == []
    assert SCHEDULER_MODEL_VERSION == "sd1"


def test_role_of_reads_only_the_two_columns() -> None:
    """Structural half of the same claim: the function's body touches its
    event argument's ``engaged`` / ``created_at`` and no other field."""

    tree = ast.parse(source_text("src/elc/scheduler/spacing.py"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "role_of"
    )
    attributes = {
        node.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "event"
    }
    assert attributes == {"engaged", "created_at"}


def test_the_two_spikes_are_declared_as_this_cuts_readings() -> None:
    """Both spikes land as *declared* readings rather than as quotations: the
    role words are this cut's (no canonical block names them), the alias is
    the platform's binding, and each module says which part is canonical text
    and which part is the judgement (with its revisit condition)."""

    docstring = ReviewEventRole.__doc__ or ""
    assert "this cut's declaration" in docstring
    for path in (
        "src/elc/scheduler/spacing.py",
        "src/elc/user_config/types.py",
    ):
        assert "revisit" in source_text(path).lower(), path
    assert review_event("re-x").event_type == "RECALL_ATTEMPT"
