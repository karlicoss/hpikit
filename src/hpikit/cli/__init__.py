"""
Command line interfaces for exporters: cli.export for export scripts, cli.dal for DAL demos.
"""

from __future__ import annotations

import argparse


def format_epilog(parser: argparse.ArgumentParser, *, prog: str) -> str:
    """Render just the epilog for literate documentation, using the supplied command."""
    formatter = parser.formatter_class(prog=prog)
    formatter.add_text(parser.epilog)
    return formatter.format_help()
