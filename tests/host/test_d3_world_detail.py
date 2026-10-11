"""D-3 — the world detail screen: the two new read faces and the page
that wears them (the frontend world-hierarchy cut, the user's dogfood
pain: the six townsfolk were nowhere to be seen).

The two faces are reads in the wf-0 family: ``GET /api/world/ensemble``
(your own character + the bound cast + the town's narrative residents,
one payload) and ``GET /api/world/storylines`` (the open arcs through
the store's own two-layer read). The page — ``#space-world``, the fourth
full-page depth screen — is endpoint-assembled in its four zones (your
character / the world's people / the storylines / the chronicle) and
entered from the masthead's world name and the envelope stack's caption.

The pinned groups:

1. **the guards** — both faces answer the inbox's own 404 with the
   inbox's own sentence, at the face seam (the stub host) and over real
   HTTP (an unbound stack);
2. **the ensemble** — the six people (one cast row joined to its card
   with the package's vignette, five residents verbatim), the
   exactly-one ``is_current`` mark, the honest letter counts, and your
   character's four declared strings (the D-1 section, first visible
   here); the honest absences: no ``user_character`` section ⇒ ``None``
   (a temp package without the section), a world whose package the
   process does not carry degrades to the honest zero shape;
3. **the storylines** — the open arcs with their three narrative
   columns verbatim; the resolved arm answers the honest empty list
   (structure word closed by hand — the read retires nothing by
   itself);
4. **the page's presence and wiring** — the screen, its four zone
   slots, the back button, the spaces registry, the navdock stand-down
   (both arms), the Esc return, the three fetchers exported/imported/
   called, the masthead's world-name door with its two arms, and the
   envelope caption's in-line link;
5. **the frontend structure pins** — the chrome table's zh/en pairs,
   the world-* screen classes' single home in screens.css, the
   renderers' textContent discipline (no innerHTML in the block), and
   the three-reads-to-four-zones contract: every key the page reads is
   a key the live payloads carry;
6. **the read-only posture** — AST-level: the two new faces and the
   binding helper the family shares contain zero ``reveal_all`` calls
   and zero store write-face calls (the positive control: the inbox's
   own reveal still counted; the write names are the same audit the
   two-layer law's faces keep).

The pin migrations this cut carries (same-cut truth moves, no strength
lost):

* ``test_wf1_parlor_world_first.py``'s ``showSpace("world")`` absence
  pin — the WR-5 retirement's literal form; the retired world *log*
  screen stays retired (its own names are pinned absent in the new
  location), while the new world *detail* screen legitimately wears the
  ``world`` space key (the task book's own suggested name);
* ``test_fg2_entry_and_states.py``'s ``data-brand-mark="sm"`` count —
  every depth screen wears one, the world screen joins as the seventh.

"""

from __future__ import annotations

import ast
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import elc.web
from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import ConversationId, Ok
from elc.web import _WebFace
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"
PACKAGE = REPO / "worlds" / "berrymoor.json"

#: One durable timestamp for the injected rows (the a2 suite's posture).
NOW = "2025-09-14T08:00:00+00:00"

#: The user_character section's declared strings (v7 / D-1) — the four
#: values the ensemble hands the page and the page renders verbatim.
YOU_NAME = "你"
YOU_ANCHOR = "你是镇上的人，住在装订铺楼上的小房间"
YOU_HOME = "装订铺楼上"

#: The town's narrative residents (the package's five, in file order).
RESIDENT_NAMES = (
    "Old Tam",
    "Mrs. Fenwick",
    "Silas Croft",
    "Edie Marsh",
    "Hester Cowley",
)


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _get_json(port: int, path: str) -> tuple[int, Any]:
    """A GET that decodes error answers too (the read faces' 404 bodies
    are exactly the error shapes the page's judge consumes)."""

    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _function_slice(source: str, head: str) -> str:
    """One top-level function's source, from its def line to the next
    (function-scoped assertions — a string elsewhere cannot satisfy
    them)."""

    start = source.index(head)
    ends = [
        found
        for found in (
            source.find("\nfunction ", start + 1),
            source.find("\nasync function ", start + 1),
        )
        if found != -1
    ]
    return source[start : min(ends)] if ends else source[start:]


