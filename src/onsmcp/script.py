"""NScripter / ONScripter 脚本解析：分词、参数读取、指令表。

设计对应引擎的 ScriptHandler：
  * 命令名与标签名在读取时就被折成小写（ScriptHandler.cpp:281/306），
    所以查表一律用 lower()。
  * "是不是文本行"由行首字符决定，不是靠命令白名单
    （ScriptHandler.cpp readTokenTop 的 text 分支）：
    行首为双字节字符 / 数字 / `" ` @ \\ / % ? $ [ ( < > ! # ,` 即文本行。
  * 一行内用 ':' 分隔多条语句；`if` 的条件成立时吞掉本行剩余部分。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- 词法

T_STR, T_NUM, T_IVAR, T_SVAR, T_LABEL, T_IDENT, T_OP, T_COMMA, T_AVAR = range(9)

OP_CHARS = set("+-*/%=<>!&|")


@dataclass
class Tok:
    kind: int
    text: str
    pos: int = 0

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.kind}:{self.text}>"


def split_statements(line: str) -> list[str]:
    """按顶层 ':' 切语句，忽略引号内的 ':'。"""
    out, buf, in_str = [], [], False
    for ch in line:
        if ch == '"':
            in_str = not in_str
            buf.append(ch)
        elif ch == ":" and not in_str:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def strip_comment(line: str) -> str:
    """去掉引号外的 ';' 注释。"""
    in_str = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_str = not in_str
        elif ch == ";" and not in_str:
            return line[:i]
    return line


def is_text_line(s: str) -> bool:
    if not s:
        return False
    c = s[0]
    if ord(c) >= 0x80:
        return True
    return c.isdigit() or c in '"`@\\/%?$[(<>!#,'


def tokenize(s: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in " \t\r":
            i += 1
            continue
        if ch == '"':
            j = s.find('"', i + 1)
            if j < 0:
                toks.append(Tok(T_STR, s[i + 1:]))
                break
            toks.append(Tok(T_STR, s[i + 1:j], i))
            i = j + 1
            continue
        if ch == ",":
            toks.append(Tok(T_COMMA, ",", i))
            i += 1
            continue
        if ch in "()":
            # 括号只出现在表达式里（行首的 '(' 是文本行标志，走不到这里）。
            # 引擎 readNextOp 遇到 '(' 会递归 parseIntExpression。
            toks.append(Tok(T_OP, ch, i))
            i += 1
            continue
        if ch == "?":
            # 数组变量 `?name[e1][e2]`（引擎 parseInt 的 VAR_ARRAY 分支）。
            # 名字可以是数字（Ever17 就是 `dim ?0[100]`），下标是完整表达式，
            # 所以整段留成原文，取值时再交给 Args 递归求值。
            m = re.match(r"([A-Za-z0-9_]+)((?:\[[^\[\]]*\])+)", s[i + 1:])
            if m:
                toks.append(Tok(T_AVAR, m.group(1).lower() + m.group(2), i))
                i += 1 + len(m.group(0))
                continue
            toks.append(Tok(T_STR, ch, i))
            i += 1
            continue
        if ch in "%$":
            # `%?a[i]` 是"拿数组元素的值当槽号"（引擎 parseInt 递归到 VAR_ARRAY，
            # 再 getVariableData(那个值)）。Ever17 用它做十进制拆位：mov %?0[1],%0
            if ch == "%" and s[i + 1:i + 2] == "?":
                m = re.match(r"\?([A-Za-z0-9_]+)((?:\[[^\[\]]*\])+)", s[i + 1:])
                if m:
                    toks.append(Tok(T_IVAR, "?" + m.group(1).lower() + m.group(2), i))
                    i += 1 + len(m.group(0))
                    continue
            # 变量名可以是数字：NScripter 里 %0…%N 是最常用的数值变量
            # （Ever17 大量用 %1 / %101），$0 / $1 同理。
            m = re.match(r"[A-Za-z0-9_]+", s[i + 1:])
            if m and m.group(0):
                name = m.group(0).lower()
                toks.append(Tok(T_IVAR if ch == "%" else T_SVAR, name, i))
                i += 1 + len(m.group(0))
                continue
            toks.append(Tok(T_OP, ch, i))
            i += 1
            continue
        if ch == "*":
            # '*' 既是标签前缀（goto *foo）又是乘号：后面跟标识符才算标签
            m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[i + 1:])
            if m and m.group(0):
                toks.append(Tok(T_LABEL, m.group(0).lower(), i))
                i += 1 + len(m.group(0))
            else:
                toks.append(Tok(T_OP, "*", i))
                i += 1
            continue
        if ch.isdigit():
            m = re.match(r"\d+", s[i:])
            toks.append(Tok(T_NUM, m.group(0), i))
            i += len(m.group(0))
            continue
        if ch.isalpha() or ch == "_":
            m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[i:])
            toks.append(Tok(T_IDENT, m.group(0).lower(), i))
            i += len(m.group(0))
            continue
        if ch == "#":
            # 颜色常量 #RRGGBB 要当一个整体，否则会被拆成 '#' + 一堆字母
            m = re.match(r"#[0-9A-Fa-f]{6}", s[i:])
            if m:
                toks.append(Tok(T_STR, m.group(0), i))
                i += 7
                continue
            toks.append(Tok(T_STR, ch, i))
            i += 1
            continue
        if ch in OP_CHARS:
            two = s[i:i + 2]
            if two in ("==", "!=", "<=", ">=", "&&", "||"):
                toks.append(Tok(T_OP, two, i))
                i += 2
            else:
                toks.append(Tok(T_OP, ch, i))
                i += 1
            continue
        # 其他字符（全角标点等）当字符串字面量吃进去
        toks.append(Tok(T_STR, ch, i))
        i += 1
    return toks


class Args:
    """按引擎 readInt()/readStr()/readLabel() 的习惯顺序消费参数。

    `variables` / `strings` 只要提供 `.get(名字, 默认值)` 即可——
    解释器传进来的是按槽位解析的只读视图（见 `state.SlotView`），
    单元测试里可以直接传普通 dict。

    `str_aliases` 是 `stralias` 定义的字符串常量表：引擎里裸名字出现在
    字符串表达式里时会查它，查不到才原样输出。

    `aliases` 是 `numalias` 的名字→槽号表，**裸名字出现在数值表达式里时返回的是槽号本身**
    （引擎 `parseInt`：`ret = alias_no; type = VAR_INT|VAR_CONST`）。
    所以脚本把 `numalias save_num,5` 当"具名常量"用：
    `for %sub1=0 to save_num` 的终点是 5，不是 5 号槽的值。

    `arrays` 是数组表（`state.State` 本身即可），提供
    `get_array(名字, 下标列表) -> int` / `set_array(...) -> bool`；
    为 `None` 时 `?数组` 一律读作 0（单测里不需要数组时可以不传）。
    """

    def __init__(self, toks: list[Tok], variables: dict, strings: dict,
                 str_aliases: dict | None = None,
                 aliases: dict | None = None,
                 arrays=None):
        self.toks = toks
        self.i = 0
        self.variables = variables
        self.strings = strings
        self.str_aliases = str_aliases or {}
        self.aliases = aliases or {}
        self.arrays = arrays

    # -- 基础 -------------------------------------------------
    def _skip_comma(self) -> None:
        while self.i < len(self.toks) and self.toks[self.i].kind == T_COMMA:
            self.i += 1

    def eof(self) -> bool:
        self._skip_comma()
        return self.i >= len(self.toks)

    def peek(self) -> Tok | None:
        self._skip_comma()
        return self.toks[self.i] if self.i < len(self.toks) else None

    def rest_text(self) -> str:
        """把剩余 token 还原成文本（给 if 的 tail 用）。"""
        parts = []
        for t in self.toks[self.i:]:
            parts.append(t.text)
        self.i = len(self.toks)
        return " ".join(parts)

    # -- 数值表达式 -------------------------------------------
    def read_int(self) -> int:
        try:
            return self._expr()
        except Exception:
            return 0

    def _expr(self) -> int:
        self._skip_comma()
        val = self._term()
        while True:
            t = self.peek()
            if t and t.kind == T_OP and t.text in "+-":
                self.i += 1
                rhs = self._term()
                val = val + rhs if t.text == "+" else val - rhs
            else:
                return val

    def _term(self) -> int:
        val = self._factor()
        while True:
            t = self.peek()
            op = ""
            if t and t.kind == T_OP and t.text in "*/%":
                op = t.text
            elif t and t.kind == T_IDENT and t.text == "mod":
                # 引擎 readNextOp 把 "mod" 当乘除同级运算符（后跟空格/tab/结束符）
                op = "mod"
            if not op:
                return val
            self.i += 1
            rhs = self._factor()
            if op == "*":
                val *= rhs
            elif op == "/":
                val = int(val / rhs) if rhs else 0
            else:
                val = val % rhs if rhs else 0

    def _factor(self) -> int:
        self._skip_comma()
        if self.i >= len(self.toks):
            return 0
        t = self.toks[self.i]
        if t.kind == T_OP and t.text == "-":
            self.i += 1
            return -self._factor()
        if t.kind == T_OP and t.text == "(":
            # 引擎 parseIntExpression 遇到 '(' 递归求值
            self.i += 1
            val = self._expr()
            if (self.i < len(self.toks) and self.toks[self.i].kind == T_OP
                    and self.toks[self.i].text == ")"):
                self.i += 1
            return val
        if t.kind == T_STR:
            # 引擎 parseInt 遇到引号串：前缀扫描长度为 0 → VAR_NONE 且**指针不动**。
            # 所以 `mov %a,"123"` 的值是 0（不是 123），而且后面还能把它当字符串读出来。
            return 0
        if t.kind == T_IDENT and t.text not in self.aliases:
            # 引擎 parseInt 未命中别名：`*buf = buf_start` 把指针退回名字开头，
            # 于是同一条命令的下一个参数会把这个名字当字符串/标签再读一次。
            # 我们同样不消费 —— 注意这要求调用方的循环按逗号收尾，不能只看 eof。
            note = getattr(self.arrays, "note_undefined", None)
            if note is not None:
                note(t.text)
            return 0

        self.i += 1
        if t.kind == T_NUM:
            return int(t.text)
        if t.kind == T_IVAR:
            if t.text.startswith("?"):
                # %?a[i]：先取数组元素值，再把它当槽号
                return int(self.variables.get(str(self.array_get(t.text[1:])), 0))
            return int(self.variables.get(t.text, 0))
        if t.kind == T_SVAR:
            try:
                return int(self.strings.get(t.text, "0") or 0)
            except ValueError:
                return 0
        if t.kind == T_IDENT:
            # 裸名字 = 别名槽号（具名常量，引擎 VAR_INT|VAR_CONST）
            return int(self.aliases.get(t.text, 0))
        if t.kind == T_AVAR:
            return self.array_get(t.text)
        return 0

    # -- 数组（dim） -------------------------------------------
    def array_spec(self, text: str) -> tuple[str, list[int]]:
        """`a[%i+1][2]` → ("a", [下标值...])。下标用完整整数表达式求值。"""
        m = re.match(r"([A-Za-z0-9_]+)(.*)$", text or "", re.S)
        if not m:
            return "", []
        name, rest = m.group(1).lower(), m.group(2)
        idxs = []
        for expr in re.findall(r"\[([^\[\]]*)\]", rest):
            sub = Args(tokenize(expr), self.variables, self.strings,
                       self.str_aliases, self.aliases, self.arrays)
            idxs.append(sub.read_int())
        return name, idxs

    def array_get(self, text: str, offset: int = 0) -> int:
        """读 `?name[i]` 的元素；未声明/越界给 0（引擎在这种情况下会直接退出）。"""
        if self.arrays is None:
            return 0
        name, idxs = self.array_spec(text)
        if not name or not idxs:
            return 0
        return self.arrays.get_array(name, idxs, offset)

    def array_set(self, text: str, value: int, offset: int = 0) -> bool:
        if self.arrays is None:
            return False
        name, idxs = self.array_spec(text)
        if not name or not idxs:
            return False
        return self.arrays.set_array(name, idxs, value, offset)

    def _substitute(self, text: str) -> str:
        """引号串里的 %var / $var 也要替换——移植脚本大量用 ":s/30,30,1;#88FFFF$name"。"""
        if "%" not in text and "$" not in text:
            return text
        out = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "%" and text[i + 1:i + 2] == "?":
                # %?a[i]：数组元素的值当槽号（Ever17 的十进制拆位写法）
                m = re.match(r"\?([A-Za-z0-9_]+)((?:\[[^\[\]]*\])+)", text[i + 1:])
                if m:
                    slot = self.array_get(m.group(1).lower() + m.group(2))
                    out.append(str(self.variables.get(str(slot), 0)))
                    i += 1 + len(m.group(0))
                    continue
            if ch in "%$":
                m = re.match(r"[A-Za-z0-9_]+", text[i + 1:])
                if m:
                    name = m.group(0).lower()
                    out.append(str(self.variables.get(name, 0)) if ch == "%"
                               else str(self.strings.get(name, "")))
                    i += 1 + len(m.group(0))
                    continue
            out.append(ch)
            i += 1
        return "".join(out)

    # -- 字符串表达式（支持 ""+$var+".png" 拼接） ----------------
    def read_str(self) -> str:
        out = []
        while True:
            self._skip_comma()
            if self.i >= len(self.toks):
                break
            t = self.toks[self.i]
            if t.kind == T_STR:
                out.append(self._substitute(t.text))
                self.i += 1
            elif t.kind == T_IDENT:
                out.append(self.str_aliases.get(t.text, t.text))
                self.i += 1
            elif t.kind == T_NUM:
                out.append(t.text)
                self.i += 1
            elif t.kind == T_SVAR:
                out.append(str(self.strings.get(t.text, "")))
                self.i += 1
            elif t.kind == T_IVAR:
                if t.text.startswith("?"):
                    slot = self.array_get(t.text[1:])
                    out.append(str(self.variables.get(str(slot), 0)))
                else:
                    out.append(str(self.variables.get(t.text, 0)))
                self.i += 1
            elif t.kind == T_AVAR:
                # 引擎 parseStr 没有数组分支：`?a[1]` 在普通字符串参数里就是原样字符
                out.append("?" + t.text)
                self.i += 1
            elif t.kind == T_LABEL:
                out.append(t.text)
                self.i += 1
            else:
                break
            # 只有 '+' 才继续拼，逗号代表下一个参数
            if self.i < len(self.toks):
                nxt = self.toks[self.i]
                if nxt.kind == T_OP and nxt.text == "+":
                    self.i += 1
                    continue
            break
        return "".join(out)

    def read_label(self) -> str:
        self._skip_comma()
        if self.i >= len(self.toks):
            return ""
        t = self.toks[self.i]
        if t.kind == T_LABEL:
            self.i += 1
            return t.text
        if t.kind == T_SVAR:
            self.i += 1
            return str(self.strings.get(t.text, ""))
        if t.kind == T_IDENT:
            self.i += 1
            return t.text
        self.i += 1
        return t.text

    def remaining(self) -> list[Tok]:
        return self.toks[self.i:]


# ---------------------------------------------------------------- 指令表

K_TEXT, K_STMT, K_TILDE = "text", "stmt", "tilde"


@dataclass
class Instr:
    line_no: int          # 1-based 源码行号
    text: str             # 原始语句（文本行则是原始文本）
    kind: str = K_STMT
    label: str | None = None   # 该行若有标签


@dataclass
class Script:
    lines: list[str]
    instrs: list[Instr] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    label_of: list[str] = field(default_factory=list)   # 每条指令所属标签
    text_count: int = 0

    @classmethod
    def load(cls, path: str, encoding: str = "gbk") -> "Script":
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode(encoding, errors="replace")
        if text.startswith("\ufeff"):
            text = text[1:]
        return cls.from_text(text)

    @classmethod
    def from_text(cls, text: str) -> "Script":
        lines = text.split("\n")
        sc = cls(lines=lines)
        cur_label = ""
        for idx, raw in enumerate(lines):
            ln = idx + 1
            s = raw.strip()
            if not s:
                continue
            if s[0] == "*":
                # '*label;说明' —— 引擎的 token 在 ';' 处断开
                name = s[1:].split(";")[0].strip().lower()
                if name and name not in sc.labels:
                    sc.labels[name] = len(sc.instrs)
                cur_label = name or cur_label
                continue
            if s[0] == ";":
                continue
            if s[0] == "~":
                sc.instrs.append(Instr(ln, "~", K_TILDE))
                sc.label_of.append(cur_label)
                continue
            if is_text_line(s):
                sc.instrs.append(Instr(ln, raw.strip(), K_TEXT))
                sc.label_of.append(cur_label)
                sc.text_count += 1
                continue
            body = strip_comment(s).strip()
            if body:
                sc.instrs.append(Instr(ln, body, K_STMT))
                sc.label_of.append(cur_label)
        return sc

    def label_index(self, name: str) -> int | None:
        return self.labels.get(name.lstrip("*").lower())

    def index_of_line(self, line_no: int) -> int:
        """第一个行号 `>= line_no` 的指令下标；没有就是 `len(instrs)`（= 脚本结束）。

        `skip` 用：引擎 `getAddressByLine(line)` 取到该行起始地址后从那里读 token，
        空行/注释/标签行会被读 token 的过程自然跳过，
        所以等价于"从这一行起的第一条可执行指令"。
        """
        lo, hi = 0, len(self.instrs)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.instrs[mid].line_no < line_no:
                lo = mid + 1
            else:
                hi = mid
        return lo
