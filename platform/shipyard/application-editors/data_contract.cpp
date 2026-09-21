int main() {
    assert(groupLabels.size()==21 && cosmeticsRandomizerModes.size()==5 && audioRandomizerModes.size()==5);
    assert(ShowTypes().size()==9 && allTypes.size()==8);
    for(int v=-1;v<1025;++v) {
        SeqType t=static_cast<SeqType>(v);ImVec4 c=GetSequenceTypeColor(t);
        std::cout<<v<<':'<<AuthenticCountBySequenceType(t)<<':'<<GetSequenceTypeName(t)<<':'<<c.x<<':'<<c.y<<':'<<c.z<<':'<<c.w<<'\n';
    }
    for(auto& row:groupLabels)std::cout<<row.first<<':'<<row.second<<'\n';
    for(auto& row:audioRandomizerModes)std::cout<<row.first<<':'<<row.second<<'\n';
    for(auto& row:cosmeticsRandomizerModes)std::cout<<row.first<<':'<<row.second<<'\n';
    for(auto& row:ShowTypes()){assert(row.second);std::cout<<row.first<<'\n';}
    for(auto v:allTypes)std::cout<<v<<'\n';
    for(auto& row:cosmeticOptions){const CosmeticOption& c=row.second;
        assert(c.currentColor.x==c.defaultColor.r/255.0f && c.currentColor.y==c.defaultColor.g/255.0f && c.currentColor.z==c.defaultColor.b/255.0f && c.currentColor.w==c.defaultColor.a/255.0f);
        std::cout<<row.first<<':'<<c.cvar<<':'<<c.valuesCvar<<':'<<c.rainbowCvar<<':'<<c.lockedCvar<<':'<<c.changedCvar<<':'<<c.label<<':'<<c.group<<':'<<unsigned(c.defaultColor.r)<<':'<<unsigned(c.defaultColor.g)<<':'<<unsigned(c.defaultColor.b)<<':'<<unsigned(c.defaultColor.a)<<':'<<c.currentColor.x<<':'<<c.currentColor.y<<':'<<c.currentColor.z<<':'<<c.currentColor.w<<':'<<c.supportsAlpha<<':'<<c.supportsRainbow<<':'<<c.advancedOption<<'\n';
    }
    std::cout<<"Cosmetic options: "<<cosmeticOptions.size()<<'\n';
}
