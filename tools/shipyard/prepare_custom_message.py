"""Full current CustomMessageManager implementation projection; no methods omitted."""
import argparse,hashlib,json,re,runpy,struct,subprocess
from pathlib import Path
from cpp_ast import PARSER,walk
from prepare_randomizer import ROOT,OUT as RANDOMIZER_OUT,CUSTOM,includes as randomizer_includes
OWN=ROOT/'platform/shipyard/custom-message'
OUT=ROOT/'scratch/custom-message-xdk'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def functions(text):
    return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
def edit(raw,edits):
    for a,b,v in sorted(edits,reverse=True):raw=raw[:a]+v.encode()+raw[b:]
    return raw.decode()
def literal_bytes(spelling):
    if not spelling.startswith('"'):raise ValueError('unsupported literal '+spelling)
    body=spelling[1:-1];out=bytearray();i=0
    escapes={'a':7,'b':8,'f':12,'n':10,'r':13,'t':9,'v':11,'\\':92,'"':34,"'":39,'?':63}
    while i<len(body):
        c=body[i];i+=1
        if c!='\\':out.extend(c.encode('utf-8'));continue
        c=body[i];i+=1
        if c in escapes:out.append(escapes[c])
        elif c in '01234567':
            digits=c
            while i<len(body) and len(digits)<3 and body[i] in '01234567':digits+=body[i];i+=1
            out.append(int(digits,8))
        elif c=='x':
            start=i
            while i<len(body) and body[i] in '0123456789abcdefABCDEF':i+=1
            value=int(body[start:i],16)
            if value>255:raise ValueError('multi-byte hex escape')
            out.append(value)
        elif c in 'uU':
            n=4 if c=='u' else 8;out.extend(chr(int(body[i:i+n],16)).encode('utf-8'));i+=n
        elif c=='\n':pass
        else:raise ValueError('unhandled escape '+c)
    return bytes(out)
def escape_literal(spelling):
    # Three-digit octal escapes make execution bytes independent of XDK's ACP;
    # unlike hex escapes, they cannot absorb a following hex digit.
    return '"'+''.join('\\%03o'%b for b in literal_bytes(spelling))+'"'
def lower_literals(text):
    raw=text.encode();edits=[];records=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='string_literal' or n.parent.type=='preproc_include':continue
        spelling=n.text.decode()
        # Macro expansion is audited separately for QM_WHITE and HS_HORSE_ARCHERY.
        value=literal_bytes(spelling);projected=escape_literal(spelling)
        end=n.end_byte;user=n.parent.type=='user_defined_literal'
        if user:
            suffix=raw[n.end_byte:n.parent.end_byte].decode()
            if suffix!='s':raise ValueError('unsupported user-defined string suffix '+suffix)
            end=n.parent.end_byte;projected='std::string('+projected+', '+'static_cast<size_t>('+str(len(value))+'))'
        edits.append((n.start_byte,end,projected))
        records.append(dict(original=spelling,projected=projected,bytes=value.hex(),udl=user))
    return edit(raw,edits),records

def lower_tables(text):
    raw=text.encode();edits=[];audit=[]
    for node in PARSER.parse(raw).root_node.named_children:
        if node.type!='declaration':continue
        decl=node.child_by_field_name('declarator')
        value=decl.child_by_field_name('value') if decl else None
        if value is None or value.type!='initializer_list':continue
        typ=node.child_by_field_name('type').text.decode();name=decl.child_by_field_name('declarator').text.decode()
        if name not in ['textBoxSpecialCharacters','percentColors','colorToPercent','altarIcons','pixelWidthTable']:raise ValueError('unknown table '+name)
        values=[]
        for item in value.named_children:
            if item.type=='comment':continue
            if item.type!='initializer_list' or len(item.named_children)!=2:raise ValueError('table pair grammar changed')
            values.append(typ+'::value_type('+', '.join(c.text.decode() for c in item.named_children)+')')
        const='const ' if any(c.text==b'const' for c in node.named_children) else ''
        replacement='static '+typ+' '+name+'_initialize() {\n    const '+typ+'::value_type values[] = {\n'+',\n'.join(values)+'\n    };\n    return '+typ+'(values, values + sizeof(values)/sizeof(values[0]));\n}\nstatic '+const+typ+' '+name+' = '+name+'_initialize();'
        edits.append((node.start_byte,node.end_byte,replacement));audit.append(dict(name=name,type=typ,entries=len(values),original_sha256=sha(node.text)))
    if len(audit)!=5:raise ValueError('table inventory changed')
    return edit(raw,edits),audit

