"""③ — the curriculum read face: one signature per name, one origin per row.

P5-0 review F-6 left one thing open: the same method name existed twice with
two different signatures (`prerequisites_of` taking ``str`` on the content face
and ``CurriculumNodeId`` on the curriculum face; `curriculum_version` nullable
on one side and total on the other) and nothing said which one a Planner gets.
P5-1 answers it here: the curriculum package's read face is the one callers
use, its ids are curriculum ids, its version is the domain's nullable result,
and the artifact reader's ``str`` spelling stops at the adapter.

The other half of the file is IMPLEMENTATION_PLAN §6's two acceptance facts —
"candidate content excluded" and "canonical/personal origin preserved" — read
off the built artifact, plus the two statements whose absence would leave the
migration口径 implicit: content.db 是 §24 双树共用 artifact 读面，curriculum
侧权威未迁移.
"""

from __future__ import annotations

import inspect
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

import pytest

import elc.content.store as content_store_module
import elc.curriculum.store as curriculum_store_module
from elc.content.build import CONTENT_SRC_DIR
from elc.content.store import ContentStore
from elc.content.types import (
    CONTENT_ORIGINS,
    PERSONAL_CONTENT_WIRED,
    ContentOrigin,
    ExampleLinkRole,
    supply_eligible,
)
from elc.curriculum.queries import CurriculumSupplyQueries
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import (
    CurriculumNodeId,
    CurriculumVersion,
    DomainErrorCode,
    Err,
    Ok,
)
from tests.phase5.conftest import DOCS_ROOT, canonical_blocks

FOCUS = "res-hedge-i-think"

METHOD_NAMES = tuple(
    name
    for name, member in vars(CurriculumSupplyQueries).items()
    if not name.startswith("_") and inspect.isfunction(member)
)


def _result_value_annotation(annotation: Any) -> Any:
    """The ``T`` of an ``Ok[T]`` inside a ``Result[T]``/``Ok[T] | Err[Any]``
    annotation (the error channel is deliberately untyped)."""

    for arg in get_args(annotation):
        if get_origin(arg) is Ok:
            return get_args(arg)[0]
    raise AssertionError(f"not a Result annotation: {annotation!r}")


def _declared_signature(owner: Any, name: str) -> tuple[tuple[str, Any], ...]:
    hints = get_type_hints(getattr(owner, name))
    signature = inspect.signature(getattr(owner, name))
    entries: list[tuple[str, Any]] = []
    for parameter in signature.parameters.values():
        if parameter.name in ("self", "cls"):
            continue
        entries.append((parameter.name, hints.get(parameter.name)))
    entries.append(("return", hints.get("return")))
    return tuple(entries)


def test_the_protocol_declares_the_read_face_this_slice_ships() -> None:
    assert set(METHOD_NAMES) >= {
        "content_version",
        "curriculum_version",
        "prerequisites_of",
        "curriculum_links_of",
        "curriculum_links_to",
        "content_origin",
        "is_supply_eligible",
        "supply_entity_ids",
        "readiness_facts",
        "readiness",
    }


@pytest.mark.parametrize("name", METHOD_NAMES)
def test_adapter_signature_equals_the_protocol_signature(name: str) -> None:
    """F-6, closed: one name ⇒ one signature on the curriculum face."""

    assert _declared_signature(CurriculumSupplyQueries, name) == (
        _declared_signature(CurriculumContentStore, name)
    )


def test_get_examples_is_the_one_declared_off_port_name() -> None:
    """F-5: the pin covers the twelve protocol names; ``get_examples`` is the
    one same-named method outside it, and its deliberate width difference is
    declared in the protocol docstring *and* asserted here."""

    assert not hasattr(CurriculumSupplyQueries, "get_examples")
    adapter = get_type_hints(CurriculumContentStore.get_examples)
    reader = get_type_hints(content_store_module.ContentStore.get_examples)
    print(
        f"[F-5] adapter role -> {adapter['role']}; reader role -> {reader['role']}"
    )
    assert adapter["role"] is ExampleLinkRole
    assert reader["role"] != adapter["role"]
    assert ExampleLinkRole in (reader["role"], *get_args(reader["role"]))


def test_prerequisites_of_speaks_curriculum_node_ids() -> None:
    """The unification in the open: the artifact reader spells ids as ``str``,
    the curriculum face takes the domain's own id type, and the conversion is
    behaviorally equivalent for the same node."""

    adapter_hints = get_type_hints(CurriculumContentStore.prerequisites_of)
    store_hints = get_type_hints(content_store_module.ContentStore.prerequisites_of)
    assert adapter_hints["node_id"] is CurriculumNodeId
    assert store_hints["node_id"] is str
    assert adapter_hints["node_id"] is not store_hints["node_id"]


def test_prerequisites_of_reads_the_same_rows_through_both_faces(
    built_content_db: Path,
) -> None:
    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        node = CurriculumNodeId("cap-ref-ask-clarification")
        through_adapter = supply.prerequisites_of(node)
        through_reader = store.prerequisites_of(str(node))
        assert isinstance(through_adapter, Ok), through_adapter
        assert isinstance(through_reader, Ok), through_reader
        assert through_adapter.value == through_reader.value
        # The corpus declares no prerequisite edges (curriculum/README.md C3);
        # the empty tuple is a declared state, not an error.
        assert through_adapter.value == ()
        unknown = supply.prerequisites_of(CurriculumNodeId("cap-nope"))
        assert isinstance(unknown, Err)
    finally:
        store.close()


