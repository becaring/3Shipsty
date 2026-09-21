# Native ImGui backend

The primary SoH360 renderer is copied byte-for-byte into `donor`, hash locked,
and projected against the pinned current ImGui. The entire native renderer,
state capture/restore, callbacks, scissor/vertex offsets, textures, clipping and
shader creation remain. Generic modern names/interfaces were cross-checked
against Smash360; no BattleShip menu or controller pointer mode is imported.

The font atlas is native ImU32 color data; its logical channels are extracted
before RGBA upload. Decoder image buffers are RGBA bytes. These different data
sources keep the primary's proven endian boundary. Xenos half-pixel behavior
and current ImTextureID void-pointer ABI are retained. Unit channel conversion
uses the same rounded float quotient, without prematurely importing a lookup.

Only the primary platform file's actual gamepad Button/Axis helpers and binding
sequence are selected. The physical adapter supplies the first connected slot,
releases keys on disconnect and reports the actual gamepad capability. Current
Gui owns navigation/capture policy. A fresh Xbox installation registers the
existing controller-navigation CVar as enabled; an explicit saved choice is
preserved. No old application CVar names or controller mappings are imported.

The Xenos API calls actual Gui::Init after native renderer creation. Timing and
display size are supplied through the real GUI frame. Modern startup and the
modern UI remain owners of all windows. Physical keyboard, native text entry and
optional controller cursor support remain platform work, not simulated events.

`prepare_native_imgui.py --build` compiles two native objects; Gui initialization
is compiled by prepare_gui. `tests/test_native_imgui.py` compiles both genuine
shader stages with XDK fxc and runs the complete platform frame body against
real current ImGui with explicitly test-only physical/time fixtures. It checks
56 button bindings across four slots, analog/disconnect, timing and navigation
ownership. No fixture enters production, and no native UI render has run yet.
