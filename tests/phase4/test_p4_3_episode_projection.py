"""P4-3 ① — the Episode projection (TASK-OPI-4d516e4f-….19 ①).

docs/DATA_MODEL.md §5.3 owns the ten columns; elc.relationship.episode owns
what they mean; elc.relationship.episode_store owns the bytes. What is
pinned here, in that order:

- the derived ids (``ep-`` from the conversation, ``epv-`` from the content)
  and the fact that the version carries no clock;
- the row really is the §5.3 column set, column for column, and the *view*
  really drops ``updated_at`` (lifecycle metadata never reaches a prompt);
- the rebuild is a pure function of the window: extractive summary, the
  newest K rendered slices, the pair's ACTIVE OPEN_THREAD contents;
- the store's idempotence contract: same version = zero writes, a moved
  version = a content replace, same version with different content = a
  conflict, a foreign conversation = a conflict, a stale epoch = a raise;
- the CP4 half: one EPISODE job per turn, landing COMMITTED through the real
  runtime and the real store, with the deterministic id and the current
  slice's hash.

The two Local V1 stances the module declares (one conversation = one
episode; the summary is extractive, not generative) are asserted rather than
described: the tests below would fail if either changed silently.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from elc.conversation.types import ConversationStatus
from elc.platform.types import (
    ConversationId,
    Ok,
    ProjectionJobId,
    RelationshipMemoryId,
)
from elc.relationship.controller import RelationshipController
from elc.relationship.episode import (
    EPISODE_ABSENT_BASE_VERSION,
    EPISODE_PROJECTION_VERSION,
    EPISODE_RECENT_EVENT_LIMIT,
    EPISODE_SUMMARY_MAX_UTTERANCES,
    EPISODE_SUMMARY_UTTERANCE_MAX_CHARS,
    EpisodeRecord,
    EpisodeView,
    episode_id_for,
    episode_version_for,
    rebuild_episode,
)
from elc.relationship.episode_store import (
    SqliteEpisodeStore,
    StaleStoreEpochError,
)
from elc.relationship.projection import EpisodeProjectionExecutor
from elc.relationship.types import (
    MemoryProvenance,
    MemoryStatus,
    RelationshipMemorySummaryEntry,
    RelationshipMemoryType,
    SamePersonaExistingRelationshipSummary,
)
from elc.runtime.projections import PROJECTION_TYPE_EPISODE, projection_id_for

from .conftest import (
    CONV,
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    commit_chat_turn,
    deliver_reply,
    episode_row,
    episode_rows,
    open_conversation_for,
    projection_job_row,
    speak,
    turn_slice,
)

#: The ten §5.3 columns, in canonical order — the durable row is exactly
#: this, and nothing else.
EPISODE_COLUMNS = (
    "episode_id",
    "conversation_id",
    "version",
    "source_turn_sequence_start",
    "source_turn_sequence_end",
    "summary",
    "open_threads",
    "recent_events",
    "status",
    "updated_at",
)


def _thread(
    memory_id: str,
    content: str,
    memory_type: RelationshipMemoryType = RelationshipMemoryType.OPEN_THREAD,
    status: MemoryStatus = MemoryStatus.ACTIVE,
) -> RelationshipMemorySummaryEntry:
    return RelationshipMemorySummaryEntry(
        relationship_memory_id=RelationshipMemoryId(memory_id),
        memory_type=memory_type,
        provenance=MemoryProvenance.USER_STATED_FACT,
        canonical_content=content,
        status=status,
    )


def _summary(*entries: RelationshipMemorySummaryEntry, persona_id=PERSONA_A):
    return SamePersonaExistingRelationshipSummary(
        persona_id=persona_id, user_id=REL_USER, memories=entries
    )


def _turn_record(store, turn_id):
    """The durable TurnRecord of one turn (the executor's ``base_version``
    input)."""

    record = store.get_turn_record(turn_id)
    assert isinstance(record, Ok) and record.value is not None
    return record.value


def _job_view(turn_id):
    """A claimed-looking EPISODE job view for one turn — the executor's
    ``project`` input (only ``source_turn_id`` is read by the executor)."""

    from elc.runtime.projections import ProjectionJobView
    from elc.runtime.types import ProjectionJobState

    return ProjectionJobView(
        projection_job_id=ProjectionJobId("pj-episode-probe"),
        projection_type=PROJECTION_TYPE_EPISODE,
        source_turn_id=turn_id,
        source_turn_slice_hash="probe-hash",
        base_domain_version=None,
        status=ProjectionJobState.RUNNING,
        attempt_count=1,
        created_at="probe",
        updated_at="probe",
    )


def _conversation_with(store, conversation_id: str, count: int):
    """One conversation with ``count`` canonical chat turns; returns the
    conversation id and its slices in turn order."""

    conversation = open_conversation_for(store, conversation_id, PERSONA_A)
    slices = []
    for index in range(1, count + 1):
        turn_id = speak(
            store,
            conversation,
            f"cm-{conversation_id}-{index}",
            f"utterance {index}",
        )
        deliver_reply(
            store,
            turn_id,
            conversation,
            f"reply {index}",
            assistant_turn_id=f"at-{conversation_id}-{index}",
        )
        slices.append(turn_slice(store, turn_id))
    return conversation, tuple(slices)


# -- ① derived ids and the content digest -----------------------------------


def test_the_episode_id_is_derived_from_the_conversation() -> None:
    first = episode_id_for(ConversationId("conv-1"))
    assert first == episode_id_for(ConversationId("conv-1"))
    assert first.startswith("ep-")
    assert len(first) == len("ep-") + 20
    assert first != episode_id_for(ConversationId("conv-2"))


def test_the_episode_version_carries_the_content_and_no_clock() -> None:
    """The version is derived from content + window + template version, and
    the record's own lifecycle stamp is deliberately not part of it."""

    def version(**overrides) -> str:
        fields = {
            "conversation_id": ConversationId("conv-1"),
            "source_turn_sequence_start": 1,
            "source_turn_sequence_end": 3,
            "summary": "I live in Berlin.",
            "open_threads": ("ask about the trip",),
            "recent_events": ("#1 [turn-1] user: hi | assistant: hey | outcome:"
                              " REPLIED_FULL",),
            "status": ConversationStatus.ACTIVE,
        }
        fields.update(overrides)
        return episode_version_for(**fields)

    baseline = version()
    assert baseline == version()  # deterministic
    assert baseline.startswith("epv-")
    assert baseline != version(summary="I live in Paris.")
    assert baseline != version(open_threads=())
    assert baseline != version(recent_events=())
    assert baseline != version(source_turn_sequence_end=4)
    assert baseline != version(status=ConversationStatus.CLOSED)
    # The template version is part of the digest: bumping the projection
    # template invalidates the rows the old one produced.
    assert baseline != version(projection_version="episode-v2")


