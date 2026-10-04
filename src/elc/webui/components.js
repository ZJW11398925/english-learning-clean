// components.js —— 组件工厂与教学卡的当场行为（F-G1）。
// 纪律：一切用户可见的文字只走 createElement + textContent——用户的
// 英语、模型的回复、面板读数永远是惰性文本，绝不进标记（XSS 面）。
// 每个工厂对应 docs/FRONTEND_SPEC.md ③ 的一行契约；类名的样式唯一
// 出处是 components.css。本文件是确认窗的唯一封装点（confirmDialog——
// fr-B 重铸为自绘纸墨确认窗，原生 window.confirm 退役）；对端点的
// 调用只走 api.js。

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

// 信纸节点（#4 letter 的 DOM 工厂，v2-2 自 addLine 抽出）：信流
// （addLine）与信档屏的展开读（app.js 的信档节）共用同一排印骨架
// 工厂——单一出处条款（⑤）：展开读不是第二份信件实现。
// v3-3：opts.hits = 本信的命中位图（段落一行、一行一词，服务端
// _letter_hit_rows 下发）——本函数按**原始段落序**消费：称呼行与落款
// 行也占位（它们不渲染 .say，其行被跳过即可），正文段对号入座；
// 位图缺席 = 全供性（现役行为）。用户信单段，行 [0]。
export function letterNode(cls, text, opts) {
  const options = opts || {};
  const rows = options.hits || null;
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
    say.appendChild(letterWords(text, rows ? rows[0] || null : null));
    paper.appendChild(say);
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
    let cursor = 0;   // 原始段落游标：称呼行吃掉 rows[0]
    if (salut !== null) {
      const row = document.createElement("p");
      row.className = "letter-salut";
      row.appendChild(letterWords(salut, rows ? rows[cursor] || null : null));
      node.appendChild(row);
      body = paragraphs.slice(1);
      cursor += 1;
    }
    const signBlock = signatureBlockOf(body);
    const signBase = cursor + signBlock.rest.length;
    body = signBlock.rest;
    for (const para of body) {
      const say = document.createElement("p");
      say.className = "say" + (isPostscript(para) ? " letter-ps" : "");
      say.appendChild(letterWords(para, rows ? rows[cursor] || null : null));
      cursor += 1;
      node.appendChild(say);
    }
    signBlock.lines.forEach((line, k) => {
      const sign = document.createElement("p");
      sign.className = "letter-sign";
      // 落款行在段落尾部：行号从倒数第 k 行取（lines 已是原始顺序）。
      const tail = rows ? rows[signBase + k] || null : null;
      sign.appendChild(letterWords(line, tail));
      node.appendChild(sign);
    });
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
  return node;
}

export function addLine(cls, text, opts) {
  const node = letterNode(cls, text, opts);
  messages.appendChild(node);
  // v2-2 触屏可发现性（8.2.2④ (a)）：最新一封信 = 唯一带弱底纹暗示的
  // 信（.letter--latest）——「当前可查」语义随信龄衰减，历史信静默。
  // 系统行/回执不参与（只有信件件两臂落标记）。
  if (cls === "user" || cls === "assistant") {
    for (const prev of Array.from(
        messages.querySelectorAll(".letter--latest"))) {
      prev.classList.remove("letter--latest");
    }
    node.classList.add("letter--latest");
  }
  scrollBottom();
  return node;
}

