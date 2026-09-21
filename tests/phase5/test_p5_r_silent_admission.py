"""P5-R / D2 — the two-layer split: a match is not evidence.

The blocker this file closes (external review, TASK-OPI-a68fd9eb-…22 /
DEC-OPI-a68fd9eb-…15): P5-2's chat leg turned *any* string hit into a
SPONTANEOUS / POSITIVE / SUCCESS claim with ``evaluator_confidence = 1.0``
and ``support = exposure = NONE``, so a quoted, paraphrased, negated or
meta-linguistic use of a form — and a bare slot co-occurrence, and a lexical
hit on a CAPABILITY — minted strong Performance Evidence about the learner.

What is pinned here:

- the observation contract itself (fields, matcher certainty 1.0, span in the
  resolver's own coordinates);
- the V1 admission set, rule by rule: whole-sentence form-class RESOURCE
  only; the counterexample families (quotation / report / negation /
  meta-language / embedded span / slot-only / CAPABILITY) are each shown to
  be **real matches** that admission refuses — "observation-only: zero claim,
  zero LearnerState change";
- the confidence semantics: the admitted claim carries
  ``USE_JUDGMENT_CONFIDENCE`` (0.60), which clears BF-01 §10's state-mass
  floor (0.50) and fails §17's strong-retrieval floor (0.70);
- the durable-document boundary: the kernel re-applies admission to what the
  document says, so a hand-built document cannot mint what the live gate
  refuses;
- the end-to-end face: the same utterances through the shipped coordinator
  leave zero claims and zero state;
- purity and cold-start pins (the P4-3 lesson): the new modules are pure and
  every package still imports from a cold interpreter.

``1.0`` appears below only as the observation's ``match_certainty`` — never as
a claim confidence.
"""

from __future__ import annotations

import ast
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.conversation import CommitUserTurn
from elc.conversation.types import CanonicalTurnSlice
from elc.learning.analysis import (
    LearningEvidenceProposal,
    produce_learning_evidence_proposal,
)
from elc.learning.silent_claim import (
    SILENT_EVIDENCE_MODALITY,
    SILENT_OBSERVATION_CLAIM_ROLE,
    USE_JUDGMENT_CONFIDENCE,
)
from elc.learning.store import SqliteLearningStore
from elc.learning.target_match import (
    MATCH_CERTAINTY,
    TargetMatchObservation,
    admitted_for_evidence,
    observe_target_match,
    spans_the_whole_utterance,
)
from elc.learning.target_resolution import (
    NO_TARGET,
    MatchVia,
    ResolvedTarget,
    resolve_target,
)
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    EvidenceModality,
    InputId,
    InteractionChannel,
    Ok,
)
from elc.runtime.types import InputEnvelope
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase5.conftest import (
    REQUESTED_AT,
    RUNTIME_VERSION,
    commit_chat_turn,
    production_coordinator,
)

HEDGE = "res-hedge-i-think"
HEDGE_FORM = "I think it is going to rain."
BACKCHANNEL = "cap-interact-backchannel"
BACKCHANNEL_FORM = "Right, I see."
MODALITY = "TEXT_PRODUCTION"

#: Real matches the admission set must refuse, each named by the family it
#: belongs to (the review's list plus the two count-based classes).
OBSERVATION_ONLY: tuple[tuple[str, str], ...] = (
    ("embedded", f"Well, {HEDGE_FORM[:-1]} tomorrow."),
    ("quotation", f"The phrase '{HEDGE_FORM}' is in my textbook."),
    ("report", f"My teacher told me to say '{HEDGE_FORM}'"),
    ("negation", f"Don't say '{HEDGE_FORM}'"),
    ("meta-language", f"'{HEDGE_FORM}' is what she said"),
    ("trailing clause", f"{HEDGE_FORM[:-1]}, so bring a coat."),
)

#: Whole-utterance uses of the same form: the positive control.
ADMITTED: tuple[str, ...] = (
    HEDGE_FORM,
    "i think it is going to rain",
    "I THINK IT IS GOING TO RAIN!!!",
    "  I  think   it is going to rain.  ",
)


def _observation(utterance: str, resolution: ResolvedTarget) -> TargetMatchObservation:
    return observe_target_match(
        turn_id="turn-p5r", utterance=utterance, resolution=resolution
    )


