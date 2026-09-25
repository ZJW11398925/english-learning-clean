"""BYOK OpenAI-compatible provider adapter (prep-1) — the one real egress.

docs/PRODUCT_CONTRACT.md §11 puts "OpenAI-compatible ``baseURL`` + key +
model" (key kept locally) inside the V1 contract; docs/DATA_MODEL.md §2 keeps
secrets out of app.db by reference; docs/RUNTIME_ARCHITECTURE.md §24.3 resolves
the secret **at send time** and keeps it out of the prompt compiler, the
durable generation action, ordinary logs and any portable export.

This module is that adapter, and it changes nothing about the port it fills
(:class:`elc.persona.provider.PersonaProvider`): **failure is a value**
(``ProviderOutput(text=None, error=<reason>)``), never an exception — the same
contract the Phase 1 scripted provider keeps. Three properties are deliberate:

- the key travels in exactly one place — the ``Authorization: Bearer`` header
  of the one request this module builds; never the URL, the body, a return
  value or a reason code;
- reason codes are short and body-free (``http-<status>`` / ``bad-json`` /
  ``bad-shape`` / ``timeout`` / ``missing-secret`` / ``transport-error`` /
  ``key-echo`` / ``cleartext-http`` / ``response-too-large``): a non-2xx body is
  dropped by the transport without ever becoming a string, and a 2xx reply that
  *does* carry the key back is refused as a ``key-echo`` value — so no reply
  this adapter answers with can carry the key into the transcript or the durable
  delivery record (RA §24.3's durable shapes);
- one egress point — :func:`_urllib_post` is the whole of this process's
  network surface (standard library only; ``dependencies = []`` untouched) and
  it is injectable, which is what makes this repository's tests offline.

Three destinations this adapter refuses to travel to (external review
EXT-P1-01/02/05), each a value rather than a raise:

- **nowhere via redirect.** The egress opener replaces urllib's redirect
  handler with one that raises (:class:`_NoRedirects`), so a 301/302/303/307/308
  answer cannot re-send this request — and the key — to a host a ``Location``
  names; it becomes the ordinary ``http-<status>`` value. ``Authorization`` is
  also added as an *unredirected* header (the one kind urllib never copies on a
  redirect): defence in depth, not the primary guard;
- **nowhere in clear but this machine.** Plaintext ``http://`` is accepted on
  loopback hosts only and refused off them as ``cleartext-http`` **before the
  key is resolved**, unless the caller opts in through
  :attr:`OpenAICompatibleConfig.allow_insecure_http`;
- **no unbounded reply.** One answer is read up to
  :data:`MAX_PROVIDER_RESPONSE_BYTES` and no further; a longer one is
  ``response-too-large``, with none of its bytes entering a value.

Two boundaries this adapter does not paper over (prep-1 review F6/F7): the
``"failure is a value"`` promise holds for everything the transport can
report, not for a malformed ``status`` an injected transport might return
(``int(status)`` would raise; the real transport always answers an int), and
``KeyboardInterrupt`` / ``SystemExit`` deliberately escape — an operator
interrupt is not a provider failure.

The call runs outside any DB transaction (RA §24.1; R-INV-004):
``PersonaRuntime`` owns that ordering and this adapter touches no store.
"""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import IO, Mapping, Protocol

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.secrets import SecretSource
from elc.platform.types import SecretRef

__all__ = [
    "MAX_PROVIDER_RESPONSE_BYTES",
    "HttpPost",
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
    "REASON_BAD_JSON",
    "REASON_BAD_SHAPE",
    "REASON_CLEARTEXT_HTTP",
    "REASON_KEY_ECHO",
    "REASON_MISSING_SECRET",
    "REASON_RESPONSE_TOO_LARGE",
    "REASON_TIMEOUT",
    "REASON_TRANSPORT_ERROR",
    "http_reason",
    "insecure_http_destination",
]

