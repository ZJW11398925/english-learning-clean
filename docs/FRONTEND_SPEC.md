# FRONTEND_SPEC — 前端架构与规范（F-G1 · v2 重写版）

状态：**非 canonical**（经 `DEC-OPI-631452f9-…37` 授权设立的工程规范文档；
2026-10-02 经 `DEC-OPI-10bbc3c8-…3` 授权以 v2 设计内核简报为唯一权威源
全文重写）。
服从对象：`docs/` 六 canonical 文档、`docs/research/2026-10-01-v2-mature-core-brief.md`
（v2 设计唯一权威源，下称「简报」）与用户裁决；本文件的 R7 域（命名法、
组件契约措辞、规范条款）由执行者拟定、用户首验否决。适用对象：
`src/elc/webui/`（本仓唯一前端面）及其一切后续改动。

## ① 地位与治理

1. 本文件**不是 canonical**：与六 canonical 冲突时，六 canonical 胜；
   与简报冲突时，简报胜（R1 权威序：简报 > v2-1 实现现状 > 本文件旧文；
   实现与简报有出入时以实现为准并在本文件注记，不反向改代码）。
   与用户裁决冲突时，用户裁决胜。
2. 前端改动的**唯一合法路径**：先查本文件 → 复用库中已有组件 → 确无
   可复用才允许新增；新增/修改组件必须在**同一刀**内完成 spec 登记
   （本文件 ③ 追加条目 + 任务书四查写明）。**库中已有组件的重复实现
   = 评审 finding（拒收事由）。**
3. 每次触碰本文件的刀，须在处置/交付记录中列明 spec 变更条目。
4. **v2 授权链**（本重写版的效力来源）：`DEC-OPI-a31b14c9-…3` 开工
   （用户三裁决：成熟内核先行 / 全部屏一次重设计 / 命名换名）→ 简报
   落盘（`bf9c3e5`，v2-1 内核刀唯一设计权威源）→ v2-1 内核刀（章
   `VR-OPI-a31b14c9-…14` PASS）→ 2026-10-02 门三问落定：新内核首验
   判词**通过** / 命名定案**展信佳**（五候选圈选）/ 本文件重写授权
   `DEC-OPI-10bbc3c8-…3`（链件 PLAN-…7 / TASK-…9 / VAL-…5）→ 用户
   第三批定向 8 条（2026-10-02 总控转发）入 8.2 / ③ / ⑨，均由
   v2-2 实施（目标块已回填为现役描述）。
5. **设计义务（用户元指令 2026-10-02 入册）**：「高级动效应自然设计，
   总控/执行者应主动巡检优化点，不等用户提」——巡检所得以登记条目
   落本文件现役节，不等点名。

## ② Token 语义表（唯一出处：`webui/tokens.css`）

v2 内核 = 简报 §2「铁胆墨」14 色 + 水印墨扩展一值。下表逐值与
`tokens.css` 现役实值一致（本重写刀已做三方对照：简报 §2 ↔ 本表 ↔
`tokens.css`，见刀回执）；散文里的旧色名「赭红」随 v2 换档改称
「墨蓝」（`--pencil` 系旧名以别名形态在册，见别名表）。

### ②-1 色彩 14 值（简报 §2 方案 A，对比度已实算）

| token | 值 | 用面 | 禁忌 |
|---|---|---|---|
| `--paper` | `#f6f2e8` | 主纸（html/body/信纸面；L\*95.5——数码白→纸白） | 不作文字色 |
| `--paper-high` | `#fdfbf6` | 顶纸：hover 微起、浮层卡面、dock 垫板（目标态） | 不作大面积正文底 |
| `--paper-2` | `#efe9dc` | 次纸：批注底、垫纸层、短笺/词卡面 | 不作发丝线 |
| `--desk` | `#e3dccb` | 桌布：≥900px 时 body 案头底色 | 窄屏不用 |
| `--ink` | `#191b1e` | 正文墨（冷调 h267°，15.44:1——「冷墨热纸」） | — |
| `--ink-soft` | `#4a4d52` | 次墨（7.59:1）：说明行、meter、busy | 不作大面积正文 |
| `--ink-faint` | `#6b6e72` | 弱墨（4.58:1，元信息下限）：系统行、空态、占位 | 不作正文 |
| `--rule` | `#d9d3c5` | 发丝线（纸的暗面，对比度锁 1.28–1.40） | 不作文字色 |
| `--rule-soft` | `#e7e1d3` | 淡发丝线（稿纸横线/分区线） | — |
| `--accent` | `#2c476a` | 墨蓝（钢笔墨蓝，8.47:1）：链接文字/下划线/次级强调 | 面积 ≤5%/屏 |
| `--accent-deep` | `#1c3049` | 墨蓝深档（11.98:1）：hover/active/落款重档 | 只在 hover·落款·盖印 |
| `--accent-soft` | `#8ba0b8` | 墨蓝淡档（2.40）：8–12% 透明底纹/装饰点 | **永不作文字** |
| `--seal` | `#9a392b` | 朱砂（6.27:1）：**只盖印**——邮戳/红笔圈/批注；每屏 ≤1 处且必须对应真实事件 | 伪事件不盖 |
| `--touch` | `#ece6d9` | 触压底 | 只用于回执撕边衬底 |
| `--ink-ghost` | `#a8a496` | 水印墨：界尺/角饰/水印印记；墨水物理的起笔色 | **永不作文字** |

色彩纪律（简报 §2，可写成 lint）：强调色面积 ≤5%/屏（≈3 处文字链接 +
1 条下划线）；三档纪律（基准 ≥6.5:1 文字用 / 深档只在 hover·落款·盖印 /
淡档永不作文字）；**强调色 ≠ 印章色**——朱砂只盖真实事件，年份/日期/
页码一律墨色族；按钮维持下划线文字形态；唯一大色块 = 印章。

### ②-2 旧名别名（消费面平滑；语义角色不变、值全由 v2 正名承担）

| token | 值 | 说明 | 禁忌 |
|---|---|---|---|
| `--bg` | `var(--paper)` | 旧纸底名 → 主纸 | 不作文字色 |
| `--pencil` | `var(--accent)` | 旧「赭红基准」→ 墨蓝基准（次级链接/焦点圈/错误行） | 只作小面强调 |
| `--pencil-deep` | `var(--accent-deep)` | 旧「赭红加重」→ 墨蓝深档 | 不取代基准位 |
| `--pencil-soft` | `var(--accent-soft)` | 旧「赭红中间档」→ 墨蓝淡档 | 不作链接基准色 |
| `--f-sans` | `var(--f-ui)` | 旧 sans 名 → `--f-ui` | — |

### ②-3 字体栈五条（简报 §3a；离线、仅 Win11 系统字体；CJK 回退次序固定）

| token | 栈 | 用面 | 禁忌 |
|---|---|---|---|
| `--f-serif` | `'Sitka Text', Constantia, Cambria, Georgia, 'Palatino Linotype', 'Times New Roman', 'Songti SC', SimSun, 'Noto Serif CJK SC', serif` | 标题、信笺、primary 动作 | Constantia x-height 0.453 = 宋体 0.453 混排精确对齐 |
| `--f-display` | `'Sitka Display', 'Sitka Banner', Cambria, Georgia, Constantia, 'Times New Roman', 'Songti SC', SimSun, 'Noto Serif CJK SC', serif` | 大字题（opsz 自动切 Display 切面） | — |
| `--f-hand` | `KaiTi, 'Kaiti SC', STKaiti, cursive` | **仅手迹位**（落款、案头日期、边注；17–24px，每屏 ≤2 行 ≤1 处） | 禁作正文、禁 <16px、禁 >28px |
| `--f-ui` | `'Segoe UI Variable Text', 'Segoe UI Variable', 'Segoe UI', DengXian, 'Microsoft YaHei UI', sans-serif` | 界面小字 | 雅黑显大 8%，只作可读性吃紧处降级 |
| `--f-mono` | `Consolas, 'Cascadia Mono', ui-monospace, monospace` | 仪表行读数、数据列 | 数据一律配 `font-variant-numeric: tabular-nums` |

禁（简报 §3a）：宋体/楷体/仿宋 `font-weight:700`（upem=256 单一
weight，700 = 合成粗体发糊——中文标题靠字号跳档 + 字距）；数据列排
雅黑/宋体数字（非等宽无 tnum）。

### ②-4 字号–行高–字距九档（简报 §3b；行高写整 px，4 基数）

| token | 值 | 说明 | 禁忌 |
|---|---|---|---|
| `--fs-display` `--fs-title` `--fs-head` `--fs-body` `--fs-body-latin` `--fs-small` `--fs-hand` `--fs-ui` `--fs-micro` | `34px` `24px` `18px` `17px` `17px` `14.5px` `19px` `12.5px` `11.5px` | 九档标度（display/title/head/body/body-latin/small/hand/ui/micro）；正文 = 信件正文 = 核心阅读面 17px | 新规则不裸写像素 |
| `--lh-display` … `--lh-micro`（同名配对九条） | `42px` `32px` `26px` `32px` `28px` `24px` `30px` `20px` `18px` | 行高整 px（body 1.88 为中文满框留气） | 行高只写整 px |
| `--ls-display` `--ls-title` `--ls-head` `--ls-body` `--ls-small` `--ls-hand` `--ls-ui` `--ls-caps` | `0.01em` `0.02em` `0.03em` `0.01em` `0.01em` `0.04em` `0.02em` `0.14em` | 字距刻度（简报 §3b）；`--ls-caps` 只给大写微标签与 2 字中文标签 | 正文/西文小写字距 >0.02em 即「散」 |
| `--measure` | `34em`（≈578px） | 版心（中西文舒适区交集 380–580px） | — |
| `--baseline` | `32px`（= `--lh-body`） | 基线网格：正文行高、稿纸横线周期、批注卡内文字同锁——**字必须落在线上** | — |

版心与页边距：窄屏 394px ≈ 23 字/行仍舒适；页边距 ≥2 行高（64px 桌面）。

#### ②-4a 排印配方与全局应用规范（fr-A 体系化）

九档标度的**值**不动（简报逐值采用在册）；本刀补的是**应用规范**——
四族读法落成 `font:` 速记配方令牌（`--t-*`，物理出处 tokens.css），
消费面**零拼装**（不再允许「font-family + font-size 各写一半、行高靠
继承」的散写法；fr-A 前残留的相对行高 `1.7`/`1.8` 字面已全数清账）。

| 族 | 配方 | 值 | 用面（哪个层级用哪档） |
|---|---|---|---|
| ① 标题层级（display 族，400——禁合成粗体，中文标题靠字号跳档 + 字距） | `--t-display` | 34/42 | 门厅封面题（唯一） |
| | `--t-title` | 24/32 | 档案真名 / 编辑台题 |
| | `--t-head` | 18/26 | 信头名 / 信封名 / 词卡词头 |
| ② 正文文档档（serif 族） | `--t-body` | 17/32 | 信件正文 / 中文文档行（`.doc-line`——行高锁基线） |
| | `--t-body-latin` | 17/28 | 纯英文散文段（档案人物节） |
| | `--t-small` | 14.5/24 | 次墨说明 / 记忆行 / 短笺 |
| | `--t-hand` | 19/30 | 楷体手迹位（三合法面：落款/案头日期/边注，每屏 ≤2 行 ≤1 处） |
| ③ 界面档（UI sans 族） | `--t-ui` | 12.5/20 | 界面小字 / 链接族 / 说明行（`.sub` `.typing` `.errline` `.flow-calibre` 等） |
| | `--t-note` | 14.5/24 sans | 界面弱化小字（`.note` 空态行 / `.state-banner` 状态横幅） |
| ④ 微标签与 mono 数字档 | `--meta-font`（sans 500） | 11.5/20 | 微标签 sans 角色（状态词/节名/词性等元信息位——唯一去处） |
| | `--meta-mono`（等宽 400） | 11.5/20 | 时间/编号/计数/日期/版本行/数据列（恒配 `font-variant-numeric: tabular-nums`） |

规范：新规则一律 `font: var(--t-*)`（或 `var(--meta-*)`）整体取用；
族内再分层靠**墨色三级**（`--ink`/`--ink-soft`/`--ink-faint`）与
`letter-spacing` 刻度，不靠另立字号。

### ②-5 间距·动效·微标签·触感·阴影·图标·布局

| token | 值 | 用途 | 禁忌 |
|---|---|---|---|
| `--sp-1` … `--sp-8` | `4px`–`64px`（4 基数） | 间距阶八阶 | 新规则不裸写像素 |
| `--dur-micro` | `100ms` | 触感反馈档：state layer / hover / press | 一切反馈 ≤ 此档；纸事件不走它 |
| `--dur-stamp` `--dur-note` | `120ms` `260ms` | 纸事件：邮戳盖下 / 批注递出（教学卡展开档——v2 按简报 §5 重定 260ms，rd-1 旧档 240ms 已废） | 不裸写时长 |
| `--dur-1` | `140ms` | 逐行落墨步长 / hover 色变 | 同上 |
| `--dur-panel-in` `--dur-panel-out` | `280ms` `200ms` | 抽屉进·出——进入比退出略长（fr-B：容器级退出已由 .panel--leave 编排接上，⑨-5 抽屉开合行） | 同上 |
| `--dur-ink` `--dur-wet` | `360ms` `600ms` | 渗墨（opacity 恒慢于 transform ≈1.3×）/ 墨水物理（ink-ghost→ink 一次性） | opacity 先至 = 数字语汇 |
| `--dur-settle` | `320ms` | 大件封顶：信纸落桌、编辑台过渡、逐行总封顶 | 大件 >320ms 恐过慢 |
| `--dur-space-in` `--dur-space-out` | `340ms` `220ms` | 整屏转场档（fr-B 新立）：空间/全页进入·退出——进入比面板档长半档（分层错峰留时），退出与进入同帧起播成交叉淡化 | 整屏位移仍 8px 封顶 |
| `--dur-dialog-in` | `300ms` | 弹窗档（fr-B 新立）：确认窗/弹层升起——介于面板与整屏之间 | 同上 |
| `--dur-stagger` | `28ms` | 列表逐项错峰步长（fr-B 新立——20–40ms 区间取中，前 8 项封顶） | 不裸写步长 |
| `--ease-spring` | `cubic-bezier(0.34, 1.25, 0.4, 1)` | 弹簧族（fr-B 新立——spring 近似；**对 rd-1「唯一 overshoot = 盖印收束」的显式收窄修订，用户任务书授权**：只许配盖印形 keyframes（scale ≤0.96→1 幅度族），禁配位移/大尺度，幅度 ≤4%） | 绝不弹跳轻浮 |
| `--ease-paper` | `cubic-bezier(0.16, 1, 0.3, 1)` | 进入减速长尾（纸先落） | 禁 linear |
| `--ease-enter` `--ease-exit` | `cubic-bezier(0.05, 0.7, 0.1, 1)` / `cubic-bezier(0.3, 0, 1, 1)` | 教学/面板进·退缓动分离（进入长尾/退出收势） | — |
| `--ease-press` | `cubic-bezier(0.4, 0, 0.2, 1)` | 触压对称/盖印收束（唯一 overshoot 许可） | 无弹性回弹 |
| `--meta-font` | `500 var(--fs-micro)/var(--lh-ui) var(--f-sans)` | 微标签配方 sans 角色（rd-1）：状态词/节名/词性等元信息——`font: var(--meta-font)` 整体取用 | 元信息位只许引用配方，不重写字面 |
| `--meta-mono` | `var(--fs-micro)/var(--lh-ui) var(--f-mono)` | 微标签配方等宽角色（rd-1）：时间/编号/计数/日期/版本行 | 同上 |
| `--meta-track` | `var(--ls-caps)` | 微标签字距（rd-1） | — |
| `--meta-ink` | `var(--ink-faint)` | 微标签暖灰（rd-1） | — |
| `--state-hover` `--state-focus` `--state-press` | `0.08` `0.12` `0.12` | 触感层三值（rd-1；Material state layer 实测值） | 只作 `::after` 的 opacity，不碰布局 |
| `--stack-shadow-soft` `--stack-shadow-deep` | `3px -3px 6px rgba(25,27,30,.12)` / `-5px 6px 10px rgba(25,27,30,.16)` | 纸叠偏移阴影两级（rd-1 面6）：轻=右上（批注/浮层在人手近侧）、重=左下（信纸摊在案头）——方向不统一 | **阴影色 = 墨色同源**（`rgba(25,27,30,…)`，`--ink` 降透明度），禁 `rgba(0,0,0,…)`；全局恰两级；与发丝描边配对；禁大面积模糊投影型 |
| `--icon-size` `--icon-stroke` | `18px` `1.5` | #22 图标参数：默认见方与统一笔重 | — |
| `--read-pad` | `18px` | 阅读左右留白 | — |
| `--safe-bottom` | `env(safe-area-inset-bottom, 0px)` | dock 底安全区 | — |
| `--navdock-h` | `60px` | 常驻 dock（#18）**实高**：body 底 padding 与写信区让位的同一来源。v3-a 定谳：语义 = navdock 实高，`.navdock` 的上下 padding 用 `calc()` 从本令牌反推（签行 44 + 上下距 + 边框 1 = 60）——实高恒等于令牌，历史 54（记）/57（实）的 3px 账实差与 dock 盖线缺陷消亡 | 不作行高 |
| `--dock-trigger-h` | `44px` | 笔搁触发条内容高（8.2.2⑤；触靶常量） | 不作行高 |
| `--dock-compose-inset` | `16px` | 写作态面板与屏幕缘的距离（桌面档——一张新信纸摊在案头中央） | 不作行高 |
| `--navdock-clearance` | `calc(var(--navdock-h) + var(--safe-bottom))` | 固定底具补偿带（v3-2，P1-1）：一切滚动容器 bottom padding 的算术底数（.flow / .spacebody 消费），零第三处手写 | 不作行高 |
| `--shell-w` | `430px`（≥900px 媒体查询改写 `1080px`，≥1280 改 `1240px`） | 信纸栏宽：#18 navdock 与写信区 .dock 的同一宽度出处 | 不作颜色 |

（fr-A 新增：排印配方 `--t-*` 九枚与四族应用规范见 **②-4a**——本表不重列；
会话窗三件的屏级尺寸走既有 `--navdock-h` / `--dock-trigger-h` 与
`--sp-*` 阶，零新尺寸令牌。）

### ②-6 圆角法则（2026-10-02 回退记录）

圆角五档尝试（v2-2R 的 `--r-*`，commit 52aa84a）被用户否决回退（原话
2026-10-02：「改回去吧，不要用圆角了，因为你根本把握不住」）——
**简报 §6 原法则恢复并重新现役**：零大圆角面板（圆角收窄一档：信纸
物件 ≤2px，仅邮票/邮戳圆形豁免）。`--r-*` 令牌已从 tokens.css 删除，
webui 不再有任何消费点；本轮留痕见 tests/host/test_v22r_soft_radius.py
（回退钉）。

**fr-A 豁免新增一席（2026-10-05，本文件 ⑨-14 同刀登记；veto-R 退役
2026-10-04）**：豁免集合曾由「仅邮票/邮戳圆形」扩为**邮票/邮戳/回底
墨点**（fr-A 的 #24 悬浮墨点）——**该豁免已随 veto-R 退役**（用户
否决墨点形态：与应用整体纸墨文具风格不符，#24 重铸为纸底 + 发丝线
+ 图标 + 字标的现役按钮族矩形）；豁免集合**回到「仅邮票/邮戳
圆形」**。圆角普查随之由 components 9 / screens 4 记回
components 7 / screens 4（test_v22r_soft_radius 的计数钉同刀随迁）。
上文原始法则句一字保留（历史与法则原文不改写）。

规则：组件样式只许 `var()` 引用，**禁止在任何其他文件重写令牌字面值**；
禁止新增 token 之外的十六进制颜色（零青绿——旧双色主题不得回流）。
v2 起 `tokens.css` 是全套令牌的唯一物理出处，其头注即简报 §2/§3 的
逐值采用记录；旧名别名只供消费面平滑，**新写规则一律用 v2 正名**。

**元信息纪律（rd-1）**：全站元信息位（时间戳/状态词/计数/编号/版本行/
日期）一律走微标签配方（`--meta-*`）——第一次用文字表达状态差异，
第二次才用颜色；彩色徽章/胶囊保持退役（墨蓝只作文字与小面强调，
不作胶囊底）。

**「零阴影」解除登记（rd-1 面6；用户 2026-09-30 明示从未否决过阴影，
纸叠偏移阴影授权入刀，`DEC-OPI-dc0ba4b6-…13`）**：F-1R 历史提交原文
保留不改写；现役阴影法 = **纸叠偏移阴影两级**（`--stack-shadow-*`）——
阴影色与墨同源（v2 起 `rgba(25,27,30,…)`）、位移小（±3–6px 量级）、
方向不统一（信纸左下/批注右上，人手叠放感）、与发丝描边配对、
**禁大面积模糊投影型 shadow**（那是 UI 卡片语汇）。应用面三类：信纸
在桌布上（`#stage` ≥900 桌面档，重档）/ 批注在信纸上
（`--stack-shadow-soft`）/ 浮层卡面的垫纸层承影。

## ③ 组件契约（唯一出处：`webui/components.css` + `webui/components.js`）

每组件在 components.css 有契约注释块（结构/状态矩阵/使用规则/禁止变体）。
页面引用一律走新变体类；旧类名仅作为别名保留在同一规则的选择器表尾。
现役注册表 = 26 组件（#1–#22 连号 + fr-A 新增 #24–#27；rd-4 曾增 #23
partner-card，cs-2 随档案全页视图退役——浮层与名册桩拆除、same-cut
retirement，注册表不做阁楼，**编号空出不复用**，见本节表后注）。

