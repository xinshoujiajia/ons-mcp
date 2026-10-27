# 全部待办清单（Roadmap）

> 现状：一~三阶段完成。游戏能起跑 → 标题 → 序章 → 持续推进 → 选项 → 跳转；
> 排版与引擎逐项对齐（几何全 0 偏差，像素差 0.08%）；变量模型按引擎槽位语义重写（见 J 组）；
> 数组（`dim`）与表达式对齐引擎（L 组）；**存档只剩原版 `save<N>.dat` 一套格式**，
> 被真引擎验证过读档成功；读档靠脚本重跑重建 UI，与引擎同一套机制（M / N 组）。
> 单测 123 项、协议 38 项、端到端 11 项全绿。
> 下面是把"能玩"做到"能玩通、能换游戏、能交付"要做的全部事情。

命令覆盖现状（只统计脚本里真实出现的命令；宏按 `defsub` 声明排除）：

| 类别 | 万华镜 | Ever17 | 说明 |
|---|---|---|---|
| 脚本用到 | 128 | 108 | |
| 已实现 handler | 72 | 60 | 含 `mov2..mov10` / `movl` / `dim` / `cell` |
| 有意 no-op | 34 | 13 | 视频/转场/动画/菜单装饰、鼠标与层序查询，见第 7 节 |
| 游戏宏（执行宏体即可） | 21 | 35 | `bg01` / `chara01` / `cgview` 等 |
| **完全没处理** | **2** | **0** | `char1` / `overlap_long`，都是脚本笔误，引擎 LUT 里没有此命令 |

（0.10.0 之前这张表是 63 / 52 / 41 / 2 —— 之后音频、`dim`、`cell`、`getmousepos`
陆续从 no-op 变成实体，数字已重算。）

---

## A. 稳定性与内存（**已完成**）

| # | 任务 | 状态 | 实现 |
|---|---|---|---|
| A1 | 图片缓存 LRU | ✅ | `OrderedDict` + 字节预算（默认 320 MB，`start(cache_mb=...)` 可调），超预算淘汰最久未用；单张 > 预算一半则用完即弃、不进缓存 |
| A2 | 条图解码前预判 | ✅ | `_header_size()` 只读 PNG 头拿尺寸，`w*h*4` 超 `max_image_mb`（默认 96 MB）直接放弃 |
| A3 | 只缓存裁剪结果 | ✅ | `load_cell_image()` 按 `path#cell0/N` 建键，裁完的格子进缓存，原条图不驻留 |
| A4 | 资源统计进 state | ✅ | `state().memory = {entries, mb, budget_mb, decoded, skipped_too_big}` |
| A5 | 未知素材去重告警 | ✅ | `unsupported` 变成 `{count, first_line}`，同一素材只累计不刷屏 |

**实测对比（同一段 400 次点击，从 *start 到第一章中段）**

| 指标 | 修前 | 修后 |
|---|---|---|
| 缓存条目 | 703 | 116（随后稳定在 100~180） |
| 缓存占用 | **2.45 GB** | **319 MB**（预算 320） |
| RSS 增长 | +1.81 GB | +3 MB |
| 峰值 RSS | 2.53 GB | 388 MB |
| 每次点击耗时 | — | 6~10 ms |

1200 次点击长跑（跨 `w01_01 → w01_02 → w02_01` 三个标签）：缓存恒定在 317~320 MB，
RSS 波动 ≤ 3 MB，7.4 秒跑完，未出现卡死。

---

## B. 长距离通关验证（**已完成**）

| # | 任务 | 状态 | 实现 |
|---|---|---|---|
| B1 | 自动推进器 | ✅ | `tools/playthrough.py`：`state()`→有选项就 `choose()`→否则 `click()`；`--policy first/last/alternate`、`--until-label`、`--clicks` |
| B2 | 跨章节验证 | ✅ | 一次跑到 w17_03b 通关后自动回标题重开，跨章节标签切换正常 |
| B3 | 多选项验证 | ✅ | `tests/test_choices.py`：定点把 PC 摆到 6 处 `csel`，逐个选项验证跳转，12/12 通过 |
| B4 | 长跑报告 | ✅ | `docs/shots/playthrough.json`（时间线/选项/内存/未实现命令） |
| B5 | 卡死检测 | ✅ | 同一 `(waiting,label,line,page)` 重复 ≥ `--stuck-limit`（默认 12）即判定卡死并停机记录 |

**实测（20000 步，策略"总选第一项"）**

| 指标 | 数值 |
|---|---|
| 步数 / 用时 | 20000 步 / 84.5 s（4.2 ms/步） |
| 走过的标签 | **125 个**（`title_btn` → `xswl` → `w01_01` … `w17_03b`） |
| 选项 | **12 次**，覆盖全部 6 处 `csel` × 2 个分支 |
| 通关 | ✅ 走到 `w17_03b` 后回 `title_btn`，再自动重开，进入第二周目 |
| 缓存 | 全程恒定 317~320 MB |
| 卡死 | 0 次 |

**顺带查出来的东西**（都不影响跑通，记在案）：

- `dwaveloop×275` / `chvol×156` —— 音频循环与音量；0.9.0 起音频已改成"记账"（更新状态、不播放），所以现在只记一次就不再报
- `char1×4@L13204` —— 脚本笔误（引擎 LUT 里没有 `char1`），降级跳过
- `bg/117` / `bg117` 共 4 处（L23464/24344/24374/25050）—— 移植脚本的路径写错了，
  实际文件是 `bg/bg117.png`；引擎同样找不到，表现为沿用上一张背景，属移植版自带问题
- `fade/u96f22.png` —— 转场图缺失，同样只影响转场

这一步同时是 A 的验收工具。

---

## C. 游戏内 UI（`textgosub` 钩子）（**已完成主体**）

| # | 任务 | 状态 | 实现 / 说明 |
|---|---|---|---|
| C1 | 钩子打通 | ✅ | `start(hooks=true)`；等待点变成 `*text_btn` 里的 `textbtnwait`；`pretextgosub` 每页开画前同步跑完（`run_sub_sync`）；名字改由脚本自己的 `lsp 299` 画，不再重复画 |
| C2 | `strsp` | ✅ | 按 `size`/`#RRGGBB` 生成文字精灵 |
| C3 | `bar` / `barclear` | ✅（近似） | 画成实色块（原版是九宫格条），视觉近似 |
| C4 | `split` / `mid` | ✅ | 支持 `$%var` 这种"用变量值当变量名"的写法 |
| C5 | 九宫格 `cell` | ✅ 0.11.0 | `cell 槽号,帧号` 已实现，渲染按指定帧（`build_sprite_image(..., cell=)`）。`savescreenshot2`（存档缩略图截图）仍是 no-op |
| C6 | 存档界面联通 | ✅ | `savegame`/`loadgame`/`savefileexist`/`savetime` 走我们自己的 JSON，已实测从菜单存档落盘 |
| C7 | 菜单交互进 MCP | ✅ | `click(button='right')` → `bwait=-1` 开菜单；也支持 `wheelup/wheeldown/esc/space` |

