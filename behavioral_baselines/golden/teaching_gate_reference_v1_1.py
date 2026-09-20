
from __future__ import annotations

GATE_CONTEXTS={"OPEN","AUTO_CONTINUE","USER_REQUESTED_CONTINUE"}
ACTIONS={"OPENING","HINT","RETRY","EXPLANATION","REVEAL","TERMINAL_FEEDBACK"}
USER_INTENTS={
    "OPEN","LEARNING_REQUEST","TARGETED_LEARNING_REQUEST",
    "JUST_CHAT","NON_LEARNING_TASK","ACTIVE_TEACHING_CONTINUATION"
}
DENY_PRECEDENCE=[
    "SAFETY_PRIVACY_BLOCK",
    "ACTION_CANCELLED",
    "ACTION_SUPERSEDED",
    "AUTHORIZATION_INVALID",
    "TARGET_INVALID",
    "CONTENT_INVALID",
    "TARGET_SUPPRESSED",
    "USER_INTENT_BLOCK",
    "AUTO_TEACH_DISABLED",
    "TEACHING_LOCK_CONFLICT",
    "TEACHING_LOCK_INVALID",
    "MOMENT_NOT_CONTINUABLE",
    "HARD_PROTECTED_FLOW",
    "AUTO_SESSION_BUDGET_EXHAUSTED",
    "HARD_COOLDOWN_ACTIVE",
    "HARD_ATTEMPT_LIMIT",
    "HARD_TEACHING_TURN_LIMIT",
]

class GateInputError(ValueError):
    pass

def validate(req):
    gc=req.get("gate_context")
    if gc not in GATE_CONTEXTS:
        raise GateInputError("invalid gate_context")
    act=req.get("proposed_action")
    if act not in ACTIONS:
        raise GateInputError("invalid proposed_action")
    ui=req.get("user_intent_scope")
    if ui not in USER_INTENTS:
        raise GateInputError("invalid user_intent_scope")
    ap=req.get("authorization_path")
    if ap not in {"AUTOMATIC","USER_INITIATED"}:
        raise GateInputError("invalid authorization_path")

    basis=req.get("authorization_basis")
    if gc=="OPEN":
        if basis!="DECISION_CYCLE":
            raise GateInputError("OPEN requires DECISION_CYCLE authorization basis")
        if act!="OPENING":
            raise GateInputError("OPEN requires OPENING")
        if req.get("planner_execution_status")!="SUCCEEDED":
            raise GateInputError("OPEN requires successful Planner execution")
        if req.get("planner_decision")!="SELECT":
            raise GateInputError("OPEN requires Planner SELECT")
        if not req.get("selected_candidate_id"):
            raise GateInputError("OPEN requires selected candidate")
        if ap=="AUTOMATIC":
            if req.get("user_initiated",False):
                raise GateInputError("automatic OPEN cannot be user_initiated")
        else:
            if not req.get("user_initiated",False):
                raise GateInputError("user-initiated OPEN requires user_initiated")
        if req.get("moment_id") is not None:
            raise GateInputError("OPEN must not have existing moment_id")
    else:
        if basis!="ACTIVE_MOMENT":
            raise GateInputError("continuation requires ACTIVE_MOMENT authorization basis")
        if act=="OPENING":
            raise GateInputError("continuation cannot OPENING")
        if not req.get("moment_id"):
            raise GateInputError("continuation requires moment_id")
        if gc=="USER_REQUESTED_CONTINUE" and not req.get("continuation_requested",False):
            raise GateInputError("USER_REQUESTED_CONTINUE requires continuation_requested")
        if gc=="AUTO_CONTINUE" and req.get("continuation_requested",False):
            raise GateInputError("AUTO_CONTINUE cannot claim continuation_requested")
    return True

def _critical_unknown(req):
    unknown=[]
    fields=[
        ("authorization_status", {"VALID","INVALIDATED","UNKNOWN"}),
        ("subject_status", {"ACTIVE","CANCELLED","SUPERSEDED","UNKNOWN"}),
        ("target_status", {"VALID","INVALID","DEPRECATED","MISSING","UNKNOWN"}),
        ("content_status", {"VALID","INVALID","UNKNOWN"}),
        ("safety_privacy_status", {"ALLOW","BLOCK","UNKNOWN"}),
        ("lock_state", {"NONE","OWNED_BY_THIS_MOMENT","OWNED_BY_OTHER","UNKNOWN"}),
    ]
    for name,allowed in fields:
        val=req.get(name,"UNKNOWN")
        if val not in allowed:
            raise GateInputError(f"invalid {name}: {val}")
        if val=="UNKNOWN":
            unknown.append(name)
    if req.get("gate_state_status","COMPLETE") not in {"COMPLETE","INCOMPLETE"}:
        raise GateInputError("invalid gate_state_status")
    if req.get("gate_state_status","COMPLETE")=="INCOMPLETE":
        unknown.append("gate_state")
    return sorted(set(unknown))

