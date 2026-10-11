#include "cvar_snapshot_fixture.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <thread>
#include <new>

static bool countSnapshotAllocations;
static unsigned snapshotAllocations;
void* operator new(size_t size) {
    if (countSnapshotAllocations) ++snapshotAllocations;
    void* result = malloc(size ? size : 1);
    if (!result) throw std::bad_alloc();
    return result;
}
void operator delete(void* pointer) noexcept { free(pointer); }
void operator delete(void* pointer, size_t) noexcept { free(pointer); }

int main() {
    Ship::ConsoleVariable variables;
    std::string key("temporary-key");
    variables.SetString(key.c_str(), "old-string");
    variables.SetInteger("integer", 11);
    variables.SetFloat("float", 1.25f);
    Color_RGBA8 rgba = {1, 2, 3, 4};
    Color_RGB8 rgb = {5, 6, 7};
    variables.SetColor("rgba", rgba);
    variables.SetColor24("rgb", rgb);
    Ship::ConsoleVariable::Snapshot frozen;
    variables.CaptureSnapshot(frozen);
    key.assign("overwritten-key");
    variables.SetString("temporary-key", "new-string");
    variables.SetInteger("integer", 99);
    variables.SetFloat("float", 9.5f);
    rgba.a = 99;
    rgb.r = 99;
    variables.SetColor("rgba", rgba);
    variables.SetColor24("rgb", rgb);
    variables.SetInteger("added-after-capture", 123);
    variables.UseSnapshot(&frozen);
    const char* borrowed = variables.GetString("temporary-key", "missing");
    assert(std::strcmp(borrowed, "old-string") == 0);
    assert(variables.GetInteger("integer", 0) == 11);
    assert(variables.GetFloat("float", 0) == 1.25f);
    assert(variables.GetColor("rgba", rgba).a == 4);
    assert(variables.GetColor24("rgb", rgb).r == 5);
    assert(variables.GetColor("rgb", rgba).a == 255);
    assert(variables.GetColor24("rgba", rgb).r == 1);
    assert(variables.GetInteger("added-after-capture", -1) == -1);
    assert(!variables.Get("added-after-capture"));
    std::thread producer([&variables]() {
        assert(variables.GetInteger("integer", 0) == 99);
        variables.SetString("temporary-key", "worker-string");
        variables.SetInteger("integer", 200);
    });
    producer.join();
    assert(variables.GetInteger("integer", 0) == 11);
    assert(std::strcmp(borrowed, "old-string") == 0);
    Ship::ConsoleVariable other;
    other.SetInteger("integer", 77);
    assert(other.GetInteger("integer", 0) == 77);
    variables.UseSnapshot(NULL);
    assert(variables.GetInteger("integer", 0) == 200);
    assert(std::strcmp(variables.GetString("temporary-key", ""), "worker-string") == 0);
    variables.CaptureSnapshot(frozen);
    variables.UseSnapshot(&frozen);
    Ship::CVar* reused = variables.Get("float").get();
    const char* reusedString = variables.GetString("temporary-key", "");
    std::shared_ptr<Ship::CVar> retained = variables.Get("integer");
    variables.UseSnapshot(NULL);
    variables.SetInteger("integer", 300);
    variables.mVariables.erase("rgba");
    variables.mVariables.erase("rgb");
    variables.SetString("rgba", "changed-type");
    variables.SetInteger("rgb", 17);
    variables.CaptureSnapshot(frozen);
    variables.UseSnapshot(&frozen);
    assert(variables.Get("float").get() == reused);
    assert(variables.GetString("temporary-key", "") == reusedString);
    assert(retained->Integer == 200);
    assert(variables.GetInteger("integer", 0) == 300);
    assert(std::strcmp(variables.GetString("rgba", ""), "changed-type") == 0);
    assert(variables.GetInteger("rgb", 0) == 17);
    variables.UseSnapshot(NULL);
    variables.mVariables.erase("rgba");
    variables.mVariables.erase("added-after-capture");
    variables.mVariables["rgb"].reset();
    variables.SetFloat("rgba", 2.5f);
    variables.SetString("temporary-key", "");
    variables.CaptureSnapshot(frozen);
    variables.UseSnapshot(&frozen);
    assert(variables.GetFloat("rgba", 0) == 2.5f);
    assert(!variables.Get("added-after-capture"));
    assert(!variables.Get("rgb"));
    assert(std::strcmp(variables.GetString("temporary-key", "missing"), "") == 0);
    variables.UseSnapshot(NULL);
    for (unsigned i = 0; i < 2048; ++i) {
        std::string modKey = "mod-variable-" + std::to_string(i);
        variables.SetInteger(modKey.c_str(), i);
    }
    variables.CaptureSnapshot(frozen);
    snapshotAllocations = 0;
    countSnapshotAllocations = true;
    for (unsigned i = 0; i < 8; ++i) variables.CaptureSnapshot(frozen);
    countSnapshotAllocations = false;
    assert(snapshotAllocations == 0);
    std::cout << "CVar snapshot ownership, reuse, type changes and thread isolation passed\n";
}
