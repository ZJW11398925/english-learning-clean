"""Startup recovery scan — old-epoch nonterminal work (Phase 1 P1A slice).

docs/RUNTIME_ARCHITECTURE.md:
- §22: recovery 扫描非 terminal 记录；只恢复未完成 action/projection，不重跑
  整个 user turn。
- §23 / §23 "Crash after CP0": 从 analysis 继续 — 已提交的 UserTurn 不重放。
- §24 "Crash recovery": Local V1 不以 expiry 猜 owner 已死，而由新的
  runtime_epoch 对旧 epoch nonterminal work 做 startup/opportunistic
  recovery。
- §24.1 disposition vocabulary:
    CP0 → RESUME_ANALYSIS
    CP1 → RESUME_DECISION
    CP2 → RESUME_ACTION_BY_STABLE_ACTION_ID
    CP3 uncertain → CONSERVATIVE_DELIVERY_RECONCILIATION

P1A scope (TASK-OPI-091f35c3.11 deliverable ③): *identify* recoverable
TurnRecords only. The scan is a pure durable read — invoking it twice yields
the same plan, and committed UserTurns are never re-created. The read
itself is executed by the durable conversation store (Gate item 2 keeps
this package SQL-free) behind :class:`TurnRecordRecoverySource`.

P3-2 carry-over (DEC-OPI-5ba74efc-….20 ①): the scan also *names* the
TeachingLockLease residue of a dead runtime epoch. Before this, an orphan
teaching lock was only reachable through an explicit
``ConversationCoordinator.recover_orphan_teaching()`` call that no startup
path made, so a conversation whose teaching process died stayed sealed
until something happened to call the apply face. The scanner now reports
one :data:`TEACHING_LOCK_RECOVERY_ACTION` item per orphan lock (kind
``LOCK``, id = the moment id) through the optional
:class:`TeachingLockRecoverySource` port — the same pure-read bargain as
the TurnRecord list (STARTS nothing, writes nothing; the apply face is the
coordinator's), so the plan and the sweep can never disagree about which
lock is residue. A lock owned by the *current* epoch is a real
mutual-exclusion fact and is deliberately not part of the plan
(STATE_MACHINES §9/§24.1: epoch-based liveness, never TTL/heartbeat).

P3-3 review F6 (DEC-OPI-5ba74efc-….43): the plan now has a startup *entry*
— ``ConversationCoordinator.run_startup_recovery`` builds this scanner from
its own injected ports, scans once, and then applies what a new epoch may
apply (the lock sweep, plus the turn-level reconciliation of the delivery
residue that sweep just unsealed). This module stays the read half; the
coordinator stays the only writer.

P4-2 (DEC-OPI-5ba74efc-….96 F1): the same read-half bargain covers one more
startup read — the refs↔proposal reconciliation. §17's
``AttemptEvaluationRecord.evidence_proposal_refs`` names the durable
learning-side proposal an evaluation produced; a ref whose proposal row does
not exist is a durable trace pointing nowhere (the P4-0 ① durable-pending
chain removed the *write* hazard, and this scan names the residue a crash
between the two writes would have left). The read is
:class:`TeachingEvidenceRefSource` — the teaching side names what it
recorded, and the existence check itself runs on the coordinator over
Learning's own authority face (the teaching package may not import
``elc.learning``), never by re-deriving a ref string here.

P10-0 (TASK-OPI-9dba34fb-….35) adds the four §11 scan surfaces that had no
read face. IP §11 sweeps seven residue classes; three were already wired
(non-terminal TurnRecord, TeachingLockLease, and the CP4 projections the
coordinator owns) and four were not — an old-epoch GenerationActionIntent
had a store read no startup path ever called, and TeachingMoment / pending
AnalysisArtifact / ServerDeliveryRecord had no status scan at all. The four
reads below follow the same pure-read bargain as the two above (one port per
class, ``None`` when an assembly does not inject it, no writes, ids in
durable order), and the plan order becomes

    TURN → ACTION → MOMENT → ANALYSIS → DELIVERY → LOCK

(the existing TURN→LOCK relative order is preserved). R5: this cut only
*classifies* — no apply face moves and ``run_startup_recovery`` is
byte-unchanged; a kind no line consumes yet says so in its own docstring.

P10-0 disposition → executor table (R5: this table records who performs each
§24.1 word *today*, not who should). Anchors are p10-0 line anchors — the
method names are the stable part.

    word: RESUME_ANALYSIS
      executor: 入口重入 (entry re-entry) — ``begin_turn`` →
      ``_begin_turn_guarded``
      where: controller.py:1424-1441 (USER_COMMITTED → ANALYZING, then the
      analysis leg replays idempotently; §23 "Crash after CP0: 从 analysis
      继续")

    word: RESUME_DECISION
      executor: 入口重入 (entry re-entry) — the *teaching* entries, because
      the CP1 slot the word names is a teaching turn (``DECIDING``):
      ``request_teaching`` / ``respond_to_teaching``
      where: controller.py:3878-3885 and :5303-5310 (replay/repair of the
      frozen cycle); ``begin_turn`` refuses such a turn instead
      (controller.py:1394-1400 for a command payload, :1461-1465 for the
      status)

    word: RESUME_ACTION_BY_STABLE_ACTION_ID
      executor: 入口重入 (entry re-entry) — ``begin_turn``'s claim branch
      where: controller.py:1549-1560 (``claim_action_for_recovery`` at
      :1553; the action is re-armed at ``REQUESTED`` under the current epoch,
      same stable action_id)

    word: CONSERVATIVE_DELIVERY_RECONCILIATION
      executor: startup 线 — ``run_startup_recovery`` →
      ``reconcile_delivering_residue`` (controller.py:4359, via
      ``_reconcile_delivering_turn`` at :2307) + ``_close_residual_turns``
      (:4276)
      where: the same word is also reachable on entry — the ``DELIVERING``
      branch of ``begin_turn`` (controller.py:1402-1417)

    word: RELEASE_ORPHAN_TEACHING_LOCK
      executor: startup 线 — ``run_startup_recovery`` →
      ``recover_orphan_teaching`` (controller.py:3922; called at :4048)

    word: CLOSE_ORPHAN_MOMENT
      executor: 无 (this cut classifies only; no apply face reads the word)
      Revisit: the cut that adds an apply face for a moment with no lock and
      no turn left to resume

P10-0 status adjudication table — the four STATE_MACHINES §10 words no writer
produces today (a whole-repo read, p10-0):

    word: RECEIVED
      writer: 无 (kept in the §10 vocabulary; ``recovery_disposition`` maps
      it to ``RESUME_ANALYSIS``, the CP0 slot)
      Revisit: a writer appears

    word: DELIVERY_TERMINAL
      writer: 无
      Revisit: a writer appears

    word: POSTPROCESSING
      writer: 无
      Revisit: a writer appears

    word: FAILED_RECOVERABLE
      writer: 无, and no entry accepts it either — the ``begin_turn``
      re-entry takes USER_COMMITTED / ANALYZING / GENERATING and the
      teaching entries take USER_COMMITTED / DECIDING / GENERATING — so
      the ``recovery_disposition`` mapping to ``RESUME_ANALYSIS`` is kept
      but is unreachable today
      Revisit: a writer appears, or an entry accepts the word

P10-0 lease projection (D): ``ConversationCoordinatorLease`` has no durable
row in Local V1 (:mod:`elc.runtime.lease`), so there is no lease table to
scan and none is added (R7 — every read here is existing tables + JOINs).
Its sweep surface is the three ``owner_epoch`` projections that stand in for
it: ``turn_record`` (kind TURN), ``generation_action_intent`` (kind ACTION)
and ``active_teaching_lock`` reached through ``teaching_moment`` →
``decision_cycle`` → ``turn_record`` (kinds MOMENT and LOCK). That is why
every criterion below is stated on a *turn's* epoch, never on a lease.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
    RuntimeEpoch,
)
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    RecoveryAction,
    TurnRecordData,
    TurnStatus,
)

__all__ = [
    "MOMENT_RECOVERY_ACTION",
    "RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY",
    "RECOVERY_DISPOSITION_RESUME_ACTION",
    "RECOVERY_DISPOSITION_RESUME_ANALYSIS",
    "RECOVERY_DISPOSITION_RESUME_DECISION",
    "RECOVERY_KIND_ACTION",
    "RECOVERY_KIND_ANALYSIS",
    "RECOVERY_KIND_DELIVERY",
    "RECOVERY_KIND_LOCK",
    "RECOVERY_KIND_MOMENT",
    "RECOVERY_KIND_TURN",
    "TEACHING_LOCK_RECOVERY_ACTION",
    "AnalysisArtifactRecoverySource",
    "DanglingEvidenceRef",
    "DeliveryRecordRecoverySource",
    "GenerationActionRecoverySource",
    "StartupRecoveryScanner",
    "TeachingEvidenceRefSource",
    "TeachingLockRecoverySource",
    "TeachingMomentRecoverySource",
    "TurnRecordRecoverySource",
    "recovery_disposition",
]

#: The plan-item kinds the scan produces (``RecoveryAction.kind``):
#: ``TURN`` names one old-epoch nonterminal TurnRecord; ``LOCK`` names one
#: orphan TeachingLockLease; ``ACTION`` / ``MOMENT`` / ``ANALYSIS`` /
#: ``DELIVERY`` (P10-0) name the §11 residue classes that had no read face —
#: a nonterminal GenerationActionIntent, a nonterminal TeachingMoment, a
#: pending AnalysisArtifact, and an unterminated ServerDeliveryRecord. Named
#: here because the *apply* face
#: (``ConversationCoordinator.run_startup_recovery``) reads the same
#: vocabulary the scan writes — one definition, two faces.
RECOVERY_KIND_TURN = "TURN"
RECOVERY_KIND_LOCK = "LOCK"
RECOVERY_KIND_ACTION = "ACTION"
RECOVERY_KIND_MOMENT = "MOMENT"
RECOVERY_KIND_ANALYSIS = "ANALYSIS"
RECOVERY_KIND_DELIVERY = "DELIVERY"

#: The recovery action word of the TeachingMoment scan (P10-0). This repo's
#: registered word for "close a moment a dead epoch left nonterminal", on the
#: :data:`TEACHING_LOCK_RECOVERY_ACTION` precedent: §24.1 names dispositions
#: per checkpoint, not per record class, so the word is registered here and
#: its executor is disclosed in the module docstring's executor table (today:
#: none — this cut classifies only).
MOMENT_RECOVERY_ACTION = "CLOSE_ORPHAN_MOMENT"

#: §24.1's four disposition words, named once so :func:`recovery_disposition`
#: and the P10-0 kind items cannot drift (R1's kind → word table: ACTION →
#: RESUME_ACTION_BY_STABLE_ACTION_ID, ANALYSIS → RESUME_ANALYSIS, DELIVERY →
#: CONSERVATIVE_DELIVERY_RECONCILIATION; MOMENT's word is
#: :data:`MOMENT_RECOVERY_ACTION` above).
RECOVERY_DISPOSITION_RESUME_ANALYSIS = "RESUME_ANALYSIS"
RECOVERY_DISPOSITION_RESUME_DECISION = "RESUME_DECISION"
RECOVERY_DISPOSITION_RESUME_ACTION = "RESUME_ACTION_BY_STABLE_ACTION_ID"
RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY = (
    "CONSERVATIVE_DELIVERY_RECONCILIATION"
)

#: The recovery action word of the TeachingLockLease sweep (P3-2 carry-over
#: ①): the orphan lock named by the scan is released — and with it its
#: moment closed with ``SYSTEM_RECOVERY_ABORT`` — by
#: ``ConversationCoordinator.recover_orphan_teaching`` (STATE_MACHINES §9).
TEACHING_LOCK_RECOVERY_ACTION = "RELEASE_ORPHAN_TEACHING_LOCK"


@runtime_checkable
class TurnRecordRecoverySource(Protocol):
    """Durable read face for the recovery scan (implemented by the
    conversation store; RUNTIME §22 scans nonterminal records)."""

    def recoverable_turn_records(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[TurnRecordData, ...]:
        ...


@runtime_checkable
class TeachingLockRecoverySource(Protocol):
    """Durable read face for the teaching-lock scan (implemented by the
    Teaching domain store / its controller face — the runtime package
    stays SQL-free, Gate item 2).

    Returns the moment ids whose ``active_teaching_lock`` row is owned by
    a turn of an *older* runtime epoch: residue of a dead process, never a
    live mutual-exclusion fact (STATE_MACHINES §9 "startup recovery 通过
    durable Moment state + runtime_epoch revalidate/release orphan lock";
    §24.1: no TTL/heartbeat in Local V1).
    """

    def orphan_teaching_lock_moments(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        ...


@runtime_checkable
class GenerationActionRecoverySource(Protocol):
    """Durable read face for the old-epoch GenerationActionIntent scan
    (IP §11's ``GenerationActionIntent`` class; RUNTIME §22).

    Implemented by the generation store's read face — the runtime package
    stays SQL-free, Gate item 2. Returns action ids in durable order.

    **What it scans**: ``generation_action_intent`` rows a dead epoch left
    mid-flight. **Residue criterion**: ``owner_epoch != current`` AND
    ``status != 'TERMINAL'`` — an action the old process was still driving
    (PREPARED…DELIVERING) when that epoch ended. **Executor**: 入口重入 —
    ``ConversationCoordinator.begin_turn``'s claim branch re-arms exactly
    such an action under the new epoch (same stable action_id, §23), and the
    module docstring's executor table gives the anchor. **Not scanning it**:
    the row is invisible to the startup plan, so nothing names the work a
    crash left half-dispatched; the only path that ever picks it up is the
    user re-sending the same client_message_id.
    """

    def orphan_generation_actions(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        ...


@runtime_checkable
class TeachingMomentRecoverySource(Protocol):
    """Durable read face for the old-epoch TeachingMoment scan (IP §11's
    ``TeachingMoment`` class; STATE_MACHINES §1).

    Implemented by the Teaching domain store (its controller face is the
    injection point when a wiring cut lands) — the runtime package stays
    SQL-free, Gate item 2. Returns moment ids in durable order.

    **What it scans**: ``teaching_moment`` rows still walking the §1
    lifecycle whose owning turn belongs to a dead epoch, reached through
    ``teaching_moment`` → ``decision_cycle`` → ``turn_record``.
    **Residue criterion**: ``lifecycle_state`` NOT IN
    (``TEACHING_TERMINAL``, ``CLOSED``) AND that turn's
    ``owner_epoch != current``. The criterion is stated on the *moment*, not
    on the lock: a moment whose lock is already gone (released by the sweep,
    or never re-taken) is exactly the residue no earlier kind named — the
    LOCK kind only sees moments that still *hold* a lock. A moment that does
    still hold one is named by both kinds on purpose (two facts, two apply
    faces). **Executor**: 无 for the lock-free shape — this cut classifies,
    it does not apply (R5), and the registered word
    :data:`MOMENT_RECOVERY_ACTION` has no reader today; the lock-holding
    subset is settled by the LOCK word's sweep. **Not scanning it**: such a
    moment can stay nonterminal forever with nothing naming it (the sweep
    only sees locks; ``_close_residual_turns`` only walks TURN items and
    only for moments already CLOSED).
    """

    def orphan_moment_ids(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        ...


@runtime_checkable
class AnalysisArtifactRecoverySource(Protocol):
    """Durable read face for the pending AnalysisArtifact scan (IP §11's
    ``pending AnalysisArtifact`` class; RUNTIME §22/§23).

    Implemented by the Learning domain store — the runtime package stays
    SQL-free, Gate item 2. Returns analysis ids in durable order.

    **What it scans**: ``analysis_artifact`` rows a crash left pending
    (``PRODUCED`` / ``COMMIT_PENDING``), reached through the artifact's
    ``turn_id`` → ``turn_record``. **Residue criterion**: ``status IN
    ('PRODUCED', 'COMMIT_PENDING')`` AND the turn's ``owner_epoch !=
    current``. ``COMMITTED`` / ``REJECTED`` / ``SUPERSEDED`` are over — they
    are never residue, and a *current*-epoch row is live work, not residue.
    **Executor**: 入口重入 — the turn's own re-entry replays the leg
    idempotently under deterministic analysis keys (§23 "Crash after CP0: 从
    analysis 继续"; executor table). **Not scanning it**: the pending row is
    never named as old-epoch work, so a plan cannot say which analysis an
    interrupted epoch left behind; the leg only runs again if the turn is
    re-entered.
    """

    def pending_analysis_artifacts(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        ...


@runtime_checkable
class DeliveryRecordRecoverySource(Protocol):
    """Durable read face for the unterminated ServerDeliveryRecord scan
    (RUNTIME §22's recovery list; DATA_MODEL §22 Delivery Data).

    Implemented by the delivery-record store — the runtime package stays
    SQL-free, Gate item 2. Returns *action* ids in durable order (the §22
    row is keyed by ``action_id``).

    **What it scans**: ``server_delivery_record`` rows whose send never
    reached a terminal instant, joined to the action that owns them.
    **Residue criterion**: ``terminal_at IS NULL`` AND the action's
    ``owner_epoch != current`` — the record a crash left frozen mid-send.
    **Executor**: the §24.1 word is ``CONSERVATIVE_DELIVERY_RECONCILIATION``
    and its executor is the startup line / the DELIVERING entry branch (see
    the executor table) — but note the fact this cut records: that executor
    walks **TURN** items today, so a DELIVERY item is named here and consumed
    by no line yet (R5: no apply face moves). **Not scanning it**: an
    unterminated send is not named at all, and the CP3-uncertain posture
    (never blindly resend) has no read that lists the records it applies to.
    """

    def unterminal_delivery_records(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        ...


@dataclass(frozen=True)
class DanglingEvidenceRef:
    """One §17 ``evidence_proposal_refs`` entry whose durable proposal row
    does not exist (P4-2, DEC-OPI-5ba74efc-….96 F1).

    ``evaluation_id`` is the AttemptEvaluationRecord that recorded the ref
    and ``ref`` is the ref text exactly as the row carries it — never
    re-derived, never normalized: the point of the scan is to report the
    durable trace as it stands.
    """

    evaluation_id: str
    ref: str


@runtime_checkable
class TeachingEvidenceRefSource(Protocol):
    """Durable read face for the refs↔proposal reconciliation (implemented
    by the teaching store / its controller face — the runtime package stays
    SQL-free, Gate item 2).

    Returns ``(attempt_evaluation_id, evidence_proposal_refs)`` per durable
    evaluation row, in deterministic order. The face only *names* what the
    teaching side recorded; resolving each ref against Learning's proposal
    table is the coordinator's job (the two packages never import each
    other — BF-05's allow/deny lists, and the P4-G1 AST pin).
    """

    def evidence_proposal_refs(
        self,
    ) -> Result[tuple[tuple[str, tuple[str, ...]], ...]]:
        ...


def recovery_disposition(status: TurnStatus) -> str:
    """RUNTIME_ARCHITECTURE §24.1 checkpoint → disposition mapping.

    P1A only ever produces CP0-committed turns (USER_COMMITTED); the other
    mappings exist so the scan speaks the full §24.1 vocabulary as soon as
    later phases advance TurnRecords past CP0.

    Review F3 (DEC-…5ba74efc.43, P3-3 carry-over): ``DELIVERING`` is the
    CP3-uncertain slot — the action was dispatched and the process died
    before the delivery leg was canonicalized, which is exactly §24.1's
    "CP3 uncertain → CONSERVATIVE_DELIVERY_RECONCILIATION" (RA §23: "若
    delivery uncertain，保守 canonicalize，不盲目重放"). The P1A
    placeholder mapped it together with ``GENERATING`` onto
    ``RESUME_ACTION_BY_STABLE_ACTION_ID``; that is the CP2 rule (the
    action is stable and still undelivered) and it is what the coordinator
    does for a ``GENERATING`` turn. A ``DELIVERING`` turn gets the
    conservative reconciliation instead: the durable transcript decides
    whether the message went out, and the leg is completed from that
    record — never re-dispatched onto a user who may already have seen it.
    """
    if status in TERMINAL_TURN_STATUSES:
        raise ValueError(f"terminal status {status} is not recoverable work")
    if status in (
        TurnStatus.RECEIVED,
        TurnStatus.USER_COMMITTED,
        TurnStatus.ANALYZING,
        TurnStatus.FAILED_RECOVERABLE,
    ):
        # CP0 committed → resume at analysis (§23)
        return RECOVERY_DISPOSITION_RESUME_ANALYSIS
    if status == TurnStatus.DECIDING:
        return RECOVERY_DISPOSITION_RESUME_DECISION  # CP1 done
    if status == TurnStatus.GENERATING:
        return RECOVERY_DISPOSITION_RESUME_ACTION  # CP2 done
    # CP3 uncertain
    return RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY


class StartupRecoveryScanner:
    """Identify old-epoch nonterminal work as recovery work.

    The scan never rewrites anything: repeated ``scan()`` calls are
    idempotent, and already-committed CP0 UserTurns are only *referenced*,
    never replayed (§22; VAL ④).

    P3-2 carry-over ①: with a ``teaching_locks`` source the plan also names
    one ``LOCK`` item per orphan TeachingLockLease (see the module
    docstring). The teaching source is optional so every P1/P2 assembly
    keeps the exact plan shape its tests pin.

    P10-0 adds four more optional sources — ``generation_actions`` /
    ``teaching_moments`` / ``analysis_artifacts`` / ``delivery_records`` —
    each contributing one plan item per residue id it returns (kinds
    ACTION / MOMENT / ANALYSIS / DELIVERY). Every one of them defaults to
    ``None``, and a missing source contributes no item, so the plan shape an
    assembly without them sees is exactly the pre-P10-0 one.
    """

    def __init__(
        self,
        source: TurnRecordRecoverySource,
        lease: ConversationCoordinatorLease,
        teaching_locks: TeachingLockRecoverySource | None = None,
        generation_actions: GenerationActionRecoverySource | None = None,
        teaching_moments: TeachingMomentRecoverySource | None = None,
        analysis_artifacts: AnalysisArtifactRecoverySource | None = None,
        delivery_records: DeliveryRecordRecoverySource | None = None,
    ) -> None:
        self._source = source
        self._lease = lease
        self._teaching_locks = teaching_locks
        self._generation_actions = generation_actions
        self._teaching_moments = teaching_moments
        self._analysis_artifacts = analysis_artifacts
        self._delivery_records = delivery_records

    def scan(self) -> Result[tuple[RecoveryAction, ...]]:
        """Return the recovery plan for old-epoch nonterminal work.

        The item order is the plan's identity, and P10-0 pins it as

            TURN → ACTION → MOMENT → ANALYSIS → DELIVERY → LOCK

        (the pre-P10-0 TURN → LOCK relative order is preserved; LOCK stays
        last because it is the sweep's own list). Each source contributes its
        items in its own durable ``ORDER BY``, so two scans of one durable
        state return the same plan.
        """
        epoch = self._lease.epoch
        if epoch is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "startup fence not opened — adopt a runtime_epoch"
                        " first"
                    ),
                )
            )
        records = self._source.recoverable_turn_records(epoch)
        actions = [
            RecoveryAction(
                kind=RECOVERY_KIND_TURN,
                id=record.turn_id,
                action=recovery_disposition(record.status),
            )
            for record in records
            if record.status not in TERMINAL_TURN_STATUSES
        ]
        actions.extend(self._action_items(epoch))
        actions.extend(self._moment_items(epoch))
        actions.extend(self._analysis_items(epoch))
        actions.extend(self._delivery_items(epoch))
        actions.extend(self._lock_items(epoch))
        return Ok(tuple(actions))

    # -- one item list per optional kind (P10-0) ---------------------------

    def _action_items(self, epoch: RuntimeEpoch) -> tuple[RecoveryAction, ...]:
        """One ACTION item per old-epoch nonterminal GenerationActionIntent
        (:class:`GenerationActionRecoverySource`)."""

        source = self._generation_actions
        if source is None:
            return ()
        return tuple(
            RecoveryAction(
                kind=RECOVERY_KIND_ACTION,
                id=action_id,
                action=RECOVERY_DISPOSITION_RESUME_ACTION,
            )
            for action_id in source.orphan_generation_actions(epoch)
        )

    def _moment_items(self, epoch: RuntimeEpoch) -> tuple[RecoveryAction, ...]:
        """One MOMENT item per old-epoch nonterminal TeachingMoment
        (:class:`TeachingMomentRecoverySource`)."""

        source = self._teaching_moments
        if source is None:
            return ()
        return tuple(
            RecoveryAction(
                kind=RECOVERY_KIND_MOMENT,
                id=moment_id,
                action=MOMENT_RECOVERY_ACTION,
            )
            for moment_id in source.orphan_moment_ids(epoch)
        )

    def _analysis_items(
        self, epoch: RuntimeEpoch
    ) -> tuple[RecoveryAction, ...]:
        """One ANALYSIS item per pending old-epoch AnalysisArtifact
        (:class:`AnalysisArtifactRecoverySource`)."""

        source = self._analysis_artifacts
        if source is None:
            return ()
        return tuple(
            RecoveryAction(
                kind=RECOVERY_KIND_ANALYSIS,
                id=analysis_id,
                action=RECOVERY_DISPOSITION_RESUME_ANALYSIS,
            )
            for analysis_id in source.pending_analysis_artifacts(epoch)
        )

    def _delivery_items(
        self, epoch: RuntimeEpoch
    ) -> tuple[RecoveryAction, ...]:
        """One DELIVERY item per unterminated old-epoch ServerDeliveryRecord
        (:class:`DeliveryRecordRecoverySource`)."""

        source = self._delivery_records
        if source is None:
            return ()
        return tuple(
            RecoveryAction(
                kind=RECOVERY_KIND_DELIVERY,
                id=action_id,
                action=RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY,
            )
            for action_id in source.unterminal_delivery_records(epoch)
        )

    def _lock_items(self, epoch: RuntimeEpoch) -> tuple[RecoveryAction, ...]:
        """One LOCK item per orphan TeachingLockLease — the pre-P10-0 kind,
        last in the plan (deterministic order: turn work, then the new §11
        residue, then the lock residue the sweep may unseal)."""

        source = self._teaching_locks
        if source is None:
            return ()
        return tuple(
            RecoveryAction(
                kind=RECOVERY_KIND_LOCK,
                id=moment_id,
                action=TEACHING_LOCK_RECOVERY_ACTION,
            )
            for moment_id in source.orphan_teaching_lock_moments(epoch)
        )
