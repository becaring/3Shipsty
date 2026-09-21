# Genuine application startup

The complete pinned 9.2.3 `OTRGlobals.cpp` now compiles with XDK. Its actual
constructor, initialization, resource registration, audio worker, graphics and
game bridges remain in the production translation unit. There is no alternate
application or replacement service. Compilation is not startup execution;
linking, partial-initialization cleanup and Xenia validation remain open.

## Narrow adaptations

- A/B: retain all fields and move eight font defaults into the actual constructor.
  Container initializer lists become typed arrays/range constructors or builders;
  both item maps preserve every row and first-insert duplicate behavior. Explicit
  casts replace unsupported template ADL; scoped enums use the canonical wrappers.
  Designated AudioSettings initialization retains all defaults, including Stereo.
  UTF-16 character literals become numeric codepoints. JSON iteration still uses
  the real flattened DOM, with iterator key/value references replacing bindings.
- C/E/F: Xbox RunExtract invokes the original archive/version readers with the
  same acceptance policy. Extraction and permission probes stay on the PC.
  Native errors use the Xbox dialog and actual StringToU16 conversion. Runtime
  files use the existing native filesystem; timestamp uses the existing chrono
  boundary. No archive layout, byte-order convention or resource registration is
  replaced. Accepted archives are mounted by the actual Initialize method.
- C/D/E: InitOTR starts XNet before RNG/resource consumers and mounts the selected
  XContent container before Context chooses writable paths. Configuration, saves
  and mod paths resolve under that container; packaged archives remain under
  `game:`. Early device-selector behavior still needs native execution.
- D: real audio processing uses native joining threads, mutexes and condition
  variables. The worker's running predicate is read only under its existing
  lock, fixing the upstream unlocked outer read. Normal teardown joins the real
  randomizer generation worker, disables active remote workers, joins audio,
  stops libultra timers, drains/deletes the
  real SaveManager, destroys the concrete Xbox speech worker/voices and GUI ownership, drains resource and detached codec
  work while Context remains strong, releases Context, closes storage, then XNet.
  ResourceManager and detached drain contracts are documented separately.
  OTRAudio.h now declares one externally shared state, defined by OTRGlobals.cpp.
  Its original header-local static gave save states a different mutex from the
  audio worker. All members and static zero initialization remain; a two-source
  native-primitive host check reproduces the original defect and verifies shared
  identity and exclusion after projection.
- A/I: canonical complete Item, options, SaveManager, AudioCollection, network,
  input editor and application-window headers replace the corresponding original
  headers in include search order. No feature class or state is elided. The full
  SaveStateMgr declaration is retained; implementation has its own provider.

Generic platform primitives belong to Shipyard. Application acceptance policy,
source lowering and startup ordering belong to 3Shipsty. No data byteswap is
introduced here; the original archive marker selects BinaryReader endianness.

## Verification

Run from the owned root:

```
C:/Python313/python.exe -B tools/shipyard/test_application.py
C:/Python313/python.exe -B tools/shipyard/test_application_values.py
C:/Python313/python.exe -B tools/shipyard/test_application_audio_owner.py
C:/Python313/python.exe -B tools/shipyard/prepare_application.py --build
```

The five structural/boundary checks retain the complete function inventory,
actual resource factory expressions and application initializer order. Original
version checking covers all 65,536 major values and 32 archive combinations.
Declaration and eight-method probes are excluded from production coverage.

Value comparisons execute original/projected controller masks, all 15 accepted
ROM hashes, audio defaults, all 65,536 item IDs, 63,487 non-surrogate BMP characters
through normal/hiragana printing, and supplementary UTF-16 conversions. The same
projected contract compiles as native PPC. Full source/object hashes and exact
commands are recorded in `scratch/application-xdk/xdk/build.json`.

## Remaining execution work

Remaining application implementations must resolve real link dependencies.
Partial-initialization failures must drain admitted work while Context is still
strong. `_XBOX` selects the real XboxSpeechSynthesizer before `_WIN32`; its
concrete destruction is required because upstream's base destructor is not
virtual. Speech engine/backend and data evidence are in ../speech/README.md;
audible target execution remains unverified. Storage selection, UI rendering,
controller routing, audio and real resource mounting have not executed in Xenia.
