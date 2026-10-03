"""elc.lexicon — the offline mini-dictionary behind the word-card's
second tier (the v3-3 组合, docs/research/2026-10-02-word-coverage-findings
§3(c)/§4).

The corpus word face (``elc.web._word_lookup`` over ``content.db``'s 100
teaching-phrase lemmas) answers roughly one click in seven on real
letters; the overwhelming cause is that everyday words are simply not
teaching resources (§2.3: 82% of the miss mass is top-2000 words). This
package is the display-face answer: a pure-stdlib, zero-network dictionary
of ~1800 common English words with a minimal Chinese gloss each, plus the
~50 contraction expansions (``it's → it is``) the letters actually use,
plus ~10 naive suffix rules so ``senses`` finds ``sense``.

Discipline of this data:

- keys are the frequency-ordered common-word list this repo authored
  (top-2000 minus what cannot be glossed responsibly: single letters,
  brands, spam, bare abbreviations) — a word is here only with a gloss its
  author stands behind (the 收词纪律);
- the glosses are this repo's own writing (the frequency list is a public
  word ordering; the annotations are not copied from any source);
- this is a *dictionary* face, never a teaching card: it claims nothing
  about readiness, credit, detection or any content-side semantics —
  zero schema, zero CONTENT_DB_VERSION, zero migration.

Threading: the loader is a lazy module-level cache with no lock, because
every caller (the /api/word route and the letter hit bitmaps) runs on the
web face's single work-queue thread. Nothing here touches the network,
the filesystem beyond its own two data files, or any store.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "LexiconEntry",
    "covers",
    "entry_count",
    "lookup",
    "normalize_token",
]

#: The dictionary rows: ``word<TAB>pos<TAB>gloss`` per line. A tab is the
#: only separator, so a gloss may contain spaces and any punctuation that
#: is not a tab.
_ENTRIES_PATH = Path(__file__).with_name("entries.tsv")

#: The contraction rows: ``contraction<TAB>expansion`` per line, spelled
#: with the straight apostrophe (the lookup normalizes first).
_CONTRACTIONS_PATH = Path(__file__).with_name("contractions.tsv")

#: The naive suffix rules (the report's §3(c) list, no exception table —
#: an irregular form that survives these rules is its own dictionary key,
#: which is exactly why ``was``/``got``/``went`` ride the word list). The
#: minimum-length thresholds are the report's own (§9 acceptance口径).
_SUFFIX_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("ies", 4, ("y",)),
    ("es", 3, ("", "s")),
    ("s", 3, ("",)),
    ("ied", 4, ("y",)),
    ("ed", 3, ("", "e")),
    ("ing", 4, ("", "e")),
)


@dataclass(frozen=True)
class LexiconEntry:
    """One dictionary answer: the head word, its part of speech, the
    Chinese gloss, and the token that was actually looked up (the card
    shows the head; the matched token stays available for an honest
    ``senses → sense`` reading)."""

    head: str
    pos: str
    gloss: str
    matched: str


_entries: dict[str, tuple[str, str]] | None = None
_expansions: dict[str, tuple[str, ...]] | None = None


def _load() -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, ...]]]:
    """Read the two data files once and keep them for the process life.

    A malformed row is a broken installation, not a runtime condition:
    the loader raises rather than skipping silently (the dictionary must
    never answer with a gloss it does not have).
    """

    global _entries, _expansions
    if _entries is None or _expansions is None:
        entries: dict[str, tuple[str, str]] = {}
        for raw in _ENTRIES_PATH.read_text(encoding="utf-8").splitlines():
            if not raw:
                continue
            word, pos, gloss = raw.split("\t")
            entries[word] = (pos, gloss)
        expansions: dict[str, tuple[str, ...]] = {}
        for raw in _CONTRACTIONS_PATH.read_text(encoding="utf-8").splitlines():
            if not raw:
                continue
            contraction, phrase = raw.split("\t")
            expansions[contraction] = tuple(phrase.split())
        _entries = entries
        _expansions = expansions
    return _entries, _expansions


def normalize_token(token: str) -> str:
    """The lookup form of one token: curly apostrophe to straight, then
    casefolded (the letters use U+2019; the data uses ``'``)."""

    return token.replace("\u2019", "'").casefold()


def _suffix_candidates(token: str) -> set[str]:
    """The naive de-inflections of one token (no exception table)."""

    candidates: set[str] = set()
    for ending, minimum, replacements in _SUFFIX_RULES:
        if len(token) > minimum and token.endswith(ending):
            stem = token[: len(token) - len(ending)]
            for replacement in replacements:
                candidates.add(stem + replacement)
            if ending == "ed" and len(stem) >= 2 and stem[-1] == stem[-2]:
                candidates.add(stem[:-1])
            if ending == "ing" and len(stem) >= 2 and stem[-1] == stem[-2]:
                candidates.add(stem[:-1])
    return candidates


def _candidates(token: str) -> list[str]:
    """Every dictionary key one token could possibly be, most direct
    first: itself, then its contractions' expansion words, then the
    suffix candidates."""

    entries, expansions = _load()
    ordered: list[str] = [token]
    for word in expansions.get(token, ()):
        if word not in ordered:
            ordered.append(word)
    for word in sorted(_suffix_candidates(token)):
        if word not in ordered:
            ordered.append(word)
    return [word for word in ordered if word in entries]


def lookup(token: str | None) -> LexiconEntry | None:
    """One dictionary answer for one clicked token, or ``None``.

    The token is normalized here (the caller may pass the raw word as it
    sits in the letter). A contraction hit answers with the whole
    expansion as the head and a mechanically composed gloss (each part's
    own entry, joined — nothing is invented); a suffix hit answers with
    the base form's entry (``senses → sense``).
    """

    if token is None:
        return None
    normalized = normalize_token(str(token))
    if not normalized:
        return None
    ordered = _candidates(normalized)
    if not ordered:
        return None
    direct = normalized in ordered
    head = ordered[0]
    entries, expansions = _load()
    pos, gloss = entries[head]
    if not direct and normalized in expansions:
        phrase = expansions[normalized]
        parts = [f"{word}：{entries[word][1]}" for word in phrase if word in entries]
        if parts and len(parts) == len(phrase):
            gloss = " ／ ".join(parts)
            pos = "phr"
            head = " ".join(phrase)
    return LexiconEntry(head=head, pos=pos, gloss=gloss, matched=normalized)


def covers(token: str | None) -> bool:
    """Whether one token would get a dictionary card — the affordance
    face's cheap existence check (no entry is built)."""

    if token is None:
        return False
    normalized = normalize_token(str(token))
    return bool(normalized) and bool(_candidates(normalized))


def entry_count() -> int:
    """How many words the dictionary carries (the data face's own
    readable size, for the tests and the honest ``≥1800`` claim)."""

    entries, _ = _load()
    return len(entries)
