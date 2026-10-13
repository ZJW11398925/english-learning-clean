"""V3-8f — the reading face's real-wiring calibration
(TASK-OPI-c0f4d9b4…12 / the opening ruling ``DEC-OPI-c0f4d9b4…10``; the
paradigm shift §10.4).

**What this suite proves, stated honestly.** The timeout derivation and
the drive wait are exercised offline: every egress call rides an
injected transport (no socket, no real credential — the V3-8e suite's
own posture), and the wait pin patches the constant down instead of
waiting 1800 seconds. The real-model evidence is the V3-8f smoke run's
own log (``D:\\elc-scratch\\v38f\\smoke.log``), cited in the delivery
report — never in this suite.

Pinned here:

1. the world egress budget — ``WORLD_EGRESS_TIMEOUT_SECONDS`` (180.0) is
   the drive's own independent calibration, and ``with_timeout`` moves
   exactly one number: same coordinates, same secret source, same
   injected transports (buffered **and** streamed), the original
   provider untouched;
2. the seam's call really goes out with 180.0 — the injected transport
   records the ``timeout`` argument (the persona default stays 30.0, and
   the derivation is rebuilt per call, so a settings-page hot swap still
   lands on the very next call);
3. the honest faces stand — an unconfigured live provider answers
   ``not-configured`` with zero calls and no secret access, a non-OpenAI
   provider (and an absent one) answers ``no-egress``;
4. ``_provider_failure`` — each failure-code family gets its own
   actionable sentence; a timeout is never dressed as a credentials
   problem (the V3-8f bug the relay fixes);
5. web.py's drive wait — ``_V3_DRIVE_WAIT_SECONDS`` is 1800.0 (V3-8h
   moved it 600 → 1800 for the drive loop: one call presses on through
   up to twelve fresh segments), exactly the five V3 write routes pass
   it, every other ``_run_host_write`` caller keeps the house default
   (60.0), and — behaviorally, with the constant patched down and the
   offline transport blocking — a drive that outlives its wait is
   answered with the honest 500 人话, proving each route reads the
   drive budget (not the house wait) at request time.
"""

from __future__ import annotations

import contextlib
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest

from elc import web as web_module
from elc.host import open_host
from elc.narrative_web import (
    REASON_NO_EGRESS,
    WORLD_EGRESS_TIMEOUT_SECONDS,
    NarrativeWebFace,
    PersonaEgressCompletion,
)
from elc.persona.openai_provider import (
    REASON_NOT_CONFIGURED,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import SecretRef
from elc.web import run_web
from elc.world import gold
from tests.host.support import (
    REPLY_TEXT,
    SENTINEL_KEY,
    FixedSecret,
    RecordingPost,
    completion,
    config,
)

REPO = Path(__file__).resolve().parents[2]

#: The loopback opener (the V3-8e suite's own): an empty proxy map, so a
#: developer's proxy can never stand between the test and the page.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

#: The client's own ceiling: comfortably below the house 60s wait, so a
#: route that ignored the patched drive budget fails this suite loudly
#: (a socket timeout) instead of passing after a 60-second sleep.
_CLIENT_TIMEOUT_SECONDS = 10.0


def _compiled(prompt: str) -> CompiledPrompt:
    return CompiledPrompt(
        persona_id="v3-world",
        prompt_text=prompt,
        generation_contract="v3-world-prose",
    )


class _StreamPost:
    """An ``HttpStreamPost`` over scripted SSE lines; records the
    ``timeout`` argument (the derived provider's own budget witness)."""

    def __init__(self, lines: tuple[bytes, ...]) -> None:
        self.lines = lines
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, Iterator[bytes]]:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "body": body,
                "timeout": timeout,
            }
        )

        def _lines() -> Iterator[bytes]:
            yield from self.lines

        return 200, _lines()


def _sse_lines(*chunks: str) -> tuple[bytes, ...]:
    lines = [
        b"data: "
        + json.dumps({"choices": [{"delta": {"content": chunk}}]}).encode(
            "utf-8"
        )
        + b"\n"
        for chunk in chunks
    ]
    lines.append(b"data: [DONE]\n")
    return tuple(lines)


