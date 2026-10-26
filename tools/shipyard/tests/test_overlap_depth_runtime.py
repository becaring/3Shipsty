"""Check that single-replay depth is sampled after the walk and before retirement."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from overlap_depth_runtime_projection import runtime


def main():
    source = (ROOT / "platform/shipyard/application/overlap_runtime.inc").read_text(encoding="utf-8-sig")
    render = runtime(source)
    render = render[render.rindex("static bool RenderPacket("):]
    render = render[:render.index("\n}\n")]
    walk = render.index("DrawAndRunGraphicsCommands")
    sample = render.index("if (!sampled) Shipyard_OverlapSampleDepth(")
    # The previous update's depth stays published through the walk.
    assert "XboxRetireGameDepth" not in render[:walk]
    assert "Shipyard_OverlapSampleDepth" not in render[:walk]
    assert walk < sample < render.rindex("XboxRetireGameDepth") < render.index("XboxPublishGameDepth")
    assert "if (index == 0 && packet.replay.maps.size() > 1) {" in render
    print("depth runtime: ok")


if __name__ == "__main__":
    main()
