# Stable AudioCollection projection

`tools/shipyard/prepare_audio_collection.py` generates the complete pinned 9.2.3
AudioCollection declaration and implementation in `scratch/audio-collection-xdk`.
Inputs are SHA-256 locked; original application and donor files are unchanged.

## Application contract and translation

This is 3Shipsty application compatibility work using existing generic Shipyard
filesystem/platform interfaces. No alternate collection or service implementation
is supplied. The complete source TU compiles, including the genuine CVar, Gui and
notification calls. `AudioCollection::Instance` remains owned by the application.

| Class | Boundary | Adaptation |
|---|---|---|
| A/B | `std::map` initializer-list assignment | Exact source macro and all 258 source rows remain in a static POD row array. Insert each row into the real map in source order, retaining first-key behavior and all six SequenceInfo fields. The map has 257 unique keys. |
| A | In-class boolean initializer | Move `shufflePoolInitialized=false` to the existing user-provided constructor initializer list. Default and value construction both retain false. SequenceInfo stays the original aggregate without added constructors. |
| A | Structured binding loop | Traverse the same map by iterator and bind SequenceInfo by reference; the real sets retain pointers into that map. |
| B | `contains`/`emplace` | Use matching typed `find` and `insert(make_pair)`. No overwrite, integer validation, clamping or key conversion changes. |
| A | Designated Notification::Options initializer | Construct the canonical Options using its complete existing defaults, assign message/duration, call the original Emit service. |
| E | `filesystem::path(...).filename()` | Use the existing Shipyard filesystem implementation. Keep original splitting, case conversion and key sanitization, including upstream extension handling. |
| I | Broad umbrella includes | Include the exact Context/Window/Gui declarations used; remove the unused OTRGlobals dependency. |

The canonical generated `soh/Enhancements/audio/sequence_type.h` contains the exact
upstream SeqType enum. AudioCollection.h includes that path; it does not redeclare
the enum. The application-GUI generator must stop generating its prior temporary
sequence_type.h and remove that stale generated copy, because AudioEditor.h uses
a quoted sibling include. Do not let both generated files coexist in the final
include graph. Prepend `scratch/audio-collection-xdk/generated/soh` to consumers.

## Reproduction and integration

```
C:\Python313\python.exe -B tools/shipyard/prepare_audio_collection.py --build
C:\Python313\python.exe -B tools/shipyard/test_audio_collection.py
```

The isolated native recipe consumes existing `scratch/soh-menus-xdk/xdk/build.json`
and its generated dependencies; it does not run shared generators. The production
source is `generated/soh/soh/Enhancements/audio/AudioCollection.cpp`. The native
`declarations.cpp` ABI probe is not a production source. Its emitted PPC data
proves sizeof(AudioCollection)=52, sizeof(SequenceInfo)=68 and SEQ_BGM_CUSTOM=7.

Four tests pass. Original and projected host method audits print identical fields
for every map entry, and exercise map copies, missing names, custom paths/categories,
duplicate insertion, duplicate-label set equivalence, pointer identity, initial
pool construction, idempotence, add/remove, replacement fallbacks, morning-field
special handling, uint16 key conversion, and notification defaults/duration.

Host scope is explicit: real AudioCollection bodies and pinned StringHelper/CVar
bodies are extracted, with CVar member qualification rebased onto identical
storage for the isolated audit. The two live Gui scheduling calls, Config erase
dispatch and Notification::Emit dispatch are excluded only from that host audit.
Their production calls are retained and the complete production TU compiles.
This test does not claim Config persistence, a rendered notification, native
execution, Xenia execution, or hardware validation. No fake services are linked
into the application.

Evidence: `manifest.json`, `verification.json`, host `compile.json`/`run.json`,
native `xdk/build.json`, logs and native objects under the provider scratch root.
