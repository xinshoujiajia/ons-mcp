# 变更记录

遵循「能玩通一局」为里程碑，版本号在主功能落地时进位。

## 0.22.0 — 2026-10-27

**`click` 的返回值带上 `changes`：一眼看出这一下换没换画面。**

agent 每推进一步都要判断"要不要重新截图"，之前只能靠记上一屏的字段自己比。
现在 `click`（以及内部的 `choose`）返回状态里多一个 `changes`：

```json
"changes": {
 "screen": true,            // 总开关：任何一层变了都为真
 "text": false, "bg": true, "tachi": false, "sprites": true,
 "bg_image": "cut/cut038.png",          // 当前背景（没换也报，方便写上下文）
 "tachi_images": ["", "", ""],          // 左 / 中 / 右立绘
 "sprite_count": 9,                     // 可见精灵数
 "sprites_added": ["cgsys/title/Start01.png"],   // 换上的图（最多 8 个）
 "sprites_removed": ["cgsys/sys/title_skip.png"] // 撤掉的图（最多 8 个）
}
```

实现要点：

- 指纹**只读状态、不碰像素**——为了判断变化去合成/解码，0.21.0 的懒加载就白做了
  （一次 click 上百帧动画会被拖回 0.6s）。所以测的是 bg / 立绘 / 精灵表 / 文本层的状态，
  不是真实像素；`blt` 只改像素不改状态，靠 `bg_ops` 条数与 overlay 在不在间接兜住
- 万华镜的"立绘"其实是用 `lsp` 画的（两款游戏都**一次 `ld` 都没有**），所以换人看
  `sprites_added` / `sprites_removed`；`tachi_images` 留给真用 `ld` 的脚本
- 顺带给状态对象加了 `speaker`（`page` 里是「名字：台词」，单列一份免得 agent 自己切）
- 实测标题界面点空：`screen=false`（正确——`waiting='btn'` 时不带坐标不会前进）
- 单测 +2（三个层的变化节奏；点空必须 `screen=false`），全量 check_all 11/11

## 0.21.0 — 2026-10-26

**`bg` / 图片型 `lsp` 改成懒加载：开场动画的一个 click 从 0.64s 降到 0.02s。**

万华镜2 的开场动画是"一个 click 里连发 120 多次 `lsp`"，每张 1280×720。之前每次
`lsp` 都当场解码，于是这一个 click 要花 0.64s，还把 320MB 的 LRU 整块冲掉
（`entries` 102 / 318MB），后续所有点击都得重新解背景。而 agent 真正能看到的
只有停下来那一刻的那一帧——中间 118 张纯属白解。

现在 `bg` / `lsp` / `ld` / 读档恢复精灵都只记文件名（`render.DeferredImage`），
合成画面（截图）时才解码，且同一句柄只解一次。

三个必须照抄引擎语义的点：

- **透明模式是快照**：引擎在载入时就按当时的全局 `trans_mode` 建好 alpha
  （`setupAnimationInfo`），之后脚本再 `transmode` 不回头改已载入的精灵。
  句柄里存的是那一刻的模式，不是引用全局值
- **尺寸单独算、而且要算对**：`.size` 只读文件头（`Image.open` 不解码像素）。
  「右半当 alpha」要减半、条图要除以格数，两步都得复现，
  否则 `getspsize` 与 `spbtn`/`exbtn` 的命中区会偏——单测里逐条 tag 对着
  真解码的尺寸比
- **文件在不在要提前知道**：`bg` 找不到图时引擎保留旧背景，所以新增
  `GameFiles.has()`（只查目录项/归档索引，不读内容）

其他：

- `blt` / `btndef` / 文本框图片 / 存档缩略图仍然立即解码——它们当场就要像素
- `bgcopy`（`_bake_overlay`）会真的把延迟背景解出来，只发生一次
- `cache_stats()` 新增 `deferred` / `deferred_decoded` 两项计数

实测（万华镜2 开场，同一个 click）：**0.642s → 0.018s**，解码 **114 张 → 9 张**，
LRU 占用 **318MB → 9.5MB**。像素回归：万华镜2 前 26 帧、Ever17 前 14 帧与改动前
**逐帧 0 像素差异**；全量 check_all 11/11（含透明校对 / 排版校对）。

## 0.20.0 — 2026-10-26

**页面语义按移植脚本对齐 + 长 `delay` 留帧（Ever17 逐句比对的差异 3、5）。**

差异 3：`[voice|needClear]` 标签的第 2 段一直被当成语音的一部分，导致
"一句一页"的游戏把整段话累积到一页（Ever17 每帧多出 2~3 句，还带出帧内容
错位与场景切换提前）。

- `_split_tag` 拆出 `need_clear`：`|1` = 这句起新页（上一句消失）、
  `|0` = 续在前一页后面（名字行 + 台词行同屏）。
  同时把 `voice` 拆干净——脚本 `split $0,"|",$voice,$needClear` 不能再拿到带尾巴的值
- 没有这种标签的游戏（万华镜）照旧走 `linepage` / 满页换页，行为不变
- 实测：Ever17 第 1~22 句的显示内容与原版逐句一致，含折行位置

差异 5：章节日期转场（`chapterCutin` → `bg "...cal_501.jpg",10,1000` + `delay 1000`）
一帧都不出现——不是缺命令（`defsub`/`bg` 都实现了），而是 `bg` 的渐变与 `delay`
都没建模，两次换背景在同一次 run 里连续执行，中间画面直接被覆盖。

- `delay >= 800ms` 留一帧：退化成"可推进的暂停"（`waiting="delay"`），
  画面先合成等人看，下一次 click 继续。短 delay（Ever17 里 280 多次 30~180ms
  的动画同步）仍然跳过。阈值 800 是拿 Ever17 实际分布定的
  （章节 `1000` 要留帧，时钟逐位动画 `500`×3、标题转场 `700` 不该停）
- `start()` 自动跳过启动阶段的演出延迟，保证"进到能玩的状态"的语义不变
- `textoff` 现在连窗口框一起隐藏（之前只关文字，日期画面上残留一个绿框）
- 实测：Ever17 日期画面与原版差异 **0.01%**（40 像素）

测试 +5（needClear 三种组合、长/短 delay、textoff 连框）；
`tests/test_menus.py` 的固定点击序列加了 `advance()` 容忍延迟帧。
全量 check_all 11/11。

## 0.19.0 — 2026-10-25

**`setwindow` 补全参数 + 文本排版类命令落地（12 条从桩变实现）。**

### `setwindow`：之前只读前 5 个参数，是错的

翻 `ONScripter_command.cpp` 才发现 `setwindowCommand` 和 `setwindow3Command` **都调
`setwindowCore()`** —— 参数完全一样，差别只在收尾（`setwindow` 清回看缓冲、`setwindow3`
清当前页）。所以那个"老式 5 参数"的解析纯属我们自己简化出来的：

- 参数补齐：`x,y,num_x,num_y,fsize_x,fsize_y,pitch_off_x,pitch_off_y,wait,bold,shadow,窗口串,坐标`
- **`pitch` 是偏移量**（行距 = 偏移 + 字高），不是绝对值
- `#RRGGBB` 窗口要读 **4 个**坐标 `(x0,y0,x1,y1)`，矩形宽高 = 差 + 1；之前只读 2 个、
  然后"从这里铺到画布右下角"，是近似
- 缺参数时引擎读到的就是 0（行距 0 → 所有行叠在一起）。我们兜底成字高，
  否则 `max_w = num_x * 0` 会让每个字都换行、页面直接炸
- `setwindow3` 现在真的会清当前页（引擎 `clearCurrentPage`）

### 文本排版：12 条命令

