"""Session budget — docs/DATA_MODEL.md §5.2's ``Derived view``, derived (P8-2).

§5.2 spells the block ``SessionBudgetView`` / ``Derived view`` and its ten
columns; docs/DOMAIN_MODEL.md §13 names the two authorities it derives from —

    `SessionBudgetView` 由 `TeachingPolicyProfile` + `Runtime Session State`
    共同派生，至少包含：automatic_teaching_used / remaining、probe_budget、
    cooldown、recent_skips/rejections、fatigue_signal

— and closes with the sentence that fixes its scope: "它是 Planner input，不是
Learning State" (DOMAIN_MODEL.md §10 lists it among the Planner's input
authorities, beside ``ScheduleView``). This module *is* the derivation: pure
functions over the conversation's durable ``teaching_moment`` rows plus one
narrow policy port, with **zero SQL, zero clock and zero I/O** (the
``elc.scheduler.spacing`` precedent). The record shape lives in
:class:`elc.teaching.types.SessionBudgetView`; the production face that reads
the durable rows and the policy row and calls this module is
``TeachingController.get_session_budget_view`` — a **pure read**.

**Derived means derived.** §5.2 labels the block ``Derived view``, so no table
carries it, this cut lands no migration, and no canonical column moves: the
view is recomputed from the rows on every call. Nothing here writes.

**The registration this view was waited for.** ``elc.planner.frontier``'s
``MISSING_FRONTIER_AUTHORITIES['cognitive feasibility']`` registers
``SessionBudgetView`` only as a missing authority for the frontier — "no
authority in Phase 7" — with the revisit quoted verbatim: "Revisit:
SessionBudgetView lands (or a cut lands any session-scope feasibility
reading) — then the frontier question is re-asked with an authority behind it"
(that registration is P6-1's, carried into P7-3 by the entry itself). The
revisit's condition has now fired **for the view**: the authority exists,
produced by ``TeachingController.get_session_budget_view``. The entry, its
wording and every frontier predicate stay exactly as P7-3 wrote them — whether
``cognitive feasibility`` may now be assembled is a BF-02 semantics question
for its own cut, not a side effect of this one, so this paragraph registers the
fact and leaves the entry to the cut that answers it. One sibling sentence
went stale with the same landing and is registered here rather than edited:
``elc.planner.frontier``'s **module prose** beside that entry says BF-03 §17's
runtime session state "no cut produces", and P8-2 is the cut that landed the
view reading it — so that prose is expired too, and it stays with the entry
for the cut that touches ``frontier.py`` (registered here so it is found, not
forgotten).

**One session is one conversation** (declared reading). §5.2's view block
carries ``conversation_id`` and no session key, so Local V1 reads a session as
a conversation — the view *is* that conversation's budget. This is a reading,
not a quotation: a session entity spanning conversations would need its own
durable carrier first. **Revisit**: a cut lands a session object distinct from
``ConversationRecord`` (or canonical text keys the view by something else) —
the read face then takes that key and this paragraph goes.

**Per-field derivation** (each line is this cut's reading; §5.2 pins the
columns and no formulas):

- ``conversation_id`` ← the caller's key, carried verbatim (the view's own
  identity). Revisit: the session-keyed reading above lands;
- ``policy_version`` ← the version of the policy row the port read, and
  ``None`` when no policy is configured. The view must say *which policy read
  them* — the ``ScheduleView.schedule_version`` reading ("one view holds many
  rows and therefore many row versions") — and a missing row gets ``None``
  rather than an invented version. Revisit: §5.1 gains a "the policy in force
  at an instant" rule (policies are one row per user today, so there is
  nothing to choose between);
- ``automatic_teaching_used`` ← the count of this conversation's durable
  ``source='AUTOMATIC'`` moments, closed or live (§5.2 names a usage count;
  the durable history is the usage). Revisit: canonical says whether the count
  is per session, per day or bounded by a window;
- ``automatic_teaching_remaining`` / ``probe_budget_remaining`` ← ``None``,
  underivable and stated as such: §5.1 spells ``interruption_budget`` a raw
  ``str | None`` and **no document pins a value vocabulary** for it, so turning
  it into a number would be inventing one. ``None`` is not ``0``: "no number
  was read" and "the budget is spent" are different facts, and the Gate's
  ``automatic_session_budget_exhausted`` reads exactly that difference
  (``remaining <= 0``, never ``remaining is None``). The probe *usage* is
  readable instead of guessed — the count of this conversation's automatic
  ``target_mode='PROBE'`` moments (§11's word), through
  :func:`automatic_probe_moments_used` and the controller's
  ``count_automatic_probe_moments`` face. The derivation point a vocabulary
  would land at is the line right here. Revisit: canonical (or a calibration
  cut) pins the budget vocabulary and the automatic/probe split of it;
- ``cooldown_remaining`` ← :data:`COOLDOWN_WINDOW_SECONDS` minus the elapsed
  time since the newest automatic opening **at or before ``as_of``** (measured
  on §15's ``opened_at``, the column that says when the episode opened),
  floored at ``0.0``; no automatic opening (at or before ``as_of``) ⇒ ``0.0``.
  The window is an instant question ("is the cooldown still running?"), so the
  interval is computed on parsed instants, the ``spacing.state_at``
  distinction from the durable byte-order rule. Revisit: BF-03 §17 (or IP)
  pins a number, or a cut stores an opening's own cooldown instead of
  deriving it (or measures it from another §15 column, which reconciles this
  line);
- ``recent_skips`` / ``recent_rejections`` ← the count of this conversation's
  moments whose §7 ``abort_reason`` is ``USER_SKIP`` / ``USER_REJECTED_TARGET``
  and whose closure (the §15 ``teaching_terminal_at``) lies inside
  :data:`RECENT_TEACHING_WINDOW_SECONDS` before ``as_of``. The window is a
  declaration (§7 pins the words, not a recency horizon) and it is a
  **separate name** from the cooldown window, because the two answer different
  questions. Revisit: canonical names a fatigue/recency window, or a consumer
  needs the counts over a different horizon — the constant and its reading
  move together;
- ``fatigue_signal`` ← ``None``. No canonical document defines the signal and
  no landed consumer reads it — no Gate profile reads these counts today, and
  ``planner.ledger``'s same-named field is P7-3's own record, not this view's
  — so this cut states none. Revisit: canonical defines a fatigue vocabulary
  (or a producer derives one) — the field's type admits the word, and this
  line is where it would be read;
- ``as_of`` ← the caller's instant, carried verbatim — the instant the
  classification was made at (the ``ScheduleView.as_of`` precedent: a view is
  reproducible, so two consumers asking about the same instant see the same
  picture and a test can pin it, and the store's clock is never consulted).

**Instants, and what "at ``as_of``" means.** ``as_of`` is the classification
instant: the time-derived legs (``cooldown_remaining`` and the two counts)
read only facts that had happened at or before it, while the plain usage count
above counts the durable rows §5.2 names. Two spellings of one instant are the
same moment here (instants are compared, not bytes — the scheduler's
"instant, not a byte order" distinction) and the equality boundary is
inclusive on both ends (an opening exactly ``COOLDOWN_WINDOW_SECONDS`` before
``as_of`` leaves ``0.0``; a closure exactly on the window's far edge counts).
An unusable instant — empty, unparseable, or naive — **refuses the whole
view** (``VALIDATION_FAILED``, naming the column and the row) rather than
being skipped or rounded: a view that silently dropped a row would understate
the budget the Gate reads, exactly as the Scheduler's view refuses an
unparseable window.

**The instant ruler is restated, not imported.** :func:`_parse_instant`
declares the same three refusals as :func:`elc.scheduler.spacing.parse_instant`
— and, third of its line, ``elc.user_config.store``'s private copy — for the
same reason those two restate each other: this module imports no other domain
(the ruler is restated rather than imported from ``elc.scheduler.spacing``).
The Scheduler's declaration and this one are pinned to agree by test; the
``user_config.store`` copy carries no such cross-module pin. **Revisit**: the
ruler moves to the shared kernel (``elc.platform``), at which point all three
copies are replaced by the one.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol, Sequence, TypeVar

from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PolicyVersion,
    Result,
    UserId,
)
from elc.teaching.types import (
    AbortReason,
    MomentSource,
    SessionBudgetView,
    TeachingMomentRecord,
)

__all__ = [
    "COOLDOWN_WINDOW_SECONDS",
    "RECENT_TEACHING_WINDOW_SECONDS",
    "SessionBudgetPolicyPort",
    "SessionBudgetPolicySource",
    "automatic_probe_moments_used",
    "session_budget_view_of",
]

#: The hard-opening cooldown window, in seconds — an **implementation-declared
#: constant**. BF-03 §17 gives the cooldown's semantics ("只针对 ``new
#: AUTOMATIC OPEN``"; it blocks neither a user-initiated OPEN nor an active
#: Moment's continuation) and names **no number**, and neither does
#: docs/IMPLEMENTATION_PLAN.md; this cut therefore declares one, states it
#: once here, and never presents it as canonical. Thirty minutes is the
#: declared default: long enough that a hard cooldown means a break between
#: teaching bursts, short enough that one sitting's later turns are not
#: starved. **Revisit**: BF-03 v1.2 or IP §13's calibration face pins a
#: number, or p8-5's rollout gate calibrates it — a calibration replaces this
#: constant (and :data:`RECENT_TEACHING_WINDOW_SECONDS` stays independent of
#: it: they answer different questions).
COOLDOWN_WINDOW_SECONDS: float = 1800.0

#: The "recent" window of the two closure counts, in seconds — an
#: **implementation-declared constant**, separate from the cooldown on
#: purpose. §7 pins the closure *words* and no recency horizon; `recent_` in
#: §5.2's column names is what this constant makes concrete. One hour is the
#: declared default: roughly one sitting, which is the horizon over which
#: "the user keeps skipping" is a fact about this session rather than about
#: the week. **Revisit**: canonical defines the horizon, or a consumer needs
#: the counts over a different one — the constant and its reading move
#: together (never silently: a changed window changes what the Gate's
#: controls see).
RECENT_TEACHING_WINDOW_SECONDS: float = 3600.0

#: §11's ``target_mode`` word a probe opening carries — carried as the literal
#: because the Teaching domain keeps ``target_mode`` a raw §11 column (§15)
#: and the vocabulary's enum lives with the Planner
#: (:class:`elc.planner.types.TargetMode`), which this package does not import.
#: ``PROBE`` is the one word this module branches on, and it branches on it by
#: the §11 spelling.
_PROBE_TARGET_MODE = "PROBE"

#: The two §7 closure words the view's recency counts read, taken from the
#: canonical vocabulary rather than re-spelled (the store's own rule).
_RECENT_CLOSURE_WORDS = (
    AbortReason.USER_SKIP.value,
    AbortReason.USER_REJECTED_TARGET.value,
)

T = TypeVar("T")


class SessionBudgetPolicyPort(Protocol):
    """The policy legs the view reads (docs/DATA_MODEL.md §5.1's
    ``TeachingPolicyProfile``), narrowed to the fields that have a reading.

    One field, deliberately: the version the view must carry. §5.1's budget
    column (``interruption_budget``) is **not** declared here — it is raw text
    with no value vocabulary, and a port that named it would invite a reader to
    parse it into a number this cut has no authority to invent (the
    ``FreshnessPort`` rule: the other fields are unnamed so they cannot be
    consumed). The cut that lands a budget vocabulary adds the field here and
    the derivation in :func:`session_budget_view_of`.

    Satisfied structurally by :class:`elc.user_config.types.
    TeachingPolicyProfile` (its ``policy_version`` is a ``PolicyVersion``, which
    is the declared type's subtype) — this module imports no other domain.
    """

    policy_version: PolicyVersion | None


class SessionBudgetPolicySource(Protocol):
    """The one policy read the production face is wired with — the **policy
    half** of docs/DOMAIN_MODEL.md §13's derivation.

    Two members, and both are necessary:

    - :attr:`user_id` — whose policy this source serves. The user leg lives on
      the port because nothing else can supply it: DATA_MODEL §3's Conversation
      carries no ``user_id`` and ``elc.conversation.store.open_conversation``
      deliberately discards the argument that could have bound one, so a
      conversation cannot be resolved to a user anywhere in the durable world
      (the ``ControllerPersonaViews`` reading, P4-3: "the user leg comes from
      the port itself"). The assembly that wires this port is where the
      binding is decided;
    - :meth:`get_teaching_policy` — the §5.1 read, shaped exactly like
      ``elc.user_config.controller.UserConfigController.get_teaching_policy``
      so a caller's adapter is a forward, not a translation. ``Ok(None)``
      means "never written" and reaches the view as ``policy_version=None``;
      an ``Err`` is the read's own failure and the view refuses with it rather
      than answering a partial picture.

    ``Result[Any]`` rather than ``Result[SessionBudgetPolicyPort]`` for the
    mechanical reason the scheduler's ``LearningReadPort`` states: ``Ok`` is an
    invariant generic, so naming the narrow protocol here would make the real
    controller unwireable. The structure is enforced where the value is *used*
    — :func:`session_budget_view_of` takes a :class:`SessionBudgetPolicyPort`,
    so ``policy_version`` is the only field any code here can read.

    **Revisit**: a cut lands a durable conversation→user binding (or a
    user-keyed session), at which point the user leg moves from the port to
    that read and this protocol loses a member.
    """

    @property
    def user_id(self) -> UserId:
        """The user whose policy this source serves."""
        ...

    def get_teaching_policy(self, user_id: UserId) -> Result[Any]:
        """The user's teaching policy row, or ``Ok(None)`` if never written."""
        ...


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _parse_instant(text: str, *, field: str) -> Result[datetime]:
    """One ISO-8601 timestamp of this module's inputs, as an instant.

    The same three refusals :func:`elc.scheduler.spacing.parse_instant`
    declares (module docstring: restated, not imported, and pinned to agree
    by test):

    - empty — an instant that was never written cannot be compared;
    - unparseable — not ISO-8601 in any spelling ``datetime`` accepts;
    - **naive** — no UTC offset; this derivation will not assume a zone for a
      caller.

    All three are ``VALIDATION_FAILED`` and name ``field``, so a refusal says
    which input was unusable.
    """

    if not text:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} is empty; an instant must be an ISO-8601 timestamp"
            " carrying a UTC offset",
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} {text!r} is not an ISO-8601 timestamp",
        )
    if parsed.tzinfo is None:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} {text!r} carries no UTC offset; this derivation will"
            " not assume a zone (write the offset, e.g. +00:00)",
        )
    return Ok(parsed)


