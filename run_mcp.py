"""启动 MCP 服务（stdio）。

保留这个文件是为了兼容已经配好 `python run_mcp.py` 的 MCP 客户端；
新配置建议直接用包入口（任选其一）：

    python -m onsmcp          # 装了包之后
    ons-mcp                   # 控制台脚本（pip install -e . 生成）

注意：stdout 是 MCP 协议通道，任何调试输出都必须走 stderr。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许不安装、直接在本仓库里跑
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from onsmcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
