"""③ — the p5-2 supply read face: §24.11 filter, schema honesty, degradation.

`elc.learning.silent_evidence.ContentBackedTargetSupply` is the only piece of
this slice that touches content.db. Its contract, pinned here:

- a fact exists exactly for the entities the §24.11 supply filter admits
  (``CANONICAL_APPROVED``; the curriculum supply face applies it), so a
  candidate or any other unapproved entity can never be resolved onto;
- a fact carries the authored §24.5 payload verbatim, in artifact order,
  deterministically;
- a missing, junk or schema-less artifact is an ``Err(DEPENDENCY_UNAVAILABLE)``
  — never a partial answer, never a NOT_FOUND ("cannot answer" and "answered
  nothing" stay different facts, the P5-1 provider discipline);
- ownership follows the construction: a caller-supplied store is the
  caller's to close, a path-opened one is opened lazily and released by
  ``close()``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.content.store import ContentStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.learning.silent_evidence import ContentBackedTargetSupply
from elc.learning.target_resolution import NO_TARGET, resolve_target
from elc.platform.types import DomainErrorCode, Err, Ok
from tests.phase5.conftest import (
    CANDIDATE_UNIQUE_FORM,
    build_variant_artifact,
    candidate_entity_edit,
)

CANDIDATE = "res-candidate-not-approved"
UNIQUE_CANDIDATE_FORM = CANDIDATE_UNIQUE_FORM


def _supply_ids(supply: ContentBackedTargetSupply) -> set[str]:
    facts = supply.facts()
    assert isinstance(facts, Ok), facts
    return {fact.target_id for fact in facts.value}


def _unavailable(error) -> bool:
    return error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE


# ---------------------------------------------------------------------------
# ① the happy read
# ---------------------------------------------------------------------------


def test_facts_cover_exactly_the_supply_eligible_entities(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    eligible = silent_supply._supply_result().value.supply_entity_ids()
    assert isinstance(eligible, Ok), eligible
    assert _supply_ids(silent_supply) == {str(i) for i in eligible.value}
    assert len(eligible.value) == 69


def test_facts_carry_the_authored_payload_verbatim(
    silent_supply: ContentBackedTargetSupply, store: ContentStore
) -> None:
    facts = silent_supply.facts()
    assert isinstance(facts, Ok), facts
    fact = next(
        item for item in facts.value if item.target_id == "res-hedge-i-think"
    )
    teaching = store.get_teaching_content("res-hedge-i-think")
    assert isinstance(teaching, Ok), teaching
    assert fact.canonical_forms == teaching.value.canonical_forms
    assert fact.alternative_realizations == (
        teaching.value.alternative_realizations
    )
    assert fact.required_slots == teaching.value.required_slots


def test_facts_carry_only_the_canonical_kinds(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    facts = silent_supply.facts()
    assert isinstance(facts, Ok), facts
    assert {fact.target_type for fact in facts.value} == {
        "RESOURCE",
        "CAPABILITY",
    }


def test_two_reads_are_identical(silent_supply: ContentBackedTargetSupply) -> None:
    assert silent_supply.facts() == silent_supply.facts()


# ---------------------------------------------------------------------------
# ② the §24.11 supply filter (candidate exclusion)
# ---------------------------------------------------------------------------


def _candidate_edit(lifecycle: str):
    """The shared candidate edit (tests/phase5/conftest.candidate_entity_edit)
    under the name this file's probes read better with."""

    return candidate_entity_edit(lifecycle)


def test_an_unapproved_candidate_never_becomes_a_fact(tmp_path: Path) -> None:
    artifact = build_variant_artifact(
        tmp_path, _candidate_edit("REVIEW_REQUIRED")
    )
    supply = ContentBackedTargetSupply(artifact)
    try:
        facts = supply.facts()
        assert isinstance(facts, Ok), facts
        assert CANDIDATE not in {fact.target_id for fact in facts.value}
        assert resolve_target(UNIQUE_CANDIDATE_FORM, facts.value) is NO_TARGET
    finally:
        supply.close()


