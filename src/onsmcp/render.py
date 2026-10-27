"""渲染层：按引擎的 trans_mode 规则合成精灵。

引擎的 alpha 构建（`AnimationInfo::setupImageAlpha`）：

| trans_mode | 规则 |
|---|---|
| `alpha`（`:a`，两款游戏全局都用这个） | 图片**有** alpha 通道 → 用自带 alpha；**没有** → **用图片右半当 alpha**，且宽度减半，alpha = 255 − 掩码的红色通道 |
| `leftup`（`:l`，默认） | 把左上角像素的颜色当透明键（该色 → 全透明，其余 → 全不透明） |
| `topright`（`:r`） | 同上，取右上角像素 |
| `copy`（`:c`） | 完全不透明，连图片自带的 alpha 都不要 |
| `mask`（`:m遮罩.bmp`） | 用另一个文件当遮罩，alpha = 255 − 遮罩红色通道（横向平铺） |
| `direct`（`#RRGGBB`） | 指定颜色作透明键 |

「右半当 alpha」这条是 NScripter 手册里写明的：
    > alpha模式下，如果没有alpha通道，会用图片右半作为alpha通道。
Ever17 的选项按钮 `esystem/csel_btn.jpg` 就是这种图：左半是按钮画面、
右半是遮罩（黑色=不透明、白色=透明），中间的绿色条因此被遮掉了。
"""
from __future__ import annotations

import io
import os
import re
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

from .files import GameFiles
from .log import get_logger
from .spritetag import (TRANS_ALPHA, TRANS_COPY, TRANS_DIRECT, TRANS_MASK,
                         TRANS_PALETTE, TRANS_STRING, TRANS_TOPLEFT,
                         TRANS_TOPRIGHT, SpriteTag,
                         parse_sprite_tag as parse_sprite_spec)
from .state import State, WindowConfig

COLOR_RE = re.compile(r"^(#[0-9A-Fa-f]{6})(.*)$", re.S)


def parse_sprite_tag(tag: str):
    """旧接口：返回 (kind, payload)。新代码请用 spritetag.parse_sprite_spec。"""
    spec = parse_sprite_spec(tag)
    if spec.kind == "solid":
        return "solid", spec.solid
    if spec.kind == "text":
        return "text", spec.text
    if spec.kind == "image":
        return "image", spec.filename
    return "empty", None


class DeferredImage:
    """延迟解码的图片句柄（`bg` / `lsp` / `ld` 用）。

    为什么要有这一层：万华镜2 的开场动画在**一个 click** 里连发 120 多次 `lsp`，
    每次一张 1280×720 的 JPG。边发边解码会把这一个 click 拖到 0.64s，还会把
    320MB 的 LRU 整块冲掉——而 agent 真正能看到的只有最后一帧，中间 118 张白解。

    改成"只记文件名、合成画面时才解码"之后，同一个 click 只剩最后一两帧要解码。

    两个必须记住的点：
      * **透明模式是快照**。引擎在载入时就按当时的全局 `trans_mode` 建好了 alpha
        （`setupAnimationInfo`），之后脚本再 `transmode` 也不会回头改已载入的精灵。
      * **尺寸可以单独算**。`.size` 只读文件头（`Image.open` 不解码像素），所以
        `getspsize` / `spbtn` 命中区这类"要尺寸不要像素"的地方依然准确；
        只有 `materialize()` 才真解码。
    """

    __slots__ = ("spec", "mode", "cell", "raw", "_size", "_img", "_failed", "_r")

    def __init__(self, renderer: "Renderer", spec: SpriteTag, mode: str,
                 cell: int = 0, raw: bool = False):
        self._r = renderer
        self.spec = spec                  # 解析好的 tag（文件名 / 格数都在里面）
        self.mode = mode                  # 载入那一刻的透明模式（快照）
        self.cell = int(cell or 0)
        self.raw = raw                    # True = 不套透明模式（背景走这条路）
        self._size: tuple[int, int] | None = None
        self._img = None
        self._failed = False

    # ---------------------------------------------------------------- 尺寸
    @property
    def size(self) -> tuple[int, int]:
        if self._size is None:
            self._size = self._r.deferred_size(self)
        return self._size

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    # ---------------------------------------------------------------- 解码
    @property
    def decoded(self) -> bool:
        return self._img is not None

    def materialize(self):
        """真解码（幂等）。文件读不到 / 解不开时返回 None。"""
        if self._img is None and not self._failed:
            self._img = self._r.materialize(self)
            self._failed = self._img is None
        return self._img

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        tag = "bg" if self.raw else f"lsp({self.mode})"
        return f"<Deferred {tag} {self.spec.filename}>"


