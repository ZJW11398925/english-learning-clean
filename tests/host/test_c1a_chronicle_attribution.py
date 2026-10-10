"""C1-a — the chronicle attribution foundation (DEC-OPI-41a4df20…55),
the seven VAL groups:

1. **migration pins** — ``world_event`` carries the
   two attribution columns in the migration's own order
   (``participants`` NOT NULL DEFAULT '[]', ``run_id`` NULL), the
   chain's stamps land (the head moved to ``'28'`` with C2's 0028 —
   the stamp-pin discipline every head move has followed since P8-4),
   and a legacy-shaped row (written the
   pre-0027 way) answers honestly empty — zero back-fill inference;
2. **the run attribution chain** — every event a run writes carries
   that run's id: the engine-direct path (two cycles, one run) and the
   generated path (two chained steps, one anchor run) both read back
   same-run rows, and the world's own events keep walking the PENDING
   queue;
3. **the bucket precision arm (P16 down)** — a revealed event whose
   run names a served ``trigger_turn_id`` rides that turn's bucket
   (the wr-8R continue-拍 no longer floats to the next letter), while
   the fallback arms stay byte-true: a ``run_id``-NULL legacy row and
   a trigger-less run still bucket by reveal stamp; a trigger naming
   an unserved turn stays out of the window;
4. **the interaction rows** — the letter-sent fact lands right after
   each CP0 commit (the parked half included) with **zero letter
   text**, the direction-chosen call lands at the consumption point
   (candidate label—hint and free-text shapes), both direct-REVEALED
   while the world's own events sit PENDING (the discipline negative
   control), the store refuses every other kind and an effects-bearing
   interaction, and the same-shape replay is a no-op;
5. **immersion zero-change** — a worldless conversation's turn writes
   no chronicle row at all;
6. **the narrator contract byte pin** — ``build_narrator_prompt``'s
   output hashes to the C1-b golden (the pre-C1-a original
   ``ceb73d7e…`` held until C1-b widened the contract; the attribution
   cut still feeds nothing into the prompt);
7. the served face still takes the attribution material (the caller
   hands the window its turn ids; the arm reads the runs) — the
   lr-2 source-fact posture; the wr-8/lr-2 suites ride unchanged in
   this cut's fast set.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.engine.engine import EngineConfig, PoolEvent, advance
from elc.world.engine.orchestrate import run_generated_step
from elc.world.engine.types import MomentKind
from elc.world.narrator import (
    NARRATOR_SOURCE,
    build_narrator_prompt,
)
from elc.world.package import (
    WORLD_PACKAGE_VERSION,
    CastMember,
    SupplyDeclaration,
    WorldPackage,
)
from elc.world.store import (
    INTERACTION_EVENT_KINDS,
    INTERACTION_SOURCE,
    SqliteWorldStore,
    WorldRevealItem,
)
from elc.world.types import StateEffect, WorldEvent
from tests.conftest import SCHEMA_HEAD_FILE, SCHEMA_HEAD_VERSION
from tests.host.test_a1_streaming import _post
from tests.host.test_lr4a_parked_rounds import (
    _CANDIDATES_A,
    _STEP1,
    _STEP2,
    _STEP3_LETTER,
    _finals,
    _SequencedNarrator,
    _set_directed,
)
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import NARRATOR_MARK

REPO = Path(__file__).resolve().parents[2]

#: The letter-sent row's whole narration (the neutral fact sentence —
#: the zero-letter-text law's own words).
LETTER_SENT_NARRATION = "A letter from the user's character was sent."

#: The free direction's text (the lr-3 shape's own material).
FREE_TEXT = "a storm rolls in from the west"


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows through a fresh read-only connection (the
    w13/wr-8 posture — the worker thread owns the writable one)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(ro.execute(sql).fetchall())
    finally:
        ro.close()


def _conn_rows(conn: sqlite3.Connection, sql: str) -> list[tuple]:
    return list(conn.execute(sql).fetchall())


def _event_rows(app_db: Path) -> list[tuple]:
    """Every chronicle row's attribution-relevant face."""

    return _ro_rows(
        app_db,
        "SELECT event_id, kind, narration, participants, run_id"
        " FROM world_event ORDER BY event_id",
    )


