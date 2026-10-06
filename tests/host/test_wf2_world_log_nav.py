"""WF-2 — the world log as a first-class navdock space.

The ruling (DEC-OPI-5fc42174-…5 R4, verbatim intent): the world's log
becomes a first-level navigation item — a fourth dock button (案头 /
世界 / 温故 / 抽屉; the dock ≤5 red line holds, four is compliant), a
dedicated ``#space-world`` screen where the revealed chronicle is read
by story day, and the wf-1 today-line debt is paid: the line now clicks
into the world screen. The log screen is a **history reader, not a
letter** — the DEC-…92 sentence stands untouched: the letter stream's
inline story block remains the only with-letter form, and this screen
coexists beside it (zero changes to that renderer).

The screen's four faces, all endpoint-assembled (zero world-name
literals — the wf-1 precedent): the identity head (``overview``), the
grouped log (``/api/world/log``, the server's newest-first order used
as-is), the quiet-day arm (empty log + overview quiet ⇒ one chrome
sentence), and the honest empty state (no binding ⇒ the 404 error shape
⇒ 「这个世界还没有开始」— the screen stays reachable, invents nothing,
crashes on nothing).

Fourteen groups (the slice's own):

1. **the navdock carries four spaces** — the fourth button with its
   icon-slot + word-label same-button anatomy, the new icon registered
   in the icon-set template, and the registry's no-attic law (every
   registered icon has a consumer);
2. **the world space is registered and the dock stands** — the spaces
   entry, the showSpace arm (every entry re-pulls, no cache), and the
   world's absence from the three-screen stand-down list;
3. **the screen's skeleton slots** — the section, the identity head and
   the four state slots, all empty and endpoint-driven;
4. **the log fetcher is wired** — the api.js export, the import block,
   the call at its post, and the served route's own literal;
5. **the grouped render in the server's order** — the days loop uses
   the payload's order directly, the day head shows ``date_localized``
   verbatim, and the renderer carries zero clocks (no ``new Date``);
6. **the legacy group reads honestly** — the ``date_localized: null``
   group answers the chrome word, its items carry the raw ``revealed_at``
   stamp, and no story day is fabricated;
7. **the fallback note is labeled** — the server's ``fallback: true``
   gets the small honest line, never English dressed as Chinese;
8. **the empty state invents nothing** — the error-shape judge (the
   fetchWorldInbox method) consumes the 404, the title stays empty, and
   the honest sentence is the screen's only content;
9. **the quiet-day arm** — the two-part judge (empty log + overview
   quiet) gates the chrome sentence;
10. **the bilingual chrome** — the sentence table reads in zh and en for
    every chrome sentence, zh the fallback;
11. **the today line wires into the world screen** — the button form,
    the click listener, and the render function's own zero-jump half;
12. **the silent arm is unclickable in step** — the fallback masthead
    hides the line (the button's ``hidden`` is the not-clickable state);
13. **the E2E shape** — a real server answers the log endpoint with the
    grouped shape (two injected story days, newest first, both signature
    arms, the fallback label) over the production assembly;
14. **the E2E honest arms** — an unbound stack answers the same 404 the
    frontend judge consumes, and the interface-language row renders the
    log in English (the lang chain the chrome table keys off).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import elc.web
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"

#: One durable timestamp for the injected rows (the wf-0 posture): the
#: injection rides its own short-lived writable connection while the
#: worker thread sits idle in its work loop.
NOW = "2025-09-14T08:00:00+00:00"


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _function_slice(source: str, head: str) -> str:
    """One top-level function's source, from its def line to the next
    (function-scoped assertions — a string elsewhere cannot satisfy
    them)."""

    start = source.index(head)
    ends = [
        found
        for found in (
            source.find("\nfunction ", start + 1),
            source.find("\nasync function ", start + 1),
            source.find("\nconst ", start + 1),
        )
        if found != -1
    ]
    return source[start : min(ends)] if ends else source[start:]


# ---------------------------------------------------------------------------
# 1 — the navdock carries four spaces


def test_the_navdock_carries_four_spaces() -> None:
    """navdock 四项钉：恰四钮（案头/世界/温故/抽屉——R4 裁决，≤5 红线
    合规）；新钮同钮 anatomy（图标插槽 + 文字标签）；世界图标在 icon-set
    模板注册（20×20 墨线、aria-hidden 由模板带出）；「注册的图标是使用
    的图标」负控——注册表十一枚全有消费方，无阁楼。"""

    index = _text("index.html")
    navdock = index.split('id="navdock"', 1)[1].split("</nav>", 1)[0]
    for space in ("parlor", "world", "study", "drawer"):
        assert f'class="navdock-item" data-space="{space}"' in index, space
    assert navdock.count('class="navdock-item"') == 4
    for label in (">案头</span></button>", ">世界</span></button>",
                  ">温故</span></button>", ">抽屉</span></button>"):
        assert label in index
    assert '<span class="navdock-glyph" data-icon="world"></span>' in index
    # the new icon's registration: the icon-set template carries the
    # world glyph (the ink-line island family — circle boundary, horizon,
    # a hill), aria-hidden like its siblings
    template = index.split('id="icon-set-source"', 1)[1]
    assert '<svg id="icon-world" class="inkicon" viewBox="0 0 20 20"' \
        in template
    assert '<circle cx="10" cy="10" r="7.2"/>' in template
    assert '<path d="M4.6 12.5 L15.4 12.5"/>' in template
    assert '<path d="M7.8 12.5 L10 9.6 L12.2 12.5"/>' in template
    # the no-attic law: every registered icon has a consumer — a
    # data-icon slot in the page or an inkIcon() call in the script
    # (v3-a's own law, extended to the eleventh icon)
    for registered in (
        "search", "chevron", "note", "write", "inbox", "lamp", "stamp",
        "desk", "world", "revisit", "drawer",
    ):
        consumed = (
            f'data-icon="{registered}"' in index
            or f'inkIcon("{registered}")' in _text("app.js")
            or f'inkIcon("{registered}")' in _text("components.js")
        )
        assert consumed, registered
    # the CSS contract's variant clause migrated with the fourth item
    css = _text("components.css")
    assert "五项以上" in css
    assert "四项以上" not in css


# ---------------------------------------------------------------------------
# 2 — the world space is registered and the dock stands


def test_the_world_space_is_registered_and_the_dock_stands() -> None:
    """spaces 注册 world 项 + showSpace world 臂（每次进屏重拉——无缓存
    发明）+ navdock 不让位钉（源级：让位清单字面恰是三屏，world 不在
    其中——误入即红）。"""

    app = _text("app.js")
    assert 'world: document.getElementById("space-world"),' in app
    assert "if (name === \"world\") loadWorldLogFace();" in app
    # the stand-down list is exactly the three dossier depths — the
    # world is a dock-level space and never joins it
    standdown = (
        'if (name === "partner" || name === "letters"'
        ' || name === "obs") {'
    )
    assert standdown in app
    assert "world" not in standdown


# ---------------------------------------------------------------------------
# 3 — the screen's skeleton slots


def test_the_world_screen_skeleton_slots() -> None:
    """世界屏结构钉：section 骨架 + 屏头（space-header 家族 + 世界身份
    空槽）/日志节/静日/空态四态 DOM 槽在 index——全部端点驱动零字面
    （无 JS 不发明：hidden 空槽 + 「暂无数据」静态兜底）。"""

    index = _text("index.html")
    assert '<section id="space-world" hidden>' in index
    assert '<header class="top space-header" id="world-head">' in index
    assert '<div class="who" id="world-title"></div>' in index
    assert '<p class="sub world-day" id="world-day" hidden></p>' in index
    assert '<div id="world-log-board"><p class="note">暂无数据</p></div>' \
        in index
    assert '<p class="doc-line" id="world-quiet" hidden></p>' in index
    assert '<p class="doc-line" id="world-empty" hidden></p>' in index
    # the identity head rides the space-header family (brand mark sm)
    head = index.split('id="world-head"', 1)[1].split("</header>", 1)[0]
    assert 'data-brand-mark="sm"' in head


# ---------------------------------------------------------------------------
# 4 — the log fetcher is wired


def test_the_log_fetcher_is_wired() -> None:
    """wiring 钉：fetchWorldLog 在 api.js export（端点字面）+ app.js 唯一
    api.js import 块 + loadWorldLogFace 调用点；服务端路由字面双在
    （web.py 的 /api/world/log 分支——消费缝的两端）。"""

    api = _text("api.js")
    assert (
        'export function fetchWorldLog() {\n'
        '  return getJson("/api/world/log");\n}'
    ) in api
    app = _text("app.js")
    start = app.index('import {\n  fetchTurn,')
    end = app.index('} from "./api.js";', start)
    assert "fetchWorldLog," in app[start:end]
    face = _function_slice(app, "async function loadWorldLogFace(")
    assert "log = await fetchWorldLog();" in face
    web = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    assert 'self.path == "/api/world/log"' in web


# ---------------------------------------------------------------------------
# 5 — the grouped render in the server's order


def test_the_log_renders_groups_in_server_order() -> None:
    """分组渲染钉：days 循环直用载荷序（服务端新→旧排好——前端零重排，
    无 reverse 无 sort）；组头 = date_localized 服务端直显；渲染器零时钟
    （切片内零 new Date——日期只来自服务端，wf-1 先例）。"""

    app = _text("app.js")
    face = _function_slice(app, "async function loadWorldLogFace(")
    assert "for (const group of log.days) {" in face
    assert "reverse" not in face
    assert "sort(" not in face
    renderer = _function_slice(app, "function renderWorldLogDay(")
    assert "head.textContent = legacy ? T.legacy" \
        " : String(group.date_localized ?? \"\");" in renderer
    assert "new Date" not in renderer
    assert "new Date" not in face


# ---------------------------------------------------------------------------
# 6 — the legacy group reads honestly


def test_the_legacy_group_reads_honestly() -> None:
    """legacy 组诚实读法钉：date_localized:null 组头 = chrome 词
    （「旧记录」——不造故事日）；组内条目 meta 行缀 revealed_at 原样
    时戳（旧时戳诚实示出，零再格式化）。解掉 legacy 分支或把时戳改成
    再格式化即红。"""

    app = _text("app.js")
    renderer = _function_slice(app, "function renderWorldLogDay(")
    assert "const legacy = group.date_localized == null;" in renderer
    assert "head.textContent = legacy ? T.legacy" \
        " : String(group.date_localized ?? \"\");" in renderer
    assert "if (legacy && item.revealed_at)" \
        " parts.push(String(item.revealed_at));" in renderer


# ---------------------------------------------------------------------------
# 7 — the fallback note is labeled


def test_the_fallback_note_is_labeled() -> None:
    """fallback 诚实标注钉（W-L 同族）：服务端 fallback:true ⇒ 小字行
    （fallback chrome 句——中文叙述缺席、示以原文），从不把英文伪装成
    中文。"""

    app = _text("app.js")
    renderer = _function_slice(app, "function renderWorldLogDay(")
    assert "if (item.fallback) {" in renderer
    assert 'fb.className = "note world-log-fallback";' in renderer
    assert "fb.textContent = T.fallback;" in renderer


# ---------------------------------------------------------------------------
# 8 — the empty state invents nothing


def test_the_empty_state_invents_nothing() -> None:
    """无绑定空态钉（诚实句零发明）：404 的 error 形判形（fetchWorldInbox
    同法）⇒ 空态句一句 + 屏仍可达；error 臂先 return 且 title 初值空
    ——空态不发明世界名（解掉初值空行或让 error 臂落世界名即红）。"""

    app = _text("app.js")
    face = _function_slice(app, "async function loadWorldLogFace(")
    assert "if (log && log.error) {" in face
    assert "empty.textContent = T.emptyWorld;" in face
    assert "empty.hidden = false;" in face
    assert "return;" in face
    # the error arm carries no title fill at all — the empty state never
    # carries a world name (the invention form — dressing the 404 up
    # with log.world_name — dies exactly here)
    error_arm = face[face.index("if (log && log.error) {"):]
    error_arm = error_arm[:error_arm.index("return;")]
    assert "title.textContent" not in error_arm
    assert "world_name" not in error_arm
    # the title starts empty and only the overview's success arm fills it
    assert 'title.textContent = "";' in face
    fill = face.index('title.textContent = String(overview.world_name);')
    guard = face.index("if (overview && !overview.error"
                       " && overview.world_name) {")
    assert guard < fill


# ---------------------------------------------------------------------------
# 9 — the quiet-day arm


def test_the_quiet_day_arm() -> None:
    """静日态钉（判据照书）：日志空 + overview 静日 ⇒ 一句静日句；
    判据不成立（overview 缺席）⇒ 诚实空兜底（stateBanner empty——不硬凑
    静日句）。"""

    app = _text("app.js")
    face = _function_slice(app, "async function loadWorldLogFace(")
    assert "if (!log.days.length) {" in face
    assert "if (overview && !overview.error && overview.today" in face
    assert "&& overview.today.quiet) {" in face
    assert "quiet.textContent = T.quietDay;" in face
    assert 'board.appendChild(stateBanner("empty"));' in face


def test_the_log_face_fails_closed_on_a_broken_payload() -> None:
    """wf-2 处置（评审 LOW-2）：坏载荷的 fail-closed 守卫与 error 横幅
    钉——log 读到但 days 非数组（形坏）⇒ 守卫先拦 + stateBanner error
    带 retry；守卫被删时坏载荷走 TypeError 静默死而套件不红，此钉补口。"""

    app = _text("app.js")
    face = _function_slice(app, "async function loadWorldLogFace(")
    assert "if (!log || !Array.isArray(log.days)) {" in face
    assert (
        'board.appendChild(stateBanner("error",'
        " { retry: loadWorldLogFace }));" in face
    )


def test_the_today_line_button_supply_is_pinned() -> None:
    """wf-2 处置（评审 LOW-1）：today-line 按钮化的完整 supply 声明钉
    ——border: 0 + background: none + cursor: pointer + text-align
    全在（只钉 display 前缀时，掉 supply 行会回归原生钮 chrome 而全绿）。"""

    screens = _text("screens.css")
    assert (
        ".today-line { display: block; margin: 0 0 18px; padding: 0;"
        in screens
    )
    assert "border: 0; background: none; text-align: left;" in screens
    assert "cursor: pointer; }" in screens


# ---------------------------------------------------------------------------
# 10 — the bilingual chrome


def test_the_world_log_chrome_speaks_both_languages() -> None:
    """双语 chrome 钉（句键表）：静日/空态/旧记录/fallback 四句 zh/en
    两读（zh 缺省回退）。任一句缺一读即红。"""

    app = _text("app.js")
    assert 'quietDay: "静悄悄的——世界还没有写下什么。",' in app
    assert (
        "quietDay: \"All quiet — the world hasn't written anything"
        ' yet.",' in app
    )
    assert 'emptyWorld: "这个世界还没有开始。",' in app
    assert 'emptyWorld: "This world hasn\'t begun yet.",' in app
    assert 'legacy: "旧记录",' in app
    assert 'legacy: "Older entries",' in app
    assert 'fallback: "（这张便条写在世界学会中文之前——示以原文。）",' in app
    assert (
        'fallback: "(This note predates the world\'s Chinese — shown'
        ' as written.)",' in app
    )
    assert (
        "function worldLogText(lang) {\n"
        "  return WORLD_LOG_TEXT[lang] || WORLD_LOG_TEXT.zh;\n}"
    ) in app


# ---------------------------------------------------------------------------
# 11 — the today line wires into the world screen


def test_the_today_line_wires_into_the_world_screen() -> None:
    """今日动静行接线钉（wf-1 挂账兑现）：index 升 button 形（键盘可达）
    + app.js click 监听 → showSpace("world")；「今日动静 · N 则」计数句
    保留（wf-1 词表零改动）；setTodayLine 渲染函数体内仍零 open/零链接
    （跳转在装配区监听，不在渲染函数）。"""

    index = _text("index.html")
    assert (
        '<button class="today-line" id="today-line" type="button"'
        " hidden></button>" in index
    )
    app = _text("app.js")
    assert (
        'document.getElementById("today-line").addEventListener("click",'
        "\n  () => showSpace(\"world\"));" in app
    )
    assert 'todayCount: "今日动静 · {n} 则",' in app
    today = _function_slice(app, "function setTodayLine(")
    assert "open(" not in today
    assert "showSpace" not in today


# ---------------------------------------------------------------------------
# 12 — the silent arm is unclickable in step


def test_the_today_line_is_silent_when_the_world_is_absent() -> None:
    """静默臂不可点同步钉：回落臂（无世界 404 / 读失败）= setTodayLine(null)
    ⇒ hidden（button 的 hidden 就是不可点态——零 JS 不发明同族）；
    回落渲染臂不接跳转（renderMasthead 切片零 showSpace）。"""

    index = _text("index.html")
    assert (
        '<button class="today-line" id="today-line" type="button"'
        " hidden></button>" in index
    )
    app = _text("app.js")
    render = _function_slice(app, "function renderMasthead(roster)")
    assert "setTodayLine(null);" in render
    assert "showSpace" not in render
    silencer = _function_slice(app, "function setTodayLine(")
    assert "line.hidden = true;" in silencer


# ---------------------------------------------------------------------------
# 13 — the E2E shape


def _inject_note(
    app_db: Path,
    event_id: str,
    kind: str,
    day: str,
    *,
    actor_id: str | None,
    status: str,
    narration: str,
    revealed_at: str | None = None,
) -> None:
    """One chronicle event plus its reveal-queue row, written by hand
    (the wf-0 suite's injection posture: the event first — the item's FK
    names it — then the item)."""

    writer = sqlite3.connect(app_db, timeout=10)
    try:
        writer.execute(
            "INSERT INTO world_event (event_id, world_id, kind, narration,"
            " effects, occurred_at, source)"
            " VALUES (?, 'world-berrymoor', ?, ?, '[]', ?, 'test')",
            (event_id, kind, narration, day),
        )
        writer.execute(
            "INSERT INTO world_reveal_item (item_id, world_id,"
            " source_event_id, actor_id, status, revealed_at, created_at)"
            " VALUES (?, 'world-berrymoor', ?, ?, ?, ?, ?)",
            (f"{event_id}:reveal", event_id, actor_id, status, revealed_at,
             NOW),
        )
        writer.commit()
    finally:
        writer.close()


def test_e2e_log_endpoint_serves_the_grouped_shape(tmp_path: Path) -> None:
    """前端消费的载荷，活体对表（真服务器 + 内置世界自动绑定）：fresh 栈
    200 空形（days:[]——零揭示是零条目，不是错误）；注入两故事日（一签
    名行 + 一世界自述行 + 一 fallback 行）⇒ 恰两组、新→旧、条目五键全、
    fallback 标注真——分组渲染的 premise 逐格成立。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, log = stack.get_json("/api/world/log")
        assert status == 200
        assert log["world_id"]
        assert log["world_name"] == "Berrymoor"
        assert log["ui_language"] in ("zh", "en")
        assert log["days"] == []

        _inject_note(
            app_db,
            "e-wf2-16",
            "wf2_untranslated",
            "2025-09-16",
            actor_id=None,
            status="REVEALED",
            narration="A note the world wrote before its Chinese.",
            revealed_at="2025-09-16T07:00:00+00:00",
        )
        _inject_note(
            app_db,
            "e-wf2-17",
            "tam_at_the_flats",
            "2025-09-17",
            actor_id="actor-berrymoor-nell",
            status="REVEALED",
            narration="Tam waves from the flats.",
            revealed_at="2025-09-17T08:00:00+00:00",
        )
        status, log = stack.get_json("/api/world/log")
        assert status == 200
        days = log["days"]
        assert [day["date_localized"] for day in days] == [
            "9月17日", "9月16日",
        ]
        newest, older = days
        item_keys = {
            "narration", "moment", "signature", "revealed_at", "fallback",
        }
        assert all(
            set(item) == item_keys
            for item in newest["items"] + older["items"]
        )
        assert newest["items"][0]["signature"] == "Nell Alder"
        assert newest["items"][0]["fallback"] is False
        assert older["items"][0]["signature"] is None
        assert older["items"][0]["fallback"] is True


