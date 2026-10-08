"""lr-4a — the directed-mode **stop-point round** (走向停点轮,
DEC-OPI-c73dbff3…128, the user's eleventh verdict's full repair).

The user's verdict: 「发送信件后，系统一直在推进，给出的选项还没选就已
经结束了……既然是导演模式选项，每一个选择点就应当决定接下来一步的走
向」— every step is a choice point. The pins, over the production
assembly (the real ``run_web`` over the real ``open_host``, the wr-10
suite's own shape):

1. **the parked round end to end** (VAL ③) — a directed letter turns
   the world **one step** and parks: the final carries ``reply: null``,
   ``parked: true``, ``stop: awaits_direction`` and the candidates; the
   turn rests nonterminal at GENERATING with no reply dial (the parked
   half never enters generation);
2. **the walk** — a chosen direction rides the continue's step prompt
   (the director's input, consumed on success) and the round parks
   again; a directionless continue walks too (the world's own
   discretion is legal); the letter arriving flips the round to its
   reply phase and ``begin_turn`` re-enters with the **same command**
   (the idempotent CP0 replay continues the parked turn — one turn
   record, one user letter, the full reply) and the round closes;
3. **a refusing step** keeps the round parked (fail-soft — the round
   waits, the offer stands);
4. **the cap** (R7's safety line) — the directionless crank ceiling
   stops bare continues and answers ``capped``; a chosen direction
   moves the world past any count;
5. **the half-round refresh recovery** (VAL ⑤) — history reports the
   parked round additively (``parked`` + ``parked_directions``) with
   the user line and the world frames and no reply, and answers the
   keyless payload once the round is over;
6. **the crash recovery** — the parked round survives a process
   restart: the new epoch's continue runs the step, the letter arrives
   and the re-entry **adopts the old-epoch turn** (the §23/§24
   semantics — zero new recovery code) and the reply lands;
7. **the immersive byte compatibility** (R6/VAL ⑥) — immersive runs
   the pre-lr-4a chain whole (multi-step, one reply, no parking, no
   row) and the blocking face keeps its world-key shapes;
8. **the copy verdicts** (R5/VAL ⑦) — the candidates ask for *the
   immediate next step the world takes*, the label a few words, and
   the page carries the bilingual waiting sentences.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.world.narrator import MIN_DIRECTIONS, build_narrator_prompt
from tests.host.test_a1_streaming import _post, _sse_frames
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import NARRATOR_MARK
from tests.host.test_wr10_web_directions import _pending_rows

REPO = Path(__file__).resolve().parents[2]

#: The parking row's key for the served conversation (the lr-4a prefix
#: plus the conversation id — one parked round per desk).
_PARKED_KEY = "world_parked_turn:web-test"

#: The world step answers, scripted per narrator dial (a queue): step
#: one turns without the letter (candidates A), step two turns without
#: the letter (candidates B), step three brings the letter ashore.
_CANDIDATES_A = (
    {"label": "a storm rolls in", "hint": "The harbour braces for weather."},
    {"label": "the fair arrives", "hint": "Tents dot the cliff meadow."},
)
_CANDIDATES_B = (
    {"label": "the keeper travels", "hint": "The light goes dark a night."},
    {"label": "a whale passes", "hint": "A spout off the headland."},
)


def _beats(
    candidates: tuple[dict[str, str], ...],
    *,
    stop: str | None = None,
    narration: str = "The harbour kept its morning silence.",
) -> str:
    """One directed narrator answer: one beat, the candidates, the
    optional stop verdict."""

    answer: dict[str, object] = {
        "beats": [
            {
                "kind": "quiet-morning",
                "narration": narration,
                "days": 0,
            },
        ],
        "directions": list(candidates),
    }
    if stop is not None:
        answer["stop"] = {"kind": stop}
    return json.dumps(answer)


_STEP1 = _beats(_CANDIDATES_A)
_STEP2 = _beats(
    _CANDIDATES_B,
    narration="A stranger walked the cliff path to the keeper's door.",
)
_STEP3_LETTER = _beats(
    (),
    stop="letter_arrives",
    narration="She broke the seal and read your letter by the window.",
)

#: The broken answer (a beats-shaped refusal): the whole batch dies.
_REFUSING = json.dumps(
    {"beats": [{"kind": "BAD KIND", "narration": "Refused.", "days": 0}]}
)


class _SequencedNarrator:
    """The scripted double (the BeatsProvider posture with a queue): a
    dial whose prompt carries the narrator's mark pops the next scripted
    beats answer; every other dial is the reply's generation. The
    prompts it saw are the wiring's reading instrument, and the reply
    dial **count** is the no-generation-while-parked proof."""

    def __init__(self, scripts: list[str]) -> None:
        self._scripts = list(scripts)
        self.prompts: list[str] = []
        self.reply_dials = 0

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        if NARRATOR_MARK in prompt.prompt_text:
            assert self._scripts, "the script ran dry — the test overshot"
            return ProviderOutput(text=self._scripts.pop(0), error=None)
        self.reply_dials += 1
        return ProviderOutput(text=REPLY, error=None)

    def narrator_prompts(self) -> list[str]:
        return [prompt for prompt in self.prompts if NARRATOR_MARK in prompt]


def _set_directed(stack: object) -> None:
    """The mode write over the real settings route (the wr-10 face)."""

    status, payload = stack.post(  # type: ignore[attr-defined]
        "/api/settings/world_direction_mode",
        {"world_direction_mode": "directed"},
    )
    assert status == 200, payload
    assert payload["accepted"] is True


def _parked_rows(app_db: Path) -> list[tuple[str, str]]:
    """The parking rows off the serving database (the w13 ro posture)."""

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


def _turn_rows(app_db: Path) -> list[tuple[str, str]]:
    """Every turn record's ``(id, status)`` — the round's own shape."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return [
            (str(row[0]), str(row[1]))
            for row in ro.execute(
                "SELECT turn_id, status FROM turn_record ORDER BY turn_id"
            ).fetchall()
        ]
    finally:
        ro.close()


