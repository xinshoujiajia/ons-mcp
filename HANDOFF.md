# 交接文档：ONS 游戏 MCP（agent 游玩引擎）

> 这份文档用于把一次云端会话的上下文完整带到本地新会话。
> 读完本文档即可接续工作，**不需要重新分析源码**。

生成时间：2026-10-23
原始会话记录：同目录 `session-raw.jsonl`（内部格式，仅供追溯原文，新会话不必读取）

> **⚠️ 这是一份初始快照，事实已部分过期。**
> 本地会话接手后又完成了大量工作（可移植性、游戏内菜单、工程化、工具精简等）。
> **当前状态以 `CHANGELOG.md`（变更）与 `docs/roadmap.md`（进度）为准**，
> 本文保留的是当初的决策记录与源码分析结论（仍然有效）。
> 下面凡与现状冲突之处，都已就地标注。

---

## 0. 一句话目标

改造 ONS 游戏模拟器（Onscripter），做成一个 MCP 服务，让 agent 能**像玩家一样**玩中文移植版 ONS 视觉小说——追求**完整体验**而非速通，能从头玩到尾。

---

## 1. 当前进度

| 阶段 | 状态 |
|---|---|
| 需求澄清 | ✅ 完成（见第 2 节决策记录） |
| 源码分析 | ✅ 完成（三个主流分支已下载并分析，见第 3 节） |
| 方案定稿 | ✅ 完成（见第 4 节） |
| 测试游戏 | ✅ `D:/game/美少女万华镜2`（ONS 移植版，已解包为 0.txt，GBK） |
| 命令集统计 | ✅ `docs/command-inventory.md`（引擎 LUT 347/348 条 × 游戏实际 128 种） |
| 第一阶段实现 | ✅ bg + 文本 + 点击推进 + 截图/文本输出 |
| 第二阶段 | ✅ 按钮系统 / `csel` 选项 / 含调用栈的存档 |
| 稳定性 | ✅ 图片缓存 LRU（2.45 GB → 319 MB）、长跑 20000 步通关 |
| 游戏内菜单 | ✅ `textgosub` 钩子 + 右键菜单 + 存读档 |
| 工程化 | ✅ `pip install -e .` / `python -m onsmcp`、结构化错误、超时保护、`tools/check_all.py` |
| 可移植性 | ✅ `nscript.dat` 解扰、`.nsa` 直读（LZSS/SPB）、脚本头分辨率、字体回退、多会话 |

**现状（快照时）**：MCP 13 个工具；两款游戏实测（万华镜2 解包版 1280×720、Ever17 原始发布版 800×600）。
`tools/check_all.py` 8 项全过。

> **已过期 —— 现状**：MCP 工具 **11 个**（`state` 与 `script_trace` 已移除，见 `docs/roadmap.md` G 组）；
> `tools/check_all.py` **11 项**全过。详细进度见 `docs/roadmap.md`，变更见 `CHANGELOG.md`。

---

## 2. 已确认的决策（不要重新讨论，除非有充分理由）

| # | 决策 | 结论 | 理由 |
|---|---|---|---|
| 1 | 基线分支 | **ONScripter-Jh** | 唯一自带 GBK 全表的活跃分支；EN 只有 CP932/UTF-8，中文直接乱码 |
| 2 | 实现语言 | **纯 Python** | 操作直接，无跨语言边界；Playwright 驱动 wasm 的异步/状态不可见问题太多 |
| 3 | 进程模型 | **单进程** | 双进程（socket）改造成本高，无收益 |
| 4 | 是否用 SDL | **完全不用** | 纯 Python 用 Pillow 做合成，无 video/event/timer 任何依赖 |
| 5 | 编码策略 | **运行时自动探测** | 读 0.txt 前若干 KB，按 GBK/UTF-8/CP932 的合法率判定 |
| 6 | 动画/转场 | **不实现，保留函数** | agent 感知不到，且工作量最大 |
| 7 | 音频/视频 | ~~**不实现**~~ → 音频 0.9.0 起**只记账**（更新状态、不播放）；视频仍不做 | DeepSeek 系模型无音视频能力 |
| 8 | 工具范围 | 必需 5 个 + 建议 3 个 | 见 4.3 |
| 9 | 轨迹粒度 | **按"事件段"切分** | 用户定义：两次等待点击之间执行的脚本 |
| 10 | 存档格式 | ~~第一版用自有 JSON~~ → **0.12.0 起只有原版 `save<N>.dat`**，自有 JSON 已删除 | 当初的理由是"不做兼容"；后来目标改为"与原版完全一致"，于是反过来只留原版格式 |
| 11 | 归档解包 | **用现成 nsadec 预处理** | 避开 Python 侧实现 LZSS/NBZ 压缩 |
| 12 | 运行环境 | 迁移会话到本地 | 本地有游戏和调试工具 |

