"""④ — the four production-provider probes, printed verbatim.

`pytest tests/phase5/test_p5_1_provider_probes.py -s` reproduces the delivery
report's provider evidence instead of quoting it second-hand:

1. a known target resolves to ``Ok(VALID/VALID)`` and its view is the artifact
   row by row (the supply chain is content.db, not a fixture);
2. an unknown id — and an id of the *other* target kind — resolve to
   ``Err(NOT_FOUND)`` (the deterministic "no such target" the Gate turns into
   DENY TARGET_INVALID);
3. an unusable artifact (missing path, not-a-content.db, an artifact missing a
   required per-entity row) resolves to ``Err(DEPENDENCY_UNAVAILABLE)`` — the
   resolver could not answer, which the Gate degrades on;
4. a non-``CANONICAL_APPROVED`` entity is excluded from supply while staying
   readable, and resolves to its own deterministic non-VALID statuses
   (IMPLEMENTATION_PLAN §6 "candidate content excluded"; docs/DATA_MODEL.md
   §24.11).

Probes 1–3 run over the repository's own built artifact; probe 4 needs a
source that declares a candidate and a retired entity, so it builds one into a
pytest temp directory through the real build (the P5-0 bad-source-matrix
style) — the canonical corpus is never edited to make a test convenient.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from elc.content.store import ContentStore
from elc.content.types import (
    ARTIFACT_CONTENT_ORIGIN,
    CONTENT_ORIGINS,
    PERSONAL_CONTENT_WIRED,
    ContentOrigin,
    ExampleLinkRole,
    supply_eligible,
)
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import Err, Ok
from elc.teaching.targets import (
    CONTENT_STATUSES,
    TARGET_STATUSES,
    TeachingTargetView,
)
from tests.phase5.conftest import CONTENT_SRC_DIR, artifact_with_lifecycle

FOCUS = "res-hedge-i-think"
FOCUS_CAPABILITY = "cap-ref-ask-clarification"
CANDIDATE = "res-candidate-not-approved"
RETIRED = "res-retired-expression"


def _view(
    provider: ContentBackedTeachingTargetProvider, target_type: str, target_id: str
):
    result = provider.resolve(target_type, target_id)
    print(f"[probe] resolve({target_type!r}, {target_id!r}) -> {result}")
    return result


# ---------------------------------------------------------------------------
# probe 1 — a known target
# ---------------------------------------------------------------------------


def test_probe_1_known_target_resolves_valid(built_content_db: Path) -> None:
    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        result = _view(provider, "RESOURCE", FOCUS)
    finally:
        provider.close()

    assert isinstance(result, Ok), result
    view = result.value
    assert isinstance(view, TeachingTargetView)
    assert (view.target_type, view.target_status, view.content_status) == (
        "RESOURCE",
        "VALID",
        "VALID",
    )
    assert view.target_status in TARGET_STATUSES
    assert view.content_status in CONTENT_STATUSES

    # The view *is* the artifact row: every field reconciled against a direct
    # read of content.db (no fixture can satisfy this).
    store = ContentStore(built_content_db)
    try:
        target_row = store.get_target(FOCUS)
        teaching = store.get_teaching_content(FOCUS)
        canonical = store.get_examples(FOCUS, ExampleLinkRole.PRIMARY_TARGET)
        supporting = store.get_examples(FOCUS, ExampleLinkRole.SUPPORTING)
        print(f"[probe 1] content_target row      -> {target_row.value}")
        print(f"[probe 1] reveal_form             -> {teaching.value.reveal_form}")
        print(
            "[probe 1] capability_linkage      -> "
            f"{teaching.value.capability_linkage}"
        )
        assert isinstance(target_row, Ok) and isinstance(teaching, Ok)
        assert isinstance(canonical, Ok) and isinstance(supporting, Ok)
        assert view.target_mode == target_row.value.target_mode
        assert view.learning_intent == target_row.value.learning_intent
        assert view.evidence_modality == target_row.value.evidence_modality
        assert view.hint_ladder == teaching.value.hint_ladder
        assert view.reveal_form == teaching.value.reveal_form
        assert view.canonical_forms == teaching.value.canonical_forms
        assert view.canonical_forms == canonical.value
        assert view.alternative_realizations == teaching.value.alternative_realizations
        assert view.alternative_realizations == supporting.value
        assert view.required_slots == teaching.value.required_slots
        assert view.capability_linkage == teaching.value.capability_linkage
    finally:
        store.close()

    # A CAPABILITY target resolves too (it is the capability node's own
    # realization entity in the migrated corpus).
    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        capability = _view(provider, "CAPABILITY", FOCUS_CAPABILITY)
    finally:
        provider.close()
    assert isinstance(capability, Ok), capability
    assert capability.value.target_type == "CAPABILITY"
    assert capability.value.target_status == "VALID"
    assert capability.value.capability_linkage is None  # curriculum/README.md C1


# ---------------------------------------------------------------------------
# probe 2 — unknown ids (deterministic)
# ---------------------------------------------------------------------------


def test_probe_2_unknown_ids_are_not_found(built_content_db: Path) -> None:
    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        unknown = _view(provider, "RESOURCE", "res-does-not-exist")
        # the id exists, but not as this kind of target
        kind_mismatch = _view(provider, "CAPABILITY", FOCUS)
        kind_mismatch_reverse = _view(provider, "RESOURCE", FOCUS_CAPABILITY)
    finally:
        provider.close()

    for result in (unknown, kind_mismatch, kind_mismatch_reverse):
        assert isinstance(result, Err), result
        assert "NOT_FOUND" in str(result.error.code)


# ---------------------------------------------------------------------------
# probe 3 — an unusable artifact (the resolver cannot answer)
# ---------------------------------------------------------------------------


def test_probe_3_unusable_artifact_degrades(
    built_content_db: Path, tmp_path: Path
) -> None:
    missing = tmp_path / "not-built-yet" / "content.db"
    provider = ContentBackedTeachingTargetProvider(missing)
    try:
        absent = _view(provider, "RESOURCE", FOCUS)
    finally:
        provider.close()

    empty_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(empty_path))
    conn.execute("CREATE TABLE unrelated (x TEXT)")
    conn.commit()
    conn.close()
    provider = ContentBackedTeachingTargetProvider(empty_path)
    try:
        not_a_content_db = _view(provider, "RESOURCE", FOCUS)
    finally:
        provider.close()

    truncated = tmp_path / "truncated.db"
    shutil.copyfile(built_content_db, truncated)
    writable = sqlite3.connect(str(truncated))
    writable.execute("DELETE FROM content_target WHERE entity_id = ?", (FOCUS,))
    writable.commit()
    writable.close()
    provider = ContentBackedTeachingTargetProvider(truncated)
    try:
        broken_schema = _view(provider, "RESOURCE", FOCUS)
    finally:
        provider.close()

    for result in (absent, not_a_content_db, broken_schema):
        assert isinstance(result, Err), result
        assert "DEPENDENCY_UNAVAILABLE" in str(result.error.code)
    # ... and the healthy artifact on the same code path still answers.
    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        healthy = _view(provider, "RESOURCE", FOCUS)
    finally:
        provider.close()
    assert isinstance(healthy, Ok), healthy


# ---------------------------------------------------------------------------
# probe 4 — candidate exclusion + origin separation
# ---------------------------------------------------------------------------


def test_probe_4_candidates_are_excluded_and_origins_are_preserved(
    tmp_path: Path,
) -> None:
    artifact = artifact_with_lifecycle(
        tmp_path, {CANDIDATE: "REVIEW_REQUIRED", RETIRED: "DEPRECATED"}
    )
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        eligible = supply.supply_entity_ids()
        assert isinstance(eligible, Ok), eligible
        eligible_ids = tuple(str(entity_id) for entity_id in eligible.value)
        print(f"[probe 4] supply_entity_ids ({len(eligible_ids)}) -> {eligible_ids}")
        assert len(eligible_ids) == 51
        assert CANDIDATE not in eligible_ids
        assert RETIRED not in eligible_ids
        assert isinstance(store.entity_ids().value, tuple)
        assert len(store.entity_ids().value) == 53

        for entity_id in (CANDIDATE, RETIRED):
            # excluded, not deleted: still readable, still no readiness
            # level (P5-R strict reading — the whole corpus reads None), still
            # canonical origin
            assert isinstance(store.get_resource(entity_id), Ok)
            assert supply.content_origin(entity_id).value is ContentOrigin.CANONICAL
            assert supply.is_supply_eligible(entity_id).value is False
            assessment = supply.readiness(entity_id)
            assert assessment.value.level is None
            assert assessment.value.missing_keys == ("assessment_membership",)
        print(
            "[probe 4] origin of every artifact row -> "
            f"{ARTIFACT_CONTENT_ORIGIN} (declared set: {CONTENT_ORIGINS},"
            f" personal source wired: {PERSONAL_CONTENT_WIRED})"
        )
        assert supply.content_origin(FOCUS).value is ARTIFACT_CONTENT_ORIGIN
        assert supply.is_supply_eligible(FOCUS).value is True
        assert supply_eligible("CANONICAL_APPROVED") is True
    finally:
        store.close()

    provider = ContentBackedTeachingTargetProvider(artifact)
    try:
        candidate = _view(provider, "RESOURCE", CANDIDATE)
        retired = _view(provider, "RESOURCE", RETIRED)
    finally:
        provider.close()

    assert isinstance(candidate, Ok) and isinstance(retired, Ok)
    candidate_view = candidate.value
    retired_view = retired.value
    print(
        f"[probe 4] candidate statuses -> "
        f"({candidate_view.target_status}, {candidate_view.content_status})"
    )
    print(
        f"[probe 4] retired statuses   -> "
        f"({retired_view.target_status}, {retired_view.content_status})"
    )
    # §24.11: not approved is not "approved"; the Gate owns the DENY, and the
    # trace keeps the two reasons apart.
    assert (candidate_view.target_status, candidate_view.content_status) == (
        "INVALID",
        "INVALID",
    )
    assert (retired_view.target_status, retired_view.content_status) == (
        "DEPRECATED",
        "INVALID",
    )
    assert candidate_view.target_status in TARGET_STATUSES
    assert retired_view.target_status in TARGET_STATUSES
    assert candidate_view.content_status in CONTENT_STATUSES


def test_probe_4_an_unknown_entity_is_not_found_not_ineligible(
    built_content_db: Path,
) -> None:
    """``is_supply_eligible`` keeps "not in the registry" and "in the registry
    but not approved" apart — a silent False would erase that difference."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        unknown = supply.is_supply_eligible("res-does-not-exist")
        origin = supply.content_origin("res-does-not-exist")
        print(f"[probe 4] is_supply_eligible(unknown) -> {unknown}")
        print(f"[probe 4] content_origin(unknown)     -> {origin}")
        assert isinstance(unknown, Err) and isinstance(origin, Err)
        assert supply.is_supply_eligible(FOCUS).value is True
    finally:
        store.close()


