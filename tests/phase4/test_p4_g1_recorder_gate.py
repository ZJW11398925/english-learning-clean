"""P4-G1 — the Recorder consumption gate, now enforced (P4-1 ①).

P4-0 wrote this file as the *frame*: the two red lines the Relationship
Recorder must satisfy, executable but not yet wired to an implementation.
P4-1 built the Recorder (elc.relationship.recorder) and the durable write
face behind it, so the frame is upgraded to behaviour:

1. **Consumption surface** (BF-05
   ``provider_actions.RELATIONSHIP_PROPOSAL``: allow = CanonicalTurnSlice +
   SamePersonaExistingRelationshipSummary; deny = LearnerState /
   LearningEvidence / TeachingTrace / OtherPersonaRelationship / APISecret).
   Three pins together: the AST scan over ``src/elc/relationship`` (no
   denied import, no denied symbol — with a canary proving the scanner is
   not vacuous), the *signature* pin (the Recorder's state inputs are
   exactly the two allow-listed types — a denied object cannot even be
   passed in), and a sealed-state probe (the Recorder reads nothing but
   ``is_command_payload_turn`` from its state input).

2. **Command turns are not utterances**: the classification is the durable
   read ``is_command_payload_turn`` (never a heuristic over the text), a
   TEACHING_REQUEST / TEACHING_RESPONSE turn is refused for the three
   assertion types, and the real Recorder is what applies it — driven here
   through a real command turn produced by the live teaching assembly.

Not in this slice (recorded so the boundary is explicit, review F1): the
refs↔proposal reconciliation scan (a proposal written but left dangling in
the teaching side's §17 ``evidence_proposal_refs``) belongs to P4-2's
recovery line, where it sits next to the startup recovery scan.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import sqlite3
from pathlib import Path
from typing import get_type_hints

import pytest

from elc.conversation import CanonicalTurnSlice, SqliteConversationStore
from elc.conversation.store import (
    TEACHING_REQUEST_PAYLOAD_MARKER,
    TEACHING_RESPONSE_PAYLOAD_MARKER,
)
from elc.platform.db import migrations
from elc.platform.types import Ok, Result, TurnId
from elc.relationship.recorder import (
    COMMAND_TURN_ASSERTION_MEMORY_TYPES,
    CommandTurnClassifier,
    RelationshipMemoryCandidate,
    RelationshipRecorder,
    RelationshipRecorderKey,
    command_turn_memory_refusal,
)
from elc.relationship.types import (
    RelationshipMemoryType,
    SamePersonaExistingRelationshipSummary,
)
from elc.teaching.envelope import CONTROL_INTENTS, TeachingControlIntent
from tests.conftest import SRC_ROOT
from tests.phase4.conftest import (
    CONV,
    PERSONA_A,
    REL_USER,
    deliver_reply,
    memory_candidate,
    newest_command_turn_slice,
    open_conversation_for,
    open_moment,
    record_turn,
    speak,
    turn_slice,
)

#: BF-05 ``provider_actions.RELATIONSHIP_PROPOSAL.deny`` — the symbols a
#: Relationship Recorder module must never reference.
DENIED_SYMBOLS = (
    "LearnerState",
    "LearningEvidence",
    "TeachingTrace",
    "OtherPersonaRelationship",
    "APISecret",
    "RawLearningEvidence",
    "RawDiagnostics",
    "DeletionLedger",
)

#: Packages the Relationship package must not import (BF-05's deny list plus
#: DOMAIN_MODEL §17 "Relationship 不跨 Persona 泄漏": another persona's
#: relationship面 is reached through this domain's own view, never through
#: an import of the Persona domain).
DENIED_PACKAGES = ("elc.learning", "elc.teaching", "elc.persona")

#: VAL-…5ba74efc.72 ⑤ says three things must not enter Relationship Memory —
#: "TeachingDirective/AttemptEvaluation/LearnerState 不入 Relationship
#: Memory" (DOMAIN_MODEL §18.1: 教学只通过 EphemeralTeachingDirective 注入
#: 当前必要信息，Persona Runtime 默认不获得 PlannerTrace/Teaching 私有态).
#: ``LearnerState`` is a BF-05 ``RELATIONSHIP_PROPOSAL.deny`` word already
#: installed above; the other two arrive through the teaching slice and are
#: pinned here, so all three are named by an executable assertion instead of
#: resting on the package pin and the signature pin alone.
FORBIDDEN_TEACHING_STATE_SYMBOLS = ("TeachingDirective", "AttemptEvaluation")

#: The three VAL-…72 ⑤ words as one list, for the pointed pin below.
VAL_72_FORBIDDEN_SYMBOLS = ("LearnerState", "TeachingDirective", "AttemptEvaluation")

#: The payload markers of a command turn (elc.conversation.store owns them;
#: the ConversationWindow filter and ``is_command_payload_turn`` use exactly
#: these two).
COMMAND_TURN_PAYLOAD_MARKERS = (
    TEACHING_REQUEST_PAYLOAD_MARKER,
    TEACHING_RESPONSE_PAYLOAD_MARKER,
)

#: VAL-…5ba74efc.72 ⑤, word for word: the memory types a command turn must
#: never be read as. P4-0's frame carried two of them and left SHARED_EVENT
#: legal on a command turn; the acceptance criterion names all three, so the
#: shipped rule carries all three (the P4-0 arm was superseded, not
#: silently).
COMMAND_TURN_ASSERTION_MEMORY_TYPES_VERBATIM = (
    "USER_STATED_FACT",
    "CONVERSATION_PREFERENCE",
    "SHARED_EVENT",
)


def _referenced_symbols(source: str) -> set[str]:
    """Identifiers a module references: names, attributes, import aliases.

    Docstrings and other prose are deliberately *not* symbols — the phase-3
    AST pin precedent: naming an interface while explaining a boundary is not
    using it.
    """

    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
    return names


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _module_paths() -> list[Path]:
    return sorted((SRC_ROOT / "relationship").rglob("*.py"))


def _violations(source: str) -> list[str]:
    found: list[str] = []
    for module in _imported_modules(source):
        if any(
            module == denied or module.startswith(f"{denied}.")
            for denied in DENIED_PACKAGES
        ):
            found.append(f"import {module}")
    for symbol in sorted(_referenced_symbols(source)):
        if symbol in DENIED_SYMBOLS or symbol in FORBIDDEN_TEACHING_STATE_SYMBOLS:
            found.append(f"symbol {symbol}")
    return found


def test_the_relationship_package_respects_the_consumption_surface() -> None:
    assert _module_paths(), "the relationship package must exist to be scanned"
    offenders: list[str] = []
    for path in _module_paths():
        for violation in _violations(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(SRC_ROOT)}: {violation}")
    assert not offenders, offenders


def test_the_scan_is_not_vacuous() -> None:
    """Canary: a module that *does* import a denied package, and one that
    merely references a denied symbol without importing anything, are both
    caught — a broken walk cannot pass the pin above silently."""

    assert _violations(
        "from elc.learning.store import SqliteLearningStore\n"
    ) == ["import elc.learning.store"]
    assert _violations("import elc.teaching.evidence as evidence\n") == [
        "import elc.teaching.evidence"
    ]
    assert _violations("x = other.APISecret\n") == ["symbol APISecret"]
    # ... and the scanner really sees the allowed imports the package uses.
    allowed = (SRC_ROOT / "relationship" / "types.py").read_text(encoding="utf-8")
    assert "elc.platform.types" in _imported_modules(allowed)
    assert _violations(allowed) == []
    # The whole package — recorder, validation, sensitivity, store, controller
    # included — passes the same scan (the P4-0 pin, unchanged in spirit and
    # now covering the implementation).
    for path in _module_paths():
        assert _violations(path.read_text(encoding="utf-8")) == [], path.name


def test_the_command_turn_markers_are_the_canonical_two() -> None:
    """The command-turn vocabulary is read off the code that owns it — a
    third command payload added later fails this pin instead of silently
    escaping the red line."""

    assert COMMAND_TURN_PAYLOAD_MARKERS == (
        '"type":"TEACHING_REQUEST"',
        '"type":"TEACHING_RESPONSE"',
    )
    assert {"TEACHING_REQUEST", "TEACHING_RESPONSE"} == {
        marker.split('"')[3] for marker in COMMAND_TURN_PAYLOAD_MARKERS
    }
    # The eleven §4 control intents, word for word (STATE_MACHINES §4).
    assert CONTROL_INTENTS == (
        "CONTINUE",
        "ASK_HINT",
        "ASK_ANSWER",
        "ASK_EXPLANATION",
        "ASK_CLARIFICATION",
        "SKIP",
        "REJECT_TARGET",
        "CHANGE_TOPIC",
        "SWITCH_TARGET",
        "META_DISCUSSION",
        "NONE",
    )
    assert tuple(item.value for item in TeachingControlIntent) == CONTROL_INTENTS


def test_the_command_turn_red_line_predicate() -> None:
    """The shipped predicate (elc.relationship.recorder), pinned against
    VAL-…72 ⑤'s three words."""

    assert COMMAND_TURN_ASSERTION_MEMORY_TYPES == (
        COMMAND_TURN_ASSERTION_MEMORY_TYPES_VERBATIM
    )
    for memory_type in COMMAND_TURN_ASSERTION_MEMORY_TYPES_VERBATIM:
        refusal = command_turn_memory_refusal(
            is_command_turn=True, memory_type=memory_type
        )
        assert refusal is not None
        assert "command turn" in refusal
    # An OPEN_THREAD is not an assertion about the user's own words, so the
    # red line does not name it; and an ordinary turn is unaffected.
    assert (
        command_turn_memory_refusal(
            is_command_turn=True,
            memory_type=RelationshipMemoryType.OPEN_THREAD.value,
        )
        is None
    )
    assert (
        command_turn_memory_refusal(
            is_command_turn=False,
            memory_type=RelationshipMemoryType.USER_STATED_FACT.value,
        )
        is None
    )


