// components.js —— 组件工厂与教学卡的当场行为（F-G1）。
// 纪律：一切用户可见的文字只走 createElement + textContent——用户的
// 英语、模型的回复、面板读数永远是惰性文本，绝不进标记（XSS 面）。
// 每个工厂对应 docs/FRONTEND_SPEC.md ③ 的一行契约；类名的样式唯一
// 出处是 components.css。本文件是 window.confirm 的唯一封装点
// （confirmDialog）；对端点的调用只走 api.js。

import { fetchTeachingReply } from "./api.js";

// the flow's two boxes; `messages` is exported (the blocked-line writer
// in app.js appends to it directly), `momentsBox` stays module-internal.
export const messages = document.getElementById("messages");
const momentsBox = document.getElementById("moments");

function scrollBottom() {
  // R-1V：短通信不追底——旧实现无条件滚到文档最底，内容不满一屏时
  // 也把第一封信顶进 sticky 品牌条背后（滚掉的只是底部留白）。新法：
  // 只在「最后一行的底部会没入写信区」时滚到刚好让它露出；长通信的
  // 追底行为与旧实现一致（clamp 到文档底）。
  const last = messages.lastElementChild;
  if (!last) return;
  const clearance = 150;  // dock + navdock 的遮挡余量（保守值）
  const lastBottom = last.offsetTop + last.offsetHeight;
  const target = lastBottom + clearance - window.innerHeight;
  window.scrollTo(0, Math.max(0, Math.min(target,
    document.body.scrollHeight - window.innerHeight)));
}

// F-1R: the letter flow — a turn's words become letters, never bubbles.
// v2 信件排印骨架（简报 T1）：件件来自真实数据，不虚构文本——
// 来信 .letter.may = 日期行（真实时间戳；无则整件缺席）+ 称呼（仅当
// 正文自带）+ 正文段（段间距模式）+ 落款（仅当正文自带结束语/署名，
// 楷体手迹位齐右）+ 又及（仅当正文自带）。我方回信 .letter.me = 撕口
// 信纸 + 原文 + 落款「你」（界面通篇的第二人称——现役无用户名字源，
// 不虚构人名）。a failure is marginalia (a pencil rule in the left
// margin), a system note is a centered faint line. Every word rides
// textContent — the user's own words stay inert text, never markup.

// 段落切分：信件惯例（单换行即新段——模型的回信与西文 block 传统）。
function letterParagraphs(text) {
  return String(text).split(/\n+/).map((p) => p.trim()).filter(Boolean);
}

// 称呼（salutation）：仅当正文自带——首段是独立称呼行（短、以逗号/
// 叹号/冒号收尾【中英全角半角皆收——v2-1R M-1：主语言中文的回信
// 不能系统性缺这件】、无句中标点）。提取不到就没有这件（不虚构问候）。
function salutationOf(paragraphs) {
  const first = paragraphs[0] || "";
  if (paragraphs.length < 2 || first.length > 48) return null;
  if (!/[,，!！：:]$/.test(first)) return null;
  if (/[.。；;?？]/.test(first.slice(0, -1))) return null;
  return first;
}

// 落款块（complimentary close + signature）：仅当正文自带——尾部收
// 结束语行（短、常见结束语词【中英语表皆收——v2-1R M-1】、逗号收尾
// 或中文无标点短语）与/或署名行（更短、无终端标点、非 P.S.）。
// 提取不到就没有这件（不虚构结束语文本）。
const SIGN_CLOSE =
  /(yours|best|love|warmly|regards|cheers|sincerely|talk soon|take care|later|as ever|thanks|此致|敬上|敬祝|祝好|祝安|顺祝|近好|秋安|冬安|春安|夏安|勿念)/i;

function signatureBlockOf(paragraphs) {
  const lines = [];
  let at = paragraphs.length;
  const last = paragraphs[at - 1] || "";
  const isPs = /^(p\.?\s?s\.?|ps)/i.test(last);
  if (!isPs && at > 1 && last.split(/\s+/).length <= 4 &&
      !/[.!?。！？]$/.test(last)) {
    lines.push(last);
    at -= 1;
    const close = paragraphs[at - 1] || "";
    const closeOk =
      (/[,，]$/.test(close) && SIGN_CLOSE.test(close)) ||
      (SIGN_CLOSE.test(close) && close.length <= 8 &&
       !/[.!?。！？，,]$/.test(close));
    if (at > 1 && close.split(/\s+/).length <= 6 && closeOk) {
      lines.unshift(close);
      at -= 1;
    }
  }
  return { lines, rest: paragraphs.slice(0, at) };
}

// 又及（P.S.）：仅当正文自带——以 P.S. / PS 开头的段落（弱墨、不缩进）。
function isPostscript(paragraph) {
  return /^(p\.?\s?s\.?:?|ps\.?:?)/i.test(paragraph);
}

// 日期行（dateline）：真实时间戳才有——历史回填无时间戳（web.py 冻结
// 面故无字段），一个日期都不造；新信由调用方传落地当下（客户端本机
// 时间的真实事件时刻）。
function letterDate(when) {
  if (!when) return null;
  const row = document.createElement("p");
  row.className = "letter-date";
  const span = document.createElement("span");
  span.title = String(when);
  span.textContent = humanLetterTime(String(when));
  row.appendChild(span);
  return row;
}

