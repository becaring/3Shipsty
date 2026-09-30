# Current Xenos rendering backend

All three active consumers compile Shipyard's physical `sources/xenos/core.cpp`.
Modern SoH's local `api.cpp` adapts the current 9.2.3 rendering interface,
including its uint64/uint32 shader IDs.

API 7 uses the single shared package root. `tools/shipyard/xenos_capabilities.py`
selects shader ABI 2, prebuilt shader packs, deferred framebuffer work, binding
reuse and the tiling budget for this adapter. Normal builds disable diagnostic
instrumentation; `SHIPYARD_XENOS_DIAGNOSTICS=1` enables it explicitly. The host
shader-pack builder and runtime probe both request shader ABI 2.

The shared core implements six texture/sampler slots, independent attachment
clears, rectangular copy, native RGB5551 readback, and native display creation
before Xbox system UI. BattleShip-specific callback behavior remains in its
adapter.

Shipyard's physical `sources/graphics/shader_provider.cpp` runs feature decode,
Prism HLSL generation, and exception handling. This adapter supplies the
current interpreter decoder; Smash supplies its own full-width decoder. The
shared Xenos lowerer and D3DX compiler consume the result.
The old donor combiner generator is removed. An internal cache key includes
the complete current IDs, filtering and sRGB, because those modes change the
generated shader. Existing interpreter-held pointers are resolved to the
current variant when loaded, including an already-bound shader on a mode
change. The game-facing interface and vertex layout do not change.

The old title's disk shader cache/save worker is deliberately not linked yet;
actual native compilation remains available on every miss. Modern storage
must own cache location, worker lifetime and ABI rejection before persistence
is restored. The old application's asset-cache eviction call is also removed:
current LUS owns resources and real XDK allocation failures remain fatal.

Known generic donor sampler/three-register/upload exact-value reuse is retained
with native-state invalidation and opt-in verification. New six-binding
constants initially use direct SDK writes. Thread-local native timing and
native state/upload counters remain observable; application report wiring and
measurement are pending. No old performance percentage is claimed for 9.2.3.

Readback converts an untiled native ARGB numeric word to native RGB5551,
preserving the current rounded channel and nonzero-alpha rules. The existing
interpreter owns requested BE-byte conversion. RGBA source uploads and native
GPU tiling/resolve remain separate byte boundaries. Independent clear retains
the unrequested attachment; copy samples the stored image while drawing into
separate EDRAM, including overlapping self-copy.

Commands:

```powershell
python -B tools/shipyard/prepare_xenos.py --build
python -B tools/shipyard/tests/test_xenos.py
```

Five native Xenos and shader-provider TUs compile. The host boundary audit checks all 196,608
channel/alpha cases, 1,536 full-width/mode shader identities and a concrete
current interface. Prism's separate audit covers actual generated shaders.
These tests do not execute D3D, independent clears, copies, GPU ownership or
mode transitions. They are not runtime or hardware validation of the migrated
build.
