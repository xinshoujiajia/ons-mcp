# ons-mcp

把 ONScripter（NScripter）中文视觉小说改造成 MCP 服务，让 agent 像玩家一样玩。
纯 Python 单进程，不用 SDL，不用 wasm，不依赖浏览器。

**能做什么**：指向一个 ONS 游戏目录（**解包版或只有 `.nsa` 的原始发布版都行**），
走标题 → 序章 → 任意章节，遇到分支能读选项并选择，能读台词、看截图、点任意坐标、
随时存档读档（含游戏内菜单的存读档）。

实测两款：

| 游戏 | 形态 | 结果 |
|---|---|---|
| 《美少女万华镜2》 | 解包版，GBK，1280×720 | 全 17 章 20000 步无卡死跑通，12 处选项全对 |
| 《Ever17》 | 原始发布版（`nscript.dat` + `arc*.nsa`），GBK，800×600 | 从标题进正文，背景/立绘/文本框/台词全对；与同源解包版**逐像素一致**；1500 步长跑、4 次选项、无卡死 |

## 安装

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .        # 或 pip install -r requirements.txt
```

`pip install -e .` 会同时装出两个等价入口：`python -m onsmcp` 和 `ons-mcp`。
不想安装也可以直接用仓库里的 `run_mcp.py`（内部会把 `src/` 加进 `sys.path`）。

## 接入 MCP 客户端

```json
{
  "mcpServers": {
    "ons": {
      "command": "D:/project/dsh-ons-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "onsmcp"],
      "env": { "ONSMCP_LOG": "warning" }
    }
  }
}
```

三种 `command`/`args` 写法都可用，按你装没装包选：

| 方式 | command | args |
|---|---|---|
| 包入口（推荐） | `<venv>/python.exe` | `["-m", "onsmcp"]` |
| 控制台脚本 | `<venv>/Scripts/ons-mcp.exe` | `[]` |
| 免安装 | `<venv>/python.exe` | `["D:/project/dsh-ons-mcp/run_mcp.py"]` |

WorkBuddy 的配置文件是 `~/.workbuddy/mcp.json`，格式同上（`mcpServers` 字典）。
改完需要在连接器管理页右上角的自定义连接器入口点一次「信任」才会生效。

**信任是按配置内容算哈希的**，别手改已批准过的那条：

```
sha256( command | args 排序后 join(",") | env 的键名排序后 join(",") [| cwd] )
```

所以改 `command`（哪怕只把 `/` 换成 `\`）或增删 `env` 的**键名**都会让信任失效、需要重点一次；
改 env 的**值**不影响。（宿主体在 `~/.workbuddy/mcp-approvals.json` 里记的就是这个哈希。）

宿主起进程时只传一组白名单环境变量（`APPDATA`/`PATH`/`SYSTEMROOT`/`TEMP` 等）再覆盖我们
配的 `env`，`cwd` 是宿主自己的目录。我们的代码不碰 `Path.cwd()`，所以用 `ons-mcp.exe`
这种绝对路径入口最省事。

### 自己先试玩一遍

`tools/play_via_mcp.py` 用**真实 MCP 协议**（stdio + JSON-RPC：initialize → tools/list →
tools/call）起一个客户端，像 agent 一样把游戏玩一遍：

```
python tools/play_via_mcp.py --game "D:/game/美少女万华镜2" --steps 40
python tools/play_via_mcp.py --game "ever17_packed/Ever17" --steps 20   # 未解包版也能玩
```

它的决策顺序就是给 agent 用的顺序：**有选项 → `choices()` → `choose(0)`；
在等按钮 → `buttons()` → 点矩形中心；否则 → `click()` 推进**。
这个脚本已经进了 `tools/check_all.py`（"MCP 试玩"一项）。

### 截图的两种模式

| `format` | 返回 | 写硬盘？ | 适合谁 |
|---|---|---|---|
| `image`（默认） | MCP 的 `image` content 块（base64 + mimeType） | ❌ 不写 | 视觉模型直接看画面 |
| `base64` | JSON 字符串 `{format, media_type, data, bytes}` | ❌ 不写 | 需要自己解码的客户端 |

两种模式全程在内存里完成（裁剪也在内存做），**不产生任何文件**——
连游戏目录下的 `.onsmcp_shots/` 都不会被创建。想要留档的话，由客户端自己把
base64 写成本地文件。

`rect` 传「游戏屏幕上的矩形区域」`[x, y, w, h]`（游戏分辨率下的像素坐标），
不传就截整屏。

```
screenshot(rect=[980, 310, 145, 52])   # 只截那一块
```

### 环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `ONSMCP_LOG` | `warning` | 日志级别：`debug` / `info` / `warning` / `error` / `silent`。日志只走 stderr |
| `ONSMCP_TIMEOUT` | `10` | 单次 `start`/`click` 的墙钟上限（秒），超时会被中断并在返回值的 `stopped` 字段里报告 |
| `ONSMCP_FONT` | 空 | 强制指定字体文件，优先于游戏自带的 `default.ttf` |
| `ONSMCP_SAVE_DIR` | 游戏目录 | 存档目录（对应引擎的 `--save-dir`）。装进 `Program Files` 这类只读位置时，不设这个变量也会自动回落到 `%LOCALAPPDATA%/onsmcp/<游戏目录名>`；设了但建不出来/不可写会直接报错 |

## agent 的典型一轮

```
start(game_dir="D:/game/美少女万华镜2", hooks=true)
text(history=5)   # 读当前台词 + 最近 5 句（理解上下文）
screenshot()      # 看一眼画面（可选）
click()           # 推进（返回值里就带当前状态：waiting/label/line/…）
choices()         # 有分支时：拿到 [{index, text, rect}]
choose(0)         # 直接选第 0 项
sessions()        # 看各个会话停在哪
save(1) / load(1) # 随时存读
```

同时玩两个游戏：

```
start(game_dir="D:/game/美少女万华镜2", session="wanko")
start(game_dir="D:/ever17", session="e17")
click(session="wanko")     # 只推进万华镜
text(session="e17")        # 读 Ever17 的台词
sessions()                 # 看两边各自停在哪
close("wanko")             # 释放它打开的 .nsa 映射
```

## 工具

| 工具 | 作用 |
|---|---|
| `start(game_dir, label?, width?, height?, cache_mb?, hooks?, timeout_s?, session?)` | 初始化并跑到第一个等待点；`width/height=0` 表示用脚本头解析出的分辨率。返回值就是初始状态 |
| `sessions()` | 列出所有会话及其剧情位置 |
| `close(session?)` | 关闭会话并释放归档映射 |
| `text(history?)` | 当前屏幕文本（有说话人时是 `【名字】：台词`）；`history=N` 附带最近 N 句台词。返回的是裸字符串，不是 JSON；状态对象里另有 `speaker` 单列说话人（**原样**，部分移植脚本自带【】，如 `【雫】`） |
| `screenshot(rect?, format?)` | 取画面。`rect` 是游戏屏幕上的矩形区域 `[x, y, w, h]`，不传则截整屏。`format='image'`（默认）返回 MCP 图片块，客户端与视觉模型可直接看；`'base64'` 返回 base64 文本 JSON。**两种模式都不写任何文件** |
| `click(x?, y?, button?)` | 不传坐标=推进/翻页，传坐标=点选项；`button=right` 开游戏内菜单。返回状态 + `changes`：`screen`（画面有没有动，总开关）、`text`/`bg`/`tachi`/`sprites` 四个细分，外加 `bg_image`（当前背景文件）、`tachi_images`（左中右立绘）、`sprite_count`（可见精灵数）、`sprites_added`/`sprites_removed`（换掉的图，最多各 8 个）——**`screen=false` 就不用再截图** |
| `choices()` | 当前选项：序号、文本、按钮编号、可点矩形；不在选项界面时返回 `{choices: [], hint}` |
| `choose(index)` | 按序号选一项（等价于点中心）；越界时带 `hint` 说明当前状态 |
| `buttons()` | 列出所有可点按钮的矩形（标题菜单/界面调试用）。`rect` 是游戏屏幕上的矩形区域 `[x, y, w, h]` |
| `save(slot)` / `load(slot)` | **原版 `save<N>.dat`**（ONS 2.8）。引擎能直接读，我们自己也只读它。全局变量写 `gloval.sav`（引擎同名文件）。槽位是 `0..999` 的整数，越界返回 `ToolError`；文件落在 `ONSMCP_SAVE_DIR`（默认游戏目录）。`save` 返回 `{slot, path, size}`（只讲写盘，不带剧情位置）；`load` 返回当前状态并多一个 `slot` |

除 `sessions()` / `close()` 外，所有工具都接受可选的 `session` 参数。

工具**不会抛异常**：出错时返回 `{"error": {"type", "message", "hint"}}`，
`hint` 会告诉 agent 下一步该怎么改（比如「先调用 start」「检查 game_dir」）。

## 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `error.type = ToolError: 还没 start` | 先调 `start(game_dir=...)`，后续工具都依赖会话 |
| `FileNotFoundError: 目录下没有 0.txt / nscript.dat` | 目录没解包。先用 nsadec 解开 `nscript.dat` / `.nsa` |
| 文本是乱码 | 编码探测失败。检查脚本是不是 GBK/UTF-8/CP932/Big5 之外的编码 |
| 字全是方框（豆腐块） | 游戏自带字体缺字。设 `ONSMCP_FONT=C:/Windows/Fonts/msyh.ttc` |
| 未解包的游戏能直接跑吗 | 能。目录里有 `nscript.dat` 和 `arc*.nsa` 就够，引擎直接读归档（内置 LZSS/SPB 解压） |
| `nscript.___` 读不了 | 这种格式要用游戏 EXE 里的 key table 解密，本引擎不支持；换 `0.txt` 或 `nscript.dat` |
| 分辨率不对 | 脚本首行 `;$S<w>,<h>` / `;mode800` 决定；也可以在 `start(width=,height=)` 里强制 |
| 画面全黑、只有文本 | 素材路径缺失，看 `click()` 返回值里 `unsupported` 的 `image:xxx` 及首次出现行号 |
| 点不动、`waiting='btn'` 但 `buttons()` 为空 | 该界面用 `cell` 九宫格或未实现命令铺的，看 `unsupported` |
| 返回值里 `stopped = "timeout:..."` | 脚本里有死循环或等待型命令；`ONSMCP_TIMEOUT` 调大再试 |
| `type = SaveFormatError` | 不是 ONS 2.8 存档（版本不符或文件截断）。换一个槽位，或重新存一次 |
| `type = SaveDirError` / 存档时 `PermissionError` | 游戏目录不可写（装在 Program Files 等）。设 `ONSMCP_SAVE_DIR` 指向可写目录；不设也会自动回落到 `%LOCALAPPDATA%/onsmcp/<游戏名>` |
| `error.type = ToolError: 槽位 1000 超出范围` | 槽位是 `0..999` 的整数；游戏内存档界面一般用 1..9 |
| 返回值里出现 `undefined_vars` | 脚本里用了没有 `numalias` 的名字（引擎会当 0 号槽）。移植新游戏时先查别名定义 |
| 内存涨得快 | `start(cache_mb=128)` 压小图片缓存；返回值里 `memory` 看实时占用 |
| 客户端连不上 / 解析失败 | 确认服务只往 stderr 写日志（`ONSMCP_LOG=debug` 时也如此）；别在游戏目录放会 print 的脚本 |

## 自测

```bash
# 一条命令跑全部（单测 / 协议 / 端到端 / 选项 / 菜单 / 可移植性 / 排版·禁则·透明校对 / 长跑）
./.venv/Scripts/python.exe tools/check_all.py

