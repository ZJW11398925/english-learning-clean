# 调研报告：词卡词表覆盖率——体验 P1-2 根因定量取证（2026-10-02）

> 执行者：调研执行者（executor-flash）。授权：v3-2 四查登记 §10.6「Revisit = v3-3 裁量（方向：miss 的一次性轻提示 / 词表扩容后的复测）」。
> 纪律：全程零仓内写盘（唯一例外 = 本报告文件）；content.db 仓外构建；用户 dogfood 库只读。
> 所有数字均为机器读数，复现命令见 §9。证据工作目录（仓外）：`D:\_wordcoverage\`。

## 0. 一句话结论

**词卡链路本身无缺陷；命中条件是「整条 lemma 短语以整词连续方式包含在点击词的 1–3 词窗口内」，而词表 100 条 lemma 中 98 条是多词短语、且无任何词形还原——在真实信件上按本次 35 封 dogfood 库信件实测，可点击词的命中率只有 14.5%（去重词 12.2%），miss 的 84% 以上由「常用词/功能词根本不在词表」造成。** 服务端加一个纯标准库的离线常用词小词典（top-2000 + 40 条缩写映射 + ~10 条朴素词形规则，数据 40–60 KB）即可把命中率抬到 **89.9%（top-5000 版 94.4%）**；配合「不可达词取消点词可供性」的呈现分层，体验上可达「**所有可点的词都必有卡**」。

---

## 1. 词表面四查（事件链事实）

### 1.1 数据源与请求链

| 环节 | 位置 | 事实 |
|---|---|---|
| HTTP 路由 | `src/elc/web.py:3455-3471` | `GET /api/word?q=<text>`；无 `q` ⇒ 400；miss 或 q 剥空 ⇒ **`{"found": false}` 200，永不为 404** |
| 查词实现 | `src/elc/web.py:1447-1524` `_word_lookup` | 只读 SELECT，遍历 `content_lexical_entry` 全表（100 行），对每条 lemma 做包含判定 |
| 命中判据 | `src/elc/web.py:1423-1444` | 两边同法 token 化（按空白切分 → 剥 43 字符边标点集 `_WORD_EDGE_CHARS` → `casefold`）；命中 = **lemma 的整条 token 串**作为连续整词子串出现在查询 token 串内（`_contains_run`）；最长 lemma 优先，同长取小 entity_id |
| 词形还原 | — | **不存在**。`content_form` 的 188 行屈折形态（PAST 31 / THIRD_PERSON_SINGULAR 29 / PRESENT_PARTICIPLE 22 / PLURAL 1 / …）**只在卡上展示，从不参与匹配**（实测：`"makes sense"`、`"made a decision"`、`"decisions"` 全部 miss） |
| 卡面内容 | `content_example` 220 行 / `content_sense` 100 行 / `content_text` 493 行 / `content_form` 188 行 | senses/examples/forms 均按 entity 取，≤2 例句（`_WORD_EXAMPLE_LIMIT`） |
| 前端分片 | `src/elc/webui/components.js:648`（letterWords） | `.say` 文本按空白切成 `span.word`；assistant 信按段落分 `.say`（components.js:40 `letterParagraphs` = `\n+` 切分），窗口**不跨段** |
| 前端查询 | `src/elc/webui/components.js:684`（wordWindows） | 以被点词为中心取 **1–3 词窗口**（3/2/1，长窗优先，去重）；**单次点击最多串行发 6 个请求**（实测分布：6 个请求的点击 483 次 / 均值 5.07） |
| 前端 miss | `src/elc/webui/app.js:2122-2144` + `:2073-2075` | 逐窗口 fetch，**首个 `found:true` 开卡；全部 miss = 静默**（规格 #15：`docs/FRONTEND_SPEC.md:181`「无 busy——命中即显，miss 按契约静默」）；fetch 异常也静默 |

### 1.2 词表现状（仓外构建 content.db 实测）

- `content_lexical_entry` = **100 行**（1 entity 恰 1 条 lexical_entry，来自 evidence 的 `lexical_entry` 块）。
- token 长度分布：**1 词 2 条**（`anyway`、`right`）、2 词 34、3 词 39、4 词 17、5 词 6、6 词 2 → **98/100 是多词短语**。
- **25 条 lemma 超 3 词**（最长 6：`the ball is in your court`）——被 1–3 词窗口**结构性不可达**（p-1 登记②已预言；components.js:617-619）。本次实测：这 25 条在当前 29 封英文信中出现 **0 次**，在语料文本（fixtures/教学句）中出现 **174 次**（`what do you mean`×14、`I hear you, but`×10、`I see your point, but`×10…）——教学 reveal 引用进信件后这些词照样点不开。
- 词表全部是**教学资源**（colloc/discourse/idiom/phrasal/frame/hedge/softener/pragmatic 的 lemma），**没有一个「日常词」条目**。

### 1.3 「一个词命中」的确切条件（重要推论）

点击词 hit ⟺ 存在一条 lemma，其**完整** token 串落进以被点词为中心的某个 1–3 词窗口内。推论（全部实测验证，§9 探针表）：

- 点 **`decision`** → miss（单 token 查询装不下 3-token lemma `make a decision`——包含方向是 lemma ⊆ query，不是 query ⊆ lemma）；点 `make a decision` 全短语或点短语中的词（窗口盖住全短语）→ hit。
- 任何**屈折变形**（`decisions` / `makes sense` / `made a decision`）→ miss。
- 单词点击能命中的只有 2 个单词 lemma：`anyway`、`right`（含边标点变体 `Anyway,` → hit，边标点剥离）。
- 弯撇号缩写（`it’s / can’t / you’re`，U+2019）→ miss：撇号在 token 中部不剥，词表与词典均无此形（dogfood 信件中弯撇号缩写 32 处 / 16 种，**直撇号 0 处**——模型输出用弯引号）。
- 纯中文 chunk（信件按空白切的整句）→ 必 miss（查询不是英语 token）。

---

## 2. 覆盖统计（机器读数）

### 2.1 语料库与口径

- **真实信件**：用户 dogfood 库 `D:\_d6b\app.db`（只读）`assistant_turn` 35 封 = **英文 29 + 中文 6**；英文信可点击 token 854 处、去重 688 种。
- **语料内文本**：`content_src` 的 595 条 detection fixtures + 220 条 content_example + 325 条教学形（reveal_form / canonical_forms / alternative_realizations）= 1,140 句。
- 模拟器逐条复刻 `wordWindows`（3/2/1、长窗优先、去重、按段）与 `_word_lookup`（整词连续包含、最长优先）语义；边标点字符集与 `web.py` **程序化比对一致**（43 字符集合相等）。
- 注：P1-2 四查取证的那封「36 去重词 1 命中」信件不在当前库快照中；形态最接近的是 L08（36 种去重词 / 4 命中，11.1%）。以下数字以本次 29 封为样本独立成立。

### 2.2 命中率总表（S1 = 现状基线）

| 文本域 | token 处命中 | 去重词命中 | 每封中位数 | 0% 信件 |
|---|---|---|---|---|
| 英文真实信件（29 封） | **124/854 = 14.5%** | **84/688 = 12.2%** | 12.9%（type） | **8/29 封全 miss** |
| 语料内文本（1,140 句） | 1,884/9,745 = 19.3% | 1,818/9,370 = 19.4% | 21.4%（token） | 564/1,140 句 |
| 中文真实信件（6 封） | 0/48 = 0% | 0/44 = 0% | 0% | 6/6 封 |

**语料内也只有 ~19%**：用户即使拿 fixtures 例句来聊，点词同样大面积静默。

### 2.3 miss 分型（英文信件，730 个 miss token 处）

| 类别 | 占比 | 例 |
|---|---|---|
| **B1 = 该词本身就是某 lemma 的内部 token**（a/the/you/to/it/i/that/me…），但窗口盖不住短语 | **44.9%** | `a`×15、`the`×31、`you`×41、`to`×29、`it`×12、`what`×12 |
| **C = top-2000 常用词**（词表里根本没有） | **32.7%** | `please`、`send`、`file`、`want`、`and`、`will`、`english`、`stop`、`complete`、`practice` |
| E = 其他（专名/低频/便签脚手架词） | 11.4% | `colleague`、`phrase`×14、`frustrating`、`correction`、`refusal` |
| D = top-5000 词 | 5.1% | `tonight`、`sounds`、`glad`、`expression`、`surprise` |
| （剥空）纯标点/占位符 span | 3.3% | `**“______!”**`、`-` |
| B2 = 真屈折 miss（还原后落进词表 token） | 2.6% | `says`、`going`、`making`、`means`、`meeting` |

去重词口径：202 个 miss 种类中 **131 种（64.9%）在 top-2000 词表内**（按出现次数计 82.2%）。**「常用词缺失」是压倒性根因，词形还原只占 2.6%。**

### 2.4 常用词表覆盖曲线（occurrence-weighted，对英文信件 token）

| 词表规模 | top-500 | top-1000 | top-2000 | top-3000 | top-5000 | top-10000 |
|---|---|---|---|---|---|---|
| 英文信件 | 63.7% | 74.1% | **82.0%** | 84.2% | 88.6% | 92.3% |
| 语料内文本 | 65.7% | 74.6% | 83.7% | 87.6% | 91.5% | 94.9% |

（词频表 = google-10000-english 排序表，仓外抓取；曲线只说明「日常信件 token 落在常用词表内的比例」，未含教学短语贡献。）

### 2.5 扩容情景对照（修正口径：词典命中只看**被点词**）

| 情景 | 内容 | token 处命中 | 去重词命中 |
|---|---|---|---|
| S1 | 现状（100 条短语 lemma） | 14.5% | 12.2% |
| S2 | S1 + 匹配器词形还原容忍 | 14.5%（**零增益**） | 12.2% |
| S3' | S1 + top-2000 词典（被点词 + 朴素还原） | 86.7% | 84.4% |
| **S3''** | **S3' + 40 条缩写映射（it’s→it is…）** | **89.9%** | **88.4%** |
| **S4'** | **top-5000 词典 + 缩写映射** | **94.4%** | **93.5%** |

- S2 为什么否：在真实信件上**一个百分点都不涨**（信件里短语出现即原形，词形 miss 只占 2.6% 且集中在单词上）；同时它把 **40 条 fixture 文本**从 no-hit 翻成 hit，并破坏 `make senses` ≠ `make sense` 的边界设计（探针：S1=False → S2=True）。**匹配器级词形还原 = 代价全收、收益为零，否决。**
- S3''/S4' 残余 miss（36 种去重词）= 信件脚手架词（`Hint:`/`Correction:`/`Surprise:`/占位符）、专名（`Lisbon`）、低频词（`colleague`/`disbelief`/`refusal`/`frustrating`…）——正是「不应显示点词可供性」的那部分（见 §3(b)）。
- 中文信件在 S3'' 下 27.1%：命中的全是夹在中文句里的英文示例词；22 个纯中文 chunk 结构性永远 miss（词卡是英语学习面，中文应直接不做点词可供性）。
- **过程披露**：第一轮情景实现有一处语义错误——词典命中检查了窗口内**任意** token（等价于点 `can’t` 靠邻词 `and` 命中），得出 99.6% 的虚高读数；已修正为「词典命中只看被点词」，本节全部为修正后数字。错误口径的 99.6% 不作为任何依据。

---

## 3. 扩容方案（施工级）

### (a) 语料面扩容——容量与代价：**否决大规模路线**

- 结构容量：`lexical_entry` 与 entity **严格 1:1**（evidence 的 `lexical_entry` 是单对象块；build.py:1722-1726、2822-2829）。**加词 = 加实体**。
- 单实体成本（本仓实绩）：c2-b 新增 19 实体 = +5,987/−288（62 文件）；c3-a 新增 18 实体 = +5,816/−315（61 文件）→ **约 310–325 净增行/实体**（19 键 evidence + 三词 fixtures + link + audits 全套）。
- 量级换算：覆盖到 top-2000 需 ~1,900 个新实体 ≈ **59–62 万行**（≈ 30+ 个 C2/C3 量级的刀）；即便只补 top-500 也要 ~400 实体 ≈ 12–13 万行。
- 语义错位：功能词/常用词（`the`/`want`/`please`）**不是可教学资源**——硬塞进 resource 实体会虚增 readiness 阶梯、CORE_A 计数与 credit 面（R-C1-credit 域），污染 Calibration100 的语义。
- **结论：语料面只保留一个可选小尾巴**——待词典层上线后，按真实点击日志定向补**高频被点低频词**的词条（如 `phrase`/`colleague` 级，每次内容刀顺手，零星进入），不做规模扩容。

### (b) miss 呈现——**推荐「可供性分层」，而非「miss 提示」**

基线下 85% 的点击以 6 个请求换一声不响；逐次 toast/浮层提示在当前命中率下是噪声灾难（每封信会弹几十次），**不建议**。推荐两层：

1. **主案：点词可供性分层（affordance gating）**。信件渲染时（或按 turn 批量）由服务端/本地用与 §1 完全相同的窗口+匹配语义预计算每封的**命中位图**（实测成本 3.3 ms/封，纯 Python，O(token×6 窗×词表)）：
   - 有命中可能的 token → 保留现 `span.word` 供性（hover 点线/按压即亮/触屏弱底纹，全部现役件）；
   - 无命中可能的 token（词典外词、纯中文 chunk、纯标点/占位符、脚手架词）→ 渲染为普通文本，**不显示任何点词供性**。
   - 效果：**用户可点的词 100% 开卡**——「miss 静默」从「体验缺陷」降级为「不可达面根本不出现」。规格 #15 的负钉「全文常显点线永禁」不受影响（这是收紧供性，不是扩大）；契约变更点是「`.word` 供性不再覆盖全部文本」，属 R7 域、需用户首验。
   - 落点：信件 payload 增加命中位图（或新只读端点批量给最近 N 封的位图）；`letterWords`/`app.js` 点击委派加「无供性则不拦截」短路。客户端算（同一套规则移植 JS）与服务端算（位图随信下发）二选一，**倾向随信下发**（单一事实源，避免 JS/Python 双实现漂移）。
2. **辅案（可选，一次性教学提示）**：每会话首次 miss 点击时给一条内联小字提示（如「点短语中的词可查教学卡」），仅出现一次。是否需要由用户首验裁决；主案落地后其必要性存疑。

### (c) 兜底层——离线常用词小词典：**可行且便宜**

- **形态**：纯标准库单模块（建议 `src/elc/platform/lexicon.py` 或 webui 侧），三件套：
  1. **top-2000 词表 → 简注**（词条：词 + 词性 + 中文简注）；
  2. **缩写映射** ~40 条（`it’s→it is`、`can’t→can not`…，同时解决弯/直撇号：查询 token 化时 `’→'` 归一，2 行）；
  3. **朴素词形还原** ~10 条后缀规则（s/es/ies/ed/ing，无例外表——不规则形 `was/got/went` 本身多在 top-2000 内，天然覆盖）。
