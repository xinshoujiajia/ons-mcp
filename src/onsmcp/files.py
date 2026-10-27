"""统一资源访问：先查磁盘目录，再查 .nsa 归档。

引擎的行为就是这样——`DirectReader` 找不到文件时会到注册过的归档里找。
所以"解包版"和"原始压缩版"必须走同一条路径，代码里不该出现两套分支。
"""
from __future__ import annotations

from pathlib import Path

from .archive import NsaArchive, normalize, open_archives
from .log import get_logger

log = get_logger("files")

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
ANY_EXT = IMAGE_EXT + (".ttf", ".otf", ".ttc", "")


class GameFiles:
    def __init__(self, game_dir: Path, archives: list[NsaArchive] | None = None):
        self.game_dir = Path(game_dir)
        self.archives = archives or []
        self._missing: set[str] = set()

    # ---------------------------------------------------------------- 构造
    @classmethod
    def open(cls, game_dir: str | Path, use_archives: bool = True) -> "GameFiles":
        game_dir = Path(game_dir)
        archives = open_archives(game_dir) if use_archives else []
        return cls(game_dir, archives)

    # ---------------------------------------------------------------- 查询
    def path(self, rel: str) -> Path | None:
        """只在磁盘上找（有些调用需要真实路径，比如截图、存档）。"""
        rel = rel.strip().replace("\\", "/")
        if not rel:
            return None
        p = self.game_dir / rel
        if p.is_file():
            return p
        # 大小写不敏感兜底：Windows 上无所谓，跨平台打包时有用
        low = rel.lower()
        parent = self.game_dir
        for part in low.split("/"):
            cand = next((c for c in parent.iterdir()
                         if c.name.lower() == part), None) if parent.is_dir() else None
            if cand is None:
                return None
            parent = cand
        return parent if parent.is_file() else None

    def exists(self, rel: str) -> bool:
        return self.read(rel) is not None

    def has(self, rel: str) -> bool:
        """文件在不在 —— 只看目录项，**不读内容**。

        懒加载要靠它做"载入失败"的判定：`bg` 找不到图时引擎保留旧背景，
        我们得在 defer 的那一刻就知道文件在不在，又不能为此把文件读进内存。
        """
        for cand in self.candidates(rel):
            if self.path(cand) is not None:
                return True
            key = normalize(cand)
            if any(arc.has(key) for arc in self.archives):
                return True
        return False

    def candidates(self, rel: str) -> list[str]:
        rel = rel.strip().replace("\\", "/")
        if not rel:
            return []
        out = [rel] if rel.lower().endswith(ANY_EXT) else [rel + e for e in IMAGE_EXT] + [rel]
        return out

    def read(self, rel: str) -> bytes | None:
        """磁盘优先，其次归档（归档按 arc / arc1 / arc2 的顺序）。"""
        for cand in self.candidates(rel):
            key = normalize(cand)
            p = self.path(cand)
            if p is not None:
                try:
                    return p.read_bytes()
                except OSError:
                    pass
            for arc in self.archives:
                data = arc.read(key)
                if data is not None:
                    return data
        self._missing.add(normalize(rel))
        return None

    # ---------------------------------------------------------------- 统计
    def stats(self) -> dict:
        return {
            "archives": [{"name": a.path.name, "files": len(a.entries)} for a in self.archives],
            "archive_files": sum(len(a.entries) for a in self.archives),
            "missing": len(self._missing),
        }

    def close(self) -> None:
        for a in self.archives:
            a.close()
