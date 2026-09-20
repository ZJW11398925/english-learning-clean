
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import math, json

ABILITY_DIMS = [
    "recognition", "guided_production", "independent_production",
    "spontaneous_production", "accuracy", "pragmatic_control"
]

PRODUCTION_TYPES = {
    "IMITATIVE_PRODUCTION", "GUIDED_PRODUCTION", "INDEPENDENT_PRODUCTION",
    "SPONTANEOUS_PRODUCTION", "SELF_REPAIR", "FAILED_ATTEMPT", "MISUSE"
}

DIRECT_DIMENSION = {
    "RECOGNITION": "recognition",
    "GUIDED_PRODUCTION": "guided_production",
    "INDEPENDENT_PRODUCTION": "independent_production",
    "SPONTANEOUS_PRODUCTION": "spontaneous_production",
    "SELF_REPAIR": "independent_production",
}

def validate_claims(claims):
    """Validate canonical EstimatorClaimView invariants before state estimation."""
    errors=[]
    group_primary=defaultdict(list)
    for i,c in enumerate(claims):
        pt=c.get("performance_type")
        support=c.get("support_level","NONE")
        exposure=c.get("exposure_level","NONE")
        opp=c.get("opportunity_type")
        key=(c.get("group_id"),c.get("target_type"),c.get("target_id"),c.get("modality"))
        if pt in PRODUCTION_TYPES or pt=="RECOGNITION":
            group_primary[key].append((i,pt))

        if pt in {"INDEPENDENT_PRODUCTION","SPONTANEOUS_PRODUCTION"}:
            if support not in {"NONE","CONTEXT_ONLY"}:
                errors.append({"index":i,"code":"INDEPENDENT_WITH_ASSISTANCE","performance_type":pt,"support_level":support})
            if exposure != "NONE":
                errors.append({"index":i,"code":"INDEPENDENT_WITH_ANSWER_EXPOSURE","performance_type":pt,"exposure_level":exposure})
        if pt=="SPONTANEOUS_PRODUCTION" and opp!="NATURAL":
            errors.append({"index":i,"code":"SPONTANEOUS_REQUIRES_NATURAL_OPPORTUNITY","opportunity_type":opp})

    for key,vals in group_primary.items():
        if len(vals)>1:
            # One user behavior may generate multiple claims, but not multiple
            # primary performance claims for the same target × modality.
            errors.append({"code":"MULTIPLE_PRIMARY_PERFORMANCE_CLAIMS_SAME_GROUP_TARGET",
                           "group_target":key,"claims":vals})
    return errors

def _dt(x):
    if isinstance(x, datetime):
        return x
    return datetime.fromisoformat(x.replace("Z","+00:00"))

def _assist_factor(c, cfg):
    sf = cfg["support_factor"].get(c.get("support_level","NONE"), 1.0)
    ef = cfg["exposure_factor"].get(c.get("exposure_level","NONE"), 1.0)
    return min(sf, ef)

def _error_mult(c, cfg):
    return cfg["error_attribution_multiplier"].get(c.get("error_attribution","UNKNOWN"), 0.60)

def _cluster_key(c):
    # Teaching attempts in one moment are intentionally correlated.
    if c.get("teaching_moment_id"):
        return "teach:" + str(c["teaching_moment_id"])
    day = _dt(c["timestamp"]).date().isoformat()
    context = c.get("context_key") or (
        "novel:"+str(c["group_id"]) if "CROSS_CONTEXT" in c.get("qualifiers",[]) or
        "HIGH_CONTEXT_NOVELTY" in c.get("qualifiers",[]) else "context:unknown"
    )
    realization = c.get("realization_key") or (
        "novel:"+str(c["group_id"]) if "NOVEL_REALIZATION" in c.get("qualifiers",[]) else "realization:unknown"
    )
    persona = c.get("persona_id") or "persona:none"
    return f"natural:{c.get('conversation_id','conv:none')}:{day}:{context}:{realization}:{persona}"

