"""cs-2 — the dossier knife's pins (档案页刀).

The rd-4 partner face was a floating stub card: an honest placeholder
name ("一位还没取名字的笔友"), two read-outs pulled from the diagnostics
memory face, and a three-card preview roster whose pick rode localStorage
with zero effect claims. cs-2 retires the whole stub and opens the real
face: the penpal is Nell Alder by name, her dossier is a full page (the
cover's form, not an overlay), her character text has a server-side
single source, and the drawer's memory page says who remembers what.

Six groups (the slice VAL's own):

1. **overlay retirement pins** — the overlay card, its factory and the
   roster stub are gone from every served file (zero occurrences), and
   the full-page view is present in their place (the section, the back
   button, the navdock standing down, the dock's three items untouched);
2. **endpoint truth pins** — ``GET /api/partner`` serves the character
   from its one source (the name and the prose derive from
   ``penpal_character_package()``, the webui spells none of it), the
   statistics come from the conversation's own committed turns, the
   memories face serves only ACTIVE rows of the penpal's pair, the
   episode face decodes the conversation's ACTIVE row;
3. **drawer partition pins** — the five memory panels regroup into three
   labelled zones (character / learning / audit) with the ownership
   notes on the zone faces, the page consumes the response's ``domain``
   field to place each panel, and every panel is a disclosure (the
   collapse/expand control the user asked for); the unfulfilled-promise
   empty sentence is corrected to what the producer actually does;
4. **input-state pins** — the focused pen lifts the desk (dock rise +
   deepened hairline + the ink line at the sheet's left edge) at the
   100ms tier, pure CSS, no glow, and the unfocused state occupies
   nothing;
5. **placeholder retirement pin** — the placeholder name sentence has no
   occurrence left in the served union (the endpoint's real name took
   its place);
6. **old-consumer pins** — ``/api/memory`` keeps its five panel keys and
   the cs-1 domain partition verbatim (the dossier added a face, it did
   not reshape the old one);
7. **the cs-2R disposition pins** — command turns are not letters (a
   teaching request or reply commits an empty ``raw_content`` row and
   the stats read reuses the store's own two payload markers to exclude
   it), the timeline order is pinned on *multi-day* data (a single-day
   ascend assertion is vacuous), the in-flight guard and the
   no-nesting rule are source-pinned, the day label coarsens without
   lying (更早, not 去年, for older years), and the two docstrings say
   what the SQL actually reads.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from elc.persona.penpal import (
    PENPAL_PERSONA_ID,
    penpal_character_package,
)
from tests.host.test_w1_web import (
    _page_source,
    web_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "src" / "elc" / "web.py"

CONV = "web-test"


def _page_of(tmp_path: Path) -> str:
    """The served page source over the plain offline stack (the F-G1
    union: index.html + every static asset it links)."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


def _fn_body(source: str, name: str) -> str:
    """One JS function's body from the served union — cut at the next
    ``function``/``async function`` head, whichever comes first."""

    after = source.split(f"function {name}(", 1)[1]
    cut = len(after)
    for marker in ("\nfunction ", "\nasync function "):
        index = after.find(marker)
        if index != -1:
            cut = min(cut, index)
    return after[:cut]


