"""P8-4 ⑤ — the ordinary turn with the automatic leg (the same-turn integration).

This is the cut's core: RA §4 steps 3–8 run **inside** a plain conversation
turn, behind one opt-in (``ConversationCoordinator``'s ``automatic_teaching``
wiring), and every face below is asserted against the durable rows the shipped
chain writes:

- **not injected ⇒ nothing changes**: the reply is the ordinary persona's, the
  cycle keeps its all-``None`` bindings, and no planner / Gate / teaching /
  ledger row exists — the same world that ALLOWs with the wiring produces none
  of that without it;
- **injected over the real corpus ⇒ the honest verdict**: the authorities are
  read (bindings stamped), the generators answer **no candidates** (the R2/R3
  gap BF-02 §10 names), the run is a complete ``NO_TARGET`` with its Planner
  half durable, and the turn still finishes as an ordinary one — no Gate row,
  no Moment, no exposure event, nothing silent; a wiring that withholds an
  authority instead gets BF-02 §5's ``INCOMPLETE`` / ``DEGRADED``;
- **injected with the acceptance's test supply ⇒ the ALLOW chain**: CP2's five
  facts in one commit, the opening delivered through the P1 pipeline, the
  Moment at ``AWAITING_USER``, and the §20 ``teaching_presented`` event carrying
  the Moment as its provenance;
- **the crash windows (RA §23)**: a CP2 that was committed and a delivery that
  never happened is re-dispatched on the *same* action id (one assistant turn,
  one Gate decision, one event); a CP3 crash leaves a ``DELIVERING`` turn whose
  re-entry **reconciles** it — P9-4 landed the repair this file registered
  (``test_a_cp3_crash_is_reconciled_and_re_sends_nothing``), so the exposure
  event is written once and nothing is re-sent;
- **the leg's own read-back** (the "continue the same ``action_id``" evidence):
  a generation face that answers no action, or fails the read, refuses the leg
  and the turn still lands as an ordinary reply — with the CP2 half durable and
  undelivered (measured and registered in those two cases);
- **§13's protection is the Gate's**: with a Moment live, the next ordinary
  turn's leg opens nothing new and the persona answers.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.persona import ScriptedPersonaProvider
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from tests.phase7.conftest import TARGET_ID
from tests.phase8.p8_4_world import (
    PLANNER_FACT_TABLES,
    TEACHING_FACT_TABLES,
    TEACHING_ONLY_TABLES,
    TURN_TEXT,
    World,
    acceptance_supply,
    begin_turn,
    begin_turn_ok,
    build_content,
    count_events,
    counts,
    wiring,
    world,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db: sqlite3.Connection, fence, content: Path) -> World:
    return world(db, fence, content)


def automatic(p8world, *, supply=True):
    """The wiring, with the ALLOW acceptance's test supply by default."""

    return wiring(p8world, supply=acceptance_supply() if supply else None)


# -- ① not injected ⇒ nothing changes ----------------------------------------


def test_an_uninjected_turn_answers_with_the_ordinary_persona(
    db: sqlite3.Connection, p8world
) -> None:
    completion = begin_turn_ok(build_coordinator(p8world), "cm-plain")
    assert completion.outcome == "REPLIED_FULL"
    assert completion.reply_text is not None
    assert TURN_TEXT in completion.reply_text
    assert completion.ledger_event is None
    assert completion.ledger_failure is None


def test_an_uninjected_turn_writes_no_planner_gate_or_ledger_row(
    db: sqlite3.Connection, p8world
) -> None:
    begin_turn_ok(build_coordinator(p8world), "cm-plain")
    assert counts(db, *PLANNER_FACT_TABLES) == dict.fromkeys(
        PLANNER_FACT_TABLES, 0
    )
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 0
    )
    assert not str(
        db.execute("SELECT action_id FROM generation_action_intent").fetchone()[0]
    ).endswith(("-automatic-open", "-teaching-open"))
    assert counts(db, "planning_ledger", "planning_ledger_event") == {
        "planning_ledger": 0,
        "planning_ledger_event": 0,
    }


