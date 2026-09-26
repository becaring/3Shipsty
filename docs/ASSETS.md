# Assets and packaging

3Shipsty requires a supported, legally acquired Ocarina of Time ROM. The
repository does not provide ROMs or extracted game assets. Supported ROM hashes
are listed in [supportedHashes.json](supportedHashes.json).

Use the matching Ship of Harkinian 9.2.3 PC release to extract assets. Xbox
startup consumes the resulting archives; it does not run the desktop extraction
tools. The runtime uses `soh.o2r`, `oot.o2r`, and optionally `oot-mq.o2r`.
Mods use the existing OTR/O2R resource system and a `mods` directory.

Package the application and its matching archives together. Preserve the
runtime's selected writable storage for configuration and saves. Speech also
requires the standard `espeak-ng-data` package described by the
[speech provider](../platform/shipyard/speech/README.md).

## Archive format

A ZIP/MPQ container has no single scalar byte order. Resource records carry
their own markers. PC-generated regular binary resource headers and payloads
are little endian; the version records below are explicitly big endian.
Xenon's native endianness must not replace these per-record rules.

The 9.2.3 `portVersion` record is `01 0009 0002 0003`. A game-version record
contains its own marker and game CRC. `OTRExporter/Main.cpp` selects big endian
for version records, while `OTRExporter/Exporter.cpp` selects little endian for
regular headers.

## Extraction reference identities

These hashes identify fixed extraction fixtures, not downloadable game data or
universal hashes for every supported ROM. The verifier checks archive member
lengths, CRCs, unsafe/duplicate paths, and version records.

| Artifact | SHA-256 |
| --- | --- |
| Official `SoH-Ackbar-Delta-Win64.zip` | `cc7bd5ada1332be50013976fc3db3289cacde1df57e7e6cf73d4a1df81313e30` |
| `soh.o2r` (1,279 entries) | `7b375d854385a6cdb6843db89c18da981948e5b56986f479297cca33d2914a2f` |
| Debug fixture `oot.o2r` (35,646 entries) | `2cb12f54bc058cb841981c3e47f30dcd62bb9b7c2f67b6fad2e93756b0f415e0` |
| Retail NTSC 1.0 fixture `oot.o2r` (38,390 entries) | `c2b5d5af24a52095a13e50479763ff4b9dcc1d8afe6a0788fbfc26a91b17c03c` |

The debug fixture has ROM SHA-1 `cee6bc3c2a634b41728f2af8da54d9bf8cc14099`
and game CRC `871e1c92`. The retail fixture has ROM SHA-1
`ad69c91157f6705e8ab06c79fe08aad47bb57ba7`, size 33,554,432 bytes, and header
CRC pair `EC7011B7/7616D72B`. A filename alone does not establish ROM identity.

`python -B tools/shipyard/verify_assets.py` verifies the configured debug fixture;
`--retail-ntsc10` selects the retail fixture. The command expects independently
provided input files in its documented fixture layout. Successful extraction
and integrity checks do not establish gameplay or hardware compatibility.
