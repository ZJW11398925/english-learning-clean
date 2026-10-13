// reader.js —— V3 试读面（/v3）的唯一脚本（V3-8e）。
//
// 纪律：零依赖、零外链、零内联样式；DOM 一律 createElement +
// textContent（不拼 HTML 串）；每一次驱动（continue/submit/…）是一个
// 长请求（真实模型一段可能 10–60 秒），页面在此期间以定时轮询
// /api/v3/state 呈现进度——state 路由在服务端脱队读（自己的只读连接），
// 不会被驱动阻塞。渲染后对新增 passage 发一次 ack（record_exposure 的
// 页面侧：渲染即曝光；与对话/提交解耦）。

const API = {
  state: "/api/v3/state",
  start: "/api/v3/start",
  continue_: "/api/v3/continue",
  submit: "/api/v3/submit",
  settle: "/api/v3/settle",
  nextChapter: "/api/v3/next_chapter",
  ack: "/api/v3/ack",
};

const POLL_MS = 3000;

const el = (id) => document.getElementById(id);

let busy = false;          // one drive in flight at a time
let lastAttempt = null;    // {id, intent, option} — a retry reuses it
const acked = new Set();   // passage ids this page already acknowledged
let pollTimer = null;

async function post(path, body) {
  const options = { method: "POST", headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  return response.json();
}

async function readState() {
  const response = await fetch(API.state, { cache: "no-store" });
  return response.json();
}

function mintSubmissionId() {
  return "web-v3-" + Date.now().toString(36) + "-" +
    Math.random().toString(36).slice(2, 8);
}

function setStatus(text) {
  el("reader-status").textContent = text || "";
}

function setWorld(payload) {
  const world = payload.world;
  if (!world || !world.exists) {
    el("reader-world").textContent = "世界还没有种下";
    return;
  }
  const tick = world.current_tick;
  el("reader-world").textContent =
    (world.name || world.world_id) +
    (tick === null || tick === undefined ? "" : "　tick " + tick);
}

function renderFlow(payload) {
  const flow = el("reader-flow");
  flow.textContent = "";
  const passages = payload.passages || [];
  passages.forEach((passage, index) => {
    const article = document.createElement("article");
    article.className = "reader-passage";
    const meta = document.createElement("p");
    meta.className = "reader-meta";
    meta.textContent = "第 " + (index + 1) + " 段 · " +
      passage.scene_id + " · #" + passage.segment_seq;
    const body = document.createElement("p");
    body.className = "say";
    body.textContent = passage.body;
    article.appendChild(meta);
    article.appendChild(body);
    flow.appendChild(article);
  });
  const fresh = passages
    .map((passage) => passage.passage_id)
    .filter((id) => !acked.has(id));
  if (fresh.length > 0) {
    fresh.forEach((id) => acked.add(id));
    post(API.ack, { passage_ids: fresh }).catch(() => {
      fresh.forEach((id) => acked.delete(id)); // a failed ack retries
    });
  }
}

function renderGate(payload) {
  const gate = el("reader-gate");
  const next = payload.next || {};
  if (next.kind !== "gate") {
    gate.hidden = true;
    return;
  }
  gate.hidden = false;
  const options = el("reader-options");
  options.textContent = "";
  el("reader-gate-head").textContent = next.detail || "故事在这里停住，等你";
  (next.gate_options || []).forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn--pencil";
    button.textContent = option;
    button.addEventListener("click", () => submit(option, option));
    options.appendChild(button);
  });
}

function renderControls(payload) {
  const controls = payload.controls || {};
  el("reader-start").disabled = busy || !controls.can_start;
  el("reader-continue").disabled = busy || !controls.can_continue;
  el("reader-end-scene").disabled = busy || !controls.can_end_scene;
  el("reader-settle").disabled = busy || !controls.can_settle;
  el("reader-next").disabled = busy || !controls.can_next_chapter;
  el("reader-submit").disabled = busy;
}

function fillGroup(box, title, rows) {
  box.textContent = "";
  const head = document.createElement("b");
  head.className = "kvtitle";
  head.textContent = title;
  box.appendChild(head);
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "kv";
    const key = document.createElement("b");
    key.textContent = label + "：";
    const cell = document.createElement("span");
    cell.textContent = String(value);
    row.appendChild(key);
    row.appendChild(cell);
    box.appendChild(row);
  });
}

