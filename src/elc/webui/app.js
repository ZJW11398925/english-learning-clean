// app.js —— 装配：三屏切换 / 信流事件 / 轮询 / 学习与诊断的读数渲染
// （F-G1）。只做装配与视图渲染：端点调用只走 api.js，DOM 工厂只走
// components.js；文字一律 textContent。装配顺序＝模块加载即绑定
// （type="module" 天然延迟到文档解析后，与拆分前页尾内联脚本同语义）。

import {
  addLine,
  messages,
  showMoments,
  diagEmpty,
  diagError,
  diagLine,
  diagGroup,
  stateBanner,
  installBrandMarks,
  wordWindows,
  showWordCard,
  confirmDialog,
  fieldRow,
  chip,
} from "./components.js";
import {
  fetchTurn,
  fetchTeachMe,
  fetchDiagnostics,
  fetchLearning,
  fetchTargets,
  fetchObservations,
  fetchHistory,
  fetchCurrentMoment,
  fetchWord,
  fetchMemory,
  fetchDelete,
  fetchGoals,
  fetchSaveGoals,
  fetchSaveFrequency,
} from "./api.js";

// F-1: the diagnostics view — the five whys, read from /api/diagnostics.
// Chinese labels over the raw numbers; a panel with nothing to say says so.
const OUTCOME_CN = {
  SUCCESS: "回答正确",
  ALTERNATIVE_SUCCESS: "回答正确（另一种合格表达）",
  PARTIAL: "部分正确",
  FAILURE: "未命中目标表达",
  ABSTAIN: "本次作答无法评判",
};
const ACTION_CN = {
  TEACHING_OPEN: "打开教学",
  TEACHING_HINT: "给提示",
  TEACHING_REVEAL: "展示答案",
  TEACHING_EXPLANATION: "给解释",
};

function fmtNum(value) {
  return (value === null || value === undefined) ? "—" : String(value);
}

function diagBox(id) {
  return document.getElementById(id);
}

// F-G2: the read panels answer through the state-banner family — loading
// while the pull is in flight, empty and error through diagEmpty/diagError
// (both now delegate to the one component; the old scattered hard-coded
// notes are gone). A failed pull offers 重试, which re-pulls that panel
// only — the retry callback is injected by each loader below.
const DIAG_PANEL_IDS = ["why-teach", "why-not-teach", "why-evidence",
                        "why-support", "why-degraded"];
const LEARN_PANEL_IDS = ["learn-schedule", "learn-goals", "learn-evidence"];

function showLoading(ids) {
  for (const id of ids) {
    const box = diagBox(id);
    box.textContent = "";
    box.appendChild(stateBanner("loading"));
  }
}

function renderWhyTeach(d, retry) {
  const box = diagBox("why-teach");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  if (!d.candidate) {
    diagEmpty(box, "暂无数据——最近 50 轮规划评估里没有选中任何候选。");
    return;
  }
  const g = diagGroup(box, "被选中的候选");
  diagLine(g, "目标（canonical_key）", d.candidate.canonical_key);
  diagLine(g, "收益分 benefit", fmtNum(d.candidate.benefit_score));
  diagLine(g, "成本分 cost", fmtNum(d.candidate.cost_score));
  diagLine(g, "效用 utility", fmtNum(d.candidate.utility));
  if (d.gate) {
    const gg = diagGroup(box, "门（Gate）裁决");
    diagLine(gg, "裁决", d.gate.decision);
    const codes = d.gate.reason_codes;
    diagLine(gg, "理由码", Array.isArray(codes) ? codes.join("、") : String(codes));
    diagLine(gg, "时间", d.gate.created_at);
  }
  diagLine(box, "评估时间", d.created_at);
}

function renderWhyNot(d, retry) {
  const box = diagBox("why-not-teach");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const list = d.candidates || [];
  if (d.created_at === null && !list.length) {
    diagEmpty(box, "暂无数据——还没有任何一轮规划评估。");
    return;
  }
  if (!list.length) {
    diagLine(box, "本轮未激活候选", "无（本轮候选全部激活，或本轮没有候选）");
  }
  for (const c of list) {
    const g = diagGroup(box, c.canonical_key || c.candidate_id);
    diagLine(g, "效用 vs 阈值",
      fmtNum(c.utility) + "  vs  " + fmtNum(c.activation_threshold));
    diagLine(g, "是否激活",
      c.activated === false ? "未激活（activated: false）" : String(c.activated));
    for (const r of (c.costs || [])) {
      diagLine(g, "成本因子 " + r.factor, fmtNum(r.value));
    }
  }
  if (d.gate_deny) {
    const gg = diagGroup(box, "最近一次门拦截（DENY）");
    const codes = d.gate_deny.reason_codes;
    diagLine(gg, "理由码", Array.isArray(codes) ? codes.join("、") : String(codes));
    diagLine(gg, "时间", d.gate_deny.created_at);
  }
}

function renderEvidence(d, retry) {
  const box = diagBox("why-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.records || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有任何一次作答被判分。");
    return;
  }
  for (const r of rows) {
    const g = diagGroup(box, OUTCOME_CN[r.outcome] || r.outcome);
    diagLine(g, "outcome", r.outcome);
    diagLine(g, "confidence", fmtNum(r.confidence));
    diagLine(g, "时间", r.created_at);
  }
}

function renderSupport(d, retry) {
  const box = diagBox("why-support");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.actions || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有任何一次教学支持被交付。");
    return;
  }
  for (const a of rows) {
    const g = diagGroup(box, ACTION_CN[a.action_type] || a.action_type);
    diagLine(g, "action_type", a.action_type);
    diagLine(g, "时间", a.created_at);
  }
  diagLine(box, "曝光估计累计（exposure_estimate）",
    d.exposure_estimate_count + " 条");
}

