"""The ordinary turn's automatic teaching leg — Phase 8 P8-4 (RA §4 steps 3–8).

docs/RUNTIME_ARCHITECTURE.md §4 fixes the order this module exists to make
real, for a plain conversation turn:

    3  UserIntentScope / ConversationPriorityView (the conversation leg)
    4  Learning validates/commits current-user Evidence → CP1
    5  Create DecisionCycle → bind LearningSnapshot + versions
    6  Candidate generators
    7  ActiveLearningFrontier
    8  Pedagogy Planner
    9A/9B/9C  PlannerExecutionStatus / PlannerDecision
    10A/10B   Gate DENY / Gate ALLOW → CP2

P8-0..P8-3 landed every piece of that chain and left it unconnected: the
automatic decision unit (:mod:`elc.runtime.automatic_teaching`) had **no
production caller**, the §13 view had **no producer**, and the PlanningLedger's
log had **no writer**. This module is the assembly that connects them — and
nothing here decides anything on its own: it reads the authorities a cycle
names, hands them to P7-4's kernel run and P8-1's unit, and reports what they
answered.

**Two halves, split where the cycle is.** The read-only half
(:func:`assemble_automatic_turn`) runs before the turn's ``decision_cycle`` row
is written, because the row must carry the bindings this assembly read
(``learning_snapshot_id`` / ``evidence_watermark`` / ``curriculum_version`` /
``goal_version`` / ``schedule_version`` / ``policy_version`` — each stamped only
from a value that was really read; the remaining two columns stay ``None``
because nothing in this assembly reads them). The deciding half
(:func:`decide_automatic_turn`) runs after it, so a crash between the two
leaves a durable cycle with no planner trace and a re-entry re-derives the same
answer. Reads are side-effect-free; nothing is written by the first half.

**Every leg is optional, and a missing one is reported rather than filled.**
Each face in :class:`AutomaticTurnWiring` may be absent, and an absent face
means ``None`` reaches :class:`~elc.planner.candidates.CandidateSupplyInputs`
— which is what makes the generators emit their own :class:`~elc.planner.
candidates.SourceGap` and the assembly answer ``INCOMPLETE`` (BF-02 §5). That
is the honest production verdict for this repository today, reached without
inventing a single number. A **read** that fails is the same case: an ``Err``
(or an exception out of a port) makes that one leg ``None`` and is recorded in
:attr:`AutomaticTurnPlan.notes`; the run then degrades on its own, and its
durable trace carries the same gaps as BF-02 §5's ``missing_authorities``.

**``automatic_teaching_enabled`` is the Planner's own answer times the
rollout stage.** P8-1's disposal F2 ruled that the wiring cut "must pass the
value the Planner assembled"; here that is literally
``run.trace.context.automatic_teaching_enabled`` — the flag BF-02 §5's
authority assembly derived from the §5.1 policy — read off the run the cycle
just made, never hand-declared and never read a second time from the policy
row. P8-5's rollout gate adds the **second leg** the Gate's own registration
always named (``elc/teaching/gate.py``: the switch is "the product mode …
crossed with the rollout stage"): the wiring carries the process-level
``rollout_stage`` declaration, and the composed fact is the Planner's value
**and** :func:`elc.teaching.rollout.stage_allows_automatic` — which is
``False`` for an undeclared stage, so an assembly nobody declared a stage for
teaches nothing automatically (fail-closed). The other three controls are
derived from the two views by
:meth:`~elc.runtime.automatic_teaching.TeachingControlFacts.derived`, which
calls :func:`elc.runtime.automatic_controls.automatic_controls_of`.

**The scope word, and one view for two readers.** :func:`elc.planner.scope.
resolve_user_intent_scope` is the one §12 resolver, and its answer is what the
request carries *and* what the Gate is told (a ``JUST_CHAT`` turn cannot be
auto-opened: BF-03 §11's latest-intent revalidation is exactly that leg). The
same :class:`~elc.planner.scope.ConversationPriorityView` instance is handed to
both readers §13 has — the request's context (through which the kernel reads
BF-02 §5's ``natural_break_available``) and the control derivation — so the two
cannot see different flows.

**What is read, verbatim (each face with the landed authority it narrows).**

======================================  =====================================
face                                    the landed read it narrows
======================================  =====================================
``learning.get_learning_snapshot``      ``LearningController``
``learning.get_learning_watermark``     ``LearningController``
``learning.get_learner_target_state``   ``LearningController``
``scheduler.get_schedule_view`` / ``get_schedule_item``   ``SchedulerController``
``user_config.get_teaching_policy``     ``UserConfigController``
``user_config.get_goal_portfolio``      ``UserConfigController``
``user_config.get_planner_constraint_view``  ``UserConfigController``
``curriculum.readiness`` / ``get_target`` / ``prerequisites_of`` /
``curriculum_links_of`` / ``get_capability`` / ``curriculum_version``
                                        ``CurriculumContentStore``
``supply.facts``                        ``ContentBackedTargetSupply``
``ledger.read_ledger``                  ``SqliteLedgerStore``
``session_budget.get_session_budget_view``  ``TeachingController``
``teaching.observed_lock_state``        ``TeachingController``
======================================  =====================================

**Declared readings** (each is this cut's judgement, with the condition that
re-opens it):

1. **the instant is the turn's own.** ``as_of`` is the caller's — the
   coordinator passes the committed user turn's ``received_at``, the one
   instant this turn already carries. No clock is read here, and a second clock
   would be a second answer to "when is this cycle". Revisit: a canonical
   sentence dates a cycle by something other than its turn.
2. **the ledger view is read, not just written.** ``CandidateSupplyInputs.
   ledger`` turns the ``PLANNING_LEDGER`` authority on (the ``COVERAGE_DEBT``
   source and its three readings), and the store's own ``read_ledger`` is the
   face that answers it — a real read of the durable log, with the core's
   declared defaults for the two columns nothing materializes (P8-3's reading).
   Revisit: a narrower view read lands (only the keys this cycle considers).
3. **the moment template comes from the selected candidate.** §15's
   ``focus_target`` / ``target_mode`` / ``learning_intent`` /
   ``evidence_modality`` are the *candidate's* facts — the Planner selected that
   modal and intent, so the moment must not re-spell them — and the one field a
   candidate does not carry (its §11 ``target_type``) is read off the target's
   own row. A run that selects nothing has **no** template, and the caller
   passes ``None`` rather than describing a moment that does not exist (the unit
   refuses an ALLOW without one). Revisit: a candidate record gains its target
   type, or a second consumer needs the template without a selection.
4. **``user_id`` is the caller's binding.** ``get_teaching_policy`` /
   ``get_goal_portfolio`` are keyed by user, and nothing in this repository can
   resolve a conversation to one (DATA_MODEL §3's Conversation carries no
   ``user_id``; ``elc.conversation.store.open_conversation`` discards the
   argument that could have bound one — the ``SessionBudgetPolicySource``
   reading, one port over). The wiring therefore carries the user leg
   explicitly, and an absent one leaves both reads unasked. Revisit: a durable
   conversation→user binding lands.
5. **the leg answers values, not envelopes.** Neither function invents a
   status: a leg that could not be read is ``None`` (recorded in ``notes``), and
   the two shapes that *are* ``Err`` are caller contract breaches — a request
   the kernel refuses, and a selection whose candidate the supply it ran over
   does not carry. Revisit: the coordinator's own failure posture changes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol, Sequence, cast

from elc.planner.candidates import (
    CandidateSupply,
    CandidateSupplyInputs,
    SchedulePort,
    TargetRowPort,
    TargetSupplyPort,
    generate_candidates,
)
from elc.planner.kernel import (
    PLANNER_KERNEL_MODEL_VERSION,
    PLANNER_PROFILE_VERSION,
    CandidateProposal,
)
from elc.planner.ledger import PlanningLedger
from elc.planner.records import PlannerCycleRecords
from elc.planner.scope import (
    ConversationPriorityView,
    FlowPriority,
    InteractionPhase,
    ScopeResolution,
    resolve_user_intent_scope,
)
from elc.planner.shadow import ShadowRun, run_shadow
from elc.planner.supply import LearnerStatePort, PrerequisitePort, ReadinessPort
from elc.planner.types import (
    PlannerEvaluation,
    PlanningOutcome,
    PlanningRequest,
)
from elc.platform.types import (
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
    Result,
    TurnId,
)
from elc.runtime.automatic_teaching import (
    AutomaticTeachingResult,
    AutomaticTeachingTurn,
    PlannerDecisionRecordStore,
    TeachingControlFacts,
    TeachingOpenAuthority,
    automatic_gate_decision_id,
    automatic_moment_id,
    decide_automatic_teaching,
)
from elc.runtime.decision_cycles import DecisionCycleBindings, DecisionCycleRecord
from elc.runtime.exposure import LedgerExposureWriter
from elc.teaching.rollout import RolloutStage, stage_allows_automatic
from elc.teaching.types import (
    EvidenceModality,
    MomentSource,
    MomentState,
    PresentationPhase,
    SessionBudgetView,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from elc.user_config.types import PlannerConstraintView

__all__ = [
    "AUTOMATIC_OPEN_SLOT",
    "AUTOMATIC_TURN_LEG_UNAVAILABLE",
    "AutomaticTurnPlan",
    "AutomaticTurnWiring",
    "CurriculumTurnFace",
    "LearningTurnFace",
    "LedgerTurnFace",
    "SchedulerTurnFace",
    "SupplyTurnFace",
    "UserConfigTurnFace",
    "assemble_automatic_turn",
    "automatic_moment_template",
    "conversation_priority_view_of",
    "decide_automatic_turn",
    "moment_template_of",
    "record_leg_failure",
]

#: The CP2 first action's delivery slot — the word
#: :func:`elc.runtime.automatic_teaching.automatic_action_id` spells
#: (``ga-{turn_id}-automatic-open``), so the durable action id and the delivery
#: leg's ``slot`` argument agree (``ConversationCoordinator.
#: _deliver_teaching_action`` recognizes the existing action by
#: ``action_id.endswith(slot)``, and a re-entry must not mint a second one,
#: RA §23 "继续同 action_id").
AUTOMATIC_OPEN_SLOT = "automatic-open"

#: The ``error_code`` of the durable record a leg that could not run leaves
#: (see :func:`record_leg_failure`). A word of this cut's: nothing canonical
#: names it, and the kernel's own ``FEATURE_ASSEMBLY_INCOMPLETE`` is the
#: *assembly's* verdict — reached through a run — not the leg's failure to get
#: that far.
AUTOMATIC_TURN_LEG_UNAVAILABLE = "AUTOMATIC_TURN_LEG_UNAVAILABLE"

#: §14's lock fact as ``TeachingController.observed_lock_state`` answers it
#: (BF-03 §14): the word that means "no teaching lock in this conversation".
LOCK_NONE = "NONE"
#: The two words that mean a teaching moment is live in this conversation.
LOCK_HELD_WORDS = ("OWNED_BY_THIS_MOMENT", "OWNED_BY_OTHER")


# -- the wiring --------------------------------------------------------------


class LearningTurnFace(Protocol):
    """Learning's three reads (narrowed from ``elc.learning.controller``).

    ``get_learner_target_state`` is declared with the wide parameter types
    ``elc.planner.supply.LearnerStatePort`` already uses (that port is the
    planner-side shape, and this module hands the face to it unchanged).
    """

    def get_learning_snapshot(self) -> Result[object]: ...

    def get_learning_watermark(self) -> Result[int]: ...

    def get_learner_target_state(
        self, target_id: object, evidence_modality: object
    ) -> Result[object | None]: ...


class SchedulerTurnFace(Protocol):
    """The two Scheduler reads ``elc.planner.candidates.SchedulePort`` names
    (``SchedulerController`` satisfies both)."""

    def get_schedule_item(
        self, target_type: str, target_id: object, evidence_modality: object
    ) -> Result[object | None]: ...

    def get_schedule_view(self, as_of: str) -> Result[object]: ...


class UserConfigTurnFace(Protocol):
    """The three §5.1/§9 reads of ``UserConfigController``."""

    def get_teaching_policy(self, user_id: object) -> Result[object | None]: ...

    def get_goal_portfolio(self, user_id: object) -> Result[object | None]: ...

    def get_planner_constraint_view(
        self, as_of: str, bound_conversation_id: ConversationId
    ) -> Result[object]: ...


class CurriculumTurnFace(Protocol):
    """The curriculum reads the generators and this leg consume
    (``elc.curriculum.store.CurriculumContentStore`` satisfies all of them).

    The five reads ``elc.planner.candidates`` / ``elc.planner.supply`` declare
    as their ports are handed over unchanged, and ``curriculum_version`` is the
    §4 binding this leg stamps on the cycle.
    """

    def readiness(self, entity_id: str) -> Result[object]: ...

    def get_target(self, entity_id: str) -> Result[object]: ...

    def prerequisites_of(self, node_id: object) -> Result[object]: ...

    def curriculum_links_of(self, resource_id: object) -> Result[object]: ...

    def get_capability(self, capability_id: object) -> Result[object]: ...

    def curriculum_version(self) -> Result[object]: ...


class SupplyTurnFace(Protocol):
    """The supply set (``elc.learning.silent_evidence.ContentBackedTargetSupply``
    satisfies ``elc.planner.candidates.TargetSupplyPort``'s one method)."""

    def facts(self) -> Result[Sequence[object]]: ...


class LedgerTurnFace(LedgerExposureWriter, Protocol):
    """The PlanningLedger's two halves, over one object.

    ``read_ledger`` is the view a cycle's generators read. The *write* half
    (§20's exposure events, :class:`elc.runtime.exposure.LedgerExposureWriter`)
    is consumed by the delivery path rather than by this assembly — the
    coordinator's ``_with_exposure`` / ``_record_skip_exposure`` — and it is the
    same object's faces: ``SqliteLedgerStore`` satisfies both, and the wiring
    carries it once so a leg cannot read a ledger the delivery writes somewhere
    else. (The protocol is this module's because this module declares the
    bundle; the write face's shapes are ``elc.runtime.exposure``'s, inherited
    rather than re-spelled.)
    """

    def read_ledger(self) -> Result[PlanningLedger]: ...


class SessionBudgetFace(Protocol):
    """P8-2's §5.2 view read (``TeachingController.get_session_budget_view``).

    A controller constructed without a policy source **refuses** this — an
    ``Err`` this assembly records as a missing leg (the two budget controls then
    read ``False``, which is the mapping's own fail-open posture, stated in
    :mod:`elc.runtime.automatic_controls`).
    """

    def get_session_budget_view(
        self, conversation_id: ConversationId, as_of: str
    ) -> Result[SessionBudgetView]: ...


@dataclass(frozen=True)
class AutomaticTurnWiring:
    """The optional dependency bundle the coordinator takes for this leg.

    ``planner_store`` and ``teaching`` are the two faces P8-1's unit needs
    (CP2's Planner half and the Gate/CP2 teaching half); every other field is
    one authority this assembly reads, and **all of them are optional** — an
    absent face is a leg the assembly reports as missing rather than one it
    fills. ``user_id`` is the caller's binding for the two user-keyed reads
    (declared reading 4). ``candidate_supply`` is not a port but the *value*
    :func:`assemble_automatic_turn`'s own ``supply`` argument takes: a caller
    that already holds this cycle's supply (an acceptance test, or an
    orchestrator that generated candidates earlier) hands it in here and the
    bundle's ports are then read for everything *except* the candidate set —
    the one face a caller holding the supply must not have re-derived from
    faces that may answer differently. ``None`` is production's value and the
    generators run over the ports.

    A bundle with only ``planner_store`` and ``teaching`` is legal and useful:
    the run then answers ``INCOMPLETE`` / ``DEGRADED`` on its own authority
    (nothing declared, nothing invented), which is the same verdict the shipped
    corpus produces today for a different reason.

    ``rollout_stage`` is the one field that is not a *face*: it is the
    process-level rollout declaration P8-5 formalizes
    (docs/IMPLEMENTATION_PLAN.md §12's four stages,
    :class:`elc.teaching.rollout.RolloutStage`), and it is ``None`` by default
    — an undeclared stage refuses automatic teaching rather than assuming the
    most permissive one (``elc.teaching.rollout.stage_allows_automatic``). A
    caller that means to run the automatic leg declares the stage its rollout
    is at; a caller that does not is in the state the shipped product is in.
    """

    planner_store: PlannerDecisionRecordStore
    teaching: TeachingOpenAuthority
    learning: LearningTurnFace | None = None
    scheduler: SchedulerTurnFace | None = None
    user_config: UserConfigTurnFace | None = None
    curriculum: CurriculumTurnFace | None = None
    supply: SupplyTurnFace | None = None
    ledger: LedgerTurnFace | None = None
    session_budget: SessionBudgetFace | None = None
    user_id: object | None = None
    candidate_supply: CandidateSupply | None = None
    rollout_stage: RolloutStage | None = None


# -- §4 step 3: the conversation leg -----------------------------------------


def conversation_priority_view_of(lock_state: str) -> ConversationPriorityView:
    """docs/DOMAIN_MODEL.md §13's view, produced from the conversation's own
    durable state — the producer P7-2 left unlanded.

    One fact decides all three fields: **is a teaching moment live in this
    conversation?** The durable ``active_teaching_lock`` row answers it (the
    word ``TeachingController.observed_lock_state`` reads), and:

    ===========================  ============================================
    the lock                     the view
    ===========================  ============================================
    ``NONE``                     OPEN / NORMAL / a natural break available
    ``OWNED_BY_THIS_MOMENT``     TEACHING / PROTECTED / no break
    ``OWNED_BY_OTHER``           TEACHING / PROTECTED / no break
    ===========================  ============================================

    Three arguments for that reading, and the condition that re-opens it:

    - **§13's ``PROTECTED`` is the Gate's own leg, pointed the same way.** A
      live moment is BF-03's ``HARD_PROTECTED_FLOW`` situation — teaching in
      progress must not be interrupted by another automatic opening — so the
      view and the Gate agree by construction, and this derivation is redundant
      with the lock fact on purpose: a second, weaker authority for the same
      answer is what keeps the Gate's own read the authoritative one. The Gate
      keeps the authorization authority either way (§13's closing line: the view
      "expresses the protection level and authorizes nothing");
    - **the turn boundary is the natural break.** The assembly runs after CP0 —
      the user has just finished a turn and the runtime holds the floor — which
      is §13's ``OPEN`` reading of a turn the system may speak in, and a
      mid-moment turn is ``TEACHING`` (``DECIDING_NEXT_ACTION`` territory rather
      than a fresh opening). ``DEEP_EXCHANGE`` / ``TASK_EXECUTION`` are
      *content* readings of the exchange (the task/small-talk artifact and the
      pragmatic register, RA §4 step 3's other half); this cut lands neither,
      and inventing a phase from the utterance would be a second, weaker reading
      of a fact nothing durable records;
    - **an unknown word is refused, not guessed.** The three words above are the
      lock vocabulary (``observed_lock_state`` answers exactly them), and
      anything else is a contract breach rather than a state to interpret.

    Revisit: canonical text gives a *flow* reading this leg can be derived from
    (a deep-exchange judgement, a task-mode artifact, or a §13 producer of its
    own), or §13's phase vocabulary is re-scoped for a turn boundary.
    """

    if lock_state == LOCK_NONE:
        return ConversationPriorityView(
            flow_priority=FlowPriority.NORMAL,
            interaction_phase=InteractionPhase.OPEN,
            natural_break_available=True,
        )
    if lock_state in LOCK_HELD_WORDS:
        return ConversationPriorityView(
            flow_priority=FlowPriority.PROTECTED,
            interaction_phase=InteractionPhase.TEACHING,
            natural_break_available=False,
        )
    raise ValueError(
        f"unknown teaching lock word {lock_state!r}: the durable lock reads"
        f" {LOCK_NONE}, {LOCK_HELD_WORDS[0]} or {LOCK_HELD_WORDS[1]}, and §13's"
        " view is not derived from a word this cut does not know"
    )


# -- the plan ----------------------------------------------------------------


@dataclass(frozen=True)
class AutomaticTurnPlan:
    """One ordinary turn's read-only automatic half.

    ``run`` is P7-4's record (the §8 headline fields plus the kernel's own
    outcome and trace); ``request`` is the request it ran over;
    ``conversation_priority_view`` / ``session_budget_view`` are the two views
    the controls were derived from (kept so a caller can audit the derivation
    rather than trust it); ``controls`` is what the Gate will be told;
    ``bindings`` is what this turn's cycle row is stamped with; ``selected`` is
    the candidate a selection named (``None`` when the run selected nothing),
    which is what :func:`moment_template_of` needs.

    ``notes`` is the readable record of every leg that could not be read — one
    line per missing or failed read, in the order the assembly makes them. It is
    **not** a second authority: the run's own durable trace carries the same
    gaps as BF-02 §5's ``missing_authorities`` once the planner half is recorded.
    """

    run: ShadowRun
    request: PlanningRequest
    scope: ScopeResolution
    supply: CandidateSupply
    conversation_priority_view: ConversationPriorityView | None
    session_budget_view: SessionBudgetView | None
    controls: TeachingControlFacts
    bindings: DecisionCycleBindings
    selected: CandidateProposal | None
    notes: tuple[str, ...]

    @property
    def outcome(self) -> PlanningOutcome:
        """The kernel's canonical answer (the run's own record)."""

        return self.run.outcome


# -- the assembly (RA §4 steps 3, 5–8) ---------------------------------------


def assemble_automatic_turn(
    *,
    wiring: AutomaticTurnWiring,
    conversation_id: ConversationId,
    decision_cycle_id: DecisionCycleId,
    as_of: str,
    supply: CandidateSupply | None = None,
) -> Result[AutomaticTurnPlan]:
    """Read every authority this cycle names and run the Planner over them.

    Nothing is written: the cycle row is the caller's (it needs ``bindings``
    first), and the Planner half of CP2 goes durable in
    :func:`decide_automatic_turn`. ``supply`` is the one **injection point** — a
    caller that already holds the cycle's supply (an acceptance test, or an
    orchestrator that generated candidates earlier) may hand it in, and then the
    generators are not run a second time; production passes ``None`` and the
    generators run over the wiring's faces. Both paths converge on the same
    request, the same run and the same decision chain.

    Every failure of a *read* is a leg: it makes that one argument ``None`` (and
    adds a line to ``notes``), because that is what makes the generators answer
    ``SourceGap`` / the assembly answer ``INCOMPLETE`` — BF-02 §5's own verdict —
    instead of a number nobody supplied. The two failures that *are* ``Err`` are
    caller contract breaches: a request the kernel refuses is not something to
    paper over, and neither is a lock word §13 cannot be derived from.
    """

    notes: list[str] = []
    snapshot = _read(
        wiring.learning, "get_learning_snapshot", notes, "learning snapshot"
    )
    watermark = _read(
        wiring.learning, "get_learning_watermark", notes, "learning watermark"
    )
    schedule_view = _read(
        wiring.scheduler, "get_schedule_view", notes, "schedule view", as_of
    )
    policy = _read_user(
        wiring, "get_teaching_policy", notes, "teaching policy"
    )
    portfolio = _read_user(
        wiring, "get_goal_portfolio", notes, "goal portfolio"
    )
    constraint_view = _read(
        wiring.user_config,
        "get_planner_constraint_view",
        notes,
        "planner constraint view",
        as_of,
        conversation_id,
    )
    lock_state = _read(
        wiring.teaching,
        "observed_lock_state",
        notes,
        "teaching lock",
        conversation_id,
    )
    curriculum_version = _read(
        wiring.curriculum, "curriculum_version", notes, "curriculum version"
    )
    ledger_view = _read(wiring.ledger, "read_ledger", notes, "planning ledger")
    session_budget = _read(
        wiring.session_budget,
        "get_session_budget_view",
        notes,
        "session budget view",
        conversation_id,
        as_of,
    )

    # §4 step 3's view: produced from the durable lock when it was read, and
    # absent when it was not (a view nobody could read is not a view).
    if isinstance(lock_state, str):
        try:
            priority_view: ConversationPriorityView | None = (
                conversation_priority_view_of(lock_state)
            )
        except ValueError as exc:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=str(exc),
                )
            )
    else:
        priority_view = None

    constraints = cast("PlannerConstraintView | None", constraint_view)
    scope = resolve_user_intent_scope(constraints)
    request = PlanningRequest(
        decision_cycle_id=decision_cycle_id,
        learning_snapshot=snapshot,
        curriculum_candidate_view=None,
        schedule_view=schedule_view,
        goal_view=portfolio,
        teaching_policy_view=policy,
        context_opportunity_set=None,
        planner_constraint_view=constraints,
        session_budget_view=(
            session_budget
            if isinstance(session_budget, SessionBudgetView)
            else None
        ),
        user_intent_scope=scope.scope,
        conversation_priority_view=priority_view,
        planning_ledger=None,
    )
    if supply is None:
        supply = generate_candidates(
            CandidateSupplyInputs(
                as_of=as_of,
                targets=cast("TargetSupplyPort | None", wiring.supply),
                target_rows=cast("TargetRowPort | None", wiring.curriculum),
                readiness=cast("ReadinessPort | None", wiring.curriculum),
                prerequisites=cast("PrerequisitePort | None", wiring.curriculum),
                learner_state=cast("LearnerStatePort | None", wiring.learning),
                schedule=cast("SchedulePort | None", wiring.scheduler),
                constraints=constraints,
                priority=priority_view,
                observation=None,
                ledger=(
                    ledger_view
                    if isinstance(ledger_view, PlanningLedger)
                    else None
                ),
            )
        )

    try:
        run = run_shadow(
            request,
            supply=supply,
            current_learning_watermark=(
                watermark if isinstance(watermark, int) else None
            ),
        )
        selected = _selected_of(run, supply)
    except (TypeError, ValueError) as exc:
        # A kernel input contract breach, or a selection the supply does not
        # carry, is the caller's data (P7-4 judgement 6: the kernel raises such
        # a breach rather than answering a status) — reported, never swallowed
        # into a fabricated status.
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"the planner run refused decision cycle"
                    f" {decision_cycle_id}: {exc}"
                ),
            )
        )

    controls = replace(
        TeachingControlFacts.derived(
            session_budget_view=(
                session_budget
                if isinstance(session_budget, SessionBudgetView)
                else None
            ),
            conversation_priority_view=priority_view,
        ),
        # P8-1 disposal F2: the wiring passes the value the Planner assembled —
        # and P8-5 composes it with the stage leg the Gate's registration names
        # (mode × rollout stage). The Planner's value is the mode leg's answer
        # read once (TEACHING_FREQUENCY_TO_PROFILE through the §5.1 row); the
        # stage leg is the wiring's declaration, fail-closed when absent.
        automatic_teaching_enabled=(
            run.trace.context.automatic_teaching_enabled
            and stage_allows_automatic(wiring.rollout_stage)
        ),
    )
    return Ok(
        AutomaticTurnPlan(
            run=run,
            request=request,
            scope=scope,
            supply=supply,
            conversation_priority_view=priority_view,
            session_budget_view=(
                session_budget
                if isinstance(session_budget, SessionBudgetView)
                else None
            ),
            controls=controls,
            bindings=_bindings_of(
                snapshot=snapshot,
                curriculum_version=curriculum_version,
                policy=policy,
                portfolio=portfolio,
                schedule_view=schedule_view,
            ).decision_cycle_bindings(),
            selected=selected,
            notes=tuple(notes),
        )
    )


