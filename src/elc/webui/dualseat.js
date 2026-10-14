// dualseat.js —— DS-1 沉浸面（/ds）的唯一脚本。
//
// 纪律（与 reader.js 同族）：零依赖、零外链、零内联样式；DOM 一律
// createElement + textContent（不拼 HTML 串）。
//
// 呈现律（技术定义 §12）落法：
// 1. 拍型感知管线——阶段帧由服务端事件面给出（{"type":"stage"}），
//    open/advance 与 reply 各见各的阶段，因果不倒置；
// 2. 流式正文——delta 帧按句渐入（服务端已扣住停点标记尾），发丝线
//    按已落字数走（以最终正文长度估算）；
// 3. 可读状态句——停点行只说「轮到你了」级别的事实，绝不剧透内心；
// 4. 常开输入 chip——输入框永不禁用；驱动中的输入成为待落签，可编辑
//    可撤回；下一次 reply 携带（多签按换行并入一次提交）；
// 5. 章末非阻断内联章间面——章 CLOSED 时在正文流末尾展开（可收起），
//    方向词随「开下一章」携带（留空=让世界自行发展）；
// 6. 失败态诚实——真实秒红、话不丢（final.ok=false 时输入保留）；
// 7. 首开引导——三步，localStorage 记「已读」。

const API = {
  state: "/api/ds/state",
  start: "/api/ds/start",
  open: "/api/ds/open",
  advance: "/api/ds/advance",
  reply: "/api/ds/reply",
  settle: "/api/ds/settle",
  nextChapter: "/api/ds/next_chapter",
  bible: "/api/ds/bible",
  lightModel: null, // 见 setLightModel（同一 /api/ds/bible 通道之外的一条小设置）
};

const POLL_MS = 3000;
const STAGE_LABEL = {
  dispatching: "世界在铺陈这一幕",
  responding: "她们在听你刚才的话",
  adjudicating: "世界在定夺",
  writing: "正在落纸",
};
const STAGE_LABEL_REPLY = {
  dispatching: "世界在接你的话",
  responding: "她们在想你说的话",
  adjudicating: "世界在定夺",
  writing: "正在落纸",
};

const el = (id) => document.getElementById(id);

let busy = false;
let busyStartedAt = 0;
let busyTimer = null;
let currentStage = null;
let currentBeat = "advance";
let pollTimer = null;
let lastPayload = null;
let lastFlowFingerprint = null; // 正文面貌签（§12.2：同貌拍不重绘）
let chips = [];        // {text} — 待落签
let chipModes = {};    // field -> "now" | "next"
let acked = new Set();
let seenGuide = false;
try { seenGuide = localStorage.getItem("ds_guide_seen") === "1"; } catch (e) { /* no-op */ }

function mintSubmissionId() {
  return "ds-web-" + Date.now().toString(36) + "-" +
    Math.random().toString(36).slice(2, 8);
}

function elapsedSeconds() {
  return Math.max(0, Math.round((Date.now() - busyStartedAt) / 1000));
}

function tickBusy() {
  if (!busy) return;
  el("ds-elapsed").textContent = "已用 " + elapsedSeconds() + " 秒";
}

function beginBusy(beat) {
  busy = true;
  currentBeat = beat;
  currentStage = null;
  busyStartedAt = Date.now();
  el("ds-faultline").hidden = true;
  tickBusy();
  if (busyTimer !== null) window.clearInterval(busyTimer);
  busyTimer = window.setInterval(tickBusy, 1000);
  renderChips();
}

function endBusy() {
  busy = false;
  currentStage = null;
  if (busyTimer !== null) {
    window.clearInterval(busyTimer);
    busyTimer = null;
  }
  el("ds-elapsed").textContent = "";
}

function setStage(stage) {
  currentStage = stage;
  const table = currentBeat === "reply" ? STAGE_LABEL_REPLY : STAGE_LABEL;
  el("ds-stage").textContent = table[stage] || "世界进行中";
}

