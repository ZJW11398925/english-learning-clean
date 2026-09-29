"""p-3 — the goal-management face: the 目标 screen's read and its two
writes, over the real web server and the production assembly.

The user-config controller has held the §5.1 goal/policy faces since Phase 6
with no UI; p-3 serves them (additively — the module's existing route arms
keep their exact lines). Pinned here (the seven VAL groups):

1. ``GET /api/goals`` — the whole read in one payload after a real seed:
   the portfolio's eight columns (§5.1 verbatim, the F-4 ``""`` sentinel
   carried as the value it is), the policy's version + frequency + its
   eight unpinned columns raw (``None`` = 未配置), the taxonomy reference
   block with its non-stored marker sentence, and ``session_focus: null``
   when none exists;
2. the honest empty shape — a full-chain host that never wrote answers
   ``portfolio: null`` (and the first write starts at version ``"1"`` with
   the F-4 sentinel, the scheme :func:`elc.web._next_version` declares);
3. the no-leg refusal — a prep-1-tier host (no user-config controller)
   answers ``available: false`` on the read and the delete face's
   ``DEPENDENCY_UNAVAILABLE`` shape on both writes, never a fabricated
   save;
4. W1 happy — the full new combination upserts as the next version (a
   non-integer seed version lands on ``"1"``, the next write is ``"2"``),
   the change reads back through the same GET, and ``effective_from`` is
   preserved (no clock value invented);
5. W1 replay — the same body twice: the second answers ``idempotent``
   and no new version is written;
6. W1 CONFLICT — a same-version-different-content write (the race the
   store refuses, forced through the declared ``_next_version`` seam)
   rides HTTP 409 with 「配置已被别处更新，请重读再改」 and the durable row
   stays intact;
7. the grammar — every out-of-vocabulary word (modality, assessment,
   register, weight keys), every non-number weight and every missing piece
   is a 400 人话, fail-closed;
8. W2 happy — the single ``teaching_frequency`` column moves while the
   eight unpinned columns rebuild **verbatim** (the seeded ``mode`` /
   ``practice_density`` survive, the ``None``s stay ``None``), the version
   moves once, and an unchanged replay answers idempotent;
9. W2 grammar + conflict — a word outside the four (or a lowercase one —
   the enum's words are case-sensitive) is a 400; the forced race is 409;
10. the word lists — every taxonomy face's words equal the canonical §4
    block parsed from ``docs/PRODUCT_CONTRACT.md`` word for word, the
    three non-stored faces say so, and the frequency words are the
    implementation-declared enum's own;
11. the XSS face — a hostile description round-trips the store verbatim
    and the served page renders it inert (no ``innerHTML`` anywhere in the
    shell union);
12. the shell — the fifth screen's section, its brand-bar entry, the
    remove-goal copy, both endpoint call sites and the two new components
    are in the served union;
13. the session-focus note — a real §5.1 focus row for the served
    conversation shows up as the payload's note with its own columns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import elc.web
from elc.content.build import build_content_db
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.platform.types import (
    GoalId,
    GoalModality,
    GoalVersion,
    Ok,
    PolicyVersion,
)
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from tests.host.test_w1_web import CONV, _page_source, web_stack

REPO_ROOT = Path(__file__).resolve().parents[2]
@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("p3-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def seed_p3(host: Any) -> None:
    """p-3's own seed: a two-goal portfolio under a **non-integer** version
    string (the seed writers' shape — the W1 scheme lands its first write
    on ``"1"``) and a policy carrying two unpinned columns, so the W2
    rebuild's verbatim promise has something real to preserve."""

    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-p3"),
            teaching_frequency=TeachingFrequency.BALANCED,
            mode="focused",
            practice_density="daily",
        )
    )
    assert isinstance(written, Ok), written
    portfolio = host.user_config.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=host.user_id,
            goal_version=GoalVersion("gv-p3"),
            goals=(
                LearningGoal(
                    goal_id=GoalId("goal-p3-one"),
                    goal_modality=GoalModality.SPEAKING,
                    description="hold a conversation every day",
                ),
                LearningGoal(
                    goal_id=GoalId("goal-p3-two"),
                    goal_modality=GoalModality.READING,
                    description="read one article a day",
                ),
            ),
            modality_weights={
                GoalModality.SPEAKING: 1.0,
                GoalModality.READING: 0.5,
            },
            assessment_targets=("CET6",),
            register_style_goals=("CASUAL",),
            effective_from="",
        )
    )
    assert isinstance(portfolio, Ok), portfolio