#: The failure vocabulary: short, stable, free of any response content.
REASON_MISSING_SECRET = "missing-secret"
REASON_TIMEOUT = "timeout"
REASON_TRANSPORT_ERROR = "transport-error"
REASON_BAD_JSON = "bad-json"
REASON_BAD_SHAPE = "bad-shape"
#: A 2xx answer whose text carries the resolved key back (prep-1 review F3):
#: refuse the reply rather than let the key reach the transcript.
REASON_KEY_ECHO = "key-echo"
#: A plaintext ``http://`` destination off this machine: refused before the key
#: is even resolved (external review EXT-P1-02).
REASON_CLEARTEXT_HTTP = "cleartext-http"
#: A single reply longer than :data:`MAX_PROVIDER_RESPONSE_BYTES` (EXT-P1-05).
REASON_RESPONSE_TOO_LARGE = "response-too-large"

#: The most bytes of one reply this adapter will hold (4 MiB): a chat
#: completion, not a file transfer.
MAX_PROVIDER_RESPONSE_BYTES = 4 * 1024 * 1024

#: Plaintext ``http://`` is accepted on this host name; every loopback
#: **address literal** (``127.0.0.0/8``, ``::1`` and its long spellings) is
#: recognized by :func:`_is_local_host` through the address parser instead.
_LOOPBACK_HOSTS = frozenset({"localhost"})

#: The §11 OpenAI-compatible request path, appended to ``base_url``.
CHAT_COMPLETIONS_PATH = "/chat/completions"


def http_reason(status: int) -> str:
    """``http-401`` / ``http-429`` / ``http-500`` — the status, nothing else."""

    return f"http-{int(status)}"


def insecure_http_destination(base_url: str) -> bool:
    """Is ``base_url`` plaintext ``http://`` **off this machine**? (EXT-P1-02)

    ``https`` is never insecure; ``http`` is acceptable exactly on this machine
    (``localhost`` or a loopback **address**) and nowhere else — the host is
    read lowercased and without its port by :func:`urllib.parse.urlsplit`, so a
    userinfo prefix cannot disguise a foreign host. The provider reads this one
    predicate for its ``cleartext-http`` value and the CLI reads it for the
    sentence naming ``--allow-insecure-http``: the two faces cannot disagree
    about what "off this machine" means.

    Two fail-closed readings (prep-1R review F1/F2): "this machine" is decided
    by the address parser, never by a name's spelling — a resolvable name that
    merely *starts* with a loopback address (``127.0.0.1.evil.example``) is off
    this machine — and a target the URL parser refuses outright
    (``http://[::1``) is treated the same way rather than raising.
    """

    try:
        parts = urllib.parse.urlsplit(base_url)
    except ValueError:
        return True
    if parts.scheme.lower() != "http":
        return False
    return not _is_local_host(parts.hostname or "")


def _is_local_host(host: str) -> bool:
    """``localhost`` or a loopback **address literal** — never a DNS name.

    ``127.0.0.1.evil.example`` and ``127.evil.example`` are names, not
    addresses: only the address parser can tell, so no string prefix is used
    here (prep-1R review F1 — the spelling test this replaces let a
    registrable name through the guard).
    """

    lowered = host.lower()
    if lowered in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(lowered).is_loopback
    except ValueError:
        return False


