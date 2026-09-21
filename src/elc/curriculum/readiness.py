"""Content readiness R0–R4 — the §8.1 ladder as a pure judgement.

docs/PRODUCT_CONTRACT.md §8.1 Content Readiness (Normative) defines the five
levels; docs/DATA_MODEL.md §24.10 repeats them and adds the one extra
requirement the canonical text spells out: "R4 必须包含可测试 detection
policy/fixtures/false-positive boundary". §8.1 also states the defaults
(:data:`DEFAULT_AVAILABILITY`) and the rule that closes the loop this slice
must not break: "V1 不把'模型自称高置信'自动视为 R4 等价认证".

This module decides one target's level from *facts about the artifact* and
reports, per level, which fact keys support it. It is pure: no IO, no
sqlite3, no clock, no randomness, no model call. The caller assembles
:class:`ReadinessFacts` from the content.db read face
(:meth:`elc.curriculum.store.CurriculumContentStore.readiness_facts`) and
this module only classifies.

Level → fact keys (cumulative: a level is reached when every key of that
level and of every level below it is present). Each entry quotes the
canonical phrase it implements:

R0 INDEXED — "source / assessment membership / canonical form 可定位"

- ``entity_row`` — the §24.1 ContentEntity row; its ``created_in_version`` is
  the source trace this artifact carries (§24.6 SourceSnapshot/Assertion is
  *not* carried by V1 — declared, not assumed).
- ``canonical_form`` — a §24.5 ExampleLink row in role ``PRIMARY_TARGET``.
- ``assessment_membership`` — the R0 sentence's **third** item (§24.8
  AssessmentMembership). It is read (:attr:`ReadinessFacts.assessment_membership`)
  and reported, but no level requires it, because no V1 table carries it:
  see :data:`DECLARED_ABSENT_FACT_KEYS`. **Under the strict three-item reading
  of that sentence, no entity of this corpus has any readiness level at all** —
  dropping a named item from the level's requirements is an interpretation of
  this implementation, not a canonical ruling.

R1 LEXICALLY_RESOLVED — "POS / sense / basic definition / forms 已可追溯"

- ``lexical_resolution`` — the §24.4 expression payload (expression subtype +
  fixedness + recognition policy) with the entity's canonical surface.
  **This is entity-type scoped and checked in code**: the fact is set only for
  an entity whose §24.1 ``entity_type`` is ``EXPRESSION``. The reading behind
  it — for a multi-word expression, its lexical resolution *is* that §24.4
  payload — is an **interpretation of this corpus, not a canonical ruling**:
  under the strict "POS / sense / basic definition / forms" reading the same
  corpus reads **R0**, and for any other entity type (LEXICAL_ENTRY, SENSE,
  FORM, …) V1 carries no such rows, so ``READINESS_FACT_KEYS`` counts
  ``lexical_resolution`` among the declared-absent facts for those types
  (:data:`UNREAD_FACT_EVIDENCE`) and the entity stays at R0.

R2 PLANNER_READY — "已具备 CurriculumLink、PedagogicalProfile、goal/pack
overlay、register/usage-modality/context 等 Planner 所需信息"

- ``curriculum_link`` — at least one §24.7 CurriculumLink row for this entity
  whose ``editorial_status`` is itself ``CANONICAL_APPROVED`` (a candidate
  mapping is not a mapping any Planner may act on).
- ``pedagogical_profile`` — §24.7 PedagogicalProfile.
- ``goal_pack_overlay`` — §24.8 PackOverlay (goal/pack overlay).
- ``resource_labels`` — §24.7 ResourceLabel (register/usage-modality/context).

R3 TEACHING_READY — "已具备 reviewed explanation/note、可用 example policy、
必要 contrast/usage，以及需要时的 TypicalError"

- ``reviewed_explanation`` — a reviewed explanation/note for the target.
- ``example_policy`` — a usable example policy (which examples to present,
  when) — *not* the target's example inventory: §24.5 ExampleLink rows are
  the examples themselves (already an R0/R1 fact).
- ``contrast_or_usage`` — a §24.5 ``CONTRAST`` link row, or the usage face of
  a §24.7 ResourceLabel.
- ``typical_error_when_needed`` — §24.9 TypicalError, required only when a
  source declares the need (:attr:`ReadinessFacts.typical_error_required`),
  so "以及需要时" is an explicit condition rather than a silent skip.

R4 DETECTION_READY — "在 R3 基础上具备 detection policy / recognition rules /
negative fixtures / false-positive boundaries，可支持高置信 automatic
error-triggered teaching"

- ``detection_policy`` / ``recognition_rules`` / ``negative_fixtures`` /
  ``false_positive_boundaries``. Four separate keys on purpose: §24.10 says
  R4 "必须包含可测试 detection policy/fixtures/false-positive boundary", and
  §8.1 refuses a self-reported confidence as a substitute — so no confidence
  value, model claim or capability score is a fact key here. Note that §24.4's
  ``recognition_policy`` (EXACT/LEMMA_SEQUENCE/SLOT_PATTERN/MODEL_ASSISTED) is
  part of the *R1* lexical payload and is deliberately **not** the R4
  ``recognition_rules``: R4 wants testable rules with fixtures, not a policy
  label.

Two things this ladder deliberately does not do (stated so their absence is a
decision rather than an omission):

- it never decides supply. Supply is §24.11 lifecycle
  (elc.content.types.supply_eligible) and the §8.1 defaults are the
  automatic-frontier policy, not a filter this module applies to a request;
- it never denies and never picks a target: it reports a level and the keys
  behind it (the same discipline the teaching Gate port keeps — the Gate owns
  admissibility, docs/DOMAIN_MODEL.md §2).

How the canonical text's **slash-lists** are operationalized here (the P5-0
precedent for §24.11's two slash rows, content_src/README.md R1):

- a row that names *separately named* concepts is a conjunction — §8.1 R2's
  "CurriculumLink、PedagogicalProfile、goal/pack overlay、
  register/usage-modality/context" is **four** required facts, and §8.1 R4's
  "detection policy / recognition rules / negative fixtures /
  false-positive boundaries" is **four** more (the slash is a list separator,
  not an "or");
- a row that reads as one concept with two accepted spellings is **one** fact —
  §24.11's "SENSE_RESOLVED / STRUCTURED" and "DEPRECATED / REPLACED" are one
  value each, which is why the lifecycle vocabulary enumerates the spellings
  separately rather than inventing compounds;
- §8.1 R0's "source / assessment membership / canonical form" is a list of
  three locatable things; this implementation reads the two the artifact can
  carry and declares the third absent — see
  :data:`DECLARED_ABSENT_FACT_KEYS` and the R0 note above (strict three-item
  reading ⇒ no level at all for this corpus).

Not re-exported from ``elc.curriculum.__init__`` for the **P5-0 precedent**,
not for a cycle: ``elc.content.store`` and ``elc.content.build`` are likewise
absent from ``elc.content.__init__``, and this module imports only
``elc.content.types`` (no store, no sqlite3) — keeping the ladder a leaf makes
"readiness is pure" checkable at the import graph rather than only by reading
the code. Import it by its full path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from elc.content.types import ReadinessLevel

__all__ = [
    "DECLARED_ABSENT_FACT_KEYS",
    "DEFAULT_AVAILABILITY",
    "LEVEL_ADDED_FACTS",
    "READINESS_FACT_KEYS",
    "READINESS_LEVELS",
    "LevelJudgement",
    "ReadinessAssessment",
    "ReadinessFacts",
    "judge_readiness",
    "required_fact_keys",
    "satisfied_level",
]

#: The five §8.1 levels, lowest first. Derived from the existing canonical
#: vocabulary (elc.content.types.ReadinessLevel) instead of being re-typed, so
#: the two cannot drift.
READINESS_LEVELS = tuple(str(level) for level in ReadinessLevel)

#: The §8.1 fact keys this judgement reads, in level order (R0 → R4). A key is
#: a *testable property of the artifact*, never a model claim.
#:
#: ``assessment_membership`` and ``lexical_resolution`` are listed here (they
#: are read and reported like every other key) although the corpus cannot
#: satisfy them today — see :data:`DECLARED_ABSENT_FACT_KEYS`.
READINESS_FACT_KEYS = (
    "entity_row",
    "canonical_form",
    "assessment_membership",
    "lexical_resolution",
    "curriculum_link",
    "pedagogical_profile",
    "goal_pack_overlay",
    "resource_labels",
    "reviewed_explanation",
    "example_policy",
    "contrast_or_usage",
    "typical_error_when_needed",
    "detection_policy",
    "recognition_rules",
    "negative_fixtures",
    "false_positive_boundaries",
)

#: §8.1 facts that are **read but required by no level**, because no artifact
#: state can satisfy them today. They stay in the fact-key list so their
#: absence is reported per target rather than dropped from the vocabulary.
#:
#: - ``assessment_membership`` — the R0 sentence's third item (§24.8); no V1
#:   table carries it (elc.curriculum.store.UNREAD_FACT_EVIDENCE);
#: - (kept as a tuple so a later slice can add one by naming it here and in
#:   READINESS_FACT_KEYS; adding a *required* key is a level change and must
#:   say so).
DECLARED_ABSENT_FACT_KEYS = ("assessment_membership",)

#: What each level *adds* to the keys below it (§8.1, cited per level in the
#: module docstring). Populated from READINESS_FACT_KEYS minus
#: DECLARED_ABSENT_FACT_KEYS, so a declared-absent key can never leak into a
#: level's requirements by accident.
LEVEL_ADDED_FACTS: Mapping[str, tuple[str, ...]] = {
    "R0_INDEXED": ("entity_row", "canonical_form"),
    "R1_LEXICALLY_RESOLVED": ("lexical_resolution",),
    "R2_PLANNER_READY": (
        "curriculum_link",
        "pedagogical_profile",
        "goal_pack_overlay",
        "resource_labels",
    ),
    "R3_TEACHING_READY": (
        "reviewed_explanation",
        "example_policy",
        "contrast_or_usage",
        "typical_error_when_needed",
    ),
    "R4_DETECTION_READY": (
        "detection_policy",
        "recognition_rules",
        "negative_fixtures",
        "false_positive_boundaries",
    ),
}

#: docs/PRODUCT_CONTRACT.md §8.1 默认 block, as the availability facts it
#: states (word for word):
#:
#:     R0/R1 → 不进入自动 Teaching Frontier
#:     R2    → Planner / probe 可用，默认不自动教学
#:     R3    → teach / review / transfer 可用
#:     R4    → automatic error-triggered teaching 可用
#:
#: The empty tuple for R0/R1 *is* "不进入自动 Teaching Frontier" — an empty
#: availability, not a missing entry. These are facts a Planner/Gate policy
#: may read; nothing here filters a request.
DEFAULT_AVAILABILITY: Mapping[str, tuple[str, ...]] = {
    "R0_INDEXED": (),
    "R1_LEXICALLY_RESOLVED": (),
    "R2_PLANNER_READY": ("PLANNER", "PROBE"),
    "R3_TEACHING_READY": ("TEACH", "REVIEW", "TRANSFER"),
    "R4_DETECTION_READY": ("AUTOMATIC_ERROR_TRIGGERED_TEACHING",),
}


def required_fact_keys(level: str) -> tuple[str, ...]:
    """The cumulative fact keys a level requires (R0's keys included)."""

    if level not in READINESS_LEVELS:
        raise ValueError(f"unknown readiness level: {level!r}")
    keys: list[str] = []
    for candidate in READINESS_LEVELS:
        keys.extend(LEVEL_ADDED_FACTS[candidate])
        if candidate == level:
            break
    return tuple(keys)


@dataclass(frozen=True)
class ReadinessFacts:
    """The §8.1 facts about ONE target, as the artifact states them.

    Every field defaults to False: a fact the artifact does not carry is
    absent, never assumed present. ``typical_error_required`` is the one field
    a *source* (not the artifact) sets: it declares that this target needs a
    TypicalError, which turns ``typical_error`` into a required fact. No V1
    source declares it, so the corpus reads ``False`` — reported here rather
    than silently skipped.
    """

    target_id: str
    entity_row: bool = False
    canonical_form: bool = False
    assessment_membership: bool = False
    lexical_resolution: bool = False
    curriculum_link: bool = False
    pedagogical_profile: bool = False
    goal_pack_overlay: bool = False
    resource_labels: bool = False
    reviewed_explanation: bool = False
    example_policy: bool = False
    contrast_or_usage: bool = False
    typical_error: bool = False
    typical_error_required: bool = False
    detection_policy: bool = False
    recognition_rules: bool = False
    negative_fixtures: bool = False
    false_positive_boundaries: bool = False

    def present(self, key: str) -> bool:
        """Is this fact key satisfied? Unknown keys raise — a typo in a fact
        key must fail loudly, never read as "absent"."""

        if key == "typical_error_when_needed":
            # §8.1 "以及需要时的 TypicalError": required only when a source
            # declares the need; with no declaration the key is satisfied by
            # the declared absence of a requirement, and with one it needs
            # the TypicalError content itself.
            return self.typical_error or not self.typical_error_required
        if key not in READINESS_FACT_KEYS:
            raise ValueError(f"unknown readiness fact key: {key!r}")
        return bool(getattr(self, key))

    def satisfied_keys(self) -> tuple[str, ...]:
        """The satisfied fact keys, in §8.1 level order."""

        return tuple(key for key in READINESS_FACT_KEYS if self.present(key))


@dataclass(frozen=True)
class LevelJudgement:
    """One level's judgement for one target: the keys it needs, the keys it
    has, and the keys that block it."""

    level: str
    required_keys: tuple[str, ...]
    satisfied_keys: tuple[str, ...]
    missing_keys: tuple[str, ...]
    reached: bool


@dataclass(frozen=True)
class ReadinessAssessment:
    """One target's readiness: the level reached and the evidence per level.

    ``level`` is ``None`` when even R0 is not reached (nothing about the
    target is indexed — there is no "below R0" level in §8.1, so the honest
    answer is no level at all).
    """

    target_id: str
    level: str | None
    judgements: tuple[LevelJudgement, ...]
    next_level: str | None
    missing_keys: tuple[str, ...]

    @property
    def detection_ready(self) -> bool:
        return self.level == READINESS_LEVELS[-1]

    def judgement(self, level: str) -> LevelJudgement:
        for entry in self.judgements:
            if entry.level == level:
                return entry
        raise ValueError(f"unknown readiness level: {level!r}")


def _judge_level(facts: ReadinessFacts, level: str) -> LevelJudgement:
    required = required_fact_keys(level)
    satisfied = tuple(key for key in required if facts.present(key))
    missing = tuple(key for key in required if not facts.present(key))
    return LevelJudgement(
        level=level,
        required_keys=required,
        satisfied_keys=satisfied,
        missing_keys=missing,
        reached=not missing,
    )


def judge_readiness(facts: ReadinessFacts) -> ReadinessAssessment:
    """Judge one target's §8.1 level from its artifact facts.

    The level is the highest one whose cumulative key set is fully satisfied;
    R0 is the floor (an unindexed target has no level at all). The assessment
    names, per level, the keys that support it and the keys that are missing,
    so "which facts back which level" is answerable without re-deriving it.
    """

    judgements = tuple(_judge_level(facts, level) for level in READINESS_LEVELS)
    reached = None
    for entry in judgements:
        if entry.reached:
            reached = entry.level
        else:
            break
    next_level = None
    missing: tuple[str, ...] = ()
    for entry in judgements:
        if not entry.reached:
            next_level = entry.level
            missing = entry.missing_keys
            break
    return ReadinessAssessment(
        target_id=facts.target_id,
        level=reached,
        judgements=judgements,
        next_level=next_level,
        missing_keys=missing,
    )


def satisfied_level(facts: ReadinessFacts) -> str | None:
    """Convenience: just the level (:func:`judge_readiness` without the
    per-level evidence)."""

    return judge_readiness(facts).level
