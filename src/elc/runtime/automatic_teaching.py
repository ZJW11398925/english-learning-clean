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

A cycle's Gate trace is written **once**. Before the Gate is asked, the
unit reads the cycle's own durable trace; when one exists, the unit
**replays** it and neither asks the Gate again nor writes a second fact —
a re-entry whose freshly computed verdict would differ (the control facts
moved, a read changed) must never *answer* with something the durable
world contradicts, and must never try to persist a second, contradictory
authorization. :func:`_durable_gate_replay` names the three durable shapes,
the torn-trace refusal, and the one field a replay leaves ``None``
(``action_id``: this unit's declared teaching surface has no action read,
so the canonical first action is read through the generation store's own
replay face, ``GenerationStore.get_action_for_turn``).

What this unit does **not** do (each registered with the cut that owns it):

- it does not run the Planner. The caller owns the assembly and the kernel
  run (P7-0/P7-1/P7-4); this unit starts from the answer.
- it does not wire itself into a turn. **P8-4 landed that wiring** — the
  coordinator's automatic leg (:mod:`elc.runtime.automatic_turn` for the
  assembly, ``elc.runtime.controller`` for the ordinary turn) calls this unit
  through :func:`decide_automatic_teaching` — and the unit stayed where it
  was: it still takes a caller-assembled ``outcome``, the caller's controls and
  the caller's §15 template, and it still knows nothing about turns, delivery
  or the transcript. The opt-in boundary is the coordinator's
  (``ConversationCoordinator``'s optional wiring bundle): an assembly that
  injects nothing behaves exactly as it did before P8-4.
- it does not assemble the control facts. ``automatic_teaching_enabled``,
  the session budget / cooldown facts and the flow protection arrive as
  :class:`TeachingControlFacts`, declared by the caller — the same
  caller-declared posture :mod:`elc.teaching.gate`'s automatic profiles
  document (their declared authorities 1–3). P8-4's wiring derives the three
  view-borne controls (``TeachingControlFacts.derived`` over §5.2's
  ``SessionBudgetView`` and §13's ``ConversationPriorityView``) and passes the
  *Planner-assembled* auto-teach value (F2's ruling) composed with the
  process-level rollout stage P8-5 landed (``elc.teaching.rollout``; an
  undeclared stage refuses); a caller may still
  declare the record by hand. The Gate's remaining critical facts
  (``authorization_status``, ``subject_status``, ``target_status``,
  ``content_status``, ``learning_snapshot_status``, ``gate_state_status``,
  ``safety_privacy_status``, ``target_suppressed``) are declared on the same
  record with their healthy defaults, so an UNKNOWN can be expressed and the
  Gate's DEGRADED answer is reachable. The **lock** fact is *not* declared:
  it is read from the durable ``active_teaching_lock`` row through
  :meth:`TeachingOpenAuthority.observed_lock_state` (BF-03 §14's own fact).
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
  ``target_mode``, ``learning_intent``, ``evidence_modality``), or ``None``
  when the caller's run selected nothing (P8-4 made the field optional; the
  ALLOW path refuses a missing template rather than describing a moment the
  selection never named). The three fields an opening derives are **not** the
  caller's to choose, and a template that supplies them is refused rather than
  silently overwritten: ``source`` (always ``MomentSource.AUTOMATIC``),
  ``lifecycle_state`` (``OPENING``), ``presentation_phase``
  (``INITIAL_PROMPT``). The two identity columns derive from ``turn``
  (:func:`automatic_moment_id`).
- ``conversation_id`` / ``persona_id`` — the turn's conversation and the
  persona answering it (the coordinator reads both today;
  ``ConversationCoordinator._conversation_persona`` is that read).

The returned moment id and first-action id are **derived from the turn**
(:func:`automatic_moment_id` / :func:`automatic_action_id`), the way the
user-initiated path derives its own (``tm-{turn_id}`` / ``ga-{turn_id}-…``),
so the durable rows recognize a re-derivation. A re-entry does not get that
far any more — it replays the cycle's durable Gate trace before the Gate is
asked — but the store's own replay branch
(``elc.teaching.store.open_teaching_moment``) remains the second line of
defence behind this unit.

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
    DecisionCycleId,
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
from elc.runtime.automatic_controls import automatic_controls_of
from elc.runtime.decision_cycles import DecisionCycleRecord
from elc.teaching.gate import (
    GATE_POLICY_VERSION,
    SAFETY_PRIVACY_NO_SOURCE,
    TARGET_SUPPRESSED_NO_SOURCE,
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
    SessionBudgetView,
    TeachingMomentRecord,
)

if TYPE_CHECKING:
    from elc.planner.scope import ConversationPriorityView
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
    """The *declared* facts of one automatic opening (P8-1).

    The four controls, each with the authority registered in
    :mod:`elc.teaching.gate`'s automatic section:
    ``automatic_teaching_enabled`` ← product mode × rollout stage (both legs
    now have read faces — the Planner already derives the mode leg from the
    §5.1 policy, and **p8-5 landed the stage face**:
    :class:`elc.teaching.rollout.RolloutStage` /
    ``automatic_teaching_enabled_of``, a process-level declaration; the wiring
    cuts pass the Planner's value *and* the declared stage, which is what
    ``elc.runtime.automatic_turn`` composes); the other three ← the two views
    P8-2 landed —
    ``hard_protected_flow`` ← ``ConversationPriorityView.flow_priority ==
    "PROTECTED"`` (docs/DOMAIN_MODEL.md §13) and
    ``automatic_session_budget_exhausted`` / ``hard_cooldown_active`` ←
    ``SessionBudgetView`` (docs/DATA_MODEL.md §5.2) — through
    :mod:`elc.runtime.automatic_controls`, which :meth:`derived` calls.

    The remaining fields are the Gate's critical environment facts. They are
    declared here, with the healthy path as the default, for the same reason
    the four controls are: this cut has no durable read face for them, and a
    hard-coded healthy value would make one of the Gate's answers (DEGRADED)
    unreachable. ``lock_state`` is deliberately **absent** — the unit reads
    that fact from the durable ``active_teaching_lock`` row instead
    (:meth:`TeachingOpenAuthority.observed_lock_state`).

    A wrong declaration is a wrong *input*, and this unit does not try to
    repair one: it passes every declared value to the Gate verbatim. The
    caller's override shape is unchanged and stays the primary one — a caller
    that holds the facts declares them here; a caller that holds the two views
    asks :meth:`derived` for the three and then adjusts with
    ``dataclasses.replace`` if it knows better (both are declarations, and the
    Gate cannot tell them apart).
    """

    automatic_teaching_enabled: bool = True
    hard_protected_flow: bool = False
    automatic_session_budget_exhausted: bool = False
    hard_cooldown_active: bool = False

    authorization_status: str = "VALID"
    subject_status: str = "ACTIVE"
    target_status: str = "VALID"
    content_status: str = "VALID"
    learning_snapshot_status: str = "VALID"
    gate_state_status: str = "COMPLETE"
    safety_privacy_status: str = SAFETY_PRIVACY_NO_SOURCE
    target_suppressed: bool = TARGET_SUPPRESSED_NO_SOURCE

    @classmethod
    def derived(
        cls,
        *,
        session_budget_view: SessionBudgetView | None,
        conversation_priority_view: ConversationPriorityView | None,
    ) -> "TeachingControlFacts":
        """The three view-derived controls; every other fact at its healthy
        default.

        The derivation is :func:`elc.runtime.automatic_controls.
        automatic_controls_of` — one mapping, stated there with its authorities
        (BF-03 §12/§16/§17, DOMAIN_MODEL §13) and its fail-open reading for an
        absent view, so a caller never re-invents it. ``None`` is a legitimate
        argument for either view: this method derives what the caller holds and
        claims nothing about what it does not (a session view that could not be
        read is the caller's ``Err`` to handle, not this method's to guess).

        ``automatic_teaching_enabled`` is deliberately **not** derived here: its
        authority is the product mode crossed with the rollout stage (both
        legs' read faces are landed — ``elc.teaching.rollout`` for the stage
        (p8-5), the Planner's §5.1 assembly for the mode), and what a wiring cut
        must pass is the Planner's assembled value composed with the declared
        stage (the class docstring; ``elc.runtime.automatic_turn`` does exactly
        that). A caller that must override a derived control —
        a test pinning one control at a time, or a caller that knows the fact
        from elsewhere — replaces it on the returned record:
        ``replace(TeachingControlFacts.derived(...), hard_protected_flow=True)``.
        """

        controls = automatic_controls_of(
            session_budget_view=session_budget_view,
            conversation_priority_view=conversation_priority_view,
        )
        return cls(
            automatic_session_budget_exhausted=(
                controls.automatic_session_budget_exhausted
            ),
            hard_cooldown_active=controls.hard_cooldown_active,
            hard_protected_flow=controls.hard_protected_flow,
        )


@dataclass(frozen=True)
class AutomaticTeachingTurn:
    """The turn-level facts of one automatic decision.

    ``moment`` is the §15 template of the moment an ALLOW would open (see the
    module docstring for the fields that derive and the fields that must not be
    pre-set) — or ``None``, which is the honest shape of a caller whose Planner
    run selected nothing: there is no moment to describe, and describing one
    anyway would be a target the selection never named. The template is only
    ever *read* on the ALLOW path, where its absence is refused (P8-4 made the
    field optional for exactly that caller; every pre-P8-4 caller passes one).

    ``persona_id`` is the persona answering the turn; ``owner_epoch`` is the
    runtime epoch the CP2 unit's rows are fenced by (the coordinator passes its
    lease epoch the same way).
    """

    turn_id: TurnId
    conversation_id: ConversationId
    persona_id: PersonaId | None
    cycle: DecisionCycleRecord
    moment: TeachingMomentRecord | None
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

    On a **replay** (the cycle's Gate trace already exists, see
    :func:`_durable_gate_replay`) ``action_id`` is ``None``: this unit's
    declared teaching surface has no action read, so it reports the durable
    moment and refuses to invent the derived action id — the caller reads
    the canonical first action through
    ``GenerationStore.get_action_for_turn`` (the coordinator's own replay
    read). Every other path returns the derived id, as before.
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
    satisfies it. P9-0 widened the narrowing by one keyword — ``trace``, the
    run's kernel trace, typed ``object`` like ``outcome`` (this module uses
    none of its fields and the store's own signature is the authority on the
    shape) — because the durable ``factor_trace`` document is built from it.
    """

    def record_planner_cycle(
        self,
        *,
        turn_id: TurnId,
        outcome: object,
        reason_codes: tuple[str, ...] = (),
        trace: object | None = None,
    ) -> Result[PlannerCycleRecords]: ...


class TeachingOpenAuthority(Protocol):
    """The teaching half of CP2 — structurally
    :class:`elc.teaching.controller.TeachingController`, narrowed to the
    three commit faces, the three durable Gate reads the replay uses, and
    the lock read.

    The first action is built by the module-level
    :func:`elc.teaching.store.cp2_action_intent` (a plain helper, like the
    user-initiated coordinator's CP2 path uses it), so the commit side needs
    only the three faces. The read side is the durable truth the unit must
    consult before it asks the Gate (F1's repair) and the BF-03 §14 lock
    fact (F4's repair); both have been on the controller since P3-1A/P3-1B,
    so this Protocol grew no face the durable world did not already have.
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

    def get_gate_execution_statuses(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[tuple[GateExecutionStatusRecord, ...]]: ...
    def get_gate_decisions(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[tuple[GateDecisionRecord, ...]]: ...
    def get_moment_for_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[TeachingMomentRecord | None]: ...
    def observed_lock_state(
        self,
        conversation_id: ConversationId,
        moment_id: MomentId | None = None,
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
    asked for it). A template that is absent altogether is refused too:
    an ALLOW is the authorization of *one* moment, and one cannot be
    authorized without being described.
    """

    moment = turn.moment
    if moment is None:
        return _refusal(
            DomainErrorCode.VALIDATION_FAILED,
            "this ALLOW has no §15 template to open: the moment an automatic"
            " opening authorizes must be described by the caller (P8-4's"
            " wiring builds it from the selected candidate, and passes None"
            " only for a run that selected nothing — such a run cannot ALLOW)",
        )
    expected = {
        "source": MomentSource.AUTOMATIC,
        "lifecycle_state": MomentState.OPENING,
        "presentation_phase": PresentationPhase.INITIAL_PROMPT,
    }
    for field_name, value in expected.items():
        supplied = getattr(moment, field_name, None)
        if supplied is not None and supplied != value:
            return _refusal(
                DomainErrorCode.VALIDATION_FAILED,
                f"the automatic opening derives {field_name}={value}; the"
                f" template supplied {supplied}",
            )
    if str(moment.moment_id) != str(automatic_moment_id(turn.turn_id)):
        return _refusal(
            DomainErrorCode.VALIDATION_FAILED,
            "the moment id derives from the turn (automatic_moment_id); the"
            f" template supplied {moment.moment_id}",
        )
    if str(moment.conversation_id) != str(turn.conversation_id):
        return _refusal(
            DomainErrorCode.VALIDATION_FAILED,
            "the moment must belong to the turn's conversation",
        )
    if moment.persona_id != turn.persona_id:
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
    user_intent_scope: str = "OPEN",
    trace: object | None = None,
) -> Result[AutomaticTeachingResult]:
    """One automatic decision: Planner records first, then the cycle's
    durable Gate trace if it has one, then the Gate, then the CP2 open
    (RA §4 9A–10B, §6).

    ``outcome`` is the kernel's own answer
    (:class:`elc.planner.types.PlanningOutcome`; typed as ``object`` here
    because this module uses three of its fields and the stores' own
    signatures are the authority on its shape). ``trace`` is the *same run's*
    :class:`~elc.planner.kernel.PlannerTrace` (``ShadowRun.trace``), forwarded
    to the Planner half so the durable ``factor_trace`` document carries the
    per-candidate trace (P9-0; the keyword's default keeps every pre-P9-0
    caller recording exactly the shape it recorded before — a document whose
    ``provenance`` says ``NOT_RECORDED``).

    ``user_intent_scope`` is §12's word for the cycle — **the caller's**, read
    from the one resolver (``elc.planner.scope.resolve_user_intent_scope``) the
    same way the Planner's own request is, so the Gate's latest-intent
    revalidation judges the word the run ran under. P8-1 declared this fact as
    a literal ``"OPEN"`` (the profile's own default); P8-4's wiring passes the
    resolved word, which is what makes BF-03 §11's ``USER_INTENT_BLOCK``
    reachable in production (a ``JUST_CHAT`` turn must not be auto-opened). The
    default keeps every pre-P8-4 caller behaving exactly as before.

    A cycle the Gate already decided is not decided again: the durable trace
    is replayed (:func:`_durable_gate_replay`), so a re-entry answers with
    the durable verdict and writes nothing, whatever the fresh facts would
    have produced.
    """

    # 1. The Planner half of CP2 goes durable first (P8-0's port) — this is
    #    what makes the automatic path crash-honest: a failure here returns
    #    before the Gate is ever asked.
    recorded = planner_store.record_planner_cycle(
        turn_id=turn.turn_id, outcome=outcome, trace=trace
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

    # 3. The cycle's own Gate trace, if it exists, is the answer (F1's
    #    repair): a re-entry replays the durable facts instead of re-deciding
    #    them, so the result can never contradict the durable world and no
    #    second contradictory fact is ever written.
    replay = _durable_gate_replay(turn, records, teaching)
    if replay is not None:
        return replay

    # 4. The lock fact is BF-03 §14's, read from the durable
    #    ``active_teaching_lock`` row (never declared, never hard-coded):
    #    any existing lock denies an OPEN.
    lock = teaching.observed_lock_state(turn.conversation_id)
    if isinstance(lock, Err):
        return lock

    # 5. The Gate's AUTOMATIC OPEN profile (pure; the Planner facts are the
    #    inputs just read back from the durable rows, the critical facts are
    #    the caller's declarations).
    verdict = decide_automatic_open(
        AutomaticOpenFacts(
            decision_cycle_id=str(execution_status.decision_cycle_id),
            candidate_id=candidate_id,
            planner_execution_status=execution_status.status.value,
            planner_decision=decision.decision.value,
            user_intent_scope=user_intent_scope,
            lock_state=lock.value,
            authorization_status=controls.authorization_status,
            subject_status=controls.subject_status,
            target_status=controls.target_status,
            content_status=controls.content_status,
            learning_snapshot_status=controls.learning_snapshot_status,
            gate_state_status=controls.gate_state_status,
            safety_privacy_status=controls.safety_privacy_status,
            target_suppressed=controls.target_suppressed,
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
        # The §14.1 status row carries the fact's own value, exactly as the
        # user-initiated coordinator's OPEN does (elc/runtime/controller.py:
        # ``authorization_status=facts.authorization_status``).
        authorization_status=controls.authorization_status,
        status=(
            GateExecutionStatusValue.SUCCEEDED
            if verdict.execution_status == "SUCCEEDED"
            else GateExecutionStatusValue.DEGRADED
        ),
        missing_or_unknown=verdict.missing_or_unknown,
    )

    # 6. DEGRADED: one status row, no GateDecision (docs/DATA_MODEL.md
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

    # 7. DENY: two facts (status + decision), never a Moment / lock / action.
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

    # 8. ALLOW: the CP2 five-fact atomic open. The three derived fields are
    #    set here (not trusted from the template — refused above), the
    #    bindings come from the durable cycle, and the first action is the
    #    shared opening contract.
    refusal = _moment_template_refusal(turn)
    if refusal is not None:
        return refusal
    template = turn.moment
    assert template is not None  # the refusal above named a missing template

    moment_id = automatic_moment_id(turn.turn_id)
    action_id = automatic_action_id(turn.turn_id)
    gate_decision_id = automatic_gate_decision_id(turn.turn_id)
    moment = replace(
        template,
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


def _durable_gate_replay(
    turn: AutomaticTeachingTurn,
    records: PlannerCycleRecords,
    teaching: TeachingOpenAuthority,
) -> Result[AutomaticTeachingResult] | None:
    """The cycle's own Gate trace, when one already exists.

    A cycle's Gate facts are written once and are canonical: a re-entry
    whose freshly computed verdict would differ — the control facts moved,
    a read changed — replays the durable trace instead of answering with
    something the durable world contradicts, and never attempts a second,
    contradicting write. ``None`` means the cycle has no OPEN trace yet and
    the ordinary flow runs.

    The three durable shapes, and what each replays as:

    - a ``GateDecision`` row (ALLOW or DENY) with its status row: the
      decision's own ``policy_version``, its ordered ``reason_codes`` for a
      DENY (``primary_reason`` is the first of them), and — for an ALLOW —
      the moment the cycle opened (the CP2 unit wrote the pair in one
      transaction, so an ALLOW the *unit* wrote always has one);
    - a lone ``GateExecutionStatus(DEGRADED)``: the degradation's
      ``missing_or_unknown`` keys, ``decision=None``, no moment;
    - a lone ``GateExecutionStatus(SUCCEEDED)``: a **torn** trace no writer
      in this repository can produce (CP2 and both record faces write a
      SUCCEEDED status together with its decision, in one short
      transaction). It is refused rather than repaired — asking the Gate
      again would insert a second, contradictory fact, and there is no
      decision to replay.

    ``action_id`` is deliberately ``None`` on a replay: the declared
    teaching surface has no action read, and the derived id would claim a
    row the durable world may not hold. The caller reads the canonical
    first action through the generation store's own replay face
    (``GenerationStore.get_action_for_turn``, ``elc/runtime/generation.py``),
    which is exactly what the coordinator's replay path does.

    Revisit: the cut that gives this unit an action read replaces the ``None``
    with the durable first-action id and updates this docstring. **(P8-4: the
    wiring landed and the ``None`` stayed — this unit's declared surface is
    unchanged. What the wiring does instead is exactly what this docstring
    says a caller must: the coordinator's automatic leg reads the canonical
    first action through ``GenerationStore.get_action_for_turn`` and continues
    *that* action (``ga-{turn}-automatic-open``), so "which action" is read
    from the durable row rather than derived a second time here.)
    """

    cycle_id = turn.cycle.decision_cycle_id
    statuses = teaching.get_gate_execution_statuses(cycle_id)
    if isinstance(statuses, Err):
        return statuses
    decisions = teaching.get_gate_decisions(cycle_id)
    if isinstance(decisions, Err):
        return decisions

    open_decisions = tuple(
        decision
        for decision in decisions.value
        if decision.context is GateDecisionContext.OPEN
    )
    if open_decisions:
        decision = open_decisions[-1]
        reasons = tuple(decision.reason_codes)
        moment_id: MomentId | None = None
        if decision.decision is GateDecisionValue.ALLOW:
            moment = teaching.get_moment_for_cycle(cycle_id)
            if isinstance(moment, Err):
                return moment
            if moment.value is not None:
                moment_id = moment.value.moment_id
        return Ok(
            AutomaticTeachingResult(
                gate_verdict=GateVerdict(
                    execution_status="SUCCEEDED",
                    decision=decision.decision.value,
                    primary_reason=reasons[0] if reasons else None,
                    reasons=reasons,
                    missing_or_unknown=(),
                    policy_version=decision.policy_version,
                ),
                moment_id=moment_id,
                action_id=None,
                planner_records=records,
                normal_persona_generation=moment_id is None,
            )
        )

    open_statuses = tuple(
        status
        for status in statuses.value
        if status.gate_context is GateDecisionContext.OPEN
    )
    if not open_statuses:
        return None
    status = open_statuses[-1]
    if status.status is GateExecutionStatusValue.SUCCEEDED:
        return _refusal(
            DomainErrorCode.CONFLICT,
            "the durable Gate trace of decision cycle"
            f" {cycle_id} is torn: a SUCCEEDED execution status without its"
            " GateDecision; the unit neither asks the Gate again nor invents"
            " the decision that was never written",
        )
    return Ok(
        AutomaticTeachingResult(
            gate_verdict=GateVerdict(
                execution_status="DEGRADED",
                decision=None,
                primary_reason=None,
                reasons=(),
                missing_or_unknown=tuple(status.missing_or_unknown),
            ),
            moment_id=None,
            action_id=None,
            planner_records=records,
            normal_persona_generation=True,
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
