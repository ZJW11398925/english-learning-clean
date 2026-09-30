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
  confirmDialog,
  fieldRow,
  chip,
  wireNavdock,
  markNavdock,
  wireSectionTabs,
  markSectionTabs,
  sectionLabel,
  disclosure,
  wireReveal,
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
  fetchDelete,
  fetchGoals,
  fetchSaveGoals,
  fetchSaveFrequency,
} from "./api.js";

// ── ⑧ 8.3 术语翻译表（工程词 → 客厅语言，唯一集中定义）──────────────
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
  OFF: "不递",
  MINIMAL: "少递",
  BALANCED: "适度",
  EAGER: "勤递",
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
  }
}

// ── 档案 · 折叠明细（rd-3 降级位）────────────────────────────────────
// 三面原值渲染器保持原样——原值在折叠区里是合法形态（机械事实的唯一
// 归宿 = 折叠的原始读数，⑧ 8.4.3）。排程与目标降入「计划明细」折叠
// （时间敏感的是今天不是下周——默认层只留计划一行）；账表降入
// 「按表达看」折叠。

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
    renderSchedule(data.schedule, loadLearning);
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
const LEARN_PANEL_IDS = ["archive-board", "plan-line", "record-book",
                         "learn-schedule", "learn-goals", "learn-evidence",
                         "today-practice"];

function showLoading(ids) {
  for (const id of ids) {
    const box = diagBox(id);
    box.textContent = "";
    box.appendChild(stateBanner("loading"));
  }
}

