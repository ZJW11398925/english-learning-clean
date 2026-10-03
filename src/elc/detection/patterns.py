"""Shared text primitives for the D-3 pilot matchers.

The thirty-six pilot matchers read the learner production's plain text with
regular expressions and small word tables. This module holds only the
primitives those matchers share, each named for the rule family it
serves; the entity-specific matchers live in :mod:`elc.detection.pilot`.
Everything here is a pure text reader — no model, no I/O, no state.

- The **fronted-marker** families (any way / move on / I forget / not way
  / enough fair / fairly enough / I saw / I am seeing / get it) anchor
  the slip at the front of the turn: the marker stands where a turn
  opener belongs, so the same words mid-clause are the ordinary grammar
  and must not fire (:func:`fronted_then`, :func:`opens_with_pause`).
- The **comma-after-hedge** family (I think, + clause) excludes a
  connector after the comma — there the comma marks an ordinary clause
  boundary, not a split hedge — through :data:`CONNECTOR_WORDS`.
- The **subjectless-hedge** family (Think we should...) tells the hedge
  from the imperative (Think about it) through :data:`THINK_PREPOSITIONS`
  and asks for a complement-clause subject through :data:`SUBJECT_WORDS`.
- The **hedge-placement** family (It I guess will rain) asks for a finite
  verb after the misplaced hedge through :data:`FINITE_AUX_WORDS`.
- The **agreement and echo** families (Moving on the next topic...; She
  actually move...; that make sense) read determiners and third-person
  subjects through :data:`DETERMINER_WORDS` and
  :data:`THIRD_PERSON_SUBJECTS`.
"""

from __future__ import annotations

import re

#: Words that can open the complement clause a dropped-subject hedge
#: needs (subject pronouns and determiners). "Think we should leave"
#: qualifies; "Think positive!" does not.
SUBJECT_WORDS: frozenset[str] = frozenset({
    "i", "you", "he", "she", "it", "we", "they",
    "this", "that", "these", "those", "there",
    "a", "an", "the", "my", "your", "his", "her", "its", "our", "their",
})

#: Conjunctive adverbs and coordinating conjunctions. A comma followed by
#: one of these marks an ordinary clause boundary ("I think, therefore I
#: am"), so the comma-after-hedge family must not fire.
CONNECTOR_WORDS: frozenset[str] = frozenset({
    "therefore", "however", "thus", "hence", "moreover", "instead",
    "otherwise", "nevertheless",
    "and", "but", "or", "so", "yet", "nor", "for",
})

#: The objects the imperative "think" idiom takes ("Think about it",
#: "think twice"). "Think" followed by one of these is a command, not the
#: dropped-subject hedge.
THINK_PREPOSITIONS: frozenset[str] = frozenset({
    "about", "of", "over", "through", "twice", "back", "ahead",
})

#: The finite auxiliaries and modals that can carry the clause a hedge
#: splits ("It I guess will rain"). "I guess" followed by one of these
#: stands between the subject and its finite verb.
FINITE_AUX_WORDS: frozenset[str] = frozenset({
    "will", "would", "shall", "should", "can", "could", "may", "might",
    "must", "is", "are", "was", "were", "am", "has", "have", "had",
    "does", "do", "did",
})

#: Determiners that can open the next item named after the moving-on
#: signpost ("Moving on the agenda is the budget").
DETERMINER_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "this", "that", "these", "those",
    "my", "your", "his", "her", "its", "our", "their",
})

#: The third-person singular subjects whose bare verb form betrays the
#: agreement drop ("She actually move to Lisbon?").
THIRD_PERSON_SUBJECTS: frozenset[str] = frozenset({"she", "he", "it"})

_WORD = re.compile(r"[a-z']+")
_PAUSE_CHARS = ",;:\u2014\u2013-"


def tokens(text: str) -> list[str]:
    """Lowercase word tokens, apostrophes kept ("let's", "didn't")."""

    return _WORD.findall(text.lower())


def fronted_then(text: str, phrase: str) -> str | None:
    """The rest of the turn after a **fronted** ``phrase``, else ``None``.

    Fronted = the turn opens with the phrase: leading whitespace and
    letter case are ignored and the phrase is word-bounded (so "any way"
    never matches inside "any ways"). The fronted-marker families read
    the slip here; the same words mid-clause are the ordinary grammar
    and answer ``None``.
    """

    match = re.match(rf"\s*{re.escape(phrase)}\b", text, re.IGNORECASE)
    return text[match.end():] if match is not None else None


def opens_with_pause(text: str) -> bool:
    """Does ``text`` open (after whitespace) with a pause mark — comma,
    semicolon, colon or dash? The receipt and signpost families read the
    pause as the boundary between the marker and the matter that follows
    ("Any way, ..."; "I forget, ...")."""

    stripped = text.lstrip()
    return bool(stripped) and stripped[0] in _PAUSE_CHARS


def contains_phrase(text: str, phrase: str) -> bool:
    """Word-bounded, case-insensitive containment ("before to forget")."""

    return re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE) is not None


def first_word(text: str) -> str | None:
    """The first word token of ``text`` (leading punctuation skipped),
    or ``None`` when the text carries no words."""

    found = _WORD.search(text)
    return found.group(0) if found is not None else None
