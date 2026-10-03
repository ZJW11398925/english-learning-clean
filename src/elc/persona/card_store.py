"""The user-authored character card store (MC-0) — CRUD over app.db.

The cs-1 world had exactly one production character: the fixed penpal
(:mod:`elc.persona.penpal`), held as constants, injected by the composition
root. The multi-character adjudication (DEC-OPI-a31b14c9…43) opens that up:
**the user authors their own characters, and can author many.** This module
is the durable half of that — the ``character_card`` table (migration 0019)
and the CRUD face over it:

- **create** — a server-minted ``card-`` id, a derived
  ``persona-<character_id>`` persona (the Persona half of the
  (persona, user) pair the relationship projections key on — one card, one
  persona, one isolated memory), the user's prose as given. The text is
  **untrusted and stored as-is**: the cs-0 blacklist is a *generation-time*
  discipline (the role cannot know a teaching system exists) and the web
  face escapes what it renders; this store is a shelf, not a judge — it
  validates shape (a name exists), never words.
- **list** — builtin first, then by id (one deterministic order; the list
  face serves it as-is).
- **update** — the prose and the name, nothing else: ``character_id`` /
  ``persona_id`` / ``is_builtin`` / ``created_at`` are the card's identity
  and are immutable here. Every update bumps ``revision`` (the §5.1 package
  revision counter) and re-stamps ``updated_at``. The **builtins are
  editable** — the adjudication's ruling: the keeper of an official card
  may reword it, but an official card cannot be un-officialled (its
  persona id is bound to the conversations that already speak with it),
  so it can be shaped, never removed.
- **delete** — user cards only; a builtin card answers
  ``AUTHORITY_VIOLATION`` (the same refusal family the BF-05 authorities
  use: this store is not the authority that may end an official card).

The §5.1 bridge: :func:`card_to_package` lifts a row into the canonical
:data:`CharacterPackageRecord` the prompt compiler consumes — the storage
form and the canonical record agree column for column (``lore_refs`` rides
the deterministic JSON array document, the 0015/0016/0018 convention). The
composition root injects the **live** view over that bridge
(:class:`CharacterCardPackages` — "table first, penpal fallback"): a
conversation bound to a card's persona speaks with that card as the table
has it *right now* (a card created after the host opened speaks from its
first turn); a persona without a card row falls back to the injected
default package.

Deterministic reads: no clock on the read faces, one order, and
:func:`stamp_key_for` is a pure function of the id — the same card yields
the same stamp key forever, across processes, so the frontend can pick a
visual variant by it without asking twice.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from elc.persona.types import CharacterPackageRecord
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = [
    "USER_CARD_ID_PREFIX",
    "CharacterCardPackages",
    "CharacterCardRecord",
    "SqliteCharacterCardStore",
    "card_to_package",
    "persona_id_for_card",
    "stamp_key_for",
]

#: The server-minted id shape for user-authored cards (the store's create
#: face prefixes every mint with this; the seeded penpal keeps her own
#: ``cpkg-`` id).
USER_CARD_ID_PREFIX = "card-"


def stamp_key_for(character_id: str) -> str:
    """The stamp's derived key — a pure function of the character id.

    The frontend picks a stamp variant per character from this key; the
    server only derives it. Sixteen hex characters of the id's SHA-256: the
    same id always yields the same key (deterministic across processes and
    restarts — a pin holds this), and a **rename does not move it**, because
    the key is derived from the id alone — the stamp is who the character
    is, not what they are called this week.
    """

    return hashlib.sha256(character_id.encode("utf-8")).hexdigest()[:16]


def persona_id_for_card(character_id: str) -> str:
    """The derived persona half for a user-authored card.

    One card, one persona: the (persona, user) pair the relationship
    projections write for is what keeps two characters' memories apart, and
    the derivation makes the pairing one-to-one by construction. The seeded
    penpal does not go through this derivation — her row carries her real
    persona id (the penpal module's own constant, the one the shipped faces
    have bound since cs-1; spelled there, and only there, by the
    single-source rule).
    """

    return f"persona-{character_id}"


@dataclass(frozen=True)
class CharacterCardRecord:
    """One row of ``character_card``, field for field.

    The canonical CharacterPackage's column set (§5.1 via
    :class:`CharacterPackageRecord`) plus the two columns a user-facing
    card needs beyond it — ``name`` (the spoken name; §5.1 derives it from
    the identity line, a user names a card directly) and ``is_builtin``
    (the seeded penpal vs. user-authored). ``created_at`` / ``updated_at``
    are lifecycle metadata and render into no prompt.
    """

    character_id: str
    persona_id: str
    name: str
    identity: str
    personality: str
    background: str
    speech_style: str
    values: str
    boundaries: str
    opening: str
    scenario: str
    generation_policy: str
    lore_refs: tuple[str, ...]
    revision: int
    status: str
    is_builtin: bool
    created_at: str
    updated_at: str


def card_to_package(record: CharacterCardRecord) -> CharacterPackageRecord:
    """Lift a card row into the canonical §5.1 record the compiler consumes.

    A rename of fields, never a reshaping: every value passes through under
    its own name (``values`` the column → ``values`` the field), and the
    lifecycle metadata rides along (the record's ``updated_at`` is the
    row's — the prompt compiler ignores it, the dossier faces may show it).
    """

    return CharacterPackageRecord(
        character_package_id=record.character_id,  # type: ignore[arg-type]
        persona_id=record.persona_id,  # type: ignore[arg-type]
        revision=record.revision,
        identity=record.identity,
        personality=record.personality,
        background=record.background,
        speech_style=record.speech_style,
        values=record.values,
        boundaries=record.boundaries,
        opening=record.opening,
        scenario=record.scenario,
        generation_policy=record.generation_policy,
        lore_refs=record.lore_refs,
        status=record.status,
        updated_at=record.updated_at,
    )


_CARD_COLUMNS = (
    "character_id",
    "persona_id",
    "name",
    "identity",
    "personality",
    "background",
    "speech_style",
    '"values"',
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
)

#: The prose fields an update may reword — the update face's whole writable
#: surface, by name (``values`` quoted for the same SQL-keyword reason).
_UPDATABLE_COLUMNS = (
    "name",
    "identity",
    "personality",
    "background",
    "speech_style",
    '"values"',
    "boundaries",
    "opening",
    "scenario",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err:
    return Err(DomainError(code=code, message=message))


def _lore_document(refs: tuple[str, ...]) -> str:
    """The deterministic array document (the 0015/0016/0018 encoding)."""

    return json.dumps(list(refs), sort_keys=True, separators=(",", ":"))


def _row_to_record(row: sqlite3.Row) -> CharacterCardRecord:
    return CharacterCardRecord(
        character_id=str(row[0]),
        persona_id=str(row[1]),
        name=str(row[2]),
        identity=str(row[3]),
        personality=str(row[4]),
        background=str(row[5]),
        speech_style=str(row[6]),
        values=str(row[7]),
        boundaries=str(row[8]),
        opening=str(row[9]),
        scenario=str(row[10]),
        generation_policy=str(row[11]),
        lore_refs=tuple(json.loads(str(row[12]))),
        revision=int(row[13]),
        status=str(row[14]),
        is_builtin=bool(row[15]),
        created_at=str(row[16]),
        updated_at=str(row[17]),
    )


class SqliteCharacterCardStore:
    """The ``character_card`` CRUD face — short transactions, fenced writes.

    Reads are plain SELECTs (the shared connection, the caller's thread);
    every write is one :func:`short_transaction` guarded by the process's
    epoch fence — the same write posture as every sibling store. A
    ``UNIQUE`` violation on ``persona_id`` or the primary key surfaces as
    ``CONFLICT`` (a duplicate is a caller's naming decision, not a crash).
    """

    def __init__(
        self, conn: sqlite3.Connection, fence: RuntimeEpochFence
    ) -> None:
        self._conn = conn
        self._fence = fence

    def _require_current_epoch(self) -> None:
        """Fence inside the write transaction (the conversation store's
        shape, restated): the adopted epoch must still be the newest epoch
        row in app.db (§24 restart ownership)."""

        row = self._conn.execute(
            "SELECT MAX(epoch) FROM runtime_epoch"
        ).fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleEpochError(
                f"store epoch={self._fence.current}"
                f" fenced by db epoch={newest}"
            )

    # -- reads ------------------------------------------------------------

    def get(self, character_id: str) -> Result[CharacterCardRecord]:
        """One card by id; ``NOT_FOUND`` when there is none."""

        row = self._conn.execute(
            "SELECT " + ", ".join(_CARD_COLUMNS)
            + " FROM character_card WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if row is None:
            return _err(
                DomainErrorCode.NOT_FOUND,
                f"no such character card: {character_id}",
            )
        return Ok(_row_to_record(row))

    def get_by_persona(self, persona_id: str) -> Result[CharacterCardRecord]:
        """One card by its persona half; ``NOT_FOUND`` when there is none.

        The lookup the per-persona card resolution reads (the persona id a
        conversation row carries) — unique by construction, so one row or
        none."""

        row = self._conn.execute(
            "SELECT " + ", ".join(_CARD_COLUMNS)
            + " FROM character_card WHERE persona_id = ?",
            (persona_id,),
        ).fetchone()
        if row is None:
            return _err(
                DomainErrorCode.NOT_FOUND,
                f"no character card carries this persona: {persona_id}",
            )
        return Ok(_row_to_record(row))

    def list_all(self) -> Result[tuple[CharacterCardRecord, ...]]:
        """Every card, builtin first, then by id — one deterministic order.

        The order is a serving order, not a ranking: the list face renders
        it as-is, and the pin holds the shape so a tie-break can never
        start depending on rowid.
        """

        rows = self._conn.execute(
            "SELECT " + ", ".join(_CARD_COLUMNS)
            + " FROM character_card"
            " ORDER BY is_builtin DESC, character_id"
        ).fetchall()
        return Ok(tuple(_row_to_record(row) for row in rows))

    # -- writes -----------------------------------------------------------

    def create(self, record: CharacterCardRecord) -> Result[CharacterCardRecord]:
        """Insert one card, as given (the caller mints id and persona).

        The two shape rules this face owns: **the name exists** (a card
        without a name is a blank stamp — ``VALIDATION_FAILED``) and the
        text is stored as-is (untrusted prose is the web face's escaping
        problem, never a store refusal — the adjudication's no-blacklist
        ruling for user-authored text). ``is_builtin`` is honored as
        passed: the builtin seeders are the 0019 migration (the penpal)
        and the official family's open-time seed
        (``elc.persona.official.ensure_official_cards`` — queue ④), and a
        caller that claims builtin for a fresh row is answered here with
        the same pen those seeders use — the web face always passes
        ``False``.
        """

        if not record.name.strip():
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a character card needs a name",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO character_card ("
                    + ", ".join(_CARD_COLUMNS)
                    + ") VALUES ("
                    + ", ".join("?" * len(_CARD_COLUMNS))
                    + ")",
                    (
                        record.character_id,
                        record.persona_id,
                        record.name,
                        record.identity,
                        record.personality,
                        record.background,
                        record.speech_style,
                        record.values,
                        record.boundaries,
                        record.opening,
                        record.scenario,
                        record.generation_policy,
                        _lore_document(record.lore_refs),
                        record.revision,
                        record.status,
                        1 if record.is_builtin else 0,
                        record.created_at,
                        record.updated_at,
                    ),
                )
        except sqlite3.IntegrityError:
            return _err(
                DomainErrorCode.CONFLICT,
                f"a character card with this id or persona already exists:"
                f" {record.character_id}",
            )
        return Ok(record)

    def mint_user_card_id(self) -> str:
        """A fresh user-card id — the caller's naming seam, kept next to
        the persona derivation so the two shapes cannot drift apart."""

        return f"{USER_CARD_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    def update(
        self, character_id: str, fields: dict[str, str]
    ) -> Result[CharacterCardRecord]:
        """Reword the writable prose of one card; identity never moves.

        Accepts only :data:`_UPDATABLE_COLUMNS` names (a foreign key is
        ``VALIDATION_FAILED`` — the caller cannot rename a card's identity
        by sneaking ``persona_id`` through); an empty ``name`` is refused
        like at creation. **The builtin is editable** (the adjudication's
        ruling) — update does not look at ``is_builtin``. ``revision``
        bumps and ``updated_at`` re-stamps on every accepted update, even
        a value-identical one (an edit happened; the counter says so).
        """

        updatable = [c.strip('"') for c in _UPDATABLE_COLUMNS]
        unknown = sorted(set(fields) - set(updatable))
        if unknown:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a character card update accepts only these fields:"
                + ", ".join(updatable)
                + f"; got: {', '.join(unknown)}",
            )
        if "name" in fields and not fields["name"].strip():
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a character card needs a name",
            )
        if not fields:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a character card update needs at least one field",
            )
        assignments = []
        values: list[object] = []
        for column in _UPDATABLE_COLUMNS:
            bare = column.strip('"')
            if bare in fields:
                assignments.append(f"{column} = ?")
                values.append(fields[bare])
        assignments.append("revision = revision + 1")
        assignments.append("updated_at = ?")
        values.append(_now())
        values.append(character_id)
        with short_transaction(self._conn):
            self._require_current_epoch()
            cur = self._conn.execute(
                "UPDATE character_card SET " + ", ".join(assignments)
                + " WHERE character_id = ?",
                tuple(values),
            )
            if cur.rowcount == 0:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"no such character card: {character_id}",
                )
        return self.get(character_id)

    def delete(self, character_id: str) -> Result[None]:
        """Remove one user-authored card; the builtins are refused.

        ``AUTHORITY_VIOLATION`` for any builtin (the official family —
        the penpal and the companions seeded beside her — is not this
        store's authority to end), ``NOT_FOUND``
        for an unknown id. A user card's conversations and memories are
        **not** touched here — the conversation rows keep their persona
        binding and the relationship rows keep their pair (deleting a card
        retires the character from the roster, it does not rewrite
        history; the deeper deletion question is the BF-05 scope walk's
        business and deliberately out of this cut).
        """

        with short_transaction(self._conn):
            self._require_current_epoch()
            row = self._conn.execute(
                "SELECT is_builtin FROM character_card WHERE character_id = ?",
                (character_id,),
            ).fetchone()
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"no such character card: {character_id}",
                )
            if bool(row[0]):
                return _err(
                    DomainErrorCode.AUTHORITY_VIOLATION,
                    "the builtin character card cannot be deleted:"
                    f" {character_id}",
                )
            self._conn.execute(
                "DELETE FROM character_card WHERE character_id = ?",
                (character_id,),
            )
        return Ok(None)


class CharacterCardPackages(Mapping[str, CharacterPackageRecord]):
    """The live persona → package view the composition root injects — the
    "table first" half, **read-through**.

    A plain mapping from the outside (the coordinator's ``.get(persona_id)``
    is all it ever asks), but never a snapshot: every lookup is one SELECT
    over the card table, so a card the user creates **after** the host
    opened speaks from its very first turn, and a reworded card speaks
    reworded from the next. A persona without a row is simply absent (the
    ``KeyError`` the coordinator's fallback answers with the injected
    default package). A read that explodes raises — the same loud posture
    as every other broken read, never a guessed card.
    """

    def __init__(self, store: SqliteCharacterCardStore) -> None:
        self._store = store

    def __getitem__(self, persona_id: str) -> CharacterPackageRecord:
        read = self._store.get_by_persona(persona_id)
        if isinstance(read, Err):
            raise KeyError(persona_id)
        return card_to_package(read.value)

    def __iter__(self) -> Iterator[str]:
        listed = self._store.list_all()
        if isinstance(listed, Err):
            raise RuntimeError(
                "the character_card table could not be read:"
                f" {listed.error.message}"
            )
        return iter(record.persona_id for record in listed.value)

    def __len__(self) -> int:
        listed = self._store.list_all()
        if isinstance(listed, Err):
            raise RuntimeError(
                "the character_card table could not be read:"
                f" {listed.error.message}"
            )
        return len(listed.value)
