"""Background service entry for ops."""

from __future__ import annotations

from typing import Any

from oldman.runtime import SimpleApplication


class OpsService(SimpleApplication):
    """Run the ops background workload."""

    def prepare(self) -> None:
        """Prepare synchronous service resources."""

    async def main(self, *args: Any, **kwargs: Any) -> None:
        """Run the service workload."""
        del args, kwargs
