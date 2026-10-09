"""C1-aR v2 — the run's lifecycle aligns with the canonical §4.2
(DEC-OPI-b290799a…9, the aR v1 stop-gap's病根 repair).

The病根 (P16's ledger row): the generated step never terminalized its
run, so one conversation lived inside one never-ending run — the run's
trigger attribution was session-grained while the wr-8 buckets need
turn-grained precision, and the fill-once stop-gap piled a whole
session onto its first letter (the wr-8 pins went red; the evidence
lives in the aR v1 stop report). The canonical alignment:

1. **the terminal stops** — a chain-tail step the narrator ends with
   ``letter_arrives`` or ``awaits_you`` terminalizes its run inside
   the step (after the beats and reveals land), so the next letter
   winds a fresh run: the letter is the only run starter (spec §4.1),
   a RESPONSE stop ends the RUN (spec §4.2 step 5); a checkpoint chain
   (``she_thinks_of_you`` / no signal) keeps resuming its one run;
2. **the trigger backfill** — the run is wound before the letter's
   turn commits (WR-6's order), so the committed turn's id rides the
   row only afterwards (``adopt_trigger_turn``, idempotent, refusing a
   different starter); the wr-8 buckets then go exact in production
   (the run's events bucket to their trigger turn, the legacy
   trigger-NULL rows keep the reveal-stamp approximation);
3. **multi-letter-in-flight attribution** — a checkpoint chain's
   second letter is the SAME RUN's execution continued (§4.2): its
   beats ride the first letter's run, the row keeps the first letter's
   name, and the history buckets the resumed beats to the starter
   turn;
4. **immersion zero-change** — the frames, the stop word and the reply
   order are byte for byte as before; the terminal stop is a world-face
   fact (the run row), never a user-experience change.

The pins run over the production assembly (the real ``run_web`` over
the real ``open_host``, the lr-4 suite's own shape), beside the
store-direct law pins and the orchestrate-direct opt-in matrix.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import (
    STOP_AWAITS_YOU,
    STOP_LETTER_ARRIVES,
    STOP_SHE_THINKS_OF_YOU,
)
from elc.world.store import SqliteWorldStore
from tests.host.test_a1_streaming import _post
from tests.host.test_c1a_chronicle_attribution import (
    _frame_narrations,
    _minimal_package,
    _two_turn_stack,
)
from tests.host.test_lr4a_parked_rounds import (
    _SequencedNarrator,
    _set_directed,
)
from tests.host.test_lr4n_stop_rounds import _finals, _turn_facts
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import NARRATOR_MARK


#: The one-beat letter-arrival batch (a distinct narration per letter —
#: the two-bucket discrimination needs the words to tell the letters
#: apart).
def _letter_step(narration: str) -> str:
    return json.dumps(
        {
            "beats": [
                {
                    "kind": "quiet-morning",
                    "narration": narration,
                    "days": 0,
                },
            ],
            "stop": {"kind": STOP_LETTER_ARRIVES},
        },
        ensure_ascii=False,
    )


def _checkpoint_step(narration: str) -> str:
    return json.dumps(
        {
            "beats": [
                {
                    "kind": "quiet-morning",
                    "narration": narration,
                    "days": 0,
                },
            ],
            "stop": {"kind": STOP_SHE_THINKS_OF_YOU},
        },
        ensure_ascii=False,
    )


def _awaits_step(narration: str) -> str:
    return json.dumps(
        {
            "beats": [
                {
                    "kind": "quiet-morning",
                    "narration": narration,
                    "days": 0,
                },
            ],
            "stop": {"kind": STOP_AWAITS_YOU},
        },
        ensure_ascii=False,
    )


#: The interaction row's own fact sentence (the C1-a law's words).
LETTER_SENT = "A letter from the user's character was sent."


def _run_rows(app_db: Path) -> list[tuple[str, str, str | None, str]]:
    """Every ``world_run`` row's ``(run_id, status, trigger_turn_id,
    checkpoint_kind)``, durable order (the w13 ro posture)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return [
            (str(row[0]), str(row[1]), None if row[2] is None else str(row[2]),
             str(row[3]))
            for row in ro.execute(
                "SELECT run_id, status, trigger_turn_id, checkpoint_kind"
                " FROM world_run ORDER BY created_at, run_id"
            ).fetchall()
        ]
    finally:
        ro.close()


