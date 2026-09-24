"""Actual application extras data and serialization parity, plus full source/native checks."""
import collections,hashlib,json,re,runpy,subprocess
from prepare_application_extras import ROOT,OUT,OWN,prepare,includes
from prepare_archives import stable
from test_gameplay_features import read,structure,inventory
from cpp_ast import PARSER,walk
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE=resolve_platform_base(ROOT)
BASE='soh/soh/Enhancements/'
def method(text,name):
 return next(n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator').text.decode().split('(')[0].lstrip('* ')==name)
def decl(text,name):
 for n in walk(PARSER.parse(text.encode()).root_node):
  if n.type!='declaration':continue
  if n.child_by_field_name('declarator') is not None and n.child_by_field_name('declarator').text.decode()==name:return n.text.decode()
  for c in n.named_children:
   if c.type=='init_declarator' and c.child_by_field_name('declarator').text.decode().split('[')[0]==name:return n.text.decode()
 raise ValueError(name)
def helpers(text,pattern):
 return '\n'.join(n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition' and re.match(pattern,n.child_by_field_name('declarator').text.decode()))+'\n'
def commands(text,projected):
 result={}
 for n in walk(PARSER.parse(text.encode()).root_node):
  if n.type!='call_expression':continue
  fn=n.child_by_field_name('function').text.decode()
  if fn!='CMD_REGISTER' and not fn.endswith('->AddCommand'):continue
  args=n.child_by_field_name('arguments').named_children;assert len(args)==2
  fields=args[1]
  if projected:
   assignments={x.child_by_field_name('left').text.decode():x.child_by_field_name('right').text.decode() for x in walk(fields) if x.type=='assignment_expression'}
   handler=assignments['entry.Handler'];description=assignments['entry.Description']
   parameters=[x.child_by_field_name('arguments').text.decode()[1:-1].replace(' ','') for x in walk(fields) if x.type=='call_expression' and x.child_by_field_name('function').text==b'Ship::CommandArgument']
  else:
   values=[x for x in fields.named_children if x.type!='comment'];handler=values[0].text.decode();description=values[1].text.decode();parameters=[]
   if len(values)==3:
    parameters=[','.join(x.text.decode() for x in row.named_children if x.type!='comment').replace(' ','') for row in values[2].named_children if row.type!='comment']
  result[args[0].text.decode()]=(handler,description,parameters)
 return result
def main():
 units=prepare();original={n:read(ROOT/n) for n in units};projected={n:read(OUT/'generated'/n) for n in units}
 inventories={}
 for n in units:
  try:inventories[n]=inventory(original[n],projected[n])
  except AssertionError as e:raise AssertionError(n+': '+str(e))
 console=BASE+'debugconsole.cpp';command_inventory=commands(original[console],False);assert command_inventory==commands(projected[console],True);assert len(command_inventory)>40
 compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();rows=[]
 for is_projected in (False,True):
  folder=OUT/('host-projected' if is_projected else 'host-original');folder.mkdir(exist_ok=True);texts=projected if is_projected else original
  def src(n):return texts[BASE+n+'.cpp']
  prefix='#include <cassert>\n#include <iostream>\n#include <vector>\n#include <map>\n#include <array>\n#include <string>\n#include <cstring>\n#include <algorithm>\n#include <nlohmann/json.hpp>\n#include "resources/runtime_support.h"\n#include "z64.h"\n#include "soh/cvar_prefixes.h"\n#include "soh/Enhancements/boss-rush/BossRush.h"\n#include "soh/Enhancements/Presets/Presets.h"\n#include "soh/Enhancements/timesplits/TimeSplits.h"\n#include "ship/window/gui/IconsFontAwesome4.h"\n#include "application-windows/support.h"\n'
  data=prefix
  boss=src('boss-rush/BossRush');data+=structure(boss,'BossRushSetting')+'\n'+helpers(boss,'Shipyard_BossRushOptions_')+decl(boss,'BossRushOptions')+'\n'
  data+='\n'.join(method(boss,f) for f in ('BossRush_GetSettingName','BossRush_GetSettingChoiceName','BossRush_GetSettingOptionsAmount'))+'\n'
  preset=src('Presets/Presets');data+=structure(preset,'BlockInfo')+'\n'+structure(preset,'PresetInfo')+'\n'+helpers(preset,'Shipyard_blockInfo_')+decl(preset,'blockInfo')+'\n'+decl(preset,'presets')+'\n'+method(preset,'ParsePreset')+'\n'
  split=src('timesplits/TimeSplits');data+='\n'.join(re.findall(r'^#define COLOR_[^\n]+',split,re.M))+'\n'+helpers(split,'(?:Shipyard_popupList_|_Build_(?:popupList|splitObjectList))')
  data+=decl(split,'splitObjectList')+'\n'+decl(split,'popupList')+'\n'
  data+='\n'.join(method(split,f) for f in ('ImVec4_to_json','json_to_ImVec4','SplitObject_to_json','json_to_SplitObject','removeSpecialCharacters'))+'\n'
  data+=(OWN/'data_contract.cpp').read_text();stable(folder/'data.cpp',data)
  command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/O2','/Gy','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h')]
  if not is_projected:command+=['/Zc:preprocessor','/I'+str(ROOT/'platform/shipyard/json/upstream/include')]
  command+=['/I'+str(p) for p in includes()]+[str(folder/'data.cpp')]
  if is_projected:command+=[str(PLATFORM_BASE/'sources/json/json.cpp')]
  command+=['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'data.exe'),'/link','/OPT:REF']
  r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'data-build.log',r.stdout+r.stderr);assert not r.returncode,folder/'data-build.log'
  r=subprocess.run([str(folder/'data.exe')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8');row=dict(projected=is_projected,command=command,exit=r.returncode,stdout=r.stdout,stderr=r.stderr);rows.append(row);assert not r.returncode,row
 assert rows[0]['stdout']==rows[1]['stdout'],'Original/projected application data/serialization differs'
 native=json.loads((OUT/'xdk/build.json').read_text());assert len(native)==13
 for row in native:
  assert not row['exit'],row['path'];assert row['source_sha256']==hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest(),row['path'];assert row['object_sha256']==hashlib.sha256((ROOT/row['object']).read_bytes()).hexdigest()
 before=read(OUT/'manifest.json');prepare();assert read(OUT/'manifest.json')==before
 stable(OUT/'verification.json',json.dumps(dict(inventories=inventories,console_commands=command_inventory,host=rows,native=native,reproducible=True,native_application_executed=False),indent=2)+'\n');print('13 full source/native inventories and original/projected application data contracts pass.')
if __name__=='__main__':main()