def _seed_relationship_rows(host) -> None:
    """Two durable rows in the penpal's pair: one ACTIVE (remembered),
    one SUPERSEDED (the memory's history — the dossier must not serve
    it). Direct INSERTs through the host's own connection: the read face
    under pin is the cs-2 dossier, not the cs-1 producer pipeline."""

    now = datetime.now(tz=UTC).isoformat()
    host.db.execute(
        "INSERT INTO relationship_memory ("
        " relationship_memory_id, persona_id, user_id, memory_type,"
        " provenance, canonical_content, status, source_turn_ids,"
        " provenance_refs, recorder_version, sensitivity_class,"
        " persistence_authorization, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "rm-cs2-active",
            str(PENPAL_PERSONA_ID),
            "cs2-user",
            "USER_STATED_FACT",
            "USER_STATED_FACT",
            "The user's name is 明兰.",
            "ACTIVE",
            "[]",
            "[]",
            "cs2-seed",
            "PERSONAL",
            "VALIDATED_DOMAIN_WRITE",
            now,
            now,
        ),
    )
    host.db.execute(
        "INSERT INTO relationship_memory ("
        " relationship_memory_id, persona_id, user_id, memory_type,"
        " provenance, canonical_content, status, source_turn_ids,"
        " provenance_refs, recorder_version, sensitivity_class,"
        " persistence_authorization, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "rm-cs2-superseded",
            str(PENPAL_PERSONA_ID),
            "cs2-user",
            "USER_STATED_FACT",
            "USER_STATED_FACT",
            "The user's name was a draft.",
            "SUPERSEDED",
            "[]",
            "[]",
            "cs2-seed",
            "PERSONAL",
            "VALIDATED_DOMAIN_WRITE",
            now,
            now,
        ),
    )
    host.db.execute(
        "INSERT INTO episode (episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ep-cs2",
            CONV,
            "1",
            1,
            2,
            "You told her about your street, and she asked about the"
            " mornings there.",
            '["what the street sounds like in the morning"]',
            "[]",
            "ACTIVE",
            now,
        ),
    )
    host.db.commit()


def _seed_two_days_of_letters(host) -> None:
    """Two ordinary letters on two distinct days (the durable shape a
    web commit writes: the raw text in both the envelope payload and the
    row's raw_content). Direct INSERTs keep the dates exact — a seeded
    date is a read-face fact, never a clock race."""

    for index, (stamp, text) in enumerate(
        (
            ("2026-09-28T10:00:00+00:00", "A letter from September."),
            ("2026-10-01T09:00:00+00:00", "A letter from October."),
        )
    ):
        suffix = f"cs2-day{index}"
        host.db.execute(
            "INSERT INTO input_envelope (input_id, client_message_id,"
            " conversation_id, persona_id, scene_id, interaction_channel,"
            " raw_payload, received_at) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?)",
            (f"in-{suffix}", f"msg-{suffix}", CONV, "TEXT", text, stamp),
        )
        host.db.execute(
            "INSERT INTO user_turn (user_turn_id, turn_id, conversation_id,"
            " turn_sequence, message_sequence, input_id, client_message_id,"
            " interaction_channel, raw_content, normalized_content,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
            (
                f"ut-{suffix}",
                f"t-{suffix}",
                CONV,
                800 + index,
                800 + index,
                f"in-{suffix}",
                f"msg-{suffix}",
                "TEXT",
                text,
                stamp,
            ),
        )
    host.db.commit()


def _seed_command_turn(host) -> None:
    """One durable teaching-command turn, in the shape
    ``request_teaching``/``respond_to_teaching`` actually commit
    (controller: empty ``raw_content``, the typed payload in the
    envelope) — the read face under pin is the stats SQL's discriminator,
    seeded in the producer's own durable form. The row sits at a high
    turn_sequence so a real committed letter (sequence 1) never
    collides."""

    host.db.execute(
        "INSERT INTO input_envelope (input_id, client_message_id,"
        " conversation_id, persona_id, scene_id, interaction_channel,"
        " raw_payload, received_at) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?)",
        (
            "in-cs2-cmd",
            "msg-cs2-cmd",
            CONV,
            "TEXT",
            '{"type":"TEACHING_REQUEST","target_id":"res-discourse-anyway"}',
            "2026-09-27T08:00:00+00:00",
        ),
    )
    host.db.execute(
        "INSERT INTO user_turn (user_turn_id, turn_id, conversation_id,"
        " turn_sequence, message_sequence, input_id, client_message_id,"
        " interaction_channel, raw_content, normalized_content, created_at)"
        " VALUES (?, ?, ?, 900, 900, ?, ?, ?, '', NULL, ?)",
        (
            "ut-cs2-cmd",
            "t-cs2-cmd",
            CONV,
            "in-cs2-cmd",
            "msg-cs2-cmd",
            "TEXT",
            "2026-09-27T08:00:00+00:00",
        ),
    )
    host.db.commit()


