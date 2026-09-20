from pathlib import Path
import json, subprocess, sys, importlib.util, copy, re
ROOT=Path(__file__).resolve().parent
B=ROOT/'behavioral_baselines'
results=[]
def record(name,ok,detail): results.append({'name':name,'pass':bool(ok),'detail':detail})

def run_py(name,path):
    cp=subprocess.run([sys.executable,str(path)],capture_output=True,text=True,cwd=path.parent)
    record(name,cp.returncode==0,(cp.stdout+cp.stderr).strip()[-5000:])

run_py('Estimator stress',B/'estimator'/'run_stress.py')
run_py('Planner stress',B/'planner'/'run_stress.py')
run_py('Golden cross-layer pack',B/'golden'/'run_golden_pack.py')
run_py('Local runtime integration',B/'runtime'/'run_local_runtime_tests.py')

# Gate v1.1 regression results produced by Golden cross-layer revision.
gate_reg=json.loads((B/'gate'/'BF-03_v1_1_regression_results.json').read_text())
record('Gate v1.1 regression', all(x.get('pass') for x in gate_reg), f"{sum(bool(x.get('pass')) for x in gate_reg)}/{len(gate_reg)}")
meta=json.loads((B/'gate'/'metamorphic_results_v1.json').read_text())
record('Gate metamorphic', all(x.get('pass') for x in meta), f"{sum(bool(x.get('pass')) for x in meta)}/{len(meta)}")

# Generic module loader.
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

# Security benchmark actual replay.
sec=load('sec',B/'security'/'security_reference_v1.py')
policy=json.loads((B/'security'/'security_privacy_policy_v1.json').read_text())
sec_cases=json.loads((B/'security'/'security_benchmark_v1.json').read_text())
def contains_value(obj,val):
    if obj==val:return True
    if isinstance(obj,dict):return any(contains_value(v,val) for v in obj.values())
    if isinstance(obj,list):return any(contains_value(v,val) for v in obj)
    if isinstance(obj,str):return val in obj
    return False

def run_sec(c):
    typ=c['category']; x=c['input']; e=c['expected']
    if typ=='memory_write': r=sec.authorize_memory_write(x)
    elif typ=='provider': r=sec.authorize_provider_disclosure(x['action'],x['views'],policy)
    elif typ=='log': r=sec.sanitize_log(x['event'])
    elif typ=='export': r=sec.plan_export(x['records'])
    elif typ=='deletion': r=sec.plan_deletion(x['request'],x['graph'])
    elif typ=='import': r=sec.import_with_tombstones(x['records'],x['tombstones'])
    elif typ=='endpoint': r=sec.validate_provider_endpoint(x['url'])
    elif typ=='external_delete': r=sec.plan_external_disclosure_deletion(x['disclosure'])
    elif typ=='provider_action': r=sec.validate_provider_action(x['action'])
    else: raise ValueError(typ)
    if typ=='log':
        for k,v in e.items():
            if k=='contains':
                if not contains_value(r,v): return False
            elif r.get(k)!=v:return False
        return True
    if typ=='deletion':
        for i in e.get('must_delete',[]):
            if i not in r['delete']:return False
        for i in e.get('must_rebuild',[]):
            if i not in r['rebuild']:return False
        for i in e.get('must_cancel',[]):
            if i not in r['cancel']:return False
        for i in e.get('must_tombstone',[]):
            if i not in r['tombstones']:return False
        for i in e.get('must_keep',[]):
            if i in r['delete']:return False
        return True
    if typ=='import':return [z['id'] for z in r]==e['ids']
    return all(r.get(k)==v for k,v in e.items())
sec_ok=[run_sec(c) for c in sec_cases]
record('Security benchmark',all(sec_ok),f'{sum(sec_ok)}/{len(sec_ok)}')

# Modality benchmark actual replay.
mod=load('mod',B/'modality'/'modality_scope_reference_v1.py')
mod_policy=json.loads((B/'modality'/'modality_scope_policy_v1.json').read_text())
mod_cases=json.loads((B/'modality'/'modality_benchmark_v1.json').read_text())
runtimes={'v1':mod_policy['v1_runtime_capabilities'],'future':{**mod_policy['v1_runtime_capabilities'], 'voice_input':True,'pronunciation_evaluator':True,'speaking_fluency_evaluator':True,'listening_comprehension_evaluator':True}}
def run_mod(c):
    typ=c['category']; x=c['input']; e=c['expected']
    if typ in {'classify','classify_future'}:
        runtime=runtimes['v1'] if typ=='classify' else runtimes['future']
        r=mod.classify_observation(x,runtime)
        return all(r.get(k)==v for k,v in e.items())
    if typ=='relation':
        r=mod.goal_relation(x['evidence_modality'],x['goal_modality'],x['task_contract'],mod_policy)
        return r==e['relation']
    if typ=='dims':
        rt=runtimes[x.get('runtime','v1')]
        dims=set(mod.allowed_measurement_dimensions(x['evidence_modality'],rt))
        return all(v in dims for v in e.get('allow',[])) and all(v not in dims for v in e.get('forbid',[]))
    if typ in {'claim','claim_future'}:
        rt=runtimes['v1'] if typ=='claim' else runtimes['future']
        r=mod.can_claim(x['claim_kind'],x['evidence_modalities'],rt,x.get('validated_assessment_module',False))
        return r==e['allowed']
    if typ=='coverage':
        rt=runtimes[x['runtime']]
        r=mod.coverage_obligation(x['goal_modality'],rt)
        return all(r.get(k)==v for k,v in e.items())
    if typ=='state_key':
        r=list(mod.canonical_state_key(x['target_type'],x['target_id'],x['evidence_modality']))
        return r==e['key']
    raise ValueError(typ)
