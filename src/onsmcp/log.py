"""日志：一律写 stderr，绝不允许污染 stdout。

stdout 是 MCP 的协议通道（一行一个 JSON-RPC 帧），任何 print 过去都会让客户端
解析失败。所以这里在 import 时就把 handler 钉死在 sys.stderr 上，并给 stdlib
logging 一个固定前缀，方便从客户端日志里认出来。

级别用环境变量 `ONSMCP_LOG` 控制：debug / info / warning(默认) / error / silent。
"""
from __future__ import annotations

import logging
import os
import sys

_PREFIX = "onsmcp"
_configured = False

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "silent": logging.CRITICAL + 10,
}


def level_from_env() -> int:
    raw = (os.environ.get("ONSMCP_LOG") or "warning").strip().lower()
    return _LEVELS.get(raw, logging.WARNING)


class _StderrHandler(logging.Handler):
    """每次写日志时重新取 sys.stderr。

    logging.StreamHandler 在构造时就把流绑死了；如果宿主（比如 MCP 客户端
    的启动器）之后替换了 sys.stderr，日志就会写到旧流里去，和协议输出混在一起。
    """

    terminator = "\n"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stderr.write(self.format(record) + self.terminator)
            sys.stderr.flush()
        except Exception:                        # noqa: BLE001
            self.handleError(record)


def setup() -> None:
    """配置根 logger。重复调用安全（MCP 客户端可能会 reload 模块）。"""
    global _configured
    if _configured:
        return
    logger = logging.getLogger(_PREFIX)
    logger.setLevel(level_from_env())
    handler = _StderrHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(handler)
    # 不往上冒泡：避免客户端把 root logger 也挂到 stdout 时被带偏
    logger.propagate = False
    _configured = True


def get_logger(name: str = "") -> logging.Logger:
    setup()
    return logging.getLogger(f"{_PREFIX}.{name}" if name else _PREFIX)