# ---------------------------------------------------------------------------
# 14 — the E2E honest arms


def _get_json(port: int, path: str) -> tuple[int, Any]:
    """A GET that decodes error answers too (the read faces' 404 bodies
    are exactly the error shapes the frontend's judge consumes)."""

    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_e2e_unbound_log_404_and_the_language_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """无绑定栈（HTTP 级）：log 与 overview 同答 404 同句——前端
    ``log.error`` 判形消费的正是这个形（空态句的 premise）；语言行：
    ui_language=en ⇒ log 载荷与 date_localized 按英文形（前端 chrome
    词表的 lang 链路消费的就是载荷自己的 ui_language）。"""

    empty_dir = tmp_path / "no-worlds"
    empty_dir.mkdir()
    builtin = elc.web.BUILTIN_WORLDS_DIR
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", empty_dir)
    app_db = tmp_path / "unbound.db"
    with web_stack(app_db) as stack:
        status, log = _get_json(stack.port, "/api/world/log")
        assert status == 404
        assert "error" in log
        assert "没有绑定任何世界" in log["error"]
        status, overview = _get_json(stack.port, "/api/world/overview")
        assert status == 404
        assert overview["error"] == log["error"]

    # the language arm needs the builtin world back (the monkeypatch
    # would otherwise starve this stack's binding too)
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", builtin)
    with web_stack(tmp_path / "en.db") as stack:
        status, _ = stack.post(
            "/api/settings/ui_language", {"ui_language": "en"}
        )
        assert status == 200
        _inject_note(
            tmp_path / "en.db",
            "e-wf2-en",
            "harbour_fog",
            "2025-09-15",
            actor_id=None,
            status="REVEALED",
            narration="Fog swallows the quay.",
            revealed_at="2025-09-15T07:00:00+00:00",
        )
        status, log = stack.get_json("/api/world/log")
        assert status == 200
        assert log["ui_language"] == "en"
        assert [day["date_localized"] for day in log["days"]] == ["Sep 15"]
