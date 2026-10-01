"""cs-1 — the character activation cut's pins (TASK-OPI-…26 / VAL-OPI-…24).

The audit's two producer breaks made the character memory permanently
empty: no candidate producer existed (the ``RelationshipCandidateProvider``
protocol had only scripted test implementations), and no production
conversation was ever bound to a persona (``open_conversation`` passed no
``persona_id``, so the CP4 executors refused every job — even the
deterministic episode rebuild wrote zero rows). This file pins the
activation, end to end, over the production faces:

1. **binding pins** — the shipped chat command and the shipped web face
   both bind the fixed penpal (``conversation.persona_id ==
   persona-nell-alder``); a legacy NULL-persona row is adopted
   idempotently, and a conversation that already carries a persona is
   never overwritten;
2. **[persona] rendering pins** — the compiled prompt carries the penpal's
   real name and card text inside the trust frame; the card text carries
   zero mechanism words (the cs-0 blacklist plus the pedagogy words —
   the role cannot know a teaching system exists); ``open_host``'s default
   package **is** the penpal (an explicit ``None`` restores the bare
   shape);
3. **candidate producer pins** — the bilingual pattern inventory extracts
   the plainly stated facts (unit), a patternless utterance proposes
   nothing (unit), and a real turn's facts reach the durable
   ``relationship_memory`` through the Recorder's refusal order and the
   Controller's validate / gate / dedupe faces (e2e); a clean turn adds
   no rows;
4. **episode activation pins** — with the persona bound, the deterministic
   episode rebuild lands real rows (the refusal that made this impossible
   is gone) and the role's prompt carries the ``[episode]`` section and
   the remembered facts;
5. **endpoint partition pins** — ``/api/memory``'s five panels each name
   their semantic partition (``character`` / ``learning`` / ``audit``)
   with the pre-cs-1 shapes intact (an additive key; the page does not
   read it yet — cs-2 wires that face);
6. **single-source pins** — every literal of the penpal lives in exactly
   one src file, and the three consumers import it.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import socket
import sqlite3
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from elc.cli import main as cli_main
from elc.content.build import build_content_db
from elc.conversation.types import CanonicalTurnSlice, CommitUserTurn, UserTurnRecord
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import open_host
from elc.persona.commands import UNTRUSTED_SECTION_BEGIN, UNTRUSTED_SECTION_END
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE,
    PENPAL_PERSONA_ID,
    penpal_character_package,
)
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    MessageSequence,
    Ok,
    PersonaId,
    TurnId,
    TurnSequence,
    UserTurnId,
)
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.web import _WebFace, run_web
from tests.host.test_cs0_teaching_isolation import MECHANISM_WORDS

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "elc"

CONV = ConversationId("cs1-conv")
#: A distinctive persona id a second character could own (the never-
#: overwrite arm of the binding pin).
OTHER_PERSONA = PersonaId("persona-someone-else")

#: The pedagogy words the card text must never carry, beyond the cs-0
#: runtime blacklist: the role does not know teaching exists (cs-0's
#: unknowing-messenger rule, applied to the character's own source text).
PEDAGOGY_WORDS = (
    "teach",
    "lesson",
    "learn",
    "study",
    "批注",
    "教学",
    "课",
)

#: The full character-text blacklist: cs-0's runtime words plus the
#: pedagogy words.
CARD_BLACKLIST = MECHANISM_WORDS + PEDAGOGY_WORDS


def _card_text() -> str:
    """The penpal's free-text columns, joined (the character's own words)."""

    package = penpal_character_package()
    return "; ".join(
        (
            package.identity,
            package.personality,
            package.background,
            package.speech_style,
            package.values,
            package.boundaries,
            package.opening,
            package.scenario,
            package.generation_policy,
            "; ".join(package.lore_refs),
        )
    )


class RecordingProvider(ScriptedPersonaProvider):
    """The scripted messenger that keeps the prompts it was handed."""

    def __init__(self, script: tuple[ProviderOutput, ...]) -> None:
        super().__init__(script=script)
        self.prompts: list[object] = []

    def call(self, prompt: object):
        self.prompts.append(prompt)
        return super().call(prompt)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("cs1-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def _command(text: str, suffix: str) -> CommitUserTurn:
    message = f"cs1-{suffix}"
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(message),
            client_message_id=ClientMessageId(message),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-cs1",
    )


@pytest.fixture()
def cs1_world(tmp_path: Path, pilot_content_db: Path):
    """One real process: the full chain over the pilot artifact, the penpal
    card injected by open_host's default, the conversation bound by the
    same call the shipped faces make — and the prompts it saw."""

    provider = RecordingProvider(
        script=(
            ProviderOutput(text="How lovely to hear from you."),
            ProviderOutput(text="I mended a hymnal today."),
        )
    )
    host = open_host(tmp_path / "app.db", provider=provider,
                     content_db_path=pilot_content_db)
    try:
        assert isinstance(
            host.open_conversation(CONV, persona_id=PENPAL_PERSONA_ID), Ok
        )
        yield host, provider
    finally:
        host.close()


# ---------------------------------------------------------------------------
# ① the binding pins


def test_the_chat_command_binds_the_penpal(tmp_path: Path) -> None:
    """The shipped chat command's conversation carries the penpal's
    persona id in the durable row (the real host, the real open)."""

    app_db = tmp_path / "app.db"
    out, err = io.StringIO(), io.StringIO()
    code = cli_main(
        [
            "chat",
            "--app-db",
            str(app_db),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "CS1_UNSET_KEY_VAR",
        ],
        stdout=out,
        stderr=err,
        provider=ScriptedPersonaProvider(script=()),
        stdin=io.StringIO(":quit\n"),
    )
    assert (code, err.getvalue()) == (0, "")
    with sqlite3.connect(f"file:{app_db}?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT persona_id FROM conversation WHERE conversation_id = ?",
            ("cli-default",),
        ).fetchone()
    assert row == (str(PENPAL_PERSONA_ID),)


@contextlib.contextmanager
def _web_world(app_db: Path) -> Iterator[int]:
    """One serving web face over the real ``run_web`` (the w-1 stack
    shape): the host lives on the worker thread; the test reads the
    durable row through its own read-only connection."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    ready, stop = threading.Event(), threading.Event()
    box: dict[str, object] = {}

    def worker() -> None:
        try:
            host = open_host(
                app_db, provider=ScriptedPersonaProvider(script=())
            )
            box["host"] = host
            run_web(host, port, ready=ready, stop=stop)
        except BaseException as exc:  # surfaced to the test thread below
            box["error"] = exc
            ready.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert ready.wait(timeout=60.0), "the web worker never became ready"
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    try:
        yield port
    finally:
        stop.set()
        thread.join(timeout=60.0)