def _turn_ids(app_db: Path) -> list[str]:
    """The committed user turns' ids, durable order."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return [
            str(row[0])
            for row in ro.execute(
                "SELECT turn_id FROM user_turn ORDER BY created_at, turn_id"
            ).fetchall()
        ]
    finally:
        ro.close()


def _chronicle_of_run(app_db: Path, run_id: str) -> list[str]:
    """One run's chronicle narrations, rowid order (the landing order)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return [
            str(row[0])
            for row in ro.execute(
                "SELECT narration FROM world_event"
                " WHERE run_id = ? AND source = 'world_narrator'"
                " ORDER BY rowid",
                (run_id,),
            ).fetchall()
        ]
    finally:
        ro.close()


# ---------------------------------------------------------------------------
# 1 — letter_arrives: the RESPONSE terminal stop, the next letter a new
#     winch, the buckets exact (VAL groups ① and ③)
# ---------------------------------------------------------------------------


def test_letter_arrives_terminalizes_and_the_next_letter_winds_fresh(
    tmp_path: Path,
) -> None:
    """Two letters, each ended by the narrator's own ``letter_arrives``:
    letter one leaves run-0000 TERMINAL/RESPONSE carrying its turn as
    the trigger; letter two winds run-0001 (the only run starter) whose
    trigger is the second turn — and the wr-8 history buckets each
    letter's beats to their own turn through the exact trigger arm."""

    app_db = tmp_path / "app.db"
    provider = _SequencedNarrator(
        [
            _letter_step("The harbour woke under its first fog."),
            _letter_step("The market filled the square by noon."),
        ]
    )
    with web_stack(app_db, provider=provider) as stack:
        status, _payload = stack.post("/api/turn", {"text": "第一封信。"})
        assert status == 200
        first_turn = _turn_ids(app_db)[0]
        runs = _run_rows(app_db)
        # One letter, one run — terminalized at its RESPONSE stop, the
        # committed letter its named starter.
        assert runs == [("run-berrymoor-0000", "TERMINAL", first_turn,
                         "RESPONSE")]
        assert _chronicle_of_run(app_db, "run-berrymoor-0000") == [
            "The harbour woke under its first fog."
        ]
        # The second letter: the first run rests TERMINAL, so the letter
        # winds a fresh one and names it.
        status, _payload = stack.post("/api/turn", {"text": "第二封信。"})
        assert status == 200
        second_turn = _turn_ids(app_db)[1]
        runs = _run_rows(app_db)
        assert runs == [
            ("run-berrymoor-0000", "TERMINAL", first_turn, "RESPONSE"),
            ("run-berrymoor-0001", "TERMINAL", second_turn, "RESPONSE"),
        ]
        assert _chronicle_of_run(app_db, "run-berrymoor-0001") == [
            "The market filled the square by noon."
        ]
        # The wr-8 buckets, exact: each letter's beats ride their own
        # turn's frame (the trigger arm in production — the reveal
        # stamps of the two chains both predate the second turn, so only
        # the trigger can tell them apart).
        status, history = stack.get_json("/api/history")
        assert status == 200
        first, second = history["turns"]
        assert _frame_narrations(first) == [
            "The harbour woke under its first fog.",
            LETTER_SENT,
        ]
        assert _frame_narrations(second) == [
            "The market filled the square by noon.",
            LETTER_SENT,
        ]


# ---------------------------------------------------------------------------
# 2 — awaits_you: the RESPONSE stop with no reply in it; the close face
#     stands, the next letter a new winch (VAL group ①, the directed arm)
# ---------------------------------------------------------------------------


