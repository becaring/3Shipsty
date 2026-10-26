"""Exercise debugger-stack policy with the projected command stack methods."""

import os
from pathlib import Path
import unittest
import test_compact_triangles as contracts
from render_state_work_projection import transform


class RenderStateWork(unittest.TestCase):
    run_fixture = contracts.CompactTriangles.run_fixture

    @classmethod
    def setUpClass(cls):
        root = contracts.ROOT
        path = os.environ.get('FAST3D_CONTRACT_SOURCE', root / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp')
        cls.source = Path(path).read_text()
        if 'struct XboxGfxPathScope' not in cls.source:
            cls.source = transform(cls.source)
        cls.out = root / 'scratch/xenon-cpu-audit/render/state-contract'
        cls.out.mkdir(parents=True, exist_ok=True)
        cls.compiler, cls.environment = contracts.host_environment()

    def test_debug_paths_follow_run_snapshot_and_restore(self):
        begin = self.source.index('static __declspec(thread) bool sXboxTrackGfxPath')
        end = self.source.index('\nvoid gfx_set_framebuffer', begin)
        methods = self.source[begin:end]
        self.run_fixture('debug-path', FIXTURE.replace('/* METHODS */', methods))

    def test_tile_import_certificate_is_preserved(self):
        self.assertEqual(self.source.count('const bool xboxTileTrial = true;'), 2)
        self.assertEqual(self.source.count('!XboxCanRetainTextureImports(*this)'), 2)
        self.assertNotIn('XboxTileStateDedupTrialProfile', self.source)


FIXTURE = r'''
#include <stack>
#include <vector>
#include <cassert>
#include <cstdio>
struct F3DGfx { unsigned word; };
struct GfxExecStack {
    struct CodeDisp { const char* file; int line; };
    std::stack<F3DGfx*> cmd_stack;
    std::vector<const F3DGfx*> gfx_path;
    std::vector<CodeDisp> disp_stack;
    void start(F3DGfx*); void stop(); F3DGfx*& currCmd();
    void openDisp(const char*,int); void closeDisp();
    const std::vector<CodeDisp>& getDisp() const;
    void branch(F3DGfx*); void call(F3DGfx*,F3DGfx*); F3DGfx* ret();
};
/* METHODS */
int main() {
    F3DGfx commands[3]={};
    GfxExecStack stack;
    for(unsigned debugging=0;debugging<2;++debugging) {
        XboxGfxPathScope scope(debugging!=0);
        stack.start(commands);
        stack.call(commands,commands+1);
        stack.branch(commands+1);
        assert(stack.gfx_path.size()==(debugging?2:0));
        assert(stack.currCmd()==commands+1);
        assert(stack.ret()==commands+1);
        assert(stack.gfx_path.empty());
        assert(stack.currCmd()==commands);
        stack.call(commands,commands+2);
        assert(stack.gfx_path.size()==(debugging?1:0));
        stack.stop();
        assert(stack.cmd_stack.empty() && stack.gfx_path.empty());
        { XboxGfxPathScope nested(!debugging); assert(sXboxTrackGfxPath==!debugging); }
        assert(sXboxTrackGfxPath==bool(debugging));
    }
    assert(sXboxTrackGfxPath);
    puts("PASS debug paths: normal/debug calls, branch unwinding, scope restoration");
}
'''