- **体量**：top-2000 裸词表 13.6 KB；含中文简注（10–20 字/条）≈ **40–60 KB**；缩写映射 <1 KB。作为数据文件或模块常量都可，零依赖、零网络。
- **接线**：`_word_lookup` 在 content 词表 miss 后落词典层，返回**带层级标记**的第二档卡（`source: lexicon`：词头 + 词性 + 简注，无 senses/examples/forms——不冒充教学卡）。**零 schema 变更、零 CONTENT_DB_VERSION bump、零 readiness/credit/detection 语义声称**（纯显示面），不触任何冻结面。
- **中文简注的代价与选项**：手写 2,000 条 ≈ 数十作者小时；可选分档——首刀只上「词 + 词性 + 无简注」或「top-500 带简注」，后续批补。词典命中 ≠ 有教学卡，这点在卡面要诚实区分。
- **预期读数**（对本次真实信件样本）：top-2000 + 缩写 = **89.9% / 88.4%**；top-5000 + 缩写 = **94.4% / 93.5%**。残余 5.6–10% 由 §3(b) 主案接管为「无供性」。

---

## 4. v3-3 推荐组合（可执行）

| # | 改动 | 位置 | 量级 | 预期效果 |
|---|---|---|---|---|
| 1 | 撇号归一（`’→'`） | `web.py` `_word_tokens` | ~2 行 | 缩写词可统一进词典键 |
| 2 | 离线小词典 + 朴素还原 + 缩写映射 + `_word_lookup` 兜底（返回 `source` 层级） | 新 `src/elc/platform/lexicon.py`（或同族）+ `web.py` 兜底分支 | 模块 ~150–250 行（含 docstring）+ 数据 40–60 KB + 接线 ~20–40 行 | 真实信件命中 **14.5% → 89.9%**（top-2000）/ 94.4%（top-5000） |
| 3 | 词卡第二档形态（lexicon 来源的小卡：词头+词性+简注） | `webui` #15 组件 + spec | 小刀 | 词典命中有诚实卡面 |
| 4 | 点词可供性分层（命中位图随信下发 + 无供性 token 不渲染为可点） | `web.py` payload / `components.js` / `app.js` + spec #15 契约变更（R7，**需用户首验**） | 中刀 | 残余 miss 不再被点击，「可点必有卡」 |
| 5 | （可选）一次性 miss 教学提示 | `app.js` | ~10 行 | 用户首验后裁决 |
| 不做 | 匹配器词形还原容忍（S2） | — | — | 实测零增益 + 破坏 40 fixtures 与 `make senses` 边界 |
| 不做 | 语料面规模扩容至常用词 | — | — | ~310–325 行/实体，59 万行级成本 + 语义污染 |
| 缓做 | 中文信件词卡 | — | — | 词卡是英语面；中文 token 直接无供性（#4 覆盖） |

