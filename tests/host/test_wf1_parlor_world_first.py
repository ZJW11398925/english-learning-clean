"""WF-1 — the parlor's world-first masthead and the world's people.

The user's ruling (DEC-OPI-5fc42174-…5 R3/R7, verbatim intent): the desk
is the world's — the master-detail bar names the world first, the story
day and the resident ride the sub row, today's notes get their own weak
line, and the envelope stack is re-framed as the world's residents. The
whole face is endpoint-assembled: zero world-name literals in the webui
(the character-name precedent), and the mc-1 roster shape survives as
the honest fallback arm when no world is bound.

Nine groups (the slice's own), with the D-4 cut's truth migrations
(DEC-OPI-a4cf2d0e…63 R1/R2 — the display-hierarchy unification: the
world indicator takes the main slot, and the deck becomes the world's
people);

1. **the zero-literal pin** — no 「Berrymoor」 in any served file (any
   casing); the world name only ever arrives through
   ``/api/world/overview``'s ``world_name``;
2. **the world-first arm** — ``renderWorldMasthead`` puts the world name
   in ``.who`` and the in-world time in ``.who-when`` (one line: the
   §7.4 world indicator), assembles the sub row from the 「与…通信中」
   chrome keyed by the payload's ``ui_language``, and feeds
   ``overview.today`` to the today line;
3. **the fallback arm** — ``renderMasthead`` keeps the mc-1 truth
   (``.who`` = the roster's current character only), clears both world
   slots and silences the today line: removing the fallback call from
   ``loadMasthead`` leaves an empty masthead, and the pin goes red on
   exactly that;
4. **the wiring pins** — both fetchers are exported by api.js, imported
   by app.js's single api.js import block, and called at their posts
   (the mc-1 wiring-pin shape; the import-coverage pin in test_w1_web
   keeps the block honest mechanically);
5. **the world's people (D-4)** — the deck's world arm renders the
   ensemble: your character (display), the cast (name / one-line
   vignette / letter count / current mark; clicking the row lands in the
   correspondence) and the residents (name / role / vignette; clicking
   expands her read-only introduction) — the caption and aria-label are
   assembled from the ensemble's own ``world_name`` through the sentence
   table, and the bridge to the switch is cast ``persona_id`` ⨝ roster
   ``persona_id`` (the switch-required ``character_id`` stays on the
   roster row);
6. **the fallback arm's context** — no world (or a failed read) leaves
   the deck on the current 「信封沓」 context: the roster stack, no
   caption, no invented world name (the D-4 arm judge);
7. **the switch face is untouched** — the switch call lines survive
   verbatim (api.js's POST, app.js's await, the switch call sites, the
   local reload): re-framing the deck re-frames nothing about
   switching;
8. **the bilingual chrome** — the sentence table reads in zh and en for
   every chrome sentence; the quiet-day sentence passes through
   verbatim (the server's own human words, never re-written here);
9. **the E2E faces** — a real server on a bound stack answers the
   overview and the ensemble with exactly the keys the frontend
   assembles from (the bridge's ``persona_id`` premise included), and a
   no-binding stack answers the same honest 404 the frontend's
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
    """成功臂钉（源级）：renderWorldMasthead 把 world_name 放进 .who、
    世界内时间放进 .who-when（D-4 世界指示器：§7.4「世界名 + 世界内
    时间的静默暗示」= .who-line 主位一行两格——故事日不再走副行；
    时间格读 date_story = 不带世界名尾的同律故事日，名字不重复）；
    副行只留「与…通信中」chrome（按载荷 ui_language 走词表）；今日动静
    行吃 overview.today。删世界名行、时间格或任一拼装段即红。"""

    app = _text("app.js")
    arm = _function_slice(app, "function renderWorldMasthead(overview)")
    assert 'who.textContent = String(overview.world_name ?? "");' in arm
    # D-4：时间格在 .who-line 里（与名同行的静默暗示；date_story 无名尾）
    assert 'when.textContent = String(overview.date_story ?? "");' in arm
    assert 'document.querySelector("#space-parlor .who-when");' in arm
    assert (
        "sub.textContent = mastheadCorrespondent\n"
        '      ? T.corresponding.replace("{name}",'
        " mastheadCorrespondent)\n"
        '      : "";' in arm
    )
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
    不发明人名），并清空两个世界槽（.who-when / .who-sub）、静默今日
    动静行；loadMasthead 的编排 = overview 判形成功走世界臂、否则回落
    臂消费名册（调用方已取到的不取第二遍），回落调用 renderMasthead(roster)
    恰此一处。"""

    app = _text("app.js")
    arm = _function_slice(app, "function renderMasthead(roster)")
    assert 'who.textContent = current ? current.name : "";' in arm
    assert (
        "const current = items.find(\n"
        "    (item) => item.character_id ==="
        " (roster && roster.current_character_id));" in arm
    )
    assert 'if (when) when.textContent = "";' in arm   # D-4 时间格同静默
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


