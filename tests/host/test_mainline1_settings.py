"""主线-1 — the settings face: the drawer's third section becomes a real
control surface, over the real web server and the production assembly.

Authorization: ``DEC-OPI-76a0a10a-….30`` (read-all-knob-write) + the slice
``VAL-OPI-76a0a10a-….32`` (five groups) + ``TASK-OPI-76a0a10a-….34``. The
eight-face gap map's A + B① + D faces land here: ``GET /api/settings``
(three faces of live truth — the rollout stage, the §5.1 policy row, the
§5.1 disclosure rules; the 9.12-23① preview item closes), ``POST
/api/settings/teaching_policy`` (the eight-knob whitelist write — the
system columns refuse), the settings section rebuilt around real controls
(8.2.8 reforge②), and the privacy section's RELATIONSHIP_PAIR face (the
"页面不知道伙伴的角色编号" self-deprecation retires — the roster names the
persona now).

Pinned here (the five VAL groups):

1. the settings read — three live faces after a real seed (the stage's
   own enum spelling, the thirteen policy columns, the disclosure rule
   set) plus the two server-declared vocabularies; the honest empties (no
   row → ``null``, stage ``None`` stays ``None``) and the prep-1 tier's
   ``available: false`` with the launch parameter still riding;
2. the knob write — the full eight-knob set upserts (a non-integer seed
   version lands on ``"1"``), the new values read back equal through the
   same GET, the non-knob columns are preserved verbatim (``mode`` /
   ``effective_from`` — no clock invented), an unchanged replay answers
   ``idempotent`` and writes nothing, every refused system column gets
   its own 400 人话 (``mode`` the rollout tier's sentence) and leaves the
   durable row untouched, and the grammar refusals are fail-closed (a
   lowercase or out-of-vocabulary frequency word, a missing knob, a
   whitespace-only or non-string knob, an unknown key, a non-object
   body);
3. the page — the settings section carries the real controls (the stage
   readout slot, the knob editor, the save button, the result strip, the
   disclosure readout), SECTION_PULLS pulls the section (the old
   absence pin's truth migrated), the save loop's re-read closes the
   circuit, the 存面 badge and the stage's raw-value line stand, and the
   two endpoints live only in api.js (the page's only fetch wrappers);
4. the partner-pair deletion end to end — the roster names the served
   card's persona, RELATIONSHIP_PAIR accepts it (accepted + tombstones +
   the pair's tallies + the episode rebuild attempt), the ledger shows
   the opaque stubs, a second pass honestly removed nothing, and the
   conversation scope still works on the same stack;
5. the whitelist's derivation — the eight knobs are exactly the §5.1
   dataclass's writable fields (read from ``elc.user_config.types``, not
   copied), so a column added to the dataclass cannot sneak past the
   whitelist unnoticed.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import build_content_db
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE_ID,
    PENPAL_PERSONA_ID,
)
from elc.platform.types import ConversationId, Ok, PolicyVersion
from elc.teaching.rollout import RolloutStage
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from elc.web import (
    _SETTINGS_KNOBS,
    _SETTINGS_SYSTEM_COLUMNS,
    DEFAULT_WEB_CONVERSATION_ID,
)
from tests.host.test_w1_web import _page_source, web_stack

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "src" / "elc" / "web.py"
API = REPO_ROOT / "src" / "elc" / "webui" / "api.js"


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("m1-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def seed_settings(host: Any) -> None:
    """A §5.1 policy with two non-knob columns to preserve (``mode`` and a
    declared ``effective_from`` — the F-4 rule's real counterpart) and a
    §5.1 disclosure policy with two rules (the default rule plus the
    penpal's own)."""

    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-m1"),
            teaching_frequency=TeachingFrequency.BALANCED,
            mode="focused",
            practice_density="daily",
            effective_from="2026-09-30T08:00:00+00:00",
        )
    )
    assert isinstance(written, Ok), written
    policy = host.user_config.set_disclosure_policy(
        DisclosurePolicy(
            disclosure_policy_id=str(host.user_id),
            revision="dp-seed-1",
            rules=(
                DisclosureRule(
                    persona_id=None,
                    disclosure_level=DisclosureLevel.FUNCTIONAL,
                ),
                DisclosureRule(
                    persona_id=PENPAL_PERSONA_ID,
                    disclosure_level=DisclosureLevel.RICH,
                ),
            ),
        )
    )
    assert isinstance(policy, Ok), policy