# 只跑快的（跳过浏览器排版校对与长跑）
./.venv/Scripts/python.exe tools/check_all.py --fast

# 单跑某一项
./.venv/Scripts/python.exe tools/check_all.py --only 菜单
```

`check_all.py` 每项独立进程、独立超时，失败时打印尾部输出并整体返回非 0，
结果写到 `docs/checks.json`。

## 关键设计（对应引擎源码）

| 结论 | 依据 |
|---|---|
| 命令名、标签名大小写不敏感 | `ScriptHandler.cpp` 读 token 时把 A-Z 折成 a-z |
| 行首是双字节字符 / 数字 / `"` ` @ \ / % ? $ [ ( < > ! # ,` 即为文本行 | `ScriptHandler.cpp` `readTokenTop` 的 text 分支 |
| 行内 `:` 分语句，`if` 为假吞掉整行；`gosub` 的返回地址是行内下一个 token | `ONScripter.cpp` `parseLine` + `RET_CONTINUE` |
| `defsub` 宏 = gosub，参数由 `getparam` 顺序取 | `ScriptParser_command.cpp` `defsubCommand` |
| 文本坐标 = `top_xy`，行距 = `pitch_xy` | `FontInfo::x()/y()` = `xy*pitch/2 + top_xy` |
| 命令总表 347 条（Jh）/ 348 条（Yuri，多一条 `effectskip`） | `ONScripter_lut.cpp` |
| 精灵按 id **从大到小**绘制，`humanz` 分割文本框上下层 | `ONScripter_image.cpp:640-690` `refreshSurface` |
| `csel` 在 CSEL 模式下不画界面，直接 `setCurrentLabel("customsel")` | `ONScripter_command.cpp:879` |
| `exbtn`/`spbtn` 命中区 = 精灵图片矩形；精灵没图就静默不注册 | `exbtnCommand` / `spbtnCommand` |
| `btndef` 任何形式都清空按钮表 | `btndefCommand` 末尾 `deleteButtonLink()` |
| 精灵 tag `:a/` 只是"透明混合模式"，`/` 后第一个数是**格数**不是透明度 | `parseTaggedString`：`:a` 设 `TRANS_ALPHA`，`/` 后 `num_of_cells` + 每格毫秒 |
| 文本框图片（`setwindow3 ... ,"frame.png"`）按 **copy 模式**画，PNG 的 alpha 不当透明度用 | 实测参照引擎：α=28 的行输出的是图片 RGB，不是和底图混合；α=0 的行不画 |
| `setwindow3` 给 `#RRGGBB` 时是把区域逐像素**乘**色（变暗），不是盖半透明 | `*buf * color >> 8` |
| 脚本首行 `;...` 不是注释，是配置（`mode800` / `value500` / `$S1280,720G1500`） | `ScriptHandler::readConfiguration` |
| `nscript.dat` = 每字节 `^ 0x84`；`nscr_sec.dat` = `^` 5 字节 magic 循环 | `ScriptHandler::readScriptSub` |
| NSA 头是 **大端**；索引条目数据紧挨排列，可据此校验字节序 | `DirectReader::readShort/readLong`，`SarReader::readArchive` |
| 变量名可以是纯数字（`%1` / `%101` / `$0`） | NScripter 语法，Ever17 全篇依赖 |

