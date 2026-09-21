#include <cassert>
#include <cstring>
#include <iostream>
#ifdef SHIPYARD_MENU_PROJECTED
#include "soh-menus/support.h"
#define MAP_VALUE(m,k) Shipyard::SohMenus::ValueIndex(m,k)
#else
#define MAP_VALUE(m,k) m[k]
#endif
static int callbacks=0;
int main(){
    PrintLiterals();
    Notification::Options notice=MakeNotification();
    assert(notice.id==0&&!notice.mute&&notice.remainingTime==0.0f);
    assert(std::strcmp(notice.itemIcon,"__OTR__textures/icon_item_24_static/gQuestIconGoldSkulltulaTex")==0);
    assert(notice.prefix=="This"&&notice.message=="is a"&&notice.suffix=="test.");
    assert(notice.prefixColor.x==0.5f&&notice.messageColor.y==0.7f&&notice.suffixColor.x==1.0f);
    SidebarEntry search=MakeSearchSidebarEntry();
    assert(search.columnCount==1&&search.columnWidgets.size()==1&&search.columnWidgets[0].size()==1);
    WidgetInfo& widget=search.columnWidgets[0][0];
    assert(widget.name=="Sidebar Search"&&widget.type==WIDGET_SEARCH&&widget.options);
    assert(std::strcmp(widget.options->tooltip,"Searches all menus for the given text, including tooltips.")==0);
    assert(!widget.options->disabled&&!widget.cVar&&!widget.callback&&!widget.isHidden&&widget.raceDisable);
    for(unsigned i=0;i<256;++i){SidebarEntry entry=MakeSidebarEntry(i);assert(entry.columnCount==i&&entry.columnWidgets.empty());}
    for(int type=WIDGET_CHECKBOX;type<=WIDGET_CUSTOM;++type){
        WidgetInfo w=MakeWidgetInfo("real entry",static_cast<WidgetType>(type));
        assert(w.name=="real entry"&&w.type==type&&!w.cVar&&!w.callback&&!w.options);
        std::cout<<type<<':'<<w.valuePointer.index()<<'\n';
    }
    std::unordered_map<std::string,MainMenuEntry> entries;
    MainMenuEntry& first=MAP_VALUE(entries,"Settings");
    assert(first.label.empty()&&!first.sidebarCvar&&first.sidebars.empty()&&first.sidebarOrder.empty());
    first.label="retained";assert(&MAP_VALUE(entries,"Settings")==&first&&entries.size()==1);
    SidebarEntry& side=MAP_VALUE(first.sidebars,"General");assert(side.columnCount==0&&side.columnWidgets.empty());
    side.columnCount=3;assert(MAP_VALUE(first.sidebars,"General").columnCount==3);
    assert(PopupsQueued()==0&&!IsPopupOpen("message"));
    for(int i=0;i<128;++i){std::string title="message"+std::string(i+1,'x');
        RegisterPopup(title,"body","first","second",[i](){callbacks+=i;},[](){++callbacks;});
        assert(PopupsQueued()==static_cast<size_t>(i+1)&&callbacks==0);
        assert(modals.back().title_==title&&modals.back().message_=="body");
    }
    assert(IsPopupOpen("messagex")&&!IsPopupOpen("messagexx"));
    for(size_t i=0;i<modals.size();++i){modals[i].button1callback_();modals[i].button2callback_();}
    assert(callbacks==8256);DismissPopup();assert(closePopup&&PopupsQueued()==128);
    std::cout<<"Real menu insertion/search values and 128 deferred modal callbacks agree "<<callbacks<<'\n';
}
