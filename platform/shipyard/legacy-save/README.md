# Legacy raw-save import boundary

This module projects the complete 9.2.3 `SaveManager::ConvertFromUnversioned` method and the actual, unchanged `CopyV0Save` helper. It does not provide another save manager, JSON schema, gameplay path or storage service. Modern saves continue through the canonical SaveManager class and real `SaveGlobal`, `InitFile(false)`, `SaveSection(fileNum, SECTION_ID_BASE, false)` and `InitMeta` methods.

`prepare_legacy_save.py` verifies the pinned source hashes and historical producer Git objects, emits the frozen legacy structs with compiler assertions for every member offset/structure size, and generates a bounded decoder from the declarations. All generated files are under `scratch/legacy-save-xdk`. Both production translation units compile with the XDK; their COFF machine is checked as PPC `0x1F2`.

## Ownership and adaptations

- `reader.h` contains generic byte-range checking, signed/unsigned bit-pattern decoding and complete-file reading, plus this application's legacy header/slot validation. Generic byte-reader work is reusable Shipyard platform code. The file geometry, checksum selection policy, structs, song boundary and converter are 3Shipsty-specific compatibility work.
- `storage_path.h` obtains the import and backup paths from the selected native storage directory's parent. It supplies no alternate storage manager. The application must mount the real XContent namespace first.
- `LegacyDecode.cpp` contains all persistent scalar reads into a real aligned `SaveContext_v0`. No input buffer is reinterpreted as a C++ structure. Runtime tail fields are initialized but not imported.
- The historical song members are byte arrays containing producer-native `OcarinaNote` records. The decoder normalizes the u16 duration at each record's +2 offset. It preserves the other bytes and then calls the **unchanged** upstream CopyV0Save, including its existing memcpy operations. No conversion applies to modern JSON save values, resource archives or ROM bytes.
- Full-file reads determine the expected file length, read that many bytes and check stream status/count. Unreadable, short or failed reads throw before global state or storage writes change.
- The complete converter validates all occupied primary slots before saving anything. Invalid headers, nonzero invalid slot markers, inconsistent byte order, invalid checksums or unresolved byte order throw; the original is retained by the caller because the method never returns success in those cases.
- A candidate order needs valid producer checksums and link-age 0/1 across all occupied slots. If both orders satisfy those checks, a unique ordinary vanilla capacity interpretation resolves the tie. Capacity is not a blanket filter: modified capacities can import when the other evidence resolves order. No format order is chosen from the consumer architecture.
- The checksum/marker/ambiguity checks are an **explicit stricter input-validation deviation** from desktop 9.2.3, which only checked header/occupied markers and assumed native order. Unknown or damaged files remain available for repair or explicit producer-aware PC conversion. This module intentionally has no undocumented default or automatic word-swizzle handling.
- Each occupied slot keeps the actual upstream initialization, base-section write and metadata call. A local RAII copy restores the current global SaveContext on normal return or exception from those services. This replaces upstream's function-static snapshot, which could retain a snapshot from an earlier call. Global header settings keep their upstream behavior.
- `Storage::Commit()` runs after all modern writes and before successful return. The real existing storage implementation performs the XContent flush. No legacy rename occurs inside this fragment.

## Required integration in the owning SaveManager generator

This module deliberately does not modify shared generators or the canonical SaveManager header. Integrate both `xdk/build.json` records as **fragments**, not as complete application-TU coverage. Do not compile a second definition of `ConvertFromUnversioned` from the retained full SaveManager source.

In the existing projected `SaveManager::Init`:

1. Include `legacy-save/storage_path.h`.
2. Obtain `sOldSavePath` using `Shipyard::LegacySave::Path()` and `sOldBackupSavePath` using `Shipyard::LegacySave::BackupPath()`. Its existence check, converter read and rename must address the same selected storage namespace.
3. Keep the synchronous `ConvertFromUnversioned()` call before the rename. Do not catch conversion exceptions and fall through to the rename.
4. Rename only after the converter returns; then call `Shipyard::Storage::Commit()` so the backup rename itself is durable. An existing backup must remain recoverable if rename cannot proceed.
5. Keep the native mount before SaveManager initialization, and the existing worker barrier before shutdown.

The complete conversion method references the real canonical SaveManager and storage methods. Host/native compilation verifies those declarations; this isolated module does not link fake implementations to claim that application conversion has executed. The caller integration and actual XContent error/durability behavior still require application bring-up.

## Verification

Run from the owned root:

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_legacy_save.py --build
C:/Python313/python.exe -B tools/shipyard/test_legacy_save.py
```

The test independently extracts the historical producer's structs and actual `Sram_WriteSave` body from `73ff7ef3dae83ec85afb20ec6453c69967bb0b96`. It captures that writer's SRAM writes into a test buffer; this is only a fixture-producing I/O capture. The historical `OS_K1_TO_PHYSICAL(x)` macro was already `(0)`, as recorded by the locked historical convert.h. The fixture uses that exact offset contract.

The historical writer's `SLOT_SIZE` extends 0x28 bytes beyond SaveContext. The fixture allocates explicit trailing backing bytes, then executes the unchanged writer. Compiler assertions independently verify the producer's layout and the matching import structure. It produces real little-endian raw bytes using the historical checksum logic. The BE fixture is explicitly **synthesized** by reversing the producer's typed fields and note durations, running the same writer, and encoding the checksum/runtime file number in BE order. It is not a captured hardware save.

For 32 patterns and three slots in both orders, the decoded result passes through the actual CopyV0Save and is compared against the unchanged desktop helper's result on the historical LE output. All bytes of the initialized modern SaveContext are compared, including untouched state. This covers 192 complete destination comparisons, every copied array endpoint, all three equipment structures, signed coordinates and flags, and both recorded songs. The comparison digest is `18b075325d2724ab`.

Additional checks cover all 65,536 signed/unsigned 16-bit patterns in both orders, high-bit 32-bit patterns, every shorter input length (15,592 truncations), invalid header/slot marker, corrupt checksum, mixed slot orders, the donor's ambiguous 0x0101 capacity, supported modified capacity, unaligned input, invalid slot index, actual read/missing-file behavior, unchanged source bytes and empty slots. The entire production converter also receives a host compile using its real unresolved service references.

Receipts: `scratch/legacy-save-xdk/manifest.json`, `xdk/build.json`, `verification.json`, `host/output.txt`, and host/native compile logs. Generated source and owned helper hashes are recorded. No Xenia, physical-hardware or complete-converter runtime validation is claimed.
