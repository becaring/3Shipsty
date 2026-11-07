# Assets and packaging

3Shipsty needs a supported, legally acquired Ocarina of Time ROM. The
repository contains no ROMs or extracted game assets. Supported ROM hashes
are listed in [supportedHashes.json](supportedHashes.json).

Place the ROM beside the application. When `oot.o2r` or `oot-mq.o2r` is
missing, startup builds it from each supported ROM there: a vanilla ROM gives
`oot.o2r` and a Master Quest ROM gives `oot-mq.o2r`. A Master Quest ROM holds
only the Master Quest dungeons, so playing both dungeon sets takes both ROMs.
Extraction reads the extraction XMLs from `assets.zip`, or from the `assets`
folder when no zip is present.
`python -B tools/shipyard/pack_assets.py <release>/assets <output>/assets.zip`
packs the 9.2.3 release `assets` folder into that uncompressed zip, which
copies to the console as one file; `tools/package.py` runs it for a release. The runtime uses `soh.o2r`, `oot.o2r`, and
optionally `oot-mq.o2r`. Mods use the OTR/O2R resource system and a `mods`
directory.

`python -B tools/package.py --destination <new folder>` assembles a release
from the linked XEX, the 9.2.3 release `soh.o2r` and `assets`, the speech data,
the shader pack and the license files listed in `release-licenses.json`. It
refuses uncommitted changes unless `--allow-dirty` is given, because `SOURCE.txt`
names the commits that are the release's GPL source. Saves go to the selected
`shipyard:` container; configuration and logs stay under `game:`. Speech uses
the `espeak-ng-data` described in the
[architecture guide](ARCHITECTURE.md#speech-and-shutdown).

## Archive format

A ZIP/MPQ container has no single scalar byte order. Resource records carry
their own markers. Regular binary resource headers and payloads, whether desktop- or console-built,
are little endian; the version records below are big endian. Xenon's native
endianness must not replace these per-record rules.

The 9.2.3 `portVersion` record is `01 0009 0002 0003`. A game-version record
contains its own marker and game CRC. `OTRExporter/OTRExporter/Main.cpp` selects
big endian for version records, while `OTRExporter/OTRExporter/Exporter.cpp`
selects little endian for regular headers.

## Checking archives

`python -B tools/shipyard/verify_assets.py` checks the configured debug fixture;
`--retail-ntsc10` selects the retail fixture. It checks member lengths, CRCs,
unsafe or duplicate paths, and version records. Supply the inputs at the paths
the script declares. A filename alone does not identify a ROM or archive.