**实测**：右键 → `menu_btn` → 点「保存」(33) → `save_btn` → 点存档格 → `save_yesno` → 点「是」(55)
→ 回到 `save_btn`，`.onsmcp_save_0.json` 落盘。`tests/test_menus.py` 10 项检查全过。
钩子模式下 800 次点击（5.3 s）剧情行持续推进、无卡死。

**踩到的两个坑**（都写进注释了）：

1. `textbtnwait` 原本没记住变量名，右键/点击结果写不回去 → 整个菜单点不动；现在它和 `btnwait` 共用一个实现。
2. 开钩子后 PC 长期停在 `*text_btn` 的第 26093 行，`state().label/line` 会一直报 `text_btn`。
   现在 `label/line` 报**剧情位置**（最近一条文本），另给 `pc_label/pc_line/in_hook` 说明当前实际执行点。

顺带记录：`pretext_do` 里 `dwave ...:ead_cgdata55,1` 是移植脚本的笔误（应为 `read_cgdata55`），
引擎同样不认，每句带语音的台词会记一次，无害。

---

## D. 渲染保真（**D2 与透明模式已完成，其余按需**）

| # | 任务 | 状态 | 说明 |
|---|---|---|---|
| D1 | 文本内联颜色 `#RRGGBB` | ✅ | 正文里的 `#RRGGBB` 会切换后续文字颜色（引擎的 `color_list`），文字精灵与正文都支持 |
| D2 | 禁则处理（kinsoku） | ✅ | 按 `ScriptParser.cpp` 的默认表实现：行首禁则 `」』）］｝、。，．。？！ヽヾゝゞ々ー` 悬挂；行尾禁则 `「『（［｛` 下移。**用参照引擎逐项验证过** |
| D3 | ruby（注音） | ⏸ | 万华镜 1 次、Ever17 0 次；涉及注音体与基文成对排版，投入产出比低 |
| D4 | cell 动画 | ✅（静态） | `cell` 指定的帧会渲染；没有定时器驱动，不会自己播。长条图解码后不入缓存（60 格的条图能占几百 MB） |
| D5 | 按钮 hover 高亮 | ⏸ | `exbtn` 的悬停 ctl 已解析但没应用；agent 用 `buttons()` 拿矩形自己点，不需要 hover 视觉 |
| D6 | `monocro` 滤镜 | ⏸ | 两款游戏 0 次调用 |
| D7 | `windowback` / `transmode` | ✅ | `transmode` 已实现（全局透明模式）；`windowback` 影响文本框与立绘的层序，未做 |
| D8 | 过渡效果 | ✅（终态） | 过渡图缺失时画面是终态，不会卡住 |

### 透明模式（trans_mode）——**本轮最大的渲染修正**

手册《NScripter 函数手册》原文：

> **alpha模式下，如果没有alpha通道，会用图片右半作为alpha通道。**

引擎实现（`AnimationInfo::setupImageAlpha`，`AnimationInfo.cpp:1103`）：

| 模式 | 规则 |
|---|---|
| `alpha`（`:a`，**两款实测游戏全局都用这个**） | 图片**有** alpha 通道（PNG 一律算有）→ 用自带 alpha；**没有**（JPG/BMP）→ **用图片右半当 alpha 通道**，宽度减半，`alpha = 255 − 掩码红通道`，且掩码按**每格**分别取 |
| `leftup`（`:l`，默认） | 左上角像素的颜色作透明键，其余完全不透明 |
| `topright`（`:r`） | 同上，取右上角像素 |
| `copy`（`:c`） | 完全不透明，连自带 alpha 都不要 |
| `mask`（`:m遮罩.bmp`） | 用另一个文件当遮罩（红通道取反，横向平铺） |
| `direct`（`:#RRGGBB`） | 指定颜色作透明键 |

**实测影响**：Ever17 的选项按钮 `esystem/csel_btn.jpg` 就是这种图——左半是按钮画面、
右半是遮罩（黑=不透明、白=透明），中间那条绿色因此被遮掉了。修正前绿条直接显示在按钮上；
修正后与参照引擎一致。

**验证方式**（纯脚本判定）：排版校对新增 `--corpus alpha` 语料（半透明文本框 + `transmode alpha`），
与参照引擎逐项比：几何全同，对齐缩放后像素差 0.08%。

### D2 的验证方式

给参照工程加了一套"**断点正好压在标点上**"的语料：每行 32 字，第 32 个是"，"（行首禁则），
第 64 个是「"（行尾禁则）。然后用 OnscripterYuri 的 web 构建渲染同一份脚本，逐项比几何：

| 项 | 参照 | 我们 | 差 |
|---|---|---|---|
| 行数 | 4 | 4 | 0 |
| 首行上沿 y | 602.0 | 602.0 | 0.0 |
| 行距 | 35.7 | 35.7 | 0.0 |
| 字高 | 21.5 | 21.5 | 0.0 |
| 左边距 x0 | 301.0 | 301.0 | 0.0 |
| 右端 x1 | 1130.0 | 1130.0 | 0.0 |

像素差异：对齐缩放后明显差异 0.28%（底噪）。

