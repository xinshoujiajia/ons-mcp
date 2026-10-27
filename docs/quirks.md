# 引擎怪点与已知偏差（排查手册）

> 用途：**换新游戏测试时先看这份**，避免把"引擎本来就这样"当成我们的 bug，
> 也避免把"我们还没做"当成引擎问题。
>
> 两类内容要分清：
> * **照抄的怪点** —— 引擎就这么干，我们跟着做，**不要"修"**；
> * **已知偏差** —— 我们和引擎不一样，可能是 bug，也可能是有意为之（写明原因）。
>
> 想知道"某条命令我们到底做了没、为什么没做"：引擎有而我们没做的命令都在
> `src/onsmcp/stubs.py`，一条一个桩，docstring 里写清了参数形式与不实现的原因。

---

## 一、照抄的怪点（不要"修"）

| # | 现象 | 引擎依据 | 触发条件 / 影响 |
|---|---|---|---|
| 1 | **裸名字在数值表达式里是"槽号"不是"值"** | `parseInt` 未命中前缀时 `ret = alias_no; type = VAR_INT\|VAR_CONST` | 脚本拿它当具名常量：`for %i=0 to save_num`。**曾把这里当成变量值读，导致万华镜存档界面死循环** |
| 2 | 未定义的变量名 → **0 号槽**，不报错 | `parseInt` 注释 "assume 0" | 拼错别名时静默写到 0 号槽。我们额外记进 `state.undefined` → `state()["undefined_vars"]` |
| 3 | `dim ?a[100]` 分配 **101** 个元素（合法下标 0..100） | `declareDim`: `dim[i] = array.dim[i] + 1` | 越界时引擎直接 `errorAndExit`（且不查负下标）；我们返回 0 并记 `array_oob` |
| 4 | `mp3` 的曲目**不随存档恢复** | `mp3Command` 里 `mp3save_flag = false` | 读档后当前曲目继续放，不是存档里的。`dwave` 语音与音量也**不入档** |
| 5 | 存档的 `cur_line` 是 **0-based 且滞后一行** | `current_line` 要等读下一行 token 才递增 | 写档用 `line_no - 2`，读档用 `cur_line + 1`。差一行会导致读档后从半句话开始 |
| 6 | `bgcopy` 之后存档只留**背景文件名** | `saveSaveFile2` 存 `bg_info.file_name` | `blt` 贴上去的像素与烘焙结果**都不在档里**，靠读档后脚本重跑还原 |
| 7 | 存档里**没有按钮表**，读档靠脚本重跑注册 | `loadSaveFile2` 读完 `cur_stmt` 就返回 | 所以我们的读档会清空按钮表、让脚本重新执行 —— 存档在 `btnwait` 时画面会"闪一下" |
| 8 | 数值表达式里的**引号串得 0** | `parseInt` 见到 `"` 时前缀扫描长度为 0 → `VAR_NONE`，指针不动 | `mov %a,"123"` 的值是 **0**（不是 123）。别再"顺手转成数字" |
| 9 | 未定义名字时**指针退回名字开头** | `parseInt`: `*buf = buf_start` | 同一条命令的下一个参数会把这个名字当字符串/标签再读一次。我们把"不消费 token"也实现了 |
| 10 | `movN` / `movl` 用**逗号**决定要不要继续读 | `movCommand` 的 `END_COMMA` | `mov3 %a,7 8` 只写 7（空格不是分隔符）。曾按 `eof` 判断，`movl %a,1 2` 会多读一个 2 |
| 11 | 一条文本显示完，引擎**自己换行**，光标停在下一行行首 | `FontInfo::newLine` | `getcursorpos` 返回 `(top_x, top_y + 行数 × 行距)`。实测单行 (100,136)、折两行 (100,172) |
| 14 | **文本行不是一页**：连续文本行累积到同一页，`processEOT` 只加换行 | `ONScripter_text.cpp` | 页面在"剩余行数 <= clickstr_line"时点击后才换页。实测：3 行无 clickstr + 1 行带 `\` → 一页 4 行、只停 1 次 |
| 15 | **`linepage` 会给每条文本行自动补 clickstr** | `ScriptParser::readToken`：mode 1 补 `\`、mode 2 按剩余行补 `@`/`\` | 万华镜用了 `linepage`（"行末没有 `\` 的换行视为换页"），所以它每行都停；Ever17 没用，名字行+台词行才会落在同一页 |
| 16 | **`@` 和 `\` 是同一种 clickstr** | `checkClickstr` 对两者都返回 1 | `@` 只等点击、不单独清屏；清屏只由"页满"触发 |
| 17 | **`notif` 就是取反的 `if`** | `ScriptParser_command.cpp`：`if (isName("notif")) if_flag = false;` | `notif <条件> <命令>` 在**条件为假**时执行后半句。它和 `if` 是同一个 handler，别当成独立命令处理（否则后半句会被无条件执行） |
| 18 | **`break` 之后是"逐 token 跳过到 `next`"** | `executeLabel`：`if (break_flag && !isName("next"))` 那个分支 | 不但循环体后半段不执行，**同一行 `break:xxx` 里的 `xxx` 也不执行**；而且 `nextCommand` 见到 flag **不自增**变量、直接弹栈。`break *label` 走另一条：弹一层 for 栈 + `setCurrentLabel`，不等 `next` |
| 19 | **`skip n` 的基准是"含 `skip` 的那一行"** | `skipCommand`：`start_line + current_line + n`，而主循环要等 `parseLine` 返回后才 `++current_line` | 所以化简成"`skip` 所在行号 + n"，`n==0` 按 1；行号是**全局行表**，允许跨标签。真引擎探针（`tools/probe_flow.py`）：`skip 1/2/3` 分别落到下 1/2/3 行，`skip 0` 与 `skip 1` 同效 |
| 20 | **`loadgosub` 的返回地址是"存档位置"** | `loadgameCommand` 末尾 `gosubReal(loadgosub_label, script_h.getCurrent())` | 标签体里 `return` 回到存档那一行；同一处引擎还会复位 `break_flag`、`text_on_flag`、按钮表、选项表 |
| 21 | **`skip` 越界在引擎里是 UB** | `getLabelByLine` 超出最后标签时返回**最后一个**标签，`getAddressByLine` 再 `while(l>0)` 一路找换行符 | 会读过脚本尾部（可能崩、也可能跳到垃圾）。我们夹到脚本末尾 —— 这是有意的保守，不是 bug |
| 22 | **脚本跑完 = `exit(0)`，不是"停住"** | `executeLabel` 结尾打印 `***** End *****` 后 `endCommand()` → `quit()` + `exit(0)` | 探针脚本末尾必须有 `click`（阻塞在事件循环里），否则 web 构建进程一退画布就黑，截出来一片黑很容易被误读成"命令没执行到" |
| 23 | **`setwindow` 与 `setwindow3` 参数完全一样** | 两个 Command 都调 `setwindowCore()`，差别只在收尾：`setwindow` 清回看缓冲，`setwindow3` 清当前页 | 别再按"老式 5 参数"写 `setwindow`：`pitch` 是**偏移量**（行距 = 偏移 + 字高），`#RRGGBB` 窗口要读 **4 个**坐标。缺参数时引擎读到的就是 0（行距 0 = 所有行叠在一起），我们兜底成字高 |
| 24 | **`indent` 是"每次换行后"缩进，不是首行缩进** | `newLine()` 之后 `for(i<indent_offset) advanceCharInHankaku(2)`，并把 0x8140 写进 page 文本 | 缩进会进 `text()` 的结果、也占行宽 —— 所以它影响折行位置，不只是"看起来缩进" |
| 25 | **`locate` 的单位是字符格，换页就归零** | `setXY(x,y)` 存 `x*2`，`FontInfo::x()` 按 `xy*pitch/2 + top_xy` 算；`clearCurrentPage()` → `font.clear()` → `setXY(0,0)` | `locate 2,1` = 右移 2×pitch_x、下移 1×pitch_y；它的效果只持续到下一次换页/`textclear` |
| 26 | **`ofscopy` / `ofscpy` 不是"复制存档槽"** | `ofscopyCommand`：`SDL_RenderReadPixels` → `accumulation_surface`（屏幕快照进累积缓冲） | `bgcopyCommand` 第一句就是它。名字容易望文生义，`blt` 的图源在这套缓冲里；我们没有累积缓冲，所以是 no-op |
| 27 | **移植脚本的 `[voice\|needClear]` 第 2 段是"这句要不要清页"** | 引擎把整段 tag 交给 `gettag`，脚本自己 `split $0,"\|",$voice,$needClear`（Ever17 的 `*procPreGo`）；被注释掉的两行 `if $needClear==1 textclear` / `==0 locate` 就是原作者的意图 | `needClear=1` → 起新页（上一句消失），`needClear=0` → 续在前一页（名字行+台词行同屏）。**不解析它就会出现"整段话堆一页"**，还会连带帧内容错位、场景切换提前。Ever17 与万华镜的差别就在这：万华镜靠 `linepage`，Ever17 靠标签 |
| 28 | **长 `delay` 是演出停留，不能直接 no-op** | Ever17 的章节画面是 `bg "…cal_501.jpg",10,1000` + `delay 1000`，紧跟着 `bgload` 会覆盖它 | `delay` 直接返回 → 两次换背景在同一次 run 里连续执行，**那张画面一帧都不会被合成**。我们把 `>=800ms` 的 delay 退化成"留一帧的暂停"（短 delay 照旧跳过，Ever17 里 280 多次 30~180ms 是动画同步） |
| 12 | **文本行以"命令样"的 ASCII 开头会被当命令** | `readTokenTop` 先按命令查 LUT | 探针脚本里写 `RESULTX=...` 会报 `command [resultx] is not supported yet!!` 并 `***** End *****`。**写探针时文本行必须以中文/引号开头** |
| 13 | `setwindow` 的 pitch 参数是**偏移量**，不是绝对值 | `setwindowCore`: `pitch_xy = readInt() + font_size_xy` | 见"已知偏差 #4" |

