# Modern randomizer data foundation

This provider translates the complete pinned 9.2.3 `location.cpp` and
`static_data.cpp`. It consumes the existing complete canonical Location,
SpoilerCollectionCheck and StaticData declarations from randomizer-item, verifying
their source and generated hashes. It does not modify or duplicate shared headers.
The canonical StaticHintInfo and HintText providers remain authoritative.

## Adaptations

| Class | Boundary | Preserved behavior |
|---|---|---|
| A | 34 Location factory braced returns | Invoke the same Location constructor with exactly the same argument expressions and order. All inline constructors and SpoilerCollectionCheck factories remain in the shared canonical header. |
| A/B | 18 initialized map/vector declarations | Deterministic helper functions retain all 446 source entries and insert in source order. Actual map/vector types and first-key insertion behavior remain unchanged. |
| A/B | StaticHintInfo nested vector arguments | Typed constant arrays construct the actual vectors in their original order, then invoke the canonical record constructor, retaining Boolean variant alternatives. |
| A | Two structured binding loops and range loops | Traverse the same unordered-map and vector instances with references/copies matching upstream. |
| B | Translation-map `contains` | Equivalent typed `find`, preserving the first mapping encountered during input iteration. No new sort/order is imposed by production code. |
| B | Dynamic logging format arguments | Explicit spdlog string view preserves the existing dynamic-format call and argument lifetime. |

Empty containers remain empty default constructions. The real
`std::array<HintText, RHT_MAX> hintTextTable = {}` aggregate is retained verbatim.
Helpers initialize static members at their original declaration points. No
alternate tables, generated substitutes for game data, fake services, endian
fixups, or runtime ownership changes are introduced. The table constants are
compiled native metadata, not serialized N64 or archive bytes.

This batch covers all definitions in these two files. Other upstream definitions,
including `InitLocationTable` and the large item/location content tables residing
in other translation units, remain owned by their actual future providers.

## Build and tests

```
C:\Python313\python.exe -B tools/shipyard/prepare_randomizer_data.py --build
C:\Python313\python.exe -B tools/shipyard/test_randomizer_data.py
```

Integrate both generated production sources under
`scratch/randomizer-data-xdk/generated/soh/soh/Enhancements/randomizer`, with its
`generated/soh` root and existing canonical include roots. Native recipes consume
the verified randomizer-hints recipe and current providers; no shared generators
are run. Both complete production TUs compile for Xenon.

Four tests pass. The original/projected host audit executes all 34 factory
overloads, compares every emitted factory field and all 446 container entries,
checks all six inline collection-check factories, Location defaults and area name
generation, actual HintText-array default initialization, and both full translation
map implementations including duplicate strings and untranslated placeholders.
Sorted map traversal is used only for stable test output comparison, never in
production. Tests use actual canonical Option constructors on both sides, real
CustomMessage/HintText methods and real area-prefix data/functions. No game or
service stubs are supplied.

Evidence is in `manifest.json`, `verification.json`, both host compile/run records,
and `xdk/build.json`/logs/objects under `scratch/randomizer-data-xdk`. Shared headers
needed no changes. Native runtime, complete seed generation, Xenia and hardware
execution remain unvalidated.
