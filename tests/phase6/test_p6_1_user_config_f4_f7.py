"""P6-1 ②⑥ — the two P6-0 carry-overs this slice closes: F-4 and F-7.

Both are in ``elc.user_config``, and both are *increments* rather than a
rewrite — the tests below pin exactly that:

- **F-4 (the ``effective_from`` sentinel)** — the empty string ``""`` is now
  an **explicitly registered** "not configured" value on both versioned
  configuration objects. The registration is a declaration, not a type change:
  the columns stay ``str`` and **migration 0011 is not touched** (its DDL still
  spells ``effective_from TEXT NOT NULL`` twice), so a consumer that reads
  ``""`` as a timestamp is reading a sentinel as data.
- **F-7 (the per-conversation focus read)** — §5.1 gave ``SessionFocus`` no
  route from a conversation to its focus; the store, the query face and the
  controller now have one, 1:1, with the reading declared once (largest
  ``starts_at``; ties broken by the largest ``session_focus_id``; **no**
  ``expires_at`` filter; **no** clock judgement) and pinned here.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import textwrap
from typing import get_type_hints

import pytest

from elc.platform.types import ConversationId, Ok, UserId
from elc.user_config import types as user_config_types
from elc.user_config.controller import UserConfigController
from elc.user_config.queries import UserConfigQueries
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    LearningGoalPortfolio,
    TeachingPolicyProfile,
)
from tests.conftest import REPO_ROOT

from .conftest import (
    CONV,
    USER,
    goal,
    portfolio,
    session_focus,
    teaching_policy,
)

MIGRATION_0011 = REPO_ROOT / "migrations" / "0011_goal_policy_focus.sql"
READ_NAME = "get_session_focus_for_conversation"


# -- F-4: the sentinel is registered -----------------------------------------


@pytest.mark.parametrize(
    "schema", [LearningGoalPortfolio, TeachingPolicyProfile]
)
def test_the_empty_string_sentinel_is_registered(schema: type) -> None:
    """F-4: the reading is written down where the field is — a value, not an
    absence of one, and not a clock substitute."""

    docstring = schema.__doc__ or ""
    assert '""' in docstring
    assert "F-4" in docstring
    assert "not configured" in docstring
    assert dataclasses.fields(schema)[-2].name == "effective_from"


def test_the_sentinel_did_not_change_the_column_type_or_the_migration() -> None:
    """The registration is a declaration on purpose: ``str`` with ``""``
    leaves §5.1's column set exactly as migration 0011 wrote it (a nullable
    column would be a different canonical shape, and 0011 is frozen)."""

    assert get_type_hints(LearningGoalPortfolio)["effective_from"] is str
    assert get_type_hints(TeachingPolicyProfile)["effective_from"] is str
    ddl = MIGRATION_0011.read_text(encoding="utf-8")
    # The two ``effective_from`` columns, inside the two CREATE TABLE bodies
    # (the header's column notes quote them too, so the bodies are what count):
    # TEXT and NOT NULL in both, and nothing nullable anywhere.
    bodies = re.findall(
        r"CREATE TABLE IF NOT EXISTS \w+ \((.*?)\n\);", ddl, re.DOTALL
    )
    assert len(bodies) == 3, "0011 creates three tables"
    carriers = [body for body in bodies if "effective_from" in body]
    assert len(carriers) == 2
    for body in carriers:
        assert re.search(r"effective_from\s+TEXT NOT NULL", body)
        assert not re.search(r"effective_from\s+TEXT\s*[\n,)]", body)


def test_the_sentinel_survives_the_round_trip_verbatim(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The store invents no effective date and normalizes no sentinel: what a
    silent caller leaves is what a later read returns."""

    written = user_config_store.upsert_goal_portfolio(
        portfolio(goal("g-1"), effective_from="")
    )
    assert isinstance(written, Ok), written
    assert written.value.effective_from == ""
    read = user_config_store.get_goal_portfolio(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.effective_from == ""

    policy = user_config_store.upsert_teaching_policy(teaching_policy())
    assert isinstance(policy, Ok), policy
    assert policy.value.effective_from == ""
    assert (
        user_config_store.get_teaching_policy(USER).value.effective_from == ""
    )


def test_the_module_shape_list_still_describes_the_column_as_a_time() -> None:
    """The sentinel is the one value outside the column's declared shape, and
    the module docstring still says what the shape is."""

    docstring = user_config_types.__doc__ or ""
    assert "effective_from" in docstring
    assert "ISO-8601" in docstring


# -- F-7: the per-conversation read ------------------------------------------


def test_the_per_conversation_read_is_declared_on_all_three_layers() -> None:
    """1:1 increment: the durable read, the query face and the authority face
    each carry it, under the same name and with the same signature."""

    assert hasattr(SqliteUserConfigStore, READ_NAME)
    assert hasattr(UserConfigQueries, READ_NAME)
    assert hasattr(UserConfigController, READ_NAME)
    for face in (
        SqliteUserConfigStore.get_session_focus_for_conversation,
        UserConfigQueries.get_session_focus_for_conversation,
        UserConfigController.get_session_focus_for_conversation,
    ):
        parameters = list(inspect.signature(face).parameters)
        assert parameters == ["self", "conversation_id"], face


def test_the_read_answers_by_conversation(
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    del conversation
    assert isinstance(
        user_config_store.set_session_focus(
            session_focus("sf-late", starts_at="2026-09-22T12:00:00+00:00")
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.set_session_focus(
            session_focus("sf-early", starts_at="2026-09-22T08:00:00+00:00")
        ),
        Ok,
    )
    read = user_config_store.get_session_focus_for_conversation(CONV)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.session_focus_id == "sf-late"
    assert read.value.starts_at == "2026-09-22T12:00:00+00:00"


def test_a_tie_is_broken_by_the_largest_id(
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    """Deterministic by construction: same ``starts_at`` → the largest
    ``session_focus_id`` wins, in lexicographic (byte-wise) order."""

    del conversation
    for focus_id in ("sf-a", "sf-c", "sf-b"):
        assert isinstance(
            user_config_store.set_session_focus(
                session_focus(
                    focus_id, starts_at="2026-09-22T09:00:00+00:00"
                )
            ),
            Ok,
        )
    read = user_config_store.get_session_focus_for_conversation(CONV)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.session_focus_id == "sf-c"
    # Two calls answer identically: no clock, no insertion-order dependence.
    again = user_config_store.get_session_focus_for_conversation(CONV)
    assert again.value == read.value


def test_an_expired_window_is_not_filtered_out(
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    """The reading consults ``starts_at`` only: whether a window is still
    valid is the consumer's question, answered with the consumer's clock."""

    del conversation
    assert isinstance(
        user_config_store.set_session_focus(
            session_focus(
                "sf-expired",
                starts_at="2026-09-22T12:00:00+00:00",
                expires_at="2026-09-22T12:30:00+00:00",
            )
        ),
        Ok,
    )
    read = user_config_store.get_session_focus_for_conversation(CONV)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.session_focus_id == "sf-expired"
    assert read.value.expires_at == "2026-09-22T12:30:00+00:00"


def test_a_conversation_with_no_focus_answers_none(
    user_config_store: SqliteUserConfigStore,
) -> None:
    read = user_config_store.get_session_focus_for_conversation(
        ConversationId("conv-never")
    )
    assert isinstance(read, Ok)
    assert read.value is None


def test_the_read_does_not_borrow_another_conversations_focus(
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    del conversation
    assert isinstance(
        user_config_store.set_session_focus(
            session_focus("sf-here", conversation=CONV)
        ),
        Ok,
    )
    other = user_config_store.get_session_focus_for_conversation(
        ConversationId("conv-elsewhere")
    )
    assert isinstance(other, Ok)
    assert other.value is None


def test_the_controller_delegates_the_new_read(
    user_config_controller: UserConfigController,
    conversation,
) -> None:
    del conversation
    assert isinstance(
        user_config_controller.set_session_focus(session_focus("sf-1")), Ok
    )
    read = user_config_controller.get_session_focus_for_conversation(CONV)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.session_focus_id == "sf-1"
    assert read.value == user_config_controller.get_session_focus("sf-1").value


def test_the_id_keyed_read_is_untouched(
    user_config_controller: UserConfigController,
    conversation,
) -> None:
    """F-7 added a route; it did not replace the id-keyed one (§5.1's object
    is still readable by its own key, and the append-first history is still
    several rows)."""

    del conversation
    for index in (1, 2):
        assert isinstance(
            user_config_controller.set_session_focus(
                session_focus(f"sf-{index}")
            ),
            Ok,
        )
    assert user_config_controller.get_session_focus("sf-1").value is not None
    assert user_config_controller.get_session_focus("sf-2").value is not None
    assert user_config_controller.get_session_focus("sf-3").value is None


def test_a_user_id_is_not_a_conversation_id() -> None:
    """The new route is keyed by the conversation, not by the user: the two
    are different ids and the method's annotation says so."""

    hints = inspect.get_annotations(
        SqliteUserConfigStore.get_session_focus_for_conversation, eval_str=True
    )
    assert hints["conversation_id"] is ConversationId
    assert hints["conversation_id"] is not UserId


def _code_only(face) -> str:
    """One method's code, docstring and comments excluded — what is left is
    what the method actually does (``ast.unparse`` drops the comments)."""

    node = ast.parse(textwrap.dedent(inspect.getsource(face))).body[0]
    assert isinstance(node, ast.FunctionDef)
    body = [
        statement
        for statement in node.body
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
    ]
    return ast.unparse(ast.Module(body=body, type_ignores=[]))


def test_the_new_read_introduces_no_clock_judgement() -> None:
    """Structural half of "no ``expires_at`` filter": the method's own body
    reads no clock, and its statement selects ``expires_at`` (the row is
    decoded whole) while its **filter** is the conversation alone — nothing
    compares or filters on the window."""

    code = _code_only(
        SqliteUserConfigStore.get_session_focus_for_conversation
    )
    for token in ("_now", "datetime", "UTC"):
        assert token not in code, token
    statement = next(
        part for part in code.split("'") if "session_focus" in part
    )
    assert "expires_at" in statement  # selected: the row is decoded whole
    assert "WHERE conversation_id = ?" in statement
    assert "expires_at" not in statement.split("WHERE", 1)[1]
    assert "starts_at" in code and "session_focus_id" in code