function renderDegraded(d, retry) {
  const box = diagBox("why-degraded");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const pe = d.planner_execution;
  const ro = d.runtime_outcome;
  if (!pe && !ro) { diagEmpty(box, "无降级记录"); return; }
  if (pe) {
    const g = diagGroup(box, "Planner 执行状态");
    diagLine(g, "status", pe.status);
    diagLine(g, "error_code", pe.error_code === null ? "—" : pe.error_code);
    diagLine(g, "时间", pe.created_at);
  }
  if (ro) {
    const g = diagGroup(box, "运行时轮次结局");
    diagLine(g, "outcome", ro.outcome);
    const codes = ro.reason_codes;
    diagLine(g, "理由码", Array.isArray(codes) ? codes.join("、") : String(codes));
    diagLine(g, "时间", ro.created_at);
  }
}

async function loadDiagnostics() {
  showLoading(DIAG_PANEL_IDS);
  try {
    const data = await fetchDiagnostics();
    renderWhyTeach(data.why_teach, loadDiagnostics);
    renderWhyNot(data.why_not_teach, loadDiagnostics);
    renderEvidence(data.evidence, loadDiagnostics);
    renderSupport(data.support, loadDiagnostics);
    renderDegraded(data.degraded, loadDiagnostics);
  } catch {
    for (const id of DIAG_PANEL_IDS) {
      diagError(diagBox(id), "诊断读数拉取失败", loadDiagnostics);
    }
  }
}

document.getElementById("diag-refresh").addEventListener("click", loadDiagnostics);

// F-2: the 学习 view — what can be taught, the schedule, the goals and
// the evidence ledger. Read-only numbers under Chinese labels; the one
// act is 教我这个, which asks the runtime to open the teaching.
// p-1: the row factory is shared with the 今日 screen's two act blocks
// (the same 教我这个, the same .teach-me form).
function teachRow(name, targetId) {
  const row = document.createElement("div");
  row.className = "kv";
  const b = document.createElement("b");
  b.textContent = name;
  row.appendChild(b);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "teach-me";
  button.textContent = "教我这个";
  button.addEventListener("click", () => postTeachMe(targetId));
  row.appendChild(button);
  return row;
}

async function loadTargets() {
  const box = diagBox("target-list");
  box.textContent = "";
  box.appendChild(stateBanner("loading"));
  try {
    const data = await fetchTargets();
    box.textContent = "";
    const list = data.targets || [];
    if (!list.length) { diagEmpty(box, "暂无可教目标"); return; }
    for (const t of list) {
      box.appendChild(teachRow(t.name || t.target_id, t.target_id));
    }
  } catch {
    box.textContent = "";
    diagError(box, "目标清单拉取失败", loadTargets);
  }
}

async function postTeachMe(targetId) {
  try {
    const data = await fetchTeachMe(targetId);
    if (data.accepted) {
      addLine("system", "教学已开始，卡片出现在下方");
      showScreen("living");
      startMomentPolling();
    } else {
      addLine("failure", data.error || "无法开始这节课");
    }
  } catch {
    addLine("failure", "请求失败，请重试");
  }
}

function renderSchedule(d, retry) {
  const box = diagBox("learn-schedule");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.items || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有任何复习日程。");
    return;
  }
  for (const it of rows) {
    const g = diagGroup(box, it.target_id + "（" + it.target_type + "）");
    diagLine(g, "复习状态", it.review_state);
    diagLine(g, "紧迫度 review_urgency", fmtNum(it.review_urgency));
    diagLine(g, "窗口开始", fmtNum(it.next_review_window_start));
    diagLine(g, "窗口结束", fmtNum(it.next_review_window_end));
    diagLine(g, "间隔阶 spacing_stage", fmtNum(it.spacing_stage));
    diagLine(g, "更新时间", it.updated_at);
  }
}

function renderGoals(d, retry) {
  const box = diagBox("learn-goals");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.portfolios || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有写下学习目标。");
    return;
  }
  for (const p of rows) {
    const g = diagGroup(box, p.goal_portfolio_id);
    const goals = p.goals || [];
    diagLine(g, "目标数", goals.length);
    for (const goal of goals) {
      diagLine(g, "目标 " + (goal.goal_id || ""),
        (goal.description || "") + " · " + (goal.goal_modality || ""));
    }
    const weights = p.modality_weights || {};
    for (const key of Object.keys(weights)) {
      diagLine(g, "权重 " + key, String(weights[key]));
    }
  }
}

