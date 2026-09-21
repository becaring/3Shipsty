# Complete modern Hint provider

`prepare_randomizer_hints.py` consumes the source-locked full Hint projection from
`randomizer-xdk`, verifying its manifest and pinned source identities. It retains
every method and uses the existing canonical Hint declaration/defaults. HintText
remains owned by `randomizer-item`; it is not redeclared here.

Production sources under `scratch/randomizer-hints-xdk/generated`:

- `soh/soh/Enhancements/randomizer/hint.cpp`: complete 9.2.3 implementation.
- `StaticHintInfo.cpp`: the exact constructor extracted from pinned `3drando/hints.cpp`.
- `soh/soh/Enhancements/randomizer/3drando/StaticHintInfo.h`: complete real static-hint record needed by Hint's map accesses.

## Narrow changes

| Class | Boundary | Contract |
|---|---|---|
| A | Range loops, empty vector declarations/assignments | Existing deterministic range lowering; matching empty construction/clear, unchanged iteration order. |
| B | Static-hint map `contains` | Equivalent guarded `find`; existing accesses do not create missing records. |
| A/B | Empty ordered JSON declaration | Default JSON remains null until the first insertion; do not initialize it to an empty object. |
| B | Singular hint-key enum JSON conversion | Explicit `int` conversion matches the actual enum's underlying type and signed JSON classification. The original plural branch still creates uint32 arrays. |
| A | Single-string braced CustomMessage construction | Invoke the same constructor directly. |
| I | Transitive `3drando/hints.hpp` dependency | Include canonical HintText, complete StaticHintInfo, actual Random declarations and complete TrialInfo. |
| A/B | StaticHintInfo variant/defaulted constructor | Reuse the existing Prism `xbox_compat::variant<bool,uint8_t>`, including correct Boolean versus byte selection, and preserve empty/value construction with the existing ValueInit tag. |

StaticHintInfo keeps its original fields, order and parameterized constructor.
Its default construction leaves the original scalar members unspecified; its
`ValueInit` constructor zeroes those scalars as upstream empty/value initialization
does. `value_expressions()` projects explicit empty/value construction for future
consumers. When porting future code that inserts a missing map entry with
`operator[]`, preserve mapped-value initialization explicitly using a ValueInit
record. Current Hint accesses are already guarded against missing records.

When the full upstream `3drando/hints.hpp` is projected later, include these
canonical HintText/StaticHintInfo declarations instead of defining another copy.
There is no alternate Hint class, context, randomizer, text engine or JSON service.
All real seed/context/randomization calls remain unresolved production references
until the corresponding real provider is linked.

## Integration and verification

Prepend the provider's `generated/soh` and generated randomizer directory alongside
the existing randomizer-item/randomizer include roots. Also include the existing
`scratch/prism-xdk/generated` root for the canonical variant support. The build
recipe derives the complete application compiler flags and existing item includes;
it does not run shared generators. `xdk/declarations.cpp` is a compile/ABI probe,
not a production source. Native ABI: Hint 192 bytes, StaticHintInfo 88 bytes, the
two-alternative variant 8 bytes.

```
C:\Python313\python.exe -B tools/shipyard/prepare_randomizer_hints.py --build
C:\Python313\python.exe -B tools/shipyard/test_randomizer_hints.py
```

Four tests pass. Both production TUs and the native variant/ABI probe compile.
Original/projected host contracts execute two actual Hint constructors plus all
17 value/reset methods, actual CustomMessage methods for the extracted message
branch/formatting tail, and the actual selection-field JSON parser/emitter blocks.
They compare null initialization, singular/plural precedence, integer signedness,
array and object insertion order, malformed-value rejection, message copying,
format bytes, reset state and StaticHintInfo variant/default behavior. The JSON
comparison uses upstream nlohmann on the original side and the actual legacy
ordered JSON backend on the projected side.

No mock seed/context services are supplied. Full JSON constructor/toJSON service
resolution, names chosen from real seed data, complete runtime hint generation,
Xenia and hardware execution are not claimed. Evidence is in `manifest.json`,
`verification.json`, the two host directories, and `xdk/build.json`/logs/objects.
