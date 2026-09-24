from pathlib import Path
import difflib,hashlib,re,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"scratch/python-tools"))
import tree_sitter as ts
import tree_sitter_cpp
PARSER=ts.Parser(ts.Language(tree_sitter_cpp.language()))

def walk(node):
    yield node
    for child in node.named_children:yield from walk(child)

def tx(node):return node.text.decode()

def field(node,name):return node.child_by_field_name(name)

def braces(text):
    data=text.encode();edits=[]
    for node in walk(PARSER.parse(data).root_node):
        if node.type=='compound_literal_expression':
            val=field(node,'value')
            if val and val.type=='initializer_list':
                edits.extend(((val.start_byte,val.start_byte+1,b'('),(val.end_byte-1,val.end_byte,b')')))
        elif node.type=='new_expression':
            val=next((n for n in node.named_children if n.type=='initializer_list'),None)
            if val:edits.extend(((val.start_byte,val.start_byte+1,b'('),(val.end_byte-1,val.end_byte,b')')))
    for a,b,value in sorted(set(edits),reverse=True):data=data[:a]+value+data[b:]
    return data.decode()

def enum_wrappers(text):
    def lower(match):
        name,body=match[1],match[2]
        return 'struct '+name+' { enum Value {'+body+'}; Value value; '+name+'(Value v) : value(v) {} operator Value() const { return value; } };'
    return re.sub(r'enum class (\w+)\s*\{([^}]+)\};',lower,text)

def mapped(source_path,text,output):
    original=(ROOT/source_path).read_text(encoding='utf-8-sig').splitlines(keepends=True)
    changed=text.splitlines(keepends=True);origins={}
    for block in difflib.SequenceMatcher(None,original,changed,autojunk=False).get_matching_blocks():
        for i in range(block.size):origins[block.b+i]=block.a+i+1
    destination=str(output.relative_to(ROOT)).replace('\\','/')
    result=[];guard=None
    if output.suffix=='.h':
        guard='SHIPYARD_PRISM_'+hashlib.sha256(destination.encode()).hexdigest().upper()
        result=['#ifndef '+guard+'\n','#define '+guard+'\n']
    comment=False;quote=None;continuation=False;last_file=None;last_line=0
    for index,current in enumerate(changed):
        filename=source_path if index in origins else destination
        number=origins.get(index,len(result)+2)
        if not comment and not quote and not continuation and (filename!=last_file or number!=last_line+1):
            result.append('#line %d "%s"\n'%(number,filename));last_file=filename;last_line=number-1
        result.append(current);last_line+=1
        cursor=0
        while cursor<len(current):
            pair=current[cursor:cursor+2];char=current[cursor]
            if comment:
                if pair=='*/':comment=False;cursor+=2;continue
            elif quote:
                if char=='\\':cursor+=2;continue
                if char==quote:quote=None
            elif pair=='//':break
            elif pair=='/*':comment=True;cursor+=2;continue
            elif char in ('"',"'"):quote=char
            cursor+=1
        continuation=current.rstrip('\r\n').endswith('\\')
    if guard:result.append('\n#endif\n')
    output.parent.mkdir(parents=True,exist_ok=True)
    content=''.join(result).encode('utf-8')
    # Shared consumers may currently have unchanged generated headers open.
    # Deterministic regeneration need not rewrite those bytes or their mtimes.
    if not output.is_file() or output.read_bytes()!=content:
        output.write_bytes(content)

def lower_ranges(source,begin='Smash360Config::Begin',end='Smash360Config::End'):
    for iteration in range(64):
        edits=[]
        for node in walk(PARSER.parse(source).root_node):
            if node.type!='for_range_loop':continue
            if any(n.type=='for_range_loop' for n in list(walk(node))[1:]):continue
            right=node.child_by_field_name('right');body=node.child_by_field_name('body');decl=node.child_by_field_name('declarator')
            if right.type=='initializer_list':raise ValueError('Unaudited initializer-list range')
            opening=next(n for n in node.children if n.type=='(')
            declaration=source[opening.end_byte:decl.end_byte].decode().strip()
            if '[' in declaration:raise ValueError('Structured-binding range must be lowered explicitly first')
            suffix=str(node.start_byte);rng='_configRange'+suffix;it='_configIt'+suffix;stop='_configEnd'+suffix
            inner=body.text.decode()[1:-1] if body.type=='compound_statement' else body.text.decode()
            replacement='{ auto&& '+rng+' = '+right.text.decode()+'; auto '+it+' = '+begin+'('+rng+'); auto '+stop+' = '+end+'('+rng+'); for (; '+it+' != '+stop+'; ++'+it+') { '+declaration+' = *'+it+'; '+inner+' } }'
            edits.append((node.start_byte,node.end_byte,replacement.encode()))
        if not edits:return source
        for start,stop,value in sorted(edits,reverse=True):source=source[:start]+value+source[stop:]
    raise ValueError('Unexpected range nesting')
