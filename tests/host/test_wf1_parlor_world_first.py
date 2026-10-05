"""WF-1 — the parlor's world-first masthead and the residents face.

The user's ruling (DEC-OPI-5fc42174-…5 R3/R7, verbatim intent): the desk
is the world's — the master-detail bar names the world first, the story
day and the resident ride the sub row, today's notes get their own weak
line, and the envelope stack is re-framed as the world's residents. The
whole face is endpoint-assembled: zero world-name literals in the webui
(the character-name precedent), and the mc-1 roster shape survives as
the honest fallback arm when no world is bound.

Nine groups (the slice's own):

1. **the zero-literal pin** — no 「Berrymoor」 in any served file (any
   casing); the world name only ever arrives through
   ``/api/world/overview``'s ``world_name``;
2. **the world-first arm** — ``renderWorldMasthead`` puts the world name
   in ``.who``, assembles the sub row from ``date_localized`` (server-
   localized, shown as-is) plus the 「与…通信中」 chrome keyed by the
   payload's ``ui_language``, and feeds ``overview.today`` to the today
   line;
3. **the fallback arm** — ``renderMasthead`` keeps the mc-1 truth
   (``.who`` = the roster's current character only), clears the sub row
   and silences the today line: removing the fallback call from
   ``loadMasthead`` leaves an empty masthead, and the pin goes red on
   exactly that;
4. **the wiring pins** — both fetchers are exported by api.js, imported
   by app.js's single api.js import block, and called at their posts
   (the mc-1 wiring-pin shape; the import-coverage pin in test_w1_web
   keeps the block honest mechanically);
5. **the residents face** — the panel's aria-label and the deck caption
   are assembled from ``world_name`` through the sentence table; every
   envelope may carry the honest letters count; the confluence joins
   residents ⨝ roster **by persona_id** (the switch-required
   ``character_id`` stays on the roster row); the envelopeCard DOM shape
   is untouched (components.js carries none of the new names);
6. **the residents fallback** — a residents read that errors or 404s
   leaves the panel on the current 「信封沓」 context: no caption, no
   annotation, no invented world name;
7. **the switch face is untouched** — the switch call lines survive
   verbatim (api.js's POST, app.js's await, the three switch call sites,
   the local reload): re-framing the deck re-frames nothing about
   switching;
8. **the bilingual chrome** — the sentence table reads in zh and en for
   every chrome sentence; the quiet-day sentence passes through
   verbatim (the server's own human words, never re-written here);
9. **the E2E faces** — a real server on a bound stack answers the
   overview and the residents with exactly the keys the frontend
   assembles from (the roster join's ``persona_id`` premise included),
   and a no-binding stack answers the same honest 404 the frontend's
   error-shape judge consumes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import elc.web
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"


def _get_json(port: int, path: str) -> tuple[int, Any]:
    """A GET that decodes error answers too (the read faces' 404 bodies
    are exactly the error shapes the frontend's judge consumes)."""

    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))

#: The seven shell files (the whole face a source pin may speak about).
WEBUI_FILES = (
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
        )
        if found != -1
    ]
    return source[start : min(ends)] if ends else source[start:]


# ---------------------------------------------------------------------------
# 1 — the zero-literal pin


def test_no_world_name_literal_in_the_webui() -> None:
    """webui 零世界名字面（角色名先例同构——裁决 R7）：七文件任何大小写
    的 「berrymoor」 都不出现；世界名只经 /api/world/overview 的
    world_name 进页（服务端数据，前端只拼装）。"""

    for name in WEBUI_FILES:
        body = _text(name)
        assert "berrymoor" not in body.lower(), name


# ---------------------------------------------------------------------------
# 2 — the world-first arm


def test_the_masthead_world_first_arm() -> None:
    """成功臂钉（源级）：renderWorldMasthead 把 world_name 放进 .who；
    副行 = date_localized（服务端已本地化直显）+ 「与…通信中」 chrome
    （按载荷 ui_language 走词表）——两段拼装都在；今日动静行吃
    overview.today。删世界名行或任一拼装段即红。"""

    app = _text("app.js")
    arm = _function_slice(app, "function renderWorldMasthead(overview)")
    assert 'who.textContent = String(overview.world_name ?? "");' in arm
    assert "parts.push(String(overview.date_localized));" in arm
    assert (
        'parts.push(T.corresponding.replace("{name}",'
        " mastheadCorrespondent));" in arm
    )
    assert 'sub.textContent = parts.join(" · ");' in arm
    assert "setTodayLine(overview.today, overview.ui_language);" in arm
    # the resident feeds the compose salutation's correspondent too —
    # a null resident (the world's own narration) leaves it empty
    assert (
        'mastheadCorrespondent = resident ? String(resident.name ?? "")'
        ' : "";' in arm
    )