def _read(
    face: object | None,
    name: str,
    notes: list[str],
    label: str,
    *args: object,
) -> object | None:
    """One best-effort read: the value, or ``None`` with a note saying why.

    The three failure shapes are the repository's own reading of an optional
    authority (``ConversationCoordinator._persona_views_for``'s): the face is
    absent, the read answered ``Err``, or the read raised. All three mean "this
    leg is not available", and all three are recorded — the one thing this
    helper never does is invent a value.
    """

    if face is None:
        notes.append(f"{label}: no face was wired")
        return None
    method = getattr(face, name, None)
    if method is None:
        notes.append(f"{label}: the face declares no {name} read")
        return None
    try:
        answer = method(*args)
    except Exception as exc:  # noqa: BLE001 — a broken port is a missing leg
        notes.append(f"{label}: the read raised {exc!r}")
        return None
    if isinstance(answer, Err):
        notes.append(f"{label}: the read refused with {answer.error.message}")
        return None
    if isinstance(answer, Ok):
        return answer.value
    notes.append(f"{label}: the read answered {type(answer).__name__}")
    return None


def _read_user(
    wiring: AutomaticTurnWiring, name: str, notes: list[str], label: str
) -> object | None:
    """A user-keyed read, skipped (with a note) when no user was bound.

    Declared reading 4: the user leg is the caller's binding, and calling a
    user-keyed store with no user would ask a question with no subject.
    """

    if wiring.user_id is None:
        notes.append(f"{label}: no user binding was wired")
        return None
    return _read(wiring.user_config, name, notes, label, wiring.user_id)


