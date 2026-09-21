# Upstream baseline

Verified 2026-09-20 against the official GitHub latest-release redirect and the
fetched Git objects. Application authority is **Ackbar Delta 9.2.3**.

| Repository | URL | Pinned commit |
| --- | --- | --- |
| Shipwright | https://github.com/HarbourMasters/Shipwright | `cb71e22a79bc5d1f688fa881795bbd93094895fc` (tag `9.2.3`) |
| libultraship | https://github.com/kenix3/libultraship.git | `fdcaf6336776d24a6408d016b0a52243f108f250` |
| ZAPDTR | https://github.com/harbourmasters/ZAPDTR | `ee3397a365c5f350a60538c88f0643f155944836` |
| OTRExporter | https://github.com/harbourmasters/OTRExporter | `32e088e28c8cdd055d4bb8f3f219d33ad37963f3` |
| Torch | Not a dependency of this release | Not applicable; do not introduce BattleShip's extraction pipeline |

Release: https://github.com/HarbourMasters/Shipwright/releases/tag/9.2.3
Latest endpoint redirected to this release. The release page identifies it as
Latest and displays `cb71e22`. Local `git rev-parse HEAD` agrees with the full
commit above. The root Git tree object is
`e11beddc05e744efeb8b991f6d261965093315a4`.

Initialization: `git clone --branch 9.2.3 --single-branch
https://github.com/HarbourMasters/Shipwright.git .`, followed by
`git submodule update --init --recursive`. All three submodules were checked out
at their gitlinks, with no nested submodules reported. Before adding port files,
root and all three submodules returned empty `git status --porcelain=v1`.
Port branch: `shipyard/xbox360-9.2.3`. No develop checkout is used.

Submodule tree objects: LUS `67d22034b8f9fd1d0076d2e50e4ac9cf981c0ea4`;
OTRExporter `25f350c37d418a73dd4e8ca7ecfaf49394439a4b`;
ZAPDTR `769ae9f7fba721543790a418e066065e0c8a6570`.

The release requests C++20 and C23. Its runtime consumes `soh.o2r`, `oot.o2r`
and optionally `oot-mq.o2r`, and enables MPQ compatibility. Extraction belongs
on the development PC. The pinned CMake recipes select additional dependencies
through FetchContent and find_package; those are not Git submodules. Their
resolved source hashes must be recorded before incorporation into the Xbox build.

Explicit LUS FetchContent selections: ImGui `v1.91.9b-docking` plus the pinned
LUS patch; StormLib `v9.25` plus the pinned LUS patch; libgfxd
`008f73dca8ebc9151b205959b17773a19c5bd0da`; thread-pool `v4.1.0`;
prism `bbcbc7e3f890a5806b579361e7aa0336acd547e7`; stb_image from
`0bc88af4de5fb022db643c2d8e549a0927749354`.

Reference trees are read-only. SoH360 supplies platform mechanisms, never modern
application policy. Smash360 supplies audited generic platform/compiler lessons,
never its game behavior. Reference file hashes are required for any copied input.

Additional resolved dependencies are recorded in
`platform/shipyard/dependencies.lock.json`: libzip, zlib, tinyxml2, exact current
Prism and ImGui. Thread-pool provenance is under
`platform/shipyard/thread-pool/source-provenance.json`; JSON official/donor
hashes are under `platform/shipyard/json/source-authority.json`. Logging's
explicit spdlog/fmt selections are recorded in its separate dependency-lock.
These added pins do not alter any release gitlink. PC asset provenance and
9.2.3 archive hashes are in `porting/ASSET_BASELINE.md`.
