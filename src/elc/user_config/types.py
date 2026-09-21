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

The class names are unchanged on purpose: ``elc.platform.registry`` already
names ``UserProfile`` and ``DisclosurePolicy`` as the schemas of the
``user_profile`` / ``disclosure_policy`` canonical objects, and renaming them
would move the registry entry instead of the data (Gate item 5).

§5.1 pins the *names* of the list elements but not their shape, so this
module declares it explicitly (DATA_MODEL §27 leaves the physical form to the
implementation):

- :class:`ProfileFact` — one profile fact with its data class. The
  sensitivity vocabulary is
  :class:`elc.relationship.types.MemorySensitivityClass` (BF-05
  ``data_classes``: PERSONAL / HIGH_SENSITIVITY) rather than a second, local
  word list: the process has one privacy vocabulary, and §18.1's
  high-sensitivity rule is stated once.
- :class:`DisclosureRule` — one rule of the §5.1 ``rules[]`` list: for one
  Persona (or for everyone, when ``persona_id`` is None) it names the
  disclosure level. A default rule is *not* a persona, which is why the
  persona leg is optional rather than a wildcard word.

``DisclosedUserProfile`` keeps the Phase 0 shape (persona_id /
disclosure_level / disclosed_facts): it is a per-consumer *view*, produced by
:mod:`elc.user_config.disclosure` from a profile plus a policy, and it is
never a durable row.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import GoalId, GoalVersion, PersonaId, PolicyVersion, UserId
from elc.relationship.types import MemorySensitivityClass


class TeachingFrequency(StrEnum):
    """Coarse policy knob: how/how-often, never mastery truth (§5.1)."""

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
    """One long-term learning goal; GoalModality separates goal from evidence."""

    goal_id: GoalId
    goal_modality: str  # elc.platform.types.GoalModality value
    description: str


@dataclass(frozen=True)
class LearningGoalPortfolio:
    """Versioned goal portfolio (docs/DATA_MODEL.md §5.1
    base_goal_portfolio_version)."""

    user_id: UserId
    goal_version: GoalVersion
    goals: tuple[LearningGoal, ...]


@dataclass(frozen=True)
class TeachingPolicyProfile:
    """Versioned teaching policy — how/how-often only (§5.1)."""

    user_id: UserId
    policy_version: PolicyVersion
    teaching_frequency: TeachingFrequency
    automatic_teaching_enabled: bool


@dataclass(frozen=True)
class SessionFocus:
    """Temporary re-weighting of the portfolio; never rewrites long-term
    goals silently (§5.1)."""

    user_id: UserId
    focus_goal_ids: tuple[GoalId, ...]
    weight_override: dict[str, float]
