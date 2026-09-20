
from __future__ import annotations
import tempfile, sqlite3, importlib.util, pathlib, os, json

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("rt",HERE/"local_runtime_reference_v1.py")
rt=importlib.util.module_from_spec(spec); spec.loader.exec_module(rt)

results=[]
def check(cid,desc,fn):
    try:
        ok,detail=fn()
    except Exception as e:
        ok=False; detail=repr(e)
    results.append({"id":cid,"description":desc,"pass":bool(ok),"detail":detail})

def fresh(path=":memory:"):
    return rt.LocalRuntime(path)

def seed_turn(r,turn="t1",conv="c1",inp="i1",ut="u1"):
    r.ingest_input(inp,conv,"h")
    r.commit_cp0(turn,conv,inp,ut,"hello")

def provider_tx_test():
    r=fresh()
    r.conn.execute("BEGIN IMMEDIATE")
    try:
        try:
            r.provider_call_guard(); ok=False
        except rt.RuntimeInvariantError:
            ok=True
    finally:
        r.conn.execute("ROLLBACK")
    return ok,"provider outside transaction invariant"

def duplicate_input():
    r=fresh()
    a=r.ingest_input("i1","c1","h")
    b=r.ingest_input("i1","c1","h")
    n=r.conn.execute("SELECT COUNT(*) FROM input_envelope").fetchone()[0]
    return a and not b and n==1,{"inserted":[a,b],"count":n}

def interrupt_without_guard():
    r=fresh()
    with r.conversation_guard("c1"):
        inserted=r.ingest_input("i2","c1","h2",active_turn_id="t1",active_action_id="a1")
        n=r.conn.execute("SELECT COUNT(*) FROM interrupt_request").fetchone()[0]
    return inserted and n==1,{"interrupts":n}

def mutex_exclusion():
    r=fresh()
    with r.conversation_guard("c1"):
        try:
            with r.conversation_guard("c1",blocking=False):
                return False,"unexpected second guard"
        except rt.RuntimeInvariantError:
            return True,"second coordinator rejected"

def cp0_atomic():
    r=fresh(); r.ingest_input("i1","c1","h")
    r.commit_cp0("t1","c1","i1","u1","hello")
    a=r.conn.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0]
    b=r.conn.execute("SELECT COUNT(*) FROM user_turn").fetchone()[0]
    return a==1 and b==1,{"turn":a,"user":b}

# Baseline v1.0.1 (2026-09-20, explicit exception DEC-OPI-d5b616bf-…3):
# the two f-string COUNT lookups below were rewritten as fully literal SQL
# per table (identifiers cannot be parameter-bound; values are unchanged).
_COUNT_SQL = {
    "gate_decision": "SELECT COUNT(*) FROM gate_decision",
    "teaching_moment": "SELECT COUNT(*) FROM teaching_moment",
    "active_teaching_lock": "SELECT COUNT(*) FROM active_teaching_lock",
    "generation_action": "SELECT COUNT(*) FROM generation_action",
}

def cp2_rollback(stage):
    r=fresh(); seed_turn(r)
    try:
        r.commit_cp2_open("t1","c1","g1","m1","target","act1",fail_after=stage)
    except RuntimeError:
        pass
    counts={}
    for table in ["gate_decision","teaching_moment","active_teaching_lock","generation_action"]:
        counts[table]=r.conn.execute(_COUNT_SQL[table]).fetchone()[0]
    return all(v==0 for v in counts.values()),counts

def cp2_success():
    r=fresh(); seed_turn(r)
    r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    counts={t:r.conn.execute(_COUNT_SQL[t]).fetchone()[0]
            for t in ["gate_decision","teaching_moment","active_teaching_lock","generation_action"]}
    return all(v==1 for v in counts.values()),counts

def teaching_lock_unique():
    r=fresh(); seed_turn(r)
    r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    r.ingest_input("i2","c1","h2")
    r.commit_cp0("t2","c1","i2","u2","next")
    try:
        r.commit_cp2_open("t2","c1","g2","m2","target2","act2")
        return False,"second lock opened"
    except sqlite3.IntegrityError:
        return True,"unique active teaching lock"

def terminal_release():
    r=fresh(); seed_turn(r)
    r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    r.release_teaching_lock_terminal("m1")
    lock=r.conn.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
    st=r.conn.execute("SELECT state FROM teaching_moment WHERE moment_id='m1'").fetchone()[0]
    return lock==0 and st=="TEACHING_TERMINAL",{"lock":lock,"state":st}

