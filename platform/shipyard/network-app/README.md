# Complete network application features

All 30 pinned Anchor, Sail, Crowd Control and network-menu translation units
compile with XDK. The existing Network transport remains the owner of sockets,
framing, synchronization and receive lifetime. This provider retains the actual
packet handlers, game hooks, multiplayer actors, effect processing and menus.

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_network_app.py --build
C:/Python313/python.exe -B tools/shipyard/test_network_app.py
```

Production recipes are in scratch/network-app-xdk/xdk/build.json. Three compiler
processes build distinct objects; generation finishes before compilation starts.
No startup registrations are added: retain the original objects/registrations in
the real application. Existing startup shutdown already disables these services.

## Compatibility boundaries

- A/B: Existing container, range, binding, widget and source-location helpers
  lower unsupported syntax. Typed notification values retain all upstream
  defaults. Explicit strings satisfy the XDK rvalue-reference API. Empty native
  aggregates are value initialized; the local client-ID record keeps its zero
  default and original supplied value. All upstream fields and methods remain.
- B: Shared-pointer reinterpretation uses the real aliasing constructor, retaining
  ownership. No-argument make_unique uses unique_ptr(new T()), retaining value
  initialization and deletion. The reached plain enum JSON conversions retain
  their int representation. The ceil adaptation explicitly selects double after
  the original integer division; it does not alter the arithmetic.
- C/D: Crowd Control's real effect-processing thread uses the existing joining
  native worker and a one-second native sleep. Anchor queues keep their actual
  mutexes. Cancellation, socket shutdown and worker joining remain the existing
  runtime responsibilities; integrated runtime races still require validation.
- B/F: The complete original JsonConversions serializers are mechanically
  generated with explicit object construction and overload calls. All 12 readers
  and 11 writers remain. get<T>() value initializes then invokes the original
  reader. get_to(existing) invokes the original reader on that same object:
  unmentioned fields and partial updates before exceptions remain intact.
- I: Canonical includes replace desktop umbrella/transitive dependencies. The
  Crowd Control string/effect table remains complete in its projected header.

JSON carries host-independent textual numeric values; no raw structure dump or
byte swap is introduced. Game/native structures, notification colors and packet
types retain their actual meanings. The three-component RGBA default in the
tunic-color hook retains an implicit alpha of zero, not an invented alpha.

## Evidence and remaining validation

All complete production sources pass native XDK compilation and object/source
hash verification. Original/projected tests use the official nlohmann header on
the original side and the Xbox JSON implementation on the projected side. They
execute the actual complete serialization functions and compare 86 output lines:
full synchronized SaveContext schema, integers beyond double's exact range,
65,536 signed transforms, 256 colors, client defaults, partial updates that retain
unrelated save/player fields, value initialization and missing/type-error behavior.
Source checks retain all original functions, messages/keys and UTF-8 bytes.

No external Anchor/Crowd Control/Sail server is contacted by these checks. Prior
transport loopback evidence is separate. These tests do not claim in-game effect
execution, multiplayer synchronization, UI interaction or Xenia/hardware boot.
