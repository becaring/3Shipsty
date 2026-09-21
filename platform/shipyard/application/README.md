# OTRGlobals declaration boundary

`prepare_application.py --probe` preserves the full real OTRGlobals class and
generates its complete implementation source. The class declaration compiles
to an 80-byte Xenon layout. The complete OTRGlobals.cpp is **not yet compiled**
and contributes no completed production-unit coverage.

Only unused transitive includes become genuine forward declarations. Complete
service includes are retained or added to the implementation. Eight font-pointer
member defaults move to the same real constructor's initializer list (A). The
original constructor body, Context creation, resource/application ownership and
all other methods remain intact. The constructor and header must be consumed as
one generated pair; never combine the projected header with an unprojected ctor.

Full startup, PC-only extraction boundary, save/storage teardown and native
execution remain integration work. No alternate application or service provider
exists here. Before queue storage teardown, integrate the documented real
`Shipyard::Libultra::StopTimers()` boundary.
