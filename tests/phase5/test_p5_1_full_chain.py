"""⑤/⑥ — the p5-1 end-to-end: conversation → production provider → content.db.

The chain this file drives is the shipped one, with no fixture supply and no
seeded "before" state (TASK-OPI-4d516e4f-….46 red line, external-review
DEC-…32):

    canonical conversation turn (CP0 → deterministic analysis → CP1 commit)
      → user-initiated teaching request
      → ContentBackedTeachingTargetProvider.resolve()  → content.db
      → Gate facts → CP2 open → opening delivery
      → user attempt → evaluation → Evidence commit → rebuild → LearnerState

Five things are established, each in its own scenario:

- the supply chain is real: the moment's own stamps (§11 target_mode /
  learning_intent, §24.14 modality) and the delivered content come from the
  artifact, and the "before" state is produced by the conversation leg, not
  by a seeded evidence group;
- content.db is the supply, not a coincidence: a variant artifact (one §11
  default changed) changes what the chain opens — the fixture corpus is not
  behind this;
- the state really moves, and what it moves *on* is the artifact's data: the
  second cycle's alternative realization is **not** credited to a capability
  (P5-R: the artifact's §24.7 link is ``CURRICULUM_MAPPED``, and only an
  approved mapping reaches the credit face) — the resource carries the §5
  NEUTRAL claim and the capability's state never appears;
- an unusable artifact degrades the Gate (UNKNOWN → DEGRADED, no synthetic
  DENY), while an unknown or wrong-kind target denies deterministically;
- a §24.11 candidate — excluded from supply — reaches the Gate as its own
  deterministic non-validity (§6 "candidate content excluded").

The module also pins its own supply chain: no import of the P3 fixture
provider, no `_seed(`-style helper, and no teaching_moment/evidence row that
could have been written before the chain ran.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.content.store import ContentStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.learning.controller import LearningController
from elc.platform.types import EvidenceModality, Ok, TargetId
from elc.teaching.targets import TeachingTargetView
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase5.conftest import (
    artifact_with_lifecycle,
    attempt,
    build_variant_artifact,
    commit_chat_turn,
    open_moment,
    production_coordinator,
    reply_ok,
)

FOCUS = "res-hedge-i-think"
CANONICAL_ANSWER = "I think it is going to rain."
ALTERNATIVE_ANSWER = "It might rain."
WRONG_ANSWER = "The weather is terrible today."
CANDIDATE = "res-candidate-not-approved"
MODALITY = "TEXT_PRODUCTION"

_CLAIM_COLUMNS = (
    "evidence_claim_id",
    "evidence_group_id",
    "target_type",
    "target_id",
    "evidence_modality",
    "performance_type",
    "polarity",
    "outcome",
    "support_level",
    "status",
    "attempt_id",
    "teaching_moment_id",
    "source_turn_id",
)


# ---------------------------------------------------------------------------
# reading the durable state (the P3-3 vocabulary, kept small here)
# ---------------------------------------------------------------------------


def _claims(db: sqlite3.Connection) -> tuple[dict[str, Any], ...]:
    rows = db.execute(
        f"SELECT {', '.join(_CLAIM_COLUMNS)} FROM evidence_claim"
        " ORDER BY created_at, evidence_claim_id"
    ).fetchall()
    return tuple(dict(zip(_CLAIM_COLUMNS, row)) for row in rows)


def _claim_ids(db: sqlite3.Connection) -> frozenset[str]:
    return frozenset(str(claim["evidence_claim_id"]) for claim in _claims(db))


def _new_claims(
    db: sqlite3.Connection, before_ids: frozenset[str]
) -> tuple[dict[str, Any], ...]:
    return tuple(
        claim
        for claim in _claims(db)
        if str(claim["evidence_claim_id"]) not in before_ids
    )


def _state(db: sqlite3.Connection, target_id: str) -> dict[str, Any] | None:
    """The target's §11 projection document, or None when it has none yet."""

    row = db.execute(
        "SELECT state_json FROM learner_target_state"
        " WHERE target_id = ? AND evidence_modality = ?",
        (target_id, MODALITY),
    ).fetchone()
    return None if row is None else json.loads(str(row[0]))


def _flat(document: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in document.items():
        path = key if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flat(value, path))
        else:
            flat[path] = value
    return flat


