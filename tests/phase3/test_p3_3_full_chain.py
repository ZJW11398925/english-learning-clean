"""P3-3 全链验收（TASK-OPI-5ba74efc-….47 / VAL-OPI-2babb21e-….13）。

本文件是 Phase 3 的**端到端验收场景集**：真实链路
sample CharacterPackage（P3-0 正常链 fixture）→ fixture 教学目标
（tests/phase3/target_fixtures.py 的 14 个 validated targets；IP §17-08 的
content runtime 属后续独立刀，本刀以 tests 侧 fixture 供给，留痕于此）
→ ``request_teaching``（Gate ALLOW / CP2 五事实）→ opening 交付 →
``respond_to_teaching``（attempt → evaluation → LOR → Evidence commit）
→ rebuild → LearnerState。场景 a-f 与 VAL 命题逐条对应：

a) ``test_a_*``  **before≠after 可追溯**：教学前后各取一份 LearnerTargetState
   快照，断言语义差异逐条映射到具体 canonical EvidenceClaim（claim id /
   outcome / polarity / support）与 LOR lineage（opportunity_id → LOR →
   moment → attempt → user turn），且双向对账——差异清单里没有一条无 claim
   可归因，claim 清单里没有一条不落在差异上（无质量 claim 是 §10 的合法
   例外，本文件对它单独断言"确实什么都没改"）。
b) ``test_b_*``  **moment 不直接改 mastery**：绕过 Learning kernel 直改投影
   行后，rebuild 语义与教学链读数不变（行为面反例钉；结构面
   ``teaching`` 包无投影写入面的 AST 钉在
   tests/phase3/test_import_boundaries.py）。
c) ``test_c_*``  **full reveal 后不误记 independent evidence**
   （DOMAIN_MODEL §15）。
d) ``test_d_*``  **CLOSED 不 reopen**，且新请求 = 新 moment。
e) ``test_e_*``  **学习腿失败不拖垮聊天**（RA §21 降级）。
f) ``test_f_*``  **多轮累积**：同 moment 第二次 attempt → 新 Evidence →
   再 rebuild → 再 before/after 对账。

对账方法（本文件的证据学口径，独立于实现）：

- 差异侧写死来源——每一条 ``dimensions.*`` 差异必须落在 **claim 的维度集**
  （按冻结行为基线
  ``behavioral_baselines/estimator/BF-01_Estimator_V1_Operational_Spec_v1.1.md``
  §5 positive downward entailment / §6 negative propagation 手工转写，见
  :data:`_POSITIVE_ENTAILMENT` / :func:`_expected_dimensions`）上；coverage
  块按 DATA_MODEL §11 的定义从 durable claim 清单复算后逐项比对；watermark
  必须等于 durable commit 数。本文件**不导入** elc.learning.estimator 的映射表
  ——测试若与实现同构即无证明力。
- claim 侧可验证——每条 claim 必须在其 §5/§6 维度上留下
  ``last_relevant_evidence_at`` 等于该 claim 自身时间的痕迹；canonical
  意义上的无质量 claim（§10：ABSTAIN 或 confidence 低于地板）必须**不改**
  任何维度估计。
- 两个二次派生维度（transfer / support_dependency）不参与 §5/§6 维度集
  断言：它们有各自的派生门（§18 资源 transfer 需 ≥2 个 strong cluster；
  §21 support dependency 需达到诊断质量地板），本文件对它们的**未移动**
  单独断言（本刀场景里都没有满足各自门槛）。

红线自查：本文件全部经 Write/Edit 通道落盘；测试内 SQL 全参数绑定；
未触碰 migrations / behavioral_baselines / docs 六 canonical；不越 Phase 4+ 面。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.learning.controller import LearningController
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidenceModality,
    EvidencePolarity,
    EvidenceStatus,
    ExposureLevel,
    PerformanceType,
    SupportLevel,
)
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
    sample_character_package,
)
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    EvaluatorVersion,
    EvidenceGroupId,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.types import InputEnvelope
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest

from .conftest import CONV, make_lease

REQUESTED_AT = "2026-09-21T10:00:00+00:00"
MODALITY = "TEXT_PRODUCTION"
FOCUS_TARGET = "res-hedge-i-think"
FOCUS_CAPABILITY = "cap-eval-hedged-opinion"
CANONICAL_ANSWER = "I think it is going to rain."
ALTERNATIVE_ANSWER = "It might rain."
#: Misses the canonical form, the alternative realizations and every required
#: slot group of res-hedge-i-think ("rain" + think/guess/reckon) → FAILURE.
WRONG_ANSWER = "The weather is terrible today."
#: 种子 evidence 的 dated 时间戳：BF-01 §22 只让 strong retrieval 决定 freshness，
#: 时间不改历史 ability mass；把种子钉在过去就是为了让"新 strong retrieval
#: 把 freshness 从空推到 FRESH"这一条差异归属明确（旧时间戳不是新证据）。
SEED_CREATED_AT = "2020-01-01T00:00:00+00:00"

_BASE_DIMENSIONS = (
    "recognition",
    "guided_production",
    "independent_production",
    "spontaneous_production",
    "accuracy",
    "pragmatic_control",
)
_DERIVED_DIMENSIONS = ("transfer", "support_dependency")
_ALL_DIMENSIONS = _BASE_DIMENSIONS + _DERIVED_DIMENSIONS

#: BF-01 §5 positive downward entailment, transcribed by hand from the frozen
#: behavioural baseline into the estimator's dimension vocabulary (the
#: estimator's own weight table is deliberately not imported: see the module
#: docstring). A positive claim of one performance type feeds exactly these
#: dimensions — "强行为可以弱支持低层能力，但仍是同一条 Evidence 的多维
#: contribution，不是多份独立证据".
_POSITIVE_ENTAILMENT: dict[str, tuple[str, ...]] = {
    "RECOGNITION": ("recognition",),
    "IMITATIVE_PRODUCTION": ("recognition", "guided_production"),
    "GUIDED_PRODUCTION": ("recognition", "guided_production"),
    "INDEPENDENT_PRODUCTION": (
        "recognition",
        "guided_production",
        "independent_production",
    ),
    "SPONTANEOUS_PRODUCTION": (
        "recognition",
        "guided_production",
        "independent_production",
        "spontaneous_production",
    ),
    "SELF_REPAIR": (
        "recognition",
        "guided_production",
        "independent_production",
        "spontaneous_production",
    ),
}

#: BF-01 §22/§16 strong-retrieval membership, as the test reads it off a
#: durable claim (POSITIVE SUCCESS at INDEPENDENT/SPONTANEOUS with an
#: evaluator confidence above the §7 floor). Used for the freshness rule.
_STRONG_PERFORMANCE = ("INDEPENDENT_PRODUCTION", "SPONTANEOUS_PRODUCTION")


def _expected_dimensions(claim: dict[str, Any]) -> frozenset[str]:
    """The BF-01 §5/§6 dimension set of one claim (test-side re-derivation).

    Positive: §5 downward entailment. Negative: §6's asymmetric propagation
    ("Negative evidence 只影响 Opportunity/Attempt 直接支持诊断的维度") — a
    low-support FAILED_ATTEMPT diagnoses the attempted behavior itself, a
    supported one the guided rung, a MISUSE primarily accuracy. Mass-free
    claims (§10 ABSTAIN / below the confidence floor) touch nothing at all,
    which is how "a claim that changed nothing" stays honest rather than
    unexplained.
    """

    performance = str(claim["performance_type"])
    polarity = str(claim["polarity"])
    outcome = str(claim["outcome"])
    if outcome == "ABSTAIN" or float(claim["evaluator_confidence"]) < 0.50:
        return frozenset()
    if polarity == "POSITIVE":
        return frozenset(_POSITIVE_ENTAILMENT.get(performance, ()))
    if polarity == "NEGATIVE":
        low_support = str(claim["support_level"]) in ("NONE", "CONTEXT_ONLY")
        if performance == "RECOGNITION":
            return frozenset({"recognition"})
        if performance == "FAILED_ATTEMPT":
            if low_support:
                # §6 NATURAL low-support FAILED_ATTEMPT → the attempted
                # behavior itself; never the guided/recognition rungs the
                # attempt did not use. The elicitation word is the store's
                # documented default fill.
                return frozenset(
                    {"spontaneous_production", "independent_production"}
                )
            return frozenset({"guided_production"})
        if performance == "MISUSE":
            return frozenset({"accuracy", "independent_production"})
        return frozenset()
    return frozenset()


def _is_strong_retrieval(claim: dict[str, Any]) -> bool:
    return (
        str(claim["polarity"]) == "POSITIVE"
        and str(claim["outcome"]) == "SUCCESS"
        and str(claim["performance_type"]) in _STRONG_PERFORMANCE
        and float(claim["evaluator_confidence"]) >= 0.70
    )


# ---------------------------------------------------------------------------
# assembly / driving helpers
# ---------------------------------------------------------------------------


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycles,
    teaching,
    targets,
    *,
    provider: ScriptedPersonaProvider | None = None,
    learning_controller: LearningController | None = None,
) -> ConversationCoordinator:
    """The P3-1A/P3-1B assembly plus the P3-0 CharacterPackage fixture: the
    real chain carries a canonical §5.1 package into the prompt compiler."""

    persona = PersonaRuntime(
        actions=generation_store,
        provider=provider if provider is not None else ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=make_lease(fence),
        conversation_commands=store,
        conversation_queries=store,
        persona=persona,
        generation_actions=generation_store,
        learning=learning,
        character_package=sample_character_package(),
        decision_cycles=decision_cycles,
        learning_controller=(
            LearningController(learning)
            if learning_controller is None
            else learning_controller
        ),
        teaching=teaching,
        targets=targets,
    )


def _chat(coordinator: ConversationCoordinator, cmid: str, text: str, turn_no: int):
    """One Basic Persona Conversation turn (the IP §1.5 slice's first leg)."""

    result = coordinator.begin_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{cmid}"),
                client_message_id=ClientMessageId(cmid),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{turn_no}",
                received_at=REQUESTED_AT,
            ),
            raw_content=text,
            runtime_version="runtime-v1",
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _open(coordinator: ConversationCoordinator, cmid: str, target: str = FOCUS_TARGET):
    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=target,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _reply(coordinator: ConversationCoordinator, envelope, cmid: str):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=envelope,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )


def _reply_ok(coordinator: ConversationCoordinator, envelope, cmid: str):
    result = _reply(coordinator, envelope, cmid)
    assert isinstance(result, Ok), result
    return result.value


def _attempt(
    text: str, intent: TeachingControlIntent = TeachingControlIntent.CONTINUE
) -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(
        control_intent=intent,
        attempt_present=True,
        attempt=AttemptPayload(text=text),
    )


def _control(intent: TeachingControlIntent) -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(control_intent=intent)


# ---------------------------------------------------------------------------
# the "before" state: canonical evidence through Learning's own face
# ---------------------------------------------------------------------------


def _seed_claim(target_id: str) -> EvidenceClaimView:
    """One canonical §6 claim for the *before* state.

    It is committed through Learning's own authority face
    (``commit_evidence_group``, the Phase 0 protocol every non-teaching
    producer uses), never by writing the projection: the before-state has to
    be real evidence for the after-difference to mean anything. A
    RECOGNITION / SUCCESS / NONE-support claim is the weakest canonical
    observation, so every later dimension movement is attributable to the
    teaching claim alone.
    """

    return EvidenceClaimView(
        evidence_claim_id=f"ecl-seed-{target_id}",
        claim_role="SEED",
        scope="RESOURCE" if target_id.startswith("res-") else "CAPABILITY",
        performance_type=PerformanceType.RECOGNITION,
        evidence_modality=EvidenceModality.TEXT_PRODUCTION,
        qualifiers=(),
        polarity=EvidencePolarity.POSITIVE,
        outcome=AttemptOutcome.SUCCESS,
        support=SupportLevel.NONE,
        exposure=ExposureLevel.NONE,
        evaluator_confidence=0.9,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance="seed:basic-persona-conversation",
        target_id=target_id,
    )


