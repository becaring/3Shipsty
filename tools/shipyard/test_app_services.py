"""Actual ActorDB entry/table differential and unchanged migration source audit."""
import hashlib
import json
import re
import runpy
import subprocess
from prepare_app_services import ROOT,OUT,OWN,prepare,includes
from prepare_soh_resources import includes as resource_includes
from prepare_archives import stable
from cpp_ast import PARSER,walk

def main():
    prepare();compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();records=[]
    migration='soh/soh/config/ConfigUpdaters.cpp'
    assert (ROOT/migration).read_text()==(OUT/'generated'/migration).read_text()
    original=(ROOT/'soh/soh/ActorDB.cpp').read_text();generated=(OUT/'generated/soh/soh/ActorDB.cpp').read_text()
    table=lambda t:re.search(r'actorDescriptionData\[\] = \{([\s\S]+?)\n\};',t)[1]
    assert table(original)==table(generated)
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else ROOT
        stable(folder/'ActorDB.h',(base/'soh/soh/ActorDB.h').read_text())
        text=generated if projected else original
        methods=[n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition' and 'ActorDB::Entry::' in n.text.decode().split('{',1)[0]]
        assert len(methods)==5
        # These ownership methods are unchanged; no actor globals or game
        # services are substituted to run the bounded contract.
        for method in methods:assert method in original
        start=text.index('struct ActorDescriptionPair') if projected else text.index('static constexpr std::pair<u16, const char*> actorDescriptionData')
        end=text.index('\nActorDB::ActorDB()',start)
        source=folder/'contract.cpp'
        stable(source,'#include "ActorDB.h"\n'+text[start:end]+'\n'+'\n'.join(methods)+'\n'+(OWN/'actor_contract.cpp').read_text())
        paths=[folder]+(includes() if projected else resource_includes(False))
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/DNOMINMAX','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t']
        if not projected:command+=['/Zc:preprocessor']
        command+=['/I'+str(p) for p in paths]+[str(source),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
        assert result.returncode==0,folder/'build.log'
        result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
        row=dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);stable(folder/'run.json',json.dumps(row,indent=2)+'\n');records.append(row)
        assert result.returncode==0,row
    assert records[0]['stdout']==records[1]['stdout']
    stable(OUT/'verification.json',json.dumps(dict(host=records,actor_description_rows=len(re.findall(r'\{ ACTOR_',table(original))),configuration_migration_cpp_unchanged=True,migration_sha256=hashlib.sha256((ROOT/migration).read_text().encode()).hexdigest(),actual_game_registry_initialized=False,target_runtime_executed=False),indent=2)+'\n')
    print('Actual ActorDB descriptions/defaults/Entry ownership differential passed; complete migration source unchanged')
if __name__=='__main__':main()
