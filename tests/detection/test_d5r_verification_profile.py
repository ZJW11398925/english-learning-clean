"""D-5R — the artifact's verifier identity: ``content_verification_profile``.

Pinned here, in the artifact's own bytes and through the store's read face:

1. a pilot build (non-empty registry) writes **exactly one** profile row;
   a default build (``detector_registry=None``) and an explicitly empty
   registry write none — the legitimate empty baseline;
2. the row is deterministic: same world (source + registry + pilot
   version) ⇒ byte-identical profile — the id is a digest of the other
   three columns, and there is no timestamp;
3. ``detector_set_digest`` is sensitive to the registry's entry set (an
   added or re-ordinaled entry moves it, and the profile id with it);
4. ``fixture_set_digest`` binds the awarded levels to the fixture bytes
   they were earned on (an edited fixture text of a verified entity moves
   it, under a registry that still verifies the entity);
5. the store's ``verification_profile()`` reads the row verbatim, answers
   ``None`` for the baseline, and the table is a required one (the store
   refuses an artifact that lacks it);
6. the CLI's assembly shape — ``build_content_db(...,
   verification_pilot_version=pilot.PILOT_VERSION)`` — is what stamps the
   artifact with the pilot set's version (PILOT_VERSION itself is the
   matcher implementation set's semantic version, bump-on-behaviour).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.content.build import (
    CONTENT_DB_VERSION,
    SCHEMA_STATEMENTS,
    build_content_db,
)
from elc.content.store import ContentStore
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_ENTITIES, PILOT_VERSION, register_pilot
from elc.platform.types import Ok
from tests.detection.support import (
    ANYWAY_ENTITY,
    anyway_stub,
    copy_source_trees,
)

PILOT_REGISTRY_VERSION_KWARGS = {
    "verification_pilot_version": PILOT_VERSION,
}


def _pilot_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    register_pilot(registry)
    return registry


def _profile_rows(artifact: Path) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(str(artifact))
    try:
        return [
            tuple(row)
            for row in conn.execute(
                "SELECT profile_id, detector_set_digest, "
                "fixture_set_digest, pilot_version "
                "FROM content_verification_profile"
            )
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. the two states: one row for a registry, none for the baseline
# ---------------------------------------------------------------------------


def test_a_pilot_build_writes_exactly_one_profile_row(tmp_path: Path) -> None:
    path = tmp_path / "pilot.db"
    build_content_db(
        path,
        detector_registry=_pilot_registry(),
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    rows = _profile_rows(path)
    assert len(rows) == 1
    profile_id, detector_digest, fixture_digest, version = rows[0]
    assert profile_id and detector_digest and fixture_digest and version
    assert version == PILOT_VERSION
    for digest in (detector_digest, fixture_digest):
        assert len(str(digest)) == 64  # sha256 hex, not a truncation


def test_a_default_build_writes_no_profile_row(tmp_path: Path) -> None:
    default = tmp_path / "default.db"
    empty = tmp_path / "empty-registry.db"
    build_content_db(default)
    build_content_db(empty, detector_registry=DetectorRegistry())
    assert _profile_rows(default) == []
    assert _profile_rows(empty) == []
    # and the two baselines stay byte-identical to each other (the D-2
    # reading, still true: no registry is no registry, whichever way the
    # caller spells it)
    assert default.read_bytes() == empty.read_bytes()


def test_the_table_is_the_schemas_last_statement() -> None:
    """The schema's 26th statement is the profile table (the D-5R table)."""

    names = [
        statement.split("(", 1)[0].split()[-1]
        for statement in SCHEMA_STATEMENTS
    ]
    assert len(names) == 26
    assert names[-1] == "content_verification_profile"
    assert CONTENT_DB_VERSION == "6"


# ---------------------------------------------------------------------------
# 2. determinism: one world, one byte-identical profile
# ---------------------------------------------------------------------------


