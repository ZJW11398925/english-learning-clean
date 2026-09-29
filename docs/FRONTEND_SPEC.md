# FRONTEND_SPEC — 前端架构与规范（F-G1）

状态：**非 canonical**（经 `DEC-OPI-631452f9-…37` 授权设立的工程规范文档）。
服从对象：`docs/` 六 canonical 文档与用户裁决；本文件的 R7 域（命名法、组
件契约措辞、规范条款）由执行者拟定、用户首验否决。适用对象：`src/elc/webui/`
（本仓唯一前端面）及其一切后续改动。

## ① 地位与治理

1. 本文件**不是 canonical**：与六 canonical 冲突时，六 canonical 胜；
   与用户裁决冲突时，用户裁决胜。
2. 前端改动的**唯一合法路径**：先查本文件 → 复用库中已有组件 → 确无
   可复用才允许新增；新增/修改组件必须在**同一刀**内完成 spec 登记
   （本文件 ③ 追加条目 + 任务书四查写明）。**库中已有组件的重复实现
   = 评审 finding（拒收事由）。**
3. 每次触碰本文件的刀，须在处置/交付记录中列明 spec 变更条目。

## ② Token 语义表（唯一出处：`webui/tokens.css`）

| token | 值 | 用途 | 禁忌 |
|---|---|---|---|
| `--bg` | `#fbf9f4` | 纸底（html/body/顶栏/dock） | 不作文字色 |
| `--ink` | `#1b1a17` | 主墨：正文、primary 动作、resultstrip.miss | — |
| `--ink-soft` | `#5c574e` | 次级墨：说明行、meter、busy、resultstrip.part | 不作大面积正文 |
| `--ink-faint` | `#726a5e` | 弱化：系统行、空态、占位、跳过链接 | 不作正文 |
| `--rule` | `#ded7c9` | 发丝线（顶栏/dock/组框） | 不作文字色 |
| `--rule-soft` | `#ebe5d8` | 弱发丝线（稿纸横线/分区线/note-paper 底） | — |
| `--pencil` | `#a8562f` | 赭红铅笔：**次级链接、焦点圈、错误行、resultstrip.ok** | **只用于次级链接与强调小面，不用于大面积底色** |
| `--touch` | `#f0e9dc` | 用户回执撕边衬底 | 只用于 .letter.me .paper |
| `--f-serif` | Georgia,… | 标题、信笺、primary 动作 | — |
| `--f-sans` | system-ui,… | 小字界面词（说明/系统行/标签） | — |
| `--f-mono` | ui-monospace,… | 仪表行读数 | — |
| `--read-pad` | `18px` | 阅读左右留白 | — |
| `--safe-bottom` | `env(safe-area-inset-bottom, 0px)` | dock 底安全区 | — |
| `--navdock-h` | `54px` | 常驻 dock（#18）高度：body 底 padding 与写信区让位的同一来源 | 不作行高 |

规则：组件样式只许 `var()` 引用，**禁止在任何其他文件重写令牌字面值**；
禁止新增 token 之外的十六进制颜色（零青绿——旧双色主题不得回流）。

## ③ 组件契约（唯一出处：`webui/components.css` + `webui/components.js`）

每组件在 components.css 有契约注释块（结构/状态矩阵/使用规则/禁止变体）。
页面引用一律走新变体类；旧类名仅作为别名保留在同一规则的选择器表尾。