def seed_pair(host: Any) -> None:
    """The penpal's envelope, ready to serve: her shipped conversation
    (``web-default`` — the convention the switch honours) bound to her
    persona, one COMPLETED turn (the episode rebuild's anchor), one
    episode row, and two relationship memories in the pair. Direct
    INSERTs on the worker thread (the cs-2 seed's posture)."""

    opened = host.open_conversation(
        ConversationId(DEFAULT_WEB_CONVERSATION_ID),
        persona_id=PENPAL_PERSONA_ID,
    )
    assert isinstance(opened, Ok), opened
    now = datetime.now(tz=UTC).isoformat()
    host.db.execute(
        "INSERT INTO input_envelope (input_id, client_message_id,"
        " conversation_id, persona_id, scene_id, interaction_channel,"
        " raw_payload, received_at) VALUES (?, ?, ?, ?, NULL, ?, ?, ?)",
        (
            "in-m1-turn",
            "msg-m1-turn",
            DEFAULT_WEB_CONVERSATION_ID,
            str(PENPAL_PERSONA_ID),
            "TEXT",
            '{"type":"CONTINUE"}',
            now,
        ),
    )
    host.db.execute(
        "INSERT INTO user_turn (user_turn_id, turn_id, conversation_id,"
        " turn_sequence, message_sequence, input_id, client_message_id,"
        " interaction_channel, raw_content, normalized_content, created_at)"
        " VALUES (?, ?, ?, 1, 1, ?, ?, ?, 'I studied at night.', NULL, ?)",
        (
            "ut-m1-turn",
            "t-m1-turn",
            DEFAULT_WEB_CONVERSATION_ID,
            "in-m1-turn",
            "msg-m1-turn",
            "TEXT",
            now,
        ),
    )
    host.db.execute(
        "INSERT INTO turn_record (turn_id, conversation_id, turn_sequence,"
        " input_id, status, active_decision_cycle_id, failure_class,"
        " failure_reason, runtime_version, started_at, updated_at,"
        " terminal_at, turn_outcome, owner_epoch, state_version)"
        " VALUES (?, ?, 1, ?, 'COMPLETED', NULL, NULL, NULL, ?, ?, ?, ?,"
        " 'REPLIED_FULL', ?, 1)",
        (
            "t-m1-turn",
            DEFAULT_WEB_CONVERSATION_ID,
            "in-m1-turn",
            "m1-test",
            now,
            now,
            now,
            host.fence.current,
        ),
    )
    host.db.execute(
        "INSERT INTO episode (episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ep-m1",
            DEFAULT_WEB_CONVERSATION_ID,
            "1",
            1,
            1,
            "You told her you study at night.",
            '["the nightly study routine"]',
            "[]",
            "ACTIVE",
            now,
        ),
    )
    for memory_id, content in (
        ("rm-m1-active", "The user's name is 明兰."),
        ("rm-m1-second", "The user studies at night."),
    ):
        host.db.execute(
            "INSERT INTO relationship_memory ("
            " relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, status, source_turn_ids,"
            " provenance_refs, recorder_version, sensitivity_class,"
            " persistence_authorization, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                memory_id,
                str(PENPAL_PERSONA_ID),
                "m1-user",
                "USER_STATED_FACT",
                "USER_STATED_FACT",
                content,
                "ACTIVE",
                "[]",
                "[]",
                "m1-seed",
                "PERSONAL",
                "VALIDATED_DOMAIN_WRITE",
                now,
                now,
            ),
        )
    host.db.commit()


