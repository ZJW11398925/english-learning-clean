"""V3-8g — the reading face's language write, the state's language
field and the page's progress / busy-feedback / language-selector half
(TASK-OPI-c0f4d9b4…24 / the opening ruling ``DEC-OPI-c0f4d9b4…22``; the
paradigm shift §10.4 item 5).

**What this suite proves, stated honestly.**

1. **The language route** — the grammar is fail-closed (a bad body is
   a 400 人话); the write persists one whitelisted word into the host's
   ``app_setting`` table through the reading face, idempotently (a
   replay is a zero-write and says so); ``GET /api/v3/state`` answers
   the live word, defaulting to ``en`` when no row exists.
2. **The live read through the real chain** — after the switch the
   very next drive's writer prompt carries the Chinese language line
   (the recorded offline transport's own prompts), the fresh passage
   row's ``language`` column follows the switch, and **passages
   already committed are never rewritten** (their bodies and language
   columns are byte-identical across the switch; only the new segment
   was added).
3. **The face's honest arms** — an out-of-vocabulary word is refused
   without a write; a host without the V3 legs answers one sentence.
4. **The page half** — reader.html carries the busy line, the spinner
   and the language selector; reader.js carries the timer / spinner /
   stage / busy-feedback literals and **no silent busy guard**
   (``if (busy) return;`` is gone); reader.css carries the spinner
   rules; the main UI files are untouched.

The real-model evidence (the continuation-similarity reading and the
zh body's non-ASCII share) is the V3-8g smoke run's own log
(``D:\\elc-scratch\\v38g\\smoke.log``), cited in the delivery report —
never in this suite (the V3-8e suite's own posture).
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from elc.host import open_host
from elc.narrative_web import (
    V3_LANGUAGE_GRAMMAR,
    NarrativeWebFace,
)
from tests.host.test_v3_8e_reader import (
    _gold_egress,
    _GoldPost,
    _post_json,
    v3_stack,
)

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"


def _passage_rows(app_db: Path) -> list[tuple[str, str, str]]:
    """Every passage row as (passage_id, language, body-sha256) —
    the zero-rewrite witness reads body bytes, not only the count."""

    connection = sqlite3.connect(app_db)
    try:
        rows = connection.execute(
            "SELECT passage_id, language, body FROM narrative_passage"
            " ORDER BY passage_id"
        ).fetchall()
    finally:
        connection.close()
    return [
        (
            str(passage_id),
            str(language),
            hashlib.sha256(str(body).encode("utf-8")).hexdigest(),
        )
        for passage_id, language, body in rows
    ]


def _settings_row(app_db: Path, key: str) -> Any:
    connection = sqlite3.connect(app_db)
    try:
        row = connection.execute(
            "SELECT value FROM app_setting WHERE key = ?", (key,)
        ).fetchone()
    finally:
        connection.close()
    return None if row is None else row[0]


# ---------------------------------------------------------------------------
# 1. the route: grammar, write, state field, idempotency
# ---------------------------------------------------------------------------


def test_the_language_route_is_fail_closed_and_the_state_carries_it(
    tmp_path: Path,
) -> None:
    """A bad body is a 400 人话; a good one persists the word (visible
    in the very next state read); a replay is the zero-write idempotent
    arm. The default word with no row is ``en``."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        assert stack.state()["language"] == "en"
        assert _settings_row(app_db, "v3_prose_language") is None

        for bad in ({}, {"language": "fr"}, {"language": 1}, {"lang": "zh"}):
            status, payload = _post_json(
                stack.port, "/api/v3/language", bad
            )
            assert status == 400, bad
            assert payload["error"] == V3_LANGUAGE_GRAMMAR, bad
        assert _settings_row(app_db, "v3_prose_language") is None

        status, payload = _post_json(
            stack.port, "/api/v3/language", {"language": "zh"}
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["did"] == {
            "kind": "language",
            "language": "zh",
            "idempotent": False,
        }
        assert payload["language"] == "zh"
        assert _settings_row(app_db, "v3_prose_language") == "zh"
        assert stack.state()["language"] == "zh"

        status, replay = _post_json(
            stack.port, "/api/v3/language", {"language": "zh"}
        )
        assert status == 200
        assert replay["did"]["idempotent"] is True
        assert replay["language"] == "zh"

        status, back = _post_json(
            stack.port, "/api/v3/language", {"language": "en"}
        )
        assert status == 200
        assert back["did"]["idempotent"] is False
        assert stack.state()["language"] == "en"


def test_a_stored_word_outside_the_vocabulary_falls_back_to_the_default(
    tmp_path: Path,
) -> None:
    """The stored row is the one face the route cannot police (a hand
    edit, an older build): an out-of-vocabulary word falls back to the
    default ``en`` on the read face — the review's F2 tooth (deleting
    the fallback used to leave the whole family green)."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        connection = sqlite3.connect(app_db)
        with connection:
            connection.execute(
                "INSERT INTO app_setting(key, value) VALUES (?, ?)",
                ("v3_prose_language", "fr"),
            )
        connection.close()
        assert _settings_row(app_db, "v3_prose_language") == "fr"
        assert stack.state()["language"] == "en"


def test_the_idempotent_replay_writes_nothing(tmp_path: Path) -> None:
    """The face-level witness for the replay: a counting proxy in front
    of the host's real ``app_settings`` records every ``set`` — the
    second switch to the same word performs none."""

    app_db = tmp_path / "app.db"
    host = open_host(app_db, provider=_gold_egress(_GoldPost()))
    face = NarrativeWebFace(host)

    writes: list[tuple[str, str]] = []
    original = host.app_settings.set

    def recording_set(key: str, value: str) -> None:
        writes.append((key, value))
        original(key, value)

    host.app_settings.set = recording_set  # type: ignore[method-assign]
    first = face.set_language("zh")
    assert first["ok"] is True
    assert first["did"]["idempotent"] is False
    assert writes == [("v3_prose_language", "zh")]
    second = face.set_language("zh")
    assert second["ok"] is True
    assert second["did"]["idempotent"] is True
    assert writes == [("v3_prose_language", "zh")]  # the replay wrote none


def test_the_face_refuses_out_of_vocabulary_and_legless_hosts(
    tmp_path: Path,
) -> None:
    """The write face re-checks the vocabulary (fail-closed at both
    ends) and a host without the V3 legs answers the one honest
    sentence — neither touches the settings table."""

    app_db = tmp_path / "app.db"
    host = open_host(app_db, provider=_gold_egress(_GoldPost()))
    face = NarrativeWebFace(host)
    refused = face.set_language("fr")
    assert refused["ok"] is False
    assert "en" in refused["error"] and "zh" in refused["error"]
    assert _settings_row(app_db, "v3_prose_language") is None

    legless = NarrativeWebFace(object())
    answered = legless.set_language("zh")
    assert answered["ok"] is False
    assert "V3 世界腿" in answered["error"]


# ---------------------------------------------------------------------------
# 2. the live read through the real chain (prompt, row, no rewrite)
# ---------------------------------------------------------------------------


def test_the_switch_reaches_the_next_prompts_and_never_rewrites_canon(
    tmp_path: Path,
) -> None:
    """Start under ``en``, switch to ``zh``, then continue: the writer
    prompt recorded by the offline transport carries the Chinese line
    (the live-setting pass-through), the fresh passage row declares
    ``zh`` (the beat-language seat follows the driver), and the
    already-committed rows are byte-identical — a language switch
    never rewrites canon."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        started = stack.start()
        assert started["ok"] is True, started
        first = stack.advance()
        assert first[1]["ok"] is True, first

        writer_prompts = stack.post.prompts("writer")
        assert len(writer_prompts) >= 1
        assert "Write the segment's prose in English" in writer_prompts[0]

        before = _passage_rows(app_db)
        assert len(before) == 1
        assert before[0][1] == "en"

        status, switched = _post_json(
            stack.port, "/api/v3/language", {"language": "zh"}
        )
        assert status == 200 and switched["ok"] is True

        second = stack.advance()
        assert second[1]["ok"] is True, second

        after_prompts = stack.post.prompts("writer")
        assert len(after_prompts) == len(writer_prompts) + 1
        assert "用中文写作这一段的正文" in after_prompts[-1]
        assert "Write the segment's prose in English" not in after_prompts[-1]

        after = _passage_rows(app_db)
        assert len(after) == 2
        assert after[0] == before[0]  # the committed canon row: untouched
        assert after[1][1] == "zh"  # the fresh row declares the switch
        state = stack.state()
        assert state["language"] == "zh"
        languages = [passage["language"] for passage in state["passages"]]
        assert languages == ["en", "zh"]


# ---------------------------------------------------------------------------
# 3. the page half
# ---------------------------------------------------------------------------


def test_the_page_carries_the_progress_face_and_the_language_selector() -> None:
    """reader.html: the busy line with the spinner and the note slot,
    the language selector labelled 「正文语言」 with its two buttons;
    zero inline style/script (the V3-8e discipline restated)."""

    page = (WEBUI / "reader.html").read_text(encoding="utf-8")
    assert 'id="reader-busyline"' in page
    assert 'class="reader-spinner"' in page
    assert 'id="reader-busy-note"' in page
    assert 'id="reader-lang-en"' in page
    assert 'id="reader-lang-zh"' in page
    assert "正文语言" in page
    assert "<style" not in page and "<script>" not in page
    assert "http://" not in page and "https://" not in page


def test_the_page_script_carries_the_timer_motion_and_feedback() -> None:
    """reader.js: the busy line's timer literals (1s ticker, elapsed
    seconds), the spinner element it toggles, the three stage
    sentences, the busy-click feedback sentence — and **no silent busy
    guard** (the V3-8g failure: ``if (busy) return;`` swallowed the
    reader's clicks)."""

    script = (WEBUI / "reader.js").read_text(encoding="utf-8")
    assert "reader-busyline" in script
    assert "reader-busy-note" in script
    assert "setInterval(tickBusy, 1000)" in script
    assert "模型思考中" in script
    assert "已写下第" in script
    assert "裁定中" in script
    assert "上一步还在进行中（已用 " in script
    assert "等它跑完再点。" in script
    assert "/api/v3/language" in script
    assert "setLanguage" in script
    assert "已写下的段落不改" in script
    # the silent swallow is gone: both guards answer with a sentence.
    assert "if (busy) return;" not in script
    assert script.count("setStatus(busyNote())") >= 2
    assert "http://" not in script and "https://" not in script


def test_the_page_stylesheet_carries_the_spinner_rules() -> None:
    """reader.css: the spinner's page-level animation and the busy
    line's hidden rule (an unconditional display:flex would override
    the UA's [hidden]); still no second scroll vocabulary, no external
    reference."""

    styles = (WEBUI / "reader.css").read_text(encoding="utf-8")
    assert ".reader-spinner" in styles
    assert "@keyframes reader-spin" in styles
    assert ".reader-busyline[hidden] { display: none; }" in styles
    assert ".reader-lang" in styles
    assert "http://" not in styles and "https://" not in styles


def test_the_main_ui_files_are_untouched() -> None:
    """The reading page's V3-8g additions never leak into the main
    shell: no busy/language keywords, no /v3 entry (the V3-8e law
    restated for this cut's own strings)."""

    for name in ("index.html", "app.js"):
        text = (WEBUI / name).read_text(encoding="utf-8")
        for keyword in (
            "reader-busy",
            "reader-spinner",
            "reader-lang",
            "v3_prose_language",
            "/v3",
        ):
            assert keyword not in text, (name, keyword)