def test_the_world_fetcher_is_wired() -> None:
    """wiring 钉（mc-1 同形；D-4 迁移）：overview 的封装在 api.js export
    （带端点字面）+ app.js 唯一 api.js import 块 + 两个调用点（主从条
    装载臂 + 沓的世界臂）。删导出、删导入、删调用三者任一即红；块内
    一致性由 test_w1_web 的 import-coverage 钉机械保障。
    D-4 迁移：residents 读的前端消费者（沓的居民面）被「世界里的人」
    替下——封装 fetchWorldResidents 出集（阁楼纪律：没有消费者的封装
    不留），服务端端点照旧（wf-0 读面钉不动）。"""

    api = _text("api.js")
    assert (
        'export function fetchWorldOverview() {\n'
        '  return getJson("/api/world/overview");\n}'
    ) in api
    assert "export function fetchWorldResidents" not in api   # retired
    app = _text("app.js")
    start = app.index('import {\n  fetchTurn,')
    end = app.index('} from "./api.js";', start)
    block = app[start:end]
    assert "fetchWorldOverview," in block
    assert "fetchWorldResidents" not in block
    loader = _function_slice(app, "async function loadMasthead(")
    assert "overview = await fetchWorldOverview();" in loader
    # D-4：沓的世界臂经 readWorldEnsemble（同一读面族的 null-on-failure
    # 包装）取世界里的人
    deck = _function_slice(app, "async function renderEnvelopeStack(")
    assert "const ensemble = await readWorldEnsemble();" in deck
    # the masthead call sites: startup, the stack's own refresh, and the
    # post-switch reload
    assert "loadMasthead().catch(() => {});" in app
    assert "loadMasthead(roster);" in app
    assert "await loadMasthead();" in app


# ---------------------------------------------------------------------------
# 4 — the world's people (D-4: the deck's world arm)


