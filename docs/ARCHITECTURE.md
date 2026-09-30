# Architecture

## Ownership

The pinned `soh` tree and submodules define game behavior, data schemas, and
extraction. `platform/shipyard` holds SoH-specific adapters and source locks;
`tools/shipyard` holds projection, build, and test tools. Shipyard owns shared
Xbox services and compiler compatibility. `scratch` contains generated sources,
dependency working copies, objects, manifests, and build records.

`platform-base.lock.json` selects Shipyard independently of the upstream game
revision. Source locks reject changed inputs before generation. Keep game
policy in this consumer and reusable Xbox mechanisms in Shipyard.

## Modules

Each entry names its directory under `platform/shipyard`. Preparation scripts
and focused contracts live under `tools/shipyard`; the build guide describes
their invocation. Preserve complete source bodies and declaration ownership
when lowering syntax for the XDK.

| Module | Responsibility and constraint |
| --- | --- |
| `app-services` | ActorDB retains actor registrations and description ordering; ConfigUpdaters retains all six migrations and their copy/clear order. |
| `application` | OTRGlobals owns startup, resource registration, audio processing, and teardown. Mount storage before writable paths are selected; start XNet before its consumers. |
| `application-core` | Scene, message, resource, GBI, utility, notification, and crash bridges use the modern resource types. JPEG conversion writes explicit RGBA16 high/low bytes. |
| `application-editors` | Audio and cosmetics editors retain tables, widget defaults, search references, and graphics patch arguments. Keep their static registrations in the link. |
| `application-extras` | Presets, time displays/splits, boss rush, input viewer, equipment, console, mods, names, and statistics retain their application hooks and JSON fields. |
| `application-gui` | SohGui owns the full window registration set. Window declarations preserve fields, defaults, and shared ownership; AudioCollection supplies AudioSeqType. |
| `application-windows` | Debugger windows, ImGuiUtils, and ResolutionEditor keep their rendering bodies and current interfaces. Temporary aggregate backing storage remains in factory scope. |
| `async` | Native workers, mutexes, events, condition variables, joining threads, and futures preserve blocking and ownership. A worker must not join itself. |
| `audio` | XAudio2 retains buffers through callback completion and destroys voices before freeing storage. Modern audio settings come from AudioPlayer; the factory preserves derived deletion. |
| `audio-collection` | Sequence tables insert in source order with first-key behavior. Collection sets retain pointers into the owning map; filename handling uses the filesystem adapter. |
| `binary` | BinaryReader and BinaryWriter use each record's byte-order marker. Native endian detection and unconditional byte swaps remain separate operations. |
| `build` | Subsystem configuration selects source providers and compile records. Generated source, header, and object identities must agree before linking. |
| `codecs` | Pinned Opus/Opusfile/Ogg retain codec algorithms, floating-point CELT/SILK, and hardening. Temporary stack storage uses upstream allocation policy. |
| `configuration` | Config retains its JSON state, migrations, defaults, and reload behavior. XAudio2/Xenos backend values extend the upstream enum domains. |
| `console-variables` | ConsoleVariable retains typed JSON traversal, registration, color conversion, and persistence. Value initialization preserves integer type and null string storage. |
| `context` | Context owns initialization order and subsystem lifetimes. Partial startup cleanup checks initialized owners; Xbox dialogs wait for asynchronous completion. |
| `crt` | Shipyard supplies missing float rounding and C99 formatting functions. Preserve signed zero, exceptional values, required lengths, and terminated truncation. |
| `custom-message` | The full message implementation retains string bytes, language formatting, table order, and application service methods. Bounded host probes do not replace those services. |
| `enhancements` | Cheats, fixes, and ShipInit retain callbacks and conditions. Generated hook locations use original source anchors; variadic arguments keep XDK promotion/alignment. |
| `fast-resources` | Display-list, matrix, vertex, light, and texture factories keep BinaryReader order and raw texture bytes. F3DEX_GBI_2 stays consistent across consumers. |
| `fast3d` | The complete modern interpreter retains six opcode tables, duplicate-key order, texture-cache equality, and aggregate initialization. RGB5551 readback is native numeric data. |
| `filesystem` | Paths support Xbox mounts and native ANSI APIs. Mount storage before logical working-directory setup; rename preserves the old file if replacement fails. read_file is capped at 128 MiB. |
| `game` | Application C stays under /TC. Scoped lowering preserves declaration execution and boolean conversion; unsupported boolean shapes reject explicitly. |
| `game-interactor` | Hooks retain registry, dispatch, removal, forwarding, and cross-unit template storage. Explicit original source locations replace unavailable call-site intrinsics. |
| `gameplay-features` | Complete selected feature translation units retain game rules, hooks, callbacks, and registrations; source locks cover their shared declarations. |
| `gfxd` | The graphics disassembler keeps all five ucode targets and its public I/O and formatting APIs. Each source selects its own ucode definitions. |
| `graphics` | Modern rendering interfaces and the combiner decoder feed shared shader generation. Shader and vertex layouts must match the selected interpreter. |
| `gui` | Native dispatch handles ImGui setup, events, draws, and shutdown. Xbox has no independent desktop viewports; the clipboard is application-local. |
| `gui-resources` | Font, texture, overlay, and stb decoding retain buffer ownership, validation, failures, dimensions, and allocation/free pairs. |
| `imgui` | Pinned docking ImGui uses the LUS math and pointer ImTextureID configuration. Constructor and callback lowering rejects unaudited shapes. |
| `input` | ControlDeck and mappings retain modern config and remapping behavior. CONTROLLERBUTTONS_T stays uint32_t; native capabilities determine supported controller features. |
| `interpolation` | Pinned recorder, matrix, angle, actor, and camera algorithms remain application-owned. The replacement map transfers ownership when returned. |
| `json` | Shipyard owns the JSON backend and algorithm generators. Consumer probes retain reached modern enum and ordered-object semantics; duplicate insertion order matters. |
| `legacy-save` | The bounded decoder reads producer-order fields into aligned legacy structures before CopyV0Save. Validate every occupied primary slot before writing modern saves. |
| `libultra` | Pinned libultra and controller/graphics/resource bridges retain upstream implementations and C linkage, including upstream empty bodies. |
| `libzip` | Pinned libzip, zlib, and tinyxml2 retain archive algorithms. Narrow named-file operations use the filesystem boundary; unsupported native providers report errors. |
| `logging` | Pinned spdlog algorithms use Shipyard native synchronization. Filtering precedes conversion; formatting precedes enqueue, and queued messages own payload and logger lifetime. |
| `native-imgui` | The native renderer preserves state restoration, clipping, callbacks, and texture ABI. Font-atlas numeric colors and decoder RGBA byte buffers have distinct endian boundaries. |
| `network` | ENABLE_REMOTE_CONTROL must be consistent across all Network consumers. XDK transport owns sockets, synchronization, framing, and receive lifetimes. |
| `network-app` | Anchor, Sail, Crowd Control, and their menus retain packet handlers, game hooks, actors, effects, and registrations. Stop their producers before transport teardown. |
| `object-extension` | Object registry identities and payload types remain upstream-owned. The any compatibility subset uses RTTI, clones on copy, and preserves the destination if copying fails. |
| `presentation` | Native display creation precedes rendering and system UI. Output is 1280x720 fullscreen; upstream owns internal resolution, GUI, framebuffer, and interpolation policy. |
| `prism` | The pinned Prism projector retains the modern shader resource loader and include policy. Missing defaults and unsupported expressions fail explicitly. |
| `randomizer` | Complete Context, message, trial, hint, and item-location declarations preserve field order, defaults, and type identity across providers. |
| `randomizer-application` | Initialization, gameplay hooks, entrance handling, plandomizer, trackers, saves, and menu remain game-owned. JSON right-hand values complete before assignment. |
| `randomizer-content` | Item, location, category, enum, check, trick, and hint tables retain source order, values, and shared declaration ownership. |
| `randomizer-context` | SeedContext, item locations, fishsanity, kaleido, and item tables use the full shared Context, Logic, Settings, Hint, and Item declarations. |
| `randomizer-data` | Location factories and StaticData retain constructor arguments and ordered map/vector construction. Shared headers come from their owning provider. |
| `randomizer-dungeons` | Dungeon and trial methods retain vanilla/MQ keys, definitions, placement operations, JSON handling, and field layouts. |
| `randomizer-generation` | Seed generation retains retry paths, settings hashing, RNG calls, item/hint placement, spoiler output, and menu persistence. |
| `randomizer-hints` | Hint uses the full shared declaration and source-locked implementation; StaticHintInfo retains its source-derived constructor. HintText belongs to randomizer-item. |
| `randomizer-item` | Item retains progressive-item rules, effects, fields, hints, and value semantics. Text and LogicVal remain shared types. |
| `randomizer-logic` | The complete Logic implementation owns its constructor and game rules. Do not also link the separate LogicConstructor fragment. |
| `randomizer-options` | Option, LocationOption, TrickSetting, OptionGroup, Tricks, and Settings retain their declarations. OptionValue has one provider. |
| `randomizer-regions` | The full reachability graph retains callbacks, access conditions, source order, and shared location/shop declarations. |
| `randomizer-settings` | Complete settings and descriptions retain options, tricks, callbacks, and CVars. Do not also link the separate SettingsConstructor fragment. |
| `resource-shutdown` | Stop producers, retain Context, drain resource jobs, then drain detached codec jobs. Barriers cannot run on a waited-for worker or under a lock that worker needs. |
| `resources` | Leaf resource types and binary/XML factories retain type/version handling. Archive, loader, and manager providers keep cache, mod precedence, and ownership policies. |
| `save-manager` | Full SaveManager owns serialization, section registration, versions, randomizer metadata, and workers. Link LegacyDecode but exclude the obsolete serialization fragment. |
| `save-storage` | Mount the 16 MiB 3Shipsty XContent package as shipyard: before SaveManager starts. Drain writers before flush/close; serialize atomic replacements per destination. |
| `savestates` | SaveStateMgr preserves complete snapshots and request handling. Shared audio locking spans Save/Load; the application provider owns its declarations. |
| `ship-utils` | ShipUtils and randomizer RNG retain complete source bodies and entropy behavior. Link their native entropy provider with the generated units. |
| `soh-input-editor` | The SoH editor retains controller configuration, raw remapping, deadzones, rumble, and D-pad menus. Native queries must not claim unsupported gyro or LED features. |
| `soh-menus` | Menus retain widgets, searches, predicates, and modals. The desktop file-manager action is disabled with a platform explanation on Xbox. |
| `soh-resources` | Factories retain scene-command IDs and per-record byte order. SoundFont XML patches require RTTI; prepare resource, binary, logging, and Fast3D headers first. |
| `soh-ui` | Widget option constructors distinguish default from value initialization. SearchWidget preserves its reference; all consumers use the same projected variant declarations. |
| `speech` | eSpeak runs synchronously on its worker and submits owned PCM to a separate XAudio2 voice. New or empty requests cancel prior speech; join workers before releasing buffers. |
| `thread-pool` | Pinned BS v4.1.0 retains blocking futures, priority/pause policy, captured task ownership, and drain semantics for resources and saves. |
| `vorbis` | The full pinned libvorbisfile decoder and Ogg dependency retain format handling. Host SIMD and PPC fallback can differ in least-significant PCM rounding. |
| `window` | Window and GUI classes retain full ownership and lifecycle. Constructors preserve original defaults, including mLastScancode=-1 and value-initialized flags. |
| `xenos` | Shared Xenos uses shader ABI 2, six samplers, independent clears, framebuffer copies, and native RGB5551 reads. Modern adapts its uint64/uint32 shader IDs. |

