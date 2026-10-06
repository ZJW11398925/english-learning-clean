"""wf-0 — the world's three read endpoints, over the production assembly.

The same shape as the W-1/W-1-3 suites: the real ``elc.web.run_web`` over
the real ``open_host`` (the builtin Berrymoor package seeds at open and
``run_web`` binds the conversation into it — the cast's first member as
the signature), reached with ``urllib`` over the loopback. The three new
faces are **reads**: ``GET /api/world/overview`` (the one-screen world),
``GET /api/world/log`` (the revealed chronicle, newest day first) and
``GET /api/world/residents`` (the cast joined to its cards). The pinned
groups:

1. **the guards** — all three answer the inbox's own 404 with the inbox's
   own sentence when the conversation lives in no world (an overview, a
   log and a roster that do not exist are not empty ones);
2. **the overview** — the quiet-day arm (an honest human sentence, never
   a disclosure of what waits), the resident block (the bound actor's
   card, ``None`` for a ``NULL``-actor binding — that arm pinned at the
   binding read's own seam, since migration 0023's ``NOT NULL`` keeps
   the row out of durable reach), and the story day as a
   **pure derivation** (``calendar_start`` plus the events' story spans —
   a far-future wall clock changes nothing);
3. **the red line (the decisive pin)** — a ``PENDING`` note left by hand
   survives the overview read, survives the log read, and is flipped by
   the inbox read alone: reading is not opening, and the flip count is
   read off the durable queue after every leg;
4. **the log** — ``REVEALED`` only, grouped by story day newest first,
   the two signature arms (the world's own ``null`` and the actor's card
   name), the item shape;
5. **the residents** — the roster joined to its cards in the roster's own
   order, ``is_current`` marking exactly the bound actor (all false when
   the binding names none), and the letter count's honest zeros (no bound
   conversation answers 0, a bound-but-empty one answers 0);
6. **the languages** — the overview and the log render in the interface
   language (the W-L row, default ``zh``), dates and the quiet-day
   sentence included;
7. **the structural pin** — the three read faces (and the helpers they
   share) contain zero ``reveal_all`` calls, AST-level over the web.py
   source, with the walker's positive control on the two presentation
   triggers that legitimately keep theirs.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import elc.web
from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.web import _WebFace
from tests.host.test_w1_web import (
    CLEAN_TEXT,
    REPLY,
    web_stack,
)

REPO = Path(__file__).resolve().parents[2]

#: One durable timestamp for the injected rows (the a2 suite's posture):
#: the injection rides its own short-lived writable connection while the
#: worker thread sits idle in its work loop.
NOW = "2025-09-14T08:00:00+00:00"

#: The pending note's own English prose — a text no other row carries, so
#: its presence or absence in a payload is decidable by search.
PENDING_NOTE = "A note the next session has not read yet."


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows off the serving database through a fresh
    read-only connection (the W-4 ro posture — the worker thread owns
    the writable one)."""

    conn = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(conn.execute(sql).fetchall())
    finally:
        conn.close()


def _pending_count(app_db: Path) -> int:
    """The durable ``PENDING`` count — the red line's own gauge, read off
    the queue table after every leg of the triple."""

    rows = _ro_rows(
        app_db,
        "SELECT COUNT(*) FROM world_reveal_item WHERE status = 'PENDING'",
    )
    return int(rows[0][0])


def _inject_note(
    app_db: Path,
    event_id: str,
    kind: str,
    day: str,
    *,
    actor_id: str | None,
    status: str,
    narration: str,
    revealed_at: str | None = None,
) -> None:
    """One chronicle event plus its reveal-queue row, written by hand
    (the a2 suite's injection posture: the event first — the item's FK
    names it — then the item)."""

    writer = sqlite3.connect(app_db, timeout=10)
    try:
        writer.execute(
            "INSERT INTO world_event (event_id, world_id, kind, narration,"
            " effects, occurred_at, source)"
            " VALUES (?, 'world-berrymoor', ?, ?, '[]', ?, 'test')",
            (event_id, kind, narration, day),
        )
        writer.execute(
            "INSERT INTO world_reveal_item (item_id, world_id,"
            " source_event_id, actor_id, status, revealed_at, created_at)"
            " VALUES (?, 'world-berrymoor', ?, ?, ?, ?, ?)",
            (f"{event_id}:reveal", event_id, actor_id, status, revealed_at, NOW),
        )
        writer.commit()
    finally:
        writer.close()