def _hedge_resolution() -> ResolvedTarget:
    return ResolvedTarget(
        target_type="RESOURCE",
        target_id=HEDGE,
        matched_form=HEDGE_FORM,
        matched_via=MatchVia.CANONICAL_FORM,
    )


def _turn_slice(
    conversation_store: Any, conversation: ConversationId, cmid: str, text: str
) -> CanonicalTurnSlice:
    committed = conversation_store.commit_user_turn(
        CommitUserTurn(
            conversation_id=conversation,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{cmid}"),
                client_message_id=ClientMessageId(cmid),
                conversation_id=str(conversation),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{cmid}",
                received_at=REQUESTED_AT,
            ),
            raw_content=text,
            runtime_version=RUNTIME_VERSION,
        )
    )
    assert isinstance(committed, Ok), committed
    slice_result = conversation_store.get_canonical_turn_slice(
        committed.value.turn_id
    )
    assert isinstance(slice_result, Ok) and slice_result.value is not None
    return slice_result.value


def _claims(db: sqlite3.Connection) -> tuple[dict[str, Any], ...]:
    columns = (
        "evidence_claim_id",
        "target_id",
        "target_type",
        "claim_role",
        "evaluator_confidence",
        "polarity",
        "outcome",
    )
    rows = db.execute(f"SELECT {', '.join(columns)} FROM evidence_claim").fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


# ---------------------------------------------------------------------------
# ① the observation contract
# ---------------------------------------------------------------------------


def test_the_observation_carries_the_match_facts_and_the_matcher_certainty() -> None:
    observation = _observation(HEDGE_FORM, _hedge_resolution())
    assert observation.turn_id == "turn-p5r"
    assert (observation.target_type, observation.target_id) == ("RESOURCE", HEDGE)
    assert observation.matched_via is MatchVia.CANONICAL_FORM
    assert observation.matched_form == HEDGE_FORM
    assert observation.matched_span == "i think it is going to rain"
    assert observation.match_certainty == MATCH_CERTAINTY == 1.0
    # The observation decides nothing: no claim field, no state field.
    assert not hasattr(observation, "evaluator_confidence")


def test_the_span_is_located_in_the_utterances_comparison_coordinates() -> None:
    """``matched_span`` is the slice of the casefolded/collapsed utterance —
    deterministic, and equal to the whole utterance when it covers it."""

    observation = _observation(f"  Well, {HEDGE_FORM}  ", _hedge_resolution())
    assert observation.matched_span == "i think it is going to rain"
    assert (
        observe_target_match(
            turn_id="t", utterance="nothing of the kind", resolution=_hedge_resolution()
        ).matched_span
        == ""
    )


@pytest.mark.parametrize("utterance", ADMITTED)
def test_a_whole_utterance_form_class_resource_match_is_admitted(
    utterance: str,
) -> None:
    observation = _observation(utterance, _hedge_resolution())
    assert spans_the_whole_utterance(observation, utterance)
    assert admitted_for_evidence(observation, utterance)


@pytest.mark.parametrize(("family", "utterance"), OBSERVATION_ONLY)
def test_every_counted_counterexample_is_a_real_match_that_admission_refuses(
    family: str, utterance: str
) -> None:
    """The matcher still matches — that is the point: the string hit is real,
    and it is not evidence about the learner. (The corpus-level "it really
    resolves" half is pinned by the E2E block and by
    test_the_resolver_still_matches_the_counterexample_families.)"""

    observation = _observation(utterance, _hedge_resolution())
    assert observation.matched_span, family
    assert not spans_the_whole_utterance(observation, utterance), family
    assert not admitted_for_evidence(observation, utterance), family
    print(f"[p5-r] refused ({family}) -> {observation.matched_span!r}")


def test_a_capability_hit_is_observation_only_even_whole_sentence() -> None:
    """Admission rule 1: a lexical token is not evidence about a capability —
    no matter how exactly the sentence matches."""

    resolution = ResolvedTarget(
        target_type="CAPABILITY",
        target_id=BACKCHANNEL,
        matched_form=BACKCHANNEL_FORM,
        matched_via=MatchVia.CANONICAL_FORM,
    )
    observation = _observation(BACKCHANNEL_FORM, resolution)
    assert spans_the_whole_utterance(observation, BACKCHANNEL_FORM)
    assert not admitted_for_evidence(observation, BACKCHANNEL_FORM)


