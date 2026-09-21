# Shipyard filesystem boundary

This is a bounded native Xbox filesystem adapter, not a replacement application
or a `std` namespace facade. Its public namespace remains
`xbox_compat::filesystem` for explicit source projections; synchronization uses
the owned `Shipyard::Async` primitives. No modern feature source is changed.

## Provenance and generation

Two generic adapter source files were read and adapted from
`D:/Projects/Smash360/platform/xbox360/cpp-compat/filesystem`. Raw donor SHA-256
values are in `donor-provenance.json`. Donor tests and generators were not run.
No SoH360 application, save model, storage identity or assets were imported.

`sources.lock.json` locks 21 current application/LUS files and both owned
adapter files using UTF-8 text with BOM removed and CRLF normalized to LF.
`tools/shipyard/prepare_filesystem.py` fails closed on source or helper drift.
It projects the **actual pinned LUS Directory.h** by changing only its include,
filesystem namespace and range-for syntax, with source line mappings. The
upstream catch-all in Directory::CreateDirectory is retained, not extended to
the native API: native errors propagate through the adapter normally.

Outputs go only under `scratch/filesystem-xdk`; no reference checkout is an
executable input or an output location. The generated provenance lists exact
source lines for every matched `std::filesystem` / `fs::` use. This inventory
is lexical and includes a comment-only portable-file-dialogs match; it is not
a whole-program reachability proof.

The generator also exports `project_boundary(relative, original)` for owned
consumer projections. It verifies the original source hash and rewrites only
filesystem namespace/includes, preserving comments and string literals. The
generated `projection-hooks.json` records exact normalized-text character spans, original text and
line numbers for every edit. Nineteen of the 21 locked files are ready for this
boundary pass (including the comment-only file). Mixed OTRGlobals and Extract
contain explicitly classified PC extraction APIs and are rejected until the
caller provides a reviewed platform split. This is not permission to remove
their extraction code. Range-for/auto and other language lowering remain the
consumer projection's responsibility.

## Native contract

Path parsing supports named Xbox mount roots (`game:/`, `save:/`), slash
variants, lexical normalization, filename/stem/extension and path joining.
Invalid names, embedded NUL and UNC paths report native errors. File operations
use the native ANSI `A` APIs. General Unicode encoding conversion and Unicode
normalization are not implemented or claimed. Native path length, encoding,
mount and access limits remain authoritative.

The adapter implements status/existence/type/size, absolute/current paths,
single and recursive directory creation, directory enumeration, recursive
enumeration, removal and rename. `create_directory` never creates parents;
an already-existing directory returns false without error. `copy_file` has
throwing and error-code overloads with default no-overwrite behavior, as used
by modern SaveManager::CopyFile. It uses the native fail-if-exists operation,
not a racy existence check followed by truncation. Existing-slot copies and
self copies fail while preserving destination data. Directory sources are
rejected. Copy options are not silently emulated.

Rename uses `MoveFileExA(REPLACE_EXISTING | WRITE_THROUGH)`: the old save is not
pre-deleted, failed replacement preserves the old destination, and failures
carry both paths in `filesystem_error`. Tests cover a destination held without
sharing and confirm both old and pending bytes remain after failure. This is
the operation needed by the modern non-Switch/non-WiiU temp-to-save branch.
Do not select those other platforms' remove/copy/remove branches on Xbox.

The additional `read_file`/`write_file` helpers are native boundary APIs, not
additions to std::filesystem. Reads are capped at 128 MiB; archive streaming
belongs to the archive library. Writes check full progress and call
FlushFileBuffers. Copy and stream writes are not a claim of XContent durability.

Xbox current_path is an explicitly initialized logical path protected by the
native mutex. Startup must call InitWorkingDirectory after mounting storage.
It does not change the CRT's current directory. Relative CRT stream access must
be resolved separately or use absolute paths; a logical cwd alone is not a
process-wide stream-path redirect. The test compiles the actual stream(path)
expressions used by modern consumers against the XDK string constructors.

`file_time_type` stores the complete unsigned 64-bit native FILETIME tick
identity, with equality/inequality/order and a minimum sentinel. `last_write_time`
has throwing and error-code getters; errors return the minimum and preserve the
native error. This preserves the randomizer cache's unchanged/changed/missing
file decisions without inventing chrono conversions. Timestamp setters and
clock arithmetic are not exposed because no audited runtime consumer uses them.
Filesystem timestamp resolution still bounds cache invalidation, as upstream.