def _seed(
    db: sqlite3.Connection,
    learning: LearningController,
    *,
    group_id: str,
    target_ids: tuple[str, ...],
    source_turn_id: str,
) -> None:
    """Commit one canonical seed group and date it.

    Fixture preparation, not a bypass: the group goes through Learning's own
    validation + commit, and the date is set afterwards because BF-01 §22
    freshness reads the claim's own durable time. One claim per target (the
    §6 shape a teaching group with a capability linkage has too: one
    observable behavior, claims that independently target RESOURCE/CAPABILITY).

    ``source_turn_id`` is a *command* turn of this conversation — the P2A
    deterministic producer already owns the (turn × modality) evidence-group
    slot of a chat turn (DATA_MODEL §6 "one observable behavior per turn"), so
    a target-bearing claim of this phase anchors on a turn whose own behavior
    is the teaching command.
    """

    committed = learning.commit_evidence_group(
        EvidenceGroupRecord(
            evidence_group_id=EvidenceGroupId(group_id),
            moment_id=None,
            attempt_id=None,
            target_id=TargetId(target_ids[0]),
            evaluator_version=EvaluatorVersion("evaluator-seed-v1"),
            claims=tuple(_seed_claim(target) for target in target_ids),
        ),
        source_turn_id=source_turn_id,
        conversation_id=str(CONV),
    )
    assert isinstance(committed, Ok), committed
    db.execute(
        "UPDATE evidence_claim SET created_at = ? WHERE evidence_group_id = ?",
        (SEED_CREATED_AT, group_id),
    )
    db.commit()


def _rebuild(learning: LearningController, target_id: str) -> None:
    rebuilt = learning.rebuild_learner_state(
        TargetId(target_id), EvidenceModality.TEXT_PRODUCTION
    )
    assert isinstance(rebuilt, Ok), rebuilt


# ---------------------------------------------------------------------------
# state reads / reconciliation
# ---------------------------------------------------------------------------


def _state(db: sqlite3.Connection, target_id: str) -> dict:
    rows = db.execute(
        "SELECT state_json FROM learner_target_state"
        " WHERE target_id = ? AND evidence_modality = ?",
        (target_id, MODALITY),
    ).fetchall()
    assert len(rows) == 1, f"expected exactly one §11 row for {target_id}"
    return json.loads(str(rows[0][0]))


def _flat(document: dict, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in document.items():
        path = key if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flat(value, path))
        else:
            flat[path] = value
    return flat


def _diff(before: dict, after: dict) -> dict[str, tuple[Any, Any]]:
    before_flat = _flat(before)
    after_flat = _flat(after)
    assert set(before_flat) == set(after_flat), "state documents diverge in shape"
    return {
        path: (before_flat[path], after_flat[path])
        for path in sorted(before_flat)
        if before_flat[path] != after_flat[path]
    }


_CLAIM_COLUMNS = (
    "evidence_claim_id",
    "evidence_group_id",
    "opportunity_id",
    "target_type",
    "target_id",
    "evidence_modality",
    "performance_type",
    "polarity",
    "outcome",
    "support_level",
    "answer_exposure_state",
    "evaluator_confidence",
    "status",
    "created_at",
    "elicitation_type",
    "attempt_id",
    "claim_role",
    "teaching_moment_id",
    "source_turn_id",
    "conversation_id",
    "persona_id",
)


def _claims(db: sqlite3.Connection) -> tuple[dict[str, Any], ...]:
    """Every durable claim, as a dict (the reconciliation's claim inventory)."""

    rows = db.execute(
        f"SELECT {', '.join(_CLAIM_COLUMNS)} FROM evidence_claim"
        " ORDER BY created_at, evidence_claim_id"
    ).fetchall()
    return tuple(dict(zip(_CLAIM_COLUMNS, row)) for row in rows)


def _claim_ids(db: sqlite3.Connection) -> frozenset[str]:
    return frozenset(
        str(row[0])
        for row in db.execute(
            "SELECT evidence_claim_id FROM evidence_claim"
        ).fetchall()
    )


def _new_claims(
    db: sqlite3.Connection, before_ids: frozenset[str]
) -> tuple[dict[str, Any], ...]:
    return tuple(
        claim
        for claim in _claims(db)
        if str(claim["evidence_claim_id"]) not in before_ids
    )


def _cluster_key(claim: dict[str, Any]) -> str:
    """The BF-01 §12 correlation cluster key of one claim (test-side).

    A teaching attempt inside one moment is one cluster; an unlinked claim
    clusters by conversation × day × persona (the estimator's documented
    fallbacks collapse the context/realization keys onto their unknowns —
    the §6 column set carries novelty reals, not context keys).
    """

    moment = claim["teaching_moment_id"]
    if moment is not None:
        return f"teach:{moment}"
    persona = claim["persona_id"]
    return (
        f"natural:{claim['conversation_id']}:{str(claim['created_at'])[:10]}:"
        f"{persona if persona is not None else 'persona:none'}"
    )


def _expected_coverage(
    db: sqlite3.Connection, target_id: str
) -> dict[str, int]:
    """The §11 coverage block re-computed from the durable claim inventory.

    DATA_MODEL §11 coverage counts (BF-01 §12/§15 diversity basis) are a
    function of the target × modality's ACTIVE claims, so the projection's
    block is checked against the claims themselves rather than asserted from
    the implementation's own numbers.
    """

    active = tuple(
        claim
        for claim in _claims(db)
        if str(claim["target_id"]) == target_id
        and str(claim["evidence_modality"]) == MODALITY
        and str(claim["status"]) == "ACTIVE"
    )
    groups = {str(claim["evidence_group_id"]) for claim in active}
    clusters = {_cluster_key(claim) for claim in active}
    return {
        "evidence_groups": len(groups),
        "independent_clusters": len(clusters),
        "sessions": len({str(claim["conversation_id"]) for claim in active}),
        "days": len({str(claim["created_at"])[:10] for claim in active}),
        # The §6 column set carries novelty reals, not context/realization
        # keys, so both counts collapse onto one unknown value (documented).
        "contexts": 1 if active else 0,
        "personas": len(
            {
                "none" if claim["persona_id"] is None else str(claim["persona_id"])
                for claim in active
            }
        ),
        "realizations": 1 if active else 0,
        "modalities": len({str(claim["evidence_modality"]) for claim in active}),
    }


