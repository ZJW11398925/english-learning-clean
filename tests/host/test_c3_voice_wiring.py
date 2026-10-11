"""C3 — the voice library, wired into the production assembly
(DEC-OPI-a4cf2d0e…6 R3 / host half).

The compiler renders the block (``tests/persona/test_c3_voice_prompt.py``)
and the loader decodes the library (``tests/world/test_c3_voice.py``);
this file pins the *assembly between them*: the composition root holds the
seeded packages, the port resolves the speaking character's entry through
the binding tables' own namespaces, the coordinator degrades every arm
that cannot name a voice to ``None`` (no block, never a failed letter),
and a real bound turn's reply prompt carries 域三's lever. The pin groups:

1. **the port** — the bound conversation's cast character resolves to the
   shipped library's own entry (identity, not a copy: the value equals the
   package's ``voice_for``); a conversation bound to no world answers
   ``NOT_FOUND``; a world this assembly did not seed (a user-created
   world) answers ``NOT_FOUND`` — never a guessed voice;
2. **the coordinator's degradation** — a worldless turn loses the block
   and keeps the reply;
3. **the E2E, over a real turn** — a bound conversation's reply prompt
   carries the framed ``persona-voice`` block with the character's own
   passages, and the narrator's prompt for the same package carries the
   cast's-own-voices section (the two 域三 doors, one host);
4. **the honest zero, assembled** — a host opened over a worlds directory
   whose package ships no library: the turn's prompt loses the block,
   byte-identically to the pre-C3 shape's one-frame law.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from elc.conversation.types import CommitUserTurn
from elc.host import open_host
from elc.persona.commands import UNTRUSTED_SECTION_BEGIN, UNTRUSTED_SECTION_END
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
)
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.world.narrator import build_narrator_prompt
from elc.world.package import BUILTIN_WORLDS_DIR, load_world_package
from tests.host.test_w1_web import REPLY

CONV = "c3-voice-conv"
OTHER_CONV = "c3-voice-other"
NOW = "2026-10-10T09:00:00+00:00"


class RecordingProvider(ScriptedPersonaProvider):
    """The scripted messenger that keeps the prompts it was handed."""

    def __init__(self, script: tuple[ProviderOutput, ...]) -> None:
        super().__init__(script=script)
        self.prompts: list[CompiledPrompt] = []

    def call(self, prompt: CompiledPrompt):
        self.prompts.append(prompt)
        return super().call(prompt)


def _command(text: str, conversation: str, suffix: str) -> CommitUserTurn:
    message = f"c3-{suffix}"
    return CommitUserTurn(
        conversation_id=ConversationId(conversation),
        envelope=InputEnvelope(
            input_id=InputId(message),
            client_message_id=ClientMessageId(message),
            conversation_id=conversation,
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-c3",
    )


def _turn(host, conversation: str, suffix: str) -> str:
    result = host.coordinator.begin_turn(
        _command("你好。", conversation, suffix)
    )
    assert isinstance(result, Ok), result
    assert result.value.turn_status is TurnStatus.COMPLETED
    return result.value.reply_text  # type: ignore[union-attr]


def _frame_of(text: str, name: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if (
            line.startswith(f"{UNTRUSTED_SECTION_BEGIN} {{")
            and f'"section":"{name}"' in line
        ):
            for end in range(index + 1, len(lines)):
                if lines[end].startswith(UNTRUSTED_SECTION_END):
                    return "\n".join(lines[index : end + 1])
            raise AssertionError(f"no end marker after {name}")
    raise AssertionError(f"no frame for {name} in prompt:\n{text}")


def _host_with_binding(app_dir: Path, *, conversation: str = CONV):
    """A prep-1-tier host whose first builtin world's first actor is bound
    to ``conversation`` (the shipped package: Nell Alder)."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(app_dir / "app.db", provider=provider)
    opened = host.open_conversation(ConversationId(conversation))
    assert isinstance(opened, Ok), opened
    world = host.world_store.list_worlds()[0]
    actor = host.world_store.actors_of(str(world.world_id))[0]
    bound = host.world_store.bind_conversation(
        f"wcb-{conversation}",
        str(world.world_id),
        str(actor.actor_id),
        conversation,
        NOW,
    )
    assert isinstance(bound, Ok), bound
    return host, provider, world, actor