def test_the_masthead_fallback_arm_keeps_the_roster_truth() -> None:
    """回落臂钉（源级，两分支都有断言——解掉回落臂 ⇒ 空主从条的变异
    恰红）：renderMasthead 保持 mc-1 真源（.who = 名册 current 一行，
    不发明人名），并清空副行、静默今日动静行；loadMasthead 的编排 =
    overview 判形成功走世界臂、否则回落臂消费名册（调用方已取到的
    不取第二遍），回落调用 renderMasthead(roster) 恰此一处。"""

    app = _text("app.js")
    arm = _function_slice(app, "function renderMasthead(roster)")
    assert 'who.textContent = current ? current.name : "";' in arm
    assert (
        "const current = items.find(\n"
        "    (item) => item.character_id ==="
        " (roster && roster.current_character_id));" in arm
    )
    assert 'if (sub) sub.textContent = "";' in arm
    assert "setTodayLine(null);" in arm
    assert (
        'mastheadCorrespondent = current ? current.name : "";' in arm
    )
    loader = _function_slice(app, "async function loadMasthead(")
    assert "overview = await fetchWorldOverview();" in loader
    # the error-shape judge: a 404 body carries `error` — the fallback
    # arm is the world's honest absence, never an empty guess
    assert (
        "if (overview && !overview.error && overview.world_name)" in loader
    )
    assert "renderWorldMasthead(overview);" in loader
    assert "renderMasthead(roster);" in loader
    # the fallback call lives exactly once — inside the loader
    assert app.count("renderMasthead(roster);") == 1
    assert app.index("renderMasthead(roster);") > app.index(
        "async function loadMasthead("
    )


# ---------------------------------------------------------------------------
# 3 — the wiring pins


def test_the_two_world_fetchers_are_wired() -> None:
    """wiring 钉（mc-1 同形）：两 fetcher 在 api.js export（各带端点
    字面）+ app.js 唯一 api.js import 块 + 各自调用点（装载臂与居民
    面）。删导出、删导入、删调用三者任一即红；块内一致性由
    test_w1_web 的 import-coverage 钉机械保障。"""

    api = _text("api.js")
    assert (
        'export function fetchWorldOverview() {\n'
        '  return getJson("/api/world/overview");\n}'
    ) in api
    assert (
        'export function fetchWorldResidents() {\n'
        '  return getJson("/api/world/residents");\n}'
    ) in api
    app = _text("app.js")
    start = app.index('import {\n  fetchTurn,')
    end = app.index('} from "./api.js";', start)
    block = app[start:end]
    assert "fetchWorldOverview," in block
    assert "fetchWorldResidents," in block
    loader = _function_slice(app, "async function loadMasthead(")
    assert "overview = await fetchWorldOverview();" in loader
    residents_face = _function_slice(
        app, "async function buildEnvelopeResidentsContext(")
    assert "data = await fetchWorldResidents();" in residents_face
    # the three masthead call sites: startup, the stack's own refresh,
    # and the post-switch reload
    assert "loadMasthead().catch(() => {});" in app
    assert "loadMasthead(roster);" in app
    assert "await loadMasthead();" in app


# ---------------------------------------------------------------------------
# 4 — the residents face


