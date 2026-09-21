"""⑤②③④ — the p5-2 end-to-end: a natural chat turn, no teaching, a claim.

The chain this file drives is the shipped one, with no fixture supply and no
seeded "before" state:

    canonical conversation turn (CP0 → resolution → durable proposal → CP1
      commit → §11 rebuild)
      → target-specific silent Performance Evidence
      → (separately) the unchanged user-initiated teaching chain

Five things are established, each in its own scenario:

- the observation is silent: one natural turn on a §24.5 form — the whole
  utterance, which is the admitted class (P5-R) — lands one claim on its
  target and moves the learner state, with **no TeachingMoment,
  Gate decision or Planner choice anywhere** — and the turn still gets its
  normal persona reply;
- the before state is produced by the chain (zero claims / zero state rows
  beforehand), from the real content.db supply, with no fixture target;
- a miss, a broken supply and a raising source all leave the turn healthy
  and the evidence empty (RA §21);
- the §24.11 supplier filter decides: the same utterance that resolves in
  the canonical corpus never resolves onto an unapproved candidate;
- the teaching leg next to a silent claim is byte-for-byte the p5-1 chain
  (same claims, same moment linkage).

The module also pins its own supply chain: no `_seed`-style helper and no
import of the P3 fixture supply (AST scan over every p5-2 test module).
"""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path

from elc.learning.controller import LearningController
from elc.learning.silent_evidence import (
    ContentBackedSilentTargets,
    ContentBackedTargetSupply,
)
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.types import EvidenceModality, Ok, TargetId
from elc.runtime import ConversationCoordinator
from tests.phase5.conftest import (
    CANDIDATE_UNIQUE_FORM,
    attempt,
    build_variant_artifact,
    candidate_entity_edit,
    commit_chat_turn,
    make_lease,
    open_moment,
    production_coordinator,
    reply_ok,
)

FOCUS = "res-hedge-i-think"
CANONICAL_ANSWER = "I think it is going to rain."
#: P5-R: the admitted class is the **whole-utterance** form-class RESOURCE
#: match, so the chat turn that lands a claim is the form itself (the learner
#: really produced the target, not a sentence containing it).
SILENT_UTTERANCE = "I think it is going to rain."
#: The same form inside a longer sentence: a real match the admission set
#: refuses (observation-only — zero claim, zero state).
EMBEDDED_UTTERANCE = "Well, I think it is going to rain tomorrow."
MISS_UTTERANCE = "I like this cafe."
MODALITY = "TEXT_PRODUCTION"

_CLAIM_COLUMNS = (
    "evidence_claim_id",
    "evidence_group_id",
    "target_type",
    "target_id",
    "performance_type",
    "polarity",
    "outcome",
    "claim_role",
    "source_turn_id",
    "teaching_moment_id",
    "attempt_id",
)


def _claims(db: sqlite3.Connection) -> tuple[dict[str, object], ...]:
    rows = db.execute(
        f"SELECT {', '.join(_CLAIM_COLUMNS)} FROM evidence_claim"
        " ORDER BY created_at, evidence_claim_id"
    ).fetchall()
    return tuple(dict(zip(_CLAIM_COLUMNS, row)) for row in rows)


def _count(db: sqlite3.Connection, statement: str) -> int:
    row = db.execute(statement).fetchone()
    assert row is not None
    return int(row[0])


def _state(db: sqlite3.Connection, target_id: str) -> dict[str, object] | None:
    row = db.execute(
        "SELECT state_json FROM learner_target_state"
        " WHERE target_id = ? AND evidence_modality = ?",
        (target_id, MODALITY),
    ).fetchone()
    return None if row is None else json.loads(str(row[0]))


def _coordinator(
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    targets,
    silent_source,
):
    return production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        targets,
        silent_evidence=silent_source,
    )


# ---------------------------------------------------------------------------
# ① the silent hit: claim + state, no teaching
# ---------------------------------------------------------------------------