## Rendering and resources

The modern virtual rendering API combines 64-bit and 32-bit shader IDs and six
texture bindings. Mask/blend inputs, custom shader bits, integer combiners,
filtering, and sRGB participate in shader identity. Resource overrides feed the
Prism shader builder. External rendering must invalidate shared state caches.
Texture upload formats, numeric framebuffer reads, and serialized resource
fields have separate byte-order rules.

ZIP/MPQ containers retain their formats; each resource record selects its own
byte order. Check entry sizes and exact reads, and release handles on failure.
StormLib applies the pinned LUS patch and keeps its compression/signature
algorithms. Its integer records are little endian; the Xbox platform selects
StormLib's big-endian conversion paths and portable crypto operations.

Modern resource loading removes the legacy header from its buffer. Preserve
modern factory versions, alternate-resource identities, and mod precedence.
Do not import another game's blob offsets, MIDI padding, or archive schema.
Remove cache entries under the cache lock and destroy resources after unlocking
when destruction can reenter other services. Nested work must not deadlock a
single-worker pool.

## Storage and legacy import

Packaged archives live under `game:`. Writable saves use
`shipyard:\Save\fileN.sav` and `global.sav`. Background writes own serialized
bytes. Complete writes, file flushes, replacement, and XContent completion are
separate operations; enqueue is not persistence. A failure after replacement
reports an error without promising rollback or power-loss recovery.

