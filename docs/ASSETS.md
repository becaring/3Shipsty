# Assets and packaging

3Shipsty needs a supported, legally acquired Ocarina of Time ROM. The
repository contains no ROMs or extracted game assets. Supported ROM hashes
are listed in [supportedHashes.json](supportedHashes.json).

Place the ROM beside the application. When `oot.o2r` or `oot-mq.o2r` is
missing, startup builds it from each supported ROM there: a vanilla ROM gives
`oot.o2r` and a Master Quest ROM gives `oot-mq.o2r`. A Master Quest ROM holds
only the Master Quest dungeons, so playing both dungeon sets takes both ROMs.
Extraction reads the extraction XMLs from `assets.zip`, or from the `assets`
folder when no zip is present. `python -B tools/shipyard/pack_assets.py`
packs the 9.2.3 release `assets` folder into that uncompressed zip, which
copies to the console as one file. The runtime uses `soh.o2r`, `oot.o2r`, and
optionally `oot-mq.o2r`. Mods use the OTR/O2R resource system and a `mods`
directory.

Package the application with its matching archives. Saves go to the selected
`shipyard:` container; configuration and logs stay under `game:`. Speech also
needs the standard `espeak-ng-data` package described in the
[architecture guide](ARCHITECTURE.md#speech-and-shutdown).

## Archive format

A ZIP/MPQ container has no single scalar byte order. Resource records carry
their own markers. Desktop- and console-built regular binary resource headers and payloads
are little endian; the version records below are big endian. Xenon's native
endianness must not replace these per-record rules.

The 9.2.3 `portVersion` record is `01 0009 0002 0003`. A game-version record
contains its own marker and game CRC. `OTRExporter/Main.cpp` selects big endian
for version records, while `OTRExporter/Exporter.cpp` selects little endian for
regular headers.

## Checking archives

`python -B tools/shipyard/verify_assets.py` checks the configured debug fixture;
`--retail-ntsc10` selects the retail fixture. It checks member lengths, CRCs,
unsafe or duplicate paths, and version records. Supply the inputs at the paths
the script declares. A filename alone does not identify a ROM or archive.