def test_the_projection_template_version_is_pinned() -> None:
    assert EPISODE_PROJECTION_VERSION == "episode-v1"
    assert EPISODE_RECENT_EVENT_LIMIT == 8
    assert EPISODE_SUMMARY_MAX_UTTERANCES == 4


# -- ① the row is the §5.3 column set ---------------------------------------


def test_the_record_is_the_canonical_column_set_in_order(db) -> None:
    columns = [
        str(row[1]) for row in db.execute("PRAGMA table_info(episode)").fetchall()
    ]
    assert tuple(columns) == EPISODE_COLUMNS

    import dataclasses

    assert tuple(field.name for field in dataclasses.fields(EpisodeRecord)) == (
        EPISODE_COLUMNS
    )


def test_the_view_drops_the_lifecycle_metadata() -> None:
    """EpisodeView is the prompt face: no ``updated_at``, and none of the
    source-window bookkeeping either (provenance, not episode content)."""

    import dataclasses

    view_fields = {field.name for field in dataclasses.fields(EpisodeView)}
    assert view_fields == {
        "episode_id",
        "version",
        "summary",
        "open_threads",
        "recent_events",
        "status",
    }
    assert "updated_at" not in view_fields
    assert "conversation_id" not in view_fields
    assert "source_turn_sequence_start" not in view_fields


# -- ① the rebuild ----------------------------------------------------------


def test_the_rebuild_is_a_pure_function_of_the_window(store) -> None:
    conversation, slices = _conversation_with(store, "conv-pure", 2)
    first = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    second = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value == second.value
    # The rebuild never stamps a clock: ``updated_at`` is the store's.
    assert first.value.updated_at == ""
    assert first.value.version == second.value.version


