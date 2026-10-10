"""AOCI-CODE drift pins — the six entries the C programme left behind
stay true (the aoci catch-up cut, DEC-OPI-a4cf2d0e…30).

``aoci.code.txt`` is the repository's cognition ledger: one line per
file, the one-hop index a reader trusts when deciding what that file
is. C1-b through C4 moved live faces — the beats' ``effects`` /
``participants`` proposals, the letter-read reaction bridge, the
storyline layer, the voice library and the craft laws — without
carrying their entries along, and the 0028 migration arrived with no
entry at all. This module pins the six caught-up entries to the
strings the live source carries today: the next drift is a red test,
never a silent ledger lie.

Two kinds of pin:

* keyword pins — each entry carries the words its new faces own
  (``letter_response``, ``terminal_stop_kinds``, ``effects`` /
  ``participants``, the four narrator section headers, ``v6``, the
  ``initial_storylines`` / ``voice`` sections);
* coherence pins — where an entry quotes a live constant or a section
  header, the source file must carry the same string, so a cut that
  renames one side alone is caught.

The coverage law closes the class: every ``migrations/*.sql`` file
carries an entry in the ledger's migrations section — the 0028 case,
generalized.

D-1 (``DEC-OPI-a4cf2d0e…40``, the user-character cut) re-touches four
of the entries in place — ``package.py`` (the v7 wall and the
``user_character`` section), ``narrator.py`` (the ``Your character``
line and the roster's vocabulary extension), ``berrymoor.json`` (the
shipped player) and ``host.py`` (the seeded packages' mapping the
cognitive view's user layer reads) — and the pins below carry the new
faces the same way (the next touch is a red test, never a silent
ledger lie).
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AOCI_FILE = REPO / "aoci.code.txt"
MIGRATIONS_DIR = REPO / "migrations"
NARRATOR_SOURCE = REPO / "src" / "elc" / "world" / "narrator.py"
PACKAGE_SOURCE = REPO / "src" / "elc" / "world" / "package.py"

#: The six tags this cut caught up, each on its own line (the layout
#: law the last test re-checks).
TOUCHED_TAGS = (
    "web.py[EC8L]",
    "orchestrate.py[DB7T]",
    "narrator.py[EW8T]",
    "package.py[W14A]",
    "berrymoor.json[FQ8W]",
    "0028_world_storyline.sql[PD7T]",
)


def _ledger_text() -> str:
    return AOCI_FILE.read_text(encoding="utf-8")


def _entry_line(tag: str) -> str:
    """One entry, exactly one — a tag that vanished or split is a drift
    this module exists to catch."""

    hits = [
        line for line in _ledger_text().split("\n") if line.startswith(tag)
    ]
    assert len(hits) == 1, f"aoci entry {tag!r}: {len(hits)} lines start with it"
    return hits[0]


def _entry_line_in_section(section_header: str, tag: str) -> str:
    """One entry addressed the ledger's own way — section + tag. The
    ledger's tags are **not** globally unique (``types.py[DD7M]`` names
    four entries in four sections; the N-AOCI-disp-1 mechanism fact):
    the section header is the disambiguator the one-hop reader uses."""

    lines = _ledger_text().split("\n")
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith(section_header)
    )
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("===D:")
        ),
        len(lines),
    )
    hits = [
        line for line in lines[start + 1 : end] if line.startswith(tag)
    ]
    assert len(hits) == 1, (
        f"aoci entry {tag!r} in {section_header!r}: {len(hits)} lines"
    )
    return hits[0]


def _migrations_section() -> list[str]:
    """The ledger's migrations section: its header up to the next
    directory header."""

    lines = _ledger_text().split("\n")
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("===D:/english-learning-clean/migrations/===")
    )
    end = next(
        index
        for index in range(start + 1, len(lines))
        if lines[index].startswith("===D:")
    )
    return lines[start + 1 : end]


def test_web_entry_carries_the_letter_response_face() -> None:
    """C1.5's projection read face (DEC-OPI-b290799a…36): the per-world
    key, the defensive read and the write half are the web entry's own
    words."""

    entry = _entry_line("web.py[EC8L]")
    for keyword in (
        "letter_response",
        "_world_letter_response",
        "world_letter_response:<world_id>",
        "_record_letter_response_projection",
    ):
        assert keyword in entry


def test_orchestrate_entry_carries_the_bridge_and_the_terminal_stop() -> None:
    """C1.5 / C2 / C1-aR v2 (DEC-OPI-b290799a…36 / …45 / …9): the step's
    two pass-through faces, the RESPONSE-word run terminalization and
    the caller's trigger backfill."""

    entry = _entry_line("orchestrate.py[DB7T]")
    for keyword in (
        "letter_response",
        "active_storylines",
        "terminal_stop_kinds",
        "letter_arrives",
        "awaits_you",
        "terminalize_run",
        "adopt_trigger_turn",
    ):
        assert keyword in entry


