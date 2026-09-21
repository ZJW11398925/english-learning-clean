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
"""

from __future__ import annotations

from elc.platform.types import (
    AttemptEvaluationId,
    AttemptId,
    ConversationId,
    DecisionCycleId,
    Err,
    MomentId,
    Ok,
    Result,
)
from elc.teaching.gate import GateVerdict, UserInitiatedOpenFacts
from elc.teaching.gate import (
    decide_user_initiated_open as decide_open_facts,
)
from elc.teaching.store import CP2OpenRequest, SqliteTeachingStore
from elc.teaching.types import (
    AttemptEvaluationRecord,
    AttemptRecord,
    EphemeralTeachingDirective,
    GateDecisionId,
    GateDecisionRecord,
    GateExecutionStatusRecord,
    MomentState,
    TeachingMomentRecord,
)

__all__ = ["TeachingController"]


class TeachingController:
    """Owns TeachingMoment lifecycle + Gate authority over SqliteTeachingStore."""

    def __init__(self, store: SqliteTeachingStore) -> None:
        self._store = store

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
            " (P3-1A) — the generic continuation/automatic shape is"
            " P3-1B / Phase 8"
        )

    def open_teaching_moment(
        self, moment: TeachingMomentRecord
    ) -> Result[MomentId]:
        raise NotImplementedError(
            "CP2 needs all five facts (GateExecutionStatus + GateDecision +"
            " Moment + Lock + first action); use commit_cp2_open("
            "CP2OpenRequest) (P3-1A)"
        )

    def record_attempt(self, attempt: AttemptRecord) -> Result[AttemptId]:
        raise NotImplementedError("P3-1B: attempt recording")

    def record_attempt_evaluation(
        self, evaluation: AttemptEvaluationRecord
    ) -> Result[AttemptEvaluationId]:
        raise NotImplementedError("P3-1B: attempt evaluation")

    def terminalize_moment(
        self, moment_id: MomentId, outcome: str
    ) -> Result[MomentState]:
        raise NotImplementedError("P3-1B: terminalization + lock release")

    def issue_ephemeral_directive(
        self, moment_id: MomentId
    ) -> Result[EphemeralTeachingDirective]:
        raise NotImplementedError("P3-1B: Teaching Planner directive")