def test_the_recorder_state_inputs_are_exactly_the_allow_listed_two() -> None:
    """Signature pin: no denied object can be handed to the Recorder at all.

    The third parameter is the MODEL_PROPOSAL assertion bundle — data about
    what was proposed, not domain state (BF-05 trust_classes: "LLM
    relationship proposal").
    """

    signature = inspect.signature(RelationshipRecorder.record_turn)
    assert [name for name in signature.parameters] == [
        "self",
        "turn",
        "existing",
        "key",
    ]
    hints = get_type_hints(RelationshipRecorder.record_turn)
    assert hints["turn"] is CanonicalTurnSlice
    assert hints["existing"] is SamePersonaExistingRelationshipSummary
    assert hints["key"] is RelationshipRecorderKey
    # The durable classifier is required, not optional: a Recorder that could
    # be built without it could skip the command-turn red line.
    constructor = inspect.signature(RelationshipRecorder.__init__)
    assert "command_turns" in constructor.parameters
    assert (
        constructor.parameters["command_turns"].default
        is inspect.Parameter.empty
    )


def test_the_three_val_72_words_are_all_pointedly_pinned() -> None:
    """VAL-…5ba74efc.72 ⑤: LearnerState / TeachingDirective /
    AttemptEvaluation 不入 Relationship Memory.

    The first was already a BF-05 deny word; the other two are pinned by this
    list, so all three are named by an executable assertion — and the fact
    they are absent from the package is read directly, not inferred from the
    package pin.
    """

    assert "LearnerState" in DENIED_SYMBOLS
    assert FORBIDDEN_TEACHING_STATE_SYMBOLS == (
        "TeachingDirective",
        "AttemptEvaluation",
    )
    assert VAL_72_FORBIDDEN_SYMBOLS == (
        "LearnerState",
        "TeachingDirective",
        "AttemptEvaluation",
    )
    # The scanner catches each of them (a canary per word)...
    for word in VAL_72_FORBIDDEN_SYMBOLS:
        assert _violations(f"directive = teaching.{word}\n") == [f"symbol {word}"]
    # ... and none of them is a symbol anywhere in the shipped package.
    for path in _module_paths():
        symbols = _referenced_symbols(path.read_text(encoding="utf-8"))
        assert not symbols & set(VAL_72_FORBIDDEN_SYMBOLS), path.name


