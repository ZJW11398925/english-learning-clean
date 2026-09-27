"""The D-3 pilot detector set — the first twelve real matchers.

Twelve ``EDITOR_REVIEWED`` R4 targets are verified executable: each
matcher implements its entity's declared detection-rule prose (the rule
ordinals are named in the matcher's docstring) with anchors, word tables
and exclusion lists from :mod:`elc.detection.patterns`, so a sentence
built on the same pattern with different words is judged identically.
The fixtures under ``content_src/evidence/`` are the verification set,
never the implementation — no matcher compares against a fixture
sentence.

Registration goes through :func:`register_pilot`, called by an
assembling build entry point (the CLI, ``elc.content.build.main``): the
library default (:data:`elc.detection.GLOBAL_REGISTRY` at import time)
stays empty, so a default build still derives zero
``EXECUTABLY_VERIFIED`` rows.
"""

from __future__ import annotations

import re

from elc.detection.patterns import (
    CONNECTOR_WORDS,
    DETERMINER_WORDS,
    FINITE_AUX_WORDS,
    SUBJECT_WORDS,
    THINK_PREPOSITIONS,
    THIRD_PERSON_SUBJECTS,
    contains_phrase,
    first_word,
    fronted_then,
    opens_with_pause,
    tokens,
)
from elc.detection.registry import DetectorRegistry
from elc.detection.types import DetectionMatch, Matcher

#: The pilot detector set's semantic version — D-5R's verifier identity. The
#: word names **the matcher implementation set**, not the corpus: a change to
#: any matcher's behaviour (its pattern, its word tables, its exclusion list)
#: must bump this constant, because the verification profile the build writes
#: (``content_verification_profile.pilot_version``, D-5R) records exactly this
#: word as the "who verified" fact a provenance row cannot carry. A fixture
#: or corpus change does not bump it — the fixture-set half of the profile's
#: digests moves on its own — but a matcher change with a stale version would
#: make two different detector sets claim the same identity. The initial
#: value names the cut that landed the twelve (D-3), which is the set this
#: module still is.
PILOT_VERSION = "d3-pilot-1"

#: The pilot roster, sorted: twelve EDITOR_REVIEWED R4 targets whose
#: declared fixtures the matchers below must pass in full.
PILOT_ENTITIES: tuple[str, ...] = (
    "res-discourse-anyway",
    "res-discourse-before-i-forget",
    "res-discourse-moving-on",
    "res-hedge-i-guess",
    "res-hedge-i-think",
    "res-hedge-more-or-less",
    "res-pragmatic-come-again",
    "res-pragmatic-fair-enough",
    "res-pragmatic-got-it",
    "res-pragmatic-i-see",
    "res-pragmatic-no-way",
    "res-pragmatic-that-makes-sense",
)

_BE_BEFORE_GOT_IT = re.compile(
    r"\b(?:am|is|are|was|were|'m|'re)\s+got\s+it\b", re.IGNORECASE
)
_HEDGE_MISPLACED = re.compile(
    r"\b(?:he|she|it|this|that)\s+i\s+guess\s+([a-z']+)", re.IGNORECASE
)
_GUESS_BE_FORM = re.compile(r"\bi(?:'m|\s+am)\s+guess\b", re.IGNORECASE)
_GUESS_BARE_PARTICIPLE = re.compile(r"\bi\s+guessing\b", re.IGNORECASE)
_SAY_PREP_HOUR = re.compile(
    r"\b(?:say|said)\s+(?:at|on)\s+([a-z]+)\b", re.IGNORECASE
)
_ECHO_ADVERBS = (
    r"(?:(?:actually|really|just|finally|already|seriously"
    r"|honestly|literally)\s+)?"
)
_ECHO_BARE_VERB = re.compile(
    rf"\b(?:{'|'.join(sorted(THIRD_PERSON_SUBJECTS))})"
    rf"\s+{_ECHO_ADVERBS}([a-z]+)\b",
    re.IGNORECASE,
)
_RECEIPT_OPENERS = r"(?:(?:right|okay|ok|well|sure)\s*[,.!]?\s*)?"
_BARE_MAKE_SENSE = re.compile(
    rf"^\s*{_RECEIPT_OPENERS}that\s+make\s+sense\b", re.IGNORECASE
)
_THOSE_MAKES_SENSE = re.compile(r"\bthose\s+makes\s+sense\b", re.IGNORECASE)
_BARE_AFTER_PAIR = re.compile(
    r"\bmore\s+or\s+less\s+([a-z]+)\b", re.IGNORECASE
)
_REVERSED_PAIR = re.compile(
    r"\b(?:is|are|was|were|'s|'re)\s+less\s+or\s+more\b", re.IGNORECASE
)

