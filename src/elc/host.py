"""The composition root — one real process's assembly, in two declared tiers.

Phase 10 registered gap 7 as the honesty item the first tier closes: every
store and runtime face existed and was tested, but **nothing in ``src/`` ever
constructed them** — no place called ``open_runtime_epoch`` and no place built
a ``ConversationCoordinator``, so no real process could run a turn or recover
one. :func:`open_host` is that place, and it is deliberately the only one:

- it runs the migrations (idempotent, one short transaction each), opens this
  process's ``runtime_epoch`` (the restart fence, RA §24), builds the real
  stores, injects the provider into a ``PersonaRuntime`` and adopts the epoch
  on the new coordinator's lease — every guarded write is fenced from turn one;
- the stores are the **production** ones, injected separately: generation and
  decision cycles are two real stores, never the test suite's assembly subclass
  (nothing here reaches into ``tests/``);
- it opens no long transaction and holds none afterwards — the only
  transactions are the migration runner's own and the epoch insert, and every
  later write goes through the stores' short units;
- it is **not** a second live entry point: it assembles and does not loop.
  ``startup_recovery()`` and ``open_conversation()`` are thin delegates to
  faces that already own those semantics; the turn loop lives in the caller
  (``elc.cli`` is the V1 caller).

Optional injections pass through unchanged: ``stream_transport`` reaches the
coordinator's client boundary (``None`` keeps V1's in-process single-chunk
default) and ``character_package`` reaches the ordinary turn's
GenerationContext. cs-1 gives the package a production default: the fixed
penpal (:mod:`elc.persona.penpal`) — ``open_host`` injects her card unless
the caller passes a different package, and ``character_package=None``
restores the bare prep-1 shape (the degradation arm of the ``[persona]``
section). The shipped entry faces (``elc.cli`` / ``elc.web``) bind the
matching ``persona_id`` onto the conversations they open, so the card, the
conversation row and the Persona×User pair the projections write for are
one character.

**Two assembly tiers, declared rather than implied (D-5):**

- ``content_db_path=None`` (the default) is the prep-1 tier, field for field:
  four stores, the persona runtime, the coordinator, and every optional leg
  the coordinator takes stays ``None``. No teaching / learning / planner /
  scheduler / deletion / user_config / curriculum / projection /
  silent-evidence port is built, so the consequences prep-1 registered stay
  visible, not hidden: the startup plan carries TURN items only and closes
  nothing, and the automatic teaching leg has no wiring at all.
- a ``content_db_path`` turns on the **full chain**: the user-config,
  learning, teaching, scheduler, planner, ledger, projection, relationship and
  episode stores join the four prep-1 stores on the same app.db connection;
  the built artifact is opened **read-only through exactly one**
  ``ContentStore`` connection (the curriculum adapter, the target provider and
  the supply reader are faces over it or over the path — each closes only what
  it opened itself); and the coordinator receives every optional leg it has —
  ``learning`` (the store's analysis face) *and* ``learning_controller`` (the
  controller, the double injection), ``teaching``, ``targets``,
  ``projections`` (both CP4 executors, the complete
  :data:`SUPPORTED_PROJECTION_TYPES` set — the runtime refuses an incomplete
  one at construction), ``persona_views``, ``silent_evidence``,
  ``automatic_teaching`` and ``constraint_views``. D-6-a adds the detection
  dispatch face to the automatic wiring (the CURRENT_USER_ERROR producer over
  the process-level pilot registry — ``elc.detection.dispatch``), so the
  full chain turns a user turn's error text into a teaching opportunity the
  whole gate chain still has to authorize.

**The zero-open boundary.** ``rollout_stage`` passes through to the automatic
wiring untouched and defaults to ``None``: the wiring is assembled, but
``stage_allows_automatic(None)`` is False, so no automatic teaching can run in
a host that did not declare a stage. This module never declares one — the
stage is the operator's decision (and D-6's Study-first run needs the user's
explicit consent) — so ``open_host`` has no argument or default that implies
the permissive reading.

**Three assembly facts, registered where the reader trips over them:**

1. ``TeachingController(store, policy=_UserConfigPolicySource(...))`` — the
   §5.1 policy source is the user-config controller wrapped in this module's
   thin adapter (D-5R): the controller class itself carries no ``user_id``
   attribute for the ``SessionBudgetPolicySource`` protocol to read, so the
   adapter adds exactly that (the Local V1 user) and forwards
   ``get_teaching_policy`` untouched — "shaped exactly like the real
   controller so a caller's adapter is a forward, not a translation"
   (``elc.teaching.budget``). With the leg wired, the full chain's
   session-budget view reads for real (``policy_version=None`` until a
   policy row is written — "no policy is configured" is the honest answer,
   distinct from "no policy read face was wired", which the full chain no
   longer is); and the automatic OPEN **fail-closed** on an unreadable
   budget (:data:`elc.runtime.automatic_teaching.
   AUTO_SESSION_BUDGET_UNREADABLE`) — D-5R closed the p10-3 fail-open
   adjudication's budget half at the authorization posture, so this
   assembly can no longer produce the world where the view is unreadable
   and the OPEN proceeds anyway (external review round 5, EXT-D5-01).
2. ``LOCAL_V1_USER_ID`` — Local V1 has exactly one user, and the only user
   identity the repository names is the learning store's adjudicated scope
   word (``LOCAL_V1_DEFAULT_USER_SCOPE``); the full chain binds it as the
   ``UserId`` every user-keyed leg reads (the wiring, the policy adapter,
   the persona views and both projection executors). No user value is
   invented anywhere in this module.
3. ``content_rollout_gate()`` reads **artifact facts**, not live ones: the
   four-row answer is the corpus gate over the built ``content.db`` this host
   was opened with (the pilot build answers a fourth-row GO 12 usable / 40
   blocked; the default build answers HOLD 0 / 52). It is the content leg's
   answer only — rollout HOLD has causes outside it (the stage declaration,
   the session-budget split, the opening adjudication) — and it manufactures
   neither verdict: an unreadable artifact or a missing content leg comes
   back as the ``Err`` it is. **D-5R**: the same artifact facts feed the
   automatic wiring's ``provenance`` mapping (read once at assembly; a
   failing read fails the open — fail-closed assembly), which is the
   runtime-level per-target half of the same fifth leg the gate reads at
   release level.

``secrets`` is held, never read: the V1 secret seam belongs to the provider
(RA §24.3 — resolve at send time), and the key never enters app.db, this module
or any log. It is kept here so the process has one place that knows which
source it opened with; nothing in this module calls ``resolve``.

``candidate_supply`` passes through to the automatic wiring verbatim
(``None`` — the production value — means the generators run over the ports).
It is the wiring field's own declared seam ("a caller that already holds this
cycle's supply — an acceptance test, or an orchestrator that generated
candidates earlier"), and the composition root forwards it rather than
forcing such a caller to rebuild the assembly it just asked for.

**p-2 adds the deletion leg (additive, both tiers).** A
:class:`~elc.deletion.controller.DeletionController` over a
:class:`~elc.deletion.store.SqliteDeletionStore` built on this host's own
connection and fence (the store opens no connection of its own, so
:meth:`Host.close` needs no new step): pure composition, zero runtime
semantics changed — the module is consumed, never modified. The three
rebuild legs are injected **from the faces this assembly already holds**:
the full-chain tier passes ``learning_controller`` / ``scheduler`` /
``projections`` (each structurally satisfies the controller's narrow
ports — ``rebuild_learner_state``, ``get_schedule_item`` +
``recompute_schedule_item``, ``ensure_projection_jobs`` + ``run_pending``);
the prep-1 tier passes ``None`` for all three, and the controller's own
declared behaviour is what that costs — each affected key reports its own
``ok=False`` :class:`~elc.deletion.types.RebuildAttempt` ("no … face is
wired into this controller") instead of the rebuild running, so a
prep-1-tier deletion leaves the derived LearnerState / schedule / episode
faces un-rebuilt and *says so* in the outcome rather than hiding it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from elc.content.store import ContentStore, ContentStoreError
from elc.conversation import SqliteConversationStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.deletion.controller import DeletionController
from elc.deletion.store import SqliteDeletionStore
from elc.detection import GLOBAL_REGISTRY
from elc.detection import pilot as pilot_detectors
from elc.detection.dispatch import RegistryDispatch
from elc.learning.analysis import LearningTurnAnalysis
from elc.learning.controller import LearningController
from elc.learning.silent_evidence import (
    ContentBackedSilentTargets,
    ContentBackedTargetSupply,
)
from elc.learning.store import LOCAL_V1_DEFAULT_USER_SCOPE, SqliteLearningStore
from elc.persona.penpal import PENPAL_CHARACTER_PACKAGE
from elc.persona.provider import PersonaProvider
from elc.persona.runtime import PersonaRuntime
from elc.persona.types import CharacterPackageRecord
from elc.planner.candidates import CandidateSupply
from elc.planner.ledger_store import SqliteLedgerStore
from elc.platform.db.connection import DEFAULT_MIGRATIONS_DIR, connect
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence, open_runtime_epoch
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.db.migrations import MigrationError, apply_migrations
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.secrets import SecretSource
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    PersonaId,
    Result,
    RuntimeEpoch,
    SceneId,
    UserId,
)
from elc.relationship.candidates import PatternCandidateProvider
from elc.relationship.controller import RelationshipController
from elc.relationship.episode_store import SqliteEpisodeStore
from elc.relationship.projection import (
    EpisodeProjectionExecutor,
    RelationshipProjectionExecutor,
)
from elc.relationship.recorder import RelationshipRecorder
from elc.relationship.store import SqliteRelationshipStore
from elc.runtime.automatic_teaching import (
    PlannerDecisionRecordStore,
    TeachingOpenAuthority,
)
from elc.runtime.automatic_turn import (
    AutomaticTurnWiring,
    CurriculumTurnFace,
    LearningTurnFace,
    LedgerTurnFace,
    SchedulerTurnFace,
    SupplyTurnFace,
    UserConfigTurnFace,
)
from elc.runtime.controller import ConversationCoordinator, StartupRecoveryOutcome
from elc.runtime.guarded_stream import StreamTransportFactory
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.persona_views import ControllerPersonaViews
from elc.runtime.projections import CP4ProjectionRuntime
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.teaching.controller import TeachingController
from elc.teaching.rollout import RolloutGateReport, RolloutStage, corpus_rollout_gate
from elc.teaching.store import SqliteTeachingStore
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore

__all__ = ["LOCAL_V1_USER_ID", "Host", "open_host"]

#: Local V1's one user (assembly fact 2): the learning store's adjudicated
#: single-scope word, bound as the ``UserId`` every user-keyed leg of the full
#: chain reads. The value lives in exactly one place — the learning store's
#: constant — and this module invents no other.
LOCAL_V1_USER_ID = UserId(LOCAL_V1_DEFAULT_USER_SCOPE)


class _UserConfigPolicySource:
    """The §5.1 half of the session-budget view, wired from the real
    user-config controller (D-5R, assembly fact 1).

    A thin adapter, exactly the two members the
    ``SessionBudgetPolicySource`` protocol names: the ``user_id`` the
    protocol must read off its source (assembly fact 2 — the controller
    class carries none of its own) and a verbatim forward of
    ``get_teaching_policy`` ("shaped exactly like the real controller so the
    adapter is a forward, not a translation" — ``elc.teaching.budget``). It
    adds nothing, defaults nothing and reads nothing on its own: an
    ``Ok(None)`` ("never written") and an ``Err`` (the read's own failure)
    reach the view untouched, which is what keeps "no policy is configured"
    and "the policy read failed" the two different facts the view refuses to
    conflate.
    """

    __slots__ = ("_controller", "_user_id")

    def __init__(
        self, controller: UserConfigController, user_id: UserId
    ) -> None:
        self._controller = controller
        self._user_id = user_id

    @property
    def user_id(self) -> UserId:
        """The user whose policy this source serves (the protocol's leg)."""

        return self._user_id

    def get_teaching_policy(self, user_id: UserId) -> Result[object]:
        """The §5.1 read, forwarded verbatim (never a translation)."""

        return cast("Result[object]", self._controller.get_teaching_policy(user_id))


@dataclass(frozen=True)
class Host:
    """One process's assembled runtime: stores + coordinator + epoch.

    Every field is a face this assembly built or opened, exposed so the caller
    reaches the same objects the coordinator holds instead of assembling a
    second copy of them. The prep-1 fields are always present; the full-chain
    fields are ``None`` unless the host was opened with a ``content_db_path``
    (the two tiers of the module docstring).
    """

    app_db_path: str
    db: sqlite3.Connection
    applied_migrations: tuple[str, ...]
    fence: RuntimeEpochFence
    epoch: RuntimeEpoch
    conversations: SqliteConversationStore
    generation: SqliteGenerationStore
    decision_cycles: SqliteDecisionCycleStore
    deliveries: SqliteDeliveryRecordStore
    persona: PersonaRuntime
    coordinator: ConversationCoordinator
    secrets: SecretSource | None = None
    # -- the full-chain tier (None in the prep-1 tier) ----------------------
    rollout_stage: RolloutStage | None = None
    user_id: UserId | None = None
    user_config: UserConfigController | None = None
    learning_store: SqliteLearningStore | None = None
    learning_controller: LearningController | None = None
    teaching: TeachingController | None = None
    content_store: ContentStore | None = None
    curriculum: CurriculumContentStore | None = None
    targets: ContentBackedTeachingTargetProvider | None = None
    supply: ContentBackedTargetSupply | None = None
    silent: ContentBackedSilentTargets | None = None
    scheduler: SchedulerController | None = None
    planner_store: SqlitePlannerRecordStore | None = None
    ledger: SqliteLedgerStore | None = None
    projections: CP4ProjectionRuntime | None = None
    persona_views: ControllerPersonaViews | None = None
    automatic: AutomaticTurnWiring | None = None
    #: p-2: always built (both tiers — the store needs only the shared
    #: connection and fence); the rebuild legs differ by tier (module
    #: docstring, "p-2 adds the deletion leg").
    deletion: DeletionController | None = None

    def open_conversation(
        self,
        conversation_id: ConversationId,
        *,
        user_id: UserId | None = None,
        persona_id: PersonaId | None = None,
        scene_id: SceneId | None = None,
    ) -> Result[ConversationId]:
        """Create the §3 conversation aggregate, idempotently.

        Delegation, not logic: the store is the authority (``user_id`` is in
        the signature but §3's Conversation column set has no column for it, so
        the store discards it).

        cs-1: when a ``persona_id`` is passed, a conversation that somehow
        exists without one (a row opened before the shipped faces carried a
        persona — the dogfood app.db's legacy NULL rows) is adopted: the
        store's ``bind_persona_if_unbound`` fills the empty persona, and a
        conversation that already carries one is never overwritten. The
        fill's own ``Err`` (``NOT_FOUND`` cannot happen after the open —
        the row exists) propagates instead of being swallowed.
        """

        opened = self.conversations.open_conversation(
            conversation_id,
            user_id if user_id is not None else UserId("local-user"),
            persona_id,
            scene_id,
        )
        if isinstance(opened, Err):
            return opened
        if persona_id is not None:
            bound = self.conversations.bind_persona_if_unbound(
                conversation_id, persona_id
            )
            if isinstance(bound, Err):
                return bound
        return opened

    def startup_recovery(self) -> Result[StartupRecoveryOutcome]:
        """RA §22's startup pass — the delegate that closes gap 7.

        Called once, after this epoch was adopted and before the first turn
        (the coordinator's docstring fixes both that order and its
        read-then-write shape).
        """

        return self.coordinator.run_startup_recovery()

    def content_rollout_gate(self) -> Result[RolloutGateReport]:
        """The corpus gate over the artifact this host was opened with.

        Assembly fact 3: the checker is
        :func:`elc.teaching.rollout.corpus_rollout_gate`, the table is this
        host's own curriculum face, and the provenance mapping is the
        artifact's own derived rows — the wiring the fifth leg named as the
        composition root's responsibility. A report is never manufactured:
        an unreadable provenance table comes back as the ``Err`` it is, and
        a host opened without a content leg (the prep-1 tier) answers
        ``DEPENDENCY_UNAVAILABLE`` rather than a verdict.
        """

        if self.curriculum is None or self.content_store is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "this host was opened without a content.db, so there"
                        " is no corpus to gate (reopen with content_db_path)"
                    ),
                )
            )
        provenance = self.content_store.provenance_levels()
        if isinstance(provenance, Err):
            return provenance
        return corpus_rollout_gate(
            self.curriculum, provenance=dict(provenance.value)
        )

    def close(self) -> None:
        """Close every connection this assembly opened.

        Order: the content legs first — each releases only what it opened
        itself (a path-constructed provider or supply closes its own lazy
        connection; a no-op when it never opened one) — then the artifact's
        own connection, then app.db. Every step is safe to repeat: the
        closes are no-ops once run, so a second :meth:`close` changes
        nothing.
        """

        if self.targets is not None:
            self.targets.close()
        if self.supply is not None:
            self.supply.close()
        if self.content_store is not None:
            self.content_store.close()
        self.db.close()