class _NoWorldHost:
    """The stub host of the wf-0 404 pins: a world leg no host has."""

    app_db_path = "stub.db"


def _stub_face() -> _WebFace:
    return _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]


def _write_package_without_user_character(tmp_path: Path) -> Path:
    """A temp worlds dir carrying the shipped package minus its v7
    ``user_character`` section — the honest "world knows no player"
    arm, over the real loader and the real seed (the section is
    optional by the package law)."""

    document = json.loads(PACKAGE.read_text(encoding="utf-8"))
    del document["user_character"]
    worlds = tmp_path / "worlds"
    worlds.mkdir()
    (worlds / "berrymoor.json").write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )
    return worlds


def _sql(app_db: Path, statements: tuple[tuple[str, tuple[Any, ...]], ...]) -> None:
    """The injection posture (the a2 suite's own): one short-lived
    writable connection, the worker thread sitting idle in its loop."""

    writer = sqlite3.connect(app_db, timeout=10)
    try:
        for sql, params in statements:
            writer.execute(sql, params)
        writer.commit()
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# 1 — the guards: no binding is the inbox's own 404, on both faces
# ---------------------------------------------------------------------------


def test_both_faces_404_without_a_binding() -> None:
    """At the face seam (a host with no world leg): the ensemble and the
    storylines answer the inbox's own sentence, verbatim — an ensemble
    that does not exist is not an empty one."""

    for face_method in ("world_ensemble", "world_storylines"):
        status, payload = getattr(_stub_face(), face_method)()
        inbox_status, inbox_payload = _stub_face().world_inbox()
        assert status == 404, face_method
        assert inbox_status == 404
        assert payload == {"error": inbox_payload["error"]}
        assert "没有绑定任何世界" in payload["error"]


def test_both_faces_404_over_http_without_a_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The HTTP arm: an unbound stack (no builtin package to bind)
    answers both faces with the same 404 sentence as the overview —
    the error shape the page's judge consumes."""

    empty_dir = tmp_path / "no-worlds"
    empty_dir.mkdir()
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", empty_dir)
    with web_stack(tmp_path / "unbound.db") as stack:
        status, overview = _get_json(stack.port, "/api/world/overview")
        assert status == 404
        for path in ("/api/world/ensemble", "/api/world/storylines"):
            status, payload = _get_json(stack.port, path)
            assert status == 404, path
            assert payload["error"] == overview["error"]


# ---------------------------------------------------------------------------
# 2 — the ensemble: the six people, the mark, the counts, your character
# ---------------------------------------------------------------------------


def test_the_ensemble_answers_the_six_people(tmp_path: Path) -> None:
    """The roster face's own join, one payload: exactly one cast row
    (Nell, joined to her card and the package's vignette) and the
    package's five residents verbatim — six people, the file's own
    order; the key sets are the frontend's contract."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/ensemble")
    assert status == 200
    assert payload["world_id"] == "world-berrymoor"
    assert payload["world_name"] == "Berrymoor"
    assert payload["ui_language"] in ("zh", "en")
    cast = payload["cast"]
    assert [row["actor_id"] for row in cast] == ["actor-berrymoor-nell"]
    nell = cast[0]
    assert set(nell) == {
        "actor_id",
        "persona_id",
        "name",
        "identity",
        "vignette",
        "is_current",
        "letters_count",
    }
    assert nell["name"] == "Nell Alder"
    assert nell["persona_id"] == "persona-nell-alder"
    assert "bookbinder" in nell["identity"]
    assert "green door" in nell["vignette"]   # the package's own prose
    residents = payload["residents"]
    assert [row["name"] for row in residents] == list(RESIDENT_NAMES)
    for row in residents:
        assert set(row) == {"name", "role", "vignette"}
        assert row["role"] and row["vignette"]


def test_the_ensemble_marks_exactly_one_and_counts_honestly(
    tmp_path: Path,
) -> None:
    """``is_current`` marks exactly the bound actor; the letter count is
    the history window's own read — zero before anyone writes, one
    after one letter (the wf-0 count law, same family)."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, ensemble = stack.get_json("/api/world/ensemble")
        assert status == 200
        assert [row["is_current"] for row in ensemble["cast"]] == [True]
        assert [row["letters_count"] for row in ensemble["cast"]] == [0]
        status, _ = stack.post("/api/turn", {"text": "The meeting starts at nine."})
        assert status == 200
        status, ensemble = stack.get_json("/api/world/ensemble")
    assert status == 200
    assert [row["letters_count"] for row in ensemble["cast"]] == [1]


