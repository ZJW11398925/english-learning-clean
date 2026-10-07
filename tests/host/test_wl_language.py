"""W-L — the language and readability cut, over the production faces.

Nine pin groups (the slice VAL's nine):

1. **the settings face** — ``POST /api/settings/ui_language`` and
   ``POST /api/settings/reply_language`` take one whitelisted word each
   (case-sensitive; anything else is the 400 人话 naming its words),
   ``GET /api/settings`` answers both words (the stored row, or the
   default ``zh`` / ``follow`` when nothing is chosen — an absent row
   answers the default and writes nothing), the whitelists ride
   server-declared, and a word persists across a restart;
2. **the prompt's three states** — the ``[response]`` section's language
   row renders per the reply-language word: ``follow`` is the pre-W-L
   sentence **verbatim** (the default keeps every prompt byte-identical),
   ``zh`` / ``en`` name the language outright, the ``english
   expressions`` row is the same in all three, and the compiler stays
   byte-deterministic per state;
3. **the E2E** — the next letter through the real web stack really
   carries the row: a prompt-recording provider sees ``reply in
   English`` after the page write (persisted across the restart), the
   default letter carries the follow sentence and nothing else moved;
4. **package v4** — the loader reads v4 strictly: the shipped Berrymoor
   file is bilingual truth, a monolingual event is refused, a v1 stamp
   is refused, a missing or negative story span is refused, an empty
   ``narration_zh`` is refused, a duplicated kind is refused;
5. **the inbox payload** — the payload names the language it rendered
   in, ``zh`` items carry the package's Chinese prose, and a durable
   event the package cannot render in Chinese (v1-era history) falls
   back to its English row with ``fallback: true`` — never a fabricated
   Chinese one; the ``en`` leg is the primary language, not a fallback;
6. **the behavioral wiring** — switching the interface language re-reads
   the inbox (source-scan pairing, the W-1-3R law), the inbox mounts at
   the bottom of the conversation flow (DEC-…66) and new notes scroll
   into view on a turn's reread (scroll only, never focus);
7. **the webui instrument** — the language face rides the family
   machinery: two ``selectField`` controls with the bilingual labels,
   the section's ids exist in the served page, and the page's text
   paths stay inert (zero ``innerHTML``);
8. **the Berrymoor truth** — every shipped event carries a non-empty
   Chinese narration that differs from its English row, in Chinese
   script, with the cast's given name in the thanks note;
9. **the W-1-3 migration ledger** — the payload's W-L additions are
   purely additive: every pre-W-L key (payload and per-item) is still
   present and typed as the W-1-3 readers know it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from elc.persona.commands import (
    RESPONSE_SECTION,
    PromptCompiler,
    _response_section,
)
from elc.persona.types import (
    RESPONSE_LANGUAGE_WORDS,
    CompiledPrompt,
    PromptCompilationRequest,
    ProviderOutput,
)
from elc.platform.types import (
    ConversationId,
    Err,
    InteractionChannel,
    PersonaId,
)
from elc.web import _WebFace
from elc.world.package import BUILTIN_WORLDS_DIR, load_world_package
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack

REPO = Path(__file__).resolve().parents[2]
PACKAGE_PATH = BUILTIN_WORLDS_DIR / "berrymoor.json"

#: The pre-W-L language row, word for word — the ``follow`` state's bytes.
_FOLLOW_LINE = (
    "language: follow the user — reply in the language the user writes in"
    " (simplified Chinese by default)"
)


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows off the serving database through a fresh
    read-only connection (the W-4 ro posture — the worker thread owns
    the writable one)."""

    conn = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(conn.execute(sql).fetchall())
    finally:
        conn.close()


def _inject_event(
    app_db: Path,
    event_id: str,
    kind: str,
    day: str,
    *,
    narration: str,
) -> None:
    """One chronicle event plus its ``PENDING`` reveal row, written by
    hand from the test thread (a second connection; the worker holds no
    write lock between requests — the wf-0 suite's injection posture).
    WR-2 随迁: the turn no longer writes engine events, so the payload
    language pins inject the rows they read."""

    conn = sqlite3.connect(str(app_db), timeout=10)
    try:
        conn.execute(
            "INSERT INTO world_event (event_id, world_id, kind, narration,"
            " effects, occurred_at, source)"
            " VALUES (?, 'world-berrymoor', ?, ?, '[]', ?, 'test')",
            (event_id, kind, narration, day),
        )
        conn.execute(
            "INSERT INTO world_reveal_item (item_id, world_id,"
            " source_event_id, actor_id, status, revealed_at, created_at)"
            " VALUES (?, 'world-berrymoor', ?, NULL, 'PENDING', NULL, ?)",
            (f"{event_id}:reveal", event_id, day),
        )
        conn.commit()
    finally:
        conn.close()


