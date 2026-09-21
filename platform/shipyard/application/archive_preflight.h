#ifndef SHIPYARD_APPLICATION_ARCHIVE_PREFLIGHT_H
#define SHIPYARD_APPLICATION_ARCHIVE_PREFLIGHT_H

namespace Shipyard { namespace Application {
enum ArchivePreflight {
    ArchivesReady,
    PortArchiveMismatch,
    GameArchiveMismatch,
    GameArchiveMissing
};

// Same acceptance conditions as the pinned application's extraction/verify
// stages. On Xbox generation happens on the PC and no archive is deleted.
inline ArchivePreflight CheckArchives(bool portVersionMatches, bool vanillaNeedsRegeneration,
                                     bool mqNeedsRegeneration, bool vanillaExists, bool mqExists) {
    if (!portVersionMatches) return PortArchiveMismatch;
    if (vanillaNeedsRegeneration || mqNeedsRegeneration) return GameArchiveMismatch;
    if (!vanillaExists && !mqExists) return GameArchiveMissing;
    return ArchivesReady;
}
} }
#endif
