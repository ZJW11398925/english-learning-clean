"""lr-1 — the world step chain over the real web stack
(DEC-OPI-c73dbff3…95, the natural-run engine face).

The user's seventh direction: 「写信不是发信息，传递需要时间……一切
都应当自然而然地进行」— the mechanical pipeline (one letter, one world
step, one immediate reply) is retired. The pins:

1. **the chain E2E** — a fake narrator answering turn by turn (no
   signal, no signal, ``letter_arrives``) streams
   ``world_delta＊ → world₁ → world_delta＊ → world₂ → world_delta＊ →
   world₃ → delta＊ → final`` in exactly that order; every step lands
   its own rows (the derived ids advance step by step — no two steps
   collide on one id); the reply is generated once, at the chain's
   tail; every narration shown on a frame is the authoritative
   chronicle text verbatim (I1);
2. **the elapsed days** — each step's ``elapsed_days`` is computed
   fresh from the world's own calendar: the first step's letter was
   sent 0 days ago, the next step's letter has traveled the story days
   the earlier steps landed (变异面: a chain whose steps never advance
   the day count is the bug this pin holds);
3. **the single-step regression** — a narrator that declares
   ``letter_arrives`` on its first answer is byte for byte the pre-lr-1
   shape (one world frame, the reply at the tail);
4. **the defensive ceiling** — a narrator that never raises the signal
   stops at :data:`MAX_CHAIN_STEPS` (a safety line, not a narrative
   rule — the prompt never carries a step count) and the reply is
   still generated; the ceiling's honesty lives in the source
   docstring, and the final payload never invents a stop word;
5. **the v1 restraint, honestly** — ``she_thinks_of_you`` /
   ``awaits_you`` keep the world turning in this cut (the full
   stop-round semantics belong to lr-4); the last step's own signal is
   what the final payload's ``stop`` key carries — never an invented
   verdict; a mid-chain refusal keeps the landed steps, answers the
   honest ``world_failed`` for the shown-but-unkept step, and the
   reply still goes out; the quiet arm still answers zero world
   frames;
6. **the blocking face** — the blocking turn carries the same chain
   under ``world_steps`` (every frame in order) with ``world`` holding
   the last step's frame, byte-compatible with the one-step shape.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

from elc.persona.types import CompiledPrompt, ProviderOutput
from tests.host.test_a1_streaming import (
    A1_TEXT,
    NARRATOR_MARK,
    _post,
    _sse_frames,
)
from tests.host.test_w1_web import REPLY, web_stack

REPO = Path(__file__).resolve().parents[2]


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows through a fresh read-only connection (the
    w13/wr7 posture — the worker thread owns the writable one)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(ro.execute(sql).fetchall())
    finally:
        ro.close()


def _beat(kind: str, narration: str, days: int) -> dict[str, object]:
    return {"kind": kind, "narration": narration, "days": days}


def _batch(*beats: dict[str, object], stop: str | None = None) -> str:
    """One scripted narrator answer: the beats batch, optionally
    carrying the narrator's own stop signal."""

    payload: dict[str, object] = {"beats": list(beats)}
    if stop is not None:
        payload["stop"] = {"kind": stop}
    return json.dumps(payload, ensure_ascii=False)