# ---------------------------------------------------------------------------
# 1. the world egress budget (the derivation and its one moved number)
# ---------------------------------------------------------------------------


def test_the_world_egress_budget_is_its_own_calibration() -> None:
    """The drive's budget is a module constant of the assembly (180.0),
    independent of the persona egress's general default (30.0): the
    settings page stays the one configuration face, and this number is
    not one of its knobs."""

    import elc.narrative_web as narrative_web_module

    assert WORLD_EGRESS_TIMEOUT_SECONDS == 180.0
    assert isinstance(WORLD_EGRESS_TIMEOUT_SECONDS, float)
    assert "WORLD_EGRESS_TIMEOUT_SECONDS" in narrative_web_module.__all__
    assert config().timeout_seconds == 30.0
    assert WORLD_EGRESS_TIMEOUT_SECONDS != config().timeout_seconds


def test_with_timeout_moves_exactly_one_number() -> None:
    """The additive derivation: a new provider over the same config
    (one field replaced), the same ``SecretSource`` object and the very
    transports the instance was built with — the original call face
    keeps its own 30.0."""

    post = RecordingPost(status=200, payload=completion())
    stream = _StreamPost(lines=_sse_lines("hi"))
    secrets = FixedSecret()
    live = OpenAICompatibleProvider(
        config(), secrets, transport=post, stream_transport=stream
    )
    derived = live.with_timeout(WORLD_EGRESS_TIMEOUT_SECONDS)

    assert derived is not live
    for field in (
        "base_url",
        "model",
        "secret_ref",
        "temperature",
        "allow_insecure_http",
    ):
        assert getattr(derived.config, field) == getattr(live.config, field)
    assert derived.config.timeout_seconds == 180.0
    assert live.config.timeout_seconds == 30.0  # the live face is not mutated
    assert derived.secret_source is secrets

    out = derived.call(_compiled("PROMPT-A"))
    assert out.text == REPLY_TEXT and out.error is None
    assert post.calls[0]["timeout"] == 180.0
    assert (
        post.calls[0]["headers"]["Authorization"] == f"Bearer {SENTINEL_KEY}"
    )

    # the same injected instances stay dialled: the base provider still
    # rides its own 30.0 on the same transport, and the derived streamed
    # face dials the injected stream transport (never a real one).
    assert live.call(_compiled("PROMPT-B")).text == REPLY_TEXT
    assert post.calls[1]["timeout"] == 30.0
    seen: list[str] = []
    streamed = derived.call_streaming(_compiled("PROMPT-C"), seen.append)
    assert (streamed.text, streamed.error) == ("hi", None)
    assert seen == ["hi"]
    assert stream.calls[0]["timeout"] == 180.0


def test_the_egress_seam_dials_the_world_budget_and_rebuilds_per_call() -> None:
    """``PersonaEgressCompletion`` really sends at 180.0 (the transport
    spy records it), the failure value never carries the prompt, and the
    derivation is rebuilt per call — a hot swap lands on the very next
    call."""

    first_post = RecordingPost(status=200, payload=completion("first"))
    second_post = RecordingPost(status=200, payload=completion("second"))
    holder = [
        OpenAICompatibleProvider(
            config(), FixedSecret(), transport=first_post
        )
    ]
    seam = PersonaEgressCompletion(lambda: holder[-1])

    first = seam.complete("PROMPT-A")
    assert (first.text, first.error) == ("first", None)
    assert first_post.call_count == 1
    assert first_post.calls[0]["timeout"] == 180.0
    assert "PROMPT-A" not in str(first)

    holder.append(
        OpenAICompatibleProvider(
            config(), FixedSecret(), transport=second_post
        )
    )
    second = seam.complete("PROMPT-B")
    assert (second.text, second.error) == ("second", None)
    assert first_post.call_count == 1
    assert second_post.call_count == 1
    assert second_post.calls[0]["timeout"] == 180.0


