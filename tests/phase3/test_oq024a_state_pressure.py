"""OQ-024A 自铸案例集 —— TeachingMoment/Attempt 状态机压力（Phase 3 P3-2）。

VAL-OPI-2babb21e-….11 的验收口径：OQ-024A 16+ state cases 以 executable
scenario fixtures 复现，每个 case 的合法/非法转换判定与 canonical 状态机
一致；本体不可考时以 docs/STATE_MACHINES.md §1–§9 语义自铸并留痕。

一、自铸留痕（本体不可考的裁定与语义权威）
--------------------------------------------------
OQ-024A 本体定位为 P3-2 开工四查必答项，四查结论（TASK-…5ba74efc.24 ④）：
本仓资产只有 docs/IMPLEMENTATION_PLAN.md §9 的「复现 OQ-024A 16+ state
cases」引用、behavioral_baselines/gate/BF-03 的前置提及、golden/
GOLDEN_SCENARIOS.md 的框架文档（无案例内容），旧仓 D:/测试1 检索无文件。
裁定：本体不可考 → 按 VAL-…11 预案自铸。**语义权威 = docs/STATE_MACHINES.md
§1–§9 全文**：
§1 十态生命周期与主流程图/分支表、§2 Moment 规则（单一 FocusTarget /
Closed 不许 reopen / future teaching 用新 moment_id / SWITCH_TARGET 先关
后同 turn 新 cycle）、§3 ladder 双单调（phase 与 support）+ exposure 不得
假装更少、§4 envelope 五步与十一词 control_intent、§5 五值评估、
§6 completion 七词、§7 abort 十四词、§8 limits 与 continuation
（user-requested 不绕 hard cap）、§9 ACTIVE_MOMENT authorization。
本模块的每个 case 的「期望终态/期望拒绝」都以这些章节为唯一依据；被测
对象 = P3-1A+P3-1B 已交付的 TeachingMoment/Attempt 编排链（zero schema
变更，migrations 不动）。

二、覆盖矩阵（case_id ↔ 任务书 a–f 与 SM 章节）
--------------------------------------------------
a) §1 合法转换逐边 ≥1 case：
   sm1-authorized-to-opening          AUTHORIZED→OPENING（CP2 提交值；永不落行）
   sm1-opening-to-awaiting-user        OPENING→AWAITING_USER（§13.1 谓词）
   sm1-awaiting-user-to-evaluating     AWAITING_USER→EVALUATING
   sm1-evaluating-to-deciding          EVALUATING→DECIDING_NEXT_ACTION
   sm1-deciding-to-awaiting-user-hint  DECIDING→AWAITING_USER（HINT）
   sm1-deciding-to-awaiting-user-retry DECIDING→AWAITING_USER（RETRY）
   sm1-deciding-to-completing-success-unsupported / -supported
                                       DECIDING→COMPLETING（SUCCESS 双支持度）
   sm1-deciding-to-completing-closing-reveal
                                       DECIDING→COMPLETING（REVEAL 的收尾臂）
   sm1-deciding-to-awaiting-user-requested-reveal
                                       DECIDING→AWAITING_USER（REVEAL 的保持臂）
   sm1-deciding-to-awaiting-user-explanation（EXPLAIN 的 continuation 读法）
   sm1-deciding-to-aborting-switch / -skip / -reject / -topic-shift
                                       DECIDING→ABORTING（SWITCH/SKIP/SHIFT）
   sm1-completing-to-terminal          COMPLETING→TEACHING_TERMINAL（+锁同事务释放）
   sm1-aborting-to-terminal            ABORTING→TEACHING_TERMINAL
   sm1-terminal-to-resuming-to-closed  TEACHING_TERMINAL→RESUMING→CLOSED
   sm1-terminal-no-resume-arm          TEACHING_TERMINAL→CLOSED（SM §1:54 no-resume 臂）
b) 非法转换拒：
   sm1-closed-is-final                 CLOSED 后任何转换（含 reopen）+ 新请求=新 moment
   sm1-closed-only-from-the-tail       未终态直 CLOSED 拒（不留「CLOSED+持锁」）
   sm1-terminal-tail-is-one-way        TEACHING_TERMINAL 回退非 RESUMING/CLOSED 拒；
                                       非终态直 CLOSED/非 COMPLETING·ABORTING 拒
   sm3-ladder-refusals                 ladder 回退双单调拒（phase 与 support）+ 天花板
   sm3-reconcile-never-lowers          对账不得降低已落梯级
   sm8-limits-matrix                   limits 超限拒新动作但收尾豁免（纯矩阵）
   sm1-awaiting-user-no-attempt-jump   AWAITING_USER 无 attempt 直跳 EVALUATING 后果
c) 词汇全覆盖：
   sm6-completion-outcomes-partition   §6 七词（5 生产路径 + 2 durable-only 留痕）
   sm7-abort-reasons-partition         §7 十四词（9 编排面 + 2 映射面 + 3 不可构造留痕）
d) SWITCH_TARGET 同 turn cycle 链：
   sm2-switch-target-cycle-chain       多目标连切 cycle_index 递增链（0,1,2…）
e) continuation 面：
   sm12-continuation-basis             ACTIVE_MOMENT authorization + AUTO_CONTINUE 拒
   sm9-own-evidence-keeps-continuation 本 Moment 新 Evidence 不废自身 continuation
f) attempt 编排链顺序稳定性：
   sm4-attempt-and-control-coexist     §4 非互斥（attempt 与控制意图同存）
   sm17-attempt-chain-under-pressure   压力序列下 attempt→evaluation→gate→action→落梯
另有 sm1-… 的 store 级边界 case 与上述共同构成 32 个 case（≥16 达标；数量
服从覆盖矩阵，非凑数）。

三、与 P3-1B 11 条崩溃窗口测试的对账（不重复造）
--------------------------------------------------
tests/phase3/test_teaching_crash_windows.py 的 11 条 = F1×4（Gate 回放+梯级
对账+交付失败不推梯级）+ F2×3（同 action_id 续做+孤儿锁回收+活锁不误收）
+ F3×2（(moment,user_turn) 幂等+新 turn 新 attempt）+ F5×2（顺序见证）。
本案例集**复用**它们的注入夹具（FailOnceGenerationStore /
FailingEvaluationController / TracingTeachingController /
TracingGenerationStore），不重写其断言；增量在于**转换矩阵与词表**：
  已覆盖（不重复）：两段式交付与梯级落点、Gate 事实回放、attempt 幂等、
    顺序见证的**单轮**形态；
  本集增量：① §1 十态**逐边**的显式终态快照（含 store 级 COMPLETING/
    ABORTING→TERMINAL 与 TERMINAL→RESUMING→CLOSED 尾链）；② 非法转换
    的三层拒（durable 边界/编排面/纯面）；③ §6 七词与 §7 十四词的**分区
    完备性**断言（不是"试了几个词"）；④ 同 turn cycle_index 的 0,1,2 链；
    ⑤ 多轮压力下的编排链顺序（既有见证只覆盖单轮）；⑥ DELIVERING 槽与
    跨写者冲突由 test_p3_2_carryovers.py 承接（本集不含）。

四、自裁留痕（案例暴露的语义边界）
--------------------------------------------------
1. §1 "REVEAL / EXPLAIN → AWAITING_USER **or** COMPLETING" 的 COMPLETING
   臂：v0 只有 REVEAL 的收尾臂（§8 hard cap 转换）；EXPLAIN 无 COMPLETING
   路径，按 continuation 读法钉死（sm1-deciding-to-awaiting-user-explanation
   以 durable 证据钉死：delivery_kind=EXPLANATION、moment 停在
   AWAITING_USER、completion_outcome 仍为 None）。
2. §6 USER_SATISFIED / NO_FURTHER_VALUE 无生产路径（src 全仓检索只有
   enum 与 migration CHECK）；§7 AMBIGUOUS_EXIT（v0 无 NLU/歧义面）、
   ATTEMPT_LIMIT（§8 硬上限是**转换**成收尾 reveal，从不是 abort）、
   EXPIRED（Local V1 §24.1 禁 TTL/heartbeat，无过期面）三词不可构造。
   五词 + SNAPSHOT_INVALIDATED/PRE_DELIVERY_INVALIDATED（仅
   `closing_reason_for_gate_denial` 映射面可达，continuation facts 里
   learning_snapshot 恒 VALID、无 PreDeliveryGuard）在词表 case 中以
   分区断言 + 原因码留痕，不伪装成已复现。
3. §1 图在 durable 边界的守卫范围（本刀实测 + 最小收紧）：generic CAS
   face（transition_moment）守卫 CLOSED（既有）与 §1 **尾链**——
   TEACHING_TERMINAL 的合法目标 = {RESUMING（resume 臂），CLOSED
   （no-resume 臂，SM §1:54）}、RESUMING 只回 CLOSED、CLOSED 只接受来自
   该尾链两态的转换（本刀最小增量 `_terminal_tail_refusal`，与 CLOSED 拒
   同构、无 schema 变更；任务书 ①b 点名的「TEACHING_TERMINAL 回退非
   RESUMING」拒由此获得实质）。**中间态回退**（如 AWAITING_USER→
   AUTHORIZED、OPENING→AUTHORIZED）不在 durable 边界守卫：§1 图由域面
   /协调者承担，本集不制造不可达的回退断言，也不继续加宽 store 语义。

红线自查：本文件全部经 Write/Edit 通道落盘；SQL 全字面量+参数绑定；
未触碰 migrations / behavioral_baselines / docs 六 canonical；不越 P3-3 面
（无全链 before/after、无 content runtime、无 Planner/AUTOMATIC）。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from typing import Callable

import pytest

from elc.conversation import SqliteConversationStore
from elc.learning.controller import LearningController
from elc.persona import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db import epoch
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    Err,
    Ok,
    UserTurnId,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
    TeachingTurnResult,
)
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.flow import closing_reason_for_gate_denial
from elc.teaching.gate import (
    ContinuationFacts,
    GateInputError,
    decide_user_requested_continuation,
)
from elc.teaching.ladder import ladder_step_refusal
from elc.teaching.limits import (
    TeachingLimits,
    TeachingLoad,
    continuation_verdict,
)
from elc.teaching.next_action import closing_outcome_for
from elc.teaching.request import TeachingRequest
from elc.teaching.store import (
    CP2OpenRequest,
    MomentTransition,
    SqliteTeachingStore,
)
from elc.teaching.types import (
    ABORT_REASONS,
    COMPLETION_OUTCOMES,
    MomentState,
    TeachingMomentRecord,
)
from tests.phase2.conftest import commit_ok

from .conftest import CONV, make_lease, make_teaching_coordinator
from .target_fixtures import (
    CONTENT_INVALID_PROVIDER_VIEW,
    UNAVAILABLE_TARGET_PROVIDER,
    provider_over,
)
from .test_cp2_atomic_open import _cp2
from .test_teaching_crash_windows import (
    FailingEvaluationController,
    FailOnceGenerationStore,
    TracingGenerationStore,
    TracingTeachingController,
)

REQUESTED_AT = "2026-09-21T15:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"
CANONICAL = "I think it is going to rain."
ALTERNATIVE = "It might rain."
WRONG = "The cat sat on the mat."
SWITCH_TO = "RESOURCE/res-colloc-make-a-decision"


# ---------------------------------------------------------------------------
# the case env harness
# ---------------------------------------------------------------------------


class CaseEnv:
    """One case's world: the phase-3 fixtures plus the flow helpers.

    Every case gets a *fresh* in-memory app.db (the conftest fixtures), so a
    case can drive a whole conversation — several moment lifecycles — and
    read its durable snapshot without leaking into another case.
    """

    def __init__(
        self,
        *,
        db: sqlite3.Connection,
        store: SqliteConversationStore,
        generation_store,
        fence: RuntimeEpochFence,
        learning,
        learning_controller: LearningController,
        decision_cycle_store,
        teaching: TeachingController,
        targets,
    ) -> None:
        self.db = db
        self.store = store
        self.generation_store = generation_store
        self.fence = fence
        self.learning = learning
        self.learning_controller = learning_controller
        self.decision_cycle_store = decision_cycle_store
        self.teaching = teaching
        self.targets = targets

    # -- assembly ------------------------------------------------------------

    def coordinator(
        self,
        *,
        generation=None,
        teaching=None,
        targets=None,
        provider=None,
    ) -> ConversationCoordinator:
        """The P3-1A/P3-1B assembly, with any port replaced for one case."""

        return make_teaching_coordinator(
            self.store,
            self.generation_store if generation is None else generation,
            make_lease(self.fence),
            provider if provider is not None else ScriptedPersonaProvider(),
            self.learning,
            self.decision_cycle_store,
            self.teaching if teaching is None else teaching,
            self.targets if targets is None else targets,
        )

    # -- flows ---------------------------------------------------------------

    def open(
        self, coordinator: ConversationCoordinator, cmid: str
    ) -> TeachingTurnResult:
        result = coordinator.request_teaching(
            TeachingRequest(
                conversation_id=CONV,
                focus_target_id=FOCUS_TARGET,
                client_message_id=ClientMessageId(cmid),
                requested_at=REQUESTED_AT,
            )
        )
        assert isinstance(result, Ok), result
        return result.value

    def reply(
        self,
        coordinator: ConversationCoordinator,
        envelope: TeachingResponseEnvelope,
        cmid: str,
    ):
        return coordinator.respond_to_teaching(
            TeachingReplyRequest(
                conversation_id=CONV,
                envelope=envelope,
                client_message_id=ClientMessageId(cmid),
                requested_at=REQUESTED_AT,
            )
        )

    def reply_ok(
        self,
        coordinator: ConversationCoordinator,
        envelope: TeachingResponseEnvelope,
        cmid: str,
    ):
        result = self.reply(coordinator, envelope, cmid)
        assert isinstance(result, Ok), result
        return result.value

    # -- envelope shorthands -------------------------------------------------

    @staticmethod
    def hint_envelope() -> TeachingResponseEnvelope:
        return TeachingResponseEnvelope(
            control_intent=TeachingControlIntent.ASK_HINT
        )

    @staticmethod
    def control_envelope(
        intent: TeachingControlIntent, **extra
    ) -> TeachingResponseEnvelope:
        return TeachingResponseEnvelope(
            control_intent=intent, attempt_present=False, **extra
        )

    @staticmethod
    def attempt_envelope(
        text: str,
        intent: TeachingControlIntent = TeachingControlIntent.CONTINUE,
    ) -> TeachingResponseEnvelope:
        return TeachingResponseEnvelope(
            control_intent=intent,
            attempt_present=True,
            attempt=AttemptPayload(text=text),
        )

    # -- durable reads -------------------------------------------------------

    def moment(self, moment_id, teaching: TeachingController | None = None):
        owner = self.teaching if teaching is None else teaching
        result = owner.get_moment(moment_id)
        assert isinstance(result, Ok) and result.value is not None
        return result.value

    def lock_rows(self) -> int:
        return int(
            self.db.execute(
                "SELECT COUNT(*) FROM active_teaching_lock"
            ).fetchone()[0]
        )

    def moment_rows(self) -> int:
        return int(
            self.db.execute(
                "SELECT COUNT(*) FROM teaching_moment"
            ).fetchone()[0]
        )

    def attempt_rows(self) -> int:
        return int(
            self.db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0]
        )

    def step(self, moment: TeachingMomentRecord, **columns):
        """One CAS-guarded lifecycle/ladder step through the controller."""

        stepped = self.teaching.transition_moment(
            moment.moment_id, MomentTransition(**columns), moment.state_version
        )
        assert isinstance(stepped, Ok), stepped
        return stepped.value


def _err_code(result) -> str:
    assert isinstance(result, Err), result
    return result.error.code.value


class LockLostTeachingController(TeachingController):
    """The teaching face whose lock observation reports the lock row gone.

    The §7 POLICY_STOP case needs a continuation DENY whose BF-03 code has
    no precise §7 word. In v0 the only such fact is a lost TeachingLockLease
    (TEACHING_LOCK_INVALID): every other denial code either maps onto its own
    §7 word, degrades, or is a §8 conversion. The one injected part is the
    *fact* ("the lock is not OWNED_BY_THIS_MOMENT"); the Gate evaluates it
    for real and the coordinator's abort walk is the production code.
    """

    def observed_lock_state(self, conversation_id, moment_id=None):
        del conversation_id, moment_id
        return Ok("NONE")


def _state(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _strs(rows) -> list[str]:
    return [str(row[0]) for row in rows]


# ---------------------------------------------------------------------------
# §1 legal edges
# ---------------------------------------------------------------------------


def _case_authorized_to_opening(env: CaseEnv) -> dict[str, object]:
    """AUTHORIZED → OPENING: the pre-lock state lives inside the CP2 unit and
    is never a committed row; the committed state is OPENING (SM §1/§9)."""

    flaky = FailOnceGenerationStore(env.generation_store, "teaching-open")
    coordinator = env.coordinator(generation=flaky)
    crashed = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=FOCUS_TARGET,
            client_message_id=ClientMessageId("cm-edge-open-crash"),
            requested_at=REQUESTED_AT,
        )
    )
    assert not isinstance(crashed, Ok)

    # A second, independent parent: a CP2 request whose moment claims the
    # pre-lock state is refused (the unit commits OPENING).
    cp0 = commit_ok(env.store, CONV, "cm-edge-auth", "hello")
    cycle = env.decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-edge-auth",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(cycle, Ok), cycle
    base = _cp2("dcy-edge-auth", str(CONV), str(cp0.turn_id))
    authorized = env.teaching.commit_cp2_open(
        CP2OpenRequest(
            gate_execution_status=base.gate_execution_status,
            gate_decision=base.gate_decision,
            moment=replace(
                base.moment, lifecycle_state=MomentState.AUTHORIZED
            ),
            action=base.action,
            owner_epoch=base.owner_epoch,
        )
    )
    return {
        "cp2_committed_state": _strs(
            env.db.execute(
                "SELECT lifecycle_state FROM teaching_moment"
            ).fetchall()
        ),
        "authorized_rows": int(
            env.db.execute(
                "SELECT COUNT(*) FROM teaching_moment"
                " WHERE lifecycle_state = 'AUTHORIZED'"
            ).fetchone()[0]
        ),
        "lock_rows": env.lock_rows(),
        "first_action_status": _strs(
            env.db.execute(
                "SELECT status FROM generation_action_intent"
            ).fetchall()
        ),
        "authorized_commit_refused": _err_code(authorized),
    }


def _case_opening_to_awaiting_user(env: CaseEnv) -> dict[str, object]:
    """OPENING → AWAITING_USER only after a real opening delivery (§13.1)."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-happy")
    moment = env.moment(opened.moment_id)
    return {
        "moment_state": _state(opened.moment_state),
        "outcome": opened.outcome,
        "turn_status": _state(opened.turn_status),
        "action_status": _state(opened.action_status),
        "phase": _state(moment.presentation_phase),
        "support": _state(moment.support_level),
        "opened_at_set": moment.opened_at is not None,
        "lock_rows": env.lock_rows(),
    }


