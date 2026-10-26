"""Check lookup-cost edits against the prepared resource, bridge and interpreter sources."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
import lookup_cost_projection as lookup

GENERATED = ROOT / "scratch"


def read(path):
    return (GENERATED / path).read_text(encoding="utf-8")


def main():
    manager = lookup.resource_manager(read("resource-manager-xdk/generated/src/ship/resource/ResourceManager.cpp"))
    process = manager[manager.index("ResourceManager::LoadResourceProcess(const ResourceIdentifier& identifier"):]
    process = process[:process.index("\n}\n")]
    # A recorded miss returns before the archive probe, and fills never move the generation.
    assert process.index("ResourceLoadError::NotFound) {\n        return nullptr;") < process.index("LoadFileProcess(")
    assert process.count("InterlockedIncrement(&mXboxLookupGeneration);") == 1
    assert "if (replaces) InterlockedIncrement" in process
    assert manager.count("Shipyard_MemoResource(name, 0, NULL)") == 3

    bridge = lookup.resource_bridge(read("libultra-xdk/generated/src/libultraship/bridge/resourcebridge.cpp"))
    assert "return Shipyard_MemoResource(name, 0, NULL);" in bridge

    helpers = lookup.helpers(read("application-core-xdk/generated/soh/soh/ResourceManagerHelpers.cpp"))
    gfx = helpers[helpers.index('extern "C" Gfx* ResourceMgr_LoadGfxByName'):]
    assert "Shipyard_MemoResource(path, ResourceMgr_IsGameMasterQuest() ? 3 : 2, ResolveGfx)" in gfx

    interpreter = lookup.interpreter(read("fast3d-xdk/generated/src/fast/interpreter.cpp"))
    assert interpreter.count("XboxMaskMemo& memo = sXboxMaskMemo[") == 2
    assert "if (mMaskedTextures.erase(name)) ++sXboxMaskEpoch;" in interpreter
    print("lookup cost: ok")


if __name__ == "__main__":
    main()
