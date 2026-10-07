"""The world narrator (WR-2, DEC-OPI-5fc42174…49; WR-4 correction
…58) — the paradigm flip's generation face: the world's own next one
or two story beats, generated from the world's own life alone.

What this module claims, no more: the prompt is composed from the world
package's bible (the setting prose, the cast — each member with their
optional vignette, the town's narrative residents one line each when
the package carries them — and the whole
CURRENT lore fact set), the recent chronicle (the last eight narrations,
oldest first — an empty chronicle answers an honest ``story begins``
line), the people instruction (when the package carries residents or
more than one cast member: write around their lives and how they touch
— encounters, errands, small kindnesses, frictions, gossip — not only
weather and scenery, one event refracting through several lives) and
the rhythm law (novel prose, small-town voice; consistent
with the history above; nothing already happened repeated; each beat one
to three sentences; exactly one or two beats; each beat spanning zero to
two story days; the narration in the interface language; kinds as short
slugs). **WR-4 (the user's third direction, DEC-…58): no letter ever
enters the prompt** — the living-world spec keeps the layers apart
(§4.1: the reply is the run's mechanical wind-up, never content; the
走向 entry: the user's influence on the world rides the direction
channel, never the letter layer) — the world narrates its own life,
unreactive to correspondence. The provider is called **once** —
blocking, or through its optional streamed face when the caller asks
for the narration increments (wr-7: both faces dial the same protocol
the persona runtime dials; the streamed arm feeds its increments
through :class:`NarrationExtractor`, a preview-only decode — the
durable contract below never reads it) — and the answer (the whole
text, either face) is parsed **strictly**: the whole text must be
exactly one JSON object
``{"beats": [...]}`` carrying one or two beat objects, each with exactly
``kind`` (a slug of lowercase letters, digits and hyphens, at most 32
characters), ``narration`` (non-blank) and ``days`` (an honest int, 0
through 2). wr-10 (DEC-OPI-c73dbff3…64): the object may **also** carry
an optional ``directions`` array beside ``beats`` — the direction
candidates (走向) the director's seat asked for: zero (or no key at all
— the immersive shape), or two to four candidates, each exactly
``label`` (a short phrase) and ``hint`` (one sentence of how the world
might go). The whole-batch law covers the candidates with the beats:
one answer, one fate — a bad array refuses the narration it rode in on.
Anything else — prose around the JSON, a missing or
malformed field, an out-of-range span, an empty or oversized batch, an
unexpected key — refuses the **whole batch** (诚实不造假: no partial
adoption, no guessed beat, and **no fallback to the retired pool** —
the fixed-pool sampling is no longer a production path of any step).

The return shape is the Result the orchestrator consumes: ``Ok`` with
the generated beats and their direction candidates (a two-tuple — the
candidates are empty unless the answer carried them; the type allows an
empty beat tuple — the world's quiet
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
from typing import Callable, Protocol

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
from elc.world.package import CastMember, WorldPackage

__all__ = [
    "DIRECTION_DIRECTED",
    "DIRECTION_IMMERSIVE",
    "DirectionCandidate",
    "GeneratedBeat",
    "MIN_DIRECTIONS",
    "MAX_DIRECTIONS",
    "NARRATION_KEY",
    "NARRATOR_CONTRACT",
    "NARRATOR_PERSONA_ID",
    "NARRATOR_SOURCE",
    "NarrationExtractor",
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

#: The direction candidates' bounds (wr-10, spec §4.4's 2-4 候选): the
#: ``directions`` array carries none (the immersive shape) or two
#: through four — one is not a choice and five is a menu.
MIN_DIRECTIONS = 2
MAX_DIRECTIONS = 4

#: The world-direction mode's two words (wr-10, spec §8's 模式 as this
#: face reads it): ``directed`` asks the narrator for direction
#: candidates beside its beats; ``immersive`` is the world's autonomous
#: shape — the pre-wr-10 prompt, byte for byte.
DIRECTION_DIRECTED = "directed"
DIRECTION_IMMERSIVE = "immersive"
_DIRECTION_MODE_WORDS = (DIRECTION_DIRECTED, DIRECTION_IMMERSIVE)

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

#: The one key the streamed extractor watches (the beat's narration
#: field — matched as a JSON key only, never inside a string value).
NARRATION_KEY = '"narration"'

#: The escape sequences the JSON grammar spells, decoded as the
#: narration increments leave (``\uXXXX`` is the six-character
#: longpole the hold-back buffer is sized for).
_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

#: The extractor's postures: outside any JSON string (where key
#: matching happens), after the narration key matched (awaiting its
#: ``: "``), inside a plain string value (skipped whole), and inside a
#: narration string value (decoded and emitted).
_OUTSIDE = 0
_IN_STRING = 1
_IN_NARRATION = 2
_IN_KEY = 3

# The whitespace the JSON grammar allows around a key's colon.
_WS = " \t\r\n"


def _is_key_prefix(tail: str) -> bool:
    """Whether ``tail`` could still grow into :data:`NARRATION_KEY` —
    a strict prefix match that lets an increment boundary fall inside
    the key itself without a wrong decision."""

    return NARRATION_KEY.startswith(tail)


class NarrationExtractor:
    """The streamed narration extractor (wr-7): the pure-function state
    machine that turns the provider's raw JSON increments into decoded
    ``(beat_index, text)`` narration pieces — the preview the page
    renders while the answer is still arriving.

    What it claims, no more: key matching happens **outside** string
    values only (the word ``"narration":`` inside a narration's own
    prose is content, never a key), and the key counts only when a
    colon and an opening quote follow (its whitespace allowed); inside
    a narration value every escape is decoded as it completes and the
    decoded characters leave immediately; an escape sequence cut by an
    increment boundary (``\\n`` split in half, ``\\uXXXX`` split after
    ``\\u4f``) is held back — at most six characters — until the next
    increment completes it. The beat index is the ordinal of the
    narration key itself (the strict contract gives every beat exactly
    one), so the extraction never depends on the JSON key order (``days``
    may precede ``narration`` freely). Everything outside narration
    values — kind values, ``days`` numbers, the structure — emits
    nothing.

    Deliberately absent: any judgment about the whole. A stream that
    ends mid-something leaves its tail unemitted (nothing is invented,
    at stream end there is no next increment to complete it) and a
    malformed answer is the strict parser's refusal, not this machine's
    — the preview may have shown text the durable half then refuses,
    and the caller owns that honesty (:meth:`WorldNarrator.generate`'s
    contract keeps the shown increments real; the web face answers them
    with the failure frame).
    """

    def __init__(self) -> None:
        self._pending = ""
        self._state = _OUTSIDE
        self._index = 0
        self._out: list[tuple[int, str]] = []

    def feed(self, chunk: str) -> tuple[tuple[int, str], ...]:
        """Consume one raw increment, answer the decoded narration
        pieces it completed, in arrival order (a piece per contiguous
        run the chunk could decode; callers join freely)."""

        self._pending += chunk
        self._drain()
        pieces = tuple(self._out)
        self._out = []
        return pieces

    # -- the drain loop ---------------------------------------------------

    def _drain(self) -> None:
        text = self._pending
        pos = 0
        size = len(text)
        while pos < size:
            if self._state == _OUTSIDE:
                pos = self._drain_outside(text, pos)
            elif self._state == _IN_STRING:
                pos = self._drain_string(text, pos)
            elif self._state == _IN_KEY:
                pos = self._drain_key(text, pos)
            else:
                pos = self._drain_narration(text, pos)
            if pos < 0:  # held back — the tail waits for more increments
                pos = -pos - 1
                break
        self._pending = text[pos:]

    def _drain_outside(self, text: str, pos: int) -> int:
        """Outside any string: structure passes, and a ``"`` opens
        either the narration key (consumed here, its confirmation a
        state of its own) or a plain string value (skipped whole).
        Answers a negative position to hold."""

        if text[pos] != '"':
            return pos + 1
        tail = text[pos:]
        if tail == NARRATION_KEY[: len(tail)] and len(tail) < len(
            NARRATION_KEY
        ):
            # Still a prefix of the key — undecidable until more arrives.
            return -pos - 1
        if not tail.startswith(NARRATION_KEY):
            return self._open_plain_string(text, pos)
        self._state = _IN_KEY
        return pos + len(NARRATION_KEY)

    def _drain_key(self, text: str, pos: int) -> int:
        """Right after the narration key: whitespace, ``:``, whitespace,
        then the opening quote commits the narration value. Anything
        else says this ``"narration"`` was not the beat's key after all
        (a value string or a stranger key) — back outside; the strict
        parse owns the verdict for such an answer. Holds keep from the
        scan point (absolute position — the sub-pattern is tiny and
        rescanning it is idempotent)."""

        size = len(text)
        scan = pos
        while scan < size and text[scan] in _WS:
            scan += 1
        if scan >= size:
            return -(pos) - 1
        if text[scan] != ":":
            self._state = _OUTSIDE
            return scan
        scan += 1
        while scan < size and text[scan] in _WS:
            scan += 1
        if scan >= size:
            return -(pos) - 1
        if text[scan] != '"':
            self._state = _OUTSIDE
            return scan
        self._state = _IN_NARRATION
        return scan + 1

    def _open_plain_string(self, text: str, pos: int) -> int:
        """A ``"`` that is not the narration key: a value string (a kind
        word, prose anywhere else) — the opening quote is consumed here
        so every later re-entry scans content from ``pos`` (an
        increment boundary may fall anywhere)."""

        self._state = _IN_STRING
        return pos + 1

    def _drain_string(self, text: str, pos: int) -> int:
        """Inside a plain string value: consume to the closing quote,
        escapes skipped whole (a lone backslash at the tail holds).
        ``pos`` sits on the first **content** character — the opening
        quote left with :meth:`_open_plain_string`."""

        size = len(text)
        scan = pos
        while scan < size:
            char = text[scan]
            if char == "\\":
                if scan + 1 >= size:
                    return -(scan) - 1
                scan += 2
                continue
            if char == '"':
                self._state = _OUTSIDE
                return scan + 1
            scan += 1
        return size

    def _drain_narration(self, text: str, pos: int) -> int:
        """Inside the narration value: decode escapes, emit decoded
        characters, close on the bare quote (which also advances the
        beat index). Answers a negative position to hold."""

        size = len(text)
        scan = pos
        start = pos
        while scan < size:
            char = text[scan]
            if char == '"':
                # The narration's closing quote: flush the plain run
                # first, then close and advance to the next beat.
                if scan > start:
                    self._emit(text[start:scan])
                self._state = _OUTSIDE
                self._index += 1
                return scan + 1
            if char == "\\":
                if scan + 1 >= size:
                    break
                escape = text[scan + 1]
                if escape == "u":
                    if scan + 6 > size:
                        break
                    decoded = chr(int(text[scan + 2 : scan + 6], 16))
                    step = 6
                elif escape in _SIMPLE_ESCAPES:
                    decoded = _SIMPLE_ESCAPES[escape]
                    step = 2
                else:
                    # Not a JSON escape at all — the strict parser will
                    # refuse this answer; the preview passes the two
                    # characters verbatim rather than guessing a repair.
                    decoded = text[scan : scan + 2]
                    step = 2
                if scan > start:
                    self._emit(text[start:scan])
                self._emit(decoded)
                scan += step
                start = scan
                continue
            scan += 1
        if scan > start:
            self._emit(text[start:scan])
        if scan < size:
            # Held back inside an unfinished escape: keep from the
            # backslash (negative position encodes the hold).
            return -(scan) - 1
        return scan

    def _emit(self, piece: str) -> None:
        if piece:
            self._out.append((self._index, piece))


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
    direction_mode: str = DIRECTION_IMMERSIVE,
    pending_direction: tuple[str, str] | None = None,
) -> str:
    """The narrator's prompt, as one pure string (testable without a
    provider, a store or a world row).

    ``package`` contributes the bible: the setting prose in full, the
    cast — one member with their optional vignette after the name (a
    bare name when the member carries none, the pre-v4 shape), the
    town's narrative residents one line each under their own section
    when the package carries any (``Resident`` rows are prompt material
    only; the section's absence adds nothing). ``lore_facts`` —
    ``(canonical_key, statement)`` pairs, the projection's CURRENT half
    the caller read — is the world's established lore, in full; an
    empty set says so honestly (无则空诚实). ``recent_narrations`` is
    the story's immediate past, oldest first, exactly as the caller
    sliced it. ``ui_language`` picks the narration language instruction
    (``zh`` / ``en``; anything else is a refusal naming the two words).

    When the package carries residents or more than one cast member the
    prompt adds the people instruction: write around these people's
    lives and how they touch — encounters, errands, small kindnesses,
    frictions, gossip — not only weather and scenery, the same event
    refracting through several lives.

    wr-10 (DEC-OPI-c73dbff3…64): ``direction_mode`` is one of the two
    words (:data:`DIRECTION_DIRECTED` / :data:`DIRECTION_IMMERSIVE`;
    anything else is a ``ValueError`` naming them). ``directed`` adds
    the candidates requirement — 2 to 4 direction candidates under the
    ``directions`` key, each ``label`` short phrase + ``hint`` one
    sentence of how the world might go — and widens the JSON shape
    line; ``immersive`` adds nothing: the prompt is byte for byte the
    pre-wr-10 text (the zero-change default). ``pending_direction`` —
    the user's already-chosen ``(label, hint)`` awaiting consumption —
    adds its own section when present: **the director's input, the
    direction channel's own door** (走向, spec §4.6), never a letter's.

    WR-4 (DEC-OPI-5fc42174-…58, the user's third direction): **no
    letter ever enters this prompt** — the living-world spec is
    two-layer about influence (§4.1 / the 走向 entry): the user's reply
    is the run's *wind-up* (a mechanical starter, never content), the
    user's influence on the *world* rides the direction channel (走向,
    wr-10 opens it), and letters belong to the penpal layer only —
    they shape the character's reply, never the world's narration. The
    world moves on its own here."""

    if ui_language not in _NARRATION_LANGUAGE:
        raise ValueError(
            f"ui_language {ui_language!r} is outside the vocabulary"
            f" {_NARRATION_LANGUAGE_WORDS!r}"
        )
    if direction_mode not in _DIRECTION_MODE_WORDS:
        raise ValueError(
            f"direction_mode {direction_mode!r} is outside the"
            f" vocabulary {_DIRECTION_MODE_WORDS!r}"
        )
    if pending_direction is not None:
        label, hint = pending_direction
        if not (
            isinstance(label, str)
            and label.strip()
            and isinstance(hint, str)
            and hint.strip()
        ):
            raise ValueError(
                "pending_direction must carry a non-blank label and"
                " hint"
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

    def _cast_row(member: CastMember) -> str:
        if member.vignette:
            return f"{member.name} — {member.vignette}"
        return member.name

    sections.append(
        "Cast: " + ", ".join(_cast_row(member) for member in package.cast)
    )
    if package.residents:
        sections.append("== The town's residents ==")
        sections.extend(
            f"{resident.name}, {resident.role} — {resident.vignette}"
            for resident in package.residents
        )
    if package.residents or len(package.cast) > 1:
        sections.append(
            "The world's life is its people: write around their lives"
            " and how they touch each other — encounters, errands,"
            " small kindnesses, frictions, gossip — not only the"
            " weather and the scenery. The same event may refract"
            " through several lives."
        )
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
    if direction_mode == DIRECTION_DIRECTED:
        sections.append(
            "Direction candidates: in the same answer, also write"
            f" {MIN_DIRECTIONS} to {MAX_DIRECTIONS} directions — each"
            ' is {"label": <a short phrase>, "hint": <one sentence of'
            " how the world might go>}. A direction is a next step the"
            " world could take, one the user may pick for it; list"
            ' them under the "directions" key beside the beats.'
        )
    if pending_direction is not None:
        chosen_label, chosen_hint = pending_direction
        sections.append("== The user's chosen direction ==")
        sections.append(
            "The user has chosen where the world goes next:"
            f" {chosen_label} — {chosen_hint}. The world moves in"
            " this direction."
        )
    sections.append(_NARRATION_LANGUAGE[ui_language])
    if direction_mode == DIRECTION_DIRECTED:
        sections.append(
            "Answer with strict JSON only — no prose outside it:"
            ' {"beats": [{"kind": "<slug>", "narration": "<...>",'
            ' "days": 0}], "directions": [{"label": "<short phrase>",'
            ' "hint": "<one sentence>"}]}'
            " The ``kind`` is a short slug: lowercase letters, digits"
            " and hyphens only, at most 32 characters."
        )
    else:
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


@dataclass(frozen=True)
class DirectionCandidate:
    """One direction candidate the narrator offered beside its beats
    (wr-10, DEC-OPI-c73dbff3…64 — the 走向 channel's first production
    face): ``label`` is the short phrase the page renders as the
    user's choice, ``hint`` the one sentence of how the world might go
    under it. Prompt material and payload cargo only — a candidate is
    never a durable fact until a later cut says the chosen direction
    shaped a beat."""

    label: str
    hint: str


class _BeatProvider(Protocol):
    """The one face the narrator dials — the persona provider's blocking
    call, word for word (the same protocol
    :class:`~elc.persona.provider.PersonaProvider` spells; spelled again
    here only so the narrator's dependency is the two methods it needs,
    never the persona runtime's whole port)."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        ...


class _StreamingBeatProvider(Protocol):
    """The optional streamed face the narrator dials when the caller
    asks for the narration increments (wr-7) — the persona provider's
    ``call_streaming``, word for word: raw increments out through
    ``emit`` in arrival order, the same value contract on the return
    (the whole text, or ``None`` plus the fault word)."""

    def call_streaming(
        self, prompt: CompiledPrompt, emit: Callable[[str], None]
    ) -> ProviderOutput:
        ...


class WorldNarrator:
    """The model face that narrates the world's own next beats (WR-2,
    DEC-OPI-5fc42174…49; WR-4 correction …58 — no letter ever enters)
    — the production path the fixed-pool engine retired out of.

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
        on_increment: Callable[[int, str], None] | None = None,
        direction_mode: str = DIRECTION_IMMERSIVE,
        pending_direction: tuple[str, str] | None = None,
    ) -> Result[
        tuple[tuple[GeneratedBeat, ...], tuple[DirectionCandidate, ...]]
    ]:
        """One narration round: the prompt, the one provider call, the
        strict parse.

        Two call shapes, one contract (wr-7): with ``on_increment`` and
        a provider that carries the optional streamed face the dial
        goes through ``call_streaming`` — every raw increment feeds
        :class:`NarrationExtractor`, and each decoded
        ``(beat_index, text)`` piece rides ``on_increment`` as it
        completes (the page's preview — the shown increments are real
        facts the caller owns). Without the callback, or without the
        face, the dial is the blocking ``call`` of old and nothing
        leaves early. Either way the **return value is the same**:
        the whole text is parsed by ``_parse_beats`` exactly as before
        — the preview never influences the verdict, and an answer the
        strict parse refuses is refused whole even though its
        increments may already have been shown.

        wr-10 (DEC-OPI-c73dbff3…64): ``direction_mode`` /
        ``pending_direction`` ride to the prompt builder (the
        candidates requirement and the chosen-direction section; the
        defaults keep the immersive, direction-free shape). The return
        is the parsed **two-tuple** — the beats and the answer's own
        direction candidates (empty unless the answer carried them).

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
                direction_mode,
                pending_direction,
            ),
            generation_contract=NARRATOR_CONTRACT,
        )
        streaming = getattr(self._provider, "call_streaming", None)
        try:
            if on_increment is not None and streaming is not None:
                extractor = NarrationExtractor()

                def emit(chunk: str) -> None:
                    for index, piece in extractor.feed(chunk):
                        on_increment(index, piece)

                output = streaming(prompt, emit)
            else:
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