function setStatus(text) {
  el("ds-status").textContent = text || "";
}

function setFault(text) {
  const line = el("ds-faultline");
  if (!text) { line.hidden = true; line.textContent = ""; return; }
  line.hidden = false;
  line.textContent = text + "——你的话还在，正在重试即可。";
}

// ── SSE 驱动 ─────────────────────────────────────────────────────
async function streamDrive(path, body, busyLine) {
  const beat = path === API.reply ? "reply" : (path === API.open ? "open" : "advance");
  beginBusy(beat);
  setStage(beat === "reply" ? "dispatching" : "dispatching");
  setStatus(busyLine || "世界进行中……（真实模型）");
  const options = { method: "POST", headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let final = null;
  let firstByteAt = 0;
  try {
    const response = await fetch(path, options);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const read = await reader.read();
      if (read.done) break;
      buffer += decoder.decode(read.value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (!frame.startsWith("data:")) continue;
        let event;
        try { event = JSON.parse(frame.slice(5).trim()); } catch (e) { continue; }
        if (event.type === "delta") {
          if (firstByteAt === 0) {
            firstByteAt = Date.now();
            setStage("writing");
          }
          appendStreamText(event.text);
        } else if (event.type === "stage") {
          setStage(event.stage);
        } else if (event.type === "final") {
          final = event;
        }
      }
    }
  } catch (error) {
    final = { ok: false, error: "这一请求没有得到服务器的回答——再试一次。" };
  }
  endBusy();
  el("ds-stage").textContent = "…";
  if (final) render(final, true);
  return final;
}

// ── 正文流渲染 ───────────────────────────────────────────────────
let streamPara = null;   // 当前流式段落的 <p>
let streamChars = 0;     // 已落字数（发丝线的分子；分母=上一段长度近似）

function follow() {
  const flow = el("ds-flow");
  flow.scrollTop = flow.scrollHeight;
}

function appendStreamText(text) {
  if (!streamPara) {
    streamPara = document.createElement("p");
    el("ds-inner").appendChild(streamPara);
  }
  // 按句渐入：以换句为界把已到的文本切进 <span class="ds-sent">
  const done = streamPara.dataset.done || "";
  const fresh = text;
  const whole = done + fresh;
  const parts = whole.split(/(?<=[。！？…])/);
  const full = parts.slice(0, -1);
  const tail = parts[parts.length - 1];
  streamPara.textContent = "";
  full.forEach((sentence) => {
    const span = document.createElement("span");
    span.className = "ds-sent";
    span.textContent = sentence;
    streamPara.appendChild(span);
  });
  const tailSpan = document.createElement("span");
  tailSpan.className = "ds-sent";
  tailSpan.textContent = tail;
  streamPara.appendChild(tailSpan);
  streamPara.dataset.done = whole;
  streamChars += fresh.length;
  const total = Math.max(streamChars, (lastPayload && lastPayload.passages
    && lastPayload.passages.length
    ? averagePassageChars() : streamChars) || 1);
  el("ds-hairfill").style.width =
    Math.min(96, Math.round(streamChars / Math.max(total, 1) * 100)) + "%";
  el("ds-hairline").classList.add("on");
  follow();
}

function averagePassageChars() {
  const list = (lastPayload && lastPayload.passages) || [];
  if (!list.length) return 0;
  return list.reduce((acc, p) => acc + (p.body || "").length, 0) / list.length;
}

function sealParagraph() {
  if (streamPara) {
    streamPara = null;
    streamChars = 0;
    el("ds-hairline").classList.remove("on");
    el("ds-hairfill").style.width = "0%";
  }
}

