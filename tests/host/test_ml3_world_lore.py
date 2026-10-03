"""主线-3 — the world_lore domain implementation's pins (VAL five groups).

The gap this cut closes: World/Lore was a canonical domain on paper only —
two Protocols, the Phase 0 type shapes and a red-line skeleton; the view
Persona consumes was hard-coded ``None`` at both GenerationContext sites and
the prompt compiler had no carrier for lore text at all. After it: migration
0020's ``world_lore_fact`` table, the durable store, the graduated
controller, the builtin world batch, the coordinator's resolution port and
the compiler's framed ``[lore]`` section — the penpal knows her own town.

Five groups (the slice's own, VAL-OPI-32409938-…38):

1. **migration pins** — 0020 is the registered head, the ``world_lore_fact``
   table carries its column set with the scope/kind/status CHECKs and the
   scope-persona pairing, and the stamps say 20;
2. **store pins** — real rows in and out through the real store: the
   canonical shape comes back verbatim, the scope semantics answer (world is
   common, character answers only its owner, an unbound conversation gets
   the common world), the durable order is content, append is idempotent by
   id, PENDING rows reach no view, and the shape refusals are answers;
3. **injection E2E** — the prompt boundary: Nell's conversation compiles her
   world (the framed ``[lore]`` section with her two ``lore_refs`` keys'
   facts and her own Sunday row), Maya's gets only hers, an unbound
   conversation gets the common world, an unknown one is a NOT_FOUND
   answer, and the port-less assembly (every assembly before this cut) still
   compiles lore-less;
4. **content + census pins** — the shipped batch is twelve rows (nine world,
   three character), the seed re-runs into a no-op, every shipped card's
   ``lore_refs`` key resolves, the census row is the live face (and imports),
   and the graduated controller's one remaining refusal keeps its pointer;
5. **mutation-catcher pins** — the three structural facts the VAL's mutation
   arms attack: the coordinator really holds the resolution port (cut the
   host wiring → group 3's prompt pins go red), the host really exposes the
   controller over a seeded store, and the census row names the live face.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from elc.conversation.types import CommitUserTurn
from elc.host import open_host
from elc.persona.penpal import PENPAL_PERSONA_ID
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    PersonaId,
    WorldLoreFactId,
)
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.world_lore.content import (
    BERRYMOOR_WORLD_FACTS,
    seed_world_lore_facts,
)
from elc.world_lore.controller import WorldLoreController
from elc.world_lore.store import SqliteWorldLoreStore, WorldLoreFactRow
from elc.world_lore.types import (
    WorldLoreFactKind,
    WorldLoreProposal,
    WorldLoreRecord,
    WorldLoreView,
)
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.host.test_cs1_character_activation import RecordingProvider

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO_ROOT / "migrations"

REPLY = "The harbour is quiet tonight — what does your evening look like?"

MAYA_PERSONA = PersonaId("persona-maya")


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> SqliteWorldLoreStore:
    """The lore store over a fresh, fully migrated app.db."""

    conn = sqlite3.connect(tmp_path / "app.db")
    apply_migrations(conn)
    fence = open_runtime_epoch(conn)
    return SqliteWorldLoreStore(conn, fence)


def _fact(
    fact_id: str,
    key: str,
    kind: WorldLoreFactKind = WorldLoreFactKind.PLACE,
    *,
    persona_id: str | None = None,
    statement: str = "a fact",
    status: str = "ACTIVE",
) -> WorldLoreFactRow:
    return WorldLoreFactRow(
        world_lore_fact_id=fact_id,
        scope="character" if persona_id is not None else "world",
        persona_id=persona_id,
        fact_kind=kind,
        canonical_key=key,
        statement=statement,
        source="test-lore-v1",
        status=status,
    )


def _command(text: str, conversation: str, suffix: str) -> CommitUserTurn:
    message = f"ml3-{suffix}"
    return CommitUserTurn(
        conversation_id=ConversationId(conversation),
        envelope=InputEnvelope(
            input_id=InputId(message),
            client_message_id=ClientMessageId(message),
            conversation_id=conversation,
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-ml3",
    )


# ---------------------------------------------------------------------------
# 1 — the migration
# ---------------------------------------------------------------------------


def test_0020_is_the_registered_head() -> None:
    """The lineage ends at 主线-3's migration (the task book's ``0019`` name
    was written before MC-0's 0019_character_cards took the number — the
    head bump is the requirement, the number moved with it), the shared
    constants say so, and the stamp a fresh database carries is 20."""

    assert MIGRATION_IDS[-1] == "0020_world_lore_facts"
    assert SCHEMA_HEAD_FILE == "0020_world_lore_facts.sql"
    assert (MIGRATIONS / SCHEMA_HEAD_FILE).is_file()
    assert SCHEMA_HEAD_VERSION == "20"
    assert "0019_character_cards" in MIGRATION_IDS

    conn = sqlite3.connect(":memory:")
    applied = apply_migrations(conn)
    assert applied[-1] == "0020_world_lore_facts"
    assert schema_version(conn) == "20"


def test_the_world_lore_fact_table_carries_its_columns() -> None:
    """The physical column set, in order — the Phase 0 shapes' columns
    (``world_lore_fact_id`` / ``fact_kind`` / ``canonical_key`` /
    ``statement``, from WorldLoreRecord) plus the adjudication's
    (``scope`` / ``persona_id`` scope key / ``source`` / ``status`` /
    ``write_epoch``) and the house clock stamp."""

    conn = sqlite3.connect(":memory:")
    apply_migrations(conn)
    columns = [str(row[1]) for row in conn.execute(
        "PRAGMA table_info(world_lore_fact)"
    ).fetchall()]
    assert columns == [
        "world_lore_fact_id",
        "scope",
        "persona_id",
        "fact_kind",
        "canonical_key",
        "statement",
        "source",
        "status",
        "write_epoch",
        "created_at",
    ]
    check = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'world_lore_fact'"
    ).fetchone()[0]
    assert "CHECK (scope IN ('world', 'character'))" in str(check)
    assert "CHECK (fact_kind IN ('SCENE', 'NPC', 'PLACE', 'RULE'))" in str(
        check
    )
    assert "CHECK (status IN ('ACTIVE', 'PENDING'))" in str(check)
    assert "scope = 'character' AND persona_id IS NOT NULL" in str(check)
    index = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
        " AND name = 'idx_world_lore_fact_view'"
    ).fetchone()
    assert index is not None


# ---------------------------------------------------------------------------
# 2 — the store
# ---------------------------------------------------------------------------


def test_the_store_round_trips_the_canonical_shape(
    store: SqliteWorldLoreStore,
) -> None:
    """A fact in, the canonical Phase 0 record out — the four fields the
    consumers read, and none of the storage bookkeeping."""

    written = store.add_fact(
        _fact("wlf-test-harbour", "lore-test-harbour",
              WorldLoreFactKind.PLACE, statement="a cold harbour")
    )
    assert isinstance(written, Ok), written

    read = store.get_fact(WorldLoreFactId("wlf-test-harbour"))
    assert isinstance(read, Ok), read
    assert read.value == WorldLoreRecord(
        world_lore_fact_id=WorldLoreFactId("wlf-test-harbour"),
        fact_kind=WorldLoreFactKind.PLACE,
        canonical_key="lore-test-harbour",
        statement="a cold harbour",
    )
    unknown = store.get_fact(WorldLoreFactId("wlf-nothing"))
    assert isinstance(unknown, Ok) and unknown.value is None


def test_the_scope_semantics_answer_the_view(
    store: SqliteWorldLoreStore,
) -> None:
    """The adjudication's two scopes: a world fact is common (every persona
    and the unbound shape see it), a character fact answers only its owner,
    and the durable order (``canonical_key`` ascending, id as tiebreak) is
    the order the view carries."""

    assert isinstance(store.add_fact(
        _fact("wlf-a", "lore-a-weather", statement="rain off the water")
    ), Ok)
    assert isinstance(store.add_fact(
        _fact("wlf-b", "lore-b-quay", statement="the stone quay")
    ), Ok)
    assert isinstance(store.add_fact(
        _fact("wlf-c", "lore-a-quay-side", statement="her bench",
              persona_id="persona-nell-alder")
    ), Ok)

    world_keys = [r.canonical_key for r in store.facts_for_view(None)]
    assert world_keys == ["lore-a-weather", "lore-b-quay"]

    nell_keys = [r.canonical_key for r in
                 store.facts_for_view("persona-nell-alder")]
    assert nell_keys == ["lore-a-quay-side", "lore-a-weather", "lore-b-quay"]

    other_keys = [r.canonical_key for r in
                  store.facts_for_view("persona-someone-else")]
    assert other_keys == ["lore-a-weather", "lore-b-quay"]


def test_the_append_is_idempotent_by_id(
    store: SqliteWorldLoreStore,
) -> None:
    """The seed re-runs every open: a repeated id is a silent no-op, and the
    row's first content wins."""

    fact = _fact("wlf-idem", "lore-idem", statement="first wording")
    assert isinstance(store.add_fact(fact), Ok)
    again = WorldLoreFactRow(**{**fact.__dict__, "statement": "second wording"})
    assert isinstance(store.add_fact(again), Ok)
    rows = store.facts_for_view(None)
    assert [r.statement for r in rows] == ["first wording"]


