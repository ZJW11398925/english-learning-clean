// api.js —— 页面对全部读/写端点（含观察/历史/当前卡三个只读面）的唯一
// fetch 封装（F-G1；p-1 起随端点增长，不再数个数）。约定：每个函数收窄
// 参数、返回已解析的 JSON；网络失败或非 JSON 体原样抛出，由调用方的既有
// 失败姿态处理（一行人话，永不静默）。除本文件外页面任何代码不得直接调
// fetch（spec ⑦）。
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

/** 一轮对话：提交一句英语，拿回合信与教学批注。 */
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

/** 可练的表达清单（readiness R3+ 或 schedule 覆盖的供给目标）。 */
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

/** 点词卡查询（p-1）：q 是以点击词为中心、剥好标点的窗口串。 */
export function fetchWord(q) {
  return getJson("/api/word?q=" + encodeURIComponent(q));
}

/** 记忆读数（p-2）：关系记忆 / 剧情记忆 / 学习者状态 / 证据 / 删除台账。 */
export function fetchMemory() {
  return getJson("/api/memory");
}

/** 删除（p-2，不可逆）：scope 三词之一 + 该 scope 自己的键。
 *  CONVERSATION 可省 conversation_id（服务端补本页正在服务的对话）。 */
export function fetchDelete(payload) {
  return postJson("/api/delete", payload);
}

/** 目标读数（p-3）：组合 + 政策 + 本对话临时侧重 + 词表参考，一读全归。 */
export function fetchGoals() {
  return getJson("/api/goals");
}

/** 保存目标组合（p-3）：全组合 upsert，版本前移；409 = 冲突（重读再改）。 */
export function fetchSaveGoals(payload) {
  return postJson("/api/goals", payload);
}

/** 保存教学频率（p-3）：单列写；409 = 冲突（重读再改）。 */
export function fetchSaveFrequency(word) {
  return postJson("/api/teaching_frequency",
                  { teaching_frequency: word });
}
