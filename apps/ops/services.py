"""The tool's business functions: plain parameters and no questions, so the menu and the commands share them."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oldman import ops
from oldman.db import db_manager
from oldman.utils.files import atomic_write
from sqlalchemy import select

from apps.ops.models import OperationLog
from apps.ops.toolkit import ROOT, SYSTEMCTL, path, record

SAMPLE_ROOT = Path(__file__).resolve().parent / "sample_root"
# Only a root made from the samples carries it, so "reset" can never empty a real system's /.
SANDBOX_MARKER = ".ops-demo-sandbox"
SSHD_CONFIG = "/etc/ssh/sshd_config"
SITES = "/etc/nginx/sites-enabled"
UNITS = ("ssh", "nginx", "openresty")
_DOMAIN = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}")


def prepare_root() -> bool:
    """Create the root from the samples the first time; True when it was created now."""
    if ROOT.exists():
        return False
    shutil.copytree(SAMPLE_ROOT, ROOT)
    return True


async def reset_root() -> None:
    """Put the sandbox back to the samples."""
    if ROOT.exists() and not (ROOT / SANDBOX_MARKER).is_file():
        raise RuntimeError(f"{ROOT} is not a sandbox made from the samples; refusing to reset it")
    shutil.rmtree(ROOT, ignore_errors=True)
    shutil.copytree(SAMPLE_ROOT, ROOT)
    await record("reset-root", str(ROOT))


def check_port(port: int) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("端口要在 1 到 65535 之间")


def check_domain(domain: str) -> None:
    if _DOMAIN.fullmatch(domain.lower()) is None:
        raise ValueError("不是有效的域名,例如 example.org")


def ssh_port() -> str:
    return ops.read_directive(path(SSHD_CONFIG), "Port", "22") or "22"


@dataclass(frozen=True)
class PortChange:
    changed: bool
    restarted: str | None


async def change_ssh_port(port: int) -> PortChange:
    """Make sshd listen on `port`; on Ubuntu 22.04 and later also its socket, which otherwise keeps the old port."""
    check_port(port)
    changed = ops.set_directive(path(SSHD_CONFIG), "Port", str(port), follow_symlinks=False)
    release = ops.os_release(path("/etc/os-release"))
    if release.get("ID") == "ubuntu" and _version(release.get("VERSION_ID", "0")) >= (22, 4):
        socket_changed = ops.edit_marked_block(
            path("/etc/systemd/system/ssh.socket.d/override.conf"),
            "PORT",
            f"[Socket]\nListenStream=\nListenStream={port}",
            follow_symlinks=False,
        )
        if socket_changed:
            await ops.systemd.daemon_reload(command=SYSTEMCTL)
        changed = changed or socket_changed
    if not changed:
        return PortChange(changed=False, restarted=None)
    restarted = await ops.systemd.restart("ssh", "sshd", command=SYSTEMCTL)
    await record("ssh-port", f"Port {port}")
    return PortChange(changed=True, restarted=restarted)


def _version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


@dataclass(frozen=True)
class Site:
    domain: str
    port: int
    tls: bool
    engine: str


def sites() -> list[str]:
    return sorted(site.stem for site in path(SITES).glob("*.conf"))


def site_file(domain: str) -> Path:
    return path(SITES) / f"{domain}.conf"


def render_site(site: Site) -> str:
    listen = "    listen 443 ssl;\n" if site.tls else "    listen 80;\n"
    certificate = (
        f"    ssl_certificate /etc/letsencrypt/live/{site.domain}/fullchain.pem;\n"
        f"    ssl_certificate_key /etc/letsencrypt/live/{site.domain}/privkey.pem;\n"
        if site.tls
        else ""
    )
    return (
        "server {\n"
        f"{listen}"
        f"    server_name {site.domain};\n"
        f"{certificate}"
        "\n"
        "    location / {\n"
        f"        proxy_pass http://127.0.0.1:{site.port};\n"
        "    }\n"
        "}\n"
    )


async def add_site(site: Site) -> bool:
    """Write the site and reload its server; False when that server is not running."""
    check_domain(site.domain)
    check_port(site.port)
    atomic_write(site_file(site.domain), render_site(site), follow_symlinks=False)
    await record("add-site", f"{site.domain} -> 127.0.0.1:{site.port} ({site.engine})")
    if not await ops.systemd.is_active(site.engine, command=SYSTEMCTL):
        return False
    await ops.systemd.reload(site.engine, command=SYSTEMCTL)
    return True


async def unit_states() -> list[tuple[str, bool]]:
    return [(unit, await ops.systemd.is_active(unit, command=SYSTEMCTL)) for unit in UNITS]


async def recent_operations(limit: int = 20) -> list[OperationLog]:
    async with db_manager.get_read_session() as session:
        query = select(OperationLog).order_by(OperationLog.created_at.desc(), OperationLog.id.desc()).limit(limit)
        return list((await session.execute(query)).scalars())


async def report() -> dict[str, Any]:
    return {
        "root": str(ROOT),
        "ssh_port": ssh_port(),
        "sites": sites(),
        "units": dict(await unit_states()),
    }