## 已实现范围

- 脚本解析：`0.txt`（含多分片）/ `nscript.dat` / `nscr_sec.dat`，
  GBK / UTF-8 / CP932 / Big5 自动探测；首行 `;$S` / `;mode` 决定分辨率与变量范围
- 资源：磁盘目录 **或** `arc.nsa` / `arc1.nsa` / …（内置 LZSS / SPB / NBZ 解压，mmap 不整包载入）
- 字体：游戏 `default.ttf` → `ONSMCP_FONT` → 系统 CJK 字体，自动避开豆腐块
- 解释器：`label` / `goto` / `gosub` / `if`（含 `&&` `||`）/ `for` / `next` /
  `mov` `mov2..mov10` `add` `sub` `mul` `div` `mod` `inc` `dec` `itoa` `atoi` `len` /
  `numalias` `stralias` / `defsub` 宏 + `getparam` / `gettag` / `split` / `mid`
- **变量模型照引擎**：按**槽位**存（每槽有整数和字符串两个值），`numalias 名字,槽号`
  建映射，`%名字` 与 `%槽号` 同槽；**裸名字在数值表达式里是槽号常量**
  （脚本拿它当具名常量，如 `for %i=0 to save_num`）；未定义的名字落到 0 号槽并记进 `undefined_vars`
