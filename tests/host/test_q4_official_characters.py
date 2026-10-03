"""Queue ④ — the official character family's pins (官方角色扩充刀).

cs-1 through MC-0 shipped one production character. Queue ④
(``DEC-OPI-32409938-…30``) adds three official companions — a casual
friend (Theo Marsh, spoken register), a workplace colleague (Priya
Anand, semi-formal email+chat), a formal correspondent (Evelyn Hart,
formal letters) — widens the assembly face from the single penpal
constant to the official family, and seeds every official card into the
card table as a builtin on every open.

Five groups (the slice's own, ``VAL-OPI-32409938-…32``):

1. **the family pins** — the official set is exactly four packages by
   id (the penpal first), every card carries all eight prose faces at
   Nell's own heft (word for word compared against her), the whole
   family is cs-0 clean, and each character's literals live in exactly
   one src file;
2. **the register pins** — the language domains are audibly apart:
   opening sentence means order strictly (casual < workplace < formal,
   pairwise gap ≥ 0.5), contraction counts fall the same way (2 / 1 / 0)
   and each register carries only its own markers (slang vs workplace
   formulas vs formal set phrases);
3. **the assembly pins** — ``open_host`` still defaults to the penpal,
   the official family seeds as builtins field for field (idempotently,
   a keeper's edit surviving the reopen), ``character_package=None``
   seeds nothing, the roster serves all four as builtins, the mc-2
   semantics hold for the newcomers (editable, never deletable, stamp
   rename-stable), the web create face inherits the family's lifecycle
   pair and the dossier follows the served character;
4. **the switch E2E** — two companions over live HTTP with the real
   producer: each switch builds its own persona-bound conversation, each
   correspondence lands in its own isolated memory, and the penpal's
   line stays clear of both;
5. **the mutation carriers** — the pins mutations 1–3 must strike:
   m1 (delete a package from the set) → the family id pin; m2 (seed a
   builtin without the marker) → the seed's ``is_builtin`` pin;
   m3 (break the switch chain) → the group-4 E2E.
"""

from __future__ import annotations

import inspect
import json
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import build_content_db
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import open_host
from elc.persona.card_store import card_to_package, stamp_key_for
from elc.persona.official import (
    COLLEAGUE_CHARACTER_PACKAGE,
    COLLEAGUE_CHARACTER_PACKAGE_ID,
    COLLEAGUE_PERSONA_ID,
    CORRESPONDENT_CHARACTER_PACKAGE,
    CORRESPONDENT_CHARACTER_PACKAGE_ID,
    CORRESPONDENT_PERSONA_ID,
    FRIEND_CHARACTER_PACKAGE,
    FRIEND_CHARACTER_PACKAGE_ID,
    FRIEND_PERSONA_ID,
    OFFICIAL_CHARACTER_IDS,
    OFFICIAL_CHARACTER_PACKAGES,
)
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE,
    PENPAL_CHARACTER_PACKAGE_ID,
    PENPAL_PERSONA_ID,
    penpal_character_package,
)
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import Ok
from tests.host.test_cs0_teaching_isolation import MECHANISM_WORDS
from tests.host.test_cs1_character_activation import PEDAGOGY_WORDS
from tests.host.test_mc0_multi_character import (
    _get_json,
    _memories_text,
)
from tests.host.test_w1_web import web_stack

REPLY = "Understood — the kettle is on and I am listening."

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "elc"

#: The eight prose faces, in §5.1 order (the heft pin walks all of them;
#: lore_refs is an id list, not prose — q4R LOW-1 wording fix).
_FACES = (
    "identity",
    "personality",
    "background",
    "speech_style",
    "values",
    "boundaries",
    "opening",
    "scenario",
)

#: The pedagogy words ride cs-0's mechanism list (the cs-1 pairing).
CARD_BLACKLIST = MECHANISM_WORDS + PEDAGOGY_WORDS

