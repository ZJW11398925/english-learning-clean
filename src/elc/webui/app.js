// app.js —— 装配：空间与节切换（R-1）/ 信流事件 / 轮询 / 学习·记忆·诊断
// 读数渲染（F-G1；R-1R 起屏内信息组织与文案按 ⑧ 设计蓝图 v2 定稿）。
// 只做装配与视图渲染：端点调用只走 api.js，DOM 工厂只走 components.js；
// 文字一律惰性（textContent / 节点拼装，绝不进标记——XSS 面）。装配顺序
// ＝模块加载即绑定（type="module" 天然延迟到文档解析后）。
//
// R-1R 表达面总则（⑧ 8.3 / 8.4）：状态与枚举只出中文（翻译表在本文件
// 集中定义，未知值不兜底伪装——原样等宽小字 .rawtag）；存储词表值中英
// 并置（中文在前，英文等宽小字在后）；时间一律人话格式（title 放全时间
// 戳）；机械原值与 ISO 时间戳的唯一归宿 = 记录页折叠的「原始读数」区。

import {
  addLine,
  letterNode,
  messages,
  showMoments,
  diagEmpty,
  diagError,
  diagLine,
  diagGroup,
  stateBanner,
  installBrandMarks,
  inkIcon,
  installIcons,
  wordWindows,
  showWordCard,
  closeWordCard,
  wordCardOpen,
  applyLetterAffordance,
  confirmDialog,
  fieldRow,
  chip,
  selectField,
  closeOpenSelects,
  wireNavdock,
  markNavdock,
  wireSectionTabs,
  markSectionTabs,
  sectionLabel,
  wirePanelSwipe,
  wirePageTurn,
  playPageTurn,
  disclosure,
  wireReveal,
  restagger,
  envelopeCard,
  layoutEnvelopeStack,
  extendContainer,
  autosizeTo,
  clearAutosize,
  REDUCED_MOTION,
} from "./components.js";
import {
  fetchTurn,
  fetchTeachMe,
  fetchLearning,
  fetchTargets,
  fetchObservations,
  fetchHistory,
  fetchCurrentMoment,
  fetchWord,
  fetchMemory,
  fetchPartner,
  fetchPartnerOf,
  fetchCharacters,
  fetchSwitchCharacter,
  fetchCreateCharacter,
  fetchUpdateCharacter,
  fetchDeleteCharacter,
  fetchDelete,
  fetchGoals,
  fetchSaveGoals,
  fetchSettings,
  fetchSaveTeachingPolicy,
  fetchSaveDisclosure,
  fetchSaveProvider,
} from "./api.js";

// ── v2 品牌名单点常量（简报 §1；改名 = 改这一处）──────────────────
// 门上候选五名（现役默认见 BRAND 值）换名只动这里；index.html 的
// <title> 与信头静态兜底同值（无 JS 兜底），仓内品牌字面值不得有
// 第三处物理点。
const BRAND = { name: "展信佳", tagline: "见字如晤，今日如何", en: "Dear You" };

// ── ⑧ 8.3 术语翻译表（工程词 → 通信语言，唯一集中定义）──────────────
// 总则：状态 / 枚举只出中文；未列出的词不伪装翻译——原样小字（.rawtag）。

const OUTCOME_CN = {
  SUCCESS: "答得漂亮",
  ALTERNATIVE_SUCCESS: "答得漂亮（另一种说法也算）",
  PARTIAL: "答了一半",
  FAILURE: "没答中",
  ABSTAIN: "这次没法判",
};
const REVIEW_STATE_CN = {
  NOT_SCHEDULED: "还没排上",
  UPCOMING: "排上了",
  DUE: "今天到期",
  OVERDUE: "过期了",
};
const FAMILY_CN = {
  discourse: "接话与转题",
  hedge: "留有余地",
  pragmatic: "应对与表态",
  softener: "委婉说法",
};
// 家族组的展示序：四族现役序在前，未知家族按原名排在后（不伪装翻译）
const FAMILY_ORDER = ["discourse", "hedge", "pragmatic", "softener"];
const MODALITY_CN = {
  SPEAKING: "口语",
  LISTENING: "听力",
  READING: "阅读",
  WRITING: "写作",
};
const REGISTER_CN = {
  CASUAL: "随意",
  NEUTRAL: "中性",
  POLITE: "客气",
  FORMAL: "正式",
  ACADEMIC: "学术",
  PERSUASIVE: "说服",
  LITERARY: "文雅",
  PLAYFUL: "俏皮",
};
const FREQUENCY_CN = {
  OFF: "关",
  MINIMAL: "偶尔",
  BALANCED: "适度",
  EAGER: "勤快",
};
const POLARITY_CN = {
  POSITIVE: "正面",
  NEGATIVE: "负面",
  NEUTRAL: "中性",
};
const PERFORMANCE_TYPE_CN = {
  RECOGNITION: "认出来",
  IMITATIVE_PRODUCTION: "跟着写",
  GUIDED_PRODUCTION: "引着写",
  INDEPENDENT_PRODUCTION: "自己写",
  SPONTANEOUS_PRODUCTION: "脱口写出",
  SELF_REPAIR: "自己改对",
  FAILED_ATTEMPT: "写错了",
  MISUSE: "用偏了",
};
const MEMORY_TYPE_CN = {
  USER_STATED_FACT: "你说过的事实",
  SHARED_EVENT: "共同经历",
  PERSONA_IMPRESSION: "伙伴的印象",
  PROMISE: "约定",
  OPEN_THREAD: "未了的话头",
  RUNNING_JOKE: "两人玩笑",
  RELATIONSHIP_EVENT: "关系里的事",
  CONVERSATION_PREFERENCE: "说话的偏好",
};
const ENTITY_KIND_CN = {
  conversation: "这段通信",
  learning_target: "表达",
  relationship_pair: "伙伴关系",
};
const SCOPE_CN = {
  CONVERSATION: "这段通信",
  LEARNING_TARGET: "表达",
  RELATIONSHIP_PAIR: "伙伴关系",
};
const TARGET_TYPE_CN = {
  RESOURCE: "资源",
  CAPABILITY: "能力",
};
const EVIDENCE_MODALITY_CN = {
  TEXT_PRODUCTION: "写下的英语",
  TEXT_COMPREHENSION: "读懂的英语",
};

// ── 表达面小件（单点 helper）─────────────────────────────────────────

function diagBox(id) {
  return document.getElementById(id);
}

function fmtNum(value) {
  return (value === null || value === undefined) ? "—" : String(value);
}

// 原文小字：机械事实（英文原词 / id / 指纹 / 版本）的等宽小字形态
function rawTag(text) {
  const tag = document.createElement("span");
  tag.className = "rawtag";
  tag.textContent = String(text);
  return tag;
}

// 中英并置：中文在前 + 英文等宽小字在后（⑧ 8.3 存储词表值形态）
function biLabel(cn, en) {
  const frag = document.createDocumentFragment();
  frag.appendChild(document.createTextNode(String(cn) + " "));
  frag.appendChild(rawTag(en));
  return frag;
}

// 时间人话化（⑧ 8.3：今天 14:05 / 昨天 / 9 月 21 日；跨年只到「去年」
// 为止）；全时间戳放 title。解析不了的原样直出（不造时间）。
function humanTime(iso) {
  const then = new Date(String(iso));
  if (Number.isNaN(then.getTime())) return String(iso);
  const now = new Date();
  const hh = String(then.getHours()).padStart(2, "0");
  const mm = String(then.getMinutes()).padStart(2, "0");
  if (then.getFullYear() === now.getFullYear() &&
      then.getMonth() === now.getMonth() &&
      then.getDate() === now.getDate()) {
    return "今天 " + hh + ":" + mm;
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (then.getFullYear() === yesterday.getFullYear() &&
      then.getMonth() === yesterday.getMonth() &&
      then.getDate() === yesterday.getDate()) {
    return "昨天";
  }
  if (then.getFullYear() === now.getFullYear()) {
    return (then.getMonth() + 1) + " 月 " + then.getDate() + " 日";
  }
  return "去年";
}

function whenNode(iso) {
  const span = document.createElement("span");
  span.title = String(iso);
  span.textContent = humanTime(iso);
  return span;
}

// 分量 / 门槛：浮点收三位小数进屏（浮点噪声不进屏），原值放 title
function scoreNode(value) {
  const span = document.createElement("span");
  if (value === null || value === undefined) {
    span.textContent = "—";
    return span;
  }
  const num = Number(value);
  span.textContent = Number.isFinite(num)
    ? String(Number(num.toFixed(3)))
    : String(value);
  span.title = String(value);
  return span;
}

// 指纹：前 12 位等宽 + title 全值（⑧ 8.3 entity_hash 行）
function shortHash(hash) {
  const span = rawTag(String(hash).slice(0, 12));
  span.title = String(hash);
  return span;
}

// 表达名：界面只显示 spoken 形（⑧ 8.3）——res-hedge-i-think → i think；
// canonical_key（无 res-/cap- 前缀的键）同法去连字符。R-1V：竖线五段的
// 探针全键（i think|PROBE|TEXT_PRODUCTION|…）只念首段——⑧ 8.0.2 定的
// 「全键与浮点不进信流」对探针键同样成立。
function spokenOf(keyOrId) {
  const text = String(keyOrId).split("|")[0];
  const parts = text.split("-");
  if (parts.length > 2 && (parts[0] === "res" || parts[0] === "cap")) {
    return parts.slice(2).join(" ");
  }
  return parts.join(" ");
}

// 词表值的界面形：有中文译名 → 中英并置（中文 + 等宽小字原文）；未列出
// 的词不伪装翻译——原文等宽小字
function vocabNode(cnMap, word) {
  if (cnMap[word]) return biLabel(cnMap[word], word);
  return rawTag(word);
}

// 摘要行（⑧ 8.2.3 / 8.2.6：屏级一行 .sub + mono 数字，非组件不入库）
function renderSummaryLine(id, pairs) {
  const line = diagBox(id);
  line.hidden = false;
  line.textContent = "";
  pairs.forEach((pair, index) => {
    if (index > 0) line.appendChild(document.createTextNode(" · "));
    line.appendChild(document.createTextNode(pair[0] + " "));
    const num = document.createElement("span");
    num.className = "sumnum";
    num.textContent = String(pair[1]);
    line.appendChild(num);
  });
}

// 失败行（⑧ 8.4：人话主句 + 括号工程词，工程词等宽小字）
function failLine(main, reason) {
  const line = document.createElement("p");
  line.className = "errline";
  line.appendChild(document.createTextNode(main + "（"));
  line.appendChild(rawTag(reason));
  line.appendChild(document.createTextNode("）。"));
  messages.appendChild(line);
  window.scrollTo(0, document.body.scrollHeight);
}

// ── 记录页 · 账（在学的表达）────────────────────────────────────────
// schedule ∪ claims 客户端按 target_id 合流成一张表（⑧ 8.2.5：表达 /
// 痕迹数 / 最近判分 / 复习；无新端点，纯前端重组）。

function renderRecordBook(schedule, evidence, retry) {
  const box = diagBox("record-book");
  box.textContent = "";
  if (!schedule || schedule.error) {
    diagError(box, (schedule && schedule.error) || "空响应", retry);
    return;
  }
  if (!evidence || evidence.error) {
    diagError(box, (evidence && evidence.error) || "空响应", retry);
    return;
  }
  const byTarget = new Map();
  for (const item of schedule.items || []) {
    byTarget.set(item.target_id, { schedule: item, claims: [] });
  }
  for (const claim of evidence.claims || []) {
    let entry = byTarget.get(claim.target_id);
    if (!entry) {
      entry = { schedule: null, claims: [] };
      byTarget.set(claim.target_id, entry);
    }
    entry.claims.push(claim);
  }
  if (!byTarget.size) {
    diagEmpty(box, "还没有在学任何表达——批注来过才会有账。");
    return;
  }
  const rows = [];
  for (const [targetId, entry] of byTarget) {
    // the claims come newest-first; the first sighting is the latest verdict
    const latestClaim = entry.claims.length ? entry.claims[0] : null;
    const at = latestClaim ? latestClaim.created_at
      : (entry.schedule ? entry.schedule.updated_at : "");
    rows.push({ targetId, entry, latestClaim, at });
  }
  rows.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
  for (const row of rows) {
    const line = document.createElement("div");
    line.className = "kv";
    line.title = row.targetId;
    const b = document.createElement("b");
    b.textContent = spokenOf(row.targetId);
    line.appendChild(b);
    line.appendChild(document.createTextNode(
      "痕迹 " + row.entry.claims.length + " 条"));
    if (row.latestClaim) {
      line.appendChild(document.createTextNode(
        " · 最近 " +
        (OUTCOME_CN[row.latestClaim.outcome] ||
         row.latestClaim.outcome) + "（"));
      line.appendChild(whenNode(row.latestClaim.created_at));
      line.appendChild(document.createTextNode("）"));
    } else {
      line.appendChild(document.createTextNode(" · 最近 ——"));
    }
    line.appendChild(document.createTextNode(
      " · " + (row.entry.schedule
        ? (REVIEW_STATE_CN[row.entry.schedule.review_state] ||
           row.entry.schedule.review_state)
        : REVIEW_STATE_CN.NOT_SCHEDULED)));
    box.appendChild(line);
    box.appendChild(footprintZone(row.targetId));
  }
}

// 表达足迹区（主线-2）：按表达看每行下挂一枚「足迹」钮——第一次点开
// 才拉 /api/target_footprint（惰性，不打开不花一次读）；三态全部如实：
// 拉取失败可重试、没有证据「还没有留下学习足迹」、有足迹按轮列
// （轮次序数 + 条数 + 判分，判分走 OUTCOME_CN 中文读法、未知值原样；
// 无轮次序的落 turn_id 短值）。再点收起；重开不重拉（读时取数的
// 保鲜由重进节自然承担）。
function footprintZone(targetId) {
  const wrap = document.createElement("div");
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "btn btn--pencil";
  toggle.textContent = "足迹";
  const body = document.createElement("div");
  body.hidden = true;
  wrap.appendChild(toggle);
  wrap.appendChild(body);
  toggle.addEventListener("click", () => {
    body.hidden = !body.hidden;
    if (!body.hidden && !body.dataset.loaded) {
      loadFootprint(body, targetId);
    }
  });
  return wrap;
}

async function loadFootprint(body, targetId) {
  body.textContent = "";
  body.appendChild(stateBanner("loading", { text: "足迹正在来的路上……" }));
  let d = null;
  try {
    d = await fetchTargetFootprint(targetId);
  } catch {
    d = null;
  }
  body.textContent = "";
  if (!d) {
    const err = document.createElement("p");
    err.className = "note";
    err.textContent = "足迹没取到。";
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "btn btn--pencil";
    retry.textContent = "再试一次";
    retry.addEventListener("click", () => loadFootprint(body, targetId));
    body.appendChild(err);
    body.appendChild(retry);
    return;
  }
  body.dataset.loaded = "1";
  if (!d.found) {
    const none = document.createElement("p");
    none.className = "note";
    none.textContent = "这个表达还没有留下学习足迹。";
    body.appendChild(none);
    return;
  }
  const head = document.createElement("p");
  head.className = "sub";
  head.textContent = "学习足迹 " + d.active_claim_count + " 条，散在 "
    + d.turns.length + " 轮里：";
  body.appendChild(head);
  for (const t of d.turns) {
    const line = document.createElement("div");
    line.className = "kv";
    line.title = t.turn_id;
    const where = document.createElement("b");
    where.textContent = (t.turn_sequence !== null
      && t.turn_sequence !== undefined)
      ? "第 " + t.turn_sequence + " 轮"
      : String(t.turn_id).slice(0, 12);
    line.appendChild(where);
    line.appendChild(document.createTextNode(
      " · " + t.claim_count + " 条（"
      + t.outcomes.map((o) => OUTCOME_CN[o] || o).join("、") + "）"));
    body.appendChild(line);
  }
}

// ── 档案 · 折叠明细（rd-3 降级位）────────────────────────────────────
// 三面原值渲染器保持原样——原值在折叠区里是合法形态（机械事实的唯一
// 归宿 = 折叠的原始读数，⑧ 8.4.3）。排程与目标降入「计划明细」折叠
// （时间敏感的是今天不是下周——默认层只留计划一行）；账表降入
// 「按表达看」折叠。

// 复习调度区（主线-2）：/api/schedule 的三态，全部如实——
// ① 调度腿没装配（available=false）＝「没有可显示的排程」，不虚构；
// ② 腿在但无到期/已排期行＝诚实空态；③ 有行＝Scheduler 自己的分档
// 视图（今日到期 = DUE+OVERDUE 在前，接下来 = UPCOMING 窗口落点）。
// 行字段落原值（间隔阶是实现词表，原样直出不造中文；无阶 = 未分阶，
// types 的自有读法）；窗口时间 = 机械事实走 whenNode。
async function loadScheduleZone() {
  const box = diagBox("learn-schedule");
  box.textContent = "";
  box.appendChild(stateBanner("loading", { text: "复习排程正在来的路上……" }));
  let d = null;
  try {
    d = await fetchSchedule();
  } catch {
    d = null;
  }
  box.textContent = "";
  if (!d) {
    diagError(box, "复习调度拉取失败", loadScheduleZone);
    return;
  }
  if (d.available === false) {
    diagEmpty(box, "复习调度腿没有装配——现在没有可显示的排程。");
    return;
  }
  const due = (d.due || []).concat(d.overdue || []);
  const upcoming = d.upcoming || [];
  if (!due.length && !upcoming.length) {
    diagEmpty(box, "现在没有到期或已排期的复习——批注来过才会排。");
    return;
  }
  if (due.length) {
    const head = document.createElement("p");
    head.className = "sub";
    head.textContent = "今日到期 " + due.length + " 项";
    box.appendChild(head);
    for (const it of due) box.appendChild(scheduleRow(it));
  }
  if (upcoming.length) {
    const head = document.createElement("p");
    head.className = "sub";
    head.textContent = "接下来 " + upcoming.length + " 项";
    box.appendChild(head);
    for (const it of upcoming) box.appendChild(scheduleRow(it));
  }
}

// 调度区一行：表达名 + 复习状态（中文，未知值原样）+ 窗口落点 + 间隔阶。
function scheduleRow(it) {
  const line = document.createElement("div");
  line.className = "kv";
  line.title = it.target_id;
  const b = document.createElement("b");
  b.textContent = it.name || spokenOf(it.target_id);
  line.appendChild(b);
  line.appendChild(document.createTextNode(
    " · " + (REVIEW_STATE_CN[it.review_state] || it.review_state)));
  if (it.next_review_window_start) {
    line.appendChild(document.createTextNode(" · 窗口 "));
    line.appendChild(whenNode(it.next_review_window_start));
  }
  line.appendChild(document.createTextNode(
    " · 间隔阶 " + (it.spacing_stage || "未分阶")));
  return line;
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

// ── rd-3: 档案节拉取（进节即拉）——档案板的进行时占位先落（NN/g：
// 未加载不得显示无记录，「批注正在来的路上……」区别于空态的「还没有」
// ——8.2.5 加载态两形）；其余面板走统一 loading banner。可练的表达
// 从本节自己的 targets 拉取（家族分组筛框照旧）。
async function loadLearning() {
  const board = diagBox("archive-board");
  board.textContent = "";
  board.appendChild(stateBanner("loading",
    { text: "批注正在来的路上……" }));
  showLoading(LEARN_PANEL_IDS);
  try {
    const data = await fetchLearning();
    renderArchive(data.evidence, loadLearning);
    renderPlanLine(data.schedule, loadLearning);
    renderRecordBook(data.schedule, data.evidence, loadLearning);
    renderGoals(data.goals, loadLearning);
    renderLearnEvidence(data.evidence, loadLearning);
  } catch {
    for (const id of LEARN_PANEL_IDS) {
      diagError(diagBox(id), "学习读数拉取失败", loadLearning);
    }
    board.textContent = "";
    diagError(board, "学习读数拉取失败", loadLearning);
    return;
  }
  // 复习调度区走自己的读面（主线-2：/api/schedule 三态），失败独立
  // 降级——不拖累 /api/learning 的其余面板。
  loadScheduleZone();
  let targets = null;
  try {
    targets = await fetchTargets();
  } catch {
    targets = null;
  }
  renderTodayPractice(targets, loadLearning);
}

// ── rd-3: 温故默认层与档案（⑧ 8.2.3 / 8.2.5，rd-3 IA 重构）──────────
// 默认层（今日节）恰两块：今天的行动（到期 N 项 + 进行中的批注 + 一个
// 动词按钮；N=0 时一句邀请）/ 你的成长（恰 3 条词级结论——聚合自批注
// 判分，不是分数是结论；空态 = pull-revelation 卡）。环块诚实省略：
// 无可靠的连续天数数据源，今日进度又与行动块重复（豁免登记 9.11-22）。
// 档案节（原记录节）：搜索 + 聚合时间线 + 计划一行 + 可以练的表达 +
// 按表达看 + 原始读数深档。诊断五问与页首计数摘要行已移出用户面
// （9.11-22 移走清单：内部决策理由 = 噪音，计数是副产品）。

const TODAY_PANEL_IDS = ["today-action", "growth-summary"];
// archive-board 不在此列（OCR rd-3 处置二）：它有自己的进行时占位
// （「批注正在来的路上……」），通用横幅会整板覆盖定制态；错误路径
// 也由 loadLearning 的 catch 单独处理，无需循环重复清板。
const LEARN_PANEL_IDS = ["plan-line", "record-book",
                         "learn-schedule", "learn-goals", "learn-evidence",
                         "today-practice"];

function showLoading(ids) {
  for (const id of ids) {
    const box = diagBox(id);
    box.textContent = "";
    box.appendChild(stateBanner("loading"));
  }
}

// 回案头的直达按钮（行动块的邀请态与成长空态共用）——动作词，落点
// 是案头信流（教学批注与聊天都发生在那里）
function parlorButton(word) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn--ink";
  button.textContent = word;
  button.addEventListener("click", () => showSpace("parlor"));
  return button;
}

function teachRow(name, targetId) {
  const row = document.createElement("div");
  row.className = "kv";
  const b = document.createElement("b");
  b.textContent = name;
  row.appendChild(b);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "teach-me";
  button.textContent = "教我这一句";
  button.addEventListener("click", () => postTeachMe(targetId));
  row.appendChild(button);
  return row;
}

// R-1R（⑧ 8.2.3 / 8.2.7）：52 行的解法——家族分组（组键 = target_id
// 第二段，客户端派生）+ #21 折叠组（默认收）+ 筛框（输入即展开命中组
// 并过滤行，无命中说一句真话）。rowFor(t) 造一行；筛面 = 表达名 +
// 原 id 一并小写匹配。
function familyGroupsBlock(list, rowFor) {
  const root = document.createElement("div");
  // R-1W：家族折叠组容器带上 .family-groups——平板档起两栏网格的挂点
  // （screens.css 断点系统；窄屏自然单栏）
  root.className = "family-groups";
  const input = document.createElement("input");
  input.type = "text";
  input.autocomplete = "off";
  input.placeholder = "找一个表达……";
  // R-1V：筛框名牌配 search 墨线小图（#22）——图是装饰，「找」字仍在
  const findLabel = document.createDocumentFragment();
  findLabel.appendChild(inkIcon("search"));
  findLabel.appendChild(document.createTextNode(" 找"));
  root.appendChild(fieldRow(findLabel, input));
  const noHit = document.createElement("p");
  noHit.className = "note";
  noHit.hidden = true;
  noHit.textContent = "没有叫这个的表达。";
  root.appendChild(noHit);
  const byFamily = new Map();
  for (const item of list) {
    const family = familyOf(item.target_id);
    if (!byFamily.has(family)) byFamily.set(family, []);
    byFamily.get(family).push(item);
  }
  const families = Array.from(byFamily.keys()).sort((a, b) => {
    const ia = FAMILY_ORDER.indexOf(a);
    const ib = FAMILY_ORDER.indexOf(b);
    const ra = ia < 0 ? FAMILY_ORDER.length : ia;
    const rb = ib < 0 ? FAMILY_ORDER.length : ib;
    if (ra !== rb) return ra - rb;
    return a < b ? -1 : a > b ? 1 : 0;
  });
  const groups = [];
  for (const family of families) {
    const rows = byFamily.get(family);
    const disc = disclosure({
      name: FAMILY_CN[family] || family || "其他",
      count: rows.length,
      examples: rows.slice(0, 2).map(
        (t) => t.name || spokenOf(t.target_id)),
    });
    const built = [];
    for (const t of rows) {
      const node = rowFor(t);
      built.push({
        node,
        probe: ((t.name || "") + " " + t.target_id).toLowerCase(),
      });
      disc.body.appendChild(node);
    }
    groups.push({ disc, rows: built });
    root.appendChild(disc.root);
  }
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    let any = false;
    const shown = [];
    for (const g of groups) {
      if (!q) {
        g.disc.root.hidden = false;
        g.disc.setOpen(false);
        for (const r of g.rows) r.node.hidden = false;
        any = true;
        continue;
      }
      let hit = false;
      for (const r of g.rows) {
        const on = r.probe.includes(q);
        r.node.hidden = !on;
        if (on) {
          hit = true;
          shown.push(r.node);
        }
      }
      g.disc.root.hidden = !hit;
      g.disc.setOpen(hit);
      if (hit) any = true;
    }
    noHit.hidden = any;
    // fr-B 列表进出场：搜索结果逐项错峰（stagger 28ms 档，前 8 项封顶
    // ——components.js restagger；reduced-motion 其 JS 半区直切）。
    // 目标列表（可以练的表达 / 按表达忘掉）与搜索结果同一工厂同一面。
    if (q) restagger(shown);
  });
  return root;
}

