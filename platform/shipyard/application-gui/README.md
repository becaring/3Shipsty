# Modern application GUI ownership

`prepare_application_gui.py` projects the complete pinned SohGui.cpp and actual
window declarations. All 12 original function bodies and all 28 window
registrations are retained. It instantiates the real debugger, trackers, editors,
menus and application windows against their existing GuiWindow interfaces.
Those windows' pending implementation units remain explicit link dependencies.

A/B adaptations move original member defaults into equivalent constructors,
forward inherited GuiWindow constructors, preserve value-initialization zeros,
and lower vector/map initializer lists into typed builders. Conditional
RandomizerInf rows remain sourced from the original macro include. One original
MessageViewer inline static TABLE_ID definition moves into WindowStatics.cpp.
Complete fields/methods remain; no placeholder window or rendering path exists.
AudioCollection owns the canonical AudioSeqType header used by AudioEditor.

Unused translation-unit umbrella includes are removed only where the function
bodies do not use their declarations. The unused desktop audio-backend list is
projected to native XAudio2/Null names. No enhancement widget is replaced.

```
C:/Python313/python.exe -B tools/shipyard/prepare_application_gui.py --build
C:/Python313/python.exe -B tools/shipyard/test_application_gui.py
```

Both production units and the complete window-header probe compile as PPC.
The probe is explicitly excluded from the project. Original/projected table
comparisons match 2,485 debugger/tracker rows; generation checks preserve the
full function bodies and registrations. Receipts and generated hashes are in
`scratch/application-gui-xdk`. These are declaration/table/compile checks;
no native GUI frame or window interaction has executed.

This is 3Shipsty application syntax adaptation using Shipyard compatibility
types. Runtime data is host-native numeric metadata; no byteswaps are added.
