"""DS-1 — the immersion face's serving pins (``elc.ds_web``; the
technical definition §11–§12).

Pinned here (the V3-8e reader-suite family's shapes; the serving stack
over a stub host, the scripted completion offline):

1. the state derivation over the durable rows — the honest empty face
   before the world exists, the seeded world's draft flag, the
   controls/next face after the plan;
2. the graded bible edit (§6 F3) — a textual edit lands ONE revision
   at once (the fourteen fields as given), a structural edit parks on
   ``ds_pending_bible`` and lands folded into ONE revision at the next
   chapter plan;
3. the route grammars (fail-closed): the reply body and the bible body
   400 shapes;
4. the stop-note seat: a drive's reasoned stop persists and the state
   reads it back; the light-model word rides the state;
5. the engine's harness authorization is load-bearing through the face:
   a bible edit is the director seat's tool (the registry knows).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from elc.ds_web import (
    DS_LIGHT_MODEL_KEY,
    DS_PENDING_BIBLE_KEY,
    DualSeatWebFace,
    ds_bible_request,
    ds_state_ro,
    ds_turn_request,
)
from elc.platform.db.app_settings import AppSettingStore
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.world.ds_opening import DS_WORLD_ID
from elc.world.llm_providers import CompletionOutcome
from elc.world.store import SqliteWorldStore

NOW = "2026-10-14T00:00:00+00:00"

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"

SITUATION_PLAN: dict[str, Any] = {
    "where_you_stand": (
        "the ferry house steps at lantern light, the town's question"
        " hanging on you"
    ),
    "place": "the ferry house steps",
    "what_presses_on_you": (
        "the county clerk arrives at dawn and the mark must have an"
        " answer — yours"
    ),
    "first_speaker": "bryn",
    "first_words": "The clerk comes at dawn. Was it there when you"
        " crossed?",
    "open_question": "will your answer keep you out of the water gate",
    "world_event_candidates": [
        "the fog closes the crossing before dawn",
    ],
    "protagonist_goals": {
        "bryn": "keep the ledger clean through the dawn",
        "corvin": "keep the water's secret one more night",
    },
    "pacing": "the pressure tightens with every hour of fog",
    "settlement_expectation": "where the mark's answer has left you",
}


class ScriptedCompletion:
    """The offline seam: canned answers by prompt family."""

    def __init__(self, **queues: list[str]) -> None:
        self._queues = {kind: list(items) for kind, items in queues.items()}
        self.prompts: dict[str, list[str]] = {}

    def complete(self, prompt: str) -> CompletionOutcome:
        if "situation planner of a two-seat" in prompt:
            kind = "situation"
        elif "world director" in prompt:
            kind = "director"
        elif "dispatcher of a two-seat" in prompt:
            kind = "dispatch"
        elif "private seat" in prompt:
            kind = "character"
        elif "narrator of a two-seat" in prompt:
            kind = "narrator"
        elif "resolver of a two-seat" in prompt:
            kind = "adjudicate"
        else:
            raise AssertionError("unknown prompt family")
        self.prompts.setdefault(kind, []).append(prompt)
        queue = self._queues.get(kind)
        if not queue:
            raise AssertionError(f"the {kind} script is exhausted")
        return CompletionOutcome(text=queue.pop(0), error=None)

    def count(self, kind: str) -> int:
        return len(self.prompts.get(kind, []))


def _situation_payload() -> str:
    return json.dumps(SITUATION_PLAN, ensure_ascii=False)


def _dispatch_payload() -> str:
    return json.dumps(
        {
            "reading": "the painter answers",
            "responders": ["bryn"],
            "world_event": None,
            "pacing": "hold",
            "options": ["Ask", "Wait"],
        },
        ensure_ascii=False,
    )


def _proposal_payload() -> str:
    return json.dumps(
        {"speech": "s", "action": "a", "intent": "i", "private_thought": "p"},
        ensure_ascii=False,
    )


def _narration_payload() -> str:
    return (
        "You answer her steadily.\n---\n"
        + json.dumps(
            {
                "addresses_you": False,
                "impends_on_you": False,
                "beat_complete": True,
            }
        )
    )


def _adjudication_payload() -> str:
    return json.dumps(
        {
            "interpretation": "i",
            "outcome": "o",
            "actual_action": "a",
            "consequences": "c",
            "state_effects": [],
            "participants": ["chenyu", "bryn"],
            "replan_scope": "NONE",
        },
        ensure_ascii=False,
    )


@pytest.fixture()
def env(
    tmp_path: Path,
) -> tuple[sqlite3.Connection, DualSeatWebFace, ScriptedCompletion]:
    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    fence = open_runtime_epoch(db)
    host = SimpleNamespace(
        db=db,
        fence=fence,
        world_store=SqliteWorldStore(db, fence),
        app_settings=AppSettingStore(db, fence),
        # a provider-SHAPED stand-in for the preflight only — the actual
        # model calls ride the injected scripted completion below (the
        # face reads the seam per drive; the live object is never dialed
        # in this suite).
        coordinator=SimpleNamespace(
            persona_provider=lambda: SimpleNamespace(
                config=SimpleNamespace(base_url="http://local", model="stub")
            )
        ),
    )
    completion = ScriptedCompletion(
        situation=[_situation_payload()] * 3,
        dispatch=[_dispatch_payload()] * 3,
        character=[_proposal_payload()] * 6,
        narrator=[_narration_payload()] * 6,
        adjudicate=[_adjudication_payload()] * 3,
    )
    face = DualSeatWebFace(
        host, clock=lambda: NOW,  # type: ignore[arg-type]
    )
    face._completion = completion  # the offline seam (the face reads it per drive)
    face._light_completion = completion
    return db, face, completion


def test_the_state_face_answers_the_honest_empty_shape(
    env: tuple,
) -> None:
    db, face, _completion = env
    payload = face.state()
    assert payload["ok"] is True
    assert payload["world"]["exists"] is False
    assert payload["next"]["kind"] == "start"
    assert payload["controls"] == {"can_start": True}
    assert payload["draft"] is True


def test_start_seeds_and_plans_then_the_face_opens(
    env: tuple,
) -> None:
    db, face, completion = env
    landed = face.start()
    assert landed["ok"] is True, landed["error"]
    payload = landed
    assert payload["world"]["exists"] is True
    assert payload["chapter"]["status"] == "PLANNED"
    # the situation plan's read face carries the four questions (DS-3
    # §6) — not the blueprint's literary columns
    assert (
        payload["plan"]["what_presses_on_you"]
        == SITUATION_PLAN["what_presses_on_you"]
    )
    assert payload["plan"]["first_speaker"] == "bryn"
    assert payload["plan"]["open_question"] == (
        SITUATION_PLAN["open_question"]
    )
    assert "dramatic_question" not in payload["plan"]
    # the blueprint machine was never asked (the retired test face)
    assert completion.count("situation") == 1
    assert "situation" in completion.prompts
    prompt = completion.prompts["situation"][0]
    assert '"first_words"' in prompt
    assert "NO literary structure" in prompt
    assert payload["controls"].get("can_open") is True
    # the user's own ruling (DS-3): seeding the world plants the prose
    # word zh — the SHARED v3_prose_language key (the language button
    # keeps its switch; the V3 reading face reads the same key)
    assert db.execute(
        "SELECT value FROM app_setting WHERE key = 'v3_prose_language'"
    ).fetchone()[0] == "zh"
    # the opening beat drives through the face (the scripted completion).
    # Under the DS-3 rhythm law the scripted narrations (beat_complete,
    # never a marker) drive on — the pure guardrail stops the drive at
    # three beats, each a full world beat (dispatch + characters +
    # adjudication + narration).
    run = face.drive_beat("open", _queue())
    assert run["ok"] is True, run["error"]
    assert run["did"]["segments_written"] == 3
    assert run["did"]["stopped_on"] == "beat_ceiling"
    after = face.state()
    assert after["chapter"]["status"] == "ACTIVE"  # the first landing activated
    assert len(after["passages"]) == 3
    assert after["controls"].get("can_reply") is True


def _queue() -> "object":
    import queue as _queue_module

    return _queue_module.Queue()


def test_start_recasts_a_crashed_plan(env: tuple) -> None:
    """2026-10-15 real-model smoke's catch: a start that crashed mid-
    plan (the chapter row landed, the plan never did) made every later
    start a permanent no-op — the page stuck at 「no drivable scene」
    forever. The guard now asks the ADOPTED plan, and the situation
    machine's residue law reuses the crashed chapter and re-casts."""

    db, face, completion = env
    assert face.start()["ok"] is True
    # the crash window: roll the adopted plan back (the chapter row and
    # its scene anchor stay — exactly the crashed-open shape)
    db.execute(
        "DELETE FROM world_scene WHERE chapter_id = ("
        " SELECT chapter_id FROM world_chapter ORDER BY chapter_index"
        " DESC LIMIT 1)"
    )
    db.execute(
        "DELETE FROM world_chapter_plan"
        " WHERE chapter_id = (SELECT chapter_id FROM world_chapter"
        " ORDER BY chapter_index DESC LIMIT 1)"
    )
    db.commit()
    # the re-start must RE-CAST (not answer the empty no-op)
    landed = face.start()
    assert landed["ok"] is True, landed["error"]
    assert completion.count("situation") == 2
    assert landed["plan"] is not None
    assert landed["plan"]["what_presses_on_you"]


