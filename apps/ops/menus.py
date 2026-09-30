"""The tool's menu: the questions live here, the work in `services`; remote items come from `toolkit.remote`."""

from __future__ import annotations

from oldman import ops
from oldman.cli import tui
from oldman.conf import settings

from apps.ops import services
from apps.ops.toolkit import ROOT, record, remote

SITE_FIELDS = [
    tui.Field("domain", "域名", validate=services.check_domain, help="访问者输入的名字,不带 https://。"),
    tui.Field("port", "上游端口", type=int, default=8000, validate=services.check_port),
    tui.Field("tls", "启用 HTTPS", type=bool, default=False),
    tui.Field("engine", "服务器", choices=["nginx", "openresty"], default="nginx"),
]


def ask_ssh_port() -> int:
    return tui.ask(
        "新的 SSH 端口",
        type=int,
        validate=services.check_port,
        help=f"sshd 现在监听 {services.ssh_port()} 端口。",
        key="ssh_port.port",
    )


def ask_site() -> services.Site:
    answers = tui.ask_form(SITE_FIELDS, key_prefix="add_site", remember=settings.core.data_dir / "answers" / "add-site.json")
    return services.Site(domain=answers["domain"].strip().lower(), port=answers["port"], tls=answers["tls"], engine=answers["engine"])


async def show_system() -> None:
    release = ops.os_release()
    tui.table(
        [(key, release.get(key, "")) for key in ("PRETTY_NAME", "ID", "VERSION_ID")],
        headers=["项目", "值"],
        title="本机系统(只读)",
    )
    states = await services.unit_states()
    tui.info(f"沙箱:{ROOT}")
    tui.table([(unit, "运行中" if running else "未运行") for unit, running in states], headers=["服务", "状态"], title="沙箱里的服务")


async def change_ssh_port() -> None:
    port = ask_ssh_port()
    change = await services.change_ssh_port(port)
    if not change.changed:
        tui.info(f"sshd 已经监听 {port} 端口,没有改动。")
    elif change.restarted is None:
        tui.warning(f"已改为 {port} 端口,但 ssh 没有在运行,请手动启动。")
    else:
        tui.success(f"{change.restarted} 已重启,现在监听 {port} 端口。")


async def add_site() -> None:
    site = ask_site()
    # Not inside a spinner: with a sudo that asks for a password, the redraw would wipe its prompt.
    tui.info(f"写入 {site.domain} 并重载 {site.engine}…")
    reloaded = await services.add_site(site)
    if reloaded:
        tui.success(f"已添加 {site.domain},{site.engine} 已重载。")
    else:
        tui.warning(f"已添加 {site.domain};{site.engine} 没有在运行,站点在它下次启动时生效。")


async def show_operations() -> None:
    operations = await services.recent_operations()
    if not operations:
        tui.info("还没有操作记录。")
        return
    tui.table(
        [(operation.created_at.strftime("%Y-%m-%d %H:%M:%S"), operation.action, operation.detail) for operation in operations],
        headers=["时间(UTC)", "操作", "说明"],
        title="最近的操作",
    )


async def refresh_remote() -> None:
    with tui.spinner("下载远程文件"):
        refreshed = await remote.refresh()
    if refreshed.updated:
        tui.success(f"已更新 {len(refreshed.updated)} 个远程文件:{', '.join(refreshed.updated)}")
    for reason in refreshed.failed.values():
        tui.warning(f"没有更新,继续用缓存里的旧文件:{reason}")
    if not refreshed.updated and not refreshed.failed:
        tui.info("没有要更新的远程文件:基础地址是本地目录,或者还没有下载过。")


_run_hotfix = remote.script("hotfix.sh", str(ROOT), interpreter="bash")


async def hotfix() -> None:
    await _run_hotfix()
    await record("hotfix", "hotfix.sh")


async def reset_root() -> None:
    if not tui.confirm(f"把 {ROOT} 恢复成初始样例?现有改动都会丢失。", default=False):
        return
    await services.reset_root()
    tui.success(f"已重置 {ROOT}")


def main_menu() -> tui.Menu:
    return tui.Menu(
        "运维工具",
        [
            tui.Item("系统信息", action=show_system),
            tui.Item("SSH 端口", action=change_ssh_port),
            tui.Item("添加站点", action=add_site),
            tui.Item("Nginx", load=remote.menu("nginx.py")),
            tui.Item("安全检查", load=remote.menu("security.py")),
            tui.Item("内核参数", action=remote.action("tuning.py")),
            tui.Item("清理操作记录", action=remote.action("cleanup.py")),
            tui.Item("热修复", action=hotfix),
            tui.Item("操作记录", action=show_operations),
            tui.Item("更新远程文件", action=refresh_remote),
            tui.Item("重置沙箱", action=reset_root),
        ],
    )
