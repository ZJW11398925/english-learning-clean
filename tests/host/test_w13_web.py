"""W-1-3 — the world inbox's web half, over the production assembly.

The same shape as the W-1 suite: the real ``elc.web.run_web`` over the
real ``open_host`` (the builtin Berrymoor package seeds at open — its
cast persona is the penpal card the official family seeds), reached
with ``urllib`` over the loopback. The pinned groups:

1. **the binding** — ``run_web`` binds the conversation into the
   builtin world idempotently (the derived binding id, the cast's first
   member as the signature; a second start on the same database lands
   as the store's no-op, still exactly one row), and the CLI binds
   nothing (the registration, pinned as a source fact);
2. **the inbox endpoint** — ``GET /api/world/inbox`` answers the
   aggregate payload (the items list, the recent letters, the
   ``at_checkpoint`` bit read off the run row) and reveals atomically
   on the read; a conversation outside any world answers the honest
   404, not an empty inbox;
3. **the continue endpoint, retired** — A2R (DEC-…99) removed
   ``POST /api/world/continue`` with the button (the engine never
   pauses mid-run): the route answers the plain 404, never a step;
4. **the turn wiring** — a committed turn winds the world (the engine's
   first production caller end to end: the reply answers normally and
   the inbox carries the step's notes), and a world step that fails is
   fail-soft (the reply is untouched; the sentence rides the additive
   ``world_step_note`` field).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.web import _WebFace
from tests.host.test_w1_web import (
    CLEAN_TEXT,
    CONV,
    REPLY,
    web_stack,
)

REPO = Path(__file__).resolve().parents[2]


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows off the serving database through a fresh
    read-only connection (the W-4 ro posture — the worker thread owns
    the writable one)."""

    conn = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(conn.execute(sql).fetchall())
    finally:
        conn.close()


def test_run_web_binds_the_conversation_idempotently(tmp_path: Path) -> None:
    """The web conversation lives in the builtin world: the first start
    writes the derived binding (the cast's first member as the
    signature), and a second start on the same database answers the
    store's idempotent no-op — still exactly one binding row."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db):
        pass
    with web_stack(app_db):
        rows = _ro_rows(
            app_db,
            "SELECT binding_id, world_id, actor_id, conversation_id"
            " FROM world_conversation",
        )
    assert len(rows) == 1
    binding_id, world_id, actor_id, conversation_id = rows[0]
    assert str(binding_id) == f"bind-{CONV}"
    assert str(world_id) == "world-berrymoor"
    assert str(actor_id) == "actor-berrymoor-nell"
    assert str(conversation_id) == str(CONV)


def test_the_cli_binds_nothing() -> None:
    """The registration: the binding write lives in the web face only —
    the CLI command never binds a conversation into a world (a chat
    session is not a world residency unless a later cut says so)."""

    cli_source = (REPO / "src" / "elc" / "cli.py").read_text(encoding="utf-8")
    assert "bind_conversation" not in cli_source


def test_the_inbox_answers_the_bound_world(tmp_path: Path) -> None:
    """The inbox endpoint's aggregate payload on a freshly bound world:
    an empty items list (nothing has happened yet), the recent-letters
    list, and the honest ``at_checkpoint: false`` (no run exists)."""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.get_json("/api/world/inbox")
    assert status == 200
    assert payload["items"] == []
    assert isinstance(payload["letters"], list)
    assert payload["at_checkpoint"] is False
    assert payload["world_id"] == "world-berrymoor"


def test_the_continue_endpoint_is_retired(tmp_path: Path) -> None:
    """A2R (DEC-…99): the 「继续」 endpoint is gone with its button — the
    route answers the plain 404, never a step (there is no light action
    left to refuse anything)."""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post("/api/world/continue", {})
    assert status == 404
    assert payload == {"error": "not found"}


def test_the_turn_winds_the_world_and_the_inbox_reveals(
    tmp_path: Path,
) -> None:
    """The turn wiring end to end: the committed turn winds the world
    (the letter trigger), the reply answers normally with no step note,
    and the inbox read reveals the step's notes — one call's whole beat
    run (A2R DEC-…99: eight events to the ceiling of the always-mature
    ambient beats), the run at its stop, never at a checkpoint."""

    with web_stack(tmp_path / "app.db") as stack:
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == REPLY
        assert turn["world_step_note"] is None
        status, inbox = stack.get_json("/api/world/inbox")
    assert status == 200
    assert len(inbox["items"]) == 8
    # The read was the reveal: the notes answer revealed, each with its
    # narration, its byline (a cast name or the world's own 「世界」 for
    # a silent cycle) and the moment the event carries.
    for note in inbox["items"]:
        assert note["status"] == "REVEALED"
        assert isinstance(note["narration"], str) and note["narration"]
        assert note["actor_name"] in ("世界", "Nell Alder")
        assert isinstance(note["moment"], str) and note["moment"]
    assert inbox["at_checkpoint"] is False


def test_the_world_step_failure_is_fail_soft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fail-soft contract: a world step that blows up says one human
    sentence in the additive ``world_step_note`` field and the reply is
    untouched — the page's substance never waits on the world's
    bookkeeping. The next unpatched turn answers with no note again."""

    import elc.web

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(elc.web, "run_step", _boom)
    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, broken = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert broken["reply"] == REPLY
        assert "世界步进失败" in str(broken["world_step_note"])
    monkeypatch.undo()
    with web_stack(app_db) as stack:
        status, fine = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert fine["reply"] == REPLY
        assert fine["world_step_note"] is None


def test_the_inbox_404s_without_a_binding() -> None:
    """A conversation outside any world: the inbox does not exist — the
    honest 404, not an empty inbox (the unit-level face over a host
    without a world leg; the face's own two-word answer)."""

    class _NoWorldHost:
        app_db_path = "stub.db"

    face = _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]
    status, payload = face.world_inbox()
    assert status == 404
    assert "没有绑定任何世界" in payload["error"]