def _selected_of(
    run: ShadowRun, supply: CandidateSupply
) -> CandidateProposal | None:
    """The proposal the run selected, out of the supply it ran over.

    The decision names the candidate by id (§14's ``selected_candidate_id``) and
    the supply holds the record, so this is a lookup rather than a
    re-derivation. A selection whose candidate the supply does not carry is a
    caller contract breach: the run cannot have selected a candidate it was not
    given.
    """

    selected_id = run.would_have_selected
    if selected_id is None:
        return None
    for proposal in supply.proposals:
        if proposal.candidate_id == selected_id:
            return proposal
    raise ValueError(
        f"the planner run selected candidate {selected_id!r}, which the supply"
        " it ran over does not carry: the selection and the candidate set are"
        " the same call's answers (elc.planner.candidates)"
    )


@dataclass(frozen=True)
class _Bindings:
    """The six §4 bindings this assembly can read."""

    learning_snapshot_id: str | None
    evidence_watermark: int | None
    curriculum_version: str | None
    goal_version: str | None
    schedule_version: str | None
    policy_version: str | None

    def decision_cycle_bindings(self) -> DecisionCycleBindings:
        """§4's column set; the two columns no leg here reads stay ``None``.

        ``context_view_version`` / ``relationship_view_version`` have no source
        in this assembly (the §11 views are the prompt's, read by the persona
        side), and ``None`` is their honest "no source" value — never a
        fabricated version.
        """

        return DecisionCycleBindings(
            learning_snapshot_id=self.learning_snapshot_id,
            evidence_watermark=self.evidence_watermark,
            curriculum_version=self.curriculum_version,
            goal_version=self.goal_version,
            schedule_version=self.schedule_version,
            policy_version=self.policy_version,
        )


