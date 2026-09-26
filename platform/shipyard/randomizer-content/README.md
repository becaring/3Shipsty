# Modern randomizer content tables

This provider compiles all ten complete pinned 9.2.3 translation units:
`item_list.cpp`, `location_list.cpp`, `item_category_adj.cpp`,
`randomizerEnumStrings.cpp`, `randomizer_check_objects.cpp`, `tricks.cpp`,
`3drando/hint_list.cpp`, and all three `3drando/hint_list/hint_list_*.cpp`
files. Upstream files and shared canonical Item, Location, StaticData, HintText,
Tricks and CustomMessage classes are unchanged.

## Generate and verify

From the repository root:

```powershell
python -B tools/shipyard/prepare_randomizer_content.py --build
python -B tools/shipyard/test_randomizer_content.py
```

The generator consumes the existing randomizer-data XDK recipe and already
generated application-GUI, enhancements, randomizer context/logic/item/options,
custom-message and other transitive providers. It does not regenerate or modify
them. Outputs, commands, logs, input/output hashes and host comparisons live in
`scratch/randomizer-content-xdk`. `sources.lock.json` rejects changed pinned input.

## Compatibility boundaries

These are generic Shipyard compiler/library adaptations to modern SoH data:

- A/B: Explicit Text construction, typed vector builders and real STL
  insert/push_back operations replace unsupported initializer-list syntax. Every
  original row, argument, default, insertion order and table type is preserved.
- A/B: XDK lambda return inference requires explicit enum-map return types;
  pair insertion replaces unsupported two-argument emplace.
- B: string-view-lite and the existing optional backport preserve the enum map
  API contract. The string-view hash specialization matches string-view-lite's
  own string-based hash, guarded to avoid duplicate specializations on modern
  compilers. The existing scoped Tricks::Tag wrapper gets an underlying-int hash.
- A: Existing canonical range lowering and scoped-enum switch lowering are used.
- A/H: Each UTF-8 source literal is escaped as exact three-digit octal bytes.
  String suffixes retain explicit byte lengths. The existing CustomMessage wrapper
  supplies the exact embedded-NUL `HS_HORSE_ARCHERY` macro and message controls.
- I: Include spellings and order select existing complete canonical declarations.
  The small custom_messages header projection only roots its Text include.
- I: The full 86-enum, bidirectional map TU exceeds ordinary COFF's section limit.
  Its recipe uses `/bigobj`; other TUs use normal COFF. XDK `lib.exe` also accepts
  the resulting object. Consumers must recognize the bigobj machine field at
  offset 6, after the `00 00 FF FF` signature, rather than offset 0.

The native recipe adds this provider's `generated/soh` root, canonical
application-GUI/enhancements/context/logic roots, string-view-lite's include root,
and `scratch/custom-message-xdk/generated/include` ahead of raw source headers.
It defines `nssv_CONFIG_SELECT_STRING_VIEW=1`. The common platform include root
provides `randomizer-content/*.h`.

These tables are native runtime structures with host-generated constant text,
not ROM/archive/GPU blobs. No byte swap is introduced; strings retain their
upstream byte sequences independently of the XDK execution code page.

## Evidence and limits

The tests compile all ten complete PPC production objects and compare actual
original/projected host values, not replacement tables or game-service stubs:

- All 2,520 Location slots, actual initialization, actor multimap, name lookup,
  twelve location filters, dungeon rewards and memoized area/scene lookup.
- All 1,512 HintText slots, complete clear/ambiguous/obscure message collections,
  colors, capitalization flags, box types/positions and empty defaults. The four
  full hint initialization functions execute with real CustomMessage code.
- All 302 actual Item assignments, GetItemEntry fields, icons, articles,
  multilingual names, defaults and the original name-index population loop.
  Item category adjustment runs against a real SaveContext fixture and the actual
  upstream inventory-slot table. Trick names, text colors and tag filtering run.
- All 86 enum types in both directions, valid round trips and invalid lookups.
- Every one of 9,219 execution literals is decoded by the host compiler on both
  sides and compared byte-for-byte, including embedded NUL and UTF-8 text.
- All original function definitions remain in production; repeated generation
  must produce an identical manifest.

The bounded Item host test omits the otherwise unused Context/GetLogic query and
does not bind/call rendering callbacks; every original callback assignment is
separately required to remain identical. The bounded location test excludes the
Context/Dungeons query, visibility updates and UI rendering; these complete
methods remain compiled in production. This is no claim of seed generation,
application initialization, Xenia execution or hardware validation.

The full suite must run by itself: concurrent one-off host checks would write the
same owned contract files while the compiler reads them.
