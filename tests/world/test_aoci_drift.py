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
of the entries in place — ``package.py`` (the version wall — then v7 —
and the
``user_character`` section), ``narrator.py`` (the ``Your character``
line and the roster's vocabulary extension), ``berrymoor.json`` (the
shipped player) and ``host.py`` (the seeded packages' mapping the
cognitive view's user layer reads) — and the pins below carry the new
faces the same way (the next touch is a red test, never a silent
ledger lie).

V3-5R (``TASK-OPI-dc1bafdf…13`` / the opening ruling
``DEC-OPI-dc1bafdf…11``) adds the terminality migration
(``0034_segment_terminality.sql``), the new cognition read face
(``cognition.py``) and re-touches three entries in place —
``settlement.py`` (the ordering law, the span arm, the persisted
terminality), ``scene.py`` (the cognition input and the ``max`` time
law) and the narrative ``store.py`` (the one-UPDATE span writer) — and
the pin below carries those faces too.

V3-6 (``TASK-OPI-dc1bafdf…23`` / the opening ruling ``…5``, re-run
``…21``) adds the gate-and-action migration
(``0035_user_gate_action.sql``), the new action face
(``action.py``) and re-touches three entries in place —
``settlement.py`` (the V3-6 interlock's two arms and the promoted
``participant_namespace_of``), ``scene.py`` (``replan_scene``) and
``deletion/types.py`` (the keep set's eighteen → twenty members) — and
the pin below carries those faces too.

V3-6R (``TASK-OPI-dc1bafdf…33`` / the opening ruling ``…31``) adds the
obligation migration (``0036_action_replan.sql``) and re-touches five
entries in place — ``action.py`` (the one-gate law, the RESOLVING-only
door, the span arm ④b and the claim/complete helpers), ``settlement.py``
(the ``outcome_ref`` arm and the targeted close), ``scene.py`` (the
obligation-keyed replan), ``director.py`` (``apply_action_replan``),
``writer.py`` (the reference pass-through), the narrative ``store.py``
(the span arm's ``close_scene`` two-caller law) and
``deletion/types.py`` (the keep set's twenty → twenty-one members) — and
the pins below carry those faces too.

V3-7 (``TASK-OPI-d274a7fb…8`` / the opening ruling ``…6``) adds the
memory-and-settlement migration
(``0037_actor_memory_chapter_settlement.sql``), the new memory face
(``memory.py``) and re-touches seven entries in place — ``settlement.py``
(the NCP-4 orchestration and the settlement read face), ``action.py``
(the ⑨ memory arm and the recovery scan's sixth family), ``scene.py``
(the memory arm on ``SceneContext``), ``director.py``
(``chapter_summaries``), ``cognition.py`` (the descent to its
compatibility role), the narrative ``store.py`` (the ``_close_chapter_tx``
arm) and ``deletion/types.py`` (the keep set's twenty-one → twenty-three
members) — and the pins below carry those faces too.
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
    "0036_action_replan.sql[",
    "0037_actor_memory_chapter_settlement.sql[",
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
    """C1-b / C1.5 / C2 / C3 / C4 / D-2: the optional beat keys, the
    reaction section, the storyline section, the voices section, the
    unconditional craft laws and the density-and-weight calibration —
    the faces the entry was missing (D-2's own words added by its
    disposition, review F4's second half: the entry's D-2段 was outside
    this pin's keyword set)."""

    entry = _entry_line("narrator.py[EW8T]")
    for keyword in (
        "effects",
        "participants",
        "state_facts",
        "== She has read the letter ==",
        "== Active storylines ==",
        "== The cast's own voices ==",
        "== The craft laws ==",
        "earn an echo",
        "development, not a mention",
        "1/2→2/3",
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


def test_package_entry_reads_v8_and_matches_the_live_constant() -> None:
    """The v8 wall (C2 → v5, C3 → v6, D-1 → v7, V3-3 → v8,
    DEC-OPI-b290799a…45 /
    DEC-OPI-a4cf2d0e…6 / …40 / TASK-OPI-bab4da9f…52): the stale v4 claim is
    gone, the v5/v6/v7/v8
    decode law rides the entry, and the number is the source's own."""

    entry = _entry_line("package.py[W14A]")
    assert "WORLD_PACKAGE_VERSION=8" in entry
    assert "v8 墙" in entry
    assert "version≠4" not in entry  # the stale claim this cut replaced
    for keyword in (
        "initial_storylines",
        "voice 可选节",
        "voice_for",
        "user_character",
        "story_role",
        "pov_eligible",
        "pov_weight",
        "long_term_drive",
        "current_arc_seed",
        "private_context",
    ):
        assert keyword in entry
    assert "WORLD_PACKAGE_VERSION = 8" in PACKAGE_SOURCE.read_text(
        encoding="utf-8"
    )


def test_berrymoor_entry_carries_the_v5_arcs_and_the_v6_voices() -> None:
    """C2's two opening arcs and C3's six-character bilingual voice
    library are the shipped package's own content — and, since D-1
    (DEC-OPI-a4cf2d0e…40), the v7 ``user_character`` section, and,
    since V3-3 (TASK-OPI-bab4da9f…52), Nell's v8 narrative profile
    six keys: the entry
    carries the reader's own declared face and the moved version wall."""

    entry = _entry_line("berrymoor.json[FQ8W]")
    for keyword in (
        "initial_storylines",
        "voice",
        "v8 墙",
        "Alder & Son",
        "Silas Croft",
        "speech_habits",
        "samples",
        "user_character",
        "actor-berrymoor-you",
        "story_role",
        "private_context",
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


def test_the_touched_entries_are_single_lines() -> None:
    """The ledger's layout law for the touched entries: one line each,
    tag at the start, no stray carriage returns — a split or duplicated
    entry is drift too (the name is count-neutral since V3-6R: the set
    grows with each re-touch).

    Review F4 (D-2 disposition): the CR check reads **raw bytes** — the
    old ``read_text`` default (universal newlines) normalized ``\\r\\n``
    away, so the assertion was vacuously true. The law pinned here is
    environment-independent: whatever the line-ending style a checkout
    carries (CRLF under ``core.autocrlf``, LF on CI), a **lone** ``\\r``
    — a classic-Mac ending or an embedded control byte — reddens this;
    the committed blob's LF form itself is git's (``.gitattributes``
    ``eol=lf``), not a working-tree fact this test could pin on both
    platforms."""

    raw = AOCI_FILE.read_bytes()
    lone_cr = raw.replace(b"\r\n", b"").count(b"\r")
    assert lone_cr == 0
    lines = _ledger_text().split("\n")
    for tag in TOUCHED_TAGS:
        assert sum(1 for line in lines if line.startswith(tag)) == 1, tag


# ---------------------------------------------------------------------------
# the disposition's widened face (review MEDIUM-1): the remaining nine
# ---------------------------------------------------------------------------


def test_deletion_entry_counts_the_global_content_tables() -> None:
    """The disposition's fixed falsehood (review MEDIUM-1, one live lie
    found by the mechanical sweep): ``GLOBAL_CONTENT_TABLES`` gained
    ``world_storyline`` at C2 — the entry's 「七员」 was false; 「八员」
    was the truth then. V3-1 (DEC-OPI-bab4da9f…11/…16, the L5 ruling)
    adds migration 0029's four narrative tables, V3-2
    (TASK-OPI-bab4da9f…29) adds migration 0030's
    ``world_bible_revision``, V3-3 (TASK-OPI-bab4da9f…52) adds
    migration 0031's two cast tables (``world_player_character`` /
    ``world_actor_profile``), V3-5 (TASK-OPI-be7b094f…34) adds
    migration 0033's three narrative-commit tables
    (``narrative_passage`` / ``reader_exposure`` / ``segment_commit``),
    V3-6 (TASK-OPI-dc1bafdf…23) adds migration 0035's two tables
    (``user_gate`` / ``user_action``) and V3-6R (TASK-OPI-dc1bafdf…33)
    migration 0036's one (``action_replan``), and V3-7
    (TASK-OPI-d274a7fb…8) adds migration 0037's two
    (``actor_memory`` / ``chapter_settlement``)
    — 「廿三员」 is the truth now, and the source constant must carry
    the same twenty-three."""

    from elc.deletion.types import GLOBAL_CONTENT_TABLES

    entry = _entry_line_in_section(
        "===D:/english-learning-clean/src/elc/deletion/===", "types.py[DD7M]"
    )
    assert "廿三员" in entry
    assert entry.count("廿三员") == 1
    assert "廿一员" not in entry
    assert "二十员" not in entry
    assert "十八员" not in entry
    assert "十五员" not in entry
    assert "十三员" not in entry
    assert "十二员" not in entry
    assert "八员" not in entry
    assert "七员" not in entry
    assert "world_storyline" in entry
    assert "world_scene_dossier" in entry
    assert "world_bible_revision" in entry
    assert "world_player_character" in entry
    assert "world_actor_profile" in entry
    assert "narrative_passage" in entry
    assert "reader_exposure" in entry
    assert "segment_commit" in entry
    assert "user_gate" in entry
    assert "user_action" in entry
    assert "action_replan" in entry
    assert "actor_memory" in entry
    assert "chapter_settlement" in entry
    assert len(GLOBAL_CONTENT_TABLES) == 23
    assert "world_storyline" in GLOBAL_CONTENT_TABLES
    assert "world_scene_dossier" in GLOBAL_CONTENT_TABLES
    assert "world_bible_revision" in GLOBAL_CONTENT_TABLES
    assert "world_player_character" in GLOBAL_CONTENT_TABLES
    assert "world_actor_profile" in GLOBAL_CONTENT_TABLES
    assert "narrative_passage" in GLOBAL_CONTENT_TABLES
    assert "reader_exposure" in GLOBAL_CONTENT_TABLES
    assert "segment_commit" in GLOBAL_CONTENT_TABLES
    assert "user_gate" in GLOBAL_CONTENT_TABLES
    assert "user_action" in GLOBAL_CONTENT_TABLES
    assert "action_replan" in GLOBAL_CONTENT_TABLES
    assert "actor_memory" in GLOBAL_CONTENT_TABLES
    assert "chapter_settlement" in GLOBAL_CONTENT_TABLES


def test_v3_5_entries_carry_the_segment_commit_faces() -> None:
    """V3-5 (TASK-OPI-be7b094f…34): the three new modules and the 0033
    migration ride their ledger entries with the faces this cut owns —
    the SEGMENT COMMIT's atomic group, the lineage read path, the
    decoupled exposure face, the scene planner's dossier chain and the
    Writer's deterministic guards. The coverage law above keeps the
    0033 entry present; this pin keeps the words true."""

    section = "\n".join(_migrations_section())
    assert "0033_segment_commit.sql[" in section
    migration_entry = _entry_line("0033_segment_commit.sql[")
    for keyword in (
        "narrative_passage",
        "reader_exposure",
        "segment_commit",
        "story_time_of",
        "settlement",
        "双 stamp '33'",
    ):
        assert keyword in migration_entry, keyword

    world_section = "===D:/english-learning-clean/src/elc/world/==="
    for tag, keywords in (
        (
            "settlement.py[",
            (
                "commit_segment",
                "record_exposure",
                "story_time_of",
                "CommitOutcome",
                "NCP-3",
            ),
        ),
        (
            "scene.py[",
            (
                "ScenePlanner",
                "open_scene",
                "SceneOpening",
                "dossier",
            ),
        ),
        (
            "writer.py[",
            (
                "PovWriter",
                "write_segment",
                "must_hide",
                "一场一 POV",
            ),
        ),
    ):
        # The section-scoped read is the ledger's own way (tags are not
        # globally unique — the N-AOCI-disp-1 mechanism fact).
        entry = _entry_line_in_section(world_section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)


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
    ``Your character`` line and the roster's vocabulary extension. The
    entry side is the binding one — renaming the entry's claim reddens
    here; the source check is an existence check (the phrase must live
    somewhere in the source), not a line-level binding: the source
    carries the phrase in rendered and teaching contexts both, so a
    silent rename of one output line alone would not be caught by this
    pin (review LOW-4 — the honest claim, narrowed)."""

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


# ---------------------------------------------------------------------------
# V3-5R (TASK-OPI-dc1bafdf…13): the terminality migration, the cognition
# read face and the three updated entries
# ---------------------------------------------------------------------------


def test_v3_5r_entries_carry_the_terminality_and_cognition_faces() -> None:
    """V3-5R's ledger faces ride their entries: the 0034 migration (the
    terminality column, the back-fill and ordering laws, its stamps),
    the new cognition read face, and the three updated entries —
    ``settlement.py`` (the ordering law, terminality, the span arm),
    ``scene.py`` (the cognition input, ``SceneContext``, the ``max``
    time law) and the narrative ``store.py`` (the one-UPDATE span
    writer). The coverage law above keeps the 0034 entry present; this
    pin keeps the words true."""

    section = "\n".join(_migrations_section())
    assert "0034_segment_terminality.sql[" in section
    migration_entry = _entry_line("0034_segment_terminality.sql[")
    for keyword in (
        "is_last_segment",
        "终态",
        "顺序",
        "回填",
        "双 stamp '34'",
    ):
        assert keyword in migration_entry, keyword

    world_section = "===D:/english-learning-clean/src/elc/world/==="
    for tag, keywords in (
        (
            "cognition.py[",
            (
                "v3_cognition_view",
                "lineage",
                "canonical",
                "public",
                "witnessed",
                "SceneContext",
            ),
        ),
        (
            "settlement.py[",
            (
                "顺序律",
                "terminality",
                "_advance_scene_actual_span_tx",
            ),
        ),
        (
            "scene.py[",
            (
                "v3_cognition_view",
                "SceneContext",
                "max(context.current_tick",
                "V3-5R",
            ),
        ),
    ):
        entry = _entry_line_in_section(world_section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)

    narrative_section = (
        "===D:/english-learning-clean/src/elc/world/narrative/==="
    )
    store_entry = _entry_line_in_section(narrative_section, "store.py[")
    for keyword in (
        "_advance_scene_actual_span_tx",
        "COALESCE",
        "commit_scene",
    ):
        assert keyword in store_entry, keyword


# ---------------------------------------------------------------------------
# V3-6 (TASK-OPI-dc1bafdf…23): the gate-and-action migration, the action
# read/write face and the three updated entries
# ---------------------------------------------------------------------------


def test_v3_6_entries_carry_the_gate_and_action_faces() -> None:
    """V3-6's ledger faces ride their entries: the 0035 migration (the
    two tables, the ``segment_commit`` rebuild, the terminal-integrity
    CHECK, the ``UNIQUE (gate_id, submission_id)`` anchor and its
    stamps), the new ``action.py`` face (NCP-1 / NCP-2, the
    ``Adjudication`` shape, the interlock, ``replan_scene`` and the
    recovery scan) and the three updated entries — ``settlement.py``
    (the V3-6 interlock and the promoted namespace face),
    ``scene.py`` (``replan_scene``) and ``deletion/types.py`` (the keep
    set's twenty members). The coverage law above keeps the 0035 entry
    present; this pin keeps the words true."""

    section = "\n".join(_migrations_section())
    assert "0035_user_gate_action.sql[" in section
    migration_entry = _entry_line("0035_user_gate_action.sql[")
    for keyword in (
        "user_gate",
        "user_action",
        "'ACTION_OUTCOME'",
        "终态完整性",
        "UNIQUE (gate_id, submission_id)",
        "双 stamp '35'",
    ):
        assert keyword in migration_entry, keyword

    world_section = "===D:/english-learning-clean/src/elc/world/==="
    for tag, keywords in (
        (
            "action.py[",
            (
                "open_gate",
                "submit_gate",
                "begin_resolving",
                "commit_action",
                "Adjudication",
                "recovery_scan",
                "NCP-1",
                "NCP-2",
            ),
        ),
        (
            "settlement.py[",
            (
                "user_gate",
                "participant_namespace_of",
                "V3-6",
            ),
        ),
        (
            "scene.py[",
            (
                "replan_scene",
                "V3-6",
            ),
        ),
    ):
        entry = _entry_line_in_section(world_section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)


# ---------------------------------------------------------------------------
# V3-6R (TASK-OPI-dc1bafdf…33): the obligation migration and the
# re-touched entries
# ---------------------------------------------------------------------------


def test_v3_6r_entries_carry_the_obligation_and_outcome_faces() -> None:
    """V3-6R's ledger faces ride their entries: the 0036 migration (the
    obligation table, the eager claim, the protocol and its stamps), the
    re-touched ``action.py`` (the one-gate law, the RESOLVING-only door
    and the claim/complete helpers), ``settlement.py`` (the
    ``outcome_ref`` arm, the forced law and the targeted close),
    ``scene.py`` (the obligation-keyed replan), ``director.py``
    (``apply_action_replan``), ``writer.py`` (the reference pass-through)
    and the narrative ``store.py`` (the span arm's ``close_scene``
    two-caller law). The coverage law above keeps the 0036 entry
    present; this pin keeps the words true."""

    section = "\n".join(_migrations_section())
    assert "0036_action_replan.sql[" in section
    migration_entry = _entry_line("0036_action_replan.sql[")
    for keyword in (
        "action_replan",
        "replan_request_id",
        "user_action",
        "('SCENE','CHAPTER')",
        "('PENDING','APPLIED')",
        "target_ref",
        "claim→work→complete",
        "recovery_scan",
        "廿一员",
        "双 stamp '36'",
    ):
        assert keyword in migration_entry, keyword

    world_section = "===D:/english-learning-clean/src/elc/world/==="
    for tag, keywords in (
        (
            "action.py[",
            (
                "claim_replan_target",
                "mark_replan_applied",
                "replan_request_id_for",
                "scene_of_action",
                "pending_replans",
                "close_scene",
                "V3-6R",
            ),
        ),
        (
            "settlement.py[",
            (
                "outcome_ref",
                "强制律",
                "定向",
                "close_scene",
                "V3-6R",
            ),
        ),
        (
            "scene.py[",
            (
                "replan_request_id",
                "claim_replan_target",
                "replan_obligation",
                "V3-6R",
            ),
        ),
        (
            "director.py[",
            (
                "apply_action_replan",
                "claim_replan_target",
                "V3-6R",
            ),
        ),
        (
            "writer.py[",
            (
                "outcome_ref",
                "V3-6R",
            ),
        ),
    ):
        entry = _entry_line_in_section(world_section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)

    narrative_section = (
        "===D:/english-learning-clean/src/elc/world/narrative/==="
    )
    store_entry = _entry_line_in_section(narrative_section, "store.py[PD9T]")
    for keyword in ("close_scene", "_advance_scene_actual_span_tx", "V3-6R"):
        assert keyword in store_entry, keyword


# ---------------------------------------------------------------------------
# V3-7 (TASK-OPI-d274a7fb…8): the memory-and-settlement migration, the new
# memory face and the re-touched entries
# ---------------------------------------------------------------------------


def test_v3_7_entries_carry_the_memory_and_settlement_faces() -> None:
    """V3-7's ledger faces ride their entries: the 0037 migration (the
    two tables, the five kind words, the memory arm, the one-version
    settlement and N-INV-004's storage face), the new ``memory.py``
    (``record_belief`` / ``v3_memory_view`` / the shared EXPERIENCED
    arm) and the re-touched entries — ``settlement.py`` (the NCP-4
    orchestration and the settlement read face), ``action.py`` (the ⑨
    memory arm and the recovery scan's sixth family), ``scene.py`` (the
    memory arm on ``SceneContext``), ``director.py``
    (``chapter_summaries``), ``cognition.py`` (the descent to its
    compatibility / fallback role) and the narrative ``store.py`` (the
    ``_close_chapter_tx`` arm). The coverage law above keeps the 0037
    entry present; this pin keeps the words true."""

    section = "\n".join(_migrations_section())
    assert "0037_actor_memory_chapter_settlement.sql[" in section
    migration_entry = _entry_line("0037_actor_memory_chapter_settlement.sql[")
    for keyword in (
        "actor_memory",
        "chapter_settlement",
        "'EXPERIENCED','HEARD','BELIEVED','INFERRED','MISTAKEN'",
        "memory_id",
        "N-INV-004",
        "21→23 员",
        "双 stamp '37'",
    ):
        assert keyword in migration_entry, keyword

    world_section = "===D:/english-learning-clean/src/elc/world/==="
    for tag, keywords in (
        (
            "memory.py[",
            (
                "MemoryKind",
                "record_belief",
                "v3_memory_view",
                "record_experienced_in_transaction",
                "EXPERIENCED",
                "叶子模块",
            ),
        ),
        (
            "settlement.py[",
            (
                "settle_chapter",
                "chapter_settlements_of",
                "NCP-4",
                "N-INV-004",
                "record_experienced_in_transaction",
                "V3-7",
            ),
        ),
        (
            "action.py[",
            (
                "settling_chapters",
                "record_experienced_in_transaction",
                "第六族",
                "V3-7",
            ),
        ),
        (
            "scene.py[",
            (
                "V3MemoryView",
                "v3_memory_view",
                "V3-7",
            ),
        ),
        (
            "director.py[",
            (
                "chapter_summaries",
                "chapter_settlements_of",
                "V3-7",
            ),
        ),
        (
            "cognition.py[",
            (
                "V3-7",
                "兼容/fallback",
            ),
        ),
    ):
        entry = _entry_line_in_section(world_section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)

    # coherence: the new face's entry and the live module carry the same
    # symbols — renaming one side alone reddens here.
    memory_source = (
        REPO / "src" / "elc" / "world" / "memory.py"
    ).read_text(encoding="utf-8")
    for symbol in (
        "class MemoryKind",
        "def record_belief",
        "def v3_memory_view",
        "def record_experienced_in_transaction",
        "def memory_id_for",
    ):
        assert symbol in memory_source, symbol

    narrative_section = (
        "===D:/english-learning-clean/src/elc/world/narrative/==="
    )
    store_entry = _entry_line_in_section(narrative_section, "store.py[PD9T]")
    for keyword in ("_close_chapter_tx", "V3-7"):
        assert keyword in store_entry, keyword


# ---------------------------------------------------------------------------
# V3-8b (TASK-OPI-06b954e0…16 / the opening ruling …15, the external
# review's 3 HIGH + 1 HARD GATE + 1 MEDIUM-HIGH): the re-touched entries
# ---------------------------------------------------------------------------


def test_v3_8b_entries_carry_the_correction_faces() -> None:
    """V3-8b's ledger faces ride their entries: the narrative
    ``store.py`` (the SETTLING precondition gate on the
    ``ACTIVE → SETTLING`` flip — HIGH-1), ``providers.py`` (the
    world-authoritative ``ResolverContext`` — HIGH-2 — and the
    ``DirectorProvider`` — HIGH-3), ``pipeline.py`` (the Director path,
    the continuation drive and the dropped ``first_segment_seq``),
    ``action.py`` (the recovery scan's seventh family) and
    ``settlement.py`` (the ``hooks`` clause — MEDIUM-HIGH). Zero
    migration: no migration entry moves, and the coverage law above
    keeps every existing one present."""

    world_section = "===D:/english-learning-clean/src/elc/world/==="
    for tag, keywords in (
        (
            "pipeline.py[PL8T]",
            (
                "DirectorProvider",
                "continuations",
                "next_segment_seq",
                "first_segment_seq",
                "V3-8b",
            ),
        ),
        (
            "providers.py[PV8T]",
            (
                "ResolverContext",
                "DirectorPlanContext",
                "DirectorProvider",
                "world-authoritative",
                "V3-8b",
            ),
        ),
        (
            "settlement.py[ST5C]",
            (
                "chapter_questions_to_advance",
                "空串",
                "V3-8b",
            ),
        ),
        (
            "action.py[AC6T]",
            (
                "ContinuationObligation",
                "action_by_id",
                "next_segment_seq",
                "V3-8b",
            ),
        ),
    ):
        entry = _entry_line_in_section(world_section, tag)
        for keyword in keywords:
            assert keyword in entry, (tag, keyword)

    narrative_section = (
        "===D:/english-learning-clean/src/elc/world/narrative/==="
    )
    store_entry = _entry_line_in_section(narrative_section, "store.py[PD9T]")
    for keyword in ("_settle_chapter_tx", "_running_story_blocker", "V3-8b"):
        assert keyword in store_entry, keyword

    # coherence: the tool-visible faces the entries name are the live
    # module's own — renaming one side alone reddens here.
    action_source = (
        REPO / "src" / "elc" / "world" / "action.py"
    ).read_text(encoding="utf-8")
    for symbol in (
        "class ContinuationObligation",
        "def action_by_id",
        "continuations: tuple[ContinuationObligation, ...]",
    ):
        assert symbol in action_source, symbol
    store_source = (
        REPO / "src" / "elc" / "world" / "narrative" / "store.py"
    ).read_text(encoding="utf-8")
    for symbol in (
        "def _settle_chapter_tx",
        "def _running_story_blocker",
    ):
        assert symbol in store_source, symbol
    providers_source = (
        REPO / "src" / "elc" / "world" / "providers.py"
    ).read_text(encoding="utf-8")
    for symbol in (
        "class ResolverContext",
        "class DirectorPlanContext",
        "class DirectorProvider",
    ):
        assert symbol in providers_source, symbol