def _case_awaiting_user_to_evaluating(env: CaseEnv) -> dict[str, object]:
    """AWAITING_USER → EVALUATING: the attempt lands, the evaluation write is
    refused, and the moment is left exactly in its evaluating slot."""

    failing = FailingEvaluationController(env.teaching._store)
    coordinator = env.coordinator(teaching=failing)
    opened = env.open(coordinator, "cm-edge-eval")
    result = env.reply(
        coordinator, env.attempt_envelope(WRONG), "cm-edge-eval-a"
    )
    moment = env.moment(opened.moment_id, failing)
    return {
        "reply_refused": _err_code(result),
        "moment_state": _state(moment.lifecycle_state),
        "attempt_rows": env.attempt_rows(),
        "evaluation_rows": int(
            env.db.execute(
                "SELECT COUNT(*) FROM attempt_evaluation_record"
            ).fetchone()[0]
        ),
        "claims": int(
            env.db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0]
        ),
        "teaching_actions": int(
            env.db.execute(
                "SELECT COUNT(*) FROM generation_action_intent WHERE"
                " action_type != 'TEACHING_OPEN'"
            ).fetchone()[0]
        ),
    }


def _case_evaluating_to_deciding(env: CaseEnv) -> dict[str, object]:
    """EVALUATING → DECIDING_NEXT_ACTION: the attempt and its evaluation are
    durable, the next action is not yet dispatched."""

    flaky = FailOnceGenerationStore(env.generation_store, "retry")
    coordinator = env.coordinator(generation=flaky)
    opened = env.open(coordinator, "cm-edge-deciding")
    result = env.reply(
        coordinator, env.attempt_envelope(WRONG), "cm-edge-deciding-a"
    )
    assert not isinstance(result, Ok)
    moment = env.moment(opened.moment_id)
    return {
        "moment_state": _state(moment.lifecycle_state),
        "evaluation_rows": int(
            env.db.execute(
                "SELECT COUNT(*) FROM attempt_evaluation_record"
            ).fetchone()[0]
        ),
        "phase_unmoved": _state(moment.presentation_phase),
        "no_retry_action": int(
            env.db.execute(
                "SELECT COUNT(*) FROM generation_action_intent WHERE"
                " action_id LIKE '%-retry'"
            ).fetchone()[0]
        ),
    }