// the family key of a target id — the second dash segment
// (res-discourse-… → discourse), derived client-side like the spoken name
function familyOf(targetId) {
  const parts = String(targetId).split("-");
  return parts.length > 2 ? parts[1] : "";
}

// 成长三档的词级表达（能 / 还在练 / 暂时不能）——判分枚举到词的
// 唯一映射；数值不入本屏（9.11-22：词级表达替代内部档位）
const GROWTH_LINES = 3;
const GROWTH_VERDICTS = [
  { outcomes: ["SUCCESS", "ALTERNATIVE_SUCCESS"], word: "能做到" },
  { outcomes: ["PARTIAL", "ABSTAIN"], word: "还在练" },
  { outcomes: ["FAILURE"], word: "暂时不能" },
];

// 块② 你的成长（⑧ 8.2.3）：恰 3 条词级结论句——每个表达取最新一次
// 判分，归入三档；能做到优先、同档按最近活跃（claims 最新在前），
// 取 3 条（调研B：恒 3 条是选出来的，不是全放出来的）。不足 3 条时
// 如实显示有的几条；0 条 = pull-revelation 空态卡（给学习线索与
// 直达路径，NN/g）。不显示数值、档位、置信度。
function renderGrowth(evidence, retry) {
  const box = diagBox("growth-summary");
  box.textContent = "";
  if (!evidence || evidence.error) {
    diagError(box, (evidence && evidence.error) || "空响应", retry);
    return;
  }
  const claims = evidence.claims || [];
  if (!claims.length) {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = "学过一次之后，这里会出现你掌握的技能。";
    box.appendChild(note);
    const hint = document.createElement("p");
    hint.className = "sub";
    hint.textContent = "先去案头聊一句，批注会自己来找你。";
    box.appendChild(hint);
    box.appendChild(parlorButton("去聊一句"));
    return;
  }
  // the claims come newest-first; the first sighting of a target is its
  // most recent verdict
  const latest = new Map();
  for (const claim of claims) {
    if (!latest.has(claim.target_id)) latest.set(claim.target_id, claim);
  }
  const rows = [];
  for (const verdict of GROWTH_VERDICTS) {
    for (const [targetId, claim] of latest) {
      if (verdict.outcomes.includes(claim.outcome)) {
        rows.push({ targetId, word: verdict.word });
      }
    }
  }
  for (const row of rows.slice(0, GROWTH_LINES)) {
    const line = document.createElement("div");
    line.className = "kv";
    line.appendChild(document.createTextNode(
      row.word + "：" + spokenOf(row.targetId) + "。"));
    box.appendChild(line);
  }
}

// 块① 今天的行动（⑧ 8.2.3）：到期复习 N 项 + 进行中的批注 + 一个
// 动词按钮。按钮 = 当前第一优先的行动（批注回应 > 到期复习 > 邀请）；
// 「开始复习」直接开教第一句到期句（真动作，不是导航）。
function renderTodayAction(schedule, moment, retry) {
  const box = diagBox("today-action");
  box.textContent = "";
  if (!schedule || schedule.error) {
    diagError(box, (schedule && schedule.error) || "空响应", retry);
    return;
  }
  const due = (schedule.items || []).filter(
    (it) => it.review_state === "DUE" || it.review_state === "OVERDUE");
  if (moment) {
    const line = document.createElement("p");
    line.className = "sub";
    line.textContent = "有一张批注等着你回应。";
    box.appendChild(line);
    box.appendChild(parlorButton("去回应"));
  }
  for (const it of due) {
    box.appendChild(teachRow(
      spokenOf(it.target_id) + " · " +
      (REVIEW_STATE_CN[it.review_state] || it.review_state),
      it.target_id));
  }
  if (moment) return;
  if (due.length) {
    const start = document.createElement("button");
    start.type = "button";
    start.className = "btn btn--ink";
    start.textContent = "开始复习";
    start.addEventListener("click", () => postTeachMe(due[0].target_id));
    box.appendChild(start);
    return;
  }
  const line = document.createElement("p");
  line.className = "sub";
  line.textContent = "今天不用复习，要不要聊一句？";
  box.appendChild(line);
  box.appendChild(parlorButton("去聊一句"));
}

// 可以练的表达（rd-3 迁入档案节；家族分组 + 默认折叠 + 筛框不变——
// 组键 = target_id 第二段，客户端派生；筛框就是这个折叠自己的搜索）
function renderTodayPractice(targets, retry) {
  const box = diagBox("today-practice");
  box.textContent = "";
  if (!targets || targets.error) {
    diagError(box, (targets && targets.error) || "空响应", retry);
    return;
  }
  const list = targets.targets || [];
  if (!list.length) {
    diagEmpty(box, "还没有可练的表达——语料还没有铺到这里。");
    return;
  }
  box.appendChild(familyGroupsBlock(list,
    (t) => teachRow(t.name || spokenOf(t.target_id), t.target_id)));
}

// 档案 · 痕迹（⑧ 8.2.5）：Wrapped 期待态 + 搜索框 + 聚合时间线。
// 读数口径：明细只有服务端已加载的最近几条（web.py 的窗口，冻结面故
// 口径如实呈现——「已加载的」）；Wrapped 计数读全量 evidence_claim_count。
// 门槛不足时讲期待不讲遗憾（调研B：数据不够就不解锁）；时间线桶 =
// 本周 / 上周 / {m} 月 / 去年 / 更早，桶行一句、点开见明细。
const ARCHIVE_STORY_GATE = 30;

function timeBucketLabel(iso) {
  const then = new Date(String(iso));
  if (Number.isNaN(then.getTime())) return "更早";
  const now = new Date();
  const dayMs = 86400000;
  const midnight = (d) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const mondayOffset = (now.getDay() + 6) % 7;
  const thisMonday = midnight(now) - mondayOffset * dayMs;
  const t = then.getTime();
  if (t >= thisMonday) return "本周";
  if (t >= thisMonday - 7 * dayMs) return "上周";
  if (then.getFullYear() === now.getFullYear()) {
    return (then.getMonth() + 1) + " 月";
  }
  if (then.getFullYear() === now.getFullYear() - 1) return "去年";
  return "更早";
}

function renderArchive(evidence, retry) {
  const board = diagBox("archive-board");
  board.textContent = "";
  if (!evidence || evidence.error) {
    diagError(board, (evidence && evidence.error) || "空响应", retry);
    return;
  }
  const claims = evidence.claims || [];
  const total = evidence.evidence_claim_count || 0;
  if (!claims.length) {
    diagEmpty(board, "还没有批注留痕——聊起来才会有。");
    if (total < ARCHIVE_STORY_GATE) {
      const wish = document.createElement("p");
      wish.className = "sub";
      wish.textContent = "攒够 " + ARCHIVE_STORY_GATE +
        " 次批注，这里会讲一个学期的故事——现在有 " + total + " 条。";
      board.appendChild(wish);
    }
    return;
  }
  if (total < ARCHIVE_STORY_GATE) {
    const wish = document.createElement("p");
    wish.className = "sub";
    wish.textContent = "攒够 " + ARCHIVE_STORY_GATE + " 次批注，这里会讲一个学期的故事——现在有 " + total + " 条。";
    board.appendChild(wish);
  }
  const input = document.createElement("input");
  input.type = "text";
  input.autocomplete = "off";
  input.placeholder = "搜一句痕迹……";
  const findLabel = document.createDocumentFragment();
  findLabel.appendChild(inkIcon("search"));
  findLabel.appendChild(document.createTextNode(" 搜"));
  board.appendChild(fieldRow(findLabel, input));
  const noHit = document.createElement("p");
  noHit.className = "note";
  noHit.hidden = true;
  noHit.textContent = "没搜到这一句的痕迹。";
  board.appendChild(noHit);
  // 聚合时间线：claims 最新在前，桶按首次出现即时间倒序
  const order = [];
  const buckets = new Map();
  for (const claim of claims) {
    const bucket = timeBucketLabel(claim.created_at);
    if (!buckets.has(bucket)) {
      buckets.set(bucket, []);
      order.push(bucket);
    }
    buckets.get(bucket).push(claim);
  }
  const groups = [];
  for (const bucket of order) {
    const rows = buckets.get(bucket);
    const themes = [];
    for (const claim of rows) {
      const name = spokenOf(claim.target_id);
      if (!themes.includes(name)) themes.push(name);
      if (themes.length >= 2) break;
    }
    const body = document.createElement("div");
    const built = [];
    for (const claim of rows) {
      const line = document.createElement("div");
      line.className = "kv";
      const b = document.createElement("b");
      b.textContent = spokenOf(claim.target_id);
      line.appendChild(b);
      line.appendChild(document.createTextNode(
        (OUTCOME_CN[claim.outcome] || claim.outcome) + "（"));
      line.appendChild(whenNode(claim.created_at));
      line.appendChild(document.createTextNode("）"));
      // v2：判分行不盖章——邮戳只落三类真实事件（寄出/结课/归档开启，
      // 简报 T2），判分行不在其中；判词文字（中文判词打头）已是完整
      // 信息。旧判分戳随 v2 撤除（缺位钉在 rd4 套件）。
      // 行本身是 .kv 等宽形——日期的 mono 即此。
      body.appendChild(line);
      built.push({
        node: line,
        // rd-4 中文 probe（rd-3 INFO-4 收口）：族名与判词的中文读法
        // 并入检索串——「接话」「答得漂亮」也搜得到
        probe: ((spokenOf(claim.target_id) + " " + claim.target_id + " " +
                 (FAMILY_CN[familyOf(claim.target_id)] || "") + " " +
                 (OUTCOME_CN[claim.outcome] || ""))
                .toLowerCase()),
      });
    }
    const disc = disclosure({
      name: bucket + "：" + rows.length + " 次批注，主题 " +
        themes.join(" / "),
      content: body,
    });
    groups.push({ disc, rows: built });
    board.appendChild(disc.root);
  }
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    let any = false;
    const shown = [];
    for (const g of groups) {
      if (!q) {
        g.disc.root.hidden = false;
        g.disc.setOpen(false);
        for (const r of g.rows) r.node.hidden = false;
        any = true;
        continue;
      }
      let hit = false;
      for (const r of g.rows) {
        const on = r.probe.includes(q);
        r.node.hidden = !on;
        if (on) {
          hit = true;
          shown.push(r.node);
        }
      }
      g.disc.root.hidden = !hit;
      g.disc.setOpen(hit);
      if (hit) any = true;
    }
    noHit.hidden = any;
    // fr-B 列表进出场：搜索结果逐项错峰（stagger 28ms 档，前 8 项封顶
    // ——components.js restagger；reduced-motion 其 JS 半区直切）。
    // 目标列表（可以练的表达 / 按表达忘掉）与搜索结果同一工厂同一面。
    if (q) restagger(shown);
  });
}

// 档案 · 计划（⑧ 8.2.5）：未来 7 天一行——今天 = DUE/OVERDUE；
// 明天/往后 = UPCOMING 的复习窗口落点（窗口落在过去或 7 天外的
// UPCOMING 不上数，口径如实）。全量排程与目标降入下方折叠明细。
function renderPlanLine(schedule, retry) {
  const box = diagBox("plan-line");
  box.textContent = "";
  if (!schedule || schedule.error) {
    diagError(box, (schedule && schedule.error) || "空响应", retry);
    return;
  }
  const items = schedule.items || [];
  if (!items.length) {
    diagEmpty(box, "还没有排程——批注来过才会排。");
    return;
  }
  const due = items.filter(
    (it) => it.review_state === "DUE" || it.review_state === "OVERDUE"
  ).length;
  const dayMs = 86400000;
  const midnight = (d) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const today = midnight(new Date());
  let tomorrow = 0;
  let later = 0;
  for (const it of items) {
    if (it.review_state !== "UPCOMING") continue;
    const start = it.next_review_window_start
      ? new Date(String(it.next_review_window_start)).getTime() : NaN;
    if (Number.isNaN(start)) continue;
    const offset = Math.floor(
      (midnight(new Date(start)) - today) / dayMs);
    if (offset === 1) tomorrow += 1;
    else if (offset >= 2 && offset <= 6) later += 1;
  }
  const line = document.createElement("p");
  line.className = "sub";
  line.textContent = "未来 7 天：今天 " + due + "、明天 " + tomorrow +
    "、往后 " + later + "。";
  box.appendChild(line);
}

async function loadToday() {
  showLoading(TODAY_PANEL_IDS);
  let learning = null;
  let moment = null;
  try {
    learning = await fetchLearning();
  } catch {
    learning = null;
  }
  try {
    const current = await fetchCurrentMoment();
    moment = current.moment;
  } catch {
    moment = null;
  }
  renderTodayAction(
    learning === null ? null : learning.schedule, moment, loadToday);
  renderGrowth(
    learning === null ? null : learning.evidence, loadToday);
}

// ── p-2 / R-1R / cs-2: 记忆页 —— 摘要行 + 三摞五面板。cs-2 重组：
// 归属分区（角色记忆 / 学习记录 / 存根）由 /api/memory 的 domain 字段
// 分组落位（错位即搬家——分区是服务端声明的，页面照它归垛）；五个面板
// 各是一件 #21 折叠（默认收，组头 = 面板名 + 计数）。字段名全中文化；
// 指纹缩前 12 位；时间一律人话。 ─────────────────────────────────────

const MEM_PANEL_IDS = ["mem-relationship", "mem-episode", "mem-states",
                       "mem-evidence", "mem-tombstones"];

// cs-2 三摞：domain 词 → 摞容器与归属标注（标注文字在 index.html 的
// 摞头上，此处只持容器 id 与名）。domain 缺席/未知 = 面板留在原地，
// 不发明第四摞。
const MEM_ZONES = {
  character: { box: "mem-zone-character" },
  learning: { box: "mem-zone-learning" },
  audit: { box: "mem-zone-audit" },
};

// 分区消费：把面板槽搬进它的 domain 点名的摞（页面初次装载已在
// 静态归位处——服务端改口时这里跟着搬）。
function placePanel(panel, slotId) {
  const zone = MEM_ZONES[panel && panel.domain];
  if (!zone) return;
  const slot = diagBox(slotId);
  const container = diagBox(zone.box);
  if (!container.contains(slot)) container.appendChild(slot);
}

// 面板折叠（cs-2）：面板名 + 计数做组头，内容默认收；返回内容体。
function mountPanelDisclosure(slot, name, count) {
  slot.textContent = "";
  const body = document.createElement("div");
  slot.appendChild(disclosure({
    name: name,
    count: count,
    content: body,
  }).root);
  return body;
}

// 计数口径：面板负载体里的行数（证据面是 claims 计数列）。
function panelCount(panel, key) {
  if (!panel || panel.error) return undefined;
  if (key === "claims") return panel.evidence_claim_count || 0;
  return (panel[key] || []).length;
}

function renderMemRelationship(d, retry, box) {
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.memories || [];
  if (!rows.length) {
    diagEmpty(box, "还没记住什么——把你的事写进信里（名字、住的地方、喜欢的事），她会记下来。");
    return;
  }
  for (const m of rows) {
    const head = document.createDocumentFragment();
    head.appendChild(document.createTextNode(
      (MEMORY_TYPE_CN[m.memory_type] || "") + " "));
    head.appendChild(rawTag(m.memory_type + " · " + m.status));
    const g = diagGroup(box, head);
    diagLine(g, "记住的内容", m.canonical_content);
    diagLine(g, "从哪记住的", rawTag(m.provenance));
    diagLine(g, "敏感程度",
      rawTag(m.sensitivity_class + " / " + m.persistence_authorization));
    if (m.confidence !== null && m.confidence !== undefined) {
      diagLine(g, "把握", scoreNode(m.confidence));
    }
    diagLine(g, "时间", whenNode(m.updated_at));
  }
}

function renderMemEpisode(d, retry, box) {
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.episodes || [];
  if (!rows.length) {
    diagEmpty(box, "还没有记住什么——没有一段对话被总结成剧情。");
    return;
  }
  for (const e of rows) {
    const head = document.createDocumentFragment();
    head.appendChild(document.createTextNode("这段通信 "));
    head.appendChild(rawTag(e.conversation_id));
    const g = diagGroup(box, head);
    diagLine(g, "摘要", e.summary);
    diagLine(g, "未了的话头",
      Array.isArray(e.open_threads) ? e.open_threads.join("；") : fmtNum(e.open_threads));
    diagLine(g, "最近的事",
      Array.isArray(e.recent_events) ? e.recent_events.join("；") : fmtNum(e.recent_events));
    diagLine(g, "状态", rawTag(e.status));
    diagLine(g, "时间", whenNode(e.updated_at));
  }
}

function renderMemStates(d, retry, box) {
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.states || [];
  if (!rows.length) {
    diagEmpty(box, "还没有记住什么——还没有任何痕迹积累到这里。");
    return;
  }
  for (const s of rows) {
    const head = document.createDocumentFragment();
    head.appendChild(document.createTextNode(spokenOf(s.target_id) + " "));
    head.appendChild(rawTag(s.target_id));
    const g = diagGroup(box, head);
    diagLine(g, "目标种类", vocabNode(TARGET_TYPE_CN, s.target_type));
    diagLine(g, "凭据渠道",
      vocabNode(EVIDENCE_MODALITY_CN, s.evidence_modality));
    diagLine(g, "证据水位", fmtNum(s.evidence_watermark));
    diagLine(g, "记着哪些状态", Array.isArray(s.state_keys)
      ? (s.state_keys.length ? s.state_keys.join("、") : "（空）") : "—");
    diagLine(g, "估算法版本", rawTag(s.estimator_version));
    diagLine(g, "时间", whenNode(s.updated_at));
  }
}

function renderMemEvidence(d, retry, box) {
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const claimCount = document.createDocumentFragment();
  claimCount.appendChild(document.createTextNode(
    (d.evidence_claim_count || 0) + " 条 "));
  claimCount.appendChild(rawTag("（evidence_claim）"));
  diagLine(box, "痕迹行", claimCount);
  const commitCount = document.createDocumentFragment();
  commitCount.appendChild(document.createTextNode(
    (d.evidence_commit_count || 0) + " 次 "));
  commitCount.appendChild(rawTag("（evidence_commit）"));
  diagLine(box, "痕迹提交", commitCount);
  const rows = d.claims || [];
  if (!rows.length) {
    diagEmpty(box, "还没有记住什么——答对答错都会在这里留下痕迹。");
    return;
  }
  for (const c of rows) {
    const g = diagGroup(box, spokenOf(c.target_id));
    diagLine(g, "正负", vocabNode(POLARITY_CN, c.polarity));
    diagLine(g, "判分", vocabNode(OUTCOME_CN, c.outcome));
    diagLine(g, "出力方式",
      vocabNode(PERFORMANCE_TYPE_CN, c.performance_type));
    diagLine(g, "时间", whenNode(c.created_at));
  }
}

function renderMemTombstones(d, retry, box) {
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应", retry); return; }
  const rows = d.tombstones || [];
  if (!rows.length) {
    diagEmpty(box, "还没有忘掉过任何东西。");
    return;
  }
  for (const t of rows) {
    const head = document.createDocumentFragment();
    head.appendChild(document.createTextNode(
      (ENTITY_KIND_CN[t.entity_kind] || "") + " "));
    head.appendChild(rawTag(t.entity_kind));
    const g = diagGroup(box, head);
    diagLine(g, "指纹（单向摘要，不含正文）", shortHash(t.entity_hash));
    diagLine(g, "忘掉于", whenNode(t.deleted_at));
    diagLine(g, "范围", vocabNode(SCOPE_CN, t.deletion_scope));
    diagLine(g, "口径版本", rawTag(t.scope_version));
  }
}

function renderMemSummary(data) {
  const rel = data.relationship_memory;
  const epi = data.episode;
  const states = data.learner_states;
  const evi = data.evidence;
  const tom = data.tombstones;
  renderSummaryLine("mem-summary", [
    ["记住：关系", rel && !rel.error ? (rel.memories || []).length : "—"],
    ["剧情", epi && !epi.error ? (epi.episodes || []).length : "—"],
    ["学习", states && !states.error ? (states.states || []).length : "—"],
    ["痕迹", evi && !evi.error ? (evi.evidence_claim_count || 0) : "—"],
    ["存根", tom && !tom.error ? (tom.tombstones || []).length : "—"],
  ]);
}

async function loadMemory() {
  showLoading(MEM_PANEL_IDS);
  try {
    const data = await fetchMemory();
    // cs-2 分区消费：domain 字段决定面板归哪一摞
    placePanel(data.relationship_memory, "mem-relationship");
    placePanel(data.episode, "mem-episode");
    placePanel(data.learner_states, "mem-states");
    placePanel(data.evidence, "mem-evidence");
    placePanel(data.tombstones, "mem-tombstones");
    renderMemRelationship(data.relationship_memory, loadMemory,
      mountPanelDisclosure(diagBox("mem-relationship"), "关系",
        panelCount(data.relationship_memory, "memories")));
    renderMemEpisode(data.episode, loadMemory,
      mountPanelDisclosure(diagBox("mem-episode"), "剧情",
        panelCount(data.episode, "episodes")));
    renderMemStates(data.learner_states, loadMemory,
      mountPanelDisclosure(diagBox("mem-states"), "学习状态",
        panelCount(data.learner_states, "states")));
    renderMemEvidence(data.evidence, loadMemory,
      mountPanelDisclosure(diagBox("mem-evidence"), "痕迹",
        panelCount(data.evidence, "claims")));
    renderMemTombstones(data.tombstones, loadMemory,
      mountPanelDisclosure(diagBox("mem-tombstones"), "存根",
        panelCount(data.tombstones, "tombstones")));
    renderMemSummary(data);
  } catch {
    for (const id of MEM_PANEL_IDS) {
      diagError(diagBox(id), "记忆读数拉取失败", loadMemory);
    }
  }
}

// ── p-2 / R-1R: 隐私页 —— 请笔友忘掉一些事。先讲会失去什么，再要两次
// 点头（两层各说一件事：一说范围，二说不可逆）；结果只说 runtime 自己
// 报的数。 ────────────────────────────────────────────────────────────

function renderDelRefused(message, code) {
  const box = diagBox("del-result");
  box.textContent = "";
  const b = document.createElement("b");
  b.textContent = "没能忘掉。";
  box.appendChild(b);
  const line = document.createElement("p");
  line.className = "sub";
  line.appendChild(document.createTextNode(message + "（"));
  line.appendChild(rawTag(code));
  line.appendChild(document.createTextNode("）"));
  box.appendChild(line);
}

function renderDelResult(data, rangeText) {
  const box = diagBox("del-result");
  box.textContent = "";
  const notes = data.notes || [];
  // p-2 评审 F-2：notes 含 already absent = 幂等空删——不得对未发生的
  // 事声称发生（无新存根、记忆页不添行）。
  const alreadyAbsent = notes.some((n) => n.includes("already absent"));
    const g = diagGroup(
    box,
    alreadyAbsent
      ? "没有什么可忘——它之前就不在抽屉里。"
      : "已忘掉：" + rangeText + "（存根 " + (data.tombstoned || 0) + " 条）"
  );
  if (!alreadyAbsent) {
    const tail = document.createElement("p");
    tail.className = "sub";
    tail.textContent = "这次忘掉留下的存根，在 抽屉 · 记忆 里能看到。";
    box.appendChild(tail);
  }
}

async function runDelete(payload, rangeText) {
  // fr-B：confirmDialog 异步化（自绘纸墨确认窗）——两层各说一件事不变
  if (!(await confirmDialog(
    "将把「" + rangeText + "」请出抽屉，找不回来。确定继续？"))) return;
  if (!(await confirmDialog("再确认一次：忘掉之后无法恢复。"))) return;
  let data = null;
  try {
    data = await fetchDelete(payload);
  } catch {
    renderDelRefused("请求没送到——再试一次。", "network");
    return;
  }
  if (!data.accepted) {
    renderDelRefused(data.message || "笔友拒绝了这次忘掉。",
      data.code || "拒绝");
    return;
  }
  renderDelResult(data, rangeText);
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
  button.textContent = "忘掉这项的痕迹";
  button.addEventListener("click", () => runDelete(
    { scope: "LEARNING_TARGET", target_id: targetId },
    name));
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
    if (!list.length) {
      diagEmpty(box, "还没有可忘的表达——语料还没有铺到这里。");
      return;
    }
    box.appendChild(familyGroupsBlock(list,
      (t) => deleteTargetRow(t.name || spokenOf(t.target_id), t.target_id)));
  } catch {
    box.textContent = "";
    diagError(box, "目标清单拉取失败", loadDelTargets);
  }
}

document.getElementById("del-conversation").addEventListener("click", () =>
  runDelete(
    { scope: "CONVERSATION" },
    "这段通信的全部记录"));

// ── 主线-1（8.2.7 补缺）：按伙伴关系忘掉 —— 旧「这版做不了」自认句
// 退役。后端 RELATIONSHIP_PAIR 现成（迁移 0014 冻结词表），缺的只是
// 编号：角色名册（mc-0）随行每位角色的 persona_id + 本页正服务的
// current_character_id，两者一拼就是诚实 referent。双确认与既有两面
// 同形（runDelete 的两层各说一件事），缺席（无正服务角色）保持诚实。
// ──────────────────────────────────────────────────────────────────────

