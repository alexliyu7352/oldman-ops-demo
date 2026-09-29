"""What local actions and remote files share: the root, systemctl, the remote files and the operation log.

It reads `app.settings` when imported, so only `services`, `menus`, `commands` and the remote files import
it. `apps.py` and `models.py` must not: the `db` commands load them without any settings.
"""

from __future__ import annotations

from pathlib import Path

from oldman.cli.remote import RemoteFiles
from oldman.conf import settings
from oldman.db import db_manager

from apps.ops.apps import app
from apps.ops.models import OperationLog

ROOT = app.settings.root.resolve()
SYSTEMCTL = app.settings.systemctl
remote = RemoteFiles(app.settings.remote_base, cache_dir=settings.core.data_dir / "remote")


def path(system_path: str) -> Path:
    """Where a system path such as `/etc/ssh/sshd_config` is under the root."""
    return ROOT / system_path.lstrip("/")


async def record(action: str, detail: str = "") -> None:
    """Add one row to the operation log."""
    async with db_manager.get_session() as session:
        session.add(OperationLog(action=action, detail=detail))


__all__ = ["ROOT", "SYSTEMCTL", "path", "record", "remote"]