// 信件日期行的人话时间（humanTime 的信件读法，components.js 内自足：
// 今天 14:05 / 9 月 21 日 / 2025 年 12 月 3 日——跨年给全年月日，
// 不再「去年」止步：信要经年重读）。解析不了的原样直出。
function humanLetterTime(iso) {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  const now = new Date();
  const hh = String(then.getHours()).padStart(2, "0");
  const mm = String(then.getMinutes()).padStart(2, "0");
  if (then.getFullYear() === now.getFullYear() &&
      then.getMonth() === now.getMonth() &&
      then.getDate() === now.getDate()) {
    return "今天 " + hh + ":" + mm;
  }
  const year = then.getFullYear() === now.getFullYear()
    ? "" : then.getFullYear() + " 年 ";
  return year + (then.getMonth() + 1) + " 月 " + then.getDate() + " 日";
}

export function addLine(cls, text, opts) {
  const options = opts || {};
  let node;
  if (cls === "user") {
    node = document.createElement("div");
    node.className = "letter me";
    const paper = document.createElement("div");
    paper.className = "paper";
    const date = letterDate(options.when);
    if (date) paper.appendChild(date);
    const say = document.createElement("p");
    say.className = "say";
    say.appendChild(letterWords(text));  // 分片（#15 触发面）：文字仍全部
    paper.appendChild(say);              // 惰性文本，整段逐字不变
    const sign = document.createElement("p");
    sign.className = "letter-sign";
    sign.textContent = "你";
    paper.appendChild(sign);
    node.appendChild(paper);
  } else if (cls === "assistant") {
    node = document.createElement("div");
    node.className = "letter may";
    const paragraphs = letterParagraphs(text);
    const date = letterDate(options.when);
    if (date) node.appendChild(date);
    const salut = salutationOf(paragraphs);
    let body = paragraphs;
    if (salut !== null) {
      const row = document.createElement("p");
      row.className = "letter-salut";
      row.appendChild(letterWords(salut));
      node.appendChild(row);
      body = paragraphs.slice(1);
    }
    const signBlock = signatureBlockOf(body);
    body = signBlock.rest;
    for (const para of body) {
      const say = document.createElement("p");
      say.className = "say" + (isPostscript(para) ? " letter-ps" : "");
      say.appendChild(letterWords(para));
      node.appendChild(say);
    }
    for (const line of signBlock.lines) {
      const sign = document.createElement("p");
      sign.className = "letter-sign";
      sign.appendChild(letterWords(line));
      node.appendChild(sign);
    }
  } else if (cls === "typing") {
    node = document.createElement("p");
    node.className = "typing";
    node.appendChild(inkIcon("write"));  // R-1V：回信在途中配执笔小图
    node.appendChild(document.createTextNode(text));
  } else if (cls === "failure") {
    node = document.createElement("p");
    node.className = "errline";
    node.textContent = text;
  } else {
    node = document.createElement("p");
    node.className = "sysline";
    node.textContent = text;
  }
  // v2 动效（简报 §5 纸先落墨后渗）：opts.enter 的新信才播——双动画
  // （paper-drop transform 280 + ink-wash opacity 360，opacity 恒慢于
  // transform）+ .ink-wet 墨水物理（正文字色 ink-ghost→ink ≈600ms
  // 一次性）；历史回填（loadHistory）不播，五十轮回填不闪。
  if (options.enter) node.classList.add("flow-enter", "ink-wet");
  messages.appendChild(node);
  scrollBottom();
  return node;
}

// 11. confirm-dialog：原生 confirm 的唯一封装点——保持原生形态，
// 不自制弹层；只用于不可逆面（看答案）。
export function confirmDialog(message) {
  return window.confirm(message);
}

// W-6: the attempt loop, made legible. The verdict is a prominent strip
// （R-1R 起：中文判词打头——rd-2 豪放档判词：✓ 答得漂亮 / ◐ 答了一半 /
// ✗ 没答中——runtime 原话随后；the symbol is display only）, and a
// submitted reply is visible the instant it goes out — a help reply waits
// out a model round trip, and a silent wait reads as a dead page.
const OUTCOME_VERDICT_CN = {
  SUCCESS: "✓ 答得漂亮",
  ALTERNATIVE_SUCCESS: "✓ 答得漂亮（另一种说法也算）",
  PARTIAL: "◐ 答了一半",
  FAILURE: "✗ 没答中",
  ABSTAIN: "这次没法判",
};

function outcomeSymbol(feedback) {
  const word = String(feedback).split("（")[0];
  if (word === "SUCCESS" || word === "ALTERNATIVE_SUCCESS") return "✓";
  if (word === "PARTIAL") return "◐";
  if (word === "FAILURE") return "✗";
  return "";
}

// 7. resultstrip：判分结果条（✓/◐/✗ 是显示件；中文判词打头，runtime
// 原话随后——⑧ 8.2.10 定稿）。
export function showResultStrip(card, feedback) {
  const symbol = outcomeSymbol(feedback);
  const head = OUTCOME_VERDICT_CN[String(feedback).split("（")[0]] || "";
  const strip = document.createElement("div");
  strip.className = "resultstrip " +
    (symbol === "✓" ? "ok" : symbol === "✗" ? "miss" : "part");
  strip.textContent = head ? head + " · " + feedback : feedback;
  card.appendChild(strip);
}

// 8. busystrip：busy 期间卡内控件全 disabled、出现一行批改中条。
export function setReplyBusy(card, busy, note) {
  for (const button of Array.from(card.querySelectorAll("button"))) {
    button.disabled = busy;
  }
  const input = card.querySelector(".replytext");
  if (input) input.disabled = busy;
  let strip = card.querySelector(".busystrip");
  if (busy) {
    if (!strip) {
      strip = document.createElement("div");
      strip.className = "busystrip";
      card.appendChild(strip);
    }
    strip.textContent = note;
  } else if (strip) {
    strip.remove();
  }
}

