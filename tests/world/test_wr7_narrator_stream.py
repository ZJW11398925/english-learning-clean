"""wr-7 — the narration's streamed face (DEC-OPI-c73dbff3…4): the
incremental extractor and the narrator's streaming arm.

The world's narration was a single blocking provider call whose whole
answer arrived at once (the user's verdict: 「事件没有及时以流式慢慢显
现，而是在较长等待后突然全部闪现出来」). wr-7 splits the presentation's
time dimension without touching the durable contract: the provider's
optional streamed face feeds a pure-function state machine
(:class:`~elc.world.narrator.NarrationExtractor`) that decodes the
``narration`` string values' increments as they complete, and the
strict ``_parse_beats`` still rules on the whole text afterwards. The
pin groups:

1. **the extractor** — key matching happens outside string values only
   (``"narration":`` inside a narration's own prose is content), the
   beat index is the narration key's ordinal (key order independence —
   ``days`` may precede ``narration``), escapes cut by an increment
   boundary are held back and completed on the next increment (``\\n``
   split in half, ``\\uXXXX`` split after ``\\u4f``), everything
   outside narration values (kind values, ``days`` numbers, structure)
   emits nothing, and a stream ending mid-escape invents nothing;
2. **the streaming generate arm** — with ``on_increment`` and a
   provider carrying ``call_streaming`` the pieces leave in order and
   the return value is still the strict parse's (a well-formed batch
   passes; a malformed answer is refused whole while the already-shown
   increments stay real facts the callback recorded; a provider fault
   after shown pieces is the verbatim word with the partial stream
   preserved); without the callback, or without the face, the blocking
   dial of old runs and nothing leaves early;
3. **the orchestration seam** — ``run_generated_step`` forwards the
   callback (``on_narration_increment``) and the default ``None`` runs
   the step byte for byte as before.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

import pytest

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err, Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import (
    NARRATOR_SOURCE,
    NarrationExtractor,
    WorldNarrator,
)
from elc.world.package import (
    WORLD_PACKAGE_VERSION,
    CastMember,
    SupplyDeclaration,
    WorldPackage,
)
from elc.world.store import SqliteWorldStore

NOW = "2026-10-07T00:00:00+00:00"
WORLD = "world-main"
CALENDAR_START = "2025-09-14"

NARRATOR_MARK = "You are the narrator of a small fictional world"

#: Two beats whose JSON carries an escaped newline and a non-ASCII
#: ``\uXXXX`` escape — the decode pins' own material.
BEATS_ESCAPY = (
    '{"beats": ['
    '{"kind": "rain-tap", "narration": "Rain tapped on the'
    ' shutters.\\nIt kept the town awake.", "days": 1}, '
    '{"kind": "lamp-relit", "narration": "\\u716f\\u706b\\u718a'
    ' \\\"Berrymoor\\\" \\\\ stayed lit.", "days": 0}'
    "]}"
)


def _beats_object(text: str) -> dict:
    return json.loads(text)


def _join(pieces: tuple[tuple[int, str], ...]) -> dict[int, str]:
    joined: dict[int, str] = {}
    for index, piece in pieces:
        joined[index] = joined.get(index, "") + piece
    return joined


def _feed_all(extractor: NarrationExtractor, text: str, cut: int):
    pieces: list[tuple[int, str]] = []
    for start in range(0, len(text), cut):
        pieces.extend(extractor.feed(text[start : start + cut]))
    return pieces


# ---------------------------------------------------------------------------
# shared fixtures / helpers (the wr2 file's shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection (the w13 fixture
    shape)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _package(world_id: str = WORLD) -> WorldPackage:
    return WorldPackage(
        world_id=world_id,
        name="Calendar",
        version=WORLD_PACKAGE_VERSION,
        calendar_start=CALENDAR_START,
        setting=(
            "Calendar is a small harbour town on a cold coast.",
        ),
        cast=(CastMember(persona_id="persona-nell", name="Nell Alder"),),
        event_pool=(),
        supply=SupplyDeclaration(
            families=("DISC",), note="declared-not-consumed"
        ),
    )


def _seed_world(store: SqliteWorldStore, world_id: str = WORLD) -> None:
    assert store.create_world(world_id, "Calendar", None, NOW).value is not None


class _StreamingBeats:
    """A provider double with both faces: the blocking ``call`` answers
    whole, the streamed ``call_streaming`` emits the same text in
    scripted slices (arbitrary boundaries — mid-key, mid-escape) and
    records what it emitted and whether it was dialed at all."""

    def __init__(
        self,
        *,
        beats_text: str = BEATS_ESCAPY,
        reply_text: str = "A reply.",
        cuts: tuple[int, ...] | None = None,
        stream_error: str | None = None,
    ) -> None:
        self._beats = beats_text
        self._reply = reply_text
        self._cuts = cuts
        self._stream_error = stream_error
        self.prompts: list[str] = []
        self.streamed_prompts: list[str] = []
        self.emitted: list[str] = []
        self.blocking_calls = 0

    def _text_for(self, prompt: str) -> str:
        return self._beats if NARRATOR_MARK in prompt else self._reply

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        self.blocking_calls += 1
        return ProviderOutput(text=self._text_for(prompt.prompt_text), error=None)

    def call_streaming(
        self, prompt: CompiledPrompt, emit: Callable[[str], None]
    ) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        self.streamed_prompts.append(prompt.prompt_text)
        text = self._text_for(prompt.prompt_text)
        if self._stream_error is not None:
            # The honest partial stream: whatever the scripted cuts show
            # first stays shown, then the face answers the fault value.
            self._stream_to(text, emit)
            return ProviderOutput(text=None, error=self._stream_error)
        self._stream_to(text, emit)
        return ProviderOutput(text=text, error=None)

    def _stream_to(
        self, text: str, emit: Callable[[str], None]
    ) -> None:
        cuts = self._cuts if self._cuts is not None else (5, 11, 3)
        position = 0
        turn = 0
        while position < len(text):
            size = cuts[turn % len(cuts)]
            chunk = text[position : position + size]
            self.emitted.append(chunk)
            emit(chunk)
            position += size
            turn += 1


def _narrator_with_streaming(
    provider: _StreamingBeats,
    on_increment: Callable[[int, str], None] | None,
):
    return WorldNarrator(provider).generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="en",
        on_increment=on_increment,
    )


# ---------------------------------------------------------------------------
# 1 — the extractor (the pure-function state machine)
# ---------------------------------------------------------------------------


def test_the_extractor_switches_beat_indexes_in_order() -> None:
    """两 beat 的 index 切换分段正确：整批喂与逐字符喂同一答案，段界
    一致（0 → 1），拼接 == 权威 narration（VAL ③）。"""

    text = BEATS_ESCAPY
    expected = {
        index: beat["narration"]
        for index, beat in enumerate(_beats_object(text)["beats"])
    }
    whole = _join(NarrationExtractor().feed(text))
    assert whole == expected
    charwise = _join(_feed_all(NarrationExtractor(), text, 1))
    assert charwise == expected
    sliced = _join(_feed_all(NarrationExtractor(), text, 3))
    assert sliced == expected


def test_the_extractor_completes_escapes_cut_by_an_increment_boundary() -> None:
    """转义跨增量切割还原：``\\n`` 拆两半、``\\uXXXX`` 拆半（``\\u4f``
    之后断）各至少一例——未完成序列暂存至下一增量补齐（VAL ③）。"""

    newline_json = (
        '{"beats": [{"kind": "k", "narration": "a\\nb", "days": 0}]}'
    )
    expected = json.loads(newline_json)["beats"][0]["narration"]
    assert "\n" in expected
    head, tail = newline_json.split("\\n")
    cut_json = head + "\\n" + tail  # identical text; feed it split in half
    extractor = NarrationExtractor()
    pieces = extractor.feed(cut_json[: cut_json.index("b", 40)])
    pieces += extractor.feed(cut_json[cut_json.index("b", 40) :])
    assert _join(pieces) == {0: expected}

    unicode_json = (
        '{"beats": [{"kind": "k", "narration": "\\u4f60\\u597d",'
        ' "days": 0}]}'
    )
    expected_unicode = json.loads(unicode_json)["beats"][0]["narration"]
    assert expected_unicode == "你好"
    boundary = unicode_json.index("4f") + 2  # right after "4f"
    extractor = NarrationExtractor()
    pieces = extractor.feed(unicode_json[:boundary])
    pieces += extractor.feed(unicode_json[boundary:])
    assert _join(pieces) == {0: expected_unicode}


def test_the_extractor_never_matches_a_key_inside_a_string_value() -> None:
    """narration 内容含「narration」字样（含带冒号引号的伪装键形）不
    误判键名——字符串值内不做键匹配，闭引号才是段界（VAL ③）。"""

    text = (
        '{"beats": [{"kind": "k", "narration": "she wrote \\"narration\\":'
        ' twice, then \\"days\\": too", "days": 0}]}'
    )
    expected = json.loads(text)["beats"][0]["narration"]
    assert '"narration":' in expected  # the decoy really rides the prose
    whole = _join(NarrationExtractor().feed(text))
    assert whole == {0: expected}
    charwise = _join(_feed_all(NarrationExtractor(), text, 1))
    assert charwise == {0: expected}


def test_the_extractor_does_not_depend_on_the_json_key_order() -> None:
    """不依赖 JSON 键序：days 先于 narration（kind 亦然）仍正确提取，
    beat 序即 narration 键的序（VAL ③）。"""

    text = (
        '{"beats": ['
        '{"days": 2, "kind": "late", "narration": "Later still."}, '
        '{"days": 0, "kind": "soon", "narration": "Sooner."}'
        "]}"
    )
    whole = _join(NarrationExtractor().feed(text))
    assert whole == {0: "Later still.", 1: "Sooner."}
    charwise = _join(_feed_all(NarrationExtractor(), text, 1))
    assert charwise == whole


def test_the_extractor_emits_nothing_outside_narration_values() -> None:
    """流外文本零外发：kind 值、days 数字、结构字符一概不出（VAL ③）。"""

    text = BEATS_ESCAPY
    extractor = NarrationExtractor()
    pieces = extractor.feed(text)
    expected = {
        index: beat["narration"]
        for index, beat in enumerate(_beats_object(text)["beats"])
    }
    assert _join(pieces) == expected
    # No piece carries a kind word, a day number or bare structure.
    for _, piece in pieces:
        assert piece not in ("rain-tap", "lamp-relit")
        assert piece.strip("0123456789") != "" or piece == ""


def test_a_stream_ending_mid_escape_invents_nothing() -> None:
    """流在残缺转义处结束：普通串段照常出字，残缺转义零发明（余下的
    补齐交给下一个增量——没有下一个增量就什么都没有）。"""

    extractor = NarrationExtractor()
    pieces = extractor.feed(
        '{"beats": [{"kind": "k", "narration": "tail\\'
    )
    assert pieces == ((0, "tail"),), pieces
    pieces += extractor.feed('ndone.", "days": 0}]}')
    assert _join(pieces) == {0: "tail\ndone."}


# ---------------------------------------------------------------------------
# 2 — the streaming generate arm
# ---------------------------------------------------------------------------


def test_streamed_generate_emits_pieces_and_still_parses_whole() -> None:
    """流形生成：增量序外发（拼接 == 权威 narration），返回值仍经
    _parse_beats 严格验证——良形整批过（VAL ④）。"""

    provider = _StreamingBeats()
    seen: list[tuple[int, str]] = []
    result = _narrator_with_streaming(provider, lambda i, t: seen.append((i, t)))
    assert isinstance(result, Ok)
    assert [beat.narration for beat in result.value] == [
        beat["narration"]
        for beat in _beats_object(BEATS_ESCAPY)["beats"]
    ]
    joined = _join(tuple(seen))
    assert joined == {
        index: beat["narration"]
        for index, beat in enumerate(_beats_object(BEATS_ESCAPY)["beats"])
    }
    # The streamed face really dialed (the blocking face did not).
    assert len(provider.streamed_prompts) == 1
    assert provider.blocking_calls == 0


def test_a_refusal_keeps_the_shown_pieces_real_and_refuses_whole() -> None:
    """坏 JSON 整批拒：增量已发但 Err 的事实由回调记录保留——回调里
    的已显文本原样在列（渲染先行、持久殿后、拒收不撒谎），返回值是
    ``narrator refused: …`` 整批拒（VAL ④）。"""

    bad = '{"beats": [{"kind": "BAD KIND", "narration": "Shown already.", "days": 0}]}'
    provider = _StreamingBeats(beats_text=bad)
    seen: list[tuple[int, str]] = []
    result = _narrator_with_streaming(provider, lambda i, t: seen.append((i, t)))
    assert isinstance(result, Err)
    assert result.error.message.startswith("narrator refused:")
    assert "Shown already." in "".join(t for _, t in seen)


def test_a_stream_fault_after_shown_pieces_answers_the_verbatim_word() -> None:
    """流中途故障：已显增量保留在回调记录里，返回值 = 故障词 verbatim
    （timeout 形——回退臂与安静臂语义零改）（VAL ④）。"""

    provider = _StreamingBeats(stream_error="timeout")
    seen: list[tuple[int, str]] = []
    result = _narrator_with_streaming(provider, lambda i, t: seen.append((i, t)))
    assert isinstance(result, Err)
    assert result.error.message == "timeout"
    assert len(seen) > 0  # what the page saw stays real


def test_a_provider_without_the_stream_face_stays_blocking() -> None:
    """回退臂：provider 无 call_streaming（或回调缺省）⇒ blocking 同
    现状零增量——脚本双/裸启动的旧形字节不变（VAL ④）。"""

    class _BlockingOnly:
        """No ``call_streaming`` attribute at all — the scripted doubles'
        old shape (the capability probe finds nothing)."""

        def __init__(self) -> None:
            self.blocking_calls = 0

        def call(self, prompt: CompiledPrompt) -> ProviderOutput:
            self.blocking_calls += 1
            return ProviderOutput(text=BEATS_ESCAPY, error=None)

    provider = _BlockingOnly()
    seen: list[tuple[int, str]] = []
    result = _narrator_with_streaming(provider, lambda i, t: seen.append((i, t)))
    assert isinstance(result, Ok)
    assert seen == []
    assert provider.blocking_calls == 1

    # A streaming-capable provider without the callback stays blocking too.
    streaming_provider = _StreamingBeats()
    result = _narrator_with_streaming(streaming_provider, None)
    assert isinstance(result, Ok)
    assert streaming_provider.streamed_prompts == []
    assert streaming_provider.blocking_calls == 1


# ---------------------------------------------------------------------------
# 3 — the orchestration seam
# ---------------------------------------------------------------------------


def test_run_generated_step_forwards_the_narration_increments(
    store: SqliteWorldStore,
) -> None:
    """缝：run_generated_step 带 on_narration_increment ⇒ 增量透传且
    事件照常落库；默认 None ⇒ 字节不变的现状（VAL ④）。"""

    _seed_world(store)
    provider = _StreamingBeats()
    seen: list[tuple[int, str]] = []
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        provider,
        "turn-1",
        NOW,
        ui_language="en",
        on_narration_increment=lambda i, t: seen.append((i, t)),
    )
    assert isinstance(stepped, Ok)
    assert len(stepped.value) == 2
    assert all(event.source == NARRATOR_SOURCE for event in stepped.value)
    assert _join(tuple(seen)) == {
        index: beat["narration"]
        for index, beat in enumerate(_beats_object(BEATS_ESCAPY)["beats"])
    }
    assert provider.streamed_prompts and provider.blocking_calls == 0

    # The default arm: no callback, no stream — the step's durable half
    # is byte for byte the pre-wr-7 shape.
    provider_blocking = _StreamingBeats()
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        provider_blocking,
        "turn-2",
        NOW,
        ui_language="en",
    )
    assert isinstance(stepped, Ok)
    assert len(stepped.value) == 2
    assert provider_blocking.streamed_prompts == []