def _case_deciding_to_awaiting_user_hint(env: CaseEnv) -> dict[str, object]:
    """DECIDING → AWAITING_USER (HINT): one rung forward, gate ALLOW."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-hint")
    reply = env.reply_ok(coordinator, env.hint_envelope(), "cm-edge-hint-h")
    moment = env.moment(opened.moment_id)
    return {
        "delivery_kind": reply.delivery_kind,
        "action_type": reply.action_type,
        "gate_decision": reply.gate_decision,
        "moment_state": _state(reply.moment_state),
        "phase": _state(moment.presentation_phase),
        "support": _state(moment.support_level),
    }


def _case_deciding_to_awaiting_user_retry(env: CaseEnv) -> dict[str, object]:
    """DECIDING → AWAITING_USER (RETRY): a failed attempt without a hint
    request re-prompts at the same rung."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-retry")
    reply = env.reply_ok(
        coordinator, env.attempt_envelope(WRONG), "cm-edge-retry-a"
    )
    moment = env.moment(opened.moment_id)
    return {
        "delivery_kind": reply.delivery_kind,
        "action_type": reply.action_type,
        "evaluation_outcome": reply.evaluation_outcome,
        "moment_state": _state(reply.moment_state),
        "phase": _state(moment.presentation_phase),
        "support": _state(moment.support_level),
    }


def _case_deciding_to_completing_success(env: CaseEnv) -> dict[str, object]:
    """DECIDING → COMPLETING (SUCCESS): both support readings, and the whole
    closure chain (COMPLETING → TERMINAL → RESUMING → CLOSED)."""

    coordinator = env.coordinator()
    # Unsupported: no rung was ever shown (CONTEXT_ONLY is the initial prompt).
    opened = env.open(coordinator, "cm-edge-unsupported")
    unsupported = env.reply_ok(
        coordinator, env.attempt_envelope(CANONICAL), "cm-edge-unsupported-a"
    )
    # Supported: reached after a hint rung.
    opened2 = env.open(coordinator, "cm-edge-supported")
    env.reply_ok(coordinator, env.hint_envelope(), "cm-edge-supported-h")
    supported = env.reply_ok(
        coordinator, env.attempt_envelope(CANONICAL), "cm-edge-supported-a"
    )
    moment = env.moment(opened2.moment_id)
    return {
        "unsupported": unsupported.closure,
        "supported": supported.closure,
        "closing_outcome_pure": {
            "none_support": closing_outcome_for("SUCCESS", "NONE").value,
            "context_support": closing_outcome_for(
                "SUCCESS", "CONTEXT_ONLY"
            ).value,
            "semantic_support": closing_outcome_for(
                "SUCCESS", "SEMANTIC_HINT"
            ).value,
            "alternative": closing_outcome_for(
                "ALTERNATIVE_SUCCESS", "NONE"
            ).value,
        },
        "moment_state": _state(supported.moment_state),
        "completion_outcome": moment.completion_outcome,
        "abort_reason": moment.abort_reason,
        "closed_at_set": bool(moment.closed_at),
        "lock_rows": env.lock_rows(),
        "first_moment_closed": _state(
            env.moment(opened.moment_id).lifecycle_state
        ),
    }


def _case_deciding_to_completing_closing_reveal(
    env: CaseEnv,
) -> dict[str, object]:
    """DECIDING → COMPLETING via the §8 conversion: the hard attempt cap makes
    the closing move a REVEALED reveal (the frozen exemption), not a stop."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-revealed")
    env.reply_ok(coordinator, env.attempt_envelope(WRONG), "cm-edge-r1")
    env.reply_ok(coordinator, env.attempt_envelope(WRONG), "cm-edge-r2")
    reply = env.reply_ok(
        coordinator, env.attempt_envelope(WRONG), "cm-edge-r3"
    )
    moment = env.moment(opened.moment_id)
    denial = env.db.execute(
        "SELECT reason_codes FROM gate_decision WHERE decision = 'DENY'"
    ).fetchall()
    return {
        "closure": reply.closure,
        "limit_reason": reply.limit_reason,
        "delivery_kind": reply.delivery_kind,
        "moment_state": _state(reply.moment_state),
        "completion_outcome": moment.completion_outcome,
        "deny_reason_codes": [str(row[0]) for row in denial],
        "attempt_rows": env.attempt_rows(),
    }


def _case_deciding_to_awaiting_user_requested_reveal(
    env: CaseEnv,
) -> dict[str, object]:
    """DECIDING → AWAITING_USER with a REVEAL (the §1 "or" arm): a requested
    reveal keeps the moment open at FULL_REVEAL for the optional attempt."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-open-reveal")
    reply = env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.ASK_ANSWER),
        "cm-edge-open-reveal-r",
    )
    moment = env.moment(opened.moment_id)
    return {
        "delivery_kind": reply.delivery_kind,
        "action_type": reply.action_type,
        "moment_state": _state(reply.moment_state),
        "phase": _state(moment.presentation_phase),
        "support": _state(moment.support_level),
        "closure": reply.closure,
    }


def _case_deciding_to_awaiting_user_explanation(env: CaseEnv) -> dict[str, object]:
    """EXPLAIN: v0 reads the §1 branch as a continuation (AWAITING_USER at the
    EXPLANATION phase); the COMPLETING arm has no v0 path (自裁 1)."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-explain")
    reply = env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.ASK_EXPLANATION),
        "cm-edge-explain-r",
    )
    moment = env.moment(opened.moment_id)
    return {
        "delivery_kind": reply.delivery_kind,
        "moment_state": _state(reply.moment_state),
        "phase": _state(moment.presentation_phase),
        "completion_outcome": moment.completion_outcome,
        "closure": reply.closure,
    }


def _leaving_case(intent: TeachingControlIntent, reason: str, cmid: str):
    def run(env: CaseEnv) -> dict[str, object]:
        coordinator = env.coordinator()
        opened = env.open(coordinator, f"{cmid}-open")
        reply = env.reply_ok(
            coordinator, env.control_envelope(intent), f"{cmid}-r"
        )
        moment = env.moment(opened.moment_id)
        return {
            "closure": reply.closure,
            "moment_state": _state(reply.moment_state),
            "abort_reason": moment.abort_reason,
            "completion_outcome": moment.completion_outcome,
            "lock_rows": env.lock_rows(),
            "reason_in_canonical_vocabulary": reply.closure in ABORT_REASONS,
            "expected_reason": reason,
        }

    return run


def _switch_case(env: CaseEnv) -> dict[str, object]:
    """SWITCH_TARGET: 先关旧 moment，再同 turn 新 DecisionCycle（SM §2）。"""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-switch")
    reply = env.reply_ok(
        coordinator,
        env.control_envelope(
            TeachingControlIntent.SWITCH_TARGET,
            target_switch_request=SWITCH_TO,
        ),
        "cm-edge-switch-r",
    )
    moment = env.moment(opened.moment_id)
    cycles = _strs(
        env.db.execute(
            "SELECT cycle_index FROM decision_cycle WHERE turn_id = ?"
            " ORDER BY cycle_index",
            (reply.turn_id,),
        ).fetchall()
    )
    pointer = env.db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (reply.turn_id,),
    ).fetchone()
    return {
        "closure": reply.closure,
        "moment_state": _state(reply.moment_state),
        "abort_reason": moment.abort_reason,
        "cycle_indexes": cycles,
        "next_cycle_is_the_new_one": str(pointer[0]) == str(reply.next_cycle_id),
        "moment_rows": env.moment_rows(),
        "lock_rows": env.lock_rows(),
    }


def _case_completing_to_terminal(env: CaseEnv) -> dict[str, object]:
    """COMPLETING → TEACHING_TERMINAL (+ the lock release in the same short
    transaction, DATA_MODEL §18)."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-terminal")
    moment = env.step(
        env.moment(opened.moment_id), lifecycle_state=MomentState.COMPLETING
    )
    terminal = env.teaching.terminalize_moment(
        moment.moment_id, completion_outcome="USER_SATISFIED"
    )
    assert isinstance(terminal, Ok), terminal
    closed = terminal.value
    return {
        "state": _state(closed.lifecycle_state),
        "completion_outcome": closed.completion_outcome,
        "abort_reason": closed.abort_reason,
        "terminal_at_set": closed.teaching_terminal_at is not None,
        "lock_rows": env.lock_rows(),
    }


def _case_aborting_to_terminal(env: CaseEnv) -> dict[str, object]:
    """ABORTING → TEACHING_TERMINAL with the §7 reason (lock released)."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-aborting")
    moment = env.step(
        env.moment(opened.moment_id),
        lifecycle_state=MomentState.ABORTING,
        abort_reason="POLICY_STOP",
    )
    terminal = env.teaching.terminalize_moment(
        moment.moment_id, abort_reason="POLICY_STOP"
    )
    assert isinstance(terminal, Ok), terminal
    closed = terminal.value
    return {
        "state": _state(closed.lifecycle_state),
        "abort_reason": closed.abort_reason,
        "completion_outcome": closed.completion_outcome,
        "lock_rows": env.lock_rows(),
    }


def _case_terminal_to_resuming_to_closed(env: CaseEnv) -> dict[str, object]:
    """TEACHING_TERMINAL → RESUMING → CLOSED (SM §1 tail)."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-edge-tail")
    moment = env.step(
        env.moment(opened.moment_id), lifecycle_state=MomentState.COMPLETING
    )
    terminal = env.teaching.terminalize_moment(
        moment.moment_id, completion_outcome="REVEALED"
    )
    assert isinstance(terminal, Ok), terminal
    resuming = env.step(
        terminal.value, lifecycle_state=MomentState.RESUMING
    )
    closed = env.step(
        resuming,
        lifecycle_state=MomentState.CLOSED,
        closed_at=REQUESTED_AT,
    )
    return {
        "resuming_state": _state(resuming.lifecycle_state),
        "closed_state": _state(closed.lifecycle_state),
        "closed_at_set": bool(closed.closed_at),
        "closed_at_was_none_while_resuming": resuming.closed_at is None,
        "lock_rows": env.lock_rows(),
    }