// 3. note-paper：教学批注卡（rd-2 起家族词批注；R-1R 起：卡头
// 「批注：{功能句}」+ 状态行（服务端 status_cn 原词，界面不自造）+
// 类型行（中文映射，未知值省略该行——不兜底直出），等回应控件）。
// kind 的中文映射（⑧ 8.2.10 / 8.3）：CURRENT_USER_ERROR → 你信里的
// 句子（rd-2 豪放档）；RESOURCE_PRACTICE → 资源练习（服务端 kind_cn
// 的原词，镜像非自造，web.py 冻结故保持）；其余未知值 → 省略整行
// （不兜底直出）。
const MOMENT_KIND_CN = {
  CURRENT_USER_ERROR: "你信里的句子",
  RESOURCE_PRACTICE: "资源练习",
};

export function showMoments(list) {
  momentsBox.textContent = "";
  // rd-4 指路行（9.12-23 乙案表达）：批注开着时写信区上方一句话——
  // 纯表达不改路由；开着才显，空组与收场同隐
  const guide = document.getElementById("reply-guide");
  if (guide) {
    guide.hidden = !list.some((m) => m.lifecycle_state === "AWAITING_USER");
  }
  // R-1R（⑧ 8.2.2）：无批注的轮次不再在信流里挂空态横幅——空态是读数
  // 块的答法，不是信流的；信流只放信与批注。
  if (!list.length) {
    return;
  }
  // R-1V：批注递入动效只在新批注组到达时播一次——轮询的每次重渲染
  // 同 key 静帧（key = 本组批注 id 列），不重演不闪。
  const noteKey = list.map(
    (m) => String(m.id || m.focus_target_id)).join("|");
  const arrive = noteKey !== momentsBox.dataset.noteKey;
  momentsBox.dataset.noteKey = noteKey;
  for (const m of list) {
    const card = document.createElement("div");
    card.className = "note-paper" + (arrive ? " note-paper--enter" : "");
    const head = document.createElement("div");
    head.className = "note-head";
    head.appendChild(inkIcon("note"));
    const b = document.createElement("b");
    b.textContent = "批注：" + (m.title || m.focus_target_id);
    head.appendChild(b);
    card.appendChild(head);
    const status = document.createElement("div");
    status.className = "noteline";
    status.textContent = m.status_cn || m.lifecycle_state;
    card.appendChild(status);
    const kindCn = MOMENT_KIND_CN[m.kind];
    if (kindCn) {
      const kind = document.createElement("div");
      kind.className = "noteline";
      kind.textContent = kindCn;
      card.appendChild(kind);
    }
    if (m.last_attempt_feedback) {
      // W-6: the verdict survives a refresh — the ro current card carries
      // the moment's latest durable evaluation outcome
      showResultStrip(card, m.last_attempt_feedback);
    }
    if (m.lifecycle_state === "AWAITING_USER") {
      // the W-2/W-3 reply face: a moment waiting for the user offers the
      // attempt box (their own English sentence, judged) and the skip.
      // rd-4 手写批注层：等回应的卡带红笔圈线（锚行外包伪元素椭圆，
      // 静态形随卡入场一次；收场即摘——9.12-23）
      card.classList.add("circled");
      addReplyControls(card);
    }
    momentsBox.appendChild(card);
  }
}

export function addReplyControls(card) {
  // R-1R（⑧ 8.2.10）：回应面开启时的卡内指路行——回应写在这张批注上，
  // 不是下面的信纸（rd-2：作答→回应族）。
  const guide = document.createElement("div");
  guide.className = "noteline guide";
  guide.textContent = "回应写在这张批注上（不是下面的信纸）。";
  card.appendChild(guide);
  const row = document.createElement("div");
  row.className = "replyrow";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "replytext";
  input.autocomplete = "off";
  input.placeholder = "用英语写一句试试……";
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "btn btn--send";
  submit.textContent = "寄出回应";
  submit.addEventListener("click", () => submitAttempt(card, input));
  row.appendChild(input);
  row.appendChild(submit);
  card.appendChild(row);
  // W-6: the three help arms SM §1 names, as pencil links at the note's
  // tail — the words map onto the runtime's ASK_HINT / ASK_ANSWER /
  // ASK_EXPLANATION and nothing else（R-1R 起三词同性：提示 / 答案 /
  // 讲解；busy / seen 词族：取提示中…… / 已看提示 ……）
  const help = document.createElement("div");
  help.className = "replyrow";
  help.appendChild(helpButton("提示", "hint", "取提示中……", "已看提示", card));
  help.appendChild(helpButton("答案", "reveal", "取答案中……", "已看答案", card));
  help.appendChild(helpButton("讲解", "explanation", "取讲解中……", "已看讲解", card));
  card.appendChild(help);
  // W-2: the skip — a faint small link under the help arms; the moment's
  // lock releases through the runtime's own reply entry, nothing else.
  // rd-2：跳过 → 搁置族（「先搁着」）。
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "btn btn--faint";
  skip.textContent = "先搁着";
  skip.addEventListener("click", () =>
    postReply(card, { control: "skip" }, "搁置中……", "先搁着了——回头再拾。"));
  card.appendChild(skip);
}

function helpButton(label, control, busyText, doneNote, card) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn";
  button.textContent = label;
  button.addEventListener("click", () => {
    if (control === "reveal" &&
        !confirmDialog("看了答案，完整说法就摆在眼前——看过之后仍可回应。要看吗？")) {
      return;
    }
    postReply(card, { control: control }, busyText, doneNote);
  });
  return button;
}

function disarmMomentCard(card) {
  for (const row of Array.from(card.querySelectorAll(".replyrow"))) {
    row.remove();
  }
  // the guide line belongs to the reply face: it leaves with the controls
  // and comes back with them (never duplicated on a re-arm)
  for (const note of Array.from(card.querySelectorAll(".guide"))) {
    note.remove();
  }
}

