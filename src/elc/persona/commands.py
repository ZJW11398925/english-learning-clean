"""Persona Runtime command face — the only PromptCompiler in the codebase.

docs/DOMAIN_MODEL.md D-INV-012: the final provider prompt is built only by
Persona Runtime / PromptCompiler. tests/architecture enforces that this
class exists nowhere else.

The GenerationActionStore port moved to elc.runtime.generation in
TASK-OPI-eaaa5a1d.6: GenerationActionIntent / ProviderAttempt are
Runtime-specific records (docs/DOMAIN_MODEL.md §16), so their durable face
and §14 state-machine authority are runtime-owned, not persona-owned.

**P9-0 (门三): the untrusted sections are framed, and their content cannot
make a frame.** Four of the compiled sections carry text the *user or a model
produced and the system persisted* — ``[profile]``'s disclosed facts,
``[relationship]``'s remembered memories, ``[episode]``'s summary and
threads, and ``[history]``'s turns — while the other four (``[persona]``'s
CharacterPackage, ``[contract]``, ``[teaching]``'s directive, ``[channel]``)
are the system's own. A section is a *line* whose first character is ``[``
and whose last is ``]``, so untrusted text that could reach a line start
could impersonate a section — the classic prompt-injection shape this cut
closes, on the boundary the P9-0 ruling names (门三, the untrusted
prompt-framing gate).

Two mechanisms, both structural rather than advisory:

- **every untrusted section is delimited by fixed boundary markers** — a
  ``<<untrusted-section {…}>>`` line before it and a
  ``<<end-untrusted-section {…}>>`` line after it, each carrying a JSON
  object with this framing's version, the section's name and the payload's
  character count (the length prefix). The markers are separate blocks, so
  the section's own header and key lines are byte-identical to what they
  were - the delimiter is *added around* a section, never inside it;
- **every value of an untrusted section is line-escaped** — the characters
  Python (and every reasonable reader) treats as line breaks (
  ``\\r \\n \\v \\f \\x1c \\x1d \\x1e \\x85 \\u2028 \\u2029``) are rewritten
  to their two-character escapes. The transform is unconditional and the
  identity on single-line text, and it makes the property checkable rather
  than hoped for: no untrusted value can contain a line break, so no
  untrusted value can start a line, so — **for a line-oriented reader, the
  reader these sections and their scanner are built on** — no untrusted
  value can create a section boundary. The claim is structural, not a claim
  about substrings: a value may still carry a marker's or a header's *text*
  inside its own line (a user's ``<<untrusted-section`` is just characters,
  rendered on the value's line), and that text is not a boundary. A reader
  that scans for marker substrings anywhere rather than at line starts is
  not the reader this frame is written for.

The trusted sections' rendering is untouched: a request with no untrusted
views compiles byte-identically to the pre-P9-0 prompt, and the four trusted
sections' bytes are unchanged wherever they appear (the P1/P3/P4 pins hold;
P4-3's byte-determinism pin — same request, same bytes — holds for every
request, framed or not).

Declared readings (this cut's, each with the condition that re-opens it):

1. **The frame is a marker pair plus an escape, not a re-encoding of the
   values.** JSON framing of each *value* (``disclosed_facts: ["…"]``) would
   change the rendering of every view, including the ones the P4-3 pins read
   verbatim — and the pins are the record of the section templates P4-3
   declared. This cut therefore frames the *region* (the ruling's mandatory
   half: explicit delimiting, fixed boundary markers, no boundary creation)
   and keeps the values' spelling, escaping only the line-breaking
   characters. The JSON recommendation is honoured where it is
   separable — the markers are JSON payloads, and the escape spellings are
   JSON's own. Revisit: canonical text (or a later trust-boundary cut) asks
   for the values themselves to be JSON-encoded, or the section templates
   are re-declared — then the P4-3 pins are rewritten with this module, on
   purpose.
2. **The four untrusted sections are exactly the ones whose content the user
   or a model produced and the system persisted.** ``[history]`` is included
   although the ruling's enumeration names the three §11 views: turn text is
   the same shape of input (a user turn's ``raw_content`` reaches the prompt
   verbatim) and leaving it unframed would be a boundary drawn around the
   least-trusted text. ``[persona]``/``[contract]``/``[teaching]``/
   ``[channel]`` are system-authored (the CharacterPackage is the persona's
   own content, the directive is built by the teaching flow from validated
   targets), and the ruling names them trusted. Revisit: a future section is
   fed by user- or model-produced durable text — it joins
   :data:`UNTRUSTED_PROMPT_SECTIONS`, and the frame travels with it.
3. **The escaping is structural, not semantic.** A value containing the
   two-character sequence ``\\n`` is indistinguishable after escaping from
   one containing a real newline: the transform's promise is "no line
   breaks", not "the reader can recover the original bytes from the prompt".
   Recovering the original text is the *store's* job (the durable turn or
   memory row holds it verbatim); the prompt's job is to stop carrying
   structure an attacker chose. Revisit: a consumer needs the prompt to be a
   lossless carrier of untrusted text (then the transform becomes a full
   reversible encoding, and the values' spelling changes with it).
4. **The frame is version-stamped and length-prefixed.** The marker's
   ``version`` word (``elc-untrusted-v1``) lets a stored prompt say which
   framing produced it — the ``[teaching]``/P4-3 section-version convention —
   and ``chars`` (the payload block's length) is the length prefix a reader
   needs to know where the delimited payload ends without trusting its
   contents. Revisit: the marker's shape changes (then the version word
   moves), or a reader needs a different quantity (e.g. the count of
   *escaped* characters rather than the block's length).
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from elc.persona.types import (
    CharacterPackageRecord,
    CompiledPrompt,
    PromptCompilationRequest,
    TeachingPromptView,
    episode_prompt_fields,
    profile_prompt_fields,
    relationship_prompt_fields,
)
from elc.platform.types import (
    CharacterPackageId,
    Ok,
    Result,
)

#: The fixed section order of the compiled prompt (Phase 3 P3-1B ⑨ pinned
#: it; Phase 4 P4-3 ④ extends it with the three §11 views the persona
#: consumes — docs/RUNTIME_ARCHITECTURE.md §11 lists CharacterPackage,
#: RelationshipView, EpisodeView, WorldLoreView, DisclosedUserProfile,
#: ConversationWindow among the GenerationContext members):
#:
#:     persona → profile → contract → history → relationship → episode →
#:     teaching → channel
#:
#: The new sections sit where they do for stated reasons, not by accident:
#: ``profile`` immediately after ``persona`` (both are "who is talking to
#: whom"); ``relationship``/``episode`` after ``history`` (they are the
#: distilled form of what history shows in full, so the model reads the
#: transcript first and the continuity summary after it); ``teaching`` stays
#: last-but-one because it is the ephemeral directive of *this* turn.
#: Byte-determinism of the compiled prompt depends on this order, so it lives
#: here as a declared constant and is asserted by test rather than being
#: implied by the sequence of appends below. A section is only emitted when
#: its view is present, so every pre-P4-3 assembly compiles byte-identical
#: prompts (pinned by the P1/P3 suites).
PROMPT_SECTION_ORDER = (
    "persona",
    "profile",
    "contract",
    "history",
    "relationship",
    "episode",
    "teaching",
    "channel",
)

#: P9-0 (门三): the sections whose content the user or a model produced and
#: the system persisted — every one of them is rendered inside the trust
#: frame below (module docstring, reading 2). Membership is by *provenance*,
#: not by position: a section joins this tuple when its text stops being the
#: system's own.
UNTRUSTED_PROMPT_SECTIONS = (
    "profile",
    "history",
    "relationship",
    "episode",
)

#: The frame's version word — a stored prompt says which framing produced it
#: (the ``[teaching]``/P4-3 section-version convention).
UNTRUSTED_FRAMING_VERSION = "elc-untrusted-v1"

#: The two boundary marker prefixes. They are **not** ``[...]``-shaped on
#: purpose: a marker must not be mistakable for a section header by a reader
#: that scans for that shape (the P4-3 suite's own scanner does), and the
#: end marker's prefix is not a prefix of the begin marker's.
UNTRUSTED_SECTION_BEGIN = "<<untrusted-section"
UNTRUSTED_SECTION_END = "<<end-untrusted-section"

#: The characters the escape rewrites, as ``(character, escape)`` pairs. Every
#: member is a line break for :meth:`str.splitlines` (the reader a section
#: scanner is built on) or for a text-mode consumer; the escape is the
#: two-character sequence a reader sees instead. The list is explicit and
#: pinned by test rather than taken from ``str.splitlines`` at runtime, so a
#: Python version that moves the boundary cannot move this frame silently.
UNTRUSTED_ESCAPES: tuple[tuple[str, str], ...] = (
    ("\r", "\\r"),
    ("\n", "\\n"),
    ("\v", "\\v"),
    ("\f", "\\f"),
    ("\x1c", "\\x1c"),
    ("\x1d", "\\x1d"),
    ("\x1e", "\\x1e"),
    ("\x85", "\\x85"),
    ("\u2028", "\\u2028"),
    ("\u2029", "\\u2029"),
)


@runtime_checkable
class PersonaCommands(Protocol):
    """Persona Runtime writes: package registration + prompt compilation."""

    def register_character_package(
        self, package: CharacterPackageRecord
    ) -> Result[CharacterPackageId]:
        ...

    def compile_prompt(
        self, request: PromptCompilationRequest
    ) -> Result[CompiledPrompt]:
        """Build the final provider prompt via PromptCompiler."""
        ...


class PromptCompiler:
    """Persona Runtime prompt compiler — the sole final-prompt authority.

    Consumes only the views handed in via PromptCompilationRequest. It never
    creates TeachingDirectives (D-INV-002) and never resolves secrets:
    provider disclosure flows through action-specific minimal views and
    secret_ref resolution happens in the transport layer at send time
    (docs/RUNTIME_ARCHITECTURE.md §24.3).

    Deterministic assembly (IMPLEMENTATION_PLAN §3 "PromptCompiler"): the
    same request always yields byte-identical prompt text — no randomness,
    no timestamps, no environment reads; conversation-window slices render
    in turn_sequence order.

    P3-0 (TASK-…55 ③): the [persona] section consumes the canonical
    CharacterPackage §5.1 fields (identity / personality / background /
    speech_style / values / boundaries / opening / scenario /
    generation_policy / lore_refs plus the id/revision provenance) —
    package fields really enter the compiled prompt (a different package
    yields a different prompt, pinned by test). Lifecycle metadata
    (status / updated_at) deliberately stays OUT of the prompt: it is not
    character content, and rendering a clock stamp would break
    byte-determinism.

    P4-3 (TASK-OPI-4d516e4f-….19 ④): three §11 views join the prompt —
    [profile] (the DisclosedUserProfile the disclosure decision produced:
    facts / level / persona), [relationship] (the RelationshipView's ACTIVE
    memories, in the view's own order) and [episode] (the EpisodeView's
    content columns). Each section is versioned and renders its version key
    first, exactly like [teaching]. Scope isolation is structural, not
    defensive: the compiler renders what the views hold, and the views are
    scope-bound reads (one Persona×User pair, one disclosure grant), so
    Persona A's material cannot appear in Persona B's prompt — there is no
    cross-persona object in the request to render. The compiler still
    resolves no secrets and creates no teaching directive (D-INV-002;
    RUNTIME §24.3 "PromptCompiler … 只能消费 action-specific disclosure
    view").
    """

    def compile(self, request: PromptCompilationRequest) -> Result[CompiledPrompt]:
        contract = request.generation_contract
        context = request.generation_context
        contract_id = (
            contract.generation_contract_id if contract is not None else "default"
        )
        sections: list[str] = []

        if context is not None and context.character_package is not None:
            package = context.character_package
            lore_refs = "; ".join(package.lore_refs)
            style = "; ".join(contract.style_constraints) if contract else ""
            forbidden = "; ".join(contract.forbidden_claims) if contract else ""
            sections.append(
                "[persona]\n"
                f"character_package_id: {package.character_package_id}\n"
                f"persona_id: {package.persona_id}\n"
                f"revision: {package.revision}\n"
                f"identity: {package.identity}\n"
                f"personality: {package.personality}\n"
                f"background: {package.background}\n"
                f"speech_style: {package.speech_style}\n"
                f"values: {package.values}\n"
                f"boundaries: {package.boundaries}\n"
                f"opening: {package.opening}\n"
                f"scenario: {package.scenario}\n"
                f"generation_policy: {package.generation_policy}\n"
                f"lore_refs: {lore_refs}\n"
                f"language_policy: {context.language_policy}\n"
                f"style_constraints: {style}\n"
                f"forbidden_claims: {forbidden}"
            )
        else:
            sections.append(
                f"[persona]\npersona_id: {request.persona_id}\n"
                "language_policy: default"
            )

        if context is not None and context.disclosed_user_profile is not None:
            sections.append(
                _framed_untrusted_section(
                    "profile",
                    profile_prompt_fields(context.disclosed_user_profile),
                )
            )

        if contract is not None:
            disclosures = "; ".join(contract.allowed_disclosures)
            max_length = (
                str(contract.max_length) if contract.max_length is not None else "none"
            )
            sections.append(
                "[contract]\n"
                f"generation_contract_id: {contract.generation_contract_id}\n"
                f"action_type: {contract.action_type.value}\n"
                f"response_mode: {contract.response_mode}\n"
                f"allowed_disclosures: {disclosures}\n"
                f"max_length: {max_length}"
            )

        window = getattr(context, "conversation_window", None) if context else None
        slices = getattr(window, "slices", None) if window is not None else None
        if slices:
            lines: list[str] = []
            for slice_ in slices:
                user_text = getattr(slice_.user_turn, "raw_content", "")
                assistant = slice_.assistant_turn
                assistant_text = (
                    assistant.content if assistant is not None else ""
                )
                seq = getattr(slice_, "turn_sequence", 0)
                lines.append(
                    f"#{seq} user: {_escaped_untrusted_text(user_text)}"
                )
                if assistant_text:
                    lines.append(
                        f"#{seq} assistant:"
                        f" {_escaped_untrusted_text(assistant_text)}"
                    )
            sections.append(
                _framed_untrusted_block("history", "[history]\n" + "\n".join(lines))
            )

        if context is not None and context.relationship_view is not None:
            sections.append(
                _framed_untrusted_section(
                    "relationship",
                    relationship_prompt_fields(context.relationship_view),
                )
            )

        if context is not None and context.episode_view is not None:
            sections.append(
                _framed_untrusted_section(
                    "episode",
                    episode_prompt_fields(context.episode_view),
                )
            )

        if context is not None and context.ephemeral_teaching_directive is not None:
            sections.append(
                _rendered_teaching_section(
                    context.ephemeral_teaching_directive
                )
            )

        sections.append(f"[channel]\n{request.interaction_channel.value}")
        prompt_text = "\n\n".join(sections)
        return Ok(
            CompiledPrompt(
                persona_id=request.persona_id,
                prompt_text=prompt_text,
                generation_contract=contract_id,
            )
        )


def _section(name: str, fields: tuple[tuple[str, str], ...]) -> str:
    """One P4-3 section: ``[name]`` plus its ``key: value`` lines.

    The shape is the ``[teaching]`` one — a fixed key order, one line per
    key, values already rendered to text — so a section's line count and key
    order never depend on which optional values are set.
    """

    lines = "\n".join(f"{key}: {value}" for key, value in fields)
    return f"[{name}]\n{lines}"


def _escaped_untrusted_text(text: str) -> str:
    """One untrusted value, with its line breaks escaped (module docstring).

    The transform is unconditional — every member of
    :data:`UNTRUSTED_ESCAPES` is rewritten, every time — and the identity on
    single-line text, so a value that carries no line break renders exactly
    as it always did (the P4-3 pins' own values), while a value that does
    cannot start a line the reader would treat as structure.
    """

    for character, escape in UNTRUSTED_ESCAPES:
        text = text.replace(character, escape)
    return text


def _framed_untrusted_section(
    name: str, fields: tuple[tuple[str, str], ...]
) -> str:
    """One untrusted section, escaped and framed (module docstring).

    Every value of the section is escaped (:func:`_escaped_untrusted_text`)
    and the rendered block is wrapped in the marker pair. The keys, the order
    and the separators are exactly ``_section``'s — the frame is *around* the
    section, so a reader that finds sections the way it always did reads the
    same block it read before.
    """

    escaped = tuple(
        (key, _escaped_untrusted_text(value)) for key, value in fields
    )
    return _framed_untrusted_block(name, _section(name, escaped))


def _framed_untrusted_block(name: str, block: str) -> str:
    """The marker pair around one already-rendered untrusted block.

    The markers are ``<<…>>`` lines carrying JSON objects (compact,
    ``sort_keys``) with three facts: the framing version
    (:data:`UNTRUSTED_FRAMING_VERSION`), the section's name, and the
    payload's character count — the length prefix. They are joined to the
    block with the same blank line that separates sections, so nothing about
    the block itself moves.
    """

    begin = json.dumps(
        {
            "chars": len(block),
            "section": name,
            "version": UNTRUSTED_FRAMING_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    end = json.dumps(
        {"section": name, "version": UNTRUSTED_FRAMING_VERSION},
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{UNTRUSTED_SECTION_BEGIN} {begin}>>\n\n{block}\n\n"
        f"{UNTRUSTED_SECTION_END} {end}>>"
    )


def _rendered_teaching_section(directive: object) -> str:
    """Render the teaching section of the prompt — PromptCompiler-owned.

    Phase 3 P3-1B ⑨: Teaching produces a directive, Persona Runtime owns
    the prompt. The canonical directive projection is
    :class:`TeachingPromptView`; it renders as the ``[teaching]`` section
    with the keys of :data:`TEACHING_PROMPT_KEY_ORDER` in that exact order
    and ``key: value`` lines, so the same view always yields the same
    bytes. Any other object keeps the pre-P3-1B ``[directive]`` rendering
    (no silent drop of a caller's directive).
    """

    if isinstance(directive, TeachingPromptView):
        lines = "\n".join(
            f"{key}: {value}" for key, value in directive.as_prompt_fields()
        )
        return "[teaching]\n" + lines
    return f"[directive]\n{str(directive)}"
