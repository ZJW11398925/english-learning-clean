from __future__ import annotations
import re, copy
from urllib.parse import urlparse, parse_qs

SECRET_KEYS={"api_key","apikey","authorization","access_token","refresh_token","secret","password","token"}

class SecurityContractError(ValueError):
    pass

def authorize_memory_write(p):
    if not p.get("provenance_present",False):
        return {"decision":"DENY","reason":"MISSING_PROVENANCE"}
    domain=p.get("domain")
    src=p.get("source_type")
    sensitivity=p.get("sensitivity","NORMAL")
    kind=p.get("proposal_kind")
    if domain=="LEARNING":
        if kind=="SELF_REPORT":
            return {"decision":"ALLOW_SEPARATE_SELF_REPORT","reason":"NOT_PERFORMANCE_EVIDENCE"}
        if kind=="PERFORMANCE_EVIDENCE":
            if not p.get("observable_behavior",False):
                return {"decision":"DENY","reason":"NO_OBSERVABLE_BEHAVIOR"}
            if src=="MODEL_PROPOSAL" and not p.get("domain_validation_passed",False):
                return {"decision":"DENY","reason":"MODEL_PROPOSAL_NOT_VALIDATED"}
            return {"decision":"ALLOW","reason":"VALIDATED_PERFORMANCE_EVIDENCE"}
        return {"decision":"DENY","reason":"INVALID_LEARNING_WRITE_KIND"}
    if domain=="USER_PROFILE":
        if sensitivity=="HIGH":
            if src=="MODEL_PROPOSAL":
                return {"decision":"DENY","reason":"NO_SENSITIVE_INFERENCE"}
            if not p.get("explicit_persistence",False):
                return {"decision":"DENY","reason":"SENSITIVE_EXPLICIT_PERSISTENCE_REQUIRED"}
        if src=="MODEL_PROPOSAL" and not p.get("domain_validation_passed",False):
            return {"decision":"DENY","reason":"MODEL_PROPOSAL_NOT_VALIDATED"}
        return {"decision":"ALLOW","reason":"PROFILE_WRITE_ALLOWED"}
    if domain=="RELATIONSHIP":
        if not p.get("same_persona",False):
            return {"decision":"DENY","reason":"CROSS_PERSONA_RELATIONSHIP_WRITE"}
        if kind=="TEACHING_STATE":
            return {"decision":"DENY","reason":"TEACHING_STATE_NOT_RELATIONSHIP_MEMORY"}
        if sensitivity=="HIGH" and not p.get("explicit_persistence",False):
            return {"decision":"DENY","reason":"SENSITIVE_EXPLICIT_PERSISTENCE_REQUIRED"}
        if src=="MODEL_PROPOSAL" and not p.get("domain_validation_passed",False):
            return {"decision":"DENY","reason":"MODEL_PROPOSAL_NOT_VALIDATED"}
        return {"decision":"ALLOW","reason":"RELATIONSHIP_WRITE_ALLOWED"}
    if domain=="EPISODE":
        if src=="MODEL_PROPOSAL" and not p.get("domain_validation_passed",False):
            return {"decision":"DENY","reason":"MODEL_PROPOSAL_NOT_VALIDATED"}
        return {"decision":"ALLOW","reason":"EPISODE_WRITE_ALLOWED"}
    return {"decision":"DENY","reason":"UNKNOWN_DOMAIN"}

def authorize_provider_disclosure(action, requested_views, policy):
    if action not in policy["provider_actions"]:
        raise SecurityContractError("unknown provider action")
    rule=policy["provider_actions"][action]
    allow=set(rule["allow"]); deny=set(rule["deny"]); requested=set(requested_views)
    denied=sorted(v for v in requested if v in deny or v not in allow)
    approved=sorted(v for v in requested if v in allow and v not in deny)
    return {"decision":"ALLOW" if not denied else "FILTER","approved":approved,"denied":denied}

def _looks_secret_key(k):
    x=str(k).lower()
    return any(s in x for s in SECRET_KEYS)

def sanitize_log(value, inherited_key=None):
    raw_forbidden={"raw_user_text","raw_provider_prompt","raw_provider_response","prompt","provider_response","message_body","conversation_text"}
    if inherited_key and _looks_secret_key(inherited_key):
        return "[REDACTED]"
    if isinstance(value,dict):
        out={}
        for k,v in value.items():
            kl=str(k).lower()
            if _looks_secret_key(kl): out[k]="[REDACTED]"
            elif kl in raw_forbidden: out[k]="[OMITTED_RAW_CONTENT]"
            else: out[k]=sanitize_log(v,k)
        return out
    if isinstance(value,list): return [sanitize_log(x,inherited_key) for x in value]
    if isinstance(value,str):
        v=re.sub(r'(?i)Bearer\s+[A-Za-z0-9._\-]+','Bearer [REDACTED]',value)
        v=re.sub(r'(?i)(sk-[A-Za-z0-9_\-]{6,})','[REDACTED_SECRET]',v)
        return v
    return value

def plan_export(records):
    included=[]; excluded=[]
    for r in records:
        cls=r["data_class"]
        if cls in {"SECRET","RUNTIME_DIAGNOSTIC"}: excluded.append(r["id"])
        elif cls=="DERIVED_PRIVATE" and not r.get("required_for_restore",False): excluded.append(r["id"])
        else: included.append(r["id"])
    return {"included":sorted(included),"excluded":sorted(excluded),"requires_secret_reentry":True}

