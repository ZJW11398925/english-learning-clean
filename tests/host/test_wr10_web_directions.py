"""wr-10 — the direction channel's web half, over the production
assembly (DEC-OPI-c73dbff3…64).

The same shape as the W-1/wr-2 suites: the real ``elc.web.run_web``
over the real ``open_host`` (the builtin Berrymoor package binds at
open), reached with ``urllib`` over the loopback. The pin groups:

1. **the mode write** — ``POST /api/settings/world_direction_mode``
   takes one whitelisted word (``directed`` / ``immersive``), persists
   it, and the settings read face carries the word and its whitelist
   (the default is ``immersive`` = the pre-wr-10 behavior; a word
   outside the two is the 400 grammar sentence);
2. **the choice write** — ``POST /api/world/direction`` parks the
   ``{"label", "hint"}`` candidate under the bound world's key (a
   later choice overwrites the earlier one), the empty body clears it,
   a conversation bound to no world is the 404, and the malformed
   bodies are 400 人话;
3. **the directed turn end to end** — mode directed, the world frame
   carries the narrator's candidates; a choice made between turns
   rides the **next** world step's prompt (the director's input — the
   direction channel, never a letter) and is consumed on success
   (选了即用即清 — the pending row is gone);
4. **拒收不清** — a narrator refusal leaves the parked choice parked
   (the world never heard it, so it stays);
5. **the zero-change default** — immersive (no row, or the explicit
   word) renders no ``directions`` key even when a dishonest answer
   carries one, and the prompt carries no requirement line;
6. **the page** — the option row's renderer, the two fetchers and the
   settings third knob ride the served sources (textContent, zero
   scroll hijack).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.host.test_w1_web import CLEAN_TEXT, web_stack
from tests.host.test_wr2_post_turn_wiring import (
    NARRATOR_MARK,
    BeatsProvider,
)

REPO = Path(__file__).resolve().parents[2]

#: The world the web start binds (the builtin Berrymoor package).
WORLD_ID = "world-berrymoor"

#: The pending-choice key's prefix (the per-world key shape).
_PENDING_PREFIX = "world_pending_direction:"

#: The directed answer the scripted double serves: the beats batch plus
#: the narrator's own candidates (three — a legal middle count).
_CANDIDATES = (
    {"label": "a storm rolls in", "hint": "The harbour braces for weather."},
    {"label": "the fair arrives", "hint": "Tents dot the cliff meadow."},
    {
        "label": "the keeper travels",
        "hint": "The lighthouse goes dark for a night.",
    },
)
DIRECTED_BEATS = json.dumps(
    {
        "beats": [
            {
                "kind": "quiet-morning",
                "narration": "The harbour kept its silence through the morning.",
                "days": 0,
            },
            {
                "kind": "keeper-visitor",
                "narration": "A stranger walked the cliff path to the keeper's door.",
                "days": 2,
            },
        ],
        "directions": list(_CANDIDATES),
        # lr-1：单步即停形（模型一步 letter_arrives）。
        "stop": {"kind": "letter_arrives"},
    }
)

#: The broken answer (a beats-shaped refusal): the whole batch dies.
_REFUSING_BEATS = json.dumps(
    {"beats": [{"kind": "BAD KIND", "narration": "Refused.", "days": 0}]}
)


def _pending_rows(app_db: Path) -> list[tuple[str, str]]:
    """The pending-direction rows off the serving database (the w13 ro
    posture)."""

    from tests.host.test_w13_web import _ro_rows

    return [
        (str(key), str(value))
        for key, value in _ro_rows(
            app_db,
            "SELECT key, value FROM app_setting"
            f" WHERE key LIKE '{_PENDING_PREFIX}%' ORDER BY key",
        )
    ]


def _narrator_prompts(provider: BeatsProvider) -> list[str]:
    """The narrator's prompts only (the reply dials share the double)."""

    return [
        prompt for prompt in provider.prompts if NARRATOR_MARK in prompt
    ]


# ---------------------------------------------------------------------------
# 1 — the mode write and the read face
# ---------------------------------------------------------------------------


def test_the_mode_write_persists_and_the_read_face_rides_it(
    tmp_path: Path,
) -> None:
    """The mode write: one whitelisted word persisted, the settings
    read carrying the word and its whitelist; the default is
    ``immersive`` (an absent row answers the default and writes
    nothing); a word outside the two is the 400 grammar sentence."""

    with web_stack(tmp_path / "app.db") as stack:
        status, face = stack.get_json("/api/settings")
        assert status == 200
        assert face["world_direction_mode"] == "immersive"
        assert face["world_direction_mode_words"] == [
            "directed",
            "immersive",
        ]
        status, saved = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "directed"},
        )
        assert status == 200
        assert saved["accepted"] is True
        status, face = stack.get_json("/api/settings")
        assert status == 200
        assert face["world_direction_mode"] == "directed"
        status, refused = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "god"},
        )
        assert status == 400
        assert "directed | immersive" in refused["error"]
        status, cleared = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "immersive"},
        )
        assert status == 200
        assert cleared["accepted"] is True


