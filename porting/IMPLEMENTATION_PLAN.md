# First XDK compatibility implementation plan

Goal: compile genuine pinned source at narrow platform/compiler boundaries,
then connect it to the real application. Spec: ../PORTING_LEDGER.md.
Execution is authorized inline, with independent binary/graphics work assigned
to separate owned paths. No reference tree writes or upstream source edits.

- [x] Lock pristine release/submodules and source-backed migration table.
- [x] Inventory real sources; test main/graph/SaveManager/randomizer/UI retention,
  upstream-only exclusions and deterministic unique output.
- [x] Binary boundary: compile original binarytools to capture XDK rejection;
  project source-locked modern files, correct central Xbox endian detection;
  compare real reader/writer/stream outputs on LE/BE data and bounds failures.
- [x] Graphics boundary: capture original interface failures; preserve 64/32
  keys and exact virtual signatures in projection; compile current decoder,
  compare outputs/layout; source-lock generic Xenos shader lowering.
- [ ] Game C boundary: capture original main/actor failures; isolate desktop
  entry guard, missing C headers and real C99 constructs in generated files.
  Preserve boolean conversion (a byte typedef is not equivalent). Verify chosen
  source-language projection with actual compiler and differential semantics.
- [ ] Generate inspectable XDK projects from the audited source inventory.
  Unknown sources/errors remain reported; no source silently removed to link.
- [ ] Adapt complete current resource/async/filesystem/config consumers, retaining
  new save filesystem operations and errors absent from the Smash donor.
- [ ] Integrate current LUS backends and real OTRGlobals/main/graph ownership;
  host-build exact ZAPDTR/OTRExporter and generate version-matching archives.
- [ ] Link and run real application in owned Xenia storage; validate every
  acceptance condition in PORTING_LEDGER.md, then address nearby defects.

Review focus: noncanonical boolean inputs; malformed/truncated archive headers;
uninitialized aggregate members; mixed-size PPC bitfields; worker failure and
shutdown; save temp-file replacement; shader cache identity and attachment clears.

Commands/evidence belong beside each provider and in scratch logs. Native object
success is a compilation checkpoint, never application/runtime acceptance.