def test_the_unconfigured_and_non_openai_faces_stand() -> None:
    """The honest faces the seam always had: no coordinates ⇒
    ``not-configured`` with zero calls (and no secret access); a
    non-OpenAI provider — or none — ⇒ ``no-egress``."""

    post = RecordingPost(status=200, payload=completion("never sent"))
    bare = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="", model="", secret_ref=SecretRef("api-key")
        ),
        FixedSecret(),
        transport=post,
    )
    unconfigured = PersonaEgressCompletion(lambda: bare).complete("PROMPT-A")
    assert unconfigured.text is None
    assert unconfigured.error == REASON_NOT_CONFIGURED
    assert post.call_count == 0
    assert "PROMPT-A" not in str(unconfigured)

    scripted = ScriptedPersonaProvider(script=(ProviderOutput(text="x"),))
    not_openai = PersonaEgressCompletion(lambda: scripted).complete(
        "PROMPT-B"
    )
    assert not_openai.text is None
    assert not_openai.error == REASON_NO_EGRESS
    absent = PersonaEgressCompletion(lambda: None).complete("PROMPT-C")
    assert absent.error == REASON_NO_EGRESS


# ---------------------------------------------------------------------------
# 2. the failure codes as actionable sentences
# ---------------------------------------------------------------------------


def test_each_failure_code_family_gets_its_own_sentence() -> None:
    """``_provider_failure``: the named families each carry their own
    action; a timeout never wears the credentials sentence (the V3-8f
    bug — a flattened code misreported the cause), and every other code
    keeps the generic retry sentence with the code appended."""

    failure = NarrativeWebFace._provider_failure

    timeout_sentence = failure("timeout")
    assert "180" in timeout_sentence
    assert "重试" in timeout_sentence
    assert "设置" not in timeout_sentence
    assert "密钥" not in timeout_sentence

    for code in ("http-401", "missing-secret", "key-echo"):
        sentence = failure(code)
        assert code in sentence
        assert "密钥" in sentence and "设置" in sentence
        # the family's own literals — the generic sentence carries none of
        # them, so deleting the branch turns this red (V3-8f review F1:
        # the generic text alone let a branch deletion slide through)
        assert "没能通过这把密钥" in sentence
        assert "BYOK" in sentence

    for code in ("not-configured", REASON_NO_EGRESS):
        sentence = failure(code)
        assert code in sentence
        assert "设置" in sentence
        # the config family's own literals, same tooth as above
        assert "没有可用的模型端点" in sentence
        assert "--base-url" in sentence

    limited = failure("http-429")
    assert "429" in limited
    assert "等一会儿" in limited

    generic = failure("transport-error")
    assert "transport-error" in generic
    assert "重试" in generic

    # the families do not collapse into one another — nor into the generic
    # sentence (review F1's tooth: a deleted branch falls back to generic
    # and these equalities turn red)
    assert failure("timeout") != failure("http-401")
    assert failure("http-429") != failure("http-401")
    assert failure("transport-error") != failure("timeout")
    assert failure("http-401") != generic
    assert failure("missing-secret") != generic
    assert failure("key-echo") != generic
    assert failure("not-configured") != generic
    assert failure(REASON_NO_EGRESS) != generic
    assert failure("http-429") != generic


# ---------------------------------------------------------------------------
# 3. web.py's drive wait (the constant, the five callers, the default arm)
# ---------------------------------------------------------------------------


def test_the_drive_wait_is_the_reading_faces_own_budget() -> None:
    """The wait split, pinned mechanically: the house default stays 60.0
    and its default arm is untouched; exactly the five V3 write routes
    pass the 1800.0 drive budget (V3-8h: the drive loop's own arithmetic
    — the ceiling × the measured per-call latency + the planning round
    trips); no other ``_run_host_write`` caller does (the ack route and
    every non-V3 write keep the house wait)."""

    source = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    assert web_module._WORKER_WAIT_SECONDS == 60.0
    assert web_module._V3_DRIVE_WAIT_SECONDS == 1800.0
    assert "_WORKER_WAIT_SECONDS = 60.0" in source
    assert "_V3_DRIVE_WAIT_SECONDS = 1800.0" in source
    assert "timeout = _WORKER_WAIT_SECONDS if wait is None else wait" in source
    assert source.count("wait=") == 5
    assert source.count("wait=_V3_DRIVE_WAIT_SECONDS") == 5

    start = source.index('if self.path == "/api/v3/start":')
    ack = source.index('if self.path == "/api/v3/ack":')
    span = source[start:ack]
    for path in (
        "/api/v3/start",
        "/api/v3/continue",
        "/api/v3/submit",
        "/api/v3/settle",
        "/api/v3/next_chapter",
    ):
        assert f'if self.path == "{path}":' in span, path
    assert span.count("self._run_host_write(") == 5
    assert span.count("wait=_V3_DRIVE_WAIT_SECONDS") == 5

    outside = source[:start] + source[ack:]
    assert "wait=" not in outside
    assert outside.count("self._run_host_write(") > 0
    assert "timeout=_WORKER_WAIT_SECONDS" in source  # the sibling waits keep it