class _PromptRecorder:
    """A provider that answers a fixed reply and records the **prompt
    text** of every call — the E2E's reading instrument (the scripted
    default records only hashes)."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        return ProviderOutput(text=REPLY, error=None)


# ---------------------------------------------------------------------------
# 1 — the settings face
# ---------------------------------------------------------------------------


def test_ui_language_write_whitelist_and_persistence(tmp_path: Path) -> None:
    """The interface-language write: the two words ride, everything else
    is the 400 人话 naming the whitelist, the read answers the stored
    word, and the word survives a restart (the row is the truth, not the
    process)."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, body = stack.post("/api/settings/ui_language",
                                  {"ui_language": "en"})
        assert status == 200
        assert body["accepted"] is True
        assert body["ui_language"] == "en"
        status, seen = stack.get_json("/api/settings")
        assert seen["ui_language"] == "en"
        # The whitelist, fail-closed: an unknown word and a malformed
        # body are both the grammar sentence, never a guessed language.
        for bad in ({"ui_language": "fr"}, {"ui_language": "EN"},
                    {"language": "en"}, {}):
            status, err = stack.post("/api/settings/ui_language", bad)
            assert status == 400, bad
            assert '"ui_language": zh | en' in err["error"], bad
    with web_stack(app_db) as stack:
        _, seen = stack.get_json("/api/settings")
    assert seen["ui_language"] == "en"


def test_reply_language_write_whitelist_and_persistence(
    tmp_path: Path,
) -> None:
    """The reply-language write: the three words ride (``follow`` is a
    word, the pre-W-L stance), everything else is the 400 人话, and the
    word survives a restart."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        for word in ("zh", "en", "follow"):
            status, body = stack.post("/api/settings/reply_language",
                                      {"reply_language": word})
            assert status == 200
            assert body["accepted"] is True
            status, seen = stack.get_json("/api/settings")
            assert seen["reply_language"] == word
        for bad in ({"reply_language": "fr"}, {"reply_language": "ZH"},
                    {"language": "zh"}, {}):
            status, err = stack.post("/api/settings/reply_language", bad)
            assert status == 400, bad
            assert '"reply_language": zh | en | follow' in err["error"], bad
    with web_stack(app_db) as stack:
        _, seen = stack.get_json("/api/settings")
    assert seen["reply_language"] == "follow"


def test_settings_read_answers_defaults_without_writing(
    tmp_path: Path,
) -> None:
    """A fresh database reads the two defaults — ``zh`` / ``follow`` —
    and writes nothing: the read substitutes, the store stays empty (an
    absent row is the honest "not chosen yet")."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _, seen = stack.get_json("/api/settings")
        assert seen["ui_language"] == "zh"
        assert seen["reply_language"] == "follow"
        rows = _ro_rows(
            app_db,
            "SELECT key FROM app_setting WHERE key IN"
            " ('ui_language', 'reply_language')",
        )
    assert rows == []


def test_settings_read_rides_the_word_lists(tmp_path: Path) -> None:
    """The whitelists ride server-declared (the page copies no word
    list — the mode_words discipline): the reply vocabulary is the
    compiler's own tuple, verbatim."""

    with web_stack(tmp_path / "app.db") as stack:
        _, seen = stack.get_json("/api/settings")
    assert seen["ui_language_words"] == ["zh", "en"]
    assert seen["reply_language_words"] == list(RESPONSE_LANGUAGE_WORDS)


# ---------------------------------------------------------------------------
# 2 — the prompt's three states
# ---------------------------------------------------------------------------


def _request(word: str) -> PromptCompilationRequest:
    return PromptCompilationRequest(
        conversation_id=ConversationId("conv-wl"),
        persona_id=PersonaId("persona-wl"),
        interaction_channel=InteractionChannel.TEXT,
        response_language=word,
    )


