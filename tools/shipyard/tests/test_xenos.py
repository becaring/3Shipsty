"""Native ABI plus host pixel/cache boundaries; never claims GPU execution."""

from pathlib import Path
import json
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from prepare_xenos import prepare, OUT, OWN, PLATFORM_BASE
from prepare_archives import stable


def main():
    prepare()
    folder = OUT / "host"
    folder.mkdir(exist_ok=True)
    env = runpy.run_path(str(Path(__file__).with_name("test_binary.py")))
    compiler, environment = env["host_environment"]()
    text = """#include "pixels.h"
#include "shader_provider.h"
#include "xenos_backend.h"
#include <type_traits>
#include <map>
#include <cstdio>
#include <stdexcept>
#define CHECK(c) do{if(!(c))throw std::runtime_error(#c);}while(0)
static_assert(!std::is_abstract<Fast::GfxRenderingAPIXenos>::value,"missing current rendering virtual method");
int main(){
    for(unsigned v=0;v<256;++v)for(unsigned alpha=0;alpha<256;++alpha){
        unsigned five=(31*v+124)/255;
        CHECK(Shipyard::Xenos::PackReadbackPixel((alpha<<24)|(v<<16))==((five<<11)|(alpha?1:0)));
        CHECK(Shipyard::Xenos::PackReadbackPixel((alpha<<24)|(v<<8))==((five<<6)|(alpha?1:0)));
        CHECK(Shipyard::Xenos::PackReadbackPixel((alpha<<24)|v)==((five<<1)|(alpha?1:0)));
    }
    CHECK(Shipyard::Xenos::PackReadbackPixel(0xffffffff)==0xffff);
    std::map<Fast::ShaderProgramKey,int> variants;
    for(unsigned id=0;id<16;++id)for(unsigned option=0;option<16;++option)for(int filter=0;filter<3;++filter)for(int srgb=0;srgb<2;++srgb){
        Fast::ShaderProgramKey key={uint64_t(id)<<60,uint32_t(option)<<28,static_cast<Fast::FilteringMode>(filter),srgb!=0};
        CHECK(variants.insert(std::make_pair(key,static_cast<int>(variants.size()))).second);
    }
    CHECK(variants.size()==1536);
    std::puts("196608 ARGB/RGB5551 channel-alpha cases and 1536 full-width shader identities pass; current interface is concrete");
}
"""
    stable(folder / "contract.cpp", text)
    flags = ["/nologo", "/std:c++20", "/EHsc", "/MD"] + [
        "/I" + str(p)
        for p in [
            PLATFORM_BASE / "sources/xenos",
            OWN,
            OUT / "generated",
            ROOT / "scratch/fast3d-xdk/generated/include",
            ROOT / "scratch/imgui-xdk/generated",
            PLATFORM_BASE / "sources/graphics",
        ]
    ]
    env["invoke"](
        [compiler]
        + flags
        + [folder / "contract.cpp", "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")],
        folder,
        "build",
        environment,
    )
    result = env["invoke"]([folder / "contract.exe"], folder, "run")
    # Formatting changes preserve the literal SDK slots and VMX contracts.
    core = re.sub(r"\s+", "", (PLATFORM_BASE / "sources/xenos/core.cpp").read_text())
    assert all("SetTexture(" + str(slot) + ",texture)" in core for slot in range(6))
    assert "SetTexture(tile,texture)" not in core
    assert core.count("__vxor(__lvx(cached,") == 6
    assert core.count("__stvx(__lvx(values,") == 6
    assert "native_state.binding_constants_valid=false;" in core
    assert "published_framebuffer_image=image;" in core
    assert "voidDestroyFramebufferNative(intid)" in core
    assert "voidClearRegion(floatx0,floaty0,floatx1,floaty1)" in core
    assert "Smash360_" not in core and "SoH_" not in core
    api = re.sub(r"\s+", "", (OWN / "api.cpp").read_text())
    assert "ShipyardXenos::SetShaderCache(NULL)" not in api
    assert "ShipyardXenos::SetShaderCache(&cache)" in api
    assert "Shipyard::Xenos::LoadShaderCode" in api and "Shipyard::Xenos::StoreShaderCode" in api
    # Prebuilt programs by key, gated on the probe regenerating the pack's source.
    assert "Shipyard::Xenos::StoreShaderCode,PackedProgram}" in api
    assert "PackMatchesBuild()||!Shipyard::Xenos::FindPackedProgram(" in api
    assert api.index("Shipyard::IO::ShutdownShaderWrites()") < api.index("ShipyardXenos::Shutdown()")
    assert not (OUT / "generated/native.cpp").exists()
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host_output=result["stdout"],
                target_runtime_executed=False,
                physical_core=str(PLATFORM_BASE / "sources/xenos/core.cpp"),
            ),
            indent=2,
        )
        + "\n",
    )
    print(result["stdout"])
    print("physical Xenos core and six literal binding contracts pass")


if __name__ == "__main__":
    main()
