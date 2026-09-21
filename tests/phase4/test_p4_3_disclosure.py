"""P4-3 ② — DisclosedUserProfile: the write gate and the disclosure ladder.

docs/DOMAIN_MODEL.md §5.1 Rules: "Persona Runtime 只能获得
`DisclosedUserProfile`，不能读取完整 UserProfile"; §18.1: "高敏感 Profile/
Relationship persistence 需要显式用户许可；模型不得把推断的高敏感属性直接
提交为长期事实". Two questions live apart on purpose, and both are pinned
here:

- **persistence** (elc.user_config.controller.upsert_user_profile): a
  profile carrying any HIGH_SENSITIVITY fact needs explicit consent, and a
  refusal writes nothing;
- **disclosure** (elc.user_config.disclosure.decide_disclosure): even a
  legitimately persisted high-sensitivity fact is only shown to a persona
  whose *own* rule is RICH — the default rule never authorizes it, at any
  level.

The ladder (MINIMAL → the PERSONAL facts; FUNCTIONAL → +preferences; RICH →
+settings) is this slice's declared reading of §5.1's three level words; the
isolation cases prove that another persona's rule is not a weaker match but
no match at all.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.types import Ok, UserId
from elc.relationship.types import MemorySensitivityClass
from elc.user_config import (
    HIGH_SENSITIVITY_CONSENT_REQUIRED,
    DisclosedUserProfile,
    DisclosureLevel,
    UserConfigController,
    decide_disclosure,
)
from elc.user_config.store import SqliteUserConfigStore

from .conftest import (
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    fact,
    policy,
    policy_row,
    profile,
    profile_row,
    rule,
)

HIGH = MemorySensitivityClass.HIGH_SENSITIVITY
PERSONAL = MemorySensitivityClass.PERSONAL


def _controller_with(
    controller: UserConfigController,
    *,
    facts=(),
    preferences=(),
    settings=(),
    rules=(),
    consent: bool = False,
):
    """One profile + one policy through the real write faces."""

    written = controller.upsert_user_profile(
        profile(
            *facts,
            preferences=preferences,
            settings=settings,
        ),
        explicit_consent=consent,
    )
    if rules:
        stored = controller.set_disclosure_policy(policy(*rules))
        assert isinstance(stored, Ok), stored
    return written


# -- ② the persistence gate (§18.1) -----------------------------------------


def test_a_high_sensitivity_fact_needs_explicit_consent(
    db: sqlite3.Connection,
    user_config_controller: UserConfigController,
) -> None:
    refused = user_config_controller.upsert_user_profile(
        profile(fact("the user is quietly leaving their job", HIGH)),
        explicit_consent=False,
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert HIGH_SENSITIVITY_CONSENT_REQUIRED in refused.error.message
    # Zero writes: no row at all.
    assert db.execute("SELECT COUNT(*) FROM user_profile").fetchone() == (0,)


def test_a_high_sensitivity_fact_lands_with_explicit_consent(
    db: sqlite3.Connection,
    user_config_controller: UserConfigController,
) -> None:
    written = user_config_controller.upsert_user_profile(
        profile(fact("the user is quietly leaving their job", HIGH)),
        explicit_consent=True,
    )
    assert isinstance(written, Ok), written
    row = profile_row(db, REL_USER)
    assert row[1] == "rev-1"
    assert '"HIGH_SENSITIVITY"' in str(row[2])


def test_a_personal_only_profile_needs_no_consent(
    db: sqlite3.Connection,
    user_config_controller: UserConfigController,
) -> None:
    written = user_config_controller.upsert_user_profile(
        profile(fact("the user lives in Berlin")), explicit_consent=False
    )
    assert isinstance(written, Ok), written
    assert profile_row(db, REL_USER)[1] == "rev-1"


def test_the_gate_is_the_write_faces_not_the_stores() -> None:
    """Layer separation, pinned by source: the store has no consent
    parameter, and the controller consults the profile's own
    ``high_sensitivity_facts`` rather than re-deriving the class list."""

    from elc.platform.types import UserId as _UserId  # noqa: F401
    from tests.conftest import SRC_ROOT

    store_source = (SRC_ROOT / "user_config" / "store.py").read_text(
        encoding="utf-8"
    )
    assert "explicit_consent" not in store_source
    controller_source = (SRC_ROOT / "user_config" / "controller.py").read_text(
        encoding="utf-8"
    )
    assert "high_sensitivity_facts" in controller_source


# -- ② the ladder -----------------------------------------------------------


def test_minimal_discloses_the_personal_facts() -> None:
    disclosed = decide_disclosure(
        profile(
            fact("the user lives in Berlin"),
            fact("the user is quietly leaving their job", HIGH),
            preferences=("short replies",),
            settings=("morning sessions",),
        ),
        policy(rule(DisclosureLevel.MINIMAL, PERSONA_A)),
        PERSONA_A,
    )
    assert disclosed.disclosure_level is DisclosureLevel.MINIMAL
    assert disclosed.disclosed_facts == ("the user lives in Berlin",)


def test_functional_adds_the_preferences() -> None:
    disclosed = decide_disclosure(
        profile(
            fact("the user lives in Berlin"),
            preferences=("short replies", "no emoji"),
            settings=("morning sessions",),
        ),
        policy(rule(DisclosureLevel.FUNCTIONAL, PERSONA_A)),
        PERSONA_A,
    )
    assert disclosed.disclosure_level is DisclosureLevel.FUNCTIONAL
    assert disclosed.disclosed_facts == (
        "the user lives in Berlin",
        "short replies",
        "no emoji",
    )


def test_rich_adds_the_settings() -> None:
    disclosed = decide_disclosure(
        profile(
            fact("the user lives in Berlin"),
            preferences=("short replies",),
            settings=("morning sessions",),
        ),
        policy(rule(DisclosureLevel.RICH, PERSONA_A)),
        PERSONA_A,
    )
    assert disclosed.disclosure_level is DisclosureLevel.RICH
    assert disclosed.disclosed_facts == (
        "the user lives in Berlin",
        "short replies",
        "morning sessions",
    )


def test_no_rule_means_an_empty_minimal_disclosure() -> None:
    """Fail-closed: an unconfigured world discloses nothing."""

    full = profile(fact("the user lives in Berlin"), preferences=("a",))
    for policy_value in (None, policy()):
        disclosed = decide_disclosure(full, policy_value, PERSONA_A)
        assert disclosed.disclosure_level is DisclosureLevel.MINIMAL
        assert disclosed.disclosed_facts == ()
    # … and a missing profile is empty too, never an error.
    empty = decide_disclosure(
        None, policy(rule(DisclosureLevel.RICH, PERSONA_A)), PERSONA_A
    )
    assert empty.disclosed_facts == ()


# -- ② the high-sensitivity disclosure rule ---------------------------------


def test_a_persona_specific_rich_rule_discloses_high_sensitivity() -> None:
    disclosed = decide_disclosure(
        profile(fact("a sensitive fact", HIGH)),
        policy(rule(DisclosureLevel.RICH, PERSONA_A)),
        PERSONA_A,
    )
    assert disclosed.disclosed_facts == ("a sensitive fact",)


def test_the_same_rule_of_another_level_does_not() -> None:
    for level in (DisclosureLevel.MINIMAL, DisclosureLevel.FUNCTIONAL):
        disclosed = decide_disclosure(
            profile(fact("a sensitive fact", HIGH)),
            policy(rule(level, PERSONA_A)),
            PERSONA_A,
        )
        assert disclosed.disclosed_facts == ()
        assert disclosed.disclosure_level is level


def test_the_default_rule_never_discloses_high_sensitivity() -> None:
    """At any level: "everyone may know this" is not explicit consent for the
    most sensitive class of fact (§18.1)."""

    for level in (
        DisclosureLevel.MINIMAL,
        DisclosureLevel.FUNCTIONAL,
        DisclosureLevel.RICH,
    ):
        disclosed = decide_disclosure(
            profile(fact("a sensitive fact", HIGH)),
            policy(rule(level)),
            PERSONA_A,
        )
        assert disclosed.disclosed_facts == ()
        assert disclosed.disclosure_level is level


def test_a_richer_context_rule_does_not_upgrade_the_default() -> None:
    """A named rule for persona A plus a default rule: B is governed by the
    default, so A's RICH grant never leaks one axis over."""

    policy_value = policy(
        rule(DisclosureLevel.RICH, PERSONA_A),
        rule(DisclosureLevel.MINIMAL),
    )
    for persona in (PERSONA_A, PERSONA_B):
        disclosed = decide_disclosure(
            profile(fact("a sensitive fact", HIGH), fact("a personal fact")),
            policy_value,
            persona,
        )
        if persona == PERSONA_A:
            assert disclosed.disclosure_level is DisclosureLevel.RICH
            # The profile's own storage order is preserved (the sensitive
            # fact was stored first).
            assert disclosed.disclosed_facts == ("a sensitive fact", "a personal fact")
        else:
            # B is governed by the default rule: its own MINIMAL grant (the
            # PERSONAL fact), and nothing of A's — no level, no fact.
            assert disclosed.disclosure_level is DisclosureLevel.MINIMAL
            assert disclosed.disclosed_facts == ("a personal fact",)


