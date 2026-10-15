"""The real LLM providers behind the Narrative V3 provider face
(V3-8c, TASK-OPI-cddb517c-…7 / the opening ruling
``DEC-OPI-cddb517c-…5``) — the four production faces
:mod:`elc.world.providers` froze its Protocols for, implemented over
one narrow transport seam.

**The seam** (:class:`TextCompletion`): ``complete(prompt) ->
CompletionOutcome`` — one method, one value shape, no network, no
secret, no clock. The BYOK egress (the persona package's
``OpenAICompatibleProvider`` + ``SecretSource``) is adapted onto this
seam by the **assembly face** (the V3-8e reading-face wiring); this
module deliberately does **not** import ``elc.persona`` in any form —
``elc.world`` keeps no cross-package import edge (the P4-3 cold-start
discipline), and the seam is where a transport plugs in. The seam's
streaming face (``complete_streaming(prompt, on_chunk)``) was the
registered extension point for a later cut — and that cut arrived:
**DS-1** (the dual-seat technical definition §12, F15) re-opened it
explicitly for the narration arm, as the separate
:class:`StreamingTextCompletion` protocol below — the bypass channel
that leaves every existing constructor and the four original arms'
signatures byte for byte untouched.

**The four implementations** satisfy the frozen Protocols structurally
(no inheritance — the Protocol *is* the contract):

- :class:`LlmWriterProvider` → :meth:`~LlmWriterProvider.write_segment`
  (:class:`~elc.world.providers.PovContext` → the segment's prose);
- :class:`LlmPlannerProvider` →
  :meth:`~LlmPlannerProvider.plan_scene` /
  :meth:`~LlmPlannerProvider.replan_element` (:class:`ScenePlanContext`
  → the element payload);
- :class:`LlmDirectorProvider` →
  :meth:`~LlmDirectorProvider.draft_blueprint` /
  :meth:`~LlmDirectorProvider.replan_blueprint`
  (:class:`DirectorPlanContext` → the Blueprint payload);
- :class:`LlmResolverProvider` →
  :meth:`~LlmResolverProvider.adjudicate`
  (:class:`ResolverContext` → the
  :class:`~elc.world.action.Adjudication` shape verbatim).

**The prompt assembly is the cut's value**: every prompt is a pure
function of the context the Protocol hands over (input context → prompt
string). The POV-limited faces read exactly the faces ``PovContext`` /
``ScenePlanContext`` carry — the V3-5R hard door's physical form is the
compiled context itself, and this module cannot leak what the context
does not carry (the writer's prompt lists the adopted dossier's
``must_hide`` item by item as hard prohibitions; its knowledge block is
the POV's own cognition / memory only). The two world-authoritative
faces (:class:`ResolverContext` / :class:`DirectorPlanContext`) are
deliberately not POV-limited: the resolver is fed the world's rules,
settled facts, the player's profile and the player character's own
knowledge arms (**F4, V3-8c**: ``player_cognition`` / ``player_memory``
are the authority for "what the user character knows"; the scene POV's
cognition / memory ride as the presentation face), and the director is
fed the full ``DirectorContext``. The soft-expectation wording law is
stated in the Director prompt: ``closing_pressure`` and the other soft
fields say where a chapter presses — never a postcondition.

**The parsing law** (deliberately strict beyond a minimal deterministic
cleaning): the seam's ``text`` is stripped of leading / trailing
whitespace and of **one** surrounding markdown fence — a first line
that is exactly ```` ``` ```` or ```` ```json ```` (optionally other
alphanumerics) with a bare ```` ``` ```` closing the remainder; nothing
else is reinterpreted. The cleaned text must parse as a JSON **object**
of the expected key set with the expected types (missing key →
``missing-field:<name>``, wrong type / non-object / bad JSON /
out-of-vocabulary ``replan_scope`` → ``bad-shape`` / ``bad-payload``);
keys beyond the canonical set are **ignored** (tolerance, never a
second schema). **One tolerance arm rides the text fields (V3-8f,
§10.4)**: a text field answered as a JSON **array of strings** is
joined deterministically into the one string the canonical type
promises (``"\\n".join`` — the same newline separator the ``must_hide``
fragment law splits on; an empty array is the honest empty string).
Real models were observed to answer a plural-meaning prose field as an
array even when the schema names a string, and the two-sided fix is the
prompt's explicit per-field type contract **plus** this one deterministic
join — canonical types and stored shapes are untouched (the library
faces keep every deeper judgment; nothing else about the strictness
moves: a non-string item, a number or an object in a text field is
still ``bad-shape``). **A second contract rides the identity fields**
(the V3-8f smoke's fifth face, same family as the type contract — and
**strengthened on that smoke's second run**, the planner layer of the
same face): the prompts state that a participant identity is the
**bare id token** the prompt lists — the part before any parenthesised
name or role — never the rendered composite (a real Resolver copied
the prompt's own ``cousin (Renn)`` form and the namespace check
refused it, the V3-3R freeze doing its job); that identity strings are
taken **only from the ids the prompt itself lists**, written exactly
as listed; that an id is never replaced by a character's display name
and no identity outside that vocabulary is ever added; and that names
appearing only in prose (cognition / memory / a ruling's text) are not
identities — a character first met on the page exists in the prose
alone, never in ``participants`` (the smoke's planner replan answered
``renn`` — the display name of the id ``cousin`` — beside the
prose-only newcomer ``carter``, and the continuation segment was
refused). The refusal stays the strict backstop, and the contract is
stated where the model reads it. The library faces
downstream (the Director's
schema, the ``_checked_fields`` family, ``commit_action``) keep every
deeper judgment — the parser blesses a payload's *shape*, never its
content.

**The prose-language face (V3-8g, the paradigm shift §10.4 item 5).**
Every prompt carries one language line over the two-word vocabulary
(:data:`PROSE_LANGUAGE_WORDS`: ``en`` — the default,
:data:`PROSE_LANGUAGE_DEFAULT` — and ``zh``). At ``en`` the writer's
line is the existing sentence verbatim and the three JSON arms state
the same English default explicitly; at ``zh`` every line names Chinese
— the JSON answers' natural-language fields and the segment's prose
follow it, while JSON keys, identity strings and the three-word enum
are untouched (the contract's own boundary). The providers default to
``en``, so every caller that passes no word keeps today's prompts byte
for byte; the reading face reads the live ``v3_prose_language``
setting per drive and hands the word to these constructors. A language
switch never rewrites canon: passages already committed stay as they
are, and only segments written after the switch carry the new
language.

**The continuity law (V3-8g, the paradigm shift §10.4 item 6).** The
writer's event lists (cognition / memory) are **what has already
happened and has already been narrated** — the field failure this cut
fixes was a real model copying the previous segment's narration
straight back out as the next segment (byte-near-identical
continuations). The writer prompt therefore carries
:data:`_CONTINUITY_SENTENCE`: the segment must advance the story (new
beats, actions and perceptions), never repeat, restate or transcribe a
narration already on those lists, and a continuation resuming a
committed ruling does the same — the ruling is already narrated, so
the segment carries the story past it. The line's voice is the
instruction frame's (English at every language word: it governs the
prose, not the prose itself).

**The gate-production and player-anchoring faces (V3-8i, the paradigm
shift §10.6).** The Director prompt's scene schema now carries the
plan-level seat of §2.5's stop law (:data:`_GATE_BEATS_SENTENCE`):
every scene plans the reader's own will — a ``required_beats`` list of
beat objects (segment beats and gate beats; a gate beat names its §2.5
stop ``reason`` and 2–4 natural behaviour ``options``) with **at least
one gate beat per scene**, plus a ``user_present`` boolean. The parser
carries both verbatim when the answer declares them (shape-checked;
absent keys parse exactly as before) and the library judge
(``elc.world.director.blueprint_gate_refusal``) keeps the deeper
refusal. The three arms that render a participant list anchor the
no-puppet rule to the concrete name (:data:`_WRITER_PLAYER_SENTENCE` /
:data:`_PLANNER_PLAYER_SENTENCE` / :data:`_RESOLVER_PLAYER_SENTENCE`):
the player character's id rides the compiled contexts
(``player_character_id`` — the pipeline passes it from the durable
cast; a context without it renders today's prompt byte for byte), and
the anchor lines are additive — the existing participants lines stay
byte for byte (the prompt pins ride them).

**Failure semantics** — the V3 Protocol face (``providers.py``, sealed)
has no Result channel, so a real provider's runtime failure escapes as
:class:`LlmProviderError` (a module-owned ``Exception`` carrying a
short body-free ``reason``): the module's own codes (``no-output`` /
``bad-payload`` / ``missing-field:<name>`` / ``bad-shape``, the
persona ``ProviderOutput`` reason-code style) **plus the seam's short
codes relayed** (V3-8f, §10.4: ``timeout`` / ``http-<status>`` /
``missing-secret`` / ``not-configured`` / ``no-egress`` / ``key-echo``
/ ``cleartext-http`` / ``bad-json`` / ``response-too-large`` — a
flattened ``transport-error`` would misreport a timeout as a
credentials problem at the user face). The relay is code-shaped only
(:func:`_seam_code`): free text from a seam that breaks its own
contract is still flattened, so no message ever carries the prompt or a
prompt fragment. This is the runtime-error posture, the fake's honest
``ValueError`` being the programmer-error one; the caller (the drive /
the reading face) owns converting the exception into its Err / HTTP
answer, and translates the code into an actionable sentence.

Discipline: no ``sqlite3``, no transaction, no SQL, no clock — the
module never touches the database (every call happens outside any
transaction by construction, and the seam's own contract keeps the
network call there too); runtime imports from ``elc`` are the two
value shapes its output requires (``elc.world.action`` /
``elc.world.types``); value semantics throughout, ``__all__`` names
the exported faces.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from elc.world.action import Adjudication, ReplanScope
from elc.world.memory import V3MemoryView
from elc.world.types import StateEffect

if TYPE_CHECKING:  # the annotation-only edges (same-package contexts)
    from elc.world.bible import BibleRevision
    from elc.world.cast import (
        ActorProfileRecord,
        PlayerCharacterRecord,
    )
    from elc.world.cognition import V3CognitionView
    from elc.world.director import (
        DirectorCastMember,
        DirectorContext,
        DirectorPlayerCharacter,
    )
    from elc.world.providers import (
        DirectorPlanContext,
        PovContext,
        ResolverContext,
        ScenePlanContext,
    )
    from elc.world.settlement import ChapterSettlementRecord
    from elc.world.store import WorldStorylineRecord
    from elc.world.types import WorldStateFact

__all__ = [
    "PROSE_LANGUAGE_DEFAULT",
    "PROSE_LANGUAGE_WORDS",
    "BatchAdjudicationContext",
    "CharacterContext",
    "CharacterProposal",
    "CompletionOutcome",
    "DispatchContext",
    "DispatchDecision",
    "LlmBatchAdjudicatorProvider",
    "LlmCharacterProvider",
    "LlmDispatcherProvider",
    "LlmDirectorProvider",
    "LlmNarratorProvider",
    "LlmPlannerProvider",
    "LlmProviderError",
    "LlmResolverProvider",
    "LlmSituationPlannerProvider",
    "LlmWriterProvider",
    "NarrationContext",
    "NarrationResult",
    "SituationPlan",
    "SituationPlanContext",
    "StreamingTextCompletion",
    "TextCompletion",
    "WorldAdjudicationContext",
]


@dataclass(frozen=True)
class CompletionOutcome:
    """One completion call's outcome — the seam's value semantics.

    ``text`` is the answer (``None`` when the transport produced none);
    ``error`` is a short body-free transport-side reason (``None`` on a
    surfaced answer). Both set, or neither, is a corrupted call: the
    failure arms read ``error`` first, and a missing ``text`` answers
    the honest ``no-output`` — never a fabricated answer. The message
    side stays body-free by construction: an error string must never
    carry the prompt or a prompt fragment (the persona reason-code
    posture, ``ProviderOutput``'s sibling).
    """

    text: str | None
    error: str | None = None


@runtime_checkable
class TextCompletion(Protocol):
    """The one-method transport seam: prompt in, :class:`CompletionOutcome`
    out. Implementations must be side-effect-free with respect to
    app.db and call the network outside any transaction (RA §24.1 /
    R-INV-004); the streaming face (``complete_streaming(prompt,
    on_chunk)``) is the registered extension point this cut does not
    implement — the reading face re-opens it explicitly if its UX needs
    it."""

    def complete(self, prompt: str) -> CompletionOutcome: ...


class LlmProviderError(Exception):
    """A real provider's runtime failure, body-free and code-shaped.

    ``reason`` is one short code, from either of two families: the
    **seam codes relayed** from the transport (V3-8f, §10.4 — the
    persona adapter's own vocabulary: ``timeout`` / ``http-<status>`` /
    ``missing-secret`` / ``not-configured`` / ``no-egress`` /
    ``key-echo`` / ``cleartext-http`` / ``bad-json`` / ``bad-shape`` /
    ``response-too-large``) or the **module's own** codes (``no-output``
    for an empty answer, ``bad-payload`` for a non-object JSON answer,
    ``bad-shape`` for a wrong type or an out-of-vocabulary word,
    ``missing-field:<name>`` for a required key absent — nested
    coordinates read ``scenes[0].place``, the Director schema's own
    language). Flattening every seam failure into ``transport-error``
    was the V3-8f bug the relay fixes: a timeout must reach the user
    face as a timeout. The message is the code alone: the prompt, and
    anything a transport might have echoed, never rides through — a
    seam handing free text instead of a code is flattened to
    ``transport-error`` (see :func:`_seam_code`).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------------------