function flowFingerprint(payload) {
  // 正文面（renderFlow + 开始卡/开篇卡/章末面）依赖的全部输入——貌
  // 签恒等 ⇔ 正文区一个节点都不必动；任何一类态变迁（种世界/开篇/
  // 新段落落/章末）都改变其中至少一项，必然重绘。
  const world = payload.world || {};
  const chapter = payload.chapter || null;
  const settlement = payload.settlement || null;
  return JSON.stringify([
    world.exists === true,
    payload.draft === true,
    chapter ? chapter.chapter_index : null,
    chapter ? chapter.status : null,
    (payload.plan || {}).dramatic_question || null,
    (payload.passages || []).map(
      (passage) => [passage.passage_id, passage.body]
    ),
    settlement ? settlement.summary || null : null,
    (payload.next || {}).kind || null,
    (payload.controls || {}).can_open === true,
  ]);
}

function renderFlow(payload) {
  const inner = el("ds-inner");
  inner.textContent = "";
  const chapter = payload.chapter;
  if (chapter && chapter.chapter_index) {
    const head = document.createElement("div");
    head.className = "ds-chaphead";
    const h2 = document.createElement("h2");
    h2.textContent = "第" + zhIndex(chapter.chapter_index) + "章";
    head.appendChild(h2);
    const rule = document.createElement("div");
    rule.className = "ds-rule";
    head.appendChild(rule);
    if (payload.plan && payload.plan.dramatic_question) {
      const q = document.createElement("p");
      q.className = "ds-chapq";
      q.textContent = "本章之问 · " + payload.plan.dramatic_question;
      head.appendChild(q);
    }
    inner.appendChild(head);
  }
  (payload.passages || []).forEach((passage) => {
    const p = document.createElement("p");
    p.textContent = passage.body;
    inner.appendChild(p);
  });
  streamPara = null;
  streamChars = 0;
  const fresh = (payload.passages || [])
    .map((passage) => passage.passage_id)
    .filter((id) => !acked.has(id));
  if (fresh.length) {
    fresh.forEach((id) => acked.add(id));
  }
  if (chapter && chapter.status === "CLOSED") renderChapterEnd(payload);
}

function zhIndex(n) {
  const words = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
  return words[n] || String(n);
}

