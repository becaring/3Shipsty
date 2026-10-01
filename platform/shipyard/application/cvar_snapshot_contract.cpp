#include "cvar_snapshot_fixture.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <thread>

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
    std::cout << "CVar snapshot ownership, types, missing keys and thread isolation passed\n";
}
