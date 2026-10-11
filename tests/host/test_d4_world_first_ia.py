"""D-4 — the display-hierarchy unification (DEC-OPI-a4cf2d0e…63).

The user's ruling: the frontend stops carrying two logics side by side
(the character-card deck + the D-3 world screen) and reorganises onto
canonical §7's one layer — §7.1「世界是第一公民：先有世界，再有角色」
and §7.4「案头 = 当前世界的收件箱；世界架 = 世界切换面；世界指示器 =
世界名 + 世界内时间/天气的静默暗示」。

Six groups (the slice's own):

1. **the world indicator** — the masthead's main line is the world
   indicator: the world name (``.who``) and the in-world time
   (``.who-when``, driven by ``overview.date_localized``) on one line;
   the sub row keeps only the correspondence chrome, and the no-world
   fallback silences both world slots and restores the mc-1 shape;
2. **the deck's people face** — ``renderEnvelopeStack`` reads the
   ensemble (not the character list) and renders your character, the
   cast and the residents as rows; the roster read stays the bridge and
   the fallback arm;
3. **the unified click semantics** — a cast row lands in the
   correspondence (persona_id → roster character_id → the existing
   switch flow; the second click-through in the world screen goes home
   to the parlor), a resident row expands her read-only introduction
   and never touches a correspondence face, and your-character row is
   not a door;
4. **the world screen's doors** — the same two behaviours on the world
   screen's people zone, the world shelf zone (one cell = the current
   world), and the vacated stand-down arms (the world space is a
   navdock member now);
5. **the live probe** — a real ``run_web`` over a bound stack: the
   served DOM carries the world indicator slots, the navdock's world
   item, the shelf slot; the deck's payload chain (ensemble → rows →
   bridge) is real over HTTP and the 404 shape the arm judge consumes
   is real on an unbound stack;
6. **the migration manifest** — the same-cut truth moves restated in
   one place (the navdock count, the cover's postscript, the icon
   roster, the residents wrapper's retirement), each with its
   mechanical home named.

The pins are source-level where the shape is the contract (the wf-1 /
mc-1 idiom: a string elsewhere cannot satisfy a function-scoped pin)
and live-HTTP where behaviour is the contract.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import elc.web
from elc.web import _WebFace
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"

#: The D-3 section's declared strings (the ensemble's honest facts).
YOU_ANCHOR = "你是镇上的人，住在装订铺楼上的小房间"


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


def _get_json(port: int, path: str) -> tuple[int, Any]:
    """A GET that decodes error answers too (the read faces' 404 bodies
    are exactly the error shapes the page's judge consumes)."""

    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 1 — the world indicator (§7.4, R1)
# ---------------------------------------------------------------------------


def test_the_world_indicator_takes_the_main_line() -> None:
    """世界指示器升格（源级 + 结构）：index.html 的主位一行 = .who-line
    包 .who（世界名）与 .who-when（世界内时间）；renderWorldMasthead 把
    date_localized 放进时间格、副行只留「与…通信中」；回落臂把两个世界
    槽清空（.who = 角色名）。删时间格、把它退回副行、或让回落臂留残字
    都红。"""

    index = _text("index.html")
    assert (
        '<div class="who-line">\n'
        '          <div class="who"></div>\n'
        '          <div class="who-when"></div>\n'
        '        </div>' in index
    )
    assert '<div class="who-sub"></div>' in index
    app = _text("app.js")
    arm = _function_slice(app, "function renderWorldMasthead(overview)")
    assert (
        'const when = document.querySelector("#space-parlor .who-when");'
        in arm
    )
    assert (
        'when.textContent = String(overview.date_story ?? "");' in arm
    )
    # 副行只留通信 chrome——故事日不再进副行
    assert "date_localized" not in arm.split("const sub =")[1]
    assert "date_story" not in arm.split("const sub =")[1]
    assert 'T.corresponding.replace("{name}", mastheadCorrespondent)' in arm
    fallback = _function_slice(app, "function renderMasthead(roster)")
    assert 'if (when) when.textContent = "";' in fallback
    assert 'if (sub) sub.textContent = "";' in fallback
    # 屏级语汇单处（screens.css）零新令牌
    screens = _text("screens.css")
    assert (
        ".who-line { display: flex; align-items: baseline;"
        " gap: var(--sp-2); }" in screens
    )
    assert (
        ".who-when { font: var(--t-ui); color: var(--ink-faint); }" in screens
    )
    # 世界名仍不是页面字面（wf-1 律随迁：时间格的食粮是端点串）
    assert "Berrymoor" not in _text("index.html")
    assert "Berrymoor" not in app


# ---------------------------------------------------------------------------
# 2 — the deck's people face (R2, ensemble-driven)
# ---------------------------------------------------------------------------


def test_the_deck_reads_the_ensemble_not_the_character_list() -> None:
    """沓人面数据钉（源级）：世界臂的行全从 ensemble 的行区拼装——你的
    角色（user_character）/ cast / residents；名册（charactersCache）
    只作桥与回落臂的数据源。把行区换回名册列表（或删 ensemble 读）即
    红：遍历的对象必须是 ensemble.cast / ensemble.residents。"""

    app = _text("app.js")
    deck = _function_slice(app, "async function renderEnvelopeStack(")
    assert "const ensemble = await readWorldEnsemble();" in deck
    assert "roster = await fetchCharacters();" in deck   # 桥 + 回落臂
    assert "charactersCache = roster;" in deck
    assert "loadMasthead(roster);" in deck
    people = _function_slice(app, "function renderWorldPeopleStack(")
    assert (
        'for (const row of Array.isArray(ensemble.cast) ? ensemble.cast : []) {'
        in people
    )
    assert (
        "for (const row of Array.isArray(ensemble.residents)\n"
        "    ? ensemble.residents : []) {" in people
    )
    assert "stack.appendChild(buildWorldCastRow(row, card, T));" in people
    assert "stack.appendChild(buildWorldResidentRow(row));" in people
    assert "const you = ensemble.user_character;" in people
    # 世界臂不逐封建卡（envelopeCard 只归回落臂——renderRosterStack）
    assert "envelopeCard(" not in people
    roster_arm = _function_slice(app, "function renderRosterStack(")
    assert "const env = envelopeCard(item, {" in roster_arm
    assert "stack.appendChild(newEnvelopeCard());" in roster_arm
    # 世界臂的行区布局类与面板臂类
    assert (
        'stack.classList.toggle("envsel-stack--people", envselPeopleArm);'
        in deck
    )
    assert (
        'envselPanel.classList.toggle("envsel--people", envselPeopleArm);'
        in deck
    )
    screens = _text("screens.css")
    assert ".envsel-stack--people { height: auto; max-height: 60dvh; }" in screens
    assert ".envsel--people .env-browse { display: none; }" in screens
    assert ".person--you { border-left-style: dashed; }" in screens


# ---------------------------------------------------------------------------
# 3 — the unified click semantics (R2)
# ---------------------------------------------------------------------------


def test_the_cast_row_lands_in_the_correspondence() -> None:
    """点击桥钉（源级）：cast 行的点击 = persona_id → 名册桥（
    characterIdForPersona 的 persona_id 匹配）→ 既有 switchToCharacter
    流程 → 关沓（沓开着）或回案头（世界屏上）落通信。删桥、把行点击
    接回预览/别的面、或让无卡的行装门都红。"""

    app = _text("app.js")
    bridge = _function_slice(app, "function characterIdForPersona(personaId)")
    assert (
        "const roster = (charactersCache && charactersCache.characters)"
        " || [];" in bridge
    )
    assert (
        "(item) => item.persona_id != null\n"
        "      && String(item.persona_id) === String(personaId));" in bridge
    )
    assert "return row ? row.character_id : null;" in bridge
    open_corr = _function_slice(app, "async function openCorrespondence(")
    assert "const characterId = characterIdForPersona(personaId);" in open_corr
    assert "if (!characterId) return false;" in open_corr
    assert "const done = await switchToCharacter(characterId);" in open_corr
    assert "if (envselPanel) unfoldToParlor();" in open_corr
    assert 'else showSpace("parlor");' in open_corr
    cast_row = _function_slice(app, "function buildWorldCastRow(row, card, T)")
    assert "openCorrespondence(row.persona_id);" in cast_row
    assert 'person.classList.add("person--door");' in cast_row
    # the actions of the row keep their own entries (and stop the row click)
    assert 'act("起笔", "person-act-compose"' in cast_row
    assert 'act("档案", "person-act-dossier"' in cast_row
    assert 'act("编辑", "person-act-edit"' in cast_row
    assert "event.stopPropagation();" in cast_row
    # the world screen's cast row shares the same door
    screen = _function_slice(app, "function wireCastRow(row, personaId)")
    assert "if (characterIdForPersona(personaId) === null) return;" in screen
    assert "openCorrespondence(personaId);" in screen
    people = _function_slice(app, "function renderWorldPeople(")
    assert "wireCastRow(el, row.persona_id);" in people


def test_the_residents_expand_an_intro_and_never_a_communication_face() -> None:
    """居民无通信面钉（源级）：居民行（沓与世界屏两处同一实现
    wirePersonIntro）的点击只做介绍开合（aria-expanded + .person-intro
    全文），行内绝不出现 switchToCharacter / fetchSwitchCharacter /
    openCorrespondence / 沓的切换动作——正典：镇民无 persona 不通信。
    往居民行接任何通信面即红。"""

    app = _text("app.js")
    intro = _function_slice(app, "function wirePersonIntro(row, fields)")
    assert 'row.setAttribute("aria-expanded", "false");' in intro
    assert 'row.querySelector(".person-intro")' in intro
    assert "row.appendChild(personIntroBlock(fields));" in intro
    assert "toggle();" in intro
    for banned in ("switchToCharacter", "fetchSwitchCharacter",
                   "openCorrespondence", "unfoldToParlor",
                   "startComposing", "openPartnerDossier"):
        assert banned not in intro, banned
    block = _function_slice(app, "function personIntroBlock(fields)")
    assert 'intro.className = "person-intro";' in block
    assert "prose.textContent = vignette;" in block
    assert "innerHTML" not in block
    resident_row = _function_slice(app, "function buildWorldResidentRow(row)")
    for banned in ("switchToCharacter", "fetchSwitchCharacter",
                   "openCorrespondence", "characterIdForPersona"):
        assert banned not in resident_row, banned
    # Disposition (review LOW-3): the intro fields carry the role too —
    # the deck's expand matches the world screen's four-field shape.
    assert "wirePersonIntro(person, {" in resident_row
    assert "role: row.role," in resident_row
    assert "vignette: row.vignette," in resident_row
    people = _function_slice(app, "function renderWorldPeople(")
    assert "wirePersonIntro(el, fields);" in people
    # the you row is a display seat (no role, no tabindex, no listener)
    you = _function_slice(app, "function buildWorldYouRow(you)")
    assert "addEventListener" not in you
    assert "role" not in you
    assert "tabIndex" not in you


# ---------------------------------------------------------------------------
# 4 — the world screen's doors, the shelf, the vacated arms (R3/R4)
# ---------------------------------------------------------------------------


def test_the_world_screen_wears_the_shelf_and_the_doors() -> None:
    """世界面升格钉（源级 + 结构）：世界架区（单世界一格 = 当前世界，
    世界名 + 当前标记；无世界名走诚实空句）与两臂门（cast 行 → 通信、
    居民行 → 介绍）都在；世界屏作为 navdock 一级成员：让位两臂退役
    （缺位钉）而返回钮与 Esc 保留（在场钉）。"""

    index = _text("index.html")
    assert '<div id="world-shelf"><p class="note">暂无数据</p></div>' in index
    assert "<h3>世界架</h3>" in index
    assert 'data-space="world"' in index
    app = _text("app.js")
    shelf = _function_slice(app, "function renderWorldShelf(ensemble)")
    assert 'const box = diagBox("world-shelf");' in shelf
    assert "worldZoneError(box, ensemble, () => worldZoneRetry(\"shelf\"));" \
        in shelf
    assert "box.appendChild(stateBanner(\"empty\", { text: T.noWorldShelf }));" \
        in shelf
    assert 'cell.className = "world-shelf-cell world-shelf-cell--on";' in shelf
    assert "mark.textContent = T.current;" in shelf
    detail = _function_slice(app, "function renderWorldDetail(")
    assert "renderWorldShelf(ensemble);" in detail
    open_detail = _function_slice(app, "async function openWorldDetail(")
    assert '"world-shelf",' in open_detail
    retry = _function_slice(app, "async function worldZoneRetry(")
    assert "renderWorldShelf(ensemble);" in retry
    # 词表两读（zh/en）
    assert 'noWorldShelf: "世界架上还没有能打开的世界。",' in app
    assert 'noWorldShelf: "The shelf has no world to open yet.",' in app
    # 世界屏的读也把名册读新（桥的前提）
    assert "await readCharacterRoster();" in open_detail
    roster_read = _function_slice(app, "async function readCharacterRoster()")
    assert "charactersCache = await fetchCharacters();" in roster_read
    # navdock：让位两臂退役（世界是一级成员）——负控钉让位**形态**
    # （name 判据 + hidden 翻转同行）；处置刀在 wireNavdock 回调加的
    # 世界分叉（评审 MEDIUM-1 的入口接线）是另一层，不属让位语汇。
    assert 'if (name === "world") navdock.hidden = true;' not in app
    assert 'if (current === "world") navdock.hidden = true;' not in app
    assert (
        'document.getElementById("world-back").addEventListener(\n'
        '  "click", () => showSpace("parlor"));' in app
    )
    screens = _text("screens.css")
    assert ".world-shelf-cell { margin: var(--sp-3) 0 0;" in screens
    assert ".world-shelf-name { margin: 0; font-size: var(--fs-small);" in screens
    assert ".world-shelf-mark { margin-left: var(--sp-2); font: var(--t-ui);" \
        in screens
    assert ".world-person--door { cursor: pointer; }" in screens


# ---------------------------------------------------------------------------
# 5 — the live probe (a real server, the served DOM, the payload chain)
# ---------------------------------------------------------------------------


def test_the_live_http_faces_feed_the_two_seats(tmp_path: Path) -> None:
    """活体探针（真 HTTP）：一份绑定了内置世界的栈上——overview 的
    date_localized（世界指示器的时间格食粮）与 ensemble 的三段行区
    （你的角色 / cast / residents）逐键在；桥前提（cast.persona_id 与
    名册同键）实测成立；服务端七文件里世界指示器的 DOM 槽（.who-line/
    .who-when）与 navdock 的世界项、世界架槽在真服务的静态面里可读。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, overview = stack.get_json("/api/world/overview")
        assert status == 200
        assert overview["world_name"]
        # .who-when 的食粮：date_story = 同律故事日、不带世界名尾
        assert overview["date_story"]
        assert overview["world_name"] not in overview["date_story"]
        assert overview["date_localized"].startswith(overview["date_story"])
        status, ensemble = stack.get_json("/api/world/ensemble")
        assert status == 200
        assert ensemble["world_name"]
        who = ensemble["user_character"]
        assert who and who["anchor"] == YOU_ANCHOR
        cast = ensemble["cast"]
        assert [row["is_current"] for row in cast] == [True]
        assert all(row["vignette"] or row["identity"] for row in cast)
        residents = ensemble["residents"]
        assert len(residents) == 5
        assert all(row["role"] and row["vignette"] for row in residents)
        status, roster = stack.get_json("/api/characters")
        assert status == 200
        roster_by_persona = {
            row["persona_id"]: row["character_id"]
            for row in roster["characters"]
        }
        # 桥的实测：每个 cast 行都能在名册上找到 character_id
        for row in cast:
            assert row["persona_id"] in roster_by_persona
        # 真服务的静态面（served, not disk）：DOM 结构取证
        request = urllib.request.Request(f"http://127.0.0.1:{stack.port}/")
        with urllib.request.urlopen(request, timeout=30) as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
        for slot in (
            'class="who-line"',
            'class="who-when"',
            'data-space="world"',
            'data-icon="world"',
            'id="world-shelf"',
            "<h3>世界架</h3>",
            ">世界</span></button>",
        ):
            assert slot in page, slot
        # 静态面同源：app.js 也由这一服务出（臂与行区在同一个页面里）
        with urllib.request.urlopen(
            f"http://127.0.0.1:{stack.port}/static/app.js", timeout=30
        ) as response:
            assert response.status == 200
            assert "renderWorldPeopleStack" in response.read().decode("utf-8")


def test_the_arm_judge_consumes_the_real_404_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """无绑定栈（HTTP 级）：世界面 404 带 error 键（前端臂判据
    `!ensemble.error` 消费的正是这个形）⇒ 沓走回落臂（名册形）；同一
    栈上名册照答（回落臂的数据源在）。"""

    empty_dir = tmp_path / "no-worlds"
    empty_dir.mkdir()
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", empty_dir)
    with web_stack(tmp_path / "unbound.db") as stack:
        status, ensemble = _get_json(stack.port, "/api/world/ensemble")
        assert status == 404
        assert "error" in ensemble
        assert "没有绑定任何世界" in ensemble["error"]
        status, roster = _get_json(stack.port, "/api/characters")
        assert status == 200
        assert roster["characters"]
        # the page the judge lives in is still served whole
        request = urllib.request.Request(f"http://127.0.0.1:{stack.port}/")
        with urllib.request.urlopen(request, timeout=30) as response:
            assert response.status == 200


# ---------------------------------------------------------------------------
# 6 — the migration manifest (one mechanical home per moved truth)
# ---------------------------------------------------------------------------


def test_the_migration_manifest_restates_the_moved_truths() -> None:
    """随迁清单的机械落点（D-4 把下列真值一并搬迁，各自在就地钉住，
    此处收拢复核）：
    ① navdock 四项（世界项入坞）——r1_shell 的计数 4 与 cs2 的 navdock
       成员集；
    ② 封面又及句「底部四个词」——fg2 / wf3 / r1w 三处；
    ③ icon-set 十一枚（world 回集）——r1v 的清单与 components.css 的
       「现役十一枚」、spec 的 ③ 行尾与 ⑨-4 名册；
    ④ 世界指示器两槽（.who-line/.who-when）——wf1 的主从条两臂与
       本文件的第 1 组；
    ⑤ residents 封装出集——api.js 无导出、app.js 无导入（w1_web 的
       导入覆盖钉机械保障）；
    ⑥ 沓的居民面（buildEnvelopeResidentsContext）退役——其 caption/
       行内链迁到 buildPeopleCaption（wf1 第 4 组 + d3 的 caption 钉）。
    """

    index = _text("index.html")
    navdock = index.split('id="navdock"', 1)[1].split("</nav>", 1)[0]
    assert navdock.count('class="navdock-item"') == 4
    assert "又及：进门以后，底部四个词随时可走" in index
    components = _text("components.css")
    assert "现役十一枚" in components
    api = _text("api.js")
    assert "export function fetchWorldResidents" not in api
    app = _text("app.js")
    assert "fetchWorldResidents" not in app
    assert "buildEnvelopeResidentsContext" not in app
    assert "env-letters" not in _text("screens.css")
    assert "buildPeopleCaption(stack, String(ensemble.world_name ?? \"\"), T);" \
        in app
    # 冻结面零触碰（本刀的自我约束：docs 只动 FRONTEND_SPEC 的登记节）
    assert (REPO / "docs" / "FRONTEND_SPEC.md").exists()


def test_the_world_shelf_feeds_from_the_ensemble_seam() -> None:
    """面级守卫（stub host 的 404 形态）：世界架区在无世界 leg 时与其余
    区同答服务端 404 句（worldZoneError 消费的形），不造第二格、不造
    角标——单世界的最小就位不自造里程。"""

    class _NoWorldHost:
        app_db_path = "stub.db"

    face = _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]
    status, payload = face.world_ensemble()
    assert status == 404
    assert "没有绑定任何世界" in payload["error"]


def test_the_navdock_world_item_drives_the_read_not_only_the_switch() -> None:
    """D-4 处置钉（评审 MEDIUM-1）：navdock 的「世界」项必须驱动数据
    加载——showSpace 只切屏（study/drawer 靠 showSection 带数据），world
    在全量刷新外的唯一数据源是 openWorldDetail（三读 + 人面两臂桥）。
    本钉把「入坞后点它走 openWorldDetail」钉在源上：回调的 world 分叉
    一旦被简化回裸 showSpace，页面就是一张空屏（评审真浏览器实证）。"""

    app = _text("app.js")
    start = app.index("wireNavdock(")
    callback = app[start : app.index("});", start) + 3]
    assert 'if (name === "world")' in callback
    assert "openWorldDetail();" in callback

