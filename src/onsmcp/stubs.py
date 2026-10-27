"""未实现命令的占位实现：一条命令一个 `cmd_xxx` 桩。

为什么要写桩，而不是维护一张 "no-op 名单"：
  * 引擎 LUT 有 347 条命令，本项目只实现了 119 条。剩下的如果一点痕迹都不留，
    换游戏时只能从 unsupported.log 里看到一行命令名——查不到语义，也没法判断
    "该不该实现它"。桩函数的 docstring 就是那张速查表。
  * 桩把两种情况分开：「引擎有、我们没做」（记进 `stubbed`，在 state() 里报出来）
    和「根本不认识这条命令」（多半是别的脚本文件里的宏或拼错，仍走
    `_log_unsupported`）。混在一起就分不清是活没干完还是脚本有问题。
  * 想实现某条命令时：把 `self._stub("x")` 换成真实逻辑，或者在 `Interpreter`
    里直接写同名 `cmd_x`（子类方法优先，桩会被自然遮蔽，留着也不碍事）。

docstring 的写法约定：
  `用法 —— 语义。` 后面接"不做/不实现"说明原因；末尾的
  `（引擎 xxxCommand）` 是 `ONScripter_command.cpp` 里的函数名，
  想抄准确语义就去那里看。
  参数沿用 NScripter 手册的写法：`<number>` 数值、`<character string>` 字符串、
  `<numerical variable>` 即 `%var`、`<character variable>` 即 `$var`、`*label` 标签。

分组顺序按"换游戏时撞到的可能性 × 影响面"排，不按字母序。
"""
from __future__ import annotations

from .script import Args