def test_the_recorder_key_cannot_carry_denied_state() -> None:
    """The third parameter is the MODEL_PROPOSAL bundle, not domain state
    (BF-05 trust_classes: "LLM relationship proposal") — pinned structurally:
    the key carries exactly the declared candidates, and a candidate carries
    exactly the assertion fields, so no denied object has a place to travel
    in. Adding a field is a deliberate act that fails this pin.
    """

    key_fields = tuple(
        field.name for field in dataclasses.fields(RelationshipRecorderKey)
    )
    assert key_fields == ("candidates",)
    candidate_fields = tuple(
        field.name for field in dataclasses.fields(RelationshipMemoryCandidate)
    )
    assert candidate_fields == (
        "memory_type",
        "provenance",
        "content",
        "sensitivity_class",
        "persistence_authorization",
        "confidence",
        "supersedes_memory_id",
        "cited_message_ids",
    )
    forbidden = set(DENIED_SYMBOLS) | set(FORBIDDEN_TEACHING_STATE_SYMBOLS)
    assert not set(key_fields + candidate_fields) & forbidden


class _SealedClassifier:
    """A state input that answers the one allow-listed question and raises on
    every other read — so a Recorder that touched anything else would fail
    the test instead of passing it."""

    def __init__(self, answer: bool) -> None:
        self._answer = answer
        self.reads = 0

    def __getattr__(self, name: str) -> object:
        raise AssertionError(
            f"the recorder read {name!r} from its state input; the BF-05"
            " allow list is CanonicalTurnSlice +"
            " SamePersonaExistingRelationshipSummary and nothing else"
        )

    def is_command_payload_turn(self, turn_id: TurnId) -> Result[bool]:
        del turn_id
        self.reads += 1
        return Ok(self._answer)