function renderReadout(payload) {
  const planBox = el("reader-plan");
  planBox.textContent = "";
  if (payload.plan) {
    fillGroup(planBox, "本章计划", [
      ["版本", "r" + payload.plan.plan_revision],
      ["目标", payload.plan.goal],
      ["场次", payload.plan.scene_count + " 场"],
      ["预算窗口", payload.plan.planned_start_tick + " → " +
        payload.plan.planned_end_tick],
    ]);
  }
  const settlementBox = el("reader-settlement");
  settlementBox.textContent = "";
  if (payload.settlement) {
    const lines = payload.settlement.summary
      ? payload.settlement.summary.split("\n").length + " 条"
      : "0 条";
    fillGroup(settlementBox, "本章结算", [
      ["落账时间线", lines],
      ["摘要", payload.settlement.summary || "（空）"],
    ]);
  }
}

function render(payload) {
  if (!payload) return;
  if (payload.ok === false && payload.error) setStatus(payload.error);
  else setStatus((payload.next && payload.next.detail) || "");
  setWorld(payload);
  renderFlow(payload);
  renderGate(payload);
  renderControls(payload);
  renderReadout(payload);
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    try {
      const payload = await readState();
      // The world's own progress — render it while the drive runs; the
      // drive's response re-renders the authoritative payload after.
      if (payload && payload.world) render({ ...payload, ok: true });
    } catch (error) { /* the next tick retries */ }
  }, POLL_MS);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function drive(path, body, busyLine) {
  if (busy) return;
  busy = true;
  setStatus(busyLine);
  renderControls({ controls: {} });
  startPolling();
  let payload = null;
  try {
    payload = await post(path, body);
  } catch (error) {
    payload = { ok: false, error: "这一请求没有得到服务器的回答——再试一次。" };
    try {
      payload = { ...(await readState()), ok: false, error: payload.error };
    } catch (inner) { /* keep the sentence above */ }
  } finally {
    stopPolling();
    busy = false;
  }
  render(payload);
}

async function submit(optionText, optionWord) {
  if (busy) return;
  const typed = el("reader-intent").value.trim();
  const intent = typed || optionText || "";
  if (!intent) {
    setStatus("先写下你要说的话，或点一个自然举动。");
    return;
  }
  if (lastAttempt === null || lastAttempt.intent !== intent) {
    lastAttempt = { id: mintSubmissionId(), intent, option: optionWord || null };
  }
  const body = {
    submission_id: lastAttempt.id,
    intent_text: intent,
  };
  if (lastAttempt.option !== null) body.selected_option = lastAttempt.option;
  busy = true;
  setStatus("裁定与续写中…（真实模型，可能 10–60 秒）");
  startPolling();
  let payload = null;
  try {
    payload = await post(API.submit, body);
    if (payload && payload.ok === false && payload.error &&
        payload.error.indexOf("durable 面优先") !== -1) {
      // The durable face already holds this gate's submission — the
      // honest retry is the empty body (the server's own sentence says
      // so). One automatic retry, once per click.
      payload = await post(API.submit, {});
    }
  } catch (error) {
    payload = { ok: false, error: "提交没有得到服务器的回答——再试一次。" };
  } finally {
    stopPolling();
    busy = false;
  }
  if (payload && payload.ok) {
    el("reader-intent").value = "";
    lastAttempt = null;
  }
  render(payload);
}

el("reader-start").addEventListener("click", () =>
  drive(API.start, undefined, "种下世界、起第一幕…（真实模型）"));
el("reader-continue").addEventListener("click", () =>
  drive(API.continue_, {}, "写下下一段…（真实模型，可能 10–60 秒）"));
el("reader-end-scene").addEventListener("click", () =>
  drive(API.continue_, { end_scene: true }, "收束本场…（真实模型）"));
el("reader-settle").addEventListener("click", () =>
  drive(API.settle, undefined, "结束本章、落结算…"));
el("reader-next").addEventListener("click", () =>
  drive(API.nextChapter, undefined, "导演起新的一幕…（真实模型）"));
el("reader-submit").addEventListener("click", () => submit(null, null));

readState().then(render).catch(() => setStatus("状态读取失败——刷新页面重试。"));