| # | 组件 | 类名（新） | 别名（现役旧名） | 状态矩阵 | 出处 |
|---|---|---|---|---|---|
| 1 | link-btn | `.btn` + `.btn--ink` `--send` `--pencil` `--set` `--faint` `--dot` `--back` `--meter` | `.ob .go` `.send` `.linklike` `.setlink` `.skiplink` `.refresh` `.back` `.meter` | default / hover（v2：`--accent-deep` 加深）/ `:active`（opacity .55 + 触压 1px）/ `[disabled]`（opacity .4 + 无 pointer）/ busy（文案切换由 JS 承担）；`--pencil` 变体现役值 = 墨蓝（旧赭红名） | components.css + components.js（helpButton/skip/寄出作答） |
| 2 | pen | `.pen`（+ `--open`） | — | default / placeholder / focus（纸面微起 --paper-high）/ Enter 绑定（app.js）；`--open` = 写作态尺寸修饰（v3-a 8.2.2⑤：`flex: 1` 吃满面板余高、`max-height: none`——字面/线语汇仍唯一出处，矮视口降级档由 screens.css 媒体查询收回） | components.css + screens.css（尺寸修饰）+ components.js（autosizeTo/clearAutosize——降级档动态几何） |
| 3 | note-paper | `.note-paper`（+ `.skipped` `.note-paper--enter` `.note-head`） | — | default（--paper-2 次纸 + 左缘界尺 + 卡头 #22 note 小图）/ skipped / busy（JS 置 disabled+busystrip）/ enter（新批注组递入一次：`.note-paper--enter` = paper-drop + ink-wash 双动画，v2 改形——见 ⑨-5 note-arrive 行） | components.css + components.js（showMoments/addReplyControls） |
| 4 | letter | `.letter` `.may` `.me` `.paper` `.say` | — | plain（may）/ torn（me）；v2 增在途形态 `.letter--en-route`（rd-4 登记的虚发丝角标，回信落地/失败即摘）与 `.ink-wet` 墨水物理宿主（新到信 `--ink-ghost→--ink` 一次性，简报 T1-3） | components.css + components.js（addLine） |
| 5 | hairline-section | `.sec` | — | default（无交互态） | components.css |
| 6 | setlink-block | `.setlinks` `.setblock` | — | default / [hidden] 切换；**现役页面用户清零**（留库，再启用走 ⑤ 四步） | components.css |
| 7 | resultstrip | `.resultstrip.ok` `.part` `.miss` | — | ok / part / miss | components.css + components.js（showResultStrip） |
| 8 | busystrip | `.busystrip` | — | 出现即 busy、消失即复位 | components.css + components.js（setReplyBusy） |
| 9 | meter-row | `.kv` `.kvgroup` `.kvtitle` | — | default（无交互态） | components.css + components.js（diagLine/diagGroup） |
| 10 | empty-state | `.note` | — | default（无交互态）；现役面收窄为壳上静态占位行（「暂无数据」族首绘），运行时空态走 #14 | components.css + components.js（diagEmpty） |
| 11 | confirm-dialog | `.cfrm`（+ `.cfrm-msg` `.cfrm-actions`）+ 纸雾件 `.cfrm-scrim`（fr-B 重铸——原生 confirm 退役） | — | open（纸雾 scrim-in 淡入 + 面板 paper-drop + ink-wash 升起，`--dur-dialog-in` 弹窗档）/ close（两臂·点雾·Esc 同一路——paper-fold + ink-wash reverse 褪下 + scrim-out 同步淡出，Esc 收起与确认收起对称）/ 语义 = 原生 confirm 平移（确定 true、其余 false）；z 11/12 全站最上（⑩ 10.2） | components.css + components.js（`confirmDialog()`——全页唯一确认调用点，异步 Promise<boolean>，消息一律 textContent） |
| 12 | system-line | `.sysline` | — | default（无交互态） | components.css + components.js（addLine system 臂） |
| 13 | brand-mark | `.brandmark`（+ `--sm` `--lg`） | — | default 30px / 尺寸修饰 --sm 20px、--lg 64px / 静态标记无动效；**几何 = 信封 + 封缄墨线，封缄点 v2 裁用墨蓝**（`--accent`——朱砂只盖真实事件，品牌印记不是事件，简报 T2；aria-label「展信佳印记」随模板，改名只动模板与 BRAND 常量） | index.html（`<template id="brand-mark-source">` 内联 SVG，几何唯一出处）+ components.css + components.js（`brandMark()`/`installBrandMarks()`） |
| 14 | state-banner | `.state-banner`（+ `--loading` `--empty` `--error`） | — | loading（取信中…——v2 起尾点**静态化**：零常驻循环铁律，呼吸循环件已退役）/ empty（弱化诚实句 + #22 lamp 墨线小图）/ error（人话句 + `--pencil`（墨蓝）重试链接，回调由调用方注入）/ reduced-motion 随库尾总降级块 | components.css + components.js（`stateBanner()`；`diagEmpty`/`diagError` 一律委托它） |
| 15 | word-card | `.word-card`（+ `.wc-lemma` `.wc-pos` `.wc-forms` `.wc-zh` `.wc-en` `.wc-example` `.word` `.word--off`）+ sheet 档遮罩件 `.word-scrim` + 词典第二档件 `.wc-src`/`.wc-lemma--sm`（`.word-card--lexicon`） | — | default（--paper-high 泛起纸面 + 发丝边 + 垫纸错位层承 `--stack-shadow-soft`；开启入场 = paper-drop + ink-wash 双动画；`.word:hover` 触点泛淡墨蓝 `--pencil-soft`——hover 半区）\| sheet 档（`@media (hover: none)`——触屏 = 底部覆盖面板 bottom sheet：fixed 底部 + 墨色遮罩 + `@starting-style` 纸面曲线入场，8.2.2③）\| closed（点卡外/遮罩、「收起」或 Esc，DOM 移除语义）\| 无 busy——命中即显；**v3-d 契约：miss 无样式而非静默**（8.2.2③-a——命中位图随信下发，位图判 0 的词 `.word--off` 无供性、点击短路，可点的词必有卡）\| **词典第二档**（`source: "lexicon"`——「词典」标注小卡，与语料卡 visibly 两档，8.2.2③-a）。触屏词提示 = 两件（8.2.2④）：`.letter--latest .say .word` 弱底纹（仅最新一封）+ `.word:active` 按压即亮——「全文常显点线」永禁（负钉在库）；`.word--off` 四态全摘（cursor/hover/active/底纹） | components.css + components.js（`wordCard()`/`showWordCard()`/`closeWordCard()`；触发面 = `letterWords()` 的 `.word` 分片（带命中位图行）+ `wordWindows()` 窗口查询，app.js 委派） |
| 16 | field | `.field`（+ `.fieldname`） | — | default（下发丝线）/ `:focus-within`（发丝线与名转墨蓝，--dur-1 淡入）/ 控件 `[disabled]`（opacity .4 + 无 pointer）；名牌可配 #22 search 小图 | components.css + components.js（`fieldRow()`，p-3；label 包裹控件，点名牌即聚焦） |
| 17 | chip | `.chip`（+ `--on` `--badge`） | — | off（default，发丝线描边）/ hover（边转次级墨）/ on（`--on`，主墨反白）/ `:active`（触压 1px）/ `[disabled]`（opacity .4）/ `--badge`（只读徽标，非交互） | components.css + components.js（`chip()`，p-3；考试/语域/教学频率词表 picker + modality 徽标） |
| 18 | dock | `.navdock`（+ `.navdock-item` `--on` `.navdock-glyph` `.navdock-word` `--fold`；类名与写信区屏级类 `.dock` 异名共存） | — | **v3-a 落墨页签**：default（20×20 墨线图标描形 fill-opacity 0 + 标签次墨 400——图标与文字标签同钮上下两行）/ hover（图标与标签同落主墨，100ms——hover 半区）/ `--on`（**落墨当前态**：图标淡墨渍底 fill-opacity .15 + 标签 --ink 600，ink-wash 静态版——v3-aR 用户首验否决实墨填充后修订，裁决 DEC-OPI-76a0a10a-…9；填充切换 = 一次落墨事件——进入 260ms × --ease-paper、退出 200ms × --ease-exit 一褪一落同帧；`aria-current`；下划线语汇从导航当前态岗位退役，动作链接岗位不动）/ `:active`（触压 1px）/ `[disabled]`（opacity .4）/ `--fold`（让位收半：paper-fold 200 × --ease-exit，animationend 后 [hidden]）；垫条材质 = --paper-high 顶纸（与写信区垫板同族）；宽度随 `--shell-w`（≥900px 三项收拢居中）；常驻底部三项 **案头 / 温故 / 抽屉**（门厅/全页/写作态整条让位；z 6 低于点词卡 z 9） | components.css + components.js（`wireNavdock()`/`markNavdock()`，R-1；app.js 的 `yieldNavdock()`/`restoreNavdock()` 落 --fold） |
| 19 | space-header | `.space-header`（+ 节名槽 `.spacehead-sec`；与屏级基形 `.top` 合用） | — | default（发丝线夹持 sticky 顶栏，随 `.top`）；无交互态——静态头部；案头头部用 `.top` 原形（who 块端点驱动空槽，mc-1 起点开信封沓）；温故/抽屉头部 = `.top` 基形 + 本类；品牌名与副题退居门厅封面，空间头不再增长链接 | components.css + components.js（`sectionLabel()`，R-1） |
| 20 | section-tabs | `.section-tabs` / `.section-tab`（+ `--on`） | — | unselected（default，透明点线占位）/ hover（墨色微沉）/ selected（`--on`，主墨加重 + 墨蓝实线短下划 + `aria-selected`）/ focus（地基 `:focus-visible` 焦点环，不另设）/ `[disabled]`（opacity .4）；roving tabindex + 左右箭头循环移选；温故/抽屉各一排三项，切节即拉 | components.css + components.js（`wireSectionTabs()`/`markSectionTabs()`，R-1） |
| 21 | disclosure | `.disclosure`（+ `.disclosure-head` `.disclosure-marker` `.disclosure-title` `.disclosure-examples` `.disclosure-body` `--open`） | — | collapsed（default，内容区 hidden，chevron 向右）/ expanded（`--open`，内容区展开、chevron 旋转 90°、`aria-expanded="true"`，计数保留；入场 = ⑨-5 paper-unfold）/ focus（地基环，不另设）；标记 = #22 自绘墨线 chevron；一切「超过 8 行的同质列表」与「参考 / 原始读数」走它；不得手风琴互斥、不得嵌套、不得图标外链 | components.css + components.js（`disclosure()`，R-1R） |
| 22 | icon-set | `.inkicon`（几何模板 `id="icon-search\|chevron\|note\|write\|inbox\|lamp\|stamp\|desk\|revisit\|drawer"`） | — | default（`--icon-size` 见方、currentColor 墨色、`--icon-stroke` 1.5、圆角端点；无独立交互态——chevron 旋转是宿主 #21 的 `--open` 态面；#18 三枚的落墨填充是宿主 `.navdock-item--on` 的态面——fill-opacity 过渡，图标本体仍无独立交互态）/ reduced-motion（宿主动效随库尾总降级归零后静帧） | index.html（`<template id="icon-set-source">` 十枚内联 SVG，几何唯一出处）+ components.css + components.js（`inkIcon()`/`installIcons()`，R-1V） |
| 24 | flow-bottom | `.flow-bottom`（+ `.flow-bottom-glyph` `.flow-bottom-word`） | — | default（纸底 `--paper-high` + 发丝线边 1px `--rule` + 墨线图标 +「回到底」短字标 + `--stack-shadow-soft` 承影——veto-R 重铸，融入现役按钮族语汇）/ hover·focus·press（墨雾三值正向叠，rd-1 三档）/ `:active`（触压 1px）/ `[hidden]`（在底 / 写作态 / 离案头——JS 账）；**圆形退役**（用户否决墨点形态，②-6 的 fr-A 豁免随之退役——豁免集合回到「仅邮票/邮戳圆形」） | index.html + components.css（视觉）+ screens.css（位置账）+ app.js（`syncFlowBottom`） |
| 25 | flow-ruler | `.flow-ruler`（+ `.flow-tick` `--on`） | — | default（8×2 水印墨短线，flex 纵向均分条高——点距即窗口密度）/ 当前轮 `--on`（14×2 主墨 + `aria-current`，形态差异非颜色）/ hover（次墨半档）/ focus-visible（墨蓝细环）/ `[hidden]`（<2 轮 / 写作态 / 离案头）；**刻度点 ↔ flowTurns 轮锚一一绑定**（veto-R：高亮按真实锚点位置计算——视位线 = 顶栏之下一档呼吸，rAF 节流的被动 listener 对账；点击 = 精确滚到该轮锚点）；口径行 `.flow-calibre`（屏级，「加载更早」衔接主线-2 分页） | index.html + components.css + screens.css + app.js（`flowTurns` 锚 / `buildFlowRuler`/`scheduleFlowRulerSync`/`loadEarlierLetters`） |
| 26 | tokenmeter | `.tokenmeter`（+ `.tm-pop` `.tm-pop-head` `.tm-pop-turn` `.tm-num`） | — | **紧凑计量粒**（veto-R 重铸——用户否决 sticky 常驻遮挡与整句读法）：dock 上沿内嵌读数钮，主数据直出（会话累计总 token，tabular-nums，无说明句）；点按展开 `.tm-pop` 逐轮明细浮层（浮层家族：Esc 关、点外关、⑩ 互斥收，z 10）；未计量字段在浮层里如实「—」，不伪造 0；累计 = 服务端会话全量（窗口无关），客户端不做本地加减；`[hidden]`（开关关 / 无读数 / 写作态 / 离案头） | index.html（dock 内）+ components.css（粒 + 浮层）+ app.js（`setTokenMeter`/`toggleTokenMeterPop`/`closeTokenMeterPop`/`syncFlowMeter`/`refreshFlowMeter`；开关存 sessionStorage——如实标注） |
| 27 | select | `.select`（+ `.select-btn` `.select-value` `.select-chevron` `.select-list` `.select-option` `--on` `--active` `--open`） | — | default（按钮 = 稿纸行读法 + chevron 弱墨）/ `--open`（chevron 旋 90°，纸面浮层落 `--paper-high` + 发丝缘 + 软纸影）/ option：default（墨字）/ hover·键盘活动项（淡墨雾——color-mix 墨色同源 8%/12%，rd-1 三值读法）/ 选中 `--on`（主墨 + 勾记 ✓）/ placeholder（弱墨 ui 档）；键盘 ↑↓/Home/End/Enter/Esc/Tab 全链 + `role=listbox/option` + `aria-activedescendant` + 点外关闭 | components.css + components.js（`selectField()`，fr-A——原生 `<select>` 全应用退役，三现役消费面：方向页技能 / 设置批注频率 / 披露层级） |

**#23 退役注记（cs-2，替代 rd-4 假句的现役真值）**：rd-4 的
`.partner-card` 浮层纸卡与名册桩（名册 = 前端静态副本、选中只落
localStorage、零生效声称）已随 cs-2 档案全页视图**整体退役**——现役
伙伴面 = 全页笔友档案（`#space-partner`，数据只读 `GET /api/partner`
一个端点，角色文本真源在 `src/elc/persona/penpal.py` 单一出处，webui
零角色名字面）+ mc-1 信封沓选择器 + mc-2 角色编辑台（全页 DIY，九面
表单、真 CRUD、veiled 四面「留空保留/写下盖上」）；详见 8.2.2a。
9.12 历史登记保留 rd-4 时代的登记原文，不作现役断言。

库外现役类（登记，不扩库）：`.teach-me`（弱化行链接——sans 12px
墨蓝下划线，hover 转 `--pencil-deep`，:active 触压 1px；样式唯一出处
components.css 的库外登记规则（#1 块尾），JS 类名 `teach-me` 有钉
不动）；`.replyrow` / `.replytext`（note-paper 的内置回复面，随 #3
契约）；`.formhead` `.sub` `.hint` `.who` `.who-sub` `.typing` `.errline`
`.grouphead`（屏级文字形态，screens.css）；`.today` `.todaybody`
`.topactions` `.goalbody` `.setbody`（**R-1 退役**：五屏屏级布局类，
随空间模型让位 `.spacebody`）。
（F-G2 移出：`.diagerror`——面板失败态改走 #14，该类无现役用户，规则
已删。W-8 移出的 blocked 行族（类与规则双除名）不再登记——防回潮
负钉在测试侧。）
**R-1 现役面收窄**：#6 setlink-block（`.setlinks`/`.setblock`）与 #1 的
`--set`/`--meter` 变体的**页面现役用户清零**——组件与变体**留库**
（活注册表不是死档），再启用须走 ⑤ 四步。

**状态完备性硬门**：交互组件（本表现役 = link-btn、pen、note-paper、
resultstrip）必须定义至少 default + 一态（active/disabled/busy/skipped）；
新增交互组件同门。

## ④ 命名法

1. **语义类名**：类名说「这是什么」（`note-paper`、`resultstrip`），
   禁止定位类名（`.left-20`、`.mt-8` 族永久禁入）。
2. **变体修饰符**：`--` 后缀（`.btn--ink`）；组件基类 = 单词（`.btn`、
   `.pen`）。
3. 文件级前缀不引入；屏级布局类（`.ob` `.set` `.top` `.flow` `.dock`）
   留在 screens.css，不得进 components.css。

## ⑤ 库唯一出处条款（活注册表）

**库是活注册表**（用户裁决 2026-09-28：组件库非定死——产品长则库长）。
每个新前端需求都走同一遍入库流程：

1. **先查库**：本文件 ③ 表 + `components.css` 的契约注释块；
2. **已有则复用**（禁重写——同一需求第二个实现仍是
   重复实现 = 评审 finding（拒收事由））；
3. **无则新建**：遵循既有契约形——契约注释块（结构/状态矩阵/使用规则/
   禁止变体）进 components.css、工厂函数进 components.js（文字一律
   textContent）、交互组件过 ⑥ 的状态完备硬门；
4. **同刀登记**：本文件 ③ 表加行 **且**
   `tests/host/test_fg1_architecture.py` 的 `COMPONENTS` 元组加名——
   两处必须同刀，缺一处 = 评审 finding。

登记不是归档：③ 表的每一行都是后续需求的查库入口；组件的现役面变化
（收窄、别名退场、变体易主、**退役除名**）也随触碰它的那刀改行，
不让表说谎（cs-2 的 #23 除名即此条的首个退役先例）。

1. 组件样式的**唯一物理出处**是 `components.css`：同一组件类名（含别名）
   的样式规则在全 webui 目录**恰出现一次**；`screens.css`、`index.html`、
   JS 内联样式不得重复定义（钉：`test_fg1_architecture.py` 单出处组；
   brand-mark 与 icon-set 的 SVG **几何**是唯一例外——出处是 index.html
   的模板，其样式仍只在 components.css）。
2. 新前端需求**先查本 spec**：已有组件直接复用；确需变体时扩展现组件的
   修饰符，不另起炉灶。
3. 新增/修改组件：任务书四查写明 + 本文件 ③ 表同刀登记。
4. 重复实现 = 评审 finding（拒收事由）。

## ⑥ 状态完备性硬门

见 ③ 末条。评审按表逐组件核对；「只有 default 态的交互组件」是 finding。

## ⑦ 架构说明

```
src/elc/webui/
  index.html        页面骨架（v2 内核 + cs/mc 现役）：#screen-onboard
                    门厅封面（展信佳 · Dear You）+ #space-parlor 案头
                    （品牌条端点驱动空槽 + 信流 + 写信区）+ #space-partner
                    笔友档案全页（cs-2）+ #space-study 温故（今日/方向/
                    档案三节）+ #space-drawer 抽屉（记忆/隐私/设置三节；
                    记忆 = cs-2 三摞）+ #navdock 常驻三项 + .marginalia
                    桌面边注栏（案头日期 + 界尺；装饰邮戳水印已随 v2
                    撤除——邮戳只落真实事件）；brand-mark 与 #22
                    icon-set 的 <template> 几何出处（icon-set 现役七枚，
                    圆戳已出集）
  tokens.css        v2 内核令牌唯一物理出处（简报 §2 十四色 + 水印墨
                    + 旧名别名 + §3a 五字体栈 + §3b 九档标度/行高/字距
                    + 版心与基线 + 间距阶 + 动效档 + 微标签配方 + 触感
                    三值 + 纸叠阴影两级 + 图标参数 + 布局四件）
  components.css    组件库唯一样式源（22 组件 + 元素复位地基；v2 动效
                    注册表：paper-drop / ink-wash / ink-set / paper-unfold
                    / stamp-press 五 keyframes + reduced-motion 总降级块
                    在库尾）
  screens.css       屏级布局 + 壳层（html/body/#stage/dock=写信区/flow/
                    spacebody/屏级文字；四档断点系统 481/900/1280 +
                    桌面舞台构图；信封沓 .envsel 与角色编辑台的屏级
                    形态；容器延展过渡（extendContainer）与
                    贴底 sheet（hover:none 档）——v3-2）
  api.js            端点 fetch 封装（页面唯一 fetch 调用点；含
                    /api/partner、/api/characters 等现役读面）
  components.js     组件工厂 + 教学卡当场行为 + 点词卡 + 壳导航接线 +
                    信封卡与沓排布（envelopeCard/layoutEnvelopeStack，
                    mc-1 消费）+ 图标工厂（inkIcon/installIcons）
                    （textContent-only；唯一 confirm 封装点）
  app.js            装配：BRAND 品牌单点常量（换名只动这里 +
                    index.html <title> 静态兜底）/ 空间与节切换 / 角色
                    面（案头主从条、信封沓、编辑台、笔友档案）/ 事件 /
                    轮询 / 学习与诊断渲染（面板三态走 #14；进空间落
                    默认节，切节即拉）
```

- **ES modules、零构建**：浏览器直 import 相对路径（`./api.js`），无打包
  器、无 importmap、`type="module"` 天然延迟绑定。`dependencies = []`
  不变。
- **零外链**：无 CDN、无站外字体、无任何 http(s) 资源与 `@import`。
- **静态服务**：`elc/web.py` 按 `_STATIC_TYPES` 允许表**逐请求**读盘；
  允许表即路径校验（表外名字不触盘，404 人话）；文件缺失/不可读 →
  404 + 人话 JSON（fail-closed，永不 500 裸栈）。
- **单一出处纪律（cs-1）**：角色的一切字面（名、身份行、卡文）真源在
  `src/elc/persona/penpal.py` / `character_card` 表；webui 零角色名字面
  （无 JS 兜底 = 留空，不发明人名）；`/api/partner`（及
  `/api/partner?character_id=`）是从真源派生的只读面，不是第二份抄本。

---

## ⑧ 设计蓝图 v2（v2-s 重写版 · 2026-10-02）

> 版本史：R-0 结构蓝图（`c8649d3` 起）→ R-1A 蓝图 v2（逐页剖析与方案
> 重设计，原文见 git 历史）→ rd-2/rd-3/rd-4 三轮修订（语气/IA/全面面，
> 登记在 9.10–9.12）→ **v2**：用户否决旧范式整体（「自建了不成熟且
> 简陋的内核就开始深化，再怎么改都无济于事」），v2-1 内核刀按简报把
> 铁胆墨×真纸内核落进外壳与对话主面，cs/mc/ux 三程序跟进；本节由
> v2-s 授权（`DEC-OPI-10bbc3c8-…3`）按简报 + v2-1 实现真值整体重写。
>
> 地位：本节是 v2 前端的结构权威；② ③ 的 token 与组件契约不变，新增
> 组件一律按 ⑤ 四步入库。结构与文案属 R7 域：**用户对本蓝图有首验
> 否决权**。v2-2 起原「目标设计——实施在 v2-2」的块已回填为现役
> 描述（回填逐处标注原目标来源）；未标注的块描述现役真值。

### 8.0 旧壳诊断史（存目）

R-1 时代的逐页剖析（信息组织 / 表达方式 / 特色延续三个否决词的逐页
证据，编号 01–10 走查）已完成使命：其 P0/P1 主张由 R-1R/rd-2/rd-3/rd-4
四刀兑现，其「现状」描述已被 v2-1 内核 + cs/mc 取代。原文见 git 历史
（R-1A 蓝图 v2 全文）；本节只存目，不再作任何现役断言。方法论存续：
逐页走查 + 探针库 + 截图存档的做法沿用于 v2-2 的验收（VAL 人验门）。

### 8.1 信息架构总纲

#### 8.1.1 层级定谳

门厅（首访一次）→ 三空间（常驻）→ 空间内节（页）→ 页内块 → 块内行。
**空间模型保留**（门厅 + 案头 / 温故 / 抽屉 + dock 三项）；v2 增两处
附属面：**笔友档案全页**（`#space-partner`，从信封沓的「档案」动作进，
返回钮回案头）与**角色编辑台**（mc-2 全页 DIY，从信封沓进）——两者
是案头的纵深，不是新空间（dock ≤5 红线不动）。壳层 v2-1 已按内核
换装（品牌名退居门厅封面、边注栏水印撤除）；屏内信息架构与文案的
结构重铸属 v2-2。

#### 8.1.2 命名系统定稿

- dock（空间词）：**案头 / 温故 / 抽屉**（v2 换名：rd-2 定稿的首词
  随品牌换名改「案头」——写信的案头，信摊在上面；rd-2 前为「学案 /
  柜抽」两代旧词，均退役）。
- 温故节名：**今日 / 方向 / 档案**（「目标」改「方向」（一词三义事故）；
  「进步」改「档案」（诚实纪律：证据增益永不声称掌握））。
- 抽屉节名（不动）：**记忆 / 隐私 / 设置**。
- 品牌名：**展信佳**（副题「见字如晤，今日如何」；英文并写 `Dear You`）
  ——`app.js` 的 `BRAND` 常量是唯一可变点 + index.html `<title>` 同值
  静态兜底；门上候选四名（笔谈 / 尺素 / 提笔 / 亲启）在简报 §1 备案，
  换名 = 改一处常量。
- 领域词定稿（全应用一致，8.3 是翻译表）：teaching target → **表达**；
  teaching moment → **批注**；conversation → **这段通信**；delete →
  **忘掉**；tombstone → **存根**；gate → **门规**；character/penpal →
  **笔友**（v2 定稿：角色即笔友——Nell Alder 是内置首角色，名字由
  端点驱动，界面不写死）。
- 对话语言跟随用户（默认中文）——『学习内容本身』指教学表达/例句/词卡，
  非对话语言的限定。界面语言为中文；英文只在三种合法位置出现——
  ① 学习内容本身（表达、例句、词卡）；② 存储词表值的原文（跟在中文
  后，等宽小字）；③ 折叠的「原始读数」区。此外一律不出现。

#### 8.1.3 导航模型

- dock 三项常驻不变；门厅 dock 让位不变；节签横排不变（#20 契约）。
- **页题只念一遍**：spacehead 节名槽承担「我在哪」，节签承担「还能去哪」；
  页内 h2 取消，页首以引导句开场（8.2.9）。
- 「为什么」的归处：读数与原委归 温故 · 档案 的 why_not 面与原始读数；
  信流里没递批注的一轮静默（W-8 定案延续）。
- 满 / 加载 / 空 / 错误四态：读数块一律 #14 state-banner 族（现役）；
  信流不用横幅。
- **Esc 逐层退栈（v3-2，⑩ 层级宪法的统一关闭语义）**：Esc 永远只退
  一层——浮层关浮层、下拉容器退一层（编辑面/全览窗口 → 扇叠 → 收沓）、
  全页回其入口（笔友档案/信档 → 案头；原始读数 → 温故 · 档案，与各自
  返回钮同效）。体验矩阵确认 Esc 是全站唯一做对过的关闭控件——推广
  到全部层；「点外关闭」只属浮层与下拉容器的遮罩面。

#### 8.1.4 v2 沿用不变项（防静默丢失）

视觉内核（简报 §0–§6：铁胆墨 14 色 / 排印骨架 / 基线 32px / 封信分物 /
邮戳只落真实事件 / T3 死刑清单 / 「纸先落、墨后渗」）；交互模式注册表
（读改模式 / 教学时刻模式 / 破坏性模式 / 三态模式 / 浮层模式）；skill
使用纪律（采纳前验证适配，不适配弃用留痕）；伙伴面（cs-2 全页档案 +
mc-1 信封沓 + mc-2 编辑台——8.2.2a）与设置面（rd-4 真面——8.2.8）的
位次；canonical §18 排除项不设计。

---

### 8.2 逐页方案

（每页：现役真值 → 目标设计（如有）→ 文案定稿 → 状态 → 组件 → 映射。
文案即定稿，语气总则见 8.4；v2-2 起本节无设计态块（原目标块已回填）。）

#### 8.2.1 门厅（R-1W 修订版——封面信笺）

现役真值（v2-1 起品牌换装，结构 = R-1W 封面信笺不动）：

