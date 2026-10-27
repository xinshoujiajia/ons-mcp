"""ONS 二进制存档（`save<N>.dat`）的读写。

格式依据 `ONScripter_file2.cpp` 的 `saveSaveFile2` / `loadSaveFile2`，
序列化原语依据 `ScriptParser::writeInt / writeStr / writeChar`：

* `writeInt` —— 4 字节小端
* `writeStr` —— 原样字节（脚本编码，这里是 GBK）+ 一个 NUL；空串也只写 NUL
* `writeChar` —— 1 字节

文件布局（2.8）：

```
"ONS" 02 08
字体/窗口/cursor/bg/立绘
1000 个 sprite 槽
变量 0..global_border-1（每槽 int + str）
nest 栈（label 是偏移，for 是 4 个 int）
monocro / 音频
100 个 bar、100 个 prnum
btndef
数组（裸 int，**没有维度信息**）
loopbgm / ruby
256 个 sprite2
...
页面文本、页面 tag
行号 + 行内语句偏移
```

**两个必须知道的事实**：

1. 数组段在存档里没有维度信息，读的时候必须靠脚本的 `dim` 声明推算元素总数
   （引擎自己也是这么做的：`writeArrayVariable` 只写 `prod(av->dim[i])` 个 int）。
2. 续跑点是 `(绝对行号, 裸冒号计数)`，不是"第几条语句"：
   `writeInt(current_label_info.start_line + current_line)`，然后从该行行首数到
   当前读取位置之间有多少个 `':'`（**引号内的冒号也算**），文本行时直接写 0。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"ONS"
VERSION_MAJOR = 2
VERSION_MINOR = 8
MAX_SPRITE_NUM = 1000
MAX_SPRITE2_NUM = 256
MAX_PARAM_NUM = 100
MAX_PAGE_LIST = 16        # ScriptParser.cpp 的 MAX_PAGE_LIST


class EngineSaveError(Exception):
    """二进制存档不合法 / 版本不支持。"""


# ---------------------------------------------------------------- 槽位结构
@dataclass
class SpriteSlot:
    """`AnimationInfo` 会被存进存档的那几个字段。"""

    image_name: str = ""
    x: int = 0
    y: int = 0
    visible: int = 0
    current_cell: int = 0
    trans: int = -1          # 引擎 reset() 的默认值


@dataclass
class Sprite2Slot:
    image_name: str = ""
    x: int = 0
    y: int = 0
    scale_x: int = 0
    scale_y: int = 0
    rot: int = 0
    visible: int = 0
    trans: int = -1
    blending_mode: int = 0


@dataclass
class BarSlot:
    used: bool = False
    param: int = 0
    x: int = 0
    y: int = 0
    max_width: int = 0
    h: int = 0
    max_param: int = 0
    color: tuple[int, int, int] = (255, 255, 255)


@dataclass
class PrnumSlot:
    used: bool = False
    param: int = 0
    x: int = 0
    y: int = 0
    font_size_x: int = 0
    font_size_y: int = 0
    color: tuple[int, int, int] = (255, 255, 255)


@dataclass
class NestEntry:
    """nest 栈的一项。`label` 类型存脚本偏移；`for` 类型存 4 个 int。"""

    kind: str = "label"               # label | for
    offset: int = 0                   # label: getOffset(next_script)；for: -offset
    var_no: int = 0
    to: int = 0
    step: int = 0

    @property
    def cost(self) -> int:
        """占几个 int（num_nest 是按 int 计数，不是按项）。"""
        return 1 if self.kind == "label" else 4


@dataclass
class EngineSave:
    """一份完整的 ONS 二进制存档。

    字段名尽量贴引擎源码，方便逐行对照 `saveSaveFile2`。
    """

    version: tuple[int, int] = (VERSION_MAJOR, VERSION_MINOR)

    # 字体 / 窗口
    is_bold: int = 0
    is_shadow: int = 0
    rmode: int = 0
    color: tuple[int, int, int] = (0, 0, 0)
    cursor: tuple[str, str] = ("", "")
    window_effect: tuple[int, int] = (0, 0)
    window_anim: str = ""
    top_xy: tuple[int, int] = (0, 0)
    num_xy: tuple[int, int] = (0, 0)
    font_size: tuple[int, int] = (0, 0)
    pitch: tuple[int, int] = (0, 0)
    window_color: tuple[int, int, int] = (0, 0, 0)
    is_transparent: int = 0
    wait_time: int = 0
    font_info: tuple[int, int, int, int] = (0, 0, 0, 0)
    font_info_image: str = ""
    cursor_abs: tuple[int, int] = (1, 1)
    cursor_pos: tuple[int, int, int, int] = (0, 0, 0, 0)

    # 画面
    bg: str = ""
    tachi: tuple[str, str, str] = ("", "", "")
    tachi_x: tuple[int, int, int] = (0, 0, 0)
    tachi_y: tuple[int, int, int] = (0, 0, 0)
    sprites: list[SpriteSlot] = field(default_factory=list)   # 正好 1000

    # 变量：槽号 → (int, str)；只保存 0..border-1
    variables: dict[int, tuple[int, str]] = field(default_factory=dict)
    border: int = 0

    nest: list[NestEntry] = field(default_factory=list)

    # 滤镜 / 音频
    monocro: bool = False
    monocro_color: tuple[int, int, int] = (0, 0, 0)
    nega_mode: int = 0
    midi: str = ""
    wave: str = ""
    cd_track: int = -1
    midi_loop: int = 0
    wave_loop: int = 0
    cd_loop: int = 0
    music_loop: int = 0
    mp3save: int = 0
    music: str = ""
    erase_window: tuple[int, int] = (0, 0)

    bars: list[BarSlot] = field(default_factory=list)          # 正好 100
    prnums: list[PrnumSlot] = field(default_factory=list)      # 正好 100
    btndef: str = ""

    arrays: list[list[int]] = field(default_factory=list)      # 每个数组的裸 int

    erase_char: int = 0
    loop_bgm: tuple[str, str] = ("", "")
    rubyon: int = 0
    ruby_font_size: tuple[int, int] = (0, 0)
    ruby_font: str = ""
    sprites2: list[Sprite2Slot] = field(default_factory=list)   # 正好 256

    screen_width: int = 640
    underline: int = 0

    pages: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    cur_line: int = 0
    cur_stmt: int = 0


# ---------------------------------------------------------------- 读取
class _Reader:
    def __init__(self, data: bytes, encoding: str = "gbk"):
        self.d = data
        self.p = 0
        self.enc = encoding

    def need(self, n: int) -> None:
        if self.p + n > len(self.d):
            raise EngineSaveError(f"存档提前结束：偏移 {self.p} 之后不足 {n} 字节")

    def int(self) -> int:
        self.need(4)
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def char(self) -> int:
        self.need(1)
        v = self.d[self.p]
        self.p += 1
        return v

    def str(self) -> str:
        end = self.d.find(b"\x00", self.p)
        if end < 0:
            raise EngineSaveError(f"偏移 {self.p} 处的字符串没有 NUL 结尾")
        raw = self.d[self.p:end]
        self.p = end + 1
        return raw.decode(self.enc, "replace")

    def skip_str(self) -> None:
        end = self.d.find(b"\x00", self.p)
        if end < 0:
            raise EngineSaveError(f"偏移 {self.p} 处的字符串没有 NUL 结尾")
        self.p = end + 1


def parse(data: bytes, *, border: int, arrays: list[int],
          encoding: str = "gbk", trace: list | None = None) -> EngineSave:
    """把 `save<N>.dat` 解成 `EngineSave`。

    `border` 是脚本的 `global_variable_border`（变量段长度），
    `arrays` 是每个 `dim` 声明的**元素数**（`声明值 + 1`）——存档里没有这两项，
    缺了就无法定位后面所有字段。
    """
    r = _Reader(data, encoding)
    marks: list = trace if trace is not None else []

    def mark(name: str) -> None:
        marks.append((name, r.p))

    r.need(5)
    if data[:3] != MAGIC:
        raise EngineSaveError(f"不是 ONS 存档：头部 {data[:3]!r}")
    r.p = 3
    major, minor = r.char(), r.char()
    if (major, minor) != (VERSION_MAJOR, VERSION_MINOR):
        raise EngineSaveError(
            f"存档版本 {major}.{minor} 与当前实现（{VERSION_MAJOR}.{VERSION_MINOR}）不同")

    s = EngineSave(version=(major, minor), border=border)

    r.int()                                    # 版本 208 的标记（固定 2）
    s.is_bold = r.int()
    s.is_shadow = r.int()
    r.int()                                    # 固定 0
    s.rmode = r.int()
    s.color = (r.int(), r.int(), r.int())
    s.cursor = (r.str(), r.str())
    s.window_effect = (r.int(), r.int())
    s.window_anim = r.str()
    s.top_xy = (r.int(), r.int())
    s.num_xy = (r.int(), r.int())
    s.font_size = (r.int(), r.int())
    s.pitch = (r.int(), r.int())
    s.window_color = (r.char(), r.char(), r.char())     # 引擎倒序写：color[2],[1],[0]
    s.is_transparent = r.char()
    s.wait_time = r.int()
    s.font_info = (r.int(), r.int(), r.int(), r.int())
    s.font_info_image = r.str()
    s.cursor_abs = (r.int(), r.int())
    s.cursor_pos = (r.int(), r.int(), r.int(), r.int())

    s.bg = r.str()
    s.tachi = (r.str(), r.str(), r.str())
    s.tachi_x = (r.int(), r.int(), r.int())
    s.tachi_y = (r.int(), r.int(), r.int())
    for _ in range(3):
        r.int()
    for _ in range(3):
        r.int()

    mark("before_sprites")
    s.sprites = [SpriteSlot() for _ in range(MAX_SPRITE_NUM)]
    for i in range(MAX_SPRITE_NUM):
        sp = s.sprites[i]
        sp.image_name = r.str()
        sp.x = r.int()
        sp.y = r.int()
        sp.visible = r.int()
        sp.current_cell = r.int()
        sp.trans = r.int()

    mark("before_vars")
    for slot in range(border):
        num = r.int()
        text = r.str()
        if num or text:
            s.variables[slot] = (num, text)

    mark("before_nest")
    total = r.int()
    used = 0
    while used < total:
        v = r.int()
        if v > 0:
            s.nest.append(NestEntry(kind="label", offset=v))
            used += 1
        else:
            var_no = v
            to = r.int()
            step = r.int()
            neg = r.int()
            s.nest.append(NestEntry(kind="for", offset=neg, var_no=var_no,
                                    to=to, step=step))
            used += 4

    mark("before_monocro")
    s.monocro = bool(r.int())
    s.monocro_color = (r.int(), r.int(), r.int())
    s.nega_mode = r.int()

    s.midi = r.str()
    s.wave = r.str()
    cd = r.int()
    s.cd_track = cd if cd >= 0 else -1
    s.midi_loop = r.int()
    s.wave_loop = r.int()
    s.cd_loop = r.int()
    s.music_loop = r.int()
    s.mp3save = r.int()
    s.music = r.str()
    s.erase_window = (r.int(), r.int())

    mark("before_bars")
    s.bars = []
    for _ in range(MAX_PARAM_NUM):
        b = BarSlot()
        b.param = r.int()
        if b.param != 0:
            b.used = True
            b.x = r.int()
            b.y = r.int()
            b.max_width = r.int()
            b.h = r.int()
            b.max_param = r.int()
            b.color = (r.char(), r.char(), r.char())
            r.char()                            # 结尾 0
        else:
            r.int()                             # 空槽固定 -1
            for _ in range(5):
                r.int()
        s.bars.append(b)

    mark("before_prnums")
    s.prnums = []
    for _ in range(MAX_PARAM_NUM):
        p = PrnumSlot()
        p.param = r.int()
        if p.param != 0:
            p.used = True
            p.x = r.int()
            p.y = r.int()
            p.font_size_x = r.int()
            p.font_size_y = r.int()
            p.color = (r.char(), r.char(), r.char())
            r.char()
        else:
            r.int()
            for _ in range(4):
                r.int()
        s.prnums.append(p)

    mark("before_btndef")
    for _ in range(3):
        r.int()                                 # 1, 0, 1
    s.btndef = r.str()

    mark("before_arrays")
    for n in arrays:
        s.arrays.append([r.int() for _ in range(n)])

    r.int()                                     # 固定 0
    s.erase_char = r.char()
    r.char()
    r.char()
    r.char()
    s.loop_bgm = (r.str(), r.str())
    s.rubyon = r.int()
    s.ruby_font_size = (r.int(), r.int())
    s.ruby_font = r.str()
    r.int()                                     # 固定 0

    mark("before_sprite2")
    s.sprites2 = []
    for _ in range(MAX_SPRITE2_NUM):
        s2 = Sprite2Slot()
        s2.image_name = r.str()
        s2.x = r.int()
        s2.y = r.int()
        s2.scale_x = r.int()
        s2.scale_y = r.int()
        s2.rot = r.int()
        s2.visible = r.int()
        s2.trans = r.int()
        s2.blending_mode = r.int()
        s.sprites2.append(s2)

    mark("before_tail7")
    for _ in range(7):
        r.int()
    r.char()
    # 5 个 int：0, w/4, w/2, 3w/4, underline（207/208 版本加的）
    for i in range(5):
        v = r.int()
        if i == 3 and v:
            # 3w/4 —— 反推屏幕宽度，写回时要用
            s.screen_width = v * 4 // 3
        if i == 4:
            s.underline = v

    mark("before_pages")
    count = r.int()
    s.pages = [r.str() for _ in range(max(count, 0))]
    count = r.int()
    s.tags = [r.str() for _ in range(max(count, 0))]
    s.cur_line = r.int()
    s.cur_stmt = r.int()
    mark("end")
    if r.p != len(data):
        raise EngineSaveError(f"解析完还剩 {len(data) - r.p} 字节（疑似字段错位）")
    return s


# ---------------------------------------------------------------- 写入
class _Writer:
    def __init__(self, encoding: str = "gbk"):
        self.buf = bytearray()
        self.enc = encoding

    def int(self, v: int) -> None:
        self.buf += struct.pack("<i", int(v))

    def char(self, v: int) -> None:
        self.buf.append(int(v) & 0xFF)

    def str(self, s: str) -> None:
        if s:
            self.buf += s.encode(self.enc, "replace")
        self.buf.append(0)


def build(s: EngineSave, encoding: str = "gbk") -> bytes:
    """把 `EngineSave` 写回 `save<N>.dat` 的字节。"""
    w = _Writer(encoding)
    w.buf += MAGIC
    w.char(s.version[0])
    w.char(s.version[1])

    w.int(2)                                   # 版本 208 的标记
    w.int(s.is_bold)
    w.int(s.is_shadow)
    w.int(0)
    w.int(s.rmode)
    for c in s.color:
        w.int(c)
    w.str(s.cursor[0])
    w.str(s.cursor[1])
    w.int(s.window_effect[0])
    w.int(s.window_effect[1])
    w.str(s.window_anim)
    w.int(s.top_xy[0])
    w.int(s.top_xy[1])
    w.int(s.num_xy[0])
    w.int(s.num_xy[1])
    w.int(s.font_size[0])
    w.int(s.font_size[1])
    w.int(s.pitch[0])
    w.int(s.pitch[1])
    w.char(s.window_color[2])                  # 引擎倒序写
    w.char(s.window_color[1])
    w.char(s.window_color[0])
    w.char(s.is_transparent)
    w.int(s.wait_time)
    for v in s.font_info:
        w.int(v)
    w.str(s.font_info_image)
    w.int(s.cursor_abs[0])
    w.int(s.cursor_abs[1])
    for v in s.cursor_pos:
        w.int(v)

    w.str(s.bg)
    for t in s.tachi:
        w.str(t)
    for v in s.tachi_x:
        w.int(v)
    for v in s.tachi_y:
        w.int(v)
    for _ in range(3):
        w.int(0)
    for _ in range(3):
        w.int(-1)

    slots = list(s.sprites) + [SpriteSlot() for _ in range(MAX_SPRITE_NUM)]
    for sp in slots[:MAX_SPRITE_NUM]:
        w.str(sp.image_name)
        w.int(sp.x)
        w.int(sp.y)
        w.int(sp.visible)
        w.int(sp.current_cell)
        w.int(sp.trans)

    border = s.border or (max(s.variables) + 1 if s.variables else 0)
    for slot in range(border):
        num, text = s.variables.get(slot, (0, ""))
        w.int(num)
        w.str(text)

    w.int(sum(e.cost for e in s.nest))
    for e in s.nest:
        if e.kind == "label":
            w.int(e.offset)
        else:
            w.int(e.var_no)
            w.int(e.to)
            w.int(e.step)
            w.int(e.offset)

    w.int(1 if s.monocro else 0)
    for c in s.monocro_color:
        w.int(c)
    w.int(s.nega_mode)

    w.str(s.midi)
    w.str(s.wave)
    w.int(s.cd_track if s.cd_track >= 0 else -1)
    w.int(s.midi_loop)
    w.int(s.wave_loop)
    w.int(s.cd_loop)
    w.int(s.music_loop)
    w.int(s.mp3save)
    w.str(s.music if s.mp3save else "")
    w.int(s.erase_window[0])
    w.int(s.erase_window[1])

    bars = list(s.bars) + [BarSlot() for _ in range(MAX_PARAM_NUM)]
    for b in bars[:MAX_PARAM_NUM]:
        if b.used:
            w.int(b.param)
            w.int(b.x)
            w.int(b.y)
            w.int(b.max_width)
            w.int(b.h)
            w.int(b.max_param)
            w.char(b.color[2])
            w.char(b.color[1])
            w.char(b.color[0])
            w.char(0)
        else:
            w.int(0)
            w.int(-1)
            for _ in range(5):
                w.int(0)

    prnums = list(s.prnums) + [PrnumSlot() for _ in range(MAX_PARAM_NUM)]
    for p in prnums[:MAX_PARAM_NUM]:
        if p.used:
            w.int(p.param)
            w.int(p.x)
            w.int(p.y)
            w.int(p.font_size_x)
            w.int(p.font_size_y)
            w.char(p.color[2])
            w.char(p.color[1])
            w.char(p.color[0])
            w.char(0)
        else:
            w.int(0)
            w.int(-1)
            for _ in range(4):
                w.int(0)

    w.int(1)
    w.int(0)
    w.int(1)
    w.str(s.btndef)

    for arr in s.arrays:
        for v in arr:
            w.int(v)

    w.int(0)
    w.char(s.erase_char)
    w.char(0)
    w.char(0)
    w.char(0)
    w.str(s.loop_bgm[0])
    w.str(s.loop_bgm[1])
    w.int(s.rubyon)
    w.int(s.ruby_font_size[0])
    w.int(s.ruby_font_size[1])
    w.str(s.ruby_font)
    w.int(0)

    slots2 = list(s.sprites2) + [Sprite2Slot() for _ in range(MAX_SPRITE2_NUM)]
    for s2 in slots2[:MAX_SPRITE2_NUM]:
        w.str(s2.image_name)
        w.int(s2.x)
        w.int(s2.y)
        w.int(s2.scale_x)
        w.int(s2.scale_y)
        w.int(s2.rot)
        w.int(s2.visible)
        w.int(s2.trans)
        w.int(s2.blending_mode)

    # 固定 7 个 int（第 3 个是 1，205 版本加的标记）+ 1 个 char
    for v in (0, 0, 1, 0, 0, 0, 0):
        w.int(v)
    w.char(0)
    w.int(0)
    w.int(s.screen_width // 4)
    w.int(s.screen_width // 2)
    w.int(s.screen_width * 3 // 4)
    w.int(s.underline)

    w.int(len(s.pages))
    for text in s.pages:
        w.buf += text.encode(encoding, "replace")
        w.char(0)
    w.int(len(s.tags))
    for tag in s.tags:
        w.buf += tag.encode(encoding, "replace")
        w.char(0)
    w.int(s.cur_line)
    w.int(s.cur_stmt)
    return bytes(w.buf)


# ---------------------------------------------------------------- gloval.sav
# 全局变量单独一个文件（引擎 `ScriptHandler::saveGlovalData` / `loadGlovalData`）：
# 从 `global_variable_border` 到 `variable_range`，每槽一个 int + 一个 NUL 结尾的串。
# 实测量级：Ever17 border=500 → (4096-500)*5 = 17,980 字节（全空串时）。

DEFAULT_VARIABLE_RANGE = 4096


def parse_gloval(data: bytes, *, border: int,
                 variable_range: int | None = None,
                 encoding: str = "gbk") -> dict[int, tuple[int, str]]:
    """读 `gloval.sav` → {槽号: (int, str)}，只返回非空槽。

    `variable_range` 省略时按"读到底"处理（每槽 4 字节 + 到 NUL 的串）。
    """
    out: dict[int, tuple[int, str]] = {}
    p = 0
    slot = border
    limit = variable_range if variable_range is not None else -1
    while p + 4 <= len(data) and (limit < 0 or slot < limit):
        num = struct.unpack_from("<i", data, p)[0]
        p += 4
        end = data.find(b"\x00", p)
        if end < 0:
            raise EngineSaveError(f"gloval.sav 偏移 {p} 处的字符串没有 NUL 结尾")
        text = data[p:end].decode(encoding, "replace")
        p = end + 1
        if num or text:
            out[slot] = (num, text)
        slot += 1
    return out


def build_gloval(variables: dict[int, tuple[int, str]], *, border: int,
                 variable_range: int = DEFAULT_VARIABLE_RANGE,
                 encoding: str = "gbk") -> bytes:
    """把 >= border 的全局槽写成 `gloval.sav` 的字节。"""
    buf = bytearray()
    for slot in range(border, variable_range):
        num, text = variables.get(slot, (0, ""))
        buf += struct.pack("<i", int(num))
        if text:
            buf += text.encode(encoding, "replace")
        buf.append(0)
    return bytes(buf)
