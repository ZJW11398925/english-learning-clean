"""The two supply-side adjudications (P7-2): content readiness and prerequisites.

A candidate is not a candidate until two questions are answered, and this module
is where they are answered with a *read* rather than a guess:

1. **Is the target's content ready?** — docs/PRODUCT_CONTRACT.md §8.1's R0–R4
   ladder, read through the face P5-1 landed
   (:meth:`elc.curriculum.store.CurriculumContentStore.readiness`) and judged by
   the pure ladder in :mod:`elc.curriculum.readiness`. This module adds no rule
   of its own: it converts one answer into the Planner's own vocabulary
   (:class:`elc.planner.kernel.ReadinessLevel`, the *same* ladder) or reports
   that there is no level to convert.
2. **Are the target's prerequisites met?** — BF-02 §11's four-word contract
   (:class:`~elc.planner.kernel.PrerequisiteState`), judged over the curriculum
   graph (:meth:`…store.prerequisites_of`) and the §11 learner state.

**Missing is not zero, and missing is not READY.** The two rules this module
exists to keep are BF-02 §5's ("missing authority → no number") read one domain
over, and P5-R's ("a candidate mapping is not a mapping any Planner may act
on"):

- a target whose ladder answer is *no level* yields ``level=None`` and is
  **not usable**: the generator refuses to emit it, and the caller's context
  assembly reports ``CURRICULUM_READINESS`` missing (P7-0's own leg). Nothing
  here substitutes ``R3`` for "unknown" — the ladder still answers ``None``
  for the five capability targets whose sources state no evidence (C2's
  answer for them; its twenty-eight R4 resource targets read through
  unchanged);
- a prerequisite that cannot be *judged* is not a prerequisite that is
  *satisfied*. BF-02 §11's ``UNKNOWN`` is the word for "not judged", the kernel
  hard-excludes ``UNKNOWN`` unless the candidate is a probe or carries a
  scaffold, and this module never turns it into ``READY``.

**Which node a target's prerequisites are read from.** §7 makes Curriculum own
the graph and the registry, and the repository serves two different reads:

- a **CAPABILITY** target *is* its own curriculum node — P5-0's registry rule is
  "一个 capability 一个节点，节点 id = capability id" (curriculum/README.md C1),
  so the node is read from the registry itself
  (:meth:`…store.get_capability`) and no mapping is involved;
- a **RESOURCE** target's node comes from its §24.7 ``REALIZES`` link
  (:meth:`…store.curriculum_links_of`), and that link carries an
  ``editorial_status``. This cut reads only a link whose status is
  :data:`APPROVED_LINK_EDITORIAL_STATUS` — the same gate P5-R put on capability
  credit (``elc.content.store.CAPABILITY_CREDIT_EDITORIAL_STATUS``)
  — because acting on an unapproved mapping to *find* prerequisites is still
  acting on it. A resource with no approved link has no readable curriculum
  standing, and its answer is ``UNKNOWN`` (**registered judgement**, not a
  quotation): the shipped corpus maps twenty-eight resources, every link
  approved (C2's editorial review; before it, C1's single approval was the
  one exception in a ``CURRICULUM_MAPPED`` corpus), so the ``UNKNOWN``
  answer has no reachable case on this corpus today — it remains the
  fail-closed reading for any future unapproved row.
  Revisit: the curriculum review approves the links (the content-side 补课 P5
  registered), or canonical text says what a target outside the approved graph
  requires.

**Which edges are this node's.** The §7 graph face is served by
:meth:`elc.curriculum.store.CurriculumContentStore.prerequisites_of`, and its
query is ``WHERE from_node = ? OR to_node = ?`` with no ``edge_type`` filter —
so the tuple it returns holds three kinds of edge: the node's own incoming
``PREREQUISITE_FOR`` edges (the declared prerequisites), outgoing edges where
the node is the *from* side (the node is someone else's prerequisite), and
edges of §7's other ten types. Only the first kind says what this node
requires, so this cut filters to it before judging anything
(:func:`_is_a_prerequisite_of`). Judging an out-edge would read the node's own
state as a verdict about itself — a false ``BLOCKED``/``UNKNOWN`` word for a
target that simply has no declared prerequisite — and judging a ``SUPPORTS``
edge would read §7's other relations as requirements the graph never declared.
Today's ``curriculum/prerequisites.json`` (``{"edges": []}``) keeps both
shapes unexercised rather than correct. The filter narrows the set the face
answers with, and the reading is registered: a face that answers in-edges only
(the content domain's own narrowing) or canonical text that gives another edge
type prerequisite force re-opens it.

**What "met" means, and why only one word decides it.** BF-02 §11 pins the
scaffold contract and no mastery rule, so this cut reads the one word the
estimator already publishes: BF-01 §25's ``CONFIRMED_GAP`` flag (with §26's own
reference thresholds behind it) and BF-01 §25's ``INSUFFICIENT_EVIDENCE`` — "the
evidence does not support a state" — which is *not* evidence that the
prerequisite is met either. That flag is read **two ways** in this repository,
and both readings fail closed with only §11's word differing: here it is read
as *proven unmet* (a ``HARD`` edge carrying it is ``BLOCKED``), while
:mod:`elc.planner.candidates`' probe condition reads it as "no state to judge"
(``UNKNOWN``'s family, "a probe may resolve this") — registered in that
module's section on the fields beside the priced vector. A prerequisite node is
therefore **proven** when its §11 state exists and carries neither flag. A
prerequisite that is not proven is unmet for a ``HARD`` edge (``BLOCKED`` when a
state exists and names the gap, and ``UNKNOWN`` when there is no state at all —
"we cannot tell" is not "we know it is wrong") and scaffoldable for a
``SCAFFOLDABLE`` edge (``READY_WITH_SCAFFOLD``). BF-02 §11 lists **two** shapes
that must carry scaffold cost (``READY_WITH_SCAFFOLD`` *or* ``UNKNOWN`` +
``prerequisite_scaffoldable``), and the fold below keeps both visible: when a
``HARD`` edge is unjudged *and* a ``SCAFFOLDABLE`` edge is unmet, the answer is
``UNKNOWN`` with ``scaffoldable=True`` rather than ``READY_WITH_SCAFFOLD``, so
the HARD edge's "not judged" state does not disappear from the word. The
difference is the trace's, not the behaviour's: the kernel's hard rules admit
the ``UNKNOWN`` + scaffoldable pair exactly as they admit
``READY_WITH_SCAFFOLD`` (same exclusion outcome) and its scaffold floor reads
the pair identically. ``SOFT`` is carried and priced by nothing: BF-02 §11's
four words have no cell for it, and a soft prerequisite cannot hard-exclude —
registered, with the revisit "canonical text gives SOFT a behaviour".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from elc.curriculum.readiness import ReadinessAssessment
from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
    CurriculumEdgeType,
    CurriculumLinkRecord,
    PrerequisiteStrength,
)
from elc.planner.kernel import PrerequisiteState, ReadinessLevel
from elc.platform.types import (
    CapabilityId,
    CurriculumNodeId,
    DomainErrorCode,
    Err,
    EvidenceModality,
    ResourceId,
    Result,
    TargetId,
)

__all__ = [
    "APPROVED_LINK_EDITORIAL_STATUS",
    "CONFIRMED_GAP_FLAG",
    "INSUFFICIENT_EVIDENCE_FLAG",
    "REALIZES_RELATION",
    "LearnerStatePort",
    "PrerequisiteOutcome",
    "PrerequisitePort",
    "ReadinessOutcome",
    "ReadinessPort",
    "prerequisite_state_of",
    "readiness_of_target",
]

#: The §24.11 editorial status a curriculum link must carry before a consumer
#: may act on it. The same word is declared once in the content domain
#: (:data:`elc.content.store.CAPABILITY_CREDIT_EDITORIAL_STATUS`, where P5-R
#: put it) — this module keeps its own spelling rather than importing a store
#: module into the Planner's import graph, and a test pins the two equal.
APPROVED_LINK_EDITORIAL_STATUS = "CANONICAL_APPROVED"

#: The §24.7 relation that names a resource's curriculum node.
REALIZES_RELATION = "REALIZES"

#: The two BF-01 §25 flags that make a prerequisite *not proven*
#: (:data:`elc.learning.estimator.ALLOWED_LEARNING_FLAGS` carries the full
#: seven-word list; a test pins these two members).
CONFIRMED_GAP_FLAG = "CONFIRMED_GAP"
INSUFFICIENT_EVIDENCE_FLAG = "INSUFFICIENT_EVIDENCE"


# -- the read faces ----------------------------------------------------------


class ReadinessPort(Protocol):
    """§8.1's ladder as a read: one target in, one assessment out.

    Satisfied structurally by
    :class:`elc.curriculum.store.CurriculumContentStore` — the same method the
    P5-1 read face exposes, so no adapter stands between the Planner and the
    ladder.
    """

    def readiness(self, entity_id: str) -> Result[ReadinessAssessment]:
        ...


class PrerequisitePort(Protocol):
    """The three curriculum-graph reads the resolver consumes.

    Satisfied structurally by :class:`elc.curriculum.store.CurriculumContentStore`
    (the P5-1 read face): the registry for a capability node, the §24.7 links
    for a resource's node, and the §7 prerequisite edges for a node. The edge
    read is **not** an in-edge-only read on the shipped face (``from_node = ?
    OR to_node = ?``, no ``edge_type`` filter), so this resolver filters what it
    judges rather than assuming the face did — see the module docstring.
    """

    def get_capability(
        self, capability_id: CapabilityId
    ) -> Result[CapabilityNodeRecord]:
        ...

    def curriculum_links_of(
        self, resource_id: ResourceId
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        ...

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        ...


class LearnerStatePort(Protocol):
    """The §11 state read BF-02 §11's "proven" test consumes.

    Satisfied structurally by
    :class:`elc.learning.controller.LearningController` (same method, same
    signature: ``target_id`` × ``evidence_modality``); the *target_type* leg of
    the state key is deliberately not asked about, because a curriculum node is
    looked up as a capability target and the method's own key decides what it
    answers.
    """

    def get_learner_target_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[object | None]:
        ...


# -- ① content readiness -----------------------------------------------------


@dataclass(frozen=True)
class ReadinessOutcome:
    """One target's §8.1 answer, with the evidence behind it.

    ``level is None`` is the honest "no level" the ladder reports for a corpus
    that carries none of the facts a level requires — not an error and not a
    default. ``blocking_keys`` names the ladder's own missing keys at the
    lowest unreached level, so a reader can see *why* without re-judging.
    """

    target_id: str
    level: ReadinessLevel | None
    blocking_keys: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def usable(self) -> bool:
        """Whether a candidate may carry this target at all."""

        return self.level is not None


def readiness_of_target(
    target_id: str, readiness: ReadinessPort | None
) -> ReadinessOutcome:
    """The §8.1 level of one target, or the honest reasons there is none.

    Three shapes, and none of them invents a level:

    - no ladder face at all → no level ("no authority" is not "R3");
    - the face answers ``Err`` → no level, with the failure carried through
      (an unreadable artifact is not a target without content);
    - the face answers an assessment → its level, converted into the Planner's
      own vocabulary, or none, with the ladder's blocking keys.
    """

    if readiness is None:
        return ReadinessOutcome(
            target_id=target_id,
            level=None,
            blocking_keys=(),
            reasons=(
                "no §8.1 readiness face: a candidate's level cannot be read,"
                " and no word in the ladder means 'unknown' — §8.1 has no"
                " level under R0, so this is a refusal and not an R0",
            ),
        )
    assessment = readiness.readiness(target_id)
    if isinstance(assessment, Err):
        return ReadinessOutcome(
            target_id=target_id,
            level=None,
            blocking_keys=(),
            reasons=(
                "the §8.1 face could not answer for this target"
                f" ({assessment.error.code.value}): an unreadable ladder is"
                " not a ready target",
            ),
        )
    judged = assessment.value
    if judged.level is None:
        return ReadinessOutcome(
            target_id=target_id,
            level=None,
            blocking_keys=judged.missing_keys,
            reasons=(
                "no §8.1 level: the ladder reports the target blocked at"
                f" {judged.next_level} by"
                f" {', '.join(judged.missing_keys) or 'no named fact'}"
                " — §8.1 defines no level under R0, so the candidate is not"
                " usable rather than rounded down",
            ),
        )
    return ReadinessOutcome(
        target_id=target_id,
        level=ReadinessLevel(judged.level),
        blocking_keys=(),
        reasons=(
            f"§8.1 level {judged.level} (the ladder's own answer, converted"
            " into the Planner's vocabulary)",
        ),
    )


# -- ② prerequisites ---------------------------------------------------------


@dataclass(frozen=True)
class PrerequisiteOutcome:
    """BF-02 §11's answer for one target, with the graph it was read from.

    ``scaffoldable`` is only ever true when the graph says so (a
    ``SCAFFOLDABLE`` edge was left unsatisfied) — a missing graph does not make
    a candidate scaffoldable, it makes its prerequisites unknown.
    """

    state: PrerequisiteState
    scaffoldable: bool
    nodes: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def hard_blocked(self) -> bool:
        return self.state is PrerequisiteState.BLOCKED


def _nodes_of(
    target_type: str, target_id: str, prerequisites: PrerequisitePort
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(nodes, reasons)`` — the curriculum node(s) a target is read through.

    A capability target is its own node (the registry's own rule); a resource
    target's node is the ``REALIZES`` link's, and only an approved link counts.
    """

    if target_type == "CAPABILITY":
        declared = prerequisites.get_capability(CapabilityId(target_id))
        if isinstance(declared, Err):
            if declared.error.code is DomainErrorCode.NOT_FOUND:
                return (), (
                    f"{target_id}: the capability registry does not declare"
                    " this node — the target's curriculum standing cannot be"
                    " read",
                )
            return (), (
                f"{target_id}: the capability registry could not be read"
                f" ({declared.error.code.value})",
            )
        return (str(declared.value.curriculum_node_id),), (
            f"{target_id}: its own registry node (a capability target is the"
            " node — curriculum README C1)",
        )

    links = prerequisites.curriculum_links_of(ResourceId(target_id))
    if isinstance(links, Err):
        return (), (
            f"{target_id}: the §24.7 link face could not be read"
            f" ({links.error.code.value})",
        )
    approved = [
        link
        for link in links.value
        if link.relation.value == REALIZES_RELATION
        and link.editorial_status == APPROVED_LINK_EDITORIAL_STATUS
    ]
    if not approved:
        carried = sorted(
            {
                link.editorial_status
                for link in links.value
                if link.relation.value == REALIZES_RELATION
            }
        )
        detail = (
            f"carries {', '.join(carried)} links" if carried else "carries none"
        )
        return (), (
            f"{target_id}: no §24.7 REALIZES link with editorial status"
            f" {APPROVED_LINK_EDITORIAL_STATUS} ({detail}) — a candidate"
            " mapping is not a mapping this resolver may act on (P5-R), so the"
            " target's prerequisites are UNKNOWN rather than absent",
        )
    return tuple(str(link.node_id) for link in approved), (
        f"{target_id}: {len(approved)} approved REALIZES link(s) read",
    )


