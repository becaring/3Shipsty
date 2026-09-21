#ifndef SHIPYARD_ENVIRONMENT_H
#define SHIPYARD_ENVIRONMENT_H

#ifdef __cplusplus
extern "C" {
#endif

enum ShipyardEnvStatus {
    SHIPYARD_ENV_LOADED = 0,
    SHIPYARD_ENV_ABSENT = 1,
    SHIPYARD_ENV_IO_ERROR = 2,
    SHIPYARD_ENV_INVALID = 3,
    SHIPYARD_ENV_ALREADY_INITIALIZED = 4
};

/* Initialize once, before starting workers. Values then remain valid for the
 * process lifetime. Missing optional file means an empty environment. */
int ShipyardEnv_LoadFromFile(const char *path);
char *ShipyardEnv_Get(const char *name);

#ifdef __cplusplus
}
#endif
#endif
