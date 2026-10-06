"""The world narrator (WR-2, DEC-OPI-5fc42174…49; WR-4 correction
…58) — the paradigm flip's generation face: the world's own next one
or two story beats, generated from the world's own life alone.

What this module claims, no more: the prompt is composed from the world
package's bible (the setting prose, the cast on one line, the whole
CURRENT lore fact set), the recent chronicle (the last eight narrations,
oldest first — an empty chronicle answers an honest ``story begins``
line) and the rhythm law (novel prose, small-town voice; consistent
with the history above; nothing already happened repeated; each beat one
to three sentences; exactly one or two beats; each beat spanning zero to
two story days; the narration in the interface language; kinds as short
slugs). **WR-4 (the user's third direction, DEC-…58): no letter ever
enters the prompt** — the living-world spec keeps the layers apart
(§4.1: the reply is the run's mechanical wind-up, never content; the
走向 entry: the user's influence on the world rides the direction
channel, never the letter layer) — the world narrates its own life,
unreactive to correspondence. The provider is called **once**, blocking
(the same protocol the
persona runtime dials — never the streamed face), and the answer is
parsed **strictly**: the whole text must be exactly one JSON object
``{"beats": [...]}`` carrying one or two beat objects, each with exactly
``kind`` (a slug of lowercase letters, digits and hyphens, at most 32
characters), ``narration`` (non-blank) and ``days`` (an honest int, 0
through 2). Anything else — prose around the JSON, a missing or
malformed field, an out-of-range span, an empty or oversized batch, an
unexpected key — refuses the **whole batch** (诚实不造假: no partial
adoption, no guessed beat, and **no fallback to the retired pool** —
the fixed-pool sampling is no longer a production path of any step).

The return shape is the Result the orchestrator consumes: ``Ok`` with
the generated beats (the type allows an empty tuple — the world's quiet
— though the strict parser itself never produces one: an empty batch is
a refusal), or ``Err`` carrying either the provider's own fault word
verbatim as the message (the passthrough the orchestrator's quiet arm
reads — ``not-configured`` among them) or a ``narrator refused: …``
sentence naming what the answer got wrong.

Layering note: this module imports the provider's *types and protocol*
(:mod:`elc.persona.types`, :mod:`elc.persona.provider`) and the
package's shapes — it touches no store and no run row (the orchestrator
does the durable half around it), and nothing imports back.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from elc.persona.provider import PersonaProvider
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
)
from elc.world.package import WorldPackage

__all__ = [
    "GeneratedBeat",
    "NARRATOR_CONTRACT",
    "NARRATOR_PERSONA_ID",
    "NARRATOR_SOURCE",
    "RECENT_CHRONICLE_LIMIT",
    "WorldNarrator",
    "build_narrator_prompt",
]

#: The chronicle ``source`` word narrator-written events carry (a free
#: word — the source vocabulary is unregistered, the 0024 convention).
#: It lives beside the engine's ``world_engine`` and names the new
#: paradigm's own provenance in the durable chronicle.
NARRATOR_SOURCE = "world_narrator"

#: The persona word the narrator's prompt rides. The world has no
#: character card — the word only fills the :class:`CompiledPrompt`
#: identity field (the provider protocol's own shape), never a persona
#: lookup.
NARRATOR_PERSONA_ID = PersonaId("world-narrator")

#: The generation-contract word the narrator's prompt carries (the
#: field is a free word on this protocol — the narrator's output is
#: judged by :func:`_parse_beats`, not by the persona validator).
NARRATOR_CONTRACT = "gc-world-narrator-beats"

#: How many recent chronicle narrations the prompt carries (the story's
#: immediate past, oldest first — enough to continue a novel, not enough
#: to become one).
RECENT_CHRONICLE_LIMIT = 8

#: The beat batch's bounds (the rhythm law's own numbers): exactly one
#: or two beats, each spanning zero to two story days.
MIN_BEATS = 1
MAX_BEATS = 2
MIN_DAYS = 0
MAX_DAYS = 2

#: The kind slug's shape: lowercase letters, digits and hyphens, one
#: non-separator character first, at most 32 characters.
_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")

#: The narration language the interface language asks for (W-L's two
#: words — anything else is a prompt-build refusal naming the pair).
_NARRATION_LANGUAGE = {
    "zh": "The narration is written in Chinese (中文).",
    "en": "The narration is written in English.",
}

_NARRATION_LANGUAGE_WORDS = tuple(_NARRATION_LANGUAGE)


def _refused(reason: str) -> Err[None]:
    """One strict-parse refusal — the whole batch dies with the reason
    (``narrator refused: …``), never a partial adoption."""

    return Err(
        DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=f"narrator refused: {reason}",
        )
    )


def build_narrator_prompt(
    package: WorldPackage,
    lore_facts: tuple[tuple[str, str], ...],
    recent_narrations: tuple[str, ...],
    ui_language: str,
) -> str:
    """The narrator's prompt, as one pure string (testable without a
    provider, a store or a world row).

    ``package`` contributes the bible: the setting prose in full, the
    cast on one line. ``lore_facts`` — ``(canonical_key, statement)``
    pairs, the projection's CURRENT half the caller read — is the
    world's established lore, in full; an empty set says so honestly
    (无则空诚实). ``recent_narrations`` is the story's immediate past,
    oldest first, exactly as the caller sliced it. ``ui_language`` picks
    the narration language instruction (``zh`` / ``en``; anything else is
    a refusal naming the two words).

    WR-4 (DEC-OPI-5fc42174-…58, the user's third direction): **no
    letter ever enters this prompt** — the living-world spec is
    two-layer about influence (§4.1 / the 走向 entry): the user's reply
    is the run's *wind-up* (a mechanical starter, never content), the
    user's influence on the *world* rides the direction channel (走向,
    M2), and letters belong to the penpal layer only — they shape the
    character's reply, never the world's narration. The world moves on
    its own here."""

    if ui_language not in _NARRATION_LANGUAGE:
        raise ValueError(
            f"ui_language {ui_language!r} is outside the vocabulary"
            f" {_NARRATION_LANGUAGE_WORDS!r}"
        )
    sections: list[str] = []
    sections.append("You are the narrator of a small fictional world.")
    sections.append("Write what happens there next, as a novel would.")
    sections.append(
        "The world moves on its own — weather, seasons, the town's"
        " rhythms, the cast's lives off-stage. It does not react to any"
        " correspondence: letters belong to the penpal layer, not to"
        " the world's narration."
    )
    sections.append("== The world ==")
    sections.extend(package.setting)
    cast_line = ", ".join(member.name for member in package.cast)
    sections.append(f"Cast: {cast_line}")
    sections.append("== The world's established facts ==")
    if lore_facts:
        sections.extend(f"- {key}: {statement}" for key, statement in lore_facts)
    else:
        sections.append("- (Nothing is settled yet.)")
    sections.append("== The story so far ==")
    if recent_narrations:
        sections.extend(f"- {narration}" for narration in recent_narrations)
    else:
        sections.append("- (The chronicle is empty — this is where the story begins.)")
    sections.append("== Your task ==")
    sections.append(
        "Write the world's next beats — whatever happens next in the"
        " world's own life. Novel prose, small-town voice. Stay"
        " consistent with everything above; never repeat what already"
        f" happened. Write exactly {MIN_BEATS} or {MAX_BEATS} beats."
        " Each beat is one to three sentences of narration and spans"
        " 0, 1 or 2 story days (its ``days``)."
    )
    sections.append(_NARRATION_LANGUAGE[ui_language])
    sections.append(
        "Answer with strict JSON only — no prose outside it:"
        ' {"beats": [{"kind": "<slug>", "narration": "<...>", "days": 0}]}'
        " The ``kind`` is a short slug: lowercase letters, digits and"
        " hyphens only, at most 32 characters."
    )
    return "\n\n".join(sections)


@dataclass(frozen=True)
class GeneratedBeat:
    """One narrator-written story beat — the generation paradigm's own
    event seed.

    ``kind`` is the chronicle kind word the beat will carry (a short
    slug — new kinds are the story's own, never the pool's), ``narration``
    the beat's prose (written as the model wrote it — untrusted-as-is
    downstream: the chronicle stores it verbatim, the presentation faces
    render it as text), ``days`` the story span the beat covers (0-2;
    the orchestrator's calendar rides on it)."""

    kind: str
    narration: str
    days: int


class _BeatProvider(Protocol):
    """The one face the narrator dials — the persona provider's blocking
    call, word for word (the same protocol
    :class:`~elc.persona.provider.PersonaProvider` spells; spelled again
    here only so the narrator's dependency is the two methods it needs,
    never the persona runtime's whole port)."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        ...


class WorldNarrator:
    """The model face that turns one letter into the world's next beats
    (WR-2, DEC-OPI-5fc42174…49) — the production path the fixed-pool
    engine retired out of.

    One instance, one injected provider (the same object the persona
    runtime dials — the host's provider seam, the settings page's hot
    swap included). The narrator is stateless between calls: every
    ``generate`` composes its own prompt, dials once, parses strictly.
    """

    def __init__(self, provider: _BeatProvider | PersonaProvider) -> None:
        self._provider = provider

    def generate(
        self,
        *,
        package: WorldPackage,
        lore_facts: tuple[tuple[str, str], ...],
        recent_narrations: tuple[str, ...],
        ui_language: str,
    ) -> Result[tuple[GeneratedBeat, ...]]:
        """One narration round: the prompt, the one blocking call, the
        strict parse.

        The provider's own fault words pass through as the ``Err``
        message verbatim (``not-configured``, ``timeout``, … — the
        orchestrator's quiet arm reads ``not-configured`` and stays
        silent; every other fault surfaces to the caller's fail-soft
        log). A provider that raises dies at this boundary as a value
        too (the same posture the persona adapter holds). A syntactically
        unusable answer is a whole-batch refusal: ``narrator refused:
        …`` naming what the answer got wrong — never a partial adoption,
        never a guessed beat, never the retired pool.
        """

        prompt = CompiledPrompt(
            persona_id=NARRATOR_PERSONA_ID,
            prompt_text=build_narrator_prompt(
                package,
                lore_facts,
                recent_narrations,
                ui_language,
            ),
            generation_contract=NARRATOR_CONTRACT,
        )
        try:
            output = self._provider.call(prompt)
        except Exception as exc:  # noqa: BLE001 — the transport boundary: values, not raises
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"{type(exc).__name__}: {exc}",
                )
            )
        if output.error is not None:
            # The provider's own fault word, verbatim — the passthrough
            # the orchestrator's quiet arm matches on.
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=str(output.error),
                )
            )
        if output.text is None or not output.text.strip():
            return _refused("the provider answered no text")
        return _parse_beats(output.text)


def _parse_beats(text: str) -> Result[tuple[GeneratedBeat, ...]]:
    """The strict batch parser: the whole answer is one JSON object
    ``{"beats": [...]}``, one or two beat objects, each exactly
    ``kind`` / ``narration`` / ``days`` in shape and range. Any miss
    refuses the whole batch — the discriminator word rides every
    refusal's message."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _refused(f"the answer is not JSON ({exc})")
    if not isinstance(payload, dict):
        return _refused(
            f"the answer is not a JSON object (got {type(payload).__name__})"
        )
    if set(payload) != {"beats"}:
        return _refused(
            f"the answer must carry exactly {{'beats'}} (got"
            f" {', '.join(sorted(map(str, payload))) or 'nothing'})"
        )
    batch = payload["beats"]
    if not isinstance(batch, list):
        return _refused("'beats' is not a JSON array")
    if not MIN_BEATS <= len(batch) <= MAX_BEATS:
        return _refused(
            f"the batch must carry exactly {MIN_BEATS}-{MAX_BEATS}"
            f" beats (got {len(batch)})"
        )
    beats: list[GeneratedBeat] = []
    for index, element in enumerate(batch):
        if not isinstance(element, dict):
            return _refused(
                f"beats[{index}] is not a JSON object"
                f" (got {type(element).__name__})"
            )
        if set(element) != {"kind", "narration", "days"}:
            return _refused(
                f"beats[{index}] must carry exactly 'kind', 'narration'"
                f" and 'days' (got"
                f" {', '.join(sorted(map(str, element))) or 'nothing'})"
            )
        kind = element["kind"]
        narration = element["narration"]
        days = element["days"]
        if not isinstance(kind, str) or not _KIND_RE.fullmatch(kind):
            return _refused(
                f"beats[{index}].kind is not a short slug of lowercase"
                f" letters, digits and hyphens (at most 32 characters):"
                f" {kind!r}"
            )
        if not isinstance(narration, str) or not narration.strip():
            return _refused(f"beats[{index}].narration is blank or not a string")
        if type(days) is not int or not MIN_DAYS <= days <= MAX_DAYS:
            return _refused(
                f"beats[{index}].days is not an int in"
                f" [{MIN_DAYS}, {MAX_DAYS}]: {days!r}"
            )
        beats.append(GeneratedBeat(kind=kind, narration=narration, days=days))
    return Ok(tuple(beats))