def test_awaits_you_terminalizes_directed_and_the_close_stands(
    tmp_path: Path,
) -> None:
    """The directed ``awaits_you`` round: the step terminalizes its run
    (the word IS a RESPONSE) AND the round closes without a reply (刀
    N's ``NO_ASSISTANT_OUTPUT``, untouched) — both facts one letter
    leaves behind. The next letter winds run-0001 and answers."""

    app_db = tmp_path / "app.db"
    provider = _SequencedNarrator(
        [
            _awaits_step("The harbour fell silent; the world waits."),
            _letter_step("She broke the seal and read your words."),
        ]
    )
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": "the first letter"}
        )
        assert status == 200
        final, _worlds = _finals(raw)
        closed_turn_id = final["turn_id"]
        # 刀 N's face, byte for byte (the close stands beside the new
        # world-face fact).
        assert final["parked"] is True
        assert final["stop_kind"] == STOP_AWAITS_YOU
        assert final["turn_status"] == "COMPLETED"
        facts = _turn_facts(app_db)
        assert facts[closed_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                         False)
        # The world-face fact: the run rests TERMINAL/RESPONSE, its
        # starter the closed letter's own turn.
        first_turn = _turn_ids(app_db)[0]
        assert closed_turn_id == first_turn
        assert _run_rows(app_db) == [
            ("run-berrymoor-0000", "TERMINAL", first_turn, "RESPONSE")
        ]
        # The next letter is the crank: it winds run-0001 (the first
        # anchor ended) and the reply lands on the new turn.
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": "the second letter"}
        )
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        second_turn = _turn_ids(app_db)[1]
        assert _run_rows(app_db) == [
            ("run-berrymoor-0000", "TERMINAL", first_turn, "RESPONSE"),
            ("run-berrymoor-0001", "TERMINAL", second_turn, "RESPONSE"),
        ]
        facts = _turn_facts(app_db)
        assert facts[second_turn] == ("COMPLETED", "REPLIED_FULL", True)


# ---------------------------------------------------------------------------
# 3 — the checkpoint chain: one run, its starter letter, the resumed
#     beats bucketing to the starter turn (VAL group ② and ③)
# ---------------------------------------------------------------------------


def test_checkpoint_chain_keeps_one_run_and_its_starter_turn(
    tmp_path: Path,
) -> None:
    """A checkpoint chain across two letters (the canonical §4.2
    resume): the first letter's ``she_thinks_of_you`` parks its round
    and leaves run-0000 AT_CHECKPOINT carrying the first turn as its
    trigger; the second letter supersedes the parked round (刀 N's
    close), RESUMES the same run (never a second winch) — its beats
    ride run-0000, the row keeps the FIRST letter's name, and the
    history buckets the resumed beats to the starter turn."""

    app_db = tmp_path / "app.db"
    provider = _SequencedNarrator(
        [
            _checkpoint_step("She looked up from her desk."),
            _checkpoint_step("She walked the harbour road thinking."),
        ]
    )
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": "the first letter"}
        )
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        first_turn = _turn_ids(app_db)[0]
        runs = _run_rows(app_db)
        assert runs == [
            ("run-berrymoor-0000", "AT_CHECKPOINT", first_turn, "NOTICE")
        ]
        # The second letter: the parked round is superseded (closed), the
        # chain resumes the SAME run — one run still, the first letter
        # its starter, both letters' beats on the one row.
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": "the second letter"}
        )
        assert status == 200
        final, worlds = _finals(raw)
        assert final["parked"] is True
        assert len(worlds) == 1
        second_turn = _turn_ids(app_db)[1]
        assert second_turn != first_turn
        assert _run_rows(app_db) == [
            ("run-berrymoor-0000", "AT_CHECKPOINT", first_turn, "NOTICE")
        ]
        assert _chronicle_of_run(app_db, "run-berrymoor-0000") == [
            "She looked up from her desk.",
            "She walked the harbour road thinking.",
        ]
        # The superseded first turn closed without a reply (刀 N's law).
        facts = _turn_facts(app_db)
        assert facts[first_turn] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                     False)
        # The buckets: the resumed beats ride the STARTER turn's frame
        # (the exact trigger arm — §4.2's one-RUN attribution), the
        # second letter's own fact row rides its own turn.
        status, history = stack.get_json("/api/history")
        assert status == 200
        first, second = history["turns"]
        assert "She looked up from her desk." in _frame_narrations(first)
        assert "She walked the harbour road thinking." in (
            _frame_narrations(first)
        )
        assert "She walked the harbour road thinking." not in (
            _frame_narrations(second)
        )
        assert LETTER_SENT in _frame_narrations(second)


