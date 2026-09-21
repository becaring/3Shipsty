#define CHECK(x) do { if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;} }while(0)
int main() {
    AudioCollection audio;
    CHECK(!audio.shufflePoolInitialized);
    CHECK(audio.GetIncludedSequences().empty() && audio.GetExcludedSequences().empty());
    AudioCollection* valued=new AudioCollection();
    CHECK(!valued->shufflePoolInitialized);delete valued;
    SequenceInfo zero={};
    CHECK(zero.sequenceId==0 && zero.label.empty() && zero.sfxKey.empty());
    CHECK(zero.category==SEQ_NOSHUFFLE && !zero.canBeReplaced && !zero.canBeUsedAsReplacement);
    std::map<uint16_t,SequenceInfo> sequences=audio.GetAllSequences();
    CHECK(sequences.size()>200 && sequences.size()==audio.SequenceMapSize());
    for(auto it=sequences.begin();it!=sequences.end();++it) {
        const SequenceInfo& s=it->second;
        CHECK(audio.HasSequenceNum(it->first));
        CHECK(std::string(audio.GetSequenceName(it->first))==s.label);
        printf("%u|%u|%s|%s|%d|%d|%d\n",it->first,s.sequenceId,s.label.c_str(),s.sfxKey.c_str(),s.category,s.canBeReplaced,s.canBeUsedAsReplacement);
    }
    CHECK(audio.GetSequenceName(65535)==nullptr && !audio.HasSequenceNum(65535));
    CHECK(audio.GetReplacementSequence(65535)==65535);
    CHECK(audio.GetCvarKey("Track")==std::string(CVAR_AUDIO("ReplacedSequences.Track.value")));
    CHECK(audio.GetCvarLockKey("Track")==std::string(CVAR_AUDIO("ReplacedSequences.Track.locked")));
    sequences.begin()->second.label="copy mutation";
    CHECK(std::string(audio.GetSequenceName(sequences.begin()->first))!="copy mutation");
    char custom[]="music/My.Song ~_FANFARE";
    audio.AddToCollection(custom,65000);
    const SequenceInfo& added=audio.sequenceMap.at(65000);
    CHECK(added.label=="My.Song ~" && added.sfxKey=="MySong_-" && added.category==SEQ_FANFARE);
    CHECK(!added.canBeReplaced && added.canBeUsedAsReplacement);
    char duplicate[]="replacement_Different";audio.AddToCollection(duplicate,65000);
    CHECK(audio.sequenceMap.at(65000).label=="My.Song ~");
    char extension[]="other\\This_World_fanfare.seq";audio.AddToCollection(extension,65001);
    CHECK(audio.sequenceMap.at(65001).label=="This" && audio.sequenceMap.at(65001).category==SEQ_BGM_CUSTOM);
    char sameLabel[]="This_bgm";audio.AddToCollection(sameLabel,65002);
    CVarSetInteger(CVAR_AUDIO("Excluded.NA_BGM_FIELD_LOGIC"),1);
    audio.InitializeShufflePool();
    CHECK(audio.shufflePoolInitialized);
    CHECK(audio.excludedSequences.count(&audio.sequenceMap.at(NA_BGM_FIELD_LOGIC))==1);
    CHECK(audio.includedSequences.count(&audio.sequenceMap.at(65000))==1);
    std::set<std::string> includedLabels,excludedLabels;
    for(auto it=audio.sequenceMap.begin();it!=audio.sequenceMap.end();++it) {
        SequenceInfo& s=it->second;if(!s.canBeUsedAsReplacement)continue;
        std::string k=std::string(CVAR_AUDIO("Excluded."))+s.sfxKey;
        (CVarGetInteger(k.c_str(),0)?excludedLabels:includedLabels).insert(s.label);
    }
    CHECK(audio.includedSequences.size()==includedLabels.size());
    CHECK(audio.excludedSequences.size()==excludedLabels.size());
    // Distinct IDs with the same label intentionally occupy a single set entry.
    CHECK(audio.includedSequences.count(&audio.sequenceMap.at(65001))==1);
    CHECK(audio.includedSequences.count(&audio.sequenceMap.at(65002))==1);
    SequenceInfo* live=&audio.sequenceMap.at(65000);
    CHECK(*audio.includedSequences.find(live)==live);
    audio.RemoveFromShufflePool(live);
    CHECK(audio.excludedSequences.count(live)==1 && audio.includedSequences.count(live)==0);
    CHECK(CVarGetInteger(CVAR_AUDIO("Excluded.MySong_-"),0)==1);
    audio.AddToShufflePool(live);
    CHECK(audio.includedSequences.count(live)==1 && audio.excludedSequences.count(live)==0);
    CHECK(CVarGetInteger(CVAR_AUDIO("Excluded.MySong_-"),-1)==-1);
    char late[]="Late_bgm";audio.AddToCollection(late,65003);audio.InitializeShufflePool();
    CHECK(audio.includedSequences.count(&audio.sequenceMap.at(65003))==0);
    CHECK(audio.GetReplacementSequence(NA_BGM_FIELD_MORNING)==NA_BGM_FIELD_MORNING);
    CVarSetInteger(CVAR_AUDIO("ReplacedSequences.NA_BGM_FIELD_LOGIC.value"),65000);
    CHECK(audio.GetReplacementSequence(NA_BGM_FIELD_MORNING)==65000);
    CHECK(audio.GetReplacementSequence(NA_BGM_FIELD_LOGIC)==65000);
    CVarSetInteger(CVAR_AUDIO("ReplacedSequences.NA_BGM_FIELD_LOGIC.value"),65535);
    CHECK(audio.GetReplacementSequence(NA_BGM_FIELD_MORNING)==NA_BGM_FIELD_LOGIC);
    CVarSetInteger(CVAR_AUDIO("ReplacedSequences.NA_BGM_FIELD_LOGIC.value"),65536+65000);
    CHECK(audio.GetReplacementSequence(NA_BGM_FIELD_LOGIC)==65000);
    Notification::Options notice=MakeSongNotification("Track");
    CHECK(notice.message=="Currently playing: Track" && notice.remainingTime==5.0f);
    CHECK(notice.id==0 && notice.itemIcon==nullptr && !notice.mute);
    CHECK(notice.prefix.empty() && notice.suffix.empty());
    CHECK(notice.prefixColor.x==0.5f && notice.messageColor.x==0.7f && notice.suffixColor.x==1.0f);
    CVarSetInteger(CVAR_AUDIO("SeqNameOverlayDuration"),11);
    CHECK(MakeSongNotification("Other").remainingTime==11.0f);
    printf("pool:%zu/%zu; custom:%zu; defaults/replacement/notification passed\n",audio.includedSequences.size(),audio.excludedSequences.size(),audio.SequenceMapSize());
    return 0;
}