def _negative_dimension_map(c):
    pt = c["performance_type"]
    opp = c.get("opportunity_type")
    support = c.get("support_level","NONE")
    low_support = support in {"NONE","CONTEXT_ONLY"}

    if pt == "RECOGNITION":
        return {"recognition": 1.0}
    if pt == "FAILED_ATTEMPT":
        if opp == "NATURAL" and low_support:
            # Directly observed failure at spontaneous production also diagnoses
            # independent retrieval in the same attempted behavior; it does NOT
            # propagate to guided/recognition.
            return {"spontaneous_production": 1.0, "independent_production": 0.75}
        if low_support:
            return {"independent_production": 1.0}
        return {"guided_production": 1.0}
    if pt == "MISUSE":
        out = {"accuracy": 1.0}
        if opp == "NATURAL" and low_support:
            out["spontaneous_production"] = 0.50
            out["independent_production"] = 0.50
        elif low_support:
            out["independent_production"] = 0.50
        else:
            out["guided_production"] = 0.50
        return out
    return {}

def _claim_contrib(c, cfg):
    pos = defaultdict(float)
    neg = defaultdict(float)
    conf = float(c.get("evaluator_confidence",0.0))
    if conf < cfg["claim_min_confidence"] or c.get("outcome") == "ABSTAIN":
        return pos, neg

    outcome = c.get("outcome","SUCCESS")
    of = cfg["outcome_factor"].get(outcome,1.0)
    pt = c["performance_type"]
    polarity = c.get("polarity","POSITIVE")

    if polarity == "POSITIVE" and pt in cfg["positive_mapping"]:
        assist = _assist_factor(c,cfg)
        for d,w in cfg["positive_mapping"][pt].items():
            pos[d] += w * of * conf * assist

        # PARTIAL is not "small pure success". Repeated partial performance must
        # converge toward a partial-control estimate, not toward 1.0.
        if outcome == "PARTIAL" and pt in DIRECT_DIMENSION:
            direct = DIRECT_DIMENSION[pt]
            residual = float(cfg.get("partial_direct_negative_fraction",0.50))
            neg[direct] += cfg["positive_mapping"][pt].get(direct,1.0) * residual * conf * assist

        if pt == "SELF_REPAIR" and c.get("spontaneity") == "SPONTANEOUS" and c.get("exposure_level","NONE") != "FULL":
            pos["spontaneous_production"] += 0.50 * of * conf * assist
            if outcome == "PARTIAL":
                neg["spontaneous_production"] += 0.50 * float(cfg.get("partial_direct_negative_fraction",0.50)) * conf * assist

        qstrength = cfg["quality_strength"].get(pt,0.0) * of * conf * assist
        if c.get("accuracy") is not None and qstrength > 0:
            q = min(1.0,max(0.0,float(c["accuracy"])))
            pos["accuracy"] += qstrength*q
            neg["accuracy"] += qstrength*(1-q)
        if c.get("pragmatic_fit") is not None and qstrength > 0:
            q = min(1.0,max(0.0,float(c["pragmatic_fit"])))
            pos["pragmatic_control"] += qstrength*q
            neg["pragmatic_control"] += qstrength*(1-q)

    if polarity == "NEGATIVE":
        em = _error_mult(c,cfg)
        for d,w in _negative_dimension_map(c).items():
            neg[d] += w * of * conf * em

    return pos, neg

def _aggregate_group(claims, cfg):
    """Same EvidenceGroup: per dimension/polarity keep strongest contribution."""
    gp, gn = defaultdict(float), defaultdict(float)
    for c in claims:
        p,n = _claim_contrib(c,cfg)
        for d,v in p.items(): gp[d] = max(gp[d],v)
        for d,v in n.items(): gn[d] = max(gn[d],v)
    return gp, gn

def _aggregate_cluster(group_rows, cfg):
    """
    Same cluster: preserve both positive and negative polarity, but diminish
    repeated same-polarity contributions. This keeps failure→guided success
    visible without counting three repetitions as three independent proofs.
    """
    weights = cfg["same_cluster_repeat_weights"]
    outp, outn = defaultdict(float), defaultdict(float)

    for dim in ABILITY_DIMS:
        for side, out in [("p",outp),("n",outn)]:
            vals=[]
            for row in sorted(group_rows,key=lambda r:r["timestamp"]):
                v = row[side].get(dim,0.0)
                if v>0: vals.append(v)
            if not vals: continue
            total=0.0
            for i,v in enumerate(vals):
                w=weights[i] if i<len(weights) else weights[-1]
                total += w*v
            total=min(total, cfg["same_cluster_mass_cap_multiple"]*max(vals))
            out[dim]=total
    return outp,outn