# ---------------------------------------------------------------------------
# 4 — the parked walk's replay keeps one trigger (the idempotent face)
# ---------------------------------------------------------------------------


def test_the_parked_walk_replays_keep_one_trigger(tmp_path: Path) -> None:
    """The directed walk to the letter: park (the backfill names the
    run), continue — the letter arrives, the step terminalizes the run
    and the re-entry replays the SAME command (the idempotent CP0) —
    one turn, one run, the trigger never rewritten."""

    app_db = tmp_path / "app.db"
    provider = _SequencedNarrator(
        [
            _checkpoint_step("She looked up from her desk."),
            _letter_step("She broke the seal and read your words."),
        ]
    )
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": CLEAN_TEXT}
        )
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        turn_id = _turn_ids(app_db)[0]
        assert _run_rows(app_db) == [
            ("run-berrymoor-0000", "AT_CHECKPOINT", turn_id, "NOTICE")
        ]
        # The continue: the letter arrives — the run terminalizes, the
        # re-entry replays the parked command (no second turn, no
        # second adoption) and the reply lands.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        assert len(_turn_facts(app_db)) == 1
        assert _run_rows(app_db) == [
            ("run-berrymoor-0000", "TERMINAL", turn_id, "RESPONSE")
        ]


# ---------------------------------------------------------------------------
# 5 — the adopt law (store-direct): idempotent, one starter, defensive
# ---------------------------------------------------------------------------


def _fresh_store() -> SqliteWorldStore:
    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    return SqliteWorldStore(fresh, open_runtime_epoch(fresh))


def test_the_adopt_law_is_idempotent_and_defensive() -> None:
    """``adopt_trigger_turn``'s whole law: NULL ⇒ adopt (the row
    rewritten, the version bumped); the same turn again ⇒ the no-op
    (nothing rewritten); a different turn ⇒ VALIDATION_FAILED (runs do
    not rewrite their starter — the TERMINAL case included, the
    defensive spelling); an unknown run ⇒ NOT_FOUND."""

    store = _fresh_store()
    assert isinstance(store.create_world("world-x", "X", None, "now"), Ok)
    created = store.create_run("run-x-0000", "world-x", None, 0, "now")
    assert isinstance(created, Ok)
    assert created.value.trigger_turn_id is None
    adopted = store.adopt_trigger_turn("run-x-0000", "turn-1", "later")
    assert isinstance(adopted, Ok)
    assert adopted.value.trigger_turn_id == "turn-1"
    assert adopted.value.state_version == 2
    # The idempotent replay: the same turn, nothing rewritten.
    again = store.adopt_trigger_turn("run-x-0000", "turn-1", "later")
    assert isinstance(again, Ok)
    assert again.value.state_version == 2
    # A different starter is refused, the row untouched.
    refused = store.adopt_trigger_turn("run-x-0000", "turn-2", "later")
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert store.list_runs("world-x")[0].trigger_turn_id == "turn-1"
    # The TERMINAL defensive case: same turn after the stop ⇒ no-op,
    # another turn ⇒ refused.
    terminalized = store.terminalize_run("run-x-0000", "later")
    assert isinstance(terminalized, Ok)
    version = store.list_runs("world-x")[0].state_version
    same = store.adopt_trigger_turn("run-x-0000", "turn-1", "later")
    assert isinstance(same, Ok)
    assert store.list_runs("world-x")[0].state_version == version
    other = store.adopt_trigger_turn("run-x-0000", "turn-9", "later")
    assert isinstance(other, Err)
    assert other.error.code is DomainErrorCode.VALIDATION_FAILED
    # An unknown run is a NOT_FOUND, never a silent nothing.
    missing = store.adopt_trigger_turn("run-x-none", "turn-1", "later")
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 6 — the legacy face: a trigger-NULL run buckets by stamp until the
#     adopt face names its starter (the production switch itself)
# ---------------------------------------------------------------------------


