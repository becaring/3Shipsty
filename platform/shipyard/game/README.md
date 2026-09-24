# True C XDK projection

The provisional C-as-C++ route is rejected and removed from the generator.
Both preprocessing and object compilation now use `/TC`; C pointer conversions,
C identifiers such as `this`, and C linkage remain under the C frontend.
There is no blanket `/TP` wrapper or global void-pointer casting pass.

Verified real application sources:

| Source | XDK result | Boolean conversions | C99 scope projections |
|---|---|---|---|
| `soh/src/code/sys_math.c` | Compiles as C | Header type projections only | 0 |
| `soh/src/code/main.c` | Compiles as C | Header type projections only | 0 |
| `soh/src/code/graph.c` | Compiles as C | 1 initializer, 1 scalar store | 6 |
| `soh/src/code/z_actor.c` | Compiles as C | 2 initializers, 5 pointer stores | 30 |

Run from the project root:

```powershell
python -m unittest discover -s tools/shipyard/tests -p test_game_projection.py
python tools/shipyard/prepare_game.py --verify-semantics
python tools/shipyard/prepare_game.py --source soh/src/code/sys_math.c --source soh/src/code/main.c --source soh/src/code/graph.c --source soh/src/code/z_actor.c --keep-going
```

`scratch/game-xdk/compile-report.json` records source and generated hashes,
compiler hash, exact `/TC` commands, exits and transformation counts. Original
preprocessed input is in `preprocessed/*.i`; generated C is in `generated/*.c`.
The old generated `.cpp` files are obsolete experiment artifacts and are not
selected or compiled. Each successful object is hashed only after the compiler
returns zero; an old object does not turn a failed run into success.

## Scoped transformations

- The release's randomizer `RANDO_ENUM_ITEM` macro retains the arity-dispatch
  replacement for `__VA_OPT__`. Custom reflection macros remain intact.
- Only native `main.c` desktop guards change to exclude `_XBOX`; the actual
  main body remains compiled.
- Four `OSMesg` compound-literal constructors become typed `static __inline`
  union-return factories. The intended active member and parameter conversion
  remain the same, and the argument is evaluated once. Current C call sites
  use message values; no lvalue/address-taking replacement is claimed.
- `AudioChannelsSettingName`, the existing header-only helper, uses XDK C
  `static __inline`; no function body is replaced.
- CVar definitions follow the release's order: `CMake/soh-cvars.cmake`,
  `CMake/lus-cvars.cmake`, then LUS cache defaults. Prefix substitutions are
  resolved, and earlier cache values survive later defaults. A generated
  forced-include header avoids command-line string quoting changes. The
  game-print cutoff comes from the root CMake `SPDLOG_LEVEL_OFF` value.
- Both active game generators import Shipyard's physical
  `python/xbox360_platform/c89_lower.py`. This consumer selects non-XDK source
  spans and enables the `CutsceneData.f` literal bit-pattern conversion. The
  shared lowerer retains declaration execution points using nested scopes and
  scoped `for` initializers.

## Boolean conversion proof and limits

`stdbool.h` expands to semantic `_Bool` before the AST pass. Byte storage is
introduced only after supported scalar initializers, assignments, returns,
casts and direct-call arguments have `!!(value)` conversion. The pass tracks
scopes, scalar/pointer declarations, direct function signatures and unambiguous
field names. Pointer dereference/index/postincrement stores preserve evaluation
of the left side; only their RHS is canonicalized.

The executable corpus compiles the same functions as native host C11 and
projected C, then compares results for -257, **-256**, -1, 0, 1, 255, **256**,
257 and fractional floating values. It covers parameter conversion, scalar and
field stores, pointer writes/index/postincrement, casts, returns, one-time
evaluation, shadowing and declaration/loop scopes. The projected corpus also
compiles with the real XDK C frontend. Results are in
`scratch/game-xdk/semantics/report.json`, `host.log` and `xdk.log`.

