"""P7-2 ⑤ — the two supply-side gates: §8.1 content readiness and BF-02 §11
prerequisites, over the real faces and over declared graphs.

Two worlds are used, and the difference is named in every test that uses one:

- the **shipped world** — the content.db this repository's authoring trees
  build, read through the real P5-1 face — which is where the "no level" and
  "no approved link" answers are the truth about the corpus rather than a
  fixture's convenience;
- a **declared world** — a graph or a learner state handed in through the same
  structural ports — for the shapes the corpus does not carry (a hard
  prerequisite, a scaffoldable one, a confirmed gap). Those declarations are
  BF-02 §20's own "complete input" convention: the ladder and the resolver are
  what is under test, not the corpus.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from elc.curriculum.readiness import (
    ReadinessAssessment,
    ReadinessFacts,
    judge_readiness,
)
from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
    CurriculumEdgeType,
    CurriculumLinkRecord,
    CurriculumLinkRelation,
    PrerequisiteStrength,
)
from elc.learning.types import (
    LearnerCoverage,
    LearnerDimensionState,
    LearnerFreshness,
    LearnerProjection,
    LearnerTargetStateRecord,
)
from elc.planner.kernel import PrerequisiteState, ReadinessLevel
from elc.planner.supply import (
    APPROVED_LINK_EDITORIAL_STATUS,
    CONFIRMED_GAP_FLAG,
    INSUFFICIENT_EVIDENCE_FLAG,
    REALIZES_RELATION,
    prerequisite_state_of,
    readiness_of_target,
)
from elc.platform.types import (
    CapabilityId,
    CurriculumNodeId,
    DomainError,
    DomainErrorCode,
    Err,
    EvidenceModality,
    Ok,
    ResourceId,
    Result,
    TargetId,
)

NODE = "cap-eval-hedged-opinion"
OTHER_NODE = "cap-interact-backchannel"
MODALITY = EvidenceModality.TEXT_PRODUCTION


# -- declared ports ----------------------------------------------------------


class DeclaredGraph:
    """A curriculum graph handed in through the resolver's own port shape.

    ``links`` / ``edges`` / ``capabilities`` are what a test declares; the
    methods answer exactly as :class:`elc.curriculum.store.CurriculumContentStore`
    does (same signatures, same ``Result`` shape), so the resolver cannot tell
    one from the other — which is the point of a structural port.
    """

    def __init__(
        self,
        *,
        capabilities: Sequence[str] = (),
        links: Sequence[CurriculumLinkRecord] = (),
        edges: Sequence[CurriculumEdgeRecord] = (),
        broken: DomainErrorCode | None = None,
    ) -> None:
        self._capabilities = set(capabilities)
        self._links = tuple(links)
        self._edges = tuple(edges)
        self._broken = broken

    def _error(self) -> Err[object] | None:
        if self._broken is None:
            return None
        return Err(DomainError(code=self._broken, message="declared failure"))

    def get_capability(
        self, capability_id: CapabilityId
    ) -> Result[CapabilityNodeRecord]:
        failure = self._error()
        if failure is not None:
            return failure
        if str(capability_id) not in self._capabilities:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=f"no capability {capability_id!r}",
                )
            )
        return Ok(
            CapabilityNodeRecord(
                curriculum_node_id=CurriculumNodeId(str(capability_id)),
                capability_id=CapabilityId(str(capability_id)),
                family="EVAL",
                level=2,
            )
        )

    def curriculum_links_of(
        self, resource_id: ResourceId
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        failure = self._error()
        if failure is not None:
            return failure
        return Ok(
            tuple(
                link
                for link in self._links
                if str(link.resource_id) == str(resource_id)
            )
        )

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        failure = self._error()
        if failure is not None:
            return failure
        return Ok(
            tuple(
                edge
                for edge in self._edges
                if str(edge.to_node) == str(node_id)
            )
        )


class RealFaceGraph(DeclaredGraph):
    """The same declared graph, answered the way the *shipped* face answers it.

    :meth:`elc.curriculum.store.CurriculumContentStore.prerequisites_of` runs
    ``WHERE from_node = ? OR to_node = ?`` and filters no ``edge_type``, so an
    edge whose ``from_node`` is the node (the node is someone else's
    prerequisite) and an edge of §7's other ten types both arrive in the same
    tuple as the node's own declared prerequisites. :class:`DeclaredGraph`
    answers one-directionally (in-edges only) and so cannot show that face's
    semantics — which is exactly how a resolver assumption of "in-edges only"
    can survive a suite that only ever declares in-edges.
    """

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        failure = self._error()
        if failure is not None:
            return failure
        return Ok(
            tuple(
                edge
                for edge in self._edges
                if str(edge.from_node) == str(node_id)
                or str(edge.to_node) == str(node_id)
            )
        )


class DeclaredStates:
    """A §11 learner state handed in through the resolver's own port shape."""

    def __init__(
        self, states: Mapping[tuple[str, str], LearnerTargetStateRecord]
    ) -> None:
        self._states = dict(states)

    def get_learner_target_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[LearnerTargetStateRecord | None]:
        return Ok(
            self._states.get((str(target_id), str(evidence_modality)))
        )