def test_the_ensemble_carries_your_character_verbatim(tmp_path: Path) -> None:
    """The D-1 section, first visible on a page: the four declared
    strings exactly — the name, the anchor, and the home the screen
    renders as「住处 · …」."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/ensemble")
    assert status == 200
    who = payload["user_character"]
    assert set(who) == {"id", "name", "anchor", "home"}
    assert who["id"] == "actor-berrymoor-you"
    assert who["name"] == YOU_NAME
    assert who["anchor"] == YOU_ANCHOR
    assert who["home"] == YOU_HOME


def test_the_ensemble_answers_none_without_the_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A package without the optional v7 section: ``user_character`` is
    ``None`` — the page's honest "no player card" arm — while the cast,
    the residents and the world itself answer unchanged (the section is
    additive by law)."""

    worlds = _write_package_without_user_character(tmp_path)
    monkeypatch.setattr(elc.web, "BUILTIN_WORLDS_DIR", worlds)
    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/ensemble")
    assert status == 200
    assert payload["user_character"] is None
    assert payload["world_name"] == "Berrymoor"
    assert [row["name"] for row in payload["residents"]] == list(
        RESIDENT_NAMES
    )
    assert len(payload["cast"]) == 1


def test_the_ensemble_degrades_honestly_without_the_package(
    tmp_path: Path,
) -> None:
    """The honest zero shape (the face's own degrade arm): a face whose
    loaded-package map is empty answers empty cast-side decls, ``None``
    player and a ``None`` world name — the roster's own join still
    answers (the binding's world is real), never a fabricated name.
    Built over the real host: a conversation opened, bound into the
    seeded world, and the face's package map emptied by hand (the
    production path that reaches this arm is a re-read failure at the
    face's construction, which the map's own fallback covers)."""

    host = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(
            script=(ProviderOutput(text="d3 degrade arm"),)
        ),
    )
    try:
        opened = host.open_conversation(ConversationId("web-test"))
        assert isinstance(opened, Ok), opened
        bound = host.world_store.bind_conversation(
            "bind-web-test",
            "world-berrymoor",
            "actor-berrymoor-nell",
            "web-test",
            NOW,
        )
        assert isinstance(bound, Ok), bound
        face = _WebFace(host, "web-test")
        assert face._world_packages  # seeded by open_host
        face._world_packages = {}
        status, payload = face.world_ensemble()
        assert status == 200
        assert payload["world_name"] is None
        assert payload["user_character"] is None
        assert payload["residents"] == []
        # the cast survives: the binding names a real actor and its card.
        assert [row["name"] for row in payload["cast"]] == ["Nell Alder"]
        assert payload["cast"][0]["vignette"] is None
        # the plot face's own honesty: the arcs are durable rows, not
        # package material — with no package the rows still answer, the
        # world's name is what goes absent (the seed's own fact).
        status, lines = face.world_storylines()
        assert status == 200
        assert lines["world_name"] is None
        assert len(lines["storylines"]) == 2
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 3 — the storylines: the open arcs, the honest empty, read only
# ---------------------------------------------------------------------------


def test_the_storylines_are_the_open_arcs_verbatim(tmp_path: Path) -> None:
    """The seeded arcs (the package's own two), each with exactly the
    three narrative columns the page renders; ``theme`` / ``resolve_at``
    come through as written."""

    document = json.loads(PACKAGE.read_text(encoding="utf-8"))
    seeded = document["initial_storylines"]
    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/storylines")
    assert status == 200
    assert payload["world_name"] == "Berrymoor"
    lines = payload["storylines"]
    assert len(lines) == len(seeded) == 2
    for line, want in zip(lines, seeded):
        assert set(line) == {"line_id", "theme", "resolve_at"}
        assert line["theme"] == want["theme"]
        assert line["resolve_at"] == want["resolve_at"]
        assert line["line_id"].startswith("line-berrymoor-")


