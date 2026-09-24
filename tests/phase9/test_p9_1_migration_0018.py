"""P9-1 ① — migration 0018: the five §21.1 / §22 delivery tables.

What is pinned here is what the migration claims:

- the five tables are the canonical fenced blocks, **column for column and in
  order** — read off ``docs/DATA_MODEL.md`` §22 (three blocks) and §21.1 (two)
  by this file's own reader, compared against ``PRAGMA table_info``;
- the two inline vocabularies of §21.1 are the CHECKs, word for word, and
  §22's five vocabulary columns carry **no** schema CHECK (the words are
  STATE_MACHINES §13's, validated in Python by the port);
- five ``action_id`` foreign keys point at ``generation_action_intent`` and
  ``assistant_turn_id`` carries none (0003's own reading);
- the stamps move to ``18``, applying the chain is idempotent, and 0017 is
  immediately behind 0018 in filename order;
- ``0001–0017`` are byte-identical (per-file SHA-256, CRLF-normalized). 0017's
  digest is recorded by **this** cut (``PRE_0018_DIGESTS``) and the earlier
  cuts' records are merged in, the same way the 0017 suite merged them;
- the header states the readings the port and the deletion surfaces depend
  on (the key shapes, the FK/no-FK arguments, the empty-prefix reading, the
  §22 no-CHECK reading with its Revisit, and the registry drift note).
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import sqlite3
from pathlib import Path

from elc.persona.types import ValidatorResult
from elc.platform.db import migrations
from elc.runtime import delivery_records as port
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.phase8.conftest import (
    canonical_blocks_verbatim,
    columns_and_vocabulary,
)

MIGRATIONS_DIR = REPO_ROOT / "migrations"
HEAD_0018 = "0018_delivery_records.sql"
PRE_0018 = "0017_ledger_event_provenance.sql"

SECTION_21_1 = "## 21.1 Validator / PreDelivery Guard Records"
SECTION_22 = "## 22. Delivery Data"

TABLES = (
    "server_delivery_record",
    "client_render_ack",
    "exposure_estimate",
    "validator_result",
    "pre_delivery_guard_result",
)

#: The row shape of each table, for the field-name half of the column-map
#: check (``validator_result`` reuses the shipped §21.1 type — port judgement
#: 9 — rather than minting a second one).
SHAPES: dict[str, type] = {
    "server_delivery_record": port.ServerDeliveryRecord,
    "client_render_ack": port.ClientRenderAck,
    "exposure_estimate": port.ExposureEstimate,
    "validator_result": ValidatorResult,
    "pre_delivery_guard_result": port.PreDeliveryGuardResult,
}

#: 0017's blob, **recorded by this cut** and unchanged by it. The whole
#: ``0001–0017`` lineage is then pinned from the original records (0001–0012 in
#: tests/phase6, 0013–0014 in tests/phase8's P8-0 suite, 0015 in the P8-3
#: suite, 0016 in the P8-4 suite) plus this one value.
PRE_0018_DIGESTS = {
    "0017_ledger_event_provenance.sql": (
        "a569609765b73ade787693f970c8501f356dd1648e00b254cc6b02e79eff5805"
    ),
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _statements() -> list[str]:
    """The file's non-comment statements, each with its ``;``."""

    text = (MIGRATIONS_DIR / HEAD_0018).read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )
    return [part.strip() + ";" for part in body.split(";") if part.strip()]


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")]


def _notnull(db: sqlite3.Connection, table: str) -> dict[str, int]:
    return {
        str(row[1]): int(row[3])
        for row in db.execute(f"PRAGMA table_info({table})")
    }


def _foreign_keys(db: sqlite3.Connection, table: str) -> list[tuple[str, str, str]]:
    return [
        (str(row[2]), str(row[3]), str(row[4]))
        for row in db.execute(f"PRAGMA foreign_key_list({table})")
    ]


def _ddl(db: sqlite3.Connection, table: str) -> str:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    assert row is not None, table
    return " ".join(str(row[0]).split())


def _canonical_blocks() -> dict[str, tuple[str, ...]]:
    """The five blocks, in canonical order, keyed by their table."""

    validator, guard = canonical_blocks_verbatim("DATA_MODEL.md", SECTION_21_1)
    delivery, ack, estimate = canonical_blocks_verbatim(
        "DATA_MODEL.md", SECTION_22
    )
    return {
        "server_delivery_record": delivery,
        "client_render_ack": ack,
        "exposure_estimate": estimate,
        "validator_result": validator,
        "pre_delivery_guard_result": guard,
    }


