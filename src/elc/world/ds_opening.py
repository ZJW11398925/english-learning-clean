"""The dual-seat POC's opening world (DS-1, the technical definition
§11: 「开局设定在位」; the POC's own 开局面) — a **micro world with one
situation waiting for your reply, two protagonists, and your own
character**, seeded the same way the Gold Scenario is (the persona
cards, then the atomic creation service) and driven by the turn spine
(``elc.world.turns``).

**DRAFT, stated in place** (the cut's own honesty law): the content
below is the POC opening's **draft** — written for this cut, marked as
a draft in one place, and waiting for the user's 定调; it is NOT a
gold-style frozen script (there are no author beats, no fixed prose,
no gate plan — the world starts from this seed and everything after is
the live loop's). The draft's status is this docstring's and
:data:`DS_OPENING_IS_DRAFT`'s to carry; a user revision is an ordinary
seed-content change, never a rewrite of sealed canon.

**The situation** (one sentence): the new bridge's cornerstone carries a
fresh vermilion mark nobody claims; the ferry steward has just asked
YOU — the painter who crossed at nightfall — whether it was already
there when you passed. The chapter's whole engine is that question
awaiting your reply.

Discipline: value constants + one seeding face (the gold posture); the
persona cards land ``INSERT OR IGNORE`` with the decodable ``lore_refs``
document (the gold fixture's own restart law); no clock, no SQL beyond
the seeding preamble's fixed literals; the world rides the shared V3
tables (the DS loop's canon faces), so no migration of its own.
"""

from __future__ import annotations

import sqlite3

from elc.platform.types import Result
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.bootstrap import (
    ActorSeed,
    PlayerSeed,
    WorldCreationOutcome,
    create_world_with_bible,
)
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.store import SqliteWorldStore

__all__ = [
    "DS_OPENING_IS_DRAFT",
    "DS_WORLD_BIBLE",
    "DS_WORLD_ID",
    "DS_WORLD_NAME",
    "HAN",
    "PLAYER",
    "WENQ",
    "seed_ds_world",
]


#: The draft flag the face (and any reader) answers with: the opening
#: content is a draft awaiting the user's 定调, never a frozen script.
DS_OPENING_IS_DRAFT = True

DS_WORLD_ID = "qingxi-ds-01"
DS_WORLD_NAME = "青溪渡 · 雾季"

#: The two protagonists and the player character (the POC's 双主角场).
WENQ = "wenq"
HAN = "han"
PLAYER = "ache"

BIBLE_REVISION_ID = f"{DS_WORLD_ID}-bible-r1"

#: The story-time cost of one ruling (the engine's per-instance
#: calibration, the Pipeline's own posture): five ticks — the opening's
#: calendar defines one tick as one minute of story time.
DS_ACTION_DURATION_TICKS = 5


DS_WORLD_BIBLE = BibleContent(
    premise=(
        "青溪渡，雾季。镇子不大，靠一道新落成的石桥和一条老渡口过活。"
        "桥成第三日，晨雾未散，桥基石栏上被人用朱砂画了一道没人认领的符——"
        "管事温秋蘅当众发了话，而夜里才到埠的画师，恰好从桥上走过。"
    ),
    genre="江南水乡的悬疑家常剧",
    tone="湿冷、克制、话里带秤；雾气底下藏事，人前只说三分",
    calendar=(
        "一刻度是一分钟的叙事时间。零刻度是今年霜降前三日的清晨。"
        "画师阿澈在入夜（约 1290）到埠，符在掌灯时分（约 1300）被更夫发现，"
        "当众对质在 1310 前后。"
    ),
    physics="寻常物理；符是朱砂颜料，画上不到一个时辰。",
    magic_rules="无。这个世界没有任何超自然之力；符是人画的。",
    geography=(
        "青溪镇夹在河湾里，南岸是老街与渡口，北岸通官道；"
        "新石桥横跨两岸，桥堍第七级台阶是官家的秤台。"
    ),
    society=(
        "船户、脚夫、几家铺面；渡口的规矩比县衙的告示更管用，"
        "管事的一句话能定一行人的行止。"
    ),
    politics="县衙远在半天水路之外；镇上之事，先过管事，再谈官府。",
    technology="木船、灯笼、朱砂、笔墨；桥是新修的，石料来自上游山场。",
    religion="河神香火淡薄，渡口只供一块无字石；镇人更信规矩不信神。",
    history=(
        "老渡口比镇子老，新桥是今年秋里才合龙的；"
        "桥资出自镇上公账，账目由管事温秋蘅一手过秤。"
    ),
    hard_rules=(
        "雾夜里渡口不出船，除非韩老倌亲自掌篙；"
        "新桥的石栏没人可以私自涂改，动一笔都要过管事的秤；"
        "没人能在夜里未过桥的情况下知道桥上之事。"
    ),
    narrative_preferences=(
        "家常的对峙、克制的对话；世界的规矩不为方便而弯折；"
        "每一段只写已发生的事，绝不预告未来；"
        "第二人称「你」的限知——你看不见的，正文不写。"
    ),
)