```
      ┌────────────── 一张待拆的信（--paper-high + 双层发丝镶边）─────┐
      ｜ 2026 · 10 · 02（案头日期，真实客户端日期，mono）      〔邮票〕｜
      ｜                                                                ｜
      ｜                          〔印记 seal-press 入场〕               ｜
      ｜                         DEAR YOU（ls-caps 小字）               ｜
      ｜                           展信佳（display）                    ｜
      ｜                     见字如晤，今日如何（副题）                 ｜
      ｜                           ———（短界尺分饰）                    ｜
      ｜  致 明日之我：                                                  ｜
      ｜    今日落笔，明日展信。这张案头前，你同一位固定笔友通信，也    ｜
      ｜    在给明日之自己写信——两重收信人，同一张信纸。想写什么就写    ｜
      ｜    什么，中文英文都行；写错了，正是回信要讲给你听的地方。       ｜
      ｜    写着写着，它在旁听着。发现值得练的表达，它随信递来一条      ｜
      ｜    英文批注——答对答错都有回音，也可以先搁着。                  ｜
      ｜  又及：进门以后，底部三个词随时可走。温故摊着今天的复习        ｜
      ｜  与方向，抽屉收着它记住的事。                                   ｜
      ｜                       拆开这封信 →                              ｜
      ｜                        elc · web                                ｜
      └────────────────────────────────────────────────────────────────┘
```

- 组织：封面是一张完整的信笺对象——天头（案头日期 + #22 stamp 邮票角标，
  水印墨装饰）/ 印记（信封 + 封缄墨线，**封缄点 = 墨蓝**——品牌印记不是
  事件，朱砂不落）/ 英文并写小字与 display 题（展信佳 · Dear You——
  `BRAND` 常量消费面）/ 信体（称呼 · 两段缩进正文 · 又及）/ 进门链接
  （#1 --ink）/ 诚实 mono 落款。档位构图：≤480 信笺满幅；481–899 信笺
  560 垂直居中；≥900 信笺 640 落在案头（9.6）。
- 文案定稿（rd-2 豪放档逐字 + v2 换名）：称呼「致 明日之我：」；两段
  与又及如线框（语义底线三件在场：①「中文英文都行」②「英文批注」
  ③「写错了，正是回信要讲给你听的地方」）；进门钮「拆开这封信 →」；
  落款「elc · web」；题 = 展信佳、副题 = 见字如晤，今日如何、英文并写
  DEAR YOU（`BRAND` 大写消费）。
- 动效（⑨-5）：paper-settle（现役实现 = paper-drop + ink-wash ×1.3
  双动画 @ `--dur-settle`）信笺落座 + seal-press（现役实现 = ink-wash
  @ `--dur-ink`）印记浮现，
  均首绘一次，reduced-motion 随库尾总降级块归零。
- 状态：静态页无四态；localStorage 拒绝时直进案头（现役行为不动）。
- 组件：#13 brand-mark（--lg）、#1 btn--ink、#22 stamp。
- 映射：v2-1 已实施（index.html 门厅节 + `BRAND` 常量）；目标设计无
  新增（本屏 v2-2 只承受工艺巡检，见 ①.5 设计义务）。

#### 8.2.2 案头（信流与写信区）

现役真值：

```
  [印记] （主从条：当前角色名 + 身份行——端点驱动空槽，块可点）
         点开 = 信封沓（mc-1；沓中每封的「档案」动作进笔友档案全页）
  ─────────────────────────────
  （空厅，纸面中央一行系统小字：）
  信还没开始写——想从哪句起，就从哪句起。中文英文都
  行；写错了，笔友接得住。

  …信件（撕边回信 / 普通信；在途件带虚发丝角标）…
  …批注卡（见 8.2.10）…
  （失败，纸边小字：）
  这封信没有回音——笔友没能联系上模型端点（missing-secret）。
  ─────────────────────────────
  [ 今日如何？                  ] 寄出 →   ← v3-a 前的常驻全形（历史）
  ─────────────────────────────
     案头        温故        抽屉

v3-a 现役（两态同件，本节⑤）：

  提笔 · 今日如何？            寄出 →   ← 笔搁触发条（44px，收起态）
  ─────────────────────────────
     案头        温故        抽屉

  （点触发条升起写作态：）
  ↑ 收起            2026 · 10 · 02        ← 顶行（收起链 + dateline）
  致 Nell Alder，                          ← 称呼位（弱墨只读）
  ▏今日如何？                              ← 稿纸（吃满余高，字落线上）
  ▏
  ─────────────────────────────
                               寄出 →      ← 底行寄出链（右齐）
  （navdock 让位；Esc/↑ 收起/下滑 = 保稿收起）
```

- 组织：信流只放信与批注；失败注脚 = 纸边小字（人话主句 + 括号工程词）；
  没递批注的一轮静默；空态横幅不进信流（空态是读数块的答法）。
  主从条 who 块整体可点（键盘可达；品牌条不增长按钮元），点开信封沓。
- 文案定稿：空厅句「信还没开始写——想从哪句起，就从哪句起。中文英文
  都行；写错了，笔友接得住。」（客户端静态系统行，非伪造历史）；
  placeholder「今日如何？」；等待占位「信已寄出，等回信——笔友把灯
  留着。」；失败行「这封信没有回音——笔友没能联系上模型端点（{failure_reason}）。」；
  指路行「批注开着——回应写在上面那张；也可以直接写一封新信。」
- 状态：空厅 = 上述静态句；加载即历史（现役）；失败 = 纸边小字；批注
  轮询现役不动。
- 组件：#4 letter、#12 system-line、#3 note-paper、#15 word-card。
- 映射：v2-1 已实施（锚屏）；下列四件（①②③④）v2-2 已实施（本节
  各条即现役真值）。

① 【角色信息面板瘦身——现役（v2-2 落地；原目标设计，用户定向
2026-10-02）】案头主从条只留**当前角色姓名**一行（head 档读法）。
who-sub 长句族（大面积身份介绍行）已退役——身份介绍退入笔友档案页
（8.2.2a），案头只报名，不设展柜。**问候语子项停手呈报**（原目标：
右侧一行符合人物性格的问候语，从 scenario / opening / speech_style
派生句池、可随机切换、设置项位落 8.2.8）——施工期实测：/api/partner
卡面只回 name / identity_line / background / values / letter_habits
五键，scenario 与 opening 不在任何现役读面上（mc-2 编辑台的 veiled
「读不回」四面正是 personality / boundaries / opening / scenario）；
speech_style 是「写作风格散文」非问候素材，机械提取或翻译即造句——
按「语料面不足以派生问候句，停手呈报再裁，不得自行造句」的既裁纪律
停手；webui 侧以「零问候语句库字面」的负钉封死造句路径，待语料面
（scenario / opening 读面）落地后续刀接位。

② 【dock 与 flow 的层次质感——现役（v2-2 落地）】写信区（dock）与
信流（flow）的纸叠关系：**flow = 摊在案头上的信纸堆**（主纸
`--paper` 直出、零面板感，桌面包围与 `--stack-shadow-deep` 承托由
#stage 桌面档承担，不重复落）；**dock = 案头前沿的垫板层**（顶纸
`--paper-high` 浮起面 + 上缘发丝线 `--rule` + `--stack-shadow-soft`
向上承影落在前一封信的纸尾上——soft 的 y 分量即向上）——分层只用
paper 色阶 + 发丝线 + 两级墨色阴影，零描边框、零圆角面板（简报 §6
形态法则）；dock 聚焦微起（`:focus-within` translateY(-2px)）保留，
作为「垫板被手压起」的触感。输入框纸面 = 顶纸，与信流的主纸形成一档
色差——打字的地方比信纸「新」。

③ 【点词卡形态——现役（v2-2 落地；原目标：用户定向 2026-10-02）】
#15 word-card 为**双形态组件，媒体查询分档**（触屏档 = 输入形态查询
`@media (hover: none)`，与触屏纪律同族、非断点边界；桌面档 = 现役
浮卡）：**触屏档 = 底部覆盖面板（bottom sheet）**——fixed 底部、
左右拉满、贴底、安全区垫层，从屏幕下缘丝滑展开（`@starting-style`
纸面曲线：transform `--dur-note` 260ms × `--ease-paper`，opacity
×1.3 恒慢——同简报 §5 教学卡参数）；上缘发丝线 + 「收起」文字钮 +
墨色遮罩（`--ink` 元素透明度 0.4，禁毛玻璃）盖住下方屏幕，点遮罩 =
点卡外；Esc 关闭（v2-2 增）；DOM 移除语义不变。**桌面档**：保留点击
点近侧浮卡（viewport clamp 现役机制，定位走 `--wc-x/--wc-y` custom
props）——理由：桌面指针就在被点词上，卡贴词而现是视线最短路径；
bottom sheet 会把视线拽到屏底，桌面阅读面（`--measure` 版心）也会被
整幅遮断。两形态 = 同一组件的两档布局，数据、关闭语义与无障碍面
同源。

③-a 【点词卡第二档与供性分层——现役（v3-d 落地；词表调研报告
§3/§4 v3-3 组合）】**命中位图随信下发**：服务端以与点击同一套
窗口+匹配语义预计算每封信的命中位图（段落一行、一行一词），随
`/api/turn`（`word_hits` / `user_word_hits`）与 `/api/history`
（每轮两侧）下发；`letterWords` 分片时位图判 0 的词带
`.word--off`——**不装可点样式、点击短路**，「miss 静默」契约升级为
「miss 无样式」，可点的词必有卡（位图缺席 = 全供性，向可点方向容错）。
**词典第二档**：语料面 miss 后单 token 查询落离线小词典
（`elc.lexicon`，~1850 词中文简注 + 50 条缩写映射 + 朴素还原，纯
标准库零网络），出「词典」标注小卡（词头+词性+简注，无 senses/
examples/forms——不冒充教学卡；语料面信息量优先，corpus 命中永不落
词典层）；撇号归一（’→'）使弯撇号缩写可查。实测（报告 §9 口径，
29 封真实信件）：命中 14.5% → **89.7%**（去重 88.2%）。

④ 【触屏点词可发现性——现役（v2-2 落地；原目标：用户定向
2026-10-02）】**旧根因已除**：components.css 的 `@media (hover: none)`
半区给 `.say .word` 常显 `underline dotted` 的触屏镜像块已退役——
移动端整段对话英文词连缀成「波浪线」的根因不复存在；**「全文常显
点线」永禁（负钉在库：ux-1 套件 + v2-2 套件双面）。** 采纳的替代
两件（提示只走墨蓝族与透明度，零新色、零圆点、零图标）：
**(a) 仅最新一封信的词带弱底纹**——`.letter--latest .say .word` 带
`--accent-soft` 12% 底纹（`color-mix`，addLine 维护 latest 标记），
历史信静默——「当前可查」语义随信龄衰减，视线最干净；**(b) 按压即
亮**——`.word:active` 高亮 `--accent-soft` 30%（`:active` 是触屏
tap 的按压窗口，`--dur-micro` 档，松手即隐，零 JS）。备案（未采纳）：
无常显装饰的纯静默形态——若 (a)(b) 实测仍有发现性问题，回退至此。

（本节其余目标块无——工艺巡检义务见 ①.5，巡检所得另起登记条目。）

⑤ 【案头写信区两态化——现役（v3-a 落地；研究报告 §4 D-B 方案，
DEC-OPI-95287e92-…5 采纳）】写信区（.dock）从「常驻全形」改为
**两态同件**：**收起态 = 笔搁触发条**（一行触靶 `--dock-trigger-h`
44px：左侧占位投影文案「提笔 · 今日如何？」、右端寄出链投影——
触发条是 `form#send` 稿纸的**投影文案**，textarea 唯一真源，不做双
textarea；常驻税 163→104px 级）；**点触发条/寄出链 = 升起 `.dock--compose`
近全屏「新信纸」写作面**（⑩ 全页成员：fixed 全高、`--shell-w` 限宽、
桌面档两侧各让 `--dock-compose-inset`；navdock 让位——`--fold` 200ms
后 [hidden]，同门厅/全页语族；Esc 收起——浮层裁决之后的一层；触屏
辅出口 = 面板铬件上下滑，稿纸内滚动优先）。写作面的排印骨架：顶行
（「↑ 收起」+ dateline——本机当日，与边注栏同一数据源同一格式）+
称呼位（致 + 当前角色名，.who 端点驱动零字面，无名册时缺席不发明）
+ 稿纸（#2 pen 的 `--open` 尺寸修饰：吃满余高、超长内滚、字落线上）
+ 底行寄出链（右齐，同现役语汇）；寄出编排 = 现役链原样（盖戳/
在途封/postTurn），写作态先收（落 = paper-fold + ink-wash reverse）、
焦点回触发条（再点即回写作态）。**矮视口诚实降级**（`max-height:
520px`）：写作面降为展开条形态（top 归还、稿纸 autosize 封顶 160
内滚——`autosizeTo`/`clearAutosize`，内联样式面在库）。**草稿层** =
⑩ 10.3-6 同一定谳（退出保稿、寄出即清），桶 `draft-<character_id>`
（无角色落 `draft-local`）——与起笔桶同构独立 key。**批注开着**
（AWAITING_USER）：触发条文案态切指路行原文（components.js 与
#reply-guide 同拍同源同步），写作面内 #reply-guide 照旧——路由不变，
语义照旧。**沓开着**：置灰优先（⑩ 10.3-5——开沓先收写作态，触发条
同批不可点）。动效两行注册在 ⑨-5（落墨页签 / 写作态升落）。

⑤.1 【两入口分工定谳（v3-a）】写信的两条动线各归其位：**起笔
（8.2.2a）= 沓容器内的仪式写信**——从信封沓选定角色、容器向下延展
成写信工作区，是「郑重开始一段新通信」的门面动线（收件人信封面 +
容器内全流程 + 回执收拢）；**案头笔搁/写作态（本条）= 日常快聊**——
常驻触发条随手提笔、近全屏信纸展开即写，是「想到就说」的高频动线
（无收件人仪式——称呼位即当前通信对象）。两动线共享同一发送管线
（postTurn）、同一在途守卫、同一草稿安全律（保稿/寄出清），桶键
独立互不覆写。**用户首验否决面**：两入口的语义分工与写作面形态
（§4.4 偏离账 #1/#4——「写信区常驻全形」改「触发条常驻」）由用户
首验裁决，否决即回退。

#### 8.2.2a 笔友档案、信封沓与角色编辑台（cs/mc 现役真面）

现役真值（cs-0/cs-1/cs-2 + mc-0/mc-1/mc-2 六刀落地；rd-4 的浮层卡与
名册桩已整体退役）：

- **笔友档案全页**（`#space-partner`）：从信封沓中每封的「档案」动作进
  （参数化 `/api/partner?character_id=`），同门厅 cover 的整页形态，
  非浮层；返回钮回案头是唯一回途，导航条让位。五面数据只读
  `/api/partner` 一个端点（角色文本真源 `src/elc/persona/penpal.py`
  单一出处，webui 零字面）：① 档案头（真名 + 身份行 + 通信统计三数
  ——往来封数计入命令轮排除口径）② 人物节（角色包叙事化散文）
  ③ 她记得的关于你的事（诚实措辞，不承诺完美记忆）④ 近况（episode
  摘要 + 未完话头）⑤ 通信的日子（按日极简往来行数）。五面各走自己的
  三态（#14），一面对了别面不陪葬。
- **信封沓**（mc-1，案头主从条点开）：沓形 = 案头的一叠信封（微扇形
  错位叠放，rotate/translateX 从 stamp_key 确定性派生——同一角色恒同
  姿态，零随机）；当前通信的一封盖「当前」邮戳角标（`--seal`，真实
  状态事件——T2 合法面）；每封动作行四词（**起笔** · 对话 · 档案 ·
  编辑——「起笔」= 写信工作区入口，见下条）；沓尾 = 新建空白信封，
  只有「完整编辑」一个入口（v3-2R 定谳：**新建角色的表单归「完整编
  辑」（编辑台既有），不得占用「起笔」语义**——上一刀把「起笔」做
  成建卡表单的降级实现已被判词否定）。点沓中一封 → 滑到沓首
  微抬（260ms 减速长尾 + 让位 stagger）；再点或点「对话」→ 切换。
- **【起笔 = 容器向下延展成为写信工作界面——现役（v3-2R 重铸；
  用户判词整刀否定上一刀降级实现，2026-10-02）】**「直接起草编辑
  时，面板应当自动向下延伸拉开，是**整个容器的变化**，而不是多一
  个滚动条」：**起笔**半 = 点「起笔」（选定角色开始写信）→ 沓容
  器本体从当前高度**向下连续延展**（height 过渡，`--dur-settle` 档
  ≤320ms × `--ease-paper` 纸面曲线；reduced-motion 直落）至占据主
  屏的**写信工作区**（compose 面）；选定角色 ≠ 当前通信时先切换再
  延展。工作区内完成「写一封信并寄出」全流程：**收件人**（角色名
  与一句身份，只读——建卡表单形态禁入起笔语义）→ **多行写信输
  入**（.pen 稿纸，Enter 寄出 / Shift+Enter 换行，与案头同一手感）
  → **寄出**（信落案头信流：在途信封 + 「寄出」邮戳 + 批注轮询，
  postTurn 同一发送管线；在途守卫与案头同一枚）→ **寄出后回执**
  （「寄出了——」一拍人话；邮戳留在案头那封上，同屏 ≤1 枚不再盖）
  → **容器收拢**让位案头信流（`envsel--fold`，收拢方向与延展对称、
  同曲线反向；回执期间 Esc/「先搁着」回沓即取消自动收拢）。延展落
  定后笔尖聚焦（视口跟随，硬伤 C——「表单落在视口外像没反应」不
  发生）；稿纸起步 10 行不吃 .pen 家族 160 上限（长信不留小窗）；
  草稿安全见 ⑩ 10.3-6（退出一律保稿、寄出即清、按角色分桶）；寄出
  收拢后信流滚底（签名行不被输入条遮）。**编辑**半 = 编辑台在展开的沓容器内（`.envsel-editor`
  编辑面），容器带着九面表单的实际高度一次向下拉开；表单长就滚容
  器自己的编辑面（唯一滚动井），零新增页面级滚动条——v2-2 的独
  立全页 char-editor 与 editor-zoom 放大过渡退役，双滚动条（P2-8）
  一并消除。【禁】起笔 = 建卡表单 + 收沓回案头（上一刀形态，判词
  已否）；【禁】新页面切换；【禁】容器外新开滚动区。
- **角色编辑台**（mc-2 容器内 DIY 面，v3-2 重铸）：信封沓的「编辑」/
  空白封「完整编辑」进——**编辑台在展开的沓容器内**（容器向下延展，
  ⑩ 容器延展档）→ 九面
  表单（identity / personality / background / speech_style / values /
  boundaries / opening / scenario 等；读不回的面诚实注记）；veiled 四面
  「留空保留 / 写下盖上」（空值不伪装已填）；真 CRUD（内置卡可编辑、
  删除有确认；born/邮票不变）；开场信预览；400 人话中文化；三出口
  一致（Esc /「← 回沓」/「不改了」全部回沓，P1-4）。
- **【角色卡弹窗整体优化——现役（v2-2 落地；原目标：用户定向
  2026-10-02 第 1 条）】** 信封沓选择器（mc-1）的显示与动效已按简报
  §5「纸先落、墨后渗」整体重排：入场 = paper-drop `--dur-settle` 320
  大件档 × `--ease-paper` 减速长尾 + ink-wash ×1.3 恒慢；退场 =
  `envsel--fold`（paper-fold 200 × `--ease-exit` + ink-wash reverse
  恒慢——「收拢」语义）；预览切换节奏保持（transform 260 减速长尾 +
  让位 stagger，总封顶 320）。下两条（翻页全览 / 起笔向下展开）是本
  条的两个具体子项，同场统筹、同一动效语汇。
- **【翻看 = 容器升级为全览窗口——现役（v3-2 重铸 / v3-2R 零跳变
  修复；用户两项核心误读纠正之二）】**「翻看」不是加一个翻看按钮和
  单独的翻看页面，而是**整个角色卡的下拉窗口页面的完全升级**：沓面
  板（下拉容器）本体经一次同族容器延展过渡（⑩ 容器延展档，
  `--dur-settle` × `--ease-paper` 高度拉开）长成全览窗口——**过渡
  全程零跳变**（v3-2R 修复上一刀 F-1：升级 = **内容先装满**（隐藏层
  里异步灌完页卡，含卡面拉取）**→ 再量高 → 一次拉开**；上一刀量高
  发生在内容填入前，用户看到「长到一半→跳到全高」的 snap 伪影，已
  除名；代次守卫 `page.dataset.fill` 保证只有最新一次渲染落笔），翻
  页发生在窗口内——每页一张角色卡全貌（可读回的五面摘要——name /
  identity / background / values / letter_habits；personality /
  boundaries / opening / scenario 四面读不回 = veiled 语义，页卡如
  实注记，开场信预览位缺席不虚构）+ 页序计数（mono 竖排）；
  **横滑翻页**（`wirePageTurn`——ux-1 横滑守卫同法：横大于纵严格
  判定、单指重臂双指全拦、边界静止、零 preventDefault）+ **点击翻
  页**（两侧墨线 chevron #22 复用）；翻页动效 = page-turn（⑨-5 现
  役行）。v2-2 的「翻看/回沓一钮两态 + envsel-browser 子页面层」模
  式退役（同刀除名）。升级**主入口 = 点沓本体**（信封/动作/底行以
  外的容器纸面）**与滚到沓底再往下滚**（触屏主入口）；「翻开全沓
  ↓」文字链只作**触屏辅入口**（hover:none 档现位，桌面档不显示；
  窗口态的回程链「回扇叠 ↑」同档）。Esc 退一层回扇叠（⑩ 退栈）；
  翻页态不替换档案页——「档案」动作仍进全页；窗口里也能直接「起
  笔」（容器延展成写信工作区）。
- **【移动端沓 bottom sheet——现役（v3-2 落地，P1-5；v3-2R 三条硬伤
  收编）】** 触屏档（`@media (hover: none)`，与词卡 sheet 同法的输入
  形态查询分档——四档断点契约零新增边界）整沓落成贴底 bottom
  sheet：全宽、贴底、安全区垫层、顶缘 ≤2px（沿容器基形 2px，不另发
  覆盖声明）、墨色遮罩（`--ink` 0.4，禁毛玻璃）盖住下方屏幕，点遮罩
  = 点容器外；容器四态（扇叠/全览/编辑/写信工作区）在 sheet 形态下
  照常工作——升级与延展 = sheet 自身长高。窄屏旧疾（卡溢出/简介截
  断/动作行黏连）随之消灭。**v3-2R 三条硬伤收编**：① 沓开时常驻
  dock **淡化置灰且明确不可点**（disabled 形态复用，视觉可点性 =
  实际可点性——「看得见摸不着」除名；定谳理由见 ⑩ 10.3-5）；②
  触屏档沓叠态改**单卡纵排**（微扇叠放让位，每封独占一行、完整保
  住头部「致 + 名」，邮票不再压简介——卡右垫 64px ≥ 邮票占用，
  简介整句可读，消灭「看不清点的是谁」）；③ 起笔延展落定后笔尖聚
  焦（视口跟随——「像没反应」除名）。
- 映射：现役真面已实施（web.py 端点 + webui 七文件内）；v3-2 三块
  与 v2-2 保留块同一动效语汇，注册行见 ⑨-5。

#### 8.2.3 温故 · 今日（rd-3 修订版——默认层两块）

```
  温故 · 今日
  今日｜方向｜档案
  ─────────────────────────────
  今天的行动                 你的成长
   有一张批注等着你回应。      能做到：anyway。
   〔去回应〕                 还在练：i think。
                              暂时不能：no way。
   anyway · 今天到期
    教我这一句
   〔开始复习〕
  （空：今天不用复习，要不要聊一句？〔去聊一句〕）
  （成长空：学过一次之后，这里会出现你掌握的技能。
        先去案头聊一句，批注会自己来找你。〔去聊一句〕）
```

- 组织（rd-3 提案B；授权 `DEC-OPI-dc0ba4b6-…9` + 用户令②「大量信息
  并非用户需要看见的」）：默认层恰两块——① 今天的行动 = 到期 N 项 +
  进行中的批注 + 一个动词按钮；按钮 = 第一优先行动（批注回应 > 到期
  复习 > 邀请），「开始复习」直接开教第一句到期句（真动作不是导航），
  到期行仍带「教我这一句」行内钮；② 你的成长 = 恰 3 条词级结论句
  （「能做到 / 还在练 / 暂时不能」三档词级表达，聚合自批注判分——
  不是分数是结论；不显示数值/档位/置信度；不足 3 条如实显示有的几条，
  0 条 = pull-revelation 空态卡，给学习线索与直达路径）。
  **环块诚实省略：无可靠的连续天数数据源，今日进度又与行动块重复**
  （宁缺毋凑，两块是合法形态）。
- 文案定稿：批注在场「有一张批注等着你回应。」/ 钮「去回应」；空邀
  「今天不用复习，要不要聊一句？」/ 钮「去聊一句」；到期行沿
  「{表达} · 今天到期 / 过期了 + 教我这一句」；成长行「能做到：{表达}。」
  /「还在练：{表达}。」/「暂时不能：{表达}。」；成长空态「学过一次
  之后，这里会出现你掌握的技能。」+「先去案头聊一句，批注会自己来找
  你。」；成长三档映射 SUCCESS / ALTERNATIVE_SUCCESS → 能做到，
  PARTIAL / ABSTAIN → 还在练，FAILURE → 暂时不能。
