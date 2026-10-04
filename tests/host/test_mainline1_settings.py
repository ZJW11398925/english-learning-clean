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
from elc.host import open_host
from elc.persona.openai_provider import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE_ID,
    PENPAL_PERSONA_ID,
)
from elc.platform.types import (
    ConversationId,
    Ok,
    PolicyVersion,
    SecretRef,
)
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
    """Every refused §5.1 column gets its own 400 人话 and refuses with the
    durable row untouched.

    The five columns are enumerated **literally** (the §5.1 thirteen
    columns' non-knob remainder minus ``mode``, plus ``version``'s alias):
    looping the server's own ``_SETTINGS_SYSTEM_COLUMNS`` tuple here would let a
    mutated whitelist silently shrink this pin with it (the mutant run
    proved exactly that idle spin), so the names stand on their own and
    the derivation pin (group 5) holds the tuple to the dataclass.
    veto-R 随迁：``mode`` 从拒收集除名——它的写面是
    ``/api/settings/mode``（套件后段的行为钉）；落在旋钮写体里的
    ``mode`` 拿未知键句，照 400 照拒（零缝隙）。"""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_settings,
    ) as stack:
        for key in (
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
            assert "系统列" in answer["error"], (key, answer)
            assert key in answer["error"], (key, answer)
        # veto-R：mode 落在旋钮写体里 = 未知键句（写面搬家，不是缝隙）
        body = _knob_body()
        body["mode"] = "smuggled"
        status, answer = stack.post("/api/settings/teaching_policy", body)
        assert status == 400, answer
        assert "不认识的键：mode" in answer["error"]
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
    # provider 刀（用户否决「端点/模型名不让页面直接设」）：旧三句——
    # 「只服务你一人」导语、「如实说」节、「批注频率在温故调」（与设置
    # 节自己的频率墨选矛盾）——全部退役；接任 = 模型与端点真写面。
    assert "这台应用只服务你一个人" not in settings
    assert "<h3>如实说</h3>" not in settings
    assert "由启动命令给定" not in settings
    assert "批注频率在 温故 · 方向 里调。" not in settings
    assert 'id="set-settings-provider"' in settings
    assert "<h3>模型与端点</h3>" in settings
    assert 'id="settings-provider-editor"' in settings
    # veto-R：模式节 = 墨选编辑器 + 分寸句 + 结果行；「由启动命令给定，
    # 这里读得到，但不能改」只读读法及其两句随本刀退役
    assert 'id="set-settings-mode"' in settings
    assert "<h3>教学模式</h3>" in settings
    assert 'id="settings-mode-editor"' in settings
    assert 'id="settings-mode-note"' in settings
    assert 'id="settings-mode-result"' in settings
    assert "由启动命令给定，这里读得到，但不能改。" not in settings
    assert "换端点或换档 = 改启动命令再启动。" not in settings
    # veto-R 统一规格：设置节面板取消 panel-grid 两栏（切到 navdock 为
    # 止——纯设置节 HTML，不混入后续资产）
    settings_html = index.split('id="drawer-settings"', 1)[1].split(
        "<nav id=\"navdock\"", 1)[0]
    assert "panel-grid" not in settings_html
    # the knob group: the honest legend, the editor, the save, the result
    assert 'id="set-settings-knobs"' in settings
    # veto-R：legend 随档位化改写（badge 文本「暂不影响行为」）
    assert "批注频率有真消费方" in settings
    assert "七钮标「暂不影响行为」——先存后用，留空 = 未配置。" in settings
    assert 'id="settings-knobs"' in settings
    assert 'id="settings-save"' in settings
    assert 'id="settings-result"' in settings
    # the disclosure group: the edit face (fr-A — the read-only copy and
    # its "规则经 profile 编辑" sentence retired) + the fail-closed law
    # (veto micro-knife: the「fail-closed 缺省」jargon parenthetical is
    # gone — the plain-Chinese law sentence stays, the engineering word
    # does not surface)
    assert 'id="set-settings-disclosure"' in settings
    assert "规则经 profile 编辑，这里只读。" not in settings
    assert "规则在这里改；没有规则行时，缺省一无所露。" in settings
    assert "fail-closed" not in settings
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
    # the 409 arm has a face too: the conflict branch re-reads and offers
    # the one action that resolves it（评审 LOW-1 补钉——方向页同形分支
    # 有钉先例 test_p3_goal_management:699/test_r1r_blueprint_v2:479）
    assert '"配置已被别处更新，请重读再改"' in app
    assert 'again.addEventListener("click", () => loadSettings());' in app
    # veto-R：模式编辑面 = 墨选（存值枚举词 + 中文档名），换档走
    # fetchSaveMode → 回读刷新；mode 写端点只住在 api.js
    assert "function renderSettingsMode() {" in app
    assert "async function saveMode(word) {" in app
    assert "await fetchSaveMode(word);" in app
    assert "await loadSettings();" in app
    assert 'placeholder: "未声明——自动教学关着",' in app
    # veto-R：七钮档位化（display-layer 词表 + 未配置 null 可选），
    # badge 文本改「暂不影响行为」；自由文本框（留空 = 清除）退役
    assert "const KNOB_TIERS = {" in app
    assert "{ value: null, label: \"未配置\" }," in app
    assert 'badge.textContent = "暂不影响行为";' in app
    assert "未配置（留空 = 清除）" not in app
    # the disclosure readout maps the ladder, unknown words pass through
    assert "DISCLOSURE_CN[word]" in app
    assert "缺省一无所露。" in app
    assert "（fail-closed 缺省）" not in app
    # XSS discipline: the settings block adds no markup sink
    block = app.split("8.2.8 重铸②", 1)[1].split("── R-1: the spaces", 1)[0]
    assert "innerHTML" not in block
    assert "outerHTML" not in block
    assert "insertAdjacentHTML" not in block
    # the endpoints live only in api.js (the page's only fetch wrappers)
    api = API.read_text(encoding="utf-8")
    assert '"/api/settings"' in api
    assert '"/api/settings/teaching_policy"' in api
    # veto-R：mode 写端点同门（页面零直连 fetch）
    assert '"/api/settings/mode"' in api
    # provider 刀（用户否决「端点/模型名不让页面直接设」）：provider 写
    # 端点同门；渲染面 + 保存回路 + 密钥状态行；旧频率封装退役
    assert '"/api/settings/provider"' in api
    assert '"/api/teaching_frequency"' not in api
    assert "function renderSettingsProvider() {" in app
    assert "await fetchSaveProvider(payload);" in app
    # 启动系统刀：密钥也是页面可设面——password 输入、值永不回显
    # （GET 只报 api_key_set）、留空 = 不改
    assert 'keyInput.type = "password";' in app
    assert '"API 密钥——留空 = 不改";' in app
    assert "face.api_key_set" in app
    # 多模型配置档（用户定向）+ 自查七项修：chip = 平级双钮（无嵌套交互
    # 控件——按钮套按钮是无障碍硬伤）、删档过确认窗、catch 因果中立。
    assert "async function activateProviderProfile(id) {" in app
    assert "async function deleteProviderProfile(id, name) {" in app
    assert "async function saveProviderProfileAs(" in app
    assert 'pick.textContent = profile.name + "（" + profile.model + "）";' \
        in app
    assert 'profile.id === face.active_profile' in app
    assert 'cell.className = "profile-chip"' in app
    # 平级双钮结构钉：✕ 是真按钮（可聚焦/键盘可删），不再是 span 套钮
    assert 'const del = document.createElement("button");' in app
    assert 'del.className = "profile-chip-x";' in app
    assert '"btn chip profile-chip"' not in app
    assert 'del.setAttribute("role", "button");' not in app
    # 删档必过确认窗（档内密钥不可再见 = 不可逆面走 confirmDialog 纪律）
    assert 'const yes = await confirmDialog(' in app
    assert "删掉配置档「\" + name + \"」" in app
    # catch 因果中立（换档 ReferenceError 教训）：不再替网络背书——
    # 「连不上服务」这类因果宣称全库缺席
    assert "连不上服务" not in app
    assert "反复出现请报出来" in app
    # 档密钥语义明示（不带钥匙的档激活时沿用当前已存密钥）
    assert "不带密钥的档，激活时沿用当前已保存的密钥" in app
    assert 'saveAs.textContent = "存为配置档";' in app
    assert 'placeholder = "配置档名字' in app
    assert '"/api/settings/provider/profile"' in api
    assert '"/api/settings/provider/profile_activate"' in api
    assert '"/api/settings/provider/profile_delete"' in api
    assert "fetchSaveFrequency" not in app
    assert "renderGoalFrequency" not in app


class _Keychain:
    """One fake SecretSource: one key name, one key value, no IO."""

    def __init__(self, name: str, value: str) -> None:
        self._name = name
        self._value = value

    def resolve(self, ref: Any) -> str | None:
        # SecretRef is a NewType over str — the reference *is* the name
        return self._value if str(ref) == self._name else None


def test_the_provider_face_reads_writes_and_persists(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """provider 刀（用户否决驱动的真写面）：GET 读现值；POST 一键或两键
    ——持久化 + 热换（下一封信即新端点）；重启后页面值覆盖启动参数；
    畸形 URL 是 400 人话；明文非本机端点被拒（复用启动命令的
    EXT-P1-02 规则——页面写不授予第二条更弱的规则）；幂等重放零写。"""

    launch = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="http://127.0.0.1:9/v1",
            model="launch-model",
            secret_ref=SecretRef("OPENAI_API_KEY"),
        ),
        _Keychain("OPENAI_API_KEY", "sk-test"),
    )
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        provider=launch,
    ) as stack:
        # the read: the live pair as opened (api_key_set rides along; the
        # key's value is never in any read face)
        status, face = stack.get_json("/api/settings")
        assert status == 200, face
        assert face["provider"]["base_url"] == "http://127.0.0.1:9/v1"
        assert face["provider"]["model"] == "launch-model"
        assert face["provider"]["api_key_set"] is False
        assert "sk-test" not in str(face)
        # a malformed scheme is the route's 400 人话
        status, refused = stack.post(
            "/api/settings/provider", {"base_url": "ftp://example.com/v1"}
        )
        assert status == 400 and "http(s)" in refused["error"], refused
        # a plaintext non-loopback destination rides the launch rule
        status, insecure = stack.post(
            "/api/settings/provider",
            {"base_url": "http://provider.example.com/v1"},
        )
        assert status == 200 and insecure["accepted"] is False, insecure
        assert "明文 HTTP" in insecure["error"], insecure
        assert face["provider"]["base_url"] == (
            insecure["provider"]["base_url"]
        )   # 拒收 = 零写零换
        # the real write: both keys + the page key, hot swap + persist
        status, moved = stack.post(
            "/api/settings/provider",
            {
                "base_url": "http://127.0.0.1:10/v1",
                "model": "page-model",
                "api_key": "sk-page-key",
            },
        )
        assert (
            status == 200
            and moved["accepted"] is True
            and moved["idempotent"] is False
        ), moved
        assert moved["provider"]["model"] == "page-model", moved
        assert moved["provider"]["api_key_set"] is True, moved
        # the key's value never rides any read face — saved-ness alone
        assert "sk-page-key" not in str(moved)
        status, after = stack.get_json("/api/settings")
        assert after["provider"]["base_url"] == "http://127.0.0.1:10/v1"
        assert after["provider"]["model"] == "page-model"
        assert after["provider"]["api_key_set"] is True
        assert "sk-page-key" not in str(after)
        # the live-object move is what the queued GET above reads (provider_face
        # now touches the store, so the test thread may not call it directly —
        # sqlite3's one-thread rule); persistence is the restart leg below
        # the idempotent replay writes nothing (pair unchanged, key absent)
        status, again = stack.post(
            "/api/settings/provider",
            {"base_url": "http://127.0.0.1:10/v1", "model": "page-model"},
        )
        assert status == 200 and again["idempotent"] is True, again
    # the restart leg: a fresh open over the same app.db serves the saved
    # pair (and the saved key wins over the launch source at send time)
    # even though the launch argument names another
    reopened = open_host(
        tmp_path / "app.db",
        provider=OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url="http://127.0.0.1:9/v1",
                model="launch-model",
                secret_ref=SecretRef("OPENAI_API_KEY"),
            ),
            _Keychain("OPENAI_API_KEY", "sk-test"),
        ),
        content_db_path=pilot_content_db,
    )
    try:
        assert reopened.provider_face() == {
            "base_url": "http://127.0.0.1:10/v1",
            "model": "page-model",
            "api_key_set": True,
        }
        live = reopened.coordinator.persona_provider()
        # the saved key wins at send time: the rebuilt provider's source is
        # the saved-key wrapper over the launch fallback (white-box — the
        # black-box proof is the value never riding any read face)
        from elc.host import _SavedKeySource

        assert isinstance(live.secret_source, _SavedKeySource)
        assert live.secret_source.saved == "sk-page-key"
        assert live.secret_source.fallback.resolve(
            SecretRef("OPENAI_API_KEY")
        ) == "sk-test"
    finally:
        reopened.close()


