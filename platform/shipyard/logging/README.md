# Shipyard logging compiler provider

The spdlog core projector is now `LibUltraShip+Fast3D360/python/xbox360_platform/logging_core.py`.
This directory supplies the pinned input, native support and a narrow adapter
that selects filter-before-conversion and the Modern formatter boundary.

This projects actual spdlog 1.16 logger, registry, backtracer, pattern formatter,
rotating sink, stdout sink and asynchronous queue algorithms. It uses the owned
Shipyard native mutex/CV/thread implementation. No logging macro is suppressed,
and formatting occurs before enqueue; queued messages own their payload and
logger lifetime. There is no replacement printf logger.

LUS 9.2.3 has no spdlog gitlink. Its platform package lookups are unconstrained;
the macOS/mobile fallback requests 1.14.1. `dependency-lock.json` explicitly pins
the audited 1.16 provider. This choice does not modify the pinned LUS tree.
The source locks reject changed dependency bytes before generation writes.
All support and language transformations came from the generic, audited
Smash360 Xbox work listed in `donor-provenance.json`; no Smash application code
is included. The small C++ AST lowerer extracts only range/brace/enum/source-map
operations and has no dependency on the donor's mega-build script.

## Reproduction and integration

Acquire the two official dependency commits in `dependency-lock.json` into
`scratch/deps/spdlog` and `scratch/deps/fmt-xdk`. Existing owned receipts record
their complete clean Git-archive snapshots. Place tree-sitter 0.25.2 and
tree-sitter-cpp 0.23.4 in `scratch/python-tools` for host generation, using
`tools/shipyard/requirements.txt` for the exact versions.
These are host tools only.

Run:

```
python -B tools/shipyard/prepare_logging.py
python -B tools/shipyard/tests/test_logging_generation.py
python -B tools/shipyard/tests/test_logging.py
python -B platform/shipyard/logging/audit_consumers.py
```

Include precedence is `scratch/logging-xdk/core-include`,
`scratch/logging-xdk/include`, `scratch/deps/fmt-xdk`, then the project root.
Production links `platform/shipyard/async/native.cpp`,
`platform/shipyard/logging/chrono/chrono.cpp` and `environment.cpp`.
The real Context logging routine still needs its narrow desktop console guard
adaptation; this provider does not replace Context. Initialize the default
registry and the optional immutable launch environment on the startup thread
before starting workers. `ShipyardEnv_LoadFromFile` returns explicit absent,
invalid and I/O outcomes and never rewrites the launch configuration.

The actual current Context contract remains queue 8192, one worker, blocking
overflow, source location, configured severity, 10 MiB rotating log and ten
backups, info flush in release, and shutdown after other Context services.
Xbox stdout uses the actual CRT sink without terminal colors. `%P` explicitly
throws because the Xbox process-ID API is unavailable. Counter/level atomics
use locks, preserving widths and atomic operations, with no lock-free claim.
The donor-proven XDK optimization exclusion is retained only around
`async_logger::backend_sink_it_`; it preserves sink, flush and catch operations.
Native execution must check the current linked PPC control flow again.

## Formatting boundary and unresolved limits

The compiler formatter is official fmt 4.1.0, an **explicit limited dependency
deviation** from spdlog's bundled fmt 12, not a claim that the two are equivalent.
It retains the library's typed arguments, parser and error behavior. Fixed
overloads support 39 diagnostic arguments; custom formatters fail compilation
when not supplied. Unknown types are not converted to arbitrary strings.

The actual current-source AST inventory has 558 fmt/spdlog calls, including
93 direct fmt calls; it records source hashes, arguments and ownership in
`scratch/logging-xdk/consumer-inventory.json`. That is an inventory, not a full
type/reachability proof. Exact host differential tests cover typed source forms
for modern time displays, gameplay stats, randomizer sphere keys, preset paths,
CVar keys, menu/flag IDs, debugger integer formats, UTF-8 strings, and explicit
fixed-precision host extraction progress. Those tests also reject malformed
format strings without requiring identical exception wording.

**Default binary32/64 floating precision now matches the current formatter.**
`generate_float.py` extracts the actual fmt12 Dragonbox implementation from the
pinned spdlog dependency, rejecting changed inputs with `float-source-lock.json`.
The full cache and portable integer multiplication are used on both the host
differential and Xenon compilation paths. The double cache is stored as a POD
constant pair table: losing `constexpr` must not introduce dynamic initialization
or an unsafe first-use guard into concurrent logging. The numeric-bit boundary
uses same-size `memcpy` into native unsigned integers; it does not byteswap native
IEEE values. This is appropriate for either host endian order.

The fmt4 typed argument union now distinguishes `float` from `double`; promoting
binary32 to binary64 before choosing shortest digits is observably incorrect.
The new enum still fits the four-bit packed argument representation. **Rebuild
all formatting consumers together** because those internal type codes changed.
The bounded writer maps Dragonbox's decimal significand/exponent to fmt12's
fixed/scientific threshold, alternate form, sign, padding and nonfinite behavior.
Windows/Xenon `long double` has double precision and uses the binary64 path.

Run `python -B tools/shipyard/tests/test_logging_float.py`. The complete output
differential covers 361,013 cases: deterministic raw float/double bit patterns,
extrema, subnormals, signed zero, infinities/NaNs, threshold values, default
width/alignment/fill/sign/alternate forms, named arguments, and the packed
argument limit. It additionally compares reached explicit fixed-precision
forms and representative `e`/`g` precision forms. The whole corpus compiles as
a real XDK PPC object. Receipts are in `scratch/logging-xdk/float-tests`;
the former one-value gap probe is now a required equality regression.

Explicit precision or a presentation letter still uses fmt4's CRT branch.
The host differential does **not** prove XDK CRT rounding/exponent behavior;
the source inventory's direct `{:.0f}%` is in PC extraction. Newly reached
explicit floating forms, locale formatting, or extended floating types need
their own boundary audit. The default shortest path no longer depends on CRT
decimal conversion. Native subnormal execution remains untested in Xenia.

The donor omits periodic flush/timed dequeue convenience APIs, wide logging,
variadic logger/sink factories and terminal color controls. None is invented or
silently ignored. Deleted copy operations are undeclared definitions, so an
unsupported copy may fail at link rather than compile. The retained chronological
clock arithmetic is bounded and may throw for unrepresentable QPC frequency.

## Evidence

Unprojected spdlog fails the actual XDK compiler at missing `<atomic>`; see
`scratch/logging-xdk/raw-compiler.log`. The projected current core differential
checks default diagnostics, levels/source locations, formatting errors, patterns,
backtrace, 13/16/39 arguments, file rotation/callbacks, async owned 1200-byte
messages, registration, logger lifetime and shutdown draining. The logger,
format caller corpus, native clock and launch environment compile as four real
PPC COFF objects. Three generation checks cover hashes, repeatability and
changed-source rejection.

These results do not establish final application linkage, Xbox log-file success,
native clock accuracy, scheduler behavior, or Xenia/hardware execution.

## Filter-before-conversion correction

Integration exposed eager fmt4 argument packing before the current logger's
level/backtrace gate. A defined conversion-count regression confirmed that
filtered messages converted their argument while the original spdlog did not.
All zero-to-39-argument logger overloads are now generated with the existing
`should_log || should_backtrace` condition before packing. Global helpers forward
unpacked references to the actual logger. Packing exceptions remain inside the
logger error-handler boundary. No sink, queue or formatting algorithm changed.

Coverage includes direct and global calls, source-location overloads, packed
and extended argument lists, and backtrace retention when ordinary output is
filtered. The default-float regression now requires the modern shortest output.
