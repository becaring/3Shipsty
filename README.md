# 3Shipsty

**Ocarina of Time on Xbox 360, powered by Shipyard.**

3Shipsty brings [Ship of Harkinian](https://github.com/HarbourMasters/Shipwright) 9.2.3 (Ackbar Delta), the native port of The Legend of Zelda: Ocarina of Time, to Xbox 360 hardware. It keeps Ship of Harkinian's enhancements, randomizer, frame interpolation and mod support, and it builds its game data from your own ROM the first time it starts, so the release contains no Nintendo data.

## Requirements

- An Xbox 360 that can run homebrew, with a dashboard or file manager that launches XEX files (Aurora, FSD or XeXMenu).
- Your own Ocarina of Time ROM as a `.z64`, `.n64` or `.v64` file. [supportedHashes.json](docs/supportedHashes.json) lists the versions 3Shipsty accepts. A Master Quest ROM holds only the Master Quest dungeons, so playing both dungeon sets takes both ROMs.
- A controller.
- A storage device for saves. On first start 3Shipsty asks which one to use and creates its save container there.

## Install

1. Download the latest 3Shipsty release ZIP from [Releases](../../releases/latest), not GitHub's Source code ZIP.
2. Copy the `3Shipsty` folder from the ZIP to your console over FTP or with a USB drive.
3. Put your ROM in that folder, beside `3Shipsty.xex`.
4. Launch `3Shipsty.xex`. The first launch builds `oot.o2r` from a regular ROM and `oot-mq.o2r` from a Master Quest ROM, showing the elapsed time while it works. Later launches reuse them.

Mods go in a `mods` folder beside `3Shipsty.xex`. Texture packs and fan translations work; a Brazilian Portuguese translation pack runs at a full 60 FPS.

## Controls

The game uses Ship of Harkinian's controls, and you can remap them in its controller menu. 3Shipsty adds:

| Input | Action |
|---|---|
| `Back` | Open or close the menu |
| Right stick | Move the menu cursor |
| `A` / `B` | Click or drag / right-click |
| `LT` / `RT` | Scroll |
| `R3` | Switch between the cursor and D-pad navigation |

### Known Limitations

- Packs that replace the game's models, such as 3DS-style model packs, can run out of console memory and run well below full speed.

## Logs

3Shipsty writes its logs to the `logs` folder beside `3Shipsty.xex`: `boot.txt` records startup, and the game log records everything after.

## Reporting a problem

Open a [bug report](../../issues/new/choose) and attach the `logs` folder as a zip. A report without a log file and a description of what happened closes automatically, and it reopens when you edit it to add them.

## Support Me
[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="40">](https://buymeacoffee.com/becaring) [<img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="36">](https://ko-fi.com/becaring)

If you had fun with 3Shipsty, a donation is NEVER required but always appreciated <3

## Building from Source

You need Windows, the Xbox 360 SDK, Visual Studio 2022 and a Shipyard checkout. [Building](docs/BUILDING.md) has the steps, [Assets](docs/ASSETS.md) covers ROMs and packaging, and [Architecture](docs/ARCHITECTURE.md) and [Upstream](docs/UPSTREAM.md) describe how the port fits together.

## Credits

3Shipsty builds on the work of [Harbour Masters](https://github.com/HarbourMasters), the [Ocarina of Time decompilation](https://github.com/zeldaret/oot), libultraship, ZAPDTR, OTRExporter and their dependencies, and on [Shipyard](https://github.com/becaring/Shipyard) for its Xbox 360 platform code. [Credits](docs/CREDITS.md) has the full list.

Developed with AI coding assistants; design, integration and hardware validation by becaring.

## License

Original 3Shipsty code is [MIT](LICENSE). The release links eSpeak NG for speech, which is GPL-3.0-or-later, so the release as a whole is distributed under GPL-3.0-or-later with this repository as its source. Ship of Harkinian and the other upstream components keep their own licenses and notices; [Upstream](docs/UPSTREAM.md) lists them. 3Shipsty is an unofficial fan project, unaffiliated with Nintendo, Harbour Masters or Microsoft. The repository and releases contain no ROMs, game assets or Xbox 360 SDK files; supply your own ROM.
