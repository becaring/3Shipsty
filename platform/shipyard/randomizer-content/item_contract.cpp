void Hex(const std::string& s){std::cout<<s.size()<<":";for(unsigned char c:s)printf("%02x",c);std::cout<<";";}
void ShowText(const Text& t){Hex(t.english);Hex(t.german);Hex(t.french);Hex(t.spanish);}
int main(){
    InitValues();std::cout<<"items:"<<itemTable.size()<<"\n";
    for(size_t i=0;i<itemTable.size();++i){const auto& v=itemTable[i];
        // Unassigned Item slots retain upstream indeterminate scalar members;
        // inspect only initialized fields until a table assignment exists.
        std::cout<<i<<":"<<v.randomizerGet<<":";ShowText(v.name);
        if(v.name.english.empty()){std::cout<<"empty\n";continue;}
        std::cout<<v.type<<":"<<v.getItemId<<":"<<v.advancement<<":"<<v.logicVal<<":"<<v.hintKey<<":"<<v.category<<":";
        ShowText(v.article);Hex(v.color);std::cout<<v.progressive<<":"<<v.price<<":"<<v.playthrough<<":"<<v.iconSize<<":";
        if(v.customIcon)Hex(v.customIcon);else std::cout<<"no-icon;";
        if(v.giEntry){const auto& e=*v.giEntry;std::cout<<"entry:"<<e.itemId<<":"<<e.field<<":"<<e.gi<<":"<<e.textId<<":"<<e.objectId<<":"<<e.modIndex<<":"<<e.tableId<<":"<<e.getItemId<<":"<<e.gid<<":"<<e.collectable<<":"<<e.getItemFrom<<":"<<e.getItemCategory<<":"<<e.drawItemId<<":"<<e.drawModIndex;}
        std::cout<<"\n";
    }
    std::map<std::string,RandomizerGet> names(itemNameToEnum.begin(),itemNameToEnum.end());for(const auto& p:names){Hex(p.first);std::cout<<p.second<<"\n";}
    for(int bottle=0;bottle<2;++bottle)for(int bomb=0;bomb<2;++bomb){
        gSaveContext.inventory.items[SLOT_BOTTLE_1]=bottle?ITEM_BOTTLE:ITEM_NONE;
        gSaveContext.inventory.items[SLOT_BOMBCHU]=bomb?ITEM_BOMBCHU:ITEM_NONE;
        for(int mod=0;mod<=MOD_RANDOMIZER;++mod)for(int id=0;id<RG_MAX;++id){GetItemEntry e={};e.modIndex=mod;e.getItemId=id;e.getItemCategory=ITEM_CATEGORY_MAJOR;std::cout<<"category:"<<bottle<<":"<<bomb<<":"<<mod<<":"<<id<<":"<<Randomizer_AdjustItemCategory(e)<<"\n";}
    }
    std::map<RandomizerArea,std::string> areas(rtAreaNames.begin(),rtAreaNames.end());for(const auto& p:areas)std::cout<<"trick-area:"<<p.first<<":"<<Tricks::GetAreaName(p.first)<<"\n";
    for(int i=0;i<7;++i){Tricks::Tag tag=Tricks::Tag(i);auto color=Tricks::GetTextColor(tag);std::cout<<"tag:"<<i<<":"<<Tricks::GetTagName(tag)<<":"<<color.x<<":"<<color.y<<":"<<color.z<<":"<<color.w<<"\n";}
    std::set<Tricks::Tag> tags;std::map<Tricks::Tag,bool> show;
    if(Tricks::CheckTags(show,tags))return 2;
    tags.insert(Tricks::Tag::NOVICE);tags.insert(Tricks::Tag::GLITCH);
    for(int i=0;i<4;++i){show[Tricks::Tag::NOVICE]=(i&1)!=0;show[Tricks::Tag::GLITCH]=(i&2)!=0;bool answer=Tricks::CheckTags(show,tags);if(answer!=(i==3))return 3;std::cout<<"filter:"<<i<<":"<<answer<<"\n";}
}