#: The three answers one prerequisite node's state can give: proven met, proven
#: unmet, or nobody could be asked. The distinction is load-bearing — "unmet"
#: and "unjudged" lead to different §11 words for a HARD edge
#: (``BLOCKED`` vs ``UNKNOWN``).
_VERDICT_PROVEN = "PROVEN"
_VERDICT_UNMET = "UNMET"
_VERDICT_UNJUDGED = "UNJUDGED"


def _judge(
    node_id: str,
    modality: EvidenceModality,
    learner_state: LearnerStatePort | None,
) -> tuple[str, str]:
    """``(verdict, reason)`` for one curriculum node's prerequisite.

    The rule is the module docstring's: a state that exists and carries neither
    ``CONFIRMED_GAP`` nor ``INSUFFICIENT_EVIDENCE`` is proof enough for a
    prerequisite; a state that exists and carries one of them is proof that it
    is *not* met; and no state (or no face to ask) is not proof of either.
    """

    if learner_state is None:
        return _VERDICT_UNJUDGED, (
            f"{node_id}: no §11 learner-state face, so the prerequisite cannot"
            " be judged (and 'not judged' is not 'met')"
        )
    state = learner_state.get_learner_target_state(TargetId(node_id), modality)
    if isinstance(state, Err):
        return _VERDICT_UNJUDGED, (
            f"{node_id}: the §11 state read failed"
            f" ({state.error.code.value}) — not judged, not met"
        )
    if state.value is None:
        return _VERDICT_UNJUDGED, (
            f"{node_id}: never observed (no §11 state row) — a prerequisite"
            " with no evidence behind it is not a met prerequisite"
        )
    blocking = sorted(
        flag
        for flag in _flags_of(state.value)
        if flag in (CONFIRMED_GAP_FLAG, INSUFFICIENT_EVIDENCE_FLAG)
    )
    if blocking:
        return _VERDICT_UNMET, (
            f"{node_id}: BF-01's own flags say the evidence does not support"
            f" this: {', '.join(blocking)}"
        )
    return _VERDICT_PROVEN, (
        f"{node_id}: a §11 state without a blocking BF-01 flag"
    )


