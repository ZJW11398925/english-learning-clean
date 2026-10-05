"""A2 — the narrative order, the story's own calendar, and the story
block as the world's only presentation (the 23 pins).

The streamed turn tells the world's story **before** the reply starts to
arrive (DEC-…82: 世界故事先讲，回信自然接上——事件序 world → delta＊ →
final), the reply is typed at a fixed pace (到达与渲染解耦), and the
world's time is the **virtual calendar** (DEC-…88, revised by DEC-…90:
story-driven — the events' own spans summed on ``calendar_start``, never
a letter count, never a wall clock). DEC-…92 retires the resident inbox
region (世界呈现唯一形态 = 内联故事块; the load arm renders only what it
actually revealed), and A2R (DEC-…99) retires the 「继续」 interaction
whole — the engine's NOTICE event is a beat, not a pause, so one letter
plays the run's whole story and nothing waits mid-run. The slice VAL
groups, each a section below:

1. **the narrative order, end to end** — a live streamed turn answers
   one ``world`` frame (the story block's data) before the first delta
   and the one final; the streamed turn advances the world **exactly
   once** (the pre-step, not the turn's own wiring — one turn, one
   event, one run), and the final still carries ``world_step_note``
   (the blocking shape's key, byte for byte);
2. **the story data** — the frame's notes carry the package's Chinese
   prose by default, follow the ``ui_language`` write, and are
   **already revealed** when they reach the page (呈现即读即揭示 — the
   reveal runs with the pre-step, nothing left pending for the reread);
3. **the blocking turn is untouched** — ``/api/turn`` keeps its own
   post-commit wiring (one event, the note in its payload);
4. **the virtual calendar** — story days sum the happened events'
   spans; the same letter count with a different story answers a
   different day (与信数无关); an event stamps at the **end of its own
   span**; runs accumulate and replay to the same dates; a legacy
   real-timestamp row renders **no** date at all (诚实退化); a
   ``run_step`` without a package keeps the caller's moment (the
   engine-direct callers' unchanged shape);
5. **current-run presentation** — the inbox shows only the latest
   run's notes; the letter-count grouping (「第 N 封信后的世界」) is
   retired in source; the quiet-day arm is pinned;
6. **zero real time in the presentation; the resident region retired**
   — the world presentation faces' source carries no clock read, the
   story block stays inert text (textContent only), the resident inbox
   region and its mount are gone at the source, the 「继续」 interaction
   is retired whole (A2R DEC-…99 — the engine never pauses, so no
   button, no branch, no endpoint), and the load arm renders only what
   it actually revealed (``revealed_now``);
7. **the served calendar** — the shipped package drives the story day
   (the frame's day equals the event's own stamp; the full pool's spans
   land the story's last day on 2025-09-21).
"""

from __future__ import annotations

import inspect
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Ok
from elc.web import _localize_story_date, _WebFace
from elc.world.engine.orchestrate import TRIGGER_LETTER, run_step
from elc.world.engine.types import EngineConfig, MomentKind, PoolEvent
from elc.world.package import (
    WORLD_PACKAGE_VERSION,
    SupplyDeclaration,
    WorldPackage,
    load_world_package,
    story_days_of,
    world_date_of,
)
from elc.world.store import SqliteWorldStore
from tests.host.test_a1_streaming import (
    A1_TEXT,
    REPLY,
    WEBUI,
    _FakeOpenAI,
    _openai_stack,
    _post,
    _sse_frames,
)
from tests.host.test_w1_web import CLEAN_TEXT, web_stack

REPO = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO / "worlds" / "berrymoor.json"
NOW = "2026-10-05T00:00:00+00:00"
WORLD = "world-main"

