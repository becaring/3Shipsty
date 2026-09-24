# Modern 3Shipsty Xbox build from source

The Modern source checkpoint, its Git submodules, and the separate Shipyard
checkout are the source authority. `platform-base.lock.json` selects Shipyard's
exact commit and byte manifest. `platform/shipyard/dependencies.lock.json` pins
the 16 external Git archives used by the Xbox generators. No files from the
SoH 4.0.5 tree are used.

On Windows with Git, Python 3.13, Visual Studio 2022 host C++ tools, and Xbox
360 SDK 21256.3, place Shipyard as a sibling checkout or set
`XBOX360_PLATFORM_BASE` to its absolute path. Run from the Modern repository
root in PowerShell:

```powershell
git submodule update --init --recursive
& C:/Python313/python.exe -m pip install --target scratch/python-tools -r tools/shipyard/requirements.txt
& C:/Python313/python.exe -B tools/shipyard/setup_dependencies.py
& C:/Python313/python.exe -B tools/shipyard/regenerate_all.py --empty-owned-outputs
& C:/Python313/python.exe -B tools/shipyard/test_xdk_project.py
& C:/Python313/python.exe -B tools/shipyard/build_xdk_project.py --jobs 8
& C:/Python313/python.exe -B tools/shipyard/link_xdk_application.py
```

The dependency setup script accepts `--verify-only` for an existing prepared
checkout. Its receipts verify the pinned Git archives and every copied byte.
The regeneration driver has an inspectable `--list` mode. Its empty-output mode
first preserves the old XEX and receipts under `scratch/final-preclean/`, then
removes only directories selected by the canonical subsystem inventory. It
recreates every selected compiler recipe through its owning script and records
each exit and log hash under `scratch/final-regeneration/`. It leaves dependency
snapshots and historical checkpoints intact.

For a local source correction, keep the generated outputs and PPC objects.
Update the affected source locks, run the owning `prepare_*.py` generator and
any consumers of its projected headers, then run `test_xdk_project.py`,
`build_xdk_project.py --jobs 8`, and `link_xdk_application.py`. The project
generator writes unchanged project bytes only once, so MSBuild can reuse
objects whose source and header inputs have not changed. For example, a change
to `soh/soh/SohGui/UIWidgets.hpp` affects the `soh-ui`, `soh-menus`,
`soh-input-editor`, `gameplay-features`, and `application-extras` projections;
run those owners and their focused tests before the incremental application
build. Do the empty-output command above once after the source is stable for
the final reproducibility proof, not after each edit.

If a generation run is interrupted with the same source revision, use
`regenerate_all.py --resume`. It verifies the completed stage order, options,
and log hashes, then continues without deleting generated outputs. It rejects
a changed source revision; after a source correction, use the affected owner
generators as described above.

`build_xdk_project.py` records the source, header, PPC object, and shard proof
in `scratch/project-xdk/complete-application-verification.json`. The link
driver refuses stale inputs and records archive/link/ImageXex commands and the
new XEX at `scratch/link-integration/3Shipsty.xex`. The current candidate's
exact totals and hashes belong in `porting/SHIPYARD_FINAL_STATUS.md`; a prior
checkpoint's XEX is never accepted as final proof.