def test_the_rebuild_sorts_the_slices_it_was_handed(store) -> None:
    """A projection must not inherit its source's incidental ordering: the
    window read hands slices oldest-first, but the rebuild does not care."""

    conversation, slices = _conversation_with(store, "conv-order", 3)
    ordered = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    shuffled = rebuild_episode(
        conversation_id=conversation,
        slices=tuple(reversed(slices)),
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(ordered, Ok) and isinstance(shuffled, Ok)
    assert ordered.value == shuffled.value
    assert ordered.value.source_turn_sequence_start == 1
    assert ordered.value.source_turn_sequence_end == 3


def test_an_empty_window_is_refused_without_a_row(store) -> None:
    conversation = open_conversation_for(store, "conv-empty", PERSONA_A)
    refused = rebuild_episode(
        conversation_id=conversation,
        slices=(),
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert not isinstance(refused, Ok)
    assert "empty window" in refused.error.message


def test_the_summary_is_extractive_verbatim_and_bounded(store) -> None:
    conversation, slices = _conversation_with(store, "conv-summary", 6)
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok)
    utterances = rebuilt.value.summary.split(" / ")
    assert len(utterances) == EPISODE_SUMMARY_MAX_UTTERANCES
    # The newest four, in the order they were said.
    assert utterances == [f"utterance {index}" for index in (3, 4, 5, 6)]


def test_a_long_utterance_is_truncated_and_marked(store) -> None:
    conversation = open_conversation_for(store, "conv-long", PERSONA_A)
    long_text = "x" * (EPISODE_SUMMARY_UTTERANCE_MAX_CHARS + 30)
    turn_id = speak(store, conversation, "cm-long", long_text)
    deliver_reply(store, turn_id, conversation, "ok", assistant_turn_id="at-long")
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=(turn_slice(store, turn_id),),
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok)
    assert rebuilt.value.summary.endswith("…")
    assert len(rebuilt.value.summary) == EPISODE_SUMMARY_UTTERANCE_MAX_CHARS + 1
    assert rebuilt.value.summary.startswith("x" * 20)  # verbatim, not rewritten


def test_the_recent_events_are_the_newest_rendered_slices(store) -> None:
    conversation, slices = _conversation_with(store, "conv-events", 3)
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok)
    events = rebuilt.value.recent_events
    assert len(events) == 3
    # describe_slice renders each event, and the newest ones come last (the
    # keep window is the tail, the rendering keeps chronological order).
    assert events[0].startswith("#1 [")
    assert "user: utterance 1" in events[0]
    assert "assistant: reply 1" in events[0]
    # The outcome leg is rendered too (these turns were canonicalized without
    # being terminalized, so the renderer's own "no outcome" marker is what
    # shows — the point is that the leg is present and comes from the slice).
    assert "| outcome:" in events[0]
    assert events[-1].startswith("#3 [")


def test_the_open_threads_are_the_pairs_active_threads_by_id(store) -> None:
    conversation, slices = _conversation_with(store, "conv-threads", 1)
    summary = _summary(
        _thread("rm-2", "second thread"),
        _thread("rm-1", "first thread"),
        _thread("rm-3", "old thread", status=MemoryStatus.SUPERSEDED),
        _thread("rm-4", "a fact", RelationshipMemoryType.USER_STATED_FACT),
    )
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=summary,
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok)
    # Ordered by memory id, ACTIVE OPEN_THREAD only.
    assert rebuilt.value.open_threads == ("first thread", "second thread")


def test_another_personas_threads_are_not_in_the_episode(store) -> None:
    """The summary is scope-bound; a summary assembled for another pair
    simply carries none of this pair's threads — and the rebuild reads what
    it was handed (DOMAIN_MODEL §17)."""

    conversation, slices = _conversation_with(store, "conv-foreign", 1)
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(persona_id=PERSONA_B),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok)
    assert rebuilt.value.open_threads == ()


def test_the_status_is_the_conversations_own_word(store) -> None:
    conversation, slices = _conversation_with(store, "conv-status", 1)
    closed = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.CLOSED,
    )
    assert isinstance(closed, Ok)
    assert closed.value.status is ConversationStatus.CLOSED


# -- ① the store ------------------------------------------------------------


def _record(store, conversation_id: str, count: int = 1) -> EpisodeRecord:
    conversation, slices = _conversation_with(store, conversation_id, count)
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok)
    return rebuilt.value