def _world_id_of(app_db: Path) -> str:
    """The served conversation's bound world (the seed binding)."""

    rows = _ro_rows(app_db, "SELECT world_id FROM world_conversation")
    assert rows, "the web stack bound no world"
    return str(rows[0][0])


def _between(first: str, second: str) -> str:
    """One wall moment strictly between two ISO stamps (the direct-write
    scenario's reveal stamp — parse, half the delta, re-emit)."""

    a = datetime.fromisoformat(first)
    b = datetime.fromisoformat(second)
    return (a + (b - a) / 2).isoformat()


def _minimal_package() -> WorldPackage:
    """One minimal package (the wr-2 fixture shape): the bible's
    sections, one cast member, an empty pool — the golden-hash pin and
    the generated-step test both run on it (fully under this module's
    control, decoupled from the builtin package's content)."""

    return WorldPackage(
        world_id="world-attrib",
        name="Attrib",
        version=WORLD_PACKAGE_VERSION,
        calendar_start="2026-10-01",
        setting=(
            "Attrib is a small harbour town on a cold coast.",
            "The boats come in with the morning tide.",
        ),
        cast=(CastMember(persona_id="persona-nell", name="Nell Alder"),),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="declared-not-consumed"),
    )


# ---------------------------------------------------------------------------
# 1 — the migration (VAL ①)
# ---------------------------------------------------------------------------


def test_0027_columns_stamps_and_legacy_honesty() -> None:
    """The migration's own spelling: two columns after the W-1-1 seven,
    the chain's own head stamps (C2's 0028 moved them — the head
    literal and the stamps are the chain's, the column claims are
    0027's), and a legacy-shaped row reading back honestly
    empty (``'[]'`` / NULL via the DEFAULT — zero back-fill)."""

    assert SCHEMA_HEAD_FILE == "0028_world_storyline.sql"
    assert SCHEMA_HEAD_VERSION == "28"
    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    columns = [
        (str(row[1]), str(row[2]), int(row[3]), row[4])
        for row in fresh.execute("PRAGMA table_info(world_event)").fetchall()
    ]
    assert [name for name, *_ in columns][-2:] == ["participants", "run_id"]
    by_name = {
        name: (kind, not_null, default)
        for name, kind, not_null, default in columns
    }
    assert by_name["participants"] == ("TEXT", 1, "'[]'")
    assert by_name["run_id"] == ("TEXT", 0, None)
    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": "28",
        "runtime_schema_version": "28",
    }
    # The legacy shape: a pre-0027 write names none of the new columns —
    # the DEFAULT carries it, and the store reads it back honestly.
    fresh.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, '2026-10-09T00:00:00+00:00')"
    )
    fresh.execute(
        "INSERT INTO world_event (event_id, world_id, kind, narration,"
        " effects, occurred_at, source)"
        " VALUES ('e', 'w', 'k', 'n', '[]', '2026-10-09', 'old')"
    )
    fresh.commit()
    store = SqliteWorldStore(fresh, open_runtime_epoch(fresh))
    chronicle = store.chronicle_of("w")
    assert isinstance(chronicle, Ok)
    assert chronicle.value[0].participants == (), (
        "a legacy row must read back empty, never inferred"
    )
    assert chronicle.value[0].run_id is None


# ---------------------------------------------------------------------------
# 2 — the run attribution chain (VAL ②)
# ---------------------------------------------------------------------------


def _notice_pool(*kinds: str) -> tuple[PoolEvent, ...]:
    return tuple(
        PoolEvent(
            kind=kind,
            narration=f"n-{kind}",
            moment=MomentKind.NOTICE,
            days=1,
        )
        for kind in kinds
    )


