"""Original/current packet JSON contracts, including in-place partial updates."""
import collections,hashlib,json,re,runpy,subprocess
from prepare_network_app import ROOT,OUT,OWN,BASE,prepare,includes
from prepare_archives import stable
from prepare_randomizer_item import methods
from prepare_custom_message import literal_bytes,escape_literal
from cpp_ast import PARSER,walk
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE=resolve_platform_base(ROOT)

def name(n):return n.child_by_field_name('declarator').text.decode().split('(')[0].lstrip('*& ')
def main():
    units=prepare();inventory={}
    for p in units:
        a=(ROOT/p).read_text(encoding='utf-8-sig');b=(OUT/'generated'/p).read_text(encoding='utf-8')
        old=collections.Counter(name(n) for n in methods(a));new=collections.Counter(name(n) for n in methods(b));assert not old-new,(p,old-new)
        literals=[n.text.decode() for n in walk(PARSER.parse(a.encode()).root_node) if n.type=='string_literal' and any(c>=128 for c in n.text)]
        for s in literals:
            escaped=escape_literal(s);assert escaped in b;assert literal_bytes(s)==literal_bytes(escaped)
        def keys(t):return collections.Counter(n.text.decode() for n in walk(PARSER.parse(t.encode()).root_node) if n.type=='string_literal' and n.parent.type!='preproc_include')
        # Original string keys, messages and CVar literals are retained. Source
        # location helpers may add filenames, but no original strings disappear.
        before=collections.Counter(escape_literal(s) if any(ord(c)>127 for c in s) else s for s in keys(a).elements())
        assert not before-keys(b),(p,before-keys(b))
        inventory[p]=dict(functions=sum(old.values()),utf8_literals=len(literals))
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();runs=[]
    anchor=(ROOT/BASE/'Anchor/Anchor.h').read_text();client=re.search(r'typedef struct \{[\s\S]*?\} AnchorClient;',anchor)[0]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        root=OUT/'generated' if projected else ROOT
        header=(root/BASE/'Anchor/JsonConversions.hpp').read_text(encoding='utf-8-sig')
        header=re.sub(r'^\s*#include[^\n]*\n','',header,flags=re.M)
        source='#include <cstdio>\n#include <cassert>\n#include <cstring>\n#include "input/compiler.h"\n#include "z64.h"\n#include "randomizer-context/colors.h"\n#include <nlohmann/json.hpp>\n'+client+'\n'+header+'\n'+(OWN/'json_contract.cpp').read_text()
        stable(folder/'contract.cpp',source)
        roots=[PLATFORM_BASE/'sources/json/include' if projected else ROOT/'platform/shipyard/json/upstream/include']+includes()
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/O2','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t']+['/I'+str(p) for p in roots]+[str(folder/'contract.cpp')]
        if projected:command.append(str(PLATFORM_BASE/'sources/json/json.cpp'))
        command+=['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',r.stdout+r.stderr);assert not r.returncode,folder/'build.log'
        r=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True);assert not r.returncode,(r.stdout,r.stderr)
        (folder/'values.txt').write_bytes(r.stdout);runs.append(dict(projected=projected,command=command,exit=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),lines=len(r.stdout.splitlines())))
    assert runs[0]['stdout_sha256']==runs[1]['stdout_sha256']
    native=json.loads((OUT/'xdk/build.json').read_text())
    assert len(native)==len(units)
    for row in native:
        assert row['exit']==0 and row['source_sha256']==hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest()
        obj=OUT/'xdk'/(ROOT/row['source']).with_suffix('.obj').name
        assert row['object_sha256']==hashlib.sha256(obj.read_bytes()).hexdigest()
    stable(OUT/'json-verification.json',json.dumps(dict(inventory=inventory,host=runs,native=native,native_application_executed=False),indent=2)+'\n')
    print('Actual packet conversion outputs and partial-update behavior agree:',runs[0]['lines'],'lines')
if __name__=='__main__':main()