def _thirds(text: str) -> list[str]:
    third = max(1, len(text) // 3)
    return [text[0:third], text[third : 2 * third], text[2 * third :]]


class ChainProvider:
    """The chain's scripted double: the n-th narrator dial answers the
    n-th batch (the last repeats — the ceiling shape's own material),
    the letter's dial always answers the plain reply. The prompts it
    saw are the elapsed-days pins' reading instrument; with
    ``stream=True`` the answers stream in three slices (the streamed
    chain's world_delta frames ride the real stack)."""

    def __init__(
        self,
        *batches: str,
        reply_text: str = REPLY,
        stream: bool = True,
    ) -> None:
        self._batches = batches
        self._reply = reply_text
        self._narrations = 0
        self.prompts: list[str] = []
        self.stream = stream

    def _answer(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        if NARRATOR_MARK in prompt.prompt_text:
            index = min(self._narrations, len(self._batches) - 1)
            self._narrations += 1
            return ProviderOutput(text=self._batches[index], error=None)
        return ProviderOutput(text=self._reply, error=None)

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        return self._answer(prompt)

    def call_streaming(
        self, prompt: CompiledPrompt, emit: Callable[[str], None]
    ) -> ProviderOutput:
        output = self._answer(prompt)
        if output.error is None and output.text is not None:
            for piece in _thirds(output.text):
                emit(piece)
        return output


class BlockingChainProvider(ChainProvider):
    """The chain's blocking double (no streamed face — the blocking
    arm's chain shape): composition, not inheritance, so the class
    genuinely lacks ``call_streaming``."""

    def __init__(
        self, *batches: str, reply_text: str = REPLY
    ) -> None:
        self._inner = ChainProvider(*batches, reply_text=reply_text, stream=False)
        self.prompts = self._inner.prompts

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:  # type: ignore[override]
        return self._inner.call(prompt)


#: The three-step script: the world turns twice with no signal, the
#: third step lands the letter (its days sum: 1 + 2 → the third step's
#: letter has traveled three days).
STEP_ONE = _batch(_beat("morning-market", "早市在广场上支起来了。", 1))
STEP_TWO = _batch(_beat("tide-turns", "午后的潮水转向了。", 2))
STEP_THREE = _batch(
    _beat("letter-arrives", "她拆开了那封等了三天的信。", 0),
    stop="letter_arrives",
)


def _world_positions(types: list[str]) -> list[int]:
    return [i for i, t in enumerate(types) if t == "world"]


# ---------------------------------------------------------------------------
# 1 — the chain E2E (VAL ④)
# ---------------------------------------------------------------------------


def test_a_three_step_chain_streams_three_frames_then_the_reply(
    tmp_path: Path,
) -> None:
    """The natural-run shape over the real stack: the world turns three
    steps (two silent, one arrival) — each step's increments then its
    whole frame, the reply's deltas only after the chain, the final
    carrying the reply and the tail stop signal."""

    app_db = tmp_path / "app.db"
    provider = ChainProvider(STEP_ONE, STEP_TWO, STEP_THREE)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        world_pos = _world_positions(types)
        assert len(world_pos) == 3
        # The exact order: delta＊ → world ×3 → delta＊ → final.
        assert world_pos[0] > 0
        assert all(t == "world_delta" for t in types[: world_pos[0]])
        for first, second in zip(world_pos, world_pos[1:]):
            assert all(t == "world_delta" for t in types[first + 1 : second])
        assert types[world_pos[-1] + 1 : -1] == ["delta"] * 3
        assert types[-1] == "final"
        # The chain's tail signal rides the final payload.
        assert frames[-1]["stop"] == "letter_arrives"
        assert frames[-1]["reply"] == REPLY
        # I1: every frame's notes are the authoritative narrations,
        # verbatim — three steps, three narrations, one chronicle.
        narrations = [
            "早市在广场上支起来了。",
            "午后的潮水转向了。",
            "她拆开了那封等了三天的信。",
        ]
        for order, pos in enumerate(world_pos):
            assert [note["narration"] for note in frames[pos]["notes"]] == [
                narrations[order]
            ]
        chronicle = _ro_rows(
            app_db, "SELECT narration FROM world_event ORDER BY rowid"
        )
        assert [str(row[0]) for row in chronicle] == narrations


def test_each_step_lands_its_own_rows_and_the_ids_advance(
    tmp_path: Path,
) -> None:
    """Every step lands its own rows under one anchor run — the derived
    ids advance step by step (the count arm re-reads the chronicle each
    step), so no step overwrites another and the run count stays one."""

    app_db = tmp_path / "app.db"
    provider = ChainProvider(STEP_ONE, STEP_TWO, STEP_THREE)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        ids = [
            str(row[0])
            for row in _ro_rows(
                app_db, "SELECT event_id FROM world_event ORDER BY rowid"
            )
        ]
        assert len(ids) == 3
        assert len(set(ids)) == 3
        # The count arm's ordinals advance across the chain steps.
        assert ids == [f"run-berrymoor-0000:g{i}" for i in range(3)]
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_run")[0][0] == 1
        )
        # 帧即揭示, every step: nothing left pending after the chain.
        assert (
            _ro_rows(
                app_db,
                "SELECT COUNT(*) FROM world_reveal_item"
                " WHERE status = 'PENDING'",
            )[0][0]
            == 0
        )


def test_elapsed_days_advance_across_the_chain(tmp_path: Path) -> None:
    """The letter's journey, as the world's own calendar tells it: the
    first step's letter was sent 0 days ago; after a 1-day beat the
    next step's letter has traveled 1 day; after a 2-day beat, 3 —
    each step's prompt is computed fresh (a chain whose steps all see
    the same day count is the bug this pin holds)."""

    app_db = tmp_path / "app.db"
    provider = ChainProvider(STEP_ONE, STEP_TWO, STEP_THREE)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        narrator_prompts = [
            p for p in provider.prompts if NARRATOR_MARK in p
        ]
        assert len(narrator_prompts) == 3
        assert "it was sent 0 days ago" in narrator_prompts[0]
        assert "it was sent 1 day ago" in narrator_prompts[1]
        assert "it was sent 3 days ago" in narrator_prompts[2]
        # The journey is named, the contents never are (WR-4 rides the
        # chain too).
        for prompt in narrator_prompts:
            assert "please look in on him" not in prompt


# ---------------------------------------------------------------------------
# 2 — the single-step regression (VAL ④'s compatibility face)
# ---------------------------------------------------------------------------


def test_a_single_step_letter_arrives_matches_the_old_shape(
    tmp_path: Path,
) -> None:
    """模型一步停: a narrator that declares ``letter_arrives`` on its
    first answer runs the chain exactly one step — the streamed order
    is byte for byte the pre-lr-1 shape (world_delta＊ → world →
    delta＊ → final), the durable half lands once."""

    app_db = tmp_path / "app.db"
    one_step = _batch(
        _beat("letter-arrives", "她拆开了信。", 1),
        stop="letter_arrives",
    )
    provider = ChainProvider(one_step)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        world_pos = types.index("world")
        assert types[0] == "world_delta"
        assert all(t == "world_delta" for t in types[:world_pos])
        assert types[world_pos + 1 : -1] == ["delta"] * 3
        assert types[-1] == "final"
        assert frames[-1]["stop"] == "letter_arrives"
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 1
        )
        assert len(provider.prompts) == 2  # one narration + one reply