// ── 章末内联章间面（非阻断 §12.5）───────────────────────────────
function renderChapterEnd(payload) {
  const inner = el("ds-inner");
  const block = document.createElement("div");
  block.className = "ds-chapend";
  const sealRow = document.createElement("div");
  sealRow.className = "ds-chsealrow";
  const seal = document.createElement("span");
  seal.className = "ds-chseal";
  seal.textContent = "落";
  const sealTxt = document.createElement("span");
  sealTxt.className = "ds-chsealtxt";
  sealTxt.textContent = "本章落定";
  sealRow.appendChild(seal);
  sealRow.appendChild(sealTxt);
  block.appendChild(sealRow);
  const sub = document.createElement("p");
  sub.className = "ds-chsub";
  sub.textContent = "章间面放在正文末尾 · 可收起 · 不急";
  block.appendChild(sub);
  const card = document.createElement("div");
  card.className = "ds-chcard";
  if (payload.settlement) {
    const h5 = document.createElement("h5");
    h5.textContent = "你离场之后 · 幕外";
    card.appendChild(h5);
    const ul = document.createElement("ul");
    String(payload.settlement.summary || "").split("\n").forEach((line) => {
      if (!line.trim()) return;
      const li = document.createElement("li");
      li.textContent = line;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }
  const label = document.createElement("label");
  label.className = "field ds-chdir-label";
  const labelName = document.createElement("span");
  labelName.className = "fieldname";
  labelName.textContent = "给下一章一个方向（可留空=让世界自行发展）";
  const input = document.createElement("input");
  input.id = "ds-direction";
  input.type = "text";
  input.placeholder = "例：让那道符在雨夜里自己淡去";
  label.appendChild(labelName);
  label.appendChild(input);
  card.appendChild(label);
  const openBtn = document.createElement("button");
  openBtn.className = "btn btn--ink ds-chopen";
  openBtn.type = "button";
  openBtn.textContent = "开下一章";
  openBtn.addEventListener("click", async () => {
    if (busy) { setStatus("上一步还在进行中（已用 " + elapsedSeconds() + " 秒）——等它跑完。"); return; }
    const direction = input.value.trim();
    await postDrive(API.nextChapter, direction ? { direction } : undefined,
      "导演起新的一幕…（真实模型）");
  });
  card.appendChild(openBtn);
  block.appendChild(card);
  const fold = document.createElement("button");
  fold.className = "ds-chfold";
  fold.type = "button";
  fold.textContent = "本章落定 · 收起章间面 ▴";
  fold.addEventListener("click", () => {
    const folded = block.classList.toggle("folded");
    fold.textContent = folded ? "本章落定 · 展开章间面 ▾" : "本章落定 · 收起章间面 ▴";
  });
  block.appendChild(fold);
  inner.appendChild(block);
}

// ── 待落 chips（§12.4 常开输入）─────────────────────────────────
function renderChips() {
  const box = el("ds-chips");
  box.textContent = "";
  chips.forEach((chip, index) => {
    const d = document.createElement("div");
    d.className = "ds-chip" + (busy ? " consuming" : "");
    const top = document.createElement("div");
    top.className = "ds-chip-top";
    const label = document.createElement("span");
    label.textContent = busy ? "正在落进这一拍……" : "已听见 · 将落在下一拍";
    top.appendChild(label);
    if (!busy) {
      const act = document.createElement("span");
      act.className = "ds-chip-act";
      const edit = document.createElement("button");
      edit.type = "button";
      edit.textContent = "编辑";
      edit.addEventListener("click", () => editChip(d, chip));
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "撤回";
      del.addEventListener("click", () => {
        chips = chips.filter((x) => x !== chip);
        renderChips();
      });
      act.appendChild(edit);
      act.appendChild(del);
      top.appendChild(act);
    }
    d.appendChild(top);
    const text = document.createElement("div");
    text.className = "ds-chip-text";
    text.textContent = chip.text;
    d.appendChild(text);
    box.appendChild(d);
  });
  box.hidden = !chips.length;
}

function editChip(node, chip) {
  const textNode = node.querySelector(".ds-chip-text");
  const area = document.createElement("textarea");
  area.className = "ds-chip-edit";
  area.value = chip.text;
  textNode.replaceWith(area);
  area.focus();
  area.addEventListener("blur", () => {
    const value = area.value.trim();
    if (value) chip.text = value;
    renderChips();
  });
}

function takeChips() {
  const texts = chips.map((chip) => chip.text);
  chips = [];
  renderChips();
  return texts.join("\n");
}

// ── 输入行（永不禁用）───────────────────────────────────────────
const say = el("ds-say");
say.addEventListener("input", () => {
  say.style.height = "auto";
  say.style.height = Math.min(say.scrollHeight, 110) + "px";
});
say.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
});
el("ds-send").addEventListener("click", submit);

async function submit() {
  const text = say.value.trim();
  if (!text) return;
  if (busy) {
    // 生成中的输入 → 待落签（可编辑可撤回），绝不静默。
    chips.push({ text });
    say.value = "";
    say.style.height = "auto";
    renderChips();
    setStatus("已听见 · 将落在下一拍。");
    return;
  }
  const pending = takeChips();
  const whole = [text, pending].filter((x) => x).join("\n");
  say.value = "";
  say.style.height = "auto";
  lastSubmissionId = mintSubmissionId();
  const final = await streamDrive(API.reply, {
    text: whole,
    submission_id: lastSubmissionId,
  });
  if (final && final.ok === false) {
    // 话不丢：失败即回填（chip 区），一键重试。
    chips.push({ text: whole });
    renderChips();
  }
}
let lastSubmissionId = null;

