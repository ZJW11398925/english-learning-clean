"""P8-4 ⑥ — §20's exposure write: the mapping, the one point, the failures.

``elc.runtime.exposure`` maps "a teaching action was really delivered" to
§20's word, and the coordinator applies it at one point on the delivery leg.
What is pinned here:

- the mapping is §20's: ``OPENING`` / ``HINT`` / ``REVEAL`` → the three
  presentation words, and the three kinds §20 has **no** word for (``RETRY`` /
  ``EXPLANATION`` / ``RESUME``) are registered rather than mapped — a fourth
  unmapped kind is a refusal, not a silent no-write;
- the ids are deterministic on what the fact is about (the action, or the
  skipped moment), which names the same presentation across attempts — the
  store's replay compares the instant too, so only a same-instant re-attempt is
  a no-op and a new one is ``CONFLICT`` (``elc.runtime.exposure`` registers
  why no live path re-attempts the write);
- the write happens on real deliveries and nowhere else: an ALLOW's opening,
  a continuation's hint, a user skip — and **not** for a failed delivery, not
  when no writer is wired, and not for the resume;
- the failure posture (R-INV-010's shape): an ``Err`` from the writer, a
  writer that raises, or a writer that does not implement the face leaves the
  delivery's own outcome untouched and carries the reason on
  ``ledger_failure``.

**Registered coverage gaps (review F6; the fix is an example, not a behaviour
change).** Three legs are named here and not exercised:

- ``request_teaching`` (the user-initiated opening) with the automatic wiring
  **injected** has no case: everything above drives either the automatic leg or
  a wiring-less teaching path, so "the wiring changes nothing on the
  user-initiated path" rests on the unit-level statements elsewhere. Trigger:
  the first cut that edits ``request_teaching`` — or the delivery ladder it
  shares with ``_deliver_teaching_action`` — which brings its example with it;
- ``RETRY`` has a *mapping* case only: a delivery-path retry needs a live
  Moment mid-conversation, so "the retry writes nothing" is not driven here.
  Trigger: the continuation leg gaining a retry case (or the rollout suite);
- ``exposure.record_event`` writes every event under ``LedgerKeyType.TARGET``;
  a ``CAPABILITY`` focus target has neither a case nor a declared reading, and
  the constant is where the trigger is registered.

The deliveries are driven through the coordinator (the shipped path), not by
calling the writer directly: what matters is that the *turn* records what
happened.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.planner.ledger import LedgerEvent
from elc.platform.types import (
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.exposure import (
    LEDGER_EVENT_BY_DELIVERY,
    UNMAPPED_DELIVERY_KINDS,
    exposure_event_id,
    ledger_event_of,
    skip_event_id,
)
from elc.teaching.envelope import (
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from tests.phase7.conftest import CONV, DAY_THREE
from tests.phase8.p8_4_world import (
    World,
    acceptance_supply,
    begin_turn_ok,
    build_content,
    command,
    counts,
    wiring,
    world,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator

REPLY_AT = DAY_THREE


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db: sqlite3.Connection, fence, content: Path) -> World:
    return world(db, fence, content)


def automatic(p8world, **kwargs):
    return wiring(p8world, supply=acceptance_supply(), **kwargs)


def _reply(coordinator_, intent: TeachingControlIntent, cmid: str):
    return coordinator_.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(control_intent=intent),
            client_message_id=ClientMessageId(cmid),
            requested_at=REPLY_AT,
        )
    )


def _events(db: sqlite3.Connection) -> list[tuple[object, object]]:
    return [
        (row[0], row[1])
        for row in db.execute(
            "SELECT event, moment_id FROM planning_ledger_event"
            " ORDER BY rowid"
        )
    ]


# -- ① the mapping -----------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "word"),
    (
        ("OPENING", LedgerEvent.TEACHING_PRESENTED),
        ("HINT", LedgerEvent.HINT_PRESENTED),
        ("REVEAL", LedgerEvent.REVEAL_PRESENTED),
    ),
)
def test_the_three_presentation_kinds_map_to_section20s_words(
    kind: str, word: LedgerEvent
) -> None:
    assert ledger_event_of(kind) is word


@pytest.mark.parametrize("kind", UNMAPPED_DELIVERY_KINDS)
def test_the_registered_unmapped_kinds_answer_none(kind: str) -> None:
    assert kind in ("RETRY", "EXPLANATION", "RESUME")
    assert ledger_event_of(kind) is None


def test_a_fourth_unmapped_kind_is_refused() -> None:
    with pytest.raises(ValueError) as raised:
        ledger_event_of("CLOSING_FEEDBACK")
    assert "CLOSING_FEEDBACK" in str(raised.value)


def test_the_mappings_keys_are_the_delivery_paths_vocabulary() -> None:
    """The pin the module's own docstring promises: the mapped keys are
    ``elc.runtime.controller.TEACHING_ACTION_BY_DELIVERY``'s kind words, and
    mapped + registered covers that table exactly — a further kind lands in
    one of the two or the delivery path's vocabulary grew silently."""

    from elc.runtime.controller import TEACHING_ACTION_BY_DELIVERY

    kinds = set(TEACHING_ACTION_BY_DELIVERY)
    assert set(LEDGER_EVENT_BY_DELIVERY) | set(UNMAPPED_DELIVERY_KINDS) == kinds
    assert not set(LEDGER_EVENT_BY_DELIVERY) & set(UNMAPPED_DELIVERY_KINDS)


