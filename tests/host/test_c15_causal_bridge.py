"""C1.5 — the intermediary-causality bridge (DEC-OPI-b290799a…36, the
external review HIGH-2's root fix).

WR-4's two-layer law kept every letter word out of the world's
narration but left no door for its one world-inbound fact: she read
it. The letter could move her pen (the penpal layer's reply) yet never
her life (the world layer's beats) — unless the user walked the
director's door by hand. C1.5 names the bridge: the reply layer parks
a deterministic, zero-letter-word projection (the binding actor's
persona id + one summary sentence) after a reply lands; the next
letter's world chain rides it into the narrator's prompt as the
letter-read reaction section (its own door — never the pending-direction
key's); the narrator writes her reaction as a beat with her
``participants``; and the C1-c cognitive view carries that reaction
into her next reply's ``recent_world_events`` — 信 → 她读 → 她反应 →
世界续转 → 下一封回信她知道发生过什么.

Pin groups:

1. **the prompt contract** — the reaction section rides only when
   ``letter_response`` is passed (persona id + summary verbatim, the
   never-quote teaching present, placed after the letter-on-its-way
   section); ``None`` (explicit or omitted) keeps the prompt byte for
   byte (the two golden pins' law re-asserted here beside them);
2. **the WR-4 negative** — a prompt carrying the reaction section
   shows zero letter-content vocabulary (the section teaches
   never-quote and the builder has no letter word to leak);
3. **the two-layer separation** — a prompt carrying both the
   director's chosen direction and the reading's fact: two sections,
   each its own, neither bleeding into the other;
4. **the seam** — ``run_generated_step`` passes the projection through
   (section present) and its default runs byte for byte as before
   (section absent);
5. **the E2E closed loop** (web stack, blocking face) — letter 1's
   reply writes the projection; letter 2's narrator prompt carries the
   reaction section, the stub answers a reaction beat with her
   ``participants``, the reaction event lands in the chronicle with
   that attribution, the key is consumed before the reply dials; the
   reply prompts' ``recent_world_events`` carry the reaction narration
   (the cognitive view's own filter — the loop's last link); every
   narrator prompt stays free of the letter's words;
6. **消费即清's quiet law** — a failed world step leaves the projection
   parked (the reply dial snapshots it still present), and the next
   landed step both carries and consumes it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import build_narrator_prompt
from elc.world.store import SqliteWorldStore
from tests.host.test_w1_web import REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import (
    BEATS_TWO,
    NARRATOR_MARK,
)
from tests.world.test_wr2_narrator import (
    _beat,
    _beats,
    _package,
    _ScriptedNarrator,
    _seed_world,
)

# ---------------------------------------------------------------------------
# shared material
# ---------------------------------------------------------------------------

#: The reaction section's own header (the prompt door's name).
REACTION_HEADER = "== She has read the letter =="

#: The single deterministic summary template (the web write face's
#: constant — spelled here so a template drift turns the pins red).
SUMMARY = "She has read the letter through."

#: The bound actor's persona id, as the builtin world's roster spells
#: it (the loader's derivation — the C1-c namespace).
NELL = "persona-nell-alder"

#: The letter's content, for the negative controls only. Its words must
#: appear in no narrator prompt, ever (WR-4).
LETTER_WORDS = ("Ada", "Thursday")
LETTER_TEXT = "Please tell the keeper Ada is coming on Thursday."

#: The reaction beat the E2E stub answers on letters 2 and 3: her
#: reaction as the world's own event, her id in ``participants`` — the
#: narrator's half of the bridge.
REACTION_NARRATION = (
    "Nell folded the letter away and walked to the harbour office"
    " to settle the mooring fees."
)
_REACTION_BEAT = {
    "kind": "letter-read",
    "narration": REACTION_NARRATION,
    "days": 1,
    "participants": [NELL],
}
BEATS_REACTION = json.dumps(
    {"beats": [_REACTION_BEAT], "stop": {"kind": "letter_arrives"}}
)


# ---------------------------------------------------------------------------
# 1 — the prompt contract (the conditional-section law)
# ---------------------------------------------------------------------------


def test_the_default_prompt_gains_nothing() -> None:
    """条件段定律：``letter_response`` 缺席（显式 ``None`` 或不传）⇒ 无
    反应区，且两种调用字节同一（两金针的法律，在本文件再证一次）。"""

    omitted = build_narrator_prompt(_package(), (), (), "zh")
    explicit = build_narrator_prompt(
        _package(), (), (), "zh", letter_response=None
    )
    assert omitted == explicit
    assert REACTION_HEADER not in omitted
    assert "She has read the letter" not in omitted


def test_the_reaction_section_rides_with_the_projection() -> None:
    """反应区钉：``letter_response`` 在场 ⇒ 反应区在场——persona id 与
    摘要句逐字、never-quote 教学句在场，且位置在 letter-on-its-way 区
    之后（信在路上 → 她读毕，两个事实各归其区）。"""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        letter_elapsed_days=2,
        letter_response=(NELL, SUMMARY),
    )
    assert REACTION_HEADER in prompt
    assert NELL in prompt
    assert SUMMARY in prompt
    assert "Never quote the letter and never refer to what it said" in prompt
    letter_header = "== A letter on its way =="
    assert prompt.index(letter_header) < prompt.index(REACTION_HEADER)
    assert prompt.index(REACTION_HEADER) < prompt.index("== Your task ==")


def test_the_bridge_refuses_blank_halves() -> None:
    """形守卫：persona id 或摘要句空 ⇒ ``ValueError``（prompt 面只透传
    不生成，但透传的东西必须成形）。"""

    for bad in (
        ("  ", SUMMARY),
        (NELL, ""),
        (NELL, "   "),
        (None, SUMMARY),  # type: ignore[list-item]
    ):
        with pytest.raises(ValueError):
            build_narrator_prompt(
                _package(), (), (), "zh", letter_response=bad  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# 2 — the WR-4 negative (the section carries a fact, never text)
# ---------------------------------------------------------------------------


def test_the_reaction_section_carries_no_letter_word() -> None:
    """WR-4 负钉：含反应区的 prompt 零信文词表——「Ada」「Thursday」
    不得出现；never-quote 教学句在场（世界侧半律明示）。"""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        letter_elapsed_days=1,
        letter_response=(NELL, SUMMARY),
    )
    for word in LETTER_WORDS:
        assert word not in prompt
    assert "Never quote the letter" in prompt


# ---------------------------------------------------------------------------
# 3 — the two-layer separation (two keys, two doors)
# ---------------------------------------------------------------------------


def test_direction_and_reaction_keep_their_own_sections() -> None:
    """双层律钉：同一步携走向选择 + 读毕事实 ⇒ 两区各在、互不串——走向
    区含 label/hint 而无摘要句，反应区含摘要句而无 label。"""

    label, hint = "the fair arrives", "Tents dot the cliff meadow."
    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        direction_mode="directed",
        pending_direction=(label, hint),
        letter_response=(NELL, SUMMARY),
    )
    assert "== The user's chosen direction ==" in prompt
    assert REACTION_HEADER in prompt
    chosen = prompt.split("== The user's chosen direction ==")[1].split(
        "=="
    )[0]
    reaction = prompt.split(REACTION_HEADER)[1].split("==")[0]
    assert label in chosen and hint in chosen
    assert SUMMARY not in chosen
    assert SUMMARY in reaction and NELL in reaction
    assert label not in reaction and hint not in reaction


# ---------------------------------------------------------------------------
# 4 — the seam (the pass-through, the zero-change default)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection (the wr2 fixture
    shape — spelled here because fixtures do not import)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def test_the_step_rides_the_projection_through(store: SqliteWorldStore) -> None:
    """协议面缝合钉：``run_generated_step(letter_response=...)`` 把投影
    送进叙事者 prompt（反应区在场）；默认 ``None`` ⇒ 无反应区（零变化
    默认，wr-10 姿势）。"""

    _seed_world(store)
    carrier = _ScriptedNarrator(ProviderOutput(text=_beats(_beat(days=1))))
    stepped = run_generated_step(
        store,
        "world-main",
        _package(),
        carrier,
        "turn-c15-1",
        "2026-10-09T12:00:00+00:00",
        letter_response=("persona-nell", SUMMARY),
    )
    assert isinstance(stepped, Ok)
    assert REACTION_HEADER in carrier.prompts[0]
    assert SUMMARY in carrier.prompts[0]

    bare = _ScriptedNarrator(ProviderOutput(text=_beats(_beat(days=1))))
    plain = run_generated_step(
        store,
        "world-main",
        _package(),
        bare,
        "turn-c15-2",
        "2026-10-09T12:00:00+00:00",
    )
    assert isinstance(plain, Ok)
    assert REACTION_HEADER not in bare.prompts[0]


# ---------------------------------------------------------------------------
# 5 — the E2E closed loop (the web stack, blocking face)
# ---------------------------------------------------------------------------


class _BridgeProvider:
    """The E2E's scripted double: narrator dials answer per-letter
    beats (the narrator dial count is the letter index), reply dials
    answer the plain reply. Every prompt is recorded, and each reply
    dial snapshots the projection row at that exact moment — the reply
    dial runs strictly after the world chain (WR-6's order), so the
    snapshot is the consumption window's only honest reading
    instrument (the worker thread's own seat, a fresh ro connection)."""

    def __init__(self, app_db: Path, *, fail_letter: int | None = None) -> None:
        self._app_db = app_db
        self._fail_letter = fail_letter
        self.prompts: list[str] = []
        self.narrator_dials = 0
        self.key_at_reply_dial: list[str | None] = []

    def _projection_row_now(self) -> str | None:
        world_row = sqlite3.connect(
            self._app_db.as_uri() + "?mode=ro", uri=True
        ).execute("SELECT world_id FROM world_conversation").fetchone()
        assert world_row is not None, "the stack bound no world"
        key = "world_letter_response:" + str(world_row[0])
        ro = sqlite3.connect(self._app_db.as_uri() + "?mode=ro", uri=True)
        try:
            row = ro.execute(
                "SELECT value FROM app_setting WHERE key = ?", (key,)
            ).fetchone()
        finally:
            ro.close()
        return None if row is None else str(row[0])

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        if NARRATOR_MARK in prompt.prompt_text:
            self.narrator_dials += 1
            if self.narrator_dials == self._fail_letter:
                return ProviderOutput(text=None, error="timeout")
            if self.narrator_dials == 1:
                return ProviderOutput(text=BEATS_TWO, error=None)
            return ProviderOutput(text=BEATS_REACTION, error=None)
        self.key_at_reply_dial.append(self._projection_row_now())
        return ProviderOutput(text=self._reply_text(), error=None)

    def _reply_text(self) -> str:
        return REPLY

    def narrator_prompts(self) -> list[str]:
        return [p for p in self.prompts if NARRATOR_MARK in p]

    def reply_prompts(self) -> list[str]:
        return [p for p in self.prompts if NARRATOR_MARK not in p]


def _projection_raw(app_db: Path) -> str | None:
    """The projection row, read through a fresh ro connection (the
    test thread's own seat)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        world_row = ro.execute(
            "SELECT world_id FROM world_conversation"
        ).fetchone()
        assert world_row is not None, "the stack bound no world"
        row = ro.execute(
            "SELECT value FROM app_setting WHERE key = ?",
            ("world_letter_response:" + str(world_row[0]),),
        ).fetchone()
        return None if row is None else str(row[0])
    finally:
        ro.close()


def _chronicle_participants(app_db: Path) -> list[tuple[str, str]]:
    """The chronicle's (narration, participants) pairs, oldest first."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        rows = ro.execute(
            "SELECT narration, participants FROM world_event"
            " ORDER BY occurred_at, event_id"
        ).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]
    finally:
        ro.close()


