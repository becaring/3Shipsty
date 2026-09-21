"""Project the complete release-pinned ImGui core for XDK, preserving LUS config."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable

OWN = ROOT / 'platform/shipyard/imgui'
OUT = ROOT / 'scratch/imgui-xdk'
UNITS = ('imgui', 'imgui_draw', 'imgui_tables', 'imgui_widgets', 'imgui_demo')


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('ImGui source anchor drift: ' + before)
    return text.replace(before, after)


def prepare():
    source = verified('imgui')
    provenance = json.loads((OWN / 'provenance.json').read_text())
    locks = json.loads((OWN / 'source-lock.json').read_text())
    for relative, expected in locks['helpers'].items():
        raw = (ROOT / relative).read_text(encoding='utf-8-sig').encode()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('ImGui helper drift: ' + relative)
    for relative, expected in locks['parser'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('ImGui parser dependency drift: ' + relative)
    patch = ROOT / 'libultraship/CMake/dependencies/patches/imgui-fixes-and-config.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != provenance['current_patch_sha256']:
        raise ValueError('Release LUS ImGui patch changed')
    projection = runpy.run_path(str(OWN / 'projection.py'))
    outputs = {}; originals = {}
    for path in sorted(source.iterdir()):
        if path.suffix not in ('.h', '.cpp'): continue
        text = path.read_text(encoding='utf-8-sig')
        if path.name == 'imconfig.h':
            text = once(text, '//#define IMGUI_DEFINE_MATH_OPERATORS', '#define IMGUI_DEFINE_MATH_OPERATORS')
            text += '\n// handle https://github.com/ocornut/imgui/issues/1641 the old way\n#define ImTextureID void*\n'
        originals[path.name] = text
        if path.name == 'imconfig.h':
            text += '\n#ifdef _XBOX\n#define IMGUI_DISABLE_WIN32_FUNCTIONS\n#define IMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS\n#endif\n'
        if path.name in ('imgui.h', 'imgui_internal.h'):
            text = projection['enum_definitions_before_use'](text)
            text = re.sub(r'\bconstexpr\s+', '', text)
        if path.name.startswith('imgui'):
            text = projection['default_members'](text)
            text = projection['callback_lambdas'](text)
            text = projection['lower_ranges'](text.encode()).decode()
        if path.name == 'imgui_internal.h':
            anchor = '    ImGuiID             WindowID;\n};'
            text = once(text, anchor, anchor + '\ninline ImGuiFocusScopeData ShipyardFocusScope(ImGuiID id, ImGuiID window) { ImGuiFocusScopeData result = { id, window }; return result; }')
        if path.name == 'imgui.cpp':
            text = once(text, 'g.NavFocusRoute.push_back({ focus_scope_id, g.NavWindow->ID });', 'g.NavFocusRoute.push_back(ShipyardFocusScope(focus_scope_id, g.NavWindow->ID));')
            text = once(text, 'g.NavFocusRoute.push_back({ window->NavRootFocusScopeId, window->ID });', 'g.NavFocusRoute.push_back(ShipyardFocusScope(window->NavRootFocusScopeId, window->ID));')
        if path.name == 'imgui_demo.cpp':
            text = once(text, 'ExampleTreeNodeMemberInfos[]\n{', 'ExampleTreeNodeMemberInfos[] =\n{')
            text = once(text, 'static ImVec4 col4 = { 1.0f, 0.0f, 0.2f, 1.0f };', 'static ImVec4 col4(1.0f, 0.0f, 0.2f, 1.0f);')
            text = once(text, 'sizeof(ExampleTreeNode::Name)', 'sizeof(((ExampleTreeNode*)0)->Name)')
            text = once(text, 'ImVec2 button_sz = { ImGui::GetFrameHeight(), ImGui::GetFrameHeight() };', 'ImVec2 button_sz(ImGui::GetFrameHeight(), ImGui::GetFrameHeight());')
            match = re.search(r'const ImVec2 pos_norms\[\] = \{ (.*?) \};', text)
            if not match: raise ValueError('ImGui demo shape drift')
            converted = re.sub(r'\{ ([^{}]+) \}', r'ImVec2(\1)', match[1])
            text = text[:match.start(1)] + converted + text[match.end(1):]
        if path.name == 'imgui.h':
            text += '\n#include "range.h"\n'
        outputs[path.name] = '// Generated from ' + path.relative_to(ROOT).as_posix() + '; do not edit.\n' + text
    for name, text in outputs.items(): stable(OUT / 'generated' / name, text)
    for name, text in originals.items(): stable(OUT / 'original' / name, text)
    stable(OUT / 'generated/range.h', (OWN / 'range.h').read_text())
    manifest = dict(units=list(UNITS), patch_sha256=provenance['current_patch_sha256'],
                    outputs={name: hashlib.sha256(text.encode()).hexdigest() for name, text in sorted(outputs.items())})
    stable(OUT / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    return manifest


def compile_xdk(original=False):
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    label = 'original' if original else 'generated'
    output = OUT / ('xdk-' + label); output.mkdir(parents=True, exist_ok=True)
    records = []
    for unit in UNITS:
        obj = output / (unit + '.obj')
        command = [str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/TP', '/EHsc', '/GR', '/MT', '/W3', '/D_XBOX', '/DNOMINMAX',
                   '/I' + str(sdk / 'include/xbox'), '/I' + str(OUT / label),
                   str(OUT / label / (unit + '.cpp')), '/Fo' + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(output / (unit + '.log'), result.stdout + result.stderr)
        records.append(dict(unit=unit, exit=result.returncode, command=command))
        if result.returncode == 0 and struct.unpack_from('<H', obj.read_bytes())[0] != 0x1f2:
            raise ValueError('Not a Xenon object')
        print(unit, result.returncode)
    stable(output / 'report.json', json.dumps(records, indent=2) + '\n')
    if any(r['exit'] for r in records): raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--raw-probe', action='store_true')
    args = parser.parse_args()
    prepare()
    if args.compile or args.raw_probe: compile_xdk(args.raw_probe)
