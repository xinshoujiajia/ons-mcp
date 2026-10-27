"""运行时状态：变量表、字符串表、精灵表、文本框配置。

变量模型照引擎（`ScriptHandler::VariableData`）：

* 变量表是**按编号索引的槽位**，每个槽同时存 `num`（整数）和 `str`（字符串），
  所以 `%5` 和 `$5` 是同一个槽的两种值。
* `numalias foo,5` 建立"名字 → 槽号"的映射，`%foo`、`$foo` 都解析到槽 5。
  名字大小写不敏感（引擎读 token 时折成小写）。
* 名字全数字时直接当槽号：`%101` / `$0`（Ever17 全篇依赖）。
* **未定义的名字按 0 号槽处理** —— 这是引擎 `parseInt` 的行为：
  查不到 num alias 时返回 0（注释里写着 "assume 0"）。我们照做，但会记一笔日志，
  方便移植新游戏时发现拼错的别名。
* `stralias name,"文本"` 是**字符串常量**，只在"裸名字"出现在字符串表达式里时生效；
  它不是变量，`$name` 查的是 num alias（查不到就落到 0 号槽）。

槽号可以超出 `variable_range`：引擎 `getVariableData` 会动态扩容，我们也用 dict 兜住。
`global_border` 把槽位切成两段：`< border` 是存档里保存/恢复的"一般变量"，
`>= border` 是"全局变量"（不写进 `save<N>.dat`，单独落在 `gloval.sav`，
见 `session._write_globals`）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .log import get_logger

log = get_logger("state")


@dataclass
class ArrayVar:
    """`dim ?name[e1][e2]...` 声明出来的数组。

    引擎 `ScriptHandler::declareDim`：

    * **每维元素数 = 声明值 + 1**（`av->dim[i] = array.dim[i] + 1`），
      所以 `dim ?a[100]` 的合法下标是 `0..100`，共 101 个元素。
      实测 `exports/` 里那份真存档：数组段 404 字节 = 101 个 int，与源码一致。
    * 数据**只有 int**（`ArrayVariable::data` 是 `int*`），`dim $name[...]` 也一样；
      引擎没有字符串数组。
    * 越界时引擎 `getArrayPtr` 直接 `errorAndExit`（而且**不检查负下标**）。
      我们不崩，返回 0 / 写入失败，并记一笔 `array_oob`。
    * 元素按行主序线性存放：`linear = ((i0)*d1 + i1)*d2 + i2 ...`
    """

    no: int                        # 槽号（numalias 解析后）
    dims: list[int] = field(default_factory=list)    # 每维元素数
    data: list[int] = field(default_factory=list)    # 线性数据
    name: str = ""                 # 声明时的名字，调试用

    @property
    def size(self) -> int:
        n = 1
        for d in self.dims:
            n *= d
        return n


@dataclass
class Sprite:
    id: int
    visible: bool = False
    x: int = 0
    y: int = 0
    tag: str = ""             # 原始 tag，便于调试
    # 可能是 PIL.Image，也可能是 render.DeferredImage（图片型精灵的延迟句柄：
    # 只记文件名，`.size` 读文件头、`.materialize()` 才解码）。要像素请用
    # `Renderer.image_of()`，要尺寸直接 `.width/.height`（两者都支持）。
    image: Any = None
    kind: str = "image"       # image | text | solid | unknown
    alpha: int = 255
    text: str = ""            # kind == 'text' 时的正文（选项按钮靠它定位）
    cell: int = 0             # 条图当前帧（引擎的 current_cell；没有动画，恒为 0）

    def copy(self) -> "Sprite":
        return Sprite(self.id, self.visible, self.x, self.y, self.tag,
                      self.image, self.kind, self.alpha, self.text, self.cell)


@dataclass
class AudioState:
    """音频**状态**（不是播放）。

    引擎存档里与声音有关的字段（`saveSaveFile2`）：
      music_file_name / music_play_loop_flag / mp3save_flag /
      wave_file_name / wave_play_loop_flag / loop_bgm_name[2] / cd_track / cd_loop

    读档时引擎拿这些名字**重放**声音。我们不解码、不播放，只记账 ——
    agent 听不到，但存档语义要完整（将来做原版档互通也用得上）。

    刻意**不进存档**的两项（引擎也不存）：
      voice  —— `dwave`/`dwaveloop` 语音走独立声道，存档不持久化
      volume —— `bgmvol`/`sevol` 等写进 envdata，不在存档文件里
    """

    music: str = ""
    music_loop: bool = False
    mp3save: bool = False          # 音乐名是否随存档恢复（`mp3` 命令是 false）
    midi: str = ""                 # play / playonce 的非 CD 分支（MIDI）
    midi_loop: bool = False
    wave: str = ""
    wave_loop: bool = False
    loop_bgm: list[str] = field(default_factory=lambda: ["", ""])
    cd_track: int = -1
    cd_loop: bool = False
    # 以下只在内存里，不进存档
    voice: str = ""
    volume: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "music": self.music,
            "music_loop": self.music_loop,
            "mp3save": self.mp3save,
            "midi": self.midi,
            "midi_loop": self.midi_loop,
            "wave": self.wave,
            "wave_loop": self.wave_loop,
            "loop_bgm": list(self.loop_bgm),
            "cd_track": self.cd_track,
            "cd_loop": self.cd_loop,
        }

    def clear_music(self) -> None:
        self.music = ""
        self.music_loop = False

    def clear_wave(self) -> None:
        self.wave = ""
        self.wave_loop = False


@dataclass
class Button:
    """按钮。命中区一律是矩形（引擎里 spbtn/exbtn 用的是精灵图片矩形）。"""
    no: int
    kind: str = "rect"          # rect | sprite | exbtn
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)   # x,y,w,h
    sprite_no: int = -1
    ctl_idle: str = ""          # exbtn_d 给的空闲态
    ctl_hover: str = ""         # exbtn 自带的悬停态
    label: str = ""             # 供 choices() 关联选项文本

    def contains(self, x: int, y: int) -> bool:
        bx, by, bw, bh = self.rect
        return bx <= x < bx + bw and by <= y < by + bh


@dataclass
class SelectLink:
    text: str = ""
    label: str = ""


@dataclass
class WindowConfig:
    """setwindow3 / setwindow 解析结果。坐标语义见 FontInfo::x()/y()。"""
    x: int = 0
    y: int = 0
    num_x: int = 32
    num_y: int = 3
    font_size_x: int = 26
    font_size_y: int = 26
    pitch_x: int = 26
    pitch_y: int = 36
    wait_time: int = 1
    bold: bool = True
    shadow: bool = True
    frame_path: str = ""
    frame_x: int = 0
    frame_y: int = 0
    # `#RRGGBB` 形式的窗口：引擎读 4 个坐标 (x0,y0,x1,y1)，宽高 = x1-x0+1 / y1-y0+1
    frame_w: int = 0
    frame_h: int = 0
    frame_color: str = ""
    # `textcolor` 设的正文颜色（引擎 sentence_font.color）
    text_color: str = "#FFFFFF"
    # `setkinsoku` / `addkinsoku` 覆盖的禁则表；空串 = 用 render 里的内置表
    kinsoku_head: str = ""
    kinsoku_tail: str = ""
    active: bool = False
    # 烤好的文本框图片（引擎在 setwindow3 时就按当时的全局透明模式建好了）
    frame_image: Any = None


@dataclass
class Page:
    """一屏文本。"""
    name: str = ""
    lines: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        body = "\n".join(self.lines)
        return f"{self.name}：{body}" if self.name else body


class SlotView:
    """只读视图：把"按名字取值"翻译成"按槽号取值"。

    只为 `script.Args` 服务——它只会调 `.get(名字, 默认值)`，
    这样表达式解析那一层不用知道槽位和别名的存在。
    """

    __slots__ = ("_state", "_is_int")

    def __init__(self, state: "State", is_int: bool):
        self._state = state
        self._is_int = is_int

    def get(self, name: str, default: Any = 0) -> Any:
        state = self._state
        slot = state.resolve(name)
        table = state.int_slots if self._is_int else state.str_slots
        return table.get(slot, default)

    def __contains__(self, name: str) -> bool:
        state = self._state
        slot = state.resolve(name)
        return slot in (state.int_slots if self._is_int else state.str_slots)

    def __len__(self) -> int:
        return len(self._state.int_slots if self._is_int else self._state.str_slots)


@dataclass
class State:
    # ---- 变量：槽号 → 值（两种值共用一套槽号）
    int_slots: dict[int, int] = field(default_factory=dict)
    str_slots: dict[int, str] = field(default_factory=dict)
    aliases: dict[str, int] = field(default_factory=dict)        # numalias
    str_aliases: dict[str, str] = field(default_factory=dict)    # stralias（字符串常量）
    global_on: bool = False                                      # globalon
    global_border: int = 200                                     # 一般变量 / 全局变量的分界
    variable_range: int = 4096                                   # 脚本首行的上限（引擎会越界扩容）
    undefined: dict[str, int] = field(default_factory=dict)      # 未定义变量名的引用次数

    # `linepage` / `linepage2`：给每条文本行**自动补一个 clickstr**（引擎 readToken 里做的）。
    #   mode 0 = 不补（靠脚本自己的 `\`）
    #   mode 1 = 行末补 `\`：每行都等点击
    #   mode 2 = 页面快满时补 `@`、否则补 `\`（区别只在 clickstr 类型，我们都是等点击）
    linepage_mode: int = 0
    clickstr_line: int = 0
    # `clickstr "chars",line` 设的"等点击字符集"。引擎默认只有 `\` 和 `@`。
    clickstr_chars: str = "\\@"
    # `indent n`：每次换行后在行首插 n 个全角空格（引擎 indent_offset）
    indent_offset: int = 0
    # `locate x,y`：光标挪到第 x 格、第 y 行（单位是字符格，不是像素）。
    # 引擎换页时 `clearCurrentPage` → `sentence_font.clear()` 会把它归零，我们照做。
    text_locate: tuple[int, int] = (0, 0)
    # `texthide` / `textshow`：文本层只是不画，内容还在（和 textoff 不是一回事）
    text_hidden: bool = False
    # `pagetag`：开页标记（引擎 pagetag_flag，配合 getpage/ispage）
    pagetag: bool = False

    # `dim` 声明的数组，**按声明顺序**保存：引擎是尾插链表，存档也按这个顺序写。
    # 查找取第一个 no 匹配的节点（重复声明时第一次的有效，与 numalias 同规则）。
    arrays: list[ArrayVar] = field(default_factory=list)
    array_oob: dict[str, int] = field(default_factory=dict)      # 越界访问次数（调试用）

    sprites: dict[int, Sprite] = field(default_factory=dict)
    window: WindowConfig = field(default_factory=WindowConfig)
    bg_image: Any = None
    bg_name: str = ""            # 人读的名字；bgcopy 之后是 "*bgcpy"
    bg_source: str = ""          # 真实的背景文件名（存档靠它重建）
    bg_ops: list[dict] = field(default_factory=list)   # blt 操作流水，读档时重放
    bg_baked: bool = False       # 是否发生过 bgcopy（重放完要把 overlay 烘进背景）
    bg_color: tuple[int, int, int] = (0, 0, 0)
    text_on: bool = True
    text_window_erased: bool = False
    page: Page | None = None
    humanz: int = 256
    buttons: list[Button] = field(default_factory=list)     # 后注册的优先命中
    select_links: list[SelectLink] = field(default_factory=list)
    btnwait_var: str = ""
    btndef_image: str = ""
    btndef_pixels: Any = None       # btndef 加载的位图，blt 的图源
    exbtn_default_ctl: str = ""     # exbtn_d 设的空闲态控制串
    last_button: int = 0

    # 立绘（引擎的 tachi）：0=左 1=中 2=右，位置由 ld 自动算
    tachi: dict[int, Sprite] = field(default_factory=dict)
    tachi_visible: bool = True      # all_sprite_hide 之类没用，留个开关
    underline: int = 0              # ld 的落底基准线；0 = 画面高度

    # 全局透明模式（transmode 命令）：leftup / copy / alpha
    trans_mode: str = "leftup"

    # blt 画到这一层上；bgcopy 会把它烘进背景，bg 会清掉它
    overlay: Any = None

    # 最近一次点击坐标（getcursorpos / getcursorpos2 用）
    last_cursor: tuple[int, int] = (0, 0)

    # 音频状态（只记账，不播放）
    audio: AudioState = field(default_factory=AudioState)

    # 按钮层的文字（cselbtn 之类）。引擎里 ButtonLink 画在最后，压在所有东西上面
    ui_sprites: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._int_view = SlotView(self, True)
        self._str_view = SlotView(self, False)

    # ------------------------------------------------------------ 变量访问
    @property
    def variables(self) -> SlotView:
        """只读视图（`Args` 用）。写入请走 `set_int`。"""
        return self._int_view

    @property
    def strings(self) -> SlotView:
        return self._str_view

    def resolve(self, name: str) -> int:
        """名字 → 槽号。未定义的名字按引擎行为落到 0 号槽。"""
        n = (name or "").strip().lower()
        if not n:
            return 0
        if n.isdigit():
            return int(n)
        slot = self.aliases.get(n)
        if slot is not None:
            return slot
        self.note_undefined(n)
        return 0

    def note_undefined(self, name: str) -> None:
        """记一笔"脚本引用了没有 numalias 的名字"。引擎的做法是当作 0 号槽。

        数值表达式里的裸名字走 `Args._factor`，那里拿不到 State，所以通过这个
        方法（Args 的 `arrays` 参数就是 State）回调进来，保证计数不漏。
        """
        n = (name or "").strip().lower()
        if not n:
            return
        self.undefined[n] = self.undefined.get(n, 0) + 1
        if self.undefined[n] == 1:
            log.warning("变量名 %%%s 没有 numalias 定义，按引擎行为当作 0 号槽", n)

    def set_alias(self, name: str, slot: int) -> None:
        """numalias。引擎是头插链表、查找取第一个，所以重复定义以第一次为准。"""
        self.aliases.setdefault((name or "").lower(), int(slot))

    def set_str_alias(self, name: str, value: str) -> None:
        self.str_aliases.setdefault((name or "").lower(), value)

    def get_int(self, name: str) -> int:
        return int(self.int_slots.get(self.resolve(name), 0))

    def set_int(self, name: str, value: int) -> None:
        self.int_slots[self.resolve(name)] = int(value)

    def get_str(self, name: str) -> str:
        return self.str_slots.get(self.resolve(name), "")

    def set_str(self, name: str, value: str) -> None:
        self.str_slots[self.resolve(name)] = value

    # ------------------------------------------------------------ 数组（dim）
    def declare_array(self, name: str, dims: list[int]) -> ArrayVar:
        """`dim ?name[e1]...`：`dims` 传**元素数**（调用方已经 +1）。"""
        no = self.resolve(name)
        sizes = [max(int(d), 0) for d in (dims or [1])] or [1]
        total = 1
        for d in sizes:
            total *= d
        av = ArrayVar(no=no, dims=sizes, data=[0] * total, name=(name or "").lower())
        self.arrays.append(av)
        return av

    def find_array(self, name_or_no: str | int) -> ArrayVar | None:
        """引擎 `getArrayPtr` 从 root 遍历取**第一个** no 匹配的节点。"""
        no = int(name_or_no) if isinstance(name_or_no, int) else self.resolve(name_or_no)
        for av in self.arrays:
            if av.no == no:
                return av
        return None

    def array_ptr(self, name: str, idxs: list[int],
                  offset: int = 0) -> tuple[ArrayVar, int] | None:
        """`?name[i0][i1]...` → (数组, 线性下标)。越界或未声明返回 None。

        引擎越界直接 `errorAndExit`，我们选择"不崩但记账"。
        """
        av = self.find_array(name)
        if av is None:
            key = f"undef:{name}"
            self.array_oob[key] = self.array_oob.get(key, 0) + 1
            return None
        if len(idxs) != len(av.dims):
            key = f"ndim:{name}"
            self.array_oob[key] = self.array_oob.get(key, 0) + 1
            return None
        linear = 0
        for i, idx in enumerate(idxs):
            if idx < 0 or idx >= av.dims[i]:
                key = f"oob:{name}[{idx}]"
                self.array_oob[key] = self.array_oob.get(key, 0) + 1
                return None
            linear = linear * av.dims[i] + idx
        if offset:
            last = idxs[-1] + offset
            if last < 0 or last >= av.dims[-1]:
                key = f"oob:{name}[{idxs[-1]}+{offset}]"
                self.array_oob[key] = self.array_oob.get(key, 0) + 1
                return None
            linear += offset
        return av, linear

    def get_array(self, name: str, idxs: list[int], offset: int = 0) -> int:
        hit = self.array_ptr(name, idxs, offset)
        return int(hit[0].data[hit[1]]) if hit else 0

    def set_array(self, name: str, idxs: list[int], value: int,
                  offset: int = 0) -> bool:
        hit = self.array_ptr(name, idxs, offset)
        if hit is None:
            return False
        hit[0].data[hit[1]] = int(value)
        return True

    # ------------------------------------------------------------ 存档辅助
    def local_int_slots(self) -> dict[int, int]:
        """一般变量（槽号 < global_border）——只有这部分进存档。"""
        b = self.global_border
        return {k: v for k, v in self.int_slots.items() if k < b}

    def local_str_slots(self) -> dict[int, str]:
        b = self.global_border
        return {k: v for k, v in self.str_slots.items() if k < b}

    def global_int_slots(self) -> dict[int, int]:
        b = self.global_border
        return {k: v for k, v in self.int_slots.items() if k >= b}

    def global_str_slots(self) -> dict[int, str]:
        b = self.global_border
        return {k: v for k, v in self.str_slots.items() if k >= b}

    # ------------------------------------------------------------ 精灵
    def sprite(self, sid: int) -> Sprite:
        sp = self.sprites.get(sid)
        if sp is None:
            sp = Sprite(sid)
            self.sprites[sid] = sp
        return sp

