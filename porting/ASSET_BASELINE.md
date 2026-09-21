# PC extraction baseline

The official stable 9.2.3 Windows release was acquired from
https://github.com/HarbourMasters/Shipwright/releases/download/9.2.3/SoH-Ackbar-Delta-Win64.zip.
Package SHA256: cc7bd5ada1332be50013976fc3db3289cacde1df57e7e6cf73d4a1df81313e30.
It was expanded only to scratch/assets/official-9.2.3. The supplied PAL debug
ROM was copied read-only from the reference into scratch/assets/input.z64;
SHA1 cee6bc3c2a634b41728f2af8da54d9bf8cc14099, CRC 871e1c92.

The exact official soh.exe was launched hidden with that owned ROM pathname
as its argument and its owned directory as working directory. TEMP/TMP pointed
into scratch/assets/host-temp. This runs the release's own ZAPDTR/OTRExporter
extraction, not Xbox application code. The helper completed extraction and
was stopped at its post-extraction launch prompt after archive verification.
No ROM is embedded in target code, and no reference archive was overwritten.

`python -B tools/shipyard/verify_assets.py` verifies the official package, input
ROM, every archive CRC, duplicate/unsafe member paths, and version records.
Detailed results and extractor hash: scratch/assets/archive-verification.json.

| Archive | Entries | SHA256 |
| --- | ---: | --- |
| soh.o2r | 1,279 | 7b375d854385a6cdb6843db89c18da981948e5b56986f479297cca33d2914a2f |
| oot.o2r | 35,646 | 2cb12f54bc058cb841981c3e47f30dcd62bb9b7c2f67b6fad2e93756b0f415e0 |

Both portVersion records are bytes 01 0009 0002 0003: explicit big-endian
9.2.3. The game-version record is 01 871e1c92, also big-endian. Regular binary
resources emitted on this PC carry byte-order marker 00 and little-endian
scalar headers/payloads. OTRExporter/Main.cpp explicitly writes the version
records as Big; OTRExporter/Exporter.cpp explicitly selects Little for regular
headers. The runtime must honor each record's marker. Native Xenon byte order
does not justify treating the complete archive as uniformly big-endian.

The owned native-boundary libzip also reads all members with matching lengths
and CRCs in its host test. Current Xbox resource factories and real application
mounting remain to be validated; extraction is not gameplay evidence.

## Supplied retail candidate

The user supplied owned `oot-ntsc-1.0.z64` on 2026-09-20. Read-only inspection:
55,046,144 bytes, SHA1 70825a96565d407bf9df32a418d6e685a754bdb8,
header CRC pair 93522e7b/e506d427, big-endian z64 magic 80371240.
This file does not satisfy the pinned extractor: supported sizes are 32, 54,
or 64 MiB, and retail NTSC 1.0 is identified by header CRC EC7011B7.
Its file size is none of those accepted sizes. No validation bypass, mutation,
or extraction was performed. A supported unmodified retail dump remains needed
for the requested retail-1.0 archive validation; the verified debug archive is
still available for port bring-up. Filename is not treated as version evidence.

The subsequently supplied `baserom.z64` is 33,554,432 bytes, SHA1
ad69c91157f6705e8ab06c79fe08aad47bb57ba7, header EC7011B7/7616D72B.
The exact official extractor accepted it and produced retail NTSC 1.0 assets in
scratch/assets/retail-ntsc10. The decompressed sibling is not used. A GUI launch
without an explicit working directory encountered the upstream relative-path
permission test; the retry with the owned extraction directory succeeded. No
permission check was patched or skipped. Computer control was stopped by the
user; final archive verification used filesystem tools.

`python -B tools/shipyard/verify_assets.py --retail-ntsc10` verifies the official
package, input identity, archive versions and every member CRC. Retail oot.o2r:
38,390 entries, SHA256 c2b5d5af24a52095a13e50479763ff4b9dcc1d8afe6a0788fbfc26a91b17c03c.
Its game-version record is big-endian EC7011B7; portVersion is 9.2.3. The
1,279-entry soh.o2r remains identical to the official baseline. The resulting
retail archive is ready for real Xbox runtime validation, which has not run.