async function postDrive(path, body, busyLine) {
  if (busy) { setStatus("上一步还在进行中（已用 " + elapsedSeconds() + " 秒）——等它跑完。"); return null; }
  setStatus(busyLine || "世界进行中……");
  beginBusy(path === API.settle ? "advance" : "open");
  setStage("dispatching");
  let payload = null;
  try {
    const options = { method: "POST", headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    payload = await response.json();
  } catch (error) {
    payload = { ok: false, error: "这一请求没有得到服务器的回答——再试一次。" };
  }
  endBusy();
  el("ds-stage").textContent = "…";
  render(payload, true);
  return payload;
}

// ── 状态渲染 ────────────────────────────────────────────────────
function render(payload, isFinal) {
  if (!payload) return;
  if (payload.error && payload.ok !== true) {
    // 失败态诚实（呈现律 6）：错误进状态行的同时点亮红条（faultline），
    // 且只在下一次 beginBusy 清——轮询的后续拍（next.detail「轮到你了
    // ……」）不得覆盖它，错误粘住直到用户重试。半截流式段在此一并撤
    // 下（失败拍没有落库，重绘路径本会清它——同一份责任提前收尾，
    // 发丝线随之归零）。
    setStatus(payload.error);
    setFault(payload.error);
    if (streamPara && streamPara.parentNode) {
      streamPara.parentNode.removeChild(streamPara);
    }
    sealParagraph();
    return;
  }
  lastPayload = payload;
  const world = payload.world;
  if (world && world.exists) {
    el("ds-world").textContent = (world.name || world.world_id) +
      (world.current_tick === null || world.current_tick === undefined
        ? "" : "　·　tick " + world.current_tick) +
      (payload.draft ? "　·　开局草稿（待定调）" : "");
  } else if (world && !world.exists) {
    el("ds-world").textContent = "雾季 · 青溪渡尚未落笔";
  }
  // 正文面铸貌签（§12.2 呈现律的拍间律，DS-2）：renderFlow/开始卡/
  // 开篇卡/章末面依赖的全部输入（世界、草稿旗、章、计划之问、已落
  // 段落、幕外摘要、下一步形态、开篇许可）合成一张貌签——与上一拍
  // 同貌就整块跳过 DOM 重建，轮询拍只走下面的状态行/输入行等廉价
  // textContent 面。此前每 3 秒全量清空重建正文区（用户亲验的「画面
  // 文字一直在闪烁」）正是无貌检查的全量重绘；种世界、开篇、新段落
  // 落、章末四类态变迁必然改貌、必然重绘。
  const fingerprint = flowFingerprint(payload);
  if (fingerprint !== lastFlowFingerprint) {
    lastFlowFingerprint = fingerprint;
    sealParagraph();
    renderFlow(payload);
    // 空态开始钮：renderFlow 清空正文区后，开始钮由这里补回（boot
    // 只画一次会被轮询滴答抹掉）。
    if (world && !world.exists) renderStartCard(payload);
    const controlsNow = payload.controls || {};
    if ((payload.next || {}).kind === "opening" || controlsNow.can_open) {
      renderOpenCard();
    }
  }
  const stop = payload.stop;
  const note = payload.note || (stop && stop.note) || null;
  const next = payload.next || {};
  if (isFinal && payload.did && payload.did.stopped_on) {
    const words = {
      addresses_you: "有人等你回话——轮到你了。",
      impends_on_you: "有一件事等你拿主意——轮到你了。",
      beat_ceiling: payload.did.note || "世界停在这——轮到你了。",
      call_ceiling: payload.did.note || "世界先停在这——轮到你了。",
      pacing_hold: "这一拍落定了。想接话就开口。",
      pacing_settle: "这一幕收住了。想接话就开口。",
      pacing_press: null,
      no_chapter: null,
      chapter_not_active: null,
      no_scene: null,
      refused: null,
      exhausted: null,
      gate_awaiting: null,
    };
    const word = words[payload.did.stopped_on];
    if (word) setStatus(word);
    else if (payload.did.note) setStatus(payload.did.note);
    else if (payload.error) setStatus(payload.error);
    else setStatus(next.detail || "");
  } else if (note) {
    setStatus(note);
  } else {
    setStatus(next.detail || "");
  }
  const controls = payload.controls || {};
  el("ds-turntag").hidden = next.kind !== "your_turn";
  el("ds-inputrow").classList.toggle("yourturn", next.kind === "your_turn");
  say.placeholder = next.kind === "your_turn"
    ? "轮到你了——说什么都行" : "说点什么……任何时候都可以";
  renderLang(payload.language);
  // 设定面同律（DS-2 次生同根）：编辑进行中（editBibleRow 打开的
  // textarea 还在面板里）轮询拍不得全量重建设定面板——正在编辑的
  // 设定文本不被轮询抹掉。保存成功由 save 自行退出编辑态后恢复重
  // 绘；手动重绘（模式钮/取消/打开面板）不经此守卫。
  if (!el("ds-settings-body").querySelector(".ds-sedit")) {
    renderSettings(payload);
  }
  syncGearBadge(payload);
}

// ── 语言对钮（正文语言 · 与 V3 阅读面共享同一 v3_prose_language key）
// 当前语言高亮（读 state.language）；点击写 /api/ds/language 后重读
// state 重渲。已写段落不改写——语言只影响此后新段（V3-8g 同律）。
function renderLang(word) {
  const zh = word === "zh";
  el("ds-lang-zh").classList.toggle("on", zh);
  el("ds-lang-en").classList.toggle("on", !zh);
}

async function switchLanguage(word) {
  const payload = await postJSON("/api/ds/language", { language: word });
  if (payload && payload.ok) {
    setStatus(word === "zh"
      ? "正文语言已切到中文——此后落笔的新段用中文写，已写段落不改写。"
      : "正文语言已切到英文——此后落笔的新段用英文写，已写段落不改写。");
  } else if (payload) {
    setStatus(payload.error || "语言没有切换成功——再试一次。");
  }
  const fresh = await readState().catch(() => null);
  if (fresh) render({ ...fresh, ok: true }, false);
}

el("ds-lang-en").addEventListener("click", () => switchLanguage("en"));
el("ds-lang-zh").addEventListener("click", () => switchLanguage("zh"));

// ── 设定面（导演位 · 分级生效 §6 F3）────────────────────────────
function renderSettings(payload) {
  if (el("ds-settings").hidden) return;
  const body = el("ds-settings-body");
  body.textContent = "";
  (payload.bible || []).forEach((row) => {
    const mode = chipModes[row.field] || "next";
    const pending = (payload.pending_bible || []).some((p) => p.field === row.field);
    const div = document.createElement("div");
    div.className = "ds-srow";
    const head = document.createElement("div");
    head.className = "ds-srow-h";
    const name = document.createElement("b");
    name.textContent = row.field;
    head.appendChild(name);
    const modes = document.createElement("span");
    modes.className = "ds-smode";
    [["now", "即时生效"], ["next", "下一章生效"]].forEach(([word, label]) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      const on = mode === word;
      btn.className = on ? "on" + (word === "now" ? " now" : "") : "";
      btn.addEventListener("click", () => { chipModes[row.field] = word; renderSettings(lastPayload); });
      modes.appendChild(btn);
    });
    head.appendChild(modes);
    const stat = document.createElement("span");
    stat.className = "ds-sstat" + (pending ? " wait" : "");
    stat.textContent = pending ? "待落 · 下一章生效" : "";
    head.appendChild(stat);
    div.appendChild(head);
    const value = document.createElement("div");
    value.className = "ds-sval";
    value.textContent = row.value;
    value.addEventListener("click", () => editBibleRow(div, row, mode));
    div.appendChild(value);
    body.appendChild(div);
  });
}

