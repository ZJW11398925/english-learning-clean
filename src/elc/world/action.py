"""The Narrative V3 User Gate and Action Resolver's deterministic machine
face (V3-6, TASK-OPI-dc1bafdf…23 / the opening ruling
DEC-OPI-dc1bafdf…5, re-run revision …21; the V3-6R correction,
TASK-OPI-dc1bafdf…33 / the opening ruling DEC-OPI-dc1bafdf…31) — the
gate a story stops at, the user's own submission, the adjudication, the
ACTION OUTCOME COMMIT's one short atomic group (NCP-2) and the durable
replan obligation that group leaves behind.

**The gates** (STATE §23): the story stops when the world cannot
honestly decide for the user. The face set is the lifecycle's own:

- :func:`open_gate` — ``OPEN``: only an ``ACTIVE`` scene takes a gate,
  ``options`` are two to four non-empty strings (the design supplement
  §2.5's 2–4 natural behaviour options; the free-text arm is implied),
  and a scene holds **no gate short of ``CLOSED``** — ``OPEN`` /
  ``ANSWERED`` / ``RESOLVING`` and a ``COMMITTED`` gate nobody resumed
  past all refuse (the V3-6R one-gate law: close the previous gate
  first with a continuing segment carrying its ``outcome_ref``,
  :func:`elc.world.settlement.commit_segment`; the check runs inside the
  opening face's own short transaction, not in a partial UNIQUE index).
  ``opened_at_tick`` is the transaction's own read of
  ``world.current_tick`` — the #3 lifecycle tick authority's extension:
  opening a stop is not a commit, so the tick is read and never
  advanced. ``gate_id`` derives ``f"{scene_id}-g{gate_seq:02d}"`` (a
  local derivation law, idempotent replay only).
- :func:`submit_gate` — **NCP-1**: ``OPEN → ANSWERED`` and the
  ``user_action`` row's birth (``ANSWERED``, the eight terminal columns
  NULL) land in one short transaction, before any provider adjudication
  (RA §28: this point must succeed first). ``user_action_id`` derives
  ``f"{gate_id}-a"`` — one gate accepts exactly one submission. The
  idempotency anchor is ``(gate_id, submission_id)`` (§26.2.4): the
  same pair replayed with the same shape rides back as the stored row
  (zero write); a different shape is a ``CONFLICT``; a gate that is not
  ``OPEN`` and not this replay is ``VALIDATION_FAILED`` (the gate is
  claimed).
- :func:`begin_resolving` — ``ANSWERED → RESOLVING`` on both rows in one
  short transaction: the durable stop before the transaction-external
  adjudication; a re-call from ``RESOLVING`` is idempotent (the stored
  pair rides back), and the terminal words refuse it.
- :func:`commit_action` — **NCP-2**, the whole arm list of STATE §25's
  "V3-6 落法" in one ``BEGIN IMMEDIATE`` … ``COMMIT``: the eight
  terminal columns (``actual_tick`` = the post-advance ``actual_end``);
  the ``world_event`` behaviour-fact row (``kind='action'``,
  ``source='v3-action'``, id derived
  ``f"ac:{gate_id}:{submission_id}:event"``, ``narration`` = the
  ruling's ``outcome``, ``participants`` = the ruling's own tuple); the
  ``world_state_fact`` settlement through the world store's one-truth
  helper (:func:`elc.world.store._settle_effects_in_transaction`);
  ``world.current_tick`` advanced by ``duration_ticks`` (the only
  sanctioned mover — N-INV-007 / N-R-INV-005); the scene's actual span
  extended through the narrative store's shared span arm with
  ``close_scene=False`` (the **V3-6R span law**: NCP-2 and NCP-3 are the
  two callers of one UPDATE that never closes a scene — a gate's action
  carries no SCENE COMMIT; the flip stays the last SEGMENT's, STATE
  §26); the lineage row (``kind='ACTION_OUTCOME'``, ``commit_id``
  derived ``f"ac:{gate_id}:{submission_id}"``, ``action_id`` carried,
  ``passage_id`` / ``segment_seq`` NULL and ``is_last_segment`` = 0);
  the gate's flip (``RESOLVING`` → ``COMMITTED`` — **since V3-6R the
  only door in**: an ``ANSWERED`` gate has not passed the resolver's
  durable stop, and ``begin_resolving`` is the deterministic baseline's
  single main path); the chapter's opening when it is still ``PLANNED``
  — through the narrative store's own arm, the same move and the same
  ``opened_at_tick`` law NCP-3 keeps (``actual_start``, the
  transaction's own read before the advance: the chapter opens with its
  first segment or its first action ruling); and ⑧ the **replan
  obligation's birth** (:func:`commit_action`'s own arm ⑧, the V3-6R
  HIGH-1): ``replan_scope ≠ NONE`` ⇒ an ``action_replan`` row born
  ``PENDING`` in this same transaction (``NONE`` ⇒ zero rows — zero
  rows is "no obligation"), its ``replan_request_id`` derived
  ``f"rp:{gate_id}:{submission_id}"``; a replayed commit_action touches
  it never (the replay arm answers first); and ⑨ the **V3-7 memory arm**
  (STATE §25's "V3-7 落法"; TASK-OPI-d274a7fb…8): one ``EXPERIENCED``
  ``actor_memory`` row per event participant, through
  :func:`elc.world.memory.record_experienced_in_transaction` — content =
  the event's narration (the ruling's ``outcome``), learned_at_tick =
  the commit's ``actual_end``; the fresh path only, so a replay never
  double-lands memory.

**The replan obligation** (:func:`claim_replan_target` /
:func:`mark_replan_applied`, the V3-6R HIGH-1): the ruling's
``replan_scope`` verdict is consumed **through the obligation**, never
by a bare plan face — ``ScenePlanner.replan_scene(replan_request_id, …)``
(``SCENE``) and ``Director.apply_action_replan(replan_request_id, …)``
(``CHAPTER``) are the two consumers, and the protocol is
``claim → work → complete`` (all three steps idempotent):
:func:`claim_replan_target` writes the target revision's identity into
``target_ref`` **before** the plan change executes (the eager claim —
a crash retry recomputes the same target and converges on the same
revision, never a second one); the plan change runs; the complete step
moves ``PENDING → APPLIED`` (refused while no claim stands — the
storage's composite CHECK is the same law one layer down). An
``APPLIED`` retry is a zero-write read of ``target_ref``.
:func:`replan_obligation` / :func:`pending_replans` are the read faces
(``PENDING`` in ``gate_id`` order — the recovery survey's fifth
family), and :func:`scene_of_action` resolves the obligation's durable
chain (obligation → action → gate → scene) for the two consumers.
- :func:`recovery_scan` — RA §29's scan face for this cut's families,
  plainly read: gates ``ANSWERED`` / ``RESOLVING``, actions
  ``RESOLVING``, scenes ``ACTIVE``, chapters ``ACTIVE`` / ``SETTLING``,
  **replan obligations ``PENDING``** (the V3-6R fifth family), — since
  V3-7 (TASK-OPI-d274a7fb…8, RA §29's "V3-7 落法") — the
  **``settling_chapters``** sixth family: the ``SETTLING`` subset of the
  chapter scan, distinctly named (NCP-4's crash anchor — the recovery
  face re-runs :func:`elc.world.settlement.settle_chapter`, which
  converges to ``CLOSED`` with the same one-version settlement row),
  and — since V3-8b (TASK-OPI-06b954e0…16 / ``DEC-OPI-06b954e0-…15``,
  the external review's HARD GATE) — the **``continuations``** seventh
  family: ``COMMITTED`` gates whose scene holds no passage carrying
  their action as its ``outcome_ref`` (:class:`ContinuationObligation`
  — the ruling nobody resumed past, with the continuation's
  ``next_segment_seq`` derived from the durable ``segment_commit``
  rows); each family deterministically ordered. The automatic resume
  编排 belongs to the pipeline cut; this face is the durable survey, and
  the semantics it carries are the contract's: after NCP-1 an
  interruption re-adjudicates with the **same ``submission_id``** (the
  unique outcome), and a replayed ``commit_action`` is a whole-group
  no-op.

**The adjudication is the only writer of the action's canon** (§2.6 /
DOMAIN §20.3-1): :class:`Adjudication` is the design's output shape
verbatim — ``interpretation`` / ``outcome`` / ``actual_action`` /
``consequences`` / ``state_effects`` / ``participants`` /
``replan_scope`` — and ``commit_action`` writes ``world_event`` /
``world_state_fact`` **only** from it. The submission's own words
(``intent_text`` / ``selected_option``) are durable on the
``user_action`` row and **never enter ``world_event`` or
``world_state_fact``** — intent is not a fact until the resolver rules.
The LLM/rule-driven resolver that *produces* the adjudication (the 拔剑
example's capability / possession / body / place / rule / counterpart /
environment rulings) is registered for the pipeline cut, the same
schema-and-table-side-only boundary V3-4/V3-5 spelled; this cut ships
the face that lands its verdict.

**``replan_scope`` is the ruling's own three-word verdict** (NONE /
SCENE / CHAPTER; §2.6's first version), recorded in the terminal
columns; the plan face's *consumption* is deliberately outside NCP-2's
transaction (STATE §25's "V3-6 落法") **and rides the obligation born in
it** (the V3-6R HIGH-1): ``SCENE`` goes to
:meth:`elc.world.scene.ScenePlanner.replan_scene` (a new dossier
revision, ``max + 1``), ``CHAPTER`` to
:meth:`elc.world.director.Director.apply_action_replan` — entered by
``replan_request_id``, whose residue decision mirrors
:meth:`elc.world.director.Director.revise_blueprint`'s own
(``revise_blueprint``'s semantics are untouched; the obligation face
composes the same law under the claim/complete protocol).

**The action family's derivation laws** (§26.2.4's named form, disjoint
from the ``sg:`` / ``-p{seq:04d}`` / ``-e{seq:04d}`` namespaces):
``commit_id = f"ac:{gate_id}:{submission_id}"``, ``event_id =
f"ac:{gate_id}:{submission_id}:event"``, ``action_commit_key =
(gate_id, submission_id)`` and, since V3-6R, ``replan_request_id =
f"rp:{gate_id}:{submission_id}"`` (the action key's stable function —
:func:`replan_request_id_for`). The shape comparison of a replayed
``commit_action`` covers the semantic payload (the four ruling texts,
the effects, the participants, ``replan_scope``, ``duration_ticks``)
and not the bookkeeping stamps (the SEGMENT COMMIT law, spelled once
next door).

**The chapter arm's replay answer is a read-time derivation**, the same
posture V3-5R registered for its own ``chapter_activated`` field: the
stored witness is the chapter's ``opened_at_tick`` against this
commit's ``actual_start_tick`` (a persisted second column is a later
cut's explicit reopening — the DECISION_REGISTER's observation).

Participants are the canonical identities (the V3-3R freeze): the
ruling's tuple must sit inside the world's ``participant_namespace``
and must **carry the user role** (``player_character_id``) — a user
action fact without the user is not a user action fact; both refusals
are ``VALIDATION_FAILED`` with human sentences. The namespace assembly
is the settlement's promoted one-truth face
(:func:`elc.world.settlement.participant_namespace_of`), which is why
:func:`commit_action` takes the same connection's world store beside
the narrative store (the chapter arm is the store's own
``_flip_chapter_activated_tx`` — the action module spells no second
copy of the #4 prerequisites). ``open_gate``'s scene read is this
module's own fixed-literal read of the durable rows (the face carries
no store; the rows are the same ones the narrative store's read faces
answer).

Discipline (the house store law): **value semantics** — every refusal
is a ``Result`` ``Err`` (``VALIDATION_FAILED`` for the caller's own
payload or move, ``NOT_FOUND`` for a dangling identity, ``CONFLICT``
for a shape clash with an existing row, ``DEPENDENCY_UNAVAILABLE`` for
the database's own failures); **no hidden clock** — every stamp rides
the caller's ``now``; **one short transaction** per write with the
began-flag posture; **no SQL string building** — fixed literals and
parameter binding only; the one ``f"..."`` that builds values builds
*identities* (``gate_id`` / ``user_action_id`` / ``commit_id`` /
``event_id``), never SQL; the Package is not consulted anywhere (the
durable rows are the runtime authority); a stored payload this module's
own codec family cannot decode raises ``ValueError`` (the store
family's corrupted-row posture).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.memory import record_experienced_in_transaction
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    WorldChapterRecord,
    WorldSceneRecord,
)
from elc.world.settlement import (
    participant_namespace_of,
    player_character_id_of,
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
    "ActionOutcome",
    "ActionReplanRecord",
    "ActionStatus",
    "Adjudication",
    "ContinuationObligation",
    "GateStatus",
    "RecoveryScan",
    "ReplanScope",
    "ReplanStatus",
    "UserActionRecord",
    "UserGateRecord",
    "action_by_id",
    "action_of",
    "begin_resolving",
    "claim_replan_target",
    "commit_action",
    "gates_of",
    "get_gate",
    "mark_replan_applied",
    "open_gate",
    "pending_replans",
    "recovery_scan",
    "replan_obligation",
    "replan_request_id_for",
    "scene_of_action",
    "submit_gate",
]


class GateStatus(StrEnum):
    """The ``user_gate`` row's five-word lifecycle (STATE_MACHINES §23,
    word for word).

    ``OPEN`` — the story stops here, waiting for the user; ``ANSWERED`` —
    a submission landed (NCP-1: gate and action row together);
    ``RESOLVING`` — the adjudication's durable stop (the provider call
    runs outside the database); ``COMMITTED`` — the ruling landed
    (NCP-2's terminal word); ``CLOSED`` — a later segment commit began
    the continuation (§22's "the writing resumed" form; **since V3-6R
    the close is explicit and targeted**: the fresh segment that
    carries this gate's action as its ``outcome_ref`` closes this gate
    in its own transaction — §23's V3-6R tightening ③, never a blanket
    close of every committed gate).
    """

    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    RESOLVING = "RESOLVING"
    COMMITTED = "COMMITTED"
    CLOSED = "CLOSED"


class ActionStatus(StrEnum):
    """The ``user_action`` row's three-word lifecycle (§23's gate words
    minus ``OPEN``, minus ``CLOSED``).

    The row is born ``ANSWERED`` (NCP-1 — there is no pre-submission
    action), steps through ``RESOLVING`` (:func:`begin_resolving`) and
    ends ``COMMITTED`` (NCP-2's eight terminal columns written at once,
    the storage's own composite CHECK backing the all-or-nothing).
    **Since V3-6R ``RESOLVING`` is the only door into ``COMMITTED``**:
    the deterministic resolver baseline's main path is
    ``begin_resolving → commit_action``, and an ``ANSWERED`` row
    reaching for the terminal word directly is refused (STATE §23's
    V3-6R tightening ① — one main path, no byway).
    """

    ANSWERED = "ANSWERED"
    RESOLVING = "RESOLVING"
    COMMITTED = "COMMITTED"


class ReplanScope(StrEnum):
    """The adjudication's three-word plan verdict (the design's §2.6
    first version, verbatim).

    ``NONE`` — the plan survives the user's move; ``SCENE`` — the current
    scene's plan is re-planned
    (:meth:`elc.world.scene.ScenePlanner.replan_scene`);
    ``CHAPTER`` — the chapter's remaining part is re-planned (the
    existing :meth:`elc.world.director.Director.revise_blueprint` face).
    The consumption is outside NCP-2's transaction (STATE §25's "V3-6
    落法"); a consumed plan never rounds back to the plan the user's
    choice invalidated (the non-railroad law, the design's §三).
    """

    NONE = "NONE"
    SCENE = "SCENE"
    CHAPTER = "CHAPTER"


class ReplanStatus(StrEnum):
    """The ``action_replan`` row's two-word lifecycle (migration 0036's
    CHECK, DATA §26.2.1's "V3-6R 落法" block verbatim).

    ``PENDING`` — the obligation is outstanding; ``APPLIED`` — the plan
    change landed and the obligation is discharged. There is no
    third word: ``NONE`` never births a row, so "no obligation" is zero
    rows, not a word.
    """

    PENDING = "PENDING"
    APPLIED = "APPLIED"


@dataclass(frozen=True)
class ActionReplanRecord:
    """One durable replan obligation (migration 0036's ``action_replan``).

    The row is born ``PENDING`` in NCP-2's own short transaction (arm ⑧,
    the V3-6R HIGH-1) and discharged by the plan face's
    ``claim → work → complete`` protocol. ``scope`` is the ruling's own
    word (``SCENE`` / ``CHAPTER``); ``target_ref`` is the claimed target
    revision's identity — ``dossier_id`` for ``SCENE``,
    ``chapter_plan_id`` for ``CHAPTER`` — written by
    :func:`claim_replan_target` before the plan change executes (the
    eager claim: a crash retry converges on the same revision), ``None``
    until then, and never ``None`` once ``status`` is ``APPLIED`` (the
    storage's composite CHECK).
    """

    replan_request_id: str
    user_action_id: str
    scope: ReplanScope
    status: ReplanStatus
    target_ref: str | None
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class UserGateRecord:
    """One gate row (migration 0035's ``user_gate``; DATA §26.2.1's "V3-6
    落表形" block).

    ``options`` is the strict participants codec's decode of
    ``options_json`` (a JSON array of strings — two to four, the opening
    face's own validation). ``opened_at_tick`` is the canonical story
    tick the opening face read inside its transaction.
    """

    gate_id: str
    scene_id: str
    status: GateStatus
    opened_at_tick: int
    options: tuple[str, ...]
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class UserActionRecord:
    """One user-action row (migration 0035's ``user_action``) — the
    submission's durable face and, once ``COMMITTED``, the ruling's.

    ``intent_text`` / ``selected_option`` are the user's own submission
    (an intent, never a fact). The eight terminal fields stay ``None``
    through ``ANSWERED`` / ``RESOLVING`` and are written all at once by
    :func:`commit_action`: ``state_effects`` decodes the canonical
    effects codec, ``participants`` the canonical participants codec,
    ``replan_scope`` the three-word ``ReplanScope``, ``actual_tick`` the
    post-advance ``actual_end`` (the ACTION family's canon time anchor).
    """

    user_action_id: str
    gate_id: str
    submission_id: str
    intent_text: str
    selected_option: str | None
    status: ActionStatus
    interpretation: str | None
    outcome: str | None
    actual_action: str | None
    consequences: str | None
    state_effects: tuple[StateEffect, ...] | None
    participants: tuple[str, ...] | None
    replan_scope: ReplanScope | None
    actual_tick: int | None
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class Adjudication:
    """The Action Resolver's verdict — the design's output shape
    verbatim (§2.6: "输出至少 interpretation / outcome / actual_action /
    consequences / state_effects / participants / replan_scope").

    The face that *produces* one (the LLM / rule-driven resolver reading
    capability, possession, body, place, world rules, the counterparts
    and the environment) is the pipeline cut's; this cut lands the
    verdict. ``commit_action`` writes the event and the state settlement
    **only** from this record — the submission's own words never reach
    canon (intent ≠ world fact).
    """

    interpretation: str
    outcome: str
    actual_action: str
    consequences: str
    state_effects: tuple[StateEffect, ...]
    participants: tuple[str, ...]
    replan_scope: ReplanScope


@dataclass(frozen=True)
class ActionOutcome:
    """One ACTION OUTCOME COMMIT's answer shape.

    ``user_action_id`` / ``event_id`` / ``commit_id`` are the derived
    identities of the landed rows; ``actual_start_tick`` /
    ``actual_end_tick`` the action's actual span (the current tick
    before the advance and after it); ``replan_scope`` the ruling's
    recorded verdict; ``chapter_activated`` says this action opened its
    chapter (the chapter was ``PLANNED`` and the ``opened_at_tick`` is
    this commit's own start — on a replay the answer is a read-time
    derivation, the same posture V3-5R registered for the segment
    commit's twin field).
    """

    user_action_id: str
    event_id: str
    commit_id: str
    actual_start_tick: int
    actual_end_tick: int
    replan_scope: ReplanScope
    chapter_activated: bool


@dataclass(frozen=True)
class ContinuationObligation:
    """One committed-unclosed gate's continuation obligation — RA §29's
    **seventh family** (V3-8b, TASK-OPI-06b954e0…16 /
    ``DEC-OPI-06b954e0-…15``, the external review's HARD GATE).

    A gate that reached ``COMMITTED`` but has not been resumed past
    (``CLOSED``) is a ruling whose continuation passage never landed —
    the crash window ``NCP-2 后崩溃`` at its most precise reading. The
    family restores exactly what a driver needs and nothing it would
    have to remember: ``scene_id`` (where the passage lands),
    ``gate_id`` (the story point), ``user_action_id`` (the committed
    ruling — the forced ``outcome_ref``) and ``next_segment_seq`` (the
    sequence the passage takes, **derived from the durable
    ``segment_commit`` rows**: ``max(segment_seq) + 1`` for the scene,
    the first segment's ``1`` — never a caller-supplied counter)."""

    scene_id: str
    gate_id: str
    user_action_id: str
    next_segment_seq: int


@dataclass(frozen=True)
class RecoveryScan:
    """RA §29's scan answer for this cut's families: gates
    ``ANSWERED`` / ``RESOLVING`` (not ``COMMITTED``), actions
    ``RESOLVING`` (not ``COMMITTED``), scenes ``ACTIVE``, chapters
    ``ACTIVE`` / ``SETTLING``, — since V3-6R — replan obligations
    ``PENDING`` (the durable anchor between a ruling and its plan face:
    the claim's ``target_ref`` is written before the work, so a retry
    converges on the same revision), and — since V3-7 — the
    ``settling_chapters`` family: the ``SETTLING`` subset of the chapter
    scan, surfaced as its own recovery semantic (NCP-4's crash anchor —
    a chapter interrupted inside the settlement re-runs
    :func:`elc.world.settlement.settle_chapter`, and the one-version-per-
    chapter PK makes the re-run a no-op; RA §29's "V3-7 落法"), and —
    since V3-8b — the ``continuations`` family: ``COMMITTED`` gates
    whose scene holds no passage carrying their action as its
    ``outcome_ref`` (:class:`ContinuationObligation`; the HARD GATE's
    durable-read face). Each tuple is deterministically ordered
    (``gate_id`` / ``user_action_id`` / ``(chapter_id, scene_index)`` /
    ``(world_id, chapter_index)`` / ``gate_id`` for the obligations /
    ``(world_id, chapter_index)`` for the settling family / ``gate_id``
    for the continuations), so a recovery walk replays the same survey
    byte for byte. ``chapters`` keeps its ``ACTIVE`` / ``SETTLING``
    rows intact — the sixth family is a distinctly-named subset, not a
    replacement.
    """

    gates: tuple[UserGateRecord, ...]
    actions: tuple[UserActionRecord, ...]
    scenes: tuple[WorldSceneRecord, ...]
    chapters: tuple[WorldChapterRecord, ...]
    settling_chapters: tuple[WorldChapterRecord, ...]
    replans: tuple[ActionReplanRecord, ...]
    continuations: tuple[ContinuationObligation, ...]


def open_gate(
    conn: sqlite3.Connection,
    *,
    scene_id: str,
    gate_seq: int,
    options: tuple[str, ...],
    now: str,
) -> Result[UserGateRecord]:
    """Open one gate on one ``ACTIVE`` scene — ``OPEN``, the story's
    stop (STATE §23; the module docstring spells the checks).

    Refusals, all value semantics, nothing written:

    - ``gate_seq`` not an integer ``>= 1`` (a bool is not an integer
      here) or ``options`` not two to four non-empty strings —
      ``VALIDATION_FAILED``;
    - the scene does not exist — ``NOT_FOUND``;
    - the scene is not ``ACTIVE`` — ``VALIDATION_FAILED``;
    - the scene already holds a gate short of ``CLOSED`` (``OPEN`` /
      ``ANSWERED`` / ``RESOLVING`` / a ``COMMITTED`` gate nobody resumed
      past) — ``VALIDATION_FAILED`` naming the standing gate and the
      close it owes (commit a continuing segment that carries its
      ``outcome_ref``; the V3-6R one-gate law, STATE §23's tightening
      ② — the check runs inside this short transaction);
    - the same ``gate_id`` with a different shape (the scene or the
      options differ) — ``CONFLICT``.

    A replay of the same ``gate_id`` answers the stored row unchanged —
    zero write, and the stored ``opened_at_tick`` stands (it is a minted
    canonical read, the create faces' own posture: the caller's shape is
    what must match). ``now`` stamps the row; the tick is read, never
    advanced.
    """

    if not isinstance(gate_seq, int) or isinstance(gate_seq, bool) or gate_seq < 1:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate of scene {scene_id!r} not opened: gate_seq"
                    f" must be an integer >= 1; got {gate_seq!r}"
                ),
            )
        )
    if isinstance(options, (str, bytes)) or not isinstance(
        options, (list, tuple)
    ):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate of scene {scene_id!r} not opened: options must"
                    " be a sequence of two to four non-empty strings; got"
                    f" {type(options).__name__}"
                ),
            )
        )
    words: list[str] = []
    for word in options:
        if not isinstance(word, str) or not word.strip():
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"gate of scene {scene_id!r} not opened: every"
                        " option must be a non-empty string; got"
                        f" {word!r}"
                    ),
                )
            )
        words.append(word)
    if not 2 <= len(words) <= 4:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate of scene {scene_id!r} not opened: a gate"
                    " carries two to four natural behaviour options (the"
                    " free-text arm is implied); got"
                    f" {len(words)}"
                ),
            )
        )

    gate_id = f"{scene_id}-g{gate_seq:02d}"
    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _open_gate_tx(
            conn,
            scene_id=scene_id,
            gate_id=gate_id,
            options=tuple(words),
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
                message=f"gate {gate_id!r} not opened: {exc}",
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _open_gate_tx(
    conn: sqlite3.Connection,
    *,
    scene_id: str,
    gate_id: str,
    options: tuple[str, ...],
    now: str,
) -> Result[UserGateRecord]:
    """The opening face's body, inside the caller's transaction (the
    public :func:`open_gate` owns the BEGIN/COMMIT — the arm/owner split
    the settlement and the narrative store's flips spell)."""

    scene = conn.execute(
        "SELECT s.status, c.world_id FROM world_scene s"
        " JOIN world_chapter c ON c.chapter_id = s.chapter_id"
        " WHERE s.scene_id = ?",
        (scene_id,),
    ).fetchone()
    if scene is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"gate {gate_id!r} not opened: scene {scene_id!r}"
                    " does not exist"
                ),
            )
        )
    scene_status = str(scene[0])
    world_id = str(scene[1])

    # The replay read runs before the fresh path's gates (the house
    # posture: a stored row answers first, whatever moved since).
    existing = _gate_row(conn, gate_id)
    if existing is not None:
        if (existing.scene_id, existing.options) == (scene_id, options):
            return Ok(existing)
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"gate {gate_id!r} already exists with a different"
                    " shape (its scene is"
                    f" {existing.scene_id!r}, its options"
                    f" {existing.options!r}); a gate identity does not"
                    " rewrite"
                ),
            )
        )
    if scene_status != "ACTIVE":
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not opened: scene {scene_id!r} is"
                    f" {scene_status!r}; only an ACTIVE scene takes a"
                    " gate (the story stops inside a running scene)"
                ),
            )
        )
    standing = conn.execute(
        "SELECT gate_id, status FROM user_gate WHERE scene_id = ?"
        " AND status != 'CLOSED'"
        " ORDER BY gate_id ASC",
        (scene_id,),
    ).fetchone()
    if standing is not None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not opened: scene {scene_id!r}"
                    " already holds the standing gate"
                    f" {str(standing[0])!r} (its status is"
                    f" {str(standing[1])!r}) — a scene stops at one gate"
                    " at a time (STATE §23); close the previous gate"
                    " first by committing a continuing segment that"
                    " carries its outcome_ref (the V3-6R one-gate law)"
                ),
            )
        )
    tick = read_current_tick(conn, world_id)
    if isinstance(tick, Err):
        return Err(tick.error)
    conn.execute(
        "INSERT INTO user_gate ("
        " gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version"
        ") VALUES (?, ?, 'OPEN', ?, ?, ?, ?, 1)",
        (
            gate_id,
            scene_id,
            tick.value,
            encode_participants(options),
            now,
            now,
        ),
    )
    created = _gate_row(conn, gate_id)
    assert created is not None  # the INSERT above just landed it
    return Ok(created)