def test_a_non_admitted_span_never_spans_anything() -> None:
    resolution = _hedge_resolution()
    observation = observe_target_match(
        turn_id="t", utterance="unrelated turn", resolution=resolution
    )
    assert observation.matched_span == ""
    assert not spans_the_whole_utterance(observation, "unrelated turn")
    assert not admitted_for_evidence(observation, "unrelated turn")


def test_the_confidence_semantics_are_the_frozen_specs_bands() -> None:
    """0.60 is chosen against BF-01, not invented: above §10's state-mass
    floor, below §17's strong-retrieval floor (the estimator's own constants
    are the readings)."""

    from elc.learning.estimator import (
        CLAIM_MIN_CONFIDENCE,
        STRONG_RETRIEVAL_MIN_CONFIDENCE,
    )

    assert CLAIM_MIN_CONFIDENCE == 0.50
    assert STRONG_RETRIEVAL_MIN_CONFIDENCE == 0.70
    assert CLAIM_MIN_CONFIDENCE <= USE_JUDGMENT_CONFIDENCE < (
        STRONG_RETRIEVAL_MIN_CONFIDENCE
    )
    assert USE_JUDGMENT_CONFIDENCE == 0.60
    print(
        "[p5-r] confidence -> "
        f"{CLAIM_MIN_CONFIDENCE} <= {USE_JUDGMENT_CONFIDENCE} <"
        f" {STRONG_RETRIEVAL_MIN_CONFIDENCE}"
    )


def test_the_admission_modules_are_pure() -> None:
    """No model, no network, no clock, no DB, no filesystem in the two new
    policy modules (the AST pin the P5-2 resolver carries, extended)."""

    forbidden_modules = {
        "sqlite3",
        "os",
        "time",
        "datetime",
        "random",
        "uuid",
        "secrets",
        "socket",
        "urllib",
        "http",
        "requests",
        "subprocess",
        "pathlib",
        "json",
    }
    forbidden_names = {
        "open",
        "connect",
        "read_text",
        "write_text",
        "sleep",
        "now",
        "utcnow",
        "time",
    }
    for name in ("target_match.py", "silent_claim.py"):
        path = SRC_ROOT / "learning" / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        assert not (imported & forbidden_modules), (name, imported)
        assert not (names & forbidden_names), (name, names)
        # Only the module prologue, the stdlib dataclass plumbing and the
        # pure elc contracts (the resolver and the value types).
        allowed_prefixes = (
            "__future__",
            "dataclasses",
            "elc.learning.target_resolution",
            "elc.learning.target_match",
            "elc.learning.types",
        )
        for module in imported:
            assert module.startswith(allowed_prefixes), (name, module)


# ---------------------------------------------------------------------------
# ② the durable-document boundary (the kernel re-applies admission)
# ---------------------------------------------------------------------------


def _commit_document(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    turn: CanonicalTurnSlice,
    observed: ResolvedTarget,
    target: dict[str, Any],
):
    """Record an artifact whose ``target`` block is ``target``, then commit.

    The document is otherwise the producer's own (the utterance hash binds it
    to the canonical turn), so this is exactly the hand-edited/foreign row
    shape the trust-boundary probes use.
    """

    proposal = produce_learning_evidence_proposal(turn, resolution=observed)
    document = json.loads(proposal.structured_proposal)
    document["target"] = target
    serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
    db.execute(
        "INSERT INTO analysis_artifact (analysis_id, turn_id, analysis_type,"
        " producer_id, producer_version, structured_proposal, confidence,"
        " status, created_at) VALUES (?, ?, 'LEARNING_EVIDENCE', ?, ?, ?, ?,"
        " 'PRODUCED', ?)",
        (
            proposal.analysis_id,
            turn.turn_id,
            proposal.producer_id,
            proposal.producer_version,
            serialized,
            proposal.confidence,
            REQUESTED_AT,
        ),
    )
    db.commit()
    return learning.commit_learning_evidence(
        LearningEvidenceProposal(
            analysis_id=proposal.analysis_id,
            turn_id=proposal.turn_id,
            producer_id=proposal.producer_id,
            producer_version=proposal.producer_version,
            structured_proposal=serialized,
            confidence=proposal.confidence,
        ),
        turn,
    )


