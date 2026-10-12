"""The Narrative V3 SEGMENT COMMIT — NCP-3's one short atomic group
(V3-5, TASK-OPI-be7b094f…34 / the opening ruling DEC-OPI-be7b094f…32;
the V3-5R corrections TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11) —
plus the two faces the cut's hard doors freeze: the explicit story-time
lineage read and the decoupled reader-exposure record.

**The commit transaction** (:func:`commit_segment`): one
``BEGIN IMMEDIATE`` … ``COMMIT`` lands, all or nothing (N-R-INV-004):

1. ``narrative_passage`` — the segment's prose (the CANON face's
   immutable row; N-INV-003);
2. ``world_event`` — the segment's non-user fact row, settled through
   the world store's own one-truth helper
   (:func:`elc.world.store._settle_effects_in_transaction`) so its
   ``world_state_fact`` CURRENT/SUPERSEDED law is spelled once;
3. ``segment_commit`` — the explicit lineage row (the review's **item
   1**: V3 events' story time is attributed *here*, never inferred from
   an opaque event-id's naming; ``story_time_of`` is the read path),
   carrying the segment's persisted ``is_last_segment`` (V3-5R; the
   review's MEDIUM-HIGH — see the terminality paragraph below);
4. ``world.current_tick`` advanced by the segment's ``duration_ticks``
   (the only sanctioned mover — N-INV-007 / N-R-INV-005);
5. ``world_scene``'s actual span — the scene's **only** span writer
   (V3-5R, TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11's HIGH-2): the
   store's no-transaction arm
   (``_advance_scene_actual_span_tx``) writes ``actual_start_tick``
   (``COALESCE`` — the first committed segment's start stands), advances
   ``actual_end_tick`` for every segment, and carries the
   ``ACTIVE → COMMITTED`` flip when the segment is the scene's last —
   **one UPDATE, one version bump** (the alias law: SCENE COMMIT **is**
   the scene's last SEGMENT COMMIT, STATE §22 — not a third
   transaction);
6. the chapter's first segment — ``PLANNED → ACTIVE`` with
   ``opened_at_tick`` = the transaction's own read of
   ``world.current_tick`` (the **#3 lifecycle tick authority**: the
   commit transaction took the pipeline over from the caller-supplied
   staging; the chapter-side checks — ADOPTED Blueprint and the
   overlap ban — judge inside this same transaction, which is the
   0029 race-free obligation's discharge).

**The fresh segment's ordering law (V3-5R, the review's MEDIUM-HIGH)**:
a fresh segment takes strictly ``segment_seq == max(committed_seq) +
1`` — the first segment is 1, and 0 / negative / skipped / out-of-order
sequences are refused ``VALIDATION_FAILED`` naming the given and the
expected values. The read runs inside this one transaction, and the
replay arm below answers an existing key **first** — a stored segment's
replay is never judged by this law.

**Terminality is persisted (V3-5R; migration 0034)**:
``segment_commit.is_last_segment`` stores whether this segment's commit
carried the flip. The replay shape comparison includes it — the same
``segment_key`` replayed with a different ``is_last_segment`` is an
explicit ``CONFLICT``, never a silent "equivalent record": the
``commit_scene`` explicit face can commit a scene with no terminal
segment at all, which is exactly why the fact is stored and never
derived on read.

**Idempotent replay**: the same ``segment_key = (scene_id,
segment_seq)`` replayed with the same shape is a whole-group no-op —
the stored outcome rides back, no second row, no tick re-advance, and
no span re-write (the span arm is on the fresh path only); the same key
with a different shape is a ``CONFLICT`` (committed segments are
append-only). The shape comparison covers the semantic payload (prose
body / language / narration / participants / effects / duration) and
the persisted terminality flag; the bookkeeping stamps (``occurred_at``
/ ``created_at`` / ``updated_at``) are not compared — they are the
caller's clock stamps, and a replay carries a fresh one.

**The reader exposure face** (:func:`record_exposure`) is deliberately
**not** part of any commit transaction — the review's **item 2**
decoupling's physical form: a passage commit is not a reading
(STATE §25 / RA §28). It lands its own one-row short transaction, and
N-INV-005 holds structurally: the exposure SQL never names the actor
memory / belief vocabulary (V3-5 ships neither table; the pin scans
this module's SQL).

**V3 participants are canonical identities** (the V3-3R freeze):
:func:`commit_segment` refuses a participant word outside the world's
``participant_namespace`` derivation (actor ids ∪ the player character
id) — the legacy ``world_event.participants`` vocabulary (cast persona
ids ∪ user id) is never written back; the lineage face above is how
read paths tell V3 rows from legacy ones. The namespace's durable
sources are read inside the transaction: the actor ids through
:meth:`elc.world.store.SqliteWorldStore.actors_of`, the player id
through a parameter-bound read of ``world_player_character`` (the
store face that owns it lives in :mod:`elc.world.cast`, outside this
function's given signature).

Discipline (the house store law): **value semantics** — every refusal
is a ``Result`` ``Err`` (``VALIDATION_FAILED`` for the caller's own
payload or move, ``NOT_FOUND`` for a dangling identity, ``CONFLICT``
for a shape clash with an existing row, ``DEPENDENCY_UNAVAILABLE`` for
the database's own failures); **no hidden clock** — every stamp rides
the caller's ``now``; **one short transaction** per write with the
began-flag posture; **no SQL string building** — fixed literals and
parameter binding only; the one ``f"..."`` that builds values builds
*identities* (``passage_id`` / ``event_id`` / ``commit_id`` /
``exposure_id``), never SQL.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.cast import participant_namespace
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    SceneStatus,
    WorldSceneRecord,
)
from elc.world.store import (
    SqliteWorldStore,
    _settle_effects_in_transaction,
)
from elc.world.time import advance_current_tick, read_current_tick
from elc.world.types import (
    StateEffect,
    decode_effects,
    decode_participants,
    encode_effects,
    encode_participants,
)

__all__ = [
    "CommitOutcome",
    "ExposureRecord",
    "commit_segment",
    "record_exposure",
    "story_time_of",
]


@dataclass(frozen=True)
class CommitOutcome:
    """One SEGMENT COMMIT's answer shape.

    ``passage_id`` / ``event_id`` / ``commit_id`` are the derived
    identities of the landed rows; ``actual_start_tick`` /
    ``actual_end_tick`` the segment's actual span (the current tick
    before the advance and after it); ``scene_committed`` says this
    segment was the scene's last — the ``ACTIVE → COMMITTED`` flip
    landed with it (the SCENE COMMIT alias); ``chapter_activated`` says
    this segment opened its chapter (the chapter was ``PLANNED`` and the
    ``opened_at_tick`` is this segment's own start).
    """

    passage_id: str
    event_id: str
    commit_id: str
    actual_start_tick: int
    actual_end_tick: int
    scene_committed: bool
    chapter_activated: bool


@dataclass(frozen=True)
class ExposureRecord:
    """One reader-exposure row (migration 0033's ``reader_exposure`` —
    the record face, not story time; ``exposed_at`` is the caller's ISO
    bookkeeping stamp)."""

    exposure_id: str
    passage_id: str
    reader_id: str
    exposed_at: str
    created_at: str
    updated_at: str
    state_version: int


def commit_segment(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    scene_id: str,
    segment_seq: int,
    body: str,
    language: str,
    participants: tuple[str, ...],
    effects: tuple[StateEffect, ...],
    narration: str,
    duration_ticks: int,
    is_last_segment: bool,
    now: str,
) -> Result[CommitOutcome]:
    """Land one segment: NCP-3's single short transaction (see the module
    docstring for the atomic group's arms, the replay law and the
    identity freeze).

    Refusals, all value semantics, the whole group rolling back:

    - the scene does not exist — ``NOT_FOUND``; a dangling chapter
      (unreachable under the FK, answered honestly all the same) —
      ``NOT_FOUND``;
    - ``duration_ticks`` negative — ``VALIDATION_FAILED`` (the actual
      tick never moves backwards, STATE §26 / §27);
    - an effects entry that is not a :class:`StateEffect`, a
      participants word that is not a string, or one canonical effect
      key twice in one event — ``VALIDATION_FAILED`` (the event
      settlement's own one-claim-per-key law, mirroring
      :meth:`SqliteWorldStore.record_event`);
    - a **fresh** segment (no row for the segment_key yet) whose scene
      is not ``ACTIVE`` — ``VALIDATION_FAILED`` (only an active scene
      takes segments; a replay is answered before this check, so a
      committed scene's stored segments still replay as no-ops);
    - a **fresh** segment whose ``segment_seq`` is not
      ``max(committed_seq) + 1`` (the first segment is 1) — a 0,
      negative, skipped or out-of-order sequence is
      ``VALIDATION_FAILED`` naming the given and the expected values
      (the V3-5R ordering law; the replay arm is answered first, so an
      existing key's replay is never judged by it);
    - a participant word outside the world's ``participant_namespace``
      (canonical identity — the V3-3R freeze) — ``VALIDATION_FAILED``;
    - the same segment_key with a different shape (its persisted
      ``is_last_segment`` terminality flag included) — ``CONFLICT``
      (committed segments do not rewrite).

    ``now`` stamps the passage/event/lineage rows (``occurred_at`` =
    ``now``: the legacy ISO column V3 deliberately does not read —
    story time rides the lineage face, never ``occurred_at``).
    """

    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _commit_segment_tx(
            conn,
            narrative_store=narrative_store,
            world_store=world_store,
            scene_id=scene_id,
            segment_seq=segment_seq,
            body=body,
            language=language,
            participants=participants,
            effects=effects,
            narration=narration,
            duration_ticks=duration_ticks,
            is_last_segment=is_last_segment,
            now=now,
        )
        if isinstance(outcome, Err):
            conn.execute("ROLLBACK")
            began = False
            return Err(outcome.error)
    except sqlite3.Error as exc:
        if began:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        return Err(
            DomainError(
                code=_refusal_code(exc),
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    f" committed: {exc}"
                ),
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _commit_segment_tx(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    scene_id: str,
    segment_seq: int,
    body: str,
    language: str,
    participants: tuple[str, ...],
    effects: tuple[StateEffect, ...],
    narration: str,
    duration_ticks: int,
    is_last_segment: bool,
    now: str,
) -> Result[CommitOutcome]:
    """The atomic group's body, inside the caller's transaction (the
    public :func:`commit_segment` owns the BEGIN/COMMIT — the same
    arm/owner split :mod:`elc.world.narrative.store`'s flip arms spell).
    """

    scene = narrative_store.get_scene(scene_id)
    if scene is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"segment {segment_seq} not committed: scene"
                    f" {scene_id!r} does not exist"
                ),
            )
        )

    # The payload's own checks (before the replay read — a malformed
    # payload is the caller's mistake whether or not the segment exists).
    if duration_ticks < 0:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    f" committed: duration_ticks {duration_ticks!r} is"
                    " negative — the actual tick never moves backwards"
                    " (STATE §26)"
                ),
            )
        )
    seen_keys: set[str] = set()
    for effect in effects:
        if not isinstance(effect, StateEffect):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        " committed: effects must be StateEffect entries;"
                        f" got {type(effect).__name__}"
                    ),
                )
            )
        if effect.key in seen_keys:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        f" committed: canonical key {effect.key!r} appears"
                        " twice in one segment (one event, one claim per"
                        " key); nothing was written"
                    ),
                )
            )
        seen_keys.add(effect.key)
    for word in participants:
        if not isinstance(word, str):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        f" committed: participants carries a non-string"
                        f" entry {word!r}"
                    ),
                )
            )

    # The replay read: an existing row for this segment_key answers the
    # stored outcome (shape-equal) or CONFLICT (shape-different) — the
    # check runs before the fresh path's scene-status gate so a committed
    # scene's stored segments still replay as no-ops.
    existing = _segment_commit_row(conn, scene_id, segment_seq)
    if existing is not None:
        return _replay_outcome(
            conn,
            narrative_store=narrative_store,
            scene=scene,
            row=existing,
            body=body,
            language=language,
            participants=participants,
            effects=effects,
            narration=narration,
            duration_ticks=duration_ticks,
            is_last_segment=is_last_segment,
        )

    # The fresh path's ordering law (V3-5R, the review's MEDIUM-HIGH):
    # a fresh segment takes strictly max(committed_seq) + 1 — the first
    # segment is 1. The replay read above runs first, so a stored key's
    # replay is never judged here; the read is inside the caller's
    # transaction, so no window lets a second writer slip a sequence in.
    last_row = conn.execute(
        "SELECT MAX(segment_seq) FROM segment_commit WHERE scene_id = ?",
        (scene_id,),
    ).fetchone()
    last_seq = 0 if last_row is None or last_row[0] is None else int(last_row[0])
    expected_seq = last_seq + 1
    if segment_seq != expected_seq:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    " committed: a fresh segment takes segment_seq ="
                    f" max(committed_seq) + 1 (expected {expected_seq},"
                    f" given {segment_seq}) — the first segment is 1;"
                    " 0, negative, skipped and out-of-order sequences"
                    " are refused (STATE §25)"
                ),
            )
        )

    if scene.status is not SceneStatus.ACTIVE:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    f" committed: the scene is {scene.status.value!r};"
                    " only an ACTIVE scene takes segment commits"
                ),
            )
        )
    chapter = narrative_store.get_chapter(scene.chapter_id)
    if chapter is None:  # the FK makes this unreachable; answered honestly
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    f" committed: chapter {scene.chapter_id!r} does not"
                    " exist"
                ),
            )
        )
    world_id = chapter.world_id
    namespace = _participant_namespace(conn, world_store, world_id)
    for word in participants:
        if word not in namespace:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        f" committed: participant {word!r} is not a"
                        " canonical participant identity — the namespace"
                        " is the durable cast's actor ids union the"
                        " player character id (V3-3R freeze: a persona id"
                        " is a template identity, a resident name is"
                        " prose)"
                    ),
                )
            )

    tick = read_current_tick(conn, world_id)
    if isinstance(tick, Err):
        return Err(tick.error)
    actual_start = tick.value
    actual_end = actual_start + duration_ticks
    passage_id = f"{scene_id}-p{segment_seq:04d}"
    event_id = f"{scene_id}-e{segment_seq:04d}"
    commit_id = f"sg:{scene_id}:{segment_seq:04d}"

    conn.execute(
        "INSERT INTO narrative_passage ("
        " passage_id, scene_id, segment_seq, body, language, outcome_ref,"
        " created_at_tick, created_at, updated_at, state_version"
        ") VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, 1)",
        (passage_id, scene_id, segment_seq, body, language, actual_end, now, now),
    )
    conn.execute(
        "INSERT INTO world_event ("
        " event_id, world_id, kind, narration, effects, occurred_at,"
        " source, participants, run_id"
        ") VALUES (?, ?, 'segment', ?, ?, ?, 'v3-segment', ?, NULL)",
        (
            event_id,
            world_id,
            narration,
            encode_effects(effects),
            now,
            encode_participants(participants),
        ),
    )
    _settle_effects_in_transaction(conn, world_id, event_id, effects, now)
    conn.execute(
        "INSERT INTO segment_commit ("
        " commit_id, kind, scene_id, segment_seq, passage_id,"
        " actual_start_tick, actual_end_tick, event_id, is_last_segment,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'SEGMENT', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            commit_id,
            scene_id,
            segment_seq,
            passage_id,
            actual_start,
            actual_end,
            event_id,
            int(is_last_segment),
            now,
            now,
        ),
    )
    advanced = advance_current_tick(conn, world_id, duration_ticks)
    if isinstance(advanced, Err):
        return Err(advanced.error)

    # The scene's actual span — NCP-3's one span writer (V3-5R HIGH-2):
    # start on the first committed segment (COALESCE keeps it), end on
    # every segment, and the ACTIVE → COMMITTED flip rides the same
    # single UPDATE when this segment is the scene's last (the SCENE
    # COMMIT alias; one version bump, no third transaction).
    scene_committed = False
    span = narrative_store._advance_scene_actual_span_tx(
        scene_id,
        actual_start,
        actual_end,
        is_last_segment,
        now,
        expected_state_version=scene.state_version,
    )
    if isinstance(span, Err):
        return Err(span.error)
    if is_last_segment:
        scene_committed = True

    chapter_activated = False
    if chapter.status is ChapterStatus.PLANNED:
        opened = narrative_store._flip_chapter_activated_tx(
            chapter.chapter_id, actual_start, now, chapter.state_version
        )
        if isinstance(opened, Err):
            return Err(opened.error)
        chapter_activated = True

    return Ok(
        CommitOutcome(
            passage_id=passage_id,
            event_id=event_id,
            commit_id=commit_id,
            actual_start_tick=actual_start,
            actual_end_tick=actual_end,
            scene_committed=scene_committed,
            chapter_activated=chapter_activated,
        )
    )


def _segment_commit_row(
    conn: sqlite3.Connection, scene_id: str, segment_seq: int
) -> tuple[Any, ...] | None:
    """The segment_key's lineage row, or ``None`` — the replay read's
    own pure SELECT (``commit_id, passage_id, actual_start_tick,
    actual_end_tick, event_id, is_last_segment``)."""

    return conn.execute(
        "SELECT commit_id, passage_id, actual_start_tick,"
        " actual_end_tick, event_id, is_last_segment FROM segment_commit"
        " WHERE scene_id = ? AND segment_seq = ?",
        (scene_id, segment_seq),
    ).fetchone()


def _replay_outcome(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    scene: WorldSceneRecord,
    row: tuple[Any, ...],
    body: str,
    language: str,
    participants: tuple[str, ...],
    effects: tuple[StateEffect, ...],
    narration: str,
    duration_ticks: int,
    is_last_segment: bool,
) -> Result[CommitOutcome]:
    """Answer a replayed segment_key: shape-equal rides back as the
    stored outcome, shape-different is a ``CONFLICT``.

    The compared shape is the semantic payload — the passage's ``body``
    / ``language`` / ``created_at_tick`` (the row's own spelling of the
    segment's end tick), the event's ``kind`` / ``narration`` /
    ``effects`` / ``participants`` (through the strict codecs), the
    lineage span's duration, and the persisted terminality flag
    ``is_last_segment`` (V3-5R; a terminality mismatch answers its own
    ``CONFLICT`` sentence naming the flag). The ``scene_committed``
    answer rides that same stored flag — the durable witness the flip
    landed with this segment (the review's F1) — never a read-time
    derivation over the scene's status and its max seq. Bookkeeping
    stamps are not compared (the caller's clock differs on a replay, by
    design). An undecodable stored payload — this module's own encoder's
    output, corrupted — raises ``ValueError`` (the store family's
    corrupted-row posture), never a fabricated comparison.
    """

    (
        commit_id,
        passage_id,
        actual_start,
        actual_end,
        event_id,
        stored_is_last,
    ) = (
        str(row[0]),
        str(row[1]),
        int(row[2]),
        int(row[3]),
        str(row[4]),
        bool(row[5]),
    )
    passage = conn.execute(
        "SELECT body, language, created_at_tick FROM narrative_passage"
        " WHERE passage_id = ?",
        (passage_id,),
    ).fetchone()
    event = conn.execute(
        "SELECT world_id, kind, narration, effects, participants"
        " FROM world_event WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert passage is not None  # the FK makes a dangling passage unreachable
    assert event is not None  # the same for the event
    decoded_effects = decode_effects(str(event[3]))
    if isinstance(decoded_effects, Err):
        raise ValueError(
            f"segment {commit_id!r} carries an undecodable effects"
            f" column: {decoded_effects.error.message}"
        )
    decoded_participants = decode_participants(str(event[4]))
    if isinstance(decoded_participants, Err):
        raise ValueError(
            f"segment {commit_id!r} carries an undecodable participants"
            f" column: {decoded_participants.error.message}"
        )
    stored_shape = (
        str(passage[0]),
        str(passage[1]),
        int(passage[2]),
        str(event[1]),
        str(event[2]),
        decoded_effects.value,
        decoded_participants.value,
        actual_end - actual_start,
        stored_is_last,
    )
    if stored_shape != (
        body,
        language,
        actual_end,
        "segment",
        narration,
        effects,
        participants,
        duration_ticks,
        is_last_segment,
    ):
        if stored_is_last != is_last_segment:
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"segment {commit_id!r} already exists with a"
                        " different terminality: the stored"
                        f" is_last_segment is {stored_is_last}, the"
                        f" replay carries {is_last_segment} — terminality"
                        " is a stored fact (migration 0034) and committed"
                        " segments are append-only; they do not rewrite"
                    ),
                )
            )
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"segment {commit_id!r} already exists with a"
                    " different shape; committed segments are append-only"
                    " and do not rewrite"
                ),
            )
        )
    chapter = narrative_store.get_chapter(scene.chapter_id)
    # The stored flag is the answer (the V3-5R review's F1): it is the
    # durable witness that the flip landed with this very segment — a
    # read-time derivation over the scene's status and its max seq could
    # answer True for a segment whose flip never landed (a scene
    # committed through the explicit ``commit_scene`` face).
    scene_committed = stored_is_last
    return Ok(
        CommitOutcome(
            passage_id=passage_id,
            event_id=event_id,
            commit_id=commit_id,
            actual_start_tick=actual_start,
            actual_end_tick=actual_end,
            scene_committed=scene_committed,
            chapter_activated=(
                chapter is not None
                and chapter.status is ChapterStatus.ACTIVE
                and chapter.opened_at_tick == actual_start
            ),
        )
    )


def story_time_of(
    conn: sqlite3.Connection, event_id: str
) -> Result[tuple[int, int] | None]:
    """The V3 event's narrative span — its ``segment_commit`` row's
    actual interval — or ``Ok(None)`` for an event the lineage face does
    not own (a legacy V2 event: the honest "no V3 story time").

    **The review's item 1 hard door's read path**: story time is
    attributed through this explicit face, never inferred from an
    event-id's naming, and the legacy ``world_event.occurred_at`` (a V2
    ISO moment) is deliberately not consulted. A read: no transaction
    of its own.
    """

    row = conn.execute(
        "SELECT actual_start_tick, actual_end_tick FROM segment_commit"
        " WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if row is None:
        return Ok(None)
    return Ok((int(row[0]), int(row[1])))


def record_exposure(
    conn: sqlite3.Connection,
    *,
    passage_id: str,
    reader_id: str,
    now: str,
) -> Result[ExposureRecord]:
    """Record one reader exposure — the decoupled record face (the
    review's **item 2** hard door's physical form): a passage commit is
    not a reading, so this face is **never** part of any commit
    transaction — it lands its own one-row short transaction, called
    after the delivery/render acknowledgement.

    ``exposure_id`` derives ``f"{passage_id}-x{reader_id}"``. The first
    record wins: a replay (the same passage + reader) answers the
    stored row unchanged — zero write, the original ``exposed_at``
    stands (a conservative record, DOMAIN §20.3-7; no metagame). A
    dangling ``passage_id`` is refused by the table's own FK and
    surfaces as ``NOT_FOUND``. ``exposed_at`` is **ISO bookkeeping, not
    story time** (DATA §26.2.1).

    The existence read runs *outside* the ``BEGIN IMMEDIATE`` (the same
    posture the V3-1 review's MEDIUM registered and the V3-2 lock pin's
    family keeps): under Local V1's single-connection discipline the
    window is unreachable, and a concurrent first-write race would
    surface as the table's own UNIQUE refusal (``CONFLICT``) — never a
    silent second row; the race-free form is this face's own later
    obligation if a multi-connection deployment ever opens it.

    N-INV-005: this face writes no actor memory / belief — V3-5 ships
    neither table, and the module's SQL scan pin keeps the exposure
    statements clear of their vocabulary.
    """

    exposure_id = f"{passage_id}-x{reader_id}"
    existing = conn.execute(
        "SELECT exposure_id, passage_id, reader_id, exposed_at,"
        " created_at, updated_at, state_version FROM reader_exposure"
        " WHERE exposure_id = ?",
        (exposure_id,),
    ).fetchone()
    if existing is not None:
        return Ok(_exposure_record(existing))
    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        conn.execute(
            "INSERT INTO reader_exposure ("
            " exposure_id, passage_id, reader_id, exposed_at,"
            " created_at, updated_at, state_version"
            ") VALUES (?, ?, ?, ?, ?, ?, 1)",
            (exposure_id, passage_id, reader_id, now, now, now),
        )
    except sqlite3.Error as exc:
        if began:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        return Err(
            DomainError(
                code=_refusal_code(exc),
                message=(
                    f"exposure {exposure_id!r} not recorded: {exc}"
                ),
            )
        )
    conn.execute("COMMIT")
    row = conn.execute(
        "SELECT exposure_id, passage_id, reader_id, exposed_at,"
        " created_at, updated_at, state_version FROM reader_exposure"
        " WHERE exposure_id = ?",
        (exposure_id,),
    ).fetchone()
    assert row is not None  # the INSERT above just landed it
    return Ok(_exposure_record(row))


def _exposure_record(row: tuple[Any, ...]) -> ExposureRecord:
    return ExposureRecord(
        exposure_id=str(row[0]),
        passage_id=str(row[1]),
        reader_id=str(row[2]),
        exposed_at=str(row[3]),
        created_at=str(row[4]),
        updated_at=str(row[5]),
        state_version=int(row[6]),
    )


def _participant_namespace(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    world_id: str,
) -> frozenset[str]:
    """The world's canonical participant vocabulary, assembled from its
    two durable identity sources **inside the caller's transaction** —
    the frozen recipe (:func:`elc.world.cast.participant_namespace`)
    over :meth:`SqliteWorldStore.actors_of`'s ``actor_id`` halves and a
    parameter-bound read of ``world_player_character`` (one row per
    world; the cast store that owns the richer face is outside this
    function's given signature — the read is of the same durable row).
    """

    actor_ids = [str(actor.actor_id) for actor in world_store.actors_of(world_id)]
    row = conn.execute(
        "SELECT player_character_id FROM world_player_character"
        " WHERE world_id = ?",
        (world_id,),
    ).fetchone()
    player_id = None if row is None else str(row[0])
    return participant_namespace(
        actor_ids=actor_ids, player_character_id=player_id
    )


def _refusal_code(exc: sqlite3.Error) -> DomainErrorCode:
    """Map the database's own refusal to the store vocabulary — the same
    three families the world store's ``create_world`` spells (N-W10-6):
    a UNIQUE clash is a ``CONFLICT``, a FOREIGN KEY refusal is
    ``NOT_FOUND``, any other database failure answers
    ``DEPENDENCY_UNAVAILABLE`` with the raw error riding the message."""

    text = str(exc)
    if "UNIQUE constraint failed" in text:
        return DomainErrorCode.CONFLICT
    if "FOREIGN KEY constraint failed" in text:
        return DomainErrorCode.NOT_FOUND
    return DomainErrorCode.DEPENDENCY_UNAVAILABLE
