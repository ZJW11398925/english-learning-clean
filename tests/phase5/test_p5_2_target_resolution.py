"""⑤① — the p5-2 resolver's rule table: extraction, boundaries, priority.

The unit under test is elc.learning.target_resolution — pure functions, no
IO: the facts are built by hand here (and, in the corpus-truth-table block,
read from the real content.db through the supply face, which is the one
place in this file that touches the artifact).

Three things are pinned, each at its own address:

- the normalization (casefold + whitespace collapse + edge punctuation
  strip — the in-repo precedent) and what it deliberately does NOT loosen;
- the fixed priority order canonical form > alternative realization >
  required slots, with the documented tie-breaks;
- the resolver's own guards: the kind filter, the blank utterance, and
  NO_TARGET's zero-side-effect contract.
"""

from __future__ import annotations

import pytest

from elc.learning.silent_evidence import ContentBackedTargetSupply
from elc.learning.target_resolution import (
    NO_TARGET,
    MatchVia,
    TargetSupplyFacts,
    normalize_form,
    resolve_target,
    slots_can_discriminate,
)

HEDGE = TargetSupplyFacts(
    "RESOURCE",
    "res-hedge-i-think",
    ("I think it is going to rain.",),
    ("It might rain.", "I'd say it will rain."),
    # v3-1 后的 i-think 槽位形态：单组公式词（think/guess/reckon）——
    # 示例句话题词（rain）已按「槽位 = 目标自身的词汇材料」判据移除。
    (("think", "guess", "reckon"),),
)
TOPIC = TargetSupplyFacts(
    "CAPABILITY",
    "cap-disc-topic-shift",
    ("Speaking of which, how was the meeting?",),
    ("On that note, how was the meeting?",),
    (("meeting",),),
)
CORPUS = (HEDGE, TOPIC)


def _resolved(utterance: str, facts: tuple[TargetSupplyFacts, ...] = CORPUS):
    resolution = resolve_target(utterance, facts)
    assert resolution is not NO_TARGET, f"{utterance!r} unexpectedly missed"
    return resolution


# ---------------------------------------------------------------------------
# ① normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("  Hello  THERE ", "hello there"),
        ("I THINK it is Going to Rain.", "i think it is going to rain"),
        ("line\nbreak\tand   spaces", "line break and spaces"),
        ("...punctuation edges!?", "punctuation edges"),
        ("", ""),
        ("   ", ""),
        ("I'd say it will rain.", "i'd say it will rain"),
    ),
)
def test_normalization_is_casefold_collapse_and_edge_strip(
    text: str, expected: str
) -> None:
    assert normalize_form(text) == expected


def test_normalization_is_idempotent() -> None:
    for text in ("  Hello  THERE ", "I think it is going to rain.", "a!?"):
        once = normalize_form(text)
        assert normalize_form(once) == once


def test_internal_punctuation_is_never_loosened() -> None:
    assert normalize_form("Right, I see.") == "right, i see"
    assert normalize_form("Right I see.") != normalize_form("Right, I see.")


# ---------------------------------------------------------------------------
# ② rule 1 — canonical form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "utterance",
    (
        "I think it is going to rain.",
        "i think it is going to rain",
        "I THINK IT IS GOING TO RAIN",
        "I  think   it is going to rain.",
        "Well, I think it is going to rain tomorrow.",
        "I think it is going to rain!",
        "I think it is going to rain?",
        "I think it is going to rain, so bring a coat.",
    ),
)
def test_canonical_form_occurs_case_and_punctuation_tolerant(
    utterance: str,
) -> None:
    resolution = _resolved(utterance)
    assert resolution.target_id == "res-hedge-i-think"
    assert resolution.target_type == "RESOURCE"
    assert resolution.matched_via is MatchVia.CANONICAL_FORM
    assert resolution.matched_form == "I think it is going to rain."