| 命令 | 关键语义（都来自源码） |
|---|---|
| `textcolor #RRGGBB` | 正文颜色（`sentence_font.color`），渲染时生效 |
| `indent n` | **每次换行后**行首插 n 个全角空格，空格**写进 page 文本**（`0x8140`）→ 影响折行与 `text()` 结果 |
| `locate x,y` | 单位是**字符格**（`setXY` 存 `x*2`，`x()` 按 `pitch/2` 算）；换页/`textclear` 归零 |
| `texthide` / `textshow` | 文本层只是不画，内容和 `page` 都还在（和 `textoff` 不是一回事） |
| `br` | `newLine()` + 页里插 `0x0a` → 一个空行 |
| `puttext "str"` | 写进文本层但**不换页、不等待、不推进剧情** |
| `clickstr "chars",line` | 真正改"哪些字符触发等点击"，页面模型按它判断（默认 `\` `@`） |
| `kinsoku` / `setkinsoku` / `addkinsoku` | 禁则表可替换/追加（`addkinsoku` 的第一个参数是**摆设**，第二个才是字符表） |
| `pagetag` | 引擎 `pagetag_flag`，我们只记状态（`getpage`/`ispage` 是存档界面翻页，仍是桩） |

保留桩的 8 条都写明原因：逐字显示（`textspeeddefault`）、竖排（`tateyoko`）、
注音（`rubyon`/`rubyoff`）、英文换行（`english`）、括号对齐（`zenkakko`）、
图层插件（`layermessage`）、点击音（`clickvoice`）。

### 顺手修的两个问题

- **测试假通过**：`test_stubs_never_shadow_real_handlers` 拿 `{去前缀的名字}` 去比
  `vars(Interpreter)` 的键（带 `cmd_` 前缀），交集永远是空。修好后立刻抓到
  `ofscpy` 既是桩又有空实现。
- **`ofscopy` / `ofscpy` 的语义一直是错的**：我原来写的是"把存档槽复制到另一个槽"，
  实际 `ofscopyCommand` 是 `SDL_RenderReadPixels` → 累积缓冲（**屏幕快照**），
  `bgcopyCommand` 第一句就调它。现在两个名字都指向同一个真实现（我方是 no-op，
  因为 `blt` 直接按图源取像素、没有累积缓冲）。

### 验证

- 测试 +12：setwindow 全参数/5 参数兜底/setwindow3 清页、textcolor 像素、
  indent 缩进、locate 与 textclear、texthide、br、puttext、clickstr、setkinsoku
- 排版校对 3 项（base/禁则/透明）几何差异全 0，像素差异在阈值内
- 全量 `check_all` **11/11**

引擎 LUT 347 条现在 = **真实现 139 + 桩 198 + `mov2..mov10`/`movl`（9）+ `linepage2`**，
桩总数 207（含 9 条 LUT 已删的老命令）。

## 0.18.1 — 2026-10-25

**探针工具加固：从"人眼看颜色"变成"自动判定"，并把引擎规则做成前置检查。**

0.18.0 的 `tools/probe_flow.py` 只用一次就暴露了两个问题：三个坑只写在文档里（下次照样踩），
变体的行号是人工数的（`skip` 的落点完全依赖这个数，第一版就因为"落点之后的行会继续执行"
把判定设计错了）。

### 先看源码，改掉一个想当然

原本打算"禁止探针里写 `for %字母`" —— 翻 `ScriptHandler::readVariable` 后确认这是错的：
`for %i` **完全合法**，前提是 define 区 `numalias` 过。引擎报 `for: missing '='` 的真正原因是
`parseInt` 对没定义的名字会把指针退回名字开头（怪点 #9），于是 `forCommand` 的
`compareString("=")` 看到的是名字。所以检查要判"有没有定义"，不是"是不是字母变量"。

顺带确认另外两条：脚本跑完是 `***** End *****` → `endCommand()` → `exit(0)`（所以画布会没，
不是"没画"）；`skip` 越界在引擎里是 UB（`getLabelByLine` 返回最后一个标签后一路找换行符），
我们是夹到脚本末尾 —— 这两条都补进了 `docs/quirks.md`（怪点 #21/#22）。

### 改动

- 脚本改为 `skip_probe(n)` / `break_probe(with_break)` 生成，**行号由构造保证**；
  加模板自检 `assert_template()`（`skip` 必须在 L6，改布局时立刻炸）
- 每个变体带期望颜色，跑完自动打印 `[OK]/[FAIL]`，有违例则退出码非 0
- 新增 `static_problems()`：起浏览器**之前**按引擎规则检查 —— `for` 变量没 `numalias`、
  `skip` 目标行超过物理末行（用 `len(lines)`，空行/注释/标签行都算）
- 三个探针坑现在都固化进代码：绝对截图路径、`TAIL = "click\n"` 自动补、裸槽号 `%100`
- 截图重试保留（headless Edge 偶尔不出图）

验证：6 个变体全部 `[OK]`（skip 1/2/3/0 + break 与对照）；故意塞一条 `for %i` 和一个
越界 `skip`，都在启动浏览器前被拦下并给出引擎层面的原因。

## 0.18.0 — 2026-10-25

**四条流程命令从桩变成真实现：`break` / `tablegoto` / `skip` / `loadgosub`。**

上一版把它们当桩，是担心"不知道 `next` 在哪，没法跳"。翻源码后发现每个都有明确依据，
而且 `break` 根本不需要找 `next`：

| 命令 | 引擎依据 | 关键点 |
|---|---|---|
| `break` | `ScriptParser::breakCommand` + `ONScripter::executeLabel` | 不扫 `next`：置 `break_flag` 后主循环**逐 token 跳过**，直到名字是 `next` 的 token 才恢复；`nextCommand` 见 flag 不自增、直接弹栈。带标签的 `break *label` 走另一条：弹一层 for 栈 + `setCurrentLabel` |
| `tablegoto` | `tablegotoCommand` | 读 0-based 序号，按逗号给后续 `*label` 编号，命中的 `setCurrentLabel`；序号越界不跳 |
| `skip` | `skipCommand` | `目标行 = 标签起始行 + current_line + n`，而执行 `skip` 那一刻 `current_line` 还没自增 → 化简成"含 `skip` 的行号 + n"；`n==0` 按 1；全局行表，可跨标签 |
| `loadgosub` | `loadgosubCommand` + `loadgameCommand` 末尾 | 读档成功后 `gosubReal(loadgosub_label, script_h.getCurrent())`，**返回地址就是存档位置** |

### 真引擎对照（`tools/probe_flow.py`，新工具）

用纯色背景当探针：`bg` 几种颜色、中间夹一条 `skip n`，截图读画面中心像素就知道落点。
脚本末尾必须放 `click` 停住，否则跑完就黑屏。

| 变体 | 参照引擎实测 |
|---|---|
| `skip 1`（L6 出发） | 绿 = 落在 L7 |
| `skip 2` | 黄 = 落在 L8 |
| `skip 3` | 白 = 落在 L9，再顺跑 L10 |
| `skip 0` | 绿 = 与 `skip 1` 相同（0 按 1） |
| 对照（循环体里 `bg`，无 `break`） | 白 |
| 循环体里 `break` + 后面的 `bg` | 黄 = break 之后的命令确实没执行 |

顺带记下两个探针坑：`for %i=0 to 0` 在参照引擎里报 `for: missing '='`（要用已定义的槽号
`%100` 或先 `numalias`），`bg` 之后脚本跑完会黑屏（要有 `click`）。

### 改动

- `break` / `tablegoto` / `skip` / `loadgosub` 四个桩删掉，改成 `Interpreter` 里的真实现
- `break` 需要"逐条跳过到 next"：新增 `_consume_break_skip()`，`run()` 与 `run_sub_sync()`
  共用；无标签的 `break` 连**同一行剩下的语句**一起丢（引擎是 token 级跳过）
- `tablegoto` / `skip` 用"pc 有没有变"决定要不要丢本行剩余 —— 序号越界时不跳、继续跑
- `Script.index_of_line()`：`skip` 按行号找指令（二分），对应引擎的 `getAddressByLine`
- 读档时补齐引擎 `loadgameCommand` 的状态复位：`break_flag=false`（我们的 `break_skip`）、
  `text_on_flag=false`；`loadgosub` 在 nest 栈恢复**之后**才 gosub，否则那一帧会被覆盖
- 测试 +8：break 跳过后半段/带标签 break/tablegoto 命中与越界/skip 三种基准/跨标签/loadgosub 往返

引擎 LUT 347 条现在的分布：**真实现 126 + 桩 211 + `mov2..mov10`/`movl` 共用一个 handler
（9 条）+ `linepage2`（在 `cmd_linepage` 里分支）**；另有 10 条 LUT 已删的老命令也有桩，桩共 221。

## 0.17.0 — 2026-10-25

**未实现的引擎命令一条一个桩：`NOOP_COMMANDS` 退休，换游戏时能查到"缺什么、缺的是什么"。**

`NOOP_COMMANDS` 那张名单只解决了"别刷 unsupported.log"，没解决"换游戏怎么定位"：
59 条挤在 `interp.py` 顶部没有任何语义；另外 178 条引擎命令连名单都没进，
真撞上就只留一行命令名，既看不出该不该实现，也查不到参数形式。

### 做了什么

- 新增 `src/onsmcp/stubs.py`：`StubCommands` mixin，**225 个 `cmd_xxx` 桩**（0.18.0 后 221）。
  每条 docstring 统一写 `用法 —— 语义 —— 为什么不实现（引擎 xxxCommand）`，
  参数沿用 NScripter 手册记号（`%var` / `$var` / `*label` / `<number>`）
- `Interpreter` 改为继承它：本类里的同名方法自然遮蔽桩，**实现某条命令时不用回头删桩**
- 删掉 `NOOP_COMMANDS`（59 条全部转成桩），`_dispatch` 里对应的分支一并去掉
- `bgcpy` / `strsph` 不设桩：它们在引擎里分别是 `bgcopy` / `strsp` 的**同一个 handler**
  （`strsph` 只多一个"竖排"开关，参数表不变），直接转调已有实现。之前当 no-op 掉，
  会让用到它们的脚本白丢一次背景快照、或整块文字精灵消失
- `state()` 新增 `stubbed`（非空时才出现）：引擎有、本项目没做，跑起来是 no-op；
  和 `unsupported`（查无此命令，多半是别的脚本文件里的宏或拼错）**分账**。
  混在一起就分不清"活没干完"和"脚本有问题"了
- `notif` 从 no-op 变成真实现。引擎里它和 `if` 是**同一个** `ifCommand`，
  只是把 `if_flag` 置成 false（`条件为假才执行后半句`）。之前它落到分派层当普通 no-op，
  **后半句会被无条件执行** —— 这是本次唯一的行为修正
- `tools/missing_commands.py` 改成三分法报告（已实现 / 桩 / 未处理），
  顺手修掉 `mov2..mov10`、`movl` 的误报：它们与 `mov` 共用 handler、没有同名
  `cmd_` 方法，之前被当成"缺实现"
- `tools/playthrough.py` 的报告与终端输出里加 `stubbed`
- 测试 +7：桩必须有 docstring、桩不许遮蔽真实现、`stubbed`/`unsupported` 分账、
  `notif` 两种条件、`has_handler` 认 mov 家族

### 覆盖率

引擎 LUT 347 条 = 真实现 122 条 + 桩 216 条 + `linepage2`（在 `cmd_linepage` 里按命令名分支）；
另有 9 条 Jh/Yuri 已从 LUT 删掉的老命令（`cd`/`cdplay`/`reset_music`/`es_snd_stop`/
`automodeoff`/`cspchar`/`defspeed`/`getz`/`skipon`）也留了桩给老脚本 → 桩共 225 个。
两款样本实际撞到的桩：万华镜 17 条（`effect`/`quakey`/`setlayer`/`loadgosub`…），
Ever17 9 条（`rmenu`/`mpegplay`/`savename`…），全是装饰、系统菜单与视频。

### 顺手发现的样本问题

`tools/missing_commands.py` 报万华镜有 2 条**真·未知**命令：`char1`（2 次）、
`overlap_long`（1 次），全脚本没有对应的 `defsub` —— 原引擎同样会打印
`command [char1] is not supported yet`，不是我们的漏洞。

## 0.16.0 — 2026-10-25

**页面模型对齐引擎：文本行累积 + `linepage`。**

之前一直是"一条文本行 = 一页"，所以：
* 名字行 `【可儿】` 和台词行被拆成两页（真引擎是同一页的两行）；
* 截图/`text()` 只显示一行，引擎显示整屏；
* `getcursorpos` 算的行数偏少。

### 引擎的真实规则（源码 + 探针双确认）

| 规则 | 依据 |
|---|---|
| 文本行累积到当前页，`processEOT` 只加换行 | `ONScripter_text.cpp` |
| `\` 与 `@` 都是 clickstr，**只等点击、不清屏** | `checkClickstr` 对两者都返回 1 |
| 清屏只在"剩余行数 <= clickstr_line"时的点击之后 | `clickWait` → `clickNewPage` |
| `linepage` 给每条文本行**自动补 clickstr** | `ScriptParser::readToken` |

真引擎探针（3 行无 `\` + 1 行带 `\`）：**一页 4 行、只停 1 次、`getcursorpos=(100,208)`**。
改完后我们三个基准全部一致。

### 两款游戏为什么表现不同

万华镜在 define 区用了 `linepage`（注释："将行末没有 `\` 的显示文本的换行视为换页"），
所以它**每行都停**；Ever17 没用，名字行+台词行才会累积成同一页（真存档 16 页里 10 页含换行）。
只做其中一个模式都会错 —— 现在按 `linepage_mode` 分支。

### 改动

- `linepage` / `linepage2` 从 no-op 改成实现（`NOOP_COMMANDS` 60 → 59）
- `_exec_text` 改为**追加**到当前页；只在 clickstr（或 `linepage` 补出来的）处停
- `@` 分段改为"追加"而不是"替换整页"
- 点击时按"页满（`num_y - clickstr_line`）"清屏，对应引擎的 `clickNewPage`
- 读档恢复的页面打 `page_from_save` 标记：脚本重跑那一行时替换它，避免同一句出现两次

### 验证

- 单测 118 → **123 项**（累积同页、linepage 每行停、满页才换页、`@` 不算清屏）
- `check_all` **11/11**（62.0s）
- 万华镜 `linepage_mode=1`、Ever17 `linepage_mode=0`，两款长跑/选项/菜单全部通过

## 0.15.0 — 2026-10-25

**与引擎的最后四条差异全部对齐；新增 `docs/quirks.md` 排查手册。**

### 1. 数值表达式里的引号串 → 0

引擎 `parseInt` 见到 `"` 时前缀扫描长度为 0，返回 `VAR_NONE` 且**指针不动**。
我们过去会 `int("123")` 转成 123。现在返回 0，且**不消费 token**（后面的 `read_str`
还能取到它），与引擎逐字一致。