def _knob_body(**overrides: Any) -> dict[str, Any]:
    """One full new knob set in grammar — the settings write's body."""

    body: dict[str, Any] = {
        "teaching_frequency": "EAGER",
        "interruption_budget": None,
        "curriculum_initiative": "medium",
        "correction_strictness": None,
        "hint_policy": None,
        "assessment_visibility": None,
        "practice_density": "weekly",
        "persona_freedom": None,
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# group 1 — the settings read: three live faces


def test_the_settings_read_answers_three_live_faces(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_settings,
    ) as stack:
        status, data = stack.get_json("/api/settings")
        assert status == 200, data
        assert data["available"] is True
        # the stage: the startup parameter verbatim, in the enum's own
        # spelling — never a page-side mapping into the three tier names
        assert data["rollout_stage"] == "Study-first"
        # the policy: the thirteen §5.1 columns (``version`` under its
        # declared alias ``policy_version``)
        policy = data["teaching_policy"]
        assert set(policy) == {
            "teaching_policy_profile_id",
            "policy_version",
            "mode",
            "teaching_frequency",
            "interruption_budget",
            "curriculum_initiative",
            "correction_strictness",
            "hint_policy",
            "assessment_visibility",
            "practice_density",
            "persona_freedom",
            "effective_from",
            "updated_at",
        }
        assert policy["teaching_policy_profile_id"] == "user-local-v1"
        assert policy["policy_version"] == "pv-m1"
        assert policy["mode"] == "focused"
        assert policy["teaching_frequency"] == "BALANCED"
        assert policy["practice_density"] == "daily"
        # the F-4 sentinel is a value, carried as the value it is
        assert policy["effective_from"] == "2026-09-30T08:00:00+00:00"
        assert policy["updated_at"] != ""
        for column in (
            "interruption_budget",
            "curriculum_initiative",
            "correction_strictness",
            "hint_policy",
            "assessment_visibility",
            "persona_freedom",
        ):
            assert policy[column] is None, column
        # the disclosure rule set, exactly as it stands
        disclosure = data["disclosure"]
        assert set(disclosure) == {
            "disclosure_policy_id",
            "revision",
            "rules",
            "updated_at",
        }
        assert disclosure["disclosure_policy_id"] == "user-local-v1"
        assert disclosure["rules"] == [
            {"persona_id": None, "disclosure_level": "FUNCTIONAL"},
            {"persona_id": "persona-nell-alder", "disclosure_level": "RICH"},
        ]
        # the two server-declared vocabularies (the page copies no list)
        assert data["frequency_words"] == [
            "OFF", "MINIMAL", "BALANCED", "EAGER",
        ]
        assert data["writable_knobs"] == list(_SETTINGS_KNOBS)


def test_the_empty_read_is_honest(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """No row → ``null``; the stage ``None`` stays ``None`` — the
    fail-closed launch default is a fact about the launch, never a stage
    this face substitutes and never a fabricated policy."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, data = stack.get_json("/api/settings")
        assert status == 200, data
        assert data["available"] is True
        assert data["rollout_stage"] is None
        assert data["teaching_policy"] is None
        assert data["disclosure"] is None
        assert data["frequency_words"] == [
            "OFF", "MINIMAL", "BALANCED", "EAGER",
        ]
        assert data["writable_knobs"] == list(_SETTINGS_KNOBS)


def test_the_prep1_tier_answers_honestly(tmp_path: Path) -> None:
    """A prep-1-tier host: ``available: false`` with the launch parameter
    still riding (the stage is the host's, not the user-config leg's) and
    both rows honestly ``null``; the write answers the dependency's own
    refusal shape."""

    with web_stack(
        tmp_path / "app.db", stage=RolloutStage.LOUNGE
    ) as stack:
        status, data = stack.get_json("/api/settings")
        assert status == 200, data
        assert data["available"] is False
        assert data["rollout_stage"] == "Lounge"
        assert data["teaching_policy"] is None
        assert data["disclosure"] is None
        status, saved = stack.post(
            "/api/settings/teaching_policy", _knob_body()
        )
        assert status == 200, saved
        assert saved["accepted"] is False
        assert saved["code"] == "DEPENDENCY_UNAVAILABLE"


# ---------------------------------------------------------------------------
# group 2 — the knob write: whitelist round trip + refusals


def test_the_knob_write_round_trips_through_the_read(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_settings,
    ) as stack:
        status, saved = stack.post(
            "/api/settings/teaching_policy", _knob_body()
        )
        assert status == 200, saved
        assert saved["accepted"] is True
        assert saved["idempotent"] is False
        # the seed's non-integer version lands on "1" (_next_version's
        # declared scheme)
        assert saved["policy_version"] == "1"
        # 回读相等: the eight knobs read back through the same GET…
        status, data = stack.get_json("/api/settings")
        policy = data["teaching_policy"]
        assert policy["teaching_frequency"] == "EAGER"
        assert policy["curriculum_initiative"] == "medium"
        assert policy["practice_density"] == "weekly"
        for column in (
            "interruption_budget",
            "correction_strictness",
            "hint_policy",
            "assessment_visibility",
            "persona_freedom",
        ):
            assert policy[column] is None, column
        # …and the non-knob columns are preserved verbatim: mode was not
        # written (it is not a knob), effective_from kept the caller's
        # declaration (no clock value invented), the version moved once
        assert policy["mode"] == "focused"
        assert policy["effective_from"] == "2026-09-30T08:00:00+00:00"
        assert policy["policy_version"] == "1"


def test_the_replay_is_idempotent(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_settings,
    ) as stack:
        status, first = stack.post(
            "/api/settings/teaching_policy", _knob_body()
        )
        assert status == 200 and first["accepted"] is True, first
        status, second = stack.post(
            "/api/settings/teaching_policy", _knob_body()
        )
        assert status == 200, second
        assert second["accepted"] is True
        assert second["idempotent"] is True
        assert second["policy_version"] == first["policy_version"]
        # no empty version churn: the read still answers "1"
        status, data = stack.get_json("/api/settings")
        assert data["teaching_policy"]["policy_version"] == "1"


def test_the_system_columns_are_refused(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Every refused §5.1 column gets its own 400 人话 — ``mode`` the
    rollout tier's sentence — and refuses with the durable row untouched.

    The five columns are enumerated **literally** (the §5.1 thirteen
    columns' non-knob remainder, plus ``version``'s alias): looping the
    server's own ``_SETTINGS_SYSTEM_COLUMNS`` tuple here would let a
    mutated whitelist silently shrink this pin with it (the mutant run
    proved exactly that idle spin), so the names stand on their own and
    the derivation pin (group 5) holds the tuple to the dataclass."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_settings,
    ) as stack:
        for key in (
            "mode",
            "teaching_policy_profile_id",
            "version",
            "policy_version",
            "effective_from",
            "updated_at",
        ):
            body = _knob_body()
            body[key] = "smuggled"
            status, answer = stack.post(
                "/api/settings/teaching_policy", body
            )
            assert status == 400, (key, answer)
            if key == "mode":
                assert "mode 是当前档（rollout stage）" in answer["error"]
                assert "换档 = 改启动命令再启动" in answer["error"]
            else:
                assert "系统列" in answer["error"], (key, answer)
                assert key in answer["error"], (key, answer)
        # nothing was written: the durable row still reads pv-m1
        status, data = stack.get_json("/api/settings")
        assert data["teaching_policy"]["policy_version"] == "pv-m1"
        assert data["teaching_policy"]["teaching_frequency"] == "BALANCED"


def test_the_grammar_refusals_are_fail_closed(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_settings,
    ) as stack:
        refusals: list[tuple[Any, str]] = [
            (_knob_body(teaching_frequency="eager"), "EAGER"),
            (_knob_body(teaching_frequency="HOURLY"), "EAGER"),
            (_knob_body(practice_density="   "), "practice_density"),
            (_knob_body(practice_density=7), "practice_density"),
            (
                {
                    key: value
                    for key, value in _knob_body().items()
                    if key != "practice_density"
                },
                "full new knob set",
            ),
            (_knob_body(unexpected="x"), "不认识的键"),
            ("not an object", "eight knobs"),
        ]
        for body, fragment in refusals:
            status, answer = stack.post(
                "/api/settings/teaching_policy", body
            )
            assert status == 400, (body, answer)
            assert fragment in answer["error"], (body, answer)
        # nothing was written by any refused body
        status, data = stack.get_json("/api/settings")
        assert data["teaching_policy"]["policy_version"] == "pv-m1"


def test_the_first_write_from_the_empty_state(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """No row + a full knob set → the first policy (version "1", the F-4
    ``""`` sentinel on ``effective_from``, ``mode`` honestly ``None``)."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, saved = stack.post(
            "/api/settings/teaching_policy", _knob_body()
        )
        assert status == 200, saved
        assert saved["accepted"] is True and saved["idempotent"] is False
        assert saved["policy_version"] == "1"
        status, data = stack.get_json("/api/settings")
        policy = data["teaching_policy"]
        assert policy["teaching_frequency"] == "EAGER"
        assert policy["mode"] is None
        assert policy["effective_from"] == ""
        assert policy["updated_at"] != ""


# ---------------------------------------------------------------------------
# group 3 — the page: real controls, the pull wired, the save loop closed


def _page_of(tmp_path: Path) -> str:
    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


def test_the_settings_section_carries_the_real_controls(tmp_path: Path) -> None:
    index = _page_of(tmp_path)
    settings = index.split('id="drawer-settings"', 1)[1].split(
        'id="del-result"', 1)[0]
    # the two standing truths and the pointing sentence survive the reforge
    assert "这台应用只服务你一个人（127.0.0.1，无账号无密码）。" in settings
    assert "模型端点与模型名由启动命令给定——页面不读取，也不显示。" in settings
    assert "批注频率在 温故 · 方向 里调。" in settings
    # the stage readout: the raw value slot + the read-only law, the old
    # "页面读不到" fail-closed sentence retired by this knife
    assert 'id="settings-stage"' in settings
    assert "当前档：" in settings
    assert "由启动命令给定，这里读得到，但不能改。" in settings
    assert "当前这一档由启动命令给定——页面读不到，也不改它。" not in settings
    assert "换端点或换档 = 改启动命令再启动。" in settings
    # the three-tier reference block survives (PC §3's names and 分寸)
    assert "娱乐 · 关系优先：聊得多，递得少，笔友以听和陪为主。" in settings
    assert "平衡：聊天与练句并行，批注适度。" in settings
    assert "学习优先：练句密度优先，批注递得勤，课程感更明显。" in settings
    # the knob group: the honest legend, the editor, the save, the result
    assert 'id="set-settings-knobs"' in settings
    assert "批注频率有真消费方" in settings
    assert "标「存面」的七钮暂无消费方——先存后用，留空 = 未配置。" in settings
    assert 'id="settings-knobs"' in settings
    assert 'id="settings-save"' in settings
    assert 'id="settings-result"' in settings
    # the disclosure group: the readout + the honest edit-path sentence
    assert 'id="set-settings-disclosure"' in settings
    assert "规则经 profile 编辑，这里只读。" in settings
    assert 'id="settings-disclosure"' in settings


def test_the_settings_pull_and_save_loop_are_wired(tmp_path: Path) -> None:
    app = _page_of(tmp_path)
    # the pull: the section shows its own facts now (the old absence
    # pin's truth migrated — r1_shell asserts the same line)
    assert '"drawer-settings":' in app
    assert 'settingsBox("settings-result").hidden = true;' in app
    assert "loadSettings();" in app
    # the save loop: 读现值 → 改 → POST → 回读刷新
    assert "async function loadSettings()" in app
    assert "policyEditor = editorFromSettings(data);" in app
    assert "await fetchSaveTeachingPolicy(payload);" in app
    assert "await loadSettings();" in app
    # the stage readout is the raw value, None honest — no fabricated
    # mapping from the enum to the three tier names
    assert 'slot.textContent = stage ? String(stage) : "未声明";' in app
    # the 存面 badge rides the seven unconsumed knobs
    assert 'badge.textContent = "存面（暂无消费）";' in app
    # the disclosure readout maps the ladder, unknown words pass through
    assert "DISCLOSURE_CN[word]" in app
    assert "缺省一无所露（fail-closed 缺省）。" in app
    # XSS discipline: the settings block adds no markup sink
    block = app.split("8.2.8 重铸②", 1)[1].split("── R-1: the spaces", 1)[0]
    assert "innerHTML" not in block
    assert "outerHTML" not in block
    assert "insertAdjacentHTML" not in block
    # the endpoints live only in api.js (the page's only fetch wrappers)
    api = API.read_text(encoding="utf-8")
    assert '"/api/settings"' in api
    assert '"/api/settings/teaching_policy"' in api


def test_the_privacy_section_names_the_partner_pair(tmp_path: Path) -> None:
    """The privacy section's third face: the self-deprecation sentence
    retires, the real control takes its place, the pull loads both
    halves."""

    index = _page_of(tmp_path)
    privacy = index.split('id="drawer-privacy"', 1)[1].split(
        'id="del-result"', 1)[0]
    # the self-deprecation sentence retires everywhere on the page
    assert "这版做不了——页面不知道伙伴的角色编号。" not in index
    # the face's own copy: what the scope removes, said before the confirm
    assert "忘掉与这位伙伴的关系记忆（她记住的你们之间的事）——信件本身保留。" \
        in privacy
    assert 'id="del-partner"' in privacy
    app = index
    assert "async function loadDelPartner()" in app
    assert '"drawer-privacy": () => { loadDelTargets(); loadDelPartner(); },' \
        in app
    # the button is JS-built around the discovered persona id (the roster's
    # own field — the page never guesses a referent)
    assert 'button.textContent = "忘掉与这位伙伴的关系记忆";' in app
    assert 'scope: "RELATIONSHIP_PAIR", persona_id: current.persona_id' in app
    # the empty state is honest: no served character, no guessed referent
    assert "还没有正在服务的伙伴——先在案头挑一位笔友。" in app


# ---------------------------------------------------------------------------
# group 4 — the partner-pair deletion end to end


def test_the_partner_pair_forgets_end_to_end(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db, seed=seed_pair
    ) as stack:
        # the page's own discovery path: switch to the penpal's envelope,
        # then the roster names the served card and its persona id
        status, switched = stack.post(
            "/api/characters/switch",
            {"character_id": str(PENPAL_CHARACTER_PACKAGE_ID)},
        )
        assert status == 200 and switched["switched"] is True, switched
        status, roster = stack.get_json("/api/characters")
        assert status == 200, roster
        assert roster["current_character_id"] == str(
            PENPAL_CHARACTER_PACKAGE_ID
        )
        current = next(
            card
            for card in roster["characters"]
            if card["character_id"] == roster["current_character_id"]
        )
        persona_id = current["persona_id"]
        assert persona_id == str(PENPAL_PERSONA_ID)
        # the request the double-confirm face sends: the pair's memories go
        status, deleted = stack.post(
            "/api/delete",
            {"scope": "RELATIONSHIP_PAIR", "persona_id": persona_id},
        )
        assert status == 200 and deleted["accepted"] is True, deleted
        assert deleted["scope"] == "RELATIONSHIP_PAIR"
        # the pair's two memories go; the third row is the pair's EPISODE
        # projection job, released for re-derivation (the store's own §21
        # invalidation: only the *job* row goes, never the episode row)
        assert deleted["tombstoned"] == 3
        assert deleted["tallies"] == {
            "projection_job": 1,
            "relationship_memory": 2,
        }
        # the rebuild leg: the pair's surviving conversation's episode is
        # handed back to the CP4 path (the anchor turn is seeded)
        episode_attempts = [
            attempt
            for attempt in deleted["rebuilds"]
            if attempt["kind"] == "EPISODE"
        ]
        assert episode_attempts, deleted["rebuilds"]
        assert all(
            attempt["key"] == f"episode of {DEFAULT_WEB_CONVERSATION_ID}"
            for attempt in episode_attempts
        )
        # the tombstones: the ledger carries the removed rows as opaque
        # digests (never the deleted body), all scoped RELATIONSHIP_PAIR —
        # the two memory stubs plus the released job's stub
        status, memory = stack.get_json("/api/memory")
        assert status == 200, memory
        tombstones = memory["tombstones"]["tombstones"]
        assert all(
            tombstone["deletion_scope"] == "RELATIONSHIP_PAIR"
            for tombstone in tombstones
        )
        kinds = [tombstone["entity_kind"] for tombstone in tombstones]
        assert kinds.count("relationship_memory") == 2
        assert kinds.count("projection_job") == 1
        # the idempotent-empty honesty: a second pass removed nothing
        status, again = stack.post(
            "/api/delete",
            {"scope": "RELATIONSHIP_PAIR", "persona_id": persona_id},
        )
        assert status == 200 and again["accepted"] is True, again
        assert any(
            "held no relationship memory" in note for note in again["notes"]
        )
        # the conversation scope still works on the same stack (the other
        # two scopes' full weight stays with the p-2 suite)
        status, conversation = stack.post(
            "/api/delete", {"scope": "CONVERSATION"}
        )
        assert status == 200 and conversation["accepted"] is True, conversation


# ---------------------------------------------------------------------------
# group 5 — the whitelist is the dataclass's writable fields


def test_the_whitelist_is_the_dataclass_writable_fields() -> None:
    """The eight knobs read straight off the §5.1 dataclass (the 词表照
    types.py 现读 rule at the column level): a column added to the
    dataclass cannot sneak past the whitelist unnoticed, and the refused
    set is exactly the non-writable remainder plus ``version``'s canonical
    spelling."""

    system = {
        "teaching_policy_profile_id",
        "policy_version",
        "mode",
        "effective_from",
        "updated_at",
    }
    names = [
        field.name for field in dataclasses.fields(TeachingPolicyProfile)
    ]
    assert _SETTINGS_KNOBS == tuple(
        name for name in names if name not in system
    )
    assert set(_SETTINGS_SYSTEM_COLUMNS) == system | {"version"}
