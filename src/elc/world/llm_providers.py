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
streaming face (``complete_streaming(prompt, on_chunk)``) is the
registered extension point for a later cut — deliberately not
implemented here (the reading face's UX may re-open it explicitly).

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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from elc.world.action import Adjudication, ReplanScope
from elc.world.types import StateEffect

if TYPE_CHECKING:  # the annotation-only edges (same-package contexts)
    from elc.world.bible import BibleRevision
    from elc.world.cast import ActorProfileRecord
    from elc.world.cognition import V3CognitionView
    from elc.world.director import (
        DirectorCastMember,
        DirectorContext,
        DirectorPlayerCharacter,
    )
    from elc.world.memory import V3MemoryView
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
    "CompletionOutcome",
    "LlmDirectorProvider",
    "LlmPlannerProvider",
    "LlmProviderError",
    "LlmResolverProvider",
    "LlmWriterProvider",
    "TextCompletion",
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
    carries ``purpose`` beside them)."""

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
        "",
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
