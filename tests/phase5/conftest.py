"""Shared fixtures for the Phase 5 content.db tests (P5-0 read face, P5-1
readiness + production supply).

The fixture corpus under test is the repository's real authoring source
(`content_src/` + `curriculum/`) built by `elc.content.build`; tests never
hand-write a content.db, because the artifact's whole point is that it is
generated. `built_content_db` builds once per session into a pytest temp
directory (the artifact is gitignored and never committed).

P5-1 adds the app.db side of the same world (migrations through v10, an opened
runtime epoch, the conversation/learning/teaching stores) so the end-to-end
suites can drive the *real* assembly on top of the *real* artifact. Two
deliberate choices:

- the app.db fixtures are re-declared here (the tests/phase4/conftest.py
  pattern) and the coordinator is built here too, rather than importing the
  Phase 3 assembly helpers: `tests/phase3/conftest.py` imports the fixture
  target provider at module scope, and the p5-1 supply chain is not allowed to
  touch the P3 fixture at all (TASK-OPI-4d516e4f-….46 red line: "本刀 E2E
  不得用 `_seed()` 或 fixture 目标供给构造 before");
- `make_lease` is four lines and is re-declared for the same reason — a
  one-line import would drag the fixture provider back into the graph.

P5-2 adds the natural-conversation side of the same world: the
`ContentBackedTargetSupply` / `ContentBackedSilentTargets` pair (the supply
read face and the chat-leg resolver source) and the optional
`silent_evidence` keyword of `production_coordinator`. Both default to "not
wired", so every P5-1 assembly and its pinned behavior are exactly what they
were before.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from elc.content.build import CONTENT_SRC_DIR, CURRICULUM_DIR, build_content_db
from elc.content.store import ContentStore
from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.learning.controller import LearningController
from elc.learning.silent_evidence import (
    ContentBackedSilentTargets,
    ContentBackedTargetSupply,
    SilentEvidenceSource,
)
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
    sample_character_package,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.types import InputEnvelope
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.targets import TeachingTargetProvider
from tests.conftest import REPO_ROOT, AssemblyGenerationStore

DOCS_ROOT = REPO_ROOT / "docs"

#: The P5-1 app.db world: one conversation, one user, one fixed clock.
CONV = ConvId("conv-p5-1")
RUNTIME_VERSION = "runtime-v1"
REQUESTED_AT = "2026-09-21T10:00:00+00:00"
USER = UserId("user-p5-1")

__all__ = [
    "CANDIDATE_UNIQUE_FORM",
    "CONTENT_SRC_DIR",
    "CONV",
    "CURRICULUM_DIR",
    "DOCS_ROOT",
    "REQUESTED_AT",
    "RUNTIME_VERSION",
    "USER",
    "artifact_with_lifecycle",
    "attempt",
    "build_variant_artifact",
    "candidate_entity_edit",
    "canonical_blocks",
    "canonical_lines",
    "clone_entity",
    "commit_chat_turn",
    "make_lease",
    "open_moment",
    "production_coordinator",
    "reply",
    "reply_ok",
]


@pytest.fixture(scope="session")
def built_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The repository's content.db, built once for the whole session."""

    output = tmp_path_factory.mktemp("p5-0-content") / "content.db"
    build_content_db(output)
    return output


def build_variant_artifact(tmp_path: Path, edit=None, *, curriculum_edit=None) -> Path:
    """Build a content.db from a *copy* of both authoring trees after edits.

    ``edit(documents, index)`` receives every indexed entity document (keyed by
    its index-relative path) plus the index mapping; ``curriculum_edit``
    receives the curriculum tree's documents (keyed by tree-relative name,
    ``index.json`` included) the same way. Either may be omitted; the copy is
    then built through the real build step, so a variant artifact is a genuine
    artifact (P5-0's bad-source-matrix style).

    The canonical authoring trees are never edited to make a test convenient:
    a variant exists only to exercise a state the canonical corpus does not
    carry (a §24.11 candidate, a retired entity, a changed §11 default, an
    unapproved §24.7 mapping).
    """

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    index_path = content_src / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    documents = {
        str(entry): json.loads((content_src / str(entry)).read_text(encoding="utf-8"))
        for entry in index["entities"]
    }
    if edit is not None:
        edit(documents, index)
    for entry, document in documents.items():
        (content_src / entry).write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )
    index_path.write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    if curriculum_edit is not None:
        curriculum_documents = {
            path.relative_to(curriculum).as_posix(): json.loads(
                path.read_text(encoding="utf-8")
            )
            for path in sorted(curriculum.rglob("*.json"))
        }
        curriculum_edit(curriculum_documents, {"root": str(curriculum)})
        for name, document in curriculum_documents.items():
            (curriculum / name).write_text(
                json.dumps(document, indent=2) + "\n", encoding="utf-8"
            )
    output = tmp_path / "content.db"
    build_content_db(
        output, content_src_dir=content_src, curriculum_dir=curriculum
    )
    return output


