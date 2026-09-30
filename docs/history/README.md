# Historical development evidence

This directory preserves past investigations and delivered checkpoints. Its
source snapshots, measurements and workstation paths describe the recorded
revision and candidate; they are not selected by the maintained Xbox build.

- [Performance handoff, 2026-09-29](PERFORMANCE_HANDOFF-20260929.md) records the
  unsuccessful hardware checkpoint and the investigation state at that time.
- [Checkpoint files](performance/checkpoints/20260929/) retain the original
  source snapshots, identities and measurements byte for byte. References inside
  those frozen files use their original locations. The handoff above replaces
  the former repository-root `PERFORMANCE_HANDOFF.md` location.

Subsequent integration and build work is recorded in Git history and
[the main integration record](../MAIN-INTEGRATION-2026-09-29.md). Current build
instructions are in
[BUILD_FROM_SOURCE.md](../../platform/shipyard/build/BUILD_FROM_SOURCE.md).
Historical instructions and incomplete experiments do not override those
instructions or the active source-selection locks.
