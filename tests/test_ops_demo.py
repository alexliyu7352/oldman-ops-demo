"""The ops Demo end to end, in a copy of the project: the menu, the remote files and the commands.

Menus need a person, so a subprocess bootstraps the service and answers them with
`tui.simulate_input`; commands run through the real CLI with stdin closed and preset answers.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]

MIGRATE = """
from pathlib import Path

from oldman.db.migrations.commands import migrate
from oldman.db.migrations.project import load_migration_project


class Answers:
    is_interactive = False

    def choose(self, prompt, choices):
        assert "migration state" in prompt, prompt
        return "first use"

    def confirm(self, prompt, *, default=False):
        raise AssertionError(prompt)

    def text(self, prompt, *, default):
        raise AssertionError(prompt)


migrate(load_migration_project(Path.cwd()), Answers())
"""

# Answers the menu with `tui.simulate_input`; "^C" stands for Ctrl-C. Prints what the menu wrote as
# the last line; a remote script writes straight to this process's stdout, before it.
MENU_DRIVER = """
import asyncio
import json
import sys

from oldman import bootstrap_service

bootstrap_service("ops")

from apps.ops import menus, services
from oldman.cli import tui
from oldman.db import db_manager

answers = [KeyboardInterrupt if answer == "^C" else answer for answer in json.loads(sys.argv[1])]


async def main():
    try:
        await tui.run_menu(menus.main_menu())
    finally:
        await db_manager.close()


services.prepare_root()
with tui.simulate_input(answers) as terminal:
    asyncio.run(main())
print(json.dumps({"stdout": terminal.stdout, "stderr": terminal.stderr, "unused": len(terminal.remaining)}))
"""


def environment(project: Path, **answers: str) -> dict[str, str]:
    """The test's own environment without presets it did not ask for, English framework texts."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("OLDMAN_ANSWER_") and key != "PROJECT_ROOT"}
    env.update(OLDMAN_CLI_LANGUAGE="en", PYTHONIOENCODING="utf-8", XDG_CONFIG_HOME=str(project / ".cli-config"))
    env.update(answers)
    return env


def run_python(project: Path, source: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source), *args],
        cwd=project,
        env=environment(project),
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def run_cli(project: Path, *args: str, **answers: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "oldman.cli", *args],
        cwd=project,
        env=environment(project, **answers),
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