def test_pending_rows_reach_no_view(store: SqliteWorldLoreStore) -> None:
    """P-INV-013, durable form: a proposal lands, is readable by id, and no
    view ever serves it until an approval face flips its status."""

    assert isinstance(store.add_fact(
        _fact("wlf-prop", "lore-prop",
              WorldLoreFactKind.RULE, statement="a proposed rule",
              status="PENDING")
    ), Ok)
    assert store.facts_for_view(None) == ()
    assert store.count() == 0
    assert store.count(status="PENDING") == 1
    read = store.get_fact(WorldLoreFactId("wlf-prop"))
    assert isinstance(read, Ok) and read.value is not None


def test_the_store_refuses_the_bad_shapes(
    store: SqliteWorldLoreStore,
) -> None:
    """A world fact with a persona, a character fact without one, an unknown
    scope and an unknown status are VALIDATION_FAILED answers — never a
    guessed row."""

    smuggled = WorldLoreFactRow(
        world_lore_fact_id="wlf-x1", scope="world", persona_id="persona-x",
        fact_kind=WorldLoreFactKind.PLACE, canonical_key="k", statement="s",
        source="t",
    )
    refused = store.add_fact(smuggled)
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"

    orphan = WorldLoreFactRow(
        world_lore_fact_id="wlf-x2", scope="character", persona_id=None,
        fact_kind=WorldLoreFactKind.PLACE, canonical_key="k", statement="s",
        source="t",
    )
    refused = store.add_fact(orphan)
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"

    alien = WorldLoreFactRow(
        world_lore_fact_id="wlf-x3", scope="scene", persona_id=None,
        fact_kind=WorldLoreFactKind.PLACE, canonical_key="k", statement="s",
        source="t",
    )
    refused = store.add_fact(alien)
    assert isinstance(refused, Err)

    limbo = _fact("wlf-x4", "k", status="DRAFT")
    refused = store.add_fact(limbo)
    assert isinstance(refused, Err)
    assert store.count() == 0