// 批注生命周期词的界面读法（rd-2：作答→回应族；AWAITING_USER → 等你
// 回应；未列出的词不伪装翻译——原样小字呈现。服务端 status_cn 词面
// 已随 rd-2 处置刀同改「等你回应」，语气宪法第 6 条称你不称您全站归一）。
const LIFECYCLE_CN = {
  AWAITING_USER: "等你回应",
};

function readReplyAnswer(card, data) {
  // the reply result's own words, never a fabricated one: the new state
  // plus the feedback verdict (as the W-6 result strip) when the reply
  // carried one
  disarmMomentCard(card);
  card.appendChild(document.createElement("br"));
  const b = document.createElement("b");
  b.textContent = data.moment_state === "AWAITING_USER"
    ? "再试一回？"
    : "本次回应已收下";
  card.appendChild(b);
  card.appendChild(document.createTextNode(
    " · 状态 " + (LIFECYCLE_CN[data.moment_state] || data.moment_state || "未知")));
  if (data.feedback !== null && data.feedback !== undefined) {
    showResultStrip(card, data.feedback);
  }
  if (data.moment_state === "AWAITING_USER") {
    // the moment lives on (a miss re-prompts, an authorized reveal leaves
    // the post-reveal optional attempt open): the user can retry or skip
    addReplyControls(card);
  } else {
    // rd-4 两态可分（9.12-23）：现役两臂同落 .skipped 改为分臂——
    // 成功族（SUCCESS / ALTERNATIVE_SUCCESS）= 盖戳完成态：圈线摘下、
    // #22 stamp 同枚印记按上（stamp-press 复用，零新动效）；搁置与
    // 负值收场 = 淡出态（skipped 现役原样）。守恒律：一卡至多一处
    // 手迹——盖戳落地时圈线已离场。
    const word = String(data.feedback || "").split("（")[0];
    card.classList.remove("circled");
    if (word === "SUCCESS" || word === "ALTERNATIVE_SUCCESS") {
      card.classList.add("settled");
      const stamp = inkIcon("stamp");
      stamp.classList.add("card-stamp", "stamp-press");
      card.appendChild(stamp);
    } else {
      card.classList.add("skipped");
    }
  }
  // rd-4 指路行随收场同步：批注还开着（再试一回）则留，收场则隐
  const guide = document.getElementById("reply-guide");
  if (guide) guide.hidden = data.moment_state !== "AWAITING_USER";
}

async function postReply(card, payload, busyText, doneNote) {
  // W-6: one reply path for all five control words — the busy strip goes
  // up before the fetch and every control is disabled, so the multi-second
  // model round trip is never silent; a failed fetch (network gone, a
  // non-2xx) is one human line, and the card rearms either way
  setReplyBusy(card, true, busyText);
  try {
    const data = await fetchTeachingReply(payload);
    // 拒收面（200 + accepted:false，或 400/500）都带 error 句——一行人话，
    // 与拆分前 status 臂与 accepted 臂的合并等价（两臂回退词在服务端
    // 实际形状下不可区分，统一用没送到句；见 spec ⑦ 等价注记）。
    if (!data.accepted) {
      addLine("failure", data.error || "请求没送到——再试一次。");
      return;
    }
    addLine("system", doneNote);
    if (data.delivery_text) {
      // cs-0：交付文本是系统组装的批注（语料的提示阶梯 / 揭示形 / 讲解），
      // 不再以角色的信行入流——落在批注卡内作为系统行（note-paper 家族
      // 的 .noteline，与卡头状态行同形），信流里不出现教学文本。
      const note = document.createElement("div");
      note.className = "noteline";
      note.textContent = data.delivery_text;
      card.appendChild(note);
    }
    readReplyAnswer(card, data);
  } catch {
    addLine("failure", "请求没送到——再试一次。");
  } finally {
    setReplyBusy(card, false);
  }
}

async function submitAttempt(card, input) {
  const text = input.value.trim();
  if (!text) return;
  await postReply(card, { control: "attempt", text: text }, "批改中……",
                  "回应已寄出。");
}

// 9/10 的仪表面工厂：meter-row（kv/kvgroup/kvtitle）与 empty-state（note）。
// F-G2 起空态与失败态收拢到 state-banner（#14）：这两个入口保留签名、
// 内部一律委托——面板的空/失败两态不再各自硬编码。委托语义是「面板槽
// = 该状态」（先清空再挂）：loading 先行的拉取失败不会两态并存。
export function diagEmpty(box, word) {
  box.textContent = "";
  box.appendChild(stateBanner("empty", { text: word || "暂无数据" }));
}

export function diagError(box, message, retry) {
  box.textContent = "";
  box.appendChild(stateBanner("error",
    { text: "读取失败：" + message, retry: retry }));
}

export function diagLine(box, label, value) {
  const row = document.createElement("div");
  row.className = "kv";
  const b = document.createElement("b");
  b.textContent = label + "：";
  row.appendChild(b);
  // R-1R: the value may be a Node (a humanized timestamp with its ISO
  // tooltip, a bilingual word pair); a plain value stays a bare text node
  if (value instanceof Node) row.appendChild(value);
  else row.appendChild(document.createTextNode(String(value)));
  box.appendChild(row);
}

export function diagGroup(box, title) {
  const g = document.createElement("div");
  g.className = "kvgroup";
  const b = document.createElement("b");
  b.className = "kvtitle";
  if (title instanceof Node) b.appendChild(title);
  else b.textContent = title;
  g.appendChild(b);
  box.appendChild(g);
  return g;
}

