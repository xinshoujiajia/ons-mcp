"""NSA/SAR 归档读取（NScripter 的资源包格式）。

原始发布版游戏把素材打进 `arc.nsa` / `arc1.nsa` / `arc2.nsa`，脚本是
`nscript.dat`。要"拿到一个压缩包就能玩"，就必须能直接读这些包。

格式（`SarReader.cpp` / `DirectReader.cpp`）：

    uint16  num_of_files
    uint32  base_offset                  // 数据区起点
    num_of_files × {
        char[]  name; '\\0'              // 反斜杠路径，比较时不区分大小写
        uint8   compression_type         // 0 无 / 1 SPB / 2 LZSS / 4 NBZ
        uint32  offset                   // 相对 base_offset
        uint32  length                   // 存储长度
        uint32  original_length
    }

引擎的 `readShort/readLong` 是大端，但历史上有小端写出来的包，所以这里
**自动判字节序**：用"每条记录的 offset 应当等于前面所有 length 之和"来验证，
再要求"最后一条结束位置 == 文件大小"。两条都满足才算解析成功。
"""
from __future__ import annotations

import bz2
import mmap
import struct
from dataclasses import dataclass
from pathlib import Path

from .log import get_logger

log = get_logger("archive")

COMP_NONE = 0
COMP_SPB = 1
COMP_LZSS = 2
COMP_NBZ = 4

# LZSS 参数（DirectReader.cpp: EI=8, EJ=4, P=1）
_LZ_N = 1 << 8
_LZ_F = (1 << 4) + 1


def normalize(name: str) -> str:
    return name.replace("\\", "/").lstrip("/").lower()


class BitReader:
    """MSB 优先的位读取器（对应 DirectReader::getbit）。"""

    __slots__ = ("data", "pos", "acc", "n")

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.acc = 0
        self.n = 0

    def get(self, bits: int) -> int:
        val = 0
        for _ in range(bits):
            if self.n == 0:
                if self.pos >= len(self.data):
                    raise EOFError("位流结束")
                self.acc = self.data[self.pos]
                self.pos += 1
                self.n = 8
            self.n -= 1
            val = (val << 1) | ((self.acc >> self.n) & 1)
        return val


def decode_lzss(data: bytes, orig_len: int) -> bytes:
    br = BitReader(data)
    out = bytearray()
    buf = bytearray(_LZ_N)
    r = _LZ_N - _LZ_F
    while len(out) < orig_len:
        try:
            if br.get(1):
                c = br.get(8)
                out.append(c)
                buf[r] = c
                r = (r + 1) & (_LZ_N - 1)
            else:
                i = br.get(8)
                j = br.get(4)
                for k in range(j + 2):
                    c = buf[(i + k) & (_LZ_N - 1)]
                    out.append(c)
                    buf[r] = c
                    r = (r + 1) & (_LZ_N - 1)
                    if len(out) >= orig_len:
                        break
        except EOFError:
            break
    return bytes(out)


def decode_spb(data: bytes) -> bytes:
    """SPB = 打包过的 24 位 BMP（逐通道差值编码 + 像素蛇形排列）。"""
    if len(data) < 5:
        return b""
    width, height = struct.unpack(">HH", data[0:4])
    width_pad = (4 - width * 3 % 4) % 4
    row = width * 3 + width_pad
    total = row * height + 54

    out = bytearray(total)
    out[0:2] = b"BM"
    struct.pack_into("<I", out, 2, total)
    struct.pack_into("<I", out, 10, 54)
    struct.pack_into("<I", out, 14, 40)
    struct.pack_into("<i", out, 18, width)
    struct.pack_into("<i", out, 22, height)
    struct.pack_into("<H", out, 26, 1)
    struct.pack_into("<H", out, 28, 24)
    # 注意：引擎只写低字节（buf[34] = total_size - 54），高位留 0。
    # 大部分 BMP 解析器不看这个字段，但要跟原引擎逐字节一致就得照抄。
    out[34] = (total - 54) & 0xFF

    br = BitReader(data[4:])
    plane = bytearray(width * height + 4)
    for ch in range(3):
        count = 0
        c = br.get(8)
        plane[count] = c
        count += 1
        while count < width * height:
            try:
                n = br.get(3)
            except EOFError:
                break
            if n == 0:
                for _ in range(4):
                    if count < len(plane):
                        plane[count] = c
                    count += 1
                continue
            m = (br.get(1) + 1) if n == 7 else (n + 2)
            for _ in range(4):
                if m == 8:
                    c = br.get(8)
                else:
                    k = br.get(m)
                    c = c + (k >> 1) + 1 if k & 1 else c - (k >> 1)
                if count < len(plane):
                    plane[count] = c & 0xFF
                count += 1

        # 蛇形写回：自底向上，偶数行向右、奇数行向左，BGR 平面分离
        pos = 54 + row * (height - 1) + ch
        src = 0
        for j in range(height):
            if j & 1:
                for _ in range(width):
                    out[pos] = plane[src]
                    src += 1
                    pos -= 3
                pos -= row - 3
            else:
                for _ in range(width):
                    out[pos] = plane[src]
                    src += 1
                    pos += 3
                pos -= row + 3
    return bytes(out)


