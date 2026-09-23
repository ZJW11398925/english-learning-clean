"""The automatic teaching decision unit — Phase 8 P8-1 (RA §4 9A–10B, §6 CP2).

This module is the *one* place where a Planner answer becomes an automatic
teaching attempt:

    PlanningOutcome ─► [CP2 planner half: durable records]  (P8-0's port)
                    ─► Gate OPEN (AUTOMATIC)                (P8-1's profile)
                    ─► ALLOW  ─► CP2 five-fact atomic open  (P8-1's controller)
                       DENY   ─► GateDecision(DENY) only
                       DEGRADED / not-SELECTED ─► no teaching

Order matters, and it is RA §6's: the Planner's records go durable **first**
(the ``decision_cycle`` back-reference included), and only then is the Gate
asked — so a crash between the two halves leaves a durable Planner answer
and no teaching moment, never a moment whose authorization was never
recorded. A run that is not ``SUCCEEDED`` / ``SELECT`` never reaches the
Gate at all (RA §4's 9A/9B Normal Persona arm: nothing was judged worth
teaching, so the turn is an ordinary one). A Gate DEGRADED answer is
persisted as a status row and **no** GateDecision — critical state unknown
is never laundered into a synthetic DENY (docs/DATA_MODEL.md §14.1).

What this unit does **not** do (each registered with the cut that owns it):

- it does not run the Planner. The caller owns the assembly and the kernel
  run (P7-0/P7-1/P7-4); this unit starts from the answer.
- it does not wire itself into a turn. Nothing in ``elc.runtime.controller``
  calls it yet: connecting the ordinary turn's planner → gate → moment flow
  to ``EphemeralTeachingDirective`` / prompt / delivery is **p8-4** (the
  same-turn integration). Until then this face is exercised by its suite.
- it does not assemble the control facts. ``automatic_teaching_enabled``,
  the session budget / cooldown facts and the flow protection arrive as
  :class:`TeachingControlFacts`, declared by the caller — the same
  caller-declared posture :mod:`elc.teaching.gate`'s automatic profiles
  document (their declared authorities 1–3). The views that will derive
  them (``SessionBudgetView``, ``ConversationPriorityView``) are **p8-2**;
  the durable home of the auto-teach setting is **p8-5**.
- it does not own the continuation. ``AUTO_CONTINUE`` is P8-1's *decision*
  profile (``elc.teaching.gate.decide_auto_continuation``), but the
  mid-moment automatic continuation flow (next-action branch, delivery,
  limits) stays where it is; this unit decides open-or-not for one turn.

Facts the caller must already hold (declared reads, no second authority):

- ``cycle`` — the durable ``decision_cycle`` row's own fields
  (:class:`~elc.runtime.decision_cycles.DecisionCycleRecord`): the cycle
  holds the bindings (learning snapshot, watermark, policy version) that
  §15's moment columns copy. This unit does not re-read them.
- ``moment`` — the §15 shape of the moment to open, with its teaching
  content fields filled from the resolved target view (``focus_target``,
  ``target_mode``, ``learning_intent``, ``evidence_modality``). The three
  fields an opening derives are **not** the caller's to choose, and a
  template that supplies them is refused rather than silently overwritten:
  ``source`` (always ``MomentSource.AUTOMATIC``), ``lifecycle_state``
  (``OPENING``), ``presentation_phase`` (``INITIAL_PROMPT``). The two
  identity columns derive from ``turn`` (:func:`automatic_moment_id`).
- ``conversation_id`` / ``persona_id`` — the turn's conversation and the
  persona answering it (the coordinator reads both today;
  ``ConversationCoordinator._conversation_persona`` is that read).

The returned moment id and first-action id are **derived from the turn**
(:func:`automatic_moment_id` / :func:`automatic_action_id`), the way the
user-initiated path derives its own (``tm-{turn_id}`` / ``ga-{turn_id}-…``),
so a re-entry that reaches CP2 with a differing action id replays the
durable ``(moment, action)`` pair instead of writing a second one
(``elc.teaching.store.open_teaching_moment``'s replay branch).

The first action's generation contract is **not** re-invented here:
:data:`TEACHING_OPEN_CONTRACT_ID` is the same ``"gc-teaching-open"`` value
``elc.runtime.controller`` declares. The duplication is deliberate and
mirrored (that module would have to import this one or vice versa, and both
are Runtime faces); ``tests/phase8/test_p8_1_automatic_unit.py`` holds the
equality, the way the ``CONVERSATION_WINDOW_MAX_TURNS`` pair is held.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol

from elc.planner.records import PlannerCycleRecords
from elc.platform.types import (
    ActionId,
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    GateDecisionId,
    MomentId,
    Ok,
    PersonaId,
    PlannerDecisionOutcome,
    PlannerExecutionStatusValue,
    PolicyVersion,
    Result,
    TurnId,
)
from elc.runtime.decision_cycles import DecisionCycleRecord
from elc.teaching.gate import (
    GATE_POLICY_VERSION,
    AutomaticOpenFacts,
    GateVerdict,
    decide_automatic_open,
)
from elc.teaching.types import (
    AuthorizationBasis,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
)

if TYPE_CHECKING:
    from elc.runtime.types import GenerationActionIntentRecord
    from elc.teaching.store import CP2OpenRequest

__all__ = [
    "TEACHING_OPEN_CONTRACT_ID",
    "AutomaticTeachingResult",
    "AutomaticTeachingTurn",
    "PlannerDecisionRecordStore",
    "TeachingControlFacts",
    "TeachingOpenAuthority",
    "automatic_action_id",
    "automatic_gate_decision_id",
    "automatic_gate_execution_status_id",
    "automatic_moment_id",
    "decide_automatic_teaching",
]

#: The CP2 first action's §20 generation contract — the same value
#: ``elc.runtime.controller.TEACHING_OPEN_CONTRACT_ID`` declares (see the
#: module docstring: mirrored on purpose, held equal by a test).
TEACHING_OPEN_CONTRACT_ID = "gc-teaching-open"


def automatic_moment_id(turn_id: TurnId) -> MomentId:
    """The deterministic moment id of one turn's automatic opening.

    Derived from the turn (never random): a re-entry re-derives the same id,
    which is what lets the durable replay recognize it.
    """

    return MomentId(f"tm-{turn_id}-automatic")


def automatic_action_id(turn_id: TurnId) -> ActionId:
    """The deterministic CP2 first-action id of one turn's automatic open."""

    return ActionId(f"ga-{turn_id}-automatic-open")


