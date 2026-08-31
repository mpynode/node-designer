"""Child process for the bench-lock tests. Run as ``python -m`` script.

Usage: ``<py> _bench_lock_child.py <lockpath> <journal> <tag> <hold_s> <mode>``

Takes the global benchmark lock, appends ``ENTER <tag>`` to the journal, sleeps,
appends ``LEAVE <tag>``, and exits. ``mode=hang`` never leaves (the caller kills
it) so the stale-lock recovery can be exercised against a real SIGKILL.

Kept as a FILE (not an inline -c) because mutual exclusion has to be proven
across genuine processes; threads share an flock's open-file description in some
implementations and would prove nothing.
"""

import os
import sys
import time

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "scripts")))

from mpynode.native.ai import optimizer_live  # noqa: E402


def _append(journal, line):
    with open(journal, "a") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def main():
    lockpath, journal, tag, hold_s, mode = sys.argv[1:6]
    os.environ["MPYNODE_BENCH_LOCK"] = lockpath
    os.environ.setdefault("MPYNODE_BENCH_LOCK_TIMEOUT", "60")
    with optimizer_live.bench_lock(label=tag) as held:
        if not held:
            _append(journal, "NOTHELD " + tag)
            return 2
        _append(journal, "ENTER " + tag)
        if mode == "hang":
            _append(journal, "HANGING " + tag)
            while True:
                time.sleep(0.2)
        time.sleep(float(hold_s))
        _append(journal, "LEAVE " + tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