def plan_deletion(request, graph):
    scope=request["scope"]
    nodes={n["id"]:copy.deepcopy(n) for n in graph}
    selected=set()
    def owned(n): return n.get("owner")=="USER"
    for n in nodes.values():
        if not owned(n): continue
        if scope=="ALL_USER_DATA":
            if n["data_class"]!="GLOBAL_PUBLIC": selected.add(n["id"])
        elif scope=="PROFILE_FIELD":
            if n.get("kind")=="PROFILE_FIELD" and n.get("field_key")==request.get("field_key"): selected.add(n["id"])
        elif scope=="MEMORY_ITEM":
            if n["id"]==request.get("entity_id"): selected.add(n["id"])
        elif scope=="CONVERSATION":
            if n.get("conversation_id")==request.get("conversation_id") and n.get("kind") in {"USER_TURN","ASSISTANT_TURN","CONVERSATION","EPISODE_MEMORY"}: selected.add(n["id"])
        elif scope=="RELATIONSHIP_PAIR":
            if n.get("kind") in {"RELATIONSHIP_MEMORY","RELATIONSHIP_PROJECTION"} and n.get("persona_id")==request.get("persona_id"): selected.add(n["id"])
        elif scope=="LEARNING_TARGET":
            if n.get("target_id")==request.get("target_id") and n.get("kind") in {"EVIDENCE","LEARNER_STATE","REVIEW_EVENT","PLANNING_LEDGER_ENTRY"}: selected.add(n["id"])
        elif scope=="ALL_LEARNING_HISTORY":
            if n.get("kind") in {"EVIDENCE","LEARNER_STATE","REVIEW_EVENT","PLANNING_LEDGER_ENTRY","LEARNING_PROJECTION"}: selected.add(n["id"])
        elif scope=="PERSONA_PACKAGE":
            if n.get("kind")=="CHARACTER_PACKAGE" and n.get("persona_id")==request.get("persona_id"): selected.add(n["id"])
    delete=set(selected); rebuild=set(); cancel=set()
    changed=True
    while changed:
        changed=False
        for n in nodes.values():
            if not owned(n) or n["id"] in delete: continue
            src=set(n.get("source_ids",[])); hit=src & delete
            if not hit: continue
            if n.get("kind") in {"PENDING_PROJECTION_JOB","PENDING_PROVIDER_ACTION"}:
                cancel.add(n["id"]); delete.add(n["id"]); changed=True; continue
            if n.get("rebuildable",False):
                if src and src <= delete: delete.add(n["id"])
                else:
                    if n["id"] not in rebuild:
                        rebuild.add(n["id"]); changed=True
                continue
            if n.get("derived_from_sources",False) and src and src <= delete:
                delete.add(n["id"]); changed=True
    delete={nid for nid in delete if owned(nodes[nid]) and nodes[nid]["data_class"]!="GLOBAL_PUBLIC"}
    rebuild={nid for nid in rebuild if nid not in delete}
    cancel={nid for nid in cancel if nid in delete}
    return {"delete":sorted(delete),"rebuild":sorted(rebuild),"cancel":sorted(cancel),"tombstones":sorted(selected)}

def import_with_tombstones(records, tombstones):
    deleted=set(tombstones)
    return [r for r in records if r["id"] not in deleted]


def validate_provider_endpoint(url):
    p=urlparse(url)
    host=(p.hostname or "").lower()
    if p.username or p.password:
        return {"decision":"DENY","reason":"SECRET_IN_PROVIDER_URL"}
    for k in parse_qs(p.query, keep_blank_values=True):
        if _looks_secret_key(k):
            return {"decision":"DENY","reason":"SECRET_IN_PROVIDER_URL"}
    if p.scheme=="https" and host:
        return {"decision":"ALLOW","reason":"HTTPS_REMOTE_OR_LOCAL"}
    if p.scheme=="http" and host in {"localhost","127.0.0.1","::1"}:
        return {"decision":"ALLOW","reason":"LOOPBACK_HTTP_ALLOWED"}
    return {"decision":"DENY","reason":"INSECURE_PROVIDER_ENDPOINT"}

def validate_provider_action(action):
    for k,v in action.items():
        if _looks_secret_key(k) and k not in {"secret_ref"}:
            return {"decision":"DENY","reason":"RAW_SECRET_IN_DURABLE_ACTION"}
    if "secret_ref" not in action:
        return {"decision":"DENY","reason":"MISSING_SECRET_REFERENCE"}
    return {"decision":"ALLOW","reason":"SECRET_BY_REFERENCE"}

def plan_external_disclosure_deletion(disclosure):
    status=disclosure.get("status")
    if status in {"NOT_SENT","QUEUED"}:
        return {"local_action":"CANCEL","external_action":"NONE","remote_revocation":"NOT_APPLICABLE"}
    if status in {"SENT","SENT_COMPLETE","SENT_PARTIAL"}:
        if disclosure.get("provider_delete_supported") and disclosure.get("provider_request_id"):
            return {"local_action":"DELETE_LOCAL_RECEIPT_CONTENT_REFS","external_action":"SCHEDULE_PROVIDER_DELETE","remote_revocation":"PENDING_PROVIDER"}
        return {"local_action":"DELETE_LOCAL_RECEIPT_CONTENT_REFS","external_action":"NONE","remote_revocation":"CANNOT_BE_GUARANTEED_BY_APP"}
    return {"local_action":"REVIEW","external_action":"NONE","remote_revocation":"UNKNOWN"}