def _shipped_voice():
    package = load_world_package(BUILTIN_WORLDS_DIR / "berrymoor.json")
    assert isinstance(package, Ok), package.error.message
    voice = package.value.voice_for("Nell Alder")
    assert voice is not None
    return voice


def _voice_payload(first_line: str) -> dict[str, object]:
    """One minimal valid voice entry whose first passage carries a marker
    (the two-character wiring test tells the entries apart by it)."""

    return {
        "speech_habits": "Short, dry, one clause at a time.",
        "never_says": ["sorry"],
        "quirks": ["taps the counter"],
        "register": "Harbour plain.",
        "samples": {
            "en": [f"{first_line}", "Two.", "Three."],
            "zh": ["一。", "二。", "三。"],
        },
    }


# ---------------------------------------------------------------------------
# 1 — the port
# ---------------------------------------------------------------------------


def test_the_port_resolves_the_bound_characters_own_entry(
    tmp_path: Path,
) -> None:
    """The assembly between the package and the prompt: the bound
    conversation's actor resolves — through ``world_actor``'s persona id
    and the package's own cast row — to exactly the shipped library's
    entry (the same object, not a re-spelled copy)."""

    host, _, _, _ = _host_with_binding(tmp_path)
    try:
        port = host.coordinator._world_voice  # type: ignore[attr-defined]
        answered = port.resolve_world_voice_view(ConversationId(CONV))
        assert isinstance(answered, Ok), answered
        # value equality against a fresh decode of the same file: the
        # port answers the package's entry itself, not a re-spelled copy
        assert answered.value == _shipped_voice()
    finally:
        host.close()


