# Complete modern dungeon and trial implementation

The complete pinned 9.2.3 `dungeon.cpp` (35 definitions) and `trial.cpp`
(19 definitions) compile into native PPC objects. No methods, trial definitions,
dungeon definitions, vanilla/MQ key counts, JSON behavior, placement operations,
or class fields are removed.

```
C:/Python313/python.exe -B tools/shipyard/prepare_randomizer_dungeons.py --build
C:/Python313/python.exe -B tools/shipyard/test_randomizer_dungeons.py
```

Use `prepare_randomizer_dungeons.includes()` before existing include paths and
link `scratch/randomizer-dungeons-xdk/xdk/dungeon.obj` and `trial.obj`.
Build commands, source hashes, and validated PPC COFF hashes are in
`xdk/build.json`; contract evidence is in `verification.json`.

The canonical complete DungeonInfo/Dungeons declaration remains in
randomizer-logic-xdk. The canonical complete TrialInfo/Trials declaration remains
in randomizer-xdk. This provider supplies no duplicate class definitions and
does not regenerate either dependency. Its actual constructors include the same
relocated defaults as those declarations require. Any earlier constructor-only
object for these classes must not be linked alongside these full objects.

## Narrow adaptations

* A: Move original DungeonInfo and TrialInfo member defaults into their actual
  constructors. Preserve upstream fields that remain indeterminate, including
  default DungeonInfo area/MQ setting and default TrialInfo name/trial keys.
* A: Replace out-of-class defaulted destructor definitions with equivalent empty
  bodies; their existing user-provided status is unchanged. Lower range loops
  with the shared iterator/reference helper and spell three empty containers in
  the syntax accepted by XDK.
* A/B: Extract the complete genuine `erase_if` and `FilterFromPool` templates
  used by dungeon placement into a named generated `pool_filter.h`. The latter
  still uses actual `std::copy_if` and optional erase/remove, retaining stable
  ordering and two predicate passes when erasing. Only vector begin/end lookup
  and the empty vector declaration change. The unrelated variadic fold helper
  in the original pool header is outside this dependency boundary.
* I: Include actual resource-range helpers, scene enums, and algorithms directly.

These are 3Shipsty projections using generic Shipyard compiler compatibility.
There are no replacement classes, static tables, application services, or data
formats. No endian conversions are added; native state stays native, and actual
JSON parsing remains the existing upstream-compatible runtime boundary.

## Evidence and remaining runtime coverage

Both original and projected host tests execute 48 actual methods against the
real classes and the exact six-entry StaticData trial table extracted from
upstream. They compare all 12 dungeon definitions and key counts, all 65,536
scene IDs, 4,096 MQ masks through real JSON parsing, all 64 trial-state masks,
list pointer identity, copied location vectors, and constructor defaults.
They also test the actual pool algorithms' order, duplicate preservation,
optional erasure, and number of predicate calls. Original JSON uses nlohmann;
projected JSON links the genuine Shipyard JSON implementation.

Current host MSVC `std::find` requires iterator metadata that the XDK JSON
iterator does not declare. The host-only traits header describes that existing
iterator's operations; it adds no iterator implementation or fake behavior and
does not alter native compilation or the shared JSON provider. A future shared
JSON cleanup can supply those metadata centrally.

Four actual vanilla-placement methods and TrialInfo::GetName/Trials::ParseJson
compile in their full native units but are not host executed here: their real
Context, StaticData location/hint tables, and localized hint/message providers
remain integration dependencies. No functions are supplied to fake those
services. This is native compilation and bounded host execution evidence,
not Xenia gameplay or hardware validation.
