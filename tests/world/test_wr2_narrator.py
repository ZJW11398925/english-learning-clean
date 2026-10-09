"""WR-2 — the world narrator and the generated step (the paradigm
flip's domain half; WR-4 correction …58: no letter ever enters).

The living-world paradigm flip (direction DEC-OPI-5fc42174…49, then the
user's third direction DEC-…58: 「信不是剧情发展方向……世界的发展则完全
不受影响」): the world's step is model-generated novel prose, wound by
the turn's mechanical trigger and narrated from the world's own life —
**the letter's text never reaches this layer** (spec §4.1 / the 走向
entry's two-layer law; the letter shapes the penpal layer's reply
only). The pin groups:

1. **the prompt** — carries **no letter at all** (WR-4's judgment
   face: every letter line is absent, the letter section header is
   gone, and the world-autonomy instruction is present), the bible's
   three parts are present (setting prose, the cast on one line, the
   whole lore fact set — an empty set says so honestly), the recent
   chronicle rides old→new (only the recent slice, only what
   happened), and the interface language picks the narration language
   (zh / en; anything else is a construction refusal);
2. **the strict parse** — a well-formed batch of one or two beats
   passes; days out of range, a malformed kind, prose around the JSON,
   an empty or oversized batch, a blank narration, an unexpected field
   each refuse the **whole batch** (诚实不造假 — no partial adoption,
   zero beats); the provider's fault word passes through verbatim (the
   orchestrator's quiet arm reads ``not-configured``) and a raising
   provider dies as a value;
3. **the generated step** — the beats land in the chronicle
   (``source = world_narrator``, empty effects, the event id derived
   from the anchor run and the triggering turn), one ``PENDING`` reveal
   per beat stamped with its own event's moment, the virtual calendar
   advancing within the batch by each beat's generated days (落笔在跨度
   之末) while the pool-derived story-day sum honestly stays put;
4. **the quiet arms and the winch** — no provider and ``not-configured``
   are the world's honest silence (zero events, zero reveals, zero run
   rows — **never a fallback to the retired pool**), a replayed letter
   lands as the store's own no-ops (same ids, same shapes), the next
   letter resumes the same anchor run (it is never terminalized), and
   the prompt reads only the recent chronicle slice.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import (
    NARRATOR_SOURCE,
    RECENT_CHRONICLE_LIMIT,
    GeneratedBeat,
    WorldNarrator,
    build_narrator_prompt,
)
from elc.world.package import (
    WORLD_PACKAGE_VERSION,
    CastMember,
    SupplyDeclaration,
    WorldPackage,
    story_days_of,
    world_date_of,
)
from elc.world.store import SqliteWorldStore, WorldRevealItem
from elc.world.types import WorldEvent

NOW = "2026-10-06T00:00:00+00:00"
WORLD = "world-main"
CALENDAR_START = "2025-09-14"

LETTER = (
    "Dear Berrymoor,\n"
    "The lighthouse keeper is my uncle — please look in on him.\n"
    "- Ada"
)

BEATS_ONE = json.dumps(
    {
        "beats": [
            {
                "kind": "lamp-relit",
                "narration": "The lamp burned all night.",
                "days": 1,
            }
        ]
    }
)
BEATS_TWO = json.dumps(
    {
        "beats": [
            {
                "kind": "quiet-morning",
                "narration": "The harbour kept its silence.",
                "days": 0,
            },
            {
                "kind": "keeper-visitor",
                "narration": "Ada's letter reached the keeper.",
                "days": 2,
            },
        ]
    }
)


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection with the production
    foreign-keys-ON profile (the w13 fixture shape)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _package(world_id: str = WORLD) -> WorldPackage:
    """One minimal package: the bible's three sections and an empty
    pool (the pool is retired — the generated step reads no span from
    it, which is exactly the honest calendar law below pins)."""

    return WorldPackage(
        world_id=world_id,
        name="Calendar",
        version=WORLD_PACKAGE_VERSION,
        calendar_start=CALENDAR_START,
        setting=(
            "Calendar is a small harbour town on a cold coast.",
            "The boats come in with the morning tide.",
        ),
        cast=(CastMember(persona_id="persona-nell", name="Nell Alder"),),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="declared-not-consumed"),
    )


def _seed_world(store: SqliteWorldStore, world_id: str = WORLD) -> None:
    assert store.create_world(world_id, "Calendar", None, NOW).value is not None


class _ScriptedNarrator:
    """A provider double: scripted outputs, one per call (the last
    repeats), and the prompt texts it saw — the composition pins'
    reading instrument."""

    def __init__(self, *outputs: ProviderOutput | BaseException) -> None:
        self._outputs = outputs
        self._cursor = 0
        self.prompts: list[str] = []

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        entry = self._outputs[min(self._cursor, len(self._outputs) - 1)]
        self._cursor += 1
        if isinstance(entry, BaseException):
            raise entry
        return entry


def _beats(*beats: dict[str, object]) -> str:
    return json.dumps({"beats": list(beats)})


def _beat(
    kind: str = "lamp-relit",
    narration: str = "The lamp burned all night.",
    days: object = 1,
) -> dict[str, object]:
    return {"kind": kind, "narration": narration, "days": days}


# ---------------------------------------------------------------------------
# 1 — the prompt
# ---------------------------------------------------------------------------


def test_the_prompt_carries_no_letter_at_all() -> None:
    """WR-4 判决面（用户第三次定向，DEC-…58）：**信永不进入世界层**——
    prompt 零信文（负控：构造含独特标记的信文本，prompt 中不得出现任何
    标记行）；正控：prompt 带世界自主指令（the world moves on its own —
    it does not react to any correspondence）。spec §4.1/走向条的双层
    律：信 = 发条（机械触发），用户对世界的影响 = 走向通道（M2）。"""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
    )
    for line in LETTER.splitlines():
        assert line not in prompt
    assert "The letter ==" not in prompt
    assert (
        "It does not react to any correspondence" in prompt
    )


def test_the_prompt_carries_the_world_bible() -> None:
    """The bible's three parts are present: the setting prose in full,
    the cast on one line, the whole lore fact set — and an empty lore
    set says so honestly instead of inventing one."""

    prompt = build_narrator_prompt(
        _package(),
        (("fog_lifted", "The fog lifted by noon."), ("boats_in", "The boats are in.")),
        (),
        "zh",
    )
    assert "Calendar is a small harbour town on a cold coast." in prompt
    assert "The boats come in with the morning tide." in prompt
    assert "Cast: Nell Alder" in prompt
    assert "- fog_lifted: The fog lifted by noon." in prompt
    assert "- boats_in: The boats are in." in prompt
    quiet = build_narrator_prompt(_package(), (), (), "zh")
    assert "(Nothing is settled yet.)" in quiet


def test_the_prompt_carries_the_recent_chronicle_old_to_new() -> None:
    """The story's immediate past rides in the caller's order — oldest
    first, the novel's own direction — and an empty chronicle answers
    the honest beginning line."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        ("The fog came in.", "The fog lifted by noon."),
        "zh",
    )
    fog = prompt.index("The fog came in.")
    lifted = prompt.index("The fog lifted by noon.")
    assert fog < lifted
    empty = build_narrator_prompt(_package(), (), (), "zh")
    assert "(The chronicle is empty" in empty


