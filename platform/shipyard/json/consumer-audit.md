# JSON compiler boundary: modern 9.2.3 consumer audit

The owned dependency is unmodified nlohmann v3.12.0, commit
`55f93686c01528224f448c19128836e7df245f72`. Its 46 headers and MIT license were
copied after checking the read-only reference checkout's commit and clean state.
`source-authority.json` records every official input hash, donor file/hash,
owned implementation hash, and transforms. This version matches the fallback
in current `libultraship/CMake/dependencies/android.cmake:22` and `ios.cmake:21`.
The Windows vcpkg recipe requests JSON without an exact version; common.cmake
does not select JSON.

The backend is generic compiler-library code carried from
`D:/Projects/Smash360/platform/xbox360/cpp-compat/json`; no Smash game semantics
are included. Its lazy named object/array storage derives from the SoH360
save_json implementation, but this does not import that game's save model.
The scanner and floating formatting are generated from the complete pinned
`detail/input/lexer.hpp` and `detail/conversions/to_chars.hpp`. Only syntax,
XDK CRT names, and namespace isolation are lowered. The DOM driver, pointer
handling, quoting, ownership and API adapter are an explicit bounded backend,
not the upstream generic basic_json class.

## Confirmed modern requirements

Paths in this table are relative to the current checkout. Every modern file
remains untouched. `consumer-inventory.json` records hashes and lexical evidence
for 69 candidate files. It is an audit aid, not an AST/template-instantiation
closure: an include-only scan cannot prove all indirect/custom conversions.

| Current consumer | Reached JSON contract | Owned backend state |
|---|---|---|
| `libultraship/src/ship/config/Config.cpp`, `ConsoleVariable.cpp` | Stream parse, scalar/vector conversion, flatten/unflatten, object lookup, erase by name, emplace, explicit iteration_proxy types, dump | Generic contract differential passes; actual production class integration is separate |
| `libultraship/src/ship/resource/ResourceLoader.cpp:169`, `factory/JsonFactory.cpp:16`, `archive/Archive.cpp` | Parse strings and iterator ranges; scalar metadata; comments; JSON value ownership | API carried; actual resource consumer integration is separate |
| `soh/soh/SaveManager.h:113-144` | SaveData/LoadData template assignments, push_back, get_to, missing-field/short-array defaults | Exact method bodies extracted and hash-checked; scalar/string/vector calls tested against official library in synthetic modern section structure |
| `soh/soh/SaveManager.cpp:481,499,507-509,551` | Stream extraction; find/erase(iterator); implicit s16; value(filenameLanguage,0) | Lookup, erase, narrow integers and value now implemented/tested. Stream extraction still absent |
| `soh/soh/Enhancements/randomizer/SeedContext.cpp:418-444` | File parse via operator>>, file-hash array index, item metadata, is_structured | Predicate and scalar/index conversions implemented; operator>> absent |
| `soh/soh/Enhancements/randomizer/Plandomizer.cpp:589-636` | items structured bindings, is_number, typed gets, parse_error | Predicate added; existing iterator/exception API retained. XDK lowering of surrounding source still needed |
| `soh/soh/Enhancements/randomizer/hint.cpp:375`, `hint.h:9`, `3drando/spoiler_log.cpp:30,105,117`, `SeedContext.cpp:449` | Insertion-ordered JSON type; ordered_json references/returns; initializer-list object construction; ordered nested containers and vectors | Not implemented. Aliasing ordered_json to sorted-map json would change ordering and is deliberately rejected |
| `soh/soh/Enhancements/Presets/Presets.cpp:114` | Recursive update(object,true) preserves existing nested object fields | Added following pinned json.hpp:3434-3488; replacement, merge, conflicting scalar/object errors, null conversion and self-update tested |
| `soh/soh/Enhancements/Warping.cpp:28-46` | NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE for Vec3f/WarpPoint; implicit map<string,WarpPoint> conversions both ways; find | Find supported. Macro/ADL and map conversion remain absent |
| `soh/soh/Enhancements/timesplits/TimeSplits.cpp:256-288,363-418` | Object initializer lists, scalar/string conversion, array iteration, file streams and erase by key | Initializer lists and JSON stream operators absent; scalar/array/name-erase contracts present |
| `soh/soh/Network/Anchor/JsonConversions.hpp:15-205` | ADL conversions for Color_RGB8, Vec3f, Vec3s, PosRot, AnchorClient, Inventory, SohStats, quest/randomizer structs and SaveContext; nested objects; C arrays; value(default) | Primitive value/get_to works; custom ADL, C-array get_to/construction and initializer-list contracts absent |
| `soh/soh/Network/Anchor/Packets/AllClientState.cpp:17`, `SetCheckStatus.cpp:41-42`, `TeleportTo.cpp:42`, `UpdateTeamState.cpp:135,230` | vector<AnchorClient>, enum gets, PosRot/SaveContext gets | Scalar vector mechanism exists but custom element conversion/enum contracts remain absent |

