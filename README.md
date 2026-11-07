<picture>
  <source media="(prefers-color-scheme: light)" srcset="media/3Shipsty-on-light.svg">
  <img src="media/3Shipsty.svg" alt="3Shipsty" width="520">
</picture>

# 3Shipsty

**Ocarina of Time on Xbox 360, powered by Shipyard.**

3Shipsty brings [Ship of Harkinian](https://github.com/HarbourMasters/Shipwright) 9.2.3 (Ackbar Delta), the native port of The Legend of Zelda: Ocarina of Time, to Xbox 360. It runs at 1080p and 60 FPS, with 100% TAS validation on real hardware. It builds its game data from your own ROM on first launch, so the release contains no Nintendo data.

## Requirements

- An Xbox 360 that runs homebrew, with Aurora, FSD or XeXMenu to launch XEX files.
- Your own Ocarina of Time ROM (`.z64`, `.n64` or `.v64`). [supportedHashes.json](docs/supportedHashes.json) lists the supported versions. Master Quest needs its own ROM.
- A controller and a storage device for saves.

## Install

1. Download the release ZIP from [Releases](../../releases/latest), not GitHub's Source code ZIP.
2. Copy the `3Shipsty` folder to your console.
3. Put your ROM beside `3Shipsty.xex`.
4. Launch `3Shipsty.xex`. The first launch builds the game data from your ROM, and later launches reuse it.

Mods go in a `mods` folder beside `3Shipsty.xex`.

## Controls

The game's controls can be remapped in Ship of Harkinian's controller menu. 3Shipsty adds:

| Input | Action |
|---|---|
| `Back` | Open or close the menu |
| Right stick | Move the menu cursor |
| `A` / `B` | Click or drag / right-click |
| `LT` / `RT` | Scroll |
| `R3` | Switch between the cursor and D-pad navigation |

### Known Limitations

- Tested on an RGH console. It should work on ABadAvatar, BadUpdate and PeerPressure consoles, but those haven't been tested.
- Heavy texture packs and model replacement packs, such as 3DS-style model packs, can run out of console memory or run well below full speed.
- Translations and other mods should work but haven't been tested extensively.
- Networking features are implemented but not validated, and may not work at all.

## Logs

3Shipsty writes `boot.txt` and the game log to the `logs` folder beside `3Shipsty.xex`.

## Reporting a problem

Open a [bug report](../../issues/new/choose) and attach the `logs` folder as a zip. A report without a log and a description closes automatically and reopens when you add them.

## Support Me
[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="40">](https://buymeacoffee.com/becaring) [<img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="36">](https://ko-fi.com/becaring)

If you had fun with 3Shipsty, a donation is NEVER required but always appreciated <3

## Building from Source

You need Windows, the Xbox 360 SDK, Visual Studio 2022 and a Shipyard checkout. [Building](docs/BUILDING.md) has the steps.

## Credits

3Shipsty builds on [Harbour Masters](https://github.com/HarbourMasters)' Ship of Harkinian and libultraship, the [Ocarina of Time decompilation](https://github.com/zeldaret/oot), and [Shipyard](https://github.com/becaring/Shipyard). [Credits](docs/CREDITS.md) has the full list.

Developed with AI coding assistants; design, integration and hardware validation by becaring.

## License

Original 3Shipsty code is [MIT](LICENSE). Releases link eSpeak NG, which is GPL-3.0-or-later, so a release as a whole is GPL-3.0-or-later with this repository as its source. Upstream components keep their own licenses; [Upstream](docs/UPSTREAM.md) lists them. 3Shipsty is an unofficial fan project, unaffiliated with Nintendo, Harbour Masters or Microsoft, and contains no ROMs or game assets.
