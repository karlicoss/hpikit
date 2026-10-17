"""
Command line interface for DAL modules (e.g. python3 -m ghexport.dal), to try a DAL against exported data.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..paths import get_files


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='DAL (Data Access/Abstraction Layer)',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=100),
    )
    # todo link to exports post why multiple exports could be useful
    p.add_argument(
        'paths',
        nargs='+',
        metavar='path',
        help="Exported data: files, directories (all files inside) or globs, e.g. '/path/to/exports/*.ext'",
    )
    p.add_argument('-i', '--interactive', action='store_true', help='Start IPython session to play with data')

    p.epilog = """
You can use this DAL (Data Access/Abstraction Layer) module to access your exported data, even offline.
I elaborate on motivation behind it [here](https://beepb00p.xyz/exports.html#dal).

- the main use case is importing it as a Python module for **programmatic access** to your data.

  You can find some inspiration in [`my.`](https://beepb00p.xyz/mypkg.html) package that I'm using as an API to all my personal data.

- to test it against your export, simply run: `%(prog)s /path/to/export`

- you can also try it interactively in an IPython shell: `%(prog)s /path/to/export --interactive`

"""
    return p


def main[D](*, DAL: Callable[[tuple[Path, ...]], D], demo: Callable[[D], None] | None = None) -> None:
    """
    DAL is called with the tuple of paths found by get_files().
    For a DAL taking a single path, pass e.g. DAL=lambda paths: DAL(*paths).
    """
    p = make_parser()
    args = p.parse_args()

    # DALs read sources via read_text()/open(), and get_files() wraps compressed exports (e.g. arctee's .json.zst) in CPath if kompress is installed
    dal = DAL(get_files(args.paths))
    # logger.debug('using %s', sources)

    print(dal)
    # TODO autoreload would be nice... https://github.com/ipython/ipython/issues/1144
    # TODO maybe just launch through ipython in the first place?
    if args.interactive:
        import IPython  # type: ignore[import-not-found]  # ty: ignore[unresolved-import]

        IPython.embed(header="Feel free to mess with 'dal' object in the interactive shell")
    else:
        assert demo is not None, "No 'demo' in 'dal.py'?"
        demo(dal)
