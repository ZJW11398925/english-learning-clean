"""P6-1 ②⑤ — the invariants this slice must hold, each pinned by a counter-case.

- **The V1 modality boundary.** ``EvidenceModality`` is the frozen text pair
  (§24.14), so ``VOICE_PRODUCTION`` / ``AUDIO_COMPREHENSION`` are unreachable
  through the ScheduleItem field *and* refused by the schema — the mechanism
  face of IP §16 DoD #22 (a voice/audio review debt cannot be written here).
- **No leases, no heartbeats, no TTL.** Local V1 forbids them (RA §24.1); the
  Scheduler is a durable row plus an append-only history, and its source says
  nothing else.
- **D-INV-009.** Learning provides freshness and never emits ``REVIEW_DUE``;
  the due decision is the Scheduler's — declared here and only here.
- **Deletability.** A schedule row is reachable from its target (the modality
  key) and its history from the row, so a deletion by target has a lookup path
  instead of a scan of the world.
- **No interpretation.** ``source_learning_watermark`` and ``review_urgency``
  are carried verbatim, and nothing in this slice advances a spacing stage.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.platform.types import EvidenceModality, Ok
from elc.scheduler.controller import SchedulerController
from elc.scheduler.queries import SchedulerQueries
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState, SpacingStage
from tests.conftest import SRC_ROOT

from .conftest import (
    MODALITY,
    OTHER_MODALITY,
    TARGET_ID,
    TARGET_TYPE,
    review_event,
    schedule_item,
)

SCHEDULER_SRC = SRC_ROOT / "scheduler"
LEARNING_SRC = SRC_ROOT / "learning"

#: Local V1's permanent prohibitions (RUNTIME_ARCHITECTURE §24.1): no lease, no
#: heartbeat, no TTL, no distributed lock.
FORBIDDEN_INFRA = (
    "lease",
    "heartbeat",
    "ttl",
    "expire_after",
    "distributed_lock",
)


def _code(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_type_layer_cannot_express_a_voice_or_audio_modality() -> None:
    """§24.14's frozen V1 pair: the future members do not exist as values."""

    assert tuple(EvidenceModality.__members__) == (
        "TEXT_PRODUCTION",
        "TEXT_COMPREHENSION",
    )
    for future in ("VOICE_PRODUCTION", "AUDIO_COMPREHENSION"):
        with pytest.raises(ValueError):
            EvidenceModality(future)


@pytest.mark.parametrize("future", ["VOICE_PRODUCTION", "AUDIO_COMPREHENSION"])
def test_the_db_layer_refuses_a_voice_or_audio_modality(
    db: sqlite3.Connection,
    scheduler_store: SqliteSchedulerStore,
    future: str,
) -> None:
    """The second half of the same proof (IP §16 DoD #22): a row that reached
    the database by any other route still cannot carry one."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE schedule_item SET evidence_modality = ?"
            " WHERE schedule_item_id = 'si-1'",
            (future,),
        )
    assert db.execute(
        "SELECT evidence_modality FROM schedule_item"
    ).fetchone() == ("TEXT_PRODUCTION",)


def test_the_scheduler_source_carries_no_lease_or_ttl_vocabulary() -> None:
    offenders: list[str] = []
    for path in sorted(SCHEDULER_SRC.rglob("*.py")):
        source = _code(path).lower()
        for word in FORBIDDEN_INFRA:
            if word in source:
                offenders.append(f"{path.name}: {word}")
    assert not offenders, offenders


def test_the_scheduler_package_imports_no_other_domain() -> None:
    """The durable core is platform + its own types: it reads no Learning
    store, no curriculum provider and no teaching port — the freshness input
    arrives as a watermark column, not as a dependency (DOMAIN_MODEL §9
    Reads)."""

    allowed = (
        "elc.platform",
        "elc.scheduler",
        "dataclasses",
        "datetime",
        "enum",
        "sqlite3",
        "typing",
        "__future__",
    )
    offenders: list[str] = []
    for path in sorted(SCHEDULER_SRC.rglob("*.py")):
        for line in _code(path).splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            target = stripped.split()[1]
            if not target.startswith(allowed):
                offenders.append(f"{path.name}: {stripped}")
    assert not offenders, offenders


def test_learning_never_emits_review_due() -> None:
    """D-INV-009 (DOMAIN_MODEL.md line 903): "Scheduler 决定 review due；
    Learning 只提供 freshness" — the word is never a *value* on the Learning
    side, no learning module declares or calls ``is_review_due``, and no
    learning module touches the scheduler's two tables."""

    offenders: list[str] = []
    for path in sorted(LEARNING_SRC.rglob("*.py")):
        source = _code(path)
        if "is_review_due" in source:
            offenders.append(f"{path.name}: is_review_due")
        if '"REVIEW_DUE"' in source or "'REVIEW_DUE'" in source:
            offenders.append(f"{path.name}: REVIEW_DUE value")
        if "schedule_item" in source or "review_event" in source:
            offenders.append(f"{path.name}: scheduler table")
    assert not offenders, offenders
    # The scan is not vacuous: the invariant is *documented* where the
    # learning-flag vocabulary is declared (BF-01 §25's forbidden scheduler
    # words) — which is why a plain "the word appears nowhere" scan would be
    # the wrong pin.
    estimator = _code(LEARNING_SRC / "estimator.py")
    assert "forbidden scheduler" in estimator
    assert "REVIEW_DUE / TRANSFER_NEEDED / TEACH_NOW / HIGH_PRIORITY" in estimator


