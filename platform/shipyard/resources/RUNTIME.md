# Current archive, loader and manager projection

`prepare_resource_manager.py` projects complete pinned LUS translation units:
ResourceLoader, ResourceManager, Archive, ArchiveManager, O2rArchive,
FolderArchive, OtrArchive, StringHelper, Utils, glob and StrHash64. All eleven
compile with the XDK; MPQ support and trace logging are enabled. This is not
resource-manager execution, Context initialization or an archive-mount claim.

The generator verifies normalized source hashes before writing generated
outputs under `scratch/resource-manager-xdk`. Original application/resource
bodies remain authoritative. The compatibility boundaries are:

- Actual cache variants, futures, promises and mutexes use the already tested
  Shipyard implementations. The existing asynchronous task bodies, priorities,
  pause policy, cache identities and alternate-resource behavior are retained.
- Container `contains` becomes `find != end`, and the actual string prefix
  check uses `compare`. Scoped enum storage remains a distinct type. Existing
  constructor initializers replace in-class initializers; no state is omitted.
- Structured bindings keep references to the map entry's two members. Range
  loops evaluate the range, begin and end once. The filesystem iterator uses
  the tested native input iterator directly.
- Current positional constructor calls replace only the audited brace forms.
  ResourceFactoryKey remains an aggregate with its original field order.
- StringHelper uses pinned official string-view-lite 1.8.0 in `nonstd`, without
  adding types to `std`. Views retain original buffers, lengths and embedded
  NUL bytes. Four-iterator `equal` becomes a size check plus the existing
  three-iterator algorithm. The C glob implementation remains `/TC`; it uses
  the same semantic boolean projection as the 696 application C files.
- Context retains its real class declaration, members and methods. Its
  unnecessary transitive Audio/backend include is narrowed to the actual
  AudioSettings value type extracted from AudioPlayer.h. Later AudioPlayer
  projection must include that same generated definition, avoiding duplicate
  types. The default settings remain 44100/1024/2480/stereo; the actual SoH
  caller's 32000/1024/1680 settings must still be passed through.
- Archive implementation files include ResourceManager directly in place of
  Window's unused transitive dependency. Filesystem streams receive native
  path strings. No alternative archive manager or Context body is supplied.
- `if constexpr(sizeof(size_t) >= 8)` in HashCombine becomes an ordinary
  constant condition; both branches are valid for both widths. Exact upstream
  hash expressions remain intact. Unqualified dynamic_pointer_cast is made
  explicitly `std::dynamic_pointer_cast` for XDK lookup.

```powershell
python -B tools/shipyard/prepare_stormlib.py
python -B tools/shipyard/prepare_resource_manager.py --build
python -B tools/shipyard/tests/test_resource_loader.py
```

The bounded host audit selects exact loader method definitions and the exact
projected glob function for unit execution. Those selected files exist only
under the host test directory; production compilation always uses complete
TUs. No fake Context, manager or runtime path is linked. Tests verify LE/BE
resource headers, 64-bit IDs, rewind/defaults, real factory registration and
conflicts, zero-copy views and current C/projected glob agreement. A failed
attempt to link a partial full-TU test without Context was replaced by this
explicit unit audit; it is not described as full manager execution.

An inherited glob edge case was observed: a negated class can consume the
terminating NUL (notably after `*`). The original function has no NUL rejection
in its `[` branch. No platform change was made to its behavior; comparisons
use padded buffers and do not claim POSIX glob conformance. Integrated usage
and upstream correction remain separate review work.

Full Context initialization, asynchronous cache/resource behavior, native
archive mounting and game-specific resource factories still require actual
application integration. Native compiler coverage does not prove those paths.
