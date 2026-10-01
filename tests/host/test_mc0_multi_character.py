"""MC-0 — the multi-character ground cut's pins (后端地基刀).

The world before this cut had one production character: the fixed penpal,
held as constants, injected by the composition root. MC-0 (the user's call,
the DEC-OPI-a31b14c9…43 adjudication) opens that up: **the user authors
their own character cards, and can author many**; every character is one
communication line (its own conversation, its own persona, its own
isolated memory); switching characters switches the envelope.

Eight groups (the slice's own):

1. **migration pins** — 0019 is the registered head, the ``character_card``
   table carries its column set, and the stamps say 19;
2. **seed pins** — the builtin row is the penpal, field for field from
   ``penpal_character_package()`` (the migration is pure SQL, so this pin
   is what holds the copy honest);
3. **store CRUD pins** — create / list / update / delete through the real
   store, the builtin editable and never deletable, the shape refusals
   (name required, foreign field refused, unknown id), and the stamp key
   deterministic and rename-stable;
4. **mapping + switch pins, over live HTTP** — the roster, the create, the
   envelope switch (lazily building the character's own conversation bound
   to its persona), the parameterized dossier, and the isolation proof:
   two characters, two real correspondences through the real producer, and
   each dossier reads only its own memory;
5. **HTTP refusal pins** — the builtin 409 on delete, the grammar 400s,
   the unknown-id 404s, and the stamp key surviving a rename;
6. **assembly pins** — "table first, penpal fallback" at the prompt
   boundary: a user card reaches the provider's eyes, an edited table card
   overrides the constant, a persona without a card falls back to the
   injected default, and ``character_package=None`` stays bare (the
   prep-1 shape survives MC-0 untouched);
7. **backward-compatibility pins** — the conversation mapping keeps
   ``web-default`` for the penpal and derives ``web-<character_id>`` for
   everyone else, and ``cli-default`` is not the web face's;
8. **deletion pins** — the BF-05 sweep walks the user's cards and never
   the builtin (the store's ``is_builtin = 0`` leg, the same authority
   rule the delete face enforces).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import build_content_db
from elc.conversation.types import CommitUserTurn
from elc.deletion.controller import DeletionController
from elc.deletion.store import SqliteDeletionStore
from elc.deletion.types import DeletionRequest, DeletionScope
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import open_host
from elc.persona.card_store import (
    CharacterCardRecord,
    SqliteCharacterCardStore,
    card_to_package,
    persona_id_for_card,
    stamp_key_for,
)
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE,
    PENPAL_CHARACTER_PACKAGE_ID,
    PENPAL_PERSONA_ID,
    penpal_character_package,
)
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
)
from elc.runtime.types import InputEnvelope, TurnStatus
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.host.test_cs1_character_activation import RecordingProvider
from tests.host.test_w1_web import web_stack

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO_ROOT / "migrations"

REPLY = "Understood — the kettle is on and I am listening."
CONV = "web-test"

NELL_ID = str(PENPAL_CHARACTER_PACKAGE_ID)
NELL_PERSONA = str(PENPAL_PERSONA_ID)

#: A user-authored card used across the groups — a retired ferryman, the
#: kind of second character the adjudication imagines.
FERRYMAN_FIELDS = {
    "name": "Old Zhou",
    "identity": "a retired ferryman who still mends nets at dawn",
    "personality": "gruff but kind; few words, well chosen",
    "background": "forty years on the river; now the dock and its nets",
    "speech_style": "short sentences; river metaphors; signs off as — Zhou",
    "values": "honesty, hard work, keeping the mooring rope coiled",
    "boundaries": "never talks about the storm of five years ago",
    "opening": "Morning. Tide turned an hour ago — what brings you here?",
    "scenario": "the ferry dock at first light, mist on the water",
}


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One built content artifact for the module (the cs-1 shape — the
    relationship projections need the full chain to run for real)."""

    path = tmp_path_factory.mktemp("mc0-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


@pytest.fixture()
def cards(tmp_path: Path) -> SqliteCharacterCardStore:
    """The card store over a fresh, fully migrated app.db."""

    conn = sqlite3.connect(tmp_path / "app.db")
    apply_migrations(conn)
    fence = open_runtime_epoch(conn)
    return SqliteCharacterCardStore(conn, fence)


def _user_record(cards: SqliteCharacterCardStore) -> CharacterCardRecord:
    """A minted user card from :data:`FERRYMAN_FIELDS` (not yet inserted)."""

    character_id = cards.mint_user_card_id()
    now = datetime.now(tz=UTC).isoformat()
    return CharacterCardRecord(
        character_id=character_id,
        persona_id=persona_id_for_card(character_id),
        name=FERRYMAN_FIELDS["name"],
        identity=FERRYMAN_FIELDS["identity"],
        personality=FERRYMAN_FIELDS["personality"],
        background=FERRYMAN_FIELDS["background"],
        speech_style=FERRYMAN_FIELDS["speech_style"],
        values=FERRYMAN_FIELDS["values"],
        boundaries=FERRYMAN_FIELDS["boundaries"],
        opening=FERRYMAN_FIELDS["opening"],
        scenario=FERRYMAN_FIELDS["scenario"],
        generation_policy=PENPAL_CHARACTER_PACKAGE.generation_policy,
        lore_refs=(),
        revision=1,
        status=PENPAL_CHARACTER_PACKAGE.status,
        is_builtin=False,
        created_at=now,
        updated_at=now,
    )


def _command(text: str, conversation: str, suffix: str) -> CommitUserTurn:
    message = f"mc0-{suffix}"
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
        runtime_version="runtime-mc0",
    )


