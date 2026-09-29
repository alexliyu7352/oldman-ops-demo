"""Deployment settings of the ops App: where remote files come from, which root it changes, how it runs systemctl."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class OpsSettings(BaseModel):
    """A sandbox by default; a real server sets `root: /` and `systemctl: [sudo, systemctl]`."""

    model_config = ConfigDict(extra="forbid")

    remote_base: str = Field(description="Base address of the remote files: a GitHub raw URL, a file server or a local directory")
    root: Path = Field(default=Path("var/root"), description="Directory standing in for /; every change lands under it")
    systemctl: tuple[str, ...] = Field(default=("systemctl",), description="How systemctl is run")