def test_the_graded_bible_edit_lands_now_and_parks_next(
    env: tuple,
) -> None:
    db, face, _completion = env
    face.start()
    # a textual edit lands ONE revision at once
    landed = face.bible_edit("tone", "colder, wetter, closer to the bone", "now")
    assert landed["ok"] is True, landed["error"]
    row = db.execute(
        "SELECT COUNT(*) FROM world_bible_revision WHERE world_id = ?",
        (DS_WORLD_ID,),
    ).fetchone()
    assert row[0] == 2  # the seed revision + this one
    current = db.execute(
        "SELECT tone FROM world_bible_revision"
        " WHERE world_id = ? AND status = 'CURRENT'",
        (DS_WORLD_ID,),
    ).fetchone()
    assert current[0] == "colder, wetter, closer to the bone"
    # the untouched fields rode as given (the fourteen-fields law)
    premise = db.execute(
        "SELECT premise FROM world_bible_revision"
        " WHERE world_id = ? AND status = 'CURRENT'",
        (DS_WORLD_ID,),
    ).fetchone()
    assert "灰隼要塞" in premise[0]
    # a structural edit parks
    landed = face.bible_edit("geography", "the bridge is washed out", "next")
    assert landed["ok"] is True
    pending_row = db.execute(
        "SELECT value FROM app_setting WHERE key = ?", (DS_PENDING_BIBLE_KEY,)
    ).fetchone()
    assert pending_row is not None
    assert "washed out" in pending_row[0]
    state = face.state()
    assert any(
        entry["field"] == "geography" for entry in state["pending_bible"]
    )


