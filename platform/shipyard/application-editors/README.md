# Complete audio and cosmetics editors

The generator projects the complete pinned 9.2.3 `AudioEditor.cpp` (26
definitions) and `CosmeticsEditor.cpp` (35 definitions). It uses the canonical
full window declarations from application-gui, AudioCollection/SeqType from
audio-collection, and the actual current UIWidgets, menu, GameInteractor,
SeedContext, resource patching and controller interfaces. It introduces no
replacement UI, service, state machine or class declaration.

Reproduce from the repository root after the existing dependencies are ready:

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_application_editors.py --build
C:/Python313/python.exe -B tools/shipyard/test_application_editors.py
```

Integrate the two generated source paths from `SOURCES` using `includes()`
prepended to the existing application compile recipe. Exact commands, source
hashes, PowerPC machine verification and object hashes are in
`scratch/application-editors-xdk/xdk/build.json`. Objects are `AudioEditor.obj`
and `CosmeticsEditor.obj` in that directory. There is no new startup hook:
the complete original window initialization and ShipInit/MenuInit registrations
remain in the actual translation units. Retain these objects in the normal
application link so their static registrations are included.

## Narrow adaptations

* Generic Shipyard compiler work: map/vector initializer construction; unchanged
  ordered map insertion; a helper initializes the original function-local static
  sequence visibility map at its original first-use point; empty containers;
  array list syntax; structured bindings/range loops/contains through the
  existing compiler helper; canonical source-location hook arguments.
* Generic Shipyard UI work: aggregate widget values use the canonical value-init
  constructor, preserving every omitted/default field; SearchWidget uses its
  canonical reference-preserving constructor. Option value initialization is
  preserved before applying the real chained setters.
* Application source projection: real cosmetic ImVec4/Color_RGBA8 construction
  uses equivalent constructors/the existing ColorRGBA8 function. The original
  `CosmeticOption` definition, all fields and 197 active options remain intact.
  No save, randomization, color algorithm or asset identifier is changed.
* Gfx command aggregates are assigned to a local actual `Gfx` before being passed
  by value. The PATCH_GFX local stays inside its original enabled branch; the
  four direct patch calls remain in their original execution scope. All 260
  command macro calls and 256 PATCH_GFX sites retain their original arguments.
  These are runtime-native display-list command structures; no byte swap,
  archive conversion or GPU representation change is introduced.

The source lock also covers both original headers and the relevant enum/value
headers. It refuses source drift. The manifest hashes projection helpers;
generated output remains reproducible and does not edit pinned sources.

## Validation and limits

Both full translation units compile with the native XDK. Original/projected
host executions compare all cosmetic option fields and colors, 21 group labels,
both five-entry randomization-mode maps, all nine sequence visibility entries,
the ordered eight-type randomization list, and category count/name/color results
for 1,026 enum inputs. A separate fixture executes the real widget assignment
and chained-option statements against original/projected WidgetInfo and option
classes, checking all 11 values, nine reference-backed search records and shared
option ownership. It takes theme color as a test parameter; it does not replace
the runtime theme provider or instantiate a fake menu.

The source audit verifies all definitions and CVar, UI, hook, cosmetic and Gfx
call inventories. It reports counts in `verification.json`. The pinned default
color getter's existing multiply-by-255 casts remain; tests compare the source
color data without relying on out-of-range float-to-byte conversions.

No shared-header change is required. Real menu interaction, resource patch
execution, randomization, controller behavior and game-frame callbacks still
require integrated Xenia validation. No Xbox hardware execution is claimed.