def _moment_row(db: sqlite3.Connection, moment_id: str) -> dict[str, Any]:
    """The moment row's target stamps + lifecycle (§15 columns)."""

    row = db.execute(
        "SELECT moment_id, focus_target, target_mode, learning_intent,"
        " evidence_modality, lifecycle_state FROM teaching_moment"
        " WHERE moment_id = ?",
        (moment_id,),
    ).fetchone()
    assert row is not None, f"no teaching_moment row for {moment_id}"
    document: dict[str, Any] = {
        "moment_id": row[0],
        "target_mode": row[2],
        "learning_intent": row[3],
        "evidence_modality": row[4],
        "lifecycle_state": row[5],
    }
    focus = json.loads(str(row[1]))
    document["focus_target_type"] = focus["target_type"]
    document["focus_target_id"] = focus["target_id"]
    return document


def _rebuild(learning: LearningController, target_id: str) -> None:
    rebuilt = learning.rebuild_learner_state(
        TargetId(target_id), EvidenceModality(MODALITY)
    )
    assert isinstance(rebuilt, Ok), rebuilt


def _provider_view(
    provider: ContentBackedTeachingTargetProvider, target_id: str
) -> TeachingTargetView:
    resolved = provider.resolve("RESOURCE", target_id)
    assert isinstance(resolved, Ok), resolved
    return resolved.value


# ---------------------------------------------------------------------------
# ① the supply chain
# ---------------------------------------------------------------------------


def test_the_before_state_comes_from_the_conversation_not_a_seed(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    """The IP §1.5 first leg: a canonical chat turn produces its own durable
    analysis artifact and evidence commit — and nothing else exists yet."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
    )
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone() == (0,)
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone() == (0,)

    commit_chat_turn(coordinator, "cm-p51-chat", "I like this cafe.", 1)

    artifacts = db.execute(
        "SELECT count(*) FROM analysis_artifact WHERE status = 'COMMITTED'"
    ).fetchone()
    commits = db.execute("SELECT count(*) FROM evidence_commit").fetchone()
    claims = _claims(db)
    print(f"[e2e] committed analysis artifacts -> {artifacts}")
    print(f"[e2e] evidence commits             -> {commits}")
    print(f"[e2e] claims after one chat turn   -> {len(claims)}")
    assert artifacts is not None and artifacts[0] >= 1
    assert commits is not None and commits[0] >= 1
    # The P2A producer is target-less by design (elc.learning.analysis): the
    # conversation leg builds the session, not the taught target's history —
    # which is exactly why the teaching chain below is the only source of
    # target-bearing claims. Read it off the durable proposal, not by
    # trusting an empty list.
    proposal = db.execute(
        "SELECT structured_proposal FROM analysis_artifact LIMIT 1"
    ).fetchone()
    assert proposal is not None
    document = json.loads(str(proposal[0]))
    print(f"[e2e] chat proposal keys -> {sorted(document)}")
    assert "target_id" not in document and "target_type" not in document
    assert document["evidence_modality"] == MODALITY
    assert all(claim["target_id"] is None for claim in claims)


def test_the_chain_resolves_everything_through_content_db(
    db: sqlite3.Connection,
    built_content_db: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    """One teaching turn: the Gate allows, CP2 stamps the artifact's own §11
    defaults, and the delivered content is the artifact's."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
    )
    commit_chat_turn(coordinator, "cm-p51-chain-chat", "Nice to meet you.", 1)

    opened = open_moment(coordinator, "cm-p51-chain-open", FOCUS)
    print(f"[e2e] gate -> {opened.gate_execution_status}/{opened.gate_decision}")
    assert opened.gate_execution_status == "SUCCEEDED"
    assert opened.gate_decision == "ALLOW"
    assert opened.moment_id is not None

    view = _provider_view(production_provider, FOCUS)
    moment = _moment_row(db, str(opened.moment_id))
    print(f"[e2e] moment stamps -> {moment}")
    assert moment["focus_target_id"] == FOCUS
    # The stamps could only come from the resolved view: §11 default mode and
    # intent, §24.14 modality, read from content.db by the provider.
    assert moment["target_mode"] == view.target_mode
    assert moment["learning_intent"] == view.learning_intent
    assert moment["evidence_modality"] == view.evidence_modality
    assert moment["lifecycle_state"] == "AWAITING_USER"

    store = ContentStore(built_content_db)
    try:
        row = store.get_target(FOCUS)
        assert isinstance(row, Ok), row
        assert view.target_mode == row.value.target_mode
        assert view.learning_intent == row.value.learning_intent
        assert view.evidence_modality == row.value.evidence_modality
        teaching = store.get_teaching_content(FOCUS)
        assert isinstance(teaching, Ok), teaching
        assert view.hint_ladder == teaching.value.hint_ladder
    finally:
        store.close()


