# Complete application windows

This provider projects all eleven pinned debugger window implementations plus
ImGuiUtils and ResolutionEditor. It uses the existing complete canonical window
classes, real ImGui/UIWidgets, hooks, CVars, resources and Fast3D interfaces.
No window registration, method, menu or rendering body is replaced.

Reproduce after the existing dependency projections:

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_application_windows.py --build
C:/Python313/python.exe -B tools/shipyard/test_application_windows.py
```

Generic Shipyard A/B adaptations lower container initialization and structured
bindings, materialize actual Gfx/Vtx aggregates, preserve widget defaults through
canonical constructors, and supply named functions for captureless function
pointer callbacks. Temporary table storage stays in factory scope rather than
adding permanent copies. Numeric std::get calls retain tuple semantics. The
XDK lambda member-access defect requires explicit this-> on captured members.
UTF-8 string literals are escaped byte-for-byte for the XDK source code page.

The performance timer uses the existing Shipyard chrono implementation and
native monotonic counter; all five original functions and reset behavior remain.
The collision viewer's original normal-vertex union member, signed normals and
qs105 texture-coordinate scaling are retained. All values here are native
runtime geometry or metadata; no endian conversion is introduced. Xbox is added
to the existing platform label in the statistics window.

All thirteen complete sources compile with XDK. Original/projected host checks
execute the actual cylinder/sphere/triangle geometry routines and compare every
vertex and command (normalizing only host vertex addresses). Checks cover all
65,536 icon inputs, all 65,536 tested popcount inputs, 1,025 signed vertex cases,
the real timer functions, all function/UI/CVar call inventories and 161 UTF-8
literals. Output matches across 712 geometry/icon/timer lines. This does not
validate rendered frames or integrated target execution.

Source locks, generated source/helper hashes, native recipes and object evidence
are under scratch/application-windows-xdk. These sources belong in the normal
application link alongside the actual SohGui window registrations.
