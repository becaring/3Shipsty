#include <cassert>
#include <cstdio>
#include <cstring>
#include <new>
#include <type_traits>
namespace Rando {
struct ItemTestAccess {
    static std::shared_ptr<GetItemEntry> entry(const Item& v) { return v.giEntry; }
    static bool progressive(const Item& v) { return v.progressive; }
    static void untouchedDefaults(const Item& v) {
        const unsigned char* p = reinterpret_cast<const unsigned char*>(&v.logicVal);
        for (size_t i=0;i<sizeof(v.logicVal);++i) assert(p[i]==0xa5);
        p = reinterpret_cast<const unsigned char*>(&v.category);
        for (size_t i=0;i<sizeof(v.category);++i) assert(p[i]==0xa5);
    }
};
}
static void draw(PlayState*,GetItemEntry*) {}
int main() {
    using namespace Rando;
    typename std::aligned_storage<sizeof(Item),alignof(Item)>::type bytes;
    memset(&bytes,0xa5,sizeof(bytes));
    Item* defaults=new(&bytes) Item;
    assert(defaults->GetRandomizerGet()==RG_NONE && defaults->GetItemID()==GI_NONE);
    assert(defaults->GetItemType()==ITEMTYPE_ITEM && !defaults->IsAdvancement());
    assert(defaults->GetName().GetEnglish().empty() && defaults->GetArticle().GetEnglish().empty());
    assert(defaults->GetColor().empty() && defaults->GetHintKey()==RHT_NONE);
    assert(defaults->GetPrice()==0 && !defaults->IsPlaythrough() && !defaults->HasCustomIcon());
    assert(defaults->GetCustomIcon()==nullptr && defaults->GetCustomIconSize()==ICON_SIZE_32);
    assert(!ItemTestAccess::entry(*defaults) && !ItemTestAccess::progressive(*defaults));
    ItemTestAccess::untouchedDefaults(*defaults);defaults->~Item();
    unsigned bottles=0,cases=0;unsigned long long checksum=0;
    for (int id=-32768;id<=32767;++id) {
        Item item(RG_NONE,Text("name"),ITEMTYPE_ITEM,int16_t(id),false,LOGIC_NONE,RHT_NONE,ITEM_CATEGORY_JUNK);
        bool expected=id==15||id==20||(id>=140&&id<=148);
        assert(item.IsBottleItem()==expected);bottles+=item.IsBottleItem();
        assert(!ItemTestAccess::entry(item) && !item.IsPlaythrough() && !item.HasCustomIcon());
        assert(item.GetColor()=="%g" && item.GetCustomIconSize()==ICON_SIZE_32);
    }
    const int ids[]={-32768,-1,0,125,126,32767};
    const unsigned mods[]={MOD_NONE,MOD_RANDOMIZER,2,65535};
    const unsigned gids[]={0,32767,65535};
    const int animations[]={CHEST_ANIM_SHORT,CHEST_ANIM_LONG,-1};
    for (int id:ids) for (unsigned mod:mods) for(unsigned gid:gids) for(int anim:animations) {
        Item item(RG_FAIRY_BOW,Text("Bow","Arc","Bogen"),ITEMTYPE_EQUIP,int16_t(id),true,LOGIC_NONE,RHT_NONE,
                  0x1234,0x4567,uint16_t(gid),0x2345,0x3456,int16_t(anim),ITEM_CATEGORY_MAJOR,uint16_t(mod),
                  Text("the"),"%r",true,65535);
        auto entry=ItemTestAccess::entry(item);assert(entry);
        bool random=mod==MOD_RANDOMIZER||id>125;
        assert(entry->itemId==0x1234 && entry->field==0x3456 && entry->textId==0x2345 && entry->objectId==0x4567);
        assert(entry->gi==int16_t((anim!=CHEST_ANIM_SHORT?1:-1)*(gid+1)));
        assert(entry->modIndex==mod && entry->tableId==(random?TABLE_RANDOMIZER:TABLE_VANILLA));
        assert(entry->getItemId==(random?int16_t(RG_FAIRY_BOW):int16_t(id)) && entry->gid==gid);
        assert(entry->collectable==true && entry->getItemFrom==ITEM_FROM_NPC && entry->getItemCategory==ITEM_CATEGORY_MAJOR);
        assert(entry->drawItemId==(random?uint16_t(RG_FAIRY_BOW):0x1234));
        assert(entry->drawModIndex==(random?MOD_RANDOMIZER:mod) && !entry->drawFunc);
        assert(item.GetName().GetEnglish()=="Bow" && item.GetName().GetFrench()=="Arc" && item.GetName().GetGerman()=="Bogen");
        assert(item.GetArticle().GetEnglish()=="the" && item.GetColor()=="%r" && item.GetCategory()==ITEM_CATEGORY_MAJOR);
        assert(item.GetLogicVal()==LOGIC_NONE && item.GetPrice()==65535 && ItemTestAccess::progressive(item));
        Item alias=item;assert(ItemTestAccess::entry(alias).get()==entry.get());
        alias.SetCustomDrawFunc(draw);assert(entry->drawFunc==draw);
        alias.SetPrice(37);alias.SetAsPlaythrough();assert(item.GetPrice()==65535&&!item.IsPlaythrough());
        assert(alias.GetPrice()==37&&alias.IsPlaythrough()&&alias==item&&!(alias!=item));
        char borrowed[]="icon";Item iconCopy=item.CustomIcon(borrowed,ICON_SIZE_24);
        assert(item.GetCustomIcon()==borrowed && iconCopy.GetCustomIcon()==borrowed && item.HasCustomIcon());
        assert(iconCopy.GetCustomIconSize()==ICON_SIZE_24 && ItemTestAccess::entry(iconCopy).get()==entry.get());
        Item different(RG_NONE,Text("other"),ITEMTYPE_SONG,int16_t(id),false,LOGIC_NONE,RHT_NONE,ITEM_CATEGORY_JUNK);
        assert(item!=different);checksum+=entry->itemId+uint16_t(entry->gi)+entry->drawItemId+entry->drawModIndex;++cases;
    }
    Logic logic;
    assert(!logic.Bottles&&!logic.NumBottles&&!logic.PieceOfHeart&&!logic.HeartContainer);
    assert(!logic.IsChild&&!logic.IsAdult&&!logic.BigPoes&&!logic.BaseHearts&&!logic.AtDay&&!logic.AtNight);
    assert(logic.CurrentRegionKey==RR_NONE && logic.CurrentCheckKey==RC_UNKNOWN_CHECK);
    assert(!logic.CalculatingAvailableChecks&&!logic.ACProcessUndiscoveredExits&&!logic.mSaveContext);
    printf("Item: 65536 bottle IDs; %u GI metadata branches; %u bottles; checksum %llu; shared ownership/defaults/Logic defaults pass\n",cases,bottles,checksum);
}