def test_the_web_face_binds_the_penpal(tmp_path: Path) -> None:
    """The shipped web face's conversation carries the penpal's persona id
    (the real run_web open, before the bind)."""

    app_db = tmp_path / "app.db"
    with _web_world(app_db):
        with sqlite3.connect(f"file:{app_db}?mode=ro", uri=True) as db:
            row = db.execute(
                "SELECT persona_id FROM conversation WHERE conversation_id"
                " = ?",
                ("web-default",),
            ).fetchone()
    assert row == (str(PENPAL_PERSONA_ID),)


def test_a_legacy_null_persona_row_is_adopted_and_never_overwritten(
    tmp_path: Path,
) -> None:
    """The dogfood app.db's legacy rows (``persona_id`` NULL) are adopted
    idempotently by the same open the shipped faces make; a conversation
    that already carries a persona keeps it; the store's own fill refuses
    a conversation that does not exist."""

    host = open_host(tmp_path / "app.db",
                     provider=ScriptedPersonaProvider(script=()))
    try:
        legacy = ConversationId("legacy-conv")
        # the pre-cs-1 shape: opened without a persona, the row keeps NULL
        assert isinstance(host.open_conversation(legacy), Ok)
        record = host.conversations.get_conversation(legacy)
        assert isinstance(record, Ok) and record.value is not None
        assert record.value.persona_id is None
        # the adoption: one open with the penpal fills it
        assert isinstance(
            host.open_conversation(legacy, persona_id=PENPAL_PERSONA_ID), Ok
        )
        record = host.conversations.get_conversation(legacy)
        assert record.value is not None
        assert record.value.persona_id == PENPAL_PERSONA_ID
        # idempotent: reopening changes nothing
        assert isinstance(
            host.open_conversation(legacy, persona_id=PENPAL_PERSONA_ID), Ok
        )
        record = host.conversations.get_conversation(legacy)
        assert record.value is not None
        assert record.value.persona_id == PENPAL_PERSONA_ID
        # never overwrite: a bound conversation keeps its own character
        bound = ConversationId("bound-conv")
        assert isinstance(
            host.open_conversation(bound, persona_id=OTHER_PERSONA), Ok
        )
        assert isinstance(
            host.open_conversation(bound, persona_id=PENPAL_PERSONA_ID), Ok
        )
        record = host.conversations.get_conversation(bound)
        assert record.value is not None
        assert record.value.persona_id == OTHER_PERSONA
        # the store's fill alone refuses a missing conversation
        outcome = host.conversations.bind_persona_if_unbound(
            ConversationId("no-such-conv"), PENPAL_PERSONA_ID
        )
        assert not isinstance(outcome, Ok)
    finally:
        host.close()


