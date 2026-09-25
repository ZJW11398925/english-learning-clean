"""Phase 10 fixtures.

The p10-0 world is phase 3's (the real conversation store + Learning store +
Teaching controller + generation store over one app.db), re-exported here so
this package's modules can ask for those fixtures directly — the phase-9
precedent: a phase's *fixtures* are its world, and copying them line for line
would only give the two copies a chance to drift. The builders the tests use
(``make_teaching_coordinator``, ``make_lease``) are imported as plain
functions in the modules that need them, the same way.

Only one fixture is new: ``delivery_store`` — the §22 delivery-record store,
which no earlier phase's fixture set carries.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence
from tests.phase3.conftest import (  # noqa: F401  (fixtures, re-exported)
    conversation,
    db,
    decision_cycle_store,
    fence,
    generation_store,
    learning,
    learning_controller,
    store,
    target_provider,
    teaching_controller,
    teaching_store,
)

__all__ = [
    "conversation",
    "db",
    "decision_cycle_store",
    "delivery_store",
    "fence",
    "generation_store",
    "learning",
    "learning_controller",
    "store",
    "target_provider",
    "teaching_controller",
    "teaching_store",
]


@pytest.fixture()
def delivery_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteDeliveryRecordStore:
    """The §22 delivery-record store over this test's app.db + epoch."""

    return SqliteDeliveryRecordStore(db, fence)
