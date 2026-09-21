# Current Fast3D resource factories

`python -B tools/shipyard/prepare_fast_resources.py --build` projects 19 pinned
LUS inputs and builds nine complete production TUs with XDK, RTTI and upstream
`F3DEX_GBI_2`: DisplayList, Matrix, Vertex and Light types/factories, plus both
TextureFactory versions. Texture itself is supplied by the GUI-resource group.
No handler, XML branch or ownership method is removed. These are generic
Shipyard modern LUS compatibility changes; no application-specific behavior.

Language adaptations (A/B/I): explicit inherited constructors; the existing
scoped-enum representation; range iteration; 33 render-mode entries initialized
via a POD table and the same first-insertion map semantics; `std::size` for a
local array; and 57 GBI brace-assignment expressions given typed local temporaries.
The original GBI macros, command arguments and expanded-command handling remain.
Texture's serialized integer enters its scoped enum through the explicit Value
boundary. `F3DEX_GBI_2` is required by root CMake's GBI_UCODE selection, including
the XML display-list ucode assignment; omitting it does not reproduce upstream.

Endian boundaries: binary Matrix/Vertex/display-list fields and texture metadata
use the actual BinaryReader's declared byte order. Texture image bytes remain
raw GPU/resource-format data; no blanket swap. LightFactory reads an entire raw
LightEntry union exactly as upstream. Directional fields are bytes, but the
point-light union contains int16 coordinates without a factory discriminator.
No SoH registration/producer for that resource has been established; proving its
point-light producer format remains required before enabling any conversion.
Host raw-byte parity is not evidence of native point-light coordinate parity.

`python -B tools/shipyard/test_fast_resources.py` executes the complete original
and generated production TUs. Independent LE/BE fixtures cover signed matrix and
vertex fields, texture versions/scales/raw bytes, all six ucodes and all seven
expanded command kinds; XML covers vertex fields, command packing, render modes,
owned path strings and segmented pointers. Wrong-reader/format and truncated
matrix failures are checked. Outputs also match for all 19,167 applicable records
from the matching official archives: 9,843 display lists, 9,221 textures and 103
matrices. No archive vertex entries were encountered; the explicit fixtures cover
that factory. Test-only fixture framing never enters the runtime asset path.

Receipts: scratch/fast-resources-xdk/{manifest.json,verification.json,xdk/build.json}.
Native objects are verified PowerPC COFF 0x1f2. This is compilation and host
behavior evidence; actual LUS mounting, Xbox rendering and gameplay remain open.