组合后的体验闭环：**常用词开小卡（~90%+），教学短语开教学卡（现链路不动），词典外词不可点不再静默失败**。若词表/词典后续扩到 top-5000，读数再 +4.5 个百分点。

---

## 5. 边界、风险与开放问题

1. **`make senses` 边界**：词典/还原层只作用于**单词**查询兜底，不进短语包含判定——本调研的 S3/S4 语义即如此实现（单词窗口才落词典），boundary 保持。v3-3 施工时须把这条写进验收钉。
2. **p-1 登记①（命中可不含被点词）**：本调研未改窗口语义；分层供性按「该词存在任一命中窗口」计算，与现行为一致。是否收紧为「命中须含被点 token」仍是独立产品裁决。
3. **「命中 ≠ 有用卡」**：top-2000 命中给的是词典型小卡；教学卡仍只来自 100 条资源。卡面必须 visibly 区分两档，避免把简注误当教学。
4. **信件脚手架词**（`Hint:`/`Correction:`/`**…**`）是 persona 提示语的形态产物：分层供性会天然把它们排除；若要更干净，可在 persona 侧约定脚手架记号，属另一刀。
5. **样本局限**：29 封英文信来自单一 dogfood 会话（教学密集型对话）；随真实使用多样化，比例会浮动，但「常用词缺失为根因」的结构性结论对样本不敏感（语料内文本同样只有 19.3%）。
6. **词频表外来性**：google-10000-english 是通用英语频率表（美式拼写、无缩写词）；作为词典键集适用，若要中文注释的取舍与词表版权（该表为公有域风格词表，逐词注解为本仓自产）由总控裁量。
7. **隐私**：报告只含聚合读数与单词级例子，未引用任何信件原文。

