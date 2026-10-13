"""The fixed Gold Scenario of the Narrative V3 programme (V3-8d,
TASK-OPI-cddb517c-…21 / the opening ruling ``DEC-OPI-cddb517c-…19``) —
the acceptance screenplay the structural gates drive, not a generator.

**The scenario is fixed; the prose and the plan wording ride the
provider.** The paradigm shift's §10.2 固定要素, word for word: the
Empire's 105th year, the first day of the tenth month; Lia, the
household's daughter (``PROTAGONIST``, ``pov_eligible``); the reader's
character — the distant cousin from the countryside; the father's cart
gone down the capital road before dawn; the mother bringing the cousin
back from the countryside in the morning; the first meeting at the
courtyard gate; one real User Gate carrying the user's own free
submission; the Action Resolver's ruling; the story continuing along
the user's choice; the first chapter's settlement; the second chapter's
Blueprint planned from the first chapter's real outcome. This module
carries that skeleton as data: the world's seeds
(:func:`seed_gold_world`), the three scenes' beats
(:func:`gold_beats_by_scene`), the scripted answers the real LLM
providers are fed in CI (:class:`GoldScriptedCompletion`), and the
fixed payloads (:data:`CH1_BLUEPRINT` / :data:`CH1_REPLAN_BLUEPRINT` /
:data:`CH2_BLUEPRINT` / :data:`GOLD_ADJUDICATION_PAYLOAD`).

**The calendar** (the Bible's own declaration): one tick is one minute
of story time; tick 0 is 105-10-01 00:00; the father's cart took the
capital road at dawn (tick 300 = 05:00) and the mother brings the
cousin from the countryside in the morning (tick 480 = 08:00). The
chapter's first scene opens from tick 480, the gate stands at tick 540
= 09:00, and the scripted beats' durations carry the drive there — the
commits are the canonical time's only movers (N-INV-007), so this
fixture never writes a tick.

**The scripted completion** (:class:`GoldScriptedCompletion`) is a
:class:`~elc.world.llm_providers.TextCompletion` seam answered **by
prompt content, never by call order** — a pure function of the prompt,
so replaying the same prompt answers the same payload: the Writer arm's
answer is keyed by the ``(place, segment_seq)`` pair its prompt
carries, the Resolver arm's by the submission's own ``intent_text``,
the Director's CHAPTER replan by the ``replan_request_id``, and the
Director's initial arm by the first matching marker among the scripted
candidates (the second chapter's initial draft is recognised by the
first chapter's id riding its settled-summaries block; the single
``None`` marker is the fallback and sits last). A prompt this script
has no answer for raises :class:`GoldScriptError` — a scripted gap is a
loud programmer error, never a silently invented payload (the
deterministic fake's own posture, at the seam). Every prompt is
recorded in call order (``prompts`` / ``prompts_by_arm``) — the
evidence the acceptance gates read for what a provider could see.

**Two honesty statements.** (1) The drive this script feeds is a
**structural** acceptance: the production faces are real
(:mod:`elc.world.llm_providers` over this script), but no network call
happens and no model judges the prose — the user's own 「好玩」
acceptance is V3-8e's, with a real model. (2) ``must_hide`` is the
scene's real secret: scene 1's dossier forbids "the sealed letter from
the capital" and "the Imperial post's red seal"; the scripted prose
touches the secret's edge (the folded paper at the mother's sleeve) and
never names it, and :data:`LEAK_SAMPLE` is the deliberate violator the
leak gate feeds the deterministic guard.

Discipline: this module is a library fixture — value shapes and plain
data, no clock of its own, no state between calls; the one write it
performs is the persona cards' creation-time preamble
(:func:`seed_gold_world` — the ``world_actor`` FK's prerequisite),
which commits before the atomic creation service opens its own
transaction.
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from elc.platform.types import Result
from elc.world.action import Adjudication, ReplanScope
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.bootstrap import (
    ActorSeed,
    PlayerSeed,
    WorldCreationOutcome,
    create_world_with_bible,
)
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmDirectorProvider,
    LlmPlannerProvider,
    LlmResolverProvider,
    LlmWriterProvider,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.pipeline import GateBeat, Pipeline, SegmentBeat
from elc.world.store import SqliteWorldStore
from elc.world.types import StateEffect

__all__ = [
    "ACTION_DURATION_TICKS",
    "ACTION_ID",
    "BIBLE_REVISION_ID",
    "CH1",
    "CH1_BLUEPRINT",
    "CH1_REPLAN_BLUEPRINT",
    "CH2",
    "CH2_BLUEPRINT",
    "GATE",
    "GATE_OPTIONS",
    "GOLD_ACTORS",
    "GOLD_ADJUDICATION_PAYLOAD",
    "GOLD_BIBLE",
    "GOLD_INTENT",
    "GOLD_PLAYER",
    "GOLD_PROSE",
    "GoldScriptError",
    "GoldScriptedCompletion",
    "LEAK_SAMPLE",
    "LIA",
    "MOTHER",
    "MOTHER_PRIVATE",
    "MUST_HIDE",
    "MUST_HIDE_FRAGMENTS",
    "PLACE_CH2_ROAD",
    "PLACE_CH2_YARD",
    "PLACE_GATE",
    "PLACE_GUEST_ROOM",
    "PLACE_KITCHEN",
    "PLACE_MAP_ROOM",
    "PLACE_MARKET",
    "PLACE_TOWER",
    "PLAN_R1",
    "PLAN_R2",
    "PLAYER",
    "REPLAN_REQUEST_ID",
    "S1",
    "S2",
    "S3",
    "S4",
    "SUBMISSION_ID",
    "TICK_CH1_END",
    "TICK_GATE_OPENS",
    "WORLD_ID",
    "WORLD_NAME",
    "build_gold_pipeline",
    "gold_adjudication",
    "gold_beats_by_scene",
    "gold_completion",
    "seed_gold_world",
]

# ---------------------------------------------------------------------------
# the fixed identities (the scenario's skeleton)
# ---------------------------------------------------------------------------

WORLD_ID = "gold-empire-105"
WORLD_NAME = "Greenhollow at the Edge of the Empire"
BIBLE_REVISION_ID = f"{WORLD_ID}-bible-r1"

LIA = "lia"
MOTHER = "mother"
PLAYER = "cousin"
PERSONA_LIA = "persona-lia"
PERSONA_MOTHER = "persona-mother"

CH1 = f"{WORLD_ID}-ch01"
CH2 = f"{WORLD_ID}-ch02"
S1 = f"{CH1}-s01"
S2 = f"{CH1}-s02"
S3 = f"{CH1}-s03"
S4 = f"{CH1}-s04"
GATE = f"{S1}-g01"
ACTION_ID = f"{GATE}-a"
SUBMISSION_ID = "gold-sub-1"
REPLAN_REQUEST_ID = f"rp:{GATE}:{SUBMISSION_ID}"
PLAN_R1 = f"{CH1}-bp-r1"
PLAN_R2 = f"{CH1}-bp-r2"
PLAN_CH2_R1 = f"{CH2}-bp-r1"

#: The ruling's story-time cost (the pipeline instance's one calibration).
ACTION_DURATION_TICKS = 30

#: The fixed clock faces the beats' durations land on (the commits'
#: actual ticks): the gate stands at 09:00, the first chapter ends at
#: 11:30 — ninety ticks past its own optimistic planned window (the
#: chapter planned [0, 600], the actual end 690).
TICK_GATE_OPENS = 540
TICK_CH1_END = 690

S1_SEGMENT_1_TICKS = 300
S1_SEGMENT_2_TICKS = 240
S1_SEGMENT_3_TICKS = 30
S2_SEGMENT_1_TICKS = 30
S2_SEGMENT_2_TICKS = 30
S3_SEGMENT_1_TICKS = 30

#: The private context each AI actor's ``world_actor_profile`` carries.
#: ``MOTHER_PRIVATE`` is the POV-safe contrast witness: it rides the
#: world-authoritative Director's prompts (the full cast reading) and
#: never a POV-limited one (the Writer's). The Resolver's counterpart
#: arm carries only the ruling scene's participants minus the player,
#: and Mother is no scene's participant — so in this fixture the
#: Resolver's prompts do not carry it either.
LIA_PRIVATE = (
    "LIA_PRIVATE: she noticed the folded paper at Mother's sleeve before"
    " anyone else did."
)
MOTHER_PRIVATE = (
    "MOTHER_PRIVATE: she has read the red seal and knows what the"
    " household will be asked to do."
)

#: Scene 1's real secret, in the dossier's own frame: the must_hide
#: fragments (line 1 / line 2, the guard's own split).
MUST_HIDE = (
    "the sealed letter from the capital\nthe Imperial post's red seal"
)
MUST_HIDE_FRAGMENTS = (
    "the sealed letter from the capital",
    "the Imperial post's red seal",
)

#: The places — one per scene, so a prompt's ``place`` line names the
#: scene the scripted prose belongs to (the completion's writer key).
PLACE_GATE = "the courtyard gate of the Li family compound"
PLACE_GUEST_ROOM = "the west guest room"
PLACE_MARKET = "the market square below the compound"
PLACE_TOWER = "the compound's east watchtower"
PLACE_KITCHEN = "the kitchen of the Li compound"
PLACE_MAP_ROOM = "the map room above the storehouse"
PLACE_CH2_YARD = "the storehouse yard at first light"
PLACE_CH2_ROAD = "the capital road above the town"

#: The gate's natural behaviour options (three of them — the free-text
#: arm is implied) and the user's own submission. The intent is what
#: makes the original plan untenable: it refuses the guest treatment the
#: planned scenes are built around.
GATE_OPTIONS = (
    "offer the courtyard bench and water",
    "ask straight out who he is and why now",
    "let Mother do the explaining",
)
GOLD_INTENT = (
    "I will not be settled like a parcel. The pack stays on the"
    " gate-stone until someone tells me why this house smells of a hard"
    " ride this morning."
)

# ---------------------------------------------------------------------------
# the Bible and the seeds
# ---------------------------------------------------------------------------

GOLD_BIBLE = BibleContent(
    premise=(
        "Greenhollow, a waystation town at the last bend before the"
        " capital road climbs west into the hills, on the first day of"
        " the tenth month of the Empire's 105th year. The Li household"
        " keeps a storehouse, a walled yard, and a father who has just"
        " taken the capital road before dawn."
    ),
    genre="quiet historical family drama",
    tone="plain-spoken and close to the ground, warm under the surface",
    calendar=(
        "One tick is one minute of story time. Tick 0 is the first watch"
        " of the tenth month of the 105th year of the Empire:"
        " 105-10-01 00:00. The father's cart took the capital road at"
        " dawn (tick 300 = 05:00); the mother brings the cousin from the"
        " countryside in the morning (tick 480 = 08:00)."
    ),
    physics="Ordinary; nothing in this world bends a rule of physics.",
    magic_rules="None. Magic does not exist in this world.",
    geography=(
        "The market town of Greenhollow sits in a river bend; the"
        " capital road climbs west into the hills, one imperial post"
        " relay beyond the town."
    ),
    society=(
        "Farmers, carters and one post relay; household bonds carry"
        " more weight than any town office."
    ),
    politics=(
        "Distant and paper-thin: the capital's decrees arrive as"
        " letters, never as soldiers."
    ),
    technology=(
        "Carts, horses, hand tools, oil lamps, and the imperial post's"
        " relay horses."
    ),
    religion=(
        "Loose household customs and a roadside shrine at the"
        " crossroads; no temple in town."
    ),
    history=(
        "The post road came first and the town grew around its stopping"
        " house; the Li storehouse is older than the wall around it."
    ),
    hard_rules=(
        "A letter from the capital reaches Greenhollow no sooner than"
        " the next day, however hard the rider presses. No one in this"
        " household opens a sealed letter that is not theirs."
    ),
    narrative_preferences=(
        "Quiet domestic scenes; the world's rules never bend for a"
        " convenience, and no scene narrates a future that has not"
        " happened."
    ),
)

GOLD_ACTORS = (
    ActorSeed(
        actor_id=LIA,
        persona_id=PERSONA_LIA,
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=1,
        long_term_drive=(
            "keep the household's accounts straight until Father is back"
        ),
        current_arc_seed=(
            "the morning the house would not say where it had ridden"
        ),
        private_context=LIA_PRIVATE,
    ),
    ActorSeed(
        actor_id=MOTHER,
        persona_id=PERSONA_MOTHER,
        story_role=StoryRole.SUPPORTING,
        pov_eligible=True,
        pov_weight=2,
        long_term_drive=(
            "hold the household together until the capital answers"
        ),
        current_arc_seed=(
            "a letter she has not decided how to speak of"
        ),
        private_context=MOTHER_PRIVATE,
    ),
)

GOLD_PLAYER = PlayerSeed(
    player_character_id=PLAYER,
    name="Renn",
    background=(
        "the distant cousin from the countryside, sent to the town"
        " household for the winter"
    ),
    appearance="a dusty coat and a pack he will not set down",
    abilities="steady hands with animals, and a good ear",
    limits="no standing in the town's eyes; he is a stranger here",
    location="on the road in from the countryside",
    state="tired from the walk",
    knowledge_refs="the household's letter that told him to come now",
)

#: The persona cards the ``world_actor`` FK requires, in the same order
#: as the seeds: (persona_id, name, identity, personality, background,
#: speech_style, values, boundaries).
GOLD_PERSONA_CARDS = (
    (
        PERSONA_LIA,
        "Lia",
        "the household's daughter, sixteen, keeps the storehouse books",
        "watchful, dry-humoured, slow to ask and quick to notice",
        "raised in the storehouse counting carts and candles",
        "short sentences, answers questions with questions",
        "the household's name, and a straight account of any ledger",
        "she will not be lied to twice about the same morning",
    ),
    (
        PERSONA_MOTHER,
        "Mother",
        "the household's head while Father is away",
        "brisk, careful with words, carries more than she says",
        "she has run the yard through three bad winters",
        "warm in the yard, clipped at the table",
        "the household's safety before its comfort",
        "she does not explain a thing before she must",
    ),
)

# ---------------------------------------------------------------------------
# the scripted Blueprints (the providers' answers)
# ---------------------------------------------------------------------------

CH1_SCENE_1: dict[str, Any] = {
    "purpose": "first sight: the cousin arrives at the gate",
    "place": PLACE_GATE,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 480,
    "entry_goals": (
        "welcome the cousin before the morning's unease can show"
    ),
    "exit_condition": (
        "the cousin is invited in, or left standing at the gate"
    ),
    "elasticity": "may run long if the greeting turns awkward",
    "revealable": (
        "that a courier rode hard up the capital road this morning"
    ),
    "must_hide": MUST_HIDE,
}

CH1_SCENE_2: dict[str, Any] = {
    "purpose": "the guest room and the unpacking",
    "place": PLACE_GUEST_ROOM,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 480,
    "entry_goals": "show the cousin where he will sleep and let him unpack",
    "exit_condition": "the pack is opened, or closed for good",
    "elasticity": "short",
    "revealable": "the shelf where Father keeps his road maps",
    "must_hide": "",
}

CH1_SCENE_3: dict[str, Any] = {
    "purpose": "the evening walk through the town",
    "place": PLACE_MARKET,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 480,
    "entry_goals": "walk the cousin through the town so the town sees him",
    "exit_condition": "the walk ends, or is cut short",
    "elasticity": "may stretch past dusk",
    "revealable": "who in town is owed an explanation",
    "must_hide": "",
}

CH1_SCENE_4: dict[str, Any] = {
    "purpose": "the first quiet night",
    "place": PLACE_TOWER,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 480,
    "entry_goals": "keep the cousin's first night quiet",
    "exit_condition": "the night closes",
    "elasticity": "short",
    "revealable": "the light of the post relay on the capital road",
    "must_hide": "",
}

#: The first chapter's initial Blueprint — the Director prompt's answer
#: for a world whose summaries block is empty. Its optimistic window
#: ([0, 600]) and its four-scene roster are the plan the actual chapter
#: visibly diverges from (the acceptance's honesty witness).
CH1_BLUEPRINT: dict[str, Any] = {
    "goal": (
        "Get the cousin from the countryside settled into the household"
        " before the first frost."
    ),
    "dramatic_question": (
        "Will the stranger from the countryside be taken in as family,"
        " or kept at arm's length?"
    ),
    "planned_start_tick": 0,
    "planned_end_tick": 600,
    "closing_pressure": (
        "the household's patience presses against the stranger's silence"
    ),
    "desired_development": (
        "the first meeting loosens into something like trust"
    ),
    "soft_outcomes": "a seat at the evening table, perhaps",
    "chapter_questions_to_advance": (
        "what is waiting for this household in the capital?"
    ),
    "scenes": [CH1_SCENE_1, CH1_SCENE_2, CH1_SCENE_3, CH1_SCENE_4],
}

CH1_REPLAN_SCENE_1: dict[str, Any] = {
    "purpose": "first sight: the cousin arrives at the gate (kept)",
    "place": PLACE_GATE,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 480,
    "entry_goals": (
        "hold the yard together around whatever the stranger decides"
    ),
    "exit_condition": "the gate's question is settled for the morning",
    "elasticity": "may run long if the greeting turns awkward",
    "revealable": (
        "that a courier rode hard up the capital road this morning"
    ),
    "must_hide": MUST_HIDE,
}

CH1_REPLAN_SCENE_2: dict[str, Any] = {
    "purpose": "the kitchen: the cousin's question cannot be put down",
    "place": PLACE_KITCHEN,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 600,
    "entry_goals": "feed the cousin and answer nothing about the dawn",
    "exit_condition": "the question is met, or turned aside",
    "elasticity": "may run long",
    "revealable": "that Father's cart turned west at the crossroads",
    "must_hide": "",
}

CH1_REPLAN_SCENE_3: dict[str, Any] = {
    "purpose": "the map room before anyone asks",
    "place": PLACE_MAP_ROOM,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 660,
    "entry_goals": (
        "find what Father left in the map room, and what he took"
    ),
    "exit_condition": "the search is answered, or interrupted",
    "elasticity": "short",
    "revealable": "the map of the capital road",
    "must_hide": "",
}

#: The CHAPTER replan's answer: the remaining part restated in the new
#: direction — the running scene kept, the two later scenes re-planned,
#: and the old tail (``CH1_SCENE_4``) left unclaimed (the reconciliation
#: retires it ``DISCARDED``).
CH1_REPLAN_BLUEPRINT: dict[str, Any] = {
    "goal": (
        "Find out what the household's morning is hiding, with the"
        " cousin standing in the yard."
    ),
    "dramatic_question": (
        "Can Lia keep the household's silence while the stranger asks"
        " the one question nobody will answer?"
    ),
    "planned_start_tick": 0,
    "planned_end_tick": 900,
    "closing_pressure": (
        "the gate-stone and the map room pull the morning in two"
        " directions at once"
    ),
    "desired_development": (
        "the cousin turns from a parcel into a question the house"
        " cannot put down"
    ),
    "soft_outcomes": "an answer, or an honest refusal to give one",
    "chapter_questions_to_advance": (
        "what is waiting for this household in the capital?"
    ),
    "scenes": [
        CH1_REPLAN_SCENE_1,
        CH1_REPLAN_SCENE_2,
        CH1_REPLAN_SCENE_3,
    ],
}

CH2_SCENE_1: dict[str, Any] = {
    "purpose": "first light: the cart to the capital is loaded",
    "place": PLACE_CH2_YARD,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 690,
    "entry_goals": "settle whose pack goes on the cart and whose stays",
    "exit_condition": "the cart is loaded, or left standing",
    "elasticity": "short",
    "revealable": "the storehouse ledger's last page",
    "must_hide": "",
}

CH2_SCENE_2: dict[str, Any] = {
    "purpose": "the road out of Greenhollow",
    "place": PLACE_CH2_ROAD,
    "pov_actor_id": LIA,
    "participants": [LIA, PLAYER],
    "planned_start_tick": 900,
    "entry_goals": "climb to the crossroads and decide at the turn",
    "exit_condition": "the turn is taken, or refused",
    "elasticity": "may run to the relay and back",
    "revealable": "what the relay keeper saw at dawn",
    "must_hide": "",
}

#: The second chapter's Blueprint — planned **from the first chapter's
#: real outcome**: the gate-stone morning, the carved wooden horse, the
#: household's silence. Its scenes pick up where the first chapter
#: actually closed (tick 690).
CH2_BLUEPRINT: dict[str, Any] = {
    "goal": (
        "Follow the carved wooden horse: get the household — and the"
        " cousin camped at the gate — onto the capital road before the"
        " second frost."
    ),
    "dramatic_question": (
        "Will Lia carry the household's silence all the way to the"
        " capital, or set it down at the crossroads?"
    ),
    "planned_start_tick": 690,
    "planned_end_tick": 1200,
    "closing_pressure": (
        "the cart to the capital leaves at first light and the house is"
        " not ready"
    ),
    "desired_development": (
        "the cousin's stubbornness turns from an obstacle into a compass"
    ),
    "soft_outcomes": "a place on the cart, maybe",
    "chapter_questions_to_advance": (
        "what is waiting for this household in the capital?"
    ),
    "scenes": [CH2_SCENE_1, CH2_SCENE_2],
}

# ---------------------------------------------------------------------------
# the scripted ruling (the Resolver's answer)
# ---------------------------------------------------------------------------

#: The gate's ruling, in the wire shape the parser reads: the user's
#: choice really does invalidate the plan (``replan_scope`` CHAPTER — the
#: day's plan to settle the cousin as a guest no longer stands), the
#: state effect lands a current fact the second chapter plans from, and
#: the participants carry the user and Lia.
GOLD_ADJUDICATION_PAYLOAD: dict[str, Any] = {
    "interpretation": (
        "He is not refusing the house; he is refusing to be handled like"
        " cargo, and the question about the hard ride is the real"
        " submission."
    ),
    "outcome": (
        "The cousin's pack stays on the gate-stone; the household's plan"
        " to settle him as a guest is set aside, and Mother must answer"
        " him now, in the yard, or let the lane hear the silence."
    ),
    "actual_action": (
        "he sets the pack down at the gate and stands his ground in the"
        " yard"
    ),
    "consequences": (
        "the day's plan no longer stands: the guest room will stay cold,"
        " and the evening will not follow the house's script"
    ),
    "state_effects": [
        {
            "key": "household:cousin",
            "statement": "camped at the gate; the guest room refused",
        }
    ],
    "participants": [PLAYER, LIA],
    "replan_scope": "CHAPTER",
}

#: The ruling as the frozen record (for the callers that compare against
#: the library shape rather than the wire payload).
_GOLD_STATE_EFFECT = StateEffect(
    key="household:cousin", statement="camped at the gate; the guest room refused"
)


def gold_adjudication() -> Adjudication:
    """The scripted ruling in its library shape (:class:`Adjudication`)
    — the same content :data:`GOLD_ADJUDICATION_PAYLOAD` answers over the
    wire."""

    return Adjudication(
        interpretation=GOLD_ADJUDICATION_PAYLOAD["interpretation"],
        outcome=GOLD_ADJUDICATION_PAYLOAD["outcome"],
        actual_action=GOLD_ADJUDICATION_PAYLOAD["actual_action"],
        consequences=GOLD_ADJUDICATION_PAYLOAD["consequences"],
        state_effects=(_GOLD_STATE_EFFECT,),
        participants=(PLAYER, LIA),
        replan_scope=ReplanScope.CHAPTER,
    )


# ---------------------------------------------------------------------------
# the scripted prose (the Writer's answers)
# ---------------------------------------------------------------------------

S1_PROSE_1 = (
    "Before first light the compound is awake in pieces: the kettle, the"
    " bolt drawn back, and Father's cart already a mile down the capital"
    " road. Lia keeps the gate open and watches the grey come up over"
    " the hills."
)
S1_PROSE_2 = (
    "By mid-morning Mother comes up the lane with a stranger at her"
    " side. The dust on her hem says a hard ride; a corner of folded"
    " paper shows at her sleeve, and Lia looks away before it can show"
    " more."
)
S1_PROSE_3 = (
    "He sets the pack down on the gate-stone and does not step into the"
    " yard. Lia hears her own voice offer water, and hears the yard go"
    " quiet around the offer."
)
S2_PROSE_1 = (
    "In the kitchen the kettle works where the question cannot. The"
    " cousin sits at the long table and turns his cup as if it were a"
    " lock."
)
S2_PROSE_2 = (
    "He sets a carved wooden horse on the table between them: a gift he"
    " carried all the way for Father, and he says nothing about where"
    " Father has gone."
)
S3_PROSE_1 = (
    "The map room smells of cold ink. Lia sets the carved wooden horse"
    " on the map table, where the capital road lies inked from the"
    " crossroads west, and she stands there until the bell below marks"
    " the hour."
)

#: The deliberate violator the leak gate feeds the deterministic guard:
#: the prose names a ``must_hide`` fragment outright.
LEAK_SAMPLE = (
    "Mother turns her sleeve aside, and the sealed letter from the"
    " capital shows against the cloth."
)

#: The Writer arm's script, keyed by the scene's ``(place,
#: segment_seq)`` pair — the two faces the prompt carries. Scene 1's
#: post-gate continuation takes the ``(gate, 3)`` entry in both windows:
#: the full drive writes segments 1–2, the gate, then the continuation
#: as segment 3; the crash-resume window derives the continuation's
#: ordinal from the committed rows (``max + 1`` = 3) — the same place,
#: the same segment ordinal, the same honest prose either way.
GOLD_PROSE: dict[tuple[str, int], str] = {
    (PLACE_GATE, 1): S1_PROSE_1,
    (PLACE_GATE, 2): S1_PROSE_2,
    (PLACE_GATE, 3): S1_PROSE_3,
    (PLACE_KITCHEN, 1): S2_PROSE_1,
    (PLACE_KITCHEN, 2): S2_PROSE_2,
    (PLACE_MAP_ROOM, 1): S3_PROSE_1,
}


# ---------------------------------------------------------------------------
# the scripted completion (the four faces over one seam)
# ---------------------------------------------------------------------------

_ARM_WRITER = "writer"
_ARM_PLANNER = "planner"
_ARM_DIRECTOR = "director"
_ARM_RESOLVER = "resolver"

#: The four production faces' prompt openings (the arm classifier).
#: llm_providers' prompts open with these lines; a prompt that opens
#: with none of them is a face this script does not know.
_ARM_OPENINGS = (
    (_ARM_WRITER, "You are the POV writer"),
    (_ARM_PLANNER, "You are the scene planner"),
    (_ARM_DIRECTOR, "You are the world director"),
    (_ARM_RESOLVER, "You are the action resolver"),
)

#: The prompt lines the script keys its answers on (the writer's pair,
#: the resolver's intent, the planner's scene, the replan's request id).
_PLACE_LINE = re.compile(r"^- place: (.+)$", re.MULTILINE)
_SEQ_LINE = re.compile(r"^- segment_seq: (\d+)$", re.MULTILINE)
_INTENT_LINE = re.compile(r"^- intent_text: (.+)$", re.MULTILINE)
_SCENE_LINE = re.compile(r"^Scene: (\S+) \(world ", re.MULTILINE)
_REPLAN_LINE = re.compile(r"^- replan_request_id: (.+)$", re.MULTILINE)

#: The replan arm's own prompt block (the classifier's discriminator).
_REPLAN_BLOCK = "The replan's own faces:"


class GoldScriptError(RuntimeError):
    """A prompt this script has no scripted answer for — the loud
    programmer-error arm (the deterministic fake's ``ValueError``
    posture, at the seam): a gap in the screenplay raises, it never
    returns an invented payload."""


def _answer(payload: Mapping[str, Any]) -> CompletionOutcome:
    """One JSON arm's answer on the wire (the parser's own input
    shape)."""

    return CompletionOutcome(
        text=json.dumps(payload, ensure_ascii=False), error=None
    )


def _group(pattern: re.Pattern[str], prompt: str, name: str) -> str:
    """One keyed line's value, or the loud gap."""

    match = pattern.search(prompt)
    if match is None:
        raise GoldScriptError(
            f"the prompt carries no {name} line this script keys on —"
            " the scripted gap is answered loudly, never guessed"
        )
    return match.group(1)