def _canonical_spellings() -> dict[str, tuple[str, ...]]:
    """The block words as the map's canonical side spells them: ``?`` dropped
    (it marks an optional column), list brackets kept."""

    blocks = _canonical_blocks()
    spellings: dict[str, tuple[str, ...]] = {}
    for table, block in blocks.items():
        flat, _vocabulary = columns_and_vocabulary(block)
        spellings[table] = tuple(column.rstrip("?") for column in flat)
    return spellings


def _canonical_columns() -> dict[str, tuple[str, ...]]:
    """The same words as the durable columns: ``[]`` dropped too."""

    return {
        table: tuple(column.removesuffix("[]") for column in columns)
        for table, columns in _canonical_spellings().items()
    }


def _canonical_vocabulary() -> dict[str, tuple[str, ...]]:
    blocks = _canonical_blocks()
    vocabulary: dict[str, tuple[str, ...]] = {}
    for table, block in blocks.items():
        _flat, words = columns_and_vocabulary(block)
        vocabulary[table] = words
    return vocabulary


# -- ① the lineage -----------------------------------------------------------


def test_0018_is_0017s_successor_and_the_head() -> None:
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert MIGRATION_IDS[-1] == "0018_delivery_records"
    assert names[-1] == SCHEMA_HEAD_FILE == HEAD_0018
    assert names[names.index(PRE_0018) + 1] == HEAD_0018
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]


def test_the_pre_0018_lineage_did_not_move() -> None:
    """0001–0017 are byte-identical at the blob level (CRLF-normalized)."""

    from tests.phase6.test_p6_3_migration_0013 import PRE_0013_DIGESTS
    from tests.phase8.test_p8_0_migration_0015 import PRE_0015_DIGESTS
    from tests.phase8.test_p8_3_migration_0016 import PRE_0016_DIGESTS
    from tests.phase8.test_p8_4_migration_0017 import PRE_0017_DIGESTS

    recorded = {**PRE_0013_DIGESTS, **PRE_0015_DIGESTS, **PRE_0016_DIGESTS}
    recorded.update(PRE_0017_DIGESTS)
    recorded.update(PRE_0018_DIGESTS)
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[: len(recorded)] == list(recorded)
    for name, digest in recorded.items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name


def test_applying_the_chain_is_idempotent(db: sqlite3.Connection) -> None:
    assert migrations.apply_migrations(db) == []
    assert "0018_delivery_records" in migrations.applied_migrations(db)


def test_the_stamps_move_to_the_shared_head(db: sqlite3.Connection) -> None:
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION == "18"
    stamps = dict(
        db.execute(
            "SELECT key, value FROM schema_meta WHERE key IN"
            " ('schema_version', 'runtime_schema_version')"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": SCHEMA_HEAD_VERSION,
        "runtime_schema_version": SCHEMA_HEAD_VERSION,
    }


# -- ② the file is five tables and two stamps --------------------------------


def test_the_file_is_five_create_tables_and_two_stamps() -> None:
    statements = _statements()
    assert len(statements) == 7
    creates = [s for s in statements if s.upper().startswith("CREATE TABLE")]
    stamps = [s for s in statements if s.startswith("INSERT INTO schema_meta")]
    assert len(creates) == 5
    assert len(stamps) == 2
    for statement in statements:
        upper = statement.upper()
        assert not upper.startswith("DROP"), statement
        assert not upper.startswith("DELETE"), statement
        assert not upper.startswith("UPDATE"), statement
        assert "INSERT INTO " not in statement or "schema_meta" in statement
    for table in TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table} (" in "\n".join(
            creates
        ), table


def test_the_migration_file_uses_lf_line_endings() -> None:
    raw = (MIGRATIONS_DIR / HEAD_0018).read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")


# -- ③ the blocks are the tables ---------------------------------------------


def test_the_five_tables_are_the_canonical_blocks_column_for_column(
    db: sqlite3.Connection,
) -> None:
    blocks = _canonical_columns()
    assert set(blocks) == set(TABLES)
    for table, columns in blocks.items():
        assert _columns(db, table) == list(columns), table


def test_the_column_map_agrees_with_the_blocks_and_the_row_shapes() -> None:
    """The port's single map, the canonical blocks and each record's fields
    are one declaration: same order, canonical spelling verbatim (brackets
    included), and a field name on the other side."""

    columns = _canonical_spellings()
    for table, canonical in columns.items():
        pairs = port.COLUMN_MAP[table]
        assert tuple(pair[0] for pair in pairs) == canonical, table
        assert tuple(pair[1] for pair in pairs) == tuple(
            field.name for field in dataclasses.fields(SHAPES[table])
        ), table
        # the bracketed spelling survives only in the map's canonical side
        assert tuple(pair[0].removesuffix("[]") for pair in pairs) == tuple(
            column.removesuffix("[]") for column in canonical
        ), table