---

## 二、已知偏差（可能是 bug，也可能是故意）

| # | 偏差 | 现状 | 影响 / 何时该修 |
|---|---|---|---|
| 1 | ~~每个文本行都停一次~~ → **已对齐**（0.16.0） | 见下方怪点 #14/#15：`linepage` 决定要不要每行停，现在两种模式都支持 | — |
| 2 | ~~`getcursorpos` 的 `indent_offset` 缩进~~ → **已对齐**（0.19.0） | `indent n` 的缩进以全角空格写进 page 文本，行宽和光标位置自然一致（见怪点 #24） | — |
| 3 | `getcursorpos` 只在"整页画完"时有意义 | 我们不分逐字显示，整页一次性成像 | 逐字显示中途取光标会得到"整页结束"的位置 |
| 4 | ~~**`setwindow` 只解析前 5 个参数**~~ → **已对齐**（0.19.0） | 现在和 `setwindow3` 共用一套解析（引擎本来就都调 `setwindowCore`），pitch 偏移、窗口图/色、4 个矩形坐标都读了 | — |
| 5 | `bar` 画成实色块 | 原版是九宫格条 | 画面亮度/外观不同，不影响数值与点击（万华镜 4 次都在存档/回想界面） |
| 6 | 按钮无 hover 高亮 | `ctl` 已解析未应用 | agent 用 `buttons()` 拿矩形点击，不受影响 |
| 7 | `ruby` 注音 / `monocro` 滤镜 / `windowback` 层序 | 未做 | 万华镜 ruby 1 次、monocro 0 次 |
| 8 | `cell` 只能切帧，没有定时器 | 需要动画驱动的脚本不会自己动 | 存档格缩略图正常；真做动画时不用改存档格式 |
| 9 | `nscript.___` 读不了 | 需 EXE 里的 key table | 换 `0.txt` / `nscript.dat` |
| 10 | NBZ 压缩只有解压代码 | 没有实测素材 | 遇到 NBZ 压缩的 `.nsa` 先确认能解出资源 |
| 11 | 音频只记账不播放 | `bgm/wave/...` 只更新 `state.audio` | 不影响存档与剧情；agent 听不到 |
| 12 | ~~会改流程的命令桩掉会跑错~~ → **已实现**（0.18.0） | `break` / `tablegoto` / `skip` / `loadgosub` 现在都是真实现，规则见怪点 #18–#20 | — |
| 13 | 图片**合成时才解码**（引擎是载入时就解码） | `bg` / 图片型 `lsp` / `ld` 只记文件名，`render.DeferredImage` 在截图那一刻才解码；透明模式是载入时的快照，尺寸读文件头算出（含「右半当 alpha」减半、条图除以格数） | 只影响内存与耗时；画面逐帧一致，`getspsize` / `spbtn` 命中区不受影响（0.21.0） |
| 14 | **渐变类演出不做**：`bg` / `ld` 后面的 effect,duration 参数（如 `,10,800`）忽略 | 换背景、换立绘一律**直接切到终态** | 万华镜 1258 次 `bg` 里 1243 次带 `,10,800`；终态与引擎一致，只是没有过渡过程（agent 看不了动态内容，**有意不做**，2026-10-26 用户拍板） |
| 15 | `click`（等一次点击）按 no-op 处理 | `bg …:click` 连发段（翻页式 CG / ED）在**一次 run 里整段跑完**，画面落在最后一帧 | 万华镜 73 段 / 992 帧，真引擎要按几百次才看完一张 CG；我们只把它记进 `stubbed`（**有意**，别给 `click` 补「等点击」）。护栏测试 `test_bg_click_flipbook_runs_in_one_step` |