def test_the_letter_moves_her_world_across_three_letters(
    tmp_path: Path,
) -> None:
    """端到端闭环钉：信 1 回信生成 ⇒ 投影键写入（摘要句 = 固定模板、
    收信人 = 绑定 actor 经 world_actor 解析的 persona id）；信 2 世界步
    prompt 含反应区 ⇒ 桩答反应 beat（participants=[收信人]）⇒ 反应事件
    落编年史带归属 ⇒ 回信拨号时键已清（消费即清）；信 2/信 3 回信
    prompt 的 ``recent_world_events`` 含反应叙述（C1-c 认知视图——闭环
    最后一环）；全程叙事者 prompt 零信文。"""

    app_db = tmp_path / "app.db"
    provider = _BridgeProvider(app_db)
    with web_stack(app_db, provider=provider) as stack:
        # -- letter 1: the projection does not exist yet; the reply
        # writes it. The narrator prompt stays section-free.
        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert provider.narrator_dials == 1
        assert REACTION_HEADER not in provider.narrator_prompts()[0]
        raw = _projection_raw(app_db)
        assert raw is not None, "letter 1's reply wrote no projection"
        row = json.loads(raw)
        assert row["persona_id"] == NELL
        assert row["summary"] == SUMMARY
        assert provider.key_at_reply_dial[-1] is None, (
            "letter 1's reply dial runs before the write"
        )

        # -- letter 2: the world step carries the reaction section; the
        # stub answers her reaction beat; the chronicle lands it with
        # her attribution; the key is consumed before the reply dials.
        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert provider.narrator_dials == 2
        second_narrator = provider.narrator_prompts()[1]
        assert REACTION_HEADER in second_narrator
        assert NELL in second_narrator and SUMMARY in second_narrator
        chronicle = _chronicle_participants(app_db)
        reaction_rows = [
            (narration, participants)
            for narration, participants in chronicle
            if REACTION_NARRATION in narration
        ]
        assert reaction_rows, "the reaction beat never landed"
        reaction_participants = json.loads(reaction_rows[-1][1])
        assert reaction_participants == [NELL]
        assert provider.key_at_reply_dial[-1] is None, (
            "letter 2's world step consumed the projection before the"
            " reply dialed"
        )
        # The loop's last link: her cognitive view carried the reaction
        # into the reply prompt (the view resolves at reply time — the
        # reaction landed before it, WR-6's order).
        second_reply = provider.reply_prompts()[1]
        assert "[recent_world_events]" in second_reply
        assert REACTION_NARRATION in second_reply

        # -- letter 3: the projection was re-written by letter 2's
        # reply and carried again; her view still names the reaction.
        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert provider.narrator_dials == 3
        third_narrator = provider.narrator_prompts()[2]
        assert REACTION_HEADER in third_narrator
        third_reply = provider.reply_prompts()[2]
        assert REACTION_NARRATION in third_reply
        assert provider.key_at_reply_dial[-1] is None

        # WR-4, the whole chain's own negative: no letter word in any
        # narrator prompt, ever.
        for prompt in provider.narrator_prompts():
            for word in LETTER_WORDS:
                assert word not in prompt