# ---------------------------------------------------------------------------
# 3 — the injection E2E (the prompt boundary)
# ---------------------------------------------------------------------------


def _world(
    tmp_path: Path, conversation: str, persona_id: PersonaId | None
):
    """A prep-1-tier host (the lore leg is both tiers) with a recording
    provider; the conversation opened and, when a persona is given, bound."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(tmp_path / "app.db", provider=provider)
    opened = host.open_conversation(
        ConversationId(conversation), persona_id=persona_id
    )
    assert isinstance(opened, Ok), opened
    return host, provider


def _turn(host, conversation: str, suffix: str) -> str:
    result = host.coordinator.begin_turn(
        _command("你好。", conversation, suffix)
    )
    assert isinstance(result, Ok), result
    assert result.value.turn_status is TurnStatus.COMPLETED
    return result.value.reply_text  # type: ignore[union-attr]


def test_nells_prompt_carries_her_world(tmp_path: Path) -> None:
    """The E2E the domain existed for: a conversation bound to the penpal's
    persona compiles the framed ``[lore]`` section with her two
    ``lore_refs`` keys' facts and her own Sunday row — the penpal knows her
    town."""

    host, provider = _world(tmp_path, "ml3-nell", PENPAL_PERSONA_ID)
    _turn(host, "ml3-nell", "nell")
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]

    assert "[lore]" in prompt.splitlines()
    assert "prompt_version: lore-prompt-v1" in prompt
    assert (
        "PLACE lore-berrymoor-harbour: Berrymoor is a small harbour town"
        in prompt
    )
    assert "PLACE lore-bindery-green-door:" in prompt
    assert "On Sunday mornings Nell walks the harbour path" in prompt
    # the section renders inside the untrusted frame (BF-05 "lore·world
    # text"): the facts line sits between the lore frame's markers.
    begin = [
        line for line in prompt.splitlines()
        if line.startswith("<<untrusted-section") and '"lore"' in line
    ]
    assert len(begin) == 1
    # the framed facts line is escaped single-line text: no fact statement
    # can start a line of its own.
    assert "\nBerrymoor is a small harbour town" not in prompt
    host.close()


def test_a_character_fact_stays_with_its_owner(tmp_path: Path) -> None:
    """Maya's conversation resolves Maya's world — her two keys, never the
    penpal's Sunday row; the isolation is the scope column answering."""

    host, provider = _world(tmp_path, "ml3-maya", MAYA_PERSONA)
    _turn(host, "ml3-maya", "maya")
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]

    assert "SCENE lore-shop-menu:" in prompt
    assert "PLACE lore-city-seattle:" in prompt
    assert "On Sunday mornings Nell walks the harbour path" not in prompt
    host.close()