**顺带查清的分页规则**：引擎**不会**按文本框高度自动切页——一段文字折出几行就画几行，
超出框高的部分直接溢出到框外（参照引擎在 3 行的框里画了 4 行，第 4 行压到画面底部）。
翻页只发生在显式点击点（`\`、`@`）上。我们原来按 `num_y` 切片，会比引擎多一次点击，
已改成与引擎一致。校对语料分四套：`base` / `kinsoku` / `page` / `alpha`。

## E. 可移植性（**已完成**）

验证靶子：`[KID]Ever17.7z`（原始发布版，只有 `nscript.dat` + `arc/arc1/arc2.nsa`）与
`ever17/`（同一移植组的解包版）。两者 `nscript.dat` 的 MD5 完全一致，可当同源对照。

| # | 任务 | 状态 | 实现 / 验证 |
|---|---|---|---|
| E1 | 脚本首行配置 | ✅ | `scriptfile.parse_config_header`：`;$S<w>,<h>G<n>`、`;mode800/400/320`、`value<n>`、`v<n>`、`l<n>`，语义照抄 `ScriptHandler::readConfiguration` |
| E2 | UTF-8 / 多分片脚本 | ✅ | 探测补上"纯假名"分支（原来只认汉字，纯假名 UTF-8 会被判成 GBK）；`0.txt` + `1..99.txt` / `00.txt` + `01..99.txt` 自动拼接 |
| E3 | `.nsa` 归档直读 | ✅ | `archive.py`：NSA/SAR 索引，**自动判字节序**（用"offset 连续 + 数据尾对齐文件尾"两条校验），解压支持 无压缩 / LZSS / SPB / NBZ；用 `mmap` 不整包读进内存 |
| E4 | `nscript.dat` 解扰 | ✅ | `^0x84`；另支持 `nscr_sec.dat` 的 5 字节 magic 循环异或；`nscript.___` 需要 EXE key table，给出可读错误 |
| E5 | Shift-JIS | ✅ | 合成 SJIS 脚本实测判成 `cp932`（真实日文原版素材仍缺） |
| E6 | 字体回退 | ✅ | 优先级：显式指定 → `ONSMCP_FONT` → 游戏 `default.ttf` → 系统字体（msyh/simhei/simsun/PingFang/Noto/文泉驿）；用"不同汉字点阵是否相同"判断是否豆腐块 |
| E7 | 分辨率 | ✅ | 默认取脚本头（Ever17 800×600、万华镜 1280×720），`start(width=,height=)` 显式覆盖 |
| E8 | 多会话 | ✅ | `start(session="名字")`；`sessions()` / `close()`；每个工具都可传 `session`，不传用最近一次 start 的 |

**关键实测**

| 项目 | 结果 |
|---|---|
| Ever17 从标题进正文 | ✅ 800×600、GBK、自带字体，背景/立绘/文本框/台词全部正确 |
| 打包版 vs 解包版渲染 | ✅ 40 步后 `ImageChops.difference().getbbox() is None` —— **逐像素完全相同** |
| 归档解压正确性 | ✅ arc2 的 LZSS/SPB 解出来与解包版**字节一致**（SPB 只差 BMP 行尾填充字节，引擎本身也是未初始化值） |
| 归档索引 | arc.nsa 1424 + arc1.nsa 14996 + arc2.nsa 269 = 16689 条，mmap 下 RSS 只涨 16 MB |
| 踩到的解析坑 | NSA 是**大端**（`readShort/readLong` 大端），但也有小端包 → 必须自动判；`;mode800` 不是注释而是配置行 |

**顺带修的通用 bug**：`%1` / `%101` / `$0` 这类**数字变量名**原来分词失败（要求字母开头），
Ever17 全篇依赖它，标题菜单点不动的根因就是这个。

**仍未覆盖**：`nscript.___`（要 EXE 里的 key table）、`nbz` 只有代码没有实测素材、
真实日文原版（SJIS + 800×600 + 竖排？）没跑过。

---

## F. 工程化与接入（**已完成**）

| # | 任务 | 状态 | 实现 |
|---|---|---|---|
| F1 | 打包与入口 | ✅ | `pyproject.toml`（console script `ons-mcp`）+ `src/onsmcp/__main__.py`；`pip install -e .` 后 `python -m onsmcp` 与 `ons-mcp` 皆可；`run_mcp.py` 保留兼容 |
| F2 | 日志分流 | ✅ | `onsmcp/log.py`，`_StderrHandler` 每次 emit 时重新取 `sys.stderr`（避免宿主替换流后写错地方）；`ONSMCP_LOG=debug/info/warning/error/silent` |
| F3 | 错误处理 | ✅ | `_safe` 装饰器包住全部 11 个工具，返回 `{"error": {type, message, hint}}`；常见异常带中文 hint；堆栈只在 debug 级别打 |
| F4 | 超时/步数保护 | ✅ | `Interpreter.deadline` 墙钟预算（每 256 步查一次表），`Session._run` 统一设预算；超时写 `stop_reason` 并进 `state().stopped`；步数上限同样记录 |
| F5 | 测试体系 | ✅ | `tools/check_all.py`：11 项、独立进程与超时、`--fast`/`--only`、失败非 0 退出、结果写 `docs/checks.json` |
| F6 | README 收尾 | ✅ | 安装/三种接入写法/环境变量/agent 典型一轮/故障排查表/目录说明 |
| F7 | 版本与变更记录 | ✅ | `CHANGELOG.md`（0.1.0 → 0.7.0），`__version__` 同步 |

**实测**

```
$ python tools/check_all.py
  单元测试      …  OK     2.7s
  协议测试      …  OK     1.7s
  端到端       …  OK     1.1s
  选项分支      …  OK     2.6s
  游戏内菜单     …  OK     1.5s
  可移植性      …  OK     6.5s
  排版校对      …  OK     7.7s
  禁则校对      …  OK     5.6s
  透明校对      …  OK     7.2s
  长跑        …  OK     4.6s
  MCP 试玩      …  OK     2.4s
