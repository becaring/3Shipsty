# Complete current Fast3D interpreter projection

`prepare_fast3d.py --build` compiles the entire pinned current interpreter as
one Xenon object. It does not substitute a donor interpreter or exclude failed
functions. The renderer, shader provider and native presentation still require
integration and execution.

Inputs are checked against `sources.lock.json` before generation. Generic
Shipyard adaptations are A (language), B (library) and H (XDK initialization):

- Move in-class defaults to constructors in declaration order; preserve every
  current handler and all six opcode tables, including duplicate-key order.
- Represent the uint8 opcode domain with 256 entries, replacing the unsupported
  constexpr initializer-list constructor with an ordered pointer/count input.
- Expand only audited local aggregate assignments, structured range loops,
  if-initializers, deduced arrays, attributes and function-pointer aliases.
- Retain the current two-field combiner key and exact texture-cache equality.
  BattleShip's extra key fields and Smash-specific rendering policies are absent.
- Preserve empty RSP/RDP aggregate value initialization with zeroed raw allocation
  followed by placement construction. XDK can omit aggregate zeroing preceding
  nested non-POD constructors; no live shared_ptr is overwritten. Constructor
  failure frees raw storage. This generic compiler lesson was inspected in
  Smash360's generator; its transformed interpreter was not imported.
- Replace two set emplaces with pair insertion. The local depth-result map is
  destroyed immediately after merging; range insertion preserves existing
  destination entries without needing C++17 node transfer. No node escapes.
- Supply C99 round and reference-preserving clamp at their two current call
  sites each. `modf` avoids near-halfway addition rounding and preserves signed
  zero/infinities; ties round away from zero.

Commands from the owned root:

```powershell
python -B tools/shipyard/prepare_fast3d.py --build
python -B tools/shipyard/tests/test_fast3d.py
```

The host audit compiles actual full headers and twelve extracted current
constructor/stack/scaling methods, separately from the production full-TU
compile. It checks RSP/RDP defaults, ownership, cache-key distinctions, opcode
domain/duplicate behavior, viewport scaling and exceptional math inputs.
All original/generated opcode names, function identities and ordering are
compared directly across the six real tables. This is not a runtime renderer
test. Evidence is under `scratch/fast3d-xdk`.

Endian boundary: the existing `gDPReadFB` path receives native RGB5551 numeric
values from `ReadFramebufferToCPU`. When requested, it converts them to BE bytes
only on a little-endian host. The existing binary boundary now defines
`IS_BIGENDIAN` for Xenon; that interpreter conversion remains unchanged and is
correctly omitted. The native backend must deliver numeric RGB5551 values, not
pre-swapped bytes. GPU surface layout and raw texture upload still need native
validation. No blanket ROM/resource swap was added.

The final include manifest must use this interpreter/header pair, actual current
ImGui configuration and the GUI-resource Texture header consistently. The small
`stdbool.h` generated here is C++-only; application C uses its separate boolean
projection. Existing upstream uninitialized fields without defaults are not
silently initialized or used by the audit before their real startup assignments.