// 13. brand-mark：品牌印记——几何唯一出处是 index.html 的
// <template id="brand-mark-source">（信封 + 封蜡，内联 SVG），本工厂
// 克隆模板并落尺寸变体（--sm 品牌条 / --lg 开张屏；默认 30px）。
// 零外链：模板就是页面里的一段 svg 标记，无 http(s)、无 data URI、
// 无任何资源取用——源码里连 SVG 命名串都不需要（HTML 原生解析 svg）。
export function brandMark(variant) {
  const svg = document.getElementById("brand-mark-source")
    .content.firstElementChild.cloneNode(true);
  if (variant) svg.classList.add("brandmark--" + variant);
  return svg;
}

// 把品牌印记装进壳上的插槽（<span data-brand-mark="sm|lg|">——空值落
// 默认尺寸）；DOMContentLoaded 时由 app.js 调一次。
export function installBrandMarks() {
  for (const slot of document.querySelectorAll("[data-brand-mark]")) {
    slot.replaceWith(brandMark(slot.dataset.brandMark || undefined));
  }
}

// 22. icon-set（R-1V）：自绘墨线内联 SVG 图标集——几何唯一出处是
// index.html 的 <template id="icon-set-source">（20×20 网格、笔重 1.5、
// 圆角端点；与 #13 同法：HTML 原生解析 svg，零外链、源码无命名串）。
// 工厂 inkIcon(name) 从模板内容里查一枚克隆并摘掉 id（克隆体不带重复
// id）；installIcons() 把 <span data-icon="…"> 插槽换成克隆（brandMark
// 同法），插槽自身的 class 过继给克隆体（语境尺寸/色调随插槽）。
export function inkIcon(name) {
  const template = document.getElementById("icon-set-source");
  const source = template.content.querySelector("#icon-" + name);
  if (!source) return document.createElement("span");
  const icon = source.cloneNode(true);
  icon.removeAttribute("id");
  return icon;
}

export function installIcons() {
  for (const slot of document.querySelectorAll("[data-icon]")) {
    const icon = inkIcon(slot.dataset.icon);
    if (slot.className) {
      icon.setAttribute("class", slot.className + " inkicon");
    }
    slot.replaceWith(icon);
  }
}

// 14. state-banner：读数面板三态（loading / empty / error）的唯一答法。
// loading 尾点呼吸是全页唯一动效（reduced-motion 下静止，见 #14 契约）；
// error 的人话句后跟一枚「重试」赭红链接（link-btn 的 --pencil 变体），
// 回调由调用方注入——只重拉本面板，不连带整屏。
export function stateBanner(kind, opts) {
  const options = opts || {};
  const defaults = { loading: "取信中…", empty: "暂无数据",
                     error: "读取失败" };
  const box = document.createElement("div");
  box.className = "state-banner state-banner--" + kind;
  // R-1V：空态配墨线小图（⑨-4 lamp——未点亮的灯；图是装饰，诚实句
  // 仍是主体，aria-hidden 由模板带出）
  if (kind === "empty") box.appendChild(inkIcon("lamp"));
  box.appendChild(document.createTextNode(
    options.text || defaults[kind] || "暂无数据"));
  if (kind === "error" && typeof options.retry === "function") {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "btn btn--pencil";
    retry.textContent = "重试";
    retry.addEventListener("click", options.retry);
    box.appendChild(retry);
  }
  return box;
}

// 15. word-card：点词卡——信件文本分片 + 窗口查词 + 信笺浮层（p-1）。
// 分片 letterWords 是惰性的：.say 的文本节点切成 span.word + 原样空白
// 文本节点，整段 textContent 逐字不变（信笺结构钉不动）。查询窗口
// wordWindows 以点击词为中心取 1–3 词，每种窗长把含点击词的对齐都试
// 一遍（长窗优先、去重）；查询串 normalizeWordQuery 剥边标点 + 小写化，
// 与服务端同一套边界字符。浮层 showWordCard 挂 body、贴点击点收进
// 视口；关闭 = 点卡外或「收起」（closeWordCard），无 busy——命中即显，
// miss 按契约静默。
// 两条登记（p-1 评审）：①命中词可以不含被点词——点击某词的 3 词窗若
// 含更长 lemma，出的是长窗的卡（点 "Anyway," 可能出 "I see" 的卡）；
// 是否收紧为「命中须含被点 token」属产品裁决，Revisit。②词表 100 条
// lemma 中 25 条超 3 词窗（最长 6 词）——点词对这些目标结构性不可达，
// 窗口加宽或句级匹配是 Revisit 方向，定量以词表实测为准。
const WORD_EDGE_CHARS = "\"'`.,;:!?()[]{}<>…—–-“”‘’《》「」*_/\\|=+~^%$#@&";

// W-8 前端兜底：模型偶尔仍带 markdown 记号，信笺把三记号排版出来——
// **粗** / *斜* / `码`；分段用正则，未配对或内容以空白开头/结尾的不
// 配对，原样直出。记号内照旧 span.word 分片，只是外包 strong/em/code；
// 全程纯节点拼装（老纪律：用户的字永远不进标记）。无记号文本走的分支
// 与旧实现逐字节同构（历史回填与 #15 触发面零扰动；`*` 仍在
// WORD_EDGE_CHARS）。
const LETTER_MARKS =
  /(\*\*[^*\s](?:[^*]*[^*\s])?\*\*|\*[^*\s](?:[^*]*[^*\s])?\*|`[^`]+`)/;

function appendWordSpans(parent, text) {
  for (const part of String(text).split(/(\s+)/)) {
    if (!part) continue;
    if (/^\s+$/.test(part)) {
      parent.appendChild(document.createTextNode(part));
      continue;
    }
    const span = document.createElement("span");
    span.className = "word";
    span.textContent = part;
    parent.appendChild(span);
  }
}

export function letterWords(text) {
  const frag = document.createDocumentFragment();
  const segments = String(text).split(LETTER_MARKS);
  for (let i = 0; i < segments.length; i += 1) {
    const seg = segments[i];
    if (!seg) continue;
    if (i % 2 === 0) {
      appendWordSpans(frag, seg);
      continue;
    }
    let tag = "em";
    let inner = seg.slice(1, -1);
    if (seg.startsWith("**")) {
      tag = "strong";
      inner = seg.slice(2, -2);
    } else if (seg.startsWith("`")) {
      tag = "code";
      inner = seg.slice(1, -1);
    }
    const el = document.createElement(tag);
    appendWordSpans(el, inner);
    frag.appendChild(el);
  }
  return frag;
}