| # | 组件 | 类名（新） | 别名（现役旧名） | 状态矩阵 | 出处 |
|---|---|---|---|---|---|
| 1 | link-btn | `.btn` + `.btn--ink` `--send` `--pencil` `--set` `--faint` `--dot` `--back` `--meter` | `.ob .go` `.send` `.linklike` `.setlink` `.skiplink` `.refresh` `.back` `.meter` | default / `:active`（各变体自带）/ `[disabled]`（opacity .4 + 无 pointer）/ busy（文案切换由 JS 承担） | components.css + components.js（helpButton/skip/寄出作答） |
| 2 | pen | `.pen` | — | default / placeholder / Enter 绑定（app.js） | components.css |
| 3 | note-paper | `.note-paper`（+ `.skipped`） | — | default / skipped / busy（JS 置 disabled+busystrip） | components.css + components.js（showMoments/addReplyControls） |
| 4 | letter | `.letter` `.may` `.me` `.paper` `.say` | — | plain（may）/ torn（me） | components.css + components.js（addLine） |
| 5 | hairline-section | `.sec` | — | default（无交互态） | components.css |
| 6 | setlink-block | `.setlinks` `.setblock` | — | default / [hidden] 切换 | components.css |
| 7 | resultstrip | `.resultstrip.ok` `.part` `.miss` | — | ok / part / miss | components.css + components.js（showResultStrip） |
| 8 | busystrip | `.busystrip` | — | 出现即 busy、消失即复位 | components.css + components.js（setReplyBusy） |
| 9 | meter-row | `.kv` `.kvgroup` `.kvtitle` | — | default（无交互态） | components.css + components.js（diagLine/diagGroup） |
| 10 | empty-state | `.note` | — | default（无交互态） | components.css + components.js（diagEmpty） |
| 11 | confirm-dialog | 无 CSS（原生 confirm） | — | native 确定/取消两臂 | components.js（`confirmDialog()`，全页唯一 confirm 调用点） |
| 12 | system-line | `.sysline` | — | default（无交互态） | components.css + components.js（addLine system 臂） |
| 13 | brand-mark | `.brandmark`（+ `--sm` `--lg`） | — | default 30px / 尺寸修饰 --sm 20px、--lg 64px / reduced-motion 不适用（静态标记，无动效——契约注明） | index.html（`<template id="brand-mark-source">` 内联 SVG，几何唯一出处）+ components.css + components.js（`brandMark()`/`installBrandMarks()`） |
| 14 | state-banner | `.state-banner`（+ `--loading` `--empty` `--error`） | — | loading（取信中…，尾点呼吸微动）/ empty（弱化诚实句）/ error（赭红人话句 + `--pencil` 重试链接，回调由调用方注入）/ reduced-motion（loading 呼吸降级为静态） | components.css + components.js（`stateBanner()`；`diagEmpty`/`diagError` 一律委托它） |
| 15 | word-card | `.word-card`（+ `.wc-lemma` `.wc-pos` `.wc-forms` `.wc-zh` `.wc-en` `.wc-example` `.word`） | — | default（rule-soft 底浮层）/ closed（点卡外或「收起」；DOM 移除语义，同 #11 的两臂不在 CSS）；无 busy——命中即显，miss 按契约静默 | components.css + components.js（`wordCard()`/`showWordCard()`/`closeWordCard()`；触发面 = `letterWords()` 的 `.word` 分片 + `wordWindows()` 窗口查询，app.js 委派） |
| 16 | field | `.field`（+ `.fieldname`） | — | default（下发丝线）/ `:focus-within`（发丝线与名转赭红）/ 控件 `[disabled]`（opacity .4 + 无 pointer） | components.css + components.js（`fieldRow()`，p-3；label 包裹控件，点名牌即聚焦） |
| 17 | chip | `.chip`（+ `--on` `--badge`） | — | off（default，发丝线描边）/ on（`--on`，主墨反白）/ `[disabled]`（opacity .4）/ `--badge`（只读徽标，非交互） | components.css + components.js（`chip()`，p-3；考试/语域/教学频率词表 picker + modality 徽标） |
| 18 | dock | `.navdock`（+ `.navdock-item` `--on`；类名与写信区屏级类 `.dock` 异名共存） | — | default（次级墨、透明点线占位）/ `--on`（当前空间：主墨加重 + 赭红实线短下划 + `aria-current`）/ `[disabled]`（opacity .4） | components.css + components.js（`wireNavdock()`/`markNavdock()`，R-1；常驻底部三项 客厅/学案/柜抽，门厅整条让位；z 6 低于点词卡 z 9） |
| 19 | space-header | `.space-header`（+ 节名槽 `.spacehead-sec`；与屏级基形 `.top` 合用） | — | default（发丝线夹持 sticky 顶栏，随 `.top`）；无交互态——静态头部，reduced-motion 不适用（契约注明） | components.css + components.js（`sectionLabel()`，R-1；学案/柜抽头部 = `.top` 基形 + 本类；客厅头部用 `.top` 原形；品牌条不再增长链接） |
| 20 | section-tabs | `.section-tabs` / `.section-tab`（+ `--on`） | — | unselected（default，透明点线占位）/ selected（`--on`，主墨加重 + 赭红实线短下划 + `aria-selected`）/ focus（地基 `:focus-visible` 赭红焦点环，不另设）/ `[disabled]`（opacity .4） | components.css + components.js（`wireSectionTabs()`/`markSectionTabs()`，R-1；roving tabindex + 左右箭头循环移选；学案/柜抽各一排三项，切节即拉） |