def _get_json(port: int, path: str) -> tuple[int, Any]:
    """A GET that decodes error answers too (the roster's unknown-id 404
    is a pinned shape, not an exception — test_w1's own ``_get_json``
    lets HTTPError raise, which is right for its pins, wrong for these)."""

    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _put_json(
    port: int, path: str, payload: Any
) -> tuple[int, Any]:
    """The roster's reword face — PUT with a JSON body, errors decoded."""

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _delete_json(port: int, path: str) -> tuple[int, Any]:
    """The roster's remove face — DELETE, errors decoded."""

    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method="DELETE"
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 1 + 2 — the migration, the table, the seed
# ---------------------------------------------------------------------------


def test_0019_is_the_registered_head() -> None:
    """The lineage ends at MC-0's migration, the shared constants say so,
    and the stamp a fresh database carries is 19."""

    assert MIGRATION_IDS[-1] == "0019_character_cards"
    assert SCHEMA_HEAD_FILE == "0019_character_cards.sql"
    assert (MIGRATIONS / SCHEMA_HEAD_FILE).is_file()
    assert SCHEMA_HEAD_VERSION == "19"

    conn = sqlite3.connect(":memory:")
    applied = apply_migrations(conn)
    assert applied[-1] == "0019_character_cards"
    assert schema_version(conn) == "19"


def test_the_character_card_table_carries_its_columns() -> None:
    """The physical column set, in order — the canonical CharacterPackage
    column set plus ``name`` (a user names a card directly) and
    ``is_builtin`` (the seeded penpal vs. user-authored), no portrait
    column (explicitly out of this cut's scope)."""

    conn = sqlite3.connect(":memory:")
    apply_migrations(conn)
    columns = [
        (str(row[1]), str(row[2]).upper(), int(row[3]))
        for row in conn.execute("PRAGMA table_info(character_card)").fetchall()
    ]
    assert [name for name, _, _ in columns] == [
        "character_id",
        "persona_id",
        "name",
        "identity",
        "personality",
        "background",
        "speech_style",
        "values",
        "boundaries",
        "opening",
        "scenario",
        "generation_policy",
        "lore_refs",
        "revision",
        "status",
        "is_builtin",
        "created_at",
        "updated_at",
    ]
    # The prose columns are NOT NULL (a not-yet-written field is the empty
    # string, never a second spelling of "not written"), and the builtin
    # bit carries its 0/1 CHECK.
    by_name = dict((name, (kind, notnull)) for name, kind, notnull in columns)
    for prose in (
        "identity",
        "personality",
        "background",
        "speech_style",
        "values",
        "boundaries",
        "opening",
        "scenario",
    ):
        assert by_name[prose] == ("TEXT", 1), prose
    check = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'character_card'"
    ).fetchone()[0]
    assert "CHECK (is_builtin IN (0, 1))" in str(check)