# the parsing law (see the module docstring)
# ---------------------------------------------------------------------------

#: A first fence line: a bare code fence or one carrying a short
#: language word (``json``) — anything else is not a fence this cut
#: strips. The closing fence is the bare ```` ``` ```` at the end.
_FENCE_LINE = re.compile(r"^```[A-Za-z0-9_-]*$")

#: The element payload's four value-carrying keys beside the six text
#: ones (the Director schema's canonical ten minus ``purpose`` — the
#: dossier shape :func:`elc.world.pipeline._element_mapping_of` renders;
#: the Blueprint scene element carries ``purpose`` too).
_PLAN_ELEMENT_TEXT_KEYS = (
    "place",
    "entry_goals",
    "exit_condition",
    "elasticity",
    "revealable",
    "must_hide",
)

#: The ruling's three-word plan verdict, as the parser's vocabulary.
_REPLAN_SCOPE_WORDS: dict[str, ReplanScope] = {
    "NONE": ReplanScope.NONE,
    "SCENE": ReplanScope.SCENE,
    "CHAPTER": ReplanScope.CHAPTER,
}


#: The shape a relayed seam code must have (V3-8f): one short lowercase
#: word — dashes and digits allowed, so ``timeout`` / ``http-401`` /
#: ``missing-secret`` / ``no-egress`` / ``response-too-large`` all pass.
#: The match is whole (``fullmatch``): a trailing newline is not part of
#: any code, so ``"timeout\n"`` flattens like every other free-text
#: shape (the review's F2 — an anchored ``$`` alone admitted one). A
#: seam that hands free text instead (a bug, or a hostile double) is
#: flattened to ``transport-error``: the prompt must never ride into a
#: reason through the failure arm.
_SEAM_CODE = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _seam_code(error: str) -> str:
    """The seam's ``error`` as the code to relay — or ``transport-error``.

    The seam's own contract promises a short body-free reason (the
    persona adapter's fixed vocabulary); this function relays exactly
    that shape and nothing wider. The guard is the existing posture kept
    intact: an error string that could echo a prompt (spaces, newlines,
    case, length) never becomes a ``LlmProviderError`` reason.
    """

    return error if _SEAM_CODE.fullmatch(error) else "transport-error"


def _complete_text(completion: TextCompletion, prompt: str) -> str:
    """One seam call, the failure arms first: a seam ``error`` is relayed
    as the code it is (V3-8f: ``timeout`` / ``http-<status>`` /
    ``missing-secret`` / … reach the user face instead of being flattened
    to ``transport-error``); a missing ``text`` is ``no-output``."""

    outcome = completion.complete(prompt)
    if outcome.error is not None:
        raise LlmProviderError(_seam_code(outcome.error))
    if outcome.text is None:
        raise LlmProviderError("no-output")
    return outcome.text


def _clean(text: str) -> str:
    """The deterministic minimal cleaning (see the module docstring):
    strip the surrounding whitespace, then remove one fence wrapper —
    a first line that is exactly a code fence (optionally tagged) and,
    when present, the bare closing fence on the last line (a closing
    fence that never came still strips the opening one). Nothing else
    is reinterpreted; a fence that does not fit the rule rides on to
    the parser and fails there."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1 and _FENCE_LINE.match(
            cleaned[:first_newline].strip()
        ):
            body = cleaned[first_newline + 1 :].rstrip()
            if body.endswith("```"):
                body = body[:-3]
            cleaned = body.strip()
    return cleaned


def _payload_object(text: str) -> Mapping[str, Any]:
    """The cleaned text as a JSON object, or the honest refusal: an
    empty answer is ``no-output``, unparsable text ``bad-payload`` and
    a non-object payload ``bad-payload``."""

    cleaned = _clean(text)
    if not cleaned:
        raise LlmProviderError("no-output")
    try:
        payload = json.loads(cleaned)
    except ValueError:
        raise LlmProviderError("bad-payload") from None
    if not isinstance(payload, dict):
        raise LlmProviderError("bad-payload")
    return payload


def _field(
    payload: Mapping[str, Any], name: str, *, coordinate: str = ""
) -> Any:
    """One required key, or ``missing-field:<name>`` — a nested key
    reads the schema's own coordinate language (``scenes[0].place``)."""

    if name not in payload:
        suffix = f"{coordinate}.{name}" if coordinate else name
        raise LlmProviderError(f"missing-field:{suffix}")
    return payload[name]


def _text(
    payload: Mapping[str, Any], name: str, *, coordinate: str = ""
) -> str:
    """One text field, with the V3-8f tolerance arm: a JSON **array of
    strings** is joined deterministically into the one string the
    canonical type promises (``"\\n".join`` — the newline is the same
    separator the ``must_hide`` fragment law splits on, so a model's
    several-items-as-array answer lands in the shape the design means).
    An empty array is the honest empty string (downstream faces keep
    every deeper judgment). Anything else — a non-string item, a number,
    an object — stays the strict ``bad-shape``: the tolerance is the one
    direction real models were observed to overshoot in, never a second
    schema."""

    value = _field(payload, name, coordinate=coordinate)
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(
        isinstance(item, str) for item in value
    ):
        return "\n".join(value)
    raise LlmProviderError("bad-shape")


def _tick(
    payload: Mapping[str, Any], name: str, *, coordinate: str = ""
) -> int:
    value = _field(payload, name, coordinate=coordinate)
    if not isinstance(value, int) or isinstance(value, bool):
        raise LlmProviderError("bad-shape")
    return value


def _words(
    payload: Mapping[str, Any], name: str, *, coordinate: str = ""
) -> tuple[str, ...]:
    value = _field(payload, name, coordinate=coordinate)
    if isinstance(value, (str, bytes)) or not isinstance(value, list):
        raise LlmProviderError("bad-shape")
    words: list[str] = []
    for word in value:
        if not isinstance(word, str):
            raise LlmProviderError("bad-shape")
        words.append(word)
    return tuple(words)


def _parse_scene_element(
    payload: Mapping[str, Any], *, coordinate: str = ""
) -> dict[str, Any]:
    """One scene element in the dossier's own shape — the nine keys
    :func:`elc.world.pipeline._element_mapping_of` renders, validated
    key by key (the Planner arm's payload; the Blueprint's scene table
    carries ``purpose`` beside them).

    The V3-8i gate face rides beside them: a ``required_beats`` list of
    beat objects and a ``user_present`` boolean are carried **when the
    answer declares them** (shape-checked — a non-list or a non-object
    beat entry is ``bad-shape``; the deeper judgment stays the library
    judge's) and ride verbatim into the plan payload; an answer without
    them parses exactly as before (the deterministic fakes' ten-key
    payloads keep parsing — the production prompt demands the keys, the
    plan-level judge refuses a plan that lacks them)."""

    element: dict[str, Any] = {
        "pov_actor_id": _text(payload, "pov_actor_id", coordinate=coordinate),
        "participants": _words(
            payload, "participants", coordinate=coordinate
        ),
        "planned_start_tick": _tick(
            payload, "planned_start_tick", coordinate=coordinate
        ),
    }
    for key in _PLAN_ELEMENT_TEXT_KEYS:
        element[key] = _text(payload, key, coordinate=coordinate)
    if "required_beats" in payload:
        beats = payload["required_beats"]
        if (
            isinstance(beats, (str, bytes))
            or not isinstance(beats, list)
            or not all(isinstance(beat, dict) for beat in beats)
        ):
            raise LlmProviderError("bad-shape")
        element["required_beats"] = [dict(beat) for beat in beats]
    if "user_present" in payload:
        marker = payload["user_present"]
        if not isinstance(marker, bool):
            raise LlmProviderError("bad-shape")
        element["user_present"] = marker
    return element


def _parse_blueprint(text: str) -> dict[str, Any]:
    """One Blueprint payload: the nine chapter fields plus a non-empty
    ``scenes`` table whose elements carry the canonical ten keys —
    shape only; the Director's own schema keeps every deeper judgment
    (identity namespace, POV eligibility, tick windows, membership)."""

    payload = _payload_object(text)
    blueprint: dict[str, Any] = {
        "goal": _text(payload, "goal"),
        "dramatic_question": _text(payload, "dramatic_question"),
        "planned_start_tick": _tick(payload, "planned_start_tick"),
        "planned_end_tick": _tick(payload, "planned_end_tick"),
        "closing_pressure": _text(payload, "closing_pressure"),
        "desired_development": _text(payload, "desired_development"),
        "soft_outcomes": _text(payload, "soft_outcomes"),
        "chapter_questions_to_advance": _text(
            payload, "chapter_questions_to_advance"
        ),
    }
    scenes = _field(payload, "scenes")
    if not isinstance(scenes, list) or not scenes:
        raise LlmProviderError("bad-shape")
    parsed_scenes: list[dict[str, Any]] = []
    for ordinal, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise LlmProviderError("bad-shape")
        coordinate = f"scenes[{ordinal}]"
        element = _parse_scene_element(scene, coordinate=coordinate)
        element["purpose"] = _text(
            scene, "purpose", coordinate=coordinate
        )
        parsed_scenes.append(element)
    blueprint["scenes"] = parsed_scenes
    return blueprint


def _parse_adjudication(text: str) -> Adjudication:
    """One verdict: the :class:`~elc.world.action.Adjudication` shape
    verbatim — the seven fields present, typed and (for
    ``replan_scope``) inside its three-word vocabulary; a
    ``state_effects`` entry is one ``{key, statement}`` object."""

    payload = _payload_object(text)
    interpretation = _text(payload, "interpretation")
    outcome = _text(payload, "outcome")
    actual_action = _text(payload, "actual_action")
    consequences = _text(payload, "consequences")
    effects = _field(payload, "state_effects")
    if not isinstance(effects, list):
        raise LlmProviderError("bad-shape")
    parsed_effects: list[StateEffect] = []
    for ordinal, effect in enumerate(effects):
        coordinate = f"state_effects[{ordinal}]"
        if not isinstance(effect, dict):
            raise LlmProviderError("bad-shape")
        parsed_effects.append(
            StateEffect(
                key=_text(effect, "key", coordinate=coordinate),
                statement=_text(effect, "statement", coordinate=coordinate),
            )
        )
    participants = _words(payload, "participants")
    scope = _field(payload, "replan_scope")
    if not isinstance(scope, str) or scope not in _REPLAN_SCOPE_WORDS:
        raise LlmProviderError("bad-shape")
    return Adjudication(
        interpretation=interpretation,
        outcome=outcome,
        actual_action=actual_action,
        consequences=consequences,
        state_effects=tuple(parsed_effects),
        participants=participants,
        replan_scope=_REPLAN_SCOPE_WORDS[scope],
    )


# ---------------------------------------------------------------------------
# the prompt assembly (pure functions of the context hand)
# ---------------------------------------------------------------------------

#: The ``must_hide`` fragment vocabulary — the same delimiters the
#: deterministic guard in :mod:`elc.world.writer` splits on (line
#: breaks plus the CJK and Latin sentence punctuation), mirrored here
#: so the prompt's prohibition list names exactly the fragments the
#: lexical guard will refuse.
_HIDDEN_SPLIT = re.compile(r"[\n\r。！？；.!?;]+")


def _hidden_fragments(must_hide: str) -> list[str]:
    """The non-empty ``must_hide`` fragments, in order (the guard's own
    split; an empty field answers no fragments)."""

    return [
        fragment.strip()
        for fragment in _HIDDEN_SPLIT.split(must_hide)
        if fragment.strip()
    ]


def _render_list(lines: list[str]) -> str:
    """One bullet list — the honest empty case spelled, never a blank
    slot a model could read as a prompt bug."""

    if not lines:
        return "- (nothing declared)"
    return "\n".join(f"- {line}" for line in lines)


def _render_cognition(view: V3CognitionView) -> str:
    """One viewer's cognition view as the prompt reads it — the public
    layer first, the witnessed layer second (the view's own order)."""

    lines = [f"(common knowledge) {event.narration}" for event in view.public]
    lines += [
        f"(witnessed) {event.narration}" for event in view.witnessed
    ]
    return _render_list(lines)


def _render_memory(view: V3MemoryView) -> str:
    """One viewer's memory rows as the prompt reads them (kind and
    content; the view's own layering order)."""

    return _render_list(
        [f"({row.kind.value}) {row.content}" for row in view.memories]
    )


def _render_facts(facts: tuple[WorldStateFact, ...]) -> str:
    """The settled fact half — ``canonical_key: statement`` per row."""

    return _render_list(
        [f"{fact.canonical_key}: {fact.statement}" for fact in facts]
    )