#: The contraction vocabulary the register pin counts. Possessives
#: (``mother's``) are not contractions and stay off the list.
_CONTRACTIONS = (
    "won't", "don't", "can't", "i'm", "i'll", "you're", "it's",
    "they're", "we're", "i've", "doesn't", "didn't", "isn't",
    "aren't", "couldn't", "wouldn't", "shouldn't", "hasn't",
    "haven't", "that's", "there's", "what's", "let's",
)


def _sentences(text: str) -> list[int]:
    """Sentence word counts of one opening (split on terminal marks)."""

    parts = [p for p in re.split(r"[.?!]+", text) if p.strip()]
    return [len(p.split()) for p in parts]


def _card_text(package: object) -> str:
    """One package's free-text columns, joined (the cs-1 scan shape)."""

    return "; ".join(
        (
            str(package.identity),  # type: ignore[attr-defined]
            str(package.personality),  # type: ignore[attr-defined]
            str(package.background),  # type: ignore[attr-defined]
            str(package.speech_style),  # type: ignore[attr-defined]
            str(package.values),  # type: ignore[attr-defined]
            str(package.boundaries),  # type: ignore[attr-defined]
            str(package.opening),  # type: ignore[attr-defined]
            str(package.scenario),  # type: ignore[attr-defined]
            str(package.generation_policy),  # type: ignore[attr-defined]
            "; ".join(package.lore_refs),  # type: ignore[attr-defined]
        )
    )


def _src_files_with(literal: str) -> set[str]:
    return {
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if literal in path.read_text(encoding="utf-8")
    }


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One built content artifact for the module (the relationship
    projections need the full chain to run for real)."""

    path = tmp_path_factory.mktemp("q4-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def _bare_host(tmp_path: Path) -> object:
    """A prep-1-tier host on a fresh database (the seed pins' world)."""

    return open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
    )


# ---------------------------------------------------------------------------
# 1 — the family pins
# ---------------------------------------------------------------------------


def test_the_official_family_is_four_packages_by_id() -> None:
    """① The set pin (mutation m1's target): exactly four, the penpal in
    the default seat, every id and persona pair spelled once."""

    assert OFFICIAL_CHARACTER_IDS == (
        "cpkg-nell-alder",
        "cpkg-theo-marsh",
        "cpkg-priya-anand",
        "cpkg-evelyn-hart",
    )
    assert OFFICIAL_CHARACTER_PACKAGES[0] is PENPAL_CHARACTER_PACKAGE
    assert str(PENPAL_CHARACTER_PACKAGE_ID) == "cpkg-nell-alder"
    assert str(PENPAL_PERSONA_ID) == "persona-nell-alder"
    assert str(FRIEND_CHARACTER_PACKAGE_ID) == "cpkg-theo-marsh"
    assert str(FRIEND_PERSONA_ID) == "persona-theo-marsh"
    assert str(COLLEAGUE_CHARACTER_PACKAGE_ID) == "cpkg-priya-anand"
    assert str(COLLEAGUE_PERSONA_ID) == "persona-priya-anand"
    assert str(CORRESPONDENT_CHARACTER_PACKAGE_ID) == "cpkg-evelyn-hart"
    assert str(CORRESPONDENT_PERSONA_ID) == "persona-evelyn-hart"
    # one shared lifecycle pair across the family (what the web create
    # face inherits): one generation policy, one status, all ACTIVE v1.
    assert len({p.generation_policy for p in OFFICIAL_CHARACTER_PACKAGES}) == 1
    assert len({p.status for p in OFFICIAL_CHARACTER_PACKAGES}) == 1