- **全局变量**：`globalon` + `;G<n>` / `;value<n>` 划出 `>= global_border` 的槽位。
  它们不进 `save<N>.dat`（读档不回滚），单独落在 **`gloval.sav`**（与引擎同名同格式）
- **画面状态与引擎一致**：存档只留背景**文件名**（`bgcopy` 之后写真实来源，不会是 `*bgcpy`）；
  `blt` 贴上去的像素和 `bgcopy` 的合成结果**都不存**，靠读档后脚本重跑还原 —— 引擎也是这么做的。
  精灵的条图帧号（`current_cell`）进存档
- **音频记账**：`bgm` / `mp3` / `wave` / `loopbgm` / `dwavestop` 等只更新状态、不播放。
  存档里的音频字段与引擎一致（音乐名 + loop 标志 + `mp3save`），语音与音量引擎本来就不存
- **数组（`dim`）**：`dim ?name[e1][e2]` 声明，**每维元素数 = 声明值 + 1**（`dim ?a[100]` 合法下标 0..100）；只有 int 数据，按行主序线性存放。`?a[i]` 读写、`%?a[i]` 用元素值当槽号、`?a[i]` 在文本行里插值都支持；数组按声明顺序进存档
- **表达式**：括号 `( )` 参与优先级、`mod` 与 `*` `/` 同级（引擎 `parseIntExpression` 的算法）
- **存档只有一套格式**：`savefile_bin.py` 读写原版 `save<N>.dat`，两份真引擎样本能做到**字节级往返**；续跑点按引擎口径（0-based 且滞后一行）。真引擎读我们写的档已验证
- **读档靠重跑**：不恢复按钮表/选项表，也不恢复等待态 —— 和引擎一样，让脚本从存档那行重新执行、自己把 UI 注册回来
- 图像：`bg` / `lsp` `lsph` / `vsp` / `csp` / `amsp` / `getspsize` / `setwindow` `setwindow3` /
  `strsp` / `bar` / `blt` / `bgcopy` / `ofscopy`
