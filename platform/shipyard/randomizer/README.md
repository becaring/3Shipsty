# Current randomizer header and value foundation

This provider generates the complete current `Rando::Context` declaration from
Shipwright 9.2.3, commit `cb71e22a79bc5d1f688fa881795bbd93094895fc`.
It preserves every field, its order and type, and every method declaration in
Context, ItemLocation, ItemOverride, Hint, TrialInfo, Trials, Text, CustomMessage,
CustomMessageManager and MessageNotFoundException. No partial classes, fake
services, provider implementations, alternate game state, or Pimpl are supplied.

`sources.lock.json` pins 27 upstream inputs and four additional game-header
dependencies using UTF-8 with BOM removal and CRLF-to-LF normalization. Every
input was compared with the named release commit. The generator checks hashes
before emitting files; its manifest records source/output/helper hashes and the
constructor/default inventory. Upstream and reference trees remain unchanged.

## Generation and integration

Run from the repository root with the existing current runtime projections ready:

```powershell
C:\Python313\python.exe tools/shipyard/prepare_randomizer.py --build
C:\Python313\python.exe tools/shipyard/test_randomizer.py
```

`prepare_randomizer.includes()` places `scratch/randomizer-xdk/generated/soh`
first, then the owned support root and `prepare_game_interactor.includes()`.
The latter supplies the real current z64, game, resource, binary, logging and
ordered JSON headers. Native builds use the same game/math definitions and
`/EHsc /GR /MT`; RTTI remains enabled. All generated output and test artifacts
are under `scratch/randomizer-xdk`.

SeedContext uses forward declarations for Fishsanity and the trial services.
ItemLocation uses a forward declaration for Item and the canonical OptionValue
header. Hint uses a forward declaration for HintText. These types are only named
through declarations/references/pointers at those boundaries. Complete value
members remain complete classes. Necessary full includes are retained or added
to the corresponding generated implementation files.

OptionValue is extracted from the complete current `option.h` into one generated
`OptionValue.h`. The projected full `option.h` includes that same definition.
Its four existing out-of-line methods move from projected `option.cpp` into
generated `OptionValue.cpp`; link that unit exactly once. There is no second
definition or independent OptionValue facade. The full Option, LocationOption,
TrickSetting and OptionGroup declarations and fields also remain present.

The DMI inventory contains 73 current member defaults. Fifty-eight defaults on
the native header path become constructor initializers; constructor edits are
derived from that same inventory, including all out-of-line constructors in
the retained full implementation sources. Explicit upstream initializers take
precedence. Thirty-three constructor definitions are audited. Empty vector/set
initializer-list assignments in ItemLocation/Hint reset methods become `clear`,
preserving their empty-list assignment behavior. CustomMessage's three language
slots retain the actual `TODO_TRANSLATE` macro, slot order, and default textbox
type/position. Text preserves the upstream four-argument constructor's behavior,
including its unused Spanish argument.

Fifteen defaults in the gated full UI Option/OptionGroup classes stay as their
original DMIs. Their header constructors remain `= default`: changing Option
or TrickSetting into user-provided default constructors would incorrectly change
value-initialization of other scalar members. These full UI classes are not
claimed XDK-ready.

XDK cannot parse explicit conversion operators. OptionValue therefore uses a
storage-free member-pointer safe-bool conversion on that compiler; modern
compilers retain the exact explicit `operator bool`. The value predicate is the
original `mVal != 0`, and implicit integer conversion is rejected. The legacy
language also permits implicit initialization of a bool, which is a known
source-language limitation of this spelling; the tests compare all 256 values
through both spellings. No implicit integer or arithmetic conversion is added.

## Verified scope

The test command passes eleven checks:

- Full member order/type and method declaration audits, including all Context
  members and the retained UI Option classes.
- Actual generated constructor AST initializer expressions checked against
  the original defaults, source-function preservation, canonical OptionValue
  ownership, and output hashes.
- Three original/projected host runs, including the legacy boolean spelling,
  exercise all 256 OptionValue values; Text language/fallback/form/replacement
  behavior; ItemOverride; ItemLocation defaults, visibility, price and reset
  behavior; TrialInfo defaults/toggles; Hint defaults/message constructor/reset;
  and every CustomMessage constructor.
- Host sizes and every data-member offset match for nine complete classes,
  including Context. These tests use exact complete class definitions with
  private test access, the real game enums and real nlohmann JSON declarations.
  Context's constructor is not replaced or executed by the host harness.
- XDK builds the genuine complete ItemOverride TU, the canonical four-method
  OptionValue TU, and a probe that includes the real generated SeedContext and
  trial headers. The probe also instantiates the inline value defaults.
- A separate bounded test object compiles 82 real extracted methods: eight
  ItemOverride, 40 ItemLocation, nine TrialInfo, 16 Hint, five CustomMessage
  constructors and four OptionValue methods. This is a method test object,
  not evidence that the corresponding full feature TUs compile.
- A negative XDK compile verifies that OptionValue cannot implicitly become int.

All successful native objects are verified as PowerPC big-endian COFF (`0x1f2`)
and hashed. The real ABI probe's exported target layout constants are read back
from its COFF symbol into `xdk/layout.json`: Context 196044 bytes, Hint 192,
ItemLocation 72, CustomMessage 60, Text 112, TrialInfo 12 and Trials 72.
These are XDK layout observations; host layout equality is a separate check.

`xdk/build.json` records the production/probe compile commands and hashes.
`xdk/value_methods-receipt.json` identifies the exact bounded method subset and
object hash; `value-report.json` records the three host differential runs.
No Xbox execution or linked modern game is claimed.

## Explicit remaining gates

Full SeedContext.cpp, item_location.cpp, hint.cpp, trial.cpp, option.cpp and
CustomMessageManager.cpp are retained with all methods, but are not compiled
production units in this provider. Their broader dependencies still require
current StaticData/Item/Location, Logic, settings, hint generation, entrance and
dungeon services, Fishsanity, Kaleido, OTRGlobals and full UI/widget projection,
plus remaining implementation syntax/JSON call-site work. Full `option.h` keeps
its genuine UI types and modern defaults as described above; it is also outside
the native-ready header set. No dependencies are replaced by fake APIs.

The real Context constructor keeps every service allocation and its original
VanillaLogicDefaults assignments, with all 15 Context DMIs added explicitly.
It is source-audited but not linked or run. Final provider integration, complete
randomizer/game linkage and target runtime behavior remain root-level work.
