"""
Command line interface for export scripts (e.g. python3 -m ghexport.export).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# parser default holding the API parameter names, so get_params() knows which options to collect
_PARAMS_KEY = '_export_params'


def make_parser(
    *,
    description: str,
    params: Sequence[str],
    extra_usage: str | None = None,
) -> argparse.ArgumentParser:
    """
    ArgumentParser for an export script.
    It takes API parameters either from a --secrets file or as individual --<param> options, and an optional output path.
    Add exporter-specific arguments to the returned parser, then call get_params() and dump() after parsing.
    """
    parser = argparse.ArgumentParser(
        description=description,
        # just more reasonable default for literate usage
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=100),
    )
    parser.add_argument(
        '--secrets',
        metavar='SECRETS_FILE',
        type=Path,
        required=False,
        help='.py file containing API parameters',
    )
    gr = parser.add_argument_group('API parameters')
    param_actions = [gr.add_argument('--' + param, type=str) for param in params]
    parser.set_defaults(**{_PARAMS_KEY: tuple(action.dest for action in param_actions)})
    parser.epilog = _export_epilog(param_actions=param_actions, extra_usage=extra_usage)
    parser.add_argument(
        'path',
        type=Path,
        nargs='?',
        help='Optional path where exported data will be dumped, otherwise printed to stdout',
    )
    return parser


def get_params(parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict[str, Any]:
    """
    API parameters for a parser created by make_parser(), from the --secrets file or the individual options.
    Missing parameters only cause a warning, since e.g. a login flow may need just some of them.
    """
    params: tuple[str, ...] = parser.get_default(_PARAMS_KEY)
    secrets_file: Path | None = args.secrets
    cmdline_params = {p: getattr(args, p) for p in params if getattr(args, p) is not None}
    if secrets_file is not None and len(cmdline_params) > 0:
        parser.error("Please use either --secrets file or individual --param arguments (see --help)")

    if secrets_file is None:
        params_dict = cmdline_params
    else:
        obj: dict[str, Any] = {}
        # we control the file with secrets so exec is fine
        exec(secrets_file.read_text(), {}, obj)
        missing_from_file = [p for p in params if p not in obj]
        if len(missing_from_file) > 0:
            parser.error(f"Couldn't extract API parameters from file {secrets_file}: {', '.join(missing_from_file)}")
        params_dict = {p: obj[p] for p in params}

    missing_params = [p for p in params if p not in params_dict]
    if len(missing_params) > 0:
        warnings.warn(
            f"""
    Missing API parameters: {', '.join(missing_params)}
    This might cause issues with export (see README for setup instructions).
""".rstrip(),
            stacklevel=2,
        )
    return params_dict


def dump(data: str, *, path: Path | None) -> None:
    """Write the exported data to path, or to stdout if it's None (e.g. the output path argument wasn't passed)."""
    if path is None:
        sys.stdout.write(data)
    else:
        path.write_text(data)
        print(f'saved data to {path}', file=sys.stderr)


def _export_epilog(
    *,
    param_actions: Sequence[argparse.Action],
    extra_usage: str | None,
) -> str:
    paramss = ' '.join(f'{action.option_strings[0]} <{action.dest}>' for action in param_actions)

    sep = '\n    '
    secrets_example = sep + sep.join(f'{action.dest} = "{action.dest.upper()}"' for action in param_actions)

    epilog = f'''
Usage:

**Recommended**: create `secrets.py` keeping your API parameters, e.g.:

{secrets_example}


After that, use:

    %(prog)s --secrets /path/to/secrets.py

That way you type less and have control over where you keep your plaintext secrets.

**Alternatively**, you can pass parameters directly, e.g.

    %(prog)s {paramss}

However, this is verbose and prone to leaking your keys/tokens/passwords in shell history.

'''

    if extra_usage is not None:
        epilog += extra_usage

    epilog += '''

I **highly** recommend checking exported files at least once just to make sure they contain everything you expect from your export.
If they don't, please feel free to ask or raise an issue!
    '''
    return epilog
