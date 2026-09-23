"""Teaching Domain Controller — Gate authority + TeachingMoment lifecycle.

Phase 3 P3-1A (TASK-OPI-2babb21e-….17 ③④): this controller graduates from
the Phase 0 empty skeleton into the real Teaching authority face (the P3-0
LearningController graduation precedent). docs/DOMAIN_MODEL.md §18: the
Domain Controller decides VALIDATE / COMMIT / REJECT / ABSTAIN. The Gate's
decision policy is pure (elc.teaching.gate) and the durable executor is the
domain store (elc.teaching.store, which carries the epoch fence and all
SQL), so this controller is a delegating authority face:

- :meth:`decide_user_initiated_open` — the Gate's USER_INITIATED OPEN
  profile; a pure decision (no writes),
- :meth:`commit_cp2_open` — the CP2 five-fact atomic open (one short
  transaction: GateExecutionStatus(SUCCEEDED) + GateDecision(ALLOW) +
  TeachingMoment(OPENING) + active_teaching_lock + GenerationActionIntent
  (TEACHING_OPEN, PREPARED)),
- :meth:`record_gate_denial` / :meth:`record_gate_degraded` — the other two
  Gate outputs (two facts / one fact),
- reads :meth:`get_active_moment` / :meth:`get_moment` /
  :meth:`get_moment_for_cycle` / :meth:`observed_lock_state`.

Phase 0 protocol scope (declared, so a consumer never has to guess what is
missing): the frozen ``TeachingCommands`` / ``TeachingQueries`` signatures
stay exactly as Phase 0 wrote them, and the P3-1A faces above are
deliberately *not* forced into them — ``decide_gate(candidate_id, context,
decision_cycle_id, moment_id)`` and ``open_teaching_moment(moment)`` carry
neither the critical fact bundle the Gate consumes nor the other four CP2
facts, so those frozen shapes raise NotImplementedError with a pointer to
the real entry point. The continuation / automatic paths (P3-1B, Phase 8)
own the eventual protocol reshape, exactly as they own
``record_attempt`` / ``record_attempt_evaluation`` /
``terminalize_moment`` / ``issue_ephemeral_directive``.

Phase 8 P8-2 adds the session-budget read: :meth:`get_session_budget_view`
produces docs/DATA_MODEL.md §5.2's ``Derived view`` for one conversation at
one instant (a **pure read** — :mod:`elc.teaching.budget` carries the
derivation, the store carries the rows) and
:meth:`count_automatic_probe_moments` the probe-usage count the view's
``probe_budget_remaining`` cannot subtract without a policy vocabulary. Both
are the ``SchedulerController.get_schedule_view`` shape: the domain that owns
the rows produces the view a consumer reads. The policy leg arrives through
an injected narrow port (the store carries no policy row), and a controller
constructed without one **refuses** the view instead of answering with a
policy leg it never read — the ``SchedulerController`` /
``LearningReadPort`` posture.
"""

from __future__ import annotations

from elc.platform.types import (
    ActionId,
    AttemptEvaluationId,
    AttemptId,
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    MomentId,
    Ok,
    Result,
    RuntimeEpoch,
    TargetId,
    UserTurnId,
)
from elc.teaching.budget import (
    SessionBudgetPolicySource,
    automatic_probe_moments_used,
    session_budget_view_of,
)
from elc.teaching.gate import (
    ContinuationFacts,
    GateVerdict,
    UserInitiatedOpenFacts,
)
from elc.teaching.gate import decide_user_initiated_open as decide_open_facts
from elc.teaching.gate import (
    decide_user_requested_continuation as decide_continuation_facts,
)
from elc.teaching.ladder import ladder_step
from elc.teaching.limits import TeachingLoad
from elc.teaching.store import (
    CP2OpenRequest,
    MomentTransition,
    SqliteTeachingStore,
)
from elc.teaching.types import (
    AttemptEvaluationRecord,
    AttemptRecord,
    EphemeralTeachingDirective,
    GateDecisionId,
    GateDecisionRecord,
    GateExecutionStatusRecord,
    SessionBudgetView,
    TeachingMomentRecord,
)

__all__ = ["TeachingController"]

