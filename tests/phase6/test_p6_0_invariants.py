"""P6-0 ⑤ — the four invariants, each pinned by a counter-case.

- **① a teaching-policy write changes nothing on the learning face.** The
  rows are produced by the real chain (one natural chat turn → one silent
  Performance Evidence claim → the §11 state rebuild), the three
  configuration objects are then written through their authority face, and
  every learning-owned row must still be byte-identical. A policy is
  how/how-often configuration, never Learner State truth (DOMAIN_MODEL §5.1
  Rules);
- **② a focus write never rewrites the long-term portfolio.** SessionFocus
  is explicitly the *temporary* re-weighting ("`GlobalGoalPortfolio` 可被
  `SessionFocus` 临时重加权，但不能静默修改长期目标"), so the durable
  portfolio row is compared column by column around a focus write;
- **③ configuration produces no claim.** A goal, a policy and a focus are
  not Evidence: no evidence / state / moment row appears, and the store's own
  statements cannot reach a learning table (the AST half lives in
  tests/phase6/test_p6_0_store.py);
- **④ Persona Runtime still only receives DisclosedUserProfile.** The port
  that fills the prompt has one method and it returns the disclosed view; and
  a compile with the controller's view is byte-identical before and after the
  three writes.
"""

from __future__ import annotations

import ast
import sqlite3

from elc.persona.commands import PromptCompiler
from elc.persona.types import (
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
)
from elc.platform.types import (
    ConversationId,
    GoalModality,
    InteractionChannel,
    Ok,
    PersonaId,
)
from elc.runtime.types import GenerationActionType
from elc.user_config.controller import UserConfigController
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    UserProfile,
)
from tests.conftest import SRC_ROOT

from .conftest import (
    SILENT_UTTERANCE,
    USER,
    commit_chat_turn,
    goal,
    portfolio,
    session_focus,
    teaching_policy,
)

PERSONA = PersonaId("persona-p6-0")
PERSONA_VIEWS = SRC_ROOT / "runtime" / "persona_views.py"

#: The learning-owned tables a configuration write must leave alone.
LEARNING_TABLES = (
    "evidence_claim",
    "evidence_commit",
    "evidence_group",
    "evidence_watermark",
    "learner_target_state",
    "learning_opportunity_record",
    "expression_need",
    "learner_self_report",
    "teaching_moment",
    "attempt_record",
    "gate_decision",
    "active_teaching_lock",
)

PORTFOLIO_COLUMNS = (
    "goal_portfolio_id",
    "goal_version",
    "goals",
    "modality_weights",
    "assessment_targets",
    "register_style_goals",
    "effective_from",
    "updated_at",
)