def learner_record(
    target_id: str,
    *,
    flags: tuple[str, ...] = (),
    modality: EvidenceModality = MODALITY,
) -> LearnerTargetStateRecord:
    """A real §11 record with declared flags (BF-01 §25's own vocabulary)."""

    return LearnerTargetStateRecord(
        target_type="CAPABILITY",
        target_id=TargetId(target_id),
        evidence_modality=str(modality),
        dimensions={
            "recognition": LearnerDimensionState(
                estimate=0.9, confidence=0.9, last_relevant_evidence_at=None
            )
        },
        coverage=LearnerCoverage(
            evidence_groups=1,
            independent_clusters=1,
            sessions=1,
            days=1,
            contexts=1,
            personas=1,
            realizations=1,
            modalities=1,
        ),
        freshness=LearnerFreshness(
            last_strong_retrieval_at=None,
            elapsed_since_strong_retrieval_days=None,
            freshness_band="FRESH",
        ),
        projection=LearnerProjection(
            ability_band="GUIDED",
            confidence_band="MEDIUM",
            transfer_band="NARROW",
            support_band="PARTIAL_SUPPORT",
            stability_band="STABLE",
            learning_flags=tuple(flags),
        ),
        estimator_version="est-v1",
        evidence_watermark=1,
        updated_at="2026-09-23T09:00:00+00:00",
    )


class DeclaredReadiness:
    """The §8.1 ladder with declared artifact facts (module docstring).

    Wraps the real face, so every target the test does not declare is answered
    by the shipped corpus exactly as production answers it.
    """

    def __init__(
        self,
        real,
        declared: Mapping[str, ReadinessFacts],
        *,
        broken: DomainErrorCode | None = None,
    ) -> None:
        self._real = real
        self._declared = dict(declared)
        self._broken = broken

    def readiness(self, entity_id: str) -> Result[ReadinessAssessment]:
        if self._broken is not None:
            return Err(
                DomainError(code=self._broken, message="declared failure")
            )
        if entity_id in self._declared:
            return Ok(judge_readiness(self._declared[entity_id]))
        return self._real.readiness(entity_id)


def ready_facts(target_id: str, **overrides: bool) -> ReadinessFacts:
    """Every §8.1 fact an R3 target carries, one flag per fact key."""

    facts: dict[str, bool] = {
        "entity_row": True,
        "canonical_form": True,
        "assessment_membership": True,
        "pos": True,
        "sense": True,
        "basic_definition": True,
        "forms": True,
        "curriculum_link": True,
        "pedagogical_profile": True,
        "goal_pack_overlay": True,
        "resource_labels": True,
        "reviewed_explanation": True,
        "example_policy": True,
        "contrast_or_usage": True,
    }
    facts.update(overrides)
    return ReadinessFacts(target_id=target_id, **facts)


# -- ① content readiness -----------------------------------------------------


def test_no_ladder_face_is_no_level_and_not_a_default() -> None:
    outcome = readiness_of_target("res-hedge-i-think", None)
    assert outcome.level is None
    assert outcome.usable is False
    assert "no §8.1 readiness face" in outcome.reasons[0]
    assert "no level under R0" in " ".join(outcome.reasons)


