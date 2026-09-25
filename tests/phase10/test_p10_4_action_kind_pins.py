"""P10-4 交付 D —— F4 收口：类 6 / 类 11 的 ACTION kind 正向断言。

F4（p10-1 评审登记，p10-3 交接里仍在册）：A 半 13 类里 `RECOVERY_KIND_ACTION` 的正向
断言只落 **2 处**（类 5 的 `_kinds`/`_words(plan, ACTION)` 与末条诚实钉的
`set(_kinds(injected, ACTION))`），而类 6（`CP2-crash-moment-opening`）与类 11
（`terminal-resume-fail`）的世界里**存在同形 action 行**
（`generation_action_intent`：`status='READY_TO_DELIVER'`、`owner_epoch=旧 epoch`）
却从未对它断言。本文件用 A 半的**公开构造路径**（导入的 `World` +
`World.coordinator/restart/scan` + `Refusing` 外壳 + A 半自己的 helper）重建这两类的
残件形状，只补 ACTION kind 的**正向**面（两类的其余断言在 A 半，**A 半文件一字未动**）：

- 两类的 ACTION **必然出现**：该行恰满足 p10-0 的 residue criterion
  （`owner_epoch != current` ∧ `status != 'TERMINAL'`，`runtime/recovery.py` 的
  `GenerationActionRecoverySource` 契约文），且扫描对 ACTION 只有一个词
  （`RECOVERY_DISPOSITION_RESUME_ACTION`）——所以「具名 + 词」是它的全部正面事实。
  类 6 里 MOMENT/LOCK 与它同现（两个事实两个 apply 面），类 11 里 MOMENT 已终态 ⇒
  计划只剩 TURN + ACTION ——这正是「同形 action 在两种窗口里都被具名」。
- 两类的 ACTION **不被任何线消费**：`run_startup_recovery` 自己的计划里 ACTION 缺席
  （它只带 TURN + LOCK，p10-0 R5），且 action 行在执行后**逐字不动**——
  `_close_residual_turns` 只**记录** `action_status`（`TurnRecoveryClosure`），从不推进
  行动；再扫一次仍具名它（durable 事实，不是「会被重入取走」的承诺）。

为什么这里要重建而不是改 A 半：A 半 13 类已盖过章，其 2 处 ACTION 断言的**存在**是
F4 的事实来源；改它会动已盖章的钉，重建则把同一个残件形状再走一遍公开路径、只加正面
断言（多构造一遍世界，换来 ACTION kind 在「moment 开而未交 / moment 已闭但 turn 未收」
两个窗口里的独立证据）。纪律：真库真面、零 `_seed()` 零 fixture 供给、外壳只有
`Refusing`（A 半导入，不复制）；零迁移；未触碰 `migrations/`、`docs/`、
`behavioral_baselines/`、`tests/architecture/`、`tests/conftest.py`、`registry.py`、
`tests/phase9/`。
"""

from __future__ import annotations

import pytest

from elc.platform.types import Err, Ok
from elc.runtime.recovery import (
    RECOVERY_DISPOSITION_RESUME_ACTION,
    RECOVERY_KIND_ACTION,
)
from elc.teaching.store import MomentTransition
from elc.teaching.types import AbortReason, MomentState
from tests.phase3.conftest import CONV, RECEIVED_AT
from tests.phase10.test_p10_1_failure_scenarios_a import (
    Refusing,
    World,
    _action_row,
    _counts,
    _kinds,
    _moment_row,
    _persona,
    _plan_ids,
    _teaching_request,
    _turn_row,
    _words,
)
from tests.phase10.test_p10_2_failure_scenarios_b import (  # noqa: F401  (fixture)
    world as p10_2_world,
)


@pytest.fixture()
def world(request: pytest.FixtureRequest) -> World:
    """The A-half world fixture (p10-2's, asked for by name — one world builder
    for the whole phase, imported rather than copied; the p10-3 precedent)."""

    return request.getfixturevalue("p10_2_world")