def _seeded_stack(tmp_path: Path):
    """One serving stack with the two memory rows already durable (the
    seed runs on the worker thread — the one thread the host's sqlite
    connections answer)."""

    return web_stack(tmp_path / "app.db", seed=_seed_relationship_rows)


# ---------------------------------------------------------------------------
# ① the overlay retirement + the full-page presence


def test_the_overlay_and_the_roster_are_gone(tmp_path: Path) -> None:
    """弹窗退役钉：浮层类（工厂三件与浮层类名）与名册桩（三位样例 +
    localStorage pick + 预览徽标）在服务的七个文件里零出现。"""

    page = _page_of(tmp_path)
    for gone in (
        "partnerCard",
        "showPartnerCard",
        "closePartnerCard",
        "partner-card",
        "PARTNER_PICK_KEY",
        "elp.partner.pick.v1",
        "PARTNER_ROSTER",
        "rosterCard",
        "readPartnerPick",
        "writePartnerPick",
        "Maya",
        "Nadia",
        "名册（预览）",
        "先记下这一位",
        "名字还没处取——先这么叫着。",
    ):
        assert gone not in page, gone


def test_the_full_page_view_is_present(tmp_path: Path) -> None:
    """全页视图在场钉：#space-partner 整页节 + 返回钮回案头的接线 +
    导航条让位臂 + spaces 表登记；档案不在导航条里（三项不变）。"""

    index = _page_of(tmp_path)
    assert 'id="space-partner"' in index
    assert 'id="partner-back"' in index
    assert 'id="dossier-name"' in index
    assert 'id="dossier-identity"' in index
    assert 'id="dossier-stats"' in index
    assert 'id="dossier-portrait"' in index
    assert 'id="dossier-memories"' in index
    assert 'id="dossier-episode"' in index
    assert 'id="dossier-timeline"' in index
    # the back button is the one way back (the navdock stands down here)
    assert (
        'document.getElementById("partner-back").addEventListener(\n'
        '  "click", closePartnerDossier);' in index
    )
    assert (
        "function closePartnerDossier() {\n"
        "  dossierOpen = false;\n"
        '  showSpace("parlor");\n'
        "}" in index
    )
    assert 'partner: document.getElementById("space-partner"),' in index
    # the navdock stand-down arm (the onboard line stays byte-identical);
    # v2-2 随迁：信档/观察两纵深同法让位（案头与档案的纵深，非新空间）
    assert (
        'document.getElementById("navdock").hidden = name === "onboard";'
        in index
    )
    assert (
        'if (name === "partner" || name === "letters" || name === "obs") {'
        in index
    )
    # cs-2R INFO-1：在飞守卫源钉（读在飞时人已回案头——不往看不见的页上写）
    assert "if (!dossierOpen) return;" in index
    # the dock keeps its three items; the dossier is not a fourth
    navdock = index.split('id="navdock"', 1)[1].split("</nav>", 1)[0]
    for item in ("parlor", "study", "drawer"):
        assert f'data-space="{item}"' in navdock, item
    assert 'data-space="partner"' not in navdock


# ---------------------------------------------------------------------------
# ② the endpoint truth pins


def test_the_route_and_the_page_consumer_exist() -> None:
    """路由与消费面：web.py 的 /api/partner 分支落 face.partner；api.js
    的 fetchPartner 是页面消费该端点的唯一入口。"""

    web = WEB.read_text(encoding="utf-8")
    assert '"/api/partner"' in web
    assert "self._run_on_host_thread(face.partner)" in web
    api = (REPO_ROOT / "src" / "elc" / "webui" / "api.js").read_text(
        encoding="utf-8"
    )
    assert 'getJson("/api/partner")' in api