# ---------------------------------------------------------------------------
# 3 — the defensive ceiling (VAL ⑤)
# ---------------------------------------------------------------------------


def test_the_chain_stops_at_the_defensive_ceiling_and_replies_anyway(
    tmp_path: Path,
) -> None:
    """A narrator that never raises the signal stops the world at
    MAX_CHAIN_STEPS — five frames land, and the reply is still
    generated (the safety line, never a broken round). The final
    payload invents no stop word."""

    app_db = tmp_path / "app.db"
    never = _batch(_beat("endless-drizzle", "细雨下个不停。", 0))
    provider = ChainProvider(never)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert len(_world_positions(types)) == 5
        assert types[-1] == "final"
        assert frames[-1]["reply"] == REPLY
        assert "stop" not in frames[-1]
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 5
        )


def test_the_ceiling_is_a_safety_line_the_prompt_never_carries() -> None:
    """The ceiling's honesty lives in the source: the constant is
    annotated as a safety line (never a narrative rule) and the chain's
    docstring says the same — while the prompt factory carries no step
    count anywhere (the narrative invitation only)."""

    from elc.web import MAX_CHAIN_STEPS, _WebFace

    assert MAX_CHAIN_STEPS == 5
    import elc.web as web_source_module

    source = Path(web_source_module.__file__).read_text(encoding="utf-8")
    assert "A safety line, never a narrative rule" in source
    doc = _WebFace._world_step_frame.__doc__ or ""
    assert "safety line" in doc
    assert "letter_arrives" in doc
    narrator_source = (
        Path(__file__).resolve().parents[2]
        / "src" / "elc" / "world" / "narrator.py"
    ).read_text(encoding="utf-8")
    # The narrator's own module keeps the letter section rule-free (the
    # invitation, not a deadline) — the two faces agree.
    assert "no step count, no deadline" in narrator_source


# ---------------------------------------------------------------------------
# 4 — the v1 restraint and the failure arms (VAL ⑥ / wr-7's honesty)
# ---------------------------------------------------------------------------


def test_non_letter_signals_keep_the_world_turning_and_ride_the_final(
    tmp_path: Path,
) -> None:
    """The v1 restraint: ``she_thinks_of_you`` is a checkpoint, not an
    end — the world keeps turning after it, and the round ends when the
    letter arrives. The final's ``stop`` carries the chain tail's own
    signal, never an invented verdict."""

    app_db = tmp_path / "app.db"
    provider = ChainProvider(
        _batch(
            _beat("a-thought", "她忽然想起了写信的人。", 0),
            stop="she_thinks_of_you",
        ),
        _batch(
            _beat("letter-arrives", "信到了，她坐在门廊上读完了它。", 1),
            stop="letter_arrives",
        ),
    )
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert len(_world_positions(types)) == 2
        assert types[-1] == "final"
        assert frames[-1]["stop"] == "letter_arrives"
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 2
        )


