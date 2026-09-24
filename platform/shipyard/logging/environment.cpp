// Xbox has no process environment. The caller owns the launch path and the
// decision to accept an absent optional file.
#include "environment.h"
#include "environment/launch_environment.h"

namespace {
Shipyard::Environment::Store values;
}

extern "C" int ShipyardEnv_LoadFromFile(const char* path) {
    using namespace Shipyard::Environment;
    if (values.Initialized()) return SHIPYARD_ENV_ALREADY_INITIALIZED;
    if (!path || !*path) return SHIPYARD_ENV_INVALID;
    std::string text;
    switch (ReadBoundedFile(path, text)) {
    case FileAbsent:
        values.PublishAbsent();
        return SHIPYARD_ENV_ABSENT;
    case FileIoError: return SHIPYARD_ENV_IO_ERROR;
    case FileInvalid: return SHIPYARD_ENV_INVALID;
    case FileLoaded: break;
    }
    switch (values.PublishText(text)) {
    case PublishLoaded: return SHIPYARD_ENV_LOADED;
    case PublishInvalid: return SHIPYARD_ENV_INVALID;
    case PublishIoError: return SHIPYARD_ENV_IO_ERROR;
    case PublishAlreadyInitialized: return SHIPYARD_ENV_ALREADY_INITIALIZED;
    case PublishAbsentResult: break;
    }
    return SHIPYARD_ENV_IO_ERROR;
}

extern "C" char* ShipyardEnv_Get(const char* name) {
    return const_cast<char*>(values.Get(name));
}
