# Graphics interfaces

The interface reference is Shipwright 9.2.3 with libultraship commit
`fdcaf6336776d24a6408d016b0a52243f108f250`. The authoritative definitions are in
`libultraship/include/fast` and `libultraship/src/fast`; their source locks and
projection contracts live under `platform/shipyard`.

## Modern contract

`Fast::GfxRenderingAPI` is a virtual interface. Its shader identity combines
64-bit and 32-bit fields. This differs from both the older global function table
and other consumers' wider composite shader keys. Adapters must use the modern
signatures without casting between incompatible shader structures.

The modern interpreter has six texture bindings, mask/blend inputs, a custom
shader identifier, and integer combiner fields. Its opcode handlers, vertex
layout, matrix behavior, and color-combiner decoding remain authoritative.
Game-specific display-list redirection and pillarbox rules from another consumer
are not shared Xbox behavior.

## Shader and native boundary

The modern Direct3D shader builder lives in
`libultraship/src/fast/backends/gfx_direct3d11.cpp` and uses Prism plus the
resource-loaded `shaders/directx/default.shader.hlsl`. Resource overrides remain
part of shader construction. Native lowering maps compatible shader expressions
to Xenos shader-model-3 operations, register constants, and sampler interfaces.
Unsupported expressions need explicit rejection instead of silent substitution.

Texture uploads, sampler state, state invalidation, native draw submission, and
EDRAM framebuffer transitions belong to the platform backend. Wrappers preserve
the current framebuffer interface and independent clear behavior. Shared state
suppression must account for external rendering and invalidation.

## Verification

The focused graphics and Prism contracts cover shader/layout equivalence and
native compilation. Cases should include both combiner cycles, alpha, noise,
fog, grayscale, all clamp axes, masks/blends, custom shader bits, and all six
bindings. Filtering and sRGB distinctions must not collide in shader caches.
Source-derived operation reductions require target measurement before reporting
frame-time or FPS improvements.

See [Fast3D](../../platform/shipyard/fast3d/README.md),
[graphics](../../platform/shipyard/graphics/README.md), and
[Xenos](../../platform/shipyard/xenos/README.md) for maintained contracts.
