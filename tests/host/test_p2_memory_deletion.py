"""p-2 — the memory readout and the privacy delete face, over the real web
server and the production assembly.

The BF-05 deletion backend has been ready since Gate 2 (120 tests) with no
UI and no assembly; p-2 wires it into the composition root (additively —
the module is consumed, never modified) and serves two new faces on the
same one-thread work queue as every other route. Pinned here (the six VAL
groups):

1. ``GET /api/memory`` — five panels after a real taught round: the
   learner_states panel is **row-level** (the p-1 I-4 closure — every
   ``learner_target_state`` row with its watermark and the state
   document's key set), evidence is non-empty with counts, the tombstone
   ledger is honestly empty before any deletion, and the whole readout
   writes nothing (a before/after snapshot of every table);
2. ``POST /api/delete`` CONVERSATION end to end — the page's omission of
   ``conversation_id`` names the served conversation, the transcript
   becomes invisible on ``/api/history``, the §24 tombstone is visible in
   the memory readout, the outcome's rebuild attempts carry the full
   chain's wired legs (LEARNER_STATE / SCHEDULE_ITEM, ``ok=True``), and a
   repeat deletion answers the controller's own idempotent note;
3. ``POST /api/delete`` LEARNING_TARGET end to end — the target's
   evidence claims and learner states are gone while the conversation
   transcript survives (SEC-026's shape);
4. the grammar — an unknown or out-of-trio scope word is a 400 人话
   (「此版本不支持该范围」), a key outside the scope's own is a 400, and
   a missing key for a valid scope reaches the controller and comes back
   as its own ``VALIDATION_FAILED`` (200, honestly);
5. the page's safety copy — both confirm layers' exact sentences, the
   irreversibility statement, and the result strip's structure, all
   textContent-only like the rest of the shell;
6. the wiring — ``open_host`` exposes the deletion leg in both tiers
   (fresh-db tombstone ledger reads empty), proven by every e2e above
   running over it; the six pre-existing endpoints are byte-identical by
   the full suite staying green (the additive elif/tuple arms touch no
   existing branch).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import build_content_db
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import Ok
from elc.teaching.rollout import RolloutStage
from tests.host.test_w1_web import (
    ATTEMPT_HIT,
    ERROR_TEXT,
    EV_TARGET,
    _page_source,
    seed_online,
    web_stack,
)

REPLY = "p2 web reply"


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("p2-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def _stack(app_db: Path, content_db: Path, seed: Any = seed_online) -> Any:
    """One online web stack over ``app_db``: pilot artifact, Study-first,
    the D-6-a seed (``seed=None`` for the bare-stack arms)."""

    return web_stack(
        app_db,
        content_db=content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed,
    )


def _teach_one_round(stack: Any) -> dict[str, Any]:
    """One full taught round through the page's own faces: the error text
    opens the automatic moment, the canonical attempt completes it (the
    §4 evaluation, the durable evidence chain), and one ordinary turn
    whose text silently lands a second target's evidence (the P5-2 path —
    "I see." matches the i-see lemma whole-sentence) materializes the
    first ``learner_target_state`` row, so the row-level panel has a real
    row to serve."""

    status, moment = stack.post(
        "/api/teaching_reply",
        {"control": "attempt", "text": ATTEMPT_HIT},
    )
    assert status == 200 and moment["accepted"], moment
    status, turn = stack.post("/api/turn", {"text": "I see."})
    assert status == 200 and turn["turn_status"] == "COMPLETED", turn
    return moment


def _db_rows(path: Path, sql: str, params: tuple[Any, ...] = ()) -> list:
    db = sqlite3.connect(path)
    try:
        return db.execute(sql, params).fetchall()
    finally:
        db.close()


def _snapshot(path: Path) -> list:
    """Every row of every table, as one comparable value (the read-only
    pin's eyes: insert-class and update-class mutations alike move it)."""

    db = sqlite3.connect(path)
    try:
        tables = [
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return [
            (table, db.execute(f"SELECT * FROM {table}").fetchall())
            for table in tables
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. the memory readout — five panels, row-level states, read-only
# ---------------------------------------------------------------------------


def test_the_memory_readout_answers_five_panels_after_a_taught_round(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, turn = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200 and turn["turn_status"] == "COMPLETED", turn
        _teach_one_round(stack)

        status, memory = stack.get_json("/api/memory")
        assert status == 200
        assert set(memory) == {
            "relationship_memory",
            "episode",
            "learner_states",
            "evidence",
            "tombstones",
        }
        for name, panel in memory.items():
            assert isinstance(panel, dict) and "error" not in panel, panel

        # the row-level learner states (the p-1 I-4 closure): the silent
        # turn materialized a real row — watermark and the state document's
        # key set, names never a guessed reading
        states = memory["learner_states"]["states"]
        assert states, states
        assert isinstance(states[0]["evidence_watermark"], int)
        assert states[0]["evidence_watermark"] >= 1
        assert isinstance(states[0]["state_keys"], list)
        assert states[0]["state_keys"], states[0]

        evidence = memory["evidence"]
        assert evidence["evidence_claim_count"] >= 1
        assert evidence["evidence_commit_count"] >= 1
        assert EV_TARGET in {
            claim["target_id"] for claim in evidence["claims"]
        }

        # the honest pre-deletion shape: the §24 ledger is empty, and the
        # two memory panels are honest empties over this persona-less run
        assert memory["tombstones"]["tombstones"] == []
        assert memory["relationship_memory"]["memories"] == []
        assert isinstance(memory["episode"]["episodes"], list)


def test_the_memory_readout_writes_nothing(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with _stack(app_db, pilot_content_db, seed=None) as stack:
        before = _snapshot(app_db)
        for _ in range(2):
            status, _payload = stack.get_json("/api/memory")
            assert status == 200
        assert _snapshot(app_db) == before


# ---------------------------------------------------------------------------
# 2. CONVERSATION deletion, end to end
# ---------------------------------------------------------------------------


def test_conversation_deletion_is_end_to_end_and_idempotent(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with _stack(app_db, pilot_content_db) as stack:
        status, turn = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200 and turn["turn_status"] == "COMPLETED", turn
        _teach_one_round(stack)

        status, history = stack.get_json("/api/history")
        assert status == 200 and history["turns"], history

        # the page sends the bare scope; the face names the conversation
        # it serves (the page never learns its own id)
        status, outcome = stack.post(
            "/api/delete", {"scope": "CONVERSATION"}
        )
        assert status == 200, outcome
        assert outcome["accepted"] is True
        assert outcome["scope"] == "CONVERSATION"
        assert outcome["tombstoned"] >= 1
        assert outcome["tallies"].get("conversation") == 1
        # the rebuild half: the full chain's wired legs answered for the
        # keys the deletion's evidence removal affected (LEARNER_STATE and
        # SCHEDULE_ITEM, both ok — the host wiring pin, through behaviour)
        kinds = {
            (attempt["kind"], attempt["ok"])
            for attempt in outcome["rebuilds"]
        }
        assert ("LEARNER_STATE", True) in kinds, kinds
        assert ("SCHEDULE_ITEM", True) in kinds, kinds

        # the transcript is invisible on the page's own recovery face
        status, history = stack.get_json("/api/history")
        assert status == 200 and history["turns"] == [], history

        # and the deletion is transparent: the §24 ledger says what went
        status, memory = stack.get_json("/api/memory")
        ledger = memory["tombstones"]["tombstones"]
        assert ledger, ledger
        assert any(row["entity_kind"] == "conversation" for row in ledger)
        assert {row["deletion_scope"] for row in ledger} == {
            "CONVERSATION"
        }

        # the durable rows themselves are gone
        assert _db_rows(app_db, "SELECT COUNT(*) FROM conversation") == [
            (0,)
        ]
        assert _db_rows(app_db, "SELECT COUNT(*) FROM teaching_moment") == [
            (0,)
        ]

        # a repeat deletion is the controller's own idempotent answer: no
        # refusal, no new tombstone, the honest "already absent" note
        status, repeat = stack.post("/api/delete", {"scope": "CONVERSATION"})
        assert status == 200
        assert repeat["accepted"] is True
        assert repeat["tombstoned"] == 0
        assert any("already absent" in note for note in repeat["notes"])
        status, memory = stack.get_json("/api/memory")
        assert len(memory["tombstones"]["tombstones"]) == len(ledger)


# ---------------------------------------------------------------------------
# 3. LEARNING_TARGET deletion, end to end
# ---------------------------------------------------------------------------


def test_learning_target_deletion_clears_the_target_and_keeps_the_letters(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with _stack(app_db, pilot_content_db) as stack:
        status, turn = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200 and turn["turn_status"] == "COMPLETED", turn
        _teach_one_round(stack)
        # the preconditions the taught round leaves: the taught target's
        # claim, the silent target's claim, and the silent target's state
        assert _db_rows(
            app_db,
            "SELECT COUNT(*) FROM evidence_claim WHERE target_id = ?",
            (EV_TARGET,),
        ) == [(1,)]
        silent_states = _db_rows(
            app_db, "SELECT COUNT(*) FROM learner_target_state"
        )
        assert silent_states == [(1,)]

        status, outcome = stack.post(
            "/api/delete",
            {"scope": "LEARNING_TARGET", "target_id": EV_TARGET},
        )
        assert status == 200 and outcome["accepted"] is True, outcome
        assert outcome["scope"] == "LEARNING_TARGET"
        assert outcome["tallies"].get("evidence_claim", 0) >= 1

        # the named target's evidence is gone — on the page's own readout,
        # not just in SQL — while the *other* target's learning data and
        # the transcript this evidence came from are untouched (a scope
        # deletes what it names and nothing else)
        status, memory = stack.get_json("/api/memory")
        assert memory["evidence"]["evidence_claim_count"] == 1
        assert EV_TARGET not in {
            claim["target_id"] for claim in memory["evidence"]["claims"]
        }
        assert memory["learner_states"]["states"], memory["learner_states"]
        assert _db_rows(
            app_db,
            "SELECT COUNT(*) FROM evidence_claim WHERE target_id = ?",
            (EV_TARGET,),
        ) == [(0,)]
        assert _db_rows(
            app_db,
            "SELECT COUNT(*) FROM learner_target_state WHERE target_id = ?",
            (EV_TARGET,),
        ) == [(0,)]

        # SEC-026's shape, held by behaviour: the transcript this evidence
        # came from is untouched by a learning-scope deletion
        status, history = stack.get_json("/api/history")
        assert status == 200 and history["turns"], history
        assert _db_rows(app_db, "SELECT COUNT(*) FROM conversation") == [
            (1,)
        ]


# ---------------------------------------------------------------------------
# 4. the delete grammar — three words, one key each, honest refusals
# ---------------------------------------------------------------------------


def test_the_delete_grammar_refuses_what_it_must(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        # a scope word outside the trio — whether junk or another real
        # deletion scope — is the 400 人话, never a silent widening
        for word in ("PERSONA_PACKAGE", "ALL_USER_DATA", "EVERYTHING", 7):
            status, body = stack.post("/api/delete", {"scope": word})
            assert status == 400, (word, body)
            assert "此版本不支持该范围" in body["error"], body
        status, body = stack.post(
            "/api/delete", {"scope": None, "target_id": EV_TARGET}
        )
        assert status == 400 and "此版本不支持该范围" in body["error"]

        # a key outside the scope's own is a 400
        status, body = stack.post(
            "/api/delete",
            {
                "scope": "LEARNING_TARGET",
                "target_id": EV_TARGET,
                "conversation_id": "some-conversation",
            },
        )
        assert status == 400, body
        assert "只接受" in body["error"], body

        # a non-string key value is a 400
        status, body = stack.post(
            "/api/delete", {"scope": "LEARNING_TARGET", "target_id": 42}
        )
        assert status == 400, body

        # a missing key for a valid scope reaches the controller and comes
        # back as its own VALIDATION_FAILED — honest, never an HTTP error
        status, body = stack.post("/api/delete", {"scope": "LEARNING_TARGET"})
        assert status == 200, body
        assert body["accepted"] is False
        assert body["code"] == "VALIDATION_FAILED"
        assert "target_id" in body["message"], body

        # RELATIONSHIP_PAIR is accepted with its own key; on this
        # persona-less database the controller's honest note is the answer
        status, body = stack.post(
            "/api/delete",
            {"scope": "RELATIONSHIP_PAIR", "persona_id": "persona-none"},
        )
        assert status == 200 and body["accepted"] is True, body
        assert any(
            "held no relationship memory" in note for note in body["notes"]
        ), body


# ---------------------------------------------------------------------------
# 5. the page's safety copy — double confirm, irreversibility, result strip
# ---------------------------------------------------------------------------


def test_the_page_carries_the_safety_copy_and_the_result_strip(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        page = _page_source(stack)
        # R-1R 随迁（⑧ 8.2.7 定稿）：「忘掉」语言全页——两层 confirm
        # 逐字（一说范围，二说不可逆），第二层钉在可执行形态（删掉调用
        # 留下散文注释仍红）
        assert (
            "将把「\" + rangeText + \"」请出抽屉，找不回来。确定继续？"
            in page
        )
        assert "再确认一次：忘掉之后无法恢复。" in page
        assert (
            'if (!confirmDialog("再确认一次：忘掉之后无法恢复。")) return;'
            in page
        )
        assert "确定继续？再次确认" not in page
        # the page's standing copy: the two entries' own sentences and
        # the RELATIONSHIP_PAIR face
        # v2-2 随迁（换名句对齐，spec 8.2.7 定稿）：自称主语改「笔友」
        # 主线-1 随迁（DEC-OPI-76a0a10a-….30）：第三面接通——旧自认句
        # 退役（「这版做不了——页面不知道伙伴的角色编号」），按伙伴
        # 关系忘掉接 RELATIONSHIP_PAIR（E2E 钉在 test_mainline1_settings）
        assert "请笔友忘掉一些事——走出去就找不回来。" in page
        assert "忘掉某个表达的学习痕迹、学习状态与复习安排" in page
        assert "这版做不了——页面不知道伙伴的角色编号。" not in page
        assert 'id="del-partner"' in page
        assert "此版本不出这个入口" not in page
        assert "所有删除操作都不可恢复" not in page
        assert "删除这项目标数据" not in page
        assert "忘掉这项的痕迹" in page
        # the two faces and the result strip's read fields（结果只说
        # runtime 自己报的数——存根计数；rebuilds 机件计数不进结果区）
        assert "/api/memory" in page and "/api/delete" in page
        assert 'id="del-result"' in page
        assert "tombstoned" in page
        assert "rebuilds_ok" not in page
        # the result sentences（8.2.7 定稿）and the p-2 F-2 honesty arm:
        # 幂等空删不得声称忘掉
        assert "已忘掉：" in page
        assert "没有什么可忘——它之前就不在抽屉里。" in page
        assert "这次忘掉留下的存根，在 抽屉 · 记忆 里能看到。" in page
        assert "没有可删的" not in page
        # the empty-state family lives on（记忆页空态句保留）
        assert "还没有记住什么" in page
        # textContent-only holds: the shell renders no markup anywhere
        assert "innerHTML" not in page


# ---------------------------------------------------------------------------
# 6. the wiring — the host exposes the deletion leg in both tiers
# ---------------------------------------------------------------------------


def test_open_host_exposes_the_deletion_leg_in_both_tiers(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    provider = ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),))
    full = open_host(
        tmp_path / "full.db",
        provider=provider,  # type: ignore[arg-type]
        content_db_path=pilot_content_db,
    )
    try:
        assert full.deletion is not None
        read = full.deletion.list_tombstones()
        assert isinstance(read, Ok) and read.value == ()
    finally:
        full.close()

    plain = open_host(
        tmp_path / "plain.db", provider=provider  # type: ignore[arg-type]
    )
    try:
        # the prep-1 tier carries the store-and-controller leg too (its
        # rebuild legs are None — the controller's reported-gap posture)
        assert plain.deletion is not None
        read = plain.deletion.list_tombstones()
        assert isinstance(read, Ok) and read.value == ()
    finally:
        plain.close()
