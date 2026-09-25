"""The minimum CLI (prep-1 deliverable D) — usage errors, one turn, no server.

Three cases: usage errors answer a human message and a non-zero code; one
scripted turn prints the reply, lands in app.db and exits 0 on ``:quit``; and a
source scan over ``src/elc`` proves the two structural promises — **no server
and one egress point** — with a negative control (the adapter really is the one
module that imports ``urllib``).
"""

from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest

from elc.cli import main
from elc.host import Host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db import connection
from tests.conftest import SRC_ROOT

CLI_REPLY = "cli reply from the scripted provider"


def run(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err, **kwargs)  # type: ignore[arg-type]
    return code, out.getvalue(), err.getvalue()


def _call_surface(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    """``(bare calls, dotted calls, attribute names)`` of one syntax tree.

    ``_opener()`` lands in *bare calls*, ``urllib.request.build_opener(...)`` in
    *dotted calls*, and ``_opener().open(...)`` contributes ``"open"`` to
    *attribute names* — enough to pin the egress posture structurally, without
    letting prose satisfy or break the pin (prep-1R review F4).
    """

    bare: set[str] = set()
    dotted: set[str] = set()
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            bare.add(func.id)
            continue
        if not isinstance(func, ast.Attribute):
            continue
        attrs.add(func.attr)
        parts = [func.attr]
        root: ast.expr = func.value
        while isinstance(root, ast.Attribute):
            parts.append(root.attr)
            root = root.value
        if isinstance(root, ast.Name):
            parts.append(root.id)
        dotted.add(".".join(reversed(parts)))
    return bare, dotted, attrs


def _build_opener_takes_no_redirects(tree: ast.AST) -> bool:
    """Does some ``...build_opener(<no-redirects handler>)`` call exist?
    (Any spelling of the handler name; the handler class itself is pinned by
    the adapter's own tests.)"""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "build_opener"):
            continue
        for argument in node.args:
            if isinstance(argument, ast.Name) and argument.id == "_NoRedirects":
                return True
    return False


def test_usage_errors_are_human_and_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = [
        "chat",
        "--app-db",
        str(tmp_path / "app.db"),
        "--base-url",
        "https://offline.invalid/v1",
        "--model",
        "offline-model",
    ]
    vectors = {
        "missing-required": ["chat", "--app-db", str(tmp_path / "app.db")],
        "both-key-sources": base + ["--api-key-env", "V", "--secrets-file", "s.json"],
        "neither-key-source": base,
        "unknown-command": base[:0] + ["serve"],
    }
    for name, argv in vectors.items():
        code, _, injected = run(argv, stdin=io.StringIO(""))
        # argparse writes to the real stderr; the mutual-exclusion check writes
        # to the injected one — both must be human, and both must be non-zero.
        message = injected + capsys.readouterr().err
        assert code == 2, (name, code)
        assert message.strip(), (name, message)


def test_a_scripted_turn_prints_the_reply_and_quit_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PREP1_UNSET_KEY_VAR", raising=False)
    # F4: the REPL's first move is one startup recovery — pinned so deleting
    # that call turns this red (a recovery that never runs cannot be observed
    # in the output otherwise).
    recovery_calls: list[object] = []
    real_recovery = Host.startup_recovery

    def recording_recovery(self: Host) -> object:
        recovery_calls.append(self.epoch)
        return real_recovery(self)

    monkeypatch.setattr(Host, "startup_recovery", recording_recovery)

    db_path = tmp_path / "app.db"
    provider = ScriptedPersonaProvider(script=(ProviderOutput(text=CLI_REPLY),))
    code, out, err = run(
        [
            "chat",
            "--app-db",
            str(db_path),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "PREP1_UNSET_KEY_VAR",
            "--conversation",
            "cli-test",
        ],
        stdin=io.StringIO("hello cli\n:quit\n"),
        provider=provider,
    )
    assert (code, err) == (0, "")
    assert recovery_calls == [1]  # exactly one, before the first turn
    lines = out.splitlines()
    assert lines[0].startswith("elc chat · conversation=cli-test · epoch=1")
    assert lines[1] == CLI_REPLY
    assert provider.call_count == 1

    db = connection.connect(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0] == 1
        row = db.execute("SELECT content FROM assistant_turn").fetchone()
        assert row is not None and row[0] == CLI_REPLY
    finally:
        db.close()


