# Current ShipUtils and randomizer RNG

This provider projects the complete current `soh/soh/ShipUtils.h/.cpp` and
`soh/soh/Enhancements/randomizer/3drando/random.hpp/.cpp`, pinned to Shipwright
9.2.3 commit `cb71e22a79bc5d1f688fa881795bbd93094895fc`. All four normalized
source hashes were checked against that exact commit and are verified before
generation. No upstream, reference, existing provider, or shared build file is
edited. Both complete production TUs compile with XDK; no functions are omitted
from their generated sources or native objects.

Run with the existing current runtime projections present:

```powershell
C:\Python313\python.exe tools/shipyard/prepare_ship_utils.py --build
C:\Python313\python.exe tools/shipyard/test_ship_utils.py
```

`prepare_ship_utils.includes()` puts `scratch/ship-utils-xdk/generated/soh` and
the owned support roots before `prepare_game_interactor.includes()`. This uses
the actual current z64, libultra, CVar and binary headers. C++ compilation retains
`/EHsc /GR /MT`, game definitions and the existing math boundary. Link both full
generated production TUs and `platform/shipyard/ship-utils/native_entropy.cpp`.

## Compatibility changes

Broad LUS includes become the real libultra and CVar bridge interfaces plus the
standard container headers actually used. Forward game pointers use their
`struct Actor`/`struct PlayState` tag spellings, preserving their types and C ABI
while allowing the header to be included by C without earlier game typedefs.

The generic RandomElement return declarations derive the indexed element type
using an unevaluated uint32_t subscript, preserving reference/cv qualifiers for
vectors, std::arrays, built-in arrays and other indexed containers. No container
is replaced. The size helper calls the actual `.size()` with its original result
type or uses a built-in array's extent. Tests include mutable/const containers,
raw const arrays and arrays of pointers. The actual reached vector/array/string,
Text and CustomMessage element contracts all use the same reference behavior.

The 32-bit rotate masks both shifts, including the zero-rotation case, and is
tested against real `std::rotr`. RandomDouble's integral argument explicitly
converts to double before the genuine `ldexp` call, matching the modern integral
overload without XDK's ambiguous float/double/long-double overload resolution.
`constexpr f32` becomes `const f32`; the exact constant expression is retained.

The seeded generator algorithm is unchanged: the original 64-bit multiplier,
increment, state advancement, xorshift/rotation, range cutoff and `<=` acceptance
test, equal-bound behavior, and wrapper state are retained. No distribution,
rejection threshold, shuffle order, or initialization behavior is repaired or
reinterpreted. In particular, upstream `RandInit(seed, nullptr)` does not set
`default_init`; its first default-state use still initializes from device entropy.
Explicit state pointers and the randomizer's `rando_state` remain deterministic.

## Genuine native entropy

The Xbox device seed is a real 32-bit `XNetRandom` result. Failure throws
`std::runtime_error` before `default_init` changes, matching random_device's
failure propagation rather than substituting a weak seed. There is no time/rand
fallback for Xbox. Host validation uses the real `std::random_device`.

Application startup owns XNet initialization, as with the existing libzip
XNetRandom boundary. This provider does not secretly initialize or tear down
network services. Actual XNet startup and entropy execution on the Xbox remain
an integration/runtime check; the successful native object has an unresolved
reference to the real `XNetRandom` symbol for the final system-library link.

## Evidence and scope

Five tests pass. `xdk/build.json` records commands and source/object hashes for
the complete ShipUtils and random.cpp objects, native entropy, a C++ container/
type probe and a genuine C ABI probe. All five objects are PowerPC big-endian
COFF (`0x1f2`). The C probe goes through the existing `prepare_game.lower_c`
semantic boolean projection before `/TC` compilation; it does not redefine bool
as arbitrary byte storage. Its preprocessing, lowering statistics and generated
hash are retained in the build receipt.

The native symbol audit finds all seven C utility definitions, all four RNG
methods and the wrapper definitions. Native C references use the same unmangled
utility symbols. CVarGetInteger, OTRGetAspectRatio and XNetRandom remain references
to their real providers.

Both complete TUs also compile as original and projected MSVC host objects.
The original host inputs only narrow the umbrella includes and make required
standard includes explicit; every original method body is unchanged. The host
runtime harness extracts exact C-string/vertex methods and the complete RNG
state/function source tail, then links the full original/projected random.cpp.
Actor-culling and font methods require real game services/data; no stand-ins are
linked into this bounded runtime test. Original/projected full host object
receipts and exact harness hashes are kept alongside the test logs.

The two host runs match exactly and check:

- Eight seeds, 32768 next32 outputs and states, 32768 range calls including equal
  bounds and high rejection rates, and 32768 RandomDouble values against an
  independent expression of the original algorithm.
- All global RNG wrappers, independence from an explicit state, lazy default
  device initialization followed by deterministic default-state reseeding,
  mutable and const RandomElement references, raw arrays, erase/no-erase behavior,
  set selection and its singleton no-advance contract.
- Vector shuffles of lengths 0 through 64, array shuffles, and empty/singleton
  containers without state advancement.
- 7744 quad vertex groups, both horizontal flip modes, signed positions, texture
  coordinates, and preservation of untouched vertex fields; null/empty/nonempty
  C-string behavior.
- 4194304 projected rotation cases against standard `std::rotr`.

The final differential digest and runtime scope are in `verification.json`.
No linked game or Xbox execution is claimed. Original declaration-only
LoadGuiTextures and the commented-out RestoreProjectedPos implementation remain
as upstream supplied them; this provider does not invent definitions.