def automatic_gate_decision_id(turn_id: TurnId) -> GateDecisionId:
    """The deterministic GateDecision id of one turn's automatic decision."""

    return GateDecisionId(f"gd-{turn_id}-automatic")


def automatic_gate_execution_status_id(turn_id: TurnId) -> str:
    """The deterministic GateExecutionStatus id of one turn's automatic
    decision."""

    return f"ges-{turn_id}-automatic"


@dataclass(frozen=True)
class TeachingControlFacts:
    """The *declared* control facts of one automatic opening (P8-1).

    Each field is the caller's declaration, with the authority registered in
    :mod:`elc.teaching.gate`'s automatic section: ``automatic_teaching_enabled``
    ← product mode × rollout stage (no durable home in this cut — p8-5);
    ``hard_protected_flow`` ← ``ConversationPriorityView.flow_priority ==
    "PROTECTED"`` (docs/DOMAIN_MODEL.md §13, derived by the caller — p8-2/p8-4);
    ``automatic_session_budget_exhausted`` / ``hard_cooldown_active`` ←
    ``SessionBudgetView`` (p8-2).

    A wrong declaration is a wrong *input*, and this unit does not try to
    repair one: it passes the four values to the Gate verbatim.
    """

    automatic_teaching_enabled: bool = True
    hard_protected_flow: bool = False
    automatic_session_budget_exhausted: bool = False
    hard_cooldown_active: bool = False


@dataclass(frozen=True)
class AutomaticTeachingTurn:
    """The turn-level facts of one automatic decision.

    ``moment`` is the §15 template of the moment an ALLOW would open (see
    the module docstring for the fields that derive and the fields that must
    not be pre-set); ``persona_id`` is the persona answering the turn;
    ``owner_epoch`` is the runtime epoch the CP2 unit's rows are fenced by
    (the coordinator passes its lease epoch the same way).
    """

    turn_id: TurnId
    conversation_id: ConversationId
    persona_id: PersonaId | None
    cycle: DecisionCycleRecord
    moment: TeachingMomentRecord
    owner_epoch: int