@pytest.mark.parametrize(
    "utterance",
    (
        "It is rainy today.",
        "I think it is going to rains.",
        "I think it is going to",
    ),
)
def test_canonical_form_requires_the_whole_span(utterance: str) -> None:
    """Truncations and word-char neighbours are misses for the canonical
    span.

    A rounded "I think it is going to rains." is the boundary case worth
    naming: the span occurs, but its right neighbour is a word character, so
    it is not the form — it is a different inflection, and this slice does
    not fuzzily equate the two. (v3-1 note: the slot class may still claim
    the utterance for the hedge's own card — the boundary pinned here is
    the *form* class, not the card.)
    """

    resolution = resolve_target(utterance, CORPUS)
    assert resolution is NO_TARGET or (
        resolution.matched_via is MatchVia.REQUIRED_SLOTS
    ), utterance


def test_a_bare_slot_shaped_sentence_is_a_slot_match_not_a_form_match() -> None:
    """"think it is going to rain" is not the canonical span (the form starts
    with "I"), but it does cover the slot group — so it resolves through
    rule 3, which is exactly the priority order doing its job."""

    resolution = _resolved("think it is going to rain")
    assert resolution.matched_via is MatchVia.REQUIRED_SLOTS


def test_a_quoted_form_inside_a_longer_sentence_still_matches() -> None:
    """The resolver is a span extractor, not an intent reader."""

    resolution = _resolved("So I think it is going to rain is what she said")
    assert resolution.matched_via is MatchVia.CANONICAL_FORM


def test_blank_utterance_never_matches() -> None:
    assert resolve_target("", CORPUS) is NO_TARGET
    assert resolve_target("   \n\t ", CORPUS) is NO_TARGET


# ---------------------------------------------------------------------------
# ③ rule 2 — alternative realization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "utterance",
    ("It might rain.", "it might rain later today", "I'd say it will rain."),
)
def test_alternative_realization_matches_when_no_canonical_does(
    utterance: str,
) -> None:
    resolution = _resolved(utterance)
    assert resolution.target_id == "res-hedge-i-think"
    assert resolution.matched_via is MatchVia.ALTERNATIVE_REALIZATION


def test_alternative_apostrophe_is_not_loosened() -> None:
    assert resolve_target("id say it will rain", CORPUS) is NO_TARGET


# ---------------------------------------------------------------------------
# ④ rule 3 — required slots
# ---------------------------------------------------------------------------


def test_slots_need_every_group() -> None:
    """The AND semantics on a multi-group key: every group must be covered.
    (The probe fact carries two groups the way the corpus's multi-group
    keys do; i-think's own key is single-group since v3-1.)"""

    fact = TargetSupplyFacts(
        "RESOURCE",
        "res-probe-two-groups",
        (),
        (),
        (("alpha", "beta"), ("gamma", "delta")),
    )
    covered = resolve_target("beta and then delta", (fact,))
    assert covered is not NO_TARGET
    assert covered.matched_via is MatchVia.REQUIRED_SLOTS
    assert covered.matched_form == "beta delta"
    assert (
        resolve_target("beta and then epsilon", (fact,)) is NO_TARGET
    )


def test_slots_render_takes_the_first_present_member_per_group() -> None:
    fact = TargetSupplyFacts(
        "RESOURCE",
        "res-probe-two-groups",
        (),
        (),
        (("alpha", "beta"), ("gamma", "delta")),
    )
    resolution = resolve_target("beta and delta", (fact,))
    assert resolution.matched_form == "beta delta"


def test_slots_miss_when_one_group_is_uncovered() -> None:
    assert resolve_target("It is going to rain tomorrow.", CORPUS) is NO_TARGET
    assert resolve_target("We will leave soon.", CORPUS) is NO_TARGET


def test_slot_tokens_are_whole_tokens() -> None:
    assert resolve_target("It is rainy today.", CORPUS) is NO_TARGET
    assert resolve_target("I am guessing about the rain.", CORPUS) is NO_TARGET


def test_slot_tokens_survive_punctuation_between_them() -> None:
    resolution = _resolved("rain, i guess")
    assert resolution.matched_via is MatchVia.REQUIRED_SLOTS


def test_a_fact_without_slots_never_slot_matches() -> None:
    fact = TargetSupplyFacts("RESOURCE", "res-no-slots", ("unrelated form",))
    assert resolve_target("rain and think", (fact, HEDGE)).target_id == (
        "res-hedge-i-think"
    )
    assert resolve_target("rain and think", (fact,)) is NO_TARGET


