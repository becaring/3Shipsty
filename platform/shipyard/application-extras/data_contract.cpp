int main(){
 assert(BR_OPTIONS_MAX==12);
 size_t choices=0;
 for(unsigned i=0;i<BR_OPTIONS_MAX;++i){
  unsigned count=BossRush_GetSettingOptionsAmount(i);assert(count>0);choices+=count;
  for(unsigned lang=0;lang<LANGUAGE_MAX;++lang){
   assert(std::string(BossRush_GetSettingName(i,lang))==BossRushOptions[i].name[lang]);
   std::cout<<i<<":"<<lang<<":"<<BossRush_GetSettingName(i,lang)<<"\n";
   for(unsigned c=0;c<count;++c){assert(std::string(BossRush_GetSettingChoiceName(i,c,lang))==BossRushOptions[i].choices[c][lang]);std::cout<<BossRush_GetSettingChoiceName(i,c,lang)<<"\n";}
  }
 }
 assert(choices==36);
 for(unsigned mask=0;mask<(1u<<PRESET_SECTION_MAX);++mask){
  nlohmann::json value=nlohmann::json::object();std::string name="preset"+std::to_string(mask);
  value["presetName"]=name;value["blocks"]=nlohmann::json::object();value["isBuiltIn"]=(mask&1)!=0;
  for(int s=0;s<PRESET_SECTION_MAX;++s)if(mask&(1u<<s))value["blocks"][blockInfo[s].names[1]]=nlohmann::json::object();
  ParsePreset(value,name+".json");const PresetInfo& p=presets.at(name);assert(p.presetValues==value);assert(p.fileName==name+".json");assert(p.isBuiltIn==((mask&1)!=0));
  for(int s=0;s<PRESET_SECTION_MAX;++s){assert(p.apply[s]==((mask&(1u<<s))!=0));for(size_t v=0;v<blockInfo[s].sections.size();++v)std::cout<<blockInfo[s].sections[v]<<":";std::cout<<blockInfo[s].names[0]<<":"<<blockInfo[s].names[1]<<":"<<blockInfo[s].icon<<"\n";}
 }
 assert(popupList.size()==15);assert(popupList.at(ITEM_SKULL_TOKEN).empty());
 size_t n=0;
 for(size_t i=0;i<splitObjectList.size();++i){const SplitObject& split=splitObjectList[i];assert(split.splitTimeCurrent==0&&split.splitTimeBest==0&&split.splitSkullTokenCount==0);std::cout<<SplitObject_to_json(split).dump()<<"\n";++n;}
 for(std::map<uint32_t,std::vector<uint32_t>>::const_iterator it=popupList.begin();it!=popupList.end();++it){std::cout<<it->first<<":";for(size_t i=0;i<it->second.size();++i)std::cout<<it->second[i]<<",";std::cout<<"\n";}
 for(unsigned i=0;i<512;++i){
  SplitObject split={};split.splitType=i%7;split.splitID=i*13;split.splitName="Name \xc3\xa9 "+std::to_string(i);split.splitImage="asset/"+std::to_string(i);
  split.splitTint=ImVec4(float(i%8)/8.f,float(i%16)/16.f,float(i%32)/32.f,1.f);split.splitTimeCurrent=i*100;split.splitTimeBest=i*97;split.splitTimePreviousBest=i*95;split.splitTimeStatus=i%4;split.splitSkullTokenCount=i%101;
  nlohmann::json j=SplitObject_to_json(split);assert(j.size()==10);assert(j["splitTint"].size()==4);
  SplitObject result=json_to_SplitObject(j);assert(result.splitType==split.splitType&&result.splitID==split.splitID&&result.splitName==split.splitName&&result.splitImage==split.splitImage);
  assert(result.splitTimeCurrent==split.splitTimeCurrent&&result.splitTimeBest==split.splitTimeBest&&result.splitTimePreviousBest==split.splitTimePreviousBest&&result.splitTimeStatus==SPLIT_STATUS_INACTIVE&&result.splitSkullTokenCount==split.splitSkullTokenCount);
  assert(result.splitTint.x==split.splitTint.x&&result.splitTint.y==split.splitTint.y&&result.splitTint.z==split.splitTint.z&&result.splitTint.w==split.splitTint.w);assert(SplitObject_to_json(result)==j);
  std::cout<<j.dump()<<"\n";
 }
 assert(removeSpecialCharacters("a-z A_Z!0123")=="azAZ0123");
 nlohmann::json bad=SplitObject_to_json(splitObjectList[0]);bad["splitName"]=12;bool rejected=false;try{json_to_SplitObject(bad);}catch(const nlohmann::json::type_error& e){rejected=e.id==302;}assert(rejected);
 std::cout<<"all boss settings, 128 preset masks, "<<n<<" split definitions, 15 popup groups, 512 split roundtrips passed\n";
}