def test_the_seeded_row_is_the_penpal_field_for_field(
    cards: SqliteCharacterCardStore,
) -> None:
    """The migration is pure SQL — the seed values are a copy — and this
    pin is what holds the copy honest: every canonical field of the table
    row equals ``penpal_character_package()``'s, the builtin bit is set,
    and the lifecycle stamp is her fixed one."""

    read = cards.get(NELL_ID)
    assert isinstance(read, Ok), read
    record = read.value
    assert record.is_builtin is True
    assert record.name == "Nell Alder"
    assert record.created_at == record.updated_at
    package = card_to_package(record)
    expected = penpal_character_package()
    for field in (
        "character_package_id",
        "persona_id",
        "revision",
        "identity",
        "personality",
        "background",
        "speech_style",
        "values",
        "boundaries",
        "opening",
        "scenario",
        "generation_policy",
        "lore_refs",
        "status",
        "updated_at",
    ):
        assert getattr(package, field) == getattr(expected, field), field


# ---------------------------------------------------------------------------
# 3 — the store CRUD
# ---------------------------------------------------------------------------


def test_the_store_crud_round_trip(
    cards: SqliteCharacterCardStore,
) -> None:
    """Create, list, update, delete — the real store, real rows. The list
    order is builtin first, then by id (one deterministic order), the
    update bumps revision and re-stamps, and the delete removes."""

    record = _user_record(cards)
    created = cards.create(record)
    assert isinstance(created, Ok), created

    listed = cards.list_all()
    assert isinstance(listed, Ok), listed
    ids = [item.character_id for item in listed.value]
    assert ids[0] == NELL_ID  # builtin first
    assert record.character_id in ids

    updated = cards.update(
        record.character_id,
        {"name": "周师傅", "background": "forty years, then the nets"},
    )
    assert isinstance(updated, Ok), updated
    assert updated.value.name == "周师傅"
    assert updated.value.revision == 2
    assert updated.value.updated_at >= record.updated_at
    assert updated.value.persona_id == record.persona_id  # identity immovable

    deleted = cards.delete(record.character_id)
    assert isinstance(deleted, Ok), deleted
    again = cards.delete(record.character_id)
    assert isinstance(again, Err), again
    assert again.error.code.value == "NOT_FOUND"


def test_the_builtin_is_editable_and_never_deletable(
    cards: SqliteCharacterCardStore,
) -> None:
    """The adjudication's ruling, both halves: Nell can be reworded (there
    is exactly one of her, and her keeper may shape the words), and no
    delete reaches her — the store answers AUTHORITY_VIOLATION, and she is
    still on the roster afterwards."""

    updated = cards.update(
        NELL_ID, {"personality": "unhurried and warm; still quietly funny"}
    )
    assert isinstance(updated, Ok), updated
    assert updated.value.revision == 2
    assert updated.value.is_builtin is True

    refused = cards.delete(NELL_ID)
    assert isinstance(refused, Err), refused
    assert refused.error.code.value == "AUTHORITY_VIOLATION"

    listed = cards.list_all()
    assert isinstance(listed, Ok), listed
    assert NELL_ID in [item.character_id for item in listed.value]