- 移走清单（9.11-22）：页首计数摘要行退役（计数是副产品）；诊断五问
  用户面零渲染（归档读法——8.2.5）；可以练的表达迁档案（8.2.5）。
- 状态：两块各走 #14 三态（现役）。
- 组件：#14、#1（--ink 主钮）、行内按钮沿库外类 .teach-me。
- 映射：**纯前端重组，已实施**（成长聚合与行动合并客户端派生，无新
  端点；进行中的批注读 /api/teaching/current 只读面）。

#### 8.2.4 温故 · 方向

```
  温故 · 方向
  ─────────────────────────────
  你想把英语用在哪里——这是笔友记着的长期方向。
  每次保存都前移版本；上一版找不回来。

  长期目标                  （读编合一：当前值即编辑值）
   目标 1 · 技能〔口语 SPEAKING ▾〕
   目标 1 · 内容〔____________________〕
   从当前组合移除（保存后生效）
   加一条目标

  四项的轻重
   口语 SPEAKING〔1〕   听力 LISTENING〔未设〕  …

  要考的试
   〔CET4〕〔CET6〕〔IELTS〕〔TOEFL〕

  文风
   〔随意 CASUAL〕〔中性 NEUTRAL〕〔客气 POLITE〕…

            保存方向
  ─────────────────────────────
  批注频率
   现在：适度（BALANCED）
   〔不递 OFF〕〔少递 MINIMAL〕〔适度 BALANCED〕〔勤递 EAGER〕
            保存批注频率
  ─────────────────────────────
  这段通信的临时侧重（有才出现）…
  ▸ 词表原文（三面 · 本版只作参考）   （#21 折叠，默认收）
```

- 组织：读写合一（读卡取消，当前值直接进编辑面）；保存区独立成块，与
  频率写路径分界；参考词表折叠；版本号移出常显。
- 文案定稿：引导句如上（v2 换名：rd-2 句的自称主语随本刀改「笔友」
  ——记着方向的是与你通信的笔友）；「技能」代「模态」；保存回执
  「已保存（第 {n} 版）。」/「内容没有变化——没有写新版本。」；冲突句
  「这份方向刚在别处被改过——重新读过再改。」+ 钮「重新读过」；词表词
  中英并置（中文 + 等宽英文小字）。
- 状态：各面板 #14 三态现役；保存 busy 现役；未装配面诚实句现役保留。
- 组件：#16 field、#17 chip、#1（--ink / --pencil）、#21。
- 映射：**纯前端重组，已实施**；v2-2 基线重排已落地——表单行的行高锁
  `--lh-ui`/`--lh-small` 与基线对齐（#16 契约）；保存底栏 sticky 语义
  按 ux-1 现役（calc 对齐 dock 顶）保持。

#### 8.2.5 温故 · 档案（rd-3 修订版——收藏档）

```
  温故 · 档案
  ─────────────────────────────
  批注留过的痕迹与接下来的计划——要的时候来翻。

  痕迹
   攒够 30 次批注，这里会讲一个学期的故事——现在有 7 条。
   〔搜〕搜一句痕迹……
   ▸ 本周：3 次批注，主题 i think / no way
      i think  答得漂亮（今天 14:05）
      no way   没答中（昨天）
   （空：还没有批注留痕——聊起来才会有。）
   （进行时：批注正在来的路上……）

  搜信里的句子（rd-4）
   只搜已加载的最近 50 轮。
   〔搜〕搜信里的一句话……
      第 3 封（你）……片段……
      第 5 封（笔友）……片段……

  计划
   未来 7 天：今天 2、明天 1、往后 3。
   ▸ 计划明细（复习排程 · 目标）        （#21 默认收）
      复习调度（/api/schedule 分档）/ 学习目标（原值）

  可以练的表达
   ▸ 接话与转题（12）  anyway · by the way …   （#21 默认收 + 筛框）

  ▸ 按表达看：在学的表达                （#21 默认收：账表）
  ▸ 原始读数（给排查用）                （#21 默认收：证据原值 +
      观察读数——第一次展开才拉）
```

- 组织（rd-3 提案B；显示名 记录→档案，内部 id study-progress 零改名）：
  收藏档三层——① 痕迹 = 搜索框 + 聚合时间线（按周/月折叠成一行一句，
  点开见明细；明细读服务端已加载的最近几条，Wrapped 计数读全量
  evidence_claim_count；搜索过滤已加载的明细行——表达名 + 原 id）；
  ② 计划 = 一行「未来 7 天」+ 全量排程与目标降入折叠（时间敏感的是
  今天不是下周）；③ 可以练的表达（自今日迁入，家族分组 + 筛框不变）+
  按表达看（账表：schedule ∪ claims 按 target_id 合流）+ 原始读数
  （观察读数的唯一合法归宿，第一次展开才拉）。
- 加载态两形（NN/g）：进行时「批注正在来的路上……」区别于没有的
  「还没有批注留痕——聊起来才会有。」——未加载不得显示无记录。
- 复习调度区（主线-2）：计划明细折叠内的「复习日程」升为
  `/api/schedule` 的三态读面——①调度腿没装配（`available:false`）
  「复习调度腿没有装配——现在没有可显示的排程。」不虚构；②腿在但无
  到期/已排期行「现在没有到期或已排期的复习——批注来过才会排。」；
  ③有行 = Scheduler 自己的分档视图（今日到期 = DUE+OVERDUE 在前，
  接下来 = UPCOMING 窗口落点），行字段原值直出（间隔阶是实现词表，
  原样不造中文；无阶「未分阶」——types 的自有读法）。due 的决定只
  在 Scheduler（D-INV-009）——本区不做任何第二读法的分类。
- 表达足迹（主线-2，9.12-23④ 数据缝就此闭合）：按表达看每行下挂
  一枚「足迹」钮，第一次点开才拉 `/api/target_footprint?id=`（惰性
  ——不打开不花一次读）；三态全部如实：拉取失败可重试；没有证据
  「这个表达还没有留下学习足迹。」；有足迹按轮列「第 n 轮 · 条数
  （判分中文读法，未知值原样）」，轮次序数 = 轮的持久序（机械事实），
  无序的落 turn_id 短值。口径：只数 ACTIVE 证据（§18——只有 ACTIVE
  证据进估计；服务端字段 `active_claim_count` 自带读法）。
- 搜信里的句子（rd-4）：/api/history 的默认窗口（50 轮）内找一句话，
  口径写在脸上（「只搜已加载的最近 50 轮。」——检索自己的读面不带
  宽度参数，「加载更早」翻进信档的更早轮次不在检索面）；命中列
  「第 n 封（你/笔友）」+ 前后片段——历史轮次没有时间戳，一个日期
  都不造（第 n 封按已加载窗口内的顺序数）；同一轮两侧都命中列两行；
  无命中「这五十轮里没有这一句。」；跨信重现已由表达足迹读面落成
  （上款——检索本身不升级）。痕迹搜索的检索串并入中文读法（族名 +
  判词——「接话」「答得漂亮」也搜得到；rd-3 INFO-4 收口）；判分落
  **v2-1 起判分行不盖章**（邮戳只落寄出 / 结课 / 归档开启三类真实
  事件——见 ⑨-2 与简报 T2）：旧 rd-4 判分戳（成功族 stamp 水印小图）
  已随 v2 撤除，SUCCESS / ALTERNATIVE_SUCCESS / PARTIAL / FAILURE /
  ABSTAIN 全族缺位有钉（test_rd4_full_face）。**注记（v2-2 已对齐）**：
  来信侧标签已随本节文案改「笔友」（「第 n 封（你/笔友）」）。
- 诊断归档读法（9.11-22）：诊断五问与「为什么 · 原值」整体移出用户面
  ——/api/diagnostics 端点与其数据面钉保留在 API 层（web.py 冻结），
  前端调用与渲染整体移除；**用户面零渲染**、内部决策理由 = 噪音与
  焦虑源。观察流水留在原始读数深档（排查材料，非搜索对象）。
- 文案定稿：期待态「攒够 30 次批注，这里会讲一个学期的故事——现在有
  {n} 条。」（**不足门槛讲期待不讲遗憾**——数据不够就不解锁）；搜索
  无命中「没搜到这一句的痕迹。」；桶行「{本周 / 上周 / {m} 月 / 去年 /
  更早}：{n} 次批注，主题 {A} / {B}」；计划行「未来 7 天：今天 {n}、
  明天 {m}、往后 {k}。」（UPCOMING 窗口落在过去或 7 天外不上数，口径
  如实）；排程空态「还没有排程——批注来过才会排。」；账表列沿
  「痕迹 {n} 条 / 最近判分 / 复习」，判分词沿「答得漂亮 / 答了一半 /
  没答中」，复习列沿「今天到期 / 过期了 / 排上了 / 还没排上」。
- 状态：痕迹 / 计划 #14 三态（痕迹 loading 用进行时句）；折叠内面板
  原值三态现役；账表拉取失败 = 折叠内一行 + 重试。
- 组件：#16 field、#21 折叠组、#9 meter-row（账表行）、#14。
- 映射：**纯前端重组，已实施**（聚合 / 分桶 / 计数客户端派生，无新
  端点）。

#### 8.2.6 抽屉 · 记忆

```
  抽屉 · 记忆
  ─────────────────────────────
  笔友记住的事都在这里——一条条如实，分三摞收纳。
  记住：关系 0 · 剧情 0 · 学习 0 · 痕迹 0 · 存根 0  （摘要行）

  角色记忆（cs-2 分摞）
   笔友记住的——关于你们的通信。
   （关系 + 剧情：空态各说各的实话）
  学习记录
   教学系统的记录——笔友并不知道这些。
   （学习状态 + 痕迹）
  存根
   忘掉这件事留下的收据——只有单向摘要，没有正文。
```

- 组织（cs-2 三摞归属分区）：五面板按 `/api/memory` 的 domain 字段
  分三摞——角色记忆（relationship_memory + episode）/ 学习记录
  （learner_states + evidence）/ 存根（tombstones，审计）；归属标注
  写在每摞脸上。cs-2 收起/展开：五个面板各是一件 #21 折叠（默认收，
  组头 = 面板名 + 计数）——痕迹等内容不再永久摊开。字段名全中文化
  （「从哪记住的 / 敏感程度 / 保存许可 / 把握 / 指纹」）；指纹缩为前
  12 位等宽 + title 全值；时间一律 8.4 时间格式。
- 状态：#14 三态现役。
- 组件：#9 / #14 / #21。
- 映射：**已实施**（cs-2 分摞 + 折叠化）。

#### 8.2.7 抽屉 · 隐私

```
  抽屉 · 隐私
  ─────────────────────────────
  请笔友忘掉一些事——走出去就找不回来。

  这段通信
   把这段通信的全部记录请出抽屉——信件、批注痕迹与它
   留下的证据行，一并忘掉。
   〔忘掉这段通信的全部记录〕

  按表达忘掉
   忘掉某个表达的学习痕迹、学习状态与复习安排；信件
   本身保留。
   找一个表达……〔筛框〕
   ▸ 接话与转题（12） ▸ 留有余地（13） ▸ 应对与表态（24）
   ▸ 委婉说法（3）
   （展开后每行：表达名 ……〔忘掉这项的痕迹〕）

  按伙伴关系忘掉
   忘掉与这位伙伴的关系记忆（她记住的你们之间的事）——
   信件本身保留。
   伙伴名 ……〔忘掉与这位伙伴的关系记忆〕
   （空态：还没有正在服务的伙伴——先在案头挑一位笔友。）
```

- 组织：危险分级呈现——整段通信一处一钮；52 项目标删除按族折叠 + 筛框
  （与今日同法），危险不再均质平铺；按伙伴关系一面主线-1 接通（见下）。
- 文案定稿：引导句如上（v2 换名：请求句主语随本刀改「笔友」——
  记住的是笔友，忘掉的请求也递给她）；两层 confirm——其一「将把
  「{范围}」请出抽屉，找不回来。确定继续？」其二「再确认一次：忘掉
  之后无法恢复。」；结果「已忘掉：{范围}（存根 {n} 条）」/「没有什么
  可忘——它之前就不在抽屉里。」；结果尾句「这次忘掉留下的存根，在
  抽屉 · 记忆 里能看到。」
- **按伙伴关系忘掉（主线-1 接通，8.2.7 补缺）**：rd-4 时代的自认句
  「这版做不了——页面不知道伙伴的角色编号」退役——角色名册（mc-0）
  随行每位角色的 persona_id + 本页正服务的 current_character_id，
  两者一拼即诚实 referent；后端 `DeletionScope.RELATIONSHIP_PAIR`
  现成（迁移 0014 冻结词表），双确认与既有两面同形（同一 runDelete）；
  缺席（无正服务角色）保持诚实一句，不猜编号。E2E 钉在
  `tests/host/test_mainline1_settings.py`。
- 状态：删除列表 #14 三态；结果区现役；按伙伴关系面现役。
- 组件：#11 confirm-dialog、#1 --pencil、#16、#21。
- 映射：**纯前端重组，已实施；第三面主线-1 已实施**。

#### 8.2.8 抽屉 · 设置（主线-1 重铸②——真控制面；veto-R 模式可改重做）

现役真值（veto-R 重做后；主线-1 的读写骨架保留）：

```
  抽屉 · 设置
  ─────────────────────────────
  这台应用只服务你一个人（127.0.0.1，无账号无密码）。
  如实说
   模型端点与模型名由启动命令给定——页面不读取，也不显示。
   批注频率在 温故 · 方向 里调。
  教学模式
   {#27 墨选：手动（用户发起）/ 学习优先 / 平衡 / 娱乐·关系优先
    ——存值 = §12 枚举词；当前档 = 墨选现值；未声明 = placeholder}
   {当前档的分寸句一行（MODE_HINT）}
   {换档结果行（200/400 人话原样上浮）}
  教学策略
   批注频率有真消费方；七钮标「暂不影响行为」——先存后用，留空 = 未配置。
   {八旋钮：批注频率 = 墨选（中文档名）；七钮 = 档位墨选 +「未配置」}
   {保存钮 + 结果行}
  隐私与披露
   笔友能看到你的哪些档案事实，由披露规则说了算——
   规则在这里改；没有规则行时，缺省一无所露（fail-closed 缺省）。
   {规则行：角色名（+rawtag id）→ 中文层级墨选}
  显示与计量
   token 计量的显示开关——只活在当前标签页，关掉就复位。
```

- 组织（veto-R 统一规格，9.15）：panel-grid 两栏退役——设置节 =
  导语一行（.doc-line）+ 五节块（h3 + .doc-line 正文 + 控件）。
- **教学模式可改（veto-R 核心，用户 dogfood 首验否决「由启动命令给定
  不能改」的只读读法）**：`POST /api/settings/mode`（body
  `{"stage": §12 词}`，四词白名单 case-sensitive，词表外 400 人话）→
  服务端持久化（migration 0022 的 `app_setting` 泛用表，一键
  `rollout_stage`）+ **热改生效**（coordinator 的 wiring 以
  `dataclasses.replace` 换新对象——下一轮就按新档裁决，无需重启）→
  200 回读。语义澄清（写进代码注释与本节）：页面 mode 写 = 用户的
  显式档位表达，与改启动命令同一权力（单用户本地应用，一个主体）；
  gate 函数零改；默认 None 仍 DENY 自动教学。「由启动命令给定不能改」
  「换端点或换档 = 改启动命令再启动」两句随只读读法退役；「模型端点
  与模型名由启动命令给定」句保留（端点仍非页面可改面）。
- 端点（主线-1 骨架 + veto-R 增一写）：`GET /api/settings` 一读全归
  （rollout_stage = 生效档——热改后的 live wiring 值 / §5.1 policy
  十三列 / disclosure 规则集 + 三张服务端随行词表：频率四词、八旋钮
  白名单、§12 四档词——客户端零拷贝）；`POST /api/settings/teaching_policy`
  八旋钮全组 upsert（版本前移，同 200 / 409 纪律），词表外值与系统列
  （version / id / effective_from / updated_at）一律 400 人话拒写
  （mode 自 veto-R 起不在本写面——它有自己的门）。
- 教学策略旋钮（veto-R 档位化）：七钮自由文本框退役——各一枚 #27
  墨选，档位 = **display-layer 声明词表**（app.js 常量 `KNOB_TIERS`，
  canonical/实现枚举都无此词表，存值 verbatim 字符串列），「未配置」
  （null）诚实可选；「存面（暂无消费）」badge 改「暂不影响行为」。
- 诚实读法（veto-R 现役）：当前档 = 墨选现值（生效档，非启动快照）；
  未声明 = placeholder 弱墨「未声明——自动教学关着」。prep-1 层（无
  自动教学腿）如实一句「没装配自动教学腿——换档没有可生效的地方，
  什么都没写」且不落库。SECTION_PULLS 拉本节。
- 组件：#16 / #14（备用）/ #17（保留面）/ #27（模式 + 频率 + 七钮 +
  披露层级）。
- **问候语切换设置项位（停手呈报，随 8.2.2①；既裁记录保留）**：每日
  切换 / 每次进入切换两选项的项位随问候语子项停手挂起——问候语源
  （scenario / opening 读面）不在现役端点，控制不存在的功能是死 UI；
  语料面落地后续刀接位。
- 映射：真面已实施；重铸① v2-2 已落地；重铸②主线-1 已实施；完全体
  fr-A 已实施；**veto-R 重做已实施**；问候语项位待语料面裁决。

#### 8.2.9 全局壳

- 页题去重：六节的页内 h2 取消；spacehead 节名槽 = 唯一页题；页首引导句
  接 8.2 各页定稿。案头头部 = 端点驱动主从条（mc-1 起）。
- 节签 / dock / 门厅让位 / z 序：不动（R-1 已验收；v2 换名只改词面）。
- #21 折叠组（disclosure）契约见 ③；摘要行 = 屏级一行（.sub + mono
  数字），非组件不入库。
- 边注栏（≥900px）：案头日期（楷体手迹位——简报 T1 楷体三合法面之一）
  + 界尺；**装饰邮戳水印已随 v2 撤除**（邮戳只落真实事件，简报 T2）；
  aria-hidden；窄屏整条缺席。
- 映射：**已实施**（v2-1 换装 + ux-1 sticky 四面常显）。

#### 8.2.10 教学时刻面

- 卡头（rd-2 批注家族）：「批注：{功能句}」+ 状态行（服务端 status_cn
  原词，界面不自造——AWAITING_USER 词面「等待您回应」在 web.py 冻结，
  回应结果行用客户端读法「等你回应」，9.10-21 登记）；kind 只走中文
  映射（CURRENT_USER_ERROR → 你信里的句子），未知值**不兜底直出**，
  省略该行。
- 卡内指路行（回应面开启时）：「回应写在这张批注上（不是下面的信纸）。」
- 手写批注层（rd-4）：等回应的卡带红笔圈线（v2 起色 = `--seal` 朱砂
  ——待回应的批注是真实事件，T2 合法面；border 2px + rotate
  -2.5deg；静态形随卡递入一次，零新动效）；收场两态可分——成功族 →
  盖戳完成态（圈线摘下、#22 stamp 同枚印记按上），搁置/负值 → 淡出
  态；守恒律：一卡至多一处手迹。
- 文案定稿（rd-2 豪放档）：作答框「用英语写一句试试……」（**登记例外
  不动**——教学表达练习面，W-8 已裁）；钮「寄出回应」；回应寄出后
  占位「批改中……」；求助三词「提示 / 答案 / 讲解」，busy / seen 词族
  「取提示中…… / 已看提示 · 取答案中…… / 已看答案 · 取讲解中…… /
  已看讲解」；跳过「先搁着」（busy「搁置中……」、回音「先搁着了——
  回头再拾。」）；看答案 confirm「看了答案，完整说法就摆在眼前——
  看过之后仍可回应。要看吗？」；判分条「✓ 答得漂亮 / ◐ 答了一半 /
  ✗ 没答中」+ runtime 原话随后（「这次没法判」不动）；回应回音
  「回应已寄出。」；重试问句「再试一回？」。
- 卡内槽位装配（v3-1，B）：结果条 / 回试行（「再试一回？ · 状态 …」）
  都是**槽位件**——卡内各**至多一条**，新条原位改写，绝不 append 累积
  （槽位序 = 结果条在上、回试行在下）；「先搁着」并入拆装组
  `.skiprow`（与 `.replyrow` 同规，收场与再答时随组拆除）——守恒律：
  卡内**至多一枚**「先搁着」。
- PARTIAL 方向指引（v3-1，A3）：◐ 结果条在场时，其下伴一条人话指引
  「答了一半——目标表达已经在句子里了，把整句说完，或点「提示」再看
  一眼。」（绑既有「提示」求助钮的词族，零新控件）；指引行卡内至多
  一条，PARTIAL 退场（新判词非 ◐ 或收场）即摘。FAILURE / SUCCESS
  判词映射保持既有定稿不动。
- 参考答案独立区块（v3-1，B3）：REVEAL 交付走 `.note-answer`——
  「参考答案」标签打头 + 左缘界尺（`--pencil` 2px）与主纸垫底，与信尾
  视觉断开，**永不与回信文本混排**（数据缝 = `POST /api/teaching_reply`
  响应的 `delivery_kind` 字段，additive，随 `delivery_text` 同现；
  RETRY 固定行仍走 `.noteline`）。卡内至多一块，答案永远最新。
- 交付折叠（v3-1，B4）：`.note-delivery` 容器内最新一条 HINT /
  EXPLANATION / RETRY 交付显式（`.noteline`），更早的收进
  `<details class="note-history">`（组头「已看过的提示与讲解（n）」，
  默认收起）——多轮求助后卡内形态 = 至多一封当前回信（信流）+ 一条
  结果条 + 一条回试行 + 一块参考答案（若有）+ 折叠的历史。折叠是纯
  前端态，零新端点；信流里的系统回执行不折叠（信流是流式历史）。
- 点词卡：现役双形态见 8.2.2③（触屏 = bottom sheet、桌面 = 浮卡）；
  两处登记项保持
  登记（「命中可不含被点词」「25/100 lemma 超 3 词窗」——components.js
  头注）。
- 映射：**纯前端重组，已实施**；「回应期聊天框路由」沿 9.12-23 ②
  预告（乙案指路行已落，纯表达不改路由）。

#### 8.2.11 信档屏（现役——v2-2 落地，原目标设计）

按简报内核写的结构重铸（现役对应物 = 案头信流的历史恢复 + 档案节
搜信；本屏已落为 `#space-letters` 全页——案头的纵深，从信流尾部
「翻看以前的信 →」进，返回钮是唯一回途）：

- **信封形接线（T1-4 封/信分物——本屏的定义性形态，已接线）**：
  条目 = **信封缩略形**（`.env-mini`：矩形 + 中央折线 + 封舌 polygon，
  4b 在途信封形的缩略读法——屏级形态，同 mc-1 先例不入组件注册表）；
  **展开读 = 信纸**（同一物件展开，不是跳页换新物件——letterNode
  复用 #4 的排印骨架，展开动效 = ⑨-5 paper-unfold）。条目列表都是
  归档件（在途形态只活在信流）。
- **归档戳挂点（已接线，`DEC-OPI-a31b14c9-…16` ⑦ 形态位）**：翻开
  信档 = **归档开启**（T2 邮戳三真实事件之一）——屏头盖一枚**日期
  戳**（`.postmark--archived` 形态、`--ink-ghost` 褪色墨、4c 双圈圆、
  rotate 微旋，内字 = 打开当天的月·日，客户端真实日期）；**同屏
  恰 1 枚**（本屏的定义件；其余屏多数 0，纪律不变）。
- 排印骨架：展开的信纸 = #4 letter 完整骨架（dateline / salutation /
  正文段距模式 / complimentary close + signature 楷体手迹位 / P.S.）；
  基线 32px 网格同锁。
- 口径诚实（写在脸上）：只摊开已加载的窗口（/api/history，默认
  50 轮），首行口径句「只摊开已加载的窗口——第 n 封按窗口里的顺序
  数；「加载更早」往前翻，翻到头为止。」；无时间戳的轮次不造日期
  （第 n 封口径沿 8.2.5）。
- 加载更早（主线-2，9.12-23④ 预告位次的「真全历史」数据缝就此
  闭合）：服务端 `has_more` 是诚实分页位（有界读多取一行判的，不是
  猜的）——有就给一档 50 轮的「加载更早」钮（显式 `?limit=` 宽度，
  默认窗口一字不变）；翻到头按钮退役，落一句收尾「更早的信没有了
  ——以上是全部。」。
- 状态与组件：条目列表 #14 三态；信封条目 = 4b 的缩略读法（屏级类，
  未新增注册组件）；展开 = ⑨-5 paper-unfold。
- 零开闸面：本屏读面 = `/api/history` 的宽度参数（`?full=1` /
  `?limit=<n>`，主线-2）——纯读面纵深，零新写面、零迁移；信档的
  默认窗口语义不变（不带参数仍 50 轮）。

#### 8.2.12 观察仪表屏（现役——v2-2 落地，原目标设计）

按简报内核写的结构重铸（现役对应物 = 档案节「原始读数」折叠的入口 +
`python -m elc observations` 命令行读出；本屏已落为 `#space-obs` 全页
——从档案节折叠内的「翻开原始读数 →」进，返回钮回温故 · 档案）：