---

## 三、换新游戏时的排查路径

| 现象 | 先看什么 | 常见原因 |
|---|---|---|
| 变量值不对 | `state()["undefined_vars"]` | 别名拼错（引擎当 0 号槽）；或脚本用 `mov` 写了字符串到 `%变量`（引擎给 0） |
| 剧情跑偏/卡住 | `click()` 返回的 `stopped`、`prog` | `stopped="timeout:..."` 说明死循环（`for` 边界算错最常见，见怪点 #1） |
| 文本缺字/换行不对 | `text()`、`state()["page"]` | 禁则或 `setwindow` 行距（偏差 #4） |
| 画面黑/缺图 | `unsupported` 里的 `image:xxx` 与首次出现行号 | 素材路径大小写、`bgcopy` 之后读档（怪点 #6） |
| 按钮点不到 | `buttons()` 是否为空、`unsupported` 里 `cell*` / `spbtn` | 界面用未实现命令铺的；或读档后没重跑注册（怪点 #7） |
| 剧情走向和原版不同，却没报错 | `state()["stubbed"]`、`state()["unsupported"]` | 撞到桩（引擎有、我们没做）时只是"少个效果"；**流程类已全部实现**（怪点 #18–#20），若走向仍不同，先看 `tablegoto` 的序号是不是越界、`skip` 的目标行有没有跨标签 |
| 读档后画面不全 / 少了自定义状态 | 脚本里有没有 `loadgosub`，`interp.hook_loadgosub` 是不是空 | 有 `loadgosub` 才会在读档后补状态（怪点 #20）；引擎那份"读档复位清单"我们只建模了按钮表/选项表/`break_flag`/`text_on` |
| 存档读不回来 | 用 `savefile_bin.parse` 直接解那份 `.dat`，看 `cur_line` / `pages` / `bg` | 版本不是 `ONS 2.8`、文件截断、`border` 猜错（`;G<n>` 没读到） |
| 存档"少东西" | `parse` 出来的 `variables` / `sprites` | 全局槽不进存档（怪点 #4）；`blt` 像素不进存档（怪点 #6） |