def _inject_actor(app_db: Path, actor_id: str, persona_id: str) -> None:
    """One extra cast actor (the ghost resident: a real builtin card's
    persona, no conversation bound to it)."""

    writer = sqlite3.connect(app_db, timeout=10)
    try:
        writer.execute(
            "INSERT INTO world_actor (actor_id, world_id, persona_id,"
            " created_at) VALUES (?, 'world-berrymoor', ?, ?)",
            (actor_id, persona_id, NOW),
        )
        writer.commit()
    finally:
        writer.close()


def _null_actor_face(
    app_db: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, _WebFace]:
    """A real host over a fresh app.db, opened on the calling thread (the
    web_stack worker's own posture — the thread that opens the host owns
    its connections), with the binding read answering the honest
    ``actor_id: None`` mapping. The seam is the only entrance a
    ``NULL``-actor binding has: migration 0023 pins
    ``world_conversation.actor_id NOT NULL``, so no durable write can
    produce the row — the arms below pin the defensive arm the mapping
    already carries, over real store and card data."""

    host = open_host(
        app_db,
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
    )
    face = _WebFace(host, "web-test")
    monkeypatch.setattr(
        face,
        "_world_binding",
        lambda: {
            "binding_id": "bind-web-test",
            "world_id": "world-berrymoor",
            "actor_id": None,
        },
    )
    return host, face


def _assert_note_absent(payload: Any, narration: str) -> None:
    """The narration appears nowhere in the payload (the JSON dump is the
    whole answer — one search over every block)."""

    assert narration not in json.dumps(payload, ensure_ascii=False)


class _NoWorldHost:
    """The stub host of the W-1-3 404 pin: a world leg no host has."""

    app_db_path = "stub.db"


def _stub_face() -> _WebFace:
    return _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1 — the guards: no binding is the inbox's own 404, on all three faces
# ---------------------------------------------------------------------------


def test_overview_404s_without_a_binding() -> None:
    """The overview does not exist for a conversation outside any world —
    the inbox's own sentence, verbatim (not an empty overview)."""

    status, payload = _stub_face().world_overview()
    inbox_status, inbox_payload = _stub_face().world_inbox()
    assert status == 404
    assert inbox_status == 404
    assert payload == {"error": inbox_payload["error"]}
    assert "没有绑定任何世界" in payload["error"]


def test_log_404s_without_a_binding() -> None:
    """The log's same guard — the same sentence, verbatim."""

    status, payload = _stub_face().world_log()
    inbox_status, inbox_payload = _stub_face().world_inbox()
    assert status == 404
    assert inbox_status == 404
    assert payload == {"error": inbox_payload["error"]}


def test_residents_404s_without_a_binding() -> None:
    """The roster's same guard — the same sentence, verbatim."""

    status, payload = _stub_face().world_residents()
    inbox_status, inbox_payload = _stub_face().world_inbox()
    assert status == 404
    assert inbox_status == 404
    assert payload == {"error": inbox_payload["error"]}


# ---------------------------------------------------------------------------
# 2 — the overview: quiet day, resident block, the derived story day
# ---------------------------------------------------------------------------


def test_overview_on_a_quiet_day_answers_honestly(tmp_path: Path) -> None:
    """A freshly bound world with nothing happened: the calendar's own
    start day, the quiet-day arm's human sentence, and the resident the
    binding names (the cast's first member, through the card join)."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/overview")
    assert status == 200
    assert payload["world_id"] == "world-berrymoor"
    assert payload["world_name"] == "Berrymoor"
    assert payload["ui_language"] == "zh"
    assert payload["date_localized"] == "9月14日 · Berrymoor"
    assert payload["today"] == {
        "quiet": True,
        "note": "今天风平浪静——还没有新的动静。",
    }
    assert payload["resident"] == {
        "actor_id": "actor-berrymoor-nell",
        "persona_id": "persona-nell-alder",
        "name": "Nell Alder",
    }


def test_overview_resident_is_null_when_the_binding_names_no_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``NULL``-actor binding (the world's own narration): nobody sits
    in the signature seat, and the resident block answers ``None`` — an
    honest absent, never a guessed resident (the seam-level arm: the
    table's own ``NOT NULL`` keeps the row itself out of reach)."""

    host, face = _null_actor_face(
        tmp_path / "null-actor.db", monkeypatch
    )
    try:
        status, payload = face.world_overview()
        assert status == 200
        assert payload["resident"] is None
        assert payload["world_name"] == "Berrymoor"
    finally:
        host.close()