通过 11/11 项，总耗时 43.6s
```

超时保护实测：`inc %i` + `if %i<99999999 goto` 的死循环，预算 50 ms，
实际 52 ms 停在 `timeout:3328:if`，`state().stopped` 可读。
错误返回实测：未 `start` → `ToolError` + hint；坏目录 → `FileNotFoundError` + hint。

## G. agent 体验（MCP 工具形状）（**G1/G3/G5 完成；G2/G4 已移除**）

| # | 任务 | 状态 | 实现 |
|---|---|---|---|
| G1 | `text()` 带上下文 | ✅ | `text(history=N)` 返回最近 N 句台词的滑动窗口（解释器逐页记录 `history`，上限 200 条）；`text()` 仍只给当前页 |
| G2 | `script_trace` 更可读 | ❌ **已移除** | 用户决定：语义未定稿前**直接删掉这个工具**（原计划是默认关闭）。session 层的 `trace()` 保留给内部工具（`run_scene.py`） |
| G3 | `screenshot` 返回方式 | ✅ | `format='image'`（默认）返回 MCP 图片块，客户端与视觉模型可直接看；`'base64'` 返回 base64 文本 JSON。**两种模式都不写文件**（`path` 模式已移除） |
| G4 | `state()` 语义化 | ❌ **已移除** | 用户决定：语义未定稿前**直接删掉 `state` 工具**。`start`/`click` 的返回值本身就带完整状态（waiting/label/line/unsupported/memory…），agent 不需要单独的 state 调用 |
| G5 | 工具级错误信息 | ✅ | `choices()` 在非选项界面返回 `{choices: [], hint}`；`choose()` 越界时补 `hint`，hint 按当前状态给出具体下一步 |

**`trace` 的 reset 语义**（原来含糊，现已明确）：
- `reset=True`（默认）→ 只给"上次查询之后"的新内容
- `reset=False` → 给从会话开始（define 区之后）到现在的**全部**内容

**实现过程中改掉的两个真 bug**：
1. `script_trace` 原来返回裸数组，agent 只能逐行读；改成 `{lines, summary}` 后协议测试的断言同步更新。
2. `trace` 的起点标记只有一个，导致 `reset=False` 拿不到 start 期间的执行。
   拆成 `_trace_origin`（会话起点，排除 define 区）和 `_trace_mark`（上次 reset 起点）两个。

**背景名为什么不能用 trace 推**：这个游戏的背景是宏 `bg01` 设的，trace 里只有一条 `bg01`，
看不到真实文件名。改为在解释器里维护 `bg_log`（每次换背景后的文件名），摘要直接用它。

**新增单测 6 项**（历史记录、滑动窗口、语义字段、选项态识别、trace 摘要、hint），
单测 56 → **62 项**（其后又删了 G2/G4 相关用例，现为 **61 项**）。

### G2/G4 已移除（2026-10-23 晚，最终版）

用户先要求"在明确之前先不启用"，随后决定**直接去掉** `state` 与 `script_trace` 两个工具，
并去掉 `start` 的 `agent_hints` 参数。

**最终状态**：
- MCP 工具从 13 个减到 **11 个**：`start` / `sessions` / `close` / `text` / `screenshot` /
  `click` / `choices` / `choose` / `buttons` / `save` / `load`
- `state` 的信息**没有丢**：`start` 与 `click` 的返回值本来就是完整的状态字典
  （waiting / label / line / pc_label / pc_line / in_hook / stopped / page /
  has_more_pages / unsupported / memory），agent 每次操作后自然拿到
- `script_trace` 的逐行脚本能力保留在 session 层（`Session.trace()`），
  供 `tools/run_scene.py` 等内部工具使用，不再暴露给 agent

**一并清理的代码**（原本只为 G2/G4 服务）：
- `Session._hint_fields()` / `Session._summarize()` / `Session._scene_id()`
- `Session.ENGINE_LABELS` / `Session._BG_CMDS`
- `Interpreter.bg_log` / `Script.line_label`
- `GameSession.agent_hints` 与 `ONSMCP_AGENT_HINTS` 环境变量

**踩到的坑**：删 `_summarize()` 时用字符串切片按"下一个 `def`"找边界，
结果把 `screenshot` / `_button_by_no` / `choices` / `choose` / `buttons`
五个方法一起切掉了 —— 单测立刻报 `AttributeError: 'GameSession' object has no
attribute 'choices'`，按原实现补回后恢复。教训：批量删代码要用 AST 或精确的
锚点字符串，别用"找下一个 def"这种启发式。

### G2/G4 默认关闭（2026-10-23 晚，中间态）

用户指出"G2 和 G4 的功能和实现都太模糊，在明确之前先不启用这两个工具"。

**处置**：
- 加开关 `GameSession.agent_hints`（默认 `False`），`start(agent_hints=True)` 或
  环境变量 `ONSMCP_AGENT_HINTS=1` 打开
- 关闭时：`state()` 不含五个语义字段；`script_trace()` 只返回 `{lines}`，没有 `summary`
- 实现全部保留（`_hint_fields()` / `_summarize()`），随时可调
- 新增 `docs/agent-api-semantics.md`：逐字段写明含义、取值来源、**已知歧义**，
  并列出 7 个待拍板问题（Q1~Q7），供逐条确认
  （该文档随 G2/G4 一并删除，已不存在）

**为什么 `scene` 最可疑**：这两个游戏里很多"剧情段"**在脚本里没有对应标签**
（`w08_04` 只是一段连续文本，没有 `*w08_04`），所以只能从背景文件名正则提取——
而那个正则 `([A-Za-z_]+\d+_\d+)` 是照着这两款游戏硬凑的（Ever17 的背景是
`background/1.png`，提不出场景号）。它实际含义是"背景资源名里的编号"，
不是"剧情场景"，建议改名为 `bg_id`。

### 演示时发现并修掉的问题（+2 项单测）

实际跑一遍 agent 流程后发现三处返回不准：

1. **`state()` 报的位置是错的**：`story_line` 只在执行文本行时更新，所以在选项界面
   （PC 已在 `*customsel` 第 25957 行）它仍报上一句台词的行号 8309。
   → 改成**只有 PC 停在 textgosub 钩子里时才用 `story_line`**，其余一律用 PC 真实位置。
2. **`summary.labels` 里只有宏名**（`chara01`），因为 `label_of` 记的是"最近的 `*label`"，
   而这段文本位于宏体内部。→ 拆成 `scenes`（剧情标签）/ `macros`（宏标签）/ `labels`（全部），
   并排除引擎内置界面标签（`customsel`、`text_btn`、`save_btn` …）。
3. **"场景"没有脚本级标签支撑**：万华镜的 `w08_04` 只是一段连续文本，脚本里没有 `*w08_04`。
   → `state().scene` 改为**从背景文件名提取场景号**（`ev/w08_04_1_002.png` → `w08_04`），
   这是两个游戏里都可靠的信息源（选项标签的前缀模式并不通用，Ever17 的 141 个选项几乎都没前缀）。

---

## 命令覆盖收尾（原 H 节，已并入 C 组与 I 节）

| 命令 | 次数 | 处理方式 |
|---|---|---|
| `split` | 10 | ✅ C 组已实现（支持 `$%var` 动态变量名） |
| `mid` | 2 | ✅ C 组已实现 |
| `strsp` | 2 | ✅ C 组已实现（生成文字精灵） |
| `char1` | 2 | ⚠️ 脚本笔误，引擎 LUT 里没有此命令，保持降级并记日志 |
| `overlap_long` | 1 | ⚠️ 同上 |

no-op 清单里 `bar`/`barclear`/`cellcheckspbtn`/`checkpage` 属于"以后要用"；
`cell` 已在 0.11.0 实现。音频相关命令 0.9.0 起全部改成记账；剩视频/抖动/转场按既定决策不做。

## 建议顺序

```
A 内存  →  B 长跑验证  →  F 工程化  →  C 游戏内 UI  →  E 可移植性
        →  I 命令补齐  →  D 渲染保真（D2 已做）  →  G agent 体验
