"""BF-05 source-aware deletion — the vocabulary and the durable record shapes.

Gate 2 (docs/IMPLEMENTATION_PLAN.md §16 DoD #25: "删除 canonical user source
可删除/重建 solely-derived Learning/Relationship/Episode/Index state") over
behavioral_baselines/security/SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md
(§17–§28, §33 SEC-017…SEC-028) and its executable benchmark
(behavioral_baselines/security/security_benchmark_v1.json, cases S41–S49 and
S55–S57).

This module is the package's *vocabulary*: the scope words, the deletion
request and its outcome records, the honest state of the external-disclosure
judgement, and the app.db table sets the sweep is defined over. The walks and
the derivations are elc/deletion/plan.py's (pure), the statements are
elc/deletion/store.py's, and the authority face is
elc/deletion/controller.py's.

---------------------------------------------------------------------------
The scope vocabulary — canonical text first, and the two words that are not
---------------------------------------------------------------------------

Five of the seven ``DeletionScope`` words are literal tokens in the contract's
own text, each in the section that defines what the scope deletes:

    LEARNING_TARGET       §20 "### LEARNING_TARGET"          (line 739)
    ALL_LEARNING_HISTORY  §20 "### ALL_LEARNING_HISTORY"     (line 753)
    RELATIONSHIP_PAIR     §21 "`RELATIONSHIP_PAIR(Persona P)`" (line 770)
    PERSONA_PACKAGE       §22 "底层 `PERSONA_PACKAGE` scope"   (line 790)
    ALL_USER_DATA         §23 "## ALL_USER_DATA"             (line 806)

The other two are **not** contract tokens, and the difference is stated rather
than flattened:

- ``CONVERSATION`` names §19's *section* ("## 19. Conversation 删除", line
  698). The section is quoted — its deletion list is what this package's
  conversation walk implements — but the uppercase scope token is the
  benchmark's (``security_benchmark_v1.json`` case S41 carries
  ``request.scope = "CONVERSATION"``);
- ``PROFILE_FIELD`` is the benchmark's alone (case S44's ``request.scope``
  with a ``field_key``). The contract never names a standalone profile-field
  scope: §19 deletes a profile fact as part of a conversation's provenance
  closure, and nothing else does.

Both are therefore registered as **derived** words (benchmark-sourced) rather
than presented as quotations, and the same distinction is repeated in
migration 0014's header and in this package's tests.

---------------------------------------------------------------------------
The app.db table sets — what ALL_USER_DATA sweeps, and what it must not
---------------------------------------------------------------------------

§23 deletes "all user canonical records / all user-derived records / all
secrets / all private config / all pending actions/jobs / all indexes" and
keeps "application binaries / global Curriculum / public/global Content
Library", adding that "可保留一个最小、无 plaintext 的 deletion-protection
ledger". SEC-025 restates the keep rule as an invariant ("ALL_USER_DATA never
deletes global Curriculum/Content").

Three sets express that in this repository, and
:data:`RETAINED_TABLES`, :data:`SWEPT_TABLES` and :data:`GLOBAL_CONTENT_TABLES`
are **pinned against the real database** by tests/deletion (every table of a
freshly migrated app.db is in exactly one of them), so a later migration
cannot add a table the sweep would silently walk past:

- :data:`SWEPT_TABLES` — every app.db table that holds user state, in
  **children-before-parents** order (the order the foreign keys require; the
  graph is acyclic apart from two self-references, and the store deletes in
  this order inside one transaction);
- :data:`RETAINED_TABLES` — the four tables ALL_USER_DATA keeps:
  ``schema_meta`` and ``schema_migrations`` (the schema stamp and the applied
  lineage — infrastructure, not user data), ``runtime_epoch`` (the restart
  fence; deleting it would reset the ownership boundary and is exactly the
  resurrection §24 guards against) and ``deletion_tombstone`` (§23's
  "deletion-protection ledger");
- :data:`GLOBAL_CONTENT_TABLES` — the global Curriculum / Content Library.
  **It is empty in app.db on purpose**, and that emptiness is the honest
  statement of this cut: V1 keeps global curriculum and content in
  ``content.db``, a separate read-only build artifact opened by a different
  connection (elc/content/store.py). SEC-025 is therefore enforced twice —
  structurally (no app.db table is a global content table, and the sweep is a
  closed list) and behaviourally (the deletion store opens no other database;
  a probe asserts content.db is byte-identical after an ALL_USER_DATA sweep).

Anything else — a table in app.db that is in none of the three sets — is an
**error**, not a table to skip: :func:`elc.deletion.plan.assert_known_tables`
refuses it, so a future migration that adds a table without deciding its
disposition fails the sweep loudly instead of leaking user rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from elc.platform.types import (
    ConversationId,
    PersonaId,
    TargetId,
)

__all__ = [
    "ALL_USER_DATA_SWEPT_TABLES",
    "CONVERSATION_SWEPT_TABLES",
    "DELETION_POLICY_VERSION",
    "GLOBAL_CONTENT_TABLES",
    "LEARNING_HISTORY_SWEPT_TABLES",
    "LEARNING_TARGET_SWEPT_TABLES",
    "PERSONA_PACKAGE_SWEPT_TABLES",
    "PROFILE_FIELD_SWEPT_TABLES",
    "RELATIONSHIP_PAIR_SWEPT_TABLES",
    "RETAINED_TABLES",
    "SWEPT_TABLES",
    "DeletionExecution",
    "DeletionOutcome",
    "DeletionRequest",
    "DeletionScope",
    "EpisodeRebuildKey",
    "ExternalAction",
    "ExternalDeletionPlan",
    "ExternalDisclosure",
    "ExternalDisclosureStatus",
    "RebuildAttempt",
    "RemoteRevocation",
    "TableTally",
    "TargetKey",
    "TombstoneRecord",
]


class DeletionScope(StrEnum):
    """The seven deletion scopes (five quoted from §20–§23, two derived).

    The words are frozen by migration 0014's ``deletion_scope`` CHECK, so a
    new scope is a canonical revision rather than an implementation choice
    (the 0013 ``constraint_type`` precedent for a pinned list). See the module
    docstring for which words are contract text and which are the benchmark's.
    """

    CONVERSATION = "CONVERSATION"
    LEARNING_TARGET = "LEARNING_TARGET"
    ALL_LEARNING_HISTORY = "ALL_LEARNING_HISTORY"
    RELATIONSHIP_PAIR = "RELATIONSHIP_PAIR"
    PROFILE_FIELD = "PROFILE_FIELD"
    PERSONA_PACKAGE = "PERSONA_PACKAGE"
    ALL_USER_DATA = "ALL_USER_DATA"


#: The version of the deletion semantics a tombstone records (§24
#: "deletion_scope/version"). §24 requires a version and pins no vocabulary
#: for it, so the spelling is a **derived judgement**: a single policy word
#: that moves when this package's scope surfaces move. It is *not* the
#: schema version — a schema bump that changes no deletion rule must not
#: re-version the ledger.
DELETION_POLICY_VERSION = "deletion-policy-v1"


# ---------------------------------------------------------------------------
# Table sets (see the module docstring)
# ---------------------------------------------------------------------------

#: Every app.db table that holds user state, parents last. The order is the
#: one the foreign keys require and the store deletes in.
SWEPT_TABLES: tuple[str, ...] = (
    "active_teaching_lock",
    "assistant_turn",
    "disclosure_policy",
    "episode",
    "evidence_claim",
    "evidence_commit",
    "evidence_watermark",
    "expression_need",
    "gate_execution_status",
    "goal_portfolio",
    "interrupt_request",
    "learner_self_report",
    "learner_target_state",
    "planner_constraint",
    "projection_job",
    "provider_attempt",
    "relationship_memory",
    "review_event",
    "session_focus",
    "teaching_evidence_proposal",
    "teaching_policy",
    "user_profile",
    "analysis_artifact",
    "attempt_evaluation_record",
    "evidence_group",
    "generation_action_intent",
    "learning_opportunity_record",
    "schedule_item",
    "attempt_record",
    "teaching_moment",
    "user_turn",
    "gate_decision",
    "planner_decision",
    "planner_evaluation",
    "planner_execution_status",
    "runtime_decision_outcome",
    "decision_cycle",
    "turn_record",
    "input_envelope",
    "conversation",
    # P8-3's PlanningLedger (migration 0016). Appended, and children first
    # inside the group: the event log references the per-key row, the
    # obligations reference nothing (they are debts, not a row's children —
    # migration 0016's header states the argument), so the order is
    # log → row → obligations. The three are leaves of every other table's
    # graph, which is why they can sit at the end of the sweep.
    "planning_ledger_event",
    "planning_ledger",
    "coverage_obligation",
)

#: The subset ALL_USER_DATA walks — §23's "all user canonical records / all
#: user-derived records / all private config / all pending actions/jobs".
ALL_USER_DATA_SWEPT_TABLES: tuple[str, ...] = SWEPT_TABLES

#: What ALL_USER_DATA keeps (see the module docstring for why each one).
RETAINED_TABLES: tuple[str, ...] = (
    "deletion_tombstone",
    "runtime_epoch",
    "schema_meta",
    "schema_migrations",
)

#: The global Curriculum / Content Library. Empty in app.db — they live in
#: content.db, which this package never opens. See the module docstring.
GLOBAL_CONTENT_TABLES: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Per-scope surfaces — the tables each scope removes rows from
# ---------------------------------------------------------------------------
#
# These are **declarations of scope**, not of mechanism: the store decides
# *which rows* of each table a scope removes (elc/deletion/store.py's
# predicates), and these tuples say which tables can be touched at all, so
# a test can hold the surfaces against the module's own SQL. A table absent
# from a scope's surface is a table that scope must not write — which is
# what makes SEC-026 ("learning deletion does not silently delete unrelated
# Relationship data") and SEC-027 (its converse) checkable rather than
# promised: ``relationship_memory`` is not in
# :data:`LEARNING_HISTORY_SWEPT_TABLES`, and the learning tables are not in
# :data:`RELATIONSHIP_PAIR_SWEPT_TABLES`.

#: §19's conversation closure: the conversation's own chain plus the rows
#: solely derived from its turns. Everything here is reached through the
#: conversation's turn ids, its moments or its evidence groups. Since P8-0
#: that includes the four §14 planner records: they hang off the
#: conversation's own decision cycles and turns (and their foreign keys make
#: "delete the cycle, keep its decision" a refusal, not a choice).
#:
#: Listed children-first (the same property :data:`SWEPT_TABLES` carries), so
#: the declaration is also a legal order for the rows it names — a pin holds
#: it against the real schema's foreign keys.
CONVERSATION_SWEPT_TABLES: tuple[str, ...] = (
    "active_teaching_lock",
    "assistant_turn",
    "episode",
    "evidence_claim",
    "evidence_commit",
    "expression_need",
    "gate_execution_status",
    "interrupt_request",
    "learner_self_report",
    "planner_constraint",
    "projection_job",
    "provider_attempt",
    "relationship_memory",
    "review_event",
    "session_focus",
    "teaching_evidence_proposal",
    "analysis_artifact",
    "attempt_evaluation_record",
    "evidence_group",
    "generation_action_intent",
    "learning_opportunity_record",
    "attempt_record",
    "teaching_moment",
    "user_turn",
    "gate_decision",
    "planner_decision",
    "planner_evaluation",
    "planner_execution_status",
    "runtime_decision_outcome",
    "decision_cycle",
    "turn_record",
    "input_envelope",
    "conversation",
)

#: §20 LEARNING_TARGET: the named target's evidence, its materialized state,
#: its review events, its schedule rows and its self-reports — plus, since
#: P8-3, the ledger history the contract names for exactly this scope
#: ("related PlanningLedger history", line 747): the target's event log, its
#: per-key row and its TARGET-scoped obligations. Deliberately **not** here:
#: every conversation/turn table (the transcript survives) and every
#: relationship table.
LEARNING_TARGET_SWEPT_TABLES: tuple[str, ...] = (
    "evidence_claim",
    "learner_self_report",
    "learner_target_state",
    "review_event",
    "schedule_item",
    # The ledger half, in the global order (log → row → obligations; SWEPT_
    # TABLES holds the same three in the same relative order). The store scopes
    # the rows by the declared key face, so a *family* row that happens to spell
    # this target's id is not swept by the target's deletion.
    "planning_ledger_event",
    "planning_ledger",
    "coverage_obligation",
)

#: §20 ALL_LEARNING_HISTORY: the learning side entire, plus the teaching
#: attempts and decision cycles that exist to produce it — and, since P8-0,
#: the four §14 planner records that hang off those cycles and turns.
#: Deliberately not here: conversation / transcript, relationship, profile,
#: goals and the
#: user's own settings (planner constraints, policy, focus) — §20 keeps
#: "conversation / relationship / profile / goals", and §18.1's
#: TRUSTED_AUTHORITY makes a typed user setting the user's own statement
#: rather than derived learning state.
#:
#: Children-first, in :data:`SWEPT_TABLES` order — so this walk is a
#: subsequence of the whole-database one and both order pins hold. The
#: dependency that makes the order matter most is ``teaching_moment`` before
#: ``gate_decision`` (a moment names the decision that authorized it) and
#: ``evidence_commit`` before ``analysis_artifact`` (a commit names the
#: analysis it came from); reversing either makes the sweep fail with an
#: opaque ``FOREIGN KEY constraint failed``, which is how the probe suite
#: found the first draft of this tuple.
LEARNING_HISTORY_SWEPT_TABLES: tuple[str, ...] = (
    "evidence_claim",
    "evidence_commit",
    "evidence_watermark",
    "expression_need",
    "gate_execution_status",
    "learner_self_report",
    "learner_target_state",
    "projection_job",
    "provider_attempt",
    "review_event",
    "teaching_evidence_proposal",
    "analysis_artifact",
    "attempt_evaluation_record",
    "evidence_group",
    "generation_action_intent",
    "learning_opportunity_record",
    "schedule_item",
    "attempt_record",
    "teaching_moment",
    "gate_decision",
    "planner_decision",
    "planner_evaluation",
    "planner_execution_status",
    "runtime_decision_outcome",
    "decision_cycle",
    # P8-3 — the contract's LEARNING_PRIVATE list names "PlanningLedger user
    # history" (line 87), so this walk carries all three of migration 0016's
    # tables; they are the last group because nothing references them.
    "planning_ledger_event",
    "planning_ledger",
    "coverage_obligation",
)

#: §21 RELATIONSHIP_PAIR: the pair's memories, plus the CP4 job row that
#: releases the pair's episode projections for re-derivation. Everything §21
#: lists as "不自动删除" is absent from this tuple on purpose — Learning
#: Evidence, Conversation transcript and the CharacterPackage — and so is
#: ``episode`` itself: the projection is *invalidated* (its deterministic
#: job row is released) rather than removed, so a failed rebuild leaves the
#: previous row standing instead of a hole.
RELATIONSHIP_PAIR_SWEPT_TABLES: tuple[str, ...] = (
    "projection_job",
    "relationship_memory",
)

#: The benchmark's PROFILE_FIELD scope (S44) rewrites one profile row and
#: nothing else.
PROFILE_FIELD_SWEPT_TABLES: tuple[str, ...] = ("user_profile",)

#: §22 PERSONA_PACKAGE is the **empty surface** in V1, and that emptiness is
#: the deliverable: the scope deletes a Persona definition/package, and V1's
#: app.db has no persona definition table at all (the persona package is a
#: runtime/authoring asset, elc/persona/types.py). Declaring the surface
#: empty — rather than reaching for the nearest user table — is what stops
#: §22's "不得暗中扩大删除范围" from being a promise: a test asserts that a
#: PERSONA_PACKAGE request removes no row anywhere and writes no tombstone
#: beyond the scope's own criterion record.
PERSONA_PACKAGE_SWEPT_TABLES: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# The request, and what came back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeletionRequest:
    """One deletion request: the scope word plus the keys that scope needs.

    The optional keys are not interchangeable — each scope reads its own and
    refuses a request that carries the wrong one (a ``LEARNING_TARGET``
    request with no ``target_id`` is a ``VALIDATION_FAILED``, never a
    vacuum). ``deleted_at`` is the caller's instant when the caller declares
    one and the writing store's clock otherwise (§24 pins the column and no
    format).
    """

    scope: DeletionScope
    conversation_id: ConversationId | None = None
    target_id: TargetId | None = None
    #: ``None`` on a LEARNING_TARGET request means "every target_type for
    #: this target_id" — the benchmark's own shape (S43/S48 carry only
    #: ``target_id``), declared here rather than assumed at the call site.
    target_type: str | None = None
    persona_id: PersonaId | None = None
    field_key: str | None = None
    deleted_at: str = ""


@dataclass(frozen=True)
class TargetKey:
    """A ``(target_type, target_id, evidence_modality)`` key.

    The key a materialized LearnerState row and a schedule row are stored
    under (docs/DATA_MODEL.md §11 / §5.2): a deletion collects the keys its
    removal affected and hands them back, so the rebuild runs over exactly
    the keys that lost evidence and no others.
    """

    target_type: str
    target_id: str
    evidence_modality: str


@dataclass(frozen=True)
class EpisodeRebuildKey:
    """One conversation whose episode projection must be re-derived.

    ``anchor_turn_id`` is the conversation's latest COMPLETED turn — the turn
    whose deterministic CP4 job id will be re-minted for the EPISODE type. The
    episode executor rebuilds from the whole conversation window, so exactly
    one job (per conversation) is what the rebuild needs.
    """

    conversation_id: str
    anchor_turn_id: str


@dataclass(frozen=True)
class TableTally:
    """How many rows one table lost. Zero tallies are not reported."""

    table: str
    removed: int


@dataclass(frozen=True)
class TombstoneRecord:
    """One durable §24 ledger row (the shape migration 0014 stores).

    ``entity_kind`` is the durable table the entity was removed from, or one
    of the non-table kinds this package declares (``PROFILE_FIELD`` for a
    field key). ``entity_hash`` is the one-way digest elc/deletion/plan.py
    derives; the record carries **no field for deleted content** — §24's
    "不得保存被删除正文" is structural here, not a convention.
    """

    tombstone_id: str
    entity_kind: str
    entity_hash: str
    deleted_at: str
    deletion_scope: DeletionScope
    scope_version: str


@dataclass(frozen=True)
class DeletionExecution:
    """What the durable deletion actually removed — the store's own report.

    Every count is read back from the transaction, never predicted:
    ``tallies`` holds one entry per table that lost at least one row, in
    sweep order, and ``affected_targets`` names the materialized-state and
    schedule keys the rebuild must revisit (collected *inside* the same
    transaction, before the evidence they were derived from disappears).
    """

    scope: DeletionScope
    tallies: tuple[TableTally, ...] = ()
    #: The instant the deletion ran at: the caller's when it declared one,
    #: the store's own clock otherwise. Carried on the execution because the
    #: rebuilds that follow run *at* it — the controller uses it as their
    #: ``as_of``, so a deterministic recomputation stays deterministic.
    deleted_at: str = ""
    tombstoned: int = 0
    #: SEC-028: unfinished projection jobs (PENDING / FAILED_RETRYABLE)
    #: removed in this transaction.
    cancelled_projection_jobs: int = 0
    #: SEC-021: generation actions removed before ever being transmitted.
    cancelled_provider_actions: int = 0
    #: SEC-022: actions that *were* transmitted and are gone with their
    #: conversation — reported so the caller can state the honest external
    #: position instead of claiming a remote revocation.
    sent_provider_actions: int = 0
    #: Provenance legs cleared rather than deleted (a surviving user setting
    #: whose originating turn is gone).
    cleared_provenance_legs: int = 0
    affected_targets: tuple[TargetKey, ...] = ()
    #: The conversations whose episode projection must be re-derived: their
    #: own projection was removed, or a relationship source their
    #: ``open_threads`` were built from moved.
    affected_episodes: tuple[EpisodeRebuildKey, ...] = ()
    #: Free-text, machine-readable notes: the substitutions and gaps this
    #: run carries (empty for an ordinary in-scope deletion).
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RebuildAttempt:
    """One rebuild the deletion performed through an existing face.

    ``kind`` is the face's own name (``LEARNER_STATE`` / ``SCHEDULE_ITEM`` /
    ``EPISODE``), ``key`` the key it ran for, and ``ok`` the face's verdict —
    a rebuild failure is reported, never swallowed, because §18 lists the
    rebuild among deletion's minimum semantics and a silent failure would
    leave a partially-supported view standing.
    """

    kind: str
    key: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DeletionOutcome:
    """The whole result: the durable execution plus the rebuilds it drove."""

    scope: DeletionScope
    execution: DeletionExecution
    rebuilds: tuple[RebuildAttempt, ...] = ()
    notes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# External disclosure / remote revocation (S55–S57; §25, §26, SEC-021/022)
# ---------------------------------------------------------------------------

#: The delivery states the contract names for a disclosure that has left the
#: application. §25 speaks of "NOT_SENT / QUEUED" and §26 of data that has
#: been sent; the benchmark's three cases use exactly ``NOT_SENT`` and
#: ``SENT``, and the two partial delivery words are the ones §26's
#: "sent_at / server delivery status" receipt metadata would carry. The list
#: is the reference implementation's
#: (behavioral_baselines/security/security_reference_v1.py
#: ``plan_external_disclosure_deletion``), quoted rather than invented.
class ExternalDisclosureStatus(StrEnum):
    NOT_SENT = "NOT_SENT"
    QUEUED = "QUEUED"
    SENT = "SENT"
    SENT_COMPLETE = "SENT_COMPLETE"
    SENT_PARTIAL = "SENT_PARTIAL"


class ExternalAction(StrEnum):
    """What the app will do *outside* its own boundary (§26).

    Two words, because this is a judgement and not a RPC: anything the app
    cannot perform must say ``NONE`` while the honest revocation state is
    reported separately. V1 performs no remote call at all — S55–S57 are
    satisfied by the judgement, and the receipt that would carry the
    ``provider_request_id`` is V1's ``provider_attempt`` row.
    """

    NONE = "NONE"
    SCHEDULE_PROVIDER_DELETE = "SCHEDULE_PROVIDER_DELETE"


class RemoteRevocation(StrEnum):
    """The honest answer to "is the third party's copy gone?" (§26, SEC-022).

    ``CANNOT_BE_GUARANTEED_BY_APP`` is a first-class outcome, not a failure:
    §26 requires the app to say it rather than claim
    "已从所有模型服务商永久删除", and §32 lists a malicious third party's
    retention among the things this contract does not claim to defend
    against.
    """

    NOT_APPLICABLE = "NOT_APPLICABLE"
    CANNOT_BE_GUARANTEED_BY_APP = "CANNOT_BE_GUARANTEED_BY_APP"
    PENDING_PROVIDER = "PENDING_PROVIDER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExternalDisclosure:
    """One disclosure whose source data is being deleted.

    ``provider_delete_supported`` and the identifier are the two facts §26
    requires before a provider delete may be scheduled ("Provider 支持可调用
    delete / 且有 request/object identifier"). The identifier's concrete
    carrier in V1 is ``provider_attempt.provider_request_id``; this record
    carries it opaquely because §26 names it "request/object identifier"
    without pinning a column.
    """

    status: ExternalDisclosureStatus
    provider_delete_supported: bool = False
    provider_request_identifier: str | None = None


@dataclass(frozen=True)
class ExternalDeletionPlan:
    """The two answers S55–S57 check, word for word.

    The reference implementation also returns a ``local_action``
    (``CANCEL`` / ``DELETE_LOCAL_RECEIPT_CONTENT_REFS`` / ``REVIEW``); it is
    deliberately **not** reproduced as a third word here, because in V1 that
    action *is* the deletion itself — an unsent action is removed by the
    executor (SEC-021) and a sent one's local receipt leaves with its
    conversation — and a third vocabulary whose values no shipped face
    consumes would be a word list kept for a comparator that does not exist.
    The mapping is registered here so the omission is a decision, not a gap.
    """

    external_action: ExternalAction
    remote_revocation: RemoteRevocation


#: Scope → the tables that scope may write, for the callers that want the
#: declaration without importing elc.deletion.plan.
SCOPE_SWEPT_TABLES: Mapping[DeletionScope, tuple[str, ...]] = {
    DeletionScope.CONVERSATION: CONVERSATION_SWEPT_TABLES,
    DeletionScope.LEARNING_TARGET: LEARNING_TARGET_SWEPT_TABLES,
    DeletionScope.ALL_LEARNING_HISTORY: LEARNING_HISTORY_SWEPT_TABLES,
    DeletionScope.RELATIONSHIP_PAIR: RELATIONSHIP_PAIR_SWEPT_TABLES,
    DeletionScope.PROFILE_FIELD: PROFILE_FIELD_SWEPT_TABLES,
    DeletionScope.PERSONA_PACKAGE: PERSONA_PACKAGE_SWEPT_TABLES,
    DeletionScope.ALL_USER_DATA: ALL_USER_DATA_SWEPT_TABLES,
}

#: The one kind word this package uses that is not a durable table name: a
#: PROFILE_FIELD deletion removes a *field*, and §5.1's ``profile_facts`` is
#: a JSON array inside one row, so there is no row id to name. See
#: elc/deletion/store.py for the fail-closed rule that makes this necessary.
PROFILE_FIELD_ENTITY_KIND = "PROFILE_FIELD"
