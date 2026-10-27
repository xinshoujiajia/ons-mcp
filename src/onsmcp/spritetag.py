"""精灵 tag 解析（`lsp`/`ld`/`bg` 的第一个参数）。

引擎的语法（`ONScripter::parseTaggedString`）：

    tag := [':' mode] ['/' 格数 [',' 每格毫秒...]] [';' 文件名]

    mode := 'a'  alpha 混合（**没有 alpha 通道时用图片右半当 alpha**）
          | 'l'  左上角像素色作透明键（默认）
          | 'r'  右上角像素色作透明键
          | 'c'  copy（完全不透明，忽略图片自带的 alpha）
          | 's'  文字精灵（`:s/字号,字号,抗锯齿;#RRGGBB正文`）
          | 'm'  用另一个文件当遮罩（`:m遮罩.bmp;图片.png`）
          | '#RRGGBB'  直接指定颜色
          | '!N'  调色板编号

没有 ':' 前缀时用全局默认模式（`transmode` 命令设置，默认 leftup）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 引擎的 trans_mode 常量
TRANS_ALPHA = "alpha"
TRANS_TOPLEFT = "leftup"
TRANS_TOPRIGHT = "topright"
TRANS_COPY = "copy"
TRANS_STRING = "string"
TRANS_MASK = "mask"
TRANS_DIRECT = "direct"
TRANS_PALETTE = "palette"

COLOR_RE = re.compile(r"^(#[0-9A-Fa-f]{6})(.*)$", re.S)


@dataclass
class SpriteTag:
    kind: str = "image"            # image | text | solid
    trans: str = ""                # 空 = 用全局默认
    cells: int = 1
    durations: list[int] = field(default_factory=list)
    filename: str = ""
    mask_file: str = ""
    color: str = ""                # #RRGGBB（direct 模式 / 文字精灵首色）
    colors: list[str] = field(default_factory=list)   # 文字精灵里出现的全部颜色
    text: str = ""                 # 文字精灵正文（去掉颜色标记）
    text_raw: str = ""             # 保留颜色标记的原文（渲染用）
    font_size: tuple[int, int] = (0, 0)
    antialias: int = 0
    solid: str = ""                # 纯色块参数（我们的扩展 >w,h,#c1#c2）
    raw: str = ""


def _parse_numbers(text: str) -> list[int]:
    out = []
    for part in text.split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
        elif part == "":
            continue
        else:
            break
    return out


def parse_sprite_tag(tag: str) -> SpriteTag:
    """把 tag 解析成结构化的 SpriteTag。"""
    s = (tag or "").strip()
    spec = SpriteTag(raw=tag)
    if not s:
        spec.kind = "empty"
        return spec

    if s.startswith(">"):                    # 我们的扩展：纯色/渐变块
        spec.kind = "solid"
        spec.solid = s[1:]
        return spec

    if not s.startswith(":"):
        spec.filename = s
        return spec

    body = s[1:].lstrip()
    if not body:
        spec.kind = "empty"
        return spec

    mode_char = body[0]
    if mode_char == "a":
        spec.trans, body = TRANS_ALPHA, body[1:]
    elif mode_char == "l":
        spec.trans, body = TRANS_TOPLEFT, body[1:]
    elif mode_char == "r":
        spec.trans, body = TRANS_TOPRIGHT, body[1:]
    elif mode_char == "c":
        spec.trans, body = TRANS_COPY, body[1:]
    elif mode_char == "s":
        spec.trans, body = TRANS_STRING, body[1:]
    elif mode_char == "m":
        spec.trans = TRANS_MASK
        body = body[1:]
        end = len(body)
        for i, ch in enumerate(body):
            if ch in ";\r\n":
                end = i
                break
        spec.mask_file = body[:end]
        body = body[end:]
    elif mode_char == "#":
        spec.trans = TRANS_DIRECT
        m = COLOR_RE.match(body)
        if m:
            spec.color = m.group(1)
            body = body[7:]
        else:
            body = ""
    elif mode_char == "!":
        spec.trans = TRANS_PALETTE
        m = re.match(r"(\d+)", body)
        body = body[m.end():] if m else ""
    else:
        spec.trans = TRANS_ALPHA      # 未知前缀：引擎当作普通图片

    if spec.trans == TRANS_STRING:
        # :s/字号,字号,抗锯齿;#RRGGBB正文
        if body.startswith("/"):
            body = body[1:]
            m = re.match(r"(\d+(?:,\d+)*)", body)
            if m:
                nums = [int(x) for x in m.group(1).split(",")]
                if len(nums) >= 2:
                    spec.font_size = (nums[0], nums[1])
                elif nums:
                    spec.font_size = (nums[0], nums[0])
                if len(nums) >= 3:
                    spec.antialias = nums[2]
                body = body[m.end():]
        if body.startswith(","):
            body = body[1:]
        if body.startswith(";"):
            body = body[1:]
        # 正文里可以反复出现 #RRGGBB，每出现一次就换一次颜色
        spec.text_raw = body
        m = COLOR_RE.match(body)
        if m:
            spec.color = m.group(1)
            spec.colors = [m.group(1)]
            rest = m.group(2)
            while rest.startswith("#"):
                m2 = COLOR_RE.match(rest)
                if not m2:
                    break
                spec.colors.append(m2.group(1))
                rest = m2.group(2)
            spec.text = rest
        else:
            spec.text = body
        spec.kind = "text"
        return spec

    # 其余模式：先跳到 '/' 或 ';'
    while body and body[0] not in "/;":
        body = body[1:]

    if body.startswith("/"):
        body = body[1:]
        m = re.match(r"(\d+)", body)
        if m:
            spec.cells = max(1, int(m.group(1)))
            body = body[m.end():]
        if body.startswith(","):
            body = body[1:]
            m2 = re.match(r"(\d+(?:,\d+)*)", body)
            if m2:
                spec.durations = [int(x) for x in m2.group(1).split(",")]
                body = body[m2.end():]

    if body.startswith(";"):
        spec.filename = body[1:]
    return spec