@dataclass(frozen=True)
class AutomaticTeachingResult:
    """What one automatic decision produced.

    ``normal_persona_generation`` is the RA §4 9A/9B arm: ``True`` whenever
    no teaching moment was opened — a Planner run that did not select, a
    DENY, or a DEGRADED answer all leave the turn to the ordinary Persona
    runtime. It is ``False`` exactly when ``moment_id`` is set.

    ``planner_records`` is P8-0's durable answer (never ``None``: the
    Planner half commits before the Gate is asked, so every return carries
    it).
    """

    gate_verdict: GateVerdict | None
    moment_id: MomentId | None
    action_id: ActionId | None
    planner_records: PlannerCycleRecords
    normal_persona_generation: bool


class PlannerDecisionRecordStore(Protocol):
    """The Planner half of CP2 — structurally
    :class:`elc.planner.records.PlannerRecordStore`, narrowed to the one
    face this unit uses.

    Declared here rather than imported so the unit's dependency is visible
    at its own boundary (the ``elc.runtime.projections`` ``ProjectionJobStore``
    precedent); ``elc.platform.db.planner_store.SqlitePlannerRecordStore``
    satisfies it.
    """

    def record_planner_cycle(
        self,
        *,
        turn_id: TurnId,
        outcome: object,
        reason_codes: tuple[str, ...] = (),
    ) -> Result[PlannerCycleRecords]: ...


class TeachingOpenAuthority(Protocol):
    """The teaching half of CP2 — structurally
    :class:`elc.teaching.controller.TeachingController`, narrowed to the
    three commit faces and the action-intent builder this unit calls.

    The first action is built by the module-level
    :func:`elc.teaching.store.cp2_action_intent` (a plain helper, like the
    user-initiated coordinator's CP2 path uses it), so the Protocol only
    needs the three commits.
    """

    def commit_cp2_open(self, request: object) -> Result[MomentId]: ...
    def record_gate_denial(
        self,
        status: GateExecutionStatusRecord,
        decision: GateDecisionRecord,
    ) -> Result[GateDecisionId]: ...
    def record_gate_degraded(
        self, status: GateExecutionStatusRecord
    ) -> Result[str]: ...


def _refusal(code: DomainErrorCode, message: str) -> Err[Any]:
    return Err(DomainError(code=code, message=message))


def _moment_template_refusal(
    turn: AutomaticTeachingTurn,
) -> Err[Any] | None:
    """The automatic opening's own three fields must not be pre-set on the
    template, and the identity columns must come from the turn.

    A silently overwritten template would make the caller's ``source``
    look honoured while the row says ``AUTOMATIC`` — so the refusal names
    the field instead (the durable row's truth wins only when the caller
    asked for it).
    """

    expected = {
        "source": MomentSource.AUTOMATIC,
        "lifecycle_state": MomentState.OPENING,
        "presentation_phase": PresentationPhase.INITIAL_PROMPT,
    }
    for field_name, value in expected.items():
        supplied = getattr(turn.moment, field_name, None)
        if supplied is not None and supplied != value:
            return _refusal(
                DomainErrorCode.VALIDATION_FAILED,
                f"the automatic opening derives {field_name}={value}; the"
                f" template supplied {supplied}",
            )
    if str(turn.moment.moment_id) != str(automatic_moment_id(turn.turn_id)):
        return _refusal(
            DomainErrorCode.VALIDATION_FAILED,
            "the moment id derives from the turn (automatic_moment_id); the"
            f" template supplied {turn.moment.moment_id}",
        )
    if str(turn.moment.conversation_id) != str(turn.conversation_id):
        return _refusal(
            DomainErrorCode.VALIDATION_FAILED,
            "the moment must belong to the turn's conversation",
        )
    if turn.moment.persona_id != turn.persona_id:
        return _refusal(
            DomainErrorCode.VALIDATION_FAILED,
            "the moment's persona is the turn's persona",
        )
    return None


