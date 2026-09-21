"""Profile disclosure — the pure decision that produces one DisclosedUserProfile.

docs/DATA_MODEL.md §5.1: DisclosurePolicy "Produces `DisclosedUserProfile`
for a specific Persona/runtime context". docs/DOMAIN_MODEL.md §5.1 Rules:
"Persona Runtime 只能获得 `DisclosedUserProfile`，不能读取完整 UserProfile"
— so this function is the *only* door between a profile and a persona, and
everything it does not select simply does not exist for that consumer.

§24.3 pins the runtime half of the same rule ("PromptCompiler/Provider
adapter 只能消费 action-specific disclosure view"), and §18.1 the privacy
half: "高敏感 Profile/Relationship persistence 需要显式用户许可" — the
persistence gate is the write face's
(elc.user_config.controller.upsert_user_profile); the *disclosure* gate is
this module's, and the two are deliberately separate questions. A fact that
was legitimately persisted under explicit consent is still only disclosed
when a persona-specific RICH rule authorizes it.

**The ladder** (Local V1 reading — §5.1 pins the three level words, not
their contents; this module declares what each level means):

- ``MINIMAL``  — the profile's PERSONAL facts;
- ``FUNCTIONAL`` — those plus ``preferences``;
- ``RICH``     — those plus ``settings``.

**The high-sensitivity rule**, stated once and enforced structurally:

- a HIGH_SENSITIVITY fact is disclosed **only** when the matched rule is
  persona-specific (``persona_id == persona_id``) *and* its level is RICH;
- the **default rule** (``persona_id is None``) never authorizes
  high-sensitivity disclosure, at any level — "everyone may know this" is
  not explicit consent for the most sensitive class of fact;
- a persona-specific rule of another persona is not a weaker match, it is
  **no match**: only the requested persona's own rule and the default rule
  are ever considered, so another persona's rule content cannot leak
  (DOMAIN_MODEL §17's isolation spirit, applied to configuration).

**No rule at all** → the empty disclosure: no facts, level MINIMAL. The
function is total (never raises, never returns a partial view) — an
unconfigured world discloses nothing, which is the fail-closed default
§18.1 asks for.
"""

from __future__ import annotations

from elc.platform.types import PersonaId
from elc.relationship.types import MemorySensitivityClass
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    UserProfile,
)

__all__ = ["decide_disclosure"]

#: The ladder order — a rule at or above this level discloses preferences.
_FUNCTIONAL = DisclosureLevel.FUNCTIONAL
#: … and at or above this one, settings.
_RICH = DisclosureLevel.RICH

#: The three levels in ascending order, used to compare a rule's level with a
#: ladder step (StrEnum members do not order themselves).
_LEVEL_ORDER = (
    DisclosureLevel.MINIMAL,
    DisclosureLevel.FUNCTIONAL,
    DisclosureLevel.RICH,
)


def decide_disclosure(
    profile: UserProfile | None,
    policy: DisclosurePolicy | None,
    persona_id: PersonaId,
) -> DisclosedUserProfile:
    """What this persona may be told about this user — and nothing else.

    Deterministic and total: the same (profile, policy, persona) always
    yields the same view, and a missing profile or a missing policy yields
    the empty disclosure rather than an error (an unconfigured world
    discloses nothing — DOMAIN_MODEL §18.1's fail-closed reading).

    Fact order is the profile's own storage order, then preferences, then
    settings — so the view is stable without sorting text.

    Two rules for the same persona (or two default rules) are an assembly
    error; the first one in ``policy.rules`` wins, deterministically, and the
    later duplicates are simply never reached (never merged: a rule is an
    authorization, and authorizations do not average).
    """

    matched = _matched_rule(policy, persona_id)
    if profile is None or matched is None:
        return DisclosedUserProfile(
            persona_id=persona_id,
            disclosure_level=DisclosureLevel.MINIMAL,
            disclosed_facts=(),
        )

    level = matched.disclosure_level
    persona_specific = matched.persona_id is not None
    high_sensitivity_allowed = persona_specific and level is _RICH

    facts: list[str] = [
        fact.text
        for fact in profile.profile_facts
        if fact.sensitivity is MemorySensitivityClass.PERSONAL
        or high_sensitivity_allowed
    ]
    if _at_least(level, _FUNCTIONAL):
        facts.extend(profile.preferences)
    if _at_least(level, _RICH):
        facts.extend(profile.settings)
    return DisclosedUserProfile(
        persona_id=persona_id,
        disclosure_level=level,
        disclosed_facts=tuple(facts),
    )


def _matched_rule(
    policy: DisclosurePolicy | None, persona_id: PersonaId
) -> DisclosureRule | None:
    """The rule that governs this persona: its own, else the default.

    Another persona's rule is invisible here — not selected, not compared,
    not returned. Only two kinds of rule exist for a request: "for this
    persona" and "for everyone".
    """

    if policy is None:
        return None
    named: DisclosureRule | None = None
    default: DisclosureRule | None = None
    for rule in policy.rules:
        if rule.persona_id is None:
            if default is None:
                default = rule
        elif rule.persona_id == persona_id and named is None:
            named = rule
    return named if named is not None else default


def _at_least(level: DisclosureLevel, step: DisclosureLevel) -> bool:
    return _LEVEL_ORDER.index(level) >= _LEVEL_ORDER.index(step)