#: delivery kind → §20 action_type (the five teaching action types).
_ACTION_BY_DELIVERY = {
    "OPENING": "TEACHING_OPEN",
    "HINT": "TEACHING_HINT",
    "RETRY": "TEACHING_HINT",
    "REVEAL": "TEACHING_REVEAL",
    "EXPLANATION": "TEACHING_EXPLANATION",
}


class TeachingController:
    """Owns TeachingMoment lifecycle + Gate authority over SqliteTeachingStore."""

    def __init__(
        self,
        store: SqliteTeachingStore,
        *,
        policy: SessionBudgetPolicySource | None = None,
    ) -> None:
        """The durable teaching store, plus the optional policy leg.

        ``policy`` is the §5.1 half of the session-budget view's derivation
        (docs/DOMAIN_MODEL.md §13: ``TeachingPolicyProfile`` + Runtime Session
        State). It is optional exactly as the Scheduler's Learning port is: a
        controller that never produces a budget view needs none, and
        :meth:`get_session_budget_view` **refuses** without it rather than
        answering ``policy_version=None`` for a row it never read — "no policy
        is configured" and "no policy read face was wired" are different facts
        and the view may not conflate them.
        """

        self._store = store
        self._policy = policy

    # -- P3-1A authority faces ---------------------------------------------

    def decide_user_initiated_open(
        self, facts: UserInitiatedOpenFacts
    ) -> GateVerdict:
        """The Gate's USER_INITIATED OPEN applicable profile (BF-03 v1.1
        semantics; no writes — the caller persists the verdict through the
        commit faces below)."""

        return decide_open_facts(facts)

    def commit_cp2_open(self, request: CP2OpenRequest) -> Result[MomentId]:
        """CP2: the five-fact atomic open (docs/RUNTIME_ARCHITECTURE.md §6;
        §4 step 10B). Five facts or none."""

        return self._store.open_teaching_moment(request)

    def record_gate_denial(
        self,
        status: GateExecutionStatusRecord,
        decision: GateDecisionRecord,
    ) -> Result[GateDecisionId]:
        """DENY: GateExecutionStatus(SUCCEEDED) + GateDecision(DENY), one
        short transaction; never a Moment / Lock / Action."""

        return self._store.record_gate_denial(status, decision)

    def record_gate_allow(
        self,
        status: GateExecutionStatusRecord,
        decision: GateDecisionRecord,
    ) -> Result[GateDecisionId]:
        """ALLOW of a *continuation*: GateExecutionStatus(SUCCEEDED) +
        GateDecision(ALLOW), one short transaction (the P3-1B authorization
        trace). An opening ALLOW stays the CP2 five-fact unit."""

        return self._store.record_gate_allow(status, decision)

    def record_gate_degraded(
        self, status: GateExecutionStatusRecord
    ) -> Result[str]:
        """DEGRADED: one GateExecutionStatus row, no GateDecision — no
        synthetic DENY (docs/DATA_MODEL.md §14.1)."""

        return self._store.record_gate_degraded(status)

    def observed_lock_state(
        self,
        conversation_id: ConversationId,
        moment_id: MomentId | None = None,
    ) -> Result[str]:
        """BF-03 §14 lock fact: NONE / OWNED_BY_THIS_MOMENT / OWNED_BY_OTHER
        from the durable active_teaching_lock row (the Gate itself never
        touches storage)."""

        holder = self._store.get_lock_moment_id(conversation_id)
        if isinstance(holder, Err):
            return holder
        current = holder.value
        if current is None:
            return Ok("NONE")
        if moment_id is not None and current == moment_id:
            return Ok("OWNED_BY_THIS_MOMENT")
        return Ok("OWNED_BY_OTHER")

    # -- reads ---------------------------------------------------------------

    def get_active_moment(
        self, conversation_id: ConversationId
    ) -> Result[TeachingMomentRecord | None]:
        """The active moment of one conversation (durable lock lookup)."""

        return self._store.get_active_moment(conversation_id)

    def get_moment(
        self, moment_id: MomentId
    ) -> Result[TeachingMomentRecord | None]:
        return self._store.get_moment(moment_id)

    def get_moment_for_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[TeachingMomentRecord | None]:
        """The moment opened by one cycle — the CP2 replay lookup."""

        return self._store.get_moment_for_cycle(decision_cycle_id)

    def get_gate_decisions(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[tuple[GateDecisionRecord, ...]]:
        """The durable GateDecision rows of one cycle, oldest first (the
        replay face: a DENY turn re-reads its reasons instead of re-running
        the Gate)."""

        return self._store.get_gate_decisions(decision_cycle_id)

    def get_gate_execution_statuses(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[tuple[GateExecutionStatusRecord, ...]]:
        """The durable GateExecutionStatus rows of one cycle, oldest first
        (DEGRADED traces included)."""

        return self._store.get_gate_execution_statuses(decision_cycle_id)

    # -- the session budget read (P8-2, docs/DATA_MODEL.md §5.2) ------------

    def get_session_budget_view(
        self, conversation_id: ConversationId, as_of: str
    ) -> Result[SessionBudgetView]:
        """The conversation's §5.2 session budget at ``as_of`` — a pure read.

        The two authorities docs/DOMAIN_MODEL.md §13 names, read and composed
        once: the conversation's durable ``teaching_moment`` history (Runtime
        Session State's durable half) through the store, and the §5.1 policy
        row through the injected :class:`~elc.teaching.budget.
        SessionBudgetPolicySource`. The derivation itself is
        :func:`elc.teaching.budget.session_budget_view_of` — every field's
        reading, every declared window and every refusal is stated there, and
        nothing is recomputed here.

        ``as_of`` is an argument rather than a clock read for the
        ``ScheduleView`` reason: a view is reproducible, so two consumers
        asking about the same instant see the same picture and a test can pin
        it. Nothing is written (the rows are read, the view is derived) and no
        table carries the result — §5.2 labels the block ``Derived view``.

        Three refusals, each with its own reason:

        - no policy port was injected ⇒ ``DEPENDENCY_UNAVAILABLE`` (see
          :meth:`__init__`): the view will not report
          ``policy_version=None`` for a policy it never read;
        - the policy read itself failed ⇒ that ``Err``, verbatim;
        - an unusable instant in the rows or in ``as_of`` ⇒ the derivation's
          ``VALIDATION_FAILED`` (never a dropped row — the budget must not be
          understated).
        """

        if self._policy is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "get_session_budget_view needs the TeachingPolicyProfile"
                        " read face (docs/DOMAIN_MODEL.md §13: the view is"
                        " derived from the policy profile + Runtime Session"
                        " State): this controller was constructed without a"
                        " policy source, and the view will not report a policy"
                        " version it never read"
                    ),
                )
            )
        policy = self._policy.get_teaching_policy(self._policy.user_id)
        if isinstance(policy, Err):
            return policy
        moments = self._store.list_moments_for_conversation(conversation_id)
        if isinstance(moments, Err):
            return moments
        return session_budget_view_of(
            conversation_id=conversation_id,
            as_of=as_of,
            policy=policy.value,
            moments=moments.value,
        )

    def count_automatic_probe_moments(
        self, conversation_id: ConversationId
    ) -> Result[int]:
        """The conversation's automatic §11 ``PROBE`` openings — the *usage*
        leg of §5.2's ``probe_budget_remaining``.

        The view's ``probe_budget_remaining`` is ``None`` because §5.1 pins no
        budget vocabulary to subtract from, not because the usage is unknown;
        this face makes the usage readable on its own (the derivation is
        :func:`elc.teaching.budget.automatic_probe_moments_used`, over the
        same durable rows the view reads). Closed and live moments both count,
        the way ``automatic_teaching_used`` counts the view's own history.
        """

        moments = self._store.list_moments_for_conversation(conversation_id)
        if isinstance(moments, Err):
            return moments
        return Ok(
            automatic_probe_moments_used(
                conversation_id=conversation_id, moments=moments.value
            )
        )

    # -- frozen Phase 0 protocol shapes (pointers, not logic) ---------------

    def decide_gate(
        self,
        candidate_id: str,
        context: str,
        decision_cycle_id: str | None,
        moment_id: str | None,
    ) -> Result[GateDecisionRecord | GateExecutionStatusRecord]:
        raise NotImplementedError(
            "the frozen Phase 0 shape carries no critical fact bundle;"
            " use decide_user_initiated_open(UserInitiatedOpenFacts)"
            " (P3-1A) / decide_user_requested_continuation("
            "ContinuationFacts) (P3-1B); the automatic contexts are decided"
            " by decide_automatic_open / decide_auto_continuation (P8-1,"
            " elc.teaching.gate)"
        )

    def open_teaching_moment(
        self, moment: TeachingMomentRecord
    ) -> Result[MomentId]:
        raise NotImplementedError(
            "CP2 needs all five facts (GateExecutionStatus + GateDecision +"
            " Moment + Lock + first action); use commit_cp2_open("
            "CP2OpenRequest) (P3-1A)"
        )

    # -- P3-1B authority faces ----------------------------------------------

    def decide_user_requested_continuation(
        self, facts: ContinuationFacts
    ) -> GateVerdict:
        """The Gate's USER_REQUESTED_CONTINUE profile (BF-03 v1.1
        continuation branch; ACTIVE_MOMENT authorization, §8 hard caps
        included). Pure — the caller persists / acts on the verdict."""

        return decide_continuation_facts(facts)

    def record_attempt(self, attempt: AttemptRecord) -> Result[AttemptId]:
        """One durable AttemptRecord + the moment's attempt counter."""

        return self._store.record_attempt(attempt)

    def record_attempt_evaluation(
        self, evaluation: AttemptEvaluationRecord
    ) -> Result[AttemptEvaluationId]:
        """One durable AttemptEvaluationRecord (§17: durable before the
        next irreversible teaching action)."""

        return self._store.record_attempt_evaluation(evaluation)

    def transition_moment(
        self,
        moment_id: MomentId,
        transition: MomentTransition,
        expected_state_version: int,
    ) -> Result[TeachingMomentRecord]:
        """One CAS-guarded moment advance (ladder / lifecycle / closure)."""

        return self._store.transition_moment(
            moment_id, transition, expected_state_version
        )

    def terminalize_moment(
        self,
        moment_id: MomentId,
        *,
        completion_outcome: str | None = None,
        abort_reason: str | None = None,
    ) -> Result[TeachingMomentRecord]:
        """TEACHING_TERMINAL + TeachingLockLease release, one short
        transaction (STATE_MACHINES §9; DATA_MODEL §18)."""

        return self._store.terminalize_moment(
            moment_id,
            completion_outcome=completion_outcome,
            abort_reason=abort_reason,
        )

    def count_attempts(self, moment_id: MomentId) -> int:
        return self._store.count_attempts(moment_id)

    def count_delivered_teaching_turns(self, moment_id: MomentId) -> int:
        """The §8 teaching-turn count: delivered TEACHING_OPEN / HINT /
        REVEAL / EXPLANATION actions of the moment."""

        return self._store.count_delivered_teaching_turns(moment_id)

    def count_delivered_slot_actions(
        self, moment_id: MomentId, slot: str
    ) -> int:
        """Delivered actions of one ladder slot (P3-1B crash reconciliation):
        how many hint / retry / reveal / explanation messages really went
        out, so a rung can be rebuilt from durable facts."""

        return self._store.count_delivered_slot_actions(moment_id, slot)

    def teaching_load(self, moment_id: MomentId) -> TeachingLoad:
        """Both §8 counts as one value (the continuation gate's input)."""

        return TeachingLoad(
            attempt_count=self._store.count_attempts(moment_id),
            teaching_turn_count=self._store.count_delivered_teaching_turns(
                moment_id
            ),
        )

    def get_attempts(
        self, moment_id: MomentId
    ) -> Result[tuple[AttemptRecord, ...]]:
        return self._store.get_attempts(moment_id)

    def get_attempt_for_turn(
        self, moment_id: MomentId, user_turn_id: UserTurnId
    ) -> Result[AttemptRecord | None]:
        """The attempt one user turn already contributed to one moment
        (None = not recorded yet). The (moment, user turn) pair is the
        attempt's idempotency key (review F3), so a re-entry reads the
        durable attempt instead of deriving a new index."""

        return self._store.get_attempt_for_turn(moment_id, user_turn_id)

    def recover_orphan_locks(self) -> Result[tuple[str, ...]]:
        """Startup recovery for the TeachingLockLease (STATE_MACHINES §9).

        The store's durable representation is the ``active_teaching_lock``
        row; a lock whose owning turn belongs to an older ``runtime_epoch``
        is residue from a dead process, so it is released (and its moment
        closed with ``SYSTEM_RECOVERY_ABORT``) in one short transaction.
        Local V1 deliberately has no TTL/heartbeat — the epoch is the
        liveness fact (§9/§24.1).
        """

        return self._store.recover_orphan_teaching_locks(
            self._store.current_epoch
        )

    def orphan_teaching_lock_moments(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        """The startup scan's teaching-lock read face (P3-2 carry-over ①).

        Satisfies the runtime package's ``TeachingLockRecoverySource``
        protocol, so ``StartupRecoveryScanner`` can name the orphan locks
        of a dead epoch in its plan (the runtime package itself stays
        SQL-free) and the coordinator's ``recover_orphan_teaching`` is the
        one apply face for exactly the ids the scan reported.
        """

        return self._store.orphan_teaching_lock_moments(current_epoch)

    def get_attempt_evaluation(
        self, attempt_id: AttemptId
    ) -> Result[AttemptEvaluationRecord | None]:
        """The durable evaluation of one attempt (None = not evaluated yet
        — the crash-between-attempt-and-evaluation state, which the
        re-entry path finishes)."""

        return self._store.get_attempt_evaluation(attempt_id)

    def evidence_proposal_refs(
        self,
    ) -> Result[tuple[tuple[str, tuple[str, ...]], ...]]:
        """Every evaluation's §17 ``evidence_proposal_refs``, in durable
        order (P4-2; DEC-…5ba74efc.96 F1).

        A pure delegation to the domain store — the authority face owns no
        reconciliation policy: the runtime checks each ref against Learning's
        own proposal read and reports the dangling ones. Satisfies the
        runtime package's ``TeachingEvidenceRefSource`` protocol, so the
        startup line can ask for the refs without the runtime touching SQL
        (Gate item 2) and without the teaching package importing Learning.
        """

        return self._store.evidence_proposal_refs()

    def issue_ephemeral_directive(
        self,
        moment_id: MomentId,
        *,
        action_id: ActionId | None = None,
        delivery_kind: str = "OPENING",
        text: str | None = None,
        hint_ladder: tuple[str, ...] = (),
        reveal_form: str | None = None,
    ) -> Result[EphemeralTeachingDirective]:
        """Teaching Planner: the moment's current ladder position as a
        directive for Persona Runtime.

        The directive is derived from the *durable* moment (its focus
        target, phase, support and attempt counter) and the target
        fixture's rungs — never from the provider, which only ever receives
        the finished phase/support (TASK-…2.2 ⑤ "provider 不自定阶段")."""

        moment_result = self._store.get_moment(moment_id)
        if isinstance(moment_result, Err):
            return moment_result
        moment = moment_result.value
        if moment is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=f"moment not found: {moment_id}",
                )
            )
        step = ladder_step(
            current_phase=moment.presentation_phase.value,
            current_support=moment.support_level.value,
            hint_ladder=hint_ladder,
            reveal_form=reveal_form,
            delivery_kind=delivery_kind,
        )
        hint_text = step.text if step.delivery_kind == "HINT" else None
        reveal_text = step.text if step.delivery_kind == "REVEAL" else None
        explanation_text = (
            step.text if step.delivery_kind == "EXPLANATION" else None
        )
        return Ok(
            EphemeralTeachingDirective(
                moment_id=moment.moment_id,
                action_id=(
                    action_id if action_id is not None else ActionId("")
                ),
                focus_target_id=TargetId(moment.focus_target.target_id),
                hint=hint_text,
                focus_target_type=moment.focus_target.target_type,
                action_type=_ACTION_BY_DELIVERY.get(
                    step.delivery_kind, "TEACHING_HINT"
                ),
                presentation_phase=step.presentation_phase,
                support_level=step.support_level,
                attempt_index=moment.attempt_index,
                teaching_text=text if text is not None else step.text,
                reveal_text=reveal_text,
                explanation_text=explanation_text,
            )
        )
