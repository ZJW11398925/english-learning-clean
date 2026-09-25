"""The five delivery records — the §22 / §21.1 durable face's port (P9-1).

docs/DATA_MODEL.md §22 "Delivery Data" names three records and §21.1
"Validator / PreDelivery Guard Records" names two: what one GenerationAction
was actually sent as (``ServerDeliveryRecord``), what the client confirmed it
rendered (``ClientRenderAck``), how much of the answer was exposed
(``ExposureEstimate``), what the Response Validator decided about one
provider attempt (``ValidatorResult``), and what the PreDeliveryGuard decided
before the send (``PreDeliveryGuardResult``). docs/RUNTIME_ARCHITECTURE.md §6
CP3a is the commit point the first two of those belong to, and §6's next block
is the split this port restates: the main Turn does not wait for a
``ClientRenderAck`` — the ACK is an asynchronous refinement event (RA §14:
"Late ClientRenderAck 只作为 certainty refinement").

This module is SQL-free, holds no clock and holds no connection: it declares
the four new row shapes, reuses the shipped §21.1 shape (see judgement 9), the
vocabulary refusals the write face answers with (judgement 2), the
:class:`DeliveryRecordStore` port, and — below — the **one** place where the
canonical column names are mapped to the implementation's field names. Every
durable statement lives in ``elc.platform.db.delivery_store`` (Gate item 2's
split: the authority is a port, the SQL is in the platform db layer).

---------------------------------------------------------------------------
The column map (§22 / §21.1 ↔ implementation) — stated once, here
---------------------------------------------------------------------------

The canonical spelling is the left-hand side **verbatim, brackets included**
(``reason_codes[]`` is a bracketed list column; the durable column is
``reason_codes``, the 0015/0016 convention for the same name). The right-hand
side is the field the row shape carries — every one of them spelled exactly
like the column, which is a fact this cut *has*, not one it chose: §22's and
§21.1's block words are all lower_snake_case and so are the fields.

==============================  =============================================
canonical column                implementation
==============================  =============================================
``action_id``                   ``ServerDeliveryRecord.action_id`` /
                                ``ClientRenderAck.action_id`` /
                                ``ExposureEstimate.action_id`` /
                                ``(persona.types).ValidatorResult.action_id`` /
                                ``PreDeliveryGuardResult.action_id``
``assistant_turn_id``           ``ServerDeliveryRecord.assistant_turn_id`` /
                                ``ClientRenderAck.assistant_turn_id``
``state``                       ``ServerDeliveryRecord.state``
``sent_prefix``                 ``ServerDeliveryRecord.sent_prefix``
``last_chunk_seq``              ``ServerDeliveryRecord.last_chunk_seq``
``started_at``                  ``ServerDeliveryRecord.started_at``
``terminal_at``                 ``ServerDeliveryRecord.terminal_at``
``rendered_chunk_seq``          ``ClientRenderAck.rendered_chunk_seq``
``rendered_text_hash``          ``ClientRenderAck.rendered_text_hash``
``acked_at``                    ``ClientRenderAck.acked_at``
``final_rendered``              ``ClientRenderAck.final_rendered``
``certainty``                   ``ExposureEstimate.certainty``
``exposure_level``              ``ExposureEstimate.exposure_level``
``max_possible_exposure``       ``ExposureEstimate.max_possible_exposure``
``confirmed_exposure``          ``ExposureEstimate.confirmed_exposure``
``derivation_reason``           ``ExposureEstimate.derivation_reason``
``validator_result_id``         ``(persona.types).ValidatorResult.validator_result_id``
``attempt_no``                  ``(persona.types).ValidatorResult.attempt_no``
``decision``                    ``(persona.types).ValidatorResult.decision`` /
                                ``PreDeliveryGuardResult.decision``
``reason_codes[]``              ``(persona.types).ValidatorResult.reason_codes`` /
                                ``PreDeliveryGuardResult.reason_codes``
``validator_version``           ``(persona.types).ValidatorResult.validator_version``
``pre_delivery_guard_result_id`` ``PreDeliveryGuardResult.pre_delivery_guard_result_id``
``checked_lineage_version``     ``PreDeliveryGuardResult.checked_lineage_version``
``created_at``                  ``(persona.types).ValidatorResult.created_at`` /
                                ``PreDeliveryGuardResult.created_at``
==============================  =============================================

:data:`COLUMN_MAP` carries the map per table (canonical spelling in canonical
block order ↔ field name), and the ``*_COLUMNS`` constants beside it are the
durable column lists every statement in the adapter uses — derived from the
map rather than typed a second time, so a statement and this table cannot
drift apart.

---------------------------------------------------------------------------
**Declared judgements.** Each entry is this cut's reading rather than a
quotation, and each names the condition that re-opens it.
---------------------------------------------------------------------------

1. **Five ``action_id`` foreign keys, and ``assistant_turn_id`` with none.**
   Every one of the five rows is about exactly one GenerationAction, so the
   adapter's writes land on ``generation_action_intent`` (migration 0018's
   header carries the argument). ``assistant_turn_id`` — on the two §22 rows —
   deliberately carries no reference, and that is migration 0003's own
   reading quoted forward: "the id is minted at action creation (stable opaque
   id, DATA_MODEL §1.2) and realized as the assistant_turn row only at
   canonicalization (CP3a); the back-reference survives as plain data." A
   delivery row is first written *before* CP3a, so the referenced row need not
   exist yet. Revisit: canonicalization is shown to land the assistant_turn row
   before any delivery record — then the reference becomes satisfiable and
   0003's column has to be re-audited in the same breath.
2. **The §22 vocabulary columns are refused in Python; the §21.1 ones are
   refused by the schema — and the two §21.1 columns do not have the same
   reach.** §22's blocks state no word lists (the words are STATE_MACHINES
   §13's and the repository's enums'), so nothing in the schema may spell
   them; :func:`state_word_refusal`, :func:`certainty_word_refusal` and
   :func:`exposure_word_refusal` are the write face's guard and answer
   ``VALIDATION_FAILED`` for a word outside the vocabulary — the same code the
   platform's other faces use for "the caller's data is not a value".
   §21.1's ``decision`` columns *are* spelled inline, so migration 0018 carries
   their CHECKs — but only one of the two columns has the CHECK as its first
   line: ``PreDeliveryGuardResult.decision`` is a plain ``str`` field, so an
   out-of-vocabulary word reaches the schema and the adapter answers
   ``CONFLICT``, while ``ValidatorResult.decision`` is the shipped
   ``elc.persona.types.ValidatorDecision`` enum, so the type system holds that
   vocabulary *first* and the CHECK is the schema's backstop against a caller
   that bypassed the type. The two reaches are registered rather than smoothed
   (a value the enum cannot hold never reaches a store, which is why no test
   drives that arm — the port's own tests state the enum/CHECK agreement
   instead). Revisit: canonical moves the §13 words into §22's blocks (the
   CHECKs land with that revision), or a caller appears that needs a word the
   enums do not carry (then the vocabulary is canonical text's to widen, not
   this module's).
3. **The two exposure columns carry §13's words, not numbers.**
   ``max_possible_exposure`` / ``confirmed_exposure`` are RA §14's two
   readings of one estimate ("confirmed exposure where available, otherwise
   max-possible-exposure"), and the only exposure scale canonical text
   declares is §13's three words (NONE / PARTIAL / FULL) — the shape the
   estimator's own baseline uses in its claims ("exposure_level": "FULL").
   A numeric reading has no declared scale (no unit, no range, no mapping), so
   it is **refused** rather than invented; both columns are validated by
   :func:`exposure_word_refusal`. Revisit: canonical (or BF-01) declares a
   numeric exposure scale.
4. **The server-delivery row advances under four monotonic invariants — and
   no state lattice.** ``state``'s six words are §13's, but which transition
   between them is legal is the **P9-2 writer's** face (the same split the
   Gate's two user-initiated profiles and the teaching controller already
   have), so this port's write face checks only what the record's own meaning
   makes impossible to reverse: (a) ``last_chunk_seq`` never decreases;
   (b) ``sent_prefix`` only grows — the old value is a prefix of the new one,
   and the empty string is "nothing sent yet" (RA §17: the sent boundary is
   the canonicalized fact, never replayed from the top); (c) a row's
   ``assistant_turn_id`` and ``started_at`` never change (they say *which*
   delivery this is); (d) once ``terminal_at`` is set the row is frozen. A
   re-entry that is byte-for-byte the durable row is a **replay** (the durable
   row is returned, nothing is written — the RA §23 crash-window posture);
   a re-entry that would move any of the four invariants is ``CONFLICT``.
   Revisit: the P9-2 stream writer lands (then the lattice question is that
   cut's, and a legal transition set that contradicts (c)/(d) re-opens this
   list), or canonical gives ``sent_prefix`` a second meaning for "not sent".
5. **The instants are content, and the adapter reads no clock.** Every instant
   column (``started_at`` / ``terminal_at`` / ``acked_at`` / ``created_at``)
   arrives on the record and is compared **verbatim** on a replay: the same
   bytes are a replay, a differing instant is ``CONFLICT``. This is
   deliberately **not** P8-0's convention (whose adapter stamps
   ``created_at`` itself): these records *are* the facts about a delivery's
   instants, they are written at the boundary the caller observed (the moment
   the send started, the moment the ACK arrived), and a store that stamped its
   own clock would be a second clock for a fact that already has one. Revisit:
   a cut shows a caller that cannot supply the instant it observes (then the
   clock question moves there), or canonical declares one of these stamps to be
   store-generated.
6. **§22's keys are the records' own identities.** The three §22 blocks carry
   no id column, so each is keyed by what it is: one row per action for the
   delivery fact (RA §6 CP3a names it in the singular), one row per
   (action, chunk) for the ACK stream, one row per action for the *current*
   estimate. §21.1's two blocks carry ids and are keyed by them. Nothing here
   mints a synthetic id: a second spelling of an identity that canonical text
   already pins is how two readers start disagreeing. Revisit: canonical gives
   any of the three §22 blocks an id column.
7. **The initial exposure estimate is written once; refinement is a later
   cut's explicit face.** :meth:`DeliveryRecordStore.record_initial_exposure_estimate`
   is named for what §6 CP3a commits ("initial ExposureEstimate"): a second
   submission with different content is ``CONFLICT`` rather than an in-place
   move, because if the estimate may be rewritten the record stops being what
   the evidence was attributed from (RA §14's conservative rule reads *this*
   row). Refinement is **registered as a face, and that face is judgement 11's**
   (P9-4 landed it): this method keeps its "initial" name because it writes the
   CP3a row, and an acknowledgment moves that row only through
   :meth:`DeliveryRecordStore.refine_exposure_estimate`, which refuses every
   column move the derivation did not make.
   ``attempt_record.exposure_estimate_id`` (migration 0008, §17's '?', plain
   data with no foreign key) is the one column that names this record from
   outside, and this cut registers that the identity it carries **is the
   action_id** — the estimate's key — rather than changing 0008's column.
   Revisit: a writer actually fills ``attempt_record.exposure_estimate_id``
   (then that write's reader is the place the identity reading becomes
   load-bearing).
8. **``sent_prefix``'s empty string is the "nothing sent" spelling.** §22 gives
   the column no null, RA §17 makes the sent boundary the record's durable
   fact, and the empty string is a prefix of every string — which is exactly
   the monotonic shape judgement 4(b) needs. A NULL here would be a second
   spelling of the same state, so none is offered. Revisit: a canonical
   revision makes "not sent yet" a distinct durable state (e.g. a NULL or a
   state word the advance rule branches on).
9. **``ValidatorResult`` is reused, not copied — and the registry's entry for
   that name is left where it is.** ``elc.persona.types.ValidatorResult``
   already declares itself "docs/DATA_MODEL.md §21.1 ValidatorResult (column
   set verbatim)" and the shipped validator produces it, so this port imports
   it (with the same module's ``ValidatorDecision`` for the vocabulary) rather
   than minting a second shape. Its ``created_at`` is ``str | None`` while
   §21.1's row is NOT NULL: a submission with ``None`` is refused
   (``VALIDATION_FAILED``) rather than stamped — judgement 5's rule. The
   deliberate drift is **registered, not repaired**: ``elc.platform.registry``
   binds the name ``validator_result`` to
   ``elc.runtime.types.ValidatorResultRecord`` (a Phase 0 shape: turn_id /
   proposal_status / checked_refs), a different object, and this cut does not
   touch that module — the four records of this port are Runtime-specific
   runtime records (DOMAIN_MODEL §16's list, the ``decision_cycle`` /
   ``gate_execution_status`` / ``runtime_decision_outcome`` family) and the
   registry has never carried those. Revisit: a cut touches the registry's
   ``validator_result`` entry or the ``ValidatorResultRecord`` shape — the two
   types have to be reconciled in that one place, and this note is where the
   reconciliation starts from.
10. **The writers landed, and the port's claim is unchanged.** When this face
    was declared it had no shipped caller, and it made no claim about *when* a
    row is written — only about what a written row means. The call sites have
    since arrived: P9-2's streamed face writes the ``ServerDeliveryRecord``
    (``elc.runtime.controller.finalize_streamed_delivery``) and P9-3's guard
    writes the §21.1 rows, while P9-4's exposure reconciliation writes the two
    §22 rows this port's two remaining writes serve
    (``record_initial_exposure_estimate`` at CP3a on both delivery faces, and
    :meth:`DeliveryRecordStore.refine_exposure_estimate` from the
    acknowledgment entry). Nothing above moves: the port still describes what a
    written row means, and the *when* stays each writer's declared ordering.
    Revisit: a row of this port gains a second writer (then the two orderings
    have to be reconciled where they meet, not here).
11. **The refinement face moves two columns upward and nothing else.**
    ``exposure_estimate`` is keyed by action (judgement 6), so the
    acknowledgment's refinement is a move of *this* row rather than a second
    row — and it is legal exactly when it only raises ``certainty`` /
    ``confirmed_exposure``, which
    ``elc.runtime.exposure_reconciliation.refinement_refusal`` states in one
    place that both faces read. The sent level
    (``exposure_level`` / ``max_possible_exposure``) is the derivation's and
    this face refuses to move it in either direction: an acknowledgment
    changes what is *known*, never what was sent (RA §14's conservative rule
    reads the ceiling column, ``max_possible_exposure`` — P9-R2 lets the
    released boundary raise it, and this face still refuses to move it). A
    submission already equal to the durable
    row is a replay (judgement 4's posture, and the idempotence a repeated
    acknowledgment needs); an unknown action is ``NOT_FOUND`` — refinement has
    no initial row to refine, and this face never invents one. Revisit: a cut
    finds an acknowledgment that must lower a column (then the estimate stops
    being monotone and this judgement is the one to reopen), or canonical
    gives the estimate a version column (then the supersede gets its own
    identity instead of the row's).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from elc.conversation.types import DeliveryState
from elc.persona.types import ValidatorResult
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    DomainError,
    DomainErrorCode,
    Result,
)
from elc.teaching.types import (
    AnswerExposureState,
    ExposureEstimateCertainty,
)

__all__ = [
    "CLIENT_RENDER_ACK_COLUMNS",
    "COLUMN_MAP",
    "DELIVERY_STATE_WORDS",
    "EXPOSURE_CERTAINTY_WORDS",
    "EXPOSURE_ESTIMATE_COLUMNS",
    "EXPOSURE_LEVEL_WORDS",
    "EXPOSURE_WORD_COLUMNS",
    "PRE_DELIVERY_GUARD_RESULT_COLUMNS",
    "SERVER_DELIVERY_RECORD_COLUMNS",
    "VALIDATOR_RESULT_COLUMNS",
    "ClientRenderAck",
    "DeliveryRecordStore",
    "ExposureEstimate",
    "PreDeliveryGuardResult",
    "ServerDeliveryRecord",
    "certainty_word_refusal",
    "exposure_word_refusal",
    "state_word_refusal",
]


# ---------------------------------------------------------------------------
# The vocabularies
# ---------------------------------------------------------------------------
#
# Each §22 word list is read from the enum that already holds it (judgement 2:
# §22 itself spells none of them), so the port and the type system cannot
# drift: elc.conversation.types.DeliveryState is §13's six ServerDeliveryRecord
# words, elc.teaching.types.ExposureEstimateCertainty §13's three certainty
# words, and elc.teaching.types.AnswerExposureState §13's three exposure-level
# words.

#: STATE_MACHINES §13's six ``state`` words, via the enum that carries them.
DELIVERY_STATE_WORDS: tuple[str, ...] = tuple(
    member.value for member in DeliveryState
)

#: STATE_MACHINES §13's three ``certainty`` words.
EXPOSURE_CERTAINTY_WORDS: tuple[str, ...] = tuple(
    member.value for member in ExposureEstimateCertainty
)

#: STATE_MACHINES §13's three ``exposure_level`` words — the vocabulary all
#: three of the estimate's word columns carry (judgement 3).
EXPOSURE_LEVEL_WORDS: tuple[str, ...] = tuple(
    member.value for member in AnswerExposureState
)

#: The §22 columns that carry :data:`EXPOSURE_LEVEL_WORDS`. Pinned as the
#: literal list so :func:`exposure_word_refusal` cannot be asked about a column
#: the schema does not have (a call with a foreign column name is itself a
#: refusal).
EXPOSURE_WORD_COLUMNS: tuple[str, ...] = (
    "exposure_level",
    "max_possible_exposure",
    "confirmed_exposure",
)


# ---------------------------------------------------------------------------
# The row shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerDeliveryRecord:
    """docs/DATA_MODEL.md §22 ServerDeliveryRecord (column set verbatim).

    The durable boundary of one action's send (RA §17): ``sent_prefix`` holds
    what was actually sent, ``last_chunk_seq`` where the stream got to, and
    ``terminal_at`` is the instant the row froze (judgement 4). ``state``'s six
    words are §13's and the legal transitions between them belong to the P9-2
    writer.

    ``terminal_at`` is the one optional field (§22 spells it ``terminal_at?``);
    ``assistant_turn_id`` carries no foreign key (judgement 1).
    """

    action_id: ActionId
    assistant_turn_id: AssistantTurnId
    state: str
    sent_prefix: str
    last_chunk_seq: int
    started_at: str
    terminal_at: str | None


@dataclass(frozen=True)
class ClientRenderAck:
    """docs/DATA_MODEL.md §22 ClientRenderAck (column set verbatim).

    One asynchronous refinement event — the client reporting that it rendered
    chunk ``rendered_chunk_seq`` of the action's stream (RA §6: the main Turn
    does not wait for it). The row is keyed by (``action_id``,
    ``rendered_chunk_seq``) and is append-only: a re-submission with the same
    content is a replay, a different one is a ``CONFLICT``.

    ``final_rendered`` is the event's boolean — whether this chunk was the
    final rendered one — and lands as the schema's 0/1 (migration 0018).
    """

    action_id: ActionId
    assistant_turn_id: AssistantTurnId
    rendered_chunk_seq: int
    rendered_text_hash: str
    acked_at: str
    final_rendered: bool


@dataclass(frozen=True)
class ExposureEstimate:
    """docs/DATA_MODEL.md §22 ExposureEstimate (column set verbatim).

    The row is an action's **current** estimate (judgement 6/7), written once
    by §6 CP3a. ``certainty`` says how sure the server is that the estimate was
    seen (§13's three words), and the three exposure columns all carry §13's
    three-word scale (judgement 3).

    RA §14's conservative rule reads this row: confirmed exposure where
    available, otherwise max-possible-exposure.
    """

    action_id: ActionId
    certainty: str
    exposure_level: str
    max_possible_exposure: str
    confirmed_exposure: str
    derivation_reason: str


@dataclass(frozen=True)
class PreDeliveryGuardResult:
    """docs/DATA_MODEL.md §21.1 PreDeliveryGuardResult (column set verbatim).

    One hard-invalidation check's answer before a send (RA §15: the guard
    re-runs no Planner utility). ``decision``'s two words — §16's output
    vocabulary, repeated inline by §21.1 — are carried by the schema's CHECK
    (judgement 2), and ``checked_lineage_version`` records which lineage the
    check ran against.
    """

    pre_delivery_guard_result_id: str
    action_id: ActionId
    decision: str
    reason_codes: tuple[str, ...]
    checked_lineage_version: str
    created_at: str


# ---------------------------------------------------------------------------
# The column map — canonical spelling ↔ implementation field, per table
# ---------------------------------------------------------------------------
#
# The canonical side is the block spelling **verbatim** (``reason_codes[]``
# keeps its list brackets); the implementation side is the field name. The
# ``*_COLUMNS`` tuples beside the map are the durable column lists (brackets
# stripped), derived from it so the adapter's statements and this map are one
# declaration.

#: table → ((canonical column, field name), …) in canonical block order.
COLUMN_MAP: Mapping[str, tuple[tuple[str, str], ...]] = {
    "server_delivery_record": (
        ("action_id", "action_id"),
        ("assistant_turn_id", "assistant_turn_id"),
        ("state", "state"),
        ("sent_prefix", "sent_prefix"),
        ("last_chunk_seq", "last_chunk_seq"),
        ("started_at", "started_at"),
        ("terminal_at", "terminal_at"),
    ),
    "client_render_ack": (
        ("action_id", "action_id"),
        ("assistant_turn_id", "assistant_turn_id"),
        ("rendered_chunk_seq", "rendered_chunk_seq"),
        ("rendered_text_hash", "rendered_text_hash"),
        ("acked_at", "acked_at"),
        ("final_rendered", "final_rendered"),
    ),
    "exposure_estimate": (
        ("action_id", "action_id"),
        ("certainty", "certainty"),
        ("exposure_level", "exposure_level"),
        ("max_possible_exposure", "max_possible_exposure"),
        ("confirmed_exposure", "confirmed_exposure"),
        ("derivation_reason", "derivation_reason"),
    ),
    "validator_result": (
        ("validator_result_id", "validator_result_id"),
        ("action_id", "action_id"),
        ("attempt_no", "attempt_no"),
        ("decision", "decision"),
        ("reason_codes[]", "reason_codes"),
        ("validator_version", "validator_version"),
        ("created_at", "created_at"),
    ),
    "pre_delivery_guard_result": (
        ("pre_delivery_guard_result_id", "pre_delivery_guard_result_id"),
        ("action_id", "action_id"),
        ("decision", "decision"),
        ("reason_codes[]", "reason_codes"),
        ("checked_lineage_version", "checked_lineage_version"),
        ("created_at", "created_at"),
    ),
}


def _durable_columns(table: str) -> tuple[str, ...]:
    """The SQL column list of one record: the canonical spelling with the
    list marker dropped (``reason_codes[]`` → ``reason_codes``)."""

    return tuple(
        canonical.removesuffix("[]") for canonical, _ in COLUMN_MAP[table]
    )


SERVER_DELIVERY_RECORD_COLUMNS: tuple[str, ...] = _durable_columns(
    "server_delivery_record"
)
CLIENT_RENDER_ACK_COLUMNS: tuple[str, ...] = _durable_columns(
    "client_render_ack"
)
EXPOSURE_ESTIMATE_COLUMNS: tuple[str, ...] = _durable_columns(
    "exposure_estimate"
)
VALIDATOR_RESULT_COLUMNS: tuple[str, ...] = _durable_columns("validator_result")
PRE_DELIVERY_GUARD_RESULT_COLUMNS: tuple[str, ...] = _durable_columns(
    "pre_delivery_guard_result"
)


# ---------------------------------------------------------------------------
# The write face's vocabulary refusals (judgement 2)
# ---------------------------------------------------------------------------


def _word_refusal(
    column: str, word: str, words: tuple[str, ...]
) -> DomainError | None:
    if word in words:
        return None
    return DomainError(
        code=DomainErrorCode.VALIDATION_FAILED,
        message=(
            f"{column}={word!r} is not one of the words canonical text"
            f" declares for it ({', '.join(words)})"
        ),
    )


def state_word_refusal(state: str) -> DomainError | None:
    """§13's six ``state`` words, or ``None`` when ``state`` is one of them."""

    return _word_refusal("state", state, DELIVERY_STATE_WORDS)