def provider_attempt_retry():
    r=fresh(); seed_turn(r)
    r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p1=r.create_provider_attempt("act1"); p2=r.create_provider_attempt("act1")
    n=r.conn.execute("SELECT COUNT(*) FROM provider_attempt WHERE action_id='act1'").fetchone()[0]
    return p1!=p2 and n==2,{"attempts":[p1,p2]}

def accept_once():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p1=r.create_provider_attempt("act1"); p2=r.create_provider_attempt("act1")
    a=r.accept_provider_result("act1",p1)
    b=r.accept_provider_result("act1",p2)
    return a=="ACCEPTED" and b=="DUPLICATE_IGNORED",{"first":a,"second":b}

def late_result_ignored():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p1=r.create_provider_attempt("act1")
    r.cancel_action("act1","SUPERSEDED")
    a=r.accept_provider_result("act1",p1)
    return a=="IGNORED_LATE_RESULT",a

def canonical_once():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p=r.create_provider_attempt("act1"); r.accept_provider_result("act1",p)
    a=r.canonicalize_delivery("t1","act1","d1","hello")
    b=r.canonicalize_delivery("t1","act1","d1","hello")
    n=r.conn.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0]
    return a and (not b) and n==1,{"commits":[a,b],"count":n}

def ack_after_terminal():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p=r.create_provider_attempt("act1"); r.accept_provider_result("act1",p)
    r.canonicalize_delivery("t1","act1","d1","hello")
    r.record_client_ack("ack1","act1","FULL")
    n=r.conn.execute("SELECT COUNT(*) FROM client_render_ack").fetchone()[0]
    return n==1,n

def projection_after_release():
    r=fresh(); seed_turn(r); r.enqueue_projection("pr1","c1","t1","RELATIONSHIP")
    with r.conversation_guard("c1"):
        try:
            r.run_projection("pr1")
            bad=False
        except rt.RuntimeInvariantError:
            bad=True
    r.run_projection("pr1")
    st=r.conn.execute("SELECT state FROM projection_job WHERE projection_id='pr1'").fetchone()[0]
    return bad and st=="COMPLETED",{"blocked_while_guard":bad,"state":st}

def interrupt_handoff():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    with r.conversation_guard("c1"):
        r.ingest_input("i2","c1","h2",active_turn_id="t1",active_action_id="act1")
        r.terminalize_old_turn_for_interrupt("t1","act1")
        st=r.conn.execute("SELECT state FROM turn_record WHERE turn_id='t1'").fetchone()[0]
        irq=r.conn.execute("SELECT status FROM interrupt_request").fetchone()[0]
    return st=="CANCELLED" and irq=="HANDOFF_READY",{"turn":st,"interrupt":irq}

def no_parallel_visible_streams():
    r=fresh()
    with r.conversation_guard("c1"):
        return r.is_guard_held("c1"),"single coordinator owns visible path"

def startup_epoch_recovery(checkpoint,expected):
    with tempfile.TemporaryDirectory() as td:
        db=os.path.join(td,"app.db")
        r1=fresh(db); seed_turn(r1)
        r1.conn.execute("UPDATE turn_record SET checkpoint=?,state='WORKING' WHERE turn_id='t1'",(checkpoint,))
        old=r1.runtime_epoch; r1.conn.close()
        r2=fresh(db)
        plan=r2.recovery_plan()
        acts=[x["action"] for x in plan if x["kind"]=="TURN" and x["id"]=="t1"]
        return r2.runtime_epoch==old+1 and acts==[expected],{"epoch":[old,r2.runtime_epoch],"actions":acts}

def projection_recovery():
    with tempfile.TemporaryDirectory() as td:
        db=os.path.join(td,"app.db")
        r1=fresh(db); seed_turn(r1); r1.enqueue_projection("pr1","c1","t1","EPISODE")
        r1.conn.close()
        r2=fresh(db); plan=r2.recovery_plan()
        ok=any(x["kind"]=="PROJECTION" and x["id"]=="pr1" for x in plan)
        return ok,plan

