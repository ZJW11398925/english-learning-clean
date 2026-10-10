"""C1-c — the persona reply reads her own cognitive view of the world
(DEC-OPI-b290799a…27, the cut's R1/R2/R3/R5 arms).

wr-12 handed every bound reply the world's whole recent chronicle —
the data layer's omniscience. The design supplement 域一's law is
「数据层全知，认知层分视角」: Nell's view of Berrymoor is not Silas's.
The port's read now filters to the binding actor's cognitive view —
the **public** events (``participants`` empty) plus the events she
**witnessed** (her persona id names the ``participants``; the
namespace is the narrator's cast-id roster's, resolved from the
binding's actor through ``world_actor``), dropping the peopled events
that name only others. The pin groups:

1. **the three filter arms** — witnessed in, public in, others'-only
   out, plus the namespace pin (the join is persona-keyed, never
   actor-id-keyed — the roster's vocabulary, not the binding column's);
2. **the fallback and the refusal** — an actor-less binding reads the
   whole chronicle (the defensive arm the schema's NOT NULL keeps
   unreachable through the store), a binding whose actor row is gone
   is a corruption ``Err``, never the omniscient whole;
3. **order and window** — the merged view stays chronological and the
   window slices **after** the filter (an excluded event never
   occupies a window slot);
4. **the two-actor verdict** — the same world, two conversations bound
   through two actors: each view is her own public + witnessed, the
   other's witnessed events invisible to each (port level, and the
   turn prompt level the view exists for);
5. **the honest empty** — a chronicle every peopled event of which is
   another's resolves to the empty view, nothing fabricated.
"""

from __future__ import annotations

from pathlib import Path

