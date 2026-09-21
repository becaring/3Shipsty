# Modern randomizer option and Settings declarations

This provider projects the complete pinned 9.2.3 `Option`, `LocationOption`,
`TrickSetting`, `OptionGroup`, `Tricks` and `Settings` declarations. There is no
separate upstream class named UIOption; Option is the current UI option owner.
Every member and method remains in its actual class. `OptionValue` continues to
come exclusively from the existing randomizer provider's OptionValue.h/.cpp.

The complete option.cpp now compiles through XDK: 59 methods here plus the four
already separated canonical OptionValue methods preserve all 63 upstream
definitions. The real checkbox/combobox/slider rendering, CVar interaction and
SohMenu widget registration compile. They have not executed on Xenon/Xenia.

The exact small Settings constructor is also compiled as SettingsConstructor.cpp.
The complete settings.cpp is retained with that definition removed, ready for
subsequent implementation projection. It is not yet compiled or production
coverage. No Settings method has a fabricated implementation.

## Initialization contracts

XDK cannot express the defaulted constructors plus nonstatic member defaults.
The projection preserves the distinction between `Option option;` (key,
widgetType and some WidgetInfo fields remain indeterminate) and `Option()`/`{}`
(value initialization also zeroes those fields). The normal constructor applies
only the real ten defaults. An overload taking the existing storage-free
`Shipyard::SohUI::ValueInit` tag supplies value initialization. Derived option
classes preserve the same distinction; OptionGroup retains all four defaults.
`value_expressions()` is available to project explicit empty constructions in
future consumers; do not replace ordinary default initialization with it.

Settings' seven member defaults move to its actual user-provided constructor.
Its original empty array initializers value-initialize all 232 Options and 268
TrickSettings. Because user-written compatibility constructors affect aggregate
value initialization, the generated constructor fills those actual arrays with
the tagged values before its original (empty) body. The fill operates in place
and avoids returning a 98/128 KB array temporary on the Xenon stack. All 85
OptionGroup defaults and the original excluded-area vector size are retained.
Existing explicit constructor member initializers continue to override defaults.

All corresponding changes are paired in the generated headers/source; do not
combine these headers with unprojected constructors. Current source inventory
finds no other default-created containers of these classes: spoiler_log.cpp
copies the actual Settings Option array, and other option collections hold
pointers. New container value-initialization uses require the same audit.

## Other narrow adaptations

- Scoped enums use the existing typed Xbox representation (A).
- Braced constructor returns become explicit calls with identical arguments;
  two-string option lists become typed arrays/range construction (A/B).
- `contains`, range loops and two-argument map emplace select the existing
  compatible operations. No values, bounds, callbacks or widget behavior change.
- Settings' unused SeedContext/spoiler-log transitive headers become a genuine
  Context forward declaration and no include, respectively. The complete class
  and all stored arrays/maps remain (A).
- option.cpp does not use Settings; its unused include is omitted. Its theme
  function/macro declarations are extracted from the hash-locked actual SohGui
  header. Its full SohMenu class comes from the canonical menu provider.
- The upstream pointer map/shared widget-options behavior when an Option is
  copied is preserved and tested, including the pointers referencing the source
  object's option text. This provider does not silently repair that behavior.

These are 3Shipsty source projections using generic Shipyard compatibility
primitives. No reference tree or shared provider is edited.

## Validation and integration

```
C:/Python313/python.exe -B tools/shipyard/test_randomizer_options.py
C:/Python313/python.exe -B tools/shipyard/prepare_randomizer_options.py --build
```

Five tests pass. Host original/projected execution exercises 50 real option
methods and the real Settings constructor: normal versus value initialization,
17 choices, every uint8 selection, hidden/disabled flags, callbacks, group
containers, trick tags, copy ownership and every Settings array element. The
nine excluded host methods require the real CVar/render/menu services and are
all compiled in the complete native production TU instead of using test providers.

The native ABI probe records every stored field offset. Current Xenon sizes:
Option/LocationOption 424, TrickSetting 480, OptionGroup 104, Settings 242432 bytes.
Test-only friend declarations allow inspection without changing class storage.
Host and native layouts are not claimed equal; they use different standard
libraries and native value representations.

Use `scratch/randomizer-options-xdk/generated/soh` before the partial randomizer
include root. `includes()` returns the canonical closure. Build records are in
`scratch/randomizer-options-xdk/xdk/build.json`; **exclude declarations.cpp** from
production. `abi.cpp` is also strictly a probe. Production inputs are option.cpp
and SettingsConstructor.cpp. Map the latter to the one Settings constructor
fragment from settings.cpp. Keep the existing four-method OptionValue.cpp,
and never include another definition of those methods or the Settings constructor.

Receipts: `verification.log`, `xdk/abi.json`, `host-original/run.json`,
`host-projected/run.json`, and both host scope.json files. No ImGui frame,
randomizer generation, startup or gameplay execution is claimed by these tests.