### 2. 未定义名字不推进指针

`parseInt` 未命中别名时 `*buf = buf_start` 把指针退回名字开头，同一条命令的下一个参数
会把这个名字当字符串/标签再读一次。我们过去直接消费掉 token。现在同样不推进，
并且把"未定义"统一记进 `state.undefined`（以前只记 `%名字`，裸名字漏记）。

### 3. `movN` / `movl` 按逗号收尾（顺带挖出的第 4 条差异）

引擎用 `END_COMMA` 决定要不要继续读值，我们过去只看 token 是否读完 ——
所以 `movl %a,1 2` 会多读一个 2，引擎只读到 1。

这条是**第 2 条的前置条件**：如果指针不推进、而循环只看 `eof`，
`movl` 的 `for i in range(1<<30)` 会变成 10 亿次写入的死循环。

实现上不能用"下一个 token 是不是逗号"判断 —— `peek()` / `eof()` 会把逗号顺手吃掉。
改成看"上一次读取跨过的 token 区间里（含区间末位置）有没有逗号"，
这样整数（逗号被 `peek` 吃掉）和字符串（逗号留在原地）两条路径都成立。

### 4. `getcursorpos`

引擎返回 `sentence_font` 的光标位置。真引擎探针实测（`setwindow 100,100,20,3`，行距 36）：

| 场景 | 真引擎 | 我们（改后） |
|---|---|---|
| 一行文本之后 | `X=100 Y=136` | 100 / 136 |
| 25 字折成两行之后 | `X=100 Y=172` | 100 / 172 |
| 还没画文本 | `X=100 Y=100` | 100 / 100 |

关键结论：**文本显示完引擎自己换行，光标停在下一行行首** ——
所以是 `(top_x, top_y + 行数 × 行距)`，不是"末行宽度"。`NOOP_COMMANDS` 61 → 60。

实现上按当前页现算，不缓存"上次渲染的位置"：我们的绘制是懒执行的（截图时才合成），
脚本调 `getcursorpos` 时往往还没渲染过。

### 5. 新增 `docs/quirks.md`

用户要求把隐患集中记一处，方便换新游戏时定位问题。分三类：
**照抄的 13 条引擎怪点**（裸名字=槽号、`dim` +1、`cur_line` 滞后一行、`mp3` 不随存档恢复、
文本行不能以 ASCII 命令样开头……）、**11 条已知偏差**（含"每个文本行都停一次"、
`setwindow` 只解析前 5 个参数）、**排查路径表**（现象 → 先看哪个字段 → 常见原因）。

### 验证

- 单测 107 → **118 项**（引号串/未定义指针/逗号收尾 8 项、`getcursorpos` 3 项）
- `check_all` **11/11**
- `getcursorpos` 三个场景与真引擎逐值一致（探针工程 + 截图读值）

## 0.14.0 — 2026-10-25