def test_overview_story_day_is_derived_never_clocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The story day is ``calendar_start`` plus the happened events' own
    spans (one ``market_day`` = one day): the overview answers the story's
    date, today carries exactly that day's revealed note, and a wall
    clock pinned in 2099 changes nothing — the face reads the chronicle,
    never the clock. (The ``en`` row is switched in first so the note's
    English prose passes through verbatim — the zh face renders the
    package's own Chinese narration for a kind it carries.)"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, _ = stack.post(
            "/api/settings/ui_language", {"ui_language": "en"}
        )
        assert status == 200
        _inject_note(
            app_db,
            "e-derive-1",
            "market_day",
            "2025-09-15",
            actor_id=None,
            status="REVEALED",
            narration="The market square fills before noon.",
            revealed_at="2025-09-15T09:00:00+00:00",
        )
        status, payload = stack.get_json("/api/world/overview")
        assert status == 200
        assert payload["date_localized"] == "Sep 15 · Berrymoor"
        today = payload["today"]
        assert today["quiet"] is False
        assert [
            (note["narration"], note["signature"], note["moment"])
            for note in today["items"]
        ] == [("The market square fills before noon.", None, "market_day")]
        monkeypatch.setattr(elc.web, "datetime", _FarFutureDatetime)
        status, again = stack.get_json("/api/world/overview")
        assert status == 200
    assert again == payload


class _FarFutureDatetime(datetime):
    """A wall clock pinned in 2099 — the face under the pin must not
    notice it (everything else about ``datetime`` stays working)."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        moment = datetime(2099, 1, 1)
        return moment if tz is None else moment.replace(tzinfo=tz)


# ---------------------------------------------------------------------------
# 3 — the red line: reading never flips, the inbox alone does
# ---------------------------------------------------------------------------


def test_reading_never_flips_pending_only_the_inbox_does(
    tmp_path: Path,
) -> None:
    """The decisive triple: one ``PENDING`` note left by hand, then the
    overview read (the note survives, unread, and today does not show
    it), then the log read (the same), then the inbox read — the one
    presentation trigger — flips it ``REVEALED``. The durable queue's
    own count is the gauge after every leg. (WR-2 随迁: the letter no
    longer writes engine events — the note rides the world's own story
    day, ``calendar_start`` on an empty chronicle, and the turn leg is
    only here to prove the read faces ignore it.)"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == REPLY
        # The letter step with an unversed provider writes nothing: the
        # world's today stays the story's day zero.
        assert _ro_rows(
            app_db, "SELECT COUNT(*) FROM world_event"
        )[0][0] == 0
        # The day's revealed note (the old pre-step's own legacy shape —
        # what made today non-quiet) and the unread leg: a kind the
        # package does not carry (zero story days, the English row in
        # every language — the text stays searchable in the payloads).
        _inject_note(
            app_db,
            "today-revealed-1",
            "unread_kind",
            "2025-09-14",
            actor_id=None,
            status="REVEALED",
            narration="A note the world already showed.",
            revealed_at="2025-09-14T08:00:00+00:00",
        )
        _inject_note(
            app_db,
            "unread-pending-1",
            "unread_kind",
            "2025-09-14",
            actor_id=None,
            status="PENDING",
            narration=PENDING_NOTE,
        )
        assert _pending_count(app_db) == 1

        status, overview = stack.get_json("/api/world/overview")
        assert status == 200
        assert overview["today"]["quiet"] is False  # today has real notes
        _assert_note_absent(overview, PENDING_NOTE)
        assert _pending_count(app_db) == 1  # the read flipped nothing

        status, log = stack.get_json("/api/world/log")
        assert status == 200
        _assert_note_absent(log, PENDING_NOTE)
        assert _pending_count(app_db) == 1  # the log flipped nothing either

        status, inbox = stack.get_json("/api/world/inbox")
        assert status == 200
        assert _pending_count(app_db) == 0  # the inbox's read is the flip
        assert PENDING_NOTE in [
            item["narration"] for item in inbox["items"]
        ]

        status, residents = stack.get_json("/api/world/residents")
        assert status == 200
        nell = next(
            row
            for row in residents["residents"]
            if row["actor_id"] == "actor-berrymoor-nell"
        )
        assert nell["letters_count"] == 1


# ---------------------------------------------------------------------------
# 4 — the log: REVEALED only, story-day groups newest first, signatures
# ---------------------------------------------------------------------------