@pytest.mark.parametrize(
    "package",
    list(OFFICIAL_CHARACTER_PACKAGES),
    ids=list(OFFICIAL_CHARACTER_IDS),
)
def test_every_official_card_carries_nine_nell_grade_faces(
    package: Any,
) -> None:
    """① Nine faces complete, each at least as heavy as the penpal's own
    (the quality bar is computed, not asserted in prose)."""

    nell = penpal_character_package()
    for face in _FACES:
        text = str(getattr(package, face))
        assert text.strip(), face
        assert len(text.split()) >= len(
            str(getattr(nell, face)).split()
        ), face


def test_every_official_card_is_cs0_clean() -> None:
    """① The whole family under cs-0's isolation rule: zero mechanism
    words, zero pedagogy words — none of the four knows the app's
    teaching system exists."""

    for package in OFFICIAL_CHARACTER_PACKAGES:
        card = _card_text(package)
        for word in CARD_BLACKLIST:
            assert word not in card, (package.character_package_id, word)


@pytest.mark.parametrize(
    ("literal",),
    [
        ("Theo Marsh",),
        ("persona-theo-marsh",),
        ("cpkg-theo-marsh",),
        ("Greyfield",),
        ("Priya Anand",),
        ("persona-priya-anand",),
        ("cpkg-priya-anand",),
        ("Evelyn Hart",),
        ("persona-evelyn-hart",),
        ("cpkg-evelyn-hart",),
        ("Wellsby",),
    ],
)
def test_each_new_character_lives_in_exactly_one_src_file(
    literal: str,
) -> None:
    """① The single-source rule, extended to the family: every literal of
    a companion has exactly one physical point — the official module."""

    assert _src_files_with(literal) == {str(Path("persona") / "official.py")}


# ---------------------------------------------------------------------------
# 2 — the register pins
# ---------------------------------------------------------------------------


def test_the_three_domains_sound_nothing_alike() -> None:
    """② The hard metric, on the constants themselves: opening sentence
    means order strictly with a real gap (casual < workplace < formal;
    measured 8.25 / 9.0 / 12.75 at birth), contraction counts fall the
    same way (2 / 1 / 0), and each register carries only its own
    markers — slang, workplace formulas, formal set phrases."""

    theo = FRIEND_CHARACTER_PACKAGE
    priya = COLLEAGUE_CHARACTER_PACKAGE
    evelyn = CORRESPONDENT_CHARACTER_PACKAGE

    means = {
        name: round(sum(_sentences(card.opening)) / len(_sentences(card.opening)), 2)
        for name, card in (
            ("theo", theo),
            ("priya", priya),
            ("evelyn", evelyn),
        )
    }
    assert means["theo"] < means["priya"] < means["evelyn"]
    assert means["priya"] - means["theo"] >= 0.5
    assert means["evelyn"] - means["priya"] >= 0.5
    assert means["theo"] <= 8.5
    assert means["evelyn"] >= 11.5

    def contractions(card: Any) -> int:
        text = (card.speech_style + " " + card.opening).lower()
        return sum(1 for word in _CONTRACTIONS if word in text)

    assert contractions(theo) >= 2 > contractions(priya) >= 1
    assert contractions(evelyn) == 0

    # the casual markers (slang worn natural, never explained)
    theo_text = (theo.speech_style + " " + theo.opening).lower()
    for marker in ("gonna", "kinda", "signs off later"):
        assert marker in theo_text, marker
    # the workplace markers (email + chat mix, action first)
    assert "hi <name>" in priya.speech_style.lower()
    assert "best, priya" in priya.speech_style.lower()
    assert "circling back" in priya.speech_style.lower()
    # the formal markers (complete sentences, the full-name close)
    assert "yours sincerely" in evelyn.speech_style.lower()
    assert "no contractions" in evelyn.speech_style.lower()
    assert "i remain, as ever" in evelyn.speech_style.lower()
    # and the closing conventions part company too
    assert "catch you thursday" in theo_text
    assert priya.opening.endswith("Best, Priya")
    assert evelyn.opening.endswith("Yours sincerely, Evelyn Hart")


# ---------------------------------------------------------------------------
# 3 — the assembly pins
# ---------------------------------------------------------------------------


