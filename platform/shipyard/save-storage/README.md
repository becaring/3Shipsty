# Xbox save storage

This directory provides device selection, XContent mounting, and atomic file
replacement. Full SaveManager generation is handled by the
[save-manager provider](../save-manager/README.md). The old
`SaveSerialization.cpp` fragment is excluded from the production build; do not
compile it alongside the full SaveManager.

Mount storage on the application thread before SaveManager initialization.
The package is `3Shipsty`, displayed as `Ship of Harkinian`, with a 16 MiB
capacity request and mount name `shipyard:`. Save paths are
`shipyard:\Save\fileN.sav` and `global.sav`; read-only resource archives stay
outside this container. Report selection and mount errors to the caller.

Keep the mount open until all queued saves finish. Call
`SaveManager::ThreadPoolWait()` before destroying SaveManager, finish other
writers, then call `Shipyard::Storage::Shutdown()` to flush and close XContent.

`WriteAtomicFile` writes and flushes a temporary file before replacement. The
caller must serialize writes to each destination. Failures before replacement
preserve the previous file. A flush failure after replacement reports an error;
it does not promise rollback or power-loss recovery.

Modern saves serialize fields as JSON. Do not byteswap SaveContext snapshots.
Pre-versioned saves use the separate [legacy-save adapter](../legacy-save/README.md).

Run from the repository root after dependency setup and regeneration:

```powershell
python -B tools/shipyard/prepare_save_storage.py --build
python -B tools/shipyard/test_save_storage.py
python -B tools/shipyard/test_save_manager.py
```

Test device selection, save/load, copy/delete, and persistence across restart on
the exact runtime image. Host file tests cannot establish XContent durability.
The [earlier audit](../../../archive/subsystems/save-storage/README.md) preserves
the original partial-integration report and detailed failure tests.