#: Adverbs that may sit between "didn't" and the double-marked verb
#: ("didn't quite catched"); beyond one of these the scan stops, so
#: ordinary complements ("didn't say I needed") never reach a
#: past-marked word.
_DIDNT_ADVERBS: frozenset[str] = frozenset({
    "quite", "really", "even", "just", "almost", "nearly", "exactly",
    "actually", "hardly", "barely", "already", "simply", "totally",
    "completely", "honestly", "seriously",
})

#: Bare verbs that already end in -ed ("didn't need", "didn't speed") —
#: correct English, never a double marking.
_BARE_ED_FORMS: frozenset[str] = frozenset({
    "need", "speed", "seed", "weed", "breed", "exceed", "proceed",
    "succeed", "indeed",
})

#: The hour words a bare clock time can open with ("four thirty").
_CLOCK_HOURS: frozenset[str] = frozenset({
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve",
})

#: The bare verb forms the echoed news can lose its -s on ("She actually
#: move to Lisbon?"); a past form ("moved") never matches a bare entry.
_BARE_ECHO_VERBS: frozenset[str] = frozenset({
    "move", "go", "come", "run", "win", "lose", "finish", "graduate",
    "retire", "quit", "get", "adopt", "sell", "buy", "cook", "pass",
    "make", "take", "drive", "swim", "sing", "dance", "write", "publish",
    "break", "fix", "marry", "bring", "choose", "fly", "grow", "wake",
    "rise", "fall", "speak", "spend",
})

#: The bare verbs the more-or-less frame can wrongly lower ("is more or
#: less finish"); the participles and adjectives the frame really holds
#: ("complete", "done") are deliberately absent.
_BARE_PAIR_TARGETS: frozenset[str] = frozenset({
    "finish", "end", "stop", "start", "begin", "arrive", "leave", "move",
    "decide", "agree", "deliver", "submit", "prepare", "fix", "build",
    "pay", "sign", "review", "send",
})

#: The proposal openers the move-on signpost fronts its clause with.
_PROPOSAL_OPENERS: frozenset[str] = frozenset({"let's", "let", "we"})


def detect_anyway(text: str) -> DetectionMatch | None:
    """res-discourse-anyway, rule ordinal 0 (SPLIT_SPELLING).

    Matches the two-word sequence "any way" fronted as the marker with a
    pause after it ("Any way, the course starts soon"). The noun-phrase
    use ("Is there any way to fix this?") is mid-clause, so the fronted
    anchor refuses it; the one-word marker ("Anyway, ...") is spelled
    differently and never fires.
    """

    rest = fronted_then(text, "any way")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("SPLIT_SPELLING")
    return None


def detect_got_it(text: str) -> DetectionMatch | None:
    """res-pragmatic-got-it, rule ordinals 0 (BASE_FORM_RECEIPT) and
    1 (COPULA_INTRUSION).

    Ordinal 0: the base form "get it" fronted as the receipt with a
    pause after it ("Get it, I will call you tomorrow") — the
    correct past receipt ("Got it.") and the owned clause ("I get it,
    ...") never open the turn with the base form. Ordinal 1: a form of
    be directly before "got it" ("I am got it"). The ambiguous
    contraction "'s" is excluded on purpose ("she's got it" reads as the
    accepted "has got").
    """

    rest = fronted_then(text, "get it")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("FORM_SLIP")
    if _BE_BEFORE_GOT_IT.search(text) is not None:
        return DetectionMatch("AUXILIARY_INTRUSION")
    return None