def test_the_store_refuses_the_bad_shapes(
    cards: SqliteCharacterCardStore,
) -> None:
    """A card without a name is a blank stamp; a foreign field in an
    update is a sneaked identity change; a duplicate id is a naming
    decision the store surfaces as CONFLICT."""

    record = _user_record(cards)
    record = CharacterCardRecord(**{**record.__dict__, "name": "   "})
    blank = cards.create(record)
    assert isinstance(blank, Err), blank
    assert blank.error.code.value == "VALIDATION_FAILED"

    named = _user_record(cards)
    assert isinstance(cards.create(named), Ok), cards.create
    duplicate = cards.create(named)
    assert isinstance(duplicate, Err), duplicate
    assert duplicate.error.code.value == "CONFLICT"

    foreign = cards.update(
        named.character_id, {"persona_id": "persona-sneaked"}
    )
    assert isinstance(foreign, Err), foreign
    assert foreign.error.code.value == "VALIDATION_FAILED"

    unknown = cards.update("card-nothing", {"name": "x"})
    assert isinstance(unknown, Err), unknown
    assert unknown.error.code.value == "NOT_FOUND"


def test_the_stamp_key_is_deterministic_and_rename_stable(
    cards: SqliteCharacterCardStore,
) -> None:
    """The stamp key is a pure function of the id: the same id yields the
    same key (call to call, process to process), a different id yields a
    different one, and **a rename does not move it** — the stamp is who
    the character is, not what they are called this week."""

    assert stamp_key_for("card-abc") == stamp_key_for("card-abc")
    assert stamp_key_for("card-abc") != stamp_key_for("card-xyz")
    assert stamp_key_for(NELL_ID) == stamp_key_for(NELL_ID)

    record = _user_record(cards)
    assert isinstance(cards.create(record), Ok), cards.create
    before = stamp_key_for(record.character_id)
    updated = cards.update(record.character_id, {"name": "改了名字"})
    assert isinstance(updated, Ok), updated
    assert stamp_key_for(record.character_id) == before


# ---------------------------------------------------------------------------
# 4 + 5 — the roster, the switch, the parameterized dossier (live HTTP)
# ---------------------------------------------------------------------------


def _memories_text(payload: dict) -> str:
    """The dossier's memory texts, joined (the isolation asserts read this
    — a memory present for one character and absent for the other)."""

    memories = payload["memories"].get("memories", [])
    return " | ".join(str(item["content"]) for item in memories)


