"""Inventory the fmt/spdlog calls with source hashes; types are never inferred."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scratch/python-tools'))
import tree_sitter as ts
import tree_sitter_cpp
PARSER=ts.Parser(ts.Language(tree_sitter_cpp.language()))
def walk(n):
    yield n
    for c in n.named_children:yield from walk(c)
def audit():
    records=[];sources={}
    for top in ('soh','libultraship/src','libultraship/include'):
        for path in sorted((ROOT/top).rglob('*')):
            if path.suffix not in ('.cpp','.h','.hpp','.c'):continue
            data=path.read_bytes()
            if b'fmt::' not in data and b'SPDLOG_' not in data and b'spdlog::' not in data:continue
            rel=path.relative_to(ROOT).as_posix()
            for n in walk(PARSER.parse(data).root_node):
                if n.type!='call_expression':continue
                fn=n.child_by_field_name('function');args=n.child_by_field_name('arguments')
                if not fn or not args:continue
                name=fn.text.decode()
                if not(name.startswith('fmt::') or name.startswith('SPDLOG_') or name.startswith('spdlog::')):continue
                category='diagnostic'
                if name.startswith('fmt::'):
                    category='application-format-needs-typed-review'
                    if '/gfx_metal.cpp' in rel or '/SAPISpeechSynthesizer.cpp' in rel:category='desktop-transport'
                    elif rel.endswith('OTRGlobals.cpp'):category='host-extraction-progress'
                    elif '/Presets/' in rel:category='preset-path-key-or-ui'
                    elif rel.endswith('spoiler_log.cpp'):category='randomizer-serialized-sphere-key'
                    elif any(x in rel for x in ('TimeDisplay','TimeSplits','gameplaystats')):category='gameplay-stats-ui'
                records.append(dict(path=rel,line=n.start_point.row+1,call=name,arguments=args.text.decode(),category=category))
                sources[rel]=hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()
    result=dict(status='AST call inventory, not a type proof or reachability claim',sources=sources,calls=records)
    path=ROOT/'scratch/logging-xdk/consumer-inventory.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print('Inventoried',len(records),'calls; direct fmt',sum(r['call'].startswith('fmt::') for r in records))
    return result
if __name__=='__main__':audit()
