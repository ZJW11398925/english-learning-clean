"""A1 — the streamed output face, end to end, over the production shapes.

Four layers, one file, no new network roots (the fake OpenAI endpoint is the
same loopback ``http.server`` posture the W-1 suites serve the page with):

1. **the provider's streamed face** — ``call_streaming`` over an injected
   ``HttpStreamPost``: increments concatenate in order, SSE framing noise is
   skipped, every failure stays a value (``http-<status>`` / ``bad-json`` /
   ``bad-shape`` / ``timeout`` / ``transport-error`` /
   ``response-too-large``), the error body of a non-2xx is never read, and
   the key-echo guard runs on the **accumulated** buffer — an echo split
   across two chunks is caught on the chunk that completes it;
2. **the web bridge** — the real ``run_web`` stack answering
   ``POST /api/turn_stream``: per-character deltas while the host thread
   runs the turn, then exactly one ``final`` carrying the very payload
   ``/api/turn`` would have answered; a provider without the streaming face
   answers zero deltas and one final; a failed bridge injection degrades to
   the same single-final shape with the assembly intact; a disconnecting
   reader stops the writing, never the turn;
3. **the page wiring** — source scans: ``fetchTurnStream`` (reader, data-line
   parser, the ``started`` marker), the typewriter into ``textContent``,
   the finalize pairing, the fallback and the no-resend posture;
4. **the old contract** — the blocking ``/api/turn`` payload's key set is
   exactly what it was, and a blocking turn after a streamed one is
   unchanged (the bridge's restore really restores).
"""

from __future__ import annotations

import json
import queue
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator

import pytest