def test_the_recorder_reads_nothing_but_the_one_allow_listed_question(
    store: SqliteConversationStore,
) -> None:
    conversation = open_conversation_for(store, "conv-gate", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I keep a garden.")
    deliver_reply(store, turn_id, conversation, "What do you grow?")
    slice_ = turn_slice(store, turn_id)

    sealed = _SealedClassifier(answer=False)
    recorder = RelationshipRecorder(sealed)
    outcome = recorder.record_turn(
        turn=slice_,
        existing=SamePersonaExistingRelationshipSummary(
            persona_id=PERSONA_A, user_id=REL_USER
        ),
        key=RelationshipRecorderKey(
            candidates=(memory_candidate("The user keeps a garden."),)
        ),
    )
    assert len(outcome.proposals) == 1
    assert sealed.reads == 1
    # The probe is not vacuous: any other read really does raise.
    with pytest.raises(AssertionError):
        _SealedClassifier(answer=False).learner_state  # type: ignore[attr-defined]


def test_the_seam_the_recorder_uses_is_durable_and_the_store_satisfies_it(
    db: sqlite3.Connection,
) -> None:
    """The classification seam exists, covers both markers, and the durable
    conversation store *is* the protocol — the Recorder reads a durable
    answer, not a heuristic over the text."""

    migrations.apply_migrations(db)
    source = (SRC_ROOT / "conversation" / "store.py").read_text(encoding="utf-8")
    assert "def is_command_payload_turn" in source
    assert "def get_conversation_window" in source
    for marker in COMMAND_TURN_PAYLOAD_MARKERS:
        assert marker in source
    store = SqliteConversationStore(db, _fence(db))
    assert isinstance(store, CommandTurnClassifier)


def test_a_real_command_turn_is_refused_by_the_real_recorder(
    coordinator,
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    db: sqlite3.Connection,
) -> None:
    """The behaviour the frame described: the shipped Recorder, driven by a
    live teaching assembly, refuses to read a command turn as anything the
    user said — and an ordinary turn still produces its proposal."""

    open_moment(coordinator, "cm-gate-1")
    command_slice = newest_command_turn_slice(store, db, CONV)

    refused = record_turn(
        recorder,
        command_slice,
        SamePersonaExistingRelationshipSummary(
            persona_id=PERSONA_A, user_id=REL_USER
        ),
        memory_candidate("The user said they like this."),
        memory_candidate(
            "The user prefers short lessons.",
            memory_type=RelationshipMemoryType.CONVERSATION_PREFERENCE,
        ),
        memory_candidate(
            "They shared a moment.",
            memory_type=RelationshipMemoryType.SHARED_EVENT,
        ),
    )
    assert refused.proposals == ()
    assert [item.reason for item in refused.refusals] == [
        "COMMAND_TURN_SAYS_NOTHING"
    ] * 3

    # Positive control on an ordinary turn of the same assembly.
    conversation = open_conversation_for(store, "conv-gate-2", PERSONA_A)
    turn_id = speak(store, conversation, "cm-gate-2", "I read every evening.")
    accepted = record_turn(
        recorder,
        turn_slice(store, turn_id),
        SamePersonaExistingRelationshipSummary(
            persona_id=PERSONA_A, user_id=REL_USER
        ),
        memory_candidate("The user reads every evening."),
    )
    assert len(accepted.proposals) == 1
    assert accepted.refusals == ()


def _fence(db: sqlite3.Connection):
    from elc.platform.db import epoch

    return epoch.open_runtime_epoch(db)