function renderLearnEvidence(d, retry) {
  const box = diagBox("learn-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  diagLine(box, "证据记录总数", (d.evidence_claim_count || 0) + " 条");
  diagLine(box, "学习者目标状态", (d.learner_target_state_count || 0) + " 行");
  const rows = d.claims || [];
  if (!rows.length) {
    diagEmpty(box, "暂无单条记录——还没有任何证据被写入。");
    return;
  }
  for (const c of rows) {
    const g = diagGroup(box, c.target_id);
    diagLine(g, "polarity", c.polarity);
    diagLine(g, "outcome", c.outcome);
    diagLine(g, "performance_type", c.performance_type);
    diagLine(g, "时间", c.created_at);
  }
}

async function loadLearning() {
  showLoading(LEARN_PANEL_IDS);
  try {
    const data = await fetchLearning();
    renderSchedule(data.schedule, loadLearning);
    renderGoals(data.goals, loadLearning);
    renderLearnEvidence(data.evidence, loadLearning);
  } catch {
    for (const id of LEARN_PANEL_IDS) {
      diagError(diagBox(id), "学习读数拉取失败", loadLearning);
    }
  }
}

document.getElementById("learning-refresh").addEventListener("click",
  () => { loadTargets(); loadLearning(); });

// p-1: the 今日 screen — 到期复习 / 最近在学 / 想练一把, three read-only
// blocks over the same faces the 学习 view reads (no fourth endpoint, no
// invented daily activity). Entering the screen is the pull.
const TODAY_PANEL_IDS = ["today-due", "today-recent", "today-practice"];

// the spoken name of a target id, the server's own reading rule done
// client-side (the claims and schedule rows carry ids, not names)
function todayName(targetId) {
  const parts = String(targetId).split("-");
  return parts.length > 2 ? parts.slice(2).join(" ") : String(targetId);
}

function renderTodayDue(schedule, retry) {
  const box = diagBox("today-due");
  box.textContent = "";
  if (!schedule || schedule.error) {
    diagError(box, (schedule && schedule.error) || "空响应", retry);
    return;
  }
  const due = (schedule.items || []).filter(
    (it) => it.review_state === "DUE" || it.review_state === "OVERDUE");
  if (!due.length) { diagEmpty(box, "现在没有到期的复习"); return; }
  for (const it of due) {
    box.appendChild(teachRow(
      todayName(it.target_id) + "（" + it.review_state + "）",
      it.target_id));
  }
}

function renderTodayRecent(evidence, retry) {
  const box = diagBox("today-recent");
  box.textContent = "";
  if (!evidence || evidence.error) {
    diagError(box, (evidence && evidence.error) || "空响应", retry);
    return;
  }
  const claims = evidence.claims || [];
  if (!claims.length) {
    // 槽位单态：空态独占面板（清空先于挂载），计数只随数据出现
    diagEmpty(box, "还没有学习记录——聊起来才会积累。");
    return;
  }
  diagLine(box, "有学习状态的目标",
    (evidence.learner_target_state_count || 0) + " 个");
  // the claims come newest-first; the first sighting of a target is its
  // most recent outcome
  const latest = new Map();
  for (const claim of claims) {
    if (!latest.has(claim.target_id)) latest.set(claim.target_id, claim);
  }
  for (const [targetId, claim] of latest) {
    const g = diagGroup(box, todayName(targetId));
    diagLine(g, "最近 outcome", claim.outcome);
    diagLine(g, "时间", claim.created_at);
  }
}

function renderTodayPractice(targets, retry) {
  const box = diagBox("today-practice");
  box.textContent = "";
  if (!targets || targets.error) {
    diagError(box, (targets && targets.error) || "空响应", retry);
    return;
  }
  const list = targets.targets || [];
  if (!list.length) { diagEmpty(box, "暂无可练的目标"); return; }
  for (const t of list) {
    box.appendChild(teachRow(t.name || t.target_id, t.target_id));
  }
}

async function loadToday() {
  showLoading(TODAY_PANEL_IDS);
  let learning = null;
  let targets = null;
  try {
    learning = await fetchLearning();
  } catch {
    learning = null;
  }
  try {
    targets = await fetchTargets();
  } catch {
    targets = null;
  }
  renderTodayDue(learning === null ? null : learning.schedule, loadToday);
  renderTodayRecent(learning === null ? null : learning.evidence, loadToday);
  renderTodayPractice(targets, loadToday);
}

document.getElementById("today-refresh").addEventListener("click", loadToday);

// p-2: the 记忆 view — what the parlor remembers, in five panels over one
// read (/api/memory). Honest empties say 还没有记住什么 rather than
// dressing absence up; every number is the row's own.
const MEM_PANEL_IDS = ["mem-relationship", "mem-episode", "mem-states",
                       "mem-evidence", "mem-tombstones"];

function renderMemRelationship(d, retry) {
  const box = diagBox("mem-relationship");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.memories || [];
  if (!rows.length) {
    diagEmpty(box, "还没有记住什么——聊得多起来，才会记住关于你和它的事。");
    return;
  }
  for (const m of rows) {
    const g = diagGroup(box, m.memory_type + "（" + m.status + "）");
    diagLine(g, "记住的内容", m.canonical_content);
    diagLine(g, "provenance", m.provenance);
    diagLine(g, "敏感级与授权",
      m.sensitivity_class + " / " + m.persistence_authorization);
    if (m.confidence !== null && m.confidence !== undefined) {
      diagLine(g, "confidence", fmtNum(m.confidence));
    }
    diagLine(g, "更新时间", m.updated_at);
  }
}

function renderMemEpisode(d, retry) {
  const box = diagBox("mem-episode");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.episodes || [];
  if (!rows.length) {
    diagEmpty(box, "还没有记住什么——没有一段对话被总结成剧情。");
    return;
  }
  for (const e of rows) {
    const g = diagGroup(box, e.conversation_id);
    diagLine(g, "摘要", e.summary);
    diagLine(g, "未了话题",
      Array.isArray(e.open_threads) ? e.open_threads.join("；") : fmtNum(e.open_threads));
    diagLine(g, "最近事件",
      Array.isArray(e.recent_events) ? e.recent_events.join("；") : fmtNum(e.recent_events));
    diagLine(g, "状态", e.status);
    diagLine(g, "更新时间", e.updated_at);
  }
}

function renderMemStates(d, retry) {
  const box = diagBox("mem-states");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.states || [];
  if (!rows.length) {
    diagEmpty(box, "还没有学习状态——还没有任何证据被投影到这里。");
    return;
  }
  for (const s of rows) {
    const g = diagGroup(box,
      s.target_id + "（" + s.target_type + " · " + s.evidence_modality + "）");
    diagLine(g, "证据水位", fmtNum(s.evidence_watermark));
    diagLine(g, "状态键", Array.isArray(s.state_keys)
      ? (s.state_keys.length ? s.state_keys.join("、") : "（空）") : "—");
    diagLine(g, "estimator", s.estimator_version);
    diagLine(g, "更新时间", s.updated_at);
  }
}

function renderMemEvidence(d, retry) {
  const box = diagBox("mem-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  diagLine(box, "证据行（evidence_claim）", (d.evidence_claim_count || 0) + " 条");
  diagLine(box, "证据提交（evidence_commit）", (d.evidence_commit_count || 0) + " 次");
  const rows = d.claims || [];
  if (!rows.length) {
    diagEmpty(box, "还没有任何证据——答对答错都会在这里留下痕迹。");
    return;
  }
  for (const c of rows) {
    const g = diagGroup(box, c.target_id);
    diagLine(g, "polarity", c.polarity);
    diagLine(g, "outcome", c.outcome);
    diagLine(g, "performance_type", c.performance_type);
    diagLine(g, "时间", c.created_at);
  }
}

function renderMemTombstones(d, retry) {
  const box = diagBox("mem-tombstones");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.tombstones || [];
  if (!rows.length) {
    diagEmpty(box, "删除台账为空——还没有删除过任何东西。");
    return;
  }
  for (const t of rows) {
    const g = diagGroup(box, t.entity_kind);
    diagLine(g, "摘要（单向摘要，不含正文）", t.entity_hash);
    diagLine(g, "删除于", t.deleted_at);
    diagLine(g, "范围", t.deletion_scope);
    diagLine(g, "口径版本", t.scope_version);
  }
}

async function loadMemory() {
  showLoading(MEM_PANEL_IDS);
  try {
    const data = await fetchMemory();
    renderMemRelationship(data.relationship_memory, loadMemory);
    renderMemEpisode(data.episode, loadMemory);
    renderMemStates(data.learner_states, loadMemory);
    renderMemEvidence(data.evidence, loadMemory);
    renderMemTombstones(data.tombstones, loadMemory);
  } catch {
    for (const id of MEM_PANEL_IDS) {
      diagError(diagBox(id), "记忆读数拉取失败", loadMemory);
    }
  }
}

document.getElementById("mem-refresh").addEventListener("click", loadMemory);

// p-2: the 隐私 view — three deletable scopes, each behind two confirms.
// 删除不可逆：第一层把范围用人话讲清（带「此操作不可恢复」），第二层
// 再问一次（「确定继续？再次确认」）；两层都过才发请求。结果条只说
// runtime 自己报的数（scope / notes / rebuilds 计数）。
function renderDelRefused(text) {
  const box = diagBox("del-result");
  box.textContent = "";
  const b = document.createElement("b");
  b.textContent = "删除未执行：" + text;
  box.appendChild(b);
}

function renderDelResult(data) {
  const box = diagBox("del-result");
  box.textContent = "";
  const notes = data.notes || [];
  // p-2 评审 F-2：notes 含 already absent = 幂等空删——标题与尾句不得
  // 对未发生的事声称发生（无新墓碑、台账无更新）。
  const alreadyAbsent = notes.some((n) => n.includes("already absent"));
  const g = diagGroup(
    box,
    alreadyAbsent
      ? "没有可删的（" + data.scope + " 已不在）"
      : "已删除：" + data.scope
  );
  diagLine(g, "说明", notes.length ? notes.join("；") : "无");
  diagLine(g, "重建",
    (data.rebuilds_ok || 0) + " 成功 / " + (data.rebuilds_total || 0) + " 项");
  diagLine(g, "墓碑记录", (data.tombstoned || 0) + " 条");
  const tail = document.createElement("p");
  tail.className = "sub";
  tail.textContent = alreadyAbsent
    ? "这次没有删除任何新东西——之前留下的删除记录仍可在「记忆」的「删除台账」里看到。"
    : "删除台账已更新——打开「记忆」的「删除台账」可以看到这次删除留下的记录。";
  box.appendChild(tail);
}

async function runDelete(payload, humanText) {
  if (!confirmDialog(humanText)) return;
  if (!confirmDialog("确定继续？再次确认")) return;
  let data = null;
  try {
    data = await fetchDelete(payload);
  } catch {
    renderDelRefused("请求失败，请重试");
    return;
  }
  if (!data.accepted) {
    renderDelRefused((data.code || "拒绝") + "：" + (data.message || ""));
    return;
  }
  renderDelResult(data);
  loadMemory();  // the tombstone this deletion minted is visible in 记忆
}

function deleteTargetRow(name, targetId) {
  const row = document.createElement("div");
  row.className = "kv";
  const b = document.createElement("b");
  b.textContent = name;
  row.appendChild(b);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn--pencil";
  button.textContent = "删除这项目标数据";
  button.addEventListener("click", () => runDelete(
    { scope: "LEARNING_TARGET", target_id: targetId },
    "将删除目标 " + name + " 的学习证据、学习状态与复习日程。此操作不可恢复。"));
  row.appendChild(button);
  return row;
}

async function loadDelTargets() {
  const box = diagBox("del-targets");
  box.textContent = "";
  box.appendChild(stateBanner("loading"));
  try {
    const data = await fetchTargets();
    box.textContent = "";
    const list = data.targets || [];
    if (!list.length) { diagEmpty(box, "暂无可教目标"); return; }
    for (const t of list) {
      box.appendChild(deleteTargetRow(t.name || t.target_id, t.target_id));
    }
  } catch {
    box.textContent = "";
    diagError(box, "目标清单拉取失败", loadDelTargets);
  }
}

document.getElementById("del-conversation").addEventListener("click", () =>
  runDelete(
    { scope: "CONVERSATION" },
    "将删除这段对话的全部记录，包括信件与教学痕迹。此操作不可恢复。"));

// p-3: the 目标 screen — the long-term direction, read from /api/goals and
// written back through the store's own version discipline: the full new
// combination is one upsert (every save a new version, history kept), the
// teaching frequency is a single-column write, and a CONFLICT (another
// writer won) says so with a 重新读取 action. The pickers build themselves
// from the taxonomy the server serves — the words are the server's, never a
// client copy. Every user string rides textContent.

const GOAL_PANEL_IDS = ["goal-list", "goal-weights", "goal-assessment",
                        "goal-register", "goal-frequency"];

let goalData = null;   // the last GET /api/goals payload
let goalEditor = null; // the working copy the save sends

function goalBox(id) {
  return document.getElementById(id);
}

function goalWordSet(faceName) {
  // one taxonomy face's words, served by the GET (empty when absent —
  // the pickers stay empty rather than guessing a client-side list)
  const faces = (goalData && goalData.taxonomy &&
                 goalData.taxonomy.faces) || [];
  for (const face of faces) {
    if (face.name === faceName) return face.words || [];
  }
  return [];
}

function goalFrequencyWords() {
  return (goalData && goalData.taxonomy &&
          goalData.taxonomy.teaching_frequency &&
          goalData.taxonomy.teaching_frequency.words) || [];
}

// the result box: one human line, optionally with an action (the conflict's
// 重新读取). Failure rides the .errline form, success the .sub one.
function goalResult(text, failure, action) {
  const box = goalBox("goal-result");
  box.hidden = false;
  box.textContent = "";
  const line = document.createElement("p");
  line.className = failure ? "errline" : "sub";
  line.textContent = text;
  box.appendChild(line);
  if (action) box.appendChild(action);
}

function editorFromData(data) {
  const portfolio = data.portfolio;
  return {
    goals: ((portfolio && portfolio.goals) || []).map((goal) => ({
      goal_id: goal.goal_id,
      goal_modality: goal.goal_modality,
      description: goal.description,
    })),
    weights: Object.assign(
      {}, (portfolio && portfolio.modality_weights) || {}),
    assessment: new Set((portfolio && portfolio.assessment_targets) || []),
    register: new Set((portfolio && portfolio.register_style_goals) || []),
  };
}

function renderGoalList() {
  const box = goalBox("goal-list");
  box.textContent = "";
  const goals = (goalData && goalData.portfolio &&
                 goalData.portfolio.goals) || [];
  if (!goals.length) {
    diagEmpty(box, "还没有写下目标——在下面的编辑区写下第一个目标。");
    return;
  }
  for (const goal of goals) {
    const row = document.createElement("div");
    row.className = "goalcard";
    row.appendChild(chip(goal.goal_modality, { badge: true }));
    const desc = document.createElement("span");
    desc.className = "goaldesc";
    desc.textContent = goal.description;
    row.appendChild(desc);
    box.appendChild(row);
  }
}

function renderGoalEditor() {
  const box = goalBox("goal-editor");
  box.textContent = "";
  if (!goalEditor) return;
  const editor = goalEditor;
  const words = goalWordSet("goal_modality");
  editor.goals.forEach((goal, index) => {
    const edge = document.createElement("div");
    edge.className = "goaledge";
    const select = document.createElement("select");
    for (const word of words) {
      const option = document.createElement("option");
      option.value = word;
      option.textContent = word;
      if (word === goal.goal_modality) option.selected = true;
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      goal.goal_modality = select.value;
    });
    edge.appendChild(fieldRow("目标 " + (index + 1) + " · 模态", select));
    const description = document.createElement("input");
    description.type = "text";
    description.value = goal.description;
    description.placeholder = "一句话说清这个方向……";
    description.addEventListener("input", () => {
      goal.description = description.value;
    });
    edge.appendChild(fieldRow("目标 " + (index + 1) + " · 描述", description));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn--faint";
    remove.textContent = "从当前组合移除（历史版本保留）";
    remove.addEventListener("click", () => {
      editor.goals.splice(editor.goals.indexOf(goal), 1);
      renderGoalEditor();
    });
    edge.appendChild(remove);
    box.appendChild(edge);
  });
  const add = document.createElement("button");
  add.type = "button";
  add.className = "btn btn--pencil";
  add.textContent = "加一条目标";
  add.addEventListener("click", () => {
    editor.goals.push({
      goal_id: "goal-web-" + Date.now().toString(36) + "-" +
               Math.random().toString(36).slice(2, 8),
      goal_modality: words[0] || "SPEAKING",
      description: "",
    });
    renderGoalEditor();
  });
  box.appendChild(add);
}

function renderGoalWeights() {
  const box = goalBox("goal-weights");
  box.textContent = "";
  if (!goalEditor) return;
  for (const word of goalWordSet("goal_modality")) {
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.step = "0.1";
    input.placeholder = "未设";
    const value = goalEditor.weights[word];
    if (value !== undefined && value !== null) input.value = String(value);
    input.addEventListener("input", () => {
      if (input.value === "") delete goalEditor.weights[word];
      else goalEditor.weights[word] = Number(input.value);
    });
    box.appendChild(fieldRow(word, input));
  }
}

function renderWordPicker(boxId, faceName, set) {
  const box = goalBox(boxId);
  box.textContent = "";
  if (!goalEditor) return;
  const row = document.createElement("div");
  row.className = "chips";
  for (const word of goalWordSet(faceName)) {
    const on = set.has(word);
    row.appendChild(chip(word, {
      on: on,
      onClick: () => {
        if (on) set.delete(word);
        else set.add(word);
        renderWordPicker(boxId, faceName, set);
      },
    }));
  }
  box.appendChild(row);
}

function renderGoalSave() {
  const box = goalBox("goal-save");
  box.textContent = "";
  if (!goalEditor) return;
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--ink";
  save.textContent = "保存组合（目标 + 权重 + 考试 + 语域）";
  save.addEventListener("click", () => savePortfolio(save));
  box.appendChild(save);
}

async function savePortfolio(button) {
  const editor = goalEditor;
  if (!editor) return;
  for (let i = 0; i < editor.goals.length; i += 1) {
    if (!editor.goals[i].description.trim()) {
      goalResult("第 " + (i + 1) + " 条目标还没有描述。", true);
      return;
    }
  }
  const payload = {
    goals: editor.goals.map((goal) => ({
      goal_id: goal.goal_id,
      goal_modality: goal.goal_modality,
      description: goal.description.trim(),
    })),
    modality_weights: editor.weights,
    assessment_targets: Array.from(editor.assessment),
    register_style_goals: Array.from(editor.register),
  };
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "保存中…";
  let data = null;
  try {
    data = await fetchSaveGoals(payload);
  } catch {
    goalResult("保存失败，请重试", true);
    button.disabled = false;
    button.textContent = original;
    return;
  }
  button.disabled = false;
  button.textContent = original;
  if (data.accepted) {
    goalResult(data.idempotent
      ? "内容没有变化——没有写新版本。"
      : "已保存（版本 " + data.goal_version + "）。", false);
    loadGoals();
  } else if (data.conflict) {
    // the store refused the same-version write: the human sentence plus
    // the one action that resolves it — re-read and try again
    const again = document.createElement("button");
    again.type = "button";
    again.className = "btn btn--pencil";
    again.textContent = "重新读取";
    again.addEventListener("click", loadGoals);
    goalResult(data.error || "配置已被别处更新，请重读再改。", true, again);
  } else {
    goalResult(data.error || "保存失败，请重试", true);
  }
}

function renderGoalFrequency() {
  const box = goalBox("goal-frequency");
  box.textContent = "";
  if (!goalEditor) return;
  const policy = goalData && goalData.policy;
  if (policy) {
    diagLine(box, "当前", policy.teaching_frequency +
             "（版本 " + policy.policy_version + "）");
  } else {
    diagLine(box, "当前", "未配置");
  }
  const row = document.createElement("div");
  row.className = "chips";
  for (const word of goalFrequencyWords()) {
    row.appendChild(chip(word, {
      on: goalEditor.frequency === word,
      onClick: () => {
        goalEditor.frequency = word;
        renderGoalFrequency();
      },
    }));
  }
  box.appendChild(row);
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--pencil";
  save.textContent = "保存频率";
  save.addEventListener("click", () => saveFrequency(save));
  box.appendChild(save);
}

async function saveFrequency(button) {
  const editor = goalEditor;
  if (!editor || !editor.frequency) {
    goalResult("先在下面选一个频率。", true);
    return;
  }
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "保存中…";
  let data = null;
  try {
    data = await fetchSaveFrequency(editor.frequency);
  } catch {
    goalResult("保存失败，请重试", true);
    button.disabled = false;
    button.textContent = original;
    return;
  }
  button.disabled = false;
  button.textContent = original;
  if (data.accepted) {
    goalResult(data.idempotent
      ? "频率没有变化——没有写新版本。"
      : "教学频率已保存（版本 " + data.policy_version + "）。", false);
    loadGoals();
  } else if (data.conflict) {
    const again = document.createElement("button");
    again.type = "button";
    again.className = "btn btn--pencil";
    again.textContent = "重新读取";
    again.addEventListener("click", loadGoals);
    goalResult(data.error || "配置已被别处更新，请重读再改。", true, again);
  } else {
    goalResult(data.error || "保存失败，请重试", true);
  }
}

function renderGoalFocus() {
  const sec = goalBox("goal-focus-sec");
  const box = goalBox("goal-focus");
  box.textContent = "";
  const focus = goalData && goalData.session_focus;
  if (!focus) {
    sec.hidden = true;
    return;
  }
  sec.hidden = false;
  const group = diagGroup(box, "对话 " + focus.conversation_id);
  const weights = focus.temporary_goal_weights || {};
  const said = Object.keys(weights).map(
    (word) => word + " " + weights[word]).join("；");
  diagLine(group, "临时权重", said || "（无）");
  diagLine(group, "手动聚焦", focus.manual_focus_target || "—");
  diagLine(group, "开始于", focus.starts_at || "—");
  if (focus.expires_at) diagLine(group, "结束于", focus.expires_at);
}

function renderGoalTaxref() {
  const box = goalBox("goal-taxref");
  box.textContent = "";
  const taxonomy = (goalData && goalData.taxonomy) || {};
  const note = taxonomy.non_stored_note || "";
  for (const face of taxonomy.faces || []) {
    if (face.stored) continue;
    const line = document.createElement("p");
    line.className = "taxref";
    line.textContent = "§" + (face.section || "?") + " " + face.name +
      "（" + face.words.length + " 词 · " + note + "）：" +
      face.words.join("、");
    box.appendChild(line);
  }
}

async function loadGoals() {
  for (const id of GOAL_PANEL_IDS) {
    const box = goalBox(id);
    box.textContent = "";
    box.appendChild(stateBanner("loading"));
  }
  // the result box is NOT touched here: a save's own line must survive the
  // re-read that follows it (hiding happens on screen entry, showScreen)
  try {
    goalData = await fetchGoals();
  } catch {
    for (const id of GOAL_PANEL_IDS) {
      diagError(goalBox(id), "目标读数拉取失败", loadGoals);
    }
    return;
  }
  if (!goalData.available) {
    // the honest refusal: no user-config leg on this host, nothing to
    // read and nothing to edit — said in every panel, no editor built
    goalEditor = null;
    for (const id of GOAL_PANEL_IDS) {
      diagEmpty(goalBox(id),
        "本进程未装配用户配置面（无 content-tier）——目标读写不可用。");
    }
    goalBox("goal-save").textContent = "";
    return;
  }
  goalEditor = editorFromData(goalData);
  goalEditor.frequency =
    (goalData.policy && goalData.policy.teaching_frequency) || null;
  renderGoalList();
  renderGoalEditor();
  renderGoalWeights();
  renderWordPicker("goal-assessment", "external_assessment",
    goalEditor.assessment);
  renderWordPicker("goal-register", "register_style",
    goalEditor.register);
  renderGoalSave();
  renderGoalFrequency();
  renderGoalFocus();
  renderGoalTaxref();
}

document.getElementById("goal-toggle").addEventListener("click",
  () => showScreen("goal"));
document.getElementById("goal-set").addEventListener("click",
  () => showScreen("set"));
document.getElementById("back-from-goal").addEventListener("click",
  () => showScreen("living"));
document.getElementById("goal-refresh").addEventListener("click", loadGoals);

// F-2: why a quiet turn was quiet — one gray line from the diagnostics
// face's why-not-teach panel. The gate lives in postTurn (only when the
// turn response carried no teaching moments); a failed or empty pull
// stays silent, the chat is never blocked by the note.
async function showBlockedNote() {
  let data = null;
  try {
    data = await fetchDiagnostics();
  } catch {
    return;
  }
  const panel = data && data.why_not_teach;
  if (!panel || panel.error) return;
  let summary = "";
  const candidate = (panel.candidates || [])[0];
  if (candidate) {
    summary = "本轮未教学：候选 " +
      (candidate.canonical_key || candidate.candidate_id) +
      " 效用 " + fmtNum(candidate.utility) +
      " 低于阈值 " + fmtNum(candidate.activation_threshold);
  } else if (panel.gate_deny) {
    const codes = panel.gate_deny.reason_codes;
    summary = "本轮未教学：门拦截 " +
      (Array.isArray(codes) ? codes.join("、") : String(codes));
  } else {
    return;
  }
  const line = document.createElement("div");
  line.className = "blockedline";
  line.textContent = summary;
  messages.appendChild(line);
  messages.scrollTop = messages.scrollHeight;
}

// F-1R: the screens — 开张 / 客厅 / 今日 / 仪表 — plain show/hide, no
// router: the parlor header's 今日 and 仪表 links lead to their screens
// and each screen's way back leads to the parlor.
const screens = {
  onboard: document.getElementById("screen-onboard"),
  living: document.getElementById("screen-living"),
  today: document.getElementById("screen-today"),
  goal: document.getElementById("screen-goal"),
  set: document.getElementById("screen-set"),
};

function showScreen(name) {
  for (const key of Object.keys(screens)) {
    screens[key].hidden = key !== name;
  }
  // p-1: entering the 今日 screen is the pull — the screen always shows
  // today's facts, never a stale page. p-3: the 目标 screen is the same
  // kind of door — entering it reads the goals afresh (and starts with no
  // leftover save result; a save's own line survives its re-read).
  if (name === "today") loadToday();
  if (name === "goal") {
    goalBox("goal-result").hidden = true;
    loadGoals();
  }
  window.scrollTo(0, 0);
}

document.getElementById("meter-toggle").addEventListener("click",
  () => showScreen("set"));
document.getElementById("today-toggle").addEventListener("click",
  () => showScreen("today"));
document.getElementById("today-set").addEventListener("click",
  () => showScreen("set"));
document.getElementById("back-from-today").addEventListener("click",
  () => showScreen("living"));
document.getElementById("back-to-living").addEventListener("click",
  () => showScreen("living"));

// p-1: 点词——信件与用户回条里的 .word 可点。以点击词为中心取 1–3 词
// 窗口（长窗优先），逐窗口调 /api/word，首个命中即出卡；miss 按契约
// 静默（不弹「没查到」浮层）。stopPropagation 让开卡点击不被浮层的
// 「点卡外关闭」监听立即收掉。
messages.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.classList.contains("word")) return;
  if (!target.closest(".letter")) return;
  event.stopPropagation();
  const say = target.closest(".say");
  if (!say) return;
  const spans = Array.from(say.querySelectorAll(".word"));
  const index = spans.indexOf(target);
  if (index < 0) return;
  for (const query of
       wordWindows(spans.map((span) => span.textContent || ""), index)) {
    let data = null;
    try {
      data = await fetchWord(query);
    } catch {
      return;  // 一行人话的失败姿态属于教学与读数面；点词失败保持安静
    }
    if (data && data.found) {
      showWordCard(event, data);
      return;
    }
  }
});