### 被否决的方案（不要重提）

- **C：JH → wasm + 浏览器驱动**：虽然 `wcwac/em-onscripter` 已有现成移植，但 Playwright 驱动 wasm 存在 ASYNCIFY 异步对齐、状态在 wasm 堆里不可见、跨三层调试等问题，操作繁琐。
- **B：Python MCP + C++ 引擎编成 .so**：仍需系统 SDL，且要设计 C ABI，不如纯 Python 直接。
- **A：全 C++ 单二进制**：分发简单但开发迭代慢。

---

## 3. 源码分析结论

三份源码用 `codeload.github.com` 的 tar.gz 下载（`git clone` 在本环境 443 超时，别用）。

```bash
curl -sL -o x.tgz https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/master
```

| | ONScripter-EN | **ONScripter-Jh（选定）** | ONScripter-RU |
|---|---|---|---|
| 仓库 | `Galladite27/ONScripter-EN` | `chf2000/ONScripter-Jh` | `umineko-project/onscripter-ru` |
| 定位 | 英化社区主力，2023 后恢复维护 | 中文社区 fork | Umineko 特化 |
| SDL | 1.2 | SDL2 | SDL2 |
| 规模 | 76k 行 cpp | 60k 行 cpp | 40k 行 cpp |
| 编码 | CP932 + UTF-8 | CP932 + **GBK 全表** +（无 UTF-8 脚本） | 未发现 SJIS/GBK |
| 中文游戏 | 乱码 | 可用 | 不可用 |

### 3.1 关键的编码架构限制

JH 的编码抽象是**逐 16 位单元映射**，不是字节流解码：

```cpp
// coding2utf16.h:48-50
virtual void init() = 0;
virtual uint16_t conv2UTF16(uint16_t) const = 0;
virtual uint16_t convUTF162Coding(uint16_t) const = 0;
```

- GBK / Shift-JIS 都是双字节 → 能塞进 uint16 → **可用**
- UTF-8 中文是三字节 → **该架构装不下** → JH 不支持 UTF-8 脚本

`coding2utf16` 是**全局指针，运行期可切**（`onscripter_main.cpp:313` 有 `-enc:sjis` 先例，`:457` 处 `if (coding2utf16 == NULL) ... new GBK2UTF16()`）。所以自动探测在架构上成立。

**结论**：中文 ONS 移植版绝大多数是 GBK（工具链沿用 NScripter 时代），第一版只需覆盖 GBK + Shift-JIS。UTF-8 场景留作后续。

### 3.2 关键代码位置（JH / EN 结构基本一致）