# Berrymoor's story spans (the shipped configuration, DEC-…90): the sum
# over the whole pool is 7 days, so the full story ends on 2025-09-21.
BERRYMOOR_START = "2025-09-14"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection (the w13 fixture
    shape) for the calendar's domain-level tests."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows off the serving database through a fresh
    read-only connection (the W-4 ro posture — the worker thread owns
    the writable one; a same-thread check would refuse the test's)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(ro.execute(sql).fetchall())
    finally:
        ro.close()


def _span_package(
    world_id: str = WORLD,
    calendar_start: str = BERRYMOOR_START,
    spans: tuple[tuple[str, int, str], ...] = (
        ("beat", 0, "NOTICE"),
        ("stretch", 3, "NOTICE"),
    ),
) -> WorldPackage:
    """One small package whose events carry explicit story spans — the
    calendar's own test double."""

    return WorldPackage(
        world_id=world_id,
        name="Calendar",
        version=WORLD_PACKAGE_VERSION,
        calendar_start=calendar_start,
        setting=("One paragraph of setting.",),
        cast=(),
        event_pool=tuple(
            PoolEvent(
                kind=kind,
                narration=f"The {kind} happens.",
                moment=MomentKind(word),
                days=days,
            )
            for kind, days, word in spans
        ),
        supply=SupplyDeclaration(
            families=("DISC",),
            note="declared-not-consumed",
        ),
    )


# ---------------------------------------------------------------------------
# 1 — the narrative order, end to end
# ---------------------------------------------------------------------------


def test_the_stream_tells_the_world_first(tmp_path: Path) -> None:
    """The streamed turn's event order is world → delta＊ → final: the
    story frame lands before the first generation increment, and the
    frame carries the story block's data (the world's name, its
    virtual-calendar day localized, the interface language, this run's
    notes — A2R DEC-…99: one call's whole beat run, eight events to the
    ceiling)."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            frames = _sse_frames(raw)
            assert [f["type"] for f in frames][:1] == ["world"]
            assert frames[-1]["type"] == "final"
            assert [f["type"] for f in frames][1:-1] == ["delta"] * len(REPLY)
            world = frames[0]
            assert world["world_name"] == "Berrymoor"
            assert world["ui_language"] == "zh"
            assert len(world["notes"]) == 8
            # The frame's day is the story's current day — the run's own
            # last event's stamp, localized (the calendar sums the whole
            # happened story, not the first note's).
            assert world["date_localized"] == _localize_story_date(
                world["notes"][-1]["occurred_at"], "zh", "Berrymoor"
            )
            for note in world["notes"]:
                assert note["occurred_at"].startswith("2025-09-")
    finally:
        endpoint.stop()


def test_the_streamed_turn_advances_the_world_exactly_once(
    tmp_path: Path,
) -> None:
    """One streamed turn, one world advance: the pre-step runs the
    letter trigger and the turn itself skips its own wiring — one run
    row, that run's whole beat set (eight events to the ceiling), zero
    pending after the reveal; a second stream winds the next run and
    adds exactly that run's events (no double advance)."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            app_db = tmp_path / "app.db"
            _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
            runs = _ro_rows(app_db, "SELECT COUNT(*) FROM world_run")[0][0]
            events = _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[
                0
            ][0]
            pending = _ro_rows(
                app_db,
                "SELECT COUNT(*) FROM world_reveal_item"
                " WHERE status = 'PENDING'",
            )[0][0]
            assert (runs, events, pending) == (1, 8, 0)
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            frames = _sse_frames(raw)
            assert frames[0]["type"] == "world"
            # This run's notes only (current-run presentation): the
            # second run's own step — the settled facts of the first
            # story widen the mature set, and its seed draws straight
            # into a RESPONSE stop.
            assert len(frames[0]["notes"]) == 1
            assert _ro_rows(
                app_db, "SELECT COUNT(*) FROM world_event"
            )[0][0] == 9
    finally:
        endpoint.stop()


def test_the_final_still_carries_the_world_step_note(
    tmp_path: Path,
) -> None:
    """The final's payload keeps the blocking shape byte for byte: the
    ``world_step_note`` key is present (a successful pre-step answers
    ``None``) and the rest of the keys are exactly ``/api/turn``'s."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            final = _sse_frames(raw)[-1]
            assert final["type"] == "final"
            assert "world_step_note" in final
            assert final["world_step_note"] is None
            assert final["reply"] == REPLY
    finally:
        endpoint.stop()


# ---------------------------------------------------------------------------
# 2 — the story data: language and the reveal that rode the pre-step
# ---------------------------------------------------------------------------


def test_the_story_notes_carry_the_chinese_prose(tmp_path: Path) -> None:
    """The default interface language is zh: the frame's note renders
    the package's own Chinese prose (CJK script), ``fallback`` false —
    the primary, not a stand-in."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            note = _sse_frames(raw)[0]["notes"][0]
            assert re.search(r"[\u4e00-\u9fff]", note["narration"])
            assert note["fallback"] is False
    finally:
        endpoint.stop()


def test_the_story_follows_the_ui_language(tmp_path: Path) -> None:
    """The interface write moves the story's language: after the page
    writes ``ui_language: en``, the frame's note renders the English
    row and says ``fallback: false`` (the primary language, not a
    fallback), and the date line answers in English."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, _ = stack.post(
                "/api/settings/ui_language", {"ui_language": "en"}
            )
            assert status == 200
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            world = _sse_frames(raw)[0]
            assert world["ui_language"] == "en"
            assert re.fullmatch(
                r"(Sep|Oct) \d{1,2} · Berrymoor", world["date_localized"]
            ), world["date_localized"]
            note = world["notes"][0]
            latin = note["narration"]
            assert latin and not re.search(r"[\u4e00-\u9fff]", latin)
            assert note["fallback"] is False
    finally:
        endpoint.stop()


def test_the_story_notes_are_already_revealed(tmp_path: Path) -> None:
    """呈现即读即揭示: the story frame's notes are already ``REVEALED``
    when the page later rereads the inbox — the reveal rode the
    pre-step, so the reread adds nothing new (nothing left pending)."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            story = _sse_frames(raw)[0]
            status, inbox = stack.get_json("/api/world/inbox")
            assert status == 200
            # The frame's note and the inbox's note are the same fact:
            # one per step, already revealed, no second copy.
            assert len(inbox["items"]) == len(story["notes"])
            for note in inbox["items"]:
                assert note["status"] == "REVEALED"
                assert note["story_date"] is not None
    finally:
        endpoint.stop()


# ---------------------------------------------------------------------------
# 3 — the blocking turn keeps its own wiring
# ---------------------------------------------------------------------------


def test_the_blocking_turn_keeps_its_own_wiring(tmp_path: Path) -> None:
    """/api/turn is untouched by the narrative order: the world steps
    after the commit, inside the turn (its run's whole beat set — eight
    events to the ceiling), and the reply's own ``world_step_note``
    answers ``None`` for the successful step."""

    with web_stack(tmp_path / "app.db") as stack:
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == REPLY
        assert turn["world_step_note"] is None
        assert _ro_rows(
            tmp_path / "app.db", "SELECT COUNT(*) FROM world_event"
        )[0][0] == 8


# ---------------------------------------------------------------------------
# 4 — the virtual calendar (story-driven, DEC-…90)
# ---------------------------------------------------------------------------


def test_story_days_sum_happened_events(
    store: SqliteWorldStore,
) -> None:
    """The world's day is ``calendar_start`` plus the happened events'
    spans — zero events answer the start day itself, and the spans sum
    over exactly the events the step wrote (read back from the step's
    own trace, A2R DEC-…99: one call writes a whole beat run)."""

    package = _span_package()
    store.create_world(package.world_id, package.name, None, NOW)
    assert world_date_of(package, store, package.world_id) == BERRYMOOR_START
    assert story_days_of(package, store, package.world_id) == 0
    stepped = run_step(
        store,
        package.world_id,
        package.to_event_pool(),
        EngineConfig(),
        TRIGGER_LETTER,
        NOW,
        package=package,
    )
    assert isinstance(stepped, Ok)
    # The day is the sum of the spans the step actually wrote — read
    # from the trace, the calendar never invents a span of its own.
    spans = {event.kind: event.days for event in package.event_pool}
    expected = sum(
        spans[cycle.selected]
        for cycle in stepped.value.cycles
        if cycle.selected is not None
    )
    assert len(stepped.value.cycles) == 8  # the ceiling's beat run
    assert story_days_of(package, store, package.world_id) == expected
    assert world_date_of(package, store, package.world_id) == (
        date.fromisoformat(BERRYMOOR_START) + timedelta(days=expected)
    ).isoformat()
    # A negative span is refused at the record shape itself (the loader
    # refuses it too; this is the direct-construction arm).
    with pytest.raises(ValueError):
        PoolEvent(kind="bad", narration="n", days=-1)


def test_same_letter_count_different_story_different_day(
    conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """与信数无关: two worlds at the same run count answer different
    days when their stories' spans differ — the calendar is the story's,
    never the letter counter's."""

    quiet = _span_package(
        world_id="world-quiet",
        spans=(("beat", 0, "NOTICE"),),
    )
    long_story = _span_package(
        world_id="world-long",
        spans=(("stretch", 5, "NOTICE"),),
    )
    store = SqliteWorldStore(conn, open_runtime_epoch(conn))
    for package in (quiet, long_story):
        store.create_world(package.world_id, package.name, None, NOW)
        for _ in range(2):
            stepped = run_step(
                store,
                package.world_id,
                package.to_event_pool(),
                EngineConfig(),
                TRIGGER_LETTER,
                NOW,
                package=package,
            )
            # The one-event pool is always mature: each letter winds a
            # run (the previous one hit its ceiling) and writes a whole
            # beat run — two letters, two runs, either way.
            assert isinstance(stepped, Ok)
        assert len(store.list_runs(package.world_id)) == 2
    assert story_days_of(quiet, store, "world-quiet") == 0
    assert story_days_of(long_story, store, "world-long") == 80
    assert world_date_of(quiet, store, "world-quiet") != world_date_of(
        long_story, store, "world-long"
    )


def test_the_event_stamps_at_its_span_end(
    store: SqliteWorldStore,
) -> None:
    """落笔在跨度之末: the run's first event moment is ``calendar_start``
    plus this event's own span (an empty history's first stamp), and
    every later beat in the call accumulates on it (three days per
    beat, beat after beat); the reveal item inherits its own event's
    moment."""

    package = _span_package(
        spans=(("stretch", 3, "NOTICE"),),
    )
    store.create_world(package.world_id, package.name, None, NOW)
    stepped = run_step(
        store,
        package.world_id,
        package.to_event_pool(),
        EngineConfig(),
        TRIGGER_LETTER,
        NOW,
        package=package,
    )
    assert isinstance(stepped, Ok)
    rows = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT occurred_at FROM world_event ORDER BY event_id ASC"
    ).fetchall()
    assert len(rows) == 8
    stamps = [str(r[0]) for r in rows]
    # The first beat lands at the end of its own span; each later beat
    # rides three more days (the same span, accumulated).
    assert stamps == [
        (date.fromisoformat(BERRYMOOR_START) + timedelta(days=3 * (k + 1))).isoformat()
        for k in range(8)
    ]
    items = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT created_at FROM world_reveal_item ORDER BY item_id ASC"
    ).fetchall()
    assert len(items) == 8
    assert [str(i[0]) for i in items] == stamps