def test_the_prompt_speaks_the_interface_language() -> None:
    """The interface language picks the narration language: ``zh`` asks
    for Chinese, ``en`` for English, and anything else refuses the
    prompt build naming the two words."""

    zh = build_narrator_prompt(_package(), (), (), "zh")
    en = build_narrator_prompt(_package(), (), (), "en")
    assert "Chinese" in zh and "中文" in zh
    assert "English" in en
    with pytest.raises(ValueError):
        build_narrator_prompt(_package(), (), (), "fr")


# ---------------------------------------------------------------------------
# 2 — the strict parse (the whole batch, never a part)
# ---------------------------------------------------------------------------


def test_a_well_formed_batch_parses() -> None:
    """One or two beats, exactly shaped, pass: the GeneratedBeat carries
    the kind, the narration and the span the model wrote."""

    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=BEATS_ONE)))
    parsed = narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(parsed, Ok)
    # wr-10（DEC-OPI-c73dbff3…64）：返回形扩 = (beats, directions) 二元组
    # ——沉浸形（无 directions 键）候选恒空。
    assert parsed.value[0] == (
        GeneratedBeat(
            kind="lamp-relit",
            narration="The lamp burned all night.",
            days=1,
        ),
    )
    assert parsed.value[1] == ()
    two = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=BEATS_TWO)))
    parsed_two = two.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="en",
    )
    assert isinstance(parsed_two, Ok)
    assert [beat.days for beat in parsed_two.value[0]] == [0, 2]


