"""AST-only pair binding/contains lowering for the standard containers it supports."""
from pathlib import Path
import runpy
from cpp_ast import PARSER,walk
ROOT=Path(__file__).resolve().parents[3]
RANGES=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
COMMON={'lower_ranges':lambda data:RANGES(data,'Shipyard::Resources::begin','Shipyard::Resources::end')}

def apply(source,edits):
    previous=len(source)+1
    for start,end,value in sorted(edits,reverse=True):
        if end>previous:raise ValueError('overlapping compiler edits')
        source=source[:start]+value+source[end:];previous=start
    return source

def pair_bindings(source):
    edits=[]
    for binding in walk(PARSER.parse(source).root_node):
        if binding.type!='structured_binding_declarator' or binding.parent.type!='init_declarator':continue
        init=binding.parent;decl=init.parent
        if decl.type!='declaration' or len([c for c in decl.named_children if c.type=='init_declarator'])!=1:
            raise ValueError('Unknown local structured binding')
        names=[c.text.decode() for c in binding.named_children]
        if len(names)!=2:raise ValueError('Only pair local bindings audited')
        prefix=source[decl.start_byte:binding.start_byte].decode()
        if prefix.strip()!='auto':raise ValueError('Unknown local binding qualifier')
        value=init.child_by_field_name('value');pair='_controllerPair'+str(binding.start_byte)
        replacement='auto '+pair+' = '+value.text.decode()+'; auto& '+names[0]+' = '+pair+'.first; auto& '+names[1]+' = '+pair+'.second;'
        edits.append((decl.start_byte,decl.end_byte,replacement.encode()))
    source=apply(source,edits)
    for _ in range(64):
        edits=[]
        for node in walk(PARSER.parse(source).root_node):
            if node.type!='for_range_loop':continue
            declarator=node.child_by_field_name('declarator')
            binding=next((n for n in walk(declarator) if n.type=='structured_binding_declarator'),None)
            if binding is None:continue
            if any(n.type=='structured_binding_declarator' and n.id!=binding.id for n in list(walk(node))[1:]):continue
            names=[c.text.decode() for c in binding.named_children]
            if len(names)!=2 or any(c.type!='identifier' for c in binding.named_children):
                raise ValueError('Only audited pair structured bindings supported')
            body=node.child_by_field_name('body')
            opening=next(c for c in node.children if c.type=='(')
            prefix=source[opening.end_byte:binding.start_byte].decode()
            if prefix.strip() not in ('auto','auto&','auto &','const auto&','const auto &'):
                raise ValueError('Unaudited binding qualifier '+prefix)
            pair='_controllerPair'+str(node.start_byte)
            declaration=prefix+pair
            right=node.child_by_field_name('right').text.decode()
            inner=body.text.decode()[1:-1] if body.type=='compound_statement' else body.text.decode()
            replacement='for ('+declaration+' : '+right+') { auto& '+names[0]+' = '+pair+'.first; auto& '+names[1]+' = '+pair+'.second; '+inner+' }'
            edits.append((node.start_byte,node.end_byte,replacement.encode()))
        if not edits:
            if any(n.type=='structured_binding_declarator' for n in walk(PARSER.parse(source).root_node)):
                raise ValueError('Unlowered structured binding')
            return source
        source=apply(source,edits)
    raise ValueError('Unexpected binding nesting')

def contains(source):
    edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='call_expression':continue
        fn=node.child_by_field_name('function')
        if fn.type!='field_expression':continue
        field=fn.child_by_field_name('field')
        if field.text!=b'contains':continue
        args=node.child_by_field_name('arguments').named_children
        if len(args)!=1:raise ValueError('Unexpected contains overload')
        obj=fn.child_by_field_name('argument')
        replacement=b'ShipyardInputCompiler::Contains('+obj.text+b', '+args[0].text+b')'
        edits.append((node.start_byte,node.end_byte,replacement))
    return apply(source,edits)

def syntax(text,enum_names):
    source=text.encode()
    edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type=='virtual_specifier' and node.text in (b'override',b'final'):
            edits.append((node.start_byte,node.end_byte,b''))
        elif node.type=='qualified_identifier':
            scope=node.child_by_field_name('scope')
            if scope is not None and scope.text.decode() in enum_names:
                edits.append((scope.start_byte,scope.end_byte+2,b''))
    source=apply(source,edits)
    source=pair_bindings(source)
    source=contains(source)
    source=COMMON['lower_ranges'](source)
    return source.decode().replace('std::to_string(', 'ShipyardInputCompiler::ToString(').replace('std::clamp(', 'ShipyardInputCompiler::Clamp(')
