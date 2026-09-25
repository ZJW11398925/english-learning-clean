"""The first composition root (prep-1) — one real process's assembly.

Phase 10 registered gap 7 as the honesty item this cut closes: every store and
runtime face existed and was tested, but **nothing in ``src/`` ever constructed
them** — no place called ``open_runtime_epoch`` and no place built a
``ConversationCoordinator``, so no real process could run a turn or recover
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
GenerationContext (``None`` keeps the P1 assembly).

What this host does **not** assemble, named rather than left implied (prep-1
review F5): no teaching / learning / planner / scheduler / deletion /
user_config / curriculum / projection / silent-evidence port is built, so the
coordinator's optional params for those domains stay ``None``. The consequence
is visible, not hidden: without the teaching port the startup plan carries
TURN items only and closes nothing (the coordinator's
``run_startup_recovery`` docstring states that shape), and the automatic
teaching leg has no wiring at all. ``open_host`` is the production entry point
for the ordinary turn this cut makes real; an assembly that wants those legs
must inject them (the same shape the phase suites use).

``secrets`` is held, never read: the V1 secret seam belongs to the provider
(RA §24.3 — resolve at send time), and the key never enters app.db, this module
or any log. It is kept here so the process has one place that knows which
source it opened with; nothing in this module calls ``resolve``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from elc.conversation import SqliteConversationStore
from elc.persona.provider import PersonaProvider
from elc.persona.runtime import PersonaRuntime
from elc.persona.types import CharacterPackageRecord
from elc.platform.db.connection import DEFAULT_MIGRATIONS_DIR, connect
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence, open_runtime_epoch
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.db.migrations import MigrationError, apply_migrations
from elc.platform.secrets import SecretSource
from elc.platform.types import (
    ConversationId,
    PersonaId,
    Result,
    RuntimeEpoch,
    SceneId,
    UserId,
)
from elc.runtime.controller import ConversationCoordinator, StartupRecoveryOutcome
from elc.runtime.guarded_stream import StreamTransportFactory
from elc.runtime.lease import ConversationCoordinatorLease

__all__ = ["Host", "open_host"]


@dataclass(frozen=True)
class Host:
    """One process's assembled runtime: stores + coordinator + epoch.

    Every field is a face this cut built or opened, exposed so the caller
    reaches the same objects the coordinator holds instead of assembling a
    second copy of them.
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
        """

        return self.conversations.open_conversation(
            conversation_id,
            user_id if user_id is not None else UserId("local-user"),
            persona_id,
            scene_id,
        )

    def startup_recovery(self) -> Result[StartupRecoveryOutcome]:
        """RA §22's startup pass — the delegate that closes gap 7.

        Called once, after this epoch was adopted and before the first turn
        (the coordinator's docstring fixes both that order and its
        read-then-write shape).
        """

        return self.coordinator.run_startup_recovery()

    def close(self) -> None:
        """Close the app.db connection. No transaction is open at this point."""

        self.db.close()


def open_host(
    app_db_path: str | Path,
    *,
    provider: PersonaProvider,
    secrets: SecretSource | None = None,
    stream_transport: StreamTransportFactory | None = None,
    character_package: CharacterPackageRecord | None = None,
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
) -> Host:
    """Assemble the whole loop over one app.db (see the module docstring).

    Raises what the infrastructure raises (``sqlite3.Error`` /
    ``MigrationError``) after closing the connection it opened, so a failed
    open leaves no half-open handle behind.
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
        coordinator = ConversationCoordinator(
            lease=lease,
            conversation_commands=conversations,
            conversation_queries=conversations,
            persona=persona,
            generation_actions=generation,
            decision_cycles=decision_cycles,
            delivery_records=deliveries,
            stream_transport=stream_transport,
            character_package=character_package,
        )
    except (sqlite3.Error, MigrationError):
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
    )