def test_the_endpoint_serves_the_true_source(tmp_path: Path) -> None:
    """端点真源钉：名字与身份行从笔友真源派生（身份行按卡片自己的
    破折号切），三段散文原样通过——web.py 零自拼（真源变化即端点
    变化）；webui 全树零角色字面。"""

    package = penpal_character_package()
    head, sep, tail = str(package.identity).partition(" — ")
    with _seeded_stack(tmp_path) as stack:
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    card = payload["card"]
    assert card["name"] == head
    assert card["identity_line"] == (tail if sep else "")
    assert card["background"] == str(package.background)
    assert card["values"] == str(package.values)
    assert card["letter_habits"] == str(package.speech_style)
    # the served union spells none of the character: no name, no town,
    # no signature line anywhere in the seven files
    with web_stack(tmp_path / "app.db") as stack:
        page = _page_source(stack)
    for literal in ("Nell", "Alder", "Berrymoor", "Yours, Nell"):
        assert literal not in page, literal


def test_the_statistics_are_the_conversations_own(tmp_path: Path) -> None:
    """统计真数：两轮真实提交（POST /api/turn，脚本信使）后，往来数
    = 2、首次/最近通信日在场，时间线的封数合计 = 轮数（跨日不碎）。"""

    with _seeded_stack(tmp_path) as stack:
        first = stack.post("/api/turn", {"text": "Hello from cs-2."})
        assert first[0] == 200
        second = stack.post("/api/turn", {"text": "A second letter."})
        assert second[0] == 200
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    stats = payload["stats"]
    assert "error" not in stats
    assert stats["turns"] == 2
    assert stats["first_letter_at"] is not None
    assert stats["latest_letter_at"] is not None
    assert stats["first_letter_at"] <= stats["latest_letter_at"]
    days = stats["timeline"]
    assert sum(day["turns"] for day in days) == 2
    assert all(set(day) == {"date", "turns"} for day in days)
    # dates ascend (oldest first) and are plain YYYY-MM-DD strings
    assert [day["date"] for day in days] == sorted(
        day["date"] for day in days
    )


def test_the_memories_face_serves_active_rows_only(
    tmp_path: Path,
) -> None:
    """记忆真行：只服务 ACTIVE 行（SUPERSEDED 是记忆的历史不是现在），
    且只服务笔友这一对（persona 键来自导入常量，零自拼）；canonical
    文本原样通过。"""

    with _seeded_stack(tmp_path) as stack:
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    memories = payload["memories"]
    assert "error" not in memories
    rows = memories["memories"]
    assert [row["content"] for row in rows] == ["The user's name is 明兰."]
    assert rows[0]["memory_type"] == "USER_STATED_FACT"
    assert rows[0]["updated_at"]


def test_the_episode_face_serves_the_active_row(tmp_path: Path) -> None:
    """近况真行：本会话的 ACTIVE episode——摘要与话头（JSON 数组列
    解码）原样通过；无 ACTIVE 行的会话诚实答 None。"""

    with _seeded_stack(tmp_path) as stack:
        status, payload = stack.get_json("/api/partner")
        assert status == 200
        row = payload["episode"]["episode"]
        assert row is not None
        assert row["summary"] == (
            "You told her about your street, and she asked about the"
            " mornings there."
        )
        assert row["open_threads"] == [
            "what the street sounds like in the morning"
        ]
    # the honest empty shape: a fresh stack with no episode at all
    with web_stack(tmp_path / "empty.db") as stack:
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    assert payload["episode"]["episode"] is None
    assert payload["memories"]["memories"] == []
    assert payload["stats"]["turns"] == 0
    assert payload["stats"]["timeline"] == []


def test_command_turns_are_not_letters(tmp_path: Path) -> None:
    """cs-2R MEDIUM-1：教学命令轮（request_teaching / respond_to_teaching
    各落一行 ``raw_content=''`` 的 user_turn）不是往来——种一行命令轮 +
    零普通信：turns=0、首次/最近通信日空、时间线空。修复前这两行被计
    成「往来 1 封」。"""

    with web_stack(tmp_path / "app.db", seed=_seed_command_turn) as stack:
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    stats = payload["stats"]
    assert stats["turns"] == 0
    assert stats["first_letter_at"] is None
    assert stats["latest_letter_at"] is None
    assert stats["timeline"] == []