**`save` 返回形状统一（J 组最后一项）。**

`save` 之前返回**裸路径字符串**，是 11 个工具里唯一不是 JSON 的；`load` 返回状态字典。
现在：

| 工具 | 返回 |
|---|---|
| `save(slot)` | `{ "slot": 9, "path": "...save9.dat", "size": 44605 }` |
| `load(slot)` | 当前状态（与 `click` 同构）+ `"slot": 9` |

`save` 只讲"存到哪、多大"，不掺 `line` / `waiting` —— 存档时 agent 不需要这些，
想知道位置读 `click`/`text` 的返回就行。

内部 API 不变：`GameSession.save()` 仍返回路径字符串（工具/测试里 `path = s.save(0)` 照旧），
只在 MCP 协议层组装 JSON。

**改动面**：`server.py` 两个工具、`raw_rpc_test.py` 3 条新断言（35 → 38 项）、
`test_units.py` 边界断言 + 2 项契约测试（105 → 107 项）。

**顺带**：`test_units.py` 里被发现有一段重复（`_bare_server_call` 与 4 个存档目录测试、
`test_cell_command_switches_frame` 各写了两遍），已删掉重复副本 —— 之前追加测试时
heredoc 落了两次，pytest 会重复执行但不报错，属于容易漏的坑。

## 0.13.0 — 2026-10-25

**存档收尾：目录可配 + 槽位护栏。**

### 存档目录可配（对齐引擎的 `--save-dir`）

优先级：`GameSession(save_dir=...)` → `ONSMCP_SAVE_DIR` → 游戏目录 → 用户目录。

- 引擎默认把 `save<N>.dat` / `gloval.sav` 写在游戏目录（`archive_path`），我们照做
- 装进 `Program Files` 这类只读位置时，`_dir_writable()` 真写一次探测失败，
  自动回落到 `%LOCALAPPDATA%/onsmcp/<游戏目录名>`（Linux 用 `XDG_DATA_HOME`）
- 显式指定却建不出来/不可写时抛 `SaveDirError` + hint，**不静默换地方**
- `gloval.sav` 跟着存档目录走（否则存档与通关标记会分裂到两处）
- `state()` 新增 `save_dir` 字段，读档/存档的返回值里能直接看到落在哪

### 槽位校验（只在 MCP 入口）

- `save`/`load` 限 `0..999` 的整数，越界给 `ToolError` + hint，且不落文件
- **脚本里的 `savegame`/`loadgame` 不校验** —— 引擎自带版本也不校验
  （`sprintf("save%d.dat", no)` 照写），校验了反而不一致

### 验证

- 单测 98 → **105 项**（存档目录 4 项、槽位 3 项）
- `check_all` **11/11**，50.7s
- 万华镜真机：`ONSMCP_SAVE_DIR` 指到临时目录 → `save3.dat` 44,457 字节落在那里、
  `gloval.sav` 同处、游戏目录无残留、读档回到 148 行

## 0.12.1 — 2026-10-25

**收尾 0.12.0：删掉旧的 JSON 存档残留。**

- 删掉两款游戏目录里 9 个旧格式文件（`.onsmcp_save_*.json` ×7、`.onsmcp_global.json` ×2），
  只留原版 `save<N>.dat` 与 `gloval.sav`
- `.gitignore` 去掉重复条目，存档规则改成 `save[0-9]*.dat` / `gloval.sav`；
  已用 `git check-ignore` 确认不会误伤 `tests/fixtures/engine_save0.dat`
- 清掉最后几处"自有 JSON"的表述：MCP `save`/`load` 的工具描述、README 的
  全局变量/画面状态/菜单三处、`state.py` 指向已删方法 `session._dump` 的注释
- `HANDOFF.md` 决策表第 7/10 条与工具表 `save`/`load` 就地标注为已变更

## 0.12.0 — 2026-10-25

**存档只留一套：原版 `save<N>.dat`。自有 JSON 整体移除。**

### 为什么能删

挖穿引擎的 gosub 之后确认：**引擎从来不存按钮，它相信重跑**。
`gosubReal` 只压返回地址，`setCurrentLabel` 会把 `current_line` 重设成子程序行；
再配合"`cur_line` 滞后一行"，读档从存档行的前一行开始重跑，`btndef`/`spbtn`/`btn`
自然重新注册，按钮自己回来。

我们把按钮表塞进 JSON，等于绕过了这个机制——看起来读档更快，实际是和引擎分道扬镳。

### 改了什么

| 项 | 之前 | 现在 |
|---|---|---|
| 存档文件 | `.onsmcp_save_N.json` + `saveN.dat` | **只有 `saveN.dat`** |
| 全局变量 | `.onsmcp_global.json` | **`gloval.sav`**（引擎同名同格式） |
| 读档 | 恢复到等待态，按钮表从 JSON 拿 | 清空按钮/选项表，`run()` 继续跑到下一个等待点 |

删掉的 43 个字段：原版档已有的（变量/精灵/背景/音频/页面…）、define 段重跑就有的
（别名/边界）、脚本重跑就有的（按钮/选项/层序）、引擎根本不存的（waiting/光标/按钮号），
以及两项主动放弃的超集能力——`bg_ops`（blt 合成流水）和 `stack.cont`（行内剩余语句）。

### 代价（都是"和引擎一致"的代价）

`bgcopy` 之后读档，blt 合成的那部分丢了（引擎只存背景名）；在 `btnwait` 存档，读档后
会先重跑注册命令、画面闪一下（引擎一样）；台词历史读档后清空（引擎的 Page 上限 16 屏）。

### 验证

- 单测 98 项（存档相关 12 个按新语义重写）
- `check_all` **11/11**
- 万华镜：存档 153 行 → 读档回 152 行、变量 19、精灵 49、背景一致、能继续推进
- Ever17：存档 111582 → 读档回 111580 → 重跑到 111582 停住
- 游戏内存档写出 `save2.dat`，槽号与点击位置一致，可被 `parse` 解析

## 0.11.0 — 2026-10-24

**能读写原版 `save<N>.dat`，并被真引擎验证过。** 0.9.0 时把这条判成"不做"（理由是没有
人机交接场景），现在按"最终要和原版完全一致"的目标改判为做。

### 新增：二进制存档读写器

`src/onsmcp/savefile_bin.py`，逐段照 `saveSaveFile2` / `loadSaveFile2` 实现：

```
ONS 02 08 → 字体/窗口/cursor → bg/立绘 → 1000 sprite → 变量(0..border)
          → nest → monocro/音频 → 100 bar → 100 prnum → btndef
          → 数组（裸 int，无维度信息）→ loopbgm/ruby → 256 sprite2
          → 页面文本 / 页面 tag → 行号 + 语句偏移
```

**验收标准是字节级往返**，两份真引擎样本都一字节不差：

| 样本 | 大小 | 结果 |
|---|---|---|
| `tests/fixtures/engine_save0.dat` | 42,572 | ✅ |
| `exports/ever17_web_save/save1.dat`（含 101 元素数组） | 38,666 | ✅ |

### 修掉：续跑点的三处误判

引擎的 `cur_line` 是 **0-based** 且**滞后一行**（`current_line` 要等读下一行 token 才递增）：

- 探测工程在 `savegame 0`（0-based 11）存档 → 引擎存 **10**
- Ever17 在台词行存档 → 存 **1332**（1333 才是台词）

我们原先写 `instrs[pc].line_no`（1-based、不滞后），会整体偏 1~2 行。现在改成 `line_no - 2`，
读档时用 `cur_line + 1` 反查。`cur_stmt` 也改成"从上一行行首数到当前语句的裸冒号数"。

### 新增：会话 ↔ 原版档

`GameSession.to_engine_save()` / `save_engine(slot)` / `load_engine_bytes(data)`。
背景用 `bg_source`（`bgcopy` 之后也不会写成 `*bgcpy`），精灵按 `alpha → trans`、`cell` 原样，
数组按声明顺序，页面用台词历史（上限 16 页）。

同时把自有 JSON 存档也改成 `tmp` + `os.replace` 原子写。

### 顺带：`cell` 命令

`cell 槽号,帧号` 从 no-op 改成实体（引擎 `AnimationInfo::setCell`）：存档格缩略图靠它
指定显示哪一帧，现在按指定帧渲染（越界夹到首/末格）。`NOOP_COMMANDS` 62 → 61。

### 真引擎验证（决定性证据）

OnscripterYuri web 构建 + 无头 Edge/CDP：