def adapt_calls(text):
    raw=text.encode();edits=[];counts={'literal_to_rvalue':0,'dynamic_log_view':0,'map_insert':0}
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='call_expression':continue
        fn=n.child_by_field_name('function').text.decode();args=n.child_by_field_name('arguments')
        if fn=='Replace':
            for arg in args.named_children:
                if arg.type=='string_literal':
                    edits.append((arg.start_byte,arg.end_byte,'std::string('+arg.text.decode()+')'));counts['literal_to_rvalue']+=1
        elif fn=='SPDLOG_DEBUG' and len(args.named_children)==1:
            arg=args.named_children[0];edits.append((arg.start_byte,arg.end_byte,'spdlog::string_view_t('+arg.text.decode()+')'));counts['dynamic_log_view']+=1
        elif fn in ['messageTable.emplace','messageTables.emplace']:
            replacement=fn.replace('.emplace','.insert')+'(std::make_pair'+args.text.decode()+')'
            edits.append((n.start_byte,n.end_byte,replacement));counts['map_insert']+=1
    if counts!={'literal_to_rvalue':7,'dynamic_log_view':2,'map_insert':2}:raise ValueError('call boundary inventory changed: '+str(counts))
    return edit(raw,edits),counts

def lower_if_initializers(text):
    for iteration in range(3):
        raw=text.encode();edits=[]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type!='if_statement':continue
            condition=n.child_by_field_name('condition');init=condition.child_by_field_name('initializer')
            if init is None:continue
            if any(m.type=='if_statement' and m.child_by_field_name('condition').child_by_field_name('initializer') is not None for m in list(walk(n))[1:]):continue
            value=condition.child_by_field_name('value').text.decode()
            tail=raw[condition.end_byte:n.end_byte].decode()
            edits.append((n.start_byte,n.end_byte,'{ '+init.text.decode()+' if ('+value+')'+tail+' }'))
        if not edits:return text
        text=edit(raw,edits)
    raise ValueError('if initializer nesting changed')

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={}
    for rel,digest in lock['sources'].items():
        raw=(ROOT/rel).read_bytes()
        if sha(raw)!=digest:raise ValueError('CustomMessage source drift: '+rel)
        texts[rel]=raw.decode('utf-8-sig').replace('\r\n','\n')
    provider=json.loads((RANDOMIZER_OUT/'manifest.json').read_text())
    inputs={}
    for suffix in ['.h','.cpp']:
        rel=CUSTOM+suffix;text=(RANDOMIZER_OUT/'generated'/rel).read_text(encoding='utf-8-sig')
        if sha(text.encode())!=provider['generated'][rel]:raise ValueError('CustomMessage provider drift: '+rel)
        inputs[rel]=text
    text=inputs[CUSTOM+'.cpp']
    original_functions=[n.child_by_field_name('declarator').text.decode() for n in functions(texts[CUSTOM+'.cpp'])]
    provider_functions=[n.child_by_field_name('declarator').text.decode() for n in functions(text)]
    if original_functions!=provider_functions:raise ValueError('provider omitted or changed function signatures')
    text,calls=adapt_calls(text)
    text,tables=lower_tables(text)
    text,literals=lower_literals(text)
    text=text.replace('using namespace std::literals::string_literals;','// String literal suffixes lowered with explicit byte lengths.')
    text=text.replace('messages[language].starts_with(TODO_TRANSLATE)','Shipyard::Resources::starts_with(messages[language], TODO_TRANSLATE)')
    text=text.replace("std::erase(str, '#');", "str.erase(std::remove(str.begin(), str.end(), '#'), str.end());")
    text=text.replace('std::to_string(', 'Shipyard::CustomMessages::decimal(')
    text=lower_if_initializers(text)
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    range_count=sum(n.type=='for_range_loop' for n in walk(PARSER.parse(text.encode()).root_node))
    text=lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    text='#include "custom-message/support.h"\n'+text
    header='#pragma once\n#include "'+(RANDOMIZER_OUT/'generated'/(CUSTOM+'.h')).as_posix()+'"\n'
    for macro in ['QM_WHITE','HS_HORSE_ARCHERY']:
        spelling=re.search(r'^#define '+macro+r' ("[^"\n]*")s',texts[CUSTOM+'.h'],re.M)[1]
        value=literal_bytes(spelling)
        projected='std::string('+escape_literal(spelling)+', static_cast<size_t>('+str(len(value))+'))'
        header+='#undef '+macro+'\n#define '+macro+' '+projected+'\n'
        literals.append(dict(original=spelling,projected=projected,bytes=value.hex(),udl=True,macro=macro))
    generated=OUT/'generated';generated.mkdir(parents=True,exist_ok=True)
    outputs={'CustomMessageManager.cpp':text,'include/CustomMessageManager.h':header}
    for name,content in outputs.items():
        p=generated/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,newline='\n')
    # Compile the actual projected literal spellings to target arrays; independently
    # decoded original bytes are checked against their COFF data by the tests.
    literal_probe=''.join('extern "C" const char shipyard_message_literal_'+str(i)+'[] = '+escape_literal(r['original'])+';\n' for i,r in enumerate(literals))
    (generated/'literal_probe.cpp').write_text(literal_probe,newline='\n')
    manifest=dict(source_commit=lock['source_commit'],sources=lock['sources'],provider_inputs={k:sha(v.encode()) for k,v in inputs.items()},
        generator_sha256=sha(Path(__file__).read_bytes()),helper_sha256=sha((OWN/'support.h').read_bytes()),
        range_lowering_sha256=sha((ROOT/'platform/shipyard/imgui/projection.py').read_bytes()),
        functions=original_functions,call_boundaries=calls,tables=tables,literals=literals,range_loops=range_count,
        generated={k:sha((generated/k).read_bytes()) for k in outputs},full_native_unit='CustomMessageManager.cpp',
        host_service_exclusions=['CustomMessage::LoadVanillaMessageTableEntry','CustomMessage::GetForCurrentLanguage','CustomMessage::LoadIntoFont'])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',newline='\n')
    return manifest