## 6. 异议区

- **无（对本任务书）**。两点口径自查披露：① 第一轮情景实现的词典命中口径错误（窗口任意 token 命中即算），已修正并全文采用修正口径，错误口径读数（99.6%）已在 §2.5 声明作废；② P1-2 四查的原始信件不在当前库快照，无法逐词复核「36/1」，已用同库 29 封独立复核并如实登记（§2.1 注）。

## 7. 遗留与风险

- **共享工作树观察（非本刀产物，留痕免责）**：本调研执行期间，同一工作树有并行改动在落——`src/elc/webui/app.js`（+195/−62）、`src/elc/webui/components.js`（+8）被修改（mtime 23:43–23:48），diff 全部位于信封/起笔（v3-2R compose）面，`git diff` 确认与词卡路径（`letterWords`/`wordWindows`/`wordCard`/`/api/word`）**零交集**；另有三份同日调研报告（cs3 / v3-frontend / v3-1 teaching-card）为 untracked 并行产物。本刀对仓内只写了本报告一个文件（Write @ 23:48:06），未触碰上述任何文件；本刀对 app.js/components.js/web.py 的全部读取早于并行改动落盘时点，读数不受影响。
- 模拟器/分析脚本在仓外 `D:\_wordcoverage\`（`simulate.py` / `analysis.py` / `scenarios.py` / `verify.py` + `content.db` + `google-10000-english.txt` + `analysis_out.txt`），**未入仓**；v3-3 施工时验收钉应以本报告 §9 命令重算为准，若总控认为脚本值得入库可另行授权。
- 中文简注的作者工时与词表选型（top-2000 vs top-5000 vs 先无简注）是用户可裁决项，本报告给齐了三档读数。

## 8. 结论复述（回答任务书四问）

1. **词表面**：`/api/word` = content.db `content_lexical_entry`（100 条教学短语 lemma）整词连续包含匹配，无词形还原，`content_form` 只展示；命中还要求被点词处于盖住整条 lemma 的 1–3 词窗口内；miss = 200 `{"found":false}` + 前端静默（#15 契约）。
2. **覆盖**：真实信件 14.5%/12.2%，语料内 19.3%；miss 的 82%（按次数）是 top-2000 常用词/功能词缺失，44.9% 的 miss 甚至本身就是词表短语内部的词；屈折只占 2.6%；中文信 0%。
3. **扩容**：语料面 ~310–325 行/实体不可行也不合语义；miss 呈现推荐「供性分层」而非逐次提示（#15 契约变更、用户首验）；离线小词典（top-2000+缩写+朴素还原，40–60 KB 纯标准库）完全可行。
4. **推荐组合**：§4 五项（2+4 为主力）——预期真实信件命中 14.5% → **89.9%（top-2000）/ 94.4%（top-5000）**，供性分层后「可点必有卡」。

---

## 9. 证据与复现

工作目录 `D:\_wordcoverage\`（仓外）。关键复现命令（Git Bash）：

```bash
# 1) 仓外构建 content.db（与 web 服务同形的 CLI 产物）
cd /d/_wordcoverage && PYTHONPATH=/d/english-learning-clean/src \
  python -c "import sys; sys.argv=['build','--out','D:/_wordcoverage/content.db']; from elc.content.build import main; main()"