def test_closing_feedback_reuses_the_reveal_word() -> None:
    from elc.runtime.controller import CLOSING_FEEDBACK_DELIVERY

    assert CLOSING_FEEDBACK_DELIVERY == "REVEAL"
    assert ledger_event_of(CLOSING_FEEDBACK_DELIVERY) is LedgerEvent.REVEAL_PRESENTED


def test_the_words_are_the_cores_own() -> None:
    assert {word.value for word in LEDGER_EVENT_BY_DELIVERY.values()} == {
        "teaching_presented",
        "hint_presented",
        "reveal_presented",
    }
    assert LedgerEvent.USER_SKIP.value == "user_skip"


# -- ② the ids ---------------------------------------------------------------


def test_the_event_id_derives_from_the_action() -> None:
    assert exposure_event_id("ga-turn-1-automatic-open") == (
        "ev-ga-turn-1-automatic-open"
    )


def test_the_skip_id_derives_from_the_moment() -> None:
    assert skip_event_id("tm-turn-1-automatic") == "ev-skip-tm-turn-1-automatic"


def test_the_two_ids_cannot_collide() -> None:
    action = "ga-turn-1-automatic-open"
    moment = "tm-turn-1-automatic"
    assert exposure_event_id(action) != skip_event_id(moment)


# -- ③ the write happens on real deliveries ---------------------------------


def test_the_opening_write_lands_with_the_moment(
    db: sqlite3.Connection, p8world
) -> None:
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-open"
    )
    assert completion.ledger_event == "teaching_presented"
    moment_id = db.execute("SELECT moment_id FROM teaching_moment").fetchone()[0]
    assert _events(db) == [("teaching_presented", moment_id)]
    assert db.execute(
        "SELECT event_id FROM planning_ledger_event"
    ).fetchone() == (f"ev-ga-{completion.turn_id}-automatic-open",)


def test_a_failed_delivery_records_nothing(
    db: sqlite3.Connection, p8world
) -> None:
    """The refusal path of the crash window: CP2's action is dispatched and
    the delivery returns no message — no exposure event exists (nothing was
    presented)."""

    class RefusingPersona:
        def __init__(self) -> None:
            self.refused = False

        def run_action(self, *args, **kwargs):
            if not self.refused:
                self.refused = True
                return Err(
                    DomainError(
                        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                        message="injected delivery crash",
                    )
                )
            raise AssertionError("unreachable in this test")

    crashing = build_coordinator(
        p8world, automatic=automatic(p8world), persona=RefusingPersona()
    )
    result = crashing.begin_turn(command("cm-fail"))
    assert isinstance(result, Err), result
    assert _events(db) == []
    assert counts(db, "planning_ledger") == {"planning_ledger": 0}


def test_no_writer_means_no_side_effects(
    db: sqlite3.Connection, p8world
) -> None:
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world, ledger=False)),
        "cm-open",
    )
    assert completion.ledger_event is None
    assert completion.ledger_failure is None
    assert _events(db) == []
    assert counts(db, "planning_ledger") == {"planning_ledger": 0}
    # … and the delivery itself is unaffected.
    assert completion.outcome == "REPLIED_FULL"
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("AWAITING_USER",)


def test_a_hint_delivery_records_the_hint_word(
    db: sqlite3.Connection, p8world
) -> None:
    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(coordinator_, "cm-open")
    replied = _reply(coordinator_, TeachingControlIntent.ASK_HINT, "cm-hint")
    assert isinstance(replied, Ok), replied
    assert replied.value.delivery_kind == "HINT"
    assert replied.value.ledger_event == "hint_presented"
    assert _events(db)[-1] == ("hint_presented", replied.value.moment_id)


