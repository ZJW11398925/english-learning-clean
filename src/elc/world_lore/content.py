"""Berrymoor — the shipped world's first fact batch (主线-3 first batch).

DEC-OPI-32409938…36 R3: eight to fifteen canonical world facts, written to
echo the penpal's own background (her card row in migration 0019 is the
canon this batch annotates: the bindery with the green door by the water,
the harbour path, her grandfather's workbench, the small harbour town) and
to make every ``lore_refs`` key the shipped cards name resolvable — the
penpal's ``('lore-berrymoor-harbour', 'lore-bindery-green-door')`` and the
persona fixture's ``('lore-shop-menu', 'lore-city-seattle')`` alike.

Scope reading: the Berrymoor rows are ``world`` facts (the town two
characters can stand in conversation about); Maya's two coffee-shop rows and
Nell's Sunday-walk row are ``character`` facts keyed to their personas — the
one visible proof that the character scope answers only its own owner. The
batch is twelve rows: nine world, three character.

Lore content is UNTRUSTED_CONTENT (BF-05; P-INV-013): it renders inside the
prompt's framed ``[lore]`` section and can never write the prompt's
structure; it is seeded here (the composition root's builtin content, the
penpal-package precedent) and never from user or model text.

The seed is idempotent: every id is stable (``wlf-<canonical_key>``), and
the store's append ignores a repeated primary key — an open re-seeds these
rows into a no-op.
"""

from __future__ import annotations

from elc.platform.types import Err
from elc.world_lore.store import (
    SqliteWorldLoreStore,
    WorldLoreFactRow,
    WorldLoreStoreError,
)
from elc.world_lore.types import WorldLoreFactKind

__all__ = ["BERRYMOOR_WORLD_FACTS", "seed_world_lore_facts"]

#: The source word every builtin row carries (one batch, one word).
BUILTIN_LORE_SOURCE = "builtin-lore-v1"

#: Maya's persona (the persona fixture's default — elc.persona.types).
MAYA_PERSONA_ID = "persona-maya"

#: The penpal's persona (migration 0019's seeded card row).
NELL_PERSONA_ID = "persona-nell-alder"


def _fact(
    canonical_key: str,
    kind: WorldLoreFactKind,
    statement: str,
    *,
    persona_id: str | None = None,
) -> WorldLoreFactRow:
    """One builtin row: scope and id derive from the persona argument."""

    return WorldLoreFactRow(
        world_lore_fact_id=f"wlf-{canonical_key}",
        scope="character" if persona_id is not None else "world",
        persona_id=persona_id,
        fact_kind=kind,
        canonical_key=canonical_key,
        statement=statement,
        source=BUILTIN_LORE_SOURCE,
    )


#: The shipped batch — nine world facts (the Berrymoor setting) and three
#: character facts (Maya's coffee shop, Nell's Sunday walk).
BERRYMOOR_WORLD_FACTS: tuple[WorldLoreFactRow, ...] = (
    # -- the two keys the penpal's lore_refs name ------------------------
    _fact(
        "lore-berrymoor-harbour",
        WorldLoreFactKind.PLACE,
        "Berrymoor is a small harbour town on a cold coast; the harbour"
        " path runs from the stone quay to the bindery steps, and the"
        " fishing boats come in with the morning tide.",
    ),
    _fact(
        "lore-bindery-green-door",
        WorldLoreFactKind.PLACE,
        "Nell's bindery sits by the water behind a green door that sticks"
        " in damp weather; the faded sign reads Alder & Son, though no"
        " Alder senior has walked the floor in years.",
    ),
    # -- the world the card row annotates --------------------------------
    _fact(
        "lore-bindery-workbench",
        WorldLoreFactKind.PLACE,
        "The bindery workbench under the north window still carries her"
        " grandfather's tool marks; his burnisher lives in the same drawer"
        " Nell opens first every morning.",
    ),
    _fact(
        "lore-berrymoor-market",
        WorldLoreFactKind.SCENE,
        "Saturday market on the quay: fish carts at dawn, wool and bread"
        " by mid-morning, and half the town seems to pass the green door"
        " on the way home.",
    ),
    _fact(
        "lore-city-kerrow",
        WorldLoreFactKind.PLACE,
        "The nearest city to Berrymoor is Kerrow, two hours down the coast"
        " road; the mail coach leaves the marketplace on Tuesdays and"
        " Fridays.",
    ),
    _fact(
        "lore-borrowed-day",
        WorldLoreFactKind.RULE,
        "Rain arrives sideways off the water in Berrymoor; locals call a"
        " fine morning a borrowed day and do not trust it past noon.",
    ),
    _fact(
        "lore-old-tam",
        WorldLoreFactKind.NPC,
        "Old Tam runs the fish counter at the Saturday market and saves a"
        " piece of mackerel for whoever mends his nets; he has never once"
        " said thank you in words.",
    ),
    _fact(
        "lore-mrs-fenwick",
        WorldLoreFactKind.NPC,
        "Mrs. Fenwick keeps the post office by the marketplace and reads"
        " the postmarks before she hands a letter over; overseas stamps"
        " take a fortnight, and she says so.",
    ),
    _fact(
        "lore-tuesday-coach",
        WorldLoreFactKind.RULE,
        "Letters to far-away places leave Berrymoor on the Tuesday coach;"
        " a reply takes at least a month, and everyone writes as if the"
        " distance were ordinary, because it is.",
    ),
    # -- the two keys the persona fixture's lore_refs name (character) ----
    _fact(
        "lore-shop-menu",
        WorldLoreFactKind.SCENE,
        "The coffee shop chalkboard: drip coffee, an oat-milk latte, and a"
        " cardamom bun that sells out before ten; the regulars just say"
        " the usual, and Maya knows what that means.",
        persona_id=MAYA_PERSONA_ID,
    ),
    _fact(
        "lore-city-seattle",
        WorldLoreFactKind.PLACE,
        "Maya's coffee shop sits on a Seattle side street where the morning"
        " light comes in grey off the water, and the ferry horns carry all"
        " the way up the hill.",
        persona_id=MAYA_PERSONA_ID,
    ),
    # -- Nell's own habit (character scope, the owner-only proof) ---------
    _fact(
        "lore-harbour-path-sundays",
        WorldLoreFactKind.SCENE,
        "On Sunday mornings Nell walks the harbour path from her green"
        " door to the quay and back before she opens the shop; the"
        " regulars nod and nobody expects her to stop.",
        persona_id=NELL_PERSONA_ID,
    ),
)


def seed_world_lore_facts(store: SqliteWorldLoreStore) -> None:
    """Seed the builtin batch into the store, idempotently.

    Every append is ``INSERT OR IGNORE`` by primary key, so an open re-seed
    is a no-op; a real write failure raises :class:`WorldLoreStoreError` so
    the composition root's open fails loudly instead of serving a half-seeded
    world (the fail-closed assembly posture).
    """

    for fact in BERRYMOOR_WORLD_FACTS:
        result = store.add_fact(fact)
        if isinstance(result, Err):
            raise WorldLoreStoreError(
                f"builtin lore seed failed at {fact.canonical_key}:"
                f" {result.error.message}"
            )
