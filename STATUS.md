# 3Shipsty status

2026-09-20. Active forward port of Shipwright **9.2.3 / Ackbar Delta** to Xbox 360.

- Exact release and all three submodules fetched and verified; pristine baseline
  recorded in UPSTREAM_BASELINE.md.
- Differential platform audit recorded in PORTING_LEDGER.md and porting/*.md.
- BinaryReader/Writer/MemoryStream/Stream generated from current LUS now compile
  with XDK; central Xenon endian detection is corrected in the projection.
  Host original/generated contract and six generator tests pass.
- Current graphics interfaces, extracted current combiner decoder and generic
  shader lowerer compile with XDK. Four generator tests and 2,097,152 host
  decoder/layout cases pass. Full graphics backend/interpreter remain unbuilt.
- C-preserving game projection and async/platform primitives are in progress.
  Broad C-as-C++ compilation was rejected after actual actor/graph failures.
  No upstream source has been changed.
- No modern XEX has been produced or run. No gameplay or hardware claim.
- Matching official 9.2.3 Windows package fetched for host-only extraction and
  resource validation. Owned copied ROM SHA1:
  cee6bc3c2a634b41728f2af8da54d9bf8cc14099. Extraction is not Xbox validation.
- Next: finish true C and async boundaries, mount matching archives through real
  resource consumers, then integrate the complete current application.

Authority: upstream owns game/application/features/resources/save semantics;
Shipyard owns Xbox platform mechanisms. Work and outputs remain in this tree.
All six supplied reference roots remain read-only.