def detect_i_think(text: str) -> DetectionMatch | None:
    """res-hedge-i-think, rule ordinals 0 (SUBJECTLESS_HEDGE) and
    1 (COMMA_AFTER_HEDGE).

    Ordinal 0: "think"/"thought" opens the turn with no subject and a
    complement-clause subject follows ("Think we should leave
    earlier"); the imperative ("Think about it") is refused by the
    THINK_PREPOSITIONS table and by demanding a subject word.
    Ordinal 1: "I think," followed by a clause and no connector
    ("I think, the rent was already paid"); a connector after the comma
    ("I think, therefore I am") marks an ordinary clause
    boundary and is refused by CONNECTOR_WORDS.
    """

    for verb in ("think", "thought"):
        rest = fronted_then(text, verb)
        if rest is not None:
            head = first_word(rest)
            if (
                head is not None
                and head not in THINK_PREPOSITIONS
                and head in SUBJECT_WORDS
            ):
                return DetectionMatch("SUBJECT_OMISSION")
    after = re.search(r"\bi\s+think\s*,\s*([a-z']+)", text, re.IGNORECASE)
    if after is not None and after.group(1) not in CONNECTOR_WORDS:
        return DetectionMatch("COMMA_INTRUSION")
    return None


def detect_before_i_forget(text: str) -> DetectionMatch | None:
    """res-discourse-before-i-forget, rule ordinals 0
    (INFINITIVE_AFTER_PREPOSITION) and 1 (FRAME_TRUNCATION).

    Ordinal 0: the to-infinitive built after the preposition ("Before to
    forget, ..."). Ordinal 1: the turn opens with the frame cut back to
    "I forget" plus a pause ("I forget, the invoice is due") —
    the real time clause ("before I forget to remind you") is mid-clause
    and unpunctuated at the front, so the anchor refuses it.
    """

    if contains_phrase(text, "before to forget"):
        return DetectionMatch("INFINITIVE_AFTER_PREPOSITION")
    rest = fronted_then(text, "i forget")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("FRAME_TRUNCATION")
    return None


def detect_moving_on(text: str) -> DetectionMatch | None:
    """res-discourse-moving-on, rule ordinals 0 (FORM_SLIP) and
    1 (MISSING_COMMA).

    Ordinal 0: the base form "move on" fronted with a pause and a
    proposal opener ("Move on, let's check the budget"); the gerund
    ("Moving on, ...") never opens with the base form. Ordinal 1: the
    gerund fronted with no pause running straight into a determiner
    ("Moving on the agenda is the budget"); the extended "moving on
    to" form is refused by the determiner requirement.
    """

    rest = fronted_then(text, "move on")
    if rest is not None and opens_with_pause(rest):
        if first_word(rest) in _PROPOSAL_OPENERS:
            return DetectionMatch("FORM_SLIP")
    rest = fronted_then(text, "moving on")
    if rest is not None and not opens_with_pause(rest):
        if first_word(rest) in DETERMINER_WORDS:
            return DetectionMatch("MISSING_COMMA")
    return None