def test_a_closed_line_leaves_the_read_and_an_empty_read_is_empty(
    tmp_path: Path,
) -> None:
    """The structure word closes a line (the store's own legal move,
    written by hand through a fresh connection — the injection
    posture): the read answers the honest empty list, and the face
    itself never closed anything (a second read is still empty, and the
    other line still stands)."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, payload = stack.get_json("/api/world/storylines")
        assert status == 200
        assert len(payload["storylines"]) == 2
        first = payload["storylines"][0]
        _sql(
            app_db,
            (
                (
                    "UPDATE world_storyline SET status = 'resolved'"
                    " WHERE world_id = ? AND line_id = ?",
                    ("world-berrymoor", first["line_id"]),
                ),
            ),
        )
        status, payload = stack.get_json("/api/world/storylines")
        assert status == 200
        assert [line["line_id"] for line in payload["storylines"]] != [
            first["line_id"]
        ]
        assert len(payload["storylines"]) == 1
        second = payload["storylines"][0]
        _sql(
            app_db,
            (
                (
                    "UPDATE world_storyline SET status = 'resolved'"
                    " WHERE world_id = ?",
                    ("world-berrymoor",),
                ),
            ),
        )
        status, payload = stack.get_json("/api/world/storylines")
    assert status == 200
    assert payload["storylines"] == []
    assert second["line_id"] != first["line_id"]


# ---------------------------------------------------------------------------
# 4 — the page: presence, registry, entry faces, the three fetchers
# ---------------------------------------------------------------------------


def test_the_screen_exists_with_its_five_zones() -> None:
    """index.html: the world screen — the five zone slots (D-4 adds the
    world shelf), the lead line, the back button, the static header title
    (no-JS honest), the five Chinese h3s (the dossier family's own
    chrome)."""

    index = _text("index.html")
    assert '<section id="space-world" class="dossier" hidden>' in index
    assert '<header class="top space-header" id="world-head">' in index
    assert 'id="world-back"' in index
    assert 'id="world-name"' in index
    for slot in (
        "world-shelf",
        "world-you",
        "world-people",
        "world-lines",
        "world-chronicle",
    ):
        assert f'id="{slot}"' in index, slot
    for title in ("世界架", "你的角色", "世界的人", "剧情线", "编年史"):
        assert f"<h3>{title}</h3>" in index, title


def test_the_screen_is_registered_and_guarded() -> None:
    """app.js: the spaces registry entry, the Esc return and the back
    button — the screen's wiring, each line pinned.

    D-4 迁移（DEC-OPI-a4cf2d0e…63 R4）：本屏按正典 §7.4 升格为导航一级
    成员（navdock「世界」项入坞：世界架 = 世界切换面在单世界时的最小
    就位）——D-3 的 navdock 让位两臂（showSpace 与 restoreNavdock）随
    升格退役（让位只属门厅/三全页）；返回钮与 Esc 保留为额外的回案头
    路。缺位钉（两臂 not in app）让「让位回潮」必红。"""

    app = _text("app.js")
    assert 'world: document.getElementById("space-world"),' in app
    # D-4: the stand-down arms are gone (the world is a dock member now).
    # Disposition (review MEDIUM-1 follow-up): the negative control pins
    # the stand-down **shape** (a name-judged hidden flip), not the bare
    # name test anywhere — the wireNavdock callback's world branch (the
    # entry that drives the reads) is a different layer, never a
    # stand-down.
    assert 'if (name === "world") navdock.hidden = true;' not in app
    assert 'if (current === "world") navdock.hidden = true;' not in app
    # the dock item itself (the shelf's door)
    assert 'data-space="world"' in _text("index.html")
    assert (
        '} else if (current === "world") {\n'
        "    // D-3：世界详情屏的回途（Esc 与返回钮同效）——D-4 世界入坞后\n"
        "    // 它仍保留为「回案头」的额外一路（常驻空间本无 Esc 义务，此臂\n"
        "    // 只增不减：纵深时代的回程语义对首入的用户仍成立）。\n"
        '    showSpace("parlor");'
    ) in app
    assert (
        'document.getElementById("world-back").addEventListener(\n'
        '  "click", () => showSpace("parlor"));' in app
    )
    # the original three-screen arms are untouched (the additive form)
    assert (
        'if (name === "partner" || name === "letters" || name === "obs") {'
        in app
    )
    assert 'if (current === "partner" || current === "letters") {' in app


def test_the_three_fetchers_are_wired() -> None:
    """api.js exports the three读面 (each with its endpoint literal);
    app.js's single api.js import block carries them; the load arm and
    the per-zone retries call them — deleting any link goes red."""

    api = _text("api.js")
    for name, path in (
        ("fetchWorldEnsemble", "/api/world/ensemble"),
        ("fetchWorldStorylines", "/api/world/storylines"),
        ("fetchWorldLog", "/api/world/log"),
    ):
        assert f"export function {name}() {{" in api, name
        assert f'return getJson("{path}");' in api, name
    app = _text("app.js")
    start = app.index('import {\n  fetchTurn,')
    end = app.index('} from "./api.js";', start)
    block = app[start:end]
    for name in ("fetchWorldEnsemble", "fetchWorldStorylines",
                 "fetchWorldLog"):
        assert f"{name}," in block, name
    loader = _function_slice(app, "async function openWorldDetail(")
    assert "readWorldEnsemble()," in loader
    assert "readWorldStorylines()," in loader
    assert "readWorldLog()," in loader
    retry = _function_slice(app, "async function worldZoneRetry(")
    assert "const storylines = await readWorldStorylines();" in retry
    assert "const log = await readWorldLog();" in retry
    assert "const ensemble = await readWorldEnsemble();" in retry
    # 三读包装各自直呼其 fetch（导入覆盖钉的同一形：调用点语法可见）
    for name in ("fetchWorldEnsemble", "fetchWorldStorylines",
                 "fetchWorldLog"):
        wrapper = _function_slice(app, f"async function read{name[5:]}(")
        assert f"return await {name}();" in wrapper, name


def test_the_masthead_world_name_is_the_door() -> None:
    """The masthead entry's two arms: the world arm moves the actionable
    role onto .who (world detail) and the sub row (the stack), the
    fallback arm hands the block back to mc-1's single semantics; the
    .who listener only fires while the world arm is marked and stops the
    event before the block's own toggle."""

    app = _text("app.js")
    assert "let mastheadWorldArmed = false;" in app
    arm = _function_slice(app, "function markMastheadWorldArm(")
    assert 'who.setAttribute("role", "button");' in arm
    assert 'who.setAttribute("tabindex", "0");' in arm
    assert 'who.setAttribute("aria-label", worldLabel || "");' in arm
    assert 'block.removeAttribute("role");' in arm
    assert 'block.setAttribute("role", "button");' in arm
    assert 'block.setAttribute("aria-label", "信封沓——挑一位笔友");' in arm
    world_arm = _function_slice(app, "function renderWorldMasthead(overview)")
    assert "markMastheadWorldArm(" in world_arm
    assert 'T.worldDetailLabel.replace("{world}", who.textContent || "")' \
        in world_arm
    fallback = _function_slice(app, "function renderMasthead(roster)")
    assert "markMastheadWorldArm(false);" in fallback
    door = _function_slice(app, 'const whoName = document.querySelector(')
    # 两道门（click 与 keydown）各自带同一守卫——计数钉让「翻掉其中
    # 一道」也红（M5 变异形态：只剩 keydown 的守卫时计数 1≠2）。
    assert door.count("if (!mastheadWorldArmed) return;") == 2
    assert (
        'whoName.addEventListener("click", (event) => {\n'
        "    if (!mastheadWorldArmed) return;" in door
    )
    assert (
        'whoName.addEventListener("keydown", (event) => {\n'
        "    if (!mastheadWorldArmed) return;" in door
    )
    assert "event.stopPropagation();" in door
    assert "openWorldDetail();" in door
    # the block's own mc-1 wiring survives verbatim (the door is
    # additive; the block's lines are the rd-4/mc-1 pin's own)
    assert (
        'whoBlock.setAttribute("aria-label", "信封沓——挑一位笔友");' in app
    )