from elc.persona.openai_provider import (
    MAX_PROVIDER_RESPONSE_BYTES,
    REASON_BAD_JSON,
    REASON_BAD_SHAPE,
    REASON_KEY_ECHO,
    REASON_RESPONSE_TOO_LARGE,
    REASON_TIMEOUT,
    REASON_TRANSPORT_ERROR,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import PersonaId
from tests.host.support import (
    FIXED_SECRET_REF,
    SENTINEL_KEY,
    FixedSecret,
    config,
)
from tests.host.test_w1_web import REPLY, web_stack

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "elc"
WEBUI = SRC / "webui"

#: What every streamed turn says (the fake endpoint's reply, one character
#: per delta — the same text the scripted stacks answer with).
A1_TEXT = "The meeting starts at nine."

#: The blocking turn's payload keys, in the shape every existing consumer
#: reads them — the exact set A1's ``final`` must carry and the one contract
#: this cut may not widen or shrink.
TURN_PAYLOAD_KEYS = {
    "reply",
    "turn_status",
    "failure_reason",
    "teaching_moments",
    "word_hits",
    "user_word_hits",
    "usage",
    "world_step_note",
}


def compiled(text: str = "hello there") -> CompiledPrompt:
    return CompiledPrompt(
        persona_id=PersonaId("persona-a1"),
        prompt_text=text,
        generation_contract="gc-normal-persona-reply",
    )


# ---------------------------------------------------------------------------
# Group 1 — the provider's streamed face (injected HttpStreamPost, no socket)
# ---------------------------------------------------------------------------


@dataclass
class RecordingStreamPost:
    """An ``HttpStreamPost`` that answers scripted SSE lines and records.

    ``raises`` fails the call itself; ``mid_stream_raises`` fails it *after*
    the lines went out — the streamed face's own transport boundary. A
    non-2xx status hands back an iterator that fails the test if the
    adapter ever reads it (the error body must stay unread).
    """

    status: int = 200
    lines: tuple[bytes, ...] = ()
    raises: BaseException | None = None
    mid_stream_raises: BaseException | None = None
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(
        self,
        url: str,
        headers: object,
        body: bytes,
        timeout: float,
    ) -> tuple[int, Iterator[bytes]]:
        self.calls.append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        if self.raises is not None:
            raise self.raises
        if self.status != 200:

            def _unreadable() -> Iterator[bytes]:
                raise AssertionError("the error body must never be read")
                yield b""  # pragma: no cover — makes this a generator

            return self.status, _unreadable()

        def _lines() -> Iterator[bytes]:
            for line in self.lines:
                yield line
            if self.mid_stream_raises is not None:
                raise self.mid_stream_raises

        return self.status, _lines()

    @property
    def call_count(self) -> int:
        return len(self.calls)


def sse_lines(*chunks: str, done: bool = True) -> tuple[bytes, ...]:
    """A well-formed SSE tail: one ``data:`` line per increment, ``[DONE]``."""

    lines = [
        b"data: "
        + json.dumps({"choices": [{"delta": {"content": chunk}}]}).encode(
            "utf-8"
        )
        + b"\n"
        for chunk in chunks
    ]
    if done:
        lines.append(b"data: [DONE]\n")
    return tuple(lines)


def streaming_provider_over(post: RecordingStreamPost, **overrides: object):
    return OpenAICompatibleProvider(
        config(**overrides), FixedSecret(), stream_transport=post
    )


def test_streaming_call_concatenates_increments_in_order_and_pins_the_request() -> None:
    post = RecordingStreamPost(
        lines=sse_lines("I think", " it is", " going", " to rain.")
    )
    seen: list[str] = []
    output = streaming_provider_over(post).call_streaming(
        compiled(), seen.append
    )

    assert (output.text, output.error, output.usage) == (
        "I think it is going to rain.",
        None,
        None,
    )
    assert seen == ["I think", " it is", " going", " to rain."]
    call = post.calls[0]
    assert call["url"] == "https://offline.invalid/v1/chat/completions"
    assert call["headers"] == {
        "Authorization": f"Bearer {SENTINEL_KEY}",
        "Content-Type": "application/json",
    }
    body = json.loads(call["body"])  # type: ignore[arg-type]
    assert body["stream"] is True
    assert body["model"] == "offline-model"
    assert body["messages"] == [{"role": "user", "content": "hello there"}]
    assert SENTINEL_KEY.encode() not in call["body"]  # type: ignore[operator]


def test_framing_noise_and_the_done_tail_never_become_increments() -> None:
    post = RecordingStreamPost(
        lines=(
            b": keep-alive\n",
            b"event: delta\n",
            b"\n",
            *sse_lines("Hello", " there"),
            b"data: not-a-frame\n",  # past [DONE]: ignored wholesale
        )
    )
    seen: list[str] = []
    output = streaming_provider_over(post).call_streaming(
        compiled(), seen.append
    )

    assert (output.text, output.error) == ("Hello there", None)
    assert seen == ["Hello", " there"]


def test_half_line_framing_and_no_increment_chunks_are_honest() -> None:
    # A half line — the transport's final read with **no trailing newline**
    # — still parses; role-only and empty delta chunks carry no increment
    # and are skipped, not fatal. (A line truncated *mid-JSON* is the
    # bad-json value the grammar case pins.)
    post = RecordingStreamPost(
        lines=(
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
            b'data: {"choices":[{"delta":{}}]}\n',
            b'data: {"choices":[{"delta":{"content":""}}]}\n',
            b'data: {"choices":[{"delta":{"content":"Word"}}]}',
            b"data: [DONE]\n",
        )
    )
    seen: list[str] = []
    output = streaming_provider_over(post).call_streaming(
        compiled(), seen.append
    )

    assert (output.text, output.error) == ("Word", None)
    assert seen == ["Word"]


def test_bad_json_and_bad_shape_stay_values() -> None:
    cases: tuple[tuple[bytes, str], ...] = (
        (b"data: not json at all\n", REASON_BAD_JSON),
        (b'data: {"choices": []}\n', REASON_BAD_SHAPE),
        (b'data: {"choices": ["not an object"]}\n', REASON_BAD_SHAPE),
        (b"data: [1, 2, 3]\n", REASON_BAD_SHAPE),
        (b'data: {"choices":[{"delta":{"content": 7}}]}\n', REASON_BAD_SHAPE),
    )
    for line, expected in cases:
        post = RecordingStreamPost(lines=(line,))
        output = streaming_provider_over(post).call_streaming(
            compiled(), lambda _chunk: None
        )
        assert (output.text, output.error) == (None, expected), line


def test_non_2xx_answers_the_status_and_never_reads_the_body() -> None:
    post = RecordingStreamPost(status=401)
    output = streaming_provider_over(post).call_streaming(
        compiled(), lambda _chunk: None
    )
    assert (output.text, output.error) == (None, "http-401")
    assert post.call_count == 1


def test_transport_failures_before_and_mid_stream_are_values() -> None:
    dead = RecordingStreamPost(raises=RuntimeError("socket exploded"))
    output = streaming_provider_over(dead).call_streaming(
        compiled(), lambda _chunk: None
    )
    assert (output.text, output.error) == (None, REASON_TRANSPORT_ERROR)

    timed_out = RecordingStreamPost(raises=TimeoutError())
    output = streaming_provider_over(timed_out).call_streaming(
        compiled(), lambda _chunk: None
    )
    assert (output.text, output.error) == (None, REASON_TIMEOUT)

    for exc in (TimeoutError(), RuntimeError("halfway gone")):
        mid = RecordingStreamPost(
            # no [DONE]: the transport dies before the stream ends
            lines=sse_lines("partial", done=False),
            mid_stream_raises=exc,
        )
        seen: list[str] = []
        output = streaming_provider_over(mid).call_streaming(
            compiled(), seen.append
        )
        expected = (
            REASON_TIMEOUT
            if isinstance(exc, TimeoutError)
            else REASON_TRANSPORT_ERROR
        )
        assert (output.text, output.error) == (None, expected)
        # The increment emitted before the failure cannot be recalled — the
        # honest whole is the error value, and the caller owns the partial.
        assert seen == ["partial"]


def test_key_echo_is_refused_on_the_accumulated_buffer_even_across_chunks() -> None:
    whole = RecordingStreamPost(lines=sse_lines(f"leaking {SENTINEL_KEY} now"))
    seen: list[str] = []
    output = streaming_provider_over(whole).call_streaming(
        compiled(), seen.append
    )
    assert (output.text, output.error) == (None, REASON_KEY_ECHO)
    assert seen == []  # the leaking chunk never reached emit

    first_half, second_half = SENTINEL_KEY[:10], SENTINEL_KEY[10:]
    split = RecordingStreamPost(lines=sse_lines(first_half, second_half, "!"))
    seen = []
    output = streaming_provider_over(split).call_streaming(
        compiled(), seen.append
    )
    assert (output.text, output.error) == (None, REASON_KEY_ECHO)
    # The chunk that *completes* the echo is the one refused; whatever went
    # out before it is the caller's partial stream to own.
    assert seen == [first_half]


def test_oversized_stream_is_a_value_and_empty_stream_is_no_output() -> None:
    big = "x" * (MAX_PROVIDER_RESPONSE_BYTES + 1)
    post = RecordingStreamPost(
        lines=(
            b"data: "
            + json.dumps(
                {"choices": [{"delta": {"content": big}}]}
            ).encode("utf-8")
            + b"\n",
        )
    )
    output = streaming_provider_over(post).call_streaming(
        compiled(), lambda _chunk: None
    )
    assert (output.text, output.error) == (None, REASON_RESPONSE_TOO_LARGE)

    empty = RecordingStreamPost(lines=(b"data: [DONE]\n",))
    output = streaming_provider_over(empty).call_streaming(
        compiled(), lambda _chunk: None
    )
    assert (output.text, output.error) == ("", None)


# ---------------------------------------------------------------------------
# Group 2 — the web bridge over the real stack and a fake OpenAI endpoint
# ---------------------------------------------------------------------------


class _FakeOpenAI:
    """A loopback OpenAI-compatible endpoint that speaks both faces.

    ``"stream": true`` in the request body is answered with the reply as
    SSE, one character per ``data:`` line, ``[DONE]`` at the end; a body
    without the flag gets the buffered JSON completion — so one stack can
    pin the streamed and the blocking face against each other. Every
    request's body flag and Authorization header is recorded.

    The gate (``arm_gate`` / ``release_gate``) is the interleaving pin's
    instrument: when armed, the SSE arm writes its **first** chunk, then
    blocks the provider's generation on the event until the test releases
    it — so a delta the test observes before releasing can only have been
    forwarded while generation was still running (DEC-…77's live reading;
    a collect-then-play bridge would deadlock this test).
    """

    def __init__(self) -> None:
        self.received: list[dict[str, object]] = []
        self.first_chunk_flushed = threading.Event()
        self._gate: threading.Event | None = None
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def arm_gate(self) -> threading.Event:
        """Arm the after-first-chunk gate; the caller holds the handle."""

        self._gate = threading.Event()
        self.first_chunk_flushed.clear()
        return self._gate

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                outer.received.append(
                    {
                        "stream": body.get("stream"),
                        "authorization": self.headers.get("Authorization"),
                    }
                )
                self.send_response(200)
                if body.get("stream") is True:
                    gate = outer._gate
                    outer._gate = None
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for index, character in enumerate(REPLY):
                        frame = json.dumps(
                            {"choices": [{"delta": {"content": character}}]}
                        )
                        self.wfile.write(
                            b"data: " + frame.encode("utf-8") + b"\n\n"
                        )
                        self.wfile.flush()
                        if index == 0:
                            outer.first_chunk_flushed.set()
                            if gate is not None:
                                gate.wait(timeout=60)
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                else:
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(
                            {"choices": [{"message": {"content": REPLY}}]}
                        ).encode("utf-8")
                    )

            def log_message(self, *args: object) -> None:
                del args  # silence the per-request stderr lines

        return Handler


