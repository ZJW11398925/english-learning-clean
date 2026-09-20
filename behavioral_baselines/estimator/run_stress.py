
from pathlib import Path
import json, importlib.util, copy

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("estimator", HERE/"estimator_reference_v1_1.py")
est=importlib.util.module_from_spec(spec); spec.loader.exec_module(est)
cfg=json.loads((HERE/"estimator_reference_profile_v1_1.json").read_text())
cases=json.loads((HERE/"estimator_stress_cases_v1_1.json").read_text())

def getpath(obj,path):
    cur=obj
    for p in path.split("."):
        cur=cur[p]
    return cur

def assertion_ok(st,a):
    path,op,val=a
    x=getpath(st,path)
    if op=="eq": return x==val
    if op=="not_eq": return x!=val
    if op=="is": return x is val
    if op=="not_is": return x is not val
    if op=="ge": return x is not None and x>=val
    if op=="le": return x is not None and x<=val
    if op=="between": return x is not None and val[0]<=x<=val[1]
    if op=="contains": return val in x
    if op=="not_contains": return val not in x
    raise ValueError(op)

def run_case(c):
    try:
        st=est.estimate(
            c["claims"], c.get("tt","RESOURCE"), c.get("tid","expr.test"),
            c.get("mod","TEXT_PRODUCTION"), c.get("asof","2026-09-20T10:00:00+00:00"), cfg
        )
        if c.get("expect_error"):
            return False, ["expected input contract rejection"]
        fails=[a for a in c.get("assertions",[]) if not assertion_ok(st,a)]
        if c.get("compare_claims") is not None:
            st2=est.estimate(
                c["compare_claims"], c.get("tt","RESOURCE"), c.get("tid","expr.test"),
                c.get("mod","TEXT_PRODUCTION"), c.get("asof","2026-09-20T10:00:00+00:00"), cfg
            )
            if st != st2: fails.append(["determinism","failed",None])
        return not fails, fails
    except ValueError as e:
        return bool(c.get("expect_error")), [] if c.get("expect_error") else [str(e)]

passed=0
for c in cases:
    ok,fail=run_case(c)
    print(("PASS" if ok else "FAIL"), c["id"], "" if ok else fail)
    passed+=int(ok)
print(f"\nStress: {passed}/{len(cases)} PASS")
raise SystemExit(0 if passed==len(cases) else 1)
