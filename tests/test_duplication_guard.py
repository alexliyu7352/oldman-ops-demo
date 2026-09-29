"""这个仓库只允许出现自己的业务逻辑，框架已经有的东西不再复制一份。"""

from __future__ import annotations

import unittest
from pathlib import Path

import oldman
from oldman.testing.duplication import duplicate_functions, identical_files

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = Path(oldman.__file__).resolve().parent
# 远程文件和假 systemctl 也是本项目的代码，最容易在里面顺手抄一段框架实现。
PROJECT_SOURCES = (ROOT / "apps", ROOT / "config", ROOT / "services", ROOT / "remote", ROOT / "bin")

# 还没有搬走的重复，逐条写明原因；修掉一条就从这里删掉一条。
ALLOWED_FRAMEWORK_DUPLICATES: frozenset[str] = frozenset()


class ProjectDoesNotCopyTheFrameworkTest(unittest.TestCase):
    def test_no_project_function_repeats_a_framework_implementation(self) -> None:
        unexpected = [
            item.describe(left_root=ROOT, right_root=FRAMEWORK.parent)
            for source in PROJECT_SOURCES
            for item in duplicate_functions(source, FRAMEWORK, min_lines=6)
            if item.name not in ALLOWED_FRAMEWORK_DUPLICATES
        ]
        self.assertEqual([], unexpected)

    def test_no_project_file_is_a_byte_copy_of_a_framework_file(self) -> None:
        matches = [
            item.describe(left_root=ROOT, right_root=FRAMEWORK.parent)
            for source in PROJECT_SOURCES
            for item in identical_files(source, FRAMEWORK, suffixes=(".py",))
        ]
        self.assertEqual([], matches)


if __name__ == "__main__":
    unittest.main()
