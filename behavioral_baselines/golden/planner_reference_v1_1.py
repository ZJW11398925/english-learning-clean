
from __future__ import annotations
import json

BENEFIT_KEYS = [
    "learning_need","uncertainty_reduction","curriculum_value","goal_relevance",
    "schedule_urgency","context_fit","personal_relevance","transfer_value",
    "coverage_debt","opportunity_expiry","communicative_impact"
]
COST_KEYS = [
    "interruption_cost","cognitive_load","overexposure","support_cost","user_resistance"
]
ALLOWED_SCOPE = {
    "OPEN","LEARNING_REQUEST","TARGETED_LEARNING_REQUEST","JUST_CHAT","NON_LEARNING_TASK"
}
MODE_INTENTS = {
    "RESOURCE_PRACTICE":{"ESTABLISH","DEVELOP","WITHDRAW_SUPPORT","EXPAND_REPERTOIRE"},
    "CAPABILITY_PRACTICE":{"ESTABLISH","DEVELOP","WITHDRAW_SUPPORT","EXPAND_REPERTOIRE"},
    "PROBE":{"PROBE"},
    "REVIEW":{"CONSOLIDATE"},
    "TRANSFER":{"TRANSFER"}
}
COVERAGE_SERVICE_STATES={"NONE","WATCH","DUE","CRITICAL"}

class PlannerInputError(ValueError):
    pass

def canonicalize_proposals(proposals):
    """
    Merge generator proposals before factor assembly.
    Final utility factors are deliberately not merged here; they must be
    recomputed once from authoritative views after canonicalization.
    """
    by={}
    irank={"PROACTIVE":1,"OPPORTUNISTIC":2,"REACTIVE":3}
    for p in proposals:
        key=p.get("canonical_key")
        if not key:
            raise PlannerInputError("proposal missing canonical_key")
        if key not in by:
            q=dict(p)
            q["origins"]=sorted(set(p.get("origins",[])))
            by[key]=q
            continue
        q=by[key]
        for f in ["target_mode","learning_intent","modality","focus_target","opportunity_binding_class"]:
            if p.get(f)!=q.get(f):
                raise PlannerInputError(f"{key}: conflicting proposal identity field {f}")
        q["origins"]=sorted(set(q.get("origins",[])) | set(p.get("origins",[])))
        q["user_initiated"]=bool(q.get("user_initiated",False) or p.get("user_initiated",False))
        q["request_aligned"]=bool(q.get("request_aligned",False) or p.get("request_aligned",False))
        q["request_priority"]=min(int(q.get("request_priority",0)), int(p.get("request_priority",0)))
        if irank[p.get("initiative","PROACTIVE")] > irank[q.get("initiative","PROACTIVE")]:
            q["initiative"]=p["initiative"]
    return [by[k] for k in sorted(by)]

def _planning_context(inp):
    return inp.get("planning_context") or {
        "feature_assembly_status":"COMPLETE",
        "snapshot_status":"VALID",
        "natural_break_available":False,
        "missing_authorities":[]
    }

def _precheck_context(inp,cfg):
    scope=inp.get("user_intent_scope")
    if scope not in ALLOWED_SCOPE:
        raise PlannerInputError(f"invalid user_intent_scope {scope}")
    policy=inp.get("policy_profile")
    if policy not in cfg["policy_profiles"]:
        raise PlannerInputError(f"invalid policy_profile {policy}")
    pc=_planning_context(inp)
    if pc.get("feature_assembly_status")!="COMPLETE":
        return {
            "execution_status":"DEGRADED",
            "degraded_reason":"FEATURE_ASSEMBLY_INCOMPLETE",
            "missing_authorities":pc.get("missing_authorities",[]),
            "evaluation":None,
            "decision":None
        }
    if pc.get("snapshot_status")!="VALID":
        return {
            "execution_status":"DEGRADED",
            "degraded_reason":"SNAPSHOT_INVALID",
            "snapshot_status":pc.get("snapshot_status"),
            "evaluation":None,
            "decision":None
        }
    return None