def test_upsert_writes_the_row_and_reads_it_back(
    db: sqlite3.Connection, store, episode_store: SqliteEpisodeStore
) -> None:
    record = _record(store, "conv-store")
    written = episode_store.upsert_episode(record)
    assert isinstance(written, Ok) and written.value == record.episode_id

    row = episode_row(db, record.conversation_id)
    assert row[0] == str(record.episode_id)
    assert row[2] == record.version
    assert row[9] != ""  # the store stamped a clock
    assert json.loads(str(row[6])) == list(record.open_threads)
    assert json.loads(str(row[7])) == list(record.recent_events)

    read = episode_store.get_episode(record.conversation_id)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.version == record.version
    assert read.value.updated_at == row[9]
    view = episode_store.episode_view(record.conversation_id)
    assert isinstance(view, Ok) and view.value is not None
    assert view.value.summary == record.summary
    assert not hasattr(view.value, "updated_at")


def test_upsert_replays_the_same_version_with_zero_writes(
    db: sqlite3.Connection, store, episode_store: SqliteEpisodeStore
) -> None:
    record = _record(store, "conv-idem")
    assert isinstance(episode_store.upsert_episode(record), Ok)
    before = episode_row(db, record.conversation_id)
    before_rows = episode_rows(db)

    again = episode_store.upsert_episode(record)
    assert isinstance(again, Ok) and again.value == record.episode_id
    # Byte-for-byte identical: not even updated_at moved.
    assert episode_row(db, record.conversation_id) == before
    assert episode_rows(db) == before_rows