- 定位延续 rd-3 归档读法：观察读数 = **排查材料**，不进任何默认层、
  不做运营仪表盘——本屏是「原始读数」的专门面，给排查与校准用，
  不是给学习用。
- 组织（已落）：人话摘要行（一行封顶：六表张数 + 合计行数 + 门规
  漂移信号行数——**诚实口径**：spec 语汇的「本会话轮数 / 批注递出数 /
  误报数」在现役 observations 读面（六表 durable counts + 漂移信号）
  无直接对应列，摘要给可得计数、不硬凑无源的数）+ 六表逐表 #21 折叠
  （默认全收）+ 指标定义折叠（英文原文不翻译，8.3 原则）；表内原值
  直出（#9 `.kv` mono + tabular-nums），零图表、零彩色、零徽章——
  数据列是账页不是看板（T3 死刑清单）。
- 排印与质感：mono 微标签配方（`--meta-mono`）、行高锁 `--lh-ui`。
- 状态：每表独立三态（单表 error 落表内一行）；第一次展开才拉（进屏
  拉取，档案节现役语义迁入）。
- 组件：#21、#9、#14（屏级三态）、#16（筛框备用）。
- 零开闸面：读面 = 现役 observations 端点；无新端点、无写面。

---

### 8.3 术语翻译表（工程词 → 通信语言）

总则：状态 / 枚举只出中文（原值归「原始读数」）；存储词表值中英并置
（中文在前，英文等宽小字在后）；专名（CET4 / IELTS / TOEFL）不译；
**未列出的词不伪装翻译**——原样小字呈现并登记，下次触碰时补行。
（v2 换名注：rd-2 表的拟人主体旧称全列随本刀改「笔友」——
与你通信、旁听、记着事的那一位。）

| 工程词 | 通信语言 | 备注 |
|---|---|---|
| teaching target / 可教目标 | 表达 | 「可以练的表达」 |
| canonical_key / target_id | 表达名 | 界面只显示 spoken 形（i think） |
| teaching moment / 教学时刻 | 批注 | rd-2 起（原「短笺」）；批注卡头「批注：{功能句}」 |
| conversation | 这段通信 | |
| turn | 一封信 / 一来一往 | |
| delete / deletion | 忘掉 | 动词「请笔友忘掉」 |
| tombstone / 删除台账 | 存根 | 「这次忘掉留下的存根」 |
| entity_hash | 指纹 | 前 12 位等宽 + title 全值 |
| gate | 门规 | DENY = 拦下 |
| gate reason codes | 门规理由（逐码） | 映射全集在实现刀四查列全；未知码原样小字 |
| planner / planner evaluation | 笔友（想过）/ 笔友的盘算 | 拟人主体 = 笔友（v2 换名） |
| diagnostics | 为什么 | |
| observations | 原始观察读数 | 归折叠区；指标定义原文不译（折叠呈现） |
| rollout stage | 教学模式 | Study-first → 学习优先 |
| degraded | 从简处理 | |
| NO_TARGET | 没什么可教 | |
| goal/policy 版本号 | 第 {n} 版 | 只出现在保存回执与冲突句 |
| provenance | 从哪记住的 | 记忆面 |
| sensitivity_class | 敏感程度 | |
| persistence_authorization | 保存许可 | |
| confidence | 把握 | |
| evidence | 痕迹 | 正式句可保留「证据行」 |
| learner state | 学习状态 | |
| review_state NOT_SCHEDULED | 还没排上 | |
| review_state UPCOMING | 排上了 | |
| review_state DUE | 今天到期 | |
| review_state OVERDUE | 过期了 | |
| review_urgency / spacing_stage / 窗口起止 | （不直出） | 归原始读数 |
| outcome SUCCESS | 答得漂亮 | rd-2 豪放档（原「答对了」） |
| outcome ALTERNATIVE_SUCCESS | 答得漂亮（另一种说法也算） | |
| outcome PARTIAL | 答了一半 | rd-2（原「答对一半」） |
| outcome FAILURE | 没答中 | |
| outcome ABSTAIN | 这次没法判 | |
| action TEACHING_OPEN / HINT / REVEAL / EXPLANATION | 留了批注 / 给了提示 / 摆了答案 / 给了讲解 | rd-2：TEACHING_OPEN 原词「递了短笺」 |
| lifecycle AWAITING_USER | 等你回应 | 回应结果行的客户端读法（rd-2）；卡头状态行走服务端 status_cn（词面「等待您回应」，web.py 冻结） |
| kind CURRENT_USER_ERROR | 你信里的句子 | rd-2（原「来自你的句子」）；未知 kind 省略该行，不兜底 |
| character / penpal / persona | 笔友 | v2 定稿；内置首角色 Nell Alder（名字端点驱动，界面不写死） |
| 表达家族 discourse | 接话与转题 | |
| 表达家族 hedge | 留有余地 | |
| 表达家族 pragmatic | 应对与表态 | |
| 表达家族 softener | 委婉说法 | |
| 其他家族（colloc / phrasal / idiom / frame 等） | 出现再定，先原名小字 | 不伪装翻译 |
| goal_modality SPEAKING / LISTENING / READING / WRITING | 口语 / 听力 / 阅读 / 写作 | 中英并置 |
| register CASUAL / NEUTRAL / POLITE / FORMAL / ACADEMIC / PERSUASIVE / LITERARY / PLAYFUL | 随意 / 中性 / 客气 / 正式 / 学术 / 说服 / 文雅 / 俏皮 | 中英并置 |
| frequency OFF / MINIMAL / BALANCED / EAGER | 不递 / 少递 / 适度 / 勤递 | 中英并置 |
| 时间戳 | 今天 14:05 / 昨天 / 9 月 21 日 | title 全时间戳；ISO 归原始读数 |
| failure_reason（missing-secret 等） | 人话主句 +（原值） | 括号等宽小字 |
| utility / activation_threshold | 分量 / 门槛 | 只用于「为什么」，不进信流 |
| exposure / overexposure | 递过 / 递得太勤 | 只用于「为什么」 |
| false positive | 误认 | 只用于「为什么」 |
| polarity | 正负 | 正面 POSITIVE / 负面 NEGATIVE / 中性 NEUTRAL |
| performance_type | 出力方式 | 认出来 / 跟着写 / 引着写 / 自己写 / 脱口写出 / 自己改对 / 写错了 / 用偏了（八值原文小字） |
| target_type | 目标种类 | 资源 RESOURCE / 能力 CAPABILITY（现役语料只有资源） |
| evidence_modality | 凭据渠道 | 写下的英语 TEXT_PRODUCTION / 读懂的英语 TEXT_COMPREHENSION |
| memory_type | 记的类别 | 你说过的事实 / 共同经历 / 伙伴的印象 / 约定 / 未了的话头 / 两人玩笑 / 关系里的事 / 说话的偏好（八值原文小字） |
| entity_kind | 类别 | 这段通信 CONVERSATION / 表达 LEARNING_TARGET / 伙伴关系 RELATIONSHIP_PAIR |
| state_keys / estimator_version | 记着哪些状态 / 估算法版本 | 值原文小字，不译 |
| evidence_watermark | 证据水位 | 现役标签已译；数值归 mono |
| goal_portfolio_id / goal_id | （不直出） | 组头原文小字；版次人话见「第 {n} 版」行 |
| teaching support / delivery | 帮助 | 「你收到了哪些帮助」 |

### 8.4 文案总则

1. **人称**：对用户称「你」，不称「您」；应用叙事的声音是「笔友」
   （第三人称的地方，不装成人——旁听、回信、记着事的都是笔友，v2
   定谳）；笔友有名字时用名字（端点驱动），避免代词。
2. **口吻**：克制的书卷气——短句、实词、不用感叹号（引述除外）、不
   卖萌、不客服腔（禁「请问 / 您反馈的问题 / 很高兴为您服务」）、
   不打鸡血（禁「太棒了 / 加油」）。
3. **诚实的表达式**：缺 =「还没有……——（怎样才能有）」（模板出自
   记忆页空态，升格为全应用范式）；不能 =「这版做不了——（一句原因）」；
   说不准 =「说不准」；失败 = 人话主句 + 括号工程词；机械事实（版本 /
   时间戳 / 原值）有且只有一个家 = 折叠的「原始读数」。
4. **危险与不可逆**：先讲会失去什么，再要两次点头；两次确认各说一件事
   （一说范围，二说不可逆）；危险入口视觉安静（弱化小钮），确认才加重；
   结果只说 runtime 自己报的数。
5. **动词表**（通信世界）：写 / 寄 / 回 / 递 / 收 / 记住 / 忘掉 / 摊开 /
   收起——禁系统动词（刷新 / 拉取 / 读取 / 提交 / 配置）。
6. **数字与时间**：计数用阿拉伯数字；时间用人话格式（8.3）；本机单用户，
   跨年只到「去年」为止，不设计更多。

#### 8.4.1 语气宪法（rd-2 定稿 · 2026-09-30）

（rd-2 起口吻从 8.4 第 2 条的「克制的书卷气」升「洒脱豪放」档——用户
裁定 `DEC-OPI-dc0ba4b6-…13` 之②；本节七条是豪放档的护栏，与 8.4 冲突
处以此为准，调研底稿 = `docs/research/2026-09-30-frontend-redesign-research.md`
调研E。v2-s 换名随迁：第 6 条自称改「笔友」，其余六条一字
不动。）

1. 一句一事，主句 12–22 字；30 字长句只许铺陈画面，一屏最多一句；
   禁同义反复。
2. 破折号一屏 ≤2 处；全站不用感叹号（教学反馈例外且最多一个）；问号
   只用于真问句。
3. 一屏最多一处「文」——引文必须署名；古语词必须是常用词；自造诗性
   一律现代白话，不仿古、不写「古人云」。
4. **功能语义优先（不可牺牲）**：① 中文也可以写 ② 教学发生在英文
   ③ 写错会被看见且被回应——冲突时清晰优先，氛围让路。
5. 禁用：喊话祈使（立即 / 马上 / 快来）、网络热词、机械对仗假古风、
   综艺腔、emoji 作语气。
6. 对用户称「你」（不用「您」）；自称「笔友」（第三人称，不用「我们」
   避免客服腔；v2-s 换名：rd-2 原自称旧词随品牌换名退役——
   回信的、旁听的、把灯留着的都是笔友）。
7. 错误反馈写具体改法（「这个词换成 X 更自然」）；不写「错误 / 失败」
   标签，也不写空洞安慰。

动作词表：寄出、收起、回信、留一句、搁一搁、翻看；不夹带「提交 /
确认 / 操作成功」。

### 8.5 前瞻预留

- **流式回复**：「信已寄出，等回信——笔友把灯留着。」占位即流式落点
  （rd-2 定稿句，原「（回信在途中……）」；v2-1 措辞精修：自称主语改
  笔友）——同一位置渐进显字，信纸结构与点词分片不变；信笺语言天然兼容
  逐字上纸。
- **历史回看 → 信档屏**：8.2.11（现役，v2-2 落地）承接「以前的
  信」——信封形接线 + 归档日期戳（`DEC-OPI-a31b14c9-…16` ⑦ 形态位）；
  /api/history 50 轮窗口口径不变。
- **多伙伴**：cs/mc 六刀已兑现（信封沓 / 编辑台 / 每角色一会话 / 参数
  化档案）；沓内翻页全览 = 8.2.2a 目标块（用户定向 2026-10-02）。
- **设置面**：rd-4 真面（8.2.8）+ v2-2 目标件（问候语切换项位 / 模式
  真读面端点——9.12-23 ①）。
- **数据增长**：52 → 100+ 表达后，家族分组 + 折叠 + 筛框线性扩展
  （组键是语料自身的 taxonomy 段）；摘要行不变；档案页从空到满不改版。
- **功能增长**：新读数归 温故 · 档案 / 观察仪表屏，新私事归抽屉，新
  行动归案头 / 今日；新页级功能 = 空间内加节（节签横排可扩），
  **不为新功能加新空间**（dock ≤5 红线）。

### 8.6 实现映射与状态

| 页 | 状态 | 说明 |
|---|---|---|
| 门厅 | **已实施**（v2-1 换装） | 展信佳 · Dear You 封面；`BRAND` 常量单点 |
| 案头（信流与写信区） | **已实施**（v2-1 锚屏 + v2-2 四件） | 主从条瘦身（问候语子项停手呈报）/ dock 垫板层次 / bottom sheet / 触点提示两件，8.2.2①-④ 全落 |
| 笔友档案、信封沓、编辑台 | **已实施**（cs-2/mc-1/mc-2 + v2-2 两件） | 翻页全览（page-turn + 横滑/chevron）与起笔向下展开（fold+resettle 同帧）已落 |
| 温故 · 今日 | **已实施**（rd-3） | 默认层两块 |
| 温故 · 方向 | **已实施**（v2-2 基线重排） | 读写合一；表单行行高锁整 px 档 |
| 温故 · 档案 | **已实施**（rd-3/rd-4 + v2-2 对齐） | 「第 n 封（你/笔友）」标签已落；观察读数入口行 |
| 抽屉 · 记忆 | **已实施**（cs-2 三摞） | 归属分区 + 折叠化 |
| 抽屉 · 隐私 | **已实施**（v2-2 对齐 + 文档排印） | 「请笔友忘掉」句 + .doc-line 已落 |
| 抽屉 · 设置 | **已实施**（rd-4 真面 + v2-2 重铸①） | 排印重铸已落；问候语项位停手呈报（随 8.2.2①）；模式真读面待端点裁决 |
| 信档屏 | **已实施**（v2-2，8.2.11） | 信封形条目 + 归档日期戳 + 展开读信纸 |
| 观察仪表屏 | **已实施**（v2-2，8.2.12） | 专门面：摘要一行 + 六表折叠 + 指标定义折叠 |
| 全局壳 | **已实施**（v2-1 + ux-1） | 边注栏水印撤除；sticky 常显 |
| 教学时刻面 | **已实施** | 红笔圈 = 朱砂（v2 T2 对齐） |

冻结线（v2-1 已履行存证）：十二既有端点零改动 + cs/mc 按各自任务书
新增端点；src 限 `webui/`（+ 既有壳钉随迁）；词表中文映射是**表达层**
（客户端展示），不改任何存储值。**v2-2 冻结线（已履行）**：src 仍限
`webui/`；零新端点（信档读 /api/history、观察读 /api/observations
皆现役读面）、零迁移、`/api/settings` 未动（预计中的读面未裁未做）；
词表中文映射仍零存储值改动。

### 8.7 实现注记（R-1R 落地时的注记存目；v2-s 起为历史注记——冲突处以各刀登记与现役节为准）

1. **短笺卡 kind 映射**：客户端表 `MOMENT_KIND_CN` 两键——
   `CURRENT_USER_ERROR → 来自你的句子`（8.2.10 给定；rd-2 起
   界面词 = 「你信里的句子」）与
   `RESOURCE_PRACTICE → 资源练习`（镜像服务端 `kind_cn` 的原词，非客户端
   自造译名）；其余未知值省略整行（不兜底直出，蓝图原话）。
2. **`<select>` 的中英并置**：`<option>` 只能是纯文本，无法挂等宽小字
   span——目标技能下拉的并置退化为纯文本形态「口语 SPEAKING」；chips 与
   field 名牌保持富形态（中文 + `.rawtag` 原文小字）。
3. **「原委在」链接**：blocked 行（两形）已随 W-8 从信流退役；「为什么」
   的读出归 温故 · 档案 why_not 面与原始读数（现役读法）。
4. **筛框无命中句**以蓝图 8.2.3 为准：「没有叫这个的表达。」
5. **作答/寄出的回音行**：作答成功回音后改「回应已寄出。」、跳过回音
   「先搁着了——回头再拾。」（rd-2 批注家族，8.2.10 定稿）；失败回退
   「请求没送到——再试一次。」。
6. **空厅句是客户端静态系统行**（无历史时一行，第一封信寄出即撤），
   不是伪造的历史记录。
7. **「为什么」面板**的 `benefit_score`/`cost_score` 原值不进中文行——
   它们的归宿是档案页「原始读数」区的「为什么 · 原值」（诊断载荷的
   逐字 JSON；rd-3 起整体归档读法，见 8.2.5）。
8. **刷新/拉取钮全退**（进节即拉即唯一拉取点）：today-refresh /
   learning-refresh / diag-refresh / mem-refresh / goal-refresh / obs
   六个 id 退役（观察读数改为「原始读数」区第一次展开时拉，失败区内
   一行 + 重试）；`goal-list`（方向页读卡，读写合一取消）与
   `target-list`（记录页可教目标 52 行，唯一居所 = 今日）两个面板 id
   退役。
9. **错误/空/加载三态的既有词**（读取失败 / 暂无数据 / 取信中…）是
   ⑧ 8.1.3「读数块一律 #14 state-banner 族（现役）」的保留面，未按
   8.4 动词表改写；若用户首验要求改写，另起一刀。
10. **隐私页拒绝行**：「没能忘掉。」+ 服务端 message + 括号工程词
    （code 等宽小字）；网络失败「请求没送到——再试一次。」（8.4 失败
    = 人话主句 + 括号工程词的兑现）。

---

## ⑨ 视觉工艺规范（R-1V 立 · v2 内核重写）

> 地位：本节是视觉工艺层的规范出处。v2 起工艺权威 = 简报 §0–§6
> （铁胆墨 14 色 / 排印系统 / 信件机制层 / 动效手感 / 形态法则）；
> 本节把简报参数与 webui 实现的对接面写全，参数唯一出处是 ② 的
> token 表。⑧ 的信息架构与文案、F-1R 的形态法则（零卡片/零气泡/零
> 青绿；圆角 v2 收窄一档：信纸物件 ≤2px，仅邮票/邮戳圆形）、Python
> 侧端点与 web.py 允许表——全部不动。设计义务（用户元指令 2026-10-02）：
> 高级动效应自然设计，总控/执行者主动巡检优化点，不等用户提（①.5）。

### 9.1 排版标度

九档标度（简报 §3b，token 逐值见 ②-4；行高写整 px）：

| 档 | px × 行高 | 字距 | 用面 |
|---|---|---|---|
| display | 34 × 42 | +0.01em / 西 −0.01em | 门厅题/信头（宋体 400，禁 700） |
| title | 24 × 32 | +0.02em | 节题/页级大题 |
| head | 18 × 26 | +0.03em | 卡题/词头/批注头 |
| **body** | **17 × 32** | +0.01em | **信件正文**（1.88 为中文满框留气） |
| body-latin | 17 × 28 | 0 | 纯英文段（Sitka/Constantia） |
| small | 14.5 × 24 | +0.01em | 词卡释义/批注正文（连续阅读下限） |
| hand | 19 × 30 | +0.04em | 手迹位（KaiTi，≤2 行 ≤1 处/屏） |
| ui | 12.5 × 20 | +0.02em | 按钮/界面小字 |
| micro | 11.5 × 18 | 大写 +0.14em | 元信息/节名——**禁排中文整句**，只许 2–4 字标签与数字 |

- 字体栈五条见 ②-3（简报 §3a；离线、仅 Win11 系统字体；CJK 回退次序
  固定）。**楷体边界**：仅 3 个用面（落款、案头日期、边注），17–24px，
  每屏 ≤2 行 ≤1 处；禁作正文、禁 <16px、禁 >28px。
- 工艺法则（简报 §3c 十条，逐条可执行）：中文正文 ≥15px；禁合成粗体
  （宋/楷 700 发糊——中文标题靠字号跳档 + 字距）；微标签统一「大写 +
  0.14em 字距 + 降一档重」，不用 small-caps；信件正文旧式数字
  （Georgia/Constantia 默认 onum），数据列等宽 tnum；中文全角「」、
  西文真弯引号“”，`text-spacing-trim: trim-start` 以 `CSS.supports()`
  探测启用；信件流段落 = 段间距 0.75em + 零缩进，中文文档页（设置/
  隐私）才 `text-indent:2em` 零段距；`text-wrap: pretty`（正文）/
  `balance`（标题）；行高只写整 px；中英混排不手工插空格（ex-height
  匹配由字体栈保证）；正文字距 0–0.02em。
- mono 细节：数字一律 tabular-nums（摘要行 `.sumnum`、仪表行 #9）；
  日期 / 指纹 / 版本号 / 原始 id 走 mono micro（`.rawtag`）。
- 字重：衬线正文 400，卡题与词头 600（衬线 700 禁用于中文面——合成
  粗体；head 档需要更重时切雅黑/等线真 Bold），sans 小标 500；反白仅
  `chip--on` 一处。

### 9.2 间距节奏

- 4 基数八阶（`--sp-1`…`--sp-8` = 4/8/12/16/24/32/48/64px）：新写的
  尺寸规则一律走阶，不裸写像素。
- **大处疏朗、密处有致**：节与节之间 24–48（--sp-5..7），页首引导句
  后 16（--sp-4）；行内与卡内 4–12（--sp-1..3）。发丝线分区（#5）是
  疏密的分界线，不是容器——均匀的大空白 + 细字（白板观感）是反例，
  疏密对比才是信笺。
- **基线网格**：`--baseline: 32px`（= body 行高）——正文行高、稿纸
  横线周期、批注卡内文字全部锁死同值，`background-position` 对齐
  首行，**字必须落在线上**。
- 版心 `--measure: 34em`（≈578px）；阅读宽：信纸栏 ≤640px（9.6）；
  阅读左右留白 `--read-pad`；页边距 ≥2 行高。

### 9.3 质感与层次

- **纸系四层**（同色系深浅，零彩色）：主纸 `--paper` / 顶纸
  `--paper-high`（hover 微起、浮层卡面、dock 垫板目标态）/ 次纸
  `--paper-2`（批注底、垫纸层）/ 桌布 `--desk`（≥900px 案头底）。
- 发丝边两档（`--rule` / `--rule-soft`，钉）；界尺与角饰用**水印墨**
  `--ink-ghost`（永不作文字）；水印墨同时是墨水物理的起笔色
  （新到信 `--ink-ghost → --ink` 一次性过渡 ≈600ms，reduced-motion
  直落终态——简报 T1-3「墨是暖纸上的冷墨，层级靠浓淡不靠灰」）。
- **纸叠偏移阴影两级**（rd-1 面6 解禁重写；v2 值 = `rgba(25,27,30,…)`）：
  走 `--stack-shadow-*`（轻=右上 soft / 重=左下 deep；墨色同源、方向
  不统一、与发丝描边配对、禁大面积模糊投影型）——应用面：`#stage`
  在桌布（≥900，deep）/ `.note-paper` 在信纸（soft）/ 词卡垫纸层
  （soft）/ 信封沓每封（soft，mc-1）。`rgba(0,0,0,…)` 阴影与两级之外
  的自造 shadow 永禁（F-1R 历史提交原文保留不改写；解除登记见 ②）。
- 撕边/撕缝：`.letter.me` 的 clip-path 撕口（钉——人手触碰过的件才有
  毛边，简报 T1-1）与 #7 resultstrip 的 1px dashed 撕缝线。
- 折痕（简报 T1-5）：归档件展开时两条 1px 横线（距顶 1/3 与 2/3，
  opacity 3–4%），淡到初看不见、不压字（8.2.11 信档屏载）。
- 印记母题：#13 brand-mark（信封 + 封缄，**封缄点 = 墨蓝**——品牌印记
  不是事件，朱砂不落）；**朱砂 `--seal` 只盖真实事件**：邮戳（寄出/
  结课/归档开启三类）/ 红笔圈（学习反馈存活期）/ 批注圈线；每屏 ≤1
  处。档号/编号/日期 = 等宽小字 + tabular-nums，只标真实编号，≤2
  处/屏（简报 T2 全量纪律以简报为准）。

### 9.4 图标集契约（#22 icon-set）

- 统一 20×20 网格、统一笔重 1.5（`--icon-stroke`）、统一圆角端点；
  `currentColor` 随宿主墨色层级（弱化位 `--ink-faint` / 水印位
  `--ink-ghost`）；默认见方 `--icon-size` 18px，语境尺寸随宿主登记
  在 #22 契约块。
- **现役十枚与锚位**：`search` → 筛框名牌（随 #16）/ `chevron` → #21
  折叠箭头 / `note` → #3 卡头 / `write` → 回信在途中（.typing）/
  `inbox` → 空厅（.sysline.emptyhall）/ `lamp` → #14 空态 / `stamp` →
  门厅封面邮票角标 + 教学卡结课邮票 / `desk` → #18 案头签行 /
  `revisit` → #18 温故签行 / `drawer` → #18 抽屉签行（v3-a 三枚——
  「禁止变体：图标」契约显式修订，见 9.13；锚位 = 图标与文字标签
  同钮，图标永不单独承担语义）。（v2 随边注栏水印撤除退役的那枚
  圆戳图标已出集——注册的图标是使用的图标，注册表不做阁楼。）
- 新增图标：同网格同笔重自绘 + ⑤ 四步登记；永远 `aria-hidden` 且
  锚位必有文字同行（图标永不单独承担语义）。
- 禁：外链图标 / 图标字体 / data URI / 彩色填充 / 第二套网格或笔重 /
  纯图标按钮（#1「禁图标」不动——图标不进按钮当唯一内容）。

### 9.5 动效注册表（「纸先落、墨后渗」——简报 §5）