def test_the_envelope_selector_wears_the_residents_face() -> None:
    """居民面钉（源级）：面板 aria-label 与沓顶 caption 经词表从
    world_name 拼装（caption 落沓首上方——insertBefore(stack)）；每封
    信数弱标注用 residents 的诚实计数；合流 = residents ⨝ roster
    **by persona_id**（character_id 仍在名册行上——切换必需）；
    envelopeCard DOM 形不变——components.js 不携带任何新名。"""

    app = _text("app.js")
    face = _function_slice(
        app, "async function buildEnvelopeResidentsContext(")
    assert (
        'panel.setAttribute(\n'
        '      "aria-label", T.residentsOf.replace("{world}", worldName));'
    ) in face
    assert 'caption.className = "envsel-caption";' in face
    assert "stack.parentNode.insertBefore(caption, stack);" in face
    assert 'note.className = "env-letters";' in face
    assert (
        'T.letters.replace(\n'
        '      "{n}", String(Number(resident.letters_count) || 0));' in face
    )
    # the confluence: residents keyed by persona_id, the roster row
    # found by character_id, joined on persona_id
    assert 'byPersona.set(String(resident.persona_id), resident);' in face
    assert (
        "const resident = item && item.persona_id != null\n"
        "      ? byPersona.get(String(item.persona_id))\n"
        "      : null;" in face
    )
    assert (
        "const roster = (charactersCache && charactersCache.characters)"
        " || [];" in face
    )
    # the envelopeCard factory is untouched — the annotation is a
    # sibling appended app-side, never a new envelopeCard part
    components = _text("components.js")
    for marker in ("envsel-caption", "env-letters", "persona_id",
                   "residents"):
        assert marker not in components, marker
    # the deck and the refresh share the face (idempotent re-dress)
    assert "buildEnvelopeResidentsContext(panel, stack);" in app
    assert "buildEnvelopeResidentsContext(envselPanel, stack);" in app


def test_the_selector_falls_back_without_residents() -> None:
    """回落钉（源级）：residents 缺席（404 的 error 键判形 / 读失败 /
    载荷坏形）⇒ 居民面整面弃权——aria-label 保持现役「信封沓」原词、
    无 caption 无标注，不发明世界名。守卫句与原词两断言都红才容得下
    「回落被拆」。"""

    app = _text("app.js")
    face = _function_slice(
        app, "async function buildEnvelopeResidentsContext(")
    assert (
        "if (!data || data.error || !Array.isArray(data.residents))"
        " return;" in face
    )
    assert 'panel.setAttribute("aria-label", "信封沓");' in app


# ---------------------------------------------------------------------------
# 5 — the switch face is untouched


def test_the_switch_face_is_untouched() -> None:
    """切换零改钉（源级逐行）：POST /api/characters/switch 的封装行、
    app.js 的 await 行、三处 switchToCharacter 调用点、切换成功后的
    局部刷新——逐字在场。沓归位居民面不改切换行为（裁决边界）；
    删改任一行即红。"""

    api = _text("api.js")
    assert (
        'return postJson("/api/characters/switch",'
        " { character_id: characterId });" in api
    )
    app = _text("app.js")
    switcher = _function_slice(app, "async function switchToCharacter(")
    assert "data = await fetchSwitchCharacter(characterId);" in switcher
    assert "await refreshCorrespondence();" in switcher
    # the deck's three switch entry points: re-click the previewed
    # envelope, the stack card's 对话, the browser page's 对话
    assert app.count("switchToCharacter(") >= 4  # 3 sites + the def


# ---------------------------------------------------------------------------
# 6 — the bilingual chrome


def test_the_parlor_chrome_speaks_both_languages() -> None:
    """双语钉（源级句键表）：居民位 chrome、今日动静计数、居民面
    caption、信数标注四句 zh/en 两读（zh 缺省回退）；静日句透显——
    服务端人话原样上页（前端零再创作）。任一句缺 en 缺 zh 即红。"""

    app = _text("app.js")
    assert (
        'corresponding: "与 {name} 通信中",' in app
    )
    assert 'corresponding: "In correspondence with {name}",' in app
    assert 'todayCount: "今日动静 · {n} 则",' in app
    assert 'todayCount: "Today · {n} notes",' in app
    assert 'residentsOf: "{world} 的居民",' in app
    assert 'residentsOf: "Residents of {world}",' in app
    assert 'letters: "{n} 封信",' in app
    assert 'letters: "{n} letters",' in app
    assert (
        "function parlorWorldText(lang) {\n"
        "  return PARLOR_WORLD_TEXT[lang] || PARLOR_WORLD_TEXT.zh;\n}"
    ) in app
    today = _function_slice(app, "function setTodayLine(")
    assert 'line.textContent = String(today.note ?? "");' in today
    assert (
        'parlorWorldText(lang).todayCount\n'
        '    .replace("{n}", String(count));' in today
    )


# ---------------------------------------------------------------------------
# 7 — the today line and the sub row's honest slots