// 11. confirm-dialog（fr-B 重铸：自绘纸墨确认窗——原生 window.confirm
// 退役：浏览器级硬弹与纸墨体系零关系）。异步 Promise<boolean>——
// 确定 true；再想想 / 点雾 / Esc 一律 false（原生语义平移）。
// 开 = 纸雾淡入 + 面板升起（--dur-dialog-in）；合 = 面板褪下 + 纸雾
// 淡出（Esc 收起与确认收起对称，同一 finish 编排）；消息一律
// textContent（XSS 纪律）；层位 z 11/12 全站最上（⑩ 10.2）；Esc 走
// capture 闸门 + stopPropagation——只退本层，不惊动下层的词卡/沓
// （⑩ 10.4 同刀改行）。reduced-motion：JS 半区直切 + 库尾总降级双面。
export function confirmDialog(message) {
  return new Promise((resolve) => {
    const restoreFocusTo = document.activeElement;
    const scrim = document.createElement("div");
    scrim.className = "cfrm-scrim";
    const box = document.createElement("div");
    box.className = "cfrm";
    box.setAttribute("role", "alertdialog");
    box.setAttribute("aria-modal", "true");
    const text = document.createElement("p");
    text.className = "cfrm-msg";
    text.textContent = String(message);
    box.appendChild(text);
    const row = document.createElement("p");
    row.className = "cfrm-actions";
    const no = document.createElement("button");
    no.type = "button";
    no.className = "btn btn--faint";
    no.textContent = "再想想";
    const yes = document.createElement("button");
    yes.type = "button";
    yes.className = "btn btn--pencil";
    yes.textContent = "确定";
    row.appendChild(no);
    row.appendChild(yes);
    box.appendChild(row);
    document.body.appendChild(scrim);
    document.body.appendChild(box);
    let done = false;
    const finish = (answer) => {
      if (done) return;
      done = true;
      document.removeEventListener("keydown", onKey, true);
      const settle = () => {
        scrim.remove();
        box.remove();
        if (restoreFocusTo && restoreFocusTo.isConnected) {
          restoreFocusTo.focus();
        }
        resolve(answer);
      };
      if (REDUCED_MOTION.matches) {
        settle();
        return;
      }
      scrim.classList.add("cfrm-scrim--out");
      box.classList.add("cfrm--out");
      box.addEventListener("animationend", (event) => {
        if (event.animationName === "paper-fold") settle();
      });
      setTimeout(settle, 480);   // 保险丝（同沓家对账纪律）
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        finish(false);
      } else if (event.key === "Enter") {
        event.preventDefault();
        finish(true);
      }
    };
    no.addEventListener("click", () => finish(false));
    yes.addEventListener("click", () => finish(true));
    scrim.addEventListener("click", () => finish(false));
    document.addEventListener("keydown", onKey, true);
    yes.focus();
  });
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
// 原话随后——⑧ 8.2.10 定稿）。v3-1 槽位化：卡内**至多一条**——新条来
// 时更新既有节点（类名 + 文本原位改写），不再 append 累积（P0-2 的
// 膨胀源之一）。PARTIAL（◐）伴随一条方向指引（A3）：绑「提示」按钮
// 的既有词族，指引读者把整句说完或再看一眼提示——指引行同样至多
// 一条，PARTIAL 退场即摘。
export function showResultStrip(card, feedback) {
  const symbol = outcomeSymbol(feedback);
  const head = OUTCOME_VERDICT_CN[String(feedback).split("（")[0]] || "";
  let strip = card.querySelector(".resultstrip");
  if (!strip) {
    strip = document.createElement("div");
    // 结果条排在回试行（.note-state）之前——8.2.10 的卡内槽位序。
    const state = card.querySelector(".note-state");
    if (state) state.before(strip);
    else card.appendChild(strip);
  }
  strip.className = "resultstrip " +
    (symbol === "✓" ? "ok" : symbol === "✗" ? "miss" : "part");
  strip.textContent = head ? head + " · " + feedback : feedback;
  showPartialGuide(card, strip, symbol === "◐");
}

// A3（v3-1）：PARTIAL 的人话方向指引行——「答了一半」的下一步读法，
// 绑既有「提示」按钮的词族（不引入新控件）。至多一条，随结果条走。
const PARTIAL_GUIDE_CN =
  "答了一半——目标表达已经在句子里了，把整句说完，或点「提示」再看一眼。";

function showPartialGuide(card, strip, on) {
  let line = card.querySelector(".partialguide");
  if (!on) {
    if (line) line.remove();
    return;
  }
  if (!line) {
    line = document.createElement("div");
    line.className = "partialguide";
    if (strip) strip.after(line);
    else card.appendChild(line);
  }
  line.textContent = PARTIAL_GUIDE_CN;
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
  // 纯表达不改路由；开着才显，空组与收场同隐。v3-a 同步半：笔搁触发
  // 条的文案态切同一句（收起态的批注指路，8.2.2⑤）——路由不变。
  const guide = document.getElementById("reply-guide");
  if (guide) {
    guide.hidden = !list.some((m) => m.lifecycle_state === "AWAITING_USER");
  }
  syncDockTriggerNote(guide ? !guide.hidden : false);
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
  // W-2: the skip — a faint small link in its own row under the help
  // arms; the moment's lock releases through the runtime's own reply
  // entry, nothing else. rd-2：跳过 → 搁置族（「先搁着」）。v3-1（B2）：
  // 「先搁着」并入拆装组（.skiprow 与 .replyrow 同规——disarmMomentCard
  // 一并拆），守恒律：卡内至多一枚（P0-2 的漏拆修复）。
  for (const row of Array.from(card.querySelectorAll(".skiprow"))) {
    row.remove();
  }
  const skiprow = document.createElement("div");
  skiprow.className = "skiprow";
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "btn btn--faint";
  skip.textContent = "先搁着";
  skip.addEventListener("click", () =>
    postReply(card, { control: "skip" }, "搁置中……", "先搁着了——回头再拾。"));
  skiprow.appendChild(skip);
  card.appendChild(skiprow);
}