def submit_gate(
    conn: sqlite3.Connection,
    *,
    gate_id: str,
    submission_id: str,
    intent_text: str,
    selected_option: str | None = None,
    now: str,
) -> Result[UserActionRecord]:
    """Land the user's submission — **NCP-1**'s one short transaction
    (STATE §23 / RA §28): the gate ``OPEN → ANSWERED`` and the
    ``user_action`` row's birth land together, before any adjudication
    call (this point must succeed before the provider runs).

    Refusals, all value semantics, nothing written:

    - ``submission_id`` / ``intent_text`` not non-empty strings, or
      ``selected_option`` not a string when given —
      ``VALIDATION_FAILED``;
    - the gate does not exist — ``NOT_FOUND``;
    - the same ``(gate_id, submission_id)`` with a different shape
      (``intent_text`` / ``selected_option``) — ``CONFLICT``;
    - ``selected_option`` is not one of the gate's recorded options —
      ``VALIDATION_FAILED`` (the message names the option and the
      gate's own list);
    - the gate is not ``OPEN`` and this is not its replay —
      ``VALIDATION_FAILED`` (one gate accepts exactly one submission).

    A replay of the same ``(gate_id, submission_id)`` with the same
    shape rides back as the stored row — zero write, whatever the row's
    lifecycle word is since (a replayed NCP-1 after the ruling is still
    the same submission).
    """

    if not isinstance(submission_id, str) or not submission_id.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not submitted: submission_id must"
                    " be a non-empty string (the idempotency anchor's"
                    f" half); got {submission_id!r}"
                ),
            )
        )
    if not isinstance(intent_text, str) or not intent_text.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not submitted: intent_text must be"
                    " a non-empty string — the user's own words are the"
                    f" submission; got {intent_text!r}"
                ),
            )
        )
    if selected_option is not None and not isinstance(selected_option, str):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not submitted: selected_option"
                    " must be a string when given; got"
                    f" {selected_option!r}"
                ),
            )
        )
    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _submit_gate_tx(
            conn,
            gate_id=gate_id,
            submission_id=submission_id,
            intent_text=intent_text,
            selected_option=selected_option,
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
                message=f"gate {gate_id!r} not submitted: {exc}",
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _submit_gate_tx(
    conn: sqlite3.Connection,
    *,
    gate_id: str,
    submission_id: str,
    intent_text: str,
    selected_option: str | None,
    now: str,
) -> Result[UserActionRecord]:
    """NCP-1's body, inside the caller's transaction (the atomic group:
    the gate's flip and the action row's birth — or neither)."""

    gate = _gate_row(conn, gate_id)
    if gate is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"gate {gate_id!r} not submitted: it does not exist"
                ),
            )
        )

    # The replay read (§26.2.4's anchor: the same submission answers the
    # stored row whatever moved since).
    existing = _action_row_by_submission(conn, gate_id, submission_id)
    if existing is not None:
        if (existing.intent_text, existing.selected_option) == (
            intent_text,
            selected_option,
        ):
            return Ok(existing)
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"submission {submission_id!r} of gate {gate_id!r}"
                    " already landed with a different shape (its"
                    f" intent_text is {existing.intent_text!r}, its"
                    f" selected_option {existing.selected_option!r}); the"
                    " submission is claimed and does not rewrite"
                ),
            )
        )

    if selected_option is not None and selected_option not in gate.options:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not submitted: selected_option"
                    f" {selected_option!r} is not one of the gate's"
                    f" recorded options {gate.options!r}"
                ),
            )
        )
    if gate.status is not GateStatus.OPEN:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not submitted: it is"
                    f" {gate.status.value!r}; one gate accepts exactly"
                    " one submission (NCP-1), so the move is legal only"
                    " from OPEN"
                ),
            )
        )

    cursor = conn.execute(
        "UPDATE user_gate SET status = 'ANSWERED',"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE gate_id = ? AND state_version = ?",
        (now, gate_id, gate.state_version),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM user_gate WHERE gate_id = ?"
            ),
            row_id=gate_id,
            noun="gate",
        )
    user_action_id = f"{gate_id}-a"
    conn.execute(
        "INSERT INTO user_action ("
        " user_action_id, gate_id, submission_id, intent_text,"
        " selected_option, status, created_at, updated_at, state_version"
        ") VALUES (?, ?, ?, ?, ?, 'ANSWERED', ?, ?, 1)",
        (
            user_action_id,
            gate_id,
            submission_id,
            intent_text,
            selected_option,
            now,
            now,
        ),
    )
    created = _action_row(conn, user_action_id)
    assert created is not None  # the INSERT above just landed it
    return Ok(created)


