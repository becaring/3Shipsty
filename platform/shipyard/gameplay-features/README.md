# Complete gameplay feature batch

`inventory.json` records the exact 89 pending application translation units
selected from the project manifest for this batch. `sources.lock.json` pins the
complete original source and the actual WeirdAnimation header. All upstream and
reference source remains unchanged. The generator emits complete translation
units; it does not replace their game rules, hooks, callbacks or registration.

## Reproduction and integration

```powershell
python -B tools/shipyard/prepare_gameplay_features.py --build
python -B tools/shipyard/test_gameplay_features.py
```

`--build --failed` rebuilds failed units and any unit whose generated source no
longer matches its prior compilation. It preserves successful unchanged records.
Compilation uses two compiler processes without regenerating dependencies. `--only <path-fragment>` is available for diagnosis.

Use all 89 source/object records in `scratch/gameplay-features-xdk/xdk/build.json`
with their exact native command lines. Prepend `prepare_gameplay_features.includes()`
to the existing application recipe. Object names contain path hashes, avoiding
collisions. This directory also contains compiler logs and `errors.json`.
`verification.json` records source/object hashes, complete source inventories
and original/projected host results. `manifest.json` records generator/helper
hashes and deterministic generated source hashes.

The only newly supplied application header is the complete WeirdAnimation class
at its original relative path beneath `scratch/gameplay-features-xdk/generated`.
Other declarations come from existing canonical providers. In particular,
SaveManager uses save-storage's full header; ObjectExtension, menu/widget,
custom-message, resource, randomizer, notification and console classes are the
existing application classes. There is no new startup hook. Link these objects
through the real application so their existing ShipInit/MenuInit registrations
execute.

## Compatibility decisions

| Class | Narrow adaptation | Ownership |
|---|---|---|
| A: language | Scope-preserving range/binding and if-initializer lowering; const integral constants; full aggregate values; explicit lambda return types | Generic Shipyard compiler work |
| A: language | Preserve default members in CustomStalfosPairFightData, SunlightArrowData and CamDataBackup constructors without changing any field | Generated application source |
| A/B: containers | Exact ordered rows construct the original maps, sets, daytime actor vectors and restoration animation vectors | Generic compiler technique, application data preserved |
| A: registration | Reuse canonical ShipInit and GameInteractor source-location lowering; protect hook invocations inside preprocessor macro bodies from inserted line directives | Generic Shipyard compiler work |
| B: library | Existing optional provider stores the real restoration buffer; unsigned char supplies the byte-only storage operations actually used by std::byte | Generic library compatibility |
| B: library | Preserve optional emplace's reset/construction boundary for its empty vector; preserve separate copied buffers | Generated application source |
| B: library | Existing shared-pointer aliasing cast preserves console ownership; explicit string temporaries satisfy XDK rvalue binding | Generic Shipyard compatibility |
| B: math | Fmax wrapper preserves finite, infinity and NaN behavior used by enemy health scaling | Generic Shipyard compatibility |
| B/F: JSON | Generate the original warp fields' JSON encode/decode functions from the two upstream macros, through the existing JSON provider | Narrow application serialization boundary |
| H: compiler | Explicit known field types avoid XDK's erroneous member-decltype binding during JSON get; global Gfx values avoid its nested static-initializer lambda failure | Narrow codegen workaround |
| A/G: rendering | Construct actual Gfx command values before passing them through the existing resource patch API; retain command macros and arguments | Generic compiler boundary |
| I: build | Explicit canonical includes replace reliance on desktop umbrella/transitive includes | Generic dependency hygiene |

All sources remain complete. The source projector retains the upstream
`overrideBlueWarpDestinations` identifier across the shared older override-token
lowerer. It removes the redundant `GameInteractor::` hook argument qualification
only where the existing hook macro itself supplies that scope. It preserves
UTF-8 string bytes explicitly for the XDK source code page.

Warp JSON retains `entranceId`, `roomNum`, `pos.{x,y,z}`, `rotY` and `bootToPoint`.
It uses checked `.at()` reads, preserves missing-field/type errors, builds the
replacement map before assignment, and uses the normal Config load/save path.
No custom save format, alternate config store or replacement game state exists.

## Endian and validation boundaries

Gfx values are runtime-native commands passed to the unchanged renderer/resource
interfaces. Restoration animation buffers copy the original resource manager's
native resource data and retain 16-byte padding and original frame arithmetic.
The byte-storage compatibility change introduces no conversion or byte swap.
Warp data is ordinary JSON/config data read using the existing JSON backend.

Host tests compile original and projected code/data against actual types. They
compare all 65,536 fixed-camera type values, four scene/skybox sets, the full enemy
tables, six graveyard geometry patches, all 12 daytime actors across seven scene
groups, and five restoration definitions including neighbor order, defaults,
optional state and independent copied buffer ownership. The math check compares
2,049 finite enemy-health inputs and special values. Warp tests compare 256
complete values and serialized JSON, including signed fields, coordinates,
booleans, empty maps and missing/type errors. Full source audits retain function,
hook, CVar, Gfx and string inventories.

These checks do not execute an alternate gameplay path or substitute any game
service. They do not prove game-frame execution, actor behavior, GPU rendering,
audio, saves or Xbox hardware behavior. Those require the integrated application
and subsequent Xenia/hardware validation.