def _parse_beats(
    text: str,
) -> Result[tuple[tuple[GeneratedBeat, ...], tuple[DirectionCandidate, ...]]]:
    """The strict batch parser: the whole answer is one JSON object
    ``{"beats": [...]}`` — or ``{"beats": [...], "directions": [...]}`
    (wr-10: the candidates ride the same answer; zero candidates, or an
    absent key, is the immersive shape) — one or two beat objects, each
    exactly ``kind`` / ``narration`` / ``days`` in shape and range, and
    each candidate exactly ``label`` / ``hint``, both non-blank, the
    array none or :data:`MIN_DIRECTIONS` through :data:`MAX_DIRECTIONS`.
    Any miss refuses the whole batch — the discriminator word rides
    every refusal's message."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _refused(f"the answer is not JSON ({exc})")
    if not isinstance(payload, dict):
        return _refused(
            f"the answer is not a JSON object (got {type(payload).__name__})"
        )
    if "beats" not in payload or not set(payload) <= {"beats", "directions"}:
        return _refused(
            f"the answer must carry exactly {{'beats'}} or"
            f" {{'beats', 'directions'}} (got"
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
    raw_directions = payload.get("directions")
    if raw_directions is None:
        return Ok((tuple(beats), ()))
    if not isinstance(raw_directions, list):
        return _refused("'directions' is not a JSON array")
    count = len(raw_directions)
    if count != 0 and not MIN_DIRECTIONS <= count <= MAX_DIRECTIONS:
        return _refused(
            f"'directions' must carry none or {MIN_DIRECTIONS}-"
            f"{MAX_DIRECTIONS} candidates (got {count})"
        )
    directions: list[DirectionCandidate] = []
    for index, element in enumerate(raw_directions):
        if not isinstance(element, dict):
            return _refused(
                f"directions[{index}] is not a JSON object"
                f" (got {type(element).__name__})"
            )
        if set(element) != {"label", "hint"}:
            return _refused(
                f"directions[{index}] must carry exactly 'label' and"
                f" 'hint' (got"
                f" {', '.join(sorted(map(str, element))) or 'nothing'})"
            )
        label = element["label"]
        hint = element["hint"]
        if not isinstance(label, str) or not label.strip():
            return _refused(
                f"directions[{index}].label is blank or not a string"
            )
        if not isinstance(hint, str) or not hint.strip():
            return _refused(f"directions[{index}].hint is blank or not a string")
        directions.append(DirectionCandidate(label=label, hint=hint))
    return Ok((tuple(beats), tuple(directions)))
