# Modern input projection and native physical boundary

`python -B tools/shipyard/prepare_input.py --build` stages all 97 pinned modern
controller inputs (50 headers and 47 complete TUs) and compiles those 47 TUs plus
the two native physical implementation TUs. `scratch/input-xdk/xdk/build.json`
contains actual commands/status; successful objects are checked for Xenon COFF
machine 0x1f2. This is compilation evidence, not a linked application or physical
controller execution claim. The source inventory and normalized-text hashes
fail closed; upstream and reference trees are never modified or executed.

This retains Ship/LUS ControlDeck, ControlPort, Controller, both sticks, buttons,
gyro, LED, rumble, every mapping and factory, keyboard/mouse event classes,
wheel buffering, default bindings, config paths, input blocking, raw remapping,
and the six-frame input-lag buffer. CONTROLLERBUTTONS_T is uint32_t, including
OSContPad; consumers of the projection reject an explicit narrower override.
Public ControlDeck constructor signatures are unchanged. Range loops retain
value versus reference semantics; nested pair bindings, container initializers,
generic lambdas, enum qualification, delegating constructors, round/clamp and
contains/to_string are projected for XDK without replacing classes.

## Read-only reference audit

The primary SoH360 `xinput_controller.cpp` supplies useful native physical
facts: XInputGetState/GetCapabilities/SetState, the 15 button masks, saturated
Y inversion (-32768 to +32767), and 0..255 triggers scaled to 0..32767. Its old
DeviceProfile ownership, per-game default mappings, raw remapping, N64 stick
normalization and presentation press-edge buffering are not imported: current
modern controllers already own those policies, with different APIs. The old
`input_xinput.cpp` window/hotkey glue does not become a replacement ControlDeck.

The secondary Smash360 physical bridge uses those same generic XInput semantics
and a current-core-compatible physical API. Reviewed physical and AST helpers
were copied into owned Shipyard input files, with original hashes recorded in
`reference-provenance.json`. No donor code runs during generation. Smash-specific
Raphnet branches, game/window callbacks, performance hooks and input defaults
are not part of this target. Unlike its constructor projection, this projection
preserves the original zero/one/three-argument ControlDeck overloads.

`sdl_bridge.h` is an explicit source API adapter, not an SDL runtime. The real
current SDL-named mapping classes call native physical functions through it.
Four physical slots are polled, compact enumeration is distinct from slot
identity, and reconnects receive new instance IDs. Unsupported physical gyro/RGB
LED capabilities return false and their operations return an error; existing
mapping/config code remains compiled. Keyboard and mouse mapping logic remains,
but native event delivery requires a later window/device backend.

The native topology generation refreshes the actual manager before game reads
and in its existing GUI event handler. GUI presentation may share one fresh
physical sample via ShipyardInput_BeginGamepadPresentation. Polling clears
state on disconnect and expires timed rumble across tick wrap. Duration zero
preserves current SDLRumbleMapping's sustained-effect contract; explicit stop,
disconnect and manager destruction stop motors. No synthetic runtime input
injection or fallback pad is supplied.

## Behavioral verification

`python -B tools/shipyard/test_input.py` runs original and projected C++20 host
builds of both complete default-mapping classes, mapping bases and eight actual
ControllerStick methods. All six default mapping containers compare exactly,
custom high-bit keyboard/gamepad bindings survive, and 40,401 stick vectors
exercise signs, radial deadzone, octagonal saturation and multiple-map maximum
selection. The fixture then exercises the production physical bridge using
explicit host physical-byte fixtures: sparse slots, buttons, axis extrema,
trigger scaling, reconnect IDs, timed/sustained rumble, wraparound/disconnect
and unavailable capabilities. Fixtures are not native controller execution.

## Integration and inherited behavior still to verify

Put scratch/input-xdk/generated/include ahead of original LUS headers; retain
the generated CVar definitions and uint32 controller width in every consumer.
Link all 49 objects with the current Context/config/window/ImGui closures and
native XInput/XDK libraries. No final link or console/Xenia input test has run.
Actual menu capture, raw remapping plus save/reload, routing all four ports,
controller navigation, keyboard/mouse hardware events and shutdown ordering
still require integration validation. Gui/Context must not consume destroyed
managers; complete GUI/InputEditor TUs are separate work.

Several current-source quirks are preserved for separate review: ControlDeck's
base constructor does not copy buttonNames into mButtonNames; GetControllerBits
is declared without a definition in this source tree; manager topology refresh
reapplies default ignores for ports 1..3; ControllerStick's device-clear loop
changes a copied inner map. The projection does not silently rewrite upstream
mapping behavior to match a donor branch. These are material runtime follow-ups,
not proof that mapping/routing integration is complete.