def test_an_uninjected_turn_keeps_the_all_none_bindings(
    db: sqlite3.Connection, p8world
) -> None:
    begin_turn_ok(build_coordinator(p8world), "cm-plain")
    row = db.execute(
        "SELECT learning_snapshot_id, evidence_watermark, curriculum_version,"
        " goal_version, schedule_version, policy_version, context_view_version,"
        " relationship_view_version FROM decision_cycle"
    ).fetchone()
    assert row == (None,) * 8


def test_the_opt_in_is_what_changes_the_turn(
    db: sqlite3.Connection, p8world
) -> None:
    """The same world, twice: without the wiring nothing is planned; with it
    the cycle's bindings are stamped from what the leg read."""

    begin_turn_ok(build_coordinator(p8world), "cm-plain")
    begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-auto"
    )
    rows = db.execute(
        "SELECT learning_snapshot_id, evidence_watermark, curriculum_version,"
        " goal_version, schedule_version, policy_version FROM decision_cycle"
        " ORDER BY rowid"
    ).fetchall()
    assert rows[0] == (None,) * 6
    stamp = rows[1]
    assert stamp[0] is not None
    assert stamp[1] == 0
    assert stamp[2] == "curriculum-v1"
    assert stamp[3] == "gv-p8-4"
    assert stamp[4] == "sd1"
    assert stamp[5] == "pv-p8-4"


# -- ② injected over the real corpus ⇒ the honest verdict --------------------


def test_the_real_corpus_answers_no_target_and_still_finishes_the_turn(
    db: sqlite3.Connection, p8world
) -> None:
    """No injected supply: the generators run over the shipped corpus and
    answer **zero** candidates (the R2/R3 gap BF-02 §10 names), so the run is
    a complete ``NO_TARGET`` — the turn finishes as an ordinary one, the
    Planner half is durable, and nothing teaching-shaped exists."""

    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world, supply=False)),
        "cm-real",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert TURN_TEXT in (completion.reply_text or "")
    assert completion.ledger_event is None
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 0
    )
    assert not str(
        db.execute("SELECT action_id FROM generation_action_intent").fetchone()[0]
    ).endswith(("-automatic-open", "-teaching-open"))
    assert count_events(db) == 0
    assert counts(db, *PLANNER_FACT_TABLES) == dict.fromkeys(
        PLANNER_FACT_TABLES, 1
    )
    assert counts(db, "gate_decision") == {"gate_decision": 0}
    # NO_TARGET is a decision, not a failure: the decision row is durable and
    # it selects nothing.
    assert db.execute(
        "SELECT decision, selected_candidate_id FROM planner_decision"
    ).fetchone() == ("NO_TARGET", None)


def test_the_real_corpus_run_is_durable_with_its_own_reason(
    db: sqlite3.Connection, p8world
) -> None:
    begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world, supply=False)),
        "cm-real",
    )
    assert db.execute(
        "SELECT status, error_code FROM planner_execution_status"
    ).fetchone() == ("SUCCEEDED", None)
    trace = db.execute("SELECT factor_trace FROM planner_evaluation").fetchone()[0]
    assert "NO_TARGET" in trace
    assert "NO_ELIGIBLE_CANDIDATE" in trace
    assert db.execute(
        "SELECT outcome FROM runtime_decision_outcome"
    ).fetchone() == ("NORMAL",)