def test_response_section_renders_the_three_words() -> None:
    """The language row per word: ``follow`` is the pre-W-L sentence
    verbatim (byte-equal to the module constant the existing pins
    import), ``zh`` / ``en`` name the language outright."""

    assert _response_section("follow") == RESPONSE_SECTION
    assert RESPONSE_SECTION.splitlines()[1] == _FOLLOW_LINE
    assert _response_section("zh").splitlines()[1] == (
        "language: reply in simplified Chinese"
    )
    assert _response_section("en").splitlines()[1] == "language: reply in English"


def test_english_expressions_row_unchanged_in_all_three_states() -> None:
    """The craft row is not keyed by the reply language: an expression
    the letter uses as an expression stays in English, exactly as
    given, in all three states."""

    for word in RESPONSE_LANGUAGE_WORDS:
        section = _response_section(word)
        assert section.splitlines()[2] == (
            "english expressions: keep an expression itself in English,"
            " exactly as given"
        )


def test_compiler_is_byte_deterministic_per_state() -> None:
    """Same request in, byte-identical prompt out — per state; different
    states differ (and only on the language row)."""

    compiler = PromptCompiler()
    for word in RESPONSE_LANGUAGE_WORDS:
        first = compiler.compile(_request(word)).value.prompt_text
        second = compiler.compile(_request(word)).value.prompt_text
        assert first == second
    zh = compiler.compile(_request("zh")).value.prompt_text
    en = compiler.compile(_request("en")).value.prompt_text
    follow = compiler.compile(_request("follow")).value.prompt_text
    assert len({zh, en, follow}) == 3
    assert zh.replace(
        "language: reply in simplified Chinese", _FOLLOW_LINE
    ) == follow


def test_request_refuses_out_of_vocabulary_word() -> None:
    """The prompt boundary is fail-closed: a word the write faces could
    not have written is a construction refusal naming the word and the
    vocabulary — never a silent fall-back to ``follow``. The default is
    ``follow``."""

    try:
        _request("fr")
        raise AssertionError("an out-of-vocabulary word must refuse")
    except ValueError as exc:
        assert "'fr'" in str(exc)
        assert "follow" in str(exc)
    request = _request("follow")
    assert request.response_language == "follow"
    default = PromptCompilationRequest(
        conversation_id=ConversationId("conv-wl"),
        persona_id=PersonaId("persona-wl"),
        interaction_channel=_request("follow").interaction_channel,
    )
    assert default.response_language == "follow"


# ---------------------------------------------------------------------------
# 3 — the E2E: the next letter really carries the row
# ---------------------------------------------------------------------------