export function normalizeWordQuery(text) {
  return String(text).split(/\s+/).map((word) => {
    let a = 0;
    let b = word.length;
    while (a < b && WORD_EDGE_CHARS.includes(word[a])) a += 1;
    while (b > a && WORD_EDGE_CHARS.includes(word[b - 1])) b -= 1;
    return word.slice(a, b).toLowerCase();
  }).filter(Boolean).join(" ");
}

export function wordWindows(words, index) {
  const queries = [];
  const seen = new Set();
  for (const size of [3, 2, 1]) {
    for (let start = Math.max(0, index - size + 1);
         start <= index && start + size <= words.length; start += 1) {
      const query =
        normalizeWordQuery(words.slice(start, start + size).join(" "));
      if (query && !seen.has(query)) {
        seen.add(query);
        queries.push(query);
      }
    }
  }
  return queries;
}

export function wordCard(data) {
  const card = document.createElement("div");
  card.className = "word-card";
  const lemma = document.createElement("b");
  lemma.className = "wc-lemma";
  lemma.textContent = String(data.lemma || "");
  card.appendChild(lemma);
  if (data.pos) {
    const pos = document.createElement("span");
    pos.className = "wc-pos";
    pos.textContent = data.pos;
    card.appendChild(pos);
  }
  const forms = data.forms || [];
  if (forms.length) {
    const row = document.createElement("div");
    row.className = "wc-forms";
    row.textContent = forms
      .map((f) => f.written + "（" + f.form_type + "）")
      .join(" · ");
    card.appendChild(row);
  }
  for (const sense of data.senses || []) {
    if (sense.zh) {
      const zh = document.createElement("p");
      zh.className = "wc-zh";
      zh.textContent = sense.zh;
      card.appendChild(zh);
    }
    if (sense.en) {
      const en = document.createElement("p");
      en.className = "wc-en";
      en.textContent = sense.en;
      card.appendChild(en);
    }
    for (const example of sense.examples || []) {
      const ex = document.createElement("p");
      ex.className = "wc-example";
      ex.textContent = example;
      card.appendChild(ex);
    }
  }
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn btn--faint";
  close.textContent = "收起";
  close.addEventListener("click", closeWordCard);
  card.appendChild(close);
  return card;
}

let openCard = null;
let cardCloser = null;

export function closeWordCard() {
  if (cardCloser !== null) {
    document.removeEventListener("click", cardCloser);
    cardCloser = null;
  }
  if (openCard !== null) {
    openCard.remove();
    openCard = null;
  }
}

export function showWordCard(at, data) {
  closeWordCard();
  const card = wordCard(data);
  document.body.appendChild(card);
  const maxLeft = window.scrollX + document.documentElement.clientWidth -
    card.offsetWidth - 12;
  const maxTop = window.scrollY + window.innerHeight -
    card.offsetHeight - 12;
  card.style.left =
    Math.max(window.scrollX + 6, Math.min(at.pageX, maxLeft)) + "px";
  card.style.top =
    Math.max(window.scrollY + 6, Math.min(at.pageY, maxTop)) + "px";
  openCard = card;
  cardCloser = (event) => {
    if (event.target !== card && !card.contains(event.target)) {
      closeWordCard();
    }
  };
  document.addEventListener("click", cardCloser);
}

// 16. field：编辑面一行式表单行（p-3）。label 包裹控件——点名牌即聚焦；
// 控件由调用方 createElement（input/select），字面样式随 #16 契约（唯一
// 出处 components.css）。名牌文字一律惰性（R-1R 起名牌可以是 Node——
// 中英并置的「中文 + 等宽小字」片，仍逐片 textContent）。
export function fieldRow(labelText, control) {
  const row = document.createElement("label");
  row.className = "field";
  const name = document.createElement("span");
  name.className = "fieldname";
  if (labelText instanceof Node) name.appendChild(labelText);
  else name.textContent = labelText;
  row.appendChild(name);
  row.appendChild(control);
  return row;
}

// 17. chip：词表词选择片（p-3）。可点选（on 态、点击回报调用方，选中态
// 由调用方重渲染）与只读徽标（--badge，disabled——非交互）两种用法；
// 词即内容，文字一律惰性（R-1R 起 opts.cn 给中文名牌：中文在前 + 英文
// 原词等宽小字在后，⑧ 8.3 存储词表值中英并置）。
export function chip(word, opts) {
  const options = opts || {};
  const el = document.createElement("button");
  el.type = "button";
  el.className = "chip" + (options.on ? " chip--on" : "") +
    (options.badge ? " chip--badge" : "");
  if (options.cn) {
    el.appendChild(document.createTextNode(String(options.cn) + " "));
    const en = document.createElement("span");
    en.className = "rawtag";
    en.textContent = String(word);
    el.appendChild(en);
  } else {
    el.textContent = String(word);
  }
  if (options.badge) {
    el.disabled = true;
  } else if (typeof options.onClick === "function") {
    el.addEventListener("click", options.onClick);
  }
  return el;
}