def test_a_missing_authority_degrades_and_is_recorded(
    db: sqlite3.Connection, p8world
) -> None:
    """A wiring that leaves an authority out gets BF-02 §5's ``INCOMPLETE``
    verdict rather than a number (the policy and the portfolio are the two
    the Gate's automatic profile needs), and the reason is durable: DEGRADED,
    no fabricated Decision, no Gate row, and the turn is still an ordinary
    one."""

    completion = begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(
                p8world, supply=acceptance_supply(), user_config=False
            ),
        ),
        "cm-degrade",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 0
    )
    assert count_events(db) == 0
    assert db.execute(
        "SELECT COUNT(*) FROM planner_decision"
    ).fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM gate_decision"
    ).fetchone()[0] == 0
    assert db.execute(
        "SELECT status, error_code FROM planner_execution_status"
    ).fetchone() == ("DEGRADED", "FEATURE_ASSEMBLY_INCOMPLETE")
    assert db.execute(
        "SELECT outcome FROM runtime_decision_outcome"
    ).fetchone() == ("DEGRADED_NO_AUTOMATIC_TEACHING",)
    trace = db.execute("SELECT factor_trace FROM planner_evaluation").fetchone()[0]
    assert "TEACHING_POLICY" in trace and "GOAL_PORTFOLIO" in trace


def test_a_plan_the_kernel_refuses_is_recorded_rather_than_swallowed(
    db: sqlite3.Connection, p8world
) -> None:
    """A declared ``schedule_urgency`` the §5.2 row contradicts is a kernel
    input breach (P7-1 judgement 11): the assembly answers ``Err``, the leg
    records it against the cycle and the turn proceeds — never silently."""

    from tests.phase7.conftest import cost_vector, kernel_row, proposal
    from tests.phase8.conftest import supply_of

    # The declared number and the §5.2 row it must agree with are made to
    # disagree (the row keeps the 0.75 band value).
    bad = supply_of(
        proposal(
            "cand-bad",
            schedule_urgency=0.99,
            schedule_row=kernel_row(urgency=0.75),
            cost=cost_vector(),
        )
    )
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=wiring(p8world, supply=bad)),
        "cm-bad",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 0
    )
    assert not str(
        db.execute("SELECT action_id FROM generation_action_intent").fetchone()[0]
    ).endswith(("-automatic-open", "-teaching-open"))
    status = db.execute(
        "SELECT status, error_code FROM planner_execution_status"
    ).fetchone()
    assert status == ("DEGRADED", "AUTOMATIC_TURN_LEG_UNAVAILABLE")
    trace = db.execute("SELECT factor_trace FROM planner_evaluation").fetchone()[0]
    assert "schedule_urgency" in trace


def test_a_coordinator_without_a_teaching_controller_degrades_before_cp2(
    db: sqlite3.Connection, p8world
) -> None:
    """The unit commits the Moment through the wiring's teaching face and the
    coordinator lands it through its own; an assembly with the second missing
    refuses *before* CP2, so a Moment that can never be delivered cannot
    exist."""

    from elc.persona import PersonaRuntime, PromptCompiler, ResponseValidator
    from elc.runtime.controller import ConversationCoordinator

    runtime = PersonaRuntime(
        actions=p8world.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    coordinator_ = ConversationCoordinator(
        lease=p8world.lease,
        conversation_commands=p8world.store,
        conversation_queries=p8world.store,
        persona=runtime,
        generation_actions=p8world.generation,
        decision_cycles=p8world.generation.decision_cycles,
        learning_controller=p8world.learning,
        teaching=None,
        automatic_teaching=automatic(p8world),
    )
    completion = begin_turn_ok(coordinator_, "cm-no-teaching")
    assert completion.outcome == "REPLIED_FULL"
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 0
    )
    assert not str(
        db.execute("SELECT action_id FROM generation_action_intent").fetchone()[0]
    ).endswith(("-automatic-open", "-teaching-open"))
    assert db.execute(
        "SELECT status, error_code FROM planner_execution_status"
    ).fetchone() == ("DEGRADED", "AUTOMATIC_TURN_LEG_UNAVAILABLE")


# -- ③ injected with the test supply ⇒ the ALLOW chain -----------------------