# ---------------------------------------------------------------------------
# §1/§2/§3/§8 illegal transitions
# ---------------------------------------------------------------------------


def _case_closed_is_final(env: CaseEnv) -> dict[str, object]:
    """CLOSED 后任何转换（含 reopen）拒；future teaching 用新 moment_id。"""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-final")
    env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.SKIP),
        "cm-final-skip",
    )
    closed = env.moment(opened.moment_id)
    reopen = env.teaching.transition_moment(
        closed.moment_id,
        MomentTransition(lifecycle_state=MomentState.AWAITING_USER),
        closed.state_version,
    )
    reply = env.reply(coordinator, env.hint_envelope(), "cm-final-reply")
    fresh = env.open(coordinator, "cm-final-new")
    return {
        "reopen_code": _err_code(reopen),
        "reopen_says_never_reopened": "never reopened" in reopen.error.message,
        "reply_refused": _err_code(reply),
        "new_moment_id_differs": str(fresh.moment_id) != str(opened.moment_id),
        "moment_rows": env.moment_rows(),
        "closed_moment_state": _state(
            env.moment(opened.moment_id).lifecycle_state
        ),
    }


def _case_terminal_tail_is_one_way(env: CaseEnv) -> dict[str, object]:
    """TEACHING_TERMINAL 回退非 RESUMING 拒；非终态直 TERMINAL 拒（锁不动）。"""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-tail")
    live = env.moment(opened.moment_id)
    # A live moment cannot be terminalized directly: only COMPLETING /
    # ABORTING enter TEACHING_TERMINAL, and the refusal leaves the lock alone.
    illegal = env.teaching.terminalize_moment(
        live.moment_id, completion_outcome="USER_SATISFIED"
    )
    locks_after_refusal = env.lock_rows()
    moment = env.step(live, lifecycle_state=MomentState.COMPLETING)
    terminal = env.teaching.terminalize_moment(
        moment.moment_id, completion_outcome="REVEALED"
    )
    assert isinstance(terminal, Ok), terminal
    back = env.teaching.transition_moment(
        terminal.value.moment_id,
        MomentTransition(lifecycle_state=MomentState.AWAITING_USER),
        terminal.value.state_version,
    )
    replay = env.teaching.terminalize_moment(
        terminal.value.moment_id, completion_outcome="REVEALED"
    )
    return {
        "terminalize_from_awaiting_user": _err_code(illegal),
        "lock_still_held": locks_after_refusal,
        "terminal_back_to_awaiting_user": _err_code(back),
        "back_names_both_legal_arms": "only resumes or closes"
        in back.error.message,
        "terminal_replay_is_ok": isinstance(replay, Ok),
        "replayed_state": _state(replay.value.lifecycle_state),
    }


def _case_terminal_no_resume_arm(env: CaseEnv) -> dict[str, object]:
    """TEACHING_TERMINAL → CLOSED（SM §1:54 的 no-resume 臂）：不需要 resume
    的 episode 直接闭合，不假装走 RESUMING。"""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-no-resume")
    moment = env.step(
        env.moment(opened.moment_id), lifecycle_state=MomentState.COMPLETING
    )
    terminal = env.teaching.terminalize_moment(
        moment.moment_id, completion_outcome="NO_FURTHER_VALUE"
    )
    assert isinstance(terminal, Ok), terminal
    closed = env.step(
        terminal.value,
        lifecycle_state=MomentState.CLOSED,
        closed_at=REQUESTED_AT,
    )
    return {
        "terminal_state": _state(terminal.value.lifecycle_state),
        "closed_state": _state(closed.lifecycle_state),
        "closed_at_set": closed.closed_at is not None,
        "completion_outcome": closed.completion_outcome,
        "lock_rows": env.lock_rows(),
        "durable_state": _state(
            env.moment(opened.moment_id).lifecycle_state
        ),
    }


def _case_closed_only_from_the_tail(env: CaseEnv) -> dict[str, object]:
    """未终态直 CLOSED 拒（generic CAS 面与 terminalize 面一致）：活跃
    moment 直接闭合会留下「CLOSED 却仍持锁」——controller 明确声明不可达。"""

    flaky = FailOnceGenerationStore(env.generation_store, "retry")
    coordinator = env.coordinator(generation=flaky)
    opened = env.open(coordinator, "cm-early-close")
    live = env.moment(opened.moment_id)
    early = env.teaching.transition_moment(
        live.moment_id,
        MomentTransition(lifecycle_state=MomentState.CLOSED),
        live.state_version,
    )
    # A second, real flow state: the moment parked in its deciding slot.
    crashed = env.reply(
        coordinator, env.attempt_envelope(WRONG), "cm-early-close-a"
    )
    assert isinstance(crashed, Err), crashed
    deciding = env.moment(opened.moment_id)
    from_deciding = env.teaching.transition_moment(
        deciding.moment_id,
        MomentTransition(lifecycle_state=MomentState.CLOSED),
        deciding.state_version,
    )
    return {
        "close_from_awaiting_user": _err_code(early),
        "refusal_names_the_tail": "reached from TEACHING_TERMINAL or"
        " RESUMING" in early.error.message,
        "deciding_state": _state(deciding.lifecycle_state),
        "close_from_deciding": _err_code(from_deciding),
        "moment_still_live": _state(
            env.moment(opened.moment_id).lifecycle_state
        ),
        "lock_rows": env.lock_rows(),
        "no_closed_row": int(
            env.db.execute(
                "SELECT COUNT(*) FROM teaching_moment WHERE lifecycle_state"
                " = 'CLOSED'"
            ).fetchone()[0]
        ),
    }


def _case_ladder_refusals(env: CaseEnv) -> dict[str, object]:
    """§3 双单调：phase 回退拒、support 回退拒、support 超相位天花板拒。"""

    del env
    return {
        "phase_back": (
            ladder_step_refusal(
                "HINT_STRUCTURAL", "STRUCTURAL_HINT", "HINT_SEMANTIC",
                "STRUCTURAL_HINT",
            )
            is not None
        ),
        "support_back": (
            ladder_step_refusal(
                "HINT_PARTIAL_FORM", "STRUCTURAL_HINT", "HINT_PARTIAL_FORM",
                "SEMANTIC_HINT",
            )
            is not None
        ),
        "support_over_ceiling": (
            ladder_step_refusal(
                "INITIAL_PROMPT", "CONTEXT_ONLY", "INITIAL_PROMPT",
                "FULL_FORM_SHOWN",
            )
            is not None
        ),
        "forward_is_allowed": (
            ladder_step_refusal(
                "INITIAL_PROMPT", "CONTEXT_ONLY", "HINT_SEMANTIC",
                "SEMANTIC_HINT",
            )
            is None
        ),
        "same_rung_is_allowed": (
            ladder_step_refusal(
                "HINT_SEMANTIC", "SEMANTIC_HINT", "HINT_SEMANTIC",
                "SEMANTIC_HINT",
            )
            is None
        ),
    }


def _case_reconcile_never_lowers(env: CaseEnv) -> dict[str, object]:
    """The crash reconciliation rebuilds a rung absolutely and only ever moves
    forward: a durable rung *above* the rebuilt one is kept (SM §3)."""

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-reconcile")
    delivered = env.reply_ok(coordinator, env.hint_envelope(), "cm-reconcile-h")
    # The durable rung is raised by hand (one rung above the single delivery).
    env.db.execute(
        "UPDATE teaching_moment SET presentation_phase = 'HINT_STRUCTURAL',"
        " support_level = 'STRUCTURAL_HINT' WHERE moment_id = ?",
        (str(opened.moment_id),),
    )
    env.db.commit()
    replayed = env.reply(coordinator, env.hint_envelope(), "cm-reconcile-h")
    assert isinstance(replayed, Ok), replayed
    moment = env.moment(opened.moment_id)
    return {
        "phase_after": _state(moment.presentation_phase),
        "support_after": _state(moment.support_level),
        "assistant_turns": int(
            env.db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0]
        ),
        "hint_deliveries": int(
            env.db.execute(
                "SELECT COUNT(*) FROM generation_action_intent WHERE"
                " action_id LIKE '%-hint'"
            ).fetchone()[0]
        ),
        "replayed_turn_matches": replayed.value.turn_id == delivered.turn_id,
    }


def _case_limits_matrix(env: CaseEnv) -> dict[str, object]:
    """§8 超限拒新动作但收尾豁免（纯矩阵）：hard cap 只挡 retry-like /
    非 terminalizing，terminalizing 收尾永远许可；soft cap 需显式请求。"""

    del env
    limits = TeachingLimits()
    hard_attempt = TeachingLoad(attempt_count=3, teaching_turn_count=1)
    hard_turn = TeachingLoad(attempt_count=0, teaching_turn_count=5)
    soft = TeachingLoad(attempt_count=2, teaching_turn_count=1)

    def verdict(load, kind, requested):
        result = continuation_verdict(
            limits,
            load,
            delivery_kind=kind,
            user_requested_continue=requested,
        )
        return {
            "allowed": result.allowed,
            "closing_only": result.closing_only,
            "reason": result.degraded_reason,
            "user_request_required": result.user_request_required,
        }

    return {
        "hard_attempt_hint": verdict(hard_attempt, "HINT", True),
        "hard_attempt_retry": verdict(hard_attempt, "RETRY", True),
        "hard_attempt_reveal_exempt": verdict(hard_attempt, "REVEAL", True),
        "hard_turn_hint": verdict(hard_turn, "HINT", True),
        "hard_turn_explanation": verdict(hard_turn, "EXPLANATION", True),
        "hard_turn_reveal_exempt": verdict(hard_turn, "REVEAL", True),
        "soft_without_request": verdict(soft, "RETRY", False),
        "soft_with_request": verdict(soft, "HINT", True),
        "soft_terminalizing_without_request": verdict(soft, "REVEAL", False),
    }