# ---------------------------------------------------------------------------
# 6 — 消费即清's quiet law (拒收/安静不清)
# ---------------------------------------------------------------------------


def test_a_failed_world_step_leaves_the_projection_parked(
    tmp_path: Path,
) -> None:
    """消费即清钉（拒收臂）：信 1 落投影；信 2 世界步失败（narrator 答
    错）⇒ 链断、不清——回信拨号时投影仍在（若清了即 RED）；信 3 落地步
    既携带又消费（回信拨号时键已清）。"""

    app_db = tmp_path / "app.db"
    provider = _BridgeProvider(app_db, fail_letter=2)
    with web_stack(app_db, provider=provider) as stack:
        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert _projection_raw(app_db) is not None

        # Letter 2: the narrator refuses ("timeout") — the chain
        # breaks, nothing lands, the projection stays parked.
        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert provider.narrator_dials == 2
        assert provider.key_at_reply_dial[-1] is not None, (
            "a failed world step must not consume the projection"
        )
        parked = json.loads(provider.key_at_reply_dial[-1] or "{}")
        assert parked["persona_id"] == NELL
        assert parked["summary"] == SUMMARY

        # Letter 3: the landed step carries the surviving projection
        # and consumes it (the reply dial sees the row gone).
        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert provider.narrator_dials == 3
        assert REACTION_HEADER in provider.narrator_prompts()[2]
        assert provider.key_at_reply_dial[-1] is None, (
            "the landed step must consume the projection"
        )