def test_a_command_turn_ride_along_is_not_counted(tmp_path: Path) -> None:
    """cs-2R MEDIUM-1 混合例：命令轮 + 一封普通信 → 只计普通信
    （turns=1、时间线恰一日一封）——排除面只吃命令轮，不吃邻居。"""

    with web_stack(tmp_path / "app.db", seed=_seed_command_turn) as stack:
        posted = stack.post("/api/turn", {"text": "A real letter."})
        assert posted[0] == 200
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    stats = payload["stats"]
    assert stats["turns"] == 1
    assert len(stats["timeline"]) == 1
    assert stats["timeline"][0]["turns"] == 1


def test_the_timeline_orders_days_ascending(tmp_path: Path) -> None:
    """cs-2R LOW-1：顺序钉落在多日数据上（两日各一封；单日数据的
    「升序」断言恒真、无鉴别力）——timeline 恰为升序两行逐值相等，
    first/latest 随真实先后。"""

    with web_stack(
        tmp_path / "app.db", seed=_seed_two_days_of_letters
    ) as stack:
        status, payload = stack.get_json("/api/partner")
    assert status == 200
    stats = payload["stats"]
    assert stats["turns"] == 2
    assert stats["timeline"] == [
        {"date": "2026-09-28", "turns": 1},
        {"date": "2026-10-01", "turns": 1},
    ]
    assert stats["first_letter_at"] == "2026-09-28T10:00:00+00:00"
    assert stats["latest_letter_at"] == "2026-10-01T09:00:00+00:00"


# ---------------------------------------------------------------------------
# ③ the drawer partition pins


def test_the_three_zones_carry_their_ownership_notes(
    tmp_path: Path,
) -> None:
    """三摞标注钉：角色记忆摞带「笔友记住的」归属句、学习记录摞带
    「教学系统的记录——笔友并不知道这些」（cs-0 的角色不知情边界，
    写给用户看的那一面）；三摞容器在场，五面板槽各归各摞。"""

    index = _page_of(tmp_path)
    character = index.split('id="mem-zone-character"', 1)[1].split(
        'id="mem-zone-learning"', 1)[0]
    learning = index.split('id="mem-zone-learning"', 1)[1].split(
        'id="mem-zone-audit"', 1)[0]
    audit = index.split('id="mem-zone-audit"', 1)[1].split(
        "</section>\n    </section>", 1)[0]
    assert "笔友记住的——关于你们的通信。" in character
    assert "教学系统的记录——笔友并不知道这些。" in learning
    assert "存根" in audit
    # the five panels sit in their own zones (the static initial shape;
    # the loader re-places them by the response's domain field)
    assert 'id="mem-relationship"' in character
    assert 'id="mem-episode"' in character
    assert 'id="mem-states"' in learning
    assert 'id="mem-evidence"' in learning
    assert 'id="mem-tombstones"' in audit
    # the five old panel headers are gone (the zones carry the h3 now)
    assert "<h3>关系</h3>" not in index
    assert "<h3>剧情</h3>" not in index


def test_the_page_consumes_the_domain_field(tmp_path: Path) -> None:
    """domain 分组消费钉：MEM_ZONES 以服务端 domain 词为键，placePanel
    读 .domain 落位（错位即搬家——分区是服务端声明的，页面照它归垛）。"""

    app = _page_of(tmp_path)
    zones = _fn_body_after(app, "const MEM_ZONES = {", "};")
    assert 'character: { box: "mem-zone-character" }' in zones
    assert 'learning: { box: "mem-zone-learning" }' in zones
    assert 'audit: { box: "mem-zone-audit" }' in zones
    place = _fn_body(app, "placePanel")
    assert "panel && panel.domain" in place
    assert "MEM_ZONES[panel && panel.domain]" in place
    assert "container.appendChild(slot)" in place
    # loadMemory routes all five panels through the domain placement
    load = _fn_body(app, "loadMemory")
    assert "placePanel(data." in load
    for slot in ("mem-relationship", "mem-episode", "mem-states",
                 "mem-evidence", "mem-tombstones"):
        assert f'"{slot}"' in load


