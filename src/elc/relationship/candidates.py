"""The deterministic relationship candidate producer v1 (cs-1).

The ``RelationshipCandidateProvider`` protocol (elc.relationship.projection)
had exactly two implementations before this cut: test-side scripted classes
and ``None`` — so the shipped assembly proposed nothing and the
relationship memory stayed empty forever (the audit's producer break,
断点①). This module is the first production provider: a **deterministic**,
high-precision bilingual pattern extractor that reads one canonical turn's
user utterance and declares what the user plainly stated about themselves.

Honesty about coverage (registered, not a defect): a fixed pattern set
covers only the plain self-introduction shapes below. Everything else a
friend lets slip about their life is simply not proposed — a small honest
memory beats a large invented one. The inventory IS the contract:

- ZH 我叫X / 我的名字(是|叫)X / 我姓X → "The user's name is X." /
  "The user's surname is X."
- ZH 我是做X的 → "The user works as X."
- ZH 我在X工作 / 我在X上班 → "The user works at X."
- ZH 我家在X / 我住在X → "The user lives in X."
- ZH 我来自X → "The user is from X."
- ZH 我喜欢X / 我爱好X → "The user likes X."
- EN "my name is X" → "The user's name is X."
- EN "I work as (a/an) X" → "The user works as X."
- EN "I work at/in X" → "The user works at X."
- EN "I live in X" → "The user lives in X."
- EN "I'm from X" / "I am from X" → "The user is from X."
- EN "I like X" / "I love X" → "The user likes X."

Discipline: the provider is a *source*, never an authority. Every candidate
it hands back walks the Recorder's full refusal order (the BF-05
sensitivity gate, the command-turn red line, the user-turn provenance rule,
ref resolution) and the Domain Controller's validate / gate / dedupe faces —
nothing here writes, bypasses or pre-clears any of it (the write face runs
the same gate again; defence in depth is the pipeline's own design). The
candidates are shaped to pass those gates honestly: ``USER_STATED_FACT``
type and provenance (the user really said it — the slot is quoted from the
utterance), the ``PERSONAL`` BF-05 class with the ordinary
``VALIDATED_DOMAIN_WRITE`` authorization, ``confidence=None`` (a statement
is not a scored inference), and the real user turn as the one cited id.

Pure module: regex over text, no storage, no clock, no randomness; the
same utterance always yields the same candidates in the same order
(declaration order, first match per pattern, duplicate contents dropped by
the domain's own normalize rule).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern

from elc.conversation.types import CanonicalTurnSlice
from elc.platform.types import Ok, Result
from elc.relationship.recorder import RelationshipMemoryCandidate
from elc.relationship.types import (
    MemoryProvenance,
    RelationshipMemoryType,
)
from elc.relationship.validation import normalize_memory_content

__all__ = ["PatternCandidateProvider"]


#: The slot texts that are never facts: bare pronouns and the vague
#: quantifiers a "I like it" would leave behind. Whole-slot matches only
#: (casefolded) — a slot merely *containing* one of these words is fine.
_SLOT_STOPWORDS = frozenset(
    {
        "it",
        "that",
        "this",
        "them",
        "him",
        "her",
        "you",
        "me",
        "us",
        "everything",
        "nothing",
        "something",
        "anything",
        "他们",
        "她们",
        "它们",
        "这个",
        "那个",
        "你",
        "我",
        "什么",
        "东西",
    }
)

#: Characters stripped from both ends of every captured slot (the sentence
#: punctuation a loose boundary leaves behind) before the slot is judged.
_SLOT_EDGE_CHARS = " \t。，、；：！？!?,.;:…—·\"'“”‘’()（）[]【】《》<>~～"


@dataclass(frozen=True)
class _Pattern:
    """One extraction pattern: its regex, and the canonical sentence the
    captured slot becomes. The declaration order is the proposal order."""

    regex: "Pattern[str]"
    template: str


def _compiled(expression: str) -> "Pattern[str]":
    return re.compile(expression, re.IGNORECASE)


#: The boundary that ends an EN slot: sentence punctuation, the utterance's
#: end, or a coordinating conjunction — "I work as a teacher and I live in
#: Leeds" proposes the teacher, not the whole clause after it (precision
#: first: a half capture beats a wrong one).
_EN_SLOT_END = r"(?=$|[,.;!?]|\b(?:and|or|but|then|because|so)\b)"


#: The pattern inventory, in proposal order (the module docstring is the
#: prose form of this table; the table is what runs).
_PATTERNS: tuple[_Pattern, ...] = (
    # -- ZH: name -----------------------------------------------------
    _Pattern(
        _compiled(r"我叫(?P<slot>[\w\u4e00-\u9fff·]{1,20})"),
        "The user's name is {slot}.",
    ),
    _Pattern(
        _compiled(r"我的名字(?:是|叫)(?P<slot>[\w\u4e00-\u9fff·]{1,20})"),
        "The user's name is {slot}.",
    ),
    _Pattern(
        _compiled(r"我姓(?P<slot>[\u4e00-\u9fff]{1,2})"),
        "The user's surname is {slot}.",
    ),
    # -- ZH: work -----------------------------------------------------
    _Pattern(
        _compiled(r"我是做(?P<slot>.{1,20}?)的(?:工作)?(?=$|[，。！？!?,.;；\s])"),
        "The user works as {slot}.",
    ),
    _Pattern(
        _compiled(r"我在(?P<slot>[^\s，。！？!?,.;；]{1,20})(?:工作|上班)"),
        "The user works at {slot}.",
    ),
    # -- ZH: place ----------------------------------------------------
    _Pattern(
        _compiled(r"我家在(?P<slot>[^\s，。！？!?,.;；]{1,20})"),
        "The user lives in {slot}.",
    ),
    _Pattern(
        _compiled(r"我住在(?P<slot>[^\s，。！？!?,.;；]{1,20})"),
        "The user lives in {slot}.",
    ),
    _Pattern(
        _compiled(r"我来自(?P<slot>[^\s，。！？!?,.;；]{1,20})"),
        "The user is from {slot}.",
    ),
    # -- ZH: likes ----------------------------------------------------
    _Pattern(
        _compiled(r"我喜欢(?P<slot>.{1,30}?)(?=$|[，。！？!?,.;；])"),
        "The user likes {slot}.",
    ),
    _Pattern(
        _compiled(r"我爱好(?P<slot>.{1,30}?)(?=$|[，。！？!?,.;；])"),
        "The user likes {slot}.",
    ),
    # -- EN: name -----------------------------------------------------
    _Pattern(
        _compiled(
            r"\bmy name is (?P<slot>[A-Za-z][A-Za-z'\- ]{1,29}?)"
            + _EN_SLOT_END
        ),
        "The user's name is {slot}.",
    ),
    # -- EN: work -----------------------------------------------------
    _Pattern(
        _compiled(
            r"\bI work as (?:an |a )?(?P<slot>[A-Za-z][A-Za-z'\- ]{1,29}?)"
            + _EN_SLOT_END
        ),
        "The user works as {slot}.",
    ),
    _Pattern(
        _compiled(
            r"\bI work (?:at|in) (?P<slot>[A-Za-z0-9][A-Za-z0-9'\- ]{1,29}?)"
            + _EN_SLOT_END
        ),
        "The user works at {slot}.",
    ),
    # -- EN: place ----------------------------------------------------
    _Pattern(
        _compiled(
            r"\bI live in (?P<slot>[A-Za-z0-9][A-Za-z0-9'\- ]{1,29}?)"
            + _EN_SLOT_END
        ),
        "The user lives in {slot}.",
    ),
    _Pattern(
        _compiled(
            r"\bI(?:'m| am) from (?P<slot>[A-Za-z0-9][A-Za-z0-9'\- ]{1,29}?)"
            + _EN_SLOT_END
        ),
        "The user is from {slot}.",
    ),
    # -- EN: likes ----------------------------------------------------
    _Pattern(
        _compiled(
            r"\bI like (?P<slot>[A-Za-z0-9][A-Za-z0-9'\- ]{1,39}?)"
            + _EN_SLOT_END
        ),
        "The user likes {slot}.",
    ),
    _Pattern(
        _compiled(
            r"\bI love (?P<slot>[A-Za-z0-9][A-Za-z0-9'\- ]{1,39}?)"
            + _EN_SLOT_END
        ),
        "The user likes {slot}.",
    ),
)


def _clean_slot(raw: str) -> str | None:
    """One captured slot, judged: the cleaned text, or ``None`` to reject.

    Rejections (all registered here, never silent): a slot that empties
    under edge-stripping, carries a line break or tab, runs past 40
    characters, or is one of the bare-pronoun stopwords — none of those is
    a plain self-stated fact, and a provider that guessed would be exactly
    the low-precision extractor this v1 refuses to be.
    """

    slot = str(raw).strip(_SLOT_EDGE_CHARS)
    if not slot:
        return None
    if any(character in slot for character in "\r\n\t"):
        return None
    if len(slot) > 40:
        return None
    if slot.casefold() in _SLOT_STOPWORDS:
        return None
    return slot


class PatternCandidateProvider:
    """The production ``RelationshipCandidateProvider`` v1 (the protocol
    face, structurally satisfied — see elc.relationship.projection).

    Stateless by design: one pure function over the turn's user utterance
    (``normalized_content`` falling back to ``raw_content``, the same
    reading the Recorder applies). No provider call, no network, no model —
    the v1 producer is deterministic code, so the same words always propose
    the same memories.
    """

    def candidates_for(
        self, turn: CanonicalTurnSlice
    ) -> Result[tuple[RelationshipMemoryCandidate, ...]]:
        """Extract the turn's plainly stated facts as declared candidates.

        Always ``Ok``: extraction cannot fail — an utterance with no
        pattern simply proposes nothing (the honest empty result the
        protocol's docstring describes for the no-provider assembly, now
        produced by a provider that read the turn and found nothing).
        """

        utterance = (
            turn.user_turn.normalized_content or turn.user_turn.raw_content
        )
        candidates: list[RelationshipMemoryCandidate] = []
        seen: set[str] = set()
        user_turn_id = str(turn.user_turn.user_turn_id)
        for pattern in _PATTERNS:
            match = pattern.regex.search(utterance)
            if match is None:
                continue
            slot = _clean_slot(match.group("slot"))
            if slot is None:
                continue
            content = pattern.template.format(slot=slot)
            fingerprint = normalize_memory_content(content)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            candidates.append(
                RelationshipMemoryCandidate(
                    memory_type=RelationshipMemoryType.USER_STATED_FACT,
                    provenance=MemoryProvenance.USER_STATED_FACT,
                    content=content,
                    cited_message_ids=(user_turn_id,),
                )
            )
        return Ok(tuple(candidates))