def _learning_snapshot(db: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Every learning-owned row, in durable order."""

    return {
        table: [
            tuple(row)
            for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]
        for table in LEARNING_TABLES
    }


def _portfolio_row(db: sqlite3.Connection) -> tuple[object, ...]:
    row = db.execute(
        f"SELECT {', '.join(PORTFOLIO_COLUMNS)} FROM goal_portfolio"
    ).fetchone()
    assert row is not None, "no goal_portfolio row"
    return tuple(row)


def test_a_teaching_policy_write_leaves_the_learning_face_untouched(
    db: sqlite3.Connection,
    conversation,
    silent_coordinator,
    user_config_controller: UserConfigController,
) -> None:
    del conversation
    completion = commit_chat_turn(
        silent_coordinator, "cm-p6-0-invariant", SILENT_UTTERANCE, 1
    )
    assert completion.outcome == "REPLIED_FULL"
    before = _learning_snapshot(db)
    # The chain really produced learning rows (the comparison is not vacuous).
    assert len(before["evidence_claim"]) == 1
    assert len(before["learner_target_state"]) == 1
    assert before["teaching_moment"] == []

    assert isinstance(
        user_config_controller.upsert_goal_portfolio(portfolio(goal("g-1"))), Ok
    )
    assert isinstance(
        user_config_controller.upsert_teaching_policy(teaching_policy()), Ok
    )
    moved = user_config_controller.upsert_teaching_policy(
        teaching_policy(version="pv-2", mode="SOCRATIC")
    )
    assert isinstance(moved, Ok), moved
    assert isinstance(
        user_config_controller.set_session_focus(session_focus("sf-1")), Ok
    )

    after = _learning_snapshot(db)
    assert after == before
    assert list(after) == list(LEARNING_TABLES)


def test_a_focus_write_never_rewrites_the_long_term_portfolio(
    db: sqlite3.Connection,
    user_config_controller: UserConfigController,
    conversation,
) -> None:
    del conversation
    written = user_config_controller.upsert_goal_portfolio(
        portfolio(goal("g-1"), goal("g-2", description="another goal"))
    )
    assert isinstance(written, Ok), written
    before = _portfolio_row(db)

    assert isinstance(
        user_config_controller.set_session_focus(
            session_focus("sf-1", weights={GoalModality.READING: 1.0})
        ),
        Ok,
    )
    refused = user_config_controller.set_session_focus(
        session_focus("sf-1", weights={GoalModality.WRITING: 1.0})
    )
    assert not isinstance(refused, Ok)

    after = _portfolio_row(db)
    assert after == before
    for column, previous, current in zip(PORTFOLIO_COLUMNS, before, after):
        assert previous == current, column
    read = user_config_controller.get_goal_portfolio(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert [goal_item.goal_id for goal_item in read.value.goals] == ["g-1", "g-2"]


def test_the_persona_port_still_carries_only_the_disclosed_profile() -> None:
    """The port the coordinator fills the prompt through has exactly one
    method — ``get_disclosed_user_profile`` — and the composition reaches the
    user-config face through nothing else."""

    from elc.runtime.persona_views import (
        ControllerPersonaViews,
        DisclosedProfileSource,
    )

    declared = {
        name for name in vars(DisclosedProfileSource) if not name.startswith("_")
    }
    assert declared == {"get_disclosed_user_profile"}

    source = PERSONA_VIEWS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    touched: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name != ControllerPersonaViews.__name__:
            continue
        for attribute in ast.walk(node):
            if not isinstance(attribute, ast.Attribute):
                continue
            owner = attribute.value
            if (
                isinstance(owner, ast.Attribute)
                and owner.attr == "_user_config"
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
            ):
                touched.add(attribute.attr)
    assert touched == {"get_disclosed_user_profile"}
    for name in (
        "get_goal_portfolio",
        "get_teaching_policy",
        "get_session_focus",
        "get_user_profile",
    ):
        assert name not in source, name


def test_configuration_writes_change_no_prompt_byte(
    user_config_controller: UserConfigController,
    conversation,
) -> None:
    """④'s behavioral half: the compiled prompt for one persona is
    byte-identical before and after the three configuration writes — nothing
    in the goal / policy / focus rows reaches the persona path in this
    slice."""

    del conversation

    assert isinstance(
        user_config_controller.upsert_user_profile(
            UserProfile(
                user_profile_id=USER,
                revision="rev-1",
                preferences=("short replies",),
            ),
            explicit_consent=True,
        ),
        Ok,
    )
    assert isinstance(
        user_config_controller.set_disclosure_policy(
            DisclosurePolicy(
                disclosure_policy_id=str(USER),
                revision="pol-1",
                rules=(
                    DisclosureRule(
                        persona_id=PERSONA,
                        disclosure_level=DisclosureLevel.FUNCTIONAL,
                    ),
                ),
            )
        ),
        Ok,
    )
    before = _compile(user_config_controller)
    assert "[profile]" in before
    assert "short replies" in before

    assert isinstance(
        user_config_controller.upsert_goal_portfolio(portfolio(goal("g-1"))), Ok
    )
    assert isinstance(
        user_config_controller.upsert_teaching_policy(
            teaching_policy(mode="SOCRATIC")
        ),
        Ok,
    )
    assert isinstance(
        user_config_controller.set_session_focus(session_focus("sf-1")), Ok
    )
    assert _compile(user_config_controller) == before


def _compile(controller: UserConfigController) -> str:
    """One persona-prompt compilation over the controller's disclosure view."""

    disclosed = controller.get_disclosed_user_profile(USER, PERSONA)
    assert isinstance(disclosed, Ok), disclosed
    contract = GenerationContract(
        generation_contract_id="gc-normal-persona-reply",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=PERSONA,
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
    )
    compiled = PromptCompiler().compile(
        PromptCompilationRequest(
            conversation_id=ConversationId("conv-p6-0"),
            persona_id=PERSONA,
            interaction_channel=InteractionChannel.TEXT,
            generation_context=GenerationContext(
                character_package=None,
                relationship_view=None,
                episode_view=None,
                world_lore_view=None,
                disclosed_user_profile=disclosed.value,
                conversation_window=None,
                language_policy="default",
                generation_policy="default",
                generation_contract=contract,
                ephemeral_teaching_directive=None,
            ),
            generation_contract=contract,
        )
    )
    assert isinstance(compiled, Ok), compiled
    return compiled.value.prompt_text