def _fn_body_after(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_every_panel_is_a_disclosure(tmp_path: Path) -> None:
    """收起/展开控件钉：五个面板各是一件 #21 折叠（组头 = 面板名 +
    计数，默认收）——痕迹等内容不再永久摊开。"""

    app = _page_of(tmp_path)
    load = _fn_body(app, "loadMemory")
    assert "mountPanelDisclosure(" in load
    mount = _fn_body(app, "mountPanelDisclosure")
    assert "disclosure({" in mount
    assert "name: name," in mount
    assert "count: count," in mount
    # cs-2R INFO-2：嵌套负控（#21 禁嵌套）——面板折叠体内只造一件
    # disclosure（m15 形态：体内再嵌一件 → 恰此断言变红）
    assert mount.count("disclosure(") == 1
    # the five panels mount with their own names and counts
    for name, key in (
        ("关系", "memories"),
        ("剧情", "episodes"),
        ("学习状态", "states"),
        ("痕迹", "claims"),
        ("存根", "tombstones"),
    ):
        assert f'"{name}"' in load, name
        assert "panelCount(data." in load
        assert f'"{key}")' in load, key
    counter = _fn_body(app, "panelCount")
    assert "evidence_claim_count" in counter


def test_the_empty_promise_sentence_is_corrected(tmp_path: Path) -> None:
    """未兑现承诺句退役：「聊得多起来，才会记住」许了一个生产者并不
    承诺的机制——真源是显式自述（名字/住处/喜欢的事）才提案入册，
    空态句照此修正。"""

    page = _page_of(tmp_path)
    assert "聊得多起来" not in page
    corrected = (
        "还没记住什么——把你的事写进信里（名字、住的地方、喜欢的事），"
        "她会记下来。"
    )
    assert corrected in page


# ---------------------------------------------------------------------------
# ④ the input-state pins


def test_the_focused_pen_lifts_the_desk(tmp_path: Path) -> None:
    """输入态钉（聚焦臂）：dock 微升 + 上发丝线加深 + 稿纸左缘墨线
    显形——全部 100ms 档（--dur-micro），纯 CSS（:focus-within），
    禁发光（新块零 box-shadow / 零 blur）。"""

    screens = _page_of(tmp_path)
    dock = _fn_body_after(screens, ".dock {", ".dock-guide")
    assert "transition: transform var(--dur-micro) var(--ease-press)," in dock
    assert "border-top-color var(--dur-micro) var(--ease-press);" in dock
    assert ".dock:focus-within { transform: translateY(-2px);" in screens
    assert "border-top-color: var(--ink-ghost); }" in screens
    # the ink line: absent (zero opacity) until the pen is focused
    before = _fn_body_after(screens, ".dock-row::before", ".dock:focus-within")
    assert "position: absolute;" in before
    assert "opacity: 0;" in before
    assert "background: var(--ink-soft);" in before
    focused = _fn_body_after(
        screens, ".dock:focus-within .dock-row::before", ".dock-guide"
    )
    assert "opacity: 0.5;" in focused
    # the focused arms glow nothing: no blur in the block. v2-2 随迁
    # （8.2.2② dock/flow 层次）：垫板层的静态承托影（--stack-shadow-soft
    # 向上——纸叠两级令牌之内）在此块在场；聚焦臂仍零新增阴影/零发光
    # （blur 缺位钉保持——聚焦不改变阴影形态）。
    dock_block = _fn_body_after(screens, "/* 写信区：", "/* ── 温故")
    assert "box-shadow: var(--stack-shadow-soft);" in dock_block
    assert "blur(" not in dock_block


def test_the_unfocused_pen_occupies_nothing(tmp_path: Path) -> None:
    """输入态钉（非聚焦零占用）：占位句色过渡克制（100ms），聚焦时
    淡向水印墨；非聚焦态无任何新增形（墨线 opacity 0 + 绝对定位，
    dock 无位移）。"""

    page = _page_of(tmp_path)
    pen = _fn_body_after(page, ".pen::placeholder", ".pen:focus {")
    assert "transition: color var(--dur-micro) var(--ease-press);" in pen
    assert ".pen:focus::placeholder { color: var(--ink-ghost); }" in page
    # the dock carries no transform until focused (the rise is the
    # focused arm only; the transition line names transform without a
    # value colon, so the colon form is the assertion)
    dock_rule = _fn_body_after(page, ".dock {", ".dock:focus-within")
    assert "transform:" not in dock_rule


def test_the_dossier_day_coarsens_honestly(tmp_path: Path) -> None:
    """cs-2R INFO-4：dossierDay 的粗化不撒谎——今年「N 月 N 日」、去年
    「去年」、更早「更早」（原实现把更旧的信一律谎报成「去年」）。"""

    app = _page_of(tmp_path)
    day = _fn_body(app, "dossierDay")
    assert "now.getFullYear() - 1" in day
    assert '"去年"' in day
    assert '"更早"' in day


def test_the_dossier_docstrings_say_what_the_sql_reads() -> None:
    """cs-2R LOW-2 / INFO-5 的源钉：memories 面不再声称 user 绑定
    （V1 单用户照实），stats 面写明 60 日上限作用在 GROUP BY day 之后
    （修掉的是 quiet days，不是有信的日子）；命令轮判别式来自 store
    同一对 marker（同语义复用，不再自推导）。"""

    web = WEB.read_text(encoding="utf-8")
    assert "Local V1 is single-user" in web
    assert "bound user" not in web
    assert "that carried letters" in web
    assert "_LETTER_FILTER_SQL" in web
    assert "TEACHING_REQUEST_PAYLOAD_MARKER" in web
    assert "TEACHING_RESPONSE_PAYLOAD_MARKER" in web


# ---------------------------------------------------------------------------
# ⑤ the placeholder retirement pin


def test_the_placeholder_name_sentence_is_gone(tmp_path: Path) -> None:
    """占位句退役钉：「一位还没取名字的笔友」全树零出现——真名由
    /api/partner 供给（② 组的端点钉在数据面锁同一事实）。"""

    assert "一位还没取名字的笔友" not in _page_of(tmp_path)


# ---------------------------------------------------------------------------
# ⑥ the old-consumer pins


def test_the_memory_face_keeps_its_shape(tmp_path: Path) -> None:
    """旧消费面不破：/api/memory 五键仍在、cs-1 的 domain 分区逐词
    不动、面板负载体保持各自的键——档案页长的是新脸，没有重塑旧脸。"""

    with _seeded_stack(tmp_path) as stack:
        stack.post("/api/turn", {"text": "Hello again."})
        status, readout = stack.get_json("/api/memory")
    assert status == 200
    for panel in ("relationship_memory", "episode", "learner_states",
                  "evidence", "tombstones"):
        assert panel in readout, panel
    assert readout["relationship_memory"]["domain"] == "character"
    assert readout["episode"]["domain"] == "character"
    assert readout["learner_states"]["domain"] == "learning"
    assert readout["evidence"]["domain"] == "learning"
    assert readout["tombstones"]["domain"] == "audit"
    assert isinstance(readout["relationship_memory"]["memories"], list)
    assert isinstance(readout["episode"]["episodes"], list)
    assert isinstance(readout["learner_states"]["states"], list)
    assert "claims" in readout["evidence"]
    assert "tombstones" in readout["tombstones"]


def test_the_static_allowlist_is_still_seven() -> None:
    """零新静态文件：档案页生在既有七文件之内（白名单不动）。"""

    from tests.host.test_fg1_architecture import FILES

    assert len(FILES) == 7