class OpsDemoTestCase(unittest.TestCase):
    remote_base = "remote"

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "project"
        for name in ("apps", "bin", "config", "remote", "services"):
            shutil.copytree(ROOT / name, self.project / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("pyproject.toml", "run.sh"):
            shutil.copy2(ROOT / name, self.project / name)
        self.write_settings(self.remote_base)
        migrated = run_python(self.project, MIGRATE)
        self.assertEqual(0, migrated.returncode, migrated.stderr)

    def write_settings(self, remote_base: str) -> None:
        yaml = YAML()
        settings = yaml.load((ROOT / "data" / "ops_settings.example.yaml").read_text(encoding="utf-8"))
        settings["app_settings"]["ops"]["remote_base"] = remote_base
        (self.project / "data").mkdir(exist_ok=True)
        with (self.project / "data" / "ops_settings.yaml").open("w", encoding="utf-8") as stream:
            yaml.dump(settings, stream)

    def menu(self, *answers: str) -> dict[str, Any]:
        """Run the menu with these answers; the process's own stdout (scripts) comes back as "process"."""
        completed = run_python(self.project, MENU_DRIVER, json.dumps(list(answers)))
        self.assertEqual(0, completed.returncode, completed.stderr)
        *process, last = completed.stdout.splitlines()
        result = json.loads(last)
        result["process"] = "\n".join(process)
        self.assertEqual(0, result["unused"], result["stdout"])
        return result

    def sandbox(self, system_path: str) -> Path:
        return self.project / "var" / "root" / system_path.lstrip("/")

    def calls(self) -> list[str]:
        return self.sandbox("/run/fake-systemd/calls.log").read_text(encoding="utf-8").splitlines()

    def operations(self) -> list[str]:
        with sqlite3.connect(self.project / "data" / "ops.db") as connection:
            return [action for (action,) in connection.execute("SELECT action FROM ops_operation_log ORDER BY id")]


class LocalActionsTest(OpsDemoTestCase):
    def test_system_ssh_port_and_site_form(self) -> None:
        result = self.menu(
            "1",
            "2", "70000", "2222",
            "3", "Shop.Example.com", "", "y", "",
            "3", "", "^C",
            "9",
            "0",
        )  # fmt: skip
        output = result["stdout"]

        self.assertIn("PRETTY_NAME", output)
        self.assertIn("端口要在 1 到 65535 之间", output)
        self.assertIn("ssh 已重启,现在监听 2222 端口。", output)
        self.assertIn("Port 2222\n", self.sandbox("/etc/ssh/sshd_config").read_text())
        self.assertIn("ListenStream=2222", self.sandbox("/etc/systemd/system/ssh.socket.d/override.conf").read_text())
        self.assertIn("daemon-reload", self.calls())
        self.assertIn("restart ssh", self.calls())

        site = self.sandbox("/etc/nginx/sites-enabled/shop.example.com.conf").read_text()
        self.assertIn("listen 443 ssl;", site)
        self.assertIn("proxy_pass http://127.0.0.1:8000;", site)
        self.assertIn("reload nginx", self.calls())
        # The second form was cancelled at its second question and wrote nothing, but kept last time's answers.
        self.assertEqual(["example.org", "shop.example.com"], sorted(path.stem for path in self.sandbox("/etc/nginx/sites-enabled").iterdir()))
        remembered = json.loads((self.project / "data" / "answers" / "add-site.json").read_text())
        self.assertEqual("Shop.Example.com", remembered["domain"])

        self.assertIn("最近的操作", output)
        self.assertEqual(["ssh-port", "add-site"], self.operations())
        self.assertNotIn("✗", result["stderr"])

    def test_reset_puts_the_samples_back(self) -> None:
        self.menu("2", "2200", "11", "y", "0")
        self.assertIn("#Port 22\n", self.sandbox("/etc/ssh/sshd_config").read_text())
        self.assertFalse(self.sandbox("/etc/systemd/system").exists())
        self.assertEqual(["ssh-port", "reset-root"], self.operations())


class RemoteFilesTest(OpsDemoTestCase):
    def test_every_remote_file_from_a_local_directory(self) -> None:
        result = self.menu(
            "4", "2", "1", "y", "0",
            "5", "2", "", "1", "0",
            "6", "6",
            "7", "0", "y",
            "8",
            "0",
        )  # fmt: skip
        output = result["stdout"]

        self.assertFalse(self.sandbox("/etc/nginx/sites-enabled/example.org.conf").exists())
        self.assertIn("nginx 已重载。", output)
        sshd = self.sandbox("/etc/ssh/sshd_config").read_text()
        for setting in ("PermitRootLogin no", "PasswordAuthentication no", "X11Forwarding no"):
            self.assertIn(setting + "\n", sshd)
        self.assertIn("已修改 3 项,ssh 已重启。", output)

        sysctl = self.sandbox("/etc/sysctl.conf").read_text()
        self.assertIn("# >>> OPS_DEMO_TUNING\n", sysctl)
        self.assertIn("net.core.somaxconn = 4096\n", sysctl)
        self.assertIn("sysctl.conf 已经是推荐值,没有改动。", output)

        # The cleanup removed the three earlier rows, then the hotfix added its own.
        self.assertIn("已删除 3 条记录。", output)
        self.assertEqual(["cleanup", "hotfix"], self.operations())
        # The script's `read` found no terminal and took "no".
        self.assertIn("没有改动。", result["process"])
        self.assertFalse(self.sandbox("/etc/motd").exists())
        self.assertIn("reload nginx", self.calls())
        self.assertNotIn("✗", result["stderr"])


class RemoteFilesOverHttpTest(OpsDemoTestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "remote")))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.stop_server)
        self.remote_base = f"http://127.0.0.1:{self.server.server_address[1]}"
        super().setUp()

    def stop_server(self) -> None:
        if self.server.socket.fileno() != -1:
            self.server.shutdown()
            self.server.server_close()

    def test_downloaded_files_are_cached_and_work_offline(self) -> None:
        first = self.menu("6", "10", "0")
        self.assertIn("已写入 sysctl.conf。", first["stdout"])
        self.assertIn("已更新 2 个远程文件:data/sysctl.conf, tuning.py", first["stdout"])
        self.assertTrue((self.project / "data" / "remote").is_dir())

        self.stop_server()
        offline = self.menu("6", "10", "0")
        self.assertIn("sysctl.conf 已经是推荐值,没有改动。", offline["stdout"])
        self.assertIn("✗ Could not download", offline["stderr"])


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


class CommandsTest(OpsDemoTestCase):
    def test_ssh_port_runs_unattended_with_a_preset_answer(self) -> None:
        missing = run_cli(self.project, "ops", "ssh-port")
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("OLDMAN_ANSWER_SSH_PORT_PORT", missing.stderr)

        preset = run_cli(self.project, "ops", "ssh-port", OLDMAN_ANSWER_SSH_PORT_PORT="2200")
        self.assertEqual(0, preset.returncode, preset.stderr)
        self.assertIn("Port 2200\n", self.sandbox("/etc/ssh/sshd_config").read_text())

    def test_add_site_takes_the_form_from_presets_and_defaults(self) -> None:
        added = run_cli(self.project, "ops", "add-site", OLDMAN_ANSWER_ADD_SITE_DOMAIN="api.example.org", OLDMAN_ANSWER_ADD_SITE_PORT="9000")
        self.assertEqual(0, added.returncode, added.stderr)
        site = self.sandbox("/etc/nginx/sites-enabled/api.example.org.conf").read_text()
        self.assertIn("listen 80;", site)
        self.assertIn("proxy_pass http://127.0.0.1:9000;", site)

    def test_the_menu_needs_a_terminal(self) -> None:
        menu = run_cli(self.project, "ops", "menu")
        self.assertNotEqual(0, menu.returncode)
        self.assertIn("运维工具", menu.stderr)

    def test_report_writes_only_json_to_stdout(self) -> None:
        report = run_cli(self.project, "ops", "report")
        self.assertEqual(0, report.returncode, report.stderr)
        state = json.loads(report.stdout)
        self.assertEqual("22", state["ssh_port"])
        self.assertEqual(["example.org"], state["sites"])
        self.assertEqual({"ssh": True, "nginx": True, "openresty": False}, state["units"])
        self.assertIn("检查服务", report.stderr)


if __name__ == "__main__":
    unittest.main()