def test_the_envelope_caption_carries_the_world_link() -> None:
    """The 沓 entry (R3, minimal): the caption carries an in-line link
    that closes the stack and opens the world screen — the caption's own
    text line and the stack's structure are untouched.

    D-4 迁移：caption 的生产者从 buildEnvelopeResidentsContext（residents
    读）迁到世界臂自己的 buildPeopleCaption（ensemble 一读；同一份
    world_name 一个出处）——壳形态与行内链逐行不动。"""

    app = _text("app.js")
    face = _function_slice(app, "function buildPeopleCaption(")
    assert 'caption.className = "envsel-caption";' in face
    assert (
        'caption.textContent = T.residentsOf.replace("{world}", worldName);'
        in face
    )
    assert 'worldLink.className = "btn btn--faint envsel-world-link";' in face
    assert "worldLink.textContent = T.worldDetail;" in face
    assert (
        "event.stopPropagation();\n    closeEnvelopeSelector();\n"
        "    openWorldDetail();" in face
    )
    assert "caption.appendChild(worldLink);" in face
    assert "stack.parentNode.insertBefore(caption, stack);" in face
    screens = _text("screens.css")
    assert ".envsel-world-link { margin-left: var(--sp-2); }" in screens


# ---------------------------------------------------------------------------
# 5 — the frontend structure: chrome, classes, textContent, the contract
# ---------------------------------------------------------------------------