# ---------------------------------------------------------------------------
# 4. the behavior: a drive that outlives its wait is answered honestly
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _BlockingPost:
    """The offline ``HttpPost`` that blocks its **first** call until
    ``release`` is set, then answers the Gold script's payloads (a
    scripted gap raises — the fixture's own loud posture). No sleep
    anywhere: the test decides when the blocked drive may finish."""

    def __init__(self, release: threading.Event) -> None:
        self.script = gold.gold_completion()
        self.release = release
        self.blocked = threading.Event()
        self._blocked_once = False

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, bytes]:
        del url, headers, timeout
        document = json.loads(body.decode("utf-8"))
        prompt = document["messages"][0]["content"]
        if not self._blocked_once:
            self._blocked_once = True
            self.blocked.set()
            self.release.wait(timeout=60.0)
        outcome = self.script.complete(prompt)
        text = "" if outcome.text is None else outcome.text
        reply = json.dumps({"choices": [{"message": {"content": text}}]})
        return 200, reply.encode("utf-8")


@contextlib.contextmanager
def _serving(app_db: Path, post: Any) -> Iterator[int]:
    """Serve the real ``run_web`` over one host on a daemon thread — the
    V3-8e suite's worker shape, slimmed to this suite's need."""

    port = _free_port()
    ready = threading.Event()
    stop = threading.Event()
    box: dict[str, Any] = {}
    live = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="https://egress.invalid/v1",
            model="scripted-model",
            secret_ref=SecretRef("test-key-ref"),
        ),
        FixedSecret(value="sk-offline-sentinel-NEVER-LEAK"),
        transport=post,
    )

    def worker() -> None:
        try:
            host = open_host(app_db, provider=live)
            run_web(
                host,
                port,
                conversation="web-v3",
                ready=ready,
                stop=stop,
            )
        except BaseException as exc:  # surfaced to the test thread below
            box["error"] = exc
            ready.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        assert ready.wait(timeout=60.0), "the web worker never became ready"
        if "error" in box:
            raise box["error"]
        yield port
    finally:
        stop.set()
        thread.join(timeout=60.0)
        assert not thread.is_alive(), "the web worker did not stop"


def _write_route(
    port: int, path: str, payload: Any = None
) -> tuple[int, Any]:
    if payload is None:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=b"", method="POST"
        )
    else:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    try:
        with _OPENER.open(
            request, timeout=_CLIENT_TIMEOUT_SECONDS
        ) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_a_v3_drive_outliving_its_wait_is_answered_honestly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The behavioral witness for the wait split: with the drive budget
    patched down and the offline transport blocking, each of the five V3
    write routes answers the honest 500 人话 in well under the house
    wait — a route riding the 60s default instead would blow the
    client's own 10s timeout and fail this test loudly."""

    monkeypatch.setattr(web_module, "_V3_DRIVE_WAIT_SECONDS", 0.05)
    release = threading.Event()
    post = _BlockingPost(release)
    with _serving(tmp_path / "app.db", post) as port:
        try:
            requests = (
                ("/api/v3/start", None),
                ("/api/v3/continue", {"end_scene": False}),
                (
                    "/api/v3/submit",
                    {
                        "submission_id": gold.SUBMISSION_ID,
                        "intent_text": "I wait by the gate and say nothing.",
                    },
                ),
                ("/api/v3/settle", None),
                ("/api/v3/next_chapter", None),
            )
            for path, payload in requests:
                status, body = _write_route(port, path, payload)
                assert status == 500, (path, status, body)
                assert body == {
                    "error": "the host worker did not answer in time"
                }, path
            assert post.blocked.wait(timeout=10.0), "the drive never started"
        finally:
            release.set()