Recursive iteration supports `directory_options::none` and
`follow_directory_symlink`. On Windows it honors directory reparse links/junctions;
without the option it lists links but does not descend. Status/size/timestamp
queries follow their targets, dangling links are not descended into, and remove
deletes the link itself. Like standard recursive_directory_iterator, following
cyclic links may not terminate; this is not a cycle-detection service.
`platform_properties::directory_symlinks` is false for the native XDK filesystem,
whose mount roots are not directory links. The same option remains present in
the projected mod code and traverses all actual Xbox directories. Unknown option
values fail explicitly. No symlink creation API or no-op stub is added.

## Reached integration limits

| Current consumer | Supported boundary / remaining work |
| --- | --- |
| SaveManager.cpp/.h | Required path/create_directory/exists/remove/rename/default copy_file operations supported. SaveManager itself is not projected or compiled here; JSON, task binding, snapshot lifecycle, write error handling, metadata/hooks and persistence remain integration gates. |
| Config.cpp, ConsoleVariable.cpp, Context.cpp, ArchiveManager.cpp | Reached existence/type/remove/enumeration/absolute/path methods supported. Full classes and app-root selection are not compiled here. |
| Directory.h | Actual source projected and executed in the host fixture; recursive file listing retained. |
| DiskFile.h, FileHelper.h, Path.h, PathHelper.h | Audited and locked; their stream handling and unrelated modern syntax still require source projections. |
| Presets.cpp, 3drando/spoiler_log.cpp, Plandomizer.cpp, AudioCollection.cpp | Reached basic path/create/list/remove operations supported; full feature compilation and save content validation still required. |
| randomizer.cpp:170–231 | `file_time_type` and `last_write_time` cache contracts supported and tested; namespace projection hook preserves both cache maps and validation code. Full randomizer/JSON compilation remains outside this boundary. |
| mod_menu.cpp:139–140 | `directory_options::follow_directory_symlink` supported with explicit platform capability; hook preserves the option and traversal. Full menu/language projection remains outside this boundary. |
| OTRGlobals.cpp extraction/install branches | `relative`, `canonical`, path::native used by IsSubpath are absent. Preserve host extraction with actual host std::filesystem; target selection/routing still needs explicit review. Basic runtime archive/path operations are available. |
| Extractor/Extract.cpp | `temp_directory_path`, recursive/update/overwrite `copy`, symlink creation and `remove_all` stay host-tool contracts here. No extraction implementation or UI was removed. |
| SohMenuSettings.cpp | Absolute filesystem paths supported; SDL_OpenURL folder opening requires a separate Xbox UI/platform decision. |

No arbitrary recursive delete, permission editing, hard-link creation, symlink
creation, copy options, canonicalization or chrono-clock facade is provided.
Missing APIs must fail compilation and be implemented or routed explicitly.
Read-only game assets and writable saves/config must receive distinct mounted
roots through Context/storage integration. The adapter does not invent or
select a user's storage device.

## Fresh verification

Run from this owned checkout:

```powershell
python -B tools/shipyard/prepare_filesystem.py
python -B tools/shipyard/tests/test_filesystem_generation.py
python -B tools/shipyard/tests/test_filesystem.py
```

Eight generation tests verify determinism, source/helper drift rejection, output
containment, current consumer coverage, exact projection spans, preservation of
comments/literals and explicit host routing. A recorded initial
baseline exposed absent create_directory/copy_file before implementation.

The host suite compares standard Windows std::filesystem with the adapter and
also executes the Xbox logical-cwd branch. It covers save replacement, missing
and sharing failures, exception paths, occupied/self copies, exact bytes in a
copy larger than 1 MiB, readonly asset errors, directory creation, missing and
nonempty deletion, nested paths with spaces, recursion, invalid/empty paths,
native reads/writes and the actual projected Directory::ListFiles. It also
compares timestamp cache hits/invalidation/errors, actual directory junction
traversal with/without follow, target timestamp identity, dangling-link behavior
and link removal. Junction fixtures remain inside owned scratch directories.

The actual adapter TU and contract/Directory TU compile with the installed XDK.
Both emitted object headers are checked for PPC big-endian COFF (0x1f2).
Commands, stdout/stderr and object hashes are recorded in
`scratch/filesystem-xdk`; the concise result is `verification.json`.

These are host executions and target object compilation, **not** an XEX link,
Xenia run, hardware run, XContent flush, storage removal/full-media test,
Unicode guarantee or modern SaveManager round trip. Those remain acceptance
gates for the full port.