def begin_resolving(
    conn: sqlite3.Connection,
    *,
    gate_id: str,
    now: str,
) -> Result[tuple[UserGateRecord, UserActionRecord]]:
    """Step the answered gate into ``RESOLVING`` — both rows in one short
    transaction (STATE §23: the durable stop before the
    transaction-external adjudication).

    Refusals, all value semantics, nothing written: the gate does not
    exist — ``NOT_FOUND``; a gate in ``OPEN`` has nothing submitted to
    resolve and a ``COMMITTED`` / ``CLOSED`` gate is past this step —
    ``VALIDATION_FAILED``; a gate whose submission row is missing is
    dangling — ``NOT_FOUND``. A re-call from ``RESOLVING`` is
    **idempotent**: the stored pair rides back unchanged (zero write).
    """

    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _begin_resolving_tx(conn, gate_id=gate_id, now=now)
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
                message=f"gate {gate_id!r} not moved: {exc}",
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _begin_resolving_tx(
    conn: sqlite3.Connection, *, gate_id: str, now: str
) -> Result[tuple[UserGateRecord, UserActionRecord]]:
    """The ``ANSWERED → RESOLVING`` move's body, inside the caller's
    transaction (two CAS flips, one group)."""

    gate = _gate_row(conn, gate_id)
    if gate is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"gate {gate_id!r} not moved to RESOLVING: it does"
                    " not exist"
                ),
            )
        )
    if gate.status in (GateStatus.COMMITTED, GateStatus.CLOSED):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not moved to RESOLVING: it is"
                    f" {gate.status.value!r} — a committed ruling does"
                    " not step back (STATE §23)"
                ),
            )
        )
    if gate.status is GateStatus.OPEN:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"gate {gate_id!r} not moved to RESOLVING: it is"
                    " OPEN — nothing has been submitted to resolve"
                    " (submit first; NCP-1)"
                ),
            )
        )
    user_action_id = f"{gate_id}-a"
    action = _action_row(conn, user_action_id)
    if action is None:  # the FK makes this unreachable; answered honestly
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"gate {gate_id!r} not moved to RESOLVING: its"
                    f" submission row {user_action_id!r} does not exist"
                ),
            )
        )
    if gate.status is GateStatus.RESOLVING:
        return Ok((gate, action))

    cursor = conn.execute(
        "UPDATE user_gate SET status = 'RESOLVING',"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE gate_id = ? AND state_version = ?",
        (now, gate_id, gate.state_version),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM user_gate WHERE gate_id = ?"
            ),
            row_id=gate_id,
            noun="gate",
        )
    cursor = conn.execute(
        "UPDATE user_action SET status = 'RESOLVING',"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE user_action_id = ? AND state_version = ?",
        (now, user_action_id, action.state_version),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM user_action"
                " WHERE user_action_id = ?"
            ),
            row_id=user_action_id,
            noun="user action",
        )
    moved_gate = _gate_row(conn, gate_id)
    moved_action = _action_row(conn, user_action_id)
    assert moved_gate is not None  # the UPDATE above just touched it
    assert moved_action is not None
    return Ok((moved_gate, moved_action))


