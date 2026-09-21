"""Generic Prism syntax projection derived from the inspected Smash360 generator.
No BattleShip shader builder or application rules are included.
"""
import re,json
from cpp_ast import PARSER
from prepare_configuration import once

def walk(node):
    yield node
    for child in node.named_children:yield from walk(child)


def tx(node):return node.text.decode()
def field(node,name):return node.child_by_field_name(name)


def lower_ranges(source):
    # Derived from imported cpp_range_lower.py. Unlike that donor, cache the
    # range end once, as C++ range-for requires. No source reference dependency.
    for iteration in range(64):
        nodes=[n for n in walk(PARSER.parse(source).root_node) if n.type=='for_range_loop']
        edits=[]
        for node in nodes:
            if any(n.type=='for_range_loop' for n in list(walk(node))[1:]):continue
            right=field(node,'right');body=field(node,'body');decl=field(node,'declarator')
            opening=next(n for n in node.children if n.type=='(')
            declaration=source[opening.end_byte:decl.end_byte].decode().strip()
            suffix=str(node.start_byte);rng='_prismRange'+suffix;it='_prismIt'+suffix;end='_prismEnd'+suffix
            if right.type=='initializer_list':raise ValueError('Unaudited initializer-list range')
            inner=tx(body)[1:-1] if body.type=='compound_statement' else tx(body)
            value='{ auto&& '+rng+' = '+tx(right)+'; auto '+it+' = PrismBegin('+rng+'); auto '+end+' = PrismEnd('+rng+'); for (; '+it+' != '+end+'; ++'+it+') { '+declaration+' = *'+it+'; '+inner+' } }'
            edits.append((node.start_byte,node.end_byte,value.encode()))
        if not edits:return source
        for a,b,value in sorted(edits,reverse=True):source=source[:a]+value+source[b:]
    raise ValueError('Unexpected range nesting')


def aggregates(text):
    """Add value-preserving constructors only to pure data AST node structs."""
    data=text.encode();edits=[]
    for node in walk(PARSER.parse(data).root_node):
        if node.type!='struct_specifier':continue
        name=field(node,'name');body=field(node,'body')
        if not name or not body:continue
        members=[n for n in body.named_children if n.type!='comment']
        if not members or any(n.type!='field_declaration' for n in members):continue
        fields=[]
        for member in members:
            typ=field(member,'type')
            decls=[n for n in member.named_children if n!=typ and n.type!='comment']
            if any(n.type!='field_identifier' for n in decls):fields=[];break
            fields.extend((tx(typ),tx(n)) for n in decls)
        if not fields:continue
        params=', '.join('const '+t+'& '+n+'_ = '+t+'()' for t,n in fields)
        init=', '.join(n+'('+n+'_)' for _,n in fields)
        ctor='\n    explicit '+tx(name)+'('+params+') : '+init+' {}\n'
        edits.append((body.start_byte+1,ctor.encode()))
    for pos,value in sorted(edits,reverse=True):data=data[:pos]+value+data[pos:]
    return data.decode()


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


def lower(text,name):
    text=text.replace('#include <variant>','#include <xbox_compat/variant.h>').replace('#include <optional>','#include <xbox_compat/optional.h>')
    for word in ('variant','optional','get','holds_alternative','nullopt'):
        text=re.sub(r'\bstd::'+word+r'\b', 'xbox_compat::'+word,text)
    text=text.replace('[[nodiscard]] ','').replace(' noexcept override',' throw()').replace(' noexcept',' throw()')
    text=enum_wrappers(text)
    for ns in ('lexer','ast','gv'):
        text=text.replace('namespace prism::'+ns+' {','namespace prism { namespace '+ns+' {')
        text=text.replace('} // namespace prism::'+ns,'} } // namespace prism::'+ns)
    if name=='lexer.h':
        text=once(text,'size_t pos = 0;','size_t pos;')
        text=once(text,': input(text)',': input(text), pos(0)')
    if name=='lexer.cpp':
        text=re.sub(r'tokens\.emplace_back\((.*)\);',r'tokens.push_back(Token(\1));',text)
    if name=='ast.h':
        text=once(text,'size_t pos = 0;','size_t pos;')
        text=once(text,': tokens(std::move(tokenList))',': tokens(std::move(tokenList)), pos(0)')
    if name=='processor.h':
        start=text.index('#define M_ARRAY');end=text.index('#define CONTAINS',start)
        text=text[:start]+'#define M_ARRAY(arr,type,...) prism::MTDArray<type>((uintptr_t)&arr,PrismDimensions(__VA_ARGS__))\n#define VAR(name,type) std::make_pair(name,prism::ContextTypes(type))\n\n'+text[end:]
        text=once(text,'uintptr_t ptr = 0;','uintptr_t ptr;\n    MTDArray() : ptr(0) {}\n    MTDArray(uintptr_t p,const std::vector<size_t>& d) : ptr(p),dimensions(d) {}')
        text=once(text,'int depth = 0;','int depth;')
        text=once(text,'parent(std::move(parent))','parent(std::move(parent)), depth(0)')
        text=once(text,'ScopeType scope = ScopeType::None;','ScopeType scope;')
        text=once(text,'bool skipUntilEnd = false;','bool skipUntilEnd;\n    RuntimeContext() : scope(ScopeType::None),skipUntilEnd(false) {}')
        text=once(text,'IncludeFunc m_include_loader = nullptr;','IncludeFunc m_include_loader;')
        text=once(text,'class Processor {\n  public:','class Processor {\n  public:\n    Processor() : m_include_loader(nullptr) {}')
    if name=='processor.cpp':
        if text.count('return { start, c };')!=2:raise ValueError('Unexpected iterator string returns')
        text=text.replace('return { start, c };','return std::string(start, c);')
    if name=='gv.cpp':
        text=once(text,'std::sregex_token_iterator first{ line.begin(), line.end(), re, -1 }, last;','std::sregex_token_iterator first(line.begin(), line.end(), re, -1), last;')
    text=re.sub(r'R"\((.*?)\)"',lambda m:json.dumps(m[1]),text,flags=re.S)
    text=aggregates(text) if name.endswith('.h') else text
    text=braces(text)
    text=lower_ranges(text.encode()).decode()
    if name!='invoke.h' and (name.endswith('.h') or name.endswith('.cpp')):text='#include "compat.h"\n'+text
    return text