def decide_automatic_teaching(
    *,
    turn: AutomaticTeachingTurn,
    outcome: object,
    controls: TeachingControlFacts,
    planner_store: PlannerDecisionRecordStore,
    teaching: TeachingOpenAuthority,
) -> Result[AutomaticTeachingResult]:
    """One automatic decision: Planner records first, then the Gate, then
    the CP2 open (RA §4 9A–10B, §6).

    ``outcome`` is the kernel's own answer
    (:class:`elc.planner.types.PlanningOutcome`; typed as ``object`` here
    because this module uses three of its fields and the stores' own
    signatures are the authority on its shape).
    """

    # 1. The Planner half of CP2 goes durable first (P8-0's port) — this is
    #    what makes the automatic path crash-honest: a failure here returns
    #    before the Gate is ever asked.
    recorded = planner_store.record_planner_cycle(
        turn_id=turn.turn_id, outcome=outcome
    )
    if not isinstance(recorded, Ok):
        return recorded
    records = recorded.value

    # 2. RA §4's 9A/9B: only a SUCCEEDED + SELECT run is worth teaching. A
    #    NO_TARGET decision is a *decision* (the Planner said "nothing to
    #    teach") and the turn proceeds as an ordinary one — no Gate row, no
    #    moment, and no fabricated selection.
    execution_status = records.execution_status
    decision = records.decision
    if (
        execution_status.status is not PlannerExecutionStatusValue.SUCCEEDED
        or decision is None
        or decision.decision is not PlannerDecisionOutcome.SELECT
    ):
        return Ok(
            AutomaticTeachingResult(
                gate_verdict=None,
                moment_id=None,
                action_id=None,
                planner_records=records,
                normal_persona_generation=True,
            )
        )

    candidate_id = str(decision.selected_candidate_id)

    # 3. The Gate's AUTOMATIC OPEN profile (pure; the Planner facts are the
    #    inputs just read back from the durable rows).
    verdict = decide_automatic_open(
        AutomaticOpenFacts(
            decision_cycle_id=str(execution_status.decision_cycle_id),
            candidate_id=candidate_id,
            planner_execution_status=execution_status.status.value,
            planner_decision=decision.decision.value,
            user_intent_scope="OPEN",
            automatic_teaching_enabled=controls.automatic_teaching_enabled,
            hard_protected_flow=controls.hard_protected_flow,
            automatic_session_budget_exhausted=(
                controls.automatic_session_budget_exhausted
            ),
            hard_cooldown_active=controls.hard_cooldown_active,
        )
    )

    status_record = GateExecutionStatusRecord(
        gate_execution_status_id=automatic_gate_execution_status_id(
            turn.turn_id
        ),
        decision_cycle_id=turn.cycle.decision_cycle_id,
        moment_id=None,  # an OPEN binds the DecisionCycle, not a moment
        gate_context=GateDecisionContext.OPEN,
        authorization_basis=AuthorizationBasis.DECISION_CYCLE,
        authorization_status="VALID",
        status=(
            GateExecutionStatusValue.SUCCEEDED
            if verdict.execution_status == "SUCCEEDED"
            else GateExecutionStatusValue.DEGRADED
        ),
        missing_or_unknown=verdict.missing_or_unknown,
    )

    # 4. DEGRADED: one status row, no GateDecision (docs/DATA_MODEL.md
    #    §14.1) — and no moment.
    if verdict.decision is None:
        persisted = teaching.record_gate_degraded(status_record)
        if not isinstance(persisted, Ok):
            return persisted
        return Ok(
            AutomaticTeachingResult(
                gate_verdict=verdict,
                moment_id=None,
                action_id=None,
                planner_records=records,
                normal_persona_generation=True,
            )
        )

    # 5. DENY: two facts (status + decision), never a Moment / lock / action.
    if verdict.decision == "DENY":
        denial = teaching.record_gate_denial(
            status_record,
            GateDecisionRecord(
                gate_decision_id=automatic_gate_decision_id(turn.turn_id),
                decision_cycle_id=turn.cycle.decision_cycle_id,
                candidate_id=candidate_id,
                context=GateDecisionContext.OPEN,
                decision=GateDecisionValue.DENY,
                reason_codes=verdict.reasons,
                policy_version=PolicyVersion(GATE_POLICY_VERSION),
            ),
        )
        if not isinstance(denial, Ok):
            return denial
        return Ok(
            AutomaticTeachingResult(
                gate_verdict=verdict,
                moment_id=None,
                action_id=None,
                planner_records=records,
                normal_persona_generation=True,
            )
        )

    # 6. ALLOW: the CP2 five-fact atomic open. The three derived fields are
    #    set here (not trusted from the template — refused above), the
    #    bindings come from the durable cycle, and the first action is the
    #    shared opening contract.
    refusal = _moment_template_refusal(turn)
    if refusal is not None:
        return refusal

    moment_id = automatic_moment_id(turn.turn_id)
    action_id = automatic_action_id(turn.turn_id)
    gate_decision_id = automatic_gate_decision_id(turn.turn_id)
    moment = replace(
        turn.moment,
        moment_id=moment_id,
        source=MomentSource.AUTOMATIC,
        decision_cycle_id=turn.cycle.decision_cycle_id,
        candidate_id=candidate_id,
        gate_decision_id=gate_decision_id,
        persona_id=turn.persona_id,
        learning_snapshot_id=turn.cycle.learning_snapshot_id,
        evidence_watermark=turn.cycle.evidence_watermark,
        curriculum_version=turn.cycle.curriculum_version,
        policy_version=turn.cycle.policy_version,
        lifecycle_state=MomentState.OPENING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        state_version=1,
    )
    action = _automatic_action_intent(turn, moment, action_id)
    opened = teaching.commit_cp2_open(
        _cp2_open_request(
            status_record=status_record,
            gate_decision=GateDecisionRecord(
                gate_decision_id=gate_decision_id,
                decision_cycle_id=turn.cycle.decision_cycle_id,
                candidate_id=candidate_id,
                context=GateDecisionContext.OPEN,
                decision=GateDecisionValue.ALLOW,
                reason_codes=(),
                policy_version=PolicyVersion(GATE_POLICY_VERSION),
            ),
            moment=moment,
            action=action,
            owner_epoch=turn.owner_epoch,
        )
    )
    if not isinstance(opened, Ok):
        return opened
    # The store answers with the *canonical* moment id (a replay of the same
    # cycle returns the durable one) — report that, not the derived guess.
    return Ok(
        AutomaticTeachingResult(
            gate_verdict=verdict,
            moment_id=opened.value,
            action_id=action_id,
            planner_records=records,
            normal_persona_generation=False,
        )
    )