class _TwoBeats:
    """A provider double: every narrator dial answers one two-beat
    batch; the reply's dial answers the plain reply."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        if NARRATOR_MARK not in prompt.prompt_text:
            return ProviderOutput(text=REPLY, error=None)
        return ProviderOutput(
            text=json.dumps(
                {
                    "beats": [
                        {
                            "kind": "quiet-morning",
                            "narration": "The harbour kept its silence.",
                            "days": 0,
                        },
                        {
                            "kind": "market-day",
                            "narration": "The stalls went up at dawn.",
                            "days": 1,
                        },
                    ]
                }
            ),
            error=None,
        )


def test_engine_events_carry_their_run_id() -> None:
    """The deterministic engine's rows carry their run's id — two
    cycles, one run, two rows, one attribution."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    store = SqliteWorldStore(fresh, open_runtime_epoch(fresh))
    assert isinstance(store.create_world("world-x", "X", None, "now"), Ok)
    run = store.create_run("run-x-0000", "world-x", "turn-9", 0, "now")
    assert isinstance(run, Ok)
    trace = advance(
        store,
        run.value,
        _notice_pool("hatch-the-boat", "mend-the-net"),
        EngineConfig(days_per_cycle=1, max_cycles=2),
        "2026-10-09",
    )
    assert isinstance(trace, Ok) and trace.value.outcome == "LIMIT"
    chronicle = store.chronicle_of("world-x")
    assert isinstance(chronicle, Ok)
    assert [event.kind for event in chronicle.value] == [
        "hatch-the-boat",
        "mend-the-net",
    ]
    assert all(event.run_id == "run-x-0000" for event in chronicle.value)
    assert all(event.participants == () for event in chronicle.value)