class Renderer:
    """合成器。资源统一走 GameFiles（磁盘 → .nsa 归档）。"""

    # 游戏自带字体缺字时的兜底顺序（Windows 优先，再 Linux/macOS）
    SYSTEM_FONTS = [
        r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhl.ttc",
        r"C:/Windows/Fonts/simhei.ttf", r"C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]

    def __init__(self, game_dir: str | Path, width: int = 0, height: int = 0,
                 font_file: str | None = None, cache_budget_mb: int = 320,
                 max_image_mb: int = 96, files: GameFiles | None = None):
        self.game_dir = Path(game_dir)
        # 0 = 还没定，等脚本首行的 mode/$S 配置来决定
        self.width = width or 640
        self.height = height or 480
        self.files = files or GameFiles.open(self.game_dir)
        self._explicit_font = font_file
        self.font_path: Path | None = None
        self.font_source = ""              # 人读说明：用的是哪个字体
        self._sample_text = ""
        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}
        # 按字节预算的 LRU：游戏里 CG/立绘成千上万张，无上限的字典必然 OOM
        self._image_cache: "OrderedDict[str, Image.Image]" = OrderedDict()
        self._cache_bytes = 0
        self.cache_budget = cache_budget_mb * 1024 * 1024
        # 单张解码后的上限（多格条图整条解码很吃内存，超过就整张放弃）
        self.max_image_bytes = max_image_mb * 1024 * 1024
        self._missing: set[str] = set()
        self._skipped_big: set[str] = set()
        # 源文件有没有 alpha 通道（PNG 一律算有，和引擎一致）
        self._has_alpha_map: dict[str, bool] = {}
        # 懒加载用：文件头缓存（宽高 + 有没有 alpha）与"文件在不在"缓存
        self._probe_cache: dict[str, tuple[int, int, bool] | None] = {}
        self._present: dict[str, bool] = {}
        self.stat_deferred = 0             # 建了多少个延迟句柄
        self.stat_deferred_decoded = 0     # 其中最后真解码的
        self.stat_decoded = 0
        self.stat_skipped = 0
        self.stat_halved = 0               # 统计"右半当 alpha"的图

    # ------------------------------------------------------------ 字体
    def set_sample_text(self, text: str) -> None:
        """给一段剧本样本，用来判断自带字体是否真的覆盖这些字。"""
        self._sample_text = text[:40000]

    def _materialize(self, rel: str) -> Path | None:
        """字体在归档里时得先落成临时文件——PIL 要按路径反复打开。"""
        p = self.files.path(rel)
        if p is not None:
            return p
        for cand in ("default.ttf", "DEFAULT.TTF", "default.TTF"):
            data = self.files.read(cand)
            if data:
                import hashlib
                import tempfile

                h = hashlib.md5(data).hexdigest()[:12]
                out = Path(tempfile.gettempdir()) / f"onsmcp_font_{h}.ttf"
                if not out.exists():
                    out.write_bytes(data)
                return out
        return None

    @staticmethod
    def _covers(font: ImageFont.FreeTypeFont, chars: list[str]) -> bool:
        """字形覆盖粗判：若几个不同汉字渲染出的点阵完全一样，说明都是豆腐块。

        注意别用 `font.getmask().tobytes()` —— 新版 Pillow 的 getmask 返回
        ImagingCore，没有 tobytes；画到位图上再取字节最稳。
        """
        try:
            stamps = []
            for c in chars:
                img = Image.new("L", (40, 40))
                ImageDraw.Draw(img).text((2, 2), c, font=font, fill=255)
                data = img.tobytes()
                if not any(data):
                    return False
                stamps.append(data)
        except Exception:
            return False
        return len(set(stamps)) > 1

    def _choose_font(self) -> None:
        if self.font_path is not None:
            return
        sample = [c for c in dict.fromkeys(self._sample_text) if ord(c) > 0x2E80][:6]
        candidates: list[tuple[Path, str]] = []

        if self._explicit_font:
            p = self._materialize(self._explicit_font)
            if p:
                candidates.append((p, f"指定字体 {self._explicit_font}"))
        env_font = os.environ.get("ONSMCP_FONT")
        if env_font and Path(env_font).is_file():
            candidates.append((Path(env_font), "环境变量 ONSMCP_FONT"))
        p = self._materialize("default.ttf")
        if p:
            candidates.append((p, "游戏自带 default.ttf"))
        for cand in self.SYSTEM_FONTS:
            if Path(cand).is_file():
                candidates.append((Path(cand), f"系统字体 {Path(cand).name}"))

        for path, why in candidates:
            try:
                probe = ImageFont.truetype(str(path), 24)
            except Exception:
                continue
            if not sample or self._covers(probe, sample):
                self.font_path, self.font_source = path, why
                return
            get_logger("render").warning("%s 缺字，换下一个候选", why)

        self.font_path = candidates[0][0] if candidates else None
        self.font_source = candidates[0][1] if candidates else "PIL 内置字体"

    def font(self, size: int) -> ImageFont.FreeTypeFont:
        self._choose_font()
        if size not in self._font_cache:
            try:
                if self.font_path is None:
                    raise OSError("没有可用字体")
                self._font_cache[size] = ImageFont.truetype(str(self.font_path), size)
            except Exception:
                self._font_cache[size] = ImageFont.load_default()
        return self._font_cache[size]

    def cache_stats(self) -> dict:
        return {
            "entries": len(self._image_cache),
            "mb": round(self._cache_bytes / 1024 / 1024, 1),
            "budget_mb": round(self.cache_budget / 1024 / 1024, 1),
            "decoded": self.stat_decoded,
            "deferred": self.stat_deferred,
            "deferred_decoded": self.stat_deferred_decoded,
            "skipped_too_big": self.stat_skipped,
            "halved_by_mask": self.stat_halved,
            "font": self.font_source or "(未选)",
        }

    def _cache_get(self, key: str) -> Image.Image | None:
        img = self._image_cache.get(key)
        if img is not None:
            self._image_cache.move_to_end(key)
        return img

    def _cache_put(self, key: str, img: Image.Image) -> Image.Image:
        size = img.width * img.height * 4
        if size > self.cache_budget // 2:
            # 单张就超过预算一半：用，但不进缓存（否则会把别的全挤掉）
            return img
        old = self._image_cache.pop(key, None)
        if old is not None:
            self._cache_bytes -= old.width * old.height * 4
        while self._image_cache and self._cache_bytes + size > self.cache_budget:
            _, evicted = self._image_cache.popitem(last=False)
            self._cache_bytes -= evicted.width * evicted.height * 4
        self._image_cache[key] = img
        self._cache_bytes += size
        return img

    @staticmethod
    def _size_of(data: bytes) -> tuple[int, int] | None:
        """只读文件头拿尺寸，不解码像素——大条图因此可以“看一眼就放弃”。"""
        try:
            with Image.open(io.BytesIO(data)) as im:
                return im.size
        except Exception:
            return None

    @staticmethod
    def _decode(data: bytes) -> tuple[Image.Image | None, bool]:
        """解码并返回 (RGBA 图, 源文件是否带 alpha 通道)。

        引擎的判定：PNG 一律当作有 alpha（`IMG_isPNG`），其它格式看有没有 alpha 通道。
        我们解码后统一转成 RGBA，所以必须在转换**之前**把源格式记下来。
        """
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception:
            return None, False
        fmt = (img.format or "").lower()
        mode = img.mode
        has = (fmt == "png" or mode in ("RGBA", "LA")
               or (mode == "P" and "transparency" in img.info))
        return img.convert("RGBA"), has

    def _load_raw(self, rel: str, cache: bool = True) -> Image.Image | None:
        """解码一张图。`cache=False` 用于长条动画图——那种图解码完就该丢。"""
        if not cache:
            data = self.files.read(rel)
            if data is None:
                return None
            size = self._size_of(data)
            if size is None:
                return None
            if size[0] * size[1] * 4 > self.max_image_bytes:
                self._skipped_big.add(rel)
                self.stat_skipped += 1
                return None
            img, has = self._decode(data)
            if img is not None:
                self.stat_decoded += 1
                self._has_alpha_map[rel.lower()] = has
            return img
        return self.load_image(rel)

    def load_image(self, rel: str) -> Image.Image | None:
        rel = rel.strip().replace("\\", "/")
        if not rel:
            return None
        cached = self._cache_get(rel)
        if cached is not None:
            return cached
        if rel in self._missing or rel in self._skipped_big:
            return None

        data = self.files.read(rel)
        if data is None:
            self._missing.add(rel)
            return None

        size = self._size_of(data)
        if size is None:
            self._missing.add(rel)
            return None
        if size[0] * size[1] * 4 > self.max_image_bytes:
            # 典型例子：60 格 × 1280 的花瓣条图，整条解码要 200MB+
            self._skipped_big.add(rel)
            self.stat_skipped += 1
            return None

        img, has = self._decode(data)
        if img is None:
            self._missing.add(rel)
            return None
        self._has_alpha_map[rel.lower()] = has
        self.stat_decoded += 1
        return self._cache_put(rel, img)

    # ------------------------------------------------------------ 懒加载
    def has_file(self, rel: str) -> bool:
        """文件在不在（磁盘或归档）。只查目录项，**不读内容**。"""
        key = (rel or "").strip().replace("\\", "/")
        if not key:
            return False
        got = self._present.get(key)
        if got is None:
            got = self.files.has(key)
            self._present[key] = got
        return got

    def _probe(self, rel: str) -> tuple[int, int, bool] | None:
        """(宽, 高, 源文件带不带 alpha) —— 只读文件头，**不解码像素**。

        引擎的 alpha 判定照抄（`IMG_isPNG`）：PNG 一律算有 alpha，其它格式看
        有没有 alpha 通道。`Image.open` 拿 `mode`/`info` 不需要 `load()`。
        """
        key = (rel or "").strip().replace("\\", "/")
        if key in self._probe_cache:
            return self._probe_cache[key]
        data = self.files.read(key) if key else None
        out = None
        if data is not None:
            try:
                with Image.open(io.BytesIO(data)) as im:
                    fmt = (im.format or "").lower()
                    mode = im.mode
                    has = (fmt == "png" or mode in ("RGBA", "LA")
                           or (mode == "P" and "transparency" in im.info))
                    out = (im.size[0], im.size[1], has)
            except Exception:
                out = None
        self._probe_cache[key] = out
        if out is not None:
            # 顺手把 alpha 判定喂给 apply_trans_mode，省得它再猜一次
            self._has_alpha_map.setdefault(key.lower(), out[2])
        return out

    def deferred_size(self, d: DeferredImage) -> tuple[int, int]:
        """延迟句柄的**显示尺寸**：和真解码后 `.size` 必须完全一致。

        「右半当 alpha」会把宽度减半（`alpha` 模式下源图没有 alpha 通道时），
        条图还要再除以格数——这两步都得在这里复现，否则 `getspsize` 和
        按钮命中区会偏。
        """
        probe = self._probe(d.spec.filename)
        if probe is None:
            return (0, 0)
        w, h, has_alpha = probe
        if d.raw:
            return (w, h)
        cells = max(d.spec.cells, 1)
        mode = d.mode or TRANS_TOPLEFT
        if mode == TRANS_ALPHA and not has_alpha:
            w = (w // cells) // 2
        elif cells > 1:
            w //= cells
        if w <= 0:                       # 图比格数还窄这种破图：退回原宽
            w = probe[0]
        return (w, h)

    def materialize(self, d: DeferredImage):
        """把延迟句柄变成真图（解码 + 透明模式 + 取格）。"""
        spec = d.spec
        # 长条动画图解码完就丢，不进 LRU（否则一张 60 格的条图能占几百 MB）
        raw = self._load_raw(spec.filename, cache=spec.cells <= 1)
        if raw is None:
            return None
        img = raw if d.raw else self.apply_trans_mode(raw, spec, d.mode)
        if spec.cells > 1:
            img = self._take_cell(img, spec.cells, d.cell)
        self.stat_deferred_decoded += 1
        return img

    def defer_sprite(self, tag: str,
                     default_trans: str = TRANS_TOPLEFT,
                     cell: int = 0) -> DeferredImage | None:
        """图片型精灵 → 延迟句柄。文件不存在时返回 None（和以前"载入失败"一致）。"""
        spec = parse_sprite_spec(tag)
        if spec.kind != "image" or not self.has_file(spec.filename):
            return None
        mode = spec.trans or default_trans or TRANS_TOPLEFT
        self.stat_deferred += 1
        return DeferredImage(self, spec, mode, cell)

    def background(self, name: str) -> DeferredImage | None:
        """背景图 → 延迟句柄（不套透明模式，引擎的 bg 是直接贴）。"""
        spec = parse_sprite_spec(name)
        if not spec.filename or not self.has_file(spec.filename):
            return None
        self.stat_deferred += 1
        return DeferredImage(self, spec, TRANS_COPY, raw=True)

    @staticmethod
    def image_of(obj):
        """句柄 → 真图。句柄会就地缓存结果，所以重复合成只解码一次。"""
        if obj is None:
            return None
        if isinstance(obj, DeferredImage):
            return obj.materialize()
        return obj

    def sprite_image(self, tag: str, default_trans: str = TRANS_TOPLEFT,
                     cell: int = 0) -> tuple[object, str]:
        """按 tag 取精灵：**图片型返回延迟句柄**，文字/纯色立即合成。

        这是 `lsp` / `ld` / 读档恢复精灵的统一入口；要立刻拿到像素的地方
        （`btndef`、文本框图片、`blt`）仍然走 `build_sprite_image`。
        """
        spec = parse_sprite_spec(tag)
        if spec.kind == "image":
            return self.defer_sprite(tag, default_trans, cell), "image"
        return self.build_sprite_image(tag, default_trans, cell)

    def cell_of(self, tag: str) -> int:
        return parse_sprite_spec(tag).cells

    # ------------------------------------------------------------ 透明模式
    def _has_alpha(self, rel: str, img: Image.Image) -> bool:
        """引擎判定：PNG 一律当作有 alpha；其它格式看有没有 alpha 通道。"""
        key = rel.lower()
        if key in self._has_alpha_map:
            return self._has_alpha_map[key]
        ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
        if ext == "png":
            return True
        return img.mode in ("RGBA", "LA")

    @staticmethod
    def _alpha_from_right_half(img: Image.Image, cells: int) -> Image.Image:
        """「右半当 alpha」：左半是画面，右半是遮罩（红通道取反）。

        引擎（AnimationInfo.cpp:1103）按**每格**分别取右半：
            w2 = 图宽 / 格数,  w22 = w2 / 2
            alpha = 255 - 掩码红通道
        输出宽度 = w22 * 格数。
        """
        w, h = img.width, img.height
        w2 = max(w // max(cells, 1), 1)
        w22 = w2 // 2
        if w22 <= 0:
            return img
        red = img.convert("RGB").split()[0]
        out = Image.new("RGBA", (w22 * cells, h), (0, 0, 0, 0))
        for c in range(cells):
            x0 = c * w2
            left = img.crop((x0, 0, x0 + w22, h)).convert("RGB")
            mask = red.crop((x0 + w22, 0, min(x0 + w2, w), h))
            alpha = mask.point(lambda v: 255 - v)
            tile = left.convert("RGBA")
            tile.putalpha(alpha)
            out.paste(tile, (c * w22, 0))
        return out

    def _alpha_from_mask_file(self, img: Image.Image, mask_file: str) -> Image.Image:
        """`:m遮罩.bmp;图片.png`：用另一个文件当遮罩（红通道取反，横向平铺）。"""
        if not mask_file:
            return img
        m = self.load_image(mask_file)
        if m is None:
            return img
        mw, mh = m.size
        if mw == 0 or mh == 0:
            return img
        red = m.convert("RGB").split()[0]
        tiled = Image.new("L", (img.width, img.height))
        for y in range(img.height):
            row = red.crop((0, y % mh, mw, y % mh + 1))
            for x in range(0, img.width, mw):
                tiled.paste(row, (x, y))
        out = img.convert("RGBA")
        out.putalpha(tiled.point(lambda v: 255 - v))
        return out

    @staticmethod
    def _color_key(img: Image.Image, key: tuple[int, int, int]) -> Image.Image:
        """把指定颜色整块挖成透明，其余完全不透明（引擎的 leftup/topright/direct）。"""
        rgb = img.convert("RGB")
        r, g, b = rgb.split()
        kr, kg, kb = key
        mr = r.point(lambda v, k=kr: 0 if v == k else 255)
        mg = g.point(lambda v, k=kg: 0 if v == k else 255)
        mb = b.point(lambda v, k=kb: 0 if v == k else 255)
        alpha = ImageChops.darker(ImageChops.darker(mr, mg), mb)
        out = rgb.convert("RGBA")
        out.putalpha(alpha)
        return out

    def apply_trans_mode(self, img: Image.Image, spec: SpriteTag,
                         default_trans: str = TRANS_TOPLEFT) -> Image.Image:
        """按引擎的 trans_mode 规则给图片建 alpha 通道。"""
        mode = spec.trans or default_trans or TRANS_TOPLEFT
        if mode == TRANS_STRING:
            return img
        has_alpha = self._has_alpha(spec.filename, img)

        if mode == TRANS_ALPHA:
            if has_alpha:
                return img                       # 用图片自带的 alpha
            out = self._alpha_from_right_half(img, max(spec.cells, 1))
            self.stat_halved += 1
            return out
        if mode == TRANS_MASK:
            return self._alpha_from_mask_file(img, spec.mask_file)
        if mode in (TRANS_TOPLEFT, TRANS_TOPRIGHT):
            rgb = img.convert("RGB")
            key = rgb.getpixel((0, 0)) if mode == TRANS_TOPLEFT else rgb.getpixel((rgb.width - 1, 0))
            return self._color_key(img, key)
        if mode == TRANS_DIRECT:
            if spec.color:
                try:
                    key = ImageColor.getrgb(spec.color)[:3]
                except ValueError:
                    key = (0, 0, 0)
                return self._color_key(img, key)
            return img
        if mode == TRANS_COPY:
            out = img.convert("RGBA")
            out.putalpha(255)
            return out
        if mode == TRANS_PALETTE:
            return img
        return img

    # ------------------------------------------------------------ 精灵
    def parse_string_sprite(self, tag: str):
        """字符串精灵：`:s/30,30,1;#88FFFF$name` → (size, color, text)。"""
        spec = parse_sprite_spec(tag)
        if spec.kind != "text":
            return None
        size = spec.font_size[0] or 26
        return size, spec.color or "#FFFFFF", spec.text

    @staticmethod
    def sprite_cells(tag: str) -> int:
        return parse_sprite_spec(tag).cells

    def build_sprite_image(self, tag: str, default_trans: str = TRANS_TOPLEFT,
                           cell: int = 0) -> tuple[Image.Image | None, str]:
        """按 tag 合成精灵：文字精灵 / 纯色块 / 图片（含各种透明模式）。

        `cell` 是条图的帧号（引擎的 `current_cell`）。我们不做动画，所以调用方
        基本只传 0；存档里带上帧号后，将来加动画时读档就能落回原来的那一帧。
        """
        spec = parse_sprite_spec(tag)
        if spec.kind == "solid":
            return self._solid(spec.solid), "solid"
        if spec.kind == "text":
            size = spec.font_size[0] or 26
            body = spec.text_raw or spec.text
            return self._render_text_sprite(size, spec.color or "#FFFFFF", body), "text"
        if spec.kind != "image":
            return None, "unknown"

        # 长条动画图解码完就丢，不进 LRU（否则一张 60 格的条图能占几百 MB）
        raw = self._load_raw(spec.filename, cache=spec.cells <= 1)
        if raw is None:
            return None, "image"
        img = self.apply_trans_mode(raw, spec, default_trans)
        if spec.cells > 1:
            img = self._take_cell(img, spec.cells, cell)
        return img, "image"

    def _take_cell(self, img: Image.Image, cells: int, cell: int = 0) -> Image.Image | None:
        """取条图的第 `cell` 格（越界夹到首/末格，同 `AnimationInfo::setCell`）。"""
        if cells <= 1 or img is None:
            return img
        cw = img.width // cells
        if cw <= 0:
            return img
        idx = max(0, min(int(cell), cells - 1))
        return img.crop((idx * cw, 0, idx * cw + cw, img.height))

    def cells_of(self, tag: str) -> int:
        """tag 里的格数（存档/动画用）。"""
        return parse_sprite_spec(tag).cells

    def sprite_text(self, tag: str) -> str:
        parsed = self.parse_string_sprite(tag)
        return parsed[2] if parsed else ""

    def render_text_sprite(self, size: int, color: str, body: str) -> Image.Image | None:
        """给 strsp 之类的外部调用。"""
        return self._render_text_sprite(size, color, body)

    def solid_image(self, w: int, h: int, color: str) -> Image.Image | None:
        try:
            rgb = ImageColor.getrgb(color)
        except ValueError:
            rgb = (221, 221, 221)
        return Image.new("RGBA", (max(w, 1), max(h, 1)), rgb + (255,))

    def _render_text_sprite(self, size: int, color: str, body: str) -> Image.Image | None:
        """画一段文字。正文里可以夹 `#RRGGBB` 换色（引擎的 color_list）。"""
        if not body:
            return None
        font = self.font(size)
        runs = self._split_color_runs(body, color)
        if not runs:
            return None
        try:
            boxes = [font.getbbox(text) for _c, text in runs]
        except Exception:
            return None
        widths = [max(b[2] - b[0], 0) for b in boxes]
        w = max(sum(widths), 1) + 4
        h = max(max((b[3] - b[1] for b in boxes), default=0), 1) + 4
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x = 2
        for (col, text), bbox, tw in zip(runs, boxes, widths):
            if text:
                d.text((x - bbox[0], 2 - bbox[1]), text, font=font,
                       fill=ImageColor.getrgb(col) + (255,))
            x += tw
        return img

    @staticmethod
    def _split_color_runs(body: str, first_color: str) -> list[tuple[str, str]]:
        """把 `#RRGGBB文字#RRGGBB文字` 拆成 [(颜色, 文字), ...]。"""
        runs: list[tuple[str, str]] = []
        cur = first_color or "#FFFFFF"
        i = 0
        while i < len(body):
            if body[i] == "#":
                m = COLOR_RE.match(body[i:])
                if m:
                    cur = m.group(1)
                    i += 7
                    continue
            j = body.find("#", i)
            if j < 0:
                j = len(body)
            if j > i:
                runs.append((cur, body[i:j]))
            i = j
        return runs

    def _solid(self, spec: str) -> Image.Image | None:
        # w,h,#c1#c2
        w, _, rest = spec.partition(",")
        h, _, colors = rest.partition(",")
        try:
            iw, ih = int(w), int(h)
        except ValueError:
            return None
        cols = re.findall(r"#[0-9A-Fa-f]{6}", colors)
        c1 = ImageColor.getrgb(cols[0]) if cols else (0, 0, 0)
        c2 = ImageColor.getrgb(cols[1]) if len(cols) > 1 else c1
        img = Image.new("RGBA", (max(iw, 1), max(ih, 1)), c1 + (255,))
        if c1 != c2:
            grad = Image.new("RGBA", (1, max(ih, 1)))
            for y in range(max(ih, 1)):
                t = y / max(ih - 1, 1)
                grad.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,))
            img = grad.resize((max(iw, 1), max(ih, 1)))
        return img

    # ------------------------------------------------------------ 文本排版
    # 禁则字符表（ScriptParser.cpp 的 DEFAULT_START/END_KINSOKU，GBK 版）
    # START：不能出现在行首（后引号、句读、结尾符号…）——断行时"吊"在上一行末尾
    # END  ：不能出现在行尾（前引号、起始括号…）——断行时"挤"到下一行
    START_KINSOKU = "」』）］｝、。，．。？！ヽヾゝゞ々ー"
    END_KINSOKU = "「『（［｛"

    def wrap(self, text: str, cfg: WindowConfig, indent: int = 0) -> list[str]:
        """按行宽断行，并遵守禁则。

        引擎的做法（ONScripter_text.cpp `checkLineBreak`）：
          * 行首禁则字符（。，」等）不另起一行，允许略微超出右边界（悬挂）
          * 行尾禁则字符（「（等）不留在行末，跟后面的字一起挪到下一行
          * `indent n`：**每次**换行后在行首插 n 个全角空格（引擎 `newLine()` 之后
            往 page 里塞 0x8140 并前进一个全角位），首行不缩进
          * `setkinsoku` / `addkinsoku` 会替换/追加禁则表（挂在 cfg 上）
        """
        font = self.font(cfg.font_size_x)
        max_w = cfg.num_x * cfg.pitch_x
        head_set = cfg.kinsoku_head or self.START_KINSOKU
        tail_set = cfg.kinsoku_tail or self.END_KINSOKU
        pad = "\u3000" * max(0, int(indent))
        lines: list[str] = []
        for para in text.split("\n"):
            cur = ""
            for ch in para:
                if ch == "\\":      # 强制换行符
                    lines.append(cur)
                    cur = pad
                    continue
                trial = cur + ch
                try:
                    w = font.getlength(trial)
                except Exception:
                    w = len(trial) * cfg.pitch_x
                if w > max_w and cur.strip():
                    if ch in head_set:
                        # 悬挂：标点允许超出右边界一点，不另起一行
                        cur = trial
                        continue
                    # 行尾若有前引号之类，挪到下一行跟新字一起走
                    moved = ""
                    body = cur
                    while body and body[-1] in tail_set:
                        moved = body[-1] + moved
                        body = body[:-1]
                    lines.append(body)
                    cur = pad + moved + ch
                else:
                    cur = trial
            lines.append(cur)
        return [ln for ln in lines]

    def paginate(self, text: str, cfg: WindowConfig, indent: int = 0) -> list[list[str]]:
        """一段文字 → 若干页。

        引擎的规则（实测参照引擎）：**不会**按文本框高度自动切页。
        一段文字折出多少行就画多少行，超出文本框的部分直接溢出到框外
        （参照引擎在 3 行的框里画了 4 行，第 4 行压到画面底部）。
        翻页只发生在显式的点击点（`\\`、`@`）上。

        所以这里不再按 num_y 切片——否则会比引擎多出一次点击。
        """
        lines = self.wrap(text, cfg, indent)
        return [lines] if lines else [[]]

    # ------------------------------------------------------------ 合成
    def compose(self, state: State, page_lines: list[str] | None = None,
                frame: bool = True, draw_name: bool = True) -> Image.Image:
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        bg = self.image_of(state.bg_image)
        if bg is not None:
            canvas.alpha_composite(self._fit(bg), (0, 0))
        elif state.bg_color:
            canvas.paste(Image.new("RGBA", canvas.size, state.bg_color + (255,)), (0, 0))

        # blt 贴上去的像素在引擎里是直接写在屏幕上的，下一次整屏重绘才会消失。
        # 我们按需合成，所以把它放在"背景之上、精灵之下"。
        if state.overlay is not None:
            canvas.alpha_composite(state.overlay, (0, 0))

        # 引擎 refreshSurface 的绘制次序（ONScripter_image.cpp:640-700）：
        #   1) id > humanz 的精灵，按 id **从大到小** 画（id 大的在底下）
        #   2) 立绘 tachi（左→中→右）
        #   3) 文本框
        #   4) id <= humanz 的精灵，同样从大到小画（于是 id 小的压在最上面）
        hz = state.humanz
        above = sorted((sid for sid in state.sprites if sid > hz), reverse=True)
        below = sorted((sid for sid in state.sprites if sid <= hz), reverse=True)
        for sid in above:
            self._draw_sprite(canvas, state.sprites[sid])

        if getattr(state, "tachi_visible", True):
            for no in (0, 1, 2):
                sp = state.tachi.get(no)
                if sp is not None and sp.visible and sp.image is not None:
                    self._draw_sprite(canvas, sp)

        # `textoff` 关掉的是**整个文本层**（窗口框 + 文字），不是只关文字；
        # 只藏文字是 `texthide`（走上面的 text_hidden），两者别混。
        if frame and state.window.active and state.text_on \
                and not state.text_window_erased:
            self._draw_window_frame(canvas, state.window, state.trans_mode)

        below = [sid for sid in below if sid not in state.ui_sprites]
        for sid in below:
            self._draw_sprite(canvas, state.sprites[sid])

        # 按钮层（cselbtn 的选项文字）：引擎里 ButtonLink 最后画，压在所有层之上
        for sid in sorted(state.ui_sprites):
            sp = state.sprites.get(sid)
            if sp is not None:
                self._draw_sprite(canvas, sp)

        if page_lines and state.text_on and not state.text_window_erased \
                and not state.text_hidden:
            self._draw_page_text(canvas, state.window, page_lines, state.text_locate)
            # 跑 textgosub 钩子时，名字是脚本自己用 lsp 299 画的，别重复画一遍
            if draw_name and state.page and state.page.name:
                self._draw_name(canvas, state.window, state.page.name)
        return canvas.convert("RGB")

    # 名字的样式沿用移植脚本 *pretext_do 里的定义：
    #   lsp 299,":s/30,30,1;#88FFFF"+$name, 285-len*15/2, 528+28
    NAME_STYLE = {"size": 30, "color": "#88FFFF", "center_x": 285, "y": 556}

    def _draw_name(self, canvas: Image.Image, cfg: WindowConfig, name: str) -> None:
        font = self.font(self.NAME_STYLE["size"])
        try:
            w = font.getlength(name)
        except Exception:
            w = len(name) * self.NAME_STYLE["size"]
        x = int(self.NAME_STYLE["center_x"] - w / 2)
        y = self.NAME_STYLE["y"]
        d = ImageDraw.Draw(canvas)
        color = ImageColor.getrgb(self.NAME_STYLE["color"])
        d.text((x + 1, y + 2), name, font=font, fill=(0, 0, 0))
        d.text((x, y), name, font=font, fill=color)

    def _fit(self, img: Image.Image) -> Image.Image:
        if img.size == (self.width, self.height):
            return img
        return img.resize((self.width, self.height))

    def _draw_sprite(self, canvas: Image.Image, sp) -> None:
        if not sp.visible or sp.image is None:
            return
        # sp.image 可能是 DeferredImage（lsp 时没解码）：这里才真解码
        img = self.image_of(sp.image)
        if img is None:
            return
        if sp.alpha <= 0:
            return
        if sp.alpha < 255:
            img = img.copy()
            alpha = img.getchannel("A").point(lambda a: a * sp.alpha // 255)
            img.putalpha(alpha)
        canvas.alpha_composite(img, (int(sp.x), int(sp.y)))

    def _draw_window_frame(self, canvas: Image.Image, cfg: WindowConfig,
                           trans_mode: str = TRANS_TOPLEFT) -> None:
        """文本框的两种形态，引擎行为不一样：

        * `setwindow3 ... ,"frame.png",x,y` —— 图片按 **copy 模式** 画，**忽略 PNG 的 alpha**。
          （实测：参照引擎在 α=3 的行上也直接输出图片 RGB，不是和底图混合）
        * `setwindow3 ...,"#RRGGBB",x0,y0,x1,y1` —— 不是盖一层半透明色，而是把该区域
          逐像素 **乘** 上这个颜色（`*buf * color >> 8`），即变暗而不是变透明。
        """
        if cfg.frame_path:
            # 窗口图在 setwindow3 时就按当时的透明模式烤好了（见 _bake_window_frame）
            img = getattr(cfg, "frame_image", None)
            if img is None:
                img, _kind = self.build_sprite_image(cfg.frame_path, trans_mode)
            if img is not None:
                canvas.alpha_composite(img.convert("RGBA"), (cfg.frame_x, cfg.frame_y))
                return
        if cfg.frame_color:
            try:
                color = ImageColor.getrgb(cfg.frame_color)
            except ValueError:
                return
            # 矩形由 setwindow 的 4 个坐标给出（x1-x0+1 / y1-y0+1）；
            # 老数据没有宽高就退回"从这里铺到画布右下角"
            x0, y0 = cfg.frame_x, cfg.frame_y
            x1 = x0 + cfg.frame_w if cfg.frame_w else canvas.width
            y1 = y0 + cfg.frame_h if cfg.frame_h else canvas.height
            x1, y1 = min(x1, canvas.width), min(y1, canvas.height)
            if x1 <= x0 or y1 <= y0:
                return
            region = canvas.crop((x0, y0, x1, y1))
            px = region.load()
            for y in range(region.height):
                for x in range(region.width):
                    r, g, b = px[x, y][:3]
                    px[x, y] = (r * color[0] >> 8, g * color[1] >> 8, b * color[2] >> 8)
            canvas.paste(region, (x0, y0))

    def _draw_page_text(self, canvas: Image.Image, cfg: WindowConfig, lines: list[str],
                        locate: tuple[int, int] = (0, 0)) -> None:
        """画正文。

        `locate x,y` 的偏移单位是**字符格**：引擎 `FontInfo::x()` = `xy*pitch/2 + top_xy`，
        而 `setXY(x,y)` 存的是 `x*2`，所以 `locate 2,1` = 右移 2 个 pitch_x、下移 1 个 pitch_y。
        """
        font = self.font(cfg.font_size_x)
        d = ImageDraw.Draw(canvas)
        x0 = cfg.x + locate[0] * cfg.pitch_x
        y0 = cfg.y + locate[1] * cfg.pitch_y
        try:
            fill = ImageColor.getrgb(cfg.text_color or "#FFFFFF")
        except ValueError:
            fill = (255, 255, 255)
        for i, line in enumerate(lines):
            x = x0
            y = y0 + i * cfg.pitch_y
            if not line:
                continue
            if cfg.shadow:
                d.text((x + 1, y + 2), line, font=font, fill=(0, 0, 0, 255))
            d.text((x, y), line, font=font, fill=fill + (255,) if len(fill) == 3 else fill)

    def text_cursor(self, cfg: WindowConfig,
                    lines: list[str] | None = None,
                    locate: tuple[int, int] = (0, 0)) -> tuple[int, int]:
        """文本框里"下一个字符的落点"（引擎 `FontInfo::x/y`），供 `getcursorpos` 用。

        **实测结论**（真引擎探针，setwindow 100,100,20,3，行距 36）：
        一条文本显示完之后引擎会自己换行，光标停在**下一行行首**——
        单行 `X=100 Y=136`，折成两行 `X=100 Y=172`，即 `y = top_y + 行数 * pitch_y`。
        所以这里不能用"末行宽度"，而是"已画行数 × 行距"。

        按**当前页**现算，不缓存"上次渲染的位置"——我们的绘制是懒执行的
        （截图时才合成），脚本调 `getcursorpos` 时往往还没渲染过。
        """
        drawn = len([ln for ln in (lines or []) if ln])
        return (cfg.x + locate[0] * cfg.pitch_x,
                cfg.y + locate[1] * cfg.pitch_y + drawn * cfg.pitch_y)
