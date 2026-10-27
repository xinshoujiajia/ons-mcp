"""MCP 服务入口（stdio）。

工具集：start / sessions / close / text / screenshot / click /
choices / choose / buttons / save / load。

约定：
  * 返回值一律是 JSON 字符串或纯文本，不用富对象，方便 agent 直接读
  * stdout 只走协议帧，日志一律走 stderr（见 onsmcp.log）
  * 任何工具出错都返回 `{"error": {...}}` 而不是抛异常——
    MCP 客户端看到的是内容，agent 能自己读错误并纠正参数

多会话：`start(session="名字")` 可以开多个游戏，之后每个工具都能传
`session="名字"` 指定操作哪一个；不传就用"最近一次 start 的那个"。
"""
from __future__ import annotations

import functools
import json
import logging
from pathlib import Path
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import __version__
from .log import get_logger
from .session import GameSession

log = get_logger("server")

server = MCPServer(
    name="ons-mcp",
    version=__version__,
    instructions=(
        "ONS（NScripter/ONScripter）视觉小说的游玩引擎。"
        "先 start 指定游戏目录，之后用 text 读当前台词、screenshot 看画面、"
        "click 推进对话或点击坐标（click 的返回值里就带当前状态）。"
        "遇到分支时用 choices 看选项、用 choose 选一项。"
        "同时玩多个游戏时用 start(session=...) 命名，其余工具传同样的 session。"
    ),
)

_sessions: dict[str, GameSession] = {}
_current: str = ""


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


# 常见异常 → 给 agent 的一句话提示，让它知道下一步该怎么改
_HINTS = {
    "FileNotFoundError": "检查 game_dir 是否是游戏目录（里面应有 0.txt / nscript.dat / *.nsa）",
    "IsADirectoryError": "路径是目录，这里需要文件",
    "PermissionError": "文件被占用或无权限；存档写不进去时可以设 ONSMCP_SAVE_DIR 换个目录",
    "UnicodeDecodeError": "脚本编码可能不是 GBK/Shift-JIS，可用 ONSMCP_ENCODING 指定",
    "MemoryError": "内存不足，调小 start(cache_mb=...) 再试",
    "SaveDirError": "换一个可写目录，或清掉 ONSMCP_SAVE_DIR 让存档回到游戏目录",
}

# MCP 工具面的槽位上限。引擎自己不校验（`sprintf("save%d.dat", no)` 照写），
# 槽位数由脚本的 `savenumber` 决定；这里是给 agent 的护栏，不是引擎语义。
MAX_SAVE_SLOT = 999


def _check_slot(slot: int) -> int:
    """校验存档槽位。只拦 MCP 入口 —— 脚本里的 `savegame`/`loadgame` 不拦（引擎不拦）。"""
    if isinstance(slot, bool) or not isinstance(slot, int):
        raise ToolError(f"槽位必须是整数，收到 {type(slot).__name__}",
                        hint="示例：save(slot=0) / load(slot=1)")
    if not 0 <= slot <= MAX_SAVE_SLOT:
        raise ToolError(f"槽位 {slot} 超出范围（0..{MAX_SAVE_SLOT}）",
                        hint="槽位是 0..999 的整数；游戏内存档界面一般用 1..9")
    return slot


class ToolError(Exception):
    """业务层可抛的、带提示的错误。"""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


def _error_payload(exc: Exception) -> dict:
    name = type(exc).__name__
    hint = getattr(exc, "hint", "") or _HINTS.get(name, "")
    payload = {"type": name, "message": str(exc)}
    if hint:
        payload["hint"] = hint
    if isinstance(exc, ToolError):
        payload["type"] = "ToolError"
    return payload


def _safe(fn: Callable) -> Callable:
    """工具最外层兜底：异常转结构化 JSON，同时把堆栈写进 stderr。"""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:                       # noqa: BLE001
            log.error("工具 %s 失败：%s: %s", fn.__name__,
                      type(exc).__name__, exc,
                      exc_info=log.isEnabledFor(logging.DEBUG))
            return _j({"error": _error_payload(exc)})

    return wrapper


