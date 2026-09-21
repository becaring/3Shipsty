# Modern application menus

`prepare_soh_menus.py --build --units Menu SohMenu SohModals SohMenuSettings
SohMenuEnhancements SohMenuDevTools` compiles six complete pinned application
units through XDK. It preserves every original function and all 449 feature
widget registrations: 362 enhancements, 61 settings and 26 developer tools.
The real GUI calls, callbacks, CVar names, randomizer option checks, searches,
disable predicates and modal queue remain application-owned.

Generated Menu/SohMenu/modal classes retain their full members. Inherited
constructors forward to the real GuiWindow interfaces; original member defaults
initialize in declaration order. Designated menu/search/notification values
use their actual canonical structures. Generic map insertion explicitly retains
upstream value initialization for missing menu entries; default construction
continues to preserve its distinct behavior. Map rows remain source-derived.
Real GUI shared-pointer aliasing uses the existing generic compatibility helper.
Explicit ImVec2/ImVec4/ImRect constructor calls preserve braced call arguments.

The Xbox platform has no desktop file manager. The Open App Files Folder button
remains visible, disabled with a platform explanation; its SDL desktop callback
is retained behind a non-Xbox guard. This is an OS-shell capability boundary,
not a replacement game menu. Control configuration and notifications retain
their actual service calls. Three non-ASCII strings use explicit UTF-8 octal
bytes so the XDK execution encoding cannot corrupt their accents.

`test_soh_menus.py` compares actual upstream/projected search and widget values,
notification fields/defaults, absent/present map insertion, and four modal queue
method bodies with 128 deferred callbacks. It checks native literal bytes against
host-compiled originals, all function identities and widget argument inventories.
The same contract compiles for PPC. It does not execute rendered menu frames or
pretend to provide missing application services. Randomizer/network menu units
and complete SohGui window registration remain pending.

Changes are A/B compiler/library adaptations around real 3Shipsty application
source; pointer casts, initialization techniques and OS capability handling are
reusable Shipyard techniques. Source locks and generated hashes are recorded.