Unversioned `oot_save.sav` stores producer-native structures without an endian
tag. Decode bounded scalar bytes into aligned objects and preserve signed bit
patterns. Do not infer save byte order from ROM or resource order. Validate all
occupied slots before any write; unknown or ambiguous inputs retain the source.
The decoder requires producer checksums and link-age 0/1; if both orders fit,
a unique ordinary vanilla health capacity can resolve the tie.

| Legacy property | Value |
| --- | --- |
| Header size / identity at bytes 3–11 | `0x10` / `98 09 10 21 5A 45 4C 44 41` |
| Context size / slot stride | `0x1428` / `0x1450` |
| Primary offsets | `0x0020`, `0x1470`, `0x28C0` |
| Backup offsets | `0x3D10`, `0x5160`, `0x65B0` |
| Three-primary minimum / SRAM size | `0x3CE8` / `0x8000` |
| Occupied marker | `ZELDAZ` at context offset `0x001C` |
| Checksum | producer-order u16 at `0x1352`; sum `0x1354` bytes with checksum zero modulo 65536 |
| Long song / spawn song | `0x0F41` with 108 records / `0x12C6` with 16 |

Each song note is eight bytes with a producer-order u16 duration at offset 2;
convert only that field. Farore's Wind coordinates are signed 32-bit integers.
Inventory_v0 has natural size `0x60`; do not pack it to the upstream comment's
`0x5E`. Runtime tail fields after the persistent structure are not imported.
The projector emits size/offset assertions from the pinned declarations and
retains CopyV0Save and modern section/version handling.

## Speech and shutdown

Package PC-generated `espeak-ng-data` beside the game and retain
`phondata-manifest`. The provider reads `game:\espeak-ng-data` and converts
selected little-endian data fields and PCM samples. Distribution must preserve
eSpeak's GPL notices, corresponding source, and build modifications.

Stop gameplay speech, remote, audio, and resource producers before teardown.
Join workers and drain SaveManager while their services remain alive. Keep a
strong Context through resource-pool drain followed by detached codec drain.
Destroy voices before freeing PCM storage, release Context, then close storage
and XNet. Never destroy a voice from its callback or wait while holding a lock
needed by the worker being drained.
