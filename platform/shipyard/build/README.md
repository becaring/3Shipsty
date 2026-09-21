# Deterministic Xbox source/project inventory

Current integration (2026-09-21): all 1,094 application TUs are selected. Sixteen
desktop/mobile backends have explicit Xbox replacement decisions; unchanged
upstream stox.cpp is included directly. The historical checkpoints below retain
their original scope. The complete build and genuine link run through:

```powershell
C:/Python313/python.exe -B tools/shipyard/build_xdk_project.py
C:/Python313/python.exe -B tools/shipyard/link_xdk_application.py
```

The build wrapper invokes the ordinary generated MSBuild compile target and
verifies current source hashes and PPC object headers/hashes only on success.
It also records the owned headers actually consumed in MSBuild's compiler read
log; linking rejects changed headers or a changed project configuration.
The link refuses missing application/platform decisions or stale verified inputs.
All application objects are linked directly to preserve registration initializers;
LUS/platform/dependencies use ordinary Shipyard.lib archive extraction. This
retains the pinned application's ownership of the five os_pi/os_cache overlap
symbols. No whole-archive, unresolved-symbol override, replacement entry point
or old game object is supplied. The actual generated modern main.c owns startup.

Canonical header-provider rules place the complete Window and Gui declarations
ahead of earlier standalone-stage copies. The only observed differences were
nonvirtual constructor helpers, but using one declaration avoids divergent class
definitions across the genuine combined application.

XDK link and ImageXex produce 3Shipsty.exe/.map/.pdb/.xex in
scratch/link-integration only when their real tools succeed. The development
title ID 0x534F4809 separates the modern target's storage namespace from the
private donor's 0x534F4804. The 4 MiB stack and XDK graphics/audio/network
libraries follow the working donor link configuration. Every command/exit is
recorded in link-verification.json. Artifact production is not execution proof.

The `build-metadata` recipe configures the actual pinned `soh/src/boot/build.c.in`
using version/team values parsed from the pinned root CMakeLists.txt. It supplies
the ten real build globals through a generated C translation unit, with no edit
to upstream. Classification I (CMake configuration outside the XDK build); this
generator is application-specific. Its only type substitution is libultra u16
to uint16_t. Build date uses SOURCE_DATE_EPOCH, otherwise the port commit's UTC
timestamp. Re-run `prepare_build_metadata.py` after creating a new checkpoint
before building a package so the displayed commit identifies that checkpoint.

The `crt` recipe provides the four genuinely missing C runtime functions using
two generic Shipyard sources; preserve its `/fp:strict` option and exclude its
host contract source. See `platform/shipyard/crt/README.md` for semantics and
evidence. These sources and configured metadata are ordinary production objects.

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