def test_the_composition_root_still_defaults_to_the_penpal() -> None:
    """③ R2's unchanged half: the default parameter is the penpal —
    object identity, not equality — so a family edit cannot silently
    move the shipped default."""

    parameter = inspect.signature(open_host).parameters["character_package"]
    assert parameter.default is PENPAL_CHARACTER_PACKAGE


def test_open_host_seeds_the_official_family_as_builtins(
    tmp_path: Path,
) -> None:
    """③ Every open carries the family into the card table: four builtin
    rows, field for field the packages (the seed pin, the sibling of
    MC-0's migration seed pin), roster order builtin-first by id."""

    host = _bare_host(tmp_path)  # type: ignore[arg-type]
    try:
        listed = host.character_cards.list_all()  # type: ignore[attr-defined]
        assert isinstance(listed, Ok), listed
        assert [row.character_id for row in listed.value] == sorted(
            OFFICIAL_CHARACTER_IDS
        )
        rows = {row.character_id: row for row in listed.value}
        for package in OFFICIAL_CHARACTER_PACKAGES:
            package_id = str(package.character_package_id)
            row = rows[package_id]
            # the builtin marker (mutation m2's target)
            assert row.is_builtin is True, package_id
            # the spoken name is the identity line's first segment —
            # derived, never a second spelling
            assert row.name == str(package.identity).partition(" — ")[0]
            assert row.created_at == str(package.updated_at)
            assert row.updated_at == str(package.updated_at)
            view = card_to_package(row)
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
                assert getattr(view, field) == getattr(
                    package, field
                ), (package_id, field)
    finally:
        host.close()  # type: ignore[attr-defined]


def test_the_seed_is_idempotent_and_a_keepers_edit_survives(
    tmp_path: Path,
) -> None:
    """③ Seed by presence, never by overwrite: the second open adds no
    rows and does not clobber a keeper's rewording — the constants are
    the birth record, the table is the live truth."""

    first = _bare_host(tmp_path)  # type: ignore[arg-type]
    try:
        cards = first.character_cards  # type: ignore[attr-defined]
        edited = cards.update(
            str(FRIEND_CHARACTER_PACKAGE_ID),
            {"personality": "reworded by his keeper"},
        )
        assert isinstance(edited, Ok), edited
        assert edited.value.revision == 2
    finally:
        first.close()  # type: ignore[attr-defined]

    second = _bare_host(tmp_path)  # type: ignore[arg-type]
    try:
        cards = second.character_cards  # type: ignore[attr-defined]
        read = cards.get(str(FRIEND_CHARACTER_PACKAGE_ID))
        assert isinstance(read, Ok), read
        assert read.value.personality == "reworded by his keeper"
        assert read.value.revision == 2
        listed = cards.list_all()
        assert isinstance(listed, Ok), listed
        assert len(listed.value) == 4  # no duplicates, no re-birth
    finally:
        second.close()  # type: ignore[attr-defined]


def test_an_explicit_none_package_seeds_nothing(tmp_path: Path) -> None:
    """③ The bare prep-1 shape stays bare: ``character_package=None``
    seeds nothing — the migration's penpal row is all the table has."""

    host = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
        character_package=None,
    )
    try:
        listed = host.character_cards.list_all()
        assert isinstance(listed, Ok), listed
        assert [row.character_id for row in listed.value] == [
            str(PENPAL_CHARACTER_PACKAGE_ID)
        ]
    finally:
        host.close()