def test_an_unreadable_ladder_is_no_level_and_carries_the_failure(
    content_supply,
) -> None:
    outcome = readiness_of_target(
        "res-hedge-i-think",
        DeclaredReadiness(
            content_supply, {}, broken=DomainErrorCode.DEPENDENCY_UNAVAILABLE
        ),
    )
    assert outcome.level is None
    assert "DEPENDENCY_UNAVAILABLE" in outcome.reasons[0]


def test_the_shipped_corpus_levels_are_thirteen_none_and_one_r4(
    content_supply,
) -> None:
    """The real ladder over the real corpus, at C1's truth (旧真值: every
    target read no level, blocked at R0 by ``assessment_membership`` — the
    P5-R strict reading; 新真值: the thirteen evidence-less targets still
    read exactly that, and the one target whose source states all nineteen
    facts reads R4_DETECTION_READY with no blocking key)."""

    ids = content_supply.supply_entity_ids()
    assert isinstance(ids, Ok)
    assert len(ids.value) == 14
    r4: list[str] = []
    for entity_id in ids.value:
        outcome = readiness_of_target(str(entity_id), content_supply)
        if outcome.level is ReadinessLevel.R4_DETECTION_READY:
            r4.append(str(entity_id))
            assert outcome.usable is True
            assert outcome.blocking_keys == ()
            continue
        assert outcome.level is None, entity_id
        assert outcome.blocking_keys == ("assessment_membership",), entity_id
        assert "blocked at R0_INDEXED" in outcome.reasons[0]
    assert r4 == ["res-colloc-make-a-decision"]


def test_a_declared_artifact_fact_set_reaches_the_ladder_s_own_level(
    content_supply,
) -> None:
    """The declared-facts world: the real ladder, given every R3 fact, answers
    R3 — and the Planner's vocabulary is the same five words (the conversion
    can never mint a level)."""

    port = DeclaredReadiness(content_supply, {NODE: ready_facts(NODE)})
    outcome = readiness_of_target(NODE, port)
    assert outcome.level is ReadinessLevel.R3_TEACHING_READY
    assert outcome.usable is True
    assert outcome.blocking_keys == ()
    assert outcome.level.value == judge_readiness(ready_facts(NODE)).level

    four = DeclaredReadiness(
        content_supply,
        {
            NODE: ready_facts(
                NODE,
                detection_policy=True,
                recognition_rules=True,
                negative_fixtures=True,
                false_positive_boundaries=True,
            )
        },
    )
    assert readiness_of_target(NODE, four).level is (
        ReadinessLevel.R4_DETECTION_READY
    )


def test_the_conversion_is_the_same_ladder_and_not_a_second_spelling(
    content_supply,
) -> None:
    """``ReadinessLevel`` (the Planner's) is the ladder's own five words, so a
    level read from the supply face is a level the kernel can hold."""

    from elc.curriculum.readiness import READINESS_LEVELS

    assert tuple(level.value for level in ReadinessLevel) == READINESS_LEVELS


# -- ② prerequisites ---------------------------------------------------------


def test_no_graph_face_is_unknown() -> None:
    outcome = prerequisite_state_of(
        "RESOURCE",
        "res-hedge-i-think",
        MODALITY,
        prerequisites=None,
        learner_state=None,
    )
    assert outcome.state is PrerequisiteState.UNKNOWN
    assert outcome.scaffoldable is False
    assert "no curriculum-graph face" in outcome.reasons[0]


def test_a_capability_target_is_its_own_node_and_the_corpus_declares_no_edge(
    content_supply,
) -> None:
    """The registry's own rule (curriculum README C1) makes a capability target
    a node without any link, and the shipped prerequisite set is empty — so the
    answer is READY as a *read* of an empty declared set."""

    outcome = prerequisite_state_of(
        "CAPABILITY",
        NODE,
        MODALITY,
        prerequisites=content_supply,
        learner_state=None,
    )
    assert outcome.state is PrerequisiteState.READY
    assert outcome.nodes == (NODE,)
    assert "its own registry node" in outcome.reasons[0]
    assert "no prerequisite edge" in " ".join(outcome.reasons)


