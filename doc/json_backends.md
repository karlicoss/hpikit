# JSON parser comparison

Measured on 2026-10-17 to choose the `hpikit.json` backend, on Linux x86_64 with 8 cores.
Python was 3.14.7 with the GIL ("3.14") and 3.14.8 free-threaded ("3.14t").
Versions: msgspec 0.22.0, orjson 3.13.0, ujson 6.0.0, jiter 0.17.0, ijson 3.6.0 (yajl2_c backend), simplejson 4.2.0, python-rapidjson 1.25.
These are single-machine measurements, so treat differences of a few percent as noise and recheck before relying on them.

## Summary

| Parser           | Verdict       | Why                                                                               |
|------------------|---------------|-----------------------------------------------------------------------------------|
| msgspec          | default       | fastest or on par, low memory, supports free-threading, exact large integers      |
| stdlib           | fallback      | about 3x slower, no dependencies, the most lenient                                |
| jiter            | candidate     | on par with msgspec, lowest memory on real exports, best thread scaling on 3.14t  |
| orjson           | no            | slightly slower, higher peak memory, large integers become floats, no 3.14t build |
| ujson            | no            | slower on real exports, upstream in maintenance-only mode                         |
| ijson            | only directly | about 2x slower even for one key, but tiny memory when streaming                  |
| simplejson       | no            | about stdlib speed with the GIL                                                   |
| python-rapidjson | no            | re-enables the GIL on 3.14t (not benchmarked)                                     |