def _bindings_of(
    *,
    snapshot: object | None,
    curriculum_version: object | None,
    policy: object | None,
    portfolio: object | None,
    schedule_view: object | None,
) -> _Bindings:
    """§4's six readable bindings, each stamped only from a value that was read.

    Each word is taken from the record the same read produced — the snapshot
    answers its own id **and** the watermark it was assembled at (R-INV-003:
    the cycle fixes the snapshot, not a later one), and the three version words
    come off the §5.1/§10 records the request carries.
    """

    snapshot_id: str | None = None
    snapshot_watermark: int | None = None
    if snapshot is not None:
        read_id = getattr(snapshot, "learning_snapshot_id", None)
        snapshot_id = None if read_id is None else str(read_id)
        read_watermark = getattr(snapshot, "evidence_watermark", None)
        if isinstance(read_watermark, int):
            snapshot_watermark = read_watermark
    return _Bindings(
        learning_snapshot_id=snapshot_id,
        evidence_watermark=snapshot_watermark,
        curriculum_version=_word(curriculum_version),
        goal_version=_word(portfolio, "goal_version"),
        schedule_version=_word(schedule_view, "schedule_version"),
        policy_version=_word(policy, "policy_version"),
    )


def _word(record: object | None, name: str | None = None) -> str | None:
    """One version word off a record, or ``None`` when there is no value.

    ``name is None`` means the record *is* the value (the curriculum version
    read answers a bare word rather than a record).
    """

    value = record if name is None else getattr(record, name, None)
    return None if value is None else str(value)