- **窗口配置**（`setwindow` 与 `setwindow3` 是同一套参数，引擎都走 `setwindowCore`）：
  `x,y,num_x,num_y,fsize_x,fsize_y,pitch_off_x,pitch_off_y,wait,bold,shadow,窗口图/色,坐标`
  —— `pitch` 是**偏移量**，`#RRGGBB` 窗口读 4 个坐标（矩形）
- **透明模式**（引擎的 `trans_mode`）：`alpha`（无 alpha 通道时**用图片右半当 alpha**）/
  `leftup`（左上角像素色作透明键）/ `topright` / `copy` / `mask`（`:m遮罩.bmp`），
  由 `transmode` 命令设全局默认
- 立绘：`ld l|c,r`（引擎的 tachi，位置自动计算）/ `cl l|c|a`
- 文本排版：禁则（行首标点悬挂、行尾开引号下移，`setkinsoku`/`addkinsoku` 可改表）、
  `indent`（换行后缩进，进 page 文本）、`locate`（字符格偏移）、`textcolor`（正文颜色）、
  `texthide`/`textshow`、`br`（空行）、`puttext`（指示文字，不等待）、`clickstr`（自定义等点击字符）、
  不按框高自动切页（与引擎一致）
- **页面模型照引擎**：一条文本行不是一页 —— 连续行会累积到同一页；`\` 与 `@` 都是
  clickstr（只等点击），页面剩余行数不足时点击后才换页；`linepage` / `linepage2`
  给每条文本行自动补 clickstr（万华镜用了它，所以每行都停）
- **移植脚本的标签决定分页**：`[voice|needClear]` 的第 2 段是"这句要不要清页"——
  `|1` 起新页（上一句消失、只剩当前句），`|0` 续在前一页（名字行 + 台词行同屏）。
  Ever17 靠它做到"一句一页"；不解析就会把整段话堆成一页（见 `docs/quirks.md` 怪点 27）
- **长 `delay` 留一帧**：`>=800ms` 的演出停顿会停在画面上等一次推进（`waiting="delay"`），
  否则像章节日期画面这种"换背景 → 立刻又被下一张覆盖"的中间帧一帧都看不到（怪点 28）
- 按钮：`btn` / `spbtn` / `exbtn` / `exbtn_d` / `btnwait` / `textbtnwait` / `cselbtn`
- 分支：`csel` → `*customsel` → `getcselnum`/`getcselstr` → `cselgoto`
- 菜单：`textgosub` 钩子 + `savegame`/`loadgame`/`savefileexist`/`savetime`
  （存档就是原版 `save<N>.dat`；读档后靠脚本重跑重新注册按钮，与引擎同一机制）
- 未知命令降级：**引擎有、我们没做**的命令在 `stubs.py` 里一条一个桩（docstring 写语义），
  撞到就记进 `stubbed`（含计数与首次行号）并跳过；**查无此命令**才记进 `unsupported`
  （多半是别的脚本文件里的宏或拼错）。两本账分开，换游戏时一眼看出是活没干完还是脚本有问题

## 未实现（都不阻塞剧情）

| 项 | 说明 |
|---|---|
| `bar` 外观 | 画成实色块（原版是九宫格条），位置尺寸正确 |
| 悬停高亮 | 按空闲态渲染，能点但不 hover 变色 |
| 文本内联颜色 `#RRGGBB` | 正文里夹的换色标记会被剥掉（整体颜色走 `textcolor`）；agent 只读文本，不影响理解 |
| 竖排 / 注音 / 逐字显示 | `tateyoko` / `rubyon` / `textspeed*` 仍是桩：渲染器只做横排、一次成像 |
| 精灵 cell 动画 | `cell` 指定的帧会渲染，但没有定时器驱动（不会自己播）；解码超 96 MB 的装饰条图直接跳过 |
| `monocro` | 本作 0 次调用 |
| 引擎有但我们没做的命令 | 全部进了 `stubs.py`（207 个桩，docstring 写语义与原因），跑起来是 no-op，`state()["stubbed"]` 能看到撞到哪几条 |
| 音频播放 / 视频 / 转场 | 音频**状态**已记账并进存档（只记文件名与 loop 标志，不解码不播放）；视频与转场不做 |

