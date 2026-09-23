-- 0015_planner_records.sql — Phase 8 P8-0: CP2's durable half — the four
-- docs/DATA_MODEL.md §14 planner records (TASK-OPI-64c88704-….7 ①).
--
-- Four tables land here, and nothing else. This migration is DDL + vocabulary
-- only — no backfill, no rebuild, no row is created by it. The write face
-- that fills them belongs to this same slice: elc.platform.db.planner_store
-- (every SQL statement) behind the SQL-free port
-- elc.planner.records.PlannerRecordStore. Nothing earlier in the chain is
-- touched: 0001–0014 are byte-identical (0014's header comment included —
-- this cut does not edit that file) and every table they created keeps its
-- shape.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §14  "Planner Data" (lines 800–918) — the four fenced
--                           blocks this file turns into tables:
--                             PlannerEvaluation      (lines 832–843), eight
--                               columns in this order — planner_evaluation_id /
--                               decision_cycle_id / frontier_candidate_ids[] /
--                               ranked_candidate_ids[] / factor_trace /
--                               planner_version / policy_profile_version /
--                               created_at
--                             PlannerDecision        (lines 845–858) plus its
--                               two-word Decision block (lines 859–862):
--                               SELECT / NO_TARGET — seven columns
--                             PlannerExecutionStatus (lines 864–875, whose
--                               fenced block interleaves its four status words
--                               with the column list): decision_cycle_id /
--                               status / error_code? / created_at
--                             RuntimeDecisionOutcome (lines 877–887, the same
--                               interleaved shape): turn_id /
--                               decision_cycle_id? / outcome / reason_codes[] /
--                               created_at
--                             and line 889, the sentence the coupling is:
--                               "Runtime degradation is not a PlannerDecision."
--   docs/RUNTIME_ARCHITECTURE.md §6 CP2 (lines 183–212) — the commit point
--                           these rows are: the success path is exactly
--                           DecisionCycle / PlannerExecutionStatus=SUCCEEDED /
--                           PlannerEvaluation / PlannerDecision, the failure
--                           path is PlannerExecutionStatus=DEGRADED/FAILED/
--                           UNAVAILABLE + RuntimeDecisionOutcome=
--                           DEGRADED_NO_AUTOMATIC_TEACHING with **no**
--                           PlannerDecision ("不伪造 PlannerDecision"), and
--                           the unit is "尽量同短事务原子提交". p8-0 is the
--                           Planner half of that unit; the teaching half
--                           (TeachingMoment / TeachingLockLease /
--                           GenerationActionIntent) is p8-1's and is not in
--                           this file.
--   docs/RUNTIME_ARCHITECTURE.md §4 steps 9A–9C (lines 99–108) — the three
--                           outcomes a cycle's rows record: 9A a degraded
--                           status with no synthetic decision, 9B NO_TARGET,
--                           9C SELECT → Teaching Gate.
--   docs/RUNTIME_ARCHITECTURE.md §23 (lines 682–702) — the crash windows the
--                           write face's replay rules serve: "Crash after CP1"
--                           continues from DecisionCycle/Planner without
--                           repeating Evidence, and "Crash after CP2" never
--                           creates a second Moment — on the Planner side, a
--                           re-entry of one cycle writes no second row.
--   docs/DATA_MODEL.md §26.1  migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27    the physical form (column type, JSON encoding,
--                           index names) is the implementation's; the element
--                           shapes are declared in elc.platform.types
--                           (PlannerEvaluationRecord / PlannerDecision /
--                           PlannerExecutionStatusRecord /
--                           RuntimeDecisionOutcome) and read back by
--                           elc.planner.records.
--
-- ---------------------------------------------------------------------------
-- Physical decisions (each minimal, no silent widening)
--
--   * **Keys.** planner_evaluation PK = planner_evaluation_id;
--     planner_decision PK = planner_decision_id; planner_execution_status
--     PK = decision_cycle_id (§14 gives that block no independent id: the
--     status *is* the cycle's execution health, one row per cycle);
--     runtime_decision_outcome PK = turn_id (same shape — §14 gives it no
--     independent id, and RUNTIME_ARCHITECTURE §4 step 9A defines the
--     outcome at the **turn** level). No other UNIQUE and no index: §14
--     names no second key anywhere in this section. "One decision per
--     cycle" is therefore carried by the write face (the kernel mints
--     ``pd-<decision_cycle_id>`` and the CP2 unit replays instead of
--     re-deciding), not by a second unique index this document does not
--     ask for.
--   * **Foreign keys.** planner_evaluation / planner_decision /
--     planner_execution_status reference decision_cycle(decision_cycle_id),
--     the 0007 ``gate_decision`` precedent — every §14 row belongs to a
--     cycle that exists. planner_decision.planner_evaluation_id references
--     planner_evaluation(planner_evaluation_id) (the decision names the
--     evaluation it was made from, §14 line 855). runtime_decision_outcome
--     references turn_record(turn_id) (0007/0012/0013's turn identity
--     column). **selected_candidate_id carries no FK**: §14's candidates
--     are a computed set (the same section's TargetCandidate block is not a
--     table), so there is no durable row to point at.
--   * **The two interleaved blocks.** §14's PlannerExecutionStatus and
--     RuntimeDecisionOutcome blocks mix their vocabulary *into* the column
--     list (``status`` is followed by four indented words, ``outcome`` by
--     two). This migration reads each block's **column list** and its
--     **vocabulary** and freezes both: CHECK (status IN (SUCCEEDED,
--     DEGRADED, FAILED, UNAVAILABLE)) and CHECK (outcome IN (NORMAL,
--     DEGRADED_NO_AUTOMATIC_TEACHING)) carry exactly those words, none
--     added, none dropped — the same two sets the Gate-6 pin holds the
--     type system to (tests/architecture/test_gate_6_planner_separation.py),
--     and the same words the companion Decision CHECK carries (SELECT /
--     NO_TARGET).
--   * **JSON columns.** ``frontier_candidate_ids[]``, ``ranked_candidate_ids[]``
--     and ``reason_codes[]`` are bracketed list columns, and ``factor_trace``
--     is a trace of lines; all four land as TEXT carrying a deterministic
--     JSON **array** document — one encoding, reused from
--     elc/teaching/store.py's ``_array_document`` (``json.dumps(list(...),
--     sort_keys=True, separators=(",", ":"))``) rather than a second
--     spelling. ``factor_trace`` is written in that same array form: §14
--     gives the column no bracketed spelling and this migration invents
--     none, while the value it carries is a sequence (the evaluation's
--     trace), which is what a JSON array is. See elc/planner/records.py for
--     the canonical-column ↔ implementation-field map, which lives in
--     exactly one place. Revisit: canonical rewrites ``factor_trace``'s
--     spelling or shape (``factor_trace[]``, or a form that is not an array
--     of lines) and the durable rows' encoding has to follow (the reading is
--     registered in elc/planner/records.py judgement 9).
--   * **Nullability.** ``selected_candidate_id?`` / ``no_target_reason?`` /
--     ``error_code?`` / ``decision_cycle_id?`` (the RuntimeDecisionOutcome
--     one) are the columns §14 marks optional, and they are nullable here.
--     Nothing else is: every other column of the four blocks is written
--     ``NOT NULL`` because §14 lists it without a ``?`` — **keys excepted**.
--     The four primary keys are bare ``TEXT PRIMARY KEY``, the 0010–0015
--     convention: a SQLite rowid table reports ``notnull=0`` for a
--     ``TEXT PRIMARY KEY`` column whatever the DDL says, so a ``NOT NULL``
--     beside a key would be both redundant and unreadable through
--     ``PRAGMA table_info`` (a key's nullability is the key's business). The
--     SELECT/NO_TARGET complementarity (a SELECT names a candidate; a
--     NO_TARGET names a reason) is a property of §14's decision vocabulary
--     and is enforced by the write face — a CHECK here would have to spell
--     the two decision words a second time, and §14's block states no such
--     constraint.
--   * **The reverse reference stays plain data.** decision_cycle.
--     planner_decision_id (0006) keeps its shape — no FK is added and the
--     table is not rebuilt. Three reasons, each checkable: (a) 0006's own
--     comment says the back-reference was left without a FK only because
--     "those tables do not exist yet", and the write face closes that gap
--     **transactionally** — the pointer and the decision row are committed
--     by one short transaction, so a partial commit cannot leave a
--     dangling pointer; (b) an FK would mean rebuilding decision_cycle,
--     which would rewrite 0007's legacy backfill and the three writers
--     that land on that table today — a blast radius out of proportion to
--     the guarantee, which (a) already provides; (c) the same-document
--     precedent 0002's ``turn_record.active_decision_cycle_id`` is plain
--     data under exactly this argument. Revisit: if a writer outside the
--     CP2 unit ever has to move that pointer, or if a future cut wants the
--     schema itself to refuse a dangling pointer, the question is re-opened
--     (registered in elc/platform/db/planner_store.py).
--   * **created_at.** All four tables carry it as TEXT, stamped by the
--     store at the instant the unit commits — the sibling adapters' clock
--     convention: the durable row carries the stamp, and the in-memory
--     records follow it **unevenly**, which is registered rather than
--     smoothed over. The three records minted before this cut carry no
--     clock; ``PlannerEvaluationRecord``, the row-shaped record this cut
--     mints for §14's first block, **does** carry ``created_at`` (the
--     exception is registered in elc/platform/types.py and in
--     elc/planner/records.py's judgement 6).
-- ---------------------------------------------------------------------------
-- 1. planner_evaluation — §14 lines 832–843
CREATE TABLE IF NOT EXISTS planner_evaluation (
    planner_evaluation_id  TEXT PRIMARY KEY,
    decision_cycle_id      TEXT NOT NULL
        REFERENCES decision_cycle(decision_cycle_id),
    frontier_candidate_ids TEXT NOT NULL,
    ranked_candidate_ids   TEXT NOT NULL,
    factor_trace           TEXT NOT NULL,
    planner_version        TEXT NOT NULL,
    policy_profile_version TEXT NOT NULL,
    created_at             TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 2. planner_decision — §14 lines 845–862
CREATE TABLE IF NOT EXISTS planner_decision (
    planner_decision_id   TEXT PRIMARY KEY,
    decision_cycle_id     TEXT NOT NULL
        REFERENCES decision_cycle(decision_cycle_id),
    decision              TEXT NOT NULL
        CHECK (decision IN ('SELECT', 'NO_TARGET')),
    selected_candidate_id TEXT,
    no_target_reason      TEXT,
    planner_evaluation_id TEXT NOT NULL
        REFERENCES planner_evaluation(planner_evaluation_id),
    created_at            TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 3. planner_execution_status — §14 lines 864–875
-- The four CHECK words are that block's indented status vocabulary, verbatim.
CREATE TABLE IF NOT EXISTS planner_execution_status (
    decision_cycle_id TEXT PRIMARY KEY
        REFERENCES decision_cycle(decision_cycle_id),
    status            TEXT NOT NULL
        CHECK (status IN ('SUCCEEDED', 'DEGRADED', 'FAILED', 'UNAVAILABLE')),
    error_code        TEXT,
    created_at        TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 4. runtime_decision_outcome — §14 lines 877–887
-- The two CHECK words are that block's indented outcome vocabulary, verbatim;
-- line 889 ("Runtime degradation is not a PlannerDecision.") is the rule the
-- write face serves by persisting this row **instead of** a decision.
CREATE TABLE IF NOT EXISTS runtime_decision_outcome (
    turn_id           TEXT PRIMARY KEY
        REFERENCES turn_record(turn_id),
    decision_cycle_id TEXT
        REFERENCES decision_cycle(decision_cycle_id),
    outcome           TEXT NOT NULL
        CHECK (outcome IN ('NORMAL', 'DEGRADED_NO_AUTOMATIC_TEACHING')),
    reason_codes      TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '15')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '15')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
