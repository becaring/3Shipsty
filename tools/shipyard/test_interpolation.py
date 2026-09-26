"""Full native TU plus bounded original/projected math and record methods."""
import json
import re
import runpy
import subprocess
from collections import Counter
from prepare_interpolation import ROOT,OUT,OWN,prepare
from prepare_archives import stable
from cpp_ast import PARSER,walk
from prepare_binary import PLATFORM_BASE

def verify_return_ownership(original, projected, compiler, env):
    records = []
    for label, text, copies in [('original', original, 1), ('projected', projected, 0)]:
        entries = [node.text.decode() for node in walk(PARSER.parse(text.encode()).root_node)
                   if node.type == 'function_definition'
                   and node.child_by_field_name('declarator').text.decode().startswith('FrameInterpolation_Interpolate(')]
        assert len(entries) == 1
        folder = OUT / ('return-' + label)
        folder.mkdir(exist_ok=True)
        fixture = (OWN / 'return_contract.cpp').read_text()
        stable(folder / 'contract.cpp', fixture.replace('// EXTRACTED_ENTRY', entries[0]))
        command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2',
                   '/DEXPECTED_COPY_FACTOR=' + str(copies), str(folder / 'contract.cpp'),
                   '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')]
        build = subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True)
        stable(folder / 'build.log', build.stdout + build.stderr)
        assert build.returncode == 0, build.stdout + build.stderr
        result = subprocess.run([str(folder / 'contract.exe')], cwd=folder, capture_output=True, text=True)
        record = dict(label=label, command=command, exit=result.returncode,
                      stdout=result.stdout, stderr=result.stderr)
        records.append(record)
        stable(OUT / 'return-verification.json', json.dumps(records, indent=2) + '\n')
        assert result.returncode == 0, str(record)
    return records

def main():
    prepare();manifest=(OUT/'manifest.json').read_bytes();prepare();assert manifest==(OUT/'manifest.json').read_bytes()
    original=(ROOT/'soh/soh/frame_interpolation.cpp').read_text();projected=(OUT/'generated/soh/soh/frame_interpolation.cpp').read_text()
    def functions(text):return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
    def inventory(text):return Counter(n.child_by_field_name('declarator').text.decode().split('(')[0].split()[-1] for n in functions(text))
    a,b=inventory(original),inventory(projected);assert all(b[k]>=v for k,v in a.items())
    changed={'append','interpolate_branch','FrameInterpolation_StartRecord','FrameInterpolation_RecordOpenChild',
             'FrameInterpolation_Interpolate'}
    changed.update(n for n in a if n.startswith('FrameInterpolation_RecordMatrix'))
    unchanged=[]
    for node in functions(original):
        name=node.child_by_field_name('declarator').text.decode().split('(')[0].split()[-1]
        if name not in changed:assert node.text in projected.encode(),name;unchanged.append(name)
    environment=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'));compiler,env=environment['host_environment']()
    verify_return_ownership(original, projected, compiler, env)
    records=[];outputs=[]
    for generated,text in ((False,original),(True,projected)):
        folder=OUT/('host-projected' if generated else 'host-original');folder.mkdir(exist_ok=True)
        if not generated:
            # Existing bridge body is separately hash-verified as exact forwarding.
            text=text.replace('#include "soh/OTRGlobals.h"','extern "C" uint32_t Ship_GetInterpolationFPS();').replace('OTRGlobals::Instance->GetInterpolationFPS()','Ship_GetInterpolationFPS()')
            text=text.replace('#include <libultraship/bridge.h>','// Unused LUS umbrella include omitted for host contract.')
        # Host-only pure-method audit: remove service-dependent functions instead
        # of inventing OTR/matrix implementations. Production generation retains
        # every one, as checked above and by complete native TU compilation.
        excluded={'interpolate_branch','FrameInterpolation_Interpolate','FrameInterpolation_StartRecord',
                  'FrameInterpolation_RecordMatrixSetTranslateRotateYXZ','FrameInterpolation_RecordMatrixToMtx'}
        source=text.encode();edits=[]
        for node in functions(text):
            name=node.child_by_field_name('declarator').text.decode().split('(')[0].split()[-1]
            if name in excluded:edits.append((node.start_byte,node.end_byte))
        assert len(edits)==5
        for a,b in sorted(edits,reverse=True):source=source[:a]+source[b:]
        text=source.decode()
        stable(folder/'contract.cpp',text+'\n'+(OWN/'contract.cpp').read_text())
        includes=[ROOT/'soh/soh',ROOT/'soh',ROOT/'soh/include',ROOT/'libultraship/include',ROOT/'platform/shipyard',PLATFORM_BASE/'sources']
        if generated:includes=[ROOT/'scratch/resources-xdk/generated/include',ROOT/'scratch/binary-xdk/generated/include']+includes
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/Gy','/O2','/fp:precise','/DF3DEX_GBI_2','/DNOMINMAX']
        command+=['/I'+str(p) for p in includes]+[str(folder/'contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe'),'/link','/OPT:REF']
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('See '+str(folder/'build.log'))
        result=subprocess.run([str(folder/'contract.exe')],cwd=folder,capture_output=True,text=True)
        record=dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);stable(folder/'run.json',json.dumps(record,indent=2)+'\n')
        if result.returncode:raise RuntimeError(str(record))
        records.append(record);outputs.append(result.stdout)
    assert outputs[0]==outputs[1]
    stable(OUT/'verification.json',json.dumps(dict(cases=records,unchanged_methods=unchanged,whole_frame_execution=False,target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0])
if __name__=='__main__':main()
