"""Interrupt-aware transport wrapper — §18's "cancel current stream if possible"
(P9-3).

docs/RUNTIME_ARCHITECTURE.md §17.1 rules 2-3 and §18's first move, as one
small adapter: the guard holder's own stream asks, before every step, whether
the delivery is still wanted, and answers the driver with the one word the
driver understands when it is not. Nothing here decides anything — the durable
request is the caller's read, the stop word is the driver's, and the §22/§21.1
rows are the delivery face's (``elc.runtime.controller``).

Why this is its own module rather than a class inside the coordinator: Gate 1
(tests/architecture/test_gate_1_domain_interfaces) scans **every** class
defined in a domain ``controller.py`` for the Phase 0 red line ("no domain
business logic — every controller method raises NotImplementedError"), and the
allowlist exempts classes, not methods. A transport adapter is behaviour, so it
belongs where the other delivery machinery lives
(``elc.runtime.guarded_stream``'s driver and port, this wrapper, the
coordinator's delivery legs) rather than inside the coordination facade.

The wrapper adds no vocabulary of its own: the reason it stops with is
:data:`INTERRUPT_STOP_REASON`, a constant of this module, because
``guarded_stream``'s reading 6 keeps ``STOPPED(reason)`` as the *source's* own
words and that module must not learn a cancellation word. The coordinator maps
this constant back to §13's ``CANCELLED``; a reader that wants the mapping
reads ``ConversationCoordinator.finalize_streamed_delivery``.
"""

from __future__ import annotations

from typing import Callable

from elc.platform.types import Result
from elc.runtime.guarded_stream import StreamStep, StreamTransport

__all__ = [
    "INTERRUPT_STOP_REASON",
    "InterruptAwareTransport",
]

#: The stop reason the wrapper answers with. It is a *reason string*, not a
#: §13 state word: the driver passes it through verbatim
#: (:attr:`~elc.runtime.guarded_stream.StreamRun.stop_reason`) and the
#: coordinator is what turns it into ``CANCELLED``.
INTERRUPT_STOP_REASON = "interrupt"


class InterruptAwareTransport:
    """Wrap a transport so a durable barge-in stops the stream (§17.1, §18).

    §18's first move is "cancel current stream if possible", and §17.1 rule 3
    names the only actor allowed to do it: the current guard holder. Both
    halves live here: the *holder's own* stream asks one question before every
    step — "is this delivery still wanted?" — and, when it is not, answers the
    driver with the one word the driver understands (:meth:`take` returns
    ``STOPPED``).

    Why the check sits before ``take`` and not before ``emit``: the driver's
    reading 2 guards an accumulated chunk *before* it is released, so a chunk
    taken and then refused on the way out would have been fetched from the
    source for nothing — and an interrupt arriving between the fetch and the
    release would sit in a window where the driver is already committed to
    judging text it will not send. Asking first is the conservative order: the
    interrupt stops the run **before** the next release, so the durable prefix
    is exactly what the client received and never includes a chunk the barge-in
    was meant to prevent.

    The wrapper holds no state at all: ``emit`` is the inner transport's and
    ``pending`` is the caller's read of the durable request (a callable, so the
    caller decides whether the answer comes from a store read or a test's
    script). Revisit: the transport protocol grows a cancellation face of its
    own (then this wrapper retires in its favour), or the check has to move
    *inside* the driver (P9-2's reading 6 moves with it).
    """

    def __init__(
        self, inner: StreamTransport, pending: Callable[[], bool]
    ) -> None:
        self._inner = inner
        self._pending = pending

    def take(self) -> StreamStep:
        if self._pending():
            return StreamStep.stopped(INTERRUPT_STOP_REASON)
        return self._inner.take()

    def emit(self, text: str) -> Result[None]:
        return self._inner.emit(text)