```

A、B、C、E、F、G、I 都已完成。剩下 D 的其余项（ruby / hover / monocro / windowback）：
这些命令在两款实测游戏里的使用次数分别是 0~2 次，属于"按需再做"。

**下一步建议**：D 组剩余项按需；更值得做的是**扩大实测样本**——
目前只验过 2 个游戏（1 个中文移植 + 1 个日文移植），可以再找一个未解包的
第三款 ONS 游戏来验证 `archive.py` / `scriptfile.py` 的覆盖度。


## I. 命令补齐（Ever17 带出来的）（**已完成**）

拿 Ever17 当第二个靶子后，发现 18 条命令我们不认。查引擎源码逐条补齐：

| 命令 | 语义 | 说明 |
|---|---|---|
| `ld l\|c\|r,"file"` | 载入立绘 | 位置自动算：x = 画面宽×(no+1)/4 − 图宽/2，y = 底线 − 图高（`ONScripter_command.cpp` `ldCommand`） |
| `cl l\|c\|r\|a` | 清立绘 | 引擎的 tachi 是独立于 `lsp` 精灵的一套（`tachi_info[3]`） |
| `blt dx,dy,dw,dh,sx,sy,sw,sh` | 把 `btndef` 图的一块贴到画面 | 图源是 `btndef` 载入的位图 |
| `bgcopy` | 把当前画面冻成背景 | 引擎是"存进累积缓冲再赋给 bg"，我们直接合成后烘进背景 |
| `ofscpy` / `repaint` | 累积缓冲 / 强制重绘 | 我们按需合成，no-op |
| `cselbtn csel_no,btn_no,x,y` | 把第 N 个选项画成文字按钮 | 引擎用 `sentence_font` 现画一句可点文字；我们生成文字精灵 + 矩形按钮，**画在按钮层**（引擎里 ButtonLink 最后画，压在所有层之上） |
| `selectbtnwait` | 同 `btnwait` | 引擎 LUT 里就是同一个 handler |
| `reset` | 回标题 | 清画面、跳 `*start` |
| `end` | 结束游戏 | |
| `getcursorpos2` | 取鼠标坐标 | 记录最近一次点击位置 |
| `systemcall save/load/rmenu` | 调出引擎内置菜单 | 那是引擎状态机画的 UI，脚本画不出来；agent 用 MCP 的 `save`/`load` 更直接，这里只记一笔不阻断 |
| `underline` | 立绘落底线 | |
| `savename` / `rmode` / `filelog` / `savenumber` / `mpegplay` / `logsp2` | 配置或无关 | 列入 no-op（`mov10` 已在 0.8.0 实现，见 J 组） |

**顺带修掉的四处语义偏差**（都是"换游戏就跑不起来"级别）：

1. **`len` 是字节数不是字数**（引擎用 `strlen`，GBK 汉字 2 字节）。Ever17 用它算选项居中，
   按字数算会整体偏右 7.5px/字。
2. **`csp -1` 是清空全部精灵**（引擎 `no == -1` 遍历所有 sprite），我们原来只删 id=-1。
3. **`btndef` 的参数要能吃引号串**（`btndef "background\2.png"`），原来只认裸词。
4. **数字变量名**（`%1` / `%101` / `$0`）原来分词失败，见 E 组。

**结果**：Ever17 用到的命令**全部可处理**（`tools/missing_commands.py` 报 0）；`dwaveloop`
在 0.9.0 之后也归入音频记账。万华镜只剩 2 处脚本笔误（`char1` / `overlap_long`，引擎同样不认）。


---

## J. 变量槽位与全局变量（**已完成**，0.8.0）

之前变量是"按名字存"的字典，`numalias foo,5` 只是往字典里塞了个 `foo=5`。
这在两款游戏上碰巧能跑，但和引擎的模型不是一回事。本轮按 `ONScripter-Jh` 源码改成槽位模型。

| # | 任务 | 状态 | 依据 / 实现 |
|---|---|---|---|
| J1 | 槽位模型 | ✅ | 每槽同时存 num/str（`VariableData`）；`%5` 与 `$5` 同槽 |
| J2 | numalias 映射 | ✅ | `parseInt` 命中别名取 `getVariableData(no).num`；重复定义以第一次为准（引擎头插链表） |
| J3 | **裸名字 = 槽号常量** | ✅ | `parseInt` 的 `ret = alias_no; type = VAR_INT\|VAR_CONST` —— 脚本拿它当具名常量 |
| J4 | 未定义名字 → 0 号槽 | ✅ | `parseInt` 未命中分支（注释 "assume 0"）；我们额外记 `undefined_vars` |
| J5 | stralias 常量表 | ✅ | `parseStr` 只对裸名字查 str alias；`$名字` 查 numalias |
| J6 | 越界槽位 | ✅ | 引擎 `extended_variable_data` 动态扩容；我们用 dict 兜住 |
| J7 | globalon | ✅ | 从 no-op 改成实现；`global_border` 来自脚本首行 `;G<n>` / `;value<n>` |
| J8 | gloval 持久化 | ✅ | 全局槽单独写 `gloval.sav`（0.12.0 起与引擎同名同格式；早先是自有的 `.onsmcp_global.json`），存档只含一般变量 |
| J9 | 读档不回滚全局 | ✅ | `readVariables(0, global_variable_border)` 只恢复一般变量 |
| J10 | mov2..mov10 | ✅ | `movCommand` 的 offset 语义：写 `槽号+i`；Ever17 有 1 处 `mov10` |

**实测**：万华镜 border 1500 / 424 别名 / 未定义 0；Ever17 border 500 / 151 别名 / 未定义 0。
两款都用 `globalon`（Ever17 在第 9 行，带缩进，早先统计漏了）。

**踩坑**：改完游戏内存档界面死循环 —— `for %sub1=0 to save_num` 里的 `save_num` 是裸名字，
错当成"槽值"读成 0 后，循环退出时 `%sub1` 恰好等于 1，撞上 `if %sub1=1 goto *save_drag_data_loop`。

### 存档后续（未做，按需）

| 项 | 现状 | 说明 |
|---|---|---|
| 原子写 | ✅ 0.11.0 | 原版 `.dat` 与 `gloval.sav` 都走 `tmp` + `os.replace` |
| slot 校验 | ✅ 0.13.0 | MCP 入口限 `0..999`，越界给 `ToolError` + hint；**脚本里的 `savegame` 不校验**（引擎也不校验） |
| `save` 返回形状 | ✅ 0.14.0 | `save` 返回 `{slot, path, size}`（只讲写盘）；`load` 返回状态字典 + `slot`，两边都有槽位 |
| 存档目录可配 | ✅ 0.13.0 | `ONSMCP_SAVE_DIR`（对应引擎 `--save-dir`）+ 显式参数；只读时回落 `%LOCALAPPDATA%/onsmcp/<游戏名>` |
| 原版 `save<N>.dat` 读写 | ✅ 0.11.0 | 见 M 组：字节级往返 + 真引擎读档验证都过了 |

---

## K. 存档的画面与音频状态（**已完成**，0.9.0）

目标：**读档后 agent 看到的世界与存档那一刻一致**。原版档互通在本轮之后另立 M 组；
音频只记账、不播放。

| # | 任务 | 状态 | 说明 |
|---|---|---|---|
| K1 | blt 流水重放 | ✅ | 存「图源 + 8 个参数」，读档按顺序重放；不存像素 |
| K2 | bgcopy 烘焙 | ✅ | 存 `bg_source` + `bg_baked`，读档先重建 overlay 再烘焙（修掉"读档背景变黑"） |
| K3 | 精灵帧号 | ✅ | `Sprite.cell` 进存档；`build_sprite_image(..., cell=)` 能取任意一格 |
| K4 | 音频记账 | ✅ | 26 条音频命令从 no-op 改成只更新状态（音乐/音效/循环BGM/CD/语音/音量） |
| K5 | 音频存档字段 | ✅ | 与 `saveSaveFile2` 对齐：music(+loop+mp3save) / midi / wave(+loop) / loop_bgm[2] / cd_track(+loop) |
| K6 | 语音与音量不入档 | ✅ | 引擎本来就不存（语音走独立声道、音量在 envdata），我们照做 |

**实测**：两款游戏 save 前 / load 后截图**逐字节相同**；Ever17 开局就是 `bgcopy`，属本次修掉的真问题；
`unsupported` 里已无音频命令。

**注意两个引擎怪点**（已在代码注释里写明）：`mp3` 的 `mp3save_flag` 是 false，所以它的曲目
**不随存档恢复**；`dwave` 语音与音量**根本不进存档**。

### 明确不做 / 待定

| 项 | 结论 |
|---|---|
| 音频解码与播放 | **不做**。agent 听不到，存档只需要"在放什么"这个状态 |
| cell 动画驱动（定时器推进帧号） | **待定**。属于渲染特性；存档侧已准备好帧号字段 |
| 视频 / 转场 | 不做（既定决策） |
| 与原版 `save<N>.dat` 互通 | **已做（0.11.0）**，见 M 组 |

---

## L. 数组（`dim`）与解析对齐（**已完成**，0.10.0）

目标：脚本层面凡是引擎做了而我们没做的，补上；凡是做得不一样的，改成一样。

### L1 `dim` / 数组变量

| # | 项 | 依据 | 实现 |
|---|---|---|---|
| 1 | 声明语法 | `dimCommand` → `declareDim` → `parseArray` | `dim ?name[e1][e2]`；名字走 `numalias` 取槽号，也可以是纯数字（Ever17 的 `?0`） |
| 2 | **元素数 = 声明值 + 1** | `av->dim[i] = array.dim[i]+1` | `dim ?a[100]` 分配 101 个；合法下标 0..100 |
| 3 | 只有 int | `ArrayVariable::data` 是 `int*` | 无字符串数组；`dim $name[...]` 同样落到 int 数组 |
| 4 | 线性下标 | `getArrayPtr` 的 `dim = dim*av->dim[i] + array.dim[i]` | 行主序 |
| 5 | 越界 | 引擎 `errorAndExit`（且不查负下标） | 不崩：返回 0 / 写入失败，记 `array_oob` |
| 6 | `?a[i]` 读写 | `parseInt` 的 VAR_ARRAY 分支、`setInt` 的 offset | 支持；下标是完整表达式 |
| 7 | **`%?a[i]`** | `parseInt` 递归：先取元素值，再当槽号 | Ever17 用它做十进制拆位：`mov %?0[1],%0` |
| 8 | 文本行插值 | `addIntVariable` 认 `?` | `「数值 ?a[1]」` 会替换 |
| 9 | `movN` 到数组 | `setInt(pushed, val, i++)` | `mov3 ?a[1],5,6,7` 写线性下标 1,2,3 |
| 10 | 存档 | `writeArrayVariable`：按声明顺序写裸 int，**无维度信息** | 我们额外存 name/dims 便于自检；读档形状仍以脚本 dim 为准 |

**实证**：`exports/` 那份真存档的数组段是 404 字节 = **101 个 int**，与 `dim ?0[100]` 的 +1 语义吻合。
（上一轮我用 100 解析"成功"是假象：脚本在 ruby 段多读 4 字节，恰好与数组少读 4 字节抵消。）

### L2 表达式与解析

| 项 | 之前 | 现在 |
|---|---|---|
| `(1+2)*3` | 括号落成字符串字面量，整条表达式算出 0 | 递归求值 = 9 |
| `10 mod 3` | 不认识 `mod`，得 0 | 与 `*` `/` 同级 = 1 |
| `movl` | 只支持 mov2..mov10 | 引擎的"无限个"（参数耗尽收尾） |
| `getmousepos` | no-op，`%cursory` 恒为 0 | 写最近一次点击坐标 |
| `?a[i]` 在字符串参数里 | 被当变量读成空 | 按引擎原样输出 `?a[i]` 字面 |

**`getmousepos` 的连锁影响**：万华镜的存档格号是
`(%savepos + %cursory - save_data_y)/save_height + 1`，以前 `%cursory` 恒 0、
括号又不支持，结果恒为 0 —— 点任何格子都写同一槽。现在按点击位置算，
测试因此从"固定 slot 0"改成"校验写盘的那一份"。

### 曾经不一致、现已对齐（0.15.0）

| 项 | 引擎行为 | 之前 | 现在 |
|---|---|---|---|
| 未定义名字后的指针回退 | `parseInt` 未命中 → `*buf = buf_start`，同一条命令的下一个参数会重读这个名字 | 消费掉 token，返回 0 | **不推进指针**，返回 0，并记 `undefined_vars` |
| 数值表达式里的引号串 | 见到 `"` → `VAR_NONE`，返回 0 且指针不动 | `int("123")` → 123 | **返回 0**，且不消费（后面的 `read_str` 还能取到） |
| `movN` / `movl` 的续读条件 | `END_COMMA`：上一个值后面没逗号就停 | 只看 token 是否读完 | **按逗号收尾**（`mov3 %a,7 8` 只写 7） |
| `getcursorpos` | `sentence_font` 光标 = 下一个字符的落点 | no-op | **已实现**：实测"文本显示完引擎自己换行"，所以是 `(top_x, top_y + 行数 × 行距)` |