def test_probe_4_no_personal_row_is_produced(built_content_db: Path) -> None:
    """The personal origin is an interface, not a producer: every artifact id
    is declared by the canonical authoring index, so no row can have come from
    anywhere else."""

    index = json.loads(
        (CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8")
    )
    declared = {
        str(entry).rsplit("/", 1)[-1].removesuffix(".json")
        for entry in index["entities"]
    }
    store = ContentStore(built_content_db)
    try:
        artifact_ids = set(store.entity_ids().value)
        supply = CurriculumContentStore(store)
        origins = {
            supply.content_origin(entity_id).value for entity_id in artifact_ids
        }
    finally:
        store.close()
    assert artifact_ids <= declared
    assert origins == {ContentOrigin.CANONICAL}
    assert PERSONAL_CONTENT_WIRED is False
    assert "PERSONAL" in CONTENT_ORIGINS
    print(
        f"[probe 4] artifact ids {len(artifact_ids)} ⊆ canonical index"
        f" {len(declared)}; origins={origins}"
    )


@pytest.mark.parametrize("target_id", (FOCUS, FOCUS_CAPABILITY))
def test_probe_1_provider_never_raises_on_any_input(
    built_content_db: Path, target_id: str
) -> None:
    """A resolver that raised would take the turn down; the port answers."""

    provider = ContentBackedTeachingTargetProvider(built_content_db)
    try:
        for target_type in ("RESOURCE", "CAPABILITY", "", "NONSENSE"):
            for identifier in (target_id, "res-nope", "", "../etc/passwd"):
                assert provider.resolve(target_type, identifier) is not None
    finally:
        provider.close()