def test_narrator_entry_carries_the_five_prompt_faces() -> None:
    """C1-b / C1.5 / C2 / C3 / C4: the optional beat keys, the reaction
    section, the storyline section, the voices section and the
    unconditional craft laws — the five faces the entry was missing."""

    entry = _entry_line("narrator.py[EW8T]")
    for keyword in (
        "effects",
        "participants",
        "state_facts",
        "== She has read the letter ==",
        "== Active storylines ==",
        "== The cast's own voices ==",
        "== The craft laws ==",
    ):
        assert keyword in entry


def test_narrator_entry_headers_match_the_live_source() -> None:
    """Coherence: the four section headers the entry quotes are the
    source's own strings — renaming one side alone reddens this."""

    entry = _entry_line("narrator.py[EW8T]")
    source = NARRATOR_SOURCE.read_text(encoding="utf-8")
    for header in (
        "== She has read the letter ==",
        "== Active storylines ==",
        "== The cast's own voices ==",
        "== The craft laws ==",
    ):
        assert header in entry
        assert header in source


def test_package_entry_reads_v7_and_matches_the_live_constant() -> None:
    """The v7 wall (C2 → v5, C3 → v6, D-1 → v7, DEC-OPI-b290799a…45 /
    DEC-OPI-a4cf2d0e…6 / …40): the stale v4 claim is gone, the v5/v6/v7
    decode law rides the entry, and the number is the source's own."""

    entry = _entry_line("package.py[W14A]")
    assert "WORLD_PACKAGE_VERSION=7" in entry
    assert "v7 墙" in entry
    assert "version≠4" not in entry  # the stale claim this cut replaced
    for keyword in (
        "initial_storylines",
        "voice 可选节",
        "voice_for",
        "user_character",
    ):
        assert keyword in entry
    assert "WORLD_PACKAGE_VERSION = 7" in PACKAGE_SOURCE.read_text(
        encoding="utf-8"
    )


def test_berrymoor_entry_carries_the_v5_arcs_and_the_v6_voices() -> None:
    """C2's two opening arcs and C3's six-character bilingual voice
    library are the shipped package's own content — and, since D-1
    (DEC-OPI-a4cf2d0e…40), the v7 ``user_character`` section: the entry
    carries the reader's own declared face and the moved version wall."""

    entry = _entry_line("berrymoor.json[FQ8W]")
    for keyword in (
        "initial_storylines",
        "voice",
        "v7 墙",
        "Alder & Son",
        "Silas Croft",
        "speech_habits",
        "samples",
        "user_character",
        "actor-berrymoor-you",
    ):
        assert keyword in entry


def test_the_storyline_migration_carries_its_entry() -> None:
    """0028 (C2, DEC-OPI-b290799a…45): the migration arrived without an
    entry — the debt this cut closes; its shape stays pinned too."""

    entry = _entry_line("0028_world_storyline.sql[PD7T]")
    assert entry in _migrations_section()
    for keyword in (
        "world_storyline",
        "opened_by",
        "('active','resolved','settled')",
        "resolve_at",
        "双 stamp '28'",
    ):
        assert keyword in entry


def test_every_migration_file_carries_a_ledger_entry() -> None:
    """The coverage law, generalized from the 0028 case: a migration
    with no entry is exactly the drift the entry debt left."""

    section = "\n".join(_migrations_section())
    files = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert len(files) > 0, "the migrations directory is empty — wrong path"
    for name in files:
        assert f"{name}[" in section, f"migration {name!r} has no ledger entry"


def test_the_six_touched_entries_are_single_lines() -> None:
    """The ledger's layout law for the touched entries: one line each,
    tag at the start, no carriage returns — a split or duplicated
    entry is drift too."""

    assert "\r" not in _ledger_text()
    lines = _ledger_text().split("\n")
    for tag in TOUCHED_TAGS:
        assert sum(1 for line in lines if line.startswith(tag)) == 1, tag