def test_the_roster_serves_the_official_family(tmp_path: Path) -> None:
    """③ The roster face reads the table the seed filled: four builtins,
    builtin-first by id, each with its derived stamp key and spoken
    name; nothing is current before a switch."""

    with web_stack(tmp_path / "app.db") as stack:
        status, roster = _get_json(stack.port, "/api/characters")
        assert status == 200, roster
        items = roster["characters"]
        assert [item["character_id"] for item in items] == sorted(
            OFFICIAL_CHARACTER_IDS
        )
        assert all(item["is_builtin"] for item in items)
        names = {item["character_id"]: item["name"] for item in items}
        assert names[str(FRIEND_CHARACTER_PACKAGE_ID)] == "Theo Marsh"
        assert names[str(COLLEAGUE_CHARACTER_PACKAGE_ID)] == "Priya Anand"
        assert names[str(CORRESPONDENT_CHARACTER_PACKAGE_ID)] == "Evelyn Hart"
        for item in items:
            assert item["stamp_key"] == stamp_key_for(item["character_id"])
        assert roster["current_character_id"] is None


def test_the_new_builtins_keep_mc2_semantics(tmp_path: Path) -> None:
    """③ mc-2 holds for the newcomers: a companion is editable (her
    keeper may reword her, revision bumps), never deletable (409, the
    authority refusal), and her stamp key survives a rename."""

    theo_id = str(FRIEND_CHARACTER_PACKAGE_ID)
    with web_stack(tmp_path / "app.db") as stack:
        status, payload = _delete_json(stack.port, f"/api/characters/{theo_id}")
        assert status == 409, payload
        assert "cannot be deleted" in payload["error"]

        status, payload = _put_json(
            stack.port, f"/api/characters/{theo_id}",
            {"personality": "reworded on the live face"},
        )
        assert status == 200, payload
        assert payload["character"]["revision"] == 2
        assert payload["character"]["is_builtin"] is True

        status, payload = _put_json(
            stack.port, f"/api/characters/{theo_id}", {"name": "Theo M."}
        )
        assert status == 200, payload
        assert payload["character"]["stamp_key"] == stamp_key_for(theo_id)


