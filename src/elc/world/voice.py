"""The characters' own voices — the world package's voice-library face (C3).

Canon (``docs/design/2026-10-08-cognition-and-narrative-quality.md``, 域三
「角色声音库（语言去 AI 味的核心杠杆）」): a model follows "她说话简洁"
far worse than it imitates three passages **she actually wrote** — 「模仿
具体语样远胜遵循抽象描述」. The library's entry per character carries the
five canon faces — ``speech_habits`` (sentence length, tone, rhythm, in
at most three sentences), ``never_says`` (the words she never uses),
``quirks`` (catchphrases and habitual gestures, at most three),
``samples`` (three passages in her own hand — the truth source of the
voice) and ``register`` (the register she speaks in) — plus the optional
sixth ``motivation`` (one static sentence; the P6 programme's first leg,
R4).

Where the faces render (canon 运转咬合): the character's voice library
enters the **persona reply prompt** (her letters sound like her) and the
**narrator prompt's cast section** (in the narration she speaks like
herself). This module declares the decoded record and the port the
composition root wires; the two rendering faces live where their prompts
are built — :func:`elc.world.narrator.build_narrator_prompt` and the
persona compiler's framed ``persona-voice`` block
(:mod:`elc.persona.commands`) — and the JSON decoding lives in the
loader that reads the package's ``voice`` section
(:mod:`elc.world.package`, the strict-decode authority).

The import direction is deliberately one-way: this module imports
nothing from :mod:`elc.persona` (the persona domain imports *it* for the
view's annotation), and nothing from the package loader or the stores
(it is a leaf, like :mod:`elc.world.types`), so both sides of the
prompt pipeline can name the record without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from elc.platform.types import ConversationId, Result

__all__ = [
    "VOICE_MAX_QUIRKS",
    "VOICE_SAMPLE_COUNT",
    "CharacterVoice",
    "WorldVoiceQueries",
]

#: The canon's sample count (域三 裁断点五, the user's adjudication: 「语样
#: 双语各三段——英文为源 + 中文对照」): three passages in the character's
#: own hand, per language. The loader refuses a ``samples`` section whose
#: sides are not exactly this many (a mismatch is a refusal naming the
#: offending side and count, never a half-paired library).
VOICE_SAMPLE_COUNT = 3

#: The canon's quirk ceiling (域三: 「口头禅与习惯动作（≤3 个）」) — a
#: refusal above it, never a silent truncation.
VOICE_MAX_QUIRKS = 3


@dataclass(frozen=True)
class CharacterVoice:
    """One character's decoded voice-library entry (C3, R1).

    The five canon faces plus the optional ``motivation``, in the shapes
    the loader guarantees: ``speech_habits`` / ``register`` non-empty
    strings; ``never_says`` / ``quirks`` tuples of non-empty strings
    (possibly empty — a person who bans or tics nothing is not half a
    person — and duplicate-free); ``quirks`` at most
    :data:`VOICE_MAX_QUIRKS`; ``samples_en`` / ``samples_zh`` exactly
    :data:`VOICE_SAMPLE_COUNT` passages each, English the source and
    Chinese its companion (裁断点五).

    The record is prompt material, never a correspondence face: it
    renders into the narrator's cast section and into the persona reply
    prompt's framed block, and it binds no actor and lands no durable
    row — the package file is its only home.
    """

    speech_habits: str
    register: str
    quirks: tuple[str, ...]
    never_says: tuple[str, ...]
    samples_en: tuple[str, ...]
    samples_zh: tuple[str, ...]
    motivation: str | None = None


class WorldVoiceQueries(Protocol):
    """The conversation→character-voice read (C3) — the port the
    composition root wires so each turn's reply prompt can carry the
    speaking character's own voice library.

    Declared beside the record it resolves (the ``WorldChronicleQueries``
    precedent, :mod:`elc.world_lore.types`): the shape is structural, so
    the composition root's implementation and the coordinator's port
    annotation need no shared import either way.

    ``Result`` is the port's answer shape, and an ``Err`` is an ordinary
    degradation, not a failure: a conversation bound to no world, an
    actor the world tables do not know, a world whose package ships no
    voice library, or a character the library does not name — each of
    them answers "no voice section this turn" (the coordinator's
    byte-identical fallback), never a failed letter.
    """

    def resolve_world_voice_view(
        self, conversation_id: ConversationId
    ) -> Result[CharacterVoice]:
        """The speaking character's own voice entry, or an ``Err`` when
        this conversation has no character whose library entry this
        assembly can name."""
        ...