v2-1 起注册表改形：全库 keyframes 恰五枚（`paper-drop` 落纸 /
`ink-wash` 渗墨 / `ink-set` 落墨 / `paper-unfold` 展开 / `stamp-press`
盖印，components.css 库尾；screens.css 另有
`editor-zoom-in/out` 编辑台过渡——**v3-2 随编辑台容器化退役**，见
⑩ 容器延展行）——行级动效 = 这五枚原语按消费面组合，**opacity 恒慢于
transform ≈1.3×**（消费面用 `calc(var(--dur-*) * 1.3)` 表达法则）。
v2-2 起增两枚（`paper-fold` 收拢 / `page-turn` 2D 翻页——下两行，
全库七枚）；v3-a 增一枚（`paper-drop-down` 落底——触屏贴底 sheet 的
落纸方向原语，从上方 8px 落下到位，底缘全程不出视口；全库八枚）：
呼吸循环件已随 v2 退役（零常驻循环铁律）。
**fr-B 增三枚（全库十二枚）**：`stagger-rise`（列表逐项错峰——
140ms 淡入 + 4px 上移，步长令牌的载体）/ `scrim-out`（纸雾淡出
to-only，与 scrim-in 对偶——scrim-in 自 v2-2 在库、本刀首次入册）/
`sheet-out`（触屏 sheet 向底滑出——与入场 @starting-style 100%
对偶）。**fr-B 曲线族第三族立档**：`--ease-spring`（弹簧近似——
对 rd-1「唯一 overshoot = 盖印收束」的显式收窄修订，用户任务书
授权；法则全文在 tokens.css 动效节：只许配盖印形 keyframes、幅度
≤4%、禁位移）。**veto-R 增一枚（全库十三枚）**：`paper-retract`
（沓收拢——大容器退场的方向性位移 + 淡化，无缩放；`paper-fold`
的微缩半随之**收窄为小卡专用**——法则句见纪律块）。

| 动效 | 触发 | 时长 × 缓动 | 实现 | reduced-motion 降级 |
|---|---|---|---|---|
| paper-settle 信笺落座 | 门厅封面首绘（页面加载播一次） | `--dur-settle` × `--ease-paper` | `.paper-settle` = paper-drop + ink-wash ×1.3 双动画（旧单 keyframes 已退役，类名沿用，320 封顶） | 总降级块归零 |
| seal-press 印记按落 | 门厅印记入场（首绘一次） | `--dur-ink` × `--ease-paper` | `.seal-press` = ink-wash（同上） | 同上 |
| 信到达（ink-wash 组合） | 新信寄出与到达（`addLine` 的 `opts.enter`；历史回填不播）；词卡开启同法 | `--dur-panel-in` transform × `--ease-paper` + `--dur-ink` opacity | `.flow-enter` = paper-drop + ink-wash 双动画 | 总降级块归零 |
| 墨水物理（ink-set） | 新到信正文字色 `--ink-ghost→--ink` 一次性（T1-3） | `--dur-wet` × `--ease-paper` | `.ink-wet .say` + `@keyframes ink-set` | 直落终态 |
| note-arrive 批注递出 | 新批注组到达（轮询重渲染同 key 静帧，不重演） | `--dur-note`（260ms）× `--ease-enter` transform + ×1.3 ink-wash | `.note-paper--enter` = paper-drop + ink-wash 双动画（rd-1 的单 keyframe 形由 v2 双动画取代，档值 260ms 为 v2 重定——原 240ms 旧档废） | 同上 |
| paper-unfold 纸面展开 | #21 每次展开 | `--dur-note` × `--ease-enter` + ×1.3 ink-wash | `.disclosure-body:not([hidden])` = paper-unfold + ink-wash 双动画（折叠展开 8px 下落，both） | 同上 |
| chevron 旋转 | #21 `--open` 切换 | `--dur-note` × `--ease-paper` | `.disclosure--open .disclosure-marker .inkicon` transform | 同上 |
| 触压下沉 | `:active`（#1 / #17 / #18） | `--dur-micro` × `--ease-press` | `transform: translateY(1px)`（#20 `.section-tab` 无位移——其按压走 state-layer 透明度档） | 同上 |
| 纸面微起 | #2 pen focus | `--dur-note` × `--ease-paper` | `background-color` → `--paper-high` | 同上 |
| hover 加深 | #1 / #15 .word / #17 / #18 / #20 / #21 组头 | `--dur-micro` × `--ease-press` | color / text-decoration-color / border-color | 同上 |
| 焦点环 | `:focus-visible`（button / input / textarea / select） | 无动效 | 现役环（textarea/select 已补齐） | 不适用 |
| state-layer 触感层 | 可交互件 hover / `:focus-visible` / `:active`（.btn 全族 / #17 / #18 / #20 / #21 组头 / `.teach-me` / **`.dock-trigger` 笔搁触发条——v3-a 第七族，同三值同纪律**；输入件豁免——键盘焦点有即时环 + #16 发丝线变色，雾会糊字） | `--dur-micro` × `--ease-press` | `::after` 墨雾叠色（`--state-hover` .08 / `--state-focus` .12 / `--state-press` .12），零布局位移；hover 半区 `@media (hover: hover)` 包裹（触屏只有按压半区） | 总降级块（0.01ms）即达稳态 |
| 信纸落桌（视图切换档） | 案头空间显形（`#space-parlor` 解隐，每次切换落一次） | `--dur-settle` × `--ease-enter` | `#space-parlor:not([hidden]) .flow` = ink-wash（内容层——容器动画会让 fixed 写信区在动画期改挂本节） | 总降级块归零 |
| 案头重落（mc-1 切换档） | 角色切换后的信流重铺（app.js 落类、刷新前先摘——一屏一次纸事件） | `--dur-note` + ×1.3 × `--ease-enter` | `.flow.flow-resettle` = paper-drop + ink-wash | 同上 |
| 邮戳盖下 stamp-press | 信笺寄出一瞬（composer 提交，JS 落类一次，animationend 自摘）；教学卡结课同枚 | `--dur-stamp` × `--ease-press` | `.stamp-press` + `@keyframes stamp-press`（scale .96→1 的 transform 收束——全应用唯一 overshoot 许可，非投影） | 0.01ms 即终，animationend 仍到（JS 清理不失效） |
| 容器延展（v3-2，⑩ 容器延展档；v3-2R 零跳变次序） | 沓下拉容器换形态：扇叠↔全览窗口（8.2.2a 翻看重铸）、扇叠↔编辑面（mc-2 容器化）与扇叠↔写信工作区（v3-2R 起笔重铸）——整个容器向下拉开/收回，非子页面替换；全览窗口升级 = 内容先装满 → 再量高 → 一次拉开（零跳变） | `--dur-settle`（≤320ms 档）× `--ease-paper`，height 一次过渡 | `extendContainer`（components.js：换装前后量高，`--panel-h` custom prop 落差 + `.envsel--grow` 类；prop 缺省 = auto）；reduced-motion 直切 | 直切（REDUCED_MOTION 单一归宿 + 库尾总降级块双面） |
| 抽屉开合 drawer | tabpanel 显隐（温故/抽屉的节切换） | 进 `--dur-space-in` × `--ease-enter` + 60ms 错峰（fr-B 重定——原 280 档升入整屏档）；出 `--dur-panel-out` × `--ease-exit`（**fr-B 接上**：JS 编排 `.panel--leave`——absolute 叠在 .spacebody（relative 锚）之上、纸底 ink-wash reverse 淡出，animationend 对账 + 保险丝后 [hidden]；rd-1 的「容器级退出待接」Revisit 就此关闭，allow-discrete 毒形态永禁） | 进 = `[role="tabpanel"]:not([hidden])` transition（opacity + transform 8px 双轨）+ `@starting-style`；出 = app.js `leaveLayer` 落类 | 总降级块（0.01ms）直切 + JS 半区 REDUCED_MOTION 直切 |
| 逐行落墨 reveal stagger | tabpanel 首次入视（IntersectionObserver 落 `.is-revealed`，回调只加类） | ink-wash 纯淡入 `--dur-1` × `--ease-enter`，步长 40ms、只对前 8 项生效（`--i` 由 JS 落，**总封顶 320ms**；`animation-fill-mode: both` 防先亮一下）——v2 行级改纯淡入（简报 §5「每行 140ms fade」） | `[data-reveal].is-revealed` 子项 + `--i`（components.js `wireReveal`） | 双面：CSS 总降级块 + JS 半区 `matchMedia` 即落定 |
| 回执首渲 @starting-style | 动态插入的回执件（.typing / .sysline / .errline / .busystrip / .resultstrip）首渲 | `--dur-micro` × `--ease-exit` | `@starting-style`（Baseline 2024-08；缺失 = 直接出现，天然渐进增强）。信笺/批注不走此路（JS 门控的双动画保历史回填静帧）；#15 词卡已有组合入场不叠加 | 总降级块归零 |
| 起笔写信工作区（现役——v3-2R 重铸，用户判词否定上一刀降级实现 2026-10-02；veto-R 收拢原语换行） | 「起笔」= 沓容器向下延展成为写信工作界面（compose 面——收件人 + 多行稿纸 + 寄出，全流程在容器内）；寄出后回执一拍 + 容器收拢让位案头信流（收拢方向与延展对称、同曲线反向）；「对话」两条路（沓中/二次点选）仍经 `unfoldToParlor` 收拢让位 | 延展 `--dur-settle`（≤320ms 档）× `--ease-paper`（height 一次过渡）；收拢 `--dur-panel-out`（200）× `--ease-exit` + ink-wash reverse 恒慢；transform/opacity 拆开且 opacity 恒慢 | 延展 = `extendContainer`（同上行）；收拢 = `.envsel--fold` = **`paper-retract`**（veto-R：大容器退场禁整体缩放——方向性位移+淡化）+ `ink-wash` reverse ×1.3；回执一拍（1000ms，reduced-motion 直落）后 `closeEnvelopeSelector`；信流半 = 切角色路径的 `flow-resettle` 同帧在播 | 直落终态 |
| page-turn 翻页（现役——v2-2 落库，用户点名） | 全览窗口翻页（8.2.2a——v3-2 起窗口 = 沓容器升级态）与面板横滑切换 | `--dur-settle` × `--ease-paper` | **2D 翻页感**：位移 + rotateY ≤8° + 梯形 transform（skewY）与边缘卷曲阴影（墨色同源 `color-mix` 渐变）+ `--stack-shadow-soft` 承托；方向由消费面落 `--pt-x/--pt-ry/--pt-sk`（变量驱动）；**禁 3D 书本仿真**（无 preserve-3d——简报 T3 原列「翻页 flipbook」禁令按 T2 邮票豁免先例收窄（**用户点名豁免 2026-10-02**：禁令收窄为「3D 书本仿真」，2D 翻页感不在禁列） | 总降级块直切 |
| 落墨页签（v3-a——⑨-5 新行，ink-wash 静态版；v3-aR 淡墨渍底修订） | #18 空间切换：当前项「落墨」（fill-opacity 0→.15 淡墨渍底）、旧项「墨褪为线」（.15→0）一褪一落同帧，共一屏一纸事件配额（standard 档） | 进入 `--dur-note`（260）× `--ease-paper`；退出 `--dur-panel-out`（200）× `--ease-exit` | `.navdock-item--on .inkicon` fill-opacity 过渡（进入侧 260 落墨 / 退出侧 200 褪墨，双态各持己侧曲线）；标签色重走 `--dur-micro`；零新 keyframes（复用注册原语，纯 fill-opacity 过渡） | 直落终态 |
| 空间转场 cross-fade（fr-B——⑨-5 新行；硬切换清单 ①②③④） | navdock 三空间互切、案头 ↔ 全页纵深（信档/观察/档案）、门厅 → 案头（拆信） | 进 `--dur-space-in`（340）× `--ease-paper`（内容层 transform）+ opacity ×1.3 恒慢；出 `--dur-space-out`（220）× `--ease-exit`——进出同帧起播 = **交叉淡化**；头部件先到位、内容层 60ms 错峰跟进（分层错峰）；navdock 让位节奏不动（落墨页签行自持） | 进 = screens.css `:not([hidden])` 翻转即播：温故/抽屉走 tabpanel transition（上行），全页纵深 `.dossier .spacebody` 走 paper-drop + ink-wash 双动画，案头 `.flow` 纯淡入（fixed 写信区改挂的 rd-1 坑在册）+ `.top` 纯淡入；出 = app.js `showSpace` 落 `.space--leave`（absolute 叠 #stage 上、纸底遮进层、ink-wash reverse、fixed 家具帧即 visibility 藏）——`leaveLayer`/`cancelLeave` 编排 + 保险丝，快进快出安全 | 直落终态（REDUCED_MOTION 单一归宿——进/出/让位三面直切） |
| 确认窗升降（fr-B——⑨-5 新行；弹窗三族 ⑤） | #11 confirmDialog 开/合（忘掉双层、看答案、搁批注切角色、删笔友） | 开 `--dur-dialog-in`（300）× `--ease-paper` + opacity ×1.3；合 `--dur-panel-out`（200）× `--ease-exit`——**Esc 收起与确认收起对称**（同一 finish 编排）；纸雾（--ink 降透明度 0.4，禁毛玻璃）scrim-in/out 同步 | `.cfrm` = paper-drop + ink-wash 升起 / `.cfrm--out` = paper-fold + ink-wash reverse 褪下；`.cfrm-scrim`（z 11）/ `.cfrm`（z 12）全站最上；JS Promise 编排 + animationend 对账 + 480ms 保险丝；Esc capture 闸门只退本层（⑩ 10.4） | 直落终态（REDUCED_MOTION 即 resolve，0.01ms 双面） |
| 词卡褪下（fr-B——⑨-5 新行；弹窗三族 ⑥——「信到达」行的出场半） | #15 词卡关闭三路径（Esc / 收起 / 点卡外·遮罩） | `--dur-panel-out` × `--ease-exit` + opacity ×1.3 reverse；纸雾 scrim-out 同步淡出 | `.word-card--out` = paper-fold + ink-wash reverse（浮卡档）/ sheet-out 向底滑出（触屏档，与入场对偶）；JS 落类 + animationend 对账 + 保险丝摘 DOM；**换卡/互斥路径 opts.skipOut 直摘**（showWordCard/showSpace/开沓/升写作态——残影不跟层走） | 直落终态（REDUCED_MOTION 即摘） |
| 教学卡回应区首渲（fr-B——⑨-5 新行；弹窗三族 ⑦ 的升起半） | 批注卡的回应指路行/输入行/帮助行/搁置行后插（AWAITING_USER 落定或轮询重渲） | `--dur-1`（140）× `--ease-enter`，位移 4px | `.note-paper :is(.guide, .replyrow, .skiprow)` transition + `@starting-style`（渐进增强；卡面静帧时才后插，与 note-arrive 不叠加） | 总降级块归零 |
| 列表逐项错峰 stagger（fr-B——⑨-5 新行；硬切换清单 ⑫） | 搜索结果/目标列表重过滤（familyGroupsBlock 双消费面：温故·档案「可以练的表达」与档案时间线 / 抽屉·隐私「按表达忘掉」） | 单项 `--dur-1`（140）× `--ease-enter`，步长 `--dur-stagger`（**28ms**——20–40 区间取中），前 8 项封顶（总窗 ≈364ms） | `.stagger-in` + `@keyframes stagger-rise`（淡入 + 4px 上移）+ `--i` 由 components.js `restagger` 落（摘类 + 强制重排 + 落类 = 可重触发）；**wireReveal 管首入视、restagger 管重渲染**——两轨不叠 | JS 半区 REDUCED_MOTION 直切 + 总降级块 |
| 墨选开单（fr-B——⑨-5 新行；面板进出场补面） | #27 select-list 开单（`hidden` 解隐） | `--dur-1` × `--ease-enter`，位移 4px 下移到位；**收单即关不动**（选定反馈不延迟——开有迎、合即答） | `.select-list:not([hidden])` transition + `@starting-style` | 总降级块归零 |
| 弹簧微件 flip-tick（fr-B——⑨-5 新行；微交互·开关拨动） | 设置·显示与计量的计量开关拨动（重渲后新钮补一回） | `--dur-stamp`（120）× **`--ease-spring`**（弹簧族唯一现役消费面——法则：盖印形 keyframes、幅度 ≤4%、禁位移） | `.flip-tick` = stamp-press keyframes × spring 曲线（scale .96→1）；JS 落类一次、播完即终 | 直落终态（JS 半区不落类） |
| 旋钮点选反白（fr-B——微交互补面） | #17 chip --on 切换（文风/考试/词表 picker 点选） | `--dur-micro` × `--ease-press` | `.chip` transition 族补 `background-color`（反白不再硬闪；#17 状态矩阵同刀改行） | 总降级块即达稳态 |
| 写作态升落（v3-a——⑨-5 新行，D-B） | 案头笔搁触发条 → `.dock--compose` 全页写作面升起 / 收起（8.2.2⑤）；navdock 让位的 fold 半同帧 | 升 = `--dur-panel-in`（280）× `--ease-paper` + ink-wash ×1.3 恒慢；落 = `--dur-panel-out`（200）× `--ease-exit` + ink-wash reverse；navdock fold = `--dur-panel-out` × `--ease-exit` | 升 = `.dock-compose--in` = paper-drop + ink-wash 双动画；落 = `.dock-compose--out` = paper-fold + ink-wash reverse ×1.3；navdock = `.navdock--fold`（paper-fold，animationend 后 [hidden]）；类由 app.js 落/摘（animationend 对账 + 480ms 保险丝同沓家）；**纸的物理法则收口：升起位移取注册原语 8px（§4 报告写 14px——12px 封顶法则胜，取原语不取越值）** | 直落终态（REDUCED_MOTION 单一归宿——升/落/让位三面全部直切，JS 半区同拍） |

- 纪律：零 JS 动画库、零 WAAPI；全部 CSS transitions/keyframes +
  class 切换；库尾 **reduced-motion 总降级块**是全库统一保险
  （rd-1 起用 **0.01ms 技巧**：`animation/transition-duration:
  0.01ms !important` + 延迟归零 + `iteration-count: 1`——即刻到终态而
  `animationend`/`transitionend` 照发，JS 一次性清理不失效）。
  **reduced-motion 双面纪律（rd-1）**：CSS 媒体查询管不到 WAAPI/JS
  编排——components.js 的 `wireReveal` 自行监听
  `matchMedia('(prefers-reduced-motion: reduce)')`，reduce 即落定
  全部容器并停掉在飞编排。**手感第一律（rd-1）**：一切可交互件的
  可见反馈 ≤100ms（hover/press/state layer 全走 `--dur-micro`）；
  **进入比退出略长**（`--ease-enter`/`--ease-exit` 分离）；触屏纪律：
  hover 效果一律 `@media (hover: hover)` 包裹。**纸事件守恒**：同屏
  最多 1 expressive + 1 standard；一屏一次纸事件。**纸的物理法则**
  （简报 §5）：位移 4–12px 封顶；无弹性回弹（唯一 overshoot = 盖印
  收束）；进入减速长尾/退出加速收势/禁 linear；transform 与 opacity
  拆开且 opacity 恒慢于 transform；纸不发光；阴影不做动画（用垫纸层
  opacity 换）。**双腿退场的摘除对账在最慢腿（用户三轮否决「收起
  不丝滑」的根因修，用户第五轮点名定位）**：双腿退场（纸腿 transform
  200ms + 墨腿 ink-wash reverse ×1.3 = 260ms 恒慢）的摘 DOM/[hidden]
  对账以**墨腿 animationend** 为准——纸腿先终时不得摘（此刻墨尚剩
  约三成，即摘＝半墨硬切，正是三轮否决的卡顿本体）；单腿动画对账
  本腿；对账须 `event.target === 本体`（防子件同名动画冒泡抢账——
  沓内信封 env--born 同用 ink-wash）。现役四点 = 沓收拢
  `.envsel--fold` / 写作面落 `.dock-compose--out` / 确认窗
  `.cfrm--out` / 词卡 `.word-card--out`（空间交叉淡化 `leaveLayer`
  自始即此形）。**大容器退场禁整体缩放（veto-R，用户否决驱动的
  法则句）**：大容器（信封沓等下拉容器级）退场用方向性位移 + 淡化
  （`paper-retract`——沿原路向下收拢回锚位的方向），整体微缩只许
  小卡（词卡/确认窗级）用（`paper-fold`）。**位移量必须可感知
  （用户第三轮否决定形，沓面小刀 cf45c82）**：veto-R 首版 paper-retract
  只有 -8px 微移——全屏级面板上不可感知（用户判词「根本没改」）且
  与「向下收拢」方向相反；现值 **+24px 向下沉落**（200ms 退场曲线 +
  ink-wash reverse 260ms 尾半；触屏贴底 sheet 同向成立——沉出视口
  缘）。24px/200ms 为首版定值、可按用户体感调档；②-5 的「整屏位移
  8px 封顶」是**整屏转场档**的法则，沓收拢属容器面板档、按本条
  24px 定值——两档各自成法。**痕迹随机化**（rd-1）：印记微旋 ±0.5–1° 与位置微偏移
  由 CSS 变量驱动（`--mark-*`，nth-child 离散梯，确定性零 JS 重算）；
  每屏至多一处随机痕迹——现役唯一活点 = 门厅封面邮票角标（mc-1 信封
  沓的 rotate/translateX 是 stamp_key 确定性派生，不入随机计数）。

### 9.6 断点系统（R-1W 重写版：全断点响应式）

四档构图，**媒体查询的边界值即契约**（481 / 900 / 1280，钉在
`tests/host/test_r1w_responsive_redo.py`）：

| 档 | 范围 | 构图原则 | 纸面 / 栏宽 | 边注栏 |
|---|---|---|---|---|
| 手机 | ≤480px | 基线形态（430 壳随视口收窄）；现役移动规则冻结（ux-1 横滑切面板与触摸三修落在此档） | `--shell-w` 430（token 默认） | 缺席 |
| 平板 | 481–899px | 信纸栏放宽 + 同质面板起两栏——不是把 430 拉伸居中，而是每块面板按该档重排 | `--shell-w` 600；门厅封面信笺 560 垂直居中 | 缺席 |
| 桌面 | 900–1279px | 案头舞台：桌布 + 双层发丝镶边纸面 + 阅读栏 + 右缘边注栏 | `--shell-w` 1080；阅读栏 / 门厅封面 640 | 208px |
| 宽屏 | ≥1280px | **延展的是案头与边注，不是行长**：纸面 1240、边注 240；阅读栏仍 640 | `--shell-w` 1240 | 240px |

- 平板档两栏规则（grid，`align-items: start`；跨满栏件 = 筛框与无命中
  句）：`.family-groups`（今日 · 可以练的表达 与 隐私 · 按表达忘掉 的
  家族折叠组，`minmax(260px, 1fr)`——两 JS 工厂同容器类）/
  `.panel-grid`（为什么五面板、记忆五面板、设置两块、今日的到期 +
  在学，`minmax(264px, 1fr)`）。记录页的账表（四字段行）**整幅在前**
  不分栏——需要宽度的表不分栏，同质面板才配对。两栏阈值 544 / 560
  均低于本档内容上限 564（600−2×read-pad）——约 580 / 596px 视口起
  两栏，更窄自然落单栏：两栏是本档内真实挣得到的，不是硬摆的
  （R-1W 处置修正：交付版 280px 阈值 592>564，平板档永不两栏——
  算术钉 test_r1w_responsive_redo 使其可执行）。
- 边注栏内容（案头日期 / 界尺；**装饰邮戳水印已随 v2 撤除**）与
  dock 三项 ≥900 收拢居中不动；`--shell-w` 是 #stage / #18 navdock /
  写信区 .dock 三者的同一宽度出处。
- 交互件逐档：点词卡浮层的视口收进由 JS clamp 承担（各档同面；
  触屏档 = bottom sheet，分档走输入形态查询而非宽度断点，见
  8.2.2③）；写信区软键盘 = viewport
  `interactive-widget=resizes-content`（不支持的引擎忽略该键，无回退
  面）+ 门厅 `100vh → 100dvh` 双声明。
- **旧登记撤销**：「481–899px 保持 430 居中原形」与「≤480 移动形态
  一行不动（对门厅的适用）」自 R-1W 作废（9.8-16/17）；其余页的 ≤480
  基线规则仍冻结。

### 9.6a 滚动条纪律（v3-2S 立，2026-10-02 用户实测驱动）

桌面默认滚动条 15–17px 会直接吃掉窄容器里的卡片右缘（扇叠/全览/
编辑/写信面的实测遮挡）。纪律三件，新刀必守：

1. **全局纸墨细条**：`scrollbar-width: thin` + `::-webkit-scrollbar
   6px`（轨道透明、拇指 `--rule`、悬停 `--ink-faint`）——占位从源头
   缩到 6px，全应用统一（components.css 地基块，唯一定义）。
2. **滚动井加槽**：容器内滚动面（`overflow-y: auto` 族）一律
   `scrollbar-gutter: stable`——滚动条出现/消失内容零跳动。
3. **清单钉防复发**：仓内滚动容器清单由
   `tests/host/test_v32s_scroll_discipline.py` 机检——新增滚动容器
   必须同刀进清单并带 gutter，否则钉红（评审可见的强制登记面）。

> **时点限定**：以下 9.7–9.12 为 rd 时代（2026-09-30 前后）的历史修订
> 登记，是过程记录不是现役断言——其中的语汇（含旧品牌词与旧空间词）、
> 色名与数值以本文件现役节（①–⑧ 与 9.1–9.6）为准；历史归属句保留
> 原文（prep-0 裁决 R1 纪律）。