def test_the_next_letter_answers_in_the_set_language(tmp_path: Path) -> None:
    """The page write reaches the prompt: ``en`` persisted, then the
    next letter through a **fresh** open of the same database compiles
    with ``reply in English`` (and not the follow sentence); switching
    back to ``zh`` moves the very next letter too — the coordinator
    re-reads the row per turn, no reassembly."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, body = stack.post("/api/settings/reply_language",
                                  {"reply_language": "en"})
        assert status == 200 and body["accepted"] is True
    recorder = _PromptRecorder()
    with web_stack(app_db, provider=recorder) as stack:
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == REPLY
        # WR-6 随迁: every turn dials twice — the world-first narration
        # prompt first, then the letter's reply (which this recorder
        # answers with the same fixed reply; the world step refuses it
        # quietly). The letter prompts sit at the even indices now
        # (0-based: the reply is index 1, 3, …).
        assert len(recorder.prompts) == 2
        assert "language: reply in English" in recorder.prompts[1]
        assert _FOLLOW_LINE not in recorder.prompts[1]
        status, _ = stack.post("/api/settings/reply_language",
                               {"reply_language": "zh"})
        assert status == 200
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert len(recorder.prompts) == 4
        assert "language: reply in simplified Chinese" in recorder.prompts[3]


def test_the_default_letter_is_zero_drift(tmp_path: Path) -> None:
    """With nothing chosen, the letter compiles exactly as it always
    did: the follow sentence verbatim, and neither new row in it (the
    pre-W-L bytes, pinned through the real stack)."""

    recorder = _PromptRecorder()
    with web_stack(tmp_path / "app.db", provider=recorder) as stack:
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == REPLY
    # WR-6: dial 0 is the world-first narration prompt; the letter's
    # reply prompt is dial 1.
    prompt = recorder.prompts[1]
    assert _FOLLOW_LINE in prompt
    assert "language: reply in English" not in prompt
    assert "language: reply in simplified Chinese" not in prompt


# ---------------------------------------------------------------------------
# 4 — package v4: the loader reads v4 strictly
# ---------------------------------------------------------------------------


def _v4_payload() -> dict[str, object]:
    """One minimal valid v4 payload — the negative tests mutate a copy
    of this and expect the loader to refuse the copy, never the shipped
    Berrymoor file."""

    return {
        "world_id": "world-x",
        "name": "X",
        "version": 4,
        "calendar_start": "2025-09-14",
        "setting": ["one", "two", "three"],
        "cast": [{"persona_id": "persona-nell-alder", "name": "Nell"}],
        "event_pool": [
            {
                "kind": "k",
                "narration": "n",
                "narration_zh": "n-中文",
                "days": 1,
                "effects": [],
                "conditions": [],
                "moment": "NOTICE",
            }
        ],
        "supply": {"note": "declared-not-consumed", "families": ["DISC"]},
    }


def _write_package(tmp_path: Path, payload: object, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_berrymoor_is_v4_bilingual_truth_with_a_kind_lookup() -> None:
    """The shipped package: version 4, ten events each carrying its
    story span, every Chinese narration present and non-empty, kinds
    unique, and the kind-keyed lookup answers each row (the presentation
    face's source)."""

    result = load_world_package(PACKAGE_PATH)
    assert not isinstance(result, Err), result.error.message
    package = result.value
    assert package.version == 4
    assert package.calendar_start == "2025-09-14"
    assert len(package.event_pool) == 10
    assert all(event.days >= 0 for event in package.event_pool)
    assert len(package.narrations_zh) == 10
    for event in package.event_pool:
        zh = package.narration_zh_for(event.kind)
        assert isinstance(zh, str) and zh.strip()
    assert package.narration_zh_for("kind-no-package-carries") is None


def test_loader_refuses_a_monolingual_package(tmp_path: Path) -> None:
    """A v4 event without its Chinese narration is a refusal naming the
    key — half a language cannot ride in silently."""

    payload = _v4_payload()
    del payload["event_pool"][0]["narration_zh"]  # type: ignore[index]
    result = load_world_package(_write_package(tmp_path, payload, "w.json"))
    assert isinstance(result, Err)
    assert "narration_zh" in result.error.message


def test_loader_refuses_v1_and_empty_chinese(tmp_path: Path) -> None:
    """A v1 stamp is refused with the number in the message (a v1 file
    is not read half-way), and an empty / whitespace ``narration_zh``
    is a refusal, not a note."""

    v1 = _v4_payload()
    v1["version"] = 1
    result = load_world_package(_write_package(tmp_path, v1, "w1.json"))
    assert isinstance(result, Err)
    assert "version must be 4" in result.error.message
    assert "got 1" in result.error.message
    blank = _v4_payload()
    blank["event_pool"][0]["narration_zh"] = "   "  # type: ignore[index]
    result = load_world_package(_write_package(tmp_path, blank, "w2.json"))
    assert isinstance(result, Err)
    assert "narration_zh" in result.error.message


def test_loader_refuses_a_bad_story_span(tmp_path: Path) -> None:
    """A missing or negative ``days`` is a refusal naming the field
    (a v3 face kept in v4): the calendar is story-driven, so a wrong
    span is a wrong world."""

    missing = _v4_payload()
    del missing["event_pool"][0]["days"]  # type: ignore[index]
    result = load_world_package(
        _write_package(tmp_path, missing, "wd1.json")
    )
    assert isinstance(result, Err)
    assert "days" in result.error.message
    negative = _v4_payload()
    negative["event_pool"][0]["days"] = -1  # type: ignore[index]
    result = load_world_package(
        _write_package(tmp_path, negative, "wd2.json")
    )
    assert isinstance(result, Err)
    assert "days" in result.error.message


def test_loader_refuses_a_duplicated_kind(tmp_path: Path) -> None:
    """The Chinese narrations are a kind-keyed mapping, so a duplicated
    kind would make the lookup ambiguous — a refusal naming the kind,
    never a silent overwrite."""

    payload = _v4_payload()
    payload["event_pool"] = [  # type: ignore[index]
        {
            "kind": "k",
            "narration": "n1",
            "narration_zh": "n1-中文",
            "days": 1,
        },
        {
            "kind": "k",
            "narration": "n2",
            "narration_zh": "n2-中文",
            "days": 2,
        },
    ]
    result = load_world_package(_write_package(tmp_path, payload, "w3.json"))
    assert isinstance(result, Err)
    assert "'k'" in result.error.message
    assert "twice" in result.error.message


# ---------------------------------------------------------------------------
# 5 — the inbox payload: language, zh prose, the honest fallback
# ---------------------------------------------------------------------------


def test_inbox_payload_names_language_and_serves_chinese(
    tmp_path: Path,
) -> None:
    """The payload names the language it rendered in, and ``zh`` items
    carry the package's own Chinese prose (the default language is
    ``zh``): CJK script in the narration, ``fallback`` false — the
    Chinese row is the primary, not a stand-in. (WR-2 随迁: the note
    rides a hand-injected row whose kind the package carries — the turn
    no longer writes engine events for the payload to read.)"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _inject_event(
            app_db,
            "wl-zh-1",
            "market_day",
            "2025-09-14",
            narration="Saturday on the quay: the fish carts were out.",
        )
        status, inbox = stack.get_json("/api/world/inbox")
    assert status == 200
    assert inbox["language"] == "zh"
    assert inbox["items"]
    for note in inbox["items"]:
        assert note["fallback"] is False
        assert any("\u4e00" <= ch <= "\u9fff" for ch in note["narration"])


def test_inbox_fallback_marks_the_english_leg(tmp_path: Path) -> None:
    """A durable event the v2 package cannot render in Chinese (v1-era
    history, simulated by a kind the package never carried) falls back
    to its **English** row and says so with ``fallback: true`` — never a
    fabricated Chinese one. The ``en`` leg is the primary language:
    ``fallback`` false there. (WR-2 随迁: hand-injected rows, same
    reason as the zh pin above.)"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _inject_event(
            app_db,
            "wl-old-1",
            "old_kind",
            "2025-09-14",
            narration="A note the world wrote before its Chinese.",
        )
        status, zh = stack.get_json("/api/world/inbox")
        assert status == 200
        assert zh["language"] == "zh"
        assert zh["items"]
        for note in zh["items"]:
            assert note["fallback"] is True
            assert not any(
                "\u4e00" <= ch <= "\u9fff" for ch in note["narration"]
            )
        status, _ = stack.post("/api/settings/ui_language",
                               {"ui_language": "en"})
        assert status == 200
        status, en = stack.get_json("/api/world/inbox")
        assert status == 200
        assert en["language"] == "en"
        for note in en["items"]:
            assert note["fallback"] is False


