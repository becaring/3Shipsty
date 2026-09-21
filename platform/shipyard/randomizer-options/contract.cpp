#include <cassert>
#include <cstring>
#include <cstdio>
#include <new>

namespace Rando {
struct Contract {
    static const uint32_t layout[];
    template<class T> static bool untouched(const T& field) {
        unsigned char bytes[sizeof(T)]; memcpy(bytes,&field,sizeof(T));
        for(size_t i=0;i<sizeof(T);++i) if(bytes[i]!=0xa5)return false;
        return true;
    }
    static void Zeroed(const Option& o) {
        assert(o.key==0 && o.widgetType==0 && o.widgetInfo.cVar==nullptr && o.widgetInfo.type==0);
        assert(o.contextSelection==0 && o.delayedSelection==0 && !o.hidden);
        assert(o.category==OptionCategory::Setting && o.defaultOption==0 && !o.defaultHidden);
        assert(o.imFlags==IMFLAG_NONE && !o.disabled && o.disabledText.empty());
        assert(o.name.empty() && o.options.empty() && o.cvarName.empty() && o.description.empty());
        assert(o.optionsTextToVar.empty() && o.optionsMap.empty() && !o.widgetOptions && !o.callback);
    }
    static int Run() {
        union Storage { double align; unsigned char bytes[sizeof(TrickSetting)+32]; } raw;
        memset(raw.bytes,0xa5,sizeof(raw.bytes));
        Option* normal=new(raw.bytes) Option;
        assert(untouched(normal->key) && untouched(normal->widgetType) && untouched(normal->widgetInfo.cVar));
        assert(normal->contextSelection==0 && normal->category==OptionCategory::Setting);
        normal->~Option();
        memset(raw.bytes,0xa5,sizeof(raw.bytes));
#ifdef SHIPYARD_OPTIONS_PROJECTED
        Option* value=new(raw.bytes) Option(Shipyard::SohUI::ValueInit());
#else
        Option* value=new(raw.bytes) Option();
#endif
        Zeroed(*value);value->~Option();
        memset(raw.bytes,0xa5,sizeof(raw.bytes));
        TrickSetting* normalTrick=new(raw.bytes) TrickSetting;
        assert(untouched(normalTrick->key) && untouched(normalTrick->mQuest) && untouched(normalTrick->mArea));
        normalTrick->~TrickSetting();
#ifdef SHIPYARD_OPTIONS_PROJECTED
        TrickSetting* valueTrick=new(raw.bytes) TrickSetting(Shipyard::SohUI::ValueInit());
        LocationOption loc((Shipyard::SohUI::ValueInit()));
#else
        TrickSetting* valueTrick=new(raw.bytes) TrickSetting();
        LocationOption loc{};
#endif
        Zeroed(*valueTrick);assert(valueTrick->mQuest==0 && valueTrick->mArea==0);
        valueTrick->~TrickSetting();Zeroed(loc);

        Option boolean=Option::Bool(static_cast<RandomizerSettingKey>(1),"Boolean");
        assert(boolean.GetOptionCount()==2 && boolean.GetOptionText(0)=="Off" && boolean.GetOptionText(1)=="On");
        assert(boolean.widgetOptions && boolean.widgetOptions->tooltip==boolean.description.c_str());
        assert(boolean.optionsMap[0]==boolean.options[0].c_str());
        std::vector<std::string> choices;
        for(unsigned i=0;i<17;++i) choices.push_back(std::string(90,char('a'+i)));
        Option option=Option::U8(static_cast<RandomizerSettingKey>(2),std::string(100,'n'),choices,
            OptionCategory::Setting,std::string(100,'v'),std::string(150,'d'),WIDGET_CVAR_COMBOBOX,3,true);
        assert(option.GetKey()==2 && option.GetOptionCount()==17 && option.IsHidden());
        assert(option.contextSelection==3 && option.delayedSelection==0 && !option.disabled);
        assert(option.optionsTextToVar.size()==17 && option.optionsTextToVar[choices[16]]==16);
        UIWidgets::ComboboxOptions* combo=static_cast<UIWidgets::ComboboxOptions*>(option.widgetOptions.get());
        assert(combo->defaultIndex==3 && combo->comboMap.size()==17);
        Option copied=option;
        assert(copied.widgetOptions==option.widgetOptions);
        // Preserve upstream's shared widget options and pointer map on copies.
        assert(copied.optionsMap[0]==option.optionsMap[0]);
        assert(copied.optionsMap[0]!=copied.options[0].c_str());
        for(unsigned i=0;i<256;++i) {
            option.SetContextIndex(static_cast<uint8_t>(i));
            assert(option.contextSelection==(i<17?i:16));
            option.SetDelayedOption();option.SetContextIndex(0);option.RestoreDelayedOption();
            assert(option.contextSelection==(i<17?i:16));
        }
        option.Hide();assert(option.IsHidden());option.Unhide();assert(!option.IsHidden());
        option.Disable("disabled");assert(option.disabled && option.disabledText=="disabled");
        option.Enable();assert(!option.disabled);
        option.SetFlag(0);option.AddFlag(3);option.RemoveFlag(1);assert(option.HasFlag(2) && !option.HasFlag(1));
        unsigned calls=0;option.SetCallback([&](WidgetInfo& info){++calls;assert(info.name.empty());});
        option.RunCallback();assert(calls==1);
        std::vector<Option*> options;options.push_back(&boolean);options.push_back(&option);
        OptionGroup group("group",options);assert(group.GetOptions().size()==2 && group.GetSubGroups().empty());
        assert(group.GetGroupType()==OptionGroupType::DEFAULT && group.GetContainsType()==OptionGroupType::DEFAULT);
        std::vector<OptionGroup*> groups;groups.push_back(&group);
        OptionGroup subgroup=OptionGroup::SubGroup("sub",groups,WidgetContainerType::COLUMN,"description");
        assert(subgroup.GetContainsType()==OptionGroupType::SUBGROUP && subgroup.GetGroupType()==OptionGroupType::SUBGROUP);
        assert(subgroup.GetSubGroups()[0]==&group && subgroup.GetContainerType()==WidgetContainerType::COLUMN);
        subgroup.Disable();assert(subgroup.mDisabled);subgroup.Enable();assert(!subgroup.mDisabled);
        std::set<Tricks::Tag> tags;tags.insert(Tricks::Tag::NOVICE);tags.insert(Tricks::Tag::EXPERT);
        TrickSetting trick=TrickSetting::LogicTrick(static_cast<RandomizerTrick>(1),static_cast<RandomizerCheckQuest>(1),
            static_cast<RandomizerArea>(2),tags,"Trick","tag","description");
        assert(trick.GetTags().size()==2 && trick.HasTag(Tricks::Tag::NOVICE) && !trick.HasTag(Tricks::Tag::GLITCH));
        assert(trick.GetKey()==1 && trick.GetQuest()==1 && trick.GetArea()==2 && trick.GetNameTag()=="tag");
        Settings* settings=new Settings;
        assert(settings->mTricksByArea.empty() && !settings->mContext);
        assert(settings->mExcludeLocationsOptionsAreas.size()==RCAREA_INVALID);
        for(size_t i=0;i<settings->mOptions.size();++i)Zeroed(settings->mOptions[i]);
        for(size_t i=0;i<settings->mTrickSettings.size();++i){Zeroed(settings->mTrickSettings[i]);assert(settings->mTrickSettings[i].mQuest==0 && settings->mTrickSettings[i].mArea==0);}
        for(size_t i=0;i<settings->mOptionGroups.size();++i)assert(settings->mOptionGroups[i].mGroupType==OptionGroupType::DEFAULT && !settings->mOptionGroups[i].mDisabled);
        printf("option contracts passed: choices=17 selections=256 settings=%u tricks=%u groups=%u\n",unsigned(settings->mOptions.size()),unsigned(settings->mTrickSettings.size()),unsigned(settings->mOptionGroups.size()));
        delete settings;return 0;
    }
};
}
int main(){return Rando::Contract::Run();}
