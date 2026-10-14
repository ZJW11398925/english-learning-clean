"""The dual-seat world's harness tool registry (DS-1, the technical
definition §3 — docs/design/2026-10-14-dual-seat-world-technical-definition.md)
— **the spine's authorized execution face**, not an LLM toolbox.

**What this module is.** The technical definition's §1 ruling (F9) is
explicit: the director agent performs **no LLM tool-calling free loop** —
every model call is context + task → one structured decision; the
「工具注册表」 is the **spine's** face for executing what those decisions
authorize, and nothing else. This module is that face, mechanically: a
closed vocabulary of principals (who may act) and tools (what may be
done), one permission table, and one
:func:`authorize` gate the turn spine (``elc.world.turns``) calls
immediately before each privileged library call. A tool a principal does
not carry raises :class:`ToolViolation` — the loud programmer-error arm,
never a silent no-op and never a second ad-hoc ``if`` chain elsewhere.

**The permission table is the design's own sentences, mechanized** (§3,
verbatim in intent):

- ``canon_delta`` — **the adjudication face only** (the ruling is the one
  writer of world facts; three-check deny-first stays
  :func:`elc.world.action.commit_action`'s own, downstream);
- ``memory_read`` — any principal (each sub-agent reads the world's
  durable memory through its own compiled context; the POV door is the
  context assembly, not this registry);
- ``memory_write`` — **the character seat only**, and only for its own
  row (the private-thought increment lands through
  :func:`elc.world.memory.record_belief`, whose ``participant_id`` is
  the writing character — the ownership is the call's own shape);
- ``bible_edit`` — **the director seat only**, graded (§6 F3: textual
  edits take effect at once, structural ones park until the next
  chapter);
- ``dispatch_character`` — **the spine only** (it executes the director
  agent's dispatch decision; the arm itself holds no execution power);
- ``render_narration`` — **the narrator only** (the prose commit is the
  narrator's product handed to the SEGMENT COMMIT);
- ``settle_chapter`` — **the spine only**;
- ``clock`` — any principal (the stamps ride the caller's ``now``; no
  hidden clock lives here).

**The model arms are principals, not tool-callers**: an arm never sees
this registry and never asks for a tool; the spine checks on the arm's
behalf at the execution point (:class:`Principal` names whose product is
being executed). The user's will enters only through the director seat
(:data:`Principal.DIRECTOR_SEAT`) and the durable submission — "绝不直
写行为" stays mechanical: no principal, user included, carries
``canon_delta`` but the adjudicator.

Discipline: a leaf module — imports nothing from ``elc`` at runtime, no
I/O, no clock, no SQL; value semantics throughout; ``__all__`` names the
exported faces.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "Principal",
    "Tool",
    "ToolViolation",
    "authorize",
    "permissions_of",
]


class Principal(StrEnum):
    """The who of the harness — the seats the technical definition §3
    names. The four model arms ride the seat that owns their product
    (the dispatch arm acts *for* the director seat but carries no tool
    of its own: its product is advice the spine executes)."""

    #: The turn spine — the code's own execution face (§1: the code spine
    #: owns the turn trunk).
    SPINE = "spine"
    #: The director seat — the user's authoring position (§0: the seat
    #: through which user will enters generation).
    DIRECTOR_SEAT = "director_seat"
    #: One protagonist's character arm (§2: the per-protagonist model).
    CHARACTER = "character"
    #: The batch adjudication face (§1b: the single ruling call).
    ADJUDICATOR = "adjudicator"
    #: The narration arm (§1 ⑦: the streaming second-person prose).
    NARRATOR = "narrator"


class Tool(StrEnum):
    """The what of the harness — the registry's closed tool vocabulary
    (technical definition §3, one word each)."""

    #: The world-fact landing (the ruling's δ through the commit chain's
    #: three checks — Schema ∧ Perm ∧ Rule, deny-first).
    CANON_DELTA = "canon_delta"
    #: Reading the durable memory / cognition faces (each sub-agent's own
    #: compiled context is the read door).
    MEMORY_READ = "memory_read"
    #: Writing one's own memory row (the private-thought increment).
    MEMORY_WRITE = "memory_write"
    #: Editing the world setting, graded (textual now / structural next
    #: chapter).
    BIBLE_EDIT = "bible_edit"
    #: Dispatching one protagonist's response arm.
    DISPATCH_CHARACTER = "dispatch_character"
    #: Rendering the second-person narration.
    RENDER_NARRATION = "render_narration"
    #: Landing the chapter's offstage settlement.
    SETTLE_CHAPTER = "settle_chapter"
    #: Reading the canonical time (the caller's own stamp posture).
    CLOCK = "clock"


#: The permission table — the design's §3 sentences as data. One frozen
#: set per tool; a tool outside the table is a registry bug (the module's
#: own ``KeyError`` at import proof time, never a runtime surprise).
_PERMISSIONS: dict[Tool, frozenset[Principal]] = {
    Tool.CANON_DELTA: frozenset({Principal.ADJUDICATOR}),
    Tool.MEMORY_READ: frozenset(set(Principal)),
    Tool.MEMORY_WRITE: frozenset({Principal.CHARACTER}),
    Tool.BIBLE_EDIT: frozenset({Principal.DIRECTOR_SEAT}),
    Tool.DISPATCH_CHARACTER: frozenset({Principal.SPINE}),
    Tool.RENDER_NARRATION: frozenset({Principal.NARRATOR}),
    Tool.SETTLE_CHAPTER: frozenset({Principal.SPINE}),
    Tool.CLOCK: frozenset(set(Principal)),
}


class ToolViolation(Exception):
    """A principal reached for a tool it does not carry — the loud
    programmer-error arm (the store family's corrupted-call posture). The
    message names both words and carries nothing else; the registry never
    guesses a fallback."""

    def __init__(self, tool: Tool, principal: Principal) -> None:
        super().__init__(
            f"tool {tool.value!r} is not authorized for principal"
            f" {principal.value!r} — the harness permission table refuses"
        )
        self.tool = tool
        self.principal = principal


def authorize(tool: Tool, principal: Principal) -> None:
    """The one gate the spine calls before each privileged execution —
    ``None`` when the table carries the pair, :class:`ToolViolation`
    otherwise (nothing else ever happens here: no logging, no clock, no
    I/O)."""

    if principal not in _PERMISSIONS[tool]:
        raise ToolViolation(tool, principal)


def permissions_of(tool: Tool) -> frozenset[Principal]:
    """One tool's authorized principals — the read face the pins (and
    only the pins) read; the spine authorizes through :func:`authorize`
    alone."""

    return _PERMISSIONS[tool]