def test_the_stop_note_persists_and_the_state_reads_it(
    env: tuple,
) -> None:
    db, face, _completion = env
    face.start()
    face.drive_beat("open", _queue())
    state = face.state()
    # the scripted narrations never offer a natural stop, so the drive
    # runs to the pure guardrail (the DS-3 节奏律): the reasoned stop
    # line rode, the last beat's own verdict is beat_complete
    assert state["stop"] is not None
    assert state["stop"]["stopped_on"] == "beat_ceiling"
    assert state["stop"]["last"]["reason"] == "beat_complete"
    assert "3 拍" in state["stop"]["note"]
    # and the light-model word rides the state after a save
    face.set_light_model("deepseek-chat")
    state = face.state()
    assert state["light_model"] == "deepseek-chat"
    assert db.execute(
        "SELECT value FROM app_setting WHERE key = ?",
        (DS_LIGHT_MODEL_KEY,),
    ).fetchone()[0] == "deepseek-chat"


def test_the_route_grammars_are_fail_closed() -> None:
    error, parsed = ds_turn_request({"text": "hello"})
    assert error is None and parsed is not None
    error, _parsed = ds_turn_request({"text": "   "})
    assert error is not None
    error, _parsed = ds_turn_request({"text": "hi", "extra": 1})
    assert error is not None
    error, parsed = ds_turn_request(
        {"text": "hi", "submission_id": "web-1"}
    )
    assert error is None and parsed["submission_id"] == "web-1"

    error, parsed = ds_bible_request(
        {"field": "tone", "value": "x", "mode": "next"}
    )
    assert error is None and parsed is not None
    error, _parsed = ds_bible_request(
        {"field": "nope", "value": "x", "mode": "next"}
    )
    assert error is not None
    error, _parsed = ds_bible_request(
        {"field": "tone", "value": "x", "mode": "later"}
    )
    assert error is not None