msgspec is in hpikit's `optional` extra; without it, `hpikit.json` falls back to stdlib with a warning.
`HPIKIT_JSON_BACKEND=stdlib` selects stdlib explicitly, and `HPIKIT_JSON_BACKEND=msgspec` fails if msgspec is missing.
The other parsers aren't offered by `hpikit.json`.
msgspec and stdlib gave identical results on 753 real export files, see [compatibility](#compatibility-with-real-exports).

## Real exports

The latest Reddit, GitHub events and Hypothesis exports, decompressed into memory first.
Timings exclude reading and decompression and are the best of 5 runs.
Peak memory is tracemalloc's peak during one parse.
orjson's tracemalloc peak is 6-8x msgspec's here, whereas its peak RSS on the synthetic file below is about 1.4x.

With the GIL (3.14):

| Export (decompressed) | msgspec        | jiter          | orjson          | ujson          | stdlib          |
|-----------------------|----------------|----------------|-----------------|----------------|-----------------|
| Reddit, 11.5 MB       | 32.0 ms, 22 MB | 32.8 ms, 16 MB | 36.9 ms, 162 MB | 51.2 ms, 82 MB | 103.9 ms, 69 MB |
| GitHub events, 9.1 MB | 18.1 ms, 16 MB | 21.5 ms, 12 MB | 22.8 ms, 125 MB | 31.5 ms, 60 MB | 68.0 ms, 51 MB  |
| Hypothesis, 6.0 MB    | 15.4 ms, 13 MB | 18.2 ms, 10 MB | 16.6 ms, 85 MB  | 20.9 ms, 42 MB | 40.0 ms, 37 MB  |

Free-threaded (3.14t), where orjson isn't available:

| Export (decompressed) | msgspec        | jiter          | orjson | ujson          | stdlib         |
|-----------------------|----------------|----------------|--------|----------------|----------------|
| Reddit, 11.5 MB       | 30.5 ms, 42 MB | 29.4 ms, 16 MB | n/a    | 39.2 ms, 88 MB | 85.2 ms, 69 MB |
| GitHub events, 9.1 MB | 17.7 ms, 28 MB | 20.9 ms, 14 MB | n/a    | 26.8 ms, 64 MB | 55.1 ms, 53 MB |
| Hypothesis, 6.0 MB    | 14.7 ms, 21 MB | 12.9 ms, 10 MB | n/a    | 16.2 ms, 45 MB | 36.8 ms, 38 MB |

### Streaming one key

Extracting only the `saved` collection (1,474 items) from the same Reddit export, measured separately:

| Approach                      |     Time |  Peak memory |
|-------------------------------|---------:|-------------:|
| ijson, streaming `saved.item` |  77.0 ms |       0.3 MB |
| msgspec, whole file           |  36.1 ms |      22.3 MB |
| stdlib, whole file            | 108.0 ms | not measured |

ijson only builds objects for the requested key but still scans the whole document, so the other seven collections took 70-74 ms as well.

## Compatibility with real exports

Up to 20 evenly spaced files from each of the 102 directories of JSON exports on the author's machine, 753 files in all.
Each file was decompressed and parsed with both msgspec and stdlib.
Every result was identical and neither parser failed on any file.
This doesn't cover JSON inside zip archives or stored in SQLite databases.

## Synthetic large file

A generated 58.4 MB Reddit-shaped file (60,000 + 20,000 items with nested lists and unicode), parsing its 60,000-item `saved` list.
Timings include `read_bytes()` from the page cache and are the best of 3 runs.
"msgspec, typed" decodes into a `msgspec.Struct` with only 3 of the fields.
Peak RSS is the increase in a fresh process while keeping the parsed list.

| Parser         |   3.14 |  3.14t | Peak RSS (3.14) |
|----------------|-------:|-------:|----------------:|
| msgspec, typed | 101 ms |  76 ms |           91 MB |
| msgspec        | 275 ms | 254 ms |          261 MB |
| ujson          | 298 ms | 222 ms |          310 MB |
| orjson         | 301 ms |    n/a |          365 MB |
| jiter          | 349 ms | 320 ms |          253 MB |
| stdlib         | 532 ms | 478 ms |          454 MB |
| ijson          | 543 ms | 455 ms |          191 MB |
| simplejson     | 551 ms | 381 ms |    not measured |

### Parallel parsing

Parsing the synthetic file 8 times, serially in one thread versus over 4 workers:

| Setup                                  | Parser  | Serial | 4 workers | Speedup |
|----------------------------------------|---------|-------:|----------:|--------:|
| 3.14t, threads                         | jiter   | 3.07 s |    1.28 s |    2.4x |
| 3.14t, threads                         | ujson   | 2.31 s |    1.52 s |    1.5x |
| 3.14t, threads                         | msgspec | 2.61 s |    1.57 s |    1.7x |
| 3.14t, threads                         | stdlib  | 4.23 s |    1.65 s |    2.6x |
| 3.14t, threads                         | ijson   | 4.36 s |    1.96 s |    2.2x |
| 3.14, threads                          | msgspec | 2.44 s |    2.26 s |    1.1x |
| 3.14, threads                          | orjson  | 2.64 s |    2.58 s |    1.0x |
| 3.14, processes returning parsed items | msgspec | 2.39 s |    2.41 s |    1.0x |
| 3.14, processes returning parsed items | orjson  | 2.64 s |    2.60 s |    1.0x |
| 3.14, processes returning a count      | msgspec | 2.39 s |    0.61 s |    3.9x |
| 3.14, processes returning a count      | orjson  | 2.62 s |    0.68 s |    3.8x |

With the GIL, threads don't help any parser.
A process pool only helps if workers return much less than they parse, because pickling the parsed items back costs about as much as parsing.
On 3.14t, the parser that is fastest serially isn't the fastest over threads, but the spread is small.

## Why msgspec is faster than stdlib

| Reddit export, 11.5 MB                 |     Time |
|----------------------------------------|---------:|
| stdlib, `json.loads(bytes)`            | 105.4 ms |
| stdlib, of which decoding bytes to str |  17.3 ms |
| stdlib, `json.loads(str)`              |  86.2 ms |
| msgspec, bytes                         |  32.3 ms |
| msgspec, str                           |  31.9 ms |
| stdlib, garbage collector disabled     | 100.7 ms |
| msgspec, garbage collector disabled    |  25.8 ms |

stdlib's scanner works on `str`, so `json.loads(bytes)` first decodes the whole input; msgspec parses UTF-8 bytes directly.
That decoding explains only part of the gap; the rest is msgspec's more optimized decoder.
One visible part: msgspec reuses the same dict key objects across separate calls, whereas stdlib only reuses them within one call.
That means fewer allocations, consistent with its lower peak memory.
Both return plain, fully built `dict`, `list` and `str` objects, so there's no lazy-parsing catch.
Garbage collection costs both of them; pausing it during very large loads saves about 20% with msgspec.

## Free-threading

| Parser                | Wheel for 3.14t                  | GIL after import                  |
|-----------------------|----------------------------------|-----------------------------------|
| msgspec 0.22.0        | yes                              | stays disabled                    |
| jiter 0.17.0          | yes                              | stays disabled                    |
| ujson 6.0.0           | yes                              | stays disabled                    |
| ijson 3.6.0 (yajl2_c) | yes                              | stays disabled                    |
| simplejson 4.2.0      | yes                              | stays disabled                    |
| python-rapidjson 1.25 | yes                              | re-enabled, with a RuntimeWarning |
| orjson 3.13.0         | no, and the source build refuses | n/a                               |
| pysimdjson, yyjson    | no (source builds not tried)     | n/a                               |

orjson's build fails with "orjson v3.13.0 does not support free-threaded Python".
A fallback chain that tries importing parsers can therefore re-enable the GIL for the whole process, so `hpikit.json` imports only the selected backend.

On 3.14t, 16 threads ran 3,840 concurrent msgspec decodes of the Reddit, GitHub and Hypothesis exports,
  plus synthetic documents with thousands of distinct keys to exercise msgspec's shared key cache.
Every result matched stdlib, the GIL stayed disabled, and the threads ran in parallel: 102 s of CPU time in 18 s.

## Packaging

msgspec 0.22.0 has 81 wheels on PyPI:

| Python                     | Platforms                                                                                          |
|----------------------------|----------------------------------------------------------------------------------------------------|
| CPython 3.10-3.15          | macOS x86_64 and arm64; glibc and musl Linux on x86_64, aarch64 and riscv64; Windows x64 and arm64 |
| free-threaded 3.14t, 3.15t | the same                                                                                           |
| CPython 3.14               | Pyodide (wasm32)                                                                                   |
| free-threaded 3.13t        | none                                                                                               |
| Android, iOS               | none                                                                                               |

Its source package needs only setuptools and a C compiler: the extension is a single C file (`_core.c`, about 23,000 lines), with no Rust.
It built from source here without problems.
Termux can't use the manylinux wheels and doesn't package msgspec, so pip builds it from source there, after `pkg install clang`.
That hasn't been tried on a device.
For comparison, orjson 3.13.0 has 58 wheels, none of them free-threaded, Android or iOS, and building it needs a Rust toolchain.
Building orjson on Termux is what failed for HPI in 2021 ([karlicoss/HPI#176](https://github.com/karlicoss/HPI/pull/176)).

## Edge cases

| Input                              | stdlib    | orjson    | msgspec   | ujson     | jiter     | ijson (C, `use_float=True`) |
|------------------------------------|-----------|-----------|-----------|-----------|-----------|-----------------------------|
| `[NaN]`                            | nan       | error     | error     | nan       | nan       | error                       |
| `[1180591620717411303424]` (2**70) | exact     | float     | exact     | exact     | exact     | error: integer overflow     |
| `["\ud800"]` (lone surrogate)      | kept      | error     | error     | kept      | error     | becomes `'?'`               |
| UTF-8 BOM, bytes input             | accepted  | error     | error     | error     | error     | error                       |
| `[1e400]` (overflows a float)      | inf       | error     | error     | inf       | inf       | error                       |
| Nested 2,000 levels deep           | accepted  | error     | accepted  | error     | error     | accepted                    |
| Duplicate keys                     | last wins | last wins | last wins | last wins | last wins | last wins                   |
| Invalid UTF-8                      | error     | error     | error     | error     | error     | error                       |

stdlib accepts the BOM only for bytes input, which `load()` passes.
ijson's pure-Python backend keeps 2**70 exact and keeps the lone surrogate, so even ijson's choice of internal backend changes the result.
Without `use_float=True`, ijson returns floats as `Decimal`.

## Maintenance and history

- [msgspec](https://github.com/msgspec/msgspec) releases slowed in 2024-25: 0.18.6 in January 2024, 0.19.0 in December 2024, 0.20.0 in November 2025.
  Development picked up again under the `msgspec` GitHub organization with new maintainers: 0.21.0 in April 2026 and 0.22.0 on 2026-09-29.
  In mid-October 2026 it had recent commits and 240 open issues, and its original author had made most of the commits.
- ujson's [README](https://github.com/ultrajson/ultrajson) puts it in maintenance-only mode for security reasons and recommends orjson.
- HPI adopted orjson in 2021 for serialization, i.e. dumping dataclasses and datetimes in `hpi query` output
    ([karlicoss/HPI#138](https://github.com/karlicoss/HPI/issues/138), [#140](https://github.com/karlicoss/HPI/pull/140)).
  A simplejson fallback followed because orjson didn't build on termux at the time ([#176](https://github.com/karlicoss/HPI/pull/176)).
- HPI's parsing helper `my.core.json.json_loads` ([#425](https://github.com/karlicoss/HPI/pull/425)) uses orjson with a stdlib fallback.
  `hpikit.json` would replace it if shared with HPI; `my.core.serialize` would keep orjson for dumping.
