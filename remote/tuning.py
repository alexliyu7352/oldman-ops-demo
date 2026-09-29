"""内核参数:推荐值是远程的数据文件 data/sysctl.conf,写进沙箱 sysctl.conf 的标记块。"""

from __future__ import annotations

from oldman import ops
from oldman.cli import tui

from apps.ops.toolkit import path, record, remote


async def run() -> None:
    recommended = (await remote.fetch("data/sysctl.conf")).read_text(encoding="utf-8")
    changed = ops.edit_marked_block(path("/etc/sysctl.conf"), "OPS_DEMO_TUNING", recommended, follow_symlinks=False)
    if not changed:
        tui.info("sysctl.conf 已经是推荐值,没有改动。")
        return
    await record("tuning", "sysctl.conf")
    tui.success("已写入 sysctl.conf。")
    tui.info("真实服务器上接着执行 sysctl --system 让它生效。")
