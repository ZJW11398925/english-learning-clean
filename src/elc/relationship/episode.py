"""Episode projection — the transcript-derived conversation summary.

docs/DATA_MODEL.md §5.3 owns the column set (:class:`EpisodeRecord`,
verbatim) and docs/DATA_MODEL.md §26 classifies Episode as a **rebuildable
projection**: "Episode summary/index" is derivable from the transcript, and
"不可把 rebuildable projection 当唯一事实来源" — it never owns conversation
truth (Conversation does; DOMAIN_MODEL §2 Authority Matrix).

docs/RUNTIME_ARCHITECTURE.md §19 runs this projection after the canonical
turn, and §11 lists ``EpisodeView`` among the views Persona Runtime consumes
(DOMAIN_MODEL §4 "Persona Runtime consumes … EpisodeView"). So this module
has two faces, and the split is deliberate:

- :class:`EpisodeRecord` — the durable row (all ten §5.3 columns, including
  the lifecycle metadata ``updated_at``);
- :class:`EpisodeView` — what the PromptCompiler may render. It carries the
  *content* columns only: ``updated_at`` is lifecycle metadata, not episode
  content, and rendering a clock stamp would both break prompt byte
  determinism and leak durable bookkeeping into the prompt (the P3-0
  ``CharacterPackageRecord`` precedent: status/updated_at stay OUT of the
  prompt).

**Local V1 semantics, stated honestly (nothing below is pinned by the
canonical text; each line is a站位 this slice takes and declares):**

- *one conversation, one episode* — ``source_turn_sequence_start`` is the
  first canonical slice's ``turn_sequence`` in the transcript the caller
  hands in and ``source_turn_sequence_end`` the last's. The canonical text
  gives **no segmentation algorithm** (it names neither a boundary rule nor
  a maximum episode length); the archive fold declared below is the
  segmentation **this** slice takes, cashing in the hook the episode-v1
  stance reserved: episode-v2 *is* the bump of
  :data:`EPISODE_PROJECTION_VERSION`, and a different segmentation shape
  would be a further bump or a second projection type, never a silent
  change of these bytes.
- ``summary`` is **extractive, verbatim, two-layer** (episode-v2). The
  *current layer* is the most recent :data:`EPISODE_SUMMARY_MAX_UTTERANCES`
  user utterances, each truncated to
  :data:`EPISODE_SUMMARY_UTTERANCE_MAX_CHARS`, joined with " / " — exactly
  the episode-v1 summary. The *archive layer* folds everything before the
  current-layer window: consecutive :data:`EPISODE_ARCHIVE_SEGMENT_TURNS`
  slices per segment, each segment contributing at most
  :data:`EPISODE_ARCHIVE_LINES_PER_SEGMENT` verbatim lines (the segment's
  first user utterance and its longest), older segments first. The layers
  join through :data:`_LAYER_SEPARATOR` (archive first); with an empty
  archive the summary is byte-for-byte the episode-v1 render. It is not a
  generative narrative: a model-written summary would be a different
  projection (a MODEL_PROPOSAL reading of the transcript), never this one.
- the transcript the caller hands in is the source: the full-history read
  (``get_full_persona_visible_history``, cs-3) applies the same
  persona-visible filters the window read always did, so command turns are
  already excluded (they are not utterances) — a command turn contributes
  no summary text, no archive line and no recent event.
- ``open_threads`` is the Persona×User pair's ACTIVE ``OPEN_THREAD`` memory
  content, ordered by memory id — Relationship-domain truth read through the
  same summary the Recorder consumes, never re-derived here (DOMAIN_MODEL
  §17: the pair is bound into the read that produced it).
- ``status`` is the conversation's own status word (``ACTIVE`` /
  ``CLOSED``, docs/DATA_MODEL.md §3).

Package constraints hold here as everywhere in ``elc.relationship``: no
import of ``elc.learning`` / ``elc.teaching`` / ``elc.persona``, and no
sqlite3 / SQL. This module is pure — no clock, no randomness, no store: the
same inputs always rebuild the same row, which is what makes
:func:`episode_version_for` meaningful.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from elc.conversation.commands import describe_slice
from elc.conversation.queries import ConversationWindow
from elc.conversation.types import (
    CanonicalTurnSlice,
    ConversationRecord,
    ConversationStatus,
)
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    EpisodeId,
    Err,
    Ok,
    Result,
    TurnId,
)
from elc.relationship.types import (
    RelationshipMemoryType,
    SamePersonaExistingRelationshipSummary,
)

__all__ = [
    "EPISODE_ABSENT_BASE_VERSION",
    "EPISODE_ARCHIVE_LINES_PER_SEGMENT",
    "EPISODE_ARCHIVE_SEGMENT_TURNS",
    "EPISODE_PROJECTION_VERSION",
    "EPISODE_RECENT_EVENT_LIMIT",
    "EPISODE_SUMMARY_MAX_UTTERANCES",
    "EPISODE_SUMMARY_UTTERANCE_MAX_CHARS",
    "EPISODE_WINDOW_MAX_TURNS",
    "EpisodeConversationSource",
    "EpisodeRecord",
    "EpisodeView",
    "episode_id_for",
    "episode_version_for",
    "rebuild_episode",
]

#: The template version of the episode projection (DATA_MODEL §1.4 "version
#: every derived model"): any change to what the summary, the open threads or
#: the recent events *mean* renders a different version string, so a bumped
#: template invalidates the rows the old one produced instead of silently
#: reusing them.
#:
#: episode-v2 (cs-3, the unlimited-chat slice): the summary became the
#: two-layer fold declared in the module docstring — the rebuild reads the
#: whole persona-visible transcript and folds everything before the current
#: layer into verbatim archive segments. v1 rows (window-only summaries)
#: are a different template's bytes, and the bump says so.
EPISODE_PROJECTION_VERSION = "episode-v2"

#: How many of the most recent slices the ``recent_events`` column carries.
#: Calibratable (this is a Local V1 position, not a canonical number).
EPISODE_RECENT_EVENT_LIMIT = 8

#: The extractive summary: at most this many of the most recent user
#: utterances, each truncated to
#: :data:`EPISODE_SUMMARY_UTTERANCE_MAX_CHARS`.
EPISODE_SUMMARY_MAX_UTTERANCES = 4
EPISODE_SUMMARY_UTTERANCE_MAX_CHARS = 120

#: The archive layer's fold (episode-v2, both Calibratable — Local V1
#: positions, not canonical numbers): a segment is this many consecutive
#: slices of the persona-visible transcript, and it contributes at most this
#: many verbatim lines to the summary (the segment's first user utterance
#: and its longest; one line when the two are the same utterance). Together
#: they bound the archive's prompt cost at roughly
#: ``2 * ceil(archive_slices / 20)`` truncated lines — linear in history,
#: small per segment, and a pure function of the transcript.
EPISODE_ARCHIVE_SEGMENT_TURNS = 20
EPISODE_ARCHIVE_LINES_PER_SEGMENT = 2

#: The fold's *current-layer depth* (episode-v2): how many of the newest
#: slices stay in the summary's current layer; everything before them is
#: archive. Since cs-3 this constant no longer bounds the rebuild's read —
#: the rebuild reads the whole persona-visible transcript
#: (``get_full_persona_visible_history``) — it only splits the fold. It
#: deliberately keeps the same number as elc.runtime.controller
#: ``CONVERSATION_WINDOW_MAX_TURNS`` (the ``[history]`` window the prompt
#: renders): P4-G1 forbids ``elc.relationship`` importing ``elc.runtime``,
#: so neither can reference the other, and the equality is held by a test
#: (tests/phase4/test_p4_3_gates.py) rather than by an import.
#:
#: Retirement note, kept honest: through episode-v1 this constant bounded
#: the rebuild's *read* (the episode was a projection of the window, and
#: ``source_turn_sequence_start`` was the window's first slice — a
#: full-history episode was called a different projection there). The v2
#: fold replaced that reading; the window depth is all this constant still
#: means.
EPISODE_WINDOW_MAX_TURNS = 20

#: The ``base_domain_version`` of a conversation that has no episode row yet.
#: Deliberately not a derived digest shape (real versions are ``epv-`` plus
#: 20 hex characters), so a projection job's stored base can never be
#: confused with a computed one.
EPISODE_ABSENT_BASE_VERSION = "epv-absent"

#: Digest encoding: canonical fields join with US (ASCII 0x1f, the repo's
#: unit-separator convention, elc.runtime.projections.SLICE_FIELD_SEPARATOR)
#: so no field boundary can be forged by content.
_FIELD_SEPARATOR = "\x1f"

#: Episode-id prefix — the ``ep-`` family beside the repo's ``rm-``
#: (relationship memory) / ``pj-`` (projection job) / ``sv-`` deterministic
#: ids; the version prefix is ``epv-``.
_ID_PREFIX = "ep-"
_VERSION_PREFIX = "epv-"

#: How many hex characters of the sha256 digest the derived ids keep (the
#: repo-wide convention).
_DIGEST_CHARS = 20

#: Truncation marker: a truncated utterance says so instead of pretending to
#: be the whole thing ("提取式逐字" — the words are verbatim, the cut is
#: visible).
_ELLIPSIS = "…"

#: The two-layer boundary in the summary string (episode-v2): archive lines
#: first, then this separator, then the current layer. Utterances join with
#: " / " inside a layer, so the wider separator is the one structural mark
#: that says "everything before me is the folded archive" — punctuation,
#: not content, and the only byte that is not verbatim transcript.
_LAYER_SEPARATOR = " || "


@dataclass(frozen=True)
class EpisodeView:
    """The Persona Runtime consumption view (docs/RUNTIME_ARCHITECTURE §11).

    Deliberately narrower than the record: ``episode_id`` identifies the
    projection, ``version`` says which template/content it was built from,
    and the three content columns are what a prompt may render.
    ``updated_at`` is **not** here (lifecycle metadata stays out of the
    prompt), and neither is the source-window bookkeeping
    (``conversation_id`` / ``source_turn_sequence_start`` / ``_end``), which
    is provenance rather than episode content.
    """

    episode_id: EpisodeId
    version: str
    summary: str
    open_threads: tuple[str, ...]
    recent_events: tuple[str, ...]
    status: ConversationStatus


@dataclass(frozen=True)
class EpisodeRecord:
    """One durable episode row — docs/DATA_MODEL.md §5.3, column for column.

    Ten columns, in the canonical order:

        episode_id / conversation_id / version /
        source_turn_sequence_start / source_turn_sequence_end /
        summary / open_threads[] / recent_events[] / status / updated_at

    ``open_threads[]`` and ``recent_events[]`` store as tuples (the
    implementation-defined storage form of a canonical list, DATA_MODEL §27;
    the durable column is JSON text, migration 0010). ``updated_at`` is the
    **store's** clock, not the rebuild's: :func:`rebuild_episode` never sets
    it (a rebuild is a pure function of the transcript), and the store fills
    it on write.
    """

    episode_id: EpisodeId
    conversation_id: ConversationId
    version: str
    source_turn_sequence_start: int
    source_turn_sequence_end: int
    summary: str
    open_threads: tuple[str, ...]
    recent_events: tuple[str, ...]
    status: ConversationStatus
    updated_at: str

    def as_view(self) -> EpisodeView:
        """The prompt-facing view of this row (content columns only)."""

        return EpisodeView(
            episode_id=self.episode_id,
            version=self.version,
            summary=self.summary,
            open_threads=self.open_threads,
            recent_events=self.recent_events,
            status=self.status,
        )


@runtime_checkable
class EpisodeConversationSource(Protocol):
    """The narrow conversation read face the episode projection needs.

    Satisfied structurally by ``SqliteConversationStore``. It is wider than
    ``elc.runtime.projections.ProjectionTurnSource`` by exactly one read —
    the full persona-visible history — because an episode (v2) folds the
    whole transcript, not just the single turn a job is keyed by. (Through
    episode-v1 the extra read was the bounded window; the v2 fold needs the
    same filters with no LIMIT, and the window read is the prompt's face,
    not this projection's.)
    """

    def get_canonical_turn_slice(
        self, turn_id: TurnId
    ) -> Result[CanonicalTurnSlice | None]:
        ...

    def get_conversation(
        self, conversation_id: ConversationId
    ) -> Result[ConversationRecord | None]:
        ...

    def get_full_persona_visible_history(
        self, conversation_id: ConversationId
    ) -> Result[ConversationWindow]:
        ...


def episode_id_for(conversation_id: ConversationId) -> EpisodeId:
    """The deterministic episode id of one conversation.

    Derived, never minted: ``ep-{sha256(conversation_id)[:20]}``. One
    conversation, one episode (the Local V1 stance above), so the id is a
    function of the conversation — a rebuild or a retry addresses the same
    durable row instead of minting a second one (DATA_MODEL §1.2 stable
    ids).

    Precondition (the repo-wide deterministic-id convention): the caller
    guarantees the encoded part carries no US (0x1f); conversation ids are
    store-minted today, and the encoding is a convention rather than a
    defence (it does not claim to be one).
    """

    digest = hashlib.sha256(str(conversation_id).encode("utf-8")).hexdigest()
    return EpisodeId(f"{_ID_PREFIX}{digest[:_DIGEST_CHARS]}")


def episode_version_for(
    *,
    conversation_id: ConversationId,
    source_turn_sequence_start: int,
    source_turn_sequence_end: int,
    summary: str,
    open_threads: tuple[str, ...],
    recent_events: tuple[str, ...],
    status: ConversationStatus,
    projection_version: str = EPISODE_PROJECTION_VERSION,
) -> str:
    """The content digest of one episode: ``epv-{sha256(...)[:20]}``.

    Derived over exactly the **content** fields plus the source-window
    bounds and :data:`EPISODE_PROJECTION_VERSION` — and over **no clock**:
    ``updated_at`` is the store's stamp, so a rebuild of unchanged truth must
    reproduce this string byte for byte and the store can tell "the same
    episode, re-projected" (a zero-write replay) from "the episode moved"
    (a content replace).

    Lists join as their own ordered elements, so a re-ordered
    ``open_threads`` / ``recent_events`` digests differently — order is
    content here, not presentation.
    """

    parts = (
        projection_version,
        str(conversation_id),
        str(int(source_turn_sequence_start)),
        str(int(source_turn_sequence_end)),
        summary,
        *open_threads,
        *recent_events,
        status.value,
    )
    digest = hashlib.sha256(_FIELD_SEPARATOR.join(parts).encode("utf-8")).hexdigest()
    return f"{_VERSION_PREFIX}{digest[:_DIGEST_CHARS]}"


def rebuild_episode(
    *,
    conversation_id: ConversationId,
    slices: Sequence[CanonicalTurnSlice],
    relationship_summary: SamePersonaExistingRelationshipSummary,
    conversation_status: ConversationStatus,
) -> Result[EpisodeRecord]:
    """Rebuild the episode of one conversation from the persona-visible
    transcript.

    Pure: the same inputs always produce the same row, and the row's
    ``updated_at`` is left empty — the durable clock belongs to the store
    (elc.relationship.episode_store). Since episode-v2 the caller hands the
    **whole** persona-visible transcript (cs-3's
    ``get_full_persona_visible_history``), not a bounded window: the summary
    folds all of it (current layer + archive), and
    ``source_turn_sequence_start``/``_end`` are the first and last slice of
    everything handed in.

    An empty transcript is refused with ``VALIDATION_FAILED``: there is no
    episode without a canonical slice, and the assembly (the CP4 executor)
    declares that refusal rather than persisting an empty episode (the
    caller-visible rule of this slice).

    The slices are sorted by ``turn_sequence`` here, so a caller may hand
    them in any order — the full-history read returns them oldest-first, but
    the rebuild does not depend on that (a projection must not inherit its
    source's incidental ordering).
    """

    ordered = tuple(sorted(slices, key=lambda slice_: int(slice_.turn_sequence)))
    if not ordered:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"empty window: no canonical slice in the transcript of"
                    f" conversation {conversation_id}: an episode is a"
                    " projection of the transcript, so an empty window has"
                    " nothing to project (docs/DATA_MODEL.md §5.3)"
                ),
            )
        )

    start = int(ordered[0].turn_sequence)
    end = int(ordered[-1].turn_sequence)
    recent = ordered[-EPISODE_RECENT_EVENT_LIMIT:]
    recent_events = tuple(describe_slice(slice_) for slice_ in recent)
    summary = _two_layer_summary(ordered)
    open_threads = _open_threads(relationship_summary)
    status = conversation_status
    return Ok(
        EpisodeRecord(
            episode_id=episode_id_for(conversation_id),
            conversation_id=conversation_id,
            version=episode_version_for(
                conversation_id=conversation_id,
                source_turn_sequence_start=start,
                source_turn_sequence_end=end,
                summary=summary,
                open_threads=open_threads,
                recent_events=recent_events,
                status=status,
            ),
            source_turn_sequence_start=start,
            source_turn_sequence_end=end,
            summary=summary,
            open_threads=open_threads,
            recent_events=recent_events,
            status=status,
            updated_at="",
        )
    )


def _two_layer_summary(slices: Sequence[CanonicalTurnSlice]) -> str:
    """The episode-v2 summary: the archive fold, then the current layer.

    The current layer is the tail the window still covers (the newest
    :data:`EPISODE_SUMMARY_MAX_UTTERANCES` utterances, exactly the episode-v1
    render); everything before it is folded segment by segment, older
    segments first, and the two layers join through
    :data:`_LAYER_SEPARATOR`. With an empty archive there is no separator
    and the summary is byte-for-byte the episode-v1 render — a short
    conversation reads exactly as it always did.
    """

    current = _extractive_summary(slices)
    archive = slices[: -EPISODE_WINDOW_MAX_TURNS]
    if not archive:
        return current
    lines: list[str] = []
    for start in range(0, len(archive), EPISODE_ARCHIVE_SEGMENT_TURNS):
        segment = archive[start : start + EPISODE_ARCHIVE_SEGMENT_TURNS]
        lines.extend(_segment_lines(segment))
    return _LAYER_SEPARATOR.join((" / ".join(lines), current))


def _segment_lines(
    segment: Sequence[CanonicalTurnSlice],
) -> tuple[str, ...]:
    """The at-most-:data:`EPISODE_ARCHIVE_LINES_PER_SEGMENT` verbatim lines
    one archive segment contributes.

    The deterministic selection (a fold rule, not a judgement): the
    segment's **first** user utterance and its **longest** one (length ties
    break to the earliest slice). When the longest *is* the first
    utterance — short segments, or a segment whose opener is also its
    longest line — it is contributed once, so a segment never repeats
    itself. Truncation is the same marked cut the current layer uses.
    """

    longest = max(
        segment, key=lambda slice_: len(slice_.user_turn.raw_content)
    ).user_turn.raw_content
    lines = [_truncate(segment[0].user_turn.raw_content)]
    if longest != segment[0].user_turn.raw_content:
        lines.append(_truncate(longest))
    return tuple(lines[:EPISODE_ARCHIVE_LINES_PER_SEGMENT])


def _extractive_summary(slices: Sequence[CanonicalTurnSlice]) -> str:
    """The most recent utterances, verbatim, joined with " / ".

    Chronological order (oldest of the kept ones first) so the summary reads
    like the conversation ran; truncation is marked with an ellipsis so a
    cut utterance never pretends to be complete.
    """

    kept = slices[-EPISODE_SUMMARY_MAX_UTTERANCES:]
    return " / ".join(
        _truncate(slice_.user_turn.raw_content) for slice_ in kept
    )


def _truncate(text: str) -> str:
    if len(text) <= EPISODE_SUMMARY_UTTERANCE_MAX_CHARS:
        return text
    clipped = text[:EPISODE_SUMMARY_UTTERANCE_MAX_CHARS].rstrip()
    return f"{clipped}{_ELLIPSIS}"


def _open_threads(
    summary: SamePersonaExistingRelationshipSummary,
) -> tuple[str, ...]:
    """The pair's ACTIVE OPEN_THREAD contents, ordered by memory id.

    Read through the same scope-bound summary the Recorder consumes: another
    persona's threads are not in it, so they cannot appear here (DOMAIN_MODEL
    §17; BF-05 §29).
    """

    threads = (
        entry
        for entry in summary.active
        if entry.memory_type is RelationshipMemoryType.OPEN_THREAD
    )
    return tuple(
        entry.canonical_content
        for entry in sorted(
            threads, key=lambda entry: str(entry.relationship_memory_id)
        )
    )