def test_the_allow_chain_is_five_durable_facts_and_a_real_delivery(
    db: sqlite3.Connection, p8world
) -> None:
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-allow"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert completion.action_id is not None
    assert str(completion.action_id).endswith("automatic-open")
    assert counts(db, *TEACHING_FACT_TABLES) == dict.fromkeys(
        TEACHING_FACT_TABLES, 1
    )
    row = db.execute(
        "SELECT lifecycle_state, presentation_phase, source, focus_target,"
        " target_mode, candidate_id FROM teaching_moment"
    ).fetchone()
    assert row[:3] == ("AWAITING_USER", "INITIAL_PROMPT", "AUTOMATIC")
    assert json.loads(row[3]) == {
        "target_type": "RESOURCE",
        "target_id": str(TARGET_ID),
    }
    assert row[4:] == ("RESOURCE_PRACTICE", "cand-p8-4")
    gate = db.execute("SELECT context, decision FROM gate_decision").fetchone()
    assert gate == ("OPEN", "ALLOW")
    assert db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 1


def test_the_allow_delivers_exactly_one_assistant_turn(
    db: sqlite3.Connection, p8world
) -> None:
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-allow"
    )
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert completion.reply_text is not None
    assert db.execute("SELECT status FROM turn_record").fetchone()[0] == "COMPLETED"


def test_the_allow_writes_the_exposure_event_with_its_moment(
    db: sqlite3.Connection, p8world
) -> None:
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-allow"
    )
    assert completion.ledger_event == "teaching_presented"
    assert completion.ledger_failure is None
    row = db.execute(
        "SELECT event_id, ledger_key, event, moment_id FROM"
        " planning_ledger_event"
    ).fetchone()
    moment_id = db.execute("SELECT moment_id FROM teaching_moment").fetchone()[0]
    assert row == (
        f"ev-ga-{completion.turn_id}-automatic-open",
        str(TARGET_ID),
        "teaching_presented",
        moment_id,
    )
    projection = db.execute(
        "SELECT last_presented_at, teaching_exposure_counts FROM"
        " planning_ledger"
    ).fetchone()
    assert projection is not None and projection[1] == 1


def test_the_allow_stamps_the_cycle_from_what_it_read(
    db: sqlite3.Connection, p8world
) -> None:
    begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-allow"
    )
    row = db.execute(
        "SELECT learning_snapshot_id, evidence_watermark, curriculum_version,"
        " goal_version, schedule_version, policy_version, context_view_version,"
        " relationship_view_version FROM decision_cycle"
    ).fetchone()
    assert row[0] is not None and row[0].startswith("lsnap-")
    assert row[1] == 0
    assert row[2:] == ("curriculum-v1", "gv-p8-4", "sd1", "pv-p8-4", None, None)


def test_without_the_injected_supply_the_same_world_does_not_open(
    db: sqlite3.Connection, p8world
) -> None:
    begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world, supply=False)),
        "cm-real",
    )
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 0
    )
    assert not str(
        db.execute("SELECT action_id FROM generation_action_intent").fetchone()[0]
    ).endswith(("-automatic-open", "-teaching-open"))
    assert count_events(db) == 0


def test_a_live_moment_protects_the_next_turn(
    db: sqlite3.Connection, p8world
) -> None:
    """§13's ``PROTECTED`` and BF-03's ``HARD_PROTECTED_FLOW`` are the same
    fact: with a Moment live, the next ordinary turn's leg does not open a
    second one and the persona answers."""

    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(coordinator_, "cm-allow")
    second = begin_turn_ok(coordinator_, "cm-second")
    assert second.outcome == "REPLIED_FULL"
    assert counts(db, "teaching_moment") == {"teaching_moment": 1}
    assert count_events(db) == 1
    lock = db.execute("SELECT moment_id FROM active_teaching_lock").fetchone()
    assert lock is not None


# -- ④ the crash windows (RA §23) --------------------------------------------


