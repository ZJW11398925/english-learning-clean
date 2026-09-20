"""Teaching domain — TeachingMoment lifecycle + the Teaching Gate.

docs/DOMAIN_MODEL.md §14/§15. Gate is the only "may execute now" authority.
"""

from elc.teaching.commands import TeachingCommands
from elc.teaching.controller import TeachingController
from elc.teaching.queries import TeachingQueries
from elc.teaching.types import (
    AttemptEvaluationRecord,
    AttemptRecord,
    AuthorizationBasis,
    EphemeralTeachingDirective,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentState,
    TeachingMomentRecord,
)

__all__ = [
    "AttemptEvaluationRecord",
    "AttemptRecord",
    "AuthorizationBasis",
    "EphemeralTeachingDirective",
    "GateDecisionContext",
    "GateDecisionRecord",
    "GateDecisionValue",
    "GateExecutionStatusRecord",
    "GateExecutionStatusValue",
    "MomentState",
    "TeachingCommands",
    "TeachingController",
    "TeachingMomentRecord",
    "TeachingQueries",
]