def test_legacy_triggerless_run_buckets_by_stamp_until_adopted(
    tmp_path: Path,
) -> None:
    """The fallback arm byte-true in the new world: a run written the
    legacy way (trigger NULL — the shape every pre-aR-v2 production run
    carries) buckets its note by reveal stamp (floats to the next
    letter); the adopt face naming the starter flips the very same note
    to the exact bucket — the production switch, exercised."""

    app_db = tmp_path / "app.db"
    context, stack = _two_turn_stack(app_db)
    try:
        turns = [
            row[0]
            for row in _ro_turns(app_db)
        ]
        assert len(turns) == 2
        # The legacy shape: a run with no trigger, one attributed event,
        # revealed between the two letters (the continue-拍's timing).
        _seed_triggerless_note(app_db, run_id="run-berrymoor-0000")
        status, history = stack.get_json("/api/history")
        assert status == 200
        first, second = history["turns"]
        assert "The continue beat lands." in _frame_narrations(second)
        assert "The continue beat lands." not in _frame_narrations(first)
        # The adopt face: the store names the starter — the same note
        # flips to the exact bucket on the next read.
        writer = sqlite3.connect(app_db, timeout=10)
        try:
            store = SqliteWorldStore(writer, open_runtime_epoch(writer))
            adopted = store.adopt_trigger_turn(
                "run-berrymoor-0000",
                turns[0],
                datetime.now(tz=UTC).isoformat(),
            )
            assert isinstance(adopted, Ok)
        finally:
            writer.close()
        status, history = stack.get_json("/api/history")
        assert status == 200
        first, second = history["turns"]
        assert "The continue beat lands." in _frame_narrations(first)
        assert "The continue beat lands." not in _frame_narrations(second)
    finally:
        context.__exit__(None, None, None)


def _ro_turns(app_db: Path) -> list[tuple]:
    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(
            ro.execute(
                "SELECT turn_id FROM user_turn ORDER BY created_at"
            ).fetchall()
        )
    finally:
        ro.close()


def _seed_triggerless_note(app_db: Path, *, run_id: str) -> None:
    """Direct-write the legacy shape (the C1-a injection posture): one
    trigger-NULL run, one event attributed to it, one REVEALED item
    stamped between the two served turns."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        world_id = str(
            ro.execute(
                "SELECT world_id FROM world_conversation LIMIT 1"
            ).fetchone()[0]
        )
        turn_moments = [
            str(row[0])
            for row in ro.execute(
                "SELECT created_at FROM user_turn ORDER BY created_at"
            ).fetchall()
        ]
    finally:
        ro.close()
    assert len(turn_moments) == 2, "seed two turns first"
    a = datetime.fromisoformat(turn_moments[0])
    b = datetime.fromisoformat(turn_moments[1])
    moment = (a + (b - a) / 2).isoformat()
    conn = sqlite3.connect(app_db)
    try:
        conn.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id,"
            ' seed, status, checkpoint_kind, "cursor", state_version,'
            " created_at, updated_at) VALUES (?, ?, NULL, 0,"
            " 'AT_CHECKPOINT', 'NOTICE', 0, 1, ?, ?)",
            (run_id, world_id, moment, moment),
        )
        event_id = f"{run_id}:note"
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


# ---------------------------------------------------------------------------
# 7 — the orchestrate-direct opt-in matrix (the default byte for byte)
# ---------------------------------------------------------------------------


class _StopScript:
    """A narrator double whose every dial answers one one-beat batch
    with a fixed stop verdict (``None`` = no stop key — keep going);
    the letter's dial answers a plain reply."""

    def __init__(self, stop: str | None) -> None:
        answer: dict[str, object] = {
            "beats": [
                {
                    "kind": "quiet-morning",
                    "narration": "The harbour kept its silence.",
                    "days": 0,
                },
            ]
        }
        if stop is not None:
            answer["stop"] = {"kind": stop}
        self._answer = json.dumps(answer)

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        if NARRATOR_MARK in prompt.prompt_text:
            return ProviderOutput(text=self._answer, error=None)
        return ProviderOutput(text="a plain reply", error=None)


