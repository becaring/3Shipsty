# Current configuration projection

The complete pinned Config.cpp compiles for XDK. It retains the actual JSON
flattened/nested state, migration registry, getters/setters and save/reload
behavior. No separate Xbox configuration store is introduced.

`prepare_configuration.py` provides narrow declarations for Config and Window.
Config includes the actual backend value types without pulling in GUI/input
implementation dependencies. Window retains its complete class declaration
and uses forward declarations for pointer-only dependencies. Its removed
`mLastScancode = -1` member initializer must be inserted into the upcoming
Window constructor projection; complete Window implementation is not yet built.

Current backend numbers are preserved. Audio appends XAUDIO2 after NUL. Window
appends FAST3D_XENOS after the three desktop backends and advances the count.
Native configuration selects XAudio2 for absent/desktop backend names, while
retaining the explicit null fallback. The actual Audio factory creates XAudio2.
Xenos window metadata is registered here; a real native window/rendering
implementation still needs to supply and advertise that backend.

Range loops preserve current value/reference semantics. The map insertion uses
the same key and shared pointer, returning the existing insertion success flag.
The if-initializer and enum switch/cast syntax are generated for XDK. CVar
definitions come from the same pinned CMake evaluation as the full C build,
including **gAudioChannelsSetting**; the generated headers compare identical.

Config's local input stream is converted to a complete string before the real
JSON parser. This is limited to Reload: the local stream is never observed
again, and parse failures still reach its existing catch/fallback. It is not a
claim that the JSON compatibility library now supports arbitrary stream APIs.
General JSON ordered/custom/container compatibility remains open.

```powershell
python -B tools/shipyard/prepare_audio.py
python -B tools/shipyard/prepare_configuration.py --build
python -B tools/shipyard/tests/test_configuration.py
```

Host original/projected Config method audits agree on nested/typed values,
blocks/arrays, copies, erasure, ordered version updates, file save/reload and
malformed-input fallback. Native audio/window metadata checks pass. The one
method requiring a live Context/window (`GetWindowBackend`) is excluded only
from this unit audit; the complete production TU is compiled separately. No
fake Context/window class is used.

An inherited behavior is explicitly retained: Nested skips missing path
components, so after erasing `Features.Group`, asking for
`Features.Group.Name` can resolve `Features.Name`. The differential tests
preserve this upstream behavior instead of silently changing configuration
semantics during the port. Full Context startup and native storage integration
remain unvalidated.