def _generate_refused(text: str) -> Err[None]:
    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=text)))
    parsed = narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(parsed, Err), text
    assert parsed.error.message.startswith("narrator refused:")
    return parsed


def test_days_out_of_range_refuses_the_whole_batch() -> None:
    """A span outside 0-2 — three days, a negative, a float — refuses
    the whole batch: no beat of it is adopted."""

    for days in (3, -1, 1.5):
        text = _beats(
            _beat(days=1),
            _beat(kind="second-beat", narration="The tide turned.", days=days),
        )
        assert isinstance(_generate_refused(text), Err)


def test_a_malformed_kind_refuses_the_whole_batch() -> None:
    """The kind slug's shape holds: uppercase, underscores, a 33-character
    and an empty kind each refuse the whole batch — riding a **mixed**
    batch (one well-formed beat beside the malformed one), because the
    law is no partial adoption, never a salvage of the usable half."""

    for kind in ("Lamp-Relit", "lamp_relit", "a" * 33, ""):
        text = _beats(
            _beat(kind="a-good-beat", narration="The tide turned."),
            _beat(kind=kind),
        )
        assert isinstance(_generate_refused(text), Err)
    # The boundary holds the other way too: 32 characters is a slug.
    ok = WorldNarrator(
        _ScriptedNarrator(ProviderOutput(text=_beats(_beat(kind="a" * 32))))
    )
    parsed = ok.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(parsed, Ok)


def test_prose_around_the_json_refuses_the_whole_batch() -> None:
    """不猜: prose before or after the JSON object — a polite preamble,
    a closing line, markdown fences — refuses the whole batch."""

    for text in (
        f"Here are the beats:\n{BEATS_ONE}",
        f"{BEATS_ONE}\nI hope this helps!",
        f"```json\n{BEATS_ONE}\n```",
    ):
        assert isinstance(_generate_refused(text), Err)


def test_an_empty_or_oversized_batch_refuses_the_whole() -> None:
    """The rhythm law is exactly one or two beats: an empty batch (the
    model declining to write) and a three-beat batch each refuse the
    whole answer."""

    assert isinstance(_generate_refused('{"beats": []}'), Err)
    assert isinstance(
        _generate_refused(
            _beats(
                _beat(kind="first-beat"),
                _beat(kind="second-beat", narration="The tide turned."),
                _beat(kind="third-beat", narration="The lamps went out."),
            )
        ),
        Err,
    )


def test_a_blank_narration_refuses_the_whole() -> None:
    """A blank narration — empty or whitespace — refuses the whole
    batch (mixed, for the same no-partial-adoption law): the world
    never lands an empty sentence, and never keeps the good beat
    beside one."""

    for narration in ("", "   \n  "):
        text = _beats(
            _beat(kind="a-good-beat", narration="The tide turned."),
            _beat(narration=narration),
        )
        assert isinstance(_generate_refused(text), Err)


def test_an_unexpected_field_refuses_the_whole() -> None:
    """The beat object carries exactly ``kind`` / ``narration`` /
    ``days``: an extra field (the model adding its own commentary key)
    refuses the whole batch."""

    extra = _beat()
    extra["mood"] = "wistful"
    assert isinstance(_generate_refused(_beats(extra)), Err)
    assert isinstance(_generate_refused('{"beats": [], "mood": "calm"}'), Err)


def test_the_provider_fault_word_passes_through() -> None:
    """The provider's own fault word rides the Err message verbatim —
    the passthrough the orchestrator's quiet arm matches ``not-
    configured`` on — and a provider that raises dies at this boundary
    as a value (``DEPENDENCY_UNAVAILABLE``), never an exception out."""

    narrator = WorldNarrator(
        _ScriptedNarrator(ProviderOutput(text=None, error="not-configured"))
    )
    parsed = narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(parsed, Err)
    assert parsed.error.message == "not-configured"
    assert parsed.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    boom = WorldNarrator(_ScriptedNarrator(RuntimeError("socket dead")))
    raised = boom.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(raised, Err)
    assert raised.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert "socket dead" in raised.error.message


