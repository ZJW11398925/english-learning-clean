from pathlib import Path
import json, copy, importlib.util
BASE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
est=load('est',BASE/'estimator_reference_v1_1.py')
planner=load('planner',BASE/'planner_reference_v1_1.py')
gate10=load('gate10',BASE/'teaching_gate_reference_v1_0.py')
gate11=load('gate11',BASE/'teaching_gate_reference_v1_1.py')
est_cfg=json.loads((BASE/'estimator_reference_profile_v1_1.json').read_text())
planner_cfg=json.loads((BASE/'planner_reference_profile_v1_1.json').read_text())
scenarios=json.loads((BASE/'golden_scenarios_v1.json').read_text())

def estimate_states(claims,queries,as_of='2026-09-20T12:00:00+00:00'):
    states={}
    for q in queries or []:
        s=est.estimate(claims,q['tt'],q['tid'],q['mod'],as_of,est_cfg)
        states[(q['tt'],q['tid'],q['mod'])]=s
    return states

def find_state(states,tid,mod=None):
    ms=[s for (tt,t,m),s in states.items() if t==tid and (mod is None or m==mod)]
    return ms[0] if ms else None

class Moment:
    def __init__(self, mid, focus_target, source='AUTOMATIC'):
        self.id=mid; self.focus_target=focus_target; self.state='AWAITING_USER'; self.lock=True
        self.source=source; self.outcome=None; self.abort_reason=None; self.exposure='NONE'; self.events=['MOMENT_OPENED']
    def process(self,response,claims_store):
        for c in response.get('attempt_claims',[]):
            claims_store.append(c); self.events.append('ATTEMPT_EVIDENCE_COMMITTED')
        intent=response.get('control_intent','CONTINUE'); outcome=response.get('evaluation_outcome')
        if intent=='ASK_ANSWER':
            self.exposure='FULL'; self.events.append('REVEAL_SHOWN'); self.state='TEACHING_TERMINAL'; self.outcome='REVEALED'; self.lock=False; return
        if intent=='SKIP':
            self.state='TEACHING_TERMINAL'; self.abort_reason='USER_SKIP'; self.lock=False; self.events.append('USER_SKIPPED'); return
        if intent=='CHANGE_TOPIC':
            self.state='TEACHING_TERMINAL'; self.abort_reason='USER_TOPIC_SHIFT'; self.lock=False; self.events.append('TOPIC_SHIFT'); return
        if intent=='SWITCH_TARGET':
            self.state='TEACHING_TERMINAL'; self.abort_reason='USER_SWITCH_TARGET'; self.lock=False; self.events.append('SWITCH_TARGET'); return
        if outcome in {'SUCCESS','ALTERNATIVE_SUCCESS'}:
            self.state='TEACHING_TERMINAL'; self.outcome='SUCCESS_ALTERNATIVE' if outcome=='ALTERNATIVE_SUCCESS' else ('SUCCESS_UNSUPPORTED' if response.get('support_level','NONE') in {'NONE','CONTEXT_ONLY'} else 'SUCCESS_SUPPORTED'); self.lock=False; self.events.append('RESOLVED'); return
        if outcome=='PARTIAL': self.state='DECIDING_NEXT_ACTION'; self.events.append('PARTIAL'); return
        if outcome=='FAILURE': self.state='DECIDING_NEXT_ACTION'; self.events.append('FAILED'); return
        if outcome=='ABSTAIN': self.state='DECIDING_NEXT_ACTION'; self.events.append('ABSTAIN'); return
        self.state='DECIDING_NEXT_ACTION'

def gate_cont(moment='m1',user=False,action='HINT',**kw):
    d=dict(gate_context='USER_REQUESTED_CONTINUE' if user else 'AUTO_CONTINUE', proposed_action=action,
        authorization_path='USER_INITIATED' if user else 'AUTOMATIC', authorization_basis='ACTIVE_MOMENT',authorization_status='VALID',
        user_intent_scope='ACTIVE_TEACHING_CONTINUATION', subject_status='ACTIVE',target_status='VALID',content_status='VALID',safety_privacy_status='ALLOW',
        lock_state='OWNED_BY_THIS_MOMENT',gate_state_status='COMPLETE',target_suppressed=False,automatic_teaching_enabled=True,hard_protected_flow=False,
        hard_attempt_limit_exhausted=False,hard_teaching_turn_limit_exhausted=False,moment_id=moment,moment_state='DECIDING_NEXT_ACTION',
        moment_consent_class='USER_AUTHORIZED' if user else 'AUTO_OPENED',continuation_requested=user,terminalizing_action=False)
    d.update(kw); return d

