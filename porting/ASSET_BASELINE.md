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