# -- the moment template (§15) ----------------------------------------------


def automatic_moment_template(
    *,
    turn_id: TurnId,
    conversation_id: ConversationId,
    persona_id: PersonaId | None,
    decision_cycle_id: DecisionCycleId,
    candidate: CandidateProposal,
    target_type: str,
) -> TeachingMomentRecord:
    """The §15 template of the moment an ALLOW would open (declared reading 3).

    Everything the unit refuses to see pre-set is set to the value it derives
    (``source`` / ``lifecycle_state`` / ``presentation_phase``, and the two
    identity columns from the turn), the teaching content comes from the
    selected candidate, and the bindings are left ``None`` because the unit
    stamps them from the durable cycle — this record is a *template*, not a
    plan of record.
    """

    return TeachingMomentRecord(
        moment_id=automatic_moment_id(turn_id),
        conversation_id=conversation_id,
        persona_id=persona_id,
        source=MomentSource.AUTOMATIC,
        decision_cycle_id=decision_cycle_id,
        candidate_id=candidate.candidate_id,
        gate_decision_id=automatic_gate_decision_id(turn_id),
        focus_target=TeachingTargetRef(
            target_type=target_type, target_id=candidate.focus_target
        ),
        supporting_targets=(),
        target_mode=candidate.target_mode.value,
        learning_intent=candidate.learning_intent.value,
        evidence_modality=EvidenceModality(candidate.evidence_modality),
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MomentState.OPENING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.NONE,
        completion_outcome=None,
        abort_reason=None,
        state_version=1,
    )


