import os
import sys
import zipfile
from pathlib import Path

import pytest
from kompress import CPath
from kompress.zip import ZipPath

from ..paths import as_paths, get_files


def test_as_paths() -> None:
    '''
    Paths are normalized without touching the filesystem, and Path subclasses such as CPath are kept as they are.
    '''
    # a single string is one path, even though str is a sequence too
    assert as_paths('export.json') == (Path('export.json'),)

    cpath = CPath('export.json.zst')
    [path, kept] = as_paths(['export.json', cpath])
    assert path == Path('export.json')
    assert kept is cpath


def test_single_file(tmp_path_cwd: Path) -> None:
    '''
    Regular file path is just returned as is.
    '''

    # Exception if it doesn't exist"
    with pytest.raises(Exception):
        get_files('file.ext')

    create_tree('file.ext')

    # Couple of things:
    # 1. Return type is a tuple, it's friendlier for hashing/caching
    # 2. It always returns pathlib.Path instead of plain strings
    assert get_files('file.ext') == (Path('file.ext'),)

    is_windows = os.name == 'nt'
    # if the path starts with ~, we expand it
    if not is_windows:  # windows doesn't have bashrc.. ugh
        assert get_files('~/.bashrc') == (Path('~').expanduser() / '.bashrc',)


def test_multiple_files(tmp_path_cwd: Path) -> None:
    '''
    If you pass a directory/multiple directories, it flattens the contents
    '''
    create_tree('''
dir1/
dir1/zzz
dir1/yyy
dir2/
dir2/mmm
dir2/nnn
dir3/
dir3/ttt
''')
    # create('/tmp/hpi_test/dir1/whatever/') # TODO not sure about this... should really allow extra dirs

    # it takes in Path as well as str
    assert get_files([Path('dir3'), 'dir1']) == (
        Path('dir3/ttt'),
        Path('dir1/yyy'),
        Path('dir1/zzz'),
    )


def test_sort(tmp_path_cwd: Path) -> None:
    """
    Checks that sorting only applies to globbed files.
    Otherwise the order specified in get_files should be preserved.
    """
    create_tree('''
dir1/
dir1/file2
dir1/file1
dir2/
dir2/subdir21/
dir2/subdir21/file2
dir2/subdir21/file1
dir2/subdir22/
dir2/subdir22/file2
dir2/subdir22/file1
dir3/
dir3/subdir31/
dir3/subdir31/file
dir3/subdir32/
dir3/subdir32/file
''')

    assert get_files(
        [
            'dir3/subdir32/file',
            'dir2/*/file*',
            'dir3/subdir31/file',
            'dir1',
        ]
    ) == (
        Path('dir3/subdir32/file'),
        # files under a glob should be sorted
        Path('dir2/subdir21/file1'),
        Path('dir2/subdir21/file2'),
        Path('dir2/subdir22/file1'),
        Path('dir2/subdir22/file2'),
        #
        Path('dir3/subdir31/file'),
        Path('dir1/file1'),
        Path('dir1/file2'),
    )


def test_explicit_glob(tmp_path_cwd: Path) -> None:
    '''
    You can pass a glob to restrict the extensions
    '''

    create_tree('''
file_3.gz
file_2.gz
ignoreme
file.gz
''')

    expected = (Path('file_2.gz'), Path('file_3.gz'))
    assert get_files('.', 'file_*.gz') == expected

    # named argument should work too
    assert get_files('.', glob='file_*.gz') == expected


def test_implicit_glob(tmp_path_cwd: Path) -> None:
    '''
    Asterisk in the path results in globbing too.
    '''
    # todo hopefully that makes sense? dunno why would anyone actually rely on asteriscs in names..
    # this is very convenient in configs, so people don't have to use some special types

    create_tree('''
123/
123/dummy
123/file.gz
456/
456/dummy
456/file.gz
''')

    assert get_files(['*/*.gz']) == (
        Path('123/file.gz'),
        Path('456/file.gz'),
    )


def test_no_files(tmp_path_cwd: Path) -> None:
    '''
    Test for empty matches. They work, but should result in warning
    '''
    assert get_files('') == ()

    # todo test these for warnings?
    assert get_files([]) == ()
    assert get_files('bad*glob') == ()


def test_compressed(tmp_path_cwd: Path) -> None:
    from typing import cast

    file1 = tmp_path_cwd / 'file_1.zstd'
    file2 = tmp_path_cwd / 'file_2.zip'
    file3 = tmp_path_cwd / 'file_3.csv'

    file1.touch()
    with zipfile.ZipFile(file2, 'w') as zf:
        zf.writestr('path/in/archive', 'data in zip')
    file3.touch()

    results = get_files(tmp_path_cwd)
    [res1, res2, res3] = results
    assert isinstance(res1, CPath)
    assert isinstance(res2, ZipPath)  # NOTE this didn't work on vendorized kompress, but it's fine, was never used?
    assert not isinstance(res3, CPath)

    results = get_files(
        [CPath(file1), cast(Path, ZipPath(file2)), file3],
        # sorting a mixture of ZipPath/Path was broken in old kompress
        # it almost never happened though (usually it's only a bunch of ZipPath, so not a huge issue)
        sort=False,
    )
    [res1, res2, res3] = results
    assert isinstance(res1, CPath)
    assert isinstance(res2, ZipPath)
    assert not isinstance(res3, CPath)


def create_tree(spec: str) -> None:
    for line in spec.strip().splitlines():
        line = line.strip()
        if len(line) == 0:
            continue
        if line.endswith('/'):  # dir
            Path(line).mkdir()
        else:
            Path(line).touch()


@pytest.fixture
def tmp_path_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Like tmp_path, but also changes the current working directory to it.
    """
    monkeypatch.chdir(tmp_path)  # restored after the test
    return tmp_path


# TODO not sure if should uniquify if the filenames end up same?
# TODO not sure about the symlinks? and hidden files?


def test_without_kompress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    '''
    kompress is optional: without it, compressed files are returned unwrapped by default.
    guess_compression=True requires it.
    '''
    (tmp_path / 'file.json').touch()
    (tmp_path / 'file.json.zst').touch()
    # as if kompress wasn't installed: importing it now raises ModuleNotFoundError
    monkeypatch.setitem(sys.modules, 'kompress', None)

    found = get_files(tmp_path)
    assert found == (tmp_path / 'file.json', tmp_path / 'file.json.zst')
    assert not any(isinstance(p, CPath) for p in found)

    assert get_files(tmp_path, guess_compression=False) == found
    with pytest.raises(ModuleNotFoundError, match='kompress'):
        get_files(tmp_path, guess_compression=True)
