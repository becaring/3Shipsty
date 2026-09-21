# Current audio codec dependencies

The real current `soh/soh/mixer.c` calls `op_open_memory`, `op_pcm_seek` and
`op_read`. These remain the official codec implementations. Exact source
revisions and snapshot receipts are in `../dependencies.lock.json`:

| Dependency | Release | Commit |
|---|---|---|
| xiph/opus | 1.6.1 | 22244de5a79bd1d6d623c32e72bf1954b56235be |
| xiph/opusfile | 0.12 | a55c164e9891a9326188b7d4d216ec9a88373739 |
| xiph/ogg | 1.3.6 | be05b13e98b048f0b5a0f5fa8ce514d56db5f822 |

The release uses system dependencies here, not Git submodules. These are
explicit port dependency selections; the Shipwright gitlinks remain unchanged.
Official release information: https://opus-codec.org/downloads/ . All sources
and licenses are retained in owned, verified snapshots under `scratch/deps`.

`prepare_codecs.py` derives Opus TUs from its actual upstream `.mk` manifests.
Floating-point CELT/SILK, encode/decode and float APIs remain enabled. Optional
DRED/OSCE/deep-learning and architecture intrinsics are not selected. Stack
scratch uses upstream `USE_ALLOCA`, avoiding shared global scratch storage.
Hardening checks remain enabled, with precise floating-point compilation.

Only native boundaries are projected: desktop abort-message configuration and
x86 bit-scan intrinsics exclude `_XBOX` (the upstream portable implementation
is used), and opusfile's stream layer uses XDK `xtl.h`, `_fstat` regular-file
classification and ANSI CRT paths. Non-regular input retains nonseekable
callbacks. Unicode external filenames beyond Xbox's native path encoding
remain an integration limitation; memory archives are unaffected.

Serialized Ogg/Opus fields retain upstream explicit little-endian handling.
Native decoded PCM remains host order. Xenon runtime and mixer endian
integration are not yet validated. Opus's portable float-to-integer fallback
uses `floor(.5+x)` while desktop SSE can round ties to even; target codec
quality/rounding must be measured, not assumed bit-identical to SSE output.

```powershell
python -B tools/shipyard/prepare_codecs.py --build
python -B tools/shipyard/prepare_codecs.py --build --host
python -B tools/shipyard/tests/test_codecs.py
```

All 143 PPC BE objects and three libraries build. Host tests encode a stereo
signal into a genuine Ogg Opus stream and verify memory/file decode, pre-skip,
PCM count, seek, EOF and malformed-input rejection. The exact seek comparison
disables dither via the public API because seeking legitimately changes
noise-shaping state; the full memory/file comparison retains default dither.
These are codec contract checks, not application, Xenia or hardware validation.
Commands and results are recorded under `scratch/codec-xdk`.