# ---------------------------------------------------------------------------
# ④b the slot rule's false-positive boundary (F-1, declared)
# ---------------------------------------------------------------------------


SINGLE_TOKEN_SLOT_SENTENCES = (
    ("I want to see that movie.", "see"),
    ("See you tomorrow!", "see"),
    ("What do you mean?", "mean"),
    ("The meeting starts at nine.", "meeting"),
    ("You should clarify the requirement.", "clarify"),
)


def test_a_single_one_token_group_is_a_bare_word_check() -> None:
    """The declared boundary: one group with one token has no false-positive
    lower bound — "see" is a word, not a target form."""

    fact = TargetSupplyFacts("CAPABILITY", "cap-see", (), (), (("see",),))
    for sentence, _ in SINGLE_TOKEN_SLOT_SENTENCES:
        assert resolve_target(sentence, (fact,)) is NO_TARGET, sentence


def test_a_single_multi_token_group_still_slot_matches() -> None:
    """The other arm of the threshold: one group of alternatives is a real
    key (a co-occurrence of the group's members is not a bare word)."""

    fact = TargetSupplyFacts(
        "CAPABILITY", "cap-frame", (), (), (("think", "guess", "reckon"),)
    )
    resolution = resolve_target("I think so.", (fact,))
    assert resolution is not NO_TARGET
    assert resolution.matched_via is MatchVia.REQUIRED_SLOTS
    assert resolution.matched_form == "think"