# ---------------------------------------------------------------------------
# the disposition's widened face (review MEDIUM-1): the remaining nine
# ---------------------------------------------------------------------------


def test_deletion_entry_counts_eight_global_content_tables() -> None:
    """The disposition's fixed falsehood (review MEDIUM-1, one live lie
    found by the mechanical sweep): ``GLOBAL_CONTENT_TABLES`` gained
    ``world_storyline`` at C2 — the entry's 「七员」 was false; 「八员」
    is the truth, and the source constant must carry the same eight."""

    from elc.deletion.types import GLOBAL_CONTENT_TABLES

    entry = _entry_line_in_section(
        "===D:/english-learning-clean/src/elc/deletion/===", "types.py[DD7M]"
    )
    assert "八员" in entry
    assert "七员" not in entry
    assert "world_storyline" in entry
    assert len(GLOBAL_CONTENT_TABLES) == 8
    assert "world_storyline" in GLOBAL_CONTENT_TABLES


def test_the_widened_entries_carry_the_voice_face() -> None:
    """The disposition's widened entries: the C3 voice library's wiring
    chain (host port → coordinator → compiler block → context view) and
    the C2 storyline faces ride their entries — and the leaf module has
    an entry of its own."""

    _ELC = "===D:/english-learning-clean/src/elc/==="
    _PERSONA = "===D:/english-learning-clean/src/elc/persona/==="
    _RUNTIME = "===D:/english-learning-clean/src/elc/runtime/==="
    _WORLD = "===D:/english-learning-clean/src/elc/world/==="
    for section, tag, keywords in (
        (_ELC, "host.py[AW9L]", ("_WorldVoicePort",)),
        (_PERSONA, "commands.py[DB9L]", ("persona-voice",)),
        (_PERSONA, "types.py[DB7L]", ("world_voice_view",)),
        (_RUNTIME, "controller.py[AC9L]", ("world_voice",)),
        (_WORLD, "__init__.py[DC4T]", ("voice", "剧情线")),
        (_WORLD, "types.py[DC4T]", ("STORYLINE_EFFECT_KEY_PREFIX",)),
        (
            _WORLD,
            "store.py[DB7T]",
            ("active_storylines", "resolve_storyline", "adopt_trigger_turn"),
        ),
    ):
        entry = _entry_line_in_section(section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)

    # D-1 (DEC-OPI-a4cf2d0e…40): the world package's own banner carries
    # the user-character face (the ``__init__`` entry above is pinned
    # for voice/剧情线; the reader's-own-character cut rides it too).
    banner = _entry_line_in_section(_WORLD, "__init__.py[DC4T]")
    for keyword in ("UserCharacter", "user_character"):
        assert keyword in banner, keyword

    # the leaf module's own entry (the one file the sweep found with no
    # entry at all)
    voice_entry = _entry_line_in_section(_WORLD, "voice.py[EW9T]")
    for keyword in ("CharacterVoice", "WorldVoiceQueries", "VOICE_SAMPLE_COUNT"):
        assert keyword in voice_entry


# ---------------------------------------------------------------------------
# D-1 (DEC-OPI-a4cf2d0e…40): the user-character cut's own four entries
# ---------------------------------------------------------------------------


def test_narrator_entry_carries_the_user_character_line() -> None:
    """D-1's narrator face rides its entry: the conditional
    ``Your character`` line and the roster's vocabulary extension — and
    the entry's quoted string is the source's own (rename one side alone
    and this reddens)."""

    entry = _entry_line("narrator.py[EW8T]")
    assert "Your character" in entry
    assert "user_character" in entry
    source = NARRATOR_SOURCE.read_text(encoding="utf-8")
    assert "Your character" in source
    assert "user_character" in source


def test_host_entry_carries_the_cognitive_views_user_layer() -> None:
    """D-1's assembly face rides the host entry: the seeded packages'
    ``user_character`` mapping the chronicle port's fourth filter arm
    reads, and the source keeps the same symbols."""

    entry = _entry_line("host.py[AW9L]")
    assert "user_character" in entry
    assert "world_user_characters" in entry
    source = (REPO / "src" / "elc" / "host.py").read_text(encoding="utf-8")
    assert "world_user_characters" in source
    assert "_user_character_ids" in source
