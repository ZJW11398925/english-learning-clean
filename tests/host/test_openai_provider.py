"""The adapter's value contract (prep-1 deliverable A) — every vector offline.

Seven cases, no socket: each one injects an ``HttpPost`` (or a raising one) and
asserts the exact :class:`ProviderOutput` shape plus the request the adapter
built. The reason vocabulary is short and body-free, and the key travels in the
``Authorization`` header of exactly one request — never in the URL, the body,
a reason code or an exception message.

prep-1R adds the three refusals the external review asked for (EXT-P1-01/02/05)
and re-anchors the F1 egress pin on the opener this cut installs: a redirect is
never followed, a plaintext destination off this machine is refused **before
the key is resolved**, and a reply past the ceiling is refused without any of
its bytes entering a value. Still no socket: the opener is stubbed.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from elc.persona import openai_provider as adapter
from elc.persona.openai_provider import (
    MAX_PROVIDER_RESPONSE_BYTES,
    REASON_BAD_JSON,
    REASON_BAD_SHAPE,
    REASON_CLEARTEXT_HTTP,
    REASON_KEY_ECHO,
    REASON_MISSING_SECRET,
    REASON_RESPONSE_TOO_LARGE,
    REASON_TIMEOUT,
    REASON_TRANSPORT_ERROR,
    OpenAICompatibleProvider,
)
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.secrets import EnvSecretSource, FileSecretSource
from elc.platform.types import PersonaId, SecretRef
from tests.host.support import (
    FIXED_SECRET_REF,
    REPLY_TEXT,
    SENTINEL_KEY,
    FixedSecret,
    RecordingPost,
    completion,
    completion_of_size,
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
    assert call["url"] == "https://offline.invalid/v1/chat/completions"
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


# -- the real egress function itself (prep-1 review F1, re-anchored) ---------


class _FakeResponse:
    """The context-manager shape a real opener answers with, no socket."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self, size: int | None = None) -> bytes:
        return self._body if size is None else self._body[:size]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _StubOpener:
    """An ``OpenerDirector`` stand-in: records the ``Request``, answers a script.

    ``answer`` is either a response to return or an exception to raise, which
    covers the happy path, an ``HTTPError`` and a ``URLError`` with one class.
    """

    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.requests: list[urllib.request.Request] = []

    def open(
        self, request: urllib.request.Request, timeout: float | None = None
    ) -> object:
        self.requests.append(request)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def stub_opener(monkeypatch: pytest.MonkeyPatch, opener: object) -> list[object]:
    """Make the adapter's lazy opener be ``opener`` for one test.

    The module builds (and caches) its opener lazily, so clearing the cache and
    stubbing the builder is exactly the seam :func:`_opener` documents. The
    handlers the adapter asked for are returned, so a pin can assert *which*
    redirect handler it wired — a request that ran through the real
    ``build_opener`` would open a socket, and none of this suite does.
    """

    handlers: list[object] = []

    def fake_build(*wanted: object) -> object:
        handlers.extend(wanted)
        return opener

    monkeypatch.setattr(adapter, "_opener_cache", None)
    monkeypatch.setattr(adapter.urllib.request, "build_opener", fake_build)
    return handlers


def test_the_real_egress_path_is_executed_and_its_properties_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1: ``_urllib_post`` is the repository's only real network function, so
    the properties its docstring promises are pinned **against that function**,
    with the opener stubbed (no socket).

    Three facts, in this order: the stubbed opener really is the path the
    adapter takes (negative control: the key arrives on the ``Request`` it
    receives); a non-2xx answer's body is **never read**; and a ``URLError``
    whose reason is a timeout is normalized to ``TimeoutError`` (which the
    adapter answers as ``timeout``).
    """

    read_calls: list[int] = []

    class _SpyBody(io.BytesIO):
        """A real file-like whose ``read`` records that it was ever called."""

        def read(self, *args: object, **kwargs: object) -> bytes:
            read_calls.append(1)
            return super().read(*args, **kwargs)  # type: ignore[arg-type]

    opener = _StubOpener(_FakeResponse(200, completion()))
    stub_opener(monkeypatch, opener)
    provider = OpenAICompatibleProvider(config(), FixedSecret(), transport=None)
    assert provider.call(compiled()) == ProviderOutput(text=REPLY_TEXT, error=None)
    # Negative control: the real path built one Request carrying the key once.
    assert len(opener.requests) == 1
    assert opener.requests[0].get_header("Authorization") == f"Bearer {SENTINEL_KEY}"

    rejected = _StubOpener(
        urllib.error.HTTPError(
            "https://offline.invalid/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            _SpyBody(f"denied: Bearer {SENTINEL_KEY}".encode()),
        )
    )
    stub_opener(monkeypatch, rejected)
    output = provider.call(compiled())
    assert (output.text, output.error) == (None, "http-401")
    assert read_calls == []  # the rejected body never became a string here
    assert SENTINEL_KEY not in (output.error or "")

    stub_opener(monkeypatch, _StubOpener(urllib.error.URLError(TimeoutError("slow"))))
    assert provider.call(compiled()).error == REASON_TIMEOUT


# -- prep-1R: redirects, the destination policy, the ceiling -----------------


def test_the_redirect_handler_refuses_every_3xx_urllib_would_follow() -> None:
    """EXT-P1-01: the handler urllib consults raises instead of answering a new
    request — for every code urllib itself follows for a POST."""

    request = urllib.request.Request(
        "https://offline.invalid/v1/chat/completions",
        data=b"{}",
        headers={"Authorization": f"Bearer {SENTINEL_KEY}"},
        method="POST",
    )
    for code in (301, 302, 303, 307, 308):
        with pytest.raises(urllib.error.HTTPError) as raised:
            adapter._NoRedirects().redirect_request(
                request, None, code, "Moved", {}, "https://evil.example/evil"
            )
        assert raised.value.code == code
        # The refused request keeps its own URL: nothing was re-aimed at evil.
        assert raised.value.filename == request.full_url


def test_a_3xx_answer_becomes_a_value_and_the_opener_refuses_to_follow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EXT-P1-01, end to end on the real transport path: a 302 from the endpoint
    is the ``http-302`` value, one request leaves, and the opener the adapter
    asked for is the redirect-refusing handler."""

    opener = _StubOpener(
        urllib.error.HTTPError(
            "https://offline.invalid/v1/chat/completions", 302, "Found", {}, None
        )
    )
    handlers = stub_opener(monkeypatch, opener)
    output = OpenAICompatibleProvider(config(), FixedSecret(), transport=None).call(
        compiled()
    )
    assert (output.text, output.error) == (None, "http-302")
    assert len(opener.requests) == 1
    assert opener.requests[0].get_full_url() == (
        "https://offline.invalid/v1/chat/completions"
    )
    # Which redirect handler was wired: passing urllib's default (or dropping
    # the handler) turns this red.
    assert len(handlers) == 1
    assert isinstance(handlers[0], type)
    assert issubclass(handlers[0], adapter._NoRedirects)


