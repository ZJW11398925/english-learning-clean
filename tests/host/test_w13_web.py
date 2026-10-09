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
4. **the turn wiring** — a committed turn's letter goes to the
   narrator (WR-2, DEC-OPI-5fc42174…49: the world's beats are
   model-generated now; the fixed-pool engine step is retired out of
   the production path), the reply answers normally with no world key
   in the payload, and the inbox read reveals what the step left
   pending; a world letter that fails is fail-soft (the reply is
   untouched, nothing is written, and the sentence goes to stderr —
   the payload carries no world key at all).
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
    web_stack,
)
from tests.host.test_wr2_post_turn_wiring import (
    BEATS_TWO,
    BeatsProvider,
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
    """A2R (DEC-…99) retired the 「继续」 light action; lr-4a
    (DEC-OPI-c73dbff3…128) rebirths the route for a different tenant —
    the **parked round's** continuation, not the engine's light action.
    With no parked round the preflight answers the plain 409 人话 (the
    A2R 404 truth is gone with the route's rebirth; the light action
    itself stays retired — there is no engine checkpoint to refuse)."""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post("/api/world/continue", {})
    assert status == 409
    assert "停下来的世界" in payload["error"]


def test_the_turn_winds_the_world_and_the_inbox_reveals(
    tmp_path: Path,
) -> None:
    """The turn wiring end to end (WR-2): the committed letter goes to
    the narrator, the reply answers normally with no world key in the
    payload, and the inbox read reveals the step's beats — the
    generated narrations verbatim, the world's own byline (the
    narrator signs nothing), the beat's story day, the run left at its
    checkpoint (the anchor run — the generated step never
    terminalizes)."""

    provider = BeatsProvider(beats_json=BEATS_TWO)
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == provider.reply_text
        assert "world_step_note" not in turn
        status, inbox = stack.get_json("/api/world/inbox")
    assert status == 200
    assert len(inbox["items"]) == 2
    # The read was the reveal: the notes answer revealed, each with its
    # generated narration verbatim, the world's own byline (the item
    # carries no actor) and the moment the beat carries.
    for note, narration in zip(inbox["items"], provider.narrations):
        assert note["status"] == "REVEALED"
        assert note["narration"] == narration
        assert note["actor_name"] == "世界"
        assert note["moment"]
    assert inbox["at_checkpoint"] is True


def test_the_world_letter_failure_is_fail_soft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fail-soft contract (WR-2 shape): a world letter that blows
    up costs the reply nothing — the payload is untouched and carries
    no world key — and nothing is written (no run, no event, no
    reveal). The next unpatched turn narrates again."""

    import elc.web

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(elc.web, "run_generated_step", _boom)
    app_db = tmp_path / "app.db"
    provider = BeatsProvider(beats_json=BEATS_TWO)
    with web_stack(app_db, provider=provider) as stack:
        status, broken = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert broken["reply"] == provider.reply_text
        assert "world_step_note" not in broken
        rows = _ro_rows(app_db, "SELECT COUNT(*) FROM world_run")
        assert rows[0][0] == 0
    monkeypatch.undo()
    # A fresh double for the fresh session (the scripted parity of the
    # first double stayed with its own two calls).
    fine_provider = BeatsProvider(beats_json=BEATS_TWO)
    with web_stack(app_db, provider=fine_provider) as stack:
        status, fine = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert fine["reply"] == fine_provider.reply_text
        assert "world_step_note" not in fine
        # C1-a 随迁：两轮各 +1 信寄出事实行（2 世界拍 + 2 互动行）。
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 4


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