def _optional_instant(text: str | None, *, field: str) -> Result[datetime]:
    """One durable timestamp that a row is required to carry.

    ``None`` is refused with the same vocabulary as an empty string: the
    durable writer stamps both ``created_at`` and ``opened_at`` on the way in
    (``elc.teaching.store``), so a row that names no instant is a row this
    reading cannot place in time — and a silently skipped row would understate
    the budget.
    """

    if text is None:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} is missing; the durable row carries no instant to"
            " classify at as_of",
        )
    return _parse_instant(text, field=field)


def _rows_of(
    conversation_id: ConversationId,
    moments: Sequence[TeachingMomentRecord],
) -> tuple[TeachingMomentRecord, ...]:
    """The view's own conversation's rows, in the order they arrived.

    The caller's read is this function's contract check: a wider read is
    narrowed here rather than trusted, so the view can never count another
    conversation's teaching (two conversations sharing a user is the ordinary
    case, and a budget is per session).
    """

    return tuple(
        moment
        for moment in moments
        if moment.conversation_id == conversation_id
    )


def automatic_probe_moments_used(
    *,
    conversation_id: ConversationId,
    moments: Sequence[TeachingMomentRecord],
) -> int:
    """How many automatic §11 ``PROBE`` moments this conversation holds.

    The *usage* leg of §5.2's ``probe_budget_remaining``: what the vocabulary
    would be subtracted from. It is readable without the vocabulary (the rows
    are), which is why the view's ``probe_budget_remaining`` can be ``None``
    without the usage being hidden — a reader who wants the count asks for it.

    The count is over the durable rows, closed or live, exactly like
    ``automatic_teaching_used`` (module docstring).
    """

    return sum(
        1
        for moment in _rows_of(conversation_id, moments)
        if moment.source is MomentSource.AUTOMATIC
        and moment.target_mode == _PROBE_TARGET_MODE
    )