def _openai_stack(app_db: Path, endpoint: _FakeOpenAI):
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url=f"http://127.0.0.1:{endpoint.port}/v1",
            model="a1-model",
            secret_ref=FIXED_SECRET_REF,
        ),
        FixedSecret(),
    )
    return web_stack(app_db, provider=provider)


def _post(port: int, path: str, payload: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover — grammar arms
        return exc.code, exc.read()


def _sse_frames(raw: bytes) -> list[dict[str, object]]:
    frames = []
    for blob in raw.split(b"\n\n"):
        blob = blob.strip()
        if not blob:
            continue
        assert blob.startswith(b"data: "), blob
        frames.append(json.loads(blob[len(b"data: "):].decode("utf-8")))
    return frames


def test_stream_endpoint_answers_deltas_then_one_final_equal_to_turn(
    tmp_path: Path,
) -> None:
    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
            assert status == 200
            frames = _sse_frames(raw)
            deltas = [f for f in frames if f["type"] == "delta"]
            finals = [f for f in frames if f["type"] == "final"]
            others = [f for f in frames if f["type"] not in ("delta", "final")]
            # A2 (DEC-…82): the narrative order adds one structured
            # ``world`` frame — the story block's data — before the
            # first delta; the world's step now runs before generation.
            # This bound stack tells Berrymoor's day, so the frame is
            # here; the rest of the grammar is unchanged.
            assert [f["type"] for f in others] == ["world"]
            world = others[0]
            assert world["world_name"] == "Berrymoor"
            assert isinstance(world["date_localized"], str)
            assert world["date_localized"]
            assert world["ui_language"] in ("zh", "en")
            assert isinstance(world["notes"], list)
            assert len(finals) == 1
            final = finals[0]
            # The event order is the contract: the world's story first,
            # the deltas next, the final last.
            assert frames[-1] is final
            assert frames[0] is world
            assert frames[1]["type"] == "delta"
            # The streaming was real: one delta per character of the reply.
            assert [f["text"] for f in deltas] == list(REPLY)
            assert "".join(f["text"] for f in deltas) == final["reply"]

            status, blocking_raw = _post(stack.port, "/api/turn", {"text": A1_TEXT})
            assert status == 200
            blocking = json.loads(blocking_raw.decode("utf-8"))
            assert set(final.keys()) - {"type"} == set(blocking.keys())
            assert set(blocking.keys()) == TURN_PAYLOAD_KEYS
            for key in (
                "reply",
                "turn_status",
                "failure_reason",
                "teaching_moments",
                "word_hits",
                "user_word_hits",
                "usage",
            ):
                assert final[key] == blocking[key], key
            # The streamed request is the one that carried "stream": true.
            assert endpoint.received[0]["stream"] is True
            assert endpoint.received[1]["stream"] is None
            assert all(
                call["authorization"] == f"Bearer {SENTINEL_KEY}"
                for call in endpoint.received
            )
    finally:
        endpoint.stop()


def test_deltas_flow_while_generation_is_still_running(tmp_path: Path) -> None:
    """The interleaving pin (DEC-…77's decisive instrument).

    The fake endpoint writes its **first** chunk, then blocks the
    provider's generation on a gate only the test holds. The test reads
    the SSE stream from its side and releases the gate the moment it
    observes a delta — so a delta on the page *before* the gate opened
    can only have been forwarded while generation was still running. A
    bridge that collected the answer and replayed it at the end would
    never produce that first delta (generation cannot finish before the
    gate), the read would time out, and this test would go red.
    """

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            gate = endpoint.arm_gate()
            body = json.dumps({"text": A1_TEXT}).encode("utf-8")
            sock = socket.create_connection(("127.0.0.1", stack.port))
            request = (
                b"POST /api/turn_stream HTTP/1.0\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n"
            )
            sock.sendall(request + body)
            sock.settimeout(30)
            head = b""
            while b'"type": "delta"' not in head and b'"type":"delta"' not in head:
                head += sock.recv(4096)  # times out under collect-then-play
            # A delta is on the page; the reply cannot be finished yet.
            assert endpoint.first_chunk_flushed.is_set()
            gate.set()  # only now may generation run past its first chunk
            rest = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                rest += chunk
            sock.close()
            # The first read carries the response headers; the SSE body
            # starts after the blank line.
            _, _, head_body = head.partition(b"\r\n\r\n")
            frames = _sse_frames(head_body + rest)
            finals = [f for f in frames if f["type"] == "final"]
            deltas = [f for f in frames if f["type"] == "delta"]
            assert len(finals) == 1 and finals[0]["reply"] == REPLY
            assert [f["text"] for f in deltas] == list(REPLY)
    finally:
        endpoint.stop()


def test_provider_without_stream_face_answers_zero_deltas_single_final(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        assert [f["type"] for f in frames] == ["final"]
        final = frames[0]
        assert set(final.keys()) - {"type"} == TURN_PAYLOAD_KEYS
        assert final["reply"] == REPLY
        assert final["turn_status"] == "COMPLETED"


def test_a_failed_bridge_injection_degrades_to_one_final_with_the_assembly_intact(
    tmp_path: Path,
) -> None:
    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            host = stack.box["host"]
            original = host.coordinator.replace_persona_provider
            swaps = {"n": 0}

            def flaky(provider: object) -> None:
                swaps["n"] += 1
                if swaps["n"] == 1:
                    # the proxy install is the bridge's one injection point
                    raise RuntimeError("injection refused")
                original(provider)

            host.coordinator.replace_persona_provider = flaky  # type: ignore[method-assign]
            try:
                status, raw = _post(
                    stack.port, "/api/turn_stream", {"text": A1_TEXT}
                )
            finally:
                del host.coordinator.replace_persona_provider  # type: ignore[attr-defined]
            assert host.coordinator.replace_persona_provider == original
            assert status == 200
            frames = _sse_frames(raw)
            # A2 (DEC-…82): the world step runs before the bridge is
            # installed, so its story frame is already out when the
            # injection refuses — the degradation answer is the world
            # frame plus the one failure-shaped final (no deltas).
            assert [f["type"] for f in frames] == ["world", "final"]
            final = frames[-1]
            assert final["reply"] is None
            assert final["turn_status"] is None
            assert "injection refused" in str(final["failure_reason"])
            # The live provider was never swapped: the next blocking turn
            # answers exactly as before.
            status, blocking_raw = _post(stack.port, "/api/turn", {"text": A1_TEXT})
            blocking = json.loads(blocking_raw.decode("utf-8"))
            assert (status, blocking["reply"]) == (200, REPLY)
    finally:
        endpoint.stop()


def test_a_disconnecting_reader_stops_the_writing_never_the_turn(
    tmp_path: Path,
) -> None:
    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            body = json.dumps({"text": A1_TEXT}).encode("utf-8")
            sock = socket.create_connection(("127.0.0.1", stack.port))
            request = (
                b"POST /api/turn_stream HTTP/1.0\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n"
            )
            sock.sendall(request + body)
            sock.settimeout(10)
            head = b""
            while b"delta" not in head:
                head += sock.recv(4096)
            sock.close()  # the reader is gone mid-stream
            # The turn runs to its durable end: the reply lands in history.
            deadline = time.monotonic() + 30.0
            turns: list[dict[str, object]] = []
            while time.monotonic() < deadline:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{stack.port}/api/history", timeout=10
                ) as response:
                    turns = json.loads(response.read().decode("utf-8"))["turns"]
                if any(turn["assistant"] == REPLY for turn in turns):
                    break
                time.sleep(0.1)
            assert any(turn["assistant"] == REPLY for turn in turns)
    finally:
        endpoint.stop()


def test_the_stream_grammar_is_the_blocking_turns_own(tmp_path: Path) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        request = urllib.request.Request(
            f"http://127.0.0.1:{stack.port}/api/turn_stream",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=10)
            raised = False
        except urllib.error.HTTPError as exc:
            raised = True
            assert exc.code == 400
            assert json.loads(exc.read().decode("utf-8")) == {
                "error": 'need a JSON body {"text": "..."}'
            }
        assert raised


# ---------------------------------------------------------------------------
# Group 3 — the page wiring, as source facts
# ---------------------------------------------------------------------------


def _postturn_slice(app_source: str) -> str:
    start = app_source.index("async function postTurn")
    end = app_source.index("\nasync function ", start + 1)
    return app_source[start:end]


def test_the_page_wires_reader_typewriter_finalize_fallback_and_no_resend() -> None:
    api_source = (WEBUI / "api.js").read_text(encoding="utf-8")
    app_source = (WEBUI / "app.js").read_text(encoding="utf-8")

    # api.js: the stream wrapper really reads the body defensively.
    # A2 (DEC-…82): the third callback — the world story frame's own
    # handler — rides the same defensive parser.
    assert "export async function fetchTurnStream(text, onDelta, onWorld)" in (
        api_source
    )
    assert "res.body.getReader()" in api_source
    assert "new TextDecoder()" in api_source
    assert 'startsWith("data: ")' in api_source
    assert "err.started = false" in api_source
    assert "interrupted.started = true" in api_source
    assert "if (!res.ok || !res.body) return null;" in api_source
    assert 'event.type === "delta"' in api_source
    assert 'event.type === "world"' in api_source
    assert 'event.type === "final"' in api_source

    postturn = _postturn_slice(app_source)
    # The stream face goes first; the typewriter (A2: the fixed-rate
    # pacer — deltas land in the buffer, the render loop spends them at
    # TYPING_CPS) accumulates into textContent only (the XSS discipline);
    # the fallback and the finalize pairing follow; the started arm pulls
    # history and never resends.
    assert "fetchTurnStream(" in postturn
    assert "renderWorldStory(event)" in postturn
    assert "typing.push(chunk)" in postturn
    assert "await typing.seal(" in postturn
    assert "startTypewriter()" in postturn
    typewriter = app_source[app_source.index("function startTypewriter"):]
    typewriter = typewriter[: typewriter.index("\n}", typewriter.index("return {"))]
    assert "ensureLine().textContent = state.shown;" in typewriter
    assert "requestAnimationFrame" in typewriter
    assert "cancelAnimationFrame" in typewriter
    assert "const TYPING_CPS = 35;" in app_source
    assert "err.started" in postturn
    started_arm = postturn[postturn.index("err.started"):]
    started_arm = started_arm[: started_arm.index("} else {")]
    assert "loadHistory()" in started_arm
    # DEC-…92: the turn no longer rereads the world (the pre-step
    # already revealed and presented) — neither on the started arm nor
    # at the finalize tail.
    assert "loadWorldInbox" not in started_arm
    assert "fetchTurn(" not in started_arm
    assert postturn.index("fetchTurnStream(") < postturn.index("fetchTurn(")
    # A2R (user report「信件内容重复打了两遍」加固): the null arm —
    # fetchTurnStream answered null (non-2xx / no body), where the
    # letter MAY already be committed server-side — never re-POSTs;
    # it reconciles with history instead. Only the catch's
    # not-started arm (fetch itself threw: the letter never left)
    # keeps the plain fallback. One fetchTurn call site remains.
    assert postturn.count("await fetchTurn(text)") == 1
    null_arm = postturn[postturn.index("if (data === null)"):]
    null_arm = null_arm[: null_arm.index("} else {")]
    assert "fetchTurn(" not in null_arm
    assert "loadHistory()" in null_arm
    # The finalize block survived underneath the stream attempt.
    assert "applyLetterAffordance(mine, data.user_word_hits || null);" in postturn
    assert "showMoments(moments);" in postturn


def test_the_server_bridge_wires_the_live_generation_stream() -> None:
    web_source = (SRC / "web.py").read_text(encoding="utf-8")
    provider_source = (SRC / "persona" / "openai_provider.py").read_text(
        encoding="utf-8"
    )

    # The live reading (DEC-…77): the capability probe comes first, the
    # proxy is installed over the live provider, and call_streaming's emit
    # is wired straight to the turn's queue — increments reach the page as
    # they are generated.
    assert 'hasattr(live, "call_streaming")' in web_source
    assert "coordinator.replace_persona_provider(" in web_source
    assert "coordinator.replace_persona_provider(live)" in web_source
    assert "prompt, self._bridge.push" in web_source
    # The durable delivery seam is untouched by the bridge (no second
    # sender; the §22 rows stay a blocking turn's).
    assert "replace_stream_transport" not in web_source
    assert "def call_streaming" in provider_source
    assert "def _urllib_stream_post" in provider_source


# ---------------------------------------------------------------------------
# Group 4 — the old contract, unchanged
# ---------------------------------------------------------------------------


def test_blocking_turn_payload_keys_are_exactly_what_they_were(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, raw = _post(stack.port, "/api/turn", {"text": A1_TEXT})
        assert status == 200
        payload = json.loads(raw.decode("utf-8"))
        assert set(payload.keys()) == TURN_PAYLOAD_KEYS
        assert payload["reply"] == REPLY
        assert payload["turn_status"] == "COMPLETED"


def test_a_blocking_turn_after_a_streamed_one_is_unchanged(
    tmp_path: Path,
) -> None:
    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            _, stream_raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
            streamed = [f for f in _sse_frames(stream_raw) if f["type"] == "final"][0]
            _, blocking_raw = _post(stack.port, "/api/turn", {"text": A1_TEXT})
            blocking = json.loads(blocking_raw.decode("utf-8"))
            assert set(blocking.keys()) == TURN_PAYLOAD_KEYS
            assert blocking["reply"] == streamed["reply"] == REPLY
            assert blocking["turn_status"] == streamed["turn_status"]
            assert blocking["usage"] == streamed["usage"] is None
    finally:
        endpoint.stop()


# ---------------------------------------------------------------------------
# Group 5 — the instrumentation: the piece calibration and the transport
# ---------------------------------------------------------------------------


def test_the_live_delta_queue_and_the_proxy_forward_increments_in_order() -> None:
    from elc.web import _StreamingProviderProxy, _TurnStreamBridge

    events: queue.Queue[str] = queue.Queue()

    # The bridge is the page's delta channel: push half only, FIFO.
    bridge = _TurnStreamBridge(events)
    bridge.push("one")
    bridge.push("two")
    assert (events.get_nowait(), events.get_nowait()) == ("one", "two")
    with pytest.raises(queue.Empty):
        events.get_nowait()

    # The proxy: call_streaming's emit goes straight to the bridge (live),
    # and the buffered answer passes through untouched.
    class _ScriptedStreamProvider:
        def call_streaming(self, prompt: object, emit: Callable[[str], None]):
            emit("live ")
            emit("text")
            return ProviderOutput(text="live text", error=None)

    proxy = _StreamingProviderProxy(_ScriptedStreamProvider(), bridge)  # type: ignore[arg-type]
    output = proxy.call(compiled())
    assert (output.text, output.error) == ("live text", None)
    assert (events.get_nowait(), events.get_nowait()) == ("live ", "text")


def test_a_failed_stream_still_owns_its_already_forwarded_increments() -> None:
    """The honest partial-stream edge (N-A1-3): an increment already pushed
    live cannot be recalled on a later failure — the caller owns what the
    page saw, and the error value still comes back as the whole."""

    from elc.web import _StreamingProviderProxy, _TurnStreamBridge

    events: queue.Queue[str] = queue.Queue()
    bridge = _TurnStreamBridge(events)

    class _FailingStreamProvider:
        def call_streaming(self, prompt: object, emit: Callable[[str], None]):
            emit("par")
            return ProviderOutput(text=None, error="http-500")

    proxy = _StreamingProviderProxy(_FailingStreamProvider(), bridge)  # type: ignore[arg-type]
    output = proxy.call(compiled())
    assert (output.text, output.error) == (None, "http-500")
    assert events.get_nowait() == "par"  # the page saw it; it stays seen
