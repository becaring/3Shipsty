# Modern randomizer Item

This provider projects all 31 definitions and all 16 fields of the pinned 9.2.3
`Rando::Item`. `item.cpp` is one complete native production translation unit;
no progressive-item cases, logic effects, major-item rules, hints, or methods
are removed. The class remains the actual application class used by value in
Plandomizer. It uses the canonical foundation `Text` and `LogicVal` types.

Run from the owned root:

```
C:/Python313/python.exe -B tools/shipyard/prepare_randomizer_item.py --build
C:/Python313/python.exe -B tools/shipyard/test_randomizer_item.py
```

Use `prepare_randomizer_item.includes()` in its returned order. In particular,
`scratch/randomizer-item-xdk/generated/soh` and its `soh/Enhancements/randomizer`
directory precede the randomizer foundation, original tree, and staged game
tree. The recipe also supplies modern option/UI and real OTRGlobals headers.
`scratch/randomizer-item-xdk/xdk/build.json` records exact compiler invocations,
source hashes, and verified PPC COFF object hashes.

Production objects are `item.obj` and `LogicConstructor.obj`. The latter is the
actual empty upstream `Logic::Logic()` body with all 15 original in-class
initializers moved into its initializer list. It accompanies the complete
actual Logic declaration; it must be omitted once the full generated logic.cpp
is built, to prevent duplicate definitions. The complete logic.cpp is emitted
with these defaults relocated but is **not a claimed compiled logic provider**.

## Narrow source adaptations

* A: Move three Item member defaults to all three original constructors.
  Preserve all previously uninitialized fields: notably the default constructor
  leaves `logicVal` and `category` indeterminate, exactly as upstream does.
* A: Construct both real 15-field GetItemEntry aggregates as local typed values
  before `make_shared`, preserving allocation ownership and every field value.
  Remove only the unsupported fallthrough attribute; control flow is unchanged.
* A/B: Lower empty Text default arguments and remove unused `<variant>` from
  Item. Forward declare HintText in Item's header, which returns it by reference.
* B: Narrow unused transitive includes to the complete real StaticData,
  Randomizer, Logic, and Location declarations. XDK's `std::array<Location,N>`
  eagerly requires complete Location even for its static declaration, so the
  entire actual Location and SpoilerCollectionCheck headers are projected.
  Every Location constructor, field, and method declaration is retained.
* A: Lower the two real Logic scoped enums with the shared scoped enum helper,
  Location's six deduced factory return types, and existing member defaults.
* I: Include the resource runtime template support outside the game header's
  C linkage region. This changes include order only.

The complete HintText class is extracted from `3drando/hints.hpp` into the named
`3drando/HintText.h` generated header. It retains all fields and declarations.
**Future full hints.hpp projection must include this canonical class and remove
its original duplicate definition.** No hint table or method is invented.
StaticHintInfo remains a forward declaration because no value is instantiated
here. All fields and declarations of StaticData are retained.

These are 3Shipsty source projections using generic Shipyard compiler/type
compatibility; there are no Xbox game-rule changes and no byte swapping.
GetItemEntry fields are runtime native metadata, assigned numerically on Xenon.

## Evidence and remaining integration

`verification.json` records matching host runs against the actual original and
projected Item classes, 25 actual methods, and real Logic constructors. Tests
cover all 65,536 signed item IDs (11 bottle IDs), 216 metadata combinations,
chest animation sign/narrowing, all 15 GetItemEntry fields, constructor defaults,
borrowed icon identity, copying, shared drawing callback mutation, independent
price/playthrough values, equality semantics, and all 15 Logic defaults.
The two upstream indeterminate Item members are checked through their byte
representations after placement construction, without reading their enum values.
Original Text is used in the original host run; canonical projected Text is used
in the projected run. All nonconstructor Item method bodies are compared exactly
apart from the fallthrough annotation. Complete native item.cpp compilation
retains the six game-service-dependent methods that are not host executed.

This is compile and value-contract evidence, not randomizer execution evidence.
Real runtime integration still needs the actual Context singleton/options/logic
providers, Logic item effects/upgrades/inventory/save context, Randomizer setting
lookup, StaticData item/hint tables, and OTRGlobals instance. No fake providers
or substituted data resolve those dependencies. Progressive-item runtime and
major-item setting behavior must be exercised with those real services when the
application is linked and running. No Xenia or hardware claim is made here.