# ---------------------------------------------------------------------------
# 6 — the behavioral wiring (source-scan, the W-1-3R law)
# ---------------------------------------------------------------------------


def _app_js() -> str:
    return (REPO / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )


def test_ui_language_switch_rerenders_the_history() -> None:
    """wr-8（DEC-OPI-c73dbff3…34）真值随迁（本钉原断言切换后重读收
    件箱——该臂随尾部补显退役）：界面语言保存块改走历史重渲染——世
    界块已入 history 交错，叙述按界面语言现读（a switch without the
    re-render would leave the old language on screen）。"""

    app = _app_js()
    start = app.find("async function saveUiLanguage")
    end = app.find("async function saveReplyLanguage")
    assert start != -1 and end != -1 and start < end
    block = app[start:end]
    assert "await loadHistory();" in block
    assert "loadWorldInbox" not in block
    # …and the reply-language save does not (nothing world-shaped moves):
    # the function body is the slice up to the next top-level def.
    next_def = min(
        p
        for p in (
            app.find("\nasync function ", end),
            app.find("\nfunction ", end),
            app.find("\n// ──", end),
        )
        if p != -1
    )
    assert "loadWorldInbox" not in app[end:next_def]
    assert "loadHistory" not in app[end:next_def]


def test_bottom_mount_and_scroll_into_view_are_wired() -> None:
    """DEC-…92's retirement, as the source runs it: the resident inbox
    region is gone (no ``worldInboxSec``, no bottom mount — the world's
    only presentation is the inline story block in the letter flow),
    and the load arm renders only what it actually revealed
    (``revealed_now``), so the conversation's tail stays clean."""

    app = _app_js()
    assert "worldInboxSec" not in app
    assert 'insertAdjacentElement("afterend"' not in app
    assert "revealed_now" in app
    assert "renderWorldStory(data" in app