def test_log_groups_revealed_days_newest_first_and_hides_pending(
    tmp_path: Path,
) -> None:
    """Two revealed notes on two story days, one pending note between
    them: the log answers exactly two groups, newest day first, each
    item with its signature arm (the actor's card name, the world's own
    ``None``) and its reveal stamp — and the pending note appears
    nowhere, by text or by moment word."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, _ = stack.post(
            "/api/settings/ui_language", {"ui_language": "en"}
        )
        assert status == 200
        _inject_note(
            app_db,
            "e-log-17",
            "tam_at_the_flats",
            "2025-09-17",
            actor_id="actor-berrymoor-nell",
            status="REVEALED",
            narration="Tam waves from the flats.",
            revealed_at="2025-09-17T08:00:00+00:00",
        )
        _inject_note(
            app_db,
            "e-log-16",
            "borrowed_morning",
            "2025-09-16",
            actor_id=None,
            status="PENDING",
            narration=PENDING_NOTE,
        )
        _inject_note(
            app_db,
            "e-log-15",
            "harbour_fog",
            "2025-09-15",
            actor_id=None,
            status="REVEALED",
            narration="Fog swallows the quay.",
            revealed_at="2025-09-15T07:00:00+00:00",
        )
        status, payload = stack.get_json("/api/world/log")
    assert status == 200
    assert payload["world_name"] == "Berrymoor"
    assert payload["ui_language"] == "en"
    assert [day["date_localized"] for day in payload["days"]] == [
        "Sep 17",
        "Sep 15",
    ]
    first, second = payload["days"]
    assert [
        (
            item["narration"],
            item["signature"],
            item["revealed_at"],
        )
        for item in first["items"]
    ] == [("Tam waves from the flats.", "Nell Alder",
           "2025-09-17T08:00:00+00:00")]
    assert [
        (item["narration"], item["signature"])
        for item in second["items"]
    ] == [("Fog swallows the quay.", None)]
    assert set(first["items"][0]) == {
        "narration",
        "moment",
        "signature",
        "revealed_at",
        "fallback",
    }
    _assert_note_absent(payload, PENDING_NOTE)
    assert "borrowed_morning" not in [
        item["moment"] for day in payload["days"] for item in day["items"]
    ]


# ---------------------------------------------------------------------------
# 5 — the residents: the roster, the current mark, the honest zeros
# ---------------------------------------------------------------------------


def test_residents_roster_joins_the_cards_builtin_first(
    tmp_path: Path,
) -> None:
    """Every cast actor rides its card (name, persona, identity) in the
    roster's own serving order — the ghost actor's builtin card
    (``cpkg-evelyn-hart``) sorts before the penpal's
    (``cpkg-nell-alder``), both before nothing else: one deterministic
    order, no second roster."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _inject_actor(app_db, "actor-berrymoor-ghost", "persona-evelyn-hart")
        status, payload = stack.get_json("/api/world/residents")
    assert status == 200
    assert payload["world_name"] == "Berrymoor"
    rows = payload["residents"]
    assert [
        (row["actor_id"], row["name"], row["persona_id"]) for row in rows
    ] == [
        ("actor-berrymoor-ghost", "Evelyn Hart", "persona-evelyn-hart"),
        ("actor-berrymoor-nell", "Nell Alder", "persona-nell-alder"),
    ]
    assert all(isinstance(row["identity"], str) for row in rows)
    assert all(row["identity"] for row in rows)
    # wf-0 处置（评审 LOW-1）：双居民面上的「恰一真」——单成员世界的
    # exactly-one 钉退化（m6b 形态），这里补上多居民断言：ghost 非当前、
    # nell 当前，恰一真，永不全真。
    assert [row["is_current"] for row in rows] == [False, True]


def test_residents_is_current_marks_exactly_one(tmp_path: Path) -> None:
    """With the binding naming nell, exactly one resident is current —
    the mark reads the binding, never a guess."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/residents")
        assert status == 200
        assert [
            (row["actor_id"], row["is_current"])
            for row in payload["residents"]
        ] == [("actor-berrymoor-nell", True)]


def test_residents_mark_all_false_when_the_binding_names_no_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``NULL``-actor arm over real store and card data: nobody is
    current — the marking rule's honest other half, pinned at the same
    binding seam the table's own ``NOT NULL`` makes durable-unreachable."""

    host, face = _null_actor_face(
        tmp_path / "null-actor-roster.db", monkeypatch
    )
    try:
        status, payload = face.world_residents()
        assert status == 200
        assert [
            (row["actor_id"], row["is_current"], row["letters_count"])
            for row in payload["residents"]
        ] == [("actor-berrymoor-nell", False, 0)]
    finally:
        host.close()


