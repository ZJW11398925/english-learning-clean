"""D-2 — the build seam: the EV derivation through the real build step.

Pinned here: the default path's byte-identity (``None`` ≡ empty registry ≡
the pre-D-2 artifact), the promotion (a stub that passes one real entity's
full fixture set promotes exactly that entity), the honest no-pass (a
failing stub keeps every level and refuses nothing), the three refusal
faces (dangling rule ordinal, undocumented entity, raising matcher), and
the one-way dependency pin (``elc.detection`` never imports
``elc.content``).
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from elc.content.build import BuildError, build_content_db
from elc.content.store import ContentStore
from elc.detection import DetectorRegistry
from elc.platform.types import Ok
from tests.conftest import SRC_ROOT
from tests.detection.support import (
    ANYWAY_ENTITY,
    always_match,
    anyway_stub,
    copy_source_trees,
    never_match,
    provenance_map,
)

DETECTION_ROOT = SRC_ROOT / "detection"


def test_default_and_empty_registry_builds_are_byte_identical(
    tmp_path: Path,
) -> None:
    """``None`` (the default, and what the CLI passes) and an explicitly
    handed-in empty registry produce the same bytes and the same 100-row
    provenance table with zero EV/EC rows — the pre-D-2 artifact."""

    default = tmp_path / "default.db"
    empty = tmp_path / "empty-registry.db"
    build_content_db(default)
    build_content_db(empty, detector_registry=DetectorRegistry())
    assert hashlib.sha256(default.read_bytes()).digest() == hashlib.sha256(
        empty.read_bytes()
    ).digest()
    baseline = provenance_map(default)
    assert baseline == provenance_map(empty)
    assert len(baseline) == 100
    levels = list(baseline.values())
    assert levels.count("EXECUTABLY_VERIFIED") == 0
    assert levels.count("EMPIRICALLY_CALIBRATED") == 0


def test_a_passing_stub_promotes_its_entity_and_only_its_entity(
    tmp_path: Path,
) -> None:
    """A stub that passes res-discourse-anyway's own five fixtures lifts
    exactly that entity to EXECUTABLY_VERIFIED — every other entity's level
    is untouched, and the store read face carries the promoted row."""

    content_src, curriculum = copy_source_trees(tmp_path)
    baseline_db = tmp_path / "baseline.db"
    build_content_db(
        baseline_db, content_src_dir=content_src, curriculum_dir=curriculum
    )
    baseline = provenance_map(baseline_db)
    assert baseline[ANYWAY_ENTITY] != "EXECUTABLY_VERIFIED"

    registry = DetectorRegistry()
    registry.register(ANYWAY_ENTITY, (0,), anyway_stub)
    promoted_db = tmp_path / "promoted.db"
    build_content_db(
        promoted_db,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=registry,
    )
    promoted = provenance_map(promoted_db)
    assert promoted[ANYWAY_ENTITY] == "EXECUTABLY_VERIFIED"
    assert sum(
        1 for level in promoted.values() if level == "EXECUTABLY_VERIFIED"
    ) == 1
    others_promoted = {
        entity: level
        for entity, level in promoted.items()
        if entity != ANYWAY_ENTITY
    }
    others_baseline = {
        entity: level
        for entity, level in baseline.items()
        if entity != ANYWAY_ENTITY
    }
    assert others_promoted == others_baseline

    store = ContentStore(promoted_db)
    try:
        rows = store.provenance_levels()
        assert isinstance(rows, Ok), rows
    finally:
        store.close()
    read = dict(rows.value)
    assert read[ANYWAY_ENTITY] == "EXECUTABLY_VERIFIED"
    assert (
        sum(1 for level in read.values() if level == "EXECUTABLY_VERIFIED") == 1
    )


def test_a_failing_stub_keeps_every_level_and_refuses_nothing(
    tmp_path: Path,
) -> None:
    """The honest no-pass: a stub that never matches fails the positive row,
    so its entity is not promoted — and the build does not refuse (a
    fixture failure is a report state, the state D-3 iterates from)."""

    content_src, curriculum = copy_source_trees(tmp_path)
    baseline_db = tmp_path / "baseline.db"
    build_content_db(
        baseline_db, content_src_dir=content_src, curriculum_dir=curriculum
    )
    baseline = provenance_map(baseline_db)

    registry = DetectorRegistry()
    registry.register(ANYWAY_ENTITY, (0,), never_match)
    failed_db = tmp_path / "failed.db"
    build_content_db(
        failed_db,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=registry,
    )
    assert provenance_map(failed_db) == baseline
    assert "EXECUTABLY_VERIFIED" not in provenance_map(failed_db).values()


def test_a_dangling_rule_ordinal_is_refused_with_the_legal_set(
    tmp_path: Path,
) -> None:
    content_src, curriculum = copy_source_trees(tmp_path)
    registry = DetectorRegistry()
    registry.register(ANYWAY_ENTITY, (99,), never_match)
    with pytest.raises(BuildError) as raised:
        build_content_db(
            tmp_path / "out.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
            detector_registry=registry,
        )
    message = str(raised.value)
    assert (
        "rule ordinal 99 is not one of the entity's declared rule ordinals"
        in message
    )
    assert "[0, 1, 2, 3]" in message


def test_a_registration_for_an_undocumented_entity_is_refused(
    tmp_path: Path,
) -> None:
    content_src, curriculum = copy_source_trees(tmp_path)
    registry = DetectorRegistry()
    registry.register("res-not-in-the-corpus", (), never_match)
    with pytest.raises(BuildError) as raised:
        build_content_db(
            tmp_path / "out.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
            detector_registry=registry,
        )
    message = str(raised.value)
    assert "res-not-in-the-corpus" in message
    assert "is not a documented entity" in message


def test_a_raising_matcher_is_wrapped_into_a_build_error(
    tmp_path: Path,
) -> None:
    """A matcher exception is a registration defect: the build names the
    detector and never swallows the exception."""

    content_src, curriculum = copy_source_trees(tmp_path)

    def exploding_matcher(text: str) -> object:
        raise ZeroDivisionError("division by zero")

    registry = DetectorRegistry()
    registry.register(ANYWAY_ENTITY, (), exploding_matcher)
    with pytest.raises(BuildError) as raised:
        build_content_db(
            tmp_path / "out.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
            detector_registry=registry,
        )
    message = str(raised.value)
    assert f"detector for {ANYWAY_ENTITY} raised ZeroDivisionError" in message
    assert isinstance(raised.value.__cause__, ZeroDivisionError)


def test_an_empty_fixture_set_never_verifies_even_when_registered(
    tmp_path: Path,
) -> None:
    """The ``fixture_count > 0`` guard (D-2 review LOW-1). An entity whose
    evidence omits the ``detection_fixtures`` block carries nothing to
    verify — the block is optional (the reader answers ``()`` for an
    absent block), so a registered always-matching stub must not promote
    it: an empty set passes vacuously, and verification requires something
    to have been verified. The ``typical_errors`` block goes with it,
    because D-1's per-type coverage would otherwise refuse the tree (a
    declared error_type with no positive row). The unreachable-in-corpus
    guard is reachable exactly here, through the tmp tree."""

    content_src, curriculum = copy_source_trees(tmp_path)
    evidence = content_src / "evidence" / f"{ANYWAY_ENTITY}.json"
    document = json.loads(evidence.read_text(encoding="utf-8"))
    del document["typical_errors"]
    del document["detection_fixtures"]
    evidence.write_text(json.dumps(document), encoding="utf-8")

    registry = DetectorRegistry()
    registry.register(ANYWAY_ENTITY, (), always_match("SPLIT_SPELLING"))

    baseline = tmp_path / "baseline.db"
    build_content_db(
        baseline, content_src_dir=content_src, curriculum_dir=curriculum
    )
    promoted = tmp_path / "promoted.db"
    build_content_db(
        promoted,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=registry,
    )

    baseline_levels = provenance_map(baseline)
    assert provenance_map(promoted) == baseline_levels
    assert baseline_levels[ANYWAY_ENTITY] != "EXECUTABLY_VERIFIED"
    assert "EXECUTABLY_VERIFIED" not in baseline_levels.values()


def test_the_detection_package_never_imports_content() -> None:
    """One-way dependency: ``content.build → detection``, never the
    reverse — pinned as an AST import scan over src/elc/detection/**."""

    offenders: list[str] = []
    for path in sorted(DETECTION_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "elc.content" or alias.name.startswith(
                        "elc.content."
                    ):
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "elc.content" or module.startswith("elc.content."):
                    offenders.append(f"{path.name}: from {module} import ...")
    assert not offenders, f"elc.detection imports elc.content: {offenders}"
