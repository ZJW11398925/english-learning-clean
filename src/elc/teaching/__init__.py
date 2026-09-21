"""Teaching domain — TeachingMoment lifecycle + the Teaching Gate.

docs/DOMAIN_MODEL.md §14/§15. Gate is the only "may execute now" authority.

Phase 3 P3-1A wiring: the Gate's USER_INITIATED OPEN profile lives in
elc.teaching.gate (frozen BF-03 v1.1 semantics, no behavioral_baselines
import), the durable CP2 / Gate store in elc.teaching.store, the target
resolution port in elc.teaching.targets, the command shape + canonical
payload in elc.teaching.request, and the authority face in
elc.teaching.controller.
"""

from elc.teaching.commands import TeachingCommands
from elc.teaching.controller import TeachingController
from elc.teaching.gate import (
    DENY_PRECEDENCE,
    GATE_POLICY_VERSION,
    MISSING_OR_UNKNOWN_FACT_KEYS,
    USER_INITIATED_OPEN_REASON_CODES,
    GateInputError,
    GateVerdict,
    UserInitiatedOpenFacts,
    decide_user_initiated_open,
)
from elc.teaching.queries import TeachingQueries
from elc.teaching.request import (
    TeachingRequest,
    intent_scope_for_request,
    parse_teaching_request_payload,
    teaching_request_payload,
)
from elc.teaching.store import (
    CP2OpenRequest,
    SqliteTeachingStore,
    StaleStoreEpochError,
    cp2_action_intent,
)
from elc.teaching.targets import (
    TeachingTargetProvider,
    TeachingTargetView,
)
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
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)

__all__ = [
    "AttemptEvaluationRecord",
    "AttemptRecord",
    "AuthorizationBasis",
    "CP2OpenRequest",
    "DENY_PRECEDENCE",
    "EphemeralTeachingDirective",
    "GATE_POLICY_VERSION",
    "GateDecisionContext",
    "GateDecisionRecord",
    "GateDecisionValue",
    "GateExecutionStatusRecord",
    "GateExecutionStatusValue",
    "GateInputError",
    "GateVerdict",
    "MISSING_OR_UNKNOWN_FACT_KEYS",
    "MomentSource",
    "MomentState",
    "PresentationPhase",
    "SqliteTeachingStore",
    "StaleStoreEpochError",
    "TeachingCommands",
    "TeachingController",
    "TeachingMomentRecord",
    "TeachingQueries",
    "TeachingRequest",
    "TeachingSupportLevel",
    "TeachingTargetProvider",
    "TeachingTargetRef",
    "TeachingTargetView",
    "USER_INITIATED_OPEN_REASON_CODES",
    "UserInitiatedOpenFacts",
    "cp2_action_intent",
    "decide_user_initiated_open",
    "intent_scope_for_request",
    "parse_teaching_request_payload",
    "teaching_request_payload",
]