# ---------------------------------------------------------------------------
# ② the [persona] rendering pins


def test_open_hosts_default_package_is_the_penpal() -> None:
    """The composition root's default **is** the fixed penpal (a caller may
    pass another package; an explicit ``None`` restores the bare shape)."""

    default = inspect.signature(open_host).parameters[
        "character_package"
    ].default
    assert default is PENPAL_CHARACTER_PACKAGE
    # one construction, one truth: the default and the factory agree
    assert penpal_character_package() == PENPAL_CHARACTER_PACKAGE


def test_the_penpal_card_renders_into_the_compiled_prompt(cs1_world) -> None:
    """The role's prompt carries the card: the structure lines (package and
    persona ids) and the framed card text with the character's name and
    signature line — the production chain, from the default injection to
    the provider's eyes."""

    host, provider = cs1_world
    result = host.coordinator.begin_turn(_command("你好！我叫小明。", "card"))
    assert isinstance(result, Ok), result
    assert result.value.turn_status is TurnStatus.COMPLETED
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]
    assert "character_package_id: cpkg-nell-alder" in prompt
    assert "persona_id: persona-nell-alder" in prompt
    assert "Nell Alder" in prompt
    assert "Yours, Nell" in prompt
    # the card text renders inside the trust frame (the P9-R1 shape)
    start = prompt.index(UNTRUSTED_SECTION_BEGIN)
    end = prompt.index(UNTRUSTED_SECTION_END, start)
    frame = prompt[start:end]
    assert '"section":"persona"' in frame
    assert "identity: Nell Alder" in frame


def test_the_penpal_text_carries_zero_mechanism_words(cs1_world) -> None:
    """The character's own words — the source card and the frame the
    provider actually reads — carry none of the runtime's mechanism
    vocabulary and none of the pedagogy words (the role cannot know a
    teaching system exists)."""

    card = _card_text()
    for word in CARD_BLACKLIST:
        assert word not in card, word

    host, provider = cs1_world
    assert isinstance(
        host.coordinator.begin_turn(_command("hello!", "blacklist")), Ok
    )
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]
    start = prompt.index(UNTRUSTED_SECTION_BEGIN)
    end = prompt.index(UNTRUSTED_SECTION_END, start)
    frame = prompt[start:end]
    for word in CARD_BLACKLIST:
        assert word not in frame, word


def test_an_explicit_none_package_restores_the_bare_shape(
    tmp_path: Path,
) -> None:
    """``character_package=None`` is the documented escape hatch: the
    compiled prompt falls back to the degradation arm (no card, no name)."""

    from elc.persona.commands import PromptCompiler
    from elc.persona.types import (
        GenerationContext,
        PromptCompilationRequest,
    )

    host = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=()),
        character_package=None,
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        result = host.coordinator.begin_turn(_command("hello", "bare"))
        assert isinstance(result, Ok), result
        compiled = PromptCompiler().compile(
            PromptCompilationRequest(
                conversation_id=CONV,
                persona_id=PersonaId("persona-default"),
                interaction_channel=InteractionChannel.TEXT,
                generation_context=GenerationContext(
                    character_package=None,
                    relationship_view=None,
                    episode_view=None,
                    world_lore_view=None,
                    disclosed_user_profile=None,
                    conversation_window=None,
                    language_policy="follow-user",
                    generation_policy="default",
                ),
            )
        )
        assert isinstance(compiled, Ok)
        assert "Nell Alder" not in compiled.value.prompt_text
    finally:
        host.close()