def test_the_ro_poll_reads_the_same_derivation(
    env: tuple, tmp_path: Path
) -> None:
    db, face, _completion = env
    face.start()
    # the face's connection holds the world; the ro poll opens its own
    app_db = db.execute(
        "PRAGMA database_list"
    ).fetchall()
    path = app_db[0][2]
    payload = ds_state_ro(path)
    assert payload["ok"] is True
    assert payload["world"]["exists"] is True
    assert payload["chapter"]["status"] == "PLANNED"


def test_the_served_script_wires_the_opening_button() -> None:
    """dualseat.js: the opening card is wired — the state says
    ``can_open`` / ``kind: "opening"`` and the page renders the 开篇
    button through ``streamDrive(API.open, …)``. 2026-10-14 lesson:
    ``API.open`` existed in the route table but nothing on the page
    ever called it, so a freshly seeded world showed no content and no
    way forward (the user sat on an empty reading face). The card
    hangs off the ``opening`` stop kind (the other stop kinds must not
    grow it)."""

    script = (WEBUI / "dualseat.js").read_text(encoding="utf-8")
    assert "can_open" in script
    assert "streamDrive(API.open" in script
    # DS-2 随迁：开篇卡判断挪进 render 的貌签守卫块（建卡/收卡由貌签
    # 承担），条件字面同义改写（payload.next 容空取 kind + controlsNow）。
    assert (
        '(payload.next || {}).kind === "opening"'
        " || controlsNow.can_open" in script
    )
    assert "开篇（世界落第一笔）" in script
    # the card is rebuilt inside render (after renderFlow clears the
    # flow), not appended once at boot — the poll would wipe it.
    assert "renderOpenCard" in script


def test_the_start_route_carries_the_drive_wait_budget() -> None:
    """web.py: the ``/api/ds/start`` route's ``_run_host_write`` passes
    ``wait=_V3_DRIVE_WAIT_SECONDS`` (the settle / next_chapter
    posture). 2026-10-14 lesson: seeding the world plus the real-model
    plan chain-measures ~90s while the house budget is 60s — the route
    answered 500 mid-plan; the chain tests drove the face directly and
    never crossed HTTP, so the routing wait budget was never exercised
    by a test. A revert to the default wait re-reds this pin."""

    source = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    head = source.index('"/api/ds/start"')
    tail = source.index('"/api/ds/settle"', head)
    block = source[head:tail]
    assert "_run_host_write(" in block
    assert "wait=_V3_DRIVE_WAIT_SECONDS" in block


