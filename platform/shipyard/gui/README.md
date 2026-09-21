# Current GUI on the native backend

`prepare_gui.py` retains and compiles the entire pinned Gui, ConsoleWindow,
InputEditorWindow, StatsWindow and GfxDebuggerWindow, plus the native backend's
real Gui initialization call. This is the actual current GUI: docking, viewport
calculation, resource textures, menu ownership, console commands, input capture,
remapping, device toggles and graphics debugger methods remain present.

Platform dispatch selects native ImGui initialization, per-frame events, draw
submission and shutdown. Desktop SDL implementations are preprocessor guarded;
Xbox reports no independent desktop viewport support through the existing
SupportsViewports fallback. Native textures use the current rendering API.
Debug clipboard writes use ImGui's platform clipboard interface, which supplies
an application-local clipboard on this target. Stats identifies Xbox 360.

Compatibility changes:

- A/B: inherited/delegating constructors become explicit forwarding overloads;
  original member defaults remain ordered, including console vectors and colors.
  Structured bindings/ranges use the already reviewed generic container lowering.
  Command metadata comes from the original seven declarations and is constructed
  in the same order; no replacement commands or simplified input editor.
- A/H: XDK rejects lambda default arguments (C3486), and initially crashed before
  reporting it (C1001). The debugger's 32 two-argument calls now supply the same
  null third argument explicitly. Return-type and formatter-hoisting experiments
  were discarded; the original formatter and lambda bodies remain.
- H: the 155,710-byte base85 Font Awesome string exceeds XDK's 65,535-byte string
  limit. Its exact bytes plus terminator become a generated numeric char array.
  C's escaped question marks are decoded explicitly. No font substitution.
- B/C: console varargs use XDK's required-length and bounded formatting APIs;
  the real current priority/text/channel and truncation contracts remain.
- B: the debugger reuses the tested generic optional implementation already
  projected for Prism. Its game textures/resources and disassembly path remain.
- C: GUI shutdown precedes native graphics destruction; shutdown is idempotent
  for the existing Window base destructor and uninitialized failure cleanup.
- I: RTTI is required for current dynamic casts; native C++ recipes enable /GR.

Validation: `prepare_gui.py --build` compiles six complete Xenon objects with
RTTI, including the current input editor and debugger. `tests/test_gui.py`
checks deterministic generation, full method/overload inventory and ten unchanged
GUI ownership/resolution methods. It compiles the original font literals
independently of Python decoding, compares all 155,711 bytes and builds both
through actual current ImGui: 512x256, 903 glyphs, hash 56e5f0b0 in both cases.
This is not linked GUI execution or native GPU validation.

Outstanding: actual SoH Menu/SohGui/enhancement windows and their application
dependencies, physical keyboard/text entry, storage-backed settings, full
ResourceManager/Context execution, final linking and Xenia interaction. Optional
GFX_DEBUG_DISASSEMBLER requires its real dependency before enabling that build
option. No XEX or gameplay is claimed by these compiler checks.
