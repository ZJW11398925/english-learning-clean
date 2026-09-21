"""User Configuration / Profile bounded context.

Owns (docs/DOMAIN_MODEL.md §5.1): UserProfile, DisclosurePolicy,
LearningGoalPortfolio, TeachingPolicyProfile, SessionFocus.

Goal/Policy are versioned configuration — never Learning Evidence. The
GlobalGoalPortfolio can be temporarily re-weighted by a SessionFocus but
never silently rewritten. Persona Runtime may only ever receive
DisclosedUserProfile, never the full UserProfile (§5.1 Rules: "Persona
Runtime 只能获得 `DisclosedUserProfile`，不能读取完整 UserProfile").
TeachingPolicy changes only how/how-often teaching happens — never Learner
State truth.

P4-3 (TASK-OPI-4d516e4f-….19 ③): the two Phase 0 profile stubs were
replaced by the canonical column sets, verbatim —

- ``UserProfile`` — §5.1's six columns: user_profile_id / revision /
  profile_facts / preferences / settings / updated_at (the Phase 0 skeleton
  spelled them ``user_id`` / ``display_name`` / ``high_sensitive``);
- ``DisclosurePolicy`` — §5.1's four columns: disclosure_policy_id /
  revision / rules[] / updated_at (the Phase 0 skeleton carried
  ``persona_id`` / ``disclosure_level`` as if the policy *were* a rule).

P6-0 (TASK-OPI-a68fd9eb-….48 ①): the same graduation lands for the three
remaining §5.1 objects. Their Phase 0 skeletons carried fields the
canonical set does not have — ``user_id`` on all three, ``focus_goal_ids``
/ ``weight_override`` on the focus, and ``automatic_teaching_enabled`` on
the policy. They are **removed**, not renamed: §5.1 pins the column *set*
(that block is the authority, not a sketch), so a column the canonical
block does not carry may not survive the rewrite of the object that carries
it (the P4-3 precedent above, and the P4-0 lesson: canonical outranks an
earlier implementation spelling).

Canonical column sets, in §5.1's order (the objects below carry them
verbatim):

- ``LearningGoalPortfolio`` — goal_portfolio_id / version / goals[] /
  modality_weights / assessment_targets[] / register_style_goals[] /
  effective_from / updated_at (eight);
- ``TeachingPolicyProfile`` — teaching_policy_profile_id / version / mode /
  teaching_frequency / interruption_budget / curriculum_initiative /
  correction_strictness / hint_policy / assessment_visibility /
  practice_density / persona_freedom / effective_from / updated_at
  (thirteen);
- ``SessionFocus`` — session_focus_id / conversation_id /
  base_goal_portfolio_version / temporary_goal_weights /
  manual_focus_target? / starts_at / expires_at? (seven).

**Version field naming — ``goal_version`` / ``policy_version``.** §5.1's
object blocks spell the column ``version``; this implementation uses the
**qualified** names, and the reasons are facts about the shipped platform
rather than taste:

1. the canonical documents themselves use the qualified spellings —
   docs/DATA_MODEL.md's DecisionCycle block lists ``goal_version`` /
   ``schedule_version`` / ``policy_version`` side by side (lines 175-177),
   so the qualified name is canonical vocabulary, not an invention;
2. the platform binds a version *type* by **field name**:
   ``elc.platform.types.VERSION_FIELDS`` maps ``"goal_version"`` →
   ``GoalVersion``, ``"policy_version"`` → ``PolicyVersion`` and
   ``"schedule_version"`` → ``ScheduleVersion`` — three distinct
   ``NewType``s, and ``ScheduleItem.version`` (§5.2) is a third object that
   would spell the same bare ``version``;
3. ``elc.platform.registry`` already declares this binding:
   ``version_field="goal_version"`` for ``goal_portfolio`` and
   ``version_field="policy_version"`` for ``teaching_policy`` (Gate item 5
   — "Goal/Policy/Profile … 均有 owner/schema", and
   ``test_registry_version_fields_are_canonical`` requires the spelling to
   exist in ``VERSION_FIELDS``).

A bare ``version`` is therefore *not distinguishable* under the existing
binding mechanism: the same field name would mean a different type on each
of the three objects that carries it. **Known limitation** of this reading:
§5.1's object block says ``version``, and this module says so instead.
**Revisit condition**: if the canonical documents are revised to pin a bare
``version`` on these objects (or to spell the qualified name inside the
§5.1 blocks themselves), re-adjudicate the naming here *together with*
``VERSION_FIELDS`` and the registry's ``version_field`` bindings — the
three move as one, and no one of them may move alone.

**Declared element shapes** (§5.1 pins the *names* of the list/map
elements, not their shape; docs/DATA_MODEL.md §27 leaves the physical form
to the implementation, exactly as it did for P4-3's ProfileFact /
DisclosureRule):

- :class:`LearningGoal` — one ``goals[]`` element: an opaque id, the
  long-term modality, and the description. ``goal_modality`` is
  :class:`elc.platform.types.GoalModality` (ARCHITECTURE_BASELINE §6:
  SPEAKING / LISTENING / READING / WRITING) — GoalModality is a *goal*
  vocabulary and never an evidence modality or an interaction channel
  (docs/DATA_MODEL.md §24.14 keeps the three type-separated).
- ``modality_weights`` / ``temporary_goal_weights`` — a mapping
  ``GoalModality → float`` (the weight of a long-term modality; the same
  canonical vocabulary as the goals themselves).
- ``assessment_targets[]`` / ``register_style_goals[]`` — tuples of
  ``str``. §5.1 names the columns and pins no id type for their elements,
  so this implementation carries them as opaque strings rather than
  inventing an id space (§27; "禁发明新枚举/新词表").
- ``effective_from`` / ``updated_at`` / ``starts_at`` / ``expires_at`` —
  ISO-8601 strings (``expires_at`` may be None: §5.1 spells it
  ``expires_at?``).

**Vocabulary honesty.** §5.1 pins no value range for any
``TeachingPolicyProfile`` column except by name. ``teaching_frequency``
keeps the Phase 0 :class:`TeachingFrequency` enum — an **implementation-
declared** word list (OFF / MINIMAL / BALANCED / EAGER), *not* a canonical
one — while the eight remaining unpinned columns (``mode`` /
``interruption_budget`` / ``curriculum_initiative`` /
``correction_strictness`` / ``hint_policy`` / ``assessment_visibility`` /
``practice_density`` / ``persona_freedom``) are carried as ``str | None``
raw values with **zero runtime interpretation**: ``None`` means "not
configured", and this slice invents no vocabulary for them. A consumer
that needs semantics for one of those columns needs a decision, not a
guess — the P6-0 red line.

**Keying convention (Local V1, declared rather than assumed).** §5.1 pins
no owner column linking a portfolio or a policy to a user, so — the
``user_profile_id`` / ``disclosure_policy_id`` precedent this package
already ships (migration 0010's comment) — ``goal_portfolio_id`` and
``teaching_policy_profile_id`` carry the user's own id (both typed
:class:`elc.platform.types.UserId` here). ``SessionFocus`` needs no such
convention: §5.1 gives it ``conversation_id`` directly, and its
``session_focus_id`` is its own opaque identity (``str``: no platform
``NewType`` exists for it, and this module does not mint id spaces —
§1.2's "stable opaque ID" holds for an opaque string).

``DisclosedUserProfile`` keeps the Phase 0 shape (persona_id /
disclosure_level / disclosed_facts): it is a per-consumer *view*, produced
by :mod:`elc.user_config.disclosure` from a profile plus a policy, and it
is never a durable row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from elc.platform.types import (
    ConversationId,
    GoalId,
    GoalModality,
    GoalVersion,
    PersonaId,
    PolicyVersion,
    TargetId,
    UserId,
)
from elc.relationship.types import MemorySensitivityClass


class TeachingFrequency(StrEnum):
    """Coarse policy knob: how/how-often, never mastery truth (§5.1).

    **Implementation-declared word list.** docs/DATA_MODEL.md §5.1 names the
    ``teaching_frequency`` column and pins no value range, so these four
    words are this repository's declaration, not a canonical vocabulary —
    which is why migration 0011 puts no CHECK on the column (a canonical
    column carrying an implementation word list is not frozen by the
    schema; see the migration header).
    """

    OFF = "OFF"
    MINIMAL = "MINIMAL"
    BALANCED = "BALANCED"
    EAGER = "EAGER"


class DisclosureLevel(StrEnum):
    """Per-persona disclosure policy knob (the §5.1 ``rules[]`` level).

    Ordered by what it discloses — MINIMAL < FUNCTIONAL < RICH — and the
    ladder is the one :func:`elc.user_config.disclosure.decide_disclosure`
    walks.
    """

    MINIMAL = "MINIMAL"
    FUNCTIONAL = "FUNCTIONAL"
    RICH = "RICH"


@dataclass(frozen=True)
class ProfileFact:
    """One ``profile_facts`` element (docs/DATA_MODEL.md §5.1), whose shape
    §5.1 leaves to the implementation.

    ``sensitivity`` is the BF-05 data class of the fact
    (docs/DOMAIN_MODEL.md §18.1: "高敏感 Profile/Relationship persistence
    需要显式用户许可"): a HIGH_SENSITIVITY fact is refused by the write face
    unless the caller passes explicit consent, and is disclosed to a persona
    only under a RICH, persona-specific rule
    (:mod:`elc.user_config.disclosure`).
    """

    text: str
    sensitivity: MemorySensitivityClass = MemorySensitivityClass.PERSONAL


@dataclass(frozen=True)
class UserProfile:
    """docs/DATA_MODEL.md §5.1 UserProfile — six columns, word for word.

    Owned by this bounded context (DOMAIN_MODEL §5.1/§2). ``user_profile_id``
    is the user's own id (Local V1: one profile per user; §5.1 pins no second
    owner column), ``revision`` stamps this revision of the content (§1.4
    版本化), and ``updated_at`` is filled by the store's own clock — a
    constructed profile leaves it empty and the durable writer stamps it.

    ``profile_facts`` / ``preferences`` / ``settings`` store as tuples (the
    implementation-defined form of a canonical list, DATA_MODEL §27; the
    durable columns are JSON text, migration 0010).
    """

    user_profile_id: UserId
    revision: str
    profile_facts: tuple[ProfileFact, ...] = ()
    preferences: tuple[str, ...] = ()
    settings: tuple[str, ...] = ()
    updated_at: str = ""

    @property
    def high_sensitivity_facts(self) -> tuple[ProfileFact, ...]:
        """The facts whose data class requires explicit consent (§18.1).

        The write face's gate reads this rather than re-deriving the rule:
        one place decides what "high sensitivity" means for a profile.
        """

        return tuple(
            fact
            for fact in self.profile_facts
            if fact.sensitivity is MemorySensitivityClass.HIGH_SENSITIVITY
        )


@dataclass(frozen=True)
class DisclosureRule:
    """One ``rules[]`` element of docs/DATA_MODEL.md §5.1 DisclosurePolicy.

    ``persona_id is None`` is the **default rule** — what may be disclosed to
    a persona this policy names no rule for. A default rule is deliberately
    weaker than a named one: it can never authorize high-sensitivity
    disclosure (elc.user_config.disclosure pins that, and the pinned test
    proves it).
    """

    persona_id: PersonaId | None
    disclosure_level: DisclosureLevel


@dataclass(frozen=True)
class DisclosurePolicy:
    """docs/DATA_MODEL.md §5.1 DisclosurePolicy — four columns, word for word.

    "Produces ``DisclosedUserProfile`` for a specific Persona/runtime
    context" (§5.1): this object is the *only* input of a disclosure decision
    besides the profile itself. ``disclosure_policy_id`` keys the row; Local
    V1 links it to its user by using the user's own id (the linking
    convention declared in elc.user_config.store and .controller, since §5.1
    pins no owner column).
    """

    disclosure_policy_id: str
    revision: str
    rules: tuple[DisclosureRule, ...] = ()
    updated_at: str = ""


@dataclass(frozen=True)
class DisclosedUserProfile:
    """The ONLY user-profile shape Persona Runtime may consume (§5.1).

    Built per (user, persona) by :mod:`elc.user_config.disclosure` — never
    stored, never widened: ``disclosed_facts`` carries exactly the facts the
    matched rule authorizes, so a consumer cannot reach a fact this persona
    was not granted (DOMAIN_MODEL §18.1/§24.3: PromptCompiler consumes an
    action-specific disclosure view).
    """

    persona_id: PersonaId
    disclosure_level: DisclosureLevel
    disclosed_facts: tuple[str, ...]


@dataclass(frozen=True)
class LearningGoal:
    """One ``goals[]`` element of docs/DATA_MODEL.md §5.1
    LearningGoalPortfolio, whose shape §5.1 leaves to the implementation.

    ``goal_modality`` is the **goal** modality vocabulary
    (elc.platform.types.GoalModality: SPEAKING / LISTENING / READING /
    WRITING) — a long-term goal's modality, never an EvidenceModality
    (docs/DATA_MODEL.md §24.14: "GoalModality does not rewrite evidence
    source"). A goal is configuration: it carries no evidence, no state and
    no freshness.
    """

    goal_id: GoalId
    goal_modality: GoalModality
    description: str


@dataclass(frozen=True)
class LearningGoalPortfolio:
    """docs/DATA_MODEL.md §5.1 LearningGoalPortfolio — eight columns.

    ``goal_portfolio_id`` is the user's own id (the Local V1 keying
    convention this package declares; §5.1 pins no owner column), and
    ``goal_version`` is the qualified spelling of §5.1's ``version`` (the
    naming rationale, its limitation and its revisit condition are in this
    module's docstring).

    ``effective_from`` is **the caller's** declaration of when this portfolio
    takes effect — ISO-8601, carried verbatim; the store never invents one
    (only ``updated_at`` is the store's own clock). The mutable-container
    types are the implementation-defined form of §5.1's ``goals[]`` /
    ``modality_weights`` / ``assessment_targets[]`` /
    ``register_style_goals[]`` (DATA_MODEL §27): tuples for the lists, a
    ``GoalModality → float`` mapping for the weights, JSON text on disk.
    """

    goal_portfolio_id: UserId
    goal_version: GoalVersion
    goals: tuple[LearningGoal, ...] = ()
    modality_weights: Mapping[GoalModality, float] = field(
        default_factory=dict
    )
    assessment_targets: tuple[str, ...] = ()
    register_style_goals: tuple[str, ...] = ()
    effective_from: str = ""
    updated_at: str = ""


@dataclass(frozen=True, kw_only=True)
class TeachingPolicyProfile:
    """docs/DATA_MODEL.md §5.1 TeachingPolicyProfile — thirteen columns.

    "TeachingPolicy 只改变'如何/多频繁教学'，不改 Learner State truth"
    (DOMAIN_MODEL §5.1 Rules): a policy is configuration, never evidence —
    it produces no claim, moves no estimate and owns no target state.

    ``teaching_policy_profile_id`` is the user's own id (the same Local V1
    convention as the portfolio) and ``policy_version`` is the qualified
    spelling of §5.1's ``version`` (module docstring: rationale, limitation,
    revisit condition).

    ``teaching_frequency`` carries the implementation-declared
    :class:`TeachingFrequency` word list; the eight remaining unpinned
    columns are carried **raw** as ``str | None`` (``None`` = not
    configured) with zero runtime interpretation — this slice invents no
    vocabulary and no default for them (§5.1 pins no value range; a consumer
    that needs semantics needs a decision first).

    The fields are keyword-only on purpose: §5.1 declares ``mode`` *before*
    ``teaching_frequency``, and the eight unpinned columns carry ``None``
    defaults — a defaulted field cannot precede a required one in a
    positional dataclass, and this object keeps both the canonical column
    order (pinned by test) and the "not configured" default rather than
    inventing a default *value* for the frequency (which would be a policy
    statement §5.1 does not make).
    """

    teaching_policy_profile_id: UserId
    policy_version: PolicyVersion
    mode: str | None = None
    teaching_frequency: TeachingFrequency
    interruption_budget: str | None = None
    curriculum_initiative: str | None = None
    correction_strictness: str | None = None
    hint_policy: str | None = None
    assessment_visibility: str | None = None
    practice_density: str | None = None
    persona_freedom: str | None = None
    effective_from: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class SessionFocus:
    """docs/DATA_MODEL.md §5.1 SessionFocus — seven columns.

    The temporary re-weighting of the portfolio DOMAIN_MODEL §5.1 Rules
    names: "`GlobalGoalPortfolio` 可被 `SessionFocus` 临时重加权，但不能
    静默修改长期目标" — writing a focus never touches the portfolio row
    (pinned in tests/phase6).

    **No version stamp.** §5.1 gives this object no ``version`` /
    ``revision`` column at all: ``base_goal_portfolio_version`` names the
    portfolio version the focus was derived from, not a version of the focus
    itself, and the two ``?`` columns are optional content. The store
    therefore treats ``session_focus_id`` as a one-shot identity
    (append-first, docs/DATA_MODEL.md §1.3): a new focus is a new id, and a
    write that would change the content of an existing id is refused rather
    than silently rewriting a row nothing could version (see
    elc.user_config.store, where the rule and its reasoning live).

    ``manual_focus_target`` is a ``TargetId`` (the target vocabulary
    learning/teaching already use) — a manual focus names a target, not a
    goal: §5.1 spells the column ``manual_focus_target?`` and no
    goal-modality word belongs in it. ``starts_at`` / ``expires_at`` are
    ISO-8601 (``expires_at`` may be None: an open-ended focus).
    """

    session_focus_id: str
    conversation_id: ConversationId
    base_goal_portfolio_version: GoalVersion
    temporary_goal_weights: Mapping[GoalModality, float] = field(
        default_factory=dict
    )
    manual_focus_target: TargetId | None = None
    starts_at: str = ""
    expires_at: str | None = None
