# Complete modern randomizer Logic

This provider compiles the entire pinned 9.2.3 `logic.cpp`: all 132 original
function definitions, including item effects, combat/access rules, live-check
logic, state reset, dungeon completion, scene-resource door lookup, and save
context management. It uses the existing complete canonical Logic declaration
from the Item provider. There is no alternative logic class or synthetic state.

```
C:/Python313/python.exe -B tools/shipyard/prepare_randomizer_logic.py --build
C:/Python313/python.exe -B tools/shipyard/test_randomizer_logic.py
```

The production object is `scratch/randomizer-logic-xdk/xdk/logic.obj`.
**Remove the Item provider's `LogicConstructor.obj` from the aggregate link**;
this complete object includes that same real constructor and its relocated
member defaults. Use `prepare_randomizer_logic.includes()` before existing
include paths. `xdk/build.json` records exact flags and fresh source/object
hashes; the COFF machine is verified as PPC 0x1f2.

## Translation boundaries

* A: Move the original 15 Logic member defaults into the actual constructor,
  using the same source inventory as the canonical Item provider.
* A: Replace the unsupported fallthrough annotation with a comment and lower
  three range loops through the established iterator/reference helper.
* A: Switch on the canonical strong GlitchType wrapper's explicit GetValue().
  Preserve its original cases, fallthrough, return values, and type identity.
* A/B: Initialize five actual map objects with generated ordered row tables and
  `insert`, retaining original entries, duplicate-key first-insertion behavior,
  initialization scope, and comparator. Native map lookups remain native maps.
* A/B: Construct the three Gerudo-fortress door vectors from the same 4/1/0
  elements and replace one empty-vector assignment with its typed equivalent.
  Replace one map contains test with find/end without changing the key.
* I: Select the real canonical Scene, SceneCommand, SetTransitionActorList,
  ResourceManager, Item, and Option headers. Resource RTTI and real archive
  loading remain in the complete method body.
* B/I: Include a generated exact TimerID enum plus the actual Start/Stop timer
  declarations used here, avoiding unrelated chrono objects in the diagnostic
  header. Calls remain unresolved real diagnostic services until their provider
  is linked; they are never replaced with empty functions.

The full actual DungeonInfo/Dungeons header is projected because Logic calls
their methods. All fields and method declarations are retained. Five original
DungeonInfo defaults (including the two empty-brace zero initializers) move to
the original constructors in the emitted complete `dungeon.cpp`. That dependency
source is retained but **not compiled or claimed complete by this provider**.
Its future native provider must use those relocated constructor defaults. No
DungeonInfo construction or dungeon methods are substituted in this object.

These are 3Shipsty source projections using generic Shipyard compiler helpers.
No game rule, available-check policy, feature, or resource lookup is bypassed.
No endian transformations are added: tested flags/upgrades live in native
SaveContext numeric fields; actual serialized scene data stays behind the
existing real scene resource factory boundary.

## Verification and limits

The tests compare all original signatures, retain all 132 definitions, and
check that 126 function bodies are unchanged apart from fallthrough annotations.
The remaining six are the inventoried constructor/syntax/container adaptations.
Both original and projected builds execute 26 actual Logic methods against the
real SaveContext declaration and five exact arrays extracted from upstream
`z_inventory.c`. They compare all five real map contents and exercise:

* 2,048 upgrade writes/readbacks and all 56 inventory-slot IDs;
* every LogicVal bit, 2,064 randomizer flags, and 224 event flags;
* quest/equipment/dungeon items, ammunition, and native value narrowing;
* all 256 dungeon-completion masks in both generated-logic and live-check modes.

No fake Context, Item, archive, or diagnostic providers are linked into tests.
Combat/access rules, resource-loaded door caching, ApplyItemEffect, full reset,
and real randomizer execution need application integration/runtime validation.
Full native compilation is verified, not Xenia gameplay or hardware behavior.

A pre-existing ownership concern remains visible without alteration:
`NewSaveContext()` uses `free` before allocating with `new SaveContext()`.
The complete SetSaveContext caller/allocator ownership needs a separate audit
before changing this upstream lifecycle; this translation does not conceal it.
