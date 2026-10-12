"""The Narrative V3 provider protocol face (V3-8a, TASK-OPI-06b954e0…4 /
the opening ruling ``DEC-OPI-06b954e0-…2``; RA §27's "provider 协议面"
paragraph; DOMAIN §20.2's second row) — the three production faces the
pipeline orchestrator calls through, and the deterministic fake the CI
baseline drives them with.

**The three faces, spelled as Protocols**: Writer（正文）/
:class:`WriterProvider` — one segment's prose from its POV-safe context;
Planner（dossier 内容）/:class:`PlannerProvider` — the scene's plan
content, the SCENE arm's revised element and the CHAPTER arm's revised
blueprint; Resolver（裁定）/:class:`ResolverProvider` — the verdict, in
the ``Adjudication`` shape :mod:`elc.world.action` froze. The structural
contracts are deliberately narrow: the orchestrator calls through them
(DOMAIN §20.2's「管线驱动顺序」row), and **the Resolver's sole
adjudication authority is not loosened by the indirection** — the
protocol is only *where the verdict comes from*; ``commit_action``
still writes ``world_event`` / ``world_state_fact`` **only** from the
returned :class:`~elc.world.action.Adjudication` (N-INV-002 /
DOMAIN §20.3-1 unchanged).

**The POV-safe context compilation hard door** (V3-5R's registered
obligation, TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11's item 5) takes
physical form in this module: the provider inputs are assembled by
:func:`pov_context_of` — and its **signature is the door** — from
exactly two faces: the scene's own Plan face (the adopted dossier) and
the **POV's own** :class:`~elc.world.scene.SceneContext` (the V3-5R
cognition/memory read the Scene Planner assembled for *this* dossier's
POV). The input dataclasses below (:class:`PovContext` /
:class:`AdjudicationContext` / :class:`ScenePlanContext` /
:class:`ChapterPlanContext`) carry no field another participant's
private face could ride in on — a compiled context can only say what
the POV could see. The lexical ``must_hide`` guard in
:class:`~elc.world.writer.PovWriter` stays the second, deterministic
guard it honestly is (a semantic rewrite routes around a lexical guard
by construction); the real LLM wiring — reusing the persona provider /
validator / streaming basis (design §9.1) — is the explicit step before
the user's "好玩" acceptance, and this door is its precondition.

**The deterministic fake** (:class:`DeterministicFakeProvider`): one
class satisfying all three Protocols structurally — the CI baseline's
scripted stand-in. It opens no connection, writes nothing, consults no
clock: the prose, the plan content and the verdicts are configured
per construction and echoed deterministically (the Writer face's
default is an echo-with-template; the plan faces echo the context's own
content unless configured otherwise; the Resolver face answers the
configured ruling **keyed by ``gate_id``** — an unscripted gate is an
honest ``ValueError``, the store family's corrupted-call posture, never
an invented ruling). Every call is recorded in deterministic order
(``segment_contexts`` / ``plan_contexts`` / ``replan_contexts`` /
``blueprint_contexts`` / ``adjudication_contexts``) — the POV-safe pins
read the recordings to prove what the provider could see.

Discipline: the module is a leaf — it imports nothing from ``elc`` at
runtime (the annotation imports ride ``TYPE_CHECKING``; the contexts are
value shapes and the fake's script is plain data), manages no
transaction, builds no SQL and holds no clock. The record types and the
fake are frozen/value or plainly recorded; the one ``raise`` is the
unscripted-gate arm above.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # the annotation-only edges (the module stays a leaf)
    from elc.world.action import Adjudication
    from elc.world.cognition import V3CognitionView
    from elc.world.memory import V3MemoryView
    from elc.world.narrative.types import WorldSceneDossierRecord
    from elc.world.scene import SceneContext

__all__ = [
    "AdjudicationContext",
    "ChapterPlanContext",
    "DeterministicFakeProvider",
    "PlannerProvider",
    "PovContext",
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
class AdjudicationContext:
    """The Resolver provider's input for one submission — the user's own
    submission (intent and option, durable on the ``user_action`` row)
    beside the same POV-safe faces :class:`PovContext` carries.

    ``pov_actor_id`` / ``cognition`` / ``memory`` are the ruled scene's
    POV's own read (the ruling is the *world's* answer, seen from the
    scene it happens in — the ``SceneContext.pov_actor_id`` equals the
    view's ``viewer_id`` by construction); ``options`` are the gate's
    recorded options.
    """

    gate_id: str
    scene_id: str
    submission_id: str
    intent_text: str
    selected_option: str | None
    options: tuple[str, ...]
    pov_actor_id: str
    participants: tuple[str, ...]
    current_tick: int
    cognition: V3CognitionView
    memory: V3MemoryView


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
class ChapterPlanContext:
    """The Planner provider's POV-safe input for one chapter replan (the
    CHAPTER arm).

    ``blueprint`` is the chapter's current adopted Blueprint as a
    mapping (the Plan face's own semantic fields verbatim — the payload
    shape ``Director.apply_action_replan`` re-validates); the
    ``pov_actor_id`` / ``cognition`` / ``memory`` arms are the ruling's
    own scene's POV read, exactly like :class:`ScenePlanContext`.
    """

    world_id: str
    chapter_id: str
    scene_id: str
    pov_actor_id: str
    current_tick: int
    blueprint: Mapping[str, Any]
    cognition: V3CognitionView
    memory: V3MemoryView


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
    """The Scene Planner's production face: the scene's plan content,
    and the two replan arms the ruling's ``replan_scope`` reaches
    through the durable obligation.

    - :meth:`plan_scene` — the scene's dossier content (the LLM planner
      cut's landing seat; the deterministic chain's dossier seat is
      :meth:`elc.world.scene.ScenePlanner.open_scene`'s element-verbatim
      assembly, and the protocol is the contract the LLM cut wires);
    - :meth:`replan_element` — the SCENE arm's revised element, consumed
      by :meth:`elc.world.scene.ScenePlanner.replan_scene`;
    - :meth:`replan_blueprint` — the CHAPTER arm's revised Blueprint
      payload, consumed by
      :meth:`elc.world.director.Director.apply_action_replan` (the
      Director's own LLM production face is registered with the later
      wiring; this is the protocol seat it will answer through).

    Every method answers a mapping; the library faces validate it (the
    ``_checked_fields`` / ``validate_blueprint`` families) — a bad plan
    content is refused by the seat that consumes it, not blessed here.
    """

    def plan_scene(self, context: ScenePlanContext) -> Mapping[str, Any]: ...

    def replan_element(
        self, context: ScenePlanContext
    ) -> Mapping[str, Any]: ...

    def replan_blueprint(
        self, context: ChapterPlanContext
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ResolverProvider(Protocol):
    """The Action Resolver's production face: the verdict, in the
    :class:`~elc.world.action.Adjudication` shape verbatim — the
    interpretation / outcome / actual_action / consequences /
    state_effects / participants / replan_scope the commit face writes.
    The provider is the verdict's *source*; the sole-adjudication
    authority (N-INV-002 / DOMAIN §20.3-1) is the commit face's
    unchanged.
    """

    def adjudicate(self, context: AdjudicationContext) -> Adjudication: ...


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
    """The CI baseline's scripted stand-in for all three production
    faces — one class, three structural conformances.

    The script is configured at construction and echoed
    deterministically (the design's "端到端可重复、可测、CI 可跑"):

    - :meth:`write_segment` — ``prose`` keyed by the segment's own
      ``(scene_id, segment_seq)``; an unconfigured segment rides the
      echo template (still a pure function of the POV-safe context);
    - :meth:`plan_scene` — the configured ``scene_plan``, or the
      context's own element echoed;
    - :meth:`replan_element` / :meth:`replan_blueprint` — the configured
      tuples consumed **in call order**, or the context's current
      content echoed;
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
        replan_blueprints: tuple[Mapping[str, Any], ...] = (),
        adjudications: Mapping[str, Adjudication] | None = None,
    ) -> None:
        self._prose = dict(prose or {})
        self._scene_plan = (
            None if scene_plan is None else dict(scene_plan)
        )
        self._replan_elements = tuple(replan_elements)
        self._replan_blueprints = tuple(replan_blueprints)
        self._adjudications = dict(adjudications or {})
        self._element_cursor = 0
        self._blueprint_cursor = 0
        self.segment_contexts: list[PovContext] = []
        self.plan_contexts: list[ScenePlanContext] = []
        self.replan_contexts: list[ScenePlanContext] = []
        self.blueprint_contexts: list[ChapterPlanContext] = []
        self.adjudication_contexts: list[AdjudicationContext] = []

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

    def replan_blueprint(
        self, context: ChapterPlanContext
    ) -> Mapping[str, Any]:
        """The CHAPTER arm's revised Blueprint payload (see the class
        docstring)."""

        self.blueprint_contexts.append(context)
        if self._blueprint_cursor < len(self._replan_blueprints):
            payload = self._replan_blueprints[self._blueprint_cursor]
            self._blueprint_cursor += 1
            return dict(payload)
        return dict(context.blueprint)

    # -- the Resolver face ---------------------------------------------------

    def adjudicate(self, context: AdjudicationContext) -> Adjudication:
        """The scripted ruling for this gate (see the class docstring);
        an unscripted gate raises ``ValueError`` — the fake does not
        invent verdicts."""

        self.adjudication_contexts.append(context)
        ruling = self._adjudications.get(context.gate_id)
        if ruling is None:
            raise ValueError(
                f"adjudication of gate {context.gate_id!r} not scripted:"
                " the deterministic fake answers configured rulings only"
                " — the script's gap is never papered over with an"
                " invented verdict"
            )
        return ruling
