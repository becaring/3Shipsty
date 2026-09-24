# Current-LUS graphics compiler boundary

This increment compiles the actual 9.2.3 rendering/window interfaces, an exact
extraction of its combiner decoder, and a generic Xenos shader syntax lowerer
with the Xbox 360 XDK. It is not a working graphics backend or a full
interpreter/library build.

Run from the owned project root:

```powershell
python -m unittest discover -s tools/shipyard/tests -p test_graphics_projection.py
python tools/shipyard/prepare_graphics.py --raw-probe
python tools/shipyard/prepare_graphics.py --compile --differential
```

The raw probe is expected to exit 1. It records actual XDK errors for modern
scoped enums, brace-constructed hashes, defaulted destructors and in-class
initializers in `scratch/graphics-xdk/raw/*.log`. The normal compile produces
`interface_contract.obj`, `cc_features.obj`, and `shader_lower.obj` under
`scratch/graphics-xdk/compiled`; it does not produce a XEX.

The host differential uses VS2022, runs 2,097,152 cases through original and
projected current decoder source, and verifies every `CCFeatures` field offset,
size and alignment. It exercises all 17 option bits, custom-ID upper bits,
uniform/mixed combiner terms and both cycles. Original and projected records
are initialized with the same sentinel, so fields left untouched by upstream
remain untouched here. This verifies the source projection and host layout;
it does not validate Xenos execution, Prism expansion or the generated vertex
float layout. Full compiler output, including existing upstream precedence
warnings and donor `sprintf` deprecation warnings, remains in the log.

## Scope and provenance

`source-lock.json` hashes the actual owned LUS headers, interpreter, current
shader builder/template, ImGui patch and dependency declarations. Every input
is checked before generation; drift fails closed. No generated output goes
into upstream or either reference project. The generator does not need to
read a reference project after this import.

The hash-pinned `sources/graphics/shader_lower.cpp` in the platform base is
shared with Smash360. The generated
copy changes only its include/symbol/ABI label and removes Smash profiling
hooks. Its D3D SM4-to-Xenos SM3 syntax transforms are retained. It must receive
expanded authoritative HLSL; unexpanded Prism and missing cbuffer contracts
are rejected. No donor ShaderProgramKey or combiner decoder is imported.

Public virtual signatures remain exactly the current LUS signatures. Shader
IDs stay `uint64_t` and `uint32_t`; decoder components stay `int`; six texture
bindings and the real mask/blend fields remain present. Protected in-class
defaults move to base constructors, the default destructor gets its empty
body, and `std::hash<float>{}` becomes `std::hash<float>()`. The decoder body
is not rewritten. Only its scoped enumeration declaration is represented by
the equivalent scoped constants that XDK accepts; this extraction does not
claim to project the general `ShaderOpts` type for arbitrary consumers.

The generated `imconfig.h` projects only the pointer `ImTextureID` ABI macro
from this release's actual patch. It is sufficient for these graphics headers
and intentionally provides no substitute ImGui API. A real pinned ImGui build
must supply its complete configuration at the integration boundary.

## Next shader/Prism implementation boundary

1. Import the exact dependency revision from
   `libultraship/cmake/dependencies/common.cmake`:
   Prism `bbcbc7e3f890a5806b579361e7aa0336acd547e7`. Hash-lock the selected
   dependency files. Smash's `prepare_prism_xdk.py` and generic compatibility
   helpers can inform narrow transformations after matching source shapes;
   their BattleShip builder/template and source-lock manifest are not inputs.
2. Project the real helper/builder region of
   `libultraship/src/fast/backends/gfx_direct3d11.cpp`, ending with
   `Fast::gfx_direct3d_common_build_shader` at line 1350. The similarly named
   `gfx_direct3d_common.cpp` does not contain the builder. Preserve Prism
   formulas, callbacks, context, includes and `raw_numFloats` accounting.
3. Keep real shader resource loading: type Shader, native byte order, binary
   format, `LoadResource(path, true, init)`, default path
   `shaders/directx/default.shader.hlsl`, and include loading. These are real
   link dependencies; do not manufacture a ResourceManager/Prism facade or
   replace the default with an old hand-written combiner shader.
4. Link original and projected host Prism builds to a corpus that compares
   expanded HLSL and generated float counts; feed that real HLSL through this
   lowerer and XDK vertex/pixel compilation. Cover two-cycle/fog/noise/alpha,
   maximal varyings, all clamp axes, six masks/blends, filter/sRGB state,
   custom resources and includes. The current increment's rejection checks
   are not that acceptance corpus.
5. Implement an owned Xenos backend against the projected **current**
   virtual interface, importing separately audited EDRAM/texture/presentation
   mechanics. Implement independent color/depth clears, rectangular copies,
   CPU readback and six texture slots before connecting the real current
   interpreter/window/GUI flow. No SSB-specific framebuffer policy or API
   extensions should be introduced just to reuse Smash's wrapper.

Production links must eventually use the full current interpreter definition
of `gfx_cc_get_features`, not also link this audit extraction and produce
duplicate definitions. Keep 9.2.3 `OTRGlobals`/interpolation/window sequencing.
