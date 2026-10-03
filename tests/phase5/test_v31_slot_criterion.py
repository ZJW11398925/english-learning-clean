"""v3-1 — the slot-criterion rewrite: 槽位 = 目标自身的词汇材料.

The dogfood P0-1 evidence (the four-findings research report,
docs/research/2026-10-02-v31-teaching-card-findings.md): a semantically
correct hedge attempt ("I think it depends on the weather.") judged
FAILURE because the i-think key's required_slots carried the *example
sentence's* topic word ("rain") as an AND group — the key demanded
re-stating the example's scene, not producing the target's own formula.
This cut rewrote sixty RESOURCE key faces so every slot group is the
taught expression's own lexical material (formula words, declared
alternative collocates, the frame's own function words), and gave i-think
the evidence-declared accepted realization ("It is going to rain,
I think.") as an alternative row so its declaration face and its judging
face agree.

What this file pins:

1. the rewritten slot face, verbatim, for all sixty documents (the
   machine truth of the audit table; the prewritten dict is the pin);
2. the named negatives: the P0 trio's scene words (rain / design /
   answer) appear in no slot group of their entities;
3. the P0-1 judgment, replayed through the real evaluator over the real
   built key: the depends-sentence is PARTIAL (再答可续), the canonical
   sentence SUCCESS, all three alternative rows ALTERNATIVE_SUCCESS, a
   hedge-free sentence FAILURE, and the honest boundary ("I don't think
   so." — the hedge present, the claim reversed) PARTIAL;
4. the corpus truth stands: readiness 52 × R4 + 48 × R1 + 5 × None and
   the provenance derivation are untouched by a slot rewrite (they are
   pinned in test_w5_key_judgeability and stay green).
"""

from __future__ import annotations

import pytest

from elc.content.store import ContentStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.teaching.evaluator import evaluate_attempt
from elc.teaching.types import AttemptOutcome

#: The rewritten slot face, verbatim (v3-1's audit table, plain id sort
#: order — the N-C3C-2 convention). One row per rewritten document.
#: v3-d 随迁：其中十一个动词槽位 target 的屈折组面（evidence 明文声明的
#: forms）移交 test_v3d_inflection_slots.py 承载——本表只钉 v3-1 重写
#: 后未再触碰的四十九行。
V31_SLOT_FACE: dict[str, tuple[tuple[str, ...], ...]] = {
    "res-discourse-by-the-way": (("way",),),
    "res-discourse-long-story-short": (("long",), ("story",), ("short",)),
    "res-discourse-on-another-note": (("note",), ("another", "different")),
    "res-discourse-speaking-of-which": (("speaking",),),
    "res-discourse-that-brings-me-to": (("brings",),),
    "res-discourse-that-reminds-me": (("reminds",), ("me",)),
    "res-discourse-to-be-honest": (("honest",),),
    "res-discourse-to-get-back-to-the-point": (("point",), ("back",)),
    "res-discourse-where-was-i": (("where",),),
    "res-frame-id-like-to": (("like",),),
    "res-frame-just-wondering": (("wondering",),),
    "res-frame-the-thing-is": (("thing",),),
    "res-frame-what-im-saying-is": (("saying",),),
    "res-frame-would-you-mind": (("mind",),),
    "res-hedge-as-far-as-i-know": (("know",),),
    "res-hedge-from-what-i-can-tell": (("tell",),),
    "res-hedge-i-think": (("think", "guess", "reckon"),),
    "res-hedge-if-im-not-mistaken": (("mistaken",),),
    "res-hedge-if-you-ask-me": (("ask",),),
    "res-hedge-im-not-sure": (("sure",),),
    "res-hedge-in-a-way": (("way",),),
    "res-hedge-it-depends": (("depends",),),
    "res-hedge-it-seems-to-me": (("seems",),),
    "res-hedge-not-really": (("really",),),
    "res-idiom-a-blessing-in-disguise": (("blessing",), ("disguise",)),
    "res-idiom-the-ball-is-in-your-court": (("ball",), ("court",)),
    "res-phrasal-put-off": (("off",), ("put",)),
    "res-pragmatic-are-you-saying": (("saying",),),
    "res-pragmatic-could-you": (("could", "would"),),
    "res-pragmatic-could-you-clarify": (("clarify",),),
    "res-pragmatic-go-on": (("go",), ("on",)),
    "res-pragmatic-i-hear-you-but": (("hear",),),
    "res-pragmatic-i-see-your-point-but": (("see",), ("point",)),
    "res-pragmatic-im-not-convinced": (("convinced",),),
    "res-pragmatic-let-me-make-sure": (("sure",), ("make",)),
    "res-pragmatic-no-offense-but": (("offense",),),
    "res-pragmatic-right": (("right",),),
    "res-pragmatic-run-that-by-me-again": (("run",), ("again",)),
    "res-pragmatic-sorry-to-interrupt": (("interrupt",), ("sorry",)),
    "res-pragmatic-thats-a-good-point-but": (("point",), ("good", "fair")),
    "res-pragmatic-thats-debatable": (("debatable",),),
    "res-pragmatic-up-to-a-point": (("point",),),
    "res-pragmatic-what-do-you-mean": (("mean",),),
    "res-pragmatic-what-was-that": (("what",), ("that",)),
    "res-pragmatic-with-all-due-respect": (("respect",),),
    "res-pragmatic-youre-kidding": (("kidding",),),
    "res-softener-a-bit": (("bit", "little"),),
    "res-softener-if-anything": (("anything",),),
    "res-softener-kind-of": (("kind", "sort", "bit"),),
}