mod_ok=[run_mod(c) for c in mod_cases]
record('Modality benchmark',all(mod_ok),f'{sum(mod_ok)}/{len(mod_ok)}')

# Compile all reference python.
pyfiles=list(B.rglob('*.py'))
compile_ok=True; errors=[]
for p in pyfiles:
    cp=subprocess.run([sys.executable,'-m','py_compile',str(p)],capture_output=True,text=True)
    if cp.returncode:
        compile_ok=False; errors.append(f'{p.name}:{cp.stderr}')
record('Reference Python compile',compile_ok,f'{len(pyfiles)} files' if compile_ok else errors)

# Cross-document static checks.
docs={n:(ROOT/n).read_text() for n in ['PRODUCT_CONTRACT.md','DOMAIN_MODEL.md','STATE_MACHINES.md','DATA_MODEL.md','RUNTIME_ARCHITECTURE.md','IMPLEMENTATION_PLAN.md']}
alltext='\n'.join(docs.values())
checks=[]
def must(cid,desc,cond):checks.append((cid,desc,bool(cond)))
def contains(doc,s):return s in docs[doc]
def absent(s):return s not in alltext

must('C01','All six canonical docs baseline status', all('CANONICAL IMPLEMENTATION BASELINE V1' in docs[n] for n in docs))
must('C02','Legacy SkillModality removed', absent('SkillModality') and absent('skill_modality'))
must('C03','GoalModality present', contains('PRODUCT_CONTRACT.md','GoalModality'))
must('C04','EvidenceModality present', 'EvidenceModality' in alltext and contains('DOMAIN_MODEL.md','Target × EvidenceModality'))
must('C05','InteractionChannel split', contains('PRODUCT_CONTRACT.md','InteractionChannel') and contains('DATA_MODEL.md','interaction_channel'))
must('C06','Typed chat speaking boundary', contains('PRODUCT_CONTRACT.md','typed chat != VOICE_PRODUCTION Evidence'))
must('C07','Impossible modality debt paused', contains('IMPLEMENTATION_PLAN.md','不累计 impossible CoverageDebt') or contains('IMPLEMENTATION_PLAN.md','impossible-modality pause'))
must('C08','Estimator baseline integrated', contains('DOMAIN_MODEL.md','Learner State Estimator — Behavioral Baseline V1'))
must('C09','PARTIAL mixed evidence integrated', contains('DOMAIN_MODEL.md','PARTIAL 是 mixed evidence'))
must('C10','Estimator deterministic', contains('DOMAIN_MODEL.md','deterministic、model-free projection'))
must('C11','Planner pipeline integrated', contains('DOMAIN_MODEL.md','Pareto prune') and contains('STATE_MACHINES.md','request_priority restriction'))
must('C12','Communicative impact integrated', 'communicative_impact' in alltext)
must('C13','Planner DEGRADED canonical', contains('STATE_MACHINES.md','DEGRADED\n  FAILED') and contains('DATA_MODEL.md','DEGRADED\n  FAILED'))
must('C14','NO_TARGET remains distinct', contains('STATE_MACHINES.md','SELECT\nNO_TARGET'))
must('C15','Gate no rerank semantics', contains('STATE_MACHINES.md','Gate 不重新计算 learning_need'))
must('C16','Gate OPEN authorization basis', contains('STATE_MACHINES.md','OPEN         → DECISION_CYCLE'))
must('C17','Gate continuation ActiveMoment', contains('STATE_MACHINES.md','CONTINUATION → ACTIVE_MOMENT'))
must('C18','Gate execution status schema', contains('DATA_MODEL.md','### GateExecutionStatus'))
must('C19','Gate degraded no synthetic deny', contains('DATA_MODEL.md','不存在 synthetic `GateDecision(DENY)`'))
must('C20','Active moment own evidence not invalidation', contains('RUNTIME_ARCHITECTURE.md','不构成 continuation invalidation'))
must('C21','Legacy lock TTL fields removed', absent('lease_expires_at') and absent('heartbeat_at'))
must('C22','Local keyed mutex mapping', 'keyed mutex' in alltext)
must('C23','runtime_epoch canonical', 'runtime_epoch' in alltext)
must('C24','Durable active teaching lock canonical', 'active_teaching_lock' in alltext)
must('C25','app.db physical profile', contains('DATA_MODEL.md','app.db') and contains('RUNTIME_ARCHITECTURE.md','app.db'))
must('C26','Legacy user.db/runtime.db recommendation removed', absent('user.db') and absent('runtime.db'))
must('C27','content.db remains read-only/generated', contains('DATA_MODEL.md','content.db') and 'read-only' in docs['DATA_MODEL.md'])
must('C28','SecretStore canonical', 'SecretStore' in alltext or 'secret store' in alltext)
must('C29','No provider call in transaction', contains('RUNTIME_ARCHITECTURE.md','External provider call 必须发生在 DB transaction 之外'))
must('C30','Action-level retry', contains('RUNTIME_ARCHITECTURE.md','不得重跑 whole Turn'))
must('C31','CP4 nonblocking', contains('RUNTIME_ARCHITECTURE.md','pending/failure 不阻塞下一 user-visible turn'))
must('C32','Startup recovery profile', contains('RUNTIME_ARCHITECTURE.md','runtime_epoch'))
must('C33','Security product contract integrated', contains('PRODUCT_CONTRACT.md','Security / Privacy / Deletion Product Contract'))
must('C34','Untrusted content boundary integrated', contains('DOMAIN_MODEL.md','UNTRUSTED_CONTENT'))
must('C35','High sensitivity explicit persistence', contains('PRODUCT_CONTRACT.md','持久保存需要显式用户许可'))
must('C36','Provenance-aware deletion', contains('PRODUCT_CONTRACT.md','provenance-aware operation'))
must('C37','No false third-party delete claim', contains('PRODUCT_CONTRACT.md','不得声称“已从第三方永久删除”'))
must('C38','Provider minimal disclosure', contains('RUNTIME_ARCHITECTURE.md','action-specific disclosure view'))
must('C39','R0-R4 readiness retained', all(x in alltext for x in ['R0','R1','R2','R3','R4']))
must('C40','Automatic current-error R4 preserved', 'R4' in docs['IMPLEMENTATION_PLAN.md'] or 'R4' in docs['PRODUCT_CONTRACT.md'])
must('C41','ContextOpportunity distinct', 'ContextOpportunity' in alltext and 'LearningOpportunityRecord' in alltext)
must('C42','turn/message sequence retained', 'turn_sequence' in alltext and 'message_sequence' in alltext)
must('C43','ClientRenderAck async retained', 'ClientRenderAck' in alltext and 'async' in docs['RUNTIME_ARCHITECTURE.md'])
must('C44','NO_ASSISTANT_OUTPUT retained', 'NO_ASSISTANT_OUTPUT' in alltext)
must('C45','Input interrupt durable', 'InterruptRequest' in alltext)
must('C46','Current Evidence before Planner', contains('RUNTIME_ARCHITECTURE.md','当前 turn 的用户行为先进入 Learning'))
must('C47','CP2 atomic group retained', all(x in docs['RUNTIME_ARCHITECTURE.md'] for x in ['GateDecision(ALLOW)','TeachingMoment','first GenerationActionIntent']))
must('C48','Post-BF execution order present', contains('IMPLEMENTATION_PLAN.md','Post-BF V1 Execution Order — Normative'))
must('C49','Learning before Relationship execution', docs['IMPLEMENTATION_PLAN.md'].find('Phase 2  Learning Evidence Kernel') < docs['IMPLEMENTATION_PLAN.md'].find('Phase 4  Relationship'))
must('C50','Manual Teaching vertical slice early', contains('IMPLEMENTATION_PLAN.md','Phase 3  User-initiated TeachingMoment vertical slice'))
must('C51','No distributed infra bootstrap', contains('IMPLEMENTATION_PLAN.md','Do **not** install Redis/Kafka'))
must('C52','Golden assets mandatory', contains('IMPLEMENTATION_PLAN.md','Golden Scenario Baseline V1'))
must('C53','Behavioral assets packaged', (ROOT/'behavioral_baselines').is_dir())
must('C54','Gate v1.1 reference packaged', (B/'gate'/'teaching_gate_reference_v1_1.py').exists())
must('C55','Estimator reference packaged', (B/'estimator'/'estimator_reference_v1_1.py').exists())
must('C56','Planner reference packaged', (B/'planner'/'planner_reference_v1_1.py').exists())
must('C57','Security contract packaged', (B/'security'/'SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md').exists())
must('C58','Modality contract packaged', (B/'modality'/'BF-06_V1_Operational_Modality_Scope.md').exists())
must('C59','Local runtime contract packaged', (B/'runtime'/'BF-07_Local_Runtime_Profile_v1.0.md').exists())
must('C60','Markdown fences balanced', all(docs[n].count('```')%2==0 for n in docs))

for cid,desc,ok in checks: record(f'Consistency {cid}',ok,desc)

summary={
 'regressions':[r for r in results if not r['name'].startswith('Consistency ')],
 'consistency':{'passed':sum(1 for _,_,o in checks if o),'total':len(checks),
                'failed':[{'id':i,'description':d} for i,d,o in checks if not o]},
 'all_pass':all(r['pass'] for r in results)
}
(ROOT/'POST_BF_REGRESSION_RESULTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
raise SystemExit(0 if summary['all_pass'] else 1)
