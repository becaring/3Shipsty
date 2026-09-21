# Bounded JSON compiler dependency

See [consumer-audit.md](consumer-audit.md) for the current 9.2.3 contracts,
remaining compile-proven gaps, source authority, build commands and evidence.
This backend preserves pinned nlohmann 3.12.0 scanner/Grisu2 algorithms but does
not implement generic basic_json or ordered_json. No application/game sources
are replaced. Do not use donor-only tests to claim modern save/seed parity.
