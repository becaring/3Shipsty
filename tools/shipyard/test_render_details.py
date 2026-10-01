"""Exercise opt-in count ownership without a graphics device or wall clock."""

import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = ROOT / "scratch/render-details"
    out.mkdir(parents=True, exist_ok=True)
    binary = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
    compiler, env = binary["host_environment"]()
    source = out / "contract.cpp"
    source.write_text(
        """#include "application/render_details.h"
#include "xenos/details_counts.h"
#include <cassert>
int main() {
    using namespace ModernFrameProfile;
    RenderDetailsCounts counts;
    counts.Flush(FlushDepth, 2); counts.TextureLookup(true); counts.TextureImport(false);
    assert(counts.flush[FlushDepth].calls == 0 && counts.textureLookups == 0 && counts.imports == 0);
    counts.Begin(true);
    counts.Flush(FlushDepth, 0); counts.Flush(FlushDepth, 2); counts.Flush(FlushShader, 5);
    counts.TextureLookup(true); counts.TextureLookup(false);
    counts.TextureImport(false); counts.TextureImport(true);
    assert(counts.flush[FlushDepth].calls == 2 && counts.flush[FlushDepth].empty == 1);
    assert(counts.draws == 2 && counts.triangles == 7 && counts.maximumTriangles == 5);
    assert(counts.textureLookups == 2 && counts.textureHits == 1 && counts.textureMisses == 1);
    assert(counts.imports == 1 && counts.maskImports == 1);
    counts.Reset(); assert(counts.draws == 0 && counts.enabled);
    counts.Begin(false); counts.Flush(FlushDepth, 3); assert(counts.draws == 0);
    ActorInstanceCounts actors;
    actors.Begin(false); actors.Observe(7); assert(actors.calls[7] == 0);
    actors.Begin(true); actors.Observe(7); actors.Observe(7); actors.Observe(300);
    actors.Observe(-1); actors.Observe(512);
    ActorInstanceCounts packet = actors.Take();
    assert(packet.calls[7] == 2 && packet.calls[300] == 1 && packet.total == 3);
    actors.Begin(true); actors.Observe(7);
    assert(packet.calls[7] == 2 && actors.calls[7] == 1);
    assert(actors.Take().calls[7] == 1 && actors.calls[7] == 0);
    Fast::ShipyardXenos::DetailsCounts native;
    native.Add(Fast::ShipyardXenos::DetailsDraws);
    assert(native.values[Fast::ShipyardXenos::DetailsDraws] == 0);
    native.Begin(true);
    native.Add(Fast::ShipyardXenos::DetailsDraws);
    native.Add(Fast::ShipyardXenos::DetailsTriangles, 7);
    native.Add(Fast::ShipyardXenos::DetailsSamplerAttempted, 5);
    assert(native.values[Fast::ShipyardXenos::DetailsDraws] == 1);
    assert(native.values[Fast::ShipyardXenos::DetailsTriangles] == 7);
    assert(native.values[Fast::ShipyardXenos::DetailsSamplerAttempted] == 5);
    native.Reset(); assert(native.enabled && native.values[Fast::ShipyardXenos::DetailsDraws] == 0);
    native.Begin(false); native.Add(Fast::ShipyardXenos::DetailsDraws);
    assert(native.values[Fast::ShipyardXenos::DetailsDraws] == 0);
}
""",
        encoding="utf-8",
    )
    command = [
        str(compiler),
        "/nologo",
        "/EHsc",
        "/MD",
        "/W4",
        "/I" + str(ROOT / "platform/shipyard"),
        str(source),
        "/I" + str(binary["PLATFORM_BASE"] / "sources"),
        "/Fo:" + str(out) + "/",
        "/Fe:" + str(out / "contract.exe"),
    ]
    result = subprocess.run(command, env=env, cwd=out, capture_output=True, text=True)
    (out / "build.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([str(out / "contract.exe")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    print(
        "Render details gate, Flush counts, texture counts and actor snapshot ownership passed"
    )


if __name__ == "__main__":
    main()
