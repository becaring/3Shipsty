# Modern SoH JSON contract probes

The Xbox backend and its pinned algorithm generators live in Shipyard
`sources/json` and `python/xbox360_platform/json`. This directory retains the
official 3.12.0 source for host differential tests and the modern SoH enum and
randomizer probes. `tools/shipyard/prepare_json.py` invokes the Shipyard
generator, then emits only those consumer probes.

See [consumer-audit.md](consumer-audit.md) for reached API coverage and gaps.