def test_residents_letters_count_answers_honest_zeros(
    tmp_path: Path,
) -> None:
    """The letter count's zeros: a resident with no bound conversation
    answers 0 (nobody has written them), and a resident whose bound
    conversation has no letters yet answers the same 0 through the
    history window's own read."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _inject_actor(app_db, "actor-berrymoor-ghost", "persona-evelyn-hart")
        status, payload = stack.get_json("/api/world/residents")
        assert status == 200
        assert {
            row["actor_id"]: row["letters_count"]
            for row in payload["residents"]
        } == {
            "actor-berrymoor-ghost": 0,
            "actor-berrymoor-nell": 0,
        }


# ---------------------------------------------------------------------------
# 6 — the languages: the W-L row moves dates and the quiet-day sentence
# ---------------------------------------------------------------------------


def test_overview_reads_in_both_interface_languages(tmp_path: Path) -> None:
    """The default ``zh`` answer, then the stored ``en`` one: the story
    day's localization and the quiet-day sentence follow the interface
    language row — the same law the inbox's bilingual face keeps."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, zh = stack.get_json("/api/world/overview")
        assert status == 200
        assert zh["ui_language"] == "zh"
        assert zh["date_localized"] == "9月14日 · Berrymoor"
        assert zh["today"]["note"] == "今天风平浪静——还没有新的动静。"
        status, _ = stack.post(
            "/api/settings/ui_language", {"ui_language": "en"}
        )
        assert status == 200
        status, en = stack.get_json("/api/world/overview")
        assert status == 200
        assert en["ui_language"] == "en"
        assert en["date_localized"] == "Sep 14 · Berrymoor"
        assert en["today"]["note"] == "A quiet day — nothing new has come ashore."


def test_log_group_dates_follow_the_interface_language(
    tmp_path: Path,
) -> None:
    """The log's group headlines localize with the same row: zh spellings
    before the switch, the written-out English month table after."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _inject_note(
            app_db,
            "e-lang-17",
            "tam_at_the_flats",
            "2025-09-17",
            actor_id=None,
            status="REVEALED",
            narration="Tam waves from the flats.",
            revealed_at="2025-09-17T08:00:00+00:00",
        )
        _inject_note(
            app_db,
            "e-lang-15",
            "harbour_fog",
            "2025-09-15",
            actor_id=None,
            status="REVEALED",
            narration="Fog swallows the quay.",
            revealed_at="2025-09-15T07:00:00+00:00",
        )
        status, zh = stack.get_json("/api/world/log")
        assert status == 200
        assert [day["date_localized"] for day in zh["days"]] == [
            "9月17日",
            "9月15日",
        ]
        status, _ = stack.post(
            "/api/settings/ui_language", {"ui_language": "en"}
        )
        assert status == 200
        status, en = stack.get_json("/api/world/log")
        assert status == 200
        assert [day["date_localized"] for day in en["days"]] == [
            "Sep 17",
            "Sep 15",
        ]


# ---------------------------------------------------------------------------
# 7 — the structural pin: the read faces never call reveal_all
# ---------------------------------------------------------------------------


def test_the_read_faces_never_call_reveal_all() -> None:
    """AST-level over the web.py source: the three read faces and every
    helper they share contain zero ``reveal_all`` calls — reading is not
    opening. The walker's positive control: the one presentation
    trigger that legitimately keeps the call (the inbox's atomic
    reveal) is still seen. (WR-2 随迁: the turn wiring's old
    presentation step is retired with the pre-step — the letter step
    leaves its notes pending and never reveals.)"""

    source = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    face = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_WebFace"
    )
    methods = {
        node.name: node
        for node in face.body
        if isinstance(node, ast.FunctionDef)
    }

    def reveal_calls(name: str) -> int:
        return sum(
            1
            for node in ast.walk(methods[name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "reveal_all"
        )

    read_faces = (
        "world_overview",
        "world_log",
        "world_residents",
        "_world_reveal_items",
        "_world_notes_joined",
        "_world_actor_cards",
        "_world_resident_face",
        "_world_letter_count",
    )
    for name in read_faces:
        assert reveal_calls(name) == 0, name
    for name in ("world_inbox",):
        assert reveal_calls(name) == 1, name