def open_host(
    app_db_path: str | Path,
    *,
    provider: PersonaProvider,
    secrets: SecretSource | None = None,
    stream_transport: StreamTransportFactory | None = None,
    character_package: CharacterPackageRecord | None = PENPAL_CHARACTER_PACKAGE,
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
    content_db_path: str | Path | None = None,
    rollout_stage: RolloutStage | None = None,
    candidate_supply: CandidateSupply | None = None,
) -> Host:
    """Assemble the whole loop over one app.db (see the module docstring).

    ``character_package`` defaults to the fixed penpal (cs-1) — the caller
    may pass another package, or an explicit ``None`` to restore the bare
    prep-1 shape. ``content_db_path=None`` assembles the prep-1 tier; a
    path assembles the full chain over that built artifact (read-only —
    the store refuses a writable connection by construction) and binds
    ``rollout_stage`` into the automatic wiring verbatim (``None`` keeps
    the fail-closed default; this function never substitutes a stage of
    its own). ``candidate_supply`` passes through to the wiring verbatim
    (``None`` — the production value — runs the generators over the ports;
    see the module docstring).

    D-5R: the full chain's session-budget leg is wired (assembly fact 1) and
    the wiring's ``provenance`` mapping is read from the artifact at assembly
    time — a failing provenance read **fails this open** (fail-closed
    assembly: a host that cannot say which targets are executably verified
    must not silently run as if none were, or all were).

    Raises what the infrastructure raises (``sqlite3.Error`` /
    ``MigrationError`` / ``ContentStoreError`` / ``OSError``) after closing
    the connections it opened, so a failed open leaves no half-open handle
    behind.
    """

    db = connect(app_db_path)
    try:
        applied = apply_migrations(db, migrations_dir)
        fence = open_runtime_epoch(db)
        conversations = SqliteConversationStore(db, fence)
        generation = SqliteGenerationStore(db, fence)
        decision_cycles = SqliteDecisionCycleStore(db, fence)
        deliveries = SqliteDeliveryRecordStore(db, fence)
        persona = PersonaRuntime(actions=generation, provider=provider)
        lease = ConversationCoordinatorLease()
        lease.adopt_epoch(RuntimeEpoch(fence.current))
        # -- the full-chain tier (module docstring, tier two) ----------------
        user_config: UserConfigController | None = None
        learning_store: SqliteLearningStore | None = None
        learning_controller: LearningController | None = None
        teaching: TeachingController | None = None
        content_store: ContentStore | None = None
        curriculum: CurriculumContentStore | None = None
        targets: ContentBackedTeachingTargetProvider | None = None
        supply: ContentBackedTargetSupply | None = None
        silent: ContentBackedSilentTargets | None = None
        scheduler: SchedulerController | None = None
        planner_store: SqlitePlannerRecordStore | None = None
        ledger: SqliteLedgerStore | None = None
        projections: CP4ProjectionRuntime | None = None
        persona_views: ControllerPersonaViews | None = None
        automatic: AutomaticTurnWiring | None = None
        if content_db_path is not None:
            content_path = Path(content_db_path)
            user_config = UserConfigController(SqliteUserConfigStore(db, fence))
            learning_store = SqliteLearningStore(db, fence)
            learning_controller = LearningController(learning_store)
            # D-5R (assembly fact 1): the policy leg is wired through the
            # thin adapter, so the full chain's budget view reads for real
            # and the automatic OPEN's budget refusal has a face that can
            # actually answer.
            teaching = TeachingController(
                SqliteTeachingStore(db, fence),
                policy=_UserConfigPolicySource(user_config, LOCAL_V1_USER_ID),
            )
            content_store = ContentStore(content_path)
            curriculum = CurriculumContentStore(content_store)
            # D-5R: the per-target verification face, read once at assembly.
            # An Err here is a build-time fact this host refuses to guess
            # around: fail-closed assembly, surfaced as ContentStoreError so
            # the except clause below releases the connections it opened.
            provenance_read = content_store.provenance_levels()
            if isinstance(provenance_read, Err):
                raise ContentStoreError(
                    "the content artifact's provenance table could not be"
                    f" read ({provenance_read.error.message}); refusing to"
                    " assemble a host whose automatic leg cannot tell a"
                    " verified target from an unverified one"
                )
            provenance = dict(provenance_read.value)
            targets = ContentBackedTeachingTargetProvider(content_path)
            supply = ContentBackedTargetSupply(content_path)
            silent = ContentBackedSilentTargets(supply)
            scheduler = SchedulerController(
                SqliteSchedulerStore(db, fence), learning=learning_controller
            )
            planner_store = SqlitePlannerRecordStore(db, fence)
            ledger = SqliteLedgerStore(db, fence)
            relationship = RelationshipController(
                SqliteRelationshipStore(db, fence)
            )
            episode_store = SqliteEpisodeStore(db, fence)
            recorder = RelationshipRecorder(conversations)
            # cs-1: the deterministic candidate producer replaces the
            # no-provider assembly (``candidates=None`` proposed nothing, so
            # the relationship memory stayed empty forever). The producer is
            # a source, not an authority — every candidate it hands back
            # still walks the Recorder's refusal order and the Controller's
            # validate / gate / dedupe faces (elc.relationship.candidates).
            relationship_executor = RelationshipProjectionExecutor(
                recorder=recorder,
                controller=relationship,
                conversation=conversations,
                user_id=LOCAL_V1_USER_ID,
                candidates=PatternCandidateProvider(),
            )
            episode_executor = EpisodeProjectionExecutor(
                store=episode_store,
                controller=relationship,
                conversation=conversations,
                user_id=LOCAL_V1_USER_ID,
            )
            projections = CP4ProjectionRuntime(
                store=SqliteProjectionStore(db, fence),
                executors=(relationship_executor, episode_executor),
                turns=conversations,
            )
            persona_views = ControllerPersonaViews(
                relationship=relationship,
                episodes=episode_store,
                user_config=user_config,
                user_id=LOCAL_V1_USER_ID,
            )
            # D-6-a: the detection dispatch face over the process-level pilot
            # registry — the same assembly form the build CLI uses
            # (``elc.content.build.main``): the pilot matchers are registered
            # into ``GLOBAL_REGISTRY`` once per process (the registry refuses
            # duplicate registrations, so the sentinel reuses an
            # already-assembled registry instead of re-registering), and the
            # wiring's CURRENT_USER_ERROR producer reads it. An artifact built
            # by this same process's registry and a host opened by it agree on
            # who is EXECUTABLY_VERIFIED, because they are the same detectors.
            if GLOBAL_REGISTRY.known_targets() != pilot_detectors.PILOT_ENTITIES:
                pilot_detectors.register_pilot(GLOBAL_REGISTRY)
            # The casts are the assembly point's one bridge: the automatic
            # bundle's protocols widen their parameters and answers to
            # ``object``/``Any`` so the bundle cannot reach what it does not
            # declare, which makes the concrete controllers structurally
            # satisfied at runtime (every phase suite assembles exactly these
            # objects) yet formally narrower than the protocol's widened
            # shapes. The bridge lives here, where the concrete and the
            # declared meet — the one further cast in this module is the
            # learning store's ``LearningTurnAnalysis`` bridge below.
            automatic = AutomaticTurnWiring(
                planner_store=cast("PlannerDecisionRecordStore", planner_store),
                teaching=cast("TeachingOpenAuthority", teaching),
                learning=cast("LearningTurnFace", learning_controller),
                scheduler=cast("SchedulerTurnFace", scheduler),
                user_config=cast("UserConfigTurnFace", user_config),
                curriculum=cast("CurriculumTurnFace", curriculum),
                supply=cast("SupplyTurnFace", supply),
                ledger=cast("LedgerTurnFace", ledger),
                session_budget=teaching,
                user_id=LOCAL_V1_USER_ID,
                candidate_supply=candidate_supply,
                rollout_stage=rollout_stage,
                provenance=provenance,
                error_detectors=RegistryDispatch(GLOBAL_REGISTRY),
            )
        # p-2: the deletion leg over the shared connection and fence, with
        # every rebuild face this assembly holds — built after the
        # full-chain block so the tier's controllers are the legs (all
        # three in the full chain, all None in the prep-1 tier; the
        # controller reports each missing rebuild as its own failed
        # RebuildAttempt, never a silent skip — module docstring).
        deletion = DeletionController(
            SqliteDeletionStore(db, fence),
            learning=learning_controller,
            scheduler=scheduler,
            projections=projections,
        )
        coordinator = ConversationCoordinator(
            lease=lease,
            conversation_commands=conversations,
            conversation_queries=conversations,
            persona=persona,
            generation_actions=generation,
            learning=cast(
                "LearningTurnAnalysis | None", learning_store
            ),
            character_package=character_package,
            decision_cycles=decision_cycles,
            learning_controller=learning_controller,
            teaching=teaching,
            targets=targets,
            projections=projections,
            persona_views=persona_views,
            silent_evidence=silent,
            automatic_teaching=automatic,
            delivery_records=deliveries,
            stream_transport=stream_transport,
            constraint_views=user_config,
        )
    except (sqlite3.Error, MigrationError, ContentStoreError, OSError):
        db.close()
        raise
    return Host(
        app_db_path=str(app_db_path),
        db=db,
        applied_migrations=tuple(applied),
        fence=fence,
        epoch=RuntimeEpoch(fence.current),
        conversations=conversations,
        generation=generation,
        decision_cycles=decision_cycles,
        deliveries=deliveries,
        persona=persona,
        coordinator=coordinator,
        secrets=secrets,
        rollout_stage=rollout_stage,
        user_id=LOCAL_V1_USER_ID if content_db_path is not None else None,
        user_config=user_config,
        learning_store=learning_store,
        learning_controller=learning_controller,
        teaching=teaching,
        content_store=content_store,
        curriculum=curriculum,
        targets=targets,
        supply=supply,
        silent=silent,
        scheduler=scheduler,
        planner_store=planner_store,
        ledger=ledger,
        projections=projections,
        persona_views=persona_views,
        automatic=automatic,
        deletion=deletion,
    )