def _flags_of(state: object) -> tuple[str, ...]:
    """The ``learning_flags`` of a §11 state record, read defensively.

    The record arrives through a structural port whose only guaranteed field is
    ``projection``; a state shape without the flags answers the empty tuple,
    which reads as "no flag blocks" — never as a licence to pass: the caller
    that typed the port is the one that promises the field, and a state without
    flags cannot be *proven* by them either way, so the flag test is applied to
    what the record carries and nothing is inferred from its absence.
    """

    projection = getattr(state, "projection", None)
    flags = getattr(projection, "learning_flags", ()) if projection else ()
    return tuple(str(flag) for flag in flags)


def _is_a_prerequisite_of(edge: CurriculumEdgeRecord, node: str) -> bool:
    """Whether one edge the §7 face returned is *this node's* prerequisite.

    The shipped face answers ``WHERE from_node = ? OR to_node = ?`` and filters
    no ``edge_type`` (see the module docstring), so an edge the node is the
    *from* side of — the node is someone else's prerequisite — arrives in the
    same tuple as the node's own declared prerequisites, and so does an edge of
    any of §7's other ten types. Only an incoming ``PREREQUISITE_FOR`` edge
    declares what this node requires, and this predicate is that test.
    """

    return (
        edge.edge_type is CurriculumEdgeType.PREREQUISITE_FOR
        and str(edge.to_node) == node
    )