库外现役类（登记，不扩库）：`.teach-me`（裸 button 元素复位直用，无独立
样式；p-1 起今日屏两块与目标清单共用同一行工厂；Revisit = 视觉规范刀再
裁）；`.replyrow` / `.replytext`（note-paper 的
内置回复面，随 #3 契约）；`.formhead` `.sub` `.hint` `.who` `.who-sub`
`.typing` `.errline` `.blockedline` `.grouphead`（屏级文字形态，
screens.css；`.grouphead` 是 R-1 进步节的分组小标）；`.today`
`.todaybody` `.topactions` `.goalbody` `.setbody`（**R-1 退役**：五屏
屏级布局类，随空间模型让位 `.spacebody`）。
（F-G2 移出：`.diagerror`——面板失败态改走 #14，该类无现役用户，规则已删。）
**R-1 现役面收窄**：#6 setlink-block（`.setlinks`/`.setblock`）与 #1 的
`--set`/`--meter` 变体的**页面现役用户清零**（五屏的就地展开与品牌条
链接被空间模型接替）——组件与变体**留库**（活注册表不是死档），契约块
已改行注明；再启用须走 ⑤ 四步。
#10 empty-state（`.note`）的现役面收窄为**壳上静态占位行**（index.html 的
「暂无数据 / 无降级记录 / 设置面尚未到来」首绘）；运行时面板的空态一律
走 #14 的 empty 变体。

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
（收窄、别名退场、变体易主）也随触碰它的那刀改行，不让表说谎。

1. 组件样式的**唯一物理出处**是 `components.css`：同一组件类名（含别名）
   的样式规则在全 webui 目录**恰出现一次**；`screens.css`、`index.html`、
   JS 内联样式不得重复定义（钉：`test_fg1_architecture.py` 单出处组；
   brand-mark 的 SVG **几何**是唯一例外——出处是 index.html 的模板，
   其样式仍只在 components.css）。
2. 新前端需求**先查本 spec**：已有组件直接复用；确需变体时扩展现组件的
   修饰符，不另起炉灶。
3. 新增/修改组件：任务书四查写明 + 本文件 ③ 表同刀登记。
4. 重复实现 = 评审 finding（拒收事由）。

## ⑥ 状态完备性硬门

见 ③ 末条。评审按表逐组件核对；「只有 default 态的交互组件」是 finding。

## ⑦ 架构说明

```
src/elc/webui/
  index.html        页面骨架（R-1 起三空间 + 门厅：#space-parlor /
                    #space-study（三节）/ #space-drawer（三节）+
                    #screen-onboard 门厅 + #navdock 常驻导航；
                    <link>×3 + <script type="module"> + brand-mark 的
                    <template> 几何出处）
  tokens.css        VS1 token 唯一出处（R-1 增 --navdock-h）
  components.css    组件库唯一样式源（20 组件 + 元素复位地基）
  screens.css       屏级布局 + 壳层（html/body/#stage/dock=写信区/flow/
                    spacebody/屏级文字；R-1 起三空间 + 门厅）
  api.js            端点 fetch 封装（页面唯一 fetch 调用点）
  components.js     组件工厂 + 教学卡当场行为 + 点词卡 + 壳导航接线
                    （textContent-only；唯一 confirm 封装点）
  app.js            装配：空间与节切换/事件/轮询/学习与诊断渲染（面板
                    三态走 #14；进空间落默认节，切节即拉）
```