function editBibleRow(node, row, mode) {
  const valueNode = node.querySelector(".ds-sval");
  const area = document.createElement("textarea");
  area.className = "ds-sedit";
  area.value = row.value;
  valueNode.replaceWith(area);
  const ops = document.createElement("div");
  ops.className = "ds-sops";
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "保存";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "取消";
  ops.appendChild(save);
  ops.appendChild(cancel);
  area.after(ops);
  cancel.addEventListener("click", () => renderSettings(lastPayload));
  save.addEventListener("click", async () => {
    const value = area.value.trim();
    if (!value || value === row.value) { renderSettings(lastPayload); return; }
    const payload = await postJSON(API.bible, {
      field: row.field, value, mode,
    });
    if (payload && payload.ok) {
      setStatus(mode === "now"
        ? "「" + row.field + "」已即时生效——只影响之后的世界。"
        : "「" + row.field + "」将在下一章生效。");
      // 成功即退出编辑态（恢复展示行）——随后的状态重绘恢复接管面
      // 板；失败则什么都不拆，编辑文本留在框里（话不丢，改完再存）。
      renderSettings(lastPayload);
    } else if (payload) {
      setStatus(payload.error || "设定没有落下去——再试一次。");
    }
    const fresh = await readState().catch(() => null);
    if (fresh) render(fresh, false);
  });
  area.focus();
}