def test_personas_are_independent() -> None:
    """Both personas have their own rule: neither sees the other's grant, and
    the disclosed set is decided per persona."""

    policy_value = policy(
        rule(DisclosureLevel.RICH, PERSONA_A),
        rule(DisclosureLevel.MINIMAL, PERSONA_B),
    )
    full = profile(
        fact("a personal fact"),
        fact("a sensitive fact", HIGH),
        preferences=("short replies",),
        settings=("morning sessions",),
    )
    disclosed_a = decide_disclosure(full, policy_value, PERSONA_A)
    disclosed_b = decide_disclosure(full, policy_value, PERSONA_B)
    assert disclosed_a.disclosure_level is DisclosureLevel.RICH
    assert "a sensitive fact" in disclosed_a.disclosed_facts
    assert disclosed_b.disclosure_level is DisclosureLevel.MINIMAL
    assert disclosed_b.disclosed_facts == ("a personal fact",)
    assert disclosed_b.persona_id is PERSONA_B


def test_the_first_matching_rule_wins_deterministically() -> None:
    policy_value = policy(
        rule(DisclosureLevel.RICH, PERSONA_A),
        rule(DisclosureLevel.MINIMAL, PERSONA_A),
    )
    decided = decide_disclosure(profile(fact("x")), policy_value, PERSONA_A)
    assert decided.disclosure_level is DisclosureLevel.RICH
    again = decide_disclosure(profile(fact("x")), policy_value, PERSONA_A)
    assert again == decided