def session_budget_view_of(
    *,
    conversation_id: ConversationId,
    as_of: str,
    policy: SessionBudgetPolicyPort | None,
    moments: Sequence[TeachingMomentRecord],
) -> Result[SessionBudgetView]:
    """The §5.2 view of one conversation at ``as_of`` (module docstring).

    The inputs are the two authorities §13 names and nothing else: the
    conversation's durable ``teaching_moment`` rows (Runtime Session State's
    durable half) and the policy leg (``TeachingPolicyProfile``), ``None``
    when no policy row exists. Every other field is a declared reading stated
    in the module docstring — this function composes them and computes
    nothing a reader cannot check against the rows it was handed.

    ``Err`` for exactly two reasons: an unusable instant (refused, never
    skipped — see the module docstring) and nothing else; a policy row's own
    read failure is the caller's Err, already returned before this call.
    """

    now = _parse_instant(as_of, field="as_of")
    if isinstance(now, Err):
        return now
    rows = _rows_of(conversation_id, moments)

    automatic_used = 0
    newest_automatic: datetime | None = None
    for moment in rows:
        if moment.source is not MomentSource.AUTOMATIC:
            continue
        automatic_used += 1
        opened = _optional_instant(
            moment.opened_at,
            field=f"teaching moment {moment.moment_id} opened_at",
        )
        if isinstance(opened, Err):
            return opened
        if opened.value > now.value:
            # Not yet a fact at the classification instant: an opening after
            # ``as_of`` has not started a cooldown at ``as_of``.
            continue
        if newest_automatic is None or opened.value > newest_automatic:
            newest_automatic = opened.value

    cooldown_remaining = 0.0
    if newest_automatic is not None:
        elapsed = (now.value - newest_automatic).total_seconds()
        cooldown_remaining = max(0.0, COOLDOWN_WINDOW_SECONDS - elapsed)

    window_start = now.value - timedelta(seconds=RECENT_TEACHING_WINDOW_SECONDS)
    skips = 0
    rejections = 0
    for moment in rows:
        if moment.abort_reason not in _RECENT_CLOSURE_WORDS:
            continue
        closed = _optional_instant(
            moment.teaching_terminal_at,
            field=(
                f"teaching moment {moment.moment_id} teaching_terminal_at"
            ),
        )
        if isinstance(closed, Err):
            return closed
        if not window_start <= closed.value <= now.value:
            continue
        if moment.abort_reason == AbortReason.USER_SKIP.value:
            skips += 1
        else:
            rejections += 1

    return Ok(
        SessionBudgetView(
            conversation_id=conversation_id,
            policy_version=None if policy is None else policy.policy_version,
            automatic_teaching_used=automatic_used,
            # The two budget legs have no vocabulary to read (module
            # docstring): None is the honest answer, never 0.
            automatic_teaching_remaining=None,
            probe_budget_remaining=None,
            cooldown_remaining=cooldown_remaining,
            recent_skips=skips,
            recent_rejections=rejections,
            # No canonical signal exists and no consumer reads one.
            fatigue_signal=None,
            as_of=as_of,
        )
    )