def test_a_resource_with_only_unapproved_links_is_unknown(content_supply) -> None:
    """The registered judgement, on the shipped corpus: the nine resources are
    mapped ``CURRICULUM_MAPPED``, and a candidate mapping is not a mapping this
    resolver may act on (P5-R) — so the answer is UNKNOWN, not a READY that
    would silently pass an unmapped target."""

    outcome = prerequisite_state_of(
        "RESOURCE",
        "res-hedge-i-think",
        MODALITY,
        prerequisites=content_supply,
        learner_state=None,
    )
    assert outcome.state is PrerequisiteState.UNKNOWN
    assert outcome.scaffoldable is False
    assert APPROVED_LINK_EDITORIAL_STATUS in outcome.reasons[0]
    assert "CURRICULUM_MAPPED" in outcome.reasons[0]


def approved_link(
    resource_id: str = NODE,
    node_id: str = OTHER_NODE,
    status: str = APPROVED_LINK_EDITORIAL_STATUS,
) -> CurriculumLinkRecord:
    return CurriculumLinkRecord(
        resource_id=ResourceId(resource_id),
        node_id=CurriculumNodeId(node_id),
        relation=CurriculumLinkRelation.REALIZES,
        strength=None,
        primary_flag=True,
        editorial_status=status,
        rationale="declared by the test",
    )


def edge(
    node_from: str,
    node_to: str = OTHER_NODE,
    strength: PrerequisiteStrength | None = PrerequisiteStrength.HARD,
) -> CurriculumEdgeRecord:
    return CurriculumEdgeRecord(
        from_node=CurriculumNodeId(node_from),
        to_node=CurriculumNodeId(node_to),
        edge_type=CurriculumEdgeType.PREREQUISITE_FOR,
        prerequisite_strength=strength,
    )


def test_an_approved_link_makes_the_graph_readable() -> None:
    graph = DeclaredGraph(
        capabilities=(NODE,),
        links=(approved_link(resource_id="res-x", node_id=NODE),),
        edges=(),
    )
    outcome = prerequisite_state_of(
        "RESOURCE", "res-x", MODALITY, prerequisites=graph, learner_state=None
    )
    assert outcome.state is PrerequisiteState.READY
    assert outcome.nodes == (NODE,)
    assert "approved REALIZES link(s) read" in " ".join(outcome.reasons)


@pytest.mark.parametrize(
    ("strength", "verdict", "expected", "scaffoldable"),
    [
        pytest.param(
            PrerequisiteStrength.HARD, "UNMET", "BLOCKED", False, id="hard-unmet"
        ),
        pytest.param(
            PrerequisiteStrength.HARD,
            "UNJUDGED",
            "UNKNOWN",
            False,
            id="hard-unjudged",
        ),
        pytest.param(
            PrerequisiteStrength.HARD, "PROVEN", "READY", False, id="hard-proven"
        ),
        pytest.param(
            PrerequisiteStrength.SCAFFOLDABLE,
            "UNJUDGED",
            "READY_WITH_SCAFFOLD",
            True,
            id="scaffoldable",
        ),
        pytest.param(
            PrerequisiteStrength.SOFT,
            "UNMET",
            "READY",
            False,
            id="soft-is-not-a-cell",
        ),
        pytest.param(None, "UNJUDGED", "UNKNOWN", False, id="null-strength"),
        pytest.param(None, "UNMET", "BLOCKED", False, id="null-strength-unmet"),
    ],
)
def test_the_fold_over_the_graph_s_strengths(
    strength: PrerequisiteStrength | None,
    verdict: str,
    expected: str,
    scaffoldable: bool,
) -> None:
    """BF-02 §11's four words, one row per reachable shape — including the
    fail-closed reading of an edge with no declared strength (HARD), which can
    block but never silently scaffold."""

    graph = DeclaredGraph(
        capabilities=(NODE,), edges=(edge("cap-prereq", NODE, strength),)
    )
    states = DeclaredStates(
        {
            ("cap-prereq", str(MODALITY)): learner_record(
                "cap-prereq",
                flags=(
                    (CONFIRMED_GAP_FLAG,)
                    if verdict == "UNMET"
                    else ()
                ),
            )
        }
        if verdict != "UNJUDGED"
        else {}
    )
    outcome = prerequisite_state_of(
        "CAPABILITY", NODE, MODALITY, prerequisites=graph, learner_state=states
    )
    assert outcome.state.value == expected
    assert outcome.scaffoldable is scaffoldable


