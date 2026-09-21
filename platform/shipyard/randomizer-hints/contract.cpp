#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(){
    static_assert(std::is_same<std::underlying_type<RandomizerHintTextKey>::type,int>::value,"JSON hint key underlying type changed");
    Rando::Hint hint;
    CHECK(hint.ownKey==RH_NONE && !hint.IsEnabled() && !hint.yourPocket && hint.GetNum()==0);
    CHECK(hint.GetHintType()==HINT_TYPE_HINT_KEY && hint.GetDistribution().empty());
    CHECK(EmitSelectionFields(hint).dump()=="null");
    hint.AddHintedLocation(RandomizerCheck(5));hint.AddHintedLocation(RandomizerCheck(5));
    CHECK(hint.GetHintedLocations().size()==2 && hint.GetHintedLocations()[0]==RandomizerCheck(5));
    std::vector<RandomizerCheck> copy=hint.GetHintedLocations();copy.clear();CHECK(hint.GetHintedLocations().size()==2);
    hint.AddHintedArea(RandomizerArea(2));CHECK(hint.GetHintedAreas()[0]==RandomizerArea(2));
    hint.SetDistribution("balanced");CHECK(hint.GetDistribution()=="balanced");
    hint.SetHintType(HINT_TYPE_MESSAGE);CHECK(hint.GetHintType()==HINT_TYPE_MESSAGE);
    std::vector<CustomMessage> messages;messages.push_back(CustomMessage("A message"));
    Rando::Hint messageHint(RH_NONE,messages);
    CHECK(messageHint.IsEnabled() && messageHint.GetHintType()==HINT_TYPE_MESSAGE);
    CHECK(messageHint.messages.size()==1 && messageHint.messages[0].GetEnglish(MF_RAW)=="A message");
    messages.clear();CHECK(messageHint.messages.size()==1);
    CHECK(MessageBranch(messageHint,MF_RAW,0).GetEnglish(MF_RAW)=="A message");
    CHECK(MessageBranch(messageHint,MF_CLEAN,0).GetEnglish(MF_RAW)=="A message");
    CHECK(MessageBranch(messageHint,MF_RAW,1).GetEnglish(MF_RAW).empty());
    for(int style=MF_FORMATTED;style<=MF_ENCODE;++style){
        std::string result=MessageBranch(messageHint,MessageFormat(style),0).GetEnglish(MF_RAW);
        printf("message-%d:",style);for(size_t i=0;i<result.size();++i)printf("%02x",static_cast<unsigned char>(result[i]));printf("\n");
    }
    ParseSelectionFields(hint,nlohmann::json::parse("{\"itemNameChosen\":255,\"areaNameChosen\":3,\"hintKey\":7,\"hintTextChosen\":4,\"num\":-5}"));
    CHECK(hint.GetItemNamesChosen()[0]==255 && hint.GetAreaTextsChosen()[0]==3);
    CHECK(hint.GetHintTextKeys()[0]==RandomizerHintTextKey(7) && hint.GetHintTextsChosen()[0]==4 && hint.GetNum()==-5);
    oJson single=EmitSelectionFields(hint);
    CHECK(!single["hintKey"].is_number_unsigned());
    CHECK(single.dump()=="{\"itemNameChosen\":255,\"areaNameChosen\":3,\"hintKey\":7,\"hintTextChosen\":4,\"num\":-5}");
    printf("%s\n",single.dump().c_str());
    hint.ResetVariables();
    CHECK(hint.ownKey==RH_NONE && !hint.IsEnabled() && hint.GetNum()==0 && !hint.yourPocket);
    CHECK(hint.GetHintType()==HINT_TYPE_HINT_KEY && hint.GetDistribution().empty());
    CHECK(hint.GetHintedLocations().empty() && hint.GetHintedAreas().empty() && hint.GetHintedItems().empty() && hint.GetHintedTrials().empty());
    CHECK(hint.GetItemNamesChosen().empty() && hint.GetAreaTextsChosen().empty() && hint.GetHintTextsChosen().empty());
    CHECK(hint.GetHintTextKeys().empty() && hint.messages.empty());
    ParseSelectionFields(hint,nlohmann::json::parse("{\"itemNamesChosen\":[2,1],\"itemNameChosen\":9,\"areaNamesChosen\":[5,6],\"hintKeys\":[8,7],\"hintTextsChosen\":[4,3],\"num\":9}"));
    CHECK(hint.GetItemNamesChosen().size()==2 && hint.GetItemNamesChosen()[0]==2);
    CHECK(EmitSelectionFields(hint).dump()=="{\"itemNamesChosen\":[2,1],\"areaNamesChosen\":[5,6],\"hintKeys\":[8,7],\"hintTextsChosen\":[4,3],\"num\":9}");
    printf("%s\n",EmitSelectionFields(hint).dump().c_str());
    bool rejected=false;try{ParseSelectionFields(hint,nlohmann::json::parse("{\"num\":\"invalid\"}"));}catch(const std::exception&){rejected=true;}CHECK(rejected);
    messageHint.ResetVariables();CHECK(!messageHint.IsEnabled() && messageHint.messages.empty());
    StaticHintInfo value=VALUE_STATIC_INFO;
    CHECK(int(value.type)==0 && int(value.setting)==0 && !value.yourPocket && value.num==0);
    CHECK(value.hintKeys.empty() && value.targetChecks.empty() && value.targetItems.empty() && value.hintChecks.empty());
    CHECK(value.condition.index()==0 && HINT_GET<bool>(value.condition)==false);
    HINT_VARIANT<bool,uint8_t> yes=true;CHECK(yes.index()==0 && HINT_GET<bool>(yes));
    HINT_VARIANT<bool,uint8_t> count=uint8_t(7);CHECK(count.index()==1 && HINT_GET<uint8_t>(count)==7);
    StaticHintInfo record(HINT_TYPE_MESSAGE,std::vector<RandomizerHintTextKey>(),RandomizerSettingKey(0),count,std::vector<RandomizerCheck>());
    CHECK(record.condition.index()==1 && HINT_GET<uint8_t>(record.condition)==7 && !record.yourPocket && record.num==0);
    printf("Hint defaults/copies/reset and ordered JSON; StaticHintInfo variant/defaults passed\n");
    return 0;
}
