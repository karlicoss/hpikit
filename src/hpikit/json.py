"""
JSON parsing for DALs.

msgspec is used by default if it's installed, e.g. via hpikit's 'optional' extra.
Otherwise parsing falls back to the standard library's json module, with a warning shown once per process.
Set HPIKIT_JSON_BACKEND=msgspec to require msgspec, failing if it's missing, or HPIKIT_JSON_BACKEND=stdlib to always use the standard library.
The variable is read on every call, and process-pool workers inherit it from the environment.
No other parsers are tried, since parsers differ in speed, in free-threading support, and even in the values they return.
For the same reason only the selected backend is imported: importing a parser without free-threading support re-enables the GIL.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

type Json = dict[str, Any]  # todo Mapping?
"""
A JSON object, e.g. a single exported item.
load() and loads() return Any instead, since the top level of a file can also be a list.
"""

BACKEND_ENV_VAR = 'HPIKIT_JSON_BACKEND'

# Tradeoffs below were measured on real 6-12 MB exports (Reddit, GitHub, Hypothesis) with Python 3.14 in October 2026.
# See doc/json-backends.md in the hpikit repository for the full comparison tables.


# Default when installed: the fastest or on par with it, about 3x faster than stdlib, and with low peak memory.
# Supports free-threaded Python and keeps integers beyond 64 bits exact.
# Rejects NaN (not valid JSON), lone surrogates and a UTF-8 BOM.
# A lone surrogate is an escaped half of a UTF-16 surrogate pair without its other half,
#   e.g. "\ud83d" from text truncated in the middle of an emoji, so it isn't valid Unicode.
def _msgspec(data: bytes | str) -> Any:
    import msgspec

    return msgspec.json.decode(data)


# About 3x slower than msgspec, but needs no dependencies.
# Also the most lenient: the only one accepting a UTF-8 BOM, and it accepts NaN and lone surrogates.
# A lone surrogate ends up in the returned str, and encoding that str to UTF-8 later fails.
def _stdlib(data: bytes | str) -> Any:
    return json.loads(data)


_BACKENDS: dict[str, Callable[[bytes | str], Any]] = {
    'msgspec': _msgspec,
    'stdlib': _stdlib,
}
# Not offered:
# - orjson: slightly slower than msgspec with higher peak memory, silently turns integers beyond 64 bits into floats,
#     and refuses to build for free-threaded Python.
#   Its strength is serialization, e.g. of dataclasses and datetimes in HPI's my.core.serialize, rather than parsing.
# - ujson: slower than msgspec, and upstream keeps it in maintenance-only mode for security reasons, recommending orjson.
# - jiter: on par with msgspec, with even lower memory, and it scaled best over threads on free-threaded Python.
#   Worth adding if that ever matters.
# - ijson: streams, but was about twice as slow as msgspec even when only one key was needed.
#   Use it directly where a file doesn't fit comfortably in memory.


def _backend() -> Callable[[bytes | str], Any]:
    name = os.environ.get(BACKEND_ENV_VAR)
    if name is None:
        return _default_backend()
    backend = _BACKENDS.get(name)
    assert backend is not None, f'{BACKEND_ENV_VAR}={name!r}, expected one of {sorted(_BACKENDS)}'
    return backend


# cached, so that the fallback warning is only shown once per process
@functools.cache
def _default_backend() -> Callable[[bytes | str], Any]:
    if importlib.util.find_spec('msgspec') is None:
        warnings.warn(
            f"msgspec isn't installed, falling back to the slower stdlib json. "
            f"Install it, e.g. via hpikit[optional], or set {BACKEND_ENV_VAR}=stdlib to use stdlib json without this warning.",
            stacklevel=4,  # the caller of load() or loads()
        )
        return _stdlib
    return _msgspec


def loads(data: bytes | str) -> Any:
    return _backend()(data)


def load(path: Path) -> Any:
    """
    Parse the whole file at once.
    Unlike json.load(), this takes a path rather than a file object.
    It's read with read_bytes(), so a kompress.CPath is decompressed transparently.
    """
    return _backend()(path.read_bytes())
