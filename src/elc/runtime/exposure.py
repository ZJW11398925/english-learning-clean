"""The §20 exposure write — one place, after a real teaching delivery (P8-4).

docs/RUNTIME_ARCHITECTURE.md §20 lists the five PlanningLedger events and the
two sentences the log exists to make checkable ("``SELECT != exposure``";
"CoverageDebt 不因 selection 自动偿还"). P8-3 landed the log
(``elc.planner.ledger_store`` over migration 0016's tables) and registered the
absence this module fills in: "Nothing in ``src/`` calls this store yet: the
delivery path that *presents* a Moment — p8-4's — is what makes
``teaching_presented`` (and the two lighter presentations) happen".

**What this module is.** The mapping from "a teaching action was really
delivered" to §20's word, plus the one write that appends it together with the
projection it leaves. It reads and writes through an injected store port, holds
no connection, no clock and no SQL, and it decides nothing: the caller says an
action was delivered, and this module records the fact §20 names for it.

**The two kinds §20 has no word for are registered, not silently dropped.**
The delivery path also delivers retries and explanations, and it can resume a
paused moment. §20's five words carry none of those, and the core's
:data:`~elc.planner.ledger.EVENT_EFFECTS` table is total over exactly the five —
so this module answers ``None`` for them (the same "a word nothing produces is
not a word this cut invents" posture the §12 scope resolver takes for its two
unproduced scope words). Revisit: §20 (or another canonical document) gains a
word for a retry, an explanation or a resume — then the row lands in
:data:`LEDGER_EVENT_BY_DELIVERY` and the delivery path's kinds map to it.

**``user_skip`` is the one non-presentation word this path writes.** BF-03's
skip is the user leaving a live moment (§7's abort reason), and §20's fifth
word is exactly that: a rejection that is neither a delivery nor an engagement.
Its write is a separate entry point (:func:`record_skip`) because nothing was
delivered — the word is recorded for the *moment* the user left, not for an
action.

**The event id is deterministic — and the id is only half of the store's
replay rule.** §20 names no id, and P8-3's store refuses a differing content
under an existing id (an event is a fact and is never rewritten). A delivery's
id therefore derives from what it is a fact about — the action
(:func:`exposure_event_id`) or the skipped moment (:func:`skip_event_id`) — so
the id says "this is the same presentation" across attempts. **The instant (and
the Moment) is content too**: the same id at the same instant returns the
durable row and appends nothing, while the same id at a *new* instant is
``CONFLICT``. This write stamps a fresh instant on every call
(``elc.runtime.controller`` passes ``_now()``), so a re-attempt would be the
second shape, never the first. What that buys is stated where it belongs: no
path re-attempts the write after a terminal delivery (the terminal transcript
*is* the answer — the two sites register this, and the delivery leg's one
re-offering branch is unreachable through the ordinary loop today), and a
*first* delivery is safe to write because a second row can only appear under a
second id, which only this module mints.

**The failure posture.** A read or write that returns ``Err`` never changes the
delivery's own outcome (R-INV-010's shape: a derived record's failure is not the
transcript's) — and it is never silent either: the caller receives the ``Err``
value and carries its reason on the record it returns
(``elc.runtime.controller.TeachingActionDelivery.ledger_failure``). Revisit: a
cut that gives exposure writes a durable failure trace of their own (RA §4 step
20's CP4 leg, where a projection's failures are durable job rows) replaces that
carrier with it.
"""

from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from elc.planner.ledger import (
    CoverageObligation,
    LedgerEvent,
    LedgerKeyType,
    TargetLedgerRow,
    apply_ledger_event,
)
from elc.platform.types import ActionId, Err, MomentId, Result

__all__ = [
    "LEDGER_EVENT_BY_DELIVERY",
    "UNMAPPED_DELIVERY_KINDS",
    "LedgerExposureWriter",
    "exposure_event_id",
    "ledger_event_of",
    "record_exposure",
    "record_skip",
    "skip_event_id",
]