// 回客厅的直达按钮（行动块的邀请态与成长空态共用）——动作词，落点
// 是客厅信流（教学批注与聊天都发生在那里）
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
        if (on) hit = true;
      }
      g.disc.root.hidden = !hit;
      g.disc.setOpen(hit);
      if (hit) any = true;
    }
    noHit.hidden = any;
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
    hint.textContent = "先去客厅聊一句，批注会自己来找你。";
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
  if (total < ARCHIVE_STORY_GATE) {
    const wish = document.createElement("p");
    wish.className = "sub";
    wish.textContent = "攒够 " + ARCHIVE_STORY_GATE + " 次批注，这里会讲一个学期的故事——现在有 " + total + " 条。";
    board.appendChild(wish);
  }
  if (!claims.length) {
    diagEmpty(board, "还没有批注留痕——聊起来才会有。");
    return;
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
      body.appendChild(line);
      built.push({
        node: line,
        probe: ((spokenOf(claim.target_id) + " " + claim.target_id)
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
        if (on) hit = true;
      }
      g.disc.root.hidden = !hit;
      g.disc.setOpen(hit);
      if (hit) any = true;
    }
    noHit.hidden = any;
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

// ── p-2 / R-1R: 记忆页 —— 摘要行 + 五面板（关系 / 剧情 / 学习状态 /
// 痕迹 / 存根）。字段名全中文化；指纹缩前 12 位；时间一律人话。 ──────

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

function renderMemStates(d, retry) {
  const box = diagBox("mem-states");
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

function renderMemEvidence(d, retry) {
  const box = diagBox("mem-evidence");
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

function renderMemTombstones(d, retry) {
  const box = diagBox("mem-tombstones");
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
    renderMemRelationship(data.relationship_memory, loadMemory);
    renderMemEpisode(data.episode, loadMemory);
    renderMemStates(data.learner_states, loadMemory);
    renderMemEvidence(data.evidence, loadMemory);
    renderMemTombstones(data.tombstones, loadMemory);
    renderMemSummary(data);
  } catch {
    for (const id of MEM_PANEL_IDS) {
      diagError(diagBox(id), "记忆读数拉取失败", loadMemory);
    }
  }
}

// ── p-2 / R-1R: 隐私页 —— 请客厅忘掉一些事。先讲会失去什么，再要两次
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
  if (!confirmDialog(
    "将把「" + rangeText + "」请出抽屉，找不回来。确定继续？")) return;
  if (!confirmDialog("再确认一次：忘掉之后无法恢复。")) return;
  let data = null;
  try {
    data = await fetchDelete(payload);
  } catch {
    renderDelRefused("请求没送到——再试一次。", "network");
    return;
  }
  if (!data.accepted) {
    renderDelRefused(data.message || "客厅拒绝了这次忘掉。",
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

// ── p-3 / R-1R: 方向页 —— 长期方向在此写下。读写合一（读卡取消，当前
// 值直接进编辑面）；保存 = 全组合 upsert（版本前移，不保留旧版）；冲突
// 诚实上浮（409）→「重新读过」。词表词中英并置（中文 + 等宽小字原文）。
// 词表取自服务端 taxonomy，客户端零拷贝。 ─────────────────────────────

const GOAL_PANEL_IDS = ["goal-weights", "goal-assessment",
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
    const select = document.createElement("select");
    for (const word of words) {
      const option = document.createElement("option");
      option.value = word;
      // select 的 option 只能是纯文本：中英并置在此退化为纯文本形态
      // （中文 + 空格 + 原文；等宽小字形态见 chips / field 名牌）
      option.textContent = MODALITY_CN[word]
        ? MODALITY_CN[word] + " " + word
        : word;
      if (word === goal.goal_modality) option.selected = true;
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      goal.goal_modality = select.value;
    });
    edge.appendChild(fieldRow("目标 " + (index + 1) + " · 技能", select));
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

function renderGoalFrequency() {
  const box = goalBox("goal-frequency");
  box.textContent = "";
  if (!goalEditor) return;
  const policy = goalData && goalData.policy;
  if (policy) {
    // 「现在：适度（BALANCED）」——版本号移出常显（⑧ 8.2.4：版本只出现
    // 在保存回执与冲突句）
    const line = document.createElement("div");
    line.className = "kv";
    const b = document.createElement("b");
    b.textContent = "现在：";
    line.appendChild(b);
    const word = policy.teaching_frequency;
    if (FREQUENCY_CN[word]) {
      line.appendChild(document.createTextNode(FREQUENCY_CN[word] + "（"));
      line.appendChild(rawTag(word));
      line.appendChild(document.createTextNode("）"));
    } else {
      line.appendChild(rawTag(word));
    }
    box.appendChild(line);
  } else {
    diagLine(box, "现在", "还没有写过——在下面挑一个。");
  }
  const row = document.createElement("div");
  row.className = "chips";
  for (const word of goalFrequencyWords()) {
    row.appendChild(chip(word, {
      on: goalEditor.frequency === word,
      cn: FREQUENCY_CN[word] || null,
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
  save.textContent = "保存批注频率";
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
  button.textContent = "保存中……";
  let data = null;
  try {
    data = await fetchSaveFrequency(editor.frequency);
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
      : "已保存（第 " + data.policy_version + " 版）。", false);
    loadGoals();
  } else if (data.conflict) {
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
  goalEditor.frequency =
    (goalData.policy && goalData.policy.teaching_frequency) || null;
  renderGoalEditor();
  renderGoalWeights();
  renderWordPicker("goal-assessment", "external_assessment",
    goalEditor.assessment, null);
  renderWordPicker("goal-register", "register_style",
    goalEditor.register, REGISTER_CN);
  renderGoalSave();
  renderGoalFrequency();
  renderGoalFocus();
  renderGoalTaxref();
}

// ── R-1: the spaces — 门厅 / 客厅 / 温故 / 抽屉 — plain show/hide, no
// router. The dock (#18) is the only way between spaces; entering the
// study or the drawer lands its default section, and switching a section
// (#20 tabs) is the pull — the section always shows its own facts, never
// a stale page. ────────────────────────────────────────────────────────

const spaces = {
  onboard: document.getElementById("screen-onboard"),
  parlor: document.getElementById("space-parlor"),
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

// entering a section is the pull; settings has nothing to pull yet — the
// honest placeholder stands (no promised face, no promised date)
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
  "drawer-privacy": loadDelTargets,
};

function showSection(space, name) {
  const group = SECTION_BODIES[space];
  for (const key of Object.keys(group)) {
    group[key].hidden = key !== name;
  }
  markSectionTabs(document.getElementById(space + "-tabs"), name);
  sectionLabel(document.getElementById(space + "-head"),
    SECTION_NAMES[name]);
  const pull = SECTION_PULLS[space + "-" + name];
  if (pull) pull();
  window.scrollTo(0, 0);
}

function showSpace(name) {
  for (const key of Object.keys(spaces)) {
    spaces[key].hidden = key !== name;
  }
  markNavdock(name);
  // the vestibule has no spaces to switch between — the door button is
  // the one way in, so the dock stands down while the cover is up
  document.getElementById("navdock").hidden = name === "onboard";
  if (name === "study") showSection("study", DEFAULT_SECTION.study);
  if (name === "drawer") showSection("drawer", DEFAULT_SECTION.drawer);
  window.scrollTo(0, 0);
}

// R-1 wiring: the dock switches spaces, the two tab lists switch sections
// (a click and the left/right arrows both land on the same showSection).
wireNavdock((name) => showSpace(name));
wireSectionTabs(document.getElementById("study-tabs"),
  (name) => showSection("study", name));
wireSectionTabs(document.getElementById("drawer-tabs"),
  (name) => showSection("drawer", name));

// 记录页的底：一切原值折进一个 #21（⑧ 8.2.5）——观察读数第一次展开
// 才拉，拉取失败 = 区内一行 + 重试。计划明细与按表达看同法收养
// （rd-3：排程/目标/账表降入按需折叠，默认层只留计划一行）。
let observationsLoaded = false;

async function loadObservations() {
  if (observationsLoaded) return;
  observationsLoaded = true;
  const status = diagBox("obs-status");
  const out = diagBox("obsout");
  status.textContent = "";
  status.appendChild(stateBanner("loading"));
  let data = null;
  try {
    data = await fetchObservations();
  } catch {
    data = null;
  }
  status.textContent = "";
  if (data === null) {
    status.appendChild(stateBanner("error", {
      text: "观察读数没取到。",
      retry: () => {
        observationsLoaded = false;
        loadObservations();
      },
    }));
    return;
  }
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
}

const rawReadings = disclosure({
  name: "原始读数（给排查用）",
  content: diagBox("raw-readings"),
  onFirstExpand: () => loadObservations(),
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
  "信还没开始写——想从哪句起，就从哪句起。中文英文都行；写错了，客厅接得住。";

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
  addLine("user", text, { enter: true });
  // the placeholder is the user's "it is working" signal: removed the
  // moment the turn response lands (or fails) — never left behind.
  // rd-2：发送后状态行升「信已寄出，等回信——」收尾（8.5 流式落点句随迁）
  const pending = addLine("typing", "信已寄出，等回信——客厅把灯留着。");
  startMomentPolling();
  let data = null;
  try {
    data = await fetchTurn(text);
  } catch {
    addLine("failure", "请求没送到——再试一次。");
  } finally {
    stopMomentPolling();
    pending.remove();
  }
  if (data !== null) {
    if (data.reply !== null && data.reply !== undefined) {
      addLine("assistant", data.reply, { enter: true });
    } else if (data.turn_status !== null && data.turn_status !== undefined) {
      failLine("这封信没有回音——客厅没能联系上模型端点",
        data.failure_reason || "无回复");
    } else if (data.failure_reason) {
      failLine("这封信没有回音——客厅没能联系上模型端点",
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

document.getElementById("send").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  // rd-1 邮戳盖下（⑨-5）：寄出一瞬邮票按下——scale .96→1 的 transform
  // 收束（非投影）；类由 animationend 自摘（reduced-motion 下动画
  // 0.01ms 即终、事件仍到，清理不失效）
  const stamp = document.querySelector("#send .btn--send");
  if (stamp) {
    stamp.classList.add("stamp-press");
    stamp.addEventListener("animationend",
      () => stamp.classList.remove("stamp-press"), { once: true });
  }
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

async function loadHistory() {
  const data = await fetchHistory();
  for (const turn of data.turns) {
    if (turn.user !== null) addLine("user", turn.user);
    if (turn.assistant !== null) addLine("assistant", turn.assistant);
  }
  // 空厅句：一封信都还没有时，客户端静态系统行开场（⑧ 8.2.2）
  showEmptyHall();
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
  loadHistory();
  // F-1R/R-1: the first visit sees the cover; every later visit lands in
  // the parlor directly (the cover never comes back once localStorage
  // says so)
  showSpace(seenOnboard() ? "parlor" : "onboard");
});