### 9.7 本刀的 ③ 契约修订登记（显式修订 + 理由）

1. **#1 link-btn**：状态矩阵 +hover/+:active 触压——理由：否决词
   「组件简陋」；纸压感是信笺语言的触感谢。
2. **#2 pen**：+focus 纸面微起——写字区的焦点应答从「无」到「纸亮」。
3. **#3 note-paper**：default 底 `--rule-soft`→`--paper-2` + 左缘界尺
   + 卡头 #22 note 小图 + enter 态——「短笺是一张纸」的纸色差；左缘
   界尺是契约形非描边框（禁止变体措辞同步修订：阴影、四侧描边框、
   弹层）。
4. **#5 sec**：h3 前墨线界尺小饰——手作小标治「白板感」。
5. **#7 resultstrip**：+撕缝虚线——判词条读作从短笺撕下的一行。
6. **#14 state-banner**：empty 配 #22 lamp 小图——否决词「空态纯
   文字」的正面回答（壳上 `.note` 静态行结构有钉，保持纯文字）。
7. **#15 word-card**：`--rule-soft` 底 → `--paper-high` + 发丝边 +
   垫纸错位层；禁止变体措辞「阴影」精确化为「盒影类投影」
   （`box-shadow` 字面不入库——页源负钉常绿；垫纸层是契约形，
   F-1R 零阴影法则不动）——浮层纸影与形态法则两全。
   （rd-1 注记：「零阴影法则不动」已过时——用户 2026-09-30 解除零
   阴影禁令（`DEC-OPI-dc0ba4b6-…13`），词卡垫纸层现承
   `--stack-shadow-soft`；本条其余为 R-1V 历史登记，原文保留。）
8. **#16 / #17 / #18 / #20**：+hover/:active 触压与 transition——同 1。
9. **#21 disclosure**：标记 ▸/▾ 字符 → #22 chevron（`--open` 驱动
   旋转 90°）+ paper-unfold 入场——否决词「图标简陋」；
   aria-expanded / roving / 默认折叠 / 禁手风琴语义零回退（既有钉
   随迁：`tests/host/test_r1r_blueprint_v2.py` 的标记两钉改钉
   chevron 形）。
10. **#18 dock**：宽度 430px → `--shell-w`、≥900px 三项收拢居中——
    桌面构图（否决词「留白过分」的主因）。
11. **新增 #22 icon-set**（⑤ 四步同刀）：③ 表行 + 契约块 +
    `inkIcon()`/`installIcons()` + `COMPONENTS` 元组（21 → 22，三处
    注册钉随迁）。
12. **② token 表扩充 + 本 ⑨ 节**：新 token 全登记（现役八色与字体
    栈逐值不动）；R-1V 起新写尺寸规则一律走标度与间距阶。
13. **#4 letter / #9 meter-row / 摘要行 / #15 入场**：`.say` 行高
    `--lh-letter`（信要呼吸——信笺行与界面行从此不同高）；`.kv b`
    5.5em 对齐（账页科目列）；`.sumline .sumnum` 墨色加重（账页读
    数感，mono 细节）；#15 词卡开启复用 ink-fade（--dur-2，注册表
    首行）。
14. **走查回修四件**（双宽度活体走查发现，同刀修）：①`.teach-me`
    定裁为弱化 pencil 行链接（原 ③ 库外登记「视觉规范刀再裁」
    销账）；②`spokenOf` 对竖线五段探针全键只念首段（⑧ 8.0.2
    「全键不进信流」对探针键同样成立——blocked 行不再漏工程
    键）；③`scrollBottom` 短通信不追底（旧实现把第一封信顶进
    sticky 品牌条背后；长通信追底行为不变）；④空厅整行下移
    `--sp-6` 落座。
15. **`.ob .formhead` 步题界尺小标**（处置刀补登记，评审 F-3——
    钉先落 `test_r1v_visual_craft.py::test_the_small_craft_touches_land`
    而登记缺位）：门厅步题由居中改为 flex 两侧发丝线（线随字伸缩，
    screens.css）；③ 库外 `.teach-me` 行的「铅笔行链接」定裁以
    第 14① 条为准。
    （R-1W 起第 15 条的 `.ob .formhead` 形随门厅重做退役——见 17。）

### 9.8 R-1W 修订登记（全断点响应式 + 门厅完全重做，2026-09-30）

16. **⑨-6 重写为四档断点系统**：单一 900px 断点扩为 481 / 900 / 1280
    四档（手机 / 平板 / 桌面 / 宽屏）。**撤销**旧登记「481–899px 保持
    430 居中原形」；「≤480px 移动形态一行不动」对门厅以外各页仍适用
    （门厅移动形态随 17 重做）；`#stage` 基宽由字面 430 归一为
    `var(--shell-w)`（值等价，出处归一）。平板档新容器类：`.family-
    groups` / `.panel-grid`（屏级布局类，screens.css，非组件不入库——
    与 ⑧ 8.2.9 摘要行同法）。走查改刀：记录页曾试「账｜为什么」硬两栏
    （.ledger-cols），768 实测右列过挤——当刀改为账表整幅 + 为什么五
    面板两栏（同质面板配同质网格），.ledger-cols 不留库。
17. **门厅完全重做（⑧ 8.2.1 修订版）**：三步白板版退役，封面信笺
    落成（案头日期 + stamp 邮票角标 / 印记 / 英文小字 + display 题 /
    称呼 · 缩进正文 · 又及 / 「拆开这封信 →」）。旧定稿钉随迁清单
    （旧串 → 新串，三处同刀）：
    - `test_fg2_entry_and_states.py`：`一 · 这是什么`/`二 · 短笺怎么
      来`/三句步文/`就这么定 →</button>` → 新称呼/两段正文/又及/
      `拆开这封信 →</button>`；`.ob-step {` → `.ob-sheet {`；
      `.ob .brandmark { display: block; … }` → `.ob-mark { display:
      flex; … }`；docstring 同步。
    - `test_f1r_letter_design.py`：`一 · 这是什么` → `致 来到门前
      的人：`；旧封面句（v1 三步版步文）→ R-1W 封面句（该句字面又随
      W-8 再迁一程，见 20）；`就这么定 →</button>` → `拆开这封信
      →</button>`（ONBOARD_KEY / seenOnboard / 无 persona 面 /
      `<title>` 四钉不动）。
    - `test_r1v_visual_craft.py`：`.ob .formhead::before/::after` →
      `.ob-divider {`（封面短界尺分饰）；「唯一媒体查询」计数钉 →
      三边界各恰一次（9.6 边界契约）。
18. **#22 增枚 stamp（邮票角标）**：第八枚，锚位 = 门厅封面案头日期
    行（水印墨装饰，aria-hidden，同行有日期文字）；③ 表 #22 行、
    components.css 契约块「现役八枚」、index.html 模板与头注、
    ⑨-4 现役清单四处同刀；**组件数仍 22**（icon-set 是组件、枚是成员）。
    ⑨-5 注册表增 paper-settle / seal-press 两行（首绘各一次，
    reduced-motion 随库尾总降级块归零——r1v 钉空转检查的循环元组
    同刀扩入两枚）。
19. **R-1W 处置刀（评审 MEDIUM-1 + LOW-1 + 总控活体 F-1 同源合流）**：
    - `.panel-grid` `minmax(280px→264px, 1fr)`——交付版阈值
      2×280+sp-6(32)=592 > 本档内容上限 564，**平板档全档死规则**
      （总控与评审独立活体同证：600/768 单栏、≥900 才两栏）；264 使
      阈值 560 ≤ 564，约 596px 视口起两栏。screens.css 注释 + 9.6
      表格句随迁；**新增算术契约钉**（2×min_col+gap ≤ shell−2×
      read_pad，从 tokens/screens 现读真值）使死规则类缺陷可被
      pytest 拦截。
    - index.html 诊断节「为什么」grouphead 重复行删除（交付时插
      panel-grid 开标签误复制；平板双发丝线行 + ≥900 被占一格）+
      `grouphead 恰一次`负控钉。
    - `.family-groups` 注释边界精化（两栏自约 580px 起，原句
      「481–599 落单栏」在 580–599 段不实——评审 INFO-1）。
    - f1r 旧负控 `✉ 第一步，也是唯一步 not in` 随迁复钉（交付迁移
      退役未登记——评审 INFO-2；fg2 三新负控之外补防回潮面）。
    - 登记补账（c2-a F5 判例）：`test_fg2_entry_and_states.py`
      `test_the_cover_is_a_three_step_letter → test_the_cover_is_a_
      complete_letter` 函数改名（评审 INFO-4）；8.2.1 反引号排版
      修正（INFO-3）。
    - VAL ② 组「十页截图矩阵」由总控多宽度活体亲验闭合（375/768/
      1280/1600 × 门厅/案头/今日/记录 + 计算样式探针——评审 INFO-5
      的核验不能由总控面替补）。

### 9.9 W-8 修订登记（用户思维三修，2026-09-30）

20. **语言立场全面修订（对话语言跟随用户，默认中文）**：用户立场
    「我从没有说过这个应用只能用英语交流」「前端所有显示必须从用户
    角度，使用用户思维思考」；v1 任务书范围更正见
    `DEC-OPI-6759bd35-…11`。四件落地：
    - **语言立场**：prompt 编译在 `[channel]` 之后新增固定可信节
      `[response]`（follow the user——教学表达本身保持英文原文；
      零插值、字节确定）；runtime controller 四处 `language_policy`
      → `follow-user`；phase9 节头绝对基线 16 处随迁（注入防御的
      相对断言不动），phase1/3/4 六文件入钉。
    - **文案五处**（R7 域提案，用户首验否决权保留）：封面定稿段
      「以通信学英语……中文英文都行」/ who-sub「固定笔友 · 中文英文
      都行」/ placeholder「写一句……中文英文都行」/ 空厅句「中文或
      英文都行」/ 8.1.2 原则补句；旧英语限定句全仓退役（唯一登记
      例外 = 作答框「用英语写一句试试……」——教学表达练习面，本刀
      范围外；9.8-17 随迁记录的引用字面同步改指称式）。
    - **markdown 前端兜底**：letterWords 三记号（`**粗**` / `*斜*` /
      `` `码` ``）——正则分段、记号内照旧 span.word 分片外包
      strong/em/code、纯节点拼装、无记号路径与旧输出逐字节同、
      未配对原样直出；.say strong/em/code 纸系样式三行（#4 letter
      契约块内，不新增色与圆角）。
    - **信流尾注退役**：blocked 行（两形）从信流删除——没递短笺的
      一轮在信流里静默；「为什么」的读出归温故 · 记录 why_not 面
      （数据面不动）；③ 库外类清单的对应退役类行同刀清扫（除名）。

### 9.10 rd-2 修订登记（文案洒脱豪放档，2026-09-30）

21. **文案语气升档（洒脱豪放档，R7 域提案 + 用户首验否决权保留）**：
    用户裁定 `DEC-OPI-dc0ba4b6-…13` 之②（「文案越洒脱豪放越好」+ 两锚例
    必采）；调研底稿 = 调研E（`docs/research/2026-09-30-frontend-redesign-
    research.md`：12 手法 / 书信词典 / 语气宪法 / 正反案例）。六件落地：
    - **封面「致明日之我」（锚例一）**：封面信重写为写给明日之自己的信
      ——称呼「致 明日之我：」；两重收信人叙事（与固定笔友的通信 ∥
      写给明日之我的信）；「今日落笔，明日展信」时序意象（现代白话，
      不伪古不堆辞藻）；日期/邮票/英文题/h1/`<title>`/进门钮
      「拆开这封信 →」等视觉与结构锚不动。
    - **placeholder「今日如何？」（锚例二，逐字）**。
    - **who-sub**「一位固定笔友 · 中英不拘」/ **空厅句**「信还没开始写
      ——想从哪句起，就从哪句起。中文英文都行；写错了，客厅接得住。」
      ——placeholder 让位锚例后，语义底线①（中文可写）③（写错被回应）
      由封面段与空厅句承载；②（教学在英文）由封面段「一条英文批注」
      承载；**发送后状态行**「信已寄出，等回信——客厅把灯留着。」
      （8.5 流式落点句随迁）。
    - **导航空间词**：学案 → **温故**、柜抽 → **抽屉**（调研E 提名
      「信匣」经功能核实名不副实——抽屉装记忆/隐私/设置，无信件收藏，
      退「抽屉」；「写信」动作词不动）；§② token 表、③ 组件表三行、
      8.1–8.6 现役句与 ⑨-5 注册表行（柜抽开合 → 抽屉开合）全站同族扫全；
      8.0 逐页剖析（R-1 时代诊断史）与 9.7–9.9 历史登记循 9.8-17 指称式
      先例保留旧名。
    - **批注家族**：teaching moment 定稿词 短笺 → **批注**——卡头
      「批注：{功能句}」/ 指路行「回应写在这张批注上（不是下面的信纸）。」
      /「批注来了——就在下面的信流里。」/「为什么留了这张批注」/
      「批注频率 · 保存批注频率」/ GATE 理由三词（另一张批注还在进行 ·
      批注锁不成立 · 这张批注走不下去；**rd-3 指称更正**：此三词与
      TEACHING_OPEN「留了批注」的唯一切面是诊断面板词面，服务端从未
      有这些中文映射——已随 rd-3 面板退役，见 9.11-22）/
      「没能开始这张批注——」/
      「批注来过才会有账」/「批注痕迹」/ TEACHING_OPEN「留了批注」；
      按钮族：寄出作答 → **寄出回应**、这次跳过 → **先搁着**（busy
      「搁置中……」、回音「先搁着了——回头再拾。」、作答已寄出 →
      「回应已寄出。」、再试一次？ →「再试一回？」、confirm 句
      「看过之后仍可回应」）；判词豪放化（✓ 答得漂亮 / ◐ 答了一半；
      ✗ 没答中与「这次没法判」不动）；kind 映射 CURRENT_USER_ERROR →
      「你信里的句子」（**RESOURCE_PRACTICE「资源练习」是服务端 kind_cn
      镜像，web.py 冻结故保持**）；LIFECYCLE 读法「等你回应」（服务端
      status_cn 词面「等待您回应」在 web.py 冻结——两词面并存为登记事实，
      「您」字与宪法第 6 条的张力移交总控）。**登记例外不动**：作答框
      「用英语写一句试试……」（W-8 已裁，用户未推翻）；「批改中……」
      （批注家族词面自洽保留）。
    - **语气宪法 7 条入册** = 8.4.1 新节（豪放档护栏；与 8.4 冲突处以
      宪法为准）；8.7-1 / 8.7-5 的值面随本刀更新（你信里的句子 /
      回应已寄出 / 先搁着了——回头再拾），8.7 原文不改写。
    - 钉随迁：`test_w8_user_mind.py` 文案钉升级豪放句钉（W-8 中档句入
      缺位清单防回潮）；`test_r1r_blueprint_v2.py` / `test_r1w_responsive_
      redo.py` / `test_fg2_entry_and_states.py` / `test_r1_shell.py` /
      `test_f1r_letter_design.py` / `test_w1_web.py` / `test_p2_memory_
      deletion.py` / `test_p3_goal_management.py` / `test_rd1_craft_
      foundation.py` / `test_r1v_visual_craft.py`（注释指称）随迁；新钉
      `tests/host/test_rd2_copy_bolding.py`（两锚例逐字 + 语义底线三件
      可发现性 + 导航词 + 旧词缺位与豁免 + 批注家族 + emoji 缺位 +
      宪法节 + 登记例外不动）。

### 9.11 rd-3 修订登记（信息架构重构——提案B，2026-09-30）

22. **温故信息架构重构（提案B「今日 + 一行成长」）**：rd-0 定案默认
    确认提案B（`DEC-OPI-dc0ba4b6-…9`）+ 用户令②「大量信息并非用户
    需要看见的……设计了很多功能不代表都要显式表达」；调研底稿 = 调研B
    `docs/research/2026-09-30-frontend-redesign-research.md`（IA 模式
    卡 / 三分判据 / 移走清单 / NN/g 空态判据 / Wrapped 门槛）。五面：
    - **默认层恰两块**（8.2.3 重写）：今天的行动（到期 N + 进行中
      批注 + 一个动词按钮，N=0 邀请态）+ 你的成长（恰 3 条词级结论，
      三档「能做到 / 还在练 / 暂时不能」；空态 = pull-revelation 卡）。
      环块诚实省略——无可靠的连续天数数据源，今日进度与行动块重复，
      宁缺毋凑（调研B：计数是副产品、最多 1 环；两块是合法形态）。
    - **移走清单落地**（用户令核心）：诊断五问与「为什么 · 原值」
      用户面零渲染（**归档读法**——/api/diagnostics 端点与数据面钉
      保留在 API 层，web.py 零 diff，前端调用与渲染整体移除，含
      api.js 的 fetchDiagnostics 与 app.js 的五渲染函数族）；页首
      计数摘要行退役（today-summary）；全量排程（renderSchedule）与
      目标清单（renderGoals）降入「计划明细」折叠，默认层只留计划
      一行「未来 7 天」；内部数值（confidence / priority / readiness
      档位 / 词表代号）不出现在温故**默认层**——词级表达替代
      （能 / 还在练 / 暂时不能）；「计划明细 / 原始读数」折叠内保留
      原值读数（排查档语义，非默认层，见 8.2.5）。
    - **档案节**（8.2.5 重写；显示名 记录→档案，内部 id 与键零改名）：
      搜索 + 聚合时间线（周 / 月桶行一句，点开见明细）+ Wrapped
      期待态（不足 30 条讲期待不讲遗憾）+ 可以练的表达迁入 + 按表达
      看（账表）+ 原始读数深档（观察读数第一次展开才拉）；加载态
      两形（「批注正在来的路上……」进行时 ≠「还没有批注留痕」的
      没有——NN/g）。
    - **零触碰面**：抽屉三节 / 方向节 / web.py / css / 组件库零 diff；
      docs 六 canonical 除本节与 8.2.3、8.2.5 零触碰；8.2.3-8.2.5
      之外的旧节指称（8.0 逐页剖析、8.5、8.6 等）循 9.8-17 指称式
      先例保留旧名，下次触 spec 刀扫全。
    - **R7 域声明**：成长结论句式、邀请句、期待态句、桶行句式为本刀
      拟定——用户首验否决权保留。

### 9.12 rd-4 修订登记（全面面刀——R-2/R-3 前端先行 + 手迹与机制物化，2026-09-30）

23. **伙伴面 + 设置真面 + 手写批注层 + 机制物化首批（rd-4 全面面，
    重设计程序末刀）**：授权 = `DEC-OPI-dc0ba4b6-…9` + rd-4 勘察
    简报（五硬约束 C-1..C-5：web.py 零 diff / 静态白名单 7 文件 /
    组件注册四处同刀 / 零外链零 data URI / 交付 LF）。
    - **伙伴面（R-2 前端先行桩态，8.2.2a）**：#23 partner-card 入库
      （⑤ 四步同刀：③ 表行 + components.css 契约块 + components.js
      工厂 + fg1 的 COMPONENTS 元组与三计数钉）；名册 = persona 域
      内容的前端静态临时副本（真源 `src/elc/persona/types.py`），
      选中只落 localStorage（`elp.partner.pick.v1`）、零生效声称
      （「重启后生效」类计划句现役为假——CLI 无 --character、web 不
      读 localStorage、host 全链 None）；封面「生成人设/人设卡」与
      隐私节「这版做不了——页面不知道伙伴的角色编号」缺位钉保留
      不回潮。
      （**cs-2 后记**：上款桩态已随档案全页视图整体退役——#23 出册、
      名册拆除、/api/partner 真面落成；本条为 rd-4 时代登记原文，
      现役真值见 8.2.2a。）
      （**主线-1 后记**：隐私节自认句随按伙伴关系忘掉接通退役——
      角色编号由名册现读，8.2.7 补缺；「缺位钉保留不回潮」随之解除。）
    - **设置节真面（R-3 前端先行，8.2.8 重写）**：旧两句退役（缺位
      钉随迁 r1_shell/r1r/r1w）；两真句保留 + 三档教学模式参考
      （`docs/PRODUCT_CONTRACT.md` §3）+ 诚实读法句（fail-closed：
      档位由启动命令给定，页面读不到也不改它）+ 换档句 + 批注频率
      指向句；纯静态——SECTION_PULLS 不拉本节（缺位钉保留）。
      （**主线-1 后记**：上款纯静态读法已随设置节接通整体退役——
      `GET /api/settings` 三面真值 + `POST /api/settings/teaching_policy`
      八旋钮白名单写面落成，SECTION_PULLS 拉本节，旧 fail-closed 句
      换「读得到但不能改」现役读法；本条为 rd-4 时代登记原文，现役
      真值见 8.2.8。）
    - **手写批注层（调研D 建议 3：教学 × 物感最强交集）**：主形 =
      红笔圈线（批注卡锚行外包伪元素椭圆，border 2px + rotate
      -2.5deg；静态形零新动效——⑨-5 零新行的理由：border 圆角椭圆
      没有描线路径，逐段画得换 SVG 几何）；副形 = 完成盖戳（#22
      stamp 同枚，stamp-press 复用）；守恒律：一卡至多一处手迹；
      完成 vs 搁置两态可分（成功族 → settled 盖戳；搁置/负值 →
      skipped 淡出——原两臂同落 .skipped 的合并答法退役）。
    - **机制物化首批**：盖戳只挂被验证面（档案明细行 outcome ∈
      {SUCCESS, ALTERNATIVE_SUCCESS} 落 #22 stamp 水印 + 日期沿
      .kv mono；PARTIAL/FAILURE/ABSTAIN 不盖——负控钉）；在途角标
      （`.letter--en-route` 虚发丝角标，回信落地/失败即摘——行为钉；
      typing「笔友把灯留着」不重复造）；归档检索扩展（「搜信里的
      句子」= /api/history 50 轮窗口，口径写在脸上、无时间戳不造
      日期、命中列「第 n 封（你/客厅）」+ 片段；中文 probe = 族名 +
      判词并入检索串——rd-3 INFO-4 收口；跨信重现**不做**）。新增
      符号族 = 0（盖戳/在途/圈线全复用 #22、伪元素几何与既有 token
      ——守恒律核算）。
    - **零开闸面**：web.py 零 diff；无 GET /api/partner、无
      /api/settings——R-2/R-3 的「真读面」全部诚实桩/纯静态；十二
      既有端点零改动；零迁移。
      （**cs-2 后记**：/api/partner 已由 cs-2 按设计新增（档案页唯一
      读面），上款「无 /api/partner」禁令解除；/api/settings 禁令
      保留。）
      （**主线-1 后记**：/api/settings 禁令由主线-1 按设计解除——
      `GET /api/settings` + `POST /api/settings/teaching_policy` 落成
      （读面 + 八旋钮白名单写面）；mode 拒写 = 零开闸边界原样保持，
      换档仍走启动命令。本条为 rd-4 时代登记原文，现役真值见 8.2.8。）
    - **R7 域声明**：名册三位的姓名与一行性格/背景、伙伴占位句、
      选中注记句、关系/近况空态句、设置节三档参考的分寸句、搜信
      提示与无命中句为本刀拟定——用户首验否决权保留。
    - **裁决预告（五件，按位次待用户/后续刀裁）**：① 模式真读面
      端点（页面读到当前档——需要服务端暴露 rollout stage 读面）；
      ② 作答期聊天路由（批注开着时 composer 的信落哪里——本刀已落
      乙案指路行「批注开着——回应写在上面那张；也可以直接写一封
      新信。」，纯表达不改路由）；③ 名册后端缝（--character 注入 +
      选中读面——localStorage 的意思何时真生效；**cs-2 后记**：真源
      与真面已落，此缝随名册退役闭合）；④ 跨信重现数据缝（同一表达
      在几封信里的足迹需要新索引/读面，客户端无表面形——
      **主线-2 后记**：此缝由表达足迹读面闭合——
      `/api/target_footprint` + 按表达看的「足迹」入口，现役真值见
      8.2.5）；⑤ rd-3
      INFO-3 成长条目不可点（点一条成长结论跳到它的批注/痕迹——需
      条目级锚点）。

### 9.13 v3-a 修订登记（前端升级刀——落墨页签 + 信纸全幅写作态，2026-10-03）

> 授权链：DEC-OPI-95287e92-…5（队列与两入口分工预裁、用户首验否决
> 面预留）+ `docs/research/2026-10-02-v3-frontend-upgrade-research.md`
> §4 推荐组合（N-A 落墨页签 + D-B 信纸全幅写作态）。本刀的两处
> **形态级显式修订**与三处**登记行**集中在此，其余随触碰面同刀改行
> （②-5 令牌表 / ③ #2·#18·#22 行 / ⑨-4 名册 / ⑨-5 两新行 /
> ⑩ 10.1·10.3-5·10.3-6·10.4 / 8.2.2⑤+⑤.1）。