def test_the_chain_follows_the_artifact_not_a_fixture(
    db: sqlite3.Connection,
    built_content_db: Path,
    tmp_path: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """A variant artifact with one §11 default changed opens a *different*
    moment — the supply is the file, not the fixture corpus."""

    def edit(documents: dict, index: dict) -> None:
        del index
        document = documents[f"entities/{FOCUS}.json"]
        document["target"]["target_mode"] = "TRANSFER"
        document["target"]["learning_intent"] = "TRANSFER"

    canonical_store = ContentStore(built_content_db)
    try:
        canonical_row = canonical_store.get_target(FOCUS)
        assert isinstance(canonical_row, Ok), canonical_row
        assert (
            canonical_row.value.target_mode,
            canonical_row.value.learning_intent,
        ) == ("RESOURCE_PRACTICE", "ESTABLISH")
    finally:
        canonical_store.close()

    artifact = build_variant_artifact(tmp_path, edit)
    provider = ContentBackedTeachingTargetProvider(artifact)
    try:
        coordinator = production_coordinator(
            conversation_store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            provider,
        )
        opened = open_moment(coordinator, "cm-p51-variant-open", FOCUS)
        assert opened.gate_decision == "ALLOW"
        moment = _moment_row(db, str(opened.moment_id))
        print(f"[e2e] variant moment stamps -> {moment}")
        assert moment["target_mode"] == "TRANSFER"
        assert moment["learning_intent"] == "TRANSFER"
    finally:
        provider.close()


# ---------------------------------------------------------------------------
# ② the state moves, and moves on the artifact's data
# ---------------------------------------------------------------------------


def test_two_cycles_move_the_state_without_crediting_an_unreviewed_link(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    """No seeded before state: cycle 1 is what creates it. P5-R (D1): the
    artifact's §24.7 link is CURRICULUM_MAPPED, so cycle 2's alternative
    realization is **not** credited to a capability — the resource gets the
    one honest NEUTRAL claim and the capability's state never appears. The
    gate is the artifact's own editorial status, exercised end to end."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
    )
    learning_controller = LearningController(learning)
    commit_chat_turn(coordinator, "cm-p51-move-chat", "Hello there.", 1)

    view = _provider_view(production_provider, FOCUS)
    assert view.capability_linkage is None, (
        "an unapproved §24.7 link must not reach the credit face (P5-R)"
    )
    capability = "cap-eval-hedged-opinion"

    # -- cycle 1: the canonical realization --------------------------------
    assert _state(db, FOCUS) is None
    empty_ids = _claim_ids(db)
    first = open_moment(coordinator, "cm-p51-move-open-1", FOCUS)
    assert first.gate_decision == "ALLOW"
    reply = reply_ok(coordinator, attempt(CANONICAL_ANSWER), "cm-p51-move-attempt-1")
    assert reply.evaluation_outcome == "SUCCESS"
    assert reply.evidence_commit_id is not None
    _rebuild(learning_controller, FOCUS)

    after_first = _state(db, FOCUS)
    assert after_first is not None, "the chain must create the state"
    first_claims = _new_claims(db, empty_ids)
    print(
        "[e2e] cycle 1 claims -> "
        f"{[(c['target_id'], c['outcome']) for c in first_claims]}"
    )
    assert first_claims, "a SUCCESS attempt commits evidence"
    assert {str(claim["teaching_moment_id"]) for claim in first_claims} == {
        str(first.moment_id)
    }
    assert {str(claim["target_id"]) for claim in first_claims} == {FOCUS}
    assert {str(claim["attempt_id"]) for claim in first_claims} == {
        str(reply.attempt_id)
    }
    assert all(
        claim["polarity"] == "POSITIVE" and claim["outcome"] == "SUCCESS"
        for claim in first_claims
    )

    # -- cycle 2: the alternative realization ------------------------------
    before_claims = _claim_ids(db)
    before_resource = _state(db, FOCUS)
    before_capability = _state(db, capability)
    assert before_capability is None, "the capability has no state before cycle 2"
    second = open_moment(coordinator, "cm-p51-move-open-2", FOCUS)
    assert second.gate_decision == "ALLOW"
    assert second.moment_id != first.moment_id, "a closed moment never reopens"
    alternative = reply_ok(
        coordinator, attempt(ALTERNATIVE_ANSWER), "cm-p51-move-attempt-2"
    )
    assert alternative.evaluation_outcome == "ALTERNATIVE_SUCCESS"
    _rebuild(learning_controller, FOCUS)
    _rebuild(learning_controller, capability)

    second_claims = _new_claims(db, before_claims)
    credited = {str(claim["target_id"]) for claim in second_claims}
    print(
        "[e2e] cycle 2 claims -> "
        f"{[(c['target_id'], c['outcome'], c['polarity']) for c in second_claims]}"
    )
    # P5-R: the alternative realization credits no capability, and the
    # resource it bypassed gets exactly the §5 NEUTRAL/not-demonstrated claim.
    assert credited == {FOCUS}
    resource_claim = second_claims[0]
    assert resource_claim["outcome"] == "ABSTAIN"
    assert resource_claim["polarity"] == "NEUTRAL"
    assert resource_claim["target_type"] == "RESOURCE"
    assert {str(claim["teaching_moment_id"]) for claim in second_claims} == {
        str(second.moment_id)
    }

    # The capability: no claim ever, no state ever (even after an explicit
    # rebuild — an empty claim set writes nothing).
    assert _state(db, capability) is None
    assert (
        db.execute(
            "SELECT COUNT(*) FROM evidence_claim WHERE target_id = ?",
            (capability,),
        ).fetchone()
        == (0,)
    )
    # The resource's own projection: no dimension moves (the claim is
    # NEUTRAL), and coverage/watermark still record the attempt.
    after_resource = _state(db, FOCUS)
    assert after_resource is not None
    assert after_resource["dimensions"] == before_resource["dimensions"]
    resource_changed = {
        path
        for path, value in _flat(after_resource).items()
        if _flat(before_resource).get(path) != value
    }
    print(f"[e2e] resource paths that moved -> {sorted(resource_changed)}")
    assert not [path for path in resource_changed if path.startswith("dimensions.")]
    assert resource_changed, "coverage/watermark still record the attempt"


# ---------------------------------------------------------------------------
# ③ the failure faces, through the real Gate
# ---------------------------------------------------------------------------


def test_an_unusable_artifact_degrades_instead_of_denying(
    db: sqlite3.Connection,
    tmp_path: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    provider = ContentBackedTeachingTargetProvider(tmp_path / "absent" / "content.db")
    try:
        coordinator = production_coordinator(
            conversation_store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            provider,
        )
        opened = open_moment(coordinator, "cm-p51-degraded", FOCUS)
    finally:
        provider.close()
    print(
        f"[e2e] broken supply -> {opened.gate_execution_status}"
        f" decision={opened.gate_decision}"
        f" missing_or_unknown={opened.missing_or_unknown}"
    )
    assert opened.gate_execution_status == "DEGRADED"
    assert opened.gate_decision is None
    assert "TARGET_VALIDITY" in opened.missing_or_unknown
    assert "CONTENT_VALIDITY" in opened.missing_or_unknown
    assert opened.moment_id is None
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone() == (0,)


def test_an_unknown_or_wrong_kind_target_denies_deterministically(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
    )
    unknown = open_moment(coordinator, "cm-p51-unknown", "res-does-not-exist")
    mismatch = open_moment(
        coordinator,
        "cm-p51-mismatch",
        FOCUS,
        target_type="CAPABILITY",
    )
    for result in (unknown, mismatch):
        print(
            f"[e2e] {result.turn_id} -> {result.gate_execution_status}/"
            f"{result.gate_decision} {result.reason_codes}"
        )
        assert result.gate_execution_status == "SUCCEEDED"
        assert result.gate_decision == "DENY"
        assert "TARGET_INVALID" in result.reason_codes
        assert result.moment_id is None
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone() == (0,)


def test_a_candidate_entity_denies_through_the_real_gate(
    db: sqlite3.Connection,
    tmp_path: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """IMPLEMENTATION_PLAN §6 "candidate content excluded", end to end: a
    §24.11 candidate is not in the supply set, and a request on it lands as
    the deterministic DENY its own status warrants."""

    artifact = artifact_with_lifecycle(tmp_path, {CANDIDATE: "REVIEW_REQUIRED"})
    provider = ContentBackedTeachingTargetProvider(artifact)
    try:
        store = ContentStore(artifact)
        try:
            supply = CurriculumContentStore(store)
            eligible = supply.supply_entity_ids()
            assert isinstance(eligible, Ok), eligible
            assert CANDIDATE not in {
                str(entity_id) for entity_id in eligible.value
            }
        finally:
            store.close()
        coordinator = production_coordinator(
            conversation_store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            provider,
        )
        denied = open_moment(coordinator, "cm-p51-candidate", CANDIDATE)
    finally:
        provider.close()
    print(
        f"[e2e] candidate -> {denied.gate_execution_status}/{denied.gate_decision}"
        f" {denied.reason_codes}"
    )
    assert denied.gate_decision == "DENY"
    assert "TARGET_INVALID" in denied.reason_codes
    assert denied.moment_id is None
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone() == (0,)


# ---------------------------------------------------------------------------
# ⑥ the module's own supply chain
# ---------------------------------------------------------------------------


def test_this_module_imports_no_fixture_supply_and_seeds_nothing() -> None:
    """The red line, made checkable: this file (the p5-1 E2E) neither imports
    the P3 fixture provider nor fabricates a before state."""

    path = Path(__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    assert not [module for module in imported if "target_fixtures" in module], imported
    assert not [module for module in imported if "phase3" in module], imported
    assert "_seed" not in calls
    assert "commit_evidence_group" not in calls
    assert "produce_learning_evidence_proposal" not in calls
    print(f"[e2e] imports -> {sorted(set(imported))}")
    print(f"[e2e] calls   -> {sorted(set(calls))}")


def test_the_repo_still_owns_its_fixture_supply_for_the_phase_3_tests() -> None:
    """The production provider *replaces* the fixture for new assemblies; the
    P3 tests keep theirs (migration ≠ deletion — the P5-0 rule)."""

    fixture_module = REPO_ROOT / "tests" / "phase3" / "target_fixtures.py"
    assert fixture_module.is_file()
    text = fixture_module.read_text(encoding="utf-8")
    assert "FixtureTeachingTargetProvider" in text
    assert "Phase 5 replaces it" in (
        SRC_ROOT / "teaching" / "targets.py"
    ).read_text(encoding="utf-8")


def test_the_production_provider_is_not_the_port_made_optional() -> None:
    """The port's protocol is still the only contract the coordinator needs:
    the production provider satisfies it structurally."""

    from elc.teaching.targets import TeachingTargetProvider

    provider = ContentBackedTeachingTargetProvider(
        Path(__file__).resolve().parent / "nonexistent" / "content.db"
    )
    try:
        assert isinstance(provider, TeachingTargetProvider)
    finally:
        provider.close()


@pytest.mark.parametrize("target_id", (FOCUS,))
def test_wrong_answers_do_not_destroy_the_state(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    target_id: str,
) -> None:
    """A FAILURE attempt keeps the episode open and the state readable — the
    chain's degraded shapes are still the chain (no crash, no fabricated
    success)."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
    )
    learning_controller = LearningController(learning)
    opened = open_moment(coordinator, "cm-p51-failure-open", target_id)
    reply = reply_ok(coordinator, attempt(WRONG_ANSWER), "cm-p51-failure-attempt")
    assert reply.evaluation_outcome != "SUCCESS"
    _rebuild(learning_controller, target_id)
    state = _state(db, target_id)
    assert state is not None
    moment = _moment_row(db, str(opened.moment_id))
    print(f"[e2e] failure -> outcome={reply.evaluation_outcome} moment={moment}")
    assert moment["lifecycle_state"] == "AWAITING_USER"
