"""The minimum CLI (prep-1): one process, one conversation, no HTTP server.

``python -m elc chat --app-db … --base-url … --model … [--api-key-env VAR |
--secrets-file PATH] [--allow-insecure-http]`` opens the real host
(``elc.host``), runs the startup recovery once, then reads lines: one line is
one ``CommitUserTurn`` through
``ConversationCoordinator.begin_turn``, and the reply — or the honest failure —
is printed. ``:quit`` or EOF exits and closes the connection.

``python -m elc gate --content-db PATH`` (D-5) is the corpus rollout gate over
one built content.db — no host, no app.db, no key: it reads the readiness
table and the artifact's own provenance rows, prints the report (the four
rows, the targets line, the verdict) and codes the verdict as the exit status
(GO = 0, HOLD = 1). The report is the content leg's answer only; a GO here
opens nothing, and the note it prints names what stays outside this command's
answer (the stage declaration, the session-budget split, the opening
adjudication).

Deliberate limits, each a contract rather than an omission:

- **in-process only.** This is the client boundary ``DEC-…d7937fd7.12``
  postponed: V1's surface is the process-internal Python API, so the CLI never
  starts an HTTP server and never listens on a port — the only egress it can
  cause is the provider adapter's single POST;
- **the key is never an argument.** ``--api-key-env`` / ``--secrets-file``
  point at a source (``elc.platform.secrets``); the value is resolved at send
  time and appears in no output, message or table. The two flags are mutually
  exclusive and one of them is required;
- **usage errors are human and non-zero**: a missing argument, both sources or
  neither returns 2, an un-openable app.db returns 1. A lost model connection
  does *not* abort the loop — the provider contract answers a value, so a
  failed turn reports its reason and the next line is read normally.
- **plaintext is refused off this machine.** A non-loopback ``http://``
  base-url answers exit code 2 and a sentence naming ``--allow-insecure-http``;
  loopback (``localhost`` / ``127.0.0.0/8`` / ``::1``) needs no flag, and
  ``https://`` is never questioned. The flag is never implied — the adapter
  behind this CLI reads the same predicate and would otherwise answer the turn
  with the ``cleartext-http`` value (EXT-P1-02).

One user-visible consequence of the secret seam's value contract, said out
loud (prep-1 review F8): a wrong ``--secrets-file`` path, a JSON file without
the requested ``--secret-ref`` and a genuinely unset key are *one* fact to this
CLI — each is ``None`` at the seam, so each prints ``[FAILED_FINAL]
missing-secret``. The message says what the adapter knows, not where the
config went wrong.

``provider=`` is the one injection point: it exists so ``tests/host`` can drive
an offline process, and the process entry (``elc.__main__``) never passes it.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence, TextIO

from elc.content.build import DEFAULT_OUTPUT
from elc.content.store import ContentStore, ContentStoreError
from elc.conversation.types import CommitUserTurn
from elc.curriculum.store import CurriculumContentStore
from elc.host import Host, open_host
from elc.persona.openai_provider import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    insecure_http_destination,
)
from elc.persona.provider import PersonaProvider
from elc.platform.db.migrations import MigrationError
from elc.platform.secrets import EnvSecretSource, FileSecretSource, SecretSource
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    Err,
    InputId,
    InteractionChannel,
    Result,
    RuntimeVersion,
    SecretRef,
)
from elc.runtime.types import InputEnvelope, TurnCompletion
from elc.teaching.rollout import RolloutVerdict, corpus_rollout_gate

__all__ = [
    "DEFAULT_CONVERSATION_ID",
    "DEFAULT_SECRET_REF",
    "RUNTIME_VERSION",
    "main",
]

#: The version every turn this CLI commits carries (§1.4's ``runtime_version``;
#: the value the rest of the V1 tree uses).
RUNTIME_VERSION = RuntimeVersion("runtime-v1")

#: The default ``secret_ref`` resolved inside the chosen source.
DEFAULT_SECRET_REF = "api-key"

#: The default conversation the REPL opens (idempotent; reused across runs).
DEFAULT_CONVERSATION_ID = "cli-default"

_QUIT_WORDS = frozenset({":quit", ":q"})

_KEY_SOURCE_HINT = (
    "elc chat: one of --api-key-env VAR or --secrets-file PATH is required"
    " (the BYOK key source; the key itself is never an argument)"
)

_INSECURE_HTTP_HINT = (
    "elc chat: --base-url is plaintext http:// off this machine, so the key"
    " would travel in the clear; pass --allow-insecure-http to allow it"
    " explicitly (loopback http:// needs no flag)"
)

_CHAT_REQUIRED_HINT = (
    "elc chat: --app-db, --base-url and --model are required"
    " (the gate command needs none of them)"
)

_GATE_LEG_NOTE = (
    "provenance leg live: the automatic CURRENT_USER_ERROR row also requires"
    " EXECUTABLY_VERIFIED provenance (its blocked count is in the row above)"
)

_GATE_SCOPE_NOTE = (
    "this report is the content leg's answer only; rollout stays a separate"
    " decision (the stage declaration, the session-budget split and the"
    " opening adjudication live outside it) — a GO here opens nothing"
)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    provider: PersonaProvider | None = None,
) -> int:
    """Run the CLI and answer the process exit code (never raises for usage)."""

    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:  # argparse's own usage errors: human + non-zero
        return int(exc.code) if isinstance(exc.code, int) else 2

    if args.command == "gate":
        return _gate(args, stdout=out, stderr=err)

    # chat's required arguments are validated here rather than by argparse so
    # the gate command can share one flat parser without them (a missing
    # --base-url stays a human sentence and a 2, only now from this check).
    if args.app_db is None or args.base_url is None or args.model is None:
        print(_CHAT_REQUIRED_HINT, file=err)
        return 2
    app_db: str = args.app_db
    base_url: str = args.base_url
    model: str = args.model
    if (args.api_key_env is None) == (args.secrets_file is None):
        print(_KEY_SOURCE_HINT, file=err)
        return 2
    if not args.allow_insecure_http and insecure_http_destination(base_url):
        # Before any host is opened and before any key is resolved: the rule the
        # adapter answers as a ``cleartext-http`` value, said as a sentence that
        # names the way out (EXT-P1-02).
        print(_INSECURE_HTTP_HINT, file=err)
        return 2
    secrets = _secret_source(args)
    if provider is None:
        provider = OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url=base_url,
                model=model,
                secret_ref=SecretRef(args.secret_ref),
                timeout_seconds=args.timeout,
                allow_insecure_http=args.allow_insecure_http,
            ),
            secrets,
        )

    try:
        host = open_host(app_db, provider=provider, secrets=secrets)
    except (sqlite3.Error, MigrationError, OSError) as exc:
        print(f"elc chat: cannot open app.db {app_db}: {exc}", file=err)
        return 1
    try:
        return _chat(host, args, stdin=stdin, stdout=out, stderr=err)
    finally:
        host.close()


def _chat(
    host: Host,
    args: argparse.Namespace,
    *,
    stdin: TextIO | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Startup recovery, then one turn per line until ``:quit`` / EOF."""

    conversation_id = ConversationId(args.conversation)
    opened = host.open_conversation(conversation_id)
    if isinstance(opened, Err):
        print(
            f"elc chat: cannot open conversation {args.conversation}:"
            f" {opened.error.code.value}: {opened.error.message}",
            file=stderr,
        )
        return 1

    recovery = host.startup_recovery()
    if isinstance(recovery, Err):
        # The recovery lines are failure-tolerant by contract, but a refusal to
        # scan at all is said out loud; the chat goes on.
        print(
            "elc chat: startup recovery unavailable:"
            f" {recovery.error.code.value}: {recovery.error.message}",
            file=stderr,
        )

    print(
        f"elc chat · conversation={conversation_id} · epoch={host.epoch}"
        " · type ':quit' (or EOF) to exit",
        file=stdout,
    )
    stream = stdin if stdin is not None else sys.stdin
    while True:
        try:
            line = stream.readline()
        except KeyboardInterrupt:
            break
        if line == "":
            break
        text = line.rstrip("\n").rstrip("\r")
        if text.strip() in _QUIT_WORDS:
            break
        if not text.strip():
            continue
        result = host.coordinator.begin_turn(_commit(conversation_id, text))
        print(_render(result), file=stdout)
        stdout.flush()
    return 0