def test_generated_chain_shares_one_anchor_run_id() -> None:
    """The generated path: two chained steps over one anchor run — every
    beat of every step carries the same run's id (同 run 多步同属), and
    the world's own reveals still sit PENDING until the inbox reads."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    store = SqliteWorldStore(fresh, open_runtime_epoch(fresh))
    package = _minimal_package()
    assert isinstance(store.create_world("world-attrib", "A", None, "now"), Ok)
    for _ in range(2):
        stepped = run_generated_step(
            store, "world-attrib", package, _TwoBeats(), None, "now"
        )
        assert isinstance(stepped, Ok) and len(stepped.value) == 2
    runs = store.list_runs("world-attrib")
    assert len(runs) == 1
    chronicle = store.chronicle_of("world-attrib")
    assert isinstance(chronicle, Ok)
    assert len(chronicle.value) == 4
    assert all(event.run_id == runs[0].run_id for event in chronicle.value)
    assert all(event.participants == () for event in chronicle.value)
    rows = _conn_rows(fresh, "SELECT status FROM world_reveal_item")
    assert {str(row[0]) for row in rows} == {"PENDING"}


# ---------------------------------------------------------------------------
# 3 — the bucket precision arm (VAL ③, P16 down)
# ---------------------------------------------------------------------------


def _seed_between_note(
    app_db: Path, *, run_id: str | None, trigger: str | None
) -> None:
    """Direct-write one revealed note between the two served turns: a
    run (trigger per the caller), one event attributed to it, one
    REVEALED item stamped between the turns — the continue-拍's own
    timing (after turn 1, before turn 2)."""

    world_id = _world_id_of(app_db)
    turns = _ro_rows(
        app_db, "SELECT turn_id, created_at FROM user_turn ORDER BY created_at"
    )
    assert len(turns) == 2, "seed two turns first"
    moment = _between(str(turns[0][1]), str(turns[1][1]))
    conn = sqlite3.connect(app_db)
    try:
        conn.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id,"
            ' seed, status, checkpoint_kind, "cursor", state_version,'
            " created_at, updated_at) VALUES (?, ?, ?, 0, 'AT_CHECKPOINT',"
            " 'NOTICE', 0, 1, ?, ?)",
            (run_id or "run-ghost", world_id, trigger, moment, moment),
        )
        event_id = f"{run_id or 'legacy'}:note"
        conn.execute(
            "INSERT INTO world_event (event_id, world_id, kind, narration,"
            " effects, occurred_at, source, participants, run_id)"
            " VALUES (?, ?, 'world-note', 'The continue beat lands.',"
            " '[]', '2026-10-09', 'world_engine', '[]', ?)",
            (event_id, world_id, run_id),
        )
        conn.execute(
            "INSERT INTO world_reveal_item (item_id, world_id,"
            " source_event_id, actor_id, status, revealed_at, created_at)"
            " VALUES (?, ?, ?, NULL, 'REVEALED', ?, ?)",
            (f"{event_id}:reveal", world_id, event_id, moment, moment),
        )
        conn.commit()
    finally:
        conn.close()


def _frame_narrations(turn: dict) -> list[str]:
    steps = turn.get("world_steps") or (
        [turn["world"]] if "world" in turn else []
    )
    return [
        str(note["narration"]) for frame in steps for note in frame["notes"]
    ]


def _two_turn_stack(app_db: Path, **kwargs):
    context = web_stack(app_db, **kwargs)
    stack = context.__enter__()
    assert stack.post("/api/turn", {"text": CLEAN_TEXT})[0] == 200
    assert stack.post("/api/turn", {"text": "Second letter."})[0] == 200
    return context, stack


def test_continue_beat_buckets_to_its_own_round(tmp_path: Path) -> None:
    """P16 down: the note's run names turn 1 — the note rides turn 1's
    bucket (the old arm floated it to turn 2, the next letter)."""

    app_db = tmp_path / "app.db"
    context, stack = _two_turn_stack(app_db)
    try:
        turns = _ro_rows(
            app_db, "SELECT turn_id FROM user_turn ORDER BY created_at"
        )
        _seed_between_note(
            app_db, run_id="run-berrymoor-0000", trigger=str(turns[0][0])
        )
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "The continue beat lands." in _frame_narrations(
            history["turns"][0]
        )
        assert "The continue beat lands." not in _frame_narrations(
            history["turns"][1]
        )
    finally:
        context.__exit__(None, None, None)


def test_legacy_and_triggerless_rows_keep_the_timestamp_arm(
    tmp_path: Path,
) -> None:
    """The fallback arms byte-true: a run_id-NULL legacy row and a
    trigger-less run still bucket by reveal stamp (float to the next
    letter — the registered approximation family)."""

    app_db = tmp_path / "app.db"
    context, stack = _two_turn_stack(app_db)
    try:
        _seed_between_note(app_db, run_id=None, trigger=None)
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "The continue beat lands." in _frame_narrations(
            history["turns"][1]
        )
        assert "The continue beat lands." not in _frame_narrations(
            history["turns"][0]
        )
    finally:
        context.__exit__(None, None, None)

    app_db2 = tmp_path / "b.db"
    context, stack = _two_turn_stack(app_db2)
    try:
        _seed_between_note(app_db2, run_id="run-berrymoor-0000", trigger=None)
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "The continue beat lands." in _frame_narrations(
            history["turns"][1]
        )
        assert "The continue beat lands." not in _frame_narrations(
            history["turns"][0]
        )
    finally:
        context.__exit__(None, None, None)


def test_trigger_outside_the_window_stays_out(tmp_path: Path) -> None:
    """A run whose trigger names an unserved turn: the attributed note
    stays out of this window (the letters' own law — it re-enters with
    its true turn through ?full)."""

    app_db = tmp_path / "app.db"
    context, stack = _two_turn_stack(app_db)
    try:
        _seed_between_note(
            app_db, run_id="run-berrymoor-0000", trigger="turn-never-served"
        )
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert all(
            "The continue beat lands." not in _frame_narrations(turn)
            for turn in history["turns"]
        )
    finally:
        context.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# 4 — the interaction rows (VAL ④)
# ---------------------------------------------------------------------------


def test_the_letter_lands_its_fact_row_without_its_text(
    tmp_path: Path,
) -> None:
    """The letter-sent row: landed at the CP0 commit, the neutral fact
    sentence only — zero letter text (WR-4 extended to the tree) —
    participants '[]', run_id NULL, revealed the moment it lands, and
    riding its own letter's turn in the served history."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        secret = "The password is humble-potato."
        status, _payload = stack.post("/api/turn", {"text": secret})
        assert status == 200
        rows = _event_rows(app_db)
        assert len(rows) == 1
        event_id, kind, narration, participants, run_id = rows[0]
        assert kind == "user-letter-sent"
        assert narration == LETTER_SENT_NARRATION
        assert secret not in narration and secret not in event_id
        assert participants == "[]" and run_id is None
        items = _ro_rows(
            app_db,
            "SELECT status, revealed_at, created_at FROM world_reveal_item",
        )
        assert len(items) == 1
        assert items[0][0] == "REVEALED" and items[0][1] is not None
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert _frame_narrations(history["turns"][0]) == [
            LETTER_SENT_NARRATION
        ]