def test_a_whole_sentence_document_commits_exactly_one_claim(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
) -> None:
    """The positive control at the durable boundary."""

    turn = _turn_slice(conversation_store, conversation, "cm-p5r-doc-admit", HEDGE_FORM)
    committed = _commit_document(
        db,
        learning,
        turn,
        _hedge_resolution(),
        {
            "target_type": "RESOURCE",
            "target_id": HEDGE,
            "matched_form": HEDGE_FORM,
            "matched_via": "CANONICAL_FORM",
        },
    )
    assert isinstance(committed, Ok), committed
    claims = _claims(db)
    assert len(claims) == 1
    assert claims[0]["target_id"] == HEDGE
    assert claims[0]["claim_role"] == SILENT_OBSERVATION_CLAIM_ROLE
    assert claims[0]["evaluator_confidence"] == USE_JUDGMENT_CONFIDENCE


def test_an_embedded_document_commits_no_claim(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
) -> None:
    """The same document shape, but the turn is a sentence *containing* the
    form: the durable artifact still commits (the Phase 2 shape — one group,
    one commit, zero claims), and nothing is refused."""

    utterance = f"Well, {HEDGE_FORM[:-1]} tomorrow."
    turn = _turn_slice(conversation_store, conversation, "cm-p5r-doc-embed", utterance)
    resolution = ResolvedTarget(
        target_type="RESOURCE",
        target_id=HEDGE,
        matched_form=HEDGE_FORM,
        matched_via=MatchVia.CANONICAL_FORM,
    )
    committed = _commit_document(
        db,
        learning,
        turn,
        resolution,
        {
            "target_type": "RESOURCE",
            "target_id": HEDGE,
            "matched_form": HEDGE_FORM,
            "matched_via": "CANONICAL_FORM",
        },
    )
    assert isinstance(committed, Ok), committed
    assert _claims(db) == ()
    assert (
        db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1
    )
    assert (
        db.execute("SELECT COUNT(*) FROM evidence_commit").fetchone()[0] == 1
    )


@pytest.mark.parametrize(
    ("target", "utterance"),
    (
        (
            {
                "target_type": "CAPABILITY",
                "target_id": BACKCHANNEL,
                "matched_form": BACKCHANNEL_FORM,
                "matched_via": "CANONICAL_FORM",
            },
            BACKCHANNEL_FORM,
        ),
        (
            {
                "target_type": "RESOURCE",
                "target_id": HEDGE,
                "matched_form": "rain guess",
                "matched_via": "REQUIRED_SLOTS",
            },
            "The rain was heavy, I guess.",
        ),
        (
            {
                "target_type": "RESOURCE",
                "target_id": "res-not-in-any-supply",
                "matched_form": "a form no corpus carries",
                "matched_via": "CANONICAL_FORM",
            },
            HEDGE_FORM,
        ),
    ),
)
def test_a_non_admitted_document_commits_no_claim(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    target: dict[str, Any],
    utterance: str,
) -> None:
    """CAPABILITY, slot-only and not-located documents: readable, admitted by
    nothing, zero claims — the observation-only classes at the kernel."""

    turn = _turn_slice(
        conversation_store, conversation, f"cm-p5r-{target['target_id']}", utterance
    )
    resolution = ResolvedTarget(
        target_type=str(target["target_type"]),
        target_id=str(target["target_id"]),
        matched_form=str(target["matched_form"]),
        matched_via=MatchVia(str(target["matched_via"])),
    )
    committed = _commit_document(db, learning, turn, resolution, target)
    assert isinstance(committed, Ok), committed
    assert _claims(db) == ()


