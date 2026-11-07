"""Compare the debugger and tracker tables and check that application registrations are preserved."""

import hashlib, json, runpy, subprocess, struct
from pathlib import Path
from prepare_application_gui import ROOT, OWN, OUT, BASE, prepare
from prepare_archives import stable
from cpp_ast import PARSER, walk


def main():
    prepare()
    env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
    compiler, environment = env["host_environment"]()
    results = []
    # These are the namespace-scope application tables. Exclude classes,
    # whose service-backed methods need the linked application to execute.
    for projected in [False, True]:
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        base = OUT / "generated" if projected else ROOT
        text = '#include <map>\n#include <vector>\n#include <string>\n#include <cstdio>\n#include "soh/Enhancements/randomizer/randomizerTypes.h"\n'
        debug = (base / "soh/soh/Enhancements/debugger/debugSaveEditor.h").read_text(encoding="utf-8")
        text += debug[debug.index("typedef enum") : debug.index("class SaveEditorWindow")]
        tracker = (base / "soh/soh/Enhancements/randomizer/randomizer_item_tracker.h").read_text(encoding="utf-8")
        start = (
            tracker.index("static std::vector<const char*> ShipyardBuild_")
            if projected
            else tracker.index("static std::vector<const char*> itemTrackerWindowIDs")
        )
        text += tracker[start : tracker.index("void ItemTracker_LoadFromPreset")]
        entrance = (base / "soh/soh/Enhancements/randomizer/randomizer_entrance_tracker.h").read_text(encoding="utf-8")
        start = (
            entrance.index("static std::map<int32_t, const char*> MakewindowType")
            if projected
            else entrance.index("static std::map<int32_t, const char*> windowType")
        )
        text += entrance[start : entrance.index("static const Color_RGBA8")]
        text += """
int main(){
for(size_t i=0;i<flagTables.size();++i){const FlagTable& t=flagTables[i];
printf("%s %u %u %u\\n",t.name,unsigned(t.flagTableType),unsigned(t.size),unsigned(t.flagDescriptions.size()));
for(std::map<uint16_t,const char*>::const_iterator j=t.flagDescriptions.begin();j!=t.flagDescriptions.end();\
++j)printf("%u %s\\n",unsigned(j->first),j->second);}
const std::vector<std::string>* states[]={&state1,&state2,&state3};
for(size_t s=0;s<3;++s)for(size_t i=0;i<states[s]->size();++i)printf("%u %u %s\\n",unsigned(s),unsigned(i),\
states[s]->at(i).c_str());
for(size_t i=0;i<itemTrackerWindowIDs.size();++i)printf("%u %s\\n",unsigned(i),itemTrackerWindowIDs[i]);
const std::map<int32_t,const char*>* maps[]={&windowType,&showMode,&buttonStrings};
for(size_t m=0;m<3;++m)for(std::map<int32_t,const char*>::const_iterator i=maps[m]->begin();i!=maps[m]->end();\
++i)printf("%u %d %s\\n",unsigned(m),i->first,i->second);
return 0;}
"""
        stable(folder / "tables.cpp", text)
        flags = json.loads((ROOT / "scratch/soh-ui-xdk/host-projected/run.json").read_text())["command"]
        command = [
            str(compiler),
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/MD",
            "/DF3DEX_GBI_2",
            "/I" + str(ROOT / "scratch/game-xdk/full/source/soh"),
            "/I" + str(ROOT / "scratch/game-xdk/full/source/soh/include"),
        ] + [f for f in flags if f.startswith("/I")]
        command += [str(folder / "tables.cpp"), "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "tables.exe")]
        r = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        stable(folder / "build.log", r.stdout + r.stderr)
        assert r.returncode == 0, folder / "build.log"
        r = subprocess.run([str(folder / "tables.exe")], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0
        results.append(dict(command=command, stdout=r.stdout, exit=r.returncode))
    assert results[0]["stdout"] == results[1]["stdout"]
    original = (ROOT / (BASE + "SohGui.cpp")).read_text()
    projected = (OUT / "generated" / (BASE + "SohGui.cpp")).read_text()
    bodies = lambda text: {
        n.child_by_field_name("declarator").text.decode(): n.child_by_field_name("body").text.decode()
        for n in walk(PARSER.parse(text.encode()).root_node)
        if n.type == "function_definition"
    }
    before, after = bodies(original), bodies(projected)
    assert all(after[name] == body for name, body in before.items())
    registrations = original.count("gui->AddGuiWindow(")
    assert registrations == projected.count("gui->AddGuiWindow(")
    first = json.loads((OUT / "manifest.json").read_text())["generated"]
    prepare()
    assert first == json.loads((OUT / "manifest.json").read_text())["generated"]
    flags = json.loads((OUT / "xdk/build.json").read_text())[0]["command"][:-2]
    obj = OUT / "xdk/tables.obj"
    command = flags + [str(OUT / "host-projected/tables.cpp"), "/Fo" + str(obj)]
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), r.stdout + r.stderr)
    assert r.returncode == 0, obj.with_suffix(".log")
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=results,
                native_tables=command,
                unchanged_application_function_bodies=len(before),
                registrations=registrations,
                native_ui_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(
        str(len(results[0]["stdout"].splitlines()))
        + " exact table rows match; "
        + str(len(before))
        + " original application function bodies unchanged, "
        + str(registrations)
        + " real registrations retained"
    )


if __name__ == "__main__":
    main()