| 用途 | 文件:行 | 说明 |
|---|---|---|
| 主循环 | `ONScripterLabel_event.cpp:550` `waitEvent()` | `while(1){ waitEventSub(); ... }` 阻塞 |
| 事件泵 | `ONScripterLabel_event.cpp:505` `waitEventSub()` | `SDL_AddTimer` + `runEventLoop()` |
| 事件模式 | `ONScripterLabel.h:463-476` | `WAIT_INPUT_MODE=4` / `WAIT_TEXTOUT_MODE=8` / `WAIT_BUTTON_MODE=2` / `WAIT_TEXT_MODE=256` |
| 脚本执行 | `ONScripterLabel.cpp:2047` `runScript()` | |
| 脚本位置 | `ScriptHandler.h:159` `getCurrent()` | 返回当前脚本指针 |
| 指针转行号 | `ScriptHandler.cpp:1091` `getLineByAddress()` | 遍历数 `\n`，**可复用为轨迹记录** |
| 当前字符串 | `ScriptHandler.h:150` `getStringBuffer()` | 原始 token 缓冲，非屏幕文本 |
| 截图 | `ONScripterLabel_command.cpp:3016` `getscreenshotCommand()` | 从 `screen_surface` 缩放到 `screenshot_surface` |
| 文本绘制 | `ONScripterLabel_text.cpp:1010-1150` | `out_text[5]` 是**逐字符临时量，没有已显示文本缓冲** |
| 命令表 | `ONScripterLabel.cpp` | **255 条命令** |

**重写时最需要注意的一点**：原引擎没有"当前屏幕文本"这个状态，文本是逐字符 draw 出去的。Python 重写反而有优势——文本是天然的一等公民，不需要 hook 渲染。

### 3.3 命令规模

`ONScripterLabel.cpp` 命令分派表共 **255 条**。但剔除动画/转场/音视频后，核心交互命令不到 70 条：

