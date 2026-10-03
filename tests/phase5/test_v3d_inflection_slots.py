"""v3-d — the F-1 inflection-family slot cut: 动词槽位补屈折组.

The v31R review registration (F-1 屈折回归族, commit bea4c19): the slot
coverage check is whole-token (evaluator.py ``_tokens``), so an inflected
verb falls out of a base-form-only slot group — "I made an effort to
finish the report on time." judged FAILURE against
res-colloc-make-an-effort even though the entity's own evidence declares
the inflected realization accepted (the forms block's PAST row and the
ACCEPTED_REALIZATIONS rule citing "made a real effort …").

The cut joins the declared material into the verb slot group (判据同
v3-1 A1「槽位 = 目标自身的词汇材料」——the declared forms ARE the
target's own lexical material), per entity, from that entity's own
evidence:

- res-colloc-make-an-effort  ("make","makes","made","making")
- res-colloc-raise-awareness ("raise","raises","raised","raising")
- res-colloc-make-progress   ("make","makes","made","making")
- res-colloc-save-time       ("save","saves","saved","saving")
- res-colloc-take-a-look     ("take","takes","took","taking")
- res-phrasal-bring-up       ("bring","brings","brought","bringing")
- res-phrasal-carry-on       ("carry","carries","carried","carrying")
- res-phrasal-come-up-with   ("come","came","coming")
- res-phrasal-figure-out     ("figure","figures","figured","figuring")
- res-phrasal-look-forward-to("look","looks","looked","looking")
- res-phrasal-run-out-of     ("run","ran","running")
- res-phrasal-work-out       ("work","works","worked","working")

登记面（本刀自己的边界）: res-colloc-make-sense **不**入本刀——its
"makes" would steal res-pragmatic-that-makes-sense's discriminating slot
key (P5-2's production guarantee, pinned in test_p5_2_target_resolution:
the smallest-id tie-break of ``_best_slot_match`` would hand the
"makes and sense" utterance to make-sense). The inflected faces of
make-sense stay a registered gap until that-makes-sense's key face is
redesigned.

What this file pins:

1. the new slot face, verbatim, for all twelve documents;
2. the F-1 three examples judged through the real evaluator over the
   real built key — PARTIAL (可再答), never the old whole-answer
   FAILURE — plus the family five (made progress / saves time / figured
   out / brought up / worked out);
3. the discriminative pairs stay honest: the negative probes still
   FAILURE, the canonical/alternative rows still SUCCESS /
   ALTERNATIVE_SUCCESS (monotonicity — the widened group cannot pull a
   whole-answer up);
4. the run-out-of family sentence "The printer ran out of ink." —
   PARTIAL via the group, while the canonical "We ran out of time."
   stays SUCCESS.
"""

from __future__ import annotations

import pytest

from elc.content.store import ContentStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.teaching.evaluator import evaluate_attempt
from elc.teaching.types import AttemptOutcome

#: The v3-d slot face, verbatim (plain id sort order — N-C3C-2).
V3D_SLOT_FACE: dict[str, tuple[tuple[str, ...], ...]] = {
    "res-colloc-make-an-effort": (
        ("effort",),
        ("make", "makes", "made", "making"),
    ),
    "res-colloc-make-progress": (
        ("progress",),
        ("make", "makes", "made", "making"),
    ),
    "res-colloc-raise-awareness": (
        ("awareness",),
        ("raise", "raises", "raised", "raising"),
    ),
    "res-colloc-save-time": (
        ("time",),
        ("save", "saves", "saved", "saving"),
    ),
    "res-colloc-take-a-look": (
        ("look",),
        ("take", "takes", "took", "taking"),
    ),
    "res-phrasal-bring-up": (
        ("up",),
        ("bring", "brings", "brought", "bringing"),
    ),
    "res-phrasal-carry-on": (
        ("on",),
        ("carry", "carries", "carried", "carrying"),
    ),
    "res-phrasal-come-up-with": (
        ("come", "came", "coming"),
        ("up",),
        ("with",),
    ),
    "res-phrasal-figure-out": (
        ("figure", "figures", "figured", "figuring"),
        ("out",),
    ),
    "res-phrasal-look-forward-to": (
        ("look", "looks", "looked", "looking"),
        ("forward",),
        ("to",),
    ),
    "res-phrasal-run-out-of": (
        ("run", "ran", "running"),
        ("out",),
        ("of",),
    ),
    "res-phrasal-work-out": (
        ("out",),
        ("work", "works", "worked", "working"),
    ),
}