- **ES modules、零构建**：浏览器直 import 相对路径（`./api.js`），无打包
  器、无 importmap、`type="module"` 天然延迟绑定（与拆分前页尾内联脚本
  同语义）。`dependencies = []` 不变。
- **零外链**：无 CDN、无站外字体、无任何 http(s) 资源与 `@import`。
- **静态服务**：`elc/web.py` 按 `_STATIC_TYPES` 允许表**逐请求**读盘；
  允许表即路径校验（表外名字不触盘，404 人话）；文件缺失/不可读 →
  404 + 人话 JSON（fail-closed，永不 500 裸栈）。
- **行为等价注记**：教学回应的拒收臂（原 status 臂与 accepted 臂）合并
  为单 `!accepted` 臂——服务端一切实形（200 拒收 / 400 / 500）都带
  `error` 句，渲染结果逐形相等；两臂回退词统一为「提交失败，请重试」。

---

## ⑧ 设计蓝图（R 程序 · DEC-OPI-5d2d6cef-…15 · 2026-09-29 用户裁决「深入重构·先结构后细节·前瞻性」）

> **地位**：本节是 R 程序（页面深构）的结构权威。③ 组件契约与 ② token 不变；
> 本节规定**空间模型、导航、屏内信息架构、交互模式与前瞻预留**——R-1..R-4
> 每刀的任务书以本节为基准。结构本身属 R7 域：**用户对蓝图有首验否决权**
> （F-1R 教训前置——先过目再动刀）。
>
> **落位注记**（R-1，2026-09-29）：8.1/8.2 已兑现——门厅 + 三空间
>（`#space-parlor`/`#space-study`/`#space-drawer`）+ 常驻 dock 三项 +
> 学案/柜抽节签；五屏归位映射完成（今日→学案·今日、目标→学案·目标、
> 仪表拆→学案·进步〔证据/为什么/观察〕+ 柜抽·记忆/隐私；设置节 =
> 诚实空态占位，R-3 铺面）；十二端点全部复用、零 API 改动；#18/#19/#20
> 同刀入库（⑤）。8.4 伙伴条与 8.5 设置面**未动**（R-2/R-3 的位）。

### 8.1 空间模型（产品隐喻一致）

| 空间 | 隐喻 | 频次 | 内容 | 既有端点（全部复用） |
|---|---|---|---|---|
| **门厅**（开张） | 进门的玄关 | 仅首访 | 三步开张（localStorage 门不变） | — |
| **客厅 Parlor** | 对话的客厅 | 每日主场 | 信笺流 + 教学短笺 + 点词卡 + 写作区 + **伙伴身份条**（8.4） | history/turn/teaching\*/word |
| **学案 Study** | 书桌 | 每日常顾 | 三节：**今日**（到期复习/最近在学/想练）· **目标**（目标·权重·考试·语域·频率）· **进步**（证据面板 + 诊断五 Why + 观察读数） | diagnostics/learning/targets/teach_me/goals\*/observations |
| **柜抽 Drawer** | 收纳抽屉 | 低频 | 三节：**记忆**（五面板）· **隐私**（三 scope 删除）· **设置**（8.5） | memory/delete + R-3 新增 |

- **迁移映射（纯重组零语义丢失）**：开张→门厅；客厅→客厅；今日→学案·今日；
  目标→学案·目标；仪表拆分→学案·进步（学习证据+诊断）+ 柜抽·记忆/隐私。
  十二既有端点全部复用；组件库延续（预计新增 #18 dock / #19 space-header /
  #20 section-tabs，四步入库）。

### 8.2 导航模型

- **常驻 dock 三项**：客厅 / 学案 / 柜抽（底栏 ≤5 规则满足；thumb 可达；
  `--safe-bottom` 已有；**教学卡与键盘永不遮挡**——dock 高度计入流布局，
  教学浮层 z 序高于 dock）。品牌条不再增长链接（今日/目标/仪表链接退役）。
