# Current Xenos rendering backend

The primary SoH360 native backend is imported byte-for-byte and hash-locked;
its hash also matches Smash360's copy. The owned generator selects production
rendering, readback and shutdown mechanics, excluding old callback tables and
diagnostic test scenes. The concrete class implements every current 9.2.3
GfxRenderingAPI method, retaining its original uint64/uint32 shader API.

Reviewed generic modern adaptations from Smash360 are recorded in
donor.lock.json: six texture/sampler slots, six dimension uniforms, independent
attachment clears, rectangular copy, native RGB5551 readback, write-only depth
and native display creation before Xbox system UI. BattleShip held-VI texture
ownership, framebuffer destruction/color-write extensions, postprocess and
Smash application callbacks are excluded. No donor generator runs in a
reference tree. Generated code is under scratch/xenos-xdk.

Production shader creation calls the actual current interpreter decoder and
Prism builder, then the reviewed generic Xenos lowerer and D3DXCompileShader.
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

Three complete native TUs compile. The host boundary audit checks all 196,608
channel/alpha cases, 1,536 full-width/mode shader identities and a concrete
current interface. Prism's separate audit covers actual generated shaders.
These tests do not execute D3D, independent clears, copies, GPU ownership or
mode transitions. The class still needs real Fast3dWindow/Gui wiring, native
presentation, device events, storage and application linking. No XEX, GPU or
hardware result is claimed. Error dumps currently use game:; writable XContent
must be integrated before claiming durable diagnostics/cache storage.