# -- the face's real semantics: out-edges and other edge types (F1's probe) --


def test_an_out_edge_is_not_the_node_s_own_prerequisite() -> None:
    """``cap-b`` is ``cap-c``'s declared prerequisite and has none of its own.

    The shipped face returns the out-edge ``cap-b → cap-c`` when ``cap-b`` is
    asked about (``from_node = ? OR to_node = ?``), so a resolver that judged
    every edge the face returned would judge ``cap-b`` against its own state —
    UNKNOWN, since nothing was ever observed — for a node whose declared
    prerequisite set is empty. The read answer is READY.
    """

    graph = RealFaceGraph(
        capabilities=("cap-b", "cap-c"),
        edges=(edge("cap-b", "cap-c"),),
    )
    outcome = prerequisite_state_of(
        "CAPABILITY",
        "cap-b",
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates({}),
    )
    assert outcome.state is PrerequisiteState.READY
    assert outcome.nodes == ("cap-b",)
    assert "no prerequisite edge" in " ".join(outcome.reasons)
    assert "not this node's own prerequisites" in " ".join(outcome.reasons)


def test_the_same_face_s_in_edge_still_blocks_on_the_prerequisite_s_flag() -> None:
    """The other half of the probe: reading the edge ``cap-b → cap-c`` from
    ``cap-c`` is reading a real prerequisite, and ``cap-b``'s own
    ``CONFIRMED_GAP`` is what decides — the flag on the prerequisite node
    itself, never a conclusion drawn from *its* prerequisites."""

    graph = RealFaceGraph(
        capabilities=("cap-b", "cap-c"),
        edges=(edge("cap-b", "cap-c"),),
    )
    outcome = prerequisite_state_of(
        "CAPABILITY",
        "cap-c",
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates(
            {
                ("cap-b", str(MODALITY)): learner_record(
                    "cap-b", flags=(CONFIRMED_GAP_FLAG,)
                )
            }
        ),
    )
    assert outcome.state is PrerequisiteState.BLOCKED
    assert outcome.scaffoldable is False


def test_an_edge_of_another_type_is_not_a_prerequisite() -> None:
    """The face filters no ``edge_type`` and §7's table carries eleven words:
    only ``PREREQUISITE_FOR`` declares a prerequisite, so a ``SUPPORTS`` edge
    into the node is dropped like an out-edge rather than judged as a
    requirement the graph never declared."""

    graph = RealFaceGraph(
        capabilities=("cap-x", "cap-c"),
        edges=(
            CurriculumEdgeRecord(
                from_node=CurriculumNodeId("cap-x"),
                to_node=CurriculumNodeId("cap-c"),
                edge_type=CurriculumEdgeType.SUPPORTS,
                prerequisite_strength=PrerequisiteStrength.HARD,
            ),
        ),
    )
    outcome = prerequisite_state_of(
        "CAPABILITY",
        "cap-c",
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates({}),
    )
    assert outcome.state is PrerequisiteState.READY
    assert "not this node's own prerequisites" in " ".join(outcome.reasons)


def test_a_hard_unjudged_edge_under_a_scaffold_keeps_its_unknown_word() -> None:
    """BF-02 §11's two scaffold shapes, and the merged one in particular: a
    ``HARD`` edge nobody can judge *and* an unmet ``SCAFFOLDABLE`` edge reads
    ``UNKNOWN`` with ``scaffoldable=True`` — the pair the kernel prices and
    admits exactly as it does ``READY_WITH_SCAFFOLD`` — never a
    ``READY_WITH_SCAFFOLD`` that folds the HARD edge's "not judged" state away
    from the word."""

    graph = DeclaredGraph(
        capabilities=(NODE,),
        edges=(
            edge("cap-hard", NODE),
            edge("cap-scaffold", NODE, PrerequisiteStrength.SCAFFOLDABLE),
        ),
    )
    outcome = prerequisite_state_of(
        "CAPABILITY",
        NODE,
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates({}),
    )
    assert outcome.state is PrerequisiteState.UNKNOWN
    assert outcome.scaffoldable is True

    # §11's first word still names the single shape it names
    scaffold_only = DeclaredGraph(
        capabilities=(NODE,),
        edges=(edge("cap-scaffold", NODE, PrerequisiteStrength.SCAFFOLDABLE),),
    )
    single = prerequisite_state_of(
        "CAPABILITY",
        NODE,
        MODALITY,
        prerequisites=scaffold_only,
        learner_state=DeclaredStates({}),
    )
    assert single.state is PrerequisiteState.READY_WITH_SCAFFOLD
    assert single.scaffoldable is True


