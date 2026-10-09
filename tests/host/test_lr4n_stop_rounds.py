"""lr-4 刀 N — the no-reply stop rounds (no-reply 停点轮,
DEC-OPI-41a4df20…46; the lr-4 spike's eval §3/§5 outline implemented).

The narrator's stop vocabulary has said three things since lr-1
(letter_arrives / she_thinks_of_you / awaits_you); lr-4a directed parked
on every non-letter stop and threw the word away. This cut records the
word, and gives the one word that means "RESPONSE, no reply" its
transcript fact:

1. **the word rides** (VAL ①) — the parked row and every parked final
   carry ``stop_kind`` (the narrator's own word; a no-signal stop reads
   ``none``; a pre-cut row without the field reads ``none`` too) beside
   the byte-identical turn-flow ``stop: awaits_direction``;
2. **awaits_you closes the round** (VAL ②) — a stop the narrator words
   ``awaits_you`` parks (the letter is a fact) and is then closed on
   the spot: ``NO_ASSISTANT_OUTPUT`` (the STATE_MACHINES §10 terminal
   that does not require an AssistantTurn), the row gone — and since
   C1-aR v2 (DEC-OPI-b290799a…9, the canonical §4.2 alignment) the
   world's own run terminalizes at its RESPONSE stop with the step
   (the word IS a RESPONSE: the RUN ends, the next letter is the crank
   that winds the fresh run), the reply belongs to the new turn, the
   closed turn never grows an assistant row;
3. **a new letter supersedes** (VAL ③, the probe P-1 gap closed) — a
   parked round a new letter runs into is closed first (any stop_kind,
   a restart's old epoch adopted on the way), so no turn hangs at
   GENERATING forever;
4. **checkpoints stay checkpoints** (VAL ④) — ``she_thinks_of_you`` and
   ``none`` keep the lr-4a behavior byte for byte: park, continue,
   turn, park again;
5. **the crash window converges** — a row whose word already reads
   ``awaits_you`` (a park whose close never landed) closes on the next
   continue instead of cranking the world;
6. **F-2 (P14)** — 选了即用即清 now consumes only after the step's own
   reveal settles: a refused reveal no longer eats the director's
   input while the failure arm says the offer stands.

The pins run over the production assembly (the real ``run_web`` over
the real ``open_host``, the lr-4a suite's own shape). Zero frontend
change is itself the pinned posture: the awaiting chrome of an
``awaits_you`` stop is the same chrome (zero new copy), the continue
button answers the honest 409 the page already handles.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from elc.platform.types import DomainError, DomainErrorCode, Err
from tests.host.test_a1_streaming import _post, _sse_frames
from tests.host.test_lr4a_parked_rounds import (
    _CANDIDATES_A,
    _PARKED_KEY,
    _STEP1,
    _STEP3_LETTER,
    _beats,
    _SequencedNarrator,
    _set_directed,
)
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack
from tests.host.test_wr10_web_directions import _pending_rows

REPO = Path(__file__).resolve().parents[2]

#: The narrator's checkpoint word and the RESPONSE-with-no-reply word,
#: spelled as the narrator spells them (the vocabulary is imported where
#: the production code imports it; these aliases keep the scripts
#: readable).
SHE_THINKS = "she_thinks_of_you"
AWAITS_YOU = "awaits_you"

#: The checkpoint step (a NOTICE, not an end) and the no-reply stop (the
#: world waits for the user — the word this cut gives its transcript
#: fact to).
_STEP_SHE_THINKS = _beats(
    _CANDIDATES_A,
    stop=SHE_THINKS,
    narration="She looked up from her desk and thought of the letter.",
)
_STEP_AWAITS_YOU = _beats(
    _CANDIDATES_A,
    stop=AWAITS_YOU,
    narration="The harbour fell silent; the world waits for you.",
)
_STEP_PLAIN = _beats(
    _CANDIDATES_A,
    narration="A second plain step turned without the letter.",
)


def _turn_facts(app_db: Path) -> dict[str, tuple[str, str | None, bool]]:
    """Every turn record's ``(status, outcome, has_assistant_row)`` by
    turn id — the closed round's whole transcript truth (the outcome
    word and the assistant table are two tables' facts, read as such)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        turns = {
            str(row[0]): (str(row[1]), row[2], False)
            for row in ro.execute(
                "SELECT turn_id, status, turn_outcome FROM turn_record"
            ).fetchall()
        }
        for (turn_id,) in ro.execute(
            "SELECT turn_id FROM assistant_turn"
        ).fetchall():
            status, outcome, _ = turns[str(turn_id)]
            turns[str(turn_id)] = (status, outcome, True)
        return turns
    finally:
        ro.close()