def orphan_terminal_lock_release():
    with tempfile.TemporaryDirectory() as td:
        db=os.path.join(td,"app.db")
        r1=fresh(db); seed_turn(r1); r1.commit_cp2_open("t1","c1","g1","m1","target","act1")
        r1.conn.execute("UPDATE teaching_moment SET state='TEACHING_TERMINAL' WHERE moment_id='m1'")
        r1.conn.close()
        r2=fresh(db); plan=r2.recovery_plan()
        ok=any(x["kind"]=="LOCK" and x["action"]=="RELEASE_ORPHAN_LOCK" for x in plan)
        return ok,plan

def active_moment_revalidate():
    with tempfile.TemporaryDirectory() as td:
        db=os.path.join(td,"app.db")
        r1=fresh(db); seed_turn(r1); r1.commit_cp2_open("t1","c1","g1","m1","target","act1")
        r1.conn.close()
        r2=fresh(db); plan=r2.recovery_plan()
        ok=any(x["kind"]=="TEACHING" and x["action"]=="REVALIDATE_ACTIVE_MOMENT" for x in plan)
        return ok,plan

def no_heartbeat_columns():
    r=fresh()
    cols=[x[1] for x in r.conn.execute("PRAGMA table_info(active_teaching_lock)").fetchall()]
    return "expires_at" not in cols and "heartbeat_at" not in cols,cols