def test_the_two_flags_are_the_estimator_s_own_words() -> None:
    """BF-01 §25's list carries both, and the residue is symmetric: a state
    that carries one of them is not proof, and a state that carries neither is
    the only thing this cut calls proof."""

    from elc.learning.estimator import ALLOWED_LEARNING_FLAGS

    assert CONFIRMED_GAP_FLAG in ALLOWED_LEARNING_FLAGS
    assert INSUFFICIENT_EVIDENCE_FLAG in ALLOWED_LEARNING_FLAGS


def test_the_approved_status_is_the_content_domain_s_own_word() -> None:
    """One gate, one spelling (the constant is re-declared here so the Planner
    imports no store module; this pin keeps the two equal)."""

    from elc.content.store import CAPABILITY_CREDIT_EDITORIAL_STATUS

    assert APPROVED_LINK_EDITORIAL_STATUS == CAPABILITY_CREDIT_EDITORIAL_STATUS
    assert REALIZES_RELATION == CurriculumLinkRelation.REALIZES.value


def test_an_unreadable_edge_face_is_unknown() -> None:
    graph = DeclaredGraph(
        capabilities=(NODE,), broken=DomainErrorCode.DEPENDENCY_UNAVAILABLE
    )
    outcome = prerequisite_state_of(
        "CAPABILITY", NODE, MODALITY, prerequisites=graph, learner_state=None
    )
    assert outcome.state is PrerequisiteState.UNKNOWN
    assert "DEPENDENCY_UNAVAILABLE" in " ".join(outcome.reasons)


def test_an_undeclared_capability_is_unknown_not_ready() -> None:
    graph = DeclaredGraph(capabilities=())
    outcome = prerequisite_state_of(
        "CAPABILITY", "cap-nope", MODALITY, prerequisites=graph, learner_state=None
    )
    assert outcome.state is PrerequisiteState.UNKNOWN
    assert "does not declare this node" in outcome.reasons[0]


def test_a_proven_prerequisite_needs_a_state_and_no_blocking_flag() -> None:
    """The proof rule, isolated: never observed → not proven; a state with the
    gap flag → not proven; a state with neither → proven."""

    graph = DeclaredGraph(
        capabilities=(NODE,),
        edges=(edge("cap-prereq", NODE, PrerequisiteStrength.HARD),),
    )
    never = prerequisite_state_of(
        "CAPABILITY",
        NODE,
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates({}),
    )
    assert never.state is PrerequisiteState.UNKNOWN

    insufficient = prerequisite_state_of(
        "CAPABILITY",
        NODE,
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates(
            {
                ("cap-prereq", str(MODALITY)): learner_record(
                    "cap-prereq", flags=(INSUFFICIENT_EVIDENCE_FLAG,)
                )
            }
        ),
    )
    assert insufficient.state is PrerequisiteState.BLOCKED

    proven = prerequisite_state_of(
        "CAPABILITY",
        NODE,
        MODALITY,
        prerequisites=graph,
        learner_state=DeclaredStates(
            {("cap-prereq", str(MODALITY)): learner_record("cap-prereq")}
        ),
    )
    assert proven.state is PrerequisiteState.READY
    assert "the prerequisite stands" in " ".join(proven.reasons)


def test_the_outcome_is_a_record_not_a_decision() -> None:
    """One word and its evidence: the resolver reports §11's state and the
    scaffoldability the kernel prices; it excludes nothing and selects
    nothing."""

    outcome = prerequisite_state_of(
        "RESOURCE",
        "res-hedge-i-think",
        MODALITY,
        prerequisites=None,
        learner_state=None,
    )
    fields = tuple(vars(outcome))
    assert fields == ("state", "scaffoldable", "nodes", "reasons")
    assert outcome.hard_blocked is False
