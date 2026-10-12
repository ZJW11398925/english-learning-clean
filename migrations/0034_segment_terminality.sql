-- 0034_segment_terminality.sql — V3-5R (the external review's
-- MEDIUM-HIGH; TASK-OPI-dc1bafdf…13 / the opening ruling
-- DEC-OPI-dc1bafdf…11, DECISION_REGISTER v1.4.2).
--
-- One ALTER and one exact back-fill: ``segment_commit`` gains its
-- terminality column — ``is_last_segment`` — the persisted fact that
-- this segment's SEGMENT COMMIT carried the scene's
-- ``ACTIVE → COMMITTED`` flip (the SCENE COMMIT alias, STATE §22/§25).
--
-- Authority, spelled:
--   * DATA_MODEL §26.2.1's "V3-5R 落法" block — the column, its CHECK
--     vocabulary and the back-fill law: ``is_last_segment INTEGER NOT
--     NULL DEFAULT 0 CHECK (is_last_segment IN (0,1))``; the back-fill
--     holds **only for the V3-5 pipeline's own product** (segment rows
--     are written only by :func:`elc.world.settlement.commit_segment`,
--     and that transaction flips the scene on its last segment — so a
--     ``COMMITTED`` / ``CLOSED`` scene's maximum ``segment_seq`` row is
--     the one that flipped it).
--   * STATE_MACHINES §25's "V3-5R 落法" — terminality is persisted: the
--     replay shape comparison reads it, and the same ``segment_key``
--     replayed with a different ``is_last_segment`` is an explicit
--     ``CONFLICT`` (never a silent "equivalent record").
--   * RUNTIME_ARCHITECTURE §28's "V3-5R 落法" sentence.
--
-- Why ALTER and not a rebuild (the 0032 precedent is deliberately not
-- reused): the new column is a trailing addition — no existing column's
-- name, order, data face or CHECK vocabulary changes, and every carried
-- row takes the constant DEFAULT 0 the ADD COLUMN stamps onto it. The
-- 0032 rebuild exists for a constraint ALTER TABLE cannot express (a
-- table-level composite FOREIGN KEY); nothing here needs one. The
-- back-fill below is the deliberate second half — the *only* rows the
-- pipeline's own law can honestly mark, never a reconstruction rule for
-- a scene a direct ``commit_scene`` call committed (such a scene can be
-- ``COMMITTED`` with no terminal segment at all — the ruling rejected
-- the derived-reread form for exactly that reason; those rows stay ``0``,
-- honestly).
--
-- DATA_MODEL §26.1: migrations bump schema_version explicitly.
-- ---------------------------------------------------------------------------
ALTER TABLE segment_commit ADD COLUMN is_last_segment INTEGER NOT NULL DEFAULT 0
    CHECK (is_last_segment IN (0, 1));

UPDATE segment_commit SET is_last_segment = 1
 WHERE EXISTS (
   SELECT 1 FROM world_scene s
   WHERE s.scene_id = segment_commit.scene_id
     AND s.status IN ('COMMITTED','CLOSED')
     AND segment_commit.segment_seq = (
       SELECT MAX(sc.segment_seq) FROM segment_commit sc
       WHERE sc.scene_id = segment_commit.scene_id));

-- DATA_MODEL §26.1: 数据库迁移必须显式更新版本.
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '34')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT INTO schema_meta (key, value) VALUES ('runtime_schema_version', '34')
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
