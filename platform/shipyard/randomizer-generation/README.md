# Complete current seed-generation units

This provider projects all ten remaining production units from pinned Shipwright
9.2.3 commit `cb71e22a79bc5d1f688fa881795bbd93094895fc`:
`custom_messages`, `fill`, `hints`, `item_pool`, `menu`, `playthrough`,
`rando_main`, `shops`, `spoiler_log`, and `starting_inventory`.
Every unit is compiled in full. All 157 original function definitions remain.
The generation menu, retry paths, settings hashing, RNG calls, hint and item
placement, spoiler writing, and the real Gui console-variable save call remain.

## Integration

```powershell
C:\Python313\python.exe tools/shipyard/prepare_randomizer_generation.py --build
C:\Python313\python.exe tools/shipyard/test_randomizer_generation.py
```

Use `prepare_randomizer_generation.UNITS` for the ten production source paths
relative to `scratch/randomizer-generation-xdk/generated`, and
`prepare_randomizer_generation.includes()` for include precedence.
The extra `xdk/declarations.cpp` is a compile/ABI probe, not a production unit.

**Exclude the old generated constructor fragment
`scratch/randomizer-hints-xdk/generated/StaticHintInfo.cpp` from integration.**
The complete `hints.cpp` now defines the real StaticHintInfo constructor and all
HintText methods. Keeping the old fragment would duplicate the constructor.
Continue using the canonical `StaticHintInfo.h` from the randomizer-hints
provider; this provider includes that root explicitly.

`sources.lock.json` contains normalized UTF-8 hashes for all ten sources and
eight generated headers. Generation rejects upstream drift before writing
output. `manifest.json` records generated hashes, helper hashes, constructor
default inventory, ordered list/literal inventories, and paths/hashes for the
canonical class/header providers. HintText and StaticHintInfo are imported from
their complete canonical projections; their owning manifests must agree with
this provider's upstream `hints.hpp` hash. No second class definition is emitted.

## Translation boundaries

The changes are compiler/library adaptations: canonical includes, explicit
lambda return types and generic-parameter types, complete constructor default
lowering, typed range loops, pair bindings, container lookup/erase/merge,
explicit vector deduction, and ordered container initialization. Const aggregate
arrays preserve list element order and copy semantics. Single-element vectors
use the count/value constructor, which also avoids an XDK nested-lambda frontend
bug. Static hint distribution records retain the exact field order, weights,
fixed counts, copy counts, filters and dungeon limits.

The full GetAccessibleLocationsStruct retains every original member. Its one
DMI, `calculatingAvailableChecks = false`, is added to the real constructor;
other flags that upstream leaves uninitialized remain uninitialized.

The real ordered JSON backend receives the original spoiler keys in original
order. Strong enum values and FileType are explicitly converted to their
underlying integer value. Existing filesystem APIs perform the directory
operations; native streams receive the existing path string's `c_str()`.
All spoiler output and CVar updates remain in the production function.

Integer formatting uses a classic-locale decimal formatter for the reached
int/uint32_t/uint8_t values. This matters for hash icons: streaming a uint8_t
directly would emit a character. String literals use exact UTF-8 byte escapes;
message suffix lowering retains embedded NULs and explicit string length.
The original menu's `srand`, `rand`, and blank-seed behavior are unchanged.
Seeded randomizer generation uses the existing genuine ShipUtils RNG provider.

The unused IsAnyOf variadic convenience template remains intact for modern
hosts. XDK overloads support zero through sixteen comparison operands with the
original named-lvalue comparisons and short-circuit order. No pinned generation
source calls this helper. More than sixteen comparison operands remain an
explicit generic-header limitation on XDK.

## Verification

All ten complete production TUs and the ABI/template probe compile to native
PowerPC COFF objects (`0x1f2`) with `/GR`. `xdk/build.json` records commands,
statuses and source/object hashes. Native ABI probe sizes are:

| Complete type | Xbox bytes |
|---|---:|
| GetAccessibleLocationsStruct | 116 |
| HintDistributionSetting | 72 |
| HintSetting | 20 |
| StaticHintInfo | 88 |

The test verifies all 157 original definitions, original RNG call order within
every function, exact probability tables, and all four hint distribution rows.
It verifies that the complete native hints object emits both real constructors.
Two bounded host executables use actual original/projected functions and full
class declarations, without game-service substitutes. They cover:

- 39,936 seeded hint distributions, including zero weights, zero copies, fixed
  hints, exhausted capacity and junk fallback; downstream RNG state is compared.
- 16,384 seeded cheap-shop prices and all 65 vanilla-shop priority prefixes.
- Actual item-pool replacement and starting-inventory insertion methods.
- All 24 message functions, all 65,536 GO_TO arguments, byte-valued arguments,
  embedded NULs and exact numeric decimal formatting.
- Search-state defaults, complete StaticHintInfo constructor fields and variant
  alternatives, plus actual helper erase/merge behavior.
- Both real entrance JSON initializer blocks with signed boundary indices and
  original key order, using the genuine Entrance constructor and accessors.
  The baseline block reads the canonical enum wrapper's numeric value; no
  replacement Entrance/Context service is introduced.

The host output matches exactly:

```text
generation contract 10394708580678808716; 39936 hint distributions; 16384 seeded shop prices
```

`verification.json` holds receipts and validates current native source/object
hashes, `/GR`, constructor symbols and ABI constants. Tests use the real seeded
RNG implementation; platform entropy is linked through its existing genuine
provider and is not exercised by these explicitly seeded cases.

There are no remaining production-TU compile blockers in this batch. Whole-game
linking, generating complete seeds against a live Context, saving spoiler files
through the console filesystem, and console execution remain integration work.
These checks are not claimed by the bounded host contracts.
