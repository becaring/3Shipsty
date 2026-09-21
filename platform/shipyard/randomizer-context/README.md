# Modern randomizer runtime batch

Reproduces complete pinned `SeedContext.cpp`, `item_location.cpp`,
`fishsanity.cpp`, `kaleido.cpp`, and `ItemTableManager.cpp` for XDK. All 171
original function definitions remain. Canonical Context, ItemLocation, Logic,
Settings, Hint, Item, Dungeon, Trial and Entrance declarations remain owned by
their established providers. Fishsanity and Kaleido use complete upstream
declarations with narrow syntax/default adaptations.

```
C:/Python313/python.exe -B tools/shipyard/prepare_randomizer_context.py --build
C:/Python313/python.exe -B tools/shipyard/test_randomizer_context.py
```

The main project consumes `scratch/randomizer-context-xdk/xdk/build.json`.
Generated sources, source locks, compiler commands and PPC object hashes are
recorded; the original application tree remains untouched.

## Adaptations and ownership

- A/B: Replace generic lambda parameter with its actual RandomizerCheck type;
  lower range loops, contains, emplacement, JSON item iteration and empty-list
  syntax using the existing compiler/runtime interfaces. Spoiler parsing retains
  its complete settings/items/entrances/hints/dungeons/trials sequence and failure
  flags. Paths still pass through the actual Sanitize routine.
- A: Relocate actual member defaults into the existing constructors. Preserve
  both pure virtual KaleidoEntry methods and all original fields. Preserve
  original intentionally uninitialized fields. Fish option structured bindings
  refer to the original returned value's three actual fields, with one evaluation.
- A/B: Preserve all 100 seed texture rows, 17 pond pairs, nine grotto mappings,
  25 vanilla-option pointers and their order. Seed textures have one definition
  in SeedContext rather than a C++17 inline variable. No byte swaps are added.
- A: Materialize the original Gfx aggregate before vector insertion; every
  original display-list macro and argument remains. Color and GetItemEntry
  aggregates use typed local construction. Fish location names explicitly
  materialize the same std::string that modern C++ creates implicitly.
- B: Set merge becomes range insertion. Its by-value source is local and unused
  afterwards, so destination key/value contents and ordering are unchanged.
- I: Include genuine used declarations directly instead of transitive umbrellas;
  retain the existing global `ctx` and CreateStaticHints declarations. Include
  actual hook/ShipInit support and preserve registration paths and callback order.
  A dedicated generated pool header contains actual used upstream algorithms;
  it does not replace the global pool_functions.hpp interface.

These are 3Shipsty application projections using generic Shipyard compiler,
JSON, resource-range and hook compatibility. No alternate game path or services
are provided.

## Evidence and limits

All five full sources compile as PPC objects. Original/projected host execution
compares 2,520 ItemLocation states, construction/reset/visibility/exclusion,
area merging, hint/price behavior, all 65,536 item IDs, duplicate insertion and
draw metadata, and the real fish helper table construction. Both original and
projected fish helper initialization retain the upstream behavior when invoked
twice; no opportunistic behavior fix is included. Pure virtual declarations and
the exact seed texture initializer are checked separately.

Host checks do not execute seed loading, actor hooks, graphics commands, complete
Context construction or actual gameplay. Native object compilation is not
application execution. These paths still require the genuine final application
and Xenia validation.