def test_the_deck_wears_the_worlds_people() -> None:
    """世界里的人钉（源级，D-4 重铸 wf-1 的居民面）：沓的世界臂（世界在）
    的行 = 你的角色（.person--you，展示位——非可点）+ cast（.person--cast：
    名 + 一句 vignette + 信数 + 当前标记；行点击 = 通信）+ 镇民
    （.person--resident：名/角色/vignette；点行展开介绍）。caption 与
    aria-label 由世界臂自己的 ensemble 载荷经词表从 world_name 拼装
    （caption 落沓首上方——insertBefore(stack)；幂等摘旧）；桥 = cast
    的 persona_id 在名册（charactersCache）上找 character_id（切换必需
    的 id 在名册行上）。evelopeCard 工厂不在世界臂出现（回落臂仍是它
    ——见 mc-1）；components.js 不携带任何新名。"""

    app = _text("app.js")
    face = _function_slice(app, "function buildPeopleCaption(")
    assert (
        'panel.setAttribute(\n'
        '    "aria-label", T.residentsOf.replace("{world}", worldName));'
    ) in face
    assert 'caption.className = "envsel-caption";' in face
    assert "stack.parentNode.insertBefore(caption, stack);" in face
    # wf-1 处置（评审 LOW-1）的真值随迁：caption 的幂等摘旧行——面板
    # DOM 复用时（refreshEnvelopeStack 的重排路径）无摘除则 caption
    # 逐次堆积；该行真承重，钉住。
    assert "stale.remove();" in face
    assert 'panel.querySelector(".envsel-caption");' in face
    assert "if (!panel || !worldName) return;" in face   # 无世界名不装框定
    # 世界详情行内链（D-3 入口②）随 caption 同处
    assert "worldLink.textContent = T.worldDetail;" in face

    people = _function_slice(app, "function renderWorldPeopleStack(")
    assert (
        'buildPeopleCaption(stack, String(ensemble.world_name ?? ""), T);'
        in people
    )
    assert "buildWorldYouRow(you)" in people
    assert "buildWorldCastRow(row, card, T)" in people
    assert "buildWorldResidentRow(row)" in people
    # 桥（D-4）：cast 行 persona_id ⨝ 名册行 persona_id → 卡
    assert (
        "const card = roster.find(\n"
        "      (item) => item.persona_id != null\n"
        "        && String(item.persona_id) === String(row.persona_id)"
        ") || null;" in people
    )
    assert (
        "const roster = (charactersCache && charactersCache.characters)"
        " || [];" in people
    )
    person_you = _function_slice(app, "function buildWorldYouRow(you)")
    assert 'row.className = "person person--you";' in person_you
    assert "name.textContent = String(you.name ?? \"\");" in person_you
    assert "anchor.textContent = String(you.anchor ?? \"\");" in person_you
    assert "addEventListener" not in person_you   # 展示位——非可点
    cast_row = _function_slice(app, "function buildWorldCastRow(row, card, T)")
    assert 'person.className = "person person--cast";' in cast_row
    assert "note.textContent = T.current;" in cast_row     # 当前标记
    assert "meta.textContent = T.letters.replace(" in cast_row
    assert "openCorrespondence(row.persona_id);" in cast_row
    assert 'act("起笔", "person-act-compose"' in cast_row
    assert 'act("档案", "person-act-dossier"' in cast_row
    assert 'act("编辑", "person-act-edit"' in cast_row
    resident_row = _function_slice(app, "function buildWorldResidentRow(row)")
    assert 'person.className = "person person--resident";' in resident_row
    assert "wirePersonIntro(person, { name: row.name, vignette: row.vignette });" \
        in resident_row
    # 两臂的闸与布局类（世界臂的人行区）
    deck = _function_slice(app, "async function renderEnvelopeStack(")
    assert (
        "envselPeopleArm = !!(ensemble && !ensemble.error"
        " && ensemble.world_name);" in deck
    )
    assert 'stack.classList.toggle("envsel-stack--people", envselPeopleArm);' \
        in deck
    assert "renderWorldPeopleStack(stack, ensemble);" in deck
    # components.js 不携带任何新名（envelopeCard 工厂只服务回落臂）
    components = _text("components.js")
    for marker in ("envsel-caption", "person--cast", "person--resident",
                   "persona_id", "residents"):
        assert marker not in components, marker