This is a deliberately limited semantic projection, not a general C compiler.
Boolean arrays, scalar typedef aliases, bitfields, indirect-call boolean
parameters, compound scalar stores other than identifier `|=`, scalar increment/decrement, incompatible
pointer escapes/casts, ambiguous field names and recognized boolean aggregate
initializers stop with an explicit projection error. Boolean-returning
function-pointer typedefs without boolean input parameters are preserved;
their real boolean function definitions normalize return values.

The test corpus proves those supported conversions on the host and XDK
compilability; it does not prove cross-TU C/C++ boolean ABI or Xbox runtime
behavior. Wider source coverage must audit any newly encountered construct
before widening this pass. Existing C warnings in graph/actor code (including
pointer/integer conversions and discarded const qualifiers) remain visible
and still need ABI/runtime review. No features or selected application source
files are excluded. No XEX, gameplay parity or full-game link is claimed.

`source-lock.json` fixes the transformed source/header/CMake inputs and records
the donor origin. Upstream and reference trees remain unchanged.

## Complete C inventory (2026-09-20)

All **696/696** selected current application C translation units compiled in one
complete XDK `/TC` run with the release's fixed-point matrix configuration.
The selected manifest SHA-256 is
`19d2cfa7a7ed318f5839e592727ed206660f478ed43df229f740c66e9a75dfea`.
Exact per-source commands, warnings, transformations and object hashes are in
`scratch/game-xdk/full/compile-report.json`; the compact summary is adjacent.
The earlier 646/696 diagnostic with an invented `GBI_FLOATS` define and the
corrected 656/696 diagnostic are superseded. Their objects are not linked.

Remaining compiler failures were addressed at these explicit boundaries:

- `IS_ZERO(f)` triggered an XDK preprocessor defect substituting `f` inside
  `0.008f`. Renaming only the formal to `value` preserves the expression.
- Case declarations receive scopes closing at the enclosing switch body,
  preserving visibility across fallthrough labels. The host differential
  corpus checks this behavior.
- `aggregate_c.py` lowers only audited rvalue `Color_RGB8`, `Color_RGBA8` and
  `GetItemEntry` compound literals to typed factories generated alongside the
  actual definitions. Parameter types preserve field conversions. Address,
  lvalue, file-scope, designated and incomplete forms are rejected.
- The two exact source files using designated initializers are projected only
  after checking member order against the locked modern declarations. Nested
  position vectors and the audio union's first `f` member retain their order.
- `xdk_math_boundary.h` captures the XDK's actual float math macros into inline
  functions before game locals or declarations can interfere with expansion.
  The SDK double operation and float conversion remain intact.
- Only FileChoose_IsSaveCompatible's reached `restrict` parameter uses the
  compiler's `__restrict` spelling. A broad define was rejected because it
  corrupts SDK `__declspec(restrict)` declarations.
- The modern mixer receives genuine official Opus/opusfile headers and native
  libraries, plus the XDK spelling for its two internal inline clamp functions.
- Boolean `|=` on a simple scalar identifier becomes `b = !!(b | rhs)`.
  RHS evaluation remains unconditional and once; the differential corpus checks
  false/true LHS, wide positive/negative RHS and side effects. Other compound
  boolean stores remain rejected.

The one accepted opaque boolean pointer boundary is source-locked:
`FB_CopyToFramebuffer` passes its fourth `u8*` parameter through `gDPCopyFB`
into `words.w1`; the actual current interpreter recovers it as `bool*` and
its only write is canonical `true` in `Interpreter::CopyFrameBuffer`.
This permits that exact call/argument pair, not arbitrary byte-pointer escapes.
Target C/C++ boolean storage layout and actual GPU completion still require
integrated ABI/runtime validation.

Textually included `.c` files are included in each selected TU's dependency
closure (for example Boss Ganon 2 data); they are not independent duplicate TUs.

```powershell
python -B tools/shipyard/tests/test_game_projection.py
python -B tools/shipyard/prepare_game.py --verify-semantics
python -B tools/shipyard/prepare_game.py --all --keep-going
python -B tools/shipyard/prepare_game.py --summarize
```

Nine generator tests and native/projected C semantic execution pass. This
coverage does not establish link success, Xenon runtime parity or C++ application
integration. No source selection was reduced and no upstream source was edited.
