"""v3-d — the lexicon second tier, the hit bitmap and the cleanup faces.

The word-coverage findings (docs/research/2026-10-02-word-coverage-
findings.md) measured the word-card click hit rate on real dogfood
letters at 14.5% and prescribed the v3-3 组合: an offline mini-dictionary
behind the corpus miss (§3(c)), the curly-apostrophe normalization, a
visibly-second-tier card, and the affordance layering (§3(b) — the
bitmap rides the letter payloads, a 0 word renders without the clickable
style, so "miss silence" becomes "no affordance"). This suite pins the
whole construction:

1. the dictionary data face (size, glosses, contractions, suffix rules);
2. the lookup second tier over the real built artifact (single-token
   windows only — the "make senses" boundary survives untouched; the
   corpus face wins whenever it answers);
3. the hit bitmap (paragraph mirror, spot truths, the no-content-leg
   honest None);
4. the favicon face (same-origin /favicon.ico, inline SVG, the webui
   source still free of every URI scheme);
5. the served front-end source pins (word--off gating, the lexicon card
   branch, the CLOSED 读法, the wiring on the three payload faces).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc import lexicon
from elc.content.build import build_content_db
from elc.content.store import open_read_only
from elc.web import _FAVICON_SVG, _letter_hit_rows, _word_lookup

_WEBUI = Path(__file__).resolve().parents[2] / "src" / "elc" / "webui"


@pytest.fixture(scope="module")
def built_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("v3d-lexicon") / "content.db"
    build_content_db(path)
    return path


@pytest.fixture(scope="module")
def word_conn(built_content_db: Path) -> sqlite3.Connection:
    conn = open_read_only(built_content_db)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. the dictionary data face
# ---------------------------------------------------------------------------


def test_the_dictionary_carries_at_least_1800_glossed_words() -> None:
    """The 收词纪律's floor: only words a gloss stands behind, but no
    fewer than the report's §3(c) shape needs (top-2000 minus the
    irresponsible ~119)."""

    assert lexicon.entry_count() >= 1800


def test_the_contraction_table_carries_at_least_40_entries() -> None:
    """The report named ~40 (it's → it is 级); the shipped table rides
    50, every one a two-part tab row with a straight apostrophe."""

    rows = [
        line.split("\t")
        for line in lexicon._CONTRACTIONS_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    assert len(rows) >= 40
    for contraction, phrase in rows:
        assert "'" in contraction
        assert "’" not in contraction
        assert phrase == phrase.lower()


def test_lookup_normalizes_the_curly_apostrophe() -> None:
    """The letters write U+2019; the data writes ' — one normalization
    meets them (the v3-3 组合第 3 件)."""

    straight = lexicon.lookup("it's")
    curly = lexicon.lookup("it’s")
    assert straight is not None and curly is not None
    assert straight.head == curly.head == "it is"
    assert straight.matched == curly.matched == "it's"


def test_lookup_de_inflects_through_the_suffix_rules() -> None:
    entry = lexicon.lookup("senses")
    assert entry is not None
    assert (entry.head, entry.matched) == ("sense", "senses")
    entry = lexicon.lookup("carried")
    assert entry is not None and entry.head == "carry"


def test_lookup_answers_none_for_what_it_does_not_carry() -> None:
    """Proper nouns and scaffolding stay out (the honest miss — the
    affordance face renders them dead instead)."""

    assert lexicon.lookup("lisbon") is None
    assert lexicon.lookup("") is None
    assert lexicon.lookup(None) is None
    assert not lexicon.covers("lisbon")


def test_covers_agrees_with_lookup_on_the_real_faces() -> None:
    for token in ("please", "the", "it’s", "senses", "qqqqzh"):
        entry = lexicon.lookup(token)
        assert lexicon.covers(token) is (entry is not None), token


# ---------------------------------------------------------------------------
# 2. the lookup second tier (the real artifact)
# ---------------------------------------------------------------------------


def test_a_corpus_hit_still_answers_first_with_its_own_source(
    word_conn: sqlite3.Connection,
) -> None:
    """语料面信息量优先: "anyway" is both a corpus lemma and a dictionary
    word — the corpus card wins and says so."""

    answer = _word_lookup(word_conn, "anyway")
    assert answer["found"] is True
    assert answer["source"] == "corpus"
    assert answer["entity_id"]


def test_a_single_token_corpus_miss_falls_to_the_dictionary(
    word_conn: sqlite3.Connection,
) -> None:
    answer = _word_lookup(word_conn, "please")
    assert answer["found"] is True
    assert answer["source"] == "lexicon"
    assert answer["lemma"] == "please"
    assert answer["gloss"]
    assert "entity_id" not in answer  # a dictionary card, never a teaching card


def test_the_multi_token_miss_stays_a_miss(word_conn: sqlite3.Connection) -> None:
    """The boundary the report §5.1 pinned: the dictionary never
    participates in phrase matching — "make senses" is a phrase-shaped
    query and must keep missing as a whole."""

    answer = _word_lookup(word_conn, "make senses")
    assert answer == {"found": False}


def test_word_tokens_normalize_the_curly_apostrophe() -> None:
    """The web face's own normalization (defense in depth beside the
    lexicon's): the helper must emit the straight-apostrophe token —
    a mutation that drops the replace is caught here, not masked by the
    dictionary's self-normalization."""

    from elc.web import _word_tokens

    assert _word_tokens("it’s") == ["it's"]
    assert _word_tokens("IT’S") == ["it's"]


def test_the_curly_apostrophe_reaches_the_dictionary_tier(
    word_conn: sqlite3.Connection,
) -> None:
    """The dogfood letters' 32 curly contractions: "it’s" now opens the
    expansion card instead of silently missing."""

    answer = _word_lookup(word_conn, "it’s")
    assert answer["found"] is True
    assert answer["source"] == "lexicon"
    assert answer["lemma"] == "it is"


# ---------------------------------------------------------------------------
# 3. the hit bitmap
# ---------------------------------------------------------------------------

_LEMMA_RUNS = None


def _runs(built_content_db: Path) -> tuple[list[str], ...]:
    global _LEMMA_RUNS
    if _LEMMA_RUNS is None:
        conn = open_read_only(built_content_db)
        try:
            from elc.web import _word_tokens

            _LEMMA_RUNS = tuple(
                _word_tokens(str(lemma))
                for (lemma,) in conn.execute(
                    "SELECT lemma FROM content_lexical_entry"
                )
            )
        finally:
            conn.close()
    return _LEMMA_RUNS


def test_the_bitmap_mirrors_the_page_paragraph_split(
    built_content_db: Path,
) -> None:
    text = "Dear friend,\n\nPlease make a decision soon.\n\nTake care,\nNell"
    rows = _letter_hit_rows(text, _runs(built_content_db))
    assert rows is not None
    from elc.web import _letter_paragraphs

    assert len(rows) == len(_letter_paragraphs(text))
    for row, paragraph in zip(rows, _letter_paragraphs(text)):
        assert len(row) == len(paragraph.split())


def test_the_bitmap_spot_truths(built_content_db: Path) -> None:
    """please = dictionary hit (1); decision inside "make a decision" =
    corpus window hit (1); Lisbon = proper noun (0); the scaffold token
    stays dead (0)."""

    rows = _letter_hit_rows(
        "Please make a decision, Lisbon.", _runs(built_content_db)
    )
    assert rows is not None
    row = rows[0]
    words = "Please make a decision, Lisbon.".split()
    marks = dict(zip(words, row))
    assert marks["Please"] == 1
    assert marks["make"] == 1
    assert marks["decision,"] == 1
    assert marks["Lisbon."] == 0


def test_a_letter_without_a_word_list_answers_none() -> None:
    """The honest shape: no content leg → no bitmap → every word keeps
    today's full affordance (never a fabricated wall of dead words)."""

    assert _letter_hit_rows("Any text at all", None) is None


# ---------------------------------------------------------------------------
# 4. the favicon face
# ---------------------------------------------------------------------------


def test_the_favicon_constant_is_the_inline_envelope_svg() -> None:
    assert _FAVICON_SVG.startswith("<svg ")
    assert 'viewBox="0 0 32 32"' in _FAVICON_SVG
    assert 'stroke="#191b1e"' in _FAVICON_SVG  # the ink line
    assert 'fill="#efe9dc"' in _FAVICON_SVG  # the paper tone


def test_the_page_declares_the_same_origin_icon_only() -> None:
    index = (_WEBUI / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" href="/favicon.ico">' in index
    # the zero-external law, restated at the favicon's face: the webui
    # source carries no scheme and no data URI (the namespace string
    # lives on the Python side, in _FAVICON_SVG).
    assert "http://" not in index
    assert "data:" not in index


# ---------------------------------------------------------------------------
# 5. the served front-end source pins
# ---------------------------------------------------------------------------


def test_the_dead_word_style_and_click_gate_are_in_place() -> None:
    js = (_WEBUI / "components.js").read_text(encoding="utf-8")
    app = (_WEBUI / "app.js").read_text(encoding="utf-8")
    css = (_WEBUI / "components.css").read_text(encoding="utf-8")
    # the sharding call names the dead class exactly once per word span
    assert 'hits && hits[counter.index] === 0 ? "word word--off" : "word";' in js
    # the click delegate short-circuits a dead word (呈现与行为一致)
    assert 'if (target.classList.contains("word--off")) return;' in app
    # the post-send letter gets its bitmap applied when the turn lands
    assert "applyLetterAffordance(mine, data.user_word_hits || null);" in app
    # history renders both sides through the payload bitmaps
    assert 'addLine("user", turn.user, { hits: turn.user_word_hits || null });' in app
    assert (
        'addLine("assistant", turn.assistant, { hits: turn.word_hits || null });'
        in app
    )
    # the neutralizers: no cursor, no hover, no press, no tint
    assert ".word--off { cursor: auto; }" in css
    assert ".word--off:active { background-color: transparent; }" in css


def test_the_lexicon_card_is_a_visibly_second_tier() -> None:
    js = (_WEBUI / "components.js").read_text(encoding="utf-8")
    css = (_WEBUI / "components.css").read_text(encoding="utf-8")
    assert 'if (data.source === "lexicon") {' in js
    assert 'src.textContent = "词典";' in js
    assert 'src.className = "wc-src";' in js
    assert ".wc-src {" in css
    # the corpus card's own source word rides the response
    assert '"source": "corpus"' in (
        Path(__file__).resolve().parents[2] / "src" / "elc" / "web.py"
    ).read_text(encoding="utf-8")


def test_the_closed_lifecycle_reads_已收场() -> None:
    js = (_WEBUI / "components.js").read_text(encoding="utf-8")
    assert 'CLOSED: "已收场",' in js
