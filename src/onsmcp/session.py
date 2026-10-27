"""会话层：把解释器 + 渲染器 + 轨迹拼成 MCP 工具需要的形态。"""
from __future__ import annotations

import os
import re
import time
from dataclasses import asdict
from pathlib import Path

from .files import GameFiles
from .interp import Frame, Interpreter, Utterance
from .log import get_logger
from .render import Renderer, parse_sprite_spec
from .script import Script
from .savefile_bin import (MAX_PAGE_LIST, MAX_SPRITE_NUM, EngineSave,
                           EngineSaveError, NestEntry, SpriteSlot,
                           build as build_engine_save,
                           build_gloval,
                           parse as parse_engine_save,
                           parse_gloval)
from .scriptfile import load_script
from .state import ArrayVar, Button, Page, SelectLink


def _parse_color(text: str) -> tuple[int, int, int]:
    """`#RRGGBB` → RGB；解析不了给黑色（引擎的窗口色默认就是 0）。"""
    m = re.match(r"#([0-9A-Fa-f]{6})", text or "")
    if not m:
        return (0, 0, 0)
    v = int(m.group(1), 16)
    return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


def _sprite_name(tag: str, parse_spec) -> str:
    """tag → 图片文件名。引擎的 sprite 槽只存文件名，不存整个 tag。"""
    if not tag:
        return ""
    try:
        spec = parse_spec(tag)
    except Exception:                      # noqa: BLE001
        return ""
    return getattr(spec, "filename", "") or ""


def _prod(values) -> int:
    """数组元素总数（引擎 `dim[i]` 连乘；空维度当 1）。"""
    n = 1
    for v in values:
        n *= int(v)
    return max(n, 1)


def _dir_writable(path: Path) -> bool:
    """真写一次再删 —— Windows 上 `os.access` 对只读目录并不可靠。"""
    probe = path / ".onsmcp_probe"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


# 全局变量文件：就是引擎的 gloval.sav（不再是自有的 JSON）
GLOBAL_FILE = "gloval.sav"

log = get_logger("session")


class SaveFormatError(Exception):
    """存档读不了（版本不符 / 内容坏了），带一句给 agent 的提示。"""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


class SaveDirError(Exception):
    """存档目录不可用（建不出来 / 不可写），带一句给 agent 的提示。"""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


