"""The D-3 pilot detector set — thirty-six real matchers.

Thirty-six ``EDITOR_REVIEWED`` R4 targets are verified executable: each
matcher implements its entity's declared detection-rule prose (the rule
ordinals are named in the matcher's docstring) with anchors, word tables
and exclusion lists from :mod:`elc.detection.patterns`, so a sentence
built on the same pattern with different words is judged identically.
The fixtures under ``content_src/evidence/`` are the verification set,
never the implementation — no matcher compares against a fixture
sentence. The first twelve landed with D-3; the expansion cut brought
the roster to thirty-six by the same mode (read the entity's declared
rules, implement them on surface anchors, pass the full fixture set).

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
#: value names the cut that landed the twelve (D-3) — the initial value —
#: or, since the expansion cut, the cut that brought the roster to
#: thirty-six, which is the set this module now is.
PILOT_VERSION = "d3-pilot-2"

#: The pilot roster, sorted: thirty-six EDITOR_REVIEWED R4 targets whose
#: declared fixtures the matchers below must pass in full. The sort is
#: load-bearing: the assembling entry points compare the assembled
#: registry's sorted id list against this tuple verbatim, so an unsorted
#: tuple would make every second ``main`` call re-register and refuse.
PILOT_ENTITIES: tuple[str, ...] = (
    "res-discourse-anyway",
    "res-discourse-before-i-forget",
    "res-discourse-moving-on",
    "res-discourse-on-another-note",
    "res-discourse-speaking-of-which",
    "res-discourse-that-brings-me-to",
    "res-discourse-to-be-honest",
    "res-discourse-to-get-back-to-the-point",
    "res-discourse-where-was-i",
    "res-hedge-as-far-as-i-know",
    "res-hedge-i-guess",
    "res-hedge-i-think",
    "res-hedge-if-im-not-mistaken",
    "res-hedge-in-a-way",
    "res-hedge-it-seems-to-me",
    "res-hedge-more-or-less",
    "res-pragmatic-are-you-saying",
    "res-pragmatic-come-again",
    "res-pragmatic-could-you-clarify",
    "res-pragmatic-could-you-say-that-again",
    "res-pragmatic-fair-enough",
    "res-pragmatic-go-on",
    "res-pragmatic-got-it",
    "res-pragmatic-i-hear-you-but",
    "res-pragmatic-i-see",
    "res-pragmatic-i-see-your-point-but",
    "res-pragmatic-im-not-convinced",
    "res-pragmatic-let-me-make-sure",
    "res-pragmatic-no-offense-but",
    "res-pragmatic-no-way",
    "res-pragmatic-right",
    "res-pragmatic-that-makes-sense",
    "res-pragmatic-up-to-a-point",
    "res-pragmatic-what-do-you-mean",
    "res-pragmatic-with-all-due-respect",
    "res-softener-kind-of",
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


# ---------------------------------------------------------------------------
# the expansion cut — twenty-four further matchers in D-3's mode
# ---------------------------------------------------------------------------

#: The words that can open the clause a fronted marker runs into when its
#: comma is missing ("Speaking of which the interview went badly"). A word
#: outside the table leaves the clause reading unproven: the relative
#: reading keeps its noun right after the marker's last word ("speaking of
#: which projects to fund"), where ``which`` is a determiner, not a pointer.
_CLAUSE_OPENERS: frozenset[str] = frozenset({
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "this", "that", "these", "those", "there", "here",
    "how", "what", "when", "where", "which", "who", "whom", "whose",
    "why", "whether", "if", "am", "is", "are", "was", "were", "did",
    "does", "do", "will", "would", "shall", "should", "can", "could",
    "may", "might", "must", "have", "has", "had", "the", "a", "an",
    "my", "your", "his", "its", "our", "their", "let", "let's",
    "please", "maybe", "perhaps", "anyway", "so", "and", "but", "then",
    "well", "guess",
})

#: The modifiers the article-intruded softener takes ("a kind of rushed");
#: the classifier reading takes a noun as its head ("a kind of bird"), so
#: the nouns the classifier really holds are deliberately absent.
_A_KIND_OF_MODIFIERS: frozenset[str] = frozenset({
    "annoying", "angry", "awkward", "bad", "boring", "busy", "calm",
    "cold", "confusing", "crazy", "creepy", "disappointing", "early",
    "easy", "fast", "frustrating", "funny", "good", "great", "happy",
    "hard", "harsh", "hot", "intense", "know", "late", "like", "loud",
    "mean", "nervous", "nice", "odd", "quiet", "quick", "rough", "rude",
    "rushed", "sad", "scary", "serious", "sick", "slow", "soft",
    "strange", "surprising", "tired", "tough", "warm", "weird",
    "worried",
})

#: The classifier-head nouns the bare-noun slip reads ("They opened kind
#: of shop by the river"); the modifiers the softener really holds ("kind
#: of sad") are deliberately absent.
_KIND_OF_CLASSIFIER_NOUNS: frozenset[str] = frozenset({
    "animal", "app", "beach", "bird", "book", "building", "bus", "cafe",
    "car", "cat", "city", "club", "country", "dish", "dog", "drink",
    "film", "flower", "friend", "game", "group", "home", "hostel",
    "hotel", "house", "idea", "island", "job", "machine", "man",
    "market", "meal", "movie", "park", "person", "place", "plan",
    "problem", "question", "restaurant", "room", "school", "shop",
    "song", "soup", "store", "team", "tool", "town", "train", "tree",
    "village", "woman",
})

#: Determiners, quantifiers and wh-words: a phrase whose classifier slot
#: one of these fills is either the classifier reading (an article or a
#: demonstrative stands in front of the head noun) or a question naming
#: the class ("What kind of bird is that?") — never the bare-noun slip.
_KIND_OF_BLOCKERS: frozenset[str] = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "my", "your",
    "his", "her", "its", "our", "their", "one", "each", "every", "some",
    "any", "no", "another", "other", "what", "which", "whatever",
    "whichever", "such",
})

#: The modals whose complement must be the bare verb, and the past forms
#: that betray the slip straight after one ("we can't spent any more").
#: The regular pasts answer the -ed probe; the bare -ed verbs ("didn't
#: need" family) are excluded, and the irregular pasts the objection arm
#: really takes are tabled.
_HEAR_MODALS: frozenset[str] = frozenset({
    "can", "can't", "cannot", "could", "will", "would", "shall",
    "should", "may", "might", "must",
})
_HEAR_PAST_FORMS: frozenset[str] = frozenset({
    "ate", "bought", "broke", "brought", "built", "came", "caught",
    "chose", "drank", "drove", "fell", "felt", "flew", "found", "gave",
    "grew", "held", "kept", "knew", "left", "lost", "made", "met",
    "paid", "ran", "rose", "said", "sang", "saw", "sent", "sold",
    "spoke", "spent", "swam", "taught", "told", "took", "thought",
    "went", "won", "wore", "wrote",
})
_HEAR_BARE_ED_FORMS: frozenset[str] = frozenset({
    "need", "speed", "seed", "weed", "breed", "exceed", "proceed",
    "succeed", "indeed",
})

#: The words whose presence after the concession's "and" marks the next
#: clause as the objection ("and it is still too expensive") — a plain
#: continuation ("and I'll confirm the dates tomorrow") carries none.
_OBJECTION_MARKS: frozenset[str] = frozenset({
    "still", "too", "anyway", "unfortunately", "sadly", "never", "no",
    "not", "cannot", "can't", "don't", "doesn't", "didn't", "won't",
    "isn't", "aren't", "wasn't", "weren't", "hardly", "barely",
    "neither", "nor",
})

_CLARIFY_INVERSION = re.compile(
    r"\bclarify\s+(?:what|which|when|where|why|how|who)\s+"
    r"(?:did|do|does|is|are|was|were|can|could|will|would|should)\b",
    re.IGNORECASE,
)
_REQUEST_SAY_AGAIN = re.compile(
    r"\b(?:could|can|would)\s+you\s+say\s+again\b", re.IGNORECASE
)
_WHAT_HAPPEN = re.compile(r"\bwhat\s+happen\b", re.IGNORECASE)
_BE_NOT_CONVINCE = re.compile(
    r"\b(?:am|is|are|'m|'re)\s+not\s+convince\b", re.IGNORECASE
)
_BE_NOT_CONVINCING = re.compile(
    r"\b(?:am|is|are|'m|'re)\s+not\s+convincing\s+([a-z']+)", re.IGNORECASE
)
_LET_ME_TO = re.compile(r"\blet\s+me\s+to\b", re.IGNORECASE)
_LET_ME_GERUND = re.compile(r"\blet\s+me\s+[a-z']+ing\b", re.IGNORECASE)
_WHAT_YOU_MEAN = re.compile(
    r"\bwhat\s+you\s+mean(?:\s+by\b|\s*\?)", re.IGNORECASE
)
_MEAN_DEMONSTRATIVE = re.compile(
    r"\bwhat\s+do\s+you\s+mean\s+(?:that|this)\s*\?", re.IGNORECASE
)
_UNTIL_A_POINT = re.compile(r"\buntil a point\b", re.IGNORECASE)
_SEE_YOUR_POINT = re.compile(r"\bsee your point\b", re.IGNORECASE)


def detect_on_another_note(text: str) -> DetectionMatch | None:
    """res-discourse-on-another-note, rule ordinals 0 (PREPOSITION_SLIP)
    and 1 (MISSING_COMMA).

    Ordinal 0: the marker opens the turn with the wrong preposition
    ("In another note, the invoice still waits."), the fixed phrase
    being "on another note"; the accepted realizations spell the
    preposition right and never fire. Ordinal 1: the right marker
    fronted with no pause running into a clause ("On another note the
    invoice still waits."); the noun-phrase reading ("a reminder on
    another note") is mid-clause, so the anchor refuses it.
    """

    if fronted_then(text, "in another note") is not None:
        return DetectionMatch("PREPOSITION_SLIP")
    rest = fronted_then(text, "on another note")
    if (
        rest is not None
        and not opens_with_pause(rest)
        and first_word(rest) is not None
    ):
        return DetectionMatch("MISSING_COMMA")
    return None


def detect_speaking_of_which(text: str) -> DetectionMatch | None:
    """res-discourse-speaking-of-which, rule ordinals 0
    (PRONOUN_SUBSTITUTION) and 1 (MISSING_COMMA).

    Ordinal 0: the frozen ``which`` swapped for the ordinary pronoun in
    the fronted marker position ("Speaking of it, the meeting moved to
    Friday."); the spelled-out noun ("Speaking of the meeting, ...") is
    a different phrase. Ordinal 1: the marker fronted with no pause
    running into a clause ("Speaking of which the interview went
    badly."); the relative reading keeps its noun right after
    ("speaking of which projects to fund"), so the next word must open
    a clause, not carry ``which`` as its determiner.
    """

    if (
        fronted_then(text, "speaking of it") is not None
        or fronted_then(text, "speaking of this") is not None
    ):
        return DetectionMatch("PRONOUN_SUBSTITUTION")
    rest = fronted_then(text, "speaking of which")
    if (
        rest is not None
        and not opens_with_pause(rest)
        and first_word(rest) in _CLAUSE_OPENERS
    ):
        return DetectionMatch("MISSING_COMMA")
    return None


def detect_that_brings_me_to(text: str) -> DetectionMatch | None:
    """res-discourse-that-brings-me-to, rule ordinals 0 (PREPOSITION_SLIP)
    and 1 (OBJECT_DROP).

    Ordinal 0: the signpost carries "brings me on" or "brings me at"
    before the named matter, the frame's preposition being ``to``.
    Ordinal 1: ``brings`` followed straight by ``to`` with no object
    pronoun between ("That brings to the matter directly"), the frame
    moving the speaker into the new matter; the whole frame ("brings me
    to") and the literal transport reading carry the object and never
    fire.
    """

    if (
        contains_phrase(text, "brings me on")
        or contains_phrase(text, "brings me at")
    ):
        return DetectionMatch("PREPOSITION_SLIP")
    if contains_phrase(text, "brings to"):
        return DetectionMatch("OBJECT_DROP")
    return None


def detect_to_be_honest(text: str) -> DetectionMatch | None:
    """res-discourse-to-be-honest, rule ordinals 0 (CALQUED_COMMENT_FORM)
    and 1 (PARTICIPLE_FORM).

    Ordinal 0: the comment frame over-generalised onto honest —
    "honestly speaking" or "frankly speaking" as the fronted marker
    ("Honestly speaking, the design needs another pass."); the frame
    belongs to other adverbs. Ordinal 1: the participle rebuilt as the
    fronted comment marker ("Being honest, I don't like the design."),
    the marker being fixed as "to be honest"; a gerund subject with no
    pause ("Being honest with customers builds trust.") runs into its
    own predicate and refuses.
    """

    if (
        fronted_then(text, "honestly speaking") is not None
        or fronted_then(text, "frankly speaking") is not None
    ):
        return DetectionMatch("CALQUED_COMMENT_FORM")
    rest = fronted_then(text, "being honest")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("PARTICIPLE_FORM")
    return None


def detect_to_get_back_to_the_point(text: str) -> DetectionMatch | None:
    """res-discourse-to-get-back-to-the-point, rule ordinals 0
    (PREPOSITION_SLIP) and 1 (ARTICLE_DROP).

    Ordinal 0: the marker phrase carries "back on the point", the
    stored phrase being "back to the point". Ordinal 1: the phrase
    carries "back to point" with no article, the stored phrase carrying
    "the point"; the accepted realizations keep the article and never
    fire ("to get back to the point", "getting back to the point",
    "back to the point").
    """

    if contains_phrase(text, "back on the point"):
        return DetectionMatch("PREPOSITION_SLIP")
    if contains_phrase(text, "back to point"):
        return DetectionMatch("ARTICLE_DROP")
    return None


def detect_where_was_i(text: str) -> DetectionMatch | None:
    """res-discourse-where-was-i, rule ordinals 0 (QUESTION_INVERSION_SLIP)
    and 1 (WH_IN_SITU).

    Ordinal 0: the resumption question asked with statement order — the
    turn opens "Where I was?" and a question mark closes it; the
    inverted form ("Where was I? ...") and the embedded indirect
    question ("Do you remember where I was?") never open the turn with
    the broken order. Ordinal 1: the question word left in place after
    the subject ("I was where?"); the inverted form and the statement
    ("I was where I needed to be.") refuse.
    """

    rest = fronted_then(text, "where i was")
    if rest is not None and rest.lstrip().startswith("?"):
        return DetectionMatch("QUESTION_INVERSION_SLIP")
    rest = fronted_then(text, "i was where")
    if rest is not None and rest.lstrip().startswith("?"):
        return DetectionMatch("WH_IN_SITU")
    return None


def detect_as_far_as_i_know(text: str) -> DetectionMatch | None:
    """res-hedge-as-far-as-i-know, rule ordinals 0 (CONJUNCTION_CONFUSION)
    and 1 (CONJUNCTION_DROP).

    Ordinal 0: the duration conjunction fronted in the hedge slot with
    its pause ("as long as I know," — a duration frame standing where a
    knowledge hedge belongs), the stored hedge being "as far as I know";
    a condition carrying its own object after ``know`` ("as long as I
    know where to sign, I'm fine") has no pause at the anchor and
    refuses. Ordinal 1: the string "as far I know" with no second
    ``as`` before the anchor, anywhere in the turn.
    """

    rest = fronted_then(text, "as long as i know")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("CONJUNCTION_CONFUSION")
    if contains_phrase(text, "as far i know"):
        return DetectionMatch("CONJUNCTION_DROP")
    return None


def detect_if_im_not_mistaken(text: str) -> DetectionMatch | None:
    """res-hedge-if-im-not-mistaken, rule ordinals 0 (FORM_SLIP) and
    1 (MISSING_COMMA).

    Ordinal 0: the conditional frame carries "don't mistake" or "not
    mistake" with no -en ending ("If I don't mistake," with a fresh
    clause after it); the stored participle ("not mistaken") is
    word-bounded away from the bare form. Ordinal 1: the whole formula
    fronted with no pause running into a clause; the afterthought
    position ("..., if I'm not mistaken.") is mid-clause and refuses.
    """

    if (
        contains_phrase(text, "don't mistake")
        or contains_phrase(text, "not mistake")
    ):
        return DetectionMatch("FORM_SLIP")
    rest = fronted_then(text, "if i'm not mistaken")
    if (
        rest is not None
        and not opens_with_pause(rest)
        and first_word(rest) is not None
    ):
        return DetectionMatch("MISSING_COMMA")
    return None


def detect_in_a_way(text: str) -> DetectionMatch | None:
    """res-hedge-in-a-way, rule ordinals 0 (ARTICLE_DROP) and
    1 (PREPOSITION_SLIP).

    Both slips are read at the front of the hedged claim with the
    frame's pause: "in way" (the article dropped) and "on a way" (the
    preposition swapped); the stored frame ("In a way, ...") spells
    both right and never fires, and the literal manner reading is
    mid-clause ("Cook the rice in a way that keeps the grains
    whole.").
    """

    rest = fronted_then(text, "in way")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("ARTICLE_DROP")
    rest = fronted_then(text, "on a way")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("PREPOSITION_SLIP")
    return None


def detect_it_seems_to_me(text: str) -> DetectionMatch | None:
    """res-hedge-it-seems-to-me, rule ordinals 0 (SUBJECT_DROP) and
    1 (PREPOSITION_SLIP).

    Ordinal 0: "seems that" or "seems like" opens the turn with no
    subject and a full clause follows ("Seems that the plan will not
    survive review."); the clause-opener requirement separates the
    hedge from the noun-phrase reading ("Seems like rain.", "Seems
    that way."). Ordinal 1: the frame runs "seems for me" before a
    clause, the stored formula carrying "to me"; the accepted forms
    ("it seems to me that ...", "it seems that ...") keep their subject
    and never fire.
    """

    for phrase in ("seems that", "seems like"):
        rest = fronted_then(text, phrase)
        if rest is not None and first_word(rest) in SUBJECT_WORDS:
            return DetectionMatch("SUBJECT_DROP")
    if contains_phrase(text, "seems for me"):
        return DetectionMatch("PREPOSITION_SLIP")
    return None


def detect_are_you_saying(text: str) -> DetectionMatch | None:
    """res-pragmatic-are-you-saying, rule ordinals 0 (AUXILIARY_DROP) and
    1 (VERB_FORM_SLIP).

    Ordinal 0: "you saying" opens the turn as a question with no be in
    front ("You saying that the order is cancelled?"); the whole check
    ("Are you saying that ...?") starts at the auxiliary and refuses.
    Ordinal 1: the check carries "are you say" or "are you said" before
    its clause, the frame keeping the -ing form; the word-bounded
    anchor never fires inside "are you saying".
    """

    rest = fronted_then(text, "you saying")
    if rest is not None and "?" in rest:
        return DetectionMatch("AUXILIARY_DROP")
    if (
        contains_phrase(text, "are you say")
        or contains_phrase(text, "are you said")
    ):
        return DetectionMatch("VERB_FORM_SLIP")
    return None


def detect_could_you_clarify(text: str) -> DetectionMatch | None:
    """res-pragmatic-could-you-clarify, rule ordinals 0 (DATIVE_INSERTION)
    and 1 (EMBEDDED_INVERSION).

    Ordinal 0: the frame carries a person object after ``clarify``
    ("clarify me", "clarify us", "clarify to me"), the point being
    taken directly; the go-and-act request names its document and
    refuses. Ordinal 1: the embedded question after ``clarify``
    inverts ("clarify what did you mean"), the embedded question
    keeping statement order; the accepted forms run the wh-word
    straight into the subject.
    """

    if (
        contains_phrase(text, "clarify me")
        or contains_phrase(text, "clarify us")
        or contains_phrase(text, "clarify to me")
    ):
        return DetectionMatch("DATIVE_INSERTION")
    if _CLARIFY_INVERSION.search(text) is not None:
        return DetectionMatch("EMBEDDED_INVERSION")
    return None


def detect_could_you_say_that_again(text: str) -> DetectionMatch | None:
    """res-pragmatic-could-you-say-that-again, rule ordinals 0
    (REDUNDANT_AGAIN) and 1 (OBJECT_DROP).

    Ordinal 0: the request contains "repeat again", the verb already
    carrying the second-time meaning. Ordinal 1: the request runs "say
    again" with no object between the verb and the second-time word —
    "Could you say again, please?" asks with nothing held; the accepted
    forms carry the object ("say that again", "say that last part
    again") and the conditional threat ("Say that again and I'll
    leave") is no request, so neither fires.
    """

    if contains_phrase(text, "repeat again"):
        return DetectionMatch("REDUNDANT_AGAIN")
    if _REQUEST_SAY_AGAIN.search(text) is not None:
        return DetectionMatch("OBJECT_DROP")
    return None


def detect_go_on(text: str) -> DetectionMatch | None:
    """res-pragmatic-go-on, rule ordinals 0 (SUBJECT_DROP) and
    1 (PAST_MARKING_SLIP).

    Ordinal 0: the clause after the invitation's pause opens with a
    bare be-form and no subject ("Go on, is cold in here."); a subject
    word after the be-form (the inverted question, "Go on, is it just
    me?") keeps the rule out through SUBJECT_WORDS. Ordinal 1: the
    follow-up question after the invitation carries the bare "what
    happen" shape where the story's past belongs ("Go on — what come
    next?"), with the invitation present and a question mark closing
    the probe; the corrected past ("what happened") is word-bounded
    away.
    """

    rest = fronted_then(text, "go on")
    if rest is not None and opens_with_pause(rest):
        toks = tokens(rest.lstrip()[1:])
        if (
            len(toks) >= 2
            and toks[0] in ("am", "is", "are")
            and toks[1] not in SUBJECT_WORDS
        ):
            return DetectionMatch("SUBJECT_DROP")
    if (
        contains_phrase(text, "go on")
        and _WHAT_HAPPEN.search(text) is not None
        and "?" in text
    ):
        return DetectionMatch("PAST_MARKING_SLIP")
    return None


def detect_i_hear_you_but(text: str) -> DetectionMatch | None:
    """res-pragmatic-i-hear-you-but, rule ordinals 0 (MODAL_VERB_SLIP) and
    1 (PREPOSITION_INSERTION).

    Ordinal 0: inside the frame (a ``hear`` credit clause hinged by
    ``but``), a past or participial form stands straight after a modal
    ("we can't spent any more on this"); the bare complement
    ("can't spend") never fires. Ordinal 1: the credit clause carries
    "hear to you" (or him/her), the person object belonging bare; the
    literal-hearing boundary ("I hear you, but I can't see you") keeps
    its bare object and refuses.
    """

    if contains_phrase(text, "hear") and contains_phrase(text, "but"):
        toks = tokens(text)
        for idx, tok in enumerate(toks):
            if tok not in _HEAR_MODALS:
                continue
            probe_at = idx + 1
            if probe_at < len(toks) and toks[probe_at] == "not":
                probe_at += 1
            if probe_at < len(toks):
                candidate = toks[probe_at]
                if candidate in _HEAR_PAST_FORMS or (
                    candidate.endswith("ed")
                    and len(candidate) > 3
                    and candidate not in _HEAR_BARE_ED_FORMS
                ):
                    return DetectionMatch("MODAL_VERB_SLIP")
    if (
        contains_phrase(text, "hear to you")
        or contains_phrase(text, "hear to him")
        or contains_phrase(text, "hear to her")
    ):
        return DetectionMatch("PREPOSITION_INSERTION")
    return None


def detect_i_see_your_point_but(text: str) -> DetectionMatch | None:
    """res-pragmatic-i-see-your-point-but, rule ordinals 0
    (POSSESSIVE_DROP) and 1 (CONNECTOR_CHOICE).

    Ordinal 0: the concession arm reads "see you point" with no
    possessive in front of ``point``. Ordinal 1: the whole arm pivots
    on ``and`` into a clause that carries an objection mark ("and it is
    still too expensive") with no ``but`` anywhere in the sentence; a
    plain continuation ("and I'll confirm the dates tomorrow") carries
    no mark and the plain receipt without its objection arm refuses.
    """

    if contains_phrase(text, "see you point"):
        return DetectionMatch("POSSESSIVE_DROP")
    found = _SEE_YOUR_POINT.search(text)
    if found is not None:
        tail_tokens = tokens(text[found.end():])
        if (
            "and" in tail_tokens
            and "but" not in tokens(text)
            and any(mark in tail_tokens for mark in _OBJECTION_MARKS)
        ):
            return DetectionMatch("CONNECTOR_CHOICE")
    return None


def detect_im_not_convinced(text: str) -> DetectionMatch | None:
    """res-pragmatic-im-not-convinced, rule ordinals 0 (PARTICIPLE_SLIP)
    and 1 (PARTICIPLE_VOICE_SLIP).

    Ordinal 0: the be-frame carries "not convince" with no participle
    ending ("I'm not convince the option lasts."); the stored
    -ed form is word-bounded away. Ordinal 1: the frame carries "not
    convincing" before the other person's claim, the -ing reading being
    a failure to persuade; the claim is keyed on the clause-opening
    word after it, and the stored -ed form never fires.
    """

    if _BE_NOT_CONVINCE.search(text) is not None:
        return DetectionMatch("PARTICIPLE_SLIP")
    found = _BE_NOT_CONVINCING.search(text)
    if found is not None and found.group(1) in SUBJECT_WORDS:
        return DetectionMatch("PARTICIPLE_VOICE_SLIP")
    return None


def detect_let_me_make_sure(text: str) -> DetectionMatch | None:
    """res-pragmatic-let-me-make-sure, rule ordinals 0
    (INFINITIVE_MARKER_SLIP) and 1 (GERUND_SLIP).

    Ordinal 0: the causative frame carries "let me to" before its verb,
    causative ``let`` taking the bare infinitive. Ordinal 1: the frame
    carries "let me" straight into an -ing form ("Let me making sure we
    agree on the plan."), the complement being the bare form; the
    accepted shapes ("let me make sure ...") never fire.
    """

    if _LET_ME_TO.search(text) is not None:
        return DetectionMatch("INFINITIVE_MARKER_SLIP")
    if _LET_ME_GERUND.search(text) is not None:
        return DetectionMatch("GERUND_SLIP")
    return None


def detect_no_offense_but(text: str) -> DetectionMatch | None:
    """res-pragmatic-no-offense-but, rule ordinals 0 (MISSING_CONJUNCTION)
    and 1 (NOUN_FORM_OF_OFFENSE).

    Ordinal 0: "no offense" opens the utterance and the criticism joins
    it by a comma or a full stop alone ("No offense, your handwriting
    is hard to read."), the ``but`` being the move's conjunction; the
    whole move ("No offense, but ...") carries its ``but`` and refuses.
    Ordinal 1: a verb form stands in place of the uncountable noun
    ("No offends, but ..."); the reply phrase "no offense taken" keeps
    the noun and refuses.
    """

    if (
        contains_phrase(text, "no offends")
        or contains_phrase(text, "no offensed")
    ):
        return DetectionMatch("NOUN_FORM_OF_OFFENSE")
    rest = fronted_then(text, "no offense")
    if rest is not None:
        stripped = rest.lstrip()
        if stripped[:1] in (",", "."):
            tail_tokens = tokens(stripped[1:])
            if tail_tokens and "but" not in tokens(text):
                return DetectionMatch("MISSING_CONJUNCTION")
    return None


def detect_right(text: str) -> DetectionMatch | None:
    """res-pragmatic-right, rule ordinals 0 (HOMOPHONE_SPELLING) and
    1 (ADVERB_OVERCORRECTION).

    Both slips are read at the listener receipt position — the turn
    opens with the word and a pause follows ("Write — the speaker is
    with you."; "Rightly — the speaker is with you."), the signal being
    spelled ``right``; the bare receipt ("Right — I'm with you.") and
    the adjective before its noun ("the right answer") never fire.
    """

    rest = fronted_then(text, "write")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("HOMOPHONE_SPELLING")
    rest = fronted_then(text, "rightly")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("ADVERB_OVERCORRECTION")
    return None


def detect_up_to_a_point(text: str) -> DetectionMatch | None:
    """res-pragmatic-up-to-a-point, rule ordinals 0 (ARTICLE_DROP) and
    1 (PREPOSITION_SLIP).

    Ordinal 0: the answer position opens "up to point" with no article
    and the frame's pause ("Up to point, I agree, but the survey
    worries me."), the stored phrase carrying "a point". Ordinal 1: the
    answer position carries "until a point" followed by a pause or a
    but-clause, the stored preposition being "up to"; the whole phrase
    ("up to a point, yes") and the literal extent reading refuse.
    """

    rest = fronted_then(text, "up to point")
    if rest is not None and opens_with_pause(rest):
        return DetectionMatch("ARTICLE_DROP")
    found = _UNTIL_A_POINT.search(text)
    if found is not None:
        tail = text[found.end():]
        if opens_with_pause(tail) or "but" in tokens(tail):
            return DetectionMatch("PREPOSITION_SLIP")
    return None


def detect_what_do_you_mean(text: str) -> DetectionMatch | None:
    """res-pragmatic-what-do-you-mean, rule ordinals 0 (AUXILIARY_DROP)
    and 1 (OBJECT_SLIP).

    Ordinal 0: the question runs "what you mean" with no do-support and
    a question mark or a by-phrase closing it ("What you mean by
    that?" asks it bare); the built question ("What do you mean by
    that?") carries its auxiliary and refuses. Ordinal 1: the question
    bolts the demonstrative onto ``mean`` ("What do you mean that?"),
    the object belonging in a by-phrase or an echo; the wh-echo with
    its comma ("What do you mean, the contract is void?") and the
    intention reading ("mean to do") refuse.
    """

    if _WHAT_YOU_MEAN.search(text) is not None:
        return DetectionMatch("AUXILIARY_DROP")
    if _MEAN_DEMONSTRATIVE.search(text) is not None:
        return DetectionMatch("OBJECT_SLIP")
    return None


def detect_with_all_due_respect(text: str) -> DetectionMatch | None:
    """res-pragmatic-with-all-due-respect, rule ordinals 0
    (PREPOSITION_SLIP) and 1 (NUMBER_SLIP).

    Ordinal 0: the flag stands as "in all due respect", the stored
    phrase fixing ``with`` ("In all due respect, the numbers disagree
    with you."). Ordinal 1: the flag carries "due respects", the
    stored noun being the singular ``respect``; the whole flag ("with
    all due respect, ...") and the literal courtesy report refuse.
    """

    if contains_phrase(text, "in all due respect"):
        return DetectionMatch("PREPOSITION_SLIP")
    if contains_phrase(text, "due respects"):
        return DetectionMatch("NUMBER_SLIP")
    return None


def detect_kind_of(text: str) -> DetectionMatch | None:
    """res-softener-kind-of, rule ordinals 0 (ARTICLE_BEFORE_SOFTENER) and
    1 (SOFTENER_BEFORE_A_BARE_NOUN).

    Ordinal 0: the classifier's article carried into the softener slot —
    "a kind of" followed by a modifier word ("a kind of rushed"); the
    classifier reading takes a noun as its head ("a kind of bird"), so
    the noun heads are absent from the modifier table. Ordinal 1: the
    bare softener followed by a head noun with no determiner ("They
    opened kind of shop by the river"), the classifying article being
    what belongs there; a determiner or wh-word in the phrase's frame
    ("a kind of bird", "this kind of problem", "What kind of bird is
    that?") marks the classifier or the question and keeps both rules
    out, and the softener's own shapes ("kind of sad", "kind of like")
    carry modifiers, not the tabled nouns.
    """

    toks = tokens(text)
    for idx, tok in enumerate(toks):
        if tok != "kind" or idx + 2 >= len(toks) or toks[idx + 1] != "of":
            continue
        prev = toks[idx - 1] if idx >= 1 else ""
        nxt = toks[idx + 2]
        if prev == "a" and nxt in _A_KIND_OF_MODIFIERS:
            return DetectionMatch("ARTICLE_INTRUSION")
    for idx, tok in enumerate(toks):
        if tok != "kind" or idx + 2 >= len(toks) or toks[idx + 1] != "of":
            continue
        prev = toks[idx - 1] if idx >= 1 else ""
        prev2 = toks[idx - 2] if idx >= 2 else ""
        nxt = toks[idx + 2]
        if (
            prev not in _KIND_OF_BLOCKERS
            and prev2 not in _KIND_OF_BLOCKERS
            and nxt in _KIND_OF_CLASSIFIER_NOUNS
        ):
            return DetectionMatch("CLASSIFIER_ARTICLE_MISSING")
    return None


_PILOT_DETECTORS: tuple[tuple[str, tuple[int, ...], Matcher], ...] = (
    ("res-discourse-anyway", (0,), detect_anyway),
    ("res-discourse-before-i-forget", (0, 1), detect_before_i_forget),
    ("res-discourse-moving-on", (0, 1), detect_moving_on),
    ("res-discourse-on-another-note", (0, 1), detect_on_another_note),
    ("res-discourse-speaking-of-which", (0, 1), detect_speaking_of_which),
    ("res-discourse-that-brings-me-to", (0, 1), detect_that_brings_me_to),
    ("res-discourse-to-be-honest", (0, 1), detect_to_be_honest),
    (
        "res-discourse-to-get-back-to-the-point",
        (0, 1),
        detect_to_get_back_to_the_point,
    ),
    ("res-discourse-where-was-i", (0, 1), detect_where_was_i),
    ("res-hedge-as-far-as-i-know", (0, 1), detect_as_far_as_i_know),
    ("res-hedge-i-guess", (0, 1), detect_i_guess),
    ("res-hedge-i-think", (0, 1), detect_i_think),
    ("res-hedge-if-im-not-mistaken", (0, 1), detect_if_im_not_mistaken),
    ("res-hedge-in-a-way", (0, 1), detect_in_a_way),
    ("res-hedge-it-seems-to-me", (0, 1), detect_it_seems_to_me),
    ("res-hedge-more-or-less", (0, 1), detect_more_or_less),
    ("res-pragmatic-are-you-saying", (0, 1), detect_are_you_saying),
    ("res-pragmatic-come-again", (0, 1), detect_come_again),
    ("res-pragmatic-could-you-clarify", (0, 1), detect_could_you_clarify),
    (
        "res-pragmatic-could-you-say-that-again",
        (0, 1),
        detect_could_you_say_that_again,
    ),
    ("res-pragmatic-fair-enough", (0, 1), detect_fair_enough),
    ("res-pragmatic-go-on", (0, 1), detect_go_on),
    ("res-pragmatic-got-it", (0, 1), detect_got_it),
    ("res-pragmatic-i-hear-you-but", (0, 1), detect_i_hear_you_but),
    ("res-pragmatic-i-see", (0, 1), detect_i_see),
    ("res-pragmatic-i-see-your-point-but", (0, 1), detect_i_see_your_point_but),
    ("res-pragmatic-im-not-convinced", (0, 1), detect_im_not_convinced),
    ("res-pragmatic-let-me-make-sure", (0, 1), detect_let_me_make_sure),
    ("res-pragmatic-no-offense-but", (0, 1), detect_no_offense_but),
    ("res-pragmatic-no-way", (0, 1), detect_no_way),
    ("res-pragmatic-right", (0, 1), detect_right),
    ("res-pragmatic-that-makes-sense", (0, 1), detect_that_makes_sense),
    ("res-pragmatic-up-to-a-point", (0, 1), detect_up_to_a_point),
    ("res-pragmatic-what-do-you-mean", (0, 1), detect_what_do_you_mean),
    ("res-pragmatic-with-all-due-respect", (0, 1), detect_with_all_due_respect),
    ("res-softener-kind-of", (0, 1), detect_kind_of),
)


def register_pilot(registry: DetectorRegistry) -> None:
    """Register the thirty-six pilot matchers into ``registry``.

    The idempotence posture is the registry's own: a second
    ``register_pilot`` call on the same registry is refused with
    ``ValueError`` (the registry never replaces an entry).
    """

    for entity_id, rule_ordinals, matcher in _PILOT_DETECTORS:
        registry.register(entity_id, rule_ordinals, matcher)
