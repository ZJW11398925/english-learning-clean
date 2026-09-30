"""W-7 — one instance per port, and statics that never go stale.

Two dogfood incidents out of the same week, one knife:

1. **the dual instance** — a web restart that did not stop the old
   instance left TWO processes bound to 127.0.0.1:8760. Windows lets a
   second ``ThreadingHTTPServer`` bind an in-use loopback port silently
   (``allow_reuse_address`` is SO_REUSEADDR there — a hijack permission,
   not the POSIX TIME_WAIT relief), and the two runtimes on one app.db
   answered every ``POST /api/turn`` with an instant 500: nothing
   reached the store, no turn row ever appeared. ``run_web`` now probes
   the port before touching anything and refuses with the
   ``WebOpenError`` the CLI branch already answers in human words.
2. **the stale mix** — a long-lived browser tab heuristically cached the
   unversioned static assets and mixed an old shell with a new script
   across a delivery; the new JS died on the old DOM and the page went
   dead. Every static response now carries ``Cache-Control: no-cache`` so
   the browser revalidates against the one source of truth on disk.
"""

from __future__ import annotations

import http.client
import socket
from pathlib import Path

import pytest

from elc.web import WebOpenError, _port_already_serving, run_web
from tests.host.test_w1_web import web_stack


def _cache_control_of(port: int, path: str) -> str | None:
    """One response's Cache-Control header, read raw off the wire."""

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path)
        return conn.getresponse().getheader("Cache-Control")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. one instance per port


def test_the_probe_tells_a_live_listener_from_a_free_port() -> None:
    """The helper's truth: a listening socket answers a connect, a free
    port (and a TIME_WAIT leftover) does not."""

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    busy_port = listener.getsockname()[1]
    try:
        assert _port_already_serving(busy_port) is True
    finally:
        listener.close()
    # a bound-then-closed port is exactly the restart shape — TIME_WAIT
    # leftovers must not read as "serving"
    free_port = busy_port
    for _ in range(50):
        if not _port_already_serving(free_port):
            break
    assert _port_already_serving(free_port) is False


def test_a_second_instance_on_a_serving_port_is_refused(
    tmp_path: Path,
) -> None:
    """run_web against an already-serving port refuses with the
    WebOpenError the CLI answers in human words — before opening the
    conversation, before recovery, before any database touch (this is
    the dual-instance incident's exact shape, replayed)."""

    with web_stack(tmp_path / "app.db") as stack:
        host = stack.box["host"]
        with pytest.raises(WebOpenError, match="already serving"):
            run_web(host, stack.port)


# ---------------------------------------------------------------------------
# 2. statics that never go stale


def test_every_static_response_carries_no_cache(tmp_path: Path) -> None:
    """The page and every asset revalidate on each load — an old shell
    can never mix with a new script again."""

    with web_stack(tmp_path / "app.db") as stack:
        for path in ("/", "/static/components.css", "/static/app.js"):
            assert _cache_control_of(stack.port, path) == "no-cache", path


def test_the_refusal_leaves_the_first_instance_serving(
    tmp_path: Path,
) -> None:
    """A refused second start is a no-op for the live one: the probe
    connects and closes, the serving instance keeps answering (the
    dogfood box must never lose its page to the guard that protects it)."""

    with web_stack(tmp_path / "app.db") as stack:
        host = stack.box["host"]
        with pytest.raises(WebOpenError):
            run_web(host, stack.port)
        status, _, _ = stack.get_raw("/")
        assert status == 200
