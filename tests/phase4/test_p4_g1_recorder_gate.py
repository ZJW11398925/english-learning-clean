"""P4-0 ⑤ — the P4-G1 gate skeleton (Recorder consumption red lines).

This is the *frame*, not the enforcement: P4-1 builds the Relationship
Recorder, and these are the two red lines it must satisfy. Both are written
as executable structure rather than as prose, and neither pretends the
Recorder exists:

1. **Consumption surface** (BF-05 ``provider_actions.RELATIONSHIP_PROPOSAL``:
   allow = CanonicalTurnSlice + SamePersonaExistingRelationshipSummary;
   deny = LearnerState / LearningEvidence / TeachingTrace /
   OtherPersonaRelationship / APISecret). The frame is an AST scan over
   ``src/elc/relationship``: the package may not import
   ``elc.learning`` / ``elc.teaching`` / ``elc.persona``, and the denied
   symbols may not appear as identifiers anywhere in it. Today's package
   passes (it imports platform + itself); the canary tests prove the scanner
   would not pass a violation silently.

2. **Command turns are not utterances** (TASK-…84 ⑤): the Phase 3 command
   turns (TEACHING_REQUEST) and reply turns (TEACHING_RESPONSE) carry a
   typed payload and an empty utterance, so they must never be read as
   USER_STATED_FACT. The frame enumerates the live vocabulary (the two
   payload markers, the eleven §4 control intents) and provides the refusal
   predicate; the implementation assertion (the Recorder calling it for
   every candidate memory) belongs to P4-1, and the seam it must use —
   ``SqliteConversationStore.is_command_payload_turn`` — is pinned here.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from elc.conversation.store import (
    TEACHING_REQUEST_PAYLOAD_MARKER,
    TEACHING_RESPONSE_PAYLOAD_MARKER,
)
from elc.platform.db import migrations
from elc.relationship.types import RelationshipMemoryType
from elc.teaching.envelope import CONTROL_INTENTS, TeachingControlIntent
from tests.conftest import SRC_ROOT

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

#: The payload markers of a command turn (elc.conversation.store owns them;
#: the ConversationWindow filter and ``is_command_payload_turn`` use exactly
#: these two).
COMMAND_TURN_PAYLOAD_MARKERS = (
    TEACHING_REQUEST_PAYLOAD_MARKER,
    TEACHING_RESPONSE_PAYLOAD_MARKER,
)

#: The memory types a command turn must never be recorded as: both assert
#: something about what the *user* said or prefers, and a command turn says
#: nothing (its utterance is empty by construction).
COMMAND_TURN_ASSERTION_MEMORY_TYPES = (
    RelationshipMemoryType.USER_STATED_FACT.value,
    RelationshipMemoryType.CONVERSATION_PREFERENCE.value,
)


def command_turn_memory_refusal(
    *, is_command_turn: bool, memory_type: str
) -> str | None:
    """The P4-G1 red-line predicate (P4-0 ⑤ skeleton).

    Returns the refusal message when a candidate memory would assert
    something about the user's own words or preferences on a turn that said
    nothing, and ``None`` when the candidate is legal. P4-1's Recorder calls
    it before it proposes anything; today the call site does not exist yet,
    which is exactly what the surrounding tests state.
    """

    if not is_command_turn:
        return None
    if memory_type in COMMAND_TURN_ASSERTION_MEMORY_TYPES:
        return (
            f"a command turn never becomes a {memory_type}: the turn carries"
            " a typed payload and an empty utterance, so nothing was said"
            " (DOMAIN_MODEL §18.1 UNTRUSTED_CONTENT; BF-05"
            " RELATIONSHIP_PROPOSAL)"
        )
    return None


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
        if symbol in DENIED_SYMBOLS:
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
    """The predicate P4-1's Recorder must consult: a command turn never
    becomes a USER_STATED_FACT (or a CONVERSATION_PREFERENCE)."""

    for memory_type in COMMAND_TURN_ASSERTION_MEMORY_TYPES:
        refusal = command_turn_memory_refusal(
            is_command_turn=True, memory_type=memory_type
        )
        assert refusal is not None
        assert "command turn" in refusal
    # A SHARED_EVENT could still be honest about an episode... but it is not
    # what the red line is about, and an ordinary turn is unaffected.
    assert (
        command_turn_memory_refusal(
            is_command_turn=True,
            memory_type=RelationshipMemoryType.SHARED_EVENT.value,
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


def test_the_seam_the_recorder_must_use_is_durable_and_complete(
    db: sqlite3.Connection,
) -> None:
    """The classification seam exists and covers both markers: the Recorder
    reads ``is_command_payload_turn`` (a durable read, not a heuristic over
    text), and the ConversationWindow filter refuses the same two payloads.
    The Recorder wiring itself is P4-1 — the face it will replace is still the
    unimplemented one."""

    migrations.apply_migrations(db)
    source = (SRC_ROOT / "conversation" / "store.py").read_text(encoding="utf-8")
    assert "def is_command_payload_turn" in source
    assert "def get_conversation_window" in source
    for marker in COMMAND_TURN_PAYLOAD_MARKERS:
        assert marker in source
    # The Recorder face itself is still unimplemented (no pretend P4-1).
    from elc.relationship.controller import RelationshipController

    with pytest.raises(NotImplementedError):
        RelationshipController().propose_memory(None)  # type: ignore[arg-type]