def test_runs_accumulate_and_replay_to_the_same_dates(
    tmp_path: Path,
) -> None:
    """Two steps accumulate (each stamp rides on every happened span
    before it, including the beats of the same call), and the same
    history replayed on a fresh store answers the same dates — the
    calendar is a pure function of the chronicle."""

    def _play(path: Path) -> list[str]:
        db = sqlite3.connect(path)
        db.execute("PRAGMA foreign_keys=ON")
        apply_migrations(db)
        world_store = SqliteWorldStore(db, open_runtime_epoch(db))
        package = _span_package(
            spans=(("first", 2, "NOTICE"), ("second", 1, "NOTICE"))
        )
        world_store.create_world(package.world_id, package.name, None, NOW)
        spans = {event.kind: event.days for event in package.event_pool}
        expected: list[str] = []
        total = 0
        for _ in range(2):
            stepped = run_step(
                world_store,
                package.world_id,
                package.to_event_pool(),
                EngineConfig(),
                TRIGGER_LETTER,
                NOW,
                package=package,
            )
            assert isinstance(stepped, Ok)
            for cycle in stepped.value.cycles:
                if cycle.selected is None:
                    continue
                total += spans[cycle.selected]
                expected.append(
                    (date.fromisoformat(BERRYMOOR_START) + timedelta(days=total))
                    .isoformat()
                )
        rows = world_store._conn.execute(  # noqa: SLF001 — test read
            "SELECT occurred_at FROM world_event ORDER BY event_id ASC"
        ).fetchall()
        stamps = [str(r[0]) for r in rows]
        assert len(stamps) == len(expected) == 16
        assert stamps == expected
        db.close()
        return stamps

    first = _play(tmp_path / "a.db")
    second = _play(tmp_path / "b.db")
    assert first == second