def test_a_ceiling_chain_with_a_non_letter_signal_reports_that_signal(
    tmp_path: Path,
) -> None:
    """A chain that hits the ceiling whose last step still declared a
    non-letter signal answers that signal honestly (the last step's own
    verdict) — it is the caller's raw material, not a verdict the
    engine invented."""

    app_db = tmp_path / "app.db"
    waiting = _batch(
        _beat("the-world-waits", "镇子安静下来，像在等什么。", 0),
        stop="awaits_you",
    )
    provider = ChainProvider(waiting)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        assert len(_world_positions([f["type"] for f in frames])) == 5
        assert frames[-1]["stop"] == "awaits_you"


def test_a_mid_chain_refusal_keeps_landed_steps_and_answers_world_failed(
    tmp_path: Path,
) -> None:
    """拒收不撒谎, chain edition: step one lands (and streams), step
    two's answer is refused after its pieces were shown — the honest
    ``world_failed`` frame follows the landed frame, the landed step's
    rows stay, and the reply still goes out."""

    app_db = tmp_path / "app.db"
    refused = json.dumps(
        {
            "beats": [
                {"kind": "BAD KIND", "narration": "Refused.", "days": 0}
            ]
        }
    )
    provider = ChainProvider(STEP_ONE, refused)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert types.count("world") == 1
        assert "world_failed" in types
        assert types.index("world") < types.index("world_failed")
        assert types[-1] == "final"
        assert frames[-1]["reply"] == REPLY
        # The landed step stays landed; the refused step wrote nothing.
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 1
        )


def test_the_quiet_arm_still_answers_zero_world_frames(tmp_path: Path) -> None:
    """The quiet arm (no coordinates) ends the chain before the first
    frame: zero world frames of any kind, the reply at once — the
    fail-soft posture the chain inherits untouched."""

    app_db = tmp_path / "app.db"
    provider = ChainProvider(STEP_ONE)
    provider_stream = provider.call_streaming

    def quiet_stream(
        prompt: CompiledPrompt, emit: Callable[[str], None]
    ) -> ProviderOutput:
        if NARRATOR_MARK in prompt.prompt_text:
            return ProviderOutput(text=None, error="not-configured")
        return provider_stream(prompt, emit)

    provider.call_streaming = quiet_stream  # type: ignore[method-assign]
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert "world" not in types
        assert "world_delta" not in types
        assert "world_failed" not in types
        assert types[0] == "delta"
        assert types[-1] == "final"
        assert "stop" not in frames[-1]


# ---------------------------------------------------------------------------
# 5 — the blocking face (VAL ⑥'s blocking arm)
# ---------------------------------------------------------------------------


def test_the_blocking_turn_carries_world_steps_and_stop(tmp_path: Path) -> None:
    """The blocking turn answers the whole chain under ``world_steps``
    (every frame in order) with ``world`` holding the last step's frame
    and ``stop`` the tail signal — and a one-step chain answers byte
    for byte the pre-lr-1 shape (no ``world_steps`` key at all)."""

    app_db = tmp_path / "app.db"
    provider = BlockingChainProvider(STEP_ONE, STEP_TWO, STEP_THREE)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn", {"text": A1_TEXT})
        assert status == 200
        payload = json.loads(raw.decode("utf-8"))
        steps = payload["world_steps"]
        assert [s["type"] for s in steps] == ["world", "world", "world"]
        assert payload["world"] == steps[-1]
        assert payload["stop"] == "letter_arrives"
        assert payload["reply"] == REPLY
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 3
        )

    app_db_one = tmp_path / "one.db"
    one_provider = BlockingChainProvider(
        _batch(
            _beat("letter-arrives", "她拆开了信。", 0),
            stop="letter_arrives",
        )
    )
    with web_stack(app_db_one, provider=one_provider) as stack:
        status, raw = _post(stack.port, "/api/turn", {"text": A1_TEXT})
        assert status == 200
        payload = json.loads(raw.decode("utf-8"))
        assert "world_steps" not in payload
        assert payload["world"]["type"] == "world"
        assert payload["stop"] == "letter_arrives"