def _confidence(total_mass, meta, target_type, dim, cfg):
    if total_mass <= 0:
        return 0.0
    mass_conf = 1.0 - math.exp(-total_mass/cfg["confidence_tau"])
    extra = (
        0.35*max(0,meta["days"]-1) +
        0.25*max(0,meta["contexts"]-1) +
        0.15*max(0,meta["personas"]-1) +
        0.25*max(0,meta["realizations"]-1)
    )
    div = 1.0 - math.exp(-extra)
    conf = mass_conf*(0.80+0.20*div)

    if target_type == "CAPABILITY":
        if dim in {"independent_production","spontaneous_production","pragmatic_control"} and meta["realizations"] < 2:
            conf=min(conf,cfg["capability_confidence_caps"]["independent_or_spontaneous_if_realization_diversity_lt_2"])
    return min(1.0,max(0.0,conf))

def _band_conf(x,cfg):
    if x <= cfg["confidence_bands"]["LOW_MAX"]: return "LOW"
    if x <= cfg["confidence_bands"]["MEDIUM_MAX"]: return "MEDIUM"
    return "HIGH"

def _strong_retrieval(c,cfg):
    if c.get("polarity")!="POSITIVE" or c.get("outcome")!="SUCCESS": return False
    pt=c.get("performance_type")
    if pt not in {"INDEPENDENT_PRODUCTION","SPONTANEOUS_PRODUCTION","SELF_REPAIR"}: return False
    if pt=="SELF_REPAIR" and c.get("spontaneity") not in {"INDEPENDENT","SPONTANEOUS"}:
        return False
    if c.get("evaluator_confidence",0)<0.70: return False
    if _assist_factor(c,cfg)<0.70: return False
    return True

