"""VAL ⑦ — Validator ≠ Evaluator static separation.

- elc.learning's import face has NO elc.persona dependency (AST scan of
  every learning module): the estimator consumes canonical evidence,
  never persona opinions (BF-01 §2 "Relationship opinion"/persona
  inputs are banned from the estimator).
- elc.persona.validator has no evidence-write path: the Response
  Validator decides ACCEPT/RETRY/ABORT_DELIVERY on (output, contract)
  and never writes Learning truth (STATE_MACHINES §15 /
  DOMAIN_MODEL §18 proposal-only). Pinned both statically (AST: no
  evidence kernel symbols / SQL) and behaviorally (a validation run
  against a live kernel leaves the evidence tables and the watermark
  untouched).
"""

from __future__ import annotations

import ast
import sqlite3

from elc.learning.store import SqliteLearningStore
from elc.learning.types import (
    AttemptOutcome,
    EvidencePolarity,
    PerformanceType,
)
from elc.persona import ResponseValidator
from elc.persona.types import ProviderOutput
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import ActionId
from tests.conftest import SRC_ROOT
from tests.phase2.conftest import commit_ok, make_claim, make_group

#: Evidence-kernel write surfaces that must never appear inside
#: elc.persona.validator (identifier/attribute name scan).
EVIDENCE_WRITE_SYMBOLS = (
    "commit_evidence_group",
    "commit_learning_evidence",
    "supersede_claim",
    "invalidate_claim",
    "rebuild_learner_state",
    "record_self_report",
    "record_opportunity",
    "record_expression_need",
    "_bump_watermark",
    "INSERT INTO evidence_claim",
    "INSERT INTO evidence_group",
    "UPDATE evidence_claim",
    "INSERT INTO learner_target_state",
)


def _module_names(tree: ast.AST) -> list[tuple[str, int]]:
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append((node.module, node.lineno))
    return names


def test_learning_package_never_imports_persona() -> None:
    """The Learning kernel (estimator included) is evidence-derived
    only — no elc.persona import anywhere in the package."""
    offenders: list[str] = []
    for path in sorted((SRC_ROOT / "learning").rglob("*.py")):
        for module, lineno in _module_names(
            ast.parse(path.read_text(encoding="utf-8"))
        ):
            if module == "elc.persona" or module.startswith("elc.persona."):
                offenders.append(f"{path}:{lineno}: {module}")
    assert not offenders, offenders


def test_persona_validator_module_has_no_evidence_write_path() -> None:
    """elc.persona.validator is a pure decision function: no evidence
    kernel imports, no evidence write symbols, no SQL at all."""
    validator_path = SRC_ROOT / "persona" / "validator.py"
    tree = ast.parse(validator_path.read_text(encoding="utf-8"))
    for module, lineno in _module_names(tree):
        assert not (
            module == "elc.learning"
            or module.startswith("elc.learning.")
        ), f"validator.py:{lineno} imports {module}"
    source = validator_path.read_text(encoding="utf-8")
    for symbol in EVIDENCE_WRITE_SYMBOLS:
        assert symbol not in source, symbol
    # No SQL statement of any kind in the validator module.
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.upper()
            assert not value.startswith(("SELECT ", "INSERT ", "UPDATE ",
                                         "DELETE ")), node.value


def test_persona_package_imports_of_learning_are_read_none(
) -> None:
    """Beyond the validator itself: no elc.persona module imports the
    learning store (the persona runtime never touches the evidence
    kernel directly — only the coordinator orchestrates both)."""
    offenders: list[str] = []
    for path in sorted((SRC_ROOT / "persona").rglob("*.py")):
        for module, lineno in _module_names(
            ast.parse(path.read_text(encoding="utf-8"))
        ):
            if module.startswith("elc.learning"):
                offenders.append(f"{path}:{lineno}: {module}")
    assert not offenders, offenders


def test_validation_run_leaves_the_evidence_kernel_untouched(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Behavioral pin: running the Response Validator over provider
    outputs changes no evidence row and does not move the watermark."""

    cp0 = commit_ok(store, conversation, "cm-sep", "validator separation")
    committed = learning.commit_evidence_group(
        make_group("eg-sep", (make_claim(),)),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert committed is not None
    watermark_before = learning.get_evidence_watermark()
    claims_before = db.execute(
        "SELECT COUNT(*) FROM evidence_claim"
    ).fetchone()[0]

    validator = ResponseValidator()
    outcomes = []
    for text in (
        "",  # no output → RETRY
        "You have mastered this expression completely!",
        "Sure — let's practice that phrase.",
    ):
        output = ProviderOutput(text=text)
        result = validator.validate(
            ActionId("act-sep"), 1, output, contract=None
        )
        outcomes.append(result.decision)
    assert outcomes  # the validator ran and decided

    assert db.execute(
        "SELECT COUNT(*) FROM evidence_claim"
    ).fetchone()[0] == claims_before
    assert learning.get_evidence_watermark() == watermark_before
    # And the projection is untouched by persona validation.
    assert db.execute(
        "SELECT COUNT(*) FROM learner_target_state"
    ).fetchone()[0] == 0


def test_persona_validator_decision_face_has_no_evidence_vocabulary() -> None:
    """The validator's own decision surface is ACCEPT/RETRY/FALLBACK/
    ABORT_DELIVERY (STATE_MACHINES §15) — no EvidenceStatus word can
    appear as a decision."""
    from elc.persona.types import ValidatorDecision

    decisions = {decision.value for decision in ValidatorDecision}
    from elc.learning.types import EvidenceStatus

    assert decisions.isdisjoint(
        {status.value for status in EvidenceStatus}
    )
    # The learning vocabulary and the validator vocabulary are disjoint
    # worlds.
    assert PerformanceType.RECOGNITION.value not in decisions
    assert EvidencePolarity.POSITIVE.value not in decisions
    assert AttemptOutcome.SUCCESS.value not in decisions
