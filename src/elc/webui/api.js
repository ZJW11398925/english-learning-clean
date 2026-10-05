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

async function putJson(path, payload) {
  const res = await fetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

async function getJson(path) {
  const res = await fetch(path);
  return res.json();
}

async function deleteJson(path) {
  const res = await fetch(path, { method: "DELETE" });
  return res.json();
}

/** 一轮对话：提交一句英语，拿回合信与教学批注。 */
export function fetchTurn(text) {
  return postJson("/api/turn", { text: text });
}

/** 流式一轮（A1）：POST /api/turn_stream——每个 delta 当场回调
 *  onDelta(text)，流走完以 final 载荷（旧 /api/turn 的全量形状）兑现。
 *  A2（DEC-…82）：世界故事先讲——事件序 world → delta＊ → final；
 *  首个 {"type":"world"} 帧当场回调 onWorld(event)（世界名/虚拟历日
 *  期行/本轮便条），没有世界腿的流就没有这一帧。返回 null = 对端没按
 *  SSE 回答（调用方回退旧 POST）；抛错 = 请求已经开始后中断
 *  （err.started 区分：流真开始过才为 true——调用方对 started 的中断
 *  不重发信，拉历史对齐）。解析是防御性的：只认「data: 」行，坏行/
 *  坏 JSON 一律跳过、解析本身永不抛。 */
export async function fetchTurnStream(text, onDelta, onWorld) {
  let res;
  try {
    res = await fetch("/api/turn_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    });
  } catch (err) {
    err.started = false;
    throw err;
  }
  if (!res.ok || !res.body) return null;
  const interrupted = new Error("流式回应中断了");
  interrupted.started = true;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final = null;
  try {
    for (;;) {
      const step = await reader.read();
      if (step.value) buffer += decoder.decode(step.value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const line = frame.split("\n")
          .find((candidate) => candidate.startsWith("data: "));
        if (!line) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }
        if (event && event.type === "delta"
            && typeof event.text === "string") {
          onDelta(event.text);
        } else if (event && event.type === "world") {
          if (onWorld) onWorld(event);
        } else if (event && event.type === "final") {
          final = event;
        }
      }
      if (step.done) break;
    }
  } catch (err) {
    throw interrupted;
  }
  if (final === null) throw interrupted;
  return final;
}

/** 教学回应（五个控制词之一：skip / attempt / hint / reveal / explanation）。 */
export function fetchTeachingReply(payload) {
  return postJson("/api/teaching_reply", payload);
}

/** 学习视图的唯一动作：请 runtime 立刻开教这个目标。 */
export function fetchTeachMe(targetId) {
  return postJson("/api/teach_me", { target_id: targetId });
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

/** 世界收件箱（W-1-3）：绑定世界的原子揭示 + 便条全列 + 最近信件 +
 *  at_checkpoint 位。无绑定世界服务端 404 人话（页面对 error 隐藏整区）。 */
export function fetchWorldInbox() {
  return getJson("/api/world/inbox");
}

/** 世界一屏读（wf-1）：世界名 + 派生故事日（服务端已按界面语言本地化，
 *  并带世界名尾）+ 今日动静块（静日 quiet:true + 人话句 / 有则 items）+
 *  本通信的居民位（可 null——世界的自述）。无绑定世界同样是 404 人话
 *  （error 对象由调用方判形回落——fetchWorldInbox 同法）。 */
export function fetchWorldOverview() {
  return getJson("/api/world/overview");
}

/** 世界居民名册（wf-1）：cast⨝卡（name/identity/persona_id）+
 *  is_current 反查 + 每居民的诚实信数（没写过就是 0）。无绑定世界
 *  404 人话（error 对象由调用方判形——沓回落现役语境，不发明世界名）。 */
export function fetchWorldResidents() {
  return getJson("/api/world/residents");
}

/** 历史窗口（默认最后 50 轮，已交付的助手输出）。主线-2 起宽度可显式
 *  指定：opts.full 取全文，opts.limit 取最近 n 轮——不带 opts 一字不变。 */
export function fetchHistory(opts) {
  const query = [];
  if (opts && opts.full) query.push("full=1");
  if (opts && opts.limit) query.push("limit=" + String(opts.limit));
  return getJson("/api/history" + (query.length ? "?" + query.join("&") : ""));
}

/** 复习调度区读数（主线-2）：Scheduler 自己的分档视图（到期/已过期/
 *  未到期），调度腿未装配时 available=false 如实。 */
export function fetchSchedule() {
  return getJson("/api/schedule");
}

/** 表达足迹（主线-2）：一个表达的 ACTIVE 学习证据按轮分布；没有证据
 *  的表达 found=false 如实空。 */
export function fetchTargetFootprint(targetId) {
  return getJson("/api/target_footprint?id="
                 + encodeURIComponent(targetId));
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

/** 笔友档案读数（cs-2）：角色卡叙事面（真源在服务端单一出处）+
 *  通信统计 + 她记得的事 + 近况。 */
export function fetchPartner() {
  return getJson("/api/partner");
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

/** 角色名册（mc-0）：全部卡片（内置在前）+ 本页正服务的
 *  current_character_id（可能为 null——如实，不猜）。 */
export function fetchCharacters() {
  return getJson("/api/characters");
}

/** 信封切换（mc-0）：此后由该角色自己的会话服务本页——历史、批注、
 *  档案全部随下一次请求落在新通信上。 */
export function fetchSwitchCharacter(characterId) {
  return postJson("/api/characters/switch", { character_id: characterId });
}

/** 笔友档案读数（mc-1 参数化面）：一位角色的卡与它自己通信的统计/
 *  记忆/近况。不带参数的原面仍是 fetchPartner（正服务的角色）。 */
export function fetchPartnerOf(characterId) {
  return getJson("/api/partner?character_id="
                 + encodeURIComponent(characterId));
}

/** 新建空白信封（mc-0 CRUD 面）：name 必填，其余散文面可选；超长
 *  是 400 人话（服务端 F-2 上限），错误句原样上浮。 */
export function fetchCreateCharacter(fields) {
  return postJson("/api/characters", fields);
}

/** 全字段保存（mc-2 编辑台）：PUT 只送送出的面——服务端对没送的面
 *  原样不动（mc-0 的更新文法），所以「读不回的四面」不送即保留。
 *  400 人话（超上限等）已中文化，错误句原样上浮。名字的改写也从这
 *  里走（mc-1 的信封内改名随编辑台退役——api.js 不留无人调用的封装）。 */
export function fetchUpdateCharacter(characterId, fields) {
  return putJson("/api/characters/" + encodeURIComponent(characterId),
                 fields);
}

/** 删除一张用户卡（mc-2 编辑台）：内置卡服务端 409 拒（页面也不给
 *  内置卡这个钮）；删除后退沓，已写的信留在信档。 */
export function fetchDeleteCharacter(characterId) {
  return deleteJson("/api/characters/" + encodeURIComponent(characterId));
}

/** 设置读数（主线-1）：当前档 + 教学策略十三列 + 披露规则，一读全归；
 *  词表（频率四词 + 八旋钮白名单）由服务端随行，客户端零拷贝。 */
export function fetchSettings() {
  return getJson("/api/settings");
}

/** 保存教学策略旋钮（主线-1）：八旋钮全组 upsert，版本前移；
 *  409 = 冲突（重读再改）；mode 等系统列与词表外值都是 400 人话。 */
export function fetchSaveTeachingPolicy(payload) {
  return postJson("/api/settings/teaching_policy", payload);
}

/** 保存披露规则（fr-A）：全规则集 upsert，revision 前移；409 = 冲突
 * （重读再改）；重复 persona 行与词表外层级都是 400 人话。 */
export function fetchSaveDisclosure(payload) {
  return postJson("/api/settings/disclosure", payload);
}

/** 换教学模式（veto-R）：§12 档位词一枚（case-sensitive，服务端
 * mode_words 随行）——持久化 + 热改生效（下一轮就在这一档）；
 * 词表外值是 400 人话。 */
export function fetchSaveMode(stage) {
  return postJson("/api/settings/mode", { stage: stage });
}

/** 换模型端点/模型名（用户否决驱动的 provider 面）：一键或两键，非空的
 * base_url 须是完整 http(s) 地址；持久化 + 热换 provider——下一封信就
 * 走新端点，重启后仍以这里的值为准（启动参数让位）。密钥不在此面
 * ——仍由启动环境提供。非 OpenAI 装配 200 + accepted:false 人话。 */
export function fetchSaveProvider(payload) {
  return postJson("/api/settings/provider", payload);
}

/** 换界面语言（W-L）："zh" | "en" 一词——持久化，下一次收件箱读就
 *  按它渲染（读即揭示）。词表外值是 400 人话。 */
export function fetchSaveUiLanguage(word) {
  return postJson("/api/settings/ui_language", { ui_language: word });
}

/** 换回信语言（W-L）："zh" | "en" | "follow" 一词——持久化，下一封
 *  信的 prompt 带上它的 language 行（coordinator 每轮现读，免重装）。
 *  词表外值是 400 人话。 */
export function fetchSaveReplyLanguage(word) {
  return postJson("/api/settings/reply_language", { reply_language: word });
}

/** 多模型配置档（用户定向：存多套模型随时切换）：把当前三件存成一个
 * 具名配置档（id 省略 = 新建；api_key 省略 = 沿用该档已存的）。 */
export function fetchSaveProviderProfile(payload) {
  return postJson("/api/settings/provider/profile", payload);
}

/** 切换到某个配置档：密钥先落 → 热换 → pair + 指针——下一封信即走
 * 该档；重复切换幂等零写。 */
export function fetchActivateProviderProfile(profileId) {
  return postJson("/api/settings/provider/profile_activate",
                  { id: profileId });
}

/** 删除一个配置档（幂等；删现役档不动活配置——指针归自定义）。 */
export function fetchDeleteProviderProfile(profileId) {
  return postJson("/api/settings/provider/profile_delete",
                  { id: profileId });
}
