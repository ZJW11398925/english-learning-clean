"""The F-G1 architecture face — the static split, the component library's
single sources and the frontend spec's governance clauses, pinned.

Three groups (the task book's own):

1. **architecture** — the seven webui files exist; ``elc.web`` no longer
   embeds a page constant; the three Content-Types are served as spelled;
   the static face fails closed (an unknown asset name and a raw
   traversal path answer 404 with a human sentence, never 500 and never
   file bytes); zero external resources holds per file; the shell links
   its assets with ``<link>`` and one ``type="module"`` script; the
   served bytes equal the repo's bytes.
2. **component library** — the contract blocks exist for every registered
   component (fifteen since p-1); every core component class's style is
   defined exactly once across the whole webui tree (the alias selectors
   included); screens.css defines no button styling and app.js no inline
   styling (the button unification); the interactive components carry
   their state words (the completeness gate).
3. **spec** — ``docs/FRONTEND_SPEC.md`` exists with its seven section
   headers, names every registered component, carries the
   library-as-living-registry clause, and AGENTS.md carries the
   governance clause.

Every page-source *string* pin lives where it always lived (the W/F
suites, now reading :func:`tests.host.test_w1_web._page_source`'s
union) — this file pins the architecture around that source.
"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import elc.web
from tests.host.test_w1_web import _OPENER, _Stack, web_stack

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = Path(elc.web.__file__).parent / "webui"

#: The static face's whole inventory — the seven files, name → the
#: Content-Type the server must spell for it (the server's own allowlist
#: is pinned separately; this is the on-disk half).
FILES: dict[str, str] = {
    "index.html": "text/html; charset=utf-8",
    "tokens.css": "text/css; charset=utf-8",
    "components.css": "text/css; charset=utf-8",
    "screens.css": "text/css; charset=utf-8",
    "api.js": "text/javascript; charset=utf-8",
    "components.js": "text/javascript; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}

#: The registered components, in contract order — the numbering in
#: components.css's contract blocks and the spec's table must both carry
#: them (a renamed or dropped component breaks both pins at once).
#: The registry is living (spec ⑤): F-G2 added brand-mark and
#: state-banner, p-1 added word-card, p-3 added field and chip, R-1
#: added the shell navigation trio (dock / space-header / section-tabs)
#: — each in the same cut that registered it in the spec.
COMPONENTS = (
    "link-btn",
    "pen",
    "note-paper",
    "letter",
    "hairline-section",
    "setlink-block",
    "resultstrip",
    "busystrip",
    "meter-row",
    "empty-state",
    "confirm-dialog",
    "system-line",
    "brand-mark",
    "state-banner",
    "word-card",
    "field",
    "chip",
    "dock",
    "space-header",
    "section-tabs",
)


def _webui_text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _webui_all_text() -> str:
    """Every webui file's text, joined — the corpus for the single-source
    counts (a definition twice anywhere in the tree is twice)."""

    return "\n".join(_webui_text(name) for name in FILES)


def _get_any(
    stack: _Stack, path: str
) -> tuple[int, str, bytes]:
    """GET with the 404 arm answered (urllib turns a 404 into HTTPError;
    the pin wants the status, the type and the human body)."""

    request = urllib.request.Request(f"http://127.0.0.1:{stack.port}{path}")
    try:
        with _OPENER.open(request, timeout=30) as response:
            return (
                response.status,
                response.headers.get("Content-Type") or "",
                response.read(),
            )
    except urllib.error.HTTPError as exc:
        return (
            exc.code,
            exc.headers.get("Content-Type") or "",
            exc.read(),
        )


# ---------------------------------------------------------------------------
# 1. the architecture


def test_the_seven_webui_files_exist_with_the_served_types(
    tmp_path: Path,
) -> None:
    """The split is real: every file is on disk next to elc.web, and the
    server answers each with exactly the Content-Type the allowlist
    spells (html / css / javascript — the trio the task book names)."""

    for name in FILES:
        assert (WEBUI / name).is_file(), name
    with web_stack(tmp_path / "app.db") as stack:
        for name, ctype in FILES.items():
            status, served, _ = _get_any(stack, f"/static/{name}")
            if name == "index.html":
                status, served, _ = _get_any(stack, "/")
            assert status == 200, name
            assert served == ctype, (name, served, ctype)


def test_web_py_no_longer_embeds_the_page() -> None:
    """The once-embedded page constant is gone from the Python module —
    the static face is data next to it, not a string inside it."""

    source = Path(elc.web.__file__).read_text(encoding="utf-8")
    assert "_PAGE = " not in source
    assert "_WEBUI_ROOT" in source
    assert "_STATIC_TYPES" in source


def test_the_shell_links_its_assets_and_is_served_byte_equal(
    tmp_path: Path,
) -> None:
    """The shell is an HTML skeleton: three stylesheet links, one module
    script, no inline style and no inline script — and what the server
    serves is byte-equal to what the repo holds (per-request read, no
    transform)."""

    index = _webui_text("index.html")
    assert '<link rel="stylesheet" href="/static/tokens.css">' in index
    assert '<link rel="stylesheet" href="/static/components.css">' in index
    assert '<link rel="stylesheet" href="/static/screens.css">' in index
    assert '<script type="module" src="/static/app.js"></script>' in index
    assert "<style" not in index
    assert "<script>" not in index
    with web_stack(tmp_path / "app.db") as stack:
        _, _, served = _get_any(stack, "/")
        assert served == (WEBUI / "index.html").read_bytes()
        _, _, asset = _get_any(stack, "/static/app.js")
        assert asset == (WEBUI / "app.js").read_bytes()


def test_the_static_face_fails_closed(tmp_path: Path) -> None:
    """A name outside the allowlist and a raw traversal path both answer
    404 with a human JSON sentence — never 500, never a bare traceback,
    never another file's bytes (the raw-socket probe sends the path
    unnormalized, so no client-side path cleaning can mask the answer)."""

    with web_stack(tmp_path / "app.db") as stack:
        for path in ("/static/nope.css", "/static/../../web.py", "/static/"):
            status, ctype, body = _get_any(stack, path)
            assert status == 404, (path, status)
            assert status < 500, path
            assert ctype.startswith("application/json"), path
            error = json.loads(body.decode("utf-8"))["error"]
            assert error, path
        # the raw path, unnormalized: the allowlist rejects it untouched
        connection = http.client.HTTPConnection("127.0.0.1", stack.port, timeout=30)
        connection.request("GET", "/static/../web.py")
        response = connection.getresponse()
        assert response.status == 404
        payload = json.loads(response.read().decode("utf-8"))
        assert "web.py" not in json.dumps(payload)
        connection.close()


def test_a_missing_allowlisted_file_fails_closed(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """Review LOW-1: the allowlist can pass while the file itself is gone
    (a truncated install, a stray delete). That arm — the OSError inside
    the per-request read — must answer the same 404 JSON human sentence
    as an unknown name, never a 500 traceback. The root is monkeypatched
    to a copy missing one file, so the repo tree is never touched."""

    import shutil

    short_root = tmp_path / "webui-short"
    short_root.mkdir()
    for name in FILES:
        if name != "screens.css":
            shutil.copy2(WEBUI / name, short_root / name)
    monkeypatch.setattr(elc.web, "_WEBUI_ROOT", short_root)

    with web_stack(tmp_path / "app.db") as stack:
        status, ctype, body = _get_any(stack, "/static/screens.css")
        assert status == 404
        assert status < 500
        assert ctype.startswith("application/json")
        error = json.loads(body.decode("utf-8"))["error"]
        assert error
        # the surviving half of the face still serves
        status, ctype, body = _get_any(stack, "/static/tokens.css")
        assert status == 200
        assert ctype.startswith("text/css")


def test_zero_external_resources_per_file() -> None:
    """The zero-external law, file by file: no off-site scheme and no CSS
    import anywhere in webui/ (the union pin lives in
    test_f1_product_shell; this is the per-file half)."""

    for name in FILES:
        text = _webui_text(name)
        assert "http://" not in text, name
        assert "https://" not in text, name
        if name.endswith(".css"):
            assert "@import" not in text, name


# ---------------------------------------------------------------------------
# 2. the component library


def test_the_contract_blocks_exist() -> None:
    """Each component owns one numbered contract block in components.css
    (structure / state matrix / usage rules / forbidden variants), in the
    spec's order — the block count is the registry's length, so a
    same-cut registration is the only way a new component passes."""

    css = _webui_text("components.css")
    for number, name in enumerate(COMPONENTS, start=1):
        assert f"{number}. {name}" in css, (number, name)
    # the four contract clauses, once per component (the file header's
    # rule line names them without the colon — blocks carry the colon)
    assert css.count("状态矩阵：") == len(COMPONENTS)
    assert css.count("使用规则：") == len(COMPONENTS)
    assert css.count("禁止变体：") == len(COMPONENTS)


def test_core_component_styles_have_exactly_one_source() -> None:
    """The single-source clause, mechanical: a style definition for a core
    component class occurs exactly once across the whole webui tree —
    components.css owns it; screens.css and index.html may reference a
    class but never define it (the alias selectors count as the one
    definition they belong to)."""

    whole = _webui_all_text()
    for selector in (
        ".pen {",
        ".note-paper {",
        ".resultstrip.ok {",
        ".resultstrip.miss {",
        ".busystrip {",
        ".sysline {",
        ".letter {",
        ".sec {",
        ".setlinks {",
        ".kv {",
        ".note {",
        ".btn[disabled] {",
    ):
        assert whole.count(selector) == 1, (selector, whole.count(selector))


def test_screens_and_app_define_no_button_styling() -> None:
    """The button unification: every button look lives in components.css's
    link-btn family — the screen sheet has no button rule (the old
    scattered classes are aliases there, not new definitions) and the app
    module styles nothing inline."""

    screens = _webui_text("screens.css")
    assert "button" not in screens
    assert ".btn" not in screens
    assert ".send" not in screens
    assert ".setlink" not in screens
    assert ".skiplink" not in screens
    assert ".refresh" not in screens
    assert ".back" not in screens
    assert ".meter" not in screens
    assert ".linklike" not in screens
    app = _webui_text("app.js")
    assert ".style" not in app
    assert "text-decoration" not in app


def test_interactive_components_carry_their_states() -> None:
    """The completeness gate (spec ⑥): an interactive component defines
    more than its default state — the state words are in the CSS, the
    busy wording rides the JS side."""

    css = _webui_text("components.css")
    for state in (
        ".btn[disabled] {",  # link-btn: disabled
        ".btn--ink:active",  # link-btn: active
        ".note-paper.skipped",  # note-paper: skipped
        ".replytext:focus",  # note-paper's reply face: focus
        ".resultstrip.ok",  # resultstrip: the three verdicts
        ".resultstrip.part",
        ".resultstrip.miss",
        ".pen::placeholder",  # pen: placeholder
        ".navdock-item--on {",  # dock (R-1): active
        ".navdock-item[disabled] {",  # dock: disabled
        ".section-tab--on {",  # section-tabs (R-1): selected
    ):
        assert state in css, state
    # section-tabs' focus arm rides the foundation's pencil ring (the
    # R-1 contract names it; the ring itself is the ground rule's)
    assert (
        "button:focus-visible, input:focus-visible {\n"
        "  outline: 1px solid var(--pencil); outline-offset: 2px; }" in css
    )
    app = _webui_text("components.js")
    assert "批改中…" in app  # the busy wording (busystrip's live face)
    assert "button.disabled = busy" in app  # the disabled state, driven


# ---------------------------------------------------------------------------
# 3. the spec


def test_the_frontend_spec_exists_and_governs() -> None:
    """docs/FRONTEND_SPEC.md: the seven sections, every registered
    component name, the uniqueness clause and the living-registry
    doctrine — and the AGENTS.md governance clause that makes the spec
    binding for every later frontend cut."""

    spec = (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    for header in (
        "## ① 地位与治理",
        "## ② Token 语义表",
        "## ③ 组件契约",
        "## ④ 命名法",
        "## ⑤ 库唯一出处条款",
        "## ⑥ 状态完备性硬门",
        "## ⑦ 架构说明",
    ):
        assert header in spec, header
    for name in COMPONENTS:
        assert name in spec, name
    assert "重复实现 = 评审 finding（拒收事由）" in spec
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "前端治理（`DEC-OPI-631452f9" in agents
    assert "docs/FRONTEND_SPEC.md" in agents
    assert "新组件须同刀登记 spec" in agents