async function loadDelPartner() {
  const box = diagBox("del-partner");
  box.textContent = "";
  box.appendChild(stateBanner("loading"));
  let data = null;
  try {
    data = await fetchCharacters();
  } catch {
    box.textContent = "";
    diagError(box, "角色名册拉取失败", loadDelPartner);
    return;
  }
  box.textContent = "";
  const currentId = data.current_character_id;
  const roster = data.characters || [];
  const current = roster.find((c) => c.character_id === currentId);
  if (!current || !current.persona_id) {
    // 没有正服务角色的编号就是没有——如实一句，不猜。
    const empty = document.createElement("p");
    empty.className = "note";
    empty.textContent = "还没有正在服务的伙伴——先在案头挑一位笔友。";
    box.appendChild(empty);
    return;
  }
  const row = document.createElement("div");
  row.className = "kv";
  const name = document.createElement("b");
  name.textContent = current.name || current.character_id;
  row.appendChild(name);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn--pencil";
  button.textContent = "忘掉与这位伙伴的关系记忆";
  button.addEventListener("click", () => runDelete(
    { scope: "RELATIONSHIP_PAIR", persona_id: current.persona_id },
    "与 " + (current.name || current.character_id) + " 的关系记忆"));
  row.appendChild(button);
  box.appendChild(row);
}

// ── p-3 / R-1R: 方向页 —— 长期方向在此写下。读写合一（读卡取消，当前
// 值直接进编辑面）；保存 = 全组合 upsert（版本前移，不保留旧版）；冲突
// 诚实上浮（409）→「重新读过」。词表词中英并置（中文 + 等宽小字原文）。
// 词表取自服务端 taxonomy，客户端零拷贝。 ─────────────────────────────

const GOAL_PANEL_IDS = ["goal-weights", "goal-assessment",
                        "goal-register"];

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

// the result box: one human line, optionally with an action (the conflict's
// 重新读过). Failure rides the .errline form, success the .sub one.
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