def test_user_cards_are_born_from_the_official_lifecycle_pair(
    tmp_path: Path,
) -> None:
    """③ The create face reads the family (the re-pointed direct read):
    a user card inherits the official pair — the family head is quoted,
    no second spelling — and is born ``is_builtin: False``. The static
    pin holds the re-point itself."""

    web = (REPO / "src" / "elc" / "web.py").read_text(encoding="utf-8")
    assert "OFFICIAL_CHARACTER_PACKAGES[0].generation_policy" in web
    assert "OFFICIAL_CHARACTER_PACKAGES[0].status" in web

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.post(
            "/api/characters",
            {"name": "摆渡人", "identity": "清晨还在补网的退休摆渡人"},
        )
        assert status == 200, payload
        card = payload["character"]
        assert card["is_builtin"] is False
        # the lifecycle pair itself rides the row (the summary face does
        # not serve it) — read the table after the create
        conn = sqlite3.connect(
            f"file:{tmp_path / 'app.db'}?mode=ro", uri=True
        )
        try:
            row = conn.execute(
                "SELECT generation_policy, status, is_builtin"
                " FROM character_card WHERE character_id = ?",
                (card["character_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert str(row[0]) == (
            OFFICIAL_CHARACTER_PACKAGES[0].generation_policy
        )
        assert str(row[1]) == OFFICIAL_CHARACTER_PACKAGES[0].status
        assert int(row[2]) == 0


def test_the_dossier_follows_the_served_character(tmp_path: Path) -> None:
    """③ The card face's two arms: a conversation that names no card
    falls back to the penpal constant (cs-2's world, byte-compat); one
    that names a card reads the table — so the dossier follows the
    switch instead of pinning the penpal's face."""

    theo_id = str(FRIEND_CHARACTER_PACKAGE_ID)
    with web_stack(tmp_path / "app.db") as stack:
        status, payload = _get_json(stack.port, "/api/partner")
        assert status == 200, payload
        assert payload["card"]["name"] == "Nell Alder"

        status, payload = stack.post(
            "/api/characters/switch", {"character_id": theo_id}
        )
        assert status == 200, payload
        status, payload = _get_json(stack.port, "/api/partner")
        assert status == 200, payload
        assert payload["card"]["name"] == "Theo Marsh"

        status, payload = stack.post(
            "/api/characters/switch",
            {"character_id": str(PENPAL_CHARACTER_PACKAGE_ID)},
        )
        assert status == 200, payload
        status, payload = _get_json(stack.port, "/api/partner")
        assert status == 200, payload
        assert payload["card"]["name"] == "Nell Alder"


# ---------------------------------------------------------------------------
# 4 — the switch E2E (mutation m3's target)
# ---------------------------------------------------------------------------


def test_switching_between_official_companions_isolates_the_lines(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """④ Two companions, two real correspondences through the real
    producer: each switch lazily builds ``web-<id>`` bound to the
    companion's persona, each ZH fact candidate lands as its own pair's
    durable memory, and neither line leaks into the other's dossier —
    nor into the penpal's."""

    theo_id = str(FRIEND_CHARACTER_PACKAGE_ID)
    evelyn_id = str(CORRESPONDENT_CHARACTER_PACKAGE_ID)
    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, payload = stack.post(
            "/api/characters/switch", {"character_id": theo_id}
        )
        assert status == 200, payload
        assert payload["conversation"] == f"web-{theo_id}"
        status, payload = stack.post(
            "/api/turn", {"text": "你好！我叫小舟，我在苏州工作。"}
        )
        assert status == 200, payload

        status, payload = stack.post(
            "/api/characters/switch", {"character_id": evelyn_id}
        )
        assert status == 200, payload
        assert payload["conversation"] == f"web-{evelyn_id}"
        status, payload = stack.post(
            "/api/turn", {"text": "你好！我叫小澜，我在南京工作。"}
        )
        assert status == 200, payload

        status, payload = _get_json(
            stack.port, f"/api/partner?character_id={theo_id}"
        )
        assert status == 200, payload
        assert payload["card"]["name"] == "Theo Marsh"
        assert payload["conversation_id"] == f"web-{theo_id}"
        assert payload["stats"]["turns"] == 1
        his = _memories_text(payload)
        assert "小舟" in his
        assert "小澜" not in his

        status, payload = _get_json(
            stack.port, f"/api/partner?character_id={evelyn_id}"
        )
        assert status == 200, payload
        assert payload["card"]["name"] == "Evelyn Hart"
        assert payload["conversation_id"] == f"web-{evelyn_id}"
        assert payload["stats"]["turns"] == 1
        hers = _memories_text(payload)
        assert "小澜" in hers
        assert "小舟" not in hers

        # the penpal's envelope stays hers, clear of both lines
        status, payload = stack.post(
            "/api/characters/switch",
            {"character_id": str(PENPAL_CHARACTER_PACKAGE_ID)},
        )
        assert status == 200, payload
        assert payload["conversation"] == "web-default"
        status, payload = _get_json(stack.port, "/api/partner")
        assert status == 200, payload
        neither = _memories_text(payload)
        assert "小舟" not in neither
        assert "小澜" not in neither

    # the durable half: the two lazily built rows carry the right personas
    conn = sqlite3.connect(f"file:{tmp_path / 'app.db'}?mode=ro", uri=True)
    try:
        for character_id, persona_id in (
            (theo_id, str(FRIEND_PERSONA_ID)),
            (evelyn_id, str(CORRESPONDENT_PERSONA_ID)),
        ):
            row = conn.execute(
                "SELECT persona_id FROM conversation"
                " WHERE conversation_id = ?",
                (f"web-{character_id}",),
            ).fetchone()
            assert row is not None, character_id
            assert str(row[0]) == persona_id
    finally:
        conn.close()


def _delete_json(port: int, path: str) -> tuple[int, Any]:
    """The roster's remove face — DELETE with error answers decoded (an
    HTTPError must not raise past the refusal pin)."""

    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
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