**`movN`/`movl` 那条是顺带挖出来的**：对齐"未定义名字回退"时才发现，若指针不推进，
`movl` 的 `for i in range(1<<30)` + `a.eof()` 会变成 10 亿次写入的死循环 ——
必须先把续读条件改成引擎的逗号语义，两件事得一起做。

**`getcursorpos` 的实测过程**（真引擎探针，`setwindow 100,100,20,3`、行距 36）：

| 场景 | 真引擎 | 我们 |
|---|---|---|
| 一行文本之后 | `X=100 Y=136` | 100 / 136 ✅ |
| 25 字折成两行之后 | `X=100 Y=172` | 100 / 172 ✅ |
| 还没画任何文本 | `X=100 Y=100` | 100 / 100 ✅ |

⚠️ 探针脚本踩的坑：`RESULTX=...` 被引擎当成命令（`command [resultx] is not supported yet!!`）
直接 `***** End *****`、画面全黑 —— 文本行必须以中文或引号开头。这类坑统一记在
**`docs/quirks.md`**（引擎怪点 + 我们的已知偏差 + 排查路径），换新游戏时先看它。

---|---|---|---|---|
| 未定义名字后的读取位置 | `parseInt` 扫完名字没命中 → `current_variable.type = VAR_NONE; *buf = buf_start;` 把指针**退回名字开头**，于是同一条命令的下一个参数会把这个名字当字符串/标签再读一次 | 分词在 `Script` 构建时一次完成，名字已消费，`read_int` 返回 0 并记 `state.undefined` | 只在脚本引用未定义别名时。两款游戏 `undefined_vars` 均为 0 → **从未触发** | 不修：要复刻得让读取未命中的 `T_IDENT` 时不推进指针，还要防调用方 while 循环反复读同一 token 造成死循环；收益仅限"写错别名的脚本" |
| 数值表达式里的引号串 | 遇到 `"` 时前缀扫描长度为 0 → `VAR_NONE` + 返回 0，指针不动 | `int("123")` → 123（非数字串才 0） | 把字符串当数字用；正常写法是 `atoi $s` | 不修：我们更宽容；改成引擎那样只会让某些脚本从"能用"变成静默得 0 |
| `getcursorpos` | `sentence_font` 的当前光标：**下一个字符的落点**（算行尾换行 + `indent_offset`） | no-op（`getcursorpos2` 已实现，是另一个命令） | 万华镜 **1 次**，在 `*text_btn`：`getcursorpos %textlastx,%textlasty`。这两个名字是槽 1/2，而它们**全程只写不读**，`%1`/`%2` 在脚本里出现 **0 次** → 对这款游戏是**纯死写** | 暂不做：本作收益为 0。真要做时，`render.wrap` 已经在按字累加宽度（用来判换行），把末行宽度和行号带出来即可，约 20~30 行 + 逐像素校对 |