def test_the_section22_vocabulary_is_state_machines_not_the_schema(
    db: sqlite3.Connection,
) -> None:
    """§22's five word columns carry no CHECK — and the other two §22 tables
    are not silently carrying one either.

    The positive half (the words exist, in the enums) is asserted beside the
    negative half so a migration that dropped the columns would fail here too.
    """

    word_columns = {
        "server_delivery_record": ("state",),
        "exposure_estimate": (
            "certainty",
            "exposure_level",
            "max_possible_exposure",
            "confirmed_exposure",
        ),
    }
    for table, columns in word_columns.items():
        ddl = _ddl(db, table)
        for column in columns:
            match = re.search(rf"\b{column}\s+[^,)]*", ddl)
            assert match is not None, (table, column)
            assert "CHECK" not in match.group(0), (table, column)
            assert "TEXT NOT NULL" in match.group(0), (table, column)
    assert "CHECK" not in _ddl(db, "exposure_estimate")
    assert "CHECK" not in _ddl(db, "server_delivery_record")
    # ... and the vocabularies the port validates against are §13's words:
    assert port.DELIVERY_STATE_WORDS == (
        "NOT_SENT",
        "SENDING",
        "SENT_PARTIAL",
        "SENT_COMPLETE",
        "FAILED",
        "CANCELLED",
    )
    assert port.EXPOSURE_CERTAINTY_WORDS == (
        "CONFIRMED_RENDERED",
        "SERVER_SENT_UNCONFIRMED",
        "UNKNOWN",
    )
    assert port.EXPOSURE_LEVEL_WORDS == ("NONE", "PARTIAL", "FULL")
    assert port.EXPOSURE_WORD_COLUMNS == (
        "exposure_level",
        "max_possible_exposure",
        "confirmed_exposure",
    )


def test_the_validator_check_is_the_four_inline_words(db: sqlite3.Connection) -> None:
    words = _canonical_vocabulary()["validator_result"]
    assert words == ("ACCEPT", "RETRY", "FALLBACK", "ABORT_DELIVERY")
    ddl = _ddl(db, "validator_result")
    match = re.search(r"CHECK \(decision IN \(([^)]*)\)\)", ddl)
    assert match is not None
    checked = tuple(part.strip().strip("'") for part in match.group(1).split(","))
    assert checked == words
    assert ddl.count("CHECK") == 1


def test_the_guard_check_is_the_two_inline_words(db: sqlite3.Connection) -> None:
    words = _canonical_vocabulary()["pre_delivery_guard_result"]
    assert words == ("VALID", "INVALIDATE_ACTION")
    ddl = _ddl(db, "pre_delivery_guard_result")
    match = re.search(r"CHECK \(decision IN \(([^)]*)\)\)", ddl)
    assert match is not None
    checked = tuple(part.strip().strip("'") for part in match.group(1).split(","))
    assert checked == words
    assert ddl.count("CHECK") == 1


def test_the_ack_table_carries_the_one_bit_check(db: sqlite3.Connection) -> None:
    """``final_rendered``'s CHECK is the 0/1 the adapter writes, not a
    vocabulary word: the three CHECKs in these five tables are counted here so
    a fourth one (a word list added to §22) is RED."""

    ddl = _ddl(db, "client_render_ack")
    assert ddl.count("CHECK") == 1
    assert "final_rendered INTEGER NOT NULL CHECK (final_rendered IN (0, 1))" in ddl
    assert sum(_ddl(db, table).count("CHECK") for table in TABLES) == 3


def test_the_keys_are_the_canonical_ones(db: sqlite3.Connection) -> None:
    """One row per action for the two §22 single-row records, the
    (action, chunk) pair for the ACK stream, and §21.1's own ids."""

    def _pk_columns(table: str) -> list[str]:
        return [
            str(row[1])
            for row in db.execute(f"PRAGMA table_info({table})")
            if int(row[5]) > 0
        ]

    assert _pk_columns("server_delivery_record") == ["action_id"]
    assert _pk_columns("exposure_estimate") == ["action_id"]
    assert _pk_columns("client_render_ack") == [
        "action_id",
        "rendered_chunk_seq",
    ]
    assert _pk_columns("validator_result") == ["validator_result_id"]
    assert _pk_columns("pre_delivery_guard_result") == [
        "pre_delivery_guard_result_id"
    ]