def clone_entity(documents: dict, source_id: str, new_id: str) -> dict:
    """A deep copy of one entity document under a new id (for `edit`)."""

    document = json.loads(
        json.dumps(documents[f"entities/{source_id}.json"])
    )
    document["entity"]["entity_id"] = new_id
    documents[f"entities/{new_id}.json"] = document
    return document


def artifact_with_lifecycle(tmp_path: Path, statuses: dict[str, str]) -> Path:
    """An artifact whose corpus carries extra entities with these §24.11
    lifecycle statuses (characters of the canonical entity, new ids)."""

    def edit(documents: dict, index: dict) -> None:
        for entity_id, lifecycle in statuses.items():
            document = clone_entity(documents, "res-hedge-i-think", entity_id)
            document["entity"]["lifecycle_status"] = lifecycle
            index["entities"].append(f"entities/{entity_id}.json")

    return build_variant_artifact(tmp_path, edit)


#: The canonical form of the P5-2 candidate probe entity: unique in the
#: corpus (nothing else's form, alternative or slot group matches it), so a
#: resolution on it can only be the candidate's.
CANDIDATE_UNIQUE_FORM = "I think it is going to snow."


def candidate_entity_edit(lifecycle: str):
    """One corpus edit for the P5-2 supply probes: a clone of the hedge
    entity under a candidate lifecycle whose canonical form is unique.

    The canonical corpus is left untouched (the clone's form matches no
    other entity), so "did it resolve?" answers exactly "was the candidate
    in supply?".
    """

    def edit(documents: dict, index: dict) -> None:
        clone = clone_entity(
            documents, "res-hedge-i-think", "res-candidate-not-approved"
        )
        clone["entity"]["lifecycle_status"] = lifecycle
        clone["teaching_content"]["canonical_forms"] = [CANDIDATE_UNIQUE_FORM]
        clone["teaching_content"]["reveal_form"] = CANDIDATE_UNIQUE_FORM
        clone["teaching_content"]["alternative_realizations"] = []
        clone["teaching_content"]["required_slots"] = [["snow"]]
        index["entities"].append("entities/res-candidate-not-approved.json")

    return edit


@pytest.fixture()
def store(built_content_db: Path) -> Iterator[ContentStore]:
    opened = ContentStore(built_content_db)
    yield opened
    opened.close()


# ---------------------------------------------------------------------------
# P5-1: the real artifact as a *supply*, and the app.db world around it
# ---------------------------------------------------------------------------


@pytest.fixture()
def content_supply(built_content_db: Path) -> Iterator[CurriculumContentStore]:
    """The curriculum-side read face over the session's built content.db."""

    opened = ContentStore(built_content_db)
    supply = CurriculumContentStore(opened)
    yield supply
    supply.close()


@pytest.fixture()
def production_provider(built_content_db: Path) -> Iterator[TeachingTargetProvider]:
    """The production target provider over the session's built content.db.

    Path-constructed on purpose: this is how an assembly wires it (the
    provider owns the connection and opens it lazily), and it keeps the
    fixture honest — nothing here can reach the P3 fixture provider.
    """

    provider = ContentBackedTeachingTargetProvider(built_content_db)
    yield provider
    provider.close()


@pytest.fixture()
def db() -> Iterator[sqlite3.Connection]:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture()
def silent_supply(built_content_db: Path) -> Iterator[ContentBackedTargetSupply]:
    """The P5-2 supply read face over the session's built content.db."""

    supply = ContentBackedTargetSupply(built_content_db)
    yield supply
    supply.close()


@pytest.fixture()
def silent_targets(
    silent_supply: ContentBackedTargetSupply,
) -> ContentBackedSilentTargets:
    """The P5-2 chat-leg source over the session's built content.db.

    Resolution only — the commit and the rebuild are the learning chain's
    (the coordinator drives them through its own learning ports).
    """

    return ContentBackedSilentTargets(silent_supply)


@pytest.fixture()
def fence(db: sqlite3.Connection) -> RuntimeEpochFence:
    return epoch.open_runtime_epoch(db)