def test_the_model_profiles_save_switch_and_delete(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """多模型配置档（用户定向：存多套模型随时切换）全生命周期：存两个
    具名档（GET 列表 + 密钥值永不回显，只报 api_key_set）→ 激活 B = 密钥
    先落 + 热换 + pair + 指针（重复激活幂等）→ 手改三件 = 指针归自定义
    → 删现役档不动活配置、指针归 None → 幂等删除。"""

    launch = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="http://127.0.0.1:9/v1",
            model="launch-model",
            secret_ref=SecretRef("OPENAI_API_KEY"),
        ),
        _Keychain("OPENAI_API_KEY", "sk-test"),
    )
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        provider=launch,
    ) as stack:
        # a malformed profile body is the route's 400 人话
        status, bad = stack.post(
            "/api/settings/provider/profile",
            {"name": "本地", "base_url": "ftp://x/v1", "model": "m"},
        )
        assert status == 400 and "http(s)" in bad["error"], bad
        # save two profiles (one with its own key, one without)
        status, prof_a = stack.post(
            "/api/settings/provider/profile",
            {
                "name": "本地推理",
                "base_url": "http://127.0.0.1:10/v1",
                "model": "local-model",
            },
        )
        assert status == 200 and prof_a["accepted"] is True, prof_a
        status, prof_b = stack.post(
            "/api/settings/provider/profile",
            {
                "name": "云端大模型",
                "base_url": "http://127.0.0.1:11/v1",
                "model": "cloud-model",
                "api_key": "sk-cloud",
            },
        )
        assert status == 200 and prof_b["accepted"] is True, prof_b
        id_a, id_b = prof_a["id"], prof_b["id"]
        assert id_a and id_b and id_a != id_b
        # unique names (self-audit item 5): a duplicate name is refused —
        # two chips reading the same name is user-facing ambiguity
        status, dup = stack.post(
            "/api/settings/provider/profile",
            {
                "name": "本地推理",
                "base_url": "http://127.0.0.1:13/v1",
                "model": "another",
            },
        )
        assert status == 200 and dup["accepted"] is False, dup
        assert "同名" in dup["error"], dup
        # the roster rides the settings GET; the key's value never does
        status, face = stack.get_json("/api/settings")
        assert status == 200, face
        roster = {
            p["id"]: p for p in face["provider"]["profiles"]
        }
        assert set(roster) == {id_a, id_b}
        assert roster[id_a]["name"] == "本地推理"
        assert roster[id_a]["api_key_set"] is False
        assert roster[id_b]["api_key_set"] is True
        assert "sk-cloud" not in str(face)
        assert face["provider"]["active_profile"] is None   # 尚未挂档
        # switch to B: key first → hot swap → pair + pointer
        status, switched = stack.post(
            "/api/settings/provider/profile_activate", {"id": id_b}
        )
        assert (
            status == 200
            and switched["accepted"] is True
            and switched["idempotent"] is False
        ), switched
        status, on_b = stack.get_json("/api/settings")
        assert on_b["provider"]["base_url"] == "http://127.0.0.1:11/v1"
        assert on_b["provider"]["model"] == "cloud-model"
        assert on_b["provider"]["active_profile"] == id_b
        # the replay is idempotent (zero writes)
        status, replay = stack.post(
            "/api/settings/provider/profile_activate", {"id": id_b}
        )
        assert status == 200 and replay["idempotent"] is True, replay
        # an unknown id is the honest refusal
        status, ghost = stack.post(
            "/api/settings/provider/profile_activate", {"id": "p-nope"}
        )
        assert status == 200 and ghost["accepted"] is False, ghost
        assert "没有这个配置档" in ghost["error"], ghost
        # manual edits diverge: the pointer returns to custom (None)
        status, manual = stack.post(
            "/api/settings/provider",
            {"base_url": "http://127.0.0.1:12/v1", "model": "hand-tuned"},
        )
        assert status == 200 and manual["accepted"] is True, manual
        status, custom = stack.get_json("/api/settings")
        assert custom["provider"]["model"] == "hand-tuned"
        assert custom["provider"]["active_profile"] is None
        # delete: the live pair stays exactly as it is (a delete never
        # hot-swaps), the row goes, an absent id stays fine (idempotent)
        status, gone = stack.post(
            "/api/settings/provider/profile_delete", {"id": id_b}
        )
        assert status == 200 and gone["accepted"] is True, gone
        status, roster_after = stack.get_json("/api/settings")
        ids_after = [p["id"] for p in roster_after["provider"]["profiles"]]
        assert ids_after == [id_a]
        assert roster_after["provider"]["model"] == "hand-tuned"
        status, again_gone = stack.post(
            "/api/settings/provider/profile_delete", {"id": id_b}
        )
        assert status == 200 and again_gone["accepted"] is True, again_gone


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
    spelling. veto-R 随迁：``mode``（§5.1 行自己的列）不在拒收集——§12
    档位另有自己的门（``/api/settings/mode``），它落在这里就成了未知键
    400，照拒（行为钉同刀）."""

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
    # veto-R：拒绝集 = system − {mode} + version（mode 的写面搬家）
    assert set(_SETTINGS_SYSTEM_COLUMNS) == system - {"mode"} | {"version"}
    assert "mode" not in _SETTINGS_SYSTEM_COLUMNS