# -- ② the durable rows -----------------------------------------------------


def test_the_store_replays_an_identical_profile_with_zero_writes(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    value = profile(fact("the user lives in Berlin"), preferences=("short replies",))
    first = user_config_store.upsert_user_profile(value)
    assert isinstance(first, Ok)
    before = profile_row(db, REL_USER)

    again = user_config_store.upsert_user_profile(value)
    assert isinstance(again, Ok)
    assert again.value.updated_at == first.value.updated_at
    assert profile_row(db, REL_USER) == before


def test_a_new_revision_replaces_the_content(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_user_profile(profile(fact("first"))), Ok
    )
    moved = user_config_store.upsert_user_profile(
        profile(fact("second"), revision="rev-2")
    )
    assert isinstance(moved, Ok)
    row = profile_row(db, REL_USER)
    assert row[1] == "rev-2"
    assert "second" in str(row[2])
    assert db.execute("SELECT COUNT(*) FROM user_profile").fetchone() == (1,)


def test_the_same_revision_with_different_content_is_a_conflict(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_user_profile(profile(fact("first"))), Ok
    )
    before = profile_row(db, REL_USER)
    refused = user_config_store.upsert_user_profile(profile(fact("second")))
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert profile_row(db, REL_USER) == before


def test_the_policy_has_the_same_stamp_discipline(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    first = policy(rule(DisclosureLevel.MINIMAL, PERSONA_A))
    assert isinstance(user_config_store.set_disclosure_policy(first), Ok)
    before = policy_row(db, REL_USER)

    replay = user_config_store.set_disclosure_policy(first)
    assert isinstance(replay, Ok)
    assert policy_row(db, REL_USER) == before

    moved = user_config_store.set_disclosure_policy(
        policy(rule(DisclosureLevel.RICH, PERSONA_A), revision="pol-2")
    )
    assert isinstance(moved, Ok)
    assert policy_row(db, REL_USER)[1] == "pol-2"

    conflicted = user_config_store.set_disclosure_policy(
        policy(rule(DisclosureLevel.MINIMAL, PERSONA_A), revision="pol-2")
    )
    assert not isinstance(conflicted, Ok)
    assert conflicted.error.code.value == "CONFLICT"


def test_the_facts_round_trip_with_their_data_class(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_user_profile(
            profile(
                fact("a personal fact"),
                fact("a sensitive fact", HIGH),
                preferences=("short replies",),
                settings=("morning sessions",),
            )
        ),
        Ok,
    )
    read = user_config_store.get_user_profile(REL_USER)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.profile_facts[0].sensitivity is PERSONAL
    assert read.value.profile_facts[1].sensitivity is HIGH
    assert read.value.preferences == ("short replies",)
    assert read.value.settings == ("morning sessions",)


def test_reads_are_scoped_to_the_asked_user(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_user_profile(profile(fact("berlin"))), Ok
    )
    other = user_config_store.get_user_profile(UserId("user-2"))
    assert isinstance(other, Ok) and other.value is None
    other_policy = user_config_store.get_disclosure_policy(UserId("user-2"))
    assert isinstance(other_policy, Ok) and other_policy.value is None


# -- ② the controller's read face -------------------------------------------


def test_the_disclosed_view_is_produced_by_the_controller(
    user_config_controller: UserConfigController,
) -> None:
    written = _controller_with(
        user_config_controller,
        facts=(fact("the user lives in Berlin"),),
        rules=(rule(DisclosureLevel.FUNCTIONAL, PERSONA_A),),
    )
    assert isinstance(written, Ok)
    disclosed = user_config_controller.get_disclosed_user_profile(
        REL_USER, PERSONA_A
    )
    assert isinstance(disclosed, Ok)
    assert disclosed.value == DisclosedUserProfile(
        persona_id=PERSONA_A,
        disclosure_level=DisclosureLevel.FUNCTIONAL,
        disclosed_facts=("the user lives in Berlin",),
    )
    # Another persona with no rule of its own: the empty MINIMAL view.
    other = user_config_controller.get_disclosed_user_profile(REL_USER, PERSONA_B)
    assert isinstance(other, Ok)
    assert other.value.disclosed_facts == ()


def test_an_unknown_user_discloses_nothing_and_raises_nothing(
    user_config_controller: UserConfigController,
) -> None:
    disclosed = user_config_controller.get_disclosed_user_profile(
        UserId("user-unknown"), PERSONA_A
    )
    assert isinstance(disclosed, Ok)
    assert disclosed.value.disclosure_level is DisclosureLevel.MINIMAL
    assert disclosed.value.disclosed_facts == ()


def test_the_full_profile_still_reads_back_for_the_authority_face(
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_controller.upsert_user_profile(
            profile(fact("the user lives in Berlin")), explicit_consent=False
        ),
        Ok,
    )
    full = user_config_controller.get_user_profile(REL_USER)
    assert isinstance(full, Ok) and full.value is not None
    assert full.value.profile_facts[0].text == "the user lives in Berlin"


# -- ② the Phase 6 faces stay skeletons -------------------------------------


def test_the_phase_six_faces_still_raise_with_a_pointer(
    user_config_controller: UserConfigController,
) -> None:
    from elc.platform.types import GoalVersion, PolicyVersion
    from elc.user_config.types import (
        LearningGoalPortfolio,
        SessionFocus,
        TeachingPolicyProfile,
    )

    for call in (
        lambda: user_config_controller.upsert_goal_portfolio(
            LearningGoalPortfolio(
                user_id=REL_USER,
                goal_version=GoalVersion("gv-1"),
                goals=(),
            )
        ),
        lambda: user_config_controller.upsert_teaching_policy(
            TeachingPolicyProfile(
                user_id=REL_USER,
                policy_version=PolicyVersion("pv-1"),
                teaching_frequency="BALANCED",
                automatic_teaching_enabled=False,
            )
        ),
        lambda: user_config_controller.set_session_focus(
            SessionFocus(
                user_id=REL_USER, focus_goal_ids=(), weight_override={}
            )
        ),
    ):
        with pytest.raises(NotImplementedError) as raised:
            call()
        assert "Phase 6" in str(raised.value)