def _case_awaiting_user_no_attempt_jump(env: CaseEnv) -> dict[str, object]:
    """AWAITING_USER 无 attempt 直跳 EVALUATING 的后果：控制型回复不伪造
    attempt（不造 ABSTAIN），且 durable 面拒绝在 AWAITING_USER 记录 attempt。"""

    from elc.teaching.flow import attempt_record_for

    coordinator = env.coordinator()
    opened = env.open(coordinator, "cm-nojump")
    reply = env.reply_ok(coordinator, env.hint_envelope(), "cm-nojump-h")
    moment = env.moment(opened.moment_id)
    probe = env.teaching.record_attempt(
        attempt_record_for(
            moment=moment,
            attempt_id="at-probe-nojump",
            user_turn_id=str(UserTurnId("ut-probe")),
            attempt_index=1,
        )
    )
    return {
        "control_reply_delivery": reply.delivery_kind,
        "attempt_rows": env.attempt_rows(),
        "abstain_rows": int(
            env.db.execute(
                "SELECT COUNT(*) FROM attempt_evaluation_record WHERE"
                " outcome = 'ABSTAIN'"
            ).fetchone()[0]
        ),
        "direct_attempt_refused": _err_code(probe),
        "moment_state": _state(moment.lifecycle_state),
    }


# ---------------------------------------------------------------------------
# §6 / §7 vocabulary partitions
# ---------------------------------------------------------------------------


def _case_completion_outcomes_partition(env: CaseEnv) -> dict[str, object]:
    """§6 七词逐词：五词有生产路径（本 case 实测），两词 durable-only。"""

    coordinator = env.coordinator()
    produced: dict[str, object] = {}

    env.open(coordinator, "cm-w1")
    produced["SUCCESS_UNSUPPORTED"] = env.reply_ok(
        coordinator, env.attempt_envelope(CANONICAL), "cm-w1-a"
    ).closure

    env.open(coordinator, "cm-w2")
    env.reply_ok(coordinator, env.hint_envelope(), "cm-w2-h")
    produced["SUCCESS_SUPPORTED"] = env.reply_ok(
        coordinator, env.attempt_envelope(CANONICAL), "cm-w2-a"
    ).closure

    env.open(coordinator, "cm-w3")
    produced["SUCCESS_ALTERNATIVE"] = env.reply_ok(
        coordinator, env.attempt_envelope(ALTERNATIVE), "cm-w3-a"
    ).closure

    env.open(coordinator, "cm-w4")
    env.reply_ok(coordinator, env.attempt_envelope(WRONG), "cm-w4-a1")
    env.reply_ok(coordinator, env.attempt_envelope(WRONG), "cm-w4-a2")
    produced["PARTIAL_PROGRESS"] = env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.META_DISCUSSION),
        "cm-w4-meta",
    ).closure

    env.open(coordinator, "cm-w5")
    env.reply_ok(coordinator, env.attempt_envelope(WRONG), "cm-w5-a1")
    env.reply_ok(coordinator, env.attempt_envelope(WRONG), "cm-w5-a2")
    produced["REVEALED"] = env.reply_ok(
        coordinator, env.attempt_envelope(WRONG), "cm-w5-a3"
    ).closure

    durable_only = sorted(set(COMPLETION_OUTCOMES) - set(produced))
    return {
        "produced": produced,
        # Derived complement within the canonical list; the expectation
        # carries the literal words, so a canonical growth or a newly
        # producible word fails the case (no tautological self-check).
        "durable_only": durable_only,
        "canonical_words": sorted(COMPLETION_OUTCOMES),
    }


def _case_abort_reasons_partition(env: CaseEnv) -> dict[str, object]:
    """§7 十四词逐词：九词编排面实测；两词仅映射面；三词不可构造（留痕）。"""

    coordinator = env.coordinator()
    produced: dict[str, object] = {}

    env.open(coordinator, "cm-b1")
    produced["USER_SKIP"] = env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.SKIP),
        "cm-b1-r",
    ).closure

    env.open(coordinator, "cm-b2")
    produced["USER_REJECTED_TARGET"] = env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.REJECT_TARGET),
        "cm-b2-r",
    ).closure

    env.open(coordinator, "cm-b3")
    produced["USER_TOPIC_SHIFT"] = env.reply_ok(
        coordinator,
        env.control_envelope(TeachingControlIntent.CHANGE_TOPIC),
        "cm-b3-r",
    ).closure

    env.open(coordinator, "cm-b4")
    produced["USER_SWITCH_TARGET"] = env.reply_ok(
        coordinator,
        env.control_envelope(
            TeachingControlIntent.SWITCH_TARGET,
            target_switch_request=SWITCH_TO,
        ),
        "cm-b4-r",
    ).closure

    # POLICY_STOP: the lock fact says the one-focus guarantee is gone (the
    # crash shape: the row disappeared between the moment read and the
    # Gate's fact assembly). The only injected part is that fact; the Gate
    # evaluates it for real, denies with TEACHING_LOCK_INVALID, and the
    # coordinator converts the refusal into a §7 POLICY_STOP instead of
    # dropping the move silently.
    env.open(coordinator, "cm-b5")
    lockless = env.coordinator(
        teaching=LockLostTeachingController(env.teaching._store)
    )
    policy = env.reply_ok(lockless, env.hint_envelope(), "cm-b5-r")
    produced["POLICY_STOP"] = policy.closure

    # CONTENT_INVALID: the target's content is known-invalid at reply time.
    env.open(coordinator, "cm-b6")
    invalid_targets = env.coordinator(
        targets=provider_over(CONTENT_INVALID_PROVIDER_VIEW)
    )
    produced["CONTENT_INVALID"] = env.reply_ok(
        invalid_targets, env.hint_envelope(), "cm-b6-r"
    ).closure

    # SYSTEM_FAILURE: the resolver is down (target/content UNKNOWN →
    # continuation DEGRADED, RA §21 teaching state failure).
    env.open(coordinator, "cm-b7")
    down = env.coordinator(targets=UNAVAILABLE_TARGET_PROVIDER)
    produced["SYSTEM_FAILURE"] = env.reply_ok(
        down, env.hint_envelope(), "cm-b7-r"
    ).closure

    # DELIVERY_FAILURE: the opening prompt never reached the user.
    down_provider = env.coordinator(
        provider=ScriptedPersonaProvider(
            (ProviderOutput(text=None, error="provider down"),)
        )
    )
    failed_open = env.open(down_provider, "cm-b8-fail")
    produced["DELIVERY_FAILURE"] = env.moment(
        failed_open.moment_id
    ).abort_reason

    # SYSTEM_RECOVERY_ABORT: the sweep of a dead epoch's lock (the epoch move
    # comes last — it fences every older-epoch store).
    env.open(coordinator, "cm-b9")
    new_fence = epoch.open_runtime_epoch(env.db)
    new_teaching = TeachingController(SqliteTeachingStore(env.db, new_fence))
    recovered = new_teaching.recover_orphan_locks()
    assert isinstance(recovered, Ok), recovered
    produced["SYSTEM_RECOVERY_ABORT"] = env.moment(
        recovered.value[0], new_teaching
    ).abort_reason

    mapping_only = {
        word: closing_reason_for_gate_denial((word,))
        for word in ("SNAPSHOT_INVALIDATED", "PRE_DELIVERY_INVALIDATED")
    }
    unreachable = sorted(
        set(ABORT_REASONS) - set(produced) - set(mapping_only)
    )
    deny_reason_codes = _strs(
        env.db.execute(
            "SELECT reason_codes FROM gate_decision WHERE decision = 'DENY'"
            " AND context = 'USER_REQUESTED_CONTINUE' ORDER BY rowid"
        ).fetchall()
    )
    return {
        "produced": produced,
        # Derived complements within the canonical list; the expectation
        # carries the literal words (see the §6 case note).
        "mapping_only": mapping_only,
        "unreachable": unreachable,
        "canonical_words": sorted(ABORT_REASONS),
        "deny_reason_codes": deny_reason_codes,
    }


# ---------------------------------------------------------------------------
# §2 cycle chain / §8+§12.1 continuation / §4 + §17 attempt chain
# ---------------------------------------------------------------------------


def _case_switch_target_cycle_chain(env: CaseEnv) -> dict[str, object]:
    """多目标连切：每个 switch turn 的 cycle_index 链 [0, 1]（先关旧 moment，
    再同 turn 新 cycle）；durable 面同 turn 连开三 cycle = 0,1,2（自裁：v0
    一个回复回合至多一次显式换目标，链的无限性由 cycle 面证明）。"""

    coordinator = env.coordinator()
    per_turn: list[list[str]] = []
    moments: list[str] = []
    for index in range(3):
        env.open(coordinator, f"cm-chain-open-{index}")
        reply = env.reply_ok(
            coordinator,
            env.control_envelope(
                TeachingControlIntent.SWITCH_TARGET,
                target_switch_request=SWITCH_TO,
            ),
            f"cm-chain-switch-{index}",
        )
        per_turn.append(
            _strs(
                env.db.execute(
                    "SELECT cycle_index FROM decision_cycle WHERE turn_id = ?"
                    " ORDER BY cycle_index",
                    (reply.turn_id,),
                ).fetchall()
            )
        )
        moments.append(reply.closure)

    # The durable same-turn chain, addressed directly on one live turn: the
    # store hands out 0, 1, 2 … for as long as the turn stays nonterminal.
    normal = commit_ok(env.store, CONV, "cm-chain-probe", "hello")
    chain: list[str] = []
    for index in (1, 2, 3):
        version = int(
            env.db.execute(
                "SELECT state_version FROM turn_record WHERE turn_id = ?",
                (normal.turn_id,),
            ).fetchone()[0]
        )
        recorded = env.decision_cycle_store.record_decision_cycle(
            decision_cycle_id=f"dcy-chain-probe-{index}",
            turn_id=normal.turn_id,
            bindings=DecisionCycleBindings(),
            expected_turn_state_version=version,
        )
        assert isinstance(recorded, Ok), recorded
        chain = _strs(
            env.db.execute(
                "SELECT cycle_index FROM decision_cycle WHERE turn_id = ?"
                " ORDER BY cycle_index",
                (normal.turn_id,),
            ).fetchall()
        )
    return {
        "per_turn_cycle_indexes": per_turn,
        "closures": moments,
        "moment_rows": env.moment_rows(),
        "lock_rows": env.lock_rows(),
        "durable_chain": chain,
        "cycle_ids_are_unique": int(
            env.db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0]
        )
        == int(
            env.db.execute(
                "SELECT COUNT(DISTINCT decision_cycle_id) FROM decision_cycle"
            ).fetchone()[0]
        ),
    }


