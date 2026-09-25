"""P9-R3 — teaching exposure provenance (the attempt's ``exposure_estimate_id``).

The seam this file closes (external review R3, adopted in
``DEC-OPI-e26b27a7-…44``): ``attempt_record_for`` has always *declared*
``exposure_estimate_id``, and the coordinator's single call site never passed
it, so every attempt claimed "no exposure estimate is attributed to me" while
the §22 rows sat right there. What the id means, and what it must never
mean, is the cut's second half — the two same-named ``FULL`` words:

- ``ExposureEstimate.exposure_level == FULL`` is a **delivery** fact: the
  whole message reached the client;
- ``AttemptRecord.answer_exposure_state == FULL`` is a **ladder** fact: the
  target's answer form was completely shown.

The chains below are the shipped ones over a file-backed app.db — the
automatic teaching opening of the P8-4 world, then real replies through
``respond_to_teaching`` — and every assertion is read back through a
**second connection** (the P9-2 discipline: the writing connection's view is
never the evidence). The estimator numbers are the shipped profile's
(``SUPPORT_FACTOR`` / ``EXPOSURE_FACTOR`` and ``assist = min(support,
exposure)``), run through the public ``estimate_target_state`` face over the
durable claim row, so "the exposure value reaches the assist" is an exact
reading rather than a claim that the chain returned something.

One boundary is pinned as a **registered gap**, not as fixed behaviour:
``evidence_claim.exposure_estimate_id`` is written as a literal ``None`` by
``elc.learning.store``'s claim insert (``EvidenceClaimView`` carries no such
field), and ``src/elc/learning`` is outside this cut's path set. The
provenance therefore reaches the *teaching* proposal — pinned below through
a recorder over the real commit — and stops at the Learning boundary; the
claim-side pin records today's truth so the learning-side cut that lights the
column cannot land silently.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from elc.learning.estimator import (
    EXPOSURE_FACTOR,
    SUPPORT_FACTOR,
    EstimatorClaimView,
    estimate_target_state,
)
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.types import (
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.delivery_records import ClientRenderAck
from elc.runtime.generation import GenerationActionStore
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.evidence import build_evidence_proposal
from elc.teaching.flow import SERVER_SENT_UNCONFIRMED, attempt_record_for
from elc.teaching.ladder import evidence_answer_exposure
from tests.phase7.conftest import DAY_THREE, TARGET_ID
from tests.phase8.p8_4_world import (
    CONV,
    World,
    acceptance_supply,
    build_content,
    wiring,
)
from tests.phase8.p8_4_world import (
    begin_turn_ok as p8_begin_turn_ok,
)
from tests.phase8.p8_4_world import (
    world as p8_world,
)

__all__: list[str] = []

#: The instant every reply below carries (the p8 world's own reply day).
REPLY_AT = DAY_THREE

#: The target the automatic opening teaches (``res-hedge-i-think``): its
#: reveal form is "I think it is going to rain.", so the canonical text below
#: is an exact whole-answer SUCCESS.
FOCUS_TARGET = TARGET_ID
CANONICAL = "I think it is going to rain."
MODALITY = "TEXT_PRODUCTION"

#: The acknowledgment's own instant.
ACKED_AT = "2026-09-24T11:00:00+00:00"

#: ``records=REAL_FACE`` wires the real §22 store; ``records=None`` is the
#: "no face at all" arm (a different fact from a wired face that refuses).
REAL_FACE = object()


# -- the world -----------------------------------------------------------------


@dataclass(frozen=True)
class FileWorld:
    """One file-backed app.db with the P8-4 teaching world and a coordinator.

    ``recorder`` is set only when the caller asked for it: it wraps the real
    Learning controller so the *proposal object* the coordinator hands over
    is observable — the commit itself is the shipped one, unchanged.
    """

    path: Path
    db: sqlite3.Connection
    p8: World
    coordinator: ConversationCoordinator
    recorder: RecordingLearning | None = None


class RecordingLearning:
    """The real Learning controller with ``commit_teaching_evidence``
    recorded (the call still runs; only the observation is added)."""

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.proposals: list[object] = []

    def commit_teaching_evidence(self, proposal: object, **kwargs: object):
        self.proposals.append(proposal)
        return self._inner.commit_teaching_evidence(proposal, **kwargs)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


class RefusingEstimateStore:
    """The real §22 store with ``record_initial_exposure_estimate`` refused
    (the P9-4 spy shape): every other face goes through, so the delivery is
    ordinary and only the estimate row is missing."""

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.calls = 0

    def record_initial_exposure_estimate(self, estimate: object) -> object:
        self.calls += 1
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message="the estimate face refused this write (injected)",
            )
        )

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


def coord_for(
    p8: World, *, learning: object | None = None, records: object = REAL_FACE
) -> ConversationCoordinator:
    """The P8-4 assembly with the §22 face wired (the P9-3/P9-4 shape)."""

    runtime = PersonaRuntime(
        actions=p8.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    if records is REAL_FACE:
        face: object = SqliteDeliveryRecordStore(p8.db, p8.fence)
    else:
        face = records
    return ConversationCoordinator(
        lease=p8.lease,
        conversation_commands=p8.store,
        conversation_queries=p8.store,
        persona=runtime,
        generation_actions=p8.generation,
        decision_cycles=p8.generation.decision_cycles,
        learning_controller=p8.learning if learning is None else learning,  # type: ignore[arg-type]
        teaching=p8.teaching,
        targets=p8.targets,
        automatic_teaching=wiring(p8, supply=acceptance_supply()),
        delivery_records=face,  # type: ignore[arg-type]
    )


def build_world(
    root: Path, *, records: object = REAL_FACE, recorder: bool = False
) -> FileWorld:
    """One real chain over a fresh file-backed app.db (no seeding)."""

    root.mkdir(parents=True, exist_ok=True)
    path = root / "app.db"
    content = build_content(root / "content.db")
    db = connection.connect(path)
    migrations.apply_migrations(db)
    fence = epoch.open_runtime_epoch(db)
    p8 = p8_world(db, fence, content)
    learning: object | None = None
    wrapped: RecordingLearning | None = None
    if recorder:
        wrapped = RecordingLearning(p8.learning)
        learning = wrapped
    coordinator = coord_for(p8, learning=learning, records=records)
    return FileWorld(path=path, db=db, p8=p8, coordinator=coordinator, recorder=wrapped)


# -- the shipped drives --------------------------------------------------------


def reply(
    coordinator: ConversationCoordinator,
    cmid: str,
    intent: TeachingControlIntent,
    text: str | None = None,
):
    """One teaching reply: an attempt when ``text`` is given, a control-only
    envelope otherwise (never a fabricated ABSTAIN attempt)."""

    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=intent,
                attempt_present=text is not None,
                attempt=None if text is None else AttemptPayload(text=text),
            ),
            client_message_id=ClientMessageId(cmid),
            requested_at=REPLY_AT,
        )
    )


def attempt_reply(coordinator: ConversationCoordinator, cmid: str):
    """One attempt reply carrying the target's canonical form."""

    return reply(coordinator, cmid, TeachingControlIntent.CONTINUE, CANONICAL)