def commit_action(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    narrative_store: SqliteNarrativeStore,
    gate_id: str,
    submission_id: str,
    adjudication: Adjudication,
    duration_ticks: int,
    now: str,
) -> Result[ActionOutcome]:
    """Land the user action's ruling — **NCP-2**'s one short atomic
    group (STATE §25's "V3-6 落法"; the module docstring lists the
    arms). ``duration_ticks`` is the ruling's story-time cost (``>= 0``:
    the actual tick never moves backwards).

    Refusals, all value semantics, the whole group rolling back:

    - the gate does not exist — ``NOT_FOUND``;
    - nothing has been submitted (no action row) or the given
      ``submission_id`` differs from the stored row's —
      ``VALIDATION_FAILED`` (the message names both);
    - ``adjudication`` not an :class:`Adjudication`, ``duration_ticks``
      negative or not an integer, a ruling text not a string, an effects
      entry not a :class:`StateEffect`, one canonical effect key twice
      in one ruling, a participants word that is not a string, or
      ``replan_scope`` not a :class:`ReplanScope` word —
      ``VALIDATION_FAILED``;
    - the ruling's participants not inside the world's canonical
      ``participant_namespace``, or the ruling's participants missing
      the world's user role (``player_character_id``) —
      ``VALIDATION_FAILED`` (a user action fact without the user is not
      a user action fact);
    - the same ``action_commit_key = (gate_id, submission_id)`` with a
      different shape — ``CONFLICT`` (the ruling landed once and does
      not rewrite; the compared shape is the semantic payload, the
      bookkeeping stamps excluded, the SEGMENT COMMIT law);
    - the action (or its gate) not ``RESOLVING`` — ``VALIDATION_FAILED``
      naming ``begin_resolving`` (the V3-6R tightening ①: the ruling
      enters ``COMMITTED`` only through the resolver's own durable
      stop; an ``ANSWERED`` row has not passed it).

    A gate already ``COMMITTED`` (this key's ruling landed, a replay)
    answers the stored outcome: shape-equal rides back as a whole-group
    no-op (no second event, no tick re-advance, no span re-write, no
    lineage row, no re-flip, no second obligation), shape-different is
    the ``CONFLICT`` above.
    """

    if not isinstance(adjudication, Adjudication):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: the"
                    " adjudication must be an Adjudication record; got"
                    f" {type(adjudication).__name__}"
                ),
            )
        )
    if (
        not isinstance(duration_ticks, int)
        or isinstance(duration_ticks, bool)
        or duration_ticks < 0
    ):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed:"
                    f" duration_ticks {duration_ticks!r} must be an"
                    " integer >= 0 — the actual tick never moves"
                    " backwards (STATE §26)"
                ),
            )
        )
    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _commit_action_tx(
            conn,
            world_store=world_store,
            narrative_store=narrative_store,
            gate_id=gate_id,
            submission_id=submission_id,
            adjudication=adjudication,
            duration_ticks=duration_ticks,
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
                    f"action of gate {gate_id!r} not committed: {exc}"
                ),
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _commit_action_tx(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    narrative_store: SqliteNarrativeStore,
    gate_id: str,
    submission_id: str,
    adjudication: Adjudication,
    duration_ticks: int,
    now: str,
) -> Result[ActionOutcome]:
    """NCP-2's body, inside the caller's transaction (the arm list of
    STATE §25's "V3-6 落法" plus the V3-6R block's own moves — the ④b
    span arm, the ⑧ obligation and the RESOLVING-only door, spelled
    there once)."""

    gate = _gate_row(conn, gate_id)
    if gate is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"action of gate {gate_id!r} not committed: the gate"
                    " does not exist"
                ),
            )
        )
    user_action_id = f"{gate_id}-a"
    action = _action_row(conn, user_action_id)
    if action is None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: nothing"
                    " has been submitted (submit first; NCP-1) — a"
                    " ruling adjudicates a submission"
                ),
            )
        )
    if action.submission_id != submission_id:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: the"
                    f" stored submission is {action.submission_id!r}, the"
                    f" given one {submission_id!r} — the ruling is the"
                    " stored submission's (the anchor does not swap)"
                ),
            )
        )

    # The payload's own checks (before the replay read — a malformed
    # ruling is the caller's mistake whether or not the action landed).
    for label, text in (
        ("interpretation", adjudication.interpretation),
        ("outcome", adjudication.outcome),
        ("actual_action", adjudication.actual_action),
        ("consequences", adjudication.consequences),
    ):
        if not isinstance(text, str):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"action of gate {gate_id!r} not committed: the"
                        f" ruling's {label} must be a string; got"
                        f" {type(text).__name__}"
                    ),
                )
            )
    seen_keys: set[str] = set()
    for effect in adjudication.state_effects:
        if not isinstance(effect, StateEffect):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"action of gate {gate_id!r} not committed: the"
                        " ruling's effects must be StateEffect entries;"
                        f" got {type(effect).__name__}"
                    ),
                )
            )
        if effect.key in seen_keys:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"action of gate {gate_id!r} not committed:"
                        f" canonical key {effect.key!r} appears twice in"
                        " one ruling (one event, one claim per key);"
                        " nothing was written"
                    ),
                )
            )
        seen_keys.add(effect.key)
    for word in adjudication.participants:
        if not isinstance(word, str):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"action of gate {gate_id!r} not committed: the"
                        " ruling's participants carries a non-string"
                        f" entry {word!r}"
                    ),
                )
            )
    if not isinstance(adjudication.replan_scope, ReplanScope):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed:"
                    " replan_scope must be a ReplanScope word; got"
                    f" {adjudication.replan_scope!r}"
                ),
            )
        )

    if action.status is ActionStatus.COMMITTED:
        return _replay_action(
            conn,
            narrative_store=narrative_store,
            action=action,
            adjudication=adjudication,
            duration_ticks=duration_ticks,
        )

    # The RESOLVING-only door (V3-6R tightening ①, STATE §23): since this
    # correction the ruling enters COMMITTED only from the resolver's own
    # durable stop — the replay arm above answered first, so a stored
    # ruling still rides back whatever moved since.
    if action.status is not ActionStatus.RESOLVING:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: the action"
                    f" row is {action.status.value!r} — since V3-6R the"
                    " ruling enters COMMITTED only from RESOLVING; call"
                    " begin_resolving after the submission (STATE §23's"
                    " V3-6R tightening ① — one main path, no byway)"
                ),
            )
        )
    if gate.status is not GateStatus.RESOLVING:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: the gate is"
                    f" {gate.status.value!r} — since V3-6R the ruling enters"
                    " COMMITTED only from RESOLVING (call begin_resolving"
                    " after the submission; STATE §23's V3-6R tightening ①)"
                ),
            )
        )

    scene = narrative_store.get_scene(gate.scene_id)
    if scene is None:  # the FK makes this unreachable; answered honestly
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"action of gate {gate_id!r} not committed: scene"
                    f" {gate.scene_id!r} does not exist"
                ),
            )
        )
    chapter = narrative_store.get_chapter(scene.chapter_id)
    if chapter is None:  # the FK makes this unreachable; answered honestly
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"action of gate {gate_id!r} not committed: chapter"
                    f" {scene.chapter_id!r} does not exist"
                ),
            )
        )
    world_id = chapter.world_id

    namespace = participant_namespace_of(
        conn, world_store=world_store, world_id=world_id
    )
    player_id = player_character_id_of(conn, world_id)
    if player_id is None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: world"
                    f" {world_id!r} declares no user role"
                    " (world_player_character) — a user action fact"
                    " carries the user, and there is none to carry"
                ),
            )
        )
    for word in adjudication.participants:
        if word not in namespace:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"action of gate {gate_id!r} not committed:"
                        f" participant {word!r} is not a canonical"
                        " participant identity — the namespace is the"
                        " durable cast's actor ids union the player"
                        " character id (V3-3R freeze)"
                    ),
                )
            )
    if player_id not in adjudication.participants:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"action of gate {gate_id!r} not committed: the"
                    " ruling's participants do not carry the user role"
                    f" {player_id!r} — a user action fact without the"
                    " user is not a user action fact"
                ),
            )
        )

    tick = read_current_tick(conn, world_id)
    if isinstance(tick, Err):
        return Err(tick.error)
    actual_start = tick.value
    actual_end = actual_start + duration_ticks
    commit_id = f"ac:{gate_id}:{submission_id}"
    event_id = f"{commit_id}:event"

    # ① the action's terminal face — the eight columns at once
    # (actual_tick = the post-advance actual_end: the ACTION family's
    # canon time anchor).
    cursor = conn.execute(
        "UPDATE user_action SET status = 'COMMITTED',"
        " interpretation = ?, outcome = ?, actual_action = ?,"
        " consequences = ?, state_effects = ?, participants = ?,"
        " replan_scope = ?, actual_tick = ?,"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE user_action_id = ? AND state_version = ?",
        (
            adjudication.interpretation,
            adjudication.outcome,
            adjudication.actual_action,
            adjudication.consequences,
            encode_effects(adjudication.state_effects),
            encode_participants(adjudication.participants),
            adjudication.replan_scope.value,
            actual_end,
            now,
            user_action_id,
            action.state_version,
        ),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM user_action"
                " WHERE user_action_id = ?"
            ),
            row_id=user_action_id,
            noun="user action",
        )
    # ② the behaviour fact — written only from the ruling (the
    # submission's own words never reach canon).
    conn.execute(
        "INSERT INTO world_event ("
        " event_id, world_id, kind, narration, effects, occurred_at,"
        " source, participants, run_id"
        ") VALUES (?, ?, 'action', ?, ?, ?, 'v3-action', ?, NULL)",
        (
            event_id,
            world_id,
            adjudication.outcome,
            encode_effects(adjudication.state_effects),
            now,
            encode_participants(adjudication.participants),
        ),
    )
    # ③ the state settlement — the world store's one truth.
    _settle_effects_in_transaction(
        conn, world_id, event_id, adjudication.state_effects, now
    )
    # ④ the tick — the commit transaction is its only mover, and the
    # chapter's opening stamp reads this transaction's own value.
    advanced = advance_current_tick(conn, world_id, duration_ticks)
    if isinstance(advanced, Err):
        return Err(advanced.error)
    # ④b the scene's actual span — the V3-6R span law (STATE §26's two
    # callers of one UPDATE): NCP-2 extends the scene's actual interval
    # through the narrative store's shared arm and never closes a scene
    # (close_scene=False) — a gate's action carries no SCENE COMMIT; the
    # ACTIVE → COMMITTED flip stays the last SEGMENT's.
    span = narrative_store._advance_scene_actual_span_tx(
        gate.scene_id,
        actual_start,
        actual_end,
        False,
        now,
        expected_state_version=scene.state_version,
    )
    if isinstance(span, Err):
        return Err(span.error)
    # ⑤ the lineage row — ACTION_OUTCOME: the action_id rides, the
    # passage's columns stay empty, and is_last_segment is 0 (the flip
    # stays the last SEGMENT's; the span it extends is ④b's own move).
    conn.execute(
        "INSERT INTO segment_commit ("
        " commit_id, kind, scene_id, segment_seq, passage_id, action_id,"
        " actual_start_tick, actual_end_tick, event_id, is_last_segment,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'ACTION_OUTCOME', ?, NULL, NULL, ?, ?, ?, ?, 0,"
        " ?, ?, 1)",
        (
            commit_id,
            gate.scene_id,
            user_action_id,
            actual_start,
            actual_end,
            event_id,
            now,
            now,
        ),
    )
    # ⑥ the gate's flip — RESOLVING is the only door in (the tightening
    # above is the same law one layer up; the CAS guard is its redundancy
    # at the write).
    cursor = conn.execute(
        "UPDATE user_gate SET status = 'COMMITTED',"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE gate_id = ? AND state_version = ?"
        " AND status = 'RESOLVING'",
        (now, gate_id, gate.state_version),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM user_gate WHERE gate_id = ?"
            ),
            row_id=gate_id,
            noun="gate",
        )
    # ⑦ the chapter's opening — the narrative store's own arm, the same
    # #3 law NCP-3 keeps: the first segment or the first action ruling
    # opens the chapter with the transaction's own read of the tick.
    chapter_activated = False
    if chapter.status is ChapterStatus.PLANNED:
        opened = narrative_store._flip_chapter_activated_tx(
            chapter.chapter_id, actual_start, now, chapter.state_version
        )
        if isinstance(opened, Err):
            return Err(opened.error)
        chapter_activated = True
    # ⑧ the replan obligation's birth — the V3-6R HIGH-1: a ruling whose
    # scope is not NONE leaves a durable PENDING obligation in this same
    # transaction (NONE leaves zero rows — "no obligation" is zero rows,
    # not a word); a replayed commit never reaches this arm (the replay
    # read answered first), so the row is born exactly once.
    if adjudication.replan_scope is not ReplanScope.NONE:
        conn.execute(
            "INSERT INTO action_replan ("
            " replan_request_id, user_action_id, scope, status,"
            " target_ref, created_at, updated_at, state_version"
            ") VALUES (?, ?, ?, 'PENDING', NULL, ?, ?, 1)",
            (
                replan_request_id_for(gate_id, submission_id),
                user_action_id,
                adjudication.replan_scope.value,
                now,
                now,
            ),
        )
    # ⑨ the V3-7 memory arm (STATE §25's "V3-7 落法"): every participant
    # of the action's event lived it — one EXPERIENCED row each, landed
    # in this same transaction through the shared arm (content = the
    # event's narration, the ruling's outcome). The replay arm above
    # answered first, so a replayed ruling never double-lands memory.
    record_experienced_in_transaction(
        conn,
        world_id=world_id,
        event_id=event_id,
        participants=adjudication.participants,
        content=adjudication.outcome,
        learned_at_tick=actual_end,
        now=now,
    )

    return Ok(
        ActionOutcome(
            user_action_id=user_action_id,
            event_id=event_id,
            commit_id=commit_id,
            actual_start_tick=actual_start,
            actual_end_tick=actual_end,
            replan_scope=adjudication.replan_scope,
            chapter_activated=chapter_activated,
        )
    )


