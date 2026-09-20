"""Teaching domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import ConversationId, MomentId, Result
from elc.teaching.types import TeachingMomentRecord


@runtime_checkable
class TeachingQueries(Protocol):
    """Moment lifecycle reads."""

    def get_active_moment(
        self, conversation_id: ConversationId
    ) -> Result[TeachingMomentRecord | None]:
        """Backed by the durable active_teaching_lock (one per conversation)."""
        ...

    def get_moment(self, moment_id: MomentId) -> Result[TeachingMomentRecord | None]:
        ...