def ack(action_id: str, *, seq: int = 1, final: bool = True) -> ClientRenderAck:
    return ClientRenderAck(
        action_id=action_id,  # type: ignore[arg-type]
        assistant_turn_id=f"aturn-{action_id}",
        rendered_chunk_seq=seq,
        rendered_text_hash=f"hash-{seq}",
        acked_at=ACKED_AT,
        final_rendered=final,
    )


def open_then_attempt(fw: FileWorld, *, tag: str = "p9r3") -> None:
    """The chain every group starts from: the automatic opening is delivered
    (CP3a writes its estimate), then the user replies with an attempt."""

    p8_begin_turn_ok(fw.coordinator, f"cmid-{tag}-open")
    result = attempt_reply(fw.coordinator, f"cmid-{tag}-attempt")
    assert isinstance(result, Ok), result


# -- the durable reads (a second connection; never the writer's view) ----------


def rows(
    app_path: Path, sql: str, params: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    second = connection.connect(app_path)
    try:
        return [tuple(row) for row in second.execute(sql, params).fetchall()]
    finally:
        second.close()


def moment_row(fw: FileWorld) -> tuple[object, ...]:
    rows_ = rows(
        fw.path,
        "SELECT moment_id, lifecycle_state, presentation_phase, support_level,"
        " attempt_index FROM teaching_moment",
    )
    assert len(rows_) == 1, rows_
    return rows_[0]


def actions_of(fw: FileWorld, moment_id: str) -> list[tuple[object, ...]]:
    """The moment's actions, spelled out independently of the read face under
    test — the SQL the port's own docstring declares."""

    return rows(
        fw.path,
        "SELECT action_id, action_type FROM generation_action_intent"
        " WHERE moment_id = ? ORDER BY created_at, action_id",
        (moment_id,),
    )


def attempt_row(fw: FileWorld) -> tuple[object, ...]:
    rows_ = rows(
        fw.path,
        "SELECT attempt_id, moment_id, support_level_before_attempt,"
        " answer_exposure_state, exposure_estimate_id,"
        " support_attribution_certainty FROM attempt_record",
    )
    assert len(rows_) == 1, rows_
    return rows_[0]


def estimate_row(fw: FileWorld, action_id: str) -> tuple[object, ...] | None:
    rows_ = rows(
        fw.path,
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure FROM exposure_estimate WHERE action_id = ?",
        (action_id,),
    )
    return None if not rows_ else rows_[0]


def focus_claim(fw: FileWorld) -> tuple[object, ...]:
    rows_ = rows(
        fw.path,
        "SELECT evidence_group_id, created_at, target_type, target_id,"
        " performance_type, polarity, outcome, support_level,"
        " answer_exposure_state, exposure_estimate_id,"
        " evaluator_confidence, evidence_modality FROM evidence_claim"
        " WHERE claim_role = 'FOCUS_TARGET'",
    )
    assert len(rows_) == 1, rows_
    return rows_[0]


def estimator_view(claim: tuple[object, ...]) -> EstimatorClaimView:
    """The durable claim as the estimator sees it (the mapping
    ``elc.learning.store._estimator_view`` documents; spelled here from the
    claim's own columns so the test reads the row, not the code)."""

    return EstimatorClaimView(
        group_id=str(claim[0]),
        timestamp=str(claim[1]),
        performance_type=str(claim[4]),
        polarity=str(claim[5]),
        outcome=str(claim[6]),
        evaluator_confidence=float(claim[10]),
        support_level=str(claim[7]),
        exposure_level=str(claim[8]),
        opportunity_type="ELICITED",
        target_type=str(claim[2]),
        target_id=str(claim[3]),
        modality=str(claim[11]),
    )


def estimate_state(fw: FileWorld) -> tuple[EstimatorClaimView, object]:
    view = estimator_view(focus_claim(fw))
    state = estimate_target_state(
        [view],
        target_type=view.target_type,
        target_id=view.target_id,
        modality=view.modality,
        as_of="2026-09-24T12:00:00+00:00",
    )
    return view, state


def assist_of(view: EstimatorClaimView) -> float:
    """BF-01 §8's ``assist = min(support_factor, exposure_factor)`` over the
    shipped profile constants."""

    return min(
        SUPPORT_FACTOR.get(view.support_level, 1.0),
        EXPOSURE_FACTOR.get(view.exposure_level, 1.0),
    )


def proposal_payload(fw: FileWorld) -> dict[str, object]:
    rows_ = rows(
        fw.path,
        "SELECT payload FROM teaching_evidence_proposal",
    )
    assert len(rows_) == 1, rows_
    return json.loads(str(rows_[0][0]))


# ---------------------------------------------------------------------------
# ① the wiring pin — the attempt names the delivery it is attributed to
# ---------------------------------------------------------------------------


def test_the_attempt_names_the_latest_delivered_actions_estimate(
    tmp_path: Path,
) -> None:
    """Real chain: the opening delivery (its CP3a estimate row is durable)
    then the attempt. The attempt's ``exposure_estimate_id`` is the opening
    action's ``action_id`` — the id the §22 table keys the estimate by — read
    back through a second connection, and not the resume action the closing
    move appends afterwards."""

    fw = build_world(tmp_path / "world")
    open_then_attempt(fw, tag="wire")

    moment_id = str(moment_row(fw)[0])
    actions = actions_of(fw, moment_id)
    attempt = attempt_row(fw)

    assert attempt[1] == moment_id
    opening_id = str(actions[0][0])
    assert attempt[4] == opening_id, (attempt, actions)
    assert estimate_row(fw, opening_id) == (
        "SERVER_SENT_UNCONFIRMED",
        "FULL",
        "FULL",
        "NONE",
    ), "the id must name an estimate row that really exists"
    later = [str(row[0]) for row in actions[1:]]
    assert later and opening_id not in later, (
        "the closing move's resume action is later than the attempt's"
        f" attribution: {actions}"
    )


def test_the_same_provenance_travels_into_the_evidence_proposal(
    tmp_path: Path,
) -> None:
    """The value does not stop at the attempt row: ``_commit_attempt_evidence``
    hands the *same* id to ``build_evidence_proposal``, observed by recording
    the proposal object the real commit received."""

    fw = build_world(tmp_path / "world", recorder=True)
    open_then_attempt(fw, tag="proposal")

    assert fw.recorder is not None
    assert len(fw.recorder.proposals) == 1
    proposal = fw.recorder.proposals[0]
    attempt = attempt_row(fw)
    moment_id = str(moment_row(fw)[0])
    opening_id = str(actions_of(fw, moment_id)[0][0])

    assert proposal.exposure_estimate_id == opening_id  # type: ignore[attr-defined]
    assert proposal.exposure_estimate_id == attempt[4]  # type: ignore[attr-defined]
    assert proposal.support_attribution_certainty == (  # type: ignore[attr-defined]
        SERVER_SENT_UNCONFIRMED.value
    )


def test_the_learning_side_claim_column_stays_null_and_the_gap_is_registered(
    tmp_path: Path,
) -> None:
    """**Registered gap (this cut's 异议/登记).** The durable
    ``evidence_claim.exposure_estimate_id`` column is written as a literal
    ``None`` by ``elc.learning.store``'s claim insert — ``EvidenceClaimView``
    carries no such field, and the whole ``src/elc/learning`` package is
    outside this cut's path set (``VAL-OPI-9dba34fb-…14``). The provenance
    therefore reaches the teaching proposal and stops at the Learning
    boundary; this pin records today's truth so the learning-side cut that
    lights the column must delete this assertion and extend the chain
    instead. Revisit: the first cut that touches the teaching-claim insert or
    ``EvidenceClaimView``.

    The proposal payload is checked too: Learning's own conversion
    (``_claim_document``) carries no such key, so there is no hidden second
    route into the claim row either.
    """

    fw = build_world(tmp_path / "world")
    open_then_attempt(fw, tag="claim-gap")

    claim = focus_claim(fw)
    assert attempt_row(fw)[4] is not None  # the attempt side is live...
    assert claim[9] is None  # ...and the claim side is the registered gap
    documents = proposal_payload(fw)["claims"]
    assert documents and all(
        "exposure_estimate_id" not in document for document in documents  # type: ignore[operator]
    )


# ---------------------------------------------------------------------------
# ② the two FULLs — a delivery fact and a ladder fact
# ---------------------------------------------------------------------------


def test_a_fully_delivered_opening_leaves_the_answer_exposure_at_none(
    tmp_path: Path,
) -> None:
    """Arm (a): the whole opening message was delivered (its estimate is
    ``FULL``) and nothing of the answer form was shown — the attempt's
    answer exposure is ``NONE`` and the estimator takes
    ``EXPOSURE_FACTOR[NONE]`` (1.00), so the assist is carried by the support
    side alone (``CONTEXT_ONLY`` → 0.90) and the mass is the full 0.90."""

    fw = build_world(tmp_path / "world")
    open_then_attempt(fw, tag="delivery-full")

    attempt = attempt_row(fw)
    assert attempt[2] == "CONTEXT_ONLY"
    assert attempt[3] == "NONE"
    moment_id = str(moment_row(fw)[0])
    opening_id = str(actions_of(fw, moment_id)[0][0])
    assert estimate_row(fw, opening_id)[1] == "FULL"  # the delivery was complete

    view, state = estimate_state(fw)
    assert view.exposure_level == "NONE"
    assert EXPOSURE_FACTOR[view.exposure_level] == 1.00
    assert assist_of(view) == pytest.approx(0.90)
    independent = state.dimensions["independent_production"]  # type: ignore[attr-defined]
    assert independent.positive_mass == pytest.approx(0.90)
    assert view.performance_type == "INDEPENDENT_PRODUCTION"


def test_a_reveal_raises_the_answer_exposure_to_full_and_the_factor_falls(
    tmp_path: Path,
) -> None:
    """Arm (b): the same world plus a requested REVEAL. The reveal delivery's
    estimate is ``FULL`` as well (it is a delivery fact), and *because the
    ladder moved* the attempt's answer exposure is ``FULL`` — the estimator
    now takes ``EXPOSURE_FACTOR[FULL]`` (0.15) and the assist collapses to
    ``min(0.10, 0.15) = 0.10``: a post-reveal attempt is imitative, worth
    0.065 / 0.025, not 0.90."""

    fw = build_world(tmp_path / "world")
    p8_begin_turn_ok(fw.coordinator, "cmid-reveal-open")
    asked = reply(fw.coordinator, "cmid-reveal-ask", TeachingControlIntent.ASK_ANSWER)
    assert isinstance(asked, Ok), asked
    assert asked.value.delivery_kind == "REVEAL"
    result = reply(
        fw.coordinator, "cmid-reveal-attempt", TeachingControlIntent.CONTINUE, CANONICAL
    )
    assert isinstance(result, Ok), result

    moment = moment_row(fw)
    assert moment[2] == "POST_REVEAL_OPTIONAL_ATTEMPT"
    assert moment[3] == "FULL_FORM_SHOWN"
    attempt = attempt_row(fw)
    assert attempt[2] == "FULL_FORM_SHOWN"
    assert attempt[3] == "FULL"

    reveal_id = str(actions_of(fw, str(moment[0]))[1][0])
    assert estimate_row(fw, reveal_id)[1] == "FULL"
    assert attempt[4] == reveal_id

    view, state = estimate_state(fw)
    assert view.exposure_level == "FULL"
    assert EXPOSURE_FACTOR[view.exposure_level] == 0.15
    assert assist_of(view) == pytest.approx(0.10)
    assert view.performance_type == "IMITATIVE_PRODUCTION"
    recognition = state.dimensions["recognition"]  # type: ignore[attr-defined]
    guided = state.dimensions["guided_production"]  # type: ignore[attr-defined]
    assert recognition.positive_mass == pytest.approx(0.065)
    assert guided.positive_mass == pytest.approx(0.025)


def test_the_two_full_words_are_a_delivery_and_a_ladder_fact(
    tmp_path: Path,
) -> None:
    """The contrast, side by side: both arms' delivered estimates say ``FULL``
    (the whole message reached the client) and both attempts carry a non-null
    provenance id, yet their ``answer_exposure_state`` — and therefore the
    estimator's factor — differ. One word, two facts; provenance does not
    move the exposure semantics."""

    left = build_world(tmp_path / "delivery-full")
    open_then_attempt(left, tag="contrast-a")

    right = build_world(tmp_path / "ladder-full")
    p8_begin_turn_ok(right.coordinator, "cmid-contrast-b-open")
    asked = reply(
        right.coordinator, "cmid-contrast-b-ask", TeachingControlIntent.ASK_ANSWER
    )
    assert isinstance(asked, Ok), asked
    assert isinstance(
        attempt_reply(right.coordinator, "cmid-contrast-b-attempt"), Ok
    )

    left_attempt, right_attempt = attempt_row(left), attempt_row(right)
    left_view, left_state = estimate_state(left)
    right_view, right_state = estimate_state(right)

    # the delivery side: FULL in both arms
    left_opening = str(actions_of(left, str(moment_row(left)[0]))[0][0])
    right_reveal = str(actions_of(right, str(moment_row(right)[0]))[1][0])
    assert estimate_row(left, left_opening)[1] == "FULL"
    assert estimate_row(right, right_reveal)[1] == "FULL"

    # the provenance side: non-null in both arms
    assert left_attempt[4] == left_opening
    assert right_attempt[4] == right_reveal

    # the answer-exposure side: NONE vs FULL, and the factors follow
    assert left_view.exposure_level == "NONE"
    assert right_view.exposure_level == "FULL"
    assert EXPOSURE_FACTOR[left_view.exposure_level] == 1.00
    assert EXPOSURE_FACTOR[right_view.exposure_level] == 0.15
    assert left_state.dimensions["independent_production"].positive_mass == (  # type: ignore[attr-defined]
        pytest.approx(0.90)
    )
    assert right_state.dimensions["independent_production"].positive_mass == 0.0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ③ a mid-ladder rung, whole chain
# ---------------------------------------------------------------------------


def test_a_mid_ladder_rung_is_the_position_the_attempt_is_attributed_under(
    tmp_path: Path,
) -> None:
    """The opening, a requested HINT (the ladder's first rung,
    ``HINT_SEMANTIC`` / ``SEMANTIC_HINT``), then the attempt: the attempt is
    recorded at the rung the delivery really reached, its provenance names
    the *hint* action (the latest delivery), and the hint's own estimate row
    is ``FULL`` — a full delivery of a partial reveal."""

    fw = build_world(tmp_path / "world")
    p8_begin_turn_ok(fw.coordinator, "cmid-partial-open")
    asked = reply(fw.coordinator, "cmid-partial-ask", TeachingControlIntent.ASK_HINT)
    assert isinstance(asked, Ok), asked
    assert asked.value.delivery_kind == "HINT"
    assert isinstance(attempt_reply(fw.coordinator, "cmid-partial-attempt"), Ok)

    moment = moment_row(fw)
    assert moment[2] == "HINT_SEMANTIC"
    assert moment[3] == "SEMANTIC_HINT"
    attempt = attempt_row(fw)
    assert attempt[2] == "SEMANTIC_HINT"
    assert attempt[3] == "NONE"

    actions = actions_of(fw, str(moment[0]))
    hint_id = str(actions[1][0])
    assert attempt[4] == hint_id
    assert estimate_row(fw, hint_id)[1] == "FULL"


def test_the_mid_rung_assist_is_the_shipped_profiles_min(
    tmp_path: Path,
) -> None:
    """Whole chain with the deterministic assist assertion: Attempt →
    proposal → claim → Estimator → LearnerState. The claim keeps the mid rung
    (``SEMANTIC_HINT``, support factor 0.70) and ``NONE`` exposure (factor
    1.00), so the assist is ``min(0.70, 1.00) = 0.70`` and — a SUCCESS —
    the guided mass is ``1.00 × 1.0 × 1.0 × 0.70 = 0.70`` (recognition
    0.525). The materialized LearnerState row then carries the estimate that
    mass clears the floor with (``0.70 ≥ 0.55`` ⇒ guided production 1.0)."""

    fw = build_world(tmp_path / "world")
    p8_begin_turn_ok(fw.coordinator, "cmid-assist-open")
    assert isinstance(
        reply(fw.coordinator, "cmid-assist-ask", TeachingControlIntent.ASK_HINT), Ok
    )
    assert isinstance(attempt_reply(fw.coordinator, "cmid-assist-attempt"), Ok)

    view, state = estimate_state(fw)
    assert view.support_level == "SEMANTIC_HINT"
    assert SUPPORT_FACTOR[view.support_level] == 0.70
    assert view.exposure_level == "NONE"
    assert assist_of(view) == pytest.approx(0.70)
    guided_mass = state.dimensions["guided_production"]  # type: ignore[attr-defined]
    recognition_mass = state.dimensions["recognition"]  # type: ignore[attr-defined]
    assert guided_mass.positive_mass == pytest.approx(0.70)
    assert recognition_mass.positive_mass == pytest.approx(0.525)

    # LearnerState: the shipped materialization face over the durable claim.
    rebuilt = fw.p8.learning.rebuild_learner_state(TARGET_ID, MODALITY)
    assert isinstance(rebuilt, Ok), rebuilt
    learner_state = fw.p8.learning.get_learner_target_state(TARGET_ID, MODALITY)
    assert isinstance(learner_state, Ok), learner_state
    assert learner_state.value is not None
    guided = learner_state.value.dimensions["guided_production"]
    assert guided.estimate == pytest.approx(1.0), guided
    assert learner_state.value.target_type == "RESOURCE"


# ---------------------------------------------------------------------------
# ④ the port-absent arm
# ---------------------------------------------------------------------------


def test_without_the_section22_face_the_turn_finishes_and_no_provenance_is_recorded(
    tmp_path: Path,
) -> None:
    """``delivery_records=None``: no §22 face, so no estimate row can be
    *confirmed* — the attempt records ``None`` (the honest "not attributed"
    fact), no estimate is written anywhere, and the teaching turn still
    finishes and commits its evidence: a provenance read never blocks."""

    fw = build_world(tmp_path / "world", records=None)
    open_then_attempt(fw, tag="no-face")

    attempt = attempt_row(fw)
    assert attempt[4] is None
    assert attempt[3] == "NONE"
    assert rows(fw.path, "SELECT action_id FROM exposure_estimate") == []
    assert len(rows(fw.path, "SELECT evidence_claim_id FROM evidence_claim")) == 1


def test_an_estimate_write_refusal_leaves_the_attempt_unattributed(
    tmp_path: Path,
) -> None:
    """The row-absent arm: the §22 face is wired but its estimate write was
    refused, so the opening action exists and has **no** estimate row. The
    id must be ``None`` — "the latest action exists" is not enough; the row
    the id would name has to be there. The turn still finished, and the
    delivery really happened (the action row is durable)."""

    fw = build_world(tmp_path / "world")
    refusing = RefusingEstimateStore(
        SqliteDeliveryRecordStore(fw.p8.db, fw.p8.fence)
    )
    coordinator = coord_for(fw.p8, records=refusing)
    p8_begin_turn_ok(coordinator, "cmid-refused-open")
    assert isinstance(attempt_reply(coordinator, "cmid-refused-attempt"), Ok)

    # every delivery of the chain attempted its estimate write and was
    # refused (the opening and the closing move's resume): the refusals are
    # what makes "no row" a real state rather than an unwired face.
    assert refusing.calls >= 1
    assert rows(fw.path, "SELECT action_id FROM exposure_estimate") == []
    attempt = attempt_row(fw)
    assert attempt[4] is None
    moment_id = str(moment_row(fw)[0])
    assert actions_of(fw, moment_id), (
        "the delivery really happened; only its estimate is missing"
    )


# ---------------------------------------------------------------------------
# ⑤ the read face — zero interpretation, declared order
# ---------------------------------------------------------------------------


def test_the_read_face_returns_every_action_of_the_moment_in_declared_order(
    tmp_path: Path,
) -> None:
    """``list_actions_for_moment`` is the moment's whole action set in
    ``(created_at, action_id)`` order: three rows of three distinct
    ``action_type`` words (opening, hint, resume) — no type filter and no
    "most recent" selection at the port — and the tuple the read face returns
    is exactly the SQL the port's docstring declares."""

    fw = build_world(tmp_path / "world")
    p8_begin_turn_ok(fw.coordinator, "cmid-read-open")
    assert isinstance(
        reply(fw.coordinator, "cmid-read-ask", TeachingControlIntent.ASK_HINT), Ok
    )
    assert isinstance(attempt_reply(fw.coordinator, "cmid-read-attempt"), Ok)

    moment_id = str(moment_row(fw)[0])
    result = fw.p8.generation.list_actions_for_moment(moment_id)
    assert isinstance(result, Ok), result
    returned = [
        (str(action.action_id), action.action_type.value)
        for action in result.value
    ]

    assert returned == [(str(row[0]), str(row[1])) for row in actions_of(fw, moment_id)]
    assert len(returned) == 3
    assert {kind for _, kind in returned} == {
        "TEACHING_OPEN",
        "TEACHING_HINT",
        "PERSONA_RESUME",
    }


def test_the_read_face_answers_the_empty_tuple_for_an_unknown_moment(
    tmp_path: Path,
) -> None:
    """An absent moment is a fact, not an error (the port's stated
    posture): the empty tuple, never a refusal."""

    fw = build_world(tmp_path / "world")

    result = fw.p8.generation.list_actions_for_moment("tm-does-not-exist")
    assert isinstance(result, Ok), result
    assert result.value == ()


def test_the_provenance_names_the_delivery_the_attempt_followed_not_the_latest_now(
    tmp_path: Path,
) -> None:
    """The reading the caller owns: "latest" is the latest **at the instant
    the attempt was recorded**. The closing move appends a resume action
    afterwards, so the moment's last action *now* is not what the attempt was
    attributed under — the value is a durable fact about the attempt, not a
    query answered at read time."""

    fw = build_world(tmp_path / "world")
    p8_begin_turn_ok(fw.coordinator, "cmid-latest-open")
    assert isinstance(
        reply(fw.coordinator, "cmid-latest-ask", TeachingControlIntent.ASK_HINT), Ok
    )
    assert isinstance(attempt_reply(fw.coordinator, "cmid-latest-attempt"), Ok)

    actions = actions_of(fw, str(moment_row(fw)[0]))
    hint_id, resume_id = str(actions[1][0]), str(actions[2][0])
    assert attempt_row(fw)[4] == hint_id
    assert attempt_row(fw)[4] != resume_id


def test_the_port_declares_the_zero_interpretation_read(tmp_path: Path) -> None:
    """The read face is part of the port (not a store-only helper), and its
    contract is written where the port states it: the whole action set, no
    ``action_type`` filter, and an empty tuple for an absent moment."""

    fw = build_world(tmp_path / "world")

    assert isinstance(fw.p8.generation, GenerationActionStore)
    assert hasattr(GenerationActionStore, "list_actions_for_moment")
    doc = GenerationActionStore.list_actions_for_moment.__doc__ or ""
    assert "no ``action_type`` filter" in doc
    assert "empty tuple" in doc


# ---------------------------------------------------------------------------
# ⑥ the certainty word — deliberately not linked to the estimate
# ---------------------------------------------------------------------------


def test_an_acknowledged_estimate_does_not_raise_the_attempts_certainty_word(
    tmp_path: Path,
) -> None:
    """The estimate's ``certainty`` column really is ``CONFIRMED_RENDERED``
    (the acknowledgment refined it, the precondition asserted first), and the
    attempt recorded afterwards still says ``SERVER_SENT_UNCONFIRMED`` — the
    attempt's certainty is not the estimate's (R2 review F2's truth: the
    unconditional "有 ACK: 提高 certainty" sentence is about the *estimate*
    row, and reading 7 refuses to raise certainty past the level column).
    The proposal carries the same word."""

    fw = build_world(tmp_path / "world", recorder=True)
    opened = p8_begin_turn_ok(fw.coordinator, "cmid-ack-open")
    opening_id = str(actions_of(fw, str(moment_row(fw)[0]))[0][0])

    receipt = fw.coordinator.accept_render_ack(ack(opening_id))
    assert isinstance(receipt, Ok), receipt
    assert estimate_row(fw, opening_id)[0] == "CONFIRMED_RENDERED"

    result = reply(
        fw.coordinator, "cmid-ack-attempt", TeachingControlIntent.CONTINUE, CANONICAL
    )
    assert isinstance(result, Ok), result

    attempt = attempt_row(fw)
    assert attempt[4] == opening_id
    assert attempt[5] == "SERVER_SENT_UNCONFIRMED"
    assert fw.recorder is not None
    proposal = fw.recorder.proposals[0]
    assert proposal.support_attribution_certainty == SERVER_SENT_UNCONFIRMED.value  # type: ignore[attr-defined]
    assert opened.turn_id  # the opening turn really ran


def test_flow_documents_the_two_same_named_full_words() -> None:
    """The reading is written down where the value is built (P9-R3 C①), so a
    later reader of the column cannot conflate the ladder's FULL with the
    delivery's."""

    doc = attempt_record_for.__doc__ or ""
    assert "WHAT was shown" in doc
    assert "HOW CERTAINLY it reached" in doc
    assert "Delivery FULL never raises answer exposure" in doc


def test_ladder_documents_that_its_full_is_the_other_full() -> None:
    """The ladder's own derivation points at the distinction, so
    ``evidence_answer_exposure``'s FULL cannot be read as the §22 word."""

    doc = evidence_answer_exposure.__doc__ or ""
    assert "the target's answer form was completely exposed" in doc
    assert "the whole delivery message reached the client" in doc


def test_the_certainty_constant_carries_the_unlinked_reading_and_its_revisit() -> None:
    """``SERVER_SENT_UNCONFIRMED`` is the flow constant (not a per-estimate
    lookup) and its non-linkage plus the Revisit are stated on the value the
    attempt stamps."""

    from elc.teaching.types import ExposureEstimateCertainty

    assert SERVER_SENT_UNCONFIRMED is ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED
    doc = attempt_record_for.__doc__ or ""
    assert "linked to the estimate" in doc
    assert "Revisit" in doc


def test_the_evidence_proposal_face_keeps_the_parameter_defaulted_to_none() -> None:
    """``build_evidence_proposal``'s parameter is optional on purpose: the
    producers that have no §22 fact (unit arms, fixtures) keep today's None,
    and only the coordinator resolves a real id — so this cut cannot make the
    parameter mandatory for assemblies that predate it."""

    import inspect

    signature = inspect.signature(build_evidence_proposal)
    parameter = signature.parameters["exposure_estimate_id"]
    assert parameter.default is None
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