def test_the_profile_is_deterministic_across_builds(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    for path in (first, second):
        build_content_db(
            path,
            detector_registry=_pilot_registry(),
            **PILOT_REGISTRY_VERSION_KWARGS,
        )
    assert _profile_rows(first) == _profile_rows(second)
    # the whole artifact follows: no timestamp anywhere
    assert first.read_bytes() == second.read_bytes()


def test_the_profile_id_digests_the_other_three_columns(
    tmp_path: Path,
) -> None:
    """``profile_id`` is the sha256 of detector digest ⊕ fixture digest ⊕
    pilot version, truncated to 16 hex — reproducible from the row itself,
    so the id adds no information it could lie about."""

    import hashlib

    path = tmp_path / "pilot.db"
    build_content_db(
        path,
        detector_registry=_pilot_registry(),
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    profile_id, detector_digest, fixture_digest, version = _profile_rows(
        path
    )[0]
    expected = hashlib.sha256(
        "\x1f".join(
            (str(detector_digest), str(fixture_digest), str(version))
        ).encode("utf-8")
    ).hexdigest()[:16]
    assert profile_id == expected


# ---------------------------------------------------------------------------
# 3. detector_set_digest is sensitive to the registry's entry set
# ---------------------------------------------------------------------------


def test_an_extra_registry_entry_moves_the_detector_digest(
    tmp_path: Path,
) -> None:
    content_src, curriculum = copy_source_trees(tmp_path)
    base = tmp_path / "base.db"
    wider = tmp_path / "wider.db"
    base_registry = DetectorRegistry()
    base_registry.register(ANYWAY_ENTITY, (0,), anyway_stub)
    build_content_db(
        base,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=base_registry,
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    wider_registry = DetectorRegistry()
    wider_registry.register(ANYWAY_ENTITY, (0,), anyway_stub)
    wider_registry.register("res-hedge-i-guess", (0,), anyway_stub)
    build_content_db(
        wider,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=wider_registry,
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    base_row = _profile_rows(base)[0]
    wider_row = _profile_rows(wider)[0]
    assert base_row[1] != wider_row[1]  # detector_set_digest moved
    assert base_row[0] != wider_row[0]  # and the profile id with it


def test_a_re_spelled_rule_ordinal_moves_the_detector_digest(
    tmp_path: Path,
) -> None:
    content_src, curriculum = copy_source_trees(tmp_path)
    base = tmp_path / "base.db"
    shifted = tmp_path / "shifted.db"
    first = DetectorRegistry()
    first.register(ANYWAY_ENTITY, (0,), anyway_stub)
    build_content_db(
        base,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=first,
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    second = DetectorRegistry()
    second.register(ANYWAY_ENTITY, (0, 1), anyway_stub)
    build_content_db(
        shifted,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=second,
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    assert _profile_rows(base)[0][1] != _profile_rows(shifted)[0][1]


# ---------------------------------------------------------------------------
# 4. fixture_set_digest binds the levels to the fixture bytes
# ---------------------------------------------------------------------------


def test_an_edited_fixture_text_of_a_verified_entity_moves_the_fixture_digest(
    tmp_path: Path,
) -> None:
    """The same registry over a tree whose verified entity's POSITIVE
    fixture text changed (the stub still passes it) — the fixture digest
    moves, so an awarded level can never silently outlive the sentences it
    was earned on."""

    content_src, curriculum = copy_source_trees(tmp_path)
    pristine = tmp_path / "pristine.db"
    edited = tmp_path / "edited.db"

    registry = DetectorRegistry()
    registry.register(ANYWAY_ENTITY, (0,), anyway_stub)
    build_content_db(
        pristine,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=registry,
        **PILOT_REGISTRY_VERSION_KWARGS,
    )

    evidence_path = (
        content_src / "evidence" / f"{ANYWAY_ENTITY}.json"
    )
    document = json.loads(evidence_path.read_text(encoding="utf-8"))
    positives = [
        row
        for row in document["detection_fixtures"]
        if row["kind"] == "POSITIVE_ERROR"
    ]
    assert positives
    positives[0]["text"] = (
        "Let me say this plainly. " + positives[0]["text"]
    )
    evidence_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    build_content_db(
        edited,
        content_src_dir=content_src,
        curriculum_dir=curriculum,
        detector_registry=registry,
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    pristine_row = _profile_rows(pristine)[0]
    edited_row = _profile_rows(edited)[0]
    assert pristine_row[2] != edited_row[2]  # fixture_set_digest moved
    assert pristine_row[1] == edited_row[1]  # detector set did not
    # and the entity is still verified under the stub, so the digest moved
    # because the evidence moved, not because the verification shrank
    promoted = ContentStore(edited)
    try:
        levels = promoted.provenance_levels()
        assert isinstance(levels, Ok), levels
    finally:
        promoted.close()
    assert dict(levels.value)[ANYWAY_ENTITY] == "EXECUTABLY_VERIFIED"


# ---------------------------------------------------------------------------
# 5. the store read face
# ---------------------------------------------------------------------------


def test_the_store_reads_the_profile_row(tmp_path: Path) -> None:
    path = tmp_path / "pilot.db"
    build_content_db(
        path,
        detector_registry=_pilot_registry(),
        **PILOT_REGISTRY_VERSION_KWARGS,
    )
    store = ContentStore(path)
    try:
        profile = store.verification_profile()
        assert isinstance(profile, Ok), profile
        row = _profile_rows(path)[0]
        assert profile is not None
        assert profile.value is not None
        assert (
            profile.value.profile_id,
            profile.value.detector_set_digest,
            profile.value.fixture_set_digest,
            profile.value.pilot_version,
        ) == row
    finally:
        store.close()


def test_the_store_answers_none_for_the_empty_baseline(tmp_path: Path) -> None:
    path = tmp_path / "default.db"
    build_content_db(path)
    store = ContentStore(path)
    try:
        profile = store.verification_profile()
        assert isinstance(profile, Ok), profile
        assert profile.value is None
    finally:
        store.close()


def test_the_store_refuses_an_artifact_without_the_profile_table(
    tmp_path: Path,
) -> None:
    from elc.content.store import ContentStoreError

    path = tmp_path / "stripped.db"
    build_content_db(path)
    conn = sqlite3.connect(str(path))
    conn.execute("DROP TABLE content_verification_profile")
    conn.commit()
    conn.close()
    with pytest.raises(ContentStoreError) as raised:
        ContentStore(path)
    assert "content_verification_profile" in str(raised.value)


# ---------------------------------------------------------------------------
# 6. the pilot version is the matcher set's semantic version
# ---------------------------------------------------------------------------


def test_the_pilot_version_is_a_bump_on_behaviour_constant() -> None:
    """The identity the CLI stamps must name a set, not a snapshot: a
    non-empty word, distinct from every entity id (a version is not a
    roster), and the roster it names is the D-3 twelve — the same set the
    CLI assembles. The bump-on-behaviour rule lives on the constant's own
    declaration; this pin makes a silent deletion visible."""

    assert PILOT_VERSION == "d3-pilot-1"
    assert PILOT_VERSION not in PILOT_ENTITIES
