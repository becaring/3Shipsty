# 3Shipsty

3Shipsty brings modern **Ship of Harkinian** to Xbox 360. It builds the pinned
Ackbar Delta **9.2.3** application with native Xenon/Xenos support supplied by
[Shipyard](https://github.com/becaring/Shipyard).

The port retains the modern game's resource system, randomizer, configuration,
save formats, and frame interpolation. Xbox compatibility lives in maintained
adapters and source generators; generated files are build products.

## Getting started

You need a supported, legally acquired Ocarina of Time ROM to create the game
archives. ROMs and extracted game assets are not supplied by this repository.
Extraction runs on a PC using the matching upstream release; see
[assets and packaging](docs/ASSETS.md).

This is a development port. A successful XEX build establishes compilation and
linking; hardware compatibility and performance require testing that image.
The Xbox build requires a Windows development environment and an independently
obtained Xbox 360 SDK. Start with [development](docs/DEVELOPMENT.md).

## Documentation

- [Development and Xbox build](docs/DEVELOPMENT.md)
- [Architecture and source ownership](docs/ARCHITECTURE.md)
- [Assets and packaging](docs/ASSETS.md)
- [Upstream versions and licensing](docs/UPSTREAM.md)

## Credits

Xbox 360 integration is maintained by **becaring**. 3Shipsty builds on the work
of [Harbour Masters](https://github.com/HarbourMasters) and
[Ship of Harkinian](https://www.shipofharkinian.com/), the
[Ocarina of Time decompilation project](https://github.com/zeldaret/oot),
[libultraship](https://github.com/kenix3/libultraship),
[ZAPDTR](https://github.com/HarbourMasters/ZAPDTR),
[OTRExporter](https://github.com/HarbourMasters/OTRExporter), and the dependencies
credited in their source distributions.
See the preserved [upstream credits](docs/CREDITS.md) and
[dependency provenance](docs/UPSTREAM.md). Existing licenses and copyright
notices continue to apply to their respective code and assets.