class HttpPost(Protocol):
    """One HTTP POST → ``(status, body_bytes)``.

    Raising is the transport's way of saying "no answer at all": a
    ``TimeoutError`` (or ``socket.timeout``, its 3.10+ identity) becomes the
    ``timeout`` reason, any other exception becomes ``transport-error``. The
    default is :func:`_urllib_post` (redirect-refusing, header-splitting and
    read-bounded); tests inject a recording callable. The ceiling is re-checked
    once more on whatever a transport returns, so an oversized 2xx answer is
    refused as a value even when an injected callable hands it over — the read
    bound itself belongs to the real transport (prep-1R review INFO-2: the
    re-check is a value-level refusal, not a memory bound for injected ones).
    """

    def __call__(
        self, url: str, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    """The §11 BYOK coordinates: baseURL + model + a secret **reference**.

    ``secret_ref`` is not the key — it is the name the configured
    :class:`~elc.platform.secrets.SecretSource` resolves at send time. The key
    is never a field of this record, so it cannot be logged, serialized or
    compared into a durable shape by accident.

    ``allow_insecure_http`` is the operator's explicit yes to a plaintext
    ``http://`` destination off this machine (a gateway behind TLS termination,
    a private network). It defaults to ``False``, so the default answer to
    "send this key in the clear?" is no.
    """

    base_url: str
    model: str
    secret_ref: SecretRef
    timeout_seconds: float = 30.0
    temperature: float | None = None
    allow_insecure_http: bool = False

    def endpoint(self) -> str:
        """``{base_url}/chat/completions`` (trailing slashes tolerated)."""

        return f"{self.base_url.rstrip('/')}{CHAT_COMPLETIONS_PATH}"


class OpenAICompatibleProvider:
    """``PersonaProvider`` over one OpenAI-compatible chat completion.

    Failure never raises: a missing secret, a non-2xx answer, an unparseable
    body, a shape the endpoint does not honour and a dead transport all come
    back as :class:`ProviderOutput` values carrying one of the module's reason
    codes.
    """

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        secrets: SecretSource,
        transport: HttpPost | None = None,
    ) -> None:
        self._config = config
        self._secrets = secrets
        self._post: HttpPost = transport if transport is not None else _urllib_post

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        """Check the destination, resolve the key, POST once, answer a value.

        The order is the contract: a destination this adapter refuses (plaintext
        ``http://`` off this machine, :data:`REASON_CLEARTEXT_HTTP`) is answered
        **before the key is resolved** — a refusal costs no secret access and,
        of course, no request. A secret source that raises is treated exactly
        like a missing key: no key, no call. A 2xx reply carrying the key back
        is refused (:data:`REASON_KEY_ECHO`) — the one way the key could
        otherwise enter the transcript and the durable delivery record, which RA
        §24.3 keeps it out of. A reply past :data:`MAX_PROVIDER_RESPONSE_BYTES`
        is refused as a value too (:data:`REASON_RESPONSE_TOO_LARGE`).
        """

        if not self._config.allow_insecure_http and insecure_http_destination(
            self._config.base_url
        ):
            return ProviderOutput(text=None, error=REASON_CLEARTEXT_HTTP)
        key = self._resolve_key()
        if key is None:
            return ProviderOutput(text=None, error=REASON_MISSING_SECRET)
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        try:
            status, payload = self._post(
                self._config.endpoint(),
                headers,
                self._request_body(prompt),
                self._config.timeout_seconds,
            )
        except _ResponseTooLarge:
            return ProviderOutput(text=None, error=REASON_RESPONSE_TOO_LARGE)
        except TimeoutError:
            return ProviderOutput(text=None, error=REASON_TIMEOUT)
        except Exception:  # noqa: BLE001 — the transport boundary: values, not raises
            return ProviderOutput(text=None, error=REASON_TRANSPORT_ERROR)
        if not 200 <= int(status) < 300:
            # The status word comes first: the real transport never reads a
            # non-2xx body, so an oversized one cannot arrive here as a shape the
            # ceiling applies to (prep-1R review INFO-1 — the order says which
            # fact wins, and `http-<status>` wins).
            return ProviderOutput(text=None, error=http_reason(status))
        if not isinstance(payload, (bytes, bytearray)):
            # A 2xx answer that is not bytes at all violates the transport
            # contract; answered as a transport failure rather than raising
            # (prep-1R review F2 — the ceiling check used to raise TypeError on
            # exactly this input).
            return ProviderOutput(text=None, error=REASON_TRANSPORT_ERROR)
        if len(payload) > MAX_PROVIDER_RESPONSE_BYTES:
            # The real transport stops reading at the ceiling; restated here so
            # an injected transport cannot hand the adapter an oversized body as
            # a value (the read bound itself belongs to the real transport).
            return ProviderOutput(text=None, error=REASON_RESPONSE_TOO_LARGE)
        output = _parse_success(payload)
        if output.text is not None and key in output.text:
            # A hostile 2xx that echoes the Authorization header would smuggle
            # the key into the reply. The key never enters the prompt, so a
            # reply can only carry it by leaking it — refuse the whole text.
            return ProviderOutput(text=None, error=REASON_KEY_ECHO)
        return output

    # -- internals -----------------------------------------------------------

    def _resolve_key(self) -> str | None:
        try:
            key = self._secrets.resolve(self._config.secret_ref)
        except Exception:  # noqa: BLE001 — the seam is a value boundary too
            return None
        return key if key else None

    def _request_body(self, prompt: CompiledPrompt) -> bytes:
        """§11's minimal body: one user message, no secret anywhere in it."""

        document: dict[str, object] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt.prompt_text}],
        }
        if self._config.temperature is not None:
            document["temperature"] = self._config.temperature
        return json.dumps(document).encode("utf-8")


