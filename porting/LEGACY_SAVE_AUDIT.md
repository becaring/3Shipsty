# Legacy unversioned save boundary audit

Audited 2026-09-20. Scope: historical raw `oot_save.sav` conversion only. No reference tree was modified. No implementation change or runtime validation is claimed by this document.

## Conclusion

The format is a dump of the **producer's native runtime structure**, not a ROM/resource encoding and not intrinsically little endian. The historical desktop producer writes native bytes directly; Xbox must decode each imported scalar in the producer's byte order. Keep the real 9.2.3 `InitFile(false) -> CopyV0Save -> SaveSection(BASE, false) -> InitMeta` behavior. Supply a narrow, bounded byte-reader at that conversion boundary. Do not reinterpret a byte-vector as a live C++ `SaveContext_v0` object, swap the whole blob, or copy an old application's save system.

Both desktop little-endian and canonical big-endian SRAM-layout input are established reference expectations, but **the file has no endian tag**. Format detection therefore needs explicit evidence and a safe ambiguous-input outcome. The primary donor already implements both orders, yet its heart-capacity heuristic is not a general format proof.

## Producer provenance: exact local Git objects

The owned repository contains full history. No network lookup is required to inspect these immutable source objects:

- `b4eebbbcd6951a6194d927effe3b519e42319dec`, 2022-06-20, **Versioned saves (#423)** introduced `ConvertFromUnversioned`.
- Its parent **`73ff7ef3dae83ec85afb20ec6453c69967bb0b96`** is the concrete raw-save producer examined here.
- At that parent, `soh/src/code/z_sram.c`: `SLOT_SIZE = sizeof(SaveContext) + 0x28`; slots start at `SRAM_HEADER_SIZE + 0x10 + index * SLOT_SIZE`. `Sram_WriteSave` calculates the native `u16` checksum, then passes `&gSaveContext` directly to `SsSram_ReadWrite` for primary and backup slots. Save creation uses the same path.
- At that parent, `soh/src/code/z_ss_sram.c:59`: `SsSram_ReadWrite` creates a zero-filled `SRAM_SIZE` file, seeks to the passed offset and calls **`fwrite(dramAddr, size, 1, saveFile)`**. There is no serialization or byte conversion.
- At that parent, `soh/include/z64save.h`: `SaveContext` has the same persistent field types, ordering, array counts and offsets retained in current `SaveContext_v0`. Later changes are the `_v0` type names and names of unused runtime timer/alpha members; `timerX/Y[2]` became `[TIMER_ID_MAX]`, currently 2.
- At that parent, `soh/src/code/z_message_PAL.c:2590,2653` memcpy the recorded native song buffers into the two byte arrays. `code_800EC960.c` defines `gScarecrowCustomSongPtr = sPierresSong` and `gScarecrowSpawnSongPtr = (u8*)&sOcarinaSongs[OCARINA_SONG_SCARECROW]`. Both are `OcarinaNote` data. The historical `z64audio.h` establishes the 8-byte note layout below.

These facts prove little-endian desktop files require conversion on Xenon. They do not prove that every arbitrary historical fork or emulator SRAM byte permutation is accepted.

The original N64-style producer is also present read-only at `D:/3Shipsty/Shipwright/third_party/oot/src/code/z_sram.c` and `z_ss_sram.c`: the same slot and native-structure write model uses SRAM DMA. This explains canonical big-endian SRAM bytes. This is provenance only; no recomp architecture is relevant.

## Primary Xbox donor evidence and limitations

`D:/Projects/SoH360/upstream/soh/soh/SaveManager.cpp:1712` has a source-order reader (`LegacySaveValue`) with a per-import endian choice, explicit `sizeof(SaveContext_v0) == 0x1428`, a minimum-length guard and special decoding of each song duration. `ConvertFromUnversioned` at line 1855 accepts LE or BE according to health-capacity bytes.

The donor's `scratch/native_save/tests.cpp:159` constructs both orders, checks health/rupees/song duration/global flags, preserves the original backup, and checks truncated-source retention. This is evidence of intended reference support and test source, **not evidence that those synthetic fixtures are captured historical saves or that this audit executed the tests**.

The donor chooses LE for capacity in `0x30..0x140`, otherwise BE for that range. Its comment says the interpretations cannot both be valid. That is true for ordinary vanilla capacities in multiples of `0x10`, but its implemented range omits that divisibility condition: bytes `01 01` pass both interpretations as `0x101`. Modified/cheated capacities also cannot be ruled out by this heuristic alone. Do not import that claim unchanged.

## File geometry and checks

- Header occupies `0x00..0x0F`; sound byte 0, Z-target byte 1, language byte 2. Bytes `3..11` are `98 09 10 21 5A 45 4C 44 41`. These are byte fields, never swapped.
- `0x10..0x1F` is the gap before slot 0.
- Raw context size `0x1428`; slot stride **`0x1450`**. Primary offsets **`0x0020`, `0x1470`, `0x28C0`**. Historical backup offsets **`0x3D10`, `0x5160`, `0x65B0`**. The historical producer creates `0x8000` bytes.
- Current upstream conversion inspects only the three primaries, identified by six literal bytes `ZELDAZ` at relative `0x001C`; do not silently replace its behavior with backup recovery.
- Minimum full-context length for the three primary slots is **`0x3CE8`** (last primary + `0x1428`). Full historical SRAM size is `0x8000`; current upstream did not require it, so do not reject otherwise complete smaller files merely because of exact length.
- Historical checksum is at relative `0x1352`. Producer computes the modulo-65536 sum of producer-endian `u16` words over `sizeof(Save) = 0x1354` bytes while that checksum word is zero, then stores it in producer byte order. This is a corroborating check, not an endian signature: some data/checksum combinations validate in both orders.
- Current upstream validates the magic and occupied-slot marker but does **not** validate this checksum. Treat adding mandatory checksum rejection as an explicit behavior change; do not accidentally discard formerly accepted damaged but readable saves.

## Exact decoding policy

A source-locked generated decoder can populate a real, aligned local `SaveContext_v0`, then call the actual current `CopyV0Save`. Decode only fields that conversion consumes; zero the unused local object storage without importing the runtime tail. Alternatively generate the same assignments directly against a bounded legacy byte view; keep the real assignment inventory as the generator's source of truth.

For each scalar, assemble an unsigned 16/32-bit integer from individual input bytes in the detected source order. For signed fields preserve the bit pattern into the corresponding native signed type (memcpy into the signed object avoids relying on an out-of-range unsigned-to-signed conversion). Byte fields and arrays preserve bytes. The imported Farore's Wind coordinates are **s32 integers, not floats**. There are no imported f32 fields; floats occur only in the ignored runtime tail. Do not introduce float conversion there.

Three ItemEquips values (bases `0x40`, `0x4A`, `0x68`) contain byte items/slots and one u16 equipment member at base+8; preserve the padding. Inventory begins `0x74`, scene flags `0xD4`, Farore's Wind `0xE64`. Exact member offsets and widths follow in the generated tables.

**Song exception:** although the two source members are u8 arrays, they contain producer-native OcarinaNote records. Long-song base `0x0F41`, 108 records; spawn-song base `0x12C6`, 16 records. Each record is `{u8 noteIdx, u8 unk_01, u16 unk_02, u8 volume, u8 vibrato, s8 tone, u8 semitone}`, stride 8. Preserve the six byte-valued positions and decode **u16 at base + 8*i + 2**. Long-song duration bytes are often unaligned. A blanket byte-array memcpy produces wrong durations across host orders, while a blanket u16 swap corrupts adjacent note/volume bytes.

The simplest implementation retains current CopyV0Save's song memcpy, followed by overriding each destination note's `unk_02` from the bounded source-byte reader. This resembles the primary donor's narrow fix but must use **current** `scarecrowLongSong` names and actual destination array counts.

## Endian selection without fabricated certainty

1. Read all necessary bytes first; validate bounds and header before touching global state or producing files. Check each occupied primary marker as bytes.
2. Evaluate both source-order candidates using actual historical constraints (ordinary health capacity multiple of `0x10` in `0x30..0x140`, `linkAge` 0/1, ordinary flag ranges) and independently record producer checksum results. These are evidence; do not claim any single heuristic identifies arbitrary modified saves.
3. Known producer metadata, if supplied alongside an import, can explicitly select the order. There is no such metadata embedded in this raw format. Defaulting every input to BE because the consumer is Xenon is incorrect.
4. Accept a uniquely supported order, including the donor-supported canonical BE case. If both candidates remain genuinely possible or both fail, retain the original unchanged and report **ambiguous/unsupported legacy representation**, with a route to explicitly select producer order or perform PC-side conversion. This is a narrow input-validation outcome, not disabling legacy conversion. Do not invent a byteswap for unknown emulator word-swizzled formats.
5. Keep the order as local import context, not mutable global state shared with the save worker. Do not mix different source orders silently across occupied slots of one producer file.

A policy that insists on strict vanilla invariants would reject some saves current desktop code attempts to read. If such a stricter policy is chosen, document it explicitly and provide the explicit producer-order path for modified saves.

## Storage transaction boundary

Current `SaveManager::Init` computes `sOldSavePath` relative to the application, but `ConvertFromUnversioned` opens a relative literal `oot_save.sav`. Both must reach the same selected Xbox storage namespace. Its unconditional `rename` after the conversion call must become conditional on successful read, decode and durable writes; otherwise malformed input or a failed write gets marked migrated. The donor already preserves source on failure. The original file must remain recoverable until the modern global/base saves have actually committed.

Keep the modern section/meta behavior. The 4.0.5 donor calls SaveFile; the 9.2.3 converter specifically calls SaveSection(BASE, false) then InitMeta. Carrying the old application flow forward would change modern behavior.

## Validation fixtures to generate from the producer

Implement these in owned scratch/generated test files; this audit only supplies the recipe:

1. Extract the exact parent producer structs and `Sram_WriteSave` checksum/write logic into a bounded test fixture producer, retaining a raw-write capture in place of file I/O. Compile on the development PC, assert every field offset below, `sizeof(SaveContext)==0x1428`, `sizeof(Inventory)==0x60`, Save size `0x1354` and note stride 8. **Do not model the producer merely by serializing the proposed decoder's own metadata**, which would share its mistakes.
2. Fill every imported member with distinct values, including signed negative Farore/horse coordinates, high-bit scene flags, all equips, final elements of every array, byte-song fields and durations `0x0123`/`0xFEDC`. Run the actual raw writer; assert captured slot offsets, original LE byte patterns and checksum independently.
3. Construct the canonical BE counterpart by field-aware encoding from the independently verified producer values (or capture the producer under a BE execution environment). A whole-buffer swap is not a valid fixture generator. Include the recorded note duration boundary and untouched padding. Label synthesized BE fixtures as synthesized; no hardware claim.
4. Decode each through the real projected converter and compare all actual copied fields and modern JSON/base output to the current desktop conversion of the LE original, except the intentional cross-endian song-duration correction. Compare real modern destinations, not just a mirror decoder model.
5. Validate truncation at each field/header/slot boundary; empty slots; three distinct primaries; canonical 0x8000 and minimal complete buffers; checksum disagreement; ambiguous `01 01` capacity; modified capacity with explicitly selected source order; bad magic; an unaligned input starting address; duplicate/occupied backup bytes ignored as current behavior; and no source rename on any read/decode/write failure.
6. Verify Xbox compiler sizes/offsets separately. This audit's ctypes check below is a layout audit, **not an XDK compiler/ABI or emulator execution check**.

## Layout evidence

The following tables are mechanically derived from the pinned 9.2.3 declarations using fixed-width ctypes scalar types and natural alignment. All 150 annotated offsets matched. The top-level context has 112 members and size `0x1428`. The historical persistent declaration sequence matches current legacy declarations. **Inventory's source comment says size 0x5E, but its actual naturally aligned size is 0x60**, because its u32 members impose 4-byte alignment; the following scene-flags offset proves the 2-byte tail padding. Do not pack these structs.

Offsets below are relative to the named structure. Nested bases are in the SaveContext_v0 table. Any field after `checksum` is runtime tail storage, not consumed by current CopyV0Save. The checksum itself is not copied either. Other unused/padding members (`unk_58`, etc.) must not be promoted into new saved state.

Pinned SaveManager.cpp SHA-256: `7fe420b55cd0679069eb7f484b386b45910b5fff7fe227cc6832ed0f7eef79dc`.

### ItemEquips_v0 â€” size 0xA, alignment 2

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `buttonItems` | `u8[4]` | 4 |
| `0x0004` | `cButtonSlots` | `u8[3]` | 3 |
| `0x0008` | `equipment` | `u16` | 2 |

### Inventory_v0 â€” size 0x60, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `items` | `u8[24]` | 24 |
| `0x0018` | `ammo` | `s8[16]` | 16 |
| `0x0028` | `equipment` | `u16` | 2 |
| `0x002C` | `upgrades` | `u32` | 4 |
| `0x0030` | `questItems` | `u32` | 4 |
| `0x0034` | `dungeonItems` | `u8[20]` | 20 |
| `0x0048` | `dungeonKeys` | `s8[19]` | 19 |
| `0x005B` | `defenseHearts` | `s8` | 1 |
| `0x005C` | `gsTokens` | `s16` | 2 |

### SavedSceneFlags_v0 â€” size 0x1C, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `chest` | `u32` | 4 |
| `0x0004` | `swch` | `u32` | 4 |
| `0x0008` | `clear` | `u32` | 4 |
| `0x000C` | `collect` | `u32` | 4 |
| `0x0010` | `unk` | `u32` | 4 |
| `0x0014` | `rooms` | `u32` | 4 |
| `0x0018` | `floors` | `u32` | 4 |

### Vec3i_v0 â€” size 0xC, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `x` | `s32` | 4 |
| `0x0004` | `y` | `s32` | 4 |
| `0x0008` | `z` | `s32` | 4 |

### FaroresWindData_v0 â€” size 0x28, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `pos` | `Vec3i_v0` | 12 |
| `0x000C` | `yaw` | `s32` | 4 |
| `0x0010` | `playerParams` | `s32` | 4 |
| `0x0014` | `entranceIndex` | `s32` | 4 |
| `0x0018` | `roomIndex` | `s32` | 4 |
| `0x001C` | `set` | `s32` | 4 |
| `0x0020` | `tempSwchFlags` | `s32` | 4 |
| `0x0024` | `tempCollectFlags` | `s32` | 4 |

### Vec3s_v0 â€” size 0x6, alignment 2

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `x` | `s16` | 2 |
| `0x0002` | `y` | `s16` | 2 |
| `0x0004` | `z` | `s16` | 2 |

### HorseData_v0 â€” size 0xA, alignment 2

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `scene` | `s16` | 2 |
| `0x0002` | `pos` | `Vec3s_v0` | 6 |
| `0x0008` | `angle` | `s16` | 2 |

### Vec3f_v0 â€” size 0xC, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `x` | `f32` | 4 |
| `0x0004` | `y` | `f32` | 4 |
| `0x0008` | `z` | `f32` | 4 |

### RespawnData_v0 â€” size 0x1C, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `pos` | `Vec3f_v0` | 12 |
| `0x000C` | `yaw` | `s16` | 2 |
| `0x000E` | `playerParams` | `s16` | 2 |
| `0x0010` | `entranceIndex` | `s16` | 2 |
| `0x0012` | `roomIndex` | `u8` | 1 |
| `0x0013` | `data` | `s8` | 1 |
| `0x0014` | `tempSwchFlags` | `u32` | 4 |
| `0x0018` | `tempCollectFlags` | `u32` | 4 |

### SaveContext_v0 â€” size 0x1428, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `entranceIndex` | `s32` | 4 |
| `0x0004` | `linkAge` | `s32` | 4 |
| `0x0008` | `cutsceneIndex` | `s32` | 4 |
| `0x000C` | `dayTime` | `u16` | 2 |
| `0x0010` | `nightFlag` | `s32` | 4 |
| `0x0014` | `totalDays` | `s32` | 4 |
| `0x0018` | `bgsDayCount` | `s32` | 4 |
| `0x001C` | `newf` | `char[6]` | 6 |
| `0x0022` | `deaths` | `u16` | 2 |
| `0x0024` | `playerName` | `char[8]` | 8 |
| `0x002C` | `n64ddFlag` | `s16` | 2 |
| `0x002E` | `healthCapacity` | `s16` | 2 |
| `0x0030` | `health` | `s16` | 2 |
| `0x0032` | `magicLevel` | `s8` | 1 |
| `0x0033` | `magic` | `s8` | 1 |
| `0x0034` | `rupees` | `s16` | 2 |
| `0x0036` | `swordHealth` | `u16` | 2 |
| `0x0038` | `naviTimer` | `u16` | 2 |
| `0x003A` | `magicAcquired` | `u8` | 1 |
| `0x003B` | `unk_3B` | `char[0x01]` | 1 |
| `0x003C` | `doubleMagic` | `u8` | 1 |
| `0x003D` | `doubleDefense` | `u8` | 1 |
| `0x003E` | `bgsFlag` | `u8` | 1 |
| `0x003F` | `ocarinaGameRoundNum` | `u8` | 1 |
| `0x0040` | `childEquips` | `ItemEquips_v0` | 10 |
| `0x004A` | `adultEquips` | `ItemEquips_v0` | 10 |
| `0x0054` | `unk_54` | `u32` | 4 |
| `0x0058` | `unk_58` | `char[0x0E]` | 14 |
| `0x0066` | `savedSceneNum` | `s16` | 2 |
| `0x0068` | `equips` | `ItemEquips_v0` | 10 |
| `0x0074` | `inventory` | `Inventory_v0` | 96 |
| `0x00D4` | `sceneFlags` | `SavedSceneFlags_v0[124]` | 3472 |
| `0x0E64` | `fw` | `FaroresWindData_v0` | 40 |
| `0x0E8C` | `unk_E8C` | `char[0x10]` | 16 |
| `0x0E9C` | `gsFlags` | `s32[6]` | 24 |
| `0x0EB4` | `unk_EB4` | `char[0x4]` | 4 |
| `0x0EB8` | `highScores` | `s32[7]` | 28 |
| `0x0ED4` | `eventChkInf` | `u16[14]` | 28 |
| `0x0EF0` | `itemGetInf` | `u16[4]` | 8 |
| `0x0EF8` | `infTable` | `u16[30]` | 60 |
| `0x0F34` | `unk_F34` | `char[0x04]` | 4 |
| `0x0F38` | `worldMapAreaData` | `u32` | 4 |
| `0x0F3C` | `unk_F3C` | `char[0x4]` | 4 |
| `0x0F40` | `scarecrowCustomSongSet` | `u8` | 1 |
| `0x0F41` | `scarecrowCustomSong` | `u8[0x360]` | 864 |
| `0x12A1` | `unk_12A1` | `char[0x24]` | 36 |
| `0x12C5` | `scarecrowSpawnSongSet` | `u8` | 1 |
| `0x12C6` | `scarecrowSpawnSong` | `u8[0x80]` | 128 |
| `0x1346` | `unk_1346` | `char[0x02]` | 2 |
| `0x1348` | `horseData` | `HorseData_v0` | 10 |
| `0x1352` | `checksum` | `u16` | 2 |
| `0x1354` | `fileNum` | `s32` | 4 |
| `0x1358` | `unk_1358` | `char[0x0004]` | 4 |
| `0x135C` | `gameMode` | `s32` | 4 |
| `0x1360` | `sceneSetupIndex` | `s32` | 4 |
| `0x1364` | `respawnFlag` | `s32` | 4 |
| `0x1368` | `respawn` | `RespawnData_v0[3]` | 84 |
| `0x13BC` | `entranceSpeed` | `f32` | 4 |
| `0x13C0` | `entranceSound` | `u16` | 2 |
| `0x13C2` | `unk_13C2` | `char[0x0001]` | 1 |
| `0x13C3` | `unk_13C3` | `u8` | 1 |
| `0x13C4` | `dogParams` | `s16` | 2 |
| `0x13C6` | `textTriggerFlags` | `u8` | 1 |
| `0x13C7` | `showTitleCard` | `u8` | 1 |
| `0x13C8` | `nayrusLoveTimer` | `s16` | 2 |
| `0x13CA` | `unk_13CA` | `char[0x0002]` | 2 |
| `0x13CC` | `rupeeAccumulator` | `s16` | 2 |
| `0x13CE` | `timerState` | `s16` | 2 |
| `0x13D0` | `timerSeconds` | `s16` | 2 |
| `0x13D2` | `subTimerState` | `s16` | 2 |
| `0x13D4` | `subTimerSeconds` | `s16` | 2 |
| `0x13D6` | `timerX` | `s16[TIMER_ID_MAX]` | 4 |
| `0x13DA` | `timerY` | `s16[TIMER_ID_MAX]` | 4 |
| `0x13DE` | `unk_13DE` | `char[0x0002]` | 2 |
| `0x13E0` | `seqId` | `u8` | 1 |
| `0x13E1` | `natureAmbienceId` | `u8` | 1 |
| `0x13E2` | `buttonStatus` | `u8[5]` | 5 |
| `0x13E7` | `forceRisingButtonAlphas` | `u8` | 1 |
| `0x13E8` | `unk_13E8` | `u16` | 2 |
| `0x13EA` | `unk_13EA` | `u16` | 2 |
| `0x13EC` | `unk_13EC` | `u16` | 2 |
| `0x13EE` | `unk_13EE` | `u16` | 2 |
| `0x13F0` | `unk_13F0` | `s16` | 2 |
| `0x13F2` | `unk_13F2` | `s16` | 2 |
| `0x13F4` | `unk_13F4` | `s16` | 2 |
| `0x13F6` | `unk_13F6` | `s16` | 2 |
| `0x13F8` | `unk_13F8` | `s16` | 2 |
| `0x13FA` | `eventInf` | `u16[4]` | 8 |
| `0x1402` | `mapIndex` | `u16` | 2 |
| `0x1404` | `minigameState` | `u16` | 2 |
| `0x1406` | `minigameScore` | `u16` | 2 |
| `0x1408` | `unk_1408` | `char[0x0001]` | 1 |
| `0x1409` | `language` | `u8` | 1 |
| `0x140A` | `audioSetting` | `u8` | 1 |
| `0x140B` | `unk_140B` | `char[0x0001]` | 1 |
| `0x140C` | `zTargetSetting` | `u8` | 1 |
| `0x140E` | `forcedSeqId` | `u16` | 2 |
| `0x1410` | `unk_1410` | `u8` | 1 |
| `0x1411` | `unk_1411` | `char[0x0001]` | 1 |
| `0x1412` | `nextCutsceneIndex` | `u16` | 2 |
| `0x1414` | `cutsceneTrigger` | `u8` | 1 |
| `0x1415` | `chamberCutsceneNum` | `u8` | 1 |
| `0x1416` | `nextDayTime` | `u16` | 2 |
| `0x1418` | `fadeDuration` | `u8` | 1 |
| `0x1419` | `unk_1419` | `u8` | 1 |
| `0x141A` | `skyboxTime` | `u16` | 2 |
| `0x141C` | `dogIsLost` | `u8` | 1 |
| `0x141D` | `nextTransition` | `u8` | 1 |
| `0x141E` | `unk_141E` | `char[0x0002]` | 2 |
| `0x1420` | `worldMapArea` | `s16` | 2 |
| `0x1422` | `sunsSongState` | `s16` | 2 |
| `0x1424` | `healthAccumulator` | `s16` | 2 |

## Implementation addendum

The bounded audit has now been implemented independently in `platform/shipyard/legacy-save` with `tools/shipyard/prepare_legacy_save.py` and `test_legacy_save.py`. Full ConvertFromUnversioned and the generated decoder compile for native PPC; the actual unchanged CopyV0Save matches 192 complete modern destination objects against actual historical-producer fixtures in LE and synthesized BE. Reader checks include every 16-bit pattern and 15,592 truncated lengths. The implementation normalizes song durations before the unchanged upstream memcpy, rather than overriding destination notes afterward. It performs stricter checksum/marker/order validation explicitly and preserves unknown input by throwing before writes. The historical producer's OS_K1_TO_PHYSICAL macro was independently verified as `(0)` in its locked libultraship convert.h.

The owning generator must still bind Init's existence/read/rename to the supplied selected-storage Path/BackupPath and commit the successful backup rename. The isolated method already flushes real modern outputs before returning. See the module README for precise integration and the remaining full-application/XContent runtime validation limits.
