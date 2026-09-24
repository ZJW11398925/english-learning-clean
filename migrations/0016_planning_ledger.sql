-- 0016_planning_ledger.sql — Phase 8 P8-3: the PlanningLedger's durable half
-- (TASK-OPI-6d40862d-….9 ①②③).
--
-- Three tables land here, and nothing else. This migration is DDL + the five
-- §20 event words only — no backfill, no rebuild, no row is created by it.
-- The write face that fills them belongs to this same slice:
-- elc.planner.ledger_store (every SQL statement, one short transaction per
-- event) over the **unchanged** pure core elc.planner.ledger. Nothing earlier
-- in the chain is touched: 0001–0015 are byte-identical and every table they
-- created keeps its shape. The BF-05 deletion walk is part of this same
-- change, not a later one: elc/deletion/types.py lists all three tables in
-- LEARNING_TARGET_SWEPT_TABLES and LEARNING_HISTORY_SWEPT_TABLES (and in
-- SWEPT_TABLES), and elc/deletion/store.py carries one SELECT and one DELETE
-- literal per table — the condition
-- ``elc.planner.ledger.PLANNING_LEDGER_STORAGE_REVISIT`` named before this
-- cut ("land the table in the same change *and* its statements in the BF-05
-- deletion walk") is therefore satisfied in one change.
--
-- Authority map (canonical first; every column below is verbatim from the
-- cited set, and this migration adds no column of its own):
--   docs/DATA_MODEL.md §14 "### PlanningLedger" (lines 891–918) — the fenced
--                           block this file turns into tables, under the
--                           section's own first sentence — verbatim
--                           "不记录 mastery。": no mastery column exists here,
--                           and none may be added by a later cut without a
--                           canonical revision. The block's three parts:
--                             the per-key row — its key line
--                               ``target/family last_selected_at`` plus
--                               last_presented_at / teaching_exposure_counts
--                               / probe_counts / review_offers /
--                               recent_skips/rejections / overexposure_window
--                               (table 1);
--                             ``coverage_obligations[]`` — eleven fields, the
--                               four ``?`` ones optional (table 2);
--                             ``coverage_debt_rollups`` /
--                               ``recent_target_families`` / ``version`` —
--                               the three row-independent columns (see
--                               "Not materialized" below).
--   docs/RUNTIME_ARCHITECTURE.md §20 (lines 588–598) — the five event words
--                           candidate_selected / teaching_presented /
--                           hint_presented / reveal_presented / user_skip,
--                           and the two sentences the log exists to make
--                           checkable: "SELECT != exposure" and
--                           "CoverageDebt 不因 selection 自动偿还" (both are
--                           behaviour in elc.planner.ledger's EVENT_EFFECTS;
--                           the CHECK on table 3's ``event`` column is those
--                           five words, none added, none dropped).
--   docs/DATA_MODEL.md §1.3  append-first: table 3 is a log — a new event is a
--                           new row with a new ``event_id``, never a rewrite
--                           of an earlier one (no UPDATE or DELETE statement
--                           names this table anywhere in src/).
--   docs/DATA_MODEL.md §26   "some PlanningLedger rollups" are a **rebuildable
--                           projection**, and a rebuildable projection is
--                           never the only source of truth — which is why the
--                           two rollup-shaped columns are not materialized
--                           here (below).
--   docs/DATA_MODEL.md §26.1 migrations bump schema_version explicitly.
--   docs/DATA_MODEL.md §27   the physical form (column type, JSON encoding,
--                           index names) is the implementation's; the element
--                           shapes are declared in elc/planner/ledger.py.
--   behavioral_baselines/security/SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md
--                           line 87 lists "PlanningLedger user history" under
--                           LEARNING_PRIVATE and line 747 lists "related
--                           PlanningLedger history" under the LEARNING_TARGET
--                           scope. Both legs land in this same change (see the
--                           deletion walk named in the header above); a table
--                           without them is exactly what the pre-cut
--                           PLANNING_LEDGER_STORAGE_REVISIT refused to land.
--
-- ---------------------------------------------------------------------------
-- Physical decisions (each minimal, no silent widening)
--
--   * **The row key: one column plus the declared key face.** §14's key line
--     is ``target/family last_selected_at`` — the row's key is a target **or**
--     a family. This table keeps **one** key column, ``ledger_key``, with the
--     declared discriminator ``ledger_key_type`` (two words, CHECKed here
--     because the migration is what freezes them). The alternative a reader
--     might expect — a composite ``(ledger_key_type, ledger_key_id)`` key — is
--     **refused on purpose**, and the argument is checkable in the pure core:
--     ``TargetLedgerRow.target_key`` is one string and ``PlanningLedger.rows``
--     is a mapping keyed by it, so a composite durable key would let one id
--     exist twice (once per face) while the core's mapping can carry it once —
--     two durable rows folding onto one core key, which is a silent loss. With
--     the single key the collision is unrepresentable, the decode is 1:1, and
--     the *type* column still answers the one question the key cannot: which
--     face the row belongs to (the LEARNING_TARGET walk reads exactly that
--     column, so a family row whose id spells a target's is not swept by a
--     target's deletion).
--   * **Foreign keys.** ``planning_ledger_event.ledger_key`` references
--     ``planning_ledger(ledger_key)`` — an event belongs to a row, the 0012
--     ``review_event`` → ``schedule_item`` precedent, and the core's own shape
--     (``TargetLedgerRow`` *is* its log; ``record`` opens a row when the key
--     has none). ``coverage_obligation`` carries **no** FK to
--     ``planning_ledger``: the core holds rows and obligations as two
--     independent collections, and a debt can exist for a target that was
--     never presented (``accrue`` is called on an obligation, not on a row;
--     ``governing_obligation_of`` reads obligations whatever rows exist), so
--     an FK would refuse a state the core can produce. No other FK: §14 names
--     no reference from this section to another table, and a target /
--     family / goal id is a computed key with no durable row to point at (the
--     0015 ``selected_candidate_id`` argument).
--   * **Nullability.** ``last_selected_at`` / ``last_presented_at`` are
--     nullable because they are functions of the log and "no selection yet" /
--     "never presented" is their honest value (the core returns ``None``) —
--     an empty-string sentinel would be an instant that never happened.
--     ``overexposure_window`` is nullable for the same reason: the core's
--     ``LedgerWindow | None`` says a row without its own window falls back to
--     the declared look-back window, and NULL is that "no own window" (the
--     0012 ``next_review_window_*`` optionality, one column instead of two —
--     see the JSON note). The four ``?`` columns of ``coverage_obligations[]``
--     (``goal_id`` / ``pause_reason`` / ``last_served_at`` /
--     ``last_engaged_at``) are nullable; every other column of the three
--     tables is NOT NULL because §14 lists it without a ``?`` — **keys
--     excepted**: the three primary keys are bare ``TEXT PRIMARY KEY``, the
--     0010–0015 convention (a SQLite rowid table reports ``notnull=0`` for a
--     ``TEXT PRIMARY KEY`` however the DDL is written).
--   * **JSON columns.** ``overexposure_window`` is one column carrying a
--     deterministic JSON **object** document (``{"end": …, "start": …}``,
--     ``json.dumps(..., sort_keys=True, separators=(",", ":"))`` — the same
--     one encoding 0015 reuses from elc/teaching/store.py's array document,
--     applied to the object shape here). §14 names **one** column; splitting
--     it into ``overexposure_window_start`` / ``_end`` would invent two column
--     names the document does not carry. Revisit: canonical rewrites the
--     column's spelling or shape (``overexposure_window[]``, or two names) and
--     the durable rows' encoding has to follow.
--   * **``recent_skips/rejections`` is one column, named ``recent_skips``.**
--     §14's slash spelling is the same "or" §14 uses for ``target/family``,
--     and the core has exactly one fact behind it: ``TargetLedgerRow.
--     recent_skips`` counts ``user_skip`` events, whose EVENT_EFFECTS
--     registration states the identity in one line — "a skip is a rejection,
--     not a delivery and not engagement". Two columns would either store one
--     count twice (a copy that can disagree with itself) or invent a second
--     count with no event behind it. Revisit: a canonical document or a later
--     cut distinguishes a rejection from a skip (a refusal gesture that is not
--     a skip) — then a second column lands and this reading moves with it.
--   * **Not materialized: ``coverage_debt_rollups`` and
--     ``recent_target_families``.** Both are ledger-level aggregates of the
--     per-key facts, not per-key columns (§14 lists them outside the row
--     group; the core carries them as ``PlanningLedger``'s row-independent
--     fields and *reads* rollups rather than computing them), and §26 names
--     "some PlanningLedger rollups" among the rebuildable projections with the
--     rule that a rebuildable projection is never the only source of truth. A
--     per-key copy of a ledger-level aggregate would be that forbidden single
--     source in the other direction (a stored copy nothing reconciles), and a
--     singleton row for the pair would be a fourth table this cut's mandate
--     does not carry. So neither is materialized: ``read_ledger()`` answers
--     the core's own defaults for both (``{}`` / ``()`` — the values the pure
--     core declares for a ledger nothing wrote), and the cut that first
--     *reads* a rollup out of the durable ledger lands its home in the same
--     change. Revisit: a reader needs a stored rollup (a dashboard, an
--     export), or §26's list changes — then the column/table question is
--     re-asked with that reader's shape.
--   * **``version`` is per row.** §14 lists ``version`` once at the end of the
--     block; this table carries it on every row, stamped by the writer with
--     ``elc.planner.ledger.PLANNING_LEDGER_MODEL_VERSION`` — the per-row
--     version stamp §5.2's ``schedule_item.version`` established, and the same
--     constant the core's ledger-level ``version`` field answers, so there is
--     one source for the number and no stored copy that can disagree.
--   * **The CHECK on table 3's ``event`` is canonical vocabulary.** The five
--     words are RA §20's own block, so the schema freezes them (0015's
--     ``decision`` / ``status`` / ``outcome`` precedent). ``scope_type`` and
--     ``accrual_paused``'s companion rules are **not** handled that way: no
--     canonical document lists ``scope_type``'s vocabulary (the core declares
--     ``ObligationScope`` and says so), so the column stays raw exactly as
--     §5.2's ``event_type`` does in 0012 — the implementation's word list is
--     not frozen into schema.
--   * **The pause agreement is a CHECK, not a prose rule.**
--     ``accrual_paused`` and ``pause_reason`` must agree (a pause has a
--     reason and a reason has a pause). The core refuses both halves at
--     construction and calls the invariant canonical; the CHECK below is that
--     sentence in DDL. Revisit: the invariant changes in canonical text (a
--     pause without a reason becomes stateable) — both spellings move
--     together.
--   * **No range CHECK on ``debt_value``.** ``debt_value`` lands REAL
--     NOT NULL with **no** range CHECK: the ``[0, 1]`` range is this
--     repository's *declared* number (``elc.planner.ledger.LEDGER_VALUE_RANGE``,
--     whose declaredness the module registers), the write face refuses outside
--     it through the object's own constructor, and a CHECK here would be a
--     second spelling of a declared number in a place a calibration change
--     would have to find as well.
--   * **No reference columns on the event log.** §14 and §20 name no ref
--     column for a ledger event, and the parenthetical reading of "optional
--     refs" is deliberately not taken: an FK to ``teaching_moment`` would
--     break the CONVERSATION walk (that scope deletes moments and does not
--     name this table, so the sweep would die on a foreign key), and a plain
--     TEXT ref with no FK would be a provenance pointer nothing checks — a
--     column with no writer that can only hold invented data, which is the
--     same argument the pre-cut storage registration made. Revisit: the
--     delivery path (p8-4) records the Moment a presentation belongs to, or
--     §19's "Review / Planning history solely derived from deleted Evidence"
--     is given a row-level carrier — then the ref column and the conversation
--     leg land together.
-- ---------------------------------------------------------------------------
-- 1. planning_ledger — §14 lines 891–918, the per-key row
--
-- The declared key faces (the CHECK's two words) are
-- ``elc.planner.ledger.LedgerKeyType``: §14 spells the key ``target/family``
-- and no document lists a vocabulary, so this cut declares exactly those two
-- and a test holds the CHECK against the enum, word for word.
--
-- ``ledger_key`` is the key **as spelled** — the core matches obligations
-- against it "as spelled" too (its ``obligations_for``), so no normalization
-- happens at either end.
CREATE TABLE IF NOT EXISTS planning_ledger (
    ledger_key               TEXT PRIMARY KEY,
    ledger_key_type          TEXT NOT NULL
        CHECK (ledger_key_type IN ('TARGET', 'TARGET_FAMILY')),
    last_selected_at         TEXT,
    last_presented_at        TEXT,
    teaching_exposure_counts INTEGER NOT NULL,
    probe_counts             INTEGER NOT NULL,
    review_offers            INTEGER NOT NULL,
    recent_skips             INTEGER NOT NULL,
    overexposure_window      TEXT,
    version                  TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 2. coverage_obligation — §14's ``coverage_obligations[]``, eleven fields
--
-- ``obligation_key`` is the key (§14 puts the field first in the sub-block).
-- ``scope_type`` / ``target_or_family_id`` / ``goal_id`` are the three key
-- spaces the sub-block names; the words for ``scope_type`` stay the core's
-- (``ObligationScope``) and are not frozen here.
--
-- The window's two instants are TEXT NOT NULL (the core requires both); the
-- two ``?`` timestamps and ``goal_id`` / ``pause_reason`` are nullable.
CREATE TABLE IF NOT EXISTS coverage_obligation (
    obligation_key      TEXT PRIMARY KEY,
    scope_type          TEXT NOT NULL,
    target_or_family_id TEXT NOT NULL,
    goal_id             TEXT,
    window_start        TEXT NOT NULL,
    window_end          TEXT NOT NULL,
    debt_value          REAL NOT NULL,
    accrual_paused      INTEGER NOT NULL CHECK (accrual_paused IN (0, 1)),
    pause_reason        TEXT,
    last_served_at      TEXT,
    last_engaged_at     TEXT,
    CHECK ((accrual_paused = 0 AND pause_reason IS NULL)
        OR (accrual_paused = 1 AND pause_reason IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- 3. planning_ledger_event — RA §20's five events, append-first (§1.3)
--
-- The five CHECK words are §20's block, character for character, in the
-- document's order; the effect each word has on the ledger is
-- ``elc.planner.ledger.EVENT_EFFECTS``' (the two §20 sentences are two of its
-- rows), and a test holds the CHECK against that table's keys.
--
-- ``event_id`` is the durable identity of one appended fact, minted by the
-- caller — §20 names no id, and the core's log record is exactly
-- ``(event, at)``; the 0012 ``review_event_id`` precedent is the shape (a fact
-- is never rewritten: the store refuses a differing content under an existing
-- id). The identity cannot be the content, because the core's log does **not**
-- collapse a repeat: two presentations at one instant are two presentations.
--
-- ``as_of`` is the event's instant — the core's ``LedgerEventRecord.at`` under
-- the durable name this cut declares; it is NOT NULL because every §20 event
-- carries an instant in the core (no column is invented for a second clock:
-- the store writes no stamp of its own on this log).
--
-- Append-only: no UPDATE and no DELETE statement names this table in src/,
-- and the table carries no unique index beyond its key — several events for
-- one key over time are the history §1.3 asks to keep.
CREATE TABLE IF NOT EXISTS planning_ledger_event (
    event_id   TEXT PRIMARY KEY,
    ledger_key TEXT NOT NULL REFERENCES planning_ledger(ledger_key),
    event      TEXT NOT NULL
        CHECK (event IN ('candidate_selected', 'teaching_presented',
                         'hint_presented', 'reveal_presented', 'user_skip')),
    as_of      TEXT NOT NULL
);

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '16')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '16')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