def test_the_corpus_single_token_keys_never_drive_a_slot_match(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """The corpus keys whose whole slot key is one word never drive a slot
    match. The probe sample covers the four originals (cap-interact-
    backchannel "see", cap-ref-ask-clarification "mean",
    cap-disc-topic-shift "meeting") plus one v3-1 addition
    (res-pragmatic-could-you-clarify "clarify" — the v3-1 slot rewrite
    turned 31 formerly multi-group keys into single-token keys, whose
    exclusion the count pair in
    test_every_discriminating_corpus_slot_key_resolves_to_its_own_target
    pins corpus-wide; W-5's four were res-discourse-anyway "anyway",
    res-hedge-i-guess "guess", res-pragmatic-got-it "got",
    res-pragmatic-i-see "see", and C3-d's res-pragmatic-right moved from
    "following" to "right" in v3-1). With the whole corpus present, the
    exact sentences the reviewer's probe used resolve to NO_TARGET."""

    facts = _corpus_facts(silent_supply)
    for sentence, token in SINGLE_TOKEN_SLOT_SENTENCES:
        fact = next(
            (item for item in facts if token in item.required_slots[0]),
            None,
        )
        assert fact is not None, token
        assert len(fact.required_slots) == 1 and len(fact.required_slots[0]) == 1
        assert resolve_target(sentence, facts) is NO_TARGET, sentence
    # …and their canonical forms still match, through rule 1 only.
    resolution = _resolved("Right, I see.", facts)
    assert resolution.target_id == "cap-interact-backchannel"
    assert resolution.matched_via is MatchVia.CANONICAL_FORM


# ---------------------------------------------------------------------------
# ⑤ priority and tie-breaks
# ---------------------------------------------------------------------------


def test_canonical_beats_alternative_in_one_utterance() -> None:
    resolution = _resolved(
        "It might rain. Also, I think it is going to rain."
    )
    assert resolution.matched_via is MatchVia.CANONICAL_FORM
    assert resolution.matched_form == "I think it is going to rain."


def test_canonical_beats_slots_across_facts() -> None:
    resolution = _resolved("I think it is going to rain, I guess.")
    assert resolution.matched_via is MatchVia.CANONICAL_FORM


def test_alternative_beats_slots_across_facts() -> None:
    resolution = _resolved("It might rain, I guess.")
    assert resolution.matched_via is MatchVia.ALTERNATIVE_REALIZATION


def test_the_longest_form_of_the_matching_class_wins() -> None:
    short = TargetSupplyFacts("RESOURCE", "res-short", ("going to rain.",))
    long = TargetSupplyFacts(
        "RESOURCE", "res-long", ("I think it is going to rain.",)
    )
    resolution = _resolved("I think it is going to rain.", (short, long))
    assert resolution.target_id == "res-long"
    assert resolution.target_id == "res-long"


def test_form_ties_break_on_the_smallest_target_id() -> None:
    aaa = TargetSupplyFacts("RESOURCE", "res-aaa", ("same words here",))
    bbb = TargetSupplyFacts("RESOURCE", "res-bbb", ("same words here",))
    assert _resolved("same words here", (bbb, aaa)).target_id == "res-aaa"


def test_slot_matches_break_on_the_smallest_target_id() -> None:
    aaa = TargetSupplyFacts(
        "RESOURCE", "res-aaa", (), (), (("alpha",), ("beta",))
    )
    bbb = TargetSupplyFacts(
        "RESOURCE", "res-bbb", (), (), (("alpha",), ("beta",))
    )
    assert _resolved("alpha and beta", (bbb, aaa)).target_id == "res-aaa"


def test_resolution_does_not_depend_on_fact_order() -> None:
    utterance = "I think it is going to rain, I guess."
    first = _resolved(utterance, CORPUS)
    second = _resolved(utterance, tuple(reversed(CORPUS)))
    assert first == second


# ---------------------------------------------------------------------------
# ⑥ guards: kind filter, empty supply, NO_TARGET contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ("SENSE", "LEXICAL_ENTRY", "FORM", "EXAMPLE"))
def test_a_kind_outside_the_canonical_pair_never_matches(kind: str) -> None:
    alien = TargetSupplyFacts(
        kind, "alien-1", ("I think it is going to rain.",), (), (("rain",),)
    )
    assert resolve_target("I think it is going to rain.", (alien,)) is NO_TARGET
    assert resolve_target("rain", (alien,)) is NO_TARGET


def test_an_empty_supply_answers_no_target() -> None:
    assert resolve_target("I think it is going to rain.", ()) is NO_TARGET


def test_no_target_is_the_none_sentinel_with_no_side_effects() -> None:
    facts = (HEDGE,)
    before = tuple(facts)
    result = resolve_target("nothing of the kind", facts)
    assert result is NO_TARGET
    assert facts == before, "the resolver mutated its input"


# ---------------------------------------------------------------------------
# ⑦ corpus truth table (the real content.db, through the supply face)
# ---------------------------------------------------------------------------


def _corpus_facts(supply: ContentBackedTargetSupply) -> tuple:
    read = supply.facts()
    assert not hasattr(read, "error"), read
    return read.value


def test_every_corpus_canonical_form_resolves_to_its_own_target(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    facts = _corpus_facts(silent_supply)
    assert len(facts) == 108
    for fact in facts:
        assert fact.canonical_forms, fact.target_id
        for form in fact.canonical_forms:
            resolution = _resolved(form, facts)
            assert resolution.target_id == fact.target_id, (fact, form)
            assert resolution.target_type == fact.target_type
            assert resolution.matched_via is MatchVia.CANONICAL_FORM


#: The closed W-5 cross-match list: alternative realizations that *contain*
#: one of the W-5 bare canonical formulas ("I think.", "I see."), so the
#: canonical class — which outranks the alternative class by the fixed
#: priority order — now resolves them to the formula's own target. Declared,
#: not claimed away: everything outside this exact (fact, form) pair list
#: still resolves to its own target via ALTERNATIVE_REALIZATION (or, for the
#: ten own-target upgrades in W5_ALTERNATIVE_VIA_UPGRADES below, via the
#: formula's CANONICAL_FORM), and each listed pair is pinned to its exact
#: new resolution below.
W5_ALTERNATIVE_CROSS_MATCHES = {
    ("cap-eval-hedged-opinion", "It could be too late, I think."):
        ("res-hedge-i-think", MatchVia.CANONICAL_FORM, "I think."),
    ("cap-interact-backchannel", "Uh-huh, I see."):
        ("res-pragmatic-i-see", MatchVia.CANONICAL_FORM, "I see."),
    (
        "res-pragmatic-i-see-your-point-but",
        "I see your point, but the timeline doesn't work.",
    ):
        ("res-pragmatic-i-see", MatchVia.CANONICAL_FORM, "I see."),
    (
        "res-pragmatic-no-offense-but",
        "No offense, but I think we should start again.",
    ):
        ("res-hedge-i-think", MatchVia.CANONICAL_FORM, "I think."),
}

#: The closed W-5 same-target upgrade list: alternatives that contain their
#: *own* entity's new bare formula, so the same target wins through the
#: canonical class instead of the alternative class. The target is
#: unchanged; only the rule that fired moved (ten of the twelve W-5
#: entities, plus v3-1's i-think evidence-declared realization; only
#: anyway's alternatives contain no bare formula).
W5_ALTERNATIVE_VIA_UPGRADES = {
    (
        "res-discourse-before-i-forget",
        "Before I forget, did you pay the invoice?",
    ):
        "Before I forget.",
    (
        "res-discourse-moving-on",
        "Moving on to the next item, let's look at the timeline.",
    ):
        "Moving on.",
    ("res-hedge-i-guess", "It's going to rain, I guess."):
        "I guess.",
    # v3-1: i-think's key face gained the evidence-declared accepted
    # realization as an alternative row; it carries the entity's own bare
    # formula, so the canonical class fires (same shape as i-guess above).
    ("res-hedge-i-think", "It is going to rain, I think."):
        "I think.",
    ("res-hedge-more-or-less", "The two estimates match more or less."):
        "More or less.",
    (
        "res-pragmatic-come-again",
        "Come again — did you say four thirty or four fifteen?",
    ):
        "Come again?",
    ("res-pragmatic-fair-enough", "Fair enough, we'll do it your way this time."):
        "Fair enough.",
    ("res-pragmatic-got-it", "Got it, thanks — I'll send the file tonight."):
        "Got it.",
    ("res-pragmatic-i-see", "I see. Please go on."):
        "I see.",
    ("res-pragmatic-no-way", "No way — he ran the whole marathon?"):
        "No way!",
    ("res-pragmatic-that-makes-sense", "That makes sense to me."):
        "That makes sense.",
}


def test_every_corpus_alternative_realization_resolves_to_its_own_target(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """Every corpus §24.5 SUPPORTING row still resolves to its own target —
    with the W-5 rule-class movement declared: four alternative realizations
    containing another entity's bare formula now resolve to that entity
    (CANONICAL_FORM outranks ALTERNATIVE_REALIZATION), and eleven
    alternatives containing their own entity's bare formula keep their
    target through the canonical class instead (旧真值 P5-2: own target via
    ALTERNATIVE_REALIZATION for all 102; 新真值 W-5: 88 unchanged, 10
    same-target via CANONICAL_FORM, 4 cross-target via CANONICAL_FORM;
    新真值 v3-1: 88 unchanged, 11 same-target (i-think's evidence-declared
    "It is going to rain, I think." joined the list), 4 cross-target —
    every deviation pinned to its exact pair above; 新真值 queue-2 (2026-10):
    the three new capability realizations add one SUPPORTING row each
    (103 → 106), all resolving to their own target via
    ALTERNATIVE_REALIZATION)."""

    facts = _corpus_facts(silent_supply)
    seen = 0
    cross = 0
    upgraded = 0
    for fact in facts:
        for form in fact.alternative_realizations:
            seen += 1
            resolution = _resolved(form, facts)
            exception = W5_ALTERNATIVE_CROSS_MATCHES.get(
                (fact.target_id, form)
            )
            upgrade = W5_ALTERNATIVE_VIA_UPGRADES.get(
                (fact.target_id, form)
            )
            if exception is not None:
                cross += 1
                target_id, via, matched_form = exception
                assert resolution.target_id == target_id, (fact, form)
                assert resolution.matched_via is via, (fact, form)
                assert resolution.matched_form == matched_form, (fact, form)
            elif upgrade is not None:
                upgraded += 1
                assert resolution.target_id == fact.target_id, (fact, form)
                assert (
                    resolution.matched_via is MatchVia.CANONICAL_FORM
                ), (fact, form)
                assert resolution.matched_form == upgrade, (fact, form)
            else:
                assert resolution.target_id == fact.target_id, (fact, form)
                assert (
                    resolution.matched_via is MatchVia.ALTERNATIVE_REALIZATION
                ), (fact, form)
    assert seen == 106, (
        "the corpus's §24.5 SUPPORTING rows (C2-a 13 + C2-b 17 + C3-a 18 +"
        " C3-b 18 + C3-c 18 + C3-d 18 + v3-1's i-think"
        " evidence-declared realization + queue-2's three capability"
        " realizations)"
    )
    assert cross == len(W5_ALTERNATIVE_CROSS_MATCHES)
    assert upgraded == len(W5_ALTERNATIVE_VIA_UPGRADES)
    # 旧真值 (W-5): 4 + 10 = 14. 新真值 (v3-1): 4 + 11 = 15 — i-think's
    # evidence-declared realization joined the same-target upgrade list.
    assert cross + upgraded == 15


def test_every_discriminating_corpus_slot_key_resolves_to_its_own_target(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """Every corpus §24.5 slot key with a false-positive lower bound (≥2
    groups, or a multi-token group) still resolves through rule 3 when its
    groups are covered. The single-token keys are the declared
    exception and are pinned by
    test_the_corpus_single_token_keys_never_drive_a_slot_match. The pair
    below is a count over the corpus, so it moves with the corpus (旧真值
    C2-a: 11 discriminating of 14; C2-b: 30 of 33; C3-b: 66 of 69;
    C3-c: 84 of 87; C3-d: 101 of 105; W-5: 97 of 105 — the W-5 key-face
    cut replaced four formerly multi-group keys with the bare formula's
    single one-token group; 新真值 v3-1: 67 of 105 — the v3-1 slot rewrite
    （槽位 = 目标自身的词汇材料）rewrote 60 keys, 31 of which became
    single-token keys and dropped out of the discriminating set; 新真值
    queue-2: 67 of 108 — the three new capability realizations carry
    single-token keys and join the excluded set, 38 → 41)."""

    facts = _corpus_facts(silent_supply)
    discriminating = 0
    excluded = 0
    for fact in facts:
        assert fact.required_slots, fact.target_id
        if not slots_can_discriminate(fact):
            excluded += 1
            continue
        discriminating += 1
        utterance = " and ".join(group[0] for group in fact.required_slots)
        resolution = _resolved(utterance, facts)
        assert resolution.target_id == fact.target_id, (fact, utterance)
        assert resolution.matched_via is MatchVia.REQUIRED_SLOTS
        assert resolution.matched_form == " ".join(
            group[0] for group in fact.required_slots
        )
    print(
        f"[probe] discriminating slot keys -> {discriminating};"
        f" excluded single-token keys -> {excluded}"
    )
    assert (discriminating, excluded) == (67, 41)


def test_the_corpus_resolves_to_both_kinds(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    facts = _corpus_facts(silent_supply)
    kinds = {_resolved(fact.canonical_forms[0], facts).target_type for fact in facts}
    assert kinds == {"RESOURCE", "CAPABILITY"}


def test_ordinary_chat_does_not_trip_the_corpus_keys(
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """The §2.4 product state on a hand-picked sample: these ordinary turns
    have no target. The sample is illustrative, NOT a measured false-positive
    rate — the slot rule's declared boundary (single-token keys excluded;
    ≥2-group keys requiring a co-occurrence) is the actual bound, pinned by
    the tests around it, and a measured rate needs the §8.1 R4 detection
    policy this slice only seeds."""

    facts = _corpus_facts(silent_supply)
    for utterance in (
        "I like this cafe.",
        "Nice to meet you.",
        "Hello there.",
        "The weather is terrible today.",
        "I want to see that movie.",
        "What do you mean?",
        "The meeting starts at nine.",
        "Let me check my calendar.",
    ):
        assert resolve_target(utterance, facts) is NO_TARGET, utterance