| 类别 | 约数量 | 示例 |
|---|---|---|
| 流程控制 | 15 | `goto` `gosub` `label` `if` `jumpf` `tablegoto` |
| 图像 | 20 | `bg` `ld` `sp` `cl` `alpha` `blend` `monocro` |
| 文本 | 15 | `\` 换行、ruby、禁则、clickwait、`textclear` |
| 系统 | 20 | `select` `btnwait` `rmenu` `save` `reset` |

**实现方法：先扫描再实现，不要盲目写 255 条。**

1. `nsadec` 解包 nsa → `0.txt`/`1.txt`
2. 正则扫行首命令 → `Counter` 统计
3. 得到该游戏的真实命令集（通常 40~70 条）
4. 按频次实现
5. 未知命令 **降级不崩溃**：写 `unsupported.log`，跳过继续
   （0.17.0 起这条拆成两本账：引擎里有、我们没做的命令在 `src/onsmcp/stubs.py`
   里一条一个桩，记 `stubbed`；查无此命令才记 `unsupported`）

---

## 4. 方案定稿

### 4.1 架构

```
ons-mcp (纯 Python，单进程)
├── MCP 层         官方 mcp SDK，stdio
├── 脚本层         解析器 + 解释器（逐条执行，走到"需要输入"即返回）
├── 状态层         变量表 %0-99、字符串表 $0-99、当前 label / 行号
├── 渲染层         Pillow 合成：底图 → 立绘 → 文字 → 单张 RGBA
├── 资源层         nsadec 解包后的目录，图片用 Pillow 直接读
└── 编码层         codecs：GBK / UTF-8 / CP932 自动探测
```

### 4.2 "事件段"的定义（核心概念）

```
click() → 恢复执行 → 逐条跑脚本 → 走到"需要用户输入" → 停下 → 交还控制权
```

这一段内执行的脚本，就是 `script_trace` 返回的内容。

判定"需要用户输入"的依据：遇到 `clickwait` / `textbtnwait` / `select` / `btnwait` 这类会阻塞等待玩家操作的命令。**注意**：因为没有动画和定时器，不需要处理"等待动画结束"这种中间态——这正是砍掉动画带来的简化。

### 4.3 工具清单

> **已过期 —— 工具名与参数都变了。** 下表是快照时的设计；实际是 11 个工具：
> `start` / `sessions` / `close` / `text` / `screenshot` / `click` / `choices` / `choose` /
> `buttons` / `save` / `load`。`state` 与 `script_trace` 已移除（状态信息在 `start`/`click`
> 的返回值里）；`screenshot` 的裁剪参数是 `rect`（列表 `[x, y, w, h]`），没有 `max_width`。

| 工具 | 参数 | 返回 |
|---|---|---|
| `start` | `game_dir` | 初始化，跑到第一个等待点 |
| `state` | — | 是否等待输入、当前 label、行号、是否在选项分支 |
| `text` | — | 当前屏幕文本（纯文本，已过滤控制符） |
| `screenshot` | `region?` `max_width?` | PNG（base64 或文件路径） |
| `click` | `x?` `y?` | 不传坐标=推进对话；传坐标=点选项/按钮 |
| `script_trace` | — | 上次操作以来执行过的脚本行（含行号、label、类型） |
| `choices` | — | 当前选项文本 + 各自可点击区域 |
| `save` / `load` | `slot` | ~~自有 JSON 格式~~ → 原版 `save<N>.dat`（0.12.0） |

`wait_idle` 不需要——没有动画，每次调用天然是"已完成"状态。

### 4.4 四阶段

1. **最小可跑**：单场景，`bg` + `text` + clickwait + 点击推进，输出文本和截图
2. **完整流程**：`label`/`goto`/`gosub`/`if`/`select`，让游戏能从头走到尾
3. **图像完整**：立绘 `ld`、位置 `sp`、`alpha` 混合、`cl`/`csp`
4. **兼容加固**：存档、`textgosub`、禁则细节、编码边界

---

## 5. 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| 文本排版与原引擎差异（换行、禁则、ruby 位置） | **高** | 拿原引擎当对照：本地跑原版截图，逐段比对修正 |
| 冷门命令缺失导致卡住 | 中 | 未知命令降级 + `unsupported.log`，先跑通再补 |
| 存档格式不兼容原版 | 低 | 第一版自有格式，agent 能存读即可 |
| UTF-8 脚本（少数移植版） | 低 | 探测到就转码成 GBK 再跑，或后续加 UTF-8 路径 |
| 加密 nsa / 魔改引擎 | 未知 | **尚未确认是否存在**，需拿到真实游戏后验证 |

---

## 6. 下一步（快照时的待办）

> **已过期 —— 这几项都做完了**：可移植性（`nscript.dat` 解扰、`.nsa` 直读）✅、
> 长距离通关验证 ✅、图片缓存 LRU ✅、游戏内菜单钩子 ✅、`pip install -e .` 工程化 ✅。
> 现状与剩余待办见 `docs/roadmap.md`。

1. 获取一个**最小的中文 ONS 游戏**（连资源目录）
2. 用 `nsadec` 解包，统计命令集
3. 写第 1 阶段：`bg` + `text` + `click` 跑通
4. 拿原引擎截图做对照，修文本排版

### 本地环境准备

```bash
pip install mcp pillow
# nsadec/nsaconv 需要编译（JH 源码里有 nsadec.cpp / nsaconv.cpp）
# 或者用现成的 nsadec 二进制
```

---

## 7. 工作方式约定（重要）

**上一轮会话中犯过的错误**：在需求还没讲完时就自作主张写完了整个工程，被用户明确批评"我还没说完我要做什么你怎么就写完了"。

**约定**：

- 需求有歧义时**先问，不要假设**
- 用户说"先去分析"就只分析，不要顺手实现
- 方案变更前先确认，不要自己决定技术路线
- 每一步的产出先说清楚，再动手

---

## 8. 附：已完成但与本任务无关的工作

会话早期做过一个 MCP 最小验证工程 `dsh-mcp-lab`（TypeScript，4 个工具，三层测试全过）。
**与本任务无关，可忽略或删除。** 唯一可复用的是它的测试方法论：

- 协议层用 SDK 客户端测一遍
- 再用裸 JSON-RPC 手写帧测一遍（防止"SDK 宽容"掩盖服务端不合规）
- stdout 必须零污染，每帧 `JSON.parse` 断言

这个思路已经套用到 Python 版上（`tests/raw_rpc_test.py`）。

---

## 9. 环境信息（原会话）

| 项 | 值 |
|---|---|
| 沙箱 | Ubuntu 24.04 / 256GB 磁盘 / 8GB 内存 / 4 核 |
| Python | 3.11（Pillow、mcp 可装） |
| Node | 22.13 |
| 浏览器 | Chromium（headless） |
| 源码位置 | `/root/.codebuddy/artifact/ons-src/`（沙箱销毁即失效，需重新下载） |