---

## 四、写"真引擎对照探针"的注意事项

用 OnscripterYuri 的 web 构建做对照实验时的坑（都踩过）：

1. **文本行不能以 ASCII 命令样开头**（怪点 #12）。要打印结果就写成 `结果X=$sx`，
   别写 `RESULTX=$sx`。
2. **行尾 `\` 会等点击**：想在后面继续跑命令就别加 `\`；反过来想让画面停住截图才加。
3. 想拿数值：在目标点之后立刻 `savegame 0`，再用 `savefile_bin.parse` 读槽位，
   比 OCR 截图可靠。
4. `savegame` 之前先把要观察的值写进 `< border` 的一般槽位（全局槽不进存档）。
5. **端口就是存档库**：`IDBFS` 挂在 `/onsyuri_save/game`、存在 IndexedDB 里，
   按 origin 隔离 —— 换端口等于换一个干净的库，排查"读到旧档"时先换端口。
6. 引擎报未知命令会直接 `***** End *****`（脚本终止、画面全黑），
   看不到期望结果时**先抓控制台日志**（`Log.entryAdded` + `Runtime.consoleAPICalled`）。
7. **`--screenshot` 必须给绝对路径**，相对路径会被 Edge 按它自己的 cwd 解析，
   表现为"命令成功但没图"；截图偶尔不出，加一次重试即可。
8. **脚本末尾要有等待命令**（`click`），否则命令跑完引擎就结束、画面全黑，
   截出来一片黑会让人以为"没执行到"。
9. **`for` 的变量必须 `numalias` 过**（不是"不能用字母变量"）：`readVariable` 对没定义的
   名字会把指针退回名字开头（怪点 #9），于是 `forCommand` 的 `compareString("=")` 看到的是
   名字本身，直接 `errorAndExit("for: missing '='")` 退出 —— 画面停在这一帧，看着"正常"，
   极易被当成"命令没生效"。`for %i` 只要 define 区有 `numalias i,100` 完全合法；
   探针里图省事用裸槽号 `%100`。**注意我们比引擎宽松**：我们的 `for %i` 不要求别名，
   所以同一份探针在我们这边能跑、在引擎那边会退出 —— 这正是探针要抓的差异。
10. **判定落点别用"最后一张图"**：`skip` 之后的行会继续执行，
    所以要在每个候选落点后 `goto *hold` 停住，或者用中心像素颜色区分。
    `tools/probe_flow.py` 已经把这两条做进代码：脚本由函数生成（行号由构造保证、
    有模板自检）、每个变体带期望颜色并自动判定 OK/FAIL，还会在起浏览器**之前**
    按引擎规则静态检查（`for` 变量没 `numalias`、`skip` 目标行越界）。
