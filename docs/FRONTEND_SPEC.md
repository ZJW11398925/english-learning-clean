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

库外现役类（登记，不扩库）：`.teach-me`（裸 button 元素复位直用，无独立
样式；Revisit = 视觉规范刀再裁）；`.replyrow` / `.replytext`（note-paper 的
内置回复面，随 #3 契约）；`.formhead` `.sub` `.hint` `.who` `.who-sub`
`.typing` `.errline` `.blockedline` `.diagerror`（屏级文字形态，screens.css）。

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

## ⑤ 库唯一出处条款

1. 组件样式的**唯一物理出处**是 `components.css`：同一组件类名（含别名）
   的样式规则在全 webui 目录**恰出现一次**；`screens.css`、`index.html`、
   JS 内联样式不得重复定义（钉：`test_fg1_architecture.py` 单出处组）。
2. 新前端需求**先查本 spec**：已有组件直接复用；确需变体时扩展现组件的
   修饰符，不另起炉灶。
3. 新增/修改组件：任务书四查写明 + 本文件 ③ 表同刀登记。
4. 重复实现 = 评审 finding（拒收事由）。

## ⑥ 状态完备性硬门

见 ③ 末条。评审按表逐组件核对；「只有 default 态的交互组件」是 finding。

## ⑦ 架构说明

```
src/elc/webui/
  index.html        页面骨架（三屏 + <link>×3 + <script type="module">）
  tokens.css        VS1 token 唯一出处
  components.css    组件库唯一样式源（12 组件 + 元素复位地基）
  screens.css       三屏布局 + 壳层（html/body/#stage/dock/flow/屏级文字）
  api.js            端点 fetch 封装（页面唯一 fetch 调用点）
  components.js     组件工厂 + 教学卡当场行为（textContent-only；唯一 confirm 封装点）
  app.js            装配：三屏切换/事件/轮询/学习与诊断渲染
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
