from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from ..export import dump, get_params, make_parser


def parse(params: list[str], argv: list[str]) -> tuple[argparse.Namespace, dict[str, Any]]:
    parser = make_parser(description='test exporter', params=params)
    args = parser.parse_args(argv)
    return args, get_params(parser, args)


def test_parser_help_preserves_manual_formatting() -> None:
    description = 'first line\n\n    indented line\nsecond line'
    parser = make_parser(description=description, params=[])
    parser.prog = 'test-exporter'

    help_text = parser.format_help()

    assert description in help_text


def test_parser_help_preserves_wide_lines() -> None:
    description = ' '.join(['word'] * 18)
    assert len(description) == 89
    parser = make_parser(description=description, params=[])
    parser.prog = 'test-exporter'

    help_text = parser.format_help()

    assert description in help_text


def test_export_help_uses_prog() -> None:
    parser = make_parser(description='Example exporter', params=['token'])
    parser.prog = 'example-export'

    help_text = parser.format_help()

    assert 'usage: example-export ' in help_text
    assert 'example-export --secrets /path/to/secrets.py' in help_text


def test_reads_params_from_secrets_file(tmp_path: Path) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('username = "alice"\npassword = "secret"\n')

    _, params = parse(['username', 'password'], ['--secrets', str(secrets)])

    assert params == {
        'username': 'alice',
        'password': 'secret',
    }


def test_reads_multiple_params_from_command_line() -> None:
    _, params = parse(
        ['username', 'password'],
        [
            '--username',
            'alice',
            '--password',
            'secret',
        ],
    )

    assert params == {
        'username': 'alice',
        'password': 'secret',
    }


def test_hyphenated_param_uses_normalized_name() -> None:
    _, params = parse(['token-path'], ['--token-path', '/tmp/token'])

    assert params == {'token_path': '/tmp/token'}


def test_hyphenated_param_uses_normalized_name_in_secrets_file(tmp_path: Path) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('token_path = "/tmp/token"\n')

    _, params = parse(['token-path'], ['--secrets', str(secrets)])

    assert params == {'token_path': '/tmp/token'}


def parse_error(params: list[str], argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as e:
        parse(params, argv)

    assert e.value.code == 2
    return capsys.readouterr().err


def test_rejects_mixing_secrets_file_and_command_line_params(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('token = "SECRET"\n')

    error = parse_error(['token'], ['--secrets', str(secrets), '--token', 'TOKEN'], capsys)

    assert 'Please use either --secrets file or individual --param arguments' in error


def test_missing_param_warning_lists_only_missing_params() -> None:
    with pytest.warns(UserWarning, match='Missing API parameters: password'):
        _, params = parse(['username', 'password'], ['--username', 'alice'])

    assert params == {'username': 'alice'}


def test_secrets_error_does_not_print_loaded_values(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('username = "alice"\ntoken = "SENSITIVE_VALUE"\n')

    error = parse_error(['username', 'password'], ['--secrets', str(secrets)], capsys)

    assert f"Couldn't extract API parameters from file {secrets}: password" in error
    assert 'alice' not in error
    assert 'SENSITIVE_VALUE' not in error


def test_dump_writes_to_stdout_without_output_path(capsys: pytest.CaptureFixture[str]) -> None:
    args, _ = parse(['token'], ['--token', 'SECRET'])

    dump('{"ok": true}', path=args.path)

    captured = capsys.readouterr()
    assert captured.out == '{"ok": true}'
    assert captured.err == ''


def test_dump_writes_file_and_reports_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / 'export.json'

    args, _ = parse(['token'], ['--token', 'SECRET', str(output)])
    dump('{"ok": true}', path=args.path)

    assert output.read_text() == '{"ok": true}'
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == f'saved data to {output}\n'