def decide(req):
    validate(req)

    unknown=_critical_unknown(req)
    if unknown:
        return {
            "execution_status":"DEGRADED",
            "degraded_reason":"CRITICAL_GATE_STATE_INCOMPLETE",
            "missing_or_unknown":unknown,
            "decision":None
        }

    reasons=[]
    gc=req["gate_context"]
    ap=req["authorization_path"]
    ui=req["user_intent_scope"]
    act=req["proposed_action"]

    if req["safety_privacy_status"]=="BLOCK":
        reasons.append("SAFETY_PRIVACY_BLOCK")
    if req["subject_status"]=="CANCELLED":
        reasons.append("ACTION_CANCELLED")
    if req["subject_status"]=="SUPERSEDED":
        reasons.append("ACTION_SUPERSEDED")
    if req["authorization_status"]=="INVALIDATED":
        reasons.append("AUTHORIZATION_INVALID")
    if req["target_status"] in {"INVALID","DEPRECATED","MISSING"}:
        reasons.append("TARGET_INVALID")
    if req["content_status"]=="INVALID":
        reasons.append("CONTENT_INVALID")
    if req.get("target_suppressed",False):
        reasons.append("TARGET_SUPPRESSED")

    if gc=="OPEN" and ap=="AUTOMATIC":
        if ui!="OPEN":
            reasons.append("USER_INTENT_BLOCK")
    elif gc=="OPEN" and ap=="USER_INITIATED":
        if ui not in {"LEARNING_REQUEST","TARGETED_LEARNING_REQUEST"}:
            reasons.append("USER_INTENT_BLOCK")
    elif gc in {"AUTO_CONTINUE","USER_REQUESTED_CONTINUE"}:
        if ui!="ACTIVE_TEACHING_CONTINUATION":
            reasons.append("USER_INTENT_BLOCK")

    if gc=="OPEN" and ap=="AUTOMATIC" and not req.get("automatic_teaching_enabled",True):
        reasons.append("AUTO_TEACH_DISABLED")
    if (
        gc=="AUTO_CONTINUE"
        and req.get("moment_consent_class","AUTO_OPENED")=="AUTO_OPENED"
        and not req.get("automatic_teaching_enabled",True)
    ):
        reasons.append("AUTO_TEACH_DISABLED")

    if gc=="OPEN":
        if req["lock_state"] in {"OWNED_BY_OTHER","OWNED_BY_THIS_MOMENT"}:
            reasons.append("TEACHING_LOCK_CONFLICT")
    else:
        if req["lock_state"]=="OWNED_BY_OTHER":
            reasons.append("TEACHING_LOCK_CONFLICT")
        elif req["lock_state"]!="OWNED_BY_THIS_MOMENT":
            reasons.append("TEACHING_LOCK_INVALID")
        if req.get("moment_state")!="DECIDING_NEXT_ACTION":
            reasons.append("MOMENT_NOT_CONTINUABLE")

    if ((gc=="OPEN" and ap=="AUTOMATIC") or gc=="AUTO_CONTINUE") and req.get("hard_protected_flow",False):
        reasons.append("HARD_PROTECTED_FLOW")

    if gc=="OPEN" and ap=="AUTOMATIC":
        if req.get("automatic_session_budget_exhausted",False):
            reasons.append("AUTO_SESSION_BUDGET_EXHAUSTED")
        if req.get("hard_cooldown_active",False):
            reasons.append("HARD_COOLDOWN_ACTIVE")

    terminalizing = (
        act in {"REVEAL","TERMINAL_FEEDBACK"}
        or bool(req.get("terminalizing_action",False))
    )
    retry_like = act in {"RETRY","HINT"}

    if gc in {"AUTO_CONTINUE","USER_REQUESTED_CONTINUE"}:
        if req.get("hard_attempt_limit_exhausted",False) and retry_like:
            reasons.append("HARD_ATTEMPT_LIMIT")
        if req.get("hard_teaching_turn_limit_exhausted",False) and not terminalizing:
            reasons.append("HARD_TEACHING_TURN_LIMIT")

    ordered=[r for r in DENY_PRECEDENCE if r in set(reasons)]
    if ordered:
        return {
            "execution_status":"SUCCEEDED",
            "decision":{
                "type":"DENY",
                "primary_reason":ordered[0],
                "reasons":ordered
            }
        }
    return {
        "execution_status":"SUCCEEDED",
        "decision":{"type":"ALLOW","reasons":[]}
    }