class GoldScriptedCompletion:
    """The Gold Scenario's scripted stand-in for the
    :class:`~elc.world.llm_providers.TextCompletion` seam — a pure
    function of the prompt (see the module docstring for the keying
    laws), recording every prompt in call order.

    One instance rides all four providers
    (:func:`build_gold_pipeline` hands it to each): the arm classifier
    routes a prompt to the scripted face it addresses, then the arm's
    own key extracts the payload's coordinates — the writer's
    ``(place, segment_seq)``, the resolver's ``intent_text``, the
    planner's scene id, the director's replan request id or the initial
    marker. A miss raises :class:`GoldScriptError` naming what was
    looked for; nothing here ever answers a payload nobody scripted.
    """

    def __init__(
        self,
        *,
        prose: Mapping[tuple[str, int], str],
        adjudications: Mapping[str, Mapping[str, Any]],
        blueprints: Sequence[tuple[str | None, Mapping[str, Any]]],
        replan_blueprints: Mapping[str, Mapping[str, Any]],
        elements: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self._prose = dict(prose)
        self._adjudications = {
            key: dict(payload) for key, payload in adjudications.items()
        }
        self._blueprints = [
            (marker, dict(payload)) for marker, payload in blueprints
        ]
        if any(
            marker is None
            for marker, _ in self._blueprints[: len(self._blueprints) - 1]
        ):
            raise ValueError(
                "the gold script's initial-Blueprint candidates must"
                " carry their markers in order with the single fallback"
                " (marker ``None``) last — a fallback in front of a"
                " marker would shadow it"
            )
        self._replan_blueprints = {
            key: dict(payload) for key, payload in replan_blueprints.items()
        }
        self._elements = {
            key: dict(payload) for key, payload in (elements or {}).items()
        }
        self.prompts: list[str] = []
        self.prompts_by_arm: dict[str, list[str]] = {}

    def complete(self, prompt: str) -> CompletionOutcome:
        """One prompt's scripted answer (see the class docstring)."""

        self.prompts.append(prompt)
        arm = _arm_of(prompt)
        self.prompts_by_arm.setdefault(arm, []).append(prompt)
        if arm == _ARM_WRITER:
            return self._writer_answer(prompt)
        if arm == _ARM_PLANNER:
            return self._planner_answer(prompt)
        if arm == _ARM_DIRECTOR:
            return self._director_answer(prompt)
        return self._resolver_answer(prompt)

    def prompts_for(self, arm: str) -> tuple[str, ...]:
        """Every prompt one arm received, in call order (the gates'
        evidence for what a provider could see)."""

        return tuple(self.prompts_by_arm.get(arm, ()))

    # -- the four arms -------------------------------------------------------

    def _writer_answer(self, prompt: str) -> CompletionOutcome:
        place = _group(_PLACE_LINE, prompt, "place")
        seq = int(_group(_SEQ_LINE, prompt, "segment_seq"))
        body = self._prose.get((place, seq))
        if body is None:
            raise GoldScriptError(
                f"the gold script has no prose for {place!r} segment"
                f" {seq} — the scripted gap is answered loudly, never with"
                " an invented passage"
            )
        return CompletionOutcome(text=body, error=None)

    def _planner_answer(self, prompt: str) -> CompletionOutcome:
        scene_id = _group(_SCENE_LINE, prompt, "Scene")
        payload = self._elements.get(scene_id)
        if payload is None:
            raise GoldScriptError(
                f"the gold script has no element for scene {scene_id!r} —"
                " no SCENE replan is scripted for this scenario"
            )
        return _answer(payload)

    def _director_answer(self, prompt: str) -> CompletionOutcome:
        if _REPLAN_BLOCK in prompt:
            request = _group(_REPLAN_LINE, prompt, "replan_request_id")
            payload = self._replan_blueprints.get(request)
            if payload is None:
                raise GoldScriptError(
                    "the gold script has no replanned Blueprint for"
                    f" obligation {request!r}"
                )
            return _answer(payload)
        for marker, payload in self._blueprints:
            if marker is None or marker in prompt:
                return _answer(payload)
        raise GoldScriptError(
            "the gold script has no initial Blueprint for this prompt —"
            " no marker matched and no fallback is scripted"
        )

    def _resolver_answer(self, prompt: str) -> CompletionOutcome:
        raw = _group(_INTENT_LINE, prompt, "intent_text")
        try:
            intent = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as exc:
            raise GoldScriptError(
                "the prompt's intent_text line is not a readable"
                f" literal: {exc}"
            ) from None
        if not isinstance(intent, str):
            raise GoldScriptError(
                "the prompt's intent_text line is not a string literal"
            )
        payload = self._adjudications.get(intent)
        if payload is None:
            raise GoldScriptError(
                "the gold script has no ruling for the submitted intent"
                f" {intent!r} — the scripted gap is answered loudly, never"
                " with an invented verdict"
            )
        return _answer(payload)


def _arm_of(prompt: str) -> str:
    """The production face one prompt addresses, or the loud gap."""

    head = prompt[:200]
    for arm, opening in _ARM_OPENINGS:
        if opening in head:
            return arm
    raise GoldScriptError(
        "the prompt opens with none of the four production faces this"
        f" script knows: {prompt[:60]!r}"
    )


def gold_completion(*, leak_prose: str | None = None) -> GoldScriptedCompletion:
    """The Gold Scenario's scripted completion, ready for
    :func:`build_gold_pipeline`.

    ``leak_prose`` replaces scene 1's first passage with a deliberate
    violator (the leak gate's input — the guard must refuse it); the
    default script touches the secret's edge and never names it.
    """

    prose = dict(GOLD_PROSE)
    if leak_prose is not None:
        prose[(PLACE_GATE, 1)] = leak_prose
    return GoldScriptedCompletion(
        prose=prose,
        adjudications={GOLD_INTENT: GOLD_ADJUDICATION_PAYLOAD},
        blueprints=((CH1, CH2_BLUEPRINT), (None, CH1_BLUEPRINT)),
        replan_blueprints={REPLAN_REQUEST_ID: CH1_REPLAN_BLUEPRINT},
        elements={},
    )


# ---------------------------------------------------------------------------
# the world's seed and the drive's assembly
# ---------------------------------------------------------------------------


def _seed_persona_cards(conn: sqlite3.Connection, now: str) -> None:
    """Land the two persona cards the ``world_actor`` FK requires, then
    commit — the creation service opens its own ``BEGIN IMMEDIATE``, so
    this preamble must not leave a transaction open (the tests' own
    ``_insert_card`` posture). ``INSERT OR IGNORE``: a re-seed is a
    no-op, never a rewrite.

    V3-8e: ``lore_refs`` is written as the canonical empty array document
    (``json.dumps([])`` — the card store's ``_lore_document`` shape), not
    the bare empty string: the reading face's host open reads the whole
    card table (``CharacterCardPackages.__len__`` → ``list_all`` →
    ``json.loads(lore_refs)``), so a gold card must be a decodable row
    like any other — a process restart over a gold-seeded app.db opens
    clean (the fix is this fixture's own; the V3 store-level suites never
    open a host over these rows and are unaffected).
    """

    for ordinal, card in enumerate(GOLD_PERSONA_CARDS, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO character_card ("
            " character_id, persona_id, name, identity, personality,"
            " background, speech_style, \"values\", boundaries, opening,"
            " scenario, generation_policy, lore_refs, revision, status,"
            " is_builtin, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', 'auto', '[]', 1,"
            " 'active', 1, ?, ?)",
            (f"gold-card-{ordinal}", *card, now, now),
        )
    conn.commit()


def seed_gold_world(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    bible_store: SqliteBibleStore,
    cast_store: SqliteCastStore,
    now: str,
) -> Result[WorldCreationOutcome]:
    """Seed the fixed Gold Scenario world — the persona cards, then the
    atomic creation service (the world, its revision-1 ``CURRENT``
    Bible, Lia and Mother, and the reader's cousin). A same-shape replay
    answers the stored rows zero-write (the creation service's own
    ``world_id`` idempotency)."""

    _seed_persona_cards(conn, now)
    return create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=WORLD_ID,
        name=WORLD_NAME,
        bible_revision_id=BIBLE_REVISION_ID,
        bible=GOLD_BIBLE,
        actors=GOLD_ACTORS,
        player=GOLD_PLAYER,
        now=now,
    )


def build_gold_pipeline(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative_store: SqliteNarrativeStore,
    completion: GoldScriptedCompletion,
) -> Pipeline:
    """The Gold drive's pipeline: the four **real** LLM providers
    (:mod:`elc.world.llm_providers`) over one scripted completion, with
    the scenario's own ``action_duration_ticks``."""

    return Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative_store,
        writer_provider=LlmWriterProvider(completion),
        planner_provider=LlmPlannerProvider(completion),
        director_provider=LlmDirectorProvider(completion),
        resolver_provider=LlmResolverProvider(completion),
        action_duration_ticks=ACTION_DURATION_TICKS,
    )


