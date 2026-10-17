from __future__ import annotations

import gzip
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from ..dal import main, make_parser


def test_dal_help_uses_prog() -> None:
    # prog is set explicitly: since Python 3.14, argparse derives the default from how __main__ was run, e.g. 'python -m pytest'
    parser = make_parser()
    parser.prog = 'exampleexport.dal'

    help_text = parser.format_help()

    assert 'usage: exampleexport.dal ' in help_text
    assert 'exampleexport.dal /path/to/export' in help_text


@pytest.mark.parametrize(
    'paths',
    [
        ['.'],  # a directory
        ['a.json', 'b.json.gz'],  # e.g. an unquoted glob, expanded by the shell
        ['*.json*'],  # a quoted glob, expanded by get_files()
    ],
)
def test_reads_compressed_sources(
    paths: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / 'a.json').write_text('[1]')
    with gzip.open(tmp_path / 'b.json.gz', 'wt') as fo:
        fo.write('[2]')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['exampleexport.dal', *paths])

    class DAL:
        def __init__(self, sources: Sequence[Path]) -> None:
            self.sources = sources

    def demo(dal: DAL) -> None:
        print([source.read_text() for source in dal.sources])

    main(DAL=DAL, demo=demo)

    assert capsys.readouterr().out.splitlines()[-1] == "['[1]', '[2]']"
