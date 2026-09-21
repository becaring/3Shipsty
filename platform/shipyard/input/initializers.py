"""Typed, bounded initializer-list expansion for current mapping containers."""
import re
def split_type(value):
    value=' '.join(value.split());start=value.find('<')
    if start<0:return value,[]
    name=value[:start];body=value[start+1:value.rfind('>')];items=[];depth=0;begin=0
    for i,c in enumerate(body):
        if c=='<':depth+=1
        elif c=='>':depth-=1
        elif c==',' and depth==0:items.append(body[begin:i].strip());begin=i+1
    items.append(body[begin:].strip());return name,items
def construct(node,typ):
    if node.type!='initializer_list':return node.text.decode()
    name,args=split_type(typ);values=node.named_children
    if name=='std::pair':
        if len(values)!=2 or len(args)!=2:raise ValueError('Unexpected pair initializer')
        return 'std::make_pair('+construct(values[0],args[0])+', '+construct(values[1],args[1])+')'
    if name not in ('std::vector','std::unordered_set','std::unordered_map'):
        raise ValueError('Unaudited initializer type '+typ)
    child='std::pair<'+args[0]+','+args[1]+'>' if name=='std::unordered_map' else args[0]
    return 'ShipyardInputCompiler::Build<'+typ+' >()'+''.join('.Add('+construct(v,child)+')' for v in values)+'.Get()'

def lower(text,relative,ast):
    data=text.encode();edits=[]
    method_types={
        'SetDefaultKeyboardKeyToButtonMappings':'std::unordered_map<CONTROLLERBUTTONS_T, std::unordered_set<Ship::KbScancode> >',
        'SetDefaultSDLButtonToButtonMappings':'std::unordered_map<CONTROLLERBUTTONS_T, std::unordered_set<SDL_GameControllerButton> >',
        'SetDefaultSDLAxisDirectionToButtonMappings':'std::unordered_map<CONTROLLERBUTTONS_T, std::vector<std::pair<SDL_GameControllerAxis,int32_t> > >'}
    assignment_types={
        'mDefaultKeyboardKeyToAxisDirectionMappings':'std::vector<std::pair<Direction,KbScancode> >',
        'mDefaultSDLAxisDirectionToAxisDirectionMappings':'std::vector<std::pair<Direction,std::pair<SDL_GameControllerAxis,int32_t> > >'}
    for node in ast['walk'](ast['PARSER'].parse(data).root_node):
        if node.type!='initializer_list' or node.parent.type=='initializer_list':continue
        parent=node.parent;typ=None
        if parent.type=='init_declarator':
            decl=parent.parent;type_node=decl.child_by_field_name('type')
            if type_node is not None and type_node.text.startswith((b'std::vector',b'std::unordered_map',b'std::unordered_set')):
                typ=type_node.text.decode()
        elif parent.type=='assignment_expression':
            left=parent.child_by_field_name('left').text.decode()
            typ=assignment_types.get(left.split('[')[0])
        elif parent.type=='argument_list' and parent.parent.type=='call_expression':
            function=parent.parent.child_by_field_name('function').text.decode()
            typ=method_types.get(function.split('::')[-1])
            if function.startswith(('std::unordered_map<','std::unordered_set<','std::vector<')):typ=function
        if typ:
            edits.append((node.start_byte,node.end_byte,construct(node,typ).encode()))
    return ast['apply'](data,edits).decode()
