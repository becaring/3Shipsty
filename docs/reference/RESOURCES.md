# Resource and storage boundaries

Shipwright 9.2.3 and libultraship commit
`fdcaf6336776d24a6408d016b0a52243f108f250` define the resource interfaces, modern
save schemas, and configuration semantics. Shared Xbox services implement the
platform boundary without replacing those application policies.

## Archive and binary data

BinaryReader compares the record's serialized byte order with native byte order.
XDK PowerPC must be recognized as big endian; unconditional byte-swap operations
remain distinct from host-to-big/host-to-little conversions. See
[asset markers](../ASSETS.md).

ZIP entries need checked sizes, exact-read handling, and entry/handle lifetime
management on failure. MPQ and ZIP containers retain their own formats. Resource
factories retain modern type/version behavior and mod precedence.

The pinned modern resource loader removes the legacy header from its file
buffer. Another consumer's `BufferOffset` representation, offset MemoryStream
constructor, archive manifest fields, and compressed-MIDI blob padding are
version/game differences, not generic Xbox interfaces. Modern projection source
locks must match the actual modern input rather than another consumer's file.

## Lifetime and concurrency

ResourceManager owns its cache and worker pool. Destruction must drain admitted
work while the synchronization and resource dependencies it needs remain alive.
Remove entries while holding the cache lock, then release resources outside the
lock when destruction can reenter other services. Failed loads and batch loads
need the same synchronization and processing semantics as successful loads.

A single-worker configuration must not deadlock while waiting for nested work
queued to that same pool. Futures preserve values, exceptions, and ownership;
shutdown and abandoned futures must not outlive their required services.
Resources that can outlive logging require an explicit destruction/logging
lifetime contract.

## Saves and configuration

Modern SaveManager snapshots game state before background serialization. Queued
writes own serialized bytes. Durable success requires a complete write, flush,
replacement, and storage completion where applicable; enqueue alone is not
persistence. Storage selection and callbacks must not race game-state mutation
or teardown.

Keep modern save section registration, versions, randomizer metadata, slot
operations, and configuration updaters. Config/CVar numeric distinctions,
defaults, reload, and malformed-input recovery remain observable behavior.
Legacy imports have their own [format boundary](LEGACY_SAVE.md).

## Verification

Exercise real archive/resource factories and caches with short reads, malformed
entries, missing paths, one/multiple workers, repeated load/unload, and shutdown.
Save coverage includes vanilla/MQ/randomizer data, failure injection, storage
removal, interrupted writes, and fresh-launch persistence. Host fixtures and
PowerPC compilation do not replace these runtime checks.

The maintained [resource](../../platform/shipyard/resources/README.md),
[resource shutdown](../../platform/shipyard/resource-shutdown/README.md), and
[save-storage](../../platform/shipyard/save-storage/README.md) documentation
contains the subsystem entry points and contracts.
