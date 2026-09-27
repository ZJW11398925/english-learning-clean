"""The detector registry — who can be executed, against which entity.

D-2 ships the registry **empty**: registering a matcher is a deliberate,
reviewed act (D-3 pilots the first ones), never a side effect of importing
this module. An entry names the entity it verifies and the ordinals of the
entity's declared detection rules it claims to implement — the claim is
*declarative* here and *validated by the build* (a dangling ordinal, or an
entry naming an entity without an evidence document, refuses the build),
because the registry cannot see the authoring source (one-way dependency:
``content.build → detection``, never the reverse). An entry may declare an
**empty** ``rule_ordinals`` — an honest "this matcher corresponds to no
declared rule prose" — which the build accepts.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.detection.types import Matcher


@dataclass(frozen=True)
class DetectorEntry:
    """One registered detector: the entity it verifies and its rule claim."""

    entity_id: str
    rule_ordinals: tuple[int, ...]
    matcher: Matcher


class DetectorRegistry:
    """An insert-only registry of detectors (single-threaded by contract)."""

    def __init__(self) -> None:
        self._entries: dict[str, DetectorEntry] = {}

    def register(
        self,
        entity_id: str,
        rule_ordinals: tuple[int, ...],
        matcher: Matcher,
    ) -> None:
        """Register one detector against one entity.

        A duplicate ``entity_id`` is refused: the registry never silently
        replaces a registered detector (a replacement must be a visible
        unregister-and-re-register act, which V1 does not even offer).
        """

        if entity_id in self._entries:
            raise ValueError(
                f"duplicate detector registration for {entity_id!r} — the "
                "registry never replaces an entry"
            )
        self._entries[entity_id] = DetectorEntry(
            entity_id=entity_id,
            rule_ordinals=tuple(rule_ordinals),
            matcher=matcher,
        )

    def resolve(self, entity_id: str) -> Matcher | None:
        """The registered matcher for one entity, or ``None``."""

        entry = self._entries.get(entity_id)
        return entry.matcher if entry is not None else None

    def known_targets(self) -> tuple[str, ...]:
        """Every registered entity id, sorted."""

        return tuple(sorted(self._entries))

    def entries(self) -> tuple[DetectorEntry, ...]:
        """Every entry, sorted by entity id — the build's validation view."""

        return tuple(self._entries[entity_id] for entity_id in sorted(self._entries))


#: The module-level default registry. **Empty in V1**: no matcher ships with
#: the skeleton, so this registry and a default build (which hands in no
#: registry at all) both derive zero ``EXECUTABLY_VERIFIED`` rows today.
GLOBAL_REGISTRY = DetectorRegistry()