def _parse_success(payload: bytes) -> ProviderOutput:
    """``choices[0].message.content`` or a ``bad-*`` reason — never a raise."""

    try:
        document = json.loads(payload)
    except ValueError:
        return ProviderOutput(text=None, error=REASON_BAD_JSON)
    content = _content_of(document)
    if content is None:
        return ProviderOutput(text=None, error=REASON_BAD_SHAPE)
    return ProviderOutput(text=content, error=None)


def _content_of(document: object) -> str | None:
    """The one path this adapter reads out of a 2xx body."""

    if not isinstance(document, dict):
        return None
    choices = document.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


class _ResponseTooLarge(Exception):
    """Raised by :func:`_urllib_post` past the read ceiling — never a value.

    Module-private on purpose: raised and caught in this module, and it carries
    the fact only — no byte of the refused body travels with it.
    """


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect handler that refuses to follow: every 3xx is an error.

    urllib's default follows 301/302/303 in answer to a POST (and, for
    ``GET``/``HEAD``, 307/308 too — a POST answering 307/308 already refuses
    inside ``HTTPRedirectHandler`` itself; prep-1R review F3) and re-sends the
    request — ``Authorization`` header included — to whatever host the answer's
    ``Location`` names. A BYOK key must never be replayed to a destination this
    adapter did not choose (EXT-P1-01), so the redirect becomes an
    :class:`urllib.error.HTTPError` here, which :func:`_urllib_post` turns into
    the ordinary ``(status, b"")`` shape the adapter reports as
    ``http-<status>``. This handler is a superset of urllib's own posture: it
    refuses the codes urllib would have followed *and* the ones it would not.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


#: The module's own opener, built lazily on first use. Deliberately **not**
#: ``urllib.request.install_opener``: replacing the process-wide default opener
#: is not this adapter's business, and global state a library installs is
#: global state another caller inherits.
_opener_cache: urllib.request.OpenerDirector | None = None


def _opener() -> urllib.request.OpenerDirector:
    """``build_opener(_NoRedirects)``, built once — and never installed.

    ``build_opener`` drops urllib's own redirect handler because the one passed
    subclasses it, so every request this module sends goes through
    :class:`_NoRedirects`.
    """

    global _opener_cache
    if _opener_cache is None:
        _opener_cache = urllib.request.build_opener(_NoRedirects)
    return _opener_cache


def _urllib_post(
    url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    """The process's only real egress point (standard library ``urllib``).

    Three properties hold here, each pinned executably against *this* function
    (no socket; ``tests/host/test_openai_provider.py`` — prep-1 review F1 and
    this cut's redirect/ceiling pins) so this docstring cannot drift from the
    code it describes:

    - the request goes through the module's own opener (:func:`_opener`), whose
      handler refuses every redirect: a 301/302/303/307/308 answer is an
      :class:`urllib.error.HTTPError` here, never a second request to the
      ``Location``'s host with this key attached (EXT-P1-01);
    - ``Authorization`` travels as an **unredirected** header — the header kind
      urllib's redirect machinery never copies — while the rest travel as
      ordinary headers;
    - a non-2xx answer returns ``(status, b"")``: the error body is deliberately
      **not read**, so no response text of a rejected request becomes a string
      in this process; a 2xx body is read at most
      :data:`MAX_PROVIDER_RESPONSE_BYTES` + 1 bytes (enough to detect overshoot)
      and a longer answer raises :class:`_ResponseTooLarge` without any of its
      bytes entering a value (EXT-P1-05).

    A timeout reported through ``URLError.reason`` is normalized to
    ``TimeoutError`` so the adapter's ``timeout`` reason means the same thing
    for the real transport as for an injected one.
    """

    request = urllib.request.Request(url, data=body, method="POST")
    for name, value in headers.items():
        if name.lower() == "authorization":
            request.add_unredirected_header(name, value)
        else:
            request.add_header(name, value)
    try:
        with _opener().open(request, timeout=timeout) as response:
            payload = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
            if len(payload) > MAX_PROVIDER_RESPONSE_BYTES:
                raise _ResponseTooLarge
            return int(response.status), payload
    except urllib.error.HTTPError as exc:
        return int(exc.code), b""
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError(REASON_TIMEOUT) from exc
        raise
