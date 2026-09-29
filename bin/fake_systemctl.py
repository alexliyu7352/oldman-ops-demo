#!/usr/bin/env python3
"""Stand-in for systemctl in the sandbox: records every call and answers from a state directory.

    fake_systemctl.py --state DIR <systemctl arguments>

DIR/active lists the running units, one per line; DIR/calls.log gets one line per call.
Only the standard library: it runs under the system Python, as systemctl would.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] != "--state":
        print("usage: fake_systemctl.py --state DIR <systemctl arguments>", file=sys.stderr)
        return 2
    state = Path(argv[1])
    arguments = argv[2:]
    state.mkdir(parents=True, exist_ok=True)
    with (state / "calls.log").open("a", encoding="utf-8") as log:
        log.write(" ".join(arguments) + "\n")
    active_file = state / "active"
    active = set(active_file.read_text(encoding="utf-8").split()) if active_file.is_file() else set()

    verb = arguments[0]
    if verb == "is-active":
        return 0 if arguments[-1] in active else 3
    if verb == "daemon-reload":
        return 0
    if verb in ("restart", "reload") and len(arguments) == 2:
        unit = arguments[1]
        if verb == "reload" and unit not in active:
            print(f"{unit}.service is not active, cannot reload.", file=sys.stderr)
            return 1
        active.add(unit)
        active_file.write_text("".join(f"{name}\n" for name in sorted(active)), encoding="utf-8")
        return 0
    print(f"fake_systemctl.py does not know {' '.join(arguments)!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
