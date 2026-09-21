# Current SoH widget and menu types

`python -B tools/shipyard/prepare_soh_ui.py --build` projects the complete
release-pinned UIWidgets.cpp, its public declarations, and MenuTypes.h into
scratch/soh-ui-xdk. No original widget functions are omitted. Rendering still
calls the real current ImGui/LUS/CVar interfaces. This is application source
compatibility (A/B/G); the Xenos/XAudio backend choices are generic Shipyard
platform work (C/G). No modern menu is replaced.

The canonical UIWidgetTypes.h holds all twelve real option structures, used by
both UIWidgets.hpp and MenuTypes.h. Explicit generated constructors preserve
each member and initializer. A storage-free ValueInit tag distinguishes
upstream value initialization from default initialization: the five originally
uninitialized ColorPicker flags remain untouched under default initialization
and become zero under value initialization. Call sites must also preserve this
distinction, including value initialization inside make_shared. SearchWidget
keeps its required WidgetInfo reference. No parallel value classes are created.

The existing generic Xbox variant implements the current five CVar, ten option,
and three pointer alternatives. It has its own C++ layout; consumers must use
the canonical projected declarations. Actual tables and wrapping bodies remain
source-derived. Six defaulted function templates gain forwarding overloads for
the XDK compiler. Designated option arguments use the actual option objects and
their existing setters; range loops and aliases receive mechanical lowering.
FMin/FMax preserve the reached NaN/color-clamping result; round uses the existing
tested input compiler boundary. No renderer execution is claimed.

`python -B tools/shipyard/test_soh_ui.py` executes original and projected actual
inline methods plus both real WrappedText bodies. It compares option defaults,
placement default initialization, variant type/error behavior, reference and
shared ownership, deferred registration, all 65,536 filter codepoints, all 21
color entries, wrapping widths and 1,048,576 float-bit color inputs. The final
color hash is 940321830688332629. The same projected contract and full production
UIWidgets.cpp compile to native PPC objects. Complete menu implementations and
actual ImGui rendering through Xbox remain integration work.
