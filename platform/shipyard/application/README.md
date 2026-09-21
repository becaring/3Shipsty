# Genuine application startup boundary

`prepare_application.py` retains the complete locked 9.2.3 `OTRGlobals.cpp` and
the complete `OTRGlobals` class. `--build` attempts the whole translation unit
and records its real result; it currently **fails in unresolved modern header
dependencies**. Neither the application nor its startup has run in Xenia.

`test_application.py` passes five checks. The complete class still compiles to
an 80-byte Xenon layout. Eight exact startup/audio methods compile against the
real current O2rArchive, BinaryReader, Context, game declarations and the owned
native services. This is explicitly a **compile probe**, not a production source
fragment or completed OTRGlobals coverage. No replacement providers link.

## Adaptations

- Eight font pointer defaults move to the original constructor initializer
  list. Unused application-header includes become genuine forward declarations;
  implementation includes retain the full service dependencies (A).
- Xbox `RunExtract` validates the actual `soh.o2r`, `oot.o2r` and `oot-mq.o2r`
  through the original DetectOTRVersion/ReadPortVersionFromOTR/VerifyArchiveVersion
  functions. The port archive must match major/minor/patch; present game archives
  must match the application major and at least one must exist. The original
  archive version-marker byte selects BinaryReader endianness unchanged (F).
  Failure uses the existing native error dialog and exits. Archive generation
  stays on the PC; Xbox does not delete old archives or require extractor assets.
  Successful preflight retains creation of the modern mod folder. The original
  Initialize method still owns mounting archives and registering every resource
  factory. Host extraction source stays behind the explicit platform guard (I).
- Runtime filesystem spelling selects the existing native boundary. IsSubpath
  and temporary extraction permission checks are PC-only (E).
- The full OTRAudio state uses the existing native mutex, condition variable
  and joining thread classes. The real audio worker, buffer generation, sample
  counts, resource precache, signals and join remain. The unlocked outer read of
  `audio.running` becomes an unconditional loop: its existing check while holding
  the mutex remains the sole exit decision. This removes an upstream data race
  without changing buffer processing (D). Native audio execution remains untested.
- Shutdown joins the existing save worker, then audio, then stops the real
  libultra timers before Context/game queue storage can be destroyed (D).
- The complete SaveStateMgr declaration preserves every member/method. Scoped
  enums use the existing typed compatibility representation, deleted copies
  become private declarations, and its mutex selects native storage (A/B/D).
  SaveStateMgr implementation and SaveManager are separate work.

All platform primitives are generic Shipyard work; the archive acceptance policy,
source projection and application call ordering are 3Shipsty-specific. There is
no alternate startup loop, renderer, UI, resource manager or save implementation.

## Evidence and remaining integration

Run from the owned root:

```
C:/Python313/python.exe -B tools/shipyard/test_application.py
C:/Python313/python.exe -B tools/shipyard/prepare_application.py --build
```

The second command is intentionally honest about the current failure. Its recipe
and diagnostics are `scratch/application-xdk/xdk/build.json` and `OTRGlobals.log`.
Do not add either declaration/boundary probe to the production manifest.

The host contract executes the original VerifyArchiveVersion body for all 65,536
major values and all 32 preflight availability/version conditions. Native probe
objects are PPC COFF and retain real O2rArchive references with no Extractor
references. The test also verifies the complete function inventory, unchanged
InitOTR/resource-registration bodies (apart from filesystem spelling), unchanged
version-reader body, deterministic generation and teardown order.

Full-TU compilation currently reaches unprojected settings.h and its relative
randomizer header closure, first failing on __VA_OPT__ in randomizerEnums. The
canonical randomizer value projection already solves that enum syntax, but
settings.h/Option/OptionGroup still need their complete paired declarations and
constructor defaults; merely routing one include does not finish those classes.
The full SohInputEditorWindow, SohGui/menu/trackers, SaveManager and network class
headers must likewise be consumed from their canonical projections, with every
real member preserved. Subsequent OTRGlobals source work includes aggregate/map
initializers, native error-box forwarding, timing/chrono, platform speech choice,
and actual file-drop JSON/import behavior. No broad feature includes were removed
to conceal those dependencies.

Start XNet before archive/RNG consumers and end it only after their workers have
joined. The primary donor's platform.cpp lines 38-46/436-439 establish that
XNetRandom depends on XNetStartup/XNetCleanup. The application entrypoint and
save/storage lifetime still need to establish that final platform ownership.