from elc.host import _WorldChroniclePort, open_host
from elc.persona.card_store import CharacterCardRecord, persona_id_for_card
from elc.persona.penpal import PENPAL_CHARACTER_PACKAGE
from elc.persona.types import ProviderOutput
from elc.platform.types import (
    ConversationId,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.world.types import WorldEvent
from elc.world_lore.types import RECENT_WORLD_EVENT_WINDOW
from tests.host.test_w1_web import REPLY
from tests.host.test_wr12_chronicle_view import RecordingProvider, _turn

CONV_NELL = "c1c-conv-nell"
CONV_SILAS = "c1c-conv-silas"
NOW = "2026-10-07T12:00:00+00:00"

SILAS_ACTOR_ID = "actor-berrymoor-silas"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _second_actor(host, world_id: str) -> str:
    """Bind the second actor (Silas) into the builtin world through a
    fresh user card — the cast's one builtin member is Nell, and the
    ``world_actor`` FK needs a real card to speak through. Returns the
    persona id the beats' ``participants`` must spell for him."""

    minted = host.character_cards.mint_user_card_id()
    created = host.character_cards.create(
        CharacterCardRecord(
            character_id=minted,
            persona_id=persona_id_for_card(minted),
            name="Silas Crane",
            identity="the harbour's second ferryman",
            personality="quiet, exacting",
            background="came with the tide",
            speech_style="short sentences",
            values="precision",
            boundaries="none declared",
            opening="",
            scenario="",
            generation_policy=PENPAL_CHARACTER_PACKAGE.generation_policy,
            lore_refs=(),
            revision=1,
            status=PENPAL_CHARACTER_PACKAGE.status,
            is_builtin=False,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    assert isinstance(created, Ok), created
    persona_id = str(created.value.persona_id)
    bound = host.world_store.bind_actor(
        SILAS_ACTOR_ID, world_id, persona_id, NOW
    )
    assert isinstance(bound, Ok), bound
    return persona_id


def _bound_pair(tmp_path: Path):
    """A prep-1-tier host with the builtin world and two conversations
    bound through two actors: Nell (the builtin cast member) and Silas
    (the fresh card). Returns the host, the recording provider, and the
    two actors' persona ids. The host is the caller's to close."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(tmp_path / "app.db", provider=provider)
    for conversation in (CONV_NELL, CONV_SILAS):
        opened = host.open_conversation(ConversationId(conversation))
        assert isinstance(opened, Ok), opened
    world = host.world_store.list_worlds()[0]
    world_id = str(world.world_id)
    nell = host.world_store.actors_of(world_id)[0]
    nell_persona = str(nell.persona_id)
    silas_persona = _second_actor(host, world_id)
    for binding_id, conversation, actor_id in (
        ("wcb-c1c-nell", CONV_NELL, str(nell.actor_id)),
        ("wcb-c1c-silas", CONV_SILAS, SILAS_ACTOR_ID),
    ):
        bound = host.world_store.bind_conversation(
            binding_id, world_id, actor_id, conversation, NOW
        )
        assert isinstance(bound, Ok), bound
    return host, provider, world_id, nell_persona, silas_persona


def _event(
    world_id: str,
    event_id: str,
    narration: str,
    participants: tuple[str, ...],
    index: int,
) -> WorldEvent:
    """One chronicle row with its own moment (the days keep the
    chronicle's durable order unambiguous)."""

    recorded = WorldEvent(
        event_id=event_id,
        world_id=world_id,
        kind="c1c-beat",
        narration=narration,
        effects=(),
        occurred_at=f"0025-04-{10 + index:02d}",
        source="c1c-test",
        participants=participants,
    )
    return recorded


def _record(host, world_id: str, event: WorldEvent) -> None:
    answered = host.world_store.record_event(event)
    assert isinstance(answered, Ok), answered


def _narrations(view) -> list[str]:
    return [entry.narration for entry in view.events]


def _view_of(host, conversation: str):
    port = host.coordinator._world_chronicle  # type: ignore[attr-defined]
    answered = port.resolve_world_chronicle_view(ConversationId(conversation))
    assert isinstance(answered, Ok), answered
    return answered.value


# ---------------------------------------------------------------------------
# 1 — the three filter arms (+ the namespace pin)
# ---------------------------------------------------------------------------


def test_witnessed_events_reach_their_participant(tmp_path: Path) -> None:
    """亲历臂：participants 含我的事件在她的视图里（她的在场她的细节）。"""

    host, _, world_id, nell, _ = _bound_pair(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-witnessed",
                "Nell mended the torn sail.",
                (nell,),
                0,
            ),
        )
        assert _narrations(_view_of(host, CONV_NELL)) == [
            "Nell mended the torn sail."
        ]
    finally:
        host.close()


def test_public_events_reach_every_bound_actor(tmp_path: Path) -> None:
    """公共臂：participants 为空的事件对每个绑定角色可见（镇上公知）。"""

    host, _, world_id, _, _ = _bound_pair(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-public",
                "The harbour clock struck eight.",
                (),
                0,
            ),
        )
        for conversation in (CONV_NELL, CONV_SILAS):
            assert _narrations(_view_of(host, conversation)) == [
                "The harbour clock struck eight."
            ]
    finally:
        host.close()


def test_peopled_events_of_others_stay_out(tmp_path: Path) -> None:
    """排除臂：participants 非空且不含我的事件不出现——同一世界编年史，
    另一角色的事件她不知道（认知边界第一版）。双向验：nell 不见 silas
    的、silas 不见 nell 的。"""

    host, _, world_id, nell, silas = _bound_pair(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-nells",
                "Nell mended the torn sail.",
                (nell,),
                0,
            ),
        )
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-silass",
                "Silas counted the ferry coins.",
                (silas,),
                1,
            ),
        )
        nell_view = _narrations(_view_of(host, CONV_NELL))
        silas_view = _narrations(_view_of(host, CONV_SILAS))
        assert "Silas counted the ferry coins." not in nell_view
        assert "Nell mended the torn sail." not in silas_view
        # Each still sees her/his own.
        assert nell_view == ["Nell mended the torn sail."]
        assert silas_view == ["Silas counted the ferry coins."]
    finally:
        host.close()


def test_the_join_is_persona_keyed_not_actor_id_keyed(
    tmp_path: Path,
) -> None:
    """命名空间钉：``participants`` 的词表是 cast-id roster 教的
    **persona id**（narrator 的 Cast ids 行、C1-b 的 parser 面），不是
    绑定列的 ``actor_id``——拿 actor id 署名的事件不因字串巧合可见，
    拿 persona id 署名的同形事件可见（过滤器经 ``world_actor`` 解析，
    不做裸字串比对）。"""

    host, _, world_id, nell, _ = _bound_pair(tmp_path)
    try:
        actor_id = str(host.world_store.actors_of(world_id)[0].actor_id)
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-actor-tagged",
                "A stranger asked for Nell by her ledger name.",
                (actor_id,),
                0,
            ),
        )
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-persona-tagged",
                "Nell signed the harbour book.",
                (nell,),
                1,
            ),
        )
        view = _narrations(_view_of(host, CONV_NELL))
        assert "A stranger asked for Nell by her ledger name." not in view
        assert "Nell signed the harbour book." in view
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 2 — the fallback and the refusal
# ---------------------------------------------------------------------------


