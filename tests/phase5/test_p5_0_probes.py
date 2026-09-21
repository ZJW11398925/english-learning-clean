"""The four P5-0 probes, printed verbatim for the delivery report.

These tests are ordinary assertions; each one also prints the raw reading it
asserts on, so `pytest tests/phase5/test_p5_0_probes.py -s` reproduces the
report's ④ evidence instead of quoting it second-hand:

1. a write against the read-only artifact is refused by SQLite;
2. two builds from one source yield the same id set and the same bytes;
3. an unknown entity / capability id is rejected (NOT_FOUND);
4. the content view's column set equals the §24.1 code block, line by line.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
from pathlib import Path

import pytest

from elc.content.build import build_content_db
from elc.content.queries import ContentResourceView
from elc.content.store import ContentStore, open_read_only
from elc.platform.types import Err
from tests.phase5.conftest import canonical_lines


def test_probe_1_write_refused(built_content_db: Path) -> None:
    conn = open_read_only(built_content_db)
    try:
        with pytest.raises(sqlite3.OperationalError) as caught:
            conn.execute(
                "INSERT INTO content_meta (key, value) VALUES ('probe', 'x')"
            )
    finally:
        conn.close()
    print(f"[probe 1] INSERT via file:...?mode=ro -> {caught.value!r}")
    assert "readonly" in str(caught.value)


def test_probe_2_rebuild_same_ids_and_bytes(tmp_path: Path) -> None:
    first = tmp_path / "a" / "content.db"
    second = tmp_path / "b" / "content.db"
    report = build_content_db(first)
    build_content_db(second)
    first_digest = hashlib.sha256(first.read_bytes()).hexdigest()
    second_digest = hashlib.sha256(second.read_bytes()).hexdigest()
    store = ContentStore(first)
    try:
        ids = store.entity_ids().value
        capabilities = store.capability_ids().value
    finally:
        store.close()
    print(f"[probe 2] build report -> {report}")
    print(f"[probe 2] entity_ids ({len(ids)}) -> {ids}")
    print(f"[probe 2] capability_ids ({len(capabilities)}) -> {capabilities}")
    print(f"[probe 2] sha256 a -> {first_digest}")
    print(f"[probe 2] sha256 b -> {second_digest}")
    assert first_digest == second_digest
    assert first.read_bytes() == second.read_bytes()


def test_probe_3_unknown_ids_rejected(store: ContentStore) -> None:
    readings = {
        "get_resource('res-nope')": store.get_resource("res-nope"),
        "get_capability('cap-nope')": store.get_capability("cap-nope"),
        "curriculum_links_to('cap-nope')": store.curriculum_links_to("cap-nope"),
        "prerequisites_of('cap-nope')": store.prerequisites_of("cap-nope"),
    }
    for label, result in readings.items():
        print(f"[probe 3] {label} -> {result}")
        assert isinstance(result, Err)
    assert len(readings) == 4


def test_probe_4_column_set_equals_the_canonical_block() -> None:
    canonical = canonical_lines("DATA_MODEL.md", "### 24.1 ContentEntity", 0)
    code = tuple(field.name for field in dataclasses.fields(ContentResourceView))
    print(f"[probe 4] docs/DATA_MODEL.md §24.1 columns -> {canonical}")
    print(f"[probe 4] ContentResourceView fields      -> {code}")
    assert code == canonical
