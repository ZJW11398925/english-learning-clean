"""The adapter's value contract (prep-1 deliverable A) — every vector offline.

Seven cases, no socket: each one injects an ``HttpPost`` (or a raising one) and
asserts the exact :class:`ProviderOutput` shape plus the request the adapter
built. The reason vocabulary is short and body-free, and the key travels in the
``Authorization`` header of exactly one request — never in the URL, the body,
a reason code or an exception message.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from elc.persona import openai_provider as adapter
from elc.persona.openai_provider import (
    REASON_BAD_JSON,
    REASON_BAD_SHAPE,
    REASON_KEY_ECHO,
    REASON_MISSING_SECRET,
    REASON_TIMEOUT,
    REASON_TRANSPORT_ERROR,
    OpenAICompatibleProvider,
)
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.secrets import EnvSecretSource, FileSecretSource
from elc.platform.types import PersonaId
from tests.host.support import (
    FIXED_SECRET_REF,
    REPLY_TEXT,
    SENTINEL_KEY,
    FixedSecret,
    RecordingPost,
    completion,
    config,
)


def compiled(text: str = "hello there") -> CompiledPrompt:
    return CompiledPrompt(
        persona_id=PersonaId("persona-offline"),
        prompt_text=text,
        generation_contract="gc-normal-persona-reply",
    )


def provider_over(post: RecordingPost, **overrides: object):
    return OpenAICompatibleProvider(config(**overrides), FixedSecret(), transport=post)


def test_a_successful_call_returns_the_text_and_keeps_the_key_in_the_header() -> None:
    post = RecordingPost(payload=completion())
    output = provider_over(post).call(compiled())

    assert (output.text, output.error) == (REPLY_TEXT, None)
    assert post.call_count == 1
    call = post.calls[0]
    assert call["url"] == "http://offline.invalid/v1/chat/completions"
    assert call["headers"] == {
        "Authorization": f"Bearer {SENTINEL_KEY}",
        "Content-Type": "application/json",
    }
    body = json.loads(call["body"])
    assert body == {
        "model": "offline-model",
        "messages": [{"role": "user", "content": "hello there"}],
    }
    # The key is in the header and nowhere else in the request.
    assert SENTINEL_KEY.encode() not in call["body"]
    assert SENTINEL_KEY not in call["url"]

    with_temperature = RecordingPost(payload=completion())
    provider_over(with_temperature, temperature=0.2).call(compiled())
    assert json.loads(with_temperature.calls[0]["body"])["temperature"] == 0.2


def test_non_2xx_statuses_are_values() -> None:
    for status in (401, 429, 500):
        post = RecordingPost(
            status=status,
            # A hostile error page that echoes the request's header: the
            # status is the whole reason, the body is never read.
            payload=f"denied for bearer {SENTINEL_KEY}".encode(),
        )
        output = provider_over(post).call(compiled())
        assert (output.text, output.error) == (None, f"http-{status}")


def test_unusable_bodies_are_values() -> None:
    shapes: tuple[bytes, ...] = (
        b"not json at all",
        b'"a bare string"',
        b"{}",
        b'{"choices": []}',
        b'{"choices": ["not an object"]}',
        b'{"choices": [{"message": {}}]}',
        b'{"choices": [{"message": {"content": 7}}]}',
    )
    for payload in shapes:
        post = RecordingPost(payload=payload)
        output = provider_over(post).call(compiled())
        expected = REASON_BAD_JSON if payload == shapes[0] else REASON_BAD_SHAPE
        assert (output.text, output.error) == (None, expected), payload


def test_a_timeout_is_a_value() -> None:
    post = RecordingPost(raises=TimeoutError("timed out after 30s"))
    output = provider_over(post).call(compiled())
    assert (output.text, output.error) == (None, REASON_TIMEOUT)


def test_a_transport_error_is_a_value_and_carries_no_message_text() -> None:
    post = RecordingPost(raises=OSError(f"connection refused for key {SENTINEL_KEY}"))
    output = provider_over(post).call(compiled())
    assert (output.text, output.error) == (None, REASON_TRANSPORT_ERROR)
    assert SENTINEL_KEY not in (output.error or "")


def test_a_missing_secret_is_a_value_and_no_request_leaves_the_process() -> None:
    for missing in (None, ""):
        post = RecordingPost(payload=completion())
        provider = OpenAICompatibleProvider(
            config(), FixedSecret(value=missing), transport=post
        )
        output = provider.call(compiled())
        assert (output.text, output.error) == (None, REASON_MISSING_SECRET)
        assert post.call_count == 0


def test_secret_sources_answer_none_for_every_missing_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSecretSource(path=tmp_path / "secrets.json")
    assert source.resolve(FIXED_SECRET_REF) is None  # the file does not exist

    document = tmp_path / "secrets.json"
    for text, expected in (
        ("{not json", None),
        ('["a list"]', None),
        ('{"other-ref": "sk-x"}', None),
        ('{"api-key": 7}', None),
        ('{"api-key": ""}', None),
        ('{"api-key": "sk-from-file"}', "sk-from-file"),
    ):
        document.write_text(text, encoding="utf-8")
        assert source.resolve(FIXED_SECRET_REF) == expected, text

    monkeypatch.setenv("PREP1_TEST_KEY", "sk-from-env")
    assert EnvSecretSource(var="PREP1_TEST_KEY").resolve(FIXED_SECRET_REF) == (
        "sk-from-env"
    )
    monkeypatch.setenv("PREP1_TEST_KEY", "")
    assert EnvSecretSource(var="PREP1_TEST_KEY").resolve(FIXED_SECRET_REF) is None
    monkeypatch.delenv("PREP1_TEST_KEY", raising=False)
    assert EnvSecretSource(var="PREP1_TEST_KEY").resolve(FIXED_SECRET_REF) is None


# -- the real egress function itself (prep-1 review F1) ----------------------


class _FakeResponse:
    """The context-manager shape ``urlopen`` answers with, no socket."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_the_real_egress_function_is_executed_and_its_two_properties_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1: ``_urllib_post`` is the repository's only real network function, so
    the two properties its docstring promises are pinned **against that
    function**, with ``urllib.request.urlopen`` monkeypatched (no socket).

    Three facts, in this order: the patched ``urlopen`` really is the path the
    adapter takes (negative control: the key arrives in the ``Authorization``
    header of the request it receives); a non-2xx answer's body is **never
    read**; and a ``URLError`` whose reason is a timeout is normalized to
    ``TimeoutError`` (which the adapter answers as ``timeout``).
    """

    seen: list[object] = []
    read_calls: list[int] = []

    class _SpyBody(io.BytesIO):
        """A real file-like whose ``read`` records that it was ever called."""

        def read(self, *args: object, **kwargs: object) -> bytes:
            read_calls.append(1)
            return super().read(*args, **kwargs)  # type: ignore[arg-type]

    def ok(request: object, timeout: float | None = None) -> _FakeResponse:
        seen.append(request)
        return _FakeResponse(200, completion())

    provider = OpenAICompatibleProvider(config(), FixedSecret(), transport=None)
    monkeypatch.setattr(adapter.urllib.request, "urlopen", ok)
    assert provider.call(compiled()) == ProviderOutput(text=REPLY_TEXT, error=None)
    # Negative control: the real path builds a Request carrying the key once.
    assert len(seen) == 1
    request_headers = dict(seen[0].headers)  # type: ignore[attr-defined]
    assert request_headers["Authorization"] == f"Bearer {SENTINEL_KEY}"

    def rejected(request: object, timeout: float | None = None) -> _FakeResponse:
        raise urllib.error.HTTPError(
            "http://offline.invalid/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            _SpyBody(f"denied: Bearer {SENTINEL_KEY}".encode()),
        )

    monkeypatch.setattr(adapter.urllib.request, "urlopen", rejected)
    output = provider.call(compiled())
    assert (output.text, output.error) == (None, "http-401")
    assert read_calls == []  # the rejected body never became a string here
    assert SENTINEL_KEY not in (output.error or "")

    def timing_out(request: object, timeout: float | None = None) -> _FakeResponse:
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(adapter.urllib.request, "urlopen", timing_out)
    assert provider.call(compiled()).error == REASON_TIMEOUT


def test_a_2xx_reply_that_echoes_the_key_is_refused_as_a_value() -> None:
    """prep-1 review F3: the key can only appear in a reply by being leaked
    (it never enters the prompt), so an echoing 2xx is answered as a value."""

    post = RecordingPost(
        payload=json.dumps(
            {"choices": [{"message": {"content": f"you said Bearer {SENTINEL_KEY}"}}]}
        ).encode()
    )
    output = provider_over(post).call(compiled())
    assert (output.text, output.error) == (None, REASON_KEY_ECHO)
    assert SENTINEL_KEY not in (output.error or "")
    # The refusal is about the reply, not the request: the key travelled once.
    assert post.authorization == f"Bearer {SENTINEL_KEY}"
