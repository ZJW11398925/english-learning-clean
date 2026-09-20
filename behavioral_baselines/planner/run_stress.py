
from pathlib import Path
import json, importlib.util, copy

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("planner",HERE/"planner_reference_v1_1.py")
planner=importlib.util.module_from_spec(spec); spec.loader.exec_module(planner)
cfg=json.loads((HERE/"planner_reference_profile_v1_1.json").read_text())
cases=json.loads((HERE/"planner_stress_cases_v1_1.json").read_text())

def run(c):
    e=c["expected"]
    try:
        r=planner.evaluate(c["input"],cfg)
        if e["error"]: return False
        if e["custom"]=="DEGRADED":
            return r.get("execution_status")=="DEGRADED" and r.get("decision") is None
        if e["custom"]=="EQUAL_UTILITY":
            s=r["evaluation"]["scored"]
            return len(s)==2 and abs(s[0]["utility"]-s[1]["utility"])<1e-9
        if e["custom"]=="HI_UTILITY_GE":
            s={x["candidate"]["id"]:x["utility"] for x in r["evaluation"]["scored"]}
            return s["hi"]>=s["lo"]
        if e["custom"]=="LOW_COST_UTILITY_GE":
            s={x["candidate"]["id"]:x["utility"] for x in r["evaluation"]["scored"]}
            return s["cl"]>=s["ch"]
        if e["custom"]=="ORDER_DETERMINISM":
            q=copy.deepcopy(c["input"]); q["candidates"]=list(reversed(q["candidates"]))
            return r["decision"]==planner.evaluate(q,cfg)["decision"]
        if r["decision"]["type"]!=e["decision"]: return False
        if e["decision"]=="SELECT":
            return r["decision"].get("candidate_id")==e["selected"]
        return r["decision"].get("reason")==e["reason"]
    except Exception:
        return bool(e["error"])

n=sum(run(c) for c in cases)
print(f"Stress: {n}/{len(cases)} PASS")
raise SystemExit(0 if n==len(cases) else 1)
