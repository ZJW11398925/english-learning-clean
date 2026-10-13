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
second schema). The library faces downstream (the Director's schema,
the ``_checked_fields`` family, ``commit_action``) keep every deeper
judgment — the parser blesses a payload's *shape*, never its content.

**Failure semantics** — the V3 Protocol face (``providers.py``, sealed)
has no Result channel, so a real provider's runtime failure escapes as
:class:`LlmProviderError` (a module-owned ``Exception`` carrying a
short body-free ``reason``; the persona ``ProviderOutput`` reason-code
style: ``transport-error`` / ``no-output`` / ``bad-payload`` /
``missing-field:<name>`` / ``bad-shape``). The seam's own ``error``
value is relayed as the code only — never its free text, which could
echo a prompt. This is the runtime-error posture, the fake's honest
``ValueError`` being the programmer-error one; the caller (the drive /
the reading face) owns converting the exception into its Err / HTTP
answer. No message ever carries the prompt or a prompt fragment.

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

    ``reason`` is one short code: ``transport-error`` (the seam
    answered an ``error`` value), ``no-output`` (an empty answer or a
    missing ``text``), ``bad-payload`` (not a JSON object), ``bad-shape``
    (a wrong type or an out-of-vocabulary word) or
    ``missing-field:<name>`` (a required key absent; nested coordinates
    read ``scenes[0].place`` — the Director schema's own language). The
    message is the code alone: the prompt, and anything a transport
    might have echoed, never rides through.
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

#: The Blueprint scene element's text keys (the ten-key canonical set
#: minus the identity pair and the tick).
_BLUEPRINT_SCENE_TEXT_KEYS = ("purpose", *_PLAN_ELEMENT_TEXT_KEYS)

#: The chapter's own text fields (§26.2.1's nine minus the ticks and
#: ``scenes``).
_BLUEPRINT_TEXT_KEYS = (
    "goal",
    "dramatic_question",
    "closing_pressure",
    "desired_development",
    "soft_outcomes",
    "chapter_questions_to_advance",
)

#: The ruling's three-word plan verdict, as the parser's vocabulary.
_REPLAN_SCOPE_WORDS: dict[str, ReplanScope] = {
    "NONE": ReplanScope.NONE,
    "SCENE": ReplanScope.SCENE,
    "CHAPTER": ReplanScope.CHAPTER,
}


def _complete_text(completion: TextCompletion, prompt: str) -> str:
    """One seam call, the failure arms first: a seam ``error`` is the
    body-free ``transport-error``; a missing ``text`` is ``no-output``."""

    outcome = completion.complete(prompt)
    if outcome.error is not None:
        raise LlmProviderError("transport-error")
    if outcome.text is None:
        raise LlmProviderError("no-output")
    return outcome.text


def _clean(text: str) -> str:
    """The deterministic minimal cleaning (see the module docstring):
    strip the surrounding whitespace, then remove one fence wrapper —
    a first line that is exactly a code fence (optionally tagged) and a
    bare closing fence on the last line. Nothing else is reinterpreted;
    a fence that does not fit the rule rides on to the parser and
    fails there."""

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
    value = _field(payload, name, coordinate=coordinate)
    if not isinstance(value, str):
        raise LlmProviderError("bad-shape")
    return value


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


def _writer_prompt(context: PovContext) -> str:
    """The Writer arm's prompt (see the class docstring): the POV-safe
    context is all this assembly may read — the compiled object is the
    hard door, and no face it does not carry can ride into the prompt."""

    lines = [
        "You are the POV writer for ONE segment of an interactive story",
        "world. Write the segment's prose in English.",
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


def _planner_prompt(context: ScenePlanContext) -> str:
    """The Planner arm's prompt for a fresh scene plan — the POV-safe
    scene context and nothing else."""

    return _scene_plan_prompt(context, replan=False)


def _planner_replan_prompt(context: ScenePlanContext) -> str:
    """The Planner arm's prompt for the SCENE replan — the current
    element is the content the revision starts from."""

    return _scene_plan_prompt(context, replan=True)


def _scene_plan_prompt(context: ScenePlanContext, *, replan: bool) -> str:
    """The shared scene-plan prompt body: the scene's identity, the
    current plan content and the POV's own cognition / memory; the
    answer is one JSON object in the element's own nine-key shape."""

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
        "",
        "The object's keys (all required; keys beyond them are ignored):",
        '- "pov_actor_id": the scene\'s one point-of-view character — a',
        "  participant identity string, and a member of the participants",
        '- "participants": an array of participant identity strings',
        '- "planned_start_tick": an integer story tick',
        '- "place": where the scene happens',
        '- "entry_goals": what the scene opens toward',
        '- "exit_condition": the condition under which the scene closes',
        '- "elasticity": how far the scene may stretch',
        '- "revealable": what may be revealed, once it is earned',
        '- "must_hide": the hard prohibitions — what must NOT be revealed',
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


def _director_prompt(context: DirectorPlanContext) -> str:
    """The Director arm's prompt for the initial chapter plan — the
    full ``DirectorContext`` and nothing else (the chapter plan is the
    world's, not one character's)."""

    return _blueprint_prompt(context, replan=False)


def _director_replan_prompt(context: DirectorPlanContext) -> str:
    """The Director arm's prompt for the CHAPTER replan — the committed
    ruling that invalidated the plan and the current Blueprint the
    revision starts from."""

    return _blueprint_prompt(context, replan=True)


def _blueprint_prompt(context: DirectorPlanContext, *, replan: bool) -> str:
    """The shared Blueprint prompt body: the world-authoritative
    ``DirectorContext`` reading, the wording law, the payload's own
    schema (nine chapter fields; ten-key scene elements) — plus, on the
    replan arm, the triggering ruling and the current Blueprint."""

    director_context: DirectorContext = context.director_context
    lines = [
        "You are the world director of an interactive story world. Plan",
        "ONE chapter and answer with one JSON object and nothing else.",
        "",
        "The object's chapter fields (all required):",
        '- "goal": what the chapter sets out to reach',
        '- "dramatic_question": the question the chapter presses',
        '- "planned_start_tick" / "planned_end_tick": the planned story',
        "  window (integers; the end never before the start)",
        '- "closing_pressure": where the chapter presses at its close',
        '- "desired_development": the development it works toward',
        '- "soft_outcomes": the shape of an outcome it reaches toward',
        '- "chapter_questions_to_advance": the questions it advances',
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
        "(one POV per scene).",
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


def _resolver_prompt(context: ResolverContext) -> str:
    """The Resolver arm's prompt — the world-authoritative context: the
    Bible, the settled facts, the player's profile, the counterparts,
    the scene's place and participants, the **player character's own**
    knowledge arms (``player_cognition`` / ``player_memory`` — the
    authority for what the user character knows, V3-8c's F4) and the
    scene's POV face (the presentation face, carried beside them), plus
    the user's own durable submission."""

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
        "these keys:",
        '- "interpretation": what the submission means in this world',
        "  (a reading of the user's intent, never an invented intention)",
        '- "outcome": what actually happens, as world fact',
        '- "actual_action": the action that actually unfolds',
        '- "consequences": what changes because of it',
        '- "state_effects": an array of {"key": ..., "statement": ...}',
        "  objects settling the changed world state (may be empty)",
        '- "participants": an array of participant identity strings the',
        "  outcome is about",
        '- "replan_scope": "NONE" | "SCENE" | "CHAPTER" — whether the',
        "  scene's plan or the chapter's plan must be revised",
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
    cleaned prose. An empty answer is the honest ``no-output`` refusal
    — :class:`~elc.world.writer.PovWriter`'s deterministic guards and
    the SEGMENT COMMIT stay the library face's, downstream."""

    def __init__(self, completion: TextCompletion) -> None:
        self._completion = completion

    def write_segment(self, context: PovContext) -> str:
        """One segment's prose from the POV-safe context (see the class
        docstring)."""

        body = _clean(
            _complete_text(self._completion, _writer_prompt(context))
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
    judgment."""

    def __init__(self, completion: TextCompletion) -> None:
        self._completion = completion

    def plan_scene(self, context: ScenePlanContext) -> Mapping[str, Any]:
        """The scene's plan content (see the class docstring)."""

        return _parse_scene_element(
            _payload_object(
                _complete_text(self._completion, _planner_prompt(context))
            )
        )

    def replan_element(
        self, context: ScenePlanContext
    ) -> Mapping[str, Any]:
        """The SCENE arm's revised element (see the class docstring)."""

        return _parse_scene_element(
            _payload_object(
                _complete_text(
                    self._completion, _planner_replan_prompt(context)
                )
            )
        )


class LlmDirectorProvider:
    """The Director arm (V3-8b's HIGH-3: the initial Chapter Blueprint
    and the CHAPTER replan) over one :class:`TextCompletion` seam — the
    full ``DirectorContext`` reading goes in, the Blueprint payload's
    shape comes out; ``Director.open_next_chapter`` /
    ``apply_action_replan`` keep the validation and the persistence."""

    def __init__(self, completion: TextCompletion) -> None:
        self._completion = completion

    def draft_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]:
        """The initial Blueprint (see the class docstring)."""

        return _parse_blueprint(
            _complete_text(self._completion, _director_prompt(context))
        )

    def replan_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]:
        """The CHAPTER arm's revised Blueprint (see the class
        docstring)."""

        return _parse_blueprint(
            _complete_text(
                self._completion, _director_replan_prompt(context)
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
    unchanged."""

    def __init__(self, completion: TextCompletion) -> None:
        self._completion = completion

    def adjudicate(self, context: ResolverContext) -> Adjudication:
        """The verdict for this submission (see the class docstring)."""

        return _parse_adjudication(
            _complete_text(self._completion, _resolver_prompt(context))
        )