def _replay_action(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
    action: UserActionRecord,
    adjudication: Adjudication,
    duration_ticks: int,
) -> Result[ActionOutcome]:
    """Answer a replayed ``action_commit_key``: shape-equal rides back as
    the stored outcome, shape-different is a ``CONFLICT``.

    The compared shape is the semantic payload — the four ruling texts,
    the decoded effects and participants, the ``replan_scope`` word and
    the ruling's ``duration_ticks`` (the lineage span's difference) —
    never the bookkeeping stamps (the SEGMENT COMMIT law: a replay
    carries a fresh ``now``). The eight terminal columns are NOT NULL
    together under the storage's own composite CHECK, so a ``COMMITTED``
    row always answers. ``chapter_activated`` is the read-time
    derivation V3-5R registered for its twin field (the stored
    ``opened_at_tick`` against this commit's ``actual_start_tick``).
    """

    assert action.interpretation is not None  # the composite CHECK
    assert action.outcome is not None
    assert action.actual_action is not None
    assert action.consequences is not None
    assert action.state_effects is not None
    assert action.participants is not None
    assert action.replan_scope is not None
    lineage = conn.execute(
        "SELECT commit_id, event_id, actual_start_tick, actual_end_tick"
        " FROM segment_commit WHERE action_id = ?"
        " AND kind = 'ACTION_OUTCOME'",
        (action.user_action_id,),
    ).fetchone()
    assert lineage is not None  # the commit landed the row in its own group
    commit_id = str(lineage[0])
    event_id = str(lineage[1])
    actual_start = int(lineage[2])
    actual_end = int(lineage[3])
    stored_shape = (
        action.interpretation,
        action.outcome,
        action.actual_action,
        action.consequences,
        action.state_effects,
        action.participants,
        action.replan_scope,
        actual_end - actual_start,
    )
    given_shape = (
        adjudication.interpretation,
        adjudication.outcome,
        adjudication.actual_action,
        adjudication.consequences,
        adjudication.state_effects,
        adjudication.participants,
        adjudication.replan_scope,
        duration_ticks,
    )
    if stored_shape != given_shape:
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"action {commit_id!r} already exists with a"
                    " different shape; a committed ruling is append-only"
                    " and does not rewrite"
                ),
            )
        )
    gate = _gate_row(conn, action.gate_id)
    assert gate is not None  # the FK makes it unreachable otherwise
    scene = narrative_store.get_scene(gate.scene_id)
    chapter = (
        None
        if scene is None
        else narrative_store.get_chapter(scene.chapter_id)
    )
    return Ok(
        ActionOutcome(
            user_action_id=action.user_action_id,
            event_id=event_id,
            commit_id=commit_id,
            actual_start_tick=actual_start,
            actual_end_tick=actual_end,
            replan_scope=action.replan_scope,
            chapter_activated=(
                chapter is not None
                and chapter.status is ChapterStatus.ACTIVE
                and chapter.opened_at_tick == actual_start
            ),
        )
    )


