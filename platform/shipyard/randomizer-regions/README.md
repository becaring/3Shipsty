# Current reachability graph projection

This provider translates the complete pinned Shipwright 9.2.3 reachability graph
from `cb71e22a79bc5d1f688fa881795bbd93094895fc`. `sources.lock.json` locks the
normalized UTF-8 text of 38 upstream inputs: `location_access.h`,
`3drando/shops.hpp`, and all 36 production translation units. No upstream input
is edited. Generation rejects source drift before writing output.

## Build and integration

Run from the repository root with the existing canonical providers prepared:

```powershell
C:\Python313\python.exe tools/shipyard/prepare_randomizer_regions.py --build
C:\Python313\python.exe tools/shipyard/test_randomizer_regions.py
```

The complete production inputs are `location_access.cpp`, the 12 dungeon files,
the 22 overworld files (including Thieves' Hideout), and `location_access/root.cpp`.
`prepare_randomizer_regions.includes()` supplies the ordered include roots.
Its first root, `scratch/randomizer-regions-xdk/generated/soh`, owns the complete
canonical `soh/Enhancements/randomizer/location_access.h` projection. The other
providers continue to own Logic, Context, Entrance, Location, Dungeon, Trial,
Option and resource declarations. `shops.hpp` is copied in full with its relative
Context include changed to the canonical include spelling.

All 36 full production units compile to genuine PowerPC COFF (`0x1f2`) objects
with `/GR` enabled. `scratch/randomizer-regions-xdk/xdk/build.json` records exact
commands, statuses, and source/object hashes. The generation manifest records
source hashes, generated hashes, helper hashes, predicate/container inventories,
and each Region constructor's six default initializers. No build-manifest or
other provider edits are included in this batch.

## Mechanical adaptations

The XDK cannot convert a captureless lambda to a function pointer. Each of the
5,885 predicate expressions gets a real static Boolean function with its exact
original body; nested captureless lambdas are lowered recursively. `ConditionFn`
remains `bool (*)()`. The existing macro diagnostic strings are still produced
by C preprocessing the exact original condition tokens. Predicates are never
evaluated while constructing the table.

The 1,993 nonempty container initializers use const aggregate arrays and the
real container's iterator constructor. This retains element order, duplicates,
set ordering, and copying from const initializer-list elements. Empty lists,
including lists containing only comments, construct empty containers. The
Spirit map uses its original aggregate rows and `insert`, preserving first-entry
behavior. `SpiritLogicData` remains an aggregate with all seven original fields.

All four complete value/class definitions are retained: EventAccess,
LocationAccess, SpiritLogicData and Region. The same DMI inventory generates
the six explicit defaults in all three Region constructors. The default
constructor's previously uninitialized `scene` and `timePass` members remain
uninitialized. Other syntax changes are typed range loops, an explicit deduced
array return type, exact Boolean decimal strings, and the actual Entrance type
for a generic lambda argument. In particular, the upstream by-value
`RemoveExit` callback and its address comparison are preserved without an
unrequested behavior fix. Performance timer and logging calls use existing real
provider declarations.

## Verification and limits

The focused test confirms all 79 original definitions remain. Every one of the
35 table initializer bodies is reconstructed to the original token sequence,
including branch logic and event/location/exit order. It separately reconstructs
all 5,885 predicate bodies and the full Spirit map. Complete class tokens are
checked after removing only their inventoried DMIs.

Two host executables compare genuine original and projected constructors and
methods using complete class declarations. They run 1,464 service-independent
source predicates over 1,024 age/time/event states (1,499,136 evaluations), and
construct 429 real source containers, comparing ordered IDs and diagnostic
strings. Additional assertions cover all three Region constructors, scene area
and time defaults, age restoration in `AnyAgeTime`, list pointer stability,
reset behavior and Spirit aggregate value initialization. Both produce:

```text
regions contract 16857263278497682100; 1499136 predicate evaluations; sizes 152 80 48 32
```

These sizes are host comparison evidence, not Xbox ABI sizes. The canonical
Entrance constructor and observers and real Logic constructor/Get/Set methods
are used; no fake Context, game services, or replacement predicates are linked.
`verification.json` records both host commands/results and checks current native
source/object hashes and `/GR` for every production unit.

There are no remaining compile blockers inside this batch. Whole-game linking,
complete graph initialization against a live Context, seed reachability runs,
and console execution remain integration work. This batch does not claim those
runtime checks, or compilation of the full Entrance implementation. No service
boundary is stubbed to obtain the reported results.