#: The F-1 three (the v31R registration's named failures) + the family
#: five: (target, learner sentence) pairs that must judge PARTIAL.
F1_PARTIAL_CASES: tuple[tuple[str, str], ...] = (
    (
        "res-colloc-make-an-effort",
        "I made an effort to finish the report on time.",
    ),
    (
        "res-colloc-raise-awareness",
        "The campaign raised awareness of mental health.",
    ),
    (
        "res-phrasal-look-forward-to",
        "I am looking forward to seeing you.",
    ),
    ("res-colloc-make-progress", "I made progress on my English."),
    ("res-colloc-save-time", "Working from home saves time."),
    ("res-phrasal-figure-out", "I figured out the answer."),
    ("res-phrasal-bring-up", "She brought up an interesting point."),
    ("res-phrasal-work-out", "We worked out why it failed."),
    ("res-colloc-take-a-look", "Let me take a quick look at your email."),
    ("res-phrasal-come-up-with", "I came up with a new plan."),
    ("res-phrasal-carry-on", "He carried on with his work."),
    ("res-phrasal-run-out-of", "The printer ran out of ink."),
)

#: The discriminative pairs: a sentence without the target's own
#: material still misses — the widened groups are not a free pass.
F1_FAILURE_CASES: tuple[tuple[str, str], ...] = (
    ("res-colloc-make-an-effort", "I did an effort to finish on time."),
    ("res-colloc-raise-awareness", "The campaign ignored the problem."),
    ("res-phrasal-look-forward-to", "I look forward for seeing you."),
    ("res-colloc-make-progress", "I made a cake for my sister."),
    ("res-colloc-save-time", "I spent time on the report."),
    ("res-phrasal-figure-out", "I thought about the answer."),
    ("res-phrasal-bring-up", "She grew up in the countryside."),
    ("res-phrasal-work-out", "I worked at the café all summer."),
    ("res-colloc-take-a-look", "I gave it a long stare."),
    ("res-phrasal-come-up-with", "I came to the office early."),
    ("res-phrasal-carry-on", "He carried the box upstairs."),
    ("res-phrasal-run-out-of", "We ran towards the station."),
)


@pytest.fixture()
def provider(built_content_db):
    opened = ContentBackedTeachingTargetProvider(built_content_db)
    yield opened
    opened.close()


@pytest.mark.parametrize("target_id", sorted(V3D_SLOT_FACE))
def test_the_inflection_slot_face_reads_the_prewritten_table_verbatim(
    built_content_db, target_id: str
) -> None:
    store = ContentStore(built_content_db)
    try:
        view = store.get_teaching_content(target_id)
        assert isinstance(view.value.required_slots, tuple)
        slots = view.value.required_slots
    finally:
        store.close()
    assert slots == V3D_SLOT_FACE[target_id]


@pytest.mark.parametrize(("target_id", "text"), sorted(F1_PARTIAL_CASES))
def test_the_f1_family_sentences_judge_partial_on_the_real_key(
    provider: ContentBackedTeachingTargetProvider, target_id: str, text: str
) -> None:
    """The v31R F-1 registration, replayed: the inflected sentence covers
    the widened verb group → PARTIAL（可再答），never the old FAILURE."""

    resolved = provider.resolve("RESOURCE", target_id)
    key = resolved.value.answer_key()
    evaluation = evaluate_attempt(text, key)
    assert evaluation.outcome is AttemptOutcome.PARTIAL, (target_id, text)
    assert evaluation.basis == "REQUIRED_SLOT_COVERAGE"


@pytest.mark.parametrize(("target_id", "text"), sorted(F1_FAILURE_CASES))
def test_the_discriminative_pairs_still_miss(
    provider: ContentBackedTeachingTargetProvider, target_id: str, text: str
) -> None:
    """A sentence without the target's own material still falls through —
    the inflection groups never loosen the key into a token giveaway."""

    resolved = provider.resolve("RESOURCE", target_id)
    key = resolved.value.answer_key()
    evaluation = evaluate_attempt(text, key)
    assert evaluation.outcome is AttemptOutcome.FAILURE, (target_id, text)


@pytest.mark.parametrize("target_id", sorted(V3D_SLOT_FACE))
def test_the_answer_face_stays_monotone_over_the_widened_group(
    provider: ContentBackedTeachingTargetProvider, target_id: str
) -> None:
    """The canonical sentence still SUCCESSes and the alternative rows
    still ALTERNATIVE_SUCCESS — the widened group lives one level down
    and cannot pull a whole answer up."""

    resolved = provider.resolve("RESOURCE", target_id)
    key = resolved.value.answer_key()
    for form in key.canonical_forms:
        assert evaluate_attempt(form, key).outcome is AttemptOutcome.SUCCESS
    for form in key.alternative_realizations:
        assert evaluate_attempt(form, key).outcome is (
            AttemptOutcome.ALTERNATIVE_SUCCESS
        ), (target_id, form)