# → content.db built: entities=105, capabilities=5, links=100, evidence=100

# 2) 探针（真实 _word_lookup 对真实产物）
python - <<'EOF'
import sys, sqlite3
sys.path.insert(0,"D:/english-learning-clean/src")
from elc.web import _word_lookup
conn=sqlite3.connect("file:D:/_wordcoverage/content.db?mode=ro",uri=True)
for q in ["decision","decisions","make a decision","made a decision","makes sense",
          "make senses","anyway","Anyway,","it’s","got it","the","you","right","heavy rain","rain"]:
    print(repr(q), _word_lookup(conn,q).get("found"))
EOF
# → decision/decisions/made a decision/makes sense/make senses/it’s/the/you/rain = False；
#   make a decision/anyway/Anyway,/got it/right/heavy rain = True

# 3) 覆盖统计与情景（脚本按 §2 口径）
python -W ignore analysis.py    # S1/S2 + miss 分型 + top-N 曲线 + fixture 翻转
python -W ignore scenarios.py   # 修正口径 S3'/S3''/S4' + 杠杆归因 + 残余清单
python -W ignore verify.py      # 边界探针（make senses）+ 窗口上限计数 + 残余 miss
```

数据源：`content_src/`（105 实体）、`D:\_d6b\app.db`（只读，35 封信）、google-10000-english.txt（10,000 词频率序表，仓外抓取自 first20hours/google-10000-english）。
