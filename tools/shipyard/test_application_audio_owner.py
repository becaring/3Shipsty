"""Check that save states and the worker share the OTRAudio state."""

import json, re, runpy, subprocess
from prepare_application import ROOT, OUT, prepare
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable


def main():
    prepare()
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected in [False, True]:
        folder = OUT / ("audio-owner-projected" if projected else "audio-owner-original")
        folder.mkdir(exist_ok=True)
        header = OUT / "generated/soh" if projected else ROOT / "soh"
        definition = ""
        if projected:
            source = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
            match = re.search(r"^OTRAudioState audio;$", source, re.M)
            assert match, "Production startup must own one externally shared audio state"
            definition = match[0] + "\n"
        prefix = '#include <mutex>\n#include "soh/OTRAudio.h"\n'
        stable(
            folder / "owner.cpp",
            prefix
            + definition
            + """void* OtherState(){return &audio;}
void* OtherMutex(){return &audio.mutex;}
bool TryOther(){bool result=audio.mutex.try_lock();if(result)audio.mutex.unlock();return result;}
""",
        )
        stable(
            folder / "consumer.cpp",
            prefix
            + """#include <thread>
#include <cstdio>
#include <cassert>
extern void* OtherState();extern void* OtherMutex();extern bool TryOther();
int main(){
  bool same=OtherState()==&audio && OtherMutex()==&audio.mutex;
  assert(!audio.running && !audio.processing);
  audio.mutex.lock();bool acquired=false;
  std::thread worker([&](){acquired=TryOther();});worker.join();audio.mutex.unlock();
  printf("shared=%d acquired_while_locked=%d\\n",int(same),int(acquired));
  assert(same ? !acquired : acquired);
}
""",
        )
        command = [
            str(compiler),
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/MD",
            "/I" + str(header),
            "/I" + str(ROOT / "platform/shipyard"),
            "/I" + str(PLATFORM_BASE / "sources"),
            str(folder / "owner.cpp"),
            str(folder / "consumer.cpp"),
        ]
        if projected:
            command.append(str(PLATFORM_BASE / "sources/async/native.cpp"))
        command += ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", run.stdout + run.stderr)
        assert run.returncode == 0, folder / "build.log"
        run = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True, timeout=20)
        assert run.returncode == 0, (run.returncode, run.stderr)
        expected = "shared=1 acquired_while_locked=0" if projected else "shared=0 acquired_while_locked=1"
        assert run.stdout.strip() == expected, run.stdout
        rows.append(dict(projected=projected, command=command, stdout=run.stdout))
    stable(OUT / "audio-owner-verification.json", json.dumps(dict(host=rows, target_execution=False), indent=2) + "\n")
    print("Original separate locks reproduced; projected cross-TU state and mutual exclusion verified.")


if __name__ == "__main__":
    main()