# ---------------------------------------------------------------------------
# ③ the candidate producer pins


def _slice_with(text: str) -> CanonicalTurnSlice:
    """One canonical slice carrying exactly this user utterance (the unit
    world of the producer pins)."""

    return CanonicalTurnSlice(
        turn_id=TurnId("t-cs1"),
        conversation_id=CONV,
        turn_sequence=TurnSequence(1),
        user_turn=UserTurnRecord(
            user_turn_id=UserTurnId("u-cs1"),
            turn_id=TurnId("t-cs1"),
            conversation_id=CONV,
            turn_sequence=TurnSequence(1),
            message_sequence=MessageSequence(1),
            input_id="in-cs1",
            client_message_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_content=text,
            normalized_content=None,
        ),
        assistant_turn=None,
        outcome=None,
    )


def test_the_patterns_extract_the_plain_bilingual_facts() -> None:
    """The inventory's ZH and EN faces, one candidate per plainly stated
    fact, each shaped to walk the gates honestly."""

    from elc.relationship.candidates import PatternCandidateProvider
    from elc.relationship.types import (
        MemoryProvenance,
        MemorySensitivityClass,
        PersistenceAuthorization,
    )

    provider = PatternCandidateProvider()
    outcome = provider.candidates_for(
        _slice_with("我叫小明，我在上海工作。我喜欢书法。")
    )
    assert isinstance(outcome, Ok)
    assert [candidate.content for candidate in outcome.value] == [
        "The user's name is 小明.",
        "The user works at 上海.",
        "The user likes 书法.",
    ]
    english = provider.candidates_for(
        _slice_with(
            "My name is John Smith. I work as a teacher and I live in"
            " Leeds."
        )
    )
    assert isinstance(english, Ok)
    assert [candidate.content for candidate in english.value] == [
        "The user's name is John Smith.",
        "The user works as teacher.",
        "The user lives in Leeds.",
    ]
    for candidate in (*outcome.value, *english.value):
        assert candidate.memory_type.value == "USER_STATED_FACT"
        assert candidate.provenance is MemoryProvenance.USER_STATED_FACT
        assert candidate.sensitivity_class is MemorySensitivityClass.PERSONAL
        assert (
            candidate.persistence_authorization
            is PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
        )
        assert candidate.confidence is None
        assert candidate.cited_message_ids == ("u-cs1",)


def test_an_utterance_without_a_pattern_proposes_nothing() -> None:
    """The honest empty result: weather, questions and pronoun slots
    propose nothing — coverage stays narrow on purpose."""

    from elc.relationship.candidates import PatternCandidateProvider

    provider = PatternCandidateProvider()
    for text in ("今天天气不错", "你喜欢什么？", "我喜欢你", "I'm a bit tired"):
        outcome = provider.candidates_for(_slice_with(text))
        assert isinstance(outcome, Ok)
        assert outcome.value == (), text


def test_stated_facts_reach_the_durable_memory_through_the_pipeline(
    cs1_world,
) -> None:
    """The e2e half of the producer pins: one real turn's self-introduction
    lands as durable ``relationship_memory`` rows for the penpal pair —
    nothing here pre-cleared the gates; the rows exist because the
    Recorder's refusal order and the Controller's validate / gate / dedupe
    faces let them through."""

    host, _provider = cs1_world
    before = host.db.execute(
        "SELECT COUNT(*) FROM relationship_memory"
    ).fetchone()[0]
    result = host.coordinator.begin_turn(
        _command("你好！我叫小明，我在上海工作。我喜欢书法。", "facts")
    )
    assert isinstance(result, Ok), result
    assert result.value.turn_status is TurnStatus.COMPLETED
    rows = host.db.execute(
        "SELECT canonical_content FROM relationship_memory"
        " ORDER BY relationship_memory_id"
    ).fetchall()
    contents = {row[0] for row in rows}
    assert len(rows) == before + 3
    assert {
        "The user's name is 小明.",
        "The user works at 上海.",
        "The user likes 书法.",
    } <= contents
    pair = host.db.execute(
        "SELECT persona_id, user_id, provenance, memory_type,"
        " sensitivity_class, persistence_authorization, confidence"
        " FROM relationship_memory LIMIT 1"
    ).fetchone()
    assert pair == (
        "persona-nell-alder",
        "user-local-v1",
        "USER_STATED_FACT",
        "USER_STATED_FACT",
        "PERSONAL",
        "VALIDATED_DOMAIN_WRITE",
        None,
    )


