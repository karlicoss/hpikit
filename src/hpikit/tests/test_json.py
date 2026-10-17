from __future__ import annotations

import math
import os
import subprocess
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..json import _BACKENDS, BACKEND_ENV_VAR, _default_backend, load, loads


@pytest.fixture(autouse=True)
def uncached_default() -> Iterator[None]:
    """
    The default backend is resolved once per process, so each test here starts from a fresh resolution.
    Otherwise a test that changes what's installed would see whatever an earlier test resolved.
    """
    _default_backend.cache_clear()
    yield
    _default_backend.cache_clear()


@pytest.mark.parametrize('backend', sorted(_BACKENDS))
def test_load(backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BACKEND_ENV_VAR, backend)
    path = tmp_path / 'export.json'
    write_kwargs = {'encoding': 'utf-8'} if os.name == 'nt' and sys.version_info < (3, 15) else {}
    path.write_text('{"records": [{"id": 1, "title": "naïve 🙂", "score": 0.5, "edited": null}]}', **write_kwargs)

    assert load(path) == {'records': [{'id': 1, 'title': 'naïve 🙂', 'score': 0.5, 'edited': None}]}


def test_default_keeps_large_integers_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Integers beyond 64 bits stay exact, whereas orjson would silently turn them into floats.
    """
    monkeypatch.delenv(BACKEND_ENV_VAR, raising=False)
    assert loads(b'[1180591620717411303424]') == [2**70]


def test_imports_only_selected_backend() -> None:
    """
    With stdlib selected, msgspec is never imported.
    On free-threaded Python, importing a parser without free-threading support would re-enable the GIL.
    """
    # a fresh interpreter, since other tests have already imported msgspec into this one
    code = 'import sys; from hpikit.json import loads; loads(b"[]"); print("msgspec" in sys.modules)'
    stdout = subprocess.check_output(
        [sys.executable, '-c', code],
        env={**os.environ, BACKEND_ENV_VAR: 'stdlib'},
        text=True,
    )
    assert stdout == 'False\n'


def test_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BACKEND_ENV_VAR, 'simdjson')
    with pytest.raises(AssertionError, match='simdjson'):
        loads(b'[]')


def test_default_falls_back_to_stdlib(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Without msgspec, the default is stdlib json, with a warning shown once and attributed to the caller.
    """
    monkeypatch.delenv(BACKEND_ENV_VAR, raising=False)
    # as if msgspec wasn't installed: importing it now raises ModuleNotFoundError
    monkeypatch.setitem(sys.modules, 'msgspec', None)

    with pytest.warns(UserWarning, match="msgspec isn't installed") as record:
        # only stdlib json accepts NaN, so this shows which backend parsed it
        assert math.isnan(loads(b'[NaN]')[0])
    [warning] = record
    assert warning.filename == __file__

    # only warns once per process
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert loads(b'[1]') == [1]


def test_requested_msgspec_must_be_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    HPIKIT_JSON_BACKEND=msgspec fails without msgspec, instead of falling back to stdlib json.
    """
    monkeypatch.setenv(BACKEND_ENV_VAR, 'msgspec')
    # as if msgspec wasn't installed: importing it now raises ModuleNotFoundError
    monkeypatch.setitem(sys.modules, 'msgspec', None)

    with pytest.raises(ModuleNotFoundError, match='msgspec'):
        loads(b'[]')
