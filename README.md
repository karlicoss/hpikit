# hpikit

The library shared by [HPI](https://github.com/karlicoss/HPI) and its data exporters,
  e.g. [ghexport](https://github.com/karlicoss/ghexport) and [rexport](https://github.com/karlicoss/rexport).\
It doesn't depend on HPI, so the exporters work without it.

hpikit has no required dependencies.\
Its extras are:

- `optional`: [msgspec](https://github.com/msgspec/msgspec) for faster JSON parsing, and [kompress](https://github.com/karlicoss/kompress) for reading compressed files.
- `interactive`: IPython, for the DAL command line's `--interactive`.

## Modules

- `hpikit.json`: `load(path)`/`loads(data)`, and `Json` (`dict[str, Any]`) for a JSON object.\
  msgspec is used if it's installed, otherwise stdlib json with a warning; `HPIKIT_JSON_BACKEND=msgspec` or `stdlib` picks one explicitly.\
  [doc/json-backends.md](doc/json-backends.md) compares the parsers.
- `hpikit.paths`: `get_files` expands paths, globs and directories into a sorted tuple of paths, wrapping compressed ones in `kompress.CPath` if kompress is installed.\
  `as_paths` just normalizes a path or paths, keeping a `CPath` as it is; `Paths` is the type both accept.
- `hpikit.datetime`: checked `AwareDateTime`, `NaiveDateTime` and `Date` types, with the `aware()`, `naive()` and `date_only()` validators.\
  They're distinct types for type checkers but plain `datetime` and `date` at runtime, so [cachew](https://github.com/karlicoss/cachew) handles them.
- `hpikit.cli.export`: the command line of export scripts like `python3 -m ghexport.export`, with API parameters from a `--secrets` file or `--<param>` options.
- `hpikit.cli.dal`: the command line of DAL modules, e.g. `python3 -m ghexport.dal /path/to/exports/*.json.zst`.
- `hpikit.cli.format_epilog`: renders a parser's epilog for the literate READMEs.

## Development

Run checks with `tox -e ruff`, `tox -e format`, `tox -e tests`, `tox -e mypy` and `tox -e ty`.\
The setup follows [pymplate](https://github.com/karlicoss/pymplate).