def _require(name: str = "") -> GameSession:
    key = name or _current
    if not key:
        raise ToolError("还没 start。先调用 start(game_dir=...)。",
                        hint="例如 start(game_dir=\"D:/game/某个ONS游戏\")")
    if key not in _sessions:
        raise ToolError(f"没有名为 {key!r} 的会话",
                        hint=f"现有会话：{sorted(_sessions) or '（空）'}")
    return _sessions[key]


# ------------------------------------------------------------------ 会话管理

@server.tool(description="打开游戏目录并初始化，跑到第一个等待输入的点，返回初始状态。"
                        "session 命名会话（默认 default）。"
                        "hooks=true 时等待点变成游戏内菜单（textbtnwait），"
                        "右键可开存读档/回想/设置。"
                        "width/height 传 0 表示用脚本自带的分辨率。"
                        "timeout_s 是单次操作的墙钟上限（默认 10 秒）。")
@_safe
def start(game_dir: str, label: str | None = None, width: int = 0,
          height: int = 0, cache_mb: int = 320, hooks: bool = False,
          timeout_s: float | None = None, session: str = "default") -> str:
    global _current
    log.info("start[%s]: %s label=%s hooks=%s cache=%sMB",
             session, game_dir, label or "start", hooks, cache_mb)
    old = _sessions.get(session)
    if old is not None:
        old.close()
    _sessions[session] = GameSession(game_dir, start_label=label or "start",
                                     width=width, height=height, cache_mb=cache_mb,
                                     run_text_hooks=hooks, timeout_s=timeout_s)
    _current = session
    st = _sessions[session].start()
    st["session"] = session
    return _j(st)


@server.tool(description="列出所有会话及其状态摘要（游戏目录、剧情位置、是否在等待输入）。")
@_safe
def sessions() -> str:
    out = []
    for name, s in _sessions.items():
        st = s.state()
        out.append({"session": name, "current": name == _current,
                    "game_dir": str(s.game_dir),
                    "label": st["label"], "line": st["line"],
                    "waiting": st["waiting"], "resolution": st["resolution"]})
    return _j(out)


@server.tool(description="关闭一个会话并释放它打开的归档。不传就用当前会话。")
@_safe
def close(session: str = "") -> str:
    global _current
    key = session or _current
    if key not in _sessions:
        raise ToolError(f"没有名为 {key!r} 的会话", hint=f"现有会话：{sorted(_sessions)}")
    _sessions.pop(key).close()
    if _current == key:
        _current = next(iter(_sessions), "")
    return _j({"closed": key, "current": _current})


# ------------------------------------------------------------------ 游玩

@server.tool(description="当前屏幕上的文本（已去掉控制符）。含说话人时形如「【名字】：台词」。"
                        "history=N 时在前面附带最近 N 句台词。")
@_safe
def text(history: int = 0, session: str = "") -> str:
    return _require(session).text(history=history)


@server.tool(description="取当前画面。rect 是游戏屏幕上的矩形区域 [x, y, w, h]，不传则截整屏。"
                        "format='image'（默认）返回 MCP 图片块，'base64' 返回 base64 文本 JSON。"
                        "两种模式都不写文件。")
@_safe
def screenshot(rect: list[int] | None = None,
               format: str = "image",
               session: str = ""):
    s = _require(session)
    fmt = (format or "image").lower()

    if rect is not None and len(rect) != 4:
        raise ToolError(f"rect 应为 [x, y, w, h] 四个数字，收到 {rect!r}",
                        hint="例：[980, 310, 145, 52]")

    # 全程在内存里完成，不落盘
    data = s.screenshot_bytes(rect=rect)
    if fmt == "base64":
        import base64
        b64 = base64.b64encode(data).decode("ascii")
        return _j({"format": "base64", "media_type": "image/png",
                   "data": b64, "bytes": len(data)})
    if fmt == "image":
        from mcp.server.mcpserver.utilities.types import Image
        return Image(data=data, format="png")
    raise ToolError(f"format 只能是 image / base64，收到 {format!r}",
                    hint="image 是默认且推荐的")