function renderGoalEditor() {
  const box = goalBox("goal-editor");
  box.textContent = "";
  if (!goalEditor) return;
  const editor = goalEditor;
  const words = goalWordSet("goal_modality");
  editor.goals.forEach((goal, index) => {
    const edge = document.createElement("div");
    edge.className = "goaledge";
    // fr-A #27 墨选：原生 <select> 退役——选项文字纯文本两列（中文主列
    // + 原词弱墨辅列 sub，不再「中文 + 空格 + 原文」挤一行）。
    const select = selectField({
      name: "目标 " + (index + 1) + " · 技能",
      options: words.map((word) => ({
        value: word,
        label: MODALITY_CN[word] || word,
        sub: MODALITY_CN[word] ? word : null,
      })),
      value: goal.goal_modality,
      onChange: (next) => { goal.goal_modality = next; },
    });
    edge.appendChild(fieldRow("目标 " + (index + 1) + " · 技能",
                              select.root));
    const description = document.createElement("input");
    description.type = "text";
    description.value = goal.description;
    description.placeholder = "一句话说清这个方向……";
    description.addEventListener("input", () => {
      goal.description = description.value;
    });
    edge.appendChild(fieldRow("目标 " + (index + 1) + " · 内容", description));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn--faint";
    remove.textContent = "从当前组合移除（保存后生效）";
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
    box.appendChild(fieldRow(
      MODALITY_CN[word] ? biLabel(MODALITY_CN[word], word) : word, input));
  }
}

function renderWordPicker(boxId, faceName, set, cnMap) {
  const box = goalBox(boxId);
  box.textContent = "";
  if (!goalEditor) return;
  const row = document.createElement("div");
  row.className = "chips";
  for (const word of goalWordSet(faceName)) {
    const on = set.has(word);
    row.appendChild(chip(word, {
      on: on,
      cn: cnMap ? cnMap[word] : null,
      onClick: () => {
        if (on) set.delete(word);
        else set.add(word);
        renderWordPicker(boxId, faceName, set, cnMap);
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
  save.textContent = "保存方向";
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
  button.textContent = "保存中……";
  let data = null;
  try {
    data = await fetchSaveGoals(payload);
  } catch {
    goalResult("保存没送到——再试一次。", true);
    button.disabled = false;
    button.textContent = original;
    return;
  }
  button.disabled = false;
  button.textContent = original;
  if (data.accepted) {
    goalResult(data.idempotent
      ? "内容没有变化——没有写新版本。"
      : "已保存（第 " + data.goal_version + " 版）。", false);
    loadGoals();
  } else if (data.conflict) {
    // the store refused the same-version write: the human sentence plus
    // the one action that resolves it — re-read and try again
    const again = document.createElement("button");
    again.type = "button";
    again.className = "btn btn--pencil";
    again.textContent = "重新读过";
    again.addEventListener("click", loadGoals);
    goalResult("这份方向刚在别处被改过——重新读过再改。", true, again);
  } else {
    goalResult(data.error || "保存没送到——再试一次。", true);
  }
}

// 批注频率的编辑面随本刀退役（用户否决：同一键在设置 · 教学策略里已有
// 墨选，温故 · 方向里的第二编辑面是重复设计；teaching_frequency 后端写
// 面保留——页面唯一编辑点 = 设置节）。FREQUENCY_CN 仍服务设置节的墨选
// 与读数。

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
  const head = document.createDocumentFragment();
  head.appendChild(document.createTextNode("这段通信 "));
  head.appendChild(rawTag(focus.conversation_id));
  const group = diagGroup(box, head);
  const weights = focus.temporary_goal_weights || {};
  const said = document.createDocumentFragment();
  const entries = Object.keys(weights);
  entries.forEach((word, index) => {
    if (index > 0) said.appendChild(document.createTextNode("；"));
    if (MODALITY_CN[word]) said.appendChild(biLabel(MODALITY_CN[word], word));
    else said.appendChild(rawTag(word));
    said.appendChild(document.createTextNode(" " + weights[word]));
  });
  if (!entries.length) said.appendChild(document.createTextNode("（无）"));
  diagLine(group, "临时权重", said);
  diagLine(group, "手动聚焦",
    focus.manual_focus_target ? spokenOf(focus.manual_focus_target) : "—");
  diagLine(group, "开始于",
    focus.starts_at ? whenNode(focus.starts_at) : "—");
  if (focus.expires_at) diagLine(group, "结束于", whenNode(focus.expires_at));
}

function renderGoalTaxref() {
  const box = goalBox("goal-taxref");
  box.textContent = "";
  const taxonomy = (goalData && goalData.taxonomy) || {};
  const note = taxonomy.non_stored_note || "";
  const content = document.createElement("div");
  for (const face of taxonomy.faces || []) {
    if (face.stored) continue;
    const line = document.createElement("p");
    line.className = "taxref";
    line.textContent = "§" + (face.section || "?") + " " + face.name +
      "（" + face.words.length + " 词 · " + note + "）：" +
      face.words.join("、");
    content.appendChild(line);
  }
  // 参考词表三段折进 #21（默认收）——无存储位的参考不占主峰版面
  box.appendChild(disclosure({
    name: "词表原文（三面 · 本版只作参考）",
    content: content,
  }).root);
}

async function loadGoals() {
  for (const id of GOAL_PANEL_IDS) {
    const box = goalBox(id);
    box.textContent = "";
    box.appendChild(stateBanner("loading"));
  }
  // the result box is NOT touched here: a save's own line must survive the
  // re-read that follows it (hiding happens on section entry, showSection)
  try {
    goalData = await fetchGoals();
  } catch {
    for (const id of GOAL_PANEL_IDS) {
      diagError(goalBox(id), "方向读数没取到", loadGoals);
    }
    return;
  }
  if (!goalData.available) {
    // the honest refusal: no user-config leg on this host, nothing to
    // read and nothing to edit — said in every panel, no editor built
    goalEditor = null;
    for (const id of GOAL_PANEL_IDS) {
      diagEmpty(goalBox(id),
        "本进程未装配用户配置面（无 content-tier）——方向读写不可用。");
    }
    goalBox("goal-editor").textContent = "";
    goalBox("goal-save").textContent = "";
    return;
  }
  goalEditor = editorFromData(goalData);
  renderGoalEditor();
  renderGoalWeights();
  renderWordPicker("goal-assessment", "external_assessment",
    goalEditor.assessment, null);
  renderWordPicker("goal-register", "register_style",
    goalEditor.register, REGISTER_CN);
  renderGoalSave();
  renderGoalFocus();
  renderGoalTaxref();
}

// ── 主线-1（8.2.8 重铸②）+ veto-R 重做：设置节真面 —— SECTION_PULLS
// 拉本节。三面真值一读全归：当前档（生效档——live wiring 值，热改后
// 即变）、教学策略（§5.1 十三列；null = 还没有）、披露规则（§5.1
// DisclosurePolicy 现值，编辑面接通）。教学模式 = 四档墨选可改
// （fetchSaveMode → 持久化 + 换活 wiring，下一轮即新档）；八旋钮真
// 控件 + 保存回路（读现值→改→POST→回读刷新），七钮档位墨选
// （KNOB_TIERS display-layer 词表）+「暂不影响行为」如实标注，词表外
// 值服务端 400 人话原样上浮。
// ──────────────────────────────────────────────────────────────────────

let settingsData = null;   // the last GET /api/settings payload
let policyEditor = null;   // the eight-knob working copy the save sends
let disclosureEditor = null;   // 披露规则工作副本（fr-A 编辑面；null = 无写面）
let disclosureRoster = null;   // 名册（角色名与当前 persona 的供给面）

// 旋钮的中文读法（本刀拟定——用户首验否决权保留）；白名单本身由
// 服务端 writable_knobs 随行，这里不抄名单。
const KNOB_CN = {
  teaching_frequency: "批注频率",
  interruption_budget: "打断预算",
  curriculum_initiative: "课程主动度",
  correction_strictness: "纠错严格度",
  hint_policy: "提示策略",
  assessment_visibility: "评估可见度",
  practice_density: "练习密度",
  persona_freedom: "笔友自由度",
};

// 披露阶梯的中文读法（disclosure.py 的 Local V1 宣告——三档各露什么）。
const DISCLOSURE_CN = {
  MINIMAL: "基础事实",
  FUNCTIONAL: "基础 + 偏好",
  RICH: "基础 + 偏好 + 设置",
};

function settingsBox(id) {
  return document.getElementById(id);
}

function settingsResult(text, failure, action) {
  const box = settingsBox("settings-result");
  box.hidden = false;
  box.textContent = "";
  const line = document.createElement("p");
  line.className = failure ? "errline" : "sub";
  line.textContent = text;
  box.appendChild(line);
  if (action) box.appendChild(action);
}

// the working copy: the durable row's knob columns (null stays null —
// 未配置是列自己的诚实), or all-null when no row exists yet (the first
// save writes the first policy; the frequency must be picked by hand).
function editorFromSettings(data) {
  const policy = data.teaching_policy;
  const editor = {};
  for (const name of data.writable_knobs || []) {
    const value = policy ? policy[name] : null;
    editor[name] = (value === undefined) ? null : value;
  }
  return editor;
}

// 披露编辑面的工作副本（fr-A）：null = 无写面（prep-1 层——读不到也
// 改不了）；有面无时 = []（第一次保存即建第一条 policy 行——与八旋钮
// 的第一份策略同一读法）。
function editorFromDisclosure(data) {
  if (!data || data.available === false) return null;
  const policy = data.disclosure;
  if (!policy) return [];
  return (policy.rules || []).map((rule) => ({
    persona_id: rule.persona_id,
    disclosure_level: rule.disclosure_level,
  }));
}

// 教学模式四档（veto-R 可改读面）：存值 = §12 枚举词（服务端 mode_words
// 随行，客户端零拷贝——大小写与连字符是文档自己的）；中文读法与分寸句
// 是本刀的显示层声明（用户首验否决权保留）。页面 mode 写 = 用户的显式
// 档位表达，与改启动命令同一权力（单用户本地应用，一个主体）——gate
// 函数零改，默认 None 仍拒自动教学。
const MODE_CN = {
  "manual/user-initiated": "手动（用户发起）",
  "Study-first": "学习优先",
  "Balanced": "平衡",
  "Lounge": "娱乐 · 关系优先",
};

const MODE_HINT = {
  "manual/user-initiated": "教学只在你开口要时发生。",
  "Study-first": "练句密度优先，批注递得勤，课程感更明显。",
  "Balanced": "聊天与练句并行，批注适度。",
  "Lounge": "聊得多，递得少，笔友以听和陪为主。",
};

// 模型与端点（用户否决驱动的 provider 面）：端点地址 + 模型名两输入，
// 保存即持久化 + 热换 provider——下一封信就走新设置，重启后仍以这里的
// 值为准（启动参数让位）。密钥不在此面（仍由启动环境提供，不存库不显
// 示——一句话说清，不再整节「如实说」）。非 OpenAI 装配（测试替身）服务
// 端 provider 读数 = null——诚实空态，不虚构一对值。
function providerResult(text, failure) {
  const box = settingsBox("settings-provider-result");
  if (!box) return;
  box.textContent = "";
  const line = document.createElement("p");
  line.className = failure ? "errline" : "sub";
  line.textContent = text;
  box.appendChild(line);
}

async function saveProvider(button, baseUrlInput, modelInput, keyInput) {
  const payload = {};
  const baseUrl = baseUrlInput.value.trim();
  const model = modelInput.value.trim();
  const key = keyInput.value.trim();
  if (baseUrl) payload.base_url = baseUrl;
  if (model) payload.model = model;
  if (key) payload.api_key = key;
  if (!Object.keys(payload).length) {
    providerResult("至少填一个——端点地址、模型名或 API 密钥。", true);
    return;
  }
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "保存中……";
  let data = null;
  try {
    data = await fetchSaveProvider(payload);
  } catch {
    providerResult("保存没送到——再试一次。", true);
    button.disabled = false;
    button.textContent = original;
    return;
  }
  button.disabled = false;
  button.textContent = original;
  if (data.accepted) {
    providerResult(data.idempotent
      ? "内容没有变化——没有写。"
      : "已保存——下一封信就走新设置，重启后仍以这里为准。", false);
    loadSettings();
  } else {
    providerResult(data.error || "保存没送到——再试一次。", true);
  }
}

function renderSettingsProvider() {
  const box = settingsBox("settings-provider-editor");
  if (!box) return;
  box.textContent = "";
  const face = settingsData && settingsData.provider;
  if (!face) {
    diagEmpty(box,
      "这个进程不是 OpenAI 兼容装配——端点与模型名在这里读不到、也改不了。");
    return;
  }
  const baseUrlInput = document.createElement("input");
  baseUrlInput.type = "text";
  baseUrlInput.value = face.base_url;
  baseUrlInput.placeholder = "完整 http(s) 端点地址";
  baseUrlInput.autocomplete = "off";
  baseUrlInput.spellcheck = false;
  box.appendChild(fieldRow("端点地址", baseUrlInput));
  const modelInput = document.createElement("input");
  modelInput.type = "text";
  modelInput.value = face.model;
  modelInput.placeholder = "模型名";
  modelInput.autocomplete = "off";
  modelInput.spellcheck = false;
  box.appendChild(fieldRow("模型名", modelInput));
  // 密钥面（启动系统刀：三件都在页面设）：值永不回显——GET 只报
  // api_key_set；输入留空 = 不改（不是清除）。
  const keyInput = document.createElement("input");
  keyInput.type = "password";
  keyInput.value = "";
  keyInput.placeholder = "API 密钥——留空 = 不改";
  keyInput.autocomplete = "new-password";
  box.appendChild(fieldRow("API 密钥", keyInput));
  const keyState = document.createElement("p");
  keyState.className = "sub";
  keyState.textContent = face.api_key_set
    ? "已保存一把密钥（值不回显）。"
    : "还没有保存过密钥——发信时用启动环境的那把；或在这里存一把。";
  box.appendChild(keyState);
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--pencil";
  save.textContent = "保存端点与模型";
  save.addEventListener("click", () => {
    saveProvider(save, baseUrlInput, modelInput, keyInput);
  });
  box.appendChild(save);
  const note = document.createElement("p");
  note.className = "doc-line";
  note.textContent = "密钥只存本机这个应用，任何页面读数都不回显它。";
  box.appendChild(note);
}

function renderSettingsMode() {
  const box = settingsBox("settings-mode-editor");
  if (!box) return;
  box.textContent = "";
  if (!settingsData || settingsData.available === false) {
    diagEmpty(box, "这个进程没装配用户配置面——模式读不到也改不了。");
    renderSettingsModeHint(null);
    return;
  }
  const stage = settingsData.rollout_stage;
  const words = settingsData.mode_words || [];
  // fr-A #27 墨选：词表由服务端随行（客户端零拷贝）；中文档名主列 +
  // 原词辅列（sub——双列层级）。
  const control = selectField({
    name: "教学模式",
    options: words.map((word) => ({
      value: word,
      label: MODE_CN[word] || word,
      sub: MODE_CN[word] ? word : null,
    })),
    value: stage,
    placeholder: "未声明——自动教学关着",
    onChange: (next) => { saveMode(next); },
  });
  box.appendChild(control.root);
  renderSettingsModeHint(stage);
}

// 当前档的分寸句一行——换档要懂的差别就在这一句（解释影响操作决策，
// 数据优先原则的保留面）。
function renderSettingsModeHint(stage) {
  const note = settingsBox("settings-mode-note");
  if (!note) return;
  const hint = stage ? (MODE_HINT[stage] || "") : "";
  note.hidden = hint === "";
  note.textContent = hint;
}

function settingsModeResult(text, failure) {
  const box = settingsBox("settings-mode-result");
  if (!box) return;
  box.hidden = false;
  box.textContent = "";
  const line = document.createElement("p");
  line.className = failure ? "errline" : "sub";
  line.textContent = text;
  box.appendChild(line);
}

async function saveMode(word) {
  let data = null;
  try {
    data = await fetchSaveMode(word);
  } catch {
    settingsModeResult(
      "连不上服务（页面没送到新请求）——强制刷新页面（Ctrl+F5）；若仍失败，"
      + "确认服务还在运行、地址栏端口与启动命令一致。", true);
    return;
  }
  if (!data.accepted) {
    // 服务端 400 人话（词表外值）或 prep-1 层的诚实拒绝，原样上浮。
    settingsModeResult(data.error || "没能换档。", true);
    return;
  }
  // 保存回路收口：回读刷新——读回来的就是存下的（下一轮就在这一档）。
  await loadSettings();
  settingsModeResult("已换到 " + (MODE_CN[word] || word) + "。", false);
}

// 七钮档位词表（veto-R 档位化）：**display-layer 声明**——canonical 与
// 实现枚举都没有这些列的词表（store 是货架，存什么读什么），档位短语由
// 本刀拟定（用户首验否决权保留）；存值仍是 verbatim 字符串列（选什么
// 存什么），「未配置」= null 诚实保留可选。换词表 = 改这里一处。
const KNOB_TIERS = {
  interruption_budget: ["少", "适中", "多"],
  curriculum_initiative: ["不主动", "偶尔主动", "主动"],
  correction_strictness: ["宽", "适中", "严"],
  hint_policy: ["不给提示", "点拨为主", "提示充分"],
  assessment_visibility: ["不展示", "展示"],
  practice_density: ["稀", "适中", "密"],
  persona_freedom: ["贴信说话", "适度自由", "放开发挥"],
};

function renderPolicyKnobs() {
  const box = settingsBox("settings-knobs");
  box.textContent = "";
  if (!policyEditor) return;
  const knobs = (settingsData && settingsData.writable_knobs) || [];
  for (const name of knobs) {
    const label = document.createElement("span");
    label.textContent = KNOB_CN[name] || name;
    if (name !== "teaching_frequency") {
      // 七个未钉词表的旋钮存而不用——「暂不影响行为」照 veto-R 如实标注
      // （原存面 badge 随档位化退役）。
      const badge = document.createElement("span");
      badge.className = "rawtag";
      badge.textContent = "暂不影响行为";
      label.appendChild(document.createTextNode(" "));
      label.appendChild(badge);
    }
    let node;
    if (name === "teaching_frequency") {
      // fr-A #27 墨选：词表由服务端 frequency_words 随行（客户端零拷贝）；
      // 中文读法在前（存值枚举词不变）；null = 未选——placeholder 弱墨
      // （第一份策略必须亲手选一档）。node = 工厂的 root（DOM 节点）。
      node = selectField({
        name: "批注频率",
        options: ((settingsData && settingsData.frequency_words) || [])
          .map((word) => ({
            value: word,
            // veto-R 词面中文化：中文档名为主列 + 原词辅列（sub）；未知词
            // 不兜底——原样直出，与披露层级同一读法。
            label: FREQUENCY_CN[word] || word,
            sub: FREQUENCY_CN[word] ? word : null,
          })),
        value: (policyEditor[name] === undefined) ? null : policyEditor[name],
        placeholder: "选一档……",
        onChange: (next) => { policyEditor[name] = next; },
      }).root;
    } else {
      // veto-R 档位化：自由文本框退役，七钮各一枚墨选——display-layer
      // 档位 + 「未配置」（null）诚实可选。
      const tiers = KNOB_TIERS[name] || [];
      node = selectField({
        name: KNOB_CN[name] || name,
        options: [
          { value: null, label: "未配置" },
          ...tiers.map((tier) => ({ value: tier, label: tier })),
        ],
        value: (policyEditor[name] === undefined) ? null : policyEditor[name],
        placeholder: "未配置",
        onChange: (next) => { policyEditor[name] = next; },
      }).root;
    }
    box.appendChild(fieldRow(label, node));
  }
}

function renderSettingsSave() {
  const box = settingsBox("settings-save");
  box.textContent = "";
  if (!policyEditor) return;
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--ink";
  save.textContent = "保存教学策略";
  save.addEventListener("click", () => savePolicy(save));
  box.appendChild(save);
}

async function savePolicy(button) {
  if (!policyEditor) return;
  const payload = {};
  for (const name of (settingsData && settingsData.writable_knobs) || []) {
    payload[name] = policyEditor[name];
  }
  if (!payload.teaching_frequency) {
    settingsResult("先给批注频率选一档——第一份策略必须选。", true);
    return;
  }
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "保存中……";
  let data = null;
  try {
    data = await fetchSaveTeachingPolicy(payload);
  } catch {
    settingsResult("保存没送到——再试一次。", true);
    button.disabled = false;
    button.textContent = original;
    return;
  }
  button.disabled = false;
  button.textContent = original;
  if (data.conflict) {
    const again = document.createElement("button");
    again.type = "button";
    again.className = "btn btn--faint";
    again.textContent = "重新读过";
    again.addEventListener("click", () => loadSettings());
    settingsResult(data.error || "配置已被别处更新，请重读再改", true, again);
    return;
  }
  if (!data.accepted) {
    // 服务端 400 人话（mode 等系统列、词表外值）原样上浮——页面不转译。
    settingsResult(data.error || "没能保存。", true);
    return;
  }
  // 保存回路收口：回读刷新——读回来的就是存下的。（版本号不进面孔：
  // 机械原值的归宿是记录页折叠的原始读数区，⑧ 8.3——r1r 钉原样承重）
  await loadSettings();
  settingsResult("已保存——上面读回的就是它。", false);
}

function renderSettingsDisclosure() {
  const box = settingsBox("settings-disclosure");
  box.textContent = "";
  const levels = (settingsData && settingsData.disclosure_levels) || [];
  if (disclosureEditor === null) {
    // prep-1 层（无 user_config 腿）：读不到也改不了，如实一句。
    diagEmpty(box, "这个进程没装配用户配置面——披露规则读不到也改不了。");
    return;
  }
  if (!disclosureEditor.length) {
    const policy = settingsData && settingsData.disclosure;
    diagEmpty(box, policy
      ? "没有规则行——缺省一无所露。"
      : "还没有披露规则——缺省一无所露。");
  }
  for (const rule of disclosureEditor) {
    box.appendChild(disclosureRuleRow(rule, levels));
  }
  box.appendChild(disclosureAddRow(levels));
}

function disclosureRuleRow(rule, levels) {
  const row = document.createElement("div");
  row.className = "kv disclosurerule";
  const who = document.createElement("b");
  if (rule.persona_id === null) {
    who.textContent = "默认规则";
  } else {
    const name = personaNameOf(rule.persona_id);
    if (name) {
      who.textContent = name + " ";
      const tag = document.createElement("span");
      tag.className = "rawtag";
      tag.textContent = rule.persona_id;
      who.appendChild(tag);
    } else {
      // 名册里没有这个 persona——原值直出，不发明归属。
      who.textContent = "角色 " + rule.persona_id;
    }
  }
  row.appendChild(who);
  // fr-A #27 墨选：层级词表由服务端 disclosure_levels 随行（客户端零
  // 拷贝）；veto-R 词面中文化——中文读法主列 + 原词辅列（sub；存值枚举
  // 词不变；未知词不兜底，原样直出）。
  const select = selectField({
    name: "披露层级",
    options: levels.map((word) => ({
      value: word,
      label: DISCLOSURE_CN[word] || word,
      sub: DISCLOSURE_CN[word] ? word : null,
    })),
    value: rule.disclosure_level,
    onChange: (next) => { rule.disclosure_level = next; },
  });
  row.appendChild(select.root);
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "btn btn--faint";
  remove.textContent = "移出（保存后生效）";
  remove.addEventListener("click", () => {
    disclosureEditor.splice(disclosureEditor.indexOf(rule), 1);
    renderSettingsDisclosure();
  });
  row.appendChild(remove);
  return row;
}

function personaNameOf(personaId) {
  const roster = (disclosureRoster && disclosureRoster.characters) || [];
  const card = roster.find((entry) => entry.persona_id === personaId);
  return card ? (card.name || null) : null;
}

function currentPersonaOf() {
  const roster = (disclosureRoster && disclosureRoster.characters) || [];
  const currentId = disclosureRoster &&
    disclosureRoster.current_character_id;
  const card = roster.find((entry) => entry.character_id === currentId);
  return card && card.persona_id ? card : null;
}

// 增行控件（编辑面同构接法 = 方向页目标编辑的读法）：默认规则至多一
// 条（缺才可加）；当前笔友的专属规则按名册供给——名册没有当前 persona
// 就没有这个钮（不发明对象）。
function disclosureAddRow(levels) {
  const row = document.createElement("p");
  row.className = "sub";
  const first = levels[0] || "MINIMAL";
  if (!disclosureEditor.some((rule) => rule.persona_id === null)) {
    const add = document.createElement("button");
    add.type = "button";
    add.className = "btn btn--pencil";
    add.textContent = "加一条默认规则";
    add.addEventListener("click", () => {
      disclosureEditor.push({ persona_id: null, disclosure_level: first });
      renderSettingsDisclosure();
    });
    row.appendChild(add);
    row.appendChild(document.createTextNode("　"));
  }
  const current = currentPersonaOf();
  if (current && !disclosureEditor.some(
      (rule) => rule.persona_id === current.persona_id)) {
    const add = document.createElement("button");
    add.type = "button";
    add.className = "btn btn--pencil";
    add.textContent = "加一条 " + (current.name || "当前笔友") + " 的专属规则";
    add.addEventListener("click", () => {
      disclosureEditor.push({
        persona_id: current.persona_id, disclosure_level: first });
      renderSettingsDisclosure();
    });
    row.appendChild(add);
  }
  return row;
}

function renderDisclosureSave() {
  const box = settingsBox("settings-disclosure-save");
  if (!box) return;
  box.textContent = "";
  if (disclosureEditor === null) return;
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--ink";
  save.textContent = "保存披露规则";
  save.addEventListener("click", () => saveDisclosure(save));
  box.appendChild(save);
}

function disclosureResult(text, failure, action) {
  const box = settingsBox("settings-disclosure-result");
  box.hidden = false;
  box.textContent = "";
  const line = document.createElement("p");
  line.className = failure ? "errline" : "sub";
  line.textContent = text;
  box.appendChild(line);
  if (action) box.appendChild(action);
}

async function saveDisclosure(button) {
  if (disclosureEditor === null) return;
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "保存中……";
  let data = null;
  try {
    data = await fetchSaveDisclosure({ rules: disclosureEditor });
  } catch {
    disclosureResult("保存没送到——再试一次。", true);
    button.disabled = false;
    button.textContent = original;
    return;
  }
  button.disabled = false;
  button.textContent = original;
  if (data.conflict) {
    const again = document.createElement("button");
    again.type = "button";
    again.className = "btn btn--faint";
    again.textContent = "重新读过";
    again.addEventListener("click", () => loadSettings());
    disclosureResult(data.error || "配置已被别处更新，请重读再改",
                     true, again);
    return;
  }
  if (!data.accepted) {
    // 服务端 400 人话（重复行、词表外层级）原样上浮——页面不转译。
    disclosureResult(data.error || "没能保存。", true);
    return;
  }
  // 保存回路收口：回读刷新——读回来的就是存下的。
  await loadSettings();
  disclosureResult("已保存——上面读回的就是它。", false);
}

// 显示与计量区（fr-A）：token 计量显示开关——sessionStorage 客户端侧
// （如实标注：user_config 现面没有 UI 偏好的合适面）。
function renderSettingsMeter() {
  const box = settingsBox("settings-meter");
  if (!box) return;
  box.textContent = "";
  const row = document.createElement("p");
  row.className = "kv";
  const label = document.createElement("b");
  label.textContent = "显示 token 计量";
  row.appendChild(label);
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "btn btn--pencil";
  toggle.setAttribute("aria-pressed", tokenMeterOn ? "true" : "false");
  toggle.textContent = tokenMeterOn ? "开着——点按关掉"
                                    : "关着——点按打开";
  toggle.addEventListener("click", () => {
    setTokenMeter(!tokenMeterOn);
    renderSettingsMeter();
    // fr-B 微交互·开关拨动：重渲后的新钮补一回弹簧盖印（stamp-press
    // 同形 × --ease-spring，幅度 ≤4%——tokens.css 弹簧法则登记面）；
    // reduced-motion 直切（JS 半区）。
    const fresh = box.querySelector(".btn");
    if (fresh && !REDUCED_MOTION.matches) fresh.classList.add("flip-tick");
  });
  row.appendChild(toggle);
  box.appendChild(row);
}

async function loadSettings() {
  const knobs = settingsBox("settings-knobs");
  const rules = settingsBox("settings-disclosure");
  knobs.textContent = "";
  knobs.appendChild(stateBanner("loading"));
  rules.textContent = "";
  rules.appendChild(stateBanner("loading"));
  let data = null;
  try {
    data = await fetchSettings();
  } catch {
    knobs.textContent = "";
    diagError(knobs, "设置读数拉取失败", loadSettings);
    rules.textContent = "";
    diagError(rules, "设置读数拉取失败", loadSettings);
    return;
  }
  settingsData = data;
  policyEditor = editorFromSettings(data);
  disclosureEditor = editorFromDisclosure(data);
  try {
    disclosureRoster = await fetchCharacters();
  } catch {
    disclosureRoster = null;   // 名册拉不到——角色名退 rawtag 原值，不猜
  }
  renderSettingsProvider();
  renderSettingsMode();
  renderPolicyKnobs();
  renderSettingsSave();
  renderSettingsDisclosure();
  renderDisclosureSave();
  renderSettingsMeter();
}

// ── R-1: the spaces — 门厅 / 案头 / 温故 / 抽屉 + 两纵深（信档 ·
// 观察）— plain show/hide, no router. The dock (#18) is the only way
// between spaces; entering the
// study or the drawer lands its default section, and switching a section
// (#20 tabs) is the pull — the section always shows its own facts, never
// a stale page. ────────────────────────────────────────────────────────

const spaces = {
  onboard: document.getElementById("screen-onboard"),
  parlor: document.getElementById("space-parlor"),
  partner: document.getElementById("space-partner"),
  letters: document.getElementById("space-letters"),
  obs: document.getElementById("space-obs"),
  study: document.getElementById("space-study"),
  drawer: document.getElementById("space-drawer"),
};

const SECTION_BODIES = {
  study: {
    today: document.getElementById("study-today"),
    goal: document.getElementById("study-goal"),
    progress: document.getElementById("study-progress"),
  },
  drawer: {
    memory: document.getElementById("drawer-memory"),
    privacy: document.getElementById("drawer-privacy"),
    settings: document.getElementById("drawer-settings"),
  },
};

// R-1R（⑧ 8.1.2 命名定稿）：内部 id/键零改名，显示名 目标→方向、
// 进步→档案（rd-3：记录→档案——收藏档语义，搜索优先聚合时间线）；
// 节签文字、节名槽、此处映射，三处一致。
const SECTION_NAMES = {
  today: "今日", goal: "方向", progress: "档案",
  memory: "记忆", privacy: "隐私", settings: "设置",
};

// 进空间落默认节（温故=今日、抽屉=记忆）
const DEFAULT_SECTION = { study: "today", drawer: "memory" };

// entering a section is the pull; settings pulls its own three-face read
// since 主线-1 (the honest placeholder retired — the section shows its
// own facts, never a stale page)
const SECTION_PULLS = {
  "study-today": loadToday,
  "study-goal": () => {
    // a save's own line must survive the re-read that follows a save;
    // the hiding happens on entry (showSection), not inside loadGoals
    goalBox("goal-result").hidden = true;
    loadGoals();
  },
  "study-progress": () => { loadLearning(); },
  "drawer-memory": loadMemory,
  "drawer-privacy": () => { loadDelTargets(); loadDelPartner(); },
  "drawer-settings": () => {
    // a save's own line must survive the re-read that follows a save;
    // the hiding happens on entry (showSection), not inside loadSettings
    settingsBox("settings-result").hidden = true;
    settingsBox("settings-disclosure-result").hidden = true;
    const modeResult = settingsBox("settings-mode-result");
    if (modeResult) modeResult.hidden = true;
    loadSettings();
  },
};

// fr-B 退出编排（⑨-5 新行——交叉淡化的退出半；空间/节两档同构）：
// 旧层不落 [hidden] 直切，改落 .space--leave/.panel--leave（absolute
// 叠在锚容器之上、纸底遮住进层、ink-wash reverse × --ease-exit），与
// 进层同帧起播 = 交叉淡化；animationend 对账 + 保险丝后 [hidden]。
// 快进快出（A→B→A）安全：再入时撤 fuse 摘类，finish 只在类仍在时
// 落 hidden。reduced-motion 直切（JS 半区，库尾总降级块双面）。
function cancelLeave(node, cls) {
  if (node._leaveFuse) {
    clearTimeout(node._leaveFuse);
    node._leaveFuse = null;
  }
  node.classList.remove(cls);
}

function leaveLayer(node, cls) {
  if (REDUCED_MOTION.matches) {
    node.hidden = true;
    return;
  }
  node.classList.add(cls);
  const finish = () => {
    node._leaveFuse = null;
    if (node.classList.contains(cls)) {
      node.classList.remove(cls);
      node.hidden = true;
    }
  };
  node.addEventListener("animationend", (event) => {
    if (event.animationName === "ink-wash" && event.target === node) {
      finish();
    }
  });
  node._leaveFuse = setTimeout(finish, 400);   // 保险丝（220 + 余量）
}

function showSection(space, name) {
  const group = SECTION_BODIES[space];
  const leaving = Object.keys(group).find(
    (key) => key !== name && !group[key].hidden);
  cancelLeave(group[name], "panel--leave");
  for (const key of Object.keys(group)) {
    group[key].hidden = key !== name && key !== leaving;
  }
  if (leaving) leaveLayer(group[leaving], "panel--leave");
  markSectionTabs(document.getElementById(space + "-tabs"), name);
  sectionLabel(document.getElementById(space + "-head"),
    SECTION_NAMES[name]);
  const pull = SECTION_PULLS[space + "-" + name];
  if (pull) pull();
  window.scrollTo(0, 0);
}

function showSpace(name) {
  // ⑩ 层级宪法的互斥半：进任何空间（含全页）收一切浮层与下拉容器——
  // 换空间的人不该被上一空间的浮层/沓跟着走。closeEnvelopeSelector 在
  // 容器不在场时是安全的空操作；closeWordCard 同（fr-B：互斥路径直摘，
  // skipOut 不留残影）。v3-a：写作态同批（全页成员，8.2.2⑤——保稿收起）。
  closeWordCard({ skipOut: true });
  closeEnvelopeSelector();
  closeComposeFace();
  closeOpenSelects();
  closeTokenMeterPop();
  const leaving = Object.keys(spaces).find(
    (key) => key !== name && !spaces[key].hidden);
  cancelLeave(spaces[name], "space--leave");
  for (const key of Object.keys(spaces)) {
    spaces[key].hidden = key !== name && key !== leaving;
  }
  if (leaving) leaveLayer(spaces[leaving], "space--leave");
  syncFlowBottom();
  syncFlowRuler();
  markNavdock(name);
  // the vestibule has no spaces to switch between — the door button is
  // the one way in, so the dock stands down while the cover is up
  document.getElementById("navdock").hidden = name === "onboard";
  // cs-2 档案页同门厅形态：整页自持，导航条让位（返回钮是唯一回途）。
  // v2-2：信档/观察两屏同法——案头与档案的纵深，不是新空间（dock ≤5
  // 红线不动），返回钮各归其位（信档 → 案头、观察 → 温故 · 档案）。
  if (name === "partner" || name === "letters" || name === "obs") {
    document.getElementById("navdock").hidden = true;
  }
  if (name === "study") showSection("study", DEFAULT_SECTION.study);
  if (name === "drawer") showSection("drawer", DEFAULT_SECTION.drawer);
  window.scrollTo(0, 0);
}

// R-1 wiring: the dock switches spaces, the two tab lists switch sections
// (a click and the left/right arrows both land on the same showSection).
// ux-1: the touch swipe is a supplementary switcher for the same two
// spaces — the tabs stay the primary face.
wireNavdock((name) => showSpace(name));
wireSectionTabs(document.getElementById("study-tabs"),
  (name) => showSection("study", name));
wireSectionTabs(document.getElementById("drawer-tabs"),
  (name) => showSection("drawer", name));
wirePanelSwipe("study", (name) => showSection("study", name));
wirePanelSwipe("drawer", (name) => showSection("drawer", name));

// 记录页的底：一切原值折进一个 #21（⑧ 8.2.5）——证据记录留在折叠内
// （原值读数的第一层）；观察读数自 v2-2 迁入专门面（8.2.12 观察仪表
// 屏——排查材料不摊在档案里，折叠内只留入口）。计划明细与按表达看
// 同法收养（rd-3：排程/目标/账表降入按需折叠，默认层只留计划一行）。

const rawReadings = disclosure({
  name: "原始读数（给排查用）",
  content: diagBox("raw-readings"),
});
diagBox("raw-slot").appendChild(rawReadings.root);

diagBox("plan-slot").appendChild(disclosure({
  name: "计划明细（复习排程 · 目标）",
  content: diagBox("plan-detail"),
}).root);

diagBox("book-slot").appendChild(disclosure({
  name: "按表达看：在学的表达",
  content: diagBox("book-detail"),
}).root);

// ── v2-2: 观察仪表屏（8.2.12 结构重铸件）——观察读数的专门面───────
// 定位延续 rd-3 归档读法：观察读数 = 排查材料，不进任何默认层、不做
// 运营仪表盘。组织：人话摘要一行封顶 + 六表逐表 #21 折叠（默认全收）
// + 指标定义折叠（英文原文不翻译，8.3 原则）；表内原值直出（#9 mono
// + tabular-nums——零图表、零彩色、零徽章，账页不是看板）。
// 诚实口径（摘要在案）：spec 摘要行语汇的「本会话轮数 / 批注递出数 /
// 误报数」在现役 observations 读面（六表 durable counts + 漂移信号）
// 无直接对应列——摘要行给可得计数（六表行数 + 漂移行数），不硬凑
// 无源的数。第一次展开（进屏）才拉。
async function loadObservationsFace() {
  const board = diagBox("obs-board");
  const summary = diagBox("obs-summary");
  board.textContent = "";
  board.appendChild(stateBanner("loading"));
  let data = null;
  try {
    data = await fetchObservations();
  } catch {
    data = null;
  }
  board.textContent = "";
  if (!data) {
    diagError(board, "观察读数没取到。", loadObservationsFace);
    return;
  }
  const sections = data.sections || [];
  let rowCount = 0;
  for (const s of sections) rowCount += (s.rows || []).length;
  summary.hidden = false;
  summary.textContent = "";
  summary.appendChild(document.createTextNode(
    "六表 " + sections.length + " 张 · " + rowCount + " 行 · 门规漂移 "));
  const drift = document.createElement("span");
  drift.className = "sumnum";
  drift.textContent = String(data.drift_count ?? 0);
  drift.title = String(data.drift_reason || "");
  summary.appendChild(drift);
  summary.appendChild(document.createTextNode(" 行。"));
  for (const s of sections) {
    const content = document.createElement("div");
    if (s.error !== null && s.error !== undefined) {
      const err = document.createElement("p");
      err.className = "note";
      err.textContent = "这张表读不出来（" + s.error + "）。";
      content.appendChild(err);
    } else {
      const rows = s.rows || [];
      if (!rows.length) {
        const none = document.createElement("p");
        none.className = "note";
        none.textContent = "（无行）";
        content.appendChild(none);
      }
      for (const row of rows) {
        const line = document.createElement("div");
        line.className = "kv";
        const b = document.createElement("b");
        b.textContent = String(row[0] ?? "");
        line.appendChild(b);
        line.appendChild(document.createTextNode(row.slice(1).join(" | ")));
        content.appendChild(line);
      }
    }
    board.appendChild(disclosure({ name: s.title, content }).root);
  }
  // 指标定义：英文原文折叠呈现不翻译（8.3「观察读数」行的原则）
  const defs = document.createElement("div");
  for (const ind of data.indicators || []) {
    const line = document.createElement("p");
    line.className = "taxref";
    line.textContent = ind.indicator + " — " + ind.definition;
    defs.appendChild(line);
  }
  board.appendChild(disclosure(
    { name: "指标定义（原文）", content: defs }).root);
}

// 档案节折叠内的入口行：一行按钮进专门面（零数据拉取——摘要与六表
// 都在专门面第一次进入时才读）。
diagBox("obs-entry").appendChild((() => {
  const wrap = document.createElement("p");
  const go = document.createElement("button");
  go.type = "button";
  go.className = "btn btn--pencil";
  go.textContent = "翻开原始读数 →";
  go.addEventListener("click", () => {
    showSpace("obs");
    loadObservationsFace();
  });
  wrap.appendChild(go);
  return wrap;
})());

// ── v2-2: 信档屏（8.2.11 结构重铸件）——以前的信的专门面────────────
// 信封形接线（T1-4 封/信分物）：条目 = 信封缩略（.env-mini），点条目
// 展开读 = 信纸（letterNode 复用 #4 排印骨架——单一出处，非第二份
// 信件实现），展开动效 = paper-unfold。归档戳挂点：翻开信档 = 归档
// 开启（T2 邮戳三真实事件之一）——屏头一枚日期戳（--ink-ghost，同屏
// 恰此一枚；日期 = 打开当天，客户端真实日期）。口径诚实：只摊开
// /api/history 已加载的窗口（默认 50 轮；「加载更早」按 50 轮一档
// 往前翻，翻到头有一句收尾），第 n 封按窗口内顺序数（8.2.5 同
// 口径）；历史轮次无时间戳，一个日期都不造。
let lettersLoaded = false;
// 当前信档窗口的显式宽度（null = 默认 50 轮；每按一次「加载更早」
// 加一档），失败重试时归零回默认。
let lettersWindow = null;

function openLettersArchive() {
  showSpace("letters");
  const slot = diagBox("letters-datestamp");
  slot.textContent = "";
  const stamp = document.createElement("span");
  stamp.className = "postmark postmark--archived";
  const word = document.createElement("span");
  const now = new Date();
  word.textContent = (now.getMonth() + 1) + "·" + now.getDate() + " 归档";
  stamp.appendChild(word);
  slot.appendChild(stamp);
  if (!lettersLoaded) loadLetters();
}

async function loadLetters() {
  const board = diagBox("letters-board");
  board.textContent = "";
  board.appendChild(stateBanner("loading"));
  let data = null;
  try {
    data = await fetchHistory(lettersWindow ? { limit: lettersWindow }
                                            : undefined);
  } catch {
    data = null;
  }
  board.textContent = "";
  if (!data) {
    diagError(board, "信档没取到。", () => {
      lettersLoaded = false;
      lettersWindow = null;
      loadLetters();
    });
    return;
  }
  lettersLoaded = true;
  const turns = data.turns || [];
  if (!turns.length) {
    diagEmpty(board, "还没有信——第一封还没写。");
    return;
  }
  for (let i = 0; i < turns.length; i += 1) {
    board.appendChild(letterLine(i, turns[i]));
  }
  // 加载更早（主线-2）：has_more 是服务端的诚实分页位（多取一行判的，
  // 不是猜的）——有就给一档 50 轮的「加载更早」；翻到头给一句收尾，
  // 按钮退役。第 n 封始终按当前窗口内的顺序数。
  if (data.has_more) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "btn btn--pencil";
    more.textContent = "加载更早";
    more.addEventListener("click", () => {
      lettersWindow = (data.window || turns.length) + 50;
      loadLetters();
    });
    board.appendChild(more);
  } else if (lettersWindow !== null) {
    const end = document.createElement("p");
    end.className = "note";
    end.textContent = "更早的信没有了——以上是全部。";
    board.appendChild(end);
  }
}

// 一条信档：信封缩略 + 第 n 封 + 首行摘要，点开 = 该轮的两张信纸
// （我方撕边 / 笔友平信——letterNode 的两臂原样）。
function letterLine(index, turn) {
  const line = document.createElement("div");
  line.className = "letterline";
  const head = document.createElement("button");
  head.type = "button";
  head.className = "letterline-head";
  head.setAttribute("aria-expanded", "false");
  const mini = document.createElement("span");
  mini.className = "env-mini";
  mini.setAttribute("aria-hidden", "true");
  head.appendChild(mini);
  const no = document.createElement("span");
  no.className = "letterline-no";
  no.textContent = "第 " + (index + 1) + " 封";
  head.appendChild(no);
  const snippet = document.createElement("span");
  snippet.className = "letterline-snippet";
  const sides = [];
  if (turn.user !== null && turn.user !== undefined) sides.push(turn.user);
  if (turn.assistant !== null && turn.assistant !== undefined) {
    sides.push(turn.assistant);
  }
  snippet.textContent = sides.join(" / ").slice(0, 80);
  head.appendChild(snippet);
  line.appendChild(head);
  const body = document.createElement("div");
  body.className = "letterline-body";
  body.hidden = true;
  if (turn.user !== null && turn.user !== undefined) {
    body.appendChild(letterNode("user", turn.user));
  }
  if (turn.assistant !== null && turn.assistant !== undefined) {
    body.appendChild(letterNode("assistant", turn.assistant));
  }
  line.appendChild(body);
  head.addEventListener("click", () => {
    const open = body.hidden;
    body.hidden = !open;
    head.setAttribute("aria-expanded", open ? "true" : "false");
  });
  return line;
}

document.getElementById("letters-go").addEventListener(
  "click", openLettersArchive);
document.getElementById("letters-back").addEventListener(
  "click", () => showSpace("parlor"));
document.getElementById("obs-back").addEventListener("click", () => {
  showSpace("study");
  showSection("study", "progress");   // 回档案节（入口所在处）
});

// ⑩ 层级宪法的统一关闭语义（Esc 逐层退栈）——全页的最后一层：全页
// （笔友档案 / 信档 → 案头；原始读数 → 温故 · 档案，与各自返回钮同
// 效）。容器与浮层在全页不在场（互斥半：进空间即收），这层 Esc 只在
// 全页现役时接得住——与沓容器的 envselEsc（空间内层）互不越界。
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const current = Object.keys(spaces).find((key) => !spaces[key].hidden);
  if (current === "partner" || current === "letters") {
    showSpace("parlor");
  } else if (current === "obs") {
    showSpace("study");
    showSection("study", "progress");
  }
});

// ── rd-4: 搜信里的句子（档案节检索扩展；9.12-23）────────────────────
// 口径如实写在脸上：只搜检索自己读的默认窗口最近 50 轮（/api/history
// 不带宽度参数的读面——「加载更早」翻进信档的更早轮次不在检索面）；
// 命中列「第 n 封（你/笔友）」+ 片段——历史轮次没有时间戳，一个日期
// 都不造（第 n 封按已加载窗口内的顺序数）；同一轮两侧都命中就列两行。
// 窗口读数带十秒保鲜（LETTER_SEARCH_TTL）——新寄的信不等刷新就能搜
// 到，口径句照旧成立。跨信重现（同一表达在几封信里的足迹）已由表达
// 足迹读面落成（主线-2：/api/target_footprint + 按表达看的「足迹」
// 入口，9.12-23④ 数据缝就此闭合）——检索本身不升级。
const LETTER_SEARCH_TTL = 10000;

function mountLetterSearch() {
  const box = diagBox("letter-search");
  box.textContent = "";
  const input = document.createElement("input");
  input.type = "text";
  input.autocomplete = "off";
  input.placeholder = "搜信里的一句话……";
  const findLabel = document.createDocumentFragment();
  findLabel.appendChild(inkIcon("search"));
  findLabel.appendChild(document.createTextNode(" 搜"));
  box.appendChild(fieldRow(findLabel, input));
  const result = document.createElement("div");
  box.appendChild(result);
  let history = null;
  let historyAt = 0;
  let historyPending = null;
  input.addEventListener("input", async () => {
    const q = input.value.trim().toLowerCase();
    result.textContent = "";
    if (!q) return;
    if (!history || Date.now() - historyAt > LETTER_SEARCH_TTL) {
      // 单飞（OCR 处置三 #4）：并发按键共用一次在途请求，结果不交叠
      if (!historyPending) {
        historyPending = fetchHistory().then((h) => {
          history = h;
          historyAt = Date.now();
        }).finally(() => { historyPending = null; });
      }
      try {
        await historyPending;
      } catch {
        // 读失败不谎报「没有」（OCR 处置三 #5）：失败态如实、下次再试
        result.appendChild(stateBanner("error",
          { text: "信箱这会儿没翻开——稍后再搜一次。" }));
        return;
      }
    }
    let hits = 0;
    const turns = history.turns || [];
    for (let i = 0; i < turns.length; i += 1) {
      const sides = [["你", turns[i].user], ["笔友", turns[i].assistant]];
      for (const [who, text] of sides) {
        if (text === null || text === undefined) continue;
        const at = String(text).toLowerCase().indexOf(q);
        if (at < 0) continue;
        hits += 1;
        const line = document.createElement("div");
        line.className = "kv";
        const b = document.createElement("b");
        b.textContent = "第 " + (i + 1) + " 封（" + who + "）";
        line.appendChild(b);
        const start = Math.max(0, at - 20);
        const end = at + q.length + 20;
        line.appendChild(document.createTextNode(
          (start > 0 ? "…" : "") +
          String(text).slice(start, end).trim() +
          (end < String(text).length ? "…" : "")));
        result.appendChild(line);
      }
    }
    if (!hits) {
      result.appendChild(stateBanner("empty",
        { text: "这五十轮里没有这一句。" }));
    }
  });
}
mountLetterSearch();

// p-1: 点词——信件与用户回条里的 .word 可点。以点击词为中心取 1–3 词
// 窗口（长窗优先），逐窗口调 /api/word，首个命中即出卡；miss 按契约
// 静默（不弹「没查到」浮层）。stopPropagation 让开卡点击不被浮层的
// 「点卡外关闭」监听立即收掉。
// ux-1: 最近词兜底——命中带外扩后仍会点在行距/词间空隙（触屏尤甚），
// 以落点的文本位（caretRangeFromPoint / caretPositionFromPoint）归到
// .letter .say，取该 .say 里字心欧氏距离最近的 .word；caret 取不到、
// 不在任何 .letter .say 里或该 .say 没有词，就保持静默 miss 契约。
// 精确命中仍走快路径，行为一字不变。
function wordFromCaret(event) {
  const doc = document;
  let node = null;
  if (typeof doc.caretRangeFromPoint === "function") {
    const range = doc.caretRangeFromPoint(event.clientX, event.clientY);
    if (range) node = range.startContainer;
  } else if (typeof doc.caretPositionFromPoint === "function") {
    const pos = doc.caretPositionFromPoint(event.clientX, event.clientY);
    if (pos) node = pos.offsetNode;
  }
  const holder = node && (node.nodeType === 1 ? node : node.parentElement);
  const say = holder && holder.closest(".letter .say");
  if (!say) return null;
  let best = null;
  let bestD = Infinity;
  for (const span of say.querySelectorAll(".word")) {
    const box = span.getBoundingClientRect();
    const dx = event.clientX - (box.left + box.width / 2);
    const dy = event.clientY - (box.top + box.height / 2);
    const d = dx * dx + dy * dy;
    if (d < bestD) {
      bestD = d;
      best = span;
    }
  }
  return best;
}

messages.addEventListener("click", async (event) => {
  let target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.classList.contains("word")) {
    target = wordFromCaret(event);   // 兜底：点在字身框之外
    if (!target) return;
  }
  // v3-3 供性分层：无供性的词（word--off）点击即不拦截——样式已经
  // 说了「这个词没有卡」，行为与呈现一致，「点了没反应」不再出现。
  if (target.classList.contains("word--off")) return;
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
  showSpace("parlor");
});

// ── cs-2: 笔友档案（全页视图；rd-4 浮层卡与名册桩退役）────────────────
// 入口不变：品牌条 who 块整体可点（键盘可达），点开整页档案——同门厅
// cover 的整页形态，非浮层，导航条让位（showSpace 的 partner 臂），
// 返回钮回案头。数据只读 /api/partner 一个端点；角色文本的真源在服务
// 端单一出处（card 表 + official 官方家族，队列④），webui 零字面——
// 名字、身份行、散文全部来自端点。五面各走自己的三态（#14），读不到
// 的面自己报错，不拖累整页；在读在飞时人已回案头，就不往看不见的页
// 上写。

let dossierOpen = false;

const DOSSIER_SLOT_IDS = ["dossier-portrait", "dossier-memories",
                          "dossier-episode", "dossier-timeline"];

// 日期人话（通信统计与时间线）：今年 「10 月 1 日」，去年 「去年」，
// 更早 「更早」——一个更精的日期都不造，也不把更旧的信谎报成去年的
// （cs-2R INFO-4：往年一律「去年」是假话）；解析不了的原样直出。
function dossierDay(iso) {
  const then = new Date(String(iso));
  if (Number.isNaN(then.getTime())) return String(iso);
  const now = new Date();
  if (then.getFullYear() === now.getFullYear()) {
    return (then.getMonth() + 1) + " 月 " + then.getDate() + " 日";
  }
  if (then.getFullYear() === now.getFullYear() - 1) return "去年";
  return "更早";
}

// 时间线行的日（YYYY-MM-DD 纯日期串，不游时区）：拆串直读。
function dossierDayLabel(ymd) {
  const parts = String(ymd).split("-");
  if (parts.length !== 3) return String(ymd);
  return Number(parts[1]) + " 月 " + Number(parts[2]) + " 日";
}

function renderDossierHead(data) {
  const nameBox = diagBox("dossier-name");
  const identityBox = diagBox("dossier-identity");
  const statsBox = diagBox("dossier-stats");
  const card = data && data.card;
  if (!card) {
    nameBox.textContent = "档案没读到。";
    identityBox.textContent = "";
    statsBox.textContent = "";
    return;
  }
  nameBox.textContent = card.name;
  identityBox.textContent = card.identity_line;
  const stats = data.stats;
  statsBox.textContent = "";
  if (!stats || stats.error) {
    statsBox.textContent = "通信统计没读到。";
    return;
  }
  const parts = ["往来 " + (stats.turns || 0) + " 封"];
  if (stats.first_letter_at) {
    parts.push("第一封 " + dossierDay(stats.first_letter_at));
  }
  if (stats.latest_letter_at) {
    parts.push("最近一封 " + dossierDay(stats.latest_letter_at));
  }
  statsBox.textContent = parts.join(" · ") + "。";
}

// 人物节：角色包叙事化成散文（背景 / 价值观 / 写信习惯），非表格非
// 字段墙——三段各归各的中文小节名，正文原样（服务端来什么写什么）。
function renderDossierPortrait(card) {
  const box = diagBox("dossier-portrait");
  box.textContent = "";
  if (!card) {
    box.appendChild(stateBanner("error",
      { text: "人物这一面没读到。", retry: openPartnerDossier }));
    return;
  }
  const faces = [
    ["她的日子", card.background],
    ["她看重的事", card.values],
    ["她写信的样子", card.letter_habits],
  ];
  for (const face of faces) {
    const head = document.createElement("p");
    head.className = "dossier-prosehead";
    head.textContent = face[0];
    box.appendChild(head);
    const para = document.createElement("p");
    para.className = "dossier-prose";
    para.textContent = String(face[1] || "");
    box.appendChild(para);
  }
}

// 她记得的关于你的事：诚实措辞——她记得的只是信里说过的，不一定
// 完整，也不承诺记得更多；空态诚实（还没记住什么——聊聊你自己）。
function renderDossierMemories(memories) {
  const box = diagBox("dossier-memories");
  box.textContent = "";
  if (!memories || memories.error) {
    box.appendChild(stateBanner("error",
      { text: "记忆这一面没读到。", retry: openPartnerDossier }));
    return;
  }
  const note = document.createElement("p");
  note.className = "sub";
  note.textContent =
    "她记得的只是信里说过的——不一定完整，也不会比你说得多。";
  box.appendChild(note);
  const rows = memories.memories || [];
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "note";
    empty.textContent = "还没记住什么——聊聊你自己。";
    box.appendChild(empty);
    return;
  }
  for (const m of rows) {
    const line = document.createElement("p");
    line.className = "dossier-memory";
    line.textContent = String(m.content);
    box.appendChild(line);
  }
}