def _reconcile(
    db: sqlite3.Connection,
    *,
    target_id: str,
    before: dict,
    after: dict,
    new_claims: tuple[dict[str, Any], ...],
) -> dict[str, tuple[Any, Any]]:
    """The bidirectional before≠after reconciliation (scenarios a/c/f).

    Direction 1 — every difference is attributable: base-dimension paths must
    belong to the §5/§6 dimension set of a new claim, coverage paths must
    equal the value re-computed from the claim inventory, the watermark must
    equal the durable commit count, and a freshness move must be caused by a
    new strong-retrieval claim.

    Direction 2 — every claim is accounted for: each claim's §5/§6 dimensions
    carry ``last_relevant_evidence_at`` equal to that claim's own time, and
    a mass-free claim (§10) leaves every dimension estimate untouched.

    Returns the raw diff so each scenario can assert its own specifics.
    """

    diff = _diff(before, after)
    assert diff, "the teaching chain must move the before-state (before≠after)"

    claim_dims: set[str] = set()
    for claim in new_claims:
        claim_dims |= set(_expected_dimensions(claim))

    changed_dims = {
        path.split(".")[1] for path in diff if path.startswith("dimensions.")
    }
    assert changed_dims <= set(_ALL_DIMENSIONS)
    moved_base = changed_dims & set(_BASE_DIMENSIONS)
    unexplained = {
        path
        for path in diff
        if path.startswith("dimensions.")
        and path.split(".")[1] in _BASE_DIMENSIONS
        and path.split(".")[1] not in claim_dims
    }
    assert not unexplained, (
        "base dimension(s) changed with no claim that explains them:"
        f" {sorted(unexplained)}; claims touch {sorted(claim_dims)}"
    )
    assert moved_base <= claim_dims, (
        f"base dimensions {sorted(moved_base - claim_dims)} moved without a"
        " claim (§5/§6 entailment)"
    )

    for claim in new_claims:
        for dim in _expected_dimensions(claim):
            assert (
                after["dimensions"][dim]["last_relevant_evidence_at"]
                == claim["created_at"]
            ), f"claim {claim['evidence_claim_id']} did not touch {dim}"
        assert str(claim["target_id"]) == target_id

    # No mass-free claim may move a dimension estimate (BF-01 §10).
    for claim in new_claims:
        if _expected_dimensions(claim):
            continue
        for dim in _BASE_DIMENSIONS:
            assert (
                after["dimensions"][dim]["estimate"]
                == before["dimensions"][dim]["estimate"]
            ), f"mass-free claim {claim['evidence_claim_id']} moved {dim}"

    for counter, value in _expected_coverage(db, target_id).items():
        assert after["coverage"][counter] == value, (
            f"coverage.{counter}={after['coverage'][counter]} but the claim"
            f" inventory says {value}"
        )

    commits = db.execute("SELECT COUNT(*) FROM evidence_commit").fetchone()[0]
    assert after["meta"]["evidence_watermark"] == commits
    assert before["meta"]["evidence_watermark"] <= after["meta"]["evidence_watermark"]

    if [path for path in diff if path.startswith("freshness.")]:
        assert any(_is_strong_retrieval(claim) for claim in new_claims), (
            "freshness moved with no new strong-retrieval claim (§22)"
        )

    # Derived dimensions: each has its own gate, and neither is satisfied by
    # a single teaching attempt inside one moment (§18 needs ≥2 strong
    # clusters; §21 needs the diagnostic mass floor).
    strong_clusters = {
        _cluster_key(claim)
        for claim in _claims(db)
        if str(claim["target_id"]) == target_id and _is_strong_retrieval(claim)
    }
    if "dimensions.transfer.estimate" in diff:
        assert len(strong_clusters) >= 2, "transfer moved below the §18 gate"
    unknown_blocks = {
        path.split(".")[0] for path in diff
    }
    assert unknown_blocks <= {
        "dimensions",
        "coverage",
        "freshness",
        "projection",
        "meta",
    }, f"unattributable diff blocks: {sorted(unknown_blocks)}"
    return diff