def estimate(claims, target_type, target_id, modality, as_of, cfg, strict=True):
    contract_errors=validate_claims(claims)
    if contract_errors and strict:
        raise ValueError("EstimatorClaimView contract violation: "+json.dumps(contract_errors,ensure_ascii=False,default=str))
    active=[
        c for c in claims
        if c.get("status","ACTIVE")=="ACTIVE"
        and c["target_type"]==target_type
        and c["target_id"]==target_id
        and c["modality"]==modality
    ]

    # EvidenceGroup aggregation
    by_group=defaultdict(list)
    for c in active: by_group[c["group_id"]].append(c)

    group_rows=[]
    for gid, cs in by_group.items():
        p,n=_aggregate_group(cs,cfg)
        exemplar=sorted(cs,key=lambda x:x["timestamp"])[0]
        group_rows.append({
            "group_id":gid,
            "timestamp":_dt(exemplar["timestamp"]),
            "cluster":_cluster_key(exemplar),
            "p":p,"n":n,
            "claims":cs
        })

    # Cluster aggregation
    by_cluster=defaultdict(list)
    for r in group_rows: by_cluster[r["cluster"]].append(r)

    totalp,totaln=defaultdict(float),defaultdict(float)
    dim_meta={d: {"days":set(),"contexts":set(),"personas":set(),"realizations":set(),"clusters":set()} for d in ABILITY_DIMS}

    for ck, rows in by_cluster.items():
        cp,cn=_aggregate_cluster(rows,cfg)
        for d,v in cp.items(): totalp[d]+=v
        for d,v in cn.items(): totaln[d]+=v
        for d in ABILITY_DIMS:
            if cp.get(d,0)>0 or cn.get(d,0)>0:
                m=dim_meta[d]
                m["clusters"].add(ck)
                for r in rows:
                    for c in r["claims"]:
                        m["days"].add(_dt(c["timestamp"]).date().isoformat())
                        m["contexts"].add(c.get("context_key") or "unknown")
                        if c.get("persona_id"): m["personas"].add(c["persona_id"])
                        m["realizations"].add(c.get("realization_key") or "unknown")

    dimensions={}
    for d in ABILITY_DIMS:
        P,N=totalp[d],totaln[d]
        M=P+N
        meta={
            "days":len(dim_meta[d]["days"]),
            "contexts":len(dim_meta[d]["contexts"]),
            "personas":len(dim_meta[d]["personas"]),
            "realizations":len(dim_meta[d]["realizations"]),
            "clusters":len(dim_meta[d]["clusters"]),
        }
        if M < cfg["dimension_min_effective_mass"]:
            est=None
            conf=0.0 if M==0 else _confidence(M,meta,target_type,d,cfg)
        else:
            est=P/M if M>0 else None
            conf=_confidence(M,meta,target_type,d,cfg)
        dimensions[d]={
            "estimate": None if est is None else round(est,4),
            "confidence": round(conf,4),
            "positive_mass": round(P,4),
            "negative_mass": round(N,4),
            "effective_mass": round(M,4),
            "independent_clusters": meta["clusters"]
        }

    # Transfer: aggregate by independent strong-retrieval clusters. Repeated
    # uses inside the same new condition cannot multiply transfer confidence.
    strong=[c for c in active if _strong_retrieval(c,cfg)]
    strong_by_cluster=defaultdict(list)
    for c in strong:
        strong_by_cluster[_cluster_key(c)].append(c)

    strong_cluster_rows=[]
    for ck, cs in strong_by_cluster.items():
        rep=max(cs,key=lambda x:(x.get("evaluator_confidence",0)*_assist_factor(x,cfg), _dt(x["timestamp"])))
        strong_cluster_rows.append({
            "cluster":ck,
            "timestamp":_dt(rep["timestamp"]),
            "context":rep.get("context_key") or "unknown",
            "persona":rep.get("persona_id") or "none",
            "realization":rep.get("realization_key") or "unknown",
            "mass":rep.get("evaluator_confidence",1.0)*_assist_factor(rep,cfg),
            "claim":rep
        })
    strong_cluster_rows.sort(key=lambda x:x["timestamp"])

    transfer_pos=0.0
    transfer_neg=0.0
    if strong_cluster_rows:
        base=strong_cluster_rows[0]
        for r in strong_cluster_rows[1:]:
            c=r["claim"]
            diverse = (
                r["context"] != base["context"] or
                r["persona"] != base["persona"] or
                r["realization"] != base["realization"] or
                any(q in c.get("qualifiers",[]) for q in ["CROSS_CONTEXT","CROSS_PERSONA","NOVEL_REALIZATION","CROSS_MODALITY"])
            )
            if diverse:
                transfer_pos += r["mass"]

    neg_transfer_by_cluster=defaultdict(list)
    for c in active:
        if c.get("polarity")=="NEGATIVE" and c.get("performance_type") in {"FAILED_ATTEMPT","MISUSE"}:
            if any(q in c.get("qualifiers",[]) for q in ["CROSS_CONTEXT","CROSS_PERSONA","NOVEL_REALIZATION","CROSS_MODALITY"]):
                neg_transfer_by_cluster[_cluster_key(c)].append(
                    c.get("evaluator_confidence",1.0)*_error_mult(c,cfg)
                )
    for vals in neg_transfer_by_cluster.values():
        transfer_neg += max(vals)

    strong_clusters=set(strong_by_cluster)
    strong_contexts={r["context"] for r in strong_cluster_rows}
    strong_personas={r["persona"] for r in strong_cluster_rows}
    strong_realizations={r["realization"] for r in strong_cluster_rows}
    strong_days={r["timestamp"].date().isoformat() for r in strong_cluster_rows}
    transfer_mass=transfer_pos+transfer_neg

    transfer_gate = len(strong_clusters)>=2 and (
        len(strong_contexts)>=2 or len(strong_personas)>=2 or len(strong_realizations)>=2
    )
    if target_type=="CAPABILITY":
        transfer_gate = transfer_gate and len(strong_realizations)>=2

    if transfer_gate and transfer_mass>=cfg["dimension_min_effective_mass"]:
        transfer_est=transfer_pos/transfer_mass if transfer_mass else None
        tmeta={"days":len(strong_days),
               "contexts":len(strong_contexts),"personas":len(strong_personas),
               "realizations":len(strong_realizations),"clusters":len(strong_clusters)}
        transfer_conf=_confidence(transfer_mass,tmeta,target_type,"transfer",cfg)
        if target_type=="CAPABILITY" and len(strong_contexts)<2:
            transfer_conf=min(transfer_conf,cfg["capability_confidence_caps"]["transfer_if_context_diversity_lt_2"])
    else:
        transfer_est=None
        transfer_conf=0.0
    dimensions["transfer"]={
        "estimate": None if transfer_est is None else round(transfer_est,4),
        "confidence": round(transfer_conf,4),
        "positive_mass": round(transfer_pos,4),
        "negative_mass": round(transfer_neg,4),
        "effective_mass": round(transfer_mass,4),
        "independent_clusters":len(strong_clusters)
    }

    # Support dependency from production success/failure distribution.
    # It is NOT inferred from unsupported failures alone. A high dependency
    # estimate requires the diagnostic pattern: supported success + low-support
    # failure. Low dependency can be established by repeated low-support success.
    dep_obs=[]
    for gid, cs in by_group.items():
        candidates=[c for c in cs if c.get("performance_type") in PRODUCTION_TYPES and c.get("evaluator_confidence",0)>=cfg["claim_min_confidence"]]
        if not candidates: continue
        # strongest diagnostic claim for this target/group
        c=max(candidates,key=lambda x:x.get("evaluator_confidence",0))
        conf=c.get("evaluator_confidence",0.0)
        if c.get("polarity")=="POSITIVE" and c.get("outcome") in {"SUCCESS","PARTIAL"}:
            burden=max(
                cfg["support_burden"].get(c.get("support_level","NONE"),0.0),
                {"NONE":0.0,"PARTIAL":0.75,"FULL":0.95}.get(c.get("exposure_level","NONE"),0.0)
            )
            mass=conf*cfg["outcome_factor"].get(c.get("outcome"),1.0)
            kind="low_success" if burden<=0.10 else "assisted_success"
        elif c.get("polarity")=="NEGATIVE" and c.get("outcome") in {"FAILURE","PARTIAL"}:
            burden=1.0
            mass=conf*_error_mult(c,cfg)*cfg["outcome_factor"].get(c.get("outcome"),1.0)
            kind="low_failure" if c.get("support_level","NONE") in {"NONE","CONTEXT_ONLY"} else "supported_failure"
        else:
            continue
        dep_obs.append({"cluster":_cluster_key(c),"timestamp":_dt(c["timestamp"]),"burden":burden,"mass":mass,"kind":kind})

    # Correlated repeats diminish here too.
    dep_num=0.0; dep_den=0.0
    kind_mass=defaultdict(float)
    by_dep_cluster=defaultdict(list)
    for o in dep_obs: by_dep_cluster[o["cluster"]].append(o)
    weights=cfg["same_cluster_repeat_weights"]
    for ck, obs in by_dep_cluster.items():
        obs=sorted(obs,key=lambda x:x["timestamp"])
        for i,o in enumerate(obs):
            rw=weights[i] if i<len(weights) else weights[-1]
            em=o["mass"]*rw
            dep_den+=em; dep_num+=o["burden"]*em; kind_mass[o["kind"]]+=em

    dependency_identifiable = (
        kind_mass["low_success"] >= cfg["support_dependency_min_mass"]
        or (kind_mass["assisted_success"] >= 0.50 and kind_mass["low_failure"] >= 0.50)
    )
    if dependency_identifiable and dep_den>=cfg["support_dependency_min_mass"]:
        dep_est=dep_num/dep_den
        meta={"days":len({_dt(c["timestamp"]).date().isoformat() for c in active}),
              "contexts":len({c.get("context_key") or "unknown" for c in active}),
              "personas":len({c.get("persona_id") or "none" for c in active}),
              "realizations":len({c.get("realization_key") or "unknown" for c in active}),
              "clusters":len(by_dep_cluster)}
        dep_conf=_confidence(dep_den,meta,target_type,"support_dependency",cfg)
    else:
        dep_est=None; dep_conf=0.0
    dimensions["support_dependency"]={
        "estimate":None if dep_est is None else round(dep_est,4),
        "confidence":round(dep_conf,4),
        "effective_mass":round(dep_den,4),
        "diagnostic_mass":{k:round(v,4) for k,v in kind_mass.items()}
    }

    # Coverage
    coverage={
        "evidence_groups":len(by_group),
        "independent_clusters":len(by_cluster),
        "days":len({_dt(c["timestamp"]).date().isoformat() for c in active}),
        "contexts":len({c.get("context_key") or "unknown" for c in active}),
        "personas":len({c.get("persona_id") or "none" for c in active}),
        "realizations":len({c.get("realization_key") or "unknown" for c in active}),
        "modalities":len({c["modality"] for c in active})
    }

    # Freshness
    if strong:
        last=max(_dt(c["timestamp"]) for c in strong)
        days_since=max(0,(_dt(as_of)-last).total_seconds()/86400)
        if days_since<=cfg["freshness_days"]["FRESH_MAX"]: freshness="FRESH"
        elif days_since<=cfg["freshness_days"]["AGING_MAX"]: freshness="AGING"
        else: freshness="STALE"
    else:
        last=None; days_since=None; freshness="UNKNOWN"

    # Projection bands
    sp=dimensions["spontaneous_production"]["estimate"]
    ind=dimensions["independent_production"]["estimate"]
    gui=dimensions["guided_production"]["estimate"]

    pt=cfg["planning_thresholds"]
    def _confirmed_gap_dim(name):
        d=dimensions[name]
        return d["estimate"] is not None and d["estimate"]<=pt["CONFIRMED_GAP_estimate_max"] and d["confidence"]>=pt["CONFIRMED_GAP_confidence_min"]

    # Stronger observed tiers are blocked when a lower prerequisite tier has a
    # high-confidence gap. This prevents "SPONTANEOUS + CONFIRMED_GAP" from
    # becoming the headline ability band after one anomalous strong event.
    if sp is not None and sp>=0.75 and not _confirmed_gap_dim("independent_production"):
        ability_band="SPONTANEOUS"
    elif ind is not None and ind>=0.75 and not _confirmed_gap_dim("guided_production"):
        ability_band="INDEPENDENT"
    elif gui is not None and gui>=0.75:
        ability_band="GUIDED"
    elif any(dimensions[d]["estimate"] is not None for d in ["guided_production","independent_production","spontaneous_production"]):
        ability_band="EARLY"
    else: ability_band="UNKNOWN"

    focus_conf=0.0
    if ability_band=="SPONTANEOUS": focus_conf=dimensions["spontaneous_production"]["confidence"]
    elif ability_band=="INDEPENDENT": focus_conf=dimensions["independent_production"]["confidence"]
    elif ability_band=="GUIDED": focus_conf=dimensions["guided_production"]["confidence"]
    else:
        focus_conf=max(dimensions[d]["confidence"] for d in ["recognition","guided_production","independent_production","spontaneous_production"])
    confidence_band=_band_conf(focus_conf,cfg)

    if dimensions["transfer"]["estimate"] is None:
        transfer_band="NARROW" if (ind is not None and ind>=0.75) or (sp is not None and sp>=0.75) else "UNTESTED"
    else:
        if len(strong_contexts)>=3 and len(strong_clusters)>=3:
            transfer_band="MULTI_CONTEXT"
        else:
            transfer_band="CROSS_CONTEXT"

    dep=dimensions["support_dependency"]["estimate"]
    if dep is None: support_band="UNKNOWN"
    elif dep>=0.75: support_band="HIGH_SUPPORT"
    elif dep>=0.50: support_band="PARTIAL_SUPPORT"
    elif dep>=0.20: support_band="LOW_SUPPORT"
    else: support_band="INDEPENDENT"

    if not strong:
        stability_band="UNTESTED"
    elif len(strong_clusters)<2:
        stability_band="FRAGILE"
    elif freshness=="STALE":
        stability_band="STALE"
    elif len(strong_clusters)>=4 and len(strong_days)>=2:
        stability_band="STABLE"
    else:
        stability_band=freshness

    flags=[]
    # Confirmed gap uses strongest production dimension that has known evidence.
    prod_known=[dimensions[d] for d in ["spontaneous_production","independent_production","guided_production"] if dimensions[d]["estimate"] is not None]
    if prod_known:
        best=max(prod_known,key=lambda x:x["confidence"])
        if best["estimate"]<=pt["CONFIRMED_GAP_estimate_max"] and best["confidence"]>=pt["CONFIRMED_GAP_confidence_min"]:
            flags.append("CONFIRMED_GAP")
    if dep is not None and dep>=pt["SUPPORT_DEPENDENT_estimate_min"] and dimensions["support_dependency"]["confidence"]>=pt["SUPPORT_DEPENDENT_confidence_min"]:
        flags.append("SUPPORT_DEPENDENT")
    if ind is not None and ind>=pt["STRONG_CONTROL_estimate_min"] and dimensions["independent_production"]["confidence"]>=pt["STRONG_CONTROL_confidence_min"]:
        flags.append("STRONG_INDEPENDENT_CONTROL")
    if sp is not None and sp>=pt["STRONG_CONTROL_estimate_min"] and dimensions["spontaneous_production"]["confidence"]>=pt["STRONG_CONTROL_confidence_min"]:
        flags.append("STRONG_SPONTANEOUS_CONTROL")

    if ability_band in {"INDEPENDENT","SPONTANEOUS"} and (
        len(strong_contexts)<2 or len(strong_realizations)<2
    ):
        flags.append("NARROW_EVIDENCE")

    # Within-dimension conflict.
    for d in ABILITY_DIMS:
        P=dimensions[d]["positive_mass"]; N=dimensions[d]["negative_mass"]
        M=P+N
        if P>=pt["CONFLICT_mass_min_each"] and N>=pt["CONFLICT_mass_min_each"]:
            ratio=P/M if M else 0.5
            if pt["CONFLICT_ratio_low"]<=ratio<=pt["CONFLICT_ratio_high"]:
                flags.append("CONFLICTING_EVIDENCE"); break

    # Cross-dimensional hierarchy conflict: strong evidence at a higher tier
    # coexists with a high-confidence gap at its lower prerequisite tier.
    if (sp is not None and sp>=0.75 and _confirmed_gap_dim("independent_production")) or (
        ind is not None and ind>=0.75 and _confirmed_gap_dim("guided_production")
    ):
        flags.append("CONFLICTING_EVIDENCE")

    if all(dimensions[d]["estimate"] is None for d in ["recognition","guided_production","independent_production","spontaneous_production"]):
        flags.append("INSUFFICIENT_EVIDENCE")
    return {
        "target_type":target_type,
        "target_id":target_id,
        "modality":modality,
        "dimensions":dimensions,
        "coverage":coverage,
        "freshness":{
            "last_strong_retrieval_at":None if last is None else last.isoformat(),
            "days_since_strong_retrieval":None if days_since is None else round(days_since,2),
            "freshness_band":freshness
        },
        "projection":{
            "ability_band":ability_band,
            "confidence_band":confidence_band,
            "transfer_band":transfer_band,
            "support_band":support_band,
            "stability_band":stability_band,
            "learning_flags":sorted(set(flags))
        }
    }

if __name__ == "__main__":
    import argparse, pathlib
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile",required=True)
    ap.add_argument("--claims",required=True)
    ap.add_argument("--target-type",required=True)
    ap.add_argument("--target-id",required=True)
    ap.add_argument("--modality",required=True)
    ap.add_argument("--as-of",required=True)
    args=ap.parse_args()
    cfg=json.loads(pathlib.Path(args.profile).read_text())
    claims=json.loads(pathlib.Path(args.claims).read_text())
    print(json.dumps(estimate(claims,args.target_type,args.target_id,args.modality,args.as_of,cfg),indent=2))
