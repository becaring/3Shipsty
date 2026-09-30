# Maintainer-local code navigation (optional)

These tools are private developer conveniences for the maintainer's Windows
checkout layout. They are not portable build prerequisites, release tooling,
or part of the Xbox runtime. Consumer generation, tests, compilation and linking
use the documented build drivers without Serena, Codex or this navigation index.

`nav.py` and `launch_serena.py` deliberately contain workstation paths for the
fixed MCP registrations. A different workstation must configure its own paths
and registrations before using them; cloning the repository does not install or
activate any server. Do not copy these paths into portable build scripts.

Five fixed, read-only MCP servers are registered in the machine Codex config:
`serena_shipyard`, `serena_modern`, `serena_smash`, `serena_majora`, and `shipyard_nav`.
Each Serena process starts on one fixed worktree; never use a mutable project
switch for these registrations. Serena supplies symbol lookup, references, and
bounded source reads. `shipyard_nav` supplies selected-build and generator
relationships from local manifests, locks, and `#line` markers. It does not
infer a call graph.

`D:\Projects\becaring\shipyard` is the canonical maintained Shipyard repository.
The active consumers include Modern, Smash, and the pinned Majora source at
`D:\Projects\2Ship3Shipsty`. OoT and Majora select `selections/3Shipsty` and
`selections/2Ship` inside canonical Shipyard; Smash selects its root.
The older root checkouts and frozen candidates remain preserved.
`shipyard_topology` reports active worktree identity, lock identity, and freshness.
The navigation runtime and database remain under the original Modern root's
`scratch/code-nav`; analysis compile databases belong to the active worktrees.

The venv and SQLite database are under `scratch/code-nav/`. Installed versions:
`serena-agent==1.7.0`, `clangd 19.1.2`, `pyright 1.1.403`. Modern and Smash
have separate analysis-only `compile_commands.json` files. Majora's database
comes from its selected `scratch/project-xdk/manifest.json`; Modern and Smash
use their selected manifests and project items. No production recipe reads the
analysis databases.

After changing a source file, the relationship tools compare current file
bytes with indexed SHA-256. A stale or deleted result must be refreshed before
editing from it. After branch, dependency, repository topology, manifest, generated output, or
configuration changes, run:

```powershell
D:\Projects\3Shipsty9.x\scratch\code-nav\venv\Scripts\python.exe D:\Projects\3Shipsty9.x\tools\code_nav\nav.py refresh-all
```

This regenerates the analysis databases, scoped Serena configs, and SQLite
relationships under a writer lock. Readers use a WAL snapshot. Restart the
affected Serena MCP process after a compile/configuration change so clangd
loads the updated command. Restart Codex once after installing the MCP
registrations; the running client does not discover new tools mid-session.

Selected manifests are the coverage boundary. Callback registrations and
XDK-heavy translation units can lack language-server references; inspect the
reported selection/adapter evidence and exact source lines. `No indexed
references` is not evidence of no callers. Historical sources require an
explicit path; default Serena scopes exclude freezes and unselected trees.

To disable, remove only the five `mcp_servers` entries named above from
`C:\Users\crisj\.codex\config.toml` and the navigation paragraph in
`C:\Users\crisj\.codex\AGENTS.md`, restart Codex, and remove the four `.serena/project.yml` files,
their analysis `compile_commands.json` files, and `scratch/code-nav/`.
Keep unrelated MCP registrations and preexisting project files.