---

## M. 原版二进制存档 `save<N>.dat`（**读写都已完成**，0.11.0）

目标：把我们的状态写成**原版引擎能读**的二进制存档，反向也能读。这在 0.9.0 时判过"不做"，
理由是"没人机交接场景"；现在按"最终要和原版完全一致"的目标改判为**做**。

### M1 读写器（`src/onsmcp/savefile_bin.py`）

| # | 项 | 依据 | 实现 |
|---|---|---|---|
| M1 | 文件布局 | `saveSaveFile2` / `loadSaveFile2` | 逐段照抄：字体/窗口/cursor → bg/立绘 → 1000 sprite → 变量 → nest → monocro/音频 → 100 bar/prnum → btndef → 数组 → loopbgm/ruby → 256 sprite2 → 页面/tag → 行号 |
| M2 | 序列化原语 | `writeInt/writeStr/writeChar` | 小端 4 字节 / 原样字节+NUL（空串也是 1 字节 NUL）/ 1 字节 |
| M3 | 空槽默认值 | `AnimationInfo::reset()` | sprite 空槽 `x=y=0, visible=0, cell=0, trans=-1`；bar 空槽 7 int、prnum 空槽 6 int（两种分支都 28/24 字节） |
| M4 | 尾部固定值 | 205/206/207/208 版本标记 | 7 int（第 3 个是 1）+ 1 char + 5 int（`0, w/4, w/2, 3w/4, underline`） |
| M5 | 版本闸门 | `loadSaveFile2` | 只接受 `ONS` + 2.8，其它给 `EngineSaveError` |

**字节级往返是验收标准**：`parse → build` 必须和原文件**一字节不差**。

| 样本 | 大小 | 结果 |
|---|---|---|
| `tests/fixtures/engine_save0.dat`（探测工程） | 42,572 | ✅ 完全一致 |
| `exports/ever17_web_save/save1.dat`（Ever17 真剧情，含 101 元素数组） | 38,666 | ✅ 完全一致 |

这一关顺带暴露并纠正了 0.10.0 遗留的两处误判（数组实际 101 元素；`ruby` 段后没有多余的 int）。

### M2 续跑点：`cur_line` 不是 1-based，而且**滞后一行**

引擎写的是 `current_label_info.start_line + current_line`，其中：

* `current_line` 是**标签内行偏移**，主循环里递增；
* 存档命令执行时它**还没递增到当前行**，所以存下来的是"上一条执行完的行"；
* 值是 **0-based**。

两份真档互相印证：

| 样本 | 存档位置 | 引擎存的值 | 印证 |
|---|---|---|---|
| 探测工程 | `savegame 0`（0-based 11） | `cur_line=10` | 上一行是 `存档点。` |
| Ever17 | 在台词行按存档 | `cur_line=1332` | 0-based 1332 = 台词前一行，1333 才是台词 |

我们原本写的是 `instrs[pc].line_no`（1-based、不滞后），会整体偏移 1~2 行 —— 已在
`to_engine_save` 里改成 `line_no - 2`，并在读档时用 `cur_line + 1` 反查。

`cur_stmt` 是"从**上一行行首**数到当前语句的裸 `':'` 个数"（引号内的也算，因为引擎是
逐字节扫 `*buf == ':'`），所以要把上一行的冒号数也加上。

### M3 状态映射

`GameSession.to_engine_save()` / `save_engine(slot)` / `load_engine_bytes(data)`：

| 项 | 映射 |
|---|---|
| 变量 | 只写 `< global_border` 的槽；`build` 补满 border 个（空槽 `0 + ""`） |
| 数组 | 按声明顺序写裸 int（引擎那边没有维度信息） |
| 背景 | `bg_source`（`bgcopy` 之后也是真实来源，不会写 `*bgcpy`） |
| 精灵 | `tag → 文件名`、`alpha → trans`（255 以上写 -1）、`cell` 原样 |
| 页面 | 用台词历史填，最多 16 页（`MAX_PAGE_LIST`） |
| 续跑 | `cur_line = line_no - 2`，`cur_stmt` 按跨行冒号数 |
| nest 栈 | 用**行起始字节偏移**近似引擎的 `getOffset`（纯行首存档时栈是空的） |

### M4 真引擎验证（决定性证据）

用 OnscripterYuri 的 web 构建 + 无头 Edge/CDP 做的闭环：

```
探测工程跑一次 → 引擎写出 save0.dat（localvar=0）
   → 我们 parse、把 localvar 改成 777、build
   → 通过 CDP 直接写 IndexedDB 的 FILE_DATA（IDBFS 的存储格式）
   → Page.reload → 游戏执行 loadgame 0
   → 引擎读档 → 跳回 «存档点。» → 继续执行到 savegame 0
   → 导出：localvar = 777 ✅
```

第二次换成"**我们会话生成的档**"（`to_engine_save` → `build`，localvar=888）：
引擎读档后重存的档 `localvar = 888`、`cur_line = 8`，与我们的完全一致 ✅

结论：**原版引擎能读我们写的档，变量/续跑点都对，并且能继续往下跑**。

### 仍然不一样（不影响读档，但画面会略有差别）

| 项 | 现状 | 为什么 |
|---|---|---|
| `pages` / `tags` | 有内容时与引擎不同（我们用台词历史） | 引擎的 Page 是 `pretextgosub` 产物；我们没实现 pretextgosub |
| `top_xy` / `num_xy` / `pitch` | 用我们 `WindowConfig` 的值 | 脚本没调 `setwindow` 时，引擎内部默认值与我们的默认值不同 |
| bar / prnum / sprite2 / monocro / ruby | 写引擎默认值 | 这些子系统我们没建模，写不了真实值 |
| nest 栈的偏移 | 行起始偏移 | 引擎存的是语句级字节偏移；非行首存档时差几条语句 |

### 还没做