// F-1R: the set screen's four blocks — 学习 / 诊断 / 记忆（p-2）/ 隐私
// （p-2）— expand in place (the F-1R task book leaves the choice to this
// page, recorded here): the expansion pulls the block's read, the refresh
// links re-pull.
function toggleSetBlock(name) {
  for (const block of ["learning", "diagnostics", "memory", "privacy"]) {
    document.getElementById("set-" + block).hidden = name !== block;
  }
  if (name === "diagnostics") loadDiagnostics();
  if (name === "learning") { loadTargets(); loadLearning(); }
  if (name === "memory") loadMemory();
  if (name === "privacy") loadDelTargets();
}

for (const link of document.querySelectorAll(".btn--set")) {
  link.addEventListener("click", () =>
    toggleSetBlock(link.dataset.block || "learning"));
}

// F-1R: the first-visit screen. localStorage remembers the visit; a
// storage that refuses (privacy mode) answers "seen" so nobody is
// trapped on the cover page, and a mark that fails to persist costs
// nothing — the parlor does not depend on it.
const ONBOARD_KEY = "elp.parlor.onboarded.v1";

function seenOnboard() {
  try {
    return localStorage.getItem(ONBOARD_KEY) === "1";
  } catch {
    return true;
  }
}

function markOnboarded() {
  try {
    localStorage.setItem(ONBOARD_KEY, "1");
  } catch {
    // 存不进去就下次再问一次：聊天不受影响
  }
}