def test_the_same_entity_approved_becomes_a_matchable_fact(
    tmp_path: Path,
) -> None:
    """The control for the exclusion: same corpus edit, approved lifecycle."""

    artifact = build_variant_artifact(
        tmp_path, _candidate_edit("CANONICAL_APPROVED")
    )
    supply = ContentBackedTargetSupply(artifact)
    try:
        facts = supply.facts()
        assert isinstance(facts, Ok), facts
        assert CANDIDATE in {fact.target_id for fact in facts.value}
        resolution = resolve_target(UNIQUE_CANDIDATE_FORM, facts.value)
        assert resolution is not NO_TARGET
        assert resolution.target_id == CANDIDATE
    finally:
        supply.close()


def test_a_retired_entity_is_excluded_the_same_way(tmp_path: Path) -> None:
    artifact = build_variant_artifact(tmp_path, _candidate_edit("DEPRECATED"))
    supply = ContentBackedTargetSupply(artifact)
    try:
        assert CANDIDATE not in _supply_ids(supply)
    finally:
        supply.close()


def test_the_teaching_provider_still_reads_the_excluded_entity(
    tmp_path: Path,
) -> None:
    """Excluded ≠ deleted (the P5-1 rule): the supply filter drops the
    candidate from *matching*, while the teaching port still answers its
    deterministic non-validity.

    Hmm — the port answers DEPRECATED/INVALID for a retired entity and
    INVALID for an unapproved one; either way the entity stays *readable*.
    """

    artifact = build_variant_artifact(
        tmp_path, _candidate_edit("REVIEW_REQUIRED")
    )
    provider = ContentBackedTeachingTargetProvider(artifact)
    try:
        resolved = provider.resolve("RESOURCE", CANDIDATE)
        assert isinstance(resolved, Ok), resolved
        assert resolved.value.content_status == "INVALID"
    finally:
        provider.close()


# ---------------------------------------------------------------------------
# ③ degradation: a supply the reader cannot answer from
# ---------------------------------------------------------------------------


def test_a_missing_artifact_is_dependency_unavailable(tmp_path: Path) -> None:
    supply = ContentBackedTargetSupply(tmp_path / "absent" / "content.db")
    try:
        facts = supply.facts()
        assert isinstance(facts, Err), facts
        assert _unavailable(facts.error)
    finally:
        supply.close()


def test_a_junk_file_is_dependency_unavailable(tmp_path: Path) -> None:
    artifact = tmp_path / "content.db"
    artifact.write_bytes(b"this is not a database")
    supply = ContentBackedTargetSupply(artifact)
    try:
        facts = supply.facts()
        assert isinstance(facts, Err), facts
        assert _unavailable(facts.error)
    finally:
        supply.close()


def test_a_schema_less_artifact_is_dependency_unavailable(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "content.db"
    connection = sqlite3.connect(artifact)
    try:
        connection.execute("CREATE TABLE something_else (x TEXT)")
        connection.commit()
    finally:
        connection.close()
    supply = ContentBackedTargetSupply(artifact)
    try:
        facts = supply.facts()
        assert isinstance(facts, Err), facts
        assert _unavailable(facts.error)
        assert "rebuild it with elc.content.build" in facts.error.message
    finally:
        supply.close()


def test_a_broken_artifact_never_raises_out_of_the_read(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "content.db"
    artifact.write_bytes(b"\x00\x01\x02")
    supply = ContentBackedTargetSupply(artifact)
    try:
        # Three reads, three refusals — the reader stays usable after each.
        for _ in range(3):
            facts = supply.facts()
            assert isinstance(facts, Err), facts
    finally:
        supply.close()


# ---------------------------------------------------------------------------
# ④ ownership
# ---------------------------------------------------------------------------


def test_a_caller_supplied_store_is_not_closed_by_the_reader(
    built_content_db: Path,
) -> None:
    store = ContentStore(built_content_db)
    supply = ContentBackedTargetSupply(CurriculumContentStore(store))
    try:
        supply.close()
        assert isinstance(store.entity_ids(), Ok), "the caller's store was closed"
    finally:
        store.close()


def test_a_path_opened_reader_reopens_after_close(built_content_db: Path) -> None:
    supply = ContentBackedTargetSupply(built_content_db)
    assert isinstance(supply.facts(), Ok)
    supply.close()
    assert isinstance(supply.facts(), Ok), "the lazy open must survive close()"
    supply.close()


@pytest.mark.parametrize("entity_id", ("res-hedge-i-think", "cap-disc-topic-shift"))
def test_every_fact_is_a_declared_artifact_entity(
    silent_supply: ContentBackedTargetSupply, entity_id: str
) -> None:
    assert entity_id in _supply_ids(silent_supply)
