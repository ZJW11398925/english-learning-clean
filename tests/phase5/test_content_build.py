"""②/⑥ — rebuild idempotency, deterministic order, and the refusal paths.

Two rules from TASK-OPI-4d516e4f-….38 ②/⑥ are pinned here:

- **idempotent rebuild**: building twice from the same source yields the same
  id set and the same bytes, whether the second build writes to a fresh path
  or replaces the first artifact (temp file + os.replace);
- **no wall clock (and no other environment value) enters content**: the
  artifact carries no timestamp column and the content modules import no
  clock/randomness source, so a rebuild is a replay rather than a new fact.

The refusal half proves "源缺失/部分失败必须拒绝而非降级": a broken source
raises BuildError and writes no artifact, instead of building a smaller one.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import shutil
import sqlite3
from contextlib import redirect_stderr
from pathlib import Path

import pytest

from elc.content import build as build_module
from elc.content.build import (
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    BuildError,
    build_content_db,
    main,
)
from elc.content.store import ContentStore
from tests.conftest import SRC_ROOT

CONTENT_MODULES = (
    SRC_ROOT / "content" / "build.py",
    SRC_ROOT / "content" / "store.py",
    SRC_ROOT / "content" / "queries.py",
    SRC_ROOT / "content" / "types.py",
)
_FORBIDDEN_CLOCK_MODULES = {"time", "datetime", "random", "uuid", "secrets"}


def _source_copy(tmp_path: Path) -> tuple[Path, Path]:
    """A writable copy of both authoring trees (tests may break them)."""

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    return content_src, curriculum


def test_rebuild_same_path_is_byte_identical(tmp_path: Path) -> None:
    output = tmp_path / "content.db"
    first = build_content_db(output)
    digest_first = hashlib.sha256(output.read_bytes()).hexdigest()
    second = build_content_db(output)
    digest_second = hashlib.sha256(output.read_bytes()).hexdigest()
    assert digest_first == digest_second
    assert first.entity_count == second.entity_count == 14
    assert list(tmp_path.iterdir()) == [output]  # no leftover .tmp sibling


def test_two_builds_have_the_same_id_set_and_bytes(tmp_path: Path) -> None:
    first_path = tmp_path / "a" / "content.db"
    second_path = tmp_path / "b" / "content.db"
    build_content_db(first_path)
    build_content_db(second_path)
    first_store = ContentStore(first_path)
    second_store = ContentStore(second_path)
    try:
        assert first_store.entity_ids().value == second_store.entity_ids().value
        assert first_store.capability_ids().value == second_store.capability_ids().value
    finally:
        first_store.close()
        second_store.close()
    assert first_path.read_bytes() == second_path.read_bytes()


def test_build_report_counts(tmp_path: Path) -> None:
    """The report counts what was written: 14 entities, 5 capabilities, 9 links."""

    report = build_content_db(tmp_path / "content.db")
    assert report.entity_count == 14
    assert report.capability_count == 5
    assert report.link_count == 9
    assert report.prerequisite_count == 0
    assert report.content_version == "content-v1"
    assert report.curriculum_version == "curriculum-v1"


def test_source_index_order_does_not_change_the_artifact(tmp_path: Path) -> None:
    """Deterministic order: the index listing is not the write order."""

    content_src, curriculum = _source_copy(tmp_path)
    index_path = content_src / "index.json"
    document = json.loads(index_path.read_text(encoding="utf-8"))
    document["entities"] = list(reversed(document["entities"]))
    index_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    reference = tmp_path / "reference.db"
    shuffled = tmp_path / "shuffled.db"
    build_content_db(reference)
    build_content_db(
        shuffled, content_src_dir=content_src, curriculum_dir=curriculum
    )
    assert reference.read_bytes() == shuffled.read_bytes()


def test_rows_are_written_in_id_order(built_content_db: Path) -> None:
    """Deterministic order: file-system and index order cannot leak in.

    The read is ``ORDER BY rowid`` — insertion order — because a bare
    ``SELECT entity_id`` is answered from the PRIMARY KEY's covering index
    and comes back sorted whatever the write order was (C1 disposition F4:
    the rowid form is the one a reversed or set-ordered write cannot hide
    from). The id-order assertions keep the semantic half: insertion order
    *is* id order.

    C1: ``content_meta`` carries the three version keys **plus** the
    declared-reading TypicalError-need key for the one entity whose source
    states it (elc.content.types.typical_error_required_key) — so the meta
    table's row set is a function of the source, still sorted, still
    deterministic.
    """

    conn = sqlite3.connect(str(built_content_db))
    try:
        entities = [
            row[0]
            for row in conn.execute(
                "SELECT entity_id FROM content_entity ORDER BY rowid"
            )
        ]
        capabilities = [
            row[0]
            for row in conn.execute(
                "SELECT capability_id FROM curriculum_capability ORDER BY rowid"
            )
        ]
        meta = [
            (row[0], row[1])
            for row in conn.execute("SELECT key, value FROM content_meta ORDER BY key")
        ]
    finally:
        conn.close()
    assert entities == sorted(entities)
    assert capabilities == sorted(capabilities)
    assert meta == [
        ("content_db_version", build_module.CONTENT_DB_VERSION),
        ("content_version", "content-v1"),
        ("curriculum_version", "curriculum-v1"),
        # C1: the source's own declaration that this target needs a §24.9
        # TypicalError, carried durably and read back by the readiness face.
        (
            build_module.typical_error_required_key(
                "res-colloc-make-a-decision"
            ),
            "true",
        ),
    ]


def test_artifact_carries_no_timestamp_or_clock_column(built_content_db: Path) -> None:
    conn = sqlite3.connect(str(built_content_db))
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        columns: list[str] = []
        for table in tables:
            columns.extend(
                row[0]
                for row in conn.execute(
                    "SELECT name FROM pragma_table_info(?)", (table,)
                )
            )
    finally:
        conn.close()
    timestamp_like = [
        name
        for name in columns
        if name.endswith("_at") or name in ("timestamp", "created_time", "updated_time")
    ]
    assert not timestamp_like, timestamp_like
    assert "updated_at" not in columns


def test_content_modules_import_no_clock_or_randomness_source() -> None:
    """Positive control included: the scan reads real import lists."""

    offenders: list[str] = []
    saw_imports = 0
    for path in CONTENT_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    saw_imports += 1
                    if alias.name.split(".")[0] in _FORBIDDEN_CLOCK_MODULES:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                saw_imports += 1
                if node.module.split(".")[0] in _FORBIDDEN_CLOCK_MODULES:
                    offenders.append(f"{path.name}: from {node.module} import …")
    assert saw_imports > 10
    assert not offenders, offenders


def test_missing_source_tree_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BuildError):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=tmp_path / "absent",
            curriculum_dir=CURRICULUM_DIR,
        )
    assert not (tmp_path / "content.db").exists()


def test_listed_document_that_is_gone_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    (content_src / "entities" / "res-hedge-i-think.json").unlink()
    with pytest.raises(BuildError, match="listed document does not exist"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_unlisted_document_is_refused(tmp_path: Path) -> None:
    """A file the index does not list would be skipped silently — refuse."""

    content_src, curriculum = _source_copy(tmp_path)
    extra = content_src / "entities" / "res-not-in-index.json"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(BuildError, match="not listed"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_stray_document_in_the_tree_root_is_refused(tmp_path: Path) -> None:
    """A root-level document nobody declares is read by nobody — refuse."""

    content_src, curriculum = _source_copy(tmp_path)
    stray = curriculum / "draft-capabilities.json"
    stray.write_text("{}\n", encoding="utf-8")
    with pytest.raises(BuildError, match="not declared by the index"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_unknown_vocabulary_value_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    path = content_src / "entities" / "res-hedge-i-think.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["expression"]["fixedness"] = "HALF_FIXED"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(BuildError, match="outside the canonical set"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_dangling_link_reference_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    path = curriculum / "links.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["links"][0]["node_id"] = "cap-not-declared"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(BuildError, match="is not a declared capability"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def _load(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _store(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_index_format_version_drift_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    index_path = content_src / "index.json"
    document = _load(index_path)
    document["format_version"] = 2
    _store(index_path, document)
    with pytest.raises(BuildError, match="unexpected format_version"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_index_format_name_drift_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    index_path = curriculum / "index.json"
    document = _load(index_path)
    document["format"] = "elc.curriculum_src/v2"
    _store(index_path, document)
    with pytest.raises(BuildError, match="unexpected format"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_links_document_format_drift_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    links_path = curriculum / "links.json"
    document = _load(links_path)
    document["format"] = "elc.other_links"
    _store(links_path, document)
    with pytest.raises(BuildError, match="unexpected format"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_prerequisites_format_version_drift_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    prerequisites_path = curriculum / "prerequisites.json"
    document = _load(prerequisites_path)
    document["format_version"] = "1"
    _store(prerequisites_path, document)
    with pytest.raises(BuildError, match="unexpected format_version"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_entity_language_drift_from_the_index_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    entity_path = content_src / "entities" / "res-hedge-i-think.json"
    document = _load(entity_path)
    entity = document["entity"]
    assert isinstance(entity, dict)
    entity["language"] = "de"
    _store(entity_path, document)
    with pytest.raises(BuildError, match="the index declares"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_capability_language_is_not_a_second_declaration(
    built_content_db: Path,
) -> None:
    """language lives on the entity (§24.1) and is validated against the index;
    the registry node carries no language of its own."""

    conn = sqlite3.connect(str(built_content_db))
    try:
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM pragma_table_info('curriculum_capability')"
            )
        }
    finally:
        conn.close()
    assert "language" not in columns


def test_reveal_form_outside_canonical_forms_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    path = content_src / "entities" / "res-hedge-i-think.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["teaching_content"]["reveal_form"] = "I reckon it will rain."
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(BuildError, match="not one of the"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )
    assert not (tmp_path / "content.db").exists()


def test_second_index_capability_document_drift_is_refused(tmp_path: Path) -> None:
    content_src, curriculum = _source_copy(tmp_path)
    path = curriculum / "capabilities" / "cap-ref-ask-clarification.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["curriculum_node_id"] = "node-elsewhere"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(BuildError, match="one capability = one node"):
        build_content_db(
            tmp_path / "content.db",
            content_src_dir=content_src,
            curriculum_dir=curriculum,
        )


def test_cli_builds_and_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "content.db"
    exit_code = main(["--out", str(output)])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "entities=14" in captured
    assert "capabilities=5" in captured
    assert "links=9" in captured
    assert output.is_file()


def test_cli_refuses_a_broken_source_and_exits_two(tmp_path: Path) -> None:
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        exit_code = main(
            [
                "--out",
                str(tmp_path / "content.db"),
                "--content-src",
                str(tmp_path / "absent"),
            ]
        )
    assert exit_code == 2
    assert "content.db build refused" in stderr.getvalue()
    assert not (tmp_path / "content.db").exists()
