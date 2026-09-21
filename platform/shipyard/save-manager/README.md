# Complete modern SaveManager

The full pinned SaveManager.cpp now compiles with XDK: all 42 members and all
12 C bridges, including genuine LoadRandomizer, SaveRandomizer, InitMeta and
Save_LoadFile. Its modern schema, randomizer hints/settings/items/trials,
metadata, hooks and worker ownership remain intact. This provider supersedes
SaveSerialization.cpp and LegacyConversion.cpp. Continue linking the canonical
LegacyDecode.cpp, which owns the audited raw-byte decoder and CopyV0Save.

```
C:/Python313/python.exe -B tools/shipyard/prepare_save_manager.py --build
C:/Python313/python.exe -B tools/shipyard/test_save_manager.py
```

## Adaptations and ownership

- Reuse the existing source-locked save-storage projection, complete canonical
  SaveManager header, native storage/atomic publication and legacy conversion.
  The full source substitutes the audited converter for the old raw-structure
  parser region. It neither duplicates nor reimplements modern serialization.
- A/B: oldVerHintOrder uses its exact original rows in a typed array/range
  constructor. Item overrides use map insert/make_pair with the original key
  and ItemOverride constructor, preserving first-insert behavior.
- A/B/I: supply the actual canonical Item/Logic/Settings/StaticData/HintText
  headers and complete original Entrance/EntranceShuffler declarations. Their
  scoped enum and member defaults use existing compatibility helpers. Entrance's
  actual constructor-default projection is emitted but not claimed compiled.
  Hint and Trial remain owned by the existing randomizer foundation. No second
  class definitions, replacement shuffler, fake metadata or gameplay provider.
- B: two JSON enum traits declare the existing MSVC int representation for
  RandomizerGet and RandomizerHintTextKey. Actual modern-host underlying-type
  assertions and all 1,818 valid enum values pass JSON round trips. Native full
  compilation consumes these traits. No arbitrary fallback trait is introduced.
- H: XDK crashes in ehexcept.c:971 when LoadRandomizer's nested callbacks use
  nontrivial default-argument temporaries. The reported source position misleadingly
  names the following SaveRandomizer function. Removing SaveRandomizer did not
  fix the failure; isolated load-items and load-hints callbacks reproduce it,
  while the other load statements compile. Explicit /Od also fails. Naming the
  same temporary locally fixes it: three std::string defaults and one JSON
  default each occupy a scope around the same LoadData call. Values, const-reference
  binding and destruction after the call remain. No callback is removed, and
  optimization/exception handling remain unchanged.

The generator records all input and output hashes, relocated defaults and the
canonical conversion-method hash. These are 3Shipsty source adaptations using
Shipyard platform services. JSON values are runtime native numbers/strings;
raw legacy byte ordering stays exclusively at the audited decoder boundary.

## Evidence and remaining work

The test compares all 42 members, all 12 bridges, every serialization key, the
old hint order, and unchanged previously ported method bodies. LoadRandomizer
changes are restricted to the reviewed insertion/default-expression lowering.
Full SaveManager.cpp produces native PPC COFF with a recorded source/object hash.

Original/projected real SaveManager template and array/structure methods agree
for nested missing strings, missing/null/object/scalar/array hints, preserved
destination values on type errors, and all 1,818 enum values. The fixture uses
the exact class plus a test-only constructor to avoid application registration;
no fake randomizer/context/storage services are linked. Existing save-storage
and legacy-save suites provide the base schema, I/O and raw-decoder evidence.

Receipts: scratch/save-manager-xdk/{manifest.json,verification.json,xdk/build.json}.
Actual randomizer save/load, metadata display, storage failure UI and native
application execution remain unvalidated. Compilation does not establish save
correctness on Xbox or Xenia.