@server.tool(description="推进。不传坐标=继续对话/翻页；传坐标=点击该位置（选项/按钮）。"
                        "button 可选 left/right/wheelup/wheeldown/esc/space，右键开游戏内菜单。"
                        "等待点是按钮时（waiting='btn'）不传坐标不会前进，"
                        "要先用 buttons() 取矩形再带坐标点。"
                        "返回当前状态，另带 changes 说明这一下改了什么："
                        "screen 是总开关（任一变化），text/bg/tachi/sprites 细分到层，"
                        "并给出 bg_image（当前背景）、tachi_images（左中右立绘）、"
                        "sprite_count（可见精灵数）、sprites_added/sprites_removed（换掉的图，最多各 8 个）。"
                        "changes.screen 为 false 说明画面没动，不用再截图。")
@_safe
def click(x: int | None = None, y: int | None = None, button: str = "left",
          session: str = "") -> str:
    s = _require(session)
    if button not in s.BUTTON_CODES:
        raise ToolError(f"button 只能是 {sorted(s.BUTTON_CODES)}，收到 {button!r}",
                        hint="默认 left；开游戏内菜单用 right")
    return _j(s.click(x, y, button=button))


@server.tool(description="当前选项：序号、文本、对应按钮编号与可点击矩形。"
                        "不在选项界面时返回 [] 并附 hint。")
@_safe
def choices(session: str = "") -> str:
    s = _require(session)
    out = s.choices()
    if out:
        return _j(out)
    st = s.state()
    return _j({"choices": [], "hint": _hint_for_state(st)})


def _hint_for_state(st: dict) -> str:
    """根据当前状态给 agent 一句"接下来该干嘛"。"""
    if st.get("in_hook"):
        return ("当前在游戏内菜单的等待点（textbtnwait）。"
                "用 click(x,y) 点菜单项，或 click(button='right') 关闭菜单。")
    if st.get("waiting") == "text":
        if st.get("has_more_pages"):
            return "当前这一句还有没翻完的页，直接 click() 即可继续。"
        return "当前在等玩家推进，直接 click() 继续对话。"
    if st.get("waiting") == "btn":
        return ("当前在等按钮点击。用 buttons() 列出可点区域后 click(x,y)，"
                "或在选项界面用 choose(index)。")
    if st.get("finished"):
        return "脚本已经结束，可以 save() 或重新 start()。"
    return "当前没有等待输入，先 click() 推进看看会到哪里。"


@server.tool(description="按序号选择当前选项（等价于点击该项中心），返回点击结果与最新状态。"
                        "不在选项界面时返回 error 与 hint。")
@_safe
def choose(index: int, session: str = "") -> str:
    s = _require(session)
    out = s.choose(index)
    if "error" in out:
        out["hint"] = _hint_for_state(s.state())
    return _j(out)


@server.tool(description="列出当前所有可点击按钮（编号 / 类型 / 矩形）。"
                        "rect 是游戏屏幕上的矩形区域 [x, y, w, h]。")
@_safe
def buttons(session: str = "") -> str:
    return _j(_require(session).buttons())


@server.tool(description="存档到指定槽位。写的是原版 save<N>.dat（ONS 2.8），原版引擎可直接读。"
                        "返回 {slot, path, size}：槽位、文件绝对路径、字节数。")
@_safe
def save(slot: int = 0, session: str = "") -> str:
    s = _require(session)
    slot = _check_slot(slot)
    p = Path(s.save(slot))
    return _j({"slot": slot, "path": str(p), "size": p.stat().st_size})


@server.tool(description="从指定槽位读档（原版 save<N>.dat）。读档后会像引擎一样继续跑到下一个等待点。"
                        "返回当前状态（与 click 同构，额外带 slot）。")
@_safe
def load(slot: int = 0, session: str = "") -> str:
    s = _require(session)
    slot = _check_slot(slot)
    if not s.has_save(slot):
        raise ToolError(f"槽位 {slot} 没有存档",
                        hint="先用 save(slot=...) 存一次，或换一个槽位")
    st = s.load(slot)
    st["slot"] = slot
    return _j(st)


# ------------------------------------------------------------------ 入口

def main() -> None:
    log.info("ons-mcp %s 启动（stdio）", __version__)
    try:
        server.run(transport="stdio")
    except KeyboardInterrupt:
        log.info("收到中断，退出")
    except Exception as exc:                            # noqa: BLE001
        log.error("服务异常退出：%s: %s", type(exc).__name__, exc)
        raise
    finally:
        for s in _sessions.values():
            s.close()


if __name__ == "__main__":
    main()