function renderDossierEpisode(episodeFace) {
  const box = diagBox("dossier-episode");
  box.textContent = "";
  if (!episodeFace || episodeFace.error) {
    box.appendChild(stateBanner("error",
      { text: "近况这一面没读到。", retry: openPartnerDossier }));
    return;
  }
  const row = episodeFace.episode;
  if (!row) {
    box.appendChild(stateBanner("empty",
      { text: "还没有留下近况——通信还在早头。" }));
    return;
  }
  const summary = document.createElement("p");
  summary.className = "dossier-prose";
  summary.textContent = String(row.summary);
  box.appendChild(summary);
  const threads = Array.isArray(row.open_threads) ? row.open_threads : [];
  if (threads.length) {
    const head = document.createElement("p");
    head.className = "dossier-prosehead";
    head.textContent = "还没说完的话头";
    box.appendChild(head);
    for (const thread of threads) {
      const line = document.createElement("p");
      line.className = "dossier-memory";
      line.textContent = String(thread);
      box.appendChild(line);
    }
  }
}

function renderDossierTimeline(stats) {
  const box = diagBox("dossier-timeline");
  box.textContent = "";
  if (!stats || stats.error) {
    box.appendChild(stateBanner("error",
      { text: "通信的日子这一面没读到。", retry: openPartnerDossier }));
    return;
  }
  const days = stats.timeline || [];
  if (!days.length) {
    box.appendChild(stateBanner("empty",
      { text: "还没有通过信——第一封还没写。" }));
    return;
  }
  for (const day of days) {
    const line = document.createElement("p");
    line.className = "dossier-day";
    const b = document.createElement("b");
    b.textContent = dossierDayLabel(day.date);
    line.appendChild(b);
    line.appendChild(document.createTextNode(" · " + day.turns + " 封"));
    box.appendChild(line);
  }
}

function renderDossier(data) {
  renderDossierHead(data);
  renderDossierPortrait(data && data.card);
  renderDossierMemories(data && data.memories);
  renderDossierEpisode(data && data.episode);
  renderDossierTimeline(data && data.stats);
}

// mc-1：档案参数化——不带参数读正服务角色的原面（cs-2 原样）；带
// character_id 走 /api/partner?character_id=（信封沓的「档案」动作从
// 沓中任意一封进，读的就是那一位的卡与她自己的通信）。
async function openPartnerDossier(characterId) {
  dossierOpen = true;
  showSpace("partner");
  diagBox("dossier-name").textContent = "";
  diagBox("dossier-identity").textContent = "";
  diagBox("dossier-stats").textContent = "";
  for (const id of DOSSIER_SLOT_IDS) {
    const box = diagBox(id);
    box.textContent = "";
    box.appendChild(stateBanner("loading"));
  }
  let data = null;
  try {
    data = characterId
      ? await fetchPartnerOf(characterId)
      : await fetchPartner();
  } catch {
    data = null;
  }
  if (!dossierOpen) return;  // 人已回案头——不往看不见的页上写
  renderDossier(data);
}

function closePartnerDossier() {
  dossierOpen = false;
  showSpace("parlor");
}

// 触发与信封沓在文件尾的 mc-1 模块（接线顺序无关紧要——type="module"
// 全模块求值完后 DOMContentLoaded 才发；放尾部是 fg2「品牌印记先于
// 首次取数」位序钉的伴生事实：loadHistory 的首现保持在原位）。

// 返回钮：档案页的唯一回途（导航条在本页让位）。
document.getElementById("partner-back").addEventListener(
  "click", closePartnerDossier);

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

// R-1R（⑧ 8.2.2）：空厅不是一间空屋——历史为空时信流中央一行系统
// 小字（客户端静态系统行，非伪造历史）；第一封信寄出即撤。rd-2 豪放档
// 重写（语义底线①③在场：中文可写 + 写错被接住——placeholder 让位
// 「今日如何？」锚例后，不读封面也能从这里得知中文可写）。
const EMPTY_HALL_TEXT =
  "信还没开始写——想从哪句起，就从哪句起。中文英文都行；写错了，笔友接得住。";

function showEmptyHall() {
  if (messages.firstChild) return;
  const line = addLine("system", EMPTY_HALL_TEXT);
  line.classList.add("emptyhall");
  // R-1V：空厅配墨线小图（⑨-4 inbox——空信箱；图是装饰，定稿句不动）
  line.prepend(inkIcon("inbox"));
}

function dismissEmptyHall() {
  for (const line of Array.from(messages.querySelectorAll(".emptyhall"))) {
    line.remove();
  }
}

async function postTurn(text) {
  dismissEmptyHall();
  // 寄出的当下 = 信件日期行的真实时间源（客户端本机时间；web.py 冻结
  // 面故 /api/turn 无时间戳字段——新信落当下、历史不造）。
  const sentAt = new Date().toISOString();
  const mine = addLine("user", text, { enter: true, when: sentAt });
  // fr-A：寄出的这一轮即刻入刻度（usage 待响应落地回填——P2c）。
  flowTurns.push({ node: mine, usage: null });
  buildFlowRuler();
  // v2 封/信分物（简报 T1-4）：刚寄出的信装封在途——信封形（矩形 +
  // 封舌 + 折线，信文暂不可见），回信落地或失败即摘封见信；封上盖
  // 「寄出」邮戳（邮戳三真实事件之一——T2；盖印 120ms 唯一 overshoot，
  // 类由 animationend 自摘；reduced-motion 下 0.01ms 即终、事件仍到）。
  mine.classList.add("en-route");
  const postmark = document.createElement("span");
  postmark.className = "postmark postmark--sent stamp-press";
  const word = document.createElement("span");
  word.textContent = "寄出";
  postmark.appendChild(word);
  postmark.addEventListener("animationend",
    () => postmark.classList.remove("stamp-press"), { once: true });
  mine.appendChild(postmark);
  // the placeholder is the user's "it is working" signal: removed the
  // moment the turn response lands (or fails) — never left behind.
  // rd-2：发送后状态行「信已寄出，等回信——」收尾（8.5 流式落点句随迁）
  const pending = addLine("typing", "信已寄出，等回信——笔友把灯留着。");
  startMomentPolling();
  let data = null;
  try {
    data = await fetchTurn(text);
  } catch {
    addLine("failure", "请求没送到——再试一次。");
  } finally {
    stopMomentPolling();
    pending.remove();
    // 摘封：回信落地（或失败）即从在途信封回到撕口信纸——同一 DOM，
    // 无拆信演出（T3 死刑清单）；「寄出」邮戳随信封一并离场。
    mine.classList.remove("en-route");
    const stamp = mine.querySelector(".postmark--sent");
    if (stamp) stamp.remove();
  }
  if (data !== null) {
    // v3-3 供性后装：寄出的信在位图到达前全供性（信还封着在途）；回信
    // 落地即按 turn 响应把用户信的 0 位降为无供性（applyLetterAffordance
    // 只摘不加，方向恒向不可点收）。
    applyLetterAffordance(mine, data.user_word_hits || null);
    // fr-A：这一轮的 usage 回填轮锚（/api/turn 随行）+ 累计读回刷新。
    flowTurns[flowTurns.length - 1].usage = data.usage || null;
    refreshFlowMeter();
    if (data.reply !== null && data.reply !== undefined) {
      addLine("assistant", data.reply,
        { enter: true, when: new Date().toISOString(),
          hits: data.word_hits || null });
    } else if (data.turn_status !== null && data.turn_status !== undefined) {
      failLine("这封信没有回音——笔友没能联系上模型端点",
        data.failure_reason || "无回复");
    } else if (data.failure_reason) {
      failLine("这封信没有回音——笔友没能联系上模型端点",
        data.failure_reason);
    }
    const moments = data.teaching_moments || [];
    showMoments(moments);
  }
}

async function postTeachMe(targetId) {
  let data = null;
  try {
    data = await fetchTeachMe(targetId);
  } catch {
    addLine("failure", "请求没送到——再试一次。");
    return;
  }
  if (data.accepted) {
    addLine("system", "批注来了——就在下面的信流里。");
    showSpace("parlor");
    startMomentPolling();
  } else {
    failLine("没能开始这张批注——", data.error || "被拒绝");
  }
}

// v2-1R M-3：在途只此一封——并发寄出会让多枚「寄出」邮戳同屏并立，
// 破简报 T2「同屏 ≤1 枚」；一封落地或失败（postTurn 的 finally）才
// 解锁输入。守卫只在客户端，服务端仍按到达序处理。
let sending = false;
document.getElementById("send").addEventListener("submit", (event) => {
  event.preventDefault();
  if (sending) return;
  const input = document.getElementById("text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  // v3-a 草稿层（8.2.2⑤，10.3-6 同一定谳）：寄出是唯一清稿时机——
  // 案头笔搁草稿桶与信同清；收起/Esc 一律保稿。
  try {
    sessionStorage.removeItem(dockDraftKey());
  } catch { /* 存储不可用——无稿可清 */ }
  // D-B 寄出编排（报告 §4.2）：写作态先收（落 = paper-fold 200ms 加速
  // 收势 + ink-wash reverse），信落信流的纸事件由 postTurn/addLine 承担
  // ——一屏一次纸事件；焦点回触发条（落旗先于收场——fold finish 时
  // 兑现，快慢端点两种时序都接得住）。
  const wasComposing = composeOpen();
  if (wasComposing) {
    composeFocusPending = true;
    closeComposeFace();
  }
  sending = true;
  input.disabled = true;
  // rd-1 邮戳盖下（⑨-5）：寄出一瞬邮票按下——scale .96→1 的 transform
  // 收束（非投影）；类由 animationend 自摘（reduced-motion 下动画
  // 0.01ms 即终、事件仍到，清理不失效）
  const stamp = document.querySelector("#send .btn--send");
  if (stamp) {
    stamp.classList.add("stamp-press");
    stamp.addEventListener("animationend",
      () => stamp.classList.remove("stamp-press"), { once: true });
  }
  postTurn(text).finally(() => {
    sending = false;
    input.disabled = false;
    // v3-a 焦点流：写作态寄出的旗已在收场前落（finish 兑现）；条态
    // 寄出 → 焦点留 textarea（现役续写手感原样）。
    if (!wasComposing) input.focus();
  });
});

// The pen is a lined-paper textarea (the anchor's own .pen): plain Enter
// posts the letter, Shift+Enter stays a line break.
document.getElementById("text").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.getElementById("send").requestSubmit();
  }
});

// ── v3-a D-B 信纸写作态（8.2.2⑤；⑩ 10.1 全页成员登记行；fr-A 收窄）──
// 两态同件：收起 = 笔搁触发条（44px，常驻税 163→104px 级）；点触发条/
// 寄出链 = 升起 .dock--compose「新信纸」——fr-A 起**高度随稿纸内容
// 自适应、上限 50dvh**（v3-a 的近全屏形态退役：写信不再遮全部信流，
// 上半上下文始终可见）。navdock 让位（fold 200ms 同 envsel--fold 语族）、
// Esc 收起（浮层裁决之后的一层）、草稿按角色分桶 sessionStorage（与起笔
// 草稿层 compose-draft-* 同构独立 key——10.3-6 同一定谳：退出保稿、寄出
// 即清）、稿纸 autosize 封顶内滚（composePenCap——全视口档统一形态，
// v3-a 的 520px 降级双形态随之退役）。
// ⑩ 层级互斥：升写作态先收浮层；开沓先收写作态（保稿，置灰优先——
// 10.3-5）；进任何空间收写作态（showSpace 同批）。
let composeFoldHandler = null;   // 收场动画的对账柄（重开即拆）
let composeFocusPending = false;   // 寄出路径的焦点归还——fold 收场时兑现

function dockDraftKey() {
  // 草稿桶 = 角色 id 派生（webui 零角色名字面——id 是机械键非文案）；
  // 无名册（current 为 null）落 local 桶，不发明归属。
  const cid = (charactersCache && charactersCache.current_character_id)
    || "";
  return "draft-" + (cid || "local");
}

function composeOpen() {
  const dock = document.querySelector(".dock");
  return Boolean(dock && dock.classList.contains("dock--compose"));
}

// 稿纸 autosize 的封顶（fr-A）：面板上限 50dvh 减去铬件账——上下垫
// （sp-4×2 = 32）+ 顶行（≈24）+ 称呼位（≈32）+ 寄出行（≈28）+ 余量
// （≈32）≈ 148px；下限 4×baseline（128）——横屏/分屏的矮视口也写得
// 了四行。CSS 侧 max-height: 50dvh 是最后一道闸；稿纸超出封顶内滚。
function composePenCap() {
  return Math.max(128, Math.floor(window.innerHeight / 2) - 148);
}

// 稿纸 autosize（fr-A 统一形态：写作态开着时随内容长高，封顶后内滚；
// 内联样式面在库——autosizeTo/clearAutosize）。收起态稿纸 hidden，
// 不量（autosizePen 的 composeOpen 守卫）。
function autosizePen() {
  const pen = document.getElementById("text");
  if (pen && composeOpen()) autosizeTo(pen, composePenCap());
}

// 写作面的排印骨架：dateline = 本机当日（与边注栏/封面同一真实数据源、
// 同一格式——机械事实非文案）；称呼位 = 致 + 当前角色名（.who 端点驱动
// 空槽，零字面——无名册时 hidden，不发明称呼）。
function fillComposeChrome() {
  const dateline = document.getElementById("compose-dateline");
  if (dateline) {
    const now = new Date();
    dateline.textContent = now.getFullYear() + " · " +
      String(now.getMonth() + 1).padStart(2, "0") + " · " +
      String(now.getDate()).padStart(2, "0");
  }
  const salut = document.getElementById("compose-salut");
  if (salut) {
    const who = document.querySelector("#space-parlor .who");
    const name = who ? who.textContent.trim() : "";
    salut.textContent = name ? "致 " + name + "，" : "";
    salut.hidden = !name;
  }
}

// navdock 让位（写作态 = 全页成员，同门厅/全页语族）：fold 200ms
// （paper-fold × --ease-exit）animationend 后落 [hidden] 摘类；
// reduced-motion 直落。fuse 内查写作态仍在场——快速收起时不得把
// 已归还的导航藏掉。
function yieldNavdock() {
  const navdock = document.getElementById("navdock");
  if (!navdock || navdock.hidden) return;
  const lay = () => {
    navdock.classList.remove("navdock--fold");
    navdock.removeEventListener("animationend", onEnd);
    if (composeOpen()) navdock.hidden = true;
  };
  const onEnd = (event) => {
    if (event.animationName !== "paper-fold") return;
    lay();
  };
  if (REDUCED_MOTION.matches) {
    navdock.hidden = true;
    return;
  }
  navdock.classList.add("navdock--fold");
  navdock.addEventListener("animationend", onEnd);
  setTimeout(lay, 480);   // 保险丝（animationend 正常先到）
}

// navdock 归位：按当前空间还其可见性（与 showSpace 同一账——门厅与
// 三全页让位、三空间常驻）；在飞 fold 即刻摘类（fill both 的冻结形防呆）。
function restoreNavdock() {
  const navdock = document.getElementById("navdock");
  if (!navdock) return;
  navdock.classList.remove("navdock--fold");
  const current = Object.keys(spaces).find((key) => !spaces[key].hidden);
  navdock.hidden = current === "onboard" || current === "partner" ||
    current === "letters" || current === "obs";
}

// Esc 逐层退栈（⑩ 10.4）：浮层在场 → 归浮层（wordCardOpen 裁决，它的
// 监听收它自己）；写作态 → 收起（保稿）。沓容器与写作态互斥（开沓先
// 收写作态），二者 Esc 不可能同拍。
function composeEsc(event) {
  if (event.key !== "Escape") return;
  if (wordCardOpen()) return;
  closeComposeFace({ refocus: true });
}

function openComposeFace() {
  const dock = document.querySelector(".dock");
  if (!dock || dock.classList.contains("dock--compose")) return;
  if (dock.classList.contains("dock--stilled")) return;   // 置灰优先（⑩ 10.3-5）
  // ⑩ 互斥：升全页写作态先收浮层；上一次收场的对账柄与落半类即拆
  //（快速重开不追认旧收场）。
  closeTokenMeterPop();
  closeWordCard({ skipOut: true });
  closeOpenSelects();
  if (composeFoldHandler) {
    dock.removeEventListener("animationend", composeFoldHandler);
    composeFoldHandler = null;
  }
  dock.classList.remove("dock-compose--out");
  const pen = document.getElementById("text");
  try {
    const draft = sessionStorage.getItem(dockDraftKey());
    if (draft) pen.value = draft;
  } catch { /* 隐私模式等存储不可用——退化为无草稿，不阻断写信 */ }
  fillComposeChrome();
  const face = document.getElementById("compose-face");
  if (face) face.hidden = false;
  const trigger = document.getElementById("dock-trigger");
  if (trigger) {
    trigger.hidden = true;
    trigger.setAttribute("aria-expanded", "true");
  }
  dock.classList.add("dock--compose");
  if (!REDUCED_MOTION.matches) {
    dock.classList.add("dock-compose--in");
    const settleIn = (event) => {
      if (event.animationName !== "paper-drop") return;
      dock.classList.remove("dock-compose--in");
      dock.removeEventListener("animationend", settleIn);
    };
    dock.addEventListener("animationend", settleIn);
    setTimeout(() => dock.classList.remove("dock-compose--in"), 680);
  }
  yieldNavdock();
  document.addEventListener("keydown", composeEsc);
  pen.focus();
  autosizePen();
  syncFlowBottom();
  syncFlowRuler();
}

function closeComposeFace(opts) {
  const dock = document.querySelector(".dock");
  if (!dock || !dock.classList.contains("dock--compose")) return;
  document.removeEventListener("keydown", composeEsc);
  const pen = document.getElementById("text");
  if (pen) clearAutosize(pen);   // autosize 内联高归还（降级态→正常态）
  const finish = () => {
    if (composeFoldHandler) {
      dock.removeEventListener("animationend", composeFoldHandler);
      composeFoldHandler = null;
    }
    dock.classList.remove("dock--compose", "dock-compose--out");
    const face = document.getElementById("compose-face");
    if (face) face.hidden = true;
    const trigger = document.getElementById("dock-trigger");
    restoreNavdock();
    syncFlowBottom();
    syncFlowRuler();
    renderTokenMeter();   // veto-R：写作态让位收场，计量粒归位（藏/现对账）
    // v3-a 焦点归还（两源一收口）：寄出路径（composeFocusPending——
    // postTurn 的 finally 落旗，此处兑现：fold 未收完时触发条还 hidden，
    // 直接 focus 会竞态落空）与用户显式退出（opts.refocus）——触发条
    // 接笔，写信焦点流不丢；空间切换/开沓路径两源皆空，不抢焦点。
    if (trigger) {
      trigger.hidden = false;
      trigger.setAttribute("aria-expanded", "false");
      if (composeFocusPending) {
        composeFocusPending = false;
        trigger.focus();
      } else if (opts && opts.refocus) {
        trigger.focus();
      }
    }
  };
  if (REDUCED_MOTION.matches) {
    finish();
    return;
  }
  // 落半（报告 §4.2）：paper-fold 200ms × --ease-exit + ink-wash reverse
  // 恒慢——收势与沓家 fold 同语族；**墨腿 animationend 对账**（最慢腿——
  // 纸腿 200ms 先终即 finish 会把还剩三成墨的写信面硬切 [hidden]，同
  // closeEnvelopeSelector 根因修）+ 480ms 保险丝。
  dock.classList.add("dock-compose--out");
  composeFoldHandler = (event) => {
    if (event.animationName !== "ink-wash" || event.target !== dock) return;
    finish();
  };
  dock.addEventListener("animationend", composeFoldHandler);
  setTimeout(() => {
    if (dock.classList.contains("dock-compose--out")) finish();
  }, 480);
}

