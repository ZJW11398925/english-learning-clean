"""The Narrative V3 SEGMENT COMMIT — NCP-3's one short atomic group
(V3-5, TASK-OPI-be7b094f…34 / the opening ruling DEC-OPI-be7b094f…32;
the V3-5R corrections TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11; the
V3-6R correction TASK-OPI-dc1bafdf…33 / the opening ruling
DEC-OPI-dc1bafdf…31 — the ``outcome_ref`` arm and the targeted close) —
plus the two faces the cut's hard doors freeze: the explicit story-time
lineage read and the decoupled reader-exposure record; and, since V3-7
(TASK-OPI-d274a7fb…8 / the opening ruling DEC-OPI-d274a7fb…6), the
**NCP-4 chapter-settlement orchestration** (:func:`settle_chapter` — the
short transaction that lands one ``chapter_settlement`` row and flips
``SETTLING → CLOSED``; not a fact-landing boundary, N-INV-004).

**The commit transaction** (:func:`commit_segment`): one
``BEGIN IMMEDIATE`` … ``COMMIT`` lands, all or nothing (N-R-INV-004):

1. ``narrative_passage`` — the segment's prose (the CANON face's
   immutable row; N-INV-003), carrying the segment's ``outcome_ref``
   when one rode with it (V3-6R: the reference to the committed user
   action whose continuation this segment is);
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
5. ``world_scene``'s actual span — the shared span arm's NCP-3 caller
   (V3-5R, TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11's HIGH-2;
   **generalized to two callers by V3-6R**, STATE §26): the store's
   no-transaction arm (``_advance_scene_actual_span_tx``) writes
   ``actual_start_tick`` (``COALESCE`` — the first committed segment's
   start stands), advances ``actual_end_tick`` for every segment, and
   carries the ``ACTIVE → COMMITTED`` flip when the segment is the
   scene's last (``close_scene=True``) — **one UPDATE, one version
   bump** (the alias law: SCENE COMMIT **is** the scene's last SEGMENT
   COMMIT, STATE §22 — not a third transaction). NCP-2 calls the same
   arm with ``close_scene=False``: a gate's action extends the interval
   and never closes a scene;
6. the chapter's first segment — ``PLANNED → ACTIVE`` with
   ``opened_at_tick`` = the transaction's own read of
   ``world.current_tick`` (the **#3 lifecycle tick authority**: the
   commit transaction took the pipeline over from the caller-supplied
   staging; the chapter-side checks — ADOPTED Blueprint and the
   overlap ban — judge inside this same transaction, which is the
   0029 race-free obligation's discharge);
7. ``actor_memory`` — the **V3-7 memory arm** (STATE §25's "V3-7
   落法"): one ``EXPERIENCED`` row per event participant, in order,
   through :func:`elc.world.memory.record_experienced_in_transaction`
   (the two commit transactions' one shared arm), with ``content`` =
   the event's ``narration`` and ``learned_at_tick`` = this segment's
   ``actual_end_tick``. The arm sits on the **fresh** path only — the
   replay arm answers first, so a replayed segment never double-lands
   a memory.

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
body / language / narration / participants / effects / duration), the
persisted terminality flag and — since V3-6R — the passage's
``outcome_ref`` (a different reference answers its own dedicated
``CONFLICT`` sentence); the bookkeeping stamps (``occurred_at``
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
function's given signature). **Since V3-6** the assembly is the public
:func:`participant_namespace_of` (the one truth the action module's
``commit_action`` calls too), and the player-row read is the public
:func:`player_character_id_of`.

**The ``outcome_ref`` chain (V3-6R, TASK-OPI-dc1bafdf…33 /
DEC-OPI-dc1bafdf…31; STATE §25's "V3-6R 落法", DATA §26.2.1)** — the
traceable chain ``intent → adjudication → committed action →
outcome_ref → passage``: when ``outcome_ref`` rides with a fresh
segment it must name a real **``COMMITTED``** ``user_action`` (absent —
``NOT_FOUND``; not committed — ``VALIDATION_FAILED``) whose gate
belongs to **this** segment's scene (else ``VALIDATION_FAILED``); the
passage stores the reference, and the referenced gate moves
``COMMITTED → CLOSED`` in this same transaction (one targeted UPDATE —
**replacing the V3-6 blanket close of every committed gate**: the fresh
segment that carries the gate's action closes *that* gate — §23's
V3-6R tightening ③; a reference whose gate is already ``CLOSED``
answers a zero-row UPDATE, a no-op). The **forced law**: while the
scene holds a ``COMMITTED`` gate nobody has resumed past, a fresh
segment **must** carry that gate's action as its ``outcome_ref``
(missing / different — ``VALIDATION_FAILED``: the recovery prose never
lands with a NULL reference). A replay's shape comparison includes the
reference (the same key with a different reference — ``CONFLICT``).

**The User Gate interlock (V3-6, TASK-OPI-dc1bafdf…23 /
DEC-OPI-dc1bafdf…5, re-run …21; the V3-6R tightening …33; STATE
§22/§23/§25)** — the arms ride this same transaction, all on the
**fresh** path only (a stored segment's replay is answered first and
touches nothing):

- before a fresh segment lands, the scene must hold **no non-terminal
  gate** (``user_gate`` in ``OPEN`` / ``ANSWERED`` / ``RESOLVING``) —
  a story stopped at a User Gate does not write on, refused
  ``VALIDATION_FAILED`` naming the standing gate (the physical form of
  §22's "the story stops");
- the **forced law** above: a ``COMMITTED`` gate nobody resumed past
  refuses a fresh segment that does not carry its action as the
  ``outcome_ref`` — the resuming prose must name what it resumes
  (V3-6R tightening ②'s closing half);
- when a fresh segment lands carrying a gate's action as its
  ``outcome_ref``, that gate moves ``COMMITTED → CLOSED`` in this same
  transaction (one UPDATE, one version bump) — "the writing resumed"
  (§23; the segment commit is the continuation, and the
  ``COMMITTED → CLOSED`` step has no face of its own by design).

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
from elc.world.memory import record_experienced_in_transaction
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
    "ChapterSettlementRecord",
    "CommitOutcome",
    "ExposureRecord",
    "chapter_settlements_of",
    "commit_segment",
    "participant_namespace_of",
    "player_character_id_of",
    "record_exposure",
    "settle_chapter",
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
    outcome_ref: str | None = None,
) -> Result[CommitOutcome]:
    """Land one segment: NCP-3's single short transaction (see the module
    docstring for the atomic group's arms, the replay law and the
    identity freeze). ``outcome_ref`` — the V3-6R arm — names the
    committed user action this segment is the continuation of; ``None``
    is the arm not taken (the reference is optional *unless* the scene
    holds a committed gate, in which case the forced law demands it).

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
    - ``outcome_ref`` present but not a non-empty string —
      ``VALIDATION_FAILED``;
    - a **fresh** segment (no row for the segment_key yet) whose scene
      is not ``ACTIVE`` — ``VALIDATION_FAILED`` (only an active scene
      takes segments; a replay is answered before this check, so a
      committed scene's stored segments still replay as no-ops);
    - a **fresh** segment whose ``outcome_ref`` names no ``user_action``
      — ``NOT_FOUND`` (a dangling reference); names one that is not
      ``COMMITTED``, or whose gate does not belong to this segment's
      scene — ``VALIDATION_FAILED`` (STATE §25's "V3-6R 落法");
    - a **fresh** segment whose scene holds a ``COMMITTED`` gate while
      it does not carry that gate's action as its ``outcome_ref`` —
      ``VALIDATION_FAILED`` (the forced law: the recovery prose names
      what it resumes and closes that gate — §23's tightening ③);
    - a **fresh** segment whose scene holds a non-terminal User Gate
      (``OPEN`` / ``ANSWERED`` / ``RESOLVING``) —
      ``VALIDATION_FAILED`` naming the standing gate (the story stops
      at a gate, STATE §22/§23; the replay arm answers first here too);
    - a **fresh** segment whose ``segment_seq`` is not
      ``max(committed_seq) + 1`` (the first segment is 1) — a 0,
      negative, skipped or out-of-order sequence is
      ``VALIDATION_FAILED`` naming the given and the expected values
      (the V3-5R ordering law; the replay arm is answered first, so an
      existing key's replay is never judged by it);
    - a participant word outside the world's ``participant_namespace``
      (canonical identity — the V3-3R freeze) — ``VALIDATION_FAILED``;
    - the same segment_key with a different shape (its persisted
      ``is_last_segment`` terminality flag and its ``outcome_ref``
      included) — ``CONFLICT`` (committed segments do not rewrite).

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
            outcome_ref=outcome_ref,
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
    outcome_ref: str | None = None,
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
    if outcome_ref is not None and (
        not isinstance(outcome_ref, str) or not outcome_ref.strip()
    ):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    " committed: outcome_ref must be a non-empty string"
                    " naming a committed user action when given; got"
                    f" {outcome_ref!r}"
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
            outcome_ref=outcome_ref,
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

    # The V3-6R reference checks (fresh path; the replay arm above
    # answered first): a given ``outcome_ref`` must name a real
    # ``COMMITTED`` action of this scene's own gate — the chain
    # ``intent → adjudication → committed action → outcome_ref →
    # passage`` is checkable, not promised (STATE §25's "V3-6R 落法").
    referenced_gate_id: str | None = None
    if outcome_ref is not None:
        referenced = conn.execute(
            "SELECT a.status, a.gate_id, g.scene_id FROM user_action a"
            " JOIN user_gate g ON g.gate_id = a.gate_id"
            " WHERE a.user_action_id = ?",
            (outcome_ref,),
        ).fetchone()
        if referenced is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        f" committed: outcome_ref {outcome_ref!r} names no"
                        " user action — a passage's reference points at a"
                        " durable ruling, not a guess"
                    ),
                )
            )
        if str(referenced[0]) != "COMMITTED":
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        f" committed: outcome_ref {outcome_ref!r} names an"
                        f" action whose status is {str(referenced[0])!r};"
                        " only a COMMITTED ruling is resumed (the"
                        " adjudication lands first; NCP-2)"
                    ),
                )
            )
        if str(referenced[2]) != scene_id:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        f" committed: outcome_ref {outcome_ref!r} names an"
                        f" action of scene {str(referenced[2])!r} — a"
                        " passage resumes the ruling of its own scene"
                    ),
                )
            )
        referenced_gate_id = str(referenced[1])

    # The forced law (V3-6R): while this scene holds a COMMITTED gate
    # nobody resumed past, the fresh segment must carry that gate's
    # action as its outcome_ref — the recovery prose names what it
    # resumes (§23's V3-6R tightening ③'s other half).
    committed_gate = conn.execute(
        "SELECT gate_id FROM user_gate WHERE scene_id = ?"
        " AND status = 'COMMITTED' ORDER BY gate_id ASC",
        (scene_id,),
    ).fetchone()
    if committed_gate is not None:
        required_ref = f"{str(committed_gate[0])}-a"
        if outcome_ref != required_ref:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        " committed: the scene holds the COMMITTED gate"
                        f" {str(committed_gate[0])!r} nobody resumed past —"
                        " a fresh segment must carry its action as"
                        f" outcome_ref {required_ref!r}; got"
                        f" {outcome_ref!r} — the recovery prose never"
                        " lands with a NULL reference (§23's V3-6R"
                        " tightening ③)"
                    ),
                )
            )

    # The User Gate interlock's stop half (V3-6): a story stopped at a
    # gate does not write on — the scene must hold no non-terminal gate
    # (OPEN / ANSWERED / RESOLVING), judged inside this transaction
    # (STATE §22/§23). The replay arm above answered first, so a
    # committed scene's stored segments still replay as no-ops.
    standing = conn.execute(
        "SELECT gate_id, status FROM user_gate WHERE scene_id = ?"
        " AND status IN ('OPEN','ANSWERED','RESOLVING')"
        " ORDER BY gate_id ASC",
        (scene_id,),
    ).fetchone()
    if standing is not None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"segment {segment_seq} of scene {scene_id!r} not"
                    " committed: the story stops at the User Gate"
                    f" {str(standing[0])!r} (its status is"
                    f" {str(standing[1])!r}) — a stopped story does not"
                    " write on (STATE §22/§23)"
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
    namespace = participant_namespace_of(
        conn, world_store=world_store, world_id=world_id
    )
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
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            passage_id,
            scene_id,
            segment_seq,
            body,
            language,
            outcome_ref,
            actual_end,
            now,
            now,
        ),
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

    # The scene's actual span — the shared span arm's NCP-3 caller
    # (V3-5R HIGH-2; the V3-6R two-caller law): start on the first
    # committed segment (COALESCE keeps it), end on every segment, and
    # the ACTIVE → COMMITTED flip rides the same single UPDATE when this
    # segment is the scene's last (close_scene=True — the SCENE COMMIT
    # alias; one version bump, no third transaction).
    scene_committed = False
    span = narrative_store._advance_scene_actual_span_tx(
        scene_id,
        actual_start,
        actual_end,
        close_scene=is_last_segment,
        now=now,
        expected_state_version=scene.state_version,
    )
    if isinstance(span, Err):
        return Err(span.error)
    if is_last_segment:
        scene_committed = True

    # The User Gate interlock's resume half (V3-6; the V3-6R targeted
    # form): the fresh segment that carries a gate's action as its
    # outcome_ref closes **that** gate in this same transaction (one
    # UPDATE, one version bump) — the physical form of §23's "the
    # writing resumed"; a reference whose gate is already CLOSED answers
    # a zero-row UPDATE (a no-op), and no blanket close of other
    # committed gates survives.
    if referenced_gate_id is not None:
        conn.execute(
            "UPDATE user_gate SET status = 'CLOSED',"
            " state_version = state_version + 1, updated_at = ?"
            " WHERE gate_id = ? AND status = 'COMMITTED'",
            (now, referenced_gate_id),
        )

    chapter_activated = False
    if chapter.status is ChapterStatus.PLANNED:
        opened = narrative_store._flip_chapter_activated_tx(
            chapter.chapter_id, actual_start, now, chapter.state_version
        )
        if isinstance(opened, Err):
            return Err(opened.error)
        chapter_activated = True

    # The V3-7 memory arm (STATE §25's "V3-7 落法"): every participant of
    # the segment's event witnessed it — one EXPERIENCED row each, landed
    # in this same transaction through the shared arm. The replay read
    # above answered first, so a replayed segment never reaches this arm
    # (a replay must not double-land memory).
    record_experienced_in_transaction(
        conn,
        world_id=world_id,
        event_id=event_id,
        participants=participants,
        content=narration,
        learned_at_tick=actual_end,
        now=now,
    )

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
    outcome_ref: str | None = None,
) -> Result[CommitOutcome]:
    """Answer a replayed segment_key: shape-equal rides back as the
    stored outcome, shape-different is a ``CONFLICT``.

    The compared shape is the semantic payload — the passage's ``body``
    / ``language`` / ``created_at_tick`` (the row's own spelling of the
    segment's end tick) / ``outcome_ref`` (V3-6R; the reference is
    stored, never derived), the event's ``kind`` / ``narration`` /
    ``effects`` / ``participants`` (through the strict codecs), the
    lineage span's duration, and the persisted terminality flag
    ``is_last_segment`` (V3-5R). A reference mismatch and a terminality
    mismatch each answer their own ``CONFLICT`` sentence naming the
    fact (the reference sentence first when both differ). The
    ``scene_committed`` answer rides that same stored flag — the
    durable witness the flip landed with this segment (the review's
    F1) — never a read-time derivation over the scene's status and its
    max seq. Bookkeeping stamps are not compared (the caller's clock
    differs on a replay, by design). An undecodable stored payload —
    this module's own encoder's output, corrupted — raises ``ValueError``
    (the store family's corrupted-row posture), never a fabricated
    comparison.
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
        "SELECT body, language, created_at_tick, outcome_ref"
        " FROM narrative_passage WHERE passage_id = ?",
        (passage_id,),
    ).fetchone()
    event = conn.execute(
        "SELECT world_id, kind, narration, effects, participants"
        " FROM world_event WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert passage is not None  # the FK makes a dangling passage unreachable
    assert event is not None  # the same for the event
    stored_ref = None if passage[3] is None else str(passage[3])
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
        stored_ref,
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
        outcome_ref,
    ):
        if stored_ref != outcome_ref:
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"segment {commit_id!r} already exists with a"
                        " different outcome_ref: the stored reference is"
                        f" {stored_ref!r}, the replay carries"
                        f" {outcome_ref!r} — the reference is a stored"
                        " fact and committed segments are append-only;"
                        " they do not rewrite"
                    ),
                )
            )
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


def participant_namespace_of(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    world_id: str,
) -> frozenset[str]:
    """The world's canonical participant vocabulary, assembled from its
    two durable identity sources **inside the caller's transaction** —
    the frozen recipe (:func:`elc.world.cast.participant_namespace`)
    over :meth:`SqliteWorldStore.actors_of`'s ``actor_id`` halves and
    :func:`player_character_id_of`'s parameter-bound read of
    ``world_player_character`` (one row per world; the cast store that
    owns the richer face is outside this function's given signature —
    the read is of the same durable row).

    **The one truth since V3-6** (TASK-OPI-dc1bafdf…23): this face and
    the action module's ``commit_action`` both assemble the namespace
    here — one recipe, no second spelling.
    """

    actor_ids = [str(actor.actor_id) for actor in world_store.actors_of(world_id)]
    return participant_namespace(
        actor_ids=actor_ids,
        player_character_id=player_character_id_of(conn, world_id),
    )


def player_character_id_of(
    conn: sqlite3.Connection, world_id: str
) -> str | None:
    """One world's durable user role — the ``world_player_character``
    row's id — or ``None`` (an honest world without a declared player
    contributes nothing, the conditional law). A pure read, no
    transaction of its own; the action module's user-role check is the
    second caller (V3-6)."""

    row = conn.execute(
        "SELECT player_character_id FROM world_player_character"
        " WHERE world_id = ?",
        (world_id,),
    ).fetchone()
    return None if row is None else str(row[0])


# ---------------------------------------------------------------------------
# NCP-4 — the chapter-settlement orchestration (V3-7)
# ---------------------------------------------------------------------------


#: The conservative salience placeholder every deterministic-baseline
#: settlement carries (``salience_notes`` is 恒为保守占位 this cut — the
#: significance evaluation is a later cut's; the string is fixed so the
#: derived shape stays byte-stable across replays).
_SETTLEMENT_SALIENCE_PLACEHOLDER = (
    "salience not evaluated (the deterministic baseline stores no"
    " judgement; the retrieval policy lands with a later cut)"
)


@dataclass(frozen=True)
class ChapterSettlementRecord:
    """One ``chapter_settlement`` row — the chapter-end compression
    product (Narrative Memory's compressed half; migration 0037, one
    version per chapter by the ``chapter_id`` PK).

    ``summary`` / ``storyline_updates`` / ``hooks`` / ``resolved_lines``
    / ``salience_notes`` are the deterministic baseline's conservative
    strings (see :func:`settle_chapter`); ``created_at_revision`` is the
    chapter's latest ``plan_revision`` when the row landed — the Plan
    face's version witness.
    """

    chapter_id: str
    summary: str
    storyline_updates: str
    hooks: str
    resolved_lines: str
    salience_notes: str
    created_at_revision: int
    created_at: str
    updated_at: str
    state_version: int


def settle_chapter(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    chapter_id: str,
    now: str,
) -> Result[ChapterSettlementRecord]:
    """Land one chapter's settlement — **NCP-4**, the chapter-end
    compression of already-committed content (STATE §25's "V3-7 落法";
    RA §28). One short ``BEGIN IMMEDIATE`` … ``COMMIT``:

    1. the chapter must be ``SETTLING`` (its ``ACTIVE → SETTLING``
       entry is the narrative store's own face,
       :meth:`~elc.world.narrative.store.SqliteNarrativeStore.settle_chapter`
       — the same name, a different move: that one *begins* the
       settlement, this one *lands* it); ``PLANNED`` (or ``ACTIVE``)
       and a settlement-less ``CLOSED`` chapter are refused
       ``VALIDATION_FAILED``;
    2. one ``chapter_settlement`` row lands (``chapter_id`` PK — one
       version per chapter; the conservative assembly below);
    3. the same transaction flips ``SETTLING → CLOSED`` through the
       narrative store's no-transaction arm
       (``_close_chapter_tx``), with ``closed_at_tick`` = this
       transaction's own read of ``world.current_tick`` — **the tick is
       never advanced**: a settlement has no duration (N-INV-007);
    4. **N-INV-004's storage face** — this face writes no
       ``world_event``, no ``world_state_fact`` and no ``actor_memory``:
       a settlement only compresses / closes what is already committed.

    **The deterministic baseline's conservative assembly** (the LLM
    summary generation and the structured narrative-memory half are
    registered later cuts):

    - ``summary`` — the chapter's committed lineage rows, one line each
      (``commit_id: narration``), in lineage order
      (``actual_start_tick``, ``actual_end_tick``, ``commit_id``
      ascending): the committed faces' own conservative concatenation;
    - ``storyline_updates`` — the world's active storylines snapshot at
      the settle (``line_id: theme`` per line, the store's own
      two-layer read); the structural advancement (opening / closing /
      settling lines) is a later cut's;
    - ``hooks`` — the honest empty family this cut (**V3-8b, the
      external review's MEDIUM-HIGH**: the field no longer copies the
      Blueprint's ``chapter_questions_to_advance`` — Plan content does
      not auto-upgrade into Narrative Memory at the settlement; the
      reliable hook extraction, from already-happened foreshadowing /
      exposed questions / established open suspense〔Canon /
      Reader-visible faces〕, is a later cut's);
    - ``resolved_lines`` — the honest empty family this cut (the
      structural half is registered with the storyline work);
    - ``salience_notes`` — the fixed conservative placeholder
      (significance is a later cut's judgement);
    - ``created_at_revision`` — the chapter's latest ``plan_revision``
      (a chapter in ``SETTLING`` holds a plan by the #4 prerequisite; a
      state without one is answered honestly, refused) — **plan
      provenance: it names the plan the settlement stood beside, and
      copies none of its content** (V3-8b).

    **Replay = no-op** (the one-version PK carries the idempotence): a
    chapter already settled answers its stored row when the freshly
    derived shape matches — zero write — and a ``CONFLICT`` when it
    differs (one version per chapter; it does not rewrite). A crash
    inside NCP-4 leaves no half state (the transaction is all-or-
    nothing), so the recovery face's re-run re-derives the same shape
    and rides the stored row back (RA §29's sixth family).

    Refusals, all value semantics, the whole group rolling back: a
    dangling chapter — ``NOT_FOUND``; a chapter not ``SETTLING`` (and
    not a settled replay) — ``VALIDATION_FAILED`` naming its status;
    a chapter holding no plan revision — ``VALIDATION_FAILED`` (a
    corrupted state: the #4 door admitted only chapters with an
    ``ADOPTED`` Blueprint); a stored row whose shape differs from the
    freshly derived one — ``CONFLICT``.
    """

    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _settle_chapter_tx(
            conn,
            narrative_store=narrative_store,
            world_store=world_store,
            chapter_id=chapter_id,
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
                    f"chapter {chapter_id!r} not settled: {exc}"
                ),
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _settle_chapter_tx(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    chapter_id: str,
    now: str,
) -> Result[ChapterSettlementRecord]:
    """NCP-4's body, inside the caller's transaction (the
    arm/owner split the module's other faces keep)."""

    chapter = narrative_store.get_chapter(chapter_id)
    if chapter is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"chapter {chapter_id!r} not settled: it does not"
                    " exist"
                ),
            )
        )
    draft = _settlement_draft(
        conn,
        narrative_store=narrative_store,
        world_store=world_store,
        chapter_id=chapter_id,
        world_id=chapter.world_id,
    )
    if isinstance(draft, Err):
        return Err(draft.error)
    (
        summary,
        storyline_updates,
        hooks,
        resolved_lines,
        salience_notes,
        created_at_revision,
    ) = draft.value

    # The replay arm answers an already-settled chapter first (the house
    # posture — the one-version PK carries the idempotence): shape-equal
    # rides back as the stored row, shape-different is a CONFLICT.
    existing = _chapter_settlement_row(conn, chapter_id)
    if existing is not None:
        if (
            existing.summary,
            existing.storyline_updates,
            existing.hooks,
            existing.resolved_lines,
            existing.salience_notes,
            existing.created_at_revision,
        ) == (
            summary,
            storyline_updates,
            hooks,
            resolved_lines,
            salience_notes,
            created_at_revision,
        ):
            return Ok(existing)
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"chapter {chapter_id!r} is already settled with a"
                    " different shape; one version per chapter — the"
                    " settlement landed once and does not rewrite"
                    " (STATE §21's SETTLING recovery sentence)"
                ),
            )
        )

    if chapter.status is not ChapterStatus.SETTLING:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"chapter {chapter_id!r} is"
                    f" {chapter.status.value!r}; only a SETTLING chapter"
                    " is settled (an ACTIVE chapter enters SETTLING"
                    " first — the story stops, then the compression; a"
                    " PLANNED one has nothing committed to compress)"
                ),
            )
        )

    # The close's tick: the transaction's OWN read of the world's
    # canonical time — the settlement has no duration, so the tick is
    # read and never advanced (N-INV-007; the N-INV-004 storage face).
    tick = read_current_tick(conn, chapter.world_id)
    if isinstance(tick, Err):
        return Err(tick.error)
    closed_at_tick = tick.value

    conn.execute(
        "INSERT INTO chapter_settlement ("
        " chapter_id, summary, storyline_updates, hooks, resolved_lines,"
        " salience_notes, created_at_revision, created_at, updated_at,"
        " state_version"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            chapter_id,
            summary,
            storyline_updates,
            hooks,
            resolved_lines,
            salience_notes,
            created_at_revision,
            now,
            now,
        ),
    )
    closed = narrative_store._close_chapter_tx(
        chapter_id,
        closed_at_tick,
        now,
        expected_state_version=chapter.state_version,
    )
    if isinstance(closed, Err):
        return Err(closed.error)
    row = _chapter_settlement_row(conn, chapter_id)
    assert row is not None  # the INSERT above just landed it
    return Ok(row)


