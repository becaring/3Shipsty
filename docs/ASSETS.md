# Assets and packaging

3Shipsty requires a supported, legally acquired Ocarina of Time ROM. The
repository does not provide ROMs or extracted game assets. Supported ROM hashes
are listed in [supportedHashes.json](supportedHashes.json).

Use the matching Ship of Harkinian 9.2.3 PC release to extract assets. Xbox
startup consumes the resulting archives; it does not run the desktop extraction
tools. The runtime uses `soh.o2r`, `oot.o2r`, and optionally `oot-mq.o2r`.
Mods use the OTR/O2R resource system and a `mods` directory.

Package the application and its matching archives together. Preserve the
runtime's selected writable storage for configuration and saves. Speech also
requires the standard `espeak-ng-data` package described by the
[architecture guide](ARCHITECTURE.md#speech-and-shutdown).

## Archive format

A ZIP/MPQ container has no single scalar byte order. Resource records carry
their own markers. PC-generated regular binary resource headers and payloads
are little endian; the version records below are explicitly big endian.
Xenon's native endianness must not replace these per-record rules.

The 9.2.3 `portVersion` record is `01 0009 0002 0003`. A game-version record
contains its own marker and game CRC. `OTRExporter/Main.cpp` selects big endian
for version records, while `OTRExporter/Exporter.cpp` selects little endian for
regular headers.

## Checking archives

`python -B tools/shipyard/verify_assets.py` checks the configured debug fixture;
`--retail-ntsc10` selects the retail fixture. It checks member lengths, CRCs,
unsafe or duplicate paths, and version records. Supply the inputs at the paths
declared by the script. A filename alone does not identify a ROM or archive.