def test_the_today_line_is_endpoint_driven_and_jumpless() -> None:
    """今日动静行钉：index.html 空槽（hidden 静默——无 JS 不发明）；
    详情面属 wf-2——本行零跳转（setTodayLine 函数体内零 open/零链接）；
    副行同形空槽；screens.css 只用既有弱化语汇（.sub 族 var() 引令牌，
    零新令牌）。"""

    index = _text("index.html")
    assert '<div class="who-sub"></div>' in index
    assert '<p class="today-line" id="today-line" hidden></p>' in index
    app = _text("app.js")
    today = _function_slice(app, "function setTodayLine(")
    assert "open(" not in today
    assert "<a" not in today
    assert "location" not in today
    screens = _text("screens.css")
    assert (
        ".who-sub { font: var(--t-ui); color: var(--ink-faint); }" in screens
    )
    assert (
        ".today-line { margin: 0 0 18px; font: var(--t-ui);"
        " color: var(--ink-faint); }" in screens
    )
    assert (
        ".envsel-caption { margin: 0; font: var(--t-ui);"
        " color: var(--ink-faint); }" in screens
    )
    assert ".env-letters { margin: 2px 0 0; font-size: var(--fs-small);" in (
        screens
    )


def test_the_compose_salutation_names_the_correspondent() -> None:
    """称呼位钉（世界优先的必要随迁）：.who 装世界名后，写作面的
    「致 …」改读 mastheadCorrespondent（两个渲染臂各自更新——回落臂
    的当前角色名 / 成功臂的居民位；世界自述留空不发明称呼），
    不再从 .who 的文本反读。"""

    app = _text("app.js")
    assert "let mastheadCorrespondent = \"\";" in app
    chrome = _function_slice(app, "function fillComposeChrome(")
    assert "const name = mastheadCorrespondent.trim();" in chrome
    assert "who.textContent.trim()" not in app


# ---------------------------------------------------------------------------
# 8 — the E2E faces


def test_overview_and_residents_feed_the_new_face(tmp_path: Path) -> None:
    """前端消费的两份载荷，活体对表（真服务器 + 内置世界自动绑定）：
    overview 的 world_name/date_localized/today/resident 与 residents
    的六键行全在；合流前提 = 名册行与居民行共享 persona_id（join 键
    两侧都在）。"""

    with web_stack(tmp_path / "app.db") as stack:
        status, overview = stack.get_json("/api/world/overview")
        assert status == 200
        assert overview["world_name"]
        assert overview["date_localized"]
        assert overview["today"]["quiet"] is True
        assert overview["today"]["note"]
        assert overview["resident"] is not None
        assert set(overview["resident"]) == {
            "actor_id", "persona_id", "name",
        }
        assert overview["ui_language"] in ("zh", "en")

        status, residents = stack.get_json("/api/world/residents")
        assert status == 200
        rows = residents["residents"]
        assert rows and residents["world_name"]
        for row in rows:
            assert set(row) == {
                "actor_id", "persona_id", "name", "identity",
                "is_current", "letters_count",
            }
            assert row["letters_count"] == 0
        assert sum(1 for row in rows if row["is_current"]) == 1

        status, roster = stack.get_json("/api/characters")
        assert status == 200
        roster_personas = {
            row["persona_id"] for row in roster["characters"]
        }
        resident_personas = {row["persona_id"] for row in rows}
        # the join key lives on both sides — the confluence's premise
        assert resident_personas & roster_personas


def test_the_read_faces_404_without_a_binding(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """无绑定栈（HTTP 级）：run_web 的绑定循环拿不到内置包 ⇒ 无绑定
    ——overview 与 residents 同答 404 同句（判形路径可构造：404 体带
    error 键，前端 `data.error` 判形回落臂消费的正是这个形）。"""

    empty_dir = tmp_path / "no-worlds"
    empty_dir.mkdir()
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", empty_dir)
    with web_stack(tmp_path / "unbound.db") as stack:
        status, overview = _get_json(stack.port, "/api/world/overview")
        assert status == 404
        assert "error" in overview
        assert "没有绑定任何世界" in overview["error"]
        status, residents = _get_json(stack.port, "/api/world/residents")
        assert status == 404
        assert "error" in residents
        assert residents["error"] == overview["error"]