def test_an_actor_less_binding_reads_the_whole_chronicle() -> None:
    """回退臂：绑定行 actor 为 NULL ⇒ 现役全量行为（无视角=全知）——
    silas 署名的事件也在视图里。schema 的 ``actor_id`` NOT NULL 使该
    状态经 store 不可达，此臂是 web 面 binding 读共有的防御姿态，故按
    wr-12 ``_Boom`` 的 stub 先例在单元层钉（脚本化 binding 行 + 脚本化
    编年史）。"""

    events = (
        WorldEvent(
            event_id="we-c1c-fallback-public",
            world_id="world-c1c-stub",
            kind="c1c-beat",
            narration="The tide brought in driftwood.",
            effects=(),
            occurred_at="0025-04-10",
            source="c1c-test",
            participants=(),
        ),
        WorldEvent(
            event_id="we-c1c-fallback-silas",
            world_id="world-c1c-stub",
            kind="c1c-beat",
            narration="Silas counted the ferry coins.",
            effects=(),
            occurred_at="0025-04-11",
            source="c1c-test",
            participants=("persona-someone-else",),
        ),
    )

    class _StubRow:
        def fetchone(self):
            return ("world-c1c-stub", None)

    class _StubConn:
        def execute(self, sql, params=()):
            return _StubRow()

    class _StubWorld:
        def chronicle_of(self, world_id):
            assert world_id == "world-c1c-stub"
            return Ok(events)

    port = _WorldChroniclePort(
        _StubConn(),  # type: ignore[arg-type]
        _StubWorld(),  # type: ignore[arg-type]
    )
    answered = port.resolve_world_chronicle_view(
        ConversationId("c1c-stub-conv")
    )
    assert isinstance(answered, Ok), answered
    assert _narrations(answered.value) == [
        "The tide brought in driftwood.",
        "Silas counted the ferry coins.",
    ]


def test_a_dangling_binding_actor_is_a_refusal_not_omniscience(
    tmp_path: Path,
) -> None:
    """腐坏拒绝臂：绑定行指着一个 world 表不认识的 actor ⇒ 值语义
    ``Err``（VALIDATION_FAILED，点名的腐坏），绝不静默退成全知——
    与 ``chronicle_of`` 对坏列的拒收同一姿势。装配连接的
    ``foreign_keys`` 是 ON（0023 的 connection profile），该状态经 store
    与 FK 双重不可达；故本钉以 pragma 停用 + 直写 UPDATE 在真实库上
    模拟腐坏（store 的写面永远造不出它）。"""

    host, _, world_id, _, _ = _bound_pair(tmp_path)
    try:
        host.db.execute("PRAGMA foreign_keys = OFF")
        host.db.execute(
            "UPDATE world_conversation SET actor_id = 'actor-c1c-ghost'"
            " WHERE conversation_id = ?",
            (CONV_NELL,),
        )
        host.db.commit()
        port = host.coordinator._world_chronicle  # type: ignore[attr-defined]
        answered = port.resolve_world_chronicle_view(ConversationId(CONV_NELL))
        assert isinstance(answered, Err)
        assert answered.error.code is DomainErrorCode.VALIDATION_FAILED
        assert "actor-c1c-ghost" in answered.error.message
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 3 — order and window
# ---------------------------------------------------------------------------


def test_the_merged_view_stays_chronological(tmp_path: Path) -> None:
    """排序臂：公共 + 亲历合并后时间序不破——chronicle 本身有序，过滤
    保序，视图即 kept 子集的原序（新→旧混排不重排）。"""

    host, _, world_id, nell, _ = _bound_pair(tmp_path)
    try:
        plan = (
            ("we-c1c-o1", "The harbour clock struck eight.", (), 0),
            ("we-c1c-o2", "Silas counted the ferry coins.", ("persona-x",), 1),
            ("we-c1c-o3", "Nell mended the torn sail.", (nell,), 2),
            ("we-c1c-o4", "Rain swept the quay at noon.", (), 3),
            ("we-c1c-o5", "Silas sold the second boat.", ("persona-x",), 4),
            ("we-c1c-o6", "Nell lit the harbour lamp.", (nell,), 5),
        )
        for event_id, narration, participants, index in plan:
            _record(
                host,
                world_id,
                _event(world_id, event_id, narration, participants, index),
            )
        assert _narrations(_view_of(host, CONV_NELL)) == [
            "The harbour clock struck eight.",
            "Nell mended the torn sail.",
            "Rain swept the quay at noon.",
            "Nell lit the harbour lamp.",
        ]
    finally:
        host.close()