def get_gate(
    conn: sqlite3.Connection, gate_id: str
) -> UserGateRecord | None:
    """One gate row by id, or ``None`` (the pure column read — a missing
    id is an answer, not an error)."""

    return _gate_row(conn, gate_id)


def gates_of(
    conn: sqlite3.Connection, scene_id: str
) -> tuple[UserGateRecord, ...]:
    """One scene's gates, ``gate_id`` ascending (the derivation embeds
    the zero-padded ordinal, so the durable order is the gate order).
    Every lifecycle word rides out — history is rows, not errors."""

    rows = conn.execute(
        "SELECT gate_id FROM user_gate WHERE scene_id = ?"
        " ORDER BY gate_id ASC",
        (scene_id,),
    ).fetchall()
    return tuple(
        gate
        for gate in (_gate_row(conn, str(row[0])) for row in rows)
        if gate is not None
    )


def action_of(
    conn: sqlite3.Connection, gate_id: str
) -> UserActionRecord | None:
    """The gate's submission row — ``f"{gate_id}-a"`` — or ``None``
    (one gate, one action; the derivation is the row's identity)."""

    return _action_row(conn, f"{gate_id}-a")


def action_by_id(
    conn: sqlite3.Connection, user_action_id: str
) -> UserActionRecord | None:
    """One action row by its own id, or ``None`` — the pure column read
    (a missing id is an answer, not an error). The V3-8b sibling of
    :func:`action_of`: a consumer holding the ruling's identity directly
    (the replan obligation names its ``user_action_id``; the CHAPTER
    replan's trigger reads it through this face) need not re-derive it
    from a gate id."""

    return _action_row(conn, user_action_id)


# ---------------------------------------------------------------------------
# the replan obligation — the V3-6R HIGH-1's read faces and the
# claim → work → complete protocol (self-managed short transactions, the
# store faces' own posture)
# ---------------------------------------------------------------------------


def replan_request_id_for(gate_id: str, submission_id: str) -> str:
    """The obligation identity law: ``f"rp:{gate_id}:{submission_id}"`` —
    the stable function of the action family's ``action_commit_key``
    (§26.2.4; the ``ac:`` / ``sg:`` families' own sibling, a disjoint
    namespace). Serves idempotent replay only — narrative time
    attribution never rides an id's naming."""

    return f"rp:{gate_id}:{submission_id}"