def _settlement_draft(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    chapter_id: str,
    world_id: str,
) -> Result[tuple[str, str, str, str, str, int]]:
    """The deterministic baseline's conservative assembly (see
    :func:`settle_chapter` for what each field is): purely derived from
    already-committed faces — never from the Plan face's content
    (**V3-8b**: the Blueprint's own text does not auto-upgrade into
    Narrative Memory; the latest ``plan_revision`` rides only as the
    provenance number) — so a replay re-derives the same shape byte for
    byte. A chapter holding no plan revision is refused honestly — the
    #4 door admitted only chapters with an ``ADOPTED`` Blueprint, so
    this is a corrupted state and it is named, never guessed."""

    lineage = conn.execute(
        "SELECT c.commit_id, e.narration FROM segment_commit c"
        " JOIN world_event e ON e.event_id = c.event_id"
        " JOIN world_scene s ON s.scene_id = c.scene_id"
        " WHERE s.chapter_id = ?"
        " ORDER BY c.actual_start_tick ASC, c.actual_end_tick ASC,"
        " c.commit_id ASC",
        (chapter_id,),
    ).fetchall()
    summary = "\n".join(f"{str(row[0])}: {str(row[1])}" for row in lineage)
    storyline_updates = "\n".join(
        f"{line.line_id}: {line.theme}"
        for line in world_store.active_storylines(world_id)
    )
    plans = narrative_store.plans_of(chapter_id)
    if not plans:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"chapter {chapter_id!r} not settled: it holds no"
                    " plan revision — the summary's version witness (the"
                    " latest plan_revision) has nothing to name (a"
                    " chapter reaches SETTLING only through an ADOPTED"
                    " Blueprint; this is a corrupted state answered"
                    " honestly)"
                ),
            )
        )
    latest = plans[-1]
    return Ok(
        (
            summary,
            storyline_updates,
            "",  # hooks — the honest empty family (V3-8b: Plan content
            # does not auto-upgrade into Narrative Memory; the reliable
            # hook extraction is a later cut's — see the docstring)
            "",  # resolved_lines — the honest empty family this cut
            _SETTLEMENT_SALIENCE_PLACEHOLDER,
            latest.plan_revision,
        )
    )


