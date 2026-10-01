"""The minimum CLI (prep-1): one process, one conversation, no HTTP server.

``python -m elc chat --app-db … --base-url … --model … [--api-key-env VAR |
--secrets-file PATH] [--allow-insecure-http]`` opens the real host
(``elc.host``), runs the startup recovery once, then reads lines: one line is
one ``CommitUserTurn`` through
``ConversationCoordinator.begin_turn``, and the reply — or the honest failure —
is printed. ``:quit`` or EOF exits and closes the connection. cs-1 binds the
conversation to the fixed penpal (``elc.persona.penpal``): the persona the
character card describes is the persona the memory projections write for.

D-6-a adds the chat command's two dogfood legs (EXT-D5-02's closure: the
shipped CLI can now assemble what the dogfood observes):

- ``--content-db PATH`` assembles the **full-chain tier** (the automatic
  teaching leg with its real detectors over the pilot registry) instead of
  the plain prep-1 tier;
- ``--rollout-stage WORD`` declares one of §12's four stage words
  (``elc.teaching.rollout.RolloutStage``), which is the operator's explicit
  act the zero-open boundary requires; an unknown word is a human sentence
  and exit 2, and **not passing the flag declares no stage** —
  ``rollout_stage=None`` reaches the host, fail-closed, and no automatic
  teaching runs.

``python -m elc web …`` (W-1, user-consented) is the same assembly serving a
minimal local study page instead of the line loop: the chat command's full
argument set plus ``--port`` (default 8760), bound to **127.0.0.1 only**, no
auth — a single-user dogfood face for the D-6-b browser run, not a service.
The turn face reuses this module's envelope shape and the observations face
reads this module's readings core (``observation_sections`` /
``observation_drift_count``), so the page and the CLI answer the same numbers
by construction. ``elc.web`` documents the server's own contracts.

``python -m elc observations --app-db PATH`` is the dogfood readout: the §12
six-indicator declarations, the app.db's durable counts (gate decisions by
decision × reason codes with the ``TARGET_NOT_EXECUTABLY_VERIFIED`` drift
signal, teaching-moment states, generation-action statuses, the delivery /
exposure / ledger-event tables), and the pilot matchers' known
false-positive faces — a pure SQL read face that prints, never writes.

``python -m elc seed --app-db PATH --content-db PATH`` is the cold-start
bootstrap (the D-6 dogfood precondition): a brand-new app.db has no §5.1
teaching policy, no goal portfolio and no §5.2 schedule rows, so the planner's
candidate generators refuse everything and no automatic teaching can ever
trigger. ``seed`` writes exactly the three missing pieces through the host's
own controllers — the default policy (``pv-seed-v1``, BALANCED), the single
speaking goal (``goal-seed-v1``) and one schedule row per
``EXECUTABLY_VERIFIED`` target of the given content.db — and nothing else: no
provider, no model, no key and no network (the host is opened with a
never-called scripted provider). Every write is an idempotent upsert, so
rerunning the command is safe. It configures a study deployment; it opens
nothing (no rollout stage is declared here).

``python -m elc gate --content-db PATH`` (D-5) is the corpus rollout gate over
one built content.db — no host, no app.db, no key: it reads the readiness
table and the artifact's own provenance rows, prints the report (the four
rows, the targets line, the verdict) and codes the verdict as the exit status
(GO = 0, HOLD = 1). The report is the content leg's answer only; a GO here
opens nothing, and the note it prints names what stays outside this command's
answer (the stage declaration, the session-budget split, the opening
adjudication).

Deliberate limits, each a contract rather than an omission:

- **in-process first, one local server exception.** V1's surface is the
  process-internal Python API (client boundary ``DEC-…d7937fd7.12``): ``chat``
  never listens on a port, and the only egress it can cause is the provider
  adapter's single POST. W-1 (user-consented) adds exactly one exception —
  the ``web`` command's local study page on ``http.server``, bound to
  127.0.0.1 and documented in ``elc.web``; no other server or client
  machinery exists in ``src`` (the structural scan in ``tests/host`` pins
  the exception to that one module);
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
from dataclasses import dataclass
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
from elc.persona.penpal import PENPAL_PERSONA_ID
from elc.persona.provider import PersonaProvider, ScriptedPersonaProvider
from elc.platform.db.migrations import MigrationError
from elc.platform.secrets import EnvSecretSource, FileSecretSource, SecretSource
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    Err,
    EvidenceModality,
    GoalId,
    GoalModality,
    GoalVersion,
    InputId,
    InteractionChannel,
    PolicyVersion,
    Result,
    RuntimeVersion,
    SecretRef,
    TargetId,
)
from elc.runtime.types import InputEnvelope, TurnCompletion
from elc.teaching.rollout import (
    OBSERVATION_SPECS,
    ROLLOUT_STAGES,
    RolloutStage,
    RolloutVerdict,
    corpus_rollout_gate,
)
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    TeachingFrequency,
    TeachingPolicyProfile,
)

__all__ = [
    "DEFAULT_CONVERSATION_ID",
    "DEFAULT_SECRET_REF",
    "RUNTIME_VERSION",
    "ObservationSection",
    "main",
    "observation_drift_count",
    "observation_sections",
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

_ROLLOUT_STAGE_HINT = (
    "elc chat: unknown --rollout-stage {word!r}; the four words"
    " docs/IMPLEMENTATION_PLAN.md §12 names are "
    + ", ".join(repr(stage.value) for stage in ROLLOUT_STAGES)
    + " (not passing the flag declares no stage and opens no automatic"
    " teaching)"
)

_OBSERVATIONS_HINT = "elc observations: --app-db PATH is required"

_SEED_REQUIRED_HINT = (
    "elc seed: --app-db and --content-db are required (the seed writes the"
    " default teaching policy, the goal portfolio and one schedule row per"
    " EXECUTABLY_VERIFIED target of the built artifact; no provider, model"
    " or key is needed)"
)

#: The seeded §5.1 pieces' fixed ids (the seed's own declared values — the
#: same idea as D-6-a's test seed, promoted to the shipped command).
_SEED_POLICY_VERSION = "pv-seed-v1"
_SEED_GOAL_VERSION = "gv-seed-v1"
_SEED_GOAL_ID = "goal-seed-v1"
_SEED_GOAL_DESCRIPTION = "a long-term speaking goal"

#: The provenance level whose targets get a §5.2 row (the vocabulary is
#: ``elc.content.types.PROVENANCE_LEVELS``; the level is read off the
#: artifact's derived ``content_provenance`` rows, never declared).
_EXECUTABLY_VERIFIED = "EXECUTABLY_VERIFIED"

#: The reason code whose gate rows are the drift-interception signal: an
#: automatic OPEN that reached the Gate while pointing at a target this
#: deployment cannot executably verify should never be missing from this
#: count, and should stay at zero in a healthy deployment.
_DRIFT_REASON = "TARGET_NOT_EXECUTABLY_VERIFIED"

#: The durable-counts sections of the dogfood readout, in print order —
#: ``(title, sql)`` pairs shared verbatim by the print face and the W-1 web
#: face, so the two readouts answer the same numbers from one definition.
_OBSERVATION_SECTION_SQL: tuple[tuple[str, str], ...] = (
    (
        "gate_decision by decision × reason_codes",
        "SELECT decision, reason_codes, COUNT(*) FROM gate_decision"
        " GROUP BY decision, reason_codes ORDER BY decision, reason_codes",
    ),
    (
        "teaching_moment by lifecycle_state",
        "SELECT lifecycle_state, COUNT(*) FROM teaching_moment"
        " GROUP BY lifecycle_state ORDER BY lifecycle_state",
    ),
    (
        "generation_action_intent by status",
        "SELECT status, COUNT(*) FROM generation_action_intent"
        " GROUP BY status ORDER BY status",
    ),
    (
        "server_delivery_record by state",
        "SELECT state, COUNT(*) FROM server_delivery_record"
        " GROUP BY state ORDER BY state",
    ),
    (
        "exposure_estimate by exposure_level",
        "SELECT exposure_level, COUNT(*) FROM exposure_estimate"
        " GROUP BY exposure_level ORDER BY exposure_level",
    ),
    (
        "planning_ledger_event by event",
        "SELECT event, COUNT(*) FROM planning_ledger_event"
        " GROUP BY event ORDER BY event",
    ),
)


@dataclass(frozen=True)
class ObservationSection:
    """One durable-counts section, read and ready to print or to serialize.

    The shared core of the two dogfood readouts (W-1): the ``observations``
    command prints these and the web face serves them as JSON — one readings
    core, two faces, one number. Cells are read as strings so neither face
    can reformat its way to a different value; ``error`` is set (and ``rows``
    empty) when the section's table could not be read, which the print face
    shows as ``(unreadable: …)`` and the web face as ``{"error": …}``.
    """

    title: str
    rows: tuple[tuple[str, ...], ...]
    error: str | None = None


def observation_sections(db: sqlite3.Connection) -> tuple[ObservationSection, ...]:
    """The six durable-counts sections over one open app.db connection.

    A section whose table cannot be read comes back with its error message
    and the rest still reads — one broken table never silences the readout.
    """

    sections: list[ObservationSection] = []
    for title, sql in _OBSERVATION_SECTION_SQL:
        try:
            rows = tuple(
                tuple(str(cell) for cell in row)
                for row in db.execute(sql).fetchall()
            )
        except sqlite3.Error as exc:
            sections.append(ObservationSection(title=title, rows=(), error=str(exc)))
        else:
            sections.append(ObservationSection(title=title, rows=rows))
    return tuple(sections)


def observation_drift_count(db: sqlite3.Connection) -> int:
    """Gate rows naming ``TARGET_NOT_EXECUTABLY_VERIFIED`` — the drift signal.

    Printed even at zero, because a non-zero there is the signal that an
    automatic OPEN reached the Gate for a target this deployment cannot
    executably verify.
    """

    return int(
        db.execute(
            "SELECT COUNT(*) FROM gate_decision WHERE reason_codes LIKE ?",
            (f"%{_DRIFT_REASON}%",),
        ).fetchone()[0]
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
    if args.command == "observations":
        if args.app_db is None:
            print(_OBSERVATIONS_HINT, file=err)
            return 2
        return _observations(args, stdout=out, stderr=err)
    if args.command == "seed":
        # Its own required pair, checked before the chat validation below so
        # the seed never needs a base-url/model/key (it sends no request).
        if args.app_db is None or args.content_db is None:
            print(_SEED_REQUIRED_HINT, file=err)
            return 2
        return _seed(args, stdout=out, stderr=err)

    # chat's and web's required arguments are validated here rather than by
    # argparse so the gate command can share one flat parser without them (a
    # missing --base-url stays a human sentence and a 2, only now from this
    # check). The web command (W-1) reuses this whole validation path — and
    # the provider construction and the host assembly below — verbatim.
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
    rollout_stage: RolloutStage | None = None
    if args.rollout_stage is not None:
        try:
            rollout_stage = RolloutStage(args.rollout_stage)
        except ValueError:
            print(
                _ROLLOUT_STAGE_HINT.format(word=args.rollout_stage), file=err
            )
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

    if args.command == "web":
        # W-7 review MEDIUM-1: probe BEFORE open_host — opening the host
        # bumps the store epoch, which fences a live instance's writes even
        # when this start is then refused. Probed here, a refused second
        # start never touches the database at all (and the banner below
        # stays honest: it prints only for a start that will serve).
        from elc.web import port_is_serving

        if port_is_serving(args.port):
            print(
                f"elc web: port {args.port} is already serving an elc web"
                " instance — stop the old one first; two instances on one"
                " app.db corrupt each other's turns",
                file=err,
            )
            return 1

    try:
        host = open_host(
            app_db,
            provider=provider,
            secrets=secrets,
            content_db_path=args.content_db,
            rollout_stage=rollout_stage,
        )
    except (sqlite3.Error, MigrationError, OSError, ContentStoreError) as exc:
        print(f"elc {args.command}: cannot open app.db {app_db}: {exc}", file=err)
        return 1
    try:
        if args.command == "web":
            # The lazy import keeps elc.web → elc.cli (its readings core and
            # runtime version) acyclic: this module never imports the server
            # at load time, only here, where the command runs.
            from elc.web import (
                DEFAULT_WEB_CONVERSATION_ID,
                WebOpenError,
                run_web,
            )

            print(
                f"elc web · serving http://127.0.0.1:{args.port} · open it"
                " in a browser; Ctrl+C to stop"
                "（浏览器打开该地址开始对话；Ctrl+C 停止服务）",
                file=out,
            )
            out.flush()
            try:
                run_web(
                    host,
                    args.port,
                    conversation=(
                        args.conversation or DEFAULT_WEB_CONVERSATION_ID
                    ),
                )
            except WebOpenError as exc:
                print(f"elc web: {exc}", file=err)
                return 1
            except KeyboardInterrupt:
                # The banner promises "Ctrl+C to stop" — the stop is answered
                # with a clean exit, not a traceback (the chat loop's own
                # KeyboardInterrupt posture, one face over).
                return 0
            except OSError as exc:
                # A port already taken (or unavailable) is the one startup
                # failure an operator can fix by choosing another --port —
                # said as a sentence, never as a traceback.
                print(
                    f"elc web: cannot listen on 127.0.0.1:{args.port}:"
                    f" {exc} — pass another --port",
                    file=err,
                )
                return 1
            return 0
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

    conversation_id = ConversationId(
        args.conversation or DEFAULT_CONVERSATION_ID
    )
    # cs-1: the conversation is bound to the fixed penpal, so the Persona
    # ×User pair the CP4 projections write for is the pair the character
    # card describes (an unbound row made the projections refuse and the
    # turn pipeline fall back to ``persona-default`` — the two readings
    # disagreed). A legacy row that predates the binding is adopted
    # (``open_conversation`` fills an empty persona, never overwrites one).
    opened = host.open_conversation(
        conversation_id, persona_id=PENPAL_PERSONA_ID
    )
    if isinstance(opened, Err):
        print(
            f"elc chat: cannot open conversation {conversation_id}:"
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

    content_db = (
        args.content_db
        if args.content_db is not None
        else str(DEFAULT_OUTPUT)
    )
    try:
        content_store = ContentStore(content_db)
    except (ContentStoreError, sqlite3.Error, OSError) as exc:
        print(
            f"elc gate: cannot open content.db {content_db}: {exc!r}",
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


def _observations(
    args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO
) -> int:
    """The D-6-a dogfood readout over one app.db (the ``observations`` command).

    A pure SQL read face — no host, no provider, no key, no new table: the
    §12 six-indicator declarations (``rollout.py``'s ``OBSERVATION_SPECS``,
    the repository's own honesty about what each reading is), then the
    durable counts the declarations point at (gate decisions by decision ×
    reason codes — the ``TARGET_NOT_EXECUTABLY_VERIFIED`` count is printed
    even at zero, because a non-zero there is the drift-interception signal —
    teaching-moment states, generation-action statuses, and the delivery /
    exposure / ledger-event tables that exist to answer the six), and finally
    the known false-positive faces of the D-3 pilot matchers, named so a
    dogfood run watches them deliberately instead of rediscovering them.
    An app.db that cannot be opened read-only is exit 1; a section whose
    table cannot be read is reported as unreadable and the rest prints.
    """

    try:
        db = sqlite3.connect(f"file:{args.app_db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        print(
            f"elc observations: cannot open app.db {args.app_db}: {exc}",
            file=stderr,
        )
        return 1
    print(f"elc observations · app.db = {args.app_db}", file=stdout)

    print("the six §12 indicators (declaration first, count second):", file=stdout)
    for spec in OBSERVATION_SPECS:
        print(f"  {spec.indicator} — {spec.definition}", file=stdout)

    def section(s: ObservationSection) -> None:
        print(f"{s.title}:", file=stdout)
        if s.error is not None:
            print(f"  (unreadable: {s.error})", file=stdout)
            return
        if not s.rows:
            print("  (no rows)", file=stdout)
            return
        for row in s.rows:
            print(f"  {' | '.join(row)}", file=stdout)

    readings = observation_sections(db)
    section(readings[0])
    print(
        f"  gate rows naming {_DRIFT_REASON} (the drift signal):"
        f" {observation_drift_count(db)}",
        file=stdout,
    )
    for s in readings[1:]:
        section(s)

    print(
        "known false-positive faces (D-3 pilot matchers, watched):",
        file=stdout,
    )
    print("  - a fronted 'Thought ...' clause (N-D3-4: legal", file=stdout)
    print("    spoken-English subject omission the think/thought", file=stdout)
    print("    matcher still reads as one)", file=stdout)
    print('  - a parenthetical adverb right after "I think," (the', file=stdout)
    print("    comma-after-hedge family's insertion reading)", file=stdout)
    print("  - any fronted 'Any way, ...' split spelling (the marker", file=stdout)
    print("    family's one shape; a vocative after the comma has not", file=stdout)
    print("    reproduced as its own face — watch item, not a separate", file=stdout)
    print("    known face)", file=stdout)
    print(
        "  tracked during dogfood observation: a hit that proves false feeds",
        file=stdout,
    )
    print("  the matcher audit before anything widens.", file=stdout)
    db.close()
    return 0


def _seed(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """The cold-start bootstrap (the ``seed`` command).

    A brand-new app.db passes every migration and opens fine — but it has no
    §5.1 teaching policy, no goal portfolio and no §5.2 schedule rows, so the
    planner's generators refuse every candidate and automatic teaching can
    never trigger. This command writes exactly those three pieces, all through
    the host's own controllers (the D-6-a test seed's shape, promoted): the
    default policy, the single speaking goal, and one ``recompute_schedule_item``
    row per ``EXECUTABLY_VERIFIED`` target of the given content.db. The host is
    opened with a scripted provider whose script is empty and never called —
    the seed sends no request — and it declares no rollout stage, so the host
    this command opens could not run automatic teaching even if it wanted to.
    Every write is an idempotent upsert (the schedule row is keyed by
    target × modality and an identical recomputation replays), so rerunning
    the command is safe and says so. Exit codes: 0 seeded, 2 missing
    arguments (checked in ``main``), 1 an unopenable database or a refused
    write.
    """

    try:
        host = open_host(
            args.app_db,
            provider=ScriptedPersonaProvider(script=()),
            content_db_path=args.content_db,
        )
    except (sqlite3.Error, MigrationError, OSError, ContentStoreError) as exc:
        print(
            "elc seed: cannot open the databases"
            f" (app.db {args.app_db}, content.db {args.content_db}): {exc}",
            file=stderr,
        )
        return 1
    try:
        # The full-chain tier is guaranteed by content_db_path being required;
        # the asserts say so where mypy needs it said.
        assert host.user_id is not None and host.user_config is not None
        assert host.content_store is not None
        assert host.curriculum is not None and host.scheduler is not None

        written = host.user_config.upsert_teaching_policy(
            TeachingPolicyProfile(
                teaching_policy_profile_id=host.user_id,
                policy_version=PolicyVersion(_SEED_POLICY_VERSION),
                teaching_frequency=TeachingFrequency.BALANCED,
            )
        )
        if isinstance(written, Err):
            print(
                f"elc seed: the teaching-policy write was refused:"
                f" {written.error.message}",
                file=stderr,
            )
            return 1
        portfolio = host.user_config.upsert_goal_portfolio(
            LearningGoalPortfolio(
                goal_portfolio_id=host.user_id,
                goal_version=GoalVersion(_SEED_GOAL_VERSION),
                goals=(
                    LearningGoal(
                        goal_id=GoalId(_SEED_GOAL_ID),
                        goal_modality=GoalModality.SPEAKING,
                        description=_SEED_GOAL_DESCRIPTION,
                    ),
                ),
                modality_weights={GoalModality.SPEAKING: 1.0},
                assessment_targets=(),
                # The F-4 sentinel ("not configured"), not a clock reading: a
                # fresh effective_from per run would change the content under
                # the same goal_version, and the store would rightly refuse
                # the second write as a CONFLICT — the seed's idempotence
                # needs every byte of the write to be the same every run.
                effective_from="",
            )
        )
        if isinstance(portfolio, Err):
            print(
                f"elc seed: the goal-portfolio write was refused:"
                f" {portfolio.error.message}",
                file=stderr,
            )
            return 1

        provenance = host.content_store.provenance_levels()
        if isinstance(provenance, Err):
            print(
                "elc seed: the content artifact's provenance table could not"
                f" be read: {provenance.error.message}",
                file=stderr,
            )
            return 1
        ev_targets = [
            entity_id
            for entity_id, level in provenance.value
            if level == _EXECUTABLY_VERIFIED
        ]
        now = datetime.now(tz=UTC).isoformat()
        seeded: list[str] = []
        skipped: list[str] = []
        for entity_id in ev_targets:
            row = host.curriculum.get_target(TargetId(entity_id))
            if isinstance(row, Err):
                skipped.append(entity_id)
                continue
            scheduled = host.scheduler.recompute_schedule_item(
                row.value.target_type,
                TargetId(entity_id),
                EvidenceModality(row.value.evidence_modality),
                now,
            )
            if isinstance(scheduled, Err):
                skipped.append(entity_id)
                continue
            seeded.append(entity_id)
        skip_note = ", ".join(skipped) if skipped else "none"
        print(
            f"elc seed · seeded policy {_SEED_POLICY_VERSION} (BALANCED)",
            file=stdout,
        )
        print(
            f"elc seed · seeded goal {_SEED_GOAL_ID} (SPEAKING)",
            file=stdout,
        )
        print(
            f"elc seed · {len(seeded)} schedule rows for"
            f" {len(ev_targets)} EV targets (skipped: {skip_note})",
            file=stdout,
        )
        print(
            "elc seed · rerunning is safe: every write is an idempotent"
            " upsert",
            file=stdout,
        )
        return 0
    finally:
        host.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m elc",
        description=(
            "One in-process conversation loop over app.db — chat, the corpus"
            " gate, the dogfood readout, and (W-1) the local web face bound"
            " to 127.0.0.1."
        ),
    )
    parser.add_argument(
        "command",
        choices=("chat", "gate", "observations", "seed", "web"),
        help=(
            "chat: the conversation loop; gate: the corpus rollout gate;"
            " observations: the D-6-a dogfood readout over one app.db;"
            " seed: the cold-start bootstrap (default policy + goal + one"
            " schedule row per EV target; run once before a dogfood);"
            " web: the local study-first page over one app.db (127.0.0.1"
            " only, no auth — a single-user dogfood face, not a service)"
        ),
    )
    parser.add_argument(
        "--app-db",
        help="path to app.db (chat and seed: created and migrated when"
        " absent; observations: opened read-only)",
    )
    parser.add_argument(
        "--content-db",
        default=None,
        help=(
            "path to a built content.db (chat: the full-chain tier — the"
            " automatic teaching leg with its detectors; seed: required —"
            " its EXECUTABLY_VERIFIED targets are what gets schedule rows;"
            " absent for chat = the plain prep-1 tier. gate: the artifact"
            " to gate, default: the repository build artifact)"
        ),
    )
    parser.add_argument(
        "--rollout-stage",
        default=None,
        help=(
            "chat: declare the rollout stage (one of §12's four words;"
            " absent = no stage declared — the fail-closed default that runs"
            " no automatic teaching)"
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
        default=None,
        help=(
            "conversation id (default: chat opens cli-default, web opens"
            " web-default — the two faces never share one transcript by"
            " accident)"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8760,
        help="web: the local port to serve on (default: %(default)s)",
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