def prerequisite_state_of(
    target_type: str,
    target_id: str,
    modality: EvidenceModality,
    *,
    prerequisites: PrerequisitePort | None,
    learner_state: LearnerStatePort | None,
) -> PrerequisiteOutcome:
    """BF-02 §11's four-word answer for one target.

    The fold, in one place: only the target node's own incoming
    ``PREREQUISITE_FOR`` edges are judged (:func:`_is_a_prerequisite_of` — the
    face answers out-edges and other edge types too); a ``HARD`` edge that is
    not proven blocks (``BLOCKED`` when the evidence says so, ``UNKNOWN`` when
    nothing can be judged); an unproven ``SCAFFOLDABLE`` edge makes the
    candidate ``READY_WITH_SCAFFOLD`` — the state BF-02 §11 prices, unless a
    ``HARD`` edge is *also* unjudged, in which case the answer keeps that word
    as ``UNKNOWN`` with ``scaffoldable=True`` (§11's second shape, module
    docstring); a ``SOFT`` edge changes nothing (registered); and when the
    graph declares no edge for any of the target's nodes, the answer is
    ``READY`` — "this node has no declared prerequisite" is a read, not a
    default.
    """

    if prerequisites is None:
        return PrerequisiteOutcome(
            state=PrerequisiteState.UNKNOWN,
            scaffoldable=False,
            nodes=(),
            reasons=(
                "no curriculum-graph face: the target's prerequisites cannot be"
                " read at all, which is §11's UNKNOWN and never a READY",
            ),
        )
    nodes, node_reasons = _nodes_of(target_type, target_id, prerequisites)
    if not nodes:
        return PrerequisiteOutcome(
            state=PrerequisiteState.UNKNOWN,
            scaffoldable=False,
            nodes=(),
            reasons=node_reasons,
        )

    reasons: list[str] = list(node_reasons)
    edge_count = 0
    blocked = False
    unknown = False
    scaffold = False
    for node in nodes:
        edges = prerequisites.prerequisites_of(CurriculumNodeId(node))
        if isinstance(edges, Err):
            return PrerequisiteOutcome(
                state=PrerequisiteState.UNKNOWN,
                scaffoldable=False,
                nodes=nodes,
                reasons=(
                    *reasons,
                    f"{node}: the §7 edge face could not be read"
                    f" ({edges.error.code.value})",
                ),
            )
        skipped = 0
        for edge in edges.value:
            if not _is_a_prerequisite_of(edge, node):
                skipped += 1
                continue
            edge_count += 1
            strength = _strength_of(edge)
            if strength is PrerequisiteStrength.SOFT:
                reasons.append(
                    f"{node}: a SOFT edge from {edge.from_node} is carried and"
                    " priced by nothing (BF-02 §11's four words have no cell"
                    " for it)"
                )
                continue
            verdict, why = _judge(str(edge.from_node), modality, learner_state)
            if verdict == _VERDICT_PROVEN:
                reasons.append(f"{why} — the prerequisite stands")
                continue
            reasons.append(why)
            if strength is PrerequisiteStrength.SCAFFOLDABLE:
                scaffold = True
            elif verdict == _VERDICT_UNMET:
                blocked = True
            else:
                unknown = True
        if skipped:
            reasons.append(
                f"{node}: {skipped} edge(s) the §7 face returned are not this"
                " node's own prerequisites (an out-edge — the node is someone"
                " else's prerequisite — or one of §7's other edge types) and"
                " were not judged"
            )

    if edge_count == 0:
        reasons.append(
            f"{target_id}: the graph declares no prerequisite edge for"
            f" {', '.join(nodes)} — READY is a read of an empty declared set,"
            " not a default"
        )
        return PrerequisiteOutcome(
            state=PrerequisiteState.READY,
            scaffoldable=False,
            nodes=nodes,
            reasons=tuple(reasons),
        )
    if blocked:
        return PrerequisiteOutcome(
            state=PrerequisiteState.BLOCKED,
            scaffoldable=False,
            nodes=nodes,
            reasons=tuple(reasons),
        )
    if scaffold and unknown:
        # BF-02 §11's second shape: the HARD edge nobody could judge keeps its
        # word, and the scaffold is carried beside it (the kernel's exclusion
        # rule and scaffold floor read this pair exactly like
        # READY_WITH_SCAFFOLD).
        return PrerequisiteOutcome(
            state=PrerequisiteState.UNKNOWN,
            scaffoldable=True,
            nodes=nodes,
            reasons=tuple(reasons),
        )
    if scaffold:
        return PrerequisiteOutcome(
            state=PrerequisiteState.READY_WITH_SCAFFOLD,
            scaffoldable=True,
            nodes=nodes,
            reasons=tuple(reasons),
        )
    if unknown:
        return PrerequisiteOutcome(
            state=PrerequisiteState.UNKNOWN,
            scaffoldable=False,
            nodes=nodes,
            reasons=tuple(reasons),
        )
    return PrerequisiteOutcome(
        state=PrerequisiteState.READY,
        scaffoldable=False,
        nodes=nodes,
        reasons=tuple(reasons),
    )


def _strength_of(edge: CurriculumEdgeRecord) -> PrerequisiteStrength:
    """An edge's declared strength.

    §7's strength vocabulary is HARD / SOFT / SCAFFOLDABLE and the column is
    nullable (§24.7 carries ``strength?`` for links and §7's three words for
    prerequisite edges): an edge with no declared strength is read as the
    strictest non-scaffoldable case — the FAIL-CLOSED direction, declared in
    the module docstring — so an unlabelled prerequisite can block but never
    silently scaffold.
    """

    if edge.prerequisite_strength is None:
        return PrerequisiteStrength.HARD
    return edge.prerequisite_strength
