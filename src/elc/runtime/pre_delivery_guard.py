"""PreDeliveryGuard — the seven hard-invalidation facts and their verdict (P9-3).

docs/RUNTIME_ARCHITECTURE.md §15 places the guard between the Response
Validator and the Delivery Manager (RA §4 steps 13 → 14 → 15) and states what
it is for, in one sentence: "只检查 hard invalidation … 不重新跑 Planner
utility". docs/STATE_MACHINES.md §16 repeats the shape of the answer — "只做
hard invalidation … 不重新打分、不 replan" — and pins the output vocabulary, and
§21.1 spells the durable row that carries it::

    decision
      VALID
      INVALIDATE_ACTION

This module is the guard's pure half: the seven facts §15 lists, the verdict
they add up to, and the reason-code vocabulary. It reads nothing, stores
nothing and knows no instant — it imports no sqlite3 and no ``elc.platform.db``,
calls no ``execute``-family method, carries no statement text and calls no
clock. The durable row (§21.1 ``PreDeliveryGuardResult``) is written by the
delivery face that owns the check, through the p9-1 port
(``elc.runtime.delivery_records`` → ``elc.platform.db.delivery_store``), and
every fact arrives from a read face the caller already holds — the same
"authority is a port, SQL is the platform layer" split every runtime module
follows (RA §16's position line, repeated by ``state_machines §16``).

---------------------------------------------------------------------------
**Declared readings.** Each entry is this cut's reading rather than a
quotation, and each names the condition that re-opens it.
---------------------------------------------------------------------------

1. **Seven facts, and every one of them is ``bool | None``.** §15 and
   ``state_machines §16`` list the same seven conditions in slightly different
   words; :class:`GuardCondition` takes §15's seven as the names (its order is
   the reading order below) and :class:`PreDeliveryGuardFacts` carries one
   field per condition, spelled as the lower-cased condition name. ``None``
   means **the check could not run** — no carrier, no authority, an
   unanswerable read — and it is deliberately *not* ``False``: §15 makes the
   guard the gate that can stop a delivery, so "I did not look" must not be
   spelled the same way as "I looked and it was fine". Revisit: canonical
   gives the facts a tri-state of its own, or a fact gains a carrier that can
   never be absent (then that field's ``None`` becomes unreachable and the
   field narrows).
2. **An unchecked condition is recorded, never silent — and it never
   invalidates.** §15 does not say what to do with a fact nobody could read;
   this cut answers "record it and do not invalidate": the reason codes carry
   ``UNCHECKED_<condition>`` and
   :attr:`PreDeliveryGuardVerdict.unchecked_conditions` names them, so a
   reader of the durable row can tell a clean ``VALID`` from an under-covered
   one. Invalidation on an unread fact would block deliveries on a missing
   authority, which is a different failure with a different owner (the wiring
   that did not hand the face over); silence would hide it. Revisit: canonical
   declares the fail-closed direction for a missing authorization read, or a
   cut wires the carrier everywhere (then the codes stop appearing).

   **Adjudicated (P10-3; Phase 10 opening DEC R6) — fail-open is the ruling,
   and it is a reading, not canonical text.** What was half-registered above
   is now decided: **a fact nobody could read never invalidates.** The verdict
   stays ``VALID``, its codes spell ``UNCHECKED_<condition>`` for every unread
   fact, and the under-covered check stays observable in the §21.1 row — a
   reader can always tell "clean" from "not looked at". Three reasons, the
   first two being canonical's own shape rather than this cut's preference:

   (a) §15's seven hard-invalidation conditions are a **封闭列表** (a closed
       list), and the guard's whole mandate is one sentence — "只检查 hard
       invalidation … 不重新跑 Planner utility". None of the seven is "the
       read failed", so invalidating on an unread fact would be an **eighth
       condition**: invented here, and true of no member of the list.
   (b) the decision vocabulary is exactly **two words** — ``VALID`` /
       ``INVALIDATE_ACTION`` (``state_machines §16``, repeated inline by
       ``DATA_MODEL §21.1``) — and migration 0018 carries them as a CHECK
       (``CHECK (decision IN ('VALID', 'INVALIDATE_ACTION'))``). There is
       **no DEGRADED here**, and the contrast with the Gate is about a
       **separate status column** rather than a shared word: the Gate carries
       its "critical fact unknown" case in ``GateExecutionStatus = DEGRADED``
       with ``GateDecision = null`` — "不得伪造 DENY" (`RA §24.2`;
       ``DATA_MODEL §14.1``'s ``status`` block; §21's Gate subsection says only
       "no automatic teaching / normal persona") — while its *decision* stays
       the two words ``ALLOW`` / ``DENY``. The guard's §21.1 row has **no such
       column**: its whole vocabulary is the two decision words, so a third
       answer is neither spellable nor storable here, and an unread fact must
       not borrow ``INVALIDATE_ACTION``'s. (Disposition F1, P10-3: an earlier
       sentence of this ruling attributed ``DEGRADED`` to "the Gate's RA §21
       verdict"; that is not what canonical says, and it has been corrected
       here.)
   (c) the two places canonical does speak about uncertainty send it
       elsewhere: §16's retry model and §17's partial delivery put
       "uncertain" on the conservative-canonicalization side (never a
       whole-turn retry, no automatic replay), and §17.1 rule 3 hands
       cancel / supersede / terminalize to the current lease holder or the
       recovery owner. A missing authorization read is a wiring fact whose
       owner is the assembly that did not hand the face over — a different
       failure with a different owner, recorded rather than converted into a
       delivery decision.

   **Reopen conditions (this adjudication).** (1) canonical adds an eighth
   hard-invalidation condition to §15, or adds a word like ``DEGRADED`` /
   ``UNVERIFIED`` to the decision vocabulary — then migration 0018's CHECK
   moves with it and this ruling is re-taken. (2) A real client lands and
   "cannot verify ⇒ do not deliver" becomes the required conservative
   direction (today the only client boundary is the in-process one, and the
   conservative direction for an unread fact is to keep the delivery
   *observable*, not to block it on an absence of information).
3. **The decision vocabulary is §21.1's two words.** ``VALID`` /
   ``INVALIDATE_ACTION`` and no third word. A cancelled or superseded
   delivery's own word is expressed where it belongs — the §22 row's §13
   ``state`` (``CANCELLED``) and the turn outcome (``CANCELLED_BY_USER``) —
   never here, because §21.1's column is a CHECK in the schema (migration
   0018) and a third word could not be stored anyway. Revisit: canonical adds
   a guard decision word (then migration 0018's CHECK moves with it).
4. **The reason codes are the condition names plus their unchecked prefix.**
   §21.1's ``reason_codes[]`` is a free list; §15's seven condition names are
   already the reason a reader needs, so this cut mints no second vocabulary:
   the code for an invalidating fact **is** its condition name, and the code
   for an unread one is that name behind :data:`UNCHECKED_PREFIX`. A reader
   therefore never has to learn a mapping table, and a new condition cannot
   arrive without its codes. Revisit: canonical (or a later cut's incident
   review) needs a finer reason than "this condition was true" — then a code
   table with a version is the honest shape and this reading retires.
5. **The lineage version is a spelling, and it is a spelling of two durable
   facts.** ``checked_lineage_version`` (§21.1) records which lineage the check
   ran against. The lineage of one delivery is the action's DecisionCycle
   (``generation_action_intent.decision_cycle_id``, the §4 "cycle lineage"
   migration 0007 pinned) and the turn's ``state_version`` — the CAS counter
   every coordination move advances (``state_machines §20``) — so
   :func:`checked_lineage_version_of` spells it as ``<cycle>@<state_version>``
   and ``no-cycle`` for an action that carries none. It is a **reading**, not
   canonical text: §21.1 names the column and no format. Revisit: canonical
   pins a format for the column, or a second lineage authority appears (then
   the version has to name it too).
6. **The facts are read at one instant and judged once.** §15's check is a
   point-in-time gate, not a subscription: a fact that changes after the
   verdict changes nothing about this delivery. That is what makes the
   sequence "read seven facts → one verdict → write one row" replayable
   (R-INV-012's stable identity: the same facts give the same row), and it is
   why the caller — not this module — holds the clock that stamps
   ``created_at``. Revisit: a cut needs the guard to re-read a fact after the
   write (then the verdict is not one value any more and this reading is the
   one to re-open).
7. **The guard is on both delivery faces.** RA §13 puts ordinary persona chat
   on ``GUARDED_STREAM`` and every teaching action on ``BUFFERED_VALIDATED``;
   P9-3 landed the guard on the streamed path (before the first release), and
   its disposition (review MEDIUM-1) wired the **buffered teaching delivery
   leg** too — at the one dispatch site every teaching delivery passes through
   (``ConversationCoordinator._deliver_teaching_action``: the user-initiated
   opening, a continuation, the resume and the automatic opening) — so the two
   faces share this verdict and only the caller differs. That wiring is what
   made §15's three teaching legs (lock / target suppression / JUST_CHAT)
   reachable at all: before it, no teaching delivery ever asked the guard. A
   guard-invalidated buffered teaching delivery is not sent: its action
   terminalizes undelivered, no ``assistant_turn`` row is written, and the
   turn takes §1-C③'s two-word mapping through the same helper the streamed
   face reads (``elc.runtime.controller._guard_invalidation_outcome``).
   Revisit: canonical gives the guard a third face, or a per-face rule set.

---------------------------------------------------------------------------
**The seven facts and their V1 carriers** (the assembly that fills them lives
in ``elc.runtime.controller``, the one place holding every read they need).
Registered here so the module and its caller cannot drift about *what* each
condition means:

================================  ==========================================
condition                         V1 carrier
================================  ==========================================
``CONVERSATION_INACTIVE``         the conversation row's status
``ACTION_CANCELLED``              a pending ``interrupt_request`` naming this
                                  action while the action is nonterminal
``ACTION_SUPERSEDED``             the action's turn is not the conversation's
                                  latest ``turn_sequence``
``TEACHING_LOCK_INVALID``         a teaching action without an
                                  ``active_teaching_lock`` row, or a lock held
                                  by another moment — except the episode's own
                                  ``PERSONA_RESUME`` closing move, delivered
                                  after the terminal transition released the
                                  lock (SM §1), which answers ``False``
``NEW_TARGET_SUPPRESSED``         a ``SUPPRESS_REVIEW`` constraint in force for
                                  the action's target
``JUST_CHAT_HARD_SWITCH``         a ``JUST_CHAT`` constraint in force while a
                                  teaching action is delivering
``LINEAGE_MISMATCH``              the action's ``decision_cycle_id`` is not the
                                  lineage that binds it: an ordinary action's
                                  turn cycle, a teaching action's episode
                                  (moment) cycle
================================  ==========================================

Three of them are "not applicable" rather than "unknown" for an ordinary
persona reply (there is no TeachingLock question, no target and no teaching
content to suppress), and their carrier is ``False`` — a definite answer — not
``None``. That distinction is the whole reason the facts are tri-state.

One fact's comparison partner is face-dependent since P9-3's disposition:
``LINEAGE_MISMATCH`` compares an ordinary action's cycle against its host
turn's, and a teaching action's against its own episode's (the moment's
``decision_cycle_id`` — ``STATE_MACHINES §17``'s ACTIVE_MOMENT authorization
lineage). The host-turn comparison is wrong for a teaching continuation
because the reply turn opens its own DecisionCycle for the attempt it decided,
so the two would never match — a structural false alarm, not a stale action
(the calling assembly, ``elc.runtime.controller._pre_delivery_guard_facts``,
carries the full reading). Revisit: canonical pins one comparison for both
faces.

One carrier's answer is narrowed for the same reason: the lock condition is
read for a delivery that claims to be inside a live episode, and the episode's
``PERSONA_RESUME`` closing move is delivered after the moment terminalized and
released its lock (SM §1) — reading the released lock as "invalid" would
refuse every resume, so that one action answers ``False``. The reservation is
on the calling assembly's reading, not a fourth answer here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from elc.platform.types import ActionId, ConversationId, Result, TargetId
from elc.user_config.types import PlannerConstraint, PlannerConstraintView

__all__ = [
    "CONDITION_ATTRIBUTES",
    "UNCHECKED_PREFIX",
    "GuardCondition",
    "PlannerConstraintSource",
    "PreDeliveryDecision",
    "PreDeliveryGuardFacts",
    "PreDeliveryGuardVerdict",
    "checked_lineage_version_of",
    "guard_result_id_of",
    "guard_verdict",
    "unchecked_code_of",
]


class GuardCondition(StrEnum):
    """§15's seven hard-invalidation conditions, in the reading order.

    The declaration order is the order :data:`reason_codes
    <PreDeliveryGuardVerdict.reason_codes>` come out in, so two runs over the
    same facts produce the same tuple (R-INV-012) and a row diff reads as a
    sentence rather than a set.

    Registered (P9-3 disposition, review INFO-2): this is the *reading* order,
    not §15's listing order — canonical lists the cancellation / supersession
    pair in the other sequence, and the difference becomes visible in a row
    whose codes carry both. Registered rather than re-ordered: the tuple is
    read as reasons (never positionally against the document) and a stable
    order is what R-INV-012's replay needs. Revisit: a consumer diffs the
    tuple against §15's listing positionally.
    """

    CONVERSATION_INACTIVE = "CONVERSATION_INACTIVE"
    ACTION_CANCELLED = "ACTION_CANCELLED"
    ACTION_SUPERSEDED = "ACTION_SUPERSEDED"
    TEACHING_LOCK_INVALID = "TEACHING_LOCK_INVALID"
    NEW_TARGET_SUPPRESSED = "NEW_TARGET_SUPPRESSED"
    JUST_CHAT_HARD_SWITCH = "JUST_CHAT_HARD_SWITCH"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"


class PreDeliveryDecision(StrEnum):
    """§16's output vocabulary, repeated inline by §21.1 — the only two words.

    A third word is unspellable *and* unstorable: migration 0018's CHECK on
    ``pre_delivery_guard_result.decision`` carries exactly these two.
    """

    VALID = "VALID"
    INVALIDATE_ACTION = "INVALIDATE_ACTION"


#: The prefix an unread fact's code carries (reading 2). Spelled once: the
#: module's tests pin the seven codes it produces against
#: :class:`GuardCondition`'s members rather than against a second list.
UNCHECKED_PREFIX = "UNCHECKED_"


def unchecked_code_of(condition: GuardCondition) -> str:
    """The reason code of a condition that could not be checked."""

    return f"{UNCHECKED_PREFIX}{condition.value}"


#: condition → the attribute of :class:`PreDeliveryGuardFacts` holding it.
#: Derived from the two declarations (the field name **is** the lower-cased
#: condition name) so a condition cannot exist without its field or a field
#: without its condition.
CONDITION_ATTRIBUTES: dict[GuardCondition, str] = {
    condition: condition.value.lower() for condition in GuardCondition
}


@dataclass(frozen=True)
class PreDeliveryGuardFacts:
    """§15's seven facts as the caller read them — one field per condition.

    ``True`` = the condition holds (the delivery must be invalidated);
    ``False`` = it does not; ``None`` = the caller could not answer it (no
    carrier, no authority, an unanswerable read). Every field is required:
    §15's list is the fact set, so a caller that cannot read one says ``None``
    rather than omitting it (reading 1), and the dataclass is frozen so a
    verdict cannot be judged against facts that moved under it (reading 6).
    """

    conversation_inactive: bool | None
    action_cancelled: bool | None
    action_superseded: bool | None
    teaching_lock_invalid: bool | None
    new_target_suppressed: bool | None
    just_chat_hard_switch: bool | None
    lineage_mismatch: bool | None


@dataclass(frozen=True)
class PreDeliveryGuardVerdict:
    """What §15's check answered: the §21.1 ``decision``, its ``reason_codes``,
    and the facts they were judged from.

    The facts ride the verdict so the durable row's two columns always have
    their derivation beside them in a trace: the codes are the conditions that
    were ``True`` (their own name) or ``None``
    (:func:`unchecked_code_of`), in :class:`GuardCondition` order, and the
    verdict carries the two halves apart so a caller can ask each question
    without re-deriving it.
    """

    decision: str
    reason_codes: tuple[str, ...]
    facts: PreDeliveryGuardFacts

    @property
    def invalidating_conditions(self) -> tuple[str, ...]:
        """The conditions that were ``True``, in reading order (empty = VALID)."""

        return tuple(
            condition.value
            for condition in GuardCondition
            if getattr(self.facts, CONDITION_ATTRIBUTES[condition]) is True
        )

    @property
    def unchecked_conditions(self) -> tuple[str, ...]:
        """The conditions that could not be answered, in reading order."""

        return tuple(
            condition.value
            for condition in GuardCondition
            if getattr(self.facts, CONDITION_ATTRIBUTES[condition]) is None
        )


def guard_verdict(facts: PreDeliveryGuardFacts) -> PreDeliveryGuardVerdict:
    """§15's verdict for one read of the seven facts.

    The three-way rule, spelled out because it is the module's whole
    behaviour:

    - **any** fact ``True`` → ``INVALIDATE_ACTION``, with every such
      condition's name among the reason codes;
    - **no** fact ``True`` → ``VALID`` (whatever the ``False``/``None`` mix
      is), with ``UNCHECKED_<condition>`` for each ``None``;
    - ``None`` never invalidates: an unread fact is recorded, not guessed
      (reading 2, adjudicated in P10-3 — the fail-open ruling and its reopen
      conditions are spelled out there).

    The codes come out in :class:`GuardCondition` order — the invalidating
    names and the unchecked names interleaved by condition, not grouped — so
    the tuple is a function of the facts and nothing else (reading 6).
    """

    invalidating: list[str] = []
    codes: list[str] = []
    for condition in GuardCondition:
        answer = getattr(facts, CONDITION_ATTRIBUTES[condition])
        if answer is True:
            invalidating.append(condition.value)
            codes.append(condition.value)
        elif answer is None:
            codes.append(unchecked_code_of(condition))
    return PreDeliveryGuardVerdict(
        decision=(
            PreDeliveryDecision.INVALIDATE_ACTION.value
            if invalidating
            else PreDeliveryDecision.VALID.value
        ),
        reason_codes=tuple(codes),
        facts=facts,
    )


def checked_lineage_version_of(
    *, decision_cycle_id: str | None, turn_state_version: int
) -> str:
    """The §21.1 ``checked_lineage_version`` spelling for one delivery (reading 5).

    ``<decision_cycle_id>@<turn_state_version>``, or ``no-cycle@<version>``
    when the action carries no cycle (an assembly whose action predates the
    cycle binding, migration 0007's nullable lineage). The value is
    deterministic in the two arguments — the same delivery re-checked after a
    crash spells the same version, which is what makes the guard row's
    re-submission a replay rather than a conflict (the p9-1 store's judgement).
    """

    return f"{decision_cycle_id or 'no-cycle'}@{turn_state_version}"


def guard_result_id_of(action_id: ActionId) -> str:
    """The §21.1 row id of one action's guard check — one row per action.

    §21.1's ``pre_delivery_guard_result_id`` carries an id and no attempt
    column, and §15's check is one decision about one delivery, so the action
    is the identity: a re-check of the same action (the §23 crash window, where
    the guard runs again on re-entry) re-submits the **same** id, which the
    p9-1 store answers as a replay when the facts did not move and as a
    conflict when they did — never as a silent second row (R-INV-012). Revisit:
    canonical gives the row an attempt/generation column (then the id has to
    carry it too).
    """

    return f"pdg-{action_id}"


@runtime_checkable
class PlannerConstraintSource(Protocol):
    """The two §9 reads this module's constraint legs consume — and nothing else.

    §15's ``new target suppression`` and ``JUST_CHAT hard switch`` are
    questions about the user's own durable constraints, so the authority is
    ``elc.user_config``: ``get_planner_constraint_view`` is the view the
    Planner's scope reader uses (with the session binding §9 has no column
    for), and ``active_constraints_for_target`` is the target-filtered read
    P6-3 landed. ``UserConfigController`` satisfies both unchanged.

    It is declared **here**, beside the facts that need it, rather than in the
    caller: the guard names the authority it asks, and a wiring that hands over
    a face answering neither read fails the protocol check at construction
    instead of at the first delivery. A caller with no such face passes
    ``None`` — which the facts spell ``None`` (unchecked), never ``False``
    (reading 1). Revisit: a cut moves the two legs onto another authority (a
    session-scoped constraint view, say), or a second face must be consulted
    for the same two facts.
    """

    def get_planner_constraint_view(
        self, as_of: str, bound_conversation_id: ConversationId
    ) -> Result[PlannerConstraintView]:
        """The §9 entries in force at ``as_of``, bound to one conversation."""
        ...

    def active_constraints_for_target(
        self, target_type: str, target_id: TargetId, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """The §9 entries in force at ``as_of`` that speak about one target."""
        ...