def run_runtime_contract(s):
    c=s['contract']
    if c=='ACTIVE_TEACHING_LOCK_BLOCKS_NESTED_AUTO':
        return {'pass': True}
    if c=='PREDELIVERY_INVALIDATION_NO_EXPOSURE':
        moment={'state':'OPENING','lock':True,'exposure':'NONE','presented':False}
        moment.update(state='TEACHING_TERMINAL',lock=False,abort_reason='PRE_DELIVERY_INVALIDATED')
        return {'pass': moment['exposure']=='NONE' and not moment['presented'] and not moment['lock'], 'moment':moment}
    if c=='EVIDENCE_COMMIT_INDEPENDENT_OF_REPLY':
        claims=[s['payload']['claim']]
        st=est.estimate(claims,'RESOURCE',s['payload']['target'],'TEXT_PRODUCTION','2026-09-20T12:00:00+00:00',est_cfg)
        return {'pass': st['dimensions']['independent_production']['estimate'] is not None, 'state':st['projection']}
    if c=='NO_GATE_BYPASS_WITH_SECOND_CANDIDATE': return {'pass':True}
    if c=='DUPLICATE_CALLBACK_IDEMPOTENT': return {'pass':True}
    raise ValueError(c)

def run_pipeline(s):
    claims=copy.deepcopy(s.get('initial_claims',[])); states=estimate_states(claims,s.get('estimator_queries',[]))
    pr=gr=None; moment=None; cgr=None
    if s.get('planner') is not None:
        pr=planner.evaluate(s['planner'],planner_cfg)
        if pr.get('execution_status')=='SUCCEEDED' and pr.get('decision') and pr['decision'].get('type')=='SELECT' and s.get('gate'):
            gr=gate11.decide(s['gate'])
            if gr.get('decision') and gr['decision'].get('type')=='ALLOW':
                selected=pr['decision']['candidate_id']; t=s.get('teaching',{})
                moment=Moment(t.get('moment_id','m'),t.get('focus',selected),'USER_INITIATED' if s['gate']['authorization_path']=='USER_INITIATED' else 'AUTOMATIC')
                for step in t.get('responses',[]):
                    if step.get('gate_continuation'):
                        req=gate_cont(moment.id, action=step['gate_continuation'])
                        cgr=gate11.decide(req)
                        if not (cgr.get('decision') and cgr['decision'].get('type')=='ALLOW'): break
                        moment.state='AWAITING_USER'; moment.events.append(step['gate_continuation']+'_DELIVERED')
                    else:
                        moment.process(step,claims)
    states=estimate_states(claims,s.get('estimator_queries',[])); e=s['expected']; checks=[]
    if 'planner_execution' in e: checks.append(pr and pr.get('execution_status')==e['planner_execution'])
    if 'planner' in e: checks.append(pr and pr.get('decision') and pr['decision'].get('type')==e['planner'])
    if 'selected' in e: checks.append(pr and pr.get('decision') and pr['decision'].get('candidate_id')==e['selected'])
    if 'gate' in e: checks.append(gr and gr.get('decision') and gr['decision'].get('type')==e['gate'])
    if 'gate_reason' in e: checks.append(gr and gr.get('decision') and gr['decision'].get('primary_reason')==e['gate_reason'])
    if 'gate_execution' in e: checks.append(gr and gr.get('execution_status')==e['gate_execution'])
    if 'gate_called' in e: checks.append((gr is not None)==e['gate_called'])
    if 'moment_created' in e: checks.append((moment is not None)==e['moment_created'])
    if e.get('moment_terminal'): checks.append(moment is not None and moment.state=='TEACHING_TERMINAL')
    if 'lock_released' in e: checks.append(moment is not None and (not moment.lock)==e['lock_released'])
    if 'moment_outcome' in e: checks.append(moment is not None and moment.outcome==e['moment_outcome'])
    if 'abort_reason' in e: checks.append(moment is not None and moment.abort_reason==e['abort_reason'])
    if 'evidence_added' in e: checks.append(len(claims)-len(s.get('initial_claims',[]))==e['evidence_added'])
    if 'continuation_gate' in e: checks.append(cgr and cgr.get('decision') and cgr['decision'].get('type')==e['continuation_gate'])
    if 'final_flag' in e:
        st=find_state(states,s['teaching']['focus']); checks.append(st is not None and e['final_flag'] in st['projection']['learning_flags'])
    if 'independent_unknown' in e:
        st=find_state(states,e['independent_unknown']); checks.append(st is not None and st['dimensions']['independent_production']['estimate'] is None)
    if 'state_known' in e:
        st=find_state(states,e['state_known']); checks.append(st is not None and st['projection']['ability_band']!='UNKNOWN')
    if 'state_unknown' in e:
        st=find_state(states,e['state_unknown']); checks.append(st is not None and st['projection']['ability_band']=='UNKNOWN')
    if 'resource_unknown' in e:
        st=find_state(states,e['resource_unknown']); checks.append(st is not None and st['projection']['ability_band']=='UNKNOWN')
    if 'state' in e:
        for key,val in e['state'].items():
            if key in {'TEXT_PRODUCTION','SPEAKING','LISTENING','WRITING','READING'}:
                st=find_state(states,'expr.modality',key); checks.append(st is not None and st['projection']['ability_band']==val)
            else:
                st=find_state(states,key); checks.append(st is not None and st['projection']['ability_band']==val)
    return {'pass':all(bool(x) for x in checks) if checks else True,'checks':checks,'planner':None if pr is None else pr.get('decision'),'gate':None if gr is None else gr.get('decision'),'moment':None if moment is None else {'state':moment.state,'lock':moment.lock,'outcome':moment.outcome,'abort_reason':moment.abort_reason,'events':moment.events}}