def _assert_lineage(
    db: sqlite3.Connection,
    claim: dict[str, Any],
    *,
    moment_id: str,
    attempt_id: str,
    reply_turn_id: str,
) -> None:
    """One claim's full LOR lineage, pointer by pointer:

    claim.opportunity_id → LearningOpportunityRecord（moment + target +
    attempt_observed）→ TeachingMoment → AttemptRecord → the reply turn's user
    turn → the reply turn itself. Every hop is a durable row read back.
    """

    assert claim["teaching_moment_id"] == moment_id
    assert claim["attempt_id"] == attempt_id
    assert claim["source_turn_id"] == reply_turn_id
    assert claim["opportunity_id"] is not None
    assert claim["claim_role"] in ("FOCUS_TARGET", "CAPABILITY_LINKAGE")

    moment = db.execute(
        "SELECT focus_target, lifecycle_state FROM teaching_moment"
        " WHERE moment_id = ?",
        (moment_id,),
    ).fetchone()
    assert moment is not None
    focus_target = json.loads(str(moment[0]))

    lor = db.execute(
        "SELECT target_type, target_id, opportunity_type,"
        " target_explicitness, attempt_observed,"
        " alternative_realizations_allowed, teaching_moment_id,"
        " source_turn_id"
        " FROM learning_opportunity_record WHERE learning_opportunity_id = ?",
        (claim["opportunity_id"],),
    ).fetchone()
    assert lor is not None, "a teaching claim must name a durable opportunity"
    assert lor[6] == moment_id
    # The opportunity is the moment's own focal opportunity (its focus
    # target); the §5 capability-linkage claim is the one sanctioned exception
    # — it speaks about the CAPABILITY the focus RESOURCE realizes and stays
    # linked to the same opportunity (elc.learning.store's LOR relaxation).
    assert lor[0] == focus_target["target_type"]
    assert lor[1] == focus_target["target_id"]
    assert lor[2] == "ELICITED" and lor[3] == "EXPLICIT_TARGET"
    assert lor[4] == 1  # attempt_observed
    assert lor[5] == 1  # alternative_realizations_allowed
    assert lor[7] == reply_turn_id
    if claim["claim_role"] == "CAPABILITY_LINKAGE":
        assert claim["target_type"] == "CAPABILITY"
    else:
        assert claim["target_type"] == focus_target["target_type"]
        assert claim["target_id"] == focus_target["target_id"]

    attempt = db.execute(
        "SELECT moment_id, attempt_index, user_turn_id FROM attempt_record"
        " WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()
    assert attempt is not None
    assert attempt[0] == moment_id
    user_turn = db.execute(
        "SELECT turn_id FROM user_turn WHERE user_turn_id = ?",
        (attempt[2],),
    ).fetchone()
    assert user_turn is not None and str(user_turn[0]) == reply_turn_id


def _base_dimension_paths(diff: dict[str, tuple[Any, Any]]) -> set[str]:
    return {
        path.split(".")[1]
        for path in diff
        if path.startswith("dimensions.")
        and path.split(".")[1] in _BASE_DIMENSIONS
    }


# ---------------------------------------------------------------------------
# a) before ≠ after, claim by claim
# ---------------------------------------------------------------------------


def test_a_success_attempt_moves_the_projection_and_every_delta_maps_to_a_claim(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario a (SUCCESS leg): the full chain, with the before-difference
    reconciled against the durable claim inventory in both directions."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    learning_controller = LearningController(learning)

    # The IP §1.5 first slice's opening leg: a real Basic Persona Conversation
    # turn, then the command turn of the explicit TeachingMoment, then the
    # canonical evidence of the *before* state on the focus target, rebuilt
    # into the Estimator's LearnerState. The before-snapshot is taken before
    # the attempt — the only step that writes evidence — so every difference
    # below belongs to the teaching attempt.
    _chat(coordinator, "cm-a-chat", "I like this cafe.", 1)
    opened = _open(coordinator, "cm-a-open")
    assert opened.gate_decision == "ALLOW"
    _seed(
        db,
        learning_controller,
        group_id="eg-seed-focus",
        target_ids=(FOCUS_TARGET,),
        source_turn_id=str(opened.turn_id),
    )
    _rebuild(learning_controller, FOCUS_TARGET)
    before = _state(db, FOCUS_TARGET)
    assert before["coverage"]["evidence_groups"] == 1
    # §22: freshness is strong-retrieval only, and a RECOGNITION success is
    # not one — so the before-state has no freshness leg at all.
    assert before["freshness"]["freshness_band"] == "UNKNOWN"
    assert before["freshness"]["last_strong_retrieval_at"] is None
    assert before["dimensions"]["recognition"]["estimate"] == 1.0
    assert before["dimensions"]["independent_production"]["estimate"] is None
    before_ids = _claim_ids(db)

    reply = _reply_ok(coordinator, _attempt(CANONICAL_ANSWER), "cm-a-attempt")
    assert reply.evaluation_outcome == "SUCCESS"
    assert reply.evidence_commit_id is not None
    assert reply.attempt_id is not None

    _rebuild(learning_controller, FOCUS_TARGET)
    after = _state(db, FOCUS_TARGET)
    new_claims = _new_claims(db, before_ids)
    assert len(new_claims) == 1
    claim = new_claims[0]
    assert claim["performance_type"] == "INDEPENDENT_PRODUCTION"
    assert claim["polarity"] == "POSITIVE" and claim["outcome"] == "SUCCESS"
    assert claim["support_level"] == "CONTEXT_ONLY"
    assert claim["answer_exposure_state"] == "NONE"
    assert claim["evaluator_confidence"] == 1.0

    diff = _reconcile(
        db,
        target_id=FOCUS_TARGET,
        before=before,
        after=after,
        new_claims=new_claims,
    )

    # The §5 entailment of that one claim: three ability dimensions move, the
    # other three base dimensions must not.
    assert _base_dimension_paths(diff) == {
        "recognition",
        "guided_production",
        "independent_production",
    }
    # §11: an all-positive recognition estimate cannot move even though its
    # mass grows — the difference is confidence/recency, not the estimate.
    assert "dimensions.recognition.estimate" not in diff
    assert after["dimensions"]["recognition"]["estimate"] == 1.0
    assert diff["dimensions.guided_production.estimate"] == (None, 1.0)
    assert diff["dimensions.independent_production.estimate"] == (None, 1.0)
    assert (
        diff["dimensions.recognition.confidence"][0]
        < diff["dimensions.recognition.confidence"][1]
    )
    # §21: one assisted claim is below the support-dependency diagnostic mass
    # floor, so the derived dimension stays UNKNOWN rather than guessing.
    assert after["dimensions"]["support_dependency"]["estimate"] is None
    assert after["dimensions"]["transfer"]["estimate"] is None

    # Freshness (§22): the new strong retrieval is the teaching attempt.
    assert after["freshness"]["last_strong_retrieval_at"] == claim["created_at"]
    assert after["freshness"]["freshness_band"] == "FRESH"
    assert diff["coverage.evidence_groups"] == (1, 2)
    assert diff["coverage.independent_clusters"] == (1, 2)
    assert diff["meta.evidence_watermark"] == (2, 3)
    _assert_lineage(
        db,
        claim,
        moment_id=str(reply.moment_id),
        attempt_id=str(reply.attempt_id),
        reply_turn_id=str(reply.turn_id),
    )


def test_a_alternative_success_is_credited_to_the_capability_not_the_resource(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario a (ALTERNATIVE_SUCCESS leg): STATE_MACHINES §5's fold — the
    capability takes the positive claim, the resource is recorded neutral /
    not demonstrated (§6), and the projection says exactly that."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    learning_controller = LearningController(learning)
    _chat(coordinator, "cm-a2-chat", "Nice to meet you.", 1)
    opened = _open(coordinator, "cm-a2-open")
    _seed(
        db,
        learning_controller,
        group_id="eg-seed-a2",
        target_ids=(FOCUS_TARGET, FOCUS_CAPABILITY),
        source_turn_id=str(opened.turn_id),
    )
    _rebuild(learning_controller, FOCUS_TARGET)
    _rebuild(learning_controller, FOCUS_CAPABILITY)
    before_resource = _state(db, FOCUS_TARGET)
    before_capability = _state(db, FOCUS_CAPABILITY)
    before_ids = _claim_ids(db)

    reply = _reply_ok(coordinator, _attempt(ALTERNATIVE_ANSWER), "cm-a2-attempt")
    assert reply.evaluation_outcome == "ALTERNATIVE_SUCCESS"
    assert reply.evidence_commit_id is not None

    # The teaching leg leaves both projections lagging — the repair face
    # names exactly the two, and rebuilding both is the move the coordinator's
    # pre-cycle repair makes.
    stale = learning_controller.stale_projection_targets()
    assert isinstance(stale, Ok), stale
    assert {str(target) for target, _ in stale.value} == {
        FOCUS_TARGET,
        FOCUS_CAPABILITY,
    }
    _rebuild(learning_controller, FOCUS_TARGET)
    _rebuild(learning_controller, FOCUS_CAPABILITY)

    new_claims = _new_claims(db, before_ids)
    assert {str(claim["target_type"]) for claim in new_claims} == {
        "RESOURCE",
        "CAPABILITY",
    }
    capability_claims = tuple(
        claim for claim in new_claims if claim["target_type"] == "CAPABILITY"
    )
    resource_claims = tuple(
        claim for claim in new_claims if claim["target_type"] == "RESOURCE"
    )
    assert len(capability_claims) == 1 and len(resource_claims) == 1
    assert capability_claims[0]["polarity"] == "POSITIVE"
    assert capability_claims[0]["outcome"] == "SUCCESS"
    assert capability_claims[0]["target_id"] == FOCUS_CAPABILITY
    assert resource_claims[0]["polarity"] == "NEUTRAL"
    assert resource_claims[0]["outcome"] == "ABSTAIN"

    # Capability side: the positive claim is a real projection change.
    after_capability = _state(db, FOCUS_CAPABILITY)
    capability_diff = _reconcile(
        db,
        target_id=FOCUS_CAPABILITY,
        before=before_capability,
        after=after_capability,
        new_claims=capability_claims,
    )
    assert "dimensions.independent_production.estimate" in capability_diff

    # Resource side: the neutral claim is mass-free (§10 ABSTAIN on the
    # resource), so the eight-dimension block is *identical* and only
    # coverage/watermark move — the learner did communicate, but the taught
    # target was not demonstrated, and the projection must not pretend it was.
    after_resource = _state(db, FOCUS_TARGET)
    resource_diff = _diff(before_resource, after_resource)
    assert not [p for p in resource_diff if p.startswith("dimensions.")]
    assert after_resource["dimensions"] == before_resource["dimensions"]
    assert resource_diff["coverage.evidence_groups"] == (1, 2)
    assert resource_diff["coverage.independent_clusters"] == (1, 2)
    before_watermark = before_resource["meta"]["evidence_watermark"]
    assert resource_diff["meta.evidence_watermark"] == (
        before_watermark,
        before_watermark + 1,
    )
    for claim in new_claims:
        _assert_lineage(
            db,
            claim,
            moment_id=str(reply.moment_id),
            attempt_id=str(reply.attempt_id),
            reply_turn_id=str(reply.turn_id),
        )


# ---------------------------------------------------------------------------
# b) the moment never writes the projection
# ---------------------------------------------------------------------------


def test_b_a_hand_written_projection_row_is_discarded_by_the_next_rebuild(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario b: the projection is a *rebuild product*, not a teaching write
    face. A hand-written §11 row is not mastery — the next rebuild (the only
    producer) derives the row from the append-only claims again.

    The structural half of the same pin is the ``teaching`` package's
    projection-write AST scan (tests/phase3/test_import_boundaries.py): there
    is no write face to call, so this scenario exercises the only remaining
    route — a direct row write — and shows it is inert.
    """

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    learning_controller = LearningController(learning)
    _chat(coordinator, "cm-b-chat", "Hello there.", 1)
    opened = _open(coordinator, "cm-b-open")
    _seed(
        db,
        learning_controller,
        group_id="eg-seed-b",
        target_ids=(FOCUS_TARGET,),
        source_turn_id=str(opened.turn_id),
    )
    _rebuild(learning_controller, FOCUS_TARGET)
    canonical = _state(db, FOCUS_TARGET)
    assert canonical["dimensions"]["independent_production"]["estimate"] is None

    # The counterfeit: a hand-written mastery row nobody produced from
    # evidence (a full independent_production estimate plus a forged stamp).
    counterfeit = json.loads(json.dumps(canonical))
    counterfeit["dimensions"]["independent_production"] = {
        "estimate": 1.0,
        "confidence": 0.99,
        "last_relevant_evidence_at": "2030-01-01T00:00:00+00:00",
    }
    db.execute(
        "UPDATE learner_target_state SET state_json = ?, evidence_watermark = 99"
        " WHERE target_id = ? AND evidence_modality = ?",
        (json.dumps(counterfeit), FOCUS_TARGET, MODALITY),
    )
    db.commit()
    forged = _state(db, FOCUS_TARGET)
    assert forged["dimensions"]["independent_production"]["estimate"] == 1.0

    # A rebuild overwrites it from the claims: the hand-written document is
    # discarded wholesale, because it is not a source of truth.
    _rebuild(learning_controller, FOCUS_TARGET)
    restored = _state(db, FOCUS_TARGET)
    assert restored["dimensions"] == canonical["dimensions"]
    assert restored["meta"]["evidence_watermark"] != 99

    # And the teaching chain never reads the projection as mastery either:
    # its own contribution lands as a *new canonical claim*, while the §11 row
    # keeps reporting exactly the claims' content until the next rebuild.
    before_ids = _claim_ids(db)
    reply = _reply_ok(coordinator, _attempt(CANONICAL_ANSWER), "cm-b-attempt")
    assert reply.evidence_commit_id is not None
    assert _new_claims(db, before_ids)[0]["target_id"] == FOCUS_TARGET
    unchanged = _state(db, FOCUS_TARGET)
    assert unchanged["coverage"]["evidence_groups"] == 1  # not rebuilt yet
    assert unchanged["dimensions"] == canonical["dimensions"]


# ---------------------------------------------------------------------------
# c) a post-reveal attempt is not independent evidence
# ---------------------------------------------------------------------------


def test_c_a_post_reveal_attempt_is_imitative_never_independent(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario c (DOMAIN_MODEL §15): once the full form has been shown, the
    moment produces no more independent evidence — the durable claim is
    IMITATIVE_PRODUCTION, the moment records the post-reveal phase, and the
    projection moves only on the imitative entailment (§5: recognition +
    weak guided), never on independent_production."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    learning_controller = LearningController(learning)
    _chat(coordinator, "cm-c-chat", "It is a nice day.", 1)
    opened = _open(coordinator, "cm-c-open")
    _seed(
        db,
        learning_controller,
        group_id="eg-seed-c",
        target_ids=(FOCUS_TARGET,),
        source_turn_id=str(opened.turn_id),
    )
    _rebuild(learning_controller, FOCUS_TARGET)
    before = _state(db, FOCUS_TARGET)
    before_ids = _claim_ids(db)

    revealed = _reply_ok(
        coordinator, _control(TeachingControlIntent.ASK_ANSWER), "cm-c-reveal"
    )
    assert revealed.delivery_kind == "REVEAL"
    moment = teaching_controller.get_moment(revealed.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.presentation_phase.value == "FULL_REVEAL"

    post_reveal = _reply_ok(coordinator, _attempt(CANONICAL_ANSWER), "cm-c-answer")
    assert post_reveal.evaluation_outcome == "SUCCESS"
    assert post_reveal.evidence_commit_id is not None
    moment = teaching_controller.get_moment(post_reveal.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.presentation_phase.value == "POST_REVEAL_OPTIONAL_ATTEMPT"

    new_claims = _new_claims(db, before_ids)
    assert [claim["performance_type"] for claim in new_claims] == [
        "IMITATIVE_PRODUCTION"
    ]
    claim = new_claims[0]
    # The recorded exposure is the real one (the form was shown), so the claim
    # can never be read as low-support independent production.
    assert claim["answer_exposure_state"] == "FULL"
    assert claim["support_level"] != "NONE"
    assert not _is_strong_retrieval(claim)

    _rebuild(learning_controller, FOCUS_TARGET)
    after = _state(db, FOCUS_TARGET)
    diff = _reconcile(
        db,
        target_id=FOCUS_TARGET,
        before=before,
        after=after,
        new_claims=new_claims,
    )
    # §5 IMITATIVE_PRODUCTION → recognition + weak guided; the independent
    # dimension must not move at all, and the §14 mass threshold keeps both
    # touched dimensions UNKNOWN (an imitative reproduction of a form just
    # shown is weak evidence, never a high or low ability claim).
    assert _base_dimension_paths(diff) == {"recognition", "guided_production"}
    assert not [p for p in diff if p.startswith("dimensions.independent_")]
    assert after["dimensions"]["independent_production"]["estimate"] is None
    assert after["dimensions"]["recognition"]["estimate"] == 1.0
    # It is not fresh independent evidence either: no strong retrieval, so the
    # §22 freshness leg stays exactly where the seed left it.
    assert after["freshness"] == before["freshness"]


# ---------------------------------------------------------------------------
# d) a closed moment never reopens
# ---------------------------------------------------------------------------


def test_d_a_closed_moment_never_reopens_and_a_new_request_opens_a_new_one(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario d: the SUCCESS attempt closes the episode (SM §1 SUCCESS →
    COMPLETING → TEACHING_TERMINAL → RESUMING → CLOSED); the closed moment
    refuses replies, and the next request is a *new* moment with its own lock
    and cycle."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator, "cm-d-open")
    reply = _reply_ok(coordinator, _attempt(CANONICAL_ANSWER), "cm-d-attempt")
    assert reply.closure is not None
    assert reply.moment_state.value == "CLOSED"
    closed_row = db.execute(
        "SELECT lifecycle_state, closed_at FROM teaching_moment"
        " WHERE moment_id = ?",
        (str(opened.moment_id),),
    ).fetchone()
    assert closed_row is not None and closed_row[0] == "CLOSED"
    assert closed_row[1] is not None

    # The closed episode is not reply-able: the reply path requires a live
    # moment, and this one is over.
    again = _reply(coordinator, _attempt(CANONICAL_ANSWER), "cm-d-reopen")
    assert not isinstance(again, Ok), again
    assert again.error.code is DomainErrorCode.CONFLICT

    # A new request is a new moment (never a reopen): new id, its own lock, and
    # the opening delivery has already landed it at AWAITING_USER.
    second = _open(coordinator, "cm-d-open-2")
    assert second.gate_decision == "ALLOW"
    assert second.moment_id != opened.moment_id
    assert second.moment_state.value == "AWAITING_USER"
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment WHERE moment_id = ?",
        (str(opened.moment_id),),
    ).fetchone() == ("CLOSED",)
    locks = db.execute("SELECT moment_id FROM active_teaching_lock").fetchall()
    assert [str(row[0]) for row in locks] == [str(second.moment_id)]


# ---------------------------------------------------------------------------
# e) a failed learning leg never breaks the chat
# ---------------------------------------------------------------------------


class _BrokenTeachingEvidence:
    """A Learning authority face whose teaching commit leg is down.

    RA §21 "Learning commit unavailable": the durable proposal stays pending,
    the teaching turn still completes, and the normal persona keeps answering.
    The wrapper delegates every other face to the real controller — the seam
    the coordinator calls on that path is exactly ``commit_teaching_evidence``.
    """

    def __init__(self, inner: LearningController) -> None:
        self._inner = inner
        self.attempts = 0

    def commit_teaching_evidence(self, *_args: object, **_kwargs: object) -> Any:
        self.attempts += 1
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="learning store unavailable (injected)",
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def test_e_a_failed_learning_leg_degrades_without_breaking_the_chat(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario e (RA §21): the teaching turn still ends — the durable attempt
    and evaluation are the trace, the moment closes normally and releases its
    lock — and the conversation keeps answering afterwards."""

    del conversation
    broken = _BrokenTeachingEvidence(LearningController(learning))
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        learning_controller=broken,
    )

    opened = _open(coordinator, "cm-e-open")
    reply = _reply_ok(coordinator, _attempt(CANONICAL_ANSWER), "cm-e-attempt")
    assert broken.attempts == 1
    # No evidence commit id (the leg degraded) — but the attempt and its
    # evaluation are durable and the episode still ends without a lock.
    assert reply.evidence_commit_id is None
    assert reply.attempt_id is not None
    assert db.execute(
        "SELECT outcome, confidence FROM attempt_evaluation_record"
        " WHERE attempt_id = ?",
        (str(reply.attempt_id),),
    ).fetchone() == ("SUCCESS", 1.0)
    assert db.execute(
        "SELECT COUNT(*) FROM evidence_claim WHERE opportunity_id IS NOT NULL"
    ).fetchone() == (0,)
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.lifecycle_state.value == "CLOSED"
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone() == (
        0,
    )

    # The chat answer still arrives on the next turn (the normal persona).
    follow_up = _chat(coordinator, "cm-e-chat-after", "Anyway, how are you?", 2)
    assert follow_up.outcome == "REPLIED_FULL"
    assert follow_up.reply_text


# ---------------------------------------------------------------------------
# f) multi-round accumulation inside one moment
# ---------------------------------------------------------------------------


def test_f_a_second_attempt_in_the_same_moment_adds_evidence_and_reconciles_again(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Scenario f: two rounds inside one moment. Round 1 fails (negative
    evidence, retry continuation), round 2 succeeds after a hint. Each round
    gets its own before≠after reconciliation, and the §12 cluster identity
    (one moment = one cluster) is visible in the coverage counts."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    learning_controller = LearningController(learning)
    _chat(coordinator, "cm-f-chat", "Let me try this.", 1)
    opened = _open(coordinator, "cm-f-open")
    _seed(
        db,
        learning_controller,
        group_id="eg-seed-f",
        target_ids=(FOCUS_TARGET,),
        source_turn_id=str(opened.turn_id),
    )
    _rebuild(learning_controller, FOCUS_TARGET)

    # -- round 1: a failed attempt continues the episode (SM §1 RETRY).
    before_1 = _state(db, FOCUS_TARGET)
    ids_1 = _claim_ids(db)
    first = _reply_ok(coordinator, _attempt(WRONG_ANSWER), "cm-f-attempt-1")
    assert first.evaluation_outcome == "FAILURE"
    assert first.moment_state.value == "AWAITING_USER"
    new_claims_1 = _new_claims(db, ids_1)
    assert [claim["performance_type"] for claim in new_claims_1] == [
        "FAILED_ATTEMPT"
    ]
    assert new_claims_1[0]["polarity"] == "NEGATIVE"

    _rebuild(learning_controller, FOCUS_TARGET)
    after_1 = _state(db, FOCUS_TARGET)
    diff_1 = _reconcile(
        db,
        target_id=FOCUS_TARGET,
        before=before_1,
        after=after_1,
        new_claims=new_claims_1,
    )
    # §6 negative propagation of a low-support failure: the attempted behavior
    # itself is diagnosed, never the guided/recognition rungs it did not use.
    assert _base_dimension_paths(diff_1) == {
        "spontaneous_production",
        "independent_production",
    }
    # §14/BF-01 §10: one 0.5-confidence failure (error attribution UNKNOWN)
    # carries 0.225–0.30 of negative mass — below the UNKNOWN threshold — so
    # the negative evidence is recorded (recency + confidence) without
    # fabricating a low mastery estimate: UNKNOWN is not 0.
    assert "dimensions.independent_production.estimate" not in diff_1
    assert "dimensions.spontaneous_production.estimate" not in diff_1
    assert after_1["dimensions"]["independent_production"]["estimate"] is None
    assert after_1["dimensions"]["spontaneous_production"]["estimate"] is None
    assert diff_1["dimensions.independent_production.confidence"][0] == 0.0
    assert diff_1["dimensions.independent_production.confidence"][1] > 0.0
    assert diff_1["dimensions.spontaneous_production.confidence"][0] == 0.0
    assert diff_1["dimensions.spontaneous_production.confidence"][1] > 0.0
    assert after_1["dimensions"]["recognition"]["estimate"] == 1.0

    # -- round 2: a hint lifts the rung, the second attempt succeeds.
    hinted = _reply_ok(
        coordinator, _control(TeachingControlIntent.ASK_HINT), "cm-f-hint"
    )
    assert hinted.delivery_kind == "HINT"
    assert hinted.moment_state.value == "AWAITING_USER"
    before_2 = _state(db, FOCUS_TARGET)
    ids_2 = _claim_ids(db)
    second = _reply_ok(coordinator, _attempt(CANONICAL_ANSWER), "cm-f-attempt-2")
    assert second.evaluation_outcome == "SUCCESS"
    assert second.closure is not None
    new_claims_2 = _new_claims(db, ids_2)
    assert [claim["performance_type"] for claim in new_claims_2] == [
        "GUIDED_PRODUCTION"
    ]
    assert new_claims_2[0]["attempt_id"] != new_claims_1[0]["attempt_id"]
    assert new_claims_2[0]["support_level"] == "SEMANTIC_HINT"

    _rebuild(learning_controller, FOCUS_TARGET)
    after_2 = _state(db, FOCUS_TARGET)
    diff_2 = _reconcile(
        db,
        target_id=FOCUS_TARGET,
        before=before_2,
        after=after_2,
        new_claims=new_claims_2,
    )
    assert _base_dimension_paths(diff_2) == {"recognition", "guided_production"}
    assert "dimensions.independent_production.estimate" not in diff_2
    # §14 (BF-01 §10): round 1's below-floor failure recorded confidence on
    # the attempted behavior without producing an estimate — UNKNOWN is not 0
    # — and round 2's guided success adds no independent mass, so the two
    # attempted-behavior estimates stay exactly where round 1 left them.
    assert after_2["dimensions"]["independent_production"]["estimate"] is None
    assert after_2["dimensions"]["spontaneous_production"]["estimate"] is None
    assert after_2["dimensions"]["guided_production"]["estimate"] == 1.0

    # §12: both attempts live in one correlation cluster (the moment), so the
    # whole episode counts as one cluster — the accumulation is mass inside a
    # cluster, not a diversity claim.
    assert after_2["coverage"] == {
        "evidence_groups": 3,
        "independent_clusters": 2,
        "sessions": 1,
        "days": 2,
        "contexts": 1,
        "personas": 1,
        "realizations": 1,
        "modalities": 1,
    }
    assert after_2["meta"]["evidence_watermark"] == 4
    # No strong retrieval happened in either round, so freshness is untouched.
    assert after_2["freshness"]["last_strong_retrieval_at"] is None
    for claim in new_claims_1 + new_claims_2:
        _assert_lineage(
            db,
            claim,
            moment_id=str(second.moment_id),
            attempt_id=str(claim["attempt_id"]),
            reply_turn_id=str(claim["source_turn_id"]),
        )
