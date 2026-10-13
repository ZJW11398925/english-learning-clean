"""The Narrative V3 provider protocol face (V3-8a, TASK-OPI-06b954e0…4 /
the opening ruling ``DEC-OPI-06b954e0-…2``; RA §27's "provider 协议面"
paragraph; DOMAIN §20.2's second row; **V3-8b re-freeze** —
TASK-OPI-06b954e0…16 / ``DEC-OPI-06b954e0-…15``, the external review's
HIGH-2 / HIGH-3) — the production faces the pipeline orchestrator calls
through, and the deterministic fake the CI baseline drives them with.

**The four faces, spelled as Protocols**: Writer（正文）/
:class:`WriterProvider` — one segment's prose from its POV-safe context;
Planner（dossier 内容）/:class:`PlannerProvider` — **the SCENE level
only** (the scene's plan content and the SCENE arm's revised element);
Director（Chapter Blueprint）/:class:`DirectorProvider` — **the initial
Chapter Blueprint and the CHAPTER replan** (V3-8b's division freeze: the
chapter-level plan is the world's, produced from the full
:class:`~elc.world.director.DirectorContext`, never from a POV-limited
planner); Resolver（裁定）/:class:`ResolverProvider` — the verdict, in
the ``Adjudication`` shape :mod:`elc.world.action` froze, from the
**world-authoritative** :class:`ResolverContext`. The structural
contracts are deliberately narrow: the orchestrator calls through them
(DOMAIN §20.2's「管线驱动顺序」row), and **the Resolver's sole
adjudication authority is not loosened by the indirection** — the
protocol is only *where the verdict comes from*; ``commit_action``
still writes ``world_event`` / ``world_state_fact`` **only** from the
returned :class:`~elc.world.action.Adjudication` (N-INV-002 /
DOMAIN §20.3-1 unchanged). The Resolver's *input* is the world's:
:class:`ResolverContext` carries the CURRENT Bible, the settled facts,
the player's profile and the scene's canonical cast beside the user's
own submission — the resolver knows the real world's rules and physical
facts and must not invent the user's intent (the submission rides from
the durable ``user_action`` row); the **player character's own**
cognition / memory ride for **what the user character knows** (V3-8c's
F4 — ``player_cognition`` / ``player_memory``, the player's own read
face), the scene POV's cognition / memory ride as the **presentation
face** (RA §27's 「＋ 当前 POV 面」), and neither arm is the resolver's
own knowledge ceiling.

**The POV-safe context compilation hard door** (V3-5R's registered
obligation, TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11's item 5) takes
physical form in this module for the **POV-limited faces**: the Writer's
and the Scene Planner's inputs are assembled by :func:`pov_context_of`
— and its **signature is the door** — from exactly two faces: the
scene's own Plan face (the adopted dossier) and the **POV's own**
:class:`~elc.world.scene.SceneContext` (the V3-5R cognition/memory read
the Scene Planner assembled for *this* dossier's POV). The input
dataclasses below (:class:`PovContext` / :class:`ScenePlanContext`)
carry no field another participant's private face could ride in on — a
compiled context can only say what the POV could see. The two
world-authoritative faces (:class:`ResolverContext` /
:class:`DirectorPlanContext`) are deliberately *not* POV-limited — the
Resolver judges the world, and the Director plans chapters for it; the
door's law is about the *presentation* faces, and it stays exactly as
wide as its reason. The lexical ``must_hide`` guard in
:class:`~elc.world.writer.PovWriter` stays the second, deterministic
guard it honestly is (a semantic rewrite routes around a lexical guard
by construction); the real LLM wiring **landed in V3-8c**
(``elc/world/llm_providers.py`` — the four faces over the
``TextCompletion`` seam, with the persona BYOK egress adapting onto it
at the assembly face; TASK-OPI-cddb517c…7), and this door was its
precondition — the user's "好玩" acceptance still waits on the
assembly-side wiring and the Gold Scenario's two doors.

**The deterministic fake** (:class:`DeterministicFakeProvider`): one
class satisfying all four Protocols structurally — the CI baseline's
scripted stand-in. It opens no connection, writes nothing, consults no
clock: the prose, the plan content, the Blueprints and the verdicts are
configured per construction and echoed deterministically (the Writer
face's default is an echo-with-template; the plan faces echo the
context's own content unless configured otherwise; the Resolver face
answers the configured ruling **keyed by ``gate_id``** — an unscripted
gate is an honest ``ValueError``, the store family's corrupted-call
posture, never an invented ruling; the Director face's initial arm is
the one without a content source to echo, so an unscripted
:meth:`~DeterministicFakeProvider.draft_blueprint` is the script's gap
answered the same way, never an invented Blueprint). Every call is
recorded in deterministic order (``segment_contexts`` /
``plan_contexts`` / ``replan_contexts`` / ``blueprint_contexts`` /
``resolver_contexts``) — the POV-safe pins read the recordings to prove
what the provider could see.

Discipline: the module is a leaf — it imports nothing from ``elc`` at
runtime (the annotation imports ride ``TYPE_CHECKING``; the contexts are
value shapes and the fake's script is plain data), manages no
transaction, builds no SQL and holds no clock. The record types and the
fake are frozen/value or plainly recorded; the two ``raise`` arms are
the unscripted-gate and unscripted-draft ones above.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # the annotation-only edges (the module stays a leaf)
    from elc.world.action import Adjudication, UserActionRecord
    from elc.world.bible import BibleRevision
    from elc.world.cast import ActorProfileRecord, PlayerCharacterRecord
    from elc.world.cognition import V3CognitionView
    from elc.world.director import DirectorContext
    from elc.world.memory import V3MemoryView
    from elc.world.narrative.types import WorldSceneDossierRecord
    from elc.world.scene import SceneContext
    from elc.world.types import WorldStateFact

__all__ = [
    "DirectorPlanContext",
    "DirectorProvider",
    "DeterministicFakeProvider",
    "PlannerProvider",
    "PovContext",
    "ResolverContext",
    "ResolverProvider",
    "ScenePlanContext",
    "WriterProvider",
    "pov_context_of",
]


@dataclass(frozen=True)
class PovContext:
    """The Writer provider's compiled input for one segment — **and the
    POV-safe door's shape**.

    Every field belongs to the POV's own visible world: the scene's Plan
    face (``place`` / ``entry_goals`` / ``exit_condition`` /
    ``revealable`` / ``must_hide`` — the dossier's content, the plan's
    instruction about what may and may not be revealed), the canonical
    cast tuple, and the POV's **own** cognition / memory views (their
    ``viewer_id`` equals ``pov_actor_id``; the views' own laws already
    drop the events this POV did not witness). There is deliberately no
    field for another participant's memory, profile, card or private
    context: a semantic rewrite cannot leak from an input the object
    cannot carry.
    """

    scene_id: str
    segment_seq: int
    pov_actor_id: str
    participants: tuple[str, ...]
    place: str
    entry_goals: str
    exit_condition: str
    revealable: str
    must_hide: str
    current_tick: int
    cognition: V3CognitionView
    memory: V3MemoryView


@dataclass(frozen=True)
class ResolverContext:
    """The Resolver provider's input for one submission — **the
    world-authoritative face** (V3-8b, the external review's HIGH-2;
    DOMAIN §20.2's 「Resolver 裁定的权威输入」 row, RA §27's V3-8b
    修订). The user's own submission rides beside the world's real
    rules and physical facts: the resolver judges what actually
    happens, and must not invent what the user meant (``intent_text`` /
    ``selected_option`` come from the durable ``user_action`` row —
    N-INV-002 holds).

    The authority arms:

    - ``bible`` — the world's ``CURRENT`` Bible revision (``None`` for
      a world that never seeded one: the honest undeclared, never a
      fabricated authority); ``hard_rules`` / ``premise`` / the rest of
      the fourteen fields ride whole;
    - ``current_facts`` — the ``world_state_fact`` ``CURRENT`` half,
      key ascending: everything the world has settled, which is where
      the current location / physical state and the inventory /
      resource state live. **The baseline's honesty, stated**: this
      build holds no structured inventory table — inventory and
      resources ride the settled-fact face like every other state claim
      (``canonical_key`` names them), so the context carries that half
      whole rather than partitioning it by key naming;
    - ``player_character`` — the reader's durable character row, or
      ``None`` for a world that declares no player (the conditional
      law). Its ``abilities`` / ``limits`` are the ruling's capability
      input; **its ``location`` / ``state`` / ``knowledge_refs``
      columns are the creation-time seed only (V3-3R's freeze)** — the
      running location and physical state's authority is
      ``current_facts``, the running knowledge's is ``memory`` /
      ``cognition`` below; a resolver must not read the seed as current;
    - ``place`` / ``participants`` — the ruling scene's own canonical
      facts (its adopted dossier's — the same two the scene's plan face
      carries);
    - ``counterparts`` — the scene's AI participants' narrative
      profiles (``world_actor_profile`` rows, ``actor_id`` order): the
      relevant counterpart state the ruling reads. The player's own
      face rides ``player_character``; a participant holding no profile
      row contributes no entry (the honest undeclared, never a guessed
      one).

    The knowledge arms (the F4 ruling, V3-8c, TASK-OPI-cddb517c…7):

    - ``player_cognition`` / ``player_memory`` — the **player
      character's own** read faces (their ``viewer_id`` equals
      ``player_character.player_character_id``; both are ``None`` for a
      world that declares no player — the same conditional law the
      ``player_character`` arm keeps). This pair is the authority for
      **what the user character knows**: the player's durable
      cognition / memory read, read for the player's own identity;
    - ``pov_actor_id`` / ``cognition`` / ``memory`` — the scene's
      **narrative POV's** own read (the views' ``viewer_id`` equals
      ``pov_actor_id``), carried alongside per RA §27's 「＋ 当前 POV
      面」 as the **presentation face** (the prose presents through
      this POV). When the scene's POV is not the player character the
      two faces differ, and the POV's read is **not** the judge of
      what the user knows — the F4 wording disambiguation (V3-8c);
    - ``current_tick`` — the canonical story time both arms were read
      at.

    Neither knowledge arm bounds the resolver's own knowledge ceiling:
    that is the world's (the authority arms above).
    """

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


@dataclass(frozen=True)
class ScenePlanContext:
    """The Planner provider's POV-safe input for one scene — the SCENE
    arm's face.

    ``element`` is the scene's current Plan-face content (the Pipeline
    assembles it from the adopted dossier; ``None`` when the drive has
    no element at hand — a recovery-driven replan lets the provider
    answer from its own plan state, the LLM cut's shape). ``cognition``
    / ``memory`` are the POV's own reads again.
    """

    world_id: str
    scene_id: str
    pov_actor_id: str
    current_tick: int
    element: Mapping[str, Any] | None
    cognition: V3CognitionView
    memory: V3MemoryView


@dataclass(frozen=True)
class DirectorPlanContext:
    """The DirectorProvider's input — the Chapter Blueprint's own
    planning face (V3-8b, the external review's HIGH-3; DOMAIN §20.2's
    「CHAPTER 级 Blueprint（初次规划与 CHAPTER replan）的生产面」 row,
    RA §27's V3-8b 修订).

    ``director_context`` is the Director's full reading
    (:class:`~elc.world.director.DirectorContext`: the Bible, the
    world's CURRENT facts, the full cast, the active storylines, the
    settled chapters' summaries and ``current_tick``) — the
    chapter-level planner is **not** POV-limited, by the division
    freeze: a chapter's plan is the world's, not one character's.

    The two arms read the same record:

    - :meth:`DirectorProvider.draft_blueprint` — the initial planning:
      ``chapter_id`` / ``replan_request_id`` / ``trigger`` /
      ``blueprint`` are all ``None`` (no chapter exists yet; nothing
      triggered the plan);
    - :meth:`DirectorProvider.replan_blueprint` — the CHAPTER arm of a
      ruling's ``replan_scope``: ``chapter_id`` names the chapter,
      ``replan_request_id`` the durable obligation, ``trigger`` the
      **committed ruling** whose consequences invalidated the plan (its
      ``intent_text`` / ``outcome`` / ``consequences`` … are the
      replan's reason — the user's own words, never a fresh invented
      intent), and ``blueprint`` the chapter's current adopted payload
      (the content the replanning starts from).

    ``author_direction`` (V3-8h, the paradigm shift §10.5 item 2) is
    the **author layer's** optional word between chapters: the reader's
    free-text direction for the next chapter, handed to the **initial**
    planning arm only as a **soft expectation** — the prompt block says
    where the chapter should press toward, never a postcondition, and
    never a story fact invented on the reader's behalf. The replan arm
    never reads it (a replan's reason is the committed ruling alone),
    and nothing persists it: the direction touches the plan face only
    and writes no canon row of its own (zero migration).

    The payload either arm answers is only a proposal: the Director's
    own faces (``open_next_chapter`` / ``apply_action_replan``) keep
    the validation and the persistence — a bad plan content is refused
    by the seat that consumes it, not blessed here.
    """

    director_context: DirectorContext
    chapter_id: str | None
    replan_request_id: str | None
    trigger: UserActionRecord | None
    blueprint: Mapping[str, Any] | None
    author_direction: str | None = None


@runtime_checkable
class WriterProvider(Protocol):
    """The Writer's production face: one segment's prose from its
    POV-safe context (see :class:`PovContext`). The returned string is
    the prose the orchestrator hands to
    :meth:`elc.world.writer.PovWriter.write_segment` — the deterministic
    guards and the SEGMENT COMMIT stay the library face's; the provider
    never adjudicates a user behaviour (N-INV-002) and never writes.
    """

    def write_segment(self, context: PovContext) -> str: ...


@runtime_checkable
class PlannerProvider(Protocol):
    """The Scene Planner's production face — **the SCENE level only**
    (V3-8b's division re-freeze: the chapter level is
    :class:`DirectorProvider`'s, and it is no longer answered here).

    - :meth:`plan_scene` — the scene's dossier content (the LLM planner
      cut's landing seat; the deterministic chain's dossier seat is
      :meth:`elc.world.scene.ScenePlanner.open_scene`'s element-verbatim
      assembly, and the protocol is the contract the LLM cut wires);
    - :meth:`replan_element` — the SCENE arm's revised element, consumed
      by :meth:`elc.world.scene.ScenePlanner.replan_scene`.

    Its input is the POV-safe :class:`ScenePlanContext` — the POV's own
    cognition / memory and the current scene state are the primary
    inputs of a scene-level plan, exactly the faces this face may see.

    Every method answers a mapping; the library faces validate it (the
    ``_checked_fields`` family) — a bad plan content is refused by the
    seat that consumes it, not blessed here.
    """

    def plan_scene(self, context: ScenePlanContext) -> Mapping[str, Any]: ...

    def replan_element(
        self, context: ScenePlanContext
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class DirectorProvider(Protocol):
    """The World Director's production face (V3-8b, the external
    review's HIGH-3): **the initial Chapter Blueprint and the CHAPTER
    arm of a ruling's ``replan_scope``**, from
    :class:`DirectorPlanContext` — the full ``DirectorContext`` reading
    plus the triggering ruling on the replan arm.

    The production split this face freezes: ``Director`` keeps the
    validation and the persistence
    (:meth:`elc.world.director.Director.open_next_chapter`,
    :meth:`~elc.world.director.Director.apply_action_replan`), and the
    Blueprint's *production* is the world's own planning face — never
    the POV-limited :class:`PlannerProvider` (a chapter is planned for
    the world, not through one character's eyes). The payload is a
    proposal either way: the Director's schema judges it.
    """

    def draft_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]: ...

    def replan_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ResolverProvider(Protocol):
    """The Action Resolver's production face: the verdict, in the
    :class:`~elc.world.action.Adjudication` shape verbatim — the
    interpretation / outcome / actual_action / consequences /
    state_effects / participants / replan_scope the commit face writes.
    The provider is the verdict's *source*, fed the
    **world-authoritative** :class:`ResolverContext` (V3-8b, HIGH-2);
    the sole-adjudication authority (N-INV-002 / DOMAIN §20.3-1) is the
    commit face's unchanged.
    """

    def adjudicate(self, context: ResolverContext) -> Adjudication: ...


def pov_context_of(
    *,
    dossier: WorldSceneDossierRecord,
    context: SceneContext,
    segment_seq: int,
) -> PovContext:
    """Compile one segment's POV-safe provider input — **the hard door's
    physical form**.

    The signature is the door: the compilation can receive exactly two
    things, the scene's own Plan face (``dossier``) and one
    :class:`~elc.world.scene.SceneContext` — and a ``SceneContext`` is
    built for one POV (its ``pov_actor_id`` addressed the cognition /
    memory reads inside it). A context whose ``pov_actor_id`` does not
    address the dossier's POV is a corrupted call and raises
    ``ValueError`` (another viewer's read cannot be compiled into this
    dossier's input — the honest programmer-error arm, the
    :func:`elc.world.director.build_director_context` posture), never a
    silently mis-addressed context.
    """

    if context.pov_actor_id != dossier.pov_actor_id:
        raise ValueError(
            f"POV context of scene {dossier.scene_id!r} not compiled:"
            f" the context addresses {context.pov_actor_id!r} but the"
            f" dossier's POV is {dossier.pov_actor_id!r} — another"
            " viewer's read is not this dossier's input"
        )
    # The last-hop address check (the review's F2): the signature being
    # the door closes only when the two read faces inside the context are
    # addressed to the SAME viewer the context names — a mis-addressed
    # SceneContext (its cognition/memory read for another viewer) must
    # not compile into this POV's provider input.
    if context.cognition.viewer_id != context.pov_actor_id:
        raise ValueError(
            f"POV context of scene {dossier.scene_id!r} not compiled:"
            f" the cognition view is addressed to"
            f" {context.cognition.viewer_id!r}, not the POV"
            f" {context.pov_actor_id!r} — the read is another viewer's"
        )
    if context.memory.viewer_id != context.pov_actor_id:
        raise ValueError(
            f"POV context of scene {dossier.scene_id!r} not compiled:"
            f" the memory view is addressed to"
            f" {context.memory.viewer_id!r}, not the POV"
            f" {context.pov_actor_id!r} — the read is another viewer's"
        )
    return PovContext(
        scene_id=dossier.scene_id,
        segment_seq=segment_seq,
        pov_actor_id=dossier.pov_actor_id,
        participants=dossier.participants,
        place=dossier.place,
        entry_goals=dossier.entry_goals,
        exit_condition=dossier.exit_condition,
        revealable=dossier.revealable,
        must_hide=dossier.must_hide,
        current_tick=context.current_tick,
        cognition=context.cognition,
        memory=context.memory,
    )


class DeterministicFakeProvider:
    """The CI baseline's scripted stand-in for all four production
    faces — one class, four structural conformances.

    The script is configured at construction and echoed
    deterministically (the design's "端到端可重复、可测、CI 可跑"):

    - :meth:`write_segment` — ``prose`` keyed by the segment's own
      ``(scene_id, segment_seq)``; an unconfigured segment rides the
      echo template (still a pure function of the POV-safe context);
    - :meth:`plan_scene` — the configured ``scene_plan``, or the
      context's own element echoed;
    - :meth:`replan_element` — the configured ``replan_elements``
      consumed **in call order**, or the context's current content
      echoed;
    - :meth:`draft_blueprint` / :meth:`replan_blueprint` — the
      configured ``blueprints`` / ``replan_blueprints`` consumed in
      call order; the replan arm falls back to echoing the context's
      current blueprint, and the initial arm — with no content source
      at all — raises ``ValueError`` when unscripted (the script's gap
      is never papered over with an invented Blueprint);
    - :meth:`adjudicate` — the configured ruling **keyed by
      ``gate_id``**; a gate with no scripted ruling raises
      ``ValueError`` (an unscripted gate is the script's gap — the fake
      never invents a verdict).

    The deterministic baseline's honesty: this is **not** a language
    model and claims nothing literary; it is enough for a test — and
    for the V3-8 Gold Scenario wiring — to drive the full chain
    reproducibly. Every call is recorded, in call order, on the lists
    below; nothing here writes to the database or reads a clock.
    """

    def __init__(
        self,
        *,
        prose: Mapping[tuple[str, int], str] | None = None,
        scene_plan: Mapping[str, Any] | None = None,
        replan_elements: tuple[Mapping[str, Any], ...] = (),
        blueprints: tuple[Mapping[str, Any], ...] = (),
        replan_blueprints: tuple[Mapping[str, Any], ...] = (),
        adjudications: Mapping[str, Adjudication] | None = None,
    ) -> None:
        self._prose = dict(prose or {})
        self._scene_plan = (
            None if scene_plan is None else dict(scene_plan)
        )
        self._replan_elements = tuple(replan_elements)
        self._blueprints = tuple(blueprints)
        self._replan_blueprints = tuple(replan_blueprints)
        self._adjudications = dict(adjudications or {})
        self._element_cursor = 0
        self._draft_cursor = 0
        self._blueprint_cursor = 0
        self.segment_contexts: list[PovContext] = []
        self.plan_contexts: list[ScenePlanContext] = []
        self.replan_contexts: list[ScenePlanContext] = []
        self.blueprint_contexts: list[DirectorPlanContext] = []
        self.resolver_contexts: list[ResolverContext] = []

    # -- the Writer face -----------------------------------------------------

    def write_segment(self, context: PovContext) -> str:
        """One segment's scripted prose (see the class docstring)."""

        self.segment_contexts.append(context)
        body = self._prose.get((context.scene_id, context.segment_seq))
        if body is not None:
            return body
        return (
            f"segment {context.segment_seq} of {context.scene_id}:"
            f" {context.pov_actor_id} at {context.place} — the scene's"
            f" own goal: {context.entry_goals}"
        )

    # -- the Planner face ----------------------------------------------------

    def plan_scene(self, context: ScenePlanContext) -> Mapping[str, Any]:
        """The scene's plan content (see the class docstring)."""

        self.plan_contexts.append(context)
        if self._scene_plan is not None:
            return dict(self._scene_plan)
        return dict(context.element or {})

    def replan_element(self, context: ScenePlanContext) -> Mapping[str, Any]:
        """The SCENE arm's revised element (see the class docstring)."""

        self.replan_contexts.append(context)
        if self._element_cursor < len(self._replan_elements):
            element = self._replan_elements[self._element_cursor]
            self._element_cursor += 1
            return dict(element)
        return dict(context.element or {})

    # -- the Director face ---------------------------------------------------

    def draft_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]:
        """The initial Blueprint (see the class docstring); with no
        configured Blueprint left the fake has nothing to answer — the
        script's gap raises rather than inventing a plan."""

        self.blueprint_contexts.append(context)
        if self._draft_cursor < len(self._blueprints):
            payload = self._blueprints[self._draft_cursor]
            self._draft_cursor += 1
            return dict(payload)
        raise ValueError(
            f"blueprint of world {context.director_context.world_id!r} not"
            " scripted: the deterministic fake drafts configured blueprints"
            " only — an unscripted draft is the script's gap, never an"
            " invented plan"
        )

    def replan_blueprint(
        self, context: DirectorPlanContext
    ) -> Mapping[str, Any]:
        """The CHAPTER arm's revised Blueprint payload (see the class
        docstring)."""

        self.blueprint_contexts.append(context)
        if self._blueprint_cursor < len(self._replan_blueprints):
            payload = self._replan_blueprints[self._blueprint_cursor]
            self._blueprint_cursor += 1
            return dict(payload)
        if context.blueprint is None:
            raise ValueError(
                "chapter blueprint"
                f" {context.replan_request_id!r} not scripted: the"
                " deterministic fake replans configured payloads (or echoes"
                " the current one, absent here) only — the script's gap is"
                " never papered over with an invented plan"
            )
        return dict(context.blueprint)

    # -- the Resolver face ---------------------------------------------------

    def adjudicate(self, context: ResolverContext) -> Adjudication:
        """The scripted ruling for this gate (see the class docstring);
        an unscripted gate raises ``ValueError`` — the fake does not
        invent verdicts."""

        self.resolver_contexts.append(context)
        ruling = self._adjudications.get(context.gate_id)
        if ruling is None:
            raise ValueError(
                f"adjudication of gate {context.gate_id!r} not scripted:"
                " the deterministic fake answers configured rulings only"
                " — the script's gap is never papered over with an"
                " invented verdict"
            )
        return ruling