@dataclass
class Entry:
    name: str
    comp: int
    offset: int
    length: int
    orig_length: int


class NsaArchive:
    """一个 .nsa 包的索引 + 按需读取。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: dict[str, Entry] = {}
        self.endian = ">"
        self.base_offset = 0
        self.unsupported = 0
        # 用 mmap 而不是 read()：arc.nsa + arc1.nsa 有 600MB+，
        # 整个读进内存会白白顶上一个巨大的 RSS，而且绝大多数根本用不到。
        self._mm: mmap.mmap | None = None
        self._fh = None
        self._load()
        log.info("载入归档 %s：%d 个文件（字节序 %s）",
                 self.path.name, len(self.entries),
                 "大端" if self.endian == ">" else "小端")

    # ---------------------------------------------------------------- 解析
    def _parse(self, raw, endian: str) -> dict[str, Entry] | None:
        try:
            num = struct.unpack(endian + "H", raw[0:2])[0]
            base = struct.unpack(endian + "I", raw[2:6])[0]
        except struct.error:
            return None
        if num == 0 or num > 200000:
            return None

        pos = 6
        entries: dict[str, Entry] = {}
        cum = 0
        for _ in range(num):
            end = raw.find(b"\x00", pos)
            if end < 0 or end - pos > 260:
                return None
            name = raw[pos:end].decode("latin1")
            pos = end + 1
            if pos + 13 > len(raw):
                return None
            comp = raw[pos]
            off, length, orig = struct.unpack(endian + "III", raw[pos + 1:pos + 13])
            pos += 13
            if off != cum:            # 关键校验：数据是紧挨着排的
                return None
            cum += length
            entries.setdefault(normalize(name), Entry(name, comp, off, length, orig))
        if base + cum != len(raw):    # 数据区必须刚好到文件末尾
            return None
        self.base_offset = base
        return entries

    def _load(self) -> None:
        self._fh = open(self.path, "rb")
        try:
            self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        except (ValueError, OSError):
            self._mm = None
        if self._mm is None:
            self.close()
            raise ValueError(f"{self.path.name} 无法映射（空文件？）")
        for endian in (">", "<"):
            entries = self._parse(self._mm, endian)
            if entries is not None:
                self.entries = entries
                self.endian = endian
                return
        self.close()
        raise ValueError(f"{self.path.name} 不是可识别的 NSA 归档")

    def close(self) -> None:
        if self._mm is not None:
            try:
                self._mm.close()
            except BufferError:
                pass
            self._mm = None
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    # ---------------------------------------------------------------- 读取
    def has(self, name: str) -> bool:
        return normalize(name) in self.entries

    def read(self, name: str) -> bytes | None:
        e = self.entries.get(normalize(name))
        if e is None:
            return None
        if self._mm is None:
            return None
        start = self.base_offset + e.offset
        data = self._mm[start:start + e.length]
        try:
            if e.comp == COMP_NONE:
                return data
            if e.comp == COMP_LZSS:
                return decode_lzss(data, e.orig_length)
            if e.comp == COMP_SPB:
                return decode_spb(data)
            if e.comp == COMP_NBZ:
                return bz2.decompress(data[4:])
        except Exception as exc:                      # noqa: BLE001
            log.warning("解压失败 %s/%s：%s", self.path.name, e.name, exc)
            return None
        self.unsupported += 1
        log.debug("归档里有未支持的压缩类型 %d：%s", e.comp, e.name)
        return None

    def release(self) -> None:
        """断开映射；索引还在，但之后读不出内容。多会话时用来腾内存。"""
        self.close()


def open_archives(game_dir: Path) -> list[NsaArchive]:
    """按引擎习惯的查找顺序载入 arc.nsa / arc1.nsa / arc2.nsa …（也接受 *.nsa）。"""
    archives: list[NsaArchive] = []
    candidates: list[Path] = []
    first = game_dir / "arc.nsa"
    if first.exists():
        candidates.append(first)
    for i in range(1, 10):
        p = game_dir / f"arc{i}.nsa"
        if p.exists():
            candidates.append(p)
    if not candidates:                                # 其他命名的包也收
        candidates = sorted(game_dir.glob("*.nsa"))
    for p in candidates:
        try:
            archives.append(NsaArchive(p))
        except Exception as exc:                      # noqa: BLE001
            log.warning("跳过归档 %s：%s", p.name, exc)
    return archives
