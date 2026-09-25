"""Persona Runtime command face — the only PromptCompiler in the codebase.

docs/DOMAIN_MODEL.md D-INV-012: the final provider prompt is built only by
Persona Runtime / PromptCompiler. tests/architecture enforces that this
class exists nowhere else.

The GenerationActionStore port moved to elc.runtime.generation in
TASK-OPI-eaaa5a1d.6: GenerationActionIntent / ProviderAttempt are
Runtime-specific records (docs/DOMAIN_MODEL.md §16), so their durable face
and §14 state-machine authority are runtime-owned, not persona-owned.

**P9-0 (门三): the untrusted sections are framed, and their content cannot
make a frame; P9-R1 adds the persona card's free text to that set.** Five of
the compiled sections carry text the *user or a model produced and the
system persisted* — ``[profile]``'s disclosed facts, ``[relationship]``'s
remembered memories, ``[episode]``'s summary and threads, ``[history]``'s
turns, and the eight free-text columns of ``[persona]``'s CharacterPackage
(identity / personality / background / speech_style / values / boundaries /
opening / scenario) — while the other three (``[contract]``, ``[teaching]``'s
directive, ``[channel]``) are the system's own. A section is a *line* whose
first character is ``[`` and whose last is ``]``, so untrusted text that
could reach a line start could impersonate a section — the classic
prompt-injection shape this cut closes, on the boundary the P9-0 ruling names
(门三, the untrusted prompt-framing gate).

**P9-R1 (the persona card joins the untrusted set).** BF-05
``behavioral_baselines/security/SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md``
lists ``persona card text`` outright in its ``UNTRUSTED_CONTENT`` block
(§ "UNTRUSTED_CONTENT", :142-153: user free text / persona card text /
lore·world text / provider·model output / retrieved memory text / external
content candidate — "文本本身没有 Authority"), and ``SEC-008`` (:1030)
reads "Persona/Lore text cannot modify system security policy." Before this
cut the eight free-text columns rendered inline and unframed, so a card whose
``identity`` or ``boundaries`` carried a newline plus a ``[contract]``- or
``[teaching]``-shaped line could *forge a section* (the review's two
vectors). Canonical data *ownership* is not trusted instruction *authority*:
the Persona Domain owning the package row says whose truth it is, not that
its free text may write prompt structure. The fix therefore splits the
section: the id/revision/policy keys stay the system's own ``[persona]``
lines, and the eight free-text columns render inside the ``persona`` frame
whose marker carries the section name as the block's owner (the payload has
no second ``[persona]`` header — a header there would make the section head
appear twice, and P9-0's scanner properties rely on one head per section).
Per-field classification lives in :data:`PROMPT_FIELD_TRUST`.

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
2. **The five untrusted sections are exactly the ones whose content the user
   or a model produced and the system persisted.** ``[history]`` is included
   although the ruling's enumeration names the three §11 views: turn text is
   the same shape of input (a user turn's ``raw_content`` reaches the prompt
   verbatim) and leaving it unframed would be a boundary drawn around the
   least-trusted text. ``[persona]`` joins them in P9-R1: BF-05's
   ``UNTRUSTED_CONTENT`` block lists ``persona card text`` outright, the
   eight free-text columns are the card's editable prose rather than a
   controlled vocabulary, and ``SEC-008`` forbids persona/lore text from
   modifying system policy — a card line that can start a line can do
   exactly that to the prompt's structure. ``[contract]``/``[teaching]``/
   ``[channel]`` stay the system's own (the contract is configuration, the
   directive is built by the teaching flow from validated targets, the
   channel is an enum). Within ``[persona]`` the classification is per
   field, recorded in :data:`PROMPT_FIELD_TRUST`: the id/revision/policy
   lines remain the section's, and only the eight card-prose columns render
   inside the frame. Revisit: a future section is fed by user- or
   model-produced durable text — it joins :data:`UNTRUSTED_PROMPT_SECTIONS`,
   and the frame travels with it.
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
5. **``lore/world text`` has no carrier in this compiler yet — which is why
   it is not framed here.** BF-05's ``UNTRUSTED_CONTENT`` block lists
   ``lore/world text`` alongside ``persona card text``, but ``WorldLoreView``
   is not one of :data:`PROMPT_SECTION_ORDER`'s sections and
   :meth:`PromptCompiler.compile` never reads
   ``GenerationContext.world_lore_view`` — no lore text can reach the prompt
   today, so this cut neither frames it nor claims to have fixed that half.
   The ``lore_refs`` line of ``[persona]`` is the system's *reference* list
   (opaque ids), not lore prose. Revisit: the first cut that gives a lore
   section a carrier on this compiler — that section joins
   :data:`UNTRUSTED_PROMPT_SECTIONS` and renders inside the frame, per BF-05
   and ``SEC-008``. P9-R1 registered this so the fix is not misread as
   covering the lore half.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from elc.persona.types import (
    CharacterPackageRecord,
    CompiledPrompt,
    GenerationContext,
    GenerationContract,
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

#: P9-0 (门三) / P9-R1: the sections whose content the user or a model
#: produced and the system persisted — every one of them is rendered inside
#: the trust frame below (module docstring, reading 2). Membership is by
#: *provenance*, not by position: a section joins this tuple when its text
#: stops being the system's own. P9-R1 adds ``persona``: BF-05's
#: ``UNTRUSTED_CONTENT`` block lists ``persona card text``, and ``SEC-008``
#: forbids persona text from modifying system policy. The section keeps its
#: system-owned id/revision/policy lines and frames its eight free-text
#: columns (:data:`PROMPT_FIELD_TRUST`).
UNTRUSTED_PROMPT_SECTIONS = (
    "persona",
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

#: P9-R1: the two carriers a compiled value can have — the ``carrier`` column
#: of :data:`PROMPT_FIELD_TRUST`.
#:
#: ``TRUST_CARRIER_SECTION`` — the value is a system-authored line of its
#: ``[section]`` block, rendered literally in the template's ``key: value``
#: shape. ``TRUST_CARRIER_FRAME`` — the value is free text and renders only
#: inside its section's trust frame, escaped and marker-delimited. A value
#: with the frame carrier is by construction not the system's own, so its
#: line can never be the one a section scanner reads as structure.
TRUST_CARRIER_SECTION = "section"
TRUST_CARRIER_FRAME = "frame"

#: P9-R1: the per-field trust classification of every value the compiler can
#: put into the prompt — ``(section, field, trust, carrier)`` rows, in render
#: order within each section.
#:
#: ``trust`` is ``"trusted"`` when the value is the system's own (an id, a
#: revision, an enum, a policy word, a version word, a validated-content
#: directive) and ``"untrusted"`` when BF-05 ``UNTRUSTED_CONTENT`` covers the
#: source it comes from (user free text, persona card text, provider output,
#: remembered memory text). ``carrier`` is :data:`TRUST_CARRIER_SECTION` or
#: :data:`TRUST_CARRIER_FRAME`. The table is the *declaration*; the P9-R1
#: suite asserts it against the real rendering (every trusted value appears
#: as a literal line of its section, every untrusted value only inside its
#: frame). ``[history]`` has one value row because the whole section is turn
#: text — the ``#N user:`` / ``#N assistant:`` prefixes are the system's
#: skeleton, not values.
PROMPT_FIELD_TRUST: tuple[tuple[str, str, str, str], ...] = (
    # persona — CharacterPackage §5.1: ids/revision/policy words are the
    # system's own; the eight prose columns are persona card text (BF-05
    # UNTRUSTED_CONTENT lists "persona card text").
    ("persona", "character_package_id", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "persona_id", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "revision", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "generation_policy", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "lore_refs", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "language_policy", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "style_constraints", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "forbidden_claims", "trusted", TRUST_CARRIER_SECTION),
    ("persona", "identity", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "personality", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "background", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "speech_style", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "values", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "boundaries", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "opening", "untrusted", TRUST_CARRIER_FRAME),
    ("persona", "scenario", "untrusted", TRUST_CARRIER_FRAME),
    # profile — the disclosure view: ids/level are the system's, the
    # disclosed facts are user free text.
    ("profile", "prompt_version", "trusted", TRUST_CARRIER_SECTION),
    ("profile", "persona_id", "trusted", TRUST_CARRIER_SECTION),
    ("profile", "disclosure_level", "trusted", TRUST_CARRIER_SECTION),
    ("profile", "disclosed_facts", "untrusted", TRUST_CARRIER_FRAME),
    # history — the turns themselves (BF-05 "user free text").
    ("history", "turn_text", "untrusted", TRUST_CARRIER_FRAME),
    # relationship — the memory rows: ids are the system's, the remembered
    # content is untrusted text (BF-05 "retrieved memory text").
    ("relationship", "prompt_version", "trusted", TRUST_CARRIER_SECTION),
    ("relationship", "persona_id", "trusted", TRUST_CARRIER_SECTION),
    ("relationship", "user_id", "trusted", TRUST_CARRIER_SECTION),
    ("relationship", "memories", "untrusted", TRUST_CARRIER_FRAME),
    # episode — the conversation's digest: ids/version/status are the
    # system's, the prose columns are generated summary text.
    ("episode", "prompt_version", "trusted", TRUST_CARRIER_SECTION),
    ("episode", "episode_id", "trusted", TRUST_CARRIER_SECTION),
    ("episode", "version", "trusted", TRUST_CARRIER_SECTION),
    ("episode", "status", "trusted", TRUST_CARRIER_SECTION),
    ("episode", "summary", "untrusted", TRUST_CARRIER_FRAME),
    ("episode", "open_threads", "untrusted", TRUST_CARRIER_FRAME),
    ("episode", "recent_events", "untrusted", TRUST_CARRIER_FRAME),
    # contract — configuration, all the system's own.
    ("contract", "generation_contract_id", "trusted", TRUST_CARRIER_SECTION),
    ("contract", "action_type", "trusted", TRUST_CARRIER_SECTION),
    ("contract", "response_mode", "trusted", TRUST_CARRIER_SECTION),
    ("contract", "allowed_disclosures", "trusted", TRUST_CARRIER_SECTION),
    ("contract", "max_length", "trusted", TRUST_CARRIER_SECTION),
    # teaching — the ephemeral directive, built by the teaching flow from
    # validated curriculum targets, rendered from the persona-owned
    # TeachingPromptView (P9-0's ruling; the two-way AST pin keeps this
    # module from importing elc.teaching). Revisit: a cut that fills hint /
    # reveal / explanation from provider output rather than validated
    # content re-opens these rows — model output is UNTRUSTED_CONTENT.
    ("teaching", "prompt_version", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "action_type", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "moment_id", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "focus_target_type", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "focus_target_id", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "presentation_phase", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "support_level", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "attempt_index", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "hint", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "reveal", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "explanation", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "closure", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "completion_outcome", "trusted", TRUST_CARRIER_SECTION),
    ("teaching", "abort_reason", "trusted", TRUST_CARRIER_SECTION),
    # channel — the interaction channel enum.
    ("channel", "interaction_channel", "trusted", TRUST_CARRIER_SECTION),
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

    P9-R1 (TASK-OPI-e26b27a7-….47): the [persona] section is split by
    provenance. The id/revision/policy lines stay the section's own, and the
    eight free-text columns render inside the ``persona`` frame (the section
    joins :data:`UNTRUSTED_PROMPT_SECTIONS`), because BF-05
    ``UNTRUSTED_CONTENT`` lists ``persona card text`` and ``SEC-008``
    forbids persona text from modifying system policy. Package fields still
    really enter the prompt — a different package still yields a different
    prompt, now from inside the frame for the prose columns.

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
            sections.append(
                _persona_system_section(package, context, contract)
            )
            sections.append(
                _framed_untrusted_block(
                    "persona", _persona_card_text_block(package)
                )
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


def _persona_system_section(
    package: CharacterPackageRecord,
    context: GenerationContext,
    contract: GenerationContract | None,
) -> str:
    """The ``[persona]`` section's system-owned lines (P9-R1).

    These are the :data:`TRUST_CARRIER_SECTION` rows of the persona block in
    :data:`PROMPT_FIELD_TRUST` — the package id/revision/policy keys plus the
    contract's style/forbidden words. The section is theirs: the eight
    free-text columns are *not* rendered here (they carry the card's prose
    and render inside the ``persona`` frame, :func:`_persona_card_text_block`),
    and every line that does render here is byte-identical to what the
    pre-P9-R1 section rendered, in the same relative order.
    """

    lore_refs = "; ".join(package.lore_refs)
    style = "; ".join(contract.style_constraints) if contract else ""
    forbidden = "; ".join(contract.forbidden_claims) if contract else ""
    return (
        "[persona]\n"
        f"character_package_id: {package.character_package_id}\n"
        f"persona_id: {package.persona_id}\n"
        f"revision: {package.revision}\n"
        f"generation_policy: {package.generation_policy}\n"
        f"lore_refs: {lore_refs}\n"
        f"language_policy: {context.language_policy}\n"
        f"style_constraints: {style}\n"
        f"forbidden_claims: {forbidden}"
    )


def _persona_card_text_block(package: CharacterPackageRecord) -> str:
    """The persona card's eight free-text columns, as a frame payload (P9-R1).

    Rendered as ``key: value`` lines in the card's own column order, with no
    section header of their own — the frame marker's ``section`` field names
    the owner. A ``[persona]`` header here would make the section head appear
    twice, and P9-0's scanner properties (one head per section; a head's
    position is its section's position) rely on one head per section.
    Escaping and the marker pair are the shared mechanism, not a second one:
    every value goes through :func:`_escaped_untrusted_text` (exactly what
    :func:`_framed_untrusted_section` does per field), the frame is around
    the resulting block (:func:`_framed_untrusted_block`), and the marker
    carries :data:`UNTRUSTED_FRAMING_VERSION` plus the payload's character
    count.
    """

    return "\n".join(
        (
            f"identity: {_escaped_untrusted_text(package.identity)}",
            f"personality: {_escaped_untrusted_text(package.personality)}",
            f"background: {_escaped_untrusted_text(package.background)}",
            f"speech_style: {_escaped_untrusted_text(package.speech_style)}",
            f"values: {_escaped_untrusted_text(package.values)}",
            f"boundaries: {_escaped_untrusted_text(package.boundaries)}",
            f"opening: {_escaped_untrusted_text(package.opening)}",
            f"scenario: {_escaped_untrusted_text(package.scenario)}",
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