def test_a_clean_turn_adds_no_memory_rows(cs1_world) -> None:
    """The negative e2e: an utterance the inventory does not cover proposes
    nothing — the durable count does not move."""

    host, _provider = cs1_world
    before = host.db.execute(
        "SELECT COUNT(*) FROM relationship_memory"
    ).fetchone()[0]
    result = host.coordinator.begin_turn(
        _command("今天天气不错。", "clean")
    )
    assert isinstance(result, Ok), result
    after = host.db.execute(
        "SELECT COUNT(*) FROM relationship_memory"
    ).fetchone()[0]
    assert after == before


# ---------------------------------------------------------------------------
# ④ the episode activation pins


def test_the_episode_lands_and_the_role_sees_the_thread(cs1_world) -> None:
    """With the persona bound, the deterministic episode rebuild writes its
    durable row (the executor's persona refusal is gone) and the second
    turn's prompt carries the ``[episode]`` section and the remembered
    facts — the character actually remembers."""

    host, provider = cs1_world
    first = host.coordinator.begin_turn(
        _command("你好！我叫小明，我喜欢书法。", "ep-1")
    )
    assert isinstance(first, Ok), first
    second = host.coordinator.begin_turn(_command("今天练了半小时字。", "ep-2"))
    assert isinstance(second, Ok), second

    episode = host.db.execute(
        "SELECT conversation_id, version, summary, recent_events FROM"
        " episode"
    ).fetchall()
    assert len(episode) == 1
    assert episode[0][0] == str(CONV)
    assert episode[0][3] != ""  # recent_events: the visible turns, listed

    assert len(provider.prompts) == 2
    prompt = provider.prompts[1].prompt_text  # type: ignore[attr-defined]
    assert "[episode]" in prompt
    episode_start = prompt.index("[episode]")
    episode_block = prompt[
        episode_start : prompt.index(UNTRUSTED_SECTION_END, episode_start)
    ]
    keys = [
        line.split(": ", 1)[0]
        for line in episode_block.splitlines()[1:]
        if line.strip()
    ]
    assert keys[0] == "prompt_version"
    assert keys == [
        "prompt_version",
        "episode_id",
        "version",
        "status",
        "summary",
        "open_threads",
        "recent_events",
    ]
    recent = [
        line
        for line in episode_block.splitlines()
        if line.startswith("recent_events: ")
    ]
    assert len(recent) == 1 and recent[0] != "recent_events: "
    # the memory rides the [relationship] section into the same prompt
    relationship_start = prompt.index("[relationship]")
    relationship_block = prompt[
        relationship_start : prompt.index("\n\n[", relationship_start)
    ]
    assert "USER_STATED_FACT: The user's name is 小明." in relationship_block
    assert "USER_STATED_FACT: The user likes 书法." in relationship_block


# ---------------------------------------------------------------------------
# ⑤ the endpoint partition pins


def test_the_memory_panels_carry_their_domain_partition(cs1_world) -> None:
    """``/api/memory``'s five panels each name their partition, and the
    pre-cs-1 shapes are intact (the additive key changed nothing the page
    reads today)."""

    host, _provider = cs1_world
    assert isinstance(
        host.coordinator.begin_turn(_command("我叫小明。", "mem")), Ok
    )
    face = _WebFace(host, str(CONV))
    readout = face.memory()
    assert readout["relationship_memory"]["domain"] == "character"
    assert readout["episode"]["domain"] == "character"
    assert readout["learner_states"]["domain"] == "learning"
    assert readout["evidence"]["domain"] == "learning"
    assert readout["tombstones"]["domain"] == "audit"
    # the old shapes are untouched: each panel keeps its own payload key
    assert isinstance(readout["relationship_memory"]["memories"], list)
    assert isinstance(readout["episode"]["episodes"], list)
    assert isinstance(readout["learner_states"]["states"], list)
    assert "claims" in readout["evidence"]
    assert "tombstones" in readout["tombstones"]
    # and the panels really answer, not error: the memory rows are visible
    assert any(
        memory["canonical_content"] == "The user's name is 小明."
        for memory in readout["relationship_memory"]["memories"]
    )


