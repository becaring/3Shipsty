"""Check caller guards preserve sampled traces and all work/early-return paths."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from profile_caller_guard_projection import transform, remove_instrumentation


FIXTURE = r"""
int Pipeline(bool selected, int imports) {
    ModernFrameProfile::Sample xboxPrepSample;
    ModernFrameProfile::Begin(xboxPrepSample, selected);
    int work = 1;
    ModernFrameProfile::AdvancePipelinePreparation(xboxPrepSample, 1);
    for (int i = 0; i < imports; ++i) {
        ModernFrameProfile::EnterPipelineTextureImport(xboxPrepSample);
        work += 3;
        ModernFrameProfile::ExitPipelineTextureImport(xboxPrepSample);
    }
    ModernFrameProfile::AdvancePipelinePreparation(xboxPrepSample, 2);
    work *= 5;
    ModernFrameProfile::AdvancePipelinePreparation(xboxPrepSample, 3);
    ModernFrameProfile::EndPipelinePreparation(xboxPrepSample);
    return work;
}
int Texture(bool selected, bool missing, bool load) {
    ModernFrameProfile::Sample xboxTextureHashSample;
    ModernFrameProfile::Begin(xboxTextureHashSample, selected);
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, 4);
    if (missing) {
        ModernFrameProfile::EndTextureHash(xboxTextureHashSample);
        return 7;
    }
    ModernFrameProfile::AdvanceTextureHash(xboxTextureHashSample, 5);
    int work = 11;
    if (load) {
        ModernFrameProfile::AdvanceTextureHash(xboxTextureHashSample, 6);
        work += 13;
    }
    ModernFrameProfile::AdvanceTextureHash(xboxTextureHashSample, 7);
    ModernFrameProfile::EndTextureHash(xboxTextureHashSample);
    return work;
}
"""

HARNESS = r"""
#include <string>
namespace ModernFrameProfile {
struct Sample { bool sampled; };
int calls = 0, begins = 0;
std::string trace;
void Begin(Sample& s, bool selected) { s.sampled = selected; ++begins; }
void AdvancePipelinePreparation(Sample& s, int phase) {
    ++calls; if (s.sampled) trace += char('0' + phase);
}
void EnterPipelineTextureImport(Sample& s) { AdvancePipelinePreparation(s, 8); }
void ExitPipelineTextureImport(Sample& s) { AdvancePipelinePreparation(s, 9); }
void EndPipelinePreparation(Sample& s) { AdvancePipelinePreparation(s, 0); }
void AdvanceTextureHash(Sample& s, int phase) { AdvancePipelinePreparation(s, phase); }
void EndTextureHash(Sample& s) { AdvancePipelinePreparation(s, 0); }
}
namespace Before { BEFORE }
namespace After { AFTER }
int main() {
    using namespace ModernFrameProfile;
    for (int selected = 0; selected < 2; ++selected)
    for (int imports = 0; imports < 3; ++imports)
    for (int missing = 0; missing < 2; ++missing)
    for (int load = 0; load < 2; ++load) {
        calls = begins = 0; trace.clear();
        int expected = Before::Pipeline(selected, imports) + Before::Texture(selected, missing, load);
        const std::string expectedTrace = trace;
        const int expectedCalls = calls;
        if (begins != 2) return 1;
        calls = begins = 0; trace.clear();
        int actual = After::Pipeline(selected, imports) + After::Texture(selected, missing, load);
        if (actual != expected || trace != expectedTrace || begins != 2) return 2;
        if (calls != (selected ? expectedCalls : 0)) return 3;
    }
    return 0;
}
"""


class ProfileCallerGuards(unittest.TestCase):
    def test_roundtrip_idempotence_and_anchor_drift(self):
        changed = transform(FIXTURE)
        self.assertEqual(remove_instrumentation(changed), FIXTURE)
        self.assertEqual(transform(changed), changed)
        with self.assertRaises(RuntimeError):
            transform(FIXTURE.replace("EndTextureHash(xboxTextureHashSample);", "Other();", 1))

    def test_compiled_sampled_and_unsampled_control_flow(self):
        compiler = shutil.which("g++") or "C:/msys64/mingw64/bin/g++.exe"
        if not Path(compiler).exists():
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "contract.cpp"
            binary = Path(directory) / "contract.exe"
            source.write_text(HARNESS.replace("BEFORE", FIXTURE).replace("AFTER", transform(FIXTURE)))
            env = dict(os.environ)
            env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
            subprocess.run([compiler, "-O2", str(source), "-o", str(binary)], check=True, env=env)
            subprocess.run([str(binary)], check=True, env=env)


if __name__ == "__main__":
    unittest.main()
