# Modern window and native presentation

`prepare_presentation.py` projects all methods of the pinned LUS Fast3dWindow
and FastMouseStateManager; hashes guard the four inputs. It preserves the entire
DrawAndRunGraphicsCommands method byte for byte. No game loop is introduced.

Shipyard owns the concrete current GfxWindowBackend implementation. Native
device creation precedes renderer initialization, the presentation surface is
1280x720 fullscreen, and upstream retains internal rendering resolution, GUI,
framebuffer and interpolation ownership. Xbox has no desktop windowed mode or
independent viewport windows. Unsupported configured backends fail explicitly.

Compatibility classes A/C/I: delegating constructors initialize the same base
and call the original interpreter construction body exactly once; member
defaults move to constructor initialization, scoped enum switch uses its value,
and coordinate returns construct the same POD. The destructor guards an
interpreter that never entered Init, as Context can destroy failed startup.

Native mechanics follow SoH360 platform.cpp StartFrame and Smash360
graphics/window_xenos.cpp's modern virtual interfaces. No raw donor source is
copied. Presentation fractions use the primary SoH accumulator, with its crucial
rule that unchanged target rates do not reset the remainder. The actual display
refresh replaces the donor's fixed 60Hz, and a 64-bit addition avoids overflow.
Rates below refresh/4 use the primary explicit sleep plus four native intervals.
These are generic platform mechanisms; no Smash scheduling or profiling is
imported. The actual device presents once through SwapBuffersBegin.

HandleEvents samples real XInput; accepted presentations start the shared
physical sample used by current GUI/device handlers. Close stops rumble.
Keyboard/pointer hardware event delivery remains unimplemented; modern mappings
remain available but receive no synthetic events. No pointer capture is claimed.

Validation: `python -B tools/shipyard/prepare_presentation.py --build` compiles
three full Xenon objects. `python -B tools/shipyard/tests/test_presentation.py`
checks 2,024,400 pacing steps, unchanged target rates, target/refresh changes,
invalid zero values, overflow bounds, concrete current virtual coverage, the
unchanged draw path and deterministic projection. These checks do not execute
native presentation, GUI, controller input, or any game in Xenia. GUI native
backend wiring and final application linking remain open.
