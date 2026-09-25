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
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db import connection
from tests.conftest import SRC_ROOT

CLI_REPLY = "cli reply from the scripted provider"


def run(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err, **kwargs)  # type: ignore[arg-type]
    return code, out.getvalue(), err.getvalue()


def test_usage_errors_are_human_and_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = [
        "chat",
        "--app-db",
        str(tmp_path / "app.db"),
        "--base-url",
        "http://offline.invalid/v1",
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
    db_path = tmp_path / "app.db"
    provider = ScriptedPersonaProvider(script=(ProviderOutput(text=CLI_REPLY),))
    code, out, err = run(
        [
            "chat",
            "--app-db",
            str(db_path),
            "--base-url",
            "http://offline.invalid/v1",
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
    """R5/R6 as a source scan: no socket/server machinery anywhere in ``src``,
    and exactly one module reaches for ``urllib`` — the adapter whose single
    ``_urllib_post`` is the whole network surface."""

    forbidden: set[str] = set()
    urllib_importers: set[str] = set()
    network_roots = {"socket", "http", "socketserver", "asyncio", "ssl"}
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
                if root_name == "urllib":
                    urllib_importers.add(rel)
                if root_name in network_roots:
                    forbidden.add(f"{rel}: {name}")

    assert forbidden == set()
    # Negative control: the pin would also fail if the adapter stopped using
    # urllib — the egress point is asserted to exist, not just to be alone.
    assert urllib_importers == {"persona/openai_provider.py"}