def _finals(raw: bytes) -> tuple[dict, list[dict]]:
    """The stream's one final and its world frames (the reading shape
    every pinned flow below walks twice)."""

    frames = _sse_frames(raw)
    finals = [f for f in frames if f["type"] == "final"]
    worlds = [f for f in frames if f["type"] == "world"]
    assert len(finals) == 1
    return finals[0], worlds


# ---------------------------------------------------------------------------
# 1 — the parked round end to end (VAL ③), the walk, the letter, the
#     same-command re-entry
# ---------------------------------------------------------------------------


def test_the_directed_round_parks_then_walks_to_the_letter(
    tmp_path: Path,
) -> None:
    """The full walk (VAL ③): a directed letter parks after step one
    (the candidates on the final), a chosen direction walks step two
    (the prompt carried it, the pending row consumed), a bare continue
    walks step three — where the letter arrives and the **same command**
    re-enters: one turn record, the reply, the round closed."""

    provider = _SequencedNarrator([_STEP1, _STEP2, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        # The letter parks after one step.
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert worlds[0]["directions"] == list(_CANDIDATES_A)
        assert final["parked"] is True
        assert final["stop"] == "awaits_direction"
        assert final["reply"] is None
        assert final["turn_status"] == "GENERATING"
        assert final["directions"] == list(_CANDIDATES_A)
        assert final.get("capped") is None
        # The round is durable: the turn rests nonterminal, no reply was
        # dialed (the parked half never enters generation), the row is
        # written.
        turns = _turn_rows(tmp_path / "app.db")
        assert len(turns) == 1
        assert turns[0][1] == "GENERATING"
        assert provider.reply_dials == 0
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        parked = json.loads(rows[0][1])
        assert parked["phase"] == "chain"
        assert parked["stops"] == 1
        assert parked["directions"] == list(_CANDIDATES_A)
        # The choice parks, then the continue walks step two with it.
        status, payload = stack.post(
            "/api/world/direction",
            {
                "label": _CANDIDATES_A[0]["label"],
                "hint": _CANDIDATES_A[0]["hint"],
            },
        )
        assert status == 200 and payload["accepted"] is True
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["stop"] == "awaits_direction"
        assert final["directions"] == list(_CANDIDATES_B)
        # The director's input rode this step's prompt and was consumed
        # (the wr-10 law untouched); the round's stop count advanced.
        prompts = provider.narrator_prompts()
        assert "The user's chosen direction" in prompts[-1]
        assert _CANDIDATES_A[0]["label"] in prompts[-1]
        assert _pending_rows(tmp_path / "app.db") == []
        rows = _parked_rows(tmp_path / "app.db")
        assert json.loads(rows[0][1])["stops"] == 2
        # A bare continue walks step three — the letter arrives, the
        # re-entry answers, the round closes.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final.get("parked") is None
        assert final["reply"] == REPLY
        assert final["turn_status"] == "COMPLETED"
        # The re-entry replayed the SAME command: one turn record total,
        # one user letter, the turn terminal, the row gone.
        turns = _turn_rows(tmp_path / "app.db")
        assert len(turns) == 1
        assert turns[0][1] == "COMPLETED"
        assert _parked_rows(tmp_path / "app.db") == []
        assert provider.reply_dials == 1
        # History tells the whole round: the user line, three world
        # frames, the reply — and no parked key.
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "parked" not in history
        turn = history["turns"][-1]
        assert turn["assistant"] == REPLY
        assert len(turn["world_steps"]) == 3


def test_the_replied_round_refuses_further_continues(
    tmp_path: Path,
) -> None:
    """The round is over, the row is gone: a further continue answers
    the honest 409 人话 (no parked round), and the turn table still
    holds exactly one turn — the re-entry replayed the parked command,
    it never minted a second one."""

    provider = _SequencedNarrator([_STEP1, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        status, payload = stack.post("/api/world/continue", {})
        assert status == 409
        assert "停下来的世界" in payload["error"]
        assert len(_turn_rows(tmp_path / "app.db")) == 1


# ---------------------------------------------------------------------------
# 2 — directionless walking, refusing steps, the cap
# ---------------------------------------------------------------------------


def test_continue_without_a_choice_walks_the_world_anyway(
    tmp_path: Path,
) -> None:
    """Not choosing is legal (the world's own discretion): a bare
    continue turns the world one step with no chosen-direction section
    in the prompt and parks again with the fresh candidates."""

    provider = _SequencedNarrator([_STEP1, _STEP2])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["directions"] == list(_CANDIDATES_B)
        prompt = provider.narrator_prompts()[-1]
        assert "The user's chosen direction" not in prompt


def test_a_refusing_step_keeps_the_round_parked(
    tmp_path: Path,
) -> None:
    """A narrator refusal on the continue's step (fail-soft, lr-1's
    law): nothing lands, the round stays parked with the standing
    offer, and the stop count still advances (the world could not
    move)."""

    provider = _SequencedNarrator([_STEP1, _REFUSING])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert worlds == []
        assert final["parked"] is True
        assert final["directions"] == list(_CANDIDATES_A)
        rows = _parked_rows(tmp_path / "app.db")
        parked = json.loads(rows[0][1])
        assert parked["stops"] == 2
        assert parked["phase"] == "chain"
        turns = _turn_rows(tmp_path / "app.db")
        assert turns[0][1] == "GENERATING"


def test_the_directionless_crank_ceiling_stops_bare_continues(
    tmp_path: Path, monkeypatch
) -> None:
    """R7's safety line: with the ceiling at one, a bare continue is
    refused with ``capped`` (no step, no dial, the offer stands) — and
    a chosen direction moves the world past any count."""

    import elc.web as web_module

    monkeypatch.setattr(web_module, "MAX_PARKED_STOPS", 1)
    provider = _SequencedNarrator([_STEP1, _STEP2, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        # The bare continue hits the ceiling: capped, no step, no dial.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert worlds == []
        assert final["parked"] is True
        assert final["capped"] is True
        assert final["directions"] == list(_CANDIDATES_A)
        assert len(provider.narrator_prompts()) == 1
        # A chosen direction bypasses the ceiling: the step runs.
        status, payload = stack.post(
            "/api/world/direction",
            {
                "label": _CANDIDATES_A[1]["label"],
                "hint": _CANDIDATES_A[1]["hint"],
            },
        )
        assert status == 200 and payload["accepted"] is True
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["capped"] is False


# ---------------------------------------------------------------------------
# 3 — the half-round refresh recovery (VAL ⑤)
# ---------------------------------------------------------------------------


def test_history_reports_the_parked_round_additively(
    tmp_path: Path,
) -> None:
    """The refresh recovery's read half: history carries ``parked`` and
    ``parked_directions`` only while the round waits (the user line and
    the world frames ride the turns; the reply is absent — the half
    round), and the keyless payload returns the moment the round is
    over. The worldless history stays keyless."""

    provider = _SequencedNarrator([_STEP1, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        # The worldless history: no parked keys at all.
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "parked" not in history
        assert "parked_directions" not in history
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert history["parked"] is True
        assert history["parked_directions"] == list(_CANDIDATES_A)
        turn = history["turns"][-1]
        assert turn["user"] == CLEAN_TEXT
        assert turn["assistant"] is None
        # One step: the single frame rides ``world`` (the world_steps key
        # belongs to multi-frame rounds only, the lr-2 law). The frame
        # itself carries no candidates — they are not durable; the
        # waiting state's candidates ride ``parked_directions`` above.
        assert turn["world"]["notes"]
        # The round closes: the additive keys go with it.
        status, _raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "parked" not in history
        assert "parked_directions" not in history


# ---------------------------------------------------------------------------
# 4 — the crash recovery (R7's 勘察点, the durable answer)
# ---------------------------------------------------------------------------


def test_a_parked_round_survives_a_restart_through_the_same_command(
    tmp_path: Path,
) -> None:
    """The parked round is durable across a process death: the new
    epoch's continue runs the step, the letter arrives and the re-entry
    **adopts the old-epoch nonterminal turn** (the §23/§24 recovery
    semantics — zero new recovery code) and the reply lands. The
    startup scan leaves the persona turn alone (the §23 re-entry
    semantics); the parking row is the memory."""

    provider = _SequencedNarrator([_STEP1])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        turns_before = _turn_rows(tmp_path / "app.db")
        assert turns_before[0][1] == "GENERATING"
    # The process is gone; a new one opens the same database (a new
    # epoch) with the letter-arrival script.
    provider2 = _SequencedNarrator([_STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider2) as stack:
        rows = _parked_rows(tmp_path / "app.db")
        assert len(rows) == 1
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        assert final["turn_status"] == "COMPLETED"
        turns = _turn_rows(tmp_path / "app.db")
        assert len(turns) == 1
        assert turns[0][0] == turns_before[0][0]
        assert turns[0][1] == "COMPLETED"
        assert _parked_rows(tmp_path / "app.db") == []


# ---------------------------------------------------------------------------
# 5 — the immersive byte compatibility (R6/VAL ⑥) and the blocking face
# ---------------------------------------------------------------------------


def test_immersive_mode_runs_the_whole_chain_with_zero_parking(
    tmp_path: Path,
) -> None:
    """Immersive (the default) is the pre-lr-4a chain byte for byte:
    the world turns step after step in **one request** until the letter
    arrives, the reply answers, no parked key, no row, no waiting."""

    provider = _SequencedNarrator([_STEP1, _STEP2, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 3
        assert final["reply"] == REPLY
        assert "parked" not in final
        assert final["stop"] == "letter_arrives"
        assert provider.reply_dials == 1
        assert len(_turn_rows(tmp_path / "app.db")) == 1
        assert _parked_rows(tmp_path / "app.db") == []
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "parked" not in history


def test_the_blocking_turn_face_parks_with_its_world_keys(
    tmp_path: Path,
) -> None:
    """The blocking face (the stream fallback's tenant) parks with the
    same contract plus its world keys: the frame rides ``world``, the
    parked shape rides beside it — the page's fallback arm renders the
    world block and then the waiting state."""

    provider = _SequencedNarrator([_STEP1, _STEP3_LETTER])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["parked"] is True
        assert turn["stop"] == "awaits_direction"
        assert turn["reply"] is None
        assert turn["directions"] == list(_CANDIDATES_A)
        assert turn["world"]["directions"] == list(_CANDIDATES_A)
        assert provider.reply_dials == 0


# ---------------------------------------------------------------------------
# 6 — the copy verdicts (R5/VAL ⑦) and the page's parked state
# ---------------------------------------------------------------------------


def test_the_candidates_ask_for_the_immediate_next_step() -> None:
    """R5's copy verdict, at the prompt's own door: a direction is the
    **immediate next step the world takes** (never a far horizon), the
    label is a few words, never a sentence — the user's 「给的文案也有
    问题」 repaired at the source."""

    from tests.world.test_wr10_directions import _package

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        direction_mode="directed",
    )
    assert "the immediate" in prompt
    assert "next step the world takes" in prompt
    assert "never a far horizon" in prompt
    assert "a few words, never a sentence" in prompt
    assert MIN_DIRECTIONS >= 2


def test_the_page_carries_the_waiting_state() -> None:
    """The page half (R4): the waiting state's renderer, the continue
    walker and the parked arms ride the served sources — the bilingual
    waits sentence, the continue button, the cap sentence, and the
    shared stream reader behind both fetchers."""

    app = (REPO / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "故事停在这里——下一笔，由你来落。" in app
    assert "The story rests here — the next line is yours." in app
    assert "让世界继续" in app
    assert "Let the world go on" in app
    assert "世界已经走了很远，还没收到你的方向" in app
    assert "function renderWorldWaits" in app
    assert "function enterParkedRound" in app
    assert "async function postContinue" in app
    assert "if (parkedRound) postContinue();" in app
    # The parked final's arms: no seam, no unseal, no failure line.
    assert "worldStream.closeChain(data.parked !== true);" in app
    assert "if (!(data && data.parked === true)) {" in app
    # The refresh recovery reads the additive history keys.
    assert "data.parked_directions || []" in app
    api = (REPO / "src" / "elc" / "webui" / "api.js").read_text(
        encoding="utf-8"
    )
    assert "export async function fetchWorldContinue" in api
    assert "/api/world/continue" in api
    assert "async function consumeTurnStream" in api


def test_the_parked_chrome_waits_for_the_chain_to_settle() -> None:
    """lr-3R (DEC-OPI-09b3935b…1): the parked chrome rides the settle
    gate — the user's dogfood signal was the chrome (hint row, direction
    options, continue button) landing while the world's generational
    chain was still typing (the server's final ≠ the client finished).
    The pins, over the served source: the gate reads the stream's
    ``settled``/``done`` getters, the token cancel arm arms
    ``exitParkedRound``, the 60s defense ceiling stands, both parked
    arms pass their own worldStream, the recovery arm passes ``null``,
    the recast copy rides the T table and zero residue of the old
    sentences remains."""

    app = (REPO / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )
    # ① The gate exists and reads the stream's settled/done getters
    #    (the wr-11 gate law generalized: the reply typing waits for the
    #    chain, so does the parked chrome).
    assert "function renderWorldWaitsWhenSettled" in app
    assert "!stream.settled && !stream.done" in app
    # ② The token cancel arm: exitParkedRound bumps the gate token —
    #    a pending render dies when a new letter leaves or the reply
    #    lands.
    exit_body = app[app.index("function exitParkedRound"):]
    exit_body = exit_body[:exit_body.index("\n}")]
    assert "worldWaitsGateToken += 1" in exit_body
    # ③ The 60s defense ceiling (a Date.now deadline, fallback render).
    assert "Date.now() + 60000" in app
    assert "Date.now() >= deadline" in app
    # ④ Zero residue of the old sentences (both languages, both keys).
    assert "世界在等你决定下一步" not in app
    assert "The world waits for your direction" not in app
    assert "世界接下来可以往哪走" not in app
    assert "Where could the world go next" not in app
    # ⑤ The recast copy rides the T table (both languages): the hint
    #    line carries the mood, the ask line carries the instruction.
    assert 'worldWaits: "故事停在这里——下一笔，由你来落。"' in app
    assert (
        'worldWaits: "The story rests here'
        ' — the next line is yours."' in app
    )
    assert 'directionAsk: "选一个走向，或自己写一个。"' in app
    assert 'directionAsk: "Pick a direction — or write your own."' in app
    # ⑥ The call shapes: both in-stream parked arms pass their own
    #    worldStream; the refresh recovery passes null (renders
    #    immediately, as before).
    assert "enterParkedRound(letterNode, flowIndex, worldStream," in app
    assert (
        "enterParkedRound(mine, flowTurns.length - 1, worldStream,"
        in app
    )
    assert (
        "enterParkedRound(lastUserNode, flowTurns.length - 1, null,"
        in app
    )