def _render_bible(bible: BibleRevision | None) -> str:
    """The world's fourteen Bible fields, all of them (an undeclared
    field rides the empty string, the honest undeclared); no Bible at
    all is said plainly."""

    if bible is None:
        return (
            "(no Bible revision is declared for this world — the honest"
            " undeclared)"
        )
    fields = (
        ("premise", bible.premise),
        ("genre", bible.genre),
        ("tone", bible.tone),
        ("calendar", bible.calendar),
        ("physics", bible.physics),
        ("magic_rules", bible.magic_rules),
        ("geography", bible.geography),
        ("society", bible.society),
        ("politics", bible.politics),
        ("technology", bible.technology),
        ("religion", bible.religion),
        ("history", bible.history),
        ("hard_rules", bible.hard_rules),
        ("narrative_preferences", bible.narrative_preferences),
    )
    return "\n".join(f"- {name}: {value}" for name, value in fields)


def _render_storylines(storylines: tuple[WorldStorylineRecord, ...]) -> str:
    """The active storyline rows (theme and closure condition)."""

    return _render_list(
        [
            f"{line.line_id} [{line.status}]: {line.theme} — resolves at:"
            f" {line.resolve_at}"
            for line in storylines
        ]
    )


def _render_summaries(
    summaries: tuple[ChapterSettlementRecord, ...]
) -> str:
    """The settled chapters' compressed summaries (the next-chapter
    read face, V3-7)."""

    return _render_list(
        [f"{row.chapter_id}: {row.summary}" for row in summaries]
    )


def _render_members(members: tuple[DirectorCastMember, ...]) -> str:
    """The AI cast as the Director reads it: the card's six person
    fields and the world profile (the private context included — this
    is the world-authoritative face, deliberately not POV-limited)."""

    lines: list[str] = []
    for member in members:
        profile = member.profile
        if profile is None:
            profile_text = "no narrative profile declared"
        else:
            role = (
                "undeclared"
                if profile.story_role is None
                else str(profile.story_role)
            )
            eligible = (
                "undeclared"
                if profile.pov_eligible is None
                else str(profile.pov_eligible)
            )
            profile_text = (
                f"role={role}, pov_eligible={eligible},"
                f" long_term_drive={profile.long_term_drive!r},"
                f" current_arc_seed={profile.current_arc_seed!r},"
                f" private_context={profile.private_context!r}"
            )
        lines.append(
            f"{member.actor_id} ({member.name}):"
            f" identity={member.identity!r},"
            f" personality={member.personality!r},"
            f" background={member.background!r},"
            f" speech_style={member.speech_style!r},"
            f" values={member.values!r},"
            f" boundaries={member.boundaries!r} — profile: {profile_text}"
        )
    return _render_list(lines)


def _render_player(player: DirectorPlayerCharacter | None) -> str:
    """The reader's durable character as the planning faces read her
    (the profile face; the V3-3R seed columns deliberately absent)."""

    if player is None:
        return "(no player character is declared for this world)"
    return (
        f"{player.player_character_id} ({player.name}):"
        f" background={player.background!r},"
        f" appearance={player.appearance!r},"
        f" abilities={player.abilities!r},"
        f" limits={player.limits!r}"
    )


def _render_profiles(profiles: tuple[ActorProfileRecord, ...]) -> str:
    """The scene's counterpart profiles as the resolver reads them."""

    lines: list[str] = []
    for profile in profiles:
        role = (
            "undeclared"
            if profile.story_role is None
            else str(profile.story_role)
        )
        lines.append(
            f"{profile.actor_id} (role={role}):"
            f" long_term_drive={profile.long_term_drive!r},"
            f" current_arc_seed={profile.current_arc_seed!r},"
            f" private_context={profile.private_context!r}"
        )
    return _render_list(lines)