def _parked_rows(app_db: Path) -> list[tuple[str, str]]:
    """The parking rows off the serving database (the lr-4a posture)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(
            ro.execute(
                "SELECT key, value FROM app_setting"
                f" WHERE key LIKE '{_PARKED_KEY}%' ORDER BY key"
            ).fetchall()
        )
    finally:
        ro.close()


def _rewrite_parked_row(app_db: Path, mutate) -> None:
    """Rewrite the one parking row in place through the test's own
    connection (the crash-window and pre-cut-row fixtures: the durable
    shape a dead process would have left behind)."""

    rw = sqlite3.connect(app_db, timeout=10.0)
    try:
        (raw,) = rw.execute(
            "SELECT value FROM app_setting WHERE key = ?", (_PARKED_KEY,)
        ).fetchone()
        row = json.loads(raw)
        mutate(row)
        rw.execute(
            "UPDATE app_setting SET value = ? WHERE key = ?",
            (json.dumps(row, ensure_ascii=False), _PARKED_KEY),
        )
        rw.commit()
    finally:
        rw.close()


def _finals(raw: bytes) -> tuple[dict, list[dict]]:
    """The stream's one final and its world frames (the lr-4a shape)."""

    frames = _sse_frames(raw)
    finals = [f for f in frames if f["type"] == "final"]
    worlds = [f for f in frames if f["type"] == "world"]
    assert len(finals) == 1
    return finals[0], worlds


# ---------------------------------------------------------------------------
# 1 — the word rides: the row and the finals record the narrator's own
#     stop word, additively (VAL ①)
# ---------------------------------------------------------------------------


def test_the_park_records_the_narrator_word_additively(tmp_path: Path) -> None:
    """A no-signal stop reads ``none`` (the narrator's keep-going word,
    exactly what the parser normalized the absence to); a checkpoint
    stop rewrites the row's word on the continue. The turn-flow
    ``stop: awaits_direction`` stays byte for byte what lr-4a pinned —
    the additive key rides beside it, never instead of it."""

    provider = _SequencedNarrator([_STEP1, _STEP_SHE_THINKS])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, _worlds = _finals(raw)
        # The additive pair on the first parked final: the narrator's
        # word (none — no signal) beside the unchanged turn-flow word.
        assert final["stop"] == "awaits_direction"
        assert final["stop_kind"] == "none"
        assert final["parked"] is True
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        parked = json.loads(rows[0][1])
        assert parked["stop_kind"] == "none"
        # The checkpoint stop: the row's word is the narrator's freshest.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["stop"] == "awaits_direction"
        assert final["stop_kind"] == SHE_THINKS
        assert final["parked"] is True
        rows = _parked_rows(tmp_path / "app.db")
        parked = json.loads(rows[0][1])
        assert parked["stop_kind"] == SHE_THINKS
        assert parked["stops"] == 2
        # A checkpoint is not an end: the turn still waits.
        facts = _turn_facts(tmp_path / "app.db")
        assert list(facts.values()) == [("GENERATING", None, False)]


def test_a_pre_cut_row_without_the_field_reads_none(tmp_path: Path) -> None:
    """The backward-compat read: a row written before this cut (no
    ``stop_kind`` field) parks, continues and answers with the same
    ``none`` word — the round's mechanics untouched."""

    provider = _SequencedNarrator([_STEP1, _STEP_PLAIN])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200

        def strip_field(row: dict) -> None:
            row.pop("stop_kind", None)

        _rewrite_parked_row(tmp_path / "app.db", strip_field)
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        assert final["stop"] == "awaits_direction"
        assert final["stop_kind"] == "none"
        facts = _turn_facts(tmp_path / "app.db")
        assert list(facts.values()) == [("GENERATING", None, False)]


