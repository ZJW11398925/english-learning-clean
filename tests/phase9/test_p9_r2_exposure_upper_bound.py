"""P9-R2 — the exposure upper bound: "released but not recorded" (review R2).

The external review's second finding: ``DeliveryExposureFacts`` carried only the
durable half of §17's boundary, so ``exposure_estimate_of`` pinned both
``exposure_level`` and ``max_possible_exposure`` on ``_sent_level`` — and when a
run stopped between the release and the record (the durable prefix empty or
short while the client boundary had already received text) the ceiling read
``NONE`` / ``PARTIAL`` too. That ceiling *understates* what the user may hold,
which is the direction RA §14 forbids (「宁可低估 independence，不高估」;
"confirmed exposure where available, otherwise max-possible-exposure") and
STATE_MACHINES §13 makes the conservative support attribution from. The repair
is ``released_prefix`` (reading 11 of ``elc.runtime.exposure_reconciliation``)
and what this module pins:

1. **the live face passes both boundaries** — ``finalize_streamed_delivery``
   hands ``StreamRun.sent_prefix`` in as ``released_prefix`` beside the durable
   prefix; the call site is pinned by AST and by the rows the chain writes (the
   two real-chain arms below can only pass with that wiring);
2. **the ceiling rises and the level does not** — on the real chain, a delivery
   whose record refused a chunk it had already released writes a §22 estimate
   whose ``max_possible_exposure`` sits strictly above ``exposure_level``, read
   back through a **second** connection (never the writing one);
3. **reading 7 still refuses to confirm it** — an acknowledgment against the
   raised ceiling with nothing durable moves no column and writes no refinement;
4. **nothing else moved** — the transcript is still the durable prefix's
   (verbatim), the two faces that do not hold the released half still read
   ``max == level``, and the refinement face still refuses to move either of the
   two sent-level columns.

Everything here drives the shipped faces: the real migrations into a
file-backed app.db, the real conversation and generation stores, the real §22
record face, the real coordinator. The two refusal shapes reuse the P9-2
``RecordingStore`` spy (every write that is not refused goes to the real
adapter), which is the same spy the P9-2 suite uses for "released, not
recorded".
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from elc.conversation.types import DeliveryState
from elc.platform.db import connection
from elc.platform.types import ActionId, DomainErrorCode, Err, Ok
from elc.runtime.delivery_records import ClientRenderAck
from elc.runtime.exposure_reconciliation import (
    DeliveryExposureFacts,
    exposure_estimate_of,
    exposure_rank,
    refine_with_ack,
)
from elc.runtime.guarded_stream import StreamStep
from tests.conftest import SRC_ROOT
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    RecordingStore,
    ScriptedSource,
    SourceFactory,
    StreamWorld,
    action_of,
    begin_turn_ok,
    coordinator_,
    pieces,
    second_connection_row,
    stream_world,
)

ACKED_AT = "2026-09-25T09:00:00+00:00"

CONTROLLER_PATH = SRC_ROOT / "runtime" / "controller.py"


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


def _estimate_row(world: StreamWorld, action_id: ActionId) -> tuple[object, ...]:
    """The estimate as a **second** connection reads it (never the writer)."""

    second = connection.connect(world.path)
    try:
        row = second.execute(
            "SELECT certainty, exposure_level, max_possible_exposure,"
            " confirmed_exposure, derivation_reason FROM exposure_estimate"
            " WHERE action_id = ?",
            (str(action_id),),
        ).fetchone()
    finally:
        second.close()
    assert row is not None, "no exposure_estimate row for this action"
    return tuple(row)


def _ack(action_id: ActionId, *, seq: int = 1, final: bool = True) -> ClientRenderAck:
    return ClientRenderAck(
        action_id=action_id,
        assistant_turn_id=f"aturn-{action_id}",
        rendered_chunk_seq=seq,
        rendered_text_hash=f"hash-{seq}",
        acked_at=ACKED_AT,
        final_rendered=final,
    )


def _constructed_facts() -> dict[str, dict[str, str]]:
    """Every ``DeliveryExposureFacts`` construction in the controller, keyed by
    the constructor shape (``streamed`` / ``buffered`` / direct), each as
    ``{keyword: unparsed value}``. The call sites **are** the evidence about
    which half each face holds."""

    tree = ast.parse(CONTROLLER_PATH.read_text(encoding="utf-8"))
    found: dict[str, dict[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = {
            keyword.arg: ast.unparse(keyword.value) for keyword in node.keywords
        }
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id == "DeliveryExposureFacts":
                found.setdefault(f"DeliveryExposureFacts.{func.attr}", keywords)
        elif isinstance(func, ast.Name) and func.id == "DeliveryExposureFacts":
            found.setdefault("DeliveryExposureFacts", keywords)
    return found


# -- ① the wiring, at the source and at the signature -------------------------


def test_the_streamed_call_site_passes_both_boundaries() -> None:
    """R7: one live call site, and it names §17's two boundaries — the durable
    prefix (what the record confirmed) and the released prefix (what the client
    boundary received, ``StreamRun``'s own other half). A call site that
    dropped either half would be a face guessing the boundary it holds."""

    calls = _constructed_facts()
    assert calls["DeliveryExposureFacts.streamed"] == {
        "terminal_state": "run.state",
        "sent_prefix": "run.durable_prefix",
        "validated_text": "delivery.text",
        "released_prefix": "run.sent_prefix",
    }
    # and there is exactly one streamed call site: the ordinary turn's
    # finalize face (``finalize_streamed_delivery``)
    tree = ast.parse(CONTROLLER_PATH.read_text(encoding="utf-8"))
    streamed = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "streamed"
    ]
    assert len(streamed) == 1
    source = CONTROLLER_PATH.read_text(encoding="utf-8")
    assert "def finalize_streamed_delivery" in source
    assert source.index("def finalize_streamed_delivery") < source.index(
        "released_prefix=run.sent_prefix"
    )


def test_the_other_two_constructors_do_not_claim_the_released_half() -> None:
    """The buffered face delivers atomically and the recovery face reads the row
    alone: neither holds the released half, so neither passes one — reading
    11's fallback is what they get, and a durable prefix handed in as a release
    would be a claim about a boundary they never saw. Both call sites are pinned
    as they are, and the pin is by shape (a new face fails it and has to
    declare which half it holds)."""

    calls = _constructed_facts()
    assert calls["DeliveryExposureFacts.buffered"] == {
        "text": "delivery.text",
        "state": "delivery.delivery_state",
    }
    assert calls["DeliveryExposureFacts"] == {
        "terminal_state": "row.state",
        "sent_prefix": "row.sent_prefix",
        "send_attempted": "True",
    }
    # the two faces agree with the fallback's own rule, spelled out here so the
    # claim is about behaviour and not only about the call site
    recovered = exposure_estimate_of(
        action_id=ActionId("ga-p9-r2-row-alone"),
        facts=DeliveryExposureFacts(
            terminal_state=DeliveryState.CANCELLED.value,
            sent_prefix="the-prefix-the-row-holds",
            send_attempted=True,
        ),
    )
    assert recovered.max_possible_exposure == recovered.exposure_level == "PARTIAL"
    atomic = exposure_estimate_of(
        action_id=ActionId("ga-p9-r2-buffered"),
        facts=DeliveryExposureFacts.buffered(text="the whole reply"),
    )
    assert atomic.max_possible_exposure == atomic.exposure_level == "FULL"


def test_the_streamed_constructor_requires_the_released_half() -> None:
    """The fail-closed half of the wiring: the streamed face holds both
    boundaries by construction, so a streamed call that could not name the
    released one is refused at the signature rather than silently falling back
    to the durable level (that fallback belongs to the faces that really do not
    hold the half)."""

    parameter = inspect.signature(DeliveryExposureFacts.streamed).parameters[
        "released_prefix"
    ]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        DeliveryExposureFacts.streamed(  # type: ignore[call-arg]
            terminal_state=DeliveryState.SENT_PARTIAL.value,
            sent_prefix="a",
            validated_text="ab",
        )


# -- ② the real chain: released, not recorded ---------------------------------


def test_a_released_but_unrecorded_chunk_raises_only_the_ceiling(
    world: StreamWorld,
) -> None:
    """The review's own shape on the shipped chain. The first chunk **was**
    released (the client boundary received it) and the record face refused its
    write, so the §22 row freezes ``SENT_PARTIAL`` with an empty durable prefix
    — while ``StreamRun`` still reports the release. The estimate now says both
    facts: ``exposure_level`` is the record's ``NONE`` and
    ``max_possible_exposure`` is the released ``PARTIAL``. Before this repair
    the ceiling read ``NONE`` as well (the receipt's probe), which is the
    understated upper bound the review found."""

    first, second = pieces(REPLY, 3)[:2]
    spy = RecordingStore(world.deliveries, refuse_at=2)  # 1 opening, 2 chunk-1
    source = ScriptedSource(
        steps=(StreamStep.chunk(first), StreamStep.chunk(second))
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-r2-released",
    )
    action_id = action_of(world, str(completion.turn_id))

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_PARTIAL", "", 0)
    assert terminal_at is not None  # the row froze, it was not left open
    assert source.emitted == [first]  # released, and its record refused

    row = _estimate_row(world, action_id)
    assert row[:4] == ("SERVER_SENT_UNCONFIRMED", "NONE", "PARTIAL", "NONE")
    assert exposure_rank(str(row[2])) > exposure_rank(str(row[1]))
    assert row[4] == (
        "nothing was sent; partial send; the client boundary may hold more"
        f" than the record shows (released {len(first)} of {len(REPLY)}"
        " chars); no render ack"
    )


def test_a_short_durable_prefix_with_the_whole_release_raises_only_the_ceiling(
    world: StreamWorld,
) -> None:
    """The lagging-record arm: every chunk was released while the record stayed
    one behind (the third chunk's write refused), so the row's durable prefix is
    short of the validated text and the released half covers it — ``PARTIAL``
    level, ``FULL`` ceiling. The transcript stays the durable prefix's verbatim
    (the repair does not touch it), and the ceiling is the only column the
    released half moved."""

    chunks = pieces(REPLY, 3)
    spy = RecordingStore(world.deliveries, refuse_at=4)  # 1 opening, 2-3 chunks 1-2
    source = ScriptedSource(steps=tuple(StreamStep.chunk(p) for p in chunks))
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-r2-lagged",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    durable = "".join(chunks[:2])
    state, prefix, sequence, _, _ = second_connection_row(world, action_id)
    assert (state, prefix, sequence) == ("SENT_PARTIAL", durable, 2)
    assert source.emitted == chunks  # every chunk left for the client
    assert len(prefix) < len(REPLY)

    row = _estimate_row(world, action_id)
    assert row[:4] == ("SERVER_SENT_UNCONFIRMED", "PARTIAL", "FULL", "NONE")
    assert row[4] == (
        f"sent {len(durable)} of {len(REPLY)} chars; partial send; the client"
        " boundary may hold more than the record shows"
        f" (released {len(REPLY)} of {len(REPLY)} chars); no render ack"
    )
    # the transcript is the durable boundary's, byte for byte — the estimate's
    # ceiling is not a claim about the transcript
    transcript = world.db.execute(
        "SELECT content, delivery_state FROM assistant_turn WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert transcript == (durable, "SENT_PARTIAL")


def test_an_ack_against_the_raised_ceiling_still_refines_nothing(
    world: StreamWorld,
) -> None:
    """Reading 7 with the repair in place: the row above has a ``NONE`` level
    and a ``PARTIAL`` ceiling, and a final acknowledgment moves neither the
    certainty nor the confirmation — a raised ceiling is a *possible* exposure,
    not a confirmable one. The acknowledgment itself is durable (the entry is
    the caller's act); the estimate is byte-identical afterwards."""

    first, second = pieces(REPLY, 3)[:2]
    spy = RecordingStore(world.deliveries, refuse_at=2)
    source = ScriptedSource(
        steps=(StreamStep.chunk(first), StreamStep.chunk(second))
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-r2-ack",
    )
    action_id = action_of(world, str(completion.turn_id))
    before = _estimate_row(world, action_id)
    assert before[:4] == ("SERVER_SENT_UNCONFIRMED", "NONE", "PARTIAL", "NONE")

    receipt = coordinator_(world).accept_render_ack(_ack(action_id))
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is False
    assert receipt.value.estimate is not None
    assert receipt.value.note is None
    assert _estimate_row(world, action_id) == before
    assert world.db.execute(
        "SELECT COUNT(*) FROM client_render_ack"
    ).fetchone()[0] == 1


def test_the_refinement_face_still_refuses_to_move_the_raised_ceiling(
    world: StreamWorld,
) -> None:
    """The durable rule read on the repaired row: with ``max_possible_exposure``
    raised to ``FULL``, a submission that moves either sent-level column is
    ``VALIDATION_FAILED`` and the durable row is untouched — the repair widened
    what the derivation writes, not what a refinement may move."""

    chunks = pieces(REPLY, 3)
    spy = RecordingStore(world.deliveries, refuse_at=4)
    source = ScriptedSource(steps=tuple(StreamStep.chunk(p) for p in chunks))
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-r2-refusal",
    )
    action_id = action_of(world, str(completion.turn_id))
    durable = world.deliveries.get_exposure_estimate(action_id)
    assert isinstance(durable, Ok) and durable.value is not None
    estimate = durable.value
    assert (estimate.exposure_level, estimate.max_possible_exposure) == (
        "PARTIAL",
        "FULL",
    )
    row = _estimate_row(world, action_id)

    for illegal in (
        replace(estimate, max_possible_exposure="PARTIAL"),
        replace(estimate, exposure_level="FULL"),
    ):
        refused = world.deliveries.refine_exposure_estimate(illegal)
        assert isinstance(refused, Err), illegal
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED, illegal
        assert _estimate_row(world, action_id) == row

    # the control that keeps the refusals from being vacuous: an acknowledgment
    # on this row moves exactly the two columns it may move — certainty up, and
    # the confirmation up to the **raised** ceiling — while both sent-level
    # columns stay where the derivation put them, and reading 11's fragment
    # survives the tail swap
    refined = refine_with_ack(estimate, ack=_ack(action_id))
    assert refined.certainty == "CONFIRMED_RENDERED"
    assert refined.confirmed_exposure == "FULL"  # the raised ceiling, confirmed
    assert refined.exposure_level == "PARTIAL"
    assert refined.max_possible_exposure == "FULL"
    assert "may hold more" in refined.derivation_reason
    assert "no render ack" not in refined.derivation_reason
    written = world.deliveries.refine_exposure_estimate(refined)
    assert isinstance(written, Ok), written
    assert _estimate_row(world, action_id)[:4] == (
        "CONFIRMED_RENDERED",
        "PARTIAL",
        "FULL",
        "FULL",
    )