def test_a_skip_records_the_user_skip_word(
    db: sqlite3.Connection, p8world
) -> None:
    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(coordinator_, "cm-open")
    replied = _reply(coordinator_, TeachingControlIntent.SKIP, "cm-skip")
    assert isinstance(replied, Ok), replied
    assert replied.value.closure == "USER_SKIP"
    assert replied.value.ledger_event == "user_skip"
    assert replied.value.ledger_failure is None
    assert _events(db)[-1] == ("user_skip", replied.value.moment_id)
    assert db.execute(
        "SELECT recent_skips FROM planning_ledger"
    ).fetchone() == (1,)


def test_a_rejection_is_not_a_skip(db: sqlite3.Connection, p8world) -> None:
    """§7's other user-leaving words carry no §20 word: a rejection closes the
    Moment and writes no event (only ``user_skip`` is §20's)."""

    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(coordinator_, "cm-open")
    replied = _reply(
        coordinator_, TeachingControlIntent.REJECT_TARGET, "cm-reject"
    )
    assert isinstance(replied, Ok), replied
    assert replied.value.closure == "USER_REJECTED_TARGET"
    assert replied.value.ledger_event is None
    assert _events(db) == [("teaching_presented", _moment_id(db))]


def test_the_resume_delivery_records_nothing(
    db: sqlite3.Connection, p8world
) -> None:
    """The reply path's resume is one of §20's unmapped kinds: the closing
    turn's own result carries no word and the log gains no event."""

    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(coordinator_, "cm-open")
    replied = _reply(coordinator_, TeachingControlIntent.SKIP, "cm-skip")
    assert isinstance(replied, Ok), replied
    assert replied.value.delivery_kind == "RESUME"
    assert replied.value.ledger_event == "user_skip"
    assert [word for word, _moment in _events(db)] == [
        "teaching_presented",
        "user_skip",
    ]


# -- ④ the failure posture ---------------------------------------------------


class RefusingWriter:
    """The ledger write face, refusing every call with a readable reason."""

    def get_ledger_row(self, key: str):
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="injected ledger refusal",
            )
        )

    def list_obligations(self, *, target_or_family_id: str | None = None):
        return Ok(())

    def record_ledger_event(self, **kwargs):
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="injected ledger refusal",
            )
        )


class RaisingWriter(RefusingWriter):
    """The same, raising instead of answering an ``Err``."""

    def get_ledger_row(self, key: str):
        raise RuntimeError("injected ledger explosion")

    def record_ledger_event(self, **kwargs):
        raise RuntimeError("injected ledger explosion")


class ReadOnlyWriter:
    """A face that only implements the read half (the wiring's narrow port
    used to be exactly that)."""

    def read_ledger(self):
        return Ok(None)


def test_a_refusing_writer_does_not_change_the_delivery(
    db: sqlite3.Connection, p8world
) -> None:
    from dataclasses import replace

    wiring_ = replace(automatic(p8world), ledger=RefusingWriter())
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=wiring_), "cm-refuse"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert completion.ledger_event is None
    assert completion.ledger_failure == "injected ledger refusal"
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("AWAITING_USER",)
    assert _events(db) == []


def test_a_raising_writer_does_not_change_the_delivery(
    db: sqlite3.Connection, p8world
) -> None:
    from dataclasses import replace

    wiring_ = replace(automatic(p8world), ledger=RaisingWriter())
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=wiring_), "cm-raise"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert completion.ledger_event is None
    assert completion.ledger_failure is not None
    assert "raised" in completion.ledger_failure
    assert _events(db) == []


def test_a_writer_without_the_write_face_is_reported_too(
    db: sqlite3.Connection, p8world
) -> None:
    """The wiring's declared port has both halves; an object that only has the
    read one is a broken writer, and the delivery must survive it."""

    from dataclasses import replace

    wiring_ = replace(automatic(p8world), ledger=ReadOnlyWriter())
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=wiring_), "cm-readonly"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert completion.ledger_event is None
    assert completion.ledger_failure is not None
    assert "raised" in completion.ledger_failure
    assert _events(db) == []


def test_a_refusing_writer_on_the_skip_path_does_not_block_the_abort(
    db: sqlite3.Connection, p8world
) -> None:
    from dataclasses import replace

    wiring_ = replace(automatic(p8world), ledger=RefusingWriter())
    coordinator_ = build_coordinator(p8world, automatic=wiring_)
    begin_turn_ok(coordinator_, "cm-open-refuse")
    replied = _reply(coordinator_, TeachingControlIntent.SKIP, "cm-skip-refuse")
    assert isinstance(replied, Ok), replied
    assert replied.value.closure == "USER_SKIP"
    assert replied.value.ledger_event is None
    assert replied.value.ledger_failure == "injected ledger refusal"
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("CLOSED",)


def _moment_id(db: sqlite3.Connection) -> str:
    return str(db.execute("SELECT moment_id FROM teaching_moment").fetchone()[0])
