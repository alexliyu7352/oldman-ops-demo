"""清理操作记录:删除若干天以前的记录。远程文件直接用工具已有的模型和数据库。"""

from __future__ import annotations

from datetime import timedelta

from oldman.cli import tui
from oldman.db import db_manager
from oldman.utils.date import naive_utcnow
from sqlalchemy import delete, func, select

from apps.ops.models import OperationLog
from apps.ops.toolkit import record


def not_negative(days: int) -> None:
    if days < 0:
        raise ValueError("天数不能是负数")


async def run() -> None:
    days = tui.ask("删除多少天以前的记录", type=int, default=30, validate=not_negative, key="cleanup.days")
    older = OperationLog.created_at < naive_utcnow() - timedelta(days=days)
    async with db_manager.get_read_session() as session:
        count = (await session.execute(select(func.count()).select_from(OperationLog).where(older))).scalar_one()
    if not count:
        tui.info(f"没有 {days} 天以前的记录。")
        return
    if not tui.confirm(f"删除 {count} 条记录?", default=False):
        return
    async with db_manager.get_session() as session:
        await session.execute(delete(OperationLog).where(older))
    await record("cleanup", f"删除了 {count} 条 {days} 天以前的记录")
    tui.success(f"已删除 {count} 条记录。")