def _automatic_action_intent(
    turn: AutomaticTeachingTurn,
    moment: TeachingMomentRecord,
    action_id: ActionId,
) -> GenerationActionIntentRecord:
    """The CP2 first action intent (the shared helper, called with the
    automatic open's ids).

    ``cp2_action_intent`` lives in ``elc.teaching.store`` and is imported at
    the call site: this module's teaching surface is the injected
    :class:`TeachingOpenAuthority` plus this one plain helper, and the
    import stays inside the function so importing this module never pulls
    the teaching store's SQL machinery (the module is architectural
    SQL-free, and a reader must not have to trace that).
    """

    from elc.teaching.store import cp2_action_intent

    return cp2_action_intent(
        turn_id=turn.turn_id,
        moment_id=moment.moment_id,
        decision_cycle_id=turn.cycle.decision_cycle_id,
        action_id=action_id,
        assistant_turn_id=f"aturn-{turn.turn_id}-automatic-open",
        generation_contract_id=TEACHING_OPEN_CONTRACT_ID,
        owner_epoch=turn.owner_epoch,
    )


def _cp2_open_request(
    *,
    status_record: GateExecutionStatusRecord,
    gate_decision: GateDecisionRecord,
    moment: TeachingMomentRecord,
    action: GenerationActionIntentRecord,
    owner_epoch: int,
) -> CP2OpenRequest:
    """The five-fact CP2 request (constructed here rather than imported at
    module scope, so the Protocol above stays this module's declared
    teaching surface)."""

    from elc.teaching.store import CP2OpenRequest

    return CP2OpenRequest(
        gate_execution_status=status_record,
        gate_decision=gate_decision,
        moment=moment,
        action=action,
        owner_epoch=owner_epoch,
    )