async function postJSON(path, body) {
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return await response.json();
  } catch (error) {
    return { ok: false, error: "这一请求没有得到服务器的回答——再试一次。" };
  }
}

function syncGearBadge(payload) {
  const pending = (payload.pending_bible || []).length;
  const badge = el("ds-gearbadge");
  badge.hidden = !pending;
  badge.textContent = String(pending);
}

// ── 引导（§12.7 首开引导）───────────────────────────────────────
const GUIDE = [
  { h: "你是谁", t: "你叫阿澈，一个远道来的年轻画师，受雇为新桥画落成图。"
    + "今晚，桥基石栏上多了一道没人认领的朱砂符——管事温秋蘅当众问你："
    + "你过桥的时候，它已经在了吗？这一章，就从这个等你回答的问题开始。" },
  { h: "输入框永远开着", t: "底部的输入框任何时候都能用——包括世界正在落笔的时候。"
    + "那一拍会「听见」你：你的话会变成一枚待落的签，落进下一拍的正文里。"
    + "落定之前，随时可以编辑、可以撤回。" },
  { h: "停点是什么", t: "当正文停下来、悬着——那是有人在等你说话，"
    + "或有一件事等你拿主意。不是卡住，是轮到你了。说什么都行，"
    + "世界接着你的话，往下走。" },
];
let guideStep = 0;
function renderGuide() {
  const step = GUIDE[guideStep];
  const box = el("ds-gstep");
  box.textContent = "";
  const h = document.createElement("h4");
  h.textContent = step.h;
  const p = document.createElement("p");
  p.textContent = step.t;
  box.appendChild(h);
  box.appendChild(p);
  const dots = el("ds-gdots");
  dots.textContent = "";
  GUIDE.forEach((_, i) => {
    const dot = document.createElement("i");
    if (i === guideStep) dot.className = "on";
    dots.appendChild(dot);
  });
  el("ds-gnext").textContent = guideStep === GUIDE.length - 1 ? "进入青溪渡" : "下一步";
}
el("ds-gnext").addEventListener("click", () => {
  if (guideStep < GUIDE.length - 1) { guideStep += 1; renderGuide(); return; }
  closeGuide();
});
el("ds-gskip").addEventListener("click", closeGuide);
function closeGuide() {
  el("ds-guide").hidden = true;
  try { localStorage.setItem("ds_guide_seen", "1"); } catch (e) { /* no-op */ }
}
el("ds-guide-btn").addEventListener("click", () => {
  guideStep = 0;
  renderGuide();
  el("ds-guide").hidden = false;
});