class RefusingPersona:
    """The real persona, with the first ``run_action`` refused (the delivery
    never happened — CP2 already did)."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.refused = False

    def run_action(self, *args, **kwargs):
        if not self.refused:
            self.refused = True
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="injected delivery crash",
                )
            )
        return self.inner.run_action(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class FailingCommands:
    """The real conversation store, with the first ``terminalize_turn``
    refused (the assistant turn is canonical, the turn is not terminal)."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.failed = False

    def terminalize_turn(self, *args, **kwargs):
        if not self.failed:
            self.failed = True
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="injected terminalization crash",
                )
            )
        return self.inner.terminalize_turn(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_cp2_committed_and_the_delivery_lost_continues_the_same_action(
    db: sqlite3.Connection, p8world
) -> None:
    crash = begin_turn(
        build_coordinator(
            p8world,
            automatic=automatic(p8world),
            persona=RefusingPersona(_persona(p8world)),
        ),
        "cm-crash",
    )
    assert isinstance(crash, Err), crash
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("OPENING",)
    assert db.execute(
        "SELECT action_id, status FROM generation_action_intent"
    ).fetchone() == (
        f"ga-{_turn_id(db)}-automatic-open",
        "PREPARED",
    )
    assert count_events(db) == 0
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 0

    resumed = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-crash"
    )
    assert str(resumed.action_id).endswith("automatic-open")
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("AWAITING_USER",)
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM generation_action_intent"
    ).fetchone()[0] == 1
    assert count_events(db) == 1
    assert resumed.ledger_event == "teaching_presented"


class StubGeneration:
    """The real generation store, with the leg's read-back answered differently.

    ``variant`` decides what ``get_action_for_turn`` answers: ``"missing"``
    answers ``Ok(None)`` for every read, ``"err_once"`` answers the turn's
    *first* read (the leg's own) with an ``Err`` and delegates from then on.
    Both are states no shipped writer produces — a torn store, injected the way
    this suite injects the refusing persona and the failing terminalizer — and
    both drive the leg's read-back refusal, the branch this case exists for.
    """

    def __init__(self, inner: object, variant: str) -> None:
        self.inner = inner
        self.variant = variant
        self.reads: list[str] = []

    def get_action_for_turn(self, turn_id):
        self.reads.append(str(turn_id))
        if self.variant == "missing":
            return Ok(None)
        if self.variant == "err_once" and len(self.reads) == 1:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message="the durable action row is gone (injected)",
                )
            )
        return self.inner.get_action_for_turn(turn_id)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_a_read_back_that_answers_no_action_degrades_the_leg(
    db: sqlite3.Connection, p8world
) -> None:
    """The leg's identity refusal, measured (F1: this branch had no example).

    The read-back answers ``Ok(None)`` where the CP2 unit just wrote the
    turn's automatic opening: a torn store, and the state the leg refuses
    rather than inventing an action for. What the refusal leaves, exactly:

    - ① the turn is still an ordinary one — the persona replies, the
      completion names the *ordinary* action (never ``-automatic-open``), and
      both ledger fields are ``None``;
    - the durable Planner half is the **ALLOW's own** (``SUCCEEDED`` /
      ``SELECT`` / ``NORMAL``), not a leg-failure record: the read-back
      refusal happens *after* CP2, so the cycle already carries a status row,
      and P8-0's replay rule refuses the leg-failure re-submission (a
      differing status) — the best-effort write is dropped. The
      ``AUTOMATIC_TURN_LEG_UNAVAILABLE`` shape lands for the failures that
      happen *before* the unit writes (see the kernel-refusal and
      no-teaching-controller cases above);
    - ③ the CP2 half is durable and undelivered: the Moment stays ``OPENING``,
      its lock stays held and the ``ALLOW`` stays the verdict — one assistant
      turn (the ordinary reply), **zero** §20 events, and the CP2 action still
      ``PREPARED``. So "nothing teaching-shaped exists" is *not* this branch's
      shape; what is absent is the delivery, and registering that is the point
      (``elc.runtime.automatic_turn.record_leg_failure`` states the rule).
    """

    stub = StubGeneration(p8world.generation, "missing")
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world), generation=stub),
        "cm-readback",
    )
    # ① the ordinary reply, with the leg's own read as its first read
    assert completion.outcome == "REPLIED_FULL"
    assert TURN_TEXT in (completion.reply_text or "")
    assert not str(completion.action_id).endswith("-automatic-open")
    assert completion.ledger_event is None
    assert completion.ledger_failure is None
    assert stub.reads[0] == str(completion.turn_id)

    # ③ the CP2 half is durable, the delivery never happened
    assert counts(db, *TEACHING_ONLY_TABLES) == dict.fromkeys(
        TEACHING_ONLY_TABLES, 1
    )
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("OPENING",)
    assert db.execute("SELECT decision FROM gate_decision").fetchone() == (
        "ALLOW",
    )
    assert count_events(db) == 0
    assert counts(db, "planning_ledger") == {"planning_ledger": 0}
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert db.execute(
        "SELECT action_id, status FROM generation_action_intent"
        " ORDER BY rowid"
    ).fetchall() == [
        (f"ga-{completion.turn_id}-automatic-open", "PREPARED"),
        (str(completion.action_id), "TERMINAL"),
    ]

    # ② and the leg-failure record is *not* written: the ALLOW's own half stands
    assert db.execute(
        "SELECT status, error_code FROM planner_execution_status"
    ).fetchone() == ("SUCCEEDED", None)
    assert db.execute(
        "SELECT decision FROM planner_decision"
    ).fetchone() == ("SELECT",)
    assert db.execute(
        "SELECT outcome FROM runtime_decision_outcome"
    ).fetchone() == ("NORMAL",)
    assert counts(db, *PLANNER_FACT_TABLES) == dict.fromkeys(
        PLANNER_FACT_TABLES, 1
    )