def _stepped(
    store: SqliteWorldStore,
    provider: _StopScript,
    *,
    turn_id: str | None,
    terminal: tuple[str, ...] | None,
):
    return run_generated_step(
        store,
        "world-attrib",
        _minimal_package(),
        provider,
        turn_id,
        "now",
        terminal_stop_kinds=terminal,
    )


def test_the_terminal_arm_is_the_callers_explicit_opt_in() -> None:
    """The opt-in matrix over the generated face: the default and the
    checkpoint word never terminalize (the byte-for-byte posture the
    wr-2 suite pins); the two RESPONSE words terminalize when — and
    only when — the caller names them; a stopless answer never does."""

    # The default: a letter_arrives verdict, no arm — the anchor stays.
    store = _fresh_store()
    assert isinstance(store.create_world("world-attrib", "A", None, "now"), Ok)
    stepped = _stepped(
        store, _StopScript(STOP_LETTER_ARRIVES), turn_id=None, terminal=None
    )
    assert isinstance(stepped, Ok) and len(stepped.value) == 1
    assert _status(store) == "AT_CHECKPOINT"

    # The NOTICE checkpoint never terminalizes, armed or not.
    store = _fresh_store()
    assert isinstance(store.create_world("world-attrib", "A", None, "now"), Ok)
    stepped = _stepped(
        store,
        _StopScript(STOP_SHE_THINKS_OF_YOU),
        turn_id=None,
        terminal=(STOP_LETTER_ARRIVES, STOP_AWAITS_YOU),
    )
    assert isinstance(stepped, Ok)
    assert _status(store) == "AT_CHECKPOINT"

    # A stopless answer never terminalizes, armed or not.
    store = _fresh_store()
    assert isinstance(store.create_world("world-attrib", "A", None, "now"), Ok)
    stepped = _stepped(
        store, _StopScript(None), turn_id=None,
        terminal=(STOP_LETTER_ARRIVES, STOP_AWAITS_YOU),
    )
    assert isinstance(stepped, Ok)
    assert _status(store) == "AT_CHECKPOINT"

    # The RESPONSE words terminalize when the caller names them.
    for word in (STOP_LETTER_ARRIVES, STOP_AWAITS_YOU):
        store = _fresh_store()
        assert isinstance(
            store.create_world("world-attrib", "A", None, "now"), Ok
        )
        stepped = _stepped(
            store, _StopScript(word), turn_id=None, terminal=(word,)
        )
        assert isinstance(stepped, Ok)
        assert _status(store) == "TERMINAL"
        row = store.list_runs("world-attrib")[0]
        assert row.checkpoint_kind.value == "RESPONSE"


def _status(store: SqliteWorldStore) -> str:
    runs = store.list_runs("world-attrib")
    assert len(runs) == 1
    return runs[0].status.value


def test_an_armed_replay_in_the_checkpoint_window_touches_no_run() -> None:
    """The replay contract under the armed arm: with the anchor still
    standing (``AT_CHECKPOINT``), the same letter's replay re-derives
    the same ids, skips the whole batch — and the arm, riding the
    landed-something condition, never reaches the store (the row's
    version and status untouched, however armed)."""

    store = _fresh_store()
    assert isinstance(store.create_world("world-attrib", "A", None, "now"), Ok)
    provider = _StopScript(STOP_LETTER_ARRIVES)
    # The first landing runs the default (no arm): the beats stand, the
    # anchor stays at its checkpoint — the replay window is open.
    stepped = _stepped(
        store, provider, turn_id="turn-again", terminal=None
    )
    assert isinstance(stepped, Ok) and len(stepped.value) == 1
    before = store.list_runs("world-attrib")[0]
    assert before.status.value == "AT_CHECKPOINT"
    # The replay, fully armed: the no-op lands, the run row untouched —
    # the arm did not fire on an empty batch.
    replay = _stepped(
        store, provider, turn_id="turn-again",
        terminal=(STOP_LETTER_ARRIVES, STOP_AWAITS_YOU),
    )
    assert isinstance(replay, Ok)
    assert replay.value == ()
    after = store.list_runs("world-attrib")[0]
    assert after == before
    assert len(store.chronicle_of("world-attrib").value) == 1
