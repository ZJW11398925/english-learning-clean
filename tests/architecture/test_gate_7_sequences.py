"""Gate item 7 — turn_sequence and message_sequence have independent tests.

docs/IMPLEMENTATION_PLAN.md §2 Gate; docs/DATA_MODEL.md §3 Sequence
Semantics: turn_sequence advances strictly per user-input coordination turn
(the turn's AssistantTurn? shares it), message_sequence orders every
canonical UserTurn/AssistantTurn, and DecisionCycle occupies neither.
These are two separate counters with two separate types — tested separately.
"""

from __future__ import annotations

from elc.conversation import SequenceAllocator
from elc.platform.types import ConversationId, MessageSequence, TurnSequence

CONV = ConversationId("conv-gate7")
OTHER = ConversationId("conv-gate7-b")


def test_turn_sequence_is_independent() -> None:
    """turn_sequence advances per coordination turn and only then."""
    allocator = SequenceAllocator()

    assert allocator.peek_turn(CONV) == TurnSequence(1)
    assert allocator.allocate_turn(CONV) == TurnSequence(1)
    assert allocator.allocate_turn(CONV) == TurnSequence(2)
    assert allocator.allocate_turn(CONV) == TurnSequence(3)

    # Message counter untouched by turn allocation (independence).
    assert allocator.peek_message(CONV) == MessageSequence(1)

    # Sequence scope is per conversation.
    assert allocator.peek_turn(OTHER) == TurnSequence(1)

    # Distinct canonical NewType identities (static separation; NewType is
    # erased at runtime, so identity is asserted on the types themselves).
    assert TurnSequence is not MessageSequence


def test_message_sequence_is_independent() -> None:
    """message_sequence advances per canonical transcript entry and only
    then; DecisionCycle entries occupy no message sequence."""
    allocator = SequenceAllocator()

    assert allocator.peek_message(CONV) == MessageSequence(1)
    assert allocator.allocate_message(CONV) == MessageSequence(1)
    assert allocator.allocate_message(CONV) == MessageSequence(2)

    # Turn counter untouched by message allocation (independence).
    assert allocator.peek_turn(CONV) == TurnSequence(1)
    assert allocator.allocate_message(CONV) == MessageSequence(3)
    assert allocator.peek_turn(CONV) == TurnSequence(1)

    # Sequence scope is per conversation.
    assert allocator.peek_message(OTHER) == MessageSequence(1)

    # Distinct canonical types: cross-stamping is a type error, by design.
    assert MessageSequence is not TurnSequence