def test_cp2_crash_moment_opening_names_the_action_and_leaves_it_where_it_stopped(
    world: World,
) -> None:
    """类 6 重建（`CP2-crash-moment-opening`）：CP2 已提交 moment（`OPENING` + 锁）
    与 `READY_TO_DELIVER` 的 action，开课投递死在 action 自己的边上。

    ACTION **必然出现**：`owner_epoch=1 != 2` 且 `status='READY_TO_DELIVER'`
    非 `'TERMINAL'` ⇒ 扫描具名它、词为 `RESUME_ACTION_BY_STABLE_ACTION_ID`。
    本测试补 A 半该类缺的正向断言（A 半只断言了 MOMENT/LOCK 两 kind 与 action 的
    状态字），并钉住 p10-0 R5：**没有任何线消费这个 ACTION** —— startup 自己的
    计划里它是空的，`§7` 的 abort walk 只把它「停在哪里」记进
    `TurnRecoveryClosure`。
    """

    db = world.db
    crashed = world.coordinator(
        persona=Refusing(_persona(world.generation), "begin_delivery")
    ).request_teaching(_teaching_request("cm-p10-4-f4-class6"))
    assert isinstance(crashed, Err), crashed
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    action_before = _action_row(db, turn_id)
    assert action_before[1:] == ("READY_TO_DELIVER", 1)  # the residue shape
    assert _moment_row(db)[1] == "OPENING"

    new = world.restart()
    plan = new.scan()
    assert _kinds(plan, RECOVERY_KIND_ACTION) == [action_before[0]]
    assert _words(plan, RECOVERY_KIND_ACTION) == [RECOVERY_DISPOSITION_RESUME_ACTION]

    outcome = new.coordinator().run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.aborted_openings == (_moment_row(db)[0],)
    assert _moment_row(db)[1:3] == ("CLOSED", "DELIVERY_FAILURE")
    assert _turn_row(db, turn_id)[:2] == ("COMPLETED", "NO_ASSISTANT_OUTPUT")

    # the walk records where the action stopped — it never advances it
    assert _action_row(db, turn_id) == action_before
    assert [(str(c.turn_id), c.action_status)
            for c in outcome.value.closed_turns] == [
        (turn_id, "READY_TO_DELIVER")
    ]
    # ... so the durable fact survives the walk: a second scan still names it.
    assert _kinds(new.scan(), RECOVERY_KIND_ACTION) == [action_before[0]]

    # and no line consumes it: the startup line's own plan carries no ACTION item
    assert _plan_ids(outcome.value.plan, RECOVERY_KIND_ACTION) == []
    assert _counts(db, "generation_action_intent") == {
        "generation_action_intent": 1
    }


def test_terminal_resume_fail_names_the_action_after_the_moment_is_already_closed(
    world: World,
) -> None:
    """类 11 重建（`terminal-resume-fail`）：moment 已在死 epoch 里走完
    `_abort_opening` 的同一条公开 walk 到 `CLOSED`（锁已释放），而 turn 仍
    `GENERATING`、action 仍 `READY_TO_DELIVER`。

    ACTION **必然出现**（同一 residue criterion；残件就是「某面死在 moment 关闭与
    turn 收口之间」）；且**计划因此只剩 TURN + ACTION** —— MOMENT 已终态、LOCK 已释放，
    这就是「同形 action 在另一种窗口里仍被具名」的独立证据。A 半该类只断言了 TURN 项，
    本测试补 ACTION 的正向面与「不被消费」面。
    """
    db = world.db
    crashed = world.coordinator(
        persona=Refusing(_persona(world.generation), "begin_delivery")
    ).request_teaching(_teaching_request("cm-p10-4-f4-class11"))
    assert isinstance(crashed, Err), crashed
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    action_before = _action_row(db, turn_id)
    assert action_before[1:] == ("READY_TO_DELIVER", 1)

    # the same public walk `_abort_opening` performs, in the *dead* epoch
    active = world.teaching.get_active_moment(CONV)
    assert isinstance(active, Ok) and active.value is not None
    moment = active.value
    stepped = world.teaching.transition_moment(
        moment.moment_id,
        MomentTransition(
            lifecycle_state=MomentState.ABORTING,
            abort_reason=AbortReason.DELIVERY_FAILURE.value,
        ),
        moment.state_version,
    )
    assert isinstance(stepped, Ok), stepped
    current = stepped.value
    terminal = world.teaching.terminalize_moment(
        current.moment_id, abort_reason=AbortReason.DELIVERY_FAILURE.value
    )
    assert isinstance(terminal, Ok), terminal
    current = terminal.value
    for state_word in (MomentState.RESUMING, MomentState.CLOSED):
        advanced = world.teaching.transition_moment(
            current.moment_id,
            MomentTransition(
                lifecycle_state=state_word,
                closed_at=None if state_word is MomentState.RESUMING else RECEIVED_AT,
            ),
            current.state_version,
        )
        assert isinstance(advanced, Ok), advanced
        current = advanced.value
    assert _moment_row(db)[1:3] == ("CLOSED", "DELIVERY_FAILURE")
    assert _counts(db, "active_teaching_lock") == {"active_teaching_lock": 0}
    assert _turn_row(db, turn_id)[0] == "GENERATING"  # the residue

    new = world.restart()
    plan = new.scan()
    assert _kinds(plan, RECOVERY_KIND_ACTION) == [action_before[0]]
    assert _words(plan, RECOVERY_KIND_ACTION) == [RECOVERY_DISPOSITION_RESUME_ACTION]

    outcome = new.coordinator().run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert _turn_row(db, turn_id)[:2] == ("COMPLETED", "NO_ASSISTANT_OUTPUT")
    assert _action_row(db, turn_id) == action_before  # left where it stopped
    assert _plan_ids(outcome.value.plan, RECOVERY_KIND_ACTION) == []
    assert _kinds(new.scan(), RECOVERY_KIND_ACTION) == [action_before[0]]