# ---------------------------------------------------------------------------
# 2 — the choice write (park, overwrite, clear, refuse)
# ---------------------------------------------------------------------------


def test_the_direction_choice_parks_overwrites_and_clears(
    tmp_path: Path,
) -> None:
    """The choice write: the candidate parks under the bound world's
    key (strict JSON), a later choice overwrites the earlier one (one
    row, the newest word), the empty body clears it, and the malformed
    bodies are the 400 grammar sentence."""

    with web_stack(tmp_path / "app.db") as stack:
        status, saved = stack.post(
            "/api/world/direction",
            {"label": "the fair arrives", "hint": "Tents dot the meadow."},
        )
        assert status == 200
        assert saved == {
            "accepted": True,
            "cleared": False,
            "error": None,
        }
        # lr-3（DEC-OPI-17b0a47f…7）随迁（增强向）：新写行带诚实的
        # ``source`` 标记——候选形是 "candidate"（自由文本形是 "free"，
        # 由 test_lr3_free_direction.py 钉）。
        rows = _pending_rows(tmp_path / "app.db")
        assert rows == [
            (
                _PENDING_PREFIX + WORLD_ID,
                json.dumps(
                    {
                        "label": "the fair arrives",
                        "hint": "Tents dot the meadow.",
                        "source": "candidate",
                    },
                    ensure_ascii=False,
                ),
            )
        ]
        status, overwritten = stack.post(
            "/api/world/direction",
            {"label": "a storm rolls in", "hint": "Weather braces the harbour."},
        )
        assert status == 200
        rows = _pending_rows(tmp_path / "app.db")
        assert len(rows) == 1
        assert json.loads(rows[0][1])["label"] == "a storm rolls in"
        status, cleared = stack.post("/api/world/direction", {})
        assert status == 200
        assert cleared["cleared"] is True
        assert _pending_rows(tmp_path / "app.db") == []
        for body in (
            {"label": "no hint"},
            {"label": " ", "hint": "blank label"},
            {"label": "extra", "hint": "fine", "mood": "wistful"},
            {"label": "x" * 81, "hint": "over the label cap"},
            "not an object",
        ):
            status, refused = stack.post("/api/world/direction", body)
            assert status == 400, body
            assert "label" in refused["error"]


def test_the_direction_choice_404s_without_a_binding() -> None:
    """A conversation outside any world has no direction channel: the
    honest 404 (the inbox's own two-word answer), never a parked row."""

    from elc.web import _WebFace

    class _NoWorldHost:
        app_db_path = "stub.db"

    face = _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]
    status, payload = face.world_direction_save(
        {"label": "the fair arrives", "hint": "Tents dot the meadow."}
    )
    assert status == 404
    assert "没有绑定任何世界" in payload["error"]


# ---------------------------------------------------------------------------
# 3 — the directed turn, end to end
# ---------------------------------------------------------------------------


def test_the_directed_turn_carries_the_candidates(
    tmp_path: Path,
) -> None:
    """Mode directed + an answer carrying candidates ⇒ the world frame
    renders them; the pre-choice frame's candidates ride no prompt
    section (nothing chosen yet)."""

    provider = BeatsProvider(beats_json=DIRECTED_BEATS)
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        status, _ = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "directed"},
        )
        assert status == 200
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        frame = turn["world"]
        assert frame["directions"] == [
            {"label": c["label"], "hint": c["hint"]} for c in _CANDIDATES
        ]
        assert [note["narration"] for note in frame["notes"]]
        # No choice had been made: the narrator's prompt asked for
        # candidates but carried no chosen-direction section.
        prompt = _narrator_prompts(provider)[0]
        assert "The user has chosen where the world goes next:" not in prompt


def test_the_choice_rides_the_next_prompt_and_is_consumed(
    tmp_path: Path,
) -> None:
    """The full directed loop: a choice made between turns rides the
    **next** world step's prompt (label — hint, the director's input),
    the world moves, and the pending row is consumed (选了即用即清) —
    the next-next step's prompt carries no chosen section unless a new
    choice parks one."""

    provider = BeatsProvider(beats_json=DIRECTED_BEATS)
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        status, _ = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "directed"},
        )
        assert status == 200
        status, _ = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        status, saved = stack.post(
            "/api/world/direction",
            {
                "label": "the fair arrives",
                "hint": "Tents dot the cliff meadow.",
            },
        )
        assert status == 200
        assert len(_pending_rows(app_db)) == 1
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert "directions" in turn["world"]
        prompts = _narrator_prompts(provider)
        assert len(prompts) == 2
        assert (
            "The user has chosen where the world goes next:"
            " the fair arrives — Tents dot the cliff meadow." in prompts[1]
        )
        assert "The world moves in this direction." in prompts[1]
        # Consumed: the row is gone the moment the step succeeded.
        assert _pending_rows(app_db) == []
        # WR-4 stands with the director's input riding: the letter's
        # own words are in neither narrator prompt.
        for prompt in prompts:
            assert "The meeting starts at nine." not in prompt