1. **#18「禁止变体——图标」条款显式修订**（§4.4 偏离账 #1/#2）：
   navdock 三项升落墨页签——每项 20×20 墨线图标（desk/revisit/drawer，
   同网格同笔重同单色契约）与文字标签**同钮**上下两行；当前态 =
   落墨填充（ink-wash 静态版），下划线语汇从**导航当前态**岗位退役
   （动作链接岗位不动）。修订理由 = P1（图标+标签）/P2（当前态双
   通道）成熟范式 + 落墨隐喻的导航体量升级；**用户首验位** = 三枚
   新图标的意匠与落墨态本身。**首验裁决已行使（2026-10-03，
   DEC-OPI-76a0a10a-…9）**：实墨填充形态被否决（大面积矩形轮廓
   fill-opacity .9 填实 = 黑方块，封口折角/拉手细节淹没）——当前态
   改**淡墨渍底**（fill-opacity .15，墨渗纸面的淡渍语义；进入/退出
   动效与锚位契约不动；spec 注释与字面钉随迁）。
2. **8.2.2「写信区常驻全形」形态修订**（§4.4 偏离账 #4）：改为
   「触发条常驻（44px 笔搁）+ 写作态按需（.dock--compose 近全屏
   新信纸）」——理由 = D1 无法收起是用户点名的第一硬伤，常驻税
   163→104px 级；**用户首验位** = 两入口分工（⑤.1）与写作面形态
   本身，否决即回退。
3. **⑩ 宪法登记行**（非豁免）：写作态 = **全页成员**（10.1——
   案头内的容器态延伸，不新开层型：fixed 全页 + navdock 让位 +
   Esc 收起；z 序表零改动——fixed 全页沿用 dock z 8 的遮挡关系
   已被全页语义覆盖）；Esc 退栈序补写作态一层（10.4——浮层裁决
   之后、容器退栈之前；容器与写作态互斥不可能同拍）。
4. **草稿分桶登记**（§4.4 偏离账 #6，新行为非豁免）：案头桶
   `draft-<character_id>`（无角色落 `draft-local`）——与起笔桶
   `compose-draft-<character_id>` 同构独立 key；隐私面零外发
   （sessionStorage 进程级）。
5. **令牌账定谳**（N5 清账）：`--navdock-h` 语义 = navdock 实高，
   值 54→60（N-A 体量账：签行 44 + 上下距 + 边框 1）；`.navdock`
   上下 padding 从令牌反推——实高恒等于令牌，dock 盖 navdock 顶
   发丝线 3px 的账实差缺陷消亡；`#goal-save` 的 `+3px` 手工补差随
   账实归一退役（ux-1R 的补差理由不复存在）。新增 `--dock-trigger-h`
   与 `--dock-compose-inset` 两令牌（②-5）。
6. **O 清单顺手两项**：O2 沓容器触屏 sheet 贴底越界 8px（§2 移动
   读数）与 O7 滚动到底死区清账（.flow 尾距 = navdock + 安全区 +
   触发条 + 呼吸，手写余量退役）。**O2 活体定谳（本刀实测）**：静止
   态贴底账实精确（sheet bottom 844.000 = 视口 844，overhang 0）；
   报告读数 852 = `paper-drop` 入场中帧取样（+8px 起步让 sheet 连同
   底部垫层在 320ms 内沉到缘下）——报告开的「补 --safe-bottom / 改
   inset 账」在静止态是无效修。落的是报告意图（底部垫层永不被裁）：
   触屏 sheet 入场方向原语换新注册的 `paper-drop-down`（从上方 8px
   落到底缘，⑨-5 名册同刀改行，全库八枚），底缘全程不出视口。
   （同族可循：词卡 bottom sheet 的 @starting-style 入场同形，后刀
   触碰时同法换向。）
7. **报告参数的两处收口**（对研究报告的偏离，随刀披露）：升起
   位移 §4.2 写 14px——**12px 封顶法则胜**，取注册原语 paper-drop
   8px 不取越值；dateline「旧式数字」无令牌载体——mono 微标签配方
   照边注栏同源落地，不发明字位。

### 9.14 fr-A 修订登记（前端修订刀 A——写作态收窄 + 会话窗三件 + 设置页完全体 + 排印体系化 + 墨选，2026-10-05）

> 授权链：用户「前端修订刀 A（五问题）」任务书（分支 frontend-revamp）。
> 五面一刀的**形态级显式修订**与登记行集中在此；逐面实现与钉在
> `tests/host/test_frontend_revamp_a.py`（配既有套件随迁）。

1. **写作态形态修订（问题 1）**：`.dock--compose` 自 v3-a 的近全屏
   （fixed 全高）收窄为**内容自适应高 + 上限 50dvh**——信流上半始终
   可见，写信不遮全部上下文；稿纸 autosize 封顶（`composePenCap` =
   50dvh − 铬件账 148px，下限 4×baseline）后内滚；v3-a 的 520px 降级
   双形态随之退役（基础形态本身已是降级读法）。Esc 收起与笔搁触发条
   语义不变。**用户首验位** = 上限值（50dvh）与收窄方式本身，否决
   即回改。
2. **会话窗三件（问题 2，全新组件 #24/#25/#26）**：一键回底墨点
   （离底 240px 浮现，平滑回底——圆形是用户明示的墨点样式族，
   **②-6 圆角法则的 fr-A 新增豁免**：邮票/邮戳之外第二例圆形，墨点
   不盖真实事件非印章）；轮次刻度（每轮一点、当前视位高亮、点击跳
   转——刻度只管已加载窗口，更早部分以信流顶部「加载更早」衔接，
   口径句写在脸上）；token 计量（数据面全链：OpenAI 兼容响应的标准
   `usage` 字段提取 → ProviderAttempt 三列落库（迁移 0020，三列
   NULLABLE 的 adjudicated 扩列——无该字段的兼容端点如实 NULL 不伪
   造）→ `/api/history` 轮级 usage + 会话累计（窗口无关）→ 案头计量
   条（累计 + 逐轮可选展开）→ 设置页显示开关——**sessionStorage 客
   户端侧**，查过 user_config 现面无 UI 偏好合适面，如实标注）。
3. **设置页完全体（问题 3）**：分组信息架构五区（如实说 / 教学模
   式 / 教学策略 / 隐私与披露 / 显示与计量）；模式读面视觉化（三档
   名映射——PRODUCT_CONTRACT §3 档名与枚举词并写非虚构，当前档高
   亮 `aria-current` 但不可改，`mode` 写入继续 400 拒绝）；披露规则
   **编辑面接通**（§5.1 DisclosurePolicy 写面现成——全规则集版本化
   upsert、409 重读、重复 persona 行与词表外层级 400 人话；规则行可
   改层级可增可减，名册供给当前 persona 的专属规则入口）；「规则经
   profile 编辑，这里只读」句退役（钉随迁）。
4. **排印体系化（问题 4）**：九档标度值不动（简报在册），补**应用
   规范**——`--t-*` 配方九枚 + 四族读法（②-4a）；fr-A 前残留的相对
   行高 `1.7`/`1.8` 字面全数清账（`.errline` `.sub` `pre` `.taxref`
   `.state-banner` 等十处归配方）。**规范：新规则一律 `font:
   var(--t-*)` / `var(--meta-*)` 整体取用，零拼装。**
5. **墨选（问题 5，#27）**：原生 `<select>` 全应用退役——纸面浮层
   下拉（`role=listbox/option`、`aria-activedescendant`、键盘
   ↑↓/Home/End/Enter/Esc/Tab、点外关闭；选中主墨 + 勾记、hover 淡
   墨雾 color-mix 墨色同源）；三现役消费面（方向页技能 / 设置批注
   频率 / 披露层级）。z 序表新增 10 档（10.2 同刀改行）。
6. **令牌账**：`--t-*` 九枚入 tokens.css（②-4a）；`--dock-compose-inset`
   语义不变（桌面档两侧让缘照旧）；会话窗家具 z 5 与计量条 z 4 入
   ⑩ 10.2 表。

---

### 9.15 veto-R 修订登记（全应用文字显示与组件统一规范——用户首验否决五组反馈 + 两新增面，2026-10-04）

> 授权链：用户 dogfood 首验否决五组反馈（DEC-OPI-b2e889bd-…11 裁决
> R1–R9 + 第二轮修订扩权：④扩全应用 + 新增回底钮/刻度两面）+ 任务书
> TASK-…15、判据 VAL-…13。本章两部分：**A 全应用统一规范**（现役法则，
> 逐面排查的判据）+ **B 本刀修订登记**（九面，钉在
> `tests/host/test_veto_response.py` + 既有套件随迁）。

#### A. 全应用文字显示与组件统一规范（现役法则）

**A-0 数据优先原则（文字显示总纲，8.4 的姊妹法则——冲突时本章为准）**：

1. 能直接显示数据的不写说明文字——读数自明的面，文字只留单位与口径，
   用最短词（「共 45,678」优于「本段通信 token 共计 45,678 个」）。
2. 空态一句话（8.4 第 3 条的模板句即本条的实例）；多句空态收成一句。
3. 解释性散文只在解释**影响操作决策**的事实时出现（换档的分寸句、
   不可逆的后果句）；「这是什么」的导语至多一行，不写第二句。
4. 面向用户的词面一律中文——枚举词有中文读法的显中文（存值枚举词
   不变，原词进 `title` 或原始读数区备查）；机器 id（persona_id 等）
   不作曲面显示词，名册供给人名，名册缺席时原值直出（诚实的最后
   手段，不是常态）。

**A-1 十表面族统一模板**（每族一段：族内同面必同形；「不同即修」是
逐面排查的判据，排查清单随每刀回执入册）：

1. **门厅**（cover）：居中纸面 + 印记 + 一句副题 + 唯一门钮；无导语、
   无节块——封面只有进入一个动作。
2. **案头**（#space-parlor）：品牌条（`.top`：印记 + 端点驱动角色名，
   不增长按钮元）+ 信流（轮 = 用户信/回信 + 可选批注卡；口径行
   `.flow-calibre` 一行居中弱墨）+ 写作区（dock：触发条/写作面两态）
   + navdock 三项。案头家具（刻度/回底钮/计量粒）全部「有事才现身」。
3. **温故 / 抽屉**（tabpanel 族）：**每 tabpanel = 一行导语
   （.doc-line）+ 若干 .sec 节块（h3 节题 + .doc-line 正文 + 控件 +
   空态 .note）**；节内不再有第二层导语；panel-grid 两栏只许「两块
   并列同权」的今日节用，表单/设置节一律单栏纵列。
4. **信封沓四脸**（扇叠/全览/编辑/写信工作区）：同一容器的四形态
   （⑩ 容器延展档），共一套头排印与关闭语义（Esc 逐层退栈）；大容器
   退场 = 方向性位移+淡化（禁整体缩放）。
5. **词卡**（#15）：浮层家族——顶纸 + 发丝缘 + 软纸影；Esc/点外/
   收起三路关闭；小卡退场可 paper-fold（微缩许小件）。
6. **教学卡**（note-paper）：信内卡——判词文字自足，零徽章零判分戳；
   回应区后插走 @starting-style。
7. **确认窗**（#11）：纸雾 + 自绘窗，两次确认各说一件事；Esc 只退
   本层；全站最上（z 12）。
8. **全页纵深**（笔友档案/信档/观察）：整页自持 + 返回钮唯一回途 +
   `spacebody` 节块同 3 的 sec 模板；排查材料（观察）零图表零彩色。
9. **浮层家族**（墨选单/词卡/教学卡/确认窗/计量明细）：统一关闭
   语义（Esc 逐层退栈 + 点外关 + ⑩ 互斥收——开新层收旧层）；统一
   纸面语汇（--paper-high + 发丝缘 + --stack-shadow-soft）。
10. **按钮族**：纸底墨字（--paper-high/--ink）+ 发丝线或无边框 +
    触感层三值；主动作 btn--ink、铅笔动作 btn--pencil、弱化 btn--faint；
    一屏一个主墨钮；图标永不单独表意（#22 锚位契约——字标或
    aria-label 同在）。

#### B. 本刀修订登记（九面）

1. **教学模式可改（面①，唯一 src 深改）**：迁移 0022 `app_setting`
   泛用键值表（本刀只落 `rollout_stage` 一键；**W-1-0 世界设置复用
   同表，其迁移号顺延 0023**）；`POST /api/settings/mode` 四词白名单
   → 持久化 + `dataclasses.replace` 换活 wiring（下一轮即新档）；
   open_host 读序 = 显式 CLI 参数 > 持久词 > None（fail-closed 不变）；
   gate 函数零改；8.2.8 重做（墨选四档 + 分寸句 + 「由启动命令给定
   不能改」句退役）。
2. **教学策略七钮档位化（面②）**：自由文本框退役，`KNOB_TIERS`
   display-layer 词表（存值 verbatim，null=未配置保留）；badge 改
   「暂不影响行为」。
3. **词面中文化（面③，A-0 第 4 条的落地）**：频率四词显 中文档名
   （关/偶尔/适度/勤快）；披露层级墨选去英文后缀（中文 only）；
   模式四档中文名；chip 有中文读法时中文 only（原词移 title）；
   机器 id 不作曲面显示词（名册人名优先维持）。
4. **抽屉三页统一（面④实例）**：记忆页导语/节内文 `.sub`→
   `.doc-line`；设置页 panel-grid 取消归一；隐私页已合规（模板
   出处）。全应用扩展面 = 本章 A-1 十族。
5. **数据优先排查（面⑤，A-0 落地清单见本刀回执）**：计量条改粒、
   信流口径行收尾、观察摘要行收短、信档口径句收短、设置显示句收短、
   记忆页导语收短。
6. **token 计量粒（面⑥）**：sticky 独立层退役（用户否决常驻遮挡）；
   dock 上沿内嵌粒（主数据直出）+ `.tm-pop` 明细浮层（浮层家族形态，
   z 10）；无读数不现位；设置开关保留（sessionStorage 语义不变）。
7. **沓收拢动画（面⑦）**：`paper-retract` 新原语（方向性位移+淡化，
   无缩放）；`paper-fold` 收窄为小卡专用；法则句「大容器退场禁整体
   缩放，方向性位移+淡化」入 ⑨-5 纪律块。
8. **回底钮重设计（面⑧，第二轮新增）**：圆形墨点退役（用户否决），
   纸底+发丝线+墨线图标+「回到底」字标；②-6 圆角豁免退役（豁免集合
   回到「仅邮票/邮戳圆形」，v22r 计数钉随迁）；显隐语义与平滑滚动、
   reduced-motion 全保留。
9. **刻度一一对应（面⑨，第二轮新增）**：刻度点 ↔ flowTurns 轮锚
   一一绑定（数量钉）；高亮按真实锚点位置计算（视位线 = 顶栏之下
   一档呼吸，rAF 节流的被动 listener）；点击精确滚到该轮锚点（等价
   对齐含顶栏让位）；「加载更早」50 轮一档口径句保留（同刀核一致性）。
10. **沓收拢定值与滚底臂退役（第三轮否决，cf45c82）**：⑦面的
   `paper-retract` 定值 **+24px 向下沉落**（veto-R 首版 -8px 不可
   感知且方向反——用户判词「根本没改」；定值句入 ⑨-5 纪律块）；
   **滚底自动升级全沓退役**（v3-2R 曾以「触屏主入口」名义落的
   scroll 监听——用户否决「滚到底自动跳转展开全沓非常不合理」）：
   翻开全沓入口全显式化（点沓本体纸面 + 触屏「翻开全沓 ↓」链），
   回扇叠 scrollTop 归零保留为回沓首阅读位；两处负控钉在库
   （scroll 监听不得再现 / 24px 方向距离钉）。

---

## ⑩ 层级宪法（v3-2 立，2026-10-02）

> 地位：本节是全站**层**（layer）的类型学、叠放序（z 序）、互斥规则
> 与统一关闭语义的唯一出处。立刀缘由 = 新鲜眼睛体验报告的「开得越多
> 越乱，控制毫无章法」（P1 叠开矩阵）；用户两项核心误读纠正（起笔/
> 编辑 = 整个容器的变化；翻看 = 下拉窗口的完全升级）由本节定谳的
> 「下拉容器」类型承载。结构与 z 值属工程事实（本节与实现对账），
> 交互语义属 R7 域——用户有首验否决权。

### 10.1 层类型学（四类）

| 类型 | 现役成员 | 特征 |
|---|---|---|
| **内联件** | 教学批注卡（#3）、词底纹提示（8.2.2④） | 信流内、随文档流滚动，**不是浮层**——不占层位、无遮罩、无独立关闭 |
| **浮层** | #15 词卡（浮卡档 + sheet 档 + 遮罩） | 单一、贴点/贴底、遮罩只此一家 |
| **下拉容器** | 信封沓（.envsel）及其全部形态：扇叠 deck / 全览窗口 window / 编辑面 editor / 写信工作区 compose（v3-2R 第四形态；含触屏档 bottom sheet 形态 + 遮罩） | 一个容器、多个**形态**——形态切换 = 容器本体的延展过渡（见 10.4），**零子页面、零新增页面级滚动条** |
| **全页** | 笔友档案 / 信档 / 原始读数（`#space-partner` / `#space-letters` / `#space-obs`）+ 三空间与门厅 + **案头写作态（`.dock--compose`，v3-a——案头内的容器态延伸，不新开层型：fixed 全页 + navdock 让位 + Esc 收起，8.2.2⑤）** | 文档流整页；导航条让位，返回钮与 Esc 是回途 |

### 10.2 z 序表（现值实测后固化；改动须同刀改本表）

| 层 | z | 成员 |
|---|---|---|
| 全页文档流 | 常规流（sticky 顶栏 5） | 各 `#space-*` section；`.top` z 5（veto-R：`#tokenmeter` 的 sticky z 4 随独立层退役——计量粒内嵌 `.dock` 上沿，随 dock z 8） |
| 会话窗家具（fr-A） | 5 | `#flow-bottom`（回底钮）/ `#flow-ruler`（轮次刻度）——信流之上、常驻 dock 之下，与 `.top` 同值不冲突（区域不交） |
| 常驻 dock | 6 | #18 navdock |
| 下拉容器（桌面档） | 7 | `.envsel`（扇叠/全览/编辑三形态同层——形态不换层） |
| 写信区垫板 | 8 | `.dock`（fixed 底，与浮层遮罩同值——DOM 序在后者胜；veto-R 计量粒挂其上沿随本层） |
| 遮罩 | 8 | `.word-scrim` / `.envsel-scrim`（触屏档 display） |
| 浮层卡 | 9 | `.word-card`；**触屏档的下拉容器升 9**（bottom sheet 盖过写信区垫板，`.envsel` 在 hover:none 半区改 z 9） |
| 墨选浮层（fr-A） | 10 | `.select-list`（#27 的下拉纸面——盖过浮层卡与一切表单上下文；点外关闭由工厂接线）；`.tm-pop`（veto-R 计量明细浮层——同档同读法：Esc/点外/⑩ 互斥收） |
| 确认窗纸雾（fr-B） | 11 | `.cfrm-scrim`（#11 的背景纸雾——--ink 降透明度 0.4，禁毛玻璃） |
| 确认窗（fr-B） | 12 | `.cfrm`（#11 自绘确认窗——全站最上层：一切进行中的层（沓/写作态/浮层）都在它之下等答；Esc capture 闸门保证只退本层，见 10.4） |

（沓内信封自身的 --env-z 是容器**内部**排布序，不入本表。）

### 10.3 互斥规则

1. **同屏至多一个浮层**：showWordCard 开新卡先收旧卡（既有语义）。
2. **开下拉容器自动关浮层**：openEnvelopeSelector 先 closeWordCard。
3. **进任何空间收一切浮层与下拉**：showSpace 先收词卡与沓容器（换
   空间的人不被上一空间的层跟着走）；全页由此天然无层。
4. **点外关闭**只属浮层与下拉容器的遮罩面（浮层 = 点卡外；容器 =
   桌面点容器外 / 触屏点遮罩）；内联件与全页不占点外语义。
5. **开下拉容器时常驻 dock 静置**（v3-2R 硬伤 A 定谳 + 处置刀扩面）：
   沓开时 navdock 各项落 `disabled`——淡化置灰且**明确不可点**（既有
   disabled 形态复用：opacity .4 + pointer-events 无），收沓即解；
   **案头写信区（.dock）同步让路**（`.dock--stilled`：opacity .4 +
   pointer-events none + 聚焦抬起退场）——它的「寄出」浮在容器之上
   （z8 > 容器 z7），不置灰则误触 = 容器关闭 + 草稿无声丢弃（复测
   坏1 实测）；新建表单的「存」按钮同样被它咬住（复测差4）。
   **v3-a 扩面**：置灰覆盖笔搁触发条与写作态全体（同件同批）；且
   **置灰优先**——开沓先收写作态（保稿，openEnvelopeSelector 同批
   closeComposeFace），触发条在置灰态不可点（openComposeFace 的
   stilled 守卫是 CSS pointer-events 之外的第二道机械闸）。
   硬约束 = **视觉可点性与实际可点性必须一致**（沓开时底坞「可见
   但已死」的实测缺陷即此律的违反）；二选一取「置灰」不取「第一
   击直切空间并收沓」，理由：沓是带遮罩的模态层（本条之 4 的点外
   关闭），一个手势只该产一个效果——「收沓」与「切空间」压在同
   一击上是双击歧义。
6. **起笔草稿层**（v3-2R 处置刀，复测坏2/坏3 定谳）：写信面的一切
   退出路径（Esc 退层 / 「← 回沓」/「先搁着」/ 点外收拢）**一律
   保稿**——草稿按角色分桶（`compose-draft-<character_id>`，
   sessionStorage），重开起笔自动恢复；**唯一清稿时机 = 寄出成功**。
   「写了一半的东西不能丢」是写信面的第一安全律。
   **v3-a 同构独立桶**：案头笔搁/写作态草稿按同一安全律运行，桶键
   `draft-<character_id>`（无角色 id 落 `draft-local`）——与起笔桶
   **同构但独立 key**（两入口各自的稿互不覆写，寄出各清各桶）。

### 10.4 统一关闭语义（Esc 逐层退栈）

Esc 永远只退**一层**，从最上层起：**确认窗答 false**（fr-B——z 12
最上层；capture 闸门 + stopPropagation，下层的词卡/沓/写作态同拍
不惊动）→ 浮层关浮层 → 写作态收起（v3-a——
浮层裁决之后、容器退栈之前的一层；容器与写作态互斥，二者不可能同拍）
→ 下拉容器退一层
（编辑面 → 扇叠；全览窗口 → 扇叠；写信工作区 → 扇叠；扇叠 → 收沓）
→ 全页回其入口（笔友档案/信档 → 案头；原始读数 → 温故 · 档案，
与各自返回钮同效）。
浮层在场时容器的 Esc 让路（wordCardOpen 裁决）——同一拍只退一层。
reduced-motion 下退栈直切（0.01ms 即终 + JS 直切双面）。
「点外关闭」见 10.3 之 4；零「关一层顺手关三层」的级联。

### 10.5 容器延展档（下拉容器的形态过渡）

沓容器的形态切换（扇叠↔全览↔编辑↔写信工作区）= **容器本体的向下
拉开/收回**：`extendContainer`（components.js）换装前后量高，height
差经 `--panel-h` custom prop 走一次 transition（`--dur-settle` 大件
档 × `--ease-paper`，prop 缺省 = auto）；动画期 `overflow: hidden`
（纸的拉开感，内容随容器展开呈现）。**零跳变次序**（v3-2R 定谳，
上一刀 F-1 缺口「长到一半→跳到全高」的根因修复）：凡内容的异步
灌入改变容器高度的形态（现役 = 全览窗口），一律**内容先装满 → 再
量高 → 一次拉开**——量高永不在异步内容填入前发生；写信工作区 =
内容同步建好后同档延展，起笔延展落定后笔尖聚焦（视口跟随）。
**禁**：子页面替换（v2-2 的 envsel-browser 子页面层模式即此，已除
名）、形态切换引入新的页面级滚动条（v2-2 的独立全页编辑台双滚动
条，已除名）。触屏档的 sheet 形态同档——升级/延展 = sheet 自身
长高。

### 10.6 登记（v3-2 四查留档，Revisit = v3-3）

**P1-2「词卡全端不可达」四查结论：事件链完整，不构成缺陷；根因 =
词表覆盖率 × miss 静默契约的体验叠加**。活体取证（真浏览器双档，
基线 953843b）：`.word` 分片在（一封信 57 片）、`#messages` click
委托在（app.js 委派 + wordFromCaret 兜底）、真实鼠标点词开卡
（桌面浮卡档 + 390px 档）、真实触屏（hasTouch 上下文）点词开卡
（bottom sheet 档 + 遮罩）——全链无断点。**但**一封真实回信的
36 个去重词仅 1 个命中词表（/api/word 实测），命中失败按 ③ #15
契约**静默**——用户点任何词几乎必遇无声无息，读感即「全端不可达」。
**不硬修**：miss 提示是 ③ #15「miss 按契约静默」的契约变更（R7 域，
需用户首验）+ 词表覆盖是内容侧工程，均超本刀白名单——登记 v3-3
裁量（方向：miss 的一次性轻提示 / 词表扩容后的复测）。

**v3-d 收口（2026-10-03）**：v3-3 组合落地（8.2.2③-a）——本条登记
的四查根因两面俱除：覆盖率 14.5% → 89.7%（离线小词典 + 缩写映射 +
撇号归一），miss 静默升级为 miss 无样式（命中位图随信下发 +
`.word--off` 供性分层）——「可点的词必有卡」成立；本条的「miss 按
契约静默」引文自 v3-d 起为历史引文（现役契约见 ③ #15 行）。