document.getElementById("dock-trigger").addEventListener(
  "click", openComposeFace);
document.getElementById("compose-close").addEventListener(
  "click", () => closeComposeFace({ refocus: true }));
// 触屏辅出口（报告 §4.2 D-B 状态矩阵）：面板铬件上下滑（|dy|>|dx| 且
// >60px）= 收起——收起钮/Esc 是主出口，下滑只是补充；识别纪律同
// wirePanelSwipe（touch 只做识别、零 preventDefault、passive；起点在
// 稿纸/动作件上不识别——稿纸内滚动优先）。
(function wireComposeSwipe() {
  const face = document.getElementById("compose-face");
  if (!face) return;
  let x0 = 0;
  let y0 = 0;
  let live = false;
  face.addEventListener("touchstart", (event) => {
    live = event.touches.length === 1 &&
      !event.target.closest("textarea, button, input, select, a");
    if (live) {
      x0 = event.touches[0].clientX;
      y0 = event.touches[0].clientY;
    }
  }, { passive: true });
  face.addEventListener("touchcancel", () => { live = false; },
    { passive: true });
  face.addEventListener("touchend", (event) => {
    if (!live) return;
    live = false;
    const dy = event.changedTouches[0].clientY - y0;
    const dx = event.changedTouches[0].clientX - x0;
    if (dy > 60 && Math.abs(dy) > Math.abs(dx)) closeComposeFace();
  }, { passive: true });
})();
// 草稿随写随存（10.3-6 同一定谳的桶半区）；收起/Esc 不清（保稿），
// 唯一清稿时机 = 寄出（submit 半区）。
document.getElementById("text").addEventListener("input", () => {
  const pen = document.getElementById("text");
  try {
    sessionStorage.setItem(dockDraftKey(), pen.value);
  } catch { /* 存储不可用——存不上也不打断 */ }
  autosizePen();
});
// 视口尺寸变化时重量稿纸封顶（fr-A：50dvh 随视口变；写作态开着才量——
// 收起态无内联高可还，重开时 openComposeFace 自会再量）。
window.addEventListener("resize", () => {
  if (composeOpen()) autosizePen();
});

// ── fr-A 一键回底（#24 悬浮墨点）────────────────────────────────────
// flow 是整页滚动（body 滚动井）：离底超过阈值（240px——约一屏的信流
// 上下文）墨点浮现，在底即藏；写作态开着藏（稿纸面板自己占底）；离案头
// 藏（#space-parlor 的 hidden 账）。点击平滑回底（reduced-motion 直落）。
const flowBottomBtn = document.getElementById("flow-bottom");
const FLOW_BOTTOM_THRESHOLD = 240;

function flowDistanceFromBottom() {
  return Math.max(0, document.body.scrollHeight - window.innerHeight -
    window.scrollY);
}

function syncFlowBottom() {
  if (!flowBottomBtn) return;
  flowBottomBtn.hidden = Boolean(spaces.parlor.hidden) || composeOpen() ||
    flowDistanceFromBottom() < FLOW_BOTTOM_THRESHOLD;
}

if (flowBottomBtn) {
  flowBottomBtn.addEventListener("click", () => {
    window.scrollTo({ top: document.body.scrollHeight,
                      behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });
  });
  window.addEventListener("scroll", syncFlowBottom, { passive: true });
  window.addEventListener("resize", syncFlowBottom);
  // veto-R（⑨）：刻度高亮的 scroll 对账改 rAF 节流——被动 listener 只
  // 置旗，一帧至多量一次轮锚位（滚动风暴下不逐事件量 DOM）。
  window.addEventListener("scroll", scheduleFlowRulerSync, { passive: true });
  window.addEventListener("resize", scheduleFlowRulerSync);
}

// veto-R 计量粒（#26）：dock 上沿内嵌读数钮的点击面——点按展开/收起
// 逐轮明细浮层。
const tokenMeterPill = document.getElementById("tokenmeter");
if (tokenMeterPill) {
  tokenMeterPill.addEventListener("click", toggleTokenMeterPop);
}

// ── fr-A 轮次刻度（#25；veto-R 一一对应收紧）─────────────────────────
// 每轮交流一个刻度点，刻度点 ↔ flowTurns 轮锚**一一绑定**（buildFlowRuler
// 按同一数组逐一生成，第 n 点即第 n 轮）。当前视位高亮按真实锚点位置
// 计算：视位线 = 顶栏之下一档呼吸（FLOW_TURN_OFFSET，与点击跳转同一
// 条线），取最后一个起点已过线的轮；scroll 对账走 rAF 节流的被动
// listener（一帧至多量一次锚位）；点击 = 精确滚到该轮锚点（锚顶对齐
// 视位线——scrollIntoView block:start 的等价对齐，含 72px 顶栏让位）。
// 底部判据（在底 = 最新一轮）不变。刻度基于已加载窗口（/api/history
// 默认 50 轮）；未加载的更早部分由信流顶部的「加载更早」衔接（按 50
// 轮一档往前翻——主线-2 的显式宽度参数），口径句写在信流顶部。≥2 轮
// 才现身；写作态/离案头即藏。
let flowRulerSyncQueued = false;

function scheduleFlowRulerSync() {
  if (flowRulerSyncQueued) return;
  flowRulerSyncQueued = true;
  requestAnimationFrame(() => {
    flowRulerSyncQueued = false;
    syncFlowRuler();
  });
}
let flowTurns = [];        // 已加载窗口的轮锚（{node, usage}）
let parlorWindow = null;   // 案头信流的显式宽度（null = 默认窗口）
let lastHistoryWindow = null;   // 服务端回执的窗口宽度（加载更早的基数）
//: 刻度视线 / 跳转落点 = 顶栏（.top 46px）之下一档呼吸——同一常数两处
//: 消费：点击跳转把该轮起点放上视线，scroll spy 再把视线那一轮点亮。
const FLOW_TURN_OFFSET = 72;

function flowSpyTick() {
  if (!flowTurns.length) return -1;
  // 在底 = 最新一轮（末点）——短尾信不因锚点离视线远而丢高亮。
  if (flowDistanceFromBottom() <= 4) return flowTurns.length - 1;
  // 视线 = 顶栏之下（FLOW_TURN_OFFSET）：取最后一个起点在视线之上的轮
  // ——与 scrollToFlowTurn 的落点同一条线，点第 n 点即第 n 点亮；单调
  // （往下滚高亮只会往后走）。
  const line = window.scrollY + FLOW_TURN_OFFSET;
  let index = 0;
  for (let i = 0; i < flowTurns.length; i += 1) {
    const top = flowTurns[i].node.getBoundingClientRect().top +
      window.scrollY;
    if (top > line) break;
    index = i;
  }
  return index;
}

function scrollToFlowTurn(index, instant) {
  const turn = flowTurns[index];
  if (!turn) return;
  const top = turn.node.getBoundingClientRect().top + window.scrollY -
    FLOW_TURN_OFFSET;
  window.scrollTo({ top: Math.max(0, top),
                    behavior: (instant || REDUCED_MOTION.matches)
                      ? "auto" : "smooth" });
}

function syncFlowRuler() {
  const ruler = document.getElementById("flow-ruler");
  if (!ruler) return;
  const show = !spaces.parlor.hidden && !composeOpen() &&
    flowTurns.length >= 2;
  ruler.hidden = !show;
  if (!show) return;
  const current = flowSpyTick();
  Array.from(ruler.children).forEach((tick, i) => {
    const on = i === current;
    tick.classList.toggle("flow-tick--on", on);
    if (on) tick.setAttribute("aria-current", "true");
    else tick.removeAttribute("aria-current");
  });
}

function buildFlowRuler() {
  const ruler = document.getElementById("flow-ruler");
  if (!ruler) return;
  ruler.textContent = "";
  flowTurns.forEach((turn, i) => {
    const tick = document.createElement("button");
    tick.type = "button";
    tick.className = "flow-tick";
    tick.setAttribute("aria-label", "第 " + (i + 1) + " 轮");
    tick.addEventListener("click", () => scrollToFlowTurn(i));
    ruler.appendChild(tick);
  });
  syncFlowRuler();
}

// 信流顶部的口径行（主线-2 同口径）：刻度只管已加载的窗口；「加载更早」
// 往前翻（has_more 是服务端的诚实分页位），翻到头给一句收尾——按过
// 「加载更早」才说这句（与信档屏同一读法）。
function renderFlowCalibre(data) {
  const line = document.createElement("p");
  line.className = "flow-calibre";
  if (data.has_more) {
    line.appendChild(document.createTextNode(
      "刻度只管已加载的窗口——"));
    const more = document.createElement("button");
    more.type = "button";
    more.className = "btn btn--pencil";
    more.textContent = "加载更早";
    more.addEventListener("click", loadEarlierLetters);
    line.appendChild(more);
    line.appendChild(document.createTextNode(" 往前翻。"));
  } else if (parlorWindow !== null) {
    line.textContent = "更早的信没有了。";
  } else {
    return;
  }
  messages.appendChild(line);
}

// ── fr-A token 计量（#26）────────────────────────────────────────────
// 显示开关存 sessionStorage（客户端侧面——查过 user_config 现面：§5.1
// 旋钮列是 canonical 教学配置、user_profile.settings 是披露给笔友的事
// 实，都没有 UI 偏好的合适面——如实标注：只存在这个标签页这次会话里，
// 关掉标签页就复位）。数据面：/api/history 的累计（窗口无关的会话全量
// ——读回来的就是存下的，客户端不做本地加减）+ 每轮 usage（轮锚随行）。
const TOKEN_METER_KEY = "elc-token-meter";
let tokenMeterOn = tokenMeterStored();
let tokenMeterData = null;   // 会话累计（measured_calls/total_calls 随行）

function tokenMeterStored() {
  try { return sessionStorage.getItem(TOKEN_METER_KEY) === "1"; }
  catch { return false; }   // 隐私模式等存储不可用——当次不开
}

function setTokenMeter(on) {
  tokenMeterOn = Boolean(on);
  try {
    if (tokenMeterOn) sessionStorage.setItem(TOKEN_METER_KEY, "1");
    else sessionStorage.removeItem(TOKEN_METER_KEY);
  } catch { /* 存储不可用——开关只活在内存里 */ }
  renderTokenMeter();
}

function tokenCount(word) {
  return (word === null || word === undefined) ? "—" : String(word);
}

function tokenNum(word) {
  const num = document.createElement("b");
  num.className = "tm-num";
  num.textContent = tokenCount(word);
  return num;
}

// 计量粒（veto-R 重铸，用户否决常驻遮挡的 sticky 条）：dock 上沿内嵌的
// 紧凑读数钮——主数据直出（会话累计总 token，tabular-nums，无说明句）；
// 点按展开逐轮明细浮层（墨选/词卡浮层家族：Esc 关、点外关、⑩ 互斥收）。
// 无读数（端点没报 usage）不现位——空说明句随之退役；未计量字段在明细
// 浮层里如实「—」。开关关 / 无读数 / 写作态 / 离案头都不现位（W-1 的
// 50dvh 写作态与粒不同层：粒藏于写作态，无遮挡关系）。
let tokenMeterPopOpen = false;
let tokenMeterPop = null;

function tokenMeterTotal() {
  const data = tokenMeterData;
  if (!data) return null;
  const metered = data.prompt_tokens !== null ||
    data.completion_tokens !== null || data.total_tokens !== null;
  return metered ? data.total_tokens : null;
}

function renderTokenMeter() {
  const pill = document.getElementById("tokenmeter");
  if (!pill) return;
  closeTokenMeterPop();
  const total = tokenMeterTotal();
  const show = Boolean(tokenMeterOn && tokenMeterData && total !== null &&
    !spaces.parlor.hidden && !composeOpen());
  pill.hidden = !show;
  pill.textContent = "";
  if (!show) return;
  pill.textContent = Number(total).toLocaleString("en-US");
  pill.title = "token 计量——点按看逐轮";
  pill.setAttribute("aria-expanded", "false");
}

// 逐轮明细浮层（复用浮层家族形态）：只列有计量的轮——未报 usage 的轮
// 如实跳过并交代一句（数据优先：短词「N 轮未报」，不再整句）；一轮都
// 没有时如实说。Esc / 点外 / 换空间 / 开其它浮层都收（⑩ 互斥）。
function tokenMeterPopRows() {
  const box = document.createElement("div");
  box.className = "tm-pop-rows";
  const data = tokenMeterData;
  const head = document.createElement("p");
  head.className = "tm-pop-head";
  head.appendChild(document.createTextNode("提示 "));
  head.appendChild(tokenNum(data.prompt_tokens));
  head.appendChild(document.createTextNode(" · 补全 "));
  head.appendChild(tokenNum(data.completion_tokens));
  head.appendChild(document.createTextNode(" · 共 "));
  head.appendChild(tokenNum(data.total_tokens));
  head.appendChild(document.createTextNode(
    " · 计量 " + data.measured_calls + "/" + data.total_calls));
  box.appendChild(head);
  let listed = 0;
  flowTurns.forEach((turn, i) => {
    if (!turn.usage) return;
    listed += 1;
    const row = document.createElement("p");
    row.className = "tm-pop-turn";
    row.appendChild(document.createTextNode("第 " + (i + 1) + " 轮 "));
    row.appendChild(tokenNum(turn.usage.prompt_tokens));
    row.appendChild(document.createTextNode("/"));
    row.appendChild(tokenNum(turn.usage.completion_tokens));
    row.appendChild(document.createTextNode("/"));
    row.appendChild(tokenNum(turn.usage.total_tokens));
    box.appendChild(row);
  });
  if (!listed) {
    const row = document.createElement("p");
    row.className = "tm-pop-turn";
    row.textContent = "还没有逐轮读数。";
    box.appendChild(row);
  } else if (listed < flowTurns.length) {
    const row = document.createElement("p");
    row.className = "tm-pop-turn tm-pop-turn--faint";
    row.textContent = (flowTurns.length - listed) + " 轮未报";
    box.appendChild(row);
  }
  return box;
}

function closeTokenMeterPop() {
  if (tokenMeterPop) {
    tokenMeterPop.remove();
    tokenMeterPop = null;
  }
  document.removeEventListener("click", tokenMeterOutside, true);
  document.removeEventListener("keydown", tokenMeterEsc, true);
  tokenMeterPopOpen = false;
  const pill = document.getElementById("tokenmeter");
  if (pill) pill.setAttribute("aria-expanded", "false");
}

function tokenMeterOutside(event) {
  if (tokenMeterPop && !tokenMeterPop.contains(event.target)) {
    closeTokenMeterPop();
  }
}

function tokenMeterEsc(event) {
  if (event.key === "Escape") {
    event.stopPropagation();
    closeTokenMeterPop();
  }
}

function toggleTokenMeterPop() {
  if (tokenMeterPopOpen) {
    closeTokenMeterPop();
    return;
  }
  // ⑩ 互斥收：开本浮层先收一切在场的浮层/沓/下拉（墨选/词卡/沓同法）。
  closeOpenSelects();
  closeWordCard({ skipOut: true });
  closeEnvelopeSelector();
  const pill = document.getElementById("tokenmeter");
  if (!pill || pill.hidden) return;
  const pop = document.createElement("div");
  pop.className = "tm-pop";
  pop.appendChild(tokenMeterPopRows());
  document.body.appendChild(pop);
  tokenMeterPop = pop;
  tokenMeterPopOpen = true;
  pill.setAttribute("aria-expanded", "true");
  document.addEventListener("click", tokenMeterOutside, true);
  document.addEventListener("keydown", tokenMeterEsc, true);
}

function syncFlowMeter(usage) {
  tokenMeterData = usage || null;
  renderTokenMeter();
}

// 寄出一轮后的计量刷新：累计是服务端会话全量账——读一次最窄窗口把最新
// 累计读回来（客户端不做本地加减；读回来的就是存下的）。
async function refreshFlowMeter() {
  try {
    const data = await fetchHistory({ limit: 1 });
    syncFlowMeter(data.usage);
  } catch { /* 拉不到就停在旧读数——下一次进入/刷新再补 */ }
}

async function loadEarlierLetters() {
  const before = flowTurns.length;
  parlorWindow = (lastHistoryWindow || before || 50) + 50;
  await renderFlowHistory();
  // 视口锚守恒：先前读着的首轮现在往后移了（新来的是更早的信，插在前
  // 面）——跳回那一轮，不让读者跟丢。
  const shift = flowTurns.length - before;
  if (shift > 0 && flowTurns[shift]) scrollToFlowTurn(shift, true);
}

async function renderFlowHistory() {
  const data = await fetchHistory(parlorWindow ? { limit: parlorWindow }
                                               : undefined);
  lastHistoryWindow = data.window;
  messages.textContent = "";
  flowTurns = [];
  // 口径行在信流顶部（不是一轮——轮锚不收它）。
  renderFlowCalibre(data);
  for (const turn of data.turns) {
    // v3-3：位图随信渲染——历史轮两侧各带命中位图（缺字段 = 全供性）。
    let anchor = null;
    if (turn.user !== null) {
      anchor = addLine("user", turn.user, { hits: turn.user_word_hits || null });
    }
    if (turn.assistant !== null) {
      const reply = addLine("assistant", turn.assistant, { hits: turn.word_hits || null });
      if (!anchor) anchor = reply;
    }
    if (anchor) flowTurns.push({ node: anchor, usage: turn.usage || null });
  }
  buildFlowRuler();
  syncFlowMeter(data.usage);
}

async function loadHistory() {
  await renderFlowHistory();
  // 空厅句：一封信都还没有时，客户端静态系统行开场（⑧ 8.2.2）
  showEmptyHall();
  // the open teaching moment survives a refresh: rebuild its card (with
  // the attempt box and the skip button) so an open teaching is never
  // stranded without its controls
  const curData = await fetchCurrentMoment();
  if (curData.moment !== null) {
    showMoments([curData.moment]);
  }
  syncFlowBottom();
}

window.addEventListener("DOMContentLoaded", () => {
  // v2 品牌名单点驱动（简报 §1）：标题、门厅英文并写与封面副题取自
  // BRAND——index.html 的同值字面只是无 JS 静态兜底。mc-1 起案头
  // 主从条不再念品牌：.who = 当前角色名（端点驱动，见 renderMasthead；
  // 品牌名与副题退居门厅封面）。
  document.title = BRAND.name;
  const coverTagline = document.querySelector(".ob-tagline");
  if (coverTagline) coverTagline.textContent = BRAND.tagline;
  const wordmark = document.querySelector(".ob-wordmark");
  if (wordmark) wordmark.textContent = BRAND.en.toUpperCase();
  // F-G2: the brand marks (the template's clones) land before the first
  // screen shows, so the cover and every space header is never bare.
  installBrandMarks();
  // R-1V：#22 图标插槽与桌面边注栏的案头日期（客户端当日，mono——
  // 机械事实，非文案；边注栏窄屏缺席，日期槽随之不显）
  installIcons();
  const dateSlot = document.getElementById("marginalia-date");
  if (dateSlot) {
    const today = new Date();
    dateSlot.textContent = today.getFullYear() + " · " +
      String(today.getMonth() + 1).padStart(2, "0") + " · " +
      String(today.getDate()).padStart(2, "0");
  }
  // R-1W：门厅封面的案头日期（⑧ 8.2.1 修订版）——与边注栏同一真实
  // 数据源、同一格式，textContent 落（机械事实，非文案；零伪数据）
  const coverDate = document.querySelector(".ob-date");
  if (coverDate) {
    const coverToday = new Date();
    coverDate.textContent = coverToday.getFullYear() + " · " +
      String(coverToday.getMonth() + 1).padStart(2, "0") + " · " +
      String(coverToday.getDate()).padStart(2, "0");
  }
  // rd-1：入场编排接线（⑨-5 逐行落墨——IO 只加类；reduced-motion 的
  // JS 半区由 wireReveal 自行监听）
  wireReveal(document);
  // mc-1：主从条首灌（当前角色名 + 身份行）——失败留空不轰炸，下次
  // 打开信封沓会重读
  fetchCharacters().then(renderMasthead).catch(() => {});
  loadHistory();
  // F-1R/R-1: the first visit sees the cover; every later visit lands in
  // the parlor directly (the cover never comes back once localStorage
  // says so)
  showSpace(seenOnboard() ? "parlor" : "onboard");
});

// ── mc-1: 信封沓——点案头主从条弹出的那一沓信封（v3-2 容器化）────────
// 沓形 = 案头的一叠信（components.js 的 envelopeCard/layoutEnvelopeStack
// 承担 DOM 与排布半区；屏级形态在 screens.css 的 .envsel 节）：微扇形
// 错位叠放，rotate/translateX 从 stamp_key 确定性派生（同一角色恒同
// 姿态——零随机）；当前通信的一封盖「当前」邮戳角标（--seal，真实
// 状态事件）；沓尾是新建空白信封（「完整编辑」进容器内的编辑面——
// v3-2R 定谳：建卡表单不占「起笔」语义）。预览 = 点沓中一封 → 滑到
// 沓首微抬（260ms 减速长尾 + 让位 stagger）；「起笔」= 容器延展成
// 写信工作区；再点它或点「对话」→ 切换。
// v3-2 容器与层级重铸（⑩ 层级宪法；用户两项核心误读纠正）：沓面板是
// 一个**下拉容器**，起笔/编辑/翻看都是**容器本体的形态变化**，不是
// 新页面也不是容器内多一个滚动条——
//   · 扇叠（deck）＝容器的收拢态（默认）；
//   · 翻看（window）＝**整个容器升级为全览窗口**（同族容器延展过渡，
//     components.js 的 extendContainer：高度走 --dur-settle 大件档），
//     翻页发生在窗口内（wirePageTurn 横滑 + chevron，page-turn 2D）；
//     v2-2 的「翻看/回沓按钮 + envsel-browser 子页面层」模式退役；
//   · 编辑（editor）＝**编辑台在展开的容器内**（零新增页面级滚动条
//     ——v2-2 的独立全页编辑台与其放大过渡退役，mc-2 九面
//     表单原样搬进容器的编辑面）；
//   · 起笔（compose，v3-2R 重铸）＝**容器向下延展成为写信工作界面**——
//     选定角色点「起笔」，容器从当前高度一次拉开成写信工作区（收件人 +
//     多行稿纸 + 寄出 + 回执），寄出后收拢让位案头信流。
// v3-2R 定谳（用户判词整刀否定上一刀的降级实现，2026-10-02）：
//   · 翻看零跳变——窗口升级 = 内容先装满（隐藏层里异步灌完）→ 再量高 →
//     一次拉开；上一刀量高发生在页卡内容填入前，用户看到「长到一半→
//     跳到全高」。主入口 = 点沓本体（信封/动作/底行以外的容器纸面）；
//     「翻开全沓 ↓」文字链只作触屏辅入口（hover:none 档才现位）。
//     （滚到底自动升级臂曾列主入口——用户第三轮否决退役，全部入口
//     显式化。）
//   · 起笔 = 写信，不是建卡——新建角色的表单归「完整编辑」（编辑台既
//     有），不得占用「起笔」语义；空白封只剩「完整编辑」一个入口。
//   · 三条硬伤收编：沓开时底坞淡化置灰且不可点（disabled 形态复用，
//     视觉可点性 = 实际可点性）；触屏档沓改单卡纵排（消灭邮票压简介
//     与叠压遮头）；起笔延展落定后笔尖聚焦（视口跟随）。
// 层级互斥（⑩）：开容器先收浮层；进任何空间收一切浮层与容器；
// Esc 逐层退栈：编辑面/全览窗口/写信工作区 → 扇叠 → 收沓；浮层
// 在场时 Esc 归浮层（wordCardOpen 裁决）。零常驻循环；
// reduced-motion 双面降级（库尾总降级块 0.01ms 即终，fold/grow 的
// finish 有 480ms 保险丝 + REDUCED_MOTION 直切）。
let envselPanel = null;
let envselPreviewId = null;
let charactersCache = null;
let envselBornId = null;   // 刚建好的那封——重排时给它一次落沓纸事件
let envselFace = "deck";   // 容器态：deck 扇叠 / window 全览 / editor 编辑
                           // / compose 写信工作区（v3-2R 第四形态）
let envselPageAt = 0;      // 当前页（全览窗口页序）
let envselFacePending = null;   // 窗口升级的内容先装满——过渡中的二次点名忽略

// 邮票变体的确定性派生（mc-0 stamp_key 的前端消费半区）：key 是角色
// id 的 SHA-256 前 16 位十六进制（elc.persona.card_store.stamp_key_for，
// 同 id 恒同 key、改名不动）——取其中各位的离散梯拼变体类：边框图形
// 8 种 × 墨色 4 档 × 票面 3 色，全部 v2 既有色族（components.css 的
// .env-stamp 段）。同 key 恒同类（跨进程跨重启），异 key 尽散；零
// 随机零素材，纯 class 派发。
function stampVariantClasses(stampKey) {
  const key = String(stampKey || "");
  const at = (index) => parseInt(key.charAt(index), 16) || 0;
  return [
    "stamp-v" + (at(0) % 8),
    "stamp-c" + (at(1) % 4),
    "stamp-p" + (at(2) % 3),
  ];
}

