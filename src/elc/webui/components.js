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
  window.scrollTo(0, document.body.scrollHeight);
}

// F-1R: the letter flow — a turn's words become letters, never bubbles.
// The user's line is the torn-edge reply slip (.letter.me .paper), the
// parlor's is the plain sheet (.letter.may); a failure is marginalia (a
// pencil rule in the left margin), a system note is a centered faint
// line. Every word rides textContent — the user's own words stay inert
// text, never markup.
export function addLine(cls, text) {
  let node;
  if (cls === "user") {
    node = document.createElement("div");
    node.className = "letter me";
    const paper = document.createElement("div");
    paper.className = "paper";
    const say = document.createElement("p");
    say.className = "say";
    say.textContent = text;            // textContent, never markup: the
    paper.appendChild(say);            // user's own words stay inert text
    node.appendChild(paper);
  } else if (cls === "assistant") {
    node = document.createElement("div");
    node.className = "letter may";
    const say = document.createElement("p");
    say.className = "say";
    say.textContent = text;
    node.appendChild(say);
  } else if (cls === "typing") {
    node = document.createElement("p");
    node.className = "typing";
    node.textContent = text;
  } else if (cls === "failure") {
    node = document.createElement("p");
    node.className = "errline";
    node.textContent = text;
  } else {
    node = document.createElement("p");
    node.className = "sysline";
    node.textContent = text;
  }
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
// (the symbol is display only; the words are the runtime's own), and a
// submitted reply is visible the instant it goes out — a help reply waits
// out a model round trip, and a silent wait reads as a dead page.
function outcomeSymbol(feedback) {
  const word = String(feedback).split("（")[0];
  if (word === "SUCCESS" || word === "ALTERNATIVE_SUCCESS") return "✓";
  if (word === "PARTIAL") return "◐";
  if (word === "FAILURE") return "✗";
  return "";
}

// 7. resultstrip：判分结果条（✓/◐/✗ 是显示件，词是 runtime 自己的）。
export function showResultStrip(card, feedback) {
  const symbol = outcomeSymbol(feedback);
  const strip = document.createElement("div");
  strip.className = "resultstrip " +
    (symbol === "✓" ? "ok" : symbol === "✗" ? "miss" : "part");
  strip.textContent = (symbol ? symbol + " " : "") + "判分反馈：" + feedback;
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

// 3. note-paper：教学短笺卡（标题 + 状态 + 类型，等回复控件）。
export function showMoments(list) {
  momentsBox.textContent = "";
  if (!list.length) {
    const p = document.createElement("p");
    p.className = "note";
    p.textContent = "本轮没有打开教学时刻。";
    momentsBox.appendChild(p);
    return;
  }
  for (const m of list) {
    const card = document.createElement("div");
    card.className = "note-paper";
    const b = document.createElement("b");
    if (m.title) {
      b.textContent = "教学时刻：" + m.title;
      card.appendChild(b);
      card.appendChild(document.createTextNode(
        " · 状态 " + (m.status_cn || m.lifecycle_state) +
        " · " + (m.kind_cn || m.kind)));
    } else {
      b.textContent = m.focus_target_id;
      card.appendChild(b);
      card.appendChild(document.createTextNode(
        " · 状态 " + m.lifecycle_state + " · 类型 " + m.kind));
    }
    if (m.last_attempt_feedback) {
      // W-6: the verdict survives a refresh — the ro current card carries
      // the moment's latest durable evaluation outcome
      showResultStrip(card, m.last_attempt_feedback);
    }
    if (m.lifecycle_state === "AWAITING_USER") {
      // the W-2/W-3 reply face: a moment waiting for the user offers the
      // attempt box (their own English sentence, judged) and the skip
      addReplyControls(card);
    }
    momentsBox.appendChild(card);
  }
}

export function addReplyControls(card) {
  const row = document.createElement("div");
  row.className = "replyrow";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "replytext";
  input.autocomplete = "off";
  input.placeholder = "用英语试着造个句子…";
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "btn btn--send";
  submit.textContent = "寄出作答";
  submit.addEventListener("click", () => submitAttempt(card, input));
  row.appendChild(input);
  row.appendChild(submit);
  card.appendChild(row);
  // W-6: the three help arms SM §1 names, as pencil links at the note's
  // tail — the words map onto the runtime's ASK_HINT / ASK_ANSWER /
  // ASK_EXPLANATION and nothing else
  const help = document.createElement("div");
  help.className = "replyrow";
  help.appendChild(helpButton("看提示", "hint", "取提示中…", "已看提示", card));
  help.appendChild(helpButton("看答案", "reveal", "取答案中…", "已看答案", card));
  help.appendChild(helpButton("解释", "explanation", "取解释中…", "已看解释", card));
  card.appendChild(help);
  // W-2: the skip — a faint small link under the help arms; the moment's
  // lock releases through the runtime's own reply entry, nothing else
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "btn btn--faint";
  skip.textContent = "跳过这一题";
  skip.addEventListener("click", () =>
    postReply(card, { control: "skip" }, "跳过中…", "教学已跳过"));
  card.appendChild(skip);
}

function helpButton(label, control, busyText, doneNote, card) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn";
  button.textContent = label;
  button.addEventListener("click", () => {
    if (control === "reveal" &&
        !confirmDialog("看答案将显示完整目标表达，之后你仍可作答，确定？")) {
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
}

function readReplyAnswer(card, data) {
  // the reply result's own words, never a fabricated one: the new state
  // plus the feedback verdict (as the W-6 result strip) when the reply
  // carried one
  disarmMomentCard(card);
  card.appendChild(document.createElement("br"));
  const b = document.createElement("b");
  b.textContent = data.moment_state === "AWAITING_USER"
    ? "再试一次？"
    : "本次回应已收下";
  card.appendChild(b);
  card.appendChild(document.createTextNode(
    " · 状态 " + (data.moment_state || "未知")));
  if (data.feedback !== null && data.feedback !== undefined) {
    showResultStrip(card, data.feedback);
  }
  if (data.moment_state === "AWAITING_USER") {
    // the moment lives on (a miss re-prompts, an authorized reveal leaves
    // the post-reveal optional attempt open): the user can retry or skip
    addReplyControls(card);
  } else {
    card.classList.add("skipped");
  }
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
    // 实际形状下不可区分，统一用提交失败；见 spec ⑦ 等价注记）。
    if (!data.accepted) {
      addLine("failure", data.error || "提交失败，请重试");
      return;
    }
    addLine("system", doneNote);
    if (data.delivery_text) {
      // the runtime's own delivered words (the hint rung / the reveal
      // form / the explanation), shown like any assistant line
      addLine("assistant", data.delivery_text);
    }
    readReplyAnswer(card, data);
  } catch {
    addLine("failure", "提交失败，请重试");
  } finally {
    setReplyBusy(card, false);
  }
}

async function submitAttempt(card, input) {
  const text = input.value.trim();
  if (!text) return;
  await postReply(card, { control: "attempt", text: text }, "批改中…", "已提交作答");
}

// 9/10 的仪表面工厂：meter-row（kv/kvgroup/kvtitle）与 empty-state（note）。
export function diagEmpty(box, word) {
  const p = document.createElement("p");
  p.className = "note";
  p.textContent = word || "暂无数据";
  box.appendChild(p);
}

export function diagError(box, message) {
  const p = document.createElement("p");
  p.className = "diagerror";
  p.textContent = "读取失败：" + message;
  box.appendChild(p);
}

export function diagLine(box, label, value) {
  const row = document.createElement("div");
  row.className = "kv";
  const b = document.createElement("b");
  b.textContent = label + "：";
  row.appendChild(b);
  row.appendChild(document.createTextNode(String(value)));
  box.appendChild(row);
}

export function diagGroup(box, title) {
  const g = document.createElement("div");
  g.className = "kvgroup";
  const b = document.createElement("b");
  b.className = "kvtitle";
  b.textContent = title;
  g.appendChild(b);
  box.appendChild(g);
  return g;
}