def test_the_direction_choice_lands_at_the_consumption_point(
    tmp_path: Path,
) -> None:
    """The direction-chosen row: landed when the step consumed the
    choice, never at park time — the candidate shape narrates
    ``label — hint``, the free shape the text verbatim; 选了即用即清
    stands (one row per real consumption, ids advancing)."""

    provider = _SequencedNarrator([_STEP1, _STEP2, _STEP3_LETTER])
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": CLEAN_TEXT}
        )
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        # The parked letter itself is a sent letter (its CP0 committed —
        # the letter-sent row stands); the CHOICE lands no row yet.
        assert [
            row for row in _event_rows(app_db)
            if row[1] == "user-direction-chosen"
        ] == []
        label = str(_CANDIDATES_A[1]["label"])
        hint = str(_CANDIDATES_A[1]["hint"])
        assert stack.post(
            "/api/world/direction", {"label": label, "hint": hint}
        )[0] == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        rows = [
            row for row in _event_rows(app_db)
            if row[1] == "user-direction-chosen"
        ]
        assert len(rows) == 1
        assert rows[0][1] == "user-direction-chosen"
        assert rows[0][2] == f"{label} — {hint}"
        assert rows[0][3] == "[]" and rows[0][4] is None
        # The free shape: a second park, the user's own text, one more
        # row (the count-derived id — a real second choice, not a
        # rewrite), and the round walks to the letter.
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        assert stack.post("/api/world/direction", {"text": FREE_TEXT})[0] == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        rows = [
            row for row in _event_rows(app_db)
            if row[1] == "user-direction-chosen"
        ]
        assert len(rows) == 2
        assert rows[1][2] == FREE_TEXT
        assert rows[1][0] != rows[0][0]