def chapter_settlements_of(
    conn: sqlite3.Connection, world_id: str
) -> tuple[ChapterSettlementRecord, ...]:
    """One world's settled chapters' rows — the next-chapter read-only
    summary face (DATA §26.2.1's "下一章只读摘要面"): exactly the rows
    :attr:`elc.world.director.DirectorContext.chapter_summaries`
    carries, the ``CLOSED`` chapters' settlements in ``chapter_index``
    ascending order. A pure read, no transaction of its own — the
    recovery and the Director's context both read it freely."""

    rows = conn.execute(
        "SELECT s.chapter_id, s.summary, s.storyline_updates, s.hooks,"
        " s.resolved_lines, s.salience_notes, s.created_at_revision,"
        " s.created_at, s.updated_at, s.state_version"
        " FROM chapter_settlement s"
        " JOIN world_chapter c ON c.chapter_id = s.chapter_id"
        " WHERE c.world_id = ? AND c.status = 'CLOSED'"
        " ORDER BY c.chapter_index ASC",
        (world_id,),
    ).fetchall()
    return tuple(_chapter_settlement_record(row) for row in rows)


def _chapter_settlement_row(
    conn: sqlite3.Connection, chapter_id: str
) -> ChapterSettlementRecord | None:
    """One settlement row by its chapter id, or ``None`` — the read the
    replay answer uses."""

    row = conn.execute(
        "SELECT chapter_id, summary, storyline_updates, hooks,"
        " resolved_lines, salience_notes, created_at_revision,"
        " created_at, updated_at, state_version FROM chapter_settlement"
        " WHERE chapter_id = ?",
        (chapter_id,),
    ).fetchone()
    if row is None:
        return None
    return _chapter_settlement_record(row)


def _chapter_settlement_record(row: tuple[Any, ...]) -> ChapterSettlementRecord:
    return ChapterSettlementRecord(
        chapter_id=str(row[0]),
        summary=str(row[1]),
        storyline_updates=str(row[2]),
        hooks=str(row[3]),
        resolved_lines=str(row[4]),
        salience_notes=str(row[5]),
        created_at_revision=int(row[6]),
        created_at=str(row[7]),
        updated_at=str(row[8]),
        state_version=int(row[9]),
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
