#include "environment.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

int main(int argc, char** argv) {
    CHECK(argc == 3);
    const int expected = atoi(argv[2]);
    CHECK(ShipyardEnv_Get("SSB64_MAX_FRAMES") == NULL);
    CHECK(ShipyardEnv_LoadFromFile(NULL) == SHIPYARD_ENV_INVALID);
    CHECK(ShipyardEnv_LoadFromFile("") == SHIPYARD_ENV_INVALID);
    CHECK(ShipyardEnv_LoadFromFile(argv[1]) == expected);
    if (expected == SHIPYARD_ENV_LOADED) {
        char* value = ShipyardEnv_Get("SSB64_MAX_FRAMES");
        CHECK(value && strcmp(value, "123") == 0);
        CHECK(strcmp(ShipyardEnv_Get("VALUE"), " a=b #literal ") == 0);
        CHECK(strcmp(ShipyardEnv_Get("EMPTY"), "") == 0);
        CHECK(ShipyardEnv_Get("missing") == NULL);
        CHECK(ShipyardEnv_Get("ssb64_max_frames") == NULL);
        CHECK(ShipyardEnv_Get(NULL) == NULL);
        CHECK(ShipyardEnv_LoadFromFile("other.env") == SHIPYARD_ENV_ALREADY_INITIALIZED);
        CHECK(ShipyardEnv_Get("SSB64_MAX_FRAMES") == value);
    } else {
        CHECK(ShipyardEnv_Get("SSB64_MAX_FRAMES") == NULL);
        if (expected == SHIPYARD_ENV_ABSENT)
            CHECK(ShipyardEnv_LoadFromFile("other.env") == SHIPYARD_ENV_ALREADY_INITIALIZED);
    }
    puts("Modern environment adapter PASS");
    return 0;
}