# ---------------------------------------------------------------------------
# 2 — awaits_you: the RESPONSE verdict with no reply in it closes the
#     round on the spot; the world's run waits for the next letter
#     (VAL ②, the full E2E)
# ---------------------------------------------------------------------------


def test_awaits_you_closes_the_round_and_the_next_letter_replies(
    tmp_path: Path,
) -> None:
    """The full no-reply flow: the letter parks on an ``awaits_you``
    step — the final keeps the waiting chrome shape (parked true, the
    turn-flow word unchanged) with the closed truth and the word — the
    round closes as ``NO_ASSISTANT_OUTPUT`` with no assistant row and
    no reply dial, the row is gone, history carries no parked key. The
    next letter finds no row (nothing to supersede), the world turns
    from its checkpoint, the letter arrives and the **new** turn
    answers: two turns total, the first one closed forever without an
    assistant row, exactly one reply dial."""

    provider = _SequencedNarrator([_STEP_AWAITS_YOU, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "the first letter"})
        assert status == 200
        final, _worlds = _finals(raw)
        closed_turn_id = final["turn_id"]
        # The chrome shape (zero new copy) with the closed truth and
        # the word riding additively.
        assert final["parked"] is True
        assert final["stop"] == "awaits_direction"
        assert final["stop_kind"] == AWAITS_YOU
        assert final["reply"] is None
        assert final["turn_status"] == "COMPLETED"
        # The transcript fact: closed, no reply, no assistant row, no
        # reply dial, the row gone.
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[closed_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                         False)
        assert provider.reply_dials == 0
        assert _parked_rows(tmp_path / "app.db") == []
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "parked" not in history
        assert history["turns"][-1]["assistant"] is None
        # The honest 409: the world is not waiting for a director.
        status, payload = stack.post("/api/world/continue", {})
        assert status == 409
        assert "停下来的世界" in payload["error"]
        # The next letter is the crank: it winds the fresh run (the
        # first one terminalized at its RESPONSE stop — C1-aR v2), the
        # narrator dials, the letter arrives and the NEW turn answers.
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "the second letter"})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["reply"] == REPLY
        assert final["turn_status"] == "COMPLETED"
        # The reply final carries no turn id (the parked shape's key
        # alone): the new turn is the facts table's other row.
        facts = _turn_facts(tmp_path / "app.db")
        assert len(facts) == 2
        assert closed_turn_id in facts
        (new_turn_id,) = [key for key in facts if key != closed_turn_id]
        assert facts[closed_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                         False)
        assert facts[new_turn_id] == ("COMPLETED", "REPLIED_FULL", True)
        assert provider.reply_dials == 1
        assert _parked_rows(tmp_path / "app.db") == []


# ---------------------------------------------------------------------------
# 3 — the supersession arms: a new letter closes the open round it runs
#     into (VAL ③ — the probe P-1 gap, now GREEN by construction)
# ---------------------------------------------------------------------------


def test_a_new_letter_supersedes_the_open_parked_round(
    tmp_path: Path,
) -> None:
    """The probe P-1 scenario, turned GREEN: the first letter parks, the
    second letter parks — the first round is closed on the spot
    (``NO_ASSISTANT_OUTPUT``, no assistant row) and the row belongs to
    the second round; the walk then brings the second letter's reply.
    The first turn is a transcript fact, never a GENERATING residue."""

    provider = _SequencedNarrator(
        [_STEP1, _STEP_PLAIN, _STEP3_LETTER]
    )
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "first letter body"})
        assert status == 200
        first_final, _worlds = _finals(raw)
        first_turn_id = first_final["turn_id"]
        assert first_final["parked"] is True
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[first_turn_id] == ("GENERATING", None, False)
        # The second letter: the desk's one open round is closed first.
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "second letter body"})
        assert status == 200
        second_final, _worlds = _finals(raw)
        second_turn_id = second_final["turn_id"]
        assert second_final["parked"] is True
        assert second_turn_id != first_turn_id
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[first_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                        False)
        assert facts[second_turn_id] == ("GENERATING", None, False)
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        assert json.loads(rows[0][1])["turn_id"] == second_turn_id
        # The walk: the letter arrives, the second round answers.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[first_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                        False)
        assert facts[second_turn_id] == ("COMPLETED", "REPLIED_FULL", True)