def moment_template_of(
    *,
    plan: AutomaticTurnPlan,
    turn_id: TurnId,
    conversation_id: ConversationId,
    persona_id: PersonaId | None,
    decision_cycle_id: DecisionCycleId,
    wiring: AutomaticTurnWiring,
) -> Result[TeachingMomentRecord]:
    """The template for a plan that selected something, or a refusal.

    The one field the candidate does not carry — its §11 ``target_type`` — is
    read off the target's own row here (declared reading 3); a run that selected
    nothing has no template to build, and
    :func:`decide_automatic_turn` passes ``None`` to the unit instead.
    """

    candidate = plan.selected
    if candidate is None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"the run of cycle {decision_cycle_id} selected nothing, so"
                    " there is no moment to template (an ALLOW needs one)"
                ),
            )
        )
    row = _read(
        wiring.curriculum,
        "get_target",
        [],
        "target row",
        candidate.focus_target,
    )
    target_type = None if row is None else getattr(row, "target_type", None)
    if not isinstance(target_type, str):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"the target row of {candidate.focus_target!r} was not read,"
                    " so the moment cannot name its §11 target type"
                ),
            )
        )
    return Ok(
        automatic_moment_template(
            turn_id=turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
            decision_cycle_id=decision_cycle_id,
            candidate=candidate,
            target_type=target_type,
        )
    )


