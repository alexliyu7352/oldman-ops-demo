"""Nginx 站点:菜单按沙箱里现有的站点生成。"""

from __future__ import annotations

from oldman import ops
from oldman.cli import tui

from apps.ops.services import site_file, sites
from apps.ops.toolkit import SYSTEMCTL, record


def upstream(site: str) -> str:
    for line in site_file(site).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("proxy_pass "):
            return line.split(None, 1)[1].rstrip(";")
    return ""


async def show_sites() -> None:
    tui.table([(site, upstream(site)) for site in sites()], headers=["站点", "上游"], title="已启用的站点")


async def reload_nginx() -> None:
    # Not inside a spinner: with a sudo that asks for a password, the redraw would wipe its prompt.
    tui.info("重载 nginx…")
    await ops.systemd.reload("nginx", command=SYSTEMCTL)
    tui.success("nginx 已重载。")


async def delete_site() -> None:
    # The submenu keeps this item after the last site is deleted, so check again when it is chosen.
    if not sites():
        tui.info("没有站点可以删除。")
        return
    site = tui.choose("删除哪个站点", sites())
    if not tui.confirm(f"删除 {site}?", default=False):
        return
    site_file(site).unlink()
    await record("delete-site", site)
    await reload_nginx()


async def menu() -> tui.Menu:
    items = [tui.Item("站点列表", action=show_sites), tui.Item("重载 nginx", action=reload_nginx)]
    if sites():
        items.insert(1, tui.Item("删除站点", action=delete_site))
    else:
        items[0] = tui.Item("站点列表(空)", action=show_sites)
    return tui.Menu(f"Nginx:{len(sites())} 个站点", items)
