# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 基准纪律（用户明令，2026-10-11——任何计划从同一套设计修改完善，不是一套又一套新东西）

**任何计划必须从同一套设计/方案里修改完善，而不是另起新计划。** 发现问题的正确姿势是「在开发方案 xx 位置定义并规划了如何处理该问题——不够全面就完善该方案」，不是现场编一套新的。这是整个项目的基准，后续所有总控必须遵守。

**执行含义**：
1. **先查方案**：察觉问题后，第一件事是查总设计（living-world-spec / cognition-and-narrative-quality / IMPLEMENTATION_PLAN）有没有定义该问题的处理面——有则引用其位置并完善，没有则**补写进方案**（修改完善同一套设计），然后按补后的方案开工。
2. **禁止另起炉灶**：不得绕过总设计现场编新计划。任何刀的开工裁决必须引用总设计的具体章节作为依据；若总设计没有该面，开工裁决的第一条裁决必须是「把该面补写进总设计的 xx 章节」。
3. **总设计的修改也是交付**：补写总设计本身是刀的一部分（docs/ 改动与 src/ 改动同刀提交），不是「先写代码再补文档」。
4. **总控失职判例**：C 程序七刀（C1-a..C4）全部围绕「世界自转」深化，没有一刀问「用户在世界里的面」——正典 §3.2 写了「角色是世界内的演员」但用户从未被列为演员，总控读了两份正典全文七刀裁决都没停下来问。这是设计理解的失败：把「世界是第一公民」读成了「世界是唯一公民」。教训：**每刀开工前问「这一刀的用户面是什么」**。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` 最新收口 DEC（最新收口 DEC 的 id 见下方「当前状态」块的「最新收口 DEC」行；完整 DEC 链见「会话交接索引」） → ④`git log --oneline -5` → ⑤按下一动读文档（见「当前状态」块的「下一动」行——读数/迁移/现役面以「当前状态」块为单一事实源，本段不另抄）。

## 🔧 AGENTS.md 维护规范（2026-10-13 重构后立——总控必守）

本文件是**活文档**，其腐坏史（交接块堆叠/读数多处漂移/索引重复占位）促成了本规范。

1. **单一事实源**：最新读数（pytest/mypy/迁移号/GLOBAL_CONTENT_TABLES 员数/tip/rev）与「下一动」**只写在「当前状态」块一处**；其它一切节（dmcp 段/交接块/索引）**不抄数字与下一动**，只写「见当前状态」。
2. **交接块即归档**：换总控时，新交接块写入即把**上一个交接块整体移到** `docs/sessions/session-handoffs-archive.md`（压缩条目 + git 指针），主文**只留当前这一个**交接块。收口块不留主文——每刀收口只入 DEC/REGISTER + git 历史 + 索引一行。
3. **索引每会话一行、只留指针**：会话交接索引每会话一行（日期 + 刀序 + DEC 族区间 + 归档指针），**删除重复/空占位行**（历史曾有 7 行重复的「第二十七会话·wr-7 主链留档」）。
4. **现役面与历史面分离**：主文 = 基准纪律 / dmcp 段 / 本规范 / 当前状态 / 当前交接块 / 索引 / 工作流协议 / 派单协议 / 工程事实红线 / 常用命令 / AOCI。历史交付明细（Phase 4-10、D 程序、各刀交付哈希）归归档，「当前状态」只留当前程序（Narrative V3）的现役面 + 一行指向归档。
5. **防坑区只留现役通用教训**：具体某刀的留痕归该刀 DEC/REGISTER，不堆主文；防坑区在「当前状态」块下，最新在最上。
6. **改动后必跑**：`tests/world/test_aoci_drift.py`（drift 钉族盯 aoci.code.txt 与代码面；本文件是活文档不在钉面，但改动后跑一遍确认无连带）。

## 🔴 当前状态（2026-10-14——单一事实源：读数/迁移/下一动以本块为准）

- **rev 847（V3-8i 全链毕——VR `VR-OPI-f55cd8c7-…23` PASS 盖于 `6ca5995`、收口 DEC `…24` rev 847、design_sync REBUILD+CHECK = SYNCED〔844 对象〕；产品战略 DEC `…13`〔三级阶梯/三仓〕仍为本仓方向）**；master tip 以 `git log --oneline -1` 复核为准（本收口时点链 = 至 V3-8h 收口 `df1ea8f` + V3-8i 合同增量 `29c2c95` + 交付 `f951b6b` + 台账吸收 `6ca5995` + 本收口台账提交；push 视代理通断）。
- **Narrative V3 程序：V3-1 + V3-2（含 V3-2R）+ V3-3（含 V3-3R）+ V3-4（含 V3-4R）+ V3-5 + V3-5R + V3-6 + V3-6R + V3-7 + V3-8a..V3-8h + V3-8i（门的生产面+玩家角色锚定+无门兜底）全部 COMPLETE**。读数 **6330/0/0**；迁移 **0037/37**（V3-7 两表；V3-8a..V3-8i 全部零迁移）；mypy **205** 文件；GLOBAL_CONTENT_TABLES **23 员**；drift **22 钉**。**产品阶段裁定（DEC `OPI-f55cd8c7…13`）**：三级阶梯 1→2→3、三个全新仓库严格顺序（前仓建成后开后仓）、每级独立可发布（异名、异前端）、引擎随迁不重写——本仓将以终末交接块归档。
- **下一动 = 请用户重启 8760（Ctrl+C 旧进程 → `python -m elc web --app-db ./app.db`）重跑亲验**（每个新计划章有门问玩家〔2–4 选项+自由输入〕、玩家角色不再被代演、既有 ch02 旧计划场走地板 4 段即停；双门之二——**切仓前最后验证**）；**亲验过后**：一级发布就绪差距审计（从未做过）→ 终末交接块（阶梯裁定+资产清单）→ 议切一级产品新仓。**外审明令不变：双门通过前不切主 UI、不退役 Legacy V2**。
- **最新收口 DEC**：`DEC-OPI-f55cd8c7-4423-4a4c-8f62-7f238a2b760c.11`（V3-8h 收口，rev 842；产品战略 `…13` rev 843）。各刀盖章态：V3-7 = 交付 `c263192`/处置 `b4a1c4b`/VR `…12`/收口 `…14`；V3-8a = `04c5d8f`/`10b4489`/VR `…8`/收口 `…10`；V3-8b = `73f6fd7`/`2863ed8`/VR `…21`/收口 `…24`；V3-8c = 开工 `…5`/TASK `…7`/VAL `…9`/交付 `e68dcb5`（+散文扫尾 `9be8453`）/处置 `b63fcbb`/台账 `7cae9aa`/VR `…13`/收口 `…17`；V3-8d = 开工 `…19`/TASK `…21`/VAL `…23`/交付 `0013593`（+补钉 `4adba5d`）/处置 `cccae95`/台账 `439fadc`/VR `…25`/收口 `…29`；V3-8e = 开工 `…31`（rev 826）/TASK `…33`（rev 827）/VAL `…35`（rev 828）/交付 `c465b54`（+补钉 `bc31aa8`）/处置 `23afd74`/台账 `fc2589c`/VR `…37`（PASS）/收口 `…4`（族 `OPI-b8dc176c`，rev 829）；V3-8f = 开工 `…10`（rev 830）/TASK `…12`（rev 831）/VAL `…14`（rev 832）/交付 `4c75be6`+`ddd6027`（第六面授权 = 追补 `…16`，rev 833）/处置 `110b130`/VR `…18`（PASS）/收口 `…20`（rev 834，族 `OPI-c0f4d9b4`）；V3-8g = 开工 `…22`（rev 835）/TASK `…24`（rev 836）/VAL `…26`（rev 837）/交付 `2d75a6e`/处置 `feab75d`/VR `…28`（PASS）/收口 `…30`（rev 838）；V3-8h = 开工 `…32`（rev 839）/TASK `…34`（rev 840）/VAL `…36`（rev 841）/交付 `860ab31`+`7d0c658`/VR `VR-OPI-f55cd8c7-…9`（PASS，盖于 `7d0c658`；…5/…7 两投 INCONCLUSIVE 为 metric 名不匹配形态教训）/收口 `DEC-OPI-f55cd8c7-…11`（rev 842）+ 产品战略 DEC `…13`（rev 843）；V3-8i = 开工 `OPI-f55cd8c7…17`（rev 844）/TASK `…19`（rev 845）/VAL `…21`（rev 846）/交付 `f951b6b`+台账吸收 `6ca5995`/VR `…23`（PASS，盖于 `6ca5995`）/收口 `…24`（rev 847）。更早各刀（V3-1..V3-6R 与 Phase 4-10/D 程序）的交付明细见 `docs/sessions/session-handoffs-archive.md` 与 git 历史。
- **现役窗口回归册（跨刀义务）**：reader 渲染 ack 面（V3-8e 已兑现——页面 ack 驱动 `record_exposure`）/ record_exposure race-free 形态（多连接才开；V3-8e §7.1 脱队读被接受，多连接部署刀重评）/ chapter_activated 读时推导维持现形 / 散文扫尾候选（time.py 现在时句、narrative/types.py/store.py 同族、deletion/types.py docstring 与 RETAINED_TABLES 不符、settlement.py:1206「registered later cuts」触及时精化〔V3-8c 评审判仍真〕）/ F2（claim 同值幂等第二道）/ F4（AST 纪律钉维护须知）/ V3-8c F5（llm_providers AST 钉绕过须知——结构性论据优先）/ streaming 扩展点 `complete_streaming`（按需重开）/ V3-8d F3（viewer 过滤分工：V3-7 隔离钉承重）/ V3-8d F4（④负控面后刀可选）/ V3-8d F5（变异操作随日志留档——后续刀纪律）/ V3-8e F8（gold lore_refs 前向式修复——无生产路径）/ V3-8e F9（真实重规划阵地后 replay 比对面——真实 rollout 开放 SCENE 时裁）/ P1 传闻失真维持后置 / V3-8f 登记：replan 采纳面是否前置校验参与者身份（library face）/ 显示名→id 确定性归一（启发式风险）/ planner 上下文词表（追补裁决 revisit 条件）/ smoke2 观察 d2 participants 不含玩家角色（初始 plan 即如此、散文正常呈现——非缺陷）/ `wait=` 计数文本钉刚性（未来他路由加 wait 会误红——维护须知）/ `app_copy*.db` 读取须 mode=ro（WAL 未 checkpoint）/ V3-8g 登记：门卡选项保持英文（Gold 作者脚本——随章间/作者层刀或另裁）/ 驱动律已改「驱动循环三真停点」（V3-8h 兑现——本项已了）/ F4 语言钮静态类态 nit（首帧 JS 修正；可选） / F5 JS 行为 harness 可选入仓（评审 Node 桩 28/28）/ V3-8h 登记（评审 F1–F5 全 nit）：F1 无方向 prompt golden 字面钉（可选）/ F2 `_press_on` `_current_scene is None` 防御分支答面少报落段（现形不可达；下次触 narrative_web 刀顺手改带收获报告形——二级表达面刀优先）/ F3 state note docstring 收窄（同 F2 时机）/ F4 上限计数仅段写后检查边界记录 / F5 direction 带空白透传无害 / VR 形态：criterion 引擎按 metric 名配对（判据 `pytest_failures`）——报错名即 INCONCLUSIVE / resolver replan_scope 非 CHAPTER ⇒ plan_revision 留 1 = 正典裁量非缺陷（观察在册）/ V3-8i 登记（评审 F1–F5）：F1 `_press_on` `scene_run_start` 死参——真行为=submit 同场续跑地板宽松一段（接线或删参后刀；commit message 假句以 REGISTER v1.7.17 为准）/ F2 真驱证据书签中态 11/0/false 以评审复数 18/18 为准 / F3 脚本场末门后长尾可触地板句（后刀把豁免扩「脚本还有未走拍」）/ F4 Planner·Resolver 臂逐字节等义钉仅负断言（可选补齐）/ F5 replan 两臂（CHAPTER 落位/SCENE 臂）门生产不接入——仅 prompt+地板承担（revisit 在册）。
- **执行者遗留处理先例**（已发生多次：P3-1A/P3-2/P4-4/V3-5/V3-6R/V3-7/V3-8a/V3-8b——API 余额中断或 600s 静默中断留半成品）：开工前必查 git status——不干净时先取证（树状态/新钉跑绿/静态门/全量/禁改面/残标/逐面核合同点），按「吸收+复核」（总控代提交并留痕）或「拒收重交」二选一，绝不静默覆盖。
- **防坑区**（跨会话生效，最新在最上；现役通用教训，各刀具体留痕归该刀 DEC/REGISTER）：㊵**仓外工作区治理（2026-10-13 立——用户点名 D 盘被历刀 scratch 堆乱）**：代理的一切仓外产物只许放**单一根 `D:\elc-scratch\<刀号>\`**；刀一收口即清该根（仅留证据文件，并在收口条目/报告列出创建-保留-删除清单）；**测试夹具一律入仓**（测试文件禁 D:\ 绝对路径引用）；D:\ 根不许再落新物；历史遗留 **258 项/9.02GB**（`_*` 前缀族与 `v35r..v38e` 评审/变异 scratch）已一次性收治入回收站。㊴**钉的证明力须经变异验证（防「空转断言」）**：断言必须落在真正经过被测面的执行臂上——V3-8e F2 先例（重开栈钉的「零重生成」断言恒真〔点击落 gate_open 臂、不经前缀〕；补强为「重开→提交驱动前缀」后 M-B 变异由绿转红）；评审变异组应含「回退修复/替换重生成」型以验证钉自身有齿。㊳**执行者 600s 静默中断是常态型**（第四十二会话三刀全遭）——处置链同「执行者遗留处理先例」；评审的机械证据面（`_tx` 重构经「INSERT 表达式逐字节全同」证实行为保持）是吸收完整性的强证；评审应加测相邻面变异（V3-8b 评审自加 M15–M19）；**裁决 id 前瞻写入更正先例**——开工裁决 DEC id 由服务端在 decision_add 时分配，前瞻写入合同增量的裁决 id 须以铸时实际返回为准（V3-8a 实测：预判 `…16` 实得 `…2`，经 67afdc0 更正；不 amend 纪律⑱——更正用新提交）。㊲执行者 API 余额中断两型（首发即拒/重试后 600s 静默——后者半成品落地）。㊱迁移刀搬迁面含「历史归属句前的断言字面」——grep 全仓 `MIGRATION_IDS[-N]`/`applied[-N]` 负索引钉。㉟执行者长刀中断半成品处置链（取证→裁→吸收留痕）。㉞处置钉也要先过 ruff 再报绿（处置后四门完整重跑）。㉝sed 的 unicode 转义在 Git Bash 不可靠——改仓内文件一律 Edit 工具。㉜评审员仓外变异副本必须含仓根 *.md。㉚dmcp 工具参数形态以服务侧错误面为准迭代（自由文本 ref 一律 OBJECT_NOT_FOUND；V3 刀先例链 = decision_add→task_build→validation_define 同铸→validation_submit〔evidence_refs 留空、读数入 measurements〕；每次 mutation 前必刷基——decision_add 后 CST 即变，REVISION_CONFLICT 错误面可直接取新 id）。㉙编码探测别信 iconv（Git Bash 常无此命令）——判编码用 `od -c` 读字节或 Read 工具。㉘包升版刀扫尾必须含「散文层」（现在时为假的散文句一次扫全；数字戳记名归一到戳记无关耐久形）。㉗跨版本迭代的 CAS 必须锚定「行身份」而不只 state 计数（ABA——V3-2R 先例）。㉖新决定改变公共签名 ⇒ VAL 路径集同刻覆盖全部调用点。㉕钉的「名与字面」两分（数字戳记名随迁归耐久形；历史标识名可保留）。㉔错误词表 docstring⇔代码映射互相可证。㉓改 canonical 文档会伤「文档行号钉」族（文档增删行后须 grep 行号钉随迁）。㉒管道会吞 pytest 退出码（查实须「重定向到仓外文件 + 读 EXIT= 尾行」）。㉑前端负控钉按形态不按裸串。⑳密集小刀期工作树并发（add 按文件）。⑲通道违规记录两更正。⑯台账 tag 非全局唯一。⑰取证区分文件字节与终端渲染。⑱不 amend、改错追加。⑮「byte for byte the pre-X」句族有扫全钉。⑪验收探测先记分支/git worktree。⑫通道违规记录标哈希类型。⑬never_says 一致性含语义族。⑭中文译写术语仓内自证词义。

## 🔴 终末换总控交接块（2026-10-13——第四十四会话；下会话从这里接）

- **用户明令（原话）**：「本对话上下文太长，我要换一个新总控对话，请你确保可以凭DMCP等接续项目，并维持后续AOCI-CODE的合理利用。新总控务必先完全理解整个设计再布置执行任务」。
- **接续就绪三件**：①DMCP（见「当前状态」块——rev/对象数以其为准，`design_status` 复核；本交接时点 rev 841、V3-8h 三件已铸、执行者已被用户停止〔待重派，见「在途事实」〕）；②代码/文档 tip（见「当前状态」块——本时点 `08517d7` 已 push、本地=远端 0 ahead；新总控 `git log --oneline -5` 复核）；③本块即交接件。
- **本对话全貌（第四十四会话：亲验驱动的三刀——V3-8f/V3-8g 全链毕、V3-8h 在途；全部「用户亲验反馈→查方案→完善方案→开刀」闭环）**：**V3-8f（真实模型可用性）**——用户亲验实败（原话「完全无法正常使用，连流程都跑不通」）四症取证（egress 30s 超时 < 真实 43–72s／四臂 prompt 未写值类型⇒`bad-shape`／失败码压平 `transport-error`／V3 写路由 60s 等待截断长驱动）→ 四修复 + 身份合同两面（resolver 渲染形／planner 身份四要点追补 `…16`）→ 真实模型冒烟两轮（smoke2 全链至 next_chapter）；**V3-8g（阅读面体验与连续性）**——三条反馈（太慢无进度／选项点击无响应感〔实机取证实为忙碌静默，点击其实已成功提交〕／正文纯英文）+ 实机新发现续段近逐字复述（同度量 0.95823；空白归一 1.0）→ 连续律 prompt 合同／进度可见与忙碌反馈（spinner+秒表+阶段句+绝不静默）／正文语言可切（`v3_prose_language` 默认 en 可切 zh；已写段不改写），真实验证 0.95823→0.03827、zh 新段非 ASCII 0.9844、既有段 sha 零改写；**V3-8h（核心循环补完，在途）**——停点律（一次驱动跑到真门／章内计划尽／段数上限〔有故之停+说明句〕）+ 章间作者层（下一章 direction 作软期望注入 Director 计划）。另：executor-pro 一次余额中断（五文件半成品→总控取证吸收→flash 承接完成）与 executor-flash 一次 heredoc（无文件落地）训诫级留痕；D 盘治理（防坑㊵ 立）。读数/迁移/员数以「当前状态」块为准。
- **⚠️ 在途事实（改实况 2026-10-14：V3-8h 已全链毕，待办移至「用户世界级亲验」）**：~~V3-8h 待重派~~——第四十五会话已按任务书要点重派 executor-pro 并全链收口（交付 `860ab31`+`7d0c658`；四门双路 6314/0/0 + drift 22；独立评审 ACCEPT-WITH-FINDINGS〔F1–F5 全 nit 登记〕；VR `VR-OPI-f55cd8c7-…9` PASS；收口 `…11` rev 842；sync SYNCED 840 对象；详情 REGISTER v1.7.14/v1.7.15 与索引第四十五会话行）。**同会话铸产品战略 DEC `DEC-OPI-f55cd8c7-…13`（rev 843）：三级阶梯 1→2→3、三新仓严格顺序、每级独立可发布异名异前端、引擎随迁不重写、V3-8h 收完再议切仓。** 接续第一动 = **请用户重启 8760**（Ctrl+C 旧进程 → `python -m elc web --app-db ./app.db`）世界级亲验（一次点击跑到真停点 + 章间方向输入；双门之二——切仓前最后验证）；亲验过后：一级发布就绪差距审计 → 终末交接块（阶梯裁定全文+资产清单）→ 议切一级产品新仓。
- **本对话 DEC 链（新总控必读，design_get 逐读）**：`OPI-c0f4d9b4` 族——V3-8f = `…10`（开工 rev 830，含四症取证全文）/`…12`（TASK）/`…14`（VAL）/`…16`（追补：planner 身份面同刀修 rev 833）/`…18`（VR PASS）/`…20`（收口 rev 834）；V3-8g = `…22`（开工 rev 835，含体验三件与实机取证）/`…24`（TASK）/`…26`（VAL）/`…28`（VR PASS）/`…30`（收口 rev 838）；V3-8h = `…32`（开工 rev 839，含两面范围与四查）/`…34`（TASK rev 840）/`…36`（VAL rev 841）（交付/VR/收口待办）。更早链（`OPI-cddb517c` 族 V3-8c/d/e〔其收口为新族 `OPI-b8dc176c…4`〕、`OPI-06b954e0` 族 V3-8a/8b、`OPI-d274a7fb` 族 V3-7、`OPI-dc1bafdf` 族 V3-5R/6/6R、`OPI-be7b094f` 族 V3-4/4R/5、`OPI-bab4da9f` 族 V3-0R..3R）见「会话交接索引」与归档。**纪律提示㉚（本会话教训）**：`decision_add` 的 `expected` 必须顶层——本会话四次把它误嵌进 `decision` 被服务侧拒（无副作用）；决策 id 一律以铸时返回为准。
- **下一动**：见「当前状态」块（单一事实源）。
- **AOCI 接续指引**：台账 `aoci.code.txt` 随刀维护——第四十四会话已入册：V3-8f（`LP8T` 码透传/类型合同/身份四要点；`NW8E`；`EC8L`；`IN9M`）与 V3-8g（`LP8T`/`NW8E`/`EC8L` 语言面与连续律；drift 21 钉）。条目按「节区+文件名」定位（tag 非全局唯一；防坑⑯）；漂移永钉族在 `tests/world/test_aoci_drift.py`（关键词+一致性+迁移覆盖律〔现覆盖 0029–0037〕+布局律；**现 22 钉**——V3-8h 已随迁其条目〔7d0c658：NW8E/EC8L/LP8T/PL8T/PV8T 五条目〕，改动/触碰被钉面必跑）；机制事实：工作树 CRLF/blob LF（`.gitattributes eol=lf` 归一）；新表/新迁移/新模块/新常量 ⇒ 刀内随迁；维护语义=改「现在时为假的断言」、历史归属句保留；本仓现役实践=手随迁+drift 钉双保险（AOCI 块所述 `aoci_maintain` 等工具在本机实测未接入）。**V3-8h 交付时须随迁其条目**（llm_providers/narrative_web/web.py/reader 面）。
- **工作纪律留痕**：本对话总控零通道违规（仓内文件一律 Edit/Write；Bash 仅只读/`git add`·`commit`/构建命令；探针与变异一律仓外）；executor-pro 一次余额中断（处置=总控取证吸收，留痕入交付报告）；executor-flash 一次 heredoc 形态（无文件落地、零仓内写入=至多训诫级，REGISTER v1.7.13 在册）；评审一次仓外副本 `printf >>` 追加变异自报（收尾还原、归一字节全等，仓内零痕）。
- **新总控「先完全理解设计」指引（用户明令——布置任何执行任务**前**必做）**：①本文件全读（基准纪律区、dmcp 段、维护规范、CI 触发纪律、工程事实与红线、当前状态块、本块、防坑区）；②**两份正典全文**（`docs/design/2026-10-05-living-world-spec.md` **v3** + `docs/design/2026-10-08-cognition-and-narrative-quality.md` **v1.3**）；③**范式转折设计篇全文** `docs/design/2026-10-12-narrative-v3-paradigm-shift.md`（v3.1——**注意本会话新增两节：§10.4 真实模型接线基线〔五项〕与 §10.5 阅读面核心循环落法〔停点律+章间作者层〕**）；④**四份 canonical 的 V3 节**（DOMAIN §20／STATE §21–§27／DATA §26.2／RA §27–§30）；⑤`docs/IMPLEMENTATION_PLAN.md` §20（V3 刀表 + V3-8f/g/h 补写行）；⑥DMCP `design_get` 本块 DEC 链（重点读 `…10`〔四症取证〕`…22`〔体验三件〕`…32`〔核心循环两面〕）；⑦现役代码现场精读（`src/elc/world/{time,bible,cast,director,settlement,scene,writer,action,cognition,memory,providers,pipeline,bootstrap,gold,llm_providers}.py` + `src/elc/narrative_web.py`〔装配层〕+ `narrative/{types,store}.py` + `store.py` + `package.py`〔v8 墙〕+ `host.py` 装配链 + `web.py`（V3 八路由+语言路由增量面）+ `webui/reader.{html,css,js}` + `tests/world/test_v3_*` 十五族〔含 v3_8f_*/v3_8g_*〕+ `tests/host/test_v3_8e/8f/8g_*` + `migrations/0029–0037`）。**理解标准 = 能回答**：世界怎么转（章-场-段自转 + NCP-1/2/3/4 各写什么/谁推进 tick/编排器零写权）；用户在世界里是谁（durable player character + User Gate 停点判据 + Resolver 唯一裁定权 + world-authoritative ResolverContext + outcome_ref 链 + continuation obligation）；**停点律与章间作者层（§10.5——本会话新增的落法两面）**；Plan≠Canon 物理落点；教学咬合面待接线；双门纪律（12 条结构验收〔已成立〕+ 用户亲验〔在途、已重计时〕——通过前不切主 UI、不退役 Legacy V2）；三刀（V3-8f 四修复+身份合同两面；V3-8g 连续律/进度与忙碌反馈/语言可切；V3-8h 停点律+章间作者层）各交付什么；HOLD（真实 rollout／SessionBudget 三分／内容补课／多世界／UI 切换）与 sealed（0029–0037 与已盖章切片「改必显式重开」）。

## 会话交接索引（详细块归档在 docs/sessions/session-handoffs-archive.md）

每会话一行（日期 + 刀序 + DEC 族区间 + 归档指针）；完整交接块在归档文件与 git 历史。

- 第四十五会话（2026-10-14，新总控·产品裁定 + V3-8h/V3-8i 两刀全链毕）：**产品级裁定——三级阶梯 1→2→3（1 代入式小说创作应用／2 基于 1 底座「创作想法用英语表达」可学英语应用／3 基于学习应用「按需求/水平/表达思维发展世界」）+ 三新仓严格顺序 + 每级独立可发布异名异前端 + 引擎随迁不重写**（DEC `OPI-f55cd8c7-…13`，rev 843；诊断=范式 §1.1 产品定义只含「小说世界」半句、「学会带走」坠海，三级实为历史反转、梯子未写）。**V3-8h 核心循环补完刀全链毕**（交付 `860ab31`+`7d0c658`；`_press_on` 驱动循环三真停点/章间作者层 direction 软期望；四门双路 6314/drift 22；真实驱动三场景〔gold 锚定场〕；评审 ACCEPT〔F1–F5 nit 登记〕；VR `…9` PASS；收口 `…11` rev 842；REGISTER v1.7.14/15）。**用户亲验实败（一直写个没完/玩家角色被代演）→ 取证定案三层根因（真实计划章零门/schema 无门点/no-puppet 句无锚定——§2.2/§2.5 已写条款未落）→ V3-8i 门的生产面刀全链毕**（合同 §10.6 增量 `29c2c95`；交付 `f951b6b`+台账吸收 `6ca5995`；blueprint 门拍生产/校验拒+重铸一次/玩家锥定三臂/无门地板 4 段；四门双路 **6330**/drift 22；**真实计划场五场景**〔核心证：一次驱动 2 段门开问玩家、锥定句 18/18 真 prompt〕；评审 ACCEPT〔作用域裁定独立复核接受、M-A/B 变异证齿、F1 死参 M-C 双证〕；VR `…23` PASS 一投即中；收口 `…24` rev 847 SYNCED 844；REGISTER v1.7.16/17）。**下一动 = 用户重启 8760 重跑亲验（双门之二，切仓前最后验证）→ 过后发布就绪审计 → 终末交接块 → 议切新仓。**
- 第四十二会话（2026-10-13）：**V3-7 → V3-8a → V3-8b 三刀全毕**——交接块已归档（`docs/sessions/session-handoffs-archive.md` 第 0 条；原文 `git show b671fa6:AGENTS.md` 的「终末换总控交接块（2026-10-13——第四十二会话）」节）；DEC 链（`OPI-06b954e0` 族）：V3-8a = `…2`（开工）、`…4`（TASK）、`…6`（VAL）、`…8`（VR）、`…10`（收口，rev 813）；V3-8b = `…15`（开工，rev 814）、`…17`（TASK）、`…19`（VAL）、`…21`（VR）、`…24`（收口，rev 817）；V3-7 = `OPI-d274a7fb` 族 `…6`（开工）、`…8`（TASK）、`…10`（VAL）、`…12`（VR）、`…14`（收口，rev 809）。**更正留痕**：V3-8a 合同增量 `aa8674b` 前瞻写的 `DEC-OPI-d274a7fb…16` 经 `67afdc0` 更正为 `DEC-OPI-06b954e0…2`。
- 第四十三会话（2026-10-13，新总控接续）：**V3-8 本体开刀——范围裁拆 V3-8c/d/e 三刀序，三刀全链毕（V3-8 本体收官）**——DEC 链（`OPI-cddb517c` 族）：**V3-8c** `…5`（开工，rev 818，含三刀序 + F4 裁定 + 阅读面形态）/`…7`（TASK）/`…9`（VAL）/`…13`（VR PASS）/`…17`（收口，rev 821）；交付 `e68dcb5`+`9be8453`+处置 `b63fcbb`+台账 `7cae9aa`（ACCEPT-WITH-FINDINGS 无阻断，F1-F3 本刀修；REGISTER v1.7.4/v1.7.5）。**V3-8d** `…19`（开工，rev 822）/`…21`（TASK）/`…23`（VAL）/`…25`（VR PASS）/`…29`（收口，rev 825）；交付 `0013593`+`4adba5d`+处置 `cccae95`+台账 `439fadc`（同前，c-revisit 零需求；REGISTER v1.7.6/v1.7.7）。**V3-8e** `…31`（开工，rev 826）/`…33`（TASK）/`…35`（VAL）/`…37`（VR PASS）/`…4`（收口，族 `b8dc176c`，rev 829）；交付 `c465b54`+`bc31aa8`+处置 `23afd74`+台账 `fc2589c`（F1-F4 本刀修，§7.1 脱队读裁定接受；REGISTER v1.7.8/v1.7.9）。**下一动 = 用户「好玩」亲验（双门之二）；本会话终末交接块见上「终末换总控交接块（2026-10-13——第四十三会话）」。**
- 第四十四会话（2026-10-13，同总控接续）：**V3-8f 真实模型可用性修复刀全链毕**——用户「好玩」亲验实败（四症取证：egress 30s 超时 < 真实 43–72s／prompt 未写值类型⇒bad-shape／失败码压平 transport-error／路由 60s 等待截断长驱动）→ 四修复 + 身份合同两面（第五面 resolver 渲染形；第六面 planner 身份四要点，追补裁决）→ **真实模型全链冒烟两轮**（smoke2 至 next_chapter 全绿：submit 265.6s 一驱动跑通）→ 独立评审 ACCEPT-WITH-FINDINGS（F1 空转断言升格本刀修 + 回退变异证齿）→ 盖章收口。DEC 链（`OPI-c0f4d9b4` 族）：`…10`（开工，rev 830）/`…12`（TASK）/`…14`（VAL）/`…16`（追补：planner 身份面同刀修，rev 833）/`…18`（VR PASS）/`…20`（收口，rev 834）；交付 `185d861`+`4c75be6`+`ddd6027`+处置 `110b130`+台账 `ac187a9`；REGISTER v1.7.10/v1.7.11。**V3-8g 阅读面体验与连续性刀全链毕**（用户亲验反馈三件：太慢无进度／选项点击无响应感／正文纯英文 + 总控实机发现续段近逐字复述）——连续律 prompt 合同 / 进度可见与忙碌反馈（spinner+秒表+阶段句+绝不静默）/ 正文语言可切（`v3_prose_language` 默认 en 可切 zh；已写段不改写）；真实验证：连续性同度量 0.95823→0.03827、zh 新段非 ASCII 0.9844、既有段 sha 零改写；总控真浏览器复核（秒表 9s→32s 在走/语言选择器/副本 ch2 计划 CJK 0.889）；评审 ACCEPT-WITH-FINDINGS 无阻断（F2 补钉 + 回退即红）；盖章 PASS/SYNCED。DEC 链（`OPI-c0f4d9b4` 族）：`…22`（开工，rev 835）/`…24`（TASK）/`…26`（VAL）/`…28`（VR PASS）/`…30`（收口，rev 838）；交付 `5b11d2b`+`2d75a6e`+处置 `feab75d`；REGISTER v1.7.12/v1.7.13。**V3-8h（核心循环补完：停点律+章间作者层）三件已铸（`…32`/`…34`/`…36`）、合同增量 `307d835`、执行者被用户停止（半成品留档 `D:\elc-scratch\v38h\rejected-partial.diff`、拒收重交、待重派）——本会话终末交接块见上「终末换总控交接块（2026-10-13——第四十四会话）」；用户亲验在途（已见 ch02 中文段）。**
- 第四十一会话（2026-10-13）：**V3-5R → V3-6 → V3-6R 三刀全毕**——DEC 链（`OPI-dc1bafdf` 族）：V3-5R = `…11`（开工）、`…13`（TASK）、`…15`（VAL）、`…17`（VR）、`…19`（收口，rev 797）；V3-6 = `…5`（开工）、`…21`（重放行，rev 798）、`…23`（TASK）、`…25`（VAL）、`…27`（VR）、`…29`（收口，rev 801）；V3-6R = `…31`（开工，rev 802）、`…33`（TASK）、`…35`（VAL）、`…37`（VR）、`…39`（收口，rev 805）；三件暂缓留档：`…7`/`…9`（V3-6 首轮 TASK/VAL，已被 `…23`/`…25` 取代）。交接块归档于 `docs/sessions/session-handoffs-archive.md`。
- 第四十会话（2026-10-12）：**新总控会话·V3-4（含 V3-4R）→ V3-5 三刀全毕**——DEC 链（`OPI-be7b094f` 族）：V3-4 = `…7`（开工）、`…11`（TASK）、`…13`（VAL）、`…16`（VR）、`…17`（收口，rev 782）；V3-4R = `…21`（开工）、`…23`（TASK）、`…25`（VAL）、`…27`（VR）、`…28`（收口，rev 786）；V3-5 = `…32`（开工）、`…34`（TASK）、`…36`（VAL）、`…38`（VR）、`…39`（收口，rev 790）。交接块与六个收口块归档于 `docs/sessions/session-handoffs-archive.md`。
- 第三十九会话（2026-10-12）：**范式转折（Narrative V3）→ V3-0R → V3-1 → V3-2（含 V3-2R）→ V3-3（含 V3-3R）六刀全毕**——DEC 链：`…5`（E 取证）、`…7`（范式转折）、`…9`（V3-0R）、`…11/…16/…22/…25/…27`（V3-1）、`…29/…31/…33/…35/…38`（V3-2）、`…41/…44/…46/…50`（V3-2R）、`…52/…54/…56/…59`（V3-3）、`…61/…64/…66/…69`（V3-3R）。归档于 `docs/sessions/session-handoffs-archive.md`。
- 第三十七/三十八会话（2026-10-11）：**换总控交接（D 程序六刀全毕）→ dogfood 第二期取证**——归档于 `docs/sessions/session-handoffs-archive.md`（第三十八会话的「E 程序」下一动款已被第三十九会话范式转折废止，见设计篇附录 A4）。
- 第三十四/三十五/三十六会话（2026-10-11）：**总设计补写 + D-1 用户角色 + D-3 世界详情 + D-2 密度重量 + D-4 显示层级统一**——DEC 链：`…40/44/47`（D-1）、`…49/53/55`（D-3）、`…57/61/69`（D-2）、`…63/65/67`（D-4）。归档于 `docs/sessions/session-handoffs-archive.md`。
- 更早（第三十三会话及以前）：归档于 `docs/sessions/session-handoffs-archive.md`。

## dmcp 工作流协议（v2，2026-09-20 用户纠正后立——总控必守）

每刀（task）完整链：**四查+VAL+TASK 同铸 → 派执行者 → 总控独立复核（pytest/ruff/mypy/CI 亲跑）→ 独立评审（新上下文 executor-pro 只读评审，产 findings）→ 处置（修/DEFER/留痕）→ validation_submit 盖章（在最终验证过的提交上）→ design_sync REBUILD+CHECK 收口**。缺评审即违约（本仓 2026-09-20 已犯一次，用户点名纠正）。**顺序修正（2026-09-22 p6-2/p6-3 实测）**：原书写「复核 → 盖章 → 评审 → 处置」在实践中不可执行——VR 必须盖在**最终验证过的提交**上，而「处置」按定义会再改一次代码（p6-1/p6-2/p6-3 的 VR 实际都盖在处置修后的提交上）⇒ 自本行起以「处置 → 盖章」为书序（盖章仍是验收要件，只是位次挪到最终态）；因此「盖章后不得再改该切片代码」成为新硬约束。**迁移刀的成本（p6-1/p6-3 实测）**：新增一个迁移会使**所有** head/stamp/applied 钉变假（0012 断 16 个测试、0013 断 22 个），任务书必须**逐条预写**搬迁名单；自 p6-3 起这些值集中在 `tests/conftest.py` 的 `MIGRATION_IDS`/`SCHEMA_HEAD_FILE`/`SCHEMA_HEAD_VERSION`（改一处 + 该刀自己的迁移测试），并有一条自证钉校验常量 == 真实仓库。

- **纪律 ①（⟳ 刷基）**：连续两次 dmcp 变更之间必须 design_status 纯读刷新基再填 expected——REVISION_CONFLICT 即忘了刷基（错误面会给 current id 可直接重构）
- **Phase 开工第 0 步**：`plan_build` 铸 PLAN（VERTICAL_SLICE/RISK_SPIKE/VALIDATION_EXPERIMENT/ENABLER 工作项+relations）；任务从 plan 工作项展开。**readiness 更正（2026-09-20 第四会话查实）**：design_readiness 的 gate 行来自 gate policy 而非 plan_build——默认策略是 FINDING-only 单族行集（每条 finding 一行 BLOCKING），finding 册恒空 ⇒ 恒 READINESS_BASIS_INCOMPLETE；解锁要么服务端接线 preparer 让 findings 真实入册，要么宿主侧配 `DMCP_READINESS_POLICY_FILE`（宿主操作，不代执行）。**阶段门禁当前由本仓工作流承担**（VAL+独立评审+decision），readiness 仅作解锁后的复核面
- **评审面构建局限（当前服务端，已铁证）**：REVIEW_REQUIREMENT/REVIEW_PACKET 只能由宿主侧 preparer 铸，而 dist 无任何入口接线 `createHostReviewBasisPreparer`（D:\MCP apps/mcp-server，查实 0 wiring）→ review_submit 恒 OBJECT_NOT_FOUND、finding 册因构造恒空（finding_list=0 是构建事实不是「无问题」）。**降级路径**：评审照做（独立上下文评审员），findings 全文+证据+裁定入 decision（范式见 `DEC-…d7937fd7.19`/`DEC-…eaaa5a1d.9`），服务端升级接线后补录正式 finding 并迁移裁定
- **主体/能力（当前服务端 env）**：HUMAN_USER + DESIGN_STATE_READ/MUTATE 两族——FINDING_ADJUDICATION/DISPOSITION 族未授，裁决面即使有 finding 也会被诚实拒绝；升级服务端配置属宿主侧操作，skill 不代执行
- 契约=跨会话记忆：GOAL/RUNTIME/IN_SCOPE/OUT_OF_SCOPE/TECHNICAL_CONSTRAINTS/ASSUMPTIONS 在载体 `DEC-…9dc4e77f.4`（含六 canonical 文件 digest 绑定，漂移即假设失效；AGENTS.md 活文档不绑）；契约改写是整体替换（⑲），改前先 design_get 读回

## 派单协议（用户明令，2026-09-20）

- **执行者 = `executor-flash`（一般任务）/ `executor-pro`（难题）**——用户安装在 `~/.zcode/agents/`（model 钉 GLM-5.3-Flash / GLM-5.3，**须带 `thoughtLevel: max` 键**——2026-09-20 补，缺则新 harness 拒启，见 `DEC-…091f35c3.13`）。**禁止用内置 `general-purpose` 做执行任务**。
- 总控不亲自执行（写代码/测试/探针/部署一律派执行者，先 `task_build` 铸任务书）；设计类任务书先过 grilling 前沿；**任务书四查 + VAL 与任务书同铸**（前沿/实现设计条目/计划时效/预算算术；交付后补盖 VAL 视同无效验收）。红线全文 0–31 见旧仓 `D:\测试1\AGENTS.md`（红线 28/29/30/31 尤其要读）。

## 工程事实与红线（本仓特有）

- **前端治理（`DEC-OPI-631452f9-bd11-4b69-8fb6-df16f825fca6.37`，F-G1 起）**：前端改动必须经组件库（`src/elc/webui/`）与 `docs/FRONTEND_SPEC.md`；库中已有组件禁止重复实现（评审 finding + 拒收事由）；新组件须同刀登记 spec（组件契约条目 + 任务书四查写明）；**库随产品增长**（用户裁决 2026-09-28：活注册表——先查库、已有复用、无则新建并同刀登记 spec 表 + COMPONENTS 元组）。
- **远程**：github.com/ZJW11398925/english-learning-clean（public）；**CI 四门**：ruff → mypy → compileall → pytest（Ubuntu，0 skipped 为准）。**CI 触发纪律（用户明令 2026-10-11：「不要老是触发 CI，损耗太多 action 额度；**不是不 push，而是 push 跳过 CI**」）**：①**push 照常做**——代码同步/备份是硬要求，远端必须跟手（按交付节点批量推即可，不逐刀推）；②**push 与 PR 都不自动跑 CI**——`ci.yml` 已改为 `workflow_dispatch` 手动触发；本仓全流程本地验证（总控亲跑全量+四门）为硬门，CI 是按需手动的备用复核面；③**禁止再把 CI 当门用**——验收/交接一律引用本地亲跑读数。
  **「必须跑 CI」硬清单（手动触发，仅此六情形）**：
  1. **CI 配置自身变更后**（改 `ci.yml`/安装步骤/依赖）——验证配置有效（本次已跑：run 38127998426）；
  2. **相位收口 / 程序收官 / 外评轮启动前 / 换总控交接前**——远端绿标作交接面（每相位一次量级）；
  3. **跨平台风险刀**——改动涉及行尾（CRLF/LF）、文件系统行为、路径大小写、编码的刀完成后（本地 Windows 过了≠Linux 过）；
  4. **依赖面变化**——`pyproject.toml`/安装流程/导入拓扑（跨包引用、冷启动面）变更后；
  5. **长期累积兜底**——距上次绿标 ≥ 一个相位时，在下个节点补跑一次；
  6. **用户明示要求**时。
  **不必跑**（默认不跑）：单刀日常交付（本地硬门已覆盖）、纯 docs/台账/内容数据提交。**跑法**：`gh workflow run ci.yml`；结果回执入当刀/当会话台账（run id + 结论）。**红则当刀处理**（不阻塞已收口刀的本地验收，但修复优先）。
- **测试**：`python -m pytest`（0 skipped 为准；分目录读数随刀漂移，以「当前状态」块为准；**collect 须写 `-o addopts=""` 才会打印总数**）；静态：ruff + mypy；迁移 head/stamp 值集中在 `tests/conftest.py` 的 `MIGRATION_IDS`/`SCHEMA_HEAD_FILE`/`SCHEMA_HEAD_VERSION`；新增迁移会使同族钉变假，搬迁面须**预先写明**（当前迁移号/schema_version 见「当前状态」块）。
- **规范优先级执行**（P4-0 教训留痕）：canonical 与既有实现漂移时**实现服从 canonical**（列名/词表逐字照原文；无决策裁定不得以「Phase 0 拼写」为由倒置）；本仓已有两例（0007 列集、P4-0 relationship 列名/枚举）——任务书四查加「列名/词表照 canonical 原文」必答项
- **门是意图不是障碍**（P4-2 教训留痕）：实现**不得为过架构门而变形**——P4-2 首轮执行者把 `ProjectionExecutor.execute` 以「取方法值再调用」（`run = executor.execute; run(view)`）绕开 Gate 2 的 `.execute(` 调用形态扫描，总控判返工改**正向命名** `project()`（Gate 2 把 `.execute()/.commit()/.rollback()` 词表留给 runtime 不得触碰的 DB 机件；改名后结构性护栏不变、独立 AST 扫描 0 违规）。同轮总控把执行者自报的边界「RUNNING 残骸本刀不回收」升格为本刀内做（RA §22 明文把 pending projections 列入恢复扫描）——**边界自报是诚实的，但「RA 明文要求」级缺口不因自报而免做**
- **VAL 路径集纪律**（P4-2 教训留痕）：验收的 `applicability_contract.paths` 必须覆盖实际触及路径——VAL-…74 漏 `src/elc/platform/db`（Gate 2 规定 runtime 无 SQL，Runtime 拥有的投影适配器只能落此）与 `src/elc/teaching`（对账需 refs 扫描面），P4-2 铸同题扩集 `VAL-OPI-4d516e4f.…7` 盖章并在 `DEC-…4d516e4f.13` 显式留痕取代关系（**不双重声明同一观察**）；P4-3 同例（VAL-…76 漏 runtime/migrations → `VAL-…4d516e4f.17`）
- **落盘通道三段纪律**（P4-3 教训留痕，第六次违规后升级；**p6-2 追加第四段**）：①一切 `.py/.sql/.yml/.toml` **一律 Write/Edit 工具落盘**（Bash heredoc/`sed -i`/重定向/`ruff --fix` 等一律违规——`--fix` 属同族写操作）；②回执必附**「Bash 使用清单」**（逐条命令意图，非只读用途标红；同一刀内第二次违规=整刀拒收重交）；③**字节零差复写一律用 Edit 往返 + 四重验证**（H1==H2、`--no-filters` raw 相等、字节数/行数相等、分块 sha256 全等），**禁止**对超大文件（本仓 `runtime/controller.py` 195KB）做单次全量 Write 复写——该文件含历史 mojibake 字节（~3637 行），Read 显示与真实字节不一致，人工转录必带显示伪影；④**仓内零写入（含临时/诊断文件）**——「同一条命令内创建并随后删除」**不构成豁免**（红线约束的是钩子与审计面而非持久性，见 `DEC-…5a0be06d.…9`）；需要诊断脚本一律落仓外临时目录。**p8-1 追加第五段（口径收紧）**：**变异/诊断脚本（含 `.py`）一律 Write/Edit 工具落盘——仓外副本也一样**（处置刀曾以 `printf >> <仓外副本>.py` 追加变异，虽仓内零痕仍计一次违规）；Bash 只许只读命令、`git add/commit` 与不在禁列的构建命令（`pytest`/`ruff check`（无 `--fix`）/`mypy`/`compileall`）；**同一刀第 1 次＝训诫留痕、第二次＝整刀拒收重交**（p8-1 切片两刀各 1 次、均训诫留痕；本切片内第三次违规一律整刀拒收）
- **冷启动 import 闭环**（P4-3 教训留痕）：`elc.runtime.__init__` 聚合导出 + 域模块互相引用可造出「域模块 → runtime 包 → 新模块 → 域模块」的闭环，测试套件因导入顺序侥幸不报而 `import elc.conversation` 冷启动失败；解法＝本地窄 Protocol + `TYPE_CHECKING` 注解导入 + **subprocess 冷启动钉**（逐包 import）——凡新增跨包引用面必带冷启动钉
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：**Phase 5 工程 + 语义均已 COMPLETE（P5-R 已毕并重签）**；当前位次 = **Phase 8（Teaching Gate + 自动教学面）**——**p8-0/p8-1/p8-2/p8-3 均已 COMPLETE、p8-4（同 turn 集成 + exposure 生产者 + 崩溃窗口 Moment 半）可以开**；**真实 automatic-teaching rollout 本体仍 HOLD**（语料 14/14 `readiness=None` ⇒ R2/R3/R4 可用目标 0；BF-02 §10 逐字门槛——**不是 Planner 的问题**））；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学/Planner SELECT（Phase 8 才开）；`decision_cycle_id` 收紧已随 0007 兑现（`DEC-…091f35c3.7` 裁定 b 闭环）
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # push 不触发 CI（workflow_dispatch 手动触发——见「工程事实与红线」CI 触发纪律）
```

<!-- aoci:begin -->
## AOCI 仓库认知

AOCI 为本仓库维护一个稳定、可版本化、可增量更新的仓库级认知层，供模型跨任务复用对系统的理解。

`aoci.txt` 是面向模型的结构化认知索引。它以每个受管理文件、数据库表或其他受管理对象一条独立 Entry 的方式，用符号标签与 F/R/A/S 语义表达对象的核心职责、重要关系、对外契约，以及理解或修改系统时必须知道的非显然约束和设计决策。

Header、目录段和全部 Entry 共同组成完整仓库索引，可以覆盖前端、后端、配置、数据库结构及其他受管理内容。受管理内容发生变化时，通常只需维护受影响的认知条目，不需要重新生成整个索引。

AOCI 提供系统架构、对象职责、重要关系、对外契约和关键约束的高密度视图。

### 工作原理

AOCI 采用“模型生成、模型读取”的认知闭环。

Header、Entry 和 Curation 语义的创作只按当前机器签发的 Plan 与实时 Guide 执行；由 Host 模型基于当前绑定证据独立完成。

Entry 的语义必须来自模型对真实证据的理解。不得仅依据路径、文件名、扩展名、AST、符号列表、依赖扫描、正则、固定模板或规则引擎推导、预填、拼接或改写索引语义。

对 Fresh Bootstrap，只按当前机器签发的 Plan 和实时 Guide 执行。当它们要求创作时，Host 模型创作 Root、Meta、Tag 和 F/R/A/S，提供 authoring-run 声明，并把它绑定到 Plan、Evidence 与完整 Candidate。不得要求 AOCI 填写 `origin=host_model`、制造 Receipt 或把程序生成的 Framework 当作语义。本文件不自行重建 Onboarding 流程。内部批次不是用户决策；只有遇到既有批准边界或真实的安全、漂移、CAS、Recovery 条件才停止。

### 最小使用入口

- `aoci_rules`：取得当前AOCI版本的会话运行合同。
- `aoci_overview`：建立或恢复本仓库的完整认知。
- `aoci_maintain`：受管理对象达到最终稳定状态后检查认知是否需要维护。
- `aoci_update_entry`：提交与当前证据和源码摘要绑定的完整语义更新批次。
- `aoci_report`：仅当当前布局和工具状态支持时，在证据不足、无法可靠生成语义时登记待办，不猜写。

其他MCP工具、CLI命令、参数和专项流程，以当前工具说明、Guide和 `--help` 返回内容为准，不在本文件中重复完整手册。

本区块只规定仓库接入、认知使用和收尾原则。`aoci_rules` 承载当前会话合同，Guide实时输出承载当前Plan的执行顺序与停点，工具Schema、Spec和Validator承载机器结构与判据；Prompt、Description、README和静态文档不能覆盖这些机器事实。

### 建立、生成和恢复认知

1. 每个新的 Agent Run 开始时，应先判断：

   - 本仓库是否已经存在可用的完整AOCI索引；
   - 当前上下文中是否已有与本仓库根、当前索引版本和当前AOCI服务相匹配，并且模型仍可可靠使用的完整仓库认知。

2. 仓库已经存在可用的完整索引，但当前Run没有可靠完整认知时，先调用 `aoci_rules`，再调用 `aoci_overview`。

   完整认知仍可靠时直接复用。局部不确定本身不要求机械重读系统全貌。

   本Run从已知Host上下文压缩恢复时（包括宿主注入的压缩摘要），必须把此前模型认知视为不可靠。压缩handoff不得保留或摘要正式Whole-Index，也不得保留或摘要任何Overview Header、Entry、Chunk、Challenge或Attestation正文；只能保留安全续接所需的receipt身份、未完成write或Recovery状态，以及立即重载指令。复制进handoff的Whole-Index语义或receipt不能证明恢复后模型的当前认知可靠。若当前上下文已无法可靠保留运行合同，先调用 `aoci_rules`。继续业务任务前，使用 `refresh_reasons=["context_compaction"]` 和新的 `refresh_event_id` 调用普通完整Whole-Index `aoci_overview`（不设置 `check_only` 或设为false）；不得使用 `check_only` 或认知probe。原样跟随每个 `next_cursor` 直到 `completed=true`，确认交付，并且只基于新交付正文提交一次Attestation。完成这次新的完整传输后，即使Attestation为partial或fail也消费该generation，并按既有合同继续source-bound任务，不再自动调用第二次Overview。

   AOCI可以针对 `context_compaction`、项目 `cognition_refresh_threshold` 下的机器 `semantic_threshold` 或主要 `phase_transition` 提供checkpoint与认知状态事实。只需要这些紧凑事实时使用 `check_only=true`；这些事实只向Agent提供建议，不替模型决定是否需要系统全貌。

   Agent显式调用普通 `aoci_overview`（未设置 `check_only` 或为false）时，只要能形成一致的CognitionSet，AOCI必须完整交付请求scope。不得因为已有receipt、阈值未达到或没有待处理刷新原因而抑制正文。正式认知Dirty或Stale时仍交付正文，但必须标记不可靠。存在未决恢复或无法形成一致snapshot时失败关闭，不返回混合正文。

   普通Overview返回 `continuation_required=true` 时，必须原样提交 `next_cursor` 并自动继续到 `completed=true`。不得询问用户、开始业务任务或给出阶段性系统结论。Host截断、缺块、重复、乱序、cursor失败、Index变化或`chunk_tokens`变化时停止本次认知链。Attestation完成前不得用Memory、源码、Spec、`aoci.txt`、历史会话、scope、search或Entry读取修补或补充Whole-Index认知。Challenge ordinal是正式Entry序列中的1-based位置；Header内容、注释、空行、Section/Overview/Chunk Marker、Receipt与Metadata均不计数，Chunk Receipt ordinal使用同一序列。Attestation必须原样回绑本次Challenge发布的当前`index_sha256`、`entry_sequence_sha256`与`entry_count`；旧Index、旧Entry序列、旧数量或旧Attestation均无效。完整链结束后只正式提交一次既有模型认知Attestation；同一响应只允许一次不改变语义答案的JSON Schema或字段格式修正。对象、Tag或F不匹配即失败且认知吸收不确定，不得语义重试或旁路补答。首次认知失败时还不得执行Root/Meta、Migration、全局布局或其他未重新绑定的系统级决策。上下文压缩刷新若传输完整、认知身份不变、治理对齐且没有Recovery或第三方冲突，即使Attestation为partial或fail也消耗该refresh generation，并继续原任务，不再自动重读Overview。`system_mastery_percent`只自评系统框架——架构、职责、强关系、稳定外部契约以及高熵安全和维护约束——不表示完整实现或运行实况知识；机器索引覆盖率必须分开。默认只向用户输出由本次真实覆盖率、Challenge、块数、Token和掌握度生成的规定成功或失败一句话。Host截断时提示用户把 `overview_delivery.chunk_tokens` 设置为更小的合法值后重新开始，不得自动修改。

   加法认知等级必须与严格证明字段分开解释。`delivery_verified`表示已加载Index且Host交付已确认，但完整认知验证仍未完成；应表达为“已加载且交付已验证”，不得描述为“没有认知”或“没有理解系统”。`cognition_verified`要求Attestation通过（Challenge至少80%的ordinal完全正确且对象身份至多失手一处），`cognition_governed`还要求治理对齐。通用完整读取失败句只用于真实交付故障。

   当Overview响应包含可选`cognition-state/v2`投影时，必须分别解释各维度。其Level止于`model_cognition_usable`；`strict_attestation_verified`、`governance_aligned`与`current_system_cognition_reliable`都是独立状态，绝不参与该Level。ordinal、对象身份、Tag或核心F不匹配可以导致严格Attestation失败，而模型认知仍然可用；不得仅凭这种不匹配就宣称模型没有理解系统。只有`current_system_cognition_reliable=true`允许无保留地声称当前完整系统认知可靠。投影缺失时继续使用上述Legacy解释。

   普通的只读审计、分析、检查、不修改代码或不提交、不push，不自动等于严格零写入，也不改变上述认知有效性判断。Codex Memory和历史Skill只能辅助恢复经验、用户偏好与调查方向，不能替代与当前仓库根、索引摘要、AOCI服务身份和认知范围匹配的当前认知收据；项目AGENTS和当前AOCI身份在AOCI状态上优先于历史Memory。

   只有用户明确禁止Ledger、元数据、`.aoci`运行资产及任何文件写入时，才按严格零写入处理。若必要的认知建立与该边界冲突，必须报告冲突并请求用户裁决或建议使用隔离副本，不得静默以Memory替代当前仓库认知。

3. 仓库没有可用的完整索引，或当前只有最小骨架、Header不完整、Entries未完成、必要Curation尚未裁决时，如果需要建立正式完整AOCI索引，先取得 `aoci_rules`，然后进入当前AOCI Guide。由Guide依据仓库真实状态决定下一阶段并完成必要安全步骤。

   `aoci_maintain` 不替代索引建立流程。

   不在本文件中自行重建或硬编码完整索引生成状态机。

4. 在长程任务中，模型负责保留当前认知收据并正确使用刷新门禁：

   - Host报告上下文压缩或模型已知系统全貌丢失时，执行上述强制 `context_compaction` 重载规则；AOCI不能自行推断Host事件；
   - 进入真正的主要阶段时声明 `phase_transition`，不得把函数、测试运行或小步骤当作阶段；
   - 在有用的稳定检查点通过 `check_only=true` 取得机器语义计数；
   - 除已知压缩的强制重载外，由Agent判断当前任务是否需要再次显式获取指定scope或完整Overview；
   - 在维护和对齐完成前，保留AOCI报告的Dirty或Stale可靠性状态。

### 任务收尾与认知维护

5. 纯只读问答、分析、版本核验，或没有产生受AOCI管理对象变化的任务，不需要调用维护工具。当前AOCI版本是任意`aoci_overview` check_only或`aoci_maintain`响应里的`cognition_receipt.mcp_service_version`；二进制路径是项目`.mcp.json`里的`command`，CLI不必在PATH上。

6. 发生受AOCI管理对象变化时，待其达到本次任务的最终稳定状态后，只调用一次 `aoci_maintain`。不要在每次中间修改后逐文件维护。

7. 若维护结果返回真实语义候选，Host 模型必须基于每个候选绑定的对象和必要证据，独立创作完整标签与F/R/A/S更新。通过 `aoci_update_entry` 一次提交当前机器签发批次的完整候选集合，同时原样保留每项 `source_sha256`、`candidate_id` 与对应domain批次身份。`max_entries`只限制单次请求和原子事务，不限制logical plan、Whole-Index或Managed Scope。`remaining`非零时，在当前批次成功Apply后重新调用Maintain并从新preimage继续；绝不能为满足transport上限缩减Index覆盖或自行截取返回批次。

   没有足够证据且当前布局支持 `aoci_report` 时，使用它而不猜测、套用模板或为消除待办而生成缺乏证据的认知。

8. 必须遵守工具返回的结构化状态和安全边界：

   - `repair_required`：只修复明确命中的候选，再重新提交当前机器签发的完整批次；
   - `stopped`：结束当前写入尝试并检查 `failed_step`、错误、正式写入证据与Recovery。auto模式下，已证明零写入则记录closure并重新Plan；完整Intent和可证明postimage则Resume；策略要求Rollback且preimage可证明则精确恢复后重新Plan。只有证据不足、第三方正式字节冲突、需要审批或外部动作，或命中其他真实安全边界时，才停止整个用户任务；
   - 冲突、审批、人工裁决、权限和安全信号不得忽略；
   - 已经对齐后不得重复维护或重复写入；`refresh_ready_for_overview` 是checkpoint事实，由Agent决定是否为下一阶段请求普通完整Overview。

   维护完成后如果又修改了任何受管理对象，之前的维护结果失效，应在新的最终稳定状态重新完成收尾。

9. 用户只限制业务文件范围，但没有明确禁止仓库托管资产时，AOCI托管资产可以在收尾阶段为保持认知一致而更新，并应在审计和提交中与业务文件区分。

   用户明确禁止修改 `aoci.txt`、`.aoci`、元数据或任何额外文件时，以用户限制为准，不得写入，并如实报告剩余不一致。

### 专项流程

初始化、完整索引生成、Header生成、Entries生成、数据库结构索引、Curation、人工评审和故障恢复，只按当前AOCI Guide或工具在对应阶段返回的指令、命令和安全停点执行。

不预加载、不猜测，也不自行重建这些专项流程。平台调用方式、请求格式、批次上限、审批规则、索引格式细节和恢复步骤由对应Guide、工具说明、模型Prompt和CLI帮助按需提供。
<!-- aoci:end -->
