# JSON consumer coverage

The Xbox backend is selected from Shipyard `sources/json`. It implements the
JSON operations reached by the port; it is not the full upstream `basic_json`
template. The reference library is nlohmann JSON 3.12.0 at
`55f93686c01528224f448c19128836e7df245f72`. Keep its license and the Shipyard
provenance records with the generated code.

Before adding a JSON call, check the real consumer and compare its values,
exceptions, and partial writes with the pinned upstream library. Do not infer
support from a matching method name. `consumer-inventory.json` is a lexical
inventory, not proof of all template instantiations.

The test suite covers parsing/printing, numeric conversion, streams, containers,
ordered objects, and the game's extracted save methods. Generic custom ADL,
initializer-list, cross-DOM, and enum conversions need particular care; consult
the current compile probes and game projector before relying on them.

Run after dependency setup:

```powershell
python -B tools/shipyard/prepare_json.py
python -B tools/shipyard/tests/test_json_generation.py
python -B tools/shipyard/tests/test_json_backend.py
```

Use the generated backend include paths for Xbox compilation and the upstream
headers for reference comparisons. Do not mix the two implementations in one
executable. Host comparisons and XDK objects do not establish real-save parity.

The [archived audit](../../../archive/subsystems/json/consumer-audit.md) keeps
the full consumer table, implementation history, gaps at each stage, and test
results. Its unfinished-integration statements describe that earlier stage.