def test_an_unbound_conversation_gets_the_common_world(
    tmp_path: Path,
) -> None:
    """No persona binding → the common world only (world facts, no
    character facts) — the honest default, not a guess."""

    host, provider = _world(tmp_path, "ml3-open", None)
    _turn(host, "ml3-open", "open")
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]

    assert "PLACE lore-berrymoor-harbour:" in prompt
    assert "lore-shop-menu" not in prompt
    assert "lore-harbour-path-sundays" not in prompt
    host.close()


def test_an_unknown_conversation_is_a_not_found_answer(
    tmp_path: Path,
) -> None:
    """The controller never invents a world: a conversation the store has
    never heard of is a NOT_FOUND answer (and the coordinator's guard keeps
    it from ever reaching a prompt)."""

    host, _provider = _world(tmp_path, "ml3-real", None)
    resolved = host.world_lore.resolve_world_lore_view(
        ConversationId("ml3-never-opened")
    )
    assert isinstance(resolved, Err)
    assert resolved.error.code.value == "NOT_FOUND"
    host.close()


# ---------------------------------------------------------------------------
# 4 — the content batch + the census row
# ---------------------------------------------------------------------------


def test_the_builtin_batch_is_the_declared_world(
    tmp_path: Path,
) -> None:
    """Twelve rows (nine world, three character), the seed re-runs into a
    no-op, and every shipped card's ``lore_refs`` key resolves in its
    owner's view."""

    conn = sqlite3.connect(tmp_path / "app.db")
    apply_migrations(conn)
    fence = open_runtime_epoch(conn)
    store = SqliteWorldLoreStore(conn, fence)
    seed_world_lore_facts(store)
    assert store.count() == 12
    seed_world_lore_facts(store)
    assert store.count() == 12

    nell_keys = {
        r.canonical_key for r in store.facts_for_view(str(PENPAL_PERSONA_ID))
    }
    assert {"lore-berrymoor-harbour", "lore-bindery-green-door"} <= nell_keys
    assert "lore-harbour-path-sundays" in nell_keys
    maya_keys = {
        r.canonical_key for r in store.facts_for_view("persona-maya")
    }
    assert {"lore-shop-menu", "lore-city-seattle"} <= maya_keys
    # the batch declared: nine world rows and three character rows.
    world_keys = {r.canonical_key for r in store.facts_for_view(None)}
    assert len(world_keys) == 9
    conn.close()


def test_the_batch_module_declares_twelve_rows() -> None:
    """The content module's own tuple: twelve fact rows, ids derived from
    the canonical keys, every source word the builtin's."""

    assert len(BERRYMOOR_WORLD_FACTS) == 12
    for fact in BERRYMOOR_WORLD_FACTS:
        assert fact.world_lore_fact_id == f"wlf-{fact.canonical_key}"
        assert fact.status == "ACTIVE"
        assert (
            (fact.scope == "character") == (fact.persona_id is not None)
        )