def test_legacy_realtime_rows_render_no_date(tmp_path: Path) -> None:
    """A legacy row whose ``occurred_at`` carries a real wall-clock
    moment answers ``story_date: None`` — an honest old row renders no
    date at all, never a fabricated story day (DEC-…88 ④'s retirement
    arm). The row is injected inside the current run so the
    current-run filter does not hide it."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, _ = _post(stack.port, "/api/turn", {"text": CLEAN_TEXT})
            assert status == 200
            app_db = tmp_path / "app.db"
            current_run = _ro_rows(
                app_db,
                "SELECT run_id FROM world_run ORDER BY created_at DESC,"
                " run_id DESC LIMIT 1",
            )[0][0]
            # The injection rides its own short-lived writable connection
            # (the worker thread owns the serving one and sits idle in
            # its work loop while this runs).
            writer = sqlite3.connect(app_db, timeout=10)
            try:
                writer.execute(
                    "INSERT INTO world_event (event_id, world_id, kind,"
                    " narration, effects, occurred_at, source)"
                    " VALUES (?, 'world-berrymoor', 'old_kind', 'An old"
                    " letter-time note.', '[]',"
                    " '2026-10-05T12:00:00+00:00', 'test')",
                    (f"{current_run}:99",),
                )
                writer.execute(
                    "INSERT INTO world_reveal_item (item_id, world_id,"
                    " source_event_id, actor_id, status, revealed_at,"
                    " created_at)"
                    " VALUES (?, 'world-berrymoor', ?, NULL, 'PENDING',"
                    " NULL, ?)",
                    (f"{current_run}:99:reveal", f"{current_run}:99", NOW),
                )
                writer.commit()
            finally:
                writer.close()
            status, inbox = stack.get_json("/api/world/inbox")
            assert status == 200
            legacy = [
                note
                for note in inbox["items"]
                if str(note["id"]).endswith(":99:reveal")
            ]
            assert len(legacy) == 1
            assert legacy[0]["story_date"] is None
    finally:
        endpoint.stop()


def test_run_step_without_a_package_keeps_the_callers_moment(
    store: SqliteWorldStore,
) -> None:
    """The engine-direct callers' unchanged shape: a ``run_step`` with
    no package stamps the events with the caller's ``now`` exactly as
    before A2 (the virtual calendar is opt-in through the package)."""

    package = _span_package()
    store.create_world(package.world_id, package.name, None, NOW)
    stepped = run_step(
        store,
        package.world_id,
        package.to_event_pool(),
        EngineConfig(),
        TRIGGER_LETTER,
        NOW,
    )
    assert isinstance(stepped, Ok)
    row = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT occurred_at FROM world_event"
    ).fetchone()
    assert row is not None
    assert row[0] == NOW


def test_the_inbox_payload_counts_its_own_reveal(tmp_path: Path) -> None:
    """DEC-…92's data half: the inbox payload answers ``revealed_now``
    — the count of PENDING notes **this very read** flipped (counted
    before the flip). A clean world reads zero; a note left pending by
    hand (the last session's unread leg) reads one and rides the
    items."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, _ = _post(stack.port, "/api/turn", {"text": CLEAN_TEXT})
            assert status == 200
            status, payload = stack.get_json("/api/world/inbox")
            assert status == 200
            assert payload["revealed_now"] == 0  # nothing left unread
            app_db = tmp_path / "app.db"
            current_run = _ro_rows(
                app_db,
                "SELECT run_id FROM world_run ORDER BY created_at DESC,"
                " run_id DESC LIMIT 1",
            )[0][0]
            writer = sqlite3.connect(app_db, timeout=10)
            try:
                writer.execute(
                    "INSERT INTO world_event (event_id, world_id, kind,"
                    " narration, effects, occurred_at, source)"
                    " VALUES (?, 'world-berrymoor', 'left_kind', 'A note"
                    " the last session never read.', '[]',"
                    " '2025-09-18', 'test')",
                    (f"{current_run}:98",),
                )
                writer.execute(
                    "INSERT INTO world_reveal_item (item_id, world_id,"
                    " source_event_id, actor_id, status, revealed_at,"
                    " created_at)"
                    " VALUES (?, 'world-berrymoor', ?, NULL, 'PENDING',"
                    " NULL, ?)",
                    (f"{current_run}:98:reveal", f"{current_run}:98", NOW),
                )
                writer.commit()
            finally:
                writer.close()
            status, payload = stack.get_json("/api/world/inbox")
            assert status == 200
            assert payload["revealed_now"] == 1
            assert any(
                str(note["id"]).endswith(":98:reveal")
                for note in payload["items"]
            )
    finally:
        endpoint.stop()


def test_the_streamed_frame_names_the_checkpoint(tmp_path: Path) -> None:
    """The streamed world frame carries ``at_checkpoint`` and it answers
    **False** on every reachable path (A2R DEC-…99: the engine never
    pauses mid-run — the run is at its stop the moment the frame flies),
    and the frame's bit matches the inbox's (one run row, one truth)."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            world = _sse_frames(raw)[0]
            assert world["at_checkpoint"] is False
            status, inbox = stack.get_json("/api/world/inbox")
            assert status == 200
            assert inbox["at_checkpoint"] == world["at_checkpoint"]
    finally:
        endpoint.stop()


# ---------------------------------------------------------------------------
# 5 — current-run presentation; the grouping retired in source
# ---------------------------------------------------------------------------


def test_the_inbox_shows_only_the_latest_run(tmp_path: Path) -> None:
    """The inbox is current-run only: the first letter's run hits its
    own ceiling (A2R DEC-…99), so the second letter winds a fresh run
    and the payload carries exactly that run's notes — the first run's
    notes stay durable and out of sight (the world's own log face is a
    later cut's)."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
            status, inbox = stack.get_json("/api/world/inbox")
            assert status == 200
            first_ids = [str(note["id"]) for note in inbox["items"]]
            assert len(first_ids) == 8
            assert all(
                item_id.startswith("run-berrymoor-0000:")
                for item_id in first_ids
            )
            # The first run is already finished (its own ceiling), so
            # the next letter winds a new one — no hand-rolled UPDATE.
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            status, inbox = stack.get_json("/api/world/inbox")
            assert status == 200
            ids = [str(note["id"]) for note in inbox["items"]]
            assert len(ids) == 1
            assert ids[0].startswith("run-berrymoor-0001:")
            assert ids[0].endswith(":0:reveal")
    finally:
        endpoint.stop()


def test_the_letter_count_grouping_is_retired() -> None:
    """「第 N 封信后的世界 / After letter N」 is retired at the source:
    neither the page's grouping helper nor the style's group head
    survives this cut (以信计框违背「与写信次数无关」) — the rule is
    gone (the comment may name what it retired)."""

    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")
    css_source = (WEBUI / "components.css").read_text(encoding="utf-8")
    assert "runHead" not in app_source
    assert "worldRunNumberOf" not in app_source
    assert "封信后的世界" not in app_source
    assert "After letter" not in app_source
    assert ".world-run-head {" not in css_source
    assert ".world-story {" in css_source


def test_the_permanent_inbox_region_is_retired() -> None:
    """DEC-…92: the resident inbox region is gone at the source — no
    ``worldInboxSec``, no bottom mount (the ``insertAdjacentElement``
    wiring the user's report pointed at), no resident board; the
    world's only presentation is the inline story block (the streamed
    frame and the load arm both ride ``renderWorldStory``), and the
    empty-state sentence of the retired region has no carrier left."""

    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")
    css_source = (WEBUI / "components.css").read_text(encoding="utf-8")
    assert "worldInboxSec" not in app_source
    assert "worldInboxBoard" not in app_source
    assert "worldInboxHead" not in app_source
    assert 'insertAdjacentElement("afterend"' not in app_source
    assert "renderWorldInbox" not in app_source
    assert "worldNoteCard" not in app_source
    assert ".world-inbox" not in css_source
    # The resident region's own strings retired with it (the .90 empty
    # sentence's carrier went with the region; the quiet-day arm is the
    # story block's own).
    assert "世界收件箱" not in app_source
    assert "世界安静着" not in app_source
    assert "The world is quiet" not in app_source


def test_the_continue_button_is_retired_from_the_story_block() -> None:
    """A2R (DEC-…99): the 「继续」 interaction is retired whole — the
    story block carries no checkpoint branch, no actions row, no
    continue fetch, and no dead button strings (the engine never pauses
    mid-run, so the page has nothing to wait for); the inbox payload's
    ``at_checkpoint`` bit stays (the run row's own state, read by the
    same source as ever — false on every reachable path)."""

    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")
    start = app_source.index("function renderWorldStory")
    end = app_source.index("\nasync function loadWorldInbox")
    story = app_source[start:end]
    assert "event.at_checkpoint" not in story
    assert "fetchWorldContinue" not in story
    assert "world-story-actions" not in story
    assert "世界没能继续" not in app_source
    # The streamed frame still carries the bit (the face reads it from
    # the run row — the same source the inbox answers from).
    web_source = (REPO / "src" / "elc" / "web.py").read_text(
        encoding="utf-8"
    )
    assert '"at_checkpoint": world["at_checkpoint"]' in web_source
    assert 'latest_run.status.value == "AT_CHECKPOINT"' in web_source
    # The endpoint behind the retired button is gone with it.
    assert "world/continue" not in web_source
    assert "def world_continue" not in web_source


def test_the_load_arm_renders_only_unrevealed_notes() -> None:
    """DEC-…92's load arm: the page reads the world once after the
    history lands, and renders a story block **only** when that read
    revealed notes left unread from the last session (``revealed_now``
    — counted server-side before the flip); zero legacy ⇒ zero world
    blocks, the conversation's tail stays clean."""

    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")
    start = app_source.index("async function loadWorldInbox")
    end = app_source.index("\n", app_source.index("return data;", start))
    load_arm = app_source[start:end]
    assert "revealed_now" in load_arm
    assert "renderWorldStory(data" in load_arm
    # The history-first ordering: the load rides after loadHistory (the
    # block lands after the last letter).
    init_block = app_source[app_source.index("loadHistory()"):]
    assert "loadHistory()" in app_source
    assert ".then(() => loadWorldInbox())" in init_block
    # The turn's own reread is retired (the pre-step already revealed).
    postturn = app_source[
        app_source.index("async function postTurn"):
        app_source.index("async function postTeachMe")
    ]
    assert "loadWorldInbox" not in postturn


def test_the_quiet_day_arm_is_pinned_in_source() -> None:
    """The story block's two-language arms sit in the page's source:
    the quiet-day sentence (zero notes), the transition into the reply,
    and the fallback note's honest wording (the retired region's own
    strings are pinned gone by the retirement test above)."""

    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "安静的一天，没什么特殊的事。" in app_source
    assert "A quiet day, nothing out of the ordinary." in app_source
    assert "这时，她收到了你的来信。" in app_source
    assert "Then, your letter arrives." in app_source
    assert "（这张便条写在世界学会中文之前——示以原文。）" in app_source
    assert "function renderWorldStory" in app_source
    assert 'event.type === "world"' in (
        (WEBUI / "api.js").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# 6 — zero real time in the presentation; the inert text
# ---------------------------------------------------------------------------


def test_the_world_presentation_faces_never_read_a_clock() -> None:
    """DEC-…88 ④'s retirement is structural: the world presentation
    faces' source carries no clock read — the story block, the frame
    assembly and the inbox payload render from the virtual calendar
    only."""

    for face_name in (
        _WebFace._world_payload,
        _WebFace._story_notes,
        _WebFace._world_event_payload,
        _WebFace._note_narration,
    ):
        source = inspect.getsource(face_name)
        assert "datetime.now" not in source, face_name.__name__
        assert "utcnow" not in source, face_name.__name__
    module_source = inspect.getsource(_localize_story_date)
    assert "datetime" not in module_source
    assert "now(" not in module_source


def test_the_story_block_stays_inert_text() -> None:
    """The page's story paths stay on the XSS discipline: the story
    block's own function carries no markup sink — textContent only."""

    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")
    start = app_source.index("function renderWorldStory")
    end = app_source.index("\n}", start)
    story = app_source[start:end]
    assert "innerHTML" not in story
    assert "insertAdjacentHTML" not in story
    assert "textContent" in story


# ---------------------------------------------------------------------------
# 7 — the served calendar: the shipped package drives the story day
# ---------------------------------------------------------------------------


def test_the_shipped_package_sums_to_its_last_day() -> None:
    """The shipped Berrymoor configuration: v3, the start day, ten
    events, and the full pool's spans landing the story's last day on
    2025-09-21 — the shipped reading of DEC-…90's story-driven
    calendar."""

    result = load_world_package(PACKAGE_PATH)
    assert isinstance(result, Ok), result.error.message
    package = result.value
    assert package.version == 3
    assert package.calendar_start == BERRYMOOR_START
    assert len(package.event_pool) == 10
    assert sum(event.days for event in package.event_pool) == 7
    last = date.fromisoformat(BERRYMOOR_START) + timedelta(days=7)
    assert last.isoformat() == "2025-09-21"
    # The served stack's world date derives through the same faces the
    # frame uses (the pure function over the empty chronicle is the
    # start day).
    assert world_date_of(package, _empty_store(), package.world_id) == (
        BERRYMOOR_START
    )


def _empty_store() -> SqliteWorldStore:
    """A throwaway in-memory store for the pure-function read above
    (fresh migrations, no world rows — the sum over an empty chronicle
    is zero)."""

    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return SqliteWorldStore(db, open_runtime_epoch(db))