# -- the decision (RA §4 steps 9A–10B) ---------------------------------------


def decide_automatic_turn(
    *,
    wiring: AutomaticTurnWiring,
    plan: AutomaticTurnPlan,
    turn_id: TurnId,
    conversation_id: ConversationId,
    persona_id: PersonaId | None,
    cycle: DecisionCycleRecord,
    owner_epoch: int,
) -> Result[AutomaticTeachingResult]:
    """Hand one plan to P8-1's unit: Planner records → Gate → CP2.

    The unit owns the order and every refusal; this function only supplies what
    it declares: the plan's outcome, the plan's controls, the turn's identifiers,
    the run's own kernel trace (``plan.run.trace`` — P9-0: it is what the
    durable ``factor_trace`` document's ``candidates`` are built from) and the
    §15 template (``None`` when the run selected nothing — such a run is
    decided before any template is read, and an ALLOW without one is refused by
    the unit rather than guessed here).
    """

    template: TeachingMomentRecord | None = None
    if plan.selected is not None:
        built = moment_template_of(
            plan=plan,
            turn_id=turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
            decision_cycle_id=cycle.decision_cycle_id,
            wiring=wiring,
        )
        if isinstance(built, Err):
            return built
        template = built.value
    return decide_automatic_teaching(
        turn=AutomaticTeachingTurn(
            turn_id=turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
            cycle=cycle,
            moment=template,
            owner_epoch=owner_epoch,
        ),
        outcome=plan.outcome,
        controls=plan.controls,
        planner_store=wiring.planner_store,
        teaching=wiring.teaching,
        user_intent_scope=plan.scope.scope.value,
        trace=plan.run.trace,
    )


