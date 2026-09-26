# Architecture

## Source ownership

| Layer | Responsibility |
| --- | --- |
| `soh` and pinned submodules | Modern Ship of Harkinian behavior, game data schemas, resource interfaces, and extraction tools |
| `platform/shipyard` | SoH-specific Xbox adapters, source locks, contracts, and subsystem documentation |
| `tools/shipyard` | Deterministic source projection, dependency validation, native builds, and tests |
| Shipyard | Shared Xbox platform services, native rendering/audio/input/storage, compatibility types, and source-lowering machinery |
| `scratch` | Generated sources, dependency working copies, objects, manifests, and build receipts |

`platform-base.lock.json` selects the Shipyard revision independently of this
repository's upstream release. Generic Xbox mechanics belong in Shipyard;
application policy and version-specific schema adaptation remain here.

## Compilation and runtime boundaries

The modern application is projected for the XDK's C and C++ compilers. Source
locks reject unexpected input changes. Generated translation units retain the
selected upstream implementations while explicit adapters bridge platform APIs.
Generated output is never the durable owner of a correction.

The modern Fast3D interpreter feeds the Xenos backend. Its shader identifiers,
six texture bindings, resource overrides, framebuffer operations, and vertex
layout remain part of the modern interface. Shared native code must preserve
those contracts; see [graphics interfaces](reference/GRAPHICS.md).

Resource factories interpret serialized byte-order markers independently of
Xenon's native order. Configurations and saves retain modern schemas. Queued I/O
and audio retain owned data until completion, and workers drain before their
services and storage are destroyed. See [resource lifetime](reference/RESOURCES.md)
and [legacy-save layout](reference/LEGACY_SAVE.md).

Frame interpolation keeps the pinned recording and matrix/angle algorithms.
Its consumed local context transfers replacement-map ownership to the caller.
The return contract checks value preservation and map payload copies separately
from full-frame execution.

## Extending the port

Keep source selection and game behavior in the consumer. Make reusable platform
changes in Shipyard, protect them with focused contracts, and adopt a reviewed
revision by updating the explicit dependency lock. Preserve upstream and
third-party notices and the provenance files alongside each projection.
