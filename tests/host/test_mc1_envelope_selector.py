"""MC-1 — the envelope selector knife's pins (信封沓).

The user's order (verbatim, the highest authority): put the current
character's name on the desk masthead, and on click open a stack of
envelopes — one per character, each with its name, a one-line
introduction, its own stamp design, a precise preview animation, and
the current correspondence postmarked 「当前」.

Eight groups (the slice's own):

1. **masthead truth pins** — the desk's ``.who``/``.who-sub`` read the
   roster's current character over ``/api/characters`` (zero character
   name literals anywhere in the webui; the brand name and tagline
   retreat to the vestibule cover); the browser title stays the brand;
2. **the stack's presence pins** — every envelope carries the three
   faces (addressee name / one-line introduction / its own stamp), the
   action row (对话 · 档案 · 编辑), the current postmark, and the blank
   envelope at the tail (「写给一位新笔友」);
3. **stamp determinism pins** — the variant classes derive purely from
   the server's ``stamp_key`` (8 motifs × 4 inks × 3 papers, all v2
   palette); the same key always lands the same classes;
4. **preview animation pins** — the settle transition (260ms paper
   curve, stagger 20ms capped at 60ms, total ≤320ms), the lift's
   underlay-opacity shadow (shadows never animate), the reused
   registered keyframes only, and zero standing loops;
5. **switch wiring pins** — 对话 posts the switch, the masthead and the
   letter flow reload locally (one paper event), the teaching poll
   follows the conversation by itself;
6. **the three mc-0 review obligations** — F-1: two minted cards
   coexist with distinct ids (live HTTP); F-2: the card fields' length
   caps (name 40 / prose 2000) refuse with a 400 人话 (live HTTP); F-3:
   switching with an open teaching moment asks one sentence and is
   never hard-blocked;
7. **the narrow-screen form pins** — the base form is the phone form
   (near-vertical mini pile, ≤3 visible, scroll to leaf through, the
   fan factor at 0.35, hit areas ≥32px); the four-tier boundary
   contract gains no new edge;
8. **the migration manifest** — the truths that replaced the retired
   masthead pins (empty endpoint-driven slots, the cover tagline, the
   selector wiring), restated here so the manifest has a mechanical
   home.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from elc.persona.card_store import stamp_key_for
from elc.web import _CHARACTER_NAME_MAX, _CHARACTER_PROSE_MAX
from tests.host.test_mc0_multi_character import FERRYMAN_FIELDS, NELL_ID
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"

#: The seven shell files (the whole face a source pin may speak about).
SHELL_FILES = (
    "index.html",
    "tokens.css",
    "components.css",
    "screens.css",
    "api.js",
    "components.js",
    "app.js",
)


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _get_json(port: int, path: str) -> tuple[int, Any]:
    """A GET that decodes error answers too (the roster's shapes)."""

    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _put_json(port: int, path: str, payload: Any) -> tuple[int, Any]:
    """The reword face — PUT with a JSON body, errors decoded."""

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 1 — the masthead reads the roster, never a literal


def test_the_masthead_reads_the_roster_not_literals() -> None:
    """案头主从条的真源钉：.who = 当前角色名一行（v2-2 瘦身，8.2.2①：
    who-sub 身份行长句族退役——身份介绍退入笔友档案全页，缺位钉防
    回潮）——renderMasthead 只从 /api/characters 的 current 取（删驱动
    线即红）；webui 七文件零角色名字面（Nell 保持零出现）；无 JS 兜底
    = 空槽（不发明人名）；品牌名与副题退居门厅封面；页面 title 保持
    品牌（mc-1 自裁披露：不拼角色名——避免每封信重排标签页标题）。"""

    index = _text("index.html")
    assert '<div class="who"></div>' in index
    assert 'who-sub' not in index
    assert '<p class="ob-tagline">见字如晤，今日如何</p>' in index
    assert "<title>展信佳</title>" in index
    app = _text("app.js")
    assert "function renderMasthead(roster)" in app
    assert 'who.textContent = current ? current.name : "";' in app
    # the sub slot is gone with the v2-2 slim-down (the editor's own
    # editor-sub line in mc-2 shares the receiver name — pin the exact
    # masthead spelling, not the bare receiver)
    assert (
        'sub.textContent = current ? current.identity_line : "";'
        not in app
    )
    assert (
        "const current = items.find(\n"
        "    (item) => item.character_id ==="
        " (roster && roster.current_character_id));" in app
    )
    # the drivers: the first fill at startup, and the refresh after a
    # switch — deleted either way goes red
    assert "fetchCharacters().then(renderMasthead)" in app
    assert "renderMasthead(await fetchCharacters());" in app
    # the browser title keeps the brand alone (no per-character churn)
    assert "document.title = BRAND.name;" in app
    # zero character-name literals across the whole served face
    for name in SHELL_FILES:
        body = _text(name)
        assert "Nell" not in body, name
        assert "Nell Alder" not in body, name


def test_the_masthead_data_face_is_live(tmp_path: Path) -> None:
    """主从条读的那份数据，活体对表：/api/characters 的
    current_character_id 随 switch 前移、每行带 name/identity_line/
    stamp_key——renderMasthead 的三件输入端点全给。"""

    with web_stack(tmp_path / "app.db") as stack:
        status, roster = _get_json(stack.port, "/api/characters")
        assert status == 200, roster
        assert roster["current_character_id"] is None
        nell = roster["characters"][0]
        assert nell["character_id"] == NELL_ID
        assert nell["name"]
        assert "identity_line" in nell
        assert nell["stamp_key"] == stamp_key_for(NELL_ID)

        status, payload = stack.post("/api/characters", FERRYMAN_FIELDS)
        assert status == 200, payload
        ferryman_id = payload["character"]["character_id"]
        status, payload = stack.post(
            "/api/characters/switch", {"character_id": ferryman_id}
        )
        assert status == 200, payload
        status, roster = _get_json(stack.port, "/api/characters")
        assert roster["current_character_id"] == ferryman_id
        row = next(item for item in roster["characters"]
                   if item["character_id"] == ferryman_id)
        assert row["name"] == FERRYMAN_FIELDS["name"]
        assert row["identity_line"] == FERRYMAN_FIELDS["identity"]


# ---------------------------------------------------------------------------
# 2 — the stack: three faces per envelope + the blank at the tail


def test_every_envelope_carries_its_three_faces_and_the_actions() -> None:
    """信封沓在场钉（components.js 工厂 + app.js 装配）：每封三要素
    ——收件人位（致 + 角色名）/ 一行简介 / 右上角专属邮票；动作行
    三词（对话 · 档案 · 编辑，--pencil 形）；当前通信的一封带
    .env--current 与「当前」邮戳角标；沓尾新建空白信封（写给一位
    新笔友 + 起笔入口 + 诚实留白句）。一切文字 textContent。"""

    js = _text("components.js")
    assert "export function envelopeCard(item, opts)" in js
    assert (
        'env.className = "env" + (options.current ? " env--current" : "");'
        in js
    )
    assert 'toWord.textContent = "致";' in js
    assert 'name.className = "env-name";' in js
    assert 'line.className = "env-line";' in js
    assert (
        'stamp.className = ("env-stamp "'
        ' + (options.stampClasses || "")).trim();' in js
    )
    assert 'initial.textContent = String(item.name || "").charAt(0);' in js
    assert 'act("对话", "env-act-talk"' in js
    assert 'act("档案", "env-act-dossier"' in js
    assert 'act("编辑", "env-act-edit"' in js
    assert 'link.className = "btn btn--pencil " + cls;' in js
    assert 'mark.className = "env-mark";' in js
    assert 'word.textContent = "当前";' in js
    # the user's own prose stays inert text, never markup
    assert 'name.textContent = String(item.name || "");' in js
    assert 'line.textContent = String(item.identity_line || "");' in js

    app = _text("app.js")
    assert "async function renderEnvelopeStack(stack)" in app
    assert "roster = await fetchCharacters();" in app
    assert "stampClasses: stampVariantClasses(item.stamp_key).join(\" \")," in app
    assert "stack.appendChild(newEnvelopeCard());" in app
    assert 'name.textContent = "写给一位新笔友";' in app
    assert 'start.textContent = "起笔";' in app
    # mc-2 起真值随迁：编辑台已开——空白封两条路（起笔最简 / 完整
    # 编辑全字段），诚实留白的「等编辑台」句退役。
    assert (
        "起个名字就能开笔；性情、背景这些面想一次写全，点「完整编辑」。"
        in app
    )
    assert 'full.textContent = "完整编辑";' in app
    # the stack opens from the roster and the current drives the postmark
    assert "const isCurrent = item.character_id === roster.current_character_id;" in app
    assert "current: isCurrent," in app


def test_the_stack_data_face_is_live(tmp_path: Path) -> None:
    """沓面数据的活体：创建（名字 + 一句简介——空白封的最简一形）→
    名册带上它（内置在前）；该行的 stamp_key 是 id 的纯函数。"""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post(
            "/api/characters",
            {"name": "摆渡人", "identity": "清晨还在补网的退休摆渡人"},
        )
        assert status == 200, payload
        card = payload["character"]
        status, roster = _get_json(stack.port, "/api/characters")
        assert [item["character_id"] for item in roster["characters"]] == [
            NELL_ID,
            card["character_id"],
        ]
        assert roster["characters"][1]["stamp_key"] == stamp_key_for(
            card["character_id"])


# ---------------------------------------------------------------------------
# 3 — the stamp variants derive deterministically from the stamp_key


def test_stamp_variant_classes_derive_from_the_stamp_key() -> None:
    """邮票确定性钉：变体类是 stamp_key 的纯函数（同 key 恒同类——
    跨进程跨重启；异 key 可异）；三轴离散梯——图形 8（% 8）× 墨色 4
    （% 4）× 票面 3（% 3），微扇姿态取另外几位（rotate ±1..3° /
    translateX ±6..18px）；零随机零素材，纯 class 派发；CSS 侧变体
    全员在场（components.css 的 .env-stamp 段）。"""

    app = _text("app.js")
    assert "function stampVariantClasses(stampKey)" in app
    assert '"stamp-v" + (at(0) % 8),' in app
    assert '"stamp-c" + (at(1) % 4),' in app
    assert '"stamp-p" + (at(2) % 3),' in app
    # the fan pose is the same family of pure derivations
    assert "function envelopeTilt(stampKey)" in app
    assert "function envelopeDrift(stampKey)" in app
    assert "const size = (parseInt(key.charAt(3), 16) || 0) % 3;" in app
    assert "const size = (parseInt(key.charAt(4), 16) || 0) % 3;" in app
    assert "return flip * (1 + size) + \"deg\";" in app
    assert "return flip * (6 + size * 6) + \"px\";" in app
    # every envelope's classes come from that one function
    assert "stampClasses: stampVariantClasses(item.stamp_key).join(\" \")," in app

    css = _text("components.css")
    for variant in ("stamp-v0", "stamp-v1", "stamp-v2", "stamp-v3",
                    "stamp-v4", "stamp-v5", "stamp-v6", "stamp-v7"):
        assert f".{variant}::after" in css, variant
    for ink in ("stamp-c0", "stamp-c1", "stamp-c2", "stamp-c3"):
        assert f".{ink} {{ color: var(--" in css, ink
    for paper in ("stamp-p0", "stamp-p1", "stamp-p2"):
        assert f".{paper} {{ background: var(--" in css, paper
    # the palette stays in the v2 families (no new literals): the ink
    # axis resolves through var() only
    assert ".stamp-c0 { color: var(--ink); }" in css
    assert ".stamp-c1 { color: var(--accent); }" in css
    assert ".stamp-c2 { color: var(--accent-deep); }" in css
    assert ".stamp-c3 { color: var(--ink-soft); }" in css


def test_the_same_stamp_key_yields_the_same_classes(tmp_path: Path) -> None:
    """同 key 同变体类的服务端半区（活体）：两次读名册，同一角色的
    stamp_key 逐字符相等（前端类派生的输入因此稳定）。"""

    with web_stack(tmp_path / "app.db") as stack:
        _, first = _get_json(stack.port, "/api/characters")
        _, second = _get_json(stack.port, "/api/characters")
        keys_a = {item["character_id"]: item["stamp_key"]
                  for item in first["characters"]}
        keys_b = {item["character_id"]: item["stamp_key"]
                  for item in second["characters"]}
        assert keys_a == keys_b
        assert keys_a[NELL_ID] == stamp_key_for(NELL_ID)


# ---------------------------------------------------------------------------
# 4 — the preview animation: precise, finite, reduced-motion safe


def test_the_preview_animation_is_pinned_to_the_v2_motion_law() -> None:
    """预览切换动效钉（简报 §5）：落位 = transform 260ms 减速长尾
    （--dur-note × --ease-paper）+ 让位 stagger（步长 20ms、封顶
    60ms——260 + 60 = 总封顶 320ms）；微抬 = translateY(-4px) +
    垫纸层 opacity 半档（阴影不做动画——动的是垫纸透明度）；选择器
    入场与案头重落复用注册双动画（paper-drop + ink-wash，零新
    keyframes）；零 infinite（本刀零常驻循环的本地再钉）。"""

    screens = _text("screens.css")
    assert (
        "transition: transform var(--dur-note) var(--ease-paper)\n"
        "                   var(--env-delay, 0ms); }" in screens
    )
    assert (
        ".env--lift { transform: translateY(-4px)" in screens
    )
    components = _text("components.css")
    assert (
        "transform: translate(3px, 3px); opacity: 0;\n"
        "              transition: opacity var(--dur-micro)"
        " var(--ease-press); }" in components
    )
    assert ".env--lift::after { opacity: 1; }" in components
    # the desk's resettle reuses the registered pair; the panel's
    # entrance was re-sequenced by v2-2 (8.2.2a 弹窗整体优化)：面板是
    # 大件——入场 320 大件档 × --ease-paper 减速长尾（原 --ease-enter
    # 稳出档让位），退场 = paper-fold 收拢 200 × --ease-exit + ink-wash
    # reverse 恒慢（起笔向下展开的「沓收拢」半）。page-turn 两枚新
    # keyframes 是 ⑨-5 的落库行（spec 9.5 表）——沓翻页与横滑共用。
    assert (
        ".envsel--open { animation: paper-drop var(--dur-settle)"
        " var(--ease-paper) both," in screens
    )
    assert (
        ".envsel--fold { animation: paper-fold var(--dur-panel-out)"
        " var(--ease-exit)" in screens
    )
    assert (
        "animation: paper-drop var(--dur-note) var(--ease-enter) both,\n"
        "             ink-wash calc(var(--dur-note) * 1.3)"
        " var(--ease-enter) both; }" in screens
    )
    for name in ("tokens.css", "components.css", "screens.css"):
        assert "infinite" not in _text(name), name
    # the stagger arithmetic lives in one place (the layout half)
    js = _text("components.js")
    assert (
        "const delay = Math.min(Math.abs(before - position) * 20, 60);"
        in js
    )


# ---------------------------------------------------------------------------
# 5 — the switch: the talk action posts, the desk refreshes locally


def test_the_talk_action_wires_the_switch_and_the_local_refresh() -> None:
    """切换接线钉：点「对话」→ POST /api/characters/switch（api.js 的
    fetchSwitchCharacter 是唯一消费形）；成功 = 局部刷新——主从条重读
    名册、信流清空重载该角色窗口、批注面随 loadHistory 重建、案头纸
    事件恰一次（flow-resettle 落类前先摘）；api.js 的端点字面全在。"""

    api = _text("api.js")
    assert 'postJson("/api/characters/switch", { character_id: characterId });' in api
    assert 'return getJson("/api/characters");' in api
    assert (
        'return getJson("/api/partner?character_id="\n'
        "                 + encodeURIComponent(characterId));" in api
    )
    app = _text("app.js")
    assert "data = await fetchSwitchCharacter(characterId);" in app
    assert (
        "async function refreshCorrespondence()" in app
    )
    assert "renderMasthead(await fetchCharacters());" in app
    assert 'messages.textContent = "";' in app
    assert "showMoments([]);" in app
    assert "await loadHistory();" in app
    assert 'flow.classList.remove("flow-resettle");' in app
    assert 'flow.classList.add("flow-resettle");' in app
    # the talk arm and the second-click arm both land in the switch —
    # v2-2 随迁（8.2.2a 起笔向下展开）：切换确认后 unfoldToParlor
    # （沓收拢与信流首屏同帧，fold 退场），不再直摘
    assert (
        "switchToCharacter(item.character_id).then((done) => {\n"
        "          if (done) unfoldToParlor();\n"
        "        });" in app
    )
    assert (
        "if (envselPreviewId === characterId) {\n"
        "    // 再点同一封 = 就是他——切换 + 起笔向下展开\n"
        "    // （8.2.2a：选中角色后沓收拢、信纸向下铺开成对话主界面）\n"
        "    switchToCharacter(characterId).then((done) => {\n"
        "      if (done) unfoldToParlor();\n"
        "    });\n"
        "    return;\n"
        "  }" in app
    )
    # the dossier arm goes through the parameterized face
    assert "openPartnerDossier(item.character_id);" in app


# ---------------------------------------------------------------------------
# 6 — the three mc-0 review obligations


def test_f1_two_minted_cards_coexist_with_distinct_ids(
    tmp_path: Path,
) -> None:
    """F-1（mc-0 评审义务，HTTP 活体）：mint 两张用户卡——id 互异、
    两卡同册共存（内置在前），各自的面（identity_line/stamp_key）
    齐全；重读两次结果一致。"""

    with web_stack(tmp_path / "app.db") as stack:
        status, first = stack.post(
            "/api/characters",
            {"name": "摆渡人", "identity": "清晨补网的退休摆渡人"},
        )
        assert status == 200, first
        status, second = stack.post(
            "/api/characters",
            {"name": "钟表匠", "identity": "巷尾修钟的沉默钟表匠"},
        )
        assert status == 200, second
        one = first["character"]["character_id"]
        two = second["character"]["character_id"]
        assert one != two
        assert one.startswith("card-") and two.startswith("card-")
        status, roster = _get_json(stack.port, "/api/characters")
        assert status == 200, roster
        ids = [item["character_id"] for item in roster["characters"]]
        # the roster order: builtin first, then the user's cards by id —
        # both minted cards coexist on one roster
        assert ids[0] == NELL_ID
        assert set(ids[1:]) == {one, two}
        assert len(ids) == 3
        faces = {item["character_id"]: item for item in roster["characters"]}
        assert faces[one]["identity_line"] == "清晨补网的退休摆渡人"
        assert faces[two]["identity_line"] == "巷尾修钟的沉默钟表匠"
        _, again = _get_json(stack.port, "/api/characters")
        assert [item["character_id"] for item in again["characters"]] == ids


def test_f2_the_card_field_caps_refuse_with_a_human_sentence(
    tmp_path: Path,
) -> None:
    """F-2（mc-0 评审义务）：卡字段长度上限——name ≤40、各散文面
    ≤2000；超限 = 400 人话（点名字段与上限数字），不静默截断；边界
    值（恰 40 / 恰 2000）收下。"""

    assert _CHARACTER_NAME_MAX == 40
    assert _CHARACTER_PROSE_MAX == 2000
    web = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    assert "_CHARACTER_NAME_MAX = 40" in web
    assert "_CHARACTER_PROSE_MAX = 2000" in web
    assert (
        "cap = (\n"
        "            _CHARACTER_NAME_MAX if key == \"name\""
        " else _CHARACTER_PROSE_MAX\n"
        "        )" in web
    )
    # mc-2 起：400 人话中文化（INFO-3 收口）——点名字段与上限数字仍在。
    assert 'f"「{key}」太长了——最多 {cap} 字",' in web

    long_name = "n" * (_CHARACTER_NAME_MAX + 1)
    long_prose = "p" * (_CHARACTER_PROSE_MAX + 1)
    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post(
            "/api/characters", {"name": long_name, "identity": "x"})
        assert status == 400, payload
        assert "「name」太长了——最多 40 字" in payload["error"]

        status, payload = stack.post(
            "/api/characters", {"name": "钟表匠", "identity": long_prose})
        assert status == 400, payload
        assert "「identity」太长了——最多 2000 字" in (
            payload["error"])

        # the boundary values land (create, then reword at both caps)
        status, payload = stack.post(
            "/api/characters",
            {"name": "n" * _CHARACTER_NAME_MAX,
             "identity": "p" * _CHARACTER_PROSE_MAX},
        )
        assert status == 200, payload
        card_id = payload["character"]["character_id"]
        status, payload = _put_json(
            stack.port,
            f"/api/characters/{card_id}",
            {"background": "q" * _CHARACTER_PROSE_MAX},
        )
        assert status == 200, payload


def test_f3_switching_with_an_open_moment_asks_and_never_blocks() -> None:
    """F-3（mc-0 评审义务，前端处置钉）：切换前读 /api/teaching/
    current——批注开着（AWAITING_USER）给确认一句话（不硬禁：确认后
    照切）；句面逐字在册；确认发生在 switch 之前。"""

    app = _text("app.js")
    assert "async function switchToCharacter(characterId)" in app
    assert (
        "try {\n"
        "    moment = (await fetchCurrentMoment()).moment;\n"
        "  } catch {\n"
        "    moment = null;\n"
        "  }" in app
    )
    assert (
        'if (moment && moment.lifecycle_state === "AWAITING_USER") {'
        in app
    )
    assert (
        'if (!confirmDialog("那边的批注还等着回应——切过去它会先搁着。")) {'
        in app
    )
    # the gate sits before the switch, and accepting falls through to it
    gate = app.index("confirmDialog(\"那边的批注还等着回应")
    posted = app.index("fetchSwitchCharacter(characterId);")
    assert gate < posted
    # a refusal of the dialog aborts (return false), never silently switches
    assert (
        "    if (!confirmDialog(\"那边的批注还等着回应——切过去它会先搁着。\")) {\n"
        "      return false;\n"
        "    }" in app
    )


# ---------------------------------------------------------------------------
# 7 — the narrow screen: the base form is the phone form


def test_the_base_form_is_the_phone_form_and_the_tiers_gain_no_edge() -> None:
    """移动端形态钉：基础形态即窄屏形态（近垂直小叠——fan 因子 0.35、
    可见 ≤3 封、沓内滚动翻检）；命中带——整封可点 + 动作行 6px 上下
    padding（ui 档行高 20px + 12px = 32px 级，吸取单词卡审计教训）；
    四档断点契约零新增边界（三个 min-width 各恰一次、无 max-width
    查询、--shell-w 改写仍恰三处）；481 档内只放大沓步与幅面。"""

    screens = _text("screens.css")
    assert "--env-fan: 0.35; --env-step: 46px; --env-body: 104px;" in screens
    assert (
        "max-height: calc(var(--env-body) + 2 * var(--env-step));" in screens
    )
    assert "overflow-y: auto; overscroll-behavior: contain;" in screens
    assert ".env { position: absolute;" in screens
    assert "left: var(--sp-5); right: var(--sp-5);" in screens
    assert "min-height: var(--env-body);" in screens
    # the four-tier contract stands untouched (mc-1 adds no boundary)
    for boundary in ("481px", "900px", "1280px"):
        assert screens.count(f"@media (min-width: {boundary}) {{") == 1
    assert "max-width: 480px" not in screens
    assert screens.count("--shell-w:") == 3
    tablet = screens[screens.index("@media (min-width: 481px) {"):]
    tablet = tablet[:tablet.index("@media (min-width: 900px) {")]
    assert "--env-fan: 1; --env-step: 56px; --env-body: 116px;" in tablet
    assert "max-height: none;" in tablet
    # hit areas: the whole envelope is the preview target and the action
    # row links carry their own padding (20px line + 12px = 32px tier)
    components = _text("components.css")
    assert ".env-actions .btn { padding: 6px 2px; }" in components


# ---------------------------------------------------------------------------
# 8 — the migration manifest, mechanically restated


def test_the_migration_manifest_restates_the_new_truths() -> None:
    """随迁清单的机械落点（w8/rd/r1 系点名集的新真值在此再钉一遍）
    ①案头主从条：四处旧「展信佳/副题」兜底钉 → 空槽（f1r/fg2/
    r1_shell/rd4 的随迁钉各自在场，此处收拢）；②触发面：who 块点击
    → 信封沓（openEnvelopeSelector），档案改由每封「档案」动作参数化
    进入；③封面收留品牌（题字 + 副题）；④圆角/纸影计数钉的新豁免族
    （f1r/p1/r1v/rd1 的随迁值）在本清单口径下自洽。"""

    index = _text("index.html")
    assert '<div class="who"></div>' in index
    # v2-2 随迁（8.2.2①）：who-sub 身份行长句族退役（身份介绍退入
    # 笔友档案全页）——缺位钉防回潮
    assert 'who-sub' not in index
    assert "<h1>展信佳</h1>" in index
    assert '<p class="ob-tagline">见字如晤，今日如何</p>' in index
    app = _text("app.js")
    assert 'whoBlock.setAttribute("aria-label", "信封沓——挑一位笔友");' in app
    assert (
        "    openEnvelopeSelector();\n"
        "  });" in app
    )
    # the parameterized dossier replaced the bare-only entry
    assert "async function openPartnerDossier(characterId)" in app
    assert (
        "data = characterId\n"
        "      ? await fetchPartnerOf(characterId)\n"
        "      : await fetchPartner();" in app
    )
    # the counting pins' new exemptions, in one place: 2px seats in
    # screens (.envsel/.env，mc-2 起加编辑台的开场信预览短笺——同 ≤2px
    # 信纸物件档, v2-2 起加翻页全览页卡 .envpage——同档), stamp & postmark
    # geometry + the three baseline seats (circle, postmark pair) in
    # components; the soft shadows: note/deckle/en-route/stack 四座 +
    # 空白封的 none 抵消臂在 components（v2-2 增词卡遮罩无影——计数
    # 不变），screens 的 box-shadow 自 v2-2 起四座（案头舞台 deep +
    # 写信区垫板 soft 向上 8.2.2② + 翻页页卡 soft 承托 + 信档缩略封
    # soft——全部两级令牌之内、零手写字面）
    screens = _text("screens.css")
    components = _text("components.css")
    assert screens.count("border-radius") == 4
    # .envsel + .env + 预览短笺 + .envpage (2px)
    assert components.count("border-radius") == 7   # 基线3 + 邮戳双圈2 + 邮票图形2
    assert components.count("box-shadow: var(--stack-shadow-soft);") == 4
    assert screens.count("box-shadow") == 4         # 舞台 deep + 垫板/页卡/缩略封 soft
    # the mc-1 face styles live outside the component registry (the
    # dossier precedent): no numbered contract block, no clause words
    assert "mc-1 信封选择器的交互态与工艺件" in components


# ---------------------------------------------------------------------------
# 9 — the disposition cut (mc-1 评审 2M+3L 的必修面)


def test_the_preview_settle_reaches_the_front_and_others_give_way() -> None:
    """MEDIUM-1（评审活体实锤的算法缺陷）：沓首 = 全沓严格最小
    order − 1——旧 falsy 判别（!lowest，0 是合法 order）会在循环里
    被后续非零覆盖，预览封不滑到沓首、让位与 stagger 整体不发生。
    修复形态正钉 + 旧形态缺位钉（把修复还原即红）；让位重排与 z 序
    （预览封 z 最高 = count − 0）的源在场；多封连点臂（再点即切换）
    与沓首本封臂（已在通信中——收沓）随钉。行为复证由活体承担
    （settled 后 picked --env-i == "0"、其余封存在 --env-delay
    ≠ "0ms"——处置回执附 DOM 读数）。"""

    app = _text("app.js")
    js = _text("components.js")
    # the fix: a neutral Infinity seed with a pure < comparison
    assert "let lowest = Infinity;" in app
    assert "if (order < lowest) lowest = order;" in app
    # the retired falsy form is gone — restoring it turns this red
    assert "let lowest = 0;" not in app
    assert "if (!lowest || order < lowest)" not in app
    # the picked envelope takes the strict-minimum seat in front
    assert "picked.dataset.order = String(lowest - 1);" in app
    # the give-way arithmetic feeds --env-delay (the others move too)
    assert (
        "const delay = Math.min(Math.abs(before - position) * 20, 60);"
        in js
    )
    # the front seat rides the top z (count − position 0 = count)
    assert 'env.style.setProperty("--env-z", String(count - position));' in js
    # the two arms: a second click on the previewed envelope switches
    # (v2-2: 起笔向下展开——unfoldToParlor); talking to the current one
    # folds the selector into the parlor the same way
    assert (
        "if (envselPreviewId === characterId) {\n"
        "    // 再点同一封 = 就是他——切换 + 起笔向下展开\n"
        "    // （8.2.2a：选中角色后沓收拢、信纸向下铺开成对话主界面）\n"
        "    switchToCharacter(characterId).then((done) => {\n"
        "      if (done) unfoldToParlor();\n"
        "    });\n"
        "    return;\n"
        "  }" in app
    )
    assert (
        "if (isCurrent) {\n"
        "          unfoldToParlor();   // 已在通信中——沓收拢、信纸摊开（8.2.2a）\n"
        "          return;\n"
        "        }" in app
    )


def test_the_current_postmark_never_clips_and_the_live_fixes_hold() -> None:
    """LOW-1：沓内左右 --sp-5（24px）横向出血缓冲 ≥ 微扇 dx ±18 +
    ±3° 旋转角 ≈3.6 + 「当前」邮戳 −9——overflow-x:hidden 的裁切线
    不碰信封与邮戳（8a1b5dd 只修了竖向 12px 基准，此为横向半区）。
    LOW-2：8a1b5dd 的两活体修在此有源钉——空白封 z 落底（压不住任何
    真封）+ 沓首 12px 基准（.env/.env--new/stack height 三处）。还原
    任一处即红。"""

    screens = _text("screens.css")
    # LOW-1: the horizontal bleed budget, as a rule (not a comment)
    assert "left: var(--sp-5); right: var(--sp-5);" in screens
    assert ".env { position: absolute; left: 0;" not in screens
    # LOW-2a: the blank envelope sinks below every real envelope
    assert (
        ".env--new { top: calc(12px + var(--env-n, 1) * var(--env-step));\n"
        "            z-index: 0;" in screens
    )
    # LOW-2b: the 12px head seat in all three places (the postmark's
    # −9px top bleed lands inside the scroll box)
    assert (
        "top: calc(12px + var(--env-i, 0) * var(--env-step));" in screens
    )
    assert (
        "top: calc(12px + var(--env-n, 1) * var(--env-step));" in screens
    )
    assert (
        "height: calc(12px + var(--env-body)\n"
        "                             + var(--env-n, 1)"
        " * var(--env-step));" in screens
    )


def test_the_selector_esc_rename_and_z_order_wiring_is_pinned() -> None:
    """LOW-3 三交互语义源钉：①z 序（沓首最高，layoutEnvelopeStack 的
    排名公式）；②Esc 收沓（接线 + 摘除对——开关对称；v3-2 重铸：
    Esc 逐层退栈——浮层在场让路（wordCardOpen 裁决），编辑面/全览
    窗口退一层回扇叠，扇叠才收沓；v2-2 的 setEnvelopeBrowser 分支
    随容器态机退役）；③编辑台保存成功后
    refreshEnvelopeStack（沓重排：名更新、邮票与姿态不动）。删任一
    接线即红。"""

    app = _text("app.js")
    js = _text("components.js")
    # ① the visual order is the rank order (preview = rank 0 = top z)
    assert 'env.style.setProperty("--env-i", String(position));' in js
    assert 'env.style.setProperty("--env-z", String(count - position));' in js
    # ② Esc folds the selector; the listener leaves with it. v3-2 随迁：
    # Esc 是⑩层级宪法的逐层退栈——浮层先退（wordCardOpen 让路），
    # 编辑面/全览窗口各退一层回扇叠，扇叠一记收沓（层层退，不一步跳
    # 关）；v2-2 的 charEditorPanel 让路分支与 setEnvelopeBrowser 分支
    # 随容器态机（envselFace）退役——负控防回潮。
    assert (
        'function envselEsc(event) {\n'
        '  if (event.key !== "Escape") return;\n'
        "  if (wordCardOpen()) return;"
        "   // 浮层先退（它的监听收它自己）\n"
        '  if (envselFace === "editor" || envselFace === "window") {\n'
        '    setEnvelopeFace("deck");\n'
        "    return;\n"
        "  }\n"
        "  closeEnvelopeSelector();\n"
        "}" in app
    )
    assert "if (charEditorPanel) return;" not in app
    assert "setEnvelopeBrowser" not in app
    assert 'document.addEventListener("keydown", envselEsc);' in app
    assert 'document.removeEventListener("keydown", envselEsc);' in app
    # ③ a saved edit re-renders the stack (name moves, stamp stays) —
    # the comment now lives in the mc-2 editor's save path
    assert (
        "await refreshEnvelopeStack();"
        "   // 沓重排：名更新、邮票与姿态不动" in app
    )