# ---------------------------------------------------------------------------
# 7 — the webui instrument
# ---------------------------------------------------------------------------


def test_language_controls_ride_the_family_machinery() -> None:
    """The two controls are the family's ink-select (``selectField`` —
    keyboard/touch machinery the component already carries), labeled
    bilingually, fed from the server-declared word lists; the served
    page carries the section's ids."""

    app = _app_js()
    start = app.find("function renderSettingsLanguage")
    end = app.find("function settingsLanguageResult")
    block = app[start:end]
    assert block.count("selectField({") == 2
    assert "界面语言 Interface language" in block
    assert "回信语言 Reply language" in block
    assert "ui_language_words" in block
    assert "reply_language_words" in block
    page = (REPO / "src" / "elc" / "webui" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="set-settings-language"' in page
    assert 'id="settings-language-editor"' in page
    assert 'id="settings-language-result"' in page


def test_the_language_face_stays_inert_text() -> None:
    """The XSS face, family re-assertion on the touched files: every
    webui script's text paths stay ``textContent`` — zero
    ``innerHTML`` anywhere — and the fallback note's honest wording
    still rides the page (the story block's own small print)."""

    webui = REPO / "src" / "elc" / "webui"
    for name in ("app.js", "api.js", "components.js"):
        assert ".innerHTML" not in (webui / name).read_text(
            encoding="utf-8"
        ), name
    assert "（这张便条写在世界学会中文之前——示以原文。）" in _app_js()


# ---------------------------------------------------------------------------
# 8 — the Berrymoor truth
# ---------------------------------------------------------------------------


def test_every_berrymoor_zh_narration_is_real_chinese_prose() -> None:
    """The shipped file: all ten events carry a Chinese narration in
    Chinese script that differs from its English row (same-source
    translation, never a copy), and the thanks note names the cast's
    given name (the card portrait's own register)."""

    package = load_world_package(PACKAGE_PATH).value
    assert len(package.event_pool) == 10
    for event in package.event_pool:
        zh = package.narration_zh_for(event.kind)
        assert zh is not None and zh.strip()
        assert any("\u4e00" <= ch <= "\u9fff" for ch in zh)
        assert zh != event.narration
        assert event.narration.strip()
    thanks = package.narration_zh_for("nell_thanks")
    assert thanks is not None and "奈尔" in thanks


# ---------------------------------------------------------------------------
# 9 — the W-1-3 migration ledger: additive shapes only
# ---------------------------------------------------------------------------


def test_inbox_payload_shape_is_additive_over_w13(tmp_path: Path) -> None:
    """Every pre-W-L key is still present and typed as the W-1-3 readers
    know it — the payload gains ``language``, each item gains
    ``fallback``, and nothing else moved (the old readers' contract,
    pinned here so the migration ledger is checkable)."""

    with web_stack(tmp_path / "app.db") as stack:
        status, _ = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        status, inbox = stack.get_json("/api/world/inbox")
    assert status == 200
    for key in ("world_id", "items", "letters", "at_checkpoint"):
        assert key in inbox, key
    assert isinstance(inbox["letters"], list)
    # One turn wound the world: the run is at its stop, never at a
    # checkpoint (the A2R truth — the engine never pauses mid-run; the
    # bit is the run's own state, never a guess).
    assert inbox["at_checkpoint"] is False
    for note in inbox["items"]:
        for key in (
            "id",
            "narration",
            "actor_name",
            "moment",
            "occurred_at",
            "status",
        ):
            assert key in note, key
        assert isinstance(note["fallback"], bool)


def test_the_no_binding_answer_is_untouched() -> None:
    """The one W-1-3 answer this cut must not touch: a conversation
    outside any world is still the honest 404, not an empty inbox."""

    class _NoWorldHost:
        app_db_path = "stub.db"

    face = _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]
    status, payload = face.world_inbox()
    assert status == 404
    assert "没有绑定任何世界" in payload["error"]