@pytest.fixture()
def learning(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteLearningStore:
    return SqliteLearningStore(db, fence)


@pytest.fixture()
def learning_controller(learning: SqliteLearningStore) -> LearningController:
    return LearningController(learning)


@pytest.fixture()
def conversation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def generation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> AssemblyGenerationStore:
    return AssemblyGenerationStore(db, fence)


@pytest.fixture()
def conversation(conversation_store: SqliteConversationStore) -> ConvId:
    result = conversation_store.open_conversation(
        CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok), result
    return result.value


@pytest.fixture()
def decision_cycle_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteDecisionCycleStore:
    return SqliteDecisionCycleStore(db, fence)


@pytest.fixture()
def teaching_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteTeachingStore:
    return SqliteTeachingStore(db, fence)


@pytest.fixture()
def teaching_controller(teaching_store: SqliteTeachingStore) -> TeachingController:
    return TeachingController(teaching_store)


def make_lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    """The coordinator lease over this test's epoch (re-declared: four lines,
    and importing it would pull in the P3 fixture provider module)."""

    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder


def production_coordinator(
    conversation_store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    targets: TeachingTargetProvider,
    *,
    provider: ScriptedPersonaProvider | None = None,
    silent_evidence: SilentEvidenceSource | None = None,
) -> ConversationCoordinator:
    """The live assembly whose target supply is the production provider.

    Every port is the real one (conversation, generation, learning, decision
    cycles, teaching, and the content.db-backed target provider); the persona
    provider is a scripted stand-in for a model, which is the one thing a
    repo-native test cannot have.

    ``silent_evidence`` is the P5-2 optional port, defaulted to ``None`` so
    every P5-1 assembly (and its pinned behavior) stays exactly what it was;
    the P5-2 suites pass the real
    :class:`elc.learning.silent_evidence.ContentBackedSilentTargets`.
    """

    persona = PersonaRuntime(
        actions=generation_store,
        provider=provider if provider is not None else ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=make_lease(fence),
        conversation_commands=conversation_store,
        conversation_queries=conversation_store,
        persona=persona,
        generation_actions=generation_store,
        learning=learning,
        character_package=sample_character_package(),
        decision_cycles=decision_cycle_store,
        learning_controller=LearningController(learning),
        teaching=teaching_controller,
        targets=targets,
        silent_evidence=silent_evidence,
    )


# -- drivers ---------------------------------------------------------------


def commit_chat_turn(
    coordinator: ConversationCoordinator,
    cmid: str,
    text: str,
    turn_no: int,
    *,
    conversation: ConvId = CONV,
):
    """One Basic Persona Conversation turn (the IP §1.5 slice's first leg)."""

    result = coordinator.begin_turn(
        CommitUserTurn(
            conversation_id=conversation,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{cmid}"),
                client_message_id=ClientMessageId(cmid),
                conversation_id=str(conversation),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{turn_no}",
                received_at=REQUESTED_AT,
            ),
            raw_content=text,
            runtime_version=RUNTIME_VERSION,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def open_moment(
    coordinator: ConversationCoordinator,
    cmid: str,
    target: str,
    *,
    target_type: str = "RESOURCE",
    conversation: ConvId = CONV,
):
    """One user-initiated teaching request (Gate → CP2 → opening delivery)."""

    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=conversation,
            focus_target_id=TargetId(target),
            target_type=target_type,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def attempt(
    text: str, intent: TeachingControlIntent = TeachingControlIntent.CONTINUE
) -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(
        control_intent=intent,
        attempt_present=True,
        attempt=AttemptPayload(text=text),
    )


def reply(
    coordinator: ConversationCoordinator,
    envelope: TeachingResponseEnvelope,
    cmid: str,
    *,
    conversation: ConvId = CONV,
):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=conversation,
            envelope=envelope,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )


def reply_ok(
    coordinator: ConversationCoordinator,
    envelope: TeachingResponseEnvelope,
    cmid: str,
    *,
    conversation: ConvId = CONV,
):
    result = reply(coordinator, envelope, cmid, conversation=conversation)
    assert isinstance(result, Ok), result
    return result.value


# ---------------------------------------------------------------------------
# Canonical-document readers: pins extract the word lists from docs/ itself
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```")


def canonical_blocks(doc: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block after `heading`, as (line, …) tuples.

    The canonical documents are the authority these tests pin against, so the
    word lists are extracted from the document text at test time rather than
    from a second hand-typed copy. The section ends at the next heading of the
    same or higher level (the heading's own level decides).
    """

    lines = (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"heading {heading!r} not found in {doc}"
    blocks: list[tuple[str, ...]] = []
    index = start
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level and stripped[:head_level + 1].endswith(" "):
                break
        if _FENCE_RE.match(line):
            body: list[str] = []
            index += 1
            while index < len(lines) and not _FENCE_RE.match(lines[index]):
                if lines[index].strip():
                    body.append(lines[index].strip())
                index += 1
            if body:
                blocks.append(tuple(body))
        index += 1
    return blocks


def canonical_lines(doc: str, heading: str, block: int = 0) -> tuple[str, ...]:
    """The `block`-th fenced block after `heading` (0-based)."""

    blocks = canonical_blocks(doc, heading)
    assert len(blocks) > block, (
        f"{doc} {heading!r}: block {block} missing (found {len(blocks)})"
    )
    return blocks[block]
