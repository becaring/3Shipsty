"""Exercise the projected EndFrame depth ownership for both rendering routes."""

import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INTERPRETER = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'
sys.path.insert(0, str(ROOT / 'tools/shipyard'))


class ModernPresentationDepthTests(unittest.TestCase):
    def test_intermediate_and_final_replays(self):
        # Project from maintained owners so this checks the executable source.
        runpy.run_path(str(ROOT / 'tools/shipyard/prepare_fast3d.py'))['prepare']()
        source = INTERPRETER.read_text(encoding='utf-8', errors='replace')
        start = source.index('void Interpreter::EndFrame() {')
        end = source.index('\nvoid gfx_set_target_ucode(', start)
        projected_end_frame = source[start:end]

        harness = r'''#include <cassert>
namespace ModernFrameProfile {
enum Phase { PresentEndFrame, PresentSwapBegin, PresentFinishRender, PresentSwapEnd };
void Begin(Phase) {}
void End(Phase) {}
}
int depthDiscards = 0, colorDiscards = 0;
int observedDepth = -1, observedColor = -1;
namespace Fast { namespace ShipyardXenos {
void DiscardPresentationDepthOnEnd() { ++depthDiscards; }
void DiscardPresentationColorOnEnd() { ++colorDiscards; }
} }
struct RenderingAPI {
    void EndFrame() { observedDepth = depthDiscards; observedColor = colorDiscards; }
    void FinishRender() {}
};
struct WindowAPI {
    void SwapBuffersBegin() {}
    void SwapBuffersEnd() {}
};
struct Interpreter {
    bool mRendersToFb, mXboxDiscardGameDepth;
    struct { bool valid; } mXboxPipelineKey;
    RenderingAPI* mRapi;
    WindowAPI* mWapi;
    void EndFrame();
};
''' + projected_end_frame + r'''
int main() {
    RenderingAPI rendering;
    WindowAPI window;
    for (int separate = 0; separate != 2; ++separate) {
        for (int intermediate = 0; intermediate != 2; ++intermediate) {
            depthDiscards = colorDiscards = 0;
            observedDepth = observedColor = -1;
            Interpreter interpreter = {};
            interpreter.mRendersToFb = separate != 0;
            // The 1080 Run path consumes this flag before EndFrame; the
            // direct 720 path retains it for presentation-depth discard.
            interpreter.mXboxDiscardGameDepth = !separate && intermediate;
            interpreter.mRapi = &rendering;
            interpreter.mWapi = &window;
            interpreter.EndFrame();
            assert(observedDepth == (separate || intermediate));
            assert(observedColor == separate);
            assert(depthDiscards == observedDepth);
            assert(colorDiscards == observedColor);
        }
    }
}
'''
        compiler, env = runpy.run_path(
            str(ROOT / 'tools/shipyard/tests/test_binary.py'))['host_environment']()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            fixture = directory / 'end_frame.cpp'
            executable = directory / 'end_frame.exe'
            fixture.write_text(harness)
            build = subprocess.run(
                [str(compiler), '/nologo', '/EHsc', '/MD', str(fixture),
                 '/Fe:' + str(executable)], cwd=directory, env=env,
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(executable)], cwd=directory,
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