// ── 设定面板开关 ────────────────────────────────────────────────
el("ds-settings-btn").addEventListener("click", () => {
  renderSettings(lastPayload || {});
  el("ds-light-model").value = (lastPayload && lastPayload.light_model) || "";
  el("ds-settings").hidden = false;
});
el("ds-settings-close").addEventListener("click", () => {
  el("ds-settings").hidden = true;
});
el("ds-light-save").addEventListener("click", async () => {
  const word = el("ds-light-model").value.trim();
  const payload = await postJSON("/api/ds/settings/light_model", { word });
  if (payload && payload.ok) {
    setStatus("轻档已保存：调度/裁定将走「" + (word || "现役模型") + "」。");
  } else if (payload) {
    setStatus(payload.error || "轻档没有保存成功——再试一次。");
  }
});

// ── 轮询 ────────────────────────────────────────────────────────
async function readState() {
  const response = await fetch(API.state, { cache: "no-store" });
  return response.json();
}

async function driveButton(path, body, busyLine) {
  if (path === API.start) {
    await postDrive(path, body, busyLine);
    return;
  }
  await streamDrive(path, body);
}

// 顶栏不设「开始」钮：首次状态为 start 时在正文流里给一条入场行 +
// 「开始」按钮（世界还没有的时候，输入也可以先落下）。
function renderStartCard(payload) {
  if (payload.world && payload.world.exists) return;
  const inner = el("ds-inner");
  inner.textContent = "";
  const p = document.createElement("p");
  p.className = "ds-startline";
  p.textContent = "雾季的青溪渡还没有落笔——";
  const btn = document.createElement("button");
  btn.className = "btn btn--ink";
  btn.type = "button";
  btn.textContent = "开始（种下开局 · 起第一幕）";
  btn.addEventListener("click", () => driveButton(API.start, undefined,
    "种下开局、计划第一幕…（真实模型）"));
  p.appendChild(document.createElement("br"));
  p.appendChild(btn);
  inner.appendChild(p);
}

// 开篇钮：世界已种下、本章起了头而第一拍还没落——API.open 走 SSE
// 流式（与 advance 同一管线，beat 已有 "open" 分支）。建卡/收卡由
// render 的貌签守卫承担：kind==="opening"/can_open 在貌签里，开篇拍
// 落段后貌签变貌、重绘自然收卡（不再每拍重建）。
function renderOpenCard() {
  const inner = el("ds-inner");
  const p = document.createElement("p");
  p.className = "ds-startline";
  p.textContent = "本章起了头——";
  const btn = document.createElement("button");
  btn.className = "btn btn--ink";
  btn.type = "button";
  btn.textContent = "开篇（世界落第一笔）";
  btn.addEventListener("click", async () => {
    if (busy) { setStatus("上一步还在进行中（已用 " + elapsedSeconds() + " 秒）——等它跑完。"); return; }
    await streamDrive(API.open, undefined, "开篇拍落笔中……（真实模型）");
  });
  p.appendChild(document.createElement("br"));
  p.appendChild(btn);
  inner.appendChild(p);
}

// ── 轮询 ────────────────────────────────────────────────────────
function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    // busy（流式/阻塞驱动）期间不重绘——SSE 自己驱动，轮询只在不忙时对齐状态
    if (busy) return;
    try {
      const payload = await readState();
      if (payload && payload.world) render({ ...payload, ok: true }, false);
    } catch (error) { /* the next tick retries */ }
  }, POLL_MS);
}
function stopPolling() {
  if (pollTimer !== null) { window.clearInterval(pollTimer); pollTimer = null; }
}

// ── 启动 ────────────────────────────────────────────────────────
(async function boot() {
  try {
    const payload = await readState();
    render(payload, false);
    if (!seenGuide && payload.world && !payload.world.exists) {
      guideStep = 0;
      renderGuide();
      el("ds-guide").hidden = false;
    }
  } catch (error) {
    setStatus("状态读取失败——刷新页面重试。");
  }
  startPolling();
})();