def replan_obligation(
    conn: sqlite3.Connection, replan_request_id: str
) -> ActionReplanRecord | None:
    """One replan obligation by id, or ``None`` (the pure column read — a
    missing id is an answer, not an error). The two consumers enter
    through this face: the obligation is the ruling's plan verdict's
    durable anchor."""

    return _replan_row(conn, replan_request_id)


def pending_replans(
    conn: sqlite3.Connection,
) -> tuple[ActionReplanRecord, ...]:
    """Every outstanding obligation — ``status = 'PENDING'`` — in
    ``replan_request_id`` ascending order (the derivation embeds the
    gate's own order, so the durable order is the ruling order).
    ``APPLIED`` rows are discharged: history is rows, not errors. This
    face is the recovery survey's fifth family (RA §29's V3-6R 落法)."""

    rows = conn.execute(
        "SELECT replan_request_id FROM action_replan"
        " WHERE status = 'PENDING' ORDER BY replan_request_id ASC"
    ).fetchall()
    return tuple(
        record
        for record in (_replan_row(conn, str(row[0])) for row in rows)
        if record is not None
    )


def scene_of_action(
    conn: sqlite3.Connection, replan_request_id: str
) -> str | None:
    """The scene one obligation's action was taken in — the durable chain
    read ``obligation → user_action → user_gate`` — or ``None`` when a
    link is missing (answered honestly; the FK makes the action half
    unreachable, the read stays total all the same).

    The consumption path's chain resolver: ``ScenePlanner.replan_scene``
    and ``Director.apply_action_replan`` enter by ``replan_request_id``
    and carry no SQL of their own, so the walk lives here — one truth for
    both faces."""

    row = conn.execute(
        "SELECT g.scene_id FROM action_replan r"
        " JOIN user_action a ON a.user_action_id = r.user_action_id"
        " JOIN user_gate g ON g.gate_id = a.gate_id"
        " WHERE r.replan_request_id = ?",
        (replan_request_id,),
    ).fetchone()
    return None if row is None else str(row[0])


def claim_replan_target(
    conn: sqlite3.Connection,
    *,
    replan_request_id: str,
    target_ref: str,
    now: str,
) -> Result[ActionReplanRecord]:
    """Claim the plan work's own target revision — the first step of the
    ``claim → work → complete`` protocol (the V3-6R HIGH-1; STATE §25's
    "V3-6R 落法"). ``target_ref`` is the target revision's identity the
    caller computed (``dossier_id`` for SCENE, ``chapter_plan_id`` for
    CHAPTER); the claim writes it **before** the plan change executes —
    the eager claim, which is a crash retry's convergence anchor (a retry
    recomputes the same target or, when the target is already stored,
    rides it).

    Refusals and answers, all value semantics, nothing written on a
    refusal: ``target_ref`` not a non-empty string —
    ``VALIDATION_FAILED``; the obligation does not exist — ``NOT_FOUND``;
    ``status = 'PENDING'`` with an empty ``target_ref`` — the CAS write,
    the claimed row rides back; the **same** value already claimed —
    idempotent ``Ok`` (zero write); a **different** value claimed —
    ``CONFLICT`` (a claim does not rewrite); ``APPLIED`` — the stored row
    rides back (the plan change already landed; the caller answers its
    ``target_ref``). The read and the CAS write sit inside one
    ``BEGIN IMMEDIATE``, so no window lets a second writer claim a
    different target between them."""

    if not isinstance(target_ref, str) or not target_ref.strip():
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"replan obligation {replan_request_id!r} not"
                    " claimed: target_ref must be a non-empty string (the"
                    f" target revision's identity); got {target_ref!r}"
                ),
            )
        )
    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _claim_replan_target_tx(
            conn,
            replan_request_id=replan_request_id,
            target_ref=target_ref,
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
                    f"replan obligation {replan_request_id!r} not"
                    f" claimed: {exc}"
                ),
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _claim_replan_target_tx(
    conn: sqlite3.Connection,
    *,
    replan_request_id: str,
    target_ref: str,
    now: str,
) -> Result[ActionReplanRecord]:
    """The claim's body, inside the caller's transaction (the read and the
    CAS write — decided on the row this transaction itself sees)."""

    row = _replan_row(conn, replan_request_id)
    if row is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"replan obligation {replan_request_id!r} not"
                    " claimed: it does not exist"
                ),
            )
        )
    if row.status is ReplanStatus.APPLIED:
        return Ok(row)
    if row.target_ref is not None:
        if row.target_ref == target_ref:
            return Ok(row)  # the same claim already stands — zero write
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"replan obligation {replan_request_id!r} already"
                    f" claimed the target {row.target_ref!r}; the given"
                    f" one is {target_ref!r} — the claim is the crash"
                    " retry's convergence anchor and does not rewrite"
                ),
            )
        )
    cursor = conn.execute(
        "UPDATE action_replan SET target_ref = ?,"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE replan_request_id = ? AND state_version = ?"
        " AND status = 'PENDING' AND target_ref IS NULL",
        (target_ref, now, replan_request_id, row.state_version),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM action_replan"
                " WHERE replan_request_id = ?"
            ),
            row_id=replan_request_id,
            noun="replan obligation",
        )
    claimed = _replan_row(conn, replan_request_id)
    assert claimed is not None  # the UPDATE above just touched it
    return Ok(claimed)


def mark_replan_applied(
    conn: sqlite3.Connection,
    *,
    replan_request_id: str,
    now: str,
) -> Result[ActionReplanRecord]:
    """Discharge the obligation — the ``complete`` step of the
    ``claim → work → complete`` protocol: ``PENDING → APPLIED`` over a
    claimed ``target_ref``, in its own short transaction.

    Refusals and answers, all value semantics: the obligation does not
    exist — ``NOT_FOUND``; the row is ``PENDING`` with **no claim
    standing** (``target_ref`` empty) — ``VALIDATION_FAILED`` (the
    complete step is unwritable without a claim; the storage's composite
    CHECK is the same law one layer down); ``PENDING`` with a claim — the
    CAS write, the ``APPLIED`` row rides back; already ``APPLIED`` —
    idempotent ``Ok`` (zero write)."""

    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        outcome = _mark_replan_applied_tx(
            conn, replan_request_id=replan_request_id, now=now
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
                    f"replan obligation {replan_request_id!r} not"
                    f" applied: {exc}"
                ),
            )
        )
    conn.execute("COMMIT")
    return Ok(outcome.value)


def _mark_replan_applied_tx(
    conn: sqlite3.Connection,
    *,
    replan_request_id: str,
    now: str,
) -> Result[ActionReplanRecord]:
    """The complete step's body, inside the caller's transaction."""

    row = _replan_row(conn, replan_request_id)
    if row is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"replan obligation {replan_request_id!r} not"
                    " applied: it does not exist"
                ),
            )
        )
    if row.status is ReplanStatus.APPLIED:
        return Ok(row)
    if row.target_ref is None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"replan obligation {replan_request_id!r} not"
                    " applied: no claim stands (target_ref is empty) —"
                    " the complete step lands only over a claimed target"
                    " (the eager claim runs first; the storage's composite"
                    " CHECK is the same law one layer down)"
                ),
            )
        )
    cursor = conn.execute(
        "UPDATE action_replan SET status = 'APPLIED',"
        " state_version = state_version + 1, updated_at = ?"
        " WHERE replan_request_id = ? AND state_version = ?"
        " AND status = 'PENDING' AND target_ref IS NOT NULL",
        (now, replan_request_id, row.state_version),
    )
    if cursor.rowcount != 1:
        return _cas_miss(
            conn,
            version_sql=(
                "SELECT state_version FROM action_replan"
                " WHERE replan_request_id = ?"
            ),
            row_id=replan_request_id,
            noun="replan obligation",
        )
    applied = _replan_row(conn, replan_request_id)
    assert applied is not None  # the UPDATE above just touched it
    return Ok(applied)