document.getElementById("ob-go").addEventListener("click", () => {
  markOnboarded();
  showScreen("living");
});

// W-4: the teaching card must not wait for the model. The moment row is
// durable the instant the turn opens it (OPENING), so the page polls the
// read-only current face (served off the work queue — it answers while the
// generation is still running) and re-renders with the turn response.
let momentTimer = null;
let momentPollStart = 0;
const MOMENT_POLL_MS = 400;
const MOMENT_POLL_MAX_MS = 90000;

function stopMomentPolling() {
  if (momentTimer !== null) {
    clearInterval(momentTimer);
    momentTimer = null;
  }
}

function startMomentPolling() {
  stopMomentPolling();
  momentPollStart = Date.now();
  momentTimer = setInterval(async () => {
    if (Date.now() - momentPollStart > MOMENT_POLL_MAX_MS) {
      stopMomentPolling();
      return;
    }
    try {
      const data = await fetchCurrentMoment();
      if (data.moment) showMoments([data.moment]);
    } catch {
      // a failed poll just waits for the next tick; the turn response
      // re-renders the card authoritatively when it lands
    }
  }, MOMENT_POLL_MS);
}

async function postTurn(text) {
  addLine("user", text);
  // the placeholder is the user's "it is working" signal: removed the
  // moment the turn response lands (or fails) — never left behind
  const pending = addLine("typing", "（生成中…）");
  startMomentPolling();
  let data = null;
  try {
    data = await fetchTurn(text);
  } finally {
    stopMomentPolling();
    pending.remove();
  }
  if (data !== null) {
    if (data.reply !== null && data.reply !== undefined) {
      addLine("assistant", data.reply);
    } else if (data.turn_status !== null && data.turn_status !== undefined) {
      addLine("failure", "[" + data.turn_status + "] " +
        (data.failure_reason || "无回复"));
    } else if (data.failure_reason) {
      addLine("failure", data.failure_reason);
    }
    const moments = data.teaching_moments || [];
    showMoments(moments);
    // F-2: a turn that taught nothing says why, in one gray line under
    // the transcript — read from the diagnostics face, silent when the
    // read fails or has nothing to say.
    if (!moments.length) showBlockedNote();
  }
}