class _CountingSecret:
    """A source that remembers whether the key was ever asked for."""

    def __init__(self) -> None:
        self.resolved = 0

    def resolve(self, ref: SecretRef) -> str | None:
        self.resolved += 1
        return SENTINEL_KEY


def test_plaintext_off_this_machine_is_refused_before_the_key_is_resolved() -> None:
    """EXT-P1-02: the refusal is a value, and it comes **first** — no request is
    made and the secret is never resolved (both are negative controls: a pin on
    an unused seam is void)."""

    post = RecordingPost(payload=completion())
    secrets = _CountingSecret()
    provider = OpenAICompatibleProvider(
        config(base_url="http://evil.example/v1"), secrets, transport=post
    )
    output = provider.call(compiled())
    assert (output.text, output.error) == (None, REASON_CLEARTEXT_HTTP)
    assert post.call_count == 0
    assert secrets.resolved == 0


def test_loopback_plaintext_needs_no_opt_in() -> None:
    """``localhost`` / ``127.0.0.0/8`` / ``::1`` are this machine: no flag, no
    refusal, and the request really travels to the injected transport."""

    for base_url in (
        "http://localhost:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://127.9.9.9/v1",
        "http://[::1]:11434/v1",
    ):
        post = RecordingPost(payload=completion())
        output = provider_over(post, base_url=base_url).call(compiled())
        assert (output.text, output.error) == (REPLY_TEXT, None), base_url
        assert post.call_count == 1, base_url


def test_https_may_name_any_host() -> None:
    post = RecordingPost(payload=completion())
    output = provider_over(post, base_url="https://any.example/v1").call(compiled())
    assert (output.text, output.error) == (REPLY_TEXT, None)
    assert post.calls[0]["url"] == "https://any.example/v1/chat/completions"


def test_the_opt_in_allows_plaintext_off_this_machine() -> None:
    """The flag the CLI's pre-check names does exactly what it says: the same
    destination that is refused above travels once it is set."""

    post = RecordingPost(payload=completion())
    output = provider_over(
        post, base_url="http://evil.example/v1", allow_insecure_http=True
    ).call(compiled())
    assert (output.text, output.error) == (REPLY_TEXT, None)
    assert post.call_count == 1


def test_a_reply_exactly_at_the_ceiling_still_parses() -> None:
    post = RecordingPost(payload=completion_of_size(MAX_PROVIDER_RESPONSE_BYTES))
    output = provider_over(post).call(compiled())
    assert output.error is None
    assert output.text is not None and set(output.text) == {"x"}


def test_a_reply_past_the_ceiling_is_refused_without_carrying_any_of_it() -> None:
    post = RecordingPost(payload=completion_of_size(MAX_PROVIDER_RESPONSE_BYTES + 1))
    output = provider_over(post).call(compiled())
    assert (output.text, output.error) == (None, REASON_RESPONSE_TOO_LARGE)
    # No byte of the refused body becomes a string in this process.
    assert "x" * 32 not in repr(output)


def test_the_real_egress_path_splits_the_headers_and_bounds_the_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EXT-P1-01's second half and EXT-P1-05's real half: the ``Request`` the
    real ``_urllib_post`` builds puts ``Authorization`` in ``unredirected_hdrs``
    (the one kind urllib never copies onto a redirect) and asks for exactly one
    byte past the ceiling — the read is bounded at the request, not only at the
    answer."""

    reads: list[int | None] = []

    class _CountingResponse(_FakeResponse):
        def read(self, size: int | None = None) -> bytes:
            reads.append(size)
            return super().read(size)

    opener = _StubOpener(
        _CountingResponse(200, b"x" * (MAX_PROVIDER_RESPONSE_BYTES + 1))
    )
    stub_opener(monkeypatch, opener)
    output = OpenAICompatibleProvider(config(), FixedSecret(), transport=None).call(
        compiled()
    )
    assert (output.text, output.error) == (None, REASON_RESPONSE_TOO_LARGE)
    assert reads == [MAX_PROVIDER_RESPONSE_BYTES + 1]
    request = opener.requests[0]
    unredirected = {
        name.lower(): value for name, value in request.unredirected_hdrs.items()
    }
    assert unredirected == {"authorization": f"Bearer {SENTINEL_KEY}"}
    headers = {name.lower(): value for name, value in request.headers.items()}
    assert headers == {"content-type": "application/json"}


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