// 微扇姿态的确定性派生（同一 stamp_key 家族，取另外几位）：rotate
// ±1/±2/±3°、translateX ±6/±12/±18px——像案头随手叠放的一沓，同一
// 角色每次打开姿态一致。
function envelopeTilt(stampKey) {
  const key = String(stampKey || "");
  const size = (parseInt(key.charAt(3), 16) || 0) % 3;
  const flip = (parseInt(key.charAt(5), 16) || 0) % 2 ? -1 : 1;
  return flip * (1 + size) + "deg";
}

function envelopeDrift(stampKey) {
  const key = String(stampKey || "");
  const size = (parseInt(key.charAt(4), 16) || 0) % 3;
  const flip = (parseInt(key.charAt(6), 16) || 0) % 2 ? -1 : 1;
  return flip * (6 + size * 6) + "px";
}

// 案头主从条（mc-1 的真源；v2-2 瘦身，8.2.2①）：.who = 当前角色名
// 一行——全部来自 /api/characters 的 current_character_id（webui
// 零角色名字面）；读不到（无名册 / current 为 null）就留空，不发明
// 人名。身份行副槽长句族已退役（身份介绍退入笔友档案全页）；
// 品牌名与副题退居门厅封面（BRAND 常量的封面消费面）。
function renderMasthead(roster) {
  const who = document.querySelector("#space-parlor .who");
  if (!who) return;
  const items = (roster && roster.characters) || [];
  const current = items.find(
    (item) => item.character_id === (roster && roster.current_character_id));
  who.textContent = current ? current.name : "";
}

function envselCloser(event) {
  if (!(event.target instanceof Element)) return;
  if (envselPanel && !envselPanel.contains(event.target)) {
    closeEnvelopeSelector();
  }
}

// Esc 逐层退栈（⑩ 层级宪法的统一关闭语义）：浮层在场 → 归浮层（它
// 自己的监听收它，这里让路）；编辑面/全览窗口/写信工作区 → 退一层回
// 扇叠；扇叠 → 收沓。编辑面不再有独立监听（v2-2 的面板级 editorEsc +
// stopPropagation 随容器化退役——一个阶梯管到底）。
function envselEsc(event) {
  if (event.key !== "Escape") return;
  if (wordCardOpen()) return;   // 浮层先退（它的监听收它自己）
  if (envselFace !== "deck") {
    setEnvelopeFace("deck");
    return;
  }
  closeEnvelopeSelector();
}

// 沓开时底坞静置（v3-2R 硬伤 A 定谳）：淡化置灰且**明确不可点**——复用
// 既有 disabled 形态（components.css 的 .navdock-item[disabled]：
// opacity .4 + pointer-events 无），视觉可点性 = 实际可点性；收沓即解。
// 二选一取「置灰」不取「第一击直切空间并收沓」：沓是带遮罩的模态层
// （点外关闭，⑩ 10.3-4），一个手势只该产一个效果——「收沓」与「切空
// 间」压在同一击上是双击歧义；置灰后第一击的语义唯一（点容器外 = 收
// 沓），底坞的灰态也把「先了结眼前这沓」写在脸上。
function setNavdockStilled(still) {
  for (const item of document.querySelectorAll(".navdock-item")) {
    item.disabled = still;
  }
}

// 案头写信区随沓让路（v3-2R 处置刀，复测坏1/差4）：容器（含写信工作
// 区/编辑面/全览）开着时 dock 整体淡化置灰且不可点——否则它的「寄出」
// 浮在容器之上（z8>z7），误触 = 容器关闭 + 草稿无声丢弃；新建表单的
// 「存」也被它咬住。视觉可点性 = 实际可点性（⑩ 10.3-5 同一定谳），
// 收沓即解。
function setDockStilled(still) {
  const dock = document.querySelector(".dock");
  if (dock) dock.classList.toggle("dock--stilled", still);
}

// 起笔草稿层（v3-2R 处置刀，复测坏2/坏3）：写信的退出路径只有寄出才
// 清稿——Esc/回沓/先搁着/点外一律保稿（「写了一半的东西不能丢」）；
// 按角色分桶（与 D-B 方案的草稿分桶设计同向），寄出成功即清。
function composeDraftKey(characterId) {
  return `compose-draft-${characterId}`;
}

// 收沓（v2-2 重排沿用）：默认走 fold 退场（纸先落墨后渗的出场半——收拢
// 200ms × --ease-exit + ink-wash reverse 恒慢），**墨腿 animationend 后
// 摘 DOM**（最慢腿对账——见下）；移动端遮罩随批摘；reduced-motion 直切
// （REDUCED_MOTION 单一归宿 + 库尾总降级块双面）。opts.skipFold = 无动画
// 直摘（现在仅极端路径备用）。
function closeEnvelopeSelector(opts) {
  const panel = envselPanel;
  document.removeEventListener("click", envselCloser);
  document.removeEventListener("keydown", envselEsc);
  envselPanel = null;
  envselPreviewId = null;
  envselFace = "deck";
  envselPageAt = 0;
  envselFacePending = null;
  setNavdockStilled(false);   // 底坞解除静置（与开沓的置灰对称）
  setDockStilled(false);      // 案头写信区同步解除让路
  const scrim = document.querySelector(".envsel-scrim");
  if (scrim) scrim.remove();
  if (!panel) return;
  const finish = () => {
    if (panel.parentNode) panel.remove();
  };
  if (REDUCED_MOTION.matches || (opts && opts.skipFold)) {
    finish();
    return;
  }
  // 先撤入场类并强制结算，再落 fold（用户五轮否决的真根因）：CSS 动画
  // 按名续用——入场与退场墨腿同名 ink-wash，envsel--open 若不撤，已
  // 完成的入场墨腿不重启、方向翻成 reverse 后 both 填充瞬间算出
  // opacity 0，面板一帧内消失、位移全程播在隐形元素上（写作面
  // dock-compose--in 入场即摘所以没这病——正例同构）。offsetWidth 一拍
  // 让「空动画表」先结算，fold 双腿才全新起播（playPageTurn 同惯用形）。
  panel.classList.remove("envsel--open");
  void panel.offsetWidth;
  panel.classList.add("envsel--fold");
  panel.addEventListener("animationend", (event) => {
    // 最慢腿对账（用户三轮否决「不丝滑」的根因修）：fold 双腿并行——
    // 纸腿 paper-retract 200ms 先终，墨腿 ink-wash reverse ×1.3（260ms）
    // 恒慢后终。旧账对在纸腿上，200ms 即摘 DOM＝墨还剩约三成就被硬切。
    // 对账改墨腿 animationend（leaveLayer 同一惯用形）；target 钉面板
    // 本体——沓内信封 env--born 的同名动画冒泡不抢账。
    if (event.animationName === "ink-wash" && event.target === panel) finish();
  });
  setTimeout(finish, 480);   // 保险丝（animationend 正常先到）
}

// 对话让位案头（8.2.2a；⑨-5 注册行）：沓收拢与信流首屏同帧编排——
// 沓侧 fold 类（收拢退场），信流侧的「信纸摊上案头」半由
// refreshCorrespondence 的 resettle 承担（切角色路径必经，同帧在播）；
// isCurrent 直回路径信流本就完好，无需重铺。transform 与 opacity 拆
// 开（fold 的 ink-wash reverse 恒慢）。reduced-motion 直落终态
// （REDUCED_MOTION 直切 + 库尾总降级块双面）。
// v3-2R 定形：本函数服务「对话」两条路（沓中「对话」/ 二次点选同一
// 封——去看信、去读案头）；「起笔」不走这里——起笔 = 容器延展成写
// 信工作区（startComposing），寄出后的收拢让位由 compose 面自己的
// 回执节拍承担（closeEnvelopeSelector 同一 fold）。
function unfoldToParlor(after) {
  closeEnvelopeSelector();
  if (typeof after === "function") after();
}

async function openEnvelopeSelector() {
  if (envselPanel) return;
  closeTokenMeterPop();   // ⑩ 互斥：开沓先收计量明细浮层（veto-R 同法）
  closeWordCard({ skipOut: true });   // ⑩ 互斥：开下拉容器自动关浮层（fr-B 直摘）
  closeComposeFace();   // ⑩ 互斥（v3-a）：开沓先收写作态（保稿）——
                        // 两具固定底件不同屏（10.3-5 置灰优先的同一定谳）
  setNavdockStilled(true);   // 硬伤 A：底坞淡化置灰且不可点（收沓即解）
  setDockStilled(true);      // 案头写信区同步让路（复测坏1：防误触其寄出）
  const panel = document.createElement("div");
  panel.className = "envsel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "信封沓");
  panel.tabIndex = -1;
  const stack = document.createElement("div");
  stack.className = "envsel-stack";
  panel.appendChild(stack);
  const browser = document.createElement("div");
  browser.className = "envsel-browser";
  browser.hidden = true;
  panel.appendChild(browser);
  const editorFace = document.createElement("div");
  editorFace.className = "envsel-editor";
  editorFace.hidden = true;
  panel.appendChild(editorFace);
  const composeFace = document.createElement("div");
  composeFace.className = "envsel-compose";
  composeFace.hidden = true;
  panel.appendChild(composeFace);
  const foot = document.createElement("p");
  foot.className = "envsel-foot";
  // 全览窗口的触屏辅入口（主入口 = 点沓本体——滚底自动升级已随用户
  // 第三轮否决退役；本链在 hover:none 档才现位，桌面档 CSS 不显示）：
  // 容器升级态的静默链「翻开全沓 ↓」（触屏无 Esc 的回程链「回扇叠 ↑」
  // 在窗口态现位）；升级是容器本体的延展过渡，不是子页面替换。
  const browse = document.createElement("button");
  browse.type = "button";
  browse.className = "btn btn--pencil env-browse";
  browse.textContent = "翻开全沓 ↓";
  browse.addEventListener("click", (event) => {
    event.stopPropagation();
    setEnvelopeFace(envselFace === "window" ? "deck" : "window");
  });
  foot.appendChild(browse);
  const fold = document.createElement("button");
  fold.type = "button";
  fold.className = "btn btn--faint envsel-fold";
  fold.textContent = "收起";
  fold.addEventListener("click", (event) => {
    event.stopPropagation();
    closeEnvelopeSelector();
  });
  foot.appendChild(fold);
  panel.appendChild(foot);
  // 移动端沓（P1-5）的遮罩件：桌面档 CSS 不显示，触屏档（hover:none）
  // 才 display——点遮罩 = 点容器外（envselCloser 同一机制关闭）。
  const scrim = document.createElement("div");
  scrim.className = "envsel-scrim";
  document.getElementById("space-parlor").appendChild(scrim);
  document.getElementById("space-parlor").appendChild(panel);
  envselPanel = panel;
  envselFace = "deck";
  panel.classList.add("envsel--open");   // 入场一次（复用注册双动画）
  panel.focus();
  document.addEventListener("click", envselCloser);
  document.addEventListener("keydown", envselEsc);
  // 点沓本体 = 翻开全览（v3-2R 主入口）：落在容器纸面（面板留白/沓叠
  // 背景）上的点击升级成窗口；信封、动作行、底行上的点击各有己任
  // （预览/动作/收沓），不在这条路上。
  panel.addEventListener("click", (event) => {
    if (envselFace !== "deck") return;
    if (event.target !== panel && event.target !== stack) return;
    setEnvelopeFace("window");
  });
  // 滚底自动升级退役（用户第三轮否决：滚到底自动跳转展开全沓非常
  // 不合理——v3-2R 曾以「触屏主入口」名义落此臂，现删；翻开全沓的
  // 入口 = 点沓本体纸面（上方 click 臂）与「翻开全沓 ↓」文字链，全部
  // 显式，无一自动跳转）。
  await renderEnvelopeStack(stack);
  buildEnvelopeBrowser(browser);
}

// ── mc-1 全览窗口（v3-2 容器升级重铸，8.2.2a）：**整个沓面板升级成
// 的全览窗口**（同族容器延展过渡——setEnvelopeFace("window")）——每页
// 一张角色卡全貌，横滑（ux-1 守卫同法，wirePageTurn）+ 点击（#22
// chevron）翻页，page-turn 2D 形态；翻页态不替换档案页（页卡上的
// 「档案」动作仍进全页）。诚实降级（读面缺口呈报在案）：/api/partner
// 的卡面只回五键，全貌页展示可读回的 name / identity / background /
// values / letter_habits 五面；personality / boundaries / opening /
// scenario 四面读不回（mc-0 无全字段读面）——如实注记，开场信预览位
// 缺席（不虚构「第一封信」）。
let envselBrowserBox = null;

function buildEnvelopeBrowser(box) {
  envselBrowserBox = box;
  box.textContent = "";
  const prev = document.createElement("p");
  prev.className = "envpage-nav envpage-nav--prev";
  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "btn";
  prevBtn.setAttribute("aria-label", "上一封");
  prevBtn.appendChild(inkIcon("chevron"));
  prevBtn.addEventListener("click", () => turnEnvelopePage(-1));
  prev.appendChild(prevBtn);
  const page = document.createElement("div");
  page.className = "envpage";
  const next = document.createElement("p");
  next.className = "envpage-nav envpage-nav--next";
  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "btn";
  nextBtn.setAttribute("aria-label", "下一封");
  nextBtn.appendChild(inkIcon("chevron"));
  nextBtn.addEventListener("click", () => turnEnvelopePage(1));
  next.appendChild(nextBtn);
  const count = document.createElement("span");
  count.className = "envpage-count";
  count.id = "envpage-count";
  box.appendChild(prev);
  box.appendChild(page);
  box.appendChild(next);
  box.appendChild(count);
  // 横滑翻页（ux-1 守卫同法：横大于纵严格判定、单指重臂双指全拦、
  // 边界静止、零 preventDefault）；page-turn 与点击同一动效语汇。
  wirePageTurn(page, () => envselPageAt > 0,
    (step) => turnEnvelopePage(step));
  renderEnvelopePageInto(page);
}

function envelopeBrowserRoster() {
  return (charactersCache && charactersCache.characters) || [];
}

async function turnEnvelopePage(step) {
  const roster = envelopeBrowserRoster();
  const next = envselPageAt + step;
  if (next < 0 || next >= roster.length) return;   // 边界静止
  envselPageAt = next;
  const page = envselBrowserBox && envselBrowserBox.querySelector(".envpage");
  if (!page) return;
  await renderEnvelopePageInto(page);   // 先装满再翻——翻页不拖着 loading 走
  playPageTurn(page, step > 0);
}

// 一页角色卡全貌：卡面（惰性拉取 + 缓存）+ 可读回五面的摘要 +
// 读不回四面的诚实注记 + 动作行（起笔 · 对话 · 档案——下划线文字链接）。
// v3-2R 零跳变（用户判词「长到一半→跳到全高」的根因修复）：本函数
// 返回灌完的 Promise——窗口升级（setEnvelopeFace 的 window 臂）先
// await 它装满、再量高、再一次拉开；旧的面守卫（envselFace !==
// "window" 早退）随之退役——装满可以发生在隐藏层里（那正是零跳变的
// 前提），代次守卫（page.dataset.fill）保证只有最新一次渲染落笔。
const envelopeCardCache = new Map();
let envelopeFillSeq = 0;

async function envelopePageCard(characterId) {
  if (!envelopeCardCache.has(characterId)) {
    envelopeCardCache.set(characterId,
      fetchPartnerOf(characterId).catch(() => null));
  }
  try {
    return await envelopeCardCache.get(characterId);
  } catch {
    return null;
  }
}

function renderEnvelopePageInto(page) {
  const roster = envelopeBrowserRoster();
  const item = roster[envselPageAt];
  if (!item) {
    page.textContent = "";
    page.appendChild(stateBanner("empty",
      { text: "沓里还没有信——「完整编辑」建第一位笔友。" }));
    return Promise.resolve();
  }
  const count = document.getElementById("envpage-count");
  if (count) count.textContent = (envselPageAt + 1) + " / " + roster.length;
  page.textContent = "";
  envelopeFillSeq += 1;
  const fill = String(envelopeFillSeq);
  page.dataset.fill = fill;
  const face = document.createElement("div");
  face.className = "envpage-face";
  const name = document.createElement("p");
  name.className = "envpage-name";
  name.textContent = String(item.name || "");
  face.appendChild(name);
  const line = document.createElement("p");
  line.className = "envpage-line";
  line.textContent = String(item.identity_line || "");
  face.appendChild(line);
  page.appendChild(face);
  const body = document.createElement("div");
  page.appendChild(body);
  body.appendChild(stateBanner("loading"));
  const actions = document.createElement("p");
  actions.className = "envpage-actions";
  const act = (word, handler) => {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "btn btn--pencil";
    link.textContent = word;
    link.addEventListener("click", handler);
    actions.appendChild(link);
  };
  const isCurrent = charactersCache &&
    item.character_id === charactersCache.current_character_id;
  act("起笔", () => {
    startComposing(item);   // v3-2R：窗口里也能直接落笔（容器延展成工作区）
  });
  act("对话", () => {
    if (isCurrent) {
      unfoldToParlor();   // 已在通信中——沓收拢、信纸摊开
      return;
    }
    switchToCharacter(item.character_id).then((done) => {
      if (done) unfoldToParlor();
    });
  });
  act("档案", () => {
    closeEnvelopeSelector();
    openPartnerDossier(item.character_id);
  });
  page.appendChild(actions);
  // 页卡上不骗读数：卡面读不到就如实一行（全貌页的其余面照常）。
  // 返回灌完的 Promise——调用方（窗口升级臂/翻页臂）await 它再动容器。
  return envelopePageCard(item.character_id).then((data) => {
    if (page.dataset.fill !== fill) return;   // 已被更新的渲染取代——不往旧面上写
    body.textContent = "";
    const card = data && data.card;
    const faces = card ? [
      ["背景", String(card.background || "")],
      ["看重的事", String(card.values || "")],
      ["写信的样子", String(card.letter_habits || "")],
    ] : [];
    for (const [label, text] of faces) {
      if (!text) continue;
      const head = document.createElement("p");
      head.className = "envpage-label";
      head.textContent = label;
      body.appendChild(head);
      const prose = document.createElement("p");
      prose.className = "envpage-prose";
      prose.textContent = text;
      body.appendChild(prose);
    }
    const veil = document.createElement("p");
    veil.className = "envpage-veil";
    veil.textContent = "性情、边界、开场信与场景四面读不回——她收在"
      + "自己的信封里；「档案」与「编辑」里见得到的照旧。";
    body.appendChild(veil);
  });
}

// 容器态机（v3-2 重铸 / v3-2R 第四形态）：deck 扇叠 / window 全览 /
// editor 编辑 / compose 写信工作区——同一个沓面板的四个形态。切换 =
// 容器本体的延展过渡（extendContainer：内容换装前后量高，height 走
// --dur-settle 大件档 × --ease-paper），面内容只是 hidden 翻转（DOM
// 同一批子节点——**没有子页面**）。
// 翻看零跳变（v3-2R，上一刀 F-1 缺口的根因修复）：进窗口 = **内容先装
// 满 → 再量高 → 一次拉开**——先在隐藏层里把页卡灌完（await
// renderEnvelopePageInto，含异步卡面），再 extendContainer 量「换装
// 后」的实高；上一刀先量高（量到 loading 横幅的矮高）再异步填内容，
// 用户看到「长到一半→跳到全高」的 snap 伪影。装满期间过渡中的二次点
// 名（连点/连滚）由 envselFacePending 忽略；装期间沓被收则整臂弃权。
// 回扇叠：scrollTop 归零（回沓首——滚底自动升级已退役，归零只是回到
// 沓首的阅读位，不再「重武装」任何触发）。编辑/写信两态静默链让位
// （两面各有自己的回沓行）；「收起」是容器级的——四态常在，从任何
// 形态一记收沓。
async function setEnvelopeFace(face) {
  if (!envselPanel) return;
  if (face !== "deck" && face !== "window" && face !== "editor" &&
      face !== "compose") return;
  if (envselFace === face) return;
  if (envselFacePending) return;   // 一次只拉一次——过渡中的二次点名忽略
  const panel = envselPanel;
  const stack = panel.querySelector(".envsel-stack");
  const browser = panel.querySelector(".envsel-browser");
  const editorFace = panel.querySelector(".envsel-editor");
  const composeFace = panel.querySelector(".envsel-compose");
  const browse = panel.querySelector(".env-browse");
  if (face === "window") {
    // 内容先装满（隐藏层里异步灌完，含卡面拉取）——量高在装满之后，
    // 过渡只有一次（零跳变的次序钉：装满 → 量高 → 过渡）。
    envselFacePending = face;
    envselPageAt = 0;
    const page = browser.querySelector(".envpage");
    if (page) await renderEnvelopePageInto(page);
    envselFacePending = null;
    if (!envselPanel || envselPanel !== panel) return;   // 装期间沓被收
  }
  envselFace = face;
  extendContainer(panel, () => {
    stack.hidden = face !== "deck";
    browser.hidden = face !== "window";
    editorFace.hidden = face !== "editor";
    composeFace.hidden = face !== "compose";
    if (browse) {
      browse.hidden = face === "editor" || face === "compose";
      browse.textContent = face === "window" ? "回扇叠 ↑" : "翻开全沓 ↓";
    }
    panel.classList.toggle("envsel--editor", face === "editor");
    panel.classList.toggle("envsel--compose", face === "compose");
  });
  if (face === "deck") {
    stack.scrollTop = 0;
  }
  if (face === "compose") {
    followComposeWorkspace(panel, composeFace);   // 硬伤 C：延展落定视口跟随
  }
}

async function renderEnvelopeStack(stack) {
  envselPreviewId = null;
  stack.textContent = "";
  stack.appendChild(stateBanner("loading"));
  let roster = null;
  try {
    roster = await fetchCharacters();
  } catch {
    roster = null;
  }
  stack.textContent = "";
  if (!roster) {
    stack.appendChild(stateBanner("error", {
      text: "信封沓没取到。",
      retry: () => {
        closeEnvelopeSelector();
        openEnvelopeSelector();
      },
    }));
    return;
  }
  charactersCache = roster;
  renderMasthead(roster);
  let order = 0;
  for (const item of roster.characters || []) {
    const isCurrent = item.character_id === roster.current_character_id;
    const env = envelopeCard(item, {
      current: isCurrent,
      stampClasses: stampVariantClasses(item.stamp_key).join(" "),
      rot: envelopeTilt(item.stamp_key),
      dx: envelopeDrift(item.stamp_key),
      onTalk: () => {
        if (isCurrent) {
          unfoldToParlor();   // 已在通信中——沓收拢、信纸摊开（8.2.2a）
          return;
        }
        switchToCharacter(item.character_id).then((done) => {
          if (done) unfoldToParlor();
        });
      },
      onDossier: () => {
        closeEnvelopeSelector();
        openPartnerDossier(item.character_id);
      },
      onEdit: () =>
        openCharacterEditor({ item: item, mode: "edit" }),
      onCompose: () =>
        startComposing(item),   // v3-2R：起笔 = 容器延展成写信工作区
    });
    if (item.character_id === envselBornId) env.classList.add("env--born");
    env.dataset.order = String(order);
    env.addEventListener("click", (event) => {
      if (event.target instanceof Element &&
          event.target.closest(".env-actions")) {
        return;   // 动作行自理
      }
      previewEnvelope(item.character_id);
    });
    env.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.target === env) {
        event.preventDefault();
        previewEnvelope(item.character_id);
      }
    });
    stack.appendChild(env);
    order += 1;
  }
  stack.appendChild(newEnvelopeCard());
  layoutEnvelopeStack(stack);
  envselBornId = null;   // 纸事件只播一次——下轮重排不再落
}

async function refreshEnvelopeStack() {
  const stack = envselPanel && envselPanel.querySelector(".envsel-stack");
  if (!stack) return;
  await renderEnvelopeStack(stack);
}

// 预览（精准动画的第一半）：点沓中一封 → 该封滑到沓首微抬，其余
// 让位重排（layoutEnvelopeStack 的排名重算驱动 CSS transition——
// 260ms 减速长尾，stagger 步长 20ms 封顶 60ms，总封顶 320ms）；
// 再次点选同一封 = 就是他——切换。
function previewEnvelope(characterId) {
  if (!envselPanel) return;
  if (envselPreviewId === characterId) {
    // 再点同一封 = 就是他——切换 + 让位案头（8.2.2a：选中角色后沓收
    // 拢、信纸向下铺开成对话主界面；要写信用「起笔」——容器延展成
    // 写信工作区，不在此路）
    switchToCharacter(characterId).then((done) => {
      if (done) unfoldToParlor();
    });
    return;
  }
  envselPreviewId = characterId;
  const stack = envselPanel.querySelector(".envsel-stack");
  if (!stack) return;
  const picked = stack.querySelector(
    '.env[data-id="' + CSS.escape(characterId) + '"]');
  if (!picked) return;
  // 沓首 = 全沓严格最小 order − 1：初值必须取「非 0 的中性元」——
  // order=0 是合法值（首排沓首恒 0），falsy 判别（!lowest）会把
  // 最小值在循环里被后续非零覆盖（评审活体实锤：点第 2 封不滑到
  // 沓首、让位与 stagger 整体不发生），Infinity 起步 + 纯 < 比较。
  let lowest = Infinity;
  for (const env of Array.from(
      stack.querySelectorAll(".env[data-order]"))) {
    const order = Number(env.dataset.order) || 0;
    if (order < lowest) lowest = order;
  }
  picked.dataset.order = String(lowest - 1);   // 滑到沓首
  for (const env of Array.from(stack.querySelectorAll(".env"))) {
    env.classList.toggle("env--lift", env === picked);
  }
  layoutEnvelopeStack(stack);
}