def _validate_factor_vector(c):
    for section, keys in [("benefit",BENEFIT_KEYS),("cost",COST_KEYS)]:
        if section not in c:
            raise PlannerInputError(f"{c['id']}: missing {section}")
        for k in keys:
            if k not in c[section]:
                raise PlannerInputError(f"{c['id']}: missing {section}.{k}")
            v=c[section][k]
            if not isinstance(v,(int,float)) or not 0.0 <= float(v) <= 1.0:
                raise PlannerInputError(f"{c['id']}: {section}.{k} outside [0,1]")

def validate_input(inp,cfg):
    scope=inp["user_intent_scope"]
    ids=set()
    canonical_keys=set()

    for c in inp.get("candidates",[]):
        cid=c.get("id")
        if not cid or cid in ids:
            raise PlannerInputError(f"duplicate/missing candidate id {cid}")
        ids.add(cid)

        ckey=c.get("canonical_key") or cid
        if ckey in canonical_keys:
            raise PlannerInputError(f"duplicate canonical_key {ckey}")
        canonical_keys.add(ckey)

        if c.get("initiative") not in {"REACTIVE","OPPORTUNISTIC","PROACTIVE"}:
            raise PlannerInputError(f"{cid}: invalid initiative")

        mode=c.get("target_mode")
        intent=c.get("learning_intent")
        if mode not in MODE_INTENTS or intent not in MODE_INTENTS[mode]:
            raise PlannerInputError(f"{cid}: invalid mode/intent pair {mode}/{intent}")

        if c.get("content_readiness","R3") not in cfg["readiness_rank"]:
            raise PlannerInputError(f"{cid}: invalid content readiness")

        ps=c.get("prerequisite_state","READY")
        if ps not in {"READY","READY_WITH_SCAFFOLD","UNKNOWN","BLOCKED"}:
            raise PlannerInputError(f"{cid}: invalid prerequisite_state")

        if c.get("coverage_service_state","NONE") not in COVERAGE_SERVICE_STATES:
            raise PlannerInputError(f"{cid}: invalid coverage_service_state")

        rp=c.get("request_priority",0)
        if not isinstance(rp,int) or rp<0:
            raise PlannerInputError(f"{cid}: invalid request_priority")

        if scope=="JUST_CHAT" and c.get("user_initiated",False):
            raise PlannerInputError(
                f"{cid}: user_initiated candidate contradicts JUST_CHAT scope"
            )

        _validate_factor_vector(c)

        scaffold = ps=="READY_WITH_SCAFFOLD" or (
            ps=="UNKNOWN" and c.get("prerequisite_scaffoldable",False)
        )
        if scaffold:
            floors=cfg.get("scaffold_min_cost",{})
            if c["cost"]["support_cost"] < floors.get("support_cost",0.0):
                raise PlannerInputError(f"{cid}: scaffold support_cost below floor")
            if c["cost"]["cognitive_load"] < floors.get("cognitive_load",0.0):
                raise PlannerInputError(f"{cid}: scaffold cognitive_load below floor")

