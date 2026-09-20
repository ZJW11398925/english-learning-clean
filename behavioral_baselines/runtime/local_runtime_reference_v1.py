
from __future__ import annotations
import sqlite3, threading, contextlib, uuid

TERMINAL_TURN_STATES={"COMPLETED","FAILED","CANCELLED"}

class RuntimeInvariantError(RuntimeError):
    pass

class LocalRuntime:
    """
    Reference physical profile, not production framework code.

    Key property:
      logical runtime semantics are preserved without distributed infrastructure.
    """
    def __init__(self, db_path=":memory:"):
        self.conn=sqlite3.connect(db_path, isolation_level=None)
        self.conn.row_factory=sqlite3.Row
        self._mutexes={}
        self._mutexes_guard=threading.Lock()
        self._held=set()
        self._init_db()
        self.runtime_epoch=self._next_epoch()

    def _init_db(self):
        c=self.conn
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=5000")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS runtime_meta(
          key TEXT PRIMARY KEY,
          value INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS input_envelope(
          input_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          payload_hash TEXT,
          status TEXT NOT NULL DEFAULT 'DURABLE'
        );

        CREATE TABLE IF NOT EXISTS interrupt_request(
          interrupt_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          active_turn_id TEXT,
          active_action_id TEXT,
          new_input_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PENDING',
          FOREIGN KEY(new_input_id) REFERENCES input_envelope(input_id)
        );

        CREATE TABLE IF NOT EXISTS turn_record(
          turn_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          state TEXT NOT NULL,
          outcome TEXT,
          owner_epoch INTEGER NOT NULL,
          current_action_id TEXT,
          checkpoint TEXT
        );

        CREATE TABLE IF NOT EXISTS user_turn(
          user_turn_id TEXT PRIMARY KEY,
          turn_id TEXT NOT NULL UNIQUE,
          input_id TEXT NOT NULL UNIQUE,
          content TEXT,
          FOREIGN KEY(turn_id) REFERENCES turn_record(turn_id),
          FOREIGN KEY(input_id) REFERENCES input_envelope(input_id)
        );

        CREATE TABLE IF NOT EXISTS gate_decision(
          gate_decision_id TEXT PRIMARY KEY,
          turn_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          FOREIGN KEY(turn_id) REFERENCES turn_record(turn_id)
        );

        CREATE TABLE IF NOT EXISTS teaching_moment(
          moment_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          turn_id TEXT NOT NULL,
          state TEXT NOT NULL,
          focus_target TEXT NOT NULL,
          FOREIGN KEY(turn_id) REFERENCES turn_record(turn_id)
        );

        CREATE TABLE IF NOT EXISTS active_teaching_lock(
          conversation_id TEXT PRIMARY KEY,
          moment_id TEXT NOT NULL UNIQUE,
          state_version INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(moment_id) REFERENCES teaching_moment(moment_id)
        );

        CREATE TABLE IF NOT EXISTS generation_action(
          action_id TEXT PRIMARY KEY,
          turn_id TEXT NOT NULL,
          moment_id TEXT,
          state TEXT NOT NULL,
          accepted_attempt_id TEXT,
          owner_epoch INTEGER NOT NULL,
          FOREIGN KEY(turn_id) REFERENCES turn_record(turn_id)
        );

        CREATE TABLE IF NOT EXISTS provider_attempt(
          attempt_id TEXT PRIMARY KEY,
          action_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          state TEXT NOT NULL,
          UNIQUE(action_id, ordinal),
          FOREIGN KEY(action_id) REFERENCES generation_action(action_id)
        );

        CREATE TABLE IF NOT EXISTS server_delivery(
          delivery_id TEXT PRIMARY KEY,
          action_id TEXT NOT NULL UNIQUE,
          state TEXT NOT NULL,
          delivered_prefix TEXT,
          certainty TEXT,
          FOREIGN KEY(action_id) REFERENCES generation_action(action_id)
        );

        CREATE TABLE IF NOT EXISTS assistant_turn(
          assistant_turn_id TEXT PRIMARY KEY,
          turn_id TEXT NOT NULL UNIQUE,
          action_id TEXT NOT NULL UNIQUE,
          canonical_content TEXT,
          outcome TEXT NOT NULL,
          FOREIGN KEY(turn_id) REFERENCES turn_record(turn_id),
          FOREIGN KEY(action_id) REFERENCES generation_action(action_id)
        );

        CREATE TABLE IF NOT EXISTS client_render_ack(
          ack_id TEXT PRIMARY KEY,
          action_id TEXT NOT NULL,
          rendered_extent TEXT NOT NULL,
          FOREIGN KEY(action_id) REFERENCES generation_action(action_id)
        );

        CREATE TABLE IF NOT EXISTS projection_job(
          projection_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          source_turn_id TEXT NOT NULL,
          projection_type TEXT NOT NULL,
          state TEXT NOT NULL,
          owner_epoch INTEGER,
          source_version INTEGER NOT NULL DEFAULT 1,
          UNIQUE(source_turn_id, projection_type)
        );
        """)

    def _next_epoch(self):
        row=self.conn.execute("SELECT value FROM runtime_meta WHERE key='runtime_epoch'").fetchone()
        n=(row["value"] if row else 0)+1
        self.conn.execute(
            "INSERT INTO runtime_meta(key,value) VALUES('runtime_epoch',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",(n,)
        )
        return n

    def _mutex(self,conversation_id):
        with self._mutexes_guard:
            return self._mutexes.setdefault(conversation_id, threading.Lock())

    @contextlib.contextmanager
    def conversation_guard(self,conversation_id,blocking=True):
        m=self._mutex(conversation_id)
        acquired=m.acquire(blocking)
        if not acquired:
            raise RuntimeInvariantError("conversation coordinator already active")
        self._held.add(conversation_id)
        try:
            yield
        finally:
            self._held.discard(conversation_id)
            m.release()

    def is_guard_held(self,conversation_id):
        return conversation_id in self._held

    def ingest_input(self,input_id,conversation_id,payload_hash=None,
                     active_turn_id=None,active_action_id=None):
        """
        Ingestion deliberately does NOT require conversation_guard.
        This lets a new user input durably request interruption while old output owns the guard.
        """
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            before=self.conn.total_changes
            self.conn.execute(
                "INSERT OR IGNORE INTO input_envelope(input_id,conversation_id,payload_hash) VALUES(?,?,?)",
                (input_id,conversation_id,payload_hash)
            )
            inserted=self.conn.total_changes>before
            if active_turn_id:
                iid="irq:"+input_id
                self.conn.execute(
                    "INSERT OR IGNORE INTO interrupt_request("
                    "interrupt_id,conversation_id,active_turn_id,active_action_id,new_input_id"
                    ") VALUES(?,?,?,?,?)",
                    (iid,conversation_id,active_turn_id,active_action_id,input_id)
                )
            self.conn.execute("COMMIT")
            return inserted
        except:
            self.conn.execute("ROLLBACK")
            raise

    def commit_cp0(self,turn_id,conversation_id,input_id,user_turn_id,content):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO turn_record(turn_id,conversation_id,state,owner_epoch,checkpoint) "
                "VALUES(?,?,?,?,?)",
                (turn_id,conversation_id,"USER_COMMITTED",self.runtime_epoch,"CP0")
            )
            self.conn.execute(
                "INSERT INTO user_turn(user_turn_id,turn_id,input_id,content) VALUES(?,?,?,?)",
                (user_turn_id,turn_id,input_id,content)
            )
            self.conn.execute("COMMIT")
        except:
            self.conn.execute("ROLLBACK")
            raise

    def commit_cp2_open(self,turn_id,conversation_id,gate_id,moment_id,focus_target,action_id,
                        fail_after=None):
        """
        Atomically commits Gate ALLOW + TeachingMoment + active TeachingLock + first action.
        fail_after is only for integration testing rollback semantics.
        """
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO gate_decision(gate_decision_id,turn_id,decision) VALUES(?,?,?)",
                (gate_id,turn_id,"ALLOW")
            )
            if fail_after=="gate": raise RuntimeError("injected")
            self.conn.execute(
                "INSERT INTO teaching_moment(moment_id,conversation_id,turn_id,state,focus_target) "
                "VALUES(?,?,?,?,?)",
                (moment_id,conversation_id,turn_id,"OPENING",focus_target)
            )
            if fail_after=="moment": raise RuntimeError("injected")
            self.conn.execute(
                "INSERT INTO active_teaching_lock(conversation_id,moment_id,state_version) VALUES(?,?,1)",
                (conversation_id,moment_id)
            )
            if fail_after=="lock": raise RuntimeError("injected")
            self.conn.execute(
                "INSERT INTO generation_action(action_id,turn_id,moment_id,state,owner_epoch) "
                "VALUES(?,?,?,?,?)",
                (action_id,turn_id,moment_id,"PLANNED",self.runtime_epoch)
            )
            self.conn.execute(
                "UPDATE turn_record SET state='DECISION_COMMITTED',checkpoint='CP2',current_action_id=? "
                "WHERE turn_id=?",(action_id,turn_id)
            )
            if fail_after=="action": raise RuntimeError("injected")
            self.conn.execute("COMMIT")
        except:
            self.conn.execute("ROLLBACK")
            raise

    def release_teaching_lock_terminal(self,moment_id,outcome="COMPLETED"):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row=self.conn.execute(
                "SELECT conversation_id FROM teaching_moment WHERE moment_id=?",(moment_id,)
            ).fetchone()
            if not row:
                raise RuntimeInvariantError("missing moment")
            self.conn.execute(
                "UPDATE teaching_moment SET state='TEACHING_TERMINAL' WHERE moment_id=?",(moment_id,)
            )
            self.conn.execute(
                "DELETE FROM active_teaching_lock WHERE moment_id=?",(moment_id,)
            )
            self.conn.execute("COMMIT")
        except:
            self.conn.execute("ROLLBACK")
            raise

    def create_provider_attempt(self,action_id):
        row=self.conn.execute(
            "SELECT COALESCE(MAX(ordinal),0)+1 n FROM provider_attempt WHERE action_id=?",(action_id,)
        ).fetchone()
        ordinal=row["n"]
        attempt_id=f"{action_id}:p{ordinal}"
        self.conn.execute(
            "INSERT INTO provider_attempt(attempt_id,action_id,ordinal,state) VALUES(?,?,?,?)",
            (attempt_id,action_id,ordinal,"STARTED")
        )
        return attempt_id

    def provider_call_guard(self):
        if self.conn.in_transaction:
            raise RuntimeInvariantError("external provider call inside SQL transaction")
        return "EXTERNAL_CALL_ALLOWED"

    def accept_provider_result(self,action_id,attempt_id):
        """
        Exactly one accepted ProviderAttempt for an action.
        Superseded/cancelled actions ignore late callback.
        """
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            action=self.conn.execute(
                "SELECT state,accepted_attempt_id FROM generation_action WHERE action_id=?",(action_id,)
            ).fetchone()
            if not action:
                raise RuntimeInvariantError("missing action")
            if action["state"] in {"CANCELLED","SUPERSEDED","TERMINAL"}:
                self.conn.execute("ROLLBACK")
                return "IGNORED_LATE_RESULT"
            if action["accepted_attempt_id"]:
                self.conn.execute("ROLLBACK")
                return "DUPLICATE_IGNORED"
            self.conn.execute(
                "UPDATE generation_action SET accepted_attempt_id=?,state='ACCEPTED' WHERE action_id=?",
                (attempt_id,action_id)
            )
            self.conn.execute(
                "UPDATE provider_attempt SET state='ACCEPTED' WHERE attempt_id=?",(attempt_id,)
            )
            self.conn.execute("COMMIT")
            return "ACCEPTED"
        except:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise

    def cancel_action(self,action_id,state="CANCELLED"):
        self.conn.execute(
            "UPDATE generation_action SET state=? WHERE action_id=?",(state,action_id)
        )

    def canonicalize_delivery(self,turn_id,action_id,delivery_id,prefix,outcome="REPLIED_FULL"):
        """
        action_id and turn_id uniqueness provide canonical exactly-once side effect.
        """
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO server_delivery("
                "delivery_id,action_id,state,delivered_prefix,certainty"
                ") VALUES(?,?,?,?,?)",
                (delivery_id,action_id,"SENT_COMPLETE",prefix,"SERVER_SENT_UNCONFIRMED")
            )
            before=self.conn.total_changes
            self.conn.execute(
                "INSERT OR IGNORE INTO assistant_turn("
                "assistant_turn_id,turn_id,action_id,canonical_content,outcome"
                ") VALUES(?,?,?,?,?)",
                ("a:"+turn_id,turn_id,action_id,prefix,outcome)
            )
            committed=self.conn.total_changes>before
            self.conn.execute(
                "UPDATE turn_record SET state='COMPLETED',outcome=?,checkpoint='CP3' WHERE turn_id=?",
                (outcome,turn_id)
            )
            self.conn.execute(
                "UPDATE generation_action SET state='TERMINAL' WHERE action_id=?",(action_id,)
            )
            self.conn.execute("COMMIT")
            return committed
        except:
            self.conn.execute("ROLLBACK")
            raise

    def record_client_ack(self,ack_id,action_id,extent):
        self.conn.execute(
            "INSERT OR IGNORE INTO client_render_ack(ack_id,action_id,rendered_extent) VALUES(?,?,?)",
            (ack_id,action_id,extent)
        )

    def enqueue_projection(self,projection_id,conversation_id,turn_id,projection_type):
        self.conn.execute(
            "INSERT OR IGNORE INTO projection_job("
            "projection_id,conversation_id,source_turn_id,projection_type,state,source_version"
            ") VALUES(?,?,?,?,?,1)",
            (projection_id,conversation_id,turn_id,projection_type,"PENDING")
        )

    def run_projection(self,projection_id):
        row=self.conn.execute(
            "SELECT conversation_id,state FROM projection_job WHERE projection_id=?",(projection_id,)
        ).fetchone()
        if not row:
            raise RuntimeInvariantError("missing projection")
        if self.is_guard_held(row["conversation_id"]):
            raise RuntimeInvariantError("CP4 projection cannot require active conversation guard")
        self.conn.execute(
            "UPDATE projection_job SET state='COMPLETED',owner_epoch=? WHERE projection_id=?",
            (self.runtime_epoch,projection_id)
        )

    def terminalize_old_turn_for_interrupt(self,turn_id,action_id):
        self.cancel_action(action_id,"SUPERSEDED")
        self.conn.execute(
            "UPDATE turn_record SET state='CANCELLED',outcome='CANCELLED_BY_USER',checkpoint='CP3' "
            "WHERE turn_id=?",(turn_id,)
        )
        self.conn.execute(
            "UPDATE interrupt_request SET status='HANDOFF_READY' WHERE active_turn_id=?",(turn_id,)
        )

    def recovery_plan(self):
        """
        No heartbeat/TTL. A new process epoch fences work from an older crashed process.
        """
        plan=[]
        for r in self.conn.execute(
            "SELECT * FROM turn_record WHERE state NOT IN ('COMPLETED','FAILED','CANCELLED')"
        ):
            if r["owner_epoch"]>=self.runtime_epoch:
                continue
            cp=r["checkpoint"]
            if cp=="CP0":
                action="RESUME_ANALYSIS"
            elif cp=="CP1":
                action="RESUME_DECISION"
            elif cp=="CP2":
                action="RESUME_ACTION_BY_STABLE_ACTION_ID"
            elif cp=="CP3_UNCERTAIN":
                action="CONSERVATIVE_DELIVERY_RECONCILIATION"
            else:
                action="REVALIDATE_NONTERMINAL_TURN"
            plan.append({"kind":"TURN","id":r["turn_id"],"action":action})

        for r in self.conn.execute(
            "SELECT p.* FROM projection_job p WHERE state='PENDING'"
        ):
            plan.append({"kind":"PROJECTION","id":r["projection_id"],"action":"REVALIDATE_AND_RUN"})

        for r in self.conn.execute("""
            SELECT l.conversation_id,l.moment_id,m.state
            FROM active_teaching_lock l JOIN teaching_moment m ON m.moment_id=l.moment_id
        """):
            if r["state"]=="TEACHING_TERMINAL":
                plan.append({"kind":"LOCK","id":r["moment_id"],"action":"RELEASE_ORPHAN_LOCK"})
            else:
                plan.append({"kind":"TEACHING","id":r["moment_id"],"action":"REVALIDATE_ACTIVE_MOMENT"})
        return sorted(plan,key=lambda x:(x["kind"],x["id"]))