# ---------------------------------------------------------------------------
# ⑥ the single-source pins


def _src_files_with(literal: str) -> set[str]:
    return {
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if literal in path.read_text(encoding="utf-8")
    }


@pytest.mark.parametrize(
    "literal",
    ["Nell Alder", "persona-nell-alder", "cpkg-nell-alder", "Berrymoor"],
)
def test_the_penpal_lives_in_exactly_one_src_file(literal: str) -> None:
    """Every literal of the character has exactly one physical point: the
    penpal module (a second spelling anywhere in src is a drift the pin
    refuses)."""

    assert _src_files_with(literal) == {str(Path("persona") / "penpal.py")}


def test_the_three_consumers_import_the_penpal_constants() -> None:
    """host / cli / web reach the character through the one import — none
    of them spells a value of its own."""

    assert (
        "from elc.persona.penpal import PENPAL_CHARACTER_PACKAGE"
        in (SRC / "host.py").read_text(encoding="utf-8")
    )
    assert (
        "from elc.persona.penpal import PENPAL_PERSONA_ID"
        in (SRC / "cli.py").read_text(encoding="utf-8")
    )
    assert (
        "from elc.persona.penpal import PENPAL_PERSONA_ID"
        in (SRC / "web.py").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# ⑦ the cs-1R disposition pins (review MEDIUM-1 + LOW-2)
#
# The ZH fake-capture family: slots now end at person words, the
# negation/cleft family is refused, fullwidth letters land as ASCII and the
# trailing 的 particle is stripped. Every adversarial sample the review
# ran is pinned here with its exact expected behavior.


def _zh_contents(text: str) -> list[str]:
    from elc.relationship.candidates import PatternCandidateProvider

    outcome = PatternCandidateProvider().candidates_for(_slice_with(text))
    assert isinstance(outcome, Ok), outcome
    return [candidate.content for candidate in outcome.value]


@pytest.mark.parametrize(
    ("utterance",),
    [
        ("我叫你一声",),
        ("我叫你过来一下",),
        ("我喜欢你做的菜",),
        # the whole-slot pronoun rejection the v1 already had (regression)
        ("我喜欢你",),
        ("我喜欢他们做的菜",),
    ],
)
def test_the_zh_person_word_slots_propose_nothing(utterance: str) -> None:
    """A slot about someone else is not a self-statement: person words end
    a ZH slot at capture, so these propose nothing (MEDIUM-1's
    second/third-person arm)."""

    assert _zh_contents(utterance) == []


@pytest.mark.parametrize(
    ("utterance",),
    [
        ("我喜欢的不是工作",),
        ("我喜欢的工作不是这个",),
        # the cleft family: 「我喜欢的是…」 says nothing extractable
        ("我喜欢的是书法",),
    ],
)
def test_the_zh_negation_and_cleft_slots_propose_nothing(
    utterance: str,
) -> None:
    """A slot that begins with 的 or carries 不是 compares or negates — it
    never becomes content (MEDIUM-1's negation arm). The bare attributive
    不 stays legal: 「我喜欢不辣的菜」 still proposes."""

    assert _zh_contents(utterance) == []
    assert _zh_contents("我喜欢不辣的菜") == ["The user likes 不辣的菜."]


def test_the_zh_first_person_clause_boundary_splits_the_facts() -> None:
    """「我叫小明我住在杭州」 (no punctuation): 我 ends the name slot, so
    the two clauses propose their two facts independently — the name never
    swallows the city (MEDIUM-1's connected-writing adjudication: truncate,
    not refuse)."""

    assert _zh_contents("我叫小明我住在杭州") == [
        "The user's name is 小明.",
        "The user lives in 杭州.",
    ]


def test_fullwidth_letters_land_as_ascii() -> None:
    """Ｍａｒｙ is stored as Mary (LOW-2): NFKC folds the fullwidth forms
    before the slot becomes content."""

    assert _zh_contents("我的名字是Ｍａｒｙ") == ["The user's name is Mary."]


def test_the_trailing_de_particle_is_stripped() -> None:
    """「我姓王的」 remembers surname 王, not 王的 (LOW-2)."""

    assert _zh_contents("我姓王的") == ["The user's surname is 王."]