# ---------------------------------------------------------------------------
# 7 — the projection is no director input (LOW-2's mode-blind law)
# ---------------------------------------------------------------------------


def test_the_projection_rides_in_directed_mode_too(tmp_path: Path) -> None:
    """模式不设门钉（评审 LOW-2 收口）：经真 settings 路由切 directed 后，
    信 1 回信照常写投影；信 2 世界步（directed 单步停点链）照常携反应区
    ——「信已读」是世界入站事实、非导演输入，不受 direction mode 门控。
    若有人给 ``_world_letter_response`` 的读加 mode 门，本钉即 RED。"""

    app_db = tmp_path / "app.db"
    provider = _BridgeProvider(app_db)
    with web_stack(app_db, provider=provider) as stack:
        status, mode_payload = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "directed"},
        )
        assert status == 200 and mode_payload["accepted"] is True

        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert _projection_raw(app_db) is not None, (
            "directed mode's reply writes the projection all the same"
        )

        status, _turn = stack.post("/api/turn", {"text": LETTER_TEXT})
        assert status == 200
        assert provider.narrator_dials == 2
        second_narrator = provider.narrator_prompts()[1]
        assert REACTION_HEADER in second_narrator, (
            "the world step carries the reading's fact in directed mode"
            " too — it is a world-inbound fact, never a director input"
        )
        assert NELL in second_narrator and SUMMARY in second_narrator