# ---------------------------------------------------------------------------
# 3 — the generated step
# ---------------------------------------------------------------------------


def test_generated_beats_land_in_the_chronicle_and_the_queue(
    store: SqliteWorldStore,
) -> None:
    """The generated step's durable half: each beat lands as a chronicle
    event (``source = world_narrator``, empty effects, the id derived
    from the anchor run and the triggering turn), and each event leaves
    exactly one ``PENDING`` reveal stamped with its own event's moment
    (the world's own byline — the narrator signs nothing)."""

    _seed_world(store)
    provider = _ScriptedNarrator(ProviderOutput(text=BEATS_TWO))
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        provider,
        "turn-wr2-1",
        NOW,
    )
    assert isinstance(stepped, Ok)
    events = store.chronicle_of(WORLD).value
    assert [event.kind for event in events] == ["quiet-morning", "keeper-visitor"]
    assert all(event.source == NARRATOR_SOURCE for event in events)
    assert all(event.effects == () for event in events)
    assert [str(event.event_id) for event in events] == [
        "run-main-0000:turn-wr2-1:0",
        "run-main-0000:turn-wr2-1:1",
    ]
    assert [event.occurred_at for event in events] == [
        CALENDAR_START,
        (date.fromisoformat(CALENDAR_START) + timedelta(days=2)).isoformat(),
    ]
    rows = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT item_id, source_event_id, actor_id, status, revealed_at,"
        " created_at FROM world_reveal_item ORDER BY item_id ASC"
    ).fetchall()
    assert len(rows) == 2
    for row, event in zip(rows, events):
        assert str(row[0]) == f"{event.event_id}:reveal"
        assert str(row[1]) == str(event.event_id)
        assert row[2] is None
        assert str(row[3]) == "PENDING"
        assert row[4] is None
        assert str(row[5]) == str(event.occurred_at)
    runs = store.list_runs(WORLD)
    assert len(runs) == 1
    assert runs[0].trigger_turn_id == "turn-wr2-1"
    assert runs[0].seed == 0


def test_the_generated_calendar_advances_within_the_batch(
    store: SqliteWorldStore,
) -> None:
    """落笔在跨度之末, the generated span in the pool's old seat: each
    beat advances the story by its own days and stamps at its end —
    spans 1 and 2 land two dates inside one batch (S+1, S+3), and a
    same-day beat (span 0) stamps the base day itself. WR-2 处置：基 =
    编年史最远盖章日——第二封信从第一封的 S+3 续写（跨度 0 盖当日），
    世界今天随之推进；池键日和诚实不动（生成 kind 是故事自己的）。"""

    _seed_world(store)
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(kind="one-day", narration="The tide turned.", days=1),
                _beat(kind="two-days", narration="The fog stayed in.", days=2),
            ),
        ),
        ProviderOutput(
            text=_beats(
                _beat(kind="same-day", narration="A quiet hour.", days=0),
                _beat(kind="same-evening", narration="The lamps went out.", days=0),
            ),
        ),
    )
    first = run_generated_step(
        store, WORLD, _package(), provider, "turn-cal-1", NOW
    )
    assert isinstance(first, Ok)
    assert [str(event.occurred_at) for event in first.value] == [
        (date.fromisoformat(CALENDAR_START) + timedelta(days=1)).isoformat(),
        (date.fromisoformat(CALENDAR_START) + timedelta(days=3)).isoformat(),
    ]
    second = run_generated_step(
        store, WORLD, _package(), provider, "turn-cal-2", NOW
    )
    assert isinstance(second, Ok)
    # WR-2 处置（评审 MEDIUM）：基 = 编年史最远盖章日（story_elapsed_days_of）
    # —— 第二封信的 beats 落在第一封之后（S+3，跨度 0 盖当日本身），
    # 时间单调不倒退；旧基（池键日和恒零）曾把每封信拉回 day zero。
    assert [str(event.occurred_at) for event in second.value] == [
        (date.fromisoformat(CALENDAR_START) + timedelta(days=3)).isoformat(),
        (date.fromisoformat(CALENDAR_START) + timedelta(days=3)).isoformat(),
    ]
    # The world's today follows the same furthest stamp — it advances
    # with the generated story (the pool-keyed sum honestly stays at
    # zero: generated kinds are the story's own, not the pool's).
    assert story_days_of(_package(), store, WORLD) == 0
    assert world_date_of(_package(), store, WORLD) == (
        date.fromisoformat(CALENDAR_START) + timedelta(days=3)
    ).isoformat()