def _case_continuation_basis(env: CaseEnv) -> dict[str, object]:
    """§12.1/§8：continuation 由 ACTIVE_MOMENT 授权、上下文恒
    USER_REQUESTED_CONTINUE；AUTO_CONTINUE 是契约错误（Phase 8 扩展点）。"""

    coordinator = env.coordinator()
    env.open(coordinator, "cm-basis")
    env.reply_ok(coordinator, env.hint_envelope(), "cm-basis-h")
    row = env.db.execute(
        "SELECT gate_context, authorization_basis, authorization_status,"
        " status FROM gate_execution_status WHERE gate_context ="
        " 'USER_REQUESTED_CONTINUE'"
    ).fetchone()
    try:
        decide_user_requested_continuation(
            ContinuationFacts(moment_id="tm-x", gate_context="AUTO_CONTINUE")
        )
    except GateInputError as exc:
        contract_error = type(exc).__name__
    else:  # pragma: no cover - the contract check always fires
        contract_error = None
    return {
        "gate_context": str(row[0]),
        "authorization_basis": str(row[1]),
        "authorization_status": str(row[2]),
        "status": str(row[3]),
        "auto_continue_contract_error": contract_error,
    }


def _case_own_evidence_keeps_continuation(env: CaseEnv) -> dict[str, object]:
    """§9/§12.1：本 Moment 自己提交的新 Evidence 推进 watermark，但不使自身
    continuation 失效（continuation facts 不含 LEARNING_SNAPSHOT）。"""

    coordinator = env.coordinator()
    env.open(coordinator, "cm-selfev")
    before = env.learning_controller.get_learning_snapshot().value.evidence_watermark
    failed_attempt = env.reply_ok(
        coordinator, env.attempt_envelope(WRONG), "cm-selfev-a"
    )
    after = env.learning_controller.get_learning_snapshot().value.evidence_watermark
    continuation = env.reply_ok(coordinator, env.hint_envelope(), "cm-selfev-h")
    allows = int(
        env.db.execute(
            "SELECT COUNT(*) FROM gate_decision WHERE context ="
            " 'USER_REQUESTED_CONTINUE' AND decision = 'ALLOW'"
        ).fetchone()[0]
    )
    return {
        "watermark_before": int(before),
        "watermark_after": int(after),
        "watermark_advanced": int(after) > int(before),
        "claims": int(
            env.db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0]
        ),
        "first_continuation": failed_attempt.delivery_kind,
        "second_continuation_gate": continuation.gate_decision,
        "continuation_allows": allows,
        "degraded_rows": int(
            env.db.execute(
                "SELECT COUNT(*) FROM gate_execution_status WHERE status ="
                " 'DEGRADED'"
            ).fetchone()[0]
        ),
    }


def _case_attempt_and_control_coexist(env: CaseEnv) -> dict[str, object]:
    """§4 envelope 非互斥：一条回复既携带 attempt 又携带控制意图，两者都被
    处理（attempt 被评估/落证据，控制意图决定下一步）。"""

    coordinator = env.coordinator()
    env.open(coordinator, "cm-coexist")
    reply = env.reply_ok(
        coordinator,
        env.attempt_envelope(CANONICAL, TeachingControlIntent.ASK_HINT),
        "cm-coexist-r",
    )
    return {
        "evaluation_outcome": reply.evaluation_outcome,
        "delivery_kind": reply.delivery_kind,
        "moment_state": _state(reply.moment_state),
        "closure": reply.closure,
        "attempt_rows": env.attempt_rows(),
        "claims": int(
            env.db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0]
        ),
        # Derived from the returned envelope turn, not a constant: the
        # explicit hint request kept the moment open despite the success.
        "stayed_open": (
            reply.moment_state is MomentState.AWAITING_USER
            and reply.closure is None
        ),
    }


def _case_attempt_chain_under_pressure(env: CaseEnv) -> dict[str, object]:
    """§17/§4：压力序列（hint → 失败 → hint → 失败 → 成功）下，attempt →
    evaluation → gate → action → 落梯的顺序与恒链保持稳定。"""

    trace: list[str] = []
    coordinator = env.coordinator(
        generation=TracingGenerationStore(env.generation_store, trace),
        teaching=TracingTeachingController(env.teaching._store, trace),
    )
    env.open(coordinator, "cm-pressure")
    env.reply_ok(coordinator, env.hint_envelope(), "cm-pressure-h1")

    trace.clear()
    first = env.reply_ok(
        coordinator, env.attempt_envelope(WRONG), "cm-pressure-a1"
    )
    attempt_round = {
        "attempt_before_evaluation": trace.index("attempt")
        < trace.index("evaluation"),
        "evaluation_before_gate": trace.index("evaluation")
        < trace.index("gate-allow"),
        "gate_before_action": trace.index("gate-allow")
        < trace.index("action:TEACHING_HINT"),
        "action_before_landing": trace.index("action:TEACHING_HINT")
        < trace.index("moment:AWAITING_USER"),
    }

    env.reply_ok(coordinator, env.hint_envelope(), "cm-pressure-h2")
    second = env.reply_ok(
        coordinator, env.attempt_envelope(WRONG), "cm-pressure-a2"
    )
    third = env.reply_ok(
        coordinator, env.attempt_envelope(CANONICAL), "cm-pressure-a3"
    )

    attempts = [
        (int(row[0]), str(row[1]))
        for row in env.db.execute(
            "SELECT attempt_index, support_level_before_attempt"
            " FROM attempt_record ORDER BY attempt_index"
        ).fetchall()
    ]
    evaluations = [
        (int(row[0]), str(row[1]))
        for row in env.db.execute(
            "SELECT a.attempt_index, e.outcome"
            " FROM attempt_evaluation_record e"
            " JOIN attempt_record a ON a.attempt_id = e.attempt_id"
            " ORDER BY a.attempt_index"
        ).fetchall()
    ]
    groups = [
        str(row[0])
        for row in env.db.execute(
            "SELECT e.evidence_proposal_refs"
            " FROM attempt_evaluation_record e"
            " JOIN attempt_record a ON a.attempt_id = e.attempt_id"
            " ORDER BY a.attempt_index"
        ).fetchall()
    ]
    claims = [
        (str(row[0]), str(row[1]), str(row[2]))
        for row in env.db.execute(
            "SELECT evidence_group_id, outcome, polarity FROM evidence_claim"
            " ORDER BY rowid"
        ).fetchall()
    ]
    attempt_ids = _strs(
        env.db.execute(
            "SELECT attempt_id FROM attempt_record ORDER BY attempt_index"
        ).fetchall()
    )
    return {
        "attempt_round_order": attempt_round,
        "attempts": attempts,
        "evaluations": evaluations,
        "proposal_refs_link_their_attempt": all(
            group.startswith('["eg-teaching-at-') for group in groups
        ),
        "claim_groups_match_attempts_in_order": [claim[0] for claim in claims]
        == [f"eg-teaching-{attempt_id}" for attempt_id in attempt_ids],
        "claim_outcomes": [claim[1:] for claim in claims],
        "first_outcome": first.evaluation_outcome,
        "second_outcome": second.evaluation_outcome,
        "third_closure": third.closure,
        "gate_allows": int(
            env.db.execute(
                "SELECT COUNT(*) FROM gate_decision WHERE context ="
                " 'USER_REQUESTED_CONTINUE' AND decision = 'ALLOW'"
            ).fetchone()[0]
        ),
    }


# ---------------------------------------------------------------------------
# the case table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateCase:
    case_id: str
    sm_ref: str
    intent: str
    run: Callable[[CaseEnv], dict[str, object]]
    expected: dict[str, object]


