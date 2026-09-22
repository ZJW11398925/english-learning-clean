"""P6-2 ⑤⑧⑩ — the invariants this cut must not break, and the pin that reads a
baseline asset instead of a document.

Three kinds of claim live here:

- **the policy's purity**, scanned rather than promised: ``spacing.py`` carries
  no SQL, opens no connection, reads no clock, touches exactly one field of the
  freshness record it is handed, and declares no word of its own;
- **the vocabulary boundaries**: ``event_type`` still has no word list anywhere
  in this package (R5 — the due policy reads ``engaged`` and ``created_at`` and
  gives the column no meaning), the R4 anchors are BF-02's own numbers
  **extracted from the reference profile**, and the Learning side's new face is
  a 1:1 increment that did not move ``FreshnessView``;
- **the migration boundary**: R1 holds because the directory's name set and
  0012's bytes say so, not because prose says so.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import sqlite3
from pathlib import Path

import pytest

from elc.learning.controller import LearningController
from elc.learning.queries import LearningQueries
from elc.learning.store import SqliteLearningStore
from elc.learning.types import FreshnessView
from elc.platform.db import connection, migrations
from elc.platform.types import Ok
from elc.scheduler import spacing as spacing_module
from elc.scheduler.controller import SchedulerController
from elc.scheduler.spacing import (
    SCHEDULER_MODEL_VERSION,
    URGENCY_ANCHORS,
    FreshnessPort,
    LearningReadPort,
    ReviewEventRole,
    next_window,
    plan_schedule_item,
    state_at,
    urgency_of,
)
from elc.scheduler.types import ReviewState
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)
from tests.phase3.sql_write_scan import write_targets, write_targets_from_source

SCHEDULER_SRC = SRC_ROOT / "scheduler"
SPACING_PATH = SCHEDULER_SRC / "spacing.py"
SPACING_SOURCE = SPACING_PATH.read_text(encoding="utf-8")
CONTROLLER_SOURCE = (SCHEDULER_SRC / "controller.py").read_text(encoding="utf-8")

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PROFILE = (
    REPO_ROOT
    / "behavioral_baselines"
    / "planner"
    / "planner_reference_profile_v1_1.json"
)

#: The head this cut must leave exactly where P6-1 put it, byte for byte
#: (CRLF-normalized — the repo's Windows convention).
FROZEN_HEAD = "0012_schedule_review.sql"
FROZEN_HEAD_DIGEST = (
    "e0e18264bfd0d5da9adf7e1896bb34e233a92591af91b9eba837c1b67830aba1"
)

#: The modules the scheduler package consists of: P6-1's five plus the policy.
#: P7-0 added ``authority.py`` — the watermark handshake (``CURRENT`` /
#: ``STALE``) a consumer compares a row against the current Learning evidence
#: with — which is a *primitive*, not a second policy file: it reads one §5.2
#: column and answers one of two words, while the reading that acts on it
#: (BF-02 §5's degradation) lives in elc.planner.feature_assembly. A further
#: module would be a face nobody reviewed.
SCHEDULER_MODULES = (
    "__init__.py",
    "authority.py",
    "commands.py",
    "controller.py",
    "queries.py",
    "spacing.py",
    "store.py",
    "types.py",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _calls(source: str) -> list[str]:
    return [
        node.func.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


def _code_only(source: str) -> str:
    """The module's executable text: docstrings blanked, comments dropped.

    A scan for a forbidden *use* must not be defeated by the prose that
    explains why the use is absent — this cut's modules name ``datetime.now``,
    ``sqlite`` and ``event_type`` precisely to say they do not touch them (the
    p6-1 lesson: "the word appears nowhere" is the wrong pin, so the word is
    looked for where a use would have to be written).
    """

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0].value.value = ""
    return ast.unparse(tree)


SPACING_CODE = _code_only(SPACING_SOURCE)
CONTROLLER_CODE = _code_only(CONTROLLER_SOURCE)


# -- the policy's purity ------------------------------------------------------


def test_the_policy_carries_no_sql() -> None:
    """Zero SQL in both shapes: no write statement (the AST scan), no statement
    word, no database handle, no connection verb."""

    assert write_targets(SPACING_PATH) == set()
    assert write_targets_from_source(SPACING_SOURCE) == set()
    lowered = SPACING_CODE.lower()
    for token in ("select ", "insert ", "update ", "delete ", "sqlite"):
        assert token not in lowered, token
    for token in (".execute(", ".commit(", ".rollback("):
        assert token not in SPACING_CODE, token


def test_the_policy_opens_no_connection_and_imports_no_database() -> None:
    """The import set is the whole story: two standard-library helpers for the
    content-addressed version, the clock *type* (never the clock), typing, and
    the platform/domain types it returns. P7-0 added ``enum`` for the
    event-role freeze table (:class:`ReviewEventRole` — one word per way an
    event can enter the ladder, declared where the ladder is)."""

    imported: set[str] = set()
    for node in ast.walk(ast.parse(SPACING_SOURCE)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported == {
        "__future__",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "typing",
        "elc.platform.types",
        "elc.scheduler.types",
    }
    assert "connect" not in _calls(SPACING_SOURCE)
    assert "open" not in _calls(SPACING_SOURCE)


def test_the_policy_reads_no_clock() -> None:
    """Zero clock, in both shapes: no clock call in the AST, and no clock verb
    in the executable text (the module docstring is allowed to *name* the
    Learning read clock — that is where the reason for not consuming it is
    written, which is why the text scan runs over the code only)."""

    calls = _calls(SPACING_SOURCE)
    for forbidden in (
        "now",
        "utcnow",
        "today",
        "time",
        "monotonic",
        "perf_counter",
    ):
        assert forbidden not in calls, forbidden
    for token in ("datetime.now", "time.time", "monotonic", "perf_counter"):
        assert token not in SPACING_CODE, token


def test_the_decision_takes_its_instant_as_an_argument() -> None:
    """The clock is the caller's: the two faces that answer *about* a moment
    take ``as_of``, while the window builder is a function of the anchor
    alone."""

    assert "as_of" in inspect.signature(state_at).parameters
    assert "as_of" in inspect.signature(plan_schedule_item).parameters
    assert "as_of" not in inspect.signature(next_window).parameters


def test_the_policy_reads_one_freshness_field_and_no_other() -> None:
    """The port is narrow on purpose: every attribute access on the freshness
    value names the one field, so the clock-derived band and elapsed days
    cannot be consumed even by accident."""

    read = {
        node.attr
        for node in ast.walk(ast.parse(SPACING_SOURCE))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in ("freshness", "record", "view")
    }
    assert read == {"last_strong_retrieval_at"}


def test_the_freshness_port_declares_exactly_one_field() -> None:
    declared = [
        name
        for name in vars(FreshnessPort)
        if not name.startswith("_") and name != "last_strong_retrieval_at"
    ]
    assert declared == []
    assert "last_strong_retrieval_at" in SPACING_SOURCE


def test_the_learning_read_port_is_two_methods_wide() -> None:
    declared = {
        name
        for name, member in vars(LearningReadPort).items()
        if not name.startswith("_") and inspect.isfunction(member)
    }
    assert declared == {"get_freshness", "get_learning_watermark"}


def test_the_policy_declares_no_third_review_state() -> None:
    """The four §5.2 states are the vocabulary; this module adds no *state* of
    its own (a fifth state would be a review lifecycle the canonical block does
    not contain).

    P7-0 added one enum to this file, so the structural half of the pin is now
    an exact list plus a disjointness proof rather than "no enum at all":
    :class:`ReviewEventRole` names the four ways an event can enter the ladder
    (``engaged`` × ``created_at``), and every one of its words is asserted
    disjoint from the §5.2 states — the claim the original scan was making.
    """

    enums = [
        node.name
        for node in ast.walk(ast.parse(SPACING_SOURCE))
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "StrEnum"
            for base in node.bases
        )
    ]
    assert enums == ["ReviewEventRole"]
    assert set(ReviewEventRole.__members__) == {
        "ANCHOR_AND_ADVANCE",
        "ANCHOR_ONLY",
        "ADVANCE_ONLY",
        "HISTORY_ONLY",
    }
    assert set(ReviewEventRole.__members__) & set(ReviewState.__members__) == set()
    assert not [word for word in ReviewEventRole if word in set(ReviewState)]
    assert set(URGENCY_ANCHORS) == set(ReviewState)
    assert len(URGENCY_ANCHORS) == 4


# -- the urgency anchors, extracted from BF-02 --------------------------------


def test_the_urgency_anchors_are_bf_02s_reference_profile() -> None:
    """R4's numbers are read out of the frozen baseline asset rather than typed
    twice: the profile's ``reference_factor_bands.schedule_urgency`` map is
    compared with the declared table *and* with what the function answers."""

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    anchors = profile["reference_factor_bands"]["schedule_urgency"]
    assert anchors == {
        "NOT_SCHEDULED": 0.0,
        "UPCOMING": 0.25,
        "DUE": 0.75,
        "OVERDUE": 1.0,
    }
    assert {
        state.value: value for state, value in URGENCY_ANCHORS.items()
    } == anchors
    for state in ReviewState:
        assert urgency_of(state) == anchors[state.value], state.value


def test_the_anchor_maps_keys_are_the_canonical_states() -> None:
    """The keys are §5.2's four words verbatim and the values are BF-02's; the
    two vocabularies are not mixed."""

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    anchors = profile["reference_factor_bands"]["schedule_urgency"]
    assert set(anchors) == {
        "NOT_SCHEDULED",
        "UPCOMING",
        "DUE",
        "OVERDUE",
    }
    assert [state.value for state in URGENCY_ANCHORS] == [
        state.value for state in ReviewState
    ]


def test_the_profile_is_a_frozen_baseline_asset() -> None:
    assert PROFILE.parent.parent.name == "behavioral_baselines"
    body = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert body["profile_id"].startswith("planner-v1.1-reference")
    assert body["status"] == "REFERENCE_DEFAULT_CALIBRATABLE"


def test_no_scheduler_module_declares_a_second_anchor_table() -> None:
    """One table: a module-level dict literal carrying anchor values exists in
    ``spacing.py`` and nowhere else in the package (a second copy could drift
    from BF-02 with nothing to notice)."""

    holders: list[str] = []
    for path in sorted(SCHEDULER_SRC.rglob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if isinstance(value, ast.Dict) and any(
                isinstance(item, ast.Constant)
                and isinstance(item.value, float)
                and item.value in (0.25, 0.75)
                for item in value.values
            ):
                holders.append(path.name)
    assert holders == ["spacing.py"]


# -- the vocabulary boundaries -----------------------------------------------


def test_event_type_still_carries_no_vocabulary() -> None:
    """R5: the due policy reads ``engaged`` (the typed column) and
    ``created_at`` (recency) and gives ``event_type`` no meaning at all — no
    word list, no constant, no branch, and not even a mention in the two
    modules that decide."""

    assert "event_type" not in SPACING_CODE
    assert "event_type" not in CONTROLLER_CODE
    for path in sorted(SCHEDULER_SRC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "EVENT_TYPES" not in source, path.name
        assert "EVENT_TYPE_" not in source, path.name
    for node in ast.walk(ast.parse(SPACING_SOURCE + CONTROLLER_SOURCE)):
        if isinstance(node, ast.Compare):
            compared = [
                side.attr
                for side in [node.left, *node.comparators]
                if isinstance(side, ast.Attribute)
            ]
            assert "event_type" not in compared
        assert not (
            isinstance(node, ast.Constant) and node.value == "event_type"
        )


def test_the_policy_branches_on_engagement_and_recency_only() -> None:
    """The two columns the ladder and the window read, and no third: no
    ``event_type`` word of any spelling enters the decision."""

    assert "engaged" in SPACING_CODE
    assert "created_at" in SPACING_CODE
    for invented_word in ("RECALL", "REVIEW_ATTEMPT", "GRADED", "SKIPPED"):
        assert invented_word not in SPACING_CODE, invented_word


def test_the_scheduler_package_still_carries_no_lease_or_ttl() -> None:
    """Local V1's permanent prohibition (RA §24.1), re-checked over the files
    this cut touches."""

    for word in ("lease", "heartbeat", "ttl", "expire_after", "distributed_lock"):
        assert word not in SPACING_SOURCE.lower(), word
        assert word not in CONTROLLER_SOURCE.lower(), word


def test_the_scheduler_package_is_the_expected_set_of_modules() -> None:
    """The module set is the reviewed one (P7-0's ``authority.py`` included);
    no second policy file, no helper module that would move the decision
    somewhere a reviewer is not looking."""

    assert tuple(sorted(path.name for path in SCHEDULER_SRC.glob("*.py"))) == (
        SCHEDULER_MODULES
    )


def test_the_policy_names_the_documents_it_answers_to() -> None:
    docstring = spacing_module.__doc__ or ""
    for phrase in ("DOMAIN_MODEL.md §9", "§7", "DATA_MODEL §5.2", "§1.4"):
        assert phrase in docstring, phrase


# -- the Learning side (R6) ---------------------------------------------------


def test_the_learning_watermark_face_is_a_one_to_one_increment(
    learning: SqliteLearningStore,
) -> None:
    """R6: the protocol and the authority face gained one method; the store
    keeps its own spelling for its own use, and the two answer the same
    number."""

    assert "get_learning_watermark" in vars(LearningQueries)
    assert "get_learning_watermark" not in vars(SqliteLearningStore)
    assert hasattr(SqliteLearningStore, "get_evidence_watermark")
    result = LearningController(learning).get_learning_watermark()
    assert isinstance(result, Ok), result
    assert result.value == learning.get_evidence_watermark() == 0


def test_the_freshness_view_field_set_is_unchanged() -> None:
    """R6 avoided this on purpose: the watermark did not enter the freshness
    record, so no Phase 2/3 field pin was touched."""

    assert [field.name for field in dataclasses.fields(FreshnessView)] == [
        "target_id",
        "last_strong_retrieval_at",
        "days_since_strong_retrieval",
        "freshness_band",
        "stability_band",
    ]


# -- the migration boundary ---------------------------------------------------


def test_this_cut_added_no_migration() -> None:
    """P6-2's R1, restated for the world P6-3 made: *this* cut added no table,
    no column and no new file. 0012 is where P6-2 left the head, its bytes did
    not move, nothing was smuggled between it and the next slice's file, and
    the lineage is still contiguous. (The pin read ``names[-1] == FROZEN_HEAD``
    while 0012 was the head; 0013_planner_constraint is P6-3's file, and this
    one asserts what remains true of P6-2 rather than being deleted.)

    The successor is spelled as a **literal** on purpose (INFO-2): this claim
    is about 0012 and the file that follows it, which will still be true after
    a 0014 lands — a ``SCHEMA_HEAD_FILE`` reference here would silently become
    false at the next migration and force an edit to a pin that has nothing to
    do with it (the same choice tests/phase6/test_p6_1_migration_0012.py
    makes, and the opposite of the *head* pins where the constant is correct).

    Gate 2 is where that prediction was cashed: 0014_deletion_tombstone
    landed, and this pin needed **no edit** — which is the whole point of
    spelling the successor literally.
    """

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert FROZEN_HEAD in names
    assert names[names.index(FROZEN_HEAD) + 1] == "0013_planner_constraint.sql"
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]
    assert _digest(MIGRATIONS_DIR / FROZEN_HEAD) == FROZEN_HEAD_DIGEST


def test_the_schema_head_is_fourteen() -> None:
    """The stamp the shared constant declares is the one a fresh database
    carries (this pin read "12" through P6-2; P6-3's 0013 moved it to "13"
    and Gate 2's 0014 to "14" — the name moves with the value so the test
    still says what it asserts)."""

    conn = connection.connect(":memory:")
    try:
        migrations.apply_migrations(conn)
        assert migrations.schema_version(conn) == SCHEMA_HEAD_VERSION
        stamps = dict(
            conn.execute(
                "SELECT key, value FROM schema_meta WHERE key IN"
                " ('schema_version', 'runtime_schema_version')"
            ).fetchall()
        )
        assert stamps == {
            "schema_version": SCHEMA_HEAD_VERSION,
            "runtime_schema_version": SCHEMA_HEAD_VERSION,
        }
    finally:
        conn.close()


def test_the_schedule_table_is_the_one_migration_0012_created(
    db: sqlite3.Connection,
) -> None:
    """The columns this cut computes into are the twelve §5.2 columns: the
    decision added no column to store an intermediate, and no second table
    appeared beside them."""

    assert [str(row[1]) for row in db.execute("PRAGMA table_info(schedule_item)")] == [
        "schedule_item_id",
        "target_type",
        "target_id",
        "evidence_modality",
        "review_state",
        "review_urgency",
        "next_review_window_start",
        "next_review_window_end",
        "spacing_stage",
        "source_learning_watermark",
        "version",
        "updated_at",
    ]
    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "schedule_item" in tables and "review_event" in tables
    assert not [name for name in tables if "spacing" in name or "due" in name]


# -- the package face --------------------------------------------------------


def test_the_policy_is_reachable_from_the_package() -> None:
    """A face a consumer cannot find is a face it will re-implement: the policy
    and the model stamp are exported, and the controller is the composition."""

    import elc.scheduler as package

    assert package.SCHEDULER_MODEL_VERSION == SCHEDULER_MODEL_VERSION
    assert package.plan_schedule_item is spacing_module.plan_schedule_item
    assert package.urgency_of is urgency_of
    assert SchedulerController.__module__ == "elc.scheduler.controller"


@pytest.mark.parametrize(
    "name", ["spacing.py", "controller.py", "store.py", "queries.py", "commands.py"]
)
def test_no_module_reinstates_a_phase_pointer(name: str) -> None:
    """The pointer this cut deletes stays deleted: no module of the package
    raises a phase pointer or carries the constant any more (the phase
    arrived)."""

    source = (SCHEDULER_SRC / name).read_text(encoding="utf-8")
    assert "P6_2_DUE_DECISION_POINTER" not in source, name
    assert "NotImplementedError" not in source, name


def test_the_policy_has_no_side_effect_when_imported() -> None:
    """Importing it must not touch a world: no module-level call to anything
    but ``TypeVar`` (the one factory the declarations need)."""

    allowed = {"TypeVar"}
    for node in ast.parse(SPACING_SOURCE).body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            name = func.id if isinstance(func, ast.Name) else None
            assert name in allowed, ast.dump(node)[:60]
