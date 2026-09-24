# Release-patched MPQ support

The exact LUS CMake dependency is StormLib v9.25 at
`28c9b4be3f23c6b3a5ff55cacac7dbe5b9cdc4fc`, from
https://github.com/ladislav-zezula/StormLib . The generator applies the exact
pinned LUS `stormlib-optimizations.patch` after normalizing checkout newlines.
Its normalized SHA-256 is
`b0ddaae15cae92a87f7606b4bdf160039e56f48f593ad94f2341e11ef155b31f`.
Original source receipts are recorded in `../dependencies.lock.json`.

The library's actual CMake lists select all 231 runtime translation units,
including compression and signature dependencies. The already pinned zlib
library is used through upstream `__SYS_ZLIB`; bundled bzip2, LZMA, PKWARE,
sparse, Huffman, ADPCM and cryptographic source remains available. No formats
were removed to make an empty OTR implementation compile.

Xenon adaptations are confined to platform boundaries:

- StormPort selects XDK headers and **big-endian** conversion, because MPQ
  integer records are serialized little-endian. This is distinct from raw
  N64 bytes or native structures. Original StormLib conversion functions own
  the swaps. LZMA and bzip2 select XDK headers without changing algorithms.
- Cryptographic helpers use upstream `LTC_NO_ASM` portable byte operations;
  the old Windows detection must not select x86 little-endian/unaligned fast
  paths on Xenon. Optimization is deferred until native correctness evidence.
- Plain file streams use the existing Windows-compatible XDK file operations.
  Win32 mapped views and WinInet are unavailable, so only those provider guards
  select StormLib's existing unsupported branches. These fail, never pretend
  to mount data. The current OtrArchive passes MPQ_OPEN_READ_ONLY, selecting the
  ordinary file provider (zero provider bits). The native library omits the
  desktop WinInet autolink directive. Host builds retain desktop providers.

```powershell
python -B tools/shipyard/prepare_stormlib.py --build
python -B tools/shipyard/prepare_stormlib.py --build --host
python -B tools/shipyard/tests/test_stormlib.py
```

All 231 PPC BE objects and the archive library compile. Host tests create a
real format-V2 MPQ (required by upstream for LZMA), reopen it read-only, decode
encrypted zlib/bzip2/LZMA/PKWARE/sparse members, seek and read partial data,
check the listfile and reject missing members. Exact commands/results are in
`scratch/stormlib-xdk`. Big-endian execution, target I/O and signature behavior
still need native validation. No Xenia or hardware claim is made.

## Compiler projection ownership

This is Modern's pinned StormLib v9.25 dependency projection. It applies the
exact LUS patch, selects StormLib's own 231 translation units, and makes
target-specific endian, header, file-provider and crypto changes. Smash's
`tools/prepare_stb_xdk.py` prepares the unrelated pinned `stb_image` decoder;
its active application lists the stb implementation as a selected unit and
does not have a counterpart to this StormLib compiler projection. A StormLib
header include root in Smash's port preparation is not a shared compilation
mechanism. StormLib revision, patch, selected features and archive behavior
therefore remain consumer dependency/version policy. No optional Shipyard
StormLib compiler package was introduced by this review.