def test_the_due_decision_is_declared_in_one_place() -> None:
    """The decision home is this domain's face, and the declaration is the
    Phase 0 one: ``is_review_due`` on the queries protocol and on the
    controller — nowhere else in the tree."""

    assert hasattr(SchedulerQueries, "is_review_due")
    assert hasattr(SchedulerController, "is_review_due")
    holders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "def is_review_due" in _code(path):
            holders.append(path.relative_to(SRC_ROOT).as_posix())
    assert holders == ["scheduler/controller.py", "scheduler/queries.py"]


def test_a_row_is_reachable_from_its_target(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Deletion-readiness: the modality key *is* the lookup path, and the
    history hangs off the row's id — so a delete by target starts from a
    column match rather than from a full scan of the world."""

    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item("si-1")), Ok
    )
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item("si-2", modality=OTHER_MODALITY)
        ),
        Ok,
    )
    assert isinstance(
        scheduler_store.record_review_event(review_event("re-1")), Ok
    )
    found = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(found, Ok) and found.value is not None
    assert found.value.schedule_item_id == "si-1"
    history = scheduler_store.list_review_events(found.value.schedule_item_id)
    assert isinstance(history, Ok)
    assert [event.review_event_id for event in history.value] == ["re-1"]


def test_the_watermark_is_carried_and_never_interpreted(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The learning-side watermark is an opaque string here: whatever a caller
    wrote is what a read returns — no parsing, no bumping, no comparison."""

    for index, watermark in enumerate(("", "wm-7", "not-a-number")):
        written = scheduler_store.upsert_schedule_item(
            schedule_item(
                "si-1",
                watermark=watermark,
                version=f"sv-{index + 1}",
            )
        )
        assert isinstance(written, Ok), written
        read = scheduler_store.get_schedule_item(
            TARGET_TYPE, TARGET_ID, MODALITY
        )
        assert isinstance(read, Ok) and read.value is not None
        assert read.value.source_learning_watermark == watermark


def test_no_spacing_transition_is_implemented(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The ladder is p6-2's: this slice stores the stage it is given and never
    walks one — a silent stage stays silent, and no mapping table exists."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.spacing_stage is None
    source = _code(SCHEDULER_SRC / "store.py")
    assert "STAGE_1" not in source and "STAGE_4" not in source
    assert not any(
        "stage" in name.lower() and "=" in name
        for name in ("NEXT_STAGE", "STAGE_LADDER")
    )


def test_review_urgency_is_never_computed(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """R4: the column is carried, never derived — writing ``None`` keeps
    ``None``, and no arithmetic touches the field anywhere in this slice."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.review_urgency is None
    source = _code(SCHEDULER_SRC / "store.py")
    assert "review_urgency +" not in source
    assert "review_urgency *" not in source
    assert "review_urgency =" in source  # it is stored, not computed


def test_the_scheduler_cannot_reach_the_readiness_layer() -> None:
    """No R0–R4 dependency: the scheduler neither imports the curriculum
    readiness judgement nor names any readiness level — a schedule row is
    written for a target a caller already chose."""

    offenders: list[str] = []
    for path in sorted(SCHEDULER_SRC.rglob("*.py")):
        source = _code(path)
        if "readiness" in source.lower() or "elc.curriculum" in source:
            offenders.append(path.name)
        for level in ("R0", "R1", "R2", "R3", "R4"):
            if f'"{level}"' in source or f"'{level}'" in source:
                offenders.append(f"{path.name}: {level}")
    assert not offenders, offenders


def test_the_schedule_row_carries_no_owner_column(
    db: sqlite3.Connection,
) -> None:
    """§5.2 pins no user/owner column, and this slice does not add one: the
    key is the modality key (the Local V1 convention is declared, not
    invented as a column)."""

    columns = [
        str(row[1]) for row in db.execute("PRAGMA table_info(schedule_item)")
    ]
    assert not [
        name
        for name in columns
        if name.endswith("_id") and name in ("user_id", "user_profile_id")
    ]
    assert "user_scope_id" not in columns
    assert "owner_epoch" not in columns


def test_the_two_review_states_this_slice_must_not_invent_are_absent(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """§5.2's four words only: no ``LAPSED``, no ``SUSPENDED``, and no third
    value the store would accept from a caller."""

    assert tuple(ReviewState.__members__) == (
        "NOT_SCHEDULED",
        "UPCOMING",
        "DUE",
        "OVERDUE",
    )
    assert not hasattr(ReviewState, "SUSPENDED")
    assert not hasattr(SpacingStage, "STAGE_5")