// 18/19/20（R-1）：壳导航三件的接线面。dock 的项点击回报调用方
//（wireNavdock）、当前态由 markNavdock 落 --on + aria-current；
// section-tabs 的点击与左右箭头都回报调用方（wireSectionTabs——roving
// tabindex：选中项 tabindex 0、其余 -1，焦点随箭头走，键盘序 = 视觉序），
// 选中态由 markSectionTabs 落 aria-selected；space-header 的节名槽联动
// 是 sectionLabel（textContent）。一切文字 textContent。
export function wireNavdock(onSelect) {
  for (const item of document.querySelectorAll(".navdock-item")) {
    item.addEventListener("click", () => onSelect(item.dataset.space));
  }
}

export function markNavdock(name) {
  for (const item of document.querySelectorAll(".navdock-item")) {
    const on = item.dataset.space === name;
    item.classList.toggle("navdock-item--on", on);
    if (on) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
}

export function wireSectionTabs(list, onSelect) {
  const tabs = Array.from(list.querySelectorAll("[role=tab]"));
  list.addEventListener("keydown", (event) => {
    const at = tabs.indexOf(document.activeElement);
    if (at < 0) return;
    let next = null;
    if (event.key === "ArrowRight") next = (at + 1) % tabs.length;
    if (event.key === "ArrowLeft") {
      next = (at - 1 + tabs.length) % tabs.length;
    }
    if (next === null) return;
    event.preventDefault();
    tabs[next].focus();
    onSelect(tabs[next].dataset.section);
  });
  for (const tab of tabs) {
    tab.addEventListener("click", () => onSelect(tab.dataset.section));
  }
}

export function markSectionTabs(list, name) {
  for (const tab of list.querySelectorAll("[role=tab]")) {
    const on = tab.dataset.section === name;
    tab.classList.toggle("section-tab--on", on);
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
  }
}

export function sectionLabel(header, text) {
  const slot = header.querySelector(".spacehead-sec");
  if (slot) slot.textContent = text;
}

// rd-1 入场编排（spec ⑨-5 逐行落墨；置于 #21 之前——r1r 的「工厂尾部
// 无 querySelectorAll」无手风琴钉扫 disclosure 之后的文件尾，本编排
// 不是工厂、不越出自己的容器）：IntersectionObserver 只做一件事
// ——[data-reveal] 容器进入视口时落一个类（.is-revealed），错步序号
// --i 也只在这里计算（步长 REVEAL_STAGGER_MS 40ms、只给前
// REVEAL_STAGGER_MAX 8 项——总封顶 320ms；CSS 侧公式
// calc(var(--i, 0) * 40ms) 消费它，第 9 项起无 --i 即无延迟）。
// reduced-motion 双面纪律的 JS 半区：CSS 媒体查询管不到 JS 编排，
// 这里自己听 matchMedia——reduce 即刻落定全部容器（断开观察、不留
// 在飞动画），翻转事件同样接住。
const REDUCED_MOTION = window.matchMedia(
  "(prefers-reduced-motion: reduce)");
const REVEAL_STAGGER_MS = 40;
const REVEAL_STAGGER_MAX = 8;

export function wireReveal(root) {
  const containers = Array.from(root.querySelectorAll("[data-reveal]"));
  const settle = (container) => {
    container.classList.add("is-revealed");
    let index = 0;
    for (const item of container.querySelectorAll(
        ":scope > .sec, :scope > section > .sec, :scope .panel-grid > .sec")) {
      if (index < REVEAL_STAGGER_MAX) {
        item.style.setProperty("--i", String(index));
      }
      index += 1;
    }
  };
  if (REDUCED_MOTION.matches) {
    for (const container of containers) settle(container);
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        settle(entry.target);
        observer.unobserve(entry.target);
      }
    }
  });
  for (const container of containers) observer.observe(container);
  REDUCED_MOTION.addEventListener("change", () => {
    if (REDUCED_MOTION.matches) {
      observer.disconnect();
      for (const container of containers) settle(container);
    }
  });
}

// ── mc-1: 信封沓的排布半区（app.js 禁 .style，custom props 只在此落）
// ────────────────────────────────────────────────────────────────────
// 位置：在 #21 disclosure 之前（r1r 的「工厂尾部无 querySelectorAll」
// 无手风琴钉扫 disclosure 之后的文件尾——wireReveal 同例，含查询的
// 非手风琴件都排在折叠工厂之前）。
// 沓形几何：每封的视觉位序 --env-i（驱动 top 的错位叠放）/ 叠放序
// --env-z（沓首最高）/ 让位 stagger --env-delay（步长 20ms、封顶
// 60ms——transition 260ms + 60ms = 总封顶 320ms，简报 §5）由 data-order
// 的排名重算；rotate/translateX 的确定性微扇（stamp_key 派生值）由
// 工厂 envelopeCard 落，此处只读不改。首排时 delay 恒 0（排名未变），
// 预览重排才起 stagger。reduced-motion 由库尾总降级块归零（0.01ms
// 即终、transitionend 仍到——本排布不依赖事件，双面降级成立）。
export function layoutEnvelopeStack(stack) {
  const envelopes = Array.from(stack.querySelectorAll(".env[data-id]"));
  const ordered = envelopes.slice().sort(
    (a, b) => (Number(a.dataset.order) || 0) - (Number(b.dataset.order) || 0));
  const count = ordered.length;
  stack.style.setProperty("--env-n", String(count));
  ordered.forEach((env, position) => {
    env.style.setProperty("--env-i", String(position));
    env.style.setProperty("--env-z", String(count - position));
    const before = env.dataset.pos === undefined
      ? position : Number(env.dataset.pos);
    const delay = Math.min(Math.abs(before - position) * 20, 60);
    env.style.setProperty("--env-delay", delay + "ms");
    env.dataset.pos = String(position);
  });
}