def test_the_interaction_face_refuses_and_replays() -> None:
    """The durable face's law: only the two interaction kinds pass, an
    effects-bearing interaction is refused (an interaction settles no
    claim), the world's own event beside it still sits PENDING (the
    negative control), and the same-shape replay lands the idempotent
    no-op (nothing re-written)."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    store = SqliteWorldStore(fresh, open_runtime_epoch(fresh))
    assert isinstance(store.create_world("world-x", "X", None, "now"), Ok)
    assert set(INTERACTION_EVENT_KINDS) == {
        "user-letter-sent",
        "user-direction-chosen",
    }

    def _interaction(kind: str) -> WorldEvent:
        return WorldEvent(
            event_id="user-letter-sent:t1",
            world_id="world-x",
            kind=kind,
            narration=LETTER_SENT_NARRATION,
            effects=(),
            occurred_at="2026-10-09T00:00:00+00:00",
            source=INTERACTION_SOURCE,
        )

    refused = store.record_interaction_event(
        _interaction("world_beat"), "2026-10-09T00:00:00+00:00"
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    settling = WorldEvent(
        event_id="e2",
        world_id="world-x",
        kind="user-direction-chosen",
        narration="n",
        effects=(StateEffect(key="k", statement="s"),),
        occurred_at="now",
        source=INTERACTION_SOURCE,
    )
    refused = store.record_interaction_event(settling, "now")
    assert isinstance(refused, Err), "an interaction settles no claim"
    assert isinstance(
        store.record_interaction_event(
            _interaction("user-letter-sent"), "2026-10-09T00:00:00+00:00"
        ),
        Ok,
    )
    engine_event = WorldEvent(
        event_id="run-x-0000:0",
        world_id="world-x",
        kind="quiet-morning",
        narration="The harbour kept its silence.",
        effects=(),
        occurred_at="2026-10-09",
        source=NARRATOR_SOURCE,
        run_id="run-x-0000",
    )
    assert isinstance(store.record_event(engine_event), Ok)
    assert isinstance(
        store.enqueue_reveals(
            (
                WorldRevealItem(
                    item_id="run-x-0000:0:reveal",
                    world_id="world-x",
                    source_event_id="run-x-0000:0",
                    actor_id=None,
                    status="PENDING",
                    revealed_at=None,
                    created_at="2026-10-09",
                ),
            )
        ),
        Ok,
    )
    rows = _conn_rows(
        fresh, "SELECT item_id, status FROM world_reveal_item ORDER BY item_id"
    )
    assert rows == [
        ("run-x-0000:0:reveal", "PENDING"),
        ("user-letter-sent:t1:reveal", "REVEALED"),
    ]
    # The replay: same id, same shape — nothing re-written.
    assert isinstance(
        store.record_interaction_event(
            _interaction("user-letter-sent"), "2026-10-09T00:00:00+00:00"
        ),
        Ok,
    )
    assert _conn_rows(fresh, "SELECT COUNT(*) FROM world_event") == [(2,)]
    assert _conn_rows(fresh, "SELECT COUNT(*) FROM world_reveal_item") == [
        (2,)
    ]


# ---------------------------------------------------------------------------
# 5 — immersion zero-change (VAL ⑤)
# ---------------------------------------------------------------------------


def test_a_worldless_letter_writes_no_chronicle_row(tmp_path: Path) -> None:
    """No world, no row: unbind the conversation between requests and
    the next letter's CP0 lands no interaction row — the worldless
    turn stays byte for byte the pre-C1-a shape."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        assert stack.post("/api/turn", {"text": CLEAN_TEXT})[0] == 200
        assert len(_event_rows(app_db)) == 1
        conn = sqlite3.connect(app_db)
        try:
            conn.execute("DELETE FROM world_conversation")
            conn.commit()
        finally:
            conn.close()
        assert stack.post("/api/turn", {"text": "Unbound letter."})[0] == 200
        rows = _event_rows(app_db)
        assert len(rows) == 1, "no world, no chronicle row"
        assert rows[0][1] == "user-letter-sent"


# ---------------------------------------------------------------------------
# 6 — the narrator contract byte pin (VAL ⑥, the C1-b prerequisite)
# ---------------------------------------------------------------------------


def test_the_narrator_prompt_is_byte_untouched() -> None:
    """``build_narrator_prompt`` hashes to the C1-b golden (was the
    pre-C1-a golden ``ceb73d7e…8100e``). Re-cast consciously, twice:
    C1-a itself fed nothing into the prompt (the attribution cut's own
    zero-change law), and C1-b (DEC-OPI-b290799a…17) then widened the
    contract — the cast-id roster line, the optional-keys paragraph,
    both unconditional — so the hash moved to the widened shape. The
    judgment that survives: the attribution columns (participants
    values, run ids, interaction words) still feed nothing — the
    roster/teaching lines are contract, not attribution."""

    prompt = build_narrator_prompt(
        _minimal_package(),
        (("loom-key", "The loom sings at dusk."),),
        ("An older line of the story.",),
        "zh",
    )
    assert (
        hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        == "4b484ae7c497f8be291689b8ec9a54c8e5287616f6e0ed452e2662b65cc2eaba"
    )


# ---------------------------------------------------------------------------
# 7 — the served face still reads the attribution material (VAL ⑦ 随迁)
# ---------------------------------------------------------------------------


def test_the_history_caller_hands_the_window_its_turn_ids() -> None:
    """The precision arm's material flows from the caller: the history
    face passes the served window's turn ids beside the moments, and
    the arm reads the runs before falling back (the lr-2 source-fact
    posture)."""

    web = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    start = web.index("world_frames = self._world_frames_for_window(")
    call = web[start : web.index(")", start)]
    assert "turn_ids" in call
    body_start = web.index("def _world_frames_for_window(")
    body = web[body_start : web.index("def _world_payload(", body_start)]
    assert "run_triggers" in body
    assert "trigger in turn_index_by_id" in body
    assert "bisect_left(turn_moments, moment)" in body