def test_the_story_time_never_runs_backward_across_letters(
    store: SqliteWorldStore,
) -> None:
    """WR-2 处置（评审 MEDIUM 的量化形态）：故事时间跨信单调——第一封
    盖 S+2（跨度 2），第二封盖 S+3（跨度 1），后信永远落在先信之后；
    旧基下第二封会盖 S+1，时间倒退（评审探针实证的缺陷形态）。"""

    _seed_world(store)
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(kind="long-span", narration="The fair stayed.", days=2),
            ),
        ),
        ProviderOutput(
            text=_beats(
                _beat(kind="short-span", narration="The fair left.", days=1),
            ),
        ),
    )
    first = run_generated_step(
        store, WORLD, _package(), provider, "turn-mono-1", NOW
    )
    assert isinstance(first, Ok)
    assert [str(event.occurred_at) for event in first.value] == [
        (date.fromisoformat(CALENDAR_START) + timedelta(days=2)).isoformat(),
    ]
    second = run_generated_step(
        store, WORLD, _package(), provider, "turn-mono-2", NOW
    )
    assert isinstance(second, Ok)
    assert [str(event.occurred_at) for event in second.value] == [
        (date.fromisoformat(CALENDAR_START) + timedelta(days=3)).isoformat(),
    ]
    stamps = [
        str(event.occurred_at)
        for event in store.chronicle_of(WORLD).value
    ]
    assert stamps == sorted(stamps)


def test_a_same_shape_replay_of_enqueue_reveals_is_a_no_op(
    store: SqliteWorldStore,
) -> None:
    """WR-2 处置（评审 LOW-1）：enqueue_reveals 同形重放 = Ok 且行数不变
    ——预存缺陷（预读臂 continue 不剔除插入集，重插 UNIQUE 崩）当刀修；
    docstring 的「nothing is re-inserted」句自此为真。"""

    _seed_world(store)
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(kind="replay-proof", narration="Once is enough.", days=1),
            ),
        ),
    )
    stepped = run_generated_step(
        store, WORLD, _package(), provider, "turn-replay-1", NOW
    )
    assert isinstance(stepped, Ok)
    items = tuple(
        WorldRevealItem(
            item_id=f"{event.event_id}:reveal",
            world_id=WORLD,
            source_event_id=event.event_id,
            actor_id=None,
            status="PENDING",
            revealed_at=None,
            created_at=event.occurred_at,
        )
        for event in stepped.value
    )
    before = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT COUNT(*) FROM world_reveal_item"
    ).fetchone()[0]
    replayed = store.enqueue_reveals(items)
    assert isinstance(replayed, Ok)
    after = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT COUNT(*) FROM world_reveal_item"
    ).fetchone()[0]
    assert before == after


# ---------------------------------------------------------------------------
# 4 — the quiet arms and the winch
# ---------------------------------------------------------------------------


def test_no_provider_and_not_configured_are_the_quiet_arms(
    store: SqliteWorldStore,
) -> None:
    """No provider and a ``not-configured`` provider are the world's
    honest silence: zero events, zero reveals, zero run rows — and
    **never a fallback to the retired pool** (there is no pool call in
    the step to fall back to; the pin is the empty durable state)."""

    _seed_world(store)
    quiet = run_generated_step(
        store, WORLD, _package(), None, "turn-quiet", NOW
    )
    assert isinstance(quiet, Ok)
    assert quiet.value == ()
    bare = _ScriptedNarrator(ProviderOutput(text=None, error="not-configured"))
    unconfigured = run_generated_step(
        store, WORLD, _package(), bare, "turn-bare", NOW
    )
    assert isinstance(unconfigured, Ok)
    assert unconfigured.value == ()
    assert store.chronicle_of(WORLD).value == ()
    assert store.list_runs(WORLD) == ()
    assert store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT COUNT(*) FROM world_reveal_item"
    ).fetchone()[0] == 0
    # The no-provider arm never dialed; the not-configured arm dialed
    # exactly once and went quiet on the provider's own fault word.
    assert len(bare.prompts) == 1