// 切换（F-3 在内）：批注开着不硬禁，一句话——那边的批注会先搁着，
// 回来还在（教学锁是各会话自己的，不跨信封跟随）。成功 = 局部刷新
// 案头（refreshCorrespondence），失败一行人话，永静默。
async function switchToCharacter(characterId) {
  let moment = null;
  try {
    moment = (await fetchCurrentMoment()).moment;
  } catch {
    moment = null;
  }
  if (moment && moment.lifecycle_state === "AWAITING_USER") {
    if (!(await confirmDialog("那边的批注还等着回应——切过去它会先搁着。"))) {
      return false;
    }
  }
  let data = null;
  try {
    data = await fetchSwitchCharacter(characterId);
  } catch {
    data = null;
  }
  if (!data || !data.switched) {
    addLine("failure", "没切过去——再试一次。");
    return false;
  }
  await refreshCorrespondence();
  return true;
}

// 切换后的案头刷新——局部，非整页（v2 动效内）：主从条重读名册；
// 信流清空重载该角色的 50 轮窗口；批注面随 loadHistory 的当前卡重建
// （教学轮询的 /api/teaching/current 本就随会话走，无需重指）；统计
// 与档案是读时取数，下一次打开自然落在新通信上。纸事件恰一次。
async function refreshCorrespondence() {
  try {
    renderMasthead(await fetchCharacters());
  } catch {
    // 名册这会儿读不到——主从条留空，下次打开选择器再灌
  }
  messages.textContent = "";
  showMoments([]);
  await loadHistory();
  const flow = document.querySelector("#space-parlor .flow");
  if (flow) {
    flow.classList.remove("flow-resettle");
    void flow.offsetWidth;
    flow.classList.add("flow-resettle");
  }
}

// ── mc-2: 角色编辑台——信封沓的「编辑」/空白封「完整编辑」进的 DIY
// 面（v3-2 容器化：**编辑台在展开的沓容器内**——用户原话「直接起草
// 编辑时，面板应当自动向下延伸拉开，是整个容器的变化，而不是多一个
// 滚动条」）──────────────────────────────────────────────────────────
// v2-2 的独立全页（fixed inset-0 + zoom 放大过渡 + 自带滚动井
// 与页面滚动条叠双杠）随本刀退役：openCharacterEditor 现在把九面
// 表单装进沓容器的编辑面（.envsel-editor），容器本体向下延展
// （setEnvelopeFace("editor") 经 extendContainer 的同族高度过渡——
// ⑩ 层级宪法的容器延展档）；表单长就滚容器自己的编辑面（唯一的滚
// 动井——零新增页面级滚动条，P2-8 一并消除）。三出口一致化（P1-4）：
// Esc / 「← 回沓」/「不改了」同语义 = 全部回沓（容器退一层回扇叠，
// 浏览上下文 envselPreviewId 保留）；存/删成功同样回沓（重排半区照
// 旧在回沓后跑）。
// 预填的诚实边界：/api/partner 的卡面只回五个键（name、identity_line、
// background、values、letter_habits）——personality、boundaries、
// opening、scenario 四面读不回（mc-0 没有全字段读面，web.py 本刀只许
// 动 400 人话）。表单照实开九面，读不回的四面如实话注记「留空原样
// 留着，写下就盖上」，保存时只送写过字的四面（PUT 不送 = 服务端原样
// 不动，mc-0 的更新文法）——永不拿空白盖旧文。
// 内置卡九面全部可编辑（mc-0 契约：编辑不拒、删除才拒；card_store 的
// _UPDATABLE_COLUMNS 九面全可写，勘察在册），不给删除钮。

// 九面的规格表（名字单独建面——必填 + 40 上限）：键 / 中文标签 / 一句
// 克制的人话说明 / 是否读不回 / 是否带开场信预览。中英皆可——用户
// 自建卡不禁词（总控已裁）。
const EDITOR_FACES = [
  { key: "identity", label: "身份行", veiled: false,
    hint: "信封面上示人的第一句——她一句话介绍自己。" },
  { key: "personality", label: "性情", veiled: true,
    hint: "她是个什么样的人，怎么与人相处。" },
  { key: "background", label: "背景", veiled: false,
    hint: "她走过的路，过着的日子。" },
  { key: "speech_style", label: "写信习惯", veiled: false,
    hint: "她的信长什么样——长短、口气、落笔的规矩。" },
  { key: "values", label: "看重的事", veiled: false,
    hint: "她放在心里、不肯换出去的东西。" },
  { key: "boundaries", label: "边界", veiled: true,
    hint: "她不做的事，不接的话题。" },
  { key: "opening", label: "开场信", veiled: true, preview: true,
    hint: "刚开始通信时，她寄来的第一封。" },
  { key: "scenario", label: "场景", veiled: true,
    hint: "她写信的地方，提笔的那一刻。" },
];

// 卡面读回键 → 表单键的映射（只有两处错位）：identity_line 载身份行、
// letter_habits 载写信习惯（服务端的两个旧键名，如实认）。
function editorCardValue(card, key) {
  if (!card) return "";
  if (key === "identity") return String(card.identity_line || "");
  if (key === "speech_style") return String(card.letter_habits || "");
  return String(card[key] || "");
}

// 就地字数（上限与 F-2 同源：name 40 / 散文 2000——maxLength 拦输入，
// 计数给眼睛）。
function editorCapLine(input, cap) {
  const line = document.createElement("p");
  line.className = "editor-cap";
  const count = document.createElement("span");
  count.className = "editor-count";
  count.textContent = String(input.value.length);
  line.appendChild(count);
  line.appendChild(document.createTextNode(" / " + cap));
  input.addEventListener("input", () => {
    count.textContent = String(input.value.length);
  });
  return line;
}

// 错误行人话：400（超上限等）已是中文，原样上浮；服务端 404 的英文
// 定谳句（no such character card，不在本刀 400 中文化范围）映射成
// 中文——已知句的定向替换，非通译。
function editorErrLine(data, fallback) {
  const message = data && data.error ? String(data.error) : "";
  if (message.indexOf("no such character card") !== -1) {
    return "没找到这张卡——它可能刚被删掉，回沓看看。";
  }
  return message || fallback;
}

// 回沓（v3-2 三出口统一，P1-4）：容器退一层回扇叠（同族容器收拢
// 过渡）；落定后跑 after（沓重排——born 纸事件要等编辑面撤了才播得
// 见）。Esc 与两颗钮都走这里——按钮与 Esc 同效，浏览上下文
// （envselPreviewId）保留。
function closeCharacterEditor(after) {
  if (!envselPanel || envselFace !== "editor") return;
  setEnvelopeFace("deck");
  if (typeof after === "function") {
    if (REDUCED_MOTION.matches) after();
    else setTimeout(after, 360);   // 收拢落定后再重排（保险丝同款窗）
  }
}

// 开台（v3-2 容器化）：mode = "edit"（沓中一封的「编辑」）| "create"
// （空白封的「完整编辑」）。时序 = 先装内容再延展——容器带着编辑面
// 的实际高度一次拉开（extendContainer 量的是换装后的高，两段跳变不
// 发生）。编辑先读卡面再开笔——读不回就不开（错误 + 重试），免得拿
// 空白表单盖了旧文。容器没开就不开台（编辑只从沓进）。
async function openCharacterEditor(opts) {
  if (!envselPanel) return;
  const mode = opts.mode === "create" ? "create" : "edit";
  const item = opts.item || null;
  const body = envselPanel.querySelector(".envsel-editor");
  if (!body) return;
  body.textContent = "";

  const back = document.createElement("p");
  back.className = "editor-back";
  const backBtn = document.createElement("button");
  backBtn.type = "button";
  backBtn.className = "btn btn--pencil";
  backBtn.textContent = "← 回沓";
  backBtn.addEventListener("click", () => closeCharacterEditor());
  back.appendChild(backBtn);
  body.appendChild(back);

  const kicker = document.createElement("p");
  kicker.className = "editor-kicker";
  kicker.textContent = mode === "create" ? "新笔友" : "角色卡";
  body.appendChild(kicker);

  const title = document.createElement("h2");
  title.className = "editor-title";
  title.textContent = mode === "create"
    ? "写给一位新笔友"
    : String((item && item.name) || "");
  body.appendChild(title);

  const sub = document.createElement("p");
  sub.className = "editor-sub";
  sub.textContent = mode === "create"
    ? "想到什么写什么——信封上只示人名字和身份行，其余的面她自己看。"
    : "想到什么改什么——信封上只示人名字和身份行，其余的面她自己看。";
  body.appendChild(sub);

  if (item && item.is_builtin) {
    const note = document.createElement("p");
    note.className = "editor-note";
    note.textContent = "这是随信来的第一位笔友——她可以改，不能删。";
    body.appendChild(note);
  }

  const form = document.createElement("div");
  form.className = "editor-form";
  body.appendChild(form);

  if (mode === "create") {
    buildEditorForm(form, { mode: mode, item: null, card: null });
    setEnvelopeFace("editor");   // 容器带着整份表单向下延展
    body.scrollTop = 0;
    return;
  }
  form.appendChild(stateBanner("loading"));
  let data = null;
  try {
    data = await fetchPartnerOf(item.character_id);
  } catch {
    data = null;
  }
  if (!envselPanel || envselFace !== "deck") {
    return;   // 沓已被收起/换态——不往看不见的面上写
  }
  form.textContent = "";
  if (!data || !data.card) {
    form.appendChild(stateBanner("error", {
      text: "这张卡的旧文没读到——读不回就不开笔，免得拿空白盖了旧文。",
      retry: () => {
        closeCharacterEditor(() => openCharacterEditor(opts));
      },
    }));
    setEnvelopeFace("editor");
    return;
  }
  buildEditorForm(form, { mode: mode, item: item, card: data.card });
  setEnvelopeFace("editor");   // 容器带着整份表单向下延展
  body.scrollTop = 0;
}

function buildEditorForm(form, opts) {
  const mode = opts.mode;
  const item = opts.item;
  const card = opts.card;
  const caps = { name: 40, prose: 2000 };   // 与 F-2 / 服务端同源

  const err = document.createElement("p");
  err.className = "editor-err";

  // 名字（必填）：信封的收件人、邮票的首字母。
  const nameFace = document.createElement("div");
  nameFace.className = "editor-face editor-face--name";
  const nameLabel = document.createElement("p");
  nameLabel.className = "editor-label";
  nameLabel.textContent = "名字";
  nameFace.appendChild(nameLabel);
  const nameHint = document.createElement("p");
  nameHint.className = "editor-hint";
  nameHint.textContent = "信封的收件人，邮票上的首字母——40 字已是满口。";
  nameFace.appendChild(nameHint);
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.maxLength = caps.name;
  nameInput.autocomplete = "off";
  nameInput.placeholder = "名字（必填）";
  nameInput.setAttribute("aria-label", "角色名");
  nameInput.value = String((card && card.name) || "");
  nameFace.appendChild(nameInput);
  nameFace.appendChild(editorCapLine(nameInput, caps.name));
  form.appendChild(nameFace);

  // 八个散文面：稿纸 textarea（.pen 家族）+ 说明句 + 就地字数；
  // 读不回的四面加一句如实话。
  const pens = {};
  for (const face of EDITOR_FACES) {
    const wrap = document.createElement("div");
    wrap.className = "editor-face"
      + (face.veiled ? " editor-face--veiled" : "");
    const label = document.createElement("p");
    label.className = "editor-label";
    label.textContent = face.label;
    wrap.appendChild(label);
    const hint = document.createElement("p");
    hint.className = "editor-hint";
    hint.textContent = face.hint;
    wrap.appendChild(hint);
    if (face.veiled) {
      const veil = document.createElement("p");
      veil.className = "editor-veil";
      veil.textContent = "旧文这里读不回——留空原样留着，写下就盖上。";
      wrap.appendChild(veil);
    }
    const pen = document.createElement("textarea");
    pen.className = "pen editor-pen";
    pen.maxLength = caps.prose;
    pen.setAttribute("aria-label", face.label);
    pen.value = editorCardValue(card, face.key);
    wrap.appendChild(pen);
    wrap.appendChild(editorCapLine(pen, caps.prose));
    if (face.preview) {
      const prevWrap = document.createElement("div");
      prevWrap.className = "editor-openprev";
      const prevLabel = document.createElement("p");
      prevLabel.className = "editor-label";
      prevLabel.textContent = "信的样子";
      prevWrap.appendChild(prevLabel);
      const prevPaper = document.createElement("p");
      prevPaper.className = "editor-openprev-paper";
      const syncPreview = () => {
        const text = pen.value.trim();
        prevPaper.classList.toggle("editor-openprev--empty", !text);
        prevPaper.textContent = text
          ? pen.value
          : "旧信这里读不回——写上几句，这里就是新信的样子。";
      };
      pen.addEventListener("input", syncPreview);
      syncPreview();
      prevWrap.appendChild(prevPaper);
      wrap.appendChild(prevWrap);
    }
    pens[face.key] = pen;
    form.appendChild(wrap);
  }

  // 动作：存（主）· 不改了 · 删了这封（只有用户卡有）。
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--ink editor-save";
  save.textContent = "存";
  save.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    if (!name) {
      err.textContent = "一张卡得有名字——空白的信封寄不出去。";
      return;
    }
    save.disabled = true;
    let data = null;
    try {
      if (mode === "create") {
        const fields = { name: name };
        for (const face of EDITOR_FACES) {
          const raw = pens[face.key].value;
          if (raw.trim()) fields[face.key] = raw;
        }
        data = await fetchCreateCharacter(fields);
      } else {
        const fields = { name: name };
        for (const face of EDITOR_FACES) {
          const raw = pens[face.key].value;
          if (face.veiled) {
            if (raw.trim()) fields[face.key] = raw;   // 写下才盖上
          } else {
            fields[face.key] = raw;   // 读得回的五面照抄表单
          }
        }
        data = await fetchUpdateCharacter(item.character_id, fields);
      }
    } catch {
      data = null;
    }
    if (!data || !data.character) {
      save.disabled = false;
      err.textContent = editorErrLine(data, "没能落笔——再试一次。");
      return;
    }
    if (mode === "create") {
      envselBornId = data.character.character_id;   // 新封落沓的纸事件
      closeCharacterEditor(async () => {
        await refreshEnvelopeStack();   // 新封落沓（最尾，纸事件一次）
      });
    } else {
      closeCharacterEditor(async () => {
        await refreshEnvelopeStack();   // 沓重排：名更新、邮票与姿态不动
      });
    }
  });
  form.appendChild(save);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn btn--faint";
  cancel.textContent = "不改了";
  cancel.addEventListener("click", () => closeCharacterEditor());
  form.appendChild(cancel);

  if (item && !item.is_builtin) {
    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn btn--faint editor-delete";
    del.textContent = "删了这封";
    del.addEventListener("click", async () => {
      if (!(await confirmDialog(
          "删了这封，沓里就再没有这位笔友——已写过的信留在信档里。"
          + "这一步收不回来。"))) {
        return;
      }
      del.disabled = true;
      let data = null;
      try {
        data = await fetchDeleteCharacter(item.character_id);
      } catch {
        data = null;
      }
      if (!data || !data.deleted) {
        del.disabled = false;
        err.textContent = editorErrLine(data, "没删成——再试一次。");
        return;
      }
      closeCharacterEditor(async () => {
        await refreshEnvelopeStack();   // 沓重排：那封不在了
      });
    });
    form.appendChild(del);
  }

  form.appendChild(err);
}

// ── v3-2R 起笔写信工作区（核心一，零裁量重铸）：点「起笔」= 选定角色
// 开始写信——沓容器本体向下延展**成为写信工作界面**（compose 面，⑩
// 层级宪法的容器延展档），不是收沓回案头去写信，更不是建卡表单（上
// 一刀的降级实现，用户判词整刀否定；新建角色的表单归「完整编辑」，
// 不占「起笔」语义）。工作区内完成「写一封信并寄出」全流程：收件人
// （角色名与一句身份，只读）→ 多行稿纸 → 寄出 → 回执 → 容器收拢
// 让位案头信流（收拢方向与延展对称，同曲线反向——envsel--fold 同一
// 注册对）。禁新页面切换，禁容器外新开滚动区。

// 起笔（选定角色开始写信）：选定角色 ≠ 当前通信时先切换（既有确认与
// 失败姿态原样），沓缓存的 current 同步改真（随后 Esc 回沓再点起笔
// 不会重复发起切换）；再建面再延展——容器带着工作区的实际高度一次
// 拉开（extendContainer 的同族过渡）。容器没开就不起笔（起笔只从沓
// 进）。
async function startComposing(item) {
  if (!envselPanel) return;
  const isCurrent = charactersCache &&
    item.character_id === charactersCache.current_character_id;
  if (!isCurrent) {
    const done = await switchToCharacter(item.character_id);
    if (!done || !envselPanel) return;   // 没切过去/切换期间沓被收——不起笔
    charactersCache.current_character_id = item.character_id;
  }
  buildComposeFace(item);
  setEnvelopeFace("compose");   // 容器带着写信工作区向下延展
}

// 写信工作区的 DOM：回沓行 + 收件人（致 + 角色名 + 一句身份——选定角色
// 的信封面，**只读**，不是建卡表单）+ 多行稿纸（.pen 家族，与案头同一
// 手感：Enter 寄出、Shift+Enter 换行）+ 动作行（寄出 → / 先搁着）。
// 寄出 = 信落案头信流（postTurn 同一发送管线：在途信封、「寄出」邮戳、
// 等回音行、批注轮询全是它的事）+ 工作区回执一拍 + 容器收拢让位案头；
// 在途守卫与案头同一枚 sending（在途只此一封）。一切文字 textContent。
function buildComposeFace(item) {
  const body = envselPanel && envselPanel.querySelector(".envsel-compose");
  if (!body) return;
  body.textContent = "";

  const back = document.createElement("p");
  back.className = "compose-back";
  const backBtn = document.createElement("button");
  backBtn.type = "button";
  backBtn.className = "btn btn--pencil";
  backBtn.textContent = "← 回沓";
  backBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    setEnvelopeFace("deck");
  });
  back.appendChild(backBtn);
  body.appendChild(back);

  const to = document.createElement("p");
  to.className = "env-to compose-to";
  const toWord = document.createElement("span");
  toWord.className = "env-to-word";
  toWord.textContent = "致";
  to.appendChild(toWord);
  const name = document.createElement("b");
  name.className = "env-name";
  name.textContent = String(item.name || "");
  to.appendChild(name);
  body.appendChild(to);
  const line = document.createElement("p");
  line.className = "env-line compose-line";
  line.textContent = String(item.identity_line || "");
  body.appendChild(line);

  const pen = document.createElement("textarea");
  pen.className = "pen compose-pen";
  pen.maxLength = 2000;   // 与服务端散文面上限同源（mc-2 的 caps.prose）
  pen.setAttribute("aria-label", "写给她的信");
  pen.placeholder = "今日如何？想从哪句起，就从哪句起。";
  body.appendChild(pen);
  // 草稿层（复测坏3）：退出保稿、重开恢复——Esc/回沓/点外都不是「扔信」
  try {
    const draft = sessionStorage.getItem(composeDraftKey(item.character_id));
    if (draft) pen.value = draft;
  } catch { /* 隐私模式等存储不可用——退化为无草稿，不阻断写信 */ }
  pen.addEventListener("input", () => {
    try {
      sessionStorage.setItem(composeDraftKey(item.character_id), pen.value);
    } catch { /* 同上：存不上也不打断 */ }
  });

  const actions = document.createElement("p");
  actions.className = "compose-actions";
  const send = document.createElement("button");
  send.type = "button";
  send.className = "btn btn--send";
  send.textContent = "寄出 →";
  actions.appendChild(send);
  const shelve = document.createElement("button");
  shelve.type = "button";
  shelve.className = "btn btn--faint compose-shelve";
  shelve.textContent = "先搁着";
  shelve.addEventListener("click", (event) => {
    event.stopPropagation();
    setEnvelopeFace("deck");
  });
  actions.appendChild(shelve);
  body.appendChild(actions);
  const err = document.createElement("p");
  err.className = "editor-err";
  body.appendChild(err);

  const post = () => {
    const text = pen.value.trim();
    if (!text) {
      err.textContent = "空白的信寄不出去——写一句再寄。";
      return;
    }
    if (sending) {   // 在途只此一封（与案头同一守卫）
      err.textContent = "上一封还在路上——落地了再寄。";
      return;
    }
    send.disabled = true;
    pen.disabled = true;
    // rd-1 邮戳盖下（与案头同一枚动效）：寄出一瞬按钮按下——类由
    // animationend 自摘（reduced-motion 下 0.01ms 即终、事件仍到）。
    send.classList.add("stamp-press");
    send.addEventListener("animationend",
      () => send.classList.remove("stamp-press"), { once: true });
    sending = true;
    // 信落案头信流（同一发送管线——在途封与「寄出」邮戳是它的事）；
    // 回执不等回信（模型往返数秒），容器收拢后信流自己往下走。
    postTurn(text).finally(() => {
      sending = false;
    });
    // 寄出是唯一清稿时机（草稿层纪律：其余退出路径一律保稿）
    try {
      sessionStorage.removeItem(composeDraftKey(item.character_id));
    } catch { /* 存储不可用——无稿可清 */ }
    // 回执一拍：寄出是真实事件——一句人话回执（邮戳留在案头那封上，
    // 同屏 ≤1 枚的纪律不在这里再盖），随后容器收拢让位案头信流（收
    // 拢方向与延展对称，同曲线反向）。回执期间 Esc/先搁着回沓即取消
    // 自动收拢（人已选择留下，不追着关）。
    body.textContent = "";
    const receipt = document.createElement("p");
    receipt.className = "sysline compose-receipt";
    receipt.textContent = "寄出了——回信落在案头的信流里。";
    body.appendChild(receipt);
    const beat = REDUCED_MOTION.matches ? 0 : 1000;
    setTimeout(() => {
      if (envselPanel && envselFace === "compose") {
        closeEnvelopeSelector();   // 收拢让位案头——在途的信就在信流里
        // 收拢后滚到信流底：新落的信（复测小7——签名行不被输入条遮）
        const flow = document.getElementById("messages");
        if (flow) flow.scrollTop = flow.scrollHeight;
      }
    }, beat);
  };
  send.addEventListener("click", (event) => {
    // 容器内动作件一律 stopPropagation（沓家同例）：回执换装会把事件
    // 目标摘出 DOM——冒泡到 document 时 envselCloser 的 contains 判定
    // 反咬一口（收件人一边寄出一边被「点外关闭」），活体实证在案。
    event.stopPropagation();
    post();
  });
  // 与案头同一手感：Enter 寄出，Shift+Enter 换行。
  pen.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      post();
    }
  });
}

// 硬伤 C 视口跟随：起笔延展落定（--dur-settle 320 + 余量，与回沓重排
// 的 360 同款窗）后笔尖聚焦——焦点即跟随（触屏弹键盘、浏览器把聚焦
// 件送进视口，「像没反应」的落选感不发生）；容器本体若在视口外（极
// 端档）先把窗口滚到它。reduced-motion 直落（0ms）。
function followComposeWorkspace(panel, face) {
  const run = () => {
    if (!envselPanel || envselPanel !== panel) return;
    const rect = panel.getBoundingClientRect();
    if (rect.top < 0 || rect.bottom > window.innerHeight) {
      panel.scrollIntoView({ block: "nearest",
        behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });
    }
    const pen = face && face.querySelector(".compose-pen");
    if (pen) pen.focus();
  };
  if (REDUCED_MOTION.matches) {
    run();
    return;
  }
  setTimeout(run, 360);
}

// 沓尾的新建空白信封（v3-2R 定谳）：只有「完整编辑」一个入口——新建
// 角色的表单归编辑台（容器编辑面的九面 DIY，名字必填、其余面想写就
// 写），**不得占用「起笔」语义**（上一刀把「起笔」做成建卡表单的降
// 级实现已被判词否定）；建好了，她就躺在沓里等你起笔。
function newEnvelopeCard() {
  const env = document.createElement("article");
  env.className = "env env--new";
  env.tabIndex = 0;
  const to = document.createElement("p");
  to.className = "env-to";
  const name = document.createElement("b");
  name.className = "env-name";
  name.textContent = "写给一位新笔友";
  to.appendChild(name);
  env.appendChild(to);
  const hint = document.createElement("p");
  hint.className = "env-line env-newhint";
  hint.textContent = "名字加九面，点「完整编辑」一次写全——建好了，她就躺在沓里等你起笔。";
  env.appendChild(hint);
  const full = document.createElement("button");
  full.type = "button";
  full.className = "btn btn--pencil env-newbtn env-newfull";
  full.textContent = "完整编辑";
  full.addEventListener("click", (event) => {
    event.stopPropagation();
    openCharacterEditor({ item: null, mode: "create" });
  });
  env.appendChild(full);
  return env;
}

// 触发（mc-1）：品牌条 who 块整体可点（不增长按钮元——r1_shell
// 「<button 不在品牌条」钉保留）；键盘可达（tabindex + Enter/Space）。
// 点开信封沓（再点一次收沓）；档案从沓中每封的「档案」动作进。
const whoBlock = document.querySelector("#space-parlor .top > div");
if (whoBlock) {
  whoBlock.setAttribute("tabindex", "0");
  whoBlock.setAttribute("role", "button");
  whoBlock.setAttribute("aria-label", "信封沓——挑一位笔友");
  whoBlock.addEventListener("click", (event) => {
    event.stopPropagation();
    if (envselPanel) {
      closeEnvelopeSelector();
      return;
    }
    openEnvelopeSelector();
  });
  whoBlock.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      event.stopPropagation();
      if (envselPanel) {
        closeEnvelopeSelector();
        return;
      }
      openEnvelopeSelector();
    }
  });
}