- **空间内二级导航**：学案与柜抽各三节，用 section-tabs（#20）横排切换；
  进入空间即拉当前节，切节即拉对应面板（面板三态走 #14 state-banner）。
- **返回行为统一**：空间间由 dock 承担（无返回钮）；门厅→客厅保留原门钮。
  键序与视觉序一致；焦点环 `--pencil` 不移除（skill 导航/可达性规则）。
- **屏标识**：每空间头部 = space-header（#19）：brand-mark --sm + 空间名 +
  当前节名；客厅头部额外承载伙伴身份条（8.4）。

### 8.3 屏内信息架构

- **客厅**：space-header（伙伴条）→ 信笺流（.letter，撕边/普通两种）→
  教学短笺浮层（W 系全部行为不变：~1s 出现/作答/跳过/刷新恢复）→
  点词卡浮层（#15 不变）→ 写作区（横线稿纸，Enter 寄出）。
- **学案·今日**：三块保留（到期复习含内联教我这个 / 最近在学 / 想练一把），
  诚实空态不变。
- **学案·目标**：p-3 全部读写面保留（组合/权重/考试/语域/频率/taxonomy
  参考/版本前移诚实文案）；编辑器形态随 tab 宽度重排，交互零改动。
- **学案·进步**：学习三面板 + 诊断五 Why + 观察读数（含 FP 清单）合并一节，
  面板分组标题化（证据 / 为什么 / 观察），各自三态不变。
- **柜抽·记忆 / 柜抽·隐私**：p-2 全部保留（五面板/三 scope/双 confirm/
  不可逆声明），仅迁入节容器。

### 8.4 伙伴面（R-2 = p-4 A 裁决落位）

- **伙伴身份条**（客厅 space-header 内）：现役 `character_package=None` ⇒
  诚实占位「无名笔友」（不伪装人设）；有角色 ⇒ 名字 + 一句身份。
- **伙伴卡**（点身份条展开）：identity/personality/background/speech style
  等 CharacterPackage 字段诚实展示（textContent-only）。
- **预设名册**：1–3 个内置角色（sample Maya + R-2 拟 1–2 个新角色，文案 R7
  域=执行者拟定+用户首验）；选中载体 V1 = **localStorage + 「重启 web 后生效」
  诚实注记**（开张门同先例）；服务端 durable 存储/热切换登记 Revisit
  （须 runtime 刀补裁）。

### 8.5 设置节（R-3）

- **模式面**：当前 rollout stage 诚实读面 + PC §3 三模式语义说明（读面起步；
  **写路径 Revisit**——rollout_stage 是 fail-closed CLI 面）。
- **端点信息**：base-url/model 只读展示（不回显密钥）；「换端点须重启并带
  参数」人话指引。
- **前瞻预留**（结构预留不预建）：流式回复（composer 渐进渲染位）、历史
  浏览（客厅「往昔回顾」入口位——/api/history 已服务 50 轮）、多伙伴/多对话
  （空间模型不排斥；伙伴条是 per-conversation 真相）。canonical §18 排除项
  （三端/语音/云同步）**不设计**。

### 8.6 视觉与交互模式（定谳与登记）

- **视觉语言定谳**：信笺 token 全保留（F-1R 用户已验收）；skill 检索
  验证暖棕+米色方向（literary journal editorial 系）；不换风格、不加卡片
  阴影体系；新组件一律从既有 token 派生。
- **交互模式注册表**（既有模式升格为全应用规范）：读改模式（读→改→存，
  版本前移+CONFLICT 重读）、教学时刻模式（短笺+作答+跳过+刷新恢复）、
  破坏性模式（双 confirm+不可逆声明）、三态模式（loading/empty/error+重试）、
  浮层模式（点词卡/伙伴卡同族：点外即收、textContent-only）。
- **skill 使用纪律**（用户授权「灵活利用」）：采纳前验证适配本产品与平台；
  不适配结果明确弃用并留痕（首次「教育→儿童玩趣」查询已弃）。
