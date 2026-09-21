# Complete modern SoH controller editor

`prepare_soh_input_editor.py --build` source-locks and projects the entire
Shipwright 9.2.3 `SohInputEditorWindow.h/.cpp`. The complete real TU compiles to
`scratch/soh-input-editor-xdk/xdk/SohInputEditorWindow.obj`, checked for PPC COFF
machine `0x1f2`. This is application code using current LUS controller interfaces,
not an imported old controller editor. The source remains a `Ship::GuiWindow`
subclass, as upstream specifies; it is not replaced by LUS InputEditorWindow.

All 41 function definitions, 13 member declarations, 50 CVar expressions, and
seven menu-search widget registrations remain. This includes the Link/Ivan/debug
port tabs, raw remapping, ordered mapping-ID caches, controller schema preview,
stick/deadzone/notch controls, rumble, LED/gyro interfaces, device toggles,
reset/clear actions, custom ocarina input, camera controls, and D-pad menus.
The existing native mapping capability queries remain authoritative: this does
not pretend Xbox controllers have gyro or RGB-LED support.

## Narrow compatibility changes

* **A/B:** All seven inherited GuiWindow constructor signatures are expanded
  against the canonical base header. The real application uses the unchanged
  two-string constructor, then the actual InitElement lifecycle. Timer/popup
  initialization remains in InitElement. No game state moves into the platform.
* **A:** `decltype(buttons)::iterator`, which the XDK frontend rejects for this
  nonstatic member, becomes the identical explicit list iterator type.
* **A/B:** Four set initializer assignments become typed ranges. The two nested
  temporary initializer ranges retain their exact element types and loop
  lifetimes. The existing audited pair-binding/range lowering handles all map
  iteration. All controller masks remain 32-bit.
* **A:** ImVec4 aggregates use its actual constructor; RGB aggregates use the
  existing generic RGB helper. The six-entry LED-source vector uses a typed
  source array, retaining values/order and static lifetime.
* **A/B:** Seven WidgetInfo aggregate assignments and two CheckboxOptions base
  aggregates use the canonical real value-initialized UI types. Their defaults,
  ownership, and unspecified zero-initialized fields are preserved. SearchWidget
  construction retains the reference to its original static WidgetInfo object.
* **A:** The UTF-8 degree symbol is emitted as explicit byte escapes; those
  original UTF-8 bytes are found in the actual native object.
* **C:** Visible `Gamepad (SDL)` descriptions become `Gamepad (XInput)`. The real
  SDL-named mapping classes and `SDLGamepad` persisted identity remain unchanged:
  the existing Shipyard physical boundary already adapts them to XInput.

The source's analog-preview operator precedence and existing map/cache behavior
are retained. This port does not silently repair application quirks.

No donor code, dependency generator, or shared platform provider was changed or
executed. The generator reads the existing canonical MenuTypes/UIWidgets,
SohMenu, Context, GuiWindow, and native controller projections.

## Validation

```
C:/Python313/python.exe -B tools/shipyard/prepare_soh_input_editor.py --build
C:/Python313/python.exe -B tools/shipyard/test_soh_input_editor.py
```

`xdk/build.json` records the full production recipe and source/object hashes.
`manifest.json` records source/dependency hashes, generated hashes, helper hash,
and UTF-8 literal evidence. `verification.json` records the host contracts and
function/member/CVar inventory audit.

The host state contract binds four exact original/projected method bodies to
their actual field declarations in an isolated test fixture. It checks all
four initialized bitmask sets, initial timers/popup state, 15 ordered names,
duplicate-name replacement without changing earlier list nodes, a high-bit
mask, rumble sentinel semantics, and colors for known/unknown physical devices.
This exercises those algorithms; it does not instantiate or render a real
application window or supply replacement Context/controller services.

The separate value contract uses actual original/projected WidgetInfo,
CheckboxOptions and SearchWidget types. All seven editor widget names retain
their defaults; both disabled states preserve the inherited option fields and
owning option copy; search records preserve reference identity and the omitted
extraTerms default. Original/projected outputs agree.

Actual menu drawing, remapping/configuration persistence, raw input capture,
rumble motors, and all four ports still require the genuine linked application
in Xenia/hardware. Native compilation is not execution evidence.

## Integration

Use `prepare_soh_input_editor.includes()` (or its equivalent ordered manifest
paths) and consume the single production row in
`scratch/soh-input-editor-xdk/xdk/build.json`. Keep its generated `soh` include
root before original SoH headers. The canonical menu/UI and controller include
roots remain ahead of upstream fallbacks. No extra native TU is required;
`support.h` contains only typed value-construction helpers.

The existing startup construction
`make_shared<SohInputEditorWindow>(CVAR_WINDOW("ControllerConfiguration"), "Configure Controller")`
uses the unchanged real interface. RegisterInputEditorWidgets still registers
through the real MenuInit function list and attaches to the actual SohMenu.