def test_a_natural_turn_lands_one_silent_claim_and_moves_the_state(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM learner_target_state") == 0
    assert _count(db, "SELECT COUNT(*) FROM teaching_moment") == 0

    completion = commit_chat_turn(coordinator, "cm-p52-silent", SILENT_UTTERANCE, 1)
    print(f"[e2e] turn outcome -> {completion.outcome}")
    print(f"[e2e] reply        -> {completion.reply_text!r}")
    assert completion.outcome == "REPLIED_FULL"
    assert completion.reply_text

    claims = _claims(db)
    print(f"[e2e] claims -> {[(c['target_id'], c['claim_role']) for c in claims]}")
    assert len(claims) == 1
    claim = claims[0]
    assert claim["target_id"] == FOCUS
    assert claim["target_type"] == "RESOURCE"
    assert claim["claim_role"] == "SILENT_OBSERVATION"
    assert claim["performance_type"] == "SPONTANEOUS_PRODUCTION"
    assert claim["polarity"] == "POSITIVE"
    assert claim["outcome"] == "SUCCESS"
    assert claim["teaching_moment_id"] is None
    assert claim["attempt_id"] is None
    assert claim["source_turn_id"] == str(completion.turn_id)

    # The leg materialized the projection itself (validate → commit →
    # rebuild): no explicit rebuild call anywhere in this test.
    state = _state(db, FOCUS)
    assert state is not None, "the chain must create the state"
    dimensions = state["dimensions"]
    print(f"[e2e] spontaneous estimate -> {dimensions['spontaneous_production']}")
    assert dimensions["spontaneous_production"]["estimate"] not in (None, 0.0)
    assert dimensions["independent_production"]["estimate"] not in (None, 0.0)
    # P5-R: the claim carries a use-judgement (0.60), so the dimensions whose
    # per-dimension mass stays under §14's 0.55 effective-mass floor read
    # UNKNOWN — one rule-based observation is not enough to estimate
    # recognition (0.90 × 0.60) or guided production (0.80 × 0.60).
    print(
        "[e2e] recognition/guided estimates -> "
        f"{dimensions['recognition']['estimate']}/"
        f"{dimensions['guided_production']['estimate']}"
    )
    assert dimensions["recognition"]["estimate"] is None
    assert dimensions["guided_production"]["estimate"] is None
    assert state["coverage"]["evidence_groups"] == 1

    # Silent means silent: no moment, no gate, no lock, no attempt, no
    # opportunity was created anywhere.
    assert _count(db, "SELECT COUNT(*) FROM teaching_moment") == 0
    assert _count(db, "SELECT COUNT(*) FROM gate_decision") == 0
    assert _count(db, "SELECT COUNT(*) FROM active_teaching_lock") == 0
    assert _count(db, "SELECT COUNT(*) FROM attempt_record") == 0
    assert _count(db, "SELECT COUNT(*) FROM learning_opportunity_record") == 0


def test_the_p2a_artifact_is_target_bearing_only_on_a_hit(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    hit = commit_chat_turn(coordinator, "cm-p52-doc-hit", SILENT_UTTERANCE, 1)
    miss = commit_chat_turn(coordinator, "cm-p52-doc-miss", MISS_UTTERANCE, 2)

    documents = {
        str(turn_id): json.loads(str(document))
        for turn_id, document in db.execute(
            "SELECT turn_id, structured_proposal FROM analysis_artifact"
        ).fetchall()
    }
    hit_document = documents[str(hit.turn_id)]
    miss_document = documents[str(miss.turn_id)]
    print(f"[e2e] hit  target facts -> {hit_document.get('target')}")
    print(f"[e2e] miss target facts -> {miss_document.get('target')}")
    assert hit_document["target"]["target_id"] == FOCUS
    assert miss_document.get("target") is None
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 1


def test_the_leg_is_opt_in(
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
    """No silent source wired → the same utterance leaves the P2A shape: a
    claim-free group (every pre-P5-2 assembly stays what it was)."""

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
    completion = commit_chat_turn(coordinator, "cm-p52-noport", SILENT_UTTERANCE, 1)
    assert completion.outcome == "REPLIED_FULL"
    assert _count(db, "SELECT COUNT(*) FROM evidence_group") == 1
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM learner_target_state") == 0


# ---------------------------------------------------------------------------
# ② the misses and the degradations
# ---------------------------------------------------------------------------


def test_a_miss_leaves_the_evidence_empty(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    misses = (
        MISS_UTTERANCE,
        # F-1's counterexample, on the shipped chain: the single-token slot
        # key "see" must not turn an ordinary sentence into a claim.
        "I want to see that movie.",
        "What do you mean?",
        "The meeting starts at nine.",
        # P5-R's counterexamples, on the shipped chain: the form occurs, so
        # the matcher answers — and the admission set refuses the sentence
        # (embedded span; the others are pinned unit-level in
        # tests/phase5/test_p5_r_silent_admission.py).
        EMBEDDED_UTTERANCE,
        f"The phrase '{CANONICAL_ANSWER}' is in my textbook.",
        f"Don't say '{CANONICAL_ANSWER}'",
        "Right, I see.",
    )
    for index, utterance in enumerate(misses, start=1):
        completion = commit_chat_turn(
            coordinator, f"cm-p52-miss-{index}", utterance, index
        )
        print(f"[e2e] miss {index} -> outcome={completion.outcome} {utterance!r}")
        assert completion.outcome == "REPLIED_FULL"
        assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM learner_target_state") == 0
    # The P2A artifact is still the durable trace of every turn itself.
    assert _count(
        db, "SELECT COUNT(*) FROM analysis_artifact WHERE status = 'COMMITTED'"
    ) == len(misses)


def test_a_broken_supply_degrades_and_never_blocks(
    db: sqlite3.Connection,
    tmp_path: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    del conversation
    source = ContentBackedSilentTargets(
        ContentBackedTargetSupply(tmp_path / "absent" / "content.db")
    )
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        source,
    )
    completion = commit_chat_turn(coordinator, "cm-p52-broken", SILENT_UTTERANCE, 1)
    print(f"[e2e] broken supply -> outcome={completion.outcome}")
    assert completion.outcome == "REPLIED_FULL"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM learner_target_state") == 0


class _RaisingSource:
    """A source that violates its own best-effort contract on purpose."""

    def resolve_turn(self, turn):  # type: ignore[no-untyped-def]
        raise RuntimeError("injected resolver failure")


def test_a_raising_source_never_blocks_the_turn(
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
    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        _RaisingSource(),
    )
    completion = commit_chat_turn(coordinator, "cm-p52-raising", SILENT_UTTERANCE, 1)
    print(f"[e2e] raising source -> outcome={completion.outcome}")
    assert completion.outcome == "REPLIED_FULL"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0


# ---------------------------------------------------------------------------
# ③ the §24.11 supply filter, end to end
# ---------------------------------------------------------------------------


def test_a_candidate_is_never_credited_end_to_end(
    db: sqlite3.Connection,
    tmp_path: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    """The same utterance that resolves in the canonical corpus does not
    resolve onto an unapproved candidate; the approved control does."""

    del conversation
    artifact = build_variant_artifact(
        tmp_path, candidate_entity_edit("REVIEW_REQUIRED")
    )
    supply = ContentBackedTargetSupply(artifact)
    try:
        source = ContentBackedSilentTargets(supply)
        coordinator = _coordinator(
            conversation_store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            production_provider,
            source,
        )
        completion = commit_chat_turn(
            coordinator, "cm-p52-candidate", CANDIDATE_UNIQUE_FORM, 1
        )
    finally:
        supply.close()
    print(f"[e2e] candidate turn -> outcome={completion.outcome}")
    assert completion.outcome == "REPLIED_FULL"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM learner_target_state") == 0


def test_the_approved_control_of_the_candidate_is_credited(
    db: sqlite3.Connection,
    tmp_path: Path,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
) -> None:
    del conversation
    artifact = build_variant_artifact(
        tmp_path, candidate_entity_edit("CANONICAL_APPROVED")
    )
    supply = ContentBackedTargetSupply(artifact)
    try:
        source = ContentBackedSilentTargets(supply)
        coordinator = _coordinator(
            conversation_store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            production_provider,
            source,
        )
        commit_chat_turn(coordinator, "cm-p52-approved", CANDIDATE_UNIQUE_FORM, 1)
    finally:
        supply.close()
    claims = _claims(db)
    print(f"[e2e] approved control -> {[(c['target_id']) for c in claims]}")
    assert len(claims) == 1
    assert claims[0]["target_id"] == "res-candidate-not-approved"
    assert claims[0]["claim_role"] == "SILENT_OBSERVATION"


# ---------------------------------------------------------------------------
# ④ the teaching leg next to a silent claim
# ---------------------------------------------------------------------------


def test_the_teaching_leg_is_unchanged_next_to_a_silent_claim(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    """One silent hit, then one teaching cycle on the same target: the
    teaching claims are exactly the p5-1 chain's (moment/attempt linkage,
    SUCCESS/POSITIVE on the focus target), and the silent claim is left
    alone."""

    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    commit_chat_turn(coordinator, "cm-p52-mix-chat", SILENT_UTTERANCE, 1)
    silent_before = _claims(db)
    assert len(silent_before) == 1

    opened = open_moment(coordinator, "cm-p52-mix-open", FOCUS)
    print(
        f"[e2e] gate -> {opened.gate_execution_status}/{opened.gate_decision}"
    )
    assert opened.gate_execution_status == "SUCCEEDED"
    assert opened.gate_decision == "ALLOW"
    reply = reply_ok(coordinator, attempt(CANONICAL_ANSWER), "cm-p52-mix-attempt")
    assert reply.evaluation_outcome == "SUCCESS"

    claims = _claims(db)
    teaching = [
        claim for claim in claims if claim["claim_role"] != "SILENT_OBSERVATION"
    ]
    silent = [
        claim for claim in claims if claim["claim_role"] == "SILENT_OBSERVATION"
    ]
    print(
        "[e2e] teaching claims -> "
        f"{[(c['target_id'], c['outcome'], c['claim_role']) for c in teaching]}"
    )
    assert len(teaching) == 1
    assert teaching[0]["target_id"] == FOCUS
    assert teaching[0]["outcome"] == "SUCCESS"
    assert teaching[0]["polarity"] == "POSITIVE"
    assert teaching[0]["teaching_moment_id"] == str(opened.moment_id)
    assert teaching[0]["attempt_id"] == str(reply.attempt_id)
    assert len(silent) == 1
    assert silent[0]["teaching_moment_id"] is None
    assert silent[0]["attempt_id"] is None
    assert silent[0]["evidence_group_id"] != teaching[0]["evidence_group_id"]

    # The teaching chain's rebuild is its caller's move (the p5-1 E2E
    # precedent): rebuild explicitly, then both groups count.
    controller = LearningController(learning)
    rebuilt = controller.rebuild_learner_state(
        TargetId(FOCUS), EvidenceModality(MODALITY)
    )
    assert isinstance(rebuilt, Ok), rebuilt
    state = _state(db, FOCUS)
    assert state is not None
    print(f"[e2e] coverage after both -> {state['coverage']}")
    assert state["coverage"]["evidence_groups"] >= 2
    assert state["dimensions"]["spontaneous_production"]["estimate"] not in (
        None,
        0.0,
    )


def test_the_snapshot_reads_clean_next_to_a_silent_claim(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    """The leg's rebuild keeps the projections current: the Planner-facing
    snapshot read does not refuse after a silent hit (no lagging §11 row)."""

    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    commit_chat_turn(coordinator, "cm-p52-snap", SILENT_UTTERANCE, 1)
    controller = LearningController(learning)
    snapshot = controller.get_learning_snapshot()
    print(f"[e2e] snapshot -> {snapshot}")
    assert isinstance(snapshot, Ok), snapshot
    targets = {str(record.target_id) for record in snapshot.value.targets}
    assert FOCUS in targets
    state = controller.get_learner_target_state(
        TargetId(FOCUS), EvidenceModality(MODALITY)
    )
    assert isinstance(state, Ok) and state.value is not None
    assert state.value.target_type == "RESOURCE"


# ---------------------------------------------------------------------------
# ⑥ the open teaching window (F-2)
# ---------------------------------------------------------------------------


def test_an_open_moment_suppresses_the_same_target_observation(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    """The reverse order of the mixed scenario: a moment on the target is
    open (prompt sent, lock held) and the user then uses the form in free
    chat. The observation is skipped — a full exposure cannot produce
    independent evidence for the current Moment's target — so no claim is
    written, and the moment is untouched."""

    del conversation
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    opened = open_moment(coordinator, "cm-p52-window-open", FOCUS)
    assert opened.gate_decision == "ALLOW"
    assert opened.moment_id is not None

    claims_before = _count(db, "SELECT COUNT(*) FROM evidence_claim")
    completion = commit_chat_turn(
        coordinator, "cm-p52-window-chat", SILENT_UTTERANCE, 1
    )
    print(
        f"[e2e] open-moment window -> outcome={completion.outcome}"
        f" claims_before={claims_before}"
        f" claims_after={_count(db, 'SELECT COUNT(*) FROM evidence_claim')}"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _state(db, FOCUS) is None
    assert _count(db, "SELECT COUNT(*) FROM teaching_moment") == 1
    lock = db.execute(
        "SELECT moment_id FROM active_teaching_lock"
    ).fetchone()
    assert lock is not None and str(lock[0]) == str(opened.moment_id)
    assert _count(db, "SELECT COUNT(*) FROM evidence_group") == 1


def test_an_open_moment_about_another_target_does_not_suppress(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    production_provider,
    silent_targets,
) -> None:
    """The rule is target-scoped: the window only covers its own focus
    target."""

    del conversation
    other = "res-colloc-make-a-decision"
    coordinator = _coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_targets,
    )
    opened = open_moment(coordinator, "cm-p52-other-open", other)
    assert opened.gate_decision == "ALLOW"

    completion = commit_chat_turn(coordinator, "cm-p52-other-chat", SILENT_UTTERANCE, 1)
    assert completion.outcome == "REPLIED_FULL"
    claims = _claims(db)
    print(
        "[e2e] other-target window -> "
        f"{[(c['target_id'], c['claim_role']) for c in claims]}"
    )
    assert len(claims) == 1
    assert claims[0]["target_id"] == FOCUS
    assert claims[0]["claim_role"] == "SILENT_OBSERVATION"
    assert _state(db, FOCUS) is not None


def test_the_window_guard_is_absent_when_no_teaching_port_is_wired(
    db: sqlite3.Connection,
    conversation,
    conversation_store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    silent_targets,
) -> None:
    """Without the teaching port the assembly cannot open a moment at all
    (``request_teaching`` requires it), so the window is provably free and
    the observation proceeds — the P1/P2-shaped assembly keeps working."""

    del conversation
    persona = PersonaRuntime(
        actions=generation_store,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    coordinator = ConversationCoordinator(
        lease=make_lease(fence),
        conversation_commands=conversation_store,
        conversation_queries=conversation_store,
        persona=persona,
        generation_actions=generation_store,
        learning=learning,
        decision_cycles=decision_cycle_store,
        learning_controller=LearningController(learning),
        silent_evidence=silent_targets,
    )
    completion = commit_chat_turn(coordinator, "cm-p52-noteach", SILENT_UTTERANCE, 1)
    print(f"[e2e] no teaching port -> outcome={completion.outcome}")
    assert completion.outcome == "REPLIED_FULL"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 1
    assert _count(db, "SELECT COUNT(*) FROM teaching_moment") == 0


# ---------------------------------------------------------------------------
# ⑤ the module's own supply chain
# ---------------------------------------------------------------------------


def test_the_p5_2_modules_neither_seed_nor_import_the_fixture_supply() -> None:
    """The red line, made checkable, over every p5-2 test module: no
    `_seed`-style helper and no import of the P3 fixture supply."""

    modules = sorted(Path(__file__).resolve().parent.glob("test_p5_2_*.py"))
    assert len(modules) >= 3
    for path in modules:
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
        assert not [
            module for module in imported if "target_fixtures" in module
        ], path.name
        assert not [module for module in imported if "phase3" in module], path.name
        assert "_seed" not in calls, path.name
        print(f"[e2e] {path.name}: imports/calls are clean")


def test_the_fixture_supply_still_exists_for_the_phase_3_tests() -> None:
    """The P5-2 slice replaces nothing: the P3 tests keep their fixture
    (migration ≠ deletion — the P5-0 rule)."""

    from tests.conftest import REPO_ROOT

    fixture_module = REPO_ROOT / "tests" / "phase3" / "target_fixtures.py"
    assert fixture_module.is_file()


def test_the_supply_reads_the_repository_artifact_not_a_fixture(
    silent_supply: ContentBackedTargetSupply,
    production_provider,
) -> None:
    """The supply facts and the teaching provider agree on the same
    content.db rows (one artifact, two faces)."""

    facts = silent_supply.facts()
    assert isinstance(facts, Ok), facts
    hedge = next(fact for fact in facts.value if fact.target_id == FOCUS)
    resolved = production_provider.resolve("RESOURCE", FOCUS)
    assert isinstance(resolved, Ok), resolved
    assert hedge.canonical_forms == resolved.value.canonical_forms
    assert hedge.required_slots == resolved.value.required_slots
