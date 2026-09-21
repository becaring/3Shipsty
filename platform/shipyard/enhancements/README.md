# Current cheats and ShipInit

`prepare_enhancements.py --build` generates all fifteen complete 9.2.3 Cheat
translation units and the real ShipInit registration header from hash-locked
upstream. All fifteen compile with XDK, including Infinite Ammo's real modern
randomizer bombchu-bag option and Context capacity call. No gameplay effects or
conditions have been replaced. These are compiled production units, not executed
cheat validation.

Generic Shipyard language adaptations (A/B) lower range loops, constexpr integral
constants and initializer-list set arguments. Generated set helpers preserve
construction, ordering, deduplication and temporary lifetimes. Hook call sites
retain actual original source locations; conditional registration macros use
original file/line anchors. XDK's pointer-shaped va_list is copied at the native
boundary in `game-interactor/varargs.h`; SDK va_arg still owns alignment and
argument promotion. No byteswapping applies to native variadic arguments.

`test_enhancements.py` compares actual original/projected ShipInit registration
and dispatch, including boot/path callbacks, duplicate paths and unknown paths.
Independent variadic cursors retain integer/double/pointer/64-bit argument values.
Both contracts also compile natively. Full gameplay/cheat execution remains open.

This provider depends on the real projected GameInteractor, OTRGlobals declaration
and canonical randomizer Context/OptionValue headers. Narrow umbrella includes
are replaced with the actual bridge or complete class declaration required by the
caller. Full application construction remains owned by OTRGlobals.

The eight complete Fixes units also compile. `--build --group Fixes` rebuilds
that group while retaining the other recorded recipes; the assembled project
still requires fresh compilation and never treats a saved recipe as success.

Two additional A/H boundaries were observed in these real callers. XDK rejects
`__FUNCSIG__` inside a static-initializer lambda. A stateless, parameterless void
ShipInit callback is therefore hoisted to a generated named function with the
exact body. Captured/local/value-returning variants fail closed for separate
audit. Registration still stores the callback and defers its execution; the
host/native contract verifies this. Hook file/line metadata remains anchored to
the original source, while the function name identifies the generated callback.
Hammer Hand's two braced Gfx arguments become local Gfx variables initialized by
the very same original gs macros, then passed to the real patch service. No
command bits, resource keys or feature conditions change.
