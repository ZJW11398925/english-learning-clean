"""The CURRENT_USER_ERROR producer — one turn's text through the registry.

D-6-a turns the D-3 pilot matchers from a *build-time* verification set into
a *runtime* producer: the user's turn text goes once through every registered
matcher, and the entity ids whose matchers fire are the turn's
``current_user_errors`` — exactly the target ids
:class:`elc.planner.candidates.OpportunityObservation`'s
``current_user_errors`` field carries, which is the only input the
CURRENT_USER_ERROR generator reads. Detection is a *producer of candidate
target ids* here and nothing more: the pricing is the source reading's
(:mod:`elc.planner.candidates`), the identity is the content rows', and the
opening decision is the Gate's — a hit opens nothing by itself.

**Two failure layers, two postures, said apart.** The build step
(``elc.content.build``) wraps a matcher exception into a ``BuildError`` and
**refuses the build**: a broken detector must not earn ``EXECUTABLY_VERIFIED``
rows, and a corpus that cannot be verified must not ship as if it were. This
module is the runtime half, and it **skips** the failing target instead: a
matcher that raises on one turn's text costs at most one missed teaching
opportunity this turn, while an exception out of the dispatch would break the
user's turn itself — and the user turn must not break (RA §21's degradation
direction, now applied to the detection leg). The layering is deliberate:
construction-time facts refuse, run-time reads degrade.

The output is **sorted and de-duplicated** whatever order the registry offers
its entries in, so the observation a turn produces is a deterministic fact of
the text and the detector set — not of registration order — and the same text
cannot mint the same target id twice.
"""

from __future__ import annotations

from elc.detection.registry import DetectorRegistry
from elc.detection.types import DetectionMatch

__all__ = ["RegistryDispatch", "detect_current_user_errors"]


def detect_current_user_errors(
    text: str, registry: DetectorRegistry
) -> tuple[str, ...]:
    """Run every registered matcher over ``text``; answer the hit ids.

    One matcher exception skips **its own target only** (the module
    docstring's runtime layer — a lost teaching opportunity is acceptable, a
    broken turn is not); the remaining matchers still answer. The ids are
    sorted and de-duplicated, so the answer depends on the text and the
    detector set, never on the registry's iteration order.
    """

    hits: list[str] = []
    for entry in registry.entries():
        try:
            match: DetectionMatch | None = entry.matcher(text)
        except Exception:  # noqa: BLE001 — one broken matcher, one skipped id
            continue
        if match is not None:
            hits.append(entry.entity_id)
    return tuple(sorted(set(hits)))


class RegistryDispatch:
    """The registry-bound face the composition root injects into the wiring.

    One small class rather than a closure, so the deployment's dispatch face
    has a name and a docstring; it carries the registry it was bound to and
    nothing else. Its single method is
    ``elc.runtime.automatic_turn.ErrorDetectorFace``'s shape, so it satisfies
    that protocol structurally — the host hands one in with no adapter.
    """

    __slots__ = ("_registry",)

    def __init__(self, registry: DetectorRegistry) -> None:
        self._registry = registry

    def detect_current_user_errors(self, text: str) -> tuple[str, ...]:
        """The bound form of :func:`detect_current_user_errors`."""

        return detect_current_user_errors(text, self._registry)