def test_the_screen_chrome_is_bilingual() -> None:
    """The world chrome table carries the new page's sentences in zh and
    en (the wf-1 table's own law — one world chrome table): the door
    label, the home label, the current mark, the resolve prefix, the
    world-voice signature and the three honest empty sentences."""

    app = _text("app.js")
    for zh, en in (
        ('worldDetail: "看看这个世界 →",', 'worldDetail: "See this world →",'),
        (
            'worldDetailLabel: "世界详情——看看{world}",',
            'worldDetailLabel: "World detail — see {world}",',
        ),
        ('current: "当前通信",', 'current: "In correspondence now",'),
        ('home: "住处",', 'home: "Home",'),
        ('resolve: "了结条件 · {text}",', 'resolve: "Resolves when · {text}",'),
        ('worldVoice: "世界",', 'worldVoice: "The world",'),
        ('noPlayer: "这世界还没写下你的角色。",',
         'noPlayer: "This world has not written your character yet.",'),
        ('noPeople: "这镇上还没有写下可看的人。",',
         'noPeople: "No one is written into this town yet.",'),
        ('noLines: "眼下没有打开的剧情线。",',
         'noLines: "No storyline is open right now.",'),
        ('noChronicle: "编年史还没有翻开过的一页。",',
         'noChronicle: "The chronicle has nothing revealed yet.",'),
    ):
        assert zh in app, zh
        assert en in app, en


def test_the_renderers_speak_text_content_only() -> None:
    """XSS discipline (the page-wide law): every renderer in the D-3
    block writes through textContent / createTextNode — no innerHTML, no
    markup assembly anywhere in the block."""

    app = _text("app.js")
    block = app[
        app.index("// ── D-3 世界详情屏"):
        app.index("// 返回钮：世界详情屏的唯一回途")
    ]
    assert "innerHTML" not in block
    assert "insertAdjacentHTML" not in block
    assert "textContent" in block
    # every renderer reads its payload's own language (one chrome table)
    for head in (
        "function renderWorldYou(",
        "function renderWorldPeople(",
        "function renderWorldLines(",
        "function renderWorldChronicle(",
    ):
        body = _function_slice(block, head)
        assert "parlorWorldText(" in body, head


def test_the_world_screen_classes_have_one_home() -> None:
    """The single-source clause for the new screen classes: they are
    defined in screens.css only (the screen sheet owns screen-level
    layout; components.css and index.html never define them), and the
    sheet stays free of the button-styling words the fg1 audit bans."""

    classes = (
        ".world-name {",
        ".world-you-name {",
        ".world-you-anchor, .world-person-vignette, .world-line-theme,",
        ".world-person, .world-line, .world-day {",
        ".world-person-name {",
        ".world-day-date {",
    )
    screens = _text("screens.css")
    for selector in classes:
        assert selector in screens, selector
        assert selector not in _text("components.css"), selector
        assert selector not in _text("index.html"), selector
    for word in ("button", ".btn", ".linklike"):
        assert word not in screens, word


