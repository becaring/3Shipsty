# Xbox source and project inventory

For prerequisites and the complete build sequence, see
[build from source](BUILD_FROM_SOURCE.md) and
[development](../../../docs/DEVELOPMENT.md).

`subsystems.json` selects native compiler recipe reports, production sources,
platform decisions, probe exclusions, and integration gates.
`generate_xdk_project.py` emits the source manifest and an inspectable XDK
project under `scratch/project-xdk`. It does not run source projections.

## Source selection

The manifest covers the pinned application's 1,094 translation units and the
selected platform/dependency sources. Each input is selected, pending, or
excluded with an explicit reason. New application inputs and missing recipes
remain visible as pending; absence of a recipe never implies absence of work.

Each selected source records its hash, upstream identity, subsystem, originating
recipe, ordered compiler options, and a collision-safe object name. Probe and
test sources stay outside production selection. Source locks and the pinned
CMake inventory protect the release's application and submodule identities.

C sources use `/TC /MT`; C++ sources use `/TP /EHsc /GR /MT`. Definition policies
retain the release's button type, microcode, MPQ support, and logging defaults.
Already-preprocessed C must be regenerated when a missing definition affects
preprocessing; adding the definition later cannot restore discarded branches.
Precise floating-point behavior is retained, including the CRT provider's
stricter options.

## Compilation and linking

`build_xdk_project.py --jobs 8` drives independent XDK compiler shards and
verifies their source/header/object receipts. `--jobs` accepts 1–32 workers.
The generated project's supported target is `ClCompile`; default build/link
targets are guarded against accidental partial application output.

`link_xdk_application.py` requires current verified inputs. Application objects
are linked directly to retain registration initializers; platform and dependency
objects use ordinary archive extraction. The generated modern `main.c` owns
startup. There is no unresolved-symbol suppression or alternate entry point.

Successful native linking and ImageXex write `3Shipsty.exe`, `.map`, `.pdb`, and
`.xex` under `scratch/link-integration`. The development title ID is `0x534F4809`
and the stack is 4 MiB. These outputs establish build results, not execution.

Build metadata comes from the pinned `soh/src/boot/build.c.in` and root CMake
version/team values. It embeds the current Git revision. Its date uses
`SOURCE_DATE_EPOCH`, otherwise the commit's UTC timestamp. Regenerate metadata
and recompile after changing the source revision before packaging.

## Verification

```powershell
python -B tools/shipyard/generate_xdk_project.py
python -B tools/shipyard/test_xdk_project.py
python -B tools/shipyard/test_xdk_project.py --native
```

Contracts cover deterministic XML, complete application inventory, source
addition/removal, per-language options, test exclusion, object-name collisions,
SDK quoting, target definitions, preprocessed-source boundaries, and the compile
project guard. Native checks compile selected real production units and inspect
PowerPC COFF headers. Receipts are written beneath `scratch/project-xdk`.

`--subsystem` limits emitted compile items while retaining full manifest
coverage. Regenerate the full project before the complete build. `--require-complete`
reports unresolved integration gates through its exit status; inspect the
manifest rather than treating project generation as runtime validation.
