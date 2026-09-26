# Legacy save format

The unversioned `oot_save.sav` format stores the producer's native structures.
It has no endian tag. Imported scalar values require bounded decoding in the
producer's byte order; ROM/resource byte order does not identify that order.

## Producer provenance

Shipwright commit `b4eebbbcd6951a6194d927effe3b519e42319dec` introduced versioned
saves. Its parent `73ff7ef3dae83ec85afb20ec6453c69967bb0b96` supplies the raw-save
producer: `soh/src/code/z_sram.c` calculates the native checksum and passes
`gSaveContext` to `SsSram_ReadWrite`; `soh/src/code/z_ss_sram.c` writes its bytes
with `fwrite(dramAddr, size, 1, saveFile)`. The persistent declarations in
`soh/include/z64save.h` match the legacy layout retained by the 9.2.3 converter.

The corresponding song producers in `soh/src/code/z_message_PAL.c` copy
`OcarinaNote` records into byte arrays. These records contain native-order
16-bit duration fields despite their byte-array containers.

The pinned 9.2.3 `SaveManager.cpp` SHA-256 is
`7fe420b55cd0679069eb7f484b386b45910b5fff7fe227cc6832ed0f7eef79dc`.
The maintained conversion and contracts are in
[legacy-save](../../platform/shipyard/legacy-save/README.md).

## Geometry and decoding

| Property | Value |
| --- | --- |
| Header size | `0x10` bytes |
| Header identity at bytes 3–11 | `98 09 10 21 5A 45 4C 44 41` |
| Raw context size / slot stride | `0x1428` / `0x1450` |
| Primary offsets | `0x0020`, `0x1470`, `0x28C0` |
| Historical backup offsets | `0x3D10`, `0x5160`, `0x65B0` |
| Complete three-primary minimum | `0x3CE8` bytes |
| Historical SRAM file size | `0x8000` bytes |
| Occupied primary marker | `ZELDAZ` at context offset `0x001C` |
| Checksum | producer-order `u16` at `0x1352` |

The historical checksum sums producer-order words over `0x1354` bytes with the
checksum field zero, modulo 65536. A checksum alone is not an endian signature:
some byte sequences validate under both orders. Health capacity alone is also
insufficient; bytes `01 01` pass a simple range check in both orders. Unknown or
ambiguous inputs require explicit handling before any persistent write.

Decode multibyte values from bounded bytes, preserving signed bit patterns and
alignment. Byte fields remain unchanged. Farore's Wind coordinates are signed
32-bit integers, not floats. Current conversion does not consume the runtime
tail after the persistent save structure.

The long song starts at `0x0F41` with 108 records; the spawn song starts at
`0x12C6` with 16. Each 8-byte note contains its 16-bit duration at offset 2.
Decode only that field; blanket byte-array copies leave cross-endian durations
wrong, while blanket word swaps corrupt the adjacent byte fields.

Modern section/version handling remains in the real `CopyV0Save` and save
manager. Source retention, failure behavior, selected-storage paths, and flush/
rename ordering are part of the conversion contract. The bounded decoder
normalizes song durations before the upstream copy and rejects unknown input
before writing.

## Declaration layout

The tables derive from fixed-width scalar types and natural alignment in the
pinned declarations. They are a format reference, not proof of compiler ABI or
runtime execution. `Inventory_v0` is naturally `0x60` bytes despite the upstream
comment's `0x5E`; its 32-bit fields require tail padding. Do not pack the layout.
Fields after `checksum` are runtime tail storage and are not imported by
`CopyV0Save`; padding and unused members do not become saved state.

### ItemEquips_v0 — size 0xA, alignment 2

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `buttonItems` | `u8[4]` | 4 |
| `0x0004` | `cButtonSlots` | `u8[3]` | 3 |
| `0x0008` | `equipment` | `u16` | 2 |

### Inventory_v0 — size 0x60, alignment 4

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

### SavedSceneFlags_v0 — size 0x1C, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `chest` | `u32` | 4 |
| `0x0004` | `swch` | `u32` | 4 |
| `0x0008` | `clear` | `u32` | 4 |
| `0x000C` | `collect` | `u32` | 4 |
| `0x0010` | `unk` | `u32` | 4 |
| `0x0014` | `rooms` | `u32` | 4 |
| `0x0018` | `floors` | `u32` | 4 |

### Vec3i_v0 — size 0xC, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `x` | `s32` | 4 |
| `0x0004` | `y` | `s32` | 4 |
| `0x0008` | `z` | `s32` | 4 |

### FaroresWindData_v0 — size 0x28, alignment 4

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

### Vec3s_v0 — size 0x6, alignment 2

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `x` | `s16` | 2 |
| `0x0002` | `y` | `s16` | 2 |
| `0x0004` | `z` | `s16` | 2 |

### HorseData_v0 — size 0xA, alignment 2

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `scene` | `s16` | 2 |
| `0x0002` | `pos` | `Vec3s_v0` | 6 |
| `0x0008` | `angle` | `s16` | 2 |

### Vec3f_v0 — size 0xC, alignment 4

| Offset | Field | Type | Bytes |
|---|---|---|---:|
| `0x0000` | `x` | `f32` | 4 |
| `0x0004` | `y` | `f32` | 4 |
| `0x0008` | `z` | `f32` | 4 |

### RespawnData_v0 — size 0x1C, alignment 4

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

### SaveContext_v0 — size 0x1428, alignment 4

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