def test_the_selector_falls_back_without_a_world() -> None:
    """回落钉（源级，D-4 迁移）：世界缺席（无绑定 404 的 error 键判形 /
    读失败 / 无 world_name）⇒ 世界臂整面弃权——沓回落现役名册形
    （renderRosterStack：信封卡与空白封的原装配线），aria-label 保持
    现役「信封沓」原词、无 caption，不发明世界名。两断言都红才容得下
    「回落被拆」。"""

    app = _text("app.js")
    deck = _function_slice(app, "async function renderEnvelopeStack(")
    assert (
        "envselPeopleArm = !!(ensemble && !ensemble.error"
        " && ensemble.world_name);" in deck
    )
    assert "renderRosterStack(stack, roster);" in deck
    # the world name guard: a caption without a world name is never built
    face = _function_slice(app, "function buildPeopleCaption(")
    assert "if (!panel || !worldName) return;" in face
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
    """今日动静行钉（WR-5 随迁：行回纯信息 <p>——世界日志屏整体退役，
    点击接线与 button 供性随屏退役；信息仍在：overview.today 端点驱动，
    静日句/计数形/回落静默三臂不变）：index.html <p> 空槽（hidden 静默
    ——无 JS 不发明）；setTodayLine 函数体内零跳转零链接；副行同形
    空槽；screens.css .sub 族 var() 引令牌零新令牌。"""

    index = _text("index.html")
    assert '<div class="who-sub"></div>' in index
    # D-4 世界指示器：主位一行两槽（名 + 世界内时间）——两槽都在册
    assert '<div class="who-line">' in index
    assert '<div class="who-when"></div>' in index
    assert (
        '<p class="today-line" id="today-line" hidden></p>' in index
    )
    # WR-5: the button form and its click wiring are gone with the screen.
    assert 'today-line" type="button"' not in index
    app = _text("app.js")
    today = _function_slice(app, "function setTodayLine(")
    assert "open(" not in today
    assert "<a" not in today
    assert "location" not in today
    # WR-5 退役面（世界日志屏）的缺位钉随迁（D-3 世界详情屏）：旧屏的
    # 三大件名只许活在 WR-5 的历史注记里，不得有任何调用位；原字面
    # `showSpace("world") not in app` 的钉意（旧屏不回场）由「world 空间
    # 键的进屏调用恰一处——新世界详情屏」承担，新屏的在场钉落
    # tests/host/test_d3_world_detail.py（同一空间名三代屏：旧屏 = 单页
    # 日志，新屏 = 五区详情；同名不是回场，是承接）。
    for gone in ("loadWorldLogFace", "renderWorldLogDay", "WORLD_LOG_TEXT"):
        assert f"{gone}(" not in app, gone
    assert app.count('showSpace("world")') == 1
    screens = _text("screens.css")
    assert (
        ".who-sub { font: var(--t-ui); color: var(--ink-faint); }" in screens
    )
    # D-4：时间格与名同行的指示器一行（.who-line flex 基线对齐）
    assert (
        ".who-line { display: flex; align-items: baseline;"
        " gap: var(--sp-2); }" in screens
    )
    assert (
        ".who-when { font: var(--t-ui); color: var(--ink-faint); }" in screens
    )
    assert (
        ".today-line { display: block; margin: 0 0 18px; padding: 0;"
        in screens
    )
    assert (
        ".envsel-caption { margin: 0; font: var(--t-ui);"
        " color: var(--ink-faint); }" in screens
    )
    # D-4 迁移：沓中信数标注（.env-letters）随居民面出集——信数现在住在
    # 世界里的人行上（.person-meta，同族弱化语汇）
    assert ".env-letters" not in screens
    assert ".person-meta { margin: 2px 0 0; font-size: var(--fs-small);" in (
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


def test_overview_and_ensemble_feed_the_new_face(tmp_path: Path) -> None:
    """前端消费的两份载荷，活体对表（真服务器 + 内置世界自动绑定）：
    overview 的 world_name/date_localized/today/resident 与 ensemble 的
    cast 行全在（D-4 迁移：世界里的人读 ensemble——旧 residents 面已
    无前端消费者）；桥前提 = cast 行与名册行共享 persona_id（join 键
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

        status, ensemble = stack.get_json("/api/world/ensemble")
        assert status == 200
        rows = ensemble["cast"]
        assert rows and ensemble["world_name"]
        for row in rows:
            assert set(row) == {
                "actor_id", "persona_id", "name", "identity",
                "vignette", "is_current", "letters_count",
            }
            assert row["letters_count"] == 0
            assert row["vignette"]        # 世界里的人读的那句
        assert sum(1 for row in rows if row["is_current"]) == 1
        assert ensemble["residents"] and ensemble["user_character"]

        status, roster = stack.get_json("/api/characters")
        assert status == 200
        roster_personas = {
            row["persona_id"] for row in roster["characters"]
        }
        cast_personas = {row["persona_id"] for row in rows}
        # the join key lives on both sides — the bridge's premise
        assert cast_personas & roster_personas


def test_the_read_faces_404_without_a_binding(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """无绑定栈（HTTP 级）：run_web 的绑定循环拿不到内置包 ⇒ 无绑定
    ——overview 与 ensemble 同答 404 同句（判形路径可构造：404 体带
    error 键，前端 `data.error` 判形回落臂消费的正是这个形）。"""

    empty_dir = tmp_path / "no-worlds"
    empty_dir.mkdir()
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", empty_dir)
    with web_stack(tmp_path / "unbound.db") as stack:
        status, overview = _get_json(stack.port, "/api/world/overview")
        assert status == 404
        assert "error" in overview
        assert "没有绑定任何世界" in overview["error"]
        status, ensemble = _get_json(stack.port, "/api/world/ensemble")
        assert status == 404
        assert "error" in ensemble
        assert ensemble["error"] == overview["error"]