def _eligible(c,scope,cfg):
    if c.get("expired"): return False,"EXPIRED"
    if c.get("deprecated"): return False,"DEPRECATED"
    if c.get("suppressed"): return False,"SUPPRESSED"
    if not c.get("modality_available",True): return False,"MODALITY_UNAVAILABLE"

    ps=c.get("prerequisite_state","READY")
    if ps=="BLOCKED":
        return False,"HARD_PREREQUISITE_BLOCKED"
    if ps=="UNKNOWN" and not (
        c["target_mode"]=="PROBE" or c.get("prerequisite_scaffoldable",False)
    ):
        return False,"PREREQUISITE_UNKNOWN_UNRESOLVED"

    if scope=="JUST_CHAT":
        return False,"JUST_CHAT"
    if scope=="TARGETED_LEARNING_REQUEST" and not c.get("request_aligned",False):
        return False,"OUTSIDE_TARGETED_SCOPE"
    if scope=="NON_LEARNING_TASK" and not (
        c.get("user_initiated",False)
        or c.get("task_aligned",False)
        or c.get("critical_repair",False)
    ):
        return False,"NON_LEARNING_TASK_SCOPE"

    r=cfg["readiness_rank"][c.get("content_readiness","R3")]
    if c["target_mode"]=="PROBE":
        min_r=2
    elif c.get("user_initiated",False):
        min_r=3
    elif "CURRENT_USER_ERROR" in c.get("origins",[]):
        min_r=4
    else:
        min_r=3

    # V1: runtime-generated content is a user-initiated escape hatch only.
    runtime_escape=bool(
        c.get("runtime_generated_ready",False)
        and c.get("user_initiated",False)
    )
    if r < min_r and not runtime_escape:
        return False,"CONTENT_NOT_READY"

    return True,None

def _score(c,policy,pc,cfg):
    benefit=sum(
        float(c["benefit"][k])*float(cfg["benefit_weights"][k])
        for k in BENEFIT_KEYS
    )
    cost=sum(
        float(c["cost"][k])*float(cfg["cost_weights"][k])
        for k in COST_KEYS
    )
    p=cfg["policy_profiles"][policy]
    utility=(
        float(p["initiative_multiplier"][c["initiative"]])*benefit
        - float(p["cost_multiplier"])*cost
    )

    service_bonus=0.0
    if (
        c.get("coverage_service_state","NONE")=="CRITICAL"
        and pc.get("natural_break_available",False)
        and policy in {"BALANCED","STUDY_FIRST"}
    ):
        service_bonus=float(
            cfg.get("coverage_service_bonus",{}).get(policy,0.0)
        )
        utility+=service_bonus

    return benefit,cost,utility,service_bonus

def _same_dominance_class(a,b):
    ca=a["candidate"]
    cb=b["candidate"]
    return (
        a["activation_path"]==b["activation_path"]
        and ca["initiative"]==cb["initiative"]
        and int(ca.get("request_priority",0))==int(cb.get("request_priority",0))
        and ca.get("coverage_service_state","NONE")
            == cb.get("coverage_service_state","NONE")
    )

def _dominates(a,b):
    if not _same_dominance_class(a,b):
        return False
    ca=a["candidate"]
    cb=b["candidate"]

    benefits_ge=all(
        float(ca["benefit"][k]) >= float(cb["benefit"][k])
        for k in BENEFIT_KEYS
    )
    costs_le=all(
        float(ca["cost"][k]) <= float(cb["cost"][k])
        for k in COST_KEYS
    )
    strict=(
        any(
            float(ca["benefit"][k]) > float(cb["benefit"][k])
            for k in BENEFIT_KEYS
        )
        or any(
            float(ca["cost"][k]) < float(cb["cost"][k])
            for k in COST_KEYS
        )
    )
    return benefits_ge and costs_le and strict

def _pareto_prune(rows):
    keep=[]
    dominated=[]
    for i,r in enumerate(rows):
        hit=None
        for j,s in enumerate(rows):
            if i!=j and _dominates(s,r):
                hit=s
                break
        if hit is None:
            keep.append(r)
        else:
            dominated.append({
                "candidate_id":r["candidate"]["id"],
                "by":hit["candidate"]["id"]
            })
    return keep,dominated

def _tie_key(r,cfg):
    c=r["candidate"]
    return (
        1 if c.get("request_aligned",False) else 0,
        1 if c.get("user_initiated",False) else 0,
        cfg["initiative_rank"][c["initiative"]],
        float(c["benefit"]["opportunity_expiry"]),
        -float(c["cost"]["interruption_cost"]),
        -float(c["cost"]["overexposure"]),
        -float(c["cost"]["cognitive_load"])
    )

