"""③/④ — the read face cannot write, and unknown ids are rejected.

③ Write refusal is proven at the SQLite layer, not by convention: content.db
is opened through the §2 read-only URI (`file:…?mode=ro`), so any statement
that would mutate the artifact raises ``sqlite3.OperationalError: attempt to
write a readonly database``. The same probe is run against the connection the
store itself holds, and against a table-creating statement, because a
read-only connection must refuse DDL too.

④ Every id lookup rejects an id the registry does not declare with
NOT_FOUND (IMPLEMENTATION_PLAN §6 acceptance "unknown capability ID
rejected"); no lookup answers a silent ``None``/empty tuple for an unknown id.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.content.queries import ContentRuntimeQueries
from elc.content.store import ContentStore, ContentStoreError, open_read_only
from elc.platform.types import DomainErrorCode, Err

WRITE_STATEMENTS = (
    "INSERT INTO content_meta (key, value) VALUES ('probe', 'x')",
    "UPDATE content_entity SET language = 'xx' WHERE entity_id = 'res-hedge-i-think'",
    "DELETE FROM content_entity WHERE entity_id = 'res-hedge-i-think'",
    "CREATE TABLE probe_table (x TEXT)",
    "DROP TABLE content_entity",
)


def test_read_only_uri_refuses_every_write_statement(built_content_db: Path) -> None:
    conn = open_read_only(built_content_db)
    try:
        for statement in WRITE_STATEMENTS:
            with pytest.raises(sqlite3.OperationalError) as caught:
                conn.execute(statement)
            assert "readonly" in str(caught.value)
    finally:
        conn.close()


def test_store_connection_is_the_same_read_only_artifact(
    store: ContentStore, built_content_db: Path
) -> None:
    """The store holds a read-only connection (white-box probe)."""

    conn = store._conn  # noqa: SLF001 - the probe must use the real connection
    assert conn.execute("SELECT COUNT(*) FROM content_entity").fetchone() == (69,)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("INSERT INTO content_meta (key, value) VALUES ('probe', 'x')")
    assert built_content_db.stat().st_size > 0


def test_written_artifact_is_unchanged_by_read_attempts(built_content_db: Path) -> None:
    before = built_content_db.read_bytes()
    conn = open_read_only(built_content_db)
    try:
        for statement in WRITE_STATEMENTS:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
    finally:
        conn.close()
    assert built_content_db.read_bytes() == before


def test_missing_artifact_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ContentStoreError, match="content.db not found"):
        ContentStore(tmp_path / "absent.db")


def test_artifact_without_the_built_schema_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "content.db"
    sqlite3.connect(str(empty)).close()
    with pytest.raises(ContentStoreError, match="lacks the built schema"):
        ContentStore(empty)


def test_store_construction_takes_a_path_not_a_connection() -> None:
    """Hardening: a ContentStore opens its own read-only connection, so no
    caller can hand it a writable one."""

    import inspect

    parameters = list(inspect.signature(ContentStore.__init__).parameters)
    assert parameters == ["self", "db_path"]
    assert inspect.isfunction(ContentStore.__init__)
    assert not hasattr(ContentStore, "open")


def test_store_satisfies_the_published_read_face(store: ContentStore) -> None:
    assert isinstance(store, ContentRuntimeQueries)


UNKNOWN_ID_LOOKUPS = (
    "get_resource",
    "get_expression",
    "get_target",
    "get_teaching_content",
    "get_capability",
    "curriculum_links_of",
    "curriculum_links_to",
    "prerequisites_of",
)


@pytest.mark.parametrize("lookup", UNKNOWN_ID_LOOKUPS)
def test_unknown_id_is_rejected(store: ContentStore, lookup: str) -> None:
    result = getattr(store, lookup)("not-a-declared-id")
    assert isinstance(result, Err)
    assert result.error.code == DomainErrorCode.NOT_FOUND
    assert "not-a-declared-id" in result.error.message


def test_known_ids_are_not_rejected(store: ContentStore) -> None:
    for target_id in store.entity_ids().value:
        assert not isinstance(store.get_resource(target_id), Err)
        assert not isinstance(store.get_teaching_content(target_id), Err)
    for capability_id in store.capability_ids().value:
        assert not isinstance(store.get_capability(capability_id), Err)
        assert not isinstance(store.curriculum_links_to(capability_id), Err)
        assert not isinstance(store.prerequisites_of(capability_id), Err)
        assert not isinstance(store.curriculum_links_of(capability_id), Err)


def test_entity_without_links_answers_the_empty_tuple(store: ContentStore) -> None:
    """A declared entity with no link is not an error — that is a state."""

    links = store.curriculum_links_of("cap-interact-backchannel").value
    assert links == ()