| 项 | 说明 |
|---|---|
| ~~MCP 工具面暴露~~ | ✅ 0.12.0：`save`/`load` 直接就是原版档，不需要额外参数 |
| ~~原版档 → 我们的 JSON 迁移~~ | ✅ 0.12.0：JSON 已整体移除，不存在两套格式 |
| ~~`getcursorpos`~~ | ✅ 0.15.0 已实现（实测语义：下一行行首），详见 L2 末尾 |

---

## N. 去掉自有 JSON，存档只留原版格式（**已完成**，0.12.0）

### 为什么之前有两套

0.8.0 把变量改成槽位模型时，存档还带着"按钮表 / 调用栈剩余语句 / 台词历史 / blt 流水"
这些引擎存档里没有的东西。当时的理由是"读档后要立刻恢复到等待态，不能靠重跑"。

### 为什么现在能删掉

把引擎的 gosub 挖到底之后发现：**引擎从来不存按钮，它相信重跑**。

```cpp
void ScriptParser::gosubReal(const char *label, char *next_script, ...) {
    last_nest_info->next_script = next_script;   // 只压返回地址
    setCurrentLabel(label);                      // current_line 被重设成子程序行
}
```

再配合"`cur_line` 滞后一行"，整套机制就通了：读档从存档行的**前一行**开始重跑，
那批 `btndef`/`spbtn`/`btn` 自然重新执行，按钮自己回来。

我们把按钮表塞进 JSON，等于绕过这个机制 —— 看起来"读档更快"，实际是和引擎分道扬镳。

### 改了什么

| 项 | 0.11.0 | 0.12.0 |
|---|---|---|
| 存档文件 | `.onsmcp_save_N.json` + `saveN.dat` | **只有 `saveN.dat`** |
| 全局变量 | `.onsmcp_global.json` | **`gloval.sav`**（与引擎同名同格式） |
| 读档后 | 恢复到等待态，按钮表从 JSON 拿 | 清空按钮/选项表，`run()` 继续跑到下一个等待点 |
| 删掉的字段 | 43 个 | 0（都不需要了） |

删掉的 43 个字段里，绝大多数本来就不该存：

| 类别 | 字段 |
|---|---|
| 原版档已有 | `variables` `strings` `sprites` `tachi` `bg_name` `audio` `btndef_image` `underline` `page` `pc` |
| define 段重跑就有 | `aliases` `str_aliases` `global_border` `variable_range` `global_on` |
| 脚本重跑就有 | `buttons` `select_links` `btnwait_var` `exbtn_default_ctl` `ui_sprites` `trans_mode` `pending_pages` |
| 引擎根本不存 | `waiting` `last_cursor` `last_button` `humanz` `tachi_visible` `text_on` |
| 超集能力（主动放弃） | `bg_ops` / `bg_baked`（blt 合成流水）、`stack.cont`（行内剩余语句） |

### 代价（都是"和引擎一致"的代价）

| 场景 | 表现 |
|---|---|
| `bgcopy` 之后存档 | 读档后背景回到原图，`blt` 合成的那部分丢了（引擎一样，它只存文件名） |
| 在 gosub 里、且存档点在某行第 2 条语句 | 读档会重跑整行（引擎存字节偏移，粒度更细） |
| 存档在 `btnwait` | 读档后先重跑前面的注册命令，画面会闪一下才出现按钮（引擎一样） |
| 台词历史 | 读档后清空，只重建当前页（引擎的 Page 上限 16 屏） |

### 验证

- 单测 98 项（存档相关 12 个全部按新语义重写）
- `tools/check_all.py` 11/11
- 万华镜：存档 153 行 → 读档回到 152 行（滞后一行）、变量 19 个、精灵 49 个、背景一致、
  继续点击能推进到 `xswl`
- Ever17：存档 111582 → 读档回到 111580 → 重跑到 111582 停住（逐字循环里存档的固有表现）
- 菜单测试：游戏内存档写出 `save2.dat`，槽号与点击位置一致，能被 `parse` 解析

---

## O. 页面模型：文本行累积与 `linepage`（**已完成**，0.16.0）

这是 agent 看到的"每一屏"是否正确的问题，之前一直按"一条文本行 = 一页"实现。

### 引擎的真实规则（源码 + 真引擎探针双重确认）

| 规则 | 依据 |
|---|---|
| 一条文本行**不是**一页，会累积到当前页；`processEOT` 只往页里加一个换行 | `ONScripter_text.cpp::processEOT` |
| `\` 与 `@` 都是 clickstr，**只等待、不清屏** | `ScriptHandler::checkClickstr` 对两者都返回 1 |
| 清屏只发生在"剩余行数 <= clickstr_line"时的点击之后 | `clickWait` → `clickNewPage` → `newPage()` |
| `linepage` 给每条文本行**自动补 clickstr**（mode 1 补 `\`；mode 2 按剩余行补 `@`/`\`） | `ScriptParser::readToken` |

真引擎探针（`setwindow 100,100,20,3`、行距 36）：

```
第一行AAA          ← 无 \
第二行BBB          ← 无 \
测试文本六字        ← 无 \
getcursorpos → X=100 Y=208
结果X=100Y=208\    ← 有 \，这里才停
```

截图里 **4 行同时可见、只停 1 次**；我们的旧实现会停 4 次、每页只有 1 行。

### 为什么两款游戏表现不同

| 游戏 | `linepage` | 表现 |
|---|---|---|
| 万华镜 | **有**（L25106，注释写着"将行末没有 `\` 的显示文本的换行视为换页"） | 每行都停，页面累积到 `num_y` 行再换页 |
| Ever17 | 没有 | 名字行 + 台词行累积成同一页（真存档里 16 页有 10 页含换行） |

**只做"累积"或只做"每行停"都会错**：必须先读 `linepage` 再决定。

### 改动

| 文件 | 改动 |
|---|---|
| `state.py` | 新增 `linepage_mode` / `clickstr_line` |
| `interp.py` | 实现 `cmd_linepage`（`linepage` 从 no-op 移出，NOOP 60 → 59）；`_exec_text` 改为**追加**到当前页；只在 clickstr（或 linepage 补出来的）处停；`@` 分段改为追加而非替换；新增 `_page_is_full()` |
| `session.py` | 点击时按"页满"清屏（引擎的 `clickNewPage`）；读档恢复的页面打 `page_from_save` 标记，重跑那一行时**替换**而不是追加（否则同一句会出现两次） |

### 验证

| 项 | 结果 |
|---|---|
| 真引擎三个基准 | 4 行一页 / 只停 1 次 / `getcursorpos=(100,208)`，全部一致 |
| 单测 | 118 → **123 项**（新增：累积同页、linepage 每行停、满页才换页、`@` 不算清屏） |
| `check_all` | **11/11**（62.0s） |
| 万华镜 | `linepage_mode=1`，每行一停，页面 2~4 行（与引擎同样的"整页"观感） |
| Ever17 | `linepage_mode=0`，标题菜单走 `btnwait`、正文按 clickstr 累积 |