def test_the_census_row_is_the_live_face() -> None:
    """The census row activated (its own Revisit honoured): the live face
    and the store are named, importable, and the no-live-face reason is
    gone."""

    from tests.architecture.test_surface_census import SURFACE_CENSUS

    row = next(r for r in SURFACE_CENSUS if r.package == "world_lore")
    assert row.live_face == "elc.world_lore.controller:WorldLoreController"
    assert row.store == "elc.world_lore.store:SqliteWorldLoreStore"
    assert row.no_live_face_because is None
    assert row.skeletons == ()
    # the named faces import (the census pin re-proves it here so a
    # regression in the row is red from this suite too).
    module_name, _, attr = row.live_face.partition(":")
    import importlib

    assert getattr(importlib.import_module(module_name), attr) is not None


# ---------------------------------------------------------------------------
# 5 — the mutation catchers (the structural facts the arms attack)
# ---------------------------------------------------------------------------


def test_the_controller_graduated_with_one_pointer_kept(
    store: SqliteWorldLoreStore,
    tmp_path: Path,
) -> None:
    """The graduated class's behavioural shape: a proposal lands PENDING and
    view-invisible, the read answers, and supersede keeps its registered
    pointer (the planner-suite mechanism — the allowlist exempts the class,
    the refusals are pinned here)."""

    conn = sqlite3.connect(tmp_path / "app2.db")
    apply_migrations(conn)
    from elc.conversation.store import SqliteConversationStore

    conversations = SqliteConversationStore(conn, open_runtime_epoch(conn))
    controller = WorldLoreController(store, conversations)

    proposed = controller.propose_lore_fact(
        WorldLoreProposal(
            fact_kind=WorldLoreFactKind.RULE,
            canonical_key="lore-proposed",
            statement="a proposed rule",
            source="user free text — never a write authority",
        )
    )
    assert isinstance(proposed, Ok), proposed
    assert store.facts_for_view(None) == ()
    assert store.count(status="PENDING") == 1

    with pytest.raises(NotImplementedError, match="append-first supersede"):
        controller.supersede_lore_fact(
            WorldLoreFactId("wlf-nothing"),
            WorldLoreRecord(
                world_lore_fact_id=WorldLoreFactId("wlf-nothing"),
                fact_kind=WorldLoreFactKind.PLACE,
                canonical_key="k",
                statement="s",
            ),
        )


def test_the_coordinator_holds_the_resolution_port(tmp_path: Path) -> None:
    """Mutation arm 1's catcher: the host wires the controller into the
    coordinator (cut the wiring and group 3's prompt pins go red from the
    missing section)."""

    host, _provider = _world(tmp_path, "ml3-port", PENPAL_PERSONA_ID)
    assert host.coordinator._world_lore is host.world_lore
    host.close()


def test_the_host_exposes_the_controller_over_a_seeded_store(
    tmp_path: Path,
) -> None:
    """Mutation arm 2's catcher: the host field is the controller over a
    real store whose builtin batch is present (drop the table or the seed
    and the count pin — and every read — goes red)."""

    host, _provider = _world(tmp_path, "ml3-host", PENPAL_PERSONA_ID)
    assert isinstance(host.world_lore, WorldLoreController)
    assert host.world_lore._world_lore.count() == 12
    resolved = host.world_lore.resolve_world_lore_view(
        ConversationId("ml3-host")
    )
    assert isinstance(resolved, Ok)
    view = resolved.value
    assert isinstance(view, WorldLoreView)
    keys = {r.canonical_key for r in view.facts}
    assert "lore-berrymoor-harbour" in keys
    host.close()


def test_a_portless_assembly_still_compiles_lore_less(tmp_path: Path) -> None:
    """The backward half: a coordinator assembled without the port (every
    assembly before this cut, and any that opts out) answers ``None`` — no
    section, byte-identical prompt to the pre-主线-3 shape."""

    provider = ScriptedPersonaProvider(
        script=(ProviderOutput(text=REPLY),)
    )
    host = open_host(tmp_path / "app.db", provider=provider)
    bare = host.coordinator._world_lore_view_for(ConversationId("ml3-bare"))
    assert bare is None
    host.close()
