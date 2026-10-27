"""脚本文件加载：格式识别、去混淆、编码探测、首行配置解析。

引擎能吃的脚本形态（`ScriptHandler::readScript`）：

| 文件 | 处理 |
|---|---|
| `0.txt`（+ `1.txt`…`99.txt`） | 明文，多个文件按序拼接 |
| `00.txt`（+ `01.txt`…） | 同上，双位数命名 |
| `nscript.dat` | 每字节 `^ 0x84` |
| `nscr_sec.dat` | 每字节 `^ magic[i % 5]`，magic = 79 57 0d 80 04 |
| `nscript.___` | 需要用 EXE 里的 key table，本引擎不支持（要 `--key-exe`） |

首行若是 `;` 开头的注释，它其实是**配置行**（`readConfiguration`）：

    ;$S1280,720G1500      → 分辨率 1280×720，全局变量边界 1500
    ;mode800,value500     → 800×600，全局变量边界 500
    ;mode400 / mode320    → 400×300 / 320×240
    ;v4096                → 变量总数上限

`global_variable_border` 决定 `%0…%N-1` 是全局变量（存读档保留），
`variable_range` 是变量总数上限。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import encoding as enc_mod
from .files import GameFiles
from .log import get_logger

log = get_logger("script")

NS_MAGIC = bytes((0x79, 0x57, 0x0D, 0x80, 0x04))
NS_XOR = 0x84


class ScriptFormatError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


@dataclass
class ScriptConfig:
    width: int = 640
    height: int = 480
    variable_range: int = 4096
    global_border: int = 200

    def as_dict(self) -> dict:
        return {"width": self.width, "height": self.height,
                "variable_range": self.variable_range,
                "global_border": self.global_border}


@dataclass
class LoadedScript:
    text: str
    encoding: str
    detail: dict
    source: str                       # 人读的来源说明，如 "nscript.dat (XOR 0x84)"
    config: ScriptConfig = field(default_factory=ScriptConfig)
    files: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ 去混淆
def deobfuscate(raw: bytes, fmt: str) -> bytes:
    if fmt == "nscript.dat":
        return bytes(b ^ NS_XOR for b in raw)
    if fmt == "nscr_sec.dat":
        return bytes(b ^ NS_MAGIC[i % 5] for i, b in enumerate(raw))
    if fmt == "nscript.___":
        raise ScriptFormatError(
            "nscript.___ 需要游戏 EXE 里的 key table 才能解密",
            hint="先用原版引擎的 --key-exe 导出，或改用解包后的 0.txt / nscript.dat")
    return raw


# ------------------------------------------------------------------ 配置行
def _read_int(s: str, i: int) -> tuple[int, int]:
    j = i
    while j < len(s) and s[j].isdigit():
        j += 1
    return (int(s[i:j]) if j > i else 0), j


def parse_config_header(text: str) -> ScriptConfig:
    cfg = ScriptConfig()
    first = text.split("\n", 1)[0].strip()
    if not first.startswith(";"):
        return cfg
    body = first[1:].lstrip()
    if body.startswith("$"):                     # ";$S..." 这种带 $ 的写法
        body = body[1:].lstrip()

    i, n = 0, len(body)
    while i < n:
        ch = body[i]
        if ch in " \t,":
            i += 1
            continue
        if body.startswith("mode", i):
            i += 4
            val, i = _read_int(body, i)
            cfg.width, cfg.height = {800: (800, 600), 400: (400, 300),
                                     320: (320, 240)}.get(val, (cfg.width, cfg.height))
        elif body.startswith("value", i) or ch in "gG":
            i += 5 if ch not in "gG" else 1
            cfg.global_border, i = _read_int(body, i)
        elif ch in "vV":
            i += 1
            cfg.variable_range, i = _read_int(body, i)
        elif ch in "sS":
            i += 1
            w, i = _read_int(body, i)
            j = i
            while j < n and body[j] in ", \t":
                j += 1
            h, j = _read_int(body, j)
            if w and h:
                cfg.width, cfg.height = w, h
                i = j
        elif ch in "lL":
            i += 1
            _, i = _read_int(body, i)
        else:
            break
    return cfg


# ------------------------------------------------------------------ 定位
def find_script(files: GameFiles) -> tuple[str, str]:
    """返回 (格式名, 磁盘路径或归档名)。顺序照抄引擎。"""
    for name in ("0.txt", "00.txt", "nscr_sec.dat", "nscript.___", "nscript.dat"):
        if files.path(name) is not None:
            return name, name
    # 归档里的脚本（少数移植版会把 0.txt 塞进 nsa）
    for name in ("0.txt", "nscript.dat"):
        if any(a.has(name) for a in files.archives):
            return name, name
    raise ScriptFormatError(
        f"目录下没有 0.txt / 00.txt / nscript.dat: {files.game_dir}",
        hint="确认这是解包后的 ONS 游戏目录；未解包的需要先处理 nsa")


def _read_plain_series(files: GameFiles, first: str) -> tuple[bytes, list[str]]:
    """0.txt 系列：引擎会把 0.txt、1.txt…99.txt 依序拼起来（找不到就试 01.txt）。"""
    parts: list[bytes] = []
    names: list[str] = []
    data = files.read(first)
    if data is None:
        raise ScriptFormatError(f"读不到 {first}")
    parts.append(data)
    names.append(first)
    if first in ("0.txt", "00.txt"):
        for i in range(1, 100):
            for cand in (f"{i}.txt", f"{i:02d}.txt"):
                chunk = files.read(cand)
                if chunk is not None:
                    parts.append(chunk)
                    names.append(cand)
                    break
    return b"".join(parts), names


def load_script(files: GameFiles) -> LoadedScript:
    fmt, _ = find_script(files)

    if fmt.endswith(".txt"):
        raw, names = _read_plain_series(files, fmt)
        text_bytes = raw
        source = fmt if len(names) == 1 else f"{fmt} + {len(names) - 1} 个分片"
    else:
        raw = files.read(fmt)
        if raw is None:
            raise ScriptFormatError(f"读不到 {fmt}")
        text_bytes = deobfuscate(raw, fmt)
        names = [fmt]
        source = f"{fmt} ({'XOR 0x84' if fmt == 'nscript.dat' else 'magic XOR'})"

    encoding, detail = enc_mod.detect(text_bytes)
    text = text_bytes.decode(encoding, errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    config = parse_config_header(text)
    log.info("脚本 %s：编码 %s，%d 字节，%d 行，分辨率 %dx%d，变量上限 %d/%d",
             source, encoding, len(text_bytes), text.count("\n") + 1,
             config.width, config.height, config.variable_range, config.global_border)
    return LoadedScript(text=text, encoding=encoding, detail=detail,
                        source=source, config=config, files=names)


# ------------------------------------------------------------------ 兼容入口
def load_from_path(path: str | Path) -> LoadedScript:
    """给不经过 GameFiles 的场景（测试、单文件调试）用。"""
    p = Path(path)
    files = GameFiles(p.parent)
    fmt = p.name.lower()
    if fmt.endswith(".txt"):
        text_bytes = p.read_bytes()
        source = p.name
    else:
        text_bytes = deobfuscate(p.read_bytes(), fmt)
        source = fmt
    encoding, detail = enc_mod.detect(text_bytes)
    text = text_bytes.decode(encoding, errors="replace").lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return LoadedScript(text=text, encoding=encoding, detail=detail,
                        source=source, config=parse_config_header(text), files=[p.name])