# ---------------------------------------------------------------------------
# ③ end to end: the same turns through the shipped coordinator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "utterance",
    (
        *(utterance for _family, utterance in OBSERVATION_ONLY),
        "The rain was heavy, I guess.",
        BACKCHANNEL_FORM,
    ),
)
def test_observation_only_turns_leave_zero_claims_and_zero_state(
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
    utterance: str,
) -> None:
    """The chat is untouched (REPLIED_FULL), and the evidence is empty: the
    utterance really matches (the corpus resolves it), admission refuses it,
    nothing durable moves."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_evidence=silent_targets,
    )
    completion = commit_chat_turn(coordinator, "cm-p5r-obs", utterance, 1)
    print(f"[p5-r] observation-only turn -> outcome={completion.outcome} {utterance!r}")
    assert completion.outcome == "REPLIED_FULL"
    assert _claims(db) == ()
    assert (
        db.execute("SELECT COUNT(*) FROM learner_target_state").fetchone()[0] == 0
    )
    # The turn is still the durable trace of itself (P2A, unchanged).
    document = json.loads(
        db.execute(
            "SELECT structured_proposal FROM analysis_artifact"
        ).fetchone()[0]
    )
    assert "target" not in document


def test_the_positive_control_through_the_coordinator_lands_one_claim(
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
    """A whole-sentence RESOURCE use is the one admitted class: exactly one
    SILENT_OBSERVATION claim, at the judgement confidence, and the §11
    projection moves."""

    del conversation
    coordinator = production_coordinator(
        conversation_store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        production_provider,
        silent_evidence=silent_targets,
    )
    completion = commit_chat_turn(coordinator, "cm-p5r-control", HEDGE_FORM, 1)
    assert completion.outcome == "REPLIED_FULL"
    claims = _claims(db)
    assert len(claims) == 1
    assert claims[0]["target_id"] == HEDGE
    assert claims[0]["claim_role"] == SILENT_OBSERVATION_CLAIM_ROLE
    assert claims[0]["evaluator_confidence"] == USE_JUDGMENT_CONFIDENCE
    assert claims[0]["polarity"] == "POSITIVE"
    assert claims[0]["outcome"] == "SUCCESS"
    document = json.loads(
        db.execute("SELECT structured_proposal FROM analysis_artifact").fetchone()[0]
    )
    assert document["target"]["target_id"] == HEDGE
    assert (
        db.execute(
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (HEDGE,),
        ).fetchone()[0]
        == 1
    )
    assert SILENT_EVIDENCE_MODALITY == EvidenceModality.TEXT_PRODUCTION.value
    assert MODALITY == SILENT_EVIDENCE_MODALITY


# ---------------------------------------------------------------------------
# ④ the resolver is unchanged (the observation layer wraps it, never edits it)
# ---------------------------------------------------------------------------


def test_the_resolver_still_matches_the_counterexample_families(
    silent_supply,
) -> None:
    """The split is *above* the matcher: the resolver's own answers for the
    counterexample turns are unchanged (the P5-2 rule table stays frozen)."""

    facts = silent_supply.facts()
    assert isinstance(facts, Ok), facts
    for _family, utterance in OBSERVATION_ONLY:
        resolution = resolve_target(utterance, facts.value)
        assert resolution is not NO_TARGET, utterance
        assert resolution.target_id == HEDGE, utterance
    slot_hit = resolve_target("The rain was heavy, I guess.", facts.value)
    assert slot_hit is not NO_TARGET
    assert slot_hit.matched_via is MatchVia.REQUIRED_SLOTS
    print("[p5-r] the P5-2 rule table is unchanged under the admission layer")


# ---------------------------------------------------------------------------
# ⑤ purity and cold start
# ---------------------------------------------------------------------------


def test_every_package_and_the_new_module_import_from_a_cold_interpreter() -> None:
    """The P4-3 lesson, applied to this slice's cross-package edge
    (elc.runtime.controller and elc.learning.store now import
    elc.learning.target_match): a fresh interpreter importing one package
    first must succeed, for every package a caller could start from."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(SRC_ROOT.parent),
    )
    for module in (
        "elc.learning.target_match",
        "elc.learning.silent_claim",
        "elc.learning",
        "elc.runtime",
        "elc.content.store",
        "elc.curriculum.readiness",
        "elc.curriculum.store",
        "elc.teaching",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{module}: {proc.stderr}"


def test_the_new_p5_r_test_modules_neither_seed_nor_fake_supply() -> None:
    """The P5-0/P5-2 red line over this slice's own tests: no `_seed`-style
    helper, no P3 fixture import, no hand-built supply facts for the E2E legs
    (the pure unit block builds facts by hand on purpose — it resolves no
    supply)."""

    modules = sorted(Path(__file__).resolve().parent.glob("test_p5_r_*.py"))
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
        assert not [module for module in imported if "target_fixtures" in module], (
            path.name
        )
        assert not [module for module in imported if "phase3" in module], path.name
        assert "_seed" not in calls, path.name
        print(f"[p5-r] {path.name}: imports/calls are clean")
