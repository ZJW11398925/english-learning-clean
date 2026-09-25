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
  ``bad-shape`` / ``timeout`` / ``missing-secret`` / ``transport-error``): a
  non-2xx body is dropped by the transport without ever becoming a string, so
  a provider that echoes the request cannot smuggle the key into a value;
- one egress point — :func:`_urllib_post` is the whole of this process's
  network surface (standard library only; ``dependencies = []`` untouched) and
  it is injectable, which is what makes this repository's tests offline.

The call runs outside any DB transaction (RA §24.1; R-INV-004):
``PersonaRuntime`` owns that ordering and this adapter touches no store.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.secrets import SecretSource
from elc.platform.types import SecretRef

__all__ = [
    "HttpPost",
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
    "REASON_BAD_JSON",
    "REASON_BAD_SHAPE",
    "REASON_MISSING_SECRET",
    "REASON_TIMEOUT",
    "REASON_TRANSPORT_ERROR",
    "http_reason",
]

#: The failure vocabulary: short, stable, free of any response content.
REASON_MISSING_SECRET = "missing-secret"
REASON_TIMEOUT = "timeout"
REASON_TRANSPORT_ERROR = "transport-error"
REASON_BAD_JSON = "bad-json"
REASON_BAD_SHAPE = "bad-shape"

#: The §11 OpenAI-compatible request path, appended to ``base_url``.
CHAT_COMPLETIONS_PATH = "/chat/completions"


def http_reason(status: int) -> str:
    """``http-401`` / ``http-429`` / ``http-500`` — the status, nothing else."""

    return f"http-{int(status)}"


class HttpPost(Protocol):
    """One HTTP POST → ``(status, body_bytes)``.

    Raising is the transport's way of saying "no answer at all": a
    ``TimeoutError`` (or ``socket.timeout``, its 3.10+ identity) becomes the
    ``timeout`` reason, any other exception becomes ``transport-error``. The
    default is :func:`_urllib_post`; tests inject a recording callable.
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
    """

    base_url: str
    model: str
    secret_ref: SecretRef
    timeout_seconds: float = 30.0
    temperature: float | None = None

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
        """Resolve the key (here, at send time), POST once, answer a value.

        A secret source that raises is treated exactly like a missing key: no
        key, no call.
        """

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
        except TimeoutError:
            return ProviderOutput(text=None, error=REASON_TIMEOUT)
        except Exception:  # noqa: BLE001 — the transport boundary: values, not raises
            return ProviderOutput(text=None, error=REASON_TRANSPORT_ERROR)
        if not 200 <= int(status) < 300:
            return ProviderOutput(text=None, error=http_reason(status))
        return _parse_success(payload)

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


def _urllib_post(
    url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    """The process's only real egress point (standard library ``urllib``).

    A non-2xx answer returns ``(status, b"")``: the error body is deliberately
    **not read**, so no response text of a rejected request becomes a string in
    this process. A timeout reported through ``URLError.reason`` is normalized
    to ``TimeoutError`` so the adapter's ``timeout`` reason means the same
    thing for the real transport as for an injected one.
    """

    request = urllib.request.Request(
        url, data=body, headers=dict(headers), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), b""
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError(REASON_TIMEOUT) from exc
        raise