def test_every_key_the_page_reads_is_a_key_the_payload_carries(
    tmp_path: Path,
) -> None:
    """The three-reads-to-four-zones contract, live: the ensemble feeds
    ①/②, the storylines ③ and the log ④ — each payload carries exactly
    the keys the renderers read (a server-side rename the page would
    silently drop goes red here)."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        _sql(
            app_db,
            (
                (
                    "INSERT INTO world_event (event_id, world_id, kind,"
                    " narration, effects, occurred_at, source)"
                    " VALUES (?, 'world-berrymoor', 'unread_kind', ?, '[]',"
                    " ?, 'test')",
                    ("d3-note-1", "The quay smells of tar.", "2025-09-15"),
                ),
                (
                    "INSERT INTO world_reveal_item (item_id, world_id,"
                    " source_event_id, actor_id, status, revealed_at,"
                    " created_at) VALUES (?, 'world-berrymoor',"
                    " 'd3-note-1', NULL, 'REVEALED', ?, ?)",
                    (
                        "d3-note-1:reveal",
                        "2025-09-15T08:00:00+00:00",
                        NOW,
                    ),
                ),
            ),
        )
        status, ensemble = stack.get_json("/api/world/ensemble")
        status, storylines = stack.get_json("/api/world/storylines")
        status, log = stack.get_json("/api/world/log")
    assert status == 200
    # ①/② — the renderers read `world_name`, `ui_language`,
    # `user_character.{name,anchor,home}`, `cast[*].{name,identity,
    # vignette,is_current,letters_count}`, `residents[*].{name,role,
    # vignette}`.
    assert ensemble["world_name"]
    assert ensemble["ui_language"] in ("zh", "en")
    who = ensemble["user_character"]
    assert {"name", "anchor", "home"} <= set(who)
    for row in ensemble["cast"]:
        assert {
            "name",
            "identity",
            "vignette",
            "is_current",
            "letters_count",
        } <= set(row)
    for row in ensemble["residents"]:
        assert {"name", "role", "vignette"} <= set(row)
    # ③ — `ui_language` + `storylines[*].{theme,resolve_at}`
    assert storylines["ui_language"] in ("zh", "en")
    for line in storylines["storylines"]:
        assert {"theme", "resolve_at"} <= set(line)
    # ④ — `ui_language` + `days[*].{date_localized,items[*].{narration,
    # signature}}`
    assert log["ui_language"] in ("zh", "en")
    assert log["days"], "the injected revealed note must show a day"
    day = log["days"][0]
    assert "date_localized" in day and day["date_localized"]
    item = day["items"][0]
    assert {"narration", "signature"} <= set(item)
    assert item["narration"] == "The quay smells of tar."


# ---------------------------------------------------------------------------
# 6 — the read-only posture (AST over the live source)
# ---------------------------------------------------------------------------


def test_the_new_faces_are_read_only() -> None:
    """AST-level: the two new faces and the binding helper the family
    shares call no store write face and never flip a reveal. The
    positive control: the inbox's own reveal call is still counted, and
    the audit sees the family's reads (a silently widened set is a red
    walker)."""

    source = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    face = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_WebFace"
    )
    methods = {
        node.name: node
        for node in face.body
        if isinstance(node, ast.FunctionDef)
    }

    def called_names(name: str) -> set[str]:
        return {
            node.func.attr
            for node in ast.walk(methods[name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }

    write_prefixes = (
        "reveal_all",
        "resolve_",
        "create_",
        "record_",
        "enqueue_",
        "bind_",
        "checkpoint_",
        "terminalize_",
        "adopt_",
        "write_",
    )
    for name in (
        "world_ensemble",
        "world_storylines",
        "_world_bindings_by_actor",
    ):
        calls = called_names(name)
        assert "reveal_all" not in calls, name
        for prefix in write_prefixes:
            hit = {call for call in calls if call.startswith(prefix)}
            assert not hit, (name, hit)
    assert "reveal_all" in called_names("world_inbox")   # positive control
    assert "active_storylines" in called_names("world_storylines")
    assert "list_storylines" not in called_names("world_storylines")