def test_a_new_letter_that_replies_clears_the_superseded_row(
    tmp_path: Path,
) -> None:
    """The supersession arm is not the park arm's tenant: a new letter
    whose own chain reaches the letter at once commits and answers —
    and the old row must be **gone**, not overwritten (a row pointing
    at a closed turn is the stale-row lie the read face refuses)."""

    provider = _SequencedNarrator([_STEP1, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "first letter body"})
        assert status == 200
        first_final, _worlds = _finals(raw)
        first_turn_id = first_final["turn_id"]
        assert _parked_rows(tmp_path / "app.db") != []
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "second letter body"})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        assert "parked" not in final
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[first_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                        False)
        assert len(facts) == 2
        (second_turn_id,) = [key for key in facts if key != first_turn_id]
        assert facts[second_turn_id] == ("COMPLETED", "REPLIED_FULL", True)
        assert _parked_rows(tmp_path / "app.db") == []


def test_a_restart_then_a_new_letter_closes_the_old_round(
    tmp_path: Path,
) -> None:
    """The crash-recovery face of the same law (the task's 重启后新信同
    关): the parked round survives a process death; the new epoch's
    first new letter **closes** it — the adoption the close face makes
    (RUNTIME §24) turns the old-epoch round into the same transcript
    fact — and parks its own round."""

    provider = _SequencedNarrator([_STEP1])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        first_final, _worlds = _finals(raw)
        first_turn_id = first_final["turn_id"]
    # The process is gone; a new epoch opens the same database.
    provider2 = _SequencedNarrator([_STEP_PLAIN])
    with web_stack(tmp_path / "app.db", provider=provider2) as stack:
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": "a letter after the restart"})
        assert status == 200
        second_final, _worlds = _finals(raw)
        assert second_final["parked"] is True
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[first_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                        False)
        assert facts[second_final["turn_id"]] == ("GENERATING", None, False)
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        assert json.loads(rows[0][1])["turn_id"] == second_final["turn_id"]


def test_the_blocking_face_supersedes_the_same_way(tmp_path: Path) -> None:
    """The blocking face (``/api/turn``) carries the supersession law
    too — its own supersede arm, not the stream face's: the first
    letter parks, the second letter parks, the first round is the same
    closed transcript fact and the row is the second round's."""

    provider = _SequencedNarrator([_STEP1, _STEP_PLAIN])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, first = stack.post("/api/turn", {"text": "first letter"})
        assert status == 200
        assert first["parked"] is True
        first_turn_id = first["turn_id"]
        status, second = stack.post("/api/turn", {"text": "second letter"})
        assert status == 200
        assert second["parked"] is True
        assert second["turn_id"] != first_turn_id
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[first_turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT",
                                        False)
        assert facts[second["turn_id"]] == ("GENERATING", None, False)
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        assert json.loads(rows[0][1])["turn_id"] == second["turn_id"]


# ---------------------------------------------------------------------------
# 4 — the checkpoints stay checkpoints (VAL ④) and the continue-face
#     awaits_you arm
# ---------------------------------------------------------------------------


def test_checkpoint_words_keep_the_lr4a_behavior(tmp_path: Path) -> None:
    """``she_thinks_of_you`` parks and continues exactly as before: the
    world turns on a bare continue, the round parks again, the turn
    still waits (a checkpoint is not an end — the word rides, the
    behavior is byte for byte lr-4a's)."""

    provider = _SequencedNarrator([_STEP_SHE_THINKS, _STEP_PLAIN])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        assert final["stop_kind"] == SHE_THINKS
        assert final["turn_status"] == "GENERATING"
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["stop_kind"] == "none"
        facts = _turn_facts(tmp_path / "app.db")
        assert list(facts.values()) == [("GENERATING", None, False)]


def test_awaits_you_on_a_continue_step_closes_too(tmp_path: Path) -> None:
    """The no-reply law is the stop's, not the entry's: an ``awaits_you``
    word on a continue's step closes the round the same way — the word
    rides the final, the transcript fact lands, the row goes."""

    provider = _SequencedNarrator([_STEP1, _STEP_AWAITS_YOU])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        assert final["stop_kind"] == AWAITS_YOU
        assert final["turn_status"] == "COMPLETED"
        facts = _turn_facts(tmp_path / "app.db")
        assert list(facts.values()) == [
            ("COMPLETED", "NO_ASSISTANT_OUTPUT", False)
        ]
        assert _parked_rows(tmp_path / "app.db") == []
        assert provider.reply_dials == 0


