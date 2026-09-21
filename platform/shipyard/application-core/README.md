# Complete application resource bridges

Eight full pinned sources provide the actual scene/room command execution,
message loading, resource lookup/patching, GBI bridge, utilities, notifications
and crash context. These consume the existing canonical modern resource and
application types; no replacement manager or game path is introduced.

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_application_core.py --build
C:/Python313/python.exe -B tools/shipyard/test_application_core.py
```

A/B compiler adaptations use existing container/range/contains helpers, preserve
the three GfxPatch aggregates through typed temporaries, and read the existing
byte-sized SceneCommandID wrapper's value. Message lookup captures the same
uint16_t ID before the lambda and names the actual MessageTableEntry argument
type. UTF-8 literals retain their bytes. Crash printing uses the existing C99
snprintf wrapper, including required length and terminated truncation. Explicit
canonical includes replace desktop/transitive umbrella dependencies.

No serialization or endian fixup is added. JPEG decoding already writes each
RGBA16 pixel as an explicit high byte then low byte; the complete conversion
function is unchanged. Display lists/scene commands and message entries here
are runtime-native resources already decoded by the modern factories, while
utility strings are compiled UTF-8 metadata. Archive readers remain owners of
serialized input conversion.

All eight full TUs pass XDK. Host original/projected checks compare 5,297 output
lines from the actual utility tables/functions across languages and all byte
values with bounded buffer sizes. The actual message-entry conversion passes
all 65,536 text IDs and retains pointers into the owning resource string. Source
checks cover all complete functions, non-ASCII literal bytes, unchanged JPEG
conversion and all patch-record expressions.

Native scene/resource execution, notification rendering, crash reporting and
custom message archive overrides remain unexecuted. The upstream custom-message
override call passes messages.size()+1 although allocation uses messages.size();
this pre-existing boundary requires runtime review before exercising overrides.
It is not silently changed as part of syntax projection. Evidence is under
scratch/application-core-xdk; this is translation evidence, not a boot claim.