```
引擎写档(localvar=0) → 我们改 777 写回 → 经 CDP 写进 IndexedDB(FILE_DATA)
→ 页面 reload → loadgame 0 → 引擎读档并继续跑到 savegame
→ 导出: localvar = 777 ✅
```

再用"`to_engine_save` 生成的档"（888）复验：引擎读档后重存仍是 **888**、`cur_line=8` 一致 ✅

### 已知差异（不影响读档）

`pages`/`tags`（引擎是 pretextgosub 产物）、`top_xy`/`num_xy`/`pitch`（脚本没调 `setwindow`
时的内部默认值不同）、bar/prnum/sprite2/monocro/ruby（未建模，写默认值）、nest 栈偏移
（用行起始偏移近似）。

### 验证

- 单测 93 → **98 项**（两处往返、版本拒绝、会话映射、`cell` 切帧）
- `tools/check_all.py` **11/11**

## 0.10.0 — 2026-10-24

**数组（`dim`）真正实现，表达式/解析按引擎对齐。** 目标是"凡引擎做了的，补上；
凡做得不一样的，改成一样"——为将来写原版 `save<N>.dat` 铺路。

### 新增：`dim` 与数组变量

之前 `dim` 在 no-op 名单里，`?数组` 完全没建模。现在按 `declareDim` / `getArrayPtr` 重写：

| 语义 | 细节 |
|---|---|
| 元素数 = **声明值 + 1** | `dim ?a[100]` 分配 101 个，合法下标 0..100 |
| 只有 int | `ArrayVariable::data` 是 `int*`，没有字符串数组 |
| 行主序 | `linear = linear*av->dim[i] + idx` |
| 越界 | 引擎直接 `errorAndExit`（还不查负下标）；我们不崩，返回 0 并记 `array_oob` |
| 槽号 | 数组名走 `numalias`，也可以是纯数字（Ever17 的 `dim ?0[100]`） |

配套支持：`?a[i]` 读写（下标是完整表达式）、`%?a[i]`（元素值当槽号）、
`?a[i]` 在文本行里插值、`movN` 写连续元素、数组进存档（v4）。

**这一条被真存档验证过**：`exports/` 里 Ever17 的存档，数组段是 404 字节 = 101 个 int，
正好对上 `dim ?0[100]` 的 +1。顺带纠正了上一轮的两处误判（见 roadmap L1 末尾）。

### 修复：表达式与解析

- **括号**：`(1+2)*3` 以前括号落成字符串字面量，整条表达式算出 0；现在递归求值 = 9
- **`mod` 运算符**：`10 mod 3` 以前不认识，现在与 `*` `/` 同级
- **`movl`**：引擎的"无限个"写法，之前只支持 mov2..mov10
- **`getmousepos`**：从 no-op 变实体。它连带修掉一个真 bug —— 万华镜的存档格号是
  `(%savepos+%cursory-save_data_y)/save_height+1`，以前 `%cursory` 恒 0、括号又不支持，
  **点任何格子都写到同一个槽**；现在按点击位置算对了
- `?a[i]` 出现在字符串参数里时按引擎原样输出（引擎 `parseStr` 没有数组分支）

### 存档 v4

`arrays` 段：按声明顺序存 `{no, name, dims, data}`。引擎那边只写裸 int、没有维度信息，
我们多存 name/dims 便于自检；读档时形状仍以当前脚本的 `dim` 声明为准。

### 验证

- 单测 **78 → 93 项**（数组语义 ×8、表达式 ×3、间接槽号、文本插值、getmousepos、存档往返）
- `tools/check_all.py` **11/11**
- 两款游戏长跑正常；万华镜菜单测试的存档检查改为"校验写盘的那一份"并新增槽号断言

## 0.9.0 — 2026-10-24

**存档补上画面状态与音频状态。** 目标定为"读档后 agent 看到的世界和存档那一刻一致"，
不碰原版档互通，也不做音频播放。

### 修复：bgcopy 之后存档会变黑屏

`bgcopy` 把合成结果塞进 `bg_image`、把 `bg_name` 改成 `"*bgcpy"`，而存档只存了名字 ——
读档时 `load_image("*bgcpy")` 找不到文件，背景直接变黑。**Ever17 开局就用 bgcopy**，
所以这不是理论问题。

改法：存档记"背景来源 + blt 操作流水 + 是否烘焙过"，读档时重放：

| 字段 | 含义 |
|---|---|
| `bg_source` | 真实的背景文件名（bgcopy 不会污染它） |
| `bg_ops` | 每次 `blt` 的「图源 + 8 个参数」，按顺序重放 |
| `bg_baked` | 是否发生过 `bgcopy`，重放完要把 overlay 烘进背景 |

不存合成后的像素（1280×720 一张就上 MB），只存可重算的参数。

### 新增：精灵帧号进存档

`Sprite.cell`（引擎的 `current_cell`）随精灵一起存；`Renderer.build_sprite_image(..., cell=)`
支持取条图的任意一格（越界夹到首/末格，同 `AnimationInfo::setCell`）。
目前没有动画驱动，帧号恒为 0 —— 但存档格式已经带上它，将来加动画不用再改格式。

### 新增：音频改成"记账"（不播放）

把 26 条音频命令从 no-op 改成 handler，**只更新状态，不加载、不解码、不播放**：

- 音乐：`bgm` / `bgmonce` / `mp3` / `mp3loop` / `mp3save` / `mp3stop` / `bgmstop`
- 音效：`wave` / `waveloop` / `wavestop` / `stop`
- 循环 BGM：`loopbgm` / `loopbgmstop`
- CD / MIDI：`play` / `playonce`
- 语音与音量：`dwave` / `dwaveloop` / `dwaveload` / `dwaveplay` / `dwaveplayloop` / `dwavestop` /
  `bgmvol` / `mp3vol` / `sevol` / `voicevol`

存档新增 `audio` 段，字段与引擎 `saveSaveFile2()` 对齐：
`music` / `music_loop` / `mp3save` / `midi` / `midi_loop` / `wave` / `wave_loop` /
`loop_bgm` / `cd_track` / `cd_loop`。

**照抄引擎的两个反直觉行为**（都查过源码）：

1. `mp3`（不带 loop）的 `mp3save_flag` 是 **false** → 音乐名**不随存档恢复**，读档时当前曲目继续放。
2. `dwave`（语音）走独立声道，**引擎根本不把语音写进存档**；音量写的是 `envdata`，也不在存档里。
   这两项只留在内存，存档里刻意没有。

`NOOP_COMMANDS` 从 80 条降到 64 条。

### 验证

| 项目 | 结果 |
|---|---|
| 单测 | 71 → **78 项**（+7：blt 重放、bgcopy 烘焙、帧号、音频记账 ×4） |
| `tools/check_all.py` | **11/11**，41.7s |
| 画面一致性 | 两款游戏 save 前 / load 后截图**逐字节相同**（万华镜 1.2 MB PNG、Ever17 393 KB PNG） |
| 音频记账 | 万华镜 `bgm/wbgm06.ogg` loop、Ever17 `music/bgm21.ogg` loop，均在存档里；`unsupported` 已无音频命令 |
| 音频语义 | `mp3` 不随存档恢复、`dwave`/音量不入档 —— 单测覆盖 |

## 0.8.0 — 2026-10-24

**变量模型对齐引擎 + 全局变量（gloval）语义 + 存档格式 v3。**
这一版动的是解释器的地基：变量从"按名字存"改成"按槽位存"，行为变化是语义级的。

### 变更：变量表改成引擎的槽位模型

依据（`ONScripter-Jh` 源码）：

| 语义 | 出处 |
|---|---|
| 变量表是**按编号的槽位**，每槽同时存 `num` 和 `str`，`%5` 与 `$5` 同槽 | `ScriptHandler::VariableData` / `getVariableData` |
| `numalias 名字,槽号` 建"名字 → 槽号"映射；`%名字` 取该槽的值 | `parseInt`：命中别名后 `getVariableData(no).num` |
| **裸名字在数值表达式里返回槽号本身**（具名常量），不取值 | `parseInt`：`ret = alias_no; type = VAR_INT\|VAR_CONST` |
| 未定义的名字按 **0 号槽**（`parseInt` 注释 "assume 0"） | `parseInt` 未命中分支 |
| `stralias 名字,"文本"` 是**字符串常量**，只对裸名字生效；`$名字` 查的是 numalias | `parseStr` 的 str alias 分支 |
| 槽号可越界，引擎动态扩容 | `getVariableData` 的 `extended_variable_data` |
| socket 之外：`global_variable_border` 以上是全局变量 | `readConfiguration` 的 `value<n>` / `G<n>` |