def test_a_refused_step_leaves_the_choice_parked(tmp_path: Path) -> None:
    """拒收不清: a narrator refusal costs the reply nothing, writes no
    world frame, and leaves the parked choice parked — the world never
    heard it, so it waits for the next step."""

    provider = BeatsProvider(beats_json=_REFUSING_BEATS)
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        status, _ = stack.post(
            "/api/settings/world_direction_mode",
            {"world_direction_mode": "directed"},
        )
        assert status == 200
        status, saved = stack.post(
            "/api/world/direction",
            {
                "label": "the fair arrives",
                "hint": "Tents dot the cliff meadow.",
            },
        )
        assert status == 200
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == provider.reply_text
        assert "world" not in turn
        rows = _pending_rows(app_db)
        assert len(rows) == 1
        assert json.loads(rows[0][1])["label"] == "the fair arrives"


# ---------------------------------------------------------------------------
# 4 — the zero-change default (immersive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("set_mode", (False, True))
def test_immersive_never_renders_directions(
    tmp_path: Path, set_mode: bool
) -> None:
    """The zero-change default holds against a dishonest answer: with
    no mode row (the launch default) or the explicit ``immersive``
    word, an answer that carries candidates anyway renders **no**
    ``directions`` key, and the narrator's prompt carries no
    requirement line — the world keeping its own counsel."""

    provider = BeatsProvider(beats_json=DIRECTED_BEATS)
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        if set_mode:
            status, _ = stack.post(
                "/api/settings/world_direction_mode",
                {"world_direction_mode": "immersive"},
            )
            assert status == 200
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        frame = turn["world"]
        assert "directions" not in frame
        assert turn["reply"] == provider.reply_text
        prompt = _narrator_prompts(provider)[0]
        assert "Direction candidates:" not in prompt
        # The beats still landed (the answer's narration half was fine).
        status, inbox = stack.get_json("/api/world/inbox")
        assert status == 200
        assert len(inbox["items"]) == 2


# ---------------------------------------------------------------------------
# 5 — the page sources
# ---------------------------------------------------------------------------


def test_the_page_renders_the_option_row_and_the_settings_knob() -> None:
    """The served sources carry the wr-10 faces: the option row's
    renderer (chip options, aria-pressed selected state, the fetcher
    call, the natural-expiry retirement), the two fetchers in api.js,
    and the settings third knob on the server-declared word list —
    textContent throughout, zero scroll hijack in the new code."""

    app = (REPO / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )
    api = (REPO / "src" / "elc" / "webui" / "api.js").read_text(
        encoding="utf-8"
    )
    assert "world-direction-row" in app
    assert "world-direction-row--expired" in app
    assert "world-direction-option" in app
    assert 'setAttribute("aria-pressed"' in app
    assert "chip--on" in app
    assert "fetchSaveWorldDirection({ label: label, hint: hint })" in app
    assert "fetchSaveWorldDirectionMode" in app
    assert "fetchSaveWorldDirection" in api
    assert 'postJson("/api/world/direction", payload)' in api
    assert 'postJson("/api/settings/world_direction_mode",' in api
    assert "{ world_direction_mode: word }" in api
    # Zero scroll hijack (wr-5 律): the direction row's own code never
    # moves the viewport.
    start = app.find("function expireWorldDirectionRow")
    end = app.find("function renderWorldStory")
    assert start != -1 and end != -1 and start < end
    direction_code = app[start:end]
    assert "scroll" not in direction_code.lower()
    # 处置刀（评审 F-1，m9 NOT-RED 缺口闭合）：自然过期有钉——
    # renderWorldStory 的函数体内必须调 expireWorldDirectionRow（新块
    # 渲染即换代旧选项行；摘掉它源级 9/9 仍绿的钉缺口在此闭合）。
    story_start = app.find("function renderWorldStory")
    story_end = app.find("\nfunction ", story_start + 1)
    assert story_start != -1 and story_end != -1
    story_body = app[story_start:story_end]
    assert "expireWorldDirectionRow()" in story_body, (
        "renderWorldStory must retire the previous direction row — "
        "the natural-expiry law has no other enforcer"
    )
    # textContent discipline: no innerHTML anywhere in the page code.
    assert ".innerHTML" not in app
    assert ".innerHTML" not in api
