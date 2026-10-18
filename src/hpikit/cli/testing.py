"""
Test helpers for exporters' command lines.
"""

from __future__ import annotations

import subprocess
import sys


def check_cli_starts(module: str) -> None:
    """
    Smoke test that `python -m <module> --help` works: the module imports in a fresh interpreter,
      and its parser builds and prints its help.
    Catches mistakes that type checkers don't, e.g. an option clashing with one hpikit already adds, or a stray % in a help string.
    """
    # stderr isn't captured, so that pytest shows the traceback if it fails
    result = subprocess.run([sys.executable, '-m', module, '--help'], check=True, stdout=subprocess.PIPE, text=True)
    # otherwise a module without a __main__ block would pass without building its parser
    assert result.stdout.startswith('usage:'), result.stdout