def test_the_poll_tick_rests_while_busy() -> None:
    """dualseat.js: the ``startPolling`` tick carries a ``busy`` guard
    before ``render`` — during a streaming/blocking drive the SSE
    frames (and the final render) own the UI, so the poll rests a beat
    and realigns only when idle. 2026-10-14 lesson: 流式期间轮询重绘会
    打掉在流段落；busy 守卫缺失属前端生命周期缺口，三连热修之三。The
    served script is sliced by ``function startPolling`` first —
    ``renderChips``/``beginBusy`` also mention ``busy`` and a bare
    substring check could mismatch. Reverting the guard re-reds this
    pin."""

    script = (WEBUI / "dualseat.js").read_text(encoding="utf-8")
    head = script.index("function startPolling")
    tail = script.index("function stopPolling", head)
    block = script[head:tail]
    assert "if (busy) return;" in block


def test_the_flow_rerender_is_fingerprint_gated() -> None:
    """dualseat.js（DS-2 面 1）——正文面的重绘受貌签门把守：``render``
    先铸 ``flowFingerprint``（世界、草稿旗、章、计划之问、已落段落、
    幕外摘要、下一步形态、开篇许可），貌签与上一拍同貌就整块跳过
    ``renderFlow``/开始卡/开篇卡/章末面的 DOM 重建。2026-10-15 教训：
    轮询拍每 3 秒全量清空重建正文区（``inner.textContent = ""``），
    用户亲验为「画面文字一直在闪烁」——呈现律（技术定义 §12）的拍间
    形态。齿在两处：①清空行所在函数只从貌签变化的分支可达（结构偏序
    钉）；②貌签输入覆盖钉——四类态变迁（种世界/开篇/新段落落/章末）
    各自由至少一项输入变化驱动，删任何一项输入即钉红。把貌签比较改
    恒等（模拟回退为无貌检查）同样转红。"""

    script = (WEBUI / "dualseat.js").read_text(encoding="utf-8")
    # ① 貌签函数覆盖全部正文面输入。
    fp_head = script.index("function flowFingerprint")
    fp_tail = script.index("function renderFlow", fp_head)
    fingerprint = script[fp_head:fp_tail]
    assert "world.exists === true" in fingerprint
    assert "payload.draft === true" in fingerprint
    assert "chapter.chapter_index" in fingerprint
    assert "chapter.status" in fingerprint
    assert "dramatic_question" in fingerprint
    assert "passage.passage_id" in fingerprint
    assert "passage.body" in fingerprint
    assert "settlement.summary" in fingerprint
    assert "(payload.next || {}).kind" in fingerprint
    assert "can_open === true" in fingerprint
    # ② render 里清空路径只从貌签守卫可达：renderFlow/两卡/收尾全部
    # 挂在 ``if (fingerprint !== lastFlowFingerprint)`` 块内。
    head = script.index("function render(payload")
    tail = script.index("\nfunction renderLang", head)
    block = script[head:tail]
    guard_at = block.index("if (fingerprint !== lastFlowFingerprint) {")
    for call in (
        "sealParagraph()",
        "renderFlow(payload)",
        "renderStartCard(payload)",
        "renderOpenCard()",
    ):
        assert block.index(call, guard_at) > guard_at
    # ③ renderFlow 仍是正文区唯一的全量清空处（貌签门的就是它）。
    flow_head = script.index("function renderFlow")
    flow_tail = script.index("function zhIndex", flow_head)
    assert 'inner.textContent = "";' in script[flow_head:flow_tail]