def test_upsert_replaces_the_content_when_the_version_moves(
    db: sqlite3.Connection, store, episode_store: SqliteEpisodeStore
) -> None:
    conversation, slices = _conversation_with(store, "conv-moved", 1)
    first = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(first, Ok) and isinstance(
        episode_store.upsert_episode(first.value), Ok
    )
    row_before = episode_row(db, conversation)

    second = rebuild_episode(
        conversation_id=conversation,
        slices=slices,
        relationship_summary=_summary(_thread("rm-9", "a new thread")),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(second, Ok)
    assert second.value.version != first.value.version
    assert isinstance(episode_store.upsert_episode(second.value), Ok)

    row_after = episode_row(db, conversation)
    assert row_after[0] == row_before[0]  # the same episode id
    assert row_after[2] != row_before[2]  # a new version
    assert json.loads(str(row_after[6])) == ["a new thread"]
    assert len(episode_rows(db)) == 1


def test_the_same_version_with_different_content_is_a_conflict(
    db: sqlite3.Connection, store, episode_store: SqliteEpisodeStore
) -> None:
    """The version IS the content digest, so that combination means the
    derivation changed without bumping — a conflict, never a rewrite."""

    import dataclasses

    record = _record(store, "conv-conflict")
    assert isinstance(episode_store.upsert_episode(record), Ok)
    before = episode_row(db, record.conversation_id)

    tampered = dataclasses.replace(record, summary="something else entirely")
    refused = episode_store.upsert_episode(tampered)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert episode_row(db, record.conversation_id) == before


def test_a_foreign_conversation_on_the_same_id_is_a_conflict(
    db: sqlite3.Connection, store, episode_store: SqliteEpisodeStore
) -> None:
    import dataclasses

    record = _record(store, "conv-owner")
    assert isinstance(episode_store.upsert_episode(record), Ok)
    foreign = dataclasses.replace(
        record, conversation_id=ConversationId("conv-other")
    )
    refused = episode_store.upsert_episode(foreign)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert episode_rows(db) == [episode_row(db, record.conversation_id)]


def test_a_stale_epoch_store_cannot_write(
    db: sqlite3.Connection, store, fence
) -> None:
    from elc.platform.db import epoch

    stale = SqliteEpisodeStore(db, fence)
    epoch.open_runtime_epoch(db)  # a new process opened a newer epoch
    from elc.platform.types import EpisodeId

    with pytest.raises(StaleStoreEpochError):
        stale.upsert_episode(
            EpisodeRecord(
                episode_id=EpisodeId("ep-stale"),
                conversation_id=CONV,
                version="epv-stale",
                source_turn_sequence_start=1,
                source_turn_sequence_end=1,
                summary="",
                open_threads=(),
                recent_events=(),
                status=ConversationStatus.ACTIVE,
                updated_at="",
            )
        )


# -- ① the CP4 half ---------------------------------------------------------


def test_an_episode_job_lands_committed_through_cp4(
    db: sqlite3.Connection,
    store,
    projecting_coordinator,
    episode_store: SqliteEpisodeStore,
) -> None:
    conversation = open_conversation_for(store, "conv-ep-job", PERSONA_A)
    turn = commit_chat_turn(
        projecting_coordinator,
        "cm-ep-job",
        "I live in Berlin.",
        1,
        conversation=conversation,
    )
    job_id = projection_id_for(PROJECTION_TYPE_EPISODE, turn.turn_id)
    row = projection_job_row(db, job_id)
    assert row[5] == "COMMITTED"
    assert row[6] == 1

    read = episode_store.get_episode(conversation)
    assert isinstance(read, Ok) and read.value is not None
    episode = read.value
    assert episode.episode_id == episode_id_for(conversation)
    assert episode.summary == "I live in Berlin."
    assert episode.source_turn_sequence_start == 1
    assert episode.recent_events and "user: I live in Berlin." in (
        episode.recent_events[0]
    )
    assert episode.status is ConversationStatus.ACTIVE


def test_the_episode_base_version_is_the_current_row_or_the_sentinel(
    db: sqlite3.Connection,
    store,
    episode_projection,
    projecting_coordinator,
    coordinator,
) -> None:
    """The base a run records is the *current* episode version; a
    conversation that has none reports the sentinel rather than pretending to
    a digest it never computed."""

    conversation = open_conversation_for(store, "conv-ep-base", PERSONA_A)
    projected = commit_chat_turn(
        projecting_coordinator,
        "cm-ep-base",
        "I live in Berlin.",
        1,
        conversation=conversation,
    )
    record = _turn_record(store, projected.turn_id)
    landed = episode_projection.base_version(record)
    assert isinstance(landed, Ok)
    assert landed.value == episode_row(db, conversation)[2]

    # A turn of a conversation the projection never touched (the plain
    # coordinator has no CP4 port).
    bare = open_conversation_for(store, "conv-ep-none", PERSONA_A)
    bare_turn = commit_chat_turn(
        coordinator, "cm-ep-none", "Hello there.", 1, conversation=bare
    )
    fresh = episode_projection.base_version(_turn_record(store, bare_turn.turn_id))
    assert isinstance(fresh, Ok)
    assert fresh.value == EPISODE_ABSENT_BASE_VERSION
    assert episode_rows(db) == [episode_row(db, conversation)]


def test_an_episode_job_without_a_persona_is_refused(
    db: sqlite3.Connection, store, episode_projection
) -> None:
    """A conversation with no persona has no pair to read OPEN_THREADs from,
    so the projection refuses deterministically instead of writing a row
    whose open_threads column could not be filled honestly."""

    conversation = open_conversation_for(store, "conv-ep-nopersona", None)
    turn_id = speak(store, conversation, "cm-ep-nopersona", "I live in Berlin.")
    deliver_reply(store, turn_id, conversation, "ok", assistant_turn_id="at-np")

    refused = episode_projection.project(_job_view(turn_id))
    assert not isinstance(refused, Ok)
    assert "has no persona" in refused.error.message
    assert episode_rows(db) == []
    # The refusal is at the write face, not at the base: the base is the
    # sentinel (there is simply no row), which is a legal starting point.
    base = episode_projection.base_version(_turn_record(store, turn_id))
    assert isinstance(base, Ok) and base.value == EPISODE_ABSENT_BASE_VERSION


def test_a_foreign_summary_is_refused_with_zero_writes(
    db: sqlite3.Connection, store, relationship_store, episode_store
) -> None:
    """The same assembly-consistency check the relationship executor runs:
    a summary describing another pair never becomes this conversation's open
    threads (DEC-…115 待裁 B 附条件)."""

    class _ForeignScopeController(RelationshipController):
        def get_existing_summary(self, persona_id, user_id):
            del persona_id
            return Ok(
                SamePersonaExistingRelationshipSummary(
                    persona_id=PERSONA_B, user_id=user_id, memories=()
                )
            )

    conversation = open_conversation_for(store, "conv-ep-scope", PERSONA_A)
    turn_id = speak(store, conversation, "cm-ep-scope", "I live in Berlin.")
    deliver_reply(store, turn_id, conversation, "ok", assistant_turn_id="at-scope")

    executor = EpisodeProjectionExecutor(
        store=episode_store,
        controller=_ForeignScopeController(relationship_store),
        conversation=store,
        user_id=REL_USER,
    )
    refused = executor.project(_job_view(turn_id))
    assert not isinstance(refused, Ok)
    assert "scope mismatch" in refused.error.message
    assert episode_rows(db) == []