def test_the_only_egress_point_and_no_server() -> None:
    """R5/R6 as a **structural** source scan: no network client or server
    machinery anywhere in ``src``, exactly one module reaches for
    ``urllib.request`` — the adapter whose single ``_urllib_post`` is the whole
    network surface — and that module still contains the call that leaves the
    process.

    The net is wide on purpose (prep-1 review F2): third-party HTTP clients
    belong in the forbidden set next to ``socket``/``http``, and the negative
    control is *symbol*-level — the adapter is required to import
    ``urllib.request`` **and** to keep its own egress call — so deleting the
    real egress implementation cannot leave this pin green.

    This is a structural guard over the import and attribute surface, not a
    sandbox: a module that reached the network through ``subprocess``,
    ``ctypes`` or a socket assembled dynamically from strings (``getattr`` /
    ``importlib`` / ``__import__``) would not be caught here. ``src`` is the
    scan's whole scope by design — ``tests/`` may build ``Request`` objects
    (the redirect pins do) and this pin claims nothing about them (prep-1R).
    """

    forbidden: set[str] = set()
    urllib_request_importers: set[str] = set()
    network_roots = {
        "socket",
        "http",
        "socketserver",
        "asyncio",
        "ssl",
        "requests",
        "httpx",
        "urllib3",
        "aiohttp",
        "ftplib",
        "smtplib",
        "imaplib",
        "poplib",
        "telnetlib",
        "xmlrpc",
    }
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(SRC_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root_name = name.split(".")[0]
                if name == "urllib.request":
                    urllib_request_importers.add(rel)
                if root_name in network_roots:
                    forbidden.add(f"{rel}: {name}")

    assert forbidden == set()
    # Negative control, symbol level: the one module that may reach the network
    # imports urllib.request, builds its own opener and calls it — asserted over
    # the **syntax tree**, so a mention of any of these names in prose neither
    # satisfies nor breaks the pin (prep-1R review F4: the first version's
    # substring checks made a docstring sentence able to turn this red).
    assert urllib_request_importers == {"persona/openai_provider.py"}
    adapter_tree = ast.parse(
        (SRC_ROOT / "persona" / "openai_provider.py").read_text(encoding="utf-8")
    )
    bare_calls, dotted_calls, attribute_names = _call_surface(adapter_tree)
    assert "_opener" in bare_calls  # the module's own opener factory is used
    assert "open" in attribute_names  # ...as an opener call, not a global one
    assert "urlopen" not in attribute_names  # never urllib.request.urlopen(...)
    assert "install_opener" not in attribute_names  # never the process-wide one
    assert "add_unredirected_header" in attribute_names
    assert "urllib.request.build_opener" in dotted_calls
    assert _build_opener_takes_no_redirects(adapter_tree)


def test_a_plaintext_base_url_off_this_machine_is_refused_with_a_sentence(
    tmp_path: Path,
) -> None:
    """prep-1R (EXT-P1-02) as the operator feels it: exit code 2, a sentence
    naming the way out, and **no host opened** — the refusal precedes the
    app.db, so a refused destination costs nothing."""

    code, _, err = run(
        [
            "chat",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "http://evil.example/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "PREP1_UNSET_KEY_VAR",
        ],
        stdin=io.StringIO(""),
    )
    assert code == 2
    assert "--allow-insecure-http" in err
    assert not (tmp_path / "app.db").exists()


def test_a_malformed_base_url_is_a_sentence_not_a_traceback(
    tmp_path: Path,
) -> None:
    """prep-1R review F2, the operator's half: ``urlsplit`` refuses
    ``http://[::1``, and the pre-check must answer the way it answers every
    other refused destination — a sentence and exit 2 — rather than letting a
    ``ValueError`` traceback out of ``main`` (the first version did exactly
    that)."""

    code, _, err = run(
        [
            "chat",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "http://[::1",
            "--model",
            "offline-model",
            "--api-key-env",
            "PREP1_UNSET_KEY_VAR",
        ],
        stdin=io.StringIO(""),
    )
    assert code == 2
    assert "Traceback" not in err
    assert "--allow-insecure-http" in err
    assert not (tmp_path / "app.db").exists()


def test_the_opt_in_and_loopback_plaintext_both_reach_the_host(
    tmp_path: Path,
) -> None:
    """``--allow-insecure-http`` is exactly what the pre-check asks for, and
    loopback never needs it: both open a host and exit 0 at EOF. No turn is
    committed, so the provider is never called and no request is made."""

    vectors = (
        ("http://evil.example/v1", ["--allow-insecure-http"]),
        ("http://127.0.0.1:11434/v1", []),
    )
    for index, (base_url, extra) in enumerate(vectors):
        code, out, err = run(
            [
                "chat",
                "--app-db",
                str(tmp_path / f"app-{index}.db"),
                "--base-url",
                base_url,
                "--model",
                "offline-model",
                "--api-key-env",
                "PREP1_UNSET_KEY_VAR",
                "--conversation",
                "cli-http",
            ]
            + extra,
            stdin=io.StringIO(""),
        )
        assert (code, err) == (0, ""), (base_url, code, err)
        assert out.startswith("elc chat · conversation=cli-http"), base_url