// 一封信封的 DOM（mc-1）：收件人位（角色名）+ 一行简介 + 右上角专属
// 邮票（变体类由 app.js 从 stamp_key 确定性派生）+ 动作行（对话 ·
// 档案 · 编辑——下划线文字链接，形态走 #1 的 --pencil）；当前通信的
// 一封带 .env--current 并落「当前」邮戳角标（components.css 的
// .env-mark——朱砂真实状态事件，每沓恰一枚）。微扇的 rotate/
// translateX 在此落 custom props（确定性值由调用方算好传入）。一切
// 文字 textContent——角色名与简介是用户自己的散文，绝不进标记。
export function envelopeCard(item, opts) {
  const options = opts || {};
  const env = document.createElement("article");
  env.className = "env" + (options.current ? " env--current" : "");
  env.dataset.id = String(item.character_id);
  env.tabIndex = 0;
  env.style.setProperty("--env-rot", options.rot || "0deg");
  env.style.setProperty("--env-dx", options.dx || "0px");
  const stamp = document.createElement("span");
  stamp.className = ("env-stamp " + (options.stampClasses || "")).trim();
  const initial = document.createElement("span");
  initial.className = "env-stamp-ini";
  initial.textContent = String(item.name || "").charAt(0);
  stamp.appendChild(initial);
  env.appendChild(stamp);
  const to = document.createElement("p");
  to.className = "env-to";
  const toWord = document.createElement("span");
  toWord.className = "env-to-word";
  toWord.textContent = "致";
  to.appendChild(toWord);
  const name = document.createElement("b");
  name.className = "env-name";
  name.textContent = String(item.name || "");
  to.appendChild(name);
  env.appendChild(to);
  const line = document.createElement("p");
  line.className = "env-line";
  line.textContent = String(item.identity_line || "");
  env.appendChild(line);
  const actions = document.createElement("p");
  actions.className = "env-actions";
  const act = (word, cls, handler) => {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "btn btn--pencil " + cls;
    link.textContent = word;
    link.addEventListener("click", (event) => {
      event.stopPropagation();
      handler(env);
    });
    actions.appendChild(link);
    return link;
  };
  act("对话", "env-act-talk", () => {
    if (typeof options.onTalk === "function") options.onTalk();
  });
  act("档案", "env-act-dossier", () => {
    if (typeof options.onDossier === "function") options.onDossier();
  });
  act("编辑", "env-act-edit", () => {
    if (typeof options.onEdit === "function") options.onEdit(env);
  });
  env.appendChild(actions);
  if (options.current) {
    const mark = document.createElement("span");
    mark.className = "env-mark";
    const word = document.createElement("span");
    word.textContent = "当前";
    mark.appendChild(word);
    env.appendChild(mark);
  }
  return env;
}

// 21. disclosure（折叠组，R-1R；⑧ 8.2.9 契约形）：组头行（名称 + 计数 +
// 两枚示例弱化小字）即开关，内容区默认收。不得手风琴互斥、不得嵌套、
// 不得图标外链。opts：name（名称，textContent）/ count（计数，保留在
// 组头）/ examples（两枚示例）/ content（一次性收养进内容区的既有节点）
// / onFirstExpand（第一次展开时回调一次——惰性拉取的挂载点）。返回
// { root, head, body, setOpen, isOpen }——筛框等调用方经 setOpen 驱动。
export function disclosure(opts) {
  const options = opts || {};
  const root = document.createElement("div");
  root.className = "disclosure";
  const head = document.createElement("button");
  head.type = "button";
  head.className = "disclosure-head";
  head.setAttribute("aria-expanded", "false");
  const marker = document.createElement("span");
  marker.className = "disclosure-marker";
  // R-1V：▸/▾ 字符标记换 #22 的自绘墨线 chevron——展开态不再换字符，
  // 由 --open 类驱动 SVG 旋转 90°（⑨-5；aria-expanded 语义不动）
  marker.appendChild(inkIcon("chevron"));
  head.appendChild(marker);
  const title = document.createElement("span");
  title.className = "disclosure-title";
  title.appendChild(document.createTextNode(String(options.name || "")));
  if (options.count !== undefined && options.count !== null) {
    title.appendChild(document.createTextNode("（" + options.count + "）"));
  }
  const examples = options.examples || [];
  if (examples.length) {
    title.appendChild(document.createTextNode("　"));
    const shown = document.createElement("span");
    shown.className = "disclosure-examples";
    shown.textContent = examples.join(" · ") + " …";
    title.appendChild(shown);
  }
  head.appendChild(title);
  root.appendChild(head);
  const body = document.createElement("div");
  body.className = "disclosure-body";
  body.hidden = true;
  if (options.content) body.appendChild(options.content);
  root.appendChild(body);
  let open = false;
  let openedOnce = false;
  function setOpen(next) {
    open = Boolean(next);
    body.hidden = !open;
    head.setAttribute("aria-expanded", open ? "true" : "false");
    root.classList.toggle("disclosure--open", open);
    if (open && !openedOnce) {
      openedOnce = true;
      if (typeof options.onFirstExpand === "function") {
        options.onFirstExpand(body);
      }
    }
  }
  head.addEventListener("click", () => setOpen(!open));
  return { root, head, body, setOpen, isOpen: () => open };
}

// rd-4 的浮层伙伴卡（#23）：cs-2 整体退役。工厂三件（卡片壳 + 浮层
// 开合）随档案全页视图拆除——点品牌条 who 块开的是整页档案（app.js
// 的 cs-2 模块，屏级形态，非浮层）；名册桩与 localStorage pick 一并
// 退役（真名由 /api/partner 的单一真源供给）。mc-1 的信封沓两工厂
// （layoutEnvelopeStack / envelopeCard）在 wireReveal 与 #21 之间
// ——见该处的位置注记。