def evaluate(inp,cfg):
    degraded=_precheck_context(inp,cfg)
    if degraded is not None:
        return degraded

    validate_input(inp,cfg)

    scope=inp["user_intent_scope"]
    policy=inp["policy_profile"]
    pc=_planning_context(inp)

    excluded=[]
    scored=[]

    for c in inp.get("candidates",[]):
        ok,reason=_eligible(c,scope,cfg)
        if not ok:
            excluded.append({"candidate_id":c["id"],"reason":reason})
            continue

        benefit,cost,utility,service_bonus=_score(c,policy,pc,cfg)

        user_path=bool(c.get("user_initiated",False)) and scope in {
            "LEARNING_REQUEST","TARGETED_LEARNING_REQUEST"
        }
        threshold=(
            None if user_path
            else float(cfg["policy_profiles"][policy]["automatic_activation_threshold"])
        )
        activated=True if user_path else utility >= threshold

        scored.append({
            "candidate":c,
            "benefit_score":round(benefit,6),
            "cost_score":round(cost,6),
            "coverage_service_bonus":round(service_bonus,6),
            "utility":round(utility,6),
            "activation_path":"USER_INITIATED" if user_path else "AUTOMATIC",
            "threshold":threshold,
            "activated":activated
        })

    if not scored:
        return {
            "execution_status":"SUCCEEDED",
            "evaluation":{
                "excluded":excluded,
                "scored":[],
                "activated":[],
                "dominated":[]
            },
            "decision":{
                "type":"NO_TARGET",
                "reason":"NO_ELIGIBLE_CANDIDATE"
            }
        }

    active=[r for r in scored if r["activated"]]

    if not active:
        top=max(scored,key=lambda r:(r["utility"],r["candidate"]["id"]))
        return {
            "execution_status":"SUCCEEDED",
            "evaluation":{
                "excluded":excluded,
                "scored":scored,
                "activated":[],
                "dominated":[]
            },
            "decision":{
                "type":"NO_TARGET",
                "reason":"BELOW_ACTIVATION_THRESHOLD",
                "top_candidate_id":top["candidate"]["id"]
            }
        }

    # Explicit user intent is a scope class, not just another utility bonus.
    user_active=[
        r for r in active
        if r["activation_path"]=="USER_INITIATED"
    ]
    if user_active:
        min_priority=min(
            int(r["candidate"].get("request_priority",0))
            for r in user_active
        )
        active=[
            r for r in user_active
            if int(r["candidate"].get("request_priority",0))==min_priority
        ]

    active,dominated=_pareto_prune(active)

    max_utility=max(r["utility"] for r in active)
    eps=float(cfg["tie_epsilon"])
    tie=[
        r for r in active
        if max_utility-r["utility"] <= eps
    ]

    best_key=max(_tie_key(r,cfg) for r in tie)
    finalists=[
        r for r in tie
        if _tie_key(r,cfg)==best_key
    ]
    selected=sorted(
        finalists,
        key=lambda r:r["candidate"]["id"]
    )[0]

    return {
        "execution_status":"SUCCEEDED",
        "evaluation":{
            "excluded":excluded,
            "scored":scored,
            "activated":[r["candidate"]["id"] for r in active],
            "dominated":dominated,
            "tie_set":[r["candidate"]["id"] for r in tie]
        },
        "decision":{
            "type":"SELECT",
            "candidate_id":selected["candidate"]["id"],
            "utility":selected["utility"],
            "activation_path":selected["activation_path"]
        }
    }

if __name__=="__main__":
    import argparse, pathlib
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile",required=True)
    ap.add_argument("--input",required=True)
    args=ap.parse_args()
    cfg=json.loads(pathlib.Path(args.profile).read_text())
    inp=json.loads(pathlib.Path(args.input).read_text())
    print(json.dumps(evaluate(inp,cfg),indent=2))