#: The research report's named P0 trio: the example-scene topic words the
#: old keys demanded (and that no rewrite may bring back).
SCENE_WORD_BANS = {
    "res-hedge-i-think": "rain",
    "res-discourse-to-be-honest": "design",
    "res-phrasal-figure-out": "answer",
}


@pytest.fixture()
def provider(built_content_db):
    opened = ContentBackedTeachingTargetProvider(built_content_db)
    yield opened
    opened.close()


@pytest.mark.parametrize("target_id", sorted(V31_SLOT_FACE))
def test_the_rewritten_slot_face_reads_the_prewritten_table_verbatim(
    built_content_db, target_id: str
) -> None:
    store = ContentStore(built_content_db)
    try:
        view = store.get_teaching_content(target_id)
        assert isinstance(view.value.required_slots, tuple)
        slots = view.value.required_slots
    finally:
        store.close()
    assert slots == V31_SLOT_FACE[target_id]


@pytest.mark.parametrize(("target_id", "banned"), sorted(SCENE_WORD_BANS.items()))
def test_the_named_scene_words_are_in_no_slot_group(
    built_content_db, target_id: str, banned: str
) -> None:
    """The P0-1 criterion as a negative: the example sentence's topic word
    is not the target's lexical material, so it sits in no slot group."""

    store = ContentStore(built_content_db)
    try:
        view = store.get_teaching_content(target_id)
        slots = view.value.required_slots
    finally:
        store.close()
    tokens = {token for group in slots for token in group}
    assert banned not in tokens, (target_id, banned)


def test_i_thinks_key_face_is_the_rewritten_face(built_content_db) -> None:
    """i-think, the P0-1 target: the slot key is the hedge formula's own
    tokens, and the evidence-declared accepted realization
    ("It is going to rain, I think.") is now an alternative row — the
    declaration face and the judging face agree."""

    store = ContentStore(built_content_db)
    try:
        view = store.get_teaching_content("res-hedge-i-think")
        alternatives = view.value.alternative_realizations
    finally:
        store.close()
    assert alternatives == (
        "It might rain.",
        "I'd say it will rain.",
        "It is going to rain, I think.",
    )


def test_the_p01_attempt_judges_partial_on_the_real_key(
    provider: ContentBackedTeachingTargetProvider,
) -> None:
    """The dogfood P0-1 sentence, replayed: "I think it depends on the
    weather." covers the hedge formula's own slot group → PARTIAL (可再答),
    never the old whole-answer FAILURE."""

    resolved = provider.resolve("RESOURCE", "res-hedge-i-think")
    key = resolved.value.answer_key()
    evaluation = evaluate_attempt("I think it depends on the weather.", key)
    assert evaluation.outcome is AttemptOutcome.PARTIAL
    assert evaluation.basis == "REQUIRED_SLOT_COVERAGE"
    # …the rest of the §5 face on the rewritten key: the canonical sentence
    # still SUCCESS (monotonicity), the three alternative rows all
    # ALTERNATIVE_SUCCESS, a hedge-free sentence FAILURE.
    assert evaluate_attempt(
        "I think it is going to rain.", key
    ).outcome is AttemptOutcome.SUCCESS
    for form in (
        "It might rain.",
        "I'd say it will rain.",
        "It is going to rain, I think.",
    ):
        assert evaluate_attempt(form, key).outcome is (
            AttemptOutcome.ALTERNATIVE_SUCCESS
        ), form
    assert evaluate_attempt("I like rain.", key).outcome is (
        AttemptOutcome.FAILURE
    )
    # the honest boundary, declared: the hedge present with the claim
    # reversed is still a half-answer (the formula IS in the sentence) —
    # PARTIAL, not SUCCESS, and recorded here so the widened PARTIAL face
    # is a pinned fact, not a surprise.
    assert evaluate_attempt("I don't think so.", key).outcome is (
        AttemptOutcome.PARTIAL
    )
