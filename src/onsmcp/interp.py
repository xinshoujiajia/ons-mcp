"""解释器：单进程、纯 Python、逐条执行，走到"需要玩家输入"即返回。

关键约定（来自引擎源码）：
  * 命令名/标签名大小写不敏感（读取时折成小写）
  * 一行可用 ':' 串多条语句；`if` 条件为假时跳过整行剩余部分
  * 未定义的命令 = 引擎的 "command [x] is not supported yet"：记日志后跳过
  * defsub 定义的宏按普通 gosub 执行，参数由 getparam 取

本阶段（P1）只保证：bg / 文本 / 点击推进 / 变量 / if / goto / gosub / for。
动画、音频、视频、菜单按钮一律降级为 no-op，不会崩、不会卡。

"降级为 no-op"具体落在 `stubs.py`：引擎 LUT 里有、本项目还没做的命令，
一条一个 `cmd_xxx` 桩（docstring 写语义 + 为什么不实现）。走不到桩、也查不到
方法的命令（多半是宏或拼错）才记 `unsupported`。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .log import get_logger
from .render import Renderer
from .script import (K_STMT, K_TEXT, K_TILDE, Args, Instr, Script,
                     split_statements, tokenize, Tok, T_AVAR, T_COMMA, T_IDENT,
                     T_IVAR, T_LABEL, T_NUM, T_OP, T_STR, T_SVAR)
from .state import Button, Page, SelectLink, Sprite, State
from .stubs import StubCommands

log = get_logger("interp")

DEFAULT_GAME_LABEL = "start"

TAG_RE = re.compile(r"^\[([^\]]*)\]")


@dataclass
class Frame:
    return_pc: int
    params: list[list[Tok]] = field(default_factory=list)
    param_index: int = 0
    label: str = ""
    cont: tuple | None = None      # gosub 所在行的剩余语句（返回后继续跑）


@dataclass
class TraceEntry:
    line: int
    kind: str
    cmd: str
    text: str
    label: str = ""


@dataclass
class Utterance:
    """一句已经显示给玩家的台词。"""
    line: int
    label: str
    name: str
    text: str


class Interpreter(StubCommands):
    """ONScripter 子集解释器。

    未实现的引擎命令都在 `StubCommands` 里（每条一个 `cmd_xxx` 桩 + docstring），
    本类里的同名方法会自然遮蔽它们。
    """
    def __init__(self, script: Script, renderer: Renderer, *,
                 start_label: str | None = None, run_text_hooks: bool = False):
        self.script = script
        self.renderer = renderer
        self.state = State()
        self.run_text_hooks = run_text_hooks
        # 供 len 之类的命令算字节数用；session 载入脚本后会设成实际编码
        self.encoding = "gbk"

        self.pc = 0
        self.stack: list[Frame] = []
        self.for_stack: list[dict] = []
        self.macros: set[str] = set()
        self.current_label = ""
        self.waiting: str | None = None       # None | 'text' | 'btn'
        self.pending_pages: list[list[str]] = []
        # 读档恢复出来的页面：脚本重跑那一行时应该**替换**它，而不是往上追加，
        # 否则同一句话会在页里出现两次。
        self.page_from_save = False
        self.page_name = ""
        self.trace: list[TraceEntry] = []
        # 已显示的台词历史（给 agent 做上下文），环形保存
        self.history: list[Utterance] = []
        self.history_max = 200
        self.trace_max = 4000
        self.unsupported: dict[str, int] = {}
        self.unsupported_at: dict[str, int] = {}     # 首次出现的源码行号
        # "引擎有、本项目没做"的命令：桩函数记在这里，和上面那本账分开
        self.stubbed: dict[str, int] = {}
        self.stubbed_at: dict[str, int] = {}
        # 墙钟预算：run() 每 256 步看一次表。None = 不限时（define/引导阶段用）
        self.deadline: float | None = None
        # 上一次 run() 为什么停下来：空串=正常停到等待点，其余为异常原因
        self.stop_reason = ""
        self.hook_pretext: str | None = None
        self.hook_text: str | None = None
        # `loadgosub` 登记的标签：读档成功后 gosub 它（引擎 loadgameCommand 里做的事）
        self.hook_loadgosub: str = ""
        # `break` 之后进入"逐条跳过到 next"的状态（引擎的 break_flag）
        self.break_skip = False
        self.text_hook_entered = False     # 本页的 textgosub 是否已经进过
        # 开了 textgosub 钩子后，PC 会长期停在 *text_btn 里的 textbtnwait，
        # 所以额外记一份"最近一条文本所在的位置"，供 state() 报告剧情进度
        self.story_line = -1
        # 当前正执行的语句"行首到这里的裸冒号个数"（引擎存档的 cur_stmt 就是它）
        self.cur_stmt = 0
        self.story_label = ""
        # 游戏内存档接口，由 session 注入（用我们自己的 JSON 格式，不碰原版二进制存档）
        self.on_save = None       # (slot) -> None
        self.on_load = None       # (slot) -> None
        self.on_exists = None     # (slot) -> bool
        self.on_savetime = None   # (slot) -> (month, day, hour, minute)
        self.script_dir = renderer.game_dir
        self._pending_tag = ("", "", "")
        self._cur_cmd = ""                 # 当前语句的命令名（movN 取个数用）
        self.finished = False

        self.start_label = (start_label or DEFAULT_GAME_LABEL).lower()
        self._reset_pc()

    # ------------------------------------------------------------ 初始化
    def _reset_pc(self) -> None:
        idx = self.script.label_index(self.start_label)
        self.pc = idx if idx is not None else 0

    def run_define_section(self) -> None:
        """执行 *define 区（numalias / defsub / effect 定义都在里面）。

        引擎从文件头开始跑，定义区以 `game` 收尾；这里直接从 define 标签处
        开跑、遇到 `game` 停，然后把 PC 摆回目标标签。
        """
        if "define" not in self.script.labels:
            return
        def_idx = self.script.labels["define"]
        self.pc = def_idx
        steps = 0
        while steps < 200000 and self.pc < len(self.script.instrs):
            instr = self.script.instrs[self.pc]
            if instr.kind == K_STMT and instr.text.strip().lower() == "game":
                self.pc += 1
                break
            self.pc += 1
            steps += 1
            if instr.kind in (K_TEXT, K_TILDE):
                continue
            self._exec_stmt(instr)
            if self.finished:
                break
        target = self.script.label_index(self.start_label)
        self.pc = target if target is not None else 0
        self.waiting = None
        self.finished = False
        self.stack.clear()
        self.for_stack.clear()
        self.state.page = None
        self.state.text_locate = (0, 0)

    def restart(self) -> None:
        # 别名表与配置由 define 区建立，重开时保留；变量槽位清空（同引擎 reset）
        state = self.state
        self.state = State(aliases=state.aliases, str_aliases=state.str_aliases,
                           global_on=state.global_on,
                           global_border=state.global_border,
                           variable_range=state.variable_range)
        self.stack.clear()
        self.for_stack.clear()
        self.trace.clear()
        self.pending_pages.clear()
        self.page_from_save = False
        self.waiting = None
        self.finished = False
        self._reset_pc()
        self.run()

    # ------------------------------------------------------------ 主循环
    def run(self, max_steps: int = 20000) -> None:
        steps = 0
        self.stop_reason = ""
        while self.waiting is None and not self.finished:
            if self.pc >= len(self.script.instrs):
                self.finished = True
                break
            steps += 1
            if steps > max_steps:
                self.stop_reason = f"step-limit:{steps}:{self._cur_cmd_name()}"
                self._log_unsupported(f"<step-limit:{self._cur_cmd_name()}>")
                break
            # 每 256 步查一次表（monotonic 调用本身有开销，逐条查会明显变慢）
            if (steps & 255) == 0 and self.deadline is not None \
                    and time.monotonic() > self.deadline:
                self.stop_reason = f"timeout:{steps}:{self._cur_cmd_name()}"
                get_logger("interp").warning(
                    "执行超时，已停在 L%s（%s 步，命令 %s）",
                    self.script.instrs[self.pc].line_no if self.pc < len(self.script.instrs) else -1,
                    steps, self._cur_cmd_name())
                break
            instr = self.script.instrs[self.pc]
            self.pc += 1
            if self._consume_break_skip(instr):
                continue
            self._record(instr)
            if instr.kind == K_TEXT:
                self._exec_text(instr)
            elif instr.kind == K_TILDE:
                continue
            else:
                self._exec_stmt(instr)

    def _consume_break_skip(self, instr: Instr) -> bool:
        """`break` 之后要不要跳过这条指令（返回 True = 不执行）。

        对应引擎 `executeLabel` 里的 `if (break_flag && !isName("next"))` 分支：
        除名字是 `next` 的那条之外**全部跳过** —— 包括文本行、标签和同一行剩下的 token。
        `next` 本身要放行，由 `cmd_next` 看到帧上的 `brk` 标记后弹栈（不自增）。
        """
        if not self.break_skip:
            return False
        if instr.kind == K_STMT and instr.text.split()[0].lower() == "next":
            self.break_skip = False
            return False
        return True

    def _cur_cmd_name(self) -> str:
        if 0 <= self.pc < len(self.script.instrs):
            return self.script.instrs[self.pc].text.split()[0][:24]
        return "?"

    # ------------------------------------------------------------ 文本
    def _split_tag(self, raw: str):
        """拆行首标签，返回 `(voice, name, face, need_clear, body)`。

        两种写法都要认：

        * `[voice/name/face]` —— 我们自己约定的形态（万华镜这类）
        * `[voice|needClear]` —— 移植脚本（Ever17）的形态。第 2 段是
          "这一句要不要清页"：`1` = 起新页、`0` = 续在前一页后面。

        引擎把整段 tag 原样交给 `gettag`，脚本再自己 `split $0,"|",$voice,$needClear`
        （Ever17 的 `*procPreGo` 就是这么写的）。所以这里把 voice 拆干净，
        `need_clear` 单独返回，`gettag` 才不会拿到 `NONE|0` 这种带尾巴的值。
        """
        m = TAG_RE.match(raw)
        if not m:
            return "", "", "", None, raw
        inner = m.group(1) or ""
        need_clear = None
        if "|" in inner:
            inner, _, flag = inner.partition("|")
            if flag.strip() in ("0", "1"):
                need_clear = int(flag.strip())
        parts = inner.split("/")
        voice = parts[0] if parts else ""
        name = parts[1] if len(parts) > 1 else ""
        face = parts[2] if len(parts) > 2 else ""
        return voice, name, face, need_clear, raw[m.end():]

    def _array_value(self, spec: str) -> int:
        """`a[i]` 的值（下标可能是表达式，交给 Args 求值）。"""
        return self._args(tokenize("?" + spec)).array_get(spec)

    def interpolate(self, text: str) -> str:
        out = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "%" and text[i + 1:i + 2] == "?":
                # %?a[i]：数组元素的值当槽号
                m = re.match(r"\?([A-Za-z0-9_]+)((?:\[[^\[\]]*\])+)", text[i + 1:])
                if m:
                    slot = self._array_value(m.group(1).lower() + m.group(2))
                    out.append(str(self.state.int_slots.get(slot, 0)))
                    i += 1 + len(m.group(0))
                    continue
            if ch in "%$":
                # 名字可以是纯数字（%101 / $0），和引擎 parseInt 一致
                m = re.match(r"[A-Za-z0-9_]+", text[i + 1:])
                if m:
                    name = m.group(0).lower()
                    out.append(str(self.state.get_int(name) if ch == "%"
                                   else self.state.get_str(name)))
                    i += 1 + len(m.group(0))
                    continue
            if ch == "?":
                # 文本行里的 `?a[i]` 也要替换成数值（引擎 addIntVariable）
                m = re.match(r"([A-Za-z0-9_]+)((?:\[[^\[\]]*\])+)", text[i + 1:])
                if m:
                    out.append(str(self._array_value(m.group(1).lower() + m.group(2))))
                    i += 1 + len(m.group(0))
                    continue
            out.append(ch)
            i += 1
        return "".join(out)

    def _new_page(self, name: str = "") -> Page:
        """起一页新文本。

        引擎每次清页都会 `clearCurrentPage()` → `sentence_font.clear()` → `setXY(0,0)`，
        也就是 `locate` 设的偏移**换页就失效**，这里跟着归零。
        """
        self.state.text_locate = (0, 0)
        self.state.page = Page(name, [])
        return self.state.page

    def _exec_text(self, instr: Instr) -> None:
        self.story_line = instr.line_no
        self.story_label = (self.script.label_of[self.pc - 1]
                            if 0 < self.pc <= len(self.script.label_of) else self.current_label)
        self.text_hook_entered = False        # 每页新文本都要重新决定要不要进 textgosub
        voice, name, face, need_clear, body = self._split_tag(instr.text)
        self._pending_tag = (voice, name, face)
        body = self.interpolate(body)
        # 内联颜色标记 #RRGGBB 不走文本，引擎是切字体颜色用的
        body = re.sub(r"#[0-9A-Fa-f]{6}", "", body)
        # 行首 '_' 表示本行不等待点击
        no_wait = body.startswith("_")
        if no_wait:
            body = body[1:]
        # 引擎只在 clickstr 处等点击；普通换行的文本行只是换行，
        # 会继续执行下一条 —— 所以"名字行 + 台词行"才会落在同一页里。
        # clickstr 的字符集是脚本可改的（`clickstr "chars",line`），默认 `\` 和 `@`。
        cs = self.state.clickstr_chars or "\\@"
        ends_wait = (body.rstrip().endswith("\\") or any(c in body for c in cs)
                     or self.state.linepage_mode > 0)
        # 引擎的页面模型：一条文本行不是天然的一页，它会累积到当前页；
        # 但移植脚本（Ever17）用标签第 2 段 `[voice|needClear]` 显式控制：
        #   needClear=1 → 这句起新页（上一句消失，实测就是"一句一页"）
        #   needClear=0 → 续在前一页后面（名字行 + 台词行因此同屏）
        # 没有这种标签的游戏（万华镜）走 `linepage` / 满页换页的老路。
        def wrapped(chunk: str) -> list[str]:
            pages = self.renderer.paginate(chunk.replace("\\", "").strip(),
                                           self.state.window,
                                           self.state.indent_offset)
            return pages[0] if pages else []

        # '@' 把一行切成多段，每段之后都要等一次点击（等价于多个 clickstr）
        chunks = body.split("@") if "@" in cs else [body]
        self.page_name = name
        # 起新页的三种情形：还没有页 / 读档恢复的页（重跑要覆盖）/ 标签要求清页
        if self.state.page is None or self.page_from_save or need_clear == 1:
            # 上一页已被换走 / 还没开始 / 这是读档恢复的页面（重跑要覆盖它）
            self._new_page(name)
            self.page_from_save = False
        elif name and not self.state.page.name:
            self.state.page.name = name
        first_lines = wrapped(chunks[0])
        self.pending_pages = [wrapped(c) for c in chunks[1:]]
        self.state.page.lines.extend(first_lines)
        # 记一条台词历史（每页都记，翻页时 agent 能看到完整对话流）
        spoken = "\n".join(first_lines).strip()
        if spoken:
            self.history.append(Utterance(instr.line_no, self.story_label, name, spoken))
            if len(self.history) > self.history_max:
                del self.history[:len(self.history) - self.history_max]
        # 移植脚本的 *text_btn 在每页开头都会 texton；我们不跑钩子时要自己补上，
        # 否则任何一次 screen_clear 的 textoff 会让后续台词全都看不见。
        if not self.state.text_window_erased:
            self.state.text_on = True
        # pretextgosub：每页开画前跑一次（姓名/头像/语音），它是叶子子程序，同步跑完
        if self.run_text_hooks and self.hook_pretext:
            self.run_sub_sync(self.hook_pretext)

        if no_wait and not self.pending_pages:
            return
        if not ends_wait and not self.pending_pages:
            # 没有 clickstr：引擎不等，继续跑下一条（同页累积）
            return

        # 还有未显示的 @ 分段：先等点击
        if self.pending_pages:
            self.waiting = "text"
            return
        # textgosub：页尾执行，里面通常就是 textbtnwait（等待点）
        if self.run_text_hooks and self.hook_text:
            self.text_hook_entered = True
            self._gosub(self.hook_text)
            return
        self.waiting = "text"

    def enter_text_hook(self) -> bool:
        """最后一页翻完后，把 textgosub 挂上去（由 session.click 调用）。"""
        if self.run_text_hooks and self.hook_text and not self.text_hook_entered:
            self.text_hook_entered = True
            self._gosub(self.hook_text)
            return True
        return False

    def run_sub_sync(self, label: str, max_steps: int = 3000) -> None:
        """把叶子子程序跑完再返回（pretextgosub 这种不等待输入的小宏）。"""
        idx = self.script.label_index(label)
        if idx is None:
            self._log_unsupported(f"label:{label}")
            return
        depth = len(self.stack)
        self._gosub(label)
        steps = 0
        while (len(self.stack) > depth and steps < max_steps
               and self.waiting is None and not self.finished):
            if self.pc >= len(self.script.instrs):
                break
            if (steps & 255) == 0 and self.deadline is not None \
                    and time.monotonic() > self.deadline:
                self.stop_reason = f"timeout-sub:{steps}:{label}"
                break
            instr = self.script.instrs[self.pc]
            self.pc += 1
            steps += 1
            if self._consume_break_skip(instr):
                continue
            if instr.kind == K_TEXT:
                break
            if instr.kind == K_TILDE:
                continue
            self._exec_stmt(instr)

    def next_page(self) -> bool:
        """`@` 分段的下一段：**追加**到当前页（引擎不按 `@` 清屏）。"""
        if self.pending_pages:
            lines = self.pending_pages.pop(0)
            if self.state.page is None:
                self._new_page(self.page_name)
            self.state.page.lines.extend(lines)
            return True
        return False

    def _page_is_full(self) -> bool:
        """这一页排满了吗 —— 引擎的 `getRemainingLine() <= clickstr_line`。

        `clickstr_line` 默认 0（`linepage` 命令可改，本引擎未实现），
        所以"已画行数 >= num_y"就算满；满了不是立刻清屏，而是**这次点击之后**换页。
        """
        page = self.state.page
        if page is None:
            return False
        num_y = max(int(self.state.window.num_y or 1), 1)
        return len([ln for ln in page.lines if ln]) >= num_y

    # ------------------------------------------------------------ 语句执行
    def _exec_stmt(self, instr: Instr) -> None:
        self._run_line(instr.text, instr.line_no)

    def _args(self, toks) -> Args:
        """统一构造 Args：变量/字符串走槽位视图，裸名字要能查 stralias 常量与别名槽号。"""
        return Args(toks, self.state.variables, self.state.strings,
                    self.state.str_aliases, self.state.aliases, self.state)

    def _run_line(self, text: str, line_no: int = 0) -> None:
        parts = split_statements(text)
        self._run_parts(parts, line_no)

    def _run_parts(self, parts: list[str], line_no: int) -> None:
        """逐条执行一行内的语句。

        控制流命令要按引擎语义处理：goto/return/jumpf 吞掉本行剩余部分；
        gosub 把"本行剩余部分"当作返回地址（引擎的 return 地址就是下一个 token），
        子程序返回后再继续跑这些剩余语句。
        """
        i = 0
        while i < len(parts):
            # 引擎写档时存的是"从行首到当前读取位置之间的裸 ':' 个数"（引号内的也算），
            # 把前面几条语句原样拼回去再数，口径就一致了。
            self.cur_stmt = ":".join(parts[:i]).count(":") if i else 0
            part = parts[i].strip()
            if not part:
                i += 1
                continue
            if self.waiting is not None or self.finished:
                return
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", part)
            if not m:
                i += 1
                continue
            name = m.group(1).lower()
            self._cur_cmd = name            # mov2..mov10 要从命令名取个数
            rest_parts = parts[i + 1:]
            if name in ("if", "notif"):
                self._exec_if(part, rest_parts, line_no, negate=(name == "notif"))
                return
            # 这些命令会改变脚本指针，本行剩余部分不再执行（引擎 loadgame 成功
            # 后 setCurrent 已经指向存档行，失败返回 RET_SKIP 也是跳过本行）
            if name in ("goto", "return", "jumpf", "jumpb", "gameend", "reset",
                        "loadgame"):
                args = self._args(tokenize(part[m.end():]))
                self._dispatch(name, args, line_no)
                return
            self._raw_args = part[m.end():]
            args = self._args(tokenize(part[m.end():]))
            if name == "gosub":
                self._gosub(args.read_label(), cont=(rest_parts, line_no))
                return
            if name in self.macros:
                self._call_macro(name, args, cont=(rest_parts, line_no))
                return
            before = self.pc
            self._dispatch(name, args, line_no)
            # break / tablegoto / skip：真跳了（pc 变了）就丢掉本行剩余 ——
            # 引擎 setCurrent/setCurrentLabel 之后本行后面不会再执行；
            # tablegoto 序号越界时引擎不跳、继续跑，所以按"pc 有没有变"判断。
            # 无标签的 break 不改 pc，但它把 break_flag 立起来了，本行剩余同样要跳。
            if self.pc != before or self.break_skip:
                return
            i += 1

    # ------------------------------------------------------------ if
    def _exec_if(self, part: str, tail_parts: list[str], line_no: int,
                 *, negate: bool = False) -> None:
        """`if` / `notif`。

        引擎里两者是**同一个** `ifCommand`，`notif` 只是把 `if_flag` 置成 false
        （`ScriptParser_command.cpp`：`if (isName("notif")) if_flag = false;`），
        效果就是"条件为假时才执行本行剩余部分"。所以必须在这里一起处理：
        否则 `notif` 落到分派层会被当成普通 no-op，**后半句会被无条件执行**。
        """
        body = part[5 if negate else 2:].lstrip()
        toks = tokenize(body)
        if not toks:
            return
        args = self._args(toks)
        ok = self._cond_or(args)
        if negate:
            ok = not ok
        if not ok:
            return
        rest = self._tokens_to_text(args.remaining()).strip()
        new_parts = ([rest] if rest else []) + list(tail_parts)
        if new_parts:
            self._run_parts(new_parts, line_no)

    def _cond_or(self, a: Args) -> bool:
        val = self._cond_and(a)
        while True:
            t = a.peek()
            if t is not None and t.kind == T_OP and t.text == "||":
                a.i += 1
                rhs = self._cond_and(a)
                val = val or rhs
            else:
                return val

    def _cond_and(self, a: Args) -> bool:
        val = self._cond_cmp(a)
        while True:
            t = a.peek()
            if t is not None and t.kind == T_OP and t.text == "&&":
                a.i += 1
                rhs = self._cond_cmp(a)
                val = val and rhs
            else:
                return val

    def _cond_cmp(self, a: Args) -> bool:
        t = a.peek()
        if t is None:
            return False
        if t.kind == T_SVAR:
            left = a.read_str()
            op_tok = a.peek()
            if op_tok is not None and op_tok.kind == T_OP and op_tok.text in ("=", "==", "!=", "<", ">", "<=", ">="):
                op = op_tok.text
                a.i += 1
                return self._cmp_str(left, op, a.read_str())
            return bool(left)
        left = a.read_int()
        op_tok = a.peek()
        if op_tok is not None and op_tok.kind == T_OP and op_tok.text in ("=", "==", "!=", "<", ">", "<=", ">="):
            op = op_tok.text
            a.i += 1
            return self._cmp_int(left, op, a.read_int())
        return left != 0

    @staticmethod
    def _tokens_to_text(toks: list[Tok]) -> str:
        out = []
        for t in toks:
            if t.kind == T_COMMA:
                out.append(",")
            elif t.kind == T_STR:
                out.append('"' + t.text + '"')
            elif t.kind == T_IVAR:
                out.append("%" + t.text)
            elif t.kind == T_SVAR:
                out.append("$" + t.text)
            elif t.kind == T_LABEL:
                out.append("*" + t.text)
            elif t.kind == T_OP:
                out.append(" " + t.text + " ")
            else:
                out.append(t.text)
        return " ".join(x for x in out if x != "")

    @staticmethod
    def _cmp_int(a: int, op: str, b: int) -> bool:
        return {"=": a == b, "==": a == b, "!=": a != b, "<": a < b,
                ">": a > b, "<=": a <= b, ">=": a >= b}.get(op, False)

    @staticmethod
    def _cmp_str(a: str, op: str, b: str) -> bool:
        return {"=": a == b, "==": a == b, "!=": a != b,
                "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}.get(op, False)

    # ------------------------------------------------------------ 分派
    @staticmethod
    def _is_mov_family(name: str) -> bool:
        """`mov2`..`mov10` / `movl` 与 `mov` 共用 handler（引擎 LUT 里也是同一函数）。"""
        return name == "movl" or (name.startswith("mov") and name[3:].isdigit())

    @classmethod
    def has_handler(cls, name: str) -> bool:
        """脚本命令 name 在本解释器里是否有入口（真实现或桩都算）。

        给 `tools/missing_commands.py` 用：它没法靠 `dir(Interpreter)` 认出
        mov 家族（与 `mov` 共用 `cmd_mov`）和 `linepage2`（在 `cmd_linepage` 里按
        命令名分支）——这两类没有同名 `cmd_` 方法，会被误报成"缺实现"。
        """
        return (hasattr(cls, f"cmd_{name}") or cls._is_mov_family(name)
                or name == "linepage2")

    def _dispatch(self, name: str, args: Args, line_no: int) -> None:
        handler = getattr(self, f"cmd_{name}", None)
        if handler is not None:
            handler(args)
            return
        if self._is_mov_family(name):
            self.cmd_mov(args)
            return
        if name in self.macros:
            self._call_macro(name, args)
            return
        self._log_unsupported(name)

    def _call_macro(self, name: str, args: Args, cont: tuple | None = None) -> None:
        params = self._split_params(args.remaining())
        self._gosub(name, params, cont=cont)

    @staticmethod
    def _split_params(toks: list[Tok]) -> list[list[Tok]]:
        groups: list[list[Tok]] = []
        cur: list[Tok] = []
        for t in toks:
            if t.kind == T_COMMA:
                groups.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            groups.append(cur)
        return groups

    def _gosub(self, label: str, params: list[list[Tok]] | None = None,
               cont: tuple | None = None) -> None:
        idx = self.script.label_index(label)
        if idx is None:
            self._log_unsupported(f"label:{label}")
            return
        if len(self.stack) > 200:          # 防御：递归失控
            self._log_unsupported("stack-overflow")
            return
        self.stack.append(Frame(self.pc, params or [], label=self.current_label, cont=cont))
        self.pc = idx
        self.current_label = label.lower()

    # ------------------------------------------------------------ 流程控制
    def cmd_goto(self, a: Args) -> None:
        label = a.read_label()
        idx = self.script.label_index(label)
        if idx is None:
            self._log_unsupported(f"label:{label}")
            return
        self.pc = idx
        self.current_label = label.lower()

    def cmd_gosub(self, a: Args) -> None:
        label = a.read_label()
        self._gosub(label)

    def cmd_return(self, a: Args) -> None:
        if not self.stack:
            self.finished = True
            return
        fr = self.stack.pop()
        self.pc = fr.return_pc
        if fr.label:
            self.current_label = fr.label
        if fr.cont:
            parts, line_no = fr.cont
            if parts:
                self._run_parts(list(parts), line_no)

    def cmd_jumpf(self, a: Args) -> None:
        """跳到本行下一个 '~' 标记。"""
        for i in range(self.pc, min(self.pc + 400, len(self.script.instrs))):
            if self.script.instrs[i].kind == K_TILDE:
                self.pc = i + 1
                return

    def cmd_jumpb(self, a: Args) -> None:
        return

    def cmd_break(self, a: Args) -> None:
        """`break` / `break *label` —— 引擎 `ScriptParser::breakCommand` + `executeLabel`。

        引擎**不扫 `next` 找出口**，两条路：
          * 后一个 token 是 `*label` → 弹一层 for 栈 + `setCurrentLabel` 直接跳过去；
          * 否则置 `break_flag`，主循环进入"逐 token 跳过"状态
            （`executeLabel` 里 `if (break_flag && !isName("next"))` 那个分支），
            一直跳到名字是 `next` 的 token 才恢复；`nextCommand` 见 flag 就
            **不自增、直接弹栈**。
        所以 `break` 之后、`next` 之前的命令（含同一行 `break:xxx` 里的 xxx）都不执行 ——
        只设 flag 让 `next` 弹栈是不够的。
        """
        if not self.for_stack:
            # 引擎直接 errorAndExit("break: not in for loop")；我们按惯例不崩
            self._log_unsupported("break:not-in-for")
            return
        t = a.peek()
        if t is not None and t.kind == T_LABEL:
            self.for_stack.pop()
            idx = self.script.label_index(t.text)
            if idx is None:
                self._log_unsupported(f"label:{t.text}")
                return
            self.pc = idx
            self.current_label = t.text.lstrip("*").lower()
            return
        self.for_stack[-1]["brk"] = True
        self.break_skip = True

    def cmd_tablegoto(self, a: Args) -> None:
        """`tablegoto %var,*l0,*l1,...` —— 按值跳转表（引擎 `tablegotoCommand`）。

        读一个 0-based 序号，再把后续每个 `*label` 逐个编号，命中的那个 `setCurrentLabel`。
        序号越界时引擎**不跳**（继续执行本行剩余），我们照做。
        """
        no = a.read_int()
        n = 0
        while True:
            t = a.peek()
            if t is None:
                return
            a.i += 1
            if t.kind != T_LABEL:
                continue                      # 逗号、杂项：跳过
            if n == no:
                idx = self.script.label_index(t.text)
                if idx is None:
                    self._log_unsupported(f"label:{t.text}")
                    return
                self.pc = idx
                self.current_label = t.text.lstrip("*").lower()
                return
            n += 1

    def cmd_skip(self, a: Args) -> None:
        """`skip n` —— 在当前标签内按**行**前后跳（引擎 `ScriptParser::skipCommand`）。

        `目标行 = 当前标签起始行 + current_line + n`，而执行到 `skip` 这一刻
        `current_line` 就是"含 skip 的这一行在标签内的偏移"（主循环要等 `parseLine`
        返回 `RET_SKIP_LINE` 之后才 `++current_line`），所以化简成
        **`skip` 所在行的绝对行号 + n** —— 不用再管标签起始行。
        `n == 0` 按 1 算。引擎的 `getAddressByLine` 是全局行表，允许跨标签。
        """
        val = a.read_int()
        if val == 0:
            val = 1
        cur = self.pc - 1
        if not (0 <= cur < len(self.script.instrs)):
            return
        target = self.script.instrs[cur].line_no + val
        idx = self.script.index_of_line(max(target, 1))
        if idx >= len(self.script.instrs):
            # 引擎在这里会走过脚本末尾（UB）；我们停在脚本结束
            self.pc = idx
            return
        self.pc = idx
        self.current_label = self.script.label_of[idx]

    def cmd_loadgosub(self, a: Args) -> None:
        """`loadgosub *label` —— 登记"读档成功后要跑的标签"。

        引擎只在 `*define` 区接受它（`loadgosubCommand`），读档成功后在
        `loadgameCommand` 末尾 `gosubReal(loadgosub_label, script_h.getCurrent())`：
        **返回地址就是刚恢复的脚本位置**，所以这个标签负责把存档里没存的
        自定义状态（BGM、立绘、变量）补回来。
        实际调用点见 `Session._apply_engine_save`。
        """
        self.hook_loadgosub = a.read_label().lstrip("*")

    def run_loadgosub(self) -> None:
        """读档成功后 gosub `loadgosub` 登记的标签（引擎 `loadgameCommand` 末尾）。

        调用时机很关键：**脚本位置已经恢复之后**。`_gosub` 把当前 `pc` 作为返回地址
        压栈，正好对应引擎的 `gosubReal(loadgosub_label, script_h.getCurrent())` ——
        标签体跑完 `return` 就回到存档那一行继续。
        """
        if self.hook_loadgosub:
            self._gosub(self.hook_loadgosub)

    def cmd_for(self, a: Args) -> None:
        var_tok = a.peek()
        if var_tok is None or var_tok.kind != T_IVAR:
            return
        a.i += 1
        var = var_tok.text
        # for %i=0 to 5：等号是语法的一部分，跳过
        t0 = a.peek()
        if t0 is not None and t0.kind == T_OP and t0.text in ("=", "=="):
            a.i += 1
        start = a.read_int()
        # 跳过 'to'
        t = a.peek()
        if t is not None and t.kind == T_IDENT and t.text == "to":
            a.i += 1
        end = a.read_int()
        step = 1
        t = a.peek()
        if t is not None and t.kind == T_IDENT and t.text == "step":
            a.i += 1
            step = a.read_int() or 1
        self.state.set_int(var, start)
        self.for_stack.append({"var": var, "end": end, "step": step, "pc": self.pc - 1})

    def cmd_next(self, a: Args) -> None:
        if not self.for_stack:
            return
        fr = self.for_stack[-1]
        if fr.get("brk"):
            # break 落到这里：引擎见到 break_flag 时**不自增**，直接弹栈（循环结束）
            self.for_stack.pop()
            return
        val = self.state.get_int(fr["var"]) + fr["step"]
        self.state.set_int(fr["var"], val)
        if (fr["step"] > 0 and val <= fr["end"]) or (fr["step"] < 0 and val >= fr["end"]):
            self.pc = fr["pc"] + 1
        else:
            self.for_stack.pop()

    # ------------------------------------------------------------ 变量
    def cmd_dim(self, a: Args) -> None:
        """dim ?name[e1][e2]... —— 声明数组，只能在 define 段。

        引擎 `ScriptParser::dimCommand` → `ScriptHandler::declareDim`：
        **每维元素数 = 声明值 + 1**，数据全 0，且只有 int
        （`ArrayVariable::data` 是 `int*`，`dim $name[...]` 也一样）。
        """
        t = a.peek()
        if t is None or t.kind != T_AVAR:
            return
        a.i += 1
        name, decl = a.array_spec(t.text)
        if not name or not decl:
            return
        av = self.state.declare_array(name, [max(d, 0) + 1 for d in decl])
        log.debug("dim %s[%s] → 槽 %d，%d 个元素",
                       name, "][".join(str(d) for d in decl), av.no, av.size)

    def cmd_mov(self, a: Args) -> None:
        """mov / mov2..mov10 / movl：目标 + N 个值，按顺序写**连续位置**。

        引擎 `movCommand`：`mov10` 取 10、`movl` 无限（靠参数耗尽退出）、
        `mov3..mov9` 取命令名末位、其余 `mov` 取 1；第 i 个值写到
        `槽号 + i`（数组则是"线性下标 + i"）。万华镜不用 movN，Ever17 有 1 处 `mov10`。
        """
        t = a.peek()
        if t is None:
            return
        cmd = self._cur_cmd or ""
        if cmd == "movl":
            count = 1 << 30                      # 引擎是 infinite，由 a.eof() 收尾
        else:
            m = re.match(r"mov(\d+)$", cmd)
            count = int(m.group(1)) if m else 1
            count = max(1, min(count, 10))

        def has_comma(start: int, end: int) -> bool:
            """`start..end` 之间（含 end 这个位置）出现过逗号吗 —— 引擎的 `END_COMMA`。

            不能只看 `toks[end]`：`read_int` 内部的 `peek()` 会把尾随逗号顺手吃掉
            （那就落在区间里），而 `read_str` 会把逗号留在原地（那就正好在 end）。
            """
            if any(t.kind == T_COMMA for t in a.toks[start:end]):
                return True
            return end < len(a.toks) and a.toks[end].kind == T_COMMA

        prev = a.i

        if t.kind == T_IVAR:
            a.i += 1
            base = self._slot_of(a, t)
            for i in range(count):
                if i and not has_comma(prev, a.i):
                    break                     # 引擎按 END_COMMA 收尾
                if a.eof():
                    break
                prev = a.i
                self.state.int_slots[base + i] = a.read_int()
        elif t.kind == T_AVAR:
            a.i += 1
            for i in range(count):
                if i and not has_comma(prev, a.i):
                    break
                if a.eof():
                    break
                prev = a.i
                a.array_set(t.text, a.read_int(), offset=i)
        elif t.kind == T_SVAR:
            a.i += 1
            base = self._slot_of(a, t)
            for i in range(count):
                if i and not has_comma(prev, a.i):
                    break
                if a.eof():
                    break
                prev = a.i
                self.state.str_slots[base + i] = a.read_str()
        else:
            a.i += 1

    def cmd_numalias(self, a: Args) -> None:
        """numalias 名字,槽号 —— 建立"名字 → 槽位"的映射（% 和 $ 共用）。"""
        t = a.peek()
        if t is None or t.kind != T_IDENT:
            return
        a.i += 1
        self.state.set_alias(t.text, a.read_int())

    def cmd_stralias(self, a: Args) -> None:
        """stralias 名字,"文本" —— 字符串**常量**，不是变量。

        引擎里它只影响"裸名字"出现在字符串表达式里的情形；
        `$名字` 查的是 numalias，查不到就落到 0 号槽（见 state.State.resolve）。
        """
        t = a.peek()
        if t is None or t.kind != T_IDENT:
            return
        a.i += 1
        self.state.set_str_alias(t.text, a.read_str())

    def cmd_globalon(self, a: Args) -> None:
        """globalon —— 允许使用全局变量（>= global_border 的槽位）。

        引擎语义：这些槽位不写进存档，而是单独持久化（gloval.sav）；
        存档/读档只动 < border 的一般变量，所以读档不会把全局标志倒回去。
        """
        self.state.global_on = True

    def cmd_defsub(self, a: Args) -> None:
        t = a.peek()
        if t is not None and t.kind == T_IDENT:
            self.macros.add(t.text.lower())
            a.i += 1

    def _slot_of(self, a: Args, t: Tok) -> int:
        """`%name` 的槽号；`%?a[i]` 先取数组元素的值当槽号（引擎 parseInt 递归）。"""
        if t.text.startswith("?"):
            return a.array_get(t.text[1:])
        return self.state.resolve(t.text)

    def _binop(self, a: Args, fn) -> None:
        t = a.peek()
        if t is None:
            return
        if t.kind == T_AVAR:
            a.i += 1
            a.array_set(t.text, fn(a.array_get(t.text), a.read_int()))
            return
        if t.kind != T_IVAR:
            return
        a.i += 1
        slot = self._slot_of(a, t)
        self.state.int_slots[slot] = fn(int(self.state.int_slots.get(slot, 0)), a.read_int())

    def cmd_add(self, a: Args) -> None:
        self._binop(a, lambda x, y: x + y)

    def cmd_sub(self, a: Args) -> None:
        self._binop(a, lambda x, y: x - y)

    def cmd_mul(self, a: Args) -> None:
        self._binop(a, lambda x, y: x * y)

    def cmd_div(self, a: Args) -> None:
        self._binop(a, lambda x, y: int(x / y) if y else 0)

    def cmd_mod(self, a: Args) -> None:
        self._binop(a, lambda x, y: x % y if y else 0)

    def cmd_inc(self, a: Args) -> None:
        self._binop(a, lambda x, y: x + 1)

    def cmd_dec(self, a: Args) -> None:
        self._binop(a, lambda x, y: x - 1)

    def cmd_itoa(self, a: Args) -> None:
        t = a.peek()
        if t is None or t.kind != T_SVAR:
            return
        a.i += 1
        self.state.str_slots[self._slot_of(a, t)] = str(a.read_int())

    cmd_itoa2 = cmd_itoa

    def cmd_atoi(self, a: Args) -> None:
        t = a.peek()
        if t is None or t.kind != T_IVAR:
            return
        a.i += 1
        s = a.read_str()
        try:
            self.state.set_int(t.text, int(s or 0))
        except ValueError:
            self.state.set_int(t.text, 0)

    def cmd_len(self, a: Args) -> None:
        """len = **字节数**（引擎用 strlen）。GBK 下一个汉字算 2。

        脚本大量用它算居中：`mov %7,400:sub %7,%6`，按字符数算会整体偏右。
        """
        t = a.peek()
        if t is None or t.kind != T_IVAR:
            return
        a.i += 1
        text = a.read_str()
        try:
            n = len(text.encode(self.encoding or "gbk", errors="replace"))
        except LookupError:
            n = len(text)
        self.state.set_int(t.text, n)

    def cmd_rnd(self, a: Args) -> None:
        import random
        t = a.peek()
        if t is None or t.kind != T_IVAR:
            return
        a.i += 1
        n = a.read_int()
        self.state.set_int(t.text, random.randrange(n) if n > 0 else 0)

    def cmd_getparam(self, a: Args) -> None:
        if not self.stack:
            return
        fr = self.stack[-1]
        for t in a.remaining():
            if t.kind not in (T_SVAR, T_IVAR):
                continue
            val = ""
            if fr.param_index < len(fr.params):
                val = self._param_to_str(fr.params[fr.param_index])
                fr.param_index += 1
            if t.kind == T_SVAR:
                self.state.set_str(t.text, val)
            else:
                try:
                    self.state.set_int(t.text, int(val or 0))
                except ValueError:
                    self.state.set_int(t.text, 0)

    def _param_to_str(self, toks: list[Tok]) -> str:
        if not toks:
            return ""
        if len(toks) == 1:
            t = toks[0]
            if t.kind == T_STR:
                return t.text
            if t.kind == T_SVAR:
                return self.state.get_str(t.text)
            if t.kind == T_IVAR:
                return str(self.state.get_int(t.text))
        # 表达式（如 %sub1+510）
        args = self._args(toks)
        if any(t.kind == T_STR for t in toks):
            return args.read_str()
        return str(args.read_int())

    def cmd_gettag(self, a: Args) -> None:
        targets = [t for t in a.remaining() if t.kind in (T_SVAR, T_IVAR)]
        vals = list(self._pending_tag) + ["", "", ""]
        for i, t in enumerate(targets[:3]):
            if t.kind == T_SVAR:
                self.state.set_str(t.text, vals[i])

    def cmd_gettext(self, a: Args) -> None:
        t = a.peek()
        if t is None or t.kind != T_SVAR:
            return
        a.i += 1
        page = self.state.page
        self.state.set_str(t.text, page.as_text() if page else "")

    # ------------------------------------------------------------ 图像
    def cmd_bg(self, a: Args) -> None:
        # bg "file",effect,duration  /  bg "file",x,y  /  bg black
        first = a.peek()
        if first is None:
            return
        name = a.read_str()
        if name.lower() in ("black", "white", "red", "blue", "green"):
            self.state.bg_image = None
            self.state.bg_source = ""
            self.state.bg_ops = []
            self.state.bg_baked = False
            self.state.overlay = None
            self.state.bg_color = {
                "black": (0, 0, 0), "white": (255, 255, 255),
                "red": (255, 0, 0), "blue": (0, 0, 255), "green": (0, 255, 0),
            }[name.lower()]
            self.state.bg_name = name
            return
        # 只查文件在不在（不读内容）：找不到就保留旧背景，和引擎一致
        if not self.renderer.has_file(name):
            self._log_unsupported(f"image:{name}")
            return
        # 换背景不立刻解码 —— 万华镜2 的动画就是一串 20ms 的 bg 连发，
        # 真正会被看到的只有停下来那一刻的那张（见 render.DeferredImage）
        self.state.bg_image = self.renderer.background(name)
        self.state.bg_name = name
        self.state.bg_source = name
        # 换背景 = 整屏重绘：之前 blt 上去的像素和 bgcopy 的烘焙全部作废
        self.state.overlay = None
        self.state.bg_ops = []
        self.state.bg_baked = False

    def cmd_print(self, a: Args) -> None:
        return

    def cmd_cell(self, a: Args) -> None:
        """cell 槽号,帧号 —— 切到长条图的第 N 格（引擎 `AnimationInfo::setCell`）。

        存档格缩略图靠它指定显示哪一帧；越界会夹到首/末格。
        """
        sid = a.read_int()
        cell = a.read_int()
        sp = self.state.sprites.get(sid)
        if sp is None or not sp.tag:
            return
        sp.cell = int(cell)
        sp.image, sp.kind = self.renderer.sprite_image(
            sp.tag, self.state.trans_mode, sp.cell)

    def _load_sprite(self, sid: int, tag: str, x: int | None, y: int | None) -> None:
        sp = self.state.sprite(sid)
        sp.tag = tag
        sp.cell = 0                        # 换图 = 从第 0 帧开始
        # 图片型走**延迟句柄**：这里只记文件名，合成画面时才解码。
        # 透明模式在这一刻就快照进句柄里（引擎也是载入时建 alpha 的）。
        img, kind = self.renderer.sprite_image(
            tag, self.state.trans_mode, sp.cell)
        sp.image = img
        sp.kind = kind
        sp.text = self.renderer.sprite_text(tag) if kind == "text" else ""
        if x is not None:
            sp.x = x
        if y is not None:
            sp.y = y

    def cmd_lsp(self, a: Args) -> None:
        sid = a.read_int()
        tag = self._read_tag(a)
        x = a.read_int()
        y = a.read_int()
        self._load_sprite(sid, tag, x, y)
        self.state.sprite(sid).visible = True

    def cmd_lsph(self, a: Args) -> None:
        sid = a.read_int()
        tag = self._read_tag(a)
        x = a.read_int()
        y = a.read_int()
        self._load_sprite(sid, tag, x, y)
        self.state.sprite(sid).visible = False

    def _read_tag(self, a: Args) -> str:
        """tag 是字符串表达式：`"stand/"+$file0+$file1+".png"` 这种要拼起来。

        引号内的 ',' 属于 tag 内容（`:a/20,50,0;bg3/xt.png`），read_str 只在
        引号外遇到 ',' 才停，正好符合。
        """
        return a.read_str()

    def cmd_vsp(self, a: Args) -> None:
        sid = a.read_int()
        flag = a.read_int()
        self.state.sprite(sid).visible = bool(flag)

    def cmd_csp(self, a: Args) -> None:
        sid = a.read_int()
        if sid < 0:                       # 引擎：no==-1 表示清空所有精灵
            self.state.sprites.clear()
            self.state.ui_sprites.clear()
            return
        self.state.sprites.pop(sid, None)
        self.state.ui_sprites.discard(sid)

    def cmd_amsp(self, a: Args) -> None:
        sid = a.read_int()
        x = a.read_int()
        y = a.read_int()
        sp = self.state.sprite(sid)
        sp.x, sp.y = x, y

    def cmd_msp(self, a: Args) -> None:
        self.cmd_amsp(a)

    def cmd_getspsize(self, a: Args) -> None:
        sid = a.read_int()
        targets = [t for t in a.remaining() if t.kind == T_IVAR]
        sp = self.state.sprite(sid)
        w = sp.image.width if sp.image is not None else 0
        h = sp.image.height if sp.image is not None else 0
        if targets:
            self.state.set_int(targets[0].text, w)
        if len(targets) > 1:
            self.state.set_int(targets[1].text, h)

    def cmd_allspresume(self, a: Args) -> None:
        for sp in self.state.sprites.values():
            sp.visible = True

    def cmd_allsphide(self, a: Args) -> None:
        for sp in self.state.sprites.values():
            sp.visible = False

    def cmd_monocro(self, a: Args) -> None:
        return

    def cmd_humanz(self, a: Args) -> None:
        """设定文本框的 z 序：id 大于它的精灵画在文本框之上。"""
        self.state.humanz = a.read_int()

    # ------------------------------------------------------------ 文本框
    def _setwindow_core(self, a: Args) -> None:
        """`setwindow` / `setwindow3` 的公共解析 —— 引擎两个命令都调 `setwindowCore()`。

        参数顺序（`ONScripter_command.cpp`）：
        `x,y,num_x,num_y,fsize_x,fsize_y,pitch_off_x,pitch_off_y,wait,bold,shadow, 窗口串, 坐标`

        几个容易写错的点：
          * **pitch 是偏移量**：真实行距 = `offset + font_size`（不是绝对值）
          * 窗口串是 `#RRGGBB` 时**读 4 个坐标** `(x0,y0,x1,y1)`，宽高 = 差 + 1；
            是图片时只读 2 个坐标（贴图位置）
          * 两个命令都会把 `indent_offset` 清零
        """
        cfg = self.state.window
        cfg.x = a.read_int()
        cfg.y = a.read_int()
        cfg.num_x = a.read_int()
        cfg.num_y = a.read_int()
        cfg.font_size_x = a.read_int()
        cfg.font_size_y = a.read_int()
        cfg.pitch_x = a.read_int() + cfg.font_size_x
        cfg.pitch_y = a.read_int() + cfg.font_size_y
        # 引擎缺参数时 pitch 会变成 0（结果就是所有行叠在一起）。这里兜底成字宽/字高 ——
        # 否则 `max_w = num_x * 0` 会让每个字都换行，页面直接炸。
        if cfg.pitch_x <= 0:
            cfg.pitch_x = cfg.font_size_x or 26
        if cfg.pitch_y <= 0:
            cfg.pitch_y = cfg.font_size_y or cfg.font_size_x or 26
        cfg.wait_time = a.read_int()
        cfg.bold = bool(a.read_int())
        cfg.shadow = bool(a.read_int())
        # 引擎 setwindowCommand/setwindow3Command 里紧跟 setwindowCore 的那几行
        self.state.indent_offset = 0
        self.state.text_locate = (0, 0)
        cfg.active = True
        if a.eof():
            return
        val = a.read_str()
        if val.startswith("#"):
            cfg.frame_color = val
            cfg.frame_path = ""
            cfg.frame_image = None
            x0 = a.read_int()
            y0 = a.read_int()
            x1 = a.read_int()
            y1 = a.read_int()
            cfg.frame_x, cfg.frame_y = x0, y0
            cfg.frame_w = max(x1 - x0 + 1, 0)
            cfg.frame_h = max(y1 - y0 + 1, 0)
        else:
            cfg.frame_color = ""
            cfg.frame_path = val
            cfg.frame_w = cfg.frame_h = 0
            if not a.eof():
                cfg.frame_x = a.read_int()
                cfg.frame_y = a.read_int()
            self._bake_window_frame(cfg)

    def cmd_setwindow3(self, a: Args) -> None:
        """`setwindow3` —— 与 `setwindow` 同一套参数，区别是它会**清空当前页**
        （引擎 `setwindow3Command` 调 `clearCurrentPage()`）。"""
        self._setwindow_core(a)
        self.state.page = None
        self.page_from_save = False

    def _bake_window_frame(self, cfg) -> None:
        """把文本框图片按**当前**的全局透明模式烤好。

        引擎是在 setwindow3 那一刻建好窗口图的（`parseTaggedString` + `setupAnimationInfo`），
        之后 `transmode` 再变也不影响它——所以必须在这里做，不能等到画的时候。
        """
        cfg.frame_image = None
        if not cfg.frame_path:
            return
        img, _kind = self.renderer.build_sprite_image(cfg.frame_path, self.state.trans_mode)
        cfg.frame_image = img

    def cmd_setwindow(self, a: Args) -> None:
        """`setwindow` —— 与 `setwindow3` 参数完全一样（同一个 `setwindowCore`），
        差别只在收尾：它清的是回看缓冲（`lookbackflush`），不清当前页。"""
        self._setwindow_core(a)

    def cmd_texton(self, a: Args) -> None:
        self.state.text_on = True

    def cmd_textoff(self, a: Args) -> None:
        self.state.text_on = False

    def cmd_texec(self, a: Args) -> None:
        return

    def cmd_textclear(self, a: Args) -> None:
        self.state.page = None
        self.state.text_locate = (0, 0)

    def cmd_erasetextwindow(self, a: Args) -> None:
        self.state.text_window_erased = bool(a.read_int())

    def cmd_linepage(self, a: Args) -> None:
        """`linepage` / `linepage2`：给每条文本行自动补 clickstr（引擎 `readToken`）。

        万华镜在 define 区用了 `linepage`，所以它"每行都停"；Ever17 没用，
        连续文本行会累积在同一页里 —— 两种都要支持，不能写死。
        """
        if (self._cur_cmd or "") == "linepage2":
            self.state.linepage_mode = 2
            self.state.clickstr_line = a.read_int()
        else:
            self.state.linepage_mode = 1

    def cmd_textspeed(self, a: Args) -> None:
        return

    # ------------------------------------------------------------ 文本排版 / 装饰
    def cmd_textcolor(self, a: Args) -> None:
        """`textcolor #RRGGBB` —— 正文颜色（引擎 `sentence_font.color`）。"""
        val = a.read_str()
        if val.startswith("#"):
            self.state.window.text_color = val

    def cmd_indent(self, a: Args) -> None:
        """`indent n` —— **每次换行后**行首插 n 个全角空格（引擎 `indent_offset`）。

        注意不是"首行缩进"，而是 `newLine()` 之后 `for(i<indent_offset) advanceCharInHankaku(2)`，
        空格还会写进 page 文本（`current_page->add(0x8140)`）。
        """
        self.state.indent_offset = max(0, a.read_int())

    def cmd_locate(self, a: Args) -> None:
        """`locate x,y` —— 把文字光标挪到第 x 格、第 y 行（单位是字符格，不是像素）。

        引擎 `FontInfo::setXY` 存的是 `x*2`，而 `x()` 算的是 `xy*pitch/2 + top_xy`，
        所以 `locate 2,1` = 右移 2×pitch_x、下移 1×pitch_y。换页时 `clearCurrentPage`
        会把它归零（见 `_new_page`）。
        """
        x = a.read_int()
        y = a.read_int()
        self.state.text_locate = (x, y)

    def cmd_texthide(self, a: Args) -> None:
        """`texthide` —— 文本层只是不画，内容还在（和 `textoff` 不是一回事）。"""
        self.state.text_hidden = True

    def cmd_textshow(self, a: Args) -> None:
        """`textshow` —— 把 `texthide` 藏起来的文本层重画出来。"""
        self.state.text_hidden = False

    def _append_page_lines(self, lines: list[str]) -> None:
        if self.state.page is None:
            self._new_page(self.page_name)
        self.state.page.lines.extend(lines)

    def cmd_br(self, a: Args) -> None:
        """`br` —— 在文本层插入一个换行（做空行用）：`sentence_font.newLine()` + 页里加 0x0a。"""
        self._append_page_lines([""])

    def cmd_puttext(self, a: Args) -> None:
        """`puttext "str"` —— 往文本层直接写一段"指示文字"。

        引擎是 `enterTextDisplayMode(false)` + `processText()`：写进去、**不换页、不等待、
        不推进剧情**。常出现在 if 里当短提示（"已保存""调查中"）。
        """
        text = a.read_str()
        if not text:
            return
        body = text[1:] if text.startswith("`") else text
        lines = self.renderer.wrap(body, self.state.window, self.state.indent_offset)
        self._append_page_lines(lines)
        if not self.state.text_window_erased:
            self.state.text_on = True

    def cmd_clickstr(self, a: Args) -> None:
        """`clickstr "chars",line` —— 指定哪些字符触发"等点击"，以及判满的行数。

        默认字符集是 `\\` 和 `@`（引擎 `checkClickstr`）。页面模型里"哪一行会停"
        就是按这个集合判断的，所以这里改的是真行为，不只是配置。
        """
        chars = a.read_str()
        n = a.read_int()
        if chars:
            self.state.clickstr_chars = chars
        self.state.clickstr_line = max(0, n)

    def cmd_kinsoku(self, a: Args) -> None:
        """`kinsoku` —— 开启禁则处理。

        本项目的禁则表**本来就是常开**的（`render.py` 的内置表），所以这条是空转；
        真正能改表的是 `setkinsoku` / `addkinsoku`。
        """
        return

    def cmd_setkinsoku(self, a: Args) -> None:
        """`setkinsoku "head","tail"` —— 整个替换禁则表。

        head = 不能出现在行首的字符（。，」等，允许悬挂出右边界）；
        tail = 不能留在行尾的字符（「（等，要跟下一个字一起挪到下一行）。
        """
        head = a.read_str()
        tail = a.read_str()
        self.state.window.kinsoku_head = head
        self.state.window.kinsoku_tail = tail

    def cmd_addkinsoku(self, a: Args) -> None:
        """`addkinsoku "name","chars"` —— 往禁则表里**追加**字符。

        引擎读两个字符串：`readStr()` 丢掉第一个（名字），第二个才是字符集，
        所以第一个参数是摆设，别拿它当字符表。
        """
        a.read_str()
        chars = a.read_str()
        if chars:
            cfg = self.state.window
            cfg.kinsoku_head = (cfg.kinsoku_head or self.renderer.START_KINSOKU) + chars
            cfg.kinsoku_tail = (cfg.kinsoku_tail or self.renderer.END_KINSOKU) + chars

    def cmd_pagetag(self, a: Args) -> None:
        """`pagetag` —— 打开"页标记"（引擎 `pagetag_flag`，每页开始时 `page_enter_status = 1`）。"""
        self.state.pagetag = True

    def cmd_pretextgosub(self, a: Args) -> None:
        self.hook_pretext = a.read_label()

    def cmd_textgosub(self, a: Args) -> None:
        self.hook_text = a.read_label()

    def cmd_textbtnwait(self, a: Args) -> None:
        # 和 btnwait 完全同一套语义（都要记住变量名，否则点击结果写不回去）
        self.cmd_btnwait(a)

    def cmd_wait(self, a: Args) -> None:
        return

    # >= 这个毫秒数的 `delay` 才留一帧。
    # 800 是拿 Ever17 的实际分布定的：章节日期画面是 `delay 1000`（要留帧），
    # 而时钟数字逐位动画是 `delay 500`×3、标题转场是 `delay 700`（都不该停）。
    DELAY_FRAME_MS = 800

    def cmd_delay(self, a: Args) -> None:
        """`delay ms` —— 演出停顿（引擎里是真阻塞）。

        agent 侧没有真实时钟，也不该让一次调用真的挂住 n 毫秒。但**长停顿
        必须留一帧**：Ever17 的章节日期画面就是

            chapterCutin → textoff : bg "background\\cal_501.jpg",10,1000 : delay 1000

        紧跟着还有 `bgload` 会把日期图覆盖掉。`delay` 若直接返回，两次换背景
        在同一次 run 里连续执行，那张日期画面**一帧都不会被合成**
        （差异 5 的根因：不是缺命令，是中间帧被跳过了）。

        所以 >= `DELAY_FRAME_MS` 的 delay 退化成一次"可推进的暂停"：
        先把当前画面留给人看，下一次 click / step 再继续跑。
        短 delay（Ever17 里 30~180ms 的动画同步，共 280 多次）仍然直接跳过。
        """
        val = a.read_int()
        if val >= self.DELAY_FRAME_MS:
            self.waiting = "delay"

    # ------------------------------------------------------------ 按钮
    def _sprite_rect(self, sprite_no: int):
        sp = self.state.sprites.get(sprite_no)
        if sp is None or sp.image is None:
            return None
        # 延迟句柄也能给尺寸（只读文件头），所以命中区和以前完全一样
        w, h = sp.image.width, sp.image.height
        if w <= 0 or h <= 0:            # 图根本没载进来 → 引擎也不注册这个按钮
            return None
        return (int(sp.x), int(sp.y), w, h)

    def _add_button(self, button) -> None:
        self.state.buttons.append(button)

    def clear_buttons(self) -> None:
        self.state.buttons.clear()

    def apply_exbtn_ctl(self, ctl: str) -> None:
        """解析 exbtn 控制串：C=隐藏、P=显示、S=放音(忽略)、M=移动。"""
        i, n = 0, len(ctl)
        while i < n:
            c = ctl[i]
            if c in "Cc":
                i += 1
                a, i = self._ctl_number(ctl, i)
                b = a
                if i < n and ctl[i] == "-" and ctl[i + 1:i + 2].isdigit():
                    i += 1
                    b, i = self._ctl_number(ctl, i)
                for sid in range(a, b + 1):
                    sp = self.state.sprites.get(sid)
                    if sp is not None:
                        sp.visible = False
            elif c in "Pp":
                i += 1
                a, i = self._ctl_number(ctl, i)
                sp = self.state.sprites.get(a)
                if sp is not None:
                    sp.visible = True
                if i < n and ctl[i] == ",":
                    i += 1
                    _, i = self._ctl_number(ctl, i)
            elif c in "Ss":
                j = ctl.find(")", i)
                i = (j + 1) if j >= 0 else n
            elif c in "Mm":
                i += 1
                _, i = self._ctl_number(ctl, i)
                for _ in range(2):
                    if i < n and ctl[i] == ",":
                        i += 1
                        _, i = self._ctl_number(ctl, i)
            else:
                i += 1

    @staticmethod
    def _ctl_number(s: str, i: int):
        j = i
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == i:
            return 0, i
        return int(s[i:j]), j

    def cmd_btn(self, a: Args) -> None:
        no = a.read_int()
        x = a.read_int()
        y = a.read_int()
        w = a.read_int()
        h = a.read_int()
        self._add_button(Button(no=no, kind="rect", rect=(x, y, w, h)))

    def cmd_spbtn(self, a: Args) -> None:
        sid = a.read_int()
        no = a.read_int()
        rect = self._sprite_rect(sid)
        if rect is None:            # 引擎：精灵没有图就静默不注册
            return
        self._add_button(Button(no=no, kind="sprite", sprite_no=sid, rect=rect))

    def cmd_exbtn(self, a: Args) -> None:
        sid = a.read_int()
        no = a.read_int()
        ctl = a.read_str()
        rect = self._sprite_rect(sid)
        if rect is None:
            return
        self._add_button(Button(no=no, kind="exbtn", sprite_no=sid, rect=rect,
                                ctl_hover=ctl))
        # 注意：exbtn 自带的 ctl 是"悬停态"，注册时不能生效；
        # 空闲态由 exbtn_d 决定，在 flush/等待前统一应用。

    def cmd_exbtn_d(self, a: Args) -> None:
        ctl = a.read_str()
        self.state.exbtn_default_ctl = ctl
        for b in self.state.buttons:
            if b.kind == "exbtn":
                b.ctl_idle = ctl
        self.apply_exbtn_ctl(ctl)

    def cmd_btndown(self, a: Args) -> None:
        return

    def cmd_strsp(self, a: Args) -> None:
        """字符串精灵：strsp id,text,x,y,...,size_x,size_y,...,#RRGGBB"""
        toks = [t for t in a.remaining() if t.kind != T_COMMA]
        if len(toks) < 4:
            return
        sid = a.read_int()
        text = a.read_str()
        x = a.read_int()
        y = a.read_int()
        nums = []
        while not a.eof() and len(nums) < 9:
            t = a.peek()
            if t is None:
                break
            if t.kind == T_NUM or t.kind == T_IVAR:
                nums.append(a.read_int())
            else:
                break
        color = "#FFFFFF"
        t = a.peek()
        if t is not None and t.kind == T_STR and t.text.startswith("#"):
            color = a.read_str()
        size = 20
        if len(nums) >= 3:
            size = nums[2] or 20           # 第 3 个数是字号
        img = self.renderer.render_text_sprite(size, color, text)
        sp = self.state.sprite(sid)
        sp.tag = f":strsp;{text}"
        sp.kind, sp.text, sp.image = "text", text, img
        sp.x, sp.y = x, y

    def cmd_strsph(self, a: Args) -> None:
        """`strsph` 与 `strsp` 是同一个 `strspCommand`，只差一个"是否竖排"的开关。

        参数形式完全一致（引擎只多读了 flag，参数表没变），竖排我们本来就不做，
        按横排渲染即可 —— 之前当桩掉，会让用到它的界面整块文字消失。
        """
        self.cmd_strsp(a)

    def cmd_bar(self, a: Args) -> None:
        """进度/滚动条：bar id,dir,x,y,w,h,...,#RRGGBB —— 画成实色块"""
        toks = [t for t in a.remaining() if t.kind != T_COMMA]
        sid = a.read_int()
        a.read_int()                       # dir
        x = a.read_int()
        y = a.read_int()
        w = a.read_int()
        h = a.read_int()
        color = "#DDDDDD"
        for t in toks:
            if t.kind == T_STR and t.text.startswith("#"):
                color = t.text
                break
        img = self.renderer.solid_image(max(w, 1), max(h, 1), color)
        sp = self.state.sprite(sid + 9000)  # bar 用独立编号，避免和精灵冲突
        sp.tag = f":bar;{color}"
        sp.kind, sp.image = "solid", img
        sp.x, sp.y = x, y
        sp.visible = True

    def cmd_getmousepos(self, a: Args) -> None:
        """getmousepos %x,%y —— 最近一次鼠标事件的坐标。

        引擎取 `current_button_state`（游戏坐标系）；我们记的是 click 传进来的
        画面坐标，两者在 1:1 分辨率下相同。万华镜的存档/回想格子定位靠它：
        `mov %savedatanow, (%savepos + %cursory - save_data_y)/save_height + 1`
        """
        for i in range(2):
            t = a.peek()
            if t is None:
                return
            a.i += 1
            self.state.int_slots[self._slot_of(a, t)] = int(self.state.last_cursor[i])

    def cmd_savegame(self, a: Args) -> None:
        slot = a.read_int()
        if self.on_save:
            self.on_save(slot)
        else:
            self._log_unsupported(f"savegame:{slot}")

    def cmd_loadgame(self, a: Args) -> None:
        slot = a.read_int()
        if self.on_load:
            self.on_load(slot)
        else:
            self._log_unsupported(f"loadgame:{slot}")

    def cmd_savefileexist(self, a: Args) -> None:
        t = a.peek()
        if t is None or t.kind != T_IVAR:
            return
        a.i += 1
        slot = a.read_int()
        ok = bool(self.on_exists(slot)) if self.on_exists else False
        self.state.set_int(t.text, 1 if ok else 0)

    def cmd_savetime(self, a: Args) -> None:
        slot = a.read_int()
        targets = [t for t in a.remaining() if t.kind == T_IVAR]
        vals = self.on_savetime(slot) if self.on_savetime else (0, 0, 0, 0)
        for t, v in zip(targets, vals):
            self.state.set_int(t.text, v)

    def cmd_barclear(self, a: Args) -> None:
        for sid in [k for k in self.state.sprites if k >= 9000]:
            self.state.sprites.pop(sid, None)

    def cmd_split(self, a: Args) -> None:
        """split $src,",",$a,$b,... —— 也支持 $%var 这种"用变量值当变量名"的写法"""
        raw = getattr(self, "_raw_args", "")
        parts = raw.split(",")
        if len(parts) < 3:
            return
        src = self._resolve_str_expr(parts[0])
        sep = parts[1].strip().strip('"')
        values = src.split(sep) if sep else [src]
        for i, target in enumerate(parts[2:]):
            name = self._str_var_name(target)
            if not name:
                continue
            self.state.set_str(name, values[i] if i < len(values) else "")

    def cmd_mid(self, a: Args) -> None:
        """mid $dst,$src,start,len"""
        raw = getattr(self, "_raw_args", "")
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 4:
            return
        dst = self._str_var_name(parts[0])
        src = self._resolve_str_expr(parts[1])
        start = self._resolve_int_expr(parts[2])
        length = self._resolve_int_expr(parts[3])
        if dst:
            self.state.set_str(dst, src[start:start + length] if length else src[start:])

    def _str_var_name(self, expr: str) -> str:
        e = expr.strip()
        if e.startswith("$%"):                 # $%sub1 → 取 %sub1 的值当名字
            inner = e[2:].strip()
            val = self._resolve_int_expr(inner)
            return str(val)
        if e.startswith("$"):
            return e[1:].strip().lower()
        return ""

    def _resolve_int_expr(self, expr: str) -> int:
        args = self._args(tokenize(expr))
        return args.read_int()

    def _resolve_str_expr(self, expr: str) -> str:
        args = self._args(tokenize(expr))
        return args.read_str()

    def cmd_btnwait(self, a: Args) -> None:
        t = a.peek()
        self.state.btnwait_var = t.text if (t is not None and t.kind == T_IVAR) else ""
        if self.state.btnwait_var:
            self.state.set_int(self.state.btnwait_var, 0)
        # 等待前把空闲态摆正（引擎每次 flush 都会应用 exbtn_d 的 ctl）
        if self.state.exbtn_default_ctl:
            self.apply_exbtn_ctl(self.state.exbtn_default_ctl)
        self.waiting = "btn"

    def hit_test(self, x: int, y: int) -> int:
        """后注册的按钮先命中（引擎是头插链表）。"""
        for b in reversed(self.state.buttons):
            if b.contains(x, y):
                return b.no
        return 0

    def resolve_click(self, x: int | None, y: int | None) -> int:
        """把一次点击翻译成 btnwait 的返回值。"""
        if x is None or y is None:
            return 0
        return self.hit_test(int(x), int(y))

    # ------------------------------------------------------------ 选择肢
    def cmd_csel(self, a: Args) -> None:
        toks = [t for t in a.remaining() if t.kind != T_COMMA]
        links = []
        i = 0
        while i + 1 < len(toks):
            text_tok, label_tok = toks[i], toks[i + 1]
            text = text_tok.text if text_tok.kind == T_STR else self._param_to_str([text_tok])
            label = label_tok.text if label_tok.kind == T_LABEL else ""
            if label:
                links.append(SelectLink(text=text, label=label))
            i += 2
        self.state.select_links = links
        # 引擎在 CSEL 模式下把当前标签设成 customsel，界面由脚本自己画
        idx = self.script.label_index("customsel")
        if idx is None:
            self.waiting = "btn"        # 没有自定义界面就退化成等待 agent 选择
            return
        self.pc = idx
        self.current_label = "customsel"

    def cmd_cselgoto(self, a: Args) -> None:
        n = a.read_int()
        links = self.state.select_links
        if not (0 <= n < len(links)):
            self._log_unsupported(f"cselgoto:{n}")
            return
        label = links[n].label
        self.state.select_links = []
        self.state.buttons.clear()
        idx = self.script.label_index(label)
        if idx is None:
            self._log_unsupported(f"label:{label}")
            return
        self.pc = idx
        self.current_label = label.lower()

    def cmd_getcselnum(self, a: Args) -> None:
        t = a.peek()
        if t is None or t.kind != T_IVAR:
            return
        a.i += 1
        self.state.set_int(t.text, len(self.state.select_links))

    def cmd_getcselstr(self, a: Args) -> None:
        t = a.peek()
        if t is None or t.kind != T_SVAR:
            return
        a.i += 1
        n = a.read_int()
        links = self.state.select_links
        self.state.set_str(t.text, links[n].text if 0 <= n < len(links) else "")

    def cmd_nextcsel(self, a: Args) -> None:
        t = a.peek()
        if t is not None and t.kind == T_IVAR:
            self.state.set_int(t.text, 0)


    # ------------------------------------------------------------ 立绘（tachi）
    # 引擎里 ld / cl 操作的是 tachi_info[3]（左中右），和普通 lsp 精灵是两套东西：
    # 位置固定按 no 算 x = 画面宽*(no+1)/4 - 图宽/2，贴底 y = underline - 图高。
    TACHI_POS = {"l": 0, "c": 1, "r": 2}

    def _tachi(self, no: int):
        sp = self.state.tachi.get(no)
        if sp is None:
            sp = Sprite(no)
            self.state.tachi[no] = sp
        return sp

    def _tachi_xy(self, no: int, img) -> tuple[int, int]:
        w = self.renderer.width
        h = self.state.underline or self.renderer.height
        return (w * (no + 1) // 4 - img.width // 2, h - img.height)

    def cmd_ld(self, a: Args) -> None:
        """ld l|c|r,"file",effect,duration —— 载入立绘。"""
        t = a.peek()
        if t is None:
            return
        loc = (t.text or "").strip().lower()[:1]
        a.i += 1
        no = self.TACHI_POS.get(loc)
        if no is None:
            return
        name = a.read_str()
        if not name:
            return
        img, _kind = self.renderer.sprite_image(name, self.state.trans_mode)
        if img is None:
            self._log_unsupported(f"image:{name}")
            return
        sp = self._tachi(no)
        sp.tag, sp.image, sp.kind, sp.text = name, img, "image", ""
        sp.x, sp.y = self._tachi_xy(no, img)
        sp.visible = True

    def cmd_cl(self, a: Args) -> None:
        """cl l|c|r|a —— 清立绘。"""
        t = a.peek()
        if t is not None and t.kind != T_STR:
            a.i += 1
        loc = (t.text or "").strip().lower()[:1] if t is not None else "a"
        targets = {"l": (0,), "c": (1,), "r": (2,)}.get(loc, (0, 1, 2))
        for no in targets:
            sp = self.state.tachi.get(no)
            if sp is not None:
                sp.visible = False
                sp.image = None
                sp.tag = ""

    def cmd_underline(self, a: Args) -> None:
        self.state.underline = a.read_int()

    def cmd_transmode(self, a: Args) -> None:
        """transmode {leftup,copy,alpha} —— 全局透明模式。

        两款实测游戏都设了 `transmode alpha`：PNG 保留自带 alpha，
        而 JPG/BMP 没有 alpha 通道 → 引擎会用**图片右半当 alpha 通道**
        （NScripter 手册原文，见 spritetag.py 的说明）。
        """
        t = a.peek()
        if t is None:
            return
        mode = (t.text or "").strip().lower()
        if mode in ("leftup", "copy", "alpha"):
            self.state.trans_mode = mode
        else:
            self._log_unsupported(f"transmode:{mode}")

    # ------------------------------------------------------------ blt / 截图缓存
    def _overlay(self):
        """blt 的落点：和画面同尺寸的透明层。"""
        from PIL import Image
        if self.state.overlay is None:
            self.state.overlay = Image.new(
                "RGBA", (self.renderer.width, self.renderer.height), (0, 0, 0, 0))
        return self.state.overlay

    def cmd_btndef(self, a: Args) -> None:
        """btndef 无论带什么参数都会清空按钮表（引擎 deleteButtonLink）。

        同时把给的图载入成 blt 的图源（引擎里就是 btndef_info.image_surface）。
        """
        self.clear_buttons()
        self.state.btndef_image = ""
        self.state.btndef_pixels = None
        if a.eof():
            return
        # 引号串和裸词都要吃：`btndef "background\2.png"` 和 `btndef clear` 都常见
        name = a.read_str()
        if name and name.lower() != "clear":
            self.state.btndef_image = name
            self.state.btndef_pixels = self.renderer.load_image(name)

    def _apply_blt(self, image_name: str, box) -> bool:
        """一次 blt：把 `image_name` 的一块贴到 overlay 上。

        读档重放也走这里 —— 所以 blt 的效果是"可以按参数重算"的，
        存档不必存像素，只存这 8 个参数 + 图源文件名。
        """
        if not image_name or box is None or len(box) < 8:
            return False
        src = self.renderer.load_image(image_name)
        if src is None:
            return False
        dx, dy, dw, dh, sx, sy, sw, sh = (int(v) for v in box[:8])
        if dw <= 0 or dh <= 0 or sw <= 0 or sh <= 0:
            return False
        sx, sy = max(sx, 0), max(sy, 0)
        sw = min(sw, src.width - sx)
        sh = min(sh, src.height - sy)
        if sw <= 0 or sh <= 0:
            return False
        crop = src.crop((sx, sy, sx + sw, sy + sh))
        if (dw, dh) != (sw, sh):
            crop = crop.resize((dw, dh))
        self._overlay().alpha_composite(crop, (dx, dy))
        return True

    def cmd_blt(self, a: Args) -> None:
        """blt dx,dy,dw,dh,sx,sy,sw,sh —— 把 btndef 图的一块贴到画面上。"""
        box = [a.read_int() for _ in range(8)]
        name = self.state.btndef_image
        if self._apply_blt(name, box):
            # 记流水：读档时按顺序重放，才能把 blt 的像素找回来
            self.state.bg_ops.append({"image": name, "box": box})

    def cmd_ofscopy(self, a: Args) -> None:
        """`ofscopy` / `ofscpy` —— 把**当前画面快照**进累积缓冲（引擎 `ofscopyCommand`：
        `SDL_RenderReadPixels` → `accumulation_surface`），后续 `blt` 从这里取像素。

        注意别被名字骗了：它跟"复制存档槽"没关系。`bgcopyCommand` 的第一句就是它 ——
        所以 `bgcopy` = 快照 + 把快照当新背景。我们的 `blt` 直接按图源（btndef / 文件）
        取像素、没有屏幕累积缓冲，因此这里是 no-op；"冻住画面"的效果由
        `bgcopy` 走的 `_bake_overlay()` 达成。
        """
        return

    def cmd_ofscpy(self, a: Args) -> None:
        """`ofscpy` —— `ofscopy` 的别名（引擎 LUT 里两个名字指向同一个 handler）。"""
        self.cmd_ofscopy(a)

    def _bake_overlay(self) -> None:
        """把背景 + overlay 合成成一张新背景（bgcopy 与读档重放共用）。"""
        from PIL import Image
        canvas = Image.new("RGBA", (self.renderer.width, self.renderer.height),
                           tuple(self.state.bg_color) + (255,))
        # 烘焙要真像素，这里把延迟背景解码出来（只发生一次，结果是新背景）
        bg = self.renderer.image_of(self.state.bg_image)
        if bg is not None:
            canvas.alpha_composite(bg.convert("RGBA"), (0, 0))
        if self.state.overlay is not None:
            canvas.alpha_composite(self.state.overlay, (0, 0))
        self.state.bg_image = canvas
        self.state.overlay = None

    def cmd_bgcopy(self, a: Args | None = None) -> None:
        """bgcopy = 把当前画面冻成背景（bg_info 换成快照）。

        典型用法：bg 新背景 → 一串 blt 做卷动 → bgcopy 定住结果。
        存档只记 `bg_source` + `bg_ops` + `bg_baked`，读档时重放，
        所以不需要把合成后的像素写进存档。
        """
        self._bake_overlay()
        self.state.bg_name = "*bgcpy"
        self.state.bg_baked = True

    def cmd_bgcpy(self, a: Args) -> None:
        """`bgcpy` 与 `bgcopy` 在引擎里是**同一个** `bgcopyCommand`，语义完全一样。

        之前的桩把它当未实现，其实是漏了别名：用到 `bgcpy` 的脚本会白丢一次快照。
        """
        self.cmd_bgcopy(a)

    def replay_overlay(self) -> None:
        """读档后按 `bg_ops` 重建 overlay；发生过 bgcopy 就把结果烘进背景。"""
        self.state.overlay = None
        for op in self.state.bg_ops:
            self._apply_blt(op.get("image", ""), op.get("box") or [])
        if self.state.bg_baked:
            self._bake_overlay()

    def cmd_repaint(self, a: Args) -> None:
        """我们按需求合成，没有脏矩形，直接忽略。"""
        return

    # ------------------------------------------------------------ 旧式选择肢按钮
    def cmd_cselbtn(self, a: Args) -> None:
        """cselbtn csel_no,btn_no,x,y —— 把第 N 个选项画成文字按钮。

        引擎用 sentence_font 现画一句可点文字；我们生成文字精灵 + 矩形按钮。
        """
        idx, btn_no = a.read_int(), a.read_int()
        x, y = a.read_int(), a.read_int()
        links = self.state.select_links
        if not (0 <= idx < len(links)):
            return
        text = links[idx].text
        cfg = self.state.window
        size = cfg.font_size_x or 26
        img = self.renderer.render_text_sprite(size, "#FFFFFF", text)
        sp = self.state.sprite(self._CSEL_SPRITE_BASE + idx)
        sp.tag, sp.kind, sp.text, sp.image = f":cselbtn;{text}", "text", text, img
        sp.x, sp.y, sp.visible = x, y, True
        self.state.ui_sprites.add(sp.id)
        w = img.width if img is not None else len(text) * size
        h = img.height if img is not None else size
        self._add_button(Button(no=btn_no, kind="rect", rect=(x, y, w, h),
                                label=links[idx].label))

    _CSEL_SPRITE_BASE = 5000

    def cmd_selectbtnwait(self, a: Args) -> None:
        self.cmd_btnwait(a)

    # ------------------------------------------------------------ 流程 / 杂项
    def cmd_reset(self, a: Args) -> None:
        """reset = 回标题（引擎会跳回 *start 并清全局变量）。"""
        st = self.state
        st.page = None
        st.sprites.clear()
        st.tachi.clear()
        st.buttons.clear()
        st.select_links.clear()
        st.overlay = None
        st.btndef_pixels = None
        st.btndef_image = ""
        st.text_window_erased = False
        st.bg_image = None
        st.bg_color = (0, 0, 0)
        st.bg_name = ""
        self.pending_pages.clear()
        self.stack.clear()
        self.for_stack.clear()
        self.page_name = ""
        idx = self.script.label_index("start")
        self.pc = idx if idx is not None else 0
        self.current_label = "start"
        self.text_hook_entered = False
        self.story_line, self.story_label = -1, ""

    def cmd_end(self, a: Args) -> None:
        self.finished = True

    def cmd_getcursorpos(self, a: Args) -> None:
        """getcursorpos %x,%y —— 文本框里下一个字符的落点（引擎 `FontInfo::x/y`）。

        引擎会在末尾换行时先 `newLine()` 再按 `indent_offset` 缩进；我们的排版
        在 `Renderer._update_text_cursor` 里用同一套断行结果算，所以"算出来的位置"
        和"画出来的位置"一致（`locate` 的格偏移也算进去了；`indent` 的缩进空格
        已经写进 page 文本，行宽因此自然一致）。
        """
        page = self.state.page
        x, y = self.renderer.text_cursor(self.state.window,
                                         page.lines if page else [],
                                         self.state.text_locate)
        for val in (x, y):
            t = a.peek()
            if t is None or t.kind != T_IVAR:
                return
            a.i += 1
            self.state.int_slots[self._slot_of(a, t)] = int(val)

    def cmd_getcursorpos2(self, a: Args) -> None:
        x, y = self.state.last_cursor
        for val in (x, y):
            t = a.peek()
            if t is None or t.kind != T_IVAR:
                return
            a.i += 1
            self.state.set_int(t.text, val)

    def cmd_systemcall(self, a: Args) -> None:
        """systemcall save/load/lookback/rmenu 都是叫出游戏内置菜单。

        那套 UI 走的是引擎自己的 menu 状态机，不是脚本能画出来的；agent 用
        MCP 的 save/load 更直接，所以这里只记一笔，不阻断脚本。
        """
        t = a.peek()
        what = (t.text if t is not None else "").strip().lower()
        get_logger("interp").debug("systemcall %s（不实现，跳过）", what)

    # ------------------------------------------------------------ 音频（只记账，不播放）
    # 引擎把这些状态写进存档（`saveSaveFile2` 里的 music_file_name / wave_file_name /
    # loop_bgm_name / cd_track 等），读档时按名字**重放**。
    # agent 听不到声音，所以这里不加载、不解码、不播放，只维护"当前在放什么"。
    # 引擎的两个反直觉点，这里照做：
    #   * `mp3`（不带 loop）的 mp3save_flag=false → 音乐名**不随存档恢复**
    #   * `dwave`（语音）根本不进存档、音量写的是 envdata，两者都只留在内存

    def _set_music(self, a: Args, *, loop: bool, save: bool) -> None:
        name = a.read_str()
        au = self.state.audio
        au.clear_music()
        au.music = name
        au.music_loop = loop
        au.mp3save = save

    def cmd_bgm(self, a: Args) -> None:
        self._set_music(a, loop=True, save=True)

    def cmd_bgmonce(self, a: Args) -> None:
        self._set_music(a, loop=False, save=False)

    def cmd_mp3(self, a: Args) -> None:
        self._set_music(a, loop=False, save=False)

    def cmd_mp3loop(self, a: Args) -> None:
        self._set_music(a, loop=True, save=True)

    def cmd_mp3save(self, a: Args) -> None:
        self._set_music(a, loop=False, save=True)

    def cmd_mp3stop(self, a: Args) -> None:
        self.state.audio.clear_music()

    cmd_bgmstop = cmd_mp3stop

    def cmd_wave(self, a: Args) -> None:
        au = self.state.audio
        au.wave = a.read_str()
        au.wave_loop = False

    def cmd_waveloop(self, a: Args) -> None:
        au = self.state.audio
        au.wave = a.read_str()
        au.wave_loop = True

    def cmd_wavestop(self, a: Args) -> None:
        self.state.audio.clear_wave()

    def cmd_stop(self, a: Args) -> None:
        """stop = mp3stop + wavestop（引擎 stopCommand 就是这么写的）。"""
        self.state.audio.clear_music()
        self.state.audio.clear_wave()

    def cmd_loopbgm(self, a: Args) -> None:
        self.state.audio.loop_bgm = [a.read_str(), a.read_str()]

    def cmd_loopbgmstop(self, a: Args) -> None:
        self.state.audio.loop_bgm = ["", ""]

    def cmd_play(self, a: Args) -> None:
        """play / playonce："*N" 是 CD 音轨，其余是 MIDI。"""
        name = a.read_str()
        au = self.state.audio
        if name.startswith("*"):
            try:
                au.cd_track = int(name[1:].strip() or 0)
            except ValueError:
                au.cd_track = 0
            au.cd_loop = True
        else:
            au.midi = name
            au.midi_loop = True

    def cmd_playonce(self, a: Args) -> None:
        name = a.read_str()
        au = self.state.audio
        if name.startswith("*"):
            try:
                au.cd_track = int(name[1:].strip() or 0)
            except ValueError:
                au.cd_track = 0
            au.cd_loop = False
        else:
            au.midi = name
            au.midi_loop = False

    def cmd_dwave(self, a: Args) -> None:
        """dwave 声道,文件 —— 语音。只记内存状态（引擎不把语音写进存档）。"""
        a.read_int()
        self.state.audio.voice = a.read_str()

    cmd_dwaveloop = cmd_dwave
    cmd_dwaveload = cmd_dwave
    cmd_dwaveplay = cmd_dwave
    cmd_dwaveplayloop = cmd_dwave

    def cmd_dwavestop(self, a: Args) -> None:
        self.state.audio.voice = ""

    def _set_volume(self, a: Args, key: str) -> None:
        self.state.audio.volume[key] = a.read_int()

    def cmd_bgmvol(self, a: Args) -> None:
        self._set_volume(a, "music")

    def cmd_mp3vol(self, a: Args) -> None:
        self._set_volume(a, "music")

    def cmd_sevol(self, a: Args) -> None:
        self._set_volume(a, "se")

    def cmd_voicevol(self, a: Args) -> None:
        self._set_volume(a, "voice")

    # ------------------------------------------------------------ 杂项
    def cmd_if(self, a: Args) -> None:  # pragma: no cover - 理论上不会走到
        return

    def cmd_notif(self, a: Args) -> None:  # pragma: no cover - 同上，见 _exec_if
        return

    def _log_unsupported(self, name: str) -> None:
        """记"根本不认识这条命令"。

        引擎里有、我们没做的命令不该走到这里——它们在 `stubs.py` 里有桩，
        记进的是 `stubbed`。这里只统计真·未知（通常是宏没被扫到、或脚本拼错）。
        """
        self.unsupported[name] = self.unsupported.get(name, 0) + 1
        if name not in self.unsupported_at:
            pc = min(max(self.pc - 1, 0), len(self.script.instrs) - 1)
            self.unsupported_at[name] = (self.script.instrs[pc].line_no
                                         if 0 <= pc < len(self.script.instrs) else -1)

    def _record(self, instr: Instr) -> None:
        cmd = instr.text.split()[0][:32] if instr.kind == K_STMT else ("<text>" if instr.kind == K_TEXT else "~")
        self.trace.append(TraceEntry(instr.line_no, instr.kind, cmd.lower(), instr.text, self.current_label))
        if len(self.trace) > self.trace_max:
            del self.trace[:len(self.trace) - self.trace_max]
