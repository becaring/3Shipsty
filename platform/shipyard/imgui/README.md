# Current ImGui XDK projection

The complete five core TUs, including the demo, come from the exact release
dependency v1.91.9b-docking, commit 4806a1924ff6181180bf5e4b8b79ab4394118875.
The generator checks that snapshot and the actual current LUS patch before
writing. It applies the patch's math operators and pointer ImTextureID
configuration. The patch's Metal/SDL-only changes do not alter Xbox core TUs;
the original patch stays intact in the pinned LUS tree.

Generic compiler techniques are adapted from Smash360 with donor hashes in
provenance.json. The owned transformations preserve enum definitions, move
member defaults into constructors, turn actual captureless callbacks into
static methods, lower ranges while evaluating begin/end once, and explicitly
construct the handful of modern aggregate expressions XDK cannot parse.
Unknown callback shapes and initialization patterns are rejected.

No modern SoH GUI source or menu has been replaced. Disabling ImGui's desktop
Win32 clipboard/IME and shell functions on Xbox is a platform boundary; the
real native platform backend must supply available clipboard/keyboard/link
behavior. Core widgets, tables, navigation, docking and demo remain compiled.
Native renderer, input, and window integration are separate provider contracts.

Generate and verify from the repository root:

```powershell
python -B tools/shipyard/setup_dependencies.py
python -B tools/shipyard/prepare_imgui.py --raw-probe
python -B tools/shipyard/prepare_imgui.py --compile
python -B tools/shipyard/tests/test_imgui_generation.py
python -B tools/shipyard/tests/test_imgui.py
```

The raw probe is expected to fail. The corrected projection compiles all five
real TUs to PPC BE objects. Host original/projected execution compares exact
font-atlas bytes, vertices, indices, clipping and command offsets over eight
frames exercising actual core/demo, table, slider, menu and navigation APIs.
This is a dependency test; it is not a replacement application or visible
modern SoH UI acceptance. Output/evidence: scratch/imgui-xdk.

Host parser versions are in tools/shipyard/requirements.txt. Current acquired
parser byte hashes and owned helper normalized hashes are locked in
source-lock.json. Compiler diagnostics name generated files; the manifest
records the originating dependency and every generated hash. No source map
claims an inserted compiler construct is an unchanged upstream line.