document.getElementById("send").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  postTurn(text);
});

// The pen is a lined-paper textarea (the anchor's own .pen): plain Enter
// posts the letter, Shift+Enter stays a line break.
document.getElementById("text").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.getElementById("send").requestSubmit();
  }
});

document.getElementById("obs").addEventListener("click", async () => {
  const out = document.getElementById("obsout");
  const data = await fetchObservations();
  const lines = [];
  for (const ind of data.indicators) {
    lines.push(ind.indicator + " — " + ind.definition);
  }
  lines.push("");
  for (const s of data.sections) {
    lines.push(s.title + ":");
    if (s.error !== null) { lines.push("  (unreadable: " + s.error + ")"); continue; }
    if (!s.rows.length) { lines.push("  (no rows)"); continue; }
    for (const row of s.rows) lines.push("  " + row.join(" | "));
  }
  lines.push("  gate rows naming " + data.drift_reason +
    " (the drift signal): " + data.drift_count);
  out.hidden = false;
  out.textContent = lines.join("\n");
});

async function loadHistory() {
  const data = await fetchHistory();
  for (const turn of data.turns) {
    if (turn.user !== null) addLine("user", turn.user);
    if (turn.assistant !== null) addLine("assistant", turn.assistant);
  }
  // the open teaching moment survives a refresh: rebuild its card (with
  // the attempt box and the skip button) so an open teaching is never
  // stranded without its controls
  const curData = await fetchCurrentMoment();
  if (curData.moment !== null) {
    showMoments([curData.moment]);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  // F-G2: the brand marks (the template's clones) land before the first
  // screen shows, so the cover and both brand bars are never bare.
  installBrandMarks();
  loadHistory();
  // F-1R: the first visit sees the cover; every later visit lands in the
  // parlor directly (the cover never comes back once localStorage says so)
  showScreen(seenOnboard() ? "living" : "onboard");
});