def test_a_replayed_letter_lands_as_no_ops(store: SqliteWorldStore) -> None:
    """同参重跑 = 编年史/揭示不变: the same letter, the same turn id and
    the same beats re-derive the same event ids; the store answers its
    idempotent no-ops and nothing grows (the anchor run is resumed, not
    re-wound — the default step never terminalizes its run; the C1-aR
    v2 terminal arm is the caller's explicit opt-in and a replayed
    no-op touches no run row)."""

    _seed_world(store)
    provider = _ScriptedNarrator(
        ProviderOutput(text=BEATS_TWO), ProviderOutput(text=BEATS_TWO)
    )
    first = run_generated_step(
        store, WORLD, _package(), provider, "turn-wr2-again", NOW
    )
    assert isinstance(first, Ok)
    before_events = store.chronicle_of(WORLD).value
    before_items = store._conn.execute(  # noqa: SLF001 — the test's own read
        "SELECT item_id, status, created_at FROM world_reveal_item"
        " ORDER BY item_id ASC"
    ).fetchall()
    replay = run_generated_step(
        store, WORLD, _package(), provider, "turn-wr2-again", NOW
    )
    assert isinstance(replay, Ok)
    assert store.chronicle_of(WORLD).value == before_events
    assert (
        store._conn.execute(  # noqa: SLF001 — the test's own read
            "SELECT item_id, status, created_at FROM world_reveal_item"
            " ORDER BY item_id ASC"
        ).fetchall()
        == before_items
    )
    assert len(store.list_runs(WORLD)) == 1


def test_the_next_letter_resumes_the_anchor_run(
    store: SqliteWorldStore,
) -> None:
    """The second letter resumes the same anchor run (never a second
    winch, never a terminalized run): its beats carry their own turn's
    id in the event ids, the run count stays one, and the run row sits
    at its checkpoint — the anchor the next letter will resume."""

    _seed_world(store)
    provider = _ScriptedNarrator(
        ProviderOutput(text=BEATS_TWO),
        ProviderOutput(text=BEATS_ONE),
    )
    first = run_generated_step(
        store, WORLD, _package(), provider, "turn-first", NOW
    )
    assert isinstance(first, Ok)
    second = run_generated_step(
        store,
        WORLD,
        _package(),
        provider,
        "turn-second",
        NOW,
    )
    assert isinstance(second, Ok)
    runs = store.list_runs(WORLD)
    assert len(runs) == 1
    assert runs[0].status.value == "AT_CHECKPOINT"
    events = store.chronicle_of(WORLD).value
    assert len(events) == 3
    assert all(str(event.event_id).startswith("run-main-0000:") for event in events)
    assert sum(1 for event in events if ":turn-first:" in str(event.event_id)) == 2
    assert sum(1 for event in events if ":turn-second:" in str(event.event_id)) == 1


def test_the_prompt_reads_only_the_recent_chronicle(
    store: SqliteWorldStore,
) -> None:
    """The prompt carries the story's immediate past, not the whole
    chronicle: only the last eight narrations ride, oldest first (the
    slice is the step's own reading discipline)."""

    _seed_world(store)
    for index in range(10):
        written = store.record_event(
            WorldEvent(
                event_id=f"seed:{index}",
                world_id=WORLD,
                kind=f"seed-kind-{index}",
                narration=f"The past event number {index}.",
                effects=(),
                occurred_at=NOW,
                source="test",
            )
        )
        assert isinstance(written, Ok)
    provider = _ScriptedNarrator(ProviderOutput(text=BEATS_ONE))
    stepped = run_generated_step(
        store, WORLD, _package(), provider, "turn-slice", NOW
    )
    assert isinstance(stepped, Ok)
    prompt = provider.prompts[0]
    # The recent slice: the last eight narrations, oldest first.
    assert f"The past event number {10 - RECENT_CHRONICLE_LIMIT}." in prompt
    assert "The past event number 9." in prompt
    assert "The past event number 1." not in prompt
    assert "The past event number 0." not in prompt
    first = prompt.index("The past event number 2.")
    last = prompt.index("The past event number 9.")
    assert first < last