def gold_beats_by_scene() -> dict[
    str, tuple[SegmentBeat | GateBeat, ...]
]:
    """The fixed beats of the three driven scenes — a fresh mapping per
    call (the beats are frozen values; the mapping is the caller's).

    Scene 1: two segments, **exactly one** User Gate carrying the
    user's free submission (no ``selected_option``), then the
    continuation segment (the pipeline names the committed ruling as
    its ``outcome_ref``; the closing flag rides this segment). Scenes 2
    and 3: the re-planned scenes' passages, the third reading what the
    second committed.
    """

    return {
        S1: (
            SegmentBeat(duration_ticks=S1_SEGMENT_1_TICKS),
            SegmentBeat(duration_ticks=S1_SEGMENT_2_TICKS),
            GateBeat(
                gate_seq=1,
                options=GATE_OPTIONS,
                submission_id=SUBMISSION_ID,
                intent_text=GOLD_INTENT,
            ),
            SegmentBeat(
                duration_ticks=S1_SEGMENT_3_TICKS, is_last_segment=True
            ),
        ),
        S2: (
            SegmentBeat(duration_ticks=S2_SEGMENT_1_TICKS),
            SegmentBeat(
                duration_ticks=S2_SEGMENT_2_TICKS, is_last_segment=True
            ),
        ),
        S3: (
            SegmentBeat(
                duration_ticks=S3_SEGMENT_1_TICKS, is_last_segment=True
            ),
        ),
    }