function helpButton(label, control, busyText, doneNote, card) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn";
  button.textContent = label;
  button.addEventListener("click", async () => {
    if (control === "reveal" &&
        !(await confirmDialog("看了答案，完整说法就摆在眼前——看过之后仍可回应。要看吗？"))) {
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
  // v3-1（B2）：skip 与求助行同规——同一拆装契约，至多一枚。
  for (const row of Array.from(card.querySelectorAll(".skiprow"))) {
    row.remove();
  }
  // the guide line belongs to the reply face: it leaves with the controls
  // and comes back with them (never duplicated on a re-arm)
  for (const note of Array.from(card.querySelectorAll(".guide"))) {
    note.remove();
  }
}

// v3-1（B3/B4）：卡内交付的分派与收纳。REVEAL 永远走独立区块
// .note-answer（「参考答案」标签 + 左缘界尺与信尾视觉断开——never
// 混进回信文本）；至多一块，答案永远最新（原位改写）。HINT /
// EXPLANATION / RETRY 走 .note-delivery 容器：最新一条 .noteline 显式
// （cs-0 契约形不变），更早的一条收进 <details class="note-history">
// 折叠——多轮求助不膨胀。一切文字 textContent（XSS 惰性纪律不变）。
const HISTORY_LABEL_CN = "已看过的提示与讲解";

function noteDelivery(card, text, kind) {
  if (kind === "REVEAL") {
    let block = card.querySelector(".note-answer");
    if (!block) {
      block = document.createElement("div");
      block.className = "note-answer";
      const delivery = card.querySelector(".note-delivery");
      if (delivery) delivery.after(block);
      else card.appendChild(block);
    }
    block.textContent = "";
    const tag = document.createElement("b");
    tag.textContent = "参考答案";
    block.appendChild(tag);
    block.appendChild(document.createTextNode(" · " + text));
    return;
  }
  let host = card.querySelector(".note-delivery");
  if (!host) {
    host = document.createElement("div");
    host.className = "note-delivery";
    const answer = card.querySelector(".note-answer");
    if (answer) answer.before(host);
    else card.appendChild(host);
  }
  const current = host.querySelector(":scope > .noteline");
  if (current) {
    let history = host.querySelector(":scope > .note-history");
    if (!history) {
      history = document.createElement("details");
      history.className = "note-history";
      const summary = document.createElement("summary");
      summary.textContent = HISTORY_LABEL_CN + "（1）";
      history.appendChild(summary);
      host.insertBefore(history, current);
    }
    const old = document.createElement("div");
    old.className = "noteline";
    old.textContent = current.textContent;
    history.appendChild(old);
    const count = history.querySelectorAll(":scope > .noteline").length;
    history.querySelector("summary").textContent =
      HISTORY_LABEL_CN + "（" + count + "）";
    // 槽位 replace 的另一半：旧行收进折叠后，显式行的原位必须摘除——
    // 否则折叠是复制、显式行照旧累积（活体探针抓到的第一版缺陷）。
    current.remove();
  }
  const note = document.createElement("div");
  note.className = "noteline";
  note.textContent = text;
  host.appendChild(note);
}

// 批注生命周期词的界面读法（rd-2：作答→回应族；AWAITING_USER → 等你
// 回应；未列出的词不伪装翻译——原样小字呈现。服务端 status_cn 词面
// 已随 rd-2 处置刀同改「等你回应」，语气宪法第 6 条称你不称您全站归一）。
// v3-d：CLOSED 补中文读法「已收场」（v31R 复测登记：收场后状态行曾
// 以英文原词裸出）。
const LIFECYCLE_CN = {
  AWAITING_USER: "等你回应",
  CLOSED: "已收场",
};

function readReplyAnswer(card, data) {
  // the reply result's own words, never a fabricated one: the new state
  // plus the feedback verdict (as the W-6 result strip) when the reply
  // carried one. v3-1（B1）槽位化：回试行写固定槽 .note-state——卡内
  // 至多一条，新状态原位改写，不再 append 累积（P0-2 膨胀源之二）。
  disarmMomentCard(card);
  let state = card.querySelector(".note-state");
  if (!state) {
    state = document.createElement("div");
    state.className = "note-state";
    card.appendChild(state);
  }
  state.textContent =
    (data.moment_state === "AWAITING_USER" ? "再试一回？" : "本次回应已收下") +
    " · 状态 " +
    (LIFECYCLE_CN[data.moment_state] || data.moment_state || "未知");
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
    // 手迹——盖戳落地时圈线已离场。v3-1：收场即摘 PARTIAL 指引行
    // （指引是「再答一次」的读法，收场后不再是可答态）。
    const word = String(data.feedback || "").split("（")[0];
    card.classList.remove("circled");
    showPartialGuide(card, null, false);
    if (word === "SUCCESS" || word === "ALTERNATIVE_SUCCESS") {
      card.classList.add("settled");
      const stamp = inkIcon("stamp");
      stamp.classList.add("card-stamp", "stamp-press");
      card.appendChild(stamp);
    } else {
      card.classList.add("skipped");
    }
  }
  // rd-4 指路行随收场同步：批注还开着（再试一回）则留，收场则隐；
  // v3-a 同步半：触发条文案态同拍归位。
  const guide = document.getElementById("reply-guide");
  if (guide) guide.hidden = data.moment_state !== "AWAITING_USER";
  syncDockTriggerNote(guide ? !guide.hidden : false);
}

// v3-a 笔搁触发条的文案态同步（8.2.2⑤）：批注开着（AWAITING_USER）时
// 收起态触发条**切换为**指路行原文（与 #reply-guide 同一拍、同一真源——
// showMoments/noteDelivery 两处落），其余时刻显「提笔 · 今日如何？」。
// v3-a 处置刀（评审 F-1）：切 = 双向——idle 与 note 互斥（首版只显
// note 不藏 idle，两文案拼接被 ellipsis 截断）。
// 元素缺席（旧壳）安全空操作。
function syncDockTriggerNote(awaiting) {
  const note = document.getElementById("dock-trigger-note");
  const idle = document.querySelector(".dock-trigger-idle");
  if (note) note.hidden = !awaiting;
  if (idle) idle.hidden = !!awaiting;
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
      // 不再以角色的信行入流——落在批注卡内，信流里不出现教学文本。
      // v3-1（B3/B4）交付分派：REVEAL = 独立 .note-answer 区块（带
      // 「参考答案」标签 + 独立视觉边界，永不与回信文本混排）；其余
      // （HINT / EXPLANATION / RETRY）= 最新一条 .noteline 显式，更早
      // 的收进 .note-history 折叠——多轮后卡内不膨胀（P0-2）。
      noteDelivery(
        card,
        String(data.delivery_text),
        String(data.delivery_kind || "")
      );
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
// 视口；关闭 = 点卡外或「收起」（closeWordCard），无 busy——命中即显。
// v3-d 契约升级（#15 行修订）：miss 的「静默」语义升级为「无样式」——
// 服务端随信下发命中位图（与点击同一套窗口+匹配语义预计算），命中词
// 带 .word 供性样式，位图为 0 的词加 .word--off（不装可点样式、点击
// 短路）——「点了没反应」从呈现层消失；位图缺席（null/缺字段）时全词
// 保持现役全供性（向可点方向容错，行为不回退）。词典兜底命中出
// 第二档小卡（「词典」标注，无 senses/examples——不冒充教学卡）。
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

function appendWordSpans(parent, text, hits, counter) {
  for (const part of String(text).split(/(\s+)/)) {
    if (!part) continue;
    if (/^\s+$/.test(part)) {
      parent.appendChild(document.createTextNode(part));
      continue;
    }
    const span = document.createElement("span");
    // 位图裁决（v3-d）：0 = 无供性（word--off）；位图缺席或行越界
    // = 全供性（向可点方向容错）。
    span.className =
      hits && hits[counter.index] === 0 ? "word word--off" : "word";
    counter.index += 1;
    span.textContent = part;
    parent.appendChild(span);
  }
}

// hits = 本段一个词一个位的命中数组（letterWords 内自计数——分片横跨
// markdown 记号时索引连续），由 letterNode 按段下发；null = 全供性。
export function letterWords(text, hits) {
  const frag = document.createDocumentFragment();
  const counter = { index: 0 };
  const segments = String(text).split(LETTER_MARKS);
  for (let i = 0; i < segments.length; i += 1) {
    const seg = segments[i];
    if (!seg) continue;
    if (i % 2 === 0) {
      appendWordSpans(frag, seg, hits || null, counter);
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
    appendWordSpans(el, inner, hits || null, counter);
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
  // v3-3 第二档：词典来源的小卡——词头 + 词性 + 简注，无 senses/
  // examples/forms（不冒充教学卡）；「词典」小标与语料卡 visibly 区分，
  // 语料面信息量优先（corpus 命中永不落词典层）。
  if (data.source === "lexicon") {
    card.classList.add("word-card--lexicon");
    const src = document.createElement("span");
    src.className = "wc-src";
    src.textContent = "词典";
    card.appendChild(src);
    const lemma = document.createElement("b");
    lemma.className = "wc-lemma wc-lemma--sm";
    lemma.textContent = String(data.lemma || "");
    card.appendChild(lemma);
    if (data.pos) {
      const pos = document.createElement("span");
      pos.className = "wc-pos";
      pos.textContent = data.pos;
      card.appendChild(pos);
    }
    if (data.gloss) {
      const gloss = document.createElement("p");
      gloss.className = "wc-zh";
      gloss.textContent = data.gloss;
      card.appendChild(gloss);
    }
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn--faint";
    close.textContent = "收起";
    close.addEventListener("click", closeWordCard);
    card.appendChild(close);
    return card;
  }
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
  // 队列③多场景区：usage 变体行（ordinal ≥ 2，语境标签与 resource_labels
  // 同 ordinal 行对齐）——有变体才渲染标题行，无变体零痕迹。
  const variants = data.usage_variants || [];
  if (variants.length) {
    const head = document.createElement("div");
    head.className = "wc-variants-head";
    head.textContent = "多场景";
    card.appendChild(head);
    for (const v of variants) {
      const row = document.createElement("p");
      row.className = "wc-variant";
      const tag = [v.genre, v.context].filter(Boolean).join(" · ");
      if (tag) {
        const lab = document.createElement("span");
        lab.className = "wc-variant-tag";
        lab.textContent = tag;
        row.appendChild(lab);
        row.appendChild(document.createTextNode(" "));
      }
      const tx = document.createElement("span");
      tx.textContent = v.text;
      row.appendChild(tx);
      card.appendChild(row);
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
let cardEsc = null;
let openScrim = null;

export function closeWordCard(opts) {
  if (cardCloser !== null) {
    document.removeEventListener("click", cardCloser);
    cardCloser = null;
  }
  if (cardEsc !== null) {
    document.removeEventListener("keydown", cardEsc);
    cardEsc = null;
  }
  const card = openCard;
  const scrim = openScrim;
  openScrim = null;
  openCard = null;
  // fr-B 褪下半（升起+褪下双向）：Esc / 收起 / 点卡外 = paper-fold +
  // ink-wash reverse + 纸雾 scrim-out 同步淡出，animationend 对账 +
  // 保险丝摘 DOM；换卡与互斥路径（showWordCard/showSpace/开沓）走
  // opts.skipOut 直摘——残影不跟层走。reduced-motion 直切。
  const instant = REDUCED_MOTION.matches || (opts && opts.skipOut);
  if (card === null && scrim === null) return;
  if (instant) {
    if (scrim !== null) scrim.remove();
    if (card !== null) card.remove();
    return;
  }
  const settle = () => {
    if (scrim !== null) scrim.remove();
    if (card !== null) card.remove();
  };
  if (scrim !== null) scrim.classList.add("word-scrim--out");
  if (card !== null) {
    card.classList.add("word-card--out");
    card.addEventListener("animationend", (event) => {
      if (event.animationName === "paper-fold" ||
          event.animationName === "sheet-out") settle();
    });
  }
  setTimeout(settle, 480);   // 保险丝（同沓家对账纪律）
}

// v2-2 双形态（8.2.2③）：浮卡档 = 点击点近侧（--wc-x/--wc-y custom
// props 承 clamp 值，媒体查询分档——触屏 (hover: none) 档不消费坐标，
// 由 CSS 落 bottom sheet 形态；JS 零档位感知）；sheet 档 = 同批挂一片
// 墨色遮罩（.word-scrim——点遮罩冒泡到既有 cardCloser 即「点卡外」
// 关闭，零新关闭机制）+ Esc 关闭（R3 语义）。DOM 移除语义两档同源。
export function showWordCard(at, data) {
  closeWordCard({ skipOut: true });   // 换卡直摘——新旧两卡不交叠
  const card = wordCard(data);
  const scrim = document.createElement("div");
  scrim.className = "word-scrim";
  document.body.appendChild(scrim);
  document.body.appendChild(card);
  const maxLeft = window.scrollX + document.documentElement.clientWidth -
    card.offsetWidth - 12;
  const maxTop = window.scrollY + window.innerHeight -
    card.offsetHeight - 12;
  card.style.setProperty("--wc-x",
    Math.max(window.scrollX + 6, Math.min(at.pageX, maxLeft)) + "px");
  card.style.setProperty("--wc-y",
    Math.max(window.scrollY + 6, Math.min(at.pageY, maxTop)) + "px");
  openScrim = scrim;
  openCard = card;
  cardCloser = (event) => {
    if (event.target !== card && !card.contains(event.target)) {
      closeWordCard();
    }
  };
  document.addEventListener("click", cardCloser);
  cardEsc = (event) => {
    if (event.key === "Escape") closeWordCard();
  };
  document.addEventListener("keydown", cardEsc);
}

// v3-3：已渲信纸的供性后装（postTurn 的用户信——寄出当下无位图，回信
// 落地时按 turn 响应的 user_word_hits 补）。rows 按信内 .say 的 DOM 序
// 对号（用户信恰一段一行）；只摘不加——初始渲染即全供性，位图只把
// 0 位降为 word--off，方向恒向「不可点」收。off 不摘出 .word 队列
// （索引空间与查询窗口原样保留）。
export function applyLetterAffordance(node, rows) {
  if (!rows) return;
  const says = node.querySelectorAll(".say");
  says.forEach((say, i) => {
    const row = rows[i];
    if (!row) return;
    let index = 0;
    for (const span of say.querySelectorAll(".word")) {
      if (row[index] === 0) span.classList.add("word--off");
      index += 1;
    }
  });
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
    // veto-R 词面中文化：有中文读法的枚举词显中文 only（原「中文 +
    // 等宽原词」并排退役——存值枚举词不变，原词移入 title 备查）。
    el.textContent = String(options.cn);
    el.title = String(word);
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

// 27. select（墨选，fr-A）：原生 <select> 的纸墨读法替代——按钮（当前
// 值 + chevron）+ 纸面浮层列表。契约（spec ③ #27）：
//   结构：.select > .select-btn（aria-haspopup="listbox" + aria-expanded
//   + aria-activedescendant）+ .select-list（role="listbox"）
//   内 .select-option（role="option" + aria-selected；选中主墨 + 勾记）。
//   键盘：↓/↑/Home/End 移动活动项（wrap）、Enter/Space 选定、Esc 关
//   闭还焦按钮、Tab 关闭（焦点自然流走）；关态 ↓/↑/Enter/Space 开。
//   点击外部关闭； hover 淡墨雾（rd-1 三值的浮层读法）。
// opts：options = [{value, label}]（label 一律 textContent 惰性）、
// value（null = 未选——placeholder 弱墨）、placeholder、name（listbox
// 的 aria-label）、onChange(value)。返回 { root, button, list,
// getValue, setValue, setOptions, open, close }——fieldRow 直接收养
// root。值是调用方的状态：工厂只回报，不私自改口。
let selectFieldSeq = 0;
//: 现役开着的墨选（⑩ 10.3 互斥：换空间 / 升写作态 / 开沓容器都要收它
//: ——浮层与下拉容器同族待遇，同一「一个手势只产一个效果」纪律）。
const openSelects = new Set();

export function closeOpenSelects() {
  for (const api of Array.from(openSelects)) api.close();
}

export function selectField(opts) {
  const options = opts || {};
  let items = options.options || [];
  let value = (options.value === undefined) ? null : options.value;
  const placeholder = options.placeholder || "选一档……";
  selectFieldSeq += 1;
  const seq = selectFieldSeq;

  const root = document.createElement("span");
  root.className = "select";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "select-btn";
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");
  const shown = document.createElement("span");
  shown.className = "select-value";
  button.appendChild(shown);
  const chevron = document.createElement("span");
  chevron.className = "select-chevron";
  chevron.appendChild(inkIcon("chevron"));
  button.appendChild(chevron);
  root.appendChild(button);
  const list = document.createElement("span");
  list.className = "select-list";
  list.setAttribute("role", "listbox");
  if (options.name) list.setAttribute("aria-label", options.name);
  list.hidden = true;
  root.appendChild(list);

  let open = false;
  let activeIndex = -1;

  function labelOf(item) {
    return item ? String(item.label) : placeholder;
  }

  function syncButton() {
    const item = items.find((entry) => entry.value === value) || null;
    shown.textContent = labelOf(item);
    shown.classList.toggle("select-value--placeholder", item === null);
  }

  function syncMarks() {
    Array.from(list.children).forEach((optionEl, i) => {
      const on = items[i] && items[i].value === value;
      optionEl.classList.toggle("select-option--on", Boolean(on));
      optionEl.setAttribute("aria-selected", on ? "true" : "false");
      const active = i === activeIndex && open;
      optionEl.classList.toggle("select-option--active", active);
    });
    if (open && activeIndex >= 0 && list.children[activeIndex]) {
      button.setAttribute("aria-activedescendant",
                          list.children[activeIndex].id);
    } else {
      button.removeAttribute("aria-activedescendant");
    }
  }

  function buildOptions() {
    list.textContent = "";
    items.forEach((item, i) => {
      const optionEl = document.createElement("span");
      optionEl.className = "select-option";
      optionEl.id = "select-" + seq + "-option-" + i;
      optionEl.setAttribute("role", "option");
      const check = document.createElement("span");
      check.className = "select-check";
      check.setAttribute("aria-hidden", "true");
      check.textContent = "✓";
      optionEl.appendChild(check);
      const word = document.createElement("span");
      word.className = "select-word";
      word.textContent = String(item.label);
      optionEl.appendChild(word);
      optionEl.addEventListener("click", () => {
        pick(i);
      });
      optionEl.addEventListener("pointerenter", () => {
        activeIndex = i;
        syncMarks();
      });
      list.appendChild(optionEl);
    });
    syncMarks();
  }

  function pick(index) {
    if (!items[index]) return;
    value = items[index].value;
    syncButton();
    syncMarks();
    close();
    button.focus();
    if (typeof options.onChange === "function") {
      options.onChange(value);
    }
  }

  function openList() {
    if (open) return;
    open = true;
    openSelects.add(api);
    root.classList.add("select--open");
    list.hidden = false;
    button.setAttribute("aria-expanded", "true");
    const selected = items.findIndex((entry) => entry.value === value);
    activeIndex = selected >= 0 ? selected : (items.length ? 0 : -1);
    syncMarks();
    if (list.children[activeIndex]) {
      list.children[activeIndex].scrollIntoView({ block: "nearest" });
    }
    document.addEventListener("pointerdown", onOutside, true);
  }

  function close() {
    if (!open) return;
    open = false;
    openSelects.delete(api);
    root.classList.remove("select--open");
    list.hidden = true;
    button.setAttribute("aria-expanded", "false");
    activeIndex = -1;
    syncMarks();
    document.removeEventListener("pointerdown", onOutside, true);
  }

  function onOutside(event) {
    if (!root.contains(event.target)) close();
  }

  button.addEventListener("click", () => {
    if (open) { close(); } else { openList(); }
  });
  button.addEventListener("keydown", (event) => {
    if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp" ||
        event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      openList();
      return;
    }
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      button.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      pick(activeIndex);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!items.length) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      activeIndex = (activeIndex + step + items.length) % items.length;
      syncMarks();
      list.children[activeIndex].scrollIntoView({ block: "nearest" });
    } else if (event.key === "Home") {
      event.preventDefault();
      activeIndex = items.length ? 0 : -1;
      syncMarks();
    } else if (event.key === "End") {
      event.preventDefault();
      activeIndex = items.length - 1;
      syncMarks();
    } else if (event.key === "Tab") {
      close();
    }
  });

  const api = {
    root,
    button,
    list,
    getValue: () => value,
    setValue: (next) => {
      value = next;
      syncButton();
      syncMarks();
    },
    setOptions: (nextItems) => {
      items = nextItems || [];
      buildOptions();
      syncButton();
    },
    open: openList,
    close,
  };
  buildOptions();
  syncButton();
  return api;
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

// ux-1（可用性刀）：移动端横滑切面板——温故/抽屉的补充切换面（用户
// 原话：移动端在合理触发条件下左右滑动切换面板；现役三签仍是主切换
// 面）。touch 事件只做识别、全程零 preventDefault（纵向滚动不受影响；
// 桌面无 touch 不触发）。松手判定：单指、横向位移 ≥ 48px 且 |dx| 严格
// 大于 |dy|（防误触纵滚）才切相邻面板；面板序取自节签 DOM（单一出处）。
// 识别成功落一记 12px（--sp-3）方向性位移、140ms（--dur-1）弹回的落纸
// 动效（screens.css 的 .panel-nudge--*；transitionend 对账摘类）。
// 起点在动作件（button/a/input/textarea/select）或横向滚动面（pre）上
// 不识别——动作钮的点击与既有横滚优先。
const SWIPE_MIN_PX = 48;

export function wirePanelSwipe(space, onSelect) {
  const host = document.getElementById("space-" + space);
  const body = host && host.querySelector(".spacebody");
  const tabs = Array.from(
    document.querySelectorAll("#" + space + "-tabs [role=tab]"));
  if (!host || !body || tabs.length === 0) return;
  const order = tabs.map((tab) => tab.dataset.section);
  let x0 = 0;
  let y0 = 0;
  let live = false;
  host.addEventListener("touchstart", (event) => {
    live = event.touches.length === 1
      && !event.target.closest("button, a, input, textarea, select, pre");
    if (live) {
      x0 = event.touches[0].clientX;
      y0 = event.touches[0].clientY;
    }
  }, { passive: true });
  host.addEventListener("touchcancel", () => { live = false; },
    { passive: true });
  host.addEventListener("touchend", (event) => {
    if (!live) return;
    live = false;
    const dx = event.changedTouches[0].clientX - x0;
    const dy = event.changedTouches[0].clientY - y0;
    if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)) {
      return;
    }
    const current = tabs.find(
      (tab) => tab.getAttribute("aria-selected") === "true");
    const at = order.indexOf(current ? current.dataset.section : "");
    const next = at + (dx < 0 ? 1 : -1);
    if (at < 0 || next < 0 || next >= order.length) return;
    const settle = (fe) => {
      if (fe.target !== body || fe.propertyName !== "transform") return;
      body.classList.remove("panel-nudge--next", "panel-nudge--prev");
      body.removeEventListener("transitionend", settle);
    };
    body.addEventListener("transitionend", settle);
    body.classList.add(dx < 0 ? "panel-nudge--next" : "panel-nudge--prev");
    onSelect(order[next]);
  }, { passive: true });
}

// v2-2 翻页守卫（wirePageTurn，8.2.2a 翻页全览 + ⑨-5 page-turn）：
// 与 wirePanelSwipe 同法的识别纪律——touch 只做识别、全程零
// preventDefault（passive；纵向滚动不受影响）；松手判定 = 单指、
// 横向位移 ≥ 48px 且 |dx| 严格大于 |dy|；起点在动作件（button/a/
// input/textarea/select）或横向滚动面（pre）上不识别。差异只在落点：
// 面板序不来自节签 DOM，而由调用方注入 current()/delta()（信封沓的
// 翻页序是页卡数组——沓数据面），边界（next < 0 / ≥ 页数）静止。
// 识别成功对 page 容器落 --pt-* 方向变量 + turn 类（12–14px 位移 +
// rotateY ≤8° + 梯形的 2D 翻页感，page-turn 动画——⑨-5 落库行），
// animationend 对账摘类（reduced-motion 随库尾总降级块 0.01ms 即终，
// 事件仍到）。playPageTurn 是点击翻页（chevron）的同一落类面——横滑
// 与点击一个动效语汇。
export function wirePageTurn(page, current, onTurn) {
  if (!page) return;
  let x0 = 0;
  let y0 = 0;
  let live = false;
  page.addEventListener("touchstart", (event) => {
    live = event.touches.length === 1
      && !event.target.closest("button, a, input, textarea, select, pre");
    if (live) {
      x0 = event.touches[0].clientX;
      y0 = event.touches[0].clientY;
    }
  }, { passive: true });
  page.addEventListener("touchcancel", () => { live = false; },
    { passive: true });
  page.addEventListener("touchend", (event) => {
    if (!live) return;
    live = false;
    const dx = event.changedTouches[0].clientX - x0;
    const dy = event.changedTouches[0].clientY - y0;
    if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)) {
      return;
    }
    const step = dx < 0 ? 1 : -1;
    if (!current() && step < 0) return;   // 边界静止
    onTurn(step);
  }, { passive: true });
}

export function playPageTurn(page, forward) {
  if (!page) return;
  const settle = (event) => {
    if (event.animationName !== "page-turn") return;
    page.classList.remove("envpage--turn-next", "envpage--turn-prev");
    page.removeEventListener("animationend", settle);
  };
  page.addEventListener("animationend", settle);
  page.classList.remove("envpage--turn-next", "envpage--turn-prev");
  void page.offsetWidth;
  page.classList.add(forward ? "envpage--turn-next" : "envpage--turn-prev");
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
export const REDUCED_MOTION = window.matchMedia(
  "(prefers-reduced-motion: reduce)");
const REVEAL_STAGGER_MS = 40;
const REVEAL_STAGGER_MAX = 8;

// fr-B 列表逐项错峰（⑨-5 新行；stagger 28ms 档——--dur-stagger 消费
// 在 components.css 的 .stagger-in）：给一组「此刻可见」的列表行落
// --i 与 .stagger-in（140ms 淡入 + 4px 上移，步长 28ms、前 8 项封
// 顶）。消费面 = 搜索结果/目标列表的重过滤（app.js familyGroupsBlock）
// ——wireReveal 管「首入视一次」，本函数管「重渲染即错峰」。摘类 +
// 强制重排 + 落类 = 可重触发的最小编排；reduced-motion 直切（JS
// 半区，与 wireReveal 同一纪律）。
const RESTAGGER_MAX = 8;

export function restagger(nodes) {
  if (REDUCED_MOTION.matches) return;
  let index = 0;
  for (const node of nodes) {
    if (index >= RESTAGGER_MAX) break;
    node.classList.remove("stagger-in");
    node.style.setProperty("--i", String(index));
    void node.offsetWidth;   // 重触发动画（playPageTurn 同手法）
    node.classList.add("stagger-in");
    index += 1;
  }
}

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
// 邮票（变体类由 app.js 从 stamp_key 确定性派生）+ 动作行（起笔 · 对话 ·
// 档案 · 编辑——下划线文字链接，形态走 #1 的 --pencil；「起笔」=
// v3-2R 的写信工作区入口，选定角色开始写信，容器向下延展成工作界面）；当前通信的
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
  act("起笔", "env-act-compose", () => {
    if (typeof options.onCompose === "function") options.onCompose();
  });
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

// ── v3-2: 容器延展（下拉容器的形态连续过渡半区；app.js 禁 .style，
// custom props 与高度编排只在此落——mc-1 排布半区同一规矩）────────
// 「整个容器的变化，而不是多一个滚动条」（用户原话 2026-10-02）：
// 起笔/编辑/翻看都是沓面板本体向下拉开——mutate() 换装容器内容前后
// 各量一次高，高度差经 --panel-h custom prop 走一次 height transition
// （--dur-settle 大件档 × --ease-paper 减速长尾；⑩ 层级宪法的容器
// 延展档），transitionend 后摘 prop（height 回 auto）。reduced-motion
// 直切（REDUCED_MOTION 单一归宿 + 库尾总降级块双面）。480ms 保险丝
// 与沓面板的 fold 同款（animationend/transitionend 正常先到）。
export function extendContainer(panel, mutate) {
  if (typeof mutate !== "function") return;
  if (REDUCED_MOTION.matches) {
    mutate();
    return;
  }
  const from = panel.offsetHeight;
  mutate();
  const to = panel.offsetHeight;
  if (from === to) return;
  panel.style.setProperty("--panel-h", from + "px");
  panel.classList.add("envsel--grow");
  void panel.offsetHeight;   // 起点落定——从旧高过渡到新高
  panel.style.setProperty("--panel-h", to + "px");
  const done = (event) => {
    if (event && event.propertyName !== "height") return;
    panel.classList.remove("envsel--grow");
    panel.style.removeProperty("--panel-h");
    panel.removeEventListener("transitionend", done);
  };
  panel.addEventListener("transitionend", done);
  setTimeout(done, 480);   // 保险丝（transitionend 正常先到）
}

// 浮层在开吗（#15 词卡）：层级宪法的 Esc 退栈顺序裁决面——沓面板的
// Esc 只在浮层不在场时才接（浮层的监听收它自己）。零状态复制：读
// components.js 自己的 openCard 单源。
export function wordCardOpen() {
  return openCard !== null;
}

// v3-a 矮视口降级半区的稿纸 autosize（D-A 展开条形态）：rows 起步、
// scrollHeight 钳制封顶后内滚。动态几何属库（extendContainer 同族——
// app 面不落内联样式）；封顶值与档位判定由调用方（app.js 的
// SHORT_VIEWPORT 半区）注入。
export function autosizeTo(pen, cap) {
  pen.style.height = "auto";
  pen.style.height = Math.min(pen.scrollHeight, cap) + "px";
}

export function clearAutosize(pen) {
  pen.style.height = "";
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