class StubCommands:
    """混入 Interpreter 的未实现命令集合（见模块 docstring）。"""

    def _stub(self, name: str) -> None:
        """记一次"撞到未实现命令"。

        不进 `unsupported`——那本账专门留给"真不认识的命令"，混进来就失去信号了。
        """
        self.stubbed[name] = self.stubbed.get(name, 0) + 1
        if name in self.stubbed_at:
            return
        pc = min(max(self.pc - 1, 0), len(self.script.instrs) - 1)
        self.stubbed_at[name] = (self.script.instrs[pc].line_no
                                 if 0 <= pc < len(self.script.instrs) else -1)

    # ------------------------------------------------------------ 影音
    def cmd_avi(self, a: Args) -> None:
        """`avi "file.avi",0|1` —— 播全屏 AVI，第二参数 1 = 可点击跳过。不做：没有视频解码。（引擎 aviCommand）"""
        self._stub("avi")

    def cmd_movie(self, a: Args) -> None:
        """`movie "file"` —— Jh/Yuri 版把 mpeg/avi 收敛成这一个入口。不做：视频解码。（引擎 movieCommand）"""
        self._stub("movie")

    def cmd_mpegplay(self, a: Args) -> None:
        """`mpegplay "file.mpg",0|1` —— 播 MPEG，第二参数 1 = 可点击跳过。不做：视频解码。（引擎 mpegplayCommand）"""
        self._stub("mpegplay")

    def cmd_playstop(self, a: Args) -> None:
        """停止 MIDI/CD 播放。不做：音乐只记账不播放，没有可停的。（引擎 playstopCommand）"""
        self._stub("playstop")

    def cmd_chvol(self, a: Args) -> None:
        """`chvol ch,vol` —— 设 SDL_mixer 某个声道（0..n）的音量。不做：只记 music/se/voice 三类。（引擎 chvolCommand）"""
        self._stub("chvol")

    def cmd_getbgmvol(self, a: Args) -> None:
        """`getbgmvol %var` —— 读 BGM 当前音量。不做：音量只存不播，没有"运行时真实值"。（引擎 getmp3volCommand）"""
        self._stub("getbgmvol")

    def cmd_getmp3vol(self, a: Args) -> None:
        """`getmp3vol %var` —— 读 MP3 当前音量。不做：音量只存不播，没有"运行时真实值"。（引擎 getmp3volCommand）"""
        self._stub("getmp3vol")

    def cmd_getsevol(self, a: Args) -> None:
        """`getsevol %var` —— 读音效当前音量。不做：音量只存不播，没有"运行时真实值"。（引擎 getsevolCommand）"""
        self._stub("getsevol")

    def cmd_getvoicevol(self, a: Args) -> None:
        """`getvoicevol %var` —— 读语音当前音量。不做：音量只存不播，没有"运行时真实值"。（引擎 getvoicevolCommand）"""
        self._stub("getvoicevol")

    def cmd_defmp3vol(self, a: Args) -> None:
        """`defmp3vol n` —— 设 MP3 默认音量（0-100）。不做：只影响播放。（引擎 defmp3volCommand）"""
        self._stub("defmp3vol")

    def cmd_defsevol(self, a: Args) -> None:
        """`defsevol n` —— 设音效默认音量（0-100）。不做：只影响播放。（引擎 defsevolCommand）"""
        self._stub("defsevol")

    def cmd_defvoicevol(self, a: Args) -> None:
        """`defvoicevol n` —— 设语音默认音量（0-100）。不做：只影响播放。（引擎 defvoicevolCommand）"""
        self._stub("defvoicevol")

    def cmd_mp3fadein(self, a: Args) -> None:
        """`mp3fadein n[,mode]` —— MP3 淡入毫秒数。不做：没有播放器。（引擎 mp3fadeinCommand）"""
        self._stub("mp3fadein")

    def cmd_mp3fadeout(self, a: Args) -> None:
        """`mp3fadeout n[,mode]` —— MP3 淡出毫秒数。不做：没有播放器。（引擎 mp3fadeoutCommand）"""
        self._stub("mp3fadeout")

    def cmd_bgmfadein(self, a: Args) -> None:
        """`bgmfadein n[,mode]` —— 与 `mp3fadein` 同一 handler 的别名。不做：没有播放器。（引擎 mp3fadeinCommand）"""
        self._stub("bgmfadein")

    def cmd_bgmfadeout(self, a: Args) -> None:
        """`bgmfadeout n[,mode]` —— 与 `mp3fadeout` 同一 handler 的别名。不做：没有播放器。（引擎 mp3fadeoutCommand）"""
        self._stub("bgmfadeout")

    def cmd_soundpressplgin(self, a: Args) -> None:
        """`soundpressplgin "name|ext"` —— 注册第三方压缩音频解码 DLL。不做：Windows DLL。（引擎 soundpressplginCommand）"""
        self._stub("soundpressplgin")

    def cmd_spi(self, a: Args) -> None:
        """`spi "dll|ext"` —— 注册第三方图像格式解码 DLL。不做：Windows DLL；Pillow 已覆盖常见格式。（引擎 soundpressplginCommand）"""
        self._stub("spi")

    def cmd_cd(self, a: Args) -> None:
        """CD-DA 音轨控制（NScripter 遗留）。Jh/Yuri 的 LUT 里已删除，老脚本可能还留着。"""
        self._stub("cd")

    def cmd_cdplay(self, a: Args) -> None:
        """`cdplay n` —— 播第 n 条 CD 音轨。Jh/Yuri 的 LUT 里已删除，老脚本可能还留着。"""
        self._stub("cdplay")

    def cmd_reset_music(self, a: Args) -> None:
        """停掉全部音乐并清播放状态。Jh/Yuri 的 LUT 里已删除，老脚本可能还留着。"""
        self._stub("reset_music")

    def cmd_es_snd_stop(self, a: Args) -> None:
        """停掉 SDL_mixer 所有声道。Jh/Yuri 的 LUT 里已删除，老脚本可能还留着。"""
        self._stub("es_snd_stop")

    # ------------------------------------------------------------ 特效 / 动画
    def cmd_effect(self, a: Args) -> None:
        """`effect n,type,dur[,file]` —— 给内置特效注册编号，供 bg/lsp 的转场参数引用。
        **不做（有意）**：转场一律直接给终态，渐变/淡入淡出都没有——agent 看不了动态内容。
        两款游戏里 `bg` 的 `,10,800` 这类参数（万华镜 1243 次）就是靠它。（引擎 effectCommand）"""
        self._stub("effect")

    def cmd_effectblank(self, a: Args) -> None:
        """`effectblank n` —— 特效结束后额外空等 n 毫秒。不做：没有特效就没有等待。（引擎 effectblankCommand）"""
        self._stub("effectblank")

    def cmd_effectcut(self, a: Args) -> None:
        """"快进到下一个选择"时跳过所有特效。不做：没有特效可跳。（引擎 effectcutCommand）"""
        self._stub("effectcut")

    def cmd_effectskip(self, a: Args) -> None:
        """`effectskip 0|1` —— 关/开"点击可跳过特效"（Yuri 比 Jh 多这一条）。不做：没有特效。（引擎 effectskipCommand）"""
        self._stub("effectskip")

    def cmd_windoweffect(self, a: Args) -> None:
        """`windoweffect type,dur[,file]` —— 文本窗口显隐特效（与 effect 同 handler，无编号参数）。不做：窗口直接显隐。（引擎 effectCommand）"""
        self._stub("windoweffect")

    def cmd_quake(self, a: Args) -> None:
        """`quake amp,msec` —— 全屏随机抖动。不做：没有定时器，画面给终态。（引擎 quakeCommand）"""
        self._stub("quake")

    def cmd_quakex(self, a: Args) -> None:
        """`quakex amp,msec` —— 横向抖动。不做：没有定时器。（引擎 quakeCommand）"""
        self._stub("quakex")

    def cmd_quakey(self, a: Args) -> None:
        """`quakey amp,msec` —— 纵向抖动。不做：没有定时器。（引擎 quakeCommand）"""
        self._stub("quakey")

    def cmd_shadedistance(self, a: Args) -> None:
        """`shadedistance n` —— 文字阴影偏移像素。不做：渲染层没做阴影偏移。（引擎 shadedistanceCommand）"""
        self._stub("shadedistance")

    def cmd_setlayer(self, a: Args) -> None:
        """`setlayer n,no` —— 调整渲染层顺序（背景/精灵/文本）。不做：渲染顺序固定。（引擎 setlayerCommand）"""
        self._stub("setlayer")

    def cmd_btrans(self, a: Args) -> None:
        """按钮显示/隐藏的转场（与 `transbtn` 同一 handler）。不做：按钮直接显隐。（引擎 transbtnCommand）"""
        self._stub("btrans")

    def cmd_transbtn(self, a: Args) -> None:
        """`transbtn 0|1` —— 按钮显隐是否走转场。不做：按钮直接显隐。（引擎 transbtnCommand）"""
        self._stub("transbtn")

    def cmd_nega(self, a: Args) -> None:
        """`nega 1|2` —— 全屏反色（1）/ 单色化（2）。不做：整屏后处理未建模。（引擎 negaCommand）"""
        self._stub("nega")

    def cmd_sp_rgb_gradation(self, a: Args) -> None:
        """`sp_rgb_gradation r,g,b` —— 给精灵加 RGB 渐变（Yuri 扩展）。不做：精灵只有 alpha。（引擎 sp_rgb_gradationCommand）"""
        self._stub("sp_rgb_gradation")

    # ------------------------------------------------------------ 第二套精灵层（sp2）
    def cmd_lsp2(self, a: Args) -> None:
        """`lsp2 no,"file",x,y[,alpha]` —— 往第二套精灵层（sp2）放图，与主层并行。不做：只建了主层。（引擎 lsp2Command）"""
        self._stub("lsp2")

    def cmd_lsp2add(self, a: Args) -> None:
        """`lsp2add` —— sp2 叠加显示。不做：没有 sp2。（引擎 lsp2Command）"""
        self._stub("lsp2add")

    def cmd_lsp2sub(self, a: Args) -> None:
        """`lsp2sub` —— sp2 相减显示。不做：没有 sp2。（引擎 lsp2Command）"""
        self._stub("lsp2sub")

    def cmd_lsph2(self, a: Args) -> None:
        """`lsph2` —— 带九宫格参数的 sp2 显示。不做：没有 sp2。（引擎 lsp2Command）"""
        self._stub("lsph2")

    def cmd_lsph2add(self, a: Args) -> None:
        """`lsph2add` —— 九宫格 sp2 叠加。不做：没有 sp2。（引擎 lsp2Command）"""
        self._stub("lsph2add")

    def cmd_lsph2sub(self, a: Args) -> None:
        """`lsph2sub` —— 九宫格 sp2 相减。不做：没有 sp2。（引擎 lsp2Command）"""
        self._stub("lsph2sub")

    def cmd_vsp2(self, a: Args) -> None:
        """`vsp2 no` —— 显示 sp2 里的某张图。不做：没有 sp2。（引擎 vspCommand）"""
        self._stub("vsp2")

    def cmd_csp2(self, a: Args) -> None:
        """`csp2 no` —— 清掉 sp2 的某张图。不做：没有 sp2。（引擎 cspCommand）"""
        self._stub("csp2")

    def cmd_msp2(self, a: Args) -> None:
        """`msp2 no,x,y` —— 移动 sp2 的某张图。不做：没有 sp2。（引擎 mspCommand）"""
        self._stub("msp2")

    def cmd_amsp2(self, a: Args) -> None:
        """`amsp2 no,x,y,dur` —— 带补间的 sp2 移动。不做：没有 sp2，也没有定时器。（引擎 amspCommand）"""
        self._stub("amsp2")

    def cmd_allsp2hide(self, a: Args) -> None:
        """隐藏 sp2 全部精灵（可恢复）。不做：没有 sp2。（引擎 allsp2hideCommand）"""
        self._stub("allsp2hide")

    def cmd_allsp2resume(self, a: Args) -> None:
        """恢复 `allsp2hide` 隐掉的 sp2 精灵。不做：没有 sp2。（引擎 allsp2resumeCommand）"""
        self._stub("allsp2resume")

    def cmd_drawsp2(self, a: Args) -> None:
        """`drawsp2 no,cell,alpha,x,y,...` —— 把某张精灵（带缩放/旋转）直接画进背景层。不做：背景层直绘未建模。（引擎 drawsp2Command）"""
        self._stub("drawsp2")

    def cmd_drawsp3(self, a: Args) -> None:
        """`drawsp3 no,cell,alpha,x,y,mat...` —— 同 drawsp2，但直接接受完整仿射矩阵（不做插值）。不做：背景层直绘未建模。（引擎 drawsp3Command）"""
        self._stub("drawsp3")

    # ------------------------------------------------------------ 按钮 / 光标 / 精灵杂项
    def cmd_cellcheckexbtn(self, a: Args) -> None:
        """`cellcheckexbtn no,cell,"ctl"` —— 用 cell 号取 exbtn 的按钮形状（否则整张精灵算一个按钮）。不做：exbtn 控制串未实现。（引擎 exbtnCommand）"""
        self._stub("cellcheckexbtn")

    def cmd_cellcheckspbtn(self, a: Args) -> None:
        """`cellcheckspbtn no,cell` —— 用 cell 号确定 spbtn 的点击区域（多格精灵分格可点）。不做：命中按整张精灵的矩形算。（引擎 spbtnCommand）"""
        self._stub("cellcheckspbtn")

    def cmd_checkpage(self, a: Args) -> None:
        """`checkpage` —— 存档界面翻页按钮的摆放（NScripter 存档菜单专用）。不做：存档界面不在 agent 路径上。（引擎 checkpageCommand）"""
        self._stub("checkpage")

    def cmd_existspbtn(self, a: Args) -> None:
        """`existspbtn %var,no` —— 查某号精灵是否已定义为按钮。不做：agent 用 buttons() 看实际可点项。（引擎 spbtnCommand）"""
        self._stub("existspbtn")

    def cmd_bdef(self, a: Args) -> None:
        """`bdef` —— 清掉 `exbtn_d` 登记的默认按钮控制串（与 `exbtn_d` 同一分支）。不做：exbtn 控制串未实现。（引擎 exbtnCommand）"""
        self._stub("bdef")

    def cmd_bdown(self, a: Args) -> None:
        """`bdown` —— 置「按钮正被按住」标志，btndef 段据此走按下分支。不做：按键状态不建模。（引擎 bdownCommand）"""
        self._stub("bdown")

    def cmd_bexec(self, a: Args) -> None:
        """`bexec` —— 立刻按当前按钮状态返回 btndef 段（不等待点击）。不做：等点击即返回，没有"立即返回"路径。（引擎 btnwaitCommand）"""
        self._stub("bexec")

    def cmd_bclear(self, a: Args) -> None:
        """`bclear` —— 清掉 btndef 段已定义的按钮。不做：按钮表随 btndef 重建。（引擎 btndefCommand）"""
        self._stub("bclear")

    def cmd_bcursor(self, a: Args) -> None:
        """`bcursor n` —— 选第 n 号已加载的光标做鼠标指针。不做：没有鼠标指针。（引擎 getcursorCommand）"""
        self._stub("bcursor")

    def cmd_abssetcursor(self, a: Args) -> None:
        """`abssetcursor "cur","char",x,y` —— 同 setcursor，但用绝对屏幕坐标。不做：没有鼠标指针。（引擎 setcursorCommand）"""
        self._stub("abssetcursor")

    def cmd_setcursor(self, a: Args) -> None:
        """`setcursor "cur","char",dx,dy` —— 加载光标定义并设热区（相对坐标）。不做：没有鼠标指针。（引擎 setcursorCommand）"""
        self._stub("setcursor")

    def cmd_getcursor(self, a: Args) -> None:
        """`getcursor %x,%y` —— 读鼠标当前坐标。注意本项目有 `getcursorpos`（文字插入点），两者不是一回事。（引擎 getcursorCommand）"""
        self._stub("getcursor")

    def cmd_movemousecursor(self, a: Args) -> None:
        """`movemousecursor x,y` —— 把鼠标指针挪到指定位置。不做：没有真实鼠标。（引擎 movemousecursorCommand）"""
        self._stub("movemousecursor")

    def cmd_spstr(self, a: Args) -> None:
        """`spstr <control string>` —— 用 exbtn 的控制串手动摆精灵。不做：控制串语法未实现。（引擎 spstrCommand）"""
        self._stub("spstr")

    def cmd_spclclk(self, a: Args) -> None:
        """`spclclk %var` —— 读"点击命中的是哪个 spbtn"。不做：按钮点击已由 buttons()/choose() 返回。（引擎 spclclkCommand）"""
        self._stub("spclclk")

    def cmd_spreload(self, a: Args) -> None:
        """`spreload "file"` —— 预载图片到内存（省后续读盘）。不做：渲染层自带 LRU 缓存。（引擎 spreloadCommand）"""
        self._stub("spreload")

    def cmd_splitstring(self, a: Args) -> None:
        """`splitstring $src,"delim",$d0,$d1,...` —— 按分隔符切字符串到多个变量。不做：脚本里没用到，字符串函数只做了 mid/len。（引擎 splitCommand）"""
        self._stub("splitstring")

    def cmd_bsp(self, a: Args) -> None:
        """`bsp no,"ctl0","ctl1","ctl2"` —— 把第 no 号精灵直接注册成按钮（可带三段 exbtn 控制串）。不做：我们用 `spbtn`（按 cell 注册）。（引擎 bspCommand）"""
        self._stub("bsp")

    def cmd_btime(self, a: Args) -> None:
        """`btime` —— btnwait 超时毫秒（与 btntime 同 handler）。不做：没有超时机制，agent 主动点击。（引擎 btntimeCommand）"""
        self._stub("btime")

    def cmd_btntime(self, a: Args) -> None:
        """`btntime n` —— 给下一次 btnwait 设超时毫秒。不做：没有超时机制。（引擎 btntimeCommand）"""
        self._stub("btntime")

    def cmd_btntime2(self, a: Args) -> None:
        """`btntime2` —— 超时时额外回传"是否超时"标志。不做：没有超时机制。（引擎 btntimeCommand）"""
        self._stub("btntime2")

    def cmd_btnwait2(self, a: Args) -> None:
        """`btnwait2 %var` —— btnwait 的变体，超时会返回特定值。不做：`btnwait` 已实现，超时语义用不到。（引擎 btnwaitCommand）"""
        self._stub("btnwait2")

    # ------------------------------------------------------------ 往背景层直绘
    # 这一组的共同点：把当前画面/精灵/文字"烙"进背景层，之后移动精灵不会擦掉它。
    # 本项目只维护 bg 与精灵两层，没有"烙进背景"的中间缓冲。
    def cmd_draw(self, a: Args) -> None:
        """`draw` —— 把当前画面合成结果烙进背景层。不做：只有 bg + 精灵两层，无烙图缓冲。（引擎 drawCommand）"""
        self._stub("draw")

    def cmd_drawbg(self, a: Args) -> None:
        """`drawbg` —— 把当前背景烙进背景层（带累积）。不做：同 draw。（引擎 drawbgCommand）"""
        self._stub("drawbg")

    def cmd_drawbg2(self, a: Args) -> None:
        """`drawbg2 x,y,...` —— 带位置/缩放的背景直绘。不做：同 draw。（引擎 drawbg2Command）"""
        self._stub("drawbg2")

    def cmd_drawclear(self, a: Args) -> None:
        """清掉直绘出来的背景层内容。不做：没有直绘图层。（引擎 drawclearCommand）"""
        self._stub("drawclear")

    def cmd_drawfill(self, a: Args) -> None:
        """`drawfill r,g,b,x,y,w,h` —— 用实色填一块矩形进背景层。不做：没有直绘图层。（引擎 drawfillCommand）"""
        self._stub("drawfill")

    def cmd_drawsp(self, a: Args) -> None:
        """`drawsp no,cell` —— 把某张精灵烙进背景层。不做：没有直绘图层。（引擎 drawspCommand）"""
        self._stub("drawsp")

    def cmd_drawtext(self, a: Args) -> None:
        """`drawtext "str",x,y` —— 把一段文字烙进背景层。不做：没有直绘图层。（引擎 drawtextCommand）"""
        self._stub("drawtext")

    # ofscopy / ofscpy 已实现（见 Interpreter：引擎里是"把当前画面快照进累积缓冲"）

    # ------------------------------------------------------------ 文本排版 / 装饰
    # textcolor / texthide / textshow / indent / locate / puttext / br / clickstr /
    # kinsoku / addkinsoku / setkinsoku / pagetag 已实现（见 Interpreter），
    # 这里只剩"确实不做"的几个：逐字显示、竖排、注音、英文换行、图层插件、点击音。
    def cmd_textspeeddefault(self, a: Args) -> None:
        """`textspeeddefault n` —— 默认逐字显示速度。不做：文本一次给全，没有逐字动画。（引擎 textspeeddefaultCommand）"""
        self._stub("textspeeddefault")

    def cmd_tateyoko(self, a: Args) -> None:
        """`tateyoko 0|1` —— 横排 / 竖排切换（`0`=横）。不做：只做横排；竖排要另写一套排版与光标推进。（引擎 tateyokoCommand）"""
        self._stub("tateyoko")

    def cmd_zenkakko(self, a: Args) -> None:
        """`zenkakko` —— 「」等括号按全角宽度对齐的重排版模式（Jh 扩展）。不做：只影响括号的格子对齐，两款样本没用。（引擎 zenkakkoCommand）"""
        self._stub("zenkakko")

    def cmd_english(self, a: Args) -> None:
        """`english` —— 英文模式：改空格与单词换行规则（`script_h.setEnglishMode(true)`）。不做：只按中文逐字断行处理。（引擎 englishCommand）"""
        self._stub("english")

    def cmd_rubyon(self, a: Args) -> None:
        """`rubyon` —— 开启注音（ruby）区间。不做：注音要在正文上方再排一行小字，行距与折行都要另算，见 docs/quirks.md。（引擎 rubyonCommand）"""
        self._stub("rubyon")

    def cmd_rubyoff(self, a: Args) -> None:
        """`rubyoff` —— 关闭注音区间。不做：同 rubyon。（引擎 rubyoffCommand）"""
        self._stub("rubyoff")

    def cmd_layermessage(self, a: Args) -> None:
        """`layermessage no,"msg"` —— 给内置图层特效插件发消息。不做：没有内置图层特效。（引擎 layermessageCommand）"""
        self._stub("layermessage")

    def cmd_clickvoice(self, a: Args) -> None:
        """`clickvoice "file","type"` —— 等点击时播的点击音。不做：没有音频播放。（引擎 clickvoiceCommand）"""
        self._stub("clickvoice")

    # ------------------------------------------------------------ 回看（log）/ 日志文件
    def cmd_logsp(self, a: Args) -> None:
        """`logsp no` —— 往"回看"屏里放一张精灵。不做：没有回看屏。（引擎 logspCommand）"""
        self._stub("logsp")

    def cmd_logsp2(self, a: Args) -> None:
        """`logsp2 no` —— 回看屏的 sp2 版本。不做：没有回看屏。（引擎 logspCommand）"""
        self._stub("logsp2")

    def cmd_lookbackbutton(self, a: Args) -> None:
        """`lookbackbutton "up","down","pageup","pagedown"` —— 回看屏的翻页按钮图。不做：没有回看屏。（引擎 lookbackbuttonCommand）"""
        self._stub("lookbackbutton")

    def cmd_lookbackcolor(self, a: Args) -> None:
        """`lookbackcolor #rrggbb` —— 回看屏的文字颜色。不做：没有回看屏。（引擎 lookbackcolorCommand）"""
        self._stub("lookbackcolor")

    def cmd_lookbacksp(self, a: Args) -> None:
        """`lookbacksp no` —— 往回看屏里贴图。不做：没有回看屏。（引擎 lookbackspCommand）"""
        self._stub("lookbacksp")

    def cmd_lookbackflush(self, a: Args) -> None:
        """`lookbackflush` —— 清空回看缓冲。不做：历史由 `text(history=N)` 的 `history` 数组负责。（引擎 lookbackflushCommand）"""
        self._stub("lookbackflush")

    def cmd_labellog(self, a: Args) -> None:
        """`labellog` —— 把 goto/gosub 过的标签记进标签日志（调试/分支覆盖用）。不做：要覆盖情况看 trace。（引擎 labellogCommand）"""
        self._stub("labellog")

    def cmd_filelog(self, a: Args) -> None:
        """`filelog` —— 把脚本用到的资源记进 file.log（打包用）。不做：调试/打包工具链的事。（引擎 filelogCommand）"""
        self._stub("filelog")

    def cmd_getlog(self, a: Args) -> None:
        """`getlog $var,page` —— 取回看缓冲里第 page 页的文本。不做：要历史对话用 `text(history=N)`。（引擎 getlogCommand）"""
        self._stub("getlog")

    def cmd_getlogtext(self, a: Args) -> None:
        """`getlogtext $var,page` —— 同 getlog，只取纯文本。不做：同 getlog。（引擎 getlogCommand）"""
        self._stub("getlogtext")

    def cmd_gettaglog(self, a: Args) -> None:
        """`gettaglog $var,n` —— 取第 n 条带 tag（说话人）的文本历史。不做：说话人已在 `text()` 的历史里。（引擎 gettaglogCommand）"""
        self._stub("gettaglog")

    # ------------------------------------------------------------ 选择 / 系统菜单 UI
    def cmd_select(self, a: Args) -> None:
        """`select "txt",*label,...` —— 引擎自带选项框，选中后 goto 对应标签。不做：选项走 csel/cselbtn 序列 + `choices()`/`choose()`，见 docs/quirks.md。（引擎 selectCommand）"""
        self._stub("select")

    def cmd_selgosub(self, a: Args) -> None:
        """`selgosub "txt",*label,...` —— 同 select，但选中后 gosub。不做：同 select。（引擎 selectCommand）"""
        self._stub("selgosub")

    def cmd_selnum(self, a: Args) -> None:
        """`selnum %var,"txt",...` —— 选项结果写进变量，不跳转。不做：同 select。（引擎 selectCommand）"""
        self._stub("selnum")

    def cmd_selectcolor(self, a: Args) -> None:
        """`selectcolor #hover,#normal` —— 选项文字的悬停/常态颜色。不做：没有系统选项框。（引擎 selectcolorCommand）"""
        self._stub("selectcolor")

    def cmd_selectvoice(self, a: Args) -> None:
        """`selectvoice "enter","click","cancel"` —— 选项框音效。不做：没有系统选项框，也没有音频。（引擎 selectvoiceCommand）"""
        self._stub("selectvoice")

    def cmd_okcancelbox(self, a: Args) -> None:
        """`okcancelbox %var,"msg"` —— 弹系统确认框，1=OK / 0=Cancel 写进变量。不做：阻塞式原生对话框，agent 侧无法应答。（引擎 yesnoboxCommand）"""
        self._stub("okcancelbox")

    def cmd_yesnobox(self, a: Args) -> None:
        """`yesnobox %var,"msg"` —— 弹系统"是/否"框。不做：同 okcancelbox。（引擎 yesnoboxCommand）"""
        self._stub("yesnobox")

    def cmd_input(self, a: Args) -> None:
        """`input $var,"prompt","default",maxlen,2byte` —— 弹输入框读字符串。不做：阻塞式原生 UI；脚本里的名字输入在样本中没出现。（引擎 inputCommand）"""
        self._stub("input")

    def cmd_checkkey(self, a: Args) -> None:
        """`checkkey %var` —— 读键盘/手柄按键的状态位。不做：没有输入设备模型，只模拟点击。（引擎 checkkeyCommand）"""
        self._stub("checkkey")

    def cmd_getmclick(self, a: Args) -> None:
        """`getmclick %var` —— 读鼠标按键状态（0=无 / 1=左 / 2=右）。不做：点击由 MCP 调用注入，没有"轮询式"鼠标状态。（引擎 getmclickCommand）"""
        self._stub("getmclick")

    def cmd_getmouseover(self, a: Args) -> None:
        """`getmouseover %var` —— 鼠标是否在窗口内。不做：没有真实鼠标。（引擎 getmouseoverCommand）"""
        self._stub("getmouseover")

    def cmd_rmenu(self, a: Args) -> None:
        """`rmenu "txt",func,...` —— 右键菜单的菜单项与功能号。不做：没有系统右键菜单。（引擎 rmenuCommand）"""
        self._stub("rmenu")

    def cmd_rmode(self, a: Args) -> None:
        """`rmode 0|1` —— 关/开右键菜单功能。不做：没有系统右键菜单。（引擎 rmodeCommand）"""
        self._stub("rmode")

    def cmd_roff(self, a: Args) -> None:
        """`roff` —— 把右键行为设成"什么都不做"。不做：没有右键行为可关。（引擎 roffCommand）"""
        self._stub("roff")

    def cmd_trap(self, a: Args) -> None:
        """`trap *label` —— 等左键，点一下就跳标签（一次性）。不做：等点击已有 `waiting='text'`，跳转由脚本自己 goto。（引擎 trapCommand）"""
        self._stub("trap")

    def cmd_lr_trap(self, a: Args) -> None:
        """`lr_trap *label` / `lr_trap off` —— 左右键各跳一个标签的陷阱。不做：同 trap。（引擎 trapCommand）"""
        self._stub("lr_trap")

    def cmd_lrclick(self, a: Args) -> None:
        """`lrclick` —— 等左右键之一（与 `click` 同一 handler）。不做：没有真实鼠标事件。（引擎 clickCommand）"""
        self._stub("lrclick")

    def cmd_menu_automode(self, a: Args) -> None:
        """`menu_automode` —— 右键菜单里加"自动模式"项。不做：没有系统菜单。（引擎 menu_automodeCommand）"""
        self._stub("menu_automode")

    def cmd_menu_click_def(self, a: Args) -> None:
        """`menu_click_def` —— 默认文本显示模式（逐字 / 整页）。不做：文本一次给全，本来就是整页。（引擎 menu_click_defCommand）"""
        self._stub("menu_click_def")

    def cmd_menu_click_page(self, a: Args) -> None:
        """`menu_click_page` —— 切换"点一下显示整页"。不做：同 menu_click_def。（引擎 menu_click_pageCommand）"""
        self._stub("menu_click_page")

    def cmd_menu_full(self, a: Args) -> None:
        """`menu_full` —— 系统菜单的"全屏"按钮。不做：没有系统菜单，分辨率由 MCP 配置定。（引擎 menu_fullCommand）"""
        self._stub("menu_full")

    def cmd_menu_window(self, a: Args) -> None:
        """`menu_window` —— 系统菜单的"窗口化"按钮。不做：同 menu_full。（引擎 menu_windowCommand）"""
        self._stub("menu_window")

    def cmd_menuselectcolor(self, a: Args) -> None:
        """`menuselectcolor #hover,#out,#nosave` —— 右键存档菜单的三种文字颜色。不做：没有存档菜单。（引擎 menuselectcolorCommand）"""
        self._stub("menuselectcolor")

    def cmd_menuselectvoice(self, a: Args) -> None:
        """`menuselectvoice` —— 右键存档菜单的各种音效（7 个）。不做：没有存档菜单，也没有音频。（引擎 menuselectvoiceCommand）"""
        self._stub("menuselectvoice")

    def cmd_menusetwindow(self, a: Args) -> None:
        """`menusetwindow x,y,w,h,fontsize,?,color` —— 右键存档菜单的窗口样式。不做：没有存档菜单。（引擎 menusetwindowCommand）"""
        self._stub("menusetwindow")

    def cmd_windowchip(self, a: Args) -> None:
        """`windowchip no` —— 把某号精灵当"窗口芯片"，随文本窗口一起显隐。不做：窗口显隐没有独立状态。（引擎 windowchipCommand）"""
        self._stub("windowchip")

    def cmd_maxkaisoupage(self, a: Args) -> None:
        """`maxkaisoupage n` —— 存档/读档界面每页最多几项。不做：存档界面不在 agent 路径上。（引擎 maxkaisoupageCommand）"""
        self._stub("maxkaisoupage")

    # ------------------------------------------------------------ 存档扩展
    def cmd_savegame2(self, a: Args) -> None:
        """`savegame2 slot` —— 带"存档界面截图"的 savegame 变体。不做：等价于 `savegame`，截图不入档。（引擎 savegameCommand）"""
        self._stub("savegame2")

    def cmd_savepoint(self, a: Args) -> None:
        """`savepoint` —— 原地存一次档（存到当前 `save_number` 槽）。不做：槽位由 MCP 的 `save` 指定。（引擎 savepointCommand）"""
        self._stub("savepoint")

    def cmd_savescreenshot(self, a: Args) -> None:
        """`savescreenshot "file"` —— 把当前画面存成图片（存档缩略图用）。不做：截图走 MCP 的 `screenshot` 工具。（引擎 savescreenshotCommand）"""
        self._stub("savescreenshot")

    def cmd_savescreenshot2(self, a: Args) -> None:
        """`savescreenshot2` —— 缩略图存成内存图（带缩放/降采样），供存档界面。不做：存档文件格式里本来就没有缩略图槽位。（引擎 savescreenshotCommand）"""
        self._stub("savescreenshot2")

    def cmd_deletescreenshot(self, a: Args) -> None:
        """`deletescreenshot n` —— 删掉某槽的缩略图。不做：同 savescreenshot2。（引擎 deletescreenshotCommand）"""
        self._stub("deletescreenshot")

    def cmd_getsavestr(self, a: Args) -> None:
        """`getsavestr $var,n` —— 取存档槽里自定义字符串的第 n 项。不做：我们只读写引擎原生的定长槽位，没有 `savestr`。（引擎 getsavestrCommand）"""
        self._stub("getsavestr")

    def cmd_savename(self, a: Args) -> None:
        """`savename "title","file","thumb"` —— 存档界面的标题/文件名/缩略图名前缀。不做：槽位路径固定 `save<N>.dat`。（引擎 savenameCommand）"""
        self._stub("savename")

    def cmd_savenumber(self, a: Args) -> None:
        """`savenumber n` —— 存档槽上限（≤20，默认 9）。不做：MCP 的 slot 限 0..999。（引擎 savenumberCommand）"""
        self._stub("savenumber")

    def cmd_saveoff(self, a: Args) -> None:
        """`saveoff` —— 关掉"把读档位置记进日志"的存档模式（读档后从 saveon 的位置开始）。不做：我们的读档位置由 `cur_line` 决定。（引擎 saveoffCommand）"""
        self._stub("saveoff")

    def cmd_saveon(self, a: Args) -> None:
        """`saveon` —— 重新打开 `saveoff` 关掉的存档模式。不做：同 saveoff。（引擎 saveonCommand）"""
        self._stub("saveon")

    def cmd_autosaveoff(self, a: Args) -> None:
        """`autosaveoff` —— 关掉自动存档。不做：没有自动存档。（引擎 autosaveoffCommand）"""
        self._stub("autosaveoff")

    def cmd_savedir(self, a: Args) -> None:
        """`savedir "dir"` —— 让引擎把存档写到指定目录。不做：存档目录由 `GameSession(save_dir=)` / `ONSMCP_SAVE_DIR` 决定。（引擎 savedirCommand）"""
        self._stub("savedir")

    def cmd_definereset(self, a: Args) -> None:
        """`definereset` —— 回到 `*define` 重新解释定义区（热重载）。不做：`*define` 只在 start 时跑一次。（引擎 defineresetCommand）"""
        self._stub("definereset")

    # ------------------------------------------------------------ 时间 / 计时
    def cmd_date(self, a: Args) -> None:
        """`date %y,%m,%d` —— 读系统日期。不做：脚本没用到；要真实时间可加，但会让截图/存档不可复现。（引擎 dateCommand）"""
        self._stub("date")

    def cmd_time(self, a: Args) -> None:
        """`time %h,%m,%s` —— 读系统时间。不做：同 date。（引擎 timeCommand）"""
        self._stub("time")

    def cmd_resettimer(self, a: Args) -> None:
        """`resettimer` —— 把内部计时器清零（毫秒）。不做：没有跨命令的计时器，等待类命令直接 no-op。（引擎 resettimerCommand）"""
        self._stub("resettimer")

    def cmd_gettimer(self, a: Args) -> None:
        """`gettimer %var` —— 读"距上次 resettimer 过了多少毫秒"。不做：同 resettimer。（引擎 gettimerCommand）"""
        self._stub("gettimer")

    def cmd_waittimer(self, a: Args) -> None:
        """`waittimer n` —— 等到计时器超过 n 毫秒再继续（引擎里最准的定时）。不做：agent 是逐步推进的，真等会白屏卡住调用方。（引擎 waittimerCommand）"""
        self._stub("waittimer")

    def cmd_getbtntimer(self, a: Args) -> None:
        """`getbtntimer %var` —— 从进 btnwait 到现在过了多少毫秒（配合 `btntime` 做超时中断/恢复）。不做：按钮等待没有计时器。（引擎 gettimerCommand）"""
        self._stub("getbtntimer")

    # ------------------------------------------------------------ 数值 / 字符串运算
    def cmd_cmp(self, a: Args) -> None:
        """`cmp %var,"a","b"` —— 字符串比较，0=相等、负=右大、正=左大。不做：`if` 里已支持 `$a=$b` 这类直接比较，不需要绕一道。（引擎 cmpCommand）"""
        self._stub("cmp")

    def cmd_sin(self, a: Args) -> None:
        """`sin %var,angle` —— 正弦，值为 `sin(angle)*1000`（角度制）。不做：脚本没用到。（引擎 sinCommand）"""
        self._stub("sin")

    def cmd_cos(self, a: Args) -> None:
        """`cos %var,angle` —— 余弦，值为 `cos(angle)*1000`（角度制）。不做：脚本没用到。（引擎 cosCommand）"""
        self._stub("cos")

    def cmd_tan(self, a: Args) -> None:
        """`tan %var,angle` —— 正切（角度制）。不做：脚本没用到。（引擎 tanCommand）"""
        self._stub("tan")

    def cmd_sar(self, a: Args) -> None:
        """`sar` —— 载入 `sar` 归档（与 `nsa` 同一 handler，老 NScripter 的归档格式）。不做：归档自动识别。（引擎 nsaCommand）"""
        self._stub("sar")

    def cmd_tal(self, a: Args) -> None:
        """`tal {l,c,r},n` —— 设左/中/右三档立绘的透明度。不做：立绘是本项目的具体精灵号，没有"三档"概念。（引擎 talCommand）"""
        self._stub("tal")

    def cmd_rnd2(self, a: Args) -> None:
        """`rnd2 %var,min,max` —— **闭区间**随机数（`rnd` 是半开区间）。不做：两款样本只用 `rnd`；需要时可照 `cmd_rnd` 加 1 行。（引擎 rndCommand）"""
        self._stub("rnd2")

    def cmd_intlimit(self, a: Args) -> None:
        """`intlimit %var,min,max` —— 每帧把变量夹到 [min,max]。不做：没有"每帧"循环，脚本样本也没用到。（引擎 intlimitCommand）"""
        self._stub("intlimit")

    # ------------------------------------------------------------ 系统 / 运行模式
    def cmd_game(self, a: Args) -> None:
        """`game` —— 结束 `*define` 区、开始执行游戏。不做：我们的入口是 `start` 标签（`*define` 由引导阶段跑完），这条等于空转。（引擎 gameCommand）"""
        self._stub("game")

    def cmd_caption(self, a: Args) -> None:
        """`caption "title"` —— 设窗口标题。不做：没有窗口，也没有窗口标题这个概念。（引擎 captionCommand）"""
        self._stub("caption")

    def cmd_versionstr(self, a: Args) -> None:
        """`versionstr "line1","line2"` —— "关于"对话框里的版本串。不做：没有"关于"对话框。（引擎 versionstrCommand）"""
        self._stub("versionstr")

    def cmd_getversion(self, a: Args) -> None:
        """`getversion %var` —— 读引擎版本号（1.90 → 190）。不做：我们不是那个引擎，报任何值都是骗脚本。（引擎 getversionCommand）"""
        self._stub("getversion")

    def cmd_defaultfont(self, a: Args) -> None:
        """`defaultfont "file.ttf"` —— 默认字体文件。不做：字体由渲染配置决定（`default.ttf`）。（引擎 defaultfontCommand）"""
        self._stub("defaultfont")

    def cmd_defaultspeed(self, a: Args) -> None:
        """`defaultspeed slow,normal,fast` —— `!sd` 特殊串用的三档文本速度。不做：没有逐字显示。（引擎 defaultspeedCommand）"""
        self._stub("defaultspeed")

    def cmd_defspeed(self, a: Args) -> None:
        """`defspeed` —— 老版默认文本速度（Jh/Yuri 的 LUT 里已删除）。不做：同 defaultspeed。"""
        self._stub("defspeed")

    def cmd_useescspc(self, a: Args) -> None:
        """`useescspc` —— 允许 ESC 键触发"跳过到下一个选择"。不做：没有键盘。（引擎 useescspcCommand）"""
        self._stub("useescspc")

    def cmd_usewheel(self, a: Args) -> None:
        """`usewheel` —— 允许滚轮上下翻历史。不做：没有鼠标滚轮。（引擎 usewheelCommand）"""
        self._stub("usewheel")

    def cmd_windowback(self, a: Args) -> None:
        """`windowback` —— 把文本窗口插到与立绘同层（做"字幕"特效）。不做：渲染顺序固定为 背景→精灵→文本。（引擎 windowbackCommand）"""
        self._stub("windowback")

    def cmd_setwindow2(self, a: Args) -> None:
        """`setwindow2 "file"|#rrggbb` —— 只换窗口外观，不动位置/尺寸/字体。不做：窗口样式在 `setwindow`/配置里一次定好。（引擎 setwindow2Command）"""
        self._stub("setwindow2")

    def cmd_mode_ext(self, a: Args) -> None:
        """`mode_ext` —— 打开扩展模式（automode / 各种右键菜单项的开关集合）。不做：没有 automode。（引擎 mode_extCommand）"""
        self._stub("mode_ext")

    def cmd_mode_saya(self, a: Args) -> None:
        """`mode_saya` —— Saya 兼容模式：`bar`/`prnum` 那套，窗口消失时立绘 0-9 一起消失。不做：`bar`/`prnum` 都没做。（引擎 mode_sayaCommand）"""
        self._stub("mode_saya")

    def cmd_mode_wave_demo(self, a: Args) -> None:
        """`mode_wave_demo` —— 快进时也照播 WAV。不做：没有音频。（引擎 mode_wave_demoCommand）"""
        self._stub("mode_wave_demo")

    def cmd_kidokumode(self, a: Args) -> None:
        """`kidokumode n` —— KID 系（Ever17/秋之回忆那类）的读档行为模式开关。不做：存档读写按引擎原生格式，不需要模式位。（引擎 kidokumodeCommand）"""
        self._stub("kidokumode")

    def cmd_kidokuskip(self, a: Args) -> None:
        """`kidokuskip` —— KID 系"跳到下一个选择（只跳已读）"模式。不做：没有快进状态。（引擎 kidokuskipCommand）"""
        self._stub("kidokuskip")

    def cmd_isskip(self, a: Args) -> None:
        """`isskip %var` —— 当前是否在快进。不做：没有快进状态，恒为 0 会让脚本走"非快进"分支。（引擎 isskipCommand）"""
        self._stub("isskip")

    def cmd_skipon(self, a: Args) -> None:
        """进入"跳过到下一个选择"模式（Jh/Yuri 的 LUT 里已删除，用 `skipoff` 的反面）。不做：没有快进状态。"""
        self._stub("skipon")

    def cmd_skipoff(self, a: Args) -> None:
        """退出"跳过到下一个选择"与 automode。不做：没有快进状态。（引擎 skipoffCommand）"""
        self._stub("skipoff")

    def cmd_autoclick(self, a: Args) -> None:
        """`autoclick n` —— 等点击超过 n 毫秒就自动继续。不做：agent 主动点击，不需要自动。（引擎 autoclickCommand）"""
        self._stub("autoclick")

    def cmd_automode(self, a: Args) -> None:
        """`automode` —— 开自动播放模式（等同 `mode_ext`）。不做：没有定时器。（引擎 mode_extCommand）"""
        self._stub("automode")

    def cmd_automode_time(self, a: Args) -> None:
        """`automode_time n` —— 自动播放时每个字的间隔毫秒。不做：没有自动播放。（引擎 automode_timeCommand）"""
        self._stub("automode_time")

    def cmd_automodeoff(self, a: Args) -> None:
        """关掉自动播放。Jh/Yuri 的 LUT 里没有这条，老脚本可能残留。不做：没有自动播放。"""
        self._stub("automodeoff")

    def cmd_click(self, a: Args) -> None:
        """`click` —— 等一次左键。**按 no-op 处理（有意）**：`bg …:click` 连发段就是翻页式
        CG / ED 播放（万华镜 73 段、992 帧），逐帧等点击要按几百次，而 agent 看不了动态内容。
        整段在一次 run 里跑完、画面落在最后一帧，只把次数记进 `stubbed` 便于统计。
        护栏测试：`test_bg_click_flipbook_runs_in_one_step`。（引擎 clickCommand）"""
        self._stub("click")

    def cmd_isdown(self, a: Args) -> None:
        """`isdown %var` —— 读鼠标左键是否按住。不做：没有真实鼠标状态。（引擎 isdownCommand）"""
        self._stub("isdown")

    def cmd_getenter(self, a: Args) -> None:
        """`getenter %var` —— 读"确认/取消"是哪种键触发的。不做：点击是按坐标注入的，没有键类型。（引擎 getenterCommand）"""
        self._stub("getenter")

    def cmd_getinsert(self, a: Args) -> None:
        """`getinsert %var` —— 读文本输入框是否处于"插入"模式。不做：没有输入框。（引擎 getinsertCommand）"""
        self._stub("getinsert")

    def cmd_getreg(self, a: Args) -> None:
        """`getreg $var,"key","name"` —— 读 Windows 注册表（HKCU）。不做：跨平台，也没有注册表语义。（引擎 getregCommand）"""
        self._stub("getreg")

    def cmd_exec_dll(self, a: Args) -> None:
        """`exec_dll "dll","func",...` —— 调外部 DLL 里的函数。不做：Windows DLL，跨平台不可用。（引擎 exec_dllCommand）"""
        self._stub("exec_dll")

    def cmd_luacall(self, a: Args) -> None:
        """`luacall *label,args` —— 调 Lua 脚本。不做：没有内嵌 Lua。（引擎 luacallCommand）"""
        self._stub("luacall")

    def cmd_luasub(self, a: Args) -> None:
        """`luasub *label` —— 注册 Lua 子程序。不做：没有内嵌 Lua。（引擎 luasubCommand）"""
        self._stub("luasub")

    def cmd_flushout(self, a: Args) -> None:
        """`flushout` —— 把脏矩形立刻刷到屏幕（手动画帧时用）。不做：我们是"调用即渲染"，没有攒帧。（引擎 flushoutCommand）"""
        self._stub("flushout")

    def cmd_fileexist(self, a: Args) -> None:
        """`fileexist %var,"file"` —— 查资源是否存在（存在返 1）。不做：资源查找在 `GameFiles`，脚本层不该关心；样本没用到。（引擎 fileexistCommand）"""
        self._stub("fileexist")

    def cmd_getfunction(self, a: Args) -> None:
        """`getfunction %var` —— 读 `function` 命令登记的函数号（游戏内菜单项点击结果）。不做：没有 `function` 表。（引擎 getfunctionCommand）"""
        self._stub("getfunction")

    def cmd_getret(self, a: Args) -> None:
        """`getret %var` / `getret $var` —— 读上一条命令的返回值（`layermessage` 之类会写它）。不做：没有返回值通道。（引擎 getretCommand）"""
        self._stub("getret")

    def cmd_getparam2(self, a: Args) -> None:
        """`getparam2 %var` / `$var` —— 取宏参数（`getparam` 的宽松类型版）。不做：`getparam` 已实现；`getparam2` 样本没用到。（引擎 getparamCommand）"""
        self._stub("getparam2")

    def cmd_getsppos(self, a: Args) -> None:
        """`getsppos %x,%y,no` —— 读某号精灵当前坐标。不做：精灵状态是我们内部对象，脚本层用不到；样本没用到。（引擎 getspposCommand）"""
        self._stub("getsppos")

    def cmd_getspmode(self, a: Args) -> None:
        """`getspmode %var,no` —— 读某号精灵的显示模式位。不做：同 getsppos。（引擎 getspmodeCommand）"""
        self._stub("getspmode")

    def cmd_getz(self, a: Args) -> None:
        """`getz %var` —— 旧版读"点击命中"的 z 值（已被 `getzxc` 取代）。Jh/Yuri 的 LUT 里没有这条。不做：同 getzxc。"""
        self._stub("getz")

    def cmd_getzxc(self, a: Args) -> None:
        """`getzxc %var` —— 读点到的东西的 z/x/c（哪个精灵、哪一格、按钮）。不做：点击由坐标注入，有 `buttons()` 就够。（引擎 getzxcCommand）"""
        self._stub("getzxc")

    def cmd_gettab(self, a: Args) -> None:
        """`gettab %var,"str",n` —— 取字符串里第 n 个排版位置的宽度。不做：排版宽度由 Pillow 现算，脚本层用不到。（引擎 gettabCommand）"""
        self._stub("gettab")

    def cmd_getpage(self, a: Args) -> None:
        """`getpage %var` —— 读当前文本页的页号（`pagetag` 配套）。不做：页只是"当前显示的一段文本"。（引擎 getpageCommand）"""
        self._stub("getpage")

    def cmd_getpageup(self, a: Args) -> None:
        """`getpageup %var` —— 存档/回看界面翻了几页。不做：没有这些界面。（引擎 getpageupCommand）"""
        self._stub("getpageup")

    def cmd_ispage(self, a: Args) -> None:
        """`ispage %var` —— 当前是否已进入新页（`pagetag` 配套）。不做：同 getpage。（引擎 ispageCommand）"""
        self._stub("ispage")

    def cmd_isfull(self, a: Args) -> None:
        """`isfull %var` —— 当前页是否已排满。不做：内部有 `_page_is_full()`，但没接成脚本可见的值。（引擎 isfullCommand）"""
        self._stub("isfull")

    def cmd_getscreenshot(self, a: Args) -> None:
        """`getscreenshot` —— 把当前画面抓进内存（存档界面用）。不做：截图走 MCP 的 `screenshot` 工具。（引擎 getscreenshotCommand）"""
        self._stub("getscreenshot")

    def cmd_humanorder(self, a: Args) -> None:
        """`humanorder "lcr"` —— 重排立绘"左/中/右"三档的绘制顺序。不做：本项目精灵按编号叠，没有左中右三档。（引擎 humanorderCommand）"""
        self._stub("humanorder")

    def cmd_nsa(self, a: Args) -> None:
        """`nsa` —— 打开 NSA 归档读取模式（从 `nsa*.arc` 里取资源）。不做：归档是自动识别的（`archive.py`），不需要脚本开。（引擎 arcCommand）"""
        self._stub("nsa")

    def cmd_ns2(self, a: Args) -> None:
        """`ns2` —— NSA 归档的 2 号变体（`ns2.arc`）。不做：同 nsa。（引擎 nsaCommand）"""
        self._stub("ns2")

    def cmd_ns3(self, a: Args) -> None:
        """`ns3` —— NSA 归档的 3 号变体（`ns3.arc`）。不做：同 nsa。（引擎 nsaCommand）"""
        self._stub("ns3")

    def cmd_arc(self, a: Args) -> None:
        """`arc "name|dll"` —— 注册第三方归档解压插件。不做：只认 nsa 与明文目录。（引擎 arcCommand）"""
        self._stub("arc")

    def cmd_nsadir(self, a: Args) -> None:
        """`nsadir "folder"` —— 设 nsa 文件的搜索目录。不做：归档路径跟着游戏目录走。（引擎 nsadirCommand）"""
        self._stub("nsadir")

    def cmd_prnum(self, a: Args) -> None:
        """`prnum no,value,x,y,w,h,color` —— 数字标签（0-999，三位宽），改完要 `print` 才显示。不做：为 mode_saya 专门做的遗留功能。（引擎 prnumCommand）"""
        self._stub("prnum")

    def cmd_prnumclear(self, a: Args) -> None:
        """`prnumclear no` —— 清掉某个数字标签。不做：同 prnum。（引擎 prnumclearCommand）"""
        self._stub("prnumclear")

    def cmd_cspchar(self, a: Args) -> None:
        """`cspchar` —— 清掉文本窗口上的字符精灵（Jh 老扩展）。Jh/Yuri 的 LUT 里没有这条，老脚本可能残留。"""
        self._stub("cspchar")