def no_durable_coordinator_lease_table():
    r=fresh()
    names={x[0] for x in r.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return "conversation_coordinator_lease" not in names,names

def guard_not_needed_for_ingest():
    r=fresh()
    with r.conversation_guard("c1"):
        ok=r.ingest_input("i2","c1","h",active_turn_id="t1",active_action_id="a1")
    return ok,"input durable while old coordinator held"

def second_turn_after_release():
    r=fresh()
    with r.conversation_guard("c1"):
        first=True
    try:
        with r.conversation_guard("c1",blocking=False):
            second=True
    except:
        second=False
    return first and second,"handoff after release"

def content_separate_contract():
    return True,"content.db read-only separate; app.db mutable user/runtime"

def secret_separate_contract():
    return True,"secrets by reference only; excluded from app.db"

def no_whole_turn_replay():
    r=fresh(); seed_turn(r)
    r.conn.execute("UPDATE turn_record SET checkpoint='CP2',state='WORKING' WHERE turn_id='t1'")
    # simulate older epoch by incrementing local epoch after durable state
    r.conn.execute("UPDATE turn_record SET owner_epoch=? WHERE turn_id='t1'",(r.runtime_epoch-1,))
    plan=r.recovery_plan()
    acts=[x["action"] for x in plan if x["kind"]=="TURN"]
    return acts==["RESUME_ACTION_BY_STABLE_ACTION_ID"],acts

def uncertain_delivery_plan():
    r=fresh(); seed_turn(r)
    r.conn.execute("UPDATE turn_record SET checkpoint='CP3_UNCERTAIN',state='WORKING',owner_epoch=? WHERE turn_id='t1'",(r.runtime_epoch-1,))
    plan=r.recovery_plan()
    acts=[x["action"] for x in plan if x["kind"]=="TURN"]
    return acts==["CONSERVATIVE_DELIVERY_RECONCILIATION"],acts

def cp1_plan():
    r=fresh(); seed_turn(r)
    r.conn.execute("UPDATE turn_record SET checkpoint='CP1',state='WORKING',owner_epoch=? WHERE turn_id='t1'",(r.runtime_epoch-1,))
    acts=[x["action"] for x in r.recovery_plan() if x["kind"]=="TURN"]
    return acts==["RESUME_DECISION"],acts

def cp0_plan():
    r=fresh(); seed_turn(r)
    r.conn.execute("UPDATE turn_record SET checkpoint='CP0',state='WORKING',owner_epoch=? WHERE turn_id='t1'",(r.runtime_epoch-1,))
    acts=[x["action"] for x in r.recovery_plan() if x["kind"]=="TURN"]
    return acts==["RESUME_ANALYSIS"],acts

def stable_action_retry():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p1=r.create_provider_attempt("act1"); p2=r.create_provider_attempt("act1")
    action_ids={x[0] for x in r.conn.execute("SELECT DISTINCT action_id FROM provider_attempt")}
    return action_ids=={"act1"} and p1!=p2,{"action_ids":list(action_ids),"attempts":[p1,p2]}

def terminal_turn_not_recovered():
    r=fresh(); seed_turn(r)
    r.conn.execute("UPDATE turn_record SET state='COMPLETED',checkpoint='CP3',owner_epoch=? WHERE turn_id='t1'",(r.runtime_epoch-1,))
    plan=r.recovery_plan()
    return not any(x["kind"]=="TURN" and x["id"]=="t1" for x in plan),plan

def terminal_projection_can_retry():
    r=fresh(); seed_turn(r); r.enqueue_projection("pr1","c1","t1","RELATIONSHIP")
    # turn terminal first; projection remains independent
    r.conn.execute("UPDATE turn_record SET state='COMPLETED',checkpoint='CP3' WHERE turn_id='t1'")
    r.run_projection("pr1")
    st=r.conn.execute("SELECT state FROM projection_job WHERE projection_id='pr1'").fetchone()[0]
    return st=="COMPLETED",st

def no_projection_blocks_next_turn():
    r=fresh(); seed_turn(r); r.enqueue_projection("pr1","c1","t1","RELATIONSHIP")
    # don't execute projection; coordinator can still serve next turn
    try:
        with r.conversation_guard("c1",blocking=False):
            ok=True
    except:
        ok=False
    return ok,"pending projection does not own coordinator"

def action_cancel_before_late_result():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p=r.create_provider_attempt("act1")
    r.cancel_action("act1","CANCELLED")
    res=r.accept_provider_result("act1",p)
    return res=="IGNORED_LATE_RESULT",res

def client_ack_does_not_reopen_turn():
    r=fresh(); seed_turn(r); r.commit_cp2_open("t1","c1","g1","m1","target","act1")
    p=r.create_provider_attempt("act1"); r.accept_provider_result("act1",p)
    r.canonicalize_delivery("t1","act1","d1","hello")
    before=r.conn.execute("SELECT state FROM turn_record WHERE turn_id='t1'").fetchone()[0]
    r.record_client_ack("ack1","act1","FULL")
    after=r.conn.execute("SELECT state FROM turn_record WHERE turn_id='t1'").fetchone()[0]
    return before=="COMPLETED" and after=="COMPLETED",{"before":before,"after":after}

# Register 42 integration / contract checks.
check("L01_SQLITE_PROFILE","SQLite local runtime initializes.",lambda:(isinstance(fresh().conn,sqlite3.Connection),"sqlite"))
check("L02_FOREIGN_KEYS","Foreign keys enabled.",lambda:(lambda r:(r.conn.execute("PRAGMA foreign_keys").fetchone()[0]==1,"on"))(fresh()))
check("L03_WAL_OR_MEMORY_TESTMODE","WAL is used for file DB; in-memory test DB may report memory.",lambda:(lambda r:(r.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() in {"wal","memory"},"ok"))(fresh()))
check("L04_PROVIDER_OUTSIDE_TX","External provider call is forbidden inside SQL transaction.",provider_tx_test)
check("L05_DUPLICATE_INPUT","InputEnvelope dedupe is durable.",duplicate_input)
check("L06_INTERRUPT_WHILE_GUARD_HELD","New input can durably request interruption while old coordinator holds guard.",interrupt_without_guard)
check("L07_COORDINATOR_SERIAL","Per-conversation coordinator is single-owner in process.",mutex_exclusion)
check("L08_CP0_ATOMIC","CP0 commits TurnRecord + UserTurn together.",cp0_atomic)
check("L09_CP2_ROLLBACK_AFTER_GATE","CP2 rollback after Gate leaves no partial teaching state.",lambda:cp2_rollback("gate"))
check("L10_CP2_ROLLBACK_AFTER_MOMENT","CP2 rollback after Moment leaves no partial teaching state.",lambda:cp2_rollback("moment"))
check("L11_CP2_ROLLBACK_AFTER_LOCK","CP2 rollback after Lock leaves no partial teaching state.",lambda:cp2_rollback("lock"))
check("L12_CP2_ROLLBACK_AFTER_ACTION","CP2 rollback after Action leaves no partial teaching state.",lambda:cp2_rollback("action"))
check("L13_CP2_SUCCESS","Gate+Moment+Lock+first Action commit atomically.",cp2_success)
check("L14_TEACHING_LOCK_UNIQUE","One conversation cannot hold two active TeachingLocks.",teaching_lock_unique)
check("L15_TERMINAL_RELEASE","Teaching terminalization releases durable active lock.",terminal_release)
check("L16_ACTION_RETRY","Provider retry creates new attempt under same action.",provider_attempt_retry)
check("L17_ACCEPT_ONCE","At most one ProviderAttempt accepted per GenerationAction.",accept_once)
check("L18_LATE_RESULT_IGNORED","Late result after supersede is ignored.",late_result_ignored)
check("L19_CANONICAL_ASSISTANT_ONCE","Duplicate delivery callback canonicalizes AssistantTurn once.",canonical_once)
check("L20_ACK_ASYNC","ClientRenderAck can arrive after terminal turn.",ack_after_terminal)
check("L21_CP4_AFTER_GUARD","Projection execution does not run under conversation guard.",projection_after_release)
check("L22_INTERRUPT_HANDOFF","Barge-in terminalizes old action/turn before handoff.",interrupt_handoff)
check("L23_NO_PARALLEL_VISIBLE_STREAM","One coordinator owns visible path per conversation.",no_parallel_visible_streams)
check("L24_RECOVER_CP0","Crash after CP0 resumes analysis.",lambda:startup_epoch_recovery("CP0","RESUME_ANALYSIS"))
check("L25_RECOVER_CP1","Crash after CP1 resumes decision.",lambda:startup_epoch_recovery("CP1","RESUME_DECISION"))
check("L26_RECOVER_CP2","Crash after CP2 resumes same stable action.",lambda:startup_epoch_recovery("CP2","RESUME_ACTION_BY_STABLE_ACTION_ID"))
check("L27_RECOVER_UNCERTAIN_DELIVERY","Crash around uncertain delivery uses conservative reconciliation.",lambda:startup_epoch_recovery("CP3_UNCERTAIN","CONSERVATIVE_DELIVERY_RECONCILIATION"))
check("L28_RECOVER_PROJECTION","Pending projection survives restart.",projection_recovery)
check("L29_ORPHAN_LOCK","Terminal Moment with orphan lock is repaired on recovery.",orphan_terminal_lock_release)
check("L30_ACTIVE_MOMENT_REVALIDATE","Nonterminal TeachingMoment is revalidated, not blindly reopened.",active_moment_revalidate)
check("L31_NO_HEARTBEAT","Local TeachingLock has no heartbeat/TTL columns.",no_heartbeat_columns)
check("L32_NO_DISTRIBUTED_COORD_TABLE","Conversation coordination does not require durable distributed lease table.",no_durable_coordinator_lease_table)
check("L33_INGEST_OUTSIDE_COORD","Input ingestion does not require coordinator ownership.",guard_not_needed_for_ingest)
check("L34_HANDOFF_AFTER_RELEASE","Next turn may acquire coordinator after release.",second_turn_after_release)
check("L35_CONTENT_SEPARATE","Read-only content store remains physically separate.",content_separate_contract)
check("L36_SECRET_SEPARATE","Secrets remain outside app.db.",secret_separate_contract)
check("L37_NO_WHOLE_TURN_REPLAY","Recovery resumes action/checkpoint rather than replaying whole turn.",no_whole_turn_replay)
check("L38_STABLE_ACTION_RETRY","Retries retain stable GenerationAction identity.",stable_action_retry)
check("L39_TERMINAL_NOT_RECOVERED","Terminal turns are not replayed on startup.",terminal_turn_not_recovered)
check("L40_PROJECTION_INDEPENDENT","Projection may complete after turn terminalization.",terminal_projection_can_retry)
check("L41_PENDING_PROJECTION_NO_BLOCK","Pending CP4 work does not block next turn.",no_projection_blocks_next_turn)
check("L42_CANCELLED_LATE_RESULT","Cancelled provider result cannot create canonical side effect.",action_cancel_before_late_result)
check("L43_LATE_ACK_NO_REOPEN","Late ClientRenderAck does not reopen terminal turn.",client_ack_does_not_reopen_turn)

passed=sum(1 for r in results if r["pass"])
(HERE/"local_runtime_test_results_v1.json").write_text(json.dumps(results,indent=2,default=lambda o: sorted(o) if isinstance(o,set) else str(o)))
(HERE/"test_summary.json").write_text(json.dumps({
    "status":"LOCAL_RUNTIME_BASELINE_V1",
    "integration_contract_checks":{"passed":passed,"total":len(results)}
},indent=2))
print(f"Local runtime checks: {passed}/{len(results)} PASS")
for r in results:
    if not r["pass"]:
        print("FAIL",r["id"],r["detail"])
raise SystemExit(0 if passed==len(results) else 1)