## Confirmed donor gaps and adaptation

Added only reusable API behavior: is_structured/is_number, value(default) with
string-literal defaults and upstream errors, mutable/const find, mutable-iterator
erase, recursive object update, and exact implicit signed/unsigned char, short,
long and 64-bit conversions. The type predicates and error IDs/messages follow
pinned json.hpp. `get<char>()` works, but implicit plain `char` is deliberately
not added: actual XDK compilation showed it makes an existing `std::string =
json` expression ambiguous. The full integration must use a checked compiler
projection for any reached plain-char implicit conversion.

Nine isolated compile probes still pass with official JSON and fail with the
bounded backend: ordered_json, initializer lists, JSON stream operators,
custom ADL conversion, conversion macros, enum get, map conversion, C-array
conversion and std::array conversion. The std::array probe is conservative
container coverage; this audit has not established a direct serialized
std::array call site. Do not count it as an observed production regression.
Unknown conversions fail compilation rather than return defaults.

The ordered backend, initializer-list lowering and explicit ADL/container
conversion registry need deliberate implementation with the actual game types.
This increment does not safely satisfy the full modern save/seed/feature
contract. No modern feature can be omitted to make the subset compile. Full
SaveManager section registration/migrations, actual saved files, legitimate
randomizer seed/hint fixtures, custom type instantiations and target CRT/runtime
behavior remain integration gates. Compiling each real consumer is required to
close the indirect conversion inventory; the table is not a claim of exhaustive
template-instantiation coverage.

## Reproduction and evidence

Run from the owned root:

```
python -B tools/shipyard/prepare_json.py
python -B tools/shipyard/tests/test_json_generation.py
python -B tools/shipyard/tests/test_json_backend.py
```

Include order for this ABI:

1. `platform/shipyard/json/include`
2. `platform/shipyard`
3. `scratch/json-xdk/backend-generated`

Compile `platform/shipyard/json/json.cpp`. Official host comparison uses
`platform/shipyard/json/upstream/include` instead; never mix the two JSON ABIs
in one executable. Generation fails on altered official/helper inputs and
rejects output paths outside owned scratch/json-xdk. Original files are not
rewritten.

Fresh evidence in `scratch/json-xdk/verification.json` records four host
output hashes, including rich values/errors/pointers, 4,000 deterministic double
bit patterns, malformed UTF-8/JSON, signed/unsigned64 bounds, comments, deep
parsing/destruction, exact modern SaveData/LoadData templates, and modern generic
API additions. Backend and API compile to PowerPC COFF machine 0x1f2. Added
lookup/value/predicate/narrow/update probes also pass XDK syntax compilation.
Four generation/source-ownership tests pass. Commands and logs are retained
under scratch/json-xdk. This is host behavior plus XDK object evidence, not
full application linkage, console execution, real-save parity or hardware proof.
