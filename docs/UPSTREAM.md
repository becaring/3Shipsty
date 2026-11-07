# Upstream and dependencies

The application baseline is Ship of Harkinian Ackbar Delta 9.2.3. The sources
below are pinned and may not match the latest upstream release.

| Component | Source | Commit |
| --- | --- | --- |
| Shipwright | [HarbourMasters/Shipwright](https://github.com/HarbourMasters/Shipwright) | `cb71e22a79bc5d1f688fa881795bbd93094895fc` |
| libultraship | [kenix3/libultraship](https://github.com/kenix3/libultraship) | `fdcaf6336776d24a6408d016b0a52243f108f250` |
| ZAPDTR | [HarbourMasters/ZAPDTR](https://github.com/HarbourMasters/ZAPDTR) | `ee3397a365c5f350a60538c88f0643f155944836` |
| OTRExporter | [HarbourMasters/OTRExporter](https://github.com/HarbourMasters/OTRExporter) | `32e088e28c8cdd055d4bb8f3f219d33ad37963f3` |

The release tag is [9.2.3](https://github.com/HarbourMasters/Shipwright/releases/tag/9.2.3).
Gitlinks and `.gitmodules` define the submodule inputs. Shipyard is a separate
platform dependency selected by `platform-base.lock.json`; changing a repository
remote does not change that selection.

`platform/shipyard/dependencies.lock.json`, the subsystem `sources.lock.json`
files, and the subsystem provenance records hold the other dependency identities:
zlib, libzip, tinyxml2, Prism, ImGui, spdlog, fmt, Opus, Opusfile, Ogg, Vorbis,
StormLib, string-view-lite, stb, libgfxd and dr_libs in `dependencies.lock.json`,
and thread-pool and JSON in their subsystem provenance records. The pinned release extracts with ZAPDTR/OTRExporter; Torch is
not a dependency.

## Speech and distribution

The Xbox speech provider uses eSpeak NG 1.52.0, commit
`4870adfa25b1a32b4361592f1be8a40337c58d6c`, under GPL-3.0-or-later.
Any distribution must include its source notices, corresponding source, and build
modifications. Do not relabel it as permissively licensed platform code. Sonic
commit `fbf75c3d6d846bad3bb3d456cbc5d07d9fd8c104` is a build dependency and is
not linked into this Xbox runtime.

The [architecture guide](ARCHITECTURE.md#speech-and-shutdown) covers speech data
packaging and shutdown. Keep all other dependency licenses, copyright notices,
and source-authority files too. ROMs, extracted game assets, and the Xbox SDK
are external inputs.

## Credits

Harbour Masters and the Zelda decompilation contributors wrote the application
foundation. libultraship supplies the modern engine interfaces; ZAPDTR and
OTRExporter extract the assets. Keep the [upstream credits](CREDITS.md) intact.
becaring maintains the Xbox integration and Shipyard.
