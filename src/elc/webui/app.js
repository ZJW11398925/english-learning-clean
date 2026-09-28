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

function renderWhyTeach(d) {
  const box = diagBox("why-teach");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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

function renderWhyNot(d) {
  const box = diagBox("why-not-teach");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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

function renderEvidence(d) {
  const box = diagBox("why-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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

function renderSupport(d) {
  const box = diagBox("why-support");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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

function renderDegraded(d) {
  const box = diagBox("why-degraded");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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
  try {
    const data = await fetchDiagnostics();
    renderWhyTeach(data.why_teach);
    renderWhyNot(data.why_not_teach);
    renderEvidence(data.evidence);
    renderSupport(data.support);
    renderDegraded(data.degraded);
  } catch {
    for (const id of ["why-teach", "why-not-teach", "why-evidence",
                      "why-support", "why-degraded"]) {
      diagError(diagBox(id), "诊断读数拉取失败");
    }
  }
}

document.getElementById("diag-refresh").addEventListener("click", loadDiagnostics);

// F-2: the 学习 view — what can be taught, the schedule, the goals and
// the evidence ledger. Read-only numbers under Chinese labels; the one
// act is 教我这个, which asks the runtime to open the teaching.
async function loadTargets() {
  const box = diagBox("target-list");
  box.textContent = "";
  try {
    const data = await fetchTargets();
    const list = data.targets || [];
    if (!list.length) { diagEmpty(box, "暂无可教目标"); return; }
    for (const t of list) {
      const row = document.createElement("div");
      row.className = "kv";
      const b = document.createElement("b");
      b.textContent = t.name || t.target_id;
      row.appendChild(b);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "teach-me";
      button.textContent = "教我这个";
      button.addEventListener("click", () => postTeachMe(t.target_id));
      row.appendChild(button);
      box.appendChild(row);
    }
  } catch {
    diagError(box, "目标清单拉取失败");
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

function renderSchedule(d) {
  const box = diagBox("learn-schedule");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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

function renderGoals(d) {
  const box = diagBox("learn-goals");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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

function renderLearnEvidence(d) {
  const box = diagBox("learn-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
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
  try {
    const data = await fetchLearning();
    renderSchedule(data.schedule);
    renderGoals(data.goals);
    renderLearnEvidence(data.evidence);
  } catch {
    for (const id of ["learn-schedule", "learn-goals", "learn-evidence"]) {
      diagError(diagBox(id), "学习读数拉取失败");
    }
  }
}

document.getElementById("learning-refresh").addEventListener("click",
  () => { loadTargets(); loadLearning(); });

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

// F-1R: the three screens — 开张 / 客厅 / 仪表 — plain show/hide, no
// router, no tab bar: the parlor header's 仪表 link leads to the set
// screen and its 回客厅 link leads back.
const screens = {
  onboard: document.getElementById("screen-onboard"),
  living: document.getElementById("screen-living"),
  set: document.getElementById("screen-set"),
};

function showScreen(name) {
  for (const key of Object.keys(screens)) {
    screens[key].hidden = key !== name;
  }
  window.scrollTo(0, 0);
}

document.getElementById("meter-toggle").addEventListener("click",
  () => showScreen("set"));
document.getElementById("back-to-living").addEventListener("click",
  () => showScreen("living"));

// F-1R: the set screen's two blocks — 学习 and 诊断 — expand in place
// (the F-1R task book leaves the choice to this page, recorded here):
// the expansion pulls the block's read, the refresh links re-pull.
function toggleSetBlock(name) {
  document.getElementById("set-learning").hidden = name !== "learning";
  document.getElementById("set-diagnostics").hidden =
    name !== "diagnostics";
  if (name === "diagnostics") loadDiagnostics();
  if (name === "learning") { loadTargets(); loadLearning(); }
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
  loadHistory();
  // F-1R: the first visit sees the cover; every later visit lands in the
  // parlor directly (the cover never comes back once localStorage says so)
  showScreen(seenOnboard() ? "living" : "onboard");
});