实现：
- `State` 改为 `int_slots` / `str_slots` / `aliases` / `str_aliases`，`get_int`/`set_int`
  等按名字解析槽号；`SlotView` 供 `Args` 只读取值。
- 未定义的名字仍按 0 号槽（引擎行为），但**记一笔** `state.undefined`，
  非空时出现在 `start`/`click` 返回值的 `undefined_vars` 里 —— 移植新游戏能直接看出拼错的别名。
- `Args` 新增 `aliases` / `str_aliases` 两个入参：裸名字在数值上下文取槽号常量，
  在字符串上下文先查 `stralias` 常量。
- `mov2`..`mov10` 实现（引擎 `movCommand` 的 offset 语义：写 `槽号+i` 连续槽位），
  从 `NOOP_COMMANDS` 移除 `mov10`。

**踩到的坑（值得记）**：改完之后游戏内存档界面死循环。原因是 `for %sub1=0 to save_num`
里的 `save_num` 是**裸名字**，按新模型我错把它当"5 号槽的值"读（0），循环终点从 5 变成 0，
退出时 `%sub1` 恰好等于 1，撞上了脚本后面 `if %sub1=1 goto *save_drag_data_loop`。
修正成"裸名字 = 槽号常量"后恢复。这条正是引擎 `parseInt` 与 `%` 分支的差别。

### 新增：globalon / gloval

- `globalon` 从 no-op 变成实现（置 `state.global_on`）。
- 存档只写**一般变量**（槽号 `< global_border`）：`_dump` 里按槽号过滤。
- 读档只恢复一般变量，**全局槽保持当前内存值**（引擎从不回滚它们）。
- 全局槽在 `globalon` 时单独落到 `<game_dir>/.onsmcp_global.json`（对应引擎的 `gloval.sav`），
  在 `save()` 与 `close()` 时写；开局在 define 跑完后读回。
  > 偏差说明：Jh 只在 `definereset` 命令里读回 `gloval.sav`，而手册对全局变量的定义是
  > "跨重启保留其值"。两款实测游戏都用它存设置项/通关标记（`textspeed` / `bgmvol` /
  > `gameclear` / `V_08`），所以按手册在开局读回。不设 `globalon` 的游戏完全不受影响。

### 变更：存档格式 v3

- 变量与字符串改成**槽号键**（`"3": 10` 而不是 `"hp": 10`），只含一般变量。
- 新增字段：`aliases` / `str_aliases` / `global_border` / `variable_range` / `global_on` /
  `history`（台词历史）/ `ui_sprites`（按钮层文字精灵）/ `story_line` / `story_label` /
  `last_cursor` / `last_button` / `tachi_visible`。
- `btndef` 的位图不进存档（只存文件名），读档时按名字重新载入 —— 修掉"读档后 `blt` 静默失效"。
- **版本校验**：`_restore` 检查 `version`，不符时抛 `SaveFormatError` 并带 hint，
  不再"缺字段就按默认值拼一个半坏状态"。
- `load()` 对损坏的 JSON 也给结构化错误。
- 游戏内读档失败不再静默吞掉（原来 `except: pass`），改成写日志。

### 验证

| 项目 | 结果 |
|---|---|
| 单测 | 61 → **71 项**全过（新增 9 项变量/存档语义 + 1 项 movN） |
| `tools/check_all.py` | **11/11**，39.1s |
| 万华镜 | border 1500、424 别名、未定义引用 0；2000 步长跑正常推进（8 个标签） |
| Ever17 | border 500、151 别名、未定义引用 0；1200 步长跑 2 次选项全部跳对 |
| 语义实测 | 一般变量读档恢复 ✓、全局槽不被回滚 ✓、`globalon` 跨会话读回 ✓ |

### 顺带修正的认知

- Ever17 其实**也调了 `globalon`**（第 9 行，前面有缩进，早先按 `^\nglobalon` 统计漏掉了）。
- 两款游戏的别名里都有大量"具名常量"用法（`save_num,5` / `save_height,130`），
  之前靠"把别名当变量初值"的巧合工作，现在按引擎语义走。

## 0.7.1 — 2026-10-24

纯清理，**不改行为**：这一版只删死代码、修脏名单、补文档口径。

### 修复
- **`cmd_btndef` 定义了两次**（`interp.py` 按钮区 + `blt` 区），后一份覆盖前一份。
  删掉按钮区那份旧的——它是 0.5.0 修「`btndef` 要吃引号串」时没删干净的残骸，
  旧版遇到 `btndef "x.png"` 会静默清空、不登记图源。现在只剩一份正确实现。
- **`NOOP_COMMANDS` 名单不干净**：`transmode` 已有 handler 却还挂在 no-op 里；
  `dwave` / `saveon` 在各分组重复出现。重新按「音频视频 / 动画转场 / 菜单装饰 /
  配置项 / 存档 / define 杂项」归类，并加注释说明"有 handler 的命令不许进名单"。
  名单 81 → 80 条，与 handler 交集为空。
- `session.py` 里 `self.interp.encoding = loaded.encoding` 连写两次（重复赋值）。
- **`dim` 的文档口径错了**：README 把 `dim` 列在"已实现"里，实际它一直是 no-op
  （`?数组` 变量没实现；万华镜仅用于存档缩略图缓存）。README 已改为 no-op 并说明原因。

### 移除（死代码）
- `GameSession._first_arg()` —— 无调用方。
- `Renderer.load_cell_image()` —— 无调用方（条图第 0 格缓存已由 `build_sprite_image`
  走 `_load_raw(cache=False)` 承担）。
- `Renderer.first_cell()` —— 标注"兼容旧接口"，实际无人调用。
- `render.py` 的 `IMAGE_EXT`、`MAX_SPRITE_BYTES`（后者是 160 MB 的旧上限，
  真上限是 `max_image_mb=96`，留着会误导）。
- 未使用的 import：`session.py` / `scriptfile.py` 的 `re`，`render.py` 的 `Page`。
- `render.py` 里重复的「文本排版」分隔注释。

### 工程
- **仓库纳入 git**（此前只有 `.gitignore`、没有 `.git`）：初始提交收录 48 个文件、
  13.9k 行；游戏素材（`ever17/`、`*.nsa`、`*.7z`）、`.venv`、校对截图仍按 `.gitignore` 排除。
- 验证：单测 61 项全过；`tools/check_all.py` 11/11（39.6s，清理前后一致）。

## 0.7.0 — 2026-10-23

> **注意**：本版移除了 `state` 与 `script_trace` 两个 MCP 工具（语义未定稿前不暴露），
> 工具从 13 个减到 11 个。`start` / `click` 的返回值本身就是完整状态。

### 变更
- **精简 11 个工具的描述**：总字数 847 → 719。主要改动：
  - `start`：去掉与服务器 `instructions` 重复的"同时开多个游戏时靠它区分"，
    "textgosub 钩子"改成 agent 能懂的"游戏内菜单（textbtnwait）"，
    ";$S / ;mode"这类脚本内部语法改成"脚本自带的分辨率"
  - `click`："注意："开头的长句改成直述，去掉"相当于点了空白处"这类铺垫
  - `text`：去掉"便于理解对话上下文"（agent 不需要被解释用途）
  - `screenshot`：去掉"客户端与视觉模型可直接看"（MCP 图片块本来就是给它们看的）
  - `choices`：去掉"说明当前在等什么"（hint 本身就说明了）
- **`screenshot` 的裁剪参数改名为 `rect`**，取值仍是列表形式 `[x, y, w, h]`；
  说明写在工具描述里（"rect 是游戏屏幕上的矩形区域"），不再用
  `Annotated`/`Field` 给参数挂描述。
- **`buttons()` 与 `screenshot()` 的描述不再互相引用**，各自只说自己那件事。
- 相应地，session 层 `Session.screenshot()` / `Session.screenshot_bytes()`
  的 `region` 参数改名为 `rect`，内部辅助函数 `_apply_region()` 改名 `_apply_rect()`。
- **`screenshot` 返回 MCP 图片块**（`format='image'`），客户端与视觉模型可以直接看画面。
  只保留两种模式，**都不写任何文件**：
  - `image`（默认）：返回 MCP `image` content 块（base64 + mimeType）
  - `base64`：返回 base64 文本 JSON（此前它会先落盘再读回来）
  - ~~`path`~~ **已移除**（存盘 + 返回路径），连同 `path` 参数一起删掉；
    非法 format 会返回结构化错误并提示可选值
