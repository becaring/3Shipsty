# Native archive dependencies

This provider builds real libzip 1.11.4, zlib 1.3.1 and tinyxml2 from verified
owned source snapshots. The selected dependency revisions and receipt hashes
are in ../dependencies.lock.json. These are explicit Xbox dependency selections;
Shipwright's desktop vcpkg requests do not independently pin these versions.
tinyxml2 compiles unchanged. The zlib compression core compiles unchanged.

The libzip projection carries generic Xbox file/API adaptations from Smash360,
recorded in provenance.json. It does not import a resource manager or custom
archive format. Config generation selects XDK-supported CRT operations and
declares big-endian only on Xbox. ZIP serialization remains libzip-owned.
Late C declarations move without changing their assignments. Named-file
operations use the owned filesystem absolute-path boundary. Native wide-file
and arbitrary-handle APIs fail with OP_NOTSUPP rather than guessed semantics;
the real current O2rArchive consumes narrow named paths. ZIP member names retain
UTF-8. XNetRandom preserves explicit caller ownership of network startup.

The source projection preserves legal notices. Native path handling is limited
to ASCII Xbox device filenames. This limitation does not restrict serialized
resource contents or member names. Archive compression currently enables store
and deflate (the verified modern archives' formats); optional bzip2/LZMA/Zstd
and encryption providers remain explicit integration work if required by mods.
MPQ is a separate modern archive provider and is not removed by this work.

Reproduce from the owned root:

```powershell
python -B tools/shipyard/snapshot_dependency.py D:/Projects/Smash360/upstream/dependencies/zlib zlib 51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf
python -B tools/shipyard/snapshot_dependency.py D:/Projects/Smash360/upstream/dependencies/libzip libzip 6f8a0cdd24a0dc6cce9dac4a7679da784ab124ea
python -B tools/shipyard/snapshot_dependency.py D:/Projects/Smash360/upstream/dependencies/tinyxml2 tinyxml2 9148bdf719e997d1f474be6bcc7943881046dba1
python -B tools/shipyard/prepare_archives.py --build
python -B tools/shipyard/prepare_archives.py --build --host
python -B tools/shipyard/tests/test_archive_generation.py
python -B tools/shipyard/tests/test_archives.py
```

Snapshotting uses read-only git archive of exact clean reference commits; it
never executes dependency code or writes metadata in a reference tree. The
same recipe accepts a clean clone at the exact commit from each recorded
official source URL. Every archived byte is verified against a committed
receipt hash before projection/build. Receipt/source drift fails closed.

Evidence under scratch/libzip-xdk: 131 host objects, 131 PowerPC BE objects,
three libraries per target, reproducibility/source-drift tests, and host
execution of the actual projected libzip/filesystem/async boundary against
both real 9.2.3 archives. All 36,925 entries and their CRCs pass. Tests also
cover missing entries/archives and ZIP create, UTF-8 member name, overwrite
and reopen. This is not Xbox execution or resource-factory validation.
