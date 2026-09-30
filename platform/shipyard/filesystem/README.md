# Xbox filesystem adapter

`xbox_compat::filesystem` implements the filesystem operations used by the port.
`prepare_filesystem.py` checks `sources.lock.json` and generates the pinned LUS
Directory header under `scratch/filesystem-xdk`. The game-specific projectors
apply its include and namespace changes. Provenance remains in
`donor-provenance.json`.

Paths support Xbox mount names, slash normalization, joining, and directory
iteration. The adapter uses native ANSI file APIs; it does not provide general
Unicode conversion. Invalid names, embedded NUL, and UNC paths report errors.

Call `InitWorkingDirectory` after mounting storage. Its logical current path
does not change the CRT working directory: pass resolved paths to CRT streams.
`copy_file` refuses to overwrite by default. Rename replaces the destination
without deleting the old file first. Failed replacement preserves the old file.
These file operations alone do not guarantee XContent durability.

`read_file` is capped at 128 MiB; use the archive library for streaming.
`write_file` checks progress and flushes the file. Timestamps retain native
FILETIME values for comparisons; timestamp setters and clock arithmetic are not
provided. Preserve native error details when adding operations.

Run from the repository root after dependency setup:

```powershell
python -B tools/shipyard/prepare_filesystem.py
python -B tools/shipyard/tests/test_filesystem_generation.py
python -B tools/shipyard/tests/test_filesystem.py
```

The [earlier audit](../../../archive/subsystems/filesystem/README.md) records
the detailed API inventory, recursive iteration behavior, and test evidence.