- MCP 工具不再创建游戏目录下的 `.onsmcp_shots/`；落盘能力只保留在 session 层
  （`Session.screenshot(path=...)`），供内部工具 `run_scene` / `calibrate_layout` 留档用
- 新增 `Session.render_frame()`（只合成不落盘）与 `Session.screenshot_bytes()`（返回 PNG 字节）。
  裁剪改为在内存里完成，不再"落盘 → 重新打开 → 覆盖保存"。
- 此前同一版本里已经改过：`region` 改成列表形式、`screenshot` 去掉 `max_width`
  （连带移除 `Session.screenshot_bytes(max_width=...)` 与 `_apply_scale()`）、
  `buttons()` 描述去掉"注册顺序≠视觉顺序"的长段注意事项。

### 移除
- **`state` 工具**：状态信息本来就包含在 `start` / `click` 的返回值里
  （waiting / label / line / pc_label / pc_line / in_hook / stopped / page /
  has_more_pages / unsupported / memory），agent 每次操作后自然拿到。
- **`script_trace` 工具**：逐行脚本能力保留在 `Session.trace()`，
  供内部工具（`tools/run_scene.py`）使用，不再暴露给 agent。
- **`start` 的 `agent_hints` 参数**与 `ONSMCP_AGENT_HINTS` 环境变量：
  原为 G2/G4 的开关，现随两个工具一并移除。
- 内部清理：`Session._hint_fields()` / `_summarize()` / `_scene_id()` /
  `ENGINE_LABELS` / `_BG_CMDS`，`Interpreter.bg_log`，`Script.line_label`。

### 新增
- **`tools/play_via_mcp.py`**：用**真实 MCP 协议**（stdio + JSON-RPC：
  initialize → notifications/initialized → tools/list → tools/call）当客户端，
  像 agent 一样把游戏玩一遍。已进 `tools/check_all.py`（"MCP 试玩"一项）。
- **G1 文本上下文**：`text(history=N)` 返回最近 N 句台词的滑动窗口。
  解释器逐页记录 `history`（含说话人、行号、标签，上限 200 条）；
  `text()` 仍只给当前页，行为向后兼容。
- **G5 工具级提示**：`choices()` 在非选项界面返回 `{choices: [], hint}`，
  `choose()` 越界时补 `hint`；hint 按当前状态给出具体下一步该调什么。
- 解释器新增 `bg_log`：记录每次换背景后的真实文件名（宏 `bg01` 内部设背景时也能记到）。

### 中间态：G2 / G4 曾加后删（见上方"移除"）

本版一度实现过下面这些，语义未定稿，随后整体移除，**最终不包含**：

- **G2 trace 聚合摘要**：`script_trace()` 在 `agent_hints` 开启时返回 `{lines, summary}`，
  `summary` 汇总换过的背景（真实文件名）、说话人、选项、等待次数、常用命令、经过的标签。
- **G4 语义化状态字段**：`state()` 在 `agent_hints` 开启时新增
  `in_choice` / `can_advance` / `speaker` / `scene` / `background`。
- **开关 `agent_hints`**：`start(agent_hints=True)` 或环境变量 `ONSMCP_AGENT_HINTS=1`。
- **语义定义文档** `docs/agent-api-semantics.md`：逐字段的含义、取值来源、已知歧义，
  以及 7 个待拍板问题（该文档已随 G2/G4 删除）。

### 其他变更
- `script_trace()` 的返回形状曾从裸数组改成 `{lines, summary}`（协议测试断言同步更新）。
- `script_trace(reset=)` 语义明确化：`reset=True` 只给上次查询后的新内容；
  `reset=False` 给从会话开始（define 区之后）到现在的全部内容。
  （`script_trace` 工具本身随后被移除，能力保留在 session 层。）
- 版本号 0.6.0 → 0.7.0；单测 56 → **61 项**。

### 修复
- `script_trace(reset=False)` 拿不到 `start()` 期间的执行：原来只有一个起点标记，
  拆成 `_trace_origin`（会话起点，排除 define 区）和 `_trace_mark`（上次 reset 起点）。

### 修复（试玩实测后）
- **`click()` 与 `buttons()` 的工具描述补上两条实测结论**：
  ① 等待点是按钮时，不传坐标相当于点空白处、**不会前进**，必须先 `buttons()` 拿矩形；
  ② `buttons()` 返回的是**注册顺序**，不等于屏幕视觉顺序
  （标题菜单里 START/LOAD/OPTION/QUIT 的编号与上下位置不对应），
  要按位置点需自行按 `rect` 的 y 排序。

### 修复（演示实测后）
- **`state()` 报的位置不对**：选项界面时 PC 已在 `*customsel`，但 `state()` 报的是上一句
  台词的行号（`story_line` 只在文本行更新）。改成只有 PC 停在 textgosub 钩子里才用
  `story_line`，其余用 PC 真实位置。
- **`summary.labels` 只有宏名**：拆成 `scenes`（剧情标签）/ `macros`（宏标签）/ `labels`（全部），
  并排除引擎内置界面标签。
- **`state().scene` 改成从背景文件名提取场景号**（`ev/w08_04_1_002.png` → `w08_04`）——
  这些"剧情段"在脚本里没有对应标签，背景名才是最可靠的场景标识。

### 验证
- `tools/check_all.py` 10/10 项全过（49.8s）。
- 新增单测 8 项：历史记录、滑动窗口、语义字段、选项态识别、trace 摘要、hint、
  选项界面的真实 PC 位置、场景号提取。

## 0.6.0 — 2026-10-23

### 新增
- **透明模式（trans_mode）全套实现**：新增 `spritetag.py` 按引擎语法解析精灵 tag
  （`:a` / `:l` / `:r` / `:c` / `:s` / `:m遮罩` / `:#RRGGBB` / `!调色板` + `/格数,时长`），
  并按 `AnimationInfo::setupImageAlpha` 的规则建 alpha 通道：
  - `alpha` 模式 + **没有 alpha 通道** → **用图片右半当 alpha 通道**，宽度减半，
    `alpha = 255 − 掩码红通道`，掩码按每格分别取
  - `leftup` / `topright` → 左上/右上角像素色作透明键
  - `copy` → 完全不透明（连自带 alpha 也丢弃）
  - `mask`（`:m遮罩.bmp`）→ 用另一个文件当遮罩，横向平铺
- **`transmode` 命令**：设置全局透明模式（两款实测游戏都设了 `alpha`）。
- 文本框图片也按同一套规则在 `setwindow3` 那一刻烤好（引擎就是那时建好窗口图的）。
- 文字精灵支持**多段颜色**：正文里的 `#RRGGBB` 会切换后续文字颜色。
- 排版校对新增 `--corpus alpha`（半透明文本框）与 `--corpus page`（分页）语料，
  `check_all.py` 增加到 10 项。

### 修复
- **JPG/BMP 精灵宽度被减半**的隐患：此前没有实现"右半当 alpha"，Ever17 的选项按钮
  `esystem/csel_btn.jpg` 上的绿色条直接显示在按钮上（现在与参照引擎一致，被遮罩去掉）。
- 长条动画图解码后不再进 LRU 缓存（60 格的条图能占几百 MB）。
- 文字精灵的 tag 解析（字号/颜色/正文）此前会把 `2;` 之类的残留吃进正文。

### 验证
- 半透明语料与参照引擎：几何全同，对齐缩放后像素差 0.08%。
- 禁则语料与参照引擎：行数 4/4、字高 21.5/21.5、行距 35.7/35.7、左右边界 301/1130 全同。
- 单测 49 → 56 项；Ever17 1200 步长跑无卡死；万华镜 12 处选项全对。

## 0.5.0 — 2026-10-23

### 新增
- **立绘**（`ld` / `cl`）：引擎的 tachi 是独立于 `lsp` 精灵的一套，位置由引擎自动计算
  （x = 画面宽×(no+1)/4 − 图宽/2，y = 底线 − 图高）。Ever17 的角色立绘由此才画得出来。
- **画面贴图**：`blt`（把 `btndef` 图的一块贴上去）、`bgcopy`（把当前画面冻成背景）、
  `ofscpy` / `repaint`（no-op）。
- **选项文字按钮**：`cselbtn` 生成文字精灵 + 矩形按钮，并画在**按钮层**（引擎里 ButtonLink
  最后绘制，压在所有层之上）；`selectbtnwait` 与 `btnwait` 同义。