## 目录

```
src/onsmcp/
  __main__.py   python -m onsmcp 入口
  log.py        日志（只写 stderr，ONSMCP_LOG 控制级别）
  archive.py    NSA/SAR 归档读取（自动判字节序 + LZSS/SPB/NBZ 解压）
  files.py      统一资源访问（磁盘 → 归档），供渲染与脚本共用
  scriptfile.py 脚本格式识别（0.txt/nscript.dat/nscr_sec.dat）+ 首行配置解析
  encoding.py   编码探测（用字分布判定，不靠"能否解码"）
  script.py     分词 / 参数读取 / 指令表 / 标签
  interp.py     解释器：主循环、if、宏、等待点、降级、超时
  stubs.py      引擎有、本项目没做的命令：一条一个 cmd_xxx 桩（docstring 写语义与原因）
  render.py     Pillow 合成 + 图片 LRU 缓存
  state.py      变量槽 / 数组 / 精灵表 / 按钮表 / 文本框配置
  savefile_bin.py  原版 save<N>.dat 的读写（EngineSave / parse / build）
  session.py    会话编排（start/click/text/trace/screenshot/save/超时预算）
  server.py     MCP 工具定义 + 结构化错误
tools/
  check_all.py         一条命令跑全部检查（11 项）
  play_via_mcp.py      用真实 MCP 协议（stdio + JSON-RPC）当客户端试玩一遍
  build_inventory.py   命令集统计（引擎 LUT × 游戏脚本）→ docs/command-inventory.md
  missing_commands.py  查脚本用到的命令：已实现 / 桩 / 未处理（三分法）
  probe_page.py        在参照引擎里试脚本写法（分页/文本框行为探针）
  probe_flow.py        在参照引擎里验流程命令的落点（skip / break，纯色背景法）
  run_scene.py         不进 MCP 的冒烟测试
  playthrough.py       自动推进器（长跑 / 卡死检测 / 出报告）
  make_refgame.py      生成排版参照用的迷你工程（同脚本/同字体）
  calibrate_layout.py  一键校对：起 web 构建 → 无头截图 → 我们的渲染 → 量化比对
  compare_layout.py    比对实现（几何指标 + 像素差异）
  window_compare.py    文本框图片与窗口位置的单独比对
tests/
  test_units.py        解析/执行/变量槽位/数组/存档/原版二进制存档/画面状态/音频记账/按钮/选项/超时/错误处理/立绘/禁则/透明模式单测（123 项）
  raw_rpc_test.py      裸 JSON-RPC 协议测试（35 项断言，校验 stdout 零污染）
  e2e_flow.py          端到端：标题→序章→推进→选项（11 项检查）
  test_choices.py      定点验证 6 处 csel × 2 个分支的跳转
  test_menus.py        游戏内菜单：右键→保存→选格→确认→落盘
  test_portability.py  可移植性：脚本格式/编码/分辨率/归档/字体/多会话（6 项）
docs/
  quirks.md            引擎怪点与已知偏差（换新游戏先看这份）
  roadmap.md           全部待办与完成情况
  next-steps.md        当前真实待办
  command-inventory.md 命令统计报告
  checks.json          check_all 最近一次结果
```
