"""MC-2 — the character editor knife's pins (角色编辑台).

The user's order (verbatim, the highest authority): when the user wants
to edit or create a character card, the page naturally zooms into the
editor page, and the user can freely DIY the character they want.

Seven groups (the slice's own):

1. **the zoom transition pins** — the editor opens from the envelope's
   own position (transform-origin rides custom props that only
   components.js may land), 260ms enter / 200ms collapse on the
   registered v2 curves, opacity never faster than transform, and
   reduced-motion cuts straight (JS guard + the library-wide block);
2. **the nine-face form pins** — the name (required, 40) plus eight
   prose faces (2000), each with one restrained human hint and an
   in-place counter; the four faces the server cannot read back carry
   the honest veil sentence;
3. **the real-CRUD wiring pins** — create POSTs, edit PUTs, the builtin
   is editable with no delete button, the user card's delete asks
   first; and live HTTP: the veiled faces left blank survive a save
   (an empty box never covers old prose), the builtin's identity line
   rewords and reads back;
4. **the 400 人话 pins** — the grammar refusals speak Chinese (INFO-3
   closed at the source), the old English sentences are gone, and the
   refusals still name the field and the cap over live HTTP;
5. **the opening-letter preview pin** — the opening face renders a
   live letter-paper sample beside the textarea;
6. **the return-to-stack pins** — a created card is born onto the stack
   (the one paper event), a saved card re-renders with its stamp
   exactly where it was (the stamp key is a pure function of the id);
7. **the design-language pins** — the editor's own CSS section carries
   zero new hex values, zero new kaiti faces, zero vermilion, zero new
   breakpoints; the textareas reuse the .pen family; the two zoom
   keyframes are the declared new registrations (their conservation
   price: the inline rename interaction retired in the same cut).
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tests.host.test_mc0_multi_character import FERRYMAN_FIELDS, NELL_ID
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _editor_css() -> str:
    """The editor's own section of screens.css — the slice between its
    header comment and the next section marker (the design-language
    pins read this slice, not the whole file). v3-2: the header renamed
    with the container recast (角色编辑面)."""

    css = _text("screens.css")
    start = css.index("── mc-2 角色编辑面")
    end = css.index("── v2 动效基建应用层")
    return css[start:end]


def _get_json(port: int, path: str) -> tuple[int, Any]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _put_json(
    port: int, path: str, payload: Any
) -> tuple[int, Any]:
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


def _delete_json(port: int, path: str) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method="DELETE"
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 1 — the container transition (v3-2: the editor lives in the pad)
# ---------------------------------------------------------------------------


def test_the_zoom_transition_pins() -> None:
    """① 容器延展过渡（v3-2 重铸——用户原话「直接起草编辑时，面板应当
    自动向下延伸拉开，是整个容器的变化，而不是多一个滚动条」）：入口
    改指容器编辑面（信封的「编辑」/空白封的「完整编辑」）；开台 =
    先装表单再 setEnvelopeFace("editor")——容器带着实际高度一次向下
    拉开（extendContainer，--panel-h custom prop，app.js 禁 .style 的
    规矩经 components.js 落点）；v2-2 的独立全页 char-editor 与
    editor-zoom 双 keyframes 同刀退役（负控防回潮）；三出口一致
    （P1-4）：Esc /「← 回沓」/「不改了」全部 setEnvelopeFace("deck")。
    删任一接线即红。"""

    app = _text("app.js")
    js = _text("components.js")
    css = _text("screens.css")

    # the entries — both doors name the editor from the deck
    assert (
        "onEdit: () =>\n"
        "        openCharacterEditor({ item: item, mode: \"edit\" }),"
    ) in app
    assert (
        "openCharacterEditor({ item: null, mode: \"create\" });"
    ) in app
    assert 'full.textContent = "完整编辑";' in app

    # the editor lives inside the pad container: no standalone panel is
    # appended to the document — the face opens in .envsel-editor and
    # the container extends downward (extendContainer measures AFTER
    # the form is in: one continuous pull, no two-step jump)
    assert "const body = envselPanel.querySelector(\".envsel-editor\");" \
        in app
    assert "setEnvelopeFace(\"editor\");" in app
    assert 'body.scrollTop = 0;' in app
    # the guard: the pad must be open, and the await window re-checks
    assert "if (!envselPanel) return;" in app
    assert 'if (!envselPanel || envselFace !== "deck") {' in app

    # the extend mechanics live in components.js (custom props only);
    # app.js is barred from .style
    assert "export function extendContainer(panel, mutate) {" in js
    assert 'panel.style.setProperty("--panel-h", from + "px");' in js
    assert 'panel.style.setProperty("--panel-h", to + "px");' in js
    assert '"--editor-ox"' not in js and "placeEditorOrigin" not in js
    assert "extendContainer(panel," in js
    css_grow = css[css.index(".envsel--grow {"):]
    css_grow = css_grow[: css_grow.index("}") + 1]
    assert "transition: height var(--dur-settle) var(--ease-paper);" \
        in css_grow
    assert "overflow: hidden;" in css_grow

    # the retired standalone form is gone at the root (negative —
    # restoring it turns this red)
    assert "char-editor" not in app
    assert "editor-zoom" not in css and "editor-zoom" not in app
    assert "placeEditorOrigin" not in app

    # the three exits speak with one voice (P1-4): Esc, 「← 回沓」and
    # 「不改了」 all land on the deck face — and the save/delete paths
    # ride the same closer with the re-stack in the callback
    assert "function closeCharacterEditor(after)" in app
    assert 'setEnvelopeFace("deck");' in app
    assert 'backBtn.textContent = "← 回沓";' in app
    assert 'cancel.textContent = "不改了";' in app
    # reduced-motion: the JS half cuts straight — reading the one
    # REDUCED_MOTION home in components.js (rd1 的「one listener, one
    # home」钉不许第二处 matchMedia 字面进 app.js), and the CSS half is
    # the library-wide block. v3-2 随迁：直切读面随容器化改形——fold 的
    # 复合守卫与回沓回调的直切臂（旧独立 if 块字面退役），消费面照在。
    assert "REDUCED_MOTION.matches" in app
    assert "REDUCED_MOTION," in app          # 经 components.js 导入
    assert "prefers-reduced-motion" not in app
    assert "export const REDUCED_MOTION = window.matchMedia(" in js
    block = _text("components.css")
    assert "@media (prefers-reduced-motion: reduce) {" in block
    assert "animation-duration: 0.01ms !important;" in block


# ---------------------------------------------------------------------------
# 2 — the nine-face form
# ---------------------------------------------------------------------------


def test_the_form_carries_nine_faces_with_hints_and_caps() -> None:
    """② 全字段表单：名字（必填，40）+ 八个散文面（各 2000）——键、
    标签、每面一句克制的人话说明、就地字数（maxLength 拦输入 + 计数
    给眼睛，与 F-2 同源）；读不回的四面带如实话注记（mc-0 无全字段读
    面——诚实边界，不拿空白盖旧文）。"""

    app = _text("app.js")
    keys = ("identity", "personality", "background", "speech_style",
            "values", "boundaries", "opening", "scenario")
    for key in keys:
        assert '{ key: "' + key + '", label:' in app
    for label in ("身份行", "性情", "背景", "写信习惯", "看重的事",
                  "边界", "开场信", "场景"):
        assert 'label: "' + label + '"' in app
    # one restrained human hint per face (spot-hold the whole set)
    for hint in (
        "信封面上示人的第一句——她一句话介绍自己。",
        "她是个什么样的人，怎么与人相处。",
        "她走过的路，过着的日子。",
        "她的信长什么样——长短、口气、落笔的规矩。",
        "她放在心里、不肯换出去的东西。",
        "她不做的事，不接的话题。",
        "刚开始通信时，她寄来的第一封。",
        "她写信的地方，提笔的那一刻。",
    ):
        assert hint in app
    # the caps ride the same numbers as F-2 and the server
    assert "caps = { name: 40, prose: 2000 };" in app
    assert "nameInput.maxLength = caps.name;" in app
    assert "pen.maxLength = caps.prose;" in app
    assert "editorCapLine(nameInput, caps.name)" in app
    assert "editorCapLine(pen, caps.prose)" in app
    # the required name refuses in place, before any byte hits the wire
    assert "一张卡得有名字——空白的信封寄不出去。" in app
    # the honest veil on the four unreadable faces
    assert "旧文这里读不回——留空原样留着，写下就盖上。" in app
    assert 'if (raw.trim()) fields[face.key] = raw;   // 写下才盖上' in app


# ---------------------------------------------------------------------------
# 3 — the real CRUD (wiring + live)
# ---------------------------------------------------------------------------


def test_the_editor_saves_through_the_real_crud() -> None:
    """③ 接线半：新建走 POST（非空面才送），编辑走 PUT（可读五面照
    抄 + 写过字的读不回面才送）；内置卡可编辑（mc-0 契约：编辑不拒
    删除才拒——九面全可写，card_store 勘察在册）且无删除钮、带「可以
    改不能删」的注记；用户卡的删除先过 confirmDialog；读不回就不开笔
    （卡面读取失败 = 错误 + 重试，永不拿空白表单开台）。"""

    app = _text("app.js")
    assert "data = await fetchCreateCharacter(fields);" in app
    assert (
        "data = await fetchUpdateCharacter(item.character_id, fields);"
        in app
    )
    # the builtin: a note, an editable form, and no delete button
    assert 'note.textContent = "这是随信来的第一位笔友——她可以改，不能删。";' in app
    assert "if (item && !item.is_builtin) {" in app
    assert 'del.textContent = "删了这封";' in app
    # fr-B 随迁：confirmDialog 异步化（自绘纸墨确认窗）——await 形态
    assert (
        "if (!(await confirmDialog(\n"
        '          "删了这封，沓里就再没有这位笔友——已写过的信留在信档里。"\n'
        '          + "这一步收不回来。"))) {'
    ) in app
    # the never-open-blank guard: a failed card read refuses to open
    assert "data = await fetchPartnerOf(item.character_id);" in app
    assert "这张卡的旧文没读到——读不回就不开笔，免得拿空白盖了旧文。" in app
    # the known server-404 literal maps to a Chinese line in the editor
    # (LOW-5 disposition: the mapping sentence itself is pinned)
    assert "没找到这张卡——它可能刚被删掉，回沓看看。" in app


def test_the_crud_is_live_and_the_veiled_faces_survive(
    tmp_path: Path,
) -> None:
    """③ 活体半：九面建卡 → 编辑保存（只送六面：可读五面 + 写了字的
    开场信）→ 直接读表核对——没送的三面原样未动（空白盖旧文的事在
    存储层不可能发生）；内置卡身份行改得动、读得回；用户卡删得掉、
    内置卡删除 409。"""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post(
            "/api/characters", dict(FERRYMAN_FIELDS))
        assert status == 200, payload
        card_id = payload["character"]["character_id"]

        # the editor's edit-save shape: the five readable faces plus
        # exactly one overwritten veiled face
        status, payload = _put_json(
            stack.port,
            f"/api/characters/{card_id}",
            {
                "name": "老周",
                "identity": FERRYMAN_FIELDS["identity"],
                "background": FERRYMAN_FIELDS["background"],
                "speech_style": FERRYMAN_FIELDS["speech_style"],
                "values": FERRYMAN_FIELDS["values"],
                "opening": "新写的开场信——第一句从这里起。",
            },
        )
        assert status == 200, payload
        assert payload["character"]["name"] == "老周"

        conn = sqlite3.connect(
            f"file:{tmp_path / 'app.db'}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT name, identity, personality, background,"
                ' speech_style, "values", boundaries, opening, scenario'
                " FROM character_card WHERE character_id = ?",
                (card_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == "老周"
        assert row[1] == FERRYMAN_FIELDS["identity"]
        # the three veiled faces the form did not send survive verbatim
        assert row[2] == FERRYMAN_FIELDS["personality"]
        assert row[3] == FERRYMAN_FIELDS["background"]
        assert row[4] == FERRYMAN_FIELDS["speech_style"]
        assert row[5] == FERRYMAN_FIELDS["values"]
        assert row[6] == FERRYMAN_FIELDS["boundaries"]
        assert row[7] == "新写的开场信——第一句从这里起。"
        assert row[8] == FERRYMAN_FIELDS["scenario"]

        # the builtin is editable (mc-0's ruling) and reads back reworded
        status, payload = _put_json(
            stack.port,
            f"/api/characters/{NELL_ID}",
            {"identity": "改过的身份行——还是她。"},
        )
        assert status == 200, payload
        status, payload = _get_json(
            stack.port, f"/api/partner?character_id={NELL_ID}")
        assert status == 200, payload
        assert payload["card"]["identity_line"] == "改过的身份行——还是她。"

        # the user card deletes; the builtin's delete is refused
        status, payload = _delete_json(
            stack.port, f"/api/characters/{card_id}")
        assert status == 200, payload
        assert payload["deleted"] == card_id
        status, payload = _get_json(stack.port, "/api/characters")
        assert card_id not in [
            c["character_id"] for c in payload["characters"]]
        status, payload = _delete_json(
            stack.port, f"/api/characters/{NELL_ID}")
        assert status == 409, payload


# ---------------------------------------------------------------------------
# 4 — the 400 人话 (Chinese at the source)
# ---------------------------------------------------------------------------


def test_the_400_sentences_are_chinese(tmp_path: Path) -> None:
    """④ 400 人话中文化（INFO-3 在源头收口）：六句文法拒绝全中文，
    点名字段与上限数字仍在；旧英文句在 web.py 缺位；活体仍按字段与
    上限拒绝（超长 / 未知面 / 缺名字 / 非文字）。"""

    web = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    for phrase in (
        "请求体得是 JSON 对象：带",
        "没有叫 {key!r} 的卡面——能写的面是：",
        "「{key}」得是一段文字",
        "「{key}」太长了——最多 {cap} 字",
        "一张卡得有名字——名字不能是空白",
        '新建一张卡得带 \\"name\\"——名字不能是空白',
    ):
        assert phrase in web, phrase
    for gone in (
        "is too long",
        "needs a string",
        "unknown character field",
        "needs a non-empty name",
        'need a JSON object with {"name"',
        "a character card needs a non-empty name",
    ):
        assert gone not in web, gone

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post(
            "/api/characters", {"name": "n" * 41})
        assert status == 400, payload
        assert "「name」太长了——最多 40 字" in payload["error"]

        status, payload = stack.post(
            "/api/characters", {"name": "钟表匠", "motto": "x"})
        assert status == 400, payload
        assert "没有叫 'motto' 的卡面" in payload["error"]

        status, payload = stack.post(
            "/api/characters", {"identity": "没名字的一张"})
        assert status == 400, payload
        assert "新建一张卡得带 \"name\"——名字不能是空白" in payload["error"]

        status, payload = stack.post(
            "/api/characters", {"name": 3})
        assert status == 400, payload
        assert "「name」得是一段文字" in payload["error"]


# ---------------------------------------------------------------------------
# 5 — the opening-letter preview
# ---------------------------------------------------------------------------


def test_the_opening_letter_has_a_live_preview() -> None:
    """⑤ 开场信预览：opening 面旁一纸短笺（paper-2 + 发丝缘）作信件
    语体的样例渲染，随输入即刷；空态一句诚实指路，不伪装已有信。"""

    app = _text("app.js")
    assert 'prevLabel.textContent = "信的样子";' in app
    assert 'prevPaper.className = "editor-openprev-paper";' in app
    assert "pen.addEventListener(\"input\", syncPreview);" in app
    assert "prevPaper.textContent = text" in app
    # LOW-1 disposition: the empty state must not deny the card's old
    # letter (the builtin's opening is non-empty — the veil just cannot
    # read it back); the sentence speaks of the unreadable old letter
    assert "旧信这里读不回——写上几句，这里就是新信的样子。" in app
    assert "开场信还没写" not in app
    css = _editor_css()
    assert ".editor-openprev-paper { margin: var(--sp-1) 0 0;" in css
    assert "background: var(--paper-2);" in css
    # INFO-1 disposition: the value itself is pinned (the count pin
    # never locked it) — the preview paper is a ≤2px letter object
    assert "border-radius: 2px;" in css


# ---------------------------------------------------------------------------
# 6 — the return to the stack
# ---------------------------------------------------------------------------


def test_the_save_returns_to_the_stack() -> None:
    """⑥ 成功回沓：新建落 envselBornId（沓重排时 born 类恰一次纸事
    件）；编辑保存后沓重排（名更新、邮票与姿态不动——stamp_key 系于
    id 的纯函数，重建路径未被触碰）；回沓重排在收拢落定之后才跑
    （born 动画要等台撤了才播得见）。"""

    app = _text("app.js")
    assert (
        "envselBornId = data.character.character_id;"
        "   // 新封落沓的纸事件" in app
    )
    assert (
        "await refreshEnvelopeStack();"
        "   // 沓重排：名更新、邮票与姿态不动" in app
    )
    assert (
        'if (item.character_id === envselBornId) env.classList.add('
        '"env--born");' in app
    )
    # the stamp still derives from the server's id-keyed stamp_key
    assert (
        "stampClasses: stampVariantClasses(item.stamp_key).join(\" \"),"
        in app
    )
    # the re-stack runs after the collapse settles (the close callback)
    assert (
        "closeCharacterEditor(async () => {\n"
        "        await refreshEnvelopeStack();"
        "   // 新封落沓（最尾，纸事件一次）\n"
        "      });" in app
    )


# ---------------------------------------------------------------------------
# 7 — the design language
# ---------------------------------------------------------------------------


def test_the_editor_speaks_the_v2_language() -> None:
    """⑦ 设计语言：编辑台自己的 CSS 段零新色值（无 hex 字面）、零新
    楷体位（--f-hand 缺席）、零朱砂（--seal 缺席）、零新断点（@media
    缺席——版心 = --measure 四档通用）；散文面复用 .pen 家族；分级靠
    发丝线与微标签（rd-1 配方）；文字一律 textContent（用户散文绝不
    进标记）。"""

    css = _editor_css()
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None
    assert "--f-hand" not in css
    assert "--seal" not in css
    assert "@media" not in css
    # hairline layering + the rd-1 micro-label recipe + the measure
    assert "border-top: 1px solid var(--rule-soft);" in css
    assert "font: var(--meta-font);" in css
    assert "letter-spacing: var(--meta-track);" in css
    assert "max-width: var(--measure);" in css
    # the pen family is the prose input, whole (source pin)
    app = _text("app.js")
    assert 'pen.className = "pen editor-pen";' in app
    # the user's prose stays inert text, never markup
    assert "prevPaper.textContent = text" in app
    assert "pen.value = editorCardValue(card, face.key);" in app