- `reset`（回标题）、`end`、`getcursorpos2`、`systemcall`、`underline`。
- `tools/missing_commands.py`：对比脚本实际用到的命令与已实现/有意 no-op 的命令，
   Ever17 报 0 缺口。
- 排版校对增加两套语料：`--corpus kinsoku`（标点禁则）、`--corpus page`（分页）；
  `check_all.py` 增加到 9 项。

### 修复
- **`len` 返回字节数**（引擎用 `strlen`）。GBK 汉字 2 字节，Ever17 靠它算选项居中，
  按字数算整体偏右 7.5px/字。
- **`csp -1` 清空全部精灵**（引擎 `no == -1` 遍历所有 sprite），原来只删 id=-1，
  导致选项界面的按钮底图清不掉。
- **`btndef` 支持引号串**（`btndef "background\2.png"`），原来只认裸词，`blt` 拿不到图源。
- **禁则（kinsoku）**：行首禁则字符（`」』）］｝、。，．。？！ヽヾゝゞ々ー`）不再落到行首
  （悬挂到上一行末），行尾禁则字符（`「『（［｛`）不再留在行尾（挤到下一行）。
- **分页规则**：引擎不会按文本框高度自动切页（折出几行就画几行，超出的溢出到框外），
  我们原来按 `num_y` 切片，会比引擎多一次点击。

### 验证
- 禁则语料与参照引擎逐项对齐：行数 4/4、字高 21.5/21.5、行距 35.7/35.7、
  左右边界 301/1130 全同，对齐缩放后像素差 0.28%。
- Ever17 1500 步长跑：4 次选项、无卡死、内存 143MB。

## 0.4.0 — 2026-10-23

### 新增
- **`nscript.dat` / `nscr_sec.dat`**：直接读未解包的原始发布版。`nscript.dat` 是
  逐字节 `^ 0x84`，`nscr_sec.dat` 是 `^` 5 字节 magic 循环；`nscript.___` 需要 EXE key table，
  给出可读错误而不是崩掉。
- **`.nsa` 归档直读**（`archive.py`）：NSA/SAR 索引 + 无压缩/LZSS/SPB/NBZ 解压，
  `mmap` 不整包载入。自动判字节序（NSA 有的是大端、有的是小端）。
- **统一资源层**（`files.py`）：磁盘优先、归档兜底，渲染与脚本共用一条路径。
- **脚本首行配置**：`;$S<w>,<h>G<n>`、`;mode800/400/320`、`value<n>`、`v<n>` 决定
  分辨率、全局变量边界、变量上限。`start(width=0)` 表示"用脚本头的"。
- **字体回退**：显式指定 → `ONSMCP_FONT` → 游戏 `default.ttf` → 系统 CJK 字体；
  用"不同汉字点阵是否相同"判断豆腐块并自动换下一个。
- **多会话**：`start(session="名字")`、`sessions()`、`close(name)`，其余工具都可传 `session`。
- 多分片脚本：`0.txt` + `1..99.txt` / `00.txt` + `01..99.txt` 自动拼接。
- `state()` 增加 `script_source`、`resolution`、`config`。

### 修复
- **数字变量名**：`%1` / `%101` / `$0` 原来分词失败（要求字母开头），Ever17 的标题菜单
  因此点不动 —— 这是"换游戏就跑不起来"的根因。
- UTF-8 探测只认汉字，纯假名的日文脚本会被误判成 GBK；现在汉字或假名任一即可。

### 验证
- Ever17（原始发布版，800×600，GBK）从标题进正文，背景/立绘/文本框/台词全部正确。
- 打包版与解包版跑同样 40 步，渲染结果**逐像素完全相同**。
- arc2 的 LZSS/SPB 条目解出来与解包文件**字节一致**。
- 新增 `tests/test_portability.py`（30 项），`check_all.py` 增加到 8 项。

## 0.3.0 — 2026-10-23

### 新增
- **游戏内菜单**（`start(hooks=true)`）：接通 `textgosub` 钩子，等待点变成脚本自己的
  `textbtnwait`；右键（`click(button="right")`）打开菜单，存/读/回想/设置都可点。
- `click(button=...)` 支持 `left` / `right` / `wheelup` / `wheeldown` / `esc` / `space`，
  对应 `btnwait` 的 0 / -1 / -2 / -3 / -10 / -11。
- 新命令：`strsp`、`bar`/`barclear`、`split`/`mid`（含 `$%var` 动态变量名）、
  `savegame`/`loadgame`/`savefileexist`/`savetime`（回调注入，写自有 JSON）。
- **包入口**：`pyproject.toml` + `src/onsmcp/__main__.py`，
  支持 `pip install -e .`、`python -m onsmcp`、`ons-mcp` 三种启动方式。
- **日志模块** `onsmcp/log.py`：一律写 stderr，`ONSMCP_LOG` 控制级别（debug…silent）。
- **结构化错误**：所有工具捕获异常并返回 `{"error": {type, message, hint}}`，不再抛裸异常。
- **超时保护**：解释器加墙钟 `deadline`，`start`/`click` 默认 10 秒预算
  （`ONSMCP_TIMEOUT` / `start(timeout_s=...)`），超时停下并在 `state().stopped` 报告。
  步数上限也会写 `stop_reason`。
- **统一检查入口** `tools/check_all.py`：7 项、独立进程与超时、失败非 0 退出、结果落 `docs/checks.json`。
- `state()` 增加 `stopped`、`pc_label`、`pc_line`、`in_hook`、`memory`、`unsupported.first_line`。
- `load(slot)` 在槽位不存在时给出可读错误而不是抛 `FileNotFoundError`。

### 修复
- 引号字符串里的 `%var` / `$var` 不替换，导致 `lsp 299,":s/30,30,1;#88FFFF$name"` 画不出名字。
- `#RRGGBB` 被词法器拆成 `#` + 字母，`strsp` / `bar` 的颜色参数失效。
- `textbtnwait` 没记住 `%bwait` 变量名，菜单点击结果写不回去（整个菜单点不动）。
- 开钩子后 `state().label/line` 一直报 `text_btn`，改为报剧情位置 + `pc_*` 报执行点。

## 0.2.0 — 2026-10-23

### 新增
- **按钮系统**：`btn` / `spbtn` / `exbtn` / `exbtn_d` / `btnwait`，命中测试后注册优先，
  ctl 支持 `P554C555` 与 `C100-105` 区间；命中区 = 精灵图片矩形。
- **选择肢链路**：`csel` → `*customsel` → `getcselnum`/`getcselstr` → `btnwait` → `cselgoto N`。
- **agent 接口**：`choices()`（用选项文本精灵落点反查按钮）、`choose(index)`、`buttons()`。
- **存档加固**：连同 `gosub` 栈、`for` 栈、精灵表、按钮表、选项表一起存，宏/循环中途也能恢复。
- **图片缓存 LRU**：按字节预算（默认 320 MB）淘汰；多格条图先读文件头判尺寸，
  超 96 MB 直接跳过，只缓存第 0 格。修前 400 次点击吃 2.45 GB / +1.81 GB RSS，
  修后 319 MB / +3 MB。
- **自动推进器** `tools/playthrough.py`：选项策略、卡死检测、报告。
- **排版校对** `tools/calibrate_layout.py` + `compare_layout.py` + `make_refgame.py`：
  以 OnscripterYuri web 构建为参照，几何 6 项零偏差，像素差 0.08%（抗锯齿底噪）。

### 修复
- 精灵绘制顺序：引擎是 **id 从大到小**（id 小的压在上面），`humanz` 分文本框上下两层；
  原来按升序画，选项文字被按钮图盖住。
- 文本框图片按 **copy 语义**绘制（alpha 只当遮罩），原实现 `alpha_composite` 会透出底图。
- 跳过 `textgosub` 钩子时必须每页自己 `texton`，否则 `screen_clear` 的 `textoff` 让台词全消失。

## 0.1.0 — 2026-10-23

### 新增
- 命令集统计：引擎 LUT 347（Jh）/ 348（Yuri）条 × 游戏实际 128 种 → `docs/command-inventory.md`。
- 脚本解析：`0.txt` / `nscript.dat`，GBK / UTF-8 / CP932 / Big5 自动探测。
- 解释器：`label`/`goto`/`gosub`/`if`（含 `&&` `||`）/`for`/变量运算/`defsub` 宏。
- 渲染：`bg`、`lsp`/`lsph`/`vsp`/`csp`/`amsp`、`setwindow3`、文本排版与名字。
- MCP 工具 9 个：`start`/`state`/`text`/`screenshot`/`click`/`script_trace`/`choices`/`save`/`load`。