def detect_i_guess(text: str) -> DetectionMatch | None:
    """res-hedge-i-guess, rule ordinals 0 (HEDGE_PLACEMENT) and
    1 (VERB_FORM_OF_GUESS).

    Ordinal 0: the hedge wedged between a subject and its finite verb
    ("She I guess has already left"); the front position ("I guess we
    should leave soon") has no subject before the hedge. Ordinal 1: the
    be-forms directly before the bare verb ("I'm guess" / "I am guess")
    and the participle without its be ("I guessing"); "I am guessing"
    keeps its be and never fires.
    """

    misplaced = _HEDGE_MISPLACED.search(text)
    if misplaced is not None and misplaced.group(1) in FINITE_AUX_WORDS:
        return DetectionMatch("HEDGE_PLACEMENT")
    if (
        _GUESS_BE_FORM.search(text) is not None
        or _GUESS_BARE_PARTICIPLE.search(text) is not None
    ):
        return DetectionMatch("VERB_FORM_OF_GUESS")
    return None


def detect_come_again(text: str) -> DetectionMatch | None:
    """res-pragmatic-come-again, rule ordinals 0 (DOUBLE_MARKING) and
    1 (PREPOSITION_INSERTION).

    Ordinal 0: a past-marked word right after "didn't" (one echo adverb
    allowed: "didn't quite catched"). Ordinal 1: a preposition built
    into the echoed bare clock time ("did you say on four thirty"); the
    correct echo ("did you say four thirty or four fifteen?") carries no
    preposition.
    """

    toks = tokens(text)
    for idx, tok in enumerate(toks):
        if tok == "didn't":
            probe_at = idx + 1
        elif tok == "did" and idx + 1 < len(toks) and toks[idx + 1] == "not":
            probe_at = idx + 2
        else:
            continue
        if probe_at < len(toks) and toks[probe_at] in _DIDNT_ADVERBS:
            probe_at += 1
        if probe_at < len(toks):
            candidate = toks[probe_at]
            if (
                candidate.endswith("ed")
                and len(candidate) > 3
                and candidate not in _BARE_ED_FORMS
            ):
                return DetectionMatch("DOUBLE_MARKING")
    said = _SAY_PREP_HOUR.search(text)
    if said is not None and said.group(1) in _CLOCK_HOURS:
        return DetectionMatch("PREPOSITION_INSERTION")
    return None


def detect_no_way(text: str) -> DetectionMatch | None:
    """res-pragmatic-no-way, rule ordinals 0 (NEGATOR_SUBSTITUTION) and
    1 (THIRD_PERSON_S_DROP).

    Ordinal 0: the surprised receipt opens with "not way" ("Not way!").
    Ordinal 1: after the receipt ("no way" in the turn), the echoed news
    puts a bare verb after a third-person subject, one echo adverb
    allowed ("She actually move to Lisbon?"); the correct past ("She
    actually moved") never matches a bare form.
    """

    if fronted_then(text, "not way") is not None:
        return DetectionMatch("NEGATOR_SUBSTITUTION")
    if contains_phrase(text, "no way") or contains_phrase(text, "not way"):
        echo = _ECHO_BARE_VERB.search(text)
        if echo is not None and echo.group(1) in _BARE_ECHO_VERBS:
            return DetectionMatch("THIRD_PERSON_S_DROP")
    return None


def detect_that_makes_sense(text: str) -> DetectionMatch | None:
    """res-pragmatic-that-makes-sense, rule ordinals 0 (AGREEMENT_SLIP)
    and 1 (DEMONSTRATIVE_SLIP).

    Ordinal 0: the receipt frame opens the turn with the bare "that make
    sense" ("That make sense to me, thanks."), a receipt
    opener (Right/Okay/...) allowed in front; the turn-initial anchor
    keeps the relative-clause reading ("the rules that make sense") out.
    Ordinal 1: the plural demonstrative carrying the singular frame
    ("Those makes sense, thanks.").
    """

    if _BARE_MAKE_SENSE.match(text) is not None:
        return DetectionMatch("SUBJECT_VERB_AGREEMENT")
    if _THOSE_MAKES_SENSE.search(text) is not None:
        return DetectionMatch("PRONOUN_NUMBER_SLIP")
    return None