# -- a leg that could not run, recorded rather than dropped ------------------


def record_leg_failure(
    *,
    wiring: AutomaticTurnWiring,
    turn_id: TurnId,
    decision_cycle_id: DecisionCycleId,
    reason: str,
) -> Result[PlannerCycleRecords]:
    """Make an automatic leg that could not run **readable** (RA §4 step 9A).

    A leg failure — an exception out of a port, a request the kernel refuses, an
    ``Err`` from the unit before it wrote anything — means the turn proceeds as
    an ordinary conversation turn (RA §21), and the reason must not vanish: this
    records the canonical degraded shape §4's step 9A names,
    ``PlannerExecutionStatus = DEGRADED`` with ``RuntimeDecisionOutcome =
    DEGRADED_NO_AUTOMATIC_TEACHING`` and **no** synthetic ``PlannerDecision`` —
    through P8-0's own store, the same unit a run uses.

    The evaluation it carries is the honest empty one (no ranking happened): its
    ``reason_trace`` is the readable reason, and the two version words name the
    planner and policy profile that would have been responsible — they are the
    kernel's own constants, quoted rather than minted, and nothing here claims a
    run happened (the status's ``error_code`` is
    :data:`AUTOMATIC_TURN_LEG_UNAVAILABLE`).

    **A cycle that carries this record does not get a second planner half.** The
    store's replay rule refuses a differing re-submission (``elc.planner.records``
    judgement 3, executed by ``SqlitePlannerRecordStore._replay``: a differing
    status word, ``error_code``, evaluation or decision under an existing cycle
    is a ``CONFLICT``), and the caller's write is best-effort
    (``ConversationCoordinator._record_automatic_leg_failure`` swallows the
    ``Err``), so a re-entry whose assembly would now succeed only earns that
    refusal and is dropped: the durable answer stays the one that was recorded,
    never overwritten. The asymmetry cuts the other way too, and it is the same
    rule: a cycle the unit already wrote (a durable ``SUCCEEDED`` / ``SELECT``
    and its Gate trace) **cannot** be re-labelled by a later leg failure, so a
    failure that happens *after* CP2 — the delivery leg's own read-back refusing
    a missing or foreign first action — leaves no ``AUTOMATIC_TURN_LEG_UNAVAILABLE``
    row at all; the CP2 half stays as the unit wrote it and the turn proceeds as
    an ordinary one (registered in
    ``tests/phase8/test_p8_4_turn_integration.py``). That is the correct side of
    the trade — a status is a fact, not a mutable label — and it is registered
    here rather than left to a reader. Revisit: a cut gives a leg failure a
    retryable carrier of its own (a status word the store may move for one
    cycle), which is the same Revisit ``elc.planner.records`` judgement 3 names.
    """

    outcome = PlanningOutcome(
        evaluation=PlannerEvaluation(
            planner_evaluation_id=PlannerEvaluationId(f"pe-{decision_cycle_id}"),
            decision_cycle_id=decision_cycle_id,
            planner_version=PlannerVersion(PLANNER_KERNEL_MODEL_VERSION),
            policy_version=PolicyVersion(PLANNER_PROFILE_VERSION),
            ranked_candidates=(),
            reason_trace=(reason,),
            frontier_candidate_ids=(),
        ),
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=decision_cycle_id,
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code=AUTOMATIC_TURN_LEG_UNAVAILABLE,
        ),
        decision=None,
    )
    return wiring.planner_store.record_planner_cycle(
        turn_id=turn_id, outcome=outcome
    )