def test_a_read_back_that_fails_degrades_before_the_ordinary_path_adopts(
    db: sqlite3.Connection, p8world
) -> None:
    """The same refusal with an ``Err`` read-back (the branch's other arm).

    The leg's read answers ``Err`` (the store is torn), the leg records and
    degrades, and the read *then* delegates: the ordinary path's own
    ``get_action_for_turn`` sees the CP2 action row still ``PREPARED`` and
    adopts it as this turn's intent — so the reply lands under the
    ``-automatic-open`` action id while the Moment stays ``OPENING`` and the
    log gains no event. Registered, not endorsed: the durable row then reads
    as though the teaching action had delivered, which is the honest
    consequence of a torn store and the reason the leg refuses to proceed on
    it. The transcript itself is the ordinary reply."""

    stub = StubGeneration(p8world.generation, "err_once")
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world), generation=stub),
        "cm-readback-err",
    )
    assert completion.outcome == "REPLIED_FULL"
    assert TURN_TEXT in (completion.reply_text or "")
    assert str(completion.action_id).endswith("-automatic-open")
    assert completion.ledger_event is None
    assert completion.ledger_failure is None
    assert len(stub.reads) == 2 and stub.reads[0] == str(completion.turn_id)

    assert db.execute(
        "SELECT action_id, status FROM generation_action_intent"
    ).fetchall() == [
        (f"ga-{completion.turn_id}-automatic-open", "TERMINAL"),
    ]
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("OPENING",)
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert count_events(db) == 0
    assert db.execute(
        "SELECT status, error_code FROM planner_execution_status"
    ).fetchone() == ("SUCCEEDED", None)


