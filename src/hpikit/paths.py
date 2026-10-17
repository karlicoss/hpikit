"""
Finding input files from paths, directories and globs, so that compressed ones read transparently.
"""

from __future__ import annotations

import importlib.util
import os
import warnings
from collections.abc import Iterable, Sequence
from glob import glob as do_glob
from pathlib import Path

type Paths = Sequence[Path | str] | Path | str


DEFAULT_GLOB = '*'


def as_paths(paths: Paths) -> tuple[Path, ...]:
    """
    Normalize a path, a string, or a sequence of them, to a tuple of Path objects, without touching the filesystem.
    A single string is one path, even though str is itself a sequence.

    Path objects are kept as they are, including subclasses: this is mainly to support the kompress.CPath hack.
    Otherwise if we do Path(CPath(...)), it will ruin the decompression hack.
    See https://github.com/karlicoss/kompress/blob/397b2306fde2c7310aba8ffae72284fbd390876e/src/kompress/tests/kompress.py#L16-L62
      for how CPath decompresses transparently.
    """
    if isinstance(paths, Path):
        return (paths,)
    if isinstance(paths, str):
        return (Path(paths),)
    return tuple(p if isinstance(p, Path) else Path(p) for p in paths)


def get_files(
    pp: Paths,
    glob: str = DEFAULT_GLOB,
    *,
    sort: bool = True,
    guess_compression: bool | None = None,
) -> tuple[Path, ...]:
    """
    Helper function to avoid boilerplate and 'discover' files in directories.

    :param: sort: Only applies to recursive/glob file discovery.
                  Otherwise, the order specified in arguments is preserved.
    :param: guess_compression: Wrap compressed files in kompress.CPath, so that they're decompressed transparently when read.
                               None does that only if kompress is installed, whereas True requires it.

    :return: Tuple of Path objects.
             Tuple instead of list is a bit friendlier for hashing/caching.
    """
    # TODO some wrapper to assert iterator isn't empty?
    if pp == '':
        # special case -- makes sense for optional data sources, etc
        return ()  # early return to prevent warnings etc
    sources = as_paths(pp)

    paths: list[Path] = []
    for src in sources:
        if len(src.parts) > 0 and src.parts[0] == '~':
            src = src.expanduser()
        # note: glob handled first, because e.g. on Windows asterisk makes is_dir unhappy
        gs = str(src)
        if '*' in gs:
            if glob != DEFAULT_GLOB:
                warnings.warn(f"treating {gs} as glob path. Explicit glob={glob} argument is ignored!", stacklevel=2)
            globbed = do_glob(gs)  # noqa: PTH207
            if sort:
                globbed = sorted(globbed)
            paths.extend(map(Path, globbed))
        elif os.path.isdir(str(src)):  # noqa: PTH112
            # NOTE: we're using os.path here on purpose instead of src.is_dir
            # the reason is is_dir for archives might return True and then
            # this clause would try globbing insize the archives
            # this is generally undesirable (since modules handle archives themselves)

            # todo not sure if should be recursive?
            # note: glob='**/*.ext' works without any changes.. so perhaps it's ok as it is
            gp: Iterable[Path] = src.glob(glob)
            if sort:
                gp = sorted(gp)
            paths.extend(gp)
        else:
            assert src.exists(), src
            # todo assert matches glob??
            paths.append(src)

    if len(paths) == 0:
        # todo make it conditionally defensive based on some global settings
        # stacklevel points at the caller (e.g. a module's inputs()), which helps figure out what config caused it
        warnings.warn(
            f'no paths were matched against {pp}. This might result in missing data. Likely, the directory you passed is empty.',
            stacklevel=2,
        )

    if guess_compression is None:
        # optional dependency, see the 'optional' extra
        # without it, compressed files are returned as they are, and reading them fails later
        guess_compression = importlib.util.find_spec('kompress') is not None
    if guess_compression:
        from kompress import CPath, is_compressed

        # note: ideally we'd just wrap everything in CPath for simplicity, however
        # - it doesn't preserve original Path/str if not compressed -- perhaps should fix __new__ method
        # - currently, rb mode isn't handled correctly? https://github.com/karlicoss/kompress/issues/22
        paths = [(CPath(p) if is_compressed(p) else p) for p in paths]
    return tuple(paths)