DS_ACTORS = (
    ActorSeed(
        actor_id=WENQ,
        persona_id="persona-wenq",
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=1,
        long_term_drive=(
            "赶在县里账房来对账前，把桥工公账与渡口的秩序都守得干干净净"
        ),
        current_arc_seed="桥成第三日，一道没人认领的朱砂符落在她秤过的石栏上",
        private_context=(
            "她初嫁来时在账房做过十年，一笔一笔都记得；"
            "丈夫去岁没在雾夜出船的人里，她最怕的就是雾夜——"
            "符是朱砂新画的，这她闻得出来，但她还没说。"
        ),
    ),
    ActorSeed(
        actor_id=HAN,
        persona_id="persona-han",
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=2,
        long_term_drive="守着这条河的夜渡，把水底下的事带进土里",
        current_arc_seed="雾季第一夜，桥上多了一道符，岸上多了一个外乡画师",
        private_context=(
            "他年轻时在上游沉过一条船，救不回人；"
            "朱砂符的样式他见过——三十年前沉船那晚，船板上也有这么一道。"
            "这话他谁也没说过。"
        ),
    ),
)


DS_PLAYER = PlayerSeed(
    player_character_id=PLAYER,
    name="阿澈",
    background="远道来投的年轻画师，受雇为新桥画一幅落成图，工钱在渡口账上",
    appearance="一身洗旧的青布衣，背着一卷没干透的画和一个颜料匣",
    abilities="画得一手好界画，眼睛毒——看过的东西过目能描；会撑船",
    limits="外乡人，在镇上无亲无故；夜间看不清朱砂与血的区别",
    location="渡口客栈",
    state="初到，人地两生",
    knowledge_refs="雇约上写着：落成图霜降前交",
)


#: The persona cards the ``world_actor`` FK requires, in the same order
#: as the seeds: (persona_id, name, identity, personality, background,
#: speech_style, values, boundaries).
DS_PERSONA_CARDS = (
    (
        "persona-wenq",
        "温秋蘅",
        "青溪渡的管事，桥工公账的过秤人",
        "克制、眼利、话不多但每句都有分量；规则感极重，公私分得很清",
        "初嫁来时在账房做过十年，丈夫去岁没了，一个人撑着渡口的秩序",
        "短句、带秤；先摆事实后问话，几乎不用感叹",
        "渡口的规矩高于任何人的方便，包括她自己的",
        "绝不当众撒谎；绝不动没过秤的钱；绝不承认没核过的话",
    ),
    (
        "persona-han",
        "韩老倌",
        "雾夜的渡船人，镇上最老的一条船的主人",
        "沉默、缓慢、看水不看人；话极少，出手极稳",
        "在青溪渡撑了四十年船，年轻时在上游沉过一条船",
        "几乎不主动开口；开口便是短句，像篙点石",
        "水底下的事烂在水里；渡口的夜路规矩不能破",
        "绝不在雾夜之外出船；绝不说救不回的人的事——除非被逼到墙角",
    ),
)


def seed_ds_world(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    bible_store: SqliteBibleStore,
    cast_store: SqliteCastStore,
    now: str,
) -> Result[WorldCreationOutcome]:
    """Seed the POC's opening world — the persona cards, then the
    atomic creation service (the world, its revision-1 ``CURRENT``
    Bible, the two protagonists, and the reader's painter). A
    same-shape replay answers the stored rows zero-write (the creation
    service's own ``world_id`` idempotency)."""

    _seed_persona_cards(conn, now)
    return create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=DS_WORLD_ID,
        name=DS_WORLD_NAME,
        bible_revision_id=BIBLE_REVISION_ID,
        bible=DS_WORLD_BIBLE,
        actors=DS_ACTORS,
        player=DS_PLAYER,
        now=now,
    )


def _seed_persona_cards(conn: sqlite3.Connection, now: str) -> None:
    """Land the persona cards the ``world_actor`` FK requires, then
    commit — the creation service opens its own ``BEGIN IMMEDIATE``, so
    this preamble must not leave a transaction open (the gold
    fixture's own posture). ``INSERT OR IGNORE``: a re-seed is a no-op,
    never a rewrite; ``lore_refs`` rides the decodable empty-array
    document so a host open reads the card table clean (the gold
    fixture's own restart law)."""

    for ordinal, card in enumerate(DS_PERSONA_CARDS, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO character_card ("
            " character_id, persona_id, name, identity, personality,"
            " background, speech_style, \"values\", boundaries, opening,"
            " scenario, generation_policy, lore_refs, revision, status,"
            " is_builtin, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', 'auto', '[]', 1,"
            " 'active', 1, ?, ?)",
            (f"ds-card-{ordinal}", *card, now, now),
        )
    conn.commit()