def certainty_word_refusal(certainty: str) -> DomainError | None:
    """§13's three ``certainty`` words, or ``None``."""

    return _word_refusal("certainty", certainty, EXPOSURE_CERTAINTY_WORDS)


def exposure_word_refusal(column: str, word: str) -> DomainError | None:
    """§13's three exposure words on one of §22's three exposure columns.

    ``column`` must be one of :data:`EXPOSURE_WORD_COLUMNS` — asking about a
    column the schema does not have is itself a refusal — and ``word`` must be
    one of §13's three (judgement 3).
    """

    if column not in EXPOSURE_WORD_COLUMNS:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"{column!r} is not a §22 exposure word column"
                f" ({', '.join(EXPOSURE_WORD_COLUMNS)})"
            ),
        )
    return _word_refusal(column, word, EXPOSURE_LEVEL_WORDS)


# ---------------------------------------------------------------------------
# The port
# ---------------------------------------------------------------------------


@runtime_checkable
class DeliveryRecordStore(Protocol):
    """The five records' durable face: five writes and five reads.

    Implemented by ``elc.platform.db.delivery_store.SqliteDeliveryRecordStore``
    (keyword-only construction: connection + runtime epoch fence).

    Every write is one short transaction. The two verdicts a re-submission can
    receive are the module's two rules, and they are different on purpose: a
    submission byte-identical to the durable row is a **replay** — the durable
    row is returned and nothing is written (judgements 4 and 5) — while a
    submission that would move the row differently is ``CONFLICT``. The five
    reads answer ``Ok(None)`` / an empty tuple for an unknown action (the
    ``SqliteDecisionCycleStore`` precedent: an absent row is a fact, not an
    error).
    """

    def record_server_delivery(
        self, record: ServerDeliveryRecord
    ) -> Result[ServerDeliveryRecord]:
        """Persist one action's §22 delivery fact.

        The first submission inserts; a later one advances the row only while
        the four invariants hold (judgement 4) and is refused with ``CONFLICT``
        otherwise. The returned record is the durable row.
        """
        ...

    def append_client_render_ack(
        self, ack: ClientRenderAck
    ) -> Result[ClientRenderAck]:
        """Append one §22 render ACK event (keyed by action and chunk)."""
        ...

    def append_validator_result(
        self, result: ValidatorResult
    ) -> Result[ValidatorResult]:
        """Append one §21.1 ValidatorResult row (keyed by its own id).

        ``result.created_at`` must be set: the instant is content (judgement 5)
        and a ``None`` is refused with ``VALIDATION_FAILED`` rather than
        stamped by the store (judgement 9).
        """
        ...

    def append_pre_delivery_guard_result(
        self, result: PreDeliveryGuardResult
    ) -> Result[PreDeliveryGuardResult]:
        """Append one §21.1 PreDeliveryGuardResult row (keyed by its own id)."""
        ...

    def record_initial_exposure_estimate(
        self, estimate: ExposureEstimate
    ) -> Result[ExposureEstimate]:
        """Persist the §6 CP3a initial ExposureEstimate for one action.

        Written once (judgement 7): a second submission with different content
        is ``CONFLICT``; refinement is
        :meth:`refine_exposure_estimate`'s explicit face (judgement 11).
        """
        ...

    def refine_exposure_estimate(
        self, estimate: ExposureEstimate
    ) -> Result[ExposureEstimate]:
        """Move one action's §22 estimate to an acknowledgment-refined row.

        P9-4's face, and the "supersede-shaped write, not a silent move" of
        judgement 7: the submitted row is the refined estimate the caller
        derived with ``elc.runtime.exposure_reconciliation.refine_with_ack``
        (this face checks the move, it does not perform the refinement), and
        only two columns may rise — ``certainty`` / ``confirmed_exposure``
        (judgement 11). A submission identical to the durable row is a replay;
        a legal refinement replaces the row; an illegal one is
        ``VALIDATION_FAILED``; an action with no estimate is ``NOT_FOUND``
        (this face refines the CP3a row, it never mints one).
        """
        ...

    def get_server_delivery_record(
        self, action_id: ActionId
    ) -> Result[ServerDeliveryRecord | None]:
        """The action's §22 delivery row, or ``Ok(None)``."""
        ...

    def get_exposure_estimate(
        self, action_id: ActionId
    ) -> Result[ExposureEstimate | None]:
        """The action's current §22 estimate, or ``Ok(None)``."""
        ...

    def list_client_render_acks(
        self, action_id: ActionId
    ) -> Result[tuple[ClientRenderAck, ...]]:
        """The action's ACK events in ``rendered_chunk_seq`` order (possibly
        empty)."""
        ...

    def list_validator_results(
        self, action_id: ActionId
    ) -> Result[tuple[ValidatorResult, ...]]:
        """The action's §21.1 validator rows, ordered by ``attempt_no`` and id
        (possibly empty)."""
        ...

    def list_pre_delivery_guard_results(
        self, action_id: ActionId
    ) -> Result[tuple[PreDeliveryGuardResult, ...]]:
        """The action's §21.1 guard rows, ordered by instant and id (possibly
        empty)."""
        ...
