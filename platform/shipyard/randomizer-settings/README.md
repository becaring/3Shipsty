# Complete modern randomizer Settings

Both entire pinned 9.2.3 translation units compile with XDK:
`settings.cpp` (24 definitions, including `Context::FinalizeSettings`) and
`option_descriptions.cpp` (the genuine `Settings::CreateOptionDescriptions`).
They retain all 125 U8 options, 111 Boolean options, 193 trick definitions,
44 callback registrations, option groups, and 323 CVar expressions.

```
C:/Python313/python.exe -B tools/shipyard/prepare_randomizer_settings.py --build
C:/Python313/python.exe -B tools/shipyard/test_randomizer_settings.py
```

Use `prepare_randomizer_settings.includes()` before existing include paths.
Link `scratch/randomizer-settings-xdk/xdk/settings.obj` and
`option_descriptions.obj`. **Remove the randomizer-options provider's
SettingsConstructor.obj**, since this full settings object defines the exact
same constructor. The complete canonical Settings/Option/OptionGroup/TrickSetting
declarations remain owned by randomizer-options and are not copied or modified.
Dungeon declarations come from randomizer-logic; trial/context declarations use
the established canonical providers. No duplicate application class is supplied.

`xdk/build.json` contains exact build commands, source and object hashes, and
successful PPC COFF verification. `manifest.json` records source locks and all
383 reviewed initializer projections. The whole source remains inspectable.

## Compatibility changes

* A: Preserve the actual Settings constructor and all member defaults. The
  established canonical helper initializes the already allocated Option and
  TrickSetting arrays in place, avoiding huge returned arrays on the Xenon
  stack. The generated constructor is checked against the canonical fragment.
* A/B: Lower literal vectors, explicit initializer lists, and trick-tag sets to
  typed ordered builders in `lists.h`. Vectors reserve the exact literal count;
  both builders own elements and transfer the real standard container. They
  preserve ordering, duplicate handling, type identity, and element ownership.
  A one-element `{NumOpts(...)}` expression invokes the original vector-copy
  semantics and becomes that same vector expression, not a nested vector.
* A/B: Lower empty default arguments, range loops, contains checks, and one
  C++17 if initializer; use the existing exact integer-to-string helper.
* B: Explicitly choose spdlog's string-view message overload for the single
  repeated-trick diagnostic. The complete message remains a message string;
  no game or logging branch is removed.
* I: Include genuine canonical context, static data, RNG, settings, and option
  providers instead of depending on unused transitive header inclusion.

These are 3Shipsty source projections using generic Shipyard syntax helpers.
The real CreateOptions body, callbacks, finalized seed settings, JSON parsing,
context ownership, groups, descriptions, and singleton remain intact. No
renderer, CVar store, seed generator, or settings UI is replaced. No endian
conversion is added; numeric option indices and strings remain native values.

## Verification scope

The tests compile and execute the actual original and projected Settings
constructors and numeric/flattening functions. They evaluate every one of the
383 original/projected initializer values with real Option, OptionGroup,
OptionValue, and Trick tag types; compare ordered string bytes, pointer indices,
set contents, and empty/copy cases; and verify every array element's default
state. They also verify singleton-sized arrays remain initialized in place,
all function signatures/registration keys/CVar expressions survive, macro
callback definitions remain identical, and every description literal's bytes
match the original. Fresh native compile evidence covers both complete units.

The real CreateOptions method, callbacks, FinalizeSettings, and JSON parsing
are compiled but not executed by these isolated host value tests. Their real
CVar, StaticData, Context, dungeon/trial, and RNG providers still require final
application linkage and runtime validation. No fake services are used to make
those paths appear operational; there is no Xenia or hardware claim here.
