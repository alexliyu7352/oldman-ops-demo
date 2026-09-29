"""sshd 安全检查:列出不安全的设置,选择要修复的项。"""

from __future__ import annotations

from oldman import ops
from oldman.cli import tui

from apps.ops.services import SSHD_CONFIG
from apps.ops.toolkit import SYSTEMCTL, path, record

# 设置项、安全的值、说明;没写这一项时 sshd 的默认值。
CHECKS = (
    ("PermitRootLogin", "no", "禁止 root 直接登录", "prohibit-password"),
    ("PasswordAuthentication", "no", "只允许密钥登录", "yes"),
    ("X11Forwarding", "no", "关闭 X11 转发", "no"),
)


def current(key: str, default: str) -> str:
    return ops.read_directive(path(SSHD_CONFIG), key, default) or default


def unsafe() -> list[tuple[str, str, str]]:
    return [(key, safe, text) for key, safe, text, default in CHECKS if current(key, default) != safe]


async def audit() -> None:
    tui.table(
        [(text, key, current(key, default), "正常" if current(key, default) == safe else f"应为 {safe}") for key, safe, text, default in CHECKS],
        headers=["检查", "设置", "现在", "结果"],
        title="sshd_config",
    )


async def fix() -> None:
    problems = unsafe()
    if not problems:
        tui.success("没有需要修复的设置。")
        return
    chosen = tui.choose_many(
        "修复哪些设置(编号用逗号或空格隔开)",
        [(key, f"{text}:{key} {safe}") for key, safe, text in problems],
        default=[key for key, _safe, _text in problems],
    )
    if not chosen:
        return
    safe_values = {key: safe for key, safe, _text in problems}
    with tui.progress("修改 sshd_config", total=len(chosen)) as bar:
        for key in chosen:
            ops.set_directive(path(SSHD_CONFIG), key, safe_values[key], follow_symlinks=False)
            bar.advance()
    restarted = await ops.systemd.restart("ssh", "sshd", command=SYSTEMCTL)
    await record("security-fix", ", ".join(chosen))
    if restarted is None:
        tui.warning("已修改,但 ssh 没有在运行。")
    else:
        tui.success(f"已修改 {len(chosen)} 项,{restarted} 已重启。")


async def menu() -> tui.Menu:
    count = len(unsafe())
    title = "安全检查:全部正常" if not count else f"安全检查:{count} 项需要修复"
    return tui.Menu(title, [tui.Item("查看检查结果", action=audit), tui.Item("修复", action=fix)])