def test_the_settings_edit_survives_the_poll_tick() -> None:
    """dualseat.js（DS-2 面 1 次生同根）——设定面板编辑中（
    ``editBibleRow`` 打开的 ``.ds-sedit`` textarea 在场）轮询拍不得全
    量重建设定面板；保存成功路径自行退出编辑态（随后的状态重绘恢复
    接管），失败路径不动编辑行（话不丢）。2026-10-15 教训：``render``
    每拍调 ``renderSettings`` 全量 ``body.textContent = ""`` 重建——
    正在编辑的设定文本每 3 秒被轮询抹掉。删守卫行（或把保存成功路径
    的退出编辑态拆掉）即钉红。"""

    script = (WEBUI / "dualseat.js").read_text(encoding="utf-8")
    head = script.index("function render(payload")
    tail = script.index("\nfunction renderLang", head)
    block = script[head:tail]
    guard_at = block.index('querySelector(".ds-sedit")')
    assert block.index("renderSettings(payload)", guard_at) > guard_at
    eb_head = script.index("function editBibleRow")
    eb_tail = script.index("async function postJSON", eb_head)
    handler = script[eb_head:eb_tail]
    ok_at = handler.index("if (payload && payload.ok) {")
    between = handler[ok_at:handler.index("const fresh", ok_at)]
    assert "renderSettings(lastPayload)" in between


def test_the_render_error_branch_sticks_the_faultline() -> None:
    """钉 C（DS-2 面 2，热修 4 遗稿吸收）—— dualseat.js 的 ``render``
    错误分支在状态行之外点亮红条（``setFault(payload.error)``），且除
    ``beginBusy`` 外无人可再把红条藏起。2026-10-14 教训：开篇拍遇真实
    模型抖动，SSE final 答 ``ok:false``，``render`` 只把句子写进状态
    行——三秒后的下一个轮询拍用 ``next.detail``（「轮到你了……」）把
    它覆盖，用户看到空页面、无任何报错；彼时 ``setFault`` 全文件零调
    用方。粘住律一并钉死：``setFault`` 自身空文分支之外，全文件直接
    藏红条处恰一处（``beginBusy`` 的起手清）——轮询 render 永远不清
    它。拔掉 ``setFault`` 调用（或长出第二处直接藏红条）即钉红。"""

    script = (WEBUI / "dualseat.js").read_text(encoding="utf-8")
    head = script.index("function render(payload")
    tail = script.index("function renderSettings", head)
    block = script[head:tail]
    assert "setStatus(payload.error)" in block
    assert "setFault(payload.error)" in block
    # 粘住律：恰一处直接藏红条——beginBusy 的。
    assert script.count('el("ds-faultline").hidden = true') == 1


def test_the_ds_language_face_reads_and_writes_the_shared_word() -> None:
    """钉 D（DS-2 面 2，热修 4 遗稿吸收）——DS 沉浸面的语言位：
    ``web.py`` 有 ``/api/ds/language`` 路由（V3-8g 同一文法
    ``v3_language_request``、同一写面 ``set_language``——共享
    ``v3_prose_language`` key），页面（dualseat.js）接了这同一通道，
    且 ``ds_web.py`` 的空态不再携带硬编码 ``"language": "en"`` 字面
    （无腿/读失败两形状在铺开处以 ``PROSE_LANGUAGE_DEFAULT`` 作答；
    真实推导一律以 ``prose_language_of`` 活读覆盖）。2026-10-14 教训：
    空态答 ``en`` 而驱动活读共享 key——页面语言对钮对着一条假读数高
    亮；且 /ds 页面根本没有语言切换钮（bible 中文、正文英文——V3-8g
    的旧痛重现）。拔路由、退回硬编码、或拆掉页面通道任一即钉红。"""

    web_source = (REPO / "src" / "elc" / "web.py").read_text(
        encoding="utf-8"
    )
    assert '"/api/ds/language"' in web_source
    page = (WEBUI / "dualseat.js").read_text(encoding="utf-8")
    assert '"/api/ds/language"' in page
    ds_source = (REPO / "src" / "elc" / "ds_web.py").read_text(
        encoding="utf-8"
    )
    assert '"language": "en"' not in ds_source
