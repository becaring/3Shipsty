# Deterministic Xbox source/project inventory

`tools/shipyard/generate_xdk_project.py` emits an ordinary inspectable Visual
Studio/XDK project and a complete source coverage manifest below
`scratch/project-xdk`. It does not run projection scripts, copy donor sources,
execute extraction, or reuse existing object files. The generated project compiles
the real production source files again.

`subsystems.json` is the declarative input: one list of native compiler recipe
reports per subsystem, an explicit probe exclusion list, two native logging
support sources, and unresolved integration gates. Reports supply source selections
and ordered include/definition/options lists. They are **not** treated as evidence
that currently edited sources or headers have already compiled. Every emitted
source has `requires_fresh_build: true`; `prior_compile_exit` is historical only.
This distinction matters while source projections continue changing.

Run from `D:\Projects\3Shipsty9.x`:

```powershell
C:/Python313/python.exe -B tools/shipyard/generate_xdk_project.py
C:/Python313/python.exe -B tools/shipyard/test_xdk_project.py
```

The generated `manifest.json` contains every source from the pinned upstream
inventory, including all **1,094 application translation units: 696 C and 398
C++**. Each is selected, pending, or excluded with its upstream selection reason.
Application sources are never excluded merely because they lack a projection.
Host extraction tools and upstream CMake exclusions stay explicit. LUS sources
and desktop speech backends without a selected production recipe stay pending
until an explicit platform decision is made. A newly added application source
automatically appears as pending; removing a recipe makes its old source pending.

Each production source has its current SHA-256, upstream source identity where
applicable, originating compiler report, subsystem, exact ordered compiler
options, and a stable unique object name based on its full relative path. Partial
extracted functions are labeled as fragments, without claiming their entire
upstream translation unit is ported. Thus
`Json.cpp` and `json.cpp` cannot silently overwrite each other on Windows.
No timestamp or absolute checkout location is embedded in generated recipe
options. Inputs that use generated preprocessed C are identified separately from
the original application source; no C source is compiled as C++.

Only XDK `cl.exe /c` recipes are accepted. Test sources and ABI probes are
explicitly excluded. The early isolated `cc_features.cpp` is also excluded:
the complete current interpreter already defines the same decoder function,
so compiling both into the application would create duplicate ownership and
a duplicate symbol. The shader lowerer remains a required production source.
All C++ entries receive `/TP /EHsc /GR /MT`; C receives
`/TC /MT`. This deliberately repairs older isolated reports that used the XDK's
RTTI-off or implicit runtime defaults. Include ordering remains per subsystem.
The declarative target definition policies additionally enforce the pinned
release's shared button type, GBI microcode, MPQ support, release/logging defaults,
and LUS graphics disassembler definition. Missing standalone recipe definitions
are listed per source under `target_definition_corrections`. Ordinary source
recipes receive the missing definitions in the emitted project. For already
preprocessed C, defining macros afterwards cannot restore discarded branches:
these corrections instead say `regenerate_preprocessed_source` and remain an
integration requirement. The generator does not pretend this is fixed by adding
a late compiler switch. Desktop OpenGL/DX11 enables remain Xbox platform backend
decisions, not injected desktop dependencies.

In particular, the stable root enables `GFX_DEBUG_DISASSEMBLER`; prior isolated
GUI compilation omitted it. The full GUI recipe now rebuilds with that feature
and the exact libgfxd dependency; all seven gfxd C TUs are selected explicitly.
A previously successful isolated build does not establish that every release
definition was present; per-source correction metadata keeps that distinction.
LUS HEAD must match the stable release gitlink. The pinned SoH CMake selection
is verified by `source_inventory.py` before the project can be emitted.

For a bounded compile iteration, select one group:

```powershell
C:/Python313/python.exe -B tools/shipyard/generate_xdk_project.py --subsystem binary
& 'C:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe' `
  scratch/project-xdk/ShipyardCompile.vcxproj /t:ClCompile `
  /p:Configuration=Release '/p:Platform=Xbox 360' /nologo /verbosity:minimal
```

`--subsystem` changes only the emitted compile items; `manifest.json` always
contains the complete project coverage. Omitting it emits every available
production recipe. Run the relevant existing `prepare_*.py --build` or native
component check first when adding translations, then rerun this generator. A
missing subsystem report is recorded in `missing_subsystem_recipes`, never
silently inferred to have no sources. The optional scene report is incorporated
when available. Generating a project does not certify header ABI compatibility
between components; that remains an explicit integration gate.

The project uses the donor-proven Xbox platform toolset `2010-01`. Default
`Build`, `Rebuild`, `Lib`, and `Link` are guarded: it cannot produce a partial
library or executable advertised as the genuine application. `/t:ClCompile`
is the supported target. `--require-complete` emits the coverage report and
returns exit code 2 while the final application remains incomplete. Enabling
an executable is a future explicit integration change after pending source,
startup, ABI, storage, and link dependencies are actually resolved; there is no
override switch that mislabels partial coverage as ready.

## Validation

```powershell
C:/Python313/python.exe -B tools/shipyard/test_xdk_project.py --native
```

Six automated checks cover deterministic XML, complete application inventory,
source addition/removal visibility, per-language options, test exclusion,
collision-safe object naming, SDK path quoting, pinned target definitions,
preprocessed C boundaries, and the executable guard. The
native option builds **seven genuine production translation units** through the
generated project: four complete current binary classes, two native logging
support files, and preprocessed current `sys_math.c`. It verifies Xenon PPC BE
COFF machine IDs and confirms that `Build` is rejected before library output.
Evidence is written to `scratch/project-xdk/verification.json` and
`native-validation.log`. MSBuild may require access to its installed per-user
SDK registration, beyond a restricted shell sandbox.

These checks passed on 2026-09-20. The initial all-group snapshot contains
1,425 production compile items, including 773 selected application TUs and 321
pending application C++ TUs. These are recipe coverage counts, not an engineering
percentage, full-project compilation claim, link claim, or runtime validation.
The generated manifest is authoritative as additional projections are completed.

Remaining work outside this generator includes reviewing unresolved desktop
backend equivalents, testing the complete combined build with shared ABI/header
ownership, adding the genuine application entry/link target, and validating the
real application in Xenia. No XEX or runtime artifact is produced here.