def test_curriculum_version_is_nullable_on_the_curriculum_face(
    built_content_db: Path,
) -> None:
    """The domain's nullable result, and what it actually answers."""

    hints = get_type_hints(CurriculumContentStore.curriculum_version)
    value_type = _result_value_annotation(hints["return"])
    assert get_origin(value_type) is Union
    assert type(None) in get_args(value_type)
    assert CurriculumVersion in get_args(value_type)

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        version = supply.curriculum_version()
        content_version = supply.content_version()
    finally:
        store.close()
    assert isinstance(version, Ok), version
    assert isinstance(content_version, Ok), content_version
    # "No curriculum source declared" is a legal state (the authority is not
    # migrated) — it is simply not this artifact's state.
    assert version.value == CurriculumVersion("curriculum-v1")
    assert content_version.value == "content-v1"


def test_the_shared_artifact_statement_is_in_both_docstrings() -> None:
    """content.db 是 §24 双树共用 artifact 读面、curriculum 侧权威未迁移 —
    written where a caller reads it, not only in a report."""

    statement = "content.db 是 §24 双树共用 artifact 读面；curriculum 侧权威未迁移"
    assert statement in curriculum_store_module.__doc__
    assert "there is no curriculum.db" in content_store_module.__doc__


def test_the_read_face_pins_the_dual_tree_artifact_to_the_canonical_docs() -> None:
    """The claim above is checkable: §24 names both authoring trees and §2
    names the one read-only artifact."""

    blocks = canonical_blocks(
        "DATA_MODEL.md", "### 24.7 Pedagogy / Labels / Curriculum Mapping"
    )
    assert any(
        "resource_id" in block and "primary_flag" in block for block in blocks
    ), "§24.7 CurriculumLink columns not found"
    data_model = (DOCS_ROOT / "DATA_MODEL.md").read_text(encoding="utf-8")
    assert "read-only, versioned canonical content runtime build" in data_model
    assert "Content authoring source of truth" in data_model
    assert "content_src/*" in data_model and "curriculum/*" in data_model


# ---------------------------------------------------------------------------
# origin separation (§6 "canonical/personal origin preserved")
# ---------------------------------------------------------------------------


def test_the_origin_vocabulary_is_exactly_two_members() -> None:
    assert CONTENT_ORIGINS == ("CANONICAL", "PERSONAL")
    assert {str(origin) for origin in ContentOrigin} == set(CONTENT_ORIGINS)


def test_every_artifact_row_is_canonical_origin(built_content_db: Path) -> None:
    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        origins = {
            supply.content_origin(entity_id).value
            for entity_id in store.entity_ids().value
        }
    finally:
        store.close()
    assert origins == {ContentOrigin.CANONICAL}


def test_no_personal_row_is_produced(built_content_db: Path) -> None:
    """Interface only: the personal source is not wired, and every artifact id
    is declared by the canonical authoring index (so no row could have come
    from anywhere else)."""

    index = json.loads((CONTENT_SRC_DIR / "index.json").read_text(encoding="utf-8"))
    declared = {
        str(entry).rsplit("/", 1)[-1].removesuffix(".json")
        for entry in index["entities"]
    }
    store = ContentStore(built_content_db)
    try:
        artifact_ids = set(store.entity_ids().value)
    finally:
        store.close()
    assert PERSONAL_CONTENT_WIRED is False
    assert artifact_ids <= declared
    # The personal origin stays declared-but-unproduced: the vocabulary member
    # exists, the interface is what a future source would implement, and no
    # row of this artifact carries it.
    assert ContentOrigin.PERSONAL in ContentOrigin


def test_origin_and_lifecycle_are_orthogonal(tmp_path: Path) -> None:
    """An excluded entity keeps its (canonical) origin: the two §6 acceptance
    facts are separate gates, not one."""

    from tests.phase5.conftest import artifact_with_lifecycle

    artifact = artifact_with_lifecycle(
        tmp_path,
        {
            "res-candidate-not-approved": "REVIEW_REQUIRED",
            "res-retired-x": "REPLACED",
        },
    )
    store = ContentStore(artifact)
    try:
        supply = CurriculumContentStore(store)
        assert supply.is_supply_eligible("res-candidate-not-approved").value is False
        assert (
            supply.content_origin("res-candidate-not-approved").value
            is ContentOrigin.CANONICAL
        )
        assert supply_eligible("CANONICAL_APPROVED") is True
        assert supply_eligible("REPLACED") is False
    finally:
        store.close()


def test_the_canonical_corpus_is_fully_eligible(built_content_db: Path) -> None:
    """The other side of candidate exclusion: on the canonical corpus every
    declared entity is CANONICAL_APPROVED, so the supply set is the full 51
    (a filter that excluded more would be a silent content loss)."""

    store = ContentStore(built_content_db)
    try:
        supply = CurriculumContentStore(store)
        eligible = supply.supply_entity_ids()
        ids = store.entity_ids().value
    finally:
        store.close()
    assert isinstance(eligible, Ok), eligible
    assert tuple(str(entity_id) for entity_id in eligible.value) == ids
    assert len(ids) == 51


def test_a_read_failure_is_an_err_never_a_raise(
    built_content_db: Path, tmp_path: Path
) -> None:
    """The adapter answers ``Err(DEPENDENCY_UNAVAILABLE)`` when the artifact
    stops being readable under it — the teaching port's DEGRADED path depends
    on this being an ``Err``, not an exception."""

    broken = tmp_path / "broken.db"
    shutil.copyfile(built_content_db, broken)
    store = ContentStore(broken)
    supply = CurriculumContentStore(store)
    try:
        assert isinstance(supply.get_resource(FOCUS), Ok)
        writable = sqlite3.connect(str(broken))
        writable.execute("DROP TABLE content_target")
        writable.commit()
        writable.close()
        result = supply.get_target(FOCUS)
    finally:
        store.close()
    print(f"[read face] read after the artifact lost a table -> {result}")
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
