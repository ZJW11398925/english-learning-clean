// api.js —— 页面对六个读/写端点（含观察/历史/当前卡三个只读面）的唯一
// fetch 封装（F-G1）。约定：每个函数收窄参数、返回已解析的 JSON；网络
// 失败或非 JSON 体原样抛出，由调用方的既有失败姿态处理（一行人话，永不
// 静默）。除本文件外页面任何代码不得直接调 fetch（spec ⑦）。
//
// 零外链纪律：本文件不出现任何站外地址；一切请求都是同源相对路径。

async function postJson(path, payload) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

async function getJson(path) {
  const res = await fetch(path);
  return res.json();
}

/** 一轮对话：提交一句英语，拿回合信与教学时刻。 */
export function fetchTurn(text) {
  return postJson("/api/turn", { text: text });
}

/** 教学回应（五个控制词之一：skip / attempt / hint / reveal / explanation）。 */
export function fetchTeachingReply(payload) {
  return postJson("/api/teaching_reply", payload);
}

/** 学习视图的唯一动作：请 runtime 立刻开教这个目标。 */
export function fetchTeachMe(targetId) {
  return postJson("/api/teach_me", { target_id: targetId });
}

/** 五问诊断读数（每面板独立守卫，错误在面板槽内）。 */
export function fetchDiagnostics() {
  return getJson("/api/diagnostics");
}

/** 学习视图读数（日程 / 目标 / 证据）。 */
export function fetchLearning() {
  return getJson("/api/learning");
}

/** 可教目标清单（readiness R3+ 或 schedule 覆盖的供给目标）。 */
export function fetchTargets() {
  return getJson("/api/targets");
}

/** 观察读数（与 observations 命令同一读数核心）。 */
export function fetchObservations() {
  return getJson("/api/observations");
}

/** 历史窗口（最后 50 轮，已交付的助手输出）。 */
export function fetchHistory() {
  return getJson("/api/history");
}

/** 只读当前教学卡（W-4 即时面；不走工作队列）。 */
export function fetchCurrentMoment() {
  return getJson("/api/teaching/current");
}