#: The delivery kinds that present the target as teaching → §20's three
#: presentation words. The keys are
#: ``elc.runtime.controller.TEACHING_ACTION_BY_DELIVERY``'s kind words — the
#: path's own vocabulary, not a second one — and a pin holds the two together.
LEDGER_EVENT_BY_DELIVERY: Mapping[str, LedgerEvent] = {
    "OPENING": LedgerEvent.TEACHING_PRESENTED,
    "HINT": LedgerEvent.HINT_PRESENTED,
    "REVEAL": LedgerEvent.REVEAL_PRESENTED,
}

#: The delivery kinds §20 has no word for (module docstring). Declared as data
#: so :func:`ledger_event_of` can refuse a kind that is neither mapped nor
#: registered — a further kind arriving without an entry here is a contract
#: error rather than a silent no-write.
UNMAPPED_DELIVERY_KINDS: tuple[str, ...] = (
    "RETRY",
    "EXPLANATION",
    "RESUME",
)


def ledger_event_of(delivery_kind: str) -> LedgerEvent | None:
    """§20's word for one delivered teaching action, or ``None`` for the kinds
    §20 does not name.

    An unknown kind raises rather than answering ``None``: "§20 has no word for
    this" and "this is not a kind the path delivers" are different facts, and
    only the first is a reason to write nothing.
    """

    if (
        delivery_kind not in LEDGER_EVENT_BY_DELIVERY
        and delivery_kind not in UNMAPPED_DELIVERY_KINDS
    ):
        raise ValueError(
            f"unknown delivery kind {delivery_kind!r}: the teaching delivery"
            " path's kinds are the mapped ones plus the registered unmapped"
            " ones (elc.runtime.exposure)"
        )
    return LEDGER_EVENT_BY_DELIVERY.get(delivery_kind)


def exposure_event_id(action_id: ActionId) -> str:
    """The durable id of one delivery's exposure event (module docstring)."""

    return f"ev-{action_id}"


def skip_event_id(moment_id: MomentId) -> str:
    """The durable id of one moment's ``user_skip`` event.

    A moment aborts at most once (the skip *is* what terminalizes it), so
    deriving the id from the moment names that one fact; the write itself is
    attempted once by the abort path, and a re-attempt would carry a new
    instant and be refused as ``CONFLICT`` rather than silently replayed
    (module docstring — the id is only half of the store's replay rule).
    """

    return f"ev-skip-{moment_id}"


class LedgerExposureWriter(Protocol):
    """The two reads and the one write this module needs.

    Structurally ``elc.planner.ledger_store.SqliteLedgerStore`` — declared here
    rather than imported for the reason P8-1's ports are declared at their own
    boundary: this module's dependency stays visible, and the runtime package
    never pulls the ledger store's SQL machinery into its import graph. The
    three shapes are that store's, method for method; the two row types are the
    pure core's (:mod:`elc.planner.ledger`, SQL-free by construction), so naming
    them costs nothing, while ``record_ledger_event``'s answer stays
    ``Result[object]`` — its row record lives beside the SQL, and naming it here
    would import that module.
    """

    def get_ledger_row(
        self, ledger_key: str
    ) -> Result[TargetLedgerRow | None]: ...

    def list_obligations(
        self, *, target_or_family_id: str | None = None
    ) -> Result[tuple[CoverageObligation, ...]]: ...

    def record_ledger_event(
        self,
        *,
        event_id: str,
        event: LedgerEvent,
        row: TargetLedgerRow,
        key_type: LedgerKeyType = LedgerKeyType.TARGET,
        obligations: Sequence[CoverageObligation] = (),
        moment_id: str | None = None,
    ) -> Result[object]: ...