def test_an_unbound_conversation_is_a_not_found_err(tmp_path: Path) -> None:
    """No binding row → ``NOT_FOUND`` (the coordinator's ``None``): the
    prompt loses a block, never a reply — and the port never guesses a
    character for a conversation that binds none."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(tmp_path / "app.db", provider=provider)
    try:
        opened = host.open_conversation(ConversationId(CONV))
        assert isinstance(opened, Ok), opened
        port = host.coordinator._world_voice  # type: ignore[attr-defined]
        answered = port.resolve_world_voice_view(ConversationId(CONV))
        assert isinstance(answered, Err)
        assert answered.error.code is DomainErrorCode.NOT_FOUND
    finally:
        host.close()


def test_a_world_without_a_seeded_package_is_a_not_found_err(
    tmp_path: Path,
) -> None:
    """A user-created world has no package file: the port answers
    ``NOT_FOUND`` — the library is the package's, and this assembly never
    invents one for a world it did not seed."""

    host, _, _, _ = _host_with_binding(tmp_path)
    try:
        created = host.world_store.create_world(
            "world-user-made", "A User World", None, NOW
        )
        assert isinstance(created, Ok), created
        actor = host.world_store.bind_actor(
            "actor-user-made", "world-user-made", "persona-nell-alder", NOW
        )
        assert isinstance(actor, Ok), actor
        opened = host.open_conversation(ConversationId(OTHER_CONV))
        assert isinstance(opened, Ok), opened
        bound = host.world_store.bind_conversation(
            "wcb-user-made",
            "world-user-made",
            "actor-user-made",
            OTHER_CONV,
            NOW,
        )
        assert isinstance(bound, Ok), bound
        port = host.coordinator._world_voice  # type: ignore[attr-defined]
        answered = port.resolve_world_voice_view(ConversationId(OTHER_CONV))
        assert isinstance(answered, Err)
        assert answered.error.code is DomainErrorCode.NOT_FOUND
        assert "no seeded package" in answered.error.message
    finally:
        host.close()


def test_an_actor_whose_persona_the_package_does_not_cast_is_a_validation_err(
    tmp_path: Path,
) -> None:
    """The disagreement arm (review LOW-2): an actor bound through the
    public store API to a real card the seeded package does **not** cast —
    the tables and the package disagree, which is corruption, so the port
    answers ``VALIDATION_FAILED``, never a guessed voice. The other two
    arms (a NULL / unknown actor) are schema-unreachable (the binding
    table's ``NOT NULL`` + FK), the same posture the chronicle port
    declares; this one is reachable and so it carries the pin."""

    host, _, world, _ = _host_with_binding(tmp_path)
    try:
        stranger = host.world_store.bind_actor(
            "actor-not-cast", str(world.world_id), "persona-theo-marsh", NOW
        )
        assert isinstance(stranger, Ok), stranger
        opened = host.open_conversation(ConversationId(OTHER_CONV))
        assert isinstance(opened, Ok), opened
        bound = host.world_store.bind_conversation(
            "wcb-not-cast",
            str(world.world_id),
            "actor-not-cast",
            OTHER_CONV,
            NOW,
        )
        assert isinstance(bound, Ok), bound
        port = host.coordinator._world_voice  # type: ignore[attr-defined]
        answered = port.resolve_world_voice_view(ConversationId(OTHER_CONV))
        assert isinstance(answered, Err)
        assert answered.error.code is DomainErrorCode.VALIDATION_FAILED
        assert "does not cast persona" in answered.error.message
        assert "persona-theo-marsh" in answered.error.message
    finally:
        host.close()


def test_the_port_resolves_the_binding_characters_entry_not_the_first(
    tmp_path: Path,
) -> None:
    """The resolution's own discriminator: a package casting two
    characters, bound to the **second** — the port answers that
    character's entry, never the library's first row (a port that ignored
    the cast row would answer Nell's voice for Theo's letters)."""

    package = {
        "world_id": "world-two-voices",
        "name": "Two Voices",
        "version": 8,
        "calendar_start": "2025-09-14",
        "setting": ["A small town."],
        "cast": [
            {"persona_id": "persona-nell-alder", "name": "Nell Alder"},
            {"persona_id": "persona-theo-marsh", "name": "Theo Marsh"},
        ],
        "event_pool": [
            {
                "kind": "k",
                "narration": "n",
                "narration_zh": "n-中文",
                "days": 1,
            }
        ],
        "supply": {"note": "d-n-c", "families": ["DISC"]},
        "voice": {
            "Nell Alder": _voice_payload("Nell keeps the bindery."),
            "Theo Marsh": _voice_payload("Theo tends the lighthouse."),
        },
    }
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()
    (worlds_dir / "two-voices.json").write_text(
        json.dumps(package, ensure_ascii=False), encoding="utf-8"
    )
    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(
        tmp_path / "app.db", provider=provider, worlds_dir=worlds_dir
    )
    try:
        opened = host.open_conversation(ConversationId(CONV))
        assert isinstance(opened, Ok), opened
        world = host.world_store.list_worlds()[0]
        theo = next(
            actor
            for actor in host.world_store.actors_of(str(world.world_id))
            if str(actor.persona_id) == "persona-theo-marsh"
        )
        bound = host.world_store.bind_conversation(
            "wcb-two-voices",
            str(world.world_id),
            str(theo.actor_id),
            CONV,
            NOW,
        )
        assert isinstance(bound, Ok), bound
        port = host.coordinator._world_voice  # type: ignore[attr-defined]
        answered = port.resolve_world_voice_view(ConversationId(CONV))
        assert isinstance(answered, Ok), answered
        assert "Theo tends the lighthouse." in answered.value.samples_en[0]
        assert "Nell keeps the bindery." not in answered.value.samples_en[0]
        assert _turn(host, CONV, "theo") == REPLY
        prompt = provider.prompts[-1].prompt_text
        assert "Theo tends the lighthouse." in prompt
        assert "Nell keeps the bindery." not in prompt
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 3 — the two prompt doors, one host
# ---------------------------------------------------------------------------


def test_a_bound_turns_reply_prompt_carries_her_own_voice(
    tmp_path: Path,
) -> None:
    """The E2E: one real turn through the bound conversation — the reply
    prompt carries the framed ``persona-voice`` block with Nell Alder's
    own passages, inside it and nowhere outside; the card's frame is still
    the first one (the position law)."""

    host, provider, _, _ = _host_with_binding(tmp_path)
    try:
        assert _turn(host, CONV, "bound") == REPLY
        prompt = provider.prompts[-1].prompt_text
        voice = _shipped_voice()
        frame = _frame_of(prompt, "persona-voice")
        assert f"speech_habits: {voice.speech_habits}" in frame
        assert f"- {voice.samples_en[0]}" in frame
        assert f"- {voice.samples_zh[0]}" in frame
        outside = prompt.replace(frame, "")
        assert voice.samples_en[0] not in outside
        # the block rides immediately after the card's own frame, in the
        # [persona] position — before [contract] — and the card's frame is
        # still the first one
        card = _frame_of(prompt, "persona")
        assert prompt.index(card) < prompt.index(frame)
        assert prompt.index(frame) == prompt.index(card) + len(card) + 2
        assert prompt.index(frame) < prompt.index("[contract]")
    finally:
        host.close()


def test_a_worldless_turn_loses_the_block_not_the_reply(
    tmp_path: Path,
) -> None:
    """The Err arm at the turn's own scale: an unbound conversation's
    reply still lands, and its prompt carries no voice block at all."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(tmp_path / "app.db", provider=provider)
    try:
        opened = host.open_conversation(ConversationId(CONV))
        assert isinstance(opened, Ok), opened
        assert _turn(host, CONV, "worldless") == REPLY
        prompt = provider.prompts[-1].prompt_text
        assert "persona-voice" not in prompt
    finally:
        host.close()


def test_the_narrators_prompt_for_the_same_package_carries_the_cast_voices() -> None:
    """The other 域三 door, on the same package the host seeds: the
    narrator prompt's cast's-own-voices section is there for the shipped
    world (the narrator half is wired by the package itself, no port)."""

    package = load_world_package(BUILTIN_WORLDS_DIR / "berrymoor.json")
    assert isinstance(package, Ok), package.error.message
    prompt = build_narrator_prompt(package.value, (), (), "zh")
    assert "== The cast's own voices ==" in prompt.splitlines()
    assert "Nell Alder — " in prompt


# ---------------------------------------------------------------------------
# 4 — the honest zero, assembled
# ---------------------------------------------------------------------------


def test_a_host_over_a_voice_free_package_adds_no_block(
    tmp_path: Path,
) -> None:
    """The pre-C3 law, assembled: a worlds directory whose package ships
    no library (the same cast, the voice section stripped) turns without a
    ``persona-voice`` block — one frame, the card's — and the reply
    lands."""

    source = json.loads(
        (BUILTIN_WORLDS_DIR / "berrymoor.json").read_text(encoding="utf-8")
    )
    del source["voice"]
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()
    (worlds_dir / "berrymoor.json").write_text(
        json.dumps(source, ensure_ascii=False), encoding="utf-8"
    )
    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(
        tmp_path / "app.db", provider=provider, worlds_dir=worlds_dir
    )
    try:
        opened = host.open_conversation(ConversationId(CONV))
        assert isinstance(opened, Ok), opened
        world = host.world_store.list_worlds()[0]
        actor = host.world_store.actors_of(str(world.world_id))[0]
        bound = host.world_store.bind_conversation(
            "wcb-voicefree",
            str(world.world_id),
            str(actor.actor_id),
            CONV,
            NOW,
        )
        assert isinstance(bound, Ok), bound
        assert _turn(host, CONV, "voicefree") == REPLY
        prompt = provider.prompts[-1].prompt_text
        assert "persona-voice" not in prompt
        # and the port is honest about the absence rather than guessing
        port = host.coordinator._world_voice  # type: ignore[attr-defined]
        answered = port.resolve_world_voice_view(ConversationId(CONV))
        assert isinstance(answered, Err)
        assert answered.error.code is DomainErrorCode.NOT_FOUND
        assert "no voice-library entry" in answered.error.message
    finally:
        host.close()
