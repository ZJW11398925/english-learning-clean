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

P6-3 (TASK-OPI-5a0be06d-….20 ③.2): docs/DATA_MODEL.md **§9**
TeachingPreference / PlannerConstraint lands here as
:class:`PlannerConstraint` — nine columns in §9's order, the four
``constraint_type`` words and the three ``scope`` words verbatim. **The
placement is a derived judgement, not a quoted one**: §5.1's Owns list for this
bounded context does *not* name PlannerConstraint, so no canonical sentence
puts the object here. What decides it is §9's own shape (a typed *preference*
carrying a ``created_from_turn_id?`` provenance leg and three user-level
scopes), DOMAIN_MODEL §18.1's TRUSTED_AUTHORITY (a typed user setting is the
user's own statement), and the fact that the durable row belongs beside the
other user configuration rows. A canonical revision that assigns the object
elsewhere moves this module's placement with it.

**This object is durable truth, not an applied effect.** P6-3 lands the row and
its five faces; it does **not** wire the constraint into anything — no Planner
reads it, no Gate consults it, and nothing here turns a user's sentence into a
constraint (that extraction face is Phase 8's). The suppression a row will one
day cause is a *consumer's* reading of this truth, decided in the consumer's
cut.
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
    TurnId,
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


#: docs/DATA_MODEL.md §9's ``constraint_type`` list, word for word — the four
#: Types words the canonical block pins. Declared at module level (and
#: restated by :class:`PlannerConstraintType` below) so a pin can compare the
#: canonical block text with this constant *and* with the enum's members
#: rather than trusting a single spelling: the P6-0 review finding (F-2) asked
#: for exactly this second shape, because a word list can hide in a module
#: constant as easily as in an enum.
PLANNER_CONSTRAINT_TYPES: tuple[str, ...] = (
    "DO_NOT_AUTO_TEACH",
    "SUPPRESS_REVIEW",
    "JUST_CHAT",
    "MANUAL_FOCUS",
)

#: docs/DATA_MODEL.md §9's ``scope`` list ("Scope 例如"), word for word — the
#: three words, in the block's own order. Same second-shape rule as
#: :data:`PLANNER_CONSTRAINT_TYPES`.
PLANNER_CONSTRAINT_SCOPES: tuple[str, ...] = (
    "THIS_SESSION",
    "UNTIL_DATE",
    "UNTIL_USER_REENABLES",
)


class PlannerConstraintType(StrEnum):
    """What a user constraint forbids (or forces) — §9's four Types words.

    The canonical block (docs/DATA_MODEL.md §9, line 603 onward) pins exactly
    :data:`PLANNER_CONSTRAINT_TYPES`, so migration 0013 enforces them with a
    CHECK (a pinned vocabulary may be frozen in the schema — the 0010
    ``episode.status`` precedent; an unpinned one may not). The Scope list
    beside it is a **different case** — §9 offers that one as an example, so
    freezing it is a schema choice rather than a canonical claim; the
    distinction is spelled out on :class:`PlannerConstraintScope` and in the
    migration header.

    **This enum carries no behaviour.** It does not say what suppression
    happens, which face applies it or when it lapses: nothing in this cut
    consumes a constraint at all. A consumer that must branch on one of these
    words (Phase 7's ``PlannerConstraintView``, Phase 8's
    ``TARGET_SUPPRESSED``) reads the value and owns the reading.
    """

    DO_NOT_AUTO_TEACH = "DO_NOT_AUTO_TEACH"
    SUPPRESS_REVIEW = "SUPPRESS_REVIEW"
    JUST_CHAT = "JUST_CHAT"
    MANUAL_FOCUS = "MANUAL_FOCUS"


class PlannerConstraintScope(StrEnum):
    """How long a user constraint lasts — §9's three Scope words.

    :data:`PLANNER_CONSTRAINT_SCOPES`, verbatim **from §9's example block**,
    and enforced by migration 0013's CHECK.

    **This list does not hold the canonical position the Types list holds.**
    §9 introduces its Types block as a list (``Types：``) but its Scope block
    as an example (``Scope 例如``), so the three words below are taken word for
    word from the document's *example* while **closing** the set is this cut's
    schema choice rather than a canonical claim: a fourth scope word extends
    migration 0013's CHECK, and the canonical text would still be satisfied by
    it (the full statement, with the same distinction, is in that migration's
    header). Reading the closure as canonical would be a claim §9 does not
    make.

    **The three words are carried; none of them is interpreted here.** In
    particular ``THIS_SESSION`` names a session, and §9 gives the object no
    conversation column — so which session is current is a *consumer's*
    question (elc/user_config/store.py registers that state of affairs, and
    the cut that wires the first consumer answers it). ``UNTIL_DATE`` reads
    its end from ``expires_at``; ``UNTIL_USER_REENABLES`` is the open-ended
    one, whose end is the user's own act (the ``active`` transfer face, R6).
    """

    THIS_SESSION = "THIS_SESSION"
    UNTIL_DATE = "UNTIL_DATE"
    UNTIL_USER_REENABLES = "UNTIL_USER_REENABLES"


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
    (only ``updated_at`` is the store's own clock). **F-4 (P6-1 registration):
    the empty string ``""`` is the sentinel for "not configured"** — it is
    what a caller that did not declare an effective date leaves here, and it
    is a value, not an absence of one: no consumer may read ``""`` as a
    timestamp, and none may substitute a clock value for it. §5.1 pins no
    nullable ``effective_from``, so the sentinel is carried in the column's
    own type (``str``) rather than by making the column ``None``-able, and
    migration 0011 is untouched by this registration. The mutable-container
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

    ``effective_from`` is the caller's declaration (never the store's clock),
    with the **same F-4 sentinel the portfolio carries**: the empty string
    ``""`` means "not configured". It is a value the column holds, not a
    second nullability convention — §5.1 pins no nullable ``effective_from``,
    so the sign is spelled in the column's own type rather than by changing
    the type, and a consumer that reads ``""`` as a timestamp is reading a
    sentinel as data.

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


@dataclass(frozen=True, kw_only=True)
class PlannerConstraint:
    """docs/DATA_MODEL.md §9 TeachingPreference / PlannerConstraint — nine
    columns, word for word, in §9's order.

    One durable user constraint: "don't teach this automatically", "don't make
    me review this", "I just want to chat", "focus on this manually". The four
    ``constraint_type`` words and the three ``scope`` words are §9's, verbatim
    (:data:`PLANNER_CONSTRAINT_TYPES` / :data:`PLANNER_CONSTRAINT_SCOPES` and
    the two enums beside them); migration 0013 enforces both in the schema
    because canonical text pins them.

    **Ownership is a derived judgement (R1).** §5.1's Owns list does not name
    this object, so its placement in this package is this cut's reading —
    stated with its reasons in this module's docstring and in migration 0013's
    header, and registered as such rather than quoted.

    **No version column, and therefore no in-place rewrite (R6).** §9 gives
    this object no ``version`` / ``revision`` stamp, so ``constraint_id`` is a
    one-shot identity: a write that would change the content of an existing id
    is refused (``CONFLICT``) rather than silently rewriting a row nothing
    could version (the :class:`SessionFocus` precedent, and docs/DATA_MODEL.md
    §1.3's append-first reading — a different constraint is a different
    ``constraint_id``). The **one** exception is :attr:`active`, and it is
    reachable only through its own transfer face
    (``set_planner_constraint_active``): BF-03 makes re-enabling a constraint
    the User Constraint layer's act — "Gate 不偷偷修改用户约束" — so the
    content-write face refuses an ``active`` that differs from the durable row
    instead of carrying the flag through. Without that exception
    ``UNTIL_USER_REENABLES`` could never be ended. The refusal rules live in
    :mod:`elc.user_config.store`, stated once there.

    **Scope is carried, never interpreted (R7).** ``scope`` travels verbatim
    and no read face this cut lands branches on it; in particular
    ``THIS_SESSION`` names a session and §9 gives the object **no conversation
    column**, so "which session is current?" is a consumer's question — the
    store registers that fact where the read faces are declared. **Revisit
    condition**: the first consumer that must honour ``THIS_SESSION`` either
    reads the session from context it already holds (and this object stays as
    it is) or needs a session leg the canonical block does not carry — the
    latter is a canonical revision, not an implementation choice.

    ``starts_at`` / ``expires_at`` are ISO-8601 **instants carrying a UTC
    offset** when a caller declares them: the active-window read faces compare
    them as instants (never as byte order — the opposite of p6-1's replay rule
    for an immutable fact, and the same reading :mod:`elc.scheduler.spacing`
    declares for its window), and an empty, unparseable or naive timestamp is
    refused rather than assumed to be UTC. ``expires_at is None`` = no end
    declared (an open-ended constraint). ``starts_at`` is the caller's
    declaration; no store clock writes it (this row has no store-stamped column
    at all).

    ``target_type`` is a bare ``str``: §9 names the column, migration 0013
    enforces the two canonical words (RESOURCE / CAPABILITY), and the platform
    declares no ``TargetType`` type to use here — the
    :class:`elc.scheduler.types.ScheduleItem` precedent, with the same
    evidence. ``target_id`` does have a platform type and uses it
    (``TargetId``); ``created_from_turn_id`` is a ``TurnId``. The two target
    columns are ``None`` together for a constraint that is **not
    target-limited**, and ``target_type is None`` with a present ``target_id``
    (or the reverse) is a shape this object does not call illegal: §9 pins no
    such rule, and inventing one here would be a rule the canonical set does
    not make — the read faces match on the pair they are given, verbatim.

    The fields are keyword-only because §9 declares two optional columns
    (``target_type?`` / ``target_id?``) *before* the required
    ``constraint_type`` — a defaulted field cannot precede a required one in a
    positional dataclass, and keeping both the canonical column order (pinned
    by test) and the "not configured" ``None`` defaults is worth more than
    positional construction (the :class:`TeachingPolicyProfile` precedent).
    """

    constraint_id: str
    target_type: str | None = None
    target_id: TargetId | None = None
    constraint_type: PlannerConstraintType
    scope: PlannerConstraintScope
    starts_at: str
    expires_at: str | None = None
    created_from_turn_id: TurnId | None = None
    active: bool