def test_the_awaits_you_crash_window_converges_on_continue(
    tmp_path: Path,
) -> None:
    """The durable residue a dead process leaves between the row write
    and the close (the crash window the park arms carry honestly): a
    row whose word already reads ``awaits_you`` with the turn still
    GENERATING converges on the owed close at the next continue — the
    world is never cranked past a word that said it was waiting."""

    provider = _SequencedNarrator([_STEP1, _STEP_PLAIN])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, _worlds = _finals(raw)
        turn_id = final["turn_id"]

        def mark_awaits_you(row: dict) -> None:
            row["stop_kind"] = AWAITS_YOU

        _rewrite_parked_row(tmp_path / "app.db", mark_awaits_you)
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["parked"] is True
        assert final["stop_kind"] == AWAITS_YOU
        assert final["turn_status"] == "COMPLETED"
        facts = _turn_facts(tmp_path / "app.db")
        assert facts[turn_id] == ("COMPLETED", "NO_ASSISTANT_OUTPUT", False)
        assert _parked_rows(tmp_path / "app.db") == []
        # The narrator never dialed for the crank: one script consumed
        # (the first park's step), the second still queued.
        assert len(provider.narrator_prompts()) == 1


# ---------------------------------------------------------------------------
# 5 — the immersive posture and the F-2 consumption law
# ---------------------------------------------------------------------------


def test_immersive_never_parks_and_never_closes(tmp_path: Path) -> None:
    """Immersive (the default) is byte for byte the pre-刀 posture: an
    ``awaits_you`` mid-chain keeps the world turning (nobody was asked
    to choose), the letter arrives, the reply answers, no parked key,
    no row, no close."""

    provider = _SequencedNarrator([_STEP_AWAITS_YOU, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 2
        assert final["reply"] == REPLY
        assert "parked" not in final
        assert "stop_kind" not in final
        assert final["stop"] == "letter_arrives"
        assert provider.reply_dials == 1
        facts = _turn_facts(tmp_path / "app.db")
        assert list(facts.values()) == [("COMPLETED", "REPLIED_FULL", True)]
        assert _parked_rows(tmp_path / "app.db") == []


def test_a_refused_reveal_keeps_the_pending_direction(
    tmp_path: Path, monkeypatch
) -> None:
    """F-2 (wr-10 处置登记，P14 项 — the 兜底 settle face): 选了即用即清
    consumes only after the step's own reveal settles. A refused reveal
    breaks the chain before any frame — and the director's input
    **survives** (the old order consumed it before the reveal, so the
    failure arm's 「offer stands」 was a lie about the one thing that
    mattered). The next letter rides the surviving direction and the
    consumed law lands whole (the row gone the moment the step
    settles)."""

    provider = _SequencedNarrator([_STEP1, _STEP3_LETTER])
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, _ = stack.post(
            "/api/world/direction",
            {"text": "let the fair arrive early"},
        )
        assert status == 200
        assert len(_pending_rows(app_db)) == 1
        # The first reveal refuses (the store's own Err shape); the
        # chain breaks before any frame lands.
        world_store = stack.box["host"].world_store
        original = world_store.reveal_all
        calls = {"n": 0}

        def flaky_reveal(world_id: str, now: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return Err(
                    DomainError(
                        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                        message="injected reveal refusal (F-2 fixture)",
                    )
                )
            return original(world_id, now)

        monkeypatch.setattr(world_store, "reveal_all", flaky_reveal)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, _worlds = _finals(raw)
        # No frame landed, so the letter is no stop point: the reply
        # answers — and the direction is still pending.
        assert final["reply"] == REPLY
        assert len(_pending_rows(app_db)) == 1
        # The next letter rides the surviving direction and consumes it
        # the moment its step settles (the wr-10 law, whole again).
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["reply"] == REPLY
        prompts = provider.narrator_prompts()
        assert "let the fair arrive early" in prompts[-1]
        assert _pending_rows(app_db) == []
