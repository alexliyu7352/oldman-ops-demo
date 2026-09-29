"""The tool's commands: the menu, two questions that can be preset for unattended runs, and a JSON report."""

from __future__ import annotations

import json

from oldman.cli import Command, tui

from apps.ops import menus, services
from apps.ops.toolkit import ROOT


def _prepare() -> None:
    if services.prepare_root():
        tui.info(f"已从样例创建沙箱 {ROOT}")


class OpenMenu(Command):
    """The maintenance menu; with --once it ends after one action."""

    name = "menu"
    help = "打开运维菜单;--once 执行一个动作后结束。"

    async def handle(self, once: bool = False) -> None:
        _prepare()
        await tui.run_menu(menus.main_menu(), after_action="exit" if once else "return")


class SshPort(Command):
    """Change sshd's port; OLDMAN_ANSWER_SSH_PORT_PORT answers the question in a script."""

    name = "ssh-port"
    help = "修改 sshd 监听的端口。"

    async def handle(self) -> None:
        _prepare()
        await menus.change_ssh_port()


class AddSite(Command):
    """Add a site; OLDMAN_ANSWER_ADD_SITE_<FIELD> answers the form in a script."""

    name = "add-site"
    help = "添加一个反向代理站点。"

    async def handle(self) -> None:
        _prepare()
        await menus.add_site()


class Report(Command):
    """The sandbox's state as JSON on stdout; everything else goes to stderr."""

    name = "report"
    help = "以 JSON 输出沙箱的当前状态。"
    raw_stdout = True

    async def handle(self) -> None:
        _prepare()
        with tui.spinner("检查服务"):
            state = await services.report()
        tui.echo(json.dumps(state, ensure_ascii=False, indent=2))