def test_the_window_slices_after_the_filter(tmp_path: Path) -> None:
    """窗口臂：过滤先于截窗——被排除事件不占窗口位。七条编年史、nell
    可见恰五条、两条 silas 专属插在原始末五条里：先过滤后截窗 ⇒ 视图
    恰为她可见的五条全部（含最旧一条）；先截窗后过滤会只剩四条且丢最
    旧——此钉双向咬死次序。"""

    host, _, world_id, nell, _ = _bound_pair(tmp_path)
    try:
        plan = (
            ("we-c1c-w1", "The harbour clock struck eight.", (), 0),
            ("we-c1c-w2", "Silas counted the ferry coins.", ("persona-x",), 1),
            ("we-c1c-w3", "Nell mended the torn sail.", (nell,), 2),
            ("we-c1c-w4", "Rain swept the quay at noon.", (), 3),
            ("we-c1c-w5", "Silas sold the second boat.", ("persona-x",), 4),
            ("we-c1c-w6", "Nell lit the harbour lamp.", (nell,), 5),
            ("we-c1c-w7", "The ferry tied up for the night.", (), 6),
        )
        for event_id, narration, participants, index in plan:
            _record(
                host,
                world_id,
                _event(world_id, event_id, narration, participants, index),
            )
        view = _view_of(host, CONV_NELL)
        assert len(view.events) == RECENT_WORLD_EVENT_WINDOW
        narrations = _narrations(view)
        assert narrations == [
            "The harbour clock struck eight.",
            "Nell mended the torn sail.",
            "Rain swept the quay at noon.",
            "Nell lit the harbour lamp.",
            "The ferry tied up for the night.",
        ]
        assert "Silas counted the ferry coins." not in narrations
        assert "Silas sold the second boat." not in narrations
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 4 — the two-actor verdict
# ---------------------------------------------------------------------------


def test_two_actors_of_one_world_see_different_views(tmp_path: Path) -> None:
    """端到端双视角钉（port 层）：同一世界、两会话各绑不同 actor ⇒
    各自视图不同——Nell 见公共 + 她的亲历 + 共同在场；Silas 见公共 +
    他的亲历 + 共同在场；对方专属事件互不可见。"""

    host, _, world_id, nell, silas = _bound_pair(tmp_path)
    try:
        _record(
            host, world_id,
            _event(world_id, "we-c1c-d0", "The harbour clock struck eight.", (), 0),
        )
        _record(
            host, world_id,
            _event(world_id, "we-c1c-d1", "Nell mended the torn sail.", (nell,), 1),
        )
        _record(
            host, world_id,
            _event(
                world_id,
                "we-c1c-d2",
                "Silas counted the ferry coins.",
                (silas,),
                2,
            ),
        )
        _record(
            host, world_id,
            _event(
                world_id,
                "we-c1c-d3",
                "Nell and Silas argued over the mooring fee.",
                (nell, silas),
                3,
            ),
        )
        nell_view = _narrations(_view_of(host, CONV_NELL))
        silas_view = _narrations(_view_of(host, CONV_SILAS))
        assert nell_view == [
            "The harbour clock struck eight.",
            "Nell mended the torn sail.",
            "Nell and Silas argued over the mooring fee.",
        ]
        assert silas_view == [
            "The harbour clock struck eight.",
            "Silas counted the ferry coins.",
            "Nell and Silas argued over the mooring fee.",
        ]
        assert nell_view != silas_view
    finally:
        host.close()


def test_each_bound_turn_prompt_carries_its_own_view(tmp_path: Path) -> None:
    """端到端双视角钉（turn 层——视图存在的目的）：nell 会话的一轮，
    回信 prompt 带她亲历与公共事件的叙述逐字、不带 silas 专属事件——
    「她的回信内容层知道的是她的世界那一面」。"""

    host, provider, world_id, nell, silas = _bound_pair(tmp_path)
    try:
        _record(
            host, world_id,
            _event(world_id, "we-c1c-t0", "The harbour clock struck eight.", (), 0),
        )
        _record(
            host, world_id,
            _event(world_id, "we-c1c-t1", "Nell mended the torn sail.", (nell,), 1),
        )
        _record(
            host, world_id,
            _event(
                world_id,
                "we-c1c-t2",
                "Silas counted the ferry coins.",
                (silas,),
                2,
            ),
        )
        _turn(host, CONV_NELL, "nell")
        prompt = provider.prompts[-1].prompt_text
        assert "[recent_world_events]" in prompt.splitlines()
        assert "Nell mended the torn sail." in prompt
        assert "The harbour clock struck eight." in prompt
        assert "Silas counted the ferry coins." not in prompt
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 5 — the honest empty
# ---------------------------------------------------------------------------


def test_all_excluded_resolves_to_an_empty_view(tmp_path: Path) -> None:
    """诚实空臂：编年史每条 peopled 事件都属于别人 ⇒ 空视图（「世界已
    解析、她知道的还没发生什么」），不是 None 不是 Err 更不造内容。"""

    host, _, world_id, _, _ = _bound_pair(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-c1c-e1",
                "Silas counted the ferry coins.",
                ("persona-someone-else",),
                0,
            ),
        )
        view = _view_of(host, CONV_NELL)
        assert view.events == ()
    finally:
        host.close()
