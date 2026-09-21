# Current Context and lifecycle closure

`tools/shipyard/prepare_context.py --build` generates from locked current source
and compiles twelve native TUs: Context, Console, CrashHandler, FileDropMgr,
GfxDebugger, five actual C bridges (audio/CVars/crash/debugger/window), luslog,
and the native platform service. This is not application execution evidence.

Generic Shipyard changes (A/B/C/E):

- The complete current Context initialization order and all subsystem owners
  remain. Unused ControlDeck implementation inclusion is replaced by direct
  dependencies actually used by Context. No synthetic Context is introduced.
- Desktop module paths, console allocation and DbgHelp APIs are guarded away
  from Xbox. Native bundle/application paths currently match the primary
  SoH360 `game:` convention. The writable XContent root is still pending and
  must be connected before any save/storage validation claim.
- The missing-resource dialog uses XShowMessageBoxUI with real overlapped
  completion. No resource failure is converted into successful initialization.
- Failed/partial Context destruction checks Window/Config before saving;
  failed Window::Init clears the published owner before propagating. These
  generic startup failure lessons were inspected in Smash360's
  tools/prepare_context_xdk.py and prepare_startup_xdk.py. Their Smash app
  startup, paths, rumble policy and game-specific changes were not imported.
- FileDropMgr keeps all handlers, notifications and strdup/free ownership.
  Native duplicate-registration diagnostics report the address because desktop
  DbgHelp symbol lookup is unavailable.
- GfxDebugger keeps the current request/breakpoint/resume state machine.
  Console keeps current registration, lookup, command execution and usage text.
- The C logging bridge retains literal preformatted braces via the explicit
  spdlog string-view overload; source locations use the real constructor.

CrashHandler retains the current callback/buffer implementation. Native exception
capture must still be connected at Xbox entry/thread boundaries. No PPC stack
walk or automatic exception capture is claimed. Existing upstream issues are
recorded for execution review: the callback constructor creates a temporary
CrashHandler rather than initializing this buffer; AppendLine can exceed the
buffer after truncation. Neither was silently rewritten in this projection.

GameOverlay.h is a complete projected declaration needed by FileDropMgr.
GameOverlay.cpp remains unbuilt: its constructor must restore `Default` font
and `false` cleanup state when integrated. No overlay behavior is removed.

`tests/test_context_controls.py` compares current Console methods excluding
live-Context Run, and the entire GfxDebugger implementation. Registration,
duplicate handling, usage text and debugger transitions agree. An initial
attempt to link uncalled Run with /OPT:REF still required Context symbols;
that test strategy was discarded. The final audit explicitly selects methods;
the complete production Console TU separately compiles without exclusions.

No XEX, Xenia, playback, native UI, device selection or hardware validation.