def test_the_roster_switch_and_the_two_dossiers_are_isolated(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The full line, over live HTTP with the real producer:

    create a second character → switch to her (the switch lazily builds
    ``web-<character_id>`` and binds the card's persona) → write a real
    correspondence (the ZH fact candidate walks the pipeline and lands as
    the pair's durable memory) → switch back to Nell → write hers → and
    then each dossier reads **only its own** memory. One coordinator, two
    communication lines, two isolated (persona, user) pairs."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        # The roster at rest: the seeded penpal, builtin, with her stamp
        # key; the served conversation names no character (the tests' own
        # ``web-test`` follows neither mapping shape — the honest None).
        status, payload = _get_json(stack.port, "/api/characters")
        assert status == 200, payload
        assert [item["character_id"] for item in payload["characters"]] == [
            NELL_ID
        ]
        nell = payload["characters"][0]
        assert nell["is_builtin"] is True
        assert nell["name"] == "Nell Alder"
        assert nell["stamp_key"] == stamp_key_for(NELL_ID)
        assert payload["current_character_id"] is None

        # Create the second character.
        status, payload = stack.post("/api/characters", FERRYMAN_FIELDS)
        assert status == 200, payload
        card = payload["character"]
        ferryman_id = card["character_id"]
        assert ferryman_id.startswith("card-")
        assert card["persona_id"] == persona_id_for_card(ferryman_id)
        assert card["is_builtin"] is False
        assert card["stamp_key"] == stamp_key_for(ferryman_id)

        status, payload = _get_json(stack.port, "/api/characters")
        assert [item["character_id"] for item in payload["characters"]] == [
            NELL_ID,
            ferryman_id,
        ]  # builtin first, then the user's

        # Switch to the ferryman: the envelope is his conversation, built
        # here, bound to his persona.
        status, payload = stack.post(
            "/api/characters/switch", {"character_id": ferryman_id}
        )
        assert status == 200, payload
        assert payload["switched"] is True
        assert payload["conversation"] == f"web-{ferryman_id}"
        status, payload = _get_json(stack.port, "/api/characters")
        assert payload["current_character_id"] == ferryman_id

        status, payload = stack.post(
            "/api/turn", {"text": "你好！我叫小红，我在杭州工作。"}
        )
        assert status == 200, payload

        # His dossier: his card, his letters, his memory.
        status, payload = _get_json(
            stack.port, f"/api/partner?character_id={ferryman_id}"
        )
        assert status == 200, payload
        assert payload["card"]["name"] == "Old Zhou"
        assert payload["conversation_id"] == f"web-{ferryman_id}"
        assert payload["stats"]["turns"] == 1
        his_memory = _memories_text(payload)
        assert "小红" in his_memory

        # Switch back to Nell — her envelope is the shipped web-default.
        status, payload = stack.post(
            "/api/characters/switch", {"character_id": NELL_ID}
        )
        assert status == 200, payload
        assert payload["conversation"] == "web-default"
        status, payload = stack.post(
            "/api/turn", {"text": "你好！我叫小明，我在上海工作。"}
        )
        assert status == 200, payload

        # The no-parameter dossier is byte-compat: the penpal's card face,
        # her persona's memories — and not the ferryman's.
        status, payload = _get_json(stack.port, "/api/partner")
        assert status == 200, payload
        assert payload["card"]["name"] == "Nell Alder"
        nell_memory = _memories_text(payload)
        assert "小明" in nell_memory
        assert "小红" not in nell_memory

        # The ferryman's dossier again: only his.
        status, payload = _get_json(
            stack.port, f"/api/partner?character_id={ferryman_id}"
        )
        assert status == 200, payload
        his_memory = _memories_text(payload)
        assert "小红" in his_memory
        assert "小明" not in his_memory
        assert payload["stats"]["turns"] == 1  # his letters only

        status, payload = _get_json(stack.port,
            "/api/partner?character_id=card-nobody"
        )
        assert status == 404, payload


def test_the_switch_builds_a_persona_bound_conversation(
    tmp_path: Path,
) -> None:
    """The lazily built envelope is durable and correctly bound: after a
    switch the conversation row exists with the card's persona id — read
    through a second, read-only connection (the served host's own
    connection belongs to its thread, not to this test)."""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post("/api/characters", FERRYMAN_FIELDS)
        assert status == 200, payload
        ferryman_id = payload["character"]["character_id"]
        status, payload = stack.post(
            "/api/characters/switch", {"character_id": ferryman_id}
        )
        assert status == 200, payload

    conn = sqlite3.connect(f"file:{tmp_path / 'app.db'}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT persona_id FROM conversation WHERE conversation_id = ?",
            (f"web-{ferryman_id}",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert str(row[0]) == persona_id_for_card(ferryman_id)


def test_the_character_http_refusals(tmp_path: Path) -> None:
    """The grammar and the authority, over live HTTP: the builtin deletes
    as 409 and rewords as 200; an unknown field or a missing name is a
    400; an unknown id is a 404 (update, dossier, delete); and a rename
    leaves the stamp key exactly where it was."""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = _get_json(stack.port, "/api/characters")
        before_stamp = payload["characters"][0]["stamp_key"]

        status, payload = _delete_json(stack.port, f"/api/characters/{NELL_ID}")
        assert status == 409, payload
        assert "cannot be deleted" in payload["error"]

        status, payload = _put_json(
            stack.port,
            f"/api/characters/{NELL_ID}",
            {"personality": "reworded by her keeper"},
        )
        assert status == 200, payload
        assert payload["character"]["revision"] == 2

        status, payload = stack.post(
            "/api/characters", {"name": "", "identity": "x"}
        )
        assert status == 400, payload

        status, payload = stack.post(
            "/api/characters",
            {**FERRYMAN_FIELDS, "homepage": "https://no.example"},
        )
        assert status == 400, payload
        assert "unknown character field" in payload["error"]

        status, payload = _put_json(
            stack.port, "/api/characters/card-nobody", {"name": "x"}
        )
        assert status == 404, payload
        status, payload = _delete_json(
            stack.port, "/api/characters/card-nobody"
        )
        assert status == 404, payload
        status, payload = _get_json(stack.port,
            "/api/partner?character_id=card-nobody"
        )
        assert status == 404, payload

        # Create, rename, and the stamp does not move.
        status, payload = stack.post("/api/characters", FERRYMAN_FIELDS)
        assert status == 200, payload
        ferryman_id = payload["character"]["character_id"]
        status, payload = _put_json(
            stack.port,
            f"/api/characters/{ferryman_id}",
            {"name": "周师傅"},
        )
        assert status == 200, payload
        assert payload["character"]["name"] == "周师傅"
        assert payload["character"]["stamp_key"] == stamp_key_for(ferryman_id)
        assert payload["character"]["stamp_key"] != before_stamp

        status, payload = _delete_json(
            stack.port, f"/api/characters/{ferryman_id}"
        )
        assert status == 200, payload
        status, payload = _get_json(stack.port, "/api/characters")
        assert [item["character_id"] for item in payload["characters"]] == [
            NELL_ID
        ]


# ---------------------------------------------------------------------------
# 6 — the assembly: table first, penpal fallback
# ---------------------------------------------------------------------------


def _mc0_world(tmp_path: Path, pilot_content_db: Path, conversation: str):
    """A full-chain host with a recording provider (the cs-1 world's
    shape): returns (host, provider) with the conversation opened and
    bound to the persona the caller chose."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(
        tmp_path / "app.db",
        provider=provider,
        content_db_path=pilot_content_db,
    )
    assert isinstance(
        host.open_conversation(ConversationId(conversation)), Ok
    )
    return host, provider


def test_a_user_card_reaches_the_provider_prompt(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The per-persona card, at the model boundary: a conversation bound
    to a user card's persona compiles the **user card** — the structure
    lines and the framed identity text are the created character's, not
    the penpal's."""

    host, provider = _mc0_world(tmp_path, pilot_content_db, "mc0-conv")
    cards = host.character_cards
    record = _user_record(cards)
    assert isinstance(cards.create(record), Ok), cards.create
    bound = host.open_conversation(
        ConversationId("mc0-conv"),
        persona_id=PersonaId(record.persona_id),
    )
    assert isinstance(bound, Ok), bound

    result = host.coordinator.begin_turn(
        _command("你好。", "mc0-conv", "card")
    )
    assert isinstance(result, Ok), result
    assert result.value.turn_status is TurnStatus.COMPLETED
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]
    assert f"character_package_id: {record.character_id}" in prompt
    assert f"persona_id: {record.persona_id}" in prompt
    assert "a retired ferryman" in prompt
    assert "Nell Alder" not in prompt


def test_an_edited_table_card_overrides_the_constant(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Table first: Nell's row edited in the table, a fresh host, and the
    prompt for her conversation carries the **table's** wording — the
    constant is the fallback, never an override."""

    first = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
    )
    edited = first.character_cards.update(
        NELL_ID,
        {"identity": "Nell Alder — a bookbinder, now writing from the quay"},
    )
    assert isinstance(edited, Ok), edited
    first.close()

    host, provider = _mc0_world(tmp_path, pilot_content_db, "web-default")
    host.open_conversation(
        ConversationId("web-default"), persona_id=PENPAL_PERSONA_ID
    )
    result = host.coordinator.begin_turn(
        _command("你好。", "web-default", "table-first")
    )
    assert isinstance(result, Ok), result
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]
    assert "writing from the quay" in prompt
    host.close()


def test_a_persona_without_a_card_falls_back_to_the_injected_package(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The fallback half: a conversation bound to a persona no card names
    compiles the injected default (the penpal) — today's behaviour,
    byte for byte, is what an unknown persona still gets."""

    host, provider = _mc0_world(tmp_path, pilot_content_db, "mc0-conv")
    host.open_conversation(
        ConversationId("mc0-conv"),
        persona_id=PersonaId("persona-no-card-here"),
    )
    result = host.coordinator.begin_turn(
        _command("你好。", "mc0-conv", "fallback")
    )
    assert isinstance(result, Ok), result
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]
    assert "Nell Alder" in prompt
    host.close()


def test_an_explicit_none_package_stays_bare(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """``character_package=None`` restores the bare prep-1 shape — MC-0's
    table must not sneak a card back into the degraded assembly (the card
    map is built only when a package was injected)."""

    provider = RecordingProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(
        tmp_path / "app.db",
        provider=provider,
        content_db_path=pilot_content_db,
        character_package=None,
    )
    resolver = host.coordinator._character_package_for
    assert resolver(PersonaId("persona-nell-alder")) is None
    assert isinstance(
        host.open_conversation(
            ConversationId("mc0-conv"), persona_id=PENPAL_PERSONA_ID
        ),
        Ok,
    )
    result = host.coordinator.begin_turn(
        _command("你好。", "mc0-conv", "bare")
    )
    assert isinstance(result, Ok), result
    prompt = provider.prompts[0].prompt_text  # type: ignore[attr-defined]
    assert "identity: Nell Alder" not in prompt
    host.close()


# ---------------------------------------------------------------------------
# 7 — backward compatibility
# ---------------------------------------------------------------------------


def test_the_conversation_mapping_keeps_the_shipped_envelopes() -> None:
    """The mapping rule, unit-pinned: the penpal keeps ``web-default``
    (every letter ever written there stays hers), every other character
    derives ``web-<character_id>``, and the CLI's ``cli-default`` is the
    chat face's own envelope — the web mapping never claims it."""

    from elc.web import _conversation_for_character

    assert _conversation_for_character(NELL_ID) == "web-default"
    assert _conversation_for_character("card-abc123") == "web-card-abc123"
    from elc.cli import DEFAULT_CONVERSATION_ID

    assert str(DEFAULT_CONVERSATION_ID) == "cli-default"


# ---------------------------------------------------------------------------
# 8 — the BF-05 disposition
# ---------------------------------------------------------------------------


def test_the_sweep_walks_user_cards_and_keeps_the_builtin(
    tmp_path: Path,
) -> None:
    """ALL_USER_DATA removes the user's authored characters and never the
    shipped one: the sweep's ``is_builtin = 0`` leg is the same authority
    rule the card store's delete face enforces. The user cards are gone
    (and tombstoned), the builtin row is still there, and the empty-table
    fallback is visible: a fresh host after the sweep still assembles."""

    provider = ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),))
    host = open_host(tmp_path / "app.db", provider=provider)
    cards = host.character_cards
    record = _user_record(cards)
    assert isinstance(cards.create(record), Ok), cards.create
    host.close()

    conn = sqlite3.connect(tmp_path / "app.db")
    fence = open_runtime_epoch(conn)
    # The deletion suite's own assembly is the store+controller pair; MC-0
    # only needs the scope walk, so the controller is built the prep-1 way
    # (store, no rebuild legs — each affected key reports its own refusal).
    controller = DeletionController(SqliteDeletionStore(conn, fence))
    result = controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert isinstance(result, Ok), result
    remaining = [
        str(row[0])
        for row in conn.execute(
            "SELECT character_id FROM character_card"
        ).fetchall()
    ]
    assert remaining == [NELL_ID]
    tombstones = [
        str(row[0])
        for row in conn.execute(
            "SELECT entity_kind FROM deletion_tombstone"
        ).fetchall()
    ]
    assert "character_card" in tombstones
    conn.close()

    reopened = open_host(tmp_path / "app.db", provider=provider)
    listed = reopened.character_cards.list_all()
    assert isinstance(listed, Ok), listed
    assert [item.character_id for item in listed.value] == [NELL_ID]
    reopened.close()
