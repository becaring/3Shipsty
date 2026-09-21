# Actor database and configuration migrations

`prepare_app_services.py --build` projects the complete current ActorDB.cpp and
ConfigUpdaters.cpp. Both compile for Xenon. Source hashes cover their declarations,
implementations and the actual actor table; all inputs validate before emission.

ActorDB remains the real actor registry, referencing the actual compiled actor
InitVars and EnPartner implementation. Its member defaults move into constructors,
contains becomes find, and the range loop is lowered (A/B). The constant pair
description table becomes equivalent POD rows and constructs the same map through
insertion. The ActorDBInit constructor accepts the exact current field sequence
and defaults, including sizeof(Actor); the real EnPartner initializer calls it.
No actor globals or registry service substitutes are supplied.

The full ConfigUpdaters.cpp is byte-for-byte unchanged after newline normalization.
All six migrations and every ordered copy/clear action remain intact, including
upstream duplicate migration entries and the F11-default/F10 comparison. The
header names the actual Config, CVar bridge and keyboard scancodes instead of an
unused LUS umbrella and removes the unsupported final annotation (A).

ActorDB's first inclusion of endianness.h through functions.h exposed C linkage
around the new scoped-enum template helper. The binary generator now encloses
its C++ declarations/includes in extern "C++" (A); C macro behavior and endian
decisions are unchanged. A first-include native regression test fails before the
fix and passes after; original/projected binary contracts and generation tests pass.

`test_app_services.py` runs all five actual unchanged Entry ownership methods and
the real description table on original/projected code. It checks defaults, long
strings, copy/assignment/self-assignment, vector relocation and every description.
The complete real actor registry is compiled but not initialized in this test;
no fake actor definitions are used. Full migration source identity is checked;
actual application migration execution is still a runtime gate.