def test_a_cp3_crash_is_reconciled_and_re_sends_nothing(
    db: sqlite3.Connection, p8world
) -> None:
    """Crash **after CP3** (the assistant turn is canonical, the action is
    TERMINAL, the turn never terminalized): the durable state is ``DELIVERING``
    and the re-entry now **reconciles** it — P9-4 landed exactly the repair this
    test's registry named as the trigger.

    What the cut changed, and what it deliberately did not:

    - the same-epoch re-entry no longer refuses with ``turn re-entry from status
      DELIVERING is outside the Phase 1 loop``. The delivery's own facts decide:
      the assistant turn is canonical (the message really went out), so the turn
      terminalizes ``REPLIED_FULL`` and the §20 event the cut-short leg owed is
      written **once** — the CP3 exposure undercount is closed, and the record
      is the delivery's own word for the action's slot (``teaching_presented``
      for an opening). Nothing is re-sent (one assistant turn) and the Gate is
      not re-run (one ``gate_decision``);
    - the reconciliation lands **no** rung and no opening state: the Moment is
      still ``OPENING`` with its lock held, because the CP2-half landing
      (``OPENING → AWAITING_USER``) is the delivery leg's own caller's move —
      registered in ``_reconcile_delivering_turn``'s docstring, and the residue
      the recovery faces own;
    - a third call with the same ``client_message_id`` is a plain replay of the
      durable terminal result: no new assistant turn, no second event, no
      second terminalization (the reconciliation is idempotent by construction)."""

    commands = FailingCommands(p8world.store)
    first = begin_turn(
        build_coordinator(
            p8world, automatic=automatic(p8world), commands=commands
        ),
        "cm-replay",
    )
    assert isinstance(first, Err), first
    assert commands.failed is True
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert db.execute(
        "SELECT status FROM generation_action_intent"
    ).fetchone() == ("TERMINAL",)
    assert db.execute("SELECT status FROM turn_record").fetchone() == (
        "DELIVERING",
    )
    # The exposure write happens *after* the delivery leg returns, and the leg
    # was cut short by the refusal: nothing was recorded — the gap this repair
    # exists for.
    assert count_events(db) == 0

    second = begin_turn(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-replay"
    )
    assert isinstance(second, Ok), second
    completion = second.value
    assert completion.outcome == "REPLIED_FULL"
    assert completion.ledger_event == "teaching_presented"
    assert completion.ledger_failure is None
    # the reply the reconciliation answers with is the durable transcript's own
    # content, byte for byte (never a re-generated or re-sent one)
    transcript = db.execute("SELECT content FROM assistant_turn").fetchone()
    assert transcript is not None
    assert completion.reply_text == transcript[0]
    assert TURN_TEXT in completion.reply_text
    # exactly one of everything: no second message, no second Gate run, and the
    # §20 event the cut-short leg owed is now durable exactly once
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert count_events(db) == 1
    assert db.execute(
        "SELECT COUNT(*) FROM gate_decision"
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT status, turn_outcome FROM turn_record"
    ).fetchone() == ("COMPLETED", "REPLIED_FULL")
    # no rung landed, and the CP2 half is exactly where the crash left it
    assert db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone() == ("OPENING",)

    third = begin_turn(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-replay"
    )
    assert isinstance(third, Ok), third
    assert third.value.turn_id == completion.turn_id
    assert third.value.ledger_event is None  # this call wrote nothing
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert count_events(db) == 1


def test_one_replay_of_the_delivery_is_not_a_second_fact(
    db: sqlite3.Connection, p8world
) -> None:
    """A duplicate of the *input* replays the durable terminal result and never
    reaches an exposure write at all: CP0 dedupes the message to the original
    turn, so the second call answers from the transcript — nothing is written
    by it. That is **not** the store's replay rule at work: no path re-attempts
    the write after a terminal delivery, and a re-attempt would carry a fresh
    instant, which the store refuses as ``CONFLICT`` rather than replaying
    (``elc.runtime.exposure``; the delivery leg's one re-offering branch is
    unreachable through this loop — see the CP3 case below). Both ledger fields
    are therefore ``None`` for the replay: "this call wrote nothing", never "no
    exposure happened" — the event is a row in the log, not a field here."""

    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    first = begin_turn_ok(coordinator_, "cm-once")
    assert first.ledger_event == "teaching_presented"
    assert count_events(db) == 1

    again = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-once"
    )
    assert again.outcome == "REPLIED_FULL"
    assert again.ledger_event is None
    assert again.ledger_failure is None
    assert count_events(db) == 1
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1


def _persona(p8world) -> object:
    """The real persona the coordinator would build (for the refusing
    wrapper to delegate to after its one refusal)."""

    from elc.persona import (
        PersonaRuntime,
        PromptCompiler,
        ResponseValidator,
    )

    return PersonaRuntime(
        actions=p8world.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )


def _turn_id(db: sqlite3.Connection) -> str:
    return str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