def _content_block(content: Mapping[str, Any] | None) -> str:
    """One current plan payload as the prompt reads it — a deterministic
    JSON dump (sorted keys, compact), or the honest none."""

    if content is None:
        return "(none — answer from the plan state you are given)"
    return json.dumps(
        dict(content), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


#: The value-type contract the JSON-answering arms state verbatim
#: (V3-8f, the paradigm shift §10.4): every prose field is ONE JSON
#: string — several items join into that one string separated by
#: newlines (the same separator the ``must_hide`` fragment law splits
#: on); arrays and integers are named as such per field. Without this
#: contract a real model naturally answers a plural-meaning prose field
#: as an array and the strict parser refuses ``bad-shape``. The Writer
#: arm answers prose, not JSON, and does not carry it.
_PROSE_TYPE_SENTENCE = (
    "Value types: every prose (text) field is ONE JSON string — never an"
    " array; when several items belong in one field, write them into"
    " that one string separated by newlines. Arrays are JSON arrays of"
    " exactly the items named, and ticks are JSON integers."
)

#: The identity-vocabulary contract the same three arms state verbatim
#: (V3-8f's smoke run, the fifth face — same family as the type
#: contract, and **strengthened on the smoke's second run**, the
#: planner layer of the same face): the prompts render a participant as
#: ``id (name)`` or ``id (role=…)``, and a real Resolver answered the
#: rendered composite back (``cousin (Renn)``) into ``participants`` —
#: the namespace check (the V3-3R freeze) refused it. The second run
#: went one step further: the planner replan answered ``renn`` (the
#: display name of the id ``cousin``) beside the prose-only newcomer
#: ``carter``, and the continuation segment was refused. The contract
#: therefore carries four clauses — identity strings come only from
#: the ids this prompt itself lists (written exactly as listed, the
#: bare id token); an id is never replaced by a character's display
#: name; no identity outside the prompt's own vocabulary is ever
#: added; and a name that appears only in prose (cognition, memory, a
#: ruling's text) is not an identity — a character first met on the
#: page stays in the prose. The Writer arm answers prose, not
#: identities, and does not carry it.
_IDENTITY_SENTENCE = (
    "Identity strings: every identity string (participants entries,"
    " pov_actor_id) must be taken from the ids this prompt itself"
    " lists — written exactly as listed, the bare id token (the part"
    " before any parenthesis where the id is rendered with a name or"
    " role). Never answer the rendered display form: the identity"
    " string is the id alone. Never replace an id with a character's"
    " display name — a display name is not an identity, only the"
    " listed id is — and never add an identity this prompt does not"
    " list. A name that appears only in narrative prose (cognition,"
    " memory, a ruling's text) is not an identity: a character first"
    " met on the page stays in the prose and never enters"
    " participants."
)


#: The prose-language vocabulary (V3-8g, §10.4 item 5): the two words a
#: prompt's language line renders — ``en`` (the learning product's own
#: default) and ``zh`` (the switcher's second face). The reading face
#: stores exactly one of these under its ``v3_prose_language`` setting
#: and hands it to every provider it builds; a direct caller that
#: passes no word gets :data:`PROSE_LANGUAGE_DEFAULT`.
PROSE_LANGUAGE_DEFAULT = "en"
PROSE_LANGUAGE_WORDS = ("en", "zh")

#: The writer arm's prose-language sentence per word: at ``en`` — the
#: default face — exactly the sentence this cut found in place (byte
#: for byte; the existing prompt pins ride it); at ``zh`` the Chinese
#: instruction the switcher asks for.
_WRITER_PROSE_LINE = {
    "en": "Write the segment's prose in English.",
    "zh": "用中文写作这一段的正文。",
}

#: The three JSON arms' language line per word — the same default made
#: explicit (the semantics today's prompts already carried implicitly),
#: and its Chinese counterpart. JSON keys, identity strings and the
#: three-word enum are never language: the line names the
#: natural-language fields only.
_JSON_PROSE_LINE = {
    "en": "Write every natural-language field (all prose) in English.",
    "zh": "所有自然语言字段（全部散文内容）一律用中文写作。",
}

#: The continuity law's sentence (V3-8g, §10.4 item 6; see the module
#: docstring): the event lists are what has already happened AND has
#: already been narrated — the segment advances the story and never
#: re-tells what those lists carry. A continuation resuming a
#: committed ruling obeys the same law (the ruling is already
#: narrated). Stated once in the writer prompt; the same arm writes
#: plain segments and continuations both.
_CONTINUITY_SENTENCE = (
    "Advance the story, never re-tell it: the events listed below"
    " under cognition / memory — and, for a continuation, the"
    " committed ruling it resumes — have already happened and have"
    " already been narrated; they are this segment's past, never its"
    " content. Write what happens next (new beats, actions and"
    " perceptions) and never repeat, restate or transcribe a"
    " narration already on those lists; continue from where the"
    " lists end."
)

#: The gate-production law's sentence per word (V3-8i, the paradigm
#: shift §10.6 item 1): every planned scene must plan the reader's own
#: will — a ``required_beats`` list of beat objects with **at least one
#: gate beat** per scene (the §2.5 criteria: where deciding for the
#: reader might be something they would mind) and a ``user_present``
#: boolean. The ch02 field failure this face fixes was a real chapter
#: planned with zero gates and an eleven-segment runaway — the beats
#: and the marker are the plan-level seat of §2.5's stop law. The JSON
#: keys and the beat shape are never language; the law's sentence is.
_GATE_BEATS_SENTENCE = {
    "en": (
        "Every scene must also plan the reader's own will: each scene"
        ' element carries "required_beats" — a JSON array of beat'
        ' objects, each {"kind": "segment"} for one planned segment or'
        ' {"kind": "gate", "reason": <one JSON string>, "options": <a'
        " JSON array of 2-4 short natural actions>} — with AT LEAST ONE"
        " gate beat in every scene: a gate beat marks where the story"
        " MUST stop for the reader's own meaningful act of will (what"
        " to say, whether to agree or refuse, whether to attack or"
        " confess, a secret told, a bond changed — any moment where"
        " deciding for the reader might be something they would mind);"
        " the reason names that stop in one sentence, and the options"
        " are 2-4 natural behaviours the reader's character could take"
        " (never plot outlines). Each scene element also carries"
        ' "user_present": one JSON boolean — whether the reader\'s'
        " character takes part in the scene."
    ),
    "zh": (
        "每场还必须为读者自己的意志做规划：每个场景元素都携带"
        ' "required_beats"——一个 JSON 数组，元素是拍对象：段拍为'
        ' {"kind": "segment"}，门拍为 {"kind": "gate", "reason":'
        " <一个 JSON 字符串>, \"options\": <2–4 个简短自然举动的 JSON"
        " 数组>}——每场至少一个门拍：门拍标记故事必须停下来等读者自己"
        "做出有意义意志行为的位置（说什么 / 是否答应或拒绝 / 是否攻击"
        "或表白 / 说出秘密 / 关系改变——凡是替读者决定、读者可能会介意"
        "的时刻）；reason 用一句话写明这个停点，options 是该读者的角色"
        "可以采取的 2–4 个自然行为选项（绝不是剧情纲要）。每个场景元素"
        '还携带 "user_present"：一个 JSON 布尔值——读者的角色是否在场。'
    ),
}

#: The player-character anchor sentence per word, Writer arm (V3-8i,
#: the paradigm shift §10.6 item 2): the no-puppet rule anchored to the
#: concrete name — the ch02 field failure had the writer autonomously
#: puppeting the player character because the participants list was a
#: bare id list the rule could not bind to. The line is ADDITIVE (the
#: existing participants line stays byte for byte) and rides only when
#: the compiled context carries the player character's id (the
#: pipeline passes it; a context without it renders today's prompt
#: byte for byte).
_WRITER_PLAYER_SENTENCE = {
    "en": (
        "- the player character: {player} — the reader's own character;"
        " never make decisions, speak or act with intent for them:"
        " their significant acts of will enter the story only through"
        " a User Gate."
    ),
    "zh": (
        "- 玩家角色：{player}——读者自己的角色；绝不替他们做决定、说话"
        "或行动：他们显著的意志行为只会经用户意志门（User Gate）进入"
        "故事。"
    ),
}

#: The same anchor, Scene Planner arm (V3-8i): the plan never writes
#: the player's choices — their significant acts of will are the
#: scene's gate beats, nothing else.
_PLANNER_PLAYER_SENTENCE = {
    "en": (
        "- the player character: {player} — the reader's own character;"
        " the plan never writes their choices: their significant acts"
        " of will are the scene's User Gate beats, nothing else."
    ),
    "zh": (
        "- 玩家角色：{player}——读者自己的角色；计划绝不替他们写定选择："
        "他们显著的意志行为只落为本场的用户意志门（User Gate）拍，"
        "别无其他。"
    ),
}

#: The same anchor, Resolver arm (V3-8i): the player's will rides the
#: durable submission alone — never an invention of the resolver's.
_RESOLVER_PLAYER_SENTENCE = {
    "en": (
        "- the player character: {player} — the reader's own character;"
        " their will rides the submission below, never an invention of"
        " yours."
    ),
    "zh": (
        "- 玩家角色：{player}——读者自己的角色；他们的意志只来自下方那份"
        "提交本身，绝不由你发明。"
    ),
}


#: The author layer's soft-expectation sentence per word (V3-8h, the
#: paradigm shift §10.5 item 2): the reader's between-chapters
#: direction is quoted into the **initial** chapter plan prompt with
#: the wording law stated verbatim — the direction says where the
#: chapter should PRESS toward, it is never a postcondition or a hard
#: requirement, and no story fact may be invented on the reader's
#: behalf (the world's own rules and settled facts decide what
#: actually happens). The CHAPTER replan arm never carries it (its
#: reason is the committed ruling alone), and an absent direction
#: carries no line at all — the prompt stays byte for byte today's.
_AUTHOR_DIRECTION_SENTENCE = {
    "en": (
        "The reader's author-layer direction (quoted below) is a soft"
        " expectation only: it says where the next chapter should"
        " PRESS toward — treat it as pressure on the plan's choices,"
        " never as a postcondition, never as a hard requirement, and"
        " never invent story facts on the reader's behalf: the"
        " world's own rules and settled facts decide what actually"
        " happens."
    ),
    "zh": (
        "读者的作者层方向（见下方引文）只是软期望：它只表达下一章"
        "「朝哪里压」——把它当作对计划选择的倾向性压力，绝不是"
        " postcondition、不是硬性条件；不得替读者发明剧情事实："
        "实际发生什么由世界自己的规则与既定事实决定。"
    ),
}


def _prose_language_word(language: str) -> str:
    """The language word a prompt renders — the two-word vocabulary, or
    the default for anything outside it. The reading face normalizes the
    stored setting before it constructs these providers, so an unknown
    word here is a caller's bug that stays on the default face — never a
    crash and never a third dialect."""

    return language if language in PROSE_LANGUAGE_WORDS else (
        PROSE_LANGUAGE_DEFAULT
    )


def _writer_prompt(
    context: PovContext, *, language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The Writer arm's prompt (see the class docstring): the POV-safe
    context is all this assembly may read — the compiled object is the
    hard door, and no face it does not carry can ride into the prompt.
    The prose-language line and the continuity law are V3-8g's two
    additions (see the module docstring)."""

    lines = [
        "You are the POV writer for ONE segment of an interactive story",
        f"world. {_WRITER_PROSE_LINE[_prose_language_word(language)]}",
        "",
        "Hard rules:",
        "- One main point of view: write only what "
        f"{context.pov_actor_id} perceives,",
        "  knows or remembers. The scene plan and the cognition / memory",
        "  listed below are the whole of what this segment may present",
        "  as known.",
        "- Never make decisions, speak or act with intent for the user's",
        "  character: the user's own will is not yours to invent.",
        "- Only present what has already happened: never narrate the",
        "  future or anything not yet established.",
        f"- {_CONTINUITY_SENTENCE}",
        "- Never reveal, state or hint at the must_hide face below — not",
        "  in narration, not in dialogue, not in metaphor.",
        "",
        "The scene's plan face:",
        f"- place: {context.place}",
        f"- entry_goals: {context.entry_goals}",
        f"- exit_condition: {context.exit_condition}",
        f"- revealable (may be revealed, once earned): {context.revealable}",
        "- must_hide — hard prohibitions, one by one:",
    ]
    hidden = _hidden_fragments(context.must_hide)
    if hidden:
        lines.extend(f"  - {fragment}" for fragment in hidden)
    else:
        lines.append("  - (none declared)")
    lines.extend(
        [
            "",
            "The segment:",
            f"- segment_seq: {context.segment_seq}",
            f"- current_tick: {context.current_tick}",
            f"- participants: {', '.join(context.participants)}",
            # V3-8i: the no-puppet rule anchored to the concrete name —
            # the additive player line (the participants line stays byte
            # for byte); absent when the context carries no player id.
            *(
                []
                if context.player_character_id is None
                else [
                    _WRITER_PLAYER_SENTENCE[
                        _prose_language_word(language)
                    ].format(player=context.player_character_id)
                ]
            ),
            "",
            f"{context.pov_actor_id}'s own cognition (what they know as",
            "common knowledge, and what they witnessed):",
            _render_cognition(context.cognition),
            "",
            f"{context.pov_actor_id}'s own memory:",
            _render_memory(context.memory),
        ]
    )
    return "\n".join(lines)


def _planner_prompt(
    context: ScenePlanContext, *, language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The Planner arm's prompt for a fresh scene plan — the POV-safe
    scene context and nothing else."""

    return _scene_plan_prompt(context, replan=False, language=language)


def _planner_replan_prompt(
    context: ScenePlanContext, *, language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The Planner arm's prompt for the SCENE replan — the current
    element is the content the revision starts from."""

    return _scene_plan_prompt(context, replan=True, language=language)


def _scene_plan_prompt(
    context: ScenePlanContext, *, replan: bool,
    language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The shared scene-plan prompt body: the scene's identity, the
    current plan content and the POV's own cognition / memory; the
    answer is one JSON object in the element's own nine-key shape. The
    language line names the language the JSON's natural-language fields
    are written in (V3-8g; keys and identity strings are never
    language)."""

    if replan:
        opening = [
            "You are the scene planner of an interactive story world. The",
            "scene's current plan must be revised: the committed story has",
            "moved past it, and the revised element must follow what has",
            "already happened — never round back to the plan the move",
            "invalidated.",
        ]
    else:
        opening = [
            "You are the scene planner of an interactive story world.",
            "Plan ONE scene: answer its plan content as one JSON object",
            "and nothing else.",
        ]
    lines = [
        *opening,
        _JSON_PROSE_LINE[_prose_language_word(language)],
        "",
        "The object's keys (all required; keys beyond them are ignored).",
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        '- "pov_actor_id": one JSON string — the scene\'s one point-of-view',
        "  character, a participant identity string, and a member of the",
        "  participants",
        '- "participants": a JSON array of participant identity strings',
        "  — the identity strings the current plan content already",
        "  carries, written exactly as it lists them",
        '- "planned_start_tick": one JSON integer — an integer story tick',
        '- "place": one JSON string — where the scene happens',
        '- "entry_goals": one JSON string — what the scene opens toward',
        '- "exit_condition": one JSON string — the condition under which',
        "  the scene closes",
        '- "elasticity": one JSON string — how far the scene may stretch',
        '- "revealable": one JSON string — what may be revealed, once it',
        "  is earned",
        '- "must_hide": one JSON string — the hard prohibitions, what must',
        "  NOT be revealed",
        "",
        f"Scene: {context.scene_id} (world {context.world_id})",
        f"POV: {context.pov_actor_id}",
        f"current_tick: {context.current_tick}",
        # V3-8i: the additive player anchor (see the writer arm) — the
        # plan never writes the player's choices; absent without an id.
        *(
            []
            if context.player_character_id is None
            else [
                _PLANNER_PLAYER_SENTENCE[
                    _prose_language_word(language)
                ].format(player=context.player_character_id)
            ]
        ),
        "",
        "The scene's current plan content:",
        _content_block(context.element),
        "",
        f"{context.pov_actor_id}'s own cognition (what they know as",
        "common knowledge, and what they witnessed):",
        _render_cognition(context.cognition),
        "",
        f"{context.pov_actor_id}'s own memory:",
        _render_memory(context.memory),
    ]
    return "\n".join(lines)


def _author_direction_lines(
    context: DirectorPlanContext, *, replan: bool, language: str
) -> list[str]:
    """The author layer's prompt block, or ``[]`` — the wording-law
    sentence in the prompt's own language plus the direction quoted
    verbatim (``!r``). ``[]`` (never an empty-headed block) on the
    replan arm or when there is no non-blank direction: the
    no-direction prompt stays byte for byte today's."""

    direction = context.author_direction
    if replan or not isinstance(direction, str) or not direction.strip():
        return []
    return [
        _AUTHOR_DIRECTION_SENTENCE[_prose_language_word(language)],
        f"- the direction, verbatim: {direction.strip()!r}",
        "",
    ]


def _director_prompt(
    context: DirectorPlanContext, *, language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The Director arm's prompt for the initial chapter plan — the
    full ``DirectorContext`` and nothing else (the chapter plan is the
    world's, not one character's)."""

    return _blueprint_prompt(context, replan=False, language=language)


def _director_replan_prompt(
    context: DirectorPlanContext, *, language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The Director arm's prompt for the CHAPTER replan — the committed
    ruling that invalidated the plan and the current Blueprint the
    revision starts from."""

    return _blueprint_prompt(context, replan=True, language=language)


def _blueprint_prompt(
    context: DirectorPlanContext, *, replan: bool,
    language: str = PROSE_LANGUAGE_DEFAULT
) -> str:
    """The shared Blueprint prompt body: the world-authoritative
    ``DirectorContext`` reading, the wording law, the payload's own
    schema (nine chapter fields; ten-key scene elements) — plus, on the
    replan arm, the triggering ruling and the current Blueprint. The
    language line names the language the JSON's natural-language fields
    are written in (V3-8g)."""

    director_context: DirectorContext = context.director_context
    lines = [
        "You are the world director of an interactive story world. Plan",
        "ONE chapter and answer with one JSON object and nothing else.",
        _JSON_PROSE_LINE[_prose_language_word(language)],
        "",
        "The object's chapter fields (all required).",
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        '- "goal": one JSON string — what the chapter sets out to reach',
        '- "dramatic_question": one JSON string — the question the',
        "  chapter presses",
        '- "planned_start_tick" / "planned_end_tick": each one JSON',
        "  integer — the planned story window; the end never before the",
        "  start",
        '- "closing_pressure": one JSON string — where the chapter',
        "  presses at its close",
        '- "desired_development": one JSON string — the development it',
        "  works toward",
        '- "soft_outcomes": one JSON string — the shape of an outcome it',
        "  reaches toward",
        '- "chapter_questions_to_advance": one JSON string — the',
        "  questions it advances",
        '- "scenes": a non-empty array of scene elements',
        "The wording law: closing_pressure, desired_development,",
        "soft_outcomes and chapter_questions_to_advance say where the",
        "chapter PRESSES — a soft expectation, never a postcondition.",
        "No soft expectation may be written as a hard condition.",
        "",
        "Every scene element carries exactly these ten keys:",
        "purpose, place, pov_actor_id, participants,",
        "planned_start_tick, entry_goals, exit_condition, elasticity,",
        "revealable, must_hide — with the POV among the participants",
        "(one POV per scene). Inside an element: purpose, place,",
        "pov_actor_id, entry_goals, exit_condition, elasticity,",
        "revealable and must_hide are each ONE JSON string (several",
        "items join into that one string separated by newlines);",
        "participants is a JSON array of participant identity strings;",
        "planned_start_tick is one JSON integer.",
        # V3-8i (the paradigm shift §10.6 item 1): the gate-production
        # law — every scene plans the reader's own will (the beat list
        # with at least one gate beat) and marks the reader's presence.
        _GATE_BEATS_SENTENCE[_prose_language_word(language)],
        "",
        # V3-8h: the author layer's soft expectation — the initial arm
        # only (a CHAPTER replan's reason is the committed ruling, and
        # it never reads this); an absent direction leaves the prompt
        # byte for byte what it always was.
        *_author_direction_lines(
            context, replan=replan, language=language
        ),
        "The world you plan for:",
        f"- world: {director_context.world_id}",
        f"- current_tick: {director_context.current_tick}",
        "- Bible (the world's rules and setting):",
        _render_bible(director_context.bible),
        "- settled facts (the current world state):",
        _render_facts(director_context.current_facts),
        "- active storylines:",
        _render_storylines(director_context.storylines),
        "- settled chapters already compressed (what came before):",
        _render_summaries(director_context.chapter_summaries),
        "- the cast (AI actors) and their profiles:",
        _render_members(director_context.cast.members),
        "- the player character (the reader's own):",
        _render_player(director_context.cast.player_character),
    ]
    if replan:
        trigger = context.trigger
        if trigger is None:
            trigger_block = "(no committed ruling rides — replay of a plan)"
        else:
            trigger_block = (
                f"intent_text={trigger.intent_text!r},"
                f" outcome={trigger.outcome!r},"
                f" actual_action={trigger.actual_action!r},"
                f" consequences={trigger.consequences!r}"
            )
        lines.extend(
            [
                "",
                "The replan's own faces:",
                f"- chapter: {context.chapter_id}",
                f"- replan_request_id: {context.replan_request_id}",
                "- the committed ruling that invalidated the plan (the",
                "  user's own words — never a fresh invented intent):",
                f"  {trigger_block}",
                "- the chapter's current Blueprint (the revision starts",
                "  from it):",
                _content_block(context.blueprint),
            ]
        )
    return "\n".join(lines)


def _resolver_prompt(
    context: ResolverContext, *, language: str = "en"
) -> str:
    """The Resolver arm's prompt — the world-authoritative context: the
    Bible, the settled facts, the player's profile, the counterparts,
    the scene's place and participants, the **player character's own**
    knowledge arms (``player_cognition`` / ``player_memory`` — the
    authority for what the user character knows, V3-8c's F4) and the
    scene's POV face (the presentation face, carried beside them), plus
    the user's own durable submission. The language line names the
    language the JSON's natural-language fields are written in
    (V3-8g)."""

    if context.player_character is None:
        player_block = "(no player character is declared for this world)"
    else:
        player = context.player_character
        player_block = (
            f"{player.player_character_id} ({player.name}):"
            f" abilities={player.abilities!r}, limits={player.limits!r}"
            " (the row's location / state / knowledge_refs are"
            " creation-time seed only — the running location and state"
            " are the settled facts above)"
        )
    if context.player_cognition is None or context.player_memory is None:
        knows_block = (
            "(no player-side knowledge arm rides — the world declares no"
            " player character)"
        )
    else:
        knows_block = (
            "cognition:\n"
            f"{_render_cognition(context.player_cognition)}\n"
            "memory:\n"
            f"{_render_memory(context.player_memory)}"
        )
    lines = [
        "You are the action resolver of an interactive story world: the",
        "user has submitted an intent at a story stop, and you decide",
        "what actually happens — the world's one authoritative outcome.",
        "Answer with one JSON object and nothing else, carrying exactly",
        "these keys.",
        _JSON_PROSE_LINE[_prose_language_word(language)],
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        '- "interpretation": one JSON string — what the submission means',
        "  in this world (a reading of the user's intent, never an",
        "  invented intention)",
        '- "outcome": one JSON string — what actually happens, as world',
        "  fact",
        '- "actual_action": one JSON string — the action that actually',
        "  unfolds",
        '- "consequences": one JSON string — what changes because of it',
        '- "state_effects": a JSON array of {"key": <one JSON string>,',
        '  "statement": <one JSON string>} objects settling the changed',
        "  world state (may be empty)",
        '- "participants": a JSON array of participant identity strings',
        "  the outcome is about",
        '- "replan_scope": exactly one of "NONE" | "SCENE" | "CHAPTER" —',
        "  whether the scene's plan or the chapter's plan must be revised",
        "",
        "Hard rules:",
        "- The submission is the user's intent, not a world fact: never",
        "  extend, upgrade or invent the user's intent — decide what",
        "  happens, not what they meant beyond the words given.",
        "- Rule by the world's real rules, its physics and the",
        "  participants' abilities and limits: the world authority below",
        "  is your knowledge; a soft expectation is never a condition.",
        "- A plan the move invalidated must not round back: if the",
        "  committed outcome broke the current plan, say so through",
        "  replan_scope.",
        "",
        "The world authority:",
        "- Bible (the world's rules and setting):",
        _render_bible(context.bible),
        "- settled facts (the current world state — the current",
        "  location / physical state / inventory / resources live here):",
        _render_facts(context.current_facts),
        f"- place: {context.place}",
        f"- participants: {', '.join(context.participants)}",
        # V3-8i: the additive player anchor (the participants line stays
        # byte for byte) — the player's will rides the submission, never
        # an invention of the resolver's; absent with no player row.
        *(
            []
            if context.player_character is None
            else [
                _RESOLVER_PLAYER_SENTENCE[
                    _prose_language_word(language)
                ].format(
                    player=context.player_character.player_character_id
                )
            ]
        ),
        "- the player character (abilities / limits):",
        f"  {player_block}",
        "- the scene's counterpart profiles:",
        _render_profiles(context.counterparts),
        "- what the user's character knows (the player character's own",
        "  durable cognition and memory — the authority for what the",
        "  user knows):",
        knows_block,
        f"- the scene's narrative POV ({context.pov_actor_id}) — the",
        "  presentation face, carried beside the player's own read (the",
        "  prose presents through this POV; it is not the judge of what",
        "  the user knows):",
        f"  cognition:\n{_render_cognition(context.cognition)}",
        f"  memory:\n{_render_memory(context.memory)}",
        "",
        "The user's own submission (durable, never an invention):",
        f"- intent_text: {context.intent_text!r}",
        f"- selected_option: {context.selected_option!r}",
        f"- options: {', '.join(context.options)}",
        f"- current_tick: {context.current_tick}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the four implementations (structural conformance — see the module
# docstring; the Protocols are the contract, no inheritance)
# ---------------------------------------------------------------------------


class LlmWriterProvider:
    """The Writer arm over one :class:`TextCompletion` seam: the
    POV-safe prompt (the compiled context is the hard door), then the
    cleaned prose. ``language`` is the prose-language word this arm's
    prompt carries (V3-8g; default ``en`` — the existing prompt). An
    empty answer is the honest ``no-output`` refusal —
    :class:`~elc.world.writer.PovWriter`'s deterministic guards and
    the SEGMENT COMMIT stay the library face's, downstream."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def write_segment(self, context: PovContext) -> str:
        """One segment's prose from the POV-safe context (see the class
        docstring)."""

        body = _clean(
            _complete_text(
                self._completion,
                _writer_prompt(context, language=self._language),
            )
        )
        if not body:
            raise LlmProviderError("no-output")
        return body


class LlmPlannerProvider:
    """The Planner arm (the SCENE level only, V3-8b's division
    freeze) over one :class:`TextCompletion` seam: ``plan_scene``
    answers the scene's element payload, ``replan_element`` the SCENE
    replan's revised element — both parsed in the element's own
    nine-key shape; the seats that consume them keep every deeper
    judgment. ``language`` is the JSON's natural-language word
    (V3-8g; default ``en``)."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def plan_scene(self, context: ScenePlanContext) -> Mapping[str, Any]:
        """The scene's plan content (see the class docstring)."""

        return _parse_scene_element(
            _payload_object(
                _complete_text(
                    self._completion,
                    _planner_prompt(context, language=self._language),
                )
            )
        )

    def replan_element(
        self, context: ScenePlanContext
    ) -> Mapping[str, Any]:
        """The SCENE arm's revised element (see the class docstring)."""

        return _parse_scene_element(
            _payload_object(
                _complete_text(
                    self._completion,
                    _planner_replan_prompt(
                        context, language=self._language
                    ),
                )
            )
        )


class LlmDirectorProvider:
    """The Director arm (V3-8b's HIGH-3: the initial Chapter Blueprint
    and the CHAPTER replan) over one :class:`TextCompletion` seam — the
    full ``DirectorContext`` reading goes in, the Blueprint payload's
    shape comes out; ``Director.open_next_chapter`` /
    ``apply_action_replan`` keep the validation and the persistence.
    ``language`` is the JSON's natural-language word (V3-8g; default
    ``en``)."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def draft_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]:
        """The initial Blueprint (see the class docstring)."""

        return _parse_blueprint(
            _complete_text(
                self._completion,
                _director_prompt(context, language=self._language),
            )
        )

    def replan_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]:
        """The CHAPTER arm's revised Blueprint (see the class
        docstring)."""

        return _parse_blueprint(
            _complete_text(
                self._completion,
                _director_replan_prompt(
                    context, language=self._language
                ),
            )
        )


class LlmResolverProvider:
    """The Resolver arm over one :class:`TextCompletion` seam: the
    world-authoritative prompt (F4: the player character's own
    knowledge arms are the "user knows" authority; the POV face rides
    as the presentation face), then the verdict in the
    :class:`~elc.world.action.Adjudication` shape verbatim — the sole
    adjudication authority
    (:func:`elc.world.action.commit_action`) is downstream and
    unchanged. ``language`` is the JSON's natural-language word
    (V3-8g; default ``en``)."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def adjudicate(self, context: ResolverContext) -> Adjudication:
        """The verdict for this submission (see the class docstring)."""

        return _parse_adjudication(
            _complete_text(
                self._completion,
                _resolver_prompt(context, language=self._language),
            )
        )


# ---------------------------------------------------------------------------
# the dual-seat extension (DS-1, the technical definition §1–§4, §12) —
# three new model arms over the same seam, the same parsing law, and the
# re-opened streaming face. Everything below is additive: the four
# original arms above keep every constructor and signature byte for byte.
# ---------------------------------------------------------------------------


@runtime_checkable
class StreamingTextCompletion(Protocol):
    """The re-opened streaming face (DS-1, the technical definition §12
    F15) — the bypass channel beside :class:`TextCompletion`: the same
    one-prompt-in value shape, with the answer's increments handed to
    ``on_chunk`` exactly once, in arrival order, and the honest whole
    returned as the outcome (the persona adapter's ``call_streaming``
    contract). A completion that does not carry this method simply never
    satisfies the protocol — the callers check at call time and fall
    back to the blocking face, so no existing constructor changes."""

    def complete_streaming(
        self, prompt: str, on_chunk: Callable[[str], None]
    ) -> CompletionOutcome: ...


@dataclass(frozen=True)
class DispatchContext:
    """The dispatch arm's compiled input (DS-1 §1 ③) — the world-side
    situation one structured scheduling decision is asked about. The
    context is assembled by the spine from the durable rows; the arm
    itself reads nothing.

    ``responders`` is the eligible character vocabulary (id + display
    name, rendered ``id (name)`` — the same identity-contract shape the
    three JSON arms above state); ``user_utterance`` is ``None`` on the
    ``open`` / ``advance`` beats (no words of the user's to read — the
    arm then decides the world event and the pacing only)."""

    world_id: str
    place: str
    current_tick: int
    beat_kind: str
    chapter_goal: str
    situation: str
    user_utterance: str | None
    responders: tuple[str, ...]
    recent_narration: str
    premise: str
    hard_rules: str
    language: str = PROSE_LANGUAGE_DEFAULT
    # -- the chapter's situation plan (DS-3 §6, ③不退化) ---------------------
    # The scheduling input carries the plan; the decision must use it
    # (the 登场 / 逼近 choices stay cross-checkable against the plan's
    # own fields). Empty defaults render no plan block — a legacy
    # blueprint row (the retired test face) keeps today's prompt.
    plan_where: str = ""
    plan_pressing: str = ""
    plan_open_question: str = ""
    plan_pacing: str = ""
    plan_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class DispatchDecision:
    """One structured scheduling decision (DS-1 §1: who responds / the
    order / whether a world event inserts / the pacing) — the parser's
    output shape, consumed by the spine (which owns the execution; the
    arm never acts)."""

    reading: str
    responders: tuple[str, ...]
    world_event: str | None
    pacing: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class CharacterContext:
    """One protagonist's private-seat context (DS-1 §2) — the code-
    assembled context pack: the persona card, the durable profile (the
    private context included — this is that character's OWN seat), the
    retrieved memory (the layered view, recency-truncated), the current
    goal / mood facts, the situation, the event that touches her and
    her own perceivable face (the cognition view — the witness filter's
    physical form). No other participant's private face rides: the pack
    is one character's, and its shape is the door."""

    actor_id: str
    name: str
    identity: str
    personality: str
    background: str
    speech_style: str
    values: str
    boundaries: str
    long_term_drive: str
    current_arc_seed: str
    private_context: str
    goal_mood: str
    memories: V3MemoryView
    place: str
    current_tick: int
    situation: str
    event: str
    perceivable: V3CognitionView
    recent_narration: str
    language: str = PROSE_LANGUAGE_DEFAULT


@dataclass(frozen=True)
class CharacterProposal:
    """One protagonist's structured proposal (DS-1 §1b: the batch
    adjudication's per-character input) — the public face
    (``speech`` / ``action``), the private face (``intent`` /
    ``private_thought``) the adjudicator weighs and the narration never
    sees."""

    actor_id: str
    speech: str
    action: str
    intent: str
    private_thought: str


@dataclass(frozen=True)
class NarrationContext:
    """The narration arm's compiled input (DS-1 §1 ⑦, §12 item 2) — the
    second-person limited knowledge face: the player character's OWN
    cognition / memory views (the witness filter's physical form), the
    committed ruling's public outcome (a reply beat resumes it), the
    responders' **public** face only (speech / action — never an intent
    or a private thought: what ``you`` cannot perceive, the prose cannot
    tell), and the recent narration tail the segment continues from."""

    world_id: str
    player_id: str
    player_name: str
    place: str
    current_tick: int
    beat_kind: str
    player_cognition: V3CognitionView | None
    player_memory: V3MemoryView | None
    committed_outcome: str | None
    committed_actual_action: str | None
    committed_consequences: str | None
    committed_effects: tuple[StateEffect, ...]
    public_proposals: tuple[tuple[str, str, str], ...]
    world_event: str | None
    recent_narration: str
    language: str = PROSE_LANGUAGE_DEFAULT
    # A world beat's own ruling (DS-3 §1 跳①不跳④): the δ that landed
    # for THIS beat — the prose presents it as what happens (a reply's
    # committed_outcome is instead resumed, never re-told). ``None``
    # renders today's prompt (additive, the reply path untouched).
    world_outcome: str | None = None


@dataclass(frozen=True)
class NarrationResult:
    """One narration's answer — the prose beside its structured stop
    markers (DS-1 §4). The markers are the narration arm's own output,
    the stop policy's input; the prose is what the SEGMENT COMMIT
    lands."""

    prose: str
    addresses_you: bool
    impends_on_you: bool
    beat_complete: bool


@dataclass(frozen=True)
class BatchAdjudicationContext:
    """The batch adjudication face's input (DS-1 §1b) — the
    world-authoritative arms are the :class:`ResolverContext`'s own,
    field for field (the reuse the definition names), and the new input
    form rides beside them: the k character proposals and the dispatch
    arm's optional world event. One call synthesizes **one** δ — the
    seven-field :class:`~elc.world.action.Adjudication` unchanged, its
    ``state_effects`` list carrying the multi-effect batch (one claim
    per key; the per-effect gates stay the commit face's)."""

    gate_id: str
    scene_id: str
    submission_id: str
    intent_text: str
    selected_option: str | None
    options: tuple[str, ...]
    bible: BibleRevision | None
    current_facts: tuple[WorldStateFact, ...]
    player_character: PlayerCharacterRecord | None
    place: str
    participants: tuple[str, ...]
    counterparts: tuple[ActorProfileRecord, ...]
    player_cognition: V3CognitionView | None
    player_memory: V3MemoryView | None
    pov_actor_id: str
    cognition: V3CognitionView
    memory: V3MemoryView
    current_tick: int
    proposals: tuple[CharacterProposal, ...]
    world_event: str | None = None


@dataclass(frozen=True)
class SituationPlanContext:
    """The situation planner's compiled input (DS-3, the technical
    definition §6 — the dual-seat chapter's **situation plan**, the
    four-question contract). The context is assembled by the landing
    face from the durable rows; the arm reads nothing. It carries NO
    literary-structure input: no scene count, no four-part architecture,
    no ``dramatic_question`` device, no gate beats, no ``user_present``
    — the plan contract is the world's pressure on one person, nothing
    else (the old blueprint machine is the retired test face).

    ``author_direction`` (the director seat's word, V3-8h's law) rides
    as a soft expectation when present; ``cast_members`` is the
    ``(actor_id, display name)`` vocabulary the plan's identities draw
    on; ``recent_narration`` is the tail the next chapter continues
    from (empty at the opening)."""

    world_id: str
    chapter_index: int
    current_tick: int
    premise: str
    hard_rules: str
    place: str
    recent_narration: str
    cast_members: tuple[tuple[str, str], ...]
    player_id: str
    player_name: str
    author_direction: str | None = None
    language: str = PROSE_LANGUAGE_DEFAULT


@dataclass(frozen=True)
class SituationPlan:
    """One chapter's situation plan (DS-3 §6) — the four questions'
    answers beside the minimal field set, exactly as the definition
    spells them: ①这一幕你在哪（``where_you_stand``）②什么事冲你来
    （``what_presses_on_you`` — 冲着你的压力，不是氛围）③谁对你说第一
    句话（``first_speaker`` ＋ ``first_words``）④第一幕交互悬点
    （``open_question``）；最小字段集——本章世界事件候选（
    ``world_event_candidates``）×你的处境与位置（``place``）×各主角
    目标（``protagonist_goals``）×节奏（``pacing``）与结算预期
    （``settlement_expectation``）."""

    where_you_stand: str
    place: str
    what_presses_on_you: str
    first_speaker: str
    first_words: str
    open_question: str
    world_event_candidates: tuple[str, ...]
    protagonist_goals: tuple[tuple[str, str], ...]
    pacing: str
    settlement_expectation: str


@dataclass(frozen=True)
class WorldAdjudicationContext:
    """A world beat's adjudication input (DS-3 §1, 跳①不跳④) — the
    same world-authoritative read the batch face keeps, minus the user
    submission: no user action rides an ``open`` / ``advance`` beat
    (the user's words are their own); the k character proposals beside
    the dispatch arm's optional world event synthesize ONE δ. The
    seven-field :class:`~elc.world.action.Adjudication` shape verbatim,
    the batch riding ``state_effects``."""

    scene_id: str
    bible: BibleRevision | None
    current_facts: tuple[WorldStateFact, ...]
    place: str
    participants: tuple[str, ...]
    counterparts: tuple[ActorProfileRecord, ...]
    pov_actor_id: str
    cognition: V3CognitionView
    memory: V3MemoryView
    current_tick: int
    proposals: tuple[CharacterProposal, ...]
    world_event: str | None = None


#: The dispatch arm's pacing vocabulary (DS-1 §1 ③) — three words, the
#: parser's enum.
_PACING_WORDS = ("hold", "press", "settle")


#: The narrator's stop-marker tail shape (DS-1 §4): a line containing
#: only ``---`` separates the prose from one JSON object carrying the
#: three marker booleans. The streaming gate holds back this sentinel
#: and everything after it (the tail never flickers onto the page).
_NARRATION_TAIL = re.compile(r"(?m)^---\s*$")

#: The streaming gate's hold-back window: one more character than the
#: sentinel itself, so a sentinel split across two increments is still
#: withheld whole.
_TAIL_HOLD = 5


class _TailGate:
    """The streaming wrapper that keeps the marker tail off the wire:
    increments flow through until the sentinel ``\\n---`` appears in the
    accumulated text; from that point on nothing is emitted (the tail is
    parsed from the outcome's whole text after the call returns)."""

    def __init__(self, on_chunk: Callable[[str], None]) -> None:
        self._on_chunk = on_chunk
        self._buffer = ""
        self._closed = False

    def __call__(self, chunk: str) -> None:
        if self._closed or not chunk:
            return
        self._buffer += chunk
        idx = self._buffer.find("\n---")
        if idx != -1:
            self._closed = True
            head = self._buffer[:idx]
            self._buffer = ""
            if head:
                self._on_chunk(head)
            return
        if len(self._buffer) > _TAIL_HOLD:
            head = self._buffer[: -_TAIL_HOLD]
            self._buffer = self._buffer[-_TAIL_HOLD:]
            self._on_chunk(head)


def _parse_dispatch(text: str, responders: tuple[str, ...]) -> DispatchDecision:
    """One structured scheduling decision (see :class:`DispatchDecision`)
    — shape only; the spine keeps every deeper judgment (the gate
    options' 2–4 bound). The responder vocabulary is matched on the
    **bare id head** (the identity contract: the context renders the
    vocabulary as ``id (name)`` and the answer names the bare id — a
    rendered composite answered back is normalized to its head, the
    same clause the three JSON arms state)."""

    payload = _payload_object(text)
    reading = _text(payload, "reading")
    words = _words(payload, "responders")
    vocabulary = {
        rendered.split(" (", 1)[0].strip() for rendered in responders
    }
    normalized: list[str] = []
    for word in words:
        head = word.split(" (", 1)[0].strip()
        if head not in vocabulary:
            raise LlmProviderError("bad-shape")
        normalized.append(head)
    raw_event = _field(payload, "world_event")
    if raw_event is None:
        world_event = None
    elif isinstance(raw_event, str):
        world_event = raw_event
    else:
        raise LlmProviderError("bad-shape")
    pacing = _field(payload, "pacing")
    if not isinstance(pacing, str) or pacing not in _PACING_WORDS:
        raise LlmProviderError("bad-shape")
    options = _words(payload, "options")
    return DispatchDecision(
        reading=reading,
        responders=tuple(normalized),
        world_event=None if not world_event else world_event,
        pacing=pacing,
        options=options,
    )


#: The situation plan's required non-empty string keys (DS-3 §6): the
#: four questions' six prose answers beside the pacing and the
#: settlement expectation — every one concrete and specific, the
#: machine-checkable face the acceptance pin reads.
_SITUATION_TEXT_KEYS = (
    "where_you_stand",
    "place",
    "what_presses_on_you",
    "first_words",
    "open_question",
    "pacing",
    "settlement_expectation",
)


#: The proposal-fidelity law's sentence per word (DS-3 §1, 面B's
#: 验收面): a world beat's prose may only give a responder the words and
#: deeds that responder's own proposal carries — the narration arm
#: inventing speech or action for a character is the cut's named
#: violation. Stated in the narrator prompt beside the public-face
#: block; the negative-assertion pin reads the sentence.
_PROPOSAL_FIDELITY_SENTENCE = {
    "en": (
        "Every line you give a responder below must be one of their"
        " listed speech / action values — never invent further words,"
        " deeds or reactions for any character beyond the proposals"
        " themselves."
    ),
    "zh": (
        "下文每位回应者的每一句话、每一个动作，都必须出自其列出的"
        " speech / action 值——绝不在提案之外替任何角色发明言语、行为"
        "或反应。"
    ),
}


#: The body sovereignty law's sentence per word (DS-3, the technical
#: definition §12.8 — 二人称叙述只写「你」的感知面：看到/听到/感觉到/
#: 被作用；世界与他人对你做的事可写〔那是世界的行动〕；你的自发行为只能
#: 出自你的输入或留白待你；违约例与合规例照定义原文入 prompt). Replaces
#: the single clause the prompt carried before DS-3 (the negative half
#: alone) — the affirmative perceptual face and the 留白 half ride with
#: it. The word is the prompt's own (the V3-8g wording-law posture).
_SOVEREIGNTY_SENTENCE = {
    "en": (
        "Body sovereignty: write only what the reader's character"
        " PERCEIVES — what they see, hear and feel, and what is done"
        " to them. The world and other people may act on the reader's"
        " character (that is the world's own action); you never decide"
        " the reader's character's own actions, words or emotional"
        " reactions — their spontaneous acts enter the prose only"
        " through their own typed words, or stay unwritten, awaiting"
        ' them. Never write "you hold your breath" or "you move the'
        ' lamp over" — write "the lamp moved over, and the light fell'
        ' across the back of your hand."'
    ),
    "zh": (
        "身体主权：只写「你」的感知面——你看到、听到、感觉到的事，以及"
        "发生在你身上的事。世界与他人可以对你做事（那是世界的行动）；"
        "绝不替你决定你自己的行动、言语或情绪反应——你的自发行为只能"
        "来自你输入的话，否则留白待你。绝不写「你屏住呼吸」「你把灯移"
        "了过去」——要写「灯移了过去，光落在你手背上」。"
    ),
}


def _world_adjudicator_prompt(
    context: WorldAdjudicationContext, *, language: str
) -> str:
    """A world beat's adjudication prompt (DS-3 §1) — the batch face's
    world-authoritative read with NO user submission: the k proposals
    (and the dispatch arm's optional world event) synthesize ONE δ; the
    seven-key shape is the batch prompt's own, verbatim."""

    proposal_lines = [
        f"- {proposal.actor_id}: speech={proposal.speech!r},"
        f" action={proposal.action!r}, intent={proposal.intent!r},"
        f" private_thought={proposal.private_thought!r}"
        for proposal in context.proposals
    ]
    lines = [
        "You are the resolver of a two-seat story world: NO user action",
        "rides this beat — the world pressed forward and the characters",
        "present answered with their own proposals; you synthesize ONE",
        "authoritative outcome — what actually happens. Answer with one",
        "JSON object and nothing else, carrying exactly these keys.",
        _JSON_PROSE_LINE[_prose_language_word(language)],
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        '- "interpretation": one JSON string — what this beat is (the',
        "  world's move, one sentence).",
        '- "outcome": one JSON string — what actually happens, as world',
        "  fact (weighing the proposals AND the world's own pressure).",
        '- "actual_action": one JSON string — the action that actually',
        "  unfolds.",
        '- "consequences": one JSON string — what changes because of it.',
        '- "state_effects": a JSON array of {"key": <one JSON string>,',
        '  "statement": <one JSON string>} objects — the BATCH: one',
        "  object per changed fact (dotted keys such as a place fact or",
        "  one character's mood / goal), never the same key twice; an",
        "  empty array when nothing changes.",
        '- "participants": a JSON array of participant identity strings',
        "  the outcome is about — the ids this prompt lists.",
        '- "replan_scope": exactly "NONE" — a world beat lands no replan',
        "  obligation (the situation plan absorbs the pressure at the",
        "  next chapter).",
        "",
        "Hard rules:",
        "- The proposals are the characters' own attempts, not facts:",
        "  you weigh them against the world's real rules, its physics",
        "  and the participants' abilities and limits — a proposal the",
        "  world refuses simply does not happen.",
        "- No user character acts this beat: the reader's own character",
        "  is present and perceives, but nothing in the outcome may",
        "  decide, speak or act for them.",
        "- Rule by the world authority below; a soft expectation is",
        "  never a condition.",
        "",
        "The world authority:",
        "- Bible (the world's rules and setting):",
        _render_bible(context.bible),
        "- settled facts (the current world state):",
        _render_facts(context.current_facts),
        f"- place: {context.place}",
        f"- participants: {', '.join(context.participants)}",
        "- the scene's counterpart profiles:",
        _render_profiles(context.counterparts),
        "",
        "The responders' proposals (their own attempts, private faces",
        "included — you weigh all of it; the story never narrates an",
        "intent or a private thought):",
        _render_list(proposal_lines),
    ]
    if context.world_event:
        lines.extend(
            [
                "A world event inserts itself this beat (already decided):",
                f"- {context.world_event!r}",
            ]
        )
    lines.extend(
        [
            "",
            f"current_tick: {context.current_tick}",
        ]
    )
    return "\n".join(lines)


def _parse_situation_plan(
    text: str,
    cast_members: tuple[tuple[str, str], ...],
    player_id: str = "",
) -> SituationPlan:
    """One chapter's situation plan (see :class:`SituationPlan`) — the
    four questions answered concretely and the minimal field set filled.
    ``first_speaker`` obeys the identity contract (the bare id token
    from the listed vocabulary); ``protagonist_goals`` must cover every
    listed CAST character (各主角目标 — a goalless protagonist is a
    hole in the plan, not an empty map entry). The reader's own
    character is NOT a plan protagonist (their goals are theirs to
    play, not the world's to schedule — 身体主权同源): the prompt says
    so, and because a real model still names the player among the
    listed ids (the 2026-10-15 smoke specimens did, ~always), an entry
    keyed by ``player_id`` is accepted and DROPPED here — every other
    unknown id stays ``bad-shape`` (fail-closed)."""

    payload = _payload_object(text)
    values: dict[str, str] = {}
    for key in _SITUATION_TEXT_KEYS:
        value = _text(payload, key)
        if not value.strip():
            raise LlmProviderError("bad-shape")
        values[key] = value
    vocabulary = {actor_id for actor_id, _name in cast_members}
    raw_speaker = _text(payload, "first_speaker")
    speaker = raw_speaker.split(" (", 1)[0].strip()
    if speaker not in vocabulary:
        raise LlmProviderError("bad-shape")
    candidates = _words(payload, "world_event_candidates")
    if not candidates or any(not word.strip() for word in candidates):
        raise LlmProviderError("bad-shape")
    raw_goals = _field(payload, "protagonist_goals")
    if not isinstance(raw_goals, Mapping):
        raise LlmProviderError("bad-shape")
    goals: list[tuple[str, str]] = []
    for actor_id, goal in raw_goals.items():
        head = str(actor_id).split(" (", 1)[0].strip()
        if head == player_id:
            continue
        if head not in vocabulary:
            raise LlmProviderError("bad-shape")
        if not isinstance(goal, str) or not goal.strip():
            raise LlmProviderError("bad-shape")
        goals.append((head, goal))
    if {actor_id for actor_id, _goal in goals} != vocabulary:
        raise LlmProviderError("bad-shape")
    return SituationPlan(
        where_you_stand=values["where_you_stand"],
        place=values["place"],
        what_presses_on_you=values["what_presses_on_you"],
        first_speaker=speaker,
        first_words=values["first_words"],
        open_question=values["open_question"],
        world_event_candidates=tuple(candidates),
        protagonist_goals=tuple(goals),
        pacing=values["pacing"],
        settlement_expectation=values["settlement_expectation"],
    )


def _parse_proposal(text: str, actor_id: str) -> CharacterProposal:
    """One character proposal — the four contract strings; a
    ``private_thought`` answered as JSON ``null`` rides the honest empty
    string (the field is optional in spirit, never absent in shape)."""

    payload = _payload_object(text)
    speech = _text(payload, "speech")
    action = _text(payload, "action")
    intent = _text(payload, "intent")
    raw_private = _field(payload, "private_thought")
    if raw_private is None:
        private = ""
    elif isinstance(raw_private, str):
        private = raw_private
    else:
        raise LlmProviderError("bad-shape")
    return CharacterProposal(
        actor_id=actor_id,
        speech=speech,
        action=action,
        intent=intent,
        private_thought=private,
    )


def _parse_narration(text: str) -> NarrationResult:
    """One narration answer: the prose before the sentinel line, the
    three marker booleans from the JSON tail after it. No sentinel is
    ``missing-field:markers`` — the tail is the stop law's input, never
    guessed; prose before it keeps one fence's worth of cleaning (the
    parsing law's own minimal form)."""

    cleaned = _clean(text)
    parts = _NARRATION_TAIL.split(cleaned, maxsplit=1)
    if len(parts) != 2:
        raise LlmProviderError("missing-field:markers")
    prose = parts[0].strip()
    if not prose:
        raise LlmProviderError("no-output")
    payload = _payload_object(parts[1])
    markers = []
    for name in ("addresses_you", "impends_on_you", "beat_complete"):
        value = _field(payload, name)
        if not isinstance(value, bool):
            raise LlmProviderError("bad-shape")
        markers.append(value)
    return NarrationResult(
        prose=prose,
        addresses_you=markers[0],
        impends_on_you=markers[1],
        beat_complete=markers[2],
    )


def pack_memories(view: V3MemoryView, cap: int) -> V3MemoryView:
    """The character pack's memory retrieval (DS-1 §2 F5, the POC-grade
    policy — marked adjustable): the layered view is already the
    presence filter (a viewer's own rows only — 亲历或听闻 by
    construction), so this face applies the **recency truncation**
    alone: keep the ``cap`` most recent rows (``learned_at_tick`` then
    ``memory_id``), re-presented in the view's own layer order. The
    salience scoring is a later blade (the lunar greedy-packing
    design); ``cap <= 0`` answers the honest empty view."""

    if cap <= 0 or not view.memories:
        return V3MemoryView(viewer_id=view.viewer_id, memories=())
    ranked = sorted(
        view.memories,
        key=lambda row: (row.learned_at_tick, row.memory_id),
    )
    kept = set(ranked[-cap:])
    return V3MemoryView(
        viewer_id=view.viewer_id,
        memories=tuple(row for row in view.memories if row in kept),
    )


def _render_card(context: CharacterContext) -> str:
    """One protagonist's persona card as the private seat reads it."""

    return "\n".join(
        [
            f"- name: {context.name}",
            f"- identity: {context.identity!r}",
            f"- personality: {context.personality!r}",
            f"- background: {context.background!r}",
            f"- speech_style: {context.speech_style!r}",
            f"- values: {context.values!r}",
            f"- boundaries: {context.boundaries!r}",
            f"- long_term_drive: {context.long_term_drive!r}",
            f"- current_arc_seed: {context.current_arc_seed!r}",
            f"- private_context: {context.private_context!r}",
        ]
    )


#: The dispatch arm's situation-plan block (DS-3 §6, ③不退化): the
#: scheduling input carries the chapter's situation plan and the
#: decision must use it — the 登场 / 逼近 choices stay cross-checkable
#: against the plan's own fields. Rendered only when the compiled
#: context carries a plan (a legacy blueprint row renders no block).
_DISPATCH_PLAN_SENTENCE = (
    "Your decision must move this plan: choose the world event and"
    " the responders so the plan's pressure visibly advances — a"
    " reading that cannot name which part of the plan it advances is"
    " a wasted beat."
)


def _dispatch_prompt(context: DispatchContext) -> str:
    """The dispatch arm's prompt (DS-1 §1 ③) — one structured scheduling
    decision; the intent reading rides the same answer (the light-tier
    single call the probe informed)."""

    lines = [
        "You are the dispatcher of a two-seat story world: the code",
        "spine owns the turn and asks you for ONE structured scheduling",
        "decision. Answer with one JSON object and nothing else.",
        _JSON_PROSE_LINE[_prose_language_word(context.language)],
        "",
        "The object's keys (all required; keys beyond them are ignored).",
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        '- "reading": one JSON string — how this beat\'s words land in',
        "  the scene (one sentence; with no user words, what the world",
        "  is doing).",
        '- "responders": a JSON array of the character ids that respond',
        "  this beat, in the order they should respond — taken only from",
        "  the ids listed below; an empty array means nobody speaks.",
        '- "world_event": one JSON string or null — one small world',
        "  event to insert now, or null for none.",
        '- "pacing": exactly one of "hold" | "press" | "settle" — hold',
        "  the beat where it stands, press the situation forward, or",
        "  settle toward a quiet close.",
        '- "options": a JSON array of 2-4 short natural actions the',
        "  user's own character could take next (never plot outlines).",
        "",
        f"World: {context.world_id}, place: {context.place},",
        f"current_tick: {context.current_tick}, beat: {context.beat_kind}",
        "Chapter's goal (a soft expectation, never a condition):",
        f"- {context.chapter_goal}",
    ]
    if (
        context.plan_pressing
        or context.plan_where
        or context.plan_candidates
        or context.plan_open_question
        or context.plan_pacing
    ):
        lines.extend(
            [
                "The chapter's situation plan (the four questions — the",
                "world's pressure on the reader's character):",
                f"- where they stand: {context.plan_where}",
                f"- what presses on them: {context.plan_pressing}",
                f"- the act's open question: {context.plan_open_question}",
                f"- the pacing note: {context.plan_pacing}",
                "- world events that may close in (advance one of these,",
                "  or what the pressing event does next — never ignore",
                "  them):",
            ]
        )
        lines.extend(
            f"  - {candidate}" for candidate in context.plan_candidates
        )
        lines.append(f"- {_DISPATCH_PLAN_SENTENCE}")
    lines.extend(
        [
            "World premise:",
            f"- {context.premise}",
            "The world's hard rules:",
            f"- {context.hard_rules}",
            "The scene right now:",
            f"- {context.situation}",
        ]
    )
    if context.user_utterance is not None:
        lines.extend(
            [
                "The user's own words (never a world fact — read them,",
                " do not extend them):",
                f"- {context.user_utterance!r}",
            ]
        )
    else:
        lines.append("- no user words this beat (an open / advance beat).")
    lines.extend(
        [
            "",
            "Eligible responder ids (the identity vocabulary):",
            _render_list(list(context.responders)),
            "",
            "The narration so far (its tail):",
            _render_list([context.recent_narration])
            if context.recent_narration
            else "- (nothing narrated yet)",
        ]
    )
    return "\n".join(lines)


#: The situation plan's structural ban (DS-3 §6) — the sentence that
#: keeps the old blueprint machine's 章法 out of the product path's plan:
#: no literary architecture, no gate beats, no ``user_present``, no
#: dramatic-question device. Per word (the V3-8g wording-law posture).
_SITUATION_BAN_SENTENCE = {
    "en": (
        "This plan carries NO literary structure: no scene count, no"
        " four-part architecture, no atmosphere-first opening, no"
        ' "dramatic question" device, no planned gates, no'
        ' "user_present" flag. The plan is the world\'s pressure on one'
        " person — where they stand, what bears down on them, who"
        " speaks to them first, what stays unresolved — nothing else."
    ),
    "zh": (
        "本计划不含任何文学结构：不写场数、不写四段式章法、不写氛围"
        "开场、不写「戏剧之问」那一套、不排门拍、不写 user_present。"
        "计划就是世界压在一个人的身上的样子——你在哪、什么事冲你来、"
        "谁对你开口、什么悬而未决——仅此而已。"
    ),
}


def _situation_plan_prompt(context: SituationPlanContext) -> str:
    """The situation planner's prompt (DS-3 §6) — the dual-seat chapter
    planned as a SITUATION: the four questions answered concretely
    beside the minimal field set; the structural ban stated in the
    prompt's own language. One call, one JSON object (F9's posture)."""

    members = [
        f"{actor_id} ({name})" if name else actor_id
        for actor_id, name in context.cast_members
    ]
    standing = (
        context.place
        or "(nothing has happened yet — this is the opening)"
    )
    lines = [
        "You are the situation planner of a two-seat story world: the",
        "code spine asks you to plan ONE chapter as a SITUATION — the",
        "world's pressure on the reader's character. Answer with one",
        "JSON object and nothing else.",
        _JSON_PROSE_LINE[_prose_language_word(context.language)],
        "",
        "The object's keys (all required).",
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        "",
        "The four questions (every answer concrete and specific — a",
        "real place, a real event, real words; never atmosphere alone):",
        '- "where_you_stand": where the reader\'s character is and what',
        "  situation they stand in when this chapter opens (concretely,",
        "  on the spot).",
        '- "place": one short location phrase (the scene\'s place tag).',
        '- "what_presses_on_you": the event this chapter that bears',
        "  down on the reader's character — pressure aimed AT them,",
        "  never mere mood or ambience.",
        '- "first_speaker": the character id of whoever speaks the',
        "  first words TO the reader's character — from the ids listed",
        "  below only (never the reader's own character).",
        '- "first_words": those first words themselves, addressed to',
        "  the reader's character.",
        '- "open_question": the unresolved question left hanging on the',
        "  reader's character when this chapter's first act closes.",
        "",
        "The situation's minimal fields:",
        '- "world_event_candidates": a JSON array of 1-4 concrete world',
        "  events that may close in this chapter (each one sentence).",
        '- "protagonist_goals": a JSON object — EVERY listed CAST',
        "  character id maps to what they are trying to do this",
        "  chapter. The reader's own character is NEVER a key here",
        "  (their goals are theirs to play, not the plan's to set).",
        '- "pacing": one short sentence — how the pressure should move.',
        '- "settlement_expectation": one short sentence — what this',
        "  chapter's closing settlement should take stock of.",
        "",
        _SITUATION_BAN_SENTENCE[_prose_language_word(context.language)],
        "",
        f"World: {context.world_id}, chapter {context.chapter_index},",
        f"current_tick: {context.current_tick}.",
        "World premise:",
        f"- {context.premise}",
        "The world's hard rules:",
        f"- {context.hard_rules}",
        f"Where the world stands now: {standing}",
    ]
    if context.author_direction:
        lines.extend(
            [
                _AUTHOR_DIRECTION_SENTENCE[
                    _prose_language_word(context.language)
                ],
                "The direction:",
                f"- {context.author_direction!r}",
            ]
        )
    lines.extend(
        [
            "",
            "The cast (the identity vocabulary — ids with display names):",
            _render_list(members),
            f"The reader's own character: {context.player_name}"
            f" ({context.player_id}) — never the first_speaker and"
            " never a protagonist_goals key.",
            "",
            "The narration so far (its tail):",
            _render_list([context.recent_narration])
            if context.recent_narration
            else "- (nothing narrated yet — this is the opening)",
        ]
    )
    return "\n".join(lines)


def _character_prompt(context: CharacterContext) -> str:
    """The character arm's prompt (DS-1 §2) — the private seat's
    proposal: the character's own card, memory, goal / mood, situation,
    the touching event and her own perceivable face; nothing of any
    other participant's private face."""

    return "\n".join(
        [
            "You are one character of a two-seat story world, in your own",
            "private seat: propose how you respond — never decide for",
            "anyone else, never decide the outcome. Answer with one JSON",
            "object and nothing else.",
            _JSON_PROSE_LINE[_prose_language_word(context.language)],
            "",
            "The object's keys (all required).",
            _PROSE_TYPE_SENTENCE,
            '- "speech": one JSON string — what you say, in your own',
            "  voice (may be empty when you say nothing).",
            '- "action": one JSON string — what you visibly do.',
            '- "intent": one JSON string — what you are actually trying',
            "  to do (private; the judge reads it, the story never",
            "  narrates it).",
            '- "private_thought": one JSON string — your private thought',
            "  in this moment (private; may be empty).",
            "",
            "Your card:",
            _render_card(context),
            "",
            f"Where you are: {context.place}, current_tick"
            f" {context.current_tick}.",
            f"The situation right now: {context.situation}",
            "The event that touches you:",
            f"- {context.event}",
            "What you can perceive (your own witnessed face — the whole",
            " of what this proposal may draw on):",
            _render_cognition(context.perceivable),
            "",
            "Your own memory (most recent first by layer):",
            _render_memory(pack_memories(context.memories, _MEMORY_CAP)),
            "",
            "The narration so far (its tail):",
            _render_list([context.recent_narration])
            if context.recent_narration
            else "- (nothing narrated yet)",
        ]
    )


#: The character pack's memory cap (DS-1 §2 F5: 「建议 ≤24 条」) — the
#: recency truncation the prompt's own read applies.
_MEMORY_CAP = 24


def _narrator_prompt(context: NarrationContext) -> str:
    """The narration arm's prompt (DS-1 §1 ⑦, §12 item 2) — second
    person, the player's own limited knowledge, the responders' public
    face only; the answer is prose, then the sentinel line, then the
    three stop-marker booleans (§4)."""

    if context.committed_outcome is not None:
        event_block = [
            "The committed ruling this segment resumes (already canon —",
            "carry the story past it, never re-tell it):",
            f"- outcome: {context.committed_outcome!r}",
            f"- actual_action: {context.committed_actual_action!r}",
            f"- consequences: {context.committed_consequences!r}",
        ]
    elif context.world_outcome is not None:
        event_block = [
            "What actually happens this beat (the world's own ruling —",
            "already canon; present it as what happens, through the",
            "reader's character's own perceivable face below, and never",
            "contradict it):",
            f"- outcome: {context.world_outcome!r}",
        ]
    else:
        event_block = [
            "No committed ruling rides this beat — write what the world",
            "does next from the perceivable face below.",
        ]
    proposals = [
        f"- {actor_id}: speech={speech!r}, action={action!r}"
        for actor_id, speech, action in context.public_proposals
    ]
    lines = [
        "You are the narrator of a two-seat story world. Write in",
        f"SECOND PERSON: the reader IS {context.player_name}"
        f" ({context.player_id}) — every paragraph addresses them as",
        '"you", and presents only what they can perceive, know or',
        "remember (their own limited-knowledge face below is the whole",
        "of what may be presented as known; another person's intent or",
        "private thought never enters the prose).",
        _SOVEREIGNTY_SENTENCE[_prose_language_word(context.language)],
        f"{_WRITER_PROSE_LINE[_prose_language_word(context.language)]}",
        f"- {_CONTINUITY_SENTENCE}",
        "",
        "Answer shape: the prose (3-8 sentences), then a line containing",
        "only ---, then one JSON object and nothing after it:",
        '{"addresses_you": <bool>, "impends_on_you": <bool>,'
        ' "beat_complete": <bool>}',
        "- addresses_you: someone has just addressed the reader's",
        "  character and awaits their reply.",
        "- impends_on_you: something is about to demand the reader's",
        "  own decision.",
        "- beat_complete: this beat's arc is complete (true only when",
        "  neither marker above is true).",
        "",
        f"World: {context.world_id}, place: {context.place}, current_tick",
        f"{context.current_tick}, beat: {context.beat_kind}.",
        *event_block,
        "The responders' public face (speech and visible action only):",
        _render_list(proposals),
        _PROPOSAL_FIDELITY_SENTENCE[_prose_language_word(context.language)],
    ]
    if context.world_event:
        lines.extend(
            [
                "A world event inserts itself (already decided — present",
                " it as what happens):",
                f"- {context.world_event!r}",
            ]
        )
    lines.extend(
        [
            "",
            f"What {context.player_name} knows (cognition):",
            "(no player-side knowledge arm rides — the world declares no"
            " player character)"
            if context.player_cognition is None
            or context.player_memory is None
            else _render_cognition(context.player_cognition),
            "",
            f"What {context.player_name} remembers:",
            _render_memory(context.player_memory)
            if context.player_memory is not None
            else "- (nothing)",
            "",
            "The narration so far (its tail — continue from it):",
            _render_list([context.recent_narration])
            if context.recent_narration
            else "- (nothing narrated yet)",
        ]
    )
    return "\n".join(lines)


def _batch_adjudicator_prompt(
    context: BatchAdjudicationContext, *, language: str
) -> str:
    """The batch adjudication face's prompt (DS-1 §1b) — the
    world-authoritative read of the resolver arm, with the k proposals
    and the user's event beside it: ONE ruling, the seven-field shape
    verbatim, the batch riding ``state_effects``."""

    if context.player_character is None:
        player_block = "(no player character is declared for this world)"
    else:
        player = context.player_character
        player_block = (
            f"{player.player_character_id} ({player.name}):"
            f" abilities={player.abilities!r}, limits={player.limits!r}"
        )
    if context.player_cognition is None or context.player_memory is None:
        knows_block = (
            "(no player-side knowledge arm rides — the world declares no"
            " player character)"
        )
    else:
        knows_block = (
            "cognition:\n"
            f"{_render_cognition(context.player_cognition)}\n"
            "memory:\n"
            f"{_render_memory(context.player_memory)}"
        )
    proposal_lines = [
        f"- {proposal.actor_id}: speech={proposal.speech!r},"
        f" action={proposal.action!r}, intent={proposal.intent!r},"
        f" private_thought={proposal.private_thought!r}"
        for proposal in context.proposals
    ]
    lines = [
        "You are the resolver of a two-seat story world: the user took",
        "an action and the responding characters answered with their own",
        "proposals; you synthesize ONE authoritative outcome — what",
        "actually happens. Answer with one JSON object and nothing",
        "else, carrying exactly these keys.",
        _JSON_PROSE_LINE[_prose_language_word(language)],
        _PROSE_TYPE_SENTENCE,
        _IDENTITY_SENTENCE,
        '- "interpretation": one JSON string — what the user\'s action',
        "  means in this world (a reading of the user's intent, never",
        "  an invented intention).",
        '- "outcome": one JSON string — what actually happens, as world',
        "  fact (weighing the user's action AND the proposals).",
        '- "actual_action": one JSON string — the action that actually',
        "  unfolds.",
        '- "consequences": one JSON string — what changes because of it.',
        '- "state_effects": a JSON array of {"key": <one JSON string>,',
        '  "statement": <one JSON string>} objects — the BATCH: one',
        "  object per changed fact (dotted keys such as a place fact or",
        "  one character's mood / goal), never the same key twice; an",
        "  empty array when nothing changes.",
        '- "participants": a JSON array of participant identity strings',
        "  the outcome is about — the ids this prompt lists; it MUST",
        "  carry the player character's id.",
        '- "replan_scope": exactly one of "NONE" | "SCENE" | "CHAPTER" —',
        "  whether the situation plan must be revised.",
        "",
        "Hard rules:",
        "- The user's words are an intent, not a world fact: never",
        "  extend, upgrade or invent them — decide what happens, not",
        "  what they meant beyond the words given.",
        "- The proposals are the characters' own attempts, not facts:",
        "  you weigh them against the world's real rules, its physics",
        "  and the participants' abilities and limits — a proposal the",
        "  world refuses simply does not happen.",
        "- Rule by the world authority below; a soft expectation is",
        "  never a condition.",
        "",
        "The world authority:",
        "- Bible (the world's rules and setting):",
        _render_bible(context.bible),
        "- settled facts (the current world state):",
        _render_facts(context.current_facts),
        f"- place: {context.place}",
        f"- participants: {', '.join(context.participants)}",
        "- the player character (abilities / limits):",
        f"  {player_block}",
        "- the scene's counterpart profiles:",
        _render_profiles(context.counterparts),
        "- what the user's character knows (the authority for what the",
        "  user knows):",
        f"  {knows_block}",
        "",
        "The responders' proposals (their own attempts, private faces",
        "included — you weigh all of it; the story never narrates an",
        "intent or a private thought):",
        _render_list(proposal_lines),
    ]
    if context.world_event:
        lines.extend(
            [
                "A world event inserts itself this beat (already decided):",
                f"- {context.world_event!r}",
            ]
        )
    lines.extend(
        [
            "",
            "The user's own submission (durable, never an invention):",
            f"- intent_text: {context.intent_text!r}",
            f"- selected_option: {context.selected_option!r}",
            f"- options: {', '.join(context.options)}",
            f"- current_tick: {context.current_tick}",
        ]
    )
    return "\n".join(lines)


class LlmDispatcherProvider:
    """The dispatch arm (DS-1 §1 ③, the director agent's structured
    scheduling decision) over one :class:`TextCompletion` seam — one
    call, one decision; the spine owns every execution (F9: no
    tool-calling loop, no execution power on the arm)."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def decide(self, context: DispatchContext) -> DispatchDecision:
        """One structured scheduling decision (see the class
        docstring)."""

        return _parse_dispatch(
            _complete_text(
                self._completion, _dispatch_prompt(context)
            ),
            context.responders,
        )


class LlmCharacterProvider:
    """The character arm (DS-1 §2) over one :class:`TextCompletion`
    seam — one private seat's proposal per call; the k-parallel
    dispatch is the spine's (:meth:`TurnEngine` in ``elc.world.turns``),
    never this class's."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def propose(self, context: CharacterContext) -> CharacterProposal:
        """One private seat's proposal (see the class docstring); the
        answer's ``actor_id`` is the context's own — the pack was
        compiled for exactly this character."""

        return _parse_proposal(
            _complete_text(
                self._completion,
                _character_prompt(context),
            ),
            context.actor_id,
        )


class LlmNarratorProvider:
    """The narration arm (DS-1 §1 ⑦, §12 item 2) over one
    :class:`TextCompletion` seam — the second-person limited-knowledge
    prose, streamed through the re-opened
    :class:`StreamingTextCompletion` face when the seam carries it
    (the marker tail is withheld from the wire by :class:`_TailGate`)
    and blocking otherwise. The four original arms' signatures stay
    byte for byte (the bypass channel, F15)."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def render(
        self,
        context: NarrationContext,
        *,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NarrationResult:
        """One narration answer (see the class docstring); ``on_chunk``
        receives the prose increments as they arrive (never the marker
        tail) when the seam streams, and is ignored when it does not."""

        prompt = _narrator_prompt(context)
        if on_chunk is not None and isinstance(
            self._completion, StreamingTextCompletion
        ):
            outcome = self._completion.complete_streaming(
                prompt, _TailGate(on_chunk)
            )
            if outcome.error is not None:
                raise LlmProviderError(_seam_code(outcome.error))
            if outcome.text is None:
                raise LlmProviderError("no-output")
            text = outcome.text
        else:
            text = _complete_text(self._completion, prompt)
        return _parse_narration(text)


class LlmBatchAdjudicatorProvider:
    """The batch adjudication face (DS-1 §1b) over one
    :class:`TextCompletion` seam — the k proposals + the user's event →
    ONE ruling in the :class:`~elc.world.action.Adjudication` shape
    verbatim (the seven fields; the batch rides ``state_effects``); the
    commit chain's three checks stay
    :func:`elc.world.action.commit_action`'s, downstream."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def adjudicate(
        self, context: BatchAdjudicationContext
    ) -> Adjudication:
        """The one synthesized ruling (see the class docstring)."""

        return _parse_adjudication(
            _complete_text(
                self._completion,
                _batch_adjudicator_prompt(
                    context, language=self._language
                ),
            )
        )

    def adjudicate_world(
        self, context: WorldAdjudicationContext
    ) -> Adjudication:
        """A world beat's one synthesized δ (DS-3 §1 跳①不跳④) — the
        same seven-field shape, no user submission in the read."""

        return _parse_adjudication(
            _complete_text(
                self._completion,
                _world_adjudicator_prompt(
                    context, language=self._language
                ),
            )
        )


class LlmSituationPlannerProvider:
    """The situation planner arm (DS-3, the technical definition §6 —
    the dual-seat chapter's planning face, the director agent's
    situation contract) over one :class:`TextCompletion` seam — one
    call, one four-question plan; the structural ban and the identity
    contract ride the prompt (F9: a structured single call, never a
    tool-calling loop). The old blueprint machine
    (:class:`LlmDirectorProvider` + the literary schema) stays the
    retired test face; the /ds product path plans through this arm."""

    def __init__(
        self,
        completion: TextCompletion,
        language: str = PROSE_LANGUAGE_DEFAULT,
    ) -> None:
        self._completion = completion
        self._language = language

    def plan(self, context: SituationPlanContext) -> SituationPlan:
        """One chapter's situation plan (see the class docstring)."""

        return _parse_situation_plan(
            _complete_text(
                self._completion, _situation_plan_prompt(context)
            ),
            context.cast_members,
            player_id=context.player_id,
        )
