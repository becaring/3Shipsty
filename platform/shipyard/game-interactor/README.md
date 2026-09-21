# Current application hook boundary

The generator locks every current game-interactor input to stable 9.2.3. Three
complete production files currently compile: GameInteractor.cpp,
GameInteractor_State.cpp and GameInteractor_Hooks.cpp. RawAction and
GameInteractionEffect remain in the inventory but require further application
header integration; they are not counted as compiled.

The original registry/dispatch/removal bodies remain authoritative. Variadic
templates are mechanically expanded into forwarding overloads from zero through
the maximum arity in the actual hook table. Each overload uses the original
std::forward category, callback, filter and accounting expressions. Template
static storage becomes ordinary out-of-class template definitions; there is one
registry per hook type across translation units. No parallel hook dispatcher or
alternate enhancement path is introduced.

XDK lacks source_location's call-site intrinsic. Registration calls are generated
with explicit original file, line and column, plus compiler function signature.
The four registration methods have no default location argument: an unprojected
caller fails compilation instead of silently reporting the header declaration.
The actual conditional registration macros use caller __FILE__/__LINE__/__FUNCSIG__
and zero for unavailable column. Application projections must preserve original
line mappings for those macros. The source-location UI branch remains enabled;
full HookDebugger UI integration is still pending. No game data is byteswapped
at the native hook argument boundary.

XDK's missing inferred return syntax uses explicit bool or std::function return
types for the four actual HookFilter helpers; callback conditions are unchanged.
The latter adds type erasure at filter construction, outside gameplay dispatch.
Current next-ID initialization, HookInfo initialization, and all field defaults
are preserved. No failed registration/removal path is simplified.

`python -B tools/shipyard/prepare_game_interactor.py --build` regenerates the
three complete native objects. `python -B tools/shipyard/test_game_interactor.py`
runs original/projected registry code, including cross-translation-unit storage,
normal/ID/pointer/filter routes, deferred unregistration, callback counters,
ID wrap/collision, caller metadata and mutable pointer arguments. It supplies
no replacement game or resource service. Real game effects, enhancement
registration, HookDebugger rendering and Xenon execution remain unvalidated.
