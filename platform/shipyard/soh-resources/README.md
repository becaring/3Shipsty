# SoH resource factories

`prepare_soh_resources.py` adapts the pinned 9.2.3 resource types and their
binary/XML factories for the XDK. `sources.lock.json` lists the inputs. Edit the
projector or the adapters here, then regenerate; do not edit generated files in
`scratch/soh-resources-xdk`.

The factories use the byte order selected by each resource record. The archive's
version entry has its own marker. Do not byteswap an entire archive or treat its
version marker as the payload byte order. See [assets](../../../docs/ASSETS.md).

Keep all scene-command registrations and their one-byte IDs. Generated default
constructors must preserve value initialization. SoundFont XML patches need RTTI;
the build must retain `/GR`. Resource, binary, logging, and Fast3D headers must be
generated before these sources; the normal regeneration script orders them.

Run from the repository root after dependency setup:

```powershell
python -B tools/shipyard/test_soh_resources_projection.py
python -B tools/shipyard/prepare_soh_resources.py --build
python -B tools/shipyard/test_soh_resources.py
python -B tools/shipyard/test_soh_resources_methods.py
python -B tools/shipyard/test_soh_resources_scene.py
```

The host comparisons and XDK compilation check different properties. They do
not establish that a scene renders correctly in gameplay. Test affected assets
in Xenia and on hardware after rebuilding the application.

The [earlier audit](../../../archive/subsystems/soh-resources/README.md) retains
the detailed factory inventory and test results.