def detect_i_see(text: str) -> DetectionMatch | None:
    """res-pragmatic-i-see, rule ordinals 0 (PROGRESSIVE_RECEIPT) and
    1 (PAST_RECEIPT).

    Both slips are read turn-initially with the receipt pause after the
    token: the progressive ("I am seeing — go on, please") and the past
    ("I saw — do go on"). A receipt with its own object or event
    ("I saw him at the station"; "I am seeing the dentist") runs
    straight into a noun, not a pause, so the anchor refuses it.
    """

    for phrase, error_type in (
        ("i am seeing", "PROGRESSIVE_FORM"),
        ("i'm seeing", "PROGRESSIVE_FORM"),
        ("i saw", "TENSE_SLIP"),
    ):
        rest = fronted_then(text, phrase)
        if rest is not None and opens_with_pause(rest):
            return DetectionMatch(error_type)
    return None


def detect_more_or_less(text: str) -> DetectionMatch | None:
    """res-hedge-more-or-less, rule ordinals 0 (PARTICIPLE_SLIP) and
    1 (PAIR_ORDER_SLIP).

    Ordinal 0: the pair lowering a bare verb form ("is more or less
    finish"); the participles and adjectives the frame really holds
    ("more or less complete", "more or less done") are not in the target
    table. Ordinal 1: the pair reversed in the hedge slot after a finite
    be ("is less or more complete"); the literal quantity disjunction
    ("Bring more or less paper") has neither the be frame nor the
    reversal.
    """

    pair = _BARE_AFTER_PAIR.search(text)
    if pair is not None and pair.group(1) in _BARE_PAIR_TARGETS:
        return DetectionMatch("PARTICIPLE_SLIP")
    if _REVERSED_PAIR.search(text) is not None:
        return DetectionMatch("PAIR_ORDER_SLIP")
    return None


def detect_fair_enough(text: str) -> DetectionMatch | None:
    """res-pragmatic-fair-enough, rule ordinals 0 (ORDER_SLIP) and
    1 (ADVERB_SLIP).

    Both slips are read as the receipt turn's opener, word-bounded:
    "Enough fair" (the pair reordered) and "Fairly enough" (the adverb
    form). The correct frame ("Fair enough") and the literal adjective
    phrase ("The price is fair enough for a used bike") never open the
    turn with either slip.
    """

    if fronted_then(text, "enough fair") is not None:
        return DetectionMatch("WORD_ORDER_SLIP")
    if fronted_then(text, "fairly enough") is not None:
        return DetectionMatch("ADVERB_FORM_SLIP")
    return None


_PILOT_DETECTORS: tuple[tuple[str, tuple[int, ...], Matcher], ...] = (
    ("res-discourse-anyway", (0,), detect_anyway),
    ("res-discourse-before-i-forget", (0, 1), detect_before_i_forget),
    ("res-discourse-moving-on", (0, 1), detect_moving_on),
    ("res-hedge-i-guess", (0, 1), detect_i_guess),
    ("res-hedge-i-think", (0, 1), detect_i_think),
    ("res-hedge-more-or-less", (0, 1), detect_more_or_less),
    ("res-pragmatic-come-again", (0, 1), detect_come_again),
    ("res-pragmatic-fair-enough", (0, 1), detect_fair_enough),
    ("res-pragmatic-got-it", (0, 1), detect_got_it),
    ("res-pragmatic-i-see", (0, 1), detect_i_see),
    ("res-pragmatic-no-way", (0, 1), detect_no_way),
    ("res-pragmatic-that-makes-sense", (0, 1), detect_that_makes_sense),
)


def register_pilot(registry: DetectorRegistry) -> None:
    """Register the twelve pilot matchers into ``registry``.

    The idempotence posture is the registry's own: a second
    ``register_pilot`` call on the same registry is refused with
    ``ValueError`` (the registry never replaces an entry).
    """

    for entity_id, rule_ordinals, matcher in _PILOT_DETECTORS:
        registry.register(entity_id, rule_ordinals, matcher)