def test_the_only_foreign_key_per_table_is_the_action(db: sqlite3.Connection) -> None:
    for table in TABLES:
        assert _foreign_keys(db, table) == [
            ("generation_action_intent", "action_id", "action_id")
        ], table


def test_assistant_turn_id_carries_no_foreign_key(db: sqlite3.Connection) -> None:
    for table in ("server_delivery_record", "client_render_ack"):
        assert all(
            column != "assistant_turn_id"
            for _parent, column, _target in _foreign_keys(db, table)
        ), table


def test_terminal_at_is_the_one_nullable_column(db: sqlite3.Connection) -> None:
    """§22's ``terminal_at?``; every other non-key column is NOT NULL. A
    ``TEXT PRIMARY KEY`` reports ``notnull=0`` whatever the DDL says (the
    0010–0015 convention), which is why the keys are asserted as keys above
    and not as NOT NULL here."""

    notnull = _notnull(db, "server_delivery_record")
    assert notnull["terminal_at"] == 0
    for column in (
        "assistant_turn_id",
        "state",
        "sent_prefix",
        "last_chunk_seq",
        "started_at",
    ):
        assert notnull[column] == 1, column
    for table, keys in (
        ("client_render_ack", ("rendered_chunk_seq",)),
        ("exposure_estimate", ()),
        ("validator_result", ("attempt_no",)),
        ("pre_delivery_guard_result", ()),
    ):
        for column, flag in _notnull(db, table).items():
            if column in keys:
                assert flag == 1, (table, column)
            elif column.endswith("_id") and column != "assistant_turn_id":
                continue  # key columns: notnull is the key's business
            else:
                assert flag == 1, (table, column)


# -- ④ the header's registered readings --------------------------------------


def _header() -> str:
    return (MIGRATIONS_DIR / HEAD_0018).read_text(encoding="utf-8")


def test_the_header_quotes_the_canonical_blocks_with_their_line_numbers() -> None:
    text = _header()
    for citation in (
        "docs/DATA_MODEL.md §22",
        "docs/DATA_MODEL.md §21.1",
        "docs/STATE_MACHINES.md §13",
        "docs/STATE_MACHINES.md §16",
        "docs/RUNTIME_ARCHITECTURE.md §6 CP3a",
        "docs/RUNTIME_ARCHITECTURE.md §14",
        "docs/RUNTIME_ARCHITECTURE.md §15",
        "docs/RUNTIME_ARCHITECTURE.md §17",
        "docs/RUNTIME_ARCHITECTURE.md §18",
        "docs/RUNTIME_ARCHITECTURE.md §22",
        "docs/DATA_MODEL.md §26.1",
        "docs/DATA_MODEL.md §27",
    ):
        assert citation in text, citation
    for lines in ("1209–1249", "1176–1205", "405–440", "500–520"):
        assert lines in text, lines


def test_the_header_states_the_five_keys_and_the_fk_reading() -> None:
    text = _header()
    assert "the five ``action_id`` columns" in text
    assert "REFERENCES" in text
    assert "generation_action_intent(action_id)" in text
    assert "an action_id with no\n--     action is a row about nothing" in text


def test_the_header_quotes_0003_for_the_no_fk_column() -> None:
    text = _header()
    assert "assistant_turn_id" in text
    assert "No provider CHECK on generation_action_intent.assistant_turn_id:" in text
    assert "the id is minted at action creation" in text
    assert "back-reference survives as plain" in text


def test_the_header_states_the_empty_prefix_reading() -> None:
    text = _header()
    assert "the empty string is \"nothing sent yet\"" in text
    assert "an empty string is a prefix of" in text


def test_the_header_states_the_no_check_reading_and_its_revisit() -> None:
    text = _header()
    assert "carry no schema-level CHECK" in text
    assert "Revisit:" in text
    assert "canonical moves the vocabularies into §22's blocks" in text


def test_the_header_registers_the_exposure_word_reading_and_the_refusal() -> None:
    text = _header()
    assert "carry §13's ``exposure_level`` words, not" in text
    assert "exposure_level\": \"FULL\"" in text
    assert "**refused**" in text


def test_the_header_registers_the_registry_drift() -> None:
    text = _header()
    assert "ValidatorResultRecord" in text
    assert "The drift is **registered," in text
    assert "not repaired**" in text
    assert "elc.persona.types.ValidatorResult" in text


def test_the_header_claims_0001_to_0017_are_byte_identical() -> None:
    assert "0001–0017 are byte-identical" in _header()


def test_the_header_registers_the_removal_surfaces() -> None:
    text = _header()
    assert "removal surface" in text
    assert "attempt_record.exposure_estimate_id" in text