def recovery_scan(
    conn: sqlite3.Connection,
    *,
    narrative_store: SqliteNarrativeStore,
) -> Result[RecoveryScan]:
    """RA §29's scan face for this cut's families (a pure read — no
    transaction of its own): gates ``ANSWERED`` / ``RESOLVING``, actions
    ``RESOLVING``, scenes ``ACTIVE``, chapters ``ACTIVE`` /
    ``SETTLING``, — since V3-6R — replan obligations ``PENDING`` (the
    fifth family; the claim's ``target_ref`` is written before the
    work, so a retry converges on the same revision), — since V3-7 —
    the sixth family ``settling_chapters``: the ``SETTLING`` subset of
    the chapter scan, distinctly named and deterministically ordered
    (RA §29's "V3-7 落法": the chapter interrupted inside NCP-4 re-runs
    :func:`elc.world.settlement.settle_chapter`, whose one-version PK
    carries the no-op), and — since V3-8b (the HARD GATE) — the
    **seventh family** ``continuations``: ``COMMITTED`` gates whose
    scene holds no ``narrative_passage`` carrying their action as its
    ``outcome_ref`` — a ruling nobody resumed past, with the
    continuation's own ``next_segment_seq`` derived from the durable
    ``segment_commit`` rows (RA §29's V3-8b 修订). The story's resume
    编排 belongs to the pipeline cut; the semantics this face carries
    are the contract's own: after NCP-1 an interruption re-adjudicates
    with the same ``submission_id`` (the unique outcome), and the
    scan's rows are the durable survey of a crashed pipeline, not an
    error.
    """

    gate_rows = conn.execute(
        "SELECT gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version FROM user_gate"
        " WHERE status IN ('ANSWERED','RESOLVING') ORDER BY gate_id ASC"
    ).fetchall()
    gates = tuple(_gate_record(row) for row in gate_rows)
    action_rows = conn.execute(
        "SELECT user_action_id, gate_id, submission_id, intent_text,"
        " selected_option, status, interpretation, outcome, actual_action,"
        " consequences, state_effects, participants, replan_scope,"
        " actual_tick, created_at, updated_at, state_version"
        " FROM user_action WHERE status = 'RESOLVING'"
        " ORDER BY user_action_id ASC"
    ).fetchall()
    actions = tuple(_action_record(row) for row in action_rows)
    scene_rows = conn.execute(
        "SELECT scene_id FROM world_scene WHERE status = 'ACTIVE'"
        " ORDER BY chapter_id ASC, scene_index ASC"
    ).fetchall()
    scenes = tuple(
        scene
        for scene in (
            narrative_store.get_scene(str(row[0])) for row in scene_rows
        )
        if scene is not None
    )
    chapter_rows = conn.execute(
        "SELECT chapter_id FROM world_chapter"
        " WHERE status IN ('ACTIVE','SETTLING')"
        " ORDER BY world_id ASC, chapter_index ASC"
    ).fetchall()
    chapters = tuple(
        chapter
        for chapter in (
            narrative_store.get_chapter(str(row[0]))
            for row in chapter_rows
        )
        if chapter is not None
    )
    settling_rows = conn.execute(
        "SELECT chapter_id FROM world_chapter WHERE status = 'SETTLING'"
        " ORDER BY world_id ASC, chapter_index ASC"
    ).fetchall()
    settling_chapters = tuple(
        chapter
        for chapter in (
            narrative_store.get_chapter(str(row[0]))
            for row in settling_rows
        )
        if chapter is not None
    )
    replans = pending_replans(conn)
    # The seventh family (V3-8b's HARD GATE): a COMMITTED gate with no
    # passage resuming it, and the continuation's own sequence — derived
    # here, from the durable lineage rows (max committed seq + 1; the
    # first segment's 1), never from a caller's counter.
    continuation_rows = conn.execute(
        "SELECT g.gate_id, g.scene_id, a.user_action_id,"
        " COALESCE((SELECT MAX(c.segment_seq) FROM segment_commit c"
        " WHERE c.scene_id = g.scene_id), 0) + 1"
        " FROM user_gate g"
        " JOIN user_action a ON a.gate_id = g.gate_id"
        " WHERE g.status = 'COMMITTED'"
        " AND NOT EXISTS ("
        " SELECT 1 FROM narrative_passage p"
        " WHERE p.scene_id = g.scene_id"
        " AND p.outcome_ref = a.user_action_id)"
        " ORDER BY g.gate_id ASC"
    ).fetchall()
    continuations = tuple(
        ContinuationObligation(
            scene_id=str(row[1]),
            gate_id=str(row[0]),
            user_action_id=str(row[2]),
            next_segment_seq=int(row[3]),
        )
        for row in continuation_rows
    )
    return Ok(
        RecoveryScan(
            gates=gates,
            actions=actions,
            scenes=scenes,
            chapters=chapters,
            settling_chapters=settling_chapters,
            replans=replans,
            continuations=continuations,
        )
    )


def _gate_row(
    conn: sqlite3.Connection, gate_id: str
) -> UserGateRecord | None:
    """One gate row by id, or ``None`` — the one read every face uses."""

    row = conn.execute(
        "SELECT gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version FROM user_gate"
        " WHERE gate_id = ?",
        (gate_id,),
    ).fetchone()
    if row is None:
        return None
    return _gate_record(row)


def _gate_record(row: Any) -> UserGateRecord:
    """One gate row tuple in the record shape (the strict codec over
    ``options_json``; a payload this codec family cannot decode raises
    ``ValueError`` — the store family's corrupted-row posture)."""

    decoded = decode_participants(str(row[4]))
    if isinstance(decoded, Err):
        raise ValueError(
            f"gate {str(row[0])!r} carries an undecodable options_json"
            f" column: {decoded.error.message}"
        )
    return UserGateRecord(
        gate_id=str(row[0]),
        scene_id=str(row[1]),
        status=GateStatus(str(row[2])),
        opened_at_tick=int(row[3]),
        options=decoded.value,
        created_at=str(row[5]),
        updated_at=str(row[6]),
        state_version=int(row[7]),
    )


def _action_row(
    conn: sqlite3.Connection, user_action_id: str
) -> UserActionRecord | None:
    """One action row by id, or ``None``."""

    row = conn.execute(
        "SELECT user_action_id, gate_id, submission_id, intent_text,"
        " selected_option, status, interpretation, outcome, actual_action,"
        " consequences, state_effects, participants, replan_scope,"
        " actual_tick, created_at, updated_at, state_version"
        " FROM user_action WHERE user_action_id = ?",
        (user_action_id,),
    ).fetchone()
    if row is None:
        return None
    return _action_record(row)


def _action_row_by_submission(
    conn: sqlite3.Connection, gate_id: str, submission_id: str
) -> UserActionRecord | None:
    """One action row by the idempotency anchor — ``(gate_id,
    submission_id)`` (§26.2.4's UNIQUE) — or ``None``."""

    row = conn.execute(
        "SELECT user_action_id, gate_id, submission_id, intent_text,"
        " selected_option, status, interpretation, outcome, actual_action,"
        " consequences, state_effects, participants, replan_scope,"
        " actual_tick, created_at, updated_at, state_version"
        " FROM user_action WHERE gate_id = ? AND submission_id = ?",
        (gate_id, submission_id),
    ).fetchone()
    if row is None:
        return None
    return _action_record(row)


def _action_record(row: Any) -> UserActionRecord:
    """One action row tuple in the record shape (the strict codecs over
    the terminal pair; a payload this module's own codec family cannot
    decode raises ``ValueError``)."""

    effects: tuple[StateEffect, ...] | None = None
    if row[10] is not None:
        decoded_effects = decode_effects(str(row[10]))
        if isinstance(decoded_effects, Err):
            raise ValueError(
                f"user action {str(row[0])!r} carries an undecodable"
                f" state_effects column: {decoded_effects.error.message}"
            )
        effects = decoded_effects.value
    participants: tuple[str, ...] | None = None
    if row[11] is not None:
        decoded_participants = decode_participants(str(row[11]))
        if isinstance(decoded_participants, Err):
            raise ValueError(
                f"user action {str(row[0])!r} carries an undecodable"
                f" participants column: {decoded_participants.error.message}"
            )
        participants = decoded_participants.value
    return UserActionRecord(
        user_action_id=str(row[0]),
        gate_id=str(row[1]),
        submission_id=str(row[2]),
        intent_text=str(row[3]),
        selected_option=None if row[4] is None else str(row[4]),
        status=ActionStatus(str(row[5])),
        interpretation=None if row[6] is None else str(row[6]),
        outcome=None if row[7] is None else str(row[7]),
        actual_action=None if row[8] is None else str(row[8]),
        consequences=None if row[9] is None else str(row[9]),
        state_effects=effects,
        participants=participants,
        replan_scope=(
            None if row[12] is None else ReplanScope(str(row[12]))
        ),
        actual_tick=None if row[13] is None else int(row[13]),
        created_at=str(row[14]),
        updated_at=str(row[15]),
        state_version=int(row[16]),
    )


def _replan_row(
    conn: sqlite3.Connection, replan_request_id: str
) -> ActionReplanRecord | None:
    """One obligation row by id, or ``None`` — the one read every face
    uses. A stored word this module's own enums cannot decode raises
    ``ValueError`` (the store family's corrupted-row posture — the enum
    constructors are the codec)."""

    row = conn.execute(
        "SELECT replan_request_id, user_action_id, scope, status,"
        " target_ref, created_at, updated_at, state_version"
        " FROM action_replan WHERE replan_request_id = ?",
        (replan_request_id,),
    ).fetchone()
    if row is None:
        return None
    return ActionReplanRecord(
        replan_request_id=str(row[0]),
        user_action_id=str(row[1]),
        scope=ReplanScope(str(row[2])),
        status=ReplanStatus(str(row[3])),
        target_ref=None if row[4] is None else str(row[4]),
        created_at=str(row[5]),
        updated_at=str(row[6]),
        state_version=int(row[7]),
    )


def _cas_miss(
    conn: sqlite3.Connection,
    *,
    version_sql: str,
    row_id: str,
    noun: str,
) -> Err[Any]:
    """The CAS miss's two honest answers — the row is gone
    (``NOT_FOUND``) or another writer moved it first (``CONFLICT``);
    the same two-answer family the narrative store's ``_cas_miss``
    spells. ``version_sql`` rides only from this module's own closed
    call sites (no caller input reaches it)."""

    row = conn.execute(version_sql, (row_id,)).fetchone()
    if row is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"{noun} {row_id!r} not moved: it does not exist"
                ),
            )
        )
    return Err(
        DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"{noun} {row_id!r} not moved: another writer moved it"
                f" first (its state_version is now {int(row[0])}; the"
                " expected one is stale) — re-read and retry"
            ),
        )
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
