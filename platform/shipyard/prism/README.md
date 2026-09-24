# Current shader generation through Prism

Exact CMake-pinned Prism `bbcbc7e3f890a5806b579361e7aa0336acd547e7`
is receipt-verified before generation. All five library TUs, including the C
invocation bridge, compile with XDK. The sixth production TU extracts the
complete current shader helper/builder region from 9.2.3's DX11 backend.
The original shader resource load, native byte order, default path, include
loader and missing-default abort remain present. No donor application or
BattleShip shader builder is used.

Generic Shipyard A/B/H adaptations:

- The version-constrained compiler projector is
  `xbox360_platform.prism.PrismProjector` in Shipyard. This consumer supplies
  its own pinned Prism source, tree-sitter parser, shader builder, 38 context
  entries, resource loading, and debug policy. The old local syntax projector
  has been removed.
- Fixed-arity variant/optional and Prism range helpers are physical Shipyard
  headers under `sources/value_types/xbox_compat` and `sources/prism`.
  `xbox360_platform.value_types` deterministically renders the checked-in
  19-alternative variant header; the consumer does not generate a copy.
- Preserve variant selection (including bool to int), owned alternatives,
  exception/valueless behavior, copy/move and optional engagement. These
  helper types remain outside std; the smaller resource two-reader variant
  retains its own existing boundary.
- Preserve member defaults and AST node fields with explicit constructors;
  lower range loops with one range/end evaluation and array dimensions with
  bounded vector construction. Existing parser/evaluator behavior is retained.
- Replace the current builder's 38 initializer-list context entries with
  individual equivalent assignments. Its bounded anonymous shader constants
  explicitly select the same int alternative. Formula logic is unchanged.
- Add std qualification to the two current static_pointer_cast calls which
  XDK cannot resolve unqualified. Shader debug logging remains enabled through
  current spdlog; the donor's logging-suppression transformation was removed.

Commands:

```powershell
python -B tools/shipyard/prepare_prism.py --build
python -B tools/shipyard/tests/test_prism.py
```

The host audit compares original and projected full Prism implementations plus
the current shader-building logic. Only the test copy substitutes in-memory
template acquisition for live Context; the production TU retains real resource
calls. Actual pinned template bytes are read from this checkout. Nine parser
cases include loops, branches, missing variables, include success/failure and
syntax errors. Variant tests include the actual nineteenth AST alternative,
string ownership, bool selection and throwing move recovery.

936 combinations of real combiner modes, option bits, root signature, filtering
and sRGB produce identical HLSL and vertex float counts. Representative outputs
also pass the already-imported generic Xenos lowering; all 264 unique vertex/
pixel shader compilations pass the actual Xbox 360 shader compiler. Raw Xbox
microcode and logs are ignored artifacts under scratch/prism-xdk.

This proves host generation parity and native compilation, not shader execution,
GPU appearance, loaded custom shader resources, live resource ownership or
thread safety. The original builder's static raw_numFloats accounting remains;
native shader creation must follow the actual render-thread ownership. The C
invoke bridge passes only pointer/integer-width callback arguments here; its
PPC execution and stack-argument behavior still need target validation.