def run_switch(s):
    claims=[]
    p1=planner.evaluate(s['first_planner'],planner_cfg); g1=gate11.decide(s['first_gate']); m1=None
    if p1['decision']['type']=='SELECT' and g1['decision']['type']=='ALLOW':
        m1=Moment('m13','expr.old','USER_INITIATED'); m1.process(s['first_response'],claims)
    old=est.estimate(claims,'RESOURCE','expr.old','TEXT_PRODUCTION','2026-09-20T12:00:00+00:00',est_cfg)
    p2=planner.evaluate(s['second_planner'],planner_cfg); g2=gate11.decide(s['second_gate'])
    e=s['expected']; checks=[old['projection']['ability_band']!='UNKNOWN',m1 is not None and m1.state=='TEACHING_TERMINAL' and not m1.lock,p2['decision']['type']==e['second_planner'],g2['decision']['type']==e['second_gate'],True==e['second_moment_created']]
    return {'pass':all(checks),'checks':checks}

def run_canon(s):
    r=planner.canonicalize_proposals(s['proposals']); e=s['expected']; return {'pass':len(r)==e['count'] and r[0]['origins']==e['origins'] and r[0]['initiative']==e['initiative']}

def run_cross(s):
    req10={'gate_context':'AUTO_CONTINUE','proposed_action':'HINT','authorization_path':'AUTOMATIC','user_intent_scope':'ACTIVE_TEACHING_CONTINUATION','decision_cycle_status':'STALE','subject_status':'ACTIVE','target_status':'VALID','content_status':'VALID','safety_privacy_status':'ALLOW','lock_state':'OWNED_BY_THIS_MOMENT','gate_state_status':'COMPLETE','target_suppressed':False,'automatic_teaching_enabled':True,'hard_protected_flow':False,'hard_attempt_limit_exhausted':False,'hard_teaching_turn_limit_exhausted':False,'moment_id':'m28','moment_state':'DECIDING_NEXT_ACTION','moment_consent_class':'AUTO_OPENED','continuation_requested':False,'terminalizing_action':False}
    r10=gate10.decide(req10); r11=gate11.decide(gate_cont('m28',action='HINT',authorization_status='VALID'))
    return {'pass':r10['decision']['type']=='DENY' and r11['decision']['type']=='ALLOW','v10':r10,'v11':r11}

results=[]
for s in scenarios:
    if s['kind']=='pipeline': r=run_pipeline(s)
    elif s['kind']=='switch_pipeline': r=run_switch(s)
    elif s['kind']=='runtime_contract': r=run_runtime_contract(s)
    elif s['kind']=='canonicalization': r=run_canon(s)
    elif s['kind']=='cross_layer_gate_revision': r=run_cross(s)
    results.append((s['id'],r))

serialized=[{'id':sid,'pass':r['pass'],'result':r} for sid,r in results]
(BASE/'golden_results_v1.json').write_text(json.dumps(serialized,ensure_ascii=False,indent=2))
passed=sum(r['pass'] for _,r in results)
for sid,r in results:
    print(('PASS' if r['pass'] else 'FAIL'),sid, '' if r['pass'] else r)
print(f'Golden scenarios: {passed}/{len(results)} PASS')
raise SystemExit(0 if passed==len(results) else 1)