def seed_p3_with_focus(host: Any) -> None:
    """``seed_p3`` plus one real §5.1 focus row for the conversation this
    face serves — the note the payload carries when one exists."""

    seed_p3(host)
    focus = host.user_config.set_session_focus(
        SessionFocus(
            session_focus_id="focus-p3",
            conversation_id=CONV,
            base_goal_portfolio_version=GoalVersion("gv-p3"),
            temporary_goal_weights={GoalModality.SPEAKING: 2.0},
            starts_at="2026-09-29T08:00:00+00:00",
            expires_at=None,
        )
    )
    assert isinstance(focus, Ok), focus


def _stack(app_db: Path, content_db: Path, seed: Any = seed_p3) -> Any:
    """One full-chain web stack over ``app_db`` (the goals faces need the
    content tier only because that is where the user-config leg is wired)."""

    return web_stack(app_db, content_db=content_db, seed=seed)


def _combination(**overrides: Any) -> dict[str, Any]:
    """One full new combination in grammar — the W1 request body."""

    body: dict[str, Any] = {
        "goals": [
            {
                "goal_id": "goal-p3-a",
                "goal_modality": "SPEAKING",
                "description": "everyday conversation",
            }
        ],
        "modality_weights": {"SPEAKING": 1.5},
        "assessment_targets": ["CET4"],
        "register_style_goals": ["CASUAL"],
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# 1. the read — the whole payload after a real seed
# ---------------------------------------------------------------------------


def test_the_goals_readout_answers_the_full_shape_after_a_seed(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, goals = stack.get_json("/api/goals")
        assert status == 200
        assert goals["available"] is True

        portfolio = goals["portfolio"]
        assert set(portfolio) == {
            "goal_version",
            "goals",
            "modality_weights",
            "assessment_targets",
            "register_style_goals",
            "effective_from",
            "updated_at",
        }
        assert portfolio["goal_version"] == "gv-p3"
        assert portfolio["goals"] == [
            {
                "goal_id": "goal-p3-one",
                "goal_modality": "SPEAKING",
                "description": "hold a conversation every day",
            },
            {
                "goal_id": "goal-p3-two",
                "goal_modality": "READING",
                "description": "read one article a day",
            },
        ]
        assert portfolio["modality_weights"] == {
            "SPEAKING": 1.0,
            "READING": 0.5,
        }
        assert portfolio["assessment_targets"] == ["CET6"]
        assert portfolio["register_style_goals"] == ["CASUAL"]
        # the F-4 sentinel is a value, carried as the value it is
        assert portfolio["effective_from"] == ""
        assert portfolio["updated_at"] != ""

        policy = goals["policy"]
        assert set(policy) == {
            "policy_version",
            "teaching_frequency",
            "mode",
            "interruption_budget",
            "curriculum_initiative",
            "correction_strictness",
            "hint_policy",
            "assessment_visibility",
            "practice_density",
            "persona_freedom",
        }
        assert policy["policy_version"] == "pv-p3"
        assert policy["teaching_frequency"] == "BALANCED"
        assert policy["mode"] == "focused"
        assert policy["practice_density"] == "daily"
        for column in (
            "interruption_budget",
            "curriculum_initiative",
            "correction_strictness",
            "hint_policy",
            "assessment_visibility",
            "persona_freedom",
        ):
            assert policy[column] is None, column

        assert goals["session_focus"] is None
        assert (
            goals["taxonomy"]["non_stored_note"]
            == "canonical 词表参考 · V1 无存储位"
        )


# ---------------------------------------------------------------------------
# 2. the honest empty shape + the first write's disclosed scheme
# ---------------------------------------------------------------------------


def test_the_readout_is_honest_when_nothing_is_written(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db, seed=None) as stack:
        status, goals = stack.get_json("/api/goals")
        assert status == 200 and goals["available"] is True
        assert goals["portfolio"] is None
        assert goals["policy"] is None
        assert goals["session_focus"] is None

        # the first write starts at "1" (the scheme _next_version declares)
        # and leaves effective_from at the F-4 sentinel — no clock value is
        # invented for a declaration the user never made
        status, saved = stack.post("/api/goals", _combination())
        assert status == 200 and saved["accepted"] is True, saved
        assert saved["idempotent"] is False
        assert saved["goal_version"] == "1"
        status, goals = stack.get_json("/api/goals")
        assert goals["portfolio"]["goal_version"] == "1"
        assert goals["portfolio"]["effective_from"] == ""
        assert goals["portfolio"]["updated_at"] != ""


# ---------------------------------------------------------------------------
# 3. the no-leg refusal — the prep-1 tier
# ---------------------------------------------------------------------------


def test_the_goal_faces_refuse_honestly_without_the_user_config_leg(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, goals = stack.get_json("/api/goals")
        assert status == 200
        assert goals["available"] is False
        assert goals["portfolio"] is None
        assert goals["policy"] is None
        assert goals["session_focus"] is None

        status, saved = stack.post("/api/goals", _combination())
        assert status == 200 and saved["accepted"] is False, saved
        assert saved["code"] == "DEPENDENCY_UNAVAILABLE"
        status, saved = stack.post(
            "/api/teaching_frequency", {"teaching_frequency": "EAGER"}
        )
        assert status == 200 and saved["accepted"] is False, saved
        assert saved["code"] == "DEPENDENCY_UNAVAILABLE"


# ---------------------------------------------------------------------------
# 4./5./6. W1 — happy, replay, conflict
# ---------------------------------------------------------------------------


def test_w1_upsert_moves_the_version_and_the_change_reads_back(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, saved = stack.post("/api/goals", _combination())
        assert status == 200 and saved["accepted"] is True, saved
        # the seed's version is the non-integer "gv-p3" → the first web
        # write lands on "1" (the scheme's disclosed rule)
        assert saved["goal_version"] == "1"

        status, goals = stack.get_json("/api/goals")
        portfolio = goals["portfolio"]
        assert portfolio["goal_version"] == "1"
        assert portfolio["goals"] == [
            {
                "goal_id": "goal-p3-a",
                "goal_modality": "SPEAKING",
                "description": "everyday conversation",
            }
        ]
        assert portfolio["modality_weights"] == {"SPEAKING": 1.5}
        assert portfolio["assessment_targets"] == ["CET4"]
        assert portfolio["register_style_goals"] == ["CASUAL"]
        # effective_from is the caller's declaration, preserved — the
        # seed's sentinel survives the version move
        assert portfolio["effective_from"] == ""

        status, saved = stack.post(
            "/api/goals",
            _combination(
                goals=[
                    {
                        "goal_id": "goal-p3-a",
                        "goal_modality": "WRITING",
                        "description": "one entry a day",
                    }
                ]
            ),
        )
        assert status == 200 and saved["accepted"] is True, saved
        assert saved["goal_version"] == "2"
        status, goals = stack.get_json("/api/goals")
        portfolio = goals["portfolio"]
        assert portfolio["goal_version"] == "2"
        assert portfolio["goals"][0]["goal_modality"] == "WRITING"
        assert portfolio["goals"][0]["description"] == "one entry a day"


def test_w1_replay_is_idempotent_and_writes_no_new_version(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, first = stack.post("/api/goals", _combination())
        assert status == 200 and first["accepted"] is True, first
        assert first["idempotent"] is False

        status, second = stack.post("/api/goals", _combination())
        assert status == 200 and second["accepted"] is True, second
        assert second["idempotent"] is True
        assert second["goal_version"] == first["goal_version"]

        status, goals = stack.get_json("/api/goals")
        assert goals["portfolio"]["goal_version"] == "1"


def test_w1_conflict_surfaces_as_409_and_the_row_survives(
    tmp_path: Path,
    pilot_content_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, _saved = stack.post("/api/goals", _combination())
        assert status == 200

        # force the race the store refuses: the face's own version scheme
        # is pinned to answer the current version, so the write below
        # carries a version the row already holds with different content
        monkeypatch.setattr(
            elc.web,
            "_next_version",
            lambda current: current if current else "1",
        )
        status, refused = stack.post(
            "/api/goals",
            _combination(
                goals=[
                    {
                        "goal_id": "goal-p3-b",
                        "goal_modality": "WRITING",
                        "description": "a different combination",
                    }
                ]
            ),
        )
        assert status == 409, refused
        assert refused["accepted"] is False and refused["conflict"] is True
        assert "配置已被别处更新" in refused["error"], refused

        # the durable row is intact, and the honest next move works
        status, goals = stack.get_json("/api/goals")
        assert goals["portfolio"]["goal_version"] == "1"
        monkeypatch.undo()
        status, saved = stack.post(
            "/api/goals",
            _combination(
                goals=[
                    {
                        "goal_id": "goal-p3-b",
                        "goal_modality": "WRITING",
                        "description": "a different combination",
                    }
                ]
            ),
        )
        assert status == 200 and saved["accepted"] is True, saved
        assert saved["goal_version"] == "2"


# ---------------------------------------------------------------------------
# 7. the grammar — fail-closed, 400 人话
# ---------------------------------------------------------------------------


def test_w1_grammar_and_vocabulary_refusals_are_fail_closed(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        bad_bodies = [
            # a missing piece: the body is the full combination
            {key: value for key, value in _combination().items()
             if key != "register_style_goals"},
            # out-of-vocabulary words, one arm each
            _combination(goals=[{
                "goal_id": "g", "goal_modality": "SINGING",
                "description": "d",
            }]),
            _combination(assessment_targets=["GAOKAO"]),
            _combination(register_style_goals=["SARCASTIC"]),
            _combination(modality_weights={"THINKING": 1.0}),
            # not a number
            _combination(modality_weights={"SPEAKING": "high"}),
            # not a shape
            _combination(goals="two goals"),
            _combination(goals=[{"goal_id": "g", "description": "d"}]),
            _combination(goals=[{
                "goal_id": "", "goal_modality": "SPEAKING",
                "description": "d",
            }]),
            _combination(goals=[{
                "goal_id": "g", "goal_modality": "SPEAKING",
                "description": "   ",
            }]),
        ]
        for body in bad_bodies:
            status, refused = stack.post("/api/goals", body)
            assert status == 400, (body, refused)
            assert refused["error"], (body, refused)


def test_w1_refuses_non_finite_weights_even_though_json_allows_them(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    # p-3 disposition (review F-2): json.dumps(float("nan")) emits the bare
    # NaN literal and Python's json.loads accepts it back — the write face
    # must refuse non-finite weights fail-closed, or one hand-crafted POST
    # poisons the GET payload for every JSON.parse reader.
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        for bad in (float("nan"), float("inf"), float("-inf")):
            status, refused = stack.post(
                "/api/goals",
                _combination(modality_weights={"SPEAKING": bad}),
            )
            assert status == 400, (bad, refused)
            assert "finite" in refused["error"], (bad, refused)


# ---------------------------------------------------------------------------
# 8./9. W2 — the single column, verbatim rebuild, grammar, conflict
# ---------------------------------------------------------------------------


def test_w2_moves_the_column_and_rebuilds_the_rest_verbatim(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, saved = stack.post(
            "/api/teaching_frequency", {"teaching_frequency": "EAGER"}
        )
        assert status == 200 and saved["accepted"] is True, saved
        # the seed's version is the non-integer "pv-p3" → "1"
        assert saved["policy_version"] == "1"

        status, goals = stack.get_json("/api/goals")
        policy = goals["policy"]
        assert policy["teaching_frequency"] == "EAGER"
        assert policy["policy_version"] == "1"
        # the eight unpinned columns rebuilt verbatim: the seeded values
        # survive, the Nones stay None — zero invented values
        assert policy["mode"] == "focused"
        assert policy["practice_density"] == "daily"
        for column in (
            "interruption_budget",
            "curriculum_initiative",
            "correction_strictness",
            "hint_policy",
            "assessment_visibility",
            "persona_freedom",
        ):
            assert policy[column] is None, column

        # the unchanged replay answers idempotent, no new version
        status, again = stack.post(
            "/api/teaching_frequency", {"teaching_frequency": "EAGER"}
        )
        assert status == 200 and again["accepted"] is True, again
        assert again["idempotent"] is True
        assert again["policy_version"] == "1"


def test_w2_grammar_refuses_and_the_race_is_409(
    tmp_path: Path,
    pilot_content_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        for word in ("CHATTY", "off", "Balanced", None, 7):
            status, refused = stack.post(
                "/api/teaching_frequency", {"teaching_frequency": word}
            )
            assert status == 400, (word, refused)
            assert refused["error"], (word, refused)

        monkeypatch.setattr(
            elc.web,
            "_next_version",
            lambda current: current if current else "1",
        )
        status, refused = stack.post(
            "/api/teaching_frequency", {"teaching_frequency": "MINIMAL"}
        )
        assert status == 409, refused
        assert refused["conflict"] is True
        assert "配置已被别处更新" in refused["error"], refused
        status, goals = stack.get_json("/api/goals")
        assert goals["policy"]["teaching_frequency"] == "BALANCED"


# ---------------------------------------------------------------------------
# 10. the word lists — canonical §4 verbatim, parsed from the document
# ---------------------------------------------------------------------------


def _canonical_words(section: str) -> list[str]:
    """The words of one §4 ```text block, read from the canonical document
    itself (the pin compares the served lists with the source, not with a
    copy of it in this test)."""

    text = (REPO_ROOT / "docs" / "PRODUCT_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    start = text.index(f"### {section} ")
    fence = text.index("```text", start)
    end = text.index("```", fence + 7)
    return [
        line.strip()
        for line in text[fence + 7 : end].strip().splitlines()
        if line.strip()
    ]


def test_the_word_lists_are_the_canonical_words_verbatim(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, goals = stack.get_json("/api/goals")
        assert status == 200
        faces = {
            face["name"]: face for face in goals["taxonomy"]["faces"]
        }
        assert faces["goal_modality"]["words"] == _canonical_words("4.3")
        assert faces["external_assessment"]["words"] == (
            _canonical_words("4.5")
        )
        assert faces["register_style"]["words"] == _canonical_words("4.6")
        assert faces["context_domain"]["words"] == _canonical_words("4.1")
        assert faces["genre_discourse"]["words"] == _canonical_words("4.2")
        assert faces["expressive_depth"]["words"] == _canonical_words("4.4")

        # the storage truth: three faces are the editor's pickers, three
        # are reference only (V1 无存储位), never editable
        for name in ("goal_modality", "external_assessment",
                     "register_style"):
            assert faces[name]["stored"] is True, name
        for name in ("context_domain", "genre_discourse",
                     "expressive_depth"):
            assert faces[name]["stored"] is False, name
        assert (
            goals["taxonomy"]["non_stored_note"]
            == "canonical 词表参考 · V1 无存储位"
        )

        # the frequency picker's words are the implementation-declared
        # enum's own (not canonical — the enum's docstring says so)
        assert goals["taxonomy"]["teaching_frequency"]["words"] == [
            word.value for word in TeachingFrequency
        ] == ["OFF", "MINIMAL", "BALANCED", "EAGER"]


# ---------------------------------------------------------------------------
# 11. the XSS face — hostile text round-trips stored and renders inert
# ---------------------------------------------------------------------------


def test_the_hostile_description_round_trips_and_renders_inert(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    hostile = "<img src=x onerror=alert(1)>"
    with _stack(tmp_path / "app.db", pilot_content_db) as stack:
        status, saved = stack.post(
            "/api/goals",
            _combination(
                goals=[
                    {
                        "goal_id": "goal-xss",
                        "goal_modality": "WRITING",
                        "description": hostile,
                    }
                ]
            ),
        )
        assert status == 200 and saved["accepted"] is True, saved

        # the server stores what the user wrote — no invented sanitizing
        status, goals = stack.get_json("/api/goals")
        assert goals["portfolio"]["goals"][0]["description"] == hostile

        # the page renders it inert: no markup path anywhere in the shell
        page = _page_source(stack)
        assert "innerHTML" not in page
        assert "document.write" not in page


# ---------------------------------------------------------------------------
# 12. the shell — the fifth screen's wiring, in the served union
# ---------------------------------------------------------------------------


def test_the_goal_screen_is_wired_into_the_shell(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        page = _page_source(stack)
        # R-1 随迁：目标屏迁入**学案空间 · 目标节**——旧屏 id 与 toggle
        # 退役（缺位钉），节面板与刷新读数原 id 保留
        assert 'id="screen-goal"' not in page
        assert 'id="goal-toggle"' not in page
        assert 'id="study-goal"' in page
        assert 'id="tab-study-goal"' in page
        assert 'id="goal-refresh"' in page
        # the remove-goal copy says what it really is: a version move,
        # not an /api/delete-grade irreversible deletion. The p-3
        # disposition (review F-1) retired the false kept-history promise
        # — the store overwrites the single portfolio row — so the honest
        # copy is pinned present and both retired sentences pinned absent.
        assert "从当前组合移除（保存后生效）" in page
        assert "历史版本保留" not in page
        assert "旧版本保留" not in page
        # both endpoint call sites and the save actions
        assert "/api/goals" in page
        assert "/api/teaching_frequency" in page
        assert "fetchSaveGoals" in page and "fetchSaveFrequency" in page
        assert "保存组合" in page and "保存频率" in page
        assert "重新读取" in page
        # the two new components' factories and their single CSS source
        assert "fieldRow" in page and "chip(" in page
        assert ".field {" in page and ".chip--on" in page


# ---------------------------------------------------------------------------
# 13. the session-focus note — a real §5.1 row, carried when it exists
# ---------------------------------------------------------------------------


def test_the_session_focus_note_appears_when_one_exists(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with _stack(tmp_path / "app.db", pilot_content_db,
                seed=seed_p3_with_focus) as stack:
        status, goals = stack.get_json("/api/goals")
        assert status == 200
        focus = goals["session_focus"]
        assert focus is not None
        assert focus["session_focus_id"] == "focus-p3"
        assert focus["conversation_id"] == str(CONV)
        assert focus["base_goal_portfolio_version"] == "gv-p3"
        assert focus["temporary_goal_weights"] == {"SPEAKING": 2.0}
        assert focus["manual_focus_target"] is None
        assert focus["expires_at"] is None
