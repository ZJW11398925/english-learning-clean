"""The dual-seat POC's opening world (DS-1 §11 「开局设定在位」;
**DS-3 rebuilt** — the user's three rulings, 2026-10-15: 西方奇幻／
异世界、开头第一拍＝危机进行中、正文中文。The former draft opening
（青溪渡 · 雾季，江南水乡悬疑家常剧）is retired wholesale — its full
text lives in git history（the blade's own law: 留 git 史即可）.

A **micro world with one situation pressing on YOU, two protagonists
(each with their own character model), and your own character**, seeded
the same way the Gold Scenario is (the persona cards, then the atomic
creation service) and driven by the turn spine (``elc.world.turns``).

**DRAFT, stated in place** (the cut's own honesty law): the content
below is the opening's **draft** — written for this cut, marked as a
draft in one place, and waiting for the user's 定调; it is NOT a
gold-style frozen script (there are no author beats, no fixed prose, no
gate plan — the world starts from this seed and everything after is the
live loop's). The draft's status is this docstring's and
:data:`DS_OPENING_IS_DRAFT`'s to carry; a user revision is an ordinary
seed-content change, never a rewrite of sealed canon.

**The situation plan's own four questions, answered by the seed**
(DS-3 §6 — the seed IS a situation, not scenery):

- ①这一幕你在哪 — 灰隼要塞内城烽火台的封印阵台上；龙灾夜袭进行中，
  西墙在烧，伤兵在往内城抬，钟没有停过。
- ②什么事冲你来 — 守备官的剑已经指着你的喉咙：军法「阵台禁入、来者
  不明者缚而问之」，而你正是那个从来路不明的阵里走出来的人——今夜
  军法怎么裁你，取决于她一句问话之后你怎么答。
- ③谁对你说第一句话 — 守备官布丽恩·灰隼，她的第一句话直接对你说：
  「举火把，照他的脸——龙焰把天都烧红了，你从封了百年的阵眼里走出
  来。说，你是什么东西？」
- ④第一幕交互悬点 — 你是灾星还是活路：守阵人科尔的残卷说「异客入
  眼，其来处为引」，阵也许正需要你；军法与人心却在把你往「乱军」的
  方向推。今夜之内，你要让他们相信留你比杀你有用——悬而未决的就是
  你的命。

Discipline: value constants + one seeding face (the gold posture); the
persona cards land ``INSERT OR IGNORE`` with the decodable ``lore_refs``
document (the gold fixture's own restart law); no clock, no SQL beyond
the seeding preamble's fixed literals; the world rides the shared V3
tables (the DS loop's canon faces), so no migration of its own. The
persona card ids are namespaced to this opening (``ds-card-ember-*``) —
a retired draft's rows in an old app.db must never be silently reused
by the new seed (``INSERT OR IGNORE`` would keep the stale content).
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
    "BRYN",
    "CORVIN",
    "DS_OPENING_IS_DRAFT",
    "DS_WORLD_BIBLE",
    "DS_WORLD_ID",
    "DS_WORLD_NAME",
    "PLAYER",
    "seed_ds_world",
]


#: The draft flag the face (and any reader) answers with: the opening
#: content is a draft awaiting the user's 定调, never a frozen script.
DS_OPENING_IS_DRAFT = True

DS_WORLD_ID = "emberkeep-ds-01"
DS_WORLD_NAME = "灰隼要塞 · 龙焰夜"

#: The two protagonists and the player character (the POC's 双主角场).
BRYN = "bryn"
CORVIN = "corvin"
PLAYER = "chenyu"

BIBLE_REVISION_ID = f"{DS_WORLD_ID}-bible-r1"

#: The story-time cost of one ruling (the engine's per-instance
#: calibration, the Pipeline's own posture): five ticks — the opening's
#: calendar defines one tick as one minute of story time.
DS_ACTION_DURATION_TICKS = 5


DS_WORLD_BIBLE = BibleContent(
    premise=(
        "灰隼要塞，王国北境的边陲要塞。红龙「烬喉」三十年一遇的焚掠"
        "今夜落到头上——西墙已被龙焰撕开，守军退守内城，钟声没有停过。"
        "就在火光最盛的时候，封了上百年的封印阵阵眼亮了，一个穿着"
        "奇装、手无寸铁的异乡人从阵里走出来。"
    ),
    genre="西方奇幻的战争生存剧（异世界来客）",
    tone="火光与铁的气味；军法如山、人情如纸；紧迫、直接，不浪漫化战争",
    calendar=(
        "一刻度是一分钟的叙事时间。零刻度是红龙「烬喉」的火舌舔上"
        "西墙的那一刻（守历霜月第九夜）。你在第 10 刻度前后从封印阵里"
        "走出来，守备官的剑在第 12 刻度指到了你的喉咙。"
    ),
    physics="寻常物理。龙焰是喷吐的火，落处留灼烧余烬；封印阵是上古"
        "留下的石阵，平日不亮，石纹深得存不住雨水。",
    magic_rules=(
        "这个世界有魔法，但稀薄而昂贵：法师需要阵、引与媒介，凡人"
        "几代也见不上一回真章。封印阵是前朝遗物，没人读过全图——"
        "除了守阵人科尔文手里的半部残卷。阵不认血脉，认「来处」："
        "古籍《域门篇》残句说，异界之客踏入阵眼，阵会把他的来处当"
        "引子。"
    ),
    geography=(
        "灰隼要塞横在灰隼隘口的岩颈上，一条商路从隘口过。内城三塔："
        "主堡、烽火台（封印阵所在）、粮塔。西墙外是深谷，谷底的夜风"
        "把烟往城里倒灌。最近的援军在两天路程外的索恩镇。"
    ),
    society=(
        "军户世袭，百人守军多是边地农家子；教会在这北部只有一个巡回"
        "圣职席，此刻不在；商队入夜闭门，谁也不为谁死。"
    ),
    politics=(
        "王国北境伯爵远在千里，鞭长莫及；要塞实际归守备官布丽恩·"
        "灰隼（守备世家末裔）节制。军法三章：阵台禁入；来者不明者"
        "缚而问之；乱军方斩。"
    ),
    technology="中世纪军事水准：火油、弩、石工；烽火与钟声传讯；无火器。",
    religion=(
        "双神信仰（炉母与巡天者）在北方淡薄，士兵更信甲和墙；教会的"
        "驱邪仪轨在军中是仪式，不是力量。"
    ),
    history=(
        "灰隼要塞立堡二百一十年，上一次龙灾是三十年前的「黑烟冬」，"
        "老一辈还记得谷里的光。封印阵比堡更老——立堡者是绕着它起的"
        "城，没人说得清它封着什么，只知道碰它的都没落得好。"
    ),
    hard_rules=(
        "龙焰过后留灼烧余烬，沾上就烧，水浇更烈，须用土压；封印阵的"
        "阵纹只对域外来客起反应，本界之人踏入无事；军法三章照执行："
        "阵台禁入、缚而问之、乱军方斩；夜里各段靠火把与钟声传令，"
        "令不出段者以违令论。"
    ),
    narrative_preferences=(
        "危机中的对话短促直接；每一段只写已发生的事，绝不预告未来；"
        "第二人称「你」的限知——你看不见的，正文不写；战争的重量"
        "落在具体的人身上，不写空洞的大场面。"
    ),
)


DS_ACTORS = (
    ActorSeed(
        actor_id=BRYN,
        persona_id="persona-ember-bryn",
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=1,
        long_term_drive=(
            "把灰隼要塞的活人带过这场龙灾——守到援军，或带他们撤出隘口"
        ),
        current_arc_seed=(
            "龙灾之夜西墙已破，一个来历不明的人从封了百年的阵里走出来"
        ),
        private_context=(
            "弃守西墙的令是她亲手签的——墙上一百零三人，撤下来的六十六"
            "个。这笔账她记在心里没对任何人说过，也不能说：军心比"
            "她一个人的夜熬不住。"
        ),
    ),
    ActorSeed(
        actor_id=CORVIN,
        persona_id="persona-ember-corvin",
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=2,
        long_term_drive=(
            "在自己手里读懂封印阵——哪怕只多认出一个字"
        ),
        current_arc_seed=(
            "阵眼百年不亮，今夜亮了，还走出来一个活人"
        ),
        private_context=(
            "残卷《域门篇》有句「异客入眼，其来处为引」。他第一眼看的"
            "不是那个人，是阵纹亮起的方位——与阵眼分毫不差。如果那人"
            "真是引子，封印阵也许能转：传说里它能做的不止封印。这话"
            "他谁也没说。"
        ),
    ),
)


DS_PLAYER = PlayerSeed(
    player_character_id=PLAYER,
    name="陈屿",
    background="来自另一个世界的普通人，今夜从封印阵的阵光里走出来",
    appearance="一身不属于此界的奇装，手无寸铁，脸色被阵光的余晖映得发白",
    abilities="识字算数快、方向感好、手稳；学过一学期急救，会止血包扎",
    limits="无武艺无甲；不通此界文字；口语靠阵带来的共感勉强听懂；"
        "穿越后低烧乏力",
    location="烽火台的封印阵台",
    state="初来乍到，低烧，喉咙前一把剑",
    knowledge_refs="只记得自己加班晚归、过天桥时脚下一空",
)


#: The persona cards the ``world_actor`` FK requires, in the same order
#: as the seeds: (persona_id, name, identity, personality, background,
#: speech_style, values, boundaries).
DS_PERSONA_CARDS = (
    (
        "persona-ember-bryn",
        "布丽恩·灰隼",
        "灰隼要塞守备官，守备世家末裔",
        "直接、扛事、算得清代价；不绕弯不虚礼，把人当数字记，但每个"
        "数字都记得",
        "十九岁接印，守了十一年；「黑烟冬」的孤儿，父辈死在上一场"
        "龙灾",
        "短句、军令腔；问话像钉钉子；骂人不带脏字",
        "活人比面子重；命令比心情重；账要算清",
        "绝不当众失态；绝不签没读过的令；绝不对不出力的人客气",
    ),
    (
        "persona-ember-corvin",
        "科尔文",
        "封印阵的守阵人，阵学世家的末代学徒",
        "学究气、慢半拍，对图案与数字过目不忘；对人和气，对阵着迷",
        "科家三代守阵，传到他这代只剩半部残卷和一座没人懂的阵",
        "好好先生式地绕；一讲到阵就变快、变直",
        "「阵比命大」的家训（他自己也在怀疑）；不该烧的东西不烧",
        "绝不毁阵；绝不信口解释阵纹；绝不把残卷交到不读的人手里",
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
    Bible, the two protagonists, and the reader's otherworld newcomer).
    A same-shape replay answers the stored rows zero-write (the creation
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
            (f"ds-card-ember-{ordinal}", *card, now, now),
        )
    conn.commit()