def _commit(conversation_id: ConversationId, raw_content: str) -> CommitUserTurn:
    """One CP0 command: a fresh envelope per turn plus the user's line.

    The two ids are minted per turn, so re-running the CLI never collides with a
    previous run's ``client_message_id`` (which would make CP0 replay the old
    turn instead of answering this one).
    """

    suffix = uuid.uuid4().hex
    return CommitUserTurn(
        conversation_id=conversation_id,
        envelope=InputEnvelope(
            input_id=InputId(f"cli-{suffix}"),
            client_message_id=ClientMessageId(f"cli-msg-{suffix}"),
            conversation_id=str(conversation_id),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=raw_content,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=raw_content,
        runtime_version=RUNTIME_VERSION,
    )


def _render(result: Result[TurnCompletion]) -> str:
    """What one turn prints: the reply, or the durable word it ended on."""

    if isinstance(result, Err):
        return f"[error] {result.error.code.value}: {result.error.message}"
    completion = result.value
    if completion.reply_text is not None:
        return completion.reply_text
    reason = completion.failure_reason or "no reply"
    return f"[{completion.turn_status.value}] {reason}"


def _gate(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """The corpus rollout gate over one built content.db (the ``gate`` command).

    No host, no app.db, no key: the artifact and nothing else. The report is
    printed verbatim (the four rows, the targets line, the verdict), then the
    two notes — the provenance leg's live status and what this answer does
    not own. Exit codes: GO 0, HOLD 1. An artifact this command cannot open,
    or one whose reads fail, is also 1 with the reason on stderr — a failed
    read is not a HOLD and is never printed as one (the checker's own Err
    passthrough contract).
    """

    try:
        content_store = ContentStore(args.content_db)
    except (ContentStoreError, sqlite3.Error, OSError) as exc:
        print(
            f"elc gate: cannot open content.db {args.content_db}: {exc!r}",
            file=stderr,
        )
        return 1
    try:
        curriculum = CurriculumContentStore(content_store)
        provenance = content_store.provenance_levels()
        if isinstance(provenance, Err):
            print(
                "elc gate: content_provenance unreadable:"
                f" {provenance.error.message}",
                file=stderr,
            )
            return 1
        report = corpus_rollout_gate(
            curriculum, provenance=dict(provenance.value)
        )
    finally:
        content_store.close()
    if isinstance(report, Err):
        print(
            f"elc gate: the corpus has no gate answer: {report.error.message}",
            file=stderr,
        )
        return 1
    for line in report.value.summary():
        print(line, file=stdout)
    print(_GATE_LEG_NOTE, file=stdout)
    print(_GATE_SCOPE_NOTE, file=stdout)
    return 0 if report.value.verdict is RolloutVerdict.GO else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m elc",
        description="One in-process conversation loop over app.db (no HTTP server).",
    )
    parser.add_argument(
        "command",
        choices=("chat", "gate"),
        help="chat: the conversation loop; gate: the corpus rollout gate",
    )
    parser.add_argument(
        "--app-db",
        help="path to app.db (chat; created and migrated when absent)",
    )
    parser.add_argument(
        "--content-db",
        default=str(DEFAULT_OUTPUT),
        help=(
            "path to a built content.db (gate;"
            " default: the repository build artifact)"
        ),
    )
    parser.add_argument(
        "--base-url",
        help="OpenAI-compatible base URL (PC §11)",
    )
    parser.add_argument(
        "--allow-insecure-http",
        action="store_true",
        help=(
            "explicitly allow a plaintext http:// base-url off this machine;"
            " loopback http:// needs no flag and the default refuses the rest"
        ),
    )
    parser.add_argument("--model", help="model name to request")
    key_source = parser.add_mutually_exclusive_group()
    key_source.add_argument(
        "--api-key-env", metavar="VAR", help="resolve the key from variable VAR"
    )
    key_source.add_argument(
        "--secrets-file",
        metavar="PATH",
        help='resolve the key from a JSON file {"<ref>": "<key>"}',
    )
    parser.add_argument(
        "--secret-ref",
        default=DEFAULT_SECRET_REF,
        help="ref to resolve inside the chosen source (default: %(default)s)",
    )
    parser.add_argument(
        "--conversation",
        default=DEFAULT_CONVERSATION_ID,
        help="conversation id (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="provider timeout in seconds (default: %(default)s)",
    )
    return parser


def _secret_source(args: argparse.Namespace) -> SecretSource:
    if args.api_key_env is not None:
        return EnvSecretSource(var=args.api_key_env)
    return FileSecretSource(path=Path(args.secrets_file))