CASES: tuple[StateCase, ...] = (
    StateCase(
        "sm1-authorized-to-opening",
        "SM §1 AUTHORIZED→OPENING; §2; §9",
        "CP2 提交值是 OPENING，AUTHORIZED 永不落行；非 OPENING 提交值被拒",
        _case_authorized_to_opening,
        {
            "cp2_committed_state": ["OPENING"],
            "authorized_rows": 0,
            "lock_rows": 1,
            "first_action_status": ["PREPARED"],
            "authorized_commit_refused": "VALIDATION_FAILED",
        },
    ),
    StateCase(
        "sm1-opening-to-awaiting-user",
        "SM §1 OPENING→AWAITING_USER; §13.1",
        "开链交付成功后才进 AWAITING_USER（初梯 CONTEXT_ONLY）",
        _case_opening_to_awaiting_user,
        {
            "moment_state": "AWAITING_USER",
            "outcome": "REPLIED_FULL",
            "turn_status": "COMPLETED",
            "action_status": "TERMINAL",
            "phase": "INITIAL_PROMPT",
            "support": "CONTEXT_ONLY",
            "opened_at_set": True,
            "lock_rows": 1,
        },
    ),
    StateCase(
        "sm1-awaiting-user-to-evaluating",
        "SM §1 AWAITING_USER→EVALUATING; §4 step 3",
        "attempt 落在 EVALUATING 槽；evaluation 未 durable 时不得继续",
        _case_awaiting_user_to_evaluating,
        {
            "reply_refused": "DEPENDENCY_UNAVAILABLE",
            "moment_state": "EVALUATING",
            "attempt_rows": 1,
            "evaluation_rows": 0,
            "claims": 0,
            "teaching_actions": 0,
        },
    ),
    StateCase(
        "sm1-evaluating-to-deciding",
        "SM §1 EVALUATING→DECIDING_NEXT_ACTION",
        "evaluation durable 后才进 DECIDING；动作未建成时梯级不动",
        _case_evaluating_to_deciding,
        {
            "moment_state": "DECIDING_NEXT_ACTION",
            "evaluation_rows": 1,
            "phase_unmoved": "INITIAL_PROMPT",
            "no_retry_action": 0,
        },
    ),
    StateCase(
        "sm1-deciding-to-awaiting-user-hint",
        "SM §1 DECIDING→AWAITING_USER（HINT）",
        "ASK_HINT：gate ALLOW → 一档前进 → 回到 AWAITING_USER",
        _case_deciding_to_awaiting_user_hint,
        {
            "delivery_kind": "HINT",
            "action_type": "TEACHING_HINT",
            "gate_decision": "ALLOW",
            "moment_state": "AWAITING_USER",
            "phase": "HINT_SEMANTIC",
            "support": "SEMANTIC_HINT",
        },
    ),
    StateCase(
        "sm1-deciding-to-awaiting-user-retry",
        "SM §1 DECIDING→AWAITING_USER（RETRY）",
        "失败 attempt 无 hint 请求：同档重试，梯级不动",
        _case_deciding_to_awaiting_user_retry,
        {
            "delivery_kind": "RETRY",
            "action_type": "TEACHING_HINT",
            "evaluation_outcome": "FAILURE",
            "moment_state": "AWAITING_USER",
            "phase": "INITIAL_PROMPT",
            "support": "CONTEXT_ONLY",
        },
    ),
    StateCase(
        "sm1-deciding-to-completing-success",
        "SM §1 DECIDING→COMPLETING（SUCCESS）; §6",
        "SUCCESS 双支持度（unsupported/supported）+ 全收尾链 + alternative 词",
        _case_deciding_to_completing_success,
        {
            "unsupported": "SUCCESS_UNSUPPORTED",
            "supported": "SUCCESS_SUPPORTED",
            "closing_outcome_pure": {
                "none_support": "SUCCESS_UNSUPPORTED",
                "context_support": "SUCCESS_UNSUPPORTED",
                "semantic_support": "SUCCESS_SUPPORTED",
                "alternative": "SUCCESS_ALTERNATIVE",
            },
            "moment_state": "CLOSED",
            "completion_outcome": "SUCCESS_SUPPORTED",
            "abort_reason": None,
            "closed_at_set": True,
            "lock_rows": 0,
            "first_moment_closed": "CLOSED",
        },
    ),
    StateCase(
        "sm1-deciding-to-completing-closing-reveal",
        "SM §1 DECIDING→COMPLETING（REVEAL 收尾臂）; §8",
        "hard attempt cap：转换成本（REVEALED 收尾 reveal），非静默停止",
        _case_deciding_to_completing_closing_reveal,
        {
            "closure": "REVEALED",
            "limit_reason": "HARD_ATTEMPT_LIMIT",
            "delivery_kind": "RESUME",
            "moment_state": "CLOSED",
            "completion_outcome": "REVEALED",
            "deny_reason_codes": ['["HARD_ATTEMPT_LIMIT"]'],
            "attempt_rows": 3,
        },
    ),
    StateCase(
        "sm1-deciding-to-awaiting-user-requested-reveal",
        "SM §1 REVEAL→AWAITING_USER（保持臂）; §3",
        "被请求的 reveal 停在 FULL_REVEAL 保持 moment 开放（post-reveal 可选尝试）",
        _case_deciding_to_awaiting_user_requested_reveal,
        {
            "delivery_kind": "REVEAL",
            "action_type": "TEACHING_REVEAL",
            "moment_state": "AWAITING_USER",
            "phase": "FULL_REVEAL",
            "support": "FULL_FORM_SHOWN",
            "closure": None,
        },
    ),
    StateCase(
        "sm1-deciding-to-awaiting-user-explanation",
        "SM §1 EXPLAIN; §3 EXPLANATION 相位",
        "EXPLAIN 的 v0 读法=continuation；COMPLETING 臂无 v0 路径（自裁 1）",
        _case_deciding_to_awaiting_user_explanation,
        {
            "delivery_kind": "EXPLANATION",
            "moment_state": "AWAITING_USER",
            "phase": "EXPLANATION",
            # The §1 COMPLETING arm has no v0 path (docstring §四.1): the
            # durable row still carries no completion after the explanation.
            "completion_outcome": None,
            "closure": None,
        },
    ),
    StateCase(
        "sm1-deciding-to-aborting-skip",
        "SM §1 DECIDING→ABORTING（SKIP）; §7",
        "SKIP → USER_SKIP，锁释放，无 completion outcome",
        _leaving_case(TeachingControlIntent.SKIP, "USER_SKIP", "cm-skip"),
        {
            "closure": "USER_SKIP",
            "moment_state": "CLOSED",
            "abort_reason": "USER_SKIP",
            "completion_outcome": None,
            "lock_rows": 0,
            "reason_in_canonical_vocabulary": True,
            "expected_reason": "USER_SKIP",
        },
    ),
    StateCase(
        "sm1-deciding-to-aborting-reject",
        "SM §1 DECIDING→ABORTING（SKIP/TOPIC SHIFT 族）; §7",
        "REJECT_TARGET → USER_REJECTED_TARGET",
        _leaving_case(
            TeachingControlIntent.REJECT_TARGET,
            "USER_REJECTED_TARGET",
            "cm-reject",
        ),
        {
            "closure": "USER_REJECTED_TARGET",
            "moment_state": "CLOSED",
            "abort_reason": "USER_REJECTED_TARGET",
            "completion_outcome": None,
            "lock_rows": 0,
            "reason_in_canonical_vocabulary": True,
            "expected_reason": "USER_REJECTED_TARGET",
        },
    ),
    StateCase(
        "sm1-deciding-to-aborting-topic-shift",
        "SM §1 DECIDING→ABORTING（TOPIC SHIFT）; §7",
        "CHANGE_TOPIC → USER_TOPIC_SHIFT",
        _leaving_case(
            TeachingControlIntent.CHANGE_TOPIC, "USER_TOPIC_SHIFT", "cm-topic"
        ),
        {
            "closure": "USER_TOPIC_SHIFT",
            "moment_state": "CLOSED",
            "abort_reason": "USER_TOPIC_SHIFT",
            "completion_outcome": None,
            "lock_rows": 0,
            "reason_in_canonical_vocabulary": True,
            "expected_reason": "USER_TOPIC_SHIFT",
        },
    ),
    StateCase(
        "sm1-deciding-to-aborting-switch",
        "SM §1 DECIDING→ABORTING（USER SWITCH）; §2/§11",
        "SWITCH_TARGET：先关旧 moment，再同 turn cycle_index+1",
        _switch_case,
        {
            "closure": "USER_SWITCH_TARGET",
            "moment_state": "CLOSED",
            "abort_reason": "USER_SWITCH_TARGET",
            "cycle_indexes": ["0", "1"],
            "next_cycle_is_the_new_one": True,
            "moment_rows": 1,
            "lock_rows": 0,
        },
    ),
    StateCase(
        "sm1-completing-to-terminal",
        "SM §1 COMPLETING→TEACHING_TERMINAL; §9",
        "终态与 TeachingLockLease 释放同事务（终态无锁）",
        _case_completing_to_terminal,
        {
            "state": "TEACHING_TERMINAL",
            "completion_outcome": "USER_SATISFIED",
            "abort_reason": None,
            "terminal_at_set": True,
            "lock_rows": 0,
        },
    ),
    StateCase(
        "sm1-aborting-to-terminal",
        "SM §1 ABORTING→TEACHING_TERMINAL; §7",
        "abort 以 §7 词收尾，同一事务释放锁",
        _case_aborting_to_terminal,
        {
            "state": "TEACHING_TERMINAL",
            "abort_reason": "POLICY_STOP",
            "completion_outcome": None,
            "lock_rows": 0,
        },
    ),
    StateCase(
        "sm1-terminal-to-resuming-to-closed",
        "SM §1 TEACHING_TERMINAL→RESUMING→CLOSED",
        "尾链单向：RESUMING 未置 closed_at，CLOSED 才置",
        _case_terminal_to_resuming_to_closed,
        {
            "resuming_state": "RESUMING",
            "closed_state": "CLOSED",
            "closed_at_set": True,
            "closed_at_was_none_while_resuming": True,
            "lock_rows": 0,
        },
    ),
    StateCase(
        "sm1-terminal-no-resume-arm",
        "SM §1:54 TEACHING_TERMINAL→CLOSED（no resume 臂）",
        "无需 resume 的 terminal episode 直接闭合（durable-only 词的 durable 面用法）",
        _case_terminal_no_resume_arm,
        {
            "terminal_state": "TEACHING_TERMINAL",
            "closed_state": "CLOSED",
            "closed_at_set": True,
            "completion_outcome": "NO_FURTHER_VALUE",
            "lock_rows": 0,
            "durable_state": "CLOSED",
        },
    ),
    StateCase(
        "sm1-closed-is-final",
        "SM §2 Closed 不允许 reopen",
        "CLOSED 后转换拒（含 reopen）/回复拒；future teaching=新 moment",
        _case_closed_is_final,
        {
            "reopen_code": "CONFLICT",
            "reopen_says_never_reopened": True,
            "reply_refused": "CONFLICT",
            "new_moment_id_differs": True,
            "moment_rows": 2,
            "closed_moment_state": "CLOSED",
        },
    ),
    StateCase(
        "sm1-closed-only-from-the-tail",
        "SM §1 尾链入口; §9（终态无锁）",
        "未终态直 CLOSED 拒（AWAITING_USER/DECIDING 两态实测），不产出「CLOSED+持锁」",
        _case_closed_only_from_the_tail,
        {
            "close_from_awaiting_user": "CONFLICT",
            "refusal_names_the_tail": True,
            "deciding_state": "DECIDING_NEXT_ACTION",
            "close_from_deciding": "CONFLICT",
            "moment_still_live": "DECIDING_NEXT_ACTION",
            "lock_rows": 1,
            "no_closed_row": 0,
        },
    ),
    StateCase(
        "sm1-terminal-tail-is-one-way",
        "SM §1 尾链; §20",
        "TEACHING_TERMINAL 只回 RESUMING/CLOSED；非 COMPLETING/ABORTING 直 TERMINAL 拒",
        _case_terminal_tail_is_one_way,
        {
            "terminalize_from_awaiting_user": "CONFLICT",
            "lock_still_held": 1,
            "terminal_back_to_awaiting_user": "CONFLICT",
            "back_names_both_legal_arms": True,
            "terminal_replay_is_ok": True,
            "replayed_state": "TEACHING_TERMINAL",
        },
    ),
    StateCase(
        "sm3-ladder-refusals",
        "SM §3 双单调 + 天花板",
        "phase 回退/support 回退/support 超天花板全拒；前进与同档许可",
        _case_ladder_refusals,
        {
            "phase_back": True,
            "support_back": True,
            "support_over_ceiling": True,
            "forward_is_allowed": True,
            "same_rung_is_allowed": True,
        },
    ),
    StateCase(
        "sm3-reconcile-never-lowers",
        "SM §3 前向单调（崩溃对账）",
        "对账按绝对梯级重建且只前进：已落更高梯级不被拉低",
        _case_reconcile_never_lowers,
        {
            "phase_after": "HINT_STRUCTURAL",
            "support_after": "STRUCTURAL_HINT",
            "assistant_turns": 2,
            "hint_deliveries": 1,
            "replayed_turn_matches": True,
        },
    ),
    StateCase(
        "sm8-limits-matrix",
        "SM §8 hard/soft caps + terminalizing 豁免",
        "hard cap 挡 retry-like/非终态动作，terminalizing 收尾恒许可；soft 需显式请求",
        _case_limits_matrix,
        {
            "hard_attempt_hint": {
                "allowed": False,
                "closing_only": True,
                "reason": "HARD_ATTEMPT_LIMIT",
                "user_request_required": False,
            },
            "hard_attempt_retry": {
                "allowed": False,
                "closing_only": True,
                "reason": "HARD_ATTEMPT_LIMIT",
                "user_request_required": False,
            },
            "hard_attempt_reveal_exempt": {
                "allowed": True,
                "closing_only": False,
                "reason": None,
                "user_request_required": False,
            },
            "hard_turn_hint": {
                "allowed": False,
                "closing_only": True,
                "reason": "HARD_TEACHING_TURN_LIMIT",
                "user_request_required": False,
            },
            "hard_turn_explanation": {
                "allowed": False,
                "closing_only": True,
                "reason": "HARD_TEACHING_TURN_LIMIT",
                "user_request_required": False,
            },
            "hard_turn_reveal_exempt": {
                "allowed": True,
                "closing_only": False,
                "reason": None,
                "user_request_required": False,
            },
            "soft_without_request": {
                "allowed": False,
                "closing_only": False,
                "reason": None,
                "user_request_required": True,
            },
            "soft_with_request": {
                "allowed": True,
                "closing_only": False,
                "reason": None,
                "user_request_required": False,
            },
            "soft_terminalizing_without_request": {
                "allowed": True,
                "closing_only": False,
                "reason": None,
                "user_request_required": False,
            },
        },
    ),
    StateCase(
        "sm1-awaiting-user-no-attempt-jump",
        "SM §1/§4（AWAITING_USER 无 attempt 直跳的后果）",
        "控制型回复不伪造 attempt；durable 面拒绝在 AWAITING_USER 记 attempt",
        _case_awaiting_user_no_attempt_jump,
        {
            "control_reply_delivery": "HINT",
            "attempt_rows": 0,
            "abstain_rows": 0,
            "direct_attempt_refused": "VALIDATION_FAILED",
            "moment_state": "AWAITING_USER",
        },
    ),
    StateCase(
        "sm6-completion-outcomes-partition",
        "SM §6 七词",
        "五词有生产路径（实测），两词 durable-only（留痕）",
        _case_completion_outcomes_partition,
        {
            "produced": {
                "SUCCESS_UNSUPPORTED": "SUCCESS_UNSUPPORTED",
                "SUCCESS_SUPPORTED": "SUCCESS_SUPPORTED",
                "SUCCESS_ALTERNATIVE": "SUCCESS_ALTERNATIVE",
                "PARTIAL_PROGRESS": "PARTIAL_PROGRESS",
                "REVEALED": "REVEALED",
            },
            "durable_only": ["NO_FURTHER_VALUE", "USER_SATISFIED"],
            "canonical_words": [
                "NO_FURTHER_VALUE",
                "PARTIAL_PROGRESS",
                "REVEALED",
                "SUCCESS_ALTERNATIVE",
                "SUCCESS_SUPPORTED",
                "SUCCESS_UNSUPPORTED",
                "USER_SATISFIED",
            ],
        },
    ),
    StateCase(
        "sm7-abort-reasons-partition",
        "SM §7 十四词",
        "九词编排面实测；两词仅映射面；三词不可构造（无 NLU/无 TTL/硬上限是转换）",
        _case_abort_reasons_partition,
        {
            "produced": {
                "USER_SKIP": "USER_SKIP",
                "USER_REJECTED_TARGET": "USER_REJECTED_TARGET",
                "USER_TOPIC_SHIFT": "USER_TOPIC_SHIFT",
                "USER_SWITCH_TARGET": "USER_SWITCH_TARGET",
                "POLICY_STOP": "POLICY_STOP",
                "CONTENT_INVALID": "CONTENT_INVALID",
                "SYSTEM_FAILURE": "SYSTEM_FAILURE",
                "DELIVERY_FAILURE": "DELIVERY_FAILURE",
                "SYSTEM_RECOVERY_ABORT": "SYSTEM_RECOVERY_ABORT",
            },
            "mapping_only": {
                "SNAPSHOT_INVALIDATED": "SNAPSHOT_INVALIDATED",
                "PRE_DELIVERY_INVALIDATED": "PRE_DELIVERY_INVALIDATED",
            },
            "unreachable": [
                "AMBIGUOUS_EXIT",
                "ATTEMPT_LIMIT",
                "EXPIRED",
            ],
            "canonical_words": [
                "AMBIGUOUS_EXIT",
                "ATTEMPT_LIMIT",
                "CONTENT_INVALID",
                "DELIVERY_FAILURE",
                "EXPIRED",
                "POLICY_STOP",
                "PRE_DELIVERY_INVALIDATED",
                "SNAPSHOT_INVALIDATED",
                "SYSTEM_FAILURE",
                "SYSTEM_RECOVERY_ABORT",
                "USER_REJECTED_TARGET",
                "USER_SKIP",
                "USER_SWITCH_TARGET",
                "USER_TOPIC_SHIFT",
            ],
            "deny_reason_codes": [
                '["TEACHING_LOCK_INVALID"]',
                '["CONTENT_INVALID"]',
            ],
        },
    ),
    StateCase(
        "sm2-switch-target-cycle-chain",
        "SM §2/§11 cycle_index 递增",
        "多目标连切：每个 switch turn 的 [0,1]；durable 同 turn 链 0,1,2",
        _case_switch_target_cycle_chain,
        {
            "per_turn_cycle_indexes": [["0", "1"], ["0", "1"], ["0", "1"]],
            "closures": [
                "USER_SWITCH_TARGET",
                "USER_SWITCH_TARGET",
                "USER_SWITCH_TARGET",
            ],
            "moment_rows": 3,
            "lock_rows": 0,
            "durable_chain": ["0", "1", "2"],
            "cycle_ids_are_unique": True,
        },
    ),
    StateCase(
        "sm12-continuation-basis",
        "SM §12.1/§8 ACTIVE_MOMENT authorization",
        "continuation 恒 USER_REQUESTED_CONTINUE + ACTIVE_MOMENT；AUTO_CONTINUE 契约拒",
        _case_continuation_basis,
        {
            "gate_context": "USER_REQUESTED_CONTINUE",
            "authorization_basis": "ACTIVE_MOMENT",
            "authorization_status": "VALID",
            "status": "SUCCEEDED",
            "auto_continue_contract_error": "GateInputError",
        },
    ),
    StateCase(
        "sm9-own-evidence-keeps-continuation",
        "SM §9/§12.1 本 Moment 新 Evidence 不使自身 continuation 失效",
        "attempt 落证据推 watermark，随后的 continuation 仍 ALLOW（无 DEGRADED）",
        _case_own_evidence_keeps_continuation,
        {
            "watermark_before": 0,
            "watermark_after": 1,
            "watermark_advanced": True,
            "claims": 1,
            "first_continuation": "RETRY",
            "second_continuation_gate": "ALLOW",
            "continuation_allows": 2,
            "degraded_rows": 0,
        },
    ),
    StateCase(
        "sm4-attempt-and-control-coexist",
        "SM §4 envelope 非互斥单枚举",
        "成功 attempt 显式索要 hint：attempt 被评估落证，控制意图继续教学",
        _case_attempt_and_control_coexist,
        {
            "evaluation_outcome": "SUCCESS",
            "delivery_kind": "HINT",
            "moment_state": "AWAITING_USER",
            "closure": None,
            "attempt_rows": 1,
            "claims": 1,
            "stayed_open": True,
        },
    ),
    StateCase(
        "sm17-attempt-chain-under-pressure",
        "SM §4 五步 / §17 durable 顺序",
        "压力序列下 attempt→evaluation→gate→action→落梯顺序稳定；恒链无悬空",
        _case_attempt_chain_under_pressure,
        {
            "attempt_round_order": {
                "attempt_before_evaluation": True,
                "evaluation_before_gate": True,
                "gate_before_action": True,
                "action_before_landing": True,
            },
            "attempts": [
                (1, "SEMANTIC_HINT"),
                (2, "STRUCTURAL_HINT"),
                (3, "STRUCTURAL_HINT"),
            ],
            "evaluations": [
                (1, "FAILURE"),
                (2, "FAILURE"),
                (3, "SUCCESS"),
            ],
            "proposal_refs_link_their_attempt": True,
            "claim_groups_match_attempts_in_order": True,
            "claim_outcomes": [
                ("FAILURE", "NEGATIVE"),
                ("FAILURE", "NEGATIVE"),
                ("SUCCESS", "POSITIVE"),
            ],
            "first_outcome": "FAILURE",
            "second_outcome": "FAILURE",
            "third_closure": "SUCCESS_SUPPORTED",
            "gate_allows": 4,
        },
    ),
)


# ---------------------------------------------------------------------------
# the runner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[case.case_id for case in CASES])
def test_oq024a_state_case(
    case: StateCase,
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    learning_controller: LearningController,
    decision_cycle_store,
    teaching_controller: TeachingController,
    target_provider,
) -> None:
    """One OQ-024A case: build the initial state, act, snapshot the outcome.

    The observation is compared *whole* against the case's expected dict —
    a case either reproduces the canonical outcome exactly or it does not.
    """

    del conversation
    env = CaseEnv(
        db=db,
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        learning_controller=learning_controller,
        decision_cycle_store=decision_cycle_store,
        teaching=teaching_controller,
        targets=target_provider,
    )
    observed = case.run(env)
    assert observed == case.expected, (
        f"{case.case_id} ({case.sm_ref}) — {case.intent}"
    )