def includes():return [OUT/'generated/include',ROOT/'platform/shipyard']+randomizer_includes()+[ROOT/'soh/soh/Enhancements/custom-message']
def build():
    prepare();sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK');folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    flags=['/nologo','/c','/TP','/EHsc','/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DF3DEX_GBI_2','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0','/DINCLUDE_MPQ_SUPPORT','/DCONTROLLERBUTTONS_T=uint32_t',
           '/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h'),'/FI'+str(ROOT/'platform/shipyard/game/include/xdk_math_boundary.h'),'/I'+str(sdk/'include/xbox')]+['/I'+str(p) for p in includes()]
    records=[]
    for name in ['CustomMessageManager','literal_probe']:
        source=OUT/'generated'/(name+'.cpp');obj=folder/(name+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);(folder/(name+'.log')).write_text(r.stdout+r.stderr)
        row=dict(command=command,exit=r.returncode,source_sha256=sha(source.read_bytes()))
        if name=='CustomMessageManager':row['path']=CUSTOM+'.cpp'
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=sha(obj.read_bytes())
        records.append(row);print(name+': '+str(r.returncode))
        if r.returncode:print('\n'.join(x for x in r.stdout.splitlines() if 'error ' in x)[:5000])
    (folder/'build.json').write_text(json.dumps(records,indent=2)+'\n')
    if any(r['exit'] for r in records):raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args();build() if a.build else prepare()