class GameSession:
    def __init__(self, game_dir: str, *, start_label: str = "start",
                 width: int = 0, height: int = 0,
                 run_text_hooks: bool = False, screenshot_dir: str | None = None,
                 save_dir: str | None = None,
                 bootstrap: bool = True, cache_mb: int = 320,
                 timeout_s: float | None = None):
        self.game_dir = Path(game_dir)
        if not self.game_dir.is_dir():
            raise FileNotFoundError(f"游戏目录不存在: {game_dir}")
        # 存档落点。引擎也有 `--save-dir`：默认跟游戏走，但可以指到别处。
        self.save_dir = self._resolve_save_dir(save_dir)

        # 资源访问：磁盘优先，其次 .nsa 归档（原始发布版没有解包也能直接玩）
        self.files = GameFiles.open(self.game_dir)
        loaded = load_script(self.files)
        self.loaded = loaded
        self.config = loaded.config
        self.script_source = loaded.source
        self.encoding, self.encoding_detail = loaded.encoding, loaded.detail
        self.script = Script.from_text(loaded.text)
        # 分辨率：脚本首行 ;$S / ;mode 指定，调用方显式给了才覆盖
        self.renderer = Renderer(self.game_dir, width or self.config.width,
                                 height or self.config.height,
                                 cache_budget_mb=cache_mb, files=self.files)
        self.renderer.set_sample_text(loaded.text)
        self.interp = Interpreter(self.script, self.renderer, start_label=start_label,
                                  run_text_hooks=run_text_hooks)
        # len 之类的命令按脚本编码算字节数（GBK 汉字 2 字节），必须先告诉解释器
        self.interp.encoding = loaded.encoding
        # 变量槽位的分界线来自脚本首行：;value<n> / ;G<n> 定全局边界，;v<n> 定上限
        self.interp.state.global_border = self.config.global_border
        self.interp.state.variable_range = self.config.variable_range
        # 只有内部工具（run_scene 等）会显式给路径落盘；
        # MCP 的 screenshot 工具一律走内存，不碰这个目录。
        self.shot_dir = Path(screenshot_dir) if screenshot_dir else self.game_dir / ".onsmcp_shots"
        self._trace_mark = 0          # 上次 reset 的起点（增量查询用）
        self._trace_origin = 0        # 会话起点（排除 define 区）
        self._shot_seq = 0
        self.started = False
        self.bootstrap = bootstrap
        # 单次操作（start/click）的墙钟预算：正常一次推进是 1~10 ms，
        # 10 秒还没停下来就说明脚本里有死循环，宁可中断也别把客户端挂死。
        if timeout_s is None:
            try:
                timeout_s = float(os.environ.get("ONSMCP_TIMEOUT", "10"))
            except ValueError:
                timeout_s = 10.0
        self.timeout_s = timeout_s
        self.log = get_logger("session")
        # 游戏内菜单的存读档走我们自己的格式，不伪造原版二进制存档
        self.interp.on_save = self._menu_save
        self.interp.on_load = self._menu_load
        self.interp.on_exists = self._menu_exists
        self.interp.on_savetime = self._menu_savetime

    # ------------------------------------------------------------ 内部
    def _run_define(self) -> None:
        self.interp.run_define_section()

    # ------------------------------------------------------------ 工具
    def _bootstrap_window(self, macro: str = "text_nomal") -> None:
        """从剧情中段起跑时，补上"章节开始时本该执行过的"文本框初始化。

        正常流程里 text_nomal 在进入章节前被调用一次；直接从 *w01_01 之类标签
        起跑会缺这一步，导致 setwindow3 没设过、文本没有排版基准。
        """
        if self.interp.state.window.active:
            return
        idx = self.script.label_index(macro)
        if idx is None:
            return
        it = self.interp
        it.pc = idx
        it.waiting = None
        it.finished = False
        it.stack.clear()
        it.run(max_steps=5000)
        it.waiting = None
        it.finished = False
        it.stack.clear()

    def start(self) -> dict:
        if not self.started:
            self._run_define()
            # define 跑完才知道有没有 globalon；有的话把全局槽位读回来（设置项/通关标记）
            self._read_globals()
            if self.bootstrap:
                self._bootstrap_window()
                target = self.script.label_index(self.interp.start_label)
                self.interp.pc = target if target is not None else 0
            # define 区是初始化，不算"剧情动作"——从这里才开始记
            self._trace_origin = len(self.interp.trace)
            self._trace_mark = self._trace_origin
            self._run()
            # 启动阶段的演出延迟（版本 logo → 标题这类转场）自动跳过：
            # start 的语义是"进到能玩的状态"，不该让 agent 先看一帧片头静帧。
            # 剧情里的长 delay（章节日期画面）照旧停下来，click 时再返回。
            for _ in range(8):
                if self.interp.waiting != "delay":
                    break
                self.interp.waiting = None
                self._run()
            self.started = True
        return self.state()

    def _pc_in_hook(self) -> bool:
        """PC 是否停在 textgosub 钩子里（此时 PC 位置不代表剧情位置）。"""
        it = self.interp
        return bool(it.run_text_hooks and it.current_label == "text_btn")

    def state(self) -> dict:
        it = self.interp
        return {
            "waiting": it.waiting,           # 'text' / 'btn' / 'delay' / None
            "finished": it.finished,
            # label/line 报剧情位置。
            # 注意：只有"开钩子后 PC 停在 *text_btn"这种情况才用 story_line，
            # 否则一律用 PC 真实位置——否则在选项界面（PC 已在 *customsel）
            # 会报出上一句台词的行号，agent 拿到的位置是错的。
            "label": (it.story_label if self._pc_in_hook()
                      else (self.script.label_of[it.pc - 1]
                            if 0 < it.pc <= len(self.script.label_of) else it.current_label)),
            "line": (it.story_line if (self._pc_in_hook() and it.story_line > 0)
                     else (it.script.instrs[it.pc].line_no
                           if it.pc < len(self.script.instrs) else -1)),
            "pc_label": (self.script.label_of[it.pc - 1]
                         if 0 < it.pc <= len(self.script.label_of) else it.current_label),
            "pc_line": it.script.instrs[it.pc - 1].line_no if 0 < it.pc <= len(it.script.instrs) else -1,
            "in_hook": bool(it.run_text_hooks and it.waiting == "btn"
                            and it.current_label == "text_btn"),
            # 上一次操作为什么提前停下：null=正常停在等待点
            "stopped": it.stop_reason or None,
            "page": it.state.page.as_text() if it.state.page else "",
            # 说话人（`page` 里是「名字：台词」，这里单独给一份，免得 agent 自己切）
            "speaker": it.state.page.name if it.state.page else "",
            "has_more_pages": bool(it.pending_pages),
            "unsupported": {
                k: {"count": v, "first_line": it.unsupported_at.get(k, -1)}
                for k, v in sorted(it.unsupported.items(), key=lambda kv: -kv[1])[:20]
            },
            # 引擎有、本项目还没做的命令（stubs.py 里的桩被撞到了）。
            # 和上面的 unsupported 分开报：前者是"活没干完"，后者是"脚本有问题"。
            **({"stubbed": {
                k: {"count": v, "first_line": it.stubbed_at.get(k, -1)}
                for k, v in sorted(it.stubbed.items(), key=lambda kv: -kv[1])[:20]
            }} if it.stubbed else {}),
            "memory": self.renderer.cache_stats(),
            "encoding": self.encoding,
            "script_source": self.script_source,
            # 存档落点：正常情况下就是游戏目录；只读时会回落到用户目录，
            # 这里报出来避免"存了但找不到文件"
            "save_dir": str(self.save_dir),
            "resolution": [self.renderer.width, self.renderer.height],
            "config": self.config.as_dict(),
            # 出现过的"没有 numalias 定义"的变量名——移植新游戏时用来发现拼错的别名
            **({"undefined_vars": dict(sorted(it.state.undefined.items()))}
               if it.state.undefined else {}),
            "prog": f"{it.pc}/{len(it.script.instrs)}",
        }

    def text(self, history: int = 0) -> str:
        """当前页文本；history>0 时前面附带最近 N 句台词。

        agent 常用「先读文本再决定点什么」，只给当前页会丢掉上下文，
        所以这里做成一个可选的滑动窗口。
        """
        page = self.interp.state.page
        current = page.as_text() if page is not None else ""
        if history <= 0:
            return current
        past = self.interp.history[-history:]
        if not past:
            return current
        lines = []
        for u in past:
            body = u.text.replace("\n", " ")
            lines.append(f"{u.name}：{body}" if u.name else body)
        return "\n".join(lines)

    def _run(self, max_steps: int = 20000) -> None:
        """带墙钟预算地跑解释器；超时不会抛异常，只是停在中途。"""
        it = self.interp
        it.deadline = (time.monotonic() + self.timeout_s) if self.timeout_s and self.timeout_s > 0 else None
        try:
            it.run(max_steps=max_steps)
        finally:
            it.deadline = None
        if it.stop_reason:
            self.log.warning("操作被中断：%s（label=%s L%s）",
                             it.stop_reason, it.current_label,
                             it.script.instrs[it.pc - 1].line_no
                             if 0 < it.pc <= len(it.script.instrs) else -1)

    # btnwait 的返回值约定（ONScripter）：正数=按钮 id，0=空点，
    # -1=右键，-2/-3=滚轮上下，-10=ESC，-11=空格
    BUTTON_CODES = {"left": None, "right": -1, "wheelup": -2,
                    "wheeldown": -3, "esc": -10, "space": -11}

    def click(self, x: int | None = None, y: int | None = None,
              button: str = "left") -> dict:
        it = self.interp
        if it.finished:
            return self.state()

        # 记一下"点之前"的画面状态，返回时告诉 agent 这次到底变了什么
        before = self._screen_fingerprint()

        if x is not None and y is not None:
            it.state.last_cursor = (int(x), int(y))

        # 按钮等待：点在哪个按钮上，就把 btnwait 的返回值定成那个编号
        if it.waiting == "btn":
            code = self.BUTTON_CODES.get(button)
            bid = code if code is not None else it.resolve_click(x, y)
            it.state.last_button = bid
            if it.state.btnwait_var:
                it.state.set_int(it.state.btnwait_var, bid)
            it.waiting = None
            self._run()
            return self._with_changes(before)

        # 演出停顿（长 delay）：画面已经合成好了，点一下继续跑脚本
        if it.waiting == "delay":
            it.waiting = None
            self._run()
            return self._with_changes(before)

        # 文本等待：引擎的 clickNewPage —— 这一页排满了，点击之后换页（清屏）
        if it.waiting == "text" and it._page_is_full():
            it.state.page = None
        # 有未显示的 @ 分段先追加；追加完就把 textgosub 挂上
        if it.pending_pages:
            it.next_page()
            if not it.pending_pages:
                it.text_hook_entered = False
                if it.enter_text_hook():
                    self._run()
            return self._with_changes(before)
        it.waiting = None
        self._run()
        return self._with_changes(before)

    # ------------------------------------------------------------ 画面变化（click 返回值用）
    # `sprites_added` / `sprites_removed` 最多列这么多个名字，避免整场人同时上场时刷屏
    CHANGE_LIST_MAX = 8

    def _screen_fingerprint(self) -> dict:
        """当前画面的"状态指纹"，用来判断两次操作之间画面变没变。

        刻意**只读状态、不碰像素**：为了判断变化去合成或解码，懒加载就白做了
        （一次 click 上百帧动画的场景会被拖回 0.6s）。所以测的是 bg / 立绘 /
        精灵表 / 文本层的状态而不是真实像素——`blt` 只改像素不改状态，
        这里靠 `bg_ops` 条数与 overlay 在不在间接兜住。
        """
        st = self.interp.state
        w = st.window
        tachi = []
        for no in range(3):
            sp = st.tachi.get(no)
            tachi.append(sp.tag if (sp is not None and sp.visible and sp.tag) else "")
        sprites = tuple(sorted(
            (sid, sp.kind, _sprite_name(sp.tag, parse_sprite_spec),
             int(sp.x), int(sp.y), bool(sp.visible), int(sp.alpha))
            for sid, sp in st.sprites.items()))
        return {
            "text": (st.page.as_text() if st.page is not None else "",
                     bool(st.text_on), bool(st.text_hidden),
                     bool(st.text_window_erased),
                     w.active, w.x, w.y, w.frame_path, w.frame_color),
            "bg": (st.bg_source or st.bg_name, tuple(st.bg_color),
                   len(st.bg_ops), bool(st.bg_baked), st.overlay is not None),
            "tachi": tuple(tachi),
            "sprites": sprites,
        }

    def _screen_diff(self, before: dict) -> dict:
        """对比两次指纹 → 给 agent 的 `changes` 块。

        `screen` 是总开关（任何一层变了都为真），细分四项告诉它变的是哪一层：
        台词变了要不要重读、bg / 立绘变了要不要重新截图。
        """
        st = self.interp.state
        now = self._screen_fingerprint()
        changed = {k: before.get(k) != now.get(k)
                   for k in ("text", "bg", "tachi", "sprites")}
        # 换掉的图：按槽位号比"图名"（万华镜的"立绘"其实是 lsp 画的，所以要看这里）
        was = {sid: name for sid, kind, name, *_ in before["sprites"]
               if kind == "image" and name}
        cur = {sid: name for sid, kind, name, *_ in now["sprites"]
               if kind == "image" and name}
        return {
            "screen": any(changed.values()),
            **changed,
            # 下面这几个是"现在是什么"，不是"变了什么"——agent 每步都能拿到当前场景
            "bg_image": st.bg_source or st.bg_name,
            "tachi_images": list(now["tachi"]),
            "sprite_count": sum(1 for sp in st.sprites.values() if sp.visible),
            # 换掉的图：按槽位号比 tag（万华镜的"立绘"其实也是 lsp，所以要看这里）
            "sprites_added": [cur[k] for k in cur if k not in was][:self.CHANGE_LIST_MAX],
            "sprites_removed": [was[k] for k in was if k not in cur][:self.CHANGE_LIST_MAX],
        }

    def _with_changes(self, before: dict) -> dict:
        """`state()` + `changes`（click / choose 的返回形状）。"""
        st = self.state()
        st["changes"] = self._screen_diff(before)
        return st

    def trace(self, reset: bool = True) -> list[dict]:
        """上次操作以来执行过的脚本行（逐行：行号 / 类型 / 命令 / 标签）。"""
        # reset=True  → 只给"上次查询之后"的新内容，并清空起点
        # reset=False → 给从会话开始（define 区之后）到现在的全部内容
        base = self._trace_mark if reset else self._trace_origin
        entries = self.interp.trace[base:]
        if reset:
            self._trace_mark = len(self.interp.trace)
        return [{"line": e.line, "kind": e.kind, "cmd": e.cmd,
                 "label": e.label, "text": e.text[:200]} for e in entries]

    def render_frame(self) -> "Image.Image":
        """合成当前画面（不落盘）。"""
        return self.renderer.compose(
            self.interp.state,
            self.interp.state.page.lines if self.interp.state.page else None,
            draw_name=not self.interp.run_text_hooks)

    def screenshot(self, path: str | None = None,
                   rect: list[int] | None = None) -> str:
        """落盘保存截图，返回文件路径。

        仅供内部工具（run_scene / calibrate_layout）留档用；
        MCP 的 `screenshot` 工具走 `screenshot_bytes()`，不写文件。
        """
        img = self.render_frame()
        img = _apply_rect(img, rect)
        if path is None:
            self._shot_seq += 1
            path = str(self.shot_dir / f"shot_{self._shot_seq:04d}.png")
        img.save(path)
        return path

    def screenshot_bytes(self, rect: list[int] | None = None) -> bytes:
        """只返回 PNG 字节，**不写任何文件**。"""
        import io
        img = self.render_frame()
        img = _apply_rect(img, rect)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _button_by_no(self, no: int):
        for b in reversed(self.interp.state.buttons):
            if b.no == no:
                return b
        return None

    def choices(self) -> list[dict]:
        """当前选项：文本 + 可点击矩形。

        移植脚本的 *customsel 把选项文本画成字符串精灵（553/556/...），
        按钮（554/557/...）垫在同一行下面；所以用「文本精灵的落点做命中测试」
        就能反查每个选项对应哪个按钮，不依赖按钮编号的约定。
        """
        it = self.interp
        links = it.state.select_links
        if not links:
            return []
        out = []
        for i, link in enumerate(links):
            btn = None
            for sp in it.state.sprites.values():
                if sp.kind != "text" or not sp.text or not sp.visible:
                    continue
                if sp.text.strip() != link.text.strip():
                    continue
                hit = it.hit_test(int(sp.x) + 4, int(sp.y) + 4)
                if hit:
                    btn = self._button_by_no(hit)
                    break
            out.append({
                "index": i,
                "text": link.text,
                "label": link.label,
                "button_id": btn.no if btn else None,
                "rect": list(btn.rect) if btn else None,
            })
        return out

    def choose(self, index: int) -> dict:
        """按序号选一个选项（等价于点它的中心）。"""
        opts = self.choices()
        if not (0 <= index < len(opts)):
            return {"error": f"选项越界：{index}，当前 {len(opts)} 个", "choices": opts}
        rect = opts[index]["rect"]
        if not rect:
            return {"error": "该选项没有对应的可点击区域", "choice": opts[index]}
        x, y = rect[0] + rect[2] // 2, rect[1] + rect[3] // 2
        return {"clicked": opts[index], "state": self.click(x, y)}

    def buttons(self) -> list[dict]:
        """当前所有可点击按钮。rect 是"游戏屏幕上的矩形区域" [x, y, w, h]。"""
        return [{"no": b.no, "kind": b.kind, "rect": list(b.rect),
                 "sprite": b.sprite_no} for b in self.interp.state.buttons]

    def _resolve_save_dir(self, explicit: str | None) -> Path:
        """定存档目录：显式参数 → `ONSMCP_SAVE_DIR` → 游戏目录 → 用户目录。

        引擎默认把 `save<N>.dat` / `gloval.sav` 写在游戏目录（`archive_path`），
        我们也照做；但装进 Program Files 这类只读位置时写不进去，那种情况
        回落到用户目录，而不是让每次存档都抛 PermissionError。

        显式给了却不可用（建不出来 / 不可写）时直接报错 —— 静默换地方会更难查。
        """
        wanted = (explicit or os.environ.get("ONSMCP_SAVE_DIR", "")).strip()
        if wanted:
            path = Path(wanted).expanduser()
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise SaveDirError(
                    f"存档目录建不出来: {path}（{exc}）",
                    hint="检查 ONSMCP_SAVE_DIR 是否指向一个可写的目录") from exc
            if not _dir_writable(path):
                raise SaveDirError(
                    f"存档目录不可写: {path}",
                    hint="换一个可写目录，或清掉 ONSMCP_SAVE_DIR 让存档回到游戏目录")
            if path.resolve() != self.game_dir.resolve():
                log.info("存档目录 → %s", path)
            return path

        if _dir_writable(self.game_dir):
            return self.game_dir

        local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
        base = Path(local) if local else Path.home()
        fallback = base / "onsmcp" / (self.game_dir.name or "game")
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SaveDirError(
                f"游戏目录不可写，回落目录也建不出来: {fallback}（{exc}）",
                hint="设 ONSMCP_SAVE_DIR 指向一个可写目录") from exc
        log.info("游戏目录不可写（%s），存档改到 %s", self.game_dir, fallback)
        return fallback

    def _slot_path(self, slot: int) -> Path:
        """存档文件就是引擎的 `save<N>.dat`，没有第二套格式。"""
        return self.save_dir / f"save{int(slot)}.dat"

    def _menu_save(self, slot: int) -> None:
        self.save(slot)

    def _menu_load(self, slot: int) -> None:
        try:
            self.load(slot, resume=False)
        except Exception as exc:                      # noqa: BLE001
            # 游戏内读档失败不能让玩家（agent）以为读成功了
            self.log.warning("游戏内读档失败 slot=%s：%s", slot, exc)

    def _menu_exists(self, slot: int) -> bool:
        return self._slot_path(slot).exists()

    def _menu_savetime(self, slot: int):
        p = self._slot_path(slot)
        if not p.exists():
            return (0, 0, 0, 0)
        t = time.localtime(p.stat().st_mtime)
        return (t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min)

    # ------------------------------------------------------------ 原版二进制存档
    def to_engine_save(self) -> EngineSave:
        """把当前状态整理成 `EngineSave`（写 `save<N>.dat` 用）。

        原则：**引擎建模了的字段照搬，没建模的写引擎默认值**。后者读档后
        那些元素会消失（bar/prnum/sprite2/monocro/ruby），但剧情能接着跑。
        """
        it, st, r = self.interp, self.interp.state, self.renderer
        w = st.window
        s = EngineSave()
        s.screen_width = r.width

        # 字体 / 窗口
        s.is_bold = 1 if w.bold else 0
        s.is_shadow = 1 if w.shadow else 0
        s.color = (255, 255, 255)
        s.top_xy = (int(w.x), int(w.y))
        s.num_xy = (int(w.num_x), int(w.num_y))
        s.font_size = (int(w.font_size_x), int(w.font_size_y))
        s.pitch = (int(w.pitch_x), int(w.pitch_y))
        s.window_color = _parse_color(w.frame_color)
        s.wait_time = int(w.wait_time)
        if w.frame_path:
            fw = fh = 0
            if w.frame_image is not None:
                fw, fh = w.frame_image.size
            s.font_info = (int(w.frame_x), int(w.frame_y),
                           int(w.frame_x) + fw - 1, int(w.frame_y) + fh - 1)
            s.font_info_image = w.frame_path

        # 画面
        s.bg = st.bg_source or ("" if st.bg_name.startswith("*") else st.bg_name)
        tachi, tx, ty = list(s.tachi), list(s.tachi_x), list(s.tachi_y)
        for i in range(3):
            sp = st.tachi.get(i)
            if sp is not None:
                tachi[i] = _sprite_name(sp.tag, parse_sprite_spec)
                tx[i], ty[i] = int(sp.x), int(sp.y)
        s.tachi, s.tachi_x, s.tachi_y = tuple(tachi), tuple(tx), tuple(ty)

        s.sprites = [SpriteSlot() for _ in range(MAX_SPRITE_NUM)]
        for sid, sp in st.sprites.items():
            if not 0 <= sid < MAX_SPRITE_NUM:
                continue
            s.sprites[sid] = SpriteSlot(
                image_name=_sprite_name(sp.tag, parse_sprite_spec),
                x=int(sp.x), y=int(sp.y),
                visible=1 if sp.visible else 0,
                current_cell=int(sp.cell),
                trans=-1 if sp.alpha >= 255 else max(0, min(255, int(sp.alpha))))

        # 变量：只写一般变量（槽号 < global_border），空槽由 build 补 0
        border = max(int(st.global_border), 0)
        s.border = border
        for slot, v in st.int_slots.items():
            if slot < border and (v or st.str_slots.get(slot)):
                s.variables[slot] = (int(v), st.str_slots.get(slot, ""))
        for slot, v in st.str_slots.items():
            if v and slot < border and slot not in s.variables:
                s.variables[slot] = (0, v)

        # 数组：引擎按声明顺序写裸 int
        s.arrays = [list(av.data) for av in st.arrays]

        # 调用栈：引擎的 nest 用"脚本字节偏移"，我们用行起始偏移近似
        # （只有正在宏/循环里存档才会用到；纯行首存档时栈是空的）
        offsets = self._line_offsets()
        for f in it.stack:
            s.nest.append(NestEntry(kind="label",
                                    offset=self._pc_offset(offsets, f.return_pc)))
        for rec in it.for_stack:
            s.nest.append(NestEntry(
                kind="for", var_no=st.resolve(str(rec.get("var", ""))),
                to=int(rec.get("end", 0)), step=int(rec.get("step", 1)),
                offset=-self._pc_offset(offsets, int(rec.get("pc", 0)))))

        # 音频
        au = st.audio
        s.midi = au.midi
        s.wave = au.wave
        s.cd_track = int(au.cd_track)
        s.midi_loop = 1 if au.midi_loop else 0
        s.wave_loop = 1 if au.wave_loop else 0
        s.cd_loop = 1 if au.cd_loop else 0
        s.music_loop = 1 if au.music_loop else 0
        s.mp3save = 1 if au.mp3save else 0
        s.music = au.music
        s.loop_bgm = tuple((list(au.loop_bgm) + ["", ""])[:2])

        s.btndef = st.btndef_image
        s.underline = int(st.underline) or r.height

        # 页面：引擎最多 16 页，用台词历史填
        texts = [u.text for u in it.history if u.text][-MAX_PAGE_LIST:]
        if not texts and st.page is not None:
            texts = [st.page.as_text()]
        s.pages = texts
        s.tags = ["NONE|0"] * len(texts)

        # 续跑点。引擎存的 cur_line 是 **0-based** 绝对行号，而且**滞后一行**：
        # `current_line` 要等读下一行 token 时才递增，所以存档时拿到的是"上一条执行完的行"。
        # 两份真档都印证了这一点（探测工程在 savegame 行存档 → 存上一行；
        # Ever17 在台词行存档 → 存台词前一行）。
        if it.script.instrs:
            pc = min(max(it.pc - 1, 0), len(it.script.instrs) - 1)
            instr = it.script.instrs[pc]
            line0 = max(int(instr.line_no) - 2, 0)
            s.cur_line = line0
            prev = self.script.lines[line0] if line0 < len(self.script.lines) else ""
            # 冒号数是"从上一行行首数到当前语句"，跨行的部分也要算进去
            s.cur_stmt = prev.count(":") + int(it.cur_stmt)
        return s

    def save_engine(self, slot: int = 0) -> Path:
        """兼容旧名字：现在 `save()` 写的就是原版档。"""
        return Path(self.save(slot))

    def load_engine_bytes(self, data: bytes) -> dict:
        """读原版 `save<N>.dat` 并套用到当前会话（不继续执行）。"""
        try:
            es = parse_engine_save(
                data,
                border=max(int(self.interp.state.global_border), 0),
                arrays=[av.size for av in self.interp.state.arrays],
                encoding=self.encoding)
        except EngineSaveError as exc:
            raise SaveFormatError(
                str(exc),
                hint="这不是 2.8 版的 ONS 存档，或者文件被截断了；换一个槽位试试") from exc
        self._apply_engine_save(es)
        return self.state()

    def _apply_engine_save(self, es) -> None:
        it, st = self.interp, self.interp.state

        # 变量：只覆盖一般变量（全局槽不回滚 —— 引擎 readVariables 只读到 border）
        border = st.global_border
        st.int_slots = {k: v for k, v in st.int_slots.items() if k >= border}
        st.str_slots = {k: v for k, v in st.str_slots.items() if k >= border}
        for slot, (num, text) in es.variables.items():
            if slot < border:
                st.int_slots[slot] = int(num)
                if text:
                    st.str_slots[slot] = text

        # 数组：形状以当前脚本的 dim 为准
        for i, data in enumerate(es.arrays):
            if i < len(st.arrays):
                av = st.arrays[i]
                n = min(len(av.data), len(data))
                av.data[:n] = data[:n]

        st.bg_source = es.bg
        st.bg_name = es.bg
        # 读档也不立刻解码：只记文件名，等合成（截图）时才解码
        st.bg_image = self.renderer.background(es.bg) if es.bg else None
        st.bg_baked = False
        st.bg_ops = []
        st.overlay = None

        st.sprites = {}
        for sid, sp in enumerate(es.sprites):
            if not sp.image_name and not sp.visible:
                continue
            ours = st.sprite(sid)
            ours.tag = sp.image_name
            ours.x, ours.y = sp.x, sp.y
            ours.visible = bool(sp.visible)
            ours.cell = sp.current_cell
            ours.alpha = 255 if sp.trans < 0 else max(0, min(255, sp.trans))
            # 和 lsp 走同一条懒加载路径：读档 256 个槽位不应当场解码
            ours.image, ours.kind = self.renderer.sprite_image(
                ours.tag, st.trans_mode, ours.cell)
            ours.text = (self.renderer.sprite_text(ours.tag)
                         if ours.kind == "text" else "")

        st.tachi = {}
        for i, name in enumerate(es.tachi):
            if not name:
                continue
            from .state import Sprite
            sp = Sprite(i)
            sp.tag = name
            sp.x, sp.y = es.tachi_x[i], es.tachi_y[i]
            sp.visible = True
            sp.image, sp.kind = self.renderer.sprite_image(
                name, st.trans_mode, 0)
            st.tachi[i] = sp

        st.underline = es.underline
        st.btndef_image = es.btndef
        st.btndef_pixels = (self.renderer.load_image(es.btndef)
                            if es.btndef else None)
        st.audio.midi = es.midi
        st.audio.wave = es.wave
        st.audio.wave_loop = bool(es.wave_loop)
        st.audio.midi_loop = bool(es.midi_loop)
        st.audio.cd_track = es.cd_track
        st.audio.cd_loop = bool(es.cd_loop)
        st.audio.music_loop = bool(es.music_loop)
        st.audio.mp3save = bool(es.mp3save)
        if es.mp3save:
            st.audio.music = es.music
        st.audio.loop_bgm = list(es.loop_bgm)

        # 按钮表 / 选项表**不恢复**：引擎的 loadSaveFile2 只设脚本指针，
        # 这些本来就该由脚本重新注册。清空它们，让后面的重跑去重建 ——
        # 这是"和原版一致"的关键一步（以前存在 JSON 里，反而绕过了这个机制）。
        st.buttons = []
        st.select_links = []
        st.ui_sprites = set()
        st.last_button = 0
        st.btnwait_var = ""

        # 页面：引擎最多 16 页，拿回来当当前页。
        # 打上"来自存档"的标记 —— 脚本会重跑存档那一行，重跑时替换这一页而不是追加。
        if es.pages:
            st.page = Page("", [es.pages[-1]])
            it.page_from_save = True
        else:
            st.page = None
            it.page_from_save = False
        it.history = []
        it.pending_pages = []
        it.page_name = ""

        # 挂起状态清掉，交给 run() 继续跑（和引擎读档后"从那一行接着执行"一致）
        it.waiting = None
        it.finished = False
        it.stop_reason = ""

        # cur_line 是 0-based 且滞后一行，所以续跑点是它的下一行（1-based 即 +1）
        it.pc = self._pc_of_line(es.cur_line + 1)
        it.current_label = it.script.label_of[it.pc] if it.pc < len(it.script.label_of) else ""
        it.story_line = int(es.cur_line) + 1
        it.story_label = it.current_label
        it.cur_stmt = int(es.cur_stmt)

        # 调用栈：引擎的 nest 存的是字节偏移，反查成指令下标
        offsets = self._line_offsets()
        it.stack = []
        it.for_stack = []
        for entry in es.nest:
            if entry.kind == "label":
                pc = self._pc_of_offset(offsets, entry.offset)
                it.stack.append(Frame(return_pc=pc, label=""))
            else:
                pc = self._pc_of_offset(offsets, abs(entry.offset))
                it.for_stack.append({"var": str(entry.var_no), "end": entry.to,
                                     "step": entry.step, "pc": pc})

        # 引擎 loadgameCommand 在读档成功后复位的东西里，我们建模了这三项：
        # saveon / skip / automode 那几项本引擎没有对应状态
        it.break_skip = False            # break_flag = false
        st.text_on = False               # text_on_flag = false

        # `loadgosub`：引擎在 loadSaveFile 成功之后 gosubReal(loadgosub_label,
        # script_h.getCurrent())，返回地址就是刚恢复的脚本位置。这里 pc 已经指向
        # 存档行，`_gosub` 压的 return_pc 正好是它。必须在 nest 栈恢复之后调，
        # 否则这一帧会被覆盖掉。
        it.run_loadgosub()

        self.log.info("已读档：行 %d，%d 个变量，%d 个精灵",
                      es.cur_line, len(es.variables),
                      sum(1 for x in es.sprites if x.image_name or x.visible))

    # -- 脚本行号 ↔ 指令下标 ↔ 字节偏移
    def _line_offsets(self) -> list[int]:
        """每行在脚本文件里的起始字节偏移（引擎 nest 栈存的是这种偏移）。"""
        enc = self.encoding or "gbk"
        out, acc = [0], 0
        for line in self.script.lines[:-1]:
            acc += len(line.encode(enc, "replace")) + 1     # '\n'
            out.append(acc)
        return out

    def _pc_offset(self, offsets: list[int], pc: int) -> int:
        instrs = self.interp.script.instrs
        if not instrs:
            return 0
        pc = min(max(int(pc), 0), len(instrs) - 1)
        line_no = instrs[pc].line_no
        return offsets[line_no - 1] if 0 < line_no <= len(offsets) else 0

    def _pc_of_offset(self, offsets: list[int], offset: int) -> int:
        """脚本字节偏移 → 指令下标（取该偏移所在行的第一条指令）。"""
        line0 = 0
        for i, off in enumerate(offsets):
            if off <= offset:
                line0 = i
            else:
                break
        return self._pc_of_line(line0 + 1)

    def _pc_of_line(self, line_no: int) -> int:
        for i, instr in enumerate(self.interp.script.instrs):
            if instr.line_no >= line_no:
                return i
        return 0

    # ------------------------------------------------------------ 全局变量
    # 引擎的 `gloval.sav`：从 global_border 到 variable_range，每槽一个 int +
    # 一个 NUL 结尾的串。只有 `globalon` 打开时才写（`saveGlovalData` 第一句就判断）。
    def _global_path(self) -> Path:
        # 跟着存档目录走 —— 存档在一处、全局变量在另一处会对不上（通关标记之类）
        return self.save_dir / GLOBAL_FILE

    def _write_globals(self) -> None:
        st = self.interp.state
        if not st.global_on:
            return
        border = int(st.global_border)
        variables: dict[int, tuple[int, str]] = {}
        for slot, num in st.int_slots.items():
            if slot >= border:
                variables[slot] = (int(num), st.str_slots.get(slot, ""))
        for slot, text in st.str_slots.items():
            if text and slot >= border and slot not in variables:
                variables[slot] = (0, text)
        data = build_gloval(variables, border=border,
                            variable_range=int(st.variable_range),
                            encoding=self.encoding)
        p = self._global_path()
        tmp = p.with_suffix(".sav.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def _read_globals(self) -> bool:
        """开局把全局槽位读回来（引擎靠 `gloval.sav`，我们照做）。"""
        st = self.interp.state
        if not st.global_on:
            return False
        p = self._global_path()
        if not p.exists():
            return False
        try:
            values = parse_gloval(p.read_bytes(), border=int(st.global_border),
                                  variable_range=int(st.variable_range),
                                  encoding=self.encoding)
        except Exception as exc:                      # noqa: BLE001
            self.log.warning("全局变量文件读不了：%s", exc)
            return False
        border = int(st.global_border)
        for slot, (num, text) in values.items():
            if slot >= border:
                st.int_slots[slot] = int(num)
                if text:
                    st.str_slots[slot] = text
        return True

    def close(self) -> None:
        """释放归档映射。会话对象之后不应再用。"""
        try:
            self._write_globals()
        except Exception as exc:                      # noqa: BLE001
            self.log.warning("关闭时写全局变量失败：%s", exc)
        try:
            self.files.close()
        except Exception:                             # noqa: BLE001
            pass

    def has_save(self, slot: int = 0) -> bool:
        return self._slot_path(slot).exists()

    def save(self, slot: int = 0) -> str:
        """写原版 `save<N>.dat` —— 引擎能直接读，我们自己也只有这一套格式。"""
        data = build_engine_save(self.to_engine_save(), encoding=self.encoding)
        p = self._slot_path(slot)
        tmp = p.with_suffix(".dat.tmp")            # 原子写：写一半崩掉就是坏档
        tmp.write_bytes(data)
        os.replace(tmp, p)
        self._write_globals()
        self.log.info("已存档 → %s（%d 字节）", p, len(data))
        return str(p)

    def load(self, slot: int = 0, resume: bool = True) -> dict:
        """读档。`resume=True` 时像引擎那样继续跑到下一个等待点。

        游戏内的 `loadgame` 命令要传 `resume=False` —— 它是在解释器执行到一半时
        触发的，继续跑会递归进主循环。
        """
        p = self._slot_path(slot)
        if not p.exists():
            raise FileNotFoundError(f"没有存档: {p}")
        self.load_engine_bytes(p.read_bytes())
        if resume and not self.interp.finished:
            self.interp.run()
        return self.state()


def _apply_rect(img, rect):
    """裁剪（rect = [x, y, w, h]，游戏屏幕像素坐标）。"""
    if not rect:
        return img
    x, y, w, h = (int(v) for v in rect)
    return img.crop((x, y, x + w, y + h))