def record_event(
    *,
    writer: LedgerExposureWriter,
    event_id: str,
    event: LedgerEvent,
    target_key: str,
    moment_id: MomentId | None,
    at: str,
) -> Result[object]:
    """Append one §20 event and the projection it leaves, for one target key.

    The chain is the store's own contract (P8-3's ``record_ledger_event``: "the
    unit is *this event and the row it leaves*"), in the order the task book
    fixes — read the row's log (``None`` = the key has no row yet, so the row is
    the empty one this event opens), append the event to it, apply the event to
    every obligation the key carries, and hand both to the store:

    - ``target_key`` is the target id **as spelled** — the core's own key
      convention (``PlanningLedger.row_of`` / ``obligations_for`` both match "as
      spelled"), so nothing here normalizes or prefixes it;
    - ``obligations`` are the ones this event **changed**: an unchanged
      obligation is already durable and identical, and re-writing it would be a
      statement carrying no new fact. ``apply_ledger_event`` is the core's (the
      one §20 effect table), so a ``hint_presented`` exposes without serving and
      a ``teaching_presented`` serves — this module re-derives neither;
    - ``moment_id`` is migration 0017's provenance column, written with the
      event so a reader can see which presentation a fact came from.

    Every failure is the caller's to report (module docstring): this function
    returns the store's ``Err`` untouched and writes nothing else.

    **Two registered limits** (review F6), both stated rather than exercised:

    - the key face below is hard-coded ``LedgerKeyType.TARGET``. The delivery
      path always spells a target id today (§15's ``focus_target``), so no
      case in this cut delivers for a ``CAPABILITY`` focus target; the store
      compares the face when a row already exists, so a mixed history would be
      refused rather than mis-labelled — but nothing here has been run against
      one. Revisit: the first cut that delivers teaching for a ``CAPABILITY``
      target, which takes the face from the moment's
      ``focus_target.target_type`` and pins the mapping beside this constant;
    - the ``RETRY`` kind's "no word, no write" is pinned at the *mapping* only
      (:func:`ledger_event_of`): the delivery path's retry has no case that
      runs it, because a retry needs a live Moment mid-conversation. Revisit:
      the continuation leg gaining a retry example (or the rollout suite).
    """

    existing = writer.get_ledger_row(target_key)
    if isinstance(existing, Err):
        return existing
    row = existing.value
    if row is None:
        row = TargetLedgerRow(target_key=target_key)
    appended = row.record(event, at=at)
    carried = writer.list_obligations(target_or_family_id=target_key)
    if isinstance(carried, Err):
        return carried
    changed = []
    for obligation in carried.value:
        outcome = apply_ledger_event(obligation, event, at=at)
        if outcome.changed:
            changed.append(outcome.obligation)
    return writer.record_ledger_event(
        event_id=event_id,
        event=event,
        row=appended,
        key_type=LedgerKeyType.TARGET,
        obligations=tuple(changed),
        moment_id=None if moment_id is None else str(moment_id),
    )


def record_exposure(
    *,
    writer: LedgerExposureWriter,
    event_id: str,
    event: LedgerEvent,
    target_key: str,
    moment_id: MomentId,
    at: str,
) -> Result[object]:
    """One §20 presentation event for one delivered action (see
    :func:`record_event` for the unit)."""

    return record_event(
        writer=writer,
        event_id=event_id,
        event=event,
        target_key=target_key,
        moment_id=moment_id,
        at=at,
    )


def record_skip(
    *,
    writer: LedgerExposureWriter,
    event_id: str,
    target_key: str,
    moment_id: MomentId,
    at: str,
) -> Result[object]:
    """Append one §20 ``user_skip`` for the moment the user left.

    The same unit as :func:`record_exposure`, with the one word §20 names for a
    user leaving: no presentation happened, so the core's effects table makes
    this neither an exposure nor a serving — the record is a rejection, and its
    durable consequences are the row's ``recent_skips`` projection (the derived
    column) and the log's own new fact.
    """

    return record_event(
        writer=writer,
        event_id=event_id,
        event=LedgerEvent.USER_SKIP,
        target_key=target_key,
        moment_id=moment_id,
        at=at,
    )
